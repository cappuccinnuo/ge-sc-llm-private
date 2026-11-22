"""Group-disjoint nested folds: duplicate groups never straddle train/val/test.

Duplicate groups are connected components of two pair relations over a category's
source files: *exact* (equal after removing all whitespace) and *near* (comments
also removed, ``difflib.SequenceMatcher`` ratio >= 0.98 with autojunk, operands in
source-identity order). A composed dataset may add a third, *project*: files of one
audited project (Dataset B's DAppSCAN rows), which share code and style. Groups are assigned to K outer folds, then the remainder of
each fold to inner train/validation (80/20), by deterministic greedy balancing of
file class x cohort (SolidiFI or not) and positive/negative node counts, with SHA
tie-breaks. Assignment never sees predictions or scores.
"""
import collections
import difflib
import hashlib
import json
import re

VERSION = "dfg-v2-grouped-nested-v1"
ALGORITHM = "greedy-normalized-squared-stratum-balance-v1"
ROLES = ("inner_train_files", "inner_val_files", "outer_test_files")
NEAR_THRESHOLD = .98
K_FOLDS = {"contract": 5, "node": 10}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf8")).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf8")).hexdigest()


# ---------------------------------------------------------------------- duplicates

def strip_comments(text):
    """Blank out // and /* */ comments; strings and line positions are preserved."""
    chars, i = list(text), 0
    while i < len(text):
        if text[i] in ("'", '"'):
            quote, i = text[i], i + 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            continue
        if text.startswith("//", i) or text.startswith("/*", i):
            start = i
            if text.startswith("//", i):
                end = text.find("\n", i)
                end = len(text) if end < 0 else end
            else:
                end = text.find("*/", i + 2)
                end = len(text) if end < 0 else end + 2
            for k in range(start, end):
                if chars[k] not in "\r\n":
                    chars[k] = " "
            i = end
        else:
            i += 1
    return "".join(chars)


def without_whitespace(text):
    return "".join(text.split())


def source_identity(category, cohort, file, source):
    """Stable identity of one source file: category + cohort + name + SHA-256."""
    key = (category, cohort, file, sha256_text(source))
    return dict(category=category, cohort=cohort, file=file, source_sha256=key[3],
                source_id=hashlib.sha256(json.dumps(list(key), ensure_ascii=False).encode("utf8")).hexdigest())


def duplicate_pairs(identities, sources):
    """Exact and near-duplicate pairs over identities (sorted by identity)."""
    rows = sorted(identities, key=lambda r: (r["category"], r["cohort"], r["file"], r["source_sha256"]))
    exact, near = {}, {}
    for row in rows:
        text = sources[row["source_id"]]
        if not text.strip():
            raise ValueError("Empty source cannot establish duplicate identity: " + row["file"])
        exact[row["source_id"]] = without_whitespace(text)
        near[row["source_id"]] = without_whitespace(strip_comments(text))
    ids = [r["source_id"] for r in rows]
    pairs = {"exact": [], "near": []}
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            if exact[left] == exact[right]:
                pairs["exact"].append((left, right))
            a, b = near[left], near[right]
            if a == b:
                ratio = 1.0
            else:
                matcher = difflib.SequenceMatcher(None, a, b, autojunk=True)
                if matcher.real_quick_ratio() < NEAR_THRESHOLD or matcher.quick_ratio() < NEAR_THRESHOLD:
                    continue
                ratio = matcher.ratio()
            if ratio >= NEAR_THRESHOLD:
                pairs["near"].append((left, right))
    return pairs


