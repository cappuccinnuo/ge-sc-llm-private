"""NS-P9 evidence-only graph and annotation review. Never modifies an input graph."""
import argparse
from collections import defaultdict
from pathlib import Path
import networkx as nx
import torch
from scripts.DFG.dfg_v2.model_input import materialize
from .summary import ART, DEFAULT, Sources, read, write, reference, csv_write

QUERIES = {
 "modifier_reentrancy.sol": [(8498,8500,"airDrop to supportsToken modifier"),(8501,8499,"modifier check to body write"),(8515,8498,"callback callsite to airDrop"),(8511,8498,"callback function to airDrop")],
 "reentrancy_bonus.sol":[(12,4,"callsite to callee"),(9,4,"caller function to callee"),(7,13,"callee external call to caller post-call write")],
 "etherbank.sol":[(15757,15759,"call condition to throw"),(15757,15760,"call condition to later balance clear")],
 "reentrancy_dao.sol":[(8315,8317,"external call to balance clear")],
 "spank_chain_payment.sol":[(12953,12891,"caller to stored token transfer target"),(12961,12891,"token callsite to stored transfer function"),(12958,12962,"ETH transfer to channel deletion"),(12961,12962,"token transfer to channel deletion")],
 "FibonacciBalance.sol":[(10583,10587,"fallback delegatecall to library setter"),(10581,10589,"withdraw delegatecall to library function"),(10588,10572,"library write to caller storage address"),(10581,10582,"delegatecall to payout")],
 "arbitrary_location_write_simple.sol":[(11472,11473,"bound check to decrement"),(11477,11465,"indexed write to owner storage declaration")],
 "mapping_write.sol":[(12959,12953,"array write to owner declaration"),(12959,12963,"array write to withdrawal owner guard")],
 "multiowned_vulnerable.sol":[(3174,3176,"unprotected entry to owner mapping write"),(3176,3172,"owner write to modifier check"),(3183,3171,"withdraw entry to modifier")],
 "proxy.sol":[(8853,8854,"public entry to delegatecall")],
 "rubixi.sol":[(11356,11357,"public initializer to creator write"),(11357,11359,"creator write to onlyowner check"),(11390,11358,"protected function to modifier")],
 "simple_suicide.sol":[(12756,12757,"public entry to selfdestruct")],
 "unprotected0.sol":[(10847,10848,"public entry to owner write"),(10847,10842,"unprotected function to unused modifier")],
 "wallet_02_refund_nosub.sol":[(11913,11907,"refund to deposit write through shared state"),(11913,11911,"refund to different function balance debit")],
 "wallet_03_wrong_constructor.sol":[(7893,7894,"public initializer to creator write"),(7894,7903,"creator write to migration guard")],
 "wallet_04_confused_sign.sol":[(9865,9866,"comparison to payout"),(9865,9867,"comparison to balance debit")],
}


def model_edges(evidence):
    """Use the frozen materializer on edge-index tensors only (no model or feature build)."""
    by_type=defaultdict(list);loc={};types={}
    for n in evidence["nodes"]:
        typ=n["node_type"];loc[n["id"]]=len(by_type[typ]);by_type[typ].append(n["id"]);types[n["id"]]=typ
    grouped=defaultdict(lambda:([],[]))
    for edge in evidence["edges"]:
        u,v=edge["source"],edge["target"]
        k=(types[u],edge["attributes"]["edge_type"],types[v])
        grouped[k][0].append(loc[u]);grouped[k][1].append(loc[v])
    data={k:tuple(torch.tensor(v,dtype=torch.int64)for v in pair)for k,pair in grouped.items()}
    output=[]
    for (src,rel,dst),(us,vs) in materialize(data,"G3R").items():
        for u,v in zip(us.tolist(),vs.tolist()):
            output.append(dict(source=by_type[src][u],target=by_type[dst][v],relation=rel))
    return output


