"""Versioned single-level CV, derived exactly from frozen nested fold files."""
import argparse
import copy
from pathlib import Path
from .common import ROOT, new_output, read_json, write_json, sha256, digest
from . import protocol as nested

NAME = "paper_kfold"
VERSION = "ddg-paper-kfold-v1"
INITIALIZATION_VERSION = "semantic-paired-native-xavier-v1"
FORWARD_SCOPE = "complete_fixed_task_graph"
SCORE_ROLE = "cv_validation"
SCHEMA_POLICY = "registered_schema_allow_train_unseen"


def protocol_output(path, name=NAME):
    p = new_output(path)
    required = ROOT / "artifacts" / name
    if required not in p.parents:
        raise ValueError("Output must be below artifacts/" + name + "/")
    return p


def document_hash(doc):
    return digest({k: v for k, v in doc.items() if k != "split_sha256"})


def convert_document(source, source_file_sha256=None):
    nested.validate_fold_document(source)
    doc = {"protocol": NAME, "protocol_version": VERSION,
           "task": source["task"], "k_folds": source["k_folds"],
           "seed": source["seed"], "files": copy.deepcopy(source["files"]),
           "file_labels": copy.deepcopy(source["file_labels"]),
           "prepared_manifest_sha256": source["prepared_manifest_sha256"],
           "forward_scope": FORWARD_SCOPE, "score_role": SCORE_ROLE,
           "schema_policy": SCHEMA_POLICY,
           "source_nested_document": copy.deepcopy(source),
           "source_nested_file_sha256": source_file_sha256,
           "folds": [{"fold": f["fold"],
                      "train_files": sorted(f["inner_train_files"] + f["inner_val_files"]),
                      "val_files": list(f["outer_test_files"])} for f in source["folds"]],
           "note": "Single-level CV validation selects and scores the checkpoint on the same val fold. "
                   "Not an independent outer test. No resampling or new seed selection."}
    doc["split_sha256"] = document_hash(doc)
    validate_document(doc)
    return doc


def validate_document(doc):
    expected = {"protocol": NAME, "protocol_version": VERSION,
                "forward_scope": FORWARD_SCOPE, "score_role": SCORE_ROLE,
                "schema_policy": SCHEMA_POLICY}
    if any(doc.get(k) != v for k, v in expected.items()):
        raise ValueError("Wrong paper_kfold protocol/role/scope")
    if doc.get("split_sha256") != document_hash(doc):
        raise ValueError("Paper split hash mismatch")
    source = doc["source_nested_document"]
    nested.validate_fold_document(source)
    for key in ("task", "k_folds", "seed", "files", "file_labels", "prepared_manifest_sha256"):
        if doc.get(key) != source[key]:
            raise ValueError("Paper split changed frozen source " + key)
    expected_folds = [{"fold": f["fold"],
                       "train_files": sorted(f["inner_train_files"] + f["inner_val_files"]),
                       "val_files": list(f["outer_test_files"])} for f in source["folds"]]
    if doc.get("folds") != expected_folds:
        raise ValueError("Paper split is not the exact nested train-union / outer-to-val conversion")
    return doc


def initialize_pair(e0, e1, seed):
    # The algorithm is reused without changing its random draws or mapping.
    audit = nested.paired_initialize(e0, e1, seed=seed)
    audit.pop("protocol_version")
    audit["initialization_version"] = INITIALIZATION_VERSION
    audit["initializer_source_sha256"] = sha256(Path(nested.__file__))
    return audit


def convert_directory(source, output):
    source, output = Path(source).resolve(), protocol_output(output)
    docs = {}
    for task in ("contract", "node"):
        p = source / (task + "_folds.json")
        docs[task] = convert_document(read_json(p), sha256(p))
    if docs["contract"]["prepared_manifest_sha256"] != docs["node"]["prepared_manifest_sha256"]:
        raise ValueError("Tasks belong to different prepared cohorts")
    output.mkdir(parents=True)
    for task, doc in docs.items():
        write_json(output / (task + "_folds.json"), doc)
    print("Converted frozen train unions; score role=CV validation: " + str(output), flush=True)
    return docs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--nested_dir", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    convert_directory(a.nested_dir, a.output)


if __name__ == "__main__":
    main()
