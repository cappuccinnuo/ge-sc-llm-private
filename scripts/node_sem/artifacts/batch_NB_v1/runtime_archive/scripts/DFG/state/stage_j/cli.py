"""General Stage J graph enhancement; requires explicit local graph/source manifest."""
import argparse, hashlib, json, pickle
from pathlib import Path
from dataclasses import asdict
from collections import Counter
from .pipeline import prepare_graph
from .configuration import DDGConfig
from ..stage_f.model_adapter import build_dgl

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""):h.update(c)
    return h.hexdigest()

def load_sources(manifest):
    manifest=Path(manifest)
    data=json.loads(manifest.read_text())
    records=data.get("sources",data)
    sources,metadata={},{}
    for name,record in records.items():
        path=Path(record["path"])
        if not path.is_absolute():path=manifest.parent/path
        if sha(path)!=record["sha256"]:raise ValueError("Source digest mismatch: "+name)
        sources[name]=path.read_bytes().decode("utf8")
        if record.get("metadata") is not None:metadata[name]=record["metadata"]
    return sources,metadata

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph",required=True);p.add_argument("--graph-sha256",required=True)
    p.add_argument("--sources",required=True);p.add_argument("--output",required=True)
    p.add_argument("--add-scalar",action="store_true")
    p.add_argument("--state-mode",choices=["off","def_use","orders"],default="orders")
    p.add_argument("--recovery",choices=["frozen","inheritance","modifiers"],default="modifiers")
    p.add_argument("--disable-ddg",action="store_true")
    args=p.parse_args(argv);out=Path(args.output)
    if out.exists():raise ValueError("Output exists; old results are never overwritten")
    if sha(args.graph)!=args.graph_sha256:raise ValueError("Input graph SHA mismatch")
    sources,metadata=load_sources(args.sources)
    with Path(args.graph).open("rb") as f:graph=pickle.load(f)
    config=DDGConfig(not args.disable_ddg,args.add_scalar,args.state_mode,args.recovery)
    result,audit=prepare_graph(graph,sources,config,metadata)
    dg,_=build_dgl(result)
    counts={r:sum(dg.num_edges(k) for k in dg.canonical_etypes if k[1]==r)
            for r in ("DATA_DEF_USE","STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE")}
    for rel,count in counts.items():
        assert count==sum(d.get("edge_type")==rel for _,_,d in result.edges(data=True))
    out.mkdir(parents=True)
    with (out/"enhanced.gpickle").open("wb") as f:pickle.dump(result,f,pickle.HIGHEST_PROTOCOL)
    (out/"audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False))
    record={"input_graph":str(Path(args.graph).resolve()),"input_sha256":args.graph_sha256,
            "source_manifest_sha256":sha(args.sources),"config":asdict(config),
            "output_sha256":sha(out/"enhanced.gpickle"),"audit_sha256":sha(out/"audit.json"),
            "canonical_schema":[list(k) for k in dg.canonical_etypes],
            "forward_relation_counts":counts,"training_executed":False}
    (out/"manifest.json").write_text(json.dumps(record,indent=2))
    print(json.dumps({"nodes":len(result),"edges":result.number_of_edges(),
                     "relations":counts,"output":str(out)},indent=2))
if __name__=="__main__":main()
