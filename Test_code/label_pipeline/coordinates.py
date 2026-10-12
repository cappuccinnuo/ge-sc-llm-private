"""Explicit source and author-compatible coordinates, isolated from legacy code.

Codex, 2026-10-10. Author-compatible synthetic markers are legacy zero-based
root-start numbers; they must not be presented as physical previous-source lines.
"""
import ast
import re

_COMMENT_OR_STRING = re.compile(
    r"""//.*?$|/\*.*?\*/|'(?:\\.|[^\\'])*'|"(?:\\.|[^\\"])*" """.rstrip(),
    re.DOTALL | re.MULTILINE,
)
_NORMAL_SUFFIX = re.compile(r"(\d+)-([a-z_]+)-(\d+)-(\d+)$")
_SYNTHETIC_LABEL = re.compile(r"^(\d+)_ (end_if|end_loop)(?:-(\d+)-(\d+))?$")


def _literal(value):
    for _ in range(3):
        if not isinstance(value, str):
            break
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            break
        if parsed == value:
            break
        value = parsed
    return value


def _positive_integer(value):
    return type(value) is int and value >= 1


def graph_endpoints(data):
    """Recover legacy author endpoints from this node's label, without targets.

    Ordinary labels carry one-based AST start/end rows. Synthetic labels retain
    a zero-based root-start marker in their prefix; their optional local suffix
    denotes another policy and is deliberately not used as the returned marker.
    Missing, malformed, or contradictory labels raise instead of guessing.
    """
    if not isinstance(data, dict):
        raise TypeError("Node attributes must be a dictionary")
    label = _literal(data.get("label"))
    node_type = data.get("node_type")
    if not isinstance(label, str) or not isinstance(node_type, str):
        raise ValueError("Node requires string label and node_type")
    if node_type in ("end_if", "end_loop"):
        match = _SYNTHETIC_LABEL.fullmatch(label)
        if match is None or match.group(2) != node_type:
            raise ValueError("Synthetic node lacks its explicit root-start marker")
        if match.group(3) is not None:
            first, last = int(match.group(3)), int(match.group(4))
            if first < 1 or last < first:
                raise ValueError("Invalid local synthetic label suffix")
        return [int(match.group(1))]
    match = _NORMAL_SUFFIX.search(label)
    if match is None or match.group(2) != node_type:
        raise ValueError("Ordinary node lacks matching AST type/start/end suffix")
    first, last = int(match.group(3)), int(match.group(4))
    if first < 1 or last < first:
        raise ValueError("Ordinary node endpoint range must be positive and ordered")
    return sorted({first, last})


def coordinates_for_node(data, policy):
    """Return coordinates in an explicitly selected preprocessed-line policy.

    author-endpoints: label-derived endpoint/legacy-marker compatibility.
    source-range: preserve existing flat line membership, expand nested spans.
    This function never changes coordinate bases or reads vulnerability labels.
    """
    if policy == "author-endpoints":
        return graph_endpoints(data)
    if policy != "source-range":
        raise ValueError("Unknown coordinate policy: " + str(policy))
    value = _literal(data.get("node_source_code_lines"))
    if not isinstance(value, list) or not value:
        raise ValueError("source-range requires nonempty saved node coordinates")
    if all(_positive_integer(n) for n in value):
        return list(value)
    if any(not isinstance(span, (list, tuple)) or len(span) not in (1, 2)
           or any(not _positive_integer(n) for n in span) for span in value):
        raise ValueError("Coordinates must be positive flat lines or nested spans")
    result = set()
    for span in value:
        if len(span) == 2 and span[1] < span[0]:
            raise ValueError("Nested coordinate range is reversed")
        result.update(range(span[0], span[-1] + 1))
    return sorted(result)


def preprocess_with_map(source):
    """Return exact legacy Solidity preprocessing text and code-line provenance.

    Text reproduces remove_empty_lines followed by remove_comments, including
    comment replacement by one space and removal of newly blank lines.
    Each mapping row contains original one-based lines contributing surviving
    non-whitespace code/string characters. Removed comments, their replacement
    spaces, and indentation do not contribute provenance.
    """
    if not isinstance(source, str):
        raise TypeError("Source must be decoded UTF-8 text")
    source.encode("utf8", errors="strict")
    kept = [(number, line) for number, line in enumerate(source.split("\n"), 1)
            if line.strip() != ""]
    text = "\n".join(line for _, line in kept)
    origins = []
    for position, (number, line) in enumerate(kept):
        origins.extend(number if not char.isspace() else None for char in line)
        if position + 1 < len(kept):
            origins.append(None)
    assert len(origins) == len(text)
    parts, mapped, cursor = [], [], 0
    for match in _COMMENT_OR_STRING.finditer(text):
        parts.append(text[cursor:match.start()])
        mapped.extend(origins[cursor:match.start()])
        token = match.group(0)
        if token.startswith("/"):
            parts.append(" ")
            mapped.append(None)
        else:
            parts.append(token)
            mapped.extend(origins[match.start():match.end()])
        cursor = match.end()
    parts.append(text[cursor:])
    mapped.extend(origins[cursor:])
    intermediate = "".join(parts)
    assert len(mapped) == len(intermediate)
    output, line_map, cursor = [], [], 0
    for line in intermediate.split("\n"):
        stop = cursor + len(line)
        if line.strip() != "":
            output.append(line)
            line_map.append(sorted({n for n in mapped[cursor:stop] if n is not None}))
        cursor = stop + 1
    return "\n".join(output), line_map
