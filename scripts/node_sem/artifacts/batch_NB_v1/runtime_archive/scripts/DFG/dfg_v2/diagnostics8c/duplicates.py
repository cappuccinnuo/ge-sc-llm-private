"""Read-only Prompt 8C F duplicate audit; no graph/model loading or fitting.

Exact duplicates remove all Unicode whitespace from raw UTF-8 source. Near
duplicates additionally remove Solidity comments, preserving quoted strings.
SequenceMatcher uses its Python default autojunk=True explicitly, on characters,
with a deterministic source-identity order. Its ratio can depend on operand
order; we do not silently replace the requested metric by a symmetric variant.
A threshold component is a connectivity group, not an all-pairs similarity
claim. Raw source identity is category + cohort + filename + SHA256, never just
a basename. Graph and node tasks reference the same source identity once.
"""
import argparse
import collections
import difflib
import hashlib
import json
from pathlib import Path
import time

VERSION = "prompt8c-duplicates-v1"
NEAR_THRESHOLD = .98
ROLES = ("inner_train_files", "inner_val_files", "outer_test_files")
DEFAULT_PLAN = (
    Path(__file__).resolve().parents[4] / "scripts/DFG/experiments/artifacts/"
    "dfg_v2/prompt8_v1/batch1/plan.json"
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def _checked(ref):
    path = Path(ref["path"])
    data = path.read_bytes()
    if sha256_bytes(data) != ref["sha256"]:
        raise ValueError("Input SHA mismatch: " + str(path))
    return data


def _checked_json(ref):
    return json.loads(_checked(ref).decode("utf8"))


def without_whitespace(text):
    """Apply the requested textual normalization, including literal whitespace."""
    return "".join(text.split())


def without_comments(text):
    """Reuse the shared quote-aware, position-preserving diagnostics lexer."""
    from .labels import strip_comments
    return strip_comments(text)


def identity_key(record):
    return (record["category"], record["cohort"], record["file"], record["source_sha256"])


def source_id(record):
    return sha256_bytes(json.dumps(identity_key(record), ensure_ascii=False).encode("utf8"))


def load_inputs(plan_path):
    """Load only SHA-bound JSON/source inputs from the frozen formal plan."""
    plan_path = Path(plan_path).resolve()
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes.decode("utf8"))
    seal = _json(plan_path.with_name("plan.seal.json"))
    if seal["plan_sha256"] != sha256_bytes(plan_bytes):
        raise ValueError("Frozen plan seal differs")
    inputs = _checked_json(plan["input_manifest"])
    input_tasks = inputs.get("tasks")
    if isinstance(input_tasks, list):
        input_tasks = {row["task_id"]: row for row in input_tasks}
    if not isinstance(input_tasks, dict):
        raise ValueError("Input manifest requires task records")
    records, task_folds, bindings = {}, {}, []
    for task_id, task in sorted(plan["tasks"].items()):
        rec = task["record"]
        if input_tasks.get(task_id) != rec:
            raise ValueError("Task record differs from frozen input manifest: " + task_id)
        task_doc = _checked_json(rec["provenance"]["source_task_manifest"])
        cohort = task_doc["cohort"]
        if task_doc["task_id"] != rec["source_task_id"]:
            raise ValueError("Source task identity differs")
        folds = _checked_json(rec["folds"])
        files = rec["graph_files"]
        if (len(files) != len(set(files)) or set(files) != set(rec["sources"])
                or rec.get("missing_sources") or folds["files"] != files):
            raise ValueError("Incomplete or duplicated source/fold population")
        fold_list = folds["folds"]
        outer = {}
        for split in fold_list:
            sets = [set(split[r]) for r in ROLES]
            if (any(len(split[r]) != len(sets[i]) for i, r in enumerate(ROLES))
                    or set.union(*sets) != set(files)
                    or any(sets[i] & sets[j] for i in range(3) for j in range(i))):
                raise ValueError("Invalid frozen partition")
            for name in split["outer_test_files"]:
                if name in outer:
                    raise ValueError("Duplicate outer-test membership")
                outer[name] = split["fold"]
            for seed in plan["seeds"]:
                prepared = _checked_json(task["prepared"]["%s/%s" % (split["fold"], seed)])
                if (prepared["task_id"] != task_id or prepared["fold"] != split["fold"]
                        or prepared["seed"] != seed or prepared["split"] != split):
                    raise ValueError("Prepared task split differs")
        if set(outer) != set(files):
            raise ValueError("Missing outer-test membership")
        task_folds[task_id] = fold_list
        bindings.append({
            "task_id": task_id, "category": rec["category"], "cohort": cohort,
            "granularity": rec["task"], "files": len(files), "k_folds": folds["k_folds"],
            "folds": rec["folds"], "source_task_manifest": rec["provenance"]["source_task_manifest"],
            "source_metadata_manifest": rec["provenance"]["source_metadata_manifest"],
            "original_graph": rec["original_graph"],
        })
        for name in files:
            ref = rec["sources"][name]
            data = _checked(ref)
            record = {
                "category": rec["category"], "cohort": cohort, "file": name,
                "source_sha256": ref["sha256"], "path": ref["path"],
                "text": data.decode("utf8"), "task_outer_folds": {},
            }
            sid = source_id(record)
            if sid in records:
                if records[sid]["text"] != record["text"]:
                    raise ValueError("Conflicting source content")
            else:
                records[sid] = record
                record["source_id"] = sid
            records[sid]["task_outer_folds"][task_id] = outer[name]
    return list(records.values()), task_folds, {
        "plan": {"path": str(plan_path), "sha256": sha256_bytes(plan_bytes)},
        "input_manifest": plan["input_manifest"], "tasks": bindings,
    }


