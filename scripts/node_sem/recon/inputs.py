"""NS-P0 read-only identity, relation and historical-resource reconnaissance.

No training, CUDA initialization, downloads or artifact writes. Checkpoints are
hashed as files; their primitive header metadata is inspected with pickletools,
without importing or executing pickle globals. Tensor state SHA is cross-checked
between sealed JSON references, not recomputed by unsafe torch.load.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import pickletools
import re
import statistics
import zipfile

import numpy as np

from scripts.labeling_v2.safe_graph import read_graph


RELATIONS = ("DATA_DEF_USE", "WRITES_STATE", "READS_STATE", "ENV_FLOW")
BASE = Path("scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1")
STORE = Path("scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json")


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha256(path))


def checked(ref, cache):
    path = Path(ref["path"])
    key = str(path.resolve())
    actual = cache.get(key)
    if actual is None:
        actual = sha256(path)
        cache[key] = actual
    if actual != ref["sha256"]:
        raise AssertionError("SHA mismatch: " + key)
    return path


def _safe_header(path):
    """Read primitive prefix only; REDUCE/GLOBAL etc are never executed."""
    tokens = []
    with zipfile.ZipFile(str(path)) as archive:
        names = [name for name in archive.namelist() if name.endswith("/data.pkl")]
        if len(names) != 1:
            raise AssertionError("Expected one ZIP data.pkl")
        for op, value, _ in pickletools.genops(archive.read(names[0])):
            if op.name in ("PROTO", "EMPTY_DICT", "BINPUT", "LONG_BINPUT", "MARK"):
                continue
            if op.name in ("BINUNICODE", "BININT", "BININT1", "BININT2"):
                if value == "state_dict":
                    break
                tokens.append(value)
            else:
                raise AssertionError("Non-primitive checkpoint header: " + op.name)
        else:
            raise AssertionError("Checkpoint lacks state_dict header")
    if len(tokens) % 2:
        raise AssertionError("Odd checkpoint primitive header")
    meta = dict(zip(tokens[::2], tokens[1::2]))
    if meta.get("kind") != "untrained_initial" or meta.get("optimizer_steps") != 0:
        raise AssertionError("Not an untrained zero-step initial")
    return meta


def _distribution(values):
    return dict(n=len(values), minimum=min(values), maximum=max(values),
                mean=statistics.mean(values), median=statistics.median(values),
                sample_sd=statistics.stdev(values) if len(values) > 1 else None,
                total=sum(values))


def _cite(root, relative, pattern):
    path = root / relative
    matches = [i for i, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1)
               if re.search(pattern, line)]
    return dict(path=relative, sha256=sha256(path), matching_lines=matches)


def _feature_identity(ref, view, cache):
    manifest = read(checked(ref, cache))
    array_ref = manifest["data"]
    with np.load(str(checked(array_ref, cache)), allow_pickle=False) as archive:
        if archive.files != ["features"]:
            raise AssertionError("NPZ keys differ")
        arr = archive["features"]
        if list(arr.shape) != manifest["feature_shape"] or str(arr.dtype) != "float32":
            raise AssertionError("Feature shape/dtype mismatch")
        if not np.isfinite(arr).all():
            raise AssertionError("Nonfinite input")
        rows = manifest["rows"]
        if len(rows) != len(arr):
            raise AssertionError("Feature rows mismatch")
        ids = [row["original_graph_node_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise AssertionError("Duplicate feature identity")
        field = view + "_vector_sha256"
        for row, value in zip(rows, arr):
            if hashlib.sha256(value.tobytes()).hexdigest() != row[field]:
                raise AssertionError("Feature row digest differs")
        return dict(manifest=ref, npz=array_ref, view=view, rows=len(rows),
                    feature_shape=list(arr.shape), dtype=str(arr.dtype),
                    array_min=float(arr.min()), array_max=float(arr.max()),
                    all_values_nonnegative_integers=bool((arr >= 0).all() and (arr == np.floor(arr)).all()),
                    unique_original_node_ids=len(set(ids)),
                    all_row_vector_sha_verified=True,
                    auxiliary_features_unchanged=manifest["auxiliary_features_unchanged"])


def _relation_audit(graph, audit, source_rows, source_cache, cache):
    counts = {relation: Counter() for relation in RELATIONS}
    attr_counts = {relation: Counter() for relation in RELATIONS}
    examples = {relation: [] for relation in RELATIONS}
    totals = Counter()
    spelling = Counter()
    for u, v, key, attrs in graph.edges(keys=True, data=True):
        relation = attrs.get("edge_type")
        if relation not in RELATIONS:
            continue
        totals[relation] += 1
        counts[relation][(graph.nodes[u]["node_type"], graph.nodes[v]["node_type"])] += 1
        attr_counts[relation].update(attrs.keys())
        if relation == "DATA_DEF_USE":
            spelling["scalar_edges_with_spelling_attribute"] += int(
                any(name in attrs for name in ("spellings", "symbol", "name", "state_vars")))
        if len(examples[relation]) >= 5:
            continue
        file_name = graph.nodes[u]["source_file"]
        row = source_rows[file_name]
        result_path = checked(row["result"], cache)
        if str(result_path) not in source_cache:
            source_cache[str(result_path)] = read(result_path)
        mapping = source_cache[str(result_path)]["mapping"]
        item = dict(source=u, target=v, key=key,
                    source_type=graph.nodes[u]["node_type"],
                    target_type=graph.nodes[v]["node_type"],
                    source_file=file_name, attributes=attrs,
                    source_code=graph.nodes[u]["code"],
                    target_code=graph.nodes[v]["code"],
                    mapping_result=row["result"])
        if relation == "DATA_DEF_USE":
            indices = attrs["ddg_fact_indices"]
            evidence = [audit["layers"]["L1"]["evidence"][i] for i in indices]
            if any(x["source"] != u or x["target"] != v for x in evidence):
                raise AssertionError("L1 evidence endpoint mismatch")
            item["sidecar_evidence"] = evidence
            item["symbol_spelling_mapping"] = [
                dict(symbol=e["symbol"], original=e["symbol"].rsplit(":", 1)[-1],
                     anonymous=mapping.get(e["symbol"].rsplit(":", 1)[-1]))
                for e in evidence]
        if "state_vars" in attrs:
            item["original_to_anonymous_state_vars"] = {
                name: mapping.get(name) for name in attrs["state_vars"]}
            if any(value is None for value in item["original_to_anonymous_state_vars"].values()):
                raise AssertionError("State spelling absent from sealed file mapping")
        if "spellings" in attrs:
            item["environment_spellings_are_reserved_expressions"] = list(attrs["spellings"])
        examples[relation].append(item)
    env_nodes = [(nid, attrs) for nid, attrs in graph.nodes(data=True)
                 if attrs["node_type"] == "env_source"]
    file_counts = Counter(attrs["source_file"] for _, attrs in env_nodes)
    env_keys = Counter(attrs["code"] for _, attrs in env_nodes)
    env_examples = []
    for nid, attrs in env_nodes[:5]:
        item = dict(attrs)
        item["token"] = dict(shape=list(attrs["token"].shape), dtype=str(attrs["token"].dtype),
                             sha256=hashlib.sha256(attrs["token"].tobytes()).hexdigest())
        env_examples.append(dict(node_id=nid, attributes=item))
    return dict(total_edges_by_relation=dict(totals),
                relations={r: dict(direction_counts=[
                    dict(source_type=u, target_type=v, count=n)
                    for (u, v), n in sorted(counts[r].items())],
                    attribute_counts=dict(attr_counts[r]), examples=examples[r]) for r in RELATIONS},
                scalar_spelling_storage=dict(spelling),
                env_source=dict(count=len(env_nodes),
                    keys=dict(sorted(env_keys.items())),
                    attribute_keys=sorted(set(k for _, a in env_nodes for k in a)),
                    per_file={name:file_counts[name] for name in sorted(source_rows)},
                    examples=env_examples),
                scalar_sidecar_required=bool(totals["DATA_DEF_USE"] and
                    not spelling["scalar_edges_with_spelling_attribute"]),
                f3_has_no_reverse_edges=not any(str(a.get("edge_type", "")).startswith("REV_")
                    for _, _, a in graph.edges(data=True)))


def run(repo_root):
    root = Path(repo_root).resolve()
    cache = {}
    plan_path = root / BASE / "plan.json"
    plan = read(plan_path)
    plan_ref = reference(plan_path)
    seal_path = root / BASE / "plan.seal.json"
    seal = read(seal_path)
    checked(seal["plan"], cache)
    if seal["plan"] != plan_ref:
        raise AssertionError("8H plan seal differs")
    source = read(checked(plan["source_preparation"], cache))
    source_seal = read(checked(plan["source_seal"], cache))
    if source_seal["plan"] != plan["source_preparation"]:
        raise AssertionError("8G source plan seal differs")
    store_seal_path = (root / STORE).with_name("store.seal.json")
    store_seal = read(store_seal_path)
    store_ref = dict(path=str(root / STORE), sha256=store_seal["store_sha256"])
    store = read(checked(store_ref, cache))
    if (store_seal["version"] != store["version"] or store_seal["status"] != "accepted"
            or store["status"] != "accepted"):
        raise AssertionError("Graph store seal status/version differs")
    input_manifest = store["input_manifest"]
    if (input_manifest["sha256"] != store_seal["input_manifest_sha256"]
            or input_manifest["seal_sha256"] != store_seal["input_manifest_seal_sha256"]):
        raise AssertionError("Graph store sealed input identity differs")
    checked(input_manifest, cache)
    checked(dict(path=input_manifest["seal_path"], sha256=input_manifest["seal_sha256"]), cache)
    naming_ref = source["bound_artifacts"]["spelling_naming"]
    naming = read(checked(naming_ref, cache))
    source_table_ref = naming["artifacts"]["sources"]
    source_table = read(checked(source_table_ref, cache))
    source_cache = {}
    mappings = []
    for identity, row in source_table.items():
        checked(row["source"], cache)
        path = checked(row["result"], cache)
        result = read(path)
        source_cache[str(path)] = result
        mapping = result["mapping"]
        if result["source_sha256"] != row["source"]["sha256"] or result["status"] != "renamed":
            raise AssertionError("Source naming identity/fallback differs")
        if len(set(mapping.values())) != len(mapping) or any(
                re.fullmatch(r"v[0-9]+", value) is None for value in mapping.values()):
            raise AssertionError("Not an original-spelling to vN bijection")
        mappings.append(dict(identity=identity, source=row["source"], result=row["result"],
                             names=len(mapping), bijective=True))
    tasks = {}
    edges = {}
    for task_id, task in plan["tasks"].items():
        graphs = {}
        for profile in ("G0", "G3R"):
            ref = task["profiles"][profile]["graph"]
            checked(ref, cache)
            graphs[profile] = ref
        checked(task["folds"], cache)
        checked(task["label_view"], cache)
        checked(task["record"]["labels"], cache)
        feature_views = {}
        for view in ("original", "anonymous"):
            feature_views[view] = _feature_identity(source["tasks"][task_id]["feature_view"][view], view, cache)
        if task["feature_view"] != feature_views["anonymous"]["manifest"] or task["feature_npz"] != feature_views["anonymous"]["npz"]:
            raise AssertionError("8H feature refs differ from 8G anonymous")
        tasks[task_id] = dict(granularity=task["granularity"], category=task["category"],
                             files=task["files"], groups=task["groups"], k_folds=task["k_folds"],
                             graphs=graphs, label_view=task["label_view"],
                             labels=task["record"]["labels"], folds=task["folds"],
                             config=task["config"], features=feature_views)
        graph = read_graph(checked(graphs["G3R"], cache))
        if len(graph) != graphs["G3R"]["nodes"] or graph.number_of_edges() != graphs["G3R"]["edges"]:
            raise AssertionError("Graph inventory differs")
        store_task = store["tasks"][task_id]["graphs"]["F3"]
        if store_task["graph"] != graphs["G3R"]:
            raise AssertionError("8H F3 ref differs from graph store")
        audit_ref = store_task["audit"]
        audit = read(checked(audit_ref, cache))
        rows_by_file = {r["file"]:r for r in source_table.values()
                        if r["category"] == task["category"]
                        and r["file"] in task["record"]["sources"]}
        result = _relation_audit(graph, audit, rows_by_file, source_cache, cache)
        result["graph"] = graphs["G3R"]
        result["audit_sidecar"] = audit_ref
        edges[task_id] = result
        del graph, audit
    complete = read(root / BASE / "complete.json")
    if complete["passed"] is not True or complete["formal_fits"] != 170:
        raise AssertionError("8H not complete")
    receipts = []
    seen = set()
    for ref in complete["receipts"]:
        receipt_path = checked(ref, cache)
        receipt = read(receipt_path)
        job = receipt["job"]
        if job["profile"] not in ("G0", "G3R"):
            continue
        key = (job["task_id"], job["fold"], job["seed"], job["profile"])
        if key in seen or receipt["status"] != "complete" or receipt["plan"] != plan_ref:
            raise AssertionError("Duplicate/unbound successful receipt")
        seen.add(key)
        artifacts = {}
        for filename, digest in receipt["artifacts"].items():
            artifact_ref = dict(path=str(receipt_path.parent / filename), sha256=digest)
            checked(artifact_ref, cache)
            artifacts[filename] = artifact_ref
        initial = read(receipt_path.parent / "initialization_ref.json")
        checked(initial, cache)
        meta = _safe_header(initial["path"])
        task = plan["tasks"][job["task_id"]]
        prepared_ref = task["prepared"]["%s/%s" % (job["fold"], job["seed"])]
        prepared = read(checked(prepared_ref, cache))
        if prepared["profiles"][job["profile"]]["initial"] != initial:
            raise AssertionError("Receipt initial differs from prepared seal")
        binding = read(receipt_path.parent / "binding.json")
        if binding["initial_weights_sha256"] != initial["sha256"] or binding["initial_state_sha256"] != initial["state_sha256"]:
            raise AssertionError("Binding initial state identity differs")
        for name in ("task_id", "fold", "seed", "profile", "constructor_seed", "fit_seed"):
            if meta[name] != job[name]:
                raise AssertionError("Zero-step metadata differs: " + name)
        if read(receipt_path.parent / "effective_config.json") != task["config"]:
            raise AssertionError("Fit configuration differs from plan")
        for name, expected in (
                ("graph",task["profiles"][job["profile"]]["graph"]),
                ("folds",task["folds"]),("label_view",task["label_view"]),
                ("labels",task["record"]["labels"]),("feature_view",task["feature_view"]),
                ("feature_npz",task["feature_npz"]),("source_preparation",plan["source_preparation"])):
            if binding[name] != expected:
                raise AssertionError("Fit binding differs: " + name)
        receipts.append(dict(job=job, attempt_directory=str(receipt_path.parent),
                             receipt=ref, artifact_count=len(artifacts),
                             all_artifact_sha_verified=True, initialization=initial,
                             prepared_manifest=prepared_ref, zero_step_static_header=meta,
                             state_sha_metadata_consistent=True,
                             tensor_digest_independently_recomputed=False,
                             bound_inputs_match_task=True))
    expected = {(tid,fold,1,profile) for tid,t in plan["tasks"].items()
                for fold in range(t["k_folds"]) for profile in ("G0","G3R")}
    if seen != expected or len(receipts) != 60:
        raise AssertionError("S0 G0/G3R receipt matrix is not exactly 60")
    report_receipt_path = root / BASE / "reports/receipt.json"
    report_receipt = read(report_receipt_path)
    if report_receipt["plan"] != plan_ref:
        raise AssertionError("Resource report plan differs")
    checked(report_receipt["plan"], cache)
    complete_path = checked(report_receipt["complete"], cache)
    if complete_path.resolve() != (root / BASE / "complete.json").resolve():
        raise AssertionError("Resource report completion identity differs")
    resource_ref = report_receipt["artifacts"]["resources.csv"]
    resource_path = checked(resource_ref, cache)
    if resource_path.resolve() != (root / BASE / "reports/resources.csv").resolve():
        raise AssertionError("Resource report path differs")
    resource_rows = list(csv.DictReader(io.StringIO(resource_path.read_text(encoding="utf8"))))
    expected_resource_jobs = {(job["task_id"], job["fold"], job["seed"], job["profile"])
                              for job in plan["jobs"]}
    resource_jobs = [(row["task_id"], int(row["fold"]), int(row["seed"]), row["profile"])
                     for row in resource_rows]
    if (len(resource_rows) != 170 or len(set(resource_jobs)) != 170
            or len(expected_resource_jobs) != 170 or set(resource_jobs) != expected_resource_jobs):
        raise AssertionError("Resource task/fold/seed/profile matrix differs or contains duplicates")
    resources = defaultdict(list)
    for row in resource_rows:
        converted = dict(row)
        for name in ("fit_seconds","peak_allocated_mib","peak_reserved_mib","minimum_free_mib"):
            converted[name] = float(row[name])
        for name in ("fold","seed","best_epoch","last_epoch","parameter_count"):
            converted[name] = int(row[name])
        resources[(row["task_id"],row["profile"])].append(converted)
    summaries = []
    for (tid,profile), rows in sorted(resources.items()):
        summaries.append(dict(task_id=tid,profile=profile,count=len(rows),
            fit_seconds=_distribution([r["fit_seconds"] for r in rows]),
            peak_allocated_mib=_distribution([r["peak_allocated_mib"] for r in rows]),
            peak_reserved_mib=_distribution([r["peak_reserved_mib"] for r in rows]),
            minimum_free_mib=min(r["minimum_free_mib"] for r in rows),
            parameter_count=sorted(set(r["parameter_count"] for r in rows))))
    total0 = sum(r["fit_seconds"] for (tid,p),rows in resources.items() if p=="G0" for r in rows)
    total3 = sum(r["fit_seconds"] for (tid,p),rows in resources.items() if p=="G3R" for r in rows)
    estimates = {}
    for name,count,seconds,formula in (
        ("N-A",180,3*(total0+total3),"3 * sum_30_folds(G0_seconds + G3R_seconds)"),
        ("N-B",90,2*total3+total0,"2 * sum_30_folds(G3R_seconds) + G0_2layer_proxy_for_noG"),
        ("N-C",120,4*total3,"4 * sum_30_folds(G3R_seconds)"),
        ("N-D",60,2*total3,"2 * sum_30_folds(G3R_seconds)")):
        estimates[name] = dict(fits=count, historical_fit_only_seconds=seconds,
                               historical_fit_only_hours=seconds/3600., formula=formula,
                               prediction_is_not_measured_nodesem_runtime=True)
    return dict(version="nodesem-nsp0-inputs-readonly-v1",
        plan=plan_ref,seal=reference(seal_path),source_preparation=plan["source_preparation"],
        source_seal=plan["source_seal"],graph_store=store_ref,
        graph_store_seal=reference(store_seal_path), graph_store_seal_verified=True,
        tasks=tasks, receipts=receipts, reuse_receipts_count=len(receipts),
        checkpoint_inspection=dict(method="ZIP/pickletools primitive header inspection; no pickle global executed",
            state_file_sha_verified=True, metadata_binding_state_sha_consistent=True,
            tensor_digest_independently_recomputed=False,
            reason="Automatic approval review rejected torch.load executable deserialization; no checkpoint was loaded or altered.",
            limitation="A new independent tensor digest computation was not performed; sealed file SHA plus prepared/binding JSON identities are verified."),
        spelling=dict(naming_manifest=naming_ref, source_table=source_table_ref,
                      source_identities=len(mappings), mappings=mappings,
                      loader="prepare_spelling.load_result(row) returns (source, result); result['mapping'] is file-scoped original spelling -> vN.",
                      evidence_sidecar_note="DATA_DEF_USE lacks variable spelling attrs; ddg_fact_indices indexes F3 audit.layers.L1.evidence; symbol contains original name. Do not put full identity/path/byte coordinates into features.",
                      original_to_anonymous_required_attributes=["state_vars","sidecar L1 evidence.symbol spelling"],
                      env_spellings_note="ENV_FLOW spellings are environment expressions; preserve reserved env keys, do not blindly anonymize Solidity builtins."),
        edges=edges, resources=dict(source=resource_ref, all_fit_rows=resource_rows,
                    report_receipt=reference(report_receipt_path),
                    archived_resource_sha_verified=True, unique_job_identities=len(set(resource_jobs)),
                    exact_plan_job_matrix=True,
                    by_task_profile=summaries, estimates=estimates,
                    limitations=["Historical successful fit time only; excludes CPU construction, verification, failed attempts and interruptions.",
                                 "New adapter costs, early-stopping epochs, offline encoder/LLM/teacher extraction and student distillation are not measured.",
                                 "N-B noG uses G0 two-layer historical time only as a conservative proxy, not measured zero-layer time.",
                                 "Validate real NodeSem CPU construction and GPU memory in NS-P4; final experiments planned for sufficient-VRAM server, current data local RTX3050 4GiB.",
                                 "No encoder or LLM tasks launched; no fixed wall-clock promise."]),
        citations=[_cite(root,"scripts/DFG/dfg_v2/benchmark_v2/prepare_spelling.py",r"^def (load_names|load_result)"),
                   _cite(root,"scripts/DFG/dfg_v2/benchmark_v2/spelling_features.py",r"^def (build_features|assemble)"),
                   _cite(root,"scripts/DFG/dfg_v2/pipeline.py",r"^def _evidence"),
                   _cite(root,"scripts/DFG/experiments/common.py",r"^def tensor_digest"),
                   _cite(root,"scripts/labeling_v2/safe_graph.py",r"^class RestrictedReader|^def read_graph"),
                   _cite(root,"scripts/DFG/dfg_v2/experiment/init.py",r"^def (seeds|parameter_seed)")],
        verified_unique_file_sha_count=len(cache), gpu_used=False, training_executed=False,
        artifact_writes=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    print(json.dumps(run(Path(args.repo)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
