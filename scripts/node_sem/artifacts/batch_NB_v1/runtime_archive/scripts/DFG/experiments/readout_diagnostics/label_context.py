"""Read-only node-error context from frozen predictions and five-file label evidence.

REFERENCE_AGREED means agreement with an existing public endpoint projection,
not certified semantic ground truth. All other files remain UNREVIEWED.
No graph/model imports, prediction changes, relabeling, or metric replacement.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VARIANTS = ("HCG", "HCG_DDG", "HCG_DDG_GUARD")
CHECKPOINTS = ("best", "last")
STRATA = ("REFERENCE_AGREED", "DISPUTED", "UNREVIEWED")
CATEGORIES = ("reentrancy", "access_control")
TARGET_FILES = {
    "reentrancy": ("buggy_18.sol", "0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol"),
    "access_control": ("buggy_18.sol", "buggy_26.sol", "parity_wallet_bug_2.sol"),
}
HARD_COUNTS = {
    ("reentrancy_author", "buggy_18.sol"): (424, 252, 197),
    ("access_control_author", "buggy_18.sol"): (284, 87, 83),
    ("access_control_author", "buggy_26.sol"): (143, 42, 42),
}
COUNT_FIELDS = ("nodes", "errors", "false_positive", "false_negative",
                "true_positive", "true_negative", "author_positive")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Inputs:
    """Track every consumed input and recheck it before publishing outputs."""

    def __init__(self):
        self.hashes = {}

    def protect(self, path, expected=None):
        path = Path(path).resolve()
        actual = sha256(path)
        require(expected is None or expected == actual, "SHA256 mismatch: " + str(path))
        require(str(path) not in self.hashes or self.hashes[str(path)] == actual,
                "Input changed during run: " + str(path))
        self.hashes[str(path)] = actual
        return actual

    def read(self, path, expected=None):
        self.protect(path, expected)
        return json.loads(Path(path).read_text(encoding="utf8"))

    def verify_unchanged(self):
        for path, expected in self.hashes.items():
            require(sha256(path) == expected, "Input changed during run: " + path)


def identity(row):
    """Never join by basename or node number alone."""
    key = (row["cohort"], row["file"], row["source_sha256"],
           str(row["original_graph_node_id"]))
    require(all(key), "Incomplete node identity: " + repr(key))
    require(len(key[2]) == 64 and all(c in "0123456789abcdef" for c in key[2]),
            "Invalid source SHA256: " + repr(key))
    return key


def index_unique(rows, key, description):
    indexed = {}
    for row in rows:
        item = key(row)
        require(item not in indexed, "Duplicate " + description + ": " + repr(item))
        indexed[item] = row
    return indexed


def binary(value, description):
    require(str(value) in ("0", "1"), "Nonbinary " + description)
    return int(value)


def normalize_prediction(row):
    item = dict(row)
    require(item["variant"] in VARIANTS, "Unknown variant")
    require(item["task_id"] == item["cohort"] + "_node", "Task/cohort mismatch")
    require(item["cohort"] in tuple(c + "_author" for c in CATEGORIES), "Unknown cohort")
    require(item["score_role"] == "cv_validation", "Invalid score role")
    item["fold"] = int(item["fold"])
    item["target"] = binary(item["target"], "target")
    identity(item)
    for checkpoint in CHECKPOINTS:
        item[checkpoint] = binary(item[checkpoint], checkpoint)
        probability = float(item[checkpoint + "_positive_probability"])
        require(math.isfinite(probability) and 0 <= probability <= 1, "Invalid probability")
        require(item[checkpoint] == int(probability > 0.5), "Frozen prediction/probability mismatch")
        item[checkpoint + "_positive_probability"] = probability
    return item


def load_frozen_predictions(batch, inputs):
    """Bind the combined CSV to sealed plans and hash-verified fit exports."""
    batch = Path(batch)
    plan = inputs.read(batch / "plan.json", inputs.read(batch / "plan.seal.json")["sha256"])
    baseline = Path(plan["source_batch"])
    oldplan = inputs.read(baseline / "plan.json",
                          inputs.read(baseline / "plan.seal.json")["sha256"])
    require(inputs.hashes[str((baseline / "plan.json").resolve())] == plan["source_plan_sha256"],
            "Baseline plan binding mismatch")
    csv_path = batch / "oof_predictions.csv"
    inputs.protect(csv_path)
    with csv_path.open(newline="", encoding="utf8") as stream:
        raw = list(csv.DictReader(stream))
    rows = [normalize_prediction(row) for row in raw if row["task_id"].endswith("_node")]
    index_unique(rows, lambda row: (row["variant"],) + identity(row), "OOF node")
    groups = defaultdict(list)
    for row in rows:
        groups[(row["task_id"], row["fold"], row["variant"])].append(row)
    expected_groups = set()
    for current_batch, current_plan, variants in (
            (baseline, oldplan, VARIANTS[:2]), (batch, plan, VARIANTS[2:])):
        for ref in current_plan["tasks"]:
            if not ref["task_id"].endswith("_node"):
                continue
            manifest = inputs.read(ref["manifest"], ref["sha256"])
            task, fold = manifest["task_id"], manifest["fold"]
            require((task, fold) == (ref["task_id"], ref["fold"]), "Task manifest identity mismatch")
            prepared = inputs.read(manifest["source_prepared_manifest"],
                                   manifest["source_prepared_manifest_sha256"])
            sources = prepared["sources"]
            for variant in variants:
                key = (task, fold, variant)
                expected_groups.add(key)
                require(key in groups, "Missing OOF fit: " + repr(key))
                folder = current_batch / "runs" / task / ("fold_" + str(fold)) / variant
                receipts = sorted(folder.glob("attempt_*/receipt.json"))
                require(len(receipts) == 1, "Missing/duplicate fit receipt: " + str(folder))
                receipt_path = receipts[0]
                receipt = inputs.read(receipt_path)
                for name, value in dict(status="complete", task_id=task, fold=fold,
                                        variant=variant, plan_sha256=digest(current_plan)).items():
                    require(receipt.get(name) == value, "Receipt identity mismatch: " + name)
                artifacts = receipt["artifacts"]
                attempt = receipt_path.parent
                binding = inputs.read(attempt / "binding.json", artifacts["binding.json"])
                require(digest(binding) == receipt["binding_sha256"], "Binding digest mismatch")
                require(binding["plan_sha256"] == digest(current_plan), "Binding plan mismatch")
                require(binding["task_id"] == task and binding["variant"] == variant
                        and binding["cohort"] == manifest["cohort"], "Binding task mismatch")
                require(binding["split"] == manifest["split"], "Binding split mismatch")
                require(binding["graph_sha256"] == manifest["graphs"][variant]["sha256"],
                        "Binding graph SHA mismatch")
                require(binding["node_attributes_sha256"] ==
                        manifest["graphs"][variant]["node_attributes_sha256"],
                        "Binding node attributes mismatch")
                exported = inputs.read(attempt / "cv_validation_predictions.json",
                                       artifacts["cv_validation_predictions.json"])
                expected = index_unique(exported,
                                        lambda row: (row["file"], str(row["original_graph_node_id"])),
                                        "fit export node")
                observed = index_unique(groups[key],
                                        lambda row: (row["file"], str(row["original_graph_node_id"])),
                                        "fit CSV node")
                require(set(expected) == set(observed), "Unmatched CSV/export node identities")
                require({row["file"] for row in exported} == set(manifest["split"]["val_files"]),
                        "Validation file population mismatch")
                for node_key, original in expected.items():
                    row = observed[node_key]
                    require(row["cohort"] == manifest["cohort"], "CSV cohort mismatch")
                    source = sources[row["file"]]
                    require(row["source_sha256"] == source["sha256"], "CSV source SHA mismatch")
                    inputs.protect(source["path"], source["sha256"])
                    for name in ("target", "best", "last", "model_node_id"):
                        require(int(row[name]) == original[name], "Frozen export mismatch: " + name)
                    for name in ("node_type", "score_role", "graph_label_anchor"):
                        require(row[name] == original[name], "Frozen export mismatch: " + name)
                    require(json.loads(row["graph_stored_source_lines"]) ==
                            original["graph_stored_source_lines"], "Node coordinates mismatch")
                    for checkpoint in CHECKPOINTS:
                        name = checkpoint + "_positive_probability"
                        require(row[name] == original[name], "Frozen export mismatch: " + name)
    require(set(groups) == expected_groups, "Unexpected/missing OOF fit groups")
    return rows, {"full_oof_rows": len(raw), "node_oof_rows": len(rows),
                  "fit_exports_verified": len(expected_groups),
                  "prediction_source": str(csv_path.resolve())}


def review_key(cohort, filename, source_sha, node_id):
    return identity(dict(cohort=cohort, file=filename, source_sha256=source_sha,
                         original_graph_node_id=node_id))


def load_review(review_dir, prior_audit, label_root, inputs):
    """Only the five fully reviewed files establish primary review coverage."""
    review_dir, prior_audit, label_root = map(Path, (review_dir, prior_audit, label_root))
    delivery = inputs.read(review_dir / "delivery_manifest.json")
    prior_delivery = inputs.read(prior_audit.parent / "delivery_manifest.json")
    audit_refs = [entry for entry in prior_delivery["files"]
                  if Path(entry["path"]).resolve() == prior_audit.resolve()]
    require(len(audit_refs) == 1, "Missing/duplicate prior audit delivery binding")
    prior = inputs.read(prior_audit, audit_refs[0]["sha256"])
    protected = delivery["new_artifacts_sha256"]
    evidence = {}
    reviewed_files = {}
    for category, filenames in TARGET_FILES.items():
        for filename in filenames:
            name = category + "__" + Path(filename).stem + ".json"
            detail = inputs.read(review_dir / name, protected[name])
            summary = detail["summary"]
            source_sha = summary["source_sha256"]
            inputs.protect(summary["source"], source_sha)
            local = summary["source_check"]
            require(local["local_sha256"] == source_sha == local["canonical_sha256"],
                    "Target review source mismatch")
            inputs.protect(local["local_source"], source_sha)
            require(len(detail["nodes"]) == summary["nodes"], "Review node count mismatch")
            cohort = category + "_author"
            file_key = (cohort, filename, source_sha)
            reviewed_files[file_key] = len(detail["nodes"])
            nodes = index_unique(detail["nodes"], lambda node: str(node["node_id"]),
                                 "targeted review node")
            disputes = 0
            for node_id, node in nodes.items():
                author = binary(node["author_label"], "review author label")
                public = binary(node["public_endpoint_label"], "public endpoint label")
                key = review_key(cohort, filename, source_sha, node_id)
                require(key not in evidence, "Duplicate targeted review identity")
                evidence[key] = dict(author_label=author, public_endpoint_label=public,
                                     node_type=node["node_type"], evidence_file=str(review_dir / name))
                disputes += author != public
            require(disputes == summary["disagreements"], "Review disagreement count mismatch")
    require(len(reviewed_files) == delivery["files"] == 5, "Targeted file count mismatch")
    require(len(evidence) == delivery["nodes"] == 1127, "Targeted node count mismatch")
    disagreement_keys = {key for key, node in evidence.items()
                         if node["author_label"] != node["public_endpoint_label"]}
    require(len(disagreement_keys) == delivery["disagreements"] == 353,
            "Five-file disagreement count mismatch")
    full_differences = {}
    for category in CATEGORIES:
        references = [entry for entry in prior["errors_vs_label_disagreements"]
                      if entry["task_id"] == category + "_author_node"]
        require(references, "Missing prior label-audit binding")
        manifest_shas = {entry["label_audit_manifest_sha256"] for entry in references}
        difference_shas = {entry["label_differences_sha256"] for entry in references}
        require(len(manifest_shas) == len(difference_shas) == 1, "Conflicting prior label bindings")
        folder = label_root / category
        manifest = inputs.read(folder / "manifest.json", next(iter(manifest_shas)))
        differences = inputs.read(folder / "label_differences.json", next(iter(difference_shas)))
        require(inputs.hashes[str((folder / "label_differences.json").resolve())] ==
                manifest["output_sha256"]["label_differences.json"], "Label output binding mismatch")
        require(manifest["alignment_to_author"]["exact_node_identity"], "Unaligned label evidence")
        for node in differences:
            filename = node["source_file"]
            source = manifest["source_checks"][filename]
            key = review_key(category + "_author", filename, source["local_sha256"],
                             node["author_node_id"])
            require(key not in full_differences, "Duplicate full label-difference identity")
            require(node["node_id"] == node["author_node_id"], "Original node ID mapping mismatch")
            require(key in evidence, "Unmatched full label difference: " + repr(key))
            checked = evidence[key]
            require((node["author"], node["public"], node["node_type"]) ==
                    (checked["author_label"], checked["public_endpoint_label"], checked["node_type"]),
                    "Targeted/full label evidence mismatch")
            full_differences[key] = node
    require(set(full_differences) == disagreement_keys, "Full/targeted disagreement population mismatch")
    return evidence, reviewed_files


def stratify(rows, evidence, reviewed_files):
    """Preserve every frozen prediction and attach label-context columns."""
    rows = [normalize_prediction(row) for row in rows]
    index_unique(rows, lambda row: (row["variant"],) + identity(row), "OOF node")
    populations = {variant: {identity(row) for row in rows if row["variant"] == variant}
                   for variant in VARIANTS}
    require(all(populations[variant] == populations[VARIANTS[0]] for variant in VARIANTS),
            "Variant node population mismatch")
    population = populations[VARIANTS[0]]
    require(set(evidence) <= population, "Unmatched reviewed node identities")
    by_file = Counter(key[:3] for key in population)
    for file_key, count in reviewed_files.items():
        require(by_file[file_key] == count, "Reviewed file population mismatch")
        require(sum(key[:3] == file_key for key in evidence) == count,
                "Incomplete reviewed file evidence")
    sources = defaultdict(set)
    for key in population:
        sources[key[:2]].add(key[2])
    require(all(len(values) == 1 for values in sources.values()), "Mismatched source hashes within file")
    author_targets = {}
    annotated = []
    for row in rows:
        key = identity(row)
        previous = author_targets.setdefault(key, (row["target"], row["fold"], row["node_type"]))
        require(previous == (row["target"], row["fold"], row["node_type"]),
                "Frozen variant target/fold/type mismatch")
        context = evidence.get(key)
        if context is None:
            require(key[:3] not in reviewed_files, "Unmatched node within reviewed file")
            stratum, author, public, evidence_file = "UNREVIEWED", "", "", ""
        else:
            author, public = context["author_label"], context["public_endpoint_label"]
            require(row["target"] == author, "Frozen target does not equal reviewed author label")
            require(row["node_type"] == context["node_type"], "Reviewed node type mismatch")
            stratum = "DISPUTED" if author != public else "REFERENCE_AGREED"
            evidence_file = context.get("evidence_file", "")
        item = dict(row, review_stratum=stratum, reviewed_author_label=author,
                    public_endpoint_label=public, review_evidence=evidence_file)
        for checkpoint in CHECKPOINTS:
            target, predicted = row["target"], row[checkpoint]
            item[checkpoint + "_outcome"] = (
                "TP" if target and predicted else "FN" if target else "FP" if predicted else "TN")
        annotated.append(item)
    return annotated


def counts(rows, checkpoint):
    result = dict.fromkeys(COUNT_FIELDS, 0)
    for row in rows:
        target, prediction = row["target"], row[checkpoint]
        result["nodes"] += 1
        result["author_positive"] += target
        result["errors"] += target != prediction
        result["false_positive"] += target == 0 and prediction == 1
        result["false_negative"] += target == 1 and prediction == 0
        result["true_positive"] += target == 1 and prediction == 1
        result["true_negative"] += target == 0 and prediction == 0
    return result


def summarize(rows):
    aggregate, per_file = [], []
    groups = defaultdict(list)
    file_groups = defaultdict(list)
    for row in rows:
        groups[(row["task_id"], row["cohort"], row["variant"])].append(row)
        file_groups[(row["task_id"], row["cohort"], row["variant"], row["fold"],
                     row["file"], row["source_sha256"])].append(row)
    for mapping, destination, names in (
            (groups, aggregate, ("task_id", "cohort", "variant")),
            (file_groups, per_file, ("task_id", "cohort", "variant", "fold", "file", "source_sha256"))):
        for key, selected in sorted(mapping.items()):
            for checkpoint in CHECKPOINTS:
                total = counts(selected, checkpoint)
                strata = []
                for stratum in STRATA:
                    value = counts([row for row in selected if row["review_stratum"] == stratum],
                                   checkpoint)
                    strata.append(value)
                    destination.append(dict(zip(names, key), checkpoint=checkpoint,
                                            review_stratum=stratum, **value))
                require(all(sum(value[field] for value in strata) == total[field]
                            for field in COUNT_FIELDS), "Stratum totals do not conserve population")
                destination.append(dict(zip(names, key), checkpoint=checkpoint,
                                        review_stratum="ALL", **total))
    return aggregate, per_file


def verify_hard_counts(per_file):
    checked = []
    for (cohort, filename), expected in HARD_COUNTS.items():
        for variant in VARIANTS:
            selected = {row["review_stratum"]: row for row in per_file
                        if (row["cohort"], row["file"], row["variant"], row["checkpoint"]) ==
                        (cohort, filename, variant, "best")}
            require("ALL" in selected and "DISPUTED" in selected, "Missing hard-file counts")
            actual = (selected["ALL"]["nodes"], selected["ALL"]["errors"], selected["DISPUTED"]["errors"])
            require(actual == expected, "Hard-file count mismatch: " + repr((cohort, filename, variant, actual)))
            checked.append(dict(cohort=cohort, file=filename, variant=variant, checkpoint="best",
                                nodes=actual[0], errors=actual[1], disputed_errors=actual[2]))
    return checked


def write_csv(path, rows):
    require(bool(rows), "Refusing empty CSV")
    with Path(path).open("x", newline="", encoding="utf8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(batch, review_dir, prior_audit, label_root, output):
    inputs = Inputs()
    rows, metadata = load_frozen_predictions(batch, inputs)
    evidence, reviewed_files = load_review(review_dir, prior_audit, label_root, inputs)
    annotated = stratify(rows, evidence, reviewed_files)
    aggregate, per_file = summarize(annotated)
    hard_checks = verify_hard_counts(per_file)
    inputs.verify_unchanged()
    output = Path(output)
    require(not output.exists() or not any(output.iterdir()), "Output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    node_columns = ("task_id", "cohort", "fold", "variant", "file", "source_sha256",
                    "original_graph_node_id", "model_node_id", "node_type", "target", "score_role",
                    "best", "best_positive_probability", "last", "last_positive_probability",
                    "review_stratum", "reviewed_author_label", "public_endpoint_label",
                    "review_evidence", "best_outcome", "last_outcome")
    write_csv(output / "node_context.csv", [{name: row[name] for name in node_columns} for row in annotated])
    write_csv(output / "aggregate.csv", aggregate)
    write_csv(output / "per_file.csv", per_file)
    report = dict(
        schema_version="readout-label-context-v1", created_utc=datetime.now(timezone.utc).isoformat(),
        status="passed", **metadata, reviewed_files=len(reviewed_files), reviewed_unique_nodes=len(evidence),
        disputed_unique_nodes=sum(node["author_label"] != node["public_endpoint_label"]
                                  for node in evidence.values()),
        strata=list(STRATA), target_policy="Frozen author targets; no substitutions or discarded cases.",
        reference_policy="Existing public endpoint projection is contextual evidence, not certified semantic ground truth.",
        coverage_policy="Only the five targeted-review files are reviewed. All other nodes are UNREVIEWED.",
        full_difference_policy="Hash-bound full label_differences cross-checks the 353 disputed identities; absence does not establish review.",
        score_role="cv_validation", independent_test=False, training_executed=False,
        model_forward_executed=False, graph_deserialization_executed=False,
        predictions_altered=False, labels_altered=False, official_metrics_altered=False,
        hard_file_checks=hard_checks, aggregate=aggregate, input_sha256=inputs.hashes,
        outputs_sha256={name: sha256(output / name)
                        for name in ("node_context.csv", "aggregate.csv", "per_file.csv")})
    inputs.verify_unchanged()
    with (output / "audit.json").open("x", encoding="utf8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return report


def main():
    root = Path(__file__).resolve().parents[4]
    artifacts = root / "scripts/DFG/experiments/artifacts"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=artifacts / "paper_kfold/guard_extension_v1")
    parser.add_argument("--review-dir", type=Path, default=artifacts / "targeted_label_review_v1")
    parser.add_argument("--prior-audit", type=Path, default=artifacts / "next_step_review_v1/audit.json")
    parser.add_argument("--label-root", type=Path, default=root.parent / "ge-sc-llm/Test_code/label_pipeline/artifacts/public_endpoints_verified_v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.batch, args.review_dir, args.prior_audit, args.label_root, args.output)
    print(json.dumps({name: report[name] for name in
                      ("status", "node_oof_rows", "reviewed_files", "reviewed_unique_nodes",
                       "disputed_unique_nodes", "fit_exports_verified")}, indent=2))


if __name__ == "__main__":
    main()
