"""Dataset B: the committed composition, its assembly and labels.

Unit tests need no data. The tests marked ``sources`` recompose Dataset B from the
pinned sources and build each category; they need $MANDO_DATA_DIR with
`python -m hcg fetch --dataset B --no-models` and a C compiler (about 70 s to
recompose, 10-130 s per category).
"""
import hashlib
import json
import os
import re

import pytest

from hcg.cfg import author_schema
from hcg.datasets import DATASET_A, DATASET_B
from hcg.datasets import dataset_b
from hcg.pipeline import REPO, build_category
from hcg.sources import composition, repos
from hcg.sources.annotations import dappscan_record

DOCUMENT = composition.load(REPO / DATASET_B.composition)
LABEL_ROOT = os.environ.get("MANDO_DATA_DIR")
SOURCES = {"DAppSCAN", "SolidiFI", "SmartBugs-Wild-clean"}


# ------------------------------------------------------------------ the document

def test_document_pins_the_sources_and_the_builder():
    assert DOCUMENT["dataset"] == "B" and DOCUMENT["seed"] == 1
    assert DOCUMENT["sources"] == {n: repos.REPOSITORIES[n][1] for n in DATASET_B.sources}
    assert DOCUMENT["builder"]["cfg_solidity_sha256"] == author_schema.CFG_SOLIDITY_SHA256
    assert DOCUMENT["rules"] == dataset_b.RULES
    assert list(DOCUMENT["categories"]) == [c.name for c in DATASET_B.categories]
    assert DATASET_B.categories == DATASET_A.categories


@pytest.mark.parametrize("category", [c.name for c in DATASET_B.categories])
def test_each_category_is_balanced_unique_and_follows_the_rules(category):
    part = DOCUMENT["categories"][category]
    rows, counts = part["contracts"], part["counts"]
    by_source = {s: [r for r in rows if r["source"] == s] for s in SOURCES}
    assert len({r["name"] for r in rows}) == len(rows) == counts["contracts"]
    assert all(r["target"] == int(r["source"] != "SmartBugs-Wild-clean") for r in rows)
    assert len(by_source["SmartBugs-Wild-clean"]) == counts["vulnerable_contracts"] == counts["clean"]
    assert len(by_source["DAppSCAN"]) == counts["dappscan"] <= counts["dappscan_listed"]
    assert len(by_source["SolidiFI"]) == counts["solidifi"] == 50
    # Table 2's buggy count is the authors' distinct DAppSCAN files plus a full SolidiFI folder
    assert counts["dappscan_listed"] + 50 == DATASET_B.reported[category]["vulnerable_contracts"]
    assert all(re.fullmatch(r"dappscan_[0-9a-f]{10}_.+\.sol", r["name"]) and r["labels"] and
               set(r["swc"]) <= set(part["swc"]) for r in by_source["DAppSCAN"])
    assert all(re.fullmatch(r"buggy_\d+\.sol", r["name"]) for r in by_source["SolidiFI"])
    taken = {r["origin"] for r in rows}
    assert not taken & {e["origin"] for e in part["excluded"]}


# ------------------------------------------------------------------ mechanisms

def _row(tmp_path, name, text, target=1, source="SolidiFI"):
    origin = tmp_path / "src" / name
    origin.parent.mkdir(parents=True, exist_ok=True)
    origin.write_text(text)
    return dict(name=name, source=source, origin="src/" + name, target=target,
                sha256=hashlib.sha256(text.encode()).hexdigest())


