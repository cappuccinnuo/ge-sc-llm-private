"""Export a sealed, blank manual review of frozen F3 edges.

No analyzer runs here. Raw source coordinates come exclusively from the
stored audit's byte spans, never from preprocessed HCG line numbers.
"""
import argparse
import csv
import hashlib
import io
import json
import random
from pathlib import Path

from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from . import DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW, ENV_SOURCE
from . import store

VERSION = "dfg-v2-manual-review-v1"
RELATIONS = (DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW)
COLUMNS = ("review_id", "task", "file", "relation", "src_line", "src_code",
           "dst_line", "dst_code", "vars_or_key", "via_alias", "spellings",
           "grammar_recovered", "evidence_occurrence_text", "verdict", "note")
EDITABLE_COLUMNS = ("verdict", "note")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _span_record(raw, name, span):
    if span.get("file") != name:
        raise ValueError("Audit span source identity differs")
    start, end = span.get("start"), span.get("end")
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(raw)):
        raise ValueError("Invalid original-source byte span")
    # A byte slice must also begin/end on UTF-8 boundaries.
    raw[:start].decode("utf8")
    text = raw[start:end].decode("utf8")
    raw[end:].decode("utf8")
    first = raw[:start].count(b"\n") + 1
    last = raw[:end - 1].count(b"\n") + 1
    return dict(start=start, end=end, role=span.get("role"),
                line=str(first) if first == last else "{}-{}".format(first, last),
                code=text)


def _one_anchor(raw, name, spans):
    values = {_json(_span_record(raw, name, item)): _span_record(raw, name, item)
              for item in spans}
    if len(values) != 1:
        raise ValueError("Missing or ambiguous exact raw-source node anchor")
    return next(iter(values.values()))


def _proof_for_edge(audit, relation, source, target, attrs):
    layer = "L1" if relation == DATA_DEF_USE else "L3" if relation == ENV_FLOW else "L2"
    key = "ddg_fact_indices" if layer == "L1" else "evidence_indices"
    indices = attrs.get(key)
    if (not isinstance(indices, list) or not indices or len(set(indices)) != len(indices)
            or any(type(i) is not int or i < 0 for i in indices)):
        raise ValueError("Invalid edge evidence indices")
    evidence = audit["layers"][layer]["evidence"]
    try:
        proof = [evidence[i] for i in indices]
    except IndexError:
        raise ValueError("Missing indexed edge evidence")
    for item in proof:
        if item.get("source") != source or item.get("target") != target:
            raise ValueError("Edge/evidence endpoints differ")
        if layer == "L1":
            if item.get("self_fact") is not False:
                raise ValueError("Self fact cannot justify review edge")
        elif item.get("status") != "projected":
            raise ValueError("Unprojected evidence cannot justify review edge")
        if layer == "L2" and item.get("relation") != relation:
            raise ValueError("Edge/evidence relation differs")
        if layer == "L3" and item.get("env_key") != attrs.get("env_key"):
            raise ValueError("Edge/environment key differs")
    return layer, indices, proof


def _recovered(layer_audit, name, proof):
    matches = []
    for item in proof:
        occurrence = item.get("occurrence", {})
        for diag in layer_audit["files"][name].get("diagnostics", []):
            if (diag.get("kind") == "grammar_shape_recovered"
                    and diag.get("callable") == item.get("callable")
                    and diag.get("start") == occurrence.get("start")
                    and diag.get("end") == occurrence.get("end")
                    and diag.get("key") == item.get("env_key")
                    and diag.get("spelling") == item.get("spelling")):
                matches.append(diag)
    return matches


