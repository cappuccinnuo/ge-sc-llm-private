"""CP7: K1-K3 knowledge, exact-then-BM25 retrieval and leave-one-project (PROMPTS 3.4, 4.7)."""
import hashlib
import json

import pytest

from compile_repair.evaluation.report import choose_k, hit_rates, k1_correct, receipt_queries, retrieval_hits
from compile_repair.rag.knowledge import (Entry, KnowledgeBase, documentation_entries, documented_terms,
    library_entries, message_template, repair_entries, rst_sections, split_first_line, template_terms)
from compile_repair.rag.retrieve import Query, retrieve, tokens

LAYOUT = """\
********************************
Layout of a Solidity Source File
********************************

Source files contain contract definitions and pragma directives.

.. index:: ! pragma, version

Version Pragma
==============

Source files can be annotated with a version pragma::

  pragma solidity ^0.4.0;

Importing other Source Files
============================

Paths
-----

An import path names another source unit.
"""
BREAKING = """\
Solidity v0.5.0 Breaking Changes
================================

Deprecated Elements
-------------------

* The function ``sha3`` is disallowed. Use ``keccak256`` instead.
* Function visibility is now mandatory; ``public`` must be given.

Example
-------

.. code-block:: solidity

  pragma solidity >=0.5.0;
  contract MyExample { function f() public {} }
"""
NATSPEC = """\
NatSpec Format
==============

Tags
----

``@param`` documents a parameter (followed by the parameter name).
"""


@pytest.fixture
def docs(tmp_path):
    for version, files in {"0.4.26": {"layout-of-source-files.rst": LAYOUT},
                           "0.5.17": {"layout-of-source-files.rst": LAYOUT, "050-breaking-changes.rst": BREAKING,
                                      "natspec-format.rst": NATSPEC}}.items():
        for name, text in files.items():
            path = tmp_path / "docs" / version / "docs" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf8")
    return tmp_path / "docs"


def test_rst_sections_follow_heading_levels():
    sections = rst_sections(LAYOUT)
    assert [chain for chain, _ in sections] == [
        ("Layout of a Solidity Source File",), ("Layout of a Solidity Source File", "Version Pragma"),
        ("Layout of a Solidity Source File", "Importing other Source Files", "Paths")]


def test_identical_sections_share_one_entry_with_their_versions(docs):
    entries = documentation_entries(docs)
    pragma = [e for e in entries if e.title.endswith("Version Pragma")]
    assert len(pragma) == 1 and pragma[0].versions == ("0.4.26", "0.5.17")
    breaking = [e for e in entries if e.payload["path"] == "050-breaking-changes.rst"]
    assert all(e.versions == ("0.5.17",) for e in breaking)
    # Example boilerplate does not make every section about "pragma".
    example = next(e for e in breaking if e.title.endswith("Example"))
    assert "pragma" not in tokens(example.text)


def test_templates_keep_documented_terms_and_hide_identifiers(docs):
    vocabulary = documented_terms(documentation_entries(docs))
    assert {"sha3", "keccak256", "public"} <= vocabulary and "MyExample" not in vocabulary
    template = message_template('"sha3" has been deprecated in favour of "keccak256"', vocabulary)
    assert template == '"sha3" has been deprecated in favour of "keccak256"'
    assert template_terms(template) == ["keccak256", "sha3"]
    assert message_template('Documented parameter "amountIn" not found.', vocabulary) == \
        'Documented parameter "<id>" not found.'
    assert message_template('Type "uint256" is not convertible to "bool" at 0x1f in 0.5.17.', vocabulary) == \
        'Type "uint256" is not convertible to "bool" at <hex> in <version>.'


@pytest.mark.parametrize("line,expected", [
    ("a/b.sol:68:1: Error: Identifier already declared.", ("Error", "Identifier already declared.")),
    ("ParserError: Expected ';' but got '}'", ("ParserError", "Expected ';' but got '}'")),
    ("Compiler error: Stack too deep", ("Compiler error", "Stack too deep")),
    ("F: unsupported pragma expression", ("F", "unsupported pragma expression")),
    ("file_not_found", (None, "file_not_found")),
])
def test_first_lines_split_into_kind_and_message(line, expected):
    assert split_first_line(line) == expected


