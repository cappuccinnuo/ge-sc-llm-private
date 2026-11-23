"""Compare CP5.1's production scope with the review commit and independently verify completed receipts."""
import ast
import difflib
import json
from pathlib import Path
import subprocess
import sys

from population import ART, LOCAL, OUT, ROOT, load, save, sha256

BASE = "5fe7671fb6ebe6c9393bf41e29c0cfea950861e8"


def functions(data):
    entries = {}
    for node in ast.parse(data).body:
        if isinstance(node, ast.FunctionDef):
            entries[node.name] = ast.dump(node)
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, ast.FunctionDef):
                    entries[node.name+"."+method.name] = ast.dump(method)
    return entries


def main():
    stage = sys.argv[1]
    final = stage == "final"
    module = ROOT/"compile_repair"
    code = sorted(p for p in module.rglob("*.py") if not set(p.relative_to(module).parts) & {"artifacts","docs","tests"})
    assert len(code) == 18
    changed = {}
    for p in code:
        key = p.relative_to(module).as_posix()
        old = subprocess.check_output(["git","show",BASE+":"+p.relative_to(ROOT).as_posix()], cwd=ROOT)
        new = p.read_bytes()
        if old == new:
            continue
        before, after = functions(old), functions(new)
        names=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
        if key=="evaluation/benchmark.py":
            assert before["score_graphs"] == after["score_graphs"] and before["_score_facts"] == after["_score_facts"]
        if key=="toolchain/solc.py":
            assert names == ["validate_settings"]
        added, removed = 0, 0
        for op,a,b,c,d in difflib.SequenceMatcher(None,old.splitlines(),new.splitlines(),autojunk=False).get_opcodes():
            if op!="equal":
                added+=d-c
                removed+=b-a
        changed[key] = dict(functions=names,added=added,removed=removed,sha256=sha256(p))
    assert set(changed)=={"evaluation/benchmark.py","evaluation/report.py","pipeline.py","rules/dependencies.py","toolchain/solc.py"}
    frozen=load(ART/"cp3_continue_v1/baseline.json")["code_refs"]
    now=json.loads(subprocess.check_output(["/home/zhao/miniconda3/envs/mando/bin/python","-B","-c",
        "import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"], cwd=ROOT))
    assert now==frozen
    idx=load(OUT/"index_verification.json")
    assert idx["archives"]==172 and idx["solidity_files"]==13073
    moved=load(OUT/"moved_summary.json")
    assert moved["observations_sha256"]==sha256(OUT/"moved_triggers.jsonl") and moved["inverses_sha256"]==sha256(OUT/"moved_inverse.jsonl")
    assert moved["exact_inverses"]==moved["selected"]==400
    for line in (OUT/"moved_inverse.jsonl").read_bytes().splitlines():
        r=json.loads(line)
        assert r["score"]["compiled"] and r["score"]["exact"] and r["score"]["removed_by_repair"]==0
    mando_dir = OUT/("frozen_mando" if final else "mando_regression")
    mando=load(mando_dir/"summary.json")
    assert mando["passed"] and mando["counts"]==dict(graphs_equal=843,historical_failures=3,steps_on_truths=0)
    assert sha256(mando_dir/"rows.jsonl")==mando["rows_sha256"]
    suites={n:load(OUT/("frozen_suites" if final else "final_suites" if n=="production" else "suites")/(n+"_tests.json"))
            for n in ("production","mando","dfg")}
    assert all(v["returncode"]==0 for v in suites.values())
    result=dict(base=BASE, production_files=len(code),changed=changed,dfg_refs=len(frozen),
         suites=suites, index=idx["seal"], moved_exact=400, mando=mando["counts"], cost_usd=0,llm_calls=0,
         mando_implementation_matches_worktree=all(sha256(ROOT/k)==v for k,v in mando["implementation_sha256"].items()))
    if final:
        from inspect import signature
        from compile_repair.pipeline import repair, repair_unit
        policy=load(OUT/"policy.json")
        completed=load(OUT/"measurement_completion.json")
        for fn in (repair, repair_unit):
            params=signature(fn).parameters
            assert params["dependency_policy"].default==policy["policy"] and params["dependency_limit"].default==policy["limit"]
        assert completed["status"]=="complete" and result["mando_implementation_matches_worktree"]
        assert sha256(ROOT/"compile_repair/pipeline.py")==load(OUT/"policy_application.json")["pipeline_sha256"]
        external=load(OUT/"external_summary.json")
        bench=load(OUT/"benchmark_summary.json")
        assert external["units"]==9138 and bench["units"]==2264+moved["exact_inverses"]
        result.update(frozen_policy=policy["policy"], limit=policy["limit"], benchmarks=bench["units"],
                      real_units=external["units"], d3=external["d3"], truncated=external["truncated"],
                      mechanical={n:load(OUT/(n+"_provenance.json"))["counts"] for n in
                          ("package_dev","real_dev","benchmark","real_full","real_masked")})
    save(OUT/(stage+"_audit.json"),result)
    print("modules",len(code),"DFG refs",len(frozen),"moved",400,"suites",len(suites),flush=True)


if __name__=="__main__":
    main()
