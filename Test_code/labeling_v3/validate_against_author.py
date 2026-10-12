"""Validate author_rule.py against the authors' published fused graphs, all 7 bug types.

The author graph supplies the node list (with the generator's label string) and the
saved 0/1 label to compare with. Three label sets are recomputed and compared:
  clean              public annotations, rule only
  author (rule only) + the two general author behaviours, no per-file overrides
  author             + author_overrides.json

    python -B Test_code/labeling_v3/validate_against_author.py
"""
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pickle5

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import author_rule as rule  # noqa: E402

UP = rule.REPO / "data/upstream_mando_llm/graph_detection"
SRC = rule.REPO / "experiments/ge-sc-data/source_code"
VARIANTS = (("clean", dict(mode="clean")),
            ("author, rule only", dict(mode="author", use_overrides=False)),
            ("author", dict(mode="author")))


def lit(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value


def main():
    summary = {}
    for bug in rule.BUG_TYPES:
        graph = pickle5.load(open(UP / f"{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
        targets = {c["contract_name"]: int(c["targets"]) for c in json.load(open(UP / f"{bug}_graph_labels.json"))}
        nodes = defaultdict(dict)
        saved = {}
        coordinate_mismatch = 0
        for node, data in graph.nodes(data=True):
            ends = rule.node_endpoints(data["label"], data["node_type"])
            stored = sorted({x for span in lit(data["node_source_code_lines"]) for x in span})
            coordinate_mismatch += ends is None or sorted(set(ends)) != stored
            nodes[data["source_file"]][node] = ends
            saved[node] = isinstance(lit(data.get("node_info_vulnerabilities")), list)
        result = {"nodes": graph.number_of_nodes(), "author_positive": sum(saved.values()),
                  "endpoints_differing_from_published_coordinates": coordinate_mismatch}
        for key, kwargs in VARIANTS:
            positive = differing = 0
            files = Counter()
            for name, file_nodes in nodes.items():
                if targets.get(name, 0) == 1:
                    source = (SRC / bug / "source_files" / name).read_text(encoding="utf8")
                    labels = rule.label_nodes(file_nodes, rule.annotate_file(bug, name, source, **kwargs))
                else:
                    labels = dict.fromkeys(file_nodes)
                for node, hit in labels.items():
                    positive += bool(hit)
                    if bool(hit) != saved[node]:
                        differing += 1
                        files[name] += 1
            result[key] = {"positive": positive, "nodes_differing": differing, "files_differing": dict(files)}
        summary[bug] = result
        print("=" * 100)
        print(f"{bug}: nodes {result['nodes']}  author positives {result['author_positive']}  "
              f"endpoint/coordinate mismatches {coordinate_mismatch}")
        for key, _ in VARIANTS:
            r = result[key]
            print(f"   {key:18s} positives {r['positive']:6d}  nodes differing {r['nodes_differing']:4d}  "
                  f"in {len(r['files_differing'])} files {dict(Counter(r['files_differing']).most_common(5))}")
    (HERE / "validation_result.json").write_text(json.dumps(summary, indent=2))
    print("\nwrote", HERE / "validation_result.json")


if __name__ == "__main__":
    main()
