"""Pinned pretrained models: verified downloads from the Hugging Face Hub.

Every model the pipeline loads (the CodeT5+ 770M tokenizer for hcg/dfg tokens, the
CodeT5+ 110M embedding and BGE encoders and the Qwen2.5-Coder GGUF for nodesem) is
registered in ``PINNED`` at a fixed commit, and loaded from the local snapshot directory
``ensure`` returns. The snapshot lives in the standard Hub cache layout
(``<cache>/models--org--name/{blobs,snapshots/<commit>}``), so existing downloads are
reused, but a file only becomes part of it after it has been verified:

* expected size and content hash come from the Hub's file listing at the pinned commit
  (SHA-256 for LFS files, the git blob SHA-1 for regular files);
* the remote size is read from ``HEAD``; a size of 0 there is not trusted (some proxies
  return ``Content-Length: 0`` for ``HEAD``), so it is re-read from the ``Content-Range``
  of a ``Range: bytes=0-0`` request or, failing that, from the length of a full ``GET``;
* the remote ETag must equal the expected hash;
* content is streamed to a temporary file and moved into the cache only if its size and
  hash match. Any failure raises ``HubError`` and leaves nothing new in the cache.

Cached files that fail verification (for example 0-byte configuration files left by an
earlier download) are replaced one by one; files that verify, such as weights, are kept
as they are. Once a snapshot has been verified, a stat record lets later runs skip the
network and the hashing.
"""
import fnmatch
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

PINNED = {
    "codet5p-770m-tokenizer": dict(repo_id="Salesforce/codet5p-770m",
                                   revision="3f7cc6e80aee6612f41253b5ee28f09f86faa35f", weights=False),
    "codet5p-110m-embedding": dict(repo_id="Salesforce/codet5p-110m-embedding",
                                   revision="d9f3a534af4252f04b10cd9f78e05037542d10f6", weights=True),
    "bge-small-en-v1.5": dict(repo_id="BAAI/bge-small-en-v1.5",
                              revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", weights=True),
    "qwen2.5-coder-3b-instruct-gguf": dict(
        repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", revision="f74adce6aa16316c625447af059dbebe4983757c",
        files={"qwen2.5-coder-3b-instruct-q4_k_m.gguf":
               (2104932800, "724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7")}),
}

# Never needed by PyTorch loading: other frameworks' weights and exported formats.
EXCLUDE = ("onnx/*", "openvino/*", "coreml/*", "*.onnx", "*.onnx_data", "*.h5", "*.msgpack", "*.ot",
           "*.tflite", "tf_model*", "flax_model*", "rust_model*", ".gitattributes", "*.md", "*.png", "*.jpg")
WEIGHTS = ("*.safetensors", "*.bin", "*.pt", "*.pth", "*.ckpt", "*.gguf")
RECORD = ".mando-verified.json"
CHUNK = 1 << 20


class HubError(RuntimeError):
    """A pinned file could not be fetched or verified; nothing unverified was cached."""


@dataclass(frozen=True)
class FileMeta:
    path: str
    size: int
    kind: str      # "lfs": digest is SHA-256; "git": digest is the git blob SHA-1
    digest: str


def endpoint():
    return os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")


def default_cache():
    try:
        from huggingface_hub import constants
        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        return Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"


def session():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "mando-llm-pinned-models/1"
    token = os.environ.get("HF_TOKEN")
    if token:
        s.headers["Authorization"] = "Bearer " + token
    return s


def spec_for(repo_id, revision):
    for name, spec in PINNED.items():
        if spec["repo_id"] == repo_id and spec["revision"] == revision:
            return name, spec
    raise HubError("%s@%s is not a pinned model (register it in hcg.sources.models.PINNED)" % (repo_id, revision))


def _strip_etag(value):
    value = (value or "").strip()
    if value.startswith("W/"):
        value = value[2:]
    return value.strip('"')


def _hashers(meta):
    if meta.kind == "lfs":
        return hashlib.sha256()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % meta.size)
    return h


def _file_digest(path, meta):
    h = _hashers(meta)
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _get(sess, method, url, **kwargs):
    try:
        response = sess.request(method, url, timeout=(30, 300), **kwargs)
    except Exception as error:  # requests.RequestException and lower-level socket errors
        raise HubError("%s %s failed: %s: %s" % (method, url, type(error).__name__, error)) from None
    return response


