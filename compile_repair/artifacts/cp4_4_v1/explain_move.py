"""Identify the individual cp3_00291 facts underlying the one changed CP4.4 score."""
import json, sys
from pathlib import Path
from replay_scores import OUT, PREVIOUS, history, rows, base_contents, checked, sha, Patch, apply_patches
from compile_repair.evaluation.benchmark import _comparison_graph,_correspondence,_score_facts,_nodes,_ordinary_correspondence
uid="cp3_00291"
prior=next(r for r in rows(PREVIOUS/"moves_completed.jsonl") if r["unit_id"]==uid)
base=next(r for r in rows(history.OLD/"bases.jsonl.gz") if r["unit_id"]==uid)
sources=base_contents(base);fixed=dict(sources)
truth,_=_comparison_graph(json.loads(checked(base["graph_path"],prior["truth_graph_sha256"])),{},True)
actual,_=_comparison_graph(json.loads(checked(prior["graph_path"],prior["graph_sha256"])),{},True)
site=prior["site"];a,b,t,name=(site[k] for k in ("start","end","insert","file"));frag=sources[name][a:b]
fixed[name],edit=apply_patches(sources[name],[Patch(a,b,frag,b"","remove"),Patch(t,t,b"",b"\n"+frag+b"\n","insert")])
assert sha(fixed[name])==prior["source_after_sha256"]
maps,near,level=_correspondence(sources,sources,fixed,{},{name:edit});positions={}
_score_facts(truth,actual,sources,fixed,maps,near,level,True,{},kept_positions=positions)
counts=dict(participating=0,structural=0,conflict=0,definition=0,switch=0)
corrected,names,_=_ordinary_correspondence(truth,actual,positions,maps,None,sources,fixed,counts)
old,raw,new=map(_nodes,(truth,actual,corrected))
def digest(x):return sha(json.dumps(x,sort_keys=True).encode())
changes=[]
for k,target in positions.items():
    if raw[target]["ir"]!=old[k]["ir"]:
        changes.append(dict(identity=k,target=target,original_ir_sha256=digest(old[k]["ir"]),
                            raw_ir_sha256=digest(raw[target]["ir"]),scored_ir_sha256=digest(new[target]["ir"]),
                            matches_after=new[target]["ir"]==old[k]["ir"]))
assert len(changes)==3 and sum(r["matches_after"] for r in changes)==1
calls=[]
for i,(before,after) in enumerate(zip(actual["calls"],corrected["calls"])):
    if before!=after:calls.append(dict(index=i,node=before["node"],ir_index=before["ir_index"],kind=before["kind"],
                                       raw_sha256=digest(before),scored_sha256=digest(after)))
assert len(calls)==1
evidence=json.loads((OUT/"moves_summary.json").read_bytes())["differences"]
assert len(evidence)==1 and evidence[0]["unit_id"]==uid
result=dict(unit_id=uid,changed_fields=evidence[0]["fields"],renamed=names,counts=counts,
            nodes=changes,calls=calls,creation_bytes_evidence_sha256=sha((PREVIOUS/"observed_creation_hashes.json").read_bytes()))
with (OUT/"movement_difference.json").open("x",encoding="utf8") as fp:json.dump(result,fp,indent=2);fp.write("\n")
print([(r["identity"],r["matches_after"]) for r in changes])
