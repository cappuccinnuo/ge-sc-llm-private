"""Codex 2026-10-09: audit only; inputs are never rewritten.
Endpoint replay establishes compatibility, not the unpublished original algorithm.
"""
import ast, csv, json, sys
from pathlib import Path
from collections import Counter, defaultdict
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(REPO/"scripts/labeling_v2"), str(REPO/"scripts")]
from safe_graph import read_graph, sha256
from label_rules import align_graphs, parse_records, endpoints, recover_author_annotations, verified_annotations
from line_mapping import build_line_map, preprocessed_to_original

def read_json(p):
    return json.loads(p.read_text(encoding="utf8"))

def expanded(value):
    spans = ast.literal_eval(value) if isinstance(value, str) else value
    return {n for span in spans for n in range(min(span), max(span)+1)}

def stats(g):
    return dict(nodes=len(g), edges=g.number_of_edges(),
        files=len({d["source_file"] for _,d in g.nodes(data=True)}),
        positives=sum(bool(parse_records(d.get("node_info_vulnerabilities"))) for _,d in g.nodes(data=True)),
        node_types=dict(Counter(d["node_type"] for _,d in g.nodes(data=True))),
        edge_types=dict(Counter(d["edge_type"] for _,_,d in g.edges(data=True))),
        nodes_with_token=sum("token" in d for _,d in g.nodes(data=True)))

def replay(g):
    ann = {f:{n for rec in recs for n in rec["lines"]}
           for f,recs in recover_author_annotations(g).items()}
    counts, mismatch = Counter(), Counter()
    for _,d in g.nodes(data=True):
        truth = bool(parse_records(d.get("node_info_vulnerabilities")))
        for name,covered in [("endpoints",set(endpoints(d["node_source_code_lines"]))),
                             ("expanded_span",expanded(d["node_source_code_lines"]))]:
            pred = bool(covered & ann[d["source_file"]])
            counts[name] += pred
            mismatch[name] += pred != truth
    return ann, dict(stats=stats(g), positive_counts=dict(counts), mismatches=dict(mismatch))

def edge_groups(g, mapping=None):
    out = defaultdict(Counter)
    for s,t,d in g.edges(data=True):
        pair = (mapping[s],mapping[t]) if mapping else (s,t)
        out[pair][d["edge_type"]] += 1
    return out

