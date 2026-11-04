"""Read-only Stage I topology and frozen semantic-evidence diagnostics.

No analyzer replay, graph reconstruction, fitting, feature or label mutation.
Two-hop reachability is an architectural opportunity, never causal proof.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "stage-i-static-evidence-v1"
ROOT = Path(__file__).resolve().parents[4]
STATE_RELATIONS = frozenset(("STATE_DEF_USE", "STATE_ACCESS_ORDER",
                            "EXTERNAL_CALL_BEFORE_STATE_WRITE"))
CONTRASTS = (("E2", "E3a"), ("E2", "E3b"), ("E3a", "E3b"))
HARD = {"reentrancy_author": ("buggy_18.sol", "buggy_36.sol"),
        "access_control_author": ("buggy_18.sol", "buggy_26.sol")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def checked(path, expected, inputs):
    path = Path(path)
    actual = sha(path)
    if actual != expected:
        raise ValueError("Frozen input SHA mismatch: " + str(path))
    if str(path) in inputs and inputs[str(path)] != actual:
        raise ValueError("Conflicting input identity: " + str(path))
    inputs[str(path)] = actual
    return path


def write_csv(path, rows):
    rows = list(rows)
    columns = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list, tuple))
                             else v for k, v in row.items()})


def model_adjacency(graph):
    """Use the exact frozen forward adapter; original graph and attributes unchanged."""
    import networkx as nx
    from scripts.DFG.state.stage_f.model_adapter import build_dgl
    tiny = nx.MultiDiGraph()
    tiny.add_nodes_from((n, {"node_type": a["node_type"]}) for n, a in graph.nodes(data=True))
    tiny.add_edges_from((s, t, {"edge_type": a["edge_type"]}) for s, t, a in graph.edges(data=True))
    dg, ids = build_dgl(tiny)
    inverse = {(a["node_type"], ids[n]): n for n, a in tiny.nodes(data=True)}
    adj = {n: set() for n in tiny}
    pred = {n: set() for n in tiny}
    schema = set(dg.canonical_etypes)
    for canonical in dg.canonical_etypes:
        ss, tt = dg.edges(etype=canonical)
        for si, ti in zip(ss.tolist(), tt.tolist()):
            s, t = inverse[(canonical[0], si)], inverse[(canonical[2], ti)]
            adj[s].add(t)
            pred[t].add(s)
    return adj, pred, schema


def near_two(neighbors, node):
    """Include self to account for HGT residual paths, with at most two message edges."""
    return {node} | neighbors[node] | {v for u in neighbors[node] for v in neighbors[u]}


def raw_edges(graph):
    return Counter((s, t, a["edge_type"]) for s, t, a in graph.edges(data=True))


def context_features(base, enhanced, adjacency=None):
    """Return topology opportunity features for an unchanged node population."""
    if set(base) != set(enhanced):
        raise ValueError("Changed node population")
    old, new = raw_edges(base), raw_edges(enhanced)
    if any(new[k] < count for k, count in old.items()):
        raise ValueError("Removed original edge")
    added = list((new - old).elements())
    if any(r not in STATE_RELATIONS for s, t, r in added):
        raise ValueError("Unexpected added relation")
    if any(base.nodes[s]["source_file"] != base.nodes[t]["source_file"] for s, t, r in added):
        raise ValueError("Cross-file enhancement")
    if adjacency is None:
        a0, p0, s0 = model_adjacency(base)
        a1, p1, s1 = model_adjacency(enhanced)
    else:
        (a0, p0, s0), (a1, p1, s1) = adjacency
    direct = Counter(t for s, t, r in added)
    outgoing = Counter(s for s, t, r in added)
    influence = set(direct)
    for target in direct:
        influence.update(a1[target])
    new_schema = s1 - s0
    destination_types = {c[2] for c in new_schema}
    schema_nodes = {n for n, d in base.nodes(data=True) if d["node_type"] in destination_types}
    schema_scope = set(schema_nodes)
    for n in schema_nodes:
        schema_scope.update(a1[n])
    rows = {}
    for n, data in base.nodes(data=True):
        added_context = near_two(p1, n) - near_two(p0, n)
        classification = ("new_upstream_context" if added_context else
                          "added_relation_but_no_new_upstream_context" if n in influence else
                          "outside_added_edge_two_hop_scope")
        rows[n] = {"original_graph_node_id": n, "file": data["source_file"],
                   "node_type": data["node_type"], "incoming_added_edges": direct[n],
                   "outgoing_added_edges": outgoing[n],
                   "direct_added_relation_target": n in direct,
                   "potential_influence_within_two": n in influence,
                   "new_upstream_count_two": len(added_context),
                   "context_class": classification,
                   "schema_destination_type_exposed": n in schema_nodes,
                   "potential_schema_scope_two": n in schema_scope}
    edge_rows = []
    for s, t, relation in added:
        edge_rows.append({"source_node": s, "target_node": t, "relation": relation,
                          "file": base.nodes[s]["source_file"],
                          "source_type": base.nodes[s]["node_type"],
                          "target_type": base.nodes[t]["node_type"],
                          "baseline_direct_model_pair": t in a0[s],
                          "baseline_reachable_within_two": t in near_two(a0, s)})
    return rows, edge_rows, sorted(new_schema)


def pred_key(row):
    return (row["file"], json.dumps(row.get("original_graph_node_id"), sort_keys=True))


def validate_predictions(rows, info, graph, sources, labels):
    """Bind source, cohort, node IDs, target, model row and validation fold."""
    from scripts.DFG.experiments.paper_protocol import validate_document
    splits = read(info["source_splits_path"])
    validate_document(splits)
    folds = {}
    for split in splits["folds"]:
        for file in split["val_files"]:
            if file in folds:
                raise ValueError("Repeated validation file")
            folds[file] = split["fold"]
    graph_files = {d["source_file"] for _, d in graph.nodes(data=True)}
    if set(folds) != graph_files:
        raise ValueError("Fold population mismatch")
    expected = {}
    if info["task"] == "node":
        for model_id, (node, d) in enumerate(graph.nodes(data=True)):
            expected[(d["source_file"], json.dumps(node, sort_keys=True))] = {
                "target": int(d["node_info_vulnerabilities"] is not None),
                "node_type": d["node_type"], "model_node_id": model_id}
    else:
        expected = {(f, "null"): {"target": labels[f]} for f in graph_files}
    index = {}
    for row in rows:
        key = pred_key(row)
        if key in index or key not in expected:
            raise ValueError("Duplicate or unknown prediction identity")
        if row["task_id"] != info["task_id"] or row["cohort"] != info["cohort"]:
            raise ValueError("Prediction cohort/task mismatch")
        if row["source_sha256"] != sources[row["file"]]["sha256"]:
            raise ValueError("Prediction source SHA mismatch")
        if row["score_role"] != "cv_validation" or row["fold"] != folds[row["file"]]:
            raise ValueError("Prediction scoring/fold mismatch")
        if any(row.get(k) != value for k, value in expected[key].items()):
            raise ValueError("Prediction target/node identity mismatch")
        index[key] = row
    if set(index) != set(expected):
        raise ValueError("Missing prediction population")
    return index


def compare_prediction(a, b):
    if a["target"] != b["target"] or a["source_sha256"] != b["source_sha256"]:
        raise ValueError("Mismatched paired prediction")
    before, after, y = a["best"], b["best"], a["target"]
    status = ("corrected" if before != y and after == y else
              "regressed" if before == y and after != y else
              "both_correct" if before == y else "both_wrong")
    delta = b["best_positive_probability"] - a["best_positive_probability"]
    return {"fold": a["fold"], "target": y, "before_best": before, "after_best": after,
            "prediction_changed": before != after, "status": status,
            "before_probability": a["best_positive_probability"],
            "after_probability": b["best_positive_probability"],
            "probability_delta": delta, "probability_changed": abs(delta) > 1e-8}


def _delivered(path, delivery, inputs, root):
    relative = str(Path(path).relative_to(root))
    record = delivery["files"].get(relative)
    if not record:
        raise ValueError("Semantic evidence not present in Stage F delivery: " + relative)
    return checked(path, record["sha256"], inputs)


def _csv(path):
    with Path(path).open(encoding="utf8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_missing(row):
    value = row.get("missing_anchors")
    return json.loads(value) if value else []


def audit_count(row, key):
    value = row.get(key)
    return int(value) if value not in (None, "") else None


def compact_evidence(proof, sources, source_bytes):
    file = proof["definition"]["anchor"]["file"]
    if proof["source_sha256"] != sources[file]["sha256"]:
        raise ValueError("Semantic proof source mismatch")
    def anchor(item):
        a = item["anchor"]
        if a["file"] != file:
            raise ValueError("Cross-source semantic proof")
        body = source_bytes[file]
        if not 0 <= a["start"] <= a["end"] <= len(body):
            raise ValueError("Invalid frozen source anchor")
        return {"start_byte": a["start"], "end_byte": a["end"], "role": a["role"],
                "source_start_line": body[:a["start"]].count(b"\n") + 1,
                "source_end_line": body[:max(a["start"], a["end"]-1)].count(b"\n") + 1,
                "event_kind": item["kind"], "event_id": item["id"]}
    return {"function": proof["function"], "certainty": proof["certainty"],
            "source_anchor": anchor(proof["definition"]), "target_anchor": anchor(proof["use"]),
            "path_status": proof.get("path_status", "reaching_definitions_may_fact"),
            "cfg_witness": proof.get("cfg_witness", []),
            "unknown_call_events": proof.get("unknown_call_events", [])}


def produce_evidence(h2_output, output_dir, task_infos=None):
    """Write new static evidence only. Existing output is always rejected."""
    from scripts.labeling_v2.safe_graph import read_graph
    from scripts.DFG.graph_audit import frozen
    from scripts.DFG.experiments.common import digest
    h2_output, output_dir = Path(h2_output), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Refuse existing static output: " + str(output_dir))
    inputs = {}
    delivery_path = h2_output / "delivery_manifest.json"
    inputs[str(delivery_path)] = sha(delivery_path)
    delivery = read(delivery_path)
    def h2_file(name):
        return checked(h2_output/name, delivery["top_level_delivery_sha256"][name], inputs)
    plan = read(h2_file("plan.json"))
    report = read(h2_file("report.json"))
    if report["status"] != "complete" or report["complete_three_variants"] != 90:
        raise ValueError("Incomplete H2 baseline")
    oof = read(h2_file("oof_predictions.json"))
    # Independently check all accepted task manifests share the same fixed graph/labels.
    infos = {}
    for job in plan["jobs"]:
        p = checked(job["task_manifest"], job["task_manifest_sha256"], inputs)
        info = read(p)
        signature = {k: info[k] for k in ("task_id", "cohort", "task", "graphs",
                    "source_prepared_manifest", "source_prepared_manifest_sha256",
                    "source_splits_path", "source_splits_sha256", "labels_path", "labels_sha256")}
        if job["task_id"] in infos and infos[job["task_id"]][1] != signature:
            raise ValueError("Task inputs drift between folds")
        if job["fold"] == 0 or job["task_id"] not in infos:
            infos[job["task_id"]] = (info, signature)
    if task_infos is not None:
        supplied = {i["task_id"]: i for i in task_infos}
        if set(supplied) != set(infos) or any(supplied[k] != v[0] for k, v in infos.items()):
            raise ValueError("Supplied task infos differ from frozen fold0 manifests")
    all_nodes, all_edges, all_files, all_missing, all_functions, all_pred = [], [], [], [], [], []
    focus, summaries = [], []
    for task_id, (info, _) in infos.items():
        if info["config"]["layers"] != 2:
            raise ValueError("Static opportunity definition requires frozen two-layer HGT")
        prep = read(checked(info["source_prepared_manifest"],
                            info["source_prepared_manifest_sha256"], inputs))
        checked(info["source_splits_path"], info["source_splits_sha256"], inputs)
        labels = {x["contract_name"]: int(x["targets"]) for x in
                  read(checked(info["labels_path"], info["labels_sha256"], inputs))}
        graphs = {v: read_graph(checked(x["path"], x["sha256"], inputs))
                  for v, x in info["graphs"].items()}
        base = graphs["E2"]
        files = {a["source_file"] for _, a in base.nodes(data=True)}
        sources = prep["sources"]
        source_bytes = {file: checked(sources[file]["path"], sources[file]["sha256"], inputs).read_bytes()
                        for file in files}
        for variant, graph in graphs.items():
            if digest(frozen(list(graph.nodes(data=True)))) != info["graphs"][variant]["node_attributes_sha256"]:
                raise ValueError("Node attributes do not match frozen manifest")
            if frozen(list(graph.nodes(data=True))) != frozen(list(base.nodes(data=True))):
                raise ValueError("Variants changed node identities/features/labels")
        fp = [Path(p) for p in info["frozen_files"] if Path(p).name == "GRAPH_MANIFEST.json"]
        if len(fp) != 1:
            raise ValueError("Ambiguous Stage F graph manifest")
        gm_path = checked(fp[0], info["frozen_files"][str(fp[0])], inputs)
        stage_f = gm_path.parent.parent
        fdelivery_path = stage_f / "DELIVERY_MANIFEST.json"
        inputs[str(fdelivery_path)] = sha(fdelivery_path)
        fdelivery = read(fdelivery_path)
        proof_path = _delivered(gm_path.parent/"F3_EDGE_PROVENANCE.json", fdelivery, inputs, ROOT)
        projection_path = _delivered(gm_path.parent/"F2_PROJECTION_AUDIT.csv", fdelivery, inputs, ROOT)
        support_path = _delivered(stage_f/"F1_attempt_002/F1_SUPPORT_BEFORE_AFTER.csv", fdelivery, inputs, ROOT)
        proofs = next(x["evidence"] for x in read(proof_path) if x["cohort"] == info["cohort"])
        by_edge = defaultdict(list)
        for index, proof in enumerate(proofs):
            s, t, rel = proof["source_node"], proof["target_node"], proof["relation"]
            if s not in base or t not in base:
                continue  # Contract graph proofs excluded by the frozen buggy-only node view.
            file = base.nodes[s]["source_file"]
            if base.nodes[t]["source_file"] != file:
                raise ValueError("Cross-file projected proof")
            compact = compact_evidence(proof, sources, source_bytes)
            compact["stage_f_provenance_index"] = index
            by_edge[(s, t, rel)].append(compact)
        projection = {x["file"]: x for x in _csv(projection_path)
                      if x["cohort"] == info["cohort"] and x["file"] in files}
        support = defaultdict(list)
        for row in _csv(support_path):
            if row["cohort"] == info["cohort"] and row["file"] in files:
                support[row["file"]].append(row)
                all_functions.append(dict(row, task_id=task_id,
                    source_sha256=sources[row["file"]]["sha256"],
                    association_scope="function_id_from_frozen_analyzer_not_guessed_HCG_membership"))
        for file, row in projection.items():
            for missing in audit_missing(row):
                all_missing.append(dict(missing, task_id=task_id, cohort=info["cohort"],
                    source_sha256=sources[file]["sha256"],
                    association_scope="source_anchor_only_no_existing_HCG_endpoint",
                    source_start_line=source_bytes[file][:missing["start"]].count(b"\n")+1))
        indexes = {}
        for v in ("E2", "E3a", "E3b"):
            rows = [x for x in oof if x["task_id"] == task_id and x["variant"] == v]
            indexes[v] = validate_predictions(rows, info, base, sources, labels)
        adjacency = {v: model_adjacency(g) for v, g in graphs.items()}
        for before, after in CONTRASTS:
            contrast = after + "-" + before
            prefix = {"task_id": task_id, "cohort": info["cohort"], "contrast": contrast}
            contexts, edges, new_schema = context_features(
                graphs[before], graphs[after], (adjacency[before], adjacency[after]))
            file_context = defaultdict(list)
            for n, row in contexts.items():
                row = dict(prefix, **row, source_sha256=sources[row["file"]]["sha256"])
                row["stored_graph_source_lines"] = base.nodes[n].get("node_source_code_lines")
                row["stored_lines_coordinate_warning"] = "preserved_graph_coordinates_not_inferred_original_lines"
                all_nodes.append(row)
                file_context[row["file"]].append(row)
            for edge in edges:
                key = (edge["source_node"], edge["target_node"], edge["relation"])
                if key not in by_edge:
                    raise ValueError("Added model edge has no frozen semantic proof")
                all_edges.append(dict(prefix, **edge, source_sha256=sources[edge["file"]]["sha256"],
                    semantic_evidence=by_edge[key], human_approved=False,
                    interpretation="typed_relation_and_topological_opportunity_not_causal_proof"))
            perfile_pred = defaultdict(list)
            for identity, a in indexes[before].items():
                b = indexes[after][identity]
                row = dict(prefix, file=a["file"], source_sha256=a["source_sha256"],
                           score_role="cv_validation", checkpoint="best", **compare_prediction(a, b))
                row["original_graph_node_id"] = a.get("original_graph_node_id")
                row["metric_unit"] = "HCG node" if info["task"] == "node" else "file/contract label"
                if info["task"] == "node":
                    ctx = contexts[a["original_graph_node_id"]]
                    row.update({k: v for k, v in ctx.items() if k not in row})
                    row["change_outside_added_edge_scope"] = row["prediction_changed"] and not ctx["potential_influence_within_two"]
                else:
                    row["potentially_affected_nodes_in_file"] = sum(x["potential_influence_within_two"] for x in file_context[a["file"]])
                    row["new_context_nodes_in_file"] = sum(x["new_upstream_count_two"] > 0 for x in file_context[a["file"]])
                perfile_pred[a["file"]].append(row)
                all_pred.append(row)
            task_files = []
            for file in sorted(files):
                nodes, pred = file_context[file], perfile_pred[file]
                audit = projection.get(file, {})
                fns = support[file]
                row = dict(prefix, file=file, source_sha256=sources[file]["sha256"],
                    nodes=len(nodes), predictions=len(pred), score_role="cv_validation",
                    added_edges=sum(e["file"] == file for e in edges),
                    direct_targets=sum(n["direct_added_relation_target"] for n in nodes),
                    potential_influence_nodes=sum(n["potential_influence_within_two"] for n in nodes),
                    new_context_nodes=sum(n["new_upstream_count_two"] > 0 for n in nodes),
                    schema_destination_type_nodes=sum(n["schema_destination_type_exposed"] for n in nodes),
                    corrected=sum(x["status"] == "corrected" for x in pred),
                    regressed=sum(x["status"] == "regressed" for x in pred),
                    before_errors=sum(x["before_best"] != x["target"] for x in pred),
                    after_errors=sum(x["after_best"] != x["target"] for x in pred),
                    class_changes=sum(x["prediction_changed"] for x in pred),
                    probability_changes=sum(x["probability_changed"] for x in pred),
                    missing_anchor_count=len(audit_missing(audit)) if audit.get("missing_anchors") else None,
                    missing_anchor_reporting_available=bool(audit.get("missing_anchors")),
                    eligible_relations_all_stage_f=audit_count(audit, "eligible_relations"),
                    projected_facts_all_stage_f=audit_count(audit, "projected_facts"),
                    self_facts_all_stage_f=audit_count(audit, "self_facts"),
                    function_status_counts=dict(Counter(x["after"] for x in fns)),
                    fallback_reasons=dict(Counter(x["reason"] for x in fns if x["reason"])),
                    file_projection_fallback=audit.get("file_projection_fallback", ""),
                    semantic_audit_scope="all_state_relations_in_file_not_contrast_specific",
                    missing_anchor_link_scope="file_only_no_nearest_line_guess",
                    zero_materialized_edges_does_not_prove_no_dependency=True)
                all_files.append(row)
                task_files.append(row)
            selected = {}
            for row in task_files:
                if row["file"] in HARD[info["cohort"]]:
                    selected.setdefault(row["file"], []).append("prespecified_difficult_file")
                if row["class_changes"]:
                    selected.setdefault(row["file"], []).append("all_files_with_changed_best_prediction")
            for role, condition in (
                ("lexicographic_correct_control_with_relation", lambda x: x["before_errors"] == x["after_errors"] == 0 and x["added_edges"] > 0),
                ("lexicographic_correct_control_without_relation", lambda x: x["before_errors"] == x["after_errors"] == 0 and x["added_edges"] == 0)):
                choice = next((x for x in task_files if condition(x)), None)
                if choice:
                    selected.setdefault(choice["file"], []).append(role)
            for row in task_files:
                if row["file"] in selected:
                    focus.append(dict(row, selection_roles=selected[row["file"]],
                                      selection_is_descriptive_not_new_test_set=True))
            task_pred = [x for rows in perfile_pred.values() for x in rows]
            summaries.append(dict(prefix, nodes=len(base), files=len(files), added_edges=len(edges),
                added_relations=dict(Counter(e["relation"] for e in edges)),
                direct_targets=sum(x["direct_added_relation_target"] for x in contexts.values()),
                potential_influence_nodes=sum(x["potential_influence_within_two"] for x in contexts.values()),
                new_context_nodes=sum(x["new_upstream_count_two"] > 0 for x in contexts.values()),
                new_upstream_pairs=sum(x["new_upstream_count_two"] for x in contexts.values()),
                baseline_reachable_added_edges=sum(x["baseline_reachable_within_two"] for x in edges),
                new_canonical_relations=new_schema,
                prediction_status_counts=dict(Counter(x["status"] for x in task_pred)),
                prediction_changes=sum(x["prediction_changed"] for x in task_pred),
                probability_changes=sum(x["probability_changed"] for x in task_pred),
                changes_outside_added_edge_scope=sum(x.get("change_outside_added_edge_scope", False) for x in task_pred),
                interpretations=["potential_influence is at most two directed message hops after an added edge",
                    "new_context is new upstream node identity, not new learned semantic information",
                    "existing typed edges can change computation even when upstream identity was already reachable",
                    "schema mean aggregation and separately fitted shared weights can affect nodes outside local edge scope",
                    "no observed change here establishes semantic causality"]))
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, rows in (("node_evidence.csv", all_nodes), ("edge_evidence.csv", all_edges),
                       ("file_evidence.csv", all_files), ("projection_missing_anchors.csv", all_missing),
                       ("function_support.csv", all_functions), ("prediction_evidence.csv", all_pred),
                       ("focus_cases.csv", focus)):
        write_csv(output_dir/name, rows)
    result = {"version": VERSION, "status": "complete", "training_executed": False,
              "analyzer_replayed": False, "graph_mutated": False, "tasks": summaries,
              "semantic_sidecar_assurance": "Stage F sidecar contents match its historical DELIVERY_MANIFEST; the delivery manifest is recorded by this Stage I read, not claimed to be protected by the H1/H2 frozen-file seal. Graph identity is independently bound to H2 task manifests.",
              "node_context_rows": len(all_nodes), "edge_rows": len(all_edges),
              "prediction_rows": len(all_pred), "focus_rows": len(focus),
              "missing_anchor_records": len(all_missing), "inputs": inputs,
              "limits": ["Semantic proofs are inherited frozen analyzer evidence, not newly human-approved.",
                  "Source labels are preserved, not reassessed.",
                  "Projection misses link to source anchors/files, never guessed to an HCG node.",
                  "Function support remains keyed by exact analyzer function identity.",
                  "Separate-fit probability changes are not direct edge causal effects.",
                  "CV validation was used to select checkpoints; this is not an independent test."]}
    with (output_dir/"summary.json").open("x", encoding="utf8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    # Check every input remained byte-identical during the read-only analysis.
    for path, expected in inputs.items():
        checked(path, expected, {})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--h2-output", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = produce_evidence(args.h2_output, args.output)
    print(json.dumps({k: v for k, v in result.items() if k not in ("inputs", "tasks")}, indent=2))


if __name__ == "__main__":
    main()
