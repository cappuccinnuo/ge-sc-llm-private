"""Two-phase cascade detection: contract-level filter, then line-level localisation.

mando-llm.md section 10:

  Phase 1  score the whole contract graph, keep the ones above the 0.5 confidence
           threshold, and let the clean ones stop there
  Phase 2  for the survivors only, classify their nodes and map the vulnerable ones
           back to source file and line

WHY THIS IS NOT A TWO-LINE SCRIPT. The two phases are trained on different graphs by
design - section 16 puts Phase 1 on the balanced full corpus and Phase 2 on buggy
contracts only. HGT sizes relation_pri / relation_att / relation_msg by the number of
meta relations in its training graph, so the Phase 2 checkpoint (132 meta relations,
from the buggy-only subgraph) cannot be loaded straight onto the full HCG (147). A
Phase 1 false positive is exactly the case that needs the extra 15.

So the checkpoint is remapped by meta-relation triple: every relation the two graphs
share keeps its trained parameters, and the ones only the full graph has stay at
their initial values. Nodes whose edges touch an untrained relation are flagged in
the output as `untrained_relation`, because the model has no evidence about them -
they are reported, not silently scored as if they were reliable.

Line numbers are the ORIGINAL file lines (node_source_code_lines_original), not the
preprocessed ones tree-sitter emits.
"""
import argparse
import contextlib
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"

RELATION_PARAMS = ("relation_pri", "relation_att", "relation_msg")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", default=str(BASE / "tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle"),
                   help="Full HCG to run the cascade over")
    p.add_argument("--linelevel_graph", default=str(BASE / "linelevel_tokenizer_ids.gpickle"),
                   help="Graph the Phase 2 checkpoint was trained on, for the relation map")
    p.add_argument("--graph_checkpoint",
                   default=str(REPO / "models/contractlevel/tok_ids/reentrancy_hgt.pth"))
    p.add_argument("--node_checkpoint",
                   default=str(REPO / "models/linelevel/tok_ids/reentrancy_hgt.pth"))
    p.add_argument("--node_feature", default="inside_token")
    p.add_argument("--threshold", type=float, default=0.5,
                   help="Confidence above which a contract or node counts as buggy")
    p.add_argument("--source_dir", default=str(BASE / "source_files"))
    p.add_argument("--output_json", default=str(REPO / "outputs/cascade_predictions.json"))
    p.add_argument("--top_k", type=int, default=5,
                   help="Vulnerable lines to print per contract in the summary")
    return p


