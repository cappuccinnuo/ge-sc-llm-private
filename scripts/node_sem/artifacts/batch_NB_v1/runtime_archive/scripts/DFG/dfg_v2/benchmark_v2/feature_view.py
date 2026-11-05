"""Independent all-HCG token feature views for Prompt 8D.

Only an in-memory deep copy's token arrays change. Original graph files, labels,
code text, node IDs/order, edges, and auxiliary features remain unchanged.
The production tokenizer and model implementation are imported, never modified.
"""
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

import networkx as nx
import numpy as np

from scripts.DFG.graph_audit import frozen
from scripts.labeling_v2.safe_graph import read_graph
from .. import AUX_NODE_TYPES
from ..diagnostics8c.common import checked_plan
from ..diagnostics8c.inference import replacement_map, rewrite_code
from ..diagnostics8c.labels import PIN
from ..tokens import TokenEncoder
from .prepare import checked, read, ref, write, sha

VERSION = "prompt8d-all-hcg-idn-feature-view-v1"
DEFAULT_SOLIDIFI = Path("/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark")


def _bytes_sha(value):
    return hashlib.sha256(value).hexdigest()


def vector_sha(value):
    array = np.asarray(value)
    if array.dtype != np.float32 or array.shape != (512,) or not np.isfinite(array).all():
        raise ValueError("Expected frozen float32[512] token vector")
    return _bytes_sha(array.tobytes(order="C"))


def graph_fingerprint(graph):
    """Stream exact frozen tuples rather than materialize all token hex at once."""
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError("Expected directed multigraph")
    result = hashlib.sha256()
    for kind, item in [("metadata", graph.graph)]:
        result.update(repr((kind, frozen(item))).encode("utf8"))
    for nid, attrs in graph.nodes(data=True):
        result.update(repr(("node", frozen(nid), frozen(attrs))).encode("utf8"))
    for src, dst, key, attrs in graph.edges(keys=True, data=True):
        result.update(repr(("edge", frozen(src), frozen(dst), frozen(key), frozen(attrs))).encode("utf8"))
    return result.hexdigest()


def _pinned_source_index(repository):
    repository = Path(repository).resolve()
    names = subprocess.check_output(
        ["git", "-C", str(repository), "ls-tree", "-r", "--name-only", PIN, "buggy_contracts"]
    ).decode("utf8").splitlines()
    candidates = [name for name in names if re.fullmatch(r"buggy_\d+\.sol", Path(name).name)]
    by_name = {}
    for name in candidates:
        by_name.setdefault(Path(name).name, []).append(name)
    return by_name


def verify_sources(record, repository, audit_rows=None, cache=None):
    """Filename alone is not provenance; verify exact pinned Git source bytes."""
    cache = {} if cache is None else cache
    pinned = _pinned_source_index(repository)
    audit_flags = {}
    for row in audit_rows or []:
        name = row["file"]
        flag = bool(row["solidifi"])
        if name in audit_flags and audit_flags[name] != flag:
            raise ValueError("Inconsistent frozen source cohort")
        audit_flags[name] = flag
    proof, mappings = {}, {}
    for name, source_ref in record["sources"].items():
        source_path = checked(source_ref)
        raw = source_path.read_bytes()
        source = raw.decode("utf8")
        candidate = bool(re.fullmatch(r"buggy_\d+\.sol", name))
        if name in audit_flags and candidate != audit_flags[name]:
            raise ValueError("Source cohort differs from frozen 8C audit")
        matches = []
        if candidate:
            for relpath in pinned.get(name, []):
                if relpath not in cache:
                    cache[relpath] = subprocess.check_output(
                        ["git", "-C", str(repository), "show", PIN + ":" + relpath])
                if cache[relpath] == raw:
                    matches.append(relpath)
            if not matches:
                raise ValueError("SolidiFI candidate does not match pinned source bytes: " + name)
        proof[name] = {"source": source_ref, "solidifi": candidate,
                       "pinned_commit": PIN if candidate else None,
                       "pinned_matching_paths": sorted(matches),
                       "cohort_basis": "exact pinned raw source bytes" if candidate else "frozen nonSolidiFI source identity",
                       "checked_against_prior_node_audit": name in audit_flags}
        mappings[name] = replacement_map(source) if candidate else {}
    return proof, mappings


def _write_npz(path, values):
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, features=values)


