"""Read-only D1 diagnostics for archived DDG experiments (Codex, 2026-10-13)."""
import argparse
import ast
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.experiments.common import code_hashes
from scripts.DFG.graph_audit import assert_augmented, fingerprint
from scripts.DFG.experiments.prepare import positive
DDG = "DATA_DEF_USE"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def dump(path, obj):
    p = Path(path)
    if p.exists():
        raise FileExistsError(str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=True, indent=2) + "\n", encoding="utf8")


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                        for k, v in row.items()})


def checked(path, expected, inputs):
    p = Path(path)
    actual = sha(p)
    if actual != expected:
        raise ValueError("Input hash mismatch: " + str(p))
    inputs[str(p)] = actual
    return p


def resolved_tasks(run, inputs):
    plan, state = read(run / "plan.json"), read(run / "state.json")
    inputs[str(run / "plan.json")] = sha(run / "plan.json")
    inputs[str(run / "state.json")] = sha(run / "state.json")
    groups = {}
    for job in plan["jobs"]:
        entry = state["jobs"][job["id"]]
        if entry["status"] != "passed":
            raise ValueError("Unaccepted job " + job["id"])
        receipt_path = checked(run / entry["receipt"], entry["receipt_sha256"], inputs)
        receipt = read(receipt_path)
        if receipt["acceptance"]["status"] != "passed":
            raise ValueError("Rejected receipt")
        key = job["cohort"] + "_" + job["task"]
        groups.setdefault(key, {"cohort": job["cohort"], "task": job["task"],
                                "prepared": Path(job["prepared"]), "jobs": []})
        groups[key]["jobs"].append(dict(job, attempt=run / entry["attempt"], receipt=receipt))
    return groups


def load_pair(group, inputs):
    prepared = group["prepared"]
    manifest_path = prepared / "manifest.json"
    manifest = read(manifest_path)
    inputs[str(manifest_path)] = sha(manifest_path)
    audit_info = manifest["ddg_audit"]
    audit = read(checked(prepared / audit_info["path"], audit_info["sha256"], inputs))
    graphs = {}
    for variant in ("E0", "E1"):
        info = manifest["graphs"][variant][group["task"]]
        graphs[variant] = read_graph(checked(prepared / info["path"], info["sha256"], inputs))
    assert_augmented(graphs["E0"], graphs["E1"])
    return manifest, audit, graphs["E0"], graphs["E1"]


def edge_functions(graph, evidence):
    """No labels/text heuristics; only frozen DDG fact identities."""
    edges, functions = [], defaultdict(set)
    for s, t, k, d in graph.edges(keys=True, data=True):
        if d["edge_type"] != DDG:
            continue
        ev = [evidence[i] for i in d["ddg_fact_indices"]]
        if not ev or any(e["source"] != s or e["target"] != t for e in ev):
            raise ValueError("DDG evidence endpoint mismatch")
        fs = sorted({e["function"] for e in ev})
        sf, tf = graph.nodes[s]["source_file"], graph.nodes[t]["source_file"]
        if sf != tf or any(not f.startswith(sf + ":") for f in fs):
            raise ValueError("DDG fact function/file mismatch")
        functions[s].update(fs)
        functions[t].update(fs)
        edges.append({"source": s, "target": t, "key": k, "file": sf,
                      "canonical": [graph.nodes[s]["node_type"], DDG, graph.nodes[t]["node_type"]],
                      "functions": fs, "function": fs[0] if len(fs) == 1 else None})
    nodes = [{"node_id": n, "file": d["source_file"], "node_type": d["node_type"],
              "function": next(iter(functions[n])) if len(functions[n]) == 1 else None,
              "functions": sorted(functions[n])}
             for n, d in graph.nodes(data=True)]
    return {"edges": edges, "nodes": nodes,
            "ambiguous_edges": sum(e["function"] is None for e in edges),
            "ambiguous_nodes": sum(len(n["functions"]) > 1 for n in nodes),
            "meaning": "Unique frozen projected-fact function identity; nodes with no facts are null."}


