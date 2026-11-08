"""Independent NS-P7 GGUF registry; does not alter the frozen M1/BGE registry."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

from asset_registry import checked, read, reference, write, load_model_entry

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "Pre-trained-model/Qwen2.5-Coder-3B-Instruct-GGUF"
DEFAULT_PARAMETERS = dict(n_ctx=4096, n_gpu_layers=-1, n_batch=128, n_threads=4,
    temperature=0.0, top_k=1, seed=0, max_tokens=2048, repeat_penalty=1.0)


def _register(out, model_dir=MODEL):
    import llama_cpp
    model_dir, out = Path(model_dir), Path(out)
    expected = read(model_dir / "DOWNLOAD_EXPECTED.json")
    model_ref = reference(model_dir / expected["filename"])
    if model_ref["sha256"] != expected["sha256"] or Path(model_ref["path"]).stat().st_size != expected["bytes"]:
        raise ValueError("GGUF differs from pinned official metadata")
    bge_assets = Path(__file__).with_name("assets.json")
    bge = load_model_entry(bge_assets, "bge-small-en-v1.5")
    libs = sorted(Path(llama_cpp.__file__).parent.glob("lib/*"))
    refs = {p.name: reference(p) for p in libs if p.is_file()}
    runtime_root = ROOT / "scripts/node_sem/artifacts/llm_v1/backend_runtime"
    for library in sorted(runtime_root.glob("nvidia/*/lib/*.so*")):
        if library.is_file():
            refs[str(library.relative_to(runtime_root))] = reference(library)
    system = llama_cpp.llama_print_system_info()
    if isinstance(system, bytes):
        system = system.decode("utf8")
    manifest = dict(version="nodesem-llm-assets-v1", model=model_ref,
        model_repository=expected["repo_id"], revision=expected["revision"], size_bytes=expected["bytes"],
        license=reference(model_dir / "LICENSE"), model_card=reference(model_dir / "README.md"),
        backend=dict(name="llama-cpp-python", version=importlib.metadata.version("llama-cpp-python"),
            supports_gpu_offload=bool(llama_cpp.llama_supports_gpu_offload()),
            system_info=system, libraries=refs, library_path=os.environ.get("LD_LIBRARY_PATH", "")),
        bge_registry=reference(bge_assets), bge_asset_sha256=bge["asset_sha256"],
        parameters=DEFAULT_PARAMETERS, implementation={"llm_assets.py": reference(__file__)})
    if not manifest["backend"]["supports_gpu_offload"]:
        raise RuntimeError("Approved CUDA backend lacks GPU support; no silent CPU fallback")
    write(out, manifest)
    write(out.with_suffix(".seal.json"), dict(manifest=reference(out)))
    return manifest


def register(out, model_dir=MODEL):
    from encode import gpu_lock, GPU_LOCK
    # CUDA backend discovery can initialize CUDA; it also takes the shared lock.
    with gpu_lock(GPU_LOCK, "cuda"):
        return _register(out, model_dir)


def load(path):
    path = Path(path)
    if read(path.with_suffix(".seal.json"))["manifest"] != reference(path):
        raise ValueError("LLM asset seal differs")
    data = read(path)
    for key in ("model", "license", "model_card", "bge_registry"):
        checked(data[key])
    for value in data["backend"]["libraries"].values():
        checked(value)
    for value in data["implementation"].values():
        checked(value)
    if importlib.metadata.version("llama-cpp-python") != data["backend"]["version"]:
        raise ValueError("Backend version differs")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    print(json.dumps(register(args.out), indent=2))
