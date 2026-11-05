"""Strict optional recovery of old-solc missing filenames (Prompt 6d).

Validation only: never edits a Slither object, graph, source, or frozen 6c result.
Every missing-filename CFG node must have a valid nonempty UTF-8 byte span and an
independent Slither expression exactly equal to the source slice. No whitespace,
casts, parentheses or terminators are normalized. ENTRY_POINT remains unproved.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

VERSION = "dfg-v2-slither-mapping-proof-v1"
TEXT_ORIGIN = "slither_node_expression_str"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(ref):
    path = Path(ref["path"]).resolve()
    if sha(path) != ref["sha256"]:
        raise ValueError("Input SHA mismatch: " + str(path))
    return path


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf8")


def import_evidence(raw):
    """Use the raw syntax tree, never a substring hit in comments/strings."""
    from scripts.DFG.frontend import parse, walk
    from scripts.DFG.models import Unsupported
    try:
        tree = parse(raw.decode("utf8"))
    except (Unsupported, UnicodeDecodeError) as exc:
        return dict(imports=[], parse_error=True, reason=str(exc))
    imports = [dict(start=n.start_byte, end=n.end_byte,
                    text=raw[n.start_byte:n.end_byte].decode("utf8"))
               for n in walk(tree.root_node) if n.type == "import_directive"]
    return dict(imports=imports, parse_error=bool(tree.root_node.has_error))


def prove_single_source(raw, nodes):
    """Fail the entire file if any missing-filename node cannot be proved.

    Nodes are immutable snapshots from collect_nodes. Never use an alleged
    source-text property that may itself read the target slice as proof.
    """
    source = import_evidence(raw)
    failures, proofs = [], []
    if source["imports"]:
        failures.append(dict(reason="source_has_import"))
    if source["parse_error"]:
        failures.append(dict(reason="source_parse_error"))
    if not nodes:
        failures.append(dict(reason="no_cfg_nodes"))
    missing_count = 0
    for index, node in enumerate(nodes):
        mapping = node.get("mapping")
        if not isinstance(mapping, dict):
            failures.append(dict(index=index, reason="unsupported_source_mapping"))
            continue
        filename = mapping.get("filename_absolute")
        if filename:
            failures.append(dict(index=index, reason="unexpected_bound_filename"))
            continue
        missing_count += 1
        start, length = mapping.get("start"), mapping.get("length")
        if (type(start) is not int or type(length) is not int or start < 0 or
                length <= 0 or start + length > len(raw)):
            failures.append(dict(index=index, reason="invalid_or_empty_byte_span"))
            continue
        independent = node.get("expression")
        if (node.get("text_origin") != TEXT_ORIGIN or
                not isinstance(independent, str) or not independent):
            failures.append(dict(index=index, reason="missing_independent_expression"))
            continue
        try:
            actual = raw[start:start + length].decode("utf8")
        except UnicodeDecodeError:
            failures.append(dict(index=index, reason="invalid_utf8_boundary"))
            continue
        if actual != independent:
            failures.append(dict(index=index, reason="text_mismatch",
                                 source_slice=actual, independent_expression=independent))
            continue
        proofs.append(dict(index=index, start=start, length=length,
                           text_sha256=hashlib.sha256(actual.encode("utf8")).hexdigest()))
    return dict(status="proved" if not failures else "not_comparable",
                rule="exact_utf8_no_normalization_every_cfg_node_no_import",
                import_check=source, cfg_nodes=len(nodes),
                missing_filename_nodes=missing_count, proven_nodes=len(proofs),
                node_proofs=proofs, failures=failures,
                failure_counts=dict(Counter(row["reason"] for row in failures)),
                partial_mapping_committed=False)


def collect_nodes(slither):
    """Capture independent expression strings before consulting target bytes."""
    rows = []
    for contract in slither.contracts:
        modifiers = list(contract.modifiers)
        for function in list(contract.functions) + modifiers:
            declarer = getattr(function, "contract_declarer", None)
            inherited = declarer is not None and declarer is not contract
            for node in function.nodes:
                expression = getattr(node, "expression", None)
                mapping = getattr(node, "source_mapping", None)
                locals_ = list(getattr(node, "local_variables_read", ())) + list(
                    getattr(node, "local_variables_written", ()))
                alias = any(getattr(v, "location", None) == "storage" for v in locals_)
                events = []
                for layer, attr, kind in (
                    ("L1", "local_variables_read", "USE"),
                    ("L1", "local_variables_written", "DEF"),
                    ("L2", "state_variables_read", "READ"),
                    ("L2", "state_variables_written", "WRITE")):
                    for variable in getattr(node, attr, ()):
                        tags = []
                        if function in modifiers:
                            tags.append("modifier_inlining")
                        if inherited:
                            tags.append("inheritance")
                        if alias and (layer == "L2" or getattr(variable, "location", None) == "storage"):
                            tags.append("alias")
                        events.append(dict(layer=layer, name=variable.name, kind=kind,
                                           tags=tags))
                rows.append(dict(contract=getattr(contract, "name", None),
                    function=getattr(function, "canonical_name", getattr(function, "name", None)),
                    node_id=getattr(node, "node_id", None), node_type=str(getattr(node, "type", None)),
                    mapping=dict(mapping) if isinstance(mapping, dict) else None,
                    expression=str(expression) if expression is not None else None,
                    text_origin=TEXT_ORIGIN if expression is not None else None,
                    events=events))
    return rows


def proved_reference(raw, nodes, proof):
    """Generate event sets only after the whole file passes. No partial rescue."""
    if proof != prove_single_source(raw, nodes) or proof["status"] != "proved":
        raise ValueError("All-node proof required before producing reference facts")
    result = {"L1": {}, "L2": {}}
    for node in nodes:
        line = 1 + raw[:node["mapping"]["start"]].count(b"\n")
        for event in node["events"]:
            key = (line, event["name"], event["kind"])
            result[event["layer"]].setdefault(key, set()).update(event["tags"])
    return result


def run(store_path, old_report_path, trusted_path, output):
    """Only recompile previously noncomparable missing-filename files."""
    from . import validate_slither as original
    from .l1_occurrences import extract
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing mapping output: " + str(output))
    store_path, old_report_path, trusted_path = [
        Path(p).resolve() for p in (store_path, old_report_path, trusted_path)]
    old_seal = old_report_path.with_name("report.seal.json")
    old = json.loads(old_report_path.read_text())
    seal = json.loads(old_seal.read_text())
    if seal["report_sha256"] != sha(old_report_path) or seal["store_sha256"] != sha(store_path):
        raise ValueError("Frozen report/store binding mismatch")
    store = json.loads(store_path.read_text())
    manifest_path = checked(store["input_manifest"])
    manifest = json.loads(manifest_path.read_text())
    trusted = json.loads(trusted_path.read_text())["compilers"]
    bindings = {str(p): sha(p) for p in (
        store_path, old_report_path, old_seal, trusted_path, manifest_path, Path(__file__))}
    rows = []
    for task, entry in old["tasks"].items():
        for prior in entry["files"]:
            if prior["status"] != "not_comparable":
                continue
            blockers = prior.get("comparability", {}).get("blockers", {})
            if not blockers.get("missing_filename"):
                continue
            source = manifest["tasks"][task]["sources"][prior["file"]]
            path = checked(source)
            compiler = Path(prior["compiler"]["path"]).resolve()
            version = prior["version"]
            trusted_compiler = trusted.get(version)
            if not trusted_compiler:
                raise ValueError("Compiler is not in existing trusted manifest: " + version)
            if (str(compiler) != str(Path(trusted_compiler["path"]).resolve()) or
                    sha(compiler) != prior["compiler"]["sha256"] or
                    sha(compiler) != trusted_compiler["sha256"]):
                raise ValueError("Trusted compiler changed: " + str(compiler))
            if source["sha256"] != prior["source_sha256"]:
                raise ValueError("Source identity differs from frozen report")
            bindings[str(path)], bindings[str(compiler)] = sha(path), sha(compiler)
            record = dict(task=task, file=prior["file"], source_sha256=source["sha256"],
                          version=version, version_origin=prior["version_origin"],
                          compiler=prior["compiler"], old_status=prior["status"])
            raw = path.read_bytes()
            try:
                obj = original._compile(path, compiler)
                nodes = collect_nodes(obj)
                proof = prove_single_source(raw, nodes)
                record.update(status=proof["status"], proof=proof, nodes=nodes)
                if proof["status"] == "proved":
                    reference = proved_reference(raw, nodes, proof)
                    audit = json.loads(checked(store["tasks"][task]["graphs"]["F3"]["audit"]).read_text())
                    candidate, _ = original.v2_facts(audit, prior["file"], raw)
                    candidate["L1"], _ = extract(raw.decode("utf8"), prior["file"], source.get("metadata"))
                    record["comparison"] = {layer: original.compare_facts(candidate[layer], reference[layer])
                                            for layer in ("L1", "L2")}
                    record["status"] = "compared"
                else:
                    record["comparison"] = None
            except Exception as exc:
                record.update(status="verification_failed", reason=type(exc).__name__, detail=str(exc))
            rows.append(record)
    if len(rows) != 6:
        raise ValueError("Expected exactly the six frozen missing-filename files")
    for path, digest in bindings.items():
        if sha(path) != digest:
            raise ValueError("Input/computation changed during mapping proof: " + path)
    report = dict(version=VERSION, files=rows, bindings=bindings,
                  summary=dict(Counter(row["status"] for row in rows)),
                  compilation_executed=True, existing_report_modified=False,
                  source_or_graph_modified=False, training_executed=False,
                  rule="all_nodes_exact_text_no_import_no_normalization",
                  note="Unproved files have no P/R; do not merge with frozen 6c metrics.")
    output.mkdir(parents=True)
    write_json(output/"report.json", report)
    write_json(output/"report.seal.json", dict(version=VERSION,
               report_sha256=sha(output/"report.json"), bindings=bindings))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    parser.add_argument("--old-report", required=True)
    parser.add_argument("--trusted-compilers", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run(args.store, args.old_report, args.trusted_compilers, args.output)
    print(json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
