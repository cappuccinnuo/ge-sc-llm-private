"""Tests for the seven-category graph build (scripts/graph_build).

The synthetic test runs every stage on a three-contract corpus with hand-written
labels and a stub tokenizer, so it needs tree-sitter (and a C compiler for the
grammar) but no network. The registry tests check the real corpus; the label-source
test additionally needs $MANDO_DATA_DIR (scripts/fetch_vuln_labels.sh) and is
skipped without it.
"""
import csv
import json
import os
from pathlib import Path

import pytest

from scripts.graph_build.nx_io import read_gpickle, write_gpickle
from scripts.graph_build.categories import CATEGORIES, PAPER, BASELINE, Category, expected

REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "experiments/ge-sc-data/source_code"

BANK = """pragma solidity ^0.4.24;
contract Bank {
    mapping(address => uint) balances;
    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }
    function withdraw() public {
        msg.sender.call.value(balances[msg.sender])();
        balances[msg.sender] = 0;
    }
}
"""
INJECTED = """pragma solidity ^0.4.24;
contract Lottery {
    uint public pot;
    function play() public payable {
        if (block.timestamp % 2 == 0) {
            msg.sender.transfer(pot);
        }
        pot += msg.value;
    }
}
"""
CLEAN = """pragma solidity ^0.4.24;
contract Counter {
    uint public count;
    function increment() public {
        count += 1;
    }
}
"""


class StubTokenizer:
    """Enough of a HuggingFace tokenizer for encode_node_tokens: one id per char."""
    pad_token_id = 0
    eos_token_id = 1
    vocab_size = 300

    class _Out:
        def __init__(self, ids):
            self.input_ids = ids

    def __call__(self, code, add_special_tokens=True):
        return self._Out([2 + (ord(c) % 250) for c in code] + [self.eos_token_id])


