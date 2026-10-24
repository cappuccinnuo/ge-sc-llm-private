"""Checksummed L3 builds and isolated CPU forward acceptance, without fitting."""
import argparse
import copy
import csv
import gc
import os
import random
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.DFG.integration.pipeline import computation_fingerprint
from scripts.labeling_v2.safe_graph import read_graph, write_graph
from . import ENV_FLOW, ENV_SOURCE, VERSION
from .env import ENV_KEYS
from .l1_build import ARTIFACTS, _runtime, _unique_tasks, _function_records
from .l2_build import verify_l1, load_sources
from .l3 import augment_l3, assert_preserved
from .tokens import TokenEncoder

DEFAULT_L2 = ARTIFACTS / "l2_build_r1"
DEFAULT_OUTPUT = ARTIFACTS / "l3_build"


def verify_l2(directory):
    directory = Path(directory).resolve()
    receipt = read_json(directory/"receipt.json")
    if receipt.get("status") != "accepted" or receipt.get("training_executed") is not False or receipt.get("optimizer_steps") != 0:
        raise ValueError("L2 receipt is not accepted nontraining data")
    summary = read_json(checked(directory/"summary.json", receipt["summary_sha256"]))
    run_inputs = read_json(directory/"run_inputs.json")
    if (summary.get("profile") != "G2R" or summary.get("training_executed") is not False
            or summary.get("all_acceptance_passed") is not True):
        raise ValueError("Expected G2R input")
    if not (summary["runtime"] == receipt["runtime"] == run_inputs["runtime"]):
        raise ValueError("L2 runtime records disagree")
    # New L3 modules may be added; P4.0 computation files must remain identical.
    root = Path(__file__).resolve().parents[3]
    for name, digest in receipt["runtime"].items():
        checked(root/name, digest)
    l1, l1_binding = verify_l1(run_inputs["L1"]["directory"])
    if l1_binding != run_inputs["L1"] or receipt["L1_receipt_sha256"] != l1_binding["receipt_sha256"]:
        raise ValueError("L2/P2 L1 provenance differs")
    tasks = _unique_tasks(summary,"L2 summary")
    if set(tasks) != set(receipt["task_manifests"]) or set(tasks) != set(l1):
        raise ValueError("L2 task matrix differs")
    result = {}
    for tid, row in tasks.items():
        td = directory/tid
        bundle = read_json(checked(td/"manifest.json",receipt["task_manifests"][tid]))
        if bundle != row["bundle"] or bundle.get("layer")!="L2" or bundle.get("profile")!="G2R":
            raise ValueError("L2 task bundle mismatch")
        if bundle.get("training_executed") is not False:
            raise ValueError("Unexpected trained graph bundle")
        for name,digest in bundle["files"].items():
            checked(td/(name+".json"),digest)
        checked(bundle["graph"]["path"],bundle["graph"]["sha256"])
        inputs=read_json(td/"inputs.json")
        if inputs["original_inputs"]!=l1[tid]["inputs"] or inputs["L1_graph"]!=l1[tid]["bundle"]["graph"]:
            raise ValueError("L2 frozen inputs differ from L1")
        checked(inputs["L1_bundle"],inputs["L1_bundle_sha256"])
        if inputs["L1_bundle_sha256"]!=l1_binding["task_manifests"][tid]:
            raise ValueError("L2 L1 bundle SHA differs")
        result[tid]=dict(directory=td,bundle=bundle,inputs=inputs,summary=row,l1=l1[tid])
    return result,dict(directory=str(directory),receipt_sha256=sha256(directory/"receipt.json"),
        summary_sha256=sha256(directory/"summary.json"),run_inputs_sha256=sha256(directory/"run_inputs.json"),
        task_manifests=receipt["task_manifests"],runtime=receipt["runtime"])


def token_sample(graph, encoder, count=20, seed=0):
    selected=random.Random(seed).sample(list(graph), min(count,len(graph)))
    rows=[]
    for node in selected:
        data=graph.nodes[node]
        first,second=encoder(data.get("code") or ""),encoder(data.get("code") or "")
        old=data["token"]
        exact=type(old) is type(first) and old.dtype==first.dtype and old.shape==first.shape and np.array_equal(old,first)
        if not exact or not np.array_equal(first,second):
            raise ValueError("Frozen tokenizer parity failed at node "+str(node))
        rows.append(dict(node_id=int(node),source_file=data["source_file"],code=data["code"],
                         exact=True,repeat_exact=True))
    return dict(seed=seed,requested=count,matched=len(rows),selected=rows,tokenizer=encoder.provenance)


