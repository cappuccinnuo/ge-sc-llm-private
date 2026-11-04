"""Read-only, sealed Prompt 6b graph equivalence and exact review carry-forward.

No analyzer, tokenizer or model forward runs here. Acceptance is recomputed
from bound graph/audit bytes, not trusted from a report boolean or edge count.
Approved Prompt 6b exception: only DATA_DEF_USE evidence references may be
renumbered, with ordered full evidence identity preserved and remappings logged.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from scripts.DFG.graph_audit import frozen
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.labeling_v2.safe_graph import read_graph
from . import DATA_DEF_USE
from . import store
from .review_sheet import _edge_row, _one_anchor

VERSION = "dfg-v2-store-diff-v3-reference-and-fallback-identity"


def _equal(left, right, message):
    if frozen(left) != frozen(right):
        raise ValueError(message)


def _digest(value):
    return hashlib.sha256(repr(frozen(value)).encode("utf8")).hexdigest()


def _ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def _store_ref(path):
    result = _ref(path)
    result["seal"] = _ref(Path(path).with_name("store.seal.json"))
    return result


def _functions(audit):
    records = {}
    for name, item in audit["files"].items():
        for rec in item.get("analysis", {}).get("functions", []):
            ident = rec["function"]
            if ident in records or rec["file"] != name:
                raise ValueError("Duplicate or misaligned L1 function identity")
            records[ident] = rec
    return records


def _group_evidence(audit, records):
    result = defaultdict(list)
    for item in audit["evidence"]:
        ident = item["function"]
        if ident not in records:
            raise ValueError("L1 evidence references an unknown function")
        result[ident].append(item)
    return result


def _compare_anchors(before, after, recovered, sources):
    """Retain complete old Span/node records; new spans need recovery scope.

    Different spans may legitimately share an HCG node. Compare complete
    records as multisets instead of assuming node_id is an injective key.
    """
    for name, old_file in before["files"].items():
        old = old_file.get("anchors", [])
        new = after["files"][name].get("anchors", [])
        if not isinstance(old, list) or not isinstance(new, list):
            raise ValueError("L1 anchors must be lists")
        old_counts, new_counts = Counter(frozen(a) for a in old), Counter(frozen(a) for a in new)
        if old_counts - new_counts:
            raise ValueError("Old L1 node/Span anchor changed or disappeared: " + name)
        additions = new_counts - old_counts
        if not additions:
            continue
        allowed = [rec for rec in recovered.values() if rec["file"] == name]
        ref = sources[name]
        raw = checked(ref["path"], ref["sha256"]).read_bytes()
        for anchor in new:
            identity = frozen(anchor)
            if additions[identity] <= 0:
                continue
            additions[identity] -= 1
            start, end = anchor.get("start"), anchor.get("end")
            if (anchor.get("file") != name or "node_id" not in anchor
                    or not isinstance(anchor.get("role"), str)
                    or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(raw)):
                raise ValueError("Invalid added L1 node/Span anchor")
            raw[:start].decode("utf8")
            raw[start:end].decode("utf8")
            raw[end:].decode("utf8")
            if not any(rec["start"] <= start < end <= rec["end"] for rec in allowed):
                raise ValueError("New L1 anchor is outside recovered functions: " + name)


def compare_l1(before, after, sources):
    """Compare records and every fact of all non-recovered functions."""
    _equal(before["source_hashes"], after["source_hashes"], "L1 source SHA changed")
    _equal(list(before["files"]), list(after["files"]), "L1 file identities/order changed")
    old, new = _functions(before), _functions(after)
    _equal(list(old), list(new), "L1 function identities/order changed")
    old_facts, new_facts = _group_evidence(before, old), _group_evidence(after, new)
    recovered, unchanged = {}, []
    for ident, rec in old.items():
        updated = new[ident]
        name = rec["file"]
        if rec["status"] == "fallback" and updated["status"] == "supported":
            if old_facts[ident] or rec.get("partial_facts_published") is not False:
                raise ValueError("Recovered function had partial old DDG facts")
            for field in ("function", "file", "start", "end", "line", "name", "old_status", "old_reason"):
                _equal(rec.get(field), updated.get(field), "Recovered function identity changed: " + ident)
            if not updated.get("recovered") or updated.get("legacy_reused") is not False:
                raise ValueError("Recovered function did not use the v2 retry path")
            source = sources[name]
            raw = checked(source["path"], source["sha256"]).read_bytes()
            start, end = rec["start"], rec["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
                raise ValueError("Invalid recovered function source span")
            recovered[ident] = dict(function=ident, file=name, name=rec["name"],
                start=start, end=end, line=rec["line"], source_sha256=source["sha256"],
                source_code=raw[start:end].decode("utf8"), old_reason=rec.get("reason"),
                old_legacy_reason=rec.get("old_reason"), new_routes=updated["routes"],
                new_facts=len(new_facts[ident]), old_status="fallback", new_status="supported")
        else:
            still_fallback = rec["status"] == updated["status"] == "fallback"
            if still_fallback:
                if (type(rec.get("facts")) is not int or rec["facts"] != 0
                        or type(updated.get("facts")) is not int or updated["facts"] != 0
                        or old_facts[ident] or new_facts[ident]
                        or rec.get("partial_facts_published") is not False
                        or updated.get("partial_facts_published") is not False):
                    raise ValueError("Still-fallback function has facts or partial results: " + ident)
                _equal({k:v for k,v in rec.items() if k != "reason"},
                       {k:v for k,v in updated.items() if k != "reason"},
                       "Still-fallback function identity/metadata changed: " + ident)
            else:
                _equal(rec, updated, "Unchanged L1 function record changed: " + ident)
            _equal(old_facts[ident], new_facts[ident], "Unchanged L1 evidence changed: " + ident)
            a = [d for d in before["files"][name].get("diagnostics", []) if d.get("function") == ident]
            b = [d for d in after["files"][name].get("diagnostics", []) if d.get("function") == ident]
            if still_fallback:
                normalized = []
                counts = []
                for diagnostics, record in ((a, rec), (b, updated)):
                    values, count = [], 0
                    for item in diagnostics:
                        if item.get("kind") == "v2_function_fallback":
                            if item.get("reason") != record.get("reason"):
                                raise ValueError("Fallback diagnostic disagrees with function reason: " + ident)
                            count += 1
                            values.append({k:v for k,v in item.items() if k != "reason"})
                        else:
                            values.append(item)
                    normalized.append(values)
                    counts.append(count)
                if rec.get("reason") != updated.get("reason") and counts != [1, 1]:
                    raise ValueError("Changed fallback reason lacks one corresponding diagnostic: " + ident)
                _equal(normalized[0], normalized[1],
                       "Still-fallback non-reason diagnostic changed: " + ident)
            else:
                _equal(a, b, "Unchanged L1 diagnostic changed: " + ident)
            unchanged.append(ident)
    _compare_anchors(before, after, recovered, sources)
    return recovered, unchanged


def _reason_changes(before, after):
    """Called only after compare_l1 has proved empty, nonpartial fallback."""
    old, new = _functions(before), _functions(after)
    result = []
    for ident, rec in old.items():
        updated = new[ident]
        if (rec["status"] == updated["status"] == "fallback"
                and rec.get("reason") != updated.get("reason")):
            name = rec["file"]
            result.append(dict(function=ident, file=name, name=rec["name"],
                start=rec["start"], end=rec["end"], line=rec["line"],
                old_reason=rec.get("reason"), new_reason=updated.get("reason"),
                old_diagnostics=[d for d in before["files"][name].get("diagnostics", [])
                                 if d.get("function") == ident],
                new_diagnostics=[d for d in after["files"][name].get("diagnostics", [])
                                 if d.get("function") == ident],
                status="fallback", old_facts=0, new_facts=0,
                partial_facts_published=False, graph_evidence_unchanged=True))
    return result


def _added_edge(source, target, key, attrs, graph, audit, recovered, sources):
    if attrs.get("edge_type") != DATA_DEF_USE:
        raise ValueError("New edge is not DATA_DEF_USE")
    indices = attrs.get("ddg_fact_indices")
    evidence = audit["evidence"]
    if (not isinstance(indices, list) or not indices or len(indices) != len(set(indices))
            or any(type(i) is not int or i < 0 or i >= len(evidence) for i in indices)):
        raise ValueError("Invalid new edge evidence indices")
    proofs = [evidence[i] for i in indices]
    names = set()
    for item in proofs:
        ident = item["function"]
        if (ident not in recovered or item.get("self_fact") is not False
                or item.get("source") != source or item.get("target") != target):
            raise ValueError("New edge is not proven by a recovered function")
        names.add(recovered[ident]["file"])
    if (len(names) != 1 or graph.nodes[source]["source_file"] not in names
            or graph.nodes[target]["source_file"] not in names or source == target):
        raise ValueError("New edge has inconsistent file/endpoints")
    name = next(iter(names))
    ref = sources[name]
    raw = checked(ref["path"], ref["sha256"]).read_bytes()
    if audit["source_hashes"].get(name) != ref["sha256"]:
        raise ValueError("L1 source audit does not match input")
    anchors = audit["files"][name]["anchors"]
    src = _one_anchor(raw, name, [a for a in anchors if a["node_id"] == source])
    dst = _one_anchor(raw, name, [a for a in anchors if a["node_id"] == target])
    for item in proofs:
        function = recovered[item["function"]]
        if any(not function["start"] <= anchor["start"] < anchor["end"] <= function["end"]
               for anchor in (src, dst)):
            raise ValueError("New edge anchor lies outside its recovered function")
    return dict(source=source, target=target, key=key, relation=DATA_DEF_USE,
        attributes=attrs, file=name, source_sha256=ref["sha256"], source_statement=src,
        target_statement=dst, functions=sorted({p["function"] for p in proofs}),
        old_fallback_reasons={p["function"]:recovered[p["function"]]["old_reason"] for p in proofs},
        evidence=proofs)


def _resolved_l1(attrs, audit, source, target):
    indices = attrs.get("ddg_fact_indices")
    evidence = audit.get("evidence", []) if audit is not None else []
    if (not isinstance(indices, list) or not indices or len(indices) != len(set(indices))
            or any(type(i) is not int or i < 0 or i >= len(evidence) for i in indices)):
        raise ValueError("Invalid old/new L1 evidence reference indices")
    proof = [evidence[i] for i in indices]
    if any(item.get("source") != source or item.get("target") != target
           or item.get("self_fact") is not False for item in proof):
        raise ValueError("Old/new L1 evidence reference has wrong endpoints or self fact")
    return proof


def _compare_edge(attrs, updated, old_l1, new_l1, identity):
    """Only approved reference numbers may differ; no fact normalization."""
    source, target, key = identity
    if attrs.get("edge_type") != DATA_DEF_USE:
        _equal(attrs, updated, "Old edge attributes changed: " + repr(identity))
        return None
    left = {k:v for k,v in attrs.items() if k != "ddg_fact_indices"}
    right = {k:v for k,v in updated.items() if k != "ddg_fact_indices"}
    _equal(left, right, "Old edge nonreference attributes changed: " + repr(identity))
    old_proof = _resolved_l1(attrs, old_l1, source, target)
    new_proof = _resolved_l1(updated, new_l1, source, target)
    _equal(old_proof, new_proof, "Old L1 resolved evidence changed: " + repr(identity))
    old_indices, new_indices = attrs["ddg_fact_indices"], updated["ddg_fact_indices"]
    return dict(source=source, target=target, key=key, relation=DATA_DEF_USE,
        old_indices=old_indices, new_indices=new_indices,
        index_mapping=[dict(old=a, new=b) for a,b in zip(old_indices, new_indices)],
        indices_changed=old_indices != new_indices, resolved_evidence_exact=True,
        evidence_sha256=_digest(old_proof), old_attributes_sha256=_digest(attrs),
        new_attributes_sha256=_digest(updated))


def compare_graphs(old, new, old_audit, new_audit, sources, key):
    """Exact nodes and old keyed edges; only recovered-function DDU additions."""
    _equal(old.graph, new.graph, "Graph attributes changed")
    _equal(list(old.nodes(data=True)), list(new.nodes(data=True)), "Nodes/order/attributes changed")
    if not old.is_multigraph() or not new.is_multigraph():
        raise ValueError("Expected keyed multigraphs")
    a = {(s, t, k):attrs for s, t, k, attrs in old.edges(keys=True, data=True)}
    b = {(s, t, k):attrs for s, t, k, attrs in new.edges(keys=True, data=True)}
    removed = set(a) - set(b)
    if removed:
        raise ValueError("Old keyed edges disappeared: " + str(len(removed)))
    remappings = []
    for ident, attrs in a.items():
        mapping = _compare_edge(attrs, b[ident], old_audit["layers"].get("L1"),
                                new_audit["layers"].get("L1"), ident)
        if mapping is not None and mapping["indices_changed"]:
            remappings.append(mapping)
    _equal(list(a), [e for e in b if e in a], "Old edge iteration order changed")
    old_layers, new_layers = old_audit["layers"], new_audit["layers"]
    _equal(list(old_layers), list(new_layers), "Layer membership/order changed")
    for layer in ("L2", "L3"):
        if layer in old_layers:
            # These derived invariants include the input graph edge count, which
            # legitimately changes when L1 recovers a function. All semantic
            # fields including occurrence evidence/canonical counts stay exact.
            x = {k:v for k,v in old_layers[layer].items() if k != "invariants"}
            y = {k:v for k,v in new_layers[layer].items() if k != "invariants"}
            _equal(x, y, layer + " semantic audit changed")
    recovered, unchanged = ({}, [])
    if "L1" in old_layers:
        recovered, unchanged = compare_l1(old_layers["L1"], new_layers["L1"], sources)
    reason_changes = _reason_changes(old_layers["L1"], new_layers["L1"]) if "L1" in old_layers else []
    additions = [_added_edge(s,t,k,b[(s,t,k)],new,new_layers["L1"],recovered,sources)
                 for s,t,k in b if (s,t,k) not in a]
    if key == "F0" and additions:
        raise ValueError("F0 changed")
    return dict(nodes=len(old), old_edges=len(a), new_edges=len(b), removed_edges=0,
        added_edges=len(additions), added_by_relation=dict(Counter(x["relation"] for x in additions)),
        added=additions, removed=[], l1_reference_remappings=remappings,
        reason_changes=reason_changes,
        recovered_functions=list(recovered.values()),
        unchanged_function_count=len(unchanged), unchanged_function_ids=unchanged,
        invariants=dict(nodes_order_attributes_exact=True,
            old_edge_keys_and_nonreference_attributes_exact=True,
            old_edge_raw_attributes_exact=not remappings,
            old_L1_resolved_evidence_exact=True,
            old_edge_order_exact=True, L2_L3_semantics_exact=True,
            only_recovered_function_DATA_DEF_USE_added=True,
            other_L1_functions_evidence_exact=True))


def _review_rows(seal_path, old_path, old_store, new_store, manifest, comparisons):
    from .score_review import score_review, _read_csv
    seal_path = Path(seal_path).resolve()
    seal = read_json(seal_path)
    # Reuse the complete immutable-table validation; no user verdict is read.
    blank = checked(seal_path.parent / seal["blank_csv"]["path"], seal["blank_csv"]["sha256"])
    score_review(blank, seal_path)
    provenance_ref = seal["provenance"]
    provenance = read_json(checked(seal_path.parent / provenance_ref["path"], provenance_ref["sha256"]))
    if provenance["store"] != _ref(old_path) or seal["store_sha256"] != sha256(old_path):
        raise ValueError("Review does not belong to the old graph store")
    _equal(provenance["input_manifest"], old_store["input_manifest"], "Review input binding differs")
    rows = _read_csv(blank)
    proofs = provenance["rows"]
    if len(rows) != len(proofs):
        raise ValueError("Review row/proof count differs")
    checked_rows, cache = [], {}
    for row, saved in zip(rows, proofs):
        task = row["task"]
        if task not in cache:
            if task not in old_store["tasks"] or task not in new_store["tasks"]:
                raise ValueError("Review task missing from stores")
            if old_store["tasks"][task]["task"] != "contract":
                raise ValueError("Review task is not a contract task")
            pair = []
            for document in (old_store, new_store):
                entry = document["tasks"][task]["graphs"]["F3"]
                graph = read_graph(checked(entry["graph"]["path"], entry["graph"]["sha256"]))
                audit = read_json(checked(entry["audit"]["path"], entry["audit"]["sha256"]))
                pair.append((graph, audit))
            binding = provenance["task_bindings"][task]
            for name in ("graph", "audit"):
                _equal(binding[name], old_store["tasks"][task]["graphs"]["F3"][name],
                       "Review task graph/audit binding differs")
            cache[task] = pair
        name = row["file"]
        ref = manifest["tasks"][task]["sources"][name]
        raw = checked(ref["path"], ref["sha256"]).read_bytes()
        edge = (saved["source_node_id"], saved["target_node_id"], saved["edge_key"])
        derived = []
        for graph, audit in cache[task]:
            if not graph.has_edge(*edge):
                raise ValueError("Review edge no longer exists")
            attrs = graph[edge[0]][edge[1]][edge[2]]
            actual_row, actual_proof = _edge_row(task, graph, audit, ref, raw, edge + (attrs,))
            actual_row["review_id"] = row["review_id"]
            actual_proof["review_id"] = row["review_id"]
            _equal(actual_row, row, "Review CSV does not match bound edge/source")
            if not derived or row["relation"] != DATA_DEF_USE:
                _equal(actual_proof, saved, "Review proof does not match bound edge/source")
            else:
                # The complete resolved fact list, spans and recovery evidence
                # remain exact. Only the L1 global integer references can move.
                _equal({k:v for k,v in actual_proof.items() if k != "evidence_indices"},
                       {k:v for k,v in saved.items() if k != "evidence_indices"},
                       "Review resolved proof does not match bound edge/source")
            derived.append((attrs, actual_proof))
        mapping = _compare_edge(derived[0][0], derived[1][0],
            cache[task][0][1]["layers"].get("L1"),
            cache[task][1][1]["layers"].get("L1"), edge)
        old_indices = derived[0][1]["evidence_indices"]
        new_indices = derived[1][1]["evidence_indices"]
        checked_rows.append(dict(review_id=row["review_id"], task=task, file=name,
            source=edge[0], target=edge[1], key=edge[2], relation=row["relation"],
            old_attributes_sha256=_digest(derived[0][0]),
            new_attributes_sha256=_digest(derived[1][0]), source_sha256=ref["sha256"],
            old_indices=old_indices, new_indices=new_indices,
            index_mapping=[dict(old=a, new=b) for a,b in zip(old_indices, new_indices)],
            indices_changed=mapping["indices_changed"] if mapping is not None else False,
            evidence_sha256=_digest({k:v for k,v in derived[0][1].items()
                                     if k != "evidence_indices"}),
            raw_attributes_unchanged=frozen(derived[0][0]) == frozen(derived[1][0]),
            semantically_unchanged=True))
    # Report additions outside this historical sample, without grading them.
    new_edges = sum(comparisons[t]["F3"]["added_edges"] for t in cache)
    return dict(seal=_ref(seal_path), blank_csv=_ref(blank),
        provenance=_ref(seal_path.parent / provenance_ref["path"]),
        rows_verified=len(checked_rows), rows=checked_rows, tasks=sorted(cache),
        all_reviewed_edges_semantically_unchanged=True,
        only_DATA_DEF_USE_reference_indices_may_differ=True,
        reference_remapping_rows=sum(row["indices_changed"] for row in checked_rows),
        new_F3_edges_in_reviewed_tasks_not_sampled=new_edges,
        scope="Original sealed sample only; newly added edges are not reviewed")


def compare_stores(old_path, new_path, review_seal):
    old_path, new_path = Path(old_path).resolve(), Path(new_path).resolve()
    if old_path == new_path:
        raise ValueError("Old and new store paths must be different")
    for path in (old_path, new_path):
        verification = store.verify_store(path)
        if verification.get("status") != "accepted":
            raise ValueError("Store verification failed")
        checked(path, verification["store_sha256"])
    old, new = read_json(old_path), read_json(new_path)
    _equal(old["input_manifest"], new["input_manifest"], "Store input manifest changed")
    _equal(old["requested_tasks"], new["requested_tasks"], "Store task selection changed")
    _equal(old["saved_graph_keys"], new["saved_graph_keys"], "Store graph-key selection changed")
    _equal(list(old["tasks"]), list(new["tasks"]), "Stored task identities/order changed")
    manifest = read_json(checked(old["input_manifest"]["path"], old["input_manifest"]["sha256"]))
    comparisons = {}
    for task, old_task in old["tasks"].items():
        new_task = new["tasks"][task]
        for field in ("task_id", "category", "task", "input_task_digest", "missing_sources"):
            _equal(old_task[field], new_task[field], "Task identity/input changed: " + task)
        _equal(list(old_task["graphs"]), list(new_task["graphs"]), "Task graph keys changed")
        comparisons[task] = {}
        for key, old_entry in old_task["graphs"].items():
            new_entry = new_task["graphs"][key]
            pair, audits = [], []
            for entry in (old_entry, new_entry):
                pair.append(read_graph(checked(entry["graph"]["path"], entry["graph"]["sha256"])))
                audits.append(read_json(checked(entry["audit"]["path"], entry["audit"]["sha256"])))
            for field in ("version", "pipeline_version", "graph_key", "requested_graph_key",
                          "profiles", "forward_relations", "input_fingerprint",
                          "input_computation_fingerprint", "source_hashes", "missing_sources",
                          "tokenizer", "labels_used_for_analysis", "requested_max_iterations", "parsing"):
                _equal(audits[0].get(field), audits[1].get(field),
                       "Graph analysis input/config changed: " + field)
            comparisons[task][key] = compare_graphs(pair[0], pair[1], audits[0], audits[1],
                manifest["tasks"][task]["sources"], key)
            comparisons[task][key]["old_graph"] = old_entry["graph"]
            comparisons[task][key]["new_graph"] = new_entry["graph"]
            comparisons[task][key]["old_audit"] = old_entry["audit"]
            comparisons[task][key]["new_audit"] = new_entry["audit"]
            del pair, audits
    review = _review_rows(review_seal, old_path, old, new, manifest, comparisons)
    # Each cumulative graph repeats the same L1 recovery; count once per task.
    recovered = {task:rec.get("F1", next(iter(rec.values())))["recovered_functions"]
                 for task, rec in comparisons.items()}
    runtime_old, runtime_new = old.get("runtime", {}), new.get("runtime", {})
    runtime_changes = [dict(path=name, old_sha256=runtime_old.get(name), new_sha256=runtime_new.get(name))
        for name in sorted(set(runtime_old) | set(runtime_new))
        if runtime_old.get(name) != runtime_new.get(name)]
    return dict(version=VERSION, status="accepted", old_store=_store_ref(old_path),
        new_store=_store_ref(new_path), input_manifest=old["input_manifest"],
        tasks=comparisons, recovered_functions_by_task=recovered,
        reason_changes_by_task={task: rec.get("F1", next(iter(rec.values())))["reason_changes"]
                                for task, rec in comparisons.items()},
        recovered_function_count=sum(len(v) for v in recovered.values()),
        added_edges_across_stored_graphs=sum(c["added_edges"] for t in comparisons.values() for c in t.values()),
        removed_edges=0, review=review, runtime_source_changes=runtime_changes,
        layer_audit_comparison="All semantic fields exact; L2/L3 derived invariants excluded",
        old_edge_attribute_policy="Exact keys/nodes/all attributes except approved DATA_DEF_USE reference renumbering; ordered full evidence identity exact",
        fallback_diagnostic_policy="Only reason text and its matching v2_function_fallback diagnostic may change for still-fallback zero-fact nonpartial functions; identity, routes, evidence and anchors remain strict",
        training_executed=False, source_analysis_executed=False)


def write_diff(old_path, new_path, review_seal, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing store-diff output")
    result = compare_stores(old_path, new_path, review_seal)
    output.mkdir(parents=True)
    report = output / "store_diff.json"
    write_json(report, result)
    write_json(output / "store_diff.seal.json", dict(version=VERSION, status="accepted",
        report_sha256=sha256(report), old_store=result["old_store"], new_store=result["new_store"],
        review_seal=result["review"]["seal"], training_executed=False))
    return result


def verify_equivalence(path, review_seal):
    """Recompute comparison to reject forged conclusions even with a new seal."""
    path, review_seal = Path(path).resolve(), Path(review_seal).resolve()
    if path.is_dir():
        path = path / "store_diff.json"
    seal = read_json(path.with_name("store_diff.seal.json"))
    if seal.get("version") != VERSION or seal.get("status") != "accepted":
        raise ValueError("Invalid store-diff seal")
    result = read_json(checked(path, seal["report_sha256"]))
    if result.get("version") != VERSION or result.get("status") != "accepted":
        raise ValueError("Invalid store-diff result")
    _equal(result["review"]["seal"], _ref(review_seal), "Equivalence review seal mismatch")
    for field in ("old_store", "new_store"):
        _equal(seal[field], result[field], "Equivalence store binding mismatch")
        ref = result[field]
        checked(ref["path"], ref["sha256"])
        checked(ref["seal"]["path"], ref["seal"]["sha256"])
    _equal(seal["review_seal"], result["review"]["seal"], "Equivalence seal binding mismatch")
    recomputed = compare_stores(result["old_store"]["path"], result["new_store"]["path"], review_seal)
    _equal(result, recomputed, "Equivalence claims differ from actual artifacts")
    return dict(status="verified", report=_ref(path), report_seal=_ref(path.with_name("store_diff.seal.json")),
        original_store=result["old_store"], scoring_store=result["new_store"],
        rows_verified=result["review"]["rows_verified"],
        new_edges_outside_review=result["review"]["new_F3_edges_in_reviewed_tasks_not_sampled"],
        scoring_scope=result["review"]["scope"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-store", required=True)
    parser.add_argument("--new-store", required=True)
    parser.add_argument("--review-seal", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = write_diff(args.old_store, args.new_store, args.review_seal, args.output)
    print(json.dumps(dict(status=result["status"], tasks=len(result["tasks"]),
        recovered_functions=result["recovered_function_count"],
        added_edges_across_stored_graphs=result["added_edges_across_stored_graphs"],
        reviewed_edges_unchanged=result["review"]["rows_verified"]), indent=2))


if __name__ == "__main__":
    main()