def path_evidence(evidence,source,target):
    raw=nx.DiGraph();msg=nx.DiGraph()
    raw.add_nodes_from(n["id"]for n in evidence["nodes"]);msg.add_nodes_from(raw.nodes)
    for e in evidence["edges"]:raw.add_edge(e["source"],e["target"])
    modeled=model_edges(evidence)
    for e in modeled:msg.add_edge(e["source"],e["target"])
    if source not in raw or target not in raw:raise ValueError("Requested evidence endpoint absent")
    result=dict(source=source,target=target,
        raw_direct_edges=[e for e in evidence["edges"]if e["source"]==source and e["target"]==target],
        message_direct_relations=[e["relation"]for e in modeled if e["source"]==source and e["target"]==target])
    for name,g in (("raw_forward",raw),("G3R_message",msg)):
        path=nx.shortest_path(g,source,target) if nx.has_path(g,source,target)else None
        result[name+"_shortest_path"]=path
        result[name+"_hops"]=len(path)-1 if path else None
        if name=="G3R_message":
            result["message_path_relations"]=[
                sorted({e["relation"]for e in modeled if e["source"]==u and e["target"]==v})
                for u,v in zip(path or [],(path or [])[1:])]
    result["within_two_message_layers"]=result["G3R_message_hops"] is not None and result["G3R_message_hops"]<=2
    return result


def build(root=DEFAULT):
    root=Path(root);out=root/"edge_review";out.mkdir(exist_ok=False);sources=Sources()
    completion=read(sources.root(root/"cases_attempt2/complete.json"));sources.refs(completion["artifacts"])
    cases=read(root/"cases_attempt2/persistent_cases.json")
    plan=read(sources.root(ART/"batch_NC2_v1/plan.json"))
    prep=sources.json(plan["jobs"][0]["source_preparation"])
    label_ref=prep["bound_artifacts"]["node_diagnostic_views"]
    audit_ref=prep["bound_artifacts"]["node_label_audit"]
    audit=sources.json(audit_ref)
    if audit["node_views"]!=label_ref:raise ValueError("Label audit provenance differs")
    views=sources.json(label_ref)
    rows=[];seen={}
    for case in cases:
        ref=case["file_evidence"];file=case["file"];task=case["task_id"];nid=case["original_graph_node_id"]
        if ref["path"]not in seen:
            evidence=sources.json(ref)
            seen[ref["path"]]=[dict(path_evidence(evidence,u,v),question=q)for u,v,q in QUERIES[file]]
        old=[r for r in views[task]if r["file"]==file and r["original_graph_node_id"]==nid]
        if len(old)!=1:raise ValueError("Diagnostic label identity not unique")
        old=old[0];label=case["frozen_label"]
        if old["source_sha256"]!=case["source_sha256"]or old["C1"]!=label["L-audit_target"]or old["C2_include"]!=label["L-audit_include"]or old["orig"]!=label["orig"]:
            raise ValueError("Diagnostic label chain differs")
        rows.append(dict(task_id=task,file=file,node_id=nid,source_sha256=case["source_sha256"],
            node_diagnostic_ref=label_ref,node_audit_ref=audit_ref,
            original_diagnostic_record=old,inherit_original=old["C1"]==old["orig"],
            annotation_note="NonSolidiFI: C1 retains author target; C2 mask retained this node. This is provenance, not independent confirmation of a vulnerability.",
            queries=seen[ref["path"]],
            external_target_note="Edges are the stored graph and frozen input materialization, not resolved dynamic runtime calls. Topological reachability is not execution feasibility or a guard guarantee."))
    write(out/"paths_and_labels.json",rows)
    csv_write(out/"paths.csv",[dict(task_id=r["task_id"],file=r["file"],case_node=r["node_id"],**q)for r in rows for q in r["queries"]])
    write(out/"source_audit.json",list(sources.verified.values()))
    write(out/"complete.json",dict(passed=True,cases=len(rows),new_features=0,new_model_evals=0,
        artifacts=[reference(p)for p in sorted(out.iterdir())if p.is_file()]))
    return rows

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(DEFAULT));build(p.parse_args().root)
