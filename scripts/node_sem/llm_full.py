"""NS-P7c sealed full-generation schedule; old pilots remain read-only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from .llm_cache_v2 import read, reference, write, generate_cached
from .llm_protocol_v2 import cache_key, template, digest, messages

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "scripts/node_sem/artifacts/llm_v3"
OLD = ROOT / "scripts/node_sem/artifacts/llm_v2"
RUNTIME = ("llm_full.py", "llm_cache_v2.py", "llm_protocol_v2.py",
           "offline/llm_full.py", "offline/llm_describe_v2.py",
           "offline/llm_assets.py", "offline/asset_registry.py", "offline/encode.py")


def checked(value):
    path = Path(value["path"])
    if reference(path) != value:
        raise ValueError("SHA identity differs: " + str(path))
    return path


def jsonl(value):
    return [json.loads(s) for s in checked(value).read_text(encoding="utf8").splitlines()]


def body_status(source):
    from scripts.DFG.frontend import parse, walk
    from .facts_ast import FUNCTIONS
    # Constructors/modifiers are contract members, not valid standalone source.
    # This wrapper is used only to inspect body presence; prompts stay byte-identical.
    tree = parse("contract Evidence {\n" + source + "\n}")
    functions = [n for n in walk(tree.root_node) if n.type in FUNCTIONS]
    if len(functions) != 1:
        raise ValueError("Ambiguous function body evidence")
    return functions[0].child_by_field_name("body") is not None


def skip_no_body(has_body, target_lines):
    return not has_body and not target_lines


def failure_fraction(items):
    called = [x for x in items if x["status"] != "skipped_no_body"]
    failed = sum(x["status"] == "parse_failed" for x in called)
    if any(x["status"] not in ("ok", "parse_failed") for x in called):
        raise ValueError("Unexpected generation status")
    return failed / len(called) if called else 0.0


def result_for(unit, entry, backend, cache, manifest):
    if entry["skip"]:
        return dict(status="skipped_no_body", cache_key=unit["cache_key"],
                    response=None, reused=False)
    old = entry.get("prior_response")
    if old:
        path = checked(old)
        result = generate_cached(unit, None, path.parent.parent,
                                 manifest["asset_sha256"], manifest["parameters"])
        response = old
    else:
        result = generate_cached(unit, backend, cache,
                                 manifest["asset_sha256"], manifest["parameters"])
        response = reference(Path(cache) / unit["cache_key"] / "response.json")
    if (result["parameters"] != manifest["parameters"]
            or result["asset_sha256"] != manifest["asset_sha256"]
            or result["template"] != "describe_v2"):
        raise ValueError("Response execution contract differs")
    return dict(status=result["status"], cache_key=unit["cache_key"],
                response=response, reused=bool(old), cache_hit=result["cache_hit"])


def prepare(base=BASE):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=False)
    oldplan = read(checked(read(OLD / "pilot_plan.seal.json")["plan"]))
    manifest = read(checked(oldplan["inputs"]))
    if manifest["template"] != template("describe_v2"):
        raise ValueError("Frozen template differs")
    for value in oldplan["implementation"].values():
        checked(value)
    units = jsonl(manifest["units"])
    maps = jsonl(manifest["prompt_maps"])
    body = {}
    for row in maps:
        identity = row["function_id"]
        current = body_status(row["restoration"]["original"])
        if identity in body and body[identity] != current:
            raise ValueError("Conflicting body evidence")
        body[identity] = current
    report = read(checked(read(OLD / "pilot_report/report.seal.json")["report"]))
    done = read(checked(report["completed"]))
    prior = {r["cache_key"]: r["response"] for r in done["results"]}
    schedule = []
    for unit in units:
        key = unit["cache_key"]
        if key != cache_key(unit, manifest["asset_sha256"], manifest["parameters"]):
            raise ValueError("Input/cache key differs")
        states = {body[o["function_id"]] for o in unit["occurrences"]}
        if len(states) != 1:
            raise ValueError("Deduplicated prompt has conflicting body presence")
        schedule.append(dict(cache_key=key, has_body=states.pop(),
            skip=skip_no_body(body[unit["occurrences"][0]["function_id"]], unit["target_lines"]),
            priority=any(o["task_id"] == "reentrancy_node" for o in unit["occurrences"]),
            prior_response=prior.get(key)))
    schedule.sort(key=lambda e: (not e["priority"], e["cache_key"]))
    if len(schedule) != 4485 or len({e["cache_key"] for e in schedule}) != len(schedule):
        raise ValueError("Full population differs")
    write(base / "schedule.json", schedule)
    # Evidence/runtime artifacts are preserved byte-for-byte. Installed wheels and
    # backend libraries remain pinned by the existing asset seal, not duplicated.
    inventory = []
    for dirname in ("llm_v1", "llm_v2"):
        for p in sorted((base.parent / dirname).rglob("*")):
            if (p.is_file() and not any(s in p.parts for s in
                    ("backend_runtime", "__pycache__", "downloads", "wheels"))
                    and p.suffix not in (".whl", ".so", ".gguf", ".pyc")):
                inventory.append(reference(p))
    write(base / "old_artifacts.json", inventory)
    docs = {}
    for name in ("HANDOVER.md", "docs/training_changes_2026-10-07.md", "scripts/node_sem/PROGRESS.md"):
        p = ROOT / name
        docs[name] = dict(bytes=p.stat().st_size, sha256=reference(p)["sha256"])
    write(base / "start.json", dict(
        HEAD=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip(),
        prompt=reference(ROOT / "scripts/node_sem/PROMPTS.md"), documents=docs,
        full_generation_authorized=True, authorization="User request NS-P7c and PROMPTS r26",
        prior_pilots_passed=False, preserve_failed_pilot_conclusions=True,
        approved_ridge_alpha=[.01, .1, 1., 10.], ridge_selection="inner_val mean cosine",
        ridge_scaler_and_fit="inner_train only", unseen_type_baseline="not_estimable",
        unverified_is_not_verified_correct=True, HGT_training=False, student_training=False,
        server_final_experiments="Separate server batch with sufficient VRAM; local GPU is development constraint"))
    print(json.dumps(dict(units=len(schedule), skipped=sum(e["skip"] for e in schedule),
        prior_reusable=sum(bool(e["prior_response"]) and not e["skip"] for e in schedule),
        reentrancy_node=sum(e["priority"] for e in schedule), preserved_files=len(inventory)), indent=2))


def seal(base=BASE):
    base = Path(base)
    oldplan = read(checked(read(OLD / "pilot_plan.seal.json")["plan"]))
    schedule = read(base / "schedule.json")
    power = read(base / "power_check.json")
    if not all(power.get(k) for k in ("ac_power", "sleep_disabled", "hibernate_disabled")):
        raise ValueError("Power preflight incomplete")
    plan = dict(version="nodesem-llm-full-v1", stage="full", full_generation_authorized=True,
        input_manifest=oldplan["inputs"], assets=oldplan["assets"],
        old_pilot_plan=reference(OLD / "pilot_plan.json"),
        old_pilot_report=reference(OLD / "pilot_report/pilot_report.json"),
        schedule=reference(base / "schedule.json"), authorization=reference(base / "start.json"),
        old_inventory=reference(base / "old_artifacts.json"), power_check=reference(base / "power_check.json"),
        implementation={n:reference(Path(__file__).parent/n) for n in RUNTIME},
        count=len(schedule), parse_failure_stop_gt=.05,
        parse_failure_denominator="Completed inference units incl validated reused responses; skipped units excluded; checked after each completion",
        priorities="All validated historical responses reusable; new reentrancy_node units first, then others; lexical cache-key order within each",
        generation=template("describe_v2"), training=False, judge=False)
    write(base / "plan.json", plan)
    write(base / "plan.seal.json", dict(plan=reference(base / "plan.json")))
    return plan


def load(base=BASE):
    base = Path(base)
    plan = read(checked(read(base / "plan.seal.json")["plan"]))
    if plan["stage"] != "full" or not plan["full_generation_authorized"] or plan["training"] or plan["judge"]:
        raise ValueError("Not the authorized full describe-only plan")
    for value in plan["implementation"].values():
        checked(value)
    for name in ("schedule", "input_manifest", "assets", "authorization", "power_check", "old_inventory"):
        checked(plan[name])
    if plan["generation"] != template("describe_v2"):
        raise ValueError("Template changed")
    return plan


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("prepare", "seal"))
    ap.add_argument("--out", default=str(BASE))
    a = ap.parse_args()
    prepare(a.out) if a.command == "prepare" else seal(a.out)