def _components(ids, pairs):
    parent = {sid: sid for sid in ids}
    def find(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid
    for pair in pairs:
        left, right = find(pair["left"]), find(pair["right"])
        if left != right:
            parent[max(left, right)] = min(left, right)
    groups = collections.defaultdict(list)
    for sid in ids:
        groups[find(sid)].append(sid)
    return sorted((sorted(group) for group in groups.values() if len(group) > 1),
                  key=lambda group: tuple(group))


def _cluster_rows(kind, records, pairs, task_folds):
    indexed = {row["source_id"]: row for row in records}
    groups = _components(sorted(indexed), pairs)
    rows = []
    for members in groups:
        task_locations, overlap = {}, []
        for task_id, folds in sorted(task_folds.items()):
            present = [indexed[sid] for sid in members if task_id in indexed[sid]["task_outer_folds"]]
            task_locations[task_id] = [
                {"source_id": row["source_id"], "file": row["file"],
                 "outer_fold": row["task_outer_folds"][task_id]} for row in present
            ]
            for split in folds:
                role_members = {role: [row["source_id"] for row in present if row["file"] in split[role]]
                                for role in ROLES}
                if role_members["outer_test_files"]:
                    overlap.append({
                        "task_id": task_id, "fold": split["fold"], "members": role_members,
                        "outer_has_inner_train_peer": bool(role_members["inner_train_files"]),
                        "outer_has_inner_val_peer": bool(role_members["inner_val_files"]),
                    })
        member_set = set(members)
        edges = [pair for pair in pairs if pair["left"] in member_set and pair["right"] in member_set]
        rows.append({
            "cluster_id": kind + "_" + sha256_bytes("|".join(members).encode("ascii"))[:16],
            "kind": kind, "members": members, "task_locations": task_locations,
            "threshold_pairs": edges, "outer_split_overlap": overlap,
            "is_all_pairs_clique": len(edges) == len(members) * (len(members) - 1) // 2,
        })
    return rows


def audit_records(records, task_folds):
    """Pure deterministic computation, suitable for small synthetic tests."""
    records = sorted(records, key=identity_key)
    ids = [source_id(row) for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError("Repeated source identity")
    norm_exact, norm_near, output = {}, {}, []
    for row, sid in zip(records, ids):
        if not row["text"].strip():
            raise ValueError("Empty source cannot establish duplicate identity")
        exact = without_whitespace(row["text"])
        near = without_whitespace(without_comments(row["text"]))
        if not near:
            raise ValueError("Comment-only source cannot establish near duplicate")
        norm_exact[sid], norm_near[sid] = exact, near
        clean = {key: value for key, value in row.items() if key != "text"}
        clean.update({
            "source_id": sid, "exact_normalized_sha256": sha256_bytes(exact.encode("utf8")),
            "near_normalized_sha256": sha256_bytes(near.encode("utf8")),
            "exact_characters": len(exact), "near_characters": len(near),
        })
        output.append(clean)
    exact_pairs, near_pairs = [], []
    candidate_count, ratio_count, bound_rejected = 0, 0, 0
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            candidate_count += 1
            exact = norm_exact[left] == norm_exact[right]
            if exact:
                exact_pairs.append({"left": left, "right": right})
            a, b = norm_near[left], norm_near[right]
            if a == b:
                ratio = 1.0
            else:
                matcher = difflib.SequenceMatcher(None, a, b, autojunk=True)
                if (matcher.real_quick_ratio() < NEAR_THRESHOLD
                        or matcher.quick_ratio() < NEAR_THRESHOLD):
                    bound_rejected += 1
                    continue
                ratio_count += 1
                ratio = matcher.ratio()
            if ratio >= NEAR_THRESHOLD:
                near_pairs.append({
                    "left": left, "right": right, "ratio": ratio,
                    "exact_whitespace_duplicate": exact,
                })
    exact_clusters = _cluster_rows("exact", output, exact_pairs, task_folds)
    near_clusters = _cluster_rows("near", output, near_pairs, task_folds)
    task_summary = {}
    for task in sorted(task_folds):
        task_ids = {row["source_id"] for row in output if task in row["task_outer_folds"]}
        def summary(pairs, clusters):
            local = [p for p in pairs if p["left"] in task_ids and p["right"] in task_ids]
            locations = {row["source_id"]: row["task_outer_folds"].get(task) for row in output}
            crossing = [p for p in local if locations[p["left"]] != locations[p["right"]]]
            train_exposed, val_exposed = set(), set()
            for cluster in clusters:
                for entry in cluster["outer_split_overlap"]:
                    if entry["task_id"] == task:
                        if entry["outer_has_inner_train_peer"]:
                            train_exposed.update(entry["members"]["outer_test_files"])
                        if entry["outer_has_inner_val_peer"]:
                            val_exposed.update(entry["members"]["outer_test_files"])
            return {
                "pairs": len(local), "cross_outer_fold_pairs": len(crossing),
                "clusters": sum(len(c["task_locations"][task]) >= 2 for c in clusters),
                "outer_test_files_with_inner_train_cluster_peer": len(train_exposed),
                "outer_test_files_with_inner_val_cluster_peer": len(val_exposed),
            }
        task_summary[task] = {
            "files": len(task_ids), "exact": summary(exact_pairs, exact_clusters),
            "near": summary(near_pairs, near_clusters),
        }
    return {
        "version": VERSION, "sources": output,
        "pairs": {"exact": exact_pairs, "near": near_pairs},
        "clusters": {"exact": exact_clusters, "near": near_clusters},
        "summary": {
            "source_identities": len(output), "candidate_pairs": candidate_count,
            "sequence_ratio_calls": ratio_count, "safe_upper_bound_rejections": bound_rejected,
            "exact_pairs": len(exact_pairs), "near_pairs": len(near_pairs),
            "exact_clusters": len(exact_clusters), "near_clusters": len(near_clusters),
            "tasks": task_summary,
        },
    }


FUTURE_PLAN = """# Future grouped-fold proposal — not executed

This document does not assign or modify any current fold and authorizes no fit.
Use a new server batch, new split version and output directory; retain the frozen
Prompt 8 results as historical baselines. Sufficient VRAM does not remove dataset
leakage. Do not pool new grouped-fold metrics with the original file-fold metrics.

1. Bind every raw file to category, cohort, original filename and source SHA.
   Freeze normalization, SequenceMatcher settings and the 0.98 threshold before
   looking at new model results. The current audit keeps autojunk=True (Python
   default); its popular-character heuristic can miss near clones. Review this
   limitation before preregistering a future grouping rule, not after scoring.
2. Form global connected components of exact and threshold-near pairs; retain
   singleton files. Project each group into each task. Preserve every file and
   label; conflicting labels must be reported, never silently corrected/dropped.
   A chain A~B~C is one group even when A~C fails the threshold; inspect oversized
   components and record the choice before generating folds.
3. For each contract task seek 5 outer group folds, for each node task 10.
   Deterministically balance group size and source cohort, and contract class
   counts where applicable. Grouping takes priority over exact stratification.
   Node datasets contain only vulnerable files, so file class stratification
   alone provides no balance information; report per-fold node/positive support.
   If the number or distribution of groups cannot support this K, stop and
   request a separately approved protocol instead of splitting groups.
4. Split each outer-training set into inner train/validation by the same group
   IDs, using a fixed seed and a preregistered balancing algorithm. No component
   may cross inner_train / inner_val / outer_test in a fitted model. Do not use
   predictions or outer scores to choose group assignments.
5. Seal group membership, raw-source hashes, split files, initialization, protocol
   and graph inputs in the new plan. All profiles use identical grouped splits.
   Assert group disjointness and exactly-once outer membership before fitting.
   Report task-specific file/group/node counts and cohort composition, no merged
   overall F1. Keep best selection on inner validation and outer final scoring.
6. Full fixed-graph forward is still transductive even with grouped supervision.
   If inductive generalization is desired, preregister separate forward/input
   isolation checks. Grouping alone does not establish external-test performance.
"""


def run(plan_path=DEFAULT_PLAN, output_dir=None):
    if output_dir is None:
        raise ValueError("Explicit exclusive output directory required")
    out = Path(output_dir)
    if not out.parent.is_dir():
        raise ValueError("Artifact parent must already exist")
    out.mkdir(exist_ok=False)
    started = time.monotonic()
    records, folds, bindings = load_inputs(plan_path)
    result = audit_records(records, folds)
    config = {
        "version": VERSION, "threshold": NEAR_THRESHOLD,
        "exact": "raw UTF-8 source; remove all Unicode whitespace; SHA256",
        "near": "remove comments outside strings; remove all Unicode whitespace; character SequenceMatcher",
        "autojunk": True, "isjunk": None,
        "pair_order": "ascending (category, cohort, filename, source_sha256)",
        "cluster_rule": "connected components, not all-pairs cliques",
        "limitations": [
            "Whitespace normalization also removes whitespace within literal values, as requested; textual identity is not semantic equivalence.",
            "SequenceMatcher ratio is order-dependent; fixed order is recorded, not replaced by a symmetric score.",
            "Default autojunk can suppress popular characters and miss near-clones; results are for this exact algorithm.",
            "Cluster overlap shows shared clone context, not a measured causal inflation of F1.",
        ],
    }
    documents = {
        "sources.json": result["sources"], "pairs.json": result["pairs"],
        "clusters.json": result["clusters"],
    }
    for name, document in documents.items():
        with (out / name).open("x", encoding="utf8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    (out / "FUTURE_GROUP_FOLDS.md").write_text(FUTURE_PLAN, encoding="utf8")
    report = {
        "status": "complete", "version": VERSION, "config": config,
        "bindings": bindings, "summary": result["summary"],
        "training_executed": False, "current_folds_changed": False,
        "elapsed_seconds": time.monotonic() - started,
        "artifacts": {name: {"path": str(out / name),
                             "sha256": sha256_bytes((out / name).read_bytes())}
                      for name in list(documents) + ["FUTURE_GROUP_FOLDS.md"]},
    }
    with (out / "audit.json").open("x", encoding="utf8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.output)["summary"], indent=2))


if __name__ == "__main__":
    main()
