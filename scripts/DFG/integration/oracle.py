"""Finite, source-first semantic Oracle; never reads prediction/target labels.

Selection is written and sealed before analysis. This is an acceptance sample,
not a dataset-wide coverage estimate or independent Solidity compilation proof.
"""
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from ..frontend import parse, walk, text
from ..models import Unsupported
from ..projection import Projector
from ..ddg_builder import DDGBuilder
from ..state.stage_k.profile import SupportedSourceView
from ..state.stage_j.analyzer import analyze_view as analyze_state
from ..state.stage_f.relations import order_relations
from .control_v2 import analyze_view as analyze_control

ROOT = Path(__file__).resolve().parents[3]
VERSION = "source-first-bounded-oracle-v1"
DEFAULT_MANIFEST = ROOT / "scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/build/manifest.json"
DEFAULT_OUTPUT = ROOT / "scripts/DFG/experiments/artifacts/integration_release_v1/oracle"
# Hand-read source semantics, fixed before running the candidate analyzers.
# An absent relation is not a claim that the function has no other dependency.
SPECS = (
 ("reentrancy", "buggy_18.sol", "add", 673, "scalar", "DATA_DEF_USE", "present", "c = a + b;", "require(c >= a);", "The local result c is defined by assignment and subsequently read by require."),
 ("reentrancy", "simple_dao.sol", "withdraw", 303, "state", "EXTERNAL_CALL_BEFORE_STATE_WRITE", "present", "msg.sender.call.value(amount)", "credit[msg.sender]-=amount;", "The external call precedes the credit decrement on the same syntactic path; this is order, not a backwards value edge."),
 ("reentrancy", "simple_dao.sol", "queryCredit", 507, "state", "STATE_DEF_USE", "absent", None, None, "Only an entry-state read is present; there is no preceding in-function state write."),
 ("reentrancy", "simple_dao.sol", "donate", 229, "state", "STATE_DEF_USE", "absent", None, None, "One compound update reads entry state then writes; no later read creates a cross-statement state def-use."),
 ("reentrancy", "modifier_reentrancy.sol", "airDrop", 429, "state", "STATE_DEF_USE", "fallback", None, None, "Two modifier invocations including an external token check exceed the single bounded prefix modifier profile."),
 ("reentrancy", "buggy_18.sol", "approveAndCall", 27664, "state", "STATE_DEF_USE", "fallback", None, None, "The bytes memory parameter and external callback exceed the scalar/reference support contract."),
 ("access_control", "buggy_18.sol", "sendto_txorigin21", 2201, "control", "CONTROL_DEPENDENCE", "present", "require (tx.origin == owner_txorigin21);", "receiver.transfer(amount);", "Successful require gates the subsequent transfer; the Oracle judges control structure, not correctness of tx.origin authorization."),
 ("access_control", "buggy_26.sol", "add", 117, "scalar", "DATA_DEF_USE", "present", "uint256 c = a + b;", "return c;", "The local c declaration reaches the explicit return without an intervening write."),
 ("access_control", "rubixi.sol", "DynamicPyramid", 656, "state", "STATE_DEF_USE", "absent", None, None, "This function only assigns creator; there is no subsequent state read in the function."),
 ("access_control", "buggy_26.sol", "totalSupply", 4948, "state", "STATE_DEF_USE", "absent", None, None, "This getter reads entry state only; cross-function initialization is outside this relation."),
 ("access_control", "proxy.sol", "forward", 255, "control", "CONTROL_DEPENDENCE", "fallback", None, None, "bytes input and delegatecall require unsupported reference/call semantics; preserve the function without partial control edges."),
 ("access_control", "buggy_26.sol", "name", 4253, "state", "STATE_DEF_USE", "fallback", None, None, "The string memory return type is outside the supported scalar local/return type domain."),
)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def write_json(path, data):
    with Path(path).open("x", encoding="utf8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def checked(path, digest):
    path = Path(path).resolve()
    if sha(path) != digest:
        raise ValueError("Oracle frozen input SHA mismatch: " + str(path))
    return path


def validate_selection(selection):
    cases = selection["cases"]
    if not 0 < len(cases) <= 12:
        raise ValueError("Oracle must contain between one and twelve preselected functions")
    identities = [(c["cohort"], c["source_file"], c["source_sha256"], tuple(c["function_span"])) for c in cases]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate Oracle function identity")
    for case in cases:
        if case["expected"] not in ("present", "absent", "fallback"):
            raise ValueError("Invalid Oracle expectation")
        if case["family"] not in ("scalar", "state", "control"):
            raise ValueError("Invalid Oracle analyzer family")
        if case["expected"] == "present" and not (case.get("from_text") and case.get("to_text")):
            raise ValueError("Positive Oracle requires independently chosen source endpoints")
    return True


def select(manifest=DEFAULT_MANIFEST, output=DEFAULT_OUTPUT):
    manifest, output = Path(manifest).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Oracle selection output exists; never replace a chosen sample")
    seal = read_json(manifest.with_name("manifest.seal.json"))
    checked(manifest, seal["sha256"])
    build = read_json(manifest)
    task_rows = {t["task_id"]: t for t in build["tasks"]}
    selection = {"version": VERSION, "source_build_manifest": str(manifest),
                 "source_build_manifest_sha256": sha(manifest), "cases": [],
                 "selection_basis": "hand-read source semantics; fixed before candidate analysis",
                 "predictions_used": False, "vulnerability_labels_used": False,
                 "compiled": False, "compilation_reason": "No compiler invoked; grammar acceptance is not compiler validation"}
    for cohort, file, name, start, family, relation, expected, frm, to, reason in SPECS:
        task_id = cohort + "_author_contract"
        row = task_rows[task_id]
        records_path = checked(row["source_metadata_manifest"], row["source_metadata_sha256"])
        record = read_json(records_path)["sources"][file]
        source_path = checked(record["path"], record["sha256"])
        source = source_path.read_bytes().decode("utf8")
        functions = [n for n in walk(parse(source).root_node) if n.type == "function_definition" and n.start_byte == start]
        if len(functions) != 1 or text(source, functions[0].child_by_field_name("name")) != name:
            raise ValueError("Hand-selected function moved: " + cohort + "/" + file + "/" + name)
        fn = functions[0]
        raw = source.encode("utf8")[fn.start_byte:fn.end_byte]
        coverage_path = checked(row["coverage_path"], row["coverage_sha256"])
        old_file = read_json(coverage_path)["files"].get(file, {})
        old = [f for f in old_file.get("functions", []) if f["function"] == file + ":" + str(start)]
        selection["cases"].append({"case_id": "%s/%s/%s@%d" % (cohort, file, name, start),
            "cohort": cohort, "task_id": task_id, "source_file": file,
            "source_path": str(source_path), "source_sha256": record["sha256"],
            "metadata": record.get("metadata"), "metadata_manifest": str(records_path),
            "metadata_manifest_sha256": row["source_metadata_sha256"],
            "function_name": name, "function_span": [fn.start_byte, fn.end_byte],
            "function_line_range": [fn.start_point[0]+1, fn.end_point[0]+1],
            "function_sha256": sha_bytes(raw), "function_source": raw.decode("utf8"),
            "family": family, "relation": relation, "expected": expected,
            "from_text": frm, "to_text": to, "manual_reason": reason,
            "graph": row["source_graph"], "historical_control_coverage": {
                "path": str(coverage_path), "sha256": row["coverage_sha256"],
                "function_status": old[0]["status"] if old else "not_recorded"}})
    validate_selection(selection)
    output.mkdir(parents=True)
    write_json(output / "selection.json", selection)
    write_json(output / "selection.seal.json", {"sha256": sha(output / "selection.json")})
    return selection


def _anchors(fact, family):
    if family == "control":
        return fact.controller, fact.controlled
    return fact.definition.anchor, fact.use.anchor


def _source_text(view, anchor):
    return view.raw[anchor.start:anchor.end].decode("utf8")


def _matching(case, view, fact):
    if case["expected"] != "present":
        return True
    a, b = _anchors(fact, case["family"])
    # A function-entry anchor contains all descendant source text. It must not
    # impersonate the independently selected assignment/guard statement.
    if a.role in ("function_definition", "constructor_definition", "fallback_receive_definition"):
        return False
    normalize = lambda value: " ".join(value.split())
    left, right = normalize(_source_text(view, a)), normalize(_source_text(view, b))
    expected_left, expected_right = normalize(case["from_text"]), normalize(case["to_text"])
    # Order facts are statement anchored although the selected semantic source
    # is an external call subexpression; scalar/control expectations are exact.
    left_matches = expected_left in left if case["family"] == "state" else expected_left == left
    return left_matches and expected_right == right


def validate_case(case, graph, source, metadata=None):
    raw = source.encode("utf8")
    if sha_bytes(raw) != case["source_sha256"]:
        raise ValueError("Oracle source mismatch")
    start, end = case["function_span"]
    if sha_bytes(raw[start:end]) != case["function_sha256"]:
        raise ValueError("Oracle function span mismatch")
    fid = case["source_file"] + ":" + str(start)
    record = {"case_id": case["case_id"], "cohort": case["cohort"],
              "source_file": case["source_file"], "source_sha256": case["source_sha256"],
              "function_span": case["function_span"], "relation": case["relation"],
              "expected": case["expected"], "manual_reason": case["manual_reason"],
              "analysis_status": None, "semantic_facts": 0, "projected_facts": 0,
              "proofs": [], "diagnostics": [], "compiled": False}
    try:
        view = SupportedSourceView(source, case["source_file"], metadata)
        selected = [n for n in view.functions if n.start_byte == start and n.end_byte == end]
        if len(selected) != 1:
            raise ValueError("Oracle function not present in semantic view")
        if case["family"] == "scalar":
            result = DDGBuilder().analyze_source(source, case["source_file"])
            facts = [f for f in result.facts if f.use.function == fid]
            diagnostics = [d for d in result.diagnostics if d.get("function") == fid or d.get("kind") == "file_fallback"]
            status = "function_fallback" if any(d.get("kind") in ("function_fallback", "file_fallback") for d in diagnostics) else "analyzed"
        elif case["family"] == "control":
            result = analyze_control(view, selected_functions=[fid])[0]
            status, facts, diagnostics = result.status, result.facts, result.diagnostics
        else:
            selected_view = copy.copy(view)
            selected_view.functions = selected
            results, _ = analyze_state(selected_view, enable_modifiers=True)
            result = results[0]
            status, diagnostics = result.status, result.diagnostics
            if case["relation"] == "STATE_DEF_USE":
                facts = [f for f in result.facts if f.certainty == "EXACT"]
            else:
                orders, _ = order_relations(result)
                facts = [f for f in orders if f.relation == case["relation"] and f.certainty == "EXACT"]
        record.update(analysis_status=status, diagnostics=diagnostics)
        if status == "function_fallback":
            record.update(classification="analysis_scope_unsupported", passed=case["expected"] == "fallback", no_partial_facts=not facts)
            if facts:
                raise AssertionError("Fallback published partial Oracle facts")
            return record
        matching = [f for f in facts if _matching(case, view, f)]
        record["semantic_facts"] = len(matching)
        if not matching:
            record.update(classification="semantic_absent" if case["expected"] == "absent" else "missing_expected_semantic_fact", passed=case["expected"] == "absent")
            return record
        projector = Projector(graph, view)
        for fact in matching:
            a, b = _anchors(fact, case["family"])
            proof = {"from_span": [a.start, a.end, a.role], "to_span": [b.start, b.end, b.role],
                     "from_code": _source_text(view, a), "to_code": _source_text(view, b)}
            nodes = []
            for anchor in (a, b):
                k = view.compat_key(anchor)
                nodes.append(projector.by_ast.get(view.compat_ids[k]))
            proof["node_ids"] = nodes
            proof["projected"] = None not in nodes and nodes[0] != nodes[1]
            record["proofs"].append(proof)
        record["projected_facts"] = sum(p["projected"] for p in record["proofs"])
        record["classification"] = "projected" if record["projected_facts"] else "projection_missing"
        record["passed"] = case["expected"] == "present" and record["projected_facts"] > 0
    except Unsupported as exc:
        record.update(classification="analysis_scope_unsupported" if record["analysis_status"] is None else "projection_missing",
                      passed=case["expected"] == "fallback" and record["analysis_status"] is None)
        record["diagnostics"].append({"reason": str(exc)})
    return record


def validate(selection_path, output=None):
    from scripts.labeling_v2.safe_graph import read_graph
    selection_path = Path(selection_path).resolve()
    checked(selection_path, read_json(selection_path.with_name("selection.seal.json"))["sha256"])
    selection = read_json(selection_path)
    validate_selection(selection)
    checked(selection["source_build_manifest"], selection["source_build_manifest_sha256"])
    output = Path(output).resolve() if output else selection_path.parent / "validation"
    if output.exists():
        raise ValueError("Oracle validation output exists; preserve previous evidence")
    results, graphs = [], {}
    for case in selection["cases"]:
        checked(case["metadata_manifest"], case["metadata_manifest_sha256"])
        checked(case["historical_control_coverage"]["path"], case["historical_control_coverage"]["sha256"])
        source = checked(case["source_path"], case["source_sha256"]).read_bytes().decode("utf8")
        key = case["graph"]["path"]
        if key not in graphs:
            graphs[key] = read_graph(checked(key, case["graph"]["sha256"]))
        results.append(validate_case(case, graphs[key], source, case.get("metadata")))
    report = {"version": VERSION, "selection_sha256": sha(selection_path),
              "cases": results, "passed": sum(x["passed"] for x in results),
              "failed": sum(not x["passed"] for x in results),
              "classification_counts": dict(Counter(x["classification"] for x in results)),
              "training_executed": False, "labels_or_predictions_used": False,
              "compiled": False, "limitation": "Finite source-semantic acceptance sample, not corpus coverage or vulnerability ground truth verification"}
    output.mkdir(parents=True)
    write_json(output / "results.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sel = sub.add_parser("select")
    sel.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sel.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    val = sub.add_parser("validate")
    val.add_argument("--selection", type=Path, default=DEFAULT_OUTPUT / "selection.json")
    val.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "select":
        report = select(args.manifest, args.output)
        print("Selected", len(report["cases"]), "source functions; no candidate analysis executed")
    else:
        report = validate(args.selection, args.output)
        print(json.dumps({k: report[k] for k in ("passed", "failed", "classification_counts")}))
        if report["failed"]:
            raise SystemExit(1)

if __name__ == "__main__":
    main()
