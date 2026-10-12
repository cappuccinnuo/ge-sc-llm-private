"""Codex 2026-10-08: explicit annotation rules, no graph or feature rewriting."""
import ast
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

def parse_records(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        value = ast.literal_eval(value)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Vulnerability records must be a list or None")
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get("category"), str):
            raise ValueError("Malformed vulnerability record")
        lines = record.get("lines")
        if not isinstance(lines, list) or any(type(n) is not int or n < 1 for n in lines):
            raise ValueError("Vulnerability lines must be positive integers")
    return value

def unique_records(records):
    seen = set()
    result = []
    for record in records:
        key = (record["category"], tuple(sorted(set(record["lines"]))))
        if key not in seen:
            seen.add(key)
            result.append({"lines": list(key[1]), "category": key[0]})
    return result

def hit_records(lines, records, category=None):
    covered = set(lines)
    return [
        record for record in records
        if (category is None or record["category"] == category)
        and covered.intersection(record["lines"])
    ] or None

def endpoints(value):
    if isinstance(value, str):
        value = ast.literal_eval(value)
    if not isinstance(value, list) or any(
        not isinstance(span, (list, tuple)) or len(span) not in (1, 2)
        or any(type(n) is not int or n < 1 for n in span)
        for span in value
    ):
        raise ValueError("Author coordinates must be [[line]] or [[start,end], ...]")
    return sorted({n for span in value for n in span})

def unquote(text):
    if isinstance(text, str) and text.startswith('"') and text.endswith('"'):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            pass
    return text

def canonical_code(text):
    # Used ONLY for matching serialized assets. Never replace the model's code/token.
    text = unquote(text or "").replace("\\n", "\n").replace('\\"', '"')
    return re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)

def identity(data):
    label = unquote(data.get("label", ""))
    match = re.search(r"(\d+)-([a-z_]+)-(\d+)-(\d+)$", label)
    anchor = ("ast", int(match.group(1))) if match else None
    if anchor is None:
        match = re.match(r"(\d+)_ end_(?:if|loop)", label)
        if match:
            anchor = ("synthetic_start", int(match.group(1)))
    return (data["source_file"], data["node_type"], canonical_code(data["code"]), anchor)

def align_graphs(local, author):
    left, right = defaultdict(list), defaultdict(list)
    for n, d in local.nodes(data=True):
        left[identity(d)].append(n)
    for n, d in author.nodes(data=True):
        right[identity(d)].append(n)
    if set(left) != set(right):
        raise ValueError("Node identity sets differ; refusing approximate label transfer")
    mapping = {}
    for key, ids in left.items():
        if len(ids) != 1 or len(right[key]) != 1:
            raise ValueError("Ambiguous node identity; refusing an arbitrary match: " + repr(key[:2]))
        mapping[ids[0]] = right[key][0]
    actual = Counter((mapping[s], mapping[t]) for s, t in local.edges())
    expected = Counter(author.edges())
    if actual != expected:
        raise ValueError("Untyped edge endpoints/multiplicities differ from the author graph")
    return mapping

def recover_author_annotations(author):
    annotations = defaultdict(list)
    for _, data in author.nodes(data=True):
        annotations[data["source_file"]].extend(parse_records(data.get("node_info_vulnerabilities")))
    return {name: unique_records(records) for name, records in annotations.items()}

def author_replay(local, author):
    mapping = align_graphs(local, author)
    annotations = recover_author_annotations(author)
    targets = {}
    evidence = {}
    for n, ref_id in mapping.items():
        ref = author.nodes[ref_id]
        covered = endpoints(ref["node_source_code_lines"])
        records = hit_records(covered, annotations[ref["source_file"]])
        if bool(records) != bool(parse_records(ref.get("node_info_vulnerabilities"))):
            raise ValueError("Endpoint replay disagrees with saved author label: " + str(ref_id))
        targets[n] = records
        evidence[n] = {"author_node_id": ref_id, "author_preprocessed_endpoints": covered}
    return targets, evidence, annotations

