"""Contract tests authored independently of extraction algorithms."""
import copy
import json

import pytest

from scripts.node_sem.facts_schema import (
    APPLICABILITY, ENV_KEYS, NODE_KINDS, new_facts, validate,
)


@pytest.mark.parametrize("kind", NODE_KINDS)
def test_all_node_kinds_have_json_safe_complete_independent_defaults(kind):
    value = new_facts(kind)
    assert validate(value) is value
    assert json.loads(json.dumps(value)) == value
    for group, kinds in APPLICABILITY.items():
        assert bool(value[group]) == (kind in kinds)
    value["names"].append("example")
    assert new_facts(kind)["names"] == []


def test_unknown_analysis_is_not_false_support():
    f = new_facts("statement")
    for group in ("dfg", "state", "order"):
        assert f[group]["status"] == "unknown"
    f["order"]["status"] = "supported"
    assert validate(f)["order"]["reachable_from_ext_call"] is False


def test_only_original_view_is_a_production_contract():
    f = new_facts("statement")
    f["provenance"]["view"] = "anonymous"
    with pytest.raises(ValueError, match="provenance.view"):
        validate(f)


@pytest.mark.parametrize("path,value", [
    (("external", "kinds"), ["invented"]),
    (("external", "kinds"), ["call", "call"]),
    (("external", "value_attached"), 1),
    (("external", "value_class"), "bad"),
    (("external", "data_class"), "bad"),
    (("external", "target_classes"), ["owner"]),
    (("external", "return_handling"), "ignored"),
    (("state", "status"), "false"),
    (("state", "reads"), [{"var": "x", "shape": "mapping", "auth": 0}]),
    (("dfg", "defs"), [{"var": "x", "kind": "local", "from_offset": True}]),
    (("dfg", "from"), [{"node": "n", "offset": "1"}]),
    (("dfg", "to"), [{"node": "n", "offset": 1, "sink": "bad"}]),
    (("env", "keys"), ["now"]),
    (("env", "uses"), ["anything"]),
    (("arith", "ops"), ["and"]),
    (("loop", "bound"), "-"),
    (("function_ctx", "visibility"), "protected"),
    (("syntax",), ["custom"]),
    (("unresolved",), {"reason": 0}),
    (("names",), ["x", "x"]),
    (("provenance", "source_sha256"), "abc"),
    (("provenance", "store_refs"), [{"path": "x", "sha256": "not sha"}]),
])
def test_malformed_fact_rejected(path, value):
    f = new_facts("statement")
    dst = f
    for key in path[:-1]:
        dst = dst[key]
    dst[path[-1]] = value
    with pytest.raises(ValueError):
        validate(f)


@pytest.mark.parametrize("kind,group", [
    ("env", "external"), ("end", "order"), ("contract", "arith"),
    ("function", "state"), ("state_decl", "loop"),
])
def test_inapplicable_group_must_be_empty(kind, group):
    f = new_facts(kind)
    f[group] = {"fabricated": False}
    with pytest.raises(ValueError, match="inapplicable"):
        validate(f)


def _guard():
    return {"rule": "1", "kind": "require", "polarity": 1,
            "operand_classes": ["msg.sender", "state"], "eq_pairs": ["env_state"],
            "is_sender_guard": True, "disjunctive": False, "offset": -1}


def test_valid_guard_preserves_polarity_and_index():
    f = new_facts("statement")
    f["guards"] = [_guard()]
    f["guard_status"] = "present"
    f["nearest"] = 0
    validate(f)
    f["guards"][0]["polarity"] = -1
    validate(f)


@pytest.mark.parametrize("field,value", [("polarity", 0), ("polarity", True),
    ("rule", "7"), ("kind", "dominator"), ("eq_pairs", ["sender_owner"]),
    ("offset", 0.2), ("is_sender_guard", "yes")])
def test_invalid_guard_rejected(field, value):
    f = new_facts("statement")
    f["guards"] = [_guard()]
    f["guard_status"] = "present"
    f["guards"][0][field] = value
    with pytest.raises(ValueError):
        validate(f)


def test_guard_presence_consistency_and_unresolved_modifier():
    f = new_facts("statement")
    f["guard_status"] = "present"
    with pytest.raises(ValueError):
        validate(f)
    f["guard_status"] = "unknown"
    f["unresolved"] = {"modifier_not_resolved": 1}
    validate(f)
    f["nearest"] = 0
    with pytest.raises(ValueError):
        validate(f)


