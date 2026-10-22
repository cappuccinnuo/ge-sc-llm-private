"""Build and audit Stage J candidates from frozen task manifests; never trains."""
import argparse, csv, hashlib, json, pickle, time
from pathlib import Path
from collections import Counter
from dataclasses import asdict
from scripts.DFG.state.stage_j.cli import sha
from scripts.DFG.state.stage_j.pipeline import prepare_graph, STATE_RELATIONS
from scripts.DFG.state.stage_j.configuration import DDGConfig
from scripts.DFG.state.stage_f.model_adapter import build_dgl, information_increment
from scripts.DFG.graph_audit import fingerprint
ROOT=Path(__file__).resolve().parents[4]

def read(path):return json.loads(Path(path).read_text())
def checked(path,expected,inputs):
    path=Path(path).resolve()
    if sha(path)!=expected:raise ValueError("Input changed: "+str(path))
    inputs[str(path)]=expected
    return path
def relation_set(g):
    return {(s,t,d["edge_type"]) for s,t,d in g.edges(data=True) if d["edge_type"] in STATE_RELATIONS}
def write_json(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False))
def metadata_for(info,inputs):
    matches=[x for x in info["frozen_files"] if Path(x).name=="GRAPH_MANIFEST.json"]
    if len(matches)!=1:raise ValueError("Ambiguous Stage F manifest")
    gm=checked(matches[0],info["frozen_files"][matches[0]],inputs)
    delivery_path=gm.parent.parent/"DELIVERY_MANIFEST.json"
    delivery=read(delivery_path);inputs[str(delivery_path)]=sha(delivery_path)
    accepted=set(delivery["accepted_results"])
    candidates=[(ROOT/k,v["sha256"]) for k,v in delivery["files"].items()
                if Path(k).parent.name in accepted and Path(k).parent.name.startswith("F1_")
                and Path(k).name==info["cohort"]+"_results.json"]
    if len(candidates)!=1:raise ValueError("Ambiguous accepted version sidecar")
    path=checked(candidates[0][0],candidates[0][1],inputs)
    return {name:r.get("metadata") for name,r in read(path).items()}

