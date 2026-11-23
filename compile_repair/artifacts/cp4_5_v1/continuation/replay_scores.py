"""Score the frozen CP4.2 graphs under CP4.5. No compiler or Slither invocation is made."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
PREVIOUS = OUT.parent.parent/"cp4_2_v1"
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


def historical(mode):
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
    assert next(old,None) is None


def movements():
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


def run(mode):
    older=OUT.parent.parent/"cp4_4_v1"
    name=mode+".jsonl.gz"
    old_file=older/name
    checked(old_file,json.loads((older/"seal.json").read_bytes())["batch"][name])
    old=iter(rows(old_file))
    candidates=movements() if mode=="moves" else historical(mode)
    counts=Counter();differences=[];seen=set()
    start=time.monotonic()
    with (OUT/name).open("xb") as dest,gzip.GzipFile(fileobj=dest,mode="wb",filename="",mtime=0) as fp:
        for row in candidates:
            before=next(old)
            identity=(row["unit_id"],row.get("operator"),row.get("mutation_sha256"))
            assert identity==(before["unit_id"],before.get("operator"),before.get("mutation_sha256")) and identity not in seen
            seen.add(identity)
            assert before["graph_sha256"]==row["graph_sha256"]
            score,prior=row["score"],before["score"]
            fields=sorted((score.keys() | prior.keys()) - {"counter_correspondence"})
            changed={k:dict(cp44=prior.get(k),cp45=score.get(k)) for k in fields if prior.get(k)!=score.get(k)}
            if mode=="migration":
                assert score["counter_correspondence"]==prior["counter_correspondence"]
            if changed:
                differences.append(dict(unit_id=row["unit_id"],operator=row.get("operator"),fields=changed,
                                        proof=score["counter_correspondence"]))
            counts[score["counter_correspondence"]["status"]]+=1
            if mode=="moves":
                counts["surviving_all_equal"]+=all(v["ratio"]==1 for v in score["surviving"].values())
            row["changed_fields"]=sorted(changed)
            fp.write((json.dumps(row,sort_keys=True,separators=(",",":"))+"\n").encode())
            if len(seen)%1000==0:print(len(seen),flush=True)
    assert next(old,None) is None and len(seen)=={"moves":200,"exact":14196,"migration":114}[mode]
    result=dict(units=len(seen),mode=mode,counts=counts,differences=differences,
                status="comparison_stop" if differences else "passed",sha256=sha((OUT/name).read_bytes()),
                elapsed_seconds=round(time.monotonic()-start,3),solc_runs=0,slither_runs=0)
    with (OUT/(mode+"_summary.json")).open("x") as f:json.dump(result,f,indent=2);f.write("\n")
    print(mode,len(seen),counts,"metric differences",len(differences),flush=True)
    return bool(differences)

if __name__=="__main__":sys.exit(2 if run(sys.argv[1]) else 0)
