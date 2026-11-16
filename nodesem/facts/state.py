"""TODO docstring."""
import re
from collections import defaultdict

from nodesem.facts.syntax import FUNCTIONS, contains, key, operator, shape, walk

from dfg.analysis.units import iter_statement_regions
from dfg.graph.binding import StateAccessExtractor, StateBinder
from dfg.graph.state import context


# ----------------------------------------------------------------------
# node_sem/facts_io (picked: check_layer_edge)
def check_layer_edge(source, target, attrs, audit):
    relation = attrs.get("edge_type")
    layer = {"DATA_DEF_USE": "L1", "WRITES_STATE": "L2",
             "READS_STATE": "L2", "ENV_FLOW": "L3"}.get(relation)
    if layer is None:
        return []
    proof = audit["layers"][layer]["evidence"]
    field = "ddg_fact_indices" if layer == "L1" else "evidence_indices"
    indices = attrs.get(field)
    if not isinstance(indices, list) or not indices or len(set(indices)) != len(indices):
        raise ValueError("Invalid edge evidence index list")
    result = []
    for i in indices:
        if type(i) is not int or i < 0 or i >= len(proof):
            raise ValueError("Edge evidence index outside sealed array")
        ev = proof[i]
        if ev["source"] != source or ev["target"] != target:
            raise ValueError("Edge and evidence endpoints disagree")
        if layer == "L1":
            if ev.get("self_fact") is not False:
                raise ValueError("Self fact cannot justify edge")
        elif ev.get("status") != "projected":
            raise ValueError("Unprojected evidence on model edge")
        if layer == "L2" and ev["relation"] != relation:
            raise ValueError("State relation evidence differs")
        if layer == "L3" and ev["env_key"] != attrs.get("env_key"):
            raise ValueError("Environment evidence differs")
        result.append(ev)
    return result


# ----------------------------------------------------------------------
# node_sem/facts_state
# Precise support classification over frozen L2 evidence (no new edges).
#
# Diagnostics are retained by facts.py. This module controls uncertainty scope,
# recovers absent AST positions through the frozen binder, and exposes ALL sealed
# accesses for summaries, including those lacking an HCG endpoint.
GLOBALS = frozenset(("require assert revert throw keccak256 sha3 sha256 ripemd160 ecrecover "
    "addmod mulmod selfdestruct suicide now blockhash gasleft type abi msg tx block this super _").split())

PRIMITIVE = re.compile(r"address|payable|bool|string|byte|bytes[0-9]*|u?int[0-9]*|u?fixed([0-9]+x[0-9]+)?$")

def write_position(sem, node):
    cursor = node
    while cursor is not None:
        if cursor.type in ("assignment_expression", "augmented_assignment_expression"):
            target = cursor.child_by_field_name("left")
            # An index expression is read, not the overwritten storage root.
            root = target
            while root is not None and root.type in ("array_access", "member_expression"):
                root = root.child_by_field_name("base" if root.type == "array_access" else "object")
            return contains(root, node) or contains(node, target)
        if cursor.type == "update_expression" or operator(cursor) == "delete":
            return True
        if cursor.type == "call_expression":
            callee = cursor.child_by_field_name("function")
            if callee is not None and callee.type == "member_expression":
                prop = callee.child_by_field_name("property")
                if sem.text(prop) in ("push", "pop") and contains(callee.child_by_field_name("object"), node):
                    return True
        if cursor.type.endswith("_statement") or cursor.type in FUNCTIONS:
            break
        cursor = cursor.parent
    return False

def non_value_role(sem, node):
    if node is None: return None
    cursor = node
    while cursor.parent is not None:
        parent = cursor.parent
        if parent.type in ("type_name", "user_defined_type", "primitive_type", "type_alias", "new_expression"):
            return "type_role"
        if parent.child_by_field_name("type") == cursor and parent.type in (
                "parameter", "variable_declaration", "state_variable_declaration", "type_cast_expression"):
            return "type_role"
        if parent.type == "member_expression" and parent.child_by_field_name("property") == cursor:
            return "member_property"
        if parent.type == "modifier_invocation" and parent.child_by_field_name("name") == cursor:
            return "modifier_name"
        if parent.type == "call_expression":
            callee = parent.child_by_field_name("function")
            # Only a bare callee is excluded. target.method() still reads target.
            if callee == cursor and cursor.type == "identifier": return "direct_callee"
        if parent.type in ("emit_statement", "revert_statement"):
            if cursor.type == "identifier": return "event_or_error_name"
        if parent.type in ("variable_declaration", "parameter", "state_variable_declaration") and parent.child_by_field_name("name") == cursor:
            return "declaration_name"
        if parent.type.endswith("_statement") or parent.type in FUNCTIONS: break
        cursor = parent
    if node.type == "identifier":
        name = sem.text(node)
        binding = sem.resolve_identifier(node)
        if binding["kind"] in ("local", "param", "state"):
            return None
        if name in GLOBALS or PRIMITIVE.fullmatch(name): return "builtin_or_global"
    return None

