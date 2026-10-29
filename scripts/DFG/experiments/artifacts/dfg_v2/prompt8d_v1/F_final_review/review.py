"""Independent read-only final review of the prepared Prompt 8D F artifacts."""
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.tokens import TokenEncoder
from scripts.DFG.dfg_v2.diagnostics8c.inference import replacement_map, rewrite_code

BASE = ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1"
F = BASE/"F"
OUT = BASE/"F_final_review"
checked_refs = {}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_ref(reference):
    path, expected = reference["path"], reference["sha256"]
    key = (path, expected)
    if key not in checked_refs:
        actual = sha(path)
        assert actual == expected, "Reference SHA mismatch: " + path
        checked_refs[key] = actual
    return Path(path)


def check_refs(value):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            check_ref(value)
        for v in value.values():
            check_refs(v)
    elif isinstance(value, list):
        for v in value:
            check_refs(v)


def array_hash(value):
    return hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest()


def equal(a, b):
    if torch.is_tensor(a) or torch.is_tensor(b):
        return torch.is_tensor(a) and torch.is_tensor(b) and a.dtype == b.dtype and torch.equal(a,b)
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a)==set(b) and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):
        return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    if callable(a) or callable(b):
        return callable(a) and callable(b) and getattr(a,"__func__",a) is getattr(b,"__func__",b)
    return a == b


start=time.monotonic()
plan=read(F/"plan.json")
assert sha(F/"plan.json")==read(F/"plan.seal.json")["plan_sha256"]
check_refs(plan)
assert plan["fit_count"]==170 and len(plan["jobs"])==170
assert len({(j["task_id"],j["fold"],j["seed"],j["profile"]) for j in plan["jobs"]})==170
assert not plan["execution_authorized"] and plan["training_executed"]==0
assert plan["selected_label_policy"] is None and plan["selected_training_seeds"] is None
assert plan["selected_execution_location"] is None
assert plan["proposed_training_seeds"]==[1] and plan["label_policy_default"]=="L-audit"
assert all(not j["execution_authorized"] for j in plan["jobs"])
assert not plan["execution_gate"]["existing_cli_supports_this_plan"]
assert plan["execution_gate"]["local_server_mixing_forbidden"]
assert plan["execution_gate"]["keyword_baseline_binding_pending"] is False
assert sum(j["profile"]=="G0P" for j in plan["jobs"])==20
assert all(plan["tasks"][j["task_id"]]["granularity"]=="node" for j in plan["jobs"] if j["profile"]=="G0P")
authorization=read(F/"authorization_template.json")
assert authorization["execution_authorized"] is False
assert authorization["label_policy"] is authorization["training_seeds"] is authorization["execution_location"] is None
check_refs(authorization)

label_views=read(check_ref(plan["bound_artifacts"]["label_views"]))
old_views=read(check_ref(plan["bound_artifacts"]["node_diagnostic_views"]))
groups=read(check_ref(plan["bound_artifacts"]["groups"]))
members=[sid for g in groups["groups"] for sid in g["members"]]
assert len(members)==len(set(members))==256
group_of={sid:g["group_id"] for g in groups["groups"] for sid in g["members"]}
old_clusters=read(check_ref(plan["bound_artifacts"]["duplicate_clusters"]))
for kind in ("exact","near"):
    for cluster in old_clusters[kind]:
        assert len({group_of[sid] for sid in cluster["members"]})==1
