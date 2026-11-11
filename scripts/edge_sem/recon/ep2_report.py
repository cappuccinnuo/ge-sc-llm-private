"""EP2 evidence summary, preserving the historical failed EP0e recall gate."""
import re
from collections import Counter
from .common import ROOT,read,write,ref,checked
from .ep2_common import OUT,TASKS


def collect():
    tasks={}
    for task in TASKS:
        manifest=read(OUT/task/"manifest.json")
        audit=read(checked(manifest["audit"]))
        fix=read(OUT/"call_fix"/(task+".json"))
        probe=read(OUT/"probes"/(task+"_G4R_fold0.json"))
        assert fix["summary"]["hard_conditions_pass"] and not fix["summary"]["historical_ep0e_gate_pass"]
        assert all(probe[k] for k in ("empty_matches_typed_bitwise","forward_backward_finite",
            "common_parameters_equal","new_rows_match_relation_seed","repeated_initialization_equal",
            "graph_unchanged","source_file_unchanged"))
        assert probe["optimizer_steps"]==0 and not probe["cuda_initialized"]
        ep0=read(ROOT/("scripts/edge_sem/artifacts/ep0_v1/"+task+".json"))
        counts=audit["counts"]
        tasks[task]=dict(files=len(audit["files"]),edges=manifest["counts_by_relation"],
            counts=counts,statuses=audit["statuses"],reasons=audit["reasons"],call_fix=fix["summary"],
            modifier_resolution=dict(numerator=counts["modifier_resolved"],denominator=counts["modifier_invocations"]),
            resolved_call_projection=dict(numerator=counts["call_resolved"]-audit["statuses"].get("CALL_SITE:not_in_graph",0),
                                           denominator=counts["call_resolved"]),
            ep0_expected={r:ep0["prospective_relations"][r]["unique_forward"] for r in ("MOD_APPLY","CALL_SITE")},
            probe=probe,manifest=ref(OUT/task/"manifest.json"))
    tests={}
    for name in ("edge_tests","nodesem_tests","dfg_tests"):
        path=OUT/"execution"/(name+".json");receipt=read(path)
        assert receipt["exit_code"]==0
        passed=re.findall(r"(?m)^(\d+) passed",checked(receipt["log"]).read_text())
        assert len(passed)==1
        tests[name]=dict(passed=int(passed[0]),receipt=ref(path))
    sources=[ROOT/"scripts/edge_sem"/n for n in ("call_resolve.py","build_f4.py")]
    sources+=sorted((ROOT/"scripts/edge_sem/recon").glob("ep2_*.py"))
    sources += [ROOT/"scripts/edge_sem/tests"/n for n in
        ("test_call_resolve.py","test_call_fix.py","test_build_f4_calls.py","test_build_f4_model.py","fixtures/ep2_calls.sol")]
    evidence=[ref(p) for folder in ("call_fix","reentrancy_node","access_control_node","probes")
              for p in sorted((OUT/folder).rglob("*")) if p.is_file()]
    evidence += [ref(OUT/"decisions.json"),ref(OUT/"decisions_chain.json")]
    write(OUT/"summary.json",dict(stage="EP2",gate_pass=True,tasks=tasks,tests=tests,
        test_total=sum(r["passed"] for r in tests.values()),source_refs=[ref(p) for p in sources],
        evidence_refs=evidence,training_executed=False,gpu_executed=False,optimizer_steps=0,
        graphs_written=0,historical_ep0e_gate_pass=False,stop_after="EP2",ep3_started=False,
        limitations=["Post-result call fix is descriptive, not a rewritten prospective recall gate.",
            "G4R here has MOD_APPLY/CALL_SITE only; GUARDS and edge attributes are not implemented.",
            "CPU structural probes use the EP1 historical feature fixture; no training/view choice.",
            "Unresolved binding and missing exact projection remain explicit; no nearest-node fallback."]))
    print("EP2 summary complete",sum(r["passed"] for r in tests.values()),flush=True)


if __name__=="__main__":collect()