def make_edge_functions(groups, inputs):
    result = {"schema": 1, "source": "Frozen DDG evidence side tables", "tasks": {}}
    for key, group in groups.items():
        _, audit, _, enhanced = load_pair(group, inputs)
        result["tasks"][key] = edge_functions(enhanced, audit["evidence"])
    return result


def model_adjacency(graph):
    """Materialize topology via the exact production reflection helper, on a copy."""
    import networkx as nx
    import sco_models.graph_utils as gu
    tiny = nx.MultiDiGraph()
    tiny.add_nodes_from((n, {"node_type": d["node_type"]}) for n, d in graph.nodes(data=True))
    tiny.add_edges_from((s, t, {"edge_type": d["edge_type"]}) for s, t, d in graph.edges(data=True))
    gu.add_hetero_ids(tiny)
    by_type = gu.get_node_ids_dict(tiny)
    relations = gu.reflect_graph(gu.generate_hetero_graph_data(tiny))
    adj, pred = {n: set() for n in graph}, {n: set() for n in graph}
    canonical_counts = {}
    for c, (src, dst) in relations.items():
        canonical_counts[c] = len(src)
        for si, ti in zip(src.tolist(), dst.tolist()):
            s, t = by_type[c[0]][si], by_type[c[2]][ti]
            adj[s].add(t)
            pred[t].add(s)
    return adj, pred, canonical_counts


def neighborhood_two(neighbors, node):
    one = neighbors[node]
    return {node} | one | {v for u in one for v in neighbors[u]}


def distances(adj, source):
    dist, queue = {source: 0}, deque([source])
    while queue:
        n = queue.popleft()
        for t in adj[n]:
            if t not in dist:
                dist[t] = dist[n] + 1
                queue.append(t)
    return dist


def edge_increment(base, enhanced, key, output):
    adj, pred, canon0 = model_adjacency(base)
    aug, apred, canon1 = model_adjacency(enhanced)
    ddg = [(s, t, d) for s, t, d in enhanced.edges(data=True) if d["edge_type"] == DDG]
    by_src = defaultdict(list)
    for s, t, d in ddg:
        by_src[s].append(t)
    edge_rows, categories = [], Counter()
    for s, targets in by_src.items():
        ds = distances(adj, s)
        for t in targets:
            d = ds.get(t)
            bucket = "unreachable" if d is None else "0" if d == 0 else str(d) if d <= 2 else ">2"
            categories[bucket] += 1
            edge_rows.append({"task_key": key, "file": base.nodes[s]["source_file"],
                              "source": s, "target": t, "source_type": base.nodes[s]["node_type"],
                              "target_type": base.nodes[t]["node_type"], "basis": "model_reflected_E0",
                              "distance_bucket": bucket, "direct_base_pair": int(t in adj[s]),
                              "raw_direct_base_pair": int(base.has_edge(s, t))})
    direct_in, direct_out = Counter(t for s, t, d in ddg), Counter(s for s, t, d in ddg)
    influence = set(direct_in)
    for t in direct_in:
        influence.update(aug[t])
    node_rows, features = [], {}
    for n, data in base.nodes(data=True):
        new = neighborhood_two(apred, n) - neighborhood_two(pred, n)
        row = {"task_key": key, "file": data["source_file"], "node_id": n,
               "node_type": data["node_type"], "label": positive(data),
               "ddg_in": direct_in[n], "ddg_out": direct_out[n],
               "ddg_affected_within_two": int(n in influence),
               "new_upstream_count_two": len(new)}
        node_rows.append(row)
        features[n] = row
    write_csv(output / (key + "_edges.csv"), edge_rows)
    write_csv(output / (key + "_node_context.csv"), node_rows)
    summary = {"task_key": key, "basis": "exact_model_reflect_graph",
               "nodes": len(base), "ddg_edges": len(ddg),
               "distance_buckets": dict(categories),
               "nodes_with_new_upstream_two": sum(r["new_upstream_count_two"] > 0 for r in node_rows),
               "new_upstream_pairs_two": sum(r["new_upstream_count_two"] for r in node_rows),
               "nodes_receiving_ddg_within_two": len(influence),
               "canonical_E0": len(canon0), "canonical_E1": len(canon1),
               "meaning": "Reachability with residual self included; not learned semantic equivalence."}
    return summary, features


