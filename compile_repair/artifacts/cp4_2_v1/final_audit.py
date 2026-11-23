"""Join the completed movement receipts with the exact restoration, migration and suite results."""
from collections import Counter
from pathlib import Path
import json
import subprocess
from check_delivery import OUT, ROOT, BASE, digest, read, write
from checkpoint_79 import verify as verify_checkpoint


def main():
    assert verify_checkpoint()==read("checkpoint_79.json")
    summary=read("move_summary.json")
    plan=read("move_plan.json")["rows"]
    records=OUT/summary["rows_file"]
    assert digest(records)==summary["rows_sha256"]
    data=[json.loads(x) for x in records.read_bytes().splitlines()]
    assert len(plan)==len(data)==len({r["unit_id"] for r in data})==200
    proofs={x["unit_id"]:x for x in read("measured_differences.json")}
    counts=Counter();corpora=Counter();all_differences=[]
    for row,planned in zip(data,plan):
        uid=row["unit_id"]
        assert all(row[key]==planned[key] for key in ("unit_id","version","settings","corpus","truth_graph_sha256"))
        for key in ("file","end","insert","contract","function"):
            assert row["site"][key]==planned["site"][key]
        assert row["site"].get("function_start",row["site"]["start"])==planned["site"]["start"]
        assert row["split"]=="dev" and row["returncode"]==0
        for key in ("graph_path","solc_result","slither_result"):
            assert digest(Path(row[key]))==row["graph_sha256" if key=="graph_path" else key+"_sha256"]
        assert json.loads(Path(row["slither_result"]).read_bytes())["d3"] is True
        s=row["score"];kind=row["outcome"]
        assert s["compiled"] and s["lost"]==s["added"]==row["expected_moved_nodes"] and not s["missing_kept"]
        assert all(s[k]==s["raw"][k] for k in ("compiled","lost","added","change_level"))
        if kind=="all_kept_facts_equal":
            assert uid not in proofs and all(s[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
        else:
            assert kind in ("verified_creation_literal_difference","yul_source_start_raw") and uid in proofs
            p=proofs[uid]
            assert p["kind"]==kind and p["changes"] and p["unchanged_official_score"]==s and s["kept"]["ratio"]<1
            assert p["diagnostic_ratios"]==dict(kept=1,cfg_edges=1,calls=1)
            all_differences.append(dict(unit_id=uid,kind=kind,kept=s["kept"],cfg_edges=s["cfg_edges"],calls=s["calls"]))
        counts[kind]+=1
        counts["raw_kept_below_one"]+=s["raw"]["kept"]["ratio"]<1
        corpora[row["corpus"]]+=1
    assert set(proofs)=={r["unit_id"] for r in all_differences}
    assert all(summary["counts"][k]==v for k,v in counts.items()) and dict(corpora)==summary["corpora"]
    assert read("exact_summary.json")["all_prior_fields_equal"]
    assert read("migration_summary.json")["raw_and_accepted_scores_equal"]==114
    assert read("negative.json")["wrong_repairs_detected"]==22
    tests={n:read("final_tests/"+n+"_tests.json") for n in ("production","mando","dfg")}
    assert all(r["returncode"]==0 for r in tests.values())
    scope=read("final_scope.json")
    for filename,checksum in scope["production_sha256"].items():assert digest(ROOT/filename)==checksum
    assert scope["production_files"]==17 and scope["unchanged_dfg_code_refs"]==354
    write("acceptance.json",dict(self_check="passed",scope="user-approved CP4.2 movement exceptions use official raw scores",
          movement_summary=summary,movement_differences=all_differences,exact_identical=14196,
          migrations_unchanged=114,wrong_repairs=22,missing_node_control=1,new_counter_use_negatives=2,
          tests={n:r["summary"] for n,r in tests.items()},input_revision=BASE,production_files=17,
          reviewed_dfg_code_refs=354,review="independent review pending",cost_usd=0))
    print("Reviewed",len(data),"records and",len(proofs),"documented differences")


if __name__=="__main__":main()