def _extract_rows(base, sources, mappings, encoder):
    rows, original, neutral = [], [], []
    encoded = {}
    for nid, attrs in base.nodes(data=True):
        if attrs["node_type"] in AUX_NODE_TYPES:
            raise ValueError("G0 unexpectedly contains auxiliary nodes")
        name = attrs["source_file"]
        if name not in sources:
            raise ValueError("Graph node source missing from manifest")
        vector = np.asarray(attrs["token"])
        original_hash = vector_sha(vector)
        code = attrs["code"]
        if not isinstance(code, str):
            raise ValueError("Expected original exact serialized code text")
        if code not in encoded:
            encoded[code] = encoder(code)
        if not np.array_equal(encoded[code].view(np.uint32), vector.view(np.uint32)):
            raise ValueError("Frozen original feature differs from exact tokenizer recipe")
        # NonSolidiFI source mappings are empty and their features stay untouched.
        rewritten, edits = rewrite_code(code, mappings[name]) if sources[name]["solidifi"] else (code, [])
        if rewritten not in encoded:
            encoded[rewritten] = encoder(rewritten)
        transformed = encoded[rewritten] if edits else vector
        rows.append({
            "original_graph_node_id": nid, "file": name, "node_type": attrs["node_type"],
            "source_sha256": sources[name]["source"]["sha256"],
            "code_sha256": _bytes_sha(code.encode("utf8")),
            "rewritten_code_sha256": _bytes_sha(rewritten.encode("utf8")),
            "original_vector_sha256": original_hash,
            "neutral_vector_sha256": vector_sha(transformed),
            "solidifi": sources[name]["solidifi"], "identifier_replacements": len(edits),
            "feature_changed": not np.array_equal(vector.view(np.uint32), transformed.view(np.uint32)),
        })
        original.append(vector.copy())
        neutral.append(np.asarray(transformed).copy())
    return rows, np.stack(original), np.stack(neutral)


def _profile_bindings(entry, rows):
    prepared = read(checked(entry["prepared"]["0/1"]))
    bindings, fingerprints = {}, {}
    base_order = [r["original_graph_node_id"] for r in rows]
    for profile, detail in prepared["profiles"].items():
        graph_ref = detail["graph"]
        path = checked(graph_ref)
        if str(path) not in fingerprints:
            graph = read_graph(path)
            originals = [(nid, data) for nid, data in graph.nodes(data=True)
                         if data["node_type"] not in AUX_NODE_TYPES]
            if [nid for nid, _ in originals] != base_order:
                raise ValueError("Profile original-node order differs from G0")
            for row, (nid, attrs) in zip(rows, originals):
                if (attrs["source_file"] != row["file"] or attrs["node_type"] != row["node_type"]
                        or _bytes_sha(attrs["code"].encode("utf8")) != row["code_sha256"]
                        or vector_sha(attrs["token"]) != row["original_vector_sha256"]):
                    raise ValueError("Profile original code/feature identity differs")
            fingerprints[str(path)] = graph_fingerprint(graph)
        bindings[profile] = {"graph": graph_ref, "graph_fingerprint": fingerprints[str(path)],
                             "schema": detail["support"]["schema"]}
    return bindings


def build_feature_views(plan_path, old8c_dir, output_dir, solidifi_repo=DEFAULT_SOLIDIFI):
    output = Path(output_dir)
    output.mkdir(parents=False, exist_ok=False)
    plan = checked_plan(plan_path)
    node_views_path = Path(old8c_dir) / "A/node_views.json"
    node_views = read(node_views_path)
    task_views, details, source_cache = {}, {}, {}
    for task_id, entry in plan["tasks"].items():
        directory = output / task_id
        directory.mkdir()
        record = entry["record"]
        sources, mappings = verify_sources(record, solidifi_repo, node_views.get(task_id), source_cache)
        prepared = read(checked(entry["prepared"]["0/1"]))
        base = read_graph(checked(prepared["profiles"]["G0"]["graph"]))
        encoder = TokenEncoder(record["feature"])
        rows, original, neutral = _extract_rows(base, sources, mappings, encoder)
        profiles = _profile_bindings(entry, rows)
        _write_npz(directory/"original.npz", original)
        _write_npz(directory/"neutral.npz", neutral)
        shared = {
            "version": VERSION, "task_id": task_id, "rows": rows, "sources": sources,
            "mappings": mappings, "profiles": profiles, "tokenizer": encoder.provenance,
            "all_original_hcg_nodes_included": True, "partition_scope": "all train/val/test files",
            "original_inputs_unchanged": True, "auxiliary_features_unchanged": True,
            "nonSolidiFI_features_unchanged": True, "feature_shape": list(original.shape),
            "feature_dtype": "float32", "graph_changes_permitted": ["token in deep memory copy only"],
        }
        for name, is_original in (("original", True), ("neutral", False)):
            manifest = dict(shared)
            manifest.update(view="original" if is_original else "idN_neutral_all_SolidiFI",
                            data=ref(directory/(name+".npz")),
                            vector_sha_field="original_vector_sha256" if is_original else "neutral_vector_sha256")
            write(directory/(name+"_manifest.json"), manifest)
        task_views[task_id] = {
            "manifest": ref(directory/"neutral_manifest.json"), "data": ref(directory/"neutral.npz"),
            "original_manifest": ref(directory/"original_manifest.json"),
            "original_data": ref(directory/"original.npz"),
        }
        details[task_id] = {
            "nodes": len(rows), "solidifi_files": sum(p["solidifi"] for p in sources.values()),
            "solidifi_nodes": sum(row["solidifi"] for row in rows),
            "renamed_code_nodes": sum(row["identifier_replacements"] > 0 for row in rows),
            "changed_feature_nodes": sum(row["feature_changed"] for row in rows),
            "auxiliary_nodes_in_view": 0, "original_reencoding_exact_nodes": len(rows),
            "all_profiles_checked": sorted(profiles),
        }
        print(task_id + ": frozen all-node original/idN feature views", flush=True)
    manifest = {
        "version": VERSION, "source_plan": ref(plan_path), "source_node_audit": ref(node_views_path),
        "task_views": task_views, "profiles": list(plan["profiles"]), "orig_inputs_unchanged": True,
        "details": details, "source_repository": str(Path(solidifi_repo).resolve()), "pinned_commit": PIN,
        "implementation": ref(Path(__file__)), "training_executed": 0, "gpu_used": False,
    }
    write(output/"manifest.json", manifest)
    write(output/"manifest.seal.json", {"version": VERSION, "manifest_sha256": sha(output/"manifest.json")})
    return manifest


