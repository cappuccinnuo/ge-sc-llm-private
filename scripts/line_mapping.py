"""Map tree-sitter CFG line numbers back to original source line numbers.

process_graphs/tree_sitter_codeviews/tree_parser/parser_driver.py preprocesses every
source before parsing:

    src_code = preprocessor.remove_empty_lines(src_code)
    src_code = preprocessor.remove_comments(src_language, src_code)

so every `node_source_code_lines` value produced by the generator indexes the
*preprocessed* text, not the file on disk. Vulnerability annotations (SmartBugs,
SolidiFI) reference original file lines, so they can only be intersected after
translating one side.

A naive constant offset is wrong: `remove_comments` replaces each comment with a
single space, and a `/* ... */` spanning several lines therefore *merges* the code
before and after it onto one line. This module tracks character provenance through
both passes so the mapping stays exact in that case too.
"""
import re

# Identical to preprocessor.remove_comments' non-python branch.
PATTERN = re.compile(
    r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
    re.DOTALL | re.MULTILINE,
)


def build_line_map(source):
    """Return a list where entry p-1 holds the original line numbers of
    preprocessed line p (1-based on both sides)."""
    original_lines = source.split("\n")

    # Pass 1: remove_empty_lines, remembering where each surviving line came from.
    kept = [(i + 1, line) for i, line in enumerate(original_lines) if line.strip() != ""]
    if not kept:
        return []
    text1 = "\n".join(line for _, line in kept)

    # Per-character origin for text1.
    char_origin = []
    for idx, (origin, line) in enumerate(kept):
        char_origin.extend([origin] * len(line))
        if idx != len(kept) - 1:
            char_origin.append(origin)  # the joining newline
    assert len(char_origin) == len(text1), "origin tracking desynced in pass 1"

    # Pass 2: remove_comments, carrying origins across the substitution.
    out_parts = []
    out_origin = []
    pos = 0
    for match in PATTERN.finditer(text1):
        out_parts.append(text1[pos:match.start()])
        out_origin.extend(char_origin[pos:match.start()])
        matched = match.group(0)
        if matched.startswith("/"):
            # Comment -> single space, inheriting the line it started on.
            out_parts.append(" ")
            out_origin.append(char_origin[match.start()])
        else:
            # String literal -> kept verbatim.
            out_parts.append(matched)
            out_origin.extend(char_origin[match.start():match.end()])
        pos = match.end()
    out_parts.append(text1[pos:])
    out_origin.extend(char_origin[pos:])

    text2 = "".join(out_parts)
    assert len(text2) == len(out_origin), "origin tracking desynced in pass 2"

    # Drop lines that became blank, exactly as the preprocessor does.
    mapping = []
    start = 0
    for line in text2.split("\n"):
        end = start + len(line)
        if line.strip() != "":
            mapping.append(sorted(set(out_origin[start:end])))
        start = end + 1
    return mapping


def preprocessed_to_original(preprocessed_lines, line_map):
    """Translate a node's preprocessed line list into original file line numbers."""
    out = set()
    for p in preprocessed_lines or []:
        if 1 <= p <= len(line_map):
            out.update(line_map[p - 1])
    return sorted(out)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    path = Path(sys.argv[1])
    src = path.read_text(encoding="utf8", errors="ignore")
    line_map = build_line_map(src)
    original = src.split("\n")
    print(f"{path.name}: {len(original)} original lines -> {len(line_map)} preprocessed lines")
    for p, origins in enumerate(line_map, start=1):
        text = original[origins[0] - 1].strip() if origins else ""
        print(f"  pre {p:4d} <- orig {origins}   {text[:70]}")
