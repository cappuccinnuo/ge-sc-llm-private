"""Verify CP4 coverage and scores, source boundaries, test receipts and frozen DFG identities."""
import ast
from collections import Counter, defaultdict
import difflib
from pathlib import Path
import subprocess
import sys
import time

from batch import ART, BASE, OUT, ROOT, checked, frozen, json, load, receipt_rows, save, sha
from audit_samples import json_lines, key


def source_lines(text):
    owners=defaultdict(lambda: "<module>")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef):
            for line in range(node.lineno-1,node.end_lineno):
                owners[line]=node.name
    return owners


def diff_stats(old,new):
    left,right=source_lines(old),source_lines(new)
    result=defaultdict(Counter)
    for kind,a,b,c,d in difflib.SequenceMatcher(None,old.splitlines(),new.splitlines(),autojunk=False).get_opcodes():
        if kind!="equal":
            for line in range(a,b):result[left[line]]["removed"]+=1
            for line in range(c,d):result[right[line]]["added"]+=1
    return result


def verify_scope():
    module=ROOT/"compile_repair"
    paths=list(module.glob("*.py"))
    for folder in ["core","toolchain","rules","evaluation","rag","agents"]:
        paths.extend((module/folder).rglob("*.py"))
    modules={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    old=json.loads(frozen(ART/"cp3_2_v1/verification.json"))["production_sha256"]
    assert len(modules)==17 and set(modules)-set(old)=={"compile_repair/evaluation/benchmark.py"}
    changed={k for k,v in modules.items() if old.get(k)!=v}
    assert changed=={"compile_repair/cli.py","compile_repair/core/provenance.py","compile_repair/evaluation/benchmark.py"}
    functions={}
    for path in sorted(changed):
        previous=subprocess.check_output(["git","show",BASE+":"+path],cwd=str(ROOT)).decode() if path in old else ""
        current=(ROOT/path).read_text()
        if path.endswith("/provenance.py"):assert current.startswith(previous)
        functions[path]=diff_stats(previous,current)
    run=load("execution_settings.json")
    snapshots={}
    for name,digest in run["implementation"].items():
        snapshot=checked(Path(run["snapshot"])/Path(name).name,digest)
        final=(ROOT/name).read_bytes()
        assert final.startswith(snapshot)
        appended=ast.parse(final[len(snapshot):].decode()).body
        original_names={node.name for node in ast.parse(snapshot.decode()).body if hasattr(node,"name")}
        assert all(isinstance(node,ast.FunctionDef) and node.name not in original_names for node in appended)
        snapshots[name]=dict(executed_bytes=len(snapshot),executed_sha256=digest,final_bytes=len(final),
                             final_sha256=sha(final),identical_execution_prefix=True,only_new_functions=[node.name for node in appended])
    outside=subprocess.check_output(["git","diff","--name-only",BASE,"--",".",":(exclude)compile_repair"],cwd=str(ROOT))
    earlier=subprocess.check_output(["git","diff","--name-only",BASE,"--","compile_repair/artifacts",
                                     ":(exclude)compile_repair/artifacts/cp4_v1"],cwd=str(ROOT))
    assert not outside and not earlier
    source="import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"
    refs=json.loads(subprocess.check_output(["/home/zhao/miniconda3/envs/mando/bin/python","-B","-c",source],cwd=str(ROOT)))
    assert refs==json.loads(frozen(ART/"cp3_continue_v1/baseline.json"))["code_refs"]
    return dict(production_before=len(old),production_after=len(modules),production_sha256=modules,
                changes_by_function=functions,execution_sources=snapshots,frozen_dfg_code_refs=len(refs),changed_old_artifacts=[],changed_outside_module=[])


def main():
    start=time.monotonic()
    aggregate=load("benchmark_counts.json")
    exact=load("inverse_acceptance.json")
    assert sha((OUT/"inverse_scores.jsonl").read_bytes())==exact["scores_sha256"]
    assert sha((OUT/"inverse_graphs.jsonl").read_bytes())==exact["graphs_sha256"]
    expected={key(r):r["mutation_sha256"] for r in json_lines(OUT/"sample_receipts.jsonl") if r["outcome"]=="included"}
    original_scores=list(json_lines(OUT/"inverse_scores.jsonl"))
    original_graphs=list(json_lines(OUT/"inverse_graphs.jsonl"))
    assert len(original_graphs)==exact["unique_bases"] and len(original_scores)==exact["scored"]
    scores=list(original_scores)
    graphs={r["unit_id"]:r for r in original_graphs}
    if not exact["passed"]:
        auth=load("restoration_identity_authorization.json")
        checked(OUT/"restoration_identity_request.json",auth["request_sha256"])
        continuation=load("identity_continuation/acceptance.json")
        probe=load("identity_continuation/probe.json")
        assert continuation["passed"] and probe["passed"] and probe["graph_bytes_equal"] and probe["score"]["score"]["exact"]
        assert key(exact["first_failure"])==key(probe["score"])==(auth["probe_operator"],auth["probe_unit"])
        scores=[r for r in original_scores if r["score"]["exact"]]
        graphs={r["unit_id"]:r for r in original_graphs if r["unit_id"]!=auth["probe_unit"]}
        assert len(scores)==auth["reuse_original_passing_scores"] and len(scores)+1==len(original_scores)
        for kind in ["scores","graphs"]:
            name="identity_continuation/"+kind+".jsonl.gz"
            checked(OUT/name,continuation[kind+"_sha256"])
            rows=list(receipt_rows(name))
            if kind=="scores":
                assert len(rows)==continuation["scored"]==auth["approved_remaining_total_including_probe"]
                scores.extend(rows)
            else:
                assert len(rows)==continuation["bases"]
                assert not set(graphs)&{r["unit_id"] for r in rows}
                graphs.update({r["unit_id"]:r for r in rows})
    assert len(scores)==exact["expected"]==aggregate["counts"]["included"]
    assert set(graphs)=={uid for _,uid in expected}
    for row in graphs.values():
        result=Path(row["result_path"])
        checked(result,row["result_sha256"]);checked(result.with_name("graph.json"),row["graph_sha256"])
        if "binding_path" in row:
            binding=json.loads(checked(row["binding_path"],row["binding_sha256"]))
            assert binding["old_command_equal"] and binding["source_comparisons"]
            for obs in binding["source_comparisons"]:
                assert obs["bytes_equal_before_and_after"]
                assert checked(obs["canonical_input"],obs["sha256"])==Path(obs["inverse_working_path"]).read_bytes()
    seen=set()
    counts=Counter()
    sources=Counter(r["graph_source"] for r in graphs.values())
    for r in scores:
        k=key(r)
        assert k not in seen and r["mutation_sha256"]==expected[k]
        seen.add(k)
        assert graphs[r["unit_id"]]["graph_sha256"]==r["actual_graph_sha256"]
        s=r["score"]
        assert s["compiled"] and s["exact"] and all(s[name]["ratio"]==1 for name in ("kept","cfg_edges","calls"))
        assert s["lost"]==s["missing_kept"]==s["added"]==0 and s["added_bytes_near_damage"] and s["added_only_in_repair_bytes"]
        for field in ("affected_by_damage","affected_by_deletion","lost","added"):
            counts[field]+=s[field]
        for field in ("kept","cfg_edges","calls"):
            counts[field]+=s[field]["equal" if field=="kept" else "matched"]
    assert seen==set(expected)
    wrong=load("wrong_repairs.json");history=load("analyzer_history.json")
    assert wrong["expected"]==wrong["detected"]==23 and all(r["detected"] and not r["score"]["exact"] for r in wrong["rows"])
    assert {r["operator"] for r in wrong["rows"]}==set(aggregate["operators"])|{"slither_incomplete"}
    assert history["units"]==len({r["unit_id"] for r in history["rows"]})==24 and history["new_tool_calls"]==0
    control=load("control_acceptance.json");base=load("base_summary.json")
    assert control["passed"]==control["expected"]==200 and control["first_mismatch"] is None
    assert base["gates"]["mando_inputs"]==846 and base["gates"]["mando_graphs_equal_v5"]==843
    if (OUT/"relocation_test_authorization.json").is_file():
        audit=load("relocation_test_authorization.json")
        checked(OUT/"production_tests.log",audit["first_test_log_sha256"])
        checked(ROOT/"compile_repair/tests/test_cp1_1.py",audit["test_after_sha256"])
    scope=verify_scope()
    suites={}
    for name in ("production","mando","dfg"):
        fixed=OUT/"test_continuation"/(name+"_tests.json")
        receipt=fixed if fixed.exists() else OUT/(name+"_tests.json")
        item=json.loads(receipt.read_bytes())
        assert item["returncode"]==0
        suites[name]=dict(path=receipt.relative_to(OUT).as_posix(),summary=item["summary"],
            sha256=sha(receipt.read_bytes()),log_sha256=sha(receipt.with_suffix(".log").read_bytes()))
    save("acceptance.json",dict(passed=True,base_commit=BASE,scoring_counts=counts,
        graph_sources=sources,byte_equal_inverse_graphs=sum(r["graph_sha256"]==r["truth_graph_sha256"] for r in graphs.values()),
        unique_inverse_bases=len(graphs),exact_samples=len(seen),wrong_repairs=23,history_units=24,
        scope=scope,suites=suites,elapsed_seconds=round(time.monotonic()-start,3)))
    print("verified",len(seen),"inverse samples;",len(graphs),"graphs;",counts,";",suites)


if __name__=="__main__":
    main()
