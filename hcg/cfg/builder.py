"""Contract graphs (CFG + call graph) in the authors' format, from Solidity files.

Runs the repository's tree-sitter builder (process_graphs, unchanged; DFG v2,
NodeSem and EdgeSem import it too) with two temporary instrumentation hooks that
record where each edge is created, then converts every contract graph to the
authors' format and merges a corpus with disjoint_union in file-name order.
"""
import contextlib
import hashlib
import inspect
import io
import os
import platform
import sys
from pathlib import Path

import networkx as nx

from hcg.cfg import author_schema as schema

REPO = Path(__file__).resolve().parents[2]
_CFG_DIR = REPO / "process_graphs/tree_sitter_codeviews/codeviews/CFG"


def grammar_dir():
    """Per-platform tree-sitter grammar build (git-ignored).

    The my-languages.so checked in under process_graphs/.../build/ is a macOS arm64
    binary; custom_parser compiles the vendored grammar into this directory on first
    use (needs a C compiler). The old machine used the same <repo>/build/<platform>.
    """
    return REPO / "build" / ("%s-%s" % (sys.platform, platform.machine().lower()))


def _check_builder():
    actual = hashlib.sha256((_CFG_DIR / "CFG_solidity.py").read_bytes()).hexdigest()
    if actual != schema.CFG_SOLIDITY_SHA256:
        raise RuntimeError("CFG_solidity.py changed (sha256 %s); the creation-site table in "
                           "hcg/cfg/author_schema.py must be re-derived" % actual)


@contextlib.contextmanager
def _site_tagging():
    """Record each edge's creation line; restore the original methods afterwards."""
    from process_graphs.tree_sitter_codeviews.codeviews.CFG import CFG, CFG_solidity

    solidity_cls, base_cls = CFG_solidity.CFGGraph_solidity, CFG.CFGGraph
    original_add, original_export = solidity_cls.add_edge, base_cls.to_networkx

    def add_edge(self, src, dst, edge_type):
        if src is None or dst is None:
            return  # the original only prints a warning here
        site = "L%d" % inspect.currentframe().f_back.f_lineno
        self.CFG_edge_list.append((src, dst, edge_type, site))

    def to_networkx(self, nodes, edges):
        graph = nx.MultiDiGraph()
        for node in nodes:
            graph.add_node(node[0], label=str(node[1]) + "_ " + node[2], type_label=node[3],
                           node_type=node[3], method=node[4], code=node[5])
        for edge in edges:
            graph.add_edge(edge[0], edge[1], edge_type=edge[2],
                           site=edge[3] if len(edge) > 3 else "direct")
        return graph

    solidity_cls.add_edge, base_cls.to_networkx = add_edge, to_networkx
    try:
        yield
    finally:
        solidity_cls.add_edge, base_cls.to_networkx = original_add, original_export


def build_contract(path):
    """One contract's graph in the authors' format (node ids local to the file)."""
    os.environ.setdefault("TREE_SITTER_LIB_DIR", str(grammar_dir()))
    from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_file

    with _site_tagging(), contextlib.redirect_stdout(io.StringIO()):
        raw = generate_cfg_from_file(path)
    return to_author_format(raw, Path(path).name)


def to_author_format(raw, source_file):
    graph = nx.MultiDiGraph()
    for node, data in raw.nodes(data=True):
        node_type, label = data["node_type"], data["label"]
        graph.add_node(
            node,
            code=schema.quote(data.get("code") or ""),
            label=schema.quote(schema.author_label(label, node_type)),
            method=schema.quote(data.get("method") or ""),
            type_label=data["type_label"],
            node_source_code_lines=schema.endpoints(label, node_type),
            node_type=node_type,
            source_file=source_file,
        )
    for src, dst, data in raw.edges(data=True):
        flow, edge_type = schema.author_edge_names(data["site"], data["edge_type"])
        graph.add_edge(src, dst, color="red", controlflow_type=flow, edge_type=edge_type,
                       label=flow)
    return graph


def build_corpus(paths, log=None):
    """Merged corpus graph and [(file, error)] for files that failed to parse.

    Files are merged in sorted name order; node ids run 0..N-1 across the corpus and
    parallel edges get string keys, as in the authors' graphs.
    """
    _check_builder()
    merged, failures = None, []
    for path in sorted(paths, key=lambda p: Path(p).name):
        try:
            graph = build_contract(path)
        except schema.UnmappedEdge:
            raise
        except Exception as exc:  # noqa: BLE001 - report every parse failure
            failures.append((Path(path).name, repr(exc)))
            continue
        merged = graph if merged is None else nx.disjoint_union(merged, graph)
        if log:
            log(Path(path).name)
    if merged is None:
        raise ValueError("no contract could be parsed")
    return _string_edge_keys(merged), failures


def _string_edge_keys(graph):
    out = nx.MultiDiGraph(name="G")
    out.add_nodes_from(graph.nodes(data=True))
    for src, dst, key, data in graph.edges(keys=True, data=True):
        out.add_edge(src, dst, key=str(key), **data)
    return out
