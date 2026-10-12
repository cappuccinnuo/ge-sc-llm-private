"""Read-only: what source / annotation material exists per bug type, and do the copies agree?

    python -B Test_code/dataset_check/explore_sources.py
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HGT = REPO.parent / "ge-sc-transformer"
SRC = REPO / "experiments/ge-sc-data/source_code"
SOLIDIFI = REPO / "data/SolidiFI-benchmark/buggy_contracts"
BUGS = ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy",
        "time_manipulation", "unchecked_low_level_calls"]


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def csv_lines(path):
    out = set()
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            out.update(range(int(row["loc"]), int(row["loc"]) + int(row["length"])))
    return out


solidifi_hash = {}
for cat in sorted(p for p in SOLIDIFI.iterdir() if p.is_dir()):
    for sol in cat.glob("buggy_*.sol"):
        solidifi_hash.setdefault(md5(sol), []).append(f"{cat.name}/{sol.name}")

sb_local = json.load(open(REPO / "data/smartbug-dataset/vulnerabilities.json"))
sb_hgt = json.load(open(HGT / "data/smartbug-dataset/vulnerabilities.json"))
print("smartbugs vulnerabilities.json: local == HGT copy:", sb_local == sb_hgt, "records", len(sb_local))

for bug in BUGS:
    print("=" * 90)
    print(bug)
    base = SRC / bug
    for sub in sorted(p for p in base.iterdir() if p.is_dir()):
        kinds = Counter(f.suffix for f in sub.iterdir() if f.is_file())
        print(f"  {sub.name:28s} {dict(kinds)}")
    hgt_dir = HGT / f"data/solidifi_buggy_contracts/{bug}"
    recs = json.load(open(hgt_dir / "vulnerabilities.json"))
    cats = Counter()
    same_csv = diff_csv = no_csv = 0
    src_same = src_diff = 0
    examples = []
    for rec in recs:
        name = Path(rec["name"]).name
        hgt_sol = hgt_dir / name
        origin = solidifi_hash.get(md5(hgt_sol), []) if hgt_sol.exists() else []
        for o in origin:
            cats[o.split("/")[0]] += 1
        json_lines = {n for v in rec["vulnerabilities"] for n in v["lines"]}
        matched = False
        for o in origin:
            cat, sol = o.split("/")
            log = SOLIDIFI / cat / sol.replace("buggy_", "BugLog_").replace(".sol", ".csv")
            if log.exists() and csv_lines(log) == json_lines:
                matched = True
        if not origin:
            no_csv += 1
        elif matched:
            same_csv += 1
        else:
            diff_csv += 1
            examples.append(name)
        for cand in (base / "source_files" / name, base / "buggy_curated" / name, base / "buggy" / name):
            if cand.exists():
                if hgt_sol.exists() and md5(cand) == md5(hgt_sol):
                    src_same += 1
                else:
                    src_diff += 1
                break
    print(f"  HGT solidifi json: {len(recs)} records; source matches SolidiFI category {dict(cats)}")
    print(f"     json lines == BugLog csv ranges: {same_csv}, differ: {diff_csv} {examples[:6]}, no SolidiFI match: {no_csv}")
    print(f"     local source vs HGT source: same {src_same}, different {src_diff}")
    print(f"     record categories in json: {dict(Counter(v['category'] for r in recs for v in r['vulnerabilities']))}")
    # cleaned sources
    cleaned = base / "cleaned_buggy_curated"
    if cleaned.exists():
        names = sorted(f.name for f in cleaned.glob("*.sol"))
        print(f"  cleaned_buggy_curated: {len(names)} .sol; other files: {[f.name for f in cleaned.iterdir() if f.suffix not in ('.sol', '.dot')][:8]}")