def test_k1_exact_terms_come_first_and_respect_the_version(docs):
    kb = KnowledgeBase(documentation_entries(docs))
    hits = retrieve(kb, Query(errors=('Error: "sha3" has been deprecated in favour of "keccak256"',),
                              version="0.5.17"), 3, ("K1",))["K1"]
    assert hits[0].match == "exact" and "050-breaking-changes.rst" in hits[0].entry_id
    old = retrieve(kb, Query(errors=('Error: "sha3" has been deprecated',), version="0.4.26"), 3, ("K1",))["K1"]
    assert all("050-breaking-changes" not in h.entry_id for h in old)


def test_version_reader_errors_find_the_version_pragma(docs):
    kb = KnowledgeBase(documentation_entries(docs))
    entries = {e.entry_id: e for e in kb.entries}
    hits = retrieve(kb, Query(errors=("F: unterminated pragma directive",), version="0.4.26"), 1, ("K1",))["K1"]
    assert entries[hits[0].entry_id].title.endswith("Version Pragma")


def _index(tmp_path):
    files = {"contracts/math/SafeMath.sol": dict(
        sha256="a" * 64, size=1, pragma=dict(interval=[[0, 5, 0], [0, 6, 0]], unsupported=None), imports=[],
        declarations=["SafeMath"], function_signatures=["add(uint256 a , uint256 b)"]),
        "contracts/ownership/Ownable.sol": dict(
        sha256="b" * 64, size=1, pragma=dict(interval=[[0, 4, 24], [0, 5, 0]], unsupported=None), imports=[],
        declarations=["Ownable"], function_signatures=["transferOwnership(address newOwner)"])}
    body = json.dumps(dict(schema="compile-repair-dependencies-v1", packages={"openzeppelin-solidity": {
        "2.3.0": dict(path="files/x", files=files)}})).encode()
    (tmp_path / "index.json").write_bytes(body)
    (tmp_path / "seal.json").write_text(json.dumps(dict(schema="compile-repair-dependencies-v1",
                                                         index_sha256=hashlib.sha256(body).hexdigest())))
    return tmp_path


def test_k2_symbols_and_import_paths_are_exact_keys(tmp_path):
    kb = KnowledgeBase(library_entries(_index(tmp_path)), vocabulary=frozenset())
    path = retrieve(kb, Query(import_paths=("openzeppelin-solidity/contracts/math/SafeMath.sol",)), 2, ("K2",))["K2"]
    assert path[0].match == "exact" and path[0].entry_id.endswith("contracts/math/SafeMath.sol")
    symbol = retrieve(kb, Query(symbols=("Ownable",), version="0.4.26"), 2, ("K2",))["K2"]
    assert symbol[0].entry_id.endswith("Ownable.sol")
    # The pragma interval of a library file must admit the query version.
    assert retrieve(kb, Query(symbols=("Ownable",), version="0.5.17"), 2, ("K2",))["K2"] == []
    (tmp_path / "index.json").write_bytes(b"{}")
    with pytest.raises(ValueError):
        library_entries(tmp_path)


def _repair(unit, group, message, step="stub"):
    stderr = "A.sol:1:1: DeclarationError: " + message + "\n"
    environment = dict(attempts=[dict(version="0.5.17", solc=dict(returncode=1, timed_out=False, stderr=stderr))])
    final = dict(status="success", unit_id=unit, selected_version="0.5.17", provenance={"A.sol": dict(changes=[
        dict(step=step, reason="member stubs", old=dict(encoding="hex", data=""),
             new=dict(encoding="hex", data=b"modifier m() { _; }".hex()))])})
    return group, environment, final


