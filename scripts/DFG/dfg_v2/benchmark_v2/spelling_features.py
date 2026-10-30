"""Prompt 8G independent token views; frozen models/graphs stay unchanged.

Assembly adapts benchmark_v2/feature_view.py (SHA256
390a16c62b9b2126b4301e8a347581dc034ec426abe921b555f66de2b306365b).
The new view transforms both cohorts, unlike 8D's SolidiFI-only view.
No optimizer, checkpoint training or new feature extractor is introduced.
"""
import argparse
import copy
import gc
import hashlib
from pathlib import Path

import networkx as nx
import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.common import seed_all, tensor_digest
from .. import AUX_NODE_TYPES
from ..tokens import TokenEncoder
from ..model import make_model
from ..supervision import DfgV2Supervision
from .prepare import read, write, ref, checked
from .prepare_spelling import require_semantic_pass, load_result
from .anon_parity import node_code_view
from .feature_view import graph_fingerprint, vector_sha, _write_npz, _profile_bindings

VERSION = "prompt8g-all-hcg-spelling-feature-v1"


def probe_gate(naming, semantic, probes):
    manifest, sources, _, _ = require_semantic_pass(naming, semantic)
    path = Path(probes)/"summary.json";summary=read(path)
    if read(Path(probes)/"summary.seal.json")["summary"] != ref(path):
        raise ValueError("Probe summary seal differs")
    plan=read(checked(summary["plan"]))
    if plan["naming"]!=ref(Path(naming)/"manifest.json") or plan["semantic"]!=ref(Path(semantic)/"summary.json"):
        raise ValueError("Probe inputs differ")
    passed = all(v["delta_bf1_pp"]<=5 and v["passed"] is True
                 for task in summary["P2"].values() for v in task.values())
    passed = passed and summary["P3"]["auc"]<=.60 and summary["P3"]["passed"] is True
    if not passed or summary["passed"] is not True or len(summary["P2"])!=2:
        raise ValueError("Frozen P2/P3 gate failed; features forbidden")
    for task in summary["P2"].values():
        if set(task)!= {"orig","C1"}:
            raise ValueError("Missing P2 label view")
        for v in task.values():
            checked(v["artifact"])
    checked(summary["P3"]["artifact"])
    for v in summary["keywords"].values():
        checked(v["artifact"])
        if v["original_predictions_exact"] is not True:
            raise ValueError("Keyword baseline changed")
    return manifest,sources,summary


