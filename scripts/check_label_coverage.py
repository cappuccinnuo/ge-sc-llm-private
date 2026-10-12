"""Check vulnerability-annotation coverage for the reentrancy corpus.

Splits the 142 source contracts into their three provenances (SmartBugs wild-clean,
SolidiFI-injected, SmartBugs curated) and reports which ones a label source can
actually annotate. Anything buggy but unannotated would be silently trained as clean,
so this has to be verified before building the labelled graph.
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path("/home/zhao/SmartContract/ge-sc-llm")
SRC = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"
SMARTBUGS = REPO / "data/smartbug-dataset/vulnerabilities.json"
SOLIDIFI = REPO / "data/SolidiFI-benchmark"

contracts = sorted(p.name for p in SRC.glob("*.sol"))
wild = [c for c in contracts if c.startswith("0x")]
solidifi = [c for c in contracts if re.match(r"^buggy_\d+\.sol$", c)]
curated = [c for c in contracts if c not in wild and c not in solidifi]

print(f"total contracts          : {len(contracts)}")
print(f"  wild (0x*, presumed clean): {len(wild)}")
print(f"  solidifi (buggy_N.sol)    : {len(solidifi)}")
print(f"  curated (named)           : {len(curated)}")
print(f"  curated names: {curated}")
print()

# ---- SmartBugs curated ----
with open(SMARTBUGS) as f:
    sb = json.load(f)
print(f"SmartBugs vulnerabilities.json entries: {len(sb)}")
print(f"  sample entry: {json.dumps(sb[0], indent=2)[:400]}")
sb_names = {e["name"] for e in sb}
sb_cats = Counter(v["category"] for e in sb for v in e["vulnerabilities"])
print(f"  categories: {sb_cats.most_common()}")
print()

# SmartBugs 'name' may be a path; index by basename too
sb_by_base = {}
for e in sb:
    sb_by_base.setdefault(Path(e["name"]).name, e)

covered_curated = [c for c in curated if c in sb_by_base]
missing_curated = [c for c in curated if c not in sb_by_base]
print(f"curated covered by SmartBugs : {len(covered_curated)}/{len(curated)}")
if missing_curated:
    print(f"  MISSING: {missing_curated}")
for c in covered_curated[:3]:
    ent = sb_by_base[c]
    print(f"  e.g. {c} -> {ent['vulnerabilities']}")
print()

# any wild contract accidentally annotated?
wild_hit = [c for c in wild if c in sb_by_base]
print(f"wild contracts present in SmartBugs (would NOT be clean): {len(wild_hit)} {wild_hit[:5]}")
print()

# ---- SolidiFI ----
print("SolidiFI tree:")
if SOLIDIFI.exists():
    for p in sorted(SOLIDIFI.iterdir())[:15]:
        print("  ", p.name, "(dir)" if p.is_dir() else "")
    reentr = [p for p in SOLIDIFI.rglob("*") if p.is_dir() and "eentran" in p.name]
    print(f"  reentrancy-ish dirs: {[str(p.relative_to(SOLIDIFI)) for p in reentr][:10]}")
    buglogs = list(SOLIDIFI.rglob("BugLog*.csv"))
    print(f"  BugLog csv count: {len(buglogs)}")
    if buglogs:
        print(f"  sample: {buglogs[0].relative_to(SOLIDIFI)}")
        print("  ---- head ----")
        print("\n".join(buglogs[0].read_text().splitlines()[:6]))
else:
    print("  MISSING")