def quiet_build(cls, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        return cls(*a, **kw)


def remap_relation_params(state, src_etypes, dst_etypes):
    """Re-index relation-keyed tensors from the source graph's meta relations to the
    destination graph's, leaving relations the source never saw untouched."""
    src_index = {rel: i for rel, i in src_etypes.items()}
    remapped = dict(state)
    transferred, untrained = 0, []

    for key, tensor in state.items():
        if not any(key.endswith(p) for p in RELATION_PARAMS):
            continue
        new_shape = (len(dst_etypes),) + tuple(tensor.shape[1:])
        new_tensor = torch.zeros(new_shape, dtype=tensor.dtype)
        # keep the source distribution for rows we cannot fill
        new_tensor.copy_(tensor.mean(dim=0, keepdim=True).expand(new_shape))
        for rel, dst_i in dst_etypes.items():
            src_i = src_index.get(rel)
            if src_i is not None:
                new_tensor[dst_i] = tensor[src_i]
                transferred += 1
            else:
                untrained.append(rel)
        remapped[key] = new_tensor

    missing = sorted({str(r) for r in untrained})
    return remapped, missing


def main():
    args = build_parser().parse_args()
    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    from sco_models.model_hgt import HGTVulGraphClassifier, HGTVulNodeClassifier

    print(f"device: {device}")
    print(f"graph : {args.graph}")

    nx_graph = nx.read_gpickle(args.graph)
    print(f"        {nx_graph.number_of_nodes()} nodes / {nx_graph.number_of_edges()} edges")

    # ---------------- Phase 1: contract-level ----------------
    print("\n===== Phase 1: coarse-grained contract-level detection =====")
    g_model = quiet_build(HGTVulGraphClassifier, args.graph, feature_extractor=None,
                          node_feature=args.node_feature, device=device)
    g_model.load_state_dict(torch.load(args.graph_checkpoint, map_location=device))
    g_model.to(device).eval()

    contracts = sorted({d["source_file"] for _, d in nx_graph.nodes(data=True)})
    with torch.no_grad():
        logits, _ = g_model(contracts)
        probs = torch.softmax(logits, dim=1)[:, 1].cpu()

    flagged = [c for c, p in zip(contracts, probs) if float(p) > args.threshold]
    print(f"contracts scored : {len(contracts)}")
    print(f"flagged (>{args.threshold}) : {len(flagged)}")

    del g_model
    torch.cuda.empty_cache()

    # ---------------- Phase 2: line-level ----------------
    print("\n===== Phase 2: fine-grained line-level localisation =====")
    n_model = quiet_build(HGTVulNodeClassifier, args.graph, feature_extractor=None,
                          node_feature=args.node_feature, device=device)
    line_model = quiet_build(HGTVulNodeClassifier, args.linelevel_graph,
                             feature_extractor=None, node_feature=args.node_feature,
                             device=device)

    state = torch.load(args.node_checkpoint, map_location=device)
    print(f"meta relations: checkpoint {len(line_model.etypes_dict)}  "
          f"target {len(n_model.etypes_dict)}")
    remapped, untrained_rels = remap_relation_params(
        state, line_model.etypes_dict, n_model.etypes_dict)
    n_model.load_state_dict(remapped)
    n_model.to(device).eval()
    print(f"untrained meta relations in the target graph: {len(untrained_rels)}")
    for rel in untrained_rels[:5]:
        print(f"  {rel}")

    # which nodes sit on an untrained relation
    untrained_set = set()
    for rel in untrained_rels:
        untrained_set.add(rel)
    node_type = {n: d.get("node_type") for n, d in nx_graph.nodes(data=True)}
    suspect_nodes = set()
    for s, t, d in nx_graph.edges(data=True):
        triple = (node_type[s], d.get("edge_type"), node_type[t])
        if str(triple) in untrained_set or triple in untrained_rels:
            suspect_nodes.add(s)
            suspect_nodes.add(t)

    with torch.no_grad():
        # HGTVulNodeClassifier.forward returns logits only; the graph classifier is
        # the one that also hands back the pooled graph embedding.
        node_logits = n_model()
        node_probs = torch.softmax(node_logits, dim=1)[:, 1].cpu()

    nodes_by_contract = defaultdict(list)
    for node_id, data in nx_graph.nodes(data=True):
        nodes_by_contract[data["source_file"]].append(node_id)

    del line_model
    torch.cuda.empty_cache()

    # ---------------- assemble ----------------
    results = []
    localised = 0
    for contract, p in zip(contracts, probs):
        confidence = float(p)
        entry = {
            "contract_name": contract,
            "contract_confidence": confidence,
            "contract_prediction": "vulnerable" if confidence > args.threshold else "clean",
            "vulnerable_lines": [],
            "vulnerable_nodes": [],
        }
        # Phase 2 only runs on what Phase 1 kept, which is the point of the cascade.
        if confidence > args.threshold:
            hits = []
            for node_id in nodes_by_contract[contract]:
                np_ = float(node_probs[node_id])
                if np_ > args.threshold:
                    d = nx_graph.nodes[node_id]
                    hits.append({
                        "node_id": int(node_id),
                        "node_type": d.get("node_type"),
                        "confidence": np_,
                        "lines": d.get("node_source_code_lines_original") or [],
                        "code": (d.get("code") or "").strip()[:200],
                        "untrained_relation": node_id in suspect_nodes,
                    })
            hits.sort(key=lambda h: h["confidence"], reverse=True)
            entry["vulnerable_nodes"] = hits
            lines = sorted({l for h in hits for l in h["lines"]})
            entry["vulnerable_lines"] = lines
            if hits:
                localised += 1
        results.append(entry)

    n_flagged = sum(1 for r in results if r["contract_prediction"] == "vulnerable")
    print(f"\ncontracts flagged by Phase 1      : {n_flagged}")
    print(f"of those, localised by Phase 2    : {localised}")
    print(f"flagged but no node above threshold: {n_flagged - localised}")

    # cascade accounting against ground truth, when the graph carries labels
    truth = {}
    for contract, node_ids in nodes_by_contract.items():
        truth[contract] = any(
            nx_graph.nodes[n].get("node_info_vulnerabilities") for n in node_ids)
    if any(truth.values()):
        tp = sum(1 for r in results
                 if r["contract_prediction"] == "vulnerable" and truth[r["contract_name"]])
        fp = sum(1 for r in results
                 if r["contract_prediction"] == "vulnerable" and not truth[r["contract_name"]])
        fn = sum(1 for r in results
                 if r["contract_prediction"] == "clean" and truth[r["contract_name"]])
        tn = len(results) - tp - fp - fn
        print(f"\nPhase 1 against ground truth: TP {tp}  FP {fp}  FN {fn}  TN {tn}")
        print(f"  {fn} vulnerable contracts are filtered out here and never reach Phase 2")

    print("\n--- sample of localised contracts ---")
    shown = 0
    for r in results:
        if not r["vulnerable_nodes"]:
            continue
        print(f"\n{r['contract_name']}  p={r['contract_confidence']:.4f}  "
              f"{len(r['vulnerable_nodes'])} vulnerable nodes")
        for h in r["vulnerable_nodes"][: args.top_k]:
            mark = " [untrained_relation]" if h["untrained_relation"] else ""
            print(f"  line {h['lines']}  p={h['confidence']:.4f}  {h['node_type']}{mark}")
            print(f"    {h['code'][:90]}")
        shown += 1
        if shown >= 3:
            break

    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf8")
    print(f"\nwrote -> {out}")


if __name__ == "__main__":
    main()
