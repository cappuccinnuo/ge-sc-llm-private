"""Compare corpus .sol files against the SmartBugs curated originals.

If the corpus copies were edited (headers/comments stripped), SmartBugs line
annotations no longer line up and every label derived from them is wrong.
"""
import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SB = REPO / "data/smartbug-dataset/dataset/reentrancy"
CO = REPO / "experiments/ge-sc-data/source_code/reentrancy/source_files"


def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()


sb_files = {p.name: p for p in SB.glob("*.sol")} if SB.exists() else {}
print(f"SmartBugs reentrancy dataset dir: {SB}  ({len(sb_files)} files)")
if not sb_files:
    print("  !! directory missing - check the clone layout")
    for cand in sorted((REPO / 'data/smartbug-dataset').rglob('reentrancy')):
        print("   candidate:", cand)
    raise SystemExit(1)

same, diff, absent = [], [], []
for p in sorted(CO.glob("*.sol")):
    if p.name not in sb_files:
        absent.append(p.name)
        continue
    q = sb_files[p.name]
    if md5(p) == md5(q):
        same.append(p.name)
    else:
        nl_c = len(p.read_text(encoding="utf8", errors="ignore").splitlines())
        nl_s = len(q.read_text(encoding="utf8", errors="ignore").splitlines())
        diff.append((p.name, nl_s, nl_c))

print(f"\nidentical to SmartBugs : {len(same)}")
print(f"different              : {len(diff)}")
print(f"not in SmartBugs       : {len(absent)}")

print("\n--- differing files (smartbugs_lines -> corpus_lines) ---")
for name, ns, nc in diff:
    print(f"  {name:55s} {ns:5d} -> {nc:5d}   (delta {nc - ns:+d})")

print("\n--- identical files (sample) ---")
for name in same[:10]:
    print("  ", name)
