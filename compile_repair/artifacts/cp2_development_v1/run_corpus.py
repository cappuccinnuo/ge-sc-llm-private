"""CP2 corpus acceptance runner: common CLI, per-unit gates, no retries."""
import gzip
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit
from compile_repair.toolchain.slither import compare_nodes
from compile_repair.toolchain.solc import version_tuple

OUT = Path(__file__).resolve().parent
ART = ROOT / "compile_repair/artifacts"
KNOWN_FAILURES = {"reentrancy_bonus.sol", "reentrancy_cross_function.sol", "reentrancy_insecure.sol"}
LEGACY_FLOOR_SHA = "5ec2ee307684c021492194d5e63593834e164bcf878d1cddb48a0b1e1ad13237"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def change_reason(row, record, cp0):
    old, new = row["selection"]["ascending"], record.selected_version
    if old == new:
        return {"kind": "same", "old_version": old, "new_version": new}
    last = record.attempts[-1]
    if new not in cp0["compilers"] and version_tuple(new) < version_tuple(old):
        return {"kind": "a", "old_version": old, "new_version": new,
                "newly_installed": True, "observed_solc_rc": last["solc"]["returncode"],
                "observed_production_d3": last["slither"]["d3"]}
    if record.settings:
        return {"kind": "c", "old_version": old, "new_version": new,
                "settings": record.settings, "trigger": last["settings_retry"]}
    if version_tuple(new) < version_tuple(old):
        evidence = []
        with (ART / "cp0_v2/invocations.jsonl").open() as stream:
            for line in stream:
                item = json.loads(line)
                if (item.get("kind") == "slither" and item.get("source_sha256") == row["sha256"]
                        and item.get("version") == new and not item["d3"]):
                    evidence.append(item)
        if evidence:
            return {"kind": "b", "old_version": old, "new_version": new,
                    "regression_failure": evidence, "production_d3": last["slither"]["d3"]}
    raise ValueError("Unattributable CP0 version difference: " + row["path"])


