"""AST-only view for L2/L3; deliberately not a lexical-scope frontend.

Source: scripts/DFG/frontend.py::SourceView.__init__
Frozen source SHA256:
cfe6ee2a975abeb374e2ce17f0f7c47c400e823cfa8ca05c96d3e4657d161207

The constructor is copied verbatim except for self.mode = None.  In particular,
both parses, executable-token equality and all exact AST mappings remain.
The compatibility mode argument is accepted but not used: L1 must keep using
its existing version-aware frontend and must never use ProjectionView.
"""
import bisect
import hashlib

from scripts.DFG.frontend import FUNCTION_TYPES, SourceView, leaves, parse, walk
from scripts.DFG.models import Unsupported


class ProjectionView(SourceView):
    def __init__(self, source, file, mode=None):
        from process_graphs.tree_sitter_codeviews.utils import preprocessor
        self.source, self.file = source, file
        self.raw = source.encode("utf8")
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.tree = parse(source)
        self.mode = None  # L2/L3 projection has no lexical-scope semantics.
        self.compat_source = preprocessor.remove_comments(
            "solidity", preprocessor.remove_empty_lines(source))
        self.compat = self.compat_source.encode("utf8")
        self.compat_tree = parse(self.compat_source)
        a, b = leaves(self.tree.root_node), leaves(self.compat_tree.root_node)
        if [self.raw[n.start_byte:n.end_byte] for n in a] != [
                self.compat[n.start_byte:n.end_byte] for n in b]:
            raise Unsupported("Preprocessing changed executable tokens")
        self.raw_nodes = {(n.start_byte,n.end_byte,n.type):n
                          for n in walk(self.tree.root_node)}
        self.compat_nodes = {}
        self.compat_ids = {}
        def ids(n):
            if n.is_named:
                key = (n.start_byte,n.end_byte,n.type)
                self.compat_ids[key] = 5 + len(self.compat_ids)
                self.compat_nodes[key] = n
                for c in n.children:
                    if c.is_named: ids(c)
        ids(self.compat_tree.root_node)
        self.mapping = {}
        raw_starts = [n.start_byte for n in a]
        raw_ends = [n.end_byte for n in a]
        compat_starts = [n.start_byte for n in b]
        compat_ends = [n.end_byte for n in b]
        index = {}
        for k,n in self.compat_nodes.items():
            sig=(bisect.bisect_left(compat_starts,n.start_byte),
                 bisect.bisect_right(compat_ends,n.end_byte),n.type)
            index.setdefault(sig,[]).append(k)
        for k,n in self.raw_nodes.items():
            sig=(bisect.bisect_left(raw_starts,n.start_byte),
                 bisect.bisect_right(raw_ends,n.end_byte),n.type)
            matches=index.get(sig,[])
            if len(matches)==1:
                self.mapping[k]=matches[0]
        self.functions = [n for n in walk(self.tree.root_node)
                          if n.type in FUNCTION_TYPES and n.child_by_field_name("body")]

