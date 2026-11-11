"""Read-only AST and semantic-CFG sources for EdgeSem attributes.

The shape/definition/access helpers follow the r4 feasibility probe
scripts/edge_sem/recon/ep0b_attributes.py, but have no recon dependency.
CFG construction uses frozen node_sem.facts_cfg.FileCFG; dominance follows
the EP0 algorithm (reachable graph, synthetic exit, partial postdominance).
Spelling is used only for exact declaration joins, never name heuristics.
"""
from collections import defaultdict
import networkx as nx
from scripts.node_sem.facts_ast import AstSemantics, key, FUNCTIONS, contains
from scripts.node_sem.facts import _raw_projection
from scripts.node_sem.facts_cfg import FileCFG
from scripts.node_sem.facts_guards import GuardAnalyzer
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.projection import Projector
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.versioning import effective_interval
from .guard_source import modifier_guard_sources


class AttributeSource:
    """One source view and guard analyzer per file, CFG cached by function."""
    def __init__(self, source, file, graph, metadata=None):
        self.source, self.file = source, file
        self.view = ProjectionView(source, file)
        self.sem = AstSemantics(self.view)
        nodes = [n for n,a in graph.nodes(data=True)
                 if a["source_file"] == file and a["node_type"] != "env_source"]
        self.projector = Projector(graph.subgraph(nodes), self.view)
        self.raw = _raw_projection(self.view, self.projector)
        self.ast = {key(n):n for n in self.sem.nodes}
        self.inverse = {key(n):i for i,n in self.raw.items()}
        if len(self.inverse) != len(self.raw):
            raise ValueError("Nonunique attribute AST projection")
        self.cfg = FileCFG(source, file, metadata)
        self.guard = GuardAnalyzer(self.sem)
        self.cfg_cache, self.mod_cache = {}, {}
        self.functions = {file+":"+str(n.start_byte):n for n in self.sem.functions}
        try:
            iv = effective_interval(source, self.view.tree.root_node, metadata)[0]
            self.pre_08 = True if iv and iv[1] <= (0,8,0) else False if iv and iv[0] >= (0,8,0) else None
        except Unsupported:
            self.pre_08 = None

    def modifier_records(self, src, dst):
        fn, mod = self.raw[src], self.raw[dst]
        if key(fn) not in self.mod_cache:
            self.mod_cache[key(fn)] = modifier_guard_sources(self.guard, fn)
        return [r["record"] for r in self.mod_cache[key(fn)]
                if contains(mod, r["inner_anchor"])]

    def function_guard_unknown(self, src):
        fn = self.raw[src]
        # _modifiers returns (records, unresolved) in the frozen implementation.
        return bool(self.guard._modifiers(fn)[1])

    def semantic(self, function):
        ident = key(function)
        if ident in self.cfg_cache:
            return self.cfg_cache[ident]
        result = self.cfg.build(function)
        if result["status"] != "supported":
            out = dict(status="unknown", errors=result["errors"])
            self.cfg_cache[ident] = out
            return out
        ir = result["ir"]
        graph = nx.DiGraph()
        graph.add_nodes_from(ir.blocks)
        for block in ir.blocks.values():
            graph.add_edges_from((block.id,t) for t in block.successors)
        reached = {ir.entry} | nx.descendants(graph, ir.entry)
        active = graph.subgraph(reached).copy()
        dom = nx.immediate_dominators(active, ir.entry)
        exits = [b for b in active if active.out_degree(b) == 0]
        reverse = active.reverse(copy=True)
        sink = ("EdgeSem", "virtual_exit")
        reverse.add_node(sink)
        reverse.add_edges_from((sink,b) for b in exits)
        post = nx.immediate_dominators(reverse,sink)
        mappings = defaultdict(set)
        missing = 0
        for block in ir.blocks.values():
            if block.id not in active:
                continue
            for event in block.events:
                try:
                    compat = self.view.compat_key(event.anchor)
                    node = self.projector.by_ast.get(self.view.compat_ids[compat])
                except (Unsupported,KeyError):
                    node = None
                if node is None:
                    missing += 1
                else:
                    mappings[node].add(block.id)
        reach = {b: {b} | nx.descendants(active,b) for b in active}
        back = [(s,t) for s,t in active.edges() if dominates(dom,t,s)]
        out = dict(status="supported",route=result["route"],graph=active,
                   dom=dom,post=post,blocks=dict(mappings),reach=reach,back=back,
                   missing_anchors=missing,entry=ir.entry)
        self.cfg_cache[ident] = out
        return out

    def endpoints(self, src, dst):
        left,right = self.raw.get(src),self.raw.get(dst)
        fn = self.sem.owner(left)
        if fn is None or key(fn) != key(self.sem.owner(right)):
            return None
        result = self.semantic(fn)
        if result["status"] != "supported":
            return None
        if not result["blocks"].get(src) or not result["blocks"].get(dst):
            return None
        return result


