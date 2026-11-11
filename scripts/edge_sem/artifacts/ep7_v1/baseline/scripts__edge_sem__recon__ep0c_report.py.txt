"""Collect immutable EP0c audit tables and append the review report."""
import re
from collections import Counter
from .common import ROOT, ref, read, write
from .ep0c_common import OUT, TASKS


def collect():
    data = {t:read(OUT/("calls_"+t+".json")) for t in TASKS}
    tests = {}
    for name in ("edge_tests", "nodesem_tests", "dfg_tests"):
        receipt=read(OUT/("execution/"+name+".json"))
        assert receipt["exit_code"] == 0
        text=(OUT/("execution/"+name+".log")).read_text()
        counts=re.findall(r"(?m)^(\d+) passed",text)
        assert len(counts)==1
        tests[name]=dict(passed=int(counts[0]),receipt=ref(OUT/("execution/"+name+".json")))
    review = {}
    for task,d in data.items():
        rows=d["reference_edges"]
        unresolved=[r for r in rows if r["reference_class"]=="undetermined"]
        reasons=Counter(c["reason"] for r in unresolved for c in r["expression_candidates"])
        review[task]=dict(
            unknown_edges=unresolved,
            unknown_edge_reason_counts=dict(Counter(
                "|".join(sorted(set(c["reason"] for c in r["expression_candidates"])))
                for r in unresolved)),
            unprojected_confirmed=[r for r in rows if r["reference_class"]=="internal_confirmed" and not r["r5_covered"]],
            rebinding_edges=[r for r in rows if r["reference_class"]=="rebinding"],
            additional_statement_edges=[r for r in d["projected_call_sites"] if r["added_vs_ep0"]],
            no_corresponding_hcg_edges=[r for r in d["projected_call_sites"] if r["absent_from_hcg"]],
            typed_exclusions=[r for r in rows if r["reference_class"]=="not_internal"],
            no_expression_edges=[r for r in rows if r["reference_class"]=="no_expression"])
    write(OUT/"gap_review.json",review)
    before=read(OUT/"before.json")
    sources=[ROOT/"scripts/edge_sem/call_resolve.py"]
    sources+=sorted((ROOT/"scripts/edge_sem/recon").glob("ep0c_*.py"))
    sources+=[ROOT/"scripts/edge_sem/tests/test_call_resolve.py"]
    summary=dict(
        task_summaries={t:d["summary"] for t,d in data.items()}, tests=tests,
        test_total=sum(r["passed"] for r in tests.values()),
        gate_pass=all(d["summary"]["gate_pass"] for d in data.values()),
        stop_after="EP0c", no_automatic_ep1=True, training_executed=False,
        evidence_refs=[ref(OUT/("calls_"+t+".json")) for t in TASKS]+[ref(OUT/"gap_review.json")],
        current_source_refs=[ref(p) for p in sources], prior_head=before["head"],
        prompt=before["prompt"],
        limitations=[
            "Conditional projection coverage uses the same resolver to define the reference; no independent call-recall claim.",
            "The r5 coarse per-edge membership list was not supplied; counts compared, all final rows and old EP0b classes retained.",
            "No unary/binary callee binding adapter added; super and same-arity overloads remain unresolved.",
            "Library records identify the target declaration container, not the EVM opcode.",
            "No new graphs or attribute vectors, no label/fold/feature changes."])
    write(OUT/"summary.json",summary)
    print("EP0c report data saved; gate",summary["gate_pass"],"tests",summary["test_total"],flush=True)


if __name__=="__main__":
    collect()
