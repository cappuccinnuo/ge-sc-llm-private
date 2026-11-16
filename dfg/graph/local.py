"""Layer L1: local ``DATA_DEF_USE`` edges.

Reaching definitions are computed per function on the semantic CFG and the
resulting definition-use pairs are projected onto HCG statement nodes. Files the
analyzers cannot support fall back to no L1 edges (recorded in the audit).
"""
import copy
import hashlib
import re
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from typing import List, Tuple

from dfg.analysis.access import AccessExtractor, prefix_access_shape
from dfg.analysis.cfg import analyze
from dfg.analysis.dataflow import RDResult, _reachable_order, solve
from dfg.analysis.frontend import (
    FUNCTION_TYPES,
    SupportedSourceView,
    parse,
    parse_source,
    span,
    text,
    walk)
from dfg.analysis.ir import Definition, Fact, Span, Symbol, Unsupported
from dfg.analysis.state import ClosedScopeJ, StageFCallResolver, StageJCFGBuilder, prefix_modifier
from dfg.analysis.symbols import SymbolTable, _same, _scalar_type, _walk
from dfg.graph.audit import assert_augmented, fingerprint
from dfg.graph.projection import Projector
from dfg.schema import DATA_DEF_USE, DDG_VERSION, VERSION


# ----------------------------------------------------------------------
# ddg_builder
# Build auditable direct facts and forward edges, without reading labels.
@dataclass
class BuildResult:
    view: object = None
    facts: List[Fact] = field(default_factory=list)
    diagnostics: List[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

class DDGBuilder:
    def __init__(self, max_iterations=100000):
        self.max_iterations=max_iterations

    def analyze_source(self, source, file, mode=None):
        result=BuildResult(stats={"functions_total":0,"functions_supported":0,
                                 "definitions":0,"uses_total":0,"uses_resolved":0,
                                 "iterations":0})
        try: view=parse_source(source,file,mode)
        except Unsupported as exc:
            result.diagnostics.append({"kind":"file_fallback","file":file,"reason":str(exc)})
            return result
        result.view=view
        analysis=analyze(view)
        result.diagnostics.extend(analysis.diagnostics)
        result.stats["functions_total"]=len(view.functions)
        for ir in analysis.functions:
            try: rd=solve(ir,self.max_iterations)
            except Unsupported as exc:
                result.diagnostics.append({"kind":"function_fallback","function":ir.id,"reason":str(exc)})
                continue
            result.facts.extend(rd.facts)
            result.stats["functions_supported"]+=1
            result.stats["definitions"]+=len(rd.definitions)
            result.stats["uses_total"]+=rd.uses_total
            result.stats["uses_resolved"]+=rd.uses_resolved
            result.stats["iterations"]+=rd.iterations
        return result

    def projected_edges(self, facts, mapping):
        """mapping is exact Span -> frozen HCG ID; no line/nearest fallback."""
        edges={}
        evidence=[]
        skipped=0
        self_facts=0
        for fact in facts:
            if fact.definition.function != fact.use.function:
                raise ValueError("Cross-function fact")
            a,b=fact.definition.anchor,fact.use.anchor
            if a.file != b.file: raise ValueError("Cross-file fact")
            if a not in mapping or b not in mapping:
                skipped+=1
                continue
            src,dst=mapping[a],mapping[b]
            ev={"symbol":fact.symbol,"function":fact.use.function,
                "definition":fact.definition.id,"use":fact.use.id,
                "source":src,"target":dst,"self_fact":src==dst}
            evidence.append(ev)
            if src==dst:
                self_facts+=1
                continue
            edges.setdefault((src,dst),[]).append(len(evidence)-1)
        output=[(s,t,{"edge_type":DATA_DEF_USE,"ddg_version":DDG_VERSION,
                     "ddg_fact_indices":indices})
                for (s,t),indices in edges.items()]
        stats={"facts_total":len(facts),"facts_projected":len(evidence),
               "facts_unmapped":skipped,"self_facts":self_facts,
               "edges_added":len(output),
               "duplicate_projected_pairs":len(evidence)-self_facts-len(output)}
        return output,evidence,stats


# ----------------------------------------------------------------------
# dfg_v2/l1_models
# Immutable L1 events extending the frozen scalar event contract.
@dataclass(frozen=True)
class V2Event:
    id: str
    function: str
    anchor: Span
    reads: Tuple[str, ...] = ()
    writes: Tuple[str, ...] = ()
    weak_writes: Tuple[str, ...] = ()
    kind: str = "expression"


# ----------------------------------------------------------------------
# dfg_v2/l1_symbols
# Aggregate local symbols; lexical identity remains the scalar implementation.
#
# The fallback registration block mirrors scripts/DFG/symbol_table.py::_add,
# SHA256 ce57e804d684da00792ff954e53c71a55254214b2e1ef3163025aa66d8c31566.
# Only accepted type classification is extended; scope/visibility/identity and
# the original frozen Symbol are unchanged.
def _scalar_name(name):
    integer = re.fullmatch(r"(u?int)([0-9]+)", name)
    fixed = re.fullmatch(r"bytes([0-9]+)", name)
    return bool(name in ("bool", "address", "address payable", "uint", "int")
                or (integer and 8 <= int(integer.group(2)) <= 256
                    and int(integer.group(2)) % 8 == 0)
                or (fixed and 1 <= int(fixed.group(1)) <= 32))

def _extended_type(node, mode):
    """Check grammar structure; never infer the pointee type or storage slot."""
    if node is None:
        raise Unsupported("V2: declaration has no recognizable type")
    name = " ".join(node.text.decode("utf8").split())
    if any(item.type in ("function", "function_type") for item in _walk(node)):
        raise Unsupported("V2: function type remains unsupported")
    # Function is an unnamed grammar child and is not included by _walk.
    if any(child.type == "function" for child in node.children):
        raise Unsupported("V2: function type remains unsupported")
    children = [child for child in node.named_children if "comment" not in child.type]
    if node.type == "type_name":
        if any(child.type == "function" for child in node.children):
            raise Unsupported("V2: function type remains unsupported")
        if any(child.type == "[" for child in node.children):
            bases = [child for child in children if child.type == "type_name"]
            if len(bases) != 1:
                raise Unsupported("V2: ambiguous array element type")
            _extended_type(bases[0], mode)
            return True
        if any(child.type == "mapping" for child in node.children):
            key = node.child_by_field_name("key_type")
            value = node.child_by_field_name("value_type")
            if key is None or value is None:
                raise Unsupported("V2: mapping lacks key/value type")
            _extended_type(key, mode)
            _extended_type(value, mode)
            return True
        if len(children) == 1 and children[0].type in ("primitive_type", "user_defined_type"):
            return _extended_type(children[0], mode)
        raise Unsupported("V2: unsupported aggregate type shape: " + name)
    if node.type == "user_defined_type":
        # Includes contract/enum names, conservatively represented as aggregates.
        return True
    if node.type == "primitive_type":
        if name == "var":
            if mode != "legacy":
                raise Unsupported("V2: inferred var is only allowed in legacy mode")
            return True
        if name in ("string", "bytes"):
            return True
        if _scalar_name(name):
            return False
    raise Unsupported("V2: unsupported type: " + name)

class ExtendedSymbolTable(SymbolTable):
    def __init__(self, source, file, function, mode):
        self.aggregate_info = {}
        super().__init__(source, file, function, mode)

    def _add(self, declaration, kind, scope, visible):
        try:
            type_name = _scalar_type(declaration)
        except Unsupported:
            node = declaration.child_by_field_name("type")
            aggregate = _extended_type(node, self.mode)
            type_name = " ".join(node.text.decode("utf8").split())
            location = declaration.child_by_field_name("location")
            location = location.text.decode("utf8") if location is not None else None
            if location not in (None, "memory", "storage", "calldata"):
                raise Unsupported("V2: unknown data location: " + location)
            name_node = declaration.child_by_field_name("name")
            if name_node is None:
                if kind in ("parameter", "return"):
                    return
                raise Unsupported("Local declaration is missing a name")
            name = name_node.text.decode("utf8")
            # The identity and duplicate/scope checks below are copied verbatim
            # from the original registration path cited above.
            for old_scope, _, _ in self._bindings.get(name, ()):
                if _same(old_scope, scope):
                    raise Unsupported("Duplicate declaration in the same scope: " + name)
            if declaration.start_byte in self.declarations:
                raise Unsupported("Ambiguous declaration byte position")
            identity = "{}:{}:{}".format(self.function_id, declaration.start_byte, name)
            symbol = Symbol(
                identity, name, self.function_id,
                Span(self.file, declaration.start_byte, declaration.end_byte, kind),
                kind, type_name,
            )
            self.symbols[identity] = symbol
            self.declarations[declaration.start_byte] = symbol
            self._bindings.setdefault(name, []).append((scope, visible, symbol))
        else:
            # Exact existing scalar registration and its validation.
            super()._add(declaration, kind, scope, visible)
            symbol = self.declarations.get(declaration.start_byte)
            if symbol is None:  # An unnamed parameter/return is not a symbol.
                return
            aggregate, location = False, None
        self.aggregate_info[symbol.id] = {
            "aggregate": aggregate, "location": location, "type": type_name,
        }


# ----------------------------------------------------------------------
# dfg_v2/l1_access
# L1 scalar-compatible extraction with conservative aggregate weak writes.
#
# Aggregate arguments to ordinary calls remain reads only (no interprocedural
# memory/storage summaries). A member/index write changes a coarse base symbol;
# it does not model field-sensitive aliases or storage locations.
class ExtendedAccessExtractor(AccessExtractor):
    def _aggregate(self, symbol):
        return bool(symbol and self.table.aggregate_info[symbol].get("aggregate"))

    def _chain_root(self, node):
        while node is not None:
            if node.type in ("member_expression", "array_access"):
                field = "object" if node.type == "member_expression" else "base"
                node = node.child_by_field_name(field)
            elif node.type == "parenthesized_expression":
                children = [child for child in node.named_children if "comment" not in child.type]
                if len(children) != 1:
                    raise Unsupported("V2: ambiguous parenthesized access base")
                node = children[0]
            else:
                break
        return node if node is not None and node.type == "identifier" else None

    def _mutator_base(self, node):
        if node is None or node.type != "call_expression":
            return None
        function = node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            return None
        prop = function.child_by_field_name("property")
        if prop is None or self._name(prop) not in ("push", "pop"):
            return None
        return function.child_by_field_name("object")

    def reads(self, node):
        # Treat a nested local aggregate mutator as a nested write. Ordinary
        # calls (including aggregate arguments) retain the inherited read rule.
        base = self._mutator_base(node)
        root = self._chain_root(base)
        if root is not None:
            symbol = self.table.resolve(self._name(root), root)
            if symbol is not None and self._aggregate(symbol.id):
                raise Unsupported("V2: nested aggregate mutation / unspecified operand order")
        if node is not None and node.type == "new_expression":
            # P6b approved AST adaptation: the new-expression name is a type,
            # not a value read. Outer call/options nodes read their arguments.
            declared_type = node.child_by_field_name("name")
            if declared_type is None or declared_type.type != "type_name":
                raise Unsupported("V2: unknown new-expression type shape")
            # P6d defensive grammar branch: some supported parser versions
            # allow arguments directly under new_expression. Never traverse
            # the type_name as a value; inherited reads retain nested-write
            # and unknown-expression rejection for each direct argument.
            result = []
            for child in node.named_children:
                if child.type == "call_argument":
                    result += self.reads(child)
            return result
        if node is not None and node.type == "struct_expression":
            # P6b: call options are encoded as a struct-shaped wrapper.
            # Read the callee/base and option values, never the option names.
            # Recursive reads preserve inherited unknown/nested-write fallback.
            result = self.reads(node.child_by_field_name("type"))
            for child in node.named_children:
                if child.type == "struct_field_assignment":
                    result += self.reads(child.child_by_field_name("value"))
            return result
        return super().reads(node)

    def targets(self, node):
        if node.type == "identifier":
            symbol = self._resolve(node)
            return [], [symbol] if symbol else [], []
        if node.type in ("member_expression", "array_access"):
            root = self._chain_root(node)
            symbol = self._resolve(root) if root is not None else None
            # reads traverses every member/base/index and rejects nested writes.
            return self.reads(node), [], [symbol] if self._aggregate(symbol) else []
        if node.type == "tuple_expression":
            reads, writes, weak = [], [], []
            for child in node.named_children:
                if "comment" in child.type:
                    continue
                r, w, ww = self.targets(child)
                reads.extend(r)
                writes.extend(w)
                weak.extend(ww)
            all_targets = writes + weak
            if len(all_targets) != len(set(all_targets)):
                raise Unsupported("Repeated tuple assignment target")
            return reads, writes, weak
        raise Unsupported("Unsupported assignment target: " + node.type)

    def event(self, anchor, reads=(), writes=(), kind="expression", weak_writes=()):
        strong, weak = set(writes), set(weak_writes)
        if strong & weak:
            raise Unsupported("V2: overlapping strong and weak write target")
        result = V2Event(
            id=self.table.function_id + ":e" + str(self.counter),
            function=self.table.function_id,
            anchor=anchor,
            reads=tuple(sorted(set(reads))),
            writes=tuple(sorted(strong)),
            weak_writes=tuple(sorted(weak)),
            kind=kind,
        )
        self.counter += 1
        return result

    def _prefix_access_event(self, node, owner):
        """Adapt only a top-level prefix + access-chain parser precedence shape.

        Installed grammar parses delete a[i] as array_access(unary(delete,a),i).
        Follow AST base/object fields, never text replacement or line proximity.
        Nested operators in indices/arguments still pass through reads() and fail.
        """
        shape = prefix_access_shape(node)
        if shape is None:
            return None
        spelling, argument, indices = shape
        root = self._chain_root(argument)
        symbol = self._resolve(root) if root is not None else None
        reads = self.reads(argument)
        for index in indices:
            reads += self.reads(index)
        weak = [symbol] if self._aggregate(symbol) else []
        self.diagnostics.append({
            "kind": "v2_prefix_access_chain",
            "operator": spelling, "byte": node.start_byte,
            "parser_shape": argument.parent.type, "anchor_preserved": True,
        })
        return self.event(owner, reads, kind="delete" if spelling == "delete" else "update",
                          weak_writes=weak)

    def extract(self, node, anchor=None):
        if node is None:
            return []
        owner = anchor or span(self.table.file, node)
        kind = node.type
        if kind in ("member_expression", "array_access"):
            prefix_event = self._prefix_access_event(node, owner)
            if prefix_event is not None:
                return [prefix_event]
        if kind in ("assignment_expression", "augmented_assignment_expression"):
            left = node.child_by_field_name("left")
            reads, writes, weak = self.targets(left)
            if kind == "augmented_assignment_expression":
                reads += self.reads(left)
            reads += self.reads(node.child_by_field_name("right"))
            return [self.event(owner, reads, writes, "assignment", weak)]
        if kind == "update_expression":
            argument = node.child_by_field_name("argument")
            reads, writes, weak = self.targets(argument)
            return [self.event(owner, reads + self.reads(argument), writes, "update", weak)]
        if kind == "unary_expression":
            operator = node.child_by_field_name("operator")
            if operator is not None and self._name(operator) == "delete":
                reads, writes, weak = self.targets(node.child_by_field_name("argument"))
                return [self.event(owner, reads, writes, "delete", weak)]
        base = self._mutator_base(node)
        if base is not None:
            root = self._chain_root(base)
            symbol = self._resolve(root) if root is not None else None
            reads = self.reads(base)
            for child in node.named_children:
                if child.type in ("call_argument", "call_struct_argument"):
                    reads += self.reads(child)
            weak = [symbol] if self._aggregate(symbol) else []
            return [self.event(owner, reads, kind="expression", weak_writes=weak)]
        # Declaration/return/emit/entry and expression-statement dispatch are
        # inherited, with this event factory returning immutable V2Event.
        return super().extract(node, anchor)


# ----------------------------------------------------------------------
# dfg_v2/l1_cfg
# L1 analysis-only CFG: unchanged Stage J statements and modifier semantics.
#
# Constructor copied from scripts/DFG/state/stage_j/analyzer.py::StageJCFGBuilder.
# Source SHA256: f2934f3efc7d202e6fe78c2f7e26bf172b663067713fb3108e48a522b001d6af
# Only the symbol table and access extractor differ; no HCG nodes are added.
class V2CFGBuilder(StageJCFGBuilder):
    def __init__(self, view, function, enable_modifiers=True):
        self.view, self.function = view, function
        # P2 change: keep declaration identities/scopes, permit aggregate locals.
        self.table = ExtendedSymbolTable(view.source, view.file, function, view.mode)
        self.scope = ClosedScopeJ(view, function)
        # P2 change: strong/weak V2Events; inherited build/statement code unchanged.
        self.access = ExtendedAccessExtractor(view.source, self.table)
        self.blocks = {}
        self.call_bindings, self.binding_diagnostics = StageFCallResolver(
            view, function, self.table, self.scope).preflight()
        if not enable_modifiers and any(n.type == "modifier_invocation" for n in function.named_children):
            raise Unsupported("J: modifier recovery disabled")
        self.prefix, self.modifier_evidence = prefix_modifier(view, function, self.scope)


# ----------------------------------------------------------------------
# dfg_v2/l1_rd
# DFG v2 reaching definitions with strong and weak aggregate writes.
#
# Source: scripts/DFG/reaching_definitions.py
# Source SHA256: d3b35d9696a0ad922274ea9c36595531930ab46a50106bfa9a03d3634476846f
# Copied algorithm: solve and _validate_and_index; _reachable_order and RDResult
# are imported unchanged. The only transfer extension is that weak writes GEN
# without KILL. This analysis IR never changes the model CFG or graph labels.
SOURCE_SHA256 = "d3b35d9696a0ad922274ea9c36595531930ab46a50106bfa9a03d3634476846f"

def _validate_and_index_v2(ir):
    if ir.entry not in ir.blocks:
        raise Unsupported("RD entry block is absent")
    for identifier, symbol in ir.symbols.items():
        if identifier != symbol.id or symbol.function != ir.id:
            raise Unsupported("RD symbol belongs to another function or has inconsistent ID")
        if symbol.declaration.file != ir.file:
            raise Unsupported("RD symbol source file differs from its function")
    events = set()
    definitions = {}
    by_symbol = defaultdict(set)
    predecessors = {identifier: set() for identifier in ir.blocks}
    for identifier in sorted(ir.blocks):
        block = ir.blocks[identifier]
        if identifier != block.id:
            raise Unsupported("RD block dictionary key differs from its ID")
        for successor in block.successors:
            if successor not in ir.blocks:
                raise Unsupported("RD successor block is absent: " + str(successor))
            predecessors[successor].add(identifier)
        for event in block.events:
            if event.id in events:
                raise Unsupported("RD event IDs must be unique")
            events.add(event.id)
            if event.function != ir.id or event.anchor.file != ir.file:
                raise Unsupported("RD event belongs to another function or file")
            # V2: original Event is still accepted for scalar parity probes.
            weak_writes = tuple(getattr(event, "weak_writes", ()))
            if set(event.writes).intersection(weak_writes):
                raise Unsupported("RD event contains overlapping strong and weak writes")
            for symbol_id in tuple(event.reads) + tuple(event.writes) + weak_writes:
                if symbol_id not in ir.symbols:
                    raise Unsupported("RD event references an unknown symbol")
            # V2: weak definitions have the same static identity scheme.
            for symbol_id in dict.fromkeys(tuple(event.writes) + weak_writes):
                definition_id = event.id + ":" + symbol_id
                if definition_id in definitions:
                    raise Unsupported("RD static definition identity collision")
                definition = Definition(
                    definition_id, symbol_id, event.id, ir.id, event.anchor)
                definitions[definition_id] = definition
                by_symbol[symbol_id].add(definition_id)
    return definitions, by_symbol, predecessors

def solve_v2(ir, max_iterations=100000):
    """Return direct def-to-read facts after convergence, retaining weak defs.

    Strong writes replace all incoming definitions of that declaration identity.
    Weak writes add a definition while retaining the earlier possible values.
    Reads precede writes within an event. Unreachable definitions remain indexed
    for auditing but do not produce facts. Worklist ordering and accounting are
    unchanged from the scalar solver, including when weak_writes is empty.
    """
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    definitions, by_symbol, predecessors = _validate_and_index_v2(ir)
    order, reachable = _reachable_order(ir)
    generated, killed = {}, {}
    for identifier in order:
        block_generated, block_killed = set(), set()
        for event in ir.blocks[identifier].events:
            for symbol_id in dict.fromkeys(event.writes):
                # V2: a strong write also removes earlier weak writes in block.
                block_generated.difference_update(by_symbol[symbol_id])
                block_generated.add(event.id + ":" + symbol_id)
                block_killed.update(by_symbol[symbol_id])
            for symbol_id in dict.fromkeys(getattr(event, "weak_writes", ())):
                block_generated.add(event.id + ":" + symbol_id)
        generated[identifier] = frozenset(block_generated)
        killed[identifier] = block_killed
    in_sets = {identifier: frozenset() for identifier in ir.blocks}
    out_sets = {identifier: frozenset() for identifier in ir.blocks}
    # All reachable blocks start pending, including blocks reached via an empty
    # entry. Enqueuing only after nonempty changes would otherwise miss them.
    pending = deque(order)
    queued = set(order)
    iterations = 0
    while pending:
        if iterations >= max_iterations:
            raise Unsupported("RD worklist did not converge within max_iterations")
        identifier = pending.popleft()
        queued.remove(identifier)
        iterations += 1
        incoming = set()
        for predecessor in predecessors[identifier]:
            if predecessor in reachable:
                incoming.update(out_sets[predecessor])
        new_in = frozenset(incoming)
        new_out = frozenset((incoming - killed[identifier]) | generated[identifier])
        in_sets[identifier] = new_in
        if new_out != out_sets[identifier]:
            out_sets[identifier] = new_out
            for successor in sorted(ir.blocks[identifier].successors):
                if successor not in queued:
                    pending.append(successor)
                    queued.add(successor)
    # Resolve reads only after fixed point; final block GEN does not describe
    # a read before a later write inside the same block.
    facts, uses_total, uses_resolved = [], 0, 0
    for identifier in order:
        current = set(in_sets[identifier])
        for event in ir.blocks[identifier].events:
            for symbol_id in dict.fromkeys(event.reads):
                uses_total += 1
                reaching = current.intersection(by_symbol[symbol_id])
                if reaching:
                    uses_resolved += 1
                for definition_id in sorted(reaching):
                    facts.append(Fact(symbol_id, definitions[definition_id], event))
            for symbol_id in dict.fromkeys(event.writes):
                current.difference_update(by_symbol[symbol_id])
                current.add(event.id + ":" + symbol_id)
            # V2: replay must retain prior possible aggregate values as well.
            for symbol_id in dict.fromkeys(getattr(event, "weak_writes", ())):
                current.add(event.id + ":" + symbol_id)
        if current != out_sets[identifier]:
            raise AssertionError("RD block transfer and ordered event replay disagree")
    return RDResult(
        facts, in_sets, out_sets, definitions, reachable, iterations,
        uses_total, uses_resolved)


# ----------------------------------------------------------------------
# dfg_v2/l1
# Add L1 facts only for legacy fallbacks; project with each producing view.
#
# No labels, predictions or token features enter source analysis.
# Aggregate aliases and effects of callees are deliberately not summarized.
@dataclass
class _Analysis:
    facts: list = field(default_factory=list)
    origins: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    views: dict = field(default_factory=dict)
    diagnostics: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def _limits(max_iterations):
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")

def _functions(source):
    return [n for n in walk(parse(source).root_node)
            if n.type in FUNCTION_TYPES and n.child_by_field_name("body") is not None]

def _reason(exc):
    return dict(getattr(exc, "diagnostic", {}), reason=str(exc))

def _routes(builder, old_reason, file_fallback):
    routes = []
    if builder.modifier_evidence is not None:
        routes.append("v2_modifier")
    if len(builder.scope.chain) > 1:
        routes.append("v2_inheritance")
    if file_fallback or old_reason in (
            "builtin_not_guaranteed_over_pragma_interval",
            "pragma_missing_for_builtin_availability"):
        routes.append("v2_version")
    # A permitted unnamed aggregate parameter/return has no Symbol ID but
    # still required extended type acceptance. Classify the declaration, not
    # just the registered symbols. This is audit-only and does not change IR.
    extended_declaration = False
    for declaration in walk(builder.function):
        if declaration.type in ("parameter", "variable_declaration"):
            try:
                _scalar_type(declaration)
            except Unsupported:
                extended_declaration = True
                break
    if extended_declaration:
        routes.append("v2_aggregate")
    if any(d.get("kind") == "v2_prefix_access_chain" for d in builder.access.diagnostics):
        routes.append("v2_access_shape")
    return routes or ["v2_retry"]

def _in_modifier(anchor, spans):
    return any(start <= anchor.start and anchor.end <= end for start, end in spans)

def _analyze(source, file, metadata=None, max_iterations=100000):
    _limits(max_iterations)
    old = DDGBuilder(max_iterations).analyze_source(source, file)
    result = _Analysis(
        facts=list(old.facts), origins=["legacy"] * len(old.facts),
        routes=[["legacy"] for _ in old.facts], diagnostics=list(old.diagnostics))
    if old.view is not None:
        result.views["legacy"] = old.view
    old_failures = {d["function"]: d["reason"] for d in old.diagnostics
                    if d.get("kind") == "function_fallback"}
    old_file_reason = next((d["reason"] for d in old.diagnostics
                            if d.get("kind") == "file_fallback"), None)
    functions = old.view.functions if old.view is not None else []
    try:
        if old.view is None:
            functions = _functions(source)
    except Unsupported:
        pass
    supported = {file + ":" + str(n.start_byte) for n in functions
                 if old.view is not None and file + ":" + str(n.start_byte) not in old_failures}
    if len(supported) != old.stats["functions_supported"]:
        raise AssertionError("Legacy success identity accounting differs")
    pending = [n for n in functions if file + ":" + str(n.start_byte) not in supported]
    view, view_error = None, None
    if pending:
        try:
            view = SupportedSourceView(source, file, metadata)
            result.views["v2"] = view
        except Unsupported as exc:
            view_error = str(exc)
            result.diagnostics.append(dict(kind="v2_file_fallback", file=file, reason=view_error,
                                           legacy_results_retained=True))
    modifiers = [(n.start_byte, n.end_byte) for n in walk(view.tree.root_node)
                 if n.type == "modifier_definition"] if view is not None else []
    new_by_id = {file + ":" + str(n.start_byte): n for n in view.functions} if view else {}
    old_fact_counts = Counter(f.use.function for f in old.facts)
    records, filtered = [], []
    for fn in functions:
        ident = file + ":" + str(fn.start_byte)
        name = fn.child_by_field_name("name")
        rec = dict(function=ident, file=file, start=fn.start_byte, end=fn.end_byte,
                   line=fn.start_point[0] + 1,
                   name=text(source, name) if name is not None else fn.type,
                   old_status="supported" if ident in supported else "fallback",
                   old_reason=None if ident in supported else old_failures.get(ident, old_file_reason))
        if ident in supported:
            rec.update(status="supported", routes=["legacy"], facts=old_fact_counts[ident],
                       recovered=False, legacy_reused=True)
        elif view is None:
            rec.update(status="fallback", routes=[], facts=0, recovered=False,
                       reason=view_error or old_file_reason, partial_facts_published=False)
        else:
            try:
                if ident not in new_by_id:
                    raise Unsupported("Function identity differs between source views")
                builder = V2CFGBuilder(view, new_by_id[ident])
                ir = builder.build()
                rd = solve_v2(ir, max_iterations)
                routes = _routes(builder, rec["old_reason"], old.view is None)
                accepted = []
                for fact in rd.facts:
                    if _in_modifier(fact.definition.anchor, modifiers) or _in_modifier(fact.use.anchor, modifiers):
                        filtered.append(dict(function=ident, symbol=fact.symbol,
                                             definition=asdict(fact.definition.anchor),
                                             use=asdict(fact.use.anchor)))
                    else:
                        accepted.append(fact)
                # Commit only after CFG+RD complete; a failed function has no partial facts.
                result.facts.extend(accepted)
                result.origins.extend(["v2"] * len(accepted))
                result.routes.extend([list(routes) for _ in accepted])
                for diagnostic in builder.binding_diagnostics + builder.access.diagnostics:
                    result.diagnostics.append(dict(diagnostic, function=ident, analysis_path="v2"))
                rec.update(status="supported", routes=routes, facts=len(accepted), recovered=True,
                           legacy_reused=False, weak_definitions=sum(len(e.weak_writes)
                               for block in ir.blocks.values() for e in block.events),
                           binding=dict(scope=builder.scope.evidence,
                                        modifier=builder.modifier_evidence,
                                        version=view.version_evidence))
            except Unsupported as exc:
                diagnostic = dict(_reason(exc), kind="v2_function_fallback", function=ident,
                                  file=file, partial_facts_published=False)
                result.diagnostics.append(diagnostic)
                rec.update(status="fallback", routes=[], facts=0, recovered=False,
                           reason=str(exc), partial_facts_published=False)
        records.append(rec)
    routes = Counter(route for rec in records for route in rec["routes"])
    cross = Counter((rec["old_reason"] or "legacy_supported",
                     "+".join(rec["routes"]) if rec["status"] == "supported"
                     else "fallback:" + str(rec["reason"])) for rec in records)
    result.stats = dict(functions_total=len(functions), functions_supported=sum(
        rec["status"] == "supported" for rec in records),
        legacy_supported=len(supported), recovered=sum(rec["recovered"] for rec in records),
        legacy_stats=old.stats, legacy_file_reason=old_file_reason, v2_view_error=view_error,
        facts_total=len(result.facts), legacy_facts=len(old.facts),
        modifier_facts_dropped=len(filtered), modifier_fact_examples=filtered,
        routes=dict(routes), functions=records,
        fallback_reasons=dict(Counter(rec["reason"] for rec in records if rec["status"] == "fallback")),
        recovery_cross_table=[dict(old_reason=old, new_result=new, functions=count)
                              for (old, new), count in sorted(cross.items())],
        approximate_call_effects="aggregate call arguments read only; aliases/callee mutations not summarized")
    return result

def analyze_file(source, file, metadata=None, max_iterations=100000):
    """Return immutable facts, diagnostics and JSON-serializable statistics."""
    result = _analyze(source, file, metadata, max_iterations)
    return result.facts, result.diagnostics, result.stats

def augment_l1(graph, sources, metadata=None, max_iterations=100000):
    """Return a new frozen-node HCG with merged forward DATA_DEF_USE edges."""
    _limits(max_iterations)
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected a directed MultiDiGraph")
    if any(d.get("edge_type") == DATA_DEF_USE or str(d.get("edge_type", "")).startswith("REV_")
           for _, _, d in graph.edges(data=True)):
        raise ValueError("Expected an unenhanced HCG")
    initial = fingerprint(graph)
    output = copy.deepcopy(graph)
    audit = dict(version=VERSION, layer="L1", profile="G1R", files={}, evidence=[],
                 source_hashes={}, labels_used_for_analysis=False, token_features_changed=False)
    builder = DDGBuilder(max_iterations)
    files = list(dict.fromkeys(d["source_file"] for _, d in graph.nodes(data=True)))
    for file in files:
        if file not in sources:
            audit["files"][file] = dict(diagnostics=[dict(kind="file_fallback",
                reason="Source manifest has no exact file identity")])
            continue
        result = _analyze(sources[file], file, (metadata or {}).get(file), max_iterations)
        record = dict(analysis=result.stats, diagnostics=list(result.diagnostics), views={})
        audit["files"][file] = record
        audit["source_hashes"][file] = hashlib.sha256(sources[file].encode("utf8")).hexdigest()
        mapping, projectors = {}, {}
        for origin, view in result.views.items():
            selected = [f for f, path in zip(result.facts, result.origins) if path == origin]
            try:
                projector = Projector(graph, view)
                local_mapping, diagnostics = projector.map_facts(selected)
                for anchor, identifier in local_mapping.items():
                    if anchor in mapping and mapping[anchor] != identifier:
                        raise AssertionError("Producing views disagree on an exact anchor")
                    mapping[anchor] = identifier
                projectors[origin] = projector
                record["diagnostics"].extend(diagnostics)
                record["views"][origin] = dict(projector.stats, scope_mode=view.mode)
            except Unsupported as exc:
                record["diagnostics"].append(dict(kind="projection_fallback", origin=origin,
                                                   reason=str(exc)))
        if len(projectors) == 2:
            if projectors["legacy"].by_ast != projectors["v2"].by_ast:
                raise AssertionError("SourceView and SupportedSourceView AST node projections differ")
            record["projectors_by_ast_equal"] = True
        # Do not let a failed view borrow another view's projection.
        valid = [(f, origin, routes) for f, origin, routes in
                 zip(result.facts, result.origins, result.routes) if origin in projectors]
        facts = [x[0] for x in valid]
        edges, evidence, stats = builder.projected_edges(facts, mapping)
        route_lookup = {(f.definition.id, f.use.id, f.symbol): (origin, routes)
                        for f, origin, routes in valid}
        for ev in evidence:
            origin, routes = route_lookup[(ev["definition"], ev["use"], ev["symbol"])]
            ev.update(analysis_path=origin, routes=list(routes))
        record["projection"] = stats
        record["anchors"] = [dict(asdict(anchor), node_id=identifier)
                             for anchor, identifier in sorted(mapping.items())]
        offset = len(audit["evidence"])
        audit["evidence"].extend(evidence)
        for src, dst, attrs in edges:
            indices = attrs["ddg_fact_indices"]
            attrs["routes"] = sorted({route for i in indices for route in evidence[i]["routes"]})
            attrs["dfg_v2_version"] = VERSION
            attrs["ddg_fact_indices"] = [offset + i for i in indices]
            output.add_edge(src, dst, **attrs)
    audit["invariants"] = assert_augmented(graph, output)
    if fingerprint(graph) != initial:
        raise AssertionError("Input graph mutated")
    return output, audit