def _edge_row(task, graph, audit, source_ref, raw, edge):
    source, target, key, attrs = edge
    relation = attrs["edge_type"]
    name = graph.nodes[source]["source_file"]
    if name != graph.nodes[target]["source_file"]:
        raise ValueError("Cross-file review edge")
    layer, indices, proof = _proof_for_edge(audit, relation, source, target, attrs)
    layer_audit = audit["layers"][layer]
    if layer_audit.get("source_hashes", {}).get(name) != source_ref["sha256"]:
        raise ValueError("Audit/source SHA differs")
    spans, occurrences, via_alias, spellings = {}, [], False, []
    if relation == DATA_DEF_USE:
        anchors = layer_audit["files"][name]["anchors"]
        spans["source"] = [a for a in anchors if a["node_id"] == source]
        spans["target"] = [a for a in anchors if a["node_id"] == target]
        names = sorted({p["symbol"].rsplit(":", 1)[-1] for p in proof})
    else:
        if any(p.get("file") != name for p in proof):
            raise ValueError("Evidence/source file identity differs")
        statements = [p["statement"] for p in proof]
        if relation == WRITES_STATE:
            spans = dict(source=statements, target=[p["state"] for p in proof])
        elif relation == READS_STATE:
            spans = dict(source=[p["state"] for p in proof], target=statements)
        else:
            if graph.nodes[source].get("node_type") != ENV_SOURCE:
                raise ValueError("Environment source node type differs")
            spans = dict(target=statements)
        occurrences = [_span_record(raw, name, p["occurrence"]) for p in proof]
        via_alias = any(p.get("via_alias", False) for p in proof)
        names = sorted({p["env_key"] if relation == ENV_FLOW else p["state"]["name"]
                        for p in proof})
        spellings = sorted({p["spelling"] for p in proof if "spelling" in p})
    endpoints = {side: _one_anchor(raw, name, items) for side, items in spans.items()}
    if relation == ENV_FLOW:
        endpoints["source"] = dict(line="", code="ENV:" + attrs["env_key"],
                                   role="synthetic_env_source", start=None, end=None)
    recovered = _recovered(layer_audit, name, proof)
    recovery_status = "occurrence_confirmed" if recovered else "not_recorded"
    if layer == "L1" and any("v2_access_shape" in p.get("routes", []) for p in proof):
        recovery_status = "function_route_recorded"
    if relation == DATA_DEF_USE:
        # L1's frozen audit stores statement anchors, not identifier occurrence
        # spans. Label this evidence explicitly; never fabricate token offsets.
        occurrence_text = _json(dict(evidence_scope="statement_anchors",
            definition=endpoints["source"]["code"], use=endpoints["target"]["code"]))
    else:
        occurrence_text = _json(sorted({p["code"] for p in occurrences}))
    row = dict(review_id="", task=task, file=name, relation=relation,
        src_line=endpoints["source"]["line"], src_code=endpoints["source"]["code"],
        dst_line=endpoints["target"]["line"], dst_code=endpoints["target"]["code"],
        vars_or_key=_json(names), via_alias=str(via_alias).lower(),
        spellings=_json(spellings), grammar_recovered=recovery_status,
        evidence_occurrence_text=occurrence_text, verdict="", note="")
    provenance = dict(task=task, file=name, source_sha256=source_ref["sha256"],
        source_path=source_ref["path"], source_node_id=source, target_node_id=target,
        edge_key=key, relation=relation, layer=layer, evidence_indices=indices,
        evidence=proof, endpoints=endpoints, occurrences=occurrences,
        grammar_recovery_evidence=recovered,
        evidence_scope="statement_anchors" if layer == "L1" else "occurrence_bytes")
    return row, provenance


def _sample_task(task, graph, audit, sources, rng, files_per_task, max_edges):
    files = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
    if len(files) < files_per_task:
        raise ValueError("Insufficient task files for requested sample")
    selected = sorted(rng.sample(files, files_per_task))
    rows, proofs, population = [], [], []
    by_file = {name: {rel: [] for rel in RELATIONS} for name in selected}
    for edge in graph.edges(keys=True, data=True):
        source, target, key, attrs = edge
        relation = attrs.get("edge_type")
        name = graph.nodes[source]["source_file"]
        if name in by_file and relation in RELATIONS:
            if graph.nodes[target]["source_file"] != name:
                raise ValueError("Cross-file review edge")
            by_file[name][relation].append(edge)
    for name in selected:
        buckets = by_file[name]
        source_ref = sources.get(name)
        if any(buckets.values()) and source_ref is None:
            raise ValueError("Sampled edge has no frozen source")
        raw = checked(source_ref["path"], source_ref["sha256"]).read_bytes() if source_ref else None
        rec = dict(file=name, source=source_ref, available_edges={}, sampled_edges={})
        for relation in RELATIONS:
            edges = sorted(buckets[relation], key=lambda e: _json([e[0], e[1], e[2]]))
            chosen = sorted(rng.sample(range(len(edges)), min(max_edges, len(edges))))
            rec["available_edges"][relation] = len(edges)
            rec["sampled_edges"][relation] = len(chosen)
            for index in chosen:
                row, proof = _edge_row(task, graph, audit, source_ref, raw, edges[index])
                rows.append(row)
                proofs.append(proof)
        population.append(rec)
    return rows, proofs, population