def build_groups(source_ids, pairs):
    """Union of both pair relations; every singleton is its own group."""
    parent = {sid: sid for sid in source_ids}

    def find(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid

    for kind in sorted(pairs):
        for left, right in pairs[kind]:
            a, b = find(left), find(right)
            parent[max(a, b)] = min(a, b)
    result = collections.defaultdict(list)
    for sid in sorted(parent):
        result[find(sid)].append(sid)
    groups = [{"group_id": "group_" + digest(members), "members": members} for members in result.values()]
    return sorted(groups, key=lambda g: g["group_id"])


# ---------------------------------------------------------------------- assignment

def assign_groups(rows, fractions, seed):
    """Assign groups once, with seeded SHA tie-breaks; no score/seed search."""
    if type(seed) is not int or seed < 0:
        raise ValueError("Nonnegative integer split seed required")
    if len(fractions) < 2 or any(f <= 0 for f in fractions) or abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError("Positive fractions summing to one required")
    if len(rows) < len(fractions):
        raise ValueError("Too few whole groups for requested partitions")
    ids = [r["group_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated group")
    dimensions = sorted({key for r in rows for key in r["strata"]})
    totals = {d: sum(r["strata"].get(d, 0) for r in rows) for d in dimensions}
    if not dimensions or any(v < 0 for r in rows for v in r["strata"].values()) or not any(totals.values()):
        raise ValueError("Stratum counts must be nonnegative with positive support")
    dimensions = [d for d in dimensions if totals[d] > 0]
    tie = lambda name: digest([seed, name])  # noqa: E731
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
    return {"files": len(files), "groups": len({r["group_id"] for r in files}),
            "positive_files": sum(r["file_label"] == 1 for r in files),
            "negative_files": sum(r["file_label"] == 0 for r in files),
            "node_positive": sum(r["node_positive"] for r in files),
            "node_negative": sum(r["node_negative"] for r in files)}


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
            if not members or len(members) != len(set(members)) or not set(members) <= set(files):
                raise ValueError("Empty/duplicate/unknown split member")
            role_sets.append(set(members))
            role_groups.append({files[name]["group_id"] for name in members})
        if set.union(*role_sets) != set(files):
            raise ValueError("Missing sample in partition")
        for i in range(3):
            for j in range(i):
                if role_sets[i] & role_sets[j] or role_groups[i] & role_groups[j]:
                    raise ValueError("File or duplicate group leakage")
        seen.update(split["outer_test_files"])
    if seen != collections.Counter({name: 1 for name in files}):
        raise ValueError("Outer-test membership must be exactly once per source file")
    return True


def grouped_folds(task_id, file_rows, k_folds, seed=1, inner_fraction=.2):
    """Nested folds; no label-policy choice or score can influence them."""
    if k_folds < 2:
        raise ValueError("Need at least two folds")
    if not 0 < inner_fraction < 1:
        raise ValueError("Inner validation fraction must be inside (0,1)")
    groups = collections.defaultdict(list)
    for row in file_rows:
        if row["file_label"] not in (0, 1) or row["node_positive"] < 0 or row["node_negative"] < 0:
            raise ValueError("Invalid original class/support")
        groups[row["group_id"]].append(row)
    rows = [{"group_id": key, "strata": _strata(value)} for key, value in sorted(groups.items())]
    outer = assign_groups(rows, [1.0 / k_folds] * k_folds, seed)
    result = {"version": VERSION, "algorithm": ALGORITHM, "task_id": task_id, "k_folds": k_folds,
              "seed": seed, "inner_fraction": inner_fraction,
              "files": sorted(r["file"] for r in file_rows), "folds": []}
    for fold, test_groups in enumerate(outer):
        inner_seed = int(digest([seed, task_id, "inner", fold])[:8], 16)
        remainder = [r for r in rows if r["group_id"] not in test_groups]
        train_groups, val_groups = assign_groups(remainder, [1 - inner_fraction, inner_fraction], inner_seed)
        split = {"fold": fold, "inner_seed": inner_seed, "summary": {}}
        for role, ids in zip(ROLES, [train_groups, val_groups, test_groups]):
            selected = [r for r in file_rows if r["group_id"] in ids]
            split[role] = sorted(r["file"] for r in selected)
            split["summary"][role] = partition_summary(selected)
            if (k_folds == 5 and len({r["file_label"] for r in file_rows}) > 1
                    and len({r["file_label"] for r in selected}) != 2):
                raise ValueError("Grouped partition lacks a contract class; do not split groups or silently retry")
        result["folds"].append(split)
    validate_splits(result, file_rows)
    return result


# ---------------------------------------------------------------------- population

def cohort_of(file):
    return "SolidiFI" if re.fullmatch(r"buggy_\d+\.sol", file) else "nonSolidiFI"


def project_pairs(identities, projects):
    """Pairs chaining the files of each project ({file: project}; files without one: none)."""
    members = collections.defaultdict(list)
    for row in sorted(identities, key=lambda r: r["source_id"]):
        if projects.get(row["file"]):
            members[projects[row["file"]]].append(row["source_id"])
    return [(ids[i], ids[i + 1]) for _, ids in sorted(members.items()) for i in range(len(ids) - 1)]


def category_groups(category, cohort, sources, projects=None):
    """Duplicate (and, with ``projects`` {file: project}, project) groups of one category:
    ({file: group_id}, groups)."""
    identities = [source_identity(category, cohort, f, s) for f, s in sorted(sources.items())]
    texts = {r["source_id"]: sources[r["file"]] for r in identities}
    pairs = duplicate_pairs(identities, texts)
    if projects:
        pairs["project"] = project_pairs(identities, projects)
    groups = build_groups([r["source_id"] for r in identities], pairs)
    by_id = {r["source_id"]: r["file"] for r in identities}
    return {by_id[sid]: g["group_id"] for g in groups for sid in g["members"]}, groups


def population(graph, file_labels, group_of):
    """One stratification row per file of a task graph (original labels only)."""
    counts = collections.defaultdict(lambda: [0, 0])
    for _, data in graph.nodes(data=True):
        if data["node_type"] == "env_source":
            continue
        counts[data["source_file"]][int(data.get("node_info_vulnerabilities") is not None)] += 1
    return [dict(file=f, group_id=group_of[f], file_label=int(file_labels[f]), cohort=cohort_of(f),
                 node_positive=counts[f][1], node_negative=counts[f][0]) for f in sorted(counts)]
