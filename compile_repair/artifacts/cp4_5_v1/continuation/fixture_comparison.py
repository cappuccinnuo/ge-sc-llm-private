"""Compare real suite receipts and synthetic per-node winners against frozen results."""
import hashlib
import json
from pathlib import Path

from compile_repair.evaluation.benchmark import score_graphs
from compile_repair.tests.test_cp44 import competing_definitions
from compile_repair.tests.test_cp45 import CASES, measure

out=Path(__file__).resolve().parent
prior=out.parent.parent/"cp4_4_v1"
scratch=out.parents[4]/"compile-repair-local"
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
seal=read(prior/"seal.json")["batch"]
for name in ("fixture_facts.json","proportionality.json","suites/production_tests.json"):
    assert digest(prior/name)==seal[name]
facts=read(prior/"fixture_facts.json")["wrong_counter_uses"]
stale=read(out.parent.parent/"cp4_4_review_v1/probe_stale_name.json")
results={}
def record(case,old,new):
    assert old["raw"]==new["raw"],case
    results[case]=dict(cp44=old,cp45=new)
for case,left,right,winners in CASES:
    normal,found=measure(left,right)
    reverse,rev_found=measure(left,right,True)
    assert normal==reverse and found==rev_found==winners
    results[case]=dict(previous=stale[case],cp45=normal,correct_offsets=winners,measured_offsets=found,reversed_offsets=rev_found)
for label,old in facts.items():
    truth,actual=competing_definitions(label)
    source={"":b"contract C {}"}
    new=score_graphs(truth,actual,source,source,source,{},{},0,True)
    record(label,old,new)
    assert not new["exact"]
for parent in ("test_review_placement_False_0","test_review_placement_True_0","test_repair_deleting_an_undama0",
               "test_one_constant_edit_per_kep0","test_yul_switch_offset_from_co0"):
    def scores(batch):
        root=scratch/batch/"tests_production"/parent
        paths=list(root.glob("score*.json"))+list(root.glob("proportionality.json"))
        [path]=paths
        return read(path)
    old,new=scores(prior.name),scores("cp4_5_v1/continuation")
    if "kept" in old:
        record(parent,old,new)
    elif "verified" in old:
        record("yul_verified",old["verified"],new["verified"])
        for key in old["rejected"]:record("yul_"+key,old["rejected"][key],new["rejected"][key])
    else:
        for key in old:record("proportionality_"+key,old[key],new[key])
old=read(prior/"negative.json")
new=read(out/"negative.json")
for a,b in zip(old["rows"],new["rows"]):
    assert a["operator"]==b["operator"] and a["detected"] and b["detected"]
    record("negative_"+a["operator"],a["score"],b["score"])
with (out/"fixture_comparison.json").open("x") as f:
    json.dump(results,f,indent=2);f.write("\n")
print(len(results),"cases",flush=True)
