"""Read-only: is Dataset B (SolidiFI + DAppSCAN + clean) available locally or on the authors' Drive?

    python -B Test_code/dataset_check/check_dataset_b.py
"""
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent
UP = REPO / "data/upstream_mando_llm"

print("== local directories / files whose name mentions DAppSCAN or dataset B")
hits = []
for base in (REPO, ROOT / "ge-sc-transformer"):
    for p in base.rglob("*"):
        name = p.name.lower()
        if any(k in name for k in ("dappscan", "dapp_scan", "dataset_b", "datasetb", "swc")):
            hits.append(p)
for p in hits[:40]:
    print("  ", p.relative_to(ROOT))
print("   total:", len(hits))

print("\n== names listed in the saved Drive folder pages")
for html in sorted(UP.glob("*.html")):
    text = html.read_text(errors="ignore")
    files = sorted(set(re.findall(r"[A-Za-z0-9_\-]+\.(?:gpickle|json|pth|pt|pkl|zip|tar|gz|csv)", text)))
    folders = sorted(set(re.findall(r'"([A-Za-z0-9_\- ]{3,40})","application/vnd\.google-apps\.folder"', text)))
    lowered = text.lower()
    print(f"  {html.name}: {len(files)} file names; mentions dappscan={('dappscan' in lowered)} "
          f"dataset_b={bool(re.search(r'dataset[ _-]?b', lowered))} swc={('swc' in lowered)}")
    print("     folders:", folders[:20])
    kinds = Counter(re.sub(r"^(access_control|arithmetic|denial_of_service|front_running|reentrancy|time_manipulation|unchecked_low_level_calls)", "<bug>", f) for f in files)
    for k, c in sorted(kinds.items()):
        print(f"       {c:2d} x {k}")

print("\n== repository references")
for pattern in ("DAppSCAN", "dappscan", "Dataset B", "dataset_b", "SWC"):
    out = subprocess.run(["git", "-C", str(REPO), "grep", "-n", "-I", pattern, "HEAD", "--", "*.py", "*.md", ".gitignore"],
                         capture_output=True, text=True).stdout.splitlines()
    print(f"  '{pattern}': {len(out)} lines")
    for line in out[:8]:
        print("     ", line[:170])

print("\n== per-bug-type contract counts available locally vs paper Table 2 (Dataset B)")
paper_b = {"access_control": (244, 122), "arithmetic": (372, 186), "denial_of_service": (316, 158),
           "front_running": (252, 126), "reentrancy": (326, 163), "time_manipulation": (172, 86),
           "unchecked_low_level_calls": (246, 123)}
for bug, (total, buggy) in paper_b.items():
    base = REPO / "experiments/ge-sc-data/source_code" / bug
    subs = {d.name: sum(1 for _ in d.glob("*.sol")) for d in base.iterdir() if d.is_dir()}
    print(f"  {bug:26s} paper B {total}/{buggy}   local .sol per folder: {subs}")
