"""EP1 CPU gate report, drawn only from completed acceptance receipts."""
import re
from .common import ROOT, read, ref, write, checked
from .ep1_common import OUT


def collect():
    before=read(OUT/"before.json")
    probes=[read(p) for p in sorted((OUT/"probes").glob("*.json"))]
    identities={(r["task_id"],r["profile"],r["fold"]) for r in probes}
    expected={("reentrancy_node","G3R",0),("reentrancy_node","G3R",9),
              ("reentrancy_node","G3R-T",0),("access_control_node","G3R-T",0)}
    assert len(probes)==4 and identities==expected
    for row in probes:
        assert row["optimizer_steps"]==0 and not row["cuda_initialized"] and row["graph_unchanged"]
        if row["profile"]=="G3R":
            assert row["forward_bitwise_equal"] and row["all_parameters_equal"] and row["endpoints_equal"]
            assert row["max_abs"]==0
        else:
            assert row["forward_backward_finite"]
            old=read(ROOT/("scripts/edge_sem/artifacts/ep0_v1/"+row["task_id"]+".json"))
            assert row["relations"]==old["graph_counts"]["typed"]
    tests={}
    for name in ("edge_tests","nodesem_tests","dfg_tests"):
        path=OUT/("execution/"+name+".json");receipt=read(path)
        assert receipt["exit_code"]==0
        counts=re.findall(r"(?m)^(\d+) passed",checked(receipt["log"]).read_text())
        assert len(counts)==1
        tests[name]=dict(passed=int(counts[0]),receipt=ref(path))
    sources=[ROOT/"scripts/edge_sem"/n for n in ("__init__.py","materialize.py","init.py","model.py")]
    sources += [ROOT/"scripts/edge_sem/tests"/n for n in ("test_materialize.py","test_model_equivalence.py")]
    sources += sorted((ROOT/"scripts/edge_sem/recon").glob("ep1_*.py"))
    write(OUT/"summary.json",dict(
        stage="EP1",head=before["head"],prompt=before["prompt"],gate_pass=True,
        tests=tests,test_total=sum(r["passed"] for r in tests.values()),probes=probes,
        evidence_refs=[ref(p) for p in sorted((OUT/"probes").glob("*.json"))]+[ref(OUT/"audit_plan.json")],
        source_refs=[ref(p) for p in sources],training_executed=False,gpu_executed=False,
        optimizer_steps=0,graphs_written=0,cf_back=False,
        stop_after="EP1",ep2_r8_decisions_authorized=False,
        historical_ep0e=dict(gate_pass=False,matched=312,candidates=347,retained_as_measured=True),
        limitations=[
            "CPU structural acceptance only; no trained quality or GPU memory conclusion.",
            "dfg_profile is G3R anchor lineage; typed models need local validation, checkpoint adapter awaits EP7.",
            "Attribute/placebo models are registered but cannot be silently built as plain structural models.",
            "The 8H-bound historical feature view is only a parity fixture, not a new primary-view decision.",
            "Synthetic rename tests and parsing coverage remain separate from this direction/model gate."]))
    print("EP1 CPU gates passed; tests",sum(r["passed"] for r in tests.values()),flush=True)


if __name__=="__main__":
    collect()
