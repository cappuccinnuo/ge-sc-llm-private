"""Guard evidence: require/assert, if-branch early exits, modifiers and internal check
functions, with sender-identity comparisons (also disjunctive/conjunctive).
"""
from collections import Counter

from nodesem.facts.syntax import sender_condition

from dfg.analysis.frontend import walk
from dfg.analysis.ir import Unsupported
from dfg.analysis.state import ClosedScopeJ


# ----------------------------------------------------------------------
# node_sem/facts_guards
# Lexical guard evidence and bounded same-source call summaries.
#
# Only relations justified by declaration binding and AST containment are emitted.
# AST anchors and declaration keys prefixed with ``_`` are transient projection
# inputs, never part of serialized StatementFacts. No control-flow dominance is
# used to infer lexical guards.
BLOCKS = {"block_statement", "function_body"}

LOOPS = {"while_statement", "for_statement", "do_while_statement"}

FUNCTIONS = {"function_definition", "modifier_definition", "constructor_definition",
             "fallback_receive_definition"}

WRAPPERS = {"parenthesized_expression", "call_argument", "expression_statement"}

def key(node):
    return (node.start_byte, node.end_byte, node.type)

def children(node):
    return [c for c in node.named_children if "comment" not in c.type]

def unwrap(node):
    while node is not None and node.type in WRAPPERS and len(children(node)) == 1:
        node = children(node)[0]
    return node

def within(node, ancestor):
    return (node is not None and ancestor is not None and
            ancestor.start_byte <= node.start_byte and node.end_byte <= ancestor.end_byte)

def branches(node):
    # The frozen grammar uses two repeated body fields, not consequence/alternative.
    condition = node.child_by_field_name("condition")
    cs = [c for c in children(node) if c != condition]
    return condition, (cs[0] if cs else None), (cs[1] if len(cs) > 1 else None)

def arguments(call):
    return [unwrap(n) for n in children(call) if n.type == "call_argument"]

