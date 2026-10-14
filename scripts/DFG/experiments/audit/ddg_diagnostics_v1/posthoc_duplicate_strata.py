"""Posthoc train-index duplicate strata; no graph or frozen D1 changes."""
import csv
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("d1_static", str(ROOT / "static_analysis.py"))
d1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d1)


def code_state(value):
    if value is None:
        return "none_or_missing"
    if value == "":
        return "empty"
    if value in ('""', "''"):
        return "serialized_empty_literal"
    if isinstance(value, str) and not value.strip():
        return "whitespace_only"
    return "nonempty"


def summarize(counts):
    r = dict(counts)
    for numerator, denominator, name in [
        ("matched", "nodes", "duplicate_pct"),
        ("label_conflict", "nodes", "label_conflict_pct"),
        ("positive_matched", "positive_nodes", "positive_duplicate_pct"),
        ("negative_matched", "negative_nodes", "negative_duplicate_pct"),
    ]:
        r[name] = 100.0 * counts[numerator] / counts[denominator] if counts[denominator] else None
    return r


def main():
    run = d1.REPO / "scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c"
    output = ROOT / "static"
    for name in ("duplicate_strata.json", "duplicate_strata.csv"):
        if (output / name).exists():
            raise FileExistsError(str(output / name))
    frozen_paths = [output / "summary.json", output / "input_invariants.json",
                    output / "coverage.csv", output / "edge_increment.csv"]
    before = {str(p): d1.sha(p) for p in frozen_paths}
    inputs = {}
    groups = d1.resolved_tasks(run, inputs)
    all_rows, all_tasks = [], {}
    for key, group in groups.items():
        manifest_path = group["prepared"] / "manifest.json"
        manifest = d1.read(manifest_path)
        info = manifest["graphs"]["E0"][group["task"]]
        graph_path = d1.checked(group["prepared"] / info["path"], info["sha256"], inputs)
        graph = d1.read_graph(graph_path)
        # The CSV format lacks an ID type field. Refuse ambiguous stringification;
        # retain actual graph IDs when validating source identities.
        by_csv = {str(n): n for n in graph}
        if len(by_csv) != len(graph):
            raise ValueError("Ambiguous original-node ID stringification")
        path = output / (key + "_duplicates.csv")
        inputs[str(path)] = d1.sha(path)
        count_groups = defaultdict(Counter)
        seen = set()
        with path.open(newline="", encoding="utf8") as f:
            for row in csv.DictReader(f):
                if row["task_key"] != key:
                    raise ValueError("Task identity mismatch")
                identity = (row["basis"], row["fold"], row["node_id"])
                if identity in seen:
                    raise ValueError("Repeated diagnostic row")
                seen.add(identity)
                n = by_csv[row["node_id"]]
                data = graph.nodes[n]
                if row["file"] != data["source_file"]:
                    raise ValueError("Original node/file mismatch")
                target = int(row["target"])
                if target != d1.positive(data):
                    raise ValueError("Frozen label mismatch")
                typ = data["node_type"]
                state = code_state(data.get("code"))
                synthetic = typ in ("end_if", "end_loop")
                empty_like = state != "nonempty"
                dimensions = [
                    ("all", "ALL"),
                    ("node_type", typ),
                    ("code_state", state),
                    ("synthetic_control_marker", str(synthetic)),
                    ("nonempty_nonsynthetic", str(not synthetic and not empty_like)),
                    ("node_type_and_code_state", typ + "|" + state),
                ]
                for dimension, value in dimensions:
                    c = count_groups[(row["basis"], dimension, value)]
                    matched = int(row["matched"])
                    c["nodes"] += 1
                    c["matched"] += matched
                    c["label_conflict"] += int(row["train_label_conflict"])
                    c["opposite_label_train"] += int(row["has_opposite_label_train"])
                    c["positive_nodes"] += target
                    c["negative_nodes"] += 1 - target
                    c["positive_matched"] += target * matched
                    c["negative_matched"] += (1 - target) * matched
                    c["empty_like_nodes"] += int(empty_like)
                    c["synthetic_control_nodes"] += int(synthetic)
        task_rows = []
        for (basis, dimension, value), counts in sorted(count_groups.items()):
            item = dict(task_key=key, basis=basis, dimension=dimension, stratum=value,
                        **summarize(counts))
            task_rows.append(item)
            all_rows.append(item)
        all_tasks[key] = task_rows
    after = {str(p): d1.sha(p) for p in frozen_paths}
    if before != after:
        raise AssertionError("Existing D1 outputs changed")
    if any(d1.sha(p) != h for p, h in inputs.items()):
        raise AssertionError("Source artifacts changed")
    d1.write_csv(output / "duplicate_strata.csv", all_rows)
    d1.dump(output / "duplicate_strata.json", {
        "status": "passed", "tasks": all_tasks,
        "unit": "Original validation HCG node, pooled over fixed folds; each node once per basis.",
        "matching": "Reuse frozen train-only index queries; no new matching or normalization.",
        "code_state": "Raw stored code; quoted empty literal flagged separately, not decoded.",
        "synthetic_control_marker": "Exactly end_if or end_loop node type.",
        "conflict": "Train matching group contains both node labels; posthoc descriptive statistic.",
        "before_existing_d1": before, "after_existing_d1": after, "input_hashes": inputs,
    })
    for key, rows in all_tasks.items():
        chosen = [r for r in rows if r["basis"] == "stored_code_exact" and (
            r["dimension"] == "nonempty_nonsynthetic" and r["stratum"] == "True" or
            r["dimension"] == "node_type" and r["stratum"] in
            ("expression_statement", "new_variable", "function_definition", "end_if", "end_loop"))]
        print(json.dumps({"task": key, "strata": chosen}), flush=True)


if __name__ == "__main__":
    main()