def main():
    base = REPO/"scripts/access_control_test/artifacts/dataset_a_source_range_v1"
    official = REPO/"data/upstream_mando_llm/graph_detection"
    paths = dict(author=official/"access_control_tree_sitter_cfg_cg_compressed_graphs.gpickle",
        author_contract_labels=official/"access_control_graph_labels.json",
        local=base/"hcg_labeled.gpickle",
        token=base/"tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle",
        line=base/"linelevel_tokenizer_ids.gpickle", annotations=base/"annotations.json",
        local_contract_labels=base/"graph_labels.json", manifest=base/"manifest.json",
        reentrancy_author=official/"reentrancy_tree_sitter_cfg_cg_compressed_graphs.gpickle")
    hashes = {k:sha256(p) for k,p in paths.items()}
    manifest = read_json(paths["manifest"])
    source_dir = Path(manifest["source_dir"])
    inputs = [Path(p) for p in manifest["input_hashes"]]
    smartbugs = next(p for p in inputs if p.name=="vulnerabilities.json")
    solidifi = next(p.parent for p in inputs if p.name.startswith("BugLog_"))
    local,author = read_graph(paths["local"]),read_graph(paths["author"])
    mapping = align_graphs(local,author)
    files = sorted({d["source_file"] for _,d in local.nodes(data=True)})
    annotations,provenance,source_hashes = verified_annotations(
        source_dir,files,smartbugs,solidifi,"access_control",read_json)
    assert annotations == read_json(paths["annotations"])
    assert all(sha256(Path(p))==h for p,h in manifest["input_hashes"].items())
    author_ann,author_replay = replay(author)
    _,reentrancy_replay = replay(read_graph(paths["reentrancy_author"]))
    maps = {f:build_line_map((source_dir/f).read_text(encoding="utf8")) for f in files}
    orig_ann = {f:{n for rec in recs for n in rec["lines"]} for f,recs in annotations.items()}
    local_ann = {f:{i+1 for i,orig in enumerate(maps[f]) if set(orig)&orig_ann[f]} for f in files}
    ann_diff = []
    for f in files:
        if local_ann[f] == author_ann[f]:continue
        raw_len = len((source_dir/f).read_text(encoding="utf8").splitlines())
        ann_diff.append(dict(file=f,local_count=len(local_ann[f]),author_recovered_count=len(author_ann[f]),
            local_only=sorted(local_ann[f]-author_ann[f]),author_only=sorted(author_ann[f]-local_ann[f]),
            preprocessed_source_lines=len(maps[f]),original_source_lines=raw_len,
            author_outside_preprocessed=sorted(n for n in author_ann[f] if n>len(maps[f])),
            author_outside_original=sorted(n for n in author_ann[f] if n>raw_len)))
    differences,coordinates,node_map = [],[],[]
    policies,mismatches,directions,types = Counter(),Counter(),Counter(),Counter()
    per_file = {f:Counter() for f in files}
    for n,d in local.nodes(data=True):
        ref_id = mapping[n]; ref=author.nodes[ref_id]; f=d["source_file"]
        al=bool(parse_records(ref.get("node_info_vulnerabilities")))
        ll=bool(parse_records(d.get("node_info_vulnerabilities")))
        orig=preprocessed_to_original(d["node_source_code_lines"],maps[f])
        assert orig==d["node_source_code_lines_original"]
        assert ll==bool(set(orig)&orig_ann[f])
        end=set(endpoints(ref["node_source_code_lines"]))
        full=expanded(ref["node_source_code_lines"])
        span=set(d["node_source_code_lines"])
        if full!=span:
            coordinates.append(dict(local_id=n,author_id=ref_id,file=f,node_type=d["node_type"],
                local=sorted(span),author_expanded=sorted(full)))
        for rule,covered in [("author_endpoints",end),("author_expanded",full),("local_span",span)]:
            for ann_name,ann in [("author_records",author_ann[f]),("local_public",local_ann[f])]:
                key=rule+"+"+ann_name; pred=bool(covered&ann)
                policies[key]+=pred; mismatches[key]+=pred!=al
        node_map.append(dict(local_id=n,author_id=ref_id,file=f,node_type=d["node_type"]))
        for key,val in [("nodes",1),("author_positive",al),("local_positive",ll),
                        ("different_labels",al!=ll)]:per_file[f][key]+=val
        if al!=ll:
            directions[str(int(al))+"->"+str(int(ll))]+=1;types[d["node_type"]]+=1
            differences.append(dict(local_id=n,author_id=ref_id,file=f,node_type=d["node_type"],
                code=d["code"],original_lines=orig,local_preprocessed_lines=sorted(span),
                author_preprocessed_lines=ref["node_source_code_lines"],
                author_label=int(al),local_label=int(ll),
                local_records=parse_records(d.get("node_info_vulnerabilities")),
                author_records=parse_records(ref.get("node_info_vulnerabilities"))))
    ae,le=edge_groups(author),edge_groups(local,mapping)
    same=changed=0;transitions=Counter();ambiguous=[]
    for pair,at in ae.items():
        lt=le[pair]; common=at&lt
        same+=sum(common.values()); ar,lr=at-common,lt-common;changed+=sum(ar.values())
        if ar and len(ar)==len(lr)==1:
            transitions[(next(iter(ar)),next(iter(lr)))]+=sum(ar.values())
        elif ar:ambiguous.append(dict(pair=pair,author=dict(ar),local=dict(lr)))
    acl,lcl=read_json(paths["author_contract_labels"]),read_json(paths["local_contract_labels"])
    ac={x["contract_name"]:int(x["targets"]) for x in acl}
    lc={x["contract_name"]:int(x["targets"]) for x in lcl}
    assert ac==lc and set(ac)==set(files)
    token=read_graph(paths["token"]); tm=align_graphs(local,token)
    assert all(n==t for n,t in tm.items()) and edge_groups(local)==edge_groups(token)
    assert all(local.nodes[n]=={k:v for k,v in token.nodes[n].items() if k!="token"} for n in local)
    line=read_graph(paths["line"])
    chosen=[n for n,d in local.nodes(data=True) if ac[d["source_file"]]==1]
    lm=align_graphs(line,local.subgraph(chosen))
    assert all(parse_records(line.nodes[n].get("node_info_vulnerabilities"))==
        parse_records(local.nodes[t].get("node_info_vulnerabilities")) for n,t in lm.items())
    report=dict(audit_date="2026-10-09",reviewer="Codex",
        inputs={k:str(p) for k,p in paths.items()},input_sha256=hashes,source_sha256=source_hashes,
        author=stats(author),local=stats(local),local_training_token_graph=stats(token),
        local_training_line_graph=stats(line),
        author_buggy_induced_graph=stats(author.subgraph([mapping[n] for n in chosen])),
        exact_node_alignment=len(mapping),same_untyped_edge_endpoints_and_multiplicities=True,
        same_contract_labels=True,same_contract_label_order=acl==lcl,
        edge_type_comparison=dict(same=same,changed=changed,ambiguous_parallel_edges=ambiguous,
            transitions=[dict(author=a,local=b,count=c) for (a,b),c in sorted(transitions.items())]),
        labels=dict(different_nodes=len(differences),directions=dict(directions),by_type=dict(types),
            single_line_differences=sum(len(x["local_preprocessed_lines"])==1 for x in differences),
            counterfactual_positive_counts=dict(policies),counterfactual_mismatches_to_author=dict(mismatches)),
        annotation_comparison=dict(local_annotated_files=sum(bool(v) for v in annotations.values()),
            equal_recoverable_annotation_files=sum(bool(annotations[f]) and local_ann[f]==author_ann[f] for f in files),
            different_files=ann_diff),
        author_replay=dict(access_control=author_replay,reentrancy=reentrancy_replay),
        coordinate_span_differences=coordinates,
        per_file=[dict(file=f,**dict(v)) for f,v in sorted(per_file.items(),key=lambda x:(-x[1]["different_labels"],x[0]))],
        checks=dict(local_public_annotations_rebuilt_and_sources_verified=True,
            local_labels_and_line_mapping_recomputed=True,inputs_match_local_build_manifest=True,
            local_token_training_graph_preserves_raw_graph=True,line_graph_is_buggy_induced_subgraph=True),
        limitations=[
            "Recovered author records exclude annotations that never hit a saved positive node.",
            "Endpoint replay proves artifact compatibility, not original algorithm or correctness.",
            "Equal edge endpoints do not prove semantic correctness of call resolution.",
            "Author graph has no token vectors; actual author training features cannot be compared.",
            "No training or F1 causal attribution is performed in this audit."])
    assert all(sha256(p)==hashes[k] for k,p in paths.items())
    report["checks"]["all_audit_inputs_unchanged"]=True
    for filename,value in [("audit.json",report),("label_differences.json",differences)]:
        with (HERE/filename).open("x",encoding="utf8") as f:
            json.dump(value,f,ensure_ascii=False,indent=2);f.write("\n")
    for filename,rows in [("node_mapping.csv",node_map),("per_file.csv",report["per_file"])]:
        with (HERE/filename).open("x",newline="",encoding="utf8") as f:
            fields=list(dict.fromkeys(k for row in rows for k in row))
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:report[k] for k in ["edge_type_comparison","labels","checks"]},indent=2))
    print("Reports written to "+str(HERE))

if __name__=="__main__":
    main()