def coverage(graph,audit,l1_audit):
    fallback={identity for identity,rec in _function_records(l1_audit).items() if rec["status"]!="supported"}
    projected=[e for e in audit["evidence"] if e["status"]=="projected"]
    actual={(s,t) for s,t,d in graph.edges(data=True) if d["edge_type"]==ENV_FLOW}
    if actual!={(e["source"],e["target"]) for e in projected}:
        raise AssertionError("Environment evidence and graph disagree")
    unsupported={(e["source"],e["target"]) for e in projected if e["callable"] in fallback}
    per_key={}
    for key in ENV_KEYS:
        hubs=[n for n,d in graph.nodes(data=True) if d["node_type"]==ENV_SOURCE and d["code"]==key]
        rows=[e for e in audit["evidence"] if e["env_key"]==key]
        shadows=Counter()
        for rec in audit["files"].values():shadows.update(rec["shadowed"].get(key,{}))
        per_key[key]=dict(nodes=len(hubs),edges=sum(graph.out_degree(n) for n in hubs),
            occurrences=len(rows),spellings=dict(Counter(e["spelling"] for e in rows)),
            projected=sum(e["status"]=="projected" for e in rows),
            unmapped=dict(Counter(e["statement"]["role"] for e in rows if e["status"]=="unmapped")),
            shadowed=dict(shadows))
    unknown=Counter()
    for rec in audit["files"].values():unknown.update(rec["unknown_env_member"])
    return dict(env_nodes=sum(v["nodes"] for v in per_key.values()),ENV_FLOW=len(actual),
        per_key=per_key,unknown_env_member=dict(unknown),
        assembly_skipped=sum(r["assembly_skipped"] for r in audit["files"].values()),
        L1_fallback_functions=len(fallback),L1_fallback_ENV_FLOW=len(unsupported),
        L1_fallback_with_ENV_FLOW=sorted({e["callable"] for e in projected if e["callable"] in fallback}),
        unmapped=sum(e["status"]=="unmapped" for e in audit["evidence"]),
        file_fallbacks=[dict(file=file,diagnostic=d) for file,r in audit["files"].items()
                        for d in r["diagnostics"] if d["kind"] in ("file_fallback","projection_fallback")])


def sample_edges(graph,audit,count=20,seed=0):
    edges=sorted([(s,t,d) for s,t,d in graph.edges(data=True) if d["edge_type"]==ENV_FLOW],
                 key=lambda e:(graph.nodes[e[0]]["source_file"],graph.nodes[e[0]]["code"],str(e[1])))
    selected=random.Random(seed).sample(edges,min(count,len(edges)))
    return dict(seed=seed,requested=count,edges=[dict(source=int(s),target=int(t),
        file=graph.nodes[s]["source_file"],key=d["env_key"],spellings=d["spellings"],
        target_code=graph.nodes[t]["code"],evidence_indices=d["evidence_indices"]) for s,t,d in selected])


