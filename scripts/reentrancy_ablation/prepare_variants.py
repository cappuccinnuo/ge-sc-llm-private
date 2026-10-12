"""Build A/B/C/D variants while asserting exactly what changed."""
import argparse, copy
import numpy as np
import networkx as nx
from common import *
from freeze_folds import freeze

def prepare(output):
    output=confined(output)
    if output.exists():
        raise FileExistsError("Refuse overwriting prepared data: "+str(output))
    output.mkdir(parents=True)
    original=snapshot_originals()
    paths={
      "author_raw":REPO/"data/upstream_mando_llm/graph_detection/reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle",
      "author_tokenized":REPO/"experiments/ge-sc-data/source_code/reentrancy/upstream_contractlevel_tok.gpickle",
      "local_source_range":REPO/"scripts/labeling_v2/artifacts/labels_v1/source_range/contractlevel.gpickle",
      "graph_labels":REPO/"data/upstream_mando_llm/graph_detection/reentrancy_graph_labels.json"}
    raw=read_graph(paths["author_raw"])
    author=read_graph(paths["author_tokenized"])
    local=read_graph(paths["local_source_range"])
    raw_mapping=align_graphs(raw,author)
    if any(n!=m for n,m in raw_mapping.items()):
        raise ValueError("Tokenized reference changed original author node IDs")
    if Counter((s,t,d["edge_type"]) for s,t,d in raw.edges(data=True)) != Counter((s,t,d["edge_type"]) for s,t,d in author.edges(data=True)):
        raise ValueError("Tokenized author edges differ")
    for n in raw:
        if parse_records(raw.nodes[n].get("node_info_vulnerabilities"))!=parse_records(author.nodes[n].get("node_info_vulnerabilities")):
            raise ValueError("Tokenized author labels differ")
    mapping=align_graphs(local,author)
    inverse={a:l for l,a in mapping.items()}
    # Identical insertion order in all variants. Model labels and token rows follow this order.
    if list(author.nodes())!=list(range(len(author))):
        raise ValueError("Unexpected author node order")
    labels=read_json(paths["graph_labels"])
    expected={e["contract_name"] for e in labels}
    buggy={e["contract_name"] for e in labels if int(e["targets"])}
    if len(labels)!=142 or len(expected)!=142 or len(buggy)!=71:
        raise ValueError("Expected Dataset A reentrancy 142/71")
    if expected!={d["source_file"] for _,d in author.nodes(data=True)}:
        raise ValueError("Graph and contract label populations differ")
    variants={"A_author":author}
    b=copy.deepcopy(author)
    for n,d in b.nodes(data=True):
        d["node_info_vulnerabilities"]=copy.deepcopy(parse_records(local.nodes[inverse[n]].get("node_info_vulnerabilities")) or None)
    variants["B_local_labels"]=b
    c=copy.deepcopy(author); c.remove_edges_from(list(c.edges(keys=True)))
    for s,t,d in local.edges(data=True):
        c.add_edge(mapping[s],mapping[t],edge_type=d["edge_type"])
    variants["C_local_relations"]=c
    d=copy.deepcopy(author)
    changed_features=0; changed_code=0
    for n,attrs in d.nodes(data=True):
        src=local.nodes[inverse[n]]
        changed_features+=int(not np.array_equal(attrs["token"],src["token"]))
        changed_code+=int(attrs.get("code")!=src.get("code"))
        attrs["token"]=np.asarray(src["token"],dtype=np.float32).copy()
    variants["D_local_features"]=d
    components={name:graph_digests(g) for name,g in variants.items()}
    base=components["A_author"]
    allowed={"B_local_labels":{"labels"},"C_local_relations":{"typed_edges","edge_types"},
             "D_local_features":{"features"}}
    for name,digests in components.items():
        if name=="A_author": continue
        for key in ["nodes","edges","files","identities","endpoints","typed_edges","labels","features","edge_types"]:
            if key not in allowed[name] and digests[key]!=base[key]:
                raise ValueError("Unintended difference: "+name+"/"+key)
    if base["positive_nodes"]!=6570 or components["B_local_labels"]["positive_nodes"]!=6976:
        raise ValueError("Unexpected label counts")
    manifests={}
    for name,graph in variants.items():
        dest=output/name;dest.mkdir()
        contract=dest/"contract.gpickle";write_graph(graph,contract)
        selected=[n for n,attrs in graph.nodes(data=True) if attrs["source_file"] in buggy]
        line=graph.subgraph(selected).copy()
        for n in line:line.nodes[n]["original_node_id"]=n
        line=nx.convert_node_labels_to_integers(line,ordering="default")
        if list(line.nodes())!=list(range(len(line))):raise ValueError("Line IDs not contiguous")
        if len(line)!=12036 or line.number_of_edges()!=11710:raise ValueError("Wrong buggy induced graph")
        node=dest/"node.gpickle";write_graph(line,node)
        manifests[name]={"contract":str(contract),"node":str(node),
                         "contract_sha256":sha256(contract),"node_sha256":sha256(node),
                         "contract_stats":components[name],"node_stats":graph_digests(line)}
    write_json(output/"graph_labels.json",labels)
    folds={t:freeze(t,buggy if t=="node" else expected,output/(t+"_folds.json"))["split_hash"]
           for t in ["node","contract"]}
    result={"created_utc":utc(),"modified_by_ai":"Codex","source_hashes":{str(p):sha256(p) for p in paths.values()},
            "original_code_hashes":original,"node_mapping_hash":object_hash(sorted(mapping.items())),
            "fold_hashes":folds,"variants":manifests,"feature_nodes_changed":changed_features,
            "raw_code_nodes_changed":changed_code,"feature_variant_identical":changed_features==0,
            "tokenizer_note":"Reuse audited CodeT5p-770m raw IDs float32/512; author original graph has no token features.",
            "scope":"Only this folder is written. Variant B transfers local source_range labels onto author topology; D changes token only."}
    write_json(output/"manifest.json",result)
    print(json.dumps({"prepared":str(output),"feature_nodes_changed":changed_features,
                      "variant_counts":{n:(m["contract_stats"]["positive_nodes"],len(m["contract_stats"]["edge_types"])) for n,m in manifests.items()}}),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=HERE/"artifacts/v1/prepared")
    prepare(p.parse_args().output)
