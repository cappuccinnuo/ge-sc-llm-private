"""Resolve the true buggy/clean split of the reentrancy corpus.

Verifies (a) which categories the address-named contracts carry in SmartBugs, and
(b) where SolidiFI keeps the authoritative injected-bug logs and how their line
ranges are encoded.
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
solidifi_names = [c for c in contracts if re.match(r"^buggy_\d+\.sol$", c)]

with open(SMARTBUGS) as f:
    sb = json.load(f)
sb_by_base = {Path(e["name"]).name: e for e in sb}

print("=" * 70)
print("SmartBugs coverage over the 142 reentrancy contracts")
print("=" * 70)
matched = [c for c in contracts if c in sb_by_base]
print(f"matched in SmartBugs: {len(matched)}")

cat_counter = Counter()
reentrancy_matched = []
for c in matched:
    cats = {v["category"] for v in sb_by_base[c]["vulnerabilities"]}
    for cat in cats:
        cat_counter[cat] += 1
    if "reentrancy" in cats:
        reentrancy_matched.append(c)
print(f"category spread among matched: {cat_counter.most_common()}")
print(f"contracts carrying a 'reentrancy' annotation: {len(reentrancy_matched)}")
print()
print("sample address-named ones with their annotation:")
for c in [x for x in reentrancy_matched if x.startswith("0x")][:5]:
    e = sb_by_base[c]
    print(f"  {c}\n    path={e.get('path')}\n    vulns={e['vulnerabilities']}")
print()

print(f"SolidiFI-named contracts in corpus: {len(solidifi_names)}")
print(f"=> candidate buggy total = {len(reentrancy_matched)} (smartbugs) + {len(solidifi_names)} (solidifi) = {len(reentrancy_matched) + len(solidifi_names)}")
print(f"=> candidate clean total = {len(contracts)} - that = {len(contracts) - len(reentrancy_matched) - len(solidifi_names)}")
print()

print("=" * 70)
print("SolidiFI layout")
print("=" * 70)
bc = SOLIDIFI / "buggy_contracts"
if bc.exists():
    print("buggy_contracts/ subdirs:", [p.name for p in sorted(bc.iterdir()) if p.is_dir()])
    for p in sorted(bc.iterdir()):
        if p.is_dir() and "eentran" in p.name.lower():
            files = sorted(p.iterdir())
            print(f"\n  {p.name}: {len(files)} entries")
            print("   sample:", [f.name for f in files[:8]])
            logs = sorted(p.glob("BugLog_*.csv"))
            print(f"   BugLog csv: {len(logs)}")
            if logs:
                print(f"   --- {logs[0].name} head ---")
                print("\n".join("     " + l for l in logs[0].read_text().splitlines()[:6]))
            sols = sorted(p.glob("buggy_*.sol"))
            print(f"   buggy_*.sol: {len(sols)}  sample={[s.name for s in sols[:5]]}")
else:
    print("buggy_contracts/ MISSING")
