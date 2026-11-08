"""NS-P7 source-only canonicalization and exact projection regression."""
import copy
import json
import pytest
from scripts.node_sem.llm_inputs_v2 import no_comments, function_unit, produce, canonical_piece
from scripts.node_sem.llm_protocol_v2 import messages, template, cache_key, parse_response, output_schema
from scripts.node_sem.facts_ast import FUNCTIONS
from scripts.DFG.frontend import walk, parse
from scripts.node_sem.tests.test_text_view import fixture_context
from scripts.node_sem.text_view import build_text_view

SOURCE = """pragma solidity ^0.5.11;
contract Example {
 uint amount;
 // a comment is not a statement
 function pay(uint value) public {
   uint x = value;
   amount = x; // remove this
   require(amount > 0);
   if (x > 0) { x++; }
   for (uint i = 0; i < 1; i++) { x++; }
 }
}
"""


def unit(source=SOURCE):
    raw, tree = no_comments(source)
    fn = next(n for n in walk(tree.root_node) if n.type == "function_definition")
    decls = [n for n in walk(tree.root_node) if n.type == "state_variable_declaration"]
    return function_unit(raw, fn, decls)


def test_prompt_name_invariance_and_literals_untouched():
    a = unit()
    other = SOURCE.replace("Example", "Another").replace("amount", "newBalanceName").replace("pay", "execute")
    b = unit(other)
    for field in ("state_vars", "lines", "signature"):
        assert a[field] == b[field]
    assert a["inverse"]["a1"] == "pay"
    assert "require" in a["canonical"] and "amount" not in a["canonical"]
    assert "remove this" not in a["canonical"]
    c = unit(SOURCE.replace("require(amount > 0);", 'require(amount > 0, "value amount");'))
    assert '"value amount"' in c["canonical"]


def test_comment_bytes_and_line_coordinates():
    source = SOURCE.replace("a comment", "中文注释")
    raw, tree = no_comments(source)
    assert len(raw) == len(source.encode("utf8"))
    assert [i for i, b in enumerate(raw) if b == 10] == [i for i, b in enumerate(source.encode("utf8")) if b == 10]
    assert not any(n.type == "ERROR" or n.is_missing for n in walk(tree.root_node))
    assert b"comment" not in raw


def test_exact_ast_targets_and_label_independence(tmp_path):
    context = fixture_context(tmp_path, SOURCE)
    graph = context["graphs"]["F3"]
    texts = build_text_view(context["task_id"], "original", context)
    facts = [dict(row_key=r["row_key"], facts={"node_kind":"statement"}) for r in texts]
    first, refs = produce(context["task_id"], graph, context["source_text"], texts, facts)
    altered = copy.deepcopy(graph)
    for _, attrs in altered.nodes(data=True):
        attrs["type_label"] = 1
        attrs["node_info_vulnerabilities"] = ["tainted"]
        attrs["method"] = "bad"
        attrs["node_source_code_lines"] = [9999]
    second, other = produce(context["task_id"], altered, context["source_text"], texts, facts)
    assert first == second and refs == other
    targets = [r for r in refs if r["target_kind"] == "statement"]
    assert targets and len({r["row_key"] for r in targets}) == len(targets)
    fn = next(f for f in first if f["segments"][0]["target_lines"])
    assert all(r["relative_line"] in fn["segments"][0]["target_lines"] for r in targets)
    assert any(r["target_kind"] == "function" for r in refs)
    assert next(r for r in refs if r["node_type"] == "env_source")["target_kind"] == "excluded"


def test_long_function_segments_keep_signature_and_unique_targets(tmp_path):
    source = SOURCE.replace("   uint x = value;", "   uint x = value;\n" + "\n".join("   x += 1;" for _ in range(130)))
    c = fixture_context(tmp_path, source)
    texts = build_text_view(c["task_id"], "original", c)
    facts = [dict(row_key=r["row_key"], facts={}) for r in texts]
    fs, refs = produce(c["task_id"], c["graphs"]["F3"], c["source_text"], texts, facts)
    f = next(f for f in fs if len(f["segments"]) > 1)
    assert len(f["segments"]) == 3
    for s in f["segments"]:
        assert s["function_with_lines"].startswith("function a1")
    target_refs = [r for r in refs if r["target_kind"] == "statement"]
    assert len({r["row_key"] for r in target_refs}) == len(target_refs)
    assert max(r["segment"] for r in target_refs) == 2


def test_literal_marker_is_not_silently_rewritten():
    with pytest.raises(ValueError, match="literal/reserved"):
        unit(SOURCE.replace("require(amount > 0);", 'require(amount > 0, "bug_marker");'))


def test_template_exact_changes_and_bound_cache():
    u = dict(contract_header="contract a3", state_vars="uint a1;", function_with_lines="L1| return a1;", target_lines=[1])
    a, b = template("describe_v2"), template("judge_v2")
    assert b["system"].splitlines()[0] == "You describe what Solidity code does and may note possible weaknesses."
    assert b["system"].splitlines()[3] == "2. You may add a short security_note (<= 20 words) describing possible weaknesses."
    assert '"security_note"' not in a["schema"] and '"security_note"' in b["schema"]
    k = cache_key(u, "sha", {"seed":0})
    assert k != cache_key(u, "changed", {"seed":0})
    assert k != cache_key(u, "sha", {"seed":1})
    assert k != cache_key(u, "sha", {"seed":0}, "judge_v2")
    assert len(messages(u)) == 2
    assert output_schema()["properties"]["statements"]["items"]["additionalProperties"] is False


def test_strict_json_types_but_unknown_role_available_for_postprocessing():
    obj = {"function_intent":"Return amount", "statements":[dict(line=1, role="new_role", summary="Read", reads=["a1"], writes=[], external=False)]}
    assert parse_response(json.dumps(obj)) == obj
    obj["statements"][0]["line"] = True
    with pytest.raises(ValueError):
        parse_response(json.dumps(obj))

def test_contract_header_preserves_old_constructor_identity():
    a=unit("contract Example { function Example() public {} }")
    b=unit("contract Example { function Different() public {} }")
    assert a["contract_header"]=="contract a1"
    assert a["lines"][0].startswith("function a1")
    assert b["contract_header"]=="contract a2"
    assert b["lines"][0].startswith("function a1")
    assert a["contract_header"]!=b["contract_header"]

def test_v2_rules_and_contract_no_original_name():
    u=unit()
    assert "Example" not in u["contract_header"]
    msg=messages(dict(contract_header=u["contract_header"],state_vars=u["state_vars"],function_with_lines="x",target_lines=[]))
    assert msg[1]["content"].startswith(u["contract_header"])
    for i in range(6,10):assert str(i)+". " in template("describe_v2")["system"]