def execute(mode):
    assert Path.cwd() == ROOT
    if read(OUT / "attribution_authorization.json")["status"] != "approved":
        raise ValueError("Attribution adjustment is not approved")
    cp0 = read(ART / "cp0_v2/recon.json")
    inputs = cp0["inputs"]
    assert len(inputs) == 846
    by_path = {str((ROOT / r["path"]).resolve()):r for r in inputs}
    failed = {str((ROOT/r["path"]).resolve()) for r in inputs
              if r["category"] == "reentrancy" and r["file"] in KNOWN_FAILURES}
    assert len(failed) == 3
    destinations = {"ascending1":"cr_store_mando_v1", "ascending2":"cr_store_mando_v2",
                    "descending":"cp2_descending_v1"}
    output = ART / destinations[mode]
    if output.exists():
        raise FileExistsError(str(output))
    first = ART / destinations["ascending1"]
    first_records = {}
    if mode != "ascending1":
        with (first/"manifest.jsonl").open() as stream:
            first_records = {r["inputs"][0]["path"]:r for r in map(json.loads,stream)}
        assert len(first_records) == 846 and read(first/"summary.json")["status"] == "unrepaired"
    if mode == "descending":
        inputs = [r for r in inputs if str((ROOT/r["path"]).resolve()) not in failed]
        assert len(inputs) == 843
    archive = {}
    if mode != "descending":
        with gzip.open(ART/"cp0_1_env_v2/production_run1_node_facts_v2.jsonl.gz","rt") as stream:
            for line in stream:
                item = json.loads(line)
                archive[(item["source_path"], item["version"])] = item
    paths = [str((ROOT/r["path"]).resolve()) for r in inputs]
    for r,p in zip(inputs,paths):
        if sha(Path(p)) != r["sha256"]:
            raise ValueError("Corpus SHA changed: " + p)
    argv = ["repair"] + paths + ["--regression","mando","--order",
             "descending" if mode == "descending" else "ascending","--output",str(output)]
    write(mode+"_plan.json",{"argv":argv,"cwd":str(ROOT),"profile":"production",
                            "inputs":len(inputs),"support_floor":"0.4.12",
                            "expected_unrepaired":sorted(failed) if mode!="descending" else []})
    accepted, counts = [], Counter()
    started = time.monotonic()
    with (OUT/(mode+"_acceptance.jsonl")).open("x",encoding="utf8") as audit:
        def check(record, store):
            path=record.inputs[0]["path"]
            row=by_path[path]
            item={"unit_id":record.unit_id,"path":path,"source_sha256":row["sha256"],
                  "status":record.status,"selected_version":record.selected_version,
                  "flags":record.flags,"origin":record.plan.origin if record.plan else None,
                  "issues":[]}
            try:
                expected_failure=path in failed and mode!="descending"
                if expected_failure:
                    if record.status!="unrepaired" or record.reason!="slither_side_failure":
                        raise ValueError("Known Slither failure changed")
                    if (store/"units"/record.unit_id/"graph.json").exists():
                        raise ValueError("Failed unit entered graph storage")
                elif record.status!="success":
                    raise ValueError("Unexpected unrepaired input: "+str(record.reason))
                if record.status=="success":
                    last=record.attempts[-1]
                    assert last["solc"]["returncode"]==0 and last["slither"]["d3"]
                    assert last["slither"]["profile"]=="production"
                    version=version_tuple(record.selected_version)
                    assert version >= (0,4,12)
                    lo,hi=row["interval"] if row["interval"] is not None else ((0,4,12),(0,9,0))
                    assert tuple(lo)<=version<tuple(hi)
                    graph_path=store/"units"/record.unit_id/"graph.json"
                    graph=read(graph_path)
                    assert graph["schema"]=="compile-repair-graph-v1"
                    assert all(n["provenance"]=="original" for n in graph["nodes"])
                    assert " object at 0x" not in graph_path.read_text()
                    assert str(ROOT) not in graph_path.read_text()
                    item.update(graph_sha256=sha(graph_path),
                        nodes=len(graph["nodes"]),edges=len(graph["cfg_edges"]),calls=len(graph["calls"]))
                    if mode!="descending":
                        item["cp0_version_attribution"]=change_reason(row,record,cp0)
                        if item["cp0_version_attribution"]["kind"]=="same":
                            old=archive[(path,record.selected_version)]
                            diff=compare_nodes(graph["nodes"],old["nodes"])
                            item["production_archive_equal"]=diff["key5"]["equal"] and diff["slithir"]["equal"]
                            if not item["production_archive_equal"]:
                                item["production_archive_difference"]=diff
                                raise ValueError("Same-version production archive differs")
                    if mode=="ascending2":
                        ref=first_records[path]
                        other=first/"units"/ref["unit_id"]/"graph.json"
                        item["repeat_equal"]=graph_path.read_bytes()==other.read_bytes()
                        if not item["repeat_equal"] or record.selected_version!=ref["selected_version"]:
                            raise ValueError("Full-run determinism failed")
                    elif mode=="descending":
                        ref=first_records[path]
                        other=read(first/"units"/ref["unit_id"]/"graph.json")
                        item["ascending_version"]=ref["selected_version"]
                        diff=compare_nodes(other["nodes"],graph["nodes"])
                        item["cross_version"]=diff
                if mode=="ascending2":
                    ref=first_records[path]
                    assert record.status==ref["status"] and record.reason==ref["reason"]
                item["passed"]=True
            except Exception as exc:
                item["passed"]=False
                item["issues"].append(type(exc).__name__+": "+str(exc))
                emit(audit,item)
                accepted.append(item)
                raise
            emit(audit,item)
            accepted.append(item)
            counts[record.status]+=1
        rc=main(argv,result_check=check)
    summary=read(output/"summary.json")
    seal=read(output/"seal.json")
    all_sealed=all(sha(output/p)==h for p,h in seal["files"].items())
    support=[v for v in seal["tools"]["compilers"] if (0,4,12)<=version_tuple(v)<(0,9,0)]
    expected={"success":843} if mode=="descending" else {"success":843,"unrepaired":3}
    passed=(dict(counts)==expected and len(accepted)==len(inputs) and all(r["passed"] for r in accepted)
            and summary["status"]==("complete" if mode=="descending" else "unrepaired")
            and rc==(0 if mode=="descending" else 2) and len(support)==92 and all_sealed)
    result={"mode":mode,"returncode":rc,"elapsed_seconds":time.monotonic()-started,
            "expected_status_counts":expected,"observed_status_counts":dict(counts),
            "units_checked":len(accepted),"supported_compilers":len(support),
            "sealed_files":len(seal["files"]),"seal_readback_equal":all_sealed,
            "seal_sha256":sha(output/"seal.json"),"passed":passed,"output":str(output),
            "nodes":sum(r.get("nodes",0) for r in accepted),
            "cfg_edges":sum(r.get("edges",0) for r in accepted),
            "calls":sum(r.get("calls",0) for r in accepted)}
    write(mode+"_receipt.json",result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if not passed:
        raise SystemExit(2)


if __name__=="__main__":
    execute(sys.argv[1])
