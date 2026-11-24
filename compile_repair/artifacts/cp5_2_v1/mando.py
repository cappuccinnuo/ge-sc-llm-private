"""Confirm the checked-in implementation's normal CLI graphs against the frozen v5 seal."""
from pathlib import Path
import json
import time
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit, read_checked_json, sha256

ref = HERE.parent/"cr_store_mando_v5"
base = read_checked_json(ref/"seal.json","db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b")
summ = read_checked_json(ref/"summary.json",base["files"]["summary.json"])
priors = {r["unit_id"]:r for r in summ["units"]}
paths = [r["path"] for r in summ["supplied"]]
assert len(paths) == len(priors) == 846
dest = ROOT.parent/"compile-repair-local/cp5_2_v1/mando"
out = HERE/"mando"
out.mkdir(exist_ok=False)
count = {"graphs_equal":0, "historical_failures":0, "steps_on_truths":0}
start = time.monotonic()
with (out/"rows.jsonl").open("x",encoding="utf8") as log:
    def verify(record, store):
        uid = record.unit_id
        old = priors[uid]
        assert old["status"] == record.status and old["selected_version"] == record.selected_version and old["reason"] == record.reason
        assert record.inputs[0]["sha256"] == old["input_sha256"]
        key="units/"+uid+"/graph.json"
        steps=(store/"units"/uid/"repair_steps.json").exists()
        if record.status=="success":
            assert (ref/key).read_bytes() == (store/key).read_bytes() and sha256(store/key)==base["files"][key]
            assert record.attempts[-1]["slither"]["d3"] and not steps
            count["graphs_equal"] += 1
            count["steps_on_truths"] += int(steps)
        else:
            assert not (store/key).exists()
            count["historical_failures"] += 1
        flags = record.attempts[-1]["slither"]["partial_ir"] if record.status == "success" else {}
        emit(log,dict(unit_id=uid,status=record.status,reason=record.reason,steps=steps,partial_ir=flags,
                      graph_sha256=base["files"].get(key)))
    rc = main(["repair"]+paths+["--regression","mando","--order","ascending","--output",str(dest)],result_check=verify)
result=json.loads((dest/"summary.json").read_bytes())
seal=json.loads((dest/"seal.json").read_bytes())
code_equal=all(sha256(ROOT/k)==v for k,v in seal["implementation_sha256"].items())
passed=(rc==2 and result["status"]=="unrepaired" and code_equal and count==dict(graphs_equal=843,historical_failures=3,steps_on_truths=0))
receipt=dict(passed=passed,returncode=rc,status=result["status"],counts=count,modules_match=code_equal,
             implementation_sha256=seal["implementation_sha256"],store=str(dest),seal_sha256=sha256(dest/"seal.json"),
             rows_sha256=sha256(out/"rows.jsonl"),elapsed_seconds=time.monotonic()-start)
with (out/"summary.json").open("x") as fp:
    json.dump(receipt,fp,sort_keys=True,indent=2)
    fp.write("\n")
print(passed,count,flush=True)
assert passed
