"""Sealed, source-first Prompt 6 Oracle comparison; no analyzer modifications.

Expected files are authored and committed BEFORE this module may run analyzers.
Metrics describe the four forward relations of the frozen v2 design, not full
Solidity semantics. Tuple element correlation is not graph-expressible.
"""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import networkx as nx
import numpy as np

from . import DATA_DEF_USE, READS_STATE, WRITES_STATE, ENV_FLOW, ENV_SOURCE
from .pipeline import build
from .projection_view import ProjectionView
from .units import projected_node
from scripts.DFG.projection import Projector
from scripts.DFG.frontend import walk
from scripts.DFG.graph_audit import fingerprint

RELATIONS = (DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW)
CATEGORIES = ("implementation_error", "design_approximation", "expectation_error")
DEFAULT_ORACLE = Path(__file__).with_name("oracle")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty endpoint text")
    return " ".join(value.split())


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True,
                                    ensure_ascii=False) + "\n", encoding="utf8")


def fact_key(record):
    relation = record.get("relation")
    if relation not in RELATIONS:
        raise ValueError("Unknown Oracle relation")
    var = record.get("var")
    if not isinstance(var, str) or not var:
        raise ValueError("Every Oracle fact needs var / environment key")
    return relation, normalize(record["src"]), normalize(record["dst"]), var


def validate_expected(expected, source_path):
    if expected.get("source_sha256") != sha(source_path):
        raise ValueError("Oracle source SHA differs")
    source = " ".join(Path(source_path).read_text(encoding="utf8").split())
    for e in expected.get("edges", []) + expected.get("absent", []):
        for side in ("src", "dst"):
            endpoint = normalize(e[side])
            if not endpoint.startswith("ENV:") and endpoint not in source:
                raise ValueError("Expected endpoint is absent from source: " + endpoint)
    for name in ("edges", "absent"):
        if not isinstance(expected.get(name), list):
            raise ValueError("Oracle needs exhaustive edges and absent lists")
        keys = [fact_key(e) for e in expected[name]]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate expected fact: " + name)
    if {fact_key(e) for e in expected["edges"]} & {fact_key(e) for e in expected["absent"]}:
        raise ValueError("Expected and absent facts contradict")
    counts = expected.get("counts", {})
    if set(counts) - {"unmapped_env", "env_nodes"}:
        raise ValueError("Unsupported Oracle count assertion")
    if "unmapped_env" in counts and (type(counts["unmapped_env"]) is not int
                                    or counts["unmapped_env"] < 0):
        raise ValueError("Invalid unmapped count")
    if "env_nodes" in counts and (not isinstance(counts["env_nodes"], dict)
        or any(type(v) is not int or v < 0 for v in counts["env_nodes"].values())):
        raise ValueError("Invalid environment counts")
    return expected


def verify_seal(directory=DEFAULT_ORACLE):
    directory = Path(directory).resolve()
    seal = json.loads((directory / "SEAL.json").read_text(encoding="utf8"))
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                    cwd=str(directory)).decode().strip())
    commit = seal["expectations_commit"]
    recorded = seal["files"]
    source_stems = {p.stem for p in directory.glob("*.sol")}
    expected_stems = {p.name[:-len(".expected.json")] for p in directory.glob("*.expected.json")}
    if source_stems != expected_stems:
        raise ValueError("Oracle source/expectation pairs differ")
    actual_names = {p.name for p in directory.glob("*.sol")}
    actual_names.update(p.name for p in directory.glob("*.expected.json"))
    if actual_names != set(recorded):
        raise ValueError("Oracle asset set differs from seal")
    if not 18 <= len(list(directory.glob("*.sol"))) <= 20:
        raise ValueError("Expected 18-20 independently sealed cases")
    for name, digest in recorded.items():
        path = directory / name
        if sha(path) != digest:
            raise ValueError("Oracle SHA differs: " + name)
        rel = path.relative_to(root).as_posix()
        blob = subprocess.check_output(["git", "show", commit + ":" + rel], cwd=str(root))
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError("Expectation was not in the sealed Git commit: " + name)
    for path in sorted(directory.glob("*.expected.json")):
        validate_expected(json.loads(path.read_text(encoding="utf8")),
                          path.with_name(path.name.replace(".expected.json", ".sol")))
    return seal