task_checks={}
for tid,t in plan["tasks"].items():
    population=read(check_ref(t["population"]))
    byfile={r["file"]:r for r in population}
    assert len(byfile)==t["files"]
    assert set(byfile)==set(t["original_record"]["graph_files"])
    folds=read(check_ref(t["folds"]))
    assert len(folds["folds"])==t["k_folds"]==(5 if t["granularity"]=="contract" else 10)
    test_seen=collections.Counter()
    roles=("inner_train_files","inner_val_files","outer_test_files")
    role_counts=[]
    for i,split in enumerate(folds["folds"]):
        assert split["fold"]==i
        parts=[set(split[r]) for r in roles]
        assert set.union(*parts)==set(byfile)
        gs=[{byfile[name]["group_id"] for name in part} for part in parts]
        assert all(not parts[a]&parts[b] and not gs[a]&gs[b] for a in range(3) for b in range(a))
        for name in split["outer_test_files"]:test_seen[name]+=1
        if t["granularity"]=="contract":
            assert all({byfile[name]["file_label"] for name in part}=={0,1} for part in parts)
        for role,part in zip(roles,parts):
            sm=split["summary"][role]
            assert sm["files"]==len(part)
            assert sm["positive_files"]==sum(byfile[name]["file_label"] for name in part)
            assert sm["negative_files"]==len(part)-sm["positive_files"]
        role_counts.append({role:len(part) for role,part in zip(roles,parts)})
    assert test_seen==collections.Counter({name:1 for name in byfile})
    labels=label_views[tid]
    assert all(r["L-orig_include"] is True and r["L-orig_target"]==r["orig"] for r in labels)
    if t["granularity"]=="node":
        old={(r["file"],r["original_graph_node_id"]):r for r in old_views[tid]}
        assert len(labels)==len(old)
        assert len({(r["file"],r["original_graph_node_id"]) for r in labels})==len(old)
        for r in labels:
            prior=old[(r["file"],r["original_graph_node_id"])]
            assert r["orig"]==prior["orig"] and r["L-audit_target"]==prior["C1"]
            assert r["L-audit_include"]==prior["C2_include"]
            assert r["source_sha256"]==prior["source_sha256"]
        # Even masked nodes retain their original auxiliary scoring entry.
        assert sum(not r["L-audit_include"] for r in labels)>0
    else:
        assert len(labels)==len(byfile)
        for r in labels:
            assert r["orig"]==r["L-audit_target"]==byfile[r["file"]]["file_label"]
            assert r["L-audit_include"] is True
    task_checks[tid]={"files":t["files"],"groups":t["groups"],"folds":t["k_folds"],
                     "roles":role_counts,"label_rows":len(labels),
                     "audit_masked":sum(not r["L-audit_include"] for r in labels),
                     "original_scoring_included":len(labels)}
assert "ALL original" in plan["label_policies"]["always_report"]
assert plan["statistics"]["holm"]==read(check_ref(plan["bound_artifacts"]["historical_report_spec"]))["statistics"]["holm"]

feature_top=read(check_ref(plan["bound_artifacts"]["feature_views"]))
assert feature_top["orig_inputs_unchanged"] is True
assert sha(F/"features/manifest.json")==read(F/"features/manifest.seal.json")["manifest_sha256"]
feature_counts={}
encoder=None
cache={}
for tid,t in plan["tasks"].items():
    entry=feature_top["task_views"][tid]
    check_refs(entry)
    original=read(entry["original_manifest"]["path"])
    neutral=read(entry["manifest"]["path"])
    check_refs(original);check_refs(neutral)
    assert original["rows"]==neutral["rows"] and original["profiles"]==neutral["profiles"]
    with np.load(entry["original_data"]["path"],allow_pickle=False) as z: ov=z["features"]
    with np.load(entry["data"]["path"],allow_pickle=False) as z: nv=z["features"]
    assert ov.dtype==nv.dtype==np.float32 and ov.shape==nv.shape==(len(original["rows"]),512)
    g=read_graph(check_ref(original["profiles"]["G0"]["graph"]))
    assert list(g)==[r["original_graph_node_id"] for r in original["rows"]]
    if encoder is None:encoder=TokenEncoder(t["original_record"]["feature"])
    maps={}
    for name,source in original["sources"].items():
        raw=check_ref(source["source"]).read_text(encoding="utf8")
        maps[name]=replacement_map(raw) if source["solidifi"] else {}
    changed=0
    for i,row in enumerate(original["rows"]):
        attrs=g.nodes[row["original_graph_node_id"]]
        assert attrs["source_file"]==row["file"] and attrs["node_type"]==row["node_type"]
        assert np.array_equal(np.asarray(attrs["token"]).view(np.uint32),ov[i].view(np.uint32))
        assert array_hash(ov[i])==row["original_vector_sha256"]
        assert array_hash(nv[i])==row["neutral_vector_sha256"]
        code=attrs["code"]
        rewritten,_=rewrite_code(code,maps[row["file"]]) if row["solidifi"] else (code,[])
        assert hashlib.sha256(rewritten.encode()).hexdigest()==row["rewritten_code_sha256"]
        for text in (code,rewritten):
            if text not in cache:cache[text]=encoder(text)
        assert np.array_equal(cache[code].view(np.uint32),ov[i].view(np.uint32))
        assert np.array_equal(cache[rewritten].view(np.uint32),nv[i].view(np.uint32))
        different=not np.array_equal(ov[i].view(np.uint32),nv[i].view(np.uint32))
        assert different==row["feature_changed"]
        if not row["solidifi"]:assert not different
        changed+=different
    feature_counts[tid]={"rows":len(original["rows"]),"changed_features":int(changed),
                         "independent_reencoding_exact":True,"profile_bindings":len(original["profiles"])}
    print(tid+" independently reencoded feature arrays exact",flush=True)
