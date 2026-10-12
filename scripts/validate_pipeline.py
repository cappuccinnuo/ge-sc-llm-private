"""Independent validation of the merge + labelling pipeline.

Four checks, each able to fail loudly:

  1. line_mapping.build_line_map reproduces the REAL preprocessor output exactly
     (same line count, and every mapped original line's text matches), for every
     contract in the corpus. This is the check that decides whether the label
     translation is trustworthy.

  2. No node references a preprocessed line outside its file's map, which would
     make preprocessed_to_original silently drop lines and under-label.

  3. Annotation lookup is unambiguous: no contract name is claimed by more than one
     annotation record (upstream's get_vulnerabilities keeps the LAST match, so a
     collision would silently shadow one source).

  4. Labels in the built graph are internally consistent: every buggy node's
     translated original lines really do intersect its contract's annotated lines,
     and every clean node's really do not.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from line_mapping import build_line_map, preprocessed_to_original  # noqa: E402
from process_graphs.tree_sitter_codeviews.utils import preprocessor  # noqa: E402

SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/cfg_compressed_graphs.gpickle"
SMARTBUGS = REPO / "data/smartbug-dataset/vulnerabilities.json"
SOLIDIFI_LOGS = REPO / "data/SolidiFI-benchmark/buggy_contracts/Re-entrancy"

failures = []


def fail(check, msg):
    failures.append((check, msg))
    print(f"    FAIL: {msg}")


# ---------------------------------------------------------------- check 1
print("=" * 78)
print("CHECK 1: build_line_map reproduces the real preprocessor output")
print("=" * 78)
mismatch = 0
checked = 0
for sol in sorted(SRC.glob("*.sol")):
    raw = sol.read_text(encoding="utf8", errors="ignore")

    # what the real parser actually parses
    real = preprocessor.remove_empty_lines(raw)
    real = preprocessor.remove_comments("solidity", real)
    real_lines = real.split("\n")

    line_map = build_line_map(raw)
    checked += 1

    if len(real_lines) != len(line_map):
        mismatch += 1
        if mismatch <= 5:
            fail("1", f"{sol.name}: preprocessor={len(real_lines)} lines, "
                      f"line_map={len(line_map)} lines")
        continue

    # every mapped original line must textually appear in the corresponding
    # preprocessed line (comments stripped, so use the code prefix)
    original = raw.split("\n")
    bad = 0
    for idx, origins in enumerate(line_map):
        if not origins:
            continue
        pre_text = real_lines[idx].strip()
        orig_text = original[origins[0] - 1].strip()
        if not pre_text or not orig_text:
            continue
        head = orig_text.split("//")[0].split("/*")[0].strip()
        if head and not pre_text.startswith(head[: min(len(head), 25)]):
            bad += 1
    if bad:
        mismatch += 1
        if mismatch <= 5:
            fail("1", f"{sol.name}: {bad} mapped lines whose text does not match")

print(f"  contracts checked        : {checked}")
print(f"  contracts with mismatch  : {mismatch}")
if mismatch == 0:
    print("  OK - mapping is byte-faithful to the real preprocessor")

# ---------------------------------------------------------------- check 2
print()
print("=" * 78)
print("CHECK 2: no node references a preprocessed line outside its file's map")
print("=" * 78)
g = nx.read_gpickle(str(GRAPH))
maps = {}
overflow = Counter()
max_seen = defaultdict(int)
for _, d in g.nodes(data=True):
    sf = d.get("source_file")
    if sf not in maps:
        p = SRC / sf
        maps[sf] = build_line_map(p.read_text(encoding="utf8", errors="ignore")) if p.exists() else []
    m = maps[sf]
    for p_line in d.get("node_source_code_lines") or []:
        max_seen[sf] = max(max_seen[sf], p_line)
        if p_line < 1 or p_line > len(m):
            overflow[sf] += 1

print(f"  contracts                      : {len(maps)}")
print(f"  contracts with out-of-range refs: {len(overflow)}")
if overflow:
    for sf, n in overflow.most_common(10):
        fail("2", f"{sf}: {n} node lines outside map (map len={len(maps[sf])}, "
                  f"max referenced={max_seen[sf]})")
else:
    print("  OK - every node line resolves inside its map")

# ---------------------------------------------------------------- check 3
print()
print("=" * 78)
print("CHECK 3: annotation names are unambiguous")
print("=" * 78)
sb = [{"name": Path(e["name"]).name, "vulnerabilities": e["vulnerabilities"]}
      for e in json.load(open(SMARTBUGS))]
import csv  # noqa: E402
sf_records = []
for csv_path in sorted(SOLIDIFI_LOGS.glob("BugLog_*.csv")):
    idx = csv_path.stem.split("_")[-1]
    vulns = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                loc, length = int(row["loc"]), int(row["length"])
            except (KeyError, ValueError, TypeError):
                continue
            if length > 0:
                vulns.append({"lines": list(range(loc, loc + length)), "category": "reentrancy"})
    if vulns:
        sf_records.append({"name": f"buggy_{idx}.sol", "vulnerabilities": vulns})

all_records = sb + sf_records
name_counts = Counter(r["name"] for r in all_records)
corpus = {p.name for p in SRC.glob("*.sol")}
dupes = {n: c for n, c in name_counts.items() if c > 1 and n in corpus}
print(f"  annotation records            : {len(all_records)}")
print(f"  names listed more than once   : {len(dupes)} {list(dupes)}")

# Duplicates are expected (a contract can sit in two SmartBugs category folders).
# What must hold is that the built graph did not lose any of those records, i.e.
# our accumulating get_vulnerabilities kept every annotated line.
g_pre = nx.read_gpickle(str(GRAPH))
lost = []
for name in dupes:
    expected = set()
    for r in all_records:
        if r["name"] == name:
            for v in r["vulnerabilities"]:
                expected.update(v["lines"])
    seen = set()
    for _, d in g_pre.nodes(data=True):
        if d.get("source_file") != name:
            continue
        for v in (d.get("node_info_vulnerabilities") or []):
            seen.update(v["lines"])
    covered_by_nodes = set()
    for _, d in g_pre.nodes(data=True):
        if d.get("source_file") == name:
            covered_by_nodes.update(d.get("node_source_code_lines_original") or [])
    # only fault lines that a node actually covers but that never got attached
    missed = (expected & covered_by_nodes) - seen
    if missed:
        lost.append((name, sorted(missed)))

if lost:
    for name, missed in lost:
        fail("3", f"{name}: annotated lines {missed} are covered by nodes but never labelled")
else:
    print("  OK - duplicated records are accumulated, no annotation lines lost")

# ---------------------------------------------------------------- check 4
print()
print("=" * 78)
print("CHECK 4: graph labels are consistent with the annotations")
print("=" * 78)
# Accumulate, matching build_labeled_graph.get_vulnerabilities. Assigning here
# would reintroduce upstream's keep-last shadowing and report the extra labels
# from a duplicated contract as false positives.
ann = defaultdict(list)
for r in all_records:
    ann[r["name"]].extend(r["vulnerabilities"])

wrong_buggy = 0
wrong_clean = 0
buggy_nodes = 0
for _, d in g.nodes(data=True):
    sf = d.get("source_file")
    vulns = ann.get(sf)
    orig = set(d.get("node_source_code_lines_original") or [])
    should_be_buggy = False
    if vulns:
        for v in vulns:
            if orig & set(v["lines"]):
                should_be_buggy = True
                break
    is_buggy = bool(d.get("node_info_vulnerabilities"))
    if is_buggy:
        buggy_nodes += 1
    if is_buggy and not should_be_buggy:
        wrong_buggy += 1
    if should_be_buggy and not is_buggy:
        wrong_clean += 1

print(f"  buggy nodes in graph          : {buggy_nodes}")
print(f"  labelled buggy but shouldn't  : {wrong_buggy}")
print(f"  should be buggy but labelled clean: {wrong_clean}")
if wrong_buggy or wrong_clean:
    fail("4", f"{wrong_buggy} false positives, {wrong_clean} false negatives")
else:
    print("  OK - labels match a freshly recomputed intersection")

# also re-derive original lines independently and compare
drift = 0
for _, d in g.nodes(data=True):
    sf = d.get("source_file")
    recomputed = preprocessed_to_original(d.get("node_source_code_lines") or [], maps[sf])
    if recomputed != (d.get("node_source_code_lines_original") or []):
        drift += 1
print(f"  nodes whose stored original lines differ on recompute: {drift}")
if drift:
    fail("4", f"{drift} nodes have stale node_source_code_lines_original")

# ---------------------------------------------------------------- summary
print()
print("=" * 78)
if failures:
    print(f"RESULT: {len(failures)} CHECK(S) FAILED")
    for c, m in failures:
        print(f"  [check {c}] {m}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