def run(output=DEFAULT_OUTPUT,l2_directory=DEFAULT_L2):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError("Refusing to overwrite "+str(output))
    tasks,binding=verify_l2(l2_directory)
    runtime=_runtime()
    output.mkdir(parents=True)
    write_json(output/"run_inputs.json",dict(version=VERSION,L2=binding,runtime=runtime,
        training_executed=False,real_forward="CPU eval no_grad once per profile"))
    records=[]
    for tid,rec in tasks.items():
        started=time.monotonic()
        print(tid+": L3 graph and token audit",flush=True)
        ref=rec["bundle"]["graph"]
        base=read_graph(checked(ref["path"],ref["sha256"]))
        if fingerprint(base)!=ref["fingerprint"] or computation_fingerprint(base)!=ref["computation_fingerprint"]:
            raise ValueError("L2 graph fingerprint mismatch")
        sources,metadata,used=load_sources(rec["l1"],base)
        if used!=rec["inputs"]["sources"]:raise ValueError("L2 source identities differ")
        task=read_json(checked(rec["l1"]["inputs"]["task_manifest"],rec["l1"]["inputs"]["task_manifest_sha256"]))
        encoder=TokenEncoder(task["feature"])
        tokens=token_sample(base,encoder)
        graph,audit=augment_l3(base,sources,metadata,encoder)
        encoder.verify_assets()
        invariant=assert_preserved(base,graph)
        metrics=coverage(graph,audit,read_json(rec["l1"]["directory"]/"audit.json"))
        td=output/tid
        td.mkdir()
        path=td/"hcg.gpickle"
        write_graph(graph,path)
        if fingerprint(read_graph(path))!=fingerprint(graph):raise AssertionError("L3 serialization changed graph")
        graph_ref=dict(path=str(path),sha256=sha256(path),fingerprint=fingerprint(graph),
                       computation_fingerprint=computation_fingerprint(graph))
        inputs=dict(L2_graph=ref,L2_manifest=str(rec["directory"]/"manifest.json"),
            L2_manifest_sha256=binding["task_manifests"][tid],sources=used,
            source_manifest=rec["inputs"]["source_manifest"],source_manifest_sha256=rec["inputs"]["source_manifest_sha256"],
            task_manifest=rec["l1"]["inputs"]["task_manifest"],
            task_manifest_sha256=rec["l1"]["inputs"]["task_manifest_sha256"],feature=task["feature"])
        documents=dict(audit=audit,inputs=inputs,acceptance=dict(invariants=invariant,coverage=metrics),
                       token_sample=tokens,edge_sample=sample_edges(graph,audit))
        for name,data in documents.items():write_json(td/(name+".json"),data)
        # Release parent's graph/model data before sequential isolated forwards.
        task_kind=rec["summary"]["task"]
        original_nodes=len(base);nodes=len(graph);edges=graph.number_of_edges()
        del base,graph,audit,encoder
        gc.collect()
        forwards={}
        for profile in ("G3","G3R"):
            command=[sys.executable,"-B","-m","scripts.DFG.dfg_v2.l3_forward","--graph",str(path),
                     "--sha256",graph_ref["sha256"],"--task",task_kind,"--profile",profile,
                     "--output",str(td/(profile+"_forward.json"))]
            with (td/(profile+"_forward.log")).open("x") as log:
                done=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                    env=dict(os.environ,CUDA_VISIBLE_DEVICES=""))
            if done.returncode:
                raise RuntimeError("CPU forward failed; see "+str(td/(profile+"_forward.log")))
            forward=read_json(td/(profile+"_forward.json"))
            if forward["status"]!="accepted" or forward["graph_sha256"]!=graph_ref["sha256"]:
                raise ValueError("Forward receipt mismatch")
            forwards[profile]=forward
            print(tid+" "+profile+": finite "+str(forward["output_shape"]),flush=True)
        documents.update({p+"_forward":d for p,d in forwards.items()})
        bundle=dict(version=VERSION,layer="L3",profiles=["G3","G3R"],graph=graph_ref,
            files={name:sha256(td/(name+".json")) for name in documents},
            nodes=nodes,edges=edges,training_executed=False,optimizer_steps=0)
        write_json(td/"manifest.json",bundle)
        row=dict(metrics,task_id=tid,task=task_kind,files=len(sources),original_nodes=original_nodes,
            nodes=nodes,edges=edges,bundle=bundle,parameters={p:d["parameters"] for p,d in forwards.items()},
            CPU_forward={p:{k:d[k] for k in ("output_shape","forward_seconds","process_peak_rss_mib","canonical")} for p,d in forwards.items()},
            seconds=time.monotonic()-started,training_executed=False)
        write_json(td/"summary.json",row)
        records.append(row)
        for entry in used.values():checked(entry["path"],entry["sha256"])
        for asset,digest in task["feature"]["asset_hashes"].items():checked(asset,digest)
    verify_l2(l2_directory)
    if _runtime()!=runtime:raise AssertionError("Runtime changed during L3 build")
    summary=dict(version=VERSION,profiles=["G3","G3R"],tasks=records,runtime=runtime,
                 all_acceptance_passed=True,training_executed=False,optimizer_steps=0)
    write_json(output/"summary.json",summary)
    with (output/"summary.csv").open("w",newline="") as stream:
        fields=["task_id","original_nodes","env_nodes","ENV_FLOW","unmapped","L1_fallback_ENV_FLOW"]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerows({key:row[key] for key in fields} for row in records)
    write_json(output/"receipt.json",dict(version=VERSION,status="accepted",
        L2_receipt_sha256=binding["receipt_sha256"],runtime=runtime,
        summary_sha256=sha256(output/"summary.json"),
        task_manifests={row["task_id"]:sha256(output/row["task_id"]/"manifest.json") for row in records},
        training_executed=False,optimizer_steps=0))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",default=str(DEFAULT_OUTPUT))
    p.add_argument("--l2-directory",default=str(DEFAULT_L2))
    a=p.parse_args();run(a.output,a.l2_directory)


if __name__=="__main__":
    main()