def export_review(store_path, output, seed=0, files_per_task=15, max_edges=5,
                  task_ids=None):
    """Validate frozen store, sample contract F3 edges, and create a new bundle."""
    for value, name, minimum in ((seed, "seed", 0), (files_per_task, "files_per_task", 1),
                                  (max_edges, "max_edges", 1)):
        if type(value) is not int or value < minimum:
            raise ValueError("Invalid " + name)
    output, store_path = Path(output).resolve(), Path(store_path).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing review output: " + str(output))
    verification = store.verify_store(store_path)
    if verification.get("status") != "accepted":
        raise ValueError("Graph-store verification did not accept")
    checked(store_path, verification["store_sha256"])
    document = read_json(store_path)
    manifest_ref = document["input_manifest"]
    manifest = read_json(checked(manifest_ref["path"], manifest_ref["sha256"]))
    available = sorted(t for t, rec in document["tasks"].items() if rec["task"] == "contract")
    selected = available if task_ids is None else sorted(task_ids)
    if not selected or len(set(selected)) != len(selected) or any(t not in available for t in selected):
        raise ValueError("Manual review accepts unique stored contract tasks only")
    rng, rows, proofs, populations, bindings = random.Random(seed), [], [], {}, {}
    for task in selected:
        entry = document["tasks"][task]["graphs"]["F3"]
        graph = read_graph(checked(entry["graph"]["path"], entry["graph"]["sha256"]))
        audit = read_json(checked(entry["audit"]["path"], entry["audit"]["sha256"]))
        source_record = manifest["tasks"][task]
        if sorted({d["source_file"] for _, d in graph.nodes(data=True)}) != source_record["graph_files"]:
            raise ValueError("Graph/input file population differs")
        part, evidence, population = _sample_task(task, graph, audit,
            source_record["sources"], rng, files_per_task, max_edges)
        rows.extend(part)
        proofs.extend(evidence)
        populations[task] = population
        bindings[task] = dict(graph=entry["graph"], audit=entry["audit"],
                              source_task_id=source_record.get("source_task_id"),
                              label_version=source_record.get("label_version"))
    for index, (row, proof) in enumerate(zip(rows, proofs), 1):
        row["review_id"] = "R{:06d}".format(index)
        proof["review_id"] = row["review_id"]
    sampling = dict(seed=seed, files_per_task=files_per_task, max_edges_per_relation_file=max_edges,
                    tasks=selected, graph_key="F3", relations=list(RELATIONS),
                    algorithm="python-random-v1: sorted tasks/files/edge-identities; sample without replacement")
    provenance = dict(version=VERSION, store=dict(path=str(store_path), sha256=verification["store_sha256"]),
        input_manifest=manifest_ref, task_bindings=bindings, sampling=sampling,
        sampled_files=populations, rows=proofs, raw_coordinate_policy="sealed audit UTF-8 byte spans",
        env_source_line_policy="blank: synthetic node has no original source line",
        L1_occurrence_policy="statement anchors only; original audit has no identifier occurrence spans",
        grammar_recovered_policy={
            "occurrence_confirmed": "exact L3 occurrence/callable/key/spelling diagnostic match",
            "function_route_recorded": "L1 fact belongs to a v2_access_shape function; not proof this edge required recovery",
            "not_recorded": "no edge-level recovery evidence recorded; does not assert no grammar adaptation",
            "L2_limit": "prefix recovery is not recorded by frozen L2 audit; never infer false"})
    # No partially writable export is produced until all rows are validated.
    output.mkdir(parents=True)
    blank = output / "review_sheet.blank.csv"
    table = output / "review_sheet.csv"
    content = _csv_bytes(rows)
    blank.write_bytes(content)
    table.write_bytes(content)
    provenance_path = output / "review_sheet.provenance.json"
    write_json(provenance_path, provenance)
    seal = dict(version=VERSION, csv_sha256=hashlib.sha256(content).hexdigest(),
        blank_csv=dict(path=blank.name, sha256=sha256(blank)),
        provenance=dict(path=provenance_path.name, sha256=sha256(provenance_path)),
        columns=list(COLUMNS), editable_columns=list(EDITABLE_COLUMNS), sampling=sampling,
        row_count=len(rows), store_sha256=verification["store_sha256"],
        human_verdicts_filled=False, training_executed=False)
    write_json(output / "review_sheet.seal.json", seal)
    return dict(status="exported_blank", rows=len(rows), tasks=len(selected),
                sampled_files=sum(len(v) for v in populations.values()),
                csv=str(table), seal=str(output / "review_sheet.seal.json"),
                csv_sha256=seal["csv_sha256"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--files-per-task", type=int, default=15)
    parser.add_argument("--max-edges", type=int, default=5)
    parser.add_argument("--tasks", help="Optional comma-separated contract task IDs")
    args = parser.parse_args(argv)
    print(json.dumps(export_review(args.store, args.output, args.seed, args.files_per_task,
        args.max_edges, args.tasks.split(",") if args.tasks else None), indent=2))


if __name__ == "__main__":
    main()
