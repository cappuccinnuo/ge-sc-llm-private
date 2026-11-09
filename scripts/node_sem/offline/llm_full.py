"""NS-P7c full controller, reusing the frozen v2 backend and cache protocol."""
import argparse
import datetime
import json
import os
from pathlib import Path
import site
import sys
import threading
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.node_sem.llm_full import load, checked, read, reference, write, jsonl, result_for, failure_fraction
from llm_describe_v2 import LlamaBackend, heartbeat
from llm_assets import load as load_assets
from encode import gpu_lock, GPU_LOCK


def run(base, attempt="run1"):
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Run python -s")
    base = Path(base).resolve()
    plan = load(base)
    manifest = read(checked(plan["input_manifest"]))
    units = {u["cache_key"]: u for u in jsonl(manifest["units"])}
    schedule = read(checked(plan["schedule"]))
    asset = load_assets(checked(plan["assets"]))
    if asset["parameters"] != manifest["parameters"] or asset["model"]["sha256"] != manifest["asset_sha256"]:
        raise ValueError("Asset/input binding differs")
    if set(units) != {e["cache_key"] for e in schedule}:
        raise ValueError("Generation population differs")
    out = base / attempt
    out.mkdir(exist_ok=False)
    receipts = base / "unit_receipts"
    receipts.mkdir(exist_ok=True)
    cache = base / "cache/describe_v2"
    write(out/"started.json", dict(plan=reference(base/"plan.json"), pid=os.getpid(),
          utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), optimizer_steps=0))
    start = time.monotonic()
    results, pending = {}, []
    progress = dict(total=len(schedule), completed=0, current=None, status="running")
    stop = threading.Event()
    def beat():
        while not stop.is_set():
            elapsed = time.monotonic()-start
            n = progress.get("newly_generated", 0)
            heartbeat(out/"heartbeat.json", dict(progress, elapsed_seconds=elapsed,
                eta_seconds=(elapsed/n*progress.get("remaining_inference",0)) if n else None))
            stop.wait(15)
    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    try:
        # Audit/reuse historical or already completed units before loading GPU model.
        for entry in schedule:
            key = entry["cache_key"]
            saved = receipts/(key+".json")
            if saved.exists():
                item = read(checked(read(saved.with_suffix(".seal.json"))["result"]))
                expected = result_for(units[key], entry, None, cache, manifest)
                if {k:v for k,v in item.items() if k != "cache_hit"} != {k:v for k,v in expected.items() if k != "cache_hit"}:
                    raise ValueError("Completed receipt differs")
            elif entry["skip"] or entry["prior_response"]:
                item = result_for(units[key], entry, None, cache, manifest)
                write(saved,item); write(saved.with_suffix(".seal.json"),dict(result=reference(saved)))
            else:
                pending.append(entry)
                continue
            results[key] = item
        def update():
            values = list(results.values())
            progress.update(completed=len(results), reused=sum(x["reused"] for x in values),
                skipped=sum(x["status"]=="skipped_no_body" for x in values),
                parse_failed=sum(x["status"]=="parse_failed" for x in values),
                parse_failure_fraction=failure_fraction(values))
        update()
        progress.update(newly_generated=0,remaining_inference=len(pending))
        if failure_fraction(list(results.values())) > plan["parse_failure_stop_gt"]:
            raise RuntimeError("Overall parse failure rate exceeds 5 percent")
        with gpu_lock(GPU_LOCK, "cuda" if asset["parameters"]["n_gpu_layers"] else "cpu"):
            backend = LlamaBackend(asset, asset["parameters"]) if pending else None
            for entry in pending:
                key = entry["cache_key"]
                progress["current"] = key
                item = result_for(units[key], entry, backend, cache, manifest)
                saved = receipts/(key+".json")
                write(saved,item); write(saved.with_suffix(".seal.json"),dict(result=reference(saved)))
                results[key] = item
                progress["newly_generated"] += 1
                progress["remaining_inference"] -= 1
                update()
                if len(results)%25==0:
                    print(json.dumps(progress),flush=True)
                if failure_fraction(list(results.values())) > plan["parse_failure_stop_gt"]:
                    raise RuntimeError("Overall parse failure rate exceeds 5 percent")
            del backend
        completed = dict(plan=reference(base/"plan.json"),results=[results[e["cache_key"]] for e in schedule],
            elapsed_seconds=time.monotonic()-start, optimizer_steps=0)
        write(out/"completed.json", completed)
        write(out/"completed.seal.json",dict(completed=reference(out/"completed.json")))
        progress.update(current=None,status="completed")
    except Exception:
        write(out/"failure.json",dict(error=traceback.format_exc(),progress=progress,
            automatic_retry=False,elapsed_seconds=time.monotonic()-start))
        progress["status"]="failed"
        raise
    finally:
        stop.set();thread.join()
        heartbeat(out/"heartbeat.json",dict(progress,elapsed_seconds=time.monotonic()-start))


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True);ap.add_argument("--attempt",default="run1")
    a=ap.parse_args();run(a.out,a.attempt)
