"""Move one complete ordinary function, retaining the frozen compiler, settings and graph."""
from collections import Counter, defaultdict, deque
from dataclasses import asdict
import json
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
CP41=OUT.parent/"cp4_1_v1"
sys.path.insert(0,str(CP41))
from batch import OLD, ROOT, checked, rows, sha
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches, mark_span
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import SourceLayout, _materialize_closure, base_contents, score_graphs
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers
from compile_repair.toolchain.project import compile_project
from compile_repair.toolchain.slither import run_slither

SCRATCH=ROOT.parent/"compile-repair-local"/"cp4_2_v1"/"moves"
SEED=20261122


def write(name, data):
    with (OUT/name).open("x",encoding="utf8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write("\n")


def choices(base, sources, truth):
    for name,raw in sorted(sources.items()):
        layout=SourceLayout(raw)
        for _,ci,opening,closing in layout.definitions:
            contract=layout.words[ci].decode("utf8")
            nodes=[n for n in truth["nodes"] if n.get("filename","")==name and n["key5"][0]==contract]
            for fi,ni,_,body in layout.functions:
                if not opening+1<fi<body<closing or layout.words[body]!=b"{" or layout.words[ni]==layout.words[ci]:
                    continue
                fn=layout.words[ni].decode("utf8")+"("
                a,b=layout.bounds(fi,layout.matches[body])
                selected=[n for n in nodes if a<=n["key5"][3]<b and n["key5"][1].startswith(fn)]
                if any(n["ir"] for n in selected):
                    yield dict(file=name,start=a,end=b,insert=layout.tokens[opening][1],
                               contract=contract,function=selected[0]["key5"][1],body_sha256=sha(raw[a:b]))


def plan(bases):
    strata=defaultdict(list)
    for b in bases.values():
        if b["split"]=="dev":
            rank=sha(("{}:move:{}".format(SEED,b["unit_id"])).encode())
            strata[b["corpus"]].append((rank,b["unit_id"]))
    queues={k:deque(sorted(items)) for k,items in strata.items()}
    order=deque(sorted(queues))
    result=[];skipped=Counter()
    while order and len(result)<200:
        corpus=order.popleft()
        while queues[corpus]:
            _,uid=queues[corpus].popleft()
            b=bases[uid];source=base_contents(b)
            truth=json.loads(checked(b["graph_path"],b["graph_sha256"]))
            site=next(choices(b,source,truth),None)
            if site is not None:
                result.append(dict(unit_id=uid,corpus=corpus,split=b["split"],kind=b["kind"],version=b["version"],
                                   settings=b["settings"],truth_graph_sha256=b["graph_sha256"],site=site))
                break
            skipped[corpus]+=1
        if queues[corpus]:order.append(corpus)
    assert any(bases[r["unit_id"]]["project_root"] for r in result)
    write("move_plan.json",dict(seed=SEED,method="Round-robin corpus, ascending seeded unit hash, first eligible function in source order.",inapplicable=dict(skipped),rows=result))
    return result


def measure(base, row, comp, output_root=SCRATCH):
    uid=row["unit_id"];site=row["site"];name=site["file"];s=base_contents(base)
    a,b,top=site["start"],site["end"],site["insert"]
    fragment=s[name][a:b]
    assert sha(fragment)==site["body_sha256"] and top<a
    changed=dict(s)
    changed[name],repair=apply_patches(s[name],[Patch(a,b,fragment,b"","delete_function"),
                                                  Patch(top,top,b"",b"\n"+fragment+b"\n","insert_function")])
    store=ArtifactStore(output_root/uid)
    target,project=_materialize_closure(base,changed,store,"input")
    if project:
        assert not project.issues and {Path(f.path).relative_to(project.root).as_posix():f.sha256 for f in project.files}=={n:sha(v) for n,v in changed.items()}
    solc=(compile_project(project,comp,settings=base["settings"]) if project else
          compile_file(target,comp,settings=base["settings"]))
    store.write_json("solc.json",asdict(solc))
    rec=dict(row,solc_result=str(store.path/"solc.json"),solc_result_sha256=sha((store.path/"solc.json").read_bytes()),
             returncode=solc.returncode,source_before_sha256=sha(s[name]),source_after_sha256=sha(changed[name]))
    if solc.returncode!=0:return dict(rec,stop="compiler_failure",diagnostic=solc.error_first_line)
    analysis=run_slither(solc,"production",project=project)
    graph=analysis.pop("graph",None)
    store.write_json("slither.json",analysis)
    rec.update(slither_result=str(store.path/"slither.json"),slither_result_sha256=sha((store.path/"slither.json").read_bytes()))
    if not analysis["d3"] or graph is None:return dict(rec,stop="analyzer_failure",diagnostic=analysis["error_first_line"])
    maps={n:apply_patches(buf,())[1] for n,buf in changed.items()}
    graph["nodes"]=[dict(n,provenance=mark_span(maps[n.get("filename","")],n["key5"][3],n["length"])) for n in graph["nodes"]]
    path=store.write_json("graph.json",graph)
    graph=json.loads(path.read_bytes())
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    expected=sum(n.get("filename","")==name and a<=n["key5"][3]<b for n in truth["nodes"])
    score=score_graphs(truth,graph,s,s,changed,{},{name:repair},0,True)
    rec.update(score=score,graph_path=str(path),graph_sha256=sha(path.read_bytes()),expected_moved_nodes=expected)
    if (score["lost"]!=expected or score["added"]!=expected or score["missing_kept"] or
            any(score[k]["ratio"]!=1 for k in ("kept","cfg_edges","calls")) or score["counter_correspondence"]["status"]=="rejected"):
        rec["stop"]="movement_score"
    return rec


def main():
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    selected=plan(bases)
    compilers=load_trusted_compilers()[0]
    counts=Counter()
    with (OUT/"moves.jsonl").open("x",encoding="utf8") as f:
        for row in selected:
            rec=measure(bases[row["unit_id"]],row,compilers[row["version"]])
            f.write(json.dumps(rec,sort_keys=True,separators=(",",":"))+"\n");f.flush()
            if rec.get("stop"):
                write("move_stop.json",rec)
                print("Stopped",row["unit_id"],rec["stop"],flush=True)
                return
            counts["passed"]+=1
            counts["raw_below_one"]+=rec["score"]["raw"]["kept"]["ratio"]<1
    write("move_summary.json",dict(counts))
if __name__=="__main__":main()