def test_k3_leaves_the_queried_project_out(tmp_path):
    records = [_repair("u1", "P1", 'Undeclared identifier "onlyOwner".'),
               _repair("u2", "P2", 'Undeclared identifier "onlyAdmin".'),
               _repair("u3", "P1", 'Identifier not found "Base".')]
    kb = KnowledgeBase(repair_entries(records, frozenset()), vocabulary=frozenset())
    assert all(e.group for e in kb.entries) and len(kb.entries) == 3
    query = Query(errors=('DeclarationError: Undeclared identifier "x".',), group="P1")
    hits = retrieve(kb, query, 5, ("K3",))["K3"]
    groups = {e.entry_id: e.group for e in kb.entries}
    assert hits and {groups[h.entry_id] for h in hits} == {"P2"} and hits[0].match == "exact"
    with pytest.raises(ValueError):
        retrieve(kb, Query(errors=query.errors), 5, ("K3",))
    # K3 keeps no labels: only the repair, its errors and the version.
    assert set(kb.entries[0].payload) == {"unit_id", "version", "errors", "changes"}


def test_failed_or_unchanged_records_are_not_memory():
    group, environment, final = _repair("u1", "P1", "Undeclared identifier.")
    assert repair_entries([(group, environment, dict(final, status="unrepaired"))], frozenset()) == []
    assert repair_entries([(group, environment, dict(final, provenance={}))], frozenset()) == []
    assert repair_entries([(None, environment, final)], frozenset()) == []


def test_store_round_trip_and_seal(docs, tmp_path):
    kb = KnowledgeBase(documentation_entries(docs) + [Entry("K3", "K3:x", "t", "text", ("category:stub",), group="P")])
    kb.save(tmp_path / "kb")
    loaded = KnowledgeBase.load(tmp_path / "kb")
    assert loaded.entries == kb.entries and loaded.vocabulary == kb.vocabulary
    raw = (tmp_path / "kb" / "entries.jsonl").read_bytes()
    (tmp_path / "kb" / "entries.jsonl").write_bytes(raw.replace(b"Pragma", b"Pragmo", 1))
    with pytest.raises(ValueError):
        KnowledgeBase.load(tmp_path / "kb")
    with pytest.raises(ValueError):
        KnowledgeBase([Entry("K1", "a", "", ""), Entry("K1", "a", "", "")], vocabulary=())


def test_benchmark_truth_rates_and_k(docs):
    kb = KnowledgeBase(documentation_entries(docs))
    receipts = [dict(outcome="included", mutation_sha256=str(i), unit_id="u%d" % i, operator=op, split=split,
                     group="g%d" % i, series=series, selected_first_line=line, environment_categories=[op])
                for i, (op, split, series, line) in enumerate([
                    ("unterminated_pragma", "dev", "0.4", "F: unterminated pragma directive"),
                    ("docstring_error", "dev", "0.5", 'Error: Documented parameter "y" not found.'),
                    ("docstring_error", "test", "0.5", 'Error: Documented parameter "z" not found.'),
                    ("parser_error_other", "test", "0.5", "Error: Expected identifier but got ','")])]
    samples = receipt_queries(receipts, ["0.4.26", "0.5.17"])
    assert [s["query"].version for s in samples] == ["0.4.26", "0.5.17", "0.5.17", "0.5.17"]
    scored = [s for s in samples if s["operator"] != "parser_error_other"]  # no K1 truth
    ranks = retrieval_hits(kb, scored, lambda e, s: k1_correct(e, s["operator"]), "K1", 3)
    assert all(r["rank"] == 1 for r in ranks)
    rates = hit_rates(ranks + [dict(operator="x", split="dev", rank=None)], (1, 3))
    assert rates["all"]["dev"] == {"samples": 3, "hit@1": 0.6667, "hit@3": 0.6667}
    assert choose_k({"all": {"dev": {"hit@1": 0.5, "hit@3": 0.79, "hit@5": 0.8}}}, (1, 3, 5)) == 3
