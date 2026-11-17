"""Tree-sitter source views of a Solidity file.

Read-only parsing of the raw source and its comment-stripped view, plus the
compiler-version interval used to decide which constructs are supported
(the version recorded by the dataset, or the file's pragma).
"""
import bisect
import copy
import csv
import hashlib
import os
import re
from pathlib import Path

from tree_sitter import Language, Parser

from dfg.analysis.ir import Span, Unsupported
from dfg.schema import SUPPORTED_PROFILE_VERSION as VERSION


# ----------------------------------------------------------------------
# frontend
# Read-only raw/compatibility AST views; reject changed executable tokens.
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

def solidity_version_interval(source, root):
    pragmas = [text(source, n) for n in root.named_children
               if n.type == "pragma_directive"]
    sol = [p for p in pragmas if re.match(r"pragma\s+solidity\b", p)]
    if len(sol) > 1:
        raise Unsupported("Multiple Solidity pragmas require version intersection verification")
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
        return lo, hi
    return None

def scope_mode(source, root, override=None):
    pragmas = [text(source, n) for n in root.named_children
               if n.type == "pragma_directive"]
    interval = solidity_version_interval(source, root)
    modes = []
    if interval is not None:
        lo, hi = interval
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
        from mando.graphs.tree_sitter_codeviews.utils import preprocessor
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


# ----------------------------------------------------------------------
# state/stage_f/versioning
# Conjunctive pragma evidence, never an arbitrary compiler selection.
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def interval(source,root):
 expressions=[re.sub(r"^pragma\s+solidity\s*|;\s*$","",text(source,n)).strip()
              for n in root.named_children if n.type=="pragma_directive" and re.match(r"pragma\s+solidity\b",text(source,n))]
 if not expressions:return None
 lo,hi=(0,0,0),(999,0,0)
 pattern=r"(\^|~|>=|<=|>|<|=)?\s*(\d+)\.(\d+)\.(\d+)"
 for expr in expressions:
  if "||" in expr or not re.search(pattern,expr) or re.sub(pattern,"",expr).strip():raise Unsupported("F: unsupported pragma expression")
  for m in re.finditer(pattern,expr):
   op=m.group(1) or "=";v=tuple(int(m.group(i)) for i in (2,3,4));patch=(v[0],v[1],v[2]+1)
   if op in ("=","^","~"):
    upper=patch if op=="=" else (v[0],v[1]+1,0) if op=="~" else (v[0]+1,0,0) if v[0] else (0,v[1]+1,0) if v[1] else patch
    lo=max(lo,v);hi=min(hi,upper)
   elif op in (">",">="):lo=max(lo,patch if op==">" else v)
   else:hi=min(hi,patch if op=="<=" else v)
 if lo>=hi:raise Unsupported("F: empty pragma intersection")
 return lo,hi

def recorded_version(source,metadata):
 if metadata is None:return None
 # Metadata is data, never executable code. Validate its row and both byte hashes here.
 source_sha=hashlib.sha256(source.encode("utf8")).hexdigest()
 csv_path=Path(metadata["csv_path"]);origin=Path(metadata["source_path"])
 if source_sha!=metadata["source_sha256"] or sha(origin)!=source_sha or sha(csv_path)!=metadata["csv_sha256"]:
  raise Unsupported("F: version metadata/source hash mismatch")
 rows=list(csv.DictReader(csv_path.open()))
 matched=[r for r in rows if r["file"]==metadata["row_file"]]
 if len(matched)!=1 or matched[0]["compiled version"]!=metadata["version"]:
  raise Unsupported("F: ambiguous version metadata row")
 if (csv_path.parent/metadata["row_file"]).resolve()!=origin.resolve():raise Unsupported("F: metadata source path mismatch")
 if not re.fullmatch(r"\d+\.\d+\.\d+",metadata["version"]):raise Unsupported("F: unsupported recorded compiler version")
 return tuple(map(int,metadata["version"].split(".")))

def mode_for(source,root,iv):
 if iv is None:raise Unsupported("F: no version evidence for lexical scope")
 lo,hi=iv
 if (0,4,0)<=lo and hi<=(0,5,0):mode="legacy"
 elif (0,5,0)<=lo<(0,9,0):mode="modern"
 else:raise Unsupported("F: interval crosses lexical scope boundary")
 if any(re.search(r'experimental\s+["\x27]v0\.5\.0["\x27]',text(source,n)) for n in root.named_children if n.type=="pragma_directive"):mode="modern"
 return mode

def effective_interval(source,root,metadata=None):
 raw=interval(source,root);v=recorded_version(source,metadata)
 if v:
  if raw and not raw[0]<=v<raw[1]:raise Unsupported("F: recorded compiler contradicts pragma")
  return (v,(v[0],v[1],v[2]+1)),{"kind":"dataset_recorded_compiled_version","metadata":metadata,"independently_compiled":False,"pragma_interval":raw}
 return raw,{"kind":"source_pragma_intersection","pragma_interval":raw,"exact_compiler":None,"independently_compiled":False}

