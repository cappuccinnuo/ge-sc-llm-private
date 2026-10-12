"""Codex 2026-10-10: independently verified raw annotations for Dataset A.

No graph labels are read here. The released contract labels select the corpus;
a contract-negative entry is a dataset assignment, not proof of security.
Returned annotation coordinates always address the returned canonical source.
"""
import csv
import difflib
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SOLIDIFI_DIRS = {
    "access_control": "tx.origin",
    "arithmetic": "Overflow-Underflow",
    "denial_of_service": "Unhandled-Exceptions",
    "front_running": "TOD",
    "reentrancy": "Re-entrancy",
    "time_manipulation": "Timestamp-Dependency",
    "unchecked_low_level_calls": "Unchecked-Send",
}
_COMMENT = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
    re.DOTALL | re.MULTILINE,
)
_PRAGMA = re.compile(r"^\s*pragma\s+solidity\s+[^;]+;\s*$")
_HEADER = ["loc", "length", "bug type", "approach"]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(path):
    # Normalize CRLF only for comparison; hashes always cover original bytes.
    return path.read_text(encoding="utf8")


def _preprocess(source):
    """Mirror parser_driver's empty-line removal then non-Python comments pass."""
    source = "\n".join(x for x in source.split("\n") if x.strip())
    source = _COMMENT.sub(
        lambda match: " " if match.group(0).startswith("/") else match.group(0),
        source,
    )
    return "\n".join(x for x in source.split("\n") if x.strip())


def _pragma_normalized(source):
    return [
        "__SOLIDITY_PRAGMA__" if _PRAGMA.fullmatch(line) else line
        for line in _preprocess(source).split("\n")
    ]


def _source_comparison(local, canonical):
    left, right = _text(local), _text(canonical)
    left_lines, right_lines = left.splitlines(), right.splitlines()
    changes = []
    for tag, a, b, c, d in difflib.SequenceMatcher(
            a=left_lines, b=right_lines, autojunk=False).get_opcodes():
        if tag != "equal":
            changes.append({
                "operation": tag,
                "local_original_lines": list(range(a + 1, b + 1)),
                "canonical_original_lines": list(range(c + 1, d + 1)),
            })
    if local.read_bytes() == canonical.read_bytes():
        kind = "byte_identical"
    elif left == right:
        kind = "line_endings_only"
    elif _preprocess(left) == _preprocess(right):
        kind = "comments_or_blank_lines_only_same_preprocessed_text"
    elif _pragma_normalized(left) == _pragma_normalized(right):
        kind = "pragma_and_comments_only_same_preprocessed_positions"
    else:
        raise ValueError(
            "Local/canonical source code differs beyond allowed preprocessing/"
            "same-position pragma changes: " + str(local) + " vs " + str(canonical)
        )
    return {
        "local_source": str(local), "canonical_source": str(canonical),
        "local_sha256": _sha(local), "canonical_sha256": _sha(canonical),
        "source_comparison": kind, "changed_original_line_ranges": changes,
        "local_original_lines": len(left_lines),
        "canonical_original_lines": len(right_lines),
        "local_preprocessed_lines": len(_preprocess(left).splitlines()),
        "canonical_preprocessed_lines": len(_preprocess(right).splitlines()),
        "mapping_basis": "canonical_source_original_1based",
    }


def _records(value, category, source):
    if not isinstance(value, list):
        raise ValueError("Annotations must be a list: " + str(source))
    result = []
    count = len(_text(source).splitlines())
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get("category"), str):
            raise ValueError("Malformed annotation record")
        if record["category"] != category:
            continue
        lines = record.get("lines")
        if not isinstance(lines, list) or not lines or any(
                type(line) is not int or line < 1 or line > count for line in lines):
            raise ValueError("Invalid raw annotation coordinates: " + str(source))
        item = {"category": category, "lines": sorted(set(lines))}
        if item not in result:
            result.append(item)
    return result