@pytest.fixture
def toy_corpus(tmp_path):
    dataset = tmp_path / "dataset"
    src = dataset / "toy" / "source_files"
    src.mkdir(parents=True)
    (src / "bank.sol").write_text(BANK)
    (src / "buggy_1.sol").write_text(INJECTED)
    (src / "counter.sol").write_text(CLEAN)

    labels = tmp_path / "labels"
    (labels / "smartbug-dataset").mkdir(parents=True)
    (labels / "smartbug-dataset/vulnerabilities.json").write_text(json.dumps([
        {"name": "bank.sol", "path": "dataset/toy/bank.sol",
         "vulnerabilities": [{"lines": [8], "category": "toy"}]},
    ]))
    buglogs = labels / "SolidiFI-benchmark/buggy_contracts/Toy-Bug"
    buglogs.mkdir(parents=True)
    with open(buglogs / "BugLog_1.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["loc", "length", "bug type", "approach"])
        w.writerow([5, 3, "toy", "code snippet injection"])
    return dataset, labels


def test_nx_io_roundtrip_uses_protocol_4(tmp_path):
    import networkx as nx
    g = nx.MultiDiGraph()
    g.add_edge(0, 1, edge_type="next")
    path = tmp_path / "g.gpickle"
    write_gpickle(g, path)
    assert path.read_bytes()[:2] == b"\x80\x04"  # readable by the Python 3.7 env
    back = read_gpickle(path)
    assert list(back.edges(data=True)) == [(0, 1, {"edge_type": "next"})]


def test_toy_category_builds_every_stage(toy_corpus, tmp_path):
    pytest.importorskip("tree_sitter")
    from scripts.graph_build.pipeline import build_category, check_expected

    dataset, labels = toy_corpus
    out = tmp_path / "out"
    report = build_category(Category("toy", "Toy-Bug", 3), labels, out_root=out,
                            dataset_root=dataset, tokenizer=StubTokenizer(),
                            tokenizer_name="stub/tok", log=lambda *_: None)

    assert report["parse_failures"] == []
    assert report["annotation_records"] == {"smartbugs": 1, "solidifi": 1}
    cl = report["contract_level"]
    assert (cl["contracts"], cl["buggy_contracts"]) == (3, 2)
    assert cl["annotated_but_no_node_hit"] == []
    assert report["graph_labels"] == {"buggy": 2, "clean": 1}
    assert check_expected(report, {"contracts": 3, "buggy_contracts": 2}) == []
    assert check_expected(report, {"contracts": 4}) == ["contracts: expected 4, got 3"]

    d = out / "toy"
    entries = json.loads((d / "graph_labels.json").read_text())
    assert entries == [{"contract_name": "bank.sol", "targets": 1},
                       {"contract_name": "buggy_1.sol", "targets": 1},
                       {"contract_name": "counter.sol", "targets": 0}]

    full = read_gpickle(d / "hcg_compressed_graphs.gpickle")
    hit = [n for n, x in full.nodes(data=True)
           if x["source_file"] == "bank.sol" and x.get("node_info_vulnerabilities")]
    assert hit and all(8 in full.nodes[n]["node_source_code_lines_original"] for n in hit)
    assert not any(x.get("node_info_vulnerabilities") for _, x in full.nodes(data=True)
                   if x["source_file"] == "counter.sol")

    line = read_gpickle(d / "linelevel_hcg.gpickle")
    assert {x["source_file"] for _, x in line.nodes(data=True)} == {"bank.sol", "buggy_1.sol"}
    assert sorted(line.nodes()) == list(range(line.number_of_nodes()))

    tok = read_gpickle(d / "tokenizer_ids_tok_hcg_compressed_graphs.gpickle")
    widths = {x["token"].shape for _, x in tok.nodes(data=True)}
    assert widths == {(512,)}
    line_tok = read_gpickle(d / "linelevel_tokenizer_ids.gpickle")
    assert line_tok.number_of_nodes() == line.number_of_nodes()
    assert report["tokens"]["feature_size"] == 512


def test_registry_matches_corpus_and_classifier():
    assert sorted(CATEGORIES) == sorted(p.name for p in DATASET.iterdir()
                                        if (p / "source_files").is_dir())
    for c in CATEGORIES.values():
        assert len(list((DATASET / c.name / "source_files").glob("*.sol"))) == c.contracts
        assert PAPER[c.name][0] == c.contracts
        assert PAPER[c.name][1] * 2 == c.contracts  # every corpus is 1 : 1
        assert set(expected(c.name)) == {"contracts", "buggy_contracts", "nodes", "edges",
                                         "buggy_nodes", "line_nodes"}
    assert set(BASELINE) == set(CATEGORIES)
    pytest.importorskip("torch")
    from sco_models.classifier_cli import BUG_TYPES
    assert set(BUG_TYPES) >= set(CATEGORIES)


@pytest.mark.skipif(not os.environ.get("MANDO_DATA_DIR"),
                    reason="needs label sources: MANDO_DATA_DIR + scripts/graph_build/fetch_labels.sh")
def test_every_injected_contract_has_a_buglog_in_its_solidifi_folder():
    import hashlib
    root = Path(os.environ["MANDO_DATA_DIR"]) / "SolidiFI-benchmark/buggy_contracts"
    for c in CATEGORIES.values():
        folder = root / c.solidifi_dir
        digests = {hashlib.sha1(p.read_bytes()).hexdigest()
                   for p in folder.glob("buggy_*.sol")}
        injected = sorted((DATASET / c.name / "source_files").glob("buggy_*.sol"))
        assert injected, c.name
        for p in injected:
            assert hashlib.sha1(p.read_bytes()).hexdigest() in digests, (c.name, p.name)
            assert (folder / f"BugLog_{p.stem.split('_')[-1]}.csv").exists(), (c.name, p.name)


def test_grammar_dir_is_per_platform_and_not_the_checked_in_macos_library(monkeypatch):
    from scripts.graph_build import pipeline
    monkeypatch.delenv("TREE_SITTER_LIB_DIR", raising=False)
    pipeline.use_platform_grammar()
    lib_dir = Path(os.environ["TREE_SITTER_LIB_DIR"])
    assert lib_dir == pipeline.grammar_dir()
    assert lib_dir.parent == REPO / "build"  # git-ignored, the old machine's convention
    shipped = REPO / "process_graphs/tree_sitter_codeviews/build/my-languages.so"
    assert lib_dir / "my-languages.so" != shipped


def test_edge_sem_frozen_sources_still_match():
    """edge_sem/hgt_edge.py refuses to import if these files change; keep them intact."""
    import ast
    import hashlib
    tree = ast.parse((REPO / "scripts/edge_sem/hgt_edge.py").read_text())
    frozen = next(ast.literal_eval(node.value) for node in ast.walk(tree)
                  if isinstance(node, ast.Assign)
                  and any(getattr(t, "id", None) == "FROZEN_SOURCES" for t in node.targets))
    assert "sco_models/model_hgt.py" in frozen
    for name, sha in frozen.items():
        assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == sha, name
