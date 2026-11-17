"""Dataset A end to end: build each category and check it against two references.

1. The MANDO-LLM authors' released graphs (data/upstream_mando_llm): structure,
   every node and edge attribute and the contract labels must be identical.
2. The Oct 10 public-annotation policy outputs (reference/public_endpoints_verified_v1,
   from the label pipeline on the archive branch): projected annotations, the exact set of nodes
   whose label differs from the authors', and the line-level graph size.

Needs the pinned label sources ($MANDO_DATA_DIR, `python -m hcg fetch`) and a C
compiler for the tree-sitter grammar; skipped otherwise. One category takes
20-60 s; select with -k <category>.
"""
import json
import os
from pathlib import Path

import pytest

from hcg.datasets import DATASET_A
from hcg.pipeline import REPO, build_category
from hcg.sources import repos
from hcg.store import read_gpickle
from hcg.verify import _by_file

LABEL_ROOT = os.environ.get("MANDO_DATA_DIR")
POLICY = Path(__file__).parent / "reference/public_endpoints_verified_v1"
CATEGORIES = [c.name for c in DATASET_A.categories]


def _ready():
    if not LABEL_ROOT:
        return "set MANDO_DATA_DIR to the pinned label sources (python -m hcg fetch)"
    try:
        repos.verify(LABEL_ROOT)
    except SystemExit as exc:
        return str(exc)
    if not (REPO / "data/upstream_mando_llm/graph_detection").is_dir():
        return "authors' reference graphs are not checked out"
    return None


pytestmark = pytest.mark.skipif(_ready() is not None, reason=str(_ready()))


@pytest.fixture(scope="module")
def out_root(tmp_path_factory):
    return tmp_path_factory.mktemp("hcg")


@pytest.mark.parametrize("category", CATEGORIES)
def test_category_reproduces_authors_and_policy(category, out_root):
    manifest = build_category(DATASET_A, category, out_root, LABEL_ROOT, log=lambda *_: None)
    assert manifest["checks"]["failures"] == []
    reference = manifest["checks"]["reference"]
    assert reference["structure_identical"]
    assert reference["attribute_mismatches"] == {} and reference["edge_mismatches"] == 0
    assert reference["contract_label_differences"] == []
    expected = DATASET_A.expected[category]
    assert manifest["contract_level"]["nodes"] == expected["nodes"]
    assert manifest["contract_level"]["edges"] == expected["edges"]

    built = out_root / "A" / category
    policy = POLICY / category
    preprocessed = json.loads((built / "annotations.json").read_text())["preprocessed"]
    assert preprocessed == json.loads((policy / "annotations_preprocessed.json").read_text())

    authors = read_gpickle(DATASET_A.reference(REPO, category)[0])
    position = {n: (f, i) for f, ns in _by_file(authors).items() for i, n in enumerate(ns)}
    old = {position[d["author_node_id"]] + (d["public"],)
           for d in json.loads((policy / "label_differences.json").read_text())}
    new = {(d["source_file"], d["index_in_file"], d["built"])
           for d in reference["label_differences"]}
    assert new == old
    line_ids = json.loads((policy / "line_node_ids.json").read_text())
    assert manifest["line_level"]["nodes"] == len(line_ids)
    assert read_gpickle(built / "line_level.gpickle").number_of_nodes() == len(line_ids)
