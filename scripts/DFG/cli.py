"""Offline HCG/DDG selection. All outputs are new directories under scripts/DFG."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

if __package__ in (None,""):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from scripts.DFG import __version__
from scripts.DFG.models import DDGConfig
from scripts.DFG.configuration import prepare_graph
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.frontend import library_path
from scripts.labeling_v2.safe_graph import loads_graph, read_graph, write_graph

DDG_ROOT=Path(__file__).resolve().parent

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def output_directory(path):
    p=Path(path).resolve()
    if DDG_ROOT not in p.parents:
        raise ValueError("Output must be a new directory below scripts/DFG")
    if p.exists(): raise FileExistsError("Refusing to overwrite output: "+str(p))
    return p

def read_sources(graph, directory=None, manifest=None):
    names=list(dict.fromkeys(d["source_file"] for _,d in graph.nodes(data=True)))
    records={}
    if manifest:
        manifest=Path(manifest).resolve()
        records=json.loads(manifest.read_text(encoding="utf8"))
        if not isinstance(records,dict): raise ValueError("Source manifest must be an object")
    sources,modes,used,missing={},{},{},[]
    for name in names:
        expected=None
        if manifest:
            if name not in records:
                missing.append(name); continue
            item=records[name]
            if not isinstance(item,dict) or "path" not in item:
                raise ValueError("Each source record requires path; optional sha256/scope_mode")
            p=(manifest.parent/Path(item["path"])).resolve()
            expected=item.get("sha256")
            if item.get("scope_mode"):modes[name]=item["scope_mode"]
        else:
            root=Path(directory).resolve()
            p=(root/name).resolve()
            if root not in p.parents:
                raise ValueError("Source identity escapes --source_dir")
        if not p.is_file():
            missing.append(name); continue
        raw=p.read_bytes()
        digest=sha(raw)
        if expected and expected!=digest:
            raise ValueError("Source checksum mismatch: "+name)
        sources[name]=raw.decode("utf8")
        used[name]={"path":str(p),"sha256":digest}
        if name in modes: used[name]["scope_mode"]=modes[name]
    return sources,modes,used,missing

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph",required=True)
    p.add_argument("--output",required=True,help="New directory under scripts/DFG")
    src=p.add_mutually_exclusive_group()
    src.add_argument("--source_dir")
    src.add_argument("--source_manifest")
    mode=p.add_mutually_exclusive_group()
    mode.add_argument("--use_ddg",action="store_true",dest="use_ddg")
    mode.add_argument("--no_ddg",action="store_false",dest="use_ddg")
    p.set_defaults(use_ddg=False)
    p.add_argument("--max_iterations",type=int,default=100000)
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    out=output_directory(args.output)
    config=DDGConfig(args.use_ddg,args.max_iterations)
    if config.use_ddg and not (args.source_dir or args.source_manifest):
        raise ValueError("--use_ddg requires --source_dir or --source_manifest")
    input_path=Path(args.graph).resolve()
    raw=input_path.read_bytes()
    graph=loads_graph(raw)
    print("Input: {} nodes, {} edges; use_ddg={}".format(
        len(graph),graph.number_of_edges(),config.use_ddg),flush=True)
    sources,modes,used,missing={},{},{},[]
    if config.use_ddg:
        sources,modes,used,missing=read_sources(graph,args.source_dir,args.source_manifest)
    enhanced,audit=prepare_graph(graph,sources,config,modes)
    if input_path.read_bytes()!=raw:
        raise ValueError("Input graph changed during enhancement")
    for info in used.values():
        if sha(Path(info["path"]).read_bytes())!=info["sha256"]:
            raise ValueError("Source changed during enhancement: "+info["path"])
    inputs={"graph_path":str(input_path),"graph_sha256":sha(raw),
            "sources":used,"missing_sources":missing,"ddg_version":__version__,
            "created_utc":datetime.now(timezone.utc).isoformat()}
    if config.use_ddg:
        lib=library_path()
        inputs["grammar"]={"path":str(lib),"sha256":sha(lib.read_bytes())}
    audit["inputs"]=inputs
    # JSON conversion checked before any output is created.
    audit_text=json.dumps(audit,ensure_ascii=False,indent=2)
    out.mkdir(parents=True,exist_ok=False)
    write_graph(enhanced,out/"hcg.gpickle")
    if fingerprint(read_graph(out/"hcg.gpickle"))!=fingerprint(enhanced):
        raise AssertionError("Written graph failed round-trip verification")
    (out/"audit.json").write_text(audit_text+"\n",encoding="utf8")
    (out/"source_manifest.json").write_text(
        json.dumps(used,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("Output: {} nodes, {} edges; added DATA_DEF_USE={}".format(
        len(enhanced),enhanced.number_of_edges(),audit["invariants"]["ddg_edges"]),flush=True)
    for file,record in audit["files"].items():
        stats=record.get("analysis",{})
        proj=record.get("projection",{})
        print("{}: supported functions={}/{}; facts projected={}/{}; diagnostics={}".format(
            file,stats.get("functions_supported",0),stats.get("functions_total","unknown"),
            proj.get("facts_projected",0),proj.get("facts_total",0),
            len(record.get("diagnostics",[]))),flush=True)
    print("Wrote "+str(out/"hcg.gpickle"),flush=True)
    return audit

if __name__=="__main__":
    main()