def available(view,name):
 lohi=view.version_interval
 windows={"require":((0,4,10),(0,9,0)),"assert":((0,4,10),(0,9,0)),"revert":((0,4,10),(0,9,0)),
 "selfdestruct":((0,4,0),(0,9,0)),"suicide":((0,4,0),(0,5,0)),
 "call":((0,4,0),(0,9,0)),"send":((0,4,0),(0,9,0)),"transfer":((0,4,10),(0,9,0)),"staticcall":((0,5,0),(0,9,0))}
 return bool(lohi and name in windows and windows[name][0]<=lohi[0] and lohi[1]<=windows[name][1])


# ----------------------------------------------------------------------
# state/stage_f/frontend
# Stage F source view, same exact raw/compat token and AST mapping as v1.1.
class StageFSourceView(SourceView):
 def __init__(self,source,file,metadata=None):
  from mando.graphs.tree_sitter_codeviews.utils import preprocessor
  self.source,self.file=source,file;self.raw=source.encode("utf8");self.sha256=hashlib.sha256(self.raw).hexdigest()
  self.tree=parse(source);self.version_interval,self.version_evidence=effective_interval(source,self.tree.root_node,metadata)
  self.mode=mode_for(source,self.tree.root_node,self.version_interval)
  self.compat_source=preprocessor.remove_comments("solidity",preprocessor.remove_empty_lines(source))
  self.compat=self.compat_source.encode("utf8");self.compat_tree=parse(self.compat_source)
  a,b=leaves(self.tree.root_node),leaves(self.compat_tree.root_node)
  if [self.raw[n.start_byte:n.end_byte] for n in a]!=[self.compat[n.start_byte:n.end_byte] for n in b]:raise Unsupported("Preprocessing changed executable tokens")
  self.raw_nodes={(n.start_byte,n.end_byte,n.type):n for n in walk(self.tree.root_node)}
  self.compat_nodes={};self.compat_ids={}
  def ids(n):
   if n.is_named:
    k=(n.start_byte,n.end_byte,n.type);self.compat_ids[k]=5+len(self.compat_ids);self.compat_nodes[k]=n
    for c in n.children:
     if c.is_named:ids(c)
  ids(self.compat_tree.root_node);self.mapping={}
  aa=[n.start_byte for n in a];az=[n.end_byte for n in a];ba=[n.start_byte for n in b];bz=[n.end_byte for n in b];index={}
  for k,n in self.compat_nodes.items():index.setdefault((bisect.bisect_left(ba,n.start_byte),bisect.bisect_right(bz,n.end_byte),n.type),[]).append(k)
  for k,n in self.raw_nodes.items():
   matches=index.get((bisect.bisect_left(aa,n.start_byte),bisect.bisect_right(az,n.end_byte),n.type),[])
   if len(matches)==1:self.mapping[k]=matches[0]
  self.functions=[n for n in walk(self.tree.root_node) if n.type in FUNCTION_TYPES and n.child_by_field_name("body")]


# ----------------------------------------------------------------------
# state/stage_k/profile
# Bound analysis to declared supported semantics, not an invented compiler.
SUPPORTED = ((0, 4, 0), (0, 9, 0))

class SupportedSourceView(StageFSourceView):
    def __init__(self, source, file, metadata=None):
        super().__init__(source, file, metadata)
        original = self.version_interval
        low, high = max(original[0], SUPPORTED[0]), min(original[1], SUPPORTED[1])
        if low >= high:
            raise Unsupported("K: no intersection with supported semantic domain")
        # Missing/contradictory metadata and legacy/modern scope ambiguity have
        # already failed in Stage F; this must not bypass those checks.
        original_evidence = copy.deepcopy(self.version_evidence)
        self.version_interval = (low, high)
        if mode_for(source, self.tree.root_node, self.version_interval) != self.mode:
            raise Unsupported("K: profile changed lexical scope")
        self.version_evidence = {
            "kind": "explicit_supported_analysis_domain",
            "version": VERSION,
            "source_evidence": original_evidence,
            "pragma_or_recorded_interval": original,
            "supported_domain": SUPPORTED,
            "analyzed_interval": self.version_interval,
            "domain_restricted": original != self.version_interval,
            "excluded_future_interval": (high, original[1]) if high < original[1] else None,
            "exact_compiler": original_evidence.get("metadata", {}).get("version")
                if original_evidence.get("metadata") else None,
            "independently_compiled": False,
            "guarantee": "only supported interval; future versions and full compiler validity not asserted",
        }
