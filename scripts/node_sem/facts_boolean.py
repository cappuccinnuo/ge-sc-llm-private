"""Bounded boolean repair using original AST tokens and declaration identities.

Frozen grammar can attach a member suffix across a boolean operator.
This adapter neither reparses source nor invents declarations or graph nodes.
"""
from .facts_ast import key


def tokens(sem, node):
    if "comment" in node.type: return []
    if not node.children or "literal" in node.type:
        return [(sem.text(node), node.start_byte, node.end_byte, node)]
    return [t for c in node.children for t in tokens(sem, c)]


def outer(ts):
    stack, result = [], []
    pairs = {")": "(", "]": "[", "}": "{"}
    for i, (text, _, _, _) in enumerate(ts):
        if text in ("(", "[", "{"): stack.append(text)
        elif text in pairs:
            if not stack or stack.pop() != pairs[text]: return None
        elif not stack: result.append(i)
    return result if not stack else None


def strip(ts):
    while len(ts) >= 2 and ts[0][0] == "(" and ts[-1][0] == ")":
        depth, end = 0, None
        for i, t in enumerate(ts):
            if t[0] == "(": depth += 1
            if t[0] == ")": depth -= 1
            if depth == 0:
                end = i
                break
        if end != len(ts) - 1: break
        ts = ts[1:-1]
    return ts


def sender_condition(analyzer, condition, polarity, bindings):
    """Return pairs, declarations, sender, disjunctive; None if out of scope."""
    sem = analyzer.sem
    original = tokens(sem, condition)
    ts = strip(original)
    top = outer(ts)
    if not ts or top is None or not (ts[0][0] == "!" or
            any(ts[i][0] in ("&&", "||") for i in top)):
        return None

    def exact(ts):
        ts = strip(ts)
        if not ts: return None
        matches = [n for n in sem.nodes if n.start_byte == ts[0][1] and n.end_byte == ts[-1][2]]
        return min(matches, key=lambda n: len(n.named_children)) if matches else None

    def sender(ts):
        ts = strip(ts)
        if [t[0] for t in ts] not in (["msg", ".", "sender"], ["tx", ".", "origin"]):
            n = exact(ts)
            if n is not None and n.type == "identifier":
                decl = sem.resolve_identifier(n).get("declaration")
                if decl is not None and key(decl) in bindings:
                    return sender(tokens(sem, bindings[key(decl)]))
            return False
        root = ts[0][3]
        return (sem.resolve_identifier(root)["kind"] == "unknown" and
                not sem.members(root).get(ts[0][0]))

    empty = (set(), set(), False, False)

    def parse(ts, sign):
        ts = strip(ts)
        top = outer(ts)
        if not ts or top is None: return empty
        if any(ts[i][0] in ("?", ":", "=", "+=", "-=") for i in top): return empty
        for op in ("||", "&&"):
            cuts = [i for i in top if ts[i][0] == op]
            if not cuts: continue
            spans = [-1] + cuts + [len(ts)]
            parts = [parse(ts[a+1:b], sign) for a, b in zip(spans, spans[1:])]
            disjunction = (op == "||") == (sign > 0)
            if disjunction and not all(p[2] for p in parts): return empty
            return (set().union(*(p[0] for p in parts)),
                    set().union(*(p[1] for p in parts)),
                    any(p[2] for p in parts), disjunction or any(p[3] for p in parts))
        if ts[0][0] == "!": return parse(ts[1:], -sign)
        cuts = [i for i in top if ts[i][0] in ("==", "!=", ">", "<", ">=", "<=")]
        if len(cuts) != 1: return empty
        i = cuts[0]
        if ts[i][0] != ("==" if sign > 0 else "!="): return empty
        left, right = ts[:i], ts[i+1:]
        if sender(left): operand = exact(right)
        elif sender(right): operand = exact(left)
        else:
            # Preserve valid non-sender equality categories in conjunctions
            # and negations (NS-P3a3 user-approved compatibility correction).
            atom = exact(ts)
            if atom is None: return empty
            pairs, _, _ = analyzer._ast_equalities(atom, sign, bindings)
            # A sender used as a mapping index is not the compared value.
            pairs.difference_update(("env_state", "env_param", "env_literal"))
            return pairs, set(), False, False
        if operand is None: return empty
        classes = analyzer._classes(operand, bindings)
        pairs, auth = set(), set()
        if not classes & {"hash", "external_result"}:
            for cls, pair in (("state", "env_state"), ("param", "env_param"), ("literal", "env_literal")):
                if cls in classes: pairs.add(pair)
            if "state" in classes: auth.update(analyzer._state_declarations(operand, bindings))
        return pairs, auth, True, False

    return parse(original, polarity)
