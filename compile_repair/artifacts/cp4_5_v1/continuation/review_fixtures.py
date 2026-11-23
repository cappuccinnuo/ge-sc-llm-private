"""Rescore the sealed production review graphs and compare with CP4.4."""
import hashlib
import json
from pathlib import Path
import sys

from compile_repair.evaluation.benchmark import score_graphs

OUT=Path(__file__).resolve().parent
OLD=OUT.parent.parent/"cp4_4_v1"
SCRATCH=OUT.parents[4]/"compile-repair-local"/OLD.name/"review"
seal=json.loads((OLD/"seal.json").read_bytes())["batch"]
def checked(path, digest):
    data=path.read_bytes()
    assert hashlib.sha256(data).hexdigest()==digest, path
    return data
checked(OLD/"review_sources.py",seal["review_sources.py"])
sys.path.insert(0,str(OLD))
from review_sources import cases
inputs=json.loads(checked(OLD/"review_inputs.json",seal["review_inputs.json"]))
prior=json.loads(checked(OLD/"review_scores.json",seal["review_scores.json"]))
result={}
for kind in ("partial","yul"):
    result[kind]={}
    def graph(side,source):
        files={n:checked(SCRATCH/kind/side/n,h) for n,h in inputs[kind][side].items()}
        assert files["A.sol"]==source and json.loads(files["solc.json"])["returncode"]==0
        assert json.loads(files["slither.json"])["d3"] is True
        return json.loads(files["graph.json"])
    for case,(source,damaged,repaired,first,second) in cases(kind):
        truth,actual=graph("truth",source),graph(case,repaired)
        score=score_graphs(truth,actual,{"":source},{"":damaged},{"":repaired},{"":first},{"":second},0,True)
        old=prior[kind][case]
        result[kind][case]=dict(cp45=score,cp44=old["score"],other_node_fields=old["non_ir_differences"])
with (OUT/"review_scores.json").open("x") as f:
    json.dump(result,f,indent=2);f.write("\n")
for kind in result:
    for case,row in result[kind].items():
        score=row["cp45"]
        print(kind,case,score["kept"],score["counter_correspondence"]["nodes"],flush=True)
        goal={"partial":{"A":7,"B":6,"C":6},"yul":{"A":16,"B":16}}[kind].get(case)
        if goal is not None:
            assert score["kept"]["equal"]==goal
        assert score["raw"]==row["cp44"]["raw"]
        if kind=="yul" and case=="C":assert not score["exact"]
        if kind=="yul" and case=="B":
            assert score["counter_correspondence"]["nodes"]["candidate"]==16
            assert len([x for x in row["other_node_fields"] if x["fields"]==["length"]])==3
