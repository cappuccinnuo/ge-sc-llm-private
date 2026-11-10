"""Bounded EP0 CPU A/B/C probes. No optimizer, checkpoint load or graph export."""
import argparse
import copy
import gc
import resource
import threading
import time
from collections import Counter
import dgl
import os
from pathlib import Path

def current_rss():
    return int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")

import torch
from torch import nn
from .common import OUT, PLAN, read, write, checked, typed_data, ref

def rebuild(anchor,data,origins):
    model=copy.deepcopy(anchor)
    graph=dgl.heterograph(data,num_nodes_dict={t:anchor.symmetrical_global_graph.num_nodes(t)for t in anchor.ntypes_dict})
    for t in graph.ntypes:graph.nodes[t].data["inp"]=anchor.symmetrical_global_graph.nodes[t].data["inp"].detach().clone()
    model.etypes_dict={c:i for i,c in enumerate(graph.canonical_etypes)}
    for c,i in model.etypes_dict.items():graph.edges[c].data["id"]=torch.full((graph.num_edges(c),),i,dtype=torch.long)
    model.symmetrical_global_graph=graph
    model.symmetrical_global_graph_data=data
    layers=[]
    for old in anchor.gcs:
        new=type(old)(anchor.hidden_size,anchor.hidden_size,model.ntypes_dict,model.etypes_dict,anchor.num_heads,use_norm=True)
        src,dst=old.state_dict(),new.state_dict()
        with torch.no_grad():
            for name in dst:
                if name in ("relation_att","relation_msg","relation_pri"):
                    for c,i in model.etypes_dict.items():
                        if c in origins:dst[name][i].copy_(src[name][old.edge_dict[origins[c]]])
                else:dst[name].copy_(src[name])
        new.load_state_dict(dst,strict=True);layers.append(new)
    model.gcs=nn.ModuleList(layers)
    return model

def typed_support(model,parts):
    from scripts.DFG.experiments.paper_runtime import validate_registration
    from scripts.DFG.dfg_v2.benchmark_v2.support import V2_RELATIONS
    schema=validate_registration(model,deep=False)
    member={f:r for r,files in parts.items()for f in files}
    rows=[]
    for c in model.symmetrical_global_graph.canonical_etypes:
        ss,tt=model.symmetrical_global_graph.edges(etype=c)
        counter=Counter()
        for s,t in zip(ss.tolist(),tt.tolist()):
            sf=model.nx_graph.nodes[model.node_ids_dict[c[0]][s]]["source_file"]
            tf=model.nx_graph.nodes[model.node_ids_dict[c[2]][t]]["source_file"]
            assert sf==tf
            counter[member[sf]]+=1
        rows.append(dict(canonical=list(c),**{r+"_edges":counter[r]for r in parts}))
    return dict(schema=schema,profile=model.dfg_profile,relations=rows,
        v2_training_edges=sum(r["inner_train_edges"]for r in rows if r["canonical"][1]in V2_RELATIONS))

def random_scale_data(anchor,data,stats):
    """Scale estimate only. Endpoints sampled within each source file, not semantics."""
    g=torch.Generator().manual_seed(0)
    bytype={}
    for typ,ids in anchor.node_ids_dict.items():
        files={}
        for local,nid in enumerate(ids):files.setdefault(anchor.nx_graph.nodes[nid]["source_file"],[]).append(local)
        bytype[typ]=files
    data=dict(data)
    for relation,entry in stats["prospective_relations"].items():
        for row in entry["canonicals"]:
            a,r,b=row["canonical"];n=row["edges"]
            files=sorted(set(bytype[a])&set(bytype[b]));ss=[];tt=[]
            for i in range(n):
                f=files[int(torch.randint(len(files),(1,),generator=g))]
                aa,bb=bytype[a][f],bytype[b][f]
                ss.append(aa[int(torch.randint(len(aa),(1,),generator=g))])
                tt.append(bb[int(torch.randint(len(bb),(1,),generator=g))])
            pair=(torch.tensor(ss),torch.tensor(tt))
            data[(a,r,b)]=pair;data[(b,"REV_"+r,a)]=(pair[1],pair[0])
    return data

def rejection(call):
    try:call()
    except ValueError as exc:return dict(rejected=True,reason=str(exc))
    return dict(rejected=False)

