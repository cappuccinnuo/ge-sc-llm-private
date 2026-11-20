"""The MANDO-LLM authors' graph format, derived from their released graphs.

The released tree-sitter CFG (mando/graphs/.../CFG_solidity.py, also in the
authors' TOSEM-release branch) emits plain 'next' for almost every control-flow
edge, while the authors' published graphs distinguish next_line, first_next_line,
pos_next, neg_next and end_if. The version that produced those graphs is not
public. The names follow from *where* CFG_solidity creates the edge, so the builder
records each edge's creation site and this table renames it.

Derivation (2026-11-15): all seven Dataset A categories rebuilt with site tags and
aligned contract by contract to the authors' graphs. Nodes, node types and edge
endpoints were identical; every (site, emitted name) pair below mapped to exactly
one authors' (controlflow_type, edge_type) pair over 248,000 edges, with no exception and no inconsistent
multi-edge pair. The sites are line numbers of the pinned CFG_solidity.py, so
the table is only valid for that file (checked by SHA-256 before every build).

Node attributes are stored the way the authors' graphs store them, which is what a
DOT write/read round trip produces: strings wrapped in double quotes with '"' and
newlines escaped, line coverage as [[first, last]], synthetic end_if/end_loop
nodes carrying only their zero-based root marker, and string multi-edge keys.
"""
import re

CFG_SOLIDITY_SHA256 = "7b90d9dc7f682983d17f11bc7bcbe3ae6b0c3bcee71272cae18a346fca0eb097"

# (creation site, emitted name) -> (controlflow_type, edge_type) in the authors'
# graphs; their 'label' always equals controlflow_type and 'color' is 'red'. HGT
# reads edge_type. Loop-update and jump edges keep their own controlflow_type
# (the Java builder's names) while edge_type is next_line. 'direct' is the one edge
# list append that bypasses add_edge (CFG_solidity.py line 716, jump statements).
SITE_TABLE = {
    ("L193", "next"): ("first_next_line", "first_next_line"),  # first stmt, next block
    ("L231", "if_true"): ("pos_next", "pos_next"),             # branch taken
    ("L231", "if_false"): ("neg_next", "neg_next"),            # else branch
    ("L378", "recursive_method_call"): ("recursive_method_call", "recursive_method_call"),
    ("L397", "internal_call"): ("internal_call", "internal_call"),
    ("L399", "external_call"): ("external_call", "external_call"),
    ("L427", "next"): ("next_line", "next_line"),              # function -> first stmt
    ("L461", "next"): ("next_line", "next_line"),              # stmt -> next sibling
    ("L566", "next"): ("end_if", "end_if"),                    # last body stmt -> end_if
    ("L568", "next"): ("next_line", "next_line"),              # end_if -> following stmt
    ("L579", "next"): ("end_if", "end_if"),                    # last else stmt -> end_if
    ("L592", "next"): ("neg_next", "neg_next"),                # if without else -> end_if
    ("L613", "next"): ("neg_next", "neg_next"),                # loop -> end_loop
    ("L617", "next"): ("next_line", "next_line"),              # end_loop -> following
    ("L627", "next"): ("loop_update", "next_line"),            # body -> update
    ("L630", "next"): ("loop_update", "next_line"),            # body -> condition
    ("L650", "next"): ("loop_update", "next_line"),            # nested end_if -> update
    ("L656", "next"): ("loop_update", "next_line"),            # update -> condition
    ("L735", "jump_next"): ("jump_next", "next_line"),         # break / continue
    ("direct", "jump_next"): ("jump_next", "next_line"),
}

# Sites Dataset A never reaches, named by inference rather than by the authors' graphs
# (there are none to compare with). Dataset A output is unaffected: none of its edges
# has these keys. All are try/catch edges (Solidity >= 0.6; CFG_solidity.py's
# try_statement branch). L231/'next' (try or catch clause -> first statement of its
# block) is a plain 'next' entering a block, which the authors' format calls next_line
# (as for function -> first statement, L427). The others follow the convention the
# authors' graphs use for loop-update and jump edges: the builder's own name as
# controlflow_type, next_line as edge_type, so HGT sees ordinary control flow.
INFERRED_SITES = {
    ("L231", "next"): ("next_line", "next_line"),              # try/catch -> first stmt
    ("L897", "catch_exception"): ("catch_exception", "next_line"),   # try stmt -> catch
    ("L908", "finally_exit"): ("finally_exit", "next_line"),
    ("L917", "try_exit"): ("try_exit", "next_line"),                 # try block -> after
    ("L922", "catch_exit"): ("catch_exit", "next_line"),             # catch block -> after
    ("L925", "catch_exit"): ("catch_exit", "next_line"),             # empty catch -> after
}

SYNTHETIC = ("end_if", "end_loop")
_SUFFIX = re.compile(r"-(\d+)-(\d+)$")


class UnmappedEdge(ValueError):
    """An edge created at a site the authors' format has no verified name for."""


def author_edge_names(site, emitted):
    """(controlflow_type, edge_type) for an edge created at site with emitted name."""
    try:
        return SITE_TABLE[(site, emitted)]
    except KeyError:
        pass
    try:
        return INFERRED_SITES[(site, emitted)]
    except KeyError:
        raise UnmappedEdge(
            "no verified authors' name for a %r edge created at %s of CFG_solidity.py; "
            "the corpus uses a construct Dataset A never exercised" % (emitted, site))


def quote(value):
    """A string as the authors' graphs store it (DOT-style quoted)."""
    return '"' + value.replace('"', '\\"').replace("\n", "\\n") + '"'


def unquote(value):
    """Inverse of quote() for the characters it escapes."""
    if not (isinstance(value, str) and len(value) >= 2 and value[0] == value[-1] == '"'):
        return value
    out, i, body = [], 0, value[1:-1]
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] in 'n"':
            out.append("\n" if body[i + 1] == "n" else '"')
            i += 2
        else:
            out.append(body[i])
            i += 1
    return "".join(out)


def endpoints(label, node_type):
    """Line coverage in the authors' format, from a raw builder label.

    Ordinary nodes end their label in '<first>-<last>' (1-based, preprocessed
    lines). end_if/end_loop keep only the root marker before '_ ' (a zero-based
    root-start row in the authors' graphs, not a physical source line); the local
    narrow-span suffix is deliberately ignored.
    """
    if node_type in SYNTHETIC:
        return [[int(label.split("_ ", 1)[0])]]
    match = _SUFFIX.search(label)
    if match is None:
        raise ValueError("node label has no line range: %r" % label[-60:])
    return [[int(match.group(1)), int(match.group(2))]]


def author_label(label, node_type):
    if node_type in SYNTHETIC:
        return "%s_ %s" % (label.split("_ ", 1)[0], node_type)
    return label


def label_endpoints(lines):
    """Lines a node is labelled by under the author-endpoints policy.

    Only the first and last line of an ordinary node count, and the marker of a
    synthetic one (Test_code/label_pipeline, 2026-10-10); not the full range.
    """
    return sorted({span[0] for span in lines} | {span[-1] for span in lines})