class ConstantEncoder:
    provenance = {"kind": "deterministic Oracle stub, not tokenizer features"}
    def __init__(self, value=0):
        self.value = value

    def __call__(self, text):
        return np.full(512, self.value, dtype=np.float32)


def graph_for(source, file):
    # Same generator and feature shape as tests/test_l1.py::graph_for.
    # Compilation is neither executed nor implied by Tree-sitter acceptance.
    from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source
    graph = nx.MultiDiGraph(generate_cfg_from_source(source, file))
    for _, data in graph.nodes(data=True):
        data["token"] = np.zeros(512, dtype=np.float32)
        data["node_info_vulnerabilities"] = None
    return graph


def unique_endpoints(graph, source, file):
    """Resolve DOT code through exact raw/compat AST identity; no line guessing."""
    view = ProjectionView(source, file)
    projector = Projector(graph, view)
    texts, identity = {}, {}
    for node in walk(view.tree.root_node):
        identifier = projected_node(view, projector, node)
        if identifier is None:
            continue
        raw = view.raw[node.start_byte:node.end_byte].decode("utf8")
        value = normalize(raw)
        if identifier in texts and texts[identifier] != value:
            raise ValueError("Multiple raw AST texts for one graph node")
        if value in identity and identity[value] != identifier:
            raise ValueError("Nonunique normalized statement text: " + value)
        texts[identifier], identity[value] = value, identifier
    # Synthetic end_if/end_loop nodes intentionally lack source AST statements.
    return texts


def observed_facts(graph, audit, original_texts):
    texts = dict(original_texts)
    for node, data in graph.nodes(data=True):
        if data["node_type"] == ENV_SOURCE:
            texts[node] = "ENV:" + data["code"]
    facts = set()
    for src, dst, attrs in graph.edges(data=True):
        relation = attrs.get("edge_type")
        if relation not in RELATIONS:
            continue
        if src not in texts or dst not in texts:
            raise ValueError("Oracle edge has an endpoint without exact source text")
        if relation == DATA_DEF_USE:
            variables = set()
            for i in attrs["ddg_fact_indices"]:
                evidence = audit["layers"]["L1"]["evidence"][i]
                if (evidence["source"], evidence["target"]) != (src, dst):
                    raise ValueError("L1 edge evidence endpoint mismatch")
                variables.add(evidence["symbol"].rsplit(":", 1)[-1])
        elif relation in (READS_STATE, WRITES_STATE):
            variables = set(attrs["state_vars"])
        else:
            variables = {attrs["env_key"]}
        for var in variables:
            facts.add((relation, texts[src], texts[dst], var))
    counts = dict(unmapped_env=sum(e["status"] == "unmapped"
                        for e in audit["layers"]["L3"]["evidence"]),
                  env_nodes=dict(Counter(d["code"] for _, d in graph.nodes(data=True)
                                         if d["node_type"] == ENV_SOURCE)))
    return facts, counts


def record_key(key):
    return dict(zip(("relation", "src", "dst", "var"), key))


def metric(expected, actual):
    tp, fp, fn = len(expected & actual), len(actual - expected), len(expected - actual)
    return dict(tp=tp, fp=fp, fn=fn, expected=len(expected), actual=len(actual),
                precision=tp / float(tp + fp) if tp + fp else None,
                recall=tp / float(tp + fn) if tp + fn else None)