assembly=read(F/"features/assembly_validation.json")
assert assembly["passed"] and not assembly["model_forward_executed"]
assert all(v["original_view_exact_graph"] and v["neutral_assembly_validated"]
           for t in assembly["tasks"].values() for v in t.values())

accepted=read(check_ref(plan["bound_artifacts"]["feature_equivalence"]))
check_refs(accepted)
assert accepted["passed"] and all(accepted["checks"].values())
assert accepted["acceptance_optimizer_steps"]==2 and accepted["formal_fits"]==0
assert accepted["extra_optimizer_steps"]==0 and accepted["schedule_epochs"]==50
original_failed=read(check_ref(accepted["review_of"]))
assert original_failed["passed"] is False
assert original_failed["scheduler_state_equal"] is False
assert all(v for k,v in original_failed["checks"].items() if k!="scheduler_state_equal")
chain=read(F/"acceptance_evidence_verification.json");check_refs(chain)
saved={}
for name in ("original","bound_original_view"):
    directory=F/"equivalence"/name
    result=read(directory/"result.json")
    assert sha(directory/"last.pt")==result["checkpoint_sha256"]["last"]
    saved[name]=torch.load(str(directory/"last.pt"),map_location="cpu")
a,b=saved["original"],saved["bound_original_view"]
for key in ("state_dict","optimizer","scheduler"):
    assert equal(a[key],b[key]), "Independent numerical checkpoint comparison differs: "+key
assert a["state_sha256"]==b["state_sha256"]
assert accepted["checker_sha256"]==sha(ROOT/"scripts/DFG/dfg_v2/benchmark_v2/equivalence.py")

# Review unchanged model/tokenizer/production training bytes against frozen start.
protected=read(BASE/"protected_start.json")
core={}
for path,expected in protected["references"].items():
    relative=str(Path(path))
    if (relative.endswith("/sco_models/model_hgt.py") or relative.endswith("/sco_models/graph_utils.py")
            or relative.endswith("/dfg_v2/tokens.py") or relative.endswith("/dfg_v2/experiment/trainer.py")
            or relative.endswith("/dfg_v2/model.py")):
        assert sha(path)==expected
        core[path]=expected
old_plan=read(check_ref(plan["bound_artifacts"]["historical_plan"]))
for name in ("sco_models/model_hgt.py","sco_models/graph_utils.py",
             "scripts/DFG/dfg_v2/model.py","scripts/DFG/dfg_v2/tokens.py"):
    if name in old_plan["runtime"]:
        assert sha(ROOT/name)==old_plan["runtime"][name]
        core[str(ROOT/name)]=old_plan["runtime"][name]