def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_source_pair(local_source, dataset_source, annotated_lines):
    if not dataset_source.is_file():
        raise ValueError("Missing dataset source: " + str(dataset_source))
    local_bytes, dataset_bytes = local_source.read_bytes(), dataset_source.read_bytes()
    if local_bytes == dataset_bytes:
        return {"comparison": "byte_identical", "changed_lines": []}
    local_lines = local_bytes.decode("utf8").splitlines()
    dataset_lines = dataset_bytes.decode("utf8").splitlines()
    if len(local_lines) != len(dataset_lines):
        raise ValueError("Source line count changed: " + local_source.name)
    changed = [i + 1 for i, (a, b) in enumerate(zip(local_lines, dataset_lines)) if a != b]
    pragma = re.compile(r"^\s*pragma\s+solidity\s+[^;]+;\s*$")
    if any(not pragma.fullmatch(local_lines[i-1]) or not pragma.fullmatch(dataset_lines[i-1])
           for i in changed) or set(changed).intersection(annotated_lines):
        raise ValueError("Source content/annotated lines changed: " + local_source.name)
    return {"comparison": "pragma_only_same_line" if changed else "line_endings_only",
            "changed_lines": changed, "dataset_source_sha256": raw_hash(dataset_source)}


def verified_annotations(source_dir, filenames, smartbugs_path, solidifi_dir, category, json_load):
    """Verify source correspondence; allow only same-line unannotated pragma edits."""
    annotations = {name: [] for name in filenames}
    provenance = []
    used = {str(smartbugs_path): raw_hash(smartbugs_path)}
    all_smartbugs = json_load(smartbugs_path)
    for record in all_smartbugs:
        name = Path(record["name"]).name
        relevant = [v for v in parse_records(record["vulnerabilities"]) if v["category"] == category]
        if name not in annotations or not relevant:
            continue
        dataset_source = (smartbugs_path.parent / record["path"]).resolve()
        if smartbugs_path.parent.resolve() not in dataset_source.parents:
            raise ValueError("SmartBugs source path leaves its dataset directory")
        local_source = source_dir / name
        verified = verify_source_pair(local_source, dataset_source,
                                      {n for r in relevant for n in r["lines"]})
        annotations[name].extend(relevant)
        used[str(dataset_source)] = raw_hash(dataset_source)
        provenance.append(dict({"file": name, "dataset": "SmartBugs", "source_sha256": raw_hash(local_source)}, **verified))
    for name in sorted(filenames):
        match = re.fullmatch(r"buggy_(\d+)\.sol", name)
        if not match:
            continue
        dataset_source = solidifi_dir / name
        csv_path = solidifi_dir / ("BugLog_" + match.group(1) + ".csv")
        local_source = source_dir / name
        if not dataset_source.is_file() or raw_hash(dataset_source) != raw_hash(local_source):
            raise ValueError("SolidiFI source does not match local source: " + name)
        if not csv_path.is_file():
            raise ValueError("Missing CSV annotations: " + str(csv_path))
        with csv_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                loc, length = int(row["loc"]), int(row["length"])
                if loc < 1 or length < 1:
                    raise ValueError("Invalid injection interval in " + str(csv_path))
                annotations[name].append({"lines": list(range(loc, loc + length)), "category": category})
        used[str(csv_path)] = raw_hash(csv_path)
        used[str(dataset_source)] = raw_hash(dataset_source)
        provenance.append({"file": name, "dataset": "SolidiFI",
                           "source_sha256": raw_hash(local_source), "buglog_sha256": raw_hash(csv_path)})
    for name in annotations:
        annotations[name] = unique_records(annotations[name])
        line_count = len((source_dir / name).read_text(encoding="utf8").splitlines())
        bad = sorted({n for r in annotations[name] for n in r["lines"] if n > line_count})
        if bad:
            raise ValueError("Source annotation is out of bounds: " + name + " " + repr(bad[:10]))
    return annotations, provenance, used

def source_replay(local, annotations, source_dir, build_line_map, preprocessed_to_original):
    cache = {}
    targets = {}
    evidence = {}
    for n, data in local.nodes(data=True):
        name = data["source_file"]
        if name not in cache:
            cache[name] = build_line_map((source_dir / name).read_text(encoding="utf8"))
        lines = data.get("node_source_code_lines")
        if not isinstance(lines, list) or any(type(x) is not int for x in lines):
            raise ValueError("Local node coordinates must be an expanded preprocessed line list")
        if any(x < 1 or x > len(cache[name]) for x in lines):
            raise ValueError("Node coordinates are outside local source: " + str(n))
        original = preprocessed_to_original(lines, cache[name])
        if sorted(set(data.get("node_source_code_lines_original", []))) != original:
            raise ValueError("Saved node original-line mapping is stale: " + str(n))
        targets[n] = hit_records(original, annotations[name])
        evidence[n] = {"original_source_lines": original}
    return targets, evidence