def build_features(naming, semantic, probes, output):
    manifest,sources,_=probe_gate(naming,semantic,probes)
    output=Path(output);output.mkdir(exist_ok=False)
    formal=read(checked(manifest["formal_plan"]))
    task_views, details = {}, {}
    for tid,task in formal["tasks"].items():
        directory=output/tid;directory.mkdir()
        info=read(checked(task["prepared"]["0/1"]))
        base=read_graph(checked(info["profiles"]["G0"]["graph"]))
        before=graph_fingerprint(base)
        codes={}
        for file,reference in task["record"]["sources"].items():
            ident=task["record"]["category"]+"/"+file
            if sources[ident]["source"]!=reference:
                raise ValueError("Feature source reference differs")
            source,result=load_result(sources[ident])
            ids=[n for n,a in base.nodes(data=True) if a["source_file"]==file]
            local,_=node_code_view(base.subgraph(ids).copy(),file,source,result)
            codes.update(local)
        if set(codes)!=set(base):
            raise ValueError("Incomplete all-node code view")
        encoder=TokenEncoder(task["record"]["feature"])
        encoded={}
        rows,original,anonymous=[],[],[]
        for nid,a in base.nodes(data=True):
            old=np.asarray(a["token"])
            old_sha=vector_sha(old)
            for code in (a["code"],codes[nid]):
                if code not in encoded:
                    encoded[code]=encoder(code)
            if not np.array_equal(encoded[a["code"]].view(np.uint32),old.view(np.uint32)):
                raise ValueError("Original token re-encoding differs")
            new=encoded[codes[nid]]
            rows.append(dict(original_graph_node_id=nid,file=a["source_file"],node_type=a["node_type"],
                source_sha256=task["record"]["sources"][a["source_file"]]["sha256"],
                code_sha256=hashlib.sha256(a["code"].encode("utf8")).hexdigest(),
                rewritten_code_sha256=hashlib.sha256(codes[nid].encode("utf8")).hexdigest(),
                original_vector_sha256=old_sha,anonymous_vector_sha256=vector_sha(new),
                feature_changed=not np.array_equal(old.view(np.uint32),new.view(np.uint32))))
            original.append(old.copy());anonymous.append(new.copy())
        profiles=_profile_bindings(task,rows)
        arrays={"original":np.stack(original),"anonymous":np.stack(anonymous)}
        for view,values in arrays.items():
            _write_npz(directory/(view+".npz"),values)
            record=dict(version=VERSION,view=view,task_id=tid,rows=rows,profiles=profiles,
                sources=task["record"]["sources"],data=ref(directory/(view+".npz")),
                feature_shape=list(values.shape),feature_dtype="float32",
                vector_sha_field=view+"_vector_sha256",tokenizer=encoder.provenance,
                transform_cohorts="all original nodes in all files",auxiliary_features_unchanged=True,
                original_inputs_unchanged=True)
            write(directory/(view+"_manifest.json"),record)
        if graph_fingerprint(base)!=before:
            raise ValueError("Original graph mutated")
        task_views[tid]={view:ref(directory/(view+"_manifest.json")) for view in arrays}
        details[tid]=dict(nodes=len(rows),changed_nodes=sum(r["feature_changed"] for r in rows),
                         original_reencoding_exact_nodes=len(rows),profiles=list(profiles))
        print("features",tid,details[tid],flush=True)
    result=dict(version=VERSION,naming=ref(Path(naming)/"manifest.json"),
        semantic=ref(Path(semantic)/"summary.json"),probes=ref(Path(probes)/"summary.json"),
        formal_plan=manifest["formal_plan"],task_views=task_views,details=details,
        original_inputs_unchanged=True,all_original_hcg_nodes=True,implementation=ref(Path(__file__)),
        hgt_fit_count=0,optimizer_steps=0,execution_authorized=False)
    write(output/"manifest.json",result)
    write(output/"manifest.seal.json",dict(manifest=ref(output/"manifest.json")))
    return result


def assemble(graph_or_path, view_ref):
    view=read(checked(view_ref))
    if view["version"]!=VERSION or view["view"] not in ("original","anonymous"):
        raise ValueError("Unknown spelling feature view")
    graph=graph_or_path if isinstance(graph_or_path,nx.Graph) else read_graph(graph_or_path)
    fingerprint=graph_fingerprint(graph)
    if fingerprint not in {v["graph_fingerprint"] for v in view["profiles"].values()}:
        raise ValueError("Graph schema/labels/edges/features do not match feature view")
    rows=view["rows"]
    ids=[n for n,a in graph.nodes(data=True) if a["node_type"] not in AUX_NODE_TYPES]
    if ids!=[r["original_graph_node_id"] for r in rows] or len(ids)!=len(set(ids)):
        raise ValueError("Original feature row identity/order differs")
    with np.load(str(checked(view["data"])),allow_pickle=False) as archive:
        if set(archive.files)!={"features"}:
            raise ValueError("Unexpected feature array contents")
        values=archive["features"].copy()
    if values.dtype!=np.float32 or values.shape!=(len(rows),512):
        raise ValueError("Feature shape/dtype differs")
    if list(values.shape)!=view["feature_shape"] or not np.isfinite(values).all():
        raise ValueError("Non-finite or mismatched features")
    result=copy.deepcopy(graph)
    for row,vector in zip(rows,values):
        nid=row["original_graph_node_id"];a=graph.nodes[nid]
        if (a["source_file"]!=row["file"] or a["node_type"]!=row["node_type"]
                or view["sources"][row["file"]]["sha256"]!=row["source_sha256"]
                or hashlib.sha256(a["code"].encode("utf8")).hexdigest()!=row["code_sha256"]
                or vector_sha(a["token"])!=row["original_vector_sha256"]
                or vector_sha(vector)!=row[view["vector_sha_field"]]):
            raise ValueError("Feature row source/code/token mismatch")
        result.nodes[nid]["token"]=vector.copy()
    restored=copy.deepcopy(result)
    for nid in ids:
        restored.nodes[nid]["token"]=graph.nodes[nid]["token"].copy()
    if graph_fingerprint(restored)!=fingerprint:
        raise AssertionError("Non-token graph data changed")
    return result