def exact_duplicate_groups(graph, train_files, val_files, key_function):
    """Build on train only; return matches before examining any val targets."""
    train, val = set(train_files), set(val_files)
    if train & val:
        raise ValueError("Train/val overlap")
    index = defaultdict(list)
    for n, d in graph.nodes(data=True):
        if d["source_file"] in train:
            index[key_function(d)].append(n)
    return [(n, tuple(index.get(key_function(d), ())))
            for n, d in graph.nodes(data=True) if d["source_file"] in val]


def feature_key(data):
    a = np.asarray(data["token"])
    if a.dtype != np.float32 or a.shape != (512,) or not np.isfinite(a).all():
        raise ValueError("Not actual finite float32[512]")
    return a.tobytes()


def code_key(data):
    code = data.get("code")
    if code is not None and not isinstance(code, str):
        raise ValueError("Non-string stored code")
    return (type(code).__name__, code)


def compare_status(a, b, label):
    if a == label and b == label:
        return "both_correct"
    if a != label and b == label:
        return "E1_corrects"
    if a == label and b != label:
        return "E1_new_error"
    return "both_wrong"


def load_predictions(job, variant, inputs):
    relative = "fold_{}/{}/cv_validation_predictions.json".format(job["fold"], variant)
    expected = job["receipt"]["artifacts"][relative]
    return read(checked(job["attempt"] / relative, expected, inputs))


