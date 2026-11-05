"""Restricted explicit-control CFG, independent of the frozen model CFG.

Calls whose declaration is known are opaque may-return/may-revert operations.
Only explicit if/require/assert nodes can become control sources. Implicit VM
exceptions (gas exhaustion, bounds, arithmetic) are outside this explicit-control
profile. Loops, try/assembly, unresolved callees, effectful short circuit and
interprocedural divergence are not resolved; unsupported syntax falls back.
"""
import re
from types import SimpleNamespace
from ..frontend import text, walk, span
from ..models import Unsupported
from ..call_binding import BUILTIN, NON_BUILTIN, UNKNOWN
from ..semantic_cfg import _if_bodies
from ..symbol_table import SymbolTable
from ..state.stage_j.binding import ClosedScopeJ
from ..state.stage_j.modifiers import prefix_modifier
from ..state.stage_f.binding import StageFCallResolver
from ..state.stage_f.versioning import available
from .models import ControlIR, ControlNode, VERSION


def children(node):
    return [n for n in node.named_children if "comment" not in n.type]


def contains(outer, node):
    return outer.start_byte <= node.start_byte and node.end_byte <= outer.end_byte


def literal_boolean(node, source):
    """Only syntactic true/false, optionally wrapped; no symbolic evaluation."""
    while node is not None and node.type in ("call_argument", "parenthesized_expression"):
        nested = children(node)
        if len(nested) != 1:
            return None
        node = nested[0]
    if node is not None and node.type == "boolean_literal":
        value = text(source, node)
        if value in ("true", "false"):
            return value == "true"
    return None


