# Copied from llm_pilot.py SHA256 be831026d735498632e0a84482bcb0b02aa09de7915590dffd439feba54f8ec5.
# NS-P7b sampling/report adapter; v1 stays immutable.
"""NS-P7 predeclared 50-function sample and post-run report; labels only sample here."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics

from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from .llm_protocol_v2 import digest
from .llm_post_v2 import align, gates, role_agreement
from .p3_prepare import write_jsonl

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "scripts/node_sem/artifacts/ns_p6c2"
THRESHOLDS = dict(parse_success_rate=.95, faithfulness_median=.7,
    faithfulness_ge_half_fraction=.8, blacklist_max_fraction=.05,
    external_call_precision=.8, state_update_precision=.8)


def choose(candidates, seed=2):
    rng=random.Random(seed)
    groups=defaultdict(list)
    for c in sorted(candidates,key=lambda c:(c["task_id"],c["cache_key"],c["function_id"])):
        groups[(c["task_id"],c["solidifi"])].append(c)
    tasks=sorted({c["task_id"] for c in candidates})
    if len(tasks)!=4:raise ValueError("Pilot requires four tasks")
    for values in groups.values():rng.shuffle(values)
    quotas={(t,s):7 if t.endswith("_node") and not s else 6 for t in tasks for s in (False,True)}
    selected,used,hashes=[],set(),set()
    def eligible(c):
        return c["cache_key"] not in used and c["function_source_sha256"] not in hashes
    def add(c,g):
        selected.append(c);used.add(c["cache_key"]);hashes.add(c["function_source_sha256"]);quotas[g]-=1
    positive_groups=[(t,False) for t in tasks if t.endswith("_node")]
    for allow_overlap in (False,True):
        while len(selected)<10:
            advanced=False
            for g in positive_groups:
                choices=[c for c in groups[g] if c["positive_function"] and eligible(c)
                         and (allow_overlap or not c["overlap_v1"])]
                if choices and quotas[g]>0 and len(selected)<10:
                    add(choices[0],g);advanced=True
            if not advanced:break
        if len(selected)==10:break
    if len(selected)<10:raise ValueError("Fewer than ten eligible positive source functions")
    for g in sorted(quotas):
        for c in groups[g]:
            if not quotas[g]:break
            if eligible(c) and not c["overlap_v1"]:add(c,g)
        if quotas[g]:raise ValueError("Insufficient nonoverlapping functions in stratum")
    if len(selected)!=50 or sum(not c["solidifi"] for c in selected)<25:raise AssertionError("Sample quota")
    assert all(not c["overlap_v1"] or c["positive_function"] for c in selected)
    return selected


def selection(inputs_path):
    inputs_path=Path(inputs_path)
    inputs = read(inputs_path)
    if read(inputs_path.with_name("manifest.seal.json"))["manifest"] != ref(inputs_path):
        raise ValueError("Input seal differs")
    for value in inputs["implementation"].values():
        checked(value)
    units = [json.loads(s) for s in checked(inputs["units"]).read_text(encoding="utf8").splitlines()]
    old = read(checked(read(OLD / "plan.seal.json")["plan"]))
    rows = {task:[json.loads(s) for s in checked(r).read_text(encoding="utf8").splitlines()]
            for task, r in inputs["tasks"].items()}
    positive, labels_refs, positive_counts = set(), {}, {}
    for task, data in old["tasks"].items():
        if not task.endswith("_node"):
            continue
        pop = read(checked(data["population"]))
        label_ref = pop["signal"]["labels"]
        label_rows = read(checked(label_ref))[task]
        current = {(r["file"], r["row_key"]):r for r in rows[task]}
        count = 0
        for label in label_rows:
            if (label["L-audit_include"] and label["L-audit_target"] == 1
                    and not Path(label["file"]).name.startswith("buggy_")):
                row = current[(label["file"], label["original_graph_node_id"])]
                if label["node_type"] != row["node_type"]:
                    raise ValueError("Sampling label/AST identity mismatch")
                count += 1
                if row["function_id"] is not None:
                    positive.add((task, row["function_id"]))
        expected = 32 if task == "reentrancy_node" else 20
        if count != expected:
            raise ValueError("Sampling positive node count changed")
        positive_counts[task] = count
        labels_refs[task] = label_ref
    candidates = []
    for unit in units:
        for occ in unit["occurrences"]:
            # The real population currently has no >120-line functions.
            # Generic segmentation remains supported by input generation.
            if occ["segment_count"] != 1:
                raise ValueError("Segmented pilot function needs all segments registered")
            candidates.append(dict(occ, cache_key=unit["cache_key"],
                solidifi=Path(occ["file"]).name.startswith("buggy_"),
                positive_function=(occ["task_id"], occ["function_id"]) in positive))

    prior=ROOT/"scripts/node_sem/artifacts/llm_v1"
    first=read(checked(read(prior/"pilot_plan.seal.json")["plan"]))
    first_ids={x["function_id"] for x in first["selected"]}
    original_inputs=read(checked(first["inputs"]))
    maps=map(json.loads,checked(original_inputs["prompt_maps"]).read_text(encoding="utf8").splitlines())
    old_hashes={__import__("hashlib").sha256(m["restoration"]["original"].encode("utf8")).hexdigest()
                for m in maps if m["function_id"] in first_ids}
    for c in candidates:c["overlap_v1"]=c["function_source_sha256"] in old_hashes
    selected=choose(candidates)
    return dict(selected=selected,labels_refs=labels_refs,positive_counts=positive_counts,
        first_plan=ref(prior/"pilot_plan.json"),excluded_function_source_sha256=sorted(old_hashes),
        positive_overlap=[c for c in selected if c["overlap_v1"]],
        source_hash_definition="SHA256 of comment-blanked original function UTF-8 bytes; excludes same function across files/tasks")

def prepare(inputs_path,assets_path,power_path,approval_path,output):
    inputs_path,output=Path(inputs_path),Path(output)
    inputs=read(inputs_path)
    preview=selection(inputs_path)
    profile_path=inputs_path.parent.parent/"token_profile.json"
    profile=read(profile_path)
    if profile["inputs"]!=ref(inputs_path) or profile["assets"]!=ref(assets_path):
        raise ValueError("Token profile input/asset binding differs")
    if profile["pilot_overflow"]:raise ValueError("Fixed pilot exceeds context; no reselection")
    if read(checked(profile["selection"]))!=preview:raise ValueError("Selection changed")
    metric=inputs_path.parent.parent/"metrics_contract.json"
    if read(metric.with_suffix(".seal.json"))["contract"]!=ref(metric):raise ValueError("Metric seal differs")
    for value in read(metric)["implementation"].values():checked(value)
    implementation=dict(read(metric)["implementation"])
    for name in ("llm_inputs_v2.py","llm_pilot_v2.py","llm_cache_v2.py",
                 "offline/llm_describe_v2.py","offline/llm_profile_v2.py",
                 "offline/llm_assets.py","llm_role_review.py"):
        implementation[name]=ref(Path(__file__).parent/name)
    plan=dict(version="nodesem-llm-pilot-v2",stage="pilot",seed=2,selected=preview["selected"],
        cache_keys=[c["cache_key"] for c in preview["selected"]],thresholds=THRESHOLDS,
        role_agreement="external bool and state_update precision; external role union secondary; no denominator => no pass",
        unknown_facts="null faithfulness; absent teacher; counted as not >=0.5",
        inputs=ref(inputs_path),assets=ref(assets_path),token_profile=ref(profile_path),
        power_check=ref(power_path),authorization=ref(approval_path),implementation=implementation,
        metrics_contract=ref(metric),sample_label_refs=preview["labels_refs"],
        sample_positive_nodes=preview["positive_counts"],v1_overlap=preview["positive_overlap"],
        first_plan=preview["first_plan"],source_hash_definition=preview["source_hash_definition"],
        full_generation_authorized=False,optimizer_steps=0,stop="Report 50-function pilot; stop regardless of result")
    write(output,plan);write(output.with_suffix(".seal.json"),dict(plan=ref(output)))
    return plan


def report(plan_path, run_dir, out, purpose="pilot_v2"):
    plan_path, run_dir, out = Path(plan_path), Path(run_dir), Path(out)
    plan = read(checked(read(plan_path.with_suffix(".seal.json"))["plan"]))
    for value in plan["implementation"].values():
        checked(value)
    if purpose not in ("pilot_v2","posthoc_v1"):raise ValueError("Unknown report purpose")
    if (plan["version"]=="nodesem-llm-pilot-v1") != (purpose=="posthoc_v1"):
        raise ValueError("Old pilot can only be post-hoc diagnostic")
    completed = read(run_dir/"completed.json")
    if completed["plan"] != ref(plan_path):
        raise ValueError("Pilot completion belongs to another plan")
    done = {r["cache_key"]: r for r in completed["results"]}
    if set(done) != set(plan["cache_keys"]) or len(done) != len(completed["results"]):
        raise ValueError("Missing or duplicate pilot responses")
    inputs = read(checked(plan["inputs"]))
    units = {u["cache_key"]:u for u in map(json.loads, checked(inputs["units"]).read_text(encoding="utf8").splitlines())}
    task_rows, facts = {}, {}
    for task, reference in inputs["tasks"].items():
        task_rows[task] = [json.loads(s) for s in checked(reference).read_text(encoding="utf8").splitlines()]
        fm = read(checked(inputs["inputs"][task]["facts_manifest"]))
        facts[task] = {r["row_key"]:r["facts"] for r in map(json.loads,checked(fm["facts"]).read_text(encoding="utf8").splitlines())}
    responses, scored, by_fact, detail, examples = [], [], {}, [], []
    for chosen in plan["selected"]:
        cache, task = chosen["cache_key"], chosen["task_id"]
        response = read(checked(done[cache]["response"]))
        path = Path(done[cache]["response"]["path"])
        if read(path.with_suffix(".seal.json"))["response"] != done[cache]["response"]:
            raise ValueError("Response seal differs")
        refs = [r for r in task_rows[task] if r.get("cache_key")==cache and r["function_id"]==chosen["function_id"]]
        output, counters = align(refs, facts[task], units[cache], response)
        for row in output:
            original = row["row_key"]
            row.update(task_id=task, original_row_key=original, solidifi=chosen["solidifi"],overlap_v1=chosen.get("overlap_v1",False))
            row["row_key"] = task + ":" + str(original)
            by_fact[row["row_key"]] = facts[task][original]
        scored.extend(output)
        responses.append(response)
        tokens = {key:sum(a["response"]["usage"].get(key,0) for a in response["attempts"])
                  for key in ("prompt_tokens","completion_tokens","total_tokens")}
        detail.append(dict(chosen, status=response["status"], tokens=tokens,
            elapsed_seconds=response["elapsed_seconds"], counters=counters,
            target_rows=len(refs), response=done[cache]["response"]))
        if len(examples)<5:
            examples.append(dict(selection=chosen, messages=units[cache]["messages"],
                attempts=response["attempts"], postprocessed=output))
    statement_rows = [r for r in scored if r["target_kind"]=="statement"]
    agreement = role_agreement(statement_rows, by_fact)
    gate = gates(scored, responses, agreement)
    cohorts = {}
    for name, flag in (("solidifi",True),("non_solidifi",False)):
        subset = [r for r in statement_rows if r["solidifi"]==flag]
        vals = [r["faithfulness"] for r in subset if r["faithfulness"] is not None]
        cohorts[name] = dict(nodes=len(subset), verifiable=len(vals),
            median=statistics.median(vals) if vals else None,
            valid=sum(r["present"] for r in subset),
            flags=dict(Counter(f for r in subset for f in r["flags"])),
            roles=dict(Counter(r["role"] for r in subset)),
            role_agreement=role_agreement(subset,by_fact))

    overlap_groups={}
    for name,flag in (("new_functions",False),("positive_overlap",True)):
        subset=[row for row in statement_rows if row["overlap_v1"]==flag]
        values=[row["faithfulness"] for row in subset if row["faithfulness"] is not None]
        overlap_groups[name]=dict(functions=sum(c.get("overlap_v1",False)==flag for c in plan["selected"]),
            nodes=len(subset),verifiable=len(values),median=statistics.median(values) if values else None,
            ge_half=sum(v>=.5 for v in values),agreement=role_agreement(subset,by_fact))
    mean_seconds = statistics.mean(d["elapsed_seconds"] for d in detail)
    stats = dict(version="nodesem-llm-pilot-report-v2", purpose=purpose,
        interpretation="Post-hoc remeasurement; cannot pass pilot 1" if purpose=="posthoc_v1" else "Preregistered second pilot", plan=ref(plan_path),
        completed=ref(run_dir/"completed.json"), gates=gate, agreement=agreement,
        strata={k:dict(v) for k,v in ((t,Counter("solidifi" if s["solidifi"] else "non_solidifi"
                 for s in plan["selected"] if s["task_id"]==t)) for t in sorted(task_rows))},
        cohorts=cohorts, overlap_groups=overlap_groups, functions=detail, examples=examples,
        original_pilot_report=ref(ROOT/"scripts/node_sem/artifacts/llm_v1/pilot_report/pilot_report.json"),
        metrics_contract=ref(ROOT/"scripts/node_sem/artifacts/llm_v2/metrics_contract.json"),
        implementation_v2=ref(__file__),acceptance_passed=gate["passed"] if purpose=="pilot_v2" else None,
        full_unique_prompts=len(units), mean_seconds=mean_seconds,
        projected_describe_hours=len(units)*mean_seconds/3600,
        projected_judge_hours_using_describe_rate=len(units)*mean_seconds/3600,
        cost_limitations="50-function stratified sample, not token-weighted; judge adds output and may take longer",
        full_generation_executed=False, teacher_vectors_executed=False,
        teacher_diagnostics_executed=False, HGT_training=0, student_training=0,
        final_server="Final experiments will use a sufficiently provisioned server; this batch is local RTX3050 pilot")
    out.mkdir(parents=True,exist_ok=False)
    write_jsonl(out/"teacher_text_pilot.jsonl",scored)
    write(out/"pilot_report.json",stats)
    write(out/"report.seal.json",dict(report=ref(out/"pilot_report.json"),
        rows=ref(out/"teacher_text_pilot.jsonl")))
    return stats


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    p=sub.add_parser("prepare")
    for key in ("inputs","assets","power","approval","out"):p.add_argument("--"+key,required=True)
    p=sub.add_parser("report")
    for key in ("plan","run","out"):p.add_argument("--"+key,required=True)
    a=ap.parse_args()
    if a.command=="prepare":
        x=prepare(a.inputs,a.assets,a.power,a.approval,a.out)
        print(json.dumps(dict(selected=len(x["selected"]),positive_nodes=x["sample_positive_nodes"]),indent=2))
    else:
        print(json.dumps(report(a.plan,a.run,a.out)["gates"],indent=2))


if __name__=="__main__":main()
