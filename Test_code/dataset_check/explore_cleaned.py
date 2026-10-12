"""Read-only: what are the authors' cleaned_buggy_curated sources, and do they explain the labels?

    python -B Test_code/dataset_check/explore_cleaned.py
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HGT = REPO.parent / "ge-sc-transformer"
SRC = REPO / "experiments/ge-sc-data/source_code"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from line_mapping import build_line_map  # noqa: E402
from process_graphs.tree_sitter_codeviews.utils import preprocessor  # noqa: E402


def preprocess(text):
    text = preprocessor.remove_empty_lines(text)
    return preprocessor.remove_comments("solidity", text)


sb_local = json.load(open(REPO / "data/smartbug-dataset/vulnerabilities.json"))
sb_hgt = json.load(open(HGT / "data/smartbug-dataset/vulnerabilities.json"))
a = {r["name"]: r for r in sb_local}
b = {r["name"]: r for r in sb_hgt}
print("smartbugs json: only local", sorted(set(a) - set(b))[:5], "only HGT", sorted(set(b) - set(a))[:5])
for name in sorted(set(a) & set(b)):
    if a[name]["vulnerabilities"] != b[name]["vulnerabilities"]:
        print("  differs:", name, a[name]["vulnerabilities"], "| HGT:", b[name]["vulnerabilities"])
print("  other key differences:", sum(a[n] != b[n] for n in set(a) & set(b)))

for bug, name in (("reentrancy", "buggy_18.sol"), ("reentrancy", "buggy_19.sol"), ("reentrancy", "buggy_20.sol"),
                  ("access_control", "buggy_18.sol"), ("access_control", "buggy_26.sol"),
                  ("denial_of_service", "buggy_18.sol"), ("front_running", "buggy_18.sol")):
    src = SRC / bug / "source_files" / name
    cleaned = SRC / bug / "cleaned_buggy_curated" / name
    text = src.read_text(encoding="utf8")
    pre = preprocess(text)
    pre_lines = [l for l in pre.split("\n") if l.strip() != ""]
    print("=" * 80)
    print(bug, name, "orig lines", len(text.split("\n")), "our preprocessed non-blank lines", len(pre_lines),
          "line_map len", len(build_line_map(text)))
    if cleaned.exists():
        ctext = cleaned.read_text(encoding="utf8", errors="ignore")
        clines = ctext.split("\n")
        print("  cleaned file lines", len(clines), "non-blank", sum(1 for l in clines if l.strip()),
              "== our preprocessed text:", ctext.strip() == pre.strip(),
              "== original:", ctext == text)
        if ctext.strip() != pre.strip():
            for i, (x, y) in enumerate(zip(clines, pre.split("\n")), 1):
                if x != y:
                    print(f"  first diff at line {i}: cleaned {x[:70]!r} | ours {y[:70]!r}")
                    break
    else:
        print("  no cleaned file")

dot = SRC / "reentrancy/cleaned_buggy_curated/buggy_18.dot"
print("\n--- head of", dot.name)
print(dot.read_text(errors="ignore")[:1500])
csvp = SRC / "reentrancy/cleaned_buggy_curated/func_sol_dataset.csv"
print("\n--- head of", csvp.name)
print(csvp.read_text(errors="ignore")[:600])
