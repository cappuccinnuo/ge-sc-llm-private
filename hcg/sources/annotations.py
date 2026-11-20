"""Vulnerability line annotations, from public sources to graph coordinates.

Ported from Test_code/label_pipeline (raw_annotations.py, coordinates.py and
build_dataset.project_annotations, Codex, 2026-10-10) without changing the rules:

* SolidiFI files: the BugLog intervals [loc, loc+length-1], merged into one record
  per file, on the public benchmark copy of the file.
* SmartBugs files: records of the target category only, on the curated copy; every
  same-name candidate must correspond to the local file.
* DAppSCAN files (Dataset B): the line numbers of the target category's SWC entries in
  the MANDO-LLM authors' cleaned label file, on the cleaned source they refer to.
* Clean contracts carry no annotation.
* A local file may differ from its canonical copy only in ways that leave the
  preprocessed text (or its line positions, for a changed pragma) identical.
* Annotations are then projected into preprocessed coordinates: comment/blank
  removal as tree-sitter's parser driver does it, keeping for every preprocessed
  line the original lines whose code characters survive.
"""
import csv
import difflib
import json
import re
from collections import Counter
from pathlib import Path

from hcg.datasets.registry import SOLIDIFI_FILE

_COMMENT = re.compile(r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
                      re.DOTALL | re.MULTILINE)
_PRAGMA = re.compile(r"^\s*pragma\s+solidity\s+[^;]+;\s*$")
_HEADER = ["loc", "length", "bug type", "approach"]


# ---------------------------------------------------------------- preprocessing --
def preprocess(source):
    """Mirror parser_driver: drop empty lines, blank comments, drop new empty lines."""
    source = "\n".join(x for x in source.split("\n") if x.strip())
    source = _COMMENT.sub(lambda m: " " if m.group(0).startswith("/") else m.group(0),
                          source)
    return "\n".join(x for x in source.split("\n") if x.strip())


def preprocess_with_map(source):
    """(preprocessed text, [original 1-based lines behind each preprocessed line]).

    Removed comments, their replacement spaces and indentation contribute no
    provenance; only surviving non-whitespace code/string characters do.
    """
    kept = [(n, line) for n, line in enumerate(source.split("\n"), 1) if line.strip()]
    text = "\n".join(line for _, line in kept)
    origins = []
    for position, (number, line) in enumerate(kept):
        origins.extend(number if not char.isspace() else None for char in line)
        if position + 1 < len(kept):
            origins.append(None)
    parts, mapped, cursor = [], [], 0
    for match in _COMMENT.finditer(text):
        parts.append(text[cursor:match.start()])
        mapped.extend(origins[cursor:match.start()])
        if match.group(0).startswith("/"):
            parts.append(" ")
            mapped.append(None)
        else:
            parts.append(match.group(0))
            mapped.extend(origins[match.start():match.end()])
        cursor = match.end()
    parts.append(text[cursor:])
    mapped.extend(origins[cursor:])
    intermediate = "".join(parts)
    output, line_map, cursor = [], [], 0
    for line in intermediate.split("\n"):
        stop = cursor + len(line)
        if line.strip():
            output.append(line)
            line_map.append(sorted({n for n in mapped[cursor:stop] if n is not None}))
        cursor = stop + 1
    return "\n".join(output), line_map


def project(records, line_map):
    """Annotation records in original lines -> the same records in preprocessed lines."""
    return [dict(category=rec["category"],
                 lines=[p + 1 for p, origin in enumerate(line_map)
                        if set(rec["lines"]).intersection(origin)])
            for rec in records]


# ------------------------------------------------------------------ comparison --
def _text(path):
    return Path(path).read_text(encoding="utf8")


