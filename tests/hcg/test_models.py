"""hcg.sources.models against a simulated Hugging Face Hub (no network)."""
import hashlib
import json
import os

import pytest
from requests.structures import CaseInsensitiveDict

from hcg.sources import models as M

REPO, REV = "BAAI/bge-small-en-v1.5", M.PINNED["bge-small-en-v1.5"]["revision"]
CONFIG = json.dumps({"hidden_size": 384}).encode()
TOKENIZER = json.dumps({"model_max_length": 512}).encode()
WEIGHTS = bytes(range(256)) * 64           # 16 KiB "LFS" file
ONNX = b"onnx weights"


def git_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class Response:
    def __init__(self, status, headers=None, body=b"", history=(), fail_after=None):
        self.status_code, self.headers = status, CaseInsensitiveDict(headers or {})
        self.content, self.history, self.fail_after = body, list(history), fail_after

    def json(self):
        return json.loads(self.content)

    def iter_content(self, chunk):
        if self.fail_after is not None:          # send part of the body, then drop the connection
            yield self.content[:self.fail_after]
            raise ConnectionError("connection reset by peer")
        for start in range(0, len(self.content), chunk):
            yield self.content[start:start + chunk]

    def close(self):
        pass


class FakeHub:
    """Hub API + resolve endpoint. ``head_zero`` mimics the proxy: Content-Length: 0 on HEAD."""

    def __init__(self, head_zero=False, ranges=True, etag=None, corrupt=None, fail=None, cut=None):
        self.files = {"config.json": CONFIG, "tokenizer_config.json": TOKENIZER,
                      "model.safetensors": WEIGHTS, "onnx/model.onnx": ONNX}
        self.lfs = {"model.safetensors", "onnx/model.onnx"}
        self.head_zero, self.ranges, self.etag = head_zero, ranges, etag
        self.corrupt, self.fail, self.cut = corrupt, fail, cut
        self.calls = []

    def digest(self, path):
        data = self.files[path]
        return hashlib.sha256(data).hexdigest() if path in self.lfs else git_sha1(data)

    def request(self, method, url, headers=None, **kwargs):
        self.calls.append((method, url, (headers or {}).get("Range")))
        if "/api/models/" in url:
            siblings = []
            for path, data in self.files.items():
                row = dict(rfilename=path, size=len(data), blobId=git_sha1(data))
                if path in self.lfs:
                    row["lfs"] = dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
                siblings.append(row)
            return Response(200, body=json.dumps(dict(sha=REV, siblings=siblings)).encode())
        path = url.split("/resolve/%s/" % REV, 1)[1]
        if self.fail == path and method == "GET":
            raise ConnectionError("network unreachable")
        data = self.files[path]
        etag = '"%s"' % (self.etag if self.etag is not None else self.digest(path))
        if method == "HEAD":
            if path in self.lfs:   # the Hub redirects LFS files and states size/hash in X-Linked-*
                return Response(302, {"X-Linked-Size": str(len(data)), "X-Linked-Etag": etag, "Location": "cdn"})
            return Response(200, {"Content-Length": "0" if self.head_zero else str(len(data)), "ETag": etag})
        body = self.corrupt if self.corrupt is not None and path == "config.json" else data
        if headers and headers.get("Range") == "bytes=0-0" and self.ranges:
            return Response(206, {"Content-Range": "bytes 0-0/%d" % len(data), "ETag": etag}, body[:1])
        return Response(200, {"Content-Length": str(len(body)), "ETag": etag}, body,
                        fail_after=self.cut if path == "model.safetensors" else None)


def snapshot_dir(cache):
    return cache / ("models--" + REPO.replace("/", "--")) / "snapshots" / REV


def assert_clean(cache):
    """Nothing unverified: no temp files, no record, no wrong blobs."""
    repo = cache / ("models--" + REPO.replace("/", "--"))
    assert not list(repo.rglob("*.incomplete"))
    assert not (snapshot_dir(cache) / M.RECORD).exists()


@pytest.mark.parametrize("ranges", [True, False], ids=["range-get", "full-get"])
def test_head_content_length_zero_is_not_trusted(tmp_path, ranges):
    hub = FakeHub(head_zero=True, ranges=ranges)
    snap = M.ensure(REPO, REV, tmp_path, sess=hub)
    assert (snap / "config.json").read_bytes() == CONFIG
    assert (snap / "tokenizer_config.json").read_bytes() == TOKENIZER
    assert (snap / "model.safetensors").read_bytes() == WEIGHTS
    assert not (snap / "onnx").exists()
    probes = [c for c in hub.calls if c[0] == "GET" and "config.json" in c[1] and c[2] == "bytes=0-0"]
    assert len(probes) == 2   # both small files re-checked their size with a Range GET


def test_successful_download_and_offline_reuse(tmp_path):
    snap = M.ensure(REPO, REV, tmp_path, sess=FakeHub())
    assert json.loads((snap / "config.json").read_text()) == {"hidden_size": 384}
    assert (snap / "model.safetensors").is_symlink()
    record = json.loads((snap / M.RECORD).read_text())
    assert set(record["files"]) == {"config.json", "tokenizer_config.json", "model.safetensors"}

    class Offline:
        def request(self, *args, **kwargs):
            raise AssertionError("verified snapshot must not touch the network")

    assert M.ensure(REPO, REV, tmp_path, sess=Offline()) == snap