def duplicates_and_errors(group, graph, contexts, node_function, inputs, output):
    key = group["cohort"] + "_" + group["task"]
    dup_summary, dup_nodes, errors, support = [], [], [], []
    for job in group["jobs"]:
        split_path = Path(job["splits"])
        inputs[str(split_path)] = sha(split_path)
        splitdoc = read(split_path)
        split = next(s for s in splitdoc["folds"] if s["fold"] == job["fold"])
        if splitdoc["score_role"] != "cv_validation":
            raise ValueError("Unexpected score role")
        rows0, rows1 = load_predictions(job, "E0", inputs), load_predictions(job, "E1", inputs)
        def identity(row):
            return (row["file"], row.get("original_graph_node_id")) if group["task"] == "node" else row["file"]
        r0, r1 = {identity(r): r for r in rows0}, {identity(r): r for r in rows1}
        if len(r0) != len(rows0) or set(r0) != set(r1):
            raise ValueError("Prediction identity mismatch")
        node_status = {}
        for ident, row in r0.items():
            other = r1[ident]
            if row["target"] != other["target"]:
                raise ValueError("Prediction targets mismatch")
            nodes = [row["original_graph_node_id"]] if group["task"] == "node" else [
                n for n, d in graph.nodes(data=True) if d["source_file"] == row["file"]]
            status = compare_status(row["best"], other["best"], row["target"])
            for n in nodes:
                if graph.nodes[n]["source_file"] != row["file"]:
                    raise ValueError("Original ID/file mismatch")
                if group["task"] == "node" and positive(graph.nodes[n]) != row["target"]:
                    raise ValueError("Original node target mismatch")
                if group["task"] == "node":
                    node_status[n] = status
                ctx = contexts[n]
                errors.append(dict(ctx, fold=job["fold"], function=node_function.get(n),
                                   prediction_unit=group["task"], score_role="cv_validation",
                                   prediction_target=row["target"], E0_best=row["best"],
                                   E1_best=other["best"], status=status))
        for name, getter in (("stored_code_exact", code_key), ("float32_512_exact", feature_key)):
            matched = exact_duplicate_groups(graph, split["train_files"], split["val_files"], getter)
            counts = Counter()
            label_sets_after_lookup = {}
            for n, train_nodes in matched:
                target = positive(graph.nodes[n])
                # Labels are consulted only after immutable train index lookup.
                if train_nodes not in label_sets_after_lookup:
                    label_sets_after_lookup[train_nodes] = {positive(graph.nodes[t]) for t in train_nodes}
                labels = label_sets_after_lookup[train_nodes]
                row = {"task_key": key, "fold": job["fold"], "basis": name,
                       "file": graph.nodes[n]["source_file"], "node_id": n, "target": target,
                       "matched_train_nodes": len(train_nodes), "matched": int(bool(train_nodes)),
                       "train_label_conflict": int(len(labels) > 1),
                       "has_same_label_train": int(target in labels),
                       "has_opposite_label_train": int((1 - target) in labels),
                       "status": node_status.get(n, "not_node_task")}
                dup_nodes.append(row)
                counts["val_nodes"] += 1
                for field in ("matched", "train_label_conflict", "has_same_label_train", "has_opposite_label_train"):
                    counts[field] += row[field]
                counts["matched_positive"] += int(bool(train_nodes) and target == 1)
                counts["matched_negative"] += int(bool(train_nodes) and target == 0)
            dup_summary.append(dict(counts, task_key=key, fold=job["fold"], basis=name,
                                    denominator="all validation graph nodes; even for contract task"))
        relpath = "fold_{}/E1/gradient_audit.json".format(job["fold"])
        grad = read(checked(job["attempt"] / relpath, job["receipt"]["artifacts"][relpath], inputs))
        records = defaultdict(list)
        for epoch in grad["epochs"]:
            for relation in epoch["ddg_relations"]:
                records[tuple(relation["canonical"])].append(relation)
        for canonical, values in records.items():
            support.append({"task_key": key, "fold": job["fold"], "canonical": list(canonical),
                            "train_edges": values[0]["train_edges"], "val_edges": values[0]["val_edges"],
                            "epochs": len(values),
                            "zero_gradient_epochs": sum(r["message_gradient_l1"] == 0 for r in values),
                            "gradient_l1_sum": sum(r["message_gradient_l1"] for r in values),
                            "statuses": sorted(set(r["status"] for r in values))})
    write_csv(output / (key + "_duplicates.csv"), dup_nodes)
    write_csv(output / (key + "_error_coverage.csv"), errors)
    return dup_summary, errors, support