commands=read(F/"execution_command.json")
tests=read(F/"preparation_tests.command.json")
result={
 "status":"passed_preparation_only","concrete_correctness_blockers":[],
 "reviewer":"Codex independent final F artifact review",
 "plan_sha256":sha(F/"plan.json"),"reference_hashes_checked":len(checked_refs),
 "fit_count":170,"formal_training_executed_in_F":0,"execution_authorized":False,
 "acceptance_optimizer_steps":2,"extra_review_optimizer_steps":0,
 "group_identity_count":len(members),"group_count":len(groups["groups"]),
 "tasks":task_checks,"features":feature_counts,
 "identity_equivalence":{"saved_model_Adam_scheduler_independently_equal":True,
     "same_callable_implementation_and_numeric_scheduler_state":True,
     "original_failed_report_retained":True,"no_numeric_tolerance_relaxed":True},
 "unchanged_core_hashes":core,
 "remaining_authorization_choices":{"label_policy":["L-orig","L-audit"],
     "default_label_policy":"L-audit","training_seeds":"User must choose; default [1]",
     "execution_location":["local","server"]},
 "remaining_execution_gates":plan["execution_gate"],
 "limitations":[
     "This is a sealed preparation, not an implemented grouped-label/G0P training executor.",
     "All-original auxiliary score support is present in labels and required by plan; actual future executor must honor it.",
     "Identity feature equality demonstrated on real reentrancy node G0 for one acceptance epoch; no formal benchmark fit has run.",
     "Grouping removes only known textual duplicate components, not every semantic similarity.",
     "Full fixed-graph forward is transductive and grouped CV is not an independent external dataset."
 ],
 "actual_preparation_command":commands["command_equivalent"],
 "actual_preparation_execution":commands["actual_execution"],
 "actual_test_command":tests["command"],"owned_tests":{"passed":50,"failed":0},
 "local_time_reference_hours":read(F/"timing.json")["local_reference_total_hours"],
 "server_timing":"Unmeasured conditional scenarios only; final server VRAM expected sufficient.",
 "seconds":time.monotonic()-start,
}
with (OUT/"review.json").open("x",encoding="utf8") as stream:
 json.dump(result,stream,indent=2,ensure_ascii=False);stream.write("\n")
command=" \\\n  ".join(commands["command_equivalent"])
md="""# Prompt 8D F final review

Status: passed for preparation only. No concrete correctness blocker was found.

The independent review checked the sealed 170-fit proposal, all referenced input
hashes, 256 source identities / 227 duplicate groups, every role of all 30 grouped
folds, and the original/C1/C2-mask relationship. Every original scoring unit is
retained; L-audit masks loss and its diagnostic score only. Contract labels remain
unchanged.

All 51,490 original and neutral feature rows were independently re-encoded using
the frozen tokenizer and the requested 8C idN rule. Every vector matched exactly.
The saved original and feature-bound one-epoch CPU model, Adam and scheduler
states match exactly. Scheduler callable implementation identity is compared,
not the distinct deserialized bound-object address. The initial failed report is
preserved. This review ran no model forward, optimizer step or formal fit.

The new plan does not claim that the historical trainer can execute grouped
L-audit/G0P tasks. That integration is explicitly a future gate. The original
auxiliary score rule is a preparation requirement and label support, not evidence
that a new grouped executor has already run.

Authorization still requires label policy (default L-audit), training seed set
(default [1]), and location (local or server). No authorization is inferred from
this review. Final server VRAM is expected sufficient; local RTX3050 limits do
not define the final hardware.

## Actual commands and evidence

The actual preparation called prepare_benchmark via the existing WSL mando
interpreter. Its equivalent CLI command is recorded verbatim in
../F/execution_command.json. Owned tests ran the exact command recorded in
../F/preparation_tests.command.json: 50 passed, 0 failed.

The preparation command refuses existing output files. Do not rerun it against
the sealed F directory. Use read-only verification for inspection.

Detailed command arguments, hash checks, partition counts, equality evidence and
remaining execution gates are in review.json. Historical median local timing
reference is 8.2791 hours, not a measured new benchmark duration; server timing is
conditional and unmeasured.
"""
with (OUT/"REVIEW.md").open("x",encoding="utf8") as stream:stream.write(md)
print(json.dumps({"status":result["status"],"hash_refs":len(checked_refs),"feature_rows":sum(v["rows"] for v in feature_counts.values()),"seconds":result["seconds"]},indent=2))