class DeclarationBindings:
    """Collect lexical declarations solely to disprove builtin binding.

    Unlike the scalar DDG table this accepts reference/function parameter types;
    it does not infer data-flow, types of expressions, or variable definitions.
    The existing Stage F resolver decides whether a resolved callee is usable.
    """
    def __init__(self, view, function):
        self.view, self.function, self.mode = view, function, view.mode
        self.function_id = view.file + ":" + str(function.start_byte)
        self._body = function.child_by_field_name("body")
        self.bindings = {}
        if self._body is None:
            raise Unsupported("guard: callable has no body")
        for child in function.named_children:
            if child.type == "parameter":
                self.add(child, self._body, self._body.start_byte)
        returns = function.child_by_field_name("return_type")
        if returns is not None:
            for child in children(returns):
                if child.type == "parameter":
                    self.add(child, self._body, self._body.start_byte)
        for node in walk(self._body):
            if node.type == "variable_declaration":
                statement = SymbolTable._statement(self, node)
                scope = self._body if self.mode == "legacy" else SymbolTable._local_scope(self, statement)
                visible = self._body.start_byte if self.mode == "legacy" else statement.end_byte
                if self.mode == "modern":
                    SymbolTable._check_initializer_reference(self, node, statement)
                self.add(node, scope, visible)

    def add(self, node, scope, visible):
        name = node.child_by_field_name("name")
        if name is None:
            return
        name = text(self.view.source, name)
        if any((s.start_byte, s.end_byte) == (scope.start_byte, scope.end_byte)
               for s, _, _ in self.bindings.get(name, [])):
            raise Unsupported("guard: duplicate lexical declaration: " + name)
        typ = node.child_by_field_name("type")
        symbol = SimpleNamespace(id=self.function_id + ":" + str(node.start_byte) + ":" + name,
            declaration=span(self.view.file, node),
            type_name=text(self.view.source, typ) if typ else "", node=node)
        self.bindings.setdefault(name, []).append((scope, visible, symbol))

    def resolve(self, name, node):
        if not contains(self.function, node):
            return None
        candidates = [(s.end_byte - s.start_byte, sym) for s, visible, sym in self.bindings.get(name, [])
                      if contains(s, node) and visible <= node.start_byte]
        candidates.sort(key=lambda x: x[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise Unsupported("guard: ambiguous lexical declaration: " + name)
        return candidates[0][1] if candidates else None


class ControlCFGBuilder:
    def __init__(self, view, function):
        self.view, self.function = view, function
        self.function_id = view.file + ":" + str(function.start_byte)
        self.scope = ClosedScopeJ(view, function)
        self.table = DeclarationBindings(view, function)
        self.resolver = StageFCallResolver(view, function, self.table, self.scope)
        self.prefix, self.modifier = prefix_modifier(view, function, self.scope)
        self.modifier_resolver = None
        if self.modifier:
            declaration = self.modifier["declaration"]
            modifier = next(n for n in walk(view.tree.root_node)
                            if n.type == "modifier_definition" and n.start_byte == declaration["start"]
                            and n.end_byte == declaration["end"])
            table = DeclarationBindings(view, modifier)
            self.modifier_resolver = StageFCallResolver(view, modifier, table, self.scope)
        self.nodes, self.call_diagnostics = {}, []
        self.exit = self.new("unified_exit")
        self.normal_exit = self.new("normal_exit", targets={self.exit: "exit"})
        self.exceptional_exit = self.new("exceptional_exit", targets={self.exit: "exit"})

    def resolver_for(self, node):
        if self.modifier_resolver and contains(self.modifier_resolver.function, node):
            return self.modifier_resolver
        return self.resolver

    def new(self, kind, node=None, targets=None, evidence=None):
        ident = self.function_id + ":control:" + str(len(self.nodes))
        self.nodes[ident] = ControlNode(ident, kind, span(self.view.file, node) if node else None,
                                       targets or {}, evidence or {})
        return ident

    def binding(self, name, callee, form="identifier_call"):
        resolver = self.resolver_for(callee)
        decision = resolver._unqualified(name, callee, form)
        diagnostic = resolver.diagnostic(callee, decision)
        diagnostic["function"] = self.function_id
        self.call_diagnostics.append(diagnostic)
        if decision.classification == UNKNOWN:
            raise Unsupported("guard: uncertain call binding: " + name + ": " + decision.reason)
        return decision

    def unshadowed(self, name, node):
        resolver = self.resolver_for(node)
        return (resolver.table.resolve(name, node) is None and name not in self.scope.members
                and name not in self.scope.hidden
                and not resolver._declarations(self.view.tree.root_node.named_children, name))

    def address_receiver(self, node):
        if node is None:
            return False
        if node.type == "identifier":
            name = text(self.view.source, node)
            local = self.resolver_for(node).table.resolve(name, node)
            if local is not None:
                return local.type_name in ("address", "address payable")
            declarations = self.scope.require_unambiguous(name)
            if len(declarations) == 1 and declarations[0].type == "state_variable_declaration":
                typ = declarations[0].child_by_field_name("type")
                return typ is not None and text(self.view.source, typ) in ("address", "address payable")
            return (name == "this" and self.view.version_interval[1] <= (0, 5, 0)
                    and self.unshadowed(name, node))
        if node.type == "member_expression":
            obj, prop = node.child_by_field_name("object"), node.child_by_field_name("property")
            if obj is not None and prop is not None and obj.type == "identifier":
                base, name = text(self.view.source, obj), text(self.view.source, prop)
                return ((base, name) in (("msg", "sender"), ("tx", "origin"), ("block", "coinbase"))
                        and self.unshadowed(base, obj))
        if node.type == "type_cast_expression":
            named = children(node)
            return bool(named and named[0].type in ("primitive_type", "type_name")
                        and text(self.view.source, named[0]) in ("address", "address payable"))
        return False

    def call_parts(self, node):
        fn = node.child_by_field_name("function")
        arguments = [c for c in children(node) if c.type in ("call_argument", "call_struct_argument")]
        options = []
        while fn is not None and fn.type == "call_expression":
            opt = fn.child_by_field_name("function")
            prop = opt.child_by_field_name("property") if opt and opt.type == "member_expression" else None
            if prop is None or text(self.view.source, prop) not in ("value", "gas"):
                raise Unsupported("guard: computed call target")
            options.append(text(self.view.source, prop))
            arguments.extend(c for c in children(fn) if c.type in ("call_argument", "call_struct_argument"))
            fn = opt.child_by_field_name("object")
        if fn is None:
            raise Unsupported("guard: call has no target")
        return fn, arguments, options

    def call_effect(self, node, predicate=False):
        fn, args, options = self.call_parts(node)
        if any(n.type == "call_expression" for a in args for n in walk(a)):
            raise Unsupported("guard: nested argument calls require expression CFG")
        for arg in args:
            self.validate_expression(arg, predicate=True)
        if fn.type == "identifier":
            name = text(self.view.source, fn)
            decision = self.binding(name, fn)
            if decision.classification == BUILTIN:
                # Guards and terminal calls are only handled as complete statements.
                raise Unsupported("guard: nested builtin control call: " + name)
            if predicate:
                raise Unsupported("guard: user call in predicate requires expression CFG")
            return "may_revert", {"binding": decision.reason, "name": name,
                "semantics": "known declaration; opaque may-return/may-revert; no body summary"}
        if fn.type == "member_expression":
            recv, prop = fn.child_by_field_name("object"), fn.child_by_field_name("property")
            method = text(self.view.source, prop) if prop is not None else ""
            if method in ("value", "gas") and recv is not None and recv.type == "member_expression":
                op = recv.child_by_field_name("property")
                address = recv.child_by_field_name("object")
                if op is not None and text(self.view.source, op) == "call" and self.address_receiver(address):
                    return "normal", {"semantics": "call configuration only; no external invocation"}
            if method not in ("call", "send", "transfer", "staticcall") or not self.address_receiver(recv):
                raise Unsupported("guard: unresolved member call: " + method)
            if not available(self.view, method):
                raise Unsupported("guard: address operation unavailable over version interval: " + method)
            if method == "transfer" and predicate:
                raise Unsupported("guard: transfer in predicate is outside supported syntax")
            return ("may_revert" if method == "transfer" else "normal"), {
                "binding": "address receiver and version confirmed", "method": method,
                "options": options, "semantics": "callee failure reverts" if method == "transfer"
                    else "callee failure returned as success flag; implicit VM exceptions outside profile"}
        raise Unsupported("guard: unsupported computed/member call")

    def validate_expression(self, node, predicate=False):
        if node is None:
            return []
        effects = []
        for n in walk(node):
            if n.type in ("assembly_statement", "try_statement", "new_expression"):
                raise Unsupported("guard: unsupported expression control: " + n.type)
            if predicate and n.type in ("assignment_expression", "augmented_assignment_expression", "update_expression"):
                raise Unsupported("guard: predicate write requires expression CFG")
            if n.type == "ternary_expression" or (n.type == "binary_expression" and
                    any(c.type in ("&&", "||") for c in n.children)):
                if any(c.type in ("call_expression", "assignment_expression", "augmented_assignment_expression", "update_expression")
                       for c in walk(n)):
                    raise Unsupported("guard: effectful short circuit/ternary requires expression CFG")
        def visit(n):
            if n.type == "call_expression":
                effects.append(self.call_effect(n, predicate))
                return
            for child in children(n):
                visit(child)
        visit(node)
        if len(effects) > 1:
            raise Unsupported("guard: multiple calls require expression evaluation order")
        return effects

    def expression_entry(self, node, following, kind="statement"):
        effects = self.validate_expression(node)
        ident = self.new(kind, node, {following: "normal"})
        if any(effect == "may_revert" for effect, _ in effects):
            # Atomic statement anchor is executed before its return/failure outcome;
            # the virtual decision is never a model control-source node.
            decision = self.new("opaque_call_outcome", targets={following: "normal", self.exceptional_exit: "exception"},
                                evidence={"effects": [e for _, e in effects]})
            self.nodes[ident].successors = {decision: "evaluate"}
        self.nodes[ident].evidence["effects"] = [e for _, e in effects]
        return ident

    def sequence(self, statements, following):
        head = following
        for statement in reversed(statements):
            if "comment" not in statement.type:
                head = self.statement(statement, head)
        return head

    def statement(self, node, following):
        kind = node.type
        if kind in ("function_body", "block_statement"):
            return self.sequence(children(node), following)
        if kind == "if_statement":
            then_body, else_body = _if_bodies(node)
            condition = node.child_by_field_name("condition")
            effects = self.validate_expression(condition, predicate=True)
            left = self.statement(then_body, following)
            right = self.statement(else_body, following) if else_body is not None else following
            constant = literal_boolean(condition, self.view.source)
            if constant is not None:
                targets = {left if constant else right: "true" if constant else "false"}
            elif left == right:
                targets = {left: "both"}
            else:
                targets = {left: "true", right: "false"}
            return self.new("if", node, targets, {"predicate": span(self.view.file, condition).__dict__,
                                                     "effects": [e for _, e in effects]})
        if kind in ("while_statement", "for_statement", "do_while_statement", "break_statement", "continue_statement",
                    "try_statement", "assembly_statement", "unchecked_block"):
            raise Unsupported("guard: unsupported control flow: " + kind)
        if kind == "return_statement":
            return self.expression_entry(node, self.normal_exit, "return")
        if kind == "revert_statement":
            decision = self.resolver_for(node).classify(node)
            if decision is None or decision.classification == UNKNOWN:
                raise Unsupported("guard: revert binding/custom error unresolved")
            self.call_diagnostics.append(self.resolver_for(node).diagnostic(node, decision))
            if decision.classification == NON_BUILTIN:
                self.validate_expression(node, predicate=True)
                if any(n.type == "call_expression" for n in walk(node)):
                    raise Unsupported("guard: nested non-builtin revert argument call")
                ident = self.new("statement", node)
                outcome = self.new("opaque_call_outcome", targets={following: "normal", self.exceptional_exit: "exception"})
                self.nodes[ident].successors = {outcome: "evaluate"}
                return ident
            self.validate_expression(node, predicate=True)
            return self.new("revert", node, {self.exceptional_exit: "revert"})
        if kind == "expression_statement":
            direct = children(node)
            if len(direct) == 1 and direct[0].type == "identifier" and text(self.view.source, direct[0]) == "throw":
                if self.view.mode != "legacy":
                    raise Unsupported("guard: throw outside legacy scope")
                return self.new("revert", node, {self.exceptional_exit: "throw"})
            call = direct[0] if len(direct) == 1 and direct[0].type == "call_expression" else None
            callee = call.child_by_field_name("function") if call else None
            if callee is not None and callee.type == "identifier":
                name = text(self.view.source, callee)
                if name in ("require", "assert", "selfdestruct", "suicide", "revert"):
                    decision = self.binding(name, callee)
                    if decision.classification == BUILTIN:
                        _, arguments, options = self.call_parts(call)
                        if options:
                            raise Unsupported("guard: options on builtin control call")
                        for arg in arguments:
                            self.validate_expression(arg, predicate=True)
                        if any(n.type == "call_expression" for a in arguments for n in walk(a)):
                            raise Unsupported("guard: call in builtin argument requires expression CFG")
                        if name in ("require", "assert"):
                            if len(arguments) not in ((1, 2) if name == "require" else (1,)):
                                raise Unsupported("guard: unsupported builtin argument count")
                            constant = literal_boolean(arguments[0], self.view.source)
                            targets = ({following: "pass"} if constant is True else
                                       {self.exceptional_exit: "fail"} if constant is False else
                                       {following: "pass", self.exceptional_exit: "fail"})
                            return self.new("guard", node, targets,
                                {"name": name, "binding": decision.evidence, "reason": decision.reason,
                                 "literal_boolean": constant})
                        destination = self.exceptional_exit if name == "revert" else self.normal_exit
                        return self.new("terminal", node, {destination: name}, {"binding": decision.evidence})
        if kind not in ("variable_declaration_statement", "expression_statement", "emit_statement"):
            raise Unsupported("guard: unsupported statement: " + kind)
        return self.expression_entry(node, following)

    def build(self):
        head = self.statement(self.function.child_by_field_name("body"), self.normal_exit)
        head = self.sequence(self.prefix, head)
        entry = self.new("entry", targets={head: "enter"})
        reachable, todo = set(), [entry]
        while todo:
            current = todo.pop()
            if current in reachable:
                continue
            reachable.add(current)
            todo.extend(self.nodes[current].successors)
        # Keep typed exits explicit even if one is unreachable; analysis only uses reachable nodes.
        retained = reachable | {self.exit, self.normal_exit, self.exceptional_exit}
        self.nodes = {k: n for k, n in self.nodes.items() if k in retained}
        return ControlIR(self.function_id, self.view.file, self.view.sha256, entry,
            self.normal_exit, self.exceptional_exit, self.exit, self.nodes,
            {"version": VERSION, "scope": self.scope.evidence, "modifier": self.modifier,
             "version_evidence": self.view.version_evidence, "calls": self.call_diagnostics,
             "semantic_profile": "explicit guards/branches/exits; bound ordinary calls may-return/may-revert",
             "excluded": ["implicit VM exceptions", "loops and divergence", "unresolved calls", "interprocedural summaries"],
             "predicate_approximation": "only true/false literals folded; other conditions path-insensitive",
             "compiled": False})
