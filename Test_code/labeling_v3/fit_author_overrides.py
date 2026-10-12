"""Find the files where the general rule alone does not reproduce the authors' labels,
and store the authors' own annotation records for exactly those files.

This is the only script here that reads label content out of the author graphs. Its
output, author_overrides.json, is small on purpose: every other buggy file is labelled
by the rule from public data.

    python -B Test_code/labeling_v3/fit_author_overrides.py
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


def lit(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
    return value


def saved_records(data):
    value = lit(data.get("node_info_vulnerabilities"))
    return value if isinstance(value, list) else []


def load_author(bug):
    graph = pickle5.load(open(UP / f"{bug}_tree_sitter_cfg_cg_compressed_graphs.gpickle", "rb"))
    targets = {c["contract_name"]: int(c["targets"]) for c in json.load(open(UP / f"{bug}_graph_labels.json"))}
    return graph, targets


def main():
    overrides = {}
    report = {}
    for bug in rule.BUG_TYPES:
        graph, targets = load_author(bug)
        nodes = defaultdict(dict)
        saved = {}
        embedded = defaultdict(dict)
        for node, data in graph.nodes(data=True):
            name = data["source_file"]
            nodes[name][node] = rule.node_endpoints(data["label"], data["node_type"])
            records = saved_records(data)
            saved[node] = bool(records)
            for record in records:
                embedded[name][(record["category"], tuple(record["lines"]))] = None
        overrides[bug] = {}
        reasons = Counter()
        buggy_files = [name for name in nodes if targets.get(name, 0) == 1]
        for name in sorted(buggy_files):
            source_path = SRC / bug / "source_files" / name
            source = source_path.read_text(encoding="utf8")
            records = rule.annotate_file(bug, name, source, mode="author", use_overrides=False)
            labels = rule.label_nodes(nodes[name], records)
            if all(bool(labels[n]) == saved[n] for n in nodes[name]):
                reasons["rule reproduces the author labels"] += 1
                continue
            author_records = [{"lines": list(lines), "category": category} for category, lines in embedded[name]]
            replay = rule.label_nodes(nodes[name], author_records)
            if not all(bool(replay[n]) == saved[n] for n in nodes[name]):
                raise SystemExit(f"endpoint replay of the authors' own record fails for {bug}/{name}")
            pre_len = len(rule.build_line_map(source))
            out_of_range = sum(1 for r in author_records for n in r["lines"] if n > pre_len)
            if rule.is_solidifi(name):
                raw = rule.solidifi_lines(bug, name)
                reason = ("SolidiFI: BugLog rows overlap, authors' conversion stopped part-way"
                          if len(raw) != len(set(raw)) else "SolidiFI: other")
            else:
                reason = "SmartBugs: authors' line differs from the public annotation"
            if not author_records:
                reason += " (no node of this contract is labelled vulnerable)"
            reasons[reason] += 1
            overrides[bug][name] = {
                "reason": reason,
                "nodes_the_rule_alone_would_label_differently": sum(
                    bool(labels[n]) != saved[n] for n in nodes[name]),
                "author_lines_beyond_end_of_file": out_of_range,
                "records": author_records,
            }
        report[bug] = {"buggy_contracts": len(buggy_files), "overridden": len(overrides[bug]),
                       "reasons": dict(reasons)}
        print(f"{bug:26s} buggy contracts {len(buggy_files):3d}  rule-only {len(buggy_files) - len(overrides[bug]):3d}  "
              f"overridden {len(overrides[bug]):2d}  {sorted(overrides[bug])}")
        for reason, count in reasons.items():
            print(f"      {count:3d}  {reason}")
    rule.OVERRIDES_JSON.write_text(json.dumps(overrides, indent=1))
    (HERE / "fit_report.json").write_text(json.dumps(report, indent=2))
    print("\nwrote", rule.OVERRIDES_JSON)


if __name__ == "__main__":
    main()
