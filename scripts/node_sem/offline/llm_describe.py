"""NS-P7 schema-constrained generation. No graph, facts, labels or training imports."""
import argparse
import datetime
import json
import os
from pathlib import Path
import site
import sys
import time
import threading

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from llm_protocol import VERSION, cache_key, digest, messages, output_schema, parse_response
from asset_registry import checked, read, reference, write
from encode import gpu_lock, GPU_LOCK


from llm_cache import generate_cached


class LlamaBackend:
    def __init__(self, asset, parameters):
        from llama_cpp import Llama
        self.parameters = parameters
        self.mode = "gpu" if parameters["n_gpu_layers"] != 0 else "cpu"
        self.model = Llama(model_path=str(checked(asset["model"])), verbose=False,
            **{k:parameters[k] for k in ("n_ctx","n_gpu_layers","n_batch","n_threads","seed")})

    def generate(self, prompt, schema):
        start = time.monotonic()
        result = self.model.create_chat_completion(messages=prompt,
            response_format={"type":"json_object","schema":schema},
            **{k:self.parameters[k] for k in ("temperature","top_k","seed","max_tokens","repeat_penalty")})
        return dict(content=result["choices"][0]["message"]["content"],
            finish_reason=result["choices"][0]["finish_reason"], usage=result["usage"],
            elapsed_seconds=time.monotonic()-start)


def heartbeat(path, data):
    tmp = Path(path).with_suffix(".tmp")
    tmp.write_text(json.dumps(dict(data, utc=datetime.datetime.now(datetime.timezone.utc).isoformat()), indent=2)+"\n", encoding="utf8")
    os.replace(str(tmp), str(path))


def run(plan_path, assets_path, out, cache_dir=None):
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Run with python -s for environment isolation")
    from llm_assets import load
    plan_path, out = Path(plan_path), Path(out)
    plan = read(plan_path)
    if read(plan_path.with_suffix(".seal.json"))["plan"] != reference(plan_path):
        raise ValueError("Pilot plan seal differs")
    if plan["stage"] != "pilot" or plan["full_generation_authorized"]:
        raise ValueError("This entry point executes only the approved pilot")
    for value in plan["implementation"].values():
        checked(value)
    power = read(checked(plan["power_check"]))
    if not all(power.get(x) for x in ("ac_power", "sleep_disabled", "hibernate_disabled")):
        raise RuntimeError("Power preflight incomplete")
    asset = load(assets_path)
    if reference(assets_path) != plan["assets"]:
        raise ValueError("Plan/asset identity differs")
    manifest = read(checked(plan["inputs"]))
    units = {u["cache_key"]:u for u in map(json.loads, checked(manifest["units"]).read_text(encoding="utf8").splitlines())}
    params = manifest["parameters"]
    if asset["model"]["sha256"] != manifest["asset_sha256"] or params != asset["parameters"]:
        raise ValueError("Prompt/asset parameters differ")
    selected = plan["cache_keys"]
    if len(selected) != len(set(selected)) or set(selected)-set(units):
        raise ValueError("Pilot cache population differs")
    out.mkdir(parents=True, exist_ok=False)
    write(out/"started.json", dict(plan=reference(plan_path), assets=reference(assets_path)))
    cache_dir = Path(cache_dir) if cache_dir is not None else out / "cache"
    started, completed = time.monotonic(), []
    progress = dict(completed=0, total=len(selected), current=None, status="running")
    stopped = threading.Event()
    def beat():
        while not stopped.is_set():
            heartbeat(out/"heartbeat.json",dict(progress,elapsed_seconds=time.monotonic()-started))
            stopped.wait(15)
    thread = threading.Thread(target=beat,daemon=True)
    thread.start()
    try:
        with gpu_lock(GPU_LOCK, "cuda" if params["n_gpu_layers"] != 0 else "cpu"):
            backend = LlamaBackend(asset, params)
            for key in selected:
                progress.update(completed=len(completed),current=key)
                result = generate_cached(units[key], backend, cache_dir, manifest["asset_sha256"], params)
                completed.append(dict(cache_key=key, response=reference(cache_dir/key/"response.json"),
                                      status=result["status"]))
            del backend
        write(out/"completed.json", dict(results=completed, elapsed_seconds=time.monotonic()-started,
            plan=reference(plan_path), optimizer_steps=0))
        progress.update(completed=len(completed),current=None,status="completed")
    except Exception as exc:
        write(out/"failure.json", dict(error=repr(exc), completed=len(completed),
            elapsed_seconds=time.monotonic()-started))
        progress["status"]="failed"
        raise
    finally:
        stopped.set()
        thread.join()
        heartbeat(out/"heartbeat.json",dict(progress,elapsed_seconds=time.monotonic()-started))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--assets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir")
    args = ap.parse_args()
    run(args.plan,args.assets,args.out,args.cache_dir)