def listing(spec, sess):
    """{path: FileMeta} of every file at the pinned commit, from the Hub's JSON API."""
    url = "%s/api/models/%s/revision/%s?blobs=true" % (endpoint(), spec["repo_id"], spec["revision"])
    response = _get(sess, "GET", url)
    if response.status_code != 200:
        raise HubError("GET %s returned HTTP %d" % (url, response.status_code))
    try:
        info = response.json()
    except ValueError:
        raise HubError("GET %s did not return JSON (%d bytes)" % (url, len(response.content))) from None
    if info.get("sha") != spec["revision"]:
        raise HubError("%s: the Hub resolved revision %s, expected %s" % (spec["repo_id"], info.get("sha"),
                                                                           spec["revision"]))
    files = {}
    for sibling in info.get("siblings") or []:
        lfs = sibling.get("lfs")
        if lfs:
            meta = FileMeta(sibling["rfilename"], int(lfs["size"]), "lfs", lfs["sha256"])
        elif sibling.get("blobId") is not None and sibling.get("size") is not None:
            meta = FileMeta(sibling["rfilename"], int(sibling["size"]), "git", sibling["blobId"])
        else:
            raise HubError("%s: no size/hash for %s in the listing" % (spec["repo_id"], sibling.get("rfilename")))
        files[meta.path] = meta
    if not files:
        raise HubError("%s@%s: empty file listing" % (spec["repo_id"], spec["revision"]))
    return files


def select(files, spec):
    """The files a pinned model needs (PyTorch loading only)."""
    if "files" in spec:
        chosen = {}
        for path, (size, sha256) in spec["files"].items():
            meta = files.get(path)
            if meta is None or meta.size != size or meta.kind != "lfs" or meta.digest != sha256:
                raise HubError("%s: listing of %s differs from the pinned size/SHA-256" % (spec["repo_id"], path))
            chosen[path] = meta
        return chosen
    keep = {p: m for p, m in files.items() if not any(fnmatch.fnmatch(p, x) for x in EXCLUDE)}
    if not spec["weights"]:
        keep = {p: m for p, m in keep.items() if not any(fnmatch.fnmatch(p, w) for w in WEIGHTS)}
    elif any(p.endswith(".safetensors") for p in keep):
        # transformers loads safetensors when both formats exist
        keep = {p: m for p, m in keep.items() if not (p.endswith(".bin") and "model" in Path(p).name)}
    return keep


def remote_size_and_etag(url, sess):
    """(size, etag) of a resolve URL. HEAD first; a size of 0 there is confirmed with GET."""
    head = _get(sess, "HEAD", url, allow_redirects=False)
    if head.status_code not in (200, 301, 302, 303, 307, 308):
        raise HubError("HEAD %s returned HTTP %d" % (url, head.status_code))
    size = head.headers.get("X-Linked-Size") or head.headers.get("Content-Length")
    etag = _strip_etag(head.headers.get("X-Linked-Etag") or head.headers.get("ETag"))
    size = int(size) if size not in (None, "") else None
    if not size:
        probe = _get(sess, "GET", url, headers={"Range": "bytes=0-0"}, allow_redirects=True, stream=True)
        try:
            for headers in [r.headers for r in probe.history] + [probe.headers]:
                etag = etag or _strip_etag(headers.get("X-Linked-Etag") or headers.get("ETag"))
            content_range = probe.headers.get("Content-Range", "")
            if probe.status_code == 206 and "/" in content_range and not content_range.endswith("/*"):
                size = int(content_range.rsplit("/", 1)[1])
            elif probe.status_code == 416 and content_range.startswith("bytes */"):
                size = int(content_range.rsplit("/", 1)[1])
            elif probe.status_code == 200:
                size = sum(len(block) for block in probe.iter_content(CHUNK))
            else:
                raise HubError("GET %s (Range) returned HTTP %d" % (url, probe.status_code))
        finally:
            probe.close()
    if not etag:
        raise HubError("%s: no ETag in the responses; the file cannot be verified" % url)
    return size, etag


def _download(url, meta, blob, sess):
    """Stream to <blob>.incomplete, verify size and hash, then move to <blob>."""
    temp = blob.with_name(blob.name + ".incomplete")
    temp.unlink(missing_ok=True)
    h, written = _hashers(meta), 0
    response = _get(sess, "GET", url, allow_redirects=True, stream=True)
    try:
        if response.status_code != 200:
            raise HubError("GET %s returned HTTP %d" % (url, response.status_code))
        declared = response.headers.get("Content-Length")
        if declared not in (None, "", "0") and int(declared) != meta.size:
            raise HubError("GET %s declares %s bytes, expected %d" % (url, declared, meta.size))
        try:
            with open(temp, "wb") as out:
                for block in response.iter_content(CHUNK):
                    out.write(block)
                    h.update(block)
                    written += len(block)
        except HubError:
            raise
        except Exception as error:
            raise HubError("GET %s interrupted after %d bytes: %s" % (url, written, error)) from None
        if written != meta.size:
            raise HubError("%s: received %d bytes, expected %d" % (url, written, meta.size))
        if h.hexdigest() != meta.digest:
            raise HubError("%s: content hash %s, expected %s" % (url, h.hexdigest(), meta.digest))
        os.replace(temp, blob)
    finally:
        response.close()
        temp.unlink(missing_ok=True)