def compare_sources(local, canonical):
    """How a local corpus file differs from its canonical copy; raise if too much."""
    left, right = _text(local), _text(canonical)
    if Path(local).read_bytes() == Path(canonical).read_bytes():
        kind = "byte_identical"
    elif left == right:
        kind = "line_endings_only"
    elif preprocess(left) == preprocess(right):
        kind = "comments_or_blank_lines_only"
    elif _pragma_normalized(left) == _pragma_normalized(right):
        kind = "pragma_and_comments_only"
    else:
        raise ValueError("local and canonical source differ beyond preprocessing: %s vs %s"
                         % (local, canonical))
    changes = [op for op in difflib.SequenceMatcher(
        a=left.splitlines(), b=right.splitlines(), autojunk=False).get_opcodes()
        if op[0] != "equal"]
    return {"source_comparison": kind, "changed_blocks": len(changes)}


def _pragma_normalized(source):
    return ["__PRAGMA__" if _PRAGMA.fullmatch(line) else line
            for line in preprocess(source).split("\n")]


# ------------------------------------------------------------------ raw records --
def _category_records(value, category, source):
    count = len(_text(source).splitlines())
    result = []
    for record in value:
        if record.get("category") != category:
            continue
        lines = record.get("lines")
        if not isinstance(lines, list) or not lines or any(
                type(x) is not int or x < 1 or x > count for x in lines):
            raise ValueError("invalid annotation coordinates in %s" % source)
        item = {"category": category, "lines": sorted(set(lines))}
        if item not in result:
            result.append(item)
    return result


def _buglog_record(path, source, category):
    count = len(_text(source).splitlines())
    coverage, rows = Counter(), 0
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames not in (_HEADER, _HEADER + [""]):
            raise ValueError("unexpected BugLog header in %s: %r" % (path, reader.fieldnames))
        for number, row in enumerate(reader, 2):
            if None in row or any(row.get(key) is None for key in _HEADER):
                raise ValueError("malformed BugLog row %d in %s" % (number, path))
            if not (row["loc"].strip().isdigit() and row["length"].strip().isdigit()):
                raise ValueError("non-integer interval in %s" % path)
            start, length = int(row["loc"]), int(row["length"])
            if start < 1 or length < 1 or start + length - 1 > count:
                raise ValueError("out-of-bounds BugLog row %d in %s" % (number, path))
            coverage.update(range(start, start + length))
            rows += 1
    if not rows:
        raise ValueError("empty BugLog: %s" % path)
    return [{"category": category, "lines": sorted(coverage)}], rows


def load(corpus_dir, category, filenames, targets, label_root, smartbugs):
    """Per-file annotations (original lines of the canonical copy) and provenance.

    Returns (annotations, canonical_sources, provenance) keyed by file name. A
    vulnerable contract without a category annotation is an error, never a silent
    negative.
    """
    corpus_dir, label_root = Path(corpus_dir), Path(label_root)
    solidifi_dir = (label_root / "SolidiFI-benchmark/buggy_contracts" / category.solidifi_dir
                    if category.solidifi_dir else None)
    smartbugs_root = label_root / "smartbug-dataset"
    annotations, sources, provenance = {}, {}, {}
    for name in sorted(filenames):
        local = corpus_dir / name
        if targets[name] == 0:
            annotations[name], sources[name] = [], local
            provenance[name] = {"dataset": "clean", "source_comparison": "local"}
            continue
        match = SOLIDIFI_FILE.fullmatch(name)
        if match and solidifi_dir is not None:
            canonical = solidifi_dir / name
            check = compare_sources(local, canonical)
            records, rows = _buglog_record(solidifi_dir / ("BugLog_%s.csv" % match.group(1)),
                                           canonical, category.name)
            annotations[name], sources[name] = records, canonical
            provenance[name] = dict(check, dataset="SolidiFI", buglog_rows=rows)
            continue
        candidates = [row for row in smartbugs if Path(row["name"]).name == name and any(
            v.get("category") == category.name for v in row.get("vulnerabilities", []))]
        if not candidates:
            raise ValueError("vulnerable contract has no %s annotation: %s"
                             % (category.name, name))
        valid, records = [], []
        for row in candidates:
            canonical = (smartbugs_root / row["path"]).resolve()
            if smartbugs_root.resolve() not in canonical.parents:
                raise ValueError("SmartBugs path escapes the dataset: %s" % row["path"])
            check = compare_sources(local, canonical)  # raises on a mismatching twin
            valid.append((canonical, check, row))
        canonical = valid[0][0]
        for other, _, row in valid:
            if _text(other) != _text(canonical):
                raise ValueError("several canonical SmartBugs snapshots for %s" % name)
            for item in _category_records(row["vulnerabilities"], category.name, other):
                if item not in records:
                    records.append(item)
        if not records:
            raise ValueError("vulnerable contract has no usable annotation: %s" % name)
        annotations[name], sources[name] = records, canonical
        provenance[name] = dict(valid[0][1], dataset="SmartBugs",
                                paths=[row["path"] for _, _, row in valid])
    return annotations, sources, provenance


