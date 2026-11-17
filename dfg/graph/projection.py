"""Projection of source-level facts onto HCG nodes.

An HCG node is matched to its AST statement by code, label endpoints and role;
ambiguous or non-identical matches are refused rather than guessed.
"""
import ast
import bisect
import hashlib
import re


from hcg.cfg.author_schema import quote
from dfg.analysis.frontend import FUNCTION_TYPES, SourceView, leaves, parse, walk
from dfg.analysis.ir import Unsupported


# ----------------------------------------------------------------------
# projection
# Exact existing-node projection; labels/features are never consulted.
ANCHOR = re.compile(r"(\d+)-([a-z_]+)-(\d+)-(\d+)$")

NODE_TYPES = {"if_statement":"if","while_statement":"while",
              "for_statement":"for","return_statement":"return",
              "variable_declaration_statement":"new_variable",
              "variable_declaration":"new_variable"}

def decoded(value):
    if not isinstance(value,str): return value
    if value.startswith('"') and value.endswith('"'):
        try:
            candidate=ast.literal_eval(value)
            if isinstance(candidate,str): return candidate
        except (SyntaxError,ValueError): pass
    return value

def code_equal(value, expected):
    """Compare raw source or its exact production DOT representation.

    DOT quoting is not Python/JSON string escaping. In particular hcg's quote keeps
    existing Solidity backslashes: literal_eval would turn source hex/Unicode/tab
    escapes into different bytes. Do not decode arbitrary alternate spellings.
    This predicate alone is not a source-identity proof; Projector also checks
    AST identity/role/endpoints and rejects ambiguous multiline string literals.
    """
    return value == expected or (isinstance(expected, str) and
                                 value == quote(expected))

def has_multiline_string(node, source):
    """Detect the known non-injective DOT quoting case using existing AST spans.

    A physical newline inside a string (including a line continuation) and a
    literal backslash-n can have identical DOT bytes. Serialized nodes that
    contain such literals cannot establish exact source correspondence. This
    check does not reject ordinary multiline statements/functions outside string
    literals, and does not change support for exact raw source attributes.
    """
    string_types = {"string_literal", "string", "hex_string_literal",
                    "hex_string", "unicode_string_literal"}
    pending = [node]
    while pending:
        current = pending.pop()
        if current.type in string_types:
            literal = source[current.start_byte:current.end_byte]
            if b"\n" in literal or b"\r" in literal:
                return True
        pending.extend(current.named_children)
    return False

class Projector:
    def __init__(self, graph, view):
        self.graph,self.view=graph,view
        self.by_ast={}
        compat_by_id={i:k for k,i in view.compat_ids.items()}
        self.stats={"ordinary_nodes_checked":0,"synthetic_nodes":0}
        for identifier,data in graph.nodes(data=True):
            if data.get("source_file")!=view.file: continue
            label=decoded(data.get("label",""))
            m=ANCHOR.search(label)
            if not m:
                if data.get("node_type") in ("end_if","end_loop"):
                    self.stats["synthetic_nodes"]+=1
                    continue
                raise Unsupported("Node lacks an auditable AST anchor: "+str(identifier))
            ast_id=int(m.group(1))
            if ast_id not in compat_by_id:
                raise Unsupported("Stale AST ID: "+str(ast_id))
            key=compat_by_id[ast_id]
            n=view.compat_nodes[key]
            if data.get("node_type")!=m.group(2):
                raise Unsupported("Node type differs from saved AST label")
            expected_type=NODE_TYPES.get(n.type)
            if expected_type and expected_type!=data.get("node_type"):
                raise Unsupported("AST/HCG node role differs")
            if (int(m.group(3)),int(m.group(4))) != (n.start_point[0]+1,n.end_point[0]+1):
                raise Unsupported("AST endpoint coordinates differ")
            expected=view.compat[n.start_byte:n.end_byte].decode("utf8")
            if not code_equal(data.get("code"),expected):
                raise Unsupported("AST/HCG source text differs: "+str(identifier))
            if data.get("code") != expected and has_multiline_string(n,view.compat):
                raise Unsupported("Ambiguous DOT serialization of multiline string: "+str(identifier))
            if ast_id in self.by_ast:
                raise Unsupported("Ambiguous HCG nodes for one AST anchor")
            self.by_ast[ast_id]=identifier
            self.stats["ordinary_nodes_checked"]+=1
        if not self.by_ast:
            raise Unsupported("No source nodes could be verified")

    def map_facts(self, facts):
        mapping={}
        diagnostics=[]
        anchors={a for f in facts for a in (f.definition.anchor,f.use.anchor)}
        for anchor in sorted(anchors):
            try:
                k=self.view.compat_key(anchor)
                identifier=self.by_ast.get(self.view.compat_ids[k])
                if identifier is None:
                    raise Unsupported("Semantic anchor has no existing HCG node")
                mapping[anchor]=identifier
            except Unsupported as exc:
                diagnostics.append({"kind":"projection_missing","file":anchor.file,
                                    "start":anchor.start,"end":anchor.end,
                                    "role":anchor.role,"reason":str(exc)})
        return mapping,diagnostics


# ----------------------------------------------------------------------
# dfg_v2/projection_view
# AST-only view for L2/L3; deliberately not a lexical-scope frontend.
#
# Source: scripts/DFG/frontend.py::SourceView.__init__
# Frozen source SHA256:
# cfe6ee2a975abeb374e2ce17f0f7c47c400e823cfa8ca05c96d3e4657d161207
#
# The constructor is copied verbatim except for self.mode = None.  In particular,
# both parses, executable-token equality and all exact AST mappings remain.
# The compatibility mode argument is accepted but not used: L1 must keep using
# its existing version-aware frontend and must never use ProjectionView.
class ProjectionView(SourceView):
    def __init__(self, source, file, mode=None):
        from mando.graphs.tree_sitter_codeviews.utils import preprocessor
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