def test_assemble_copies_exactly_the_composition_and_checks_hashes(tmp_path):
    rows = [_row(tmp_path, "a.sol", "contract A {}"), _row(tmp_path, "b.sol", "contract B {}", 0)]
    document = {"dataset": "X", "categories": {"c": {"contracts": rows}}}
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "stray.sol").write_text("x")
    assert composition.assemble(document, "c", tmp_path, corpus) == ["a.sol", "b.sol"]
    assert sorted(p.name for p in corpus.glob("*.sol")) == ["a.sol", "b.sol"]
    assert composition.targets(document, "c") == {"a.sol": 1, "b.sol": 0}
    (tmp_path / "src/a.sol").write_text("contract Changed {}")
    (corpus / "a.sol").unlink()
    with pytest.raises(ValueError, match="hash"):
        composition.assemble(document, "c", tmp_path, corpus)


def test_dappscan_record_keeps_the_category_swc_lines_and_unites_copies(tmp_path):
    source = tmp_path / "x.sol"
    source.write_text("\n".join("line %d" % i for i in range(1, 11)))
    first, second = tmp_path / "1.json", tmp_path / "2.json"
    first.write_text(json.dumps({"SWCs": [
        {"category": "SWC-101-Integer Overflow and Underflow", "function": "f", "lineNumber": [3, 4]},
        {"category": "SWC-107-Reentrancy", "function": "g", "lineNumber": [7]}]}))
    second.write_text(json.dumps({"SWCs": [
        {"category": "SWC-101-Integer Overflow and Underflow", "function": "f", "lineNumber": [9]}]}))
    assert dappscan_record([first], source, ["SWC-101"], "arithmetic") == (
        [{"category": "arithmetic", "lines": [3, 4]}], ["SWC-101"])
    assert dappscan_record([first, second], source, ["SWC-101"], "arithmetic")[0][0]["lines"] == [3, 4, 9]
    assert dappscan_record([first], source, ["SWC-104"], "unchecked_low_level_calls") == ([], [])
    second.write_text(json.dumps({"SWCs": [{"category": "SWC-101-x", "lineNumber": [11]}]}))
    with pytest.raises(ValueError, match="invalid line numbers"):
        dappscan_record([second], source, ["SWC-101"], "arithmetic")


def test_seeded_order_is_fixed_and_differs_by_category_and_source():
    names = ["%d.sol" % i for i in range(30)]
    assert dataset_b._order(names, "c", "s", 1) == dataset_b._order(list(reversed(names)), "c", "s", 1)
    assert dataset_b._order(names, "c", "s", 1) != dataset_b._order(names, "d", "s", 1)
    assert dataset_b._order(names, "c", "s", 1) != dataset_b._order(names, "c", "t", 1)


# ------------------------------------------------------------------ from the sources

def _ready():
    if not LABEL_ROOT:
        return "set MANDO_DATA_DIR to the pinned sources (python -m hcg fetch --dataset B)"
    try:
        repos.verify(LABEL_ROOT, DATASET_B.sources)
    except SystemExit as exc:
        return str(exc)
    return None


sources = pytest.mark.skipif(_ready() is not None, reason=str(_ready()))


@sources
def test_recomposing_from_the_pinned_sources_gives_the_committed_document():
    assert dataset_b.compose(LABEL_ROOT, DOCUMENT["seed"], log=lambda *_: None) == DOCUMENT


@sources
@pytest.mark.parametrize("category", [c.name for c in DATASET_B.categories])
def test_build_labels_every_vulnerable_contract(category, tmp_path):
    manifest = build_category(DATASET_B, category, tmp_path, LABEL_ROOT, log=lambda *_: None)
    counts = DOCUMENT["categories"][category]["counts"]
    assert manifest["corpus"]["contracts"] == counts["contracts"]
    assert manifest["corpus"]["vulnerable_contracts"] == counts["vulnerable_contracts"]
    assert manifest["checks"]["failures"] == []
    annotations = json.loads((tmp_path / "B" / category / "annotations.json").read_text())
    vulnerable = [r["name"] for r in DOCUMENT["categories"][category]["contracts"] if r["target"]]
    assert all(annotations["preprocessed"][n] and annotations["preprocessed"][n][0]["lines"] for n in vulnerable)
    assert manifest["contract_level"]["positive_nodes"] > 0
