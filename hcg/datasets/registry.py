"""Datasets and their vulnerability categories.

A dataset says where each category's contracts live, how a contract is assigned its
0/1 target, and (optionally) reference graphs and expected counts to check a build
against. Adding a dataset means adding one Dataset entry; nothing else in the
package is dataset-specific.

Dataset A is MANDO-LLM's seven-category corpus. Each category corpus is half clean
contracts and half vulnerable ones, from two public sources:

    SmartBugs curated  vulnerabilities.json records of that category
    SolidiFI           buggy_N.sol with BugLog_N.csv, in the folder below

The SolidiFI folders were established by hashing every buggy_N.sol of each corpus
against the benchmark; the names do not line up obviously (denial_of_service is
Unhandled-Exceptions, access_control is tx.origin).
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

SOLIDIFI_FILE = re.compile(r"buggy_([0-9]+)\.sol")


@dataclass(frozen=True)
class Category:
    name: str
    solidifi_dir: Optional[str] = None


@dataclass(frozen=True)
class Dataset:
    name: str
    categories: Tuple[Category, ...]
    corpus_dir: str                       # relative to repo; {category} is filled in
    contract_labeler: Callable            # (category, filenames, smartbugs) -> {file: 0/1}
    reference_graph: Optional[str] = None  # relative; {category}; authors' graph to match
    reference_labels: Optional[str] = None
    expected: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def category(self, name):
        for item in self.categories:
            if item.name == name:
                return item
        raise KeyError("dataset %s has no category %r" % (self.name, name))

    def corpus(self, repo, category):
        return Path(repo) / self.corpus_dir.format(category=category)

    def reference(self, repo, category):
        if not self.reference_graph:
            return None, None
        return (Path(repo) / self.reference_graph.format(category=category),
                Path(repo) / self.reference_labels.format(category=category))


def dataset_a_targets(category, filenames, smartbugs):
    """SolidiFI injections and SmartBugs files annotated for the category are 1.

    Reproduces the authors' graph_labels.json for all seven categories exactly; a
    file name alone selects the SmartBugs record (no path), as in their corpus.
    """
    annotated = {
        Path(row["name"]).name for row in smartbugs
        if any(v.get("category") == category for v in row.get("vulnerabilities", []))
    }
    return {name: int(bool(SOLIDIFI_FILE.fullmatch(name)) or name in annotated)
            for name in filenames}


# MANDO-LLM Table 1 (contracts, vulnerable contracts, nodes, edges), as recorded in
# Test_code/author_graph_audit/audit_author_graphs.py::PAPER. A build must match.
_PAPER_A = {
    "access_control": (114, 57, 13432, 15538),
    "arithmetic": (120, 60, 16157, 17591),
    "denial_of_service": (92, 46, 12909, 14366),
    "front_running": (88, 44, 19415, 22278),
    "reentrancy": (142, 71, 18312, 19267),
    "time_manipulation": (100, 50, 15699, 18564),
    "unchecked_low_level_calls": (190, 95, 17525, 20952),
}

DATASET_A = Dataset(
    name="A",
    categories=(
        Category("access_control", "tx.origin"),
        Category("arithmetic", "Overflow-Underflow"),
        Category("denial_of_service", "Unhandled-Exceptions"),
        Category("front_running", "TOD"),
        Category("reentrancy", "Re-entrancy"),
        Category("time_manipulation", "Timestamp-Dependency"),
        Category("unchecked_low_level_calls", "Unchecked-Send"),
    ),
    corpus_dir="experiments/ge-sc-data/source_code/{category}/source_files",
    contract_labeler=dataset_a_targets,
    reference_graph="data/upstream_mando_llm/graph_detection/"
                    "{category}_tree_sitter_cfg_cg_compressed_graphs.gpickle",
    reference_labels="data/upstream_mando_llm/graph_detection/{category}_graph_labels.json",
    expected={name: dict(zip(("contracts", "vulnerable_contracts", "nodes", "edges"), row))
              for name, row in _PAPER_A.items()},
)

DATASETS = {DATASET_A.name: DATASET_A}


def get_dataset(name):
    try:
        return DATASETS[name]
    except KeyError:
        raise SystemExit("unknown dataset %r; known: %s" % (name, sorted(DATASETS)))