def replay_coverage(graph, manifest, audit, inputs):
    """Replay the frozen scalar analyzer in RAM, never reconstruct a saved graph."""
    from scripts.DFG.frontend import parse_source, parse, walk, FUNCTION_TYPES
    from scripts.DFG.semantic_cfg import analyze
    from scripts.DFG.reaching_definitions import solve
    from scripts.DFG.models import Unsupported, Span
    from scripts.DFG.projection import Projector
    file_rows, function_rows, fact_rows, node_functions = [], [], [], {}
    frozen_by_function = defaultdict(list)
    for evidence in audit["evidence"]:
        frozen_by_function[evidence["function"]].append(evidence)
    for file, saved in audit["files"].items():
        source_info = manifest["sources"].get(file)
        if not source_info:
            file_rows.append({"file": file, "source_available": 0, "functions_total": None,
                              "fallback_reasons": saved.get("diagnostics", [])})
            continue
        path = checked(source_info["path"], source_info["sha256"], inputs)
        source = path.read_text(encoding="utf8")
        raw_tree = parse(source)
        raw_nodes = list(walk(raw_tree.root_node))
        functions = [n for n in raw_nodes if n.type in FUNCTION_TYPES and n.child_by_field_name("body")]
        state_decl = [n for n in raw_nodes if n.type == "state_variable_declaration"]
        row = {"file": file, "source_available": 1, "functions_total": len(functions),
               "functions_total_basis": "parsed callable bodies, excluding modifier definitions",
               "state_declarations_syntax": len(state_decl),
               "mapping_types_syntax": sum(n.type == "type_name" and n.text.lstrip().startswith(b"mapping") for n in raw_nodes),
               "modifier_definitions_syntax": sum(n.type == "modifier_definition" for n in raw_nodes),
               "modifier_invocations_syntax": sum(n.type == "modifier_invocation" for n in raw_nodes),
               "analysis_diagnostics": dict(Counter(d["kind"] for d in saved.get("diagnostics", []))),
               "fallback_reasons": [d for d in saved.get("diagnostics", []) if "fallback" in d["kind"]]}
        try:
            view = parse_source(source, file, saved.get("scope_mode"))
        except Unsupported as exc:
            row.update(functions_analyzed=0, functions_fallback=len(functions), file_fallback=1, facts_extracted=0,
                       facts_projected=0, projection_attempted=0, file_reason=str(exc))
            file_rows.append(row)
            for fn in functions:
                function_rows.append({"file": file, "function": file + ":" + str(fn.start_byte),
                                      "start_line": fn.start_point[0] + 1, "end_line": fn.end_point[0] + 1,
                                      "analyzed": 0, "fallback_reason": "file: " + str(exc)})
            continue
        analysis = analyze(view)
        projected = "projection" in saved
        mapping, projector = {}, None
        try:
            projector = Projector(graph, view)
            if not projected:
                raise AssertionError("Previously rejected projection now accepted without code changes")
            for a in saved.get("anchors", []):
                mapping[Span(a["file"], a["start"], a["end"], a["role"])] = a["node_id"]
        except Unsupported as exc:
            if projected:
                raise AssertionError("Previously accepted projection now rejected: " + str(exc))
            row["projection_fallback_reason"] = str(exc)
        if projector is not None:
            # Existing exact AST identities, not nearest-line guessing. Include modifier bodies for reporting.
            callable_nodes = [n for n in raw_nodes
                              if n.type in FUNCTION_TYPES | {"modifier_definition"}
                              and n.child_by_field_name("body")]
            bounds = []
            for fn in callable_nodes:
                try:
                    k = view.compat_key(Span(file, fn.start_byte, fn.end_byte, fn.type))
                except Unsupported:
                    continue
                bounds.append((k[0], k[1], file + ":" + str(fn.start_byte)))
            keys = {i: k for k, i in view.compat_ids.items()}
            for ast_id, n in projector.by_ast.items():
                k = keys[ast_id]
                choices = [f for begin, end, f in bounds if begin <= k[0] and k[1] <= end]
                if len(choices) == 1:
                    node_functions[n] = choices[0]
        irs = {ir.id: ir for ir in analysis.functions}
        diagnostics = defaultdict(list)
        for d in analysis.diagnostics:
            diagnostics[d.get("function", "")].append(d)
        total_facts = total_projected = total_self = total_unmapped = total_rd = 0
        for fn in view.functions:
            fid = file + ":" + str(fn.start_byte)
            name = fn.child_by_field_name("name")
            frow = {"file": file, "function": fid, "name": name.text.decode("utf8") if name else fn.type,
                    "start_byte": fn.start_byte, "end_byte": fn.end_byte,
                    "start_line": fn.start_point[0] + 1, "end_line": fn.end_point[0] + 1,
                    "modifier_invocations": sum(c.type == "modifier_invocation" for c in fn.named_children),
                    "diagnostics": dict(Counter(d["kind"] for d in diagnostics[fid])),
                    "fallback_reason": "; ".join(d.get("reason", "") for d in diagnostics[fid]
                                                 if "fallback" in d["kind"]),
                    "projection_file_accepted": int(projected)}
            if fid not in irs:
                frow.update(analyzed=0, facts_extracted=0, facts_projected=0)
                function_rows.append(frow)
                continue
            ir = irs[fid]
            try:
                rd = solve(ir)
            except Unsupported as exc:
                frow.update(analyzed=0, facts_extracted=0, facts_projected=0, fallback_reason=str(exc))
                function_rows.append(frow)
                continue
            total_rd += 1
            events = {e.id: e for b in ir.blocks.values() for e in b.events}
            symbol_counts = Counter(s.kind for s in ir.symbols.values())
            fact_kinds, event_kinds = Counter(), Counter()
            projected_count = self_count = 0
            frozen_keys = {(e["symbol"], e["definition"], e["use"], e["source"], e["target"])
                           for e in frozen_by_function[fid]}
            actual_keys = set()
            pairs = set()
            for fact in rd.facts:
                symbol = ir.symbols[fact.symbol]
                event = events[fact.definition.event]
                fact_kinds[symbol.kind] += 1
                event_kinds[event.kind] += 1
                s, t = mapping.get(fact.definition.anchor), mapping.get(fact.use.anchor)
                mapped = s is not None and t is not None
                if mapped:
                    actual_keys.add((fact.symbol, fact.definition.id, fact.use.id, s, t))
                    projected_count += 1
                    self_count += int(s == t)
                    if s != t:
                        pairs.add((s, t))
                fact_rows.append({"file": file, "function": fid, "symbol": fact.symbol,
                                  "symbol_kind": symbol.kind, "symbol_type": symbol.type_name,
                                  "definition": fact.definition.id, "use": fact.use.id,
                                  "definition_event_kind": event.kind, "use_event_kind": fact.use.kind,
                                  "definition_anchor_role": fact.definition.anchor.role,
                                  "use_anchor_role": fact.use.anchor.role,
                                  "definition_start_byte": fact.definition.anchor.start,
                                  "use_start_byte": fact.use.anchor.start,
                                  "projected": int(mapped), "source": s, "target": t,
                                  "self_filtered": int(mapped and s == t),
                                  "projection_file_accepted": int(projected)})
            if actual_keys != frozen_keys:
                raise AssertionError("Replayed facts differ from frozen projected evidence: " + fid)
            total_facts += len(rd.facts)
            total_projected += projected_count
            total_self += self_count
            if projected:
                total_unmapped += len(rd.facts) - projected_count
            frow.update(analyzed=1, symbols=dict(symbol_counts), facts_by_symbol_kind=dict(fact_kinds),
                        facts_by_definition_event_kind=dict(event_kinds), facts_extracted=len(rd.facts),
                        facts_projected=projected_count, self_filtered=self_count,
                        facts_unmapped=len(rd.facts) - projected_count,
                        actual_unique_ddg_edges=len(pairs),
                        duplicate_projected_pairs=projected_count-self_count-len(pairs),
                        facts_lost_whole_file_projection=int(not projected) * len(rd.facts),
                        uses_total=rd.uses_total, uses_resolved=rd.uses_resolved,
                        unresolved_nonlocal_occurrences=frow["diagnostics"].get("unresolved_or_nonlocal", 0),
                        opaque_storage_occurrences=frow["diagnostics"].get("opaque_storage_access", 0),
                        opaque_member_occurrences=frow["diagnostics"].get("opaque_member", 0))
            function_rows.append(frow)
        if total_rd != saved.get("analysis", {}).get("functions_supported"):
            raise AssertionError("Replay function coverage differs")
        if projected:
            expected = saved["projection"]
            if (total_facts, total_projected, total_self, total_unmapped) != (
                    expected["facts_total"], expected["facts_projected"], expected["self_facts"],
                    expected["facts_unmapped"]):
                raise AssertionError("Replay projected counts differ")
        row.update(functions_analyzed=total_rd, functions_fallback=len(functions)-total_rd,
                   file_fallback=0, projection_attempted=int(projected),
                   facts_extracted=total_facts, facts_projected=total_projected,
                   facts_lost_whole_file_projection=total_facts if not projected else 0,
                   facts_unmapped_after_projection=total_unmapped, self_filtered=total_self,
                   actual_unique_ddg_edges=saved.get("projection", {}).get("edges_added", 0),
                   duplicate_projected_pairs=saved.get("projection", {}).get("duplicate_projected_pairs", 0))
        file_rows.append(row)
    return file_rows, function_rows, fact_rows, node_functions


