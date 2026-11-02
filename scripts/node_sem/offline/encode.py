"""NS-P2 frozen code encoding in the separate nodesem environment.

File-only exchange with mando. No DFG/training imports, network requests,
optimizer, or label readers. Run directly: python offline/encode.py ...
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys
import site
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
sys.dont_write_bytecode = True

from asset_registry import checked, load_model_entry, read, reference, sha, write

VERSION = "nodesem-code-encoder-v1"
MODALITY_VERSION = "nodesem-modality-v1"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ASSETS = Path(__file__).with_name("assets.json")
GPU_LOCK = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/.training.lock"


@contextlib.contextmanager
def gpu_lock(path, device):
    """Same nonblocking flock protocol as experiment.run._Lock; no graph imports."""
    if device == "cpu":
        yield
        return
    import fcntl
    # This is the already-existing training lock, never an alternative lock.
    with Path(path).open("r+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("DFG/NodeSem GPU lock is held; encoding refused")
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_texts(path):
    path = Path(path).resolve()
    manifest_path = path.with_name("manifest.json")
    seal = read(manifest_path.with_name("manifest.seal.json"))
    if seal["manifest"] != reference(manifest_path):
        raise ValueError("Text manifest seal differs")
    manifest = read(manifest_path)
    if manifest["version"] != "nodesem-text-v1" or checked(manifest["input_text"]) != path:
        raise ValueError("Unexpected text producer input")
    if manifest["view"] not in ("anonymous", "original"):
        raise ValueError("Unknown view")
    for ref in manifest["implementation"].values():
        checked(ref)
    for ref in manifest["sources"].values():
        checked(ref)
    rows = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    if rows != manifest["rows"] or not rows:
        raise ValueError("Text row identities/order differ")
    keys = [r["row_key"] for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate text row identities")
    for row in rows:
        if hashlib.sha256(row["text"].encode()).hexdigest() != row["text_sha256"]:
            raise ValueError("Text SHA differs")
        if manifest["sources"][row["file"]]["sha256"] != row["source_sha256"]:
            raise ValueError("Text source differs")
    return rows, manifest, reference(manifest_path)


def cache_key(text, asset_digest, max_length, pooling):
    raw = json.dumps([asset_digest, max_length, pooling, text],
                     ensure_ascii=False, separators=(",", ":")).encode("utf8")
    return hashlib.sha256(raw).hexdigest()


def schedule(texts, lengths):
    return sorted(range(len(texts)), key=lambda i: (
        lengths[i], hashlib.sha256(texts[i].encode()).hexdigest()))


def mean_pool(hidden, mask):
    weights = mask.unsqueeze(-1).to(hidden.dtype)
    return (hidden * weights).sum(1) / weights.sum(1).clamp(min=1)


def encode_unique(texts, tokenizer, model, device, max_length, pooling, batch_size, dim):
    import numpy as np
    import torch
    # Lengths are diagnostic and batching metadata, never a model input channel.
    lengths = [len(ids) for ids in tokenizer(texts, truncation=False,
               add_special_tokens=True)["input_ids"]] if texts else []
    order = schedule(texts, lengths)
    result = np.empty((len(texts), dim), dtype=np.float32)
    batches = []
    with torch.inference_mode():
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            batch = tokenizer([texts[i] for i in indices], padding=True, truncation=True,
                              max_length=max_length, return_tensors="pt")
            batch = {key: value.to(device) for key, value in batch.items()}
            output = model(**batch)
            vector = output if pooling == "model_default" else mean_pool(
                output.last_hidden_state, batch["attention_mask"])
            if vector.shape != (len(indices), dim) or not torch.isfinite(vector).all():
                raise ValueError("Non-finite or incorrectly shaped encoder output")
            result[indices] = vector.float().cpu().numpy()
            batches.append(len(indices))
    return result, dict(unique_token_lengths=lengths,
                        truncated_unique=sum(n > max_length for n in lengths),
                        batch_count=len(batches), batch_sizes=batches)


def run(texts_path, model_name, assets_path, max_length, pooling, out,
        device="cuda", batch_size=32, lock_path=GPU_LOCK):
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Run encoder with python -s or PYTHONNOUSERSITE=1 for environment isolation")
    import numpy as np
    started = time.monotonic()
    if max_length <= 0 or batch_size <= 0:
        raise ValueError("Lengths/batch size must be positive")
    output = Path(out).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    rows, text_manifest, text_ref = load_texts(texts_path)
    entry = load_model_entry(assets_path, model_name)
    if model_name not in ("codet5p-110m-embedding", "unixcoder-base"):
        raise ValueError("This M1 entry point does not implement teacher encoding")
    if pooling != entry["pooling"]:
        raise ValueError("Model/pooling mismatch")
    encoder_refs = {"offline/encode.py": reference(__file__),
                    "offline/asset_registry.py": reference(Path(__file__).with_name("asset_registry.py"))}
    output.mkdir(parents=True, exist_ok=False)
    write(output / "started.json", dict(version=VERSION, text_manifest=text_ref,
          assets=reference(assets_path), model=model_name, device=device,
          max_length=max_length, pooling=pooling, batch_size=batch_size, implementation=encoder_refs))
    try:
        with gpu_lock(lock_path, device):
            cache = output / "hf_cache"
            os.environ["HF_HOME"] = str(cache)
            os.environ["HF_MODULES_CACHE"] = str(cache / "modules")
            import torch
            import transformers
            if device != "cpu" and not torch.cuda.is_available():
                raise RuntimeError("CUDA unavailable; no automatic CPU fallback")
            torch.manual_seed(1)
            torch.set_num_threads(2)
            torch.use_deterministic_algorithms(True)
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            torch.backends.cudnn.benchmark = False
            dtype = torch.float16 if device != "cpu" else torch.float32
            # Recheck immediately before loading local custom code and weights.
            entry = load_model_entry(assets_path, model_name)
            tokenizer = transformers.AutoTokenizer.from_pretrained(
                entry["directory"], local_files_only=True, trust_remote_code=True,
                cache_dir=str(cache), use_fast=True)
            model = transformers.AutoModel.from_pretrained(
                entry["directory"], local_files_only=True, trust_remote_code=True,
                cache_dir=str(cache), torch_dtype=dtype, attn_implementation="eager",
                weights_only=True).to(device)
            model.eval()
            model.requires_grad_(False)
            unique, lookup, row_indices = [], {}, []
            for row in rows:
                if not row["text"].strip():
                    row_indices.append(None)
                    continue
                key = cache_key(row["text"], entry["asset_sha256"], max_length, pooling)
                if key not in lookup:
                    lookup[key] = len(unique)
                    unique.append(row["text"])
                row_indices.append(lookup[key])
            first, diagnostics = encode_unique(unique, tokenizer, model, device,
                max_length, pooling, batch_size, entry["dimension"])
            # A full second pass; no result cache is consulted.
            second, again = encode_unique(unique, tokenizer, model, device,
                max_length, pooling, batch_size, entry["dimension"])
            max_error = float(np.max(np.abs(first - second))) if first.size else 0.0
            if diagnostics != again or max_error > 1e-6:
                raise ValueError("Repeated inference exceeds 1e-6 determinism threshold")
            values = np.zeros((len(rows), entry["dimension"]), dtype=np.float32)
            identities = []
            for i, (row, idx) in enumerate(zip(rows, row_indices)):
                if idx is not None:
                    values[i] = first[idx]
                identities.append(dict(
                    row_key=row["row_key"], file=row["file"], node_type=row["node_type"],
                    source_sha256=row["source_sha256"], code_sha256=row["code_sha256"],
                    vector_sha256=hashlib.sha256(values[i].tobytes()).hexdigest(),
                    present=idx is not None))
            # Fail if the input or producer changed during encoding.
            if reference(text_ref["path"]) != text_ref:
                raise ValueError("Text manifest changed during encoding")
            for ref in list(text_manifest["implementation"].values()) + list(encoder_refs.values()):
                checked(ref)
            data = output / ("emb_code_" + model_name + ".npz")
            with data.open("xb") as stream:
                np.savez_compressed(stream, features=values)
            assets = dict(entry["files"])
            assets["registry"] = reference(assets_path)
            assets["registry_seal"] = reference(Path(assets_path).with_suffix(".seal.json"))
            implementations = dict(text_manifest["implementation"])
            implementations.update(encoder_refs)
            lengths = diagnostics["unique_token_lengths"]
            manifest = dict(
                version=MODALITY_VERSION, modality="code", view=text_manifest["view"],
                task_id=text_manifest["task_id"], feature_dtype="float32",
                feature_shape=list(values.shape), data=reference(data), rows=identities,
                profiles=text_manifest["profiles"], sources=text_manifest["sources"],
                input_text=text_manifest["input_text"], text_manifest=text_ref,
                implementation=implementations, assets=assets,
                encoding=dict(version=VERSION, model=model_name, revision=entry["revision"],
                    model_sha256=entry["asset_sha256"], max_length=max_length, pooling=pooling,
                    normalized=entry["normalized"],
                    normalization="model forward F.normalize after projection" if pooling=="model_default"
                                  else "attention-mask mean, no extra normalization",
                    inference_dtype=str(dtype), output_dtype="float32", device=device,
                    torch_version=torch.__version__, transformers_version=transformers.__version__,
                    python_version=sys.version, local_files_only=True, frozen=True,
                    rows=len(rows), nonempty_rows=sum(i is not None for i in row_indices),
                    unique_texts=len(unique), cache_hits=sum(i is not None for i in row_indices)-len(unique),
                    truncated_rows=sum(i is not None and lengths[i]>max_length for i in row_indices),
                    diagnostics=diagnostics, repeat_passes=2,
                    repeat_bitwise=bool(np.array_equal(first.view(np.uint32),second.view(np.uint32))),
                    repeat_max_abs_error=max_error,
                    gpu_lock=str(Path(lock_path).resolve()) if device!="cpu" else None,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated() if device!="cpu" else None,
                    elapsed_seconds=time.monotonic()-started, optimizer_steps=0))
            write(output / "manifest.json", manifest)
            write(output / "manifest.seal.json", dict(manifest=reference(output / "manifest.json")))
            return manifest
    except Exception as exc:
        write(output / "failure.json", dict(error_type=type(exc).__name__,message=str(exc),
              elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--texts",required=True)
    parser.add_argument("--model",required=True)
    parser.add_argument("--assets",default=str(DEFAULT_ASSETS))
    parser.add_argument("--max-length",type=int,default=128)
    parser.add_argument("--pooling",choices=("model_default","mean"),required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--device",choices=("cuda","cpu"),default="cuda")
    parser.add_argument("--batch-size",type=int,default=32)
    args=parser.parse_args()
    result=run(args.texts,args.model,args.assets,args.max_length,args.pooling,args.out,
               args.device,args.batch_size)
    info=result["encoding"]
    print(json.dumps(dict(task=result["task_id"],view=result["view"],
        shape=result["feature_shape"],unique_texts=info["unique_texts"],
        truncated_rows=info["truncated_rows"],repeat_bitwise=info["repeat_bitwise"],
        repeat_max_abs_error=info["repeat_max_abs_error"],
        elapsed_seconds=info["elapsed_seconds"]),indent=2))


if __name__=="__main__":
    main()
