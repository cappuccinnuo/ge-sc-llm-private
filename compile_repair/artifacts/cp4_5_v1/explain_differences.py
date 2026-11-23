"""Trace changed historical scores to individual binding and write sites without running any compiler."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

from compile_repair.evaluation import benchmark as bench
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent/"cp4_2_v1"))
import rescore as hist

def shape(op):
    if re.match(r"^REF_[0-9]+\(.*\) -> ", op):
        return "reference_binding"
    if re.fullmatch(r"REF_[0-9]+ = delete REF_[0-9]+ *", op):
        return "delete_through_reference"
    if re.fullmatch(r"REF_[0-9]+\(.+\) = \[.*\]", op):
        return "initialize_array_through_reference"
    return "other"

def analyze(row, source, fixed, damage, edits, truth, actual, damaged):
    maps,near,level = bench._correspondence(source,damaged,fixed,damage,edits)
    kept = {}
    bench._score_facts(truth,actual,source,fixed,maps,near,level,True,{},kept_positions=kept)
    nodes, locations = {}, defaultdict(list)
    left,right = bench._nodes(truth),bench._nodes(actual)
    for k,t in kept.items():
        a,b = left[k],right[t]
        node = bench._ordinary_node_names(k,t,a,b,maps,None,source,fixed)
        if node is None:continue
        nodes[k]=node
        for i,(l,r) in enumerate(zip(a["ir"],b["ir"])):
            name = bench._ordinary_definition(l)
            if name:
                scoped=(k[0] if name.startswith("switch_expr_") else None,name)
                locations[scoped].append(dict(key=k,peer=t,ir_index=i,truth_shape=shape(l),actual_shape=shape(r),
                                              truth_sha256=hist.sha(l.encode()),actual_sha256=hist.sha(r.encode()),
                                              peer_name=bench._ordinary_definition(r)))
    anchors,disputed,_=bench._definition_anchors(nodes)
    bad=[k for k,n in nodes.items() if any(a in disputed for a,b in n.pairs)]
    expected=row["score"]["counter_correspondence"]["nodes"]
    assert len(bad)==expected["disputed"]==expected["name_mismatch"], (row["unit_id"],expected)
    labels,details = Counter(),[]
    for name in sorted(disputed):
        sites=locations[name]
        pairs=[s["truth_shape"] for s in sites]
        reason="other"
        if (len(sites)==2 and sites[0]["key"]==sites[1]["key"] and sites[0]["peer"]==sites[1]["peer"]
                and sites[0]["ir_index"]<sites[1]["ir_index"] and pairs[0]=="reference_binding"
                and pairs[1] in ("delete_through_reference","initialize_array_through_reference")
                and all(s["truth_shape"]==s["actual_shape"] for s in sites)
                and sites[0]["peer_name"]==sites[1]["peer_name"]):
            reason=pairs[1]
        labels[reason]+=1
        details.append(dict(name=name[1],reason=reason,sites=sites))
    return dict(unit_id=row["unit_id"],operator=row.get("operator"),mutation_sha256=row.get("mutation_sha256"),
                graph_sha256=row["graph_sha256"],fields=row["changed_fields"],delta_nodes=bad,
                causes=labels,definitions=details)

def main(mode):
    meta=json.loads((OUT/(mode+"_summary.json")).read_bytes())
    src=OUT/(mode+".jsonl.gz")
    assert hist.sha(src.read_bytes())==meta["sha256"]
    changed={(r["unit_id"],r.get("operator"),r.get("mutation_sha256")):r
             for r in hist.rows(src) if r["changed_fields"]}
    bases={r["unit_id"]:r for r in hist.rows(hist.OLD/"bases.jsonl.gz")}
    if mode=="moves":
        path=hist.OUT/"moves_completed.jsonl"
        hist.checked(path,json.loads((hist.OUT/"seal.json").read_bytes())["batch_files_excluding_seal"][path.name])
        inputs=hist.rows(path)
    else:
        obs={(r["unit_id"],r["operator"],r["mutation_sha256"]):r
             for file in ("original_reclassified","new_observations","supplement_observations")
             for r in hist.rows(hist.CP41/(file+".jsonl.gz")) if r["outcome"]=="included"}
        inputs=hist.source_rows()
    counts=Counter();units=set();samples=0
    with (OUT/(mode+"_causes.jsonl.gz")).open("xb") as f, gzip.GzipFile(fileobj=f,filename="",mode="wb",mtime=0) as stream:
        for item in inputs:
            uid=item["unit_id"];key=uid,item.get("operator"),item.get("mutation_sha256")
            if key not in changed:continue
            row=changed.pop(key);base=bases[uid];source=hist.base_contents(base)
            truth=json.loads(hist.checked(base["graph_path"],base["graph_sha256"]))
            if mode=="moves":
                site=item["site"];a,b,t=site["start"],site["end"],site["insert"];n=site["file"]
                segment=source[n][a:b];fixed=dict(source);damaged=source;damage={}
                fixed[n],repair=apply_patches(source[n],[Patch(a,b,segment,b"","delete_function"),
                                                          Patch(t,t,b"",b"\n"+segment+b"\n","insert_function")])
                edits={n:repair}
                actual=json.loads(hist.checked(item["graph_path"],row["graph_sha256"]))
            else:
                ref=item["graph"]
                assert row["graph_sha256"]==ref["graph_sha256"]
                actual,_=hist.verify_graph(base,ref["result_path"],ref["result_sha256"],ref["graph_sha256"])
                _,damaged,fixed,damage,edits=hist.restore_sample(base,source,obs[key],migration=False)
            result=analyze(row,source,fixed,damage,edits,truth,actual,damaged)
            counts.update(result["causes"]);units.add(uid);samples+=1
            stream.write((json.dumps(result,separators=(",",":"))+"\n").encode())
    assert not changed and samples==len(meta["differences"])
    data=dict(mode=mode,different_samples=samples,distinct_units=len(units),occurrences=counts,
              breakdown_sha256=hist.sha((OUT/(mode+"_causes.jsonl.gz")).read_bytes()))
    with (OUT/(mode+"_causes.json")).open("x") as f:json.dump(data,f,indent=2);f.write("\n")
    print(data,flush=True)

if __name__=="__main__":main(sys.argv[1])
