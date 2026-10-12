"""Generate graph_labels.json, the contract-level (Phase 1) label file.

Consumers and the contract they impose:

  sco_models/dataloader.py EthIdsDataset._load_graph
      reads [{"contract_name": ..., "targets": 0|1}, ...] and keeps the list order,
      so entry i of the JSON is graph i of the dataset.

  model_hgt.HGTVulGraphClassifier.forward(batched_g_name)
      looks each name up in self.node_ids_by_filename, which graph_utils builds from
      the nodes' 'source_file' attribute. A name that is not a source_file in the
      graph raises KeyError mid-training, so the two sets have to agree exactly.

Labels are derived from the graph itself rather than from a separate contract list:
a contract is buggy when at least one of its nodes carries node_info_vulnerabilities.
That is the same criterion build_labeled_graph.py reports, so the contract-level and
line-level views cannot drift apart.

Phase 1 uses the full corpus at Clean : Buggy = 1 : 1 (mando-llm.md section 16), so
this runs on the complete HCG, not on the buggy-only line-level subgraph.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/hcg_compressed_graphs.gpickle"
DEFAULT_OUT = REPO / "experiments/ge-sc-data/source_code/reentrancy/graph_labels.json"


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", default=str(DEFAULT_GRAPH),
                   help="Labelled contract-level HCG (all contracts, not buggy-only)")
    p.add_argument("--output", default=str(DEFAULT_OUT))
    p.add_argument("--source_dir", default=None,
                   help="Optional .sol directory; if given, cross-check coverage")
    return p


def main():
    args = build_parser().parse_args()
    g = nx.read_gpickle(args.graph)
    print(f"graph : {args.graph}")
    print(f"        {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")

    # contract -> does any node carry a vulnerability record
    buggy = {}
    node_count = Counter()
    for _, d in g.nodes(data=True):
        name = d["source_file"]
        node_count[name] += 1
        if d.get("node_info_vulnerabilities"):
            buggy[name] = True
        buggy.setdefault(name, False)

    names = sorted(buggy)
    entries = [{"contract_name": n, "targets": int(buggy[n])} for n in names]

    n_buggy = sum(e["targets"] for e in entries)
    n_clean = len(entries) - n_buggy
    print(f"contracts: {len(entries)}   buggy: {n_buggy}   clean: {n_clean}")
    if n_buggy and n_clean:
        print(f"clean:buggy = {n_clean / n_buggy:.3f} : 1"
              f"   (the paper balances Phase 1 at 1 : 1)")

    # The forward pass indexes node_ids_by_filename with every name in this file;
    # a name the graph does not know would fail at training time, not here.
    graph_files = set(node_count)
    label_files = {e["contract_name"] for e in entries}
    missing_in_graph = label_files - graph_files
    missing_in_labels = graph_files - label_files
    if missing_in_graph:
        raise SystemExit(f"{len(missing_in_graph)} labelled contracts absent from the "
                         f"graph, forward() would KeyError: {sorted(missing_in_graph)[:5]}")
    if missing_in_labels:
        raise SystemExit(f"{len(missing_in_labels)} graph contracts have no label: "
                         f"{sorted(missing_in_labels)[:5]}")
    print("every contract in the graph has a label and vice versa")

    if args.source_dir:
        sol = {p.name for p in Path(args.source_dir).glob("*.sol")}
        only_disk = sol - graph_files
        only_graph = graph_files - sol
        print(f"source dir: {len(sol)} .sol files")
        if only_disk:
            print(f"  WARNING {len(only_disk)} .sol never made it into the graph: "
                  f"{sorted(only_disk)[:5]}")
        if only_graph:
            print(f"  WARNING {len(only_graph)} graph contracts missing on disk: "
                  f"{sorted(only_graph)[:5]}")
        if not only_disk and not only_graph:
            print("  disk and graph agree")

    sizes = [node_count[n] for n in names]
    print(f"nodes per contract: min {min(sizes)}  median "
          f"{sorted(sizes)[len(sizes) // 2]}  max {max(sizes)}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entries, indent=2), encoding="utf8")
    print(f"wrote -> {out}")

    # read back through the real consumer so a format slip surfaces now
    import sys
    sys.path.insert(0, str(REPO))
    from sco_models.dataloader import EthIdsDataset
    ds = EthIdsDataset(str(out))
    print(f"EthIdsDataset loaded {len(ds)} graphs, "
          f"labels sum {int(ds.label.sum())}, first entry {ds[0][0]!r} -> {int(ds[0][1])}")


if __name__ == "__main__":
    main()
