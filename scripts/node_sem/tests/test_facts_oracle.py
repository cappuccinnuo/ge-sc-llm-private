"""Independent semantic Oracle; expected.json predates extractor assertions.

AST-only checks use original source. Sealed L1/L2/semantic-CFG facts are
explicitly separate: the graph integration suite owns those positive claims.
No expected values are obtained from production extractors.
"""
import json
import re
from pathlib import Path

import pytest

from scripts.node_sem.facts_schema import validate

FIXTURES = Path(__file__).parent / "fixtures" / "nodesem_oracle"
MANIFEST = json.loads((FIXTURES / "expected.json").read_text(encoding="utf8"))


def values_at(value, parts):
    """Traverse mappings; flatten list intermediates, preserving terminal lists."""
    if not parts:
        return value
    if isinstance(value, list):
        result = []
        for item in value:
            val = values_at(item, parts)
            result.extend(val if isinstance(val, list) else [val])
        return result
    return values_at(value[parts[0]], parts[1:])


def sealed_evidence_required(path, expected):
    if path.startswith(("dfg.", "state.")):
        return True
    if path.startswith("order.") and path != "order.ext_call_in_loop":
        return True
    if path in ("state_decl.write_functions", "state_decl.read_functions",
                "state_decl.unguarded_writer", "state_decl.unguarded_write_functions",
                "fn_summary.state_write"):
        return True
    return path == "arith.sinks" and "guard" in expected


def compact(text):
    return re.sub(r"\s+", "", text)


def choose(rows, audit_rows, check):
    matches = []
    expected = compact(check["text"])
    for key, facts in rows.items():
        row = audit_rows[key]
        if check.get("node_kind") and facts["node_kind"] != check["node_kind"]:
            continue
        if check.get("function") and row.get("function") != check["function"]:
            continue
        actual = compact(row["text"])
        if actual == expected or (facts["node_kind"] in ("function", "modifier", "contract") and actual.startswith(expected)):
            matches.append((key, facts))
    assert len(matches) == 1, "selector %r matched %r" % (check, [m[0] for m in matches])
    return matches[0][1]


def assert_subset(actual, expected):
    assert isinstance(actual, list), repr(actual)
    for value in expected:
        assert value in actual, "%r not in %r" % (value, actual)


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda c: c["id"])
def test_handwritten_ast_oracle(case):
    from scripts.node_sem.facts import extract_source
    source = (FIXTURES / case["source"]).read_text(encoding="utf8")
    rows, audit = extract_source(source, file=case["source"])
    assert rows
    assert all(f["provenance"]["view"] == "original" for f in rows.values())
    assert case["validation"] == "parser_only_not_compiled"
    for facts in rows.values():
        validate(facts)
        if facts["dfg"]:
            assert facts["dfg"]["status"] == "unknown"
        if facts["order"]:
            assert facts["order"]["status"] == "unknown"
    for check in case["checks"]:
        facts = choose(rows, audit["rows"], check)
        for path, expected in check.get("equals", {}).items():
            if not sealed_evidence_required(path, expected):
                assert values_at(facts, path.split(".")) == expected, (case["id"], path, facts)
        for path, expected in check.get("contains", {}).items():
            if not sealed_evidence_required(path, expected):
                assert_subset(values_at(facts, path.split(".")), expected)
        for path, expected in check.get("absent", {}).items():
            if not sealed_evidence_required(path, expected):
                actual = values_at(facts, path.split("."))
                assert all(x not in actual for x in expected), (case["id"], path, actual)


def test_oracle_comparison_helper_is_not_vacuous():
    with pytest.raises(AssertionError):
        assert_subset(["env_state"], ["env_param"])
    assert values_at({"guards": [{"eq_pairs": ["env_state"]}, {"eq_pairs": []}]}, ["guards", "eq_pairs"]) == ["env_state"]


def test_historical_spelling_normalization_does_not_emit_version_features():
    from scripts.node_sem.facts import extract_source
    by_id = {c["id"]: c for c in MANIFEST["cases"]}
    old_case, new_case = by_id["gg"], by_id["gg_modern"]
    old_rows, old_audit = extract_source((FIXTURES / old_case["source"]).read_text(encoding="utf8"), file="old.sol")
    new_rows, new_audit = extract_source((FIXTURES / new_case["source"]).read_text(encoding="utf8"), file="new.sol")
    fields = [
        ("env.keys",), ("syntax",),
        ("external.kinds", "external.value_attached", "external.value_class"),
        ("external.kinds",), ("syntax",),
    ]
    for old_check, new_check, paths in zip(old_case["checks"], new_case["checks"], fields):
        old = choose(old_rows, old_audit["rows"], old_check)
        new = choose(new_rows, new_audit["rows"], new_check)
        for path in paths:
            assert values_at(old, path.split(".")) == values_at(new, path.split("."))
    assert "compiler_version" not in old_rows[next(iter(old_rows))]
