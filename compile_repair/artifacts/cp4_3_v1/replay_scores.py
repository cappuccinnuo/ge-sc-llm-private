"""Score the frozen CP4.2 graphs under CP4.3. No compiler or Slither invocation is made."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
PREVIOUS = OUT.parent/"cp4_2_v1"
sys.path.insert(0, str(PREVIOUS))
import rescore as history
from rescore import checked, rows, sha, base_contents, score_graphs
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches

SEAL = json.loads((PREVIOUS/"seal.json").read_bytes())["batch_files_excluding_seal"]
METRICS = ("kept", "cfg_edges", "calls")


def baseline(filename):
    checked(PREVIOUS/filename, SEAL[filename])
    return PREVIOUS/filename


def key(row):
    return row["operator"], row["unit_id"], row["mutation_sha256"]


def previous_fields(value):
    if isinstance(value, dict):
        return {k:previous_fields(v) for k,v in value.items() if k not in ("removed_by_repair","surviving")}
    return value


def historical(mode, counts):
    history.mode = mode
    history.bases = {r["unit_id"]:r for r in rows(history.OLD/"bases.jsonl.gz")}
    history.observations = {key(r):r for name in ("original_reclassified","new_observations","supplement_observations")
                            for r in rows(history.CP41/(name+".jsonl.gz")) if r["outcome"]=="included"}
    old = iter(rows(baseline("exact.jsonl.gz" if mode=="exact" else "migrations_final.jsonl.gz")))
    seen = set()
    for item in history.source_rows():
        if mode=="migration" and item["operator"]!="unresolved_package_import":
            continue
        prior = next(old)
        assert key(prior)==key(item) and key(item) not in seen, key(item)
        seen.add(key(item))
        fresh = history.score(item)
        s = fresh["score"]
        yield dict(unit_id=fresh["unit_id"],operator=fresh["operator"],mutation_sha256=fresh["mutation_sha256"],
                   graph_sha256=fresh["graph_sha256"],score=s,prior_score_sha256=sha(json.dumps(prior["score"],sort_keys=True).encode()))
        assert fresh["graph_sha256"]==prior["graph_sha256"] and previous_fields(s)==prior["score"], key(item)
        assert s["removed_by_repair"]==s["raw"]["removed_by_repair"]==0 and s["exact"],key(item)
        status=s["counter_correspondence"]["status"]
        assert mode!="exact" or status=="identical",key(item)
        counts[status]+=1
    assert next(old,None) is None


def movements(counts):
    bases = {r["unit_id"]:r for r in rows(history.OLD/"bases.jsonl.gz")}
    plan = json.loads(baseline("move_plan.json").read_bytes())["rows"]
    previous = list(rows(baseline("moves_completed.jsonl")))
    assert len(plan)==len(previous)==len({r["unit_id"] for r in plan})==200
    for choice, prior in zip(plan, previous):
        uid=prior["unit_id"]; site=prior["site"]; name=site["file"]
        assert choice["unit_id"]==uid and prior["split"]=="dev"
        base=bases[uid]; source=base_contents(base)
        truth=json.loads(checked(base["graph_path"],prior["truth_graph_sha256"]))
        actual=json.loads(checked(prior["graph_path"],prior["graph_sha256"]))
        solc,slither=(json.loads(checked(prior[k],prior[k+"_sha256"])) for k in ("solc_result","slither_result"))
        assert solc["returncode"]==0 and slither["profile"]=="production" and slither["d3"] is True
        a,b,t=site["start"],site["end"],site["insert"]
        fragment=source[name][a:b]; fixed=dict(source)
        assert sha(fragment)==site["body_sha256"] and sha(source[name])==prior["source_before_sha256"]
        fixed[name], edits=apply_patches(source[name],[Patch(a,b,fragment,b"","delete_function"),
                                                       Patch(t,t,b"",b"\n"+fragment+b"\n","insert_function")])
        assert sha(fixed[name])==prior["source_after_sha256"]
        if slither.get("project"):
            project=slither["project"]
            files={Path(f["path"]).relative_to(project["root"]).as_posix():checked(f["path"],f["sha256"])
                   for f in project["files"]}
        else:
            files={"":checked(solc["source_path"],solc["source_sha256"])}
        assert files==fixed,uid
        s=score_graphs(truth,actual,source,source,fixed,{},{name:edits},solc["returncode"],slither["d3"])
        n=prior["expected_moved_nodes"]
        yield dict(unit_id=uid,corpus=prior["corpus"],expected_moved_nodes=n,source_after_sha256=prior["source_after_sha256"],
                   graph_sha256=prior["graph_sha256"],truth_graph_sha256=prior["truth_graph_sha256"],
                   solc_result_sha256=prior["solc_result_sha256"],slither_result_sha256=prior["slither_result_sha256"],score=s)
        assert n==sum(1 for node in truth["nodes"] if node.get("filename","")==name and a<=node["key5"][3]<b)
        assert s["compiled"] and not s["exact"] and s["removed_by_repair"]==s["missing_kept"]==s["added"]==n>0
        assert s["lost"]==0 and s["kept"]["ratio"]<1 and s["kept"]["units"]==s["surviving"]["kept"]["units"]+n
        assert s["surviving"]["kept"]["units"]==prior["score"]["kept"]["units"]
        all_equal=all(s["surviving"][k]["ratio"]==1 for k in METRICS)
        assert all_equal==(uid!="cp3_00291"),(uid,s["counter_correspondence"])
        if uid=="cp3_21529":
            switches=s["counter_correspondence"]["yul_switches"]
            assert len(switches)==3 and all(int(r["src_after"].split(":")[0])-int(r["src_before"].split(":")[0])==2 for r in switches)
        if uid=="cp3_00291":
            assert s["counter_correspondence"]["status"]=="rejected" and s["surviving"]["kept"]==prior["score"]["kept"]
        counts["primary_kept_below_one"]+=s["kept"]["ratio"]<1
        counts["removed_matches_expected"]+=s["removed_by_repair"]==n
        counts["surviving_all_equal"]+=all_equal
        counts["removed_nodes"]+=n
        counts["historical_graphs"]+=1


def main(mode):
    counts=Counter()
    assert mode in ("moves","exact","migration")
    baseline("rescore.py")
    items=movements(counts) if mode=="moves" else historical(mode,counts)
    dest=OUT/(mode+".jsonl.gz")
    last=None
    try:
        with dest.open("xb") as stream,gzip.GzipFile(fileobj=stream,mode="wb",filename="",mtime=0) as fp:
            for row in items:
                last=row["unit_id"]
                fp.write((json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode())
                counts["units"]+=1
                if counts["units"]%1000==0:print(counts["units"],flush=True)
        assert counts["units"]=={"moves":200,"exact":14196,"migration":114}[mode]
    except Exception as exc:
        with (OUT/(mode+"_stop.json")).open("x") as f:
            json.dump(dict(last_written=last,counts=counts,error=repr(exc)),f,indent=2)
        raise
    result=dict(mode=mode,counts=counts,sha256=sha(dest.read_bytes()),solc_runs=0,slither_runs=0)
    with (OUT/(mode+"_summary.json")).open("x") as f:json.dump(result,f,indent=2);f.write("\n")
    print(result,flush=True)

if __name__=="__main__":main(sys.argv[1])