def _stat(path):
    st = path.stat()
    return [st.st_size, st.st_mtime_ns, st.st_ino]


def _read_record(snapshot):
    try:
        return json.loads((snapshot / RECORD).read_text())
    except (OSError, ValueError):
        return None


def _record_valid(record, snapshot, spec):
    if not record or record.get("revision") != spec["revision"] or not record.get("files"):
        return False
    for path, entry in record["files"].items():
        target = snapshot / path
        try:
            if _stat(target.resolve(strict=True)) != entry["stat"]:
                return False
        except (OSError, KeyError):
            return False
    return True


def ensure(repo_id, revision, cache_dir=None, sess=None, log=None):
    """Local directory of a pinned model snapshot whose every needed file is verified."""
    name, spec = spec_for(repo_id, revision)
    cache = Path(cache_dir) if cache_dir else default_cache()
    repo = cache / ("models--" + repo_id.replace("/", "--"))
    snapshot = repo / "snapshots" / revision
    if _record_valid(_read_record(snapshot), snapshot, spec):
        return snapshot
    sess = sess or session()
    needed = select(listing(spec, sess), spec)
    (repo / "blobs").mkdir(parents=True, exist_ok=True)
    snapshot.mkdir(parents=True, exist_ok=True)
    record, repaired, fetched = {}, [], []
    for path, meta in sorted(needed.items()):
        target, blob = snapshot / path, repo / "blobs" / meta.digest
        if target.exists() and target.stat().st_size == meta.size and _file_digest(target, meta) == meta.digest:
            record[path] = dict(size=meta.size, digest=meta.digest, stat=_stat(target.resolve()))
            continue
        if target.exists() or target.is_symlink():
            repaired.append("%s (%d bytes, expected %d)" % (path, target.stat().st_size if target.exists() else -1,
                                                           meta.size))
            target.unlink()
        if not (blob.is_file() and blob.stat().st_size == meta.size and _file_digest(blob, meta) == meta.digest):
            url = "%s/%s/resolve/%s/%s" % (endpoint(), repo_id, revision, path)
            size, etag = remote_size_and_etag(url, sess)
            if size != meta.size:
                raise HubError("%s: remote size %d, listing says %d" % (url, size, meta.size))
            if etag != meta.digest:
                raise HubError("%s: remote ETag %s, expected %s" % (url, etag, meta.digest))
            _download(url, meta, blob, sess)
            fetched.append(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(os.path.relpath(blob, target.parent))
        record[path] = dict(size=meta.size, digest=meta.digest, stat=_stat(blob))
    tmp = snapshot / (RECORD + ".tmp")
    tmp.write_text(json.dumps(dict(model=name, repo_id=repo_id, revision=revision, files=record,
                                   verified=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), indent=1))
    os.replace(tmp, snapshot / RECORD)
    if log and (repaired or fetched):
        log("%s@%s: fetched %d file(s)%s" % (repo_id, revision[:8], len(fetched),
                                              "; repaired " + ", ".join(repaired) if repaired else ""))
    return snapshot


def ensure_all(cache_dir=None, log=print):
    """Fetch and verify every pinned model; {name: snapshot directory}."""
    return {name: ensure(s["repo_id"], s["revision"], cache_dir, log=log) for name, s in PINNED.items()}


def diagnose(name="bge-small-en-v1.5", path="config.json", out=print):
    """Show what HEAD, a 1-byte Range GET and a full GET report for one file, through the
    configured proxy (if any) and directly, to locate the layer that rewrites Content-Length."""
    import requests
    spec = PINNED[name]
    url = "%s/%s/resolve/%s/%s" % (endpoint(), spec["repo_id"], spec["revision"], path)
    keys = ("Content-Length", "Content-Range", "ETag", "X-Linked-Size", "X-Linked-Etag", "Location", "Via",
            "Server", "X-Cache", "X-Amz-Cf-Pop", "X-Proxy-Id", "Proxy-Connection")
    proxies = {k: os.environ[k] for k in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY") if os.environ.get(k)}
    out("URL %s\nproxy variables: %s" % (url, proxies or "none"))
    for label, trust_env in (("configured (proxy variables, CA bundle)", True), ("direct (no proxy variables)", False)):
        s = requests.Session()
        s.trust_env = trust_env
        out("\n== %s" % label)
        for method, kwargs in (("HEAD", dict(allow_redirects=False)),
                               ("GET Range: bytes=0-0", dict(headers={"Range": "bytes=0-0"})),
                               ("GET", {})):
            try:
                response = s.request(method.split()[0], url, timeout=30, **kwargs)
                body = len(response.content)
                out("%-22s HTTP %d, body %d bytes" % (method, response.status_code, body))
                for k in keys:
                    if k in response.headers:
                        out("    %-16s %s" % (k, response.headers[k]))
            except Exception as error:
                out("%-22s failed: %s: %s" % (method, type(error).__name__, error))
