"""General node-labelling rule recovered from the authors' published graphs (all 7 bug types).

Labels are produced from the public annotations (SmartBugs vulnerabilities.json,
SolidiFI BugLog csv) and the Solidity source. No author graph is read here.

Pipeline
  1. annotation lines, in ORIGINAL source coordinates
       SolidiFI : every BugLog row contributes range(loc, loc + length)
       SmartBugs: the 'lines' of the file's records
  2. convert to PREPROCESSED coordinates (tree-sitter parses the source after
     remove_empty_lines + remove_comments, so node lines index that text)
  3. node coordinates: only the two endpoints [first_line, last_line] of a node;
     end_if / end_loop carry a single value, the 0-based start row of their statement
  4. a node is vulnerable iff one of its endpoints is an annotated line; the whole
     record is attached to the node

Modes
  clean   steps 1-4 as written, SmartBugs records restricted to the bug type.
  author  what the published graphs contain: SmartBugs records are not filtered by
          category, a code line that also holds a /* */ comment is not converted, and
          for the few files listed in author_overrides.json the authors' own (damaged)
          line list is used verbatim. See README.md for what those files are.
"""
import ast
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SMARTBUGS_JSON = REPO / "data/smartbug-dataset/vulnerabilities.json"
SOLIDIFI_DIR = REPO / "data/SolidiFI-benchmark/buggy_contracts"
OVERRIDES_JSON = HERE / "author_overrides.json"
SOLIDIFI_CATEGORY = {
    "access_control": "tx.origin",
    "arithmetic": "Overflow-Underflow",
    "denial_of_service": "Unhandled-Exceptions",
    "front_running": "TOD",
    "reentrancy": "Re-entrancy",
    "time_manipulation": "Timestamp-Dependency",
    "unchecked_low_level_calls": "Unchecked-Send",
}
BUG_TYPES = tuple(SOLIDIFI_CATEGORY)
SYNTHETIC_TYPES = ("end_if", "end_loop")

# Identical to preprocessor.remove_comments' non-python branch.
_COMMENT_OR_STRING = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"', re.DOTALL | re.MULTILINE)


# ---------------------------------------------------------------- step 1: annotations
def is_solidifi(file_name):
    return re.fullmatch(r"buggy_\d+\.sol", file_name) is not None


def solidifi_lines(bug_type, file_name, solidifi_dir=SOLIDIFI_DIR):
    """Annotated original lines of a SolidiFI file; overlapping rows yield duplicates."""
    number = re.fullmatch(r"buggy_(\d+)\.sol", file_name).group(1)
    path = Path(solidifi_dir) / SOLIDIFI_CATEGORY[bug_type] / f"BugLog_{number}.csv"
    lines = []
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            loc, length = int(row["loc"]), int(row["length"])
            if loc < 1 or length < 1:
                raise ValueError(f"invalid BugLog row in {path}")
            lines.extend(range(loc, loc + length))
    return lines


_SMARTBUGS_CACHE = {}


def smartbugs_records(file_name, smartbugs_json=SMARTBUGS_JSON):
    key = str(smartbugs_json)
    if key not in _SMARTBUGS_CACHE:
        with open(smartbugs_json) as handle:
            _SMARTBUGS_CACHE[key] = json.load(handle)
    return [v for record in _SMARTBUGS_CACHE[key] if Path(record["name"]).name == file_name
            for v in record["vulnerabilities"]]


def public_annotation(bug_type, file_name, category_filter, smartbugs_json=SMARTBUGS_JSON):
    """[{'lines': [...original...], 'category': str}] for one buggy file."""
    if is_solidifi(file_name):
        return [{"lines": solidifi_lines(bug_type, file_name), "category": bug_type}]
    records = smartbugs_records(file_name, smartbugs_json)
    if category_filter:
        records = [r for r in records if r["category"] == bug_type]
    return [{"lines": list(r["lines"]), "category": r["category"]} for r in records]


