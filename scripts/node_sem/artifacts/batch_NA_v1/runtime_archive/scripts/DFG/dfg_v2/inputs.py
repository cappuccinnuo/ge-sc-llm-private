"""Sealed, standalone Prompt 5 input manifests; no analysis or training.

Only original HCG references are retained. Source text is loaded once per task
by load_task; later layers share that dictionary. Existing augmenters retain
their own AST parsing. A missing source record is an explicit fallback, whereas
a changed registered source/asset is a rejected input.
"""
import copy
import csv
import re
from pathlib import Path

import numpy as np

from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from scripts.DFG.experiments.protocol import validate_fold_document
from scripts.labeling_v2.safe_graph import read_graph
from .tasks import get_tasks, checked_ref, read_labels
from .tokens import RECIPE
from scripts.DFG.experiments.prepare import TOKENIZER, REVISION

VERSION = "dfg-v2-inputs-v1"
PROVENANCE_KEYS = ("source_task_manifest", "source_metadata_manifest", "prepared_manifest")


def _source_records(ref, files):
    path = checked_ref(ref)
    doc = read_json(path)
    records = doc.get("sources", doc)
    if not isinstance(records, dict):
        raise ValueError("Source metadata manifest requires a mapping")
    selected, missing = {}, []
    for name in files:
        if name not in records:
            missing.append(name)
            continue
        rec = copy.deepcopy(records[name])
        if not isinstance(rec, dict) or "path" not in rec or "sha256" not in rec:
            raise ValueError("Source record requires path and sha256")
        rec["path"] = str((path.parent / rec["path"]).resolve())
        rec.setdefault("metadata", None)
        selected[name] = rec
    return selected, missing