def test_zero_byte_cached_config_is_repaired_and_weights_are_kept(tmp_path):
    hub = FakeHub()
    repo = tmp_path / ("models--" + REPO.replace("/", "--"))
    snap, blobs = snapshot_dir(tmp_path), repo / "blobs"
    snap.mkdir(parents=True)
    blobs.mkdir(parents=True)
    # What huggingface_hub left behind: an empty config blob, a correct weights blob.
    (blobs / hub.digest("config.json")).write_bytes(b"")
    (blobs / hub.digest("model.safetensors")).write_bytes(WEIGHTS)
    for path in ("config.json", "model.safetensors"):
        (snap / path).symlink_to(os.path.relpath(blobs / hub.digest(path), snap))
    weights_stat = (blobs / hub.digest("model.safetensors")).stat()

    M.ensure(REPO, REV, tmp_path, sess=hub, log=lambda *a: None)
    assert (snap / "config.json").read_bytes() == CONFIG
    after = (blobs / hub.digest("model.safetensors")).stat()
    assert (after.st_ino, after.st_mtime_ns) == (weights_stat.st_ino, weights_stat.st_mtime_ns)
    assert not any("model.safetensors" in url for _, url, _ in hub.calls)


def test_network_failure_raises_and_caches_nothing(tmp_path):
    with pytest.raises(M.HubError, match="network unreachable"):
        M.ensure(REPO, REV, tmp_path, sess=FakeHub(fail="config.json"))
    assert_clean(tmp_path)
    assert not (snapshot_dir(tmp_path) / "config.json").exists()


def test_interrupted_download_caches_nothing(tmp_path):
    with pytest.raises(M.HubError, match="interrupted"):
        M.ensure(REPO, REV, tmp_path, sess=FakeHub(cut=4096))
    assert_clean(tmp_path)
    blob = tmp_path / ("models--" + REPO.replace("/", "--")) / "blobs" / hashlib.sha256(WEIGHTS).hexdigest()
    assert not blob.exists() and not (snapshot_dir(tmp_path) / "model.safetensors").exists()


def test_wrong_content_raises_and_caches_nothing(tmp_path):
    corrupt = b"{" + b" " * (len(CONFIG) - 1)      # right size, wrong bytes
    with pytest.raises(M.HubError, match="content hash"):
        M.ensure(REPO, REV, tmp_path, sess=FakeHub(corrupt=corrupt))
    assert_clean(tmp_path)
    assert not (snapshot_dir(tmp_path) / "config.json").exists()


@pytest.mark.parametrize("etag", ["0" * 40, ""], ids=["wrong-etag", "no-etag"])
def test_unverifiable_etag_raises(tmp_path, etag):
    with pytest.raises(M.HubError, match="ETag"):
        M.ensure(REPO, REV, tmp_path, sess=FakeHub(etag=etag))
    assert_clean(tmp_path)


def test_listing_selection_rules():
    files = {p: M.FileMeta(p, 1, "git", "x") for p in
             ("config.json", "pytorch_model.bin", "model.safetensors", "onnx/model.onnx", "tf_model.h5",
              "vocab.json", "README.md", "modeling_x.py")}
    assert set(M.select(files, dict(weights=True))) == {"config.json", "model.safetensors", "vocab.json",
                                                        "modeling_x.py"}
    assert set(M.select(files, dict(weights=False))) == {"config.json", "vocab.json", "modeling_x.py"}
    with pytest.raises(M.HubError, match="not a pinned model"):
        M.spec_for("someone/else", "0" * 40)


def test_every_loaded_model_is_pinned_with_the_same_id_and_revision():
    from hcg.features.tokens import REVISION, TOKENIZER
    from nodesem.encode import MODELS
    from nodesem.llm.generate import MODEL
    pins = {(s["repo_id"], s["revision"]) for s in M.PINNED.values()}
    assert (TOKENIZER, REVISION) in pins
    assert {(m["repo_id"], m["revision"]) for m in MODELS.values()} <= pins
    assert (MODEL["repo_id"], MODEL["revision"]) in pins
    gguf = M.PINNED["qwen2.5-coder-3b-instruct-gguf"]["files"][MODEL["filename"]]
    assert gguf == (MODEL["bytes"], MODEL["sha256"])


def test_transformers_loads_from_the_verified_snapshot(tmp_path):
    from transformers import AutoTokenizer
    hub = FakeHub(head_zero=True)
    vocab = "\n".join(["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "transfer", "owner", "msg", "."]) + "\n"
    hub.files = {"config.json": json.dumps({"model_type": "bert"}).encode(),
                 "tokenizer_config.json": json.dumps({"tokenizer_class": "BertTokenizer",
                                                      "do_lower_case": True}).encode(),
                 "vocab.txt": vocab.encode()}
    hub.lfs = set()
    snap = M.ensure(REPO, REV, tmp_path, sess=hub)
    tokenizer = AutoTokenizer.from_pretrained(str(snap))
    assert tokenizer("owner transfer")["input_ids"] == [2, 6, 5, 3]
