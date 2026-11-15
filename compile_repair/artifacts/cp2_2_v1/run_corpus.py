"""CP2.2 full descending CLI run and per-file comparison with frozen v3."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ART = OUT.parent
sys.path.insert(0,str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import emit, sha256
from compile_repair.toolchain.slither import compare_nodes
from compile_repair.toolchain.solc import version_tuple


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def write(name,value):
    with (OUT/name).open("x",encoding="utf8") as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2)
        stream.write("\n")


def execute():
    assert Path.cwd() == ROOT
    assert read(OUT/"authorization.json")["status"] == "approved"
    replay = read(ART/"cp2_6c_v3/summary.json")
    assert replay["passed"] and replay["compared"] == 239
    inputs = read(ART/"cp0_v2/recon.json")["inputs"]
    assert len(inputs) == 846
    first = ART/"cr_store_mando_v3"
    seal = read(first/"seal.json")
    assert all(sha256(first/p)==h for p,h in seal["files"].items())
    records = {r["inputs"][0]["path"]:r for r in map(json.loads,(first/"manifest.jsonl").read_text().splitlines())}
    assert len(records)==846
    by_path = {str((ROOT/r["path"]).resolve()):r for r in inputs}
    failed = {p for p,r in by_path.items() if r["category"]=="reentrancy" and r["file"] in
              {"reentrancy_bonus.sol","reentrancy_cross_function.sol","reentrancy_insecure.sol"}}
    assert len(failed)==3
    paths = [str((ROOT/r["path"]).resolve()) for r in inputs]
    for r,p in zip(inputs,paths):
        assert sha256(Path(p))==r["sha256"]
    output = ART/"cp2_desc_v1"
    assert not output.exists()
    argv = ["repair"]+paths+["--regression","mando","--order","descending","--output",str(output)]
    write("descending_plan.json",dict(argv=argv,cwd=str(ROOT),inputs=846,
        expected_unrepaired=sorted(failed),profile="production",reference=str(first),
        reference_seal_sha256=sha256(first/"seal.json"),driver_sha256=sha256(Path(__file__))))
    accepted = []
    started = time.monotonic()
    with (OUT/"descending_acceptance.jsonl").open("x",encoding="utf8") as audit:
        def check(record,store):
            path = record.inputs[0]["path"]
            row = by_path[path]
            item = dict(path=path,unit_id=record.unit_id,source_sha256=row["sha256"],
                status=record.status,reason=record.reason,selected_version=record.selected_version,
                origin=record.plan.origin if record.plan else None,flags=record.flags,issues=[])
            try:
                reference = records[path]
                assert record.status==reference["status"], "Unexpected descending status"
                if path in failed:
                    assert record.status=="unrepaired" and record.reason=="slither_side_failure"
                    assert not (store/"units"/record.unit_id/"graph.json").exists()
                else:
                    assert record.status=="success"
                    last = record.attempts[-1]
                    assert last["solc"]["returncode"]==0 and last["slither"]["d3"]
                    assert last["slither"]["profile"]=="production"
                    assert version_tuple(record.selected_version)>=(0,4,12)
                    if row["interval"] is not None:
                        lo,hi=row["interval"]
                        assert tuple(lo)<=version_tuple(record.selected_version)<tuple(hi)
                    graph_path=store/"units"/record.unit_id/"graph.json"
                    graph=read(graph_path)
                    assert all(n["provenance"]=="original" for n in graph["nodes"])
                    assert " object at 0x" not in graph_path.read_text()
                    assert str(ROOT) not in graph_path.read_text()
                    keys={tuple(n["key5"]) for n in graph["nodes"]}
                    assert len(keys)==len(graph["nodes"])
                    outgoing={}
                    for e in graph["cfg_edges"]:
                        a,b=tuple(e["source"]),tuple(e["target"])
                        assert a in keys and b in keys and a[:2]==b[:2]
                        outgoing.setdefault(a,[]).append(e["kind"])
                    for n in graph["nodes"]:
                        kinds=outgoing.get(tuple(n["key5"]),[])
                        if n["node_type"] in ("IF","IFLOOP"):
                            assert Counter(kinds)=={"true":1,"false":1}
                        else:
                            assert all(k=="next" for k in kinds)
                    original=read(first/"units"/reference["unit_id"]/"graph.json")
                    diff=compare_nodes(original["nodes"],graph["nodes"])
                    same=reference["selected_version"]==record.selected_version
                    # Same-version cases count as equal, but still reject unexpected nondeterminism.
                    assert not same or (diff["key5"]["equal"] and diff["slithir"]["equal"])
                    item.update(ascending_version=reference["selected_version"],same_version=same,
                        cross_version=diff,graph_sha256=sha256(graph_path),nodes=len(graph["nodes"]),
                        cfg_edges=len(graph["cfg_edges"]),calls=len(graph["calls"]),
                        edge_kinds=dict(Counter(e["kind"] for e in graph["cfg_edges"])))
                item["passed"]=True
            except Exception as exc:
                item.update(passed=False,issues=[type(exc).__name__+": "+str(exc)])
                emit(audit,item); accepted.append(item)
                raise
            emit(audit,item); accepted.append(item)
        rc=main(argv,result_check=check)
    summary=read(output/"summary.json")
    seal=read(output/"seal.json")
    sealed=all(sha256(output/p)==h for p,h in seal["files"].items())
    counts=Counter(r["status"] for r in accepted)
    support=[v for v in seal["tools"]["compilers"] if (0,4,12)<=version_tuple(v)<(0,9,0)]
    successful=[r for r in accepted if r["status"]=="success"]
    changed=[r for r in successful if not (r["cross_version"]["key5"]["equal"] and r["cross_version"]["slithir"]["equal"])]
    result=dict(mode="descending",passed=(counts=={"success":843,"unrepaired":3} and
        len(accepted)==846 and all(r["passed"] for r in accepted) and sealed and len(support)==92 and
        summary["status"]=="unrepaired" and rc==2),returncode=rc,expected_status_counts={"success":843,"unrepaired":3},
        observed_status_counts=dict(counts),units_checked=len(accepted),supported_compilers=len(support),
        seal_readback_equal=sealed,sealed_files=len(seal["files"]),seal_sha256=sha256(output/"seal.json"),
        same_version=sum(r["same_version"] for r in successful),
        different_version=sum(not r["same_version"] for r in successful),
        key5_equal=sum(r["cross_version"]["key5"]["equal"] for r in successful),
        key5_and_ir_equal=len(successful)-len(changed),key5_and_ir_different=len(changed),
        different_entries=changed,elapsed_seconds=time.monotonic()-started,cost_usd=0)
    write("descending_receipt.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="different_entries"}),flush=True)
    if not result["passed"]:
        raise SystemExit(2)


if __name__=="__main__":
    assert len(sys.argv)==1 or sys.argv[1]=="descending"
    execute()