def coverage_summary(files, functions, facts):
    totals = Counter()
    for f in files:
        for name in ("functions_total", "functions_analyzed", "functions_fallback", "file_fallback",
                     "facts_extracted", "facts_projected", "facts_lost_whole_file_projection",
                     "facts_unmapped_after_projection", "self_filtered", "actual_unique_ddg_edges",
                     "duplicate_projected_pairs", "state_declarations_syntax", "mapping_types_syntax",
                     "modifier_definitions_syntax", "modifier_invocations_syntax"):
            totals[name] += f.get(name) or 0
    totals["files"] = len(files)
    totals["files_without_ddg"] = sum(not f.get("actual_unique_ddg_edges") for f in files)
    totals["files_projection_rejected"] = sum(bool(f.get("projection_fallback_reason")) for f in files)
    kinds = Counter(f["symbol_kind"] for f in facts)
    symbol_totals = Counter()
    for row in functions:
        symbol_totals.update(row.get("symbols", {}))
    edge_kinds = defaultdict(set)
    for fact in facts:
        if fact["projected"] and not fact["self_filtered"]:
            edge_kinds[(fact["source"], fact["target"])].add(fact["definition_event_kind"])
    edge_definitions = Counter()
    for values in edge_kinds.values():
        if values == {"entry"}:
            edge_definitions["entry_only"] += 1
        elif "entry" in values:
            edge_definitions["entry_and_statement"] += 1
        else:
            edge_definitions["statement_only"] += 1
    events = Counter(f["definition_event_kind"] for f in facts if f["projected"] and not f["self_filtered"])
    reasons = Counter(f.get("fallback_reason", "") for f in functions if not f["analyzed"])
    return {"counts": dict(totals), "facts_symbol_kind": dict(kinds), "symbols_in_analyzed_functions": dict(symbol_totals),
            "unique_edges_definition_origin": dict(edge_definitions),
            "projected_nonself_facts_definition_event_kind": dict(events),
            "function_fallback_reasons": dict(reasons),
            "limit": "Extracted scalar fact projection rate is NOT complete Solidity dependence coverage. "
                     "Syntax counts do not infer state semantics, aliases or vulnerability causes."}


