"""Export every newly recovered F3 DATA_DEF_USE edge for separate human review.

Uses the original review CSV/provenance/seal schema and scorer unchanged.
The sealed store diff is recomputed before publication; verdicts stay blank.
No analyzer, graph mutation, model, sampling or human judgment runs here.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from . import DATA_DEF_USE
from . import review_sheet as review
from .store_diff import _equal, _ref, verify_equivalence, VERSION as DIFF_VERSION


def _load_diff(diff_path):
    diff_path = Path(diff_path).resolve()
    seal_path = diff_path.with_name("store_diff.seal.json")
    seal = read_json(seal_path)
    if seal.get("version") != DIFF_VERSION or seal.get("status") != "accepted":
        raise ValueError("Invalid supplemental store-diff seal")
    document = read_json(checked(diff_path, seal["report_sha256"]))
    if document.get("version") != DIFF_VERSION or document.get("status") != "accepted":
        raise ValueError("Invalid supplemental store-diff result")
    review_seal = document["review"]["seal"]
    checked(review_seal["path"], review_seal["sha256"])
    verification = verify_equivalence(diff_path, review_seal["path"])
    return diff_path, document, verification


def _added_rows(task, graph, audit, source_record, added, prior_identities):
    rows, proofs, seen = [], [], set()
    identities = sorted(added, key=lambda r: review._json(
        [r["source"], r["target"], r["key"]]))
    raw_cache = {}
    for record in identities:
        source, target, key = record["source"], record["target"], record["key"]
        identity = (task, source, target, key)
        if identity in seen:
            raise ValueError("Duplicate supplemental edge identity")
        if identity in prior_identities:
            raise ValueError("Supplemental edge already appears in the original review")
        seen.add(identity)
        if record.get("relation") != DATA_DEF_USE:
            raise ValueError("Supplement accepts DATA_DEF_USE additions only")
        if not graph.has_edge(source, target, key):
            raise ValueError("Supplemental edge missing from graph")
        attrs = graph[source][target][key]
        if attrs.get("edge_type") != DATA_DEF_USE:
            raise ValueError("Supplemental graph edge relation differs")
        _equal(attrs, record["attributes"], "Supplemental edge attributes differ")
        name = graph.nodes[source]["source_file"]
        if name != record["file"]:
            raise ValueError("Supplemental source identity differs")
        ref = source_record["sources"][name]
        if ref["sha256"] != record["source_sha256"]:
            raise ValueError("Supplemental source SHA differs")
        if name not in raw_cache:
            raw_cache[name] = checked(ref["path"], ref["sha256"]).read_bytes()
        row, proof = review._edge_row(
            task, graph, audit, ref, raw_cache[name], (source, target, key, attrs))
        _equal(proof["evidence"], record["evidence"],
               "Supplemental resolved evidence differs")
        rows.append(row)
        proofs.append(proof)
    return rows, proofs


def export_supplement(diff_path, output):
    """Export all added edges in the original review's contract-task cohort."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing supplemental review output: " + str(output))
    diff_path, difference, verification = _load_diff(diff_path)
    store_ref = difference["new_store"]
    store_path = checked(store_ref["path"], store_ref["sha256"])
    document = read_json(store_path)
    manifest_ref = document["input_manifest"]
    manifest = read_json(checked(manifest_ref["path"], manifest_ref["sha256"]))
    old_seal_path = Path(difference["review"]["seal"]["path"])
    old_seal = read_json(old_seal_path)
    old_proof_ref = old_seal["provenance"]
    old_proof = read_json(checked(old_seal_path.parent / old_proof_ref["path"],
                                  old_proof_ref["sha256"]))
    selected = sorted(old_proof["task_bindings"])
    if not selected or any(document["tasks"].get(t, {}).get("task") != "contract"
                           for t in selected):
        raise ValueError("Supplement requires the original contract review cohort")
    prior_identities = {
        (p["task"], p["source_node_id"], p["target_node_id"], p["edge_key"])
        for p in old_proof["rows"]}
    rows, proofs, bindings, populations = [], [], {}, {}
    for task in selected:
        entry = document["tasks"][task]["graphs"]["F3"]
        comparison = difference["tasks"][task]["F3"]
        _equal(entry["graph"], comparison["new_graph"], "Supplement graph binding differs")
        _equal(entry["audit"], comparison["new_audit"], "Supplement audit binding differs")
        graph = read_graph(checked(entry["graph"]["path"], entry["graph"]["sha256"]))
        audit = read_json(checked(entry["audit"]["path"], entry["audit"]["sha256"]))
        source_record = manifest["tasks"][task]
        if sorted({d["source_file"] for _, d in graph.nodes(data=True)}) != source_record["graph_files"]:
            raise ValueError("Supplement graph/input population differs")
        added = comparison["added"]
        if len(added) != comparison["added_edges"]:
            raise ValueError("Supplement added-edge count differs")
        part, evidence = _added_rows(task, graph, audit, source_record, added, prior_identities)
        rows.extend(part)
        proofs.extend(evidence)
        populations[task] = dict(added_edges=len(part), files=sorted({r["file"] for r in part}))
        bindings[task] = dict(graph=entry["graph"], audit=entry["audit"],
            source_task_id=source_record.get("source_task_id"),
            label_version=source_record.get("label_version"))
    if len(rows) != verification["new_edges_outside_review"]:
        raise ValueError("Supplement does not cover all new contract F3 review edges")
    for index, (row, proof) in enumerate(zip(rows, proofs), 1):
        # Keep disjoint identifiers when readers combine original and supplement.
        row["review_id"] = "S{:06d}".format(index)
        proof["review_id"] = row["review_id"]
    sampling = dict(seed=None, tasks=selected, graph_key="F3", relations=[DATA_DEF_USE],
        algorithm="all-added-edges-v1: sorted task/keyed-edge identities; no sampling",
        population="all recovered DATA_DEF_USE additions in original contract review tasks")
    provenance = dict(version=review.VERSION, store=_ref(store_path),
        input_manifest=manifest_ref, task_bindings=bindings, sampling=sampling,
        sampled_files=populations, rows=proofs,
        supplement_to=difference["review"]["seal"],
        equivalence_report=_ref(diff_path), equivalence_verification=verification,
        raw_coordinate_policy="sealed audit UTF-8 byte spans",
        L1_occurrence_policy="statement anchors only; original audit has no identifier occurrence spans",
        grammar_recovered_policy={
            "function_route_recorded": "function route is not proof this edge required grammar recovery",
            "not_recorded": "no edge-level recovery evidence recorded"})
    # Publish only after every edge, source span and evidence record validates.
    output.mkdir(parents=True)
    blank, table = output / "review_sheet.blank.csv", output / "review_sheet.csv"
    content = review._csv_bytes(rows)
    blank.write_bytes(content)
    table.write_bytes(content)
    proof_path = output / "review_sheet.provenance.json"
    write_json(proof_path, provenance)
    seal = dict(version=review.VERSION, csv_sha256=hashlib.sha256(content).hexdigest(),
        blank_csv=dict(path=blank.name, sha256=sha256(blank)),
        provenance=dict(path=proof_path.name, sha256=sha256(proof_path)),
        columns=list(review.COLUMNS), editable_columns=list(review.EDITABLE_COLUMNS),
        sampling=sampling, row_count=len(rows), store_sha256=store_ref["sha256"],
        human_verdicts_filled=False, training_executed=False)
    seal_path = output / "review_sheet.seal.json"
    write_json(seal_path, seal)
    return dict(status="exported_blank_supplement", rows=len(rows),
        tasks=populations, csv=str(table), seal=str(seal_path),
        csv_sha256=seal["csv_sha256"], original_review_unchanged=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", required=True, help="Accepted Prompt 6b store_diff.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(export_supplement(args.diff, args.output), indent=2))


if __name__ == "__main__":
    main()