def _csv_annotation(path, source, category):
    count = len(_text(source).splitlines())
    intervals, coverage, raw_rows = [], Counter(), []
    extra_column_values = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames
        if header not in (_HEADER, _HEADER + [""]):
            raise ValueError("Unexpected CSV header in " + str(path) + ": " +
                             repr(reader.fieldnames))
        for number, row in enumerate(reader, 2):
            if None in row or any(row.get(key) is None for key in _HEADER):
                raise ValueError("Malformed CSV row %d in %s" % (number, path))
            if not re.fullmatch(r"[0-9]+", row["loc"].strip()) or not re.fullmatch(
                    r"[0-9]+", row["length"].strip()):
                raise ValueError("Non-integer interval in " + str(path))
            start, length = int(row["loc"]), int(row["length"])
            if start < 1 or length < 1 or start + length - 1 > count:
                raise ValueError("Out-of-bounds CSV interval at row %d in %s" %
                                 (number, path))
            intervals.append((start, length))
            raw_rows.append(tuple(row[key] for key in _HEADER))
            if "" in row:
                extra_column_values.append({"csv_row": number, "value": row[""]})
            coverage.update(range(start, start + length))
    if not intervals:
        raise ValueError("Empty BugLog: " + str(path))
    lines = sorted(coverage)
    return [{"category": category, "lines": lines}], {
        "csv": str(path), "csv_rows": len(intervals),
        "csv_header": header,
        "extra_anonymous_column": extra_column_values,
        "extra_column_used_as_coordinates": False,
        "duplicate_csv_rows": len(raw_rows) - len(set(raw_rows)),
        "duplicate_intervals": len(intervals) - len(set(intervals)),
        "overlapping_annotation_lines": sum(value > 1 for value in coverage.values()),
        "duplicate_line_occurrences": sum(coverage.values()) - len(coverage),
        "annotation_lines": len(lines),
        "csv_bug_type_values": sorted({row[2] for row in raw_rows}),
        "csv_approach_values": sorted({row[3] for row in raw_rows}),
        "interval_rule": "[loc, loc+length-1], merged per file",
    }


