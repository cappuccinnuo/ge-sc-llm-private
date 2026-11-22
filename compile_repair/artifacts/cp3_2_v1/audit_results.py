"""Verify CP3.2 lineage, admission, blockers, unchanged historical files and scope."""
import ast
from collections import Counter, defaultdict
import difflib
import inspect
import json
from pathlib import Path
import subprocess
import time

from aggregate import load_rows
from classify_inputs import BATCH, write_json
from input_census import ART, BASE, OLD, ROOT, digest, frozen
from compile_repair.evaluation.report import classify_record, primary_causes
from compile_repair.toolchain.project import solidity_snippet_evidence

start=time.monotonic()
before=load_rows(frozen(OLD))
after=load_rows((BATCH/"unit_attributions.jsonl.gz").read_bytes())
changes=json.loads((BATCH/"replacement_provenance.json").read_bytes())["rows"]
labels=load_rows((BATCH/"language_classifications.jsonl.gz").read_bytes())
s=json.loads((BATCH/"failure_summary.json").read_bytes())
orig_rule_file=subprocess.check_output(
    ["git","show",BASE+":compile_repair/evaluation/survey.py"],cwd=str(ROOT)).decode()
def old_rule_text(source):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="solidity_snippet_evidence")
    return ast.get_source_segment(source,node)
assert old_rule_text(orig_rule_file)==inspect.getsource(solidity_snippet_evidence).rstrip()
assert set(before)<=set(after) and set(labels)==set(after)
verified_bytes=0
for uid,old in before.items():
    ref=old["selected_result"]
    data=Path(ref["result_path"]).read_bytes()
    assert digest(data)==ref["result_sha256"],uid
    verified_bytes+=len(data)
    result=after[uid]
    if uid in changes:
        assert changes[uid]["old"]==ref and changes[uid]["new"]==result["selected_result"]
    else:
        for k in ("unit_id","corpus","entry_sha256","source","status","any_categories","primary","selected_result"):
            assert old[k]==result[k],(uid,k)
    if result["primary"]["categories"]==["version_dependent"]:
        record=json.loads(data)
        prim=primary_causes(record,classify_record(record))
        assert prim==result["primary"],uid
        surviving=[v for v in prim["by_version"].values() if "parser_error_other" not in v and "unbalanced_structure" not in v]
        expect=sorted(c for c in set(surviving[0]) if all(c in group for group in surviving)) if surviving else []
        assert expect==result["parseable_blockers"],uid

def line_map(source):
    mapping=defaultdict(lambda:"module")
    for n in ast.walk(ast.parse(source)):
        if isinstance(n,ast.FunctionDef):
            mapping.update({line:n.name for line in range(n.lineno-1,n.end_lineno)})
    return mapping

def changes_by_function(path):
    old=subprocess.check_output(["git","show",BASE+":"+str(path.relative_to(ROOT))],cwd=str(ROOT)).decode()
    new=path.read_text()
    om,nm=line_map(old),line_map(new)
    counts=defaultdict(Counter)
    for op,a,b,c,d in difflib.SequenceMatcher(None,old.splitlines(),new.splitlines(),autojunk=False).get_opcodes():
        if op!="equal":
            for i in range(a,b):counts[om[i]]["removed"]+=1
            for i in range(c,d):counts[nm[i]]["added"]+=1
    return counts

pre=json.loads((BATCH/"scope_check.json").read_bytes())
modules={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in (ROOT/"compile_repair").rglob("*.py")
         if not {"tests","artifacts"} & set(p.relative_to(ROOT).parts)}
assert len(modules)==16 and modules.keys()==pre["production_sha256"].keys()
updated={k for k,v in modules.items() if v!=pre["production_sha256"][k]}
assert updated=={"compile_repair/"+r for r in ("toolchain/project.py","pipeline.py","evaluation/survey.py","evaluation/report.py")}
modified={r:changes_by_function(ROOT/r) for r in sorted(updated)}
frozen_changes=subprocess.check_output(["git","diff","--name-only",BASE,"--",".",":(exclude)compile_repair"],
                                       cwd=str(ROOT)).decode().splitlines()
old_artifact_changes=subprocess.check_output(["git","diff","--name-only",BASE,"--","compile_repair/artifacts",
    ":(exclude)compile_repair/artifacts/cp3_2_v1"],cwd=str(ROOT)).decode().splitlines()
assert not frozen_changes and not old_artifact_changes
code_ref_query="import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"
refs=json.loads(subprocess.check_output(["/home/zhao/miniconda3/envs/mando/bin/python","-B","-c",code_ref_query],cwd=str(ROOT)))
assert refs==json.loads(frozen(ART/"cp3_continue_v1/baseline.json"))["code_refs"]
suite={n:json.loads((BATCH/(n+"_tests.json")).read_bytes()) for n in ("production","mando","dfg")}
assert all(r["returncode"]==0 for r in suite.values())
assert s["old_basis"]["primary"]["category_unit_counts"]==json.loads(frozen(ART/"cp3_1_v1/failure_summary.json"))["primary"]["category_unit_counts"]
block=s["version_dependent_blockers"]
wrapper_review=json.loads(frozen(ART/"cp3_1_review_v1/probe_wrapper_detect.json"))
trace=labels["cp3_23864"]["wrapper"]
assert {k:trace[k] for k in ("source_count","settings_keys")}==wrapper_review["trace_cp3_23864"]
mando=[r for r in labels.values() if r["corpus"]=="MANDO"]
raw_evidence=Counter(r["language"]["basis"] for r in labels.values() if r["language"]["status"]=="non_solidity")
mando_counts=Counter(r["language"]["status"] for r in mando)
assert mando_counts=={"solidity":846}
base_status=Counter(r["status"] for r in before.values())
new_status=Counter("non_solidity_input" if r["language"]["status"]=="non_solidity" else r["status"] for r in after.values())
receipt=dict(passed=True,base_commit=pre["base_commit"],original=len(labels),prior_outcomes=base_status,
    revised_outcomes=new_status,previous_manifest_sha256_verified=len(before),previous_manifest_bytes=verified_bytes,
    preserved_fields_for_unchanged=s["reused"],input_only_replacements=len(changes),corpus_tool_calls=0,
    unchanged_snippet_function_sha256=digest(old_rule_text(orig_rule_file).encode()),mando=mando_counts,
    non_solidity_evidence=raw_evidence,unchanged_trace_wrapper=trace,
    original_diagnostic_rechecks=sum(r["primary"]["categories"]==["version_dependent"] for r in after.values()),
    blocker_units=block["units"],production_files=len(modules),production_sha256=modules,
    changed_lines_by_function=modified,dfg_code_refs_equal=len(refs),changed_frozen_worktree_files=frozen_changes+old_artifact_changes,
    suites={k:v["summary"] for k,v in suite.items()},elapsed_seconds=round(time.monotonic()-start,3))
write_json(BATCH/"verification.json",receipt)
print("canonical manifests",len(before),"bytes",verified_bytes,"production files",len(modules),"DFG refs",len(refs),
      "diagnostic rechecks",receipt["original_diagnostic_rechecks"])
