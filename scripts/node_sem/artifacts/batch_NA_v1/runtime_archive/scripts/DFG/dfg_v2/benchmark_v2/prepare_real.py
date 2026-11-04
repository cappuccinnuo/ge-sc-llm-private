"""Prompt 8E CPU preparation and diagnostic entry points, never HGT fitting."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from .prepare import read, write, ref, checked, verify_prepared
from .real_names import inspect_source, build_pool, make_mapping, verify_rewrite
from .leakage_probes import PROTOCOL, VIEWS, p1, p2_all, p3_samples, run_p3
from ..diagnostics8c.inference import replacement_map
from ..diagnostics8d.renaming import rewrite_node
from ..diagnostics8d.keyword_baselines import keyword_prediction
from ..diagnostics8c.scoring import metric_counts, confusion
from ..projection_view import ProjectionView
from scripts.labeling_v2.safe_graph import read_graph


def load_naming(directory):
    directory = Path(directory)
    manifest = read(directory / "manifest.json")
    seal = read(directory / "manifest.seal.json")
    if ref(directory / "manifest.json") != seal["manifest"]:
        raise ValueError("Naming manifest seal mismatch")
    for value in manifest["artifacts"].values():
        checked(value)
    return (manifest, read(checked(manifest["artifacts"]["inventories"])),
            read(checked(manifest["artifacts"]["pool"])),
            read(checked(manifest["artifacts"]["mappings"])))


def prepare_names(old_plan_path, scope_path, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    verify_prepared(old_plan_path)
    old = read(old_plan_path)
    formal_path = checked(old["bound_artifacts"]["historical_plan"])
    formal = read(formal_path)
    scopes = read(scope_path)
    if scopes["bindings"]["plan"] != ref(formal_path):
        raise ValueError("A_v2 scope plan differs")
    inventories, sources = {}, {}
    for tid, entry in formal["tasks"].items():
        if entry["record"]["task"] != "node":
            continue
        indexed_scopes = defaultdict(set)
        for row in scopes["inventories"][tid]:
            if row["in_renamed_injection_function"] and row["function_compat_span"]:
                indexed_scopes[row["file"]].add((row["function_name"], *row["function_compat_span"]))
        for name, reference in sorted(entry["record"]["sources"].items()):
            source = checked(reference).read_text(encoding="utf8")
            identity = tid + "/" + name
            inv = inspect_source(source, sorted(indexed_scopes[name]))
            inv.update(task_id=tid, file=name, source=reference,
                       solidifi=name.startswith("buggy_"))
            inventories[identity] = inv
            sources[identity] = source
    if len(inventories) != 128 or sum(v["solidifi"] for v in inventories.values()) != 80:
        raise ValueError("Frozen source population differs")
    pool = build_pool(inventories)
    maps = {}
    for key, inv in inventories.items():
        if not inv["solidifi"]:
            continue
        mapping = make_mapping(inv, pool)
        _, syntax = verify_rewrite(sources[key], mapping["mapping"], inv)
        maps[key] = dict(mapping, syntax=syntax)
    write(output / "inventories.json", inventories)
    write(output / "pool.json", pool)
    write(output / "mappings.json", maps)
    write(output / "probe_protocol.json", PROTOCOL)
    # Read-only supersession record lives in 8E, never in the historical batch.
    write(output / "supersession.json", dict(
        superseded_plan=ref(old_plan_path),
        superseded_seal=ref(Path(old_plan_path).with_name("plan.seal.json")),
        reason="idN creates a new injection-name family; N-real candidate pending acceptance",
        old_files_modified=False, new_execution_authorized=False))
    manifest = dict(version="prompt8e-naming-preparation-v1", old_plan=ref(old_plan_path),
                    formal_plan=ref(formal_path), scope=ref(scope_path),
                    artifacts={key: ref(output / (file + ".json")) for key, file in
                               (("inventories", "inventories"), ("pool", "pool"),
                                ("mappings", "mappings"), ("protocol", "probe_protocol"),
                                ("supersession", "supersession"))},
                    sources=128, solidifi_files=80,
                    mapping_count=sum(len(m["mapping"]) for m in maps.values()),
                    pool_sizes={r: len(v) for r, v in pool["roles"].items()},
                    training_executed=0, gpu_used=False,
                    real_name_policy_not_tuned_to_probe_results=True)
    write(output / "manifest.json", manifest)
    write(output / "manifest.seal.json", dict(manifest=ref(output / "manifest.json")))
    return manifest


def node_probe_rows(tid, task, inventory, scope, targets, mappings):
    """Align graph, frozen labels and exact source AST scope by full identity."""
    graph = read_graph(checked(task["record"]["original_graph"]))
    indexes = {(r["file"], r["original_graph_node_id"]): r for r in scope}
    labels = {(r["file"], r["original_graph_node_id"]): r for r in targets}
    if len(indexes) != len(scope) or len(labels) != len(targets) or len(graph) != len(scope):
        raise ValueError("Missing/duplicate graph scope or target identity")
    compat = {}
    for key, item in inventory.items():
        if item["task_id"] == tid:
            compat[item["file"]] = ProjectionView(checked(item["source"]).read_text(), item["file"]).compat
    rows = []
    for nid, attrs in graph.nodes(data=True):
        name = attrs["source_file"]
        key = (name, nid)
        identity = tid + "/" + name
        src = inventory[identity]
        sc, target = indexes[key], labels[key]
        expected = src["source_sha256"]
        if (sc["source_sha256"] != expected or target["source_sha256"] != expected
                or target["orig"] != int(attrs.get("node_info_vulnerabilities") is not None)):
            raise ValueError("Node source/label binding differs")
        own = attrs["code"]
        span = sc["function_compat_span"]
        fn = compat[name][span[0]:span[1]].decode("utf8") if span else None
        mapping = mappings.get(identity, {})
        rows.append(dict(file=name, source_sha256=expected, original_graph_node_id=nid,
                         solidifi=src["solidifi"], orig=target["orig"], C1=target["C1"],
                         own_code=rewrite_node(own, mapping)[0],
                         function_code=rewrite_node(fn, mapping)[0] if fn is not None else None))
    return rows


def run_probes(naming_dir, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    manifest, inventories, pool, maps = load_naming(naming_dir)
    if read(checked(manifest["artifacts"]["protocol"])) != PROTOCOL:
        raise ValueError("Preregistered probe algorithm differs")
    old = read(checked(manifest["old_plan"]))
    formal = read(checked(manifest["formal_plan"]))
    scopes = read(checked(manifest["scope"]))["inventories"]
    targets = read(checked(old["bound_artifacts"]["node_diagnostic_views"]))
    view_maps = {v: {} for v in VIEWS}
    for key, inv in inventories.items():
        if inv["solidifi"]:
            source = checked(inv["source"]).read_text()
            view_maps["idN"][key] = replacement_map(source)
            view_maps["N-real"][key] = maps[key]["mapping"]
    group_of = {}
    for tid, task in old["tasks"].items():
        if task["granularity"] == "node":
            for row in read(checked(task["population"])):
                group_of[tid + "/" + row["file"]] = row["group_id"]
    if set(group_of) != set(inventories):
        raise ValueError("Frozen duplicate groups do not cover exact 128 sources")
    # Original view has identity replacements for its marker names so P1
    # measures their ordinary provenance rather than an empty intervention.
    p1_maps = dict(view_maps)
    p1_maps["original"] = {key: {w: w for w in inv["marker_roles"]}
                           for key, inv in inventories.items() if inv["solidifi"]}
    result = dict(version=PROTOCOL["version"], naming=ref(Path(naming_dir)/"manifest.json"),
                  protocol=manifest["artifacts"]["protocol"], P1={}, P2={}, P3={}, keywords={},
                  hgt_training_executed=0, hgt_forward_count=0, classifier_fits=0)
    for view in VIEWS:
        result["P1"][view] = p1(inventories, p1_maps[view], pool)
        write(output / ("P1_" + view + ".json"), result["P1"][view])
        result["P2"][view] = {}
        for tid, task in formal["tasks"].items():
            if task["record"]["task"] != "node":
                continue
            rows = node_probe_rows(tid, task, inventories, scopes[tid], targets[tid], view_maps[view])
            folds = read(checked(old["tasks"][tid]["folds"]))["folds"]
            result["P2"][view][tid] = {}
            for label in ("orig", "C1"):
                score = p2_all(rows, folds, label)
                path = output / ("P2_" + view + "_" + tid + "_" + label + ".json")
                write(path, score)
                result["P2"][view][tid][label] = dict(
                    artifact=ref(path), **{k: score[k] for k in
                     ("pooled", "all_positive", "delta_bf1_pp", "passed", "scored_nodes")})
                print("P2", view, tid, label, score["pooled"]["buggy_f1"],
                      "delta", score["delta_bf1_pp"], flush=True)
            if view == "N-real":
                category = task["record"]["category"]
                kw = [dict(row, prediction=keyword_prediction(category, row["own_code"],
                                                               row["function_code"])["node_or_function"])
                      for row in rows]
                summaries = []
                for cohort in (True, False):
                    for label in ("orig", "C1"):
                        selected = [r for r in kw if r["solidifi"] == cohort]
                        summaries.append(dict(label=label, solidifi=cohort, aggregation="pooled counts",
                          **metric_counts(confusion((r[label], r["prediction"]) for r in selected))))
                kw_path = output / ("keywords_" + tid + ".json")
                write(kw_path, dict(predictions=kw, metrics=summaries,
                                    interpretation="lexical semantic baseline, not a vulnerability oracle"))
                result["keywords"][tid] = dict(artifact=ref(kw_path), metrics=summaries)
        samples = p3_samples(inventories, view_maps[view], group_of)
        score = run_p3(samples)
        path = output / ("P3_" + view + ".json")
        write(path, score)
        result["classifier_fits"] += score["classifier_fits"]
        result["P3"][view] = dict(artifact=ref(path), **{k: score[k] for k in
                                 ("auc", "passed", "by_task_auc", "samples", "classifier_fits")})
        print("P3", view, score["auc"], flush=True)
    result["passed"] = (result["P1"]["N-real"]["passed"]
        and all(v["passed"] for t in result["P2"]["N-real"].values() for v in t.values())
        and result["P3"]["N-real"]["passed"])
    result["status"] = "acceptance_passed_not_authorized" if result["passed"] else "stopped_leakage_gate"
    result["execution_authorized"] = False
    result["automatic_retuning_allowed"] = False
    write(output / "summary.json", result)
    write(output / "summary.seal.json", dict(summary=ref(output / "summary.json")))
    return result


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command")
    a = sub.add_parser("names")
    a.add_argument("--old-plan", required=True)
    a.add_argument("--scope", required=True)
    a.add_argument("--output", required=True)
    a = sub.add_parser("probes")
    a.add_argument("--naming", required=True)
    a.add_argument("--output", required=True)
    args = p.parse_args()
    if args.command == "names":
        result = prepare_names(args.old_plan, args.scope, args.output)
        print({k: result[k] for k in ("sources", "solidifi_files", "mapping_count", "pool_sizes")})
    elif args.command == "probes":
        result = run_probes(args.naming, args.output)
        print(result["status"])
    else:
        p.error("Choose names or probes")


if __name__ == "__main__":
    main()
