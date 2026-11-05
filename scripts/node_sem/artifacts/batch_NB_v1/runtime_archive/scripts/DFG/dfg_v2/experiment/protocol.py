"""Read-only nested-fold adapter for DFG v2.

The existing sealed split documents remain ddg-nested-paired-v1; this module
adds an execution-protocol identity without rewriting those documents. Unlike
paper_kfold, inner validation selects checkpoints and outer test is scored only
after fitting. Full fixed-graph message passing is separate from supervision.
"""
import copy

from scripts.DFG.experiments.protocol import validate_fold_document
from scripts.DFG.integration.io import read_json
from ..tasks import checked_ref, read_labels

PROTOCOL_NAME = "dfg-v2-nested"
PROTOCOL_VERSION = "dfg-v2-nested-v1"
FORWARD_SCOPE = "full_fixed_task_graph"
SCORE_ROLE = "outer_test"
SELECTION_ROLE = "inner_val"
PARTS = ("inner_train", "inner_val", "outer_test")


def validate_parts(parts, population):
    """Return sorted file lists after checking an exact disjoint partition.

    Accept either part-name keys or frozen *_files keys. Mixed spellings are
    rejected instead of allowing one supplied partition to silently override
    another. Fold metadata, such as fold/inner_seed, is retained by callers.
    """
    population = list(population)
    if (not population or len(population) != len(set(population))
            or any(not isinstance(f, str) or not f for f in population)):
        raise ValueError("Invalid task file population")
    if not isinstance(parts, dict):
        raise ValueError("Nested partition requires a mapping")
    result = {}
    for role in PARTS:
        keys = [k for k in (role, role + "_files") if k in parts]
        if len(keys) != 1:
            raise ValueError("Exactly one file list required for " + role)
        values = parts[keys[0]]
        if (not isinstance(values, (tuple, list)) or not values
                or any(not isinstance(f, str) or not f for f in values)
                or len(values) != len(set(values))):
            raise ValueError("Empty, invalid or duplicate nested files: " + role)
        result[role] = sorted(values)
    sets = [set(result[role]) for role in PARTS]
    if any(sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError("Train/validation/test file overlap")
    if set.union(*sets) != set(population):
        raise ValueError("Nested parts do not partition the task population")
    return result


def load_folds(record):
    """Read folds from a verified inputs/manifest.json task record.

    No split generation, resampling, label conversion, or file filtering takes
    place here. Referenced fold and graph-label bytes are checked independently.
    """
    document = validate_fold_document(read_json(checked_ref(record["folds"])))
    labels = read_labels(record["labels"])
    files = record["graph_files"]
    if (record.get("task") != document["task"]
            or document["files"] != files
            or document["seed"] != 1 or document["inner_fraction"] != .2
            or document["prepared_manifest_sha256"] != record["prepared_manifest_sha256"]):
        raise ValueError("Frozen nested folds differ from input task")
    if any(f not in labels for f in files):
        raise ValueError("Task file missing from graph labels")
    if document["file_labels"] != {f: labels[f] for f in files}:
        raise ValueError("Frozen nested file labels differ from input task")
    for split in document["folds"]:
        validate_parts(split, files)
    return copy.deepcopy(document)


def select_split(record, fold):
    """Return an unchanged frozen fold by index, after complete-file checks."""
    document = load_folds(record)
    if type(fold) is not int or not 0 <= fold < document["k_folds"]:
        raise ValueError("Unknown frozen fold index")
    return copy.deepcopy(document["folds"][fold])


def load_protocol(manifest_path, task_id):
    """Load a sealed input manifest and expose one task's frozen protocol."""
    from ..inputs import load_manifest
    manifest = load_manifest(manifest_path, check_files=True)
    if task_id not in manifest["tasks"]:
        raise ValueError("Task not registered in input manifest: " + str(task_id))
    record = manifest["tasks"][task_id]
    document = load_folds(record)
    return dict(protocol=PROTOCOL_NAME, protocol_version=PROTOCOL_VERSION,
                score_role=SCORE_ROLE, selection_role=SELECTION_ROLE,
                forward_scope=FORWARD_SCOPE, task_id=task_id, task=record["task"],
                folds_ref=copy.deepcopy(record["folds"]),
                labels_ref=copy.deepcopy(record["labels"]), document=document)
