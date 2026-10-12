"""Compare what MANDO-HGT actually labels against what we label.

We carry 408 more buggy nodes than appendix C reports for reentrancy, and the excess
has to come from which node types receive a label rather than from the graph itself -
node and edge totals already match exactly.

The repo ships a real Slither-built MANDO-HGT artifact,
access_control/curated/cfg_compressed_graphs.dot, with node_type and
node_info_vulnerabilities on every node. Reading the buggy rate per node type out of
it shows upstream's labelling behaviour directly, instead of inferring it from the
generator source.
"""
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UPSTREAM_DOT = REPO / "experiments/ge-sc-data/source_code/access_control/curated/cfg_compressed_graphs.dot"
OUR_GRAPH = REPO / "experiments/ge-sc-data/source_code/reentrancy/linelevel_narrow.gpickle"

print("=" * 76)
print("MANDO-HGT (Slither) artifact shipped in the repo")
print("=" * 76)
print(f"file: {UPSTREAM_DOT.name}")

text = UPSTREAM_DOT.read_text(encoding="utf8", errors="ignore")

# each node block runs from an id followed by '[' to the closing '];'
blocks = re.findall(r"\n\t(\w+)\t\[(.*?)\];", text, re.DOTALL)
print(f"node blocks parsed: {len(blocks)}")

total = Counter()
buggy = Counter()
lines_seen = {}
for node_id, body in blocks:
    m_type = re.search(r"node_type=([A-Za-z_]+)", body)
    if not m_type:
        continue
    ntype = m_type.group(1)
    total[ntype] += 1

    m_vul = re.search(r"node_info_vulnerabilities=(.*?)(?:,\n|\n\t\t\w+=)", body, re.DOTALL)
    raw = m_vul.group(1).strip() if m_vul else "None"
    is_buggy = raw not in ("None", '"None"', "")
    if is_buggy:
        buggy[ntype] += 1

    m_lines = re.search(r'node_source_code_lines="\[(.*?)\]"', body)
    if m_lines and ntype not in lines_seen:
        lines_seen[ntype] = m_lines.group(1)[:60]

print(f"\n{'node_type':24s} {'buggy':>6s} {'total':>6s}  rate     sample lines")
for t, n in total.most_common():
    rate = 100.0 * buggy[t] / n
    print(f"{t:24s} {buggy[t]:6d} {n:6d}  {rate:5.1f}%   {lines_seen.get(t, '')}")

tb, tt = sum(buggy.values()), sum(total.values())
print(f"\ntotal buggy {tb}/{tt} ({100.0 * tb / tt:.1f}%)")

fn_total = total.get("FUNCTION_NAME", 0)
fn_buggy = buggy.get("FUNCTION_NAME", 0)
print(f"\nFUNCTION_NAME (upstream's function-span node): {fn_buggy}/{fn_total} buggy")
if fn_total:
    print("  -> upstream DOES label function-span nodes"
          if fn_buggy else
          "  -> upstream does NOT label function-span nodes")
print("contract-spanning node type present upstream:",
      [t for t in total if "CONTRACT" in t.upper()] or "none")

print()
print("=" * 76)
print("ours (reentrancy line-level, narrowed end_if)")
print("=" * 76)
import networkx as nx
g = nx.read_gpickle(str(OUR_GRAPH))
ot, ob = Counter(), Counter()
for _, d in g.nodes(data=True):
    t = d.get("node_type")
    ot[t] += 1
    if d.get("node_info_vulnerabilities"):
        ob[t] += 1
print(f"{'node_type':24s} {'buggy':>6s} {'total':>6s}  rate")
for t, n in ot.most_common():
    print(f"{str(t):24s} {ob[t]:6d} {n:6d}  {100.0 * ob[t] / n:5.1f}%")
print(f"\ntotal buggy {sum(ob.values())}/{sum(ot.values())}   paper appendix C: 6570")

print("\nwhat removing each container type would leave:")
running = sum(ob.values())
for t in ("contract_declaration", "function_definition", "end_if"):
    running_wo = sum(ob.values()) - ob[t]
    print(f"  drop {t:24s} -> {running_wo}   (delta to 6570: {running_wo - 6570:+d})")
combo = sum(ob.values()) - ob["contract_declaration"] - ob["function_definition"]
print(f"  drop contract_declaration + function_definition -> {combo} "
      f"(delta {combo - 6570:+d})")
