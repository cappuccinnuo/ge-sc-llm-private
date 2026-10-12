"""Quantify the three call-resolution defects on the real reentrancy corpus.

  containment   'recursive_method_call' edges whose source is a contract/library/
                interface declaration - those encode "declares" not "calls"
  suffix        internal/external_call edges where the callee name is only a suffix
                of the text actually written at the call site, e.g. notf(3) matching f
  arity         several call edges out of one caller to same-named callees of
                different arity, which a single call site cannot produce
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parents[1]
GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/hcg_narrow.gpickle"

DECL = {"contract_declaration", "library_declaration", "interface_declaration"}

g = nx.read_gpickle(str(GRAPH))
print(f"graph: {GRAPH.name}  {g.number_of_nodes()} nodes / {g.number_of_edges()} edges")

ntype = {n: d.get("node_type") for n, d in g.nodes(data=True)}
code = {n: (d.get("code") or "") for n, d in g.nodes(data=True)}
src = {n: d.get("source_file") for n, d in g.nodes(data=True)}

et = Counter(d.get("edge_type") for _, _, d in g.edges(data=True))
print(f"edge types: {dict(et)}")

# ---- 1. containment edges wearing a call label ----
rec = [(s, t) for s, t, d in g.edges(data=True)
       if d.get("edge_type") == "recursive_method_call"]
from_decl = [(s, t) for s, t in rec if ntype[s] in DECL]
print(f"\nrecursive_method_call edges: {len(rec)}")
print(f"  with a declaration as source (containment, not a call): {len(from_decl)} "
      f"({100.0 * len(from_decl) / max(len(rec), 1):.1f}%)")
print(f"  source node types: {dict(Counter(ntype[s] for s, _ in rec))}")

# ---- 2/3. call edges out of one caller ----
name_re = re.compile(r"function\s+([A-Za-z_]\w*)")


def callee_name(node_id):
    m = name_re.search(code[node_id])
    return m.group(1) if m else None


calls = [(s, t) for s, t, d in g.edges(data=True)
         if d.get("edge_type") in ("internal_call", "external_call")]
print(f"\ninternal/external_call edges: {len(calls)}")

by_caller = defaultdict(list)
for s, t in calls:
    by_caller[s].append(t)

suffix_hits = 0
arity_groups = 0
examples = []
for caller, callees in by_caller.items():
    text = code[caller]
    names = [callee_name(t) for t in callees]
    # same-name callees reached from one caller -> overload fan-out
    dup = [n for n, c in Counter(n for n in names if n).items() if c > 1]
    if dup:
        arity_groups += 1

    for t, nm in zip(callees, names):
        if not nm:
            continue
        # the matcher accepts "<name>(" anywhere; a real call needs a token boundary
        loose = f"{nm}(" in text
        strict = re.search(rf"(?<![A-Za-z0-9_]){re.escape(nm)}\s*\(", text) is not None
        if loose and not strict:
            suffix_hits += 1
            if len(examples) < 5:
                examples.append((src[caller], nm, text.strip()[:70]))

print(f"  callers emitting >1 edge to same-named callees (overload fan-out): {arity_groups}")
print(f"  edges whose callee name only appears as a suffix at the call site: {suffix_hits}")
for f, nm, t in examples:
    print(f"    {f}  callee={nm!r}  caller text: {t!r}")

# ---- 4. calls the matcher cannot see: whitespace before '(' ----
missed = 0
miss_examples = []
for n, c in code.items():
    if ntype[n] != "function_definition":
        continue
    for m in re.finditer(r"(?<![A-Za-z0-9_])([A-Za-z_]\w*)\s+\(", c):
        nm = m.group(1)
        if nm in ("if", "for", "while", "return", "function", "require", "assert",
                  "emit", "new", "returns", "revert"):
            continue
        if f"{nm}(" not in c:          # written only with a space -> matcher blind
            missed += 1
            if len(miss_examples) < 5:
                miss_examples.append((src[n], nm, m.group(0)))
print(f"\ncall sites written as 'name (' that the matcher cannot see: {missed}")
for f, nm, frag in miss_examples:
    print(f"    {f}  {frag!r}")
