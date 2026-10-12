"""Localise the +408 buggy-node excess against appendix C (6,570 for reentrancy).

Every hypothesis tried so far was about node types. This splits by annotation SOURCE
instead, because the two sources have very different provenance:

  SmartBugs curated : ships vulnerabilities.json already in the required shape, so it
                      is used verbatim - nothing of ours can be wrong there
  SolidiFI          : ships BugLog_*.csv, and the conversion to line ranges is a
                      reconstruction of ours; the authors used a pre-built
                      solidifi_buggy_contracts/<bug>/vulnerabilities.json that this
                      repo does not contain

If the excess sits on the SolidiFI side, the conversion is the suspect. If it sits on
the SmartBugs side, the conversion is fine and the cause is elsewhere.

Also checks the annotation counts against the scale mando-llm.md section 13 quotes
(SmartBugs 208 tagged vulnerabilities; SolidiFI 9,369 injected bugs over 7 types).
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
GRAPH = BASE / "hcg_narrow.gpickle"          # full 142-contract graph, narrowed end_if
SRC = BASE / "source_files"
SMARTBUGS = REPO / "data/smartbug-dataset/vulnerabilities.json"
SOLIDIFI_LOGS = REPO / "data/SolidiFI-benchmark/buggy_contracts/Re-entrancy"

PAPER_BUGGY = 6570

g = nx.read_gpickle(str(GRAPH))
print(f"graph: {GRAPH.name}  {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")

corpus = sorted(p.name for p in SRC.glob("*.sol"))
solidifi_names = {c for c in corpus if re.match(r"^buggy_\d+\.sol$", c)}
sb = json.load(open(SMARTBUGS))
sb_names = {Path(e["name"]).name for e in sb}
smartbugs_names = {c for c in corpus if c in sb_names}

print(f"\ncorpus {len(corpus)} contracts")
print(f"  SolidiFI-named  : {len(solidifi_names)}")
print(f"  SmartBugs-listed: {len(smartbugs_names)}")
print(f"  overlap         : {len(solidifi_names & smartbugs_names)}")
print(f"  neither (clean) : {len(set(corpus) - solidifi_names - smartbugs_names)}")

# ---- annotation volume vs the paper's stated scale ----
sb_vulns = sum(len(e["vulnerabilities"]) for e in sb)
print(f"\nSmartBugs vulnerabilities.json: {len(sb)} entries, {sb_vulns} tagged "
      f"vulnerabilities  (mando-llm.md section 13.1 says 208)")

rows = 0
lines_total = 0
per_contract = Counter()
for csv_path in sorted(SOLIDIFI_LOGS.glob("BugLog_*.csv")):
    name = f"buggy_{csv_path.stem.split('_')[-1]}.sol"
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                loc, length = int(row["loc"]), int(row["length"])
            except (KeyError, ValueError, TypeError):
                continue
            if length <= 0:
                continue
            rows += 1
            if name in solidifi_names:
                per_contract[name] += 1
                lines_total += length
print(f"SolidiFI Re-entrancy BugLogs : {rows} injected bugs across "
      f"{len(list(SOLIDIFI_LOGS.glob('BugLog_*.csv')))} contracts")
print(f"  of those, in our 40 contracts: {sum(per_contract.values())} bugs, "
      f"{lines_total} annotated lines")

# ---- where do the buggy nodes sit ----
buggy_by_source = Counter()
nodes_by_source = Counter()
buggy_types = {"solidifi": Counter(), "smartbugs": Counter(), "clean": Counter()}
for _, d in g.nodes(data=True):
    sf = d["source_file"]
    if sf in solidifi_names:
        bucket = "solidifi"
    elif sf in smartbugs_names:
        bucket = "smartbugs"
    else:
        bucket = "clean"
    nodes_by_source[bucket] += 1
    if d.get("node_info_vulnerabilities"):
        buggy_by_source[bucket] += 1
        buggy_types[bucket][d.get("node_type")] += 1

total_buggy = sum(buggy_by_source.values())
print(f"\nbuggy nodes by annotation source (total {total_buggy}, paper {PAPER_BUGGY}, "
      f"excess {total_buggy - PAPER_BUGGY:+d})")
for bucket in ("solidifi", "smartbugs", "clean"):
    n, b = nodes_by_source[bucket], buggy_by_source[bucket]
    rate = 100.0 * b / n if n else 0.0
    print(f"  {bucket:10s} nodes {n:6d}  buggy {b:6d}  ({rate:5.1f}%)")

print("\nbuggy node types, SolidiFI contracts:")
for t, n in buggy_types["solidifi"].most_common():
    print(f"  {str(t):24s} {n}")
print("buggy node types, SmartBugs contracts:")
for t, n in buggy_types["smartbugs"].most_common():
    print(f"  {str(t):24s} {n}")

# ---- annotated lines vs nodes hit, per source ----
print("\nannotated lines per contract (how wide the ground truth is)")
for bucket, names in (("solidifi", solidifi_names), ("smartbugs", smartbugs_names)):
    covered = Counter()
    for _, d in g.nodes(data=True):
        if d["source_file"] in names and d.get("node_info_vulnerabilities"):
            for v in d["node_info_vulnerabilities"]:
                covered[d["source_file"]] |= 0
    ann_lines = Counter()
    for _, d in g.nodes(data=True):
        sf = d["source_file"]
        if sf not in names:
            continue
        for v in (d.get("node_info_vulnerabilities") or []):
            ann_lines[sf] = max(ann_lines[sf], len(v["lines"]))
    if ann_lines:
        vals = sorted(ann_lines.values())
        print(f"  {bucket:10s} widest annotation span per contract: "
              f"min {vals[0]}  median {vals[len(vals)//2]}  max {vals[-1]}")