class GuardAnalyzer:
    def __init__(self, semantics):
        self.sem = semantics
        self.view = semantics.view
        self._cache = {}
        self._scopes = {}
        self._auth_cache = {}
        self._call_cache = {}
        self._modifier_cache = {}
        self.audit = Counter()

    def _scope(self, function):
        k = key(function)
        if k not in self._scopes:
            try:
                self._scopes[k] = ClosedScopeJ(self.view, function)
            except Unsupported:
                self._scopes[k] = None
        return self._scopes[k]

    def _builtin(self, call, names):
        return self.sem.builtin_call(call, set(names))

    def _require(self, statement):
        if statement.type != "expression_statement":
            return None
        call = unwrap(statement)
        if call.type != "call_expression" or not self._builtin(call, ("require", "assert")):
            return None
        args = arguments(call)
        return args[0] if args else None

    def _exits(self, statement):
        if statement is None:
            return False
        if statement.type in BLOCKS:
            cs = children(statement)
            return bool(cs) and self._exits(cs[-1])
        if statement.type in {"throw_statement", "return_statement"}:
            return True
        if statement.type == "revert_statement":
            # Revert syntax is not an ordinary same-spelling identifier call.
            return True
        call = unwrap(statement)
        if call.type == "identifier" and self.sem.text(call) == "throw":
            return True
        if call.type == "call_expression" and self._builtin(call, ("revert",)):
            return True
        condition = self._require(statement)
        return condition is not None and self.sem.text(unwrap(condition)) == "false"

    def _early(self, statement):
        if statement.type != "if_statement":
            return None
        condition, yes, no = branches(statement)
        return condition if no is None and self._exits(yes) else None

    def _substituted(self, expression, bindings):
        expression = unwrap(expression)
        if expression is not None and expression.type == "identifier":
            decl = self.sem.resolve_identifier(expression).get("declaration")
            if decl is not None and key(decl) in bindings:
                return bindings[key(decl)]
        return expression

    def _classes(self, expression, bindings):
        if expression is None:
            return set()
        expression = self._substituted(expression, bindings)
        result = set(self.sem.operand_classes(expression))
        mapped = []
        unmapped = set()
        for occurrence in walk(expression):
            if occurrence.type != "identifier":
                continue
            resolved = self.sem.resolve_identifier(occurrence)
            decl = resolved.get("declaration")
            kind = resolved.get("kind")
            if decl is not None and key(decl) in bindings:
                mapped.append((kind, bindings[key(decl)]))
            elif kind in {"state", "param", "local"}:
                unmapped.add(kind)
        for kind, actual in mapped:
            if kind not in unmapped:
                result.discard(kind)
            result.update(self.sem.operand_classes(actual))
        return result

    def _state_declarations(self, expression, bindings):
        expression = self._substituted(expression, bindings)
        result = set()
        for occurrence in walk(expression):
            if occurrence.type != "identifier":
                continue
            resolved = self.sem.resolve_identifier(occurrence)
            decl = resolved.get("declaration")
            if decl is not None and key(decl) in bindings:
                result.update(self._state_declarations(bindings[key(decl)], {}))
            elif resolved.get("kind") == "state" and decl is not None:
                result.add(key(decl))
        return result

    def _equalities(self, condition, polarity, bindings):
        adapted = sender_condition(self, condition, polarity, bindings) if condition is not None else None
        if adapted is not None:
            return adapted[:3]
        return self._ast_equalities(condition, polarity, bindings)

    def _ast_equalities(self, condition, polarity, bindings):
        """Original atomic/AST equality categories; boolean grouping is separate."""
        condition = unwrap(condition)
        if condition is None:
            return set(), set(), False
        if condition.type == "unary_expression":
            op = condition.child_by_field_name("operator")
            arg = condition.child_by_field_name("argument")
            if arg is None:
                cs = children(condition)
                arg = cs[-1] if cs else None
            if op is not None and self.sem.text(op) == "!":
                return self._equalities(arg, -polarity, bindings)
        comparison = condition
        hash_suffix = False
        if condition.type == "call_expression":
            callee = condition.child_by_field_name("function")
            # Frozen parser groups `state == sha3(argument)` as a call whose
            # callee is `state == sha3`. Only confirmed hash builtins are
            # repaired here; explicitly parenthesized computed calls are not.
            if (callee is not None and callee.type == "binary_expression" and
                    self._builtin(condition, ("sha3", "keccak256", "sha256", "ripemd160"))):
                comparison, hash_suffix = callee, True
        if comparison.type != "binary_expression":
            return set(), set(), False
        op = comparison.child_by_field_name("operator")
        left = comparison.child_by_field_name("left")
        right = condition if hash_suffix else comparison.child_by_field_name("right")
        operator = self.sem.text(op) if op is not None else ""
        if operator == "&&" and polarity == 1:
            a, b, sender = self._equalities(left, polarity, bindings)
            c, d, other = self._equalities(right, polarity, bindings)
            return a | c, b | d, sender or other
        # A false conjunction does not entail either conjunct. Disjunctions
        # are intentionally excluded in both polarities by the fixed policy.
        if operator not in {"==", "!="} or (operator == "==") != (polarity == 1):
            return set(), set(), False
        # The frozen grammar can attach a member suffix to a preceding
        # boolean expression. Never turn such a malformed grouping into an
        # equality claim. Explicitly grouped sibling conjunctions still recurse.
        for operand in ((left,) if hash_suffix else (left, right)):
            for nested in walk(operand):
                operator_node = nested.child_by_field_name("operator")
                if (nested.type == "binary_expression" and operator_node is not None
                        and self.sem.text(operator_node) in {"&&", "||", "==", "!="}):
                    return set(), set(), False
        a = self._classes(left, bindings)
        b = {"hash"} if hash_suffix else self._classes(right, bindings)
        # Compare expression results, not argument categories hidden inside
        # hashes or external calls. Inputs remain present in operand_classes.
        if "hash" in a:
            a = {"hash"}
        elif "external_result" in a:
            a = {"external_result"}
        if "hash" in b:
            b = {"hash"}
        elif "external_result" in b:
            b = {"external_result"}
        pairs = set()
        auth = set()
        sender = False
        for x, y, xnode, ynode in ((a, b, left, right), (b, a, right, left)):
            if x & {"msg.sender", "tx.origin"}:
                sender = True
                if "state" in y:
                    pairs.add("env_state")
                    auth.update(self._state_declarations(ynode, bindings))
                if "param" in y:
                    pairs.add("env_param")
                if "literal" in y:
                    pairs.add("env_literal")
            if "state" in x and "param" in y:
                pairs.add("state_param")
            if "hash" in x and y & {"state", "literal"}:
                pairs.add("hash_state_literal")
            if "timestamp" in x and y & {"state", "param"}:
                pairs.add("time_state_param")
        return pairs, auth, sender

    def _guard(self, rule, kind, polarity, condition, anchor, bindings=None):
        bindings = bindings or {}
        pairs, auth, sender = self._equalities(condition, polarity, bindings)
        # Loop conditions deliberately contribute no D1/D2 features.
        operands = self._classes(condition, bindings)
        adapted = sender_condition(self, condition, polarity, bindings)
        disjunctive = bool(adapted and adapted[3] and sender)
        if rule == "4":
            operands, pairs, auth, sender = set(), set(), set(), False
            disjunctive = False
        return {"rule": str(rule), "kind": kind, "polarity": polarity,
                "operand_classes": sorted(operands), "eq_pairs": sorted(pairs),
                "is_sender_guard": sender, "disjunctive": disjunctive, "offset": 0,
                "_anchor": anchor, "_auth_declarations": auth}

    def _bindings(self, declaration, call, extension=None):
        params = [n for n in children(declaration) if n.type == "parameter"]
        actuals = arguments(call)
        if extension is not None:
            actuals = [extension] + actuals
        if len(params) != len(actuals):
            return None
        return {key(p): a for p, a in zip(params, actuals)}

    def _internal(self, statement):
        call = unwrap(statement)
        if statement.type != "expression_statement" or call.type != "call_expression":
            return []
        callee = call.child_by_field_name("function")
        if callee is None or callee.type != "identifier":
            return []
        resolved = self.sem.resolve_callable(call)
        if resolved is None:
            return []
        vis = {self.sem.text(n) for n in children(resolved) if n.type == "visibility"}
        if not vis & {"internal", "private"}:
            return []
        bindings = self._bindings(resolved, call)
        body = resolved.child_by_field_name("body")
        if bindings is None or body is None:
            return []
        result = []
        for part in children(body):
            condition = self._require(part)
            polarity = 1
            if condition is None:
                condition = self._early(part)
                polarity = -1
            if condition is not None:
                result.append(self._guard("6", "internal_check", polarity, condition,
                                          statement, bindings))
        return result

    def _lexical(self, node, function, include_internal=True):
        result = []
        priority = []
        cursor = node
        depth = 0
        while cursor is not None and cursor != function:
            parent = cursor.parent
            if parent is None:
                break
            if parent.type in BLOCKS:
                prior = [n for n in children(parent) if n.end_byte <= cursor.start_byte]
                for distance, statement in enumerate(reversed(prior)):
                    condition = self._require(statement)
                    if condition is not None:
                        result.append(self._guard("1", "require", 1, condition, statement))
                        priority.append((0, depth, distance, statement.start_byte))
                    condition = self._early(statement)
                    if condition is not None:
                        result.append(self._guard("3", "early_exit", -1, condition, statement))
                        priority.append((0, depth, distance, statement.start_byte))
                    if include_internal:
                        for guard in self._internal(statement):
                            result.append(guard)
                            priority.append((1, depth, distance, statement.start_byte))
            if parent.type == "if_statement":
                condition, yes, no = branches(parent)
                polarity = 1 if within(node, yes) else (-1 if within(node, no) else None)
                if polarity is not None:
                    result.append(self._guard("2", "if_branch", polarity, condition, parent))
                    priority.append((0, depth, -1, parent.start_byte))
            if parent.type in LOOPS:
                body = parent.child_by_field_name("body")
                condition = parent.child_by_field_name("condition")
                if within(node, body) and condition is not None:
                    result.append(self._guard("4", "loop_cond", 1, condition, parent))
                    priority.append((0, depth, -1, parent.start_byte))
            cursor = parent
            depth += 1
        return result, priority

    def _modifiers(self, function):
        if key(function) in self._modifier_cache:
            return self._modifier_cache[key(function)]
        result, unresolved = [], Counter()
        invocations = [n for n in children(function) if n.type == "modifier_invocation"
            and not (self.sem.text(n) == "constant" and not self.sem.members(function).get("constant"))]
        if not invocations:
            return result, unresolved
        scope = self._scope(function)
        for invocation in invocations:
            cs = children(invocation)
            if scope is None or not cs or cs[0].type != "identifier":
                unresolved["modifier_binding_unresolved"] += 1
                self.audit["modifier_unresolved"] += 1
                continue
            ds = scope.declarations(self.sem.text(cs[0]))
            if len(ds) != 1 or ds[0].type != "modifier_definition":
                unresolved["modifier_binding_unresolved"] += 1
                self.audit["modifier_unresolved"] += 1
                continue
            modifier = ds[0]
            body = modifier.child_by_field_name("body")
            bindings = self._bindings(modifier, invocation)
            holes = [] if body is None else [n for n in walk(body)
                if n.type == "expression_statement" and unwrap(n).type == "identifier"
                and self.sem.text(unwrap(n)) == "_"]
            if not holes or bindings is None:
                unresolved["modifier_placeholder_or_arguments_unresolved"] += 1
                self.audit["modifier_unresolved"] += 1
                continue
            # First placeholder is the documented prefix anchor. A guard valid
            # only for that placeholder cannot be claimed for repeated bodies.
            if len(holes) != 1:
                unresolved["modifier_multiple_placeholders"] += 1
                self.audit["modifier_unresolved"] += 1
                continue
            self.audit["modifier_resolved"] += 1
            if scope.owner.get(modifier.start_byte) != scope.contract:
                self.audit["modifier_inherited"] += 1
            guards, _ = self._lexical(holes[0], modifier, include_internal=False)
            for guard in guards:
                if guard["rule"] not in {"1", "2", "3"}:
                    continue
                anchor = guard["_anchor"]
                condition = (anchor.child_by_field_name("condition") if anchor.type == "if_statement"
                             else self._require(anchor))
                rule = "5p" if guard["rule"] == "2" else "5"
                result.append(self._guard(rule, "modifier", guard["polarity"], condition,
                                          invocation, bindings))
        self._modifier_cache[key(function)] = (result, unresolved)
        return result, unresolved

    def self_condition(self, node):
        node = unwrap(node) if node.type != "expression_statement" else node
        condition = None
        if node.type in {"if_statement", "for_statement", "while_statement", "do_while_statement"}:
            condition = node.child_by_field_name("condition")
        elif node.type == "expression_statement":
            condition = self._require(node)
        elif node.type == "call_expression" and self._builtin(node, ("require", "assert")):
            args = arguments(node)
            condition = args[0] if args else None
        if condition is None:
            return None
        polarity = -1 if self._early(node) is not None else 1
        pairs, _, _ = self._equalities(condition, polarity, {})
        return {"operand_classes": sorted(self._classes(condition, {})),
                "eq_pairs": sorted(pairs), "early_exit_if": self._early(node) is not None}

    def for_node(self, node):
        ident = key(node)
        if ident in self._cache:
            return self._cache[ident]
        function = node if node.type in FUNCTIONS else self.sem.owner(node)
        if function is None:
            result = {"guards": [], "guard_status": "none", "nearest": None,
                      "self_condition": None, "unresolved": {}}
            self._cache[ident] = result
            return result
        guards, priority = self._lexical(node, function)
        modifiers, unresolved = self._modifiers(function)
        guards.extend(modifiers)
        priority.extend((2, 0, i, 0) for i in range(len(modifiers)))
        nearest = min(range(len(guards)), key=lambda i: priority[i]) if guards else None
        result = {"guards": guards, "guard_status": ("unknown" if unresolved else
                  "present" if guards else "none"), "nearest": nearest,
                  "self_condition": self.self_condition(node),
                  "unresolved": dict(unresolved)}
        self._cache[ident] = result
        return result

    def auth_declarations(self, contract):
        ident = key(contract)
        if ident in self._auth_cache:
            return self._auth_cache[ident]
        units = [n for n in self.sem.functions if self.sem.contract(n) == contract]
        chain = {ident}
        if units:
            scope = self._scope(units[0])
            if scope is not None:
                chain = {key(n) for n in scope.chain}
        result = set()
        for function in self.sem.functions:
            owner = self.sem.contract(function)
            if owner is None or key(owner) not in chain:
                continue
            body = function.child_by_field_name("body")
            if body is None:
                continue
            # Include guards even when there is no subsequent modeled statement.
            for node in walk(body):
                condition = self._require(node)
                polarity = 1
                if condition is None:
                    condition = self._early(node)
                    polarity = -1
                if condition is not None:
                    _, auth, sender = self._equalities(condition, polarity, {})
                    if sender:
                        result.update(auth)
                for guard in self.for_node(node)["guards"]:
                    if guard["rule"] in {"1", "3", "5", "5p", "6"}:
                        result.update(guard["_auth_declarations"])
        self._auth_cache[ident] = result
        return result

    def _extension(self, call):
        callee = call.child_by_field_name("function")
        if callee is None or callee.type != "member_expression":
            return None, None, False
        target = callee.child_by_field_name("object")
        prop = callee.child_by_field_name("property")
        if target is None or prop is None or target.type != "identifier":
            return None, None, False
        resolved = self.sem.resolve_identifier(target)
        type_name = resolved.get("type_name", "")
        if not type_name:
            return None, None, False
        function = self.sem.owner(call)
        scope = self._scope(function) if function is not None else None
        if scope is None:
            return None, None, True
        candidates, applicable = [], False
        for contract in scope.chain:
            body = contract.child_by_field_name("body")
            for directive in children(body):
                if directive.type != "using_directive":
                    continue
                typ = directive.child_by_field_name("source")
                # Exact scalar type matching only; aliases/structs/arrays unknown.
                normalize = lambda s: {"uint": "uint256", "int": "int256"}.get(s, s)
                if typ is not None and normalize(self.sem.text(typ)) != normalize(type_name):
                    continue
                applicable = True
                aliases = [n for n in children(directive) if n.type == "type_alias"]
                if len(aliases) != 1:
                    continue
                libraries = [n for n in self.sem.contracts if n.type == "library_declaration"
                    and self.sem.text(n.child_by_field_name("name")) == self.sem.text(aliases[0])]
                if len(libraries) != 1:
                    continue
                members = libraries[0].child_by_field_name("body")
                named = [n for n in children(members) if n.type == "function_definition"
                    and self.sem.text(n.child_by_field_name("name")) == self.sem.text(prop)]
                candidates.extend(named)
        if len(candidates) == 1:
            fn = candidates[0]
            bindings = self._bindings(fn, call, target)
            if bindings is not None:
                return fn, target, applicable
        return None, None, applicable

    def _unresolved_callable(self, call):
        callee = unwrap(call.child_by_field_name("function"))
        if callee is None:
            return False
        if callee.type == "identifier":
            candidates = self.sem.members(call).get(self.sem.text(callee), [])
            return any(n.type == "function_definition" for n in candidates)
        if callee.type == "member_expression":
            receiver = unwrap(callee.child_by_field_name("object"))
            resolved = self.sem.resolve_identifier(receiver)
            decl = resolved.get("declaration")
            return decl is not None and decl.type == "library_declaration"
        return False

    def _arithmetic(self, node):
        for expr in walk(node):
            if expr.type not in {"binary_expression", "augmented_assignment_expression", "update_expression"}:
                continue
            op = expr.child_by_field_name("operator")
            operators = [self.sem.text(op)] if op is not None else [self.sem.text(c) for c in expr.children if not c.is_named]
            if set(operators) & {"+", "-", "*", "/", "%", "**", "+=", "-=", "*=", "/=", "%=", "++", "--"}:
                return True
        return False

    def _result_checked(self, function):
        """One-level local scalar definition identity, killed by later writes.

        No inference passes through control branches or calls into another
        helper. The boolean says a computed result occurs in a guard condition;
        it is not a proof of overflow prevention or any security property.
        """
        active = set()
        body = function.child_by_field_name("body")
        if body is None:
            return False
        for statement in children(body):
            condition = self._require(statement)
            if condition is None:
                condition = self._early(statement)
            if condition is not None:
                if self._arithmetic(condition):
                    return True
                for occurrence in walk(condition):
                    if occurrence.type == "identifier":
                        decl = self.sem.resolve_identifier(occurrence).get("declaration")
                        if decl is not None and key(decl) in active:
                            return True
                continue
            if statement.type in {"if_statement", "for_statement", "while_statement", "do_while_statement", "assembly_statement"}:
                active.clear()
                continue
            if statement.type == "variable_declaration_statement":
                value = statement.child_by_field_name("value")
                declared = [n for n in children(statement) if n.type == "variable_declaration"]
                if len(declared) == 1 and value is not None and self._arithmetic(value):
                    active.add(key(declared[0]))
                continue
            expression = unwrap(statement)
            if expression.type in {"assignment_expression", "augmented_assignment_expression", "update_expression"}:
                left = expression.child_by_field_name("left")
                if left is None:
                    left = expression.child_by_field_name("argument")
                if left is None:
                    cs = children(expression)
                    left = cs[0] if cs else None
                if left is None or left.type != "identifier":
                    active.clear()
                    continue
                resolved = self.sem.resolve_identifier(left)
                declaration = resolved.get("declaration")
                if declaration is not None:
                    active.discard(key(declaration))
                    if resolved.get("kind") in {"local", "param"} and self._arithmetic(expression):
                        active.add(key(declaration))
            elif any(n.type == "call_expression" for n in walk(statement)):
                # Unknown helper side effects cannot justify retained evidence.
                active.clear()
        return False

    def checked_arithmetic(self, node):
        ident = key(node)
        if ident in self._call_cache:
            return self._call_cache[ident]
        arithmetic, guard, checked, unknown, found = False, False, False, False, False
        occurrences = walk(node) if node.type in FUNCTIONS else self.sem.owned_nodes(node)
        for call in occurrences:
            if call.type != "call_expression":
                continue
            fn = self.sem.resolve_callable(call)
            if fn is None:
                fn, _, applicable = self._extension(call)
                if fn is None:
                    unknown = unknown or applicable or self._unresolved_callable(call)
                    continue
            # This supplement follows only internal/private or a bound library
            # helper. A public internal call is outside the approved subset.
            owner = self.sem.contract(fn)
            vis = {self.sem.text(n) for n in children(fn) if n.type == "visibility"}
            if owner is None or (owner.type != "library_declaration" and not vis & {"internal", "private"}):
                continue
            body = fn.child_by_field_name("body")
            if body is None:
                unknown = True
                continue
            found = True
            local_arithmetic = self._arithmetic(body)
            local_guard = any(self._require(part) is not None or self._early(part) is not None
                              for part in children(body))
            arithmetic = arithmetic or local_arithmetic
            guard = guard or local_guard
            checked = checked or (local_arithmetic and local_guard and self._result_checked(fn))
        result = {"status": "unknown" if unknown else "supported" if found else "not_applicable",
                  "has_arithmetic": arithmetic, "has_guard": guard,
                  "result_condition_check": checked}
        self._call_cache[ident] = result
        return result
