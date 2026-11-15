"""The seven Dataset A categories and where their line annotations come from.

Every category corpus under experiments/ge-sc-data/source_code/<name>/source_files
is half clean contracts (SmartBugs-wild 0x... files with no annotation) and half
buggy ones, drawn from two sources:

  SmartBugs curated  dataset/<name>/*.sol, labelled by vulnerabilities.json
  SolidiFI injected  buggy_contracts/<solidifi_dir>/buggy_N.sol, labelled by BugLog_N.csv

The SolidiFI folder for each category was established by hashing every buggy_N.sol
in the corpus against the SolidiFI benchmark: all 40-45 files of each category
match files in exactly one SolidiFI folder (in every category two of them have a
byte-identical twin inside that same folder). The names do not line up obviously - denial_of_service is
Unhandled-Exceptions, access_control is tx.origin - so do not "fix" them by name.

As upstream, labelling applies no category filter: any SmartBugs record for a file
counts, whatever its category string.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    name: str
    solidifi_dir: str
    contracts: int  # .sol files in source_files/, the paper's corpus size


CATEGORIES = {
    c.name: c
    for c in (
        Category("access_control", "tx.origin", 114),
        Category("arithmetic", "Overflow-Underflow", 120),
        Category("denial_of_service", "Unhandled-Exceptions", 92),
        Category("front_running", "TOD", 88),
        Category("reentrancy", "Re-entrancy", 142),
        Category("time_manipulation", "Timestamp-Dependency", 100),
        Category("unchecked_low_level_calls", "Unchecked-Send", 190),
    )
}

# PAPER: MANDO-LLM Table 1 / Appendix C, as recorded in
# Test_code/author_graph_audit/audit_author_graphs.py::PAPER (contracts, buggy
# contracts, nodes, edges). Independent of this code; a rebuild must match exactly.
# The paper's buggy-node column is NOT checked: its labelling is narrower than the
# one reconstructed here (HANDOVER.md section 4: reentrancy 6570 vs 6978).
PAPER = {
    "access_control": (114, 57, 13432, 15538),
    "arithmetic": (120, 60, 16157, 17591),
    "denial_of_service": (92, 46, 12909, 14366),
    "front_running": (88, 44, 19415, 22278),
    "reentrancy": (142, 71, 18312, 19267),
    "time_manipulation": (100, 50, 15699, 18564),
    "unchecked_low_level_calls": (190, 95, 17525, 20952),
}

# BASELINE: this pipeline's own first full build (2026-11-15, Python 3.11,
# networkx 3, label sources at the commits pinned in scripts/fetch_vuln_labels.sh).
# A regression lock, not ground truth: (buggy nodes, line-level nodes). Reentrancy's
# pair also equals the documented earlier rebuild (HANDOVER.md sections 3-4).
BASELINE = {
    "access_control": (3236, 7710),
    "arithmetic": (5881, 10469),
    "denial_of_service": (4238, 8364),
    "front_running": (11001, 15138),
    "reentrancy": (6978, 12036),
    "time_manipulation": (6151, 10639),
    "unchecked_low_level_calls": (2714, 9332),
}


def expected(name):
    """{metric: value} a rebuild of this category must reproduce."""
    out = {}
    if name in PAPER:
        out.update(zip(("contracts", "buggy_contracts", "nodes", "edges"), PAPER[name]))
    if name in BASELINE:
        out.update(zip(("buggy_nodes", "line_nodes"), BASELINE[name]))
    return out


def resolve(names):
    """Category objects for a list of names, or all seven for None / ["all"]."""
    if not names or names == ["all"]:
        return list(CATEGORIES.values())
    unknown = [n for n in names if n not in CATEGORIES]
    if unknown:
        raise SystemExit(f"unknown categories {unknown}; choose from {sorted(CATEGORIES)}")
    return [CATEGORIES[n] for n in names]