def run(input_manifest,output):
    output=Path(output)
    if output.exists():raise ValueError("Output already exists; no overwrite or auto-retry")
    output.mkdir(parents=True)
    inputs={str(Path(input_manifest).resolve()):sha(input_manifest)}
    source_files=list((ROOT/"scripts/DFG/state/stage_j").rglob("*.py"))+list(Path(__file__).parent.glob("*.py"))
    code={str(p):sha(p) for p in source_files}
    plan={"version":"stage-j-candidates-v1","input_manifest":str(Path(input_manifest).resolve()),
          "input_sha256":sha(input_manifest),"code_sha256":code,"training":False,
          "modes":["frozen","inheritance","modifiers"],
          "sidecar_assurance":"Observed Stage F delivery SHA, not retroactively H2-sealed."}
    write_json(output/"plan.json",plan)
    write_json(output/"plan.seal.json",{"plan_sha256":sha(output/"plan.json")})
    summary=[];file_rows=[];function_rows=[]
    for task in read(input_manifest)["tasks"]:
        info=read(checked(task["manifest"],task["sha256"],inputs))
        prep=read(checked(info["source_prepared_manifest"],info["source_prepared_manifest_sha256"],inputs))
        metadata=metadata_for(info,inputs)
        basepath=checked(info["graphs"]["E2"]["path"],info["graphs"]["E2"]["sha256"],inputs)
        oldpath=checked(info["graphs"]["E3b"]["path"],info["graphs"]["E3b"]["sha256"],inputs)
        with basepath.open("rb") as f:base=pickle.load(f)
        with oldpath.open("rb") as f:old=pickle.load(f)
        files={d["source_file"] for _,d in base.nodes(data=True)}
        sources={}
        for name in sorted(files):
            item=prep["sources"][name]
            sources[name]=checked(item["path"],item["sha256"],inputs).read_bytes().decode("utf8")
        taskout=output/task["id"];taskout.mkdir()
        input_sources={"sources":{name:dict(prep["sources"][name],metadata=metadata.get(name)) for name in sorted(files)}}
        write_json(taskout/"sources.json",input_sources)
        prior=None
        for mode in plan["modes"]:
            print(task["id"],mode,"start",flush=True)
            start=time.monotonic()
            config=DDGConfig(recovery=mode)
            enhanced,audit=prepare_graph(base,sources,config,metadata)
            relations=relation_set(enhanced)
            if mode=="frozen" and relations!=relation_set(old):
                raise AssertionError("Frozen Stage F relations not reproduced")
            if prior is not None and not prior<=relations:
                raise AssertionError("Coverage extension lost prior state relation")
            prior=relations
            dg,_=build_dgl(enhanced)
            for rel in STATE_RELATIONS|{"DATA_DEF_USE"}:
                assert sum(dg.num_edges(k) for k in dg.canonical_etypes if k[1]==rel)==sum(d["edge_type"]==rel for _,_,d in enhanced.edges(data=True))
            modeout=taskout/mode;modeout.mkdir()
            with (modeout/"enhanced.gpickle").open("wb") as f:pickle.dump(enhanced,f,pickle.HIGHEST_PROTOCOL)
            write_json(modeout/"audit.json",audit)
            delta=information_increment(old,enhanced)
            fn=[x for a in audit["files"].values() for x in a.get("functions",[])]
            row={"task_id":task["id"],"mode":mode,"files":len(files),"nodes":len(enhanced),"edges":enhanced.number_of_edges(),
                 "functions":len(fn),"supported":sum(x["after"]!="function_fallback" for x in fn),
                 "recovered":sum(x["recovered"] for x in fn),
                 "recovered_runtime":sum(x["recovered"] and x.get("runtime_function",False) for x in fn),
                 "state_def_use":sum(d["edge_type"]=="STATE_DEF_USE" for _,_,d in enhanced.edges(data=True)),
                 "state_order":sum(d["edge_type"]=="STATE_ACCESS_ORDER" for _,_,d in enhanced.edges(data=True)),
                 "call_write":sum(d["edge_type"]=="EXTERNAL_CALL_BEFORE_STATE_WRITE" for _,_,d in enhanced.edges(data=True)),
                 "new_relations_vs_frozen":len(relations-relation_set(old)),
                 "new_context_targets_vs_frozen":delta["new_context_target_nodes"],
                 "seconds":time.monotonic()-start}
            summary.append(row)
            manifest={"task_id":task["id"],"cohort":info["cohort"],"task":info["task"],
                      "graph":str(modeout/"enhanced.gpickle"),"graph_sha256":sha(modeout/"enhanced.gpickle"),
                      "audit_sha256":sha(modeout/"audit.json"),"config":asdict(config),
                      "base_sha256":sha(basepath),"reference_sha256":sha(oldpath),
                      "canonical_schema":[list(k) for k in dg.canonical_etypes],
                      "context_increment":delta,"summary":row,"training_executed":False}
            write_json(modeout/"manifest.json",manifest)
            for name,a in audit["files"].items():
                fs=a.get("functions",[])
                file_rows.append({"task_id":task["id"],"mode":mode,"file":name,
                    "source_sha256":prep["sources"][name]["sha256"],"status":a["status"],
                    "recovered":sum(x["recovered"] for x in fs),
                    "missing_anchors":len(a.get("projection",{}).get("missing_anchors",[])),
                    "projection_fallback":a.get("projection",{}).get("file_projection_fallback",""),
                    "reason":a.get("reason",""),
                    "added_vs_frozen":sum(s in base and base.nodes[s]["source_file"]==name for s,t,rel in relations-relation_set(old))})
                for x in fs:
                    function_rows.append(dict(task_id=task["id"],mode=mode,file=name,
                       source_sha256=prep["sources"][name]["sha256"],function=x["function"],
                       name=x.get("name",""),before=x["before"],after=x["after"],route=x["route"],
                       recovered=x["recovered"],runtime=x.get("runtime_function",False),
                       before_reason=json.dumps(x.get("before_diagnostics",[])),
                       after_reason=json.dumps(x.get("after_diagnostics",[]))))
            print(json.dumps(row),flush=True)
        del base,old,enhanced,dg
    for name,rows in [("summary.csv",summary),("files.csv",file_rows),("functions.csv",function_rows)]:
        with (output/name).open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for path,digest in dict(inputs,**code).items():
        if sha(path)!=digest:raise ValueError("Frozen dependency changed during build: "+path)
    write_json(output/"input_manifest.json",{"inputs":inputs,"code":code})
    write_json(output/"receipt.json",{"status":"passed","tasks":4,"candidate_graphs":12,
        "training_executed":False,"plan_sha256":sha(output/"plan.json"),
        "files":{str(p.relative_to(output)):sha(p) for p in output.rglob("*") if p.is_file()}})
    return summary
def main():
    p=argparse.ArgumentParser();p.add_argument("--input-manifest",required=True);p.add_argument("--output",required=True)
    args=p.parse_args();run(args.input_manifest,args.output)
if __name__=="__main__":main()