def test_environment_source_has_no_consumption_usage():
    f = new_facts("env")
    f["env"]["keys"] = ["msg.sender"]
    validate(f)
    f["env"]["uses"] = ["guard"]
    with pytest.raises(ValueError):
        validate(f)


def test_env_key_contract_matches_frozen_layer():
    from scripts.DFG.dfg_v2.env import ENV_KEYS as frozen_keys
    assert tuple(ENV_KEYS) == tuple(frozen_keys)


def test_extraneous_top_level_and_missing_field_rejected():
    f = new_facts("end")
    f["extra"] = 0
    with pytest.raises(ValueError):
        validate(f)
    f = new_facts("statement")
    del f["external"]["value_class"]
    with pytest.raises(ValueError):
        validate(f)


def test_real_call_and_uninvoked_builder_are_distinct():
    f = new_facts("statement")
    f["external"]["uninvoked_call_value"] = True
    assert validate(f)["external"]["return_handling"] == "not_applicable"
    f["external"]["kinds"] = ["call"]
    f["external"]["return_handling"] = "ignored"
    validate(f)


def test_checked_call_has_identity_condition_requirement():
    f = new_facts("statement")
    f["checked_call"].update(status="supported", has_arithmetic=True,
                             has_guard=True, result_condition_check=True)
    validate(f)
    f["checked_call"]["has_guard"] = False
    with pytest.raises(ValueError):
        validate(f)


def test_unavailable_relative_distance_is_not_fabricated_zero():
    f = new_facts("statement")
    f["dfg"]["from"] = [{"node": "function", "offset": None}]
    f["order"]["pre_ext_call"] = {"node": "call", "offset": -2}
    validate(f)


@pytest.mark.parametrize("node", [1, "1"])
def test_preserve_original_hcg_identity_type(node):
    f = new_facts("statement")
    f["dfg"]["from"] = [{"node": node, "offset": None}]
    f["order"]["pre_ext_call"] = {"node": node, "offset": -2}
    validate(f)
    assert type(f["dfg"]["from"][0]["node"]) is type(node)


def test_boolean_is_not_node_identity():
    f = new_facts("statement")
    f["dfg"]["from"] = [{"node": True, "offset": None}]
    with pytest.raises(ValueError):
        validate(f)


def test_cross_function_guard_distance_unknown():
    f = new_facts("statement")
    f["guards"] = [_guard()]
    f["guards"][0].update(rule="5", kind="modifier", offset=None)
    f["guard_status"] = "present"
    validate(f)


ORACLE = __import__("pathlib").Path(__file__).parent / "fixtures" / "nodesem_oracle"
ORACLE_MANIFEST = json.loads((ORACLE / "expected.json").read_text(encoding="utf8"))


def test_independent_oracle_has_every_requested_case_and_honest_compilation_scope():
    keys = {c["id"] for c in ORACLE_MANIFEST["cases"]}
    required = set("abcdefghijklmnopqrstuvwxyz") | {"aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh"}
    assert required.issubset(keys)
    assert {"negative_local_shadow", "negative_result_overwrite", "negative_unrelated_guard"}.issubset(keys)
    for case in ORACLE_MANIFEST["cases"]:
        assert case["validation"] == "parser_only_not_compiled"
        assert case["checks"]
        assert (ORACLE / case["source"]).is_file()


@pytest.mark.parametrize("case", ORACLE_MANIFEST["cases"], ids=lambda c: c["id"])
def test_oracle_uses_real_parser_not_compilation_claim(case):
    from scripts.DFG.frontend import parse
    tree = parse((ORACLE / case["source"]).read_text(encoding="utf8"))
    assert not tree.root_node.has_error


def test_unknown_amount_and_call_result_are_explicit_not_none():
    f = new_facts("statement")
    f["external"].update(kinds=["call"], value_attached=True,
                         value_class="unknown", return_handling="unknown")
    f["unresolved"] = {"amount_classification_unresolved": 1, "return_binding_unresolved": 1}
    validate(f)
    assert f["external"]["value_class"] != "none"
    assert f["external"]["return_handling"] != "ignored"


@pytest.mark.parametrize("digest", ["a" * 64 + "\n", "A" * 64, "a" * 63])
def test_source_digest_is_exact_hex_not_a_prefix(digest):
    f = new_facts("statement")
    f["provenance"]["source_sha256"] = digest
    with pytest.raises(ValueError):
        validate(f)
