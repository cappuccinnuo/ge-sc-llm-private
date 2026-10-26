"""Independent exact-AST audit of frozen bare-expression classifications.

This is a validation-only reader: no Slither/compiler, analyzer, graph or model
execution. Parser tests do not establish Solidity language validity. The
historical classifier is deliberately not called by this audit.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from .slither_align import SourceFacts

VERSION = "dfg-v2-bare-expression-audit-v1"
WRAPPERS = frozenset(("expression", "parenthesized_expression", "expression_statement"))
CALLABLES = frozenset(("function_definition", "constructor_definition",
                      "fallback_receive_definition", "modifier_definition"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unwrap(node):
    while node is not None and node.type in WRAPPERS:
        children = [c for c in node.named_children if "comment" not in c.type]
        if len(children) != 1:
            break
        node = children[0]
    return node


def _callable(node):
    while node is not None and node.type not in CALLABLES:
        node = node.parent
    return node


def check_shape(ast, span):
    """Require one exact standalone statement; reject actual outer invocation."""
    nodes = [n for n in ast.nodes if n.type == "expression_statement"
             and [n.start_byte, n.end_byte] == list(span)]
    if len(nodes) != 1:
        return {"accepted": False, "reason": "not_one_exact_expression_statement"}
    statement = nodes[0]
    if statement.has_error:
        return {"accepted": False, "reason": "parse_error_in_statement"}
    expression = _unwrap(statement)
    base = {"statement_span": list(span), "source_text": ast.text(statement),
            "expression_type": expression.type, "outer_invocation": False}
    if expression.type == "identifier":
        base.update(accepted=True, shape="identifier", reason="standalone_identifier_without_call")
        return base
    if expression.type != "call_expression":
        base.update(accepted=False, reason="not_an_identifier_or_option_setter")
        return base
    callee = _unwrap(expression.child_by_field_name("function"))
    base["callee_type"] = callee.type if callee is not None else None
    if callee is None or callee.type != "member_expression":
        base.update(accepted=False, outer_invocation=bool(callee and callee.type == "call_expression"),
                    reason="actual_outer_call_or_unrecognized_callee")
        return base
    option = callee.child_by_field_name("property")
    receiver_method = _unwrap(callee.child_by_field_name("object"))
    if (option is None or ast.text(option) not in ("value", "gas") or
            receiver_method is None or receiver_method.type != "member_expression"):
        base.update(accepted=False, reason="not_direct_low_level_option_setter")
        return base
    method = receiver_method.child_by_field_name("property")
    receiver = _unwrap(receiver_method.child_by_field_name("object"))
    if (method is None or ast.text(method) not in ("call", "delegatecall", "callcode") or
            receiver is None or receiver.type != "identifier"):
        base.update(accepted=False, reason="not_direct_identifier_low_level_receiver")
        return base
    # A contract object method named call/value is not an address call option.
    declarations = [n for n in ast.nodes if n.type in ("parameter", "variable_declaration")
                    and _callable(n) == _callable(expression)
                    and n.child_by_field_name("name") is not None
                    and ast.text(n.child_by_field_name("name")) == ast.text(receiver)]
    if len(declarations) != 1:
        base.update(accepted=False, reason="address_receiver_declaration_not_unique")
        return base
    typ = declarations[0].child_by_field_name("type")
    if typ is None or ast.text(typ) not in ("address", "address payable"):
        base.update(accepted=False, reason="receiver_type_not_address")
        return base
    base.update(accepted=True, shape="uninvoked_low_level_option",
                reason="outermost_call_is_option_setter_no_following_invocation",
                receiver_name=ast.text(receiver), receiver_type=ast.text(typ),
                receiver_declaration_span=[declarations[0].start_byte, declarations[0].end_byte],
                method=ast.text(method), option=ast.text(option))
    return base


def run(alignment, output):
    alignment, output = Path(alignment).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(str(output))
    report = json.loads(alignment.read_text())
    frozen = [e for e in report["differences"] if e["category"] == "bare_expression_use"]
    cache, rows = {}, []
    for event in frozen:
        path = Path(event["source_path"])
        key = (str(path), event["source_sha256"])
        if key not in cache:
            if _sha(path) != event["source_sha256"]:
                raise ValueError("source SHA mismatch: " + str(path))
            cache[key] = SourceFacts(path.read_text())
        result = check_shape(cache[key], event["span"])
        rows.append(dict(result, difference_id=event["difference_id"],
                         task=event["task"], file=event["file"], source_path=str(path),
                         source_sha256=event["source_sha256"], version=event["version"],
                         variable=event["name"], declaration=event["primary"].get("declaration"),
                         layer=event["layer"], direction=event["direction"],
                         original_shape=event["classification_evidence"].get("shape")))
    counts = collections.Counter((r["task"], r.get("shape"), r["accepted"]) for r in rows)
    result = {"version": VERSION,
              "input": {"path": str(alignment), "sha256": _sha(alignment)},
              "runtime": {"path": str(Path(__file__).resolve()), "sha256": _sha(__file__)},
              "counts": [{"task": k[0], "shape": k[1], "accepted": k[2], "count": v}
                         for k, v in sorted(counts.items(), key=lambda x: str(x[0]))],
              "total": len(rows), "accepted": sum(r["accepted"] for r in rows),
              "rejected_ids": [r["difference_id"] for r in rows if not r["accepted"]],
              "shape_disagreements": [r["difference_id"] for r in rows
                                     if r.get("shape") != r["original_shape"]],
              "rows": rows, "compiler_executed": False, "slither_executed": False,
              "analyzer_executed": False, "graphs_modified": False,
              "limitation": "Exact parser shape/type audit, not language validation or semantic proof."}
    for path, sha in cache:
        if _sha(path) != sha:
            raise ValueError("source changed during audit: " + path)
    output.mkdir(parents=True)
    path = output / "report.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (output / "seal.json").write_text(json.dumps(
        {"version": VERSION, "report_sha256": _sha(path), "input": result["input"],
         "runtime": result["runtime"]}, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.alignment, args.output)
    print(json.dumps({k: result[k] for k in ("total", "accepted", "rejected_ids",
                                          "shape_disagreements", "counts")}))


if __name__ == "__main__":
    main()