def dominates(tree, source, target):
    if target not in tree:
        return False
    seen = set()
    while target not in seen:
        if target == source:
            return True
        seen.add(target)
        target = tree[target]
    return False


def reaches(result, source, target):
    return any(b in result["reach"].get(a,()) for a in result["blocks"].get(source,())
               for b in result["blocks"].get(target,()))


def carried(result, source, target):
    """r12: dependence needs a subsequent iteration of a shared natural loop.

    Explicit user-approved exception: a same-node def/use self edge inside a
    natural loop represents a previous-iteration value. Different graph nodes
    mapped to the same block remain forward reachable and are not carried.
    """
    if "natural_loops" not in result:
        graph = result["graph"]
        loops = []
        for tail, header in result["back"]:
            without_header = graph.subgraph([n for n in graph if n != header])
            body = ({tail} | nx.ancestors(without_header, tail)) if tail != header else set()
            loops.append(body | {header})
        forward = graph.copy()
        forward.remove_edges_from(result["back"])
        result["natural_loops"] = loops
        result["forward_reach"] = {n: {n} | nx.descendants(forward, n) for n in forward}
    defs, uses = result["blocks"][source], result["blocks"][target]
    shared = any(defs & loop and uses & loop for loop in result["natural_loops"])
    if not shared:
        return False
    if source == target:
        return True
    return not any(u in result["forward_reach"][d] for d in defs for u in uses)


# r4 AST classifications; frozen type helper SHA256: 644ca31a1dd890f67ac850e28fa68b9ae6b585cb0be019a6611aba154fc1d5a5
import re
from scripts.node_sem.facts_ast import shape, unwrap, operator

def shape_safe(type_name):
    name = " ".join(type_name.split())
    if name.startswith("mapping"):
        return "mapping"
    if "[" in name:
        return "array"
    if name in ("address", "address payable"):
        return "address"
    # Restore the remaining frozen categories without its startswith(address).
    if name.startswith("address"):
        return "struct_contract" if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*",name) else "other"
    return shape(type_name)


def declaration_shape(sem, statement, variable):
    """Follow r4 literally; partial/unresolved identifier matches stay unknown."""
    occurrences = [n for n in sem.owned_nodes(statement)
                   if n.type == "identifier" and sem.text(n) == variable]
    bindings = [sem.root_binding(n) for n in occurrences]
    declarations = {key(b["declaration"]): b for b in bindings if b["declaration"] is not None}
    missing = sum(b["declaration"] is None or not b["type_name"] for b in bindings)
    if len(declarations) > 1:
        status = "multiple_declarations"
    elif not occurrences:
        status = "no_identifier_occurrence"
    elif missing or not declarations:
        status = "unresolved_binding_or_type"
    else:
        status = "resolved"
    binding = next(iter(declarations.values())) if status == "resolved" else None
    return dict(status=status, occurrences=len(occurrences), unresolved_occurrences=missing,
                declarations=[list(x) for x in sorted(declarations)], declaration_count=len(declarations),
                type_name=binding["type_name"] if binding else None,
                shape=shape_safe(binding["type_name"]) if binding else None)


def def_kind(node):
    if node is None:
        return "unknown"
    if node.type in FUNCTIONS or node.type in ("variable_declaration_statement", "variable_declaration", "parameter"):
        return "decl_or_param"
    expression = unwrap(node)
    op = operator(expression)
    if expression.type in ("assignment_expression", "augmented_assignment_expression"):
        if op == "=":
            return "assign"
        if op.endswith("="):
            return "compound"
    if op in ("++", "--", "delete"):
        return "incdec_or_delete"
    return "unknown"


def write_access(node):
    if node is None:
        return "unknown"
    node = unwrap(node)
    return {"identifier":"plain", "array_access":"indexed",
            "member_expression":"member"}.get(node.type, "other")


def write_op(node):
    cursor = node
    while cursor is not None and cursor.type not in FUNCTIONS:
        if cursor.type in ("assignment_expression", "augmented_assignment_expression",
                           "update_expression", "unary_expression"):
            op = operator(cursor)
            return {"=":"assign", "+=":"increase", "++":"increase",
                    "-=":"decrease", "--":"decrease"}.get(op, "other")
        cursor = cursor.parent
    return "other"