def dappscan_record(label_paths, source, swc_ids, category):
    """One record: lines of the label files' SWC entries in ``swc_ids`` ([] if none).

    Several label files are united: copies of one text in several DAppSCAN snapshots
    of a project carry their labels to the copy that is kept.
    """
    count = len(_text(source).splitlines())
    lines, kinds = set(), set()
    for label_path in label_paths:
        for entry in json.loads(_text(label_path))["SWCs"]:
            swc = "-".join(entry["category"].split("-")[:2])
            if swc not in swc_ids:
                continue
            numbers = entry["lineNumber"]
            if not isinstance(numbers, list) or any(type(x) is not int or x < 1 or x > count for x in numbers):
                raise ValueError("invalid line numbers for %s in %s" % (swc, label_path))
            lines.update(numbers)
            kinds.add(swc)
    return ([{"category": category, "lines": sorted(lines)}] if lines else []), sorted(kinds)


def load_composed(corpus_dir, category, entries, label_root):
    """Per-file annotations of a composed corpus (``hcg.sources.composition``).

    ``entries`` are the category's composition rows: SolidiFI rows use the BugLog rule
    above on the benchmark copy, DAppSCAN rows ``dappscan_record`` on the cleaned
    source, clean rows nothing. The corpus copy (LF line endings, same lines) is the
    text projected and returned. Same return value as ``load``.
    """
    corpus_dir, label_root = Path(corpus_dir), Path(label_root)
    annotations, sources, provenance = {}, {}, {}
    for entry in sorted(entries, key=lambda e: e["name"]):
        name, local = entry["name"], corpus_dir / entry["name"]
        canonical = label_root / entry["origin"]
        check = compare_sources(local, canonical)
        if entry["target"] == 0:
            annotations[name], sources[name] = [], local
            provenance[name] = dict(check, dataset=entry["source"], origin=entry["origin"])
        elif entry["source"] == "SolidiFI":
            match = SOLIDIFI_FILE.fullmatch(Path(entry["origin"]).name)
            records, rows = _buglog_record(canonical.parent / ("BugLog_%s.csv" % match.group(1)),
                                           canonical, category.name)
            annotations[name], sources[name] = records, local
            provenance[name] = dict(check, dataset="SolidiFI", origin=entry["origin"], buglog_rows=rows)
        elif entry["source"] == "DAppSCAN":
            records, kinds = dappscan_record([label_root / p for p in entry["labels"]], canonical,
                                             entry["swc"], category.name)
            if not records:
                raise ValueError("vulnerable contract has no %s line label: %s" % (category.name, name))
            annotations[name], sources[name] = records, local
            provenance[name] = dict(check, dataset="DAppSCAN", origin=entry["origin"], swc=kinds)
        else:
            raise ValueError("unknown source %r for %s" % (entry["source"], name))
    return annotations, sources, provenance


def load_smartbugs(label_root):
    return json.loads((Path(label_root) / "smartbug-dataset/vulnerabilities.json")
                      .read_text(encoding="utf8"))
