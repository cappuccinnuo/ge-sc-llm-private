"""Exact existing-node projection; labels/features are never consulted."""
import ast
import re
from collections import defaultdict
from .models import Unsupported

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
    # Only a real serialization layer may be removed. No whitespace/line matching.
    return value==expected or decoded(value)==expected

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