def observed_properties(graph, audit, original_texts):
    texts = dict(original_texts)
    for node, data in graph.nodes(data=True):
        if data["node_type"] == ENV_SOURCE:
            texts[node] = "ENV:" + data["code"]
    result = {}
    for src, dst, attrs in graph.edges(data=True):
        relation = attrs.get("edge_type")
        if relation in (READS_STATE, WRITES_STATE):
            for var in attrs["state_vars"]:
                key = relation, texts[src], texts[dst], var
                result[key] = {"via_alias": attrs["via_alias"]}
        elif relation == ENV_FLOW:
            key = relation, texts[src], texts[dst], attrs["env_key"]
            proof = [audit["layers"]["L3"]["evidence"][i] for i in attrs["evidence_indices"]]
            evidence_spellings = sorted({ev["spelling"] for ev in proof})
            if sorted(attrs["spellings"]) != evidence_spellings:
                raise ValueError("Environment spelling evidence differs from edge")
            result[key] = {"spellings": evidence_spellings}
    return result


def compare(expected, actual, counts, properties=None):
    wanted = {fact_key(e) for e in expected["edges"]}
    forbidden = {fact_key(e) for e in expected["absent"]}
    unexpected, missing, violated = actual - wanted, wanted - actual, actual & forbidden
    issues = []
    for kind, keys in (("missing", missing), ("unexpected", unexpected),
                       ("absent_violated", violated)):
        for key in sorted(keys):
            issues.append(dict(kind=kind, fact=record_key(key)))
    for edge in expected["edges"]:
        key = fact_key(edge)
        if key not in actual:
            continue
        for name in ("spellings", "via_alias"):
            if name not in edge:
                continue
            value = sorted(edge[name]) if name == "spellings" else edge[name]
            got = (properties or {}).get(key, {}).get(name)
            if got != value:
                issues.append(dict(kind="evidence_property_mismatch", fact=record_key(key),
                                   property=name, expected=value, actual=got))
    for name, value in expected.get("counts", {}).items():
        got = counts.get(name)
        if name == "env_nodes":
            value = {k: v for k, v in value.items() if v}
        if got != value:
            issues.append(dict(kind="count_mismatch", count=name, expected=value, actual=got))
    return dict(passed=not issues, issues=issues, absent_violations=len(violated),
                metrics={r: metric({k for k in wanted if k[0] == r},
                                   {k for k in actual if k[0] == r}) for r in RELATIONS},
                graph_edge_metrics={r: metric({k[:3] for k in wanted if k[0] == r},
                                              {k[:3] for k in actual if k[0] == r})
                                    for r in RELATIONS},
                observed=[record_key(k) for k in sorted(actual)], counts=counts,
                approximations=[e for e in expected["edges"] + expected["absent"]
                                if e.get("approximation")])


def run_case(source_path, expected, encoder=None):
    source_path = Path(source_path)
    validate_expected(expected, source_path)
    source, file = source_path.read_text(encoding="utf8"), source_path.name
    graph = graph_for(source, file)
    before = fingerprint(graph)
    texts = unique_endpoints(graph, source, file)
    output, audit = build(graph, {file: source}, {}, ("L1", "L2", "L3"),
                          token_encoder=encoder or ConstantEncoder())
    if fingerprint(graph) != before:
        raise AssertionError("Oracle changed original input")
    actual, counts = observed_facts(output, audit, texts)
    properties = observed_properties(output, audit, texts)
    result = compare(expected, actual, counts, properties)
    result["observed_properties"] = [dict(fact=record_key(k), properties=v)
                                     for k, v in sorted(properties.items())]
    result.update(source_sha256=sha(source_path), input_fingerprint=before,
                  output_fingerprint=fingerprint(output), invariants=audit["invariants"],
                  compilation="not executed; parser-backed verification only")
    return result, audit


def apply_classifications(report, classification):
    """Classifications never change expectations or the original mismatch metrics."""
    digest = hashlib.sha256((json.dumps(report, indent=2, sort_keys=True,
                         ensure_ascii=False) + "\n").encode("utf8")).hexdigest()
    if classification.get("oracle_report_sha256") != digest:
        raise ValueError("Classification report SHA binding differs")
    records = classification["issues"]
    actual = {item["id"] for case in report["cases"] for item in case["issues"]}
    if set(records) != actual:
        raise ValueError("Missing, duplicate or extra mismatch classifications")
    for identifier, record in records.items():
        if record.get("category") not in CATEGORIES or not record.get("reason"):
            raise ValueError("Invalid mismatch classification: " + identifier)
        if record["category"] == "expectation_error" and not record.get("language_rule"):
            raise ValueError("Expectation corrections require a cited language rule")
    return dict(counts=dict(Counter(x["category"] for x in records.values())),
                issues=records, all_classified=True)


