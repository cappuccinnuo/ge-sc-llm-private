"""Read-only checks of the 79 measured units at the Yul decision point."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from check_delivery import read, OUT, digest, write

def verify():
    records=[json.loads(line) for line in (OUT/"moves_accepted.jsonl").read_bytes().splitlines()]
    stop=read("unexplained_move_stop.json")["row"]
    assert len(records)==78 and stop["unit_id"]=="cp3_21529"
    records.append(stop)
    plan=read("move_plan.json")["rows"]
    assert len({r["unit_id"] for r in plan})==len(plan)==200
    assert [r["unit_id"] for r in records]==[r["unit_id"] for r in plan[:79]]
    counts=Counter()
    for r in records:
        assert r["split"]=="dev" and r["returncode"]==0
        for file in ("graph_path","solc_result","slither_result"):
            checksum=r["graph_sha256" if file=="graph_path" else file+"_sha256"]
            assert digest(Path(r[file]))==checksum
        assert json.loads(Path(r["slither_result"]).read_bytes())["d3"] is True
        sc=r["score"]
        assert sc["compiled"] and sc["lost"]==sc["added"]==r["expected_moved_nodes"] and not sc["missing_kept"]
        counts["measured"]+=1
        counts["raw_kept_below_one"]+=sc["raw"]["kept"]["ratio"]<1
        counts["all_kept_facts_equal"]+=all(sc[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
    assert counts["all_kept_facts_equal"]==77
    for idx,proof in ((75,"literal_rest_of_graph.json"),(78,"observed_yul_positions.json")):
        p=read(proof)
        assert p["unit_id"]==records[idx]["unit_id"] and p["unchanged_official_score"]==records[idx]["score"]
        assert all(x==1 for x in p["diagnostic_ratios"].values())
    tests={n:read("final_tests/"+n+"_tests.json") for n in ("production","mando","dfg")}
    assert all(r["returncode"]==0 for r in tests.values())
    exact=read("exact_summary.json")
    assert exact["by_status"]=={"identical":14196} and digest(OUT/"exact.jsonl.gz")==exact["sha256"]
    assert read("migration_summary.json")["reconstructed_historical_full_proofs_equal"]==114
    return dict(plan=200,measured=counts,remaining=121,stop=stop["unit_id"],
                known_literal="cp3_00291",scope=read("final_scope.json")["changed_production"],
                final_tests={k:r["summary"] for k,r in tests.items()},production_files=17,
                exact_identical=14196,migrations=114,status="checkpoint_pending_yul_decision",cost_usd=0)

if __name__=="__main__":
    import sys
    result=verify()
    if sys.argv[1:]==["record"]:write("checkpoint_79.json",result)
    else:assert read("checkpoint_79.json")==result
    print(json.dumps(result,ensure_ascii=False))