def load_annotations(repo, category, filenames, contract_labels):
    """Return (annotations, canonical_sources, provenance, input_sha256).

    Inputs are source filenames and an explicit {filename: 0/1} contract manifest.
    Seven category names use the same algorithm, without filename exceptions.
    Missing or ambiguous positive annotations are errors, never silent negatives.
    """
    repo = Path(repo).resolve()
    if category not in SOLIDIFI_DIRS:
        raise ValueError("Unsupported Dataset A category: " + repr(category))
    filenames = list(filenames)
    if len(filenames) != len(set(filenames)):
        raise ValueError("Duplicate filenames in corpus manifest")
    for name in filenames:
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".sol"):
            raise ValueError("Expected a source basename: " + repr(name))
        if name not in contract_labels or type(contract_labels[name]) is not int or contract_labels[name] not in (0, 1):
            raise ValueError("Missing/invalid binary contract assignment: " + name)

    local_dir = repo / "experiments/ge-sc-data/source_code" / category / "source_files"
    public_dir = repo / "data/SolidiFI-benchmark/buggy_contracts" / SOLIDIFI_DIRS[category]
    sb_path = repo / "data/smartbug-dataset/vulnerabilities.json"
    hgt_path = repo.parent / "ge-sc-transformer/data/solidifi_buggy_contracts" / category / "vulnerabilities.json"
    hgt_sb_path = repo.parent / "ge-sc-transformer/data/smartbug-dataset/vulnerabilities.json"
    hashes = {}

    def record_input(path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        hashes[str(path)] = _sha(path)

    for path in (sb_path, hgt_path):
        record_input(path)
    smartbugs = json.loads(sb_path.read_text(encoding="utf8"))
    hgt = json.loads(hgt_path.read_text(encoding="utf8"))
    if not isinstance(smartbugs, list) or not isinstance(hgt, list):
        raise ValueError("Annotation JSON must contain a list")
    hgt_by_name = {}
    for row in hgt:
        name = row["name"]
        if name in hgt_by_name:
            raise ValueError("Duplicate HGT SolidiFI filename: " + name)
        hgt_by_name[name] = row
    hgt_sb = {}
    if hgt_sb_path.exists():
        record_input(hgt_sb_path)
        hgt_sb = {
            (row["name"], row["path"]): row
            for row in json.loads(hgt_sb_path.read_text(encoding="utf8"))
        }

    annotations, sources, provenance = {}, {}, {}
    for name in sorted(filenames):
        local = local_dir / name
        record_input(local)
        if contract_labels[name] == 0:
            sources[name], annotations[name] = local, []
            provenance[name] = dict(
                _source_comparison(local, local), dataset="selected_clean",
                contract_target=0, annotation_lines=0,
                clean_basis="supplied_contract_manifest",
                absence_independently_proven=False,
            )
            continue

        if re.fullmatch(r"buggy_[0-9]+\.sol", name):
            source = public_dir / name
            csv_path = public_dir / ("BugLog_" + name[len("buggy_"):-len(".sol")] + ".csv")
            record_input(source)
            record_input(csv_path)
            compared = _source_comparison(local, source)
            records, csv_info = _csv_annotation(csv_path, source, category)
            if name not in hgt_by_name:
                raise ValueError("Missing HGT SolidiFI annotation: " + name)
            hgt_records = _records(hgt_by_name[name]["vulnerabilities"], category, source)
            hgt_lines = {line for record in hgt_records for line in record["lines"]}
            if hgt_lines != set(records[0]["lines"]):
                raise ValueError("Public CSV and HGT original annotation differ: " + name)
            sources[name], annotations[name] = source, records
            provenance[name] = dict(
                compared, **csv_info, dataset="SolidiFI", contract_target=1,
                hgt_annotation=str(hgt_path), hgt_annotation_compare="raw_line_sets_equal",
                hgt_record_count=len(hgt_records),
            )
            continue

        candidates = []
        for row in smartbugs:
            if Path(row["name"]).name != name:
                continue
            if any(v.get("category") == category for v in row.get("vulnerabilities", [])):
                candidates.append(row)
        if not candidates:
            raise ValueError("Positive contract lacks category-specific SmartBugs annotation: " + name)
        valid, errors = [], []
        for row in candidates:
            source = (sb_path.parent / row["path"]).resolve()
            if sb_path.parent.resolve() not in source.parents:
                raise ValueError("SmartBugs source path escapes dataset directory")
            record_input(source)
            try:
                compared = _source_comparison(local, source)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            records = _records(row["vulnerabilities"], category, source)
            valid.append((source, records, compared, row))
        if not valid:
            raise ValueError("No matching canonical SmartBugs source for " + name + ": " + repr(errors))
        # A filename is never enough: every applicable candidate must correspond.
        if errors:
            raise ValueError("Ambiguous same-name SmartBugs source for " + name + ": " + repr(errors))
        source, _, compared, _ = valid[0]
        records, old_differences = [], []
        for other, items, check, row in valid:
            # Two source snapshots with different original coordinates cannot share
            # one raw-line record even if they preprocess identically.
            if _text(other) != _text(source):
                raise ValueError("Multiple canonical SmartBugs snapshots for " + name)
            for item in items:
                if item not in records:
                    records.append(item)
            old = hgt_sb.get((row["name"], row["path"]))
            if old is not None:
                old_lines = sorted({line for v in old["vulnerabilities"]
                                    if v["category"] == category for line in v["lines"]})
                now_lines = sorted({line for v in items for line in v["lines"]})
                if old_lines != now_lines:
                    old_differences.append({"path": row["path"], "hgt_lines": old_lines,
                                            "canonical_lines": now_lines})
        if not records:
            raise ValueError("Positive contract has no validated annotation: " + name)
        sources[name], annotations[name] = source, records
        provenance[name] = dict(
            compared, dataset="SmartBugs", contract_target=1,
            annotation_json=str(sb_path),
            annotation_lines=len({line for record in records for line in record["lines"]}),
            annotation_paths=[row["path"] for _, _, _, row in valid],
            hgt_snapshot_line_differences=old_differences,
            hgt_snapshot_used_as_ground_truth=False,
        )
    return annotations, sources, provenance, hashes