def _check_metadata(ref):
    metadata = ref.get("metadata")
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        raise ValueError("Version metadata must be a mapping or null")
    if not isinstance(metadata.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", metadata["version"]):
        raise ValueError("Version metadata requires an exact numeric recorded version")
    origin = checked(metadata["source_path"], metadata["source_sha256"])
    csv_path = checked(metadata["csv_path"], metadata["csv_sha256"])
    if metadata["source_sha256"] != ref["sha256"]:
        raise ValueError("Version metadata source identity differs")
    if (csv_path.parent / metadata["row_file"]).resolve() != origin:
        raise ValueError("Version metadata source path differs")
    with csv_path.open(encoding="utf8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row.get("file") == metadata["row_file"]]
    if len(rows) != 1 or rows[0].get("compiled version") != metadata["version"]:
        raise ValueError("Version metadata row differs")


def _validate_feature(feature, check_files):
    if not isinstance(feature, dict):
        raise ValueError("Feature record required")
    if feature.get("model") != TOKENIZER or feature.get("revision") != REVISION:
        raise ValueError("Tokenizer model/revision differs")
    for key, value in RECIPE.items():
        if feature.get(key) != value:
            raise ValueError("Tokenizer recipe differs: " + key)
    assets = feature.get("asset_hashes")
    if not isinstance(assets, dict) or not assets:
        raise ValueError("Tokenizer asset bindings required")
    for path, digest in assets.items():
        if not Path(path).is_absolute() or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Malformed tokenizer asset binding")
        if check_files:
            checked(path, digest)


def _validate_row(row, check_files=True):
    for name in ("category", "task", "task_id", "source_task_id"):
        if not isinstance(row.get(name), str) or not row[name]:
            raise ValueError("Missing task identity: " + name)
    if row["task"] not in ("contract", "node") or row["task_id"] != row["category"] + "_" + row["task"]:
        raise ValueError("Public task identity differs")
    files, missing, sources = row.get("graph_files"), row.get("missing_sources"), row.get("sources")
    if (not isinstance(files, list) or not files or files != sorted(set(files))
            or not isinstance(missing, list) or missing != sorted(set(missing))
            or not isinstance(sources, dict)
            or set(sources) & set(missing) or set(sources) | set(missing) != set(files)):
        raise ValueError("Graph/source file population differs")
    _validate_feature(row.get("feature"), check_files)
    provenance = row.get("provenance", {})
    if set(PROVENANCE_KEYS) - set(provenance):
        raise ValueError("Source task/metadata/prepared provenance required")
    if row.get("prepared_manifest_sha256") != provenance["prepared_manifest"].get("sha256"):
        raise ValueError("Original prepared-manifest identity differs")
    for ref in [row.get("original_graph"), row.get("labels"), row.get("folds")] + [
            provenance[k] for k in PROVENANCE_KEYS]:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
            raise ValueError("Missing referenced input identity")
        if check_files:
            checked_ref(ref)
    for ref in sources.values():
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
            raise ValueError("Missing source identity")
        if check_files:
            checked_ref(ref)
            _check_metadata(ref)
    if not check_files:
        return
    task = read_json(provenance["source_task_manifest"]["path"])
    prepared = read_json(provenance["prepared_manifest"]["path"])
    if (task.get("task_id") != row["source_task_id"] or task.get("task") != row["task"]
            or prepared.get("category") != row["category"]
            or task.get("cohort") != prepared.get("cohort")):
        raise ValueError("Original task/category binding differs")
    if row.get("label_version") != task.get("label_version"):
        raise ValueError("Original label provenance differs")
    if task["graphs"]["HCG"] != row["original_graph"] or task["feature"] != row["feature"]:
        raise ValueError("Original graph/feature differs from frozen task")
    if task["source_prepared_manifest_sha256"] != row["prepared_manifest_sha256"]:
        raise ValueError("Prepared-manifest binding differs")
    if (Path(task["source_prepared_manifest"]).resolve() != Path(provenance["prepared_manifest"]["path"]).resolve()
            or Path(task["labels_path"]).resolve() != Path(row["labels"]["path"]).resolve()
            or task["labels_sha256"] != row["labels"]["sha256"]):
        raise ValueError("Original task label/prepared reference differs")
    expected_sources, expected_missing = _source_records(provenance["source_metadata_manifest"], files)
    if sources != expected_sources or missing != expected_missing:
        raise ValueError("Source records differ from frozen metadata manifest")
    labels = read_labels(row["labels"])
    if any(f not in labels for f in files):
        raise ValueError("Graph file missing from labels")
    population = {f: labels[f] for f in files}
    if row["task"] == "node" and set(population.values()) != {1}:
        raise ValueError("Node graph population includes non-buggy files")
    folds = validate_fold_document(read_json(row["folds"]["path"]))
    if (folds["task"] != row["task"] or folds["files"] != files
            or folds["file_labels"] != population or folds["seed"] != 1
            or folds["inner_fraction"] != .2
            or folds["prepared_manifest_sha256"] != row["prepared_manifest_sha256"]):
        raise ValueError("Nested folds do not match task population")


def _checked_graph(row):
    graph = read_graph(checked_ref(row["original_graph"]))
    files = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
    if files != row["graph_files"]:
        raise ValueError("Original graph file population differs")
    ref = row["original_graph"]
    if ref.get("fingerprint") and fingerprint(graph) != ref["fingerprint"]:
        raise ValueError("Original graph fingerprint differs")
    if ("nodes" in ref and len(graph) != ref["nodes"]) or (
            "edges" in ref and graph.number_of_edges() != ref["edges"]):
        raise ValueError("Original graph dimensions differ")
    for _, data in graph.nodes(data=True):
        token = data.get("token")
        if not isinstance(token, np.ndarray) or token.shape != (512,) or token.dtype != np.float32:
            raise ValueError("Original inside_token must be 512 float32 values")
        if not np.isfinite(token).all():
            raise ValueError("Original inside_token is nonfinite")
    return graph


def build_manifest(output, task_ids=None, registry=None):
    """Create a new directory containing manifest.json and its immutable seal."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing input manifest directory: " + str(output))
    records = get_tasks(task_ids, registry=registry)
    tasks = {}
    for tid, record in records.items():
        source_task = read_json(checked_ref(record["source_task_manifest"]))
        graph_ref = copy.deepcopy(source_task["graphs"]["HCG"])
        graph = read_graph(checked_ref(graph_ref))
        files = sorted({d["source_file"] for _, d in graph.nodes(data=True)})
        sources, missing = _source_records(record["source_metadata_manifest"], files)
        row = dict(task_id=tid, source_task_id=record["source_task_id"],
            category=record["category"], task=record["task"],
            original_graph=graph_ref, graph_files=files,
            sources=sources, missing_sources=missing,
            labels=copy.deepcopy(record["labels"]), folds=copy.deepcopy(record["folds"]),
            feature=copy.deepcopy(source_task["feature"]),
            label_version=source_task.get("label_version"),
            prepared_manifest_sha256=record["prepared_manifest"]["sha256"],
            provenance={k: copy.deepcopy(record[k]) for k in PROVENANCE_KEYS})
        _validate_row(row)
        _checked_graph(row)
        tasks[tid] = row
    document = dict(version=VERSION, dataset="A", tasks=tasks,
        source_loading="exact source bytes loaded once per task; existing layers parse independently",
        source_metadata_policy="preserve recorded metadata; never guess compiler version",
        labels_used_for_analysis=False, training_executed=False)
    output.mkdir(parents=True)
    path = output / "manifest.json"
    write_json(path, document)
    write_json(output / "manifest.seal.json", dict(version=VERSION, sha256=sha256(path),
        task_ids=sorted(tasks), training_executed=False))
    load_manifest(path)
    return path


def load_manifest(path, check_files=True):
    """Always check seal/schema; optionally defer checks of referenced assets."""
    path = Path(path).resolve()
    seal = read_json(path.with_name("manifest.seal.json"))
    if seal.get("version") != VERSION or seal.get("training_executed") is not False:
        raise ValueError("Unknown input seal version")
    checked(path, seal.get("sha256"))
    doc = read_json(path)
    if (doc.get("version") != VERSION or not isinstance(doc.get("tasks"), dict) or not doc["tasks"]
            or doc.get("labels_used_for_analysis") is not False or doc.get("training_executed") is not False):
        raise ValueError("Unknown or empty input manifest")
    if sorted(doc["tasks"]) != seal.get("task_ids"):
        raise ValueError("Input seal task matrix differs")
    for tid, record in doc["tasks"].items():
        if record.get("task_id") != tid:
            raise ValueError("Manifest task key differs from record")
        _validate_row(record, check_files=check_files)
    return doc


def load_task(record):
    """Load one verified original graph and its exact source/metadata maps."""
    _validate_row(record)
    graph = _checked_graph(record)
    sources, metadata = {}, {}
    for name, ref in record["sources"].items():
        path = checked_ref(ref)
        source = path.read_bytes().decode("utf8")
        # Preserve CRLF and other source coordinates exactly; do not read_text.
        sources[name], metadata[name] = source, copy.deepcopy(ref.get("metadata"))
    return graph, sources, metadata
