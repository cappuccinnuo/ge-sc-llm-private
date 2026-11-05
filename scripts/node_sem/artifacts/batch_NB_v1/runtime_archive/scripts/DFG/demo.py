"""Minimal real-tokenizer end-to-end check, not a vulnerability benchmark."""
import argparse
import json
import os
from pathlib import Path

def run(output):
    from scripts.DFG.cli import output_directory
    from scripts.DFG.frontend import library_path
    out=output_directory(output)
    os.environ["TREE_SITTER_LIB_DIR"]=str(library_path().parent)
    # These variables only disable network fetches, not existing tokenizer logic.
    os.environ["TRANSFORMERS_OFFLINE"]="1"
    import networkx as nx
    import numpy as np
    import torch
    from transformers import AutoTokenizer
    from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
    from scripts.encode_tokenizer_features import encode_ids
    from scripts.labeling_v2.safe_graph import write_graph,read_graph
    from scripts.DFG.configuration import prepare_graph
    from scripts.DFG.models import DDGConfig
    from scripts.DFG.graph_audit import assert_augmented
    from scripts.DFG.model_validation import capture_model_input,assert_model_input
    from sco_models.model_hgt import HGTVulNodeClassifier,HGTVulGraphClassifier

    torch.set_num_threads(1)
    source_path=Path(__file__).resolve().parent/"tests/fixtures/minimal.sol"
    source=source_path.read_bytes().decode("utf8")
    filename="minimal.sol"
    graph=generate_cfg_from_source(source,filename)
    tokenizer_name="Salesforce/codet5p-770m"
    tokenizer=AutoTokenizer.from_pretrained(tokenizer_name,local_files_only=True)
    pad=tokenizer.pad_token_id
    if pad is None:pad=tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
    for _,data in graph.nodes(data=True):
        ids=tokenizer(data.get("code") or "",add_special_tokens=True).input_ids
        data["token"]=encode_ids(ids,512,pad)
        data["node_info_vulnerabilities"]=None
    # Use the same explicit numbering for both variants; enhancement never relabels.
    graph=nx.convert_node_labels_to_integers(graph)
    baseline,off=prepare_graph(graph,config=DDGConfig(False))
    enhanced,audit=prepare_graph(graph,{filename:source},DDGConfig(True))
    assert audit["invariants"]["ddg_edges"]==7,audit
    actual={(enhanced.nodes[s]["code"],enhanced.nodes[t]["code"])
            for s,t,d in enhanced.edges(data=True) if d["edge_type"]=="DATA_DEF_USE"}
    assert ("y = x + 1;","return y;") in actual
    assert ("y = x + 2;","return y;") in actual
    assert ("uint y = x;","return y;") not in actual
    out.mkdir(parents=True,exist_ok=False)
    base_path,ddg_path=out/"hcg.gpickle",out/"hcg_ddg.gpickle"
    write_graph(baseline,base_path);write_graph(enhanced,ddg_path)
    assert_augmented(read_graph(base_path),read_graph(ddg_path))
    results={}
    for task,cls in [("node",HGTVulNodeClassifier),("contract",HGTVulGraphClassifier)]:
        torch.manual_seed(7)
        kwargs=dict(compressed_global_graph_path=str(ddg_path),node_feature="inside_token",
                    hidden_size=16,num_layers=2,num_heads=4,use_norm=True,device="cpu")
        model=cls(**kwargs).to("cpu")
        external={"purpose":"all-clean synthetic interface test; no F1 benchmark"}
        manifest=capture_model_input(model,external)
        optimizer=torch.optim.Adam(model.parameters(),lr=0.0002)
        model.train()
        logits=model() if task=="node" else model([filename])[0]
        targets=torch.zeros(logits.shape[0],dtype=torch.long)
        loss=torch.nn.functional.cross_entropy(logits,targets)
        loss.backward()
        rows=[index for canonical,index in model.etypes_dict.items()
              if canonical[1]=="DATA_DEF_USE"]
        grad=sum(float(layer.relation_msg.grad[rows].abs().sum()) for layer in model.gcs)
        assert np.isfinite(grad) and grad>0
        old=model.gcs[0].relation_msg.detach().clone()
        optimizer.step()
        assert not torch.equal(old[rows],model.gcs[0].relation_msg.detach()[rows])
        model.eval()
        with torch.no_grad():
            expected=model() if task=="node" else model([filename])[0]
        state_path=out/(task+".pt")
        torch.save(model.state_dict(),str(state_path))
        (out/(task+"_input.json")).write_text(json.dumps(manifest,indent=2)+"\n")
        restored=cls(**kwargs).to("cpu")
        assert_model_input(restored,manifest,external)
        restored.load_state_dict(torch.load(str(state_path),map_location="cpu"))
        restored.eval()
        with torch.no_grad():
            actual_logits=restored() if task=="node" else restored([filename])[0]
        assert torch.equal(expected,actual_logits)
        results[task]={"logits_shape":list(logits.shape),"loss":float(loss.detach()),
                       "ddg_relation_gradient_l1":grad,"roundtrip_exact":True}
    result={"purpose":"interface validation only; no benchmark F1",
            "tokenizer":tokenizer_name,"feature_size":512,
            "graph":audit["invariants"],"models":results}
    (out/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
    (out/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2),flush=True)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    run(args.output)

if __name__=="__main__":
    main()
