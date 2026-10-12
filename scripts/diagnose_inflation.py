"""Work out why the line-level Buggy-F1 sits above the figure the paper reports.

Scoring higher than the source is a warning sign, not a win, so this looks for the
usual mechanical explanations rather than assuming the model is simply better:

  1. duplicate contracts - if the same .sol appears twice, splitting folds by
     contract still puts identical graphs on both sides
  2. container nodes - contract_declaration and function_definition span everything
     inside them, so in a buggy-contracts-only graph they are buggy almost by
     construction and cost the model nothing to get right
  3. label twins - end_if inherits the whole span of its if, so its label is a copy
     of an adjacent node's; a neighbour-averaging model gets those for free
  4. how much of the positive class those three account for
"""
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "experiments/ge-sc-data/source_code/reentrancy"
SRC = BASE / "source_files"
LINE_GRAPH = BASE / "linelevel_tokenizer_ids.gpickle"

CONTAINER_TYPES = {"contract_declaration", "function_definition", "library_declaration",
                   "interface_declaration", "modifier_definition", "constructor_definition",
                   "struct_declaration"}

print("=" * 74)
print("1. duplicate contracts in the corpus")
print("=" * 74)
digests = defaultdict(list)
for p in sorted(SRC.glob("*.sol")):
    digests[hashlib.md5(p.read_bytes()).hexdigest()].append(p.name)
dups = {d: names for d, names in digests.items() if len(names) > 1}
print(f"  .sol files       : {sum(len(v) for v in digests.values())}")
print(f"  distinct contents: {len(digests)}")
print(f"  duplicate groups : {len(dups)}")
for d, names in list(dups.items())[:5]:
    print(f"    {names}")

print()
print("=" * 74)
print("2/3/4. composition of the positive class in the line-level graph")
print("=" * 74)
g = nx.read_gpickle(str(LINE_GRAPH))
print(f"  nodes {g.number_of_nodes()}  edges {g.number_of_edges()}")

buggy_by_type = Counter()
total_by_type = Counter()
for _, d in g.nodes(data=True):
    t = d.get("node_type")
    total_by_type[t] += 1
    if d.get("node_info_vulnerabilities"):
        buggy_by_type[t] += 1

total_buggy = sum(buggy_by_type.values())
print(f"  buggy nodes {total_buggy}/{g.number_of_nodes()} "
      f"({100.0 * total_buggy / g.number_of_nodes():.2f}%)")
print(f"\n  {'node_type':26s} {'buggy':>6s} {'total':>6s}  buggy-rate")
for t, n in total_by_type.most_common():
    rate = 100.0 * buggy_by_type[t] / n
    flag = "  <- container" if t in CONTAINER_TYPES else ""
    print(f"  {str(t):26s} {buggy_by_type[t]:6d} {n:6d}  {rate:6.1f}%{flag}")

container_buggy = sum(buggy_by_type[t] for t in CONTAINER_TYPES)
print(f"\n  container-type buggy nodes: {container_buggy}/{total_buggy} "
      f"({100.0 * container_buggy / total_buggy:.1f}% of the positive class)")

print()
print("  end_if label twins")
node_type = {n: d.get("node_type") for n, d in g.nodes(data=True)}
is_buggy = {n: bool(d.get("node_info_vulnerabilities")) for n, d in g.nodes(data=True)}
lines_of = {n: tuple(d.get("node_source_code_lines_original") or ())
            for n, d in g.nodes(data=True)}

if_by_span = defaultdict(list)
for n, t in node_type.items():
    if t == "if":
        if_by_span[lines_of[n]].append(n)

twins = 0
twins_buggy = 0
for n, t in node_type.items():
    if t != "end_if":
        continue
    peers = if_by_span.get(lines_of[n])
    if peers:
        twins += 1
        if is_buggy[n] and any(is_buggy[p] for p in peers):
            twins_buggy += 1
print(f"    end_if nodes sharing an exact span with an 'if': {twins}/{total_by_type['end_if']}")
print(f"    of those, both labelled buggy                  : {twins_buggy}")

free = container_buggy + twins_buggy
print(f"\n  positives obtainable without real localisation: ~{free}/{total_buggy} "
      f"({100.0 * free / total_buggy:.1f}%)")
