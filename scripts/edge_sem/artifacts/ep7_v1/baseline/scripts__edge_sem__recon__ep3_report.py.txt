"""EP3 machine summary, without changing prior experiments or gate outcomes."""
import re
from .common import ROOT,read,write,ref,checked
from .ep3_common import OUT,TASKS


def collect():
    tasks={}
    for task in TASKS:
        manifest=read(OUT/task/"manifest.json");audit=read(checked(manifest["audit"]))
        probe=read(OUT/"probes"/(task+"_G4R_fold0.json"))
        assert audit["hard_conditions_pass"] and audit["ep2_rows_equal"]
        for flag in ("empty_matches_typed_bitwise","forward_backward_finite",
                     "common_parameters_equal","new_rows_match_relation_seed",
                     "repeated_initialization_equal","graph_unchanged","source_file_unchanged"):
            assert probe[flag]
        assert not probe["cuda_initialized"] and probe["optimizer_steps"]==0
        g=audit["guards"]
        tasks[task]=dict(files=len(audit["files"]),edges=manifest["counts_by_relation"],
            guards={k:v for k,v in g.items() if k!="incoming_by_node"},
            manifest=ref(OUT/task/"manifest.json"),probe=probe,
            ep2_rows_equal=True,hard_conditions_pass=True)
    tests={}
    for name in ("edge_tests","nodesem_tests","dfg_tests"):
        r=read(OUT/"execution"/(name+".json"));assert r["exit_code"]==0
        counts=re.findall(r"(?m)^(\d+) passed",checked(r["log"]).read_text())
        assert len(counts)==1
        tests[name]=dict(passed=int(counts[0]),receipt=ref(OUT/"execution"/(name+".json")))
    sources=[ROOT/"scripts/edge_sem"/n for n in ("build_f4.py","guard_edges.py")]
    sources+=sorted((ROOT/"scripts/edge_sem/recon").glob("ep3_*.py"))
    sources+=[ROOT/"scripts/edge_sem/tests"/n for n in
        ("test_build_f4_model.py","test_build_f4_guards.py","test_build_f4_guards_model.py","fixtures/ep3_guards.sol")]
    evidence=[ref(p) for folder in ("reentrancy_node","access_control_node","probes")
              for p in sorted((OUT/folder).rglob("*")) if p.is_file()]
    evidence+=[ref(OUT/"before.json"),ref(OUT/"decisions.json")]
    write(OUT/"summary.json",dict(stage="EP3",gate_pass=True,tasks=tasks,tests=tests,
        test_total=sum(v["passed"] for v in tests.values()),source_refs=[ref(p) for p in sources],
        evidence_refs=evidence,gpu_executed=False,training_executed=False,optimizer_steps=0,
        graphs_written=0,ep4_started=False,historical_ep0e_gate_pass=False,
        limitations=["GUARDS reuses bounded frozen lexical evidence; it is not a security proof.",
          "Unknown guard status and unsupported projections remain explicitly represented.",
          "Loop operands remain empty by frozen policy; attribute mapping is deferred to EP4.",
          "Historical 8H features are only CPU parity fixtures; no new main-view decision."]))
    print("EP3 summary complete",sum(v["passed"] for v in tests.values()),flush=True)


if __name__=="__main__":collect()