def main():
    p=argparse.ArgumentParser();p.add_argument("--probe",choices=["A","B","C"],required=True);a=p.parse_args()
    from scripts.DFG.dfg_v2.model import make_model,validate_registration
    from scripts.DFG.dfg_v2.model_input import edge_data,materialize
    from scripts.DFG.dfg_v2.benchmark_v2.spelling_features import assemble
    from scripts.DFG.dfg_v2.benchmark_v2.audit_supervision import bind_rows
    from scripts.DFG.dfg_v2.benchmark_v2.support import gradient_audit
    from scripts.DFG.dfg_v2.benchmark_v2.protocol import validate_parts
    from scripts.DFG.experiments.common import seed_all,tensor_digest
    from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
    assert not torch.cuda.is_initialized()
    inputs=read(OUT/"inputs.json");task=inputs["tasks"]["reentrancy_node"]
    plan=read(PLAN);cfg=task["config"]
    prepared=read(checked(task["prepared"]["0/1"]))
    seed_all(prepared["seeds"]["constructor"])
    graph=assemble(checked(task["graph_refs"]["F3"]),task["feature_view"])
    before=graph_fingerprint(graph)
    anchor=make_model("node",graph,"G3R","cpu",hidden_size=cfg["hidden_size"],layers=cfg["layers"],
        heads=cfg["heads"],reducer=inputs["reducer"],layer_impl=inputs["layer_impl"])
    raw=edge_data(anchor.nx_graph)
    merge=materialize(raw,"G3R")
    typed,origins=typed_data(raw)
    output=dict(probe=a.probe,task_id="reentrancy_node",fold=0,device="cpu",optimizer_steps=0,
        fresh_anchor=True,trained_checkpoint_loaded=False,
        seed=prepared["seeds"]["constructor"],source_feature_view=task["feature_view"])
    if a.probe=="A":
        model=rebuild(anchor,merge,{c:c for c in merge})
        validate_registration(model)
        assert tensor_digest(anchor.state_dict())==tensor_digest(model.state_dict())
        anchor.eval();model.eval()
        with torch.no_grad():y=anchor();z=model()
        output.update(state_equal=True,forward_bitwise_equal=torch.equal(y,z),
            max_abs=float((y-z).abs().max()),anchor_state_digest=tensor_digest(anchor.state_dict()))
        assert output["forward_bitwise_equal"]
    elif a.probe=="B":
        model=rebuild(anchor,typed,origins)
        output["deep_registration_under_G3R"]=rejection(lambda:validate_registration(model))
        model.dfg_profile="G3R-T"
        output["deep_registration_under_new_profile"]=rejection(lambda:validate_registration(model))
        model.dfg_profile="G3R"
        groups=validate_parts(prepared["split"],task["sources"])
        support=typed_support(model,groups)
        table=bind_rows(model,"reentrancy_node",task["label_view"])
        ids=[];targets=[]
        for nid,attrs in model.nx_graph.nodes(data=True):
            if attrs["node_type"]=="env_source" or attrs["source_file"]not in groups["inner_train"]:continue
            row=table[(attrs["source_file"],model.original_graph_node_ids[nid])]
            if row["L-audit_include"]:ids.append(nid);targets.append(row["L-audit_target"])
        model.train();logits=model()
        loss=nn.functional.cross_entropy(logits[torch.tensor(ids)],torch.tensor(targets))
        loss.backward()
        assert bool(torch.isfinite(loss))
        audit=gradient_audit(model,support)
        output.update(forward_backward_finite=True,inner_train_nodes=len(ids),
            gradient_audit=audit,typed_relations=len(typed),
            parameter_count=sum(p.numel()for p in model.parameters()),
            copied_relation_rows_equal=all(torch.equal(l.state_dict()[name][l.edge_dict[c]],
                old.state_dict()[name][old.edge_dict[origin]])for old,l in zip(anchor.gcs,model.gcs)
                for c,origin in origins.items()for name in ("relation_att","relation_msg","relation_pri")),
            gradient_validation_note="Frozen shallow registration permits G3R identity; deep registration rejects topology. This is not production checkpoint acceptance.")
    else:
        stats=read(OUT/"reentrancy_node.json")
        data=random_scale_data(anchor,typed,stats)
        model=rebuild(anchor,data,origins)
        del anchor,typed,merge,raw;gc.collect()
        baseline=current_rss();samples=[baseline];done=threading.Event()
        def sample():
            while not done.wait(.02):samples.append(current_rss())
        thread=threading.Thread(target=sample,daemon=True);thread.start()
        model.train();start=time.monotonic()
        try:
            logits=model()
            assert bool(torch.isfinite(logits).all())
            samples.append(current_rss())
        finally:done.set();thread.join()
        output.update(forward_finite=True,seconds=time.monotonic()-start,
            rss_before_forward_bytes=baseline,peak_sampled_rss_bytes=max(samples),
            incremental_forward_rss_bytes=max(samples)-baseline,
            process_high_water_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            parameter_count=sum(p.numel()for p in model.parameters()),
            relations=len(data),edges=sum(len(v[0])for v in data.values()),
            scale_only=True,semantic_edges_built=False,autograd_enabled=True,
            limitation="Random same-file endpoints, current mappable guards only; no EdgeAware attribute activations, backward or optimizer state. CPU RSS is not GPU VRAM.")
    assert graph_fingerprint(graph)==before and not torch.cuda.is_initialized()
    output.update(input_graph_unchanged=True,cuda_initialized=False)
    write(OUT/("cpu_"+a.probe+".json"),output)
    print("CPU probe",a.probe,"complete",flush=True)

if __name__=="__main__":main()
