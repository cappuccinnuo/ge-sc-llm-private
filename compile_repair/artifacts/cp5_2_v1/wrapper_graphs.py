"""Compare the 550 CP5.1 wrapper rejections against the original graph and source identities."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
OLD=OUT.parent/"cp5_1_v1"
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, expected):
    b=Path(path).read_bytes()
    if sha(b)!=expected:raise ValueError("SHA256 mismatch: "+str(path))
    return json.loads(b)


def key(item):
    return json.dumps(item,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def strip_filename(value, filename):
    if not isinstance(value,dict):return value
    result=dict(value)
    if "filename" in result:
        if result.pop("filename")!=filename:raise ValueError("unexpected source unit")
    return result


def endpoint(value,filename):
    if isinstance(value,list):return value
    result=strip_filename(value,filename)
    if set(result)=={"key5"}:return result["key5"]
    return result


def facts(graph,filename):
    nodes={tuple(n["key5"]):strip_filename(n,filename) for n in graph["nodes"]}
    assert len(nodes)==len(graph["nodes"])
    dec=[strip_filename(d,filename) for d in graph["declarations"]]
    edges=[dict(e,source=endpoint(e["source"],filename),target=endpoint(e["target"],filename)) for e in graph["cfg_edges"]]
    calls=[dict(c,node=endpoint(c["node"],filename),callee=strip_filename(c["callee"],filename)) for c in graph["calls"]]
    return nodes,dec,edges,calls


def sets(left,right):
    a=Counter(map(key,left));b=Counter(map(key,right))
    return dict(before=len(left),after=len(right),missing=sum((a-b).values()),added=sum((b-a).values()),order_equal=left==right)


def main():
    seal=json.loads((OLD/"seal.json").read_bytes())["files_excluding_this_seal"]
    src=OLD/"packed/benchmark.jsonl.gz"
    b=src.read_bytes();assert sha(b)==seal["packed/benchmark.jsonl.gz"]["sha256"]
    rows=[r for r in map(json.loads,gzip.decompress(b).splitlines()) if r["operator"]=="standard_json_input"]
    assert len(rows)==950
    basespath=OUT.parent/"cp4_v1/bases.jsonl.gz";raw_bases=basespath.read_bytes()
    bases={r["unit_id"]:r for r in map(json.loads,gzip.decompress(raw_bases).splitlines())}
    meta=Counter();node_changes=Counter();mismatches=Counter();details=[]
    for row in rows:
        score=row["score"]
        if score.get("migration_counters",{}).get("reason")!="graph_metadata_differ":continue
        assert score["raw_migration_score"]["exact"] and not score["exact"]
        uid=row["unit_id"];base=bases[uid]
        record=checked(row["result_path"],row["result_sha256"])
        path=Path(row["result_path"]);unit=path.parents[1] if path.parent.name.startswith("round_") else path.parent
        observed=checked(unit/"graph.json",row["graph_sha256"]);truth=checked(base["graph_path"],base["graph_sha256"])
        source=record["inputs"];layout=json.loads((path.parent/"project.json").read_bytes())
        source_match=len(source)==1 and source[0]["sha256"]==base["entry_sha256"] and sha(Path(source[0]["path"]).read_bytes())==base["entry_sha256"]
        names=layout["source_units"]
        filename=names[0][1] if len(names)==1 and names[0][0]==names[0][1] else None
        assert not base["project_root"] and source_match and filename is not None
        fields=set(truth)|set(observed);payload={"nodes","declarations","cfg_edges","calls"}
        diff={k:dict(truth=truth.get(k),observed=observed.get(k),truth_present=k in truth,observed_present=k in observed)
              for k in fields-payload if k not in truth or k not in observed or truth[k]!=observed[k]}
        for k,v in diff.items():meta[(k,key(v))]+=1
        a,ad,ae,ac=facts(truth,"")
        b,bd,be,bc=facts(observed,filename)
        left=set(a)-set(b);right=set(b)-set(a);nodefields=Counter()
        for i in set(a)&set(b):
            for k in set(a[i])|set(b[i]):
                if k not in a[i] or k not in b[i] or a[i][k]!=b[i][k]:nodefields[k]+=1
        report={name:sets(l,r) for name,l,r in [("declarations",ad,bd),("cfg_edges",ae,be),("calls",ac,bc)]}
        contract_a={d.get("contract") for d in ad};contract_b={d.get("contract") for d in bd}
        function_a={(d.get("contract"),d.get("function"),d.get("declaration_kind")) for d in ad}
        function_b={(d.get("contract"),d.get("function"),d.get("declaration_kind")) for d in bd}
        unequal=[k for k,v in report.items() if v["missing"] or v["added"]]
        if left or right or nodefields:unequal.append("nodes")
        if contract_a!=contract_b:unequal.append("contract_set")
        if function_a!=function_b:unequal.append("function_set")
        for k in unequal:mismatches[k]+=1
        node_changes.update(nodefields)
        details.append(dict(unit_id=uid,split=row["split"],corpus=row["corpus"],metadata=diff,filename=filename,
            source_sha256=base["entry_sha256"],truth_sha256=base["graph_sha256"],observed_sha256=row["graph_sha256"],
            result_sha256=row["result_sha256"],node_count_truth=len(a),node_count_actual=len(b),nodes_missing=len(left),nodes_added=len(right),
            node_field_changes=dict(nodefields),relations=report,unequal_facts=unequal))
    assert len(details)==550
    path=OUT/"wrapper_graph_pairs.jsonl"
    with path.open("x",encoding="utf8") as f:
        for d in details:f.write(json.dumps(d,sort_keys=True,ensure_ascii=False)+"\n")
    info=dict(units=len(details),fields=[dict(field=k,values=json.loads(v),units=n) for (k,v),n in sorted(meta.items())],
        physical_schema_only=sum(not d["unequal_facts"] for d in details),unequal_facts=dict(mismatches),
        node_field_differences=dict(node_changes),rows_sha256=sha(path.read_bytes()),bases_sha256=sha(raw_bases),
        first_unequal=next((d["unit_id"] for d in details if d["unequal_facts"]),None),
        method="Exact source identity and a single source unit justify translating implicit versus explicit filenames. Compare every node field and the full multiplicities of declarations, CFG edges and calls. No graph or score is modified.")
    with (OUT/"wrapper_graph_summary.json").open("x",encoding="utf8") as f:
        json.dump(info,f,indent=2,sort_keys=True);f.write("\n")
    print(json.dumps(info,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