class StateSupport:
    def __init__(self, sem, file, layers, nodes, graph, metadata=None, projector=None):
        self.sem, self.file = sem, file
        self.rec = (layers or {}).get("L2", {}).get("files", {}).get(file, {})
        self.available = bool(self.rec)
        self.by_key = {key(n): n for n in sem.nodes}
        self.functions = {file+":"+str(n.start_byte): n for n in sem.functions}
        self.events = []
        self.issues = []
        self.classifications = []
        self.recovered_positions = 0
        self.throw_rows = []
        self.mapped = {key(n) for n in nodes.values()} if graph is not None else set()
        self._recovery = None
        diagnostics = self.rec.get("diagnostics", [])
        for d in diagnostics:
            if not any(s in d.get("kind", "") for s in ("unresolved", "fallback")): continue
            found = self._located(d, metadata, projector)
            if not found:
                fn = self.functions.get(d.get("callable"))
                if fn is None and "fallback" in d.get("kind", ""):
                    for f in sem.functions: self._issue(f, True, "file_fallback")
                elif fn is not None:
                    self._issue(fn, True, "unlocated_diagnostic")
                self.classifications.append(dict(diagnostic=d, decision="unknown_unlocated"))
                continue
            for node in found:
                decision = self._classify(d, node)
                self.classifications.append(dict(diagnostic=d, location=list(key(node)), decision=decision))
        for ev in (layers or {}).get("L2", {}).get("evidence", []):
            if ev.get("file") != file: continue
            decl, stmt = self._identity(ev["state"]), self._identity(ev["statement"])
            if decl.type != "state_variable_declaration":
                raise ValueError("L2 summary declaration identity is not a state declaration")
            owner = context(stmt)
            if owner is None or ev.get("callable") != file+":"+str(owner.start_byte):
                raise ValueError("L2 summary callable identity differs")
            fn = self.functions.get(ev.get("callable"))
            writing = ev["relation"] == "WRITES_STATE"
            missing = (key(stmt) not in self.mapped or key(decl) not in self.mapped or
                       ev["status"] not in ("projected", "self_access_skipped"))
            self.events.append(dict(declaration=decl, statement=stmt, function=fn,
                writing=writing, missing=missing, evidence=ev))
            if missing and ev["status"] != "self_access_skipped":
                self._issue(stmt, writing, "unprojected_state_effect", {key(decl)})
        # Assembly is not guaranteed to appear in frozen L2's region inventory.
        for node in sem.nodes:
            if node.type != "assembly_statement": continue
            ops = {sem.text(n) for n in walk(node) if n.type == "yul_evm_builtin"}
            targets = {key(n) for n in self.scoped_states(node)}
            if ops & {"sstore", "delegatecall", "callcode"}:
                self._issue(node, True, "assembly_effect", targets)
            if "sload" in ops:
                self._issue(node, False, "assembly_effect", targets)

    def _identity(self, record):
        k = (record["start"], record["end"], record["role"])
        if record.get("file") != self.file or k not in self.by_key:
            raise ValueError("L2 summary evidence has no exact AST identity")
        node = self.by_key[k]
        if record.get("name") != (self.sem.text(node.child_by_field_name("name")) or node.type):
            raise ValueError("L2 summary declaration spelling identity differs")
        return node

    def _located(self, d, metadata, projector):
        k = (d.get("start"), d.get("end"), d.get("ast_type"))
        if k in self.by_key: return [self.by_key[k]]
        if d.get("kind") == "state_scope_fallback":
            fn = self.functions.get(d.get("callable"))
            return [fn] if fn is not None else []
        if self._recovery is None:
            binders, extractors = {}, {}
            for unit in iter_statement_regions(self.sem.view, projector):
                owner = context(unit.ast_node)
                if owner is None or not unit.regions: continue
                ident = self.file+":"+str(owner.start_byte)
                if ident not in binders:
                    binders[ident] = StateBinder(self.sem.view, owner, metadata)
                    extractors[ident] = StateAccessExtractor(binders[ident])
                extractors[ident].extract(unit.regions)
            self._recovery = [x for ident,b in binders.items()
                for x in b.diagnostics+extractors[ident].diagnostics]
        matches = [r for r in self._recovery if all(
            r.get(field) == d.get(field) for field in ("callable", "kind", "reason", "name") if field in d)]
        result = { (r.get("start"),r.get("end"),r.get("ast_type")) for r in matches }
        nodes = [self.by_key[k] for k in result if k in self.by_key]
        self.recovered_positions += len(nodes)
        return nodes

    def scoped_states(self, node):
        """Potential same-source declarations, NOT a new binding resolver.

        Keep a union on ambiguous inheritance; never choose an override.
        A missing external base adds no invented declaration identity.
        """
        contract = self.sem.contract(node)
        by_name = defaultdict(list)
        for c in self.sem.contracts:
            by_name[self.sem.text(c.child_by_field_name("name"))].append(c)
        pending, seen, result = [contract], set(), {}
        while pending:
            c = pending.pop()
            if c is None or key(c) in seen: continue
            seen.add(key(c))
            body = c.child_by_field_name("body")
            for d in (body.named_children if body is not None else []):
                if d.type == "state_variable_declaration": result[key(d)] = d
            for base in c.named_children:
                if base.type != "inheritance_specifier": continue
                ancestor = base.child_by_field_name("ancestor")
                name = self.sem.text(ancestor)
                if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name):
                    pending.extend(by_name.get(name, []))
        return list(result.values())

    def _reference_state(self, declaration):
        text = self.sem.text(declaration.child_by_field_name("type")).strip()
        if text.startswith("mapping") or "[" in text or text in ("string", "bytes"):
            return True
        if PRIMITIVE.fullmatch(text): return False
        # Confirmed contracts/enums are values. Unknown user types remain
        # potential references; do not turn lack of a type binding into safety.
        known_values = {self.sem.text(n.child_by_field_name("name"))
                        for n in self.sem.nodes
                        if n.type in ("contract_declaration", "interface_declaration",
                                      "library_declaration", "enum_declaration")}
        possible_structs = {self.sem.text(n.child_by_field_name("name"))
                            for n in self.sem.nodes if n.type == "struct_declaration"}
        return text in possible_structs or text not in known_values

    def _issue(self, node, writing, reason, targets=None):
        if targets is None:
            targets = {key(d) for d in self.scoped_states(node)}
        self.issues.append(dict(node=node, function=self.sem.owner(node),
            writing=bool(writing), reason=reason, targets=targets))

    def _classify(self, d, node):
        if d["kind"] == "state_scope_fallback":
            return "scope_fallback_context_only"
        if d["kind"] == "state_alias_unresolved":
            fn = self.functions.get(d.get("callable"))
            name = d.get("name")
            declarations = [n for n in self.sem.declarations if key(self.sem.owner(n)) == key(fn)
                            and self.sem.text(n.child_by_field_name("name")) == name]
            # Frozen alias diagnostics also include duplicate scalar locals.
            if declarations and all(shape(self.sem.text(n.child_by_field_name("type"))) in
                    ("integer", "bool", "address") for n in declarations):
                return "scalar_local_not_storage_alias"
            if declarations and all(any(self.sem.text(c) in ("memory", "calldata") for c in n.children)
                                    for n in declarations):
                return "non_storage_reference"
            occurrences = [n for n in walk(fn) if n.type == "identifier" and self.sem.text(n) == name
                           and non_value_role(self.sem, n) not in ("member_property", "direct_callee", "type_role")]
            if not occurrences: occurrences = [node]
            for n in occurrences:
                targets = {key(d) for d in self.scoped_states(n) if self._reference_state(d)}
                self._issue(n, write_position(self.sem, n), "unresolved_alias_use", targets)
            return "unresolved_alias_use"
        role = non_value_role(self.sem, node)
        if role: return role
        # An unsupported compound receiver can consist entirely of known
        # non-state values; do not guess that its result aliases storage.
        targets = None
        if node.type == "identifier":
            targets = {key(n) for n in self.scoped_states(node)
                       if self.sem.text(n.child_by_field_name("name")) == self.sem.text(node)}
        self._issue(node, write_position(self.sem, node), d.get("reason", "unresolved_access"), targets)
        return "uncertain_state_value"

    def own_issues(self, node):
        regions = self.sem.regions(node)
        return [i for i in self.issues if any(contains(r,i["node"]) or contains(i["node"],r)
                                            for r in regions if r is not None)]

    def function_issues(self, fn, writing=None):
        return [i for i in self.issues if key(i["function"]) == key(fn) and
                (writing is None or i["writing"] == writing)]

    def apply(self, rows, nodes):
        for nid, node in nodes.items():
            if not rows[nid]["state"]: continue
            fn = self.sem.owner(node)
            ident = self.file+":"+str(fn.start_byte) if fn is not None else None
            supported = ident in self.rec.get("callables", {}) and not self.own_issues(node)
            rows[nid]["state"]["status"] = "supported" if supported else "unknown"
            if supported:
                thrown = [self.by_key.get(tuple(c.get("location", ()))) for c in self.classifications
                          if c["decision"] == "builtin_or_global" and c["diagnostic"].get("name") == "throw"]
                if any(t is not None and any(contains(r,t) for r in self.sem.regions(node)) for t in thrown):
                    self.throw_rows.append(nid)

    def audit(self):
        return dict(classifications=self.classifications, recovered_positions=self.recovered_positions,
                    throw_supported_rows=self.throw_rows,
                    issues=[dict(location=list(key(i["node"])), function=list(key(i["function"])) if i["function"] is not None else None,
                                 writing=i["writing"],reason=i["reason"],
                                 targets=[list(k) for k in sorted(i["targets"])] if i["targets"] is not None else None)
                            for i in self.issues],
                    sealed_events=len(self.events), unprojected_events=sum(e["missing"] for e in self.events))