def grouped_coverage(rows, group_fields):
    groups = {}
    for row in rows:
        key = tuple(row.get(k) for k in group_fields)
        dest = groups.setdefault(key, Counter())
        dest["nodes"] += 1
        for field in ("ddg_in", "ddg_out", "ddg_affected_within_two", "new_upstream_count_two"):
            dest[field + "_positive_count"] += int(row[field] > 0)
        dest["ddg_in_edges"] += row["ddg_in"]
    return [dict(zip(group_fields, key), **dict(value)) for key, value in groups.items()]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=REPO/"scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c")
    parser.add_argument("--output", type=Path, default=ROOT/"static")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output != ROOT/"static":
        raise ValueError("Outputs restricted to diagnostic static directory")
    output.mkdir(exist_ok=True)
    # Refuse to overwrite diagnostic datasets; edge_functions is separately prepared early.
    if (output/"summary.json").exists() or (output/"coverage.csv").exists():
        raise FileExistsError("Static diagnostics already exist")
    before_code = code_hashes()
    inputs = {}
    groups = resolved_tasks(args.run.resolve(), inputs)
    edge_functions_path = output/"edge_functions.json"
    ef = read(edge_functions_path) if edge_functions_path.exists() else make_edge_functions(groups, inputs)
    if not edge_functions_path.exists():
        dump(edge_functions_path, ef)
    cache = {}
    all_files, all_fn, all_facts, all_increment, all_dup, all_support, all_errors = [], [], [], [], [], [], []
    summaries = {}
    for key, group in groups.items():
        print("D1 static task: " + key, flush=True)
        manifest, audit, base, enhanced = load_pair(group, inputs)
        before_graph = (fingerprint(base), fingerprint(enhanced))
        cohort = group["cohort"]
        if cohort not in cache:
            if group["task"] != "contract":
                raise ValueError("Need full contract graph for per-file projection replay")
            cache[cohort] = replay_coverage(base, manifest, audit, inputs)
        files, functions, facts, node_fun = cache[cohort]
        population = {d["source_file"] for _, d in base.nodes(data=True)}
        fs = [dict(r, task_key=key) for r in files if r["file"] in population]
        fns = [dict(r, task_key=key) for r in functions if r["file"] in population]
        fct = [dict(r, task_key=key) for r in facts if r["file"] in population]
        all_files.extend(fs); all_fn.extend(fns); all_facts.extend(fct)
        increment, contexts = edge_increment(base, enhanced, key, output)
        duplicates, errors, support = duplicates_and_errors(group, base, contexts, node_fun, inputs, output)
        all_increment.append(increment); all_dup.extend(duplicates); all_support.extend(support); all_errors.extend(errors)
        summaries[key] = dict(coverage_summary(fs, fns, fct), information_increment=increment,
                              node_labels=grouped_coverage(list(contexts.values()), ["label"]),
                              errors=grouped_coverage(errors, ["status"]))
        if before_graph != (fingerprint(base), fingerprint(enhanced)):
            raise AssertionError("In-memory input graph mutated")
        print(json.dumps({"task": key, "coverage": summaries[key]["counts"], "increment": increment}), flush=True)
    write_csv(output/"coverage.csv", all_files)
    write_csv(output/"function_coverage.csv", all_fn)
    write_csv(output/"facts.csv", all_facts)
    write_csv(output/"edge_increment.csv", all_increment)
    write_csv(output/"duplicates_summary.csv", all_dup)
    write_csv(output/"relation_support.csv", all_support)
    write_csv(output/"error_group_coverage.csv", grouped_coverage(all_errors, ["task_key", "status"]))
    write_csv(output/"file_error_coverage.csv", grouped_coverage(all_errors, ["task_key", "file", "status"]))
    write_csv(output/"function_error_coverage.csv", grouped_coverage(all_errors, ["task_key", "file", "function", "status"]))
    if before_code != code_hashes():
        raise AssertionError("Frozen runtime code changed during static diagnostics")
    drift = [p for p, h in inputs.items() if sha(p) != h]
    if drift:
        raise AssertionError("Frozen input changed: " + repr(drift))
    dump(output/"summary.json", {"status": "passed", "complete_tasks": len(summaries), "tasks": summaries,
         "scoring": "Archived best CV validation, node unit is original HCG node",
         "dedup_index": "Each fold train stored-code/float32 bit-exact index; val labels consulted only after lookup.",
         "contract_error_grouping": "File prediction status assigned to its nodes solely to summarize graph coverage.",
         "direction": "Exact production reflect_graph for base; forward-only DATA_DEF_USE.",
         "unsupported_scope": "No state/mapping contents, aliases, modifiers, interprocedural summaries inferred."})
    dump(output/"input_invariants.json", {"input_hashes": inputs, "frozen_code_before": before_code,
                                         "frozen_code_after": code_hashes(), "input_drift": drift,
                                         "graph_fingerprints_preserved": True})
    print("D1 complete: " + str(output), flush=True)


if __name__ == "__main__":
    main()
