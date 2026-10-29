"""Group-disjoint nested splits for the prepared Prompt 8D benchmark.

Grouping reuses frozen Prompt 8C textual duplicate components. Stratification
is deterministic greedy balancing of original class/cohort/node support, never
of predictions, C1/C2 scores, or prospective model results. Grouping has priority
over exact balance. This is not an independent-source test or semantic clone
detector.
"""
import collections
import hashlib
import json

VERSION = "dfg-v2-grouped-nested-v1"
ALGORITHM = "greedy-normalized-squared-stratum-balance-v1"
ROLES = ("inner_train_files", "inner_val_files", "outer_test_files")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf8")).hexdigest()


def build_groups(sources, clusters):
    """Union both frozen pair-component sets; retain every singleton."""
    indexed = {s["source_id"]: s for s in sources}
    if len(indexed) != len(sources):
        raise ValueError("Duplicate source identity")
    parent = {sid: sid for sid in indexed}

    def find(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid

    for kind in ("exact", "near"):
        for cluster in clusters[kind]:
            members = cluster["members"]
            if len(members) < 2 or len(set(members)) != len(members):
                raise ValueError("Malformed frozen duplicate component")
            if not set(members).issubset(indexed):
                raise ValueError("Duplicate component has unknown source")
            anchor = members[0]
            for sid in members[1:]:
                left, right = find(anchor), find(sid)
                parent[max(left, right)] = min(left, right)
    result = collections.defaultdict(list)
    for sid in sorted(indexed):
        result[find(sid)].append(sid)
    groups = [{"group_id": "group_" + digest(members), "members": members}
              for members in result.values()]
    return sorted(groups, key=lambda g: g["group_id"])


def assign_groups(rows, fractions, seed):
    """Assign groups once, with seeded SHA tie-breaks; no score/seed search."""
    if type(seed) is not int or seed < 0:
        raise ValueError("Nonnegative integer split seed required")
    if (len(fractions) < 2 or any(f <= 0 for f in fractions)
            or abs(sum(fractions) - 1.0) > 1e-12):
        raise ValueError("Positive fractions summing to one required")
    if len(rows) < len(fractions):
        raise ValueError("Too few whole groups for requested partitions")
    ids = [r["group_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated group")
    dimensions = sorted({key for r in rows for key in r["strata"]})
    totals = {d: sum(r["strata"].get(d, 0) for r in rows) for d in dimensions}
    if (not dimensions or any(v < 0 for r in rows for v in r["strata"].values())
            or not any(totals.values())):
        raise ValueError("Stratum counts must be nonnegative with positive support")
    dimensions = [d for d in dimensions if totals[d] > 0]
    tie = lambda name: digest([seed, name])
    ordered = sorted(rows, key=lambda r: (
        -max(r["strata"].get(d, 0) / float(totals[d]) for d in dimensions),
        -sum(r["strata"].get(d, 0) / float(totals[d]) for d in dimensions),
        tie(r["group_id"])))
    assigned = [[] for _ in fractions]
    counts = [{d: 0 for d in dimensions} for _ in fractions]
    for position, row in enumerate(ordered):
        empty = [i for i, part in enumerate(assigned) if not part]
        candidates = empty if len(ordered) - position == len(empty) else range(len(fractions))
        def cost(i):
            # Change in global normalized squared deviation from target fraction.
            value = 0.0
            for d in dimensions:
                before = counts[i][d] / float(totals[d]) - fractions[i]
                after = before + row["strata"].get(d, 0) / float(totals[d])
                value += (after * after - before * before) / fractions[i]
            return (value, len(assigned[i]), tie([row["group_id"], i]))
        selected = min(candidates, key=cost)
        assigned[selected].append(row["group_id"])
        for d in dimensions:
            counts[selected][d] += row["strata"].get(d, 0)
    return [sorted(part) for part in assigned]


def _strata(files):
    out = collections.Counter()
    for row in files:
        out["files"] += 1
        out["file_class_%s_cohort_%s" % (row["file_label"], row["cohort"])] += 1
        out["nodes_positive"] += row["node_positive"]
        out["nodes_negative"] += row["node_negative"]
    return dict(out)


def partition_summary(files):
    out = {
        "files": len(files), "groups": len({r["group_id"] for r in files}),
        "positive_files": sum(r["file_label"] == 1 for r in files),
        "negative_files": sum(r["file_label"] == 0 for r in files),
        "source_cohorts": dict(collections.Counter(r["cohort"] for r in files)),
        "original_node_positive": sum(r["node_positive"] for r in files),
        "original_node_negative": sum(r["node_negative"] for r in files),
        "audit_node_positive": sum(r.get("audit_node_positive", 0) for r in files),
        "audit_node_negative": sum(r.get("audit_node_negative", 0) for r in files),
        "audit_masked_nodes": sum(r.get("audit_masked_nodes", 0) for r in files),
        "group_members": {},
    }
    for row in files:
        out["group_members"].setdefault(row["group_id"], []).append(row["source_id"])
    out["group_members"] = {key: sorted(value) for key, value in sorted(out["group_members"].items())}
    return out


def validate_splits(document, file_rows):
    files = {r["file"]: r for r in file_rows}
    if len(files) != len(file_rows):
        raise ValueError("Filename collision within task")
    if len(document["folds"]) != document["k_folds"]:
        raise ValueError("Missing folds")
    seen = collections.Counter()
    for expected_fold, split in enumerate(document["folds"]):
        if split["fold"] != expected_fold:
            raise ValueError("Fold order/identity differs")
        role_sets, role_groups = [], []
        for role in ROLES:
            members = split[role]
            if not members or len(members) != len(set(members)) or not set(members).issubset(files):
                raise ValueError("Empty/duplicate/unknown split member")
            role_sets.append(set(members))
            role_groups.append({files[name]["group_id"] for name in members})
        if set.union(*role_sets) != set(files):
            raise ValueError("Missing sample in partition")
        for i in range(3):
            for j in range(i):
                if role_sets[i] & role_sets[j] or role_groups[i] & role_groups[j]:
                    raise ValueError("File or duplicate group leakage")
        for name in split["outer_test_files"]:
            seen[name] += 1
    if seen != collections.Counter({name: 1 for name in files}):
        raise ValueError("Outer-test membership must be exactly once per source file")
    return {"passed": True, "files": len(files), "folds": document["k_folds"],
            "cross_partition_groups": 0, "outer_memberships_exactly_once": True}


def grouped_folds(task_id, file_rows, k_folds, seed=1, inner_fraction=.2):
    """No caller-provided label-policy choice can influence these splits."""
    if k_folds not in (5, 10):
        raise ValueError("Benchmark contract/node K must be 5 or 10")
    if not 0 < inner_fraction < 1:
        raise ValueError("Inner validation fraction must be inside (0,1)")
    groups = collections.defaultdict(list)
    for row in file_rows:
        if (row["file_label"] not in (0, 1) or row["node_positive"] < 0
                or row["node_negative"] < 0):
            raise ValueError("Invalid original class/support")
        groups[row["group_id"]].append(row)
    rows = [{"group_id": key, "strata": _strata(value)} for key, value in sorted(groups.items())]
    outer = assign_groups(rows, [1.0 / k_folds] * k_folds, seed)
    result = {"version": VERSION, "algorithm": ALGORITHM, "task_id": task_id,
              "k_folds": k_folds, "seed": seed, "inner_fraction": inner_fraction,
              "group_priority_over_exact_stratification": True,
              "stratification_labels": "original frozen labels only; independent of L-orig/L-audit selection",
              "files": sorted(r["file"] for r in file_rows),
              "source_population_sha256": digest(sorted(file_rows, key=lambda r: r["file"])),
              "folds": []}
    for fold, test_groups in enumerate(outer):
        inner_seed = int(digest([seed, task_id, "inner", fold])[:8], 16)
        remainder = [r for r in rows if r["group_id"] not in test_groups]
        train_groups, val_groups = assign_groups(remainder, [1-inner_fraction, inner_fraction], inner_seed)
        group_parts = [train_groups, val_groups, test_groups]
        split = {"fold": fold, "inner_seed": inner_seed, "summary": {}}
        for role, ids in zip(ROLES, group_parts):
            selected = [r for r in file_rows if r["group_id"] in ids]
            split[role] = sorted(r["file"] for r in selected)
            split["summary"][role] = partition_summary(selected)
            if (k_folds == 5 and len({r["file_label"] for r in file_rows}) > 1
                    and len({r["file_label"] for r in selected}) != 2):
                raise ValueError("Grouped partition lacks a contract class; do not split groups or silently retry")
        result["folds"].append(split)
    result["validation"] = validate_splits(result, file_rows)
    return result