def run(directory, output):
    directory, output = Path(directory), Path(output)
    seal = verify_seal(directory)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(version="dfg-v2-oracle-v2-evidence", expectations_commit=seal["expectations_commit"],
                  oracle_seal_sha256=sha(directory / "SEAL.json"), cases=[],
                  compilation="not executed; no available approved offline solc",
                  metrics_unit="relation/source statement/target statement/variable facts",
                  no_training=True)
    for expected_path in sorted(directory.glob("*.expected.json")):
        name = expected_path.name.replace(".expected.json", "")
        source_path = directory / (name + ".sol")
        expected = json.loads(expected_path.read_text(encoding="utf8"))
        try:
            result, audit = run_case(source_path, expected)
            dump(output / (name + ".audit.json"), audit)
        except Exception as exc:
            # Keep all cases; infrastructure/parse failures are visible failures.
            result = dict(passed=False, issues=[dict(kind="execution_error",
                exception=type(exc).__name__, message=str(exc))], metrics={},
                graph_edge_metrics={}, approximations=[])
        result.update(name=name, expected_sha256=sha(expected_path))
        for number, issue in enumerate(result["issues"]):
            issue["id"] = name + ":" + str(number)
        report["cases"].append(result)
        dump(output / (name + ".result.json"), result)
    report["execution_error_cases"] = sum(any(i["kind"] == "execution_error"
                        for i in c["issues"]) for c in report["cases"])
    report["scored_cases"] = len(report["cases"]) - report["execution_error_cases"]
    report["metrics_complete"] = report["execution_error_cases"] == 0
    report["metrics_scope"] = "scored cases only; execution failures prevent complete acceptance"
    report["passed_cases"] = sum(c["passed"] for c in report["cases"])
    report["failed_cases"] = len(report["cases"]) - report["passed_cases"]
    report["issue_count"] = sum(len(c["issues"]) for c in report["cases"])
    report["unclassified"] = report["issue_count"]
    for field in ("metrics", "graph_edge_metrics"):
        totals = {}
        for relation in RELATIONS:
            sums = {k: sum(c[field].get(relation, {}).get(k, 0) for c in report["cases"])
                    for k in ("tp", "fp", "fn")}
            tp, fp, fn = (sums[k] for k in ("tp", "fp", "fn"))
            totals[relation] = dict(sums, precision=tp / float(tp + fp) if tp + fp else None,
                                   recall=tp / float(tp + fn) if tp + fn else None)
        report[field] = totals
    dump(output / "summary.json", report)
    dump(output / "seal.json", dict(summary_sha256=sha(output / "summary.json"),
         oracle_seal_sha256=sha(directory / "SEAL.json"),
         files={p.name: sha(p) for p in sorted(output.glob("*.json"))},
         runner_sha256=sha(__file__)))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", default=str(DEFAULT_ORACLE))
    parser.add_argument("--output", required=True)
    parser.add_argument("--classifications",
                        help="Optional issue classifications bound to this exact report SHA")
    args = parser.parse_args(argv)
    result = run(args.oracle, args.output)
    if args.classifications:
        classifications = json.loads(Path(args.classifications).read_text(encoding="utf8"))
        classified = apply_classifications(result, classifications)
        dump(Path(args.output) / "classifications.json", classified)
        dump(Path(args.output) / "classification_binding.json",
             dict(report_sha256=sha(Path(args.output) / "summary.json"),
                  classifications_sha256=sha(args.classifications),
                  result_sha256=sha(Path(args.output) / "classifications.json")))
    print(json.dumps({k: result[k] for k in ("passed_cases", "failed_cases", "issue_count")}))
    return 0 if result["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