# ---------------------------------------------------------------- step 2: coordinates
def build_line_map(source):
    """entry p-1 = sorted original line numbers that ended up on preprocessed line p."""
    original_lines = source.split("\n")
    kept = [(i + 1, line) for i, line in enumerate(original_lines) if line.strip() != ""]
    if not kept:
        return []
    text1 = "\n".join(line for _, line in kept)
    char_origin = []
    for idx, (origin, line) in enumerate(kept):
        char_origin.extend([origin] * len(line))
        if idx != len(kept) - 1:
            char_origin.append(origin)
    out_parts, out_origin, pos = [], [], 0
    for match in _COMMENT_OR_STRING.finditer(text1):
        out_parts.append(text1[pos:match.start()])
        out_origin.extend(char_origin[pos:match.start()])
        matched = match.group(0)
        if matched.startswith("/"):
            out_parts.append(" ")
            out_origin.append(char_origin[match.start()])
        else:
            out_parts.append(matched)
            out_origin.extend(char_origin[match.start():match.end()])
        pos = match.end()
    out_parts.append(text1[pos:])
    out_origin.extend(char_origin[pos:])
    text2 = "".join(out_parts)
    mapping, start = [], 0
    for line in text2.split("\n"):
        end = start + len(line)
        if line.strip() != "":
            mapping.append(sorted(set(out_origin[start:end])))
        start = end + 1
    return mapping


def original_to_preprocessed(source):
    forward = {}
    for pre, origins in enumerate(build_line_map(source), 1):
        for origin in origins:
            forward.setdefault(origin, []).append(pre)
    return forward


def has_block_comment(line):
    """True when a /* */ comment starts or ends on this original line."""
    return any(m.group(0).startswith("/*") for m in _COMMENT_OR_STRING.finditer(line)) or "*/" in line


def convert_lines(original_lines, source, drop_block_comment_lines=False):
    """Original annotation lines -> sorted, de-duplicated preprocessed lines."""
    forward = original_to_preprocessed(source)
    text = source.split("\n")
    out = set()
    for n in set(original_lines):
        if drop_block_comment_lines and 1 <= n <= len(text) and has_block_comment(text[n - 1]):
            continue
        out.update(forward.get(n, ()))
    return sorted(out)


# ---------------------------------------------------------------- step 3: node coordinates
_LABEL_TAIL = re.compile(r"(\d+)-([a-z_]+)-(\d+)-(\d+)$")
_LABEL_ROW = re.compile(r"^(\d+)_ ")


def unquote(text):
    if isinstance(text, str) and len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        try:
            return ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return text[1:-1]
    return text


def node_endpoints(label, node_type):
    """Endpoints of a node in preprocessed coordinates, from the generator's label string.

    Every label starts with '<row>_ ' where row is the 0-based start row of the statement.
    Ordinary nodes end in '<id>-<type>-<first>-<last>' (1-based lines) -> [first, last].
    end_if / end_loop -> [row]: the published graphs keep that single 0-based value, and
    this holds whether or not the local generator appended a line tail to the label.
    """
    label = unquote(label) or ""
    if node_type in SYNTHETIC_TYPES:
        match = _LABEL_ROW.match(label)
        return [int(match.group(1))] if match else None
    match = _LABEL_TAIL.search(label)
    return [int(match.group(3)), int(match.group(4))] if match else None


# ---------------------------------------------------------------- step 4: labels
def label_nodes(endpoints_by_node, records):
    """{node: [first, last]} + preprocessed-coordinate records -> {node: [records hit] or None}."""
    out = {}
    for node, ends in endpoints_by_node.items():
        hits = [r for r in records if set(ends or ()).intersection(r["lines"])]
        out[node] = hits or None
    return out


_OVERRIDES_CACHE = {}


def load_overrides(path=OVERRIDES_JSON):
    key = str(path)
    if key not in _OVERRIDES_CACHE:
        _OVERRIDES_CACHE[key] = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    return _OVERRIDES_CACHE[key]


def annotate_file(bug_type, file_name, source, mode="clean", use_overrides=True,
                  smartbugs_json=SMARTBUGS_JSON, overrides_json=OVERRIDES_JSON):
    """Annotation of one buggy file in preprocessed coordinates (records without lines dropped)."""
    if mode not in ("clean", "author"):
        raise ValueError("mode must be 'clean' or 'author'")
    if mode == "author" and use_overrides:
        entry = load_overrides(overrides_json).get(bug_type, {}).get(file_name)
        if entry is not None:
            return [{"lines": list(r["lines"]), "category": r["category"]} for r in entry["records"]]
    records = public_annotation(bug_type, file_name, category_filter=(mode == "clean"),
                                smartbugs_json=smartbugs_json)
    converted = []
    for record in records:
        lines = convert_lines(record["lines"], source, drop_block_comment_lines=(mode == "author"))
        if lines:
            converted.append({"lines": lines, "category": record["category"]})
    return converted