def verify_models(feature_directory, output):
    directory=Path(feature_directory);features=read(directory/"manifest.json")
    if read(directory/"manifest.seal.json")["manifest"]!=ref(directory/"manifest.json"):
        raise ValueError("Feature manifest seal differs")
    formal=read(checked(features["formal_plan"]))
    output=Path(output);output.mkdir(exist_ok=False)
    reports=[]
    torch.set_num_threads(2)
    for tid,task in formal["tasks"].items():
        info=read(checked(task["prepared"]["0/1"]))
        config=task["config"]
        for profile,entry in info["profiles"].items():
            initial=torch.load(str(checked(entry["initial"])),map_location="cpu")
            if initial.get("kind")!="untrained_initial" or initial.get("optimizer_steps")!=0:
                raise ValueError("Model proof requires a saved untrained initial")
            if tensor_digest(initial["state_dict"])!=entry["initial"]["state_sha256"]:
                raise ValueError("Initial tensor digest differs")
            original=read_graph(checked(entry["graph"]))
            modes=("direct","original","anonymous") if profile=="G0" else ("anonymous",)
            identity=None
            observations={}
            for mode in modes:
                graph=original if mode=="direct" else assemble(original,features["task_views"][tid][mode])
                seed_all(info["seeds"]["constructor"])
                model=make_model(task["record"]["task"],graph,profile,"cpu",
                    hidden_size=config["hidden_size"],layers=config["layers"],heads=config["heads"],
                    reducer=formal["reducer"],layer_impl=formal["layer_impl"])
                model.load_state_dict(initial["state_dict"])
                model.eval()
                part=DfgV2Supervision(model,task["record"]["task"],task["record"]["sources"])
                with torch.no_grad():
                    logits=part.forward(model).detach().cpu().clone()
                if not bool(torch.isfinite(logits).all()):
                    raise ValueError("Non-finite anonymous model forward")
                if mode=="direct":identity=logits
                if mode=="original" and not torch.equal(logits,identity):
                    raise ValueError("Identity view forward differs from original G0")
                if tensor_digest(model.state_dict())!=entry["initial"]["state_sha256"]:
                    raise ValueError("Forward modified frozen initial parameters")
                observations[mode]=dict(logits_shape=list(logits.shape),
                    logits_sha256=hashlib.sha256(logits.numpy().tobytes()).hexdigest(),
                    finite=True,parameters_unchanged=True,original_supervised_nodes=len(part.full_ids))
                del model,part,graph
                gc.collect()
            reports.append(dict(task=tid,profile=profile,initial=entry["initial"],
                views=observations,identity_forward_bitwise=True if profile=="G0" else None,
                anonymous_assembly_passed=True,original_inputs_unchanged=True))
            print("model proof",tid,profile,flush=True)
        write(output/(tid+".json"),[r for r in reports if r["task"]==tid])
    result=dict(passed=True,features=ref(directory/"manifest.json"),profile_checks=len(reports),
                forward_calls=sum(len(r["views"]) for r in reports),G0_identity_tasks=4,
                artifacts={tid:ref(output/(tid+".json")) for tid in formal["tasks"]},
                optimizer_steps=0,hgt_fit_count=0,device="cpu",gpu_used=False,
                old_untrained_weights_used_for_interface_proof_only=True)
    write(output/"summary.json",result)
    write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command")
    a=sub.add_parser("build")
    for n in ("naming","semantic","probes","output"):a.add_argument("--"+n,required=True)
    a=sub.add_parser("verify")
    a.add_argument("--features",required=True);a.add_argument("--output",required=True)
    args=p.parse_args()
    if args.command=="build":build_features(args.naming,args.semantic,args.probes,args.output)
    elif args.command=="verify":verify_models(args.features,args.output)
    else:p.error("Choose build or verify")
