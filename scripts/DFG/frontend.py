"""Read-only raw/compatibility AST views; reject changed executable tokens."""
import bisect
import hashlib
import os
import re
from pathlib import Path
from tree_sitter import Language, Parser
from .models import Span, Unsupported

FUNCTION_TYPES = {"function_definition", "constructor_definition",
                  "fallback_receive_definition"}

def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)

def text(source, node):
    return source.encode("utf8")[node.start_byte:node.end_byte].decode("utf8")

def span(file, node):
    return Span(file, node.start_byte, node.end_byte, node.type)

def library_path():
    root = Path(__file__).resolve().parents[2]
    path = (Path(os.environ["TREE_SITTER_LIB_DIR"]) / "my-languages.so"
            if os.environ.get("TREE_SITTER_LIB_DIR")
            else root / "build/linux-x86_64/my-languages.so")
    if not path.is_file():
        raise Unsupported("Missing existing tree-sitter library: " + str(path))
    return path.resolve()

def parse(source):
    parser = Parser()
    parser.set_language(Language(str(library_path()), "solidity"))
    tree = parser.parse(source.encode("utf8"))
    if tree.root_node.has_error or any(n.is_missing for n in walk(tree.root_node)):
        raise Unsupported("Solidity parser ERROR/MISSING")
    return tree

def scope_mode(source, root, override=None):
    pragmas = [text(source, n) for n in root.named_children
               if n.type == "pragma_directive"]
    sol = [p for p in pragmas if re.match(r"pragma\s+solidity\b", p)]
    if len(sol) > 1:
        raise Unsupported("Multiple Solidity pragmas require version intersection verification")
    modes = []
    for p in sol:
        expr = re.sub(r"^pragma\s+solidity\s*|;\s*$", "", p).strip()
        if "||" in expr:
            raise Unsupported("Disjunctive pragma needs an explicit compiler version")
        versions = list(re.finditer(r"(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)", expr))
        if not versions or re.sub(r"(\^|~|>=|<=|>|<|=)?\s*\d+\.\d+\.\d+", "", expr).strip():
            raise Unsupported("Unsupported pragma constraint: " + expr)
        lo, hi = (0, 0, 0), (999, 0, 0)
        for m in versions:
            op = m.group(1) or "="
            v = tuple(int(m.group(i)) for i in (2, 3, 4))
            if op in ("=", "^", "~"):
                lo = max(lo, v)
                upper = ((v[0], v[1], v[2]+1) if op == "="
                         else (v[0], v[1]+1, 0))
                hi = min(hi, upper)
            elif op in (">", ">="):
                lo = max(lo, (v[0], v[1], v[2]+1) if op == ">" else v)
            else:
                hi = min(hi, (v[0], v[1], v[2]+1) if op == "<=" else v)
        if lo >= hi: raise Unsupported("Empty pragma constraint")
        if lo >= (0,4,0) and hi <= (0,5,0): modes.append("legacy")
        elif lo >= (0,5,0) and lo < (0,9,0): modes.append("modern")
        else: raise Unsupported("Pragma crosses scope-semantics boundary")
    if any(re.search(r'experimental\s+["\x27]v0\.5\.0["\x27]', p) for p in pragmas):
        modes = ["modern"] if modes else []
    if len(set(modes)) > 1: raise Unsupported("Conflicting scope modes")
    if override not in (None, "legacy", "modern"): raise ValueError("Invalid mode")
    if modes:
        if override and override != modes[0]: raise Unsupported("Override contradicts pragma")
        return modes[0]
    if override: return override
    raise Unsupported("Missing supported pragma; supply recorded scope mode")

def leaves(root):
    out = []
    def visit(n):
        if "comment" in n.type: return
        if n.type in {"string_literal", "string", "hex_string_literal", "hex_string", "unicode_string_literal"} or not n.children:
            if n.end_byte > n.start_byte: out.append(n)
        else:
            for c in n.children: visit(c)
    visit(root)
    return out

class SourceView:
    def __init__(self, source, file, mode=None):
        from process_graphs.tree_sitter_codeviews.utils import preprocessor
        self.source, self.file = source, file
        self.raw = source.encode("utf8")
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.tree = parse(source)
        self.mode = scope_mode(source, self.tree.root_node, mode)
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

    def compat_key(self, anchor):
        if anchor.file != self.file: raise Unsupported("Cross-file anchor")
        key = (anchor.start,anchor.end,anchor.role)
        if key not in self.mapping: raise Unsupported("Ambiguous raw/compat span")
        return self.mapping[key]

def parse_source(source, file="example.sol", mode=None):
    return SourceView(source, file, mode)