def assemble_feature_graph(graph_or_path, view_manifest_ref):
    """Deep-copy and replace only exact bound original-node token vectors."""
    manifest_path = checked(view_manifest_ref)
    view = read(manifest_path)
    if view.get("version") != VERSION or view.get("view") not in ("original", "idN_neutral_all_SolidiFI"):
        raise ValueError("Unknown feature view")
    rows = view["rows"]
    if len(rows) != len({r["original_graph_node_id"] for r in rows}):
        raise ValueError("Duplicate feature row identity")
    if isinstance(graph_or_path, nx.Graph):
        graph = graph_or_path
    else:
        path = Path(graph_or_path).resolve()
        matches = [b for b in view["profiles"].values()
                   if Path(b["graph"]["path"]).resolve() == path]
        if not matches:
            raise ValueError("Graph path not bound to feature view")
        for match in matches:
            checked(match["graph"])
        graph = read_graph(path)
    observed_fingerprint = graph_fingerprint(graph)
    if observed_fingerprint not in {b["graph_fingerprint"] for b in view["profiles"].values()}:
        raise ValueError("Graph structure/features/order differ from bound profile")
    original_ids = [nid for nid, attrs in graph.nodes(data=True) if attrs["node_type"] not in AUX_NODE_TYPES]
    if original_ids != [r["original_graph_node_id"] for r in rows]:
        raise ValueError("Feature row ordering differs from graph")
    with np.load(str(checked(view["data"])), allow_pickle=False) as archive:
        if set(archive.files) != {"features"}:
            raise ValueError("Unknown NPZ feature contents")
        features = archive["features"].copy()
    if features.dtype != np.float32 or list(features.shape) != view["feature_shape"] or features.shape != (len(rows), 512):
        raise ValueError("Feature array shape/dtype mismatch")
    result = copy.deepcopy(graph)
    for row, vector in zip(rows, features):
        nid = row["original_graph_node_id"]
        attrs = graph.nodes[nid]
        source = view["sources"][row["file"]]["source"]
        if (attrs["source_file"] != row["file"] or attrs["node_type"] != row["node_type"]
                or source["sha256"] != row["source_sha256"]
                or _bytes_sha(attrs["code"].encode("utf8")) != row["code_sha256"]
                or vector_sha(attrs["token"]) != row["original_vector_sha256"]
                or vector_sha(vector) != row[view["vector_sha_field"]]):
            raise ValueError("Feature row code/type/source/vector identity mismatch")
        if not row["solidifi"] and vector_sha(vector) != row["original_vector_sha256"]:
            raise ValueError("NonSolidiFI feature must remain unchanged")
        result.nodes[nid]["token"] = vector.copy()
    # Graph/order/edge invariance is guaranteed by one deepcopy and token-only
    # assignments. Assert it explicitly after temporarily restoring original rows.
    audit = copy.deepcopy(result)
    for nid in original_ids:
        audit.nodes[nid]["token"] = copy.deepcopy(graph.nodes[nid]["token"])
    if graph_fingerprint(audit) != observed_fingerprint:
        raise AssertionError("Feature binding changed non-token graph content")
    return result
