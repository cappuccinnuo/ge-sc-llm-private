"""Closed same-source inheritance. C3 validates hierarchy, never guesses overrides."""
import re
from ...frontend import text
from ...models import Unsupported
from ...call_binding import CONTAINERS
from ..stage_f.binding import ClosedScope

def merge(sequences):
    sequences = [list(x) for x in sequences if x]
    result = []
    while sequences:
        candidate = next((s[0] for s in sequences
                          if not any(s[0] in t[1:] for t in sequences)), None)
        if candidate is None:
            raise Unsupported("J: inconsistent C3 inheritance")
        result.append(candidate)
        sequences = [s[1:] if s[0] == candidate else s for s in sequences]
        sequences = [s for s in sequences if s]
    return result

class ClosedScopeJ(ClosedScope):
    def __init__(self, view, function):
        self.view = view
        c = function.parent
        while c is not None and c.type not in CONTAINERS:
            c = c.parent
        if c is None:
            raise Unsupported("J: callable outside contract")
        if any(n.type == "import_directive" for n in view.tree.root_node.named_children):
            raise Unsupported("J: unresolved imports")
        units = {}
        for n in view.tree.root_node.named_children:
            if n.type in CONTAINERS:
                name = n.child_by_field_name("name")
                if name is not None:
                    units.setdefault(text(view.source, name), []).append(n)
        self.contract = c
        by_id, memo, active = {}, {}, set()
        def linearize(node):
            ident = node.start_byte
            by_id[ident] = node
            if ident in active:
                raise Unsupported("J: cyclic inheritance")
            if ident in memo:
                return memo[ident]
            if node.type == "library_declaration" and node is not self.contract:
                raise Unsupported("J: library is not an inheritance base")
            active.add(ident)
            bases = []
            for base in node.named_children:
                if base.type != "inheritance_specifier":
                    continue
                ancestor = base.child_by_field_name("ancestor")
                children = [x for x in base.named_children if "comment" not in x.type]
                if ancestor is None or len(children) != 1:
                    raise Unsupported("J: base constructor arguments unsupported")
                name = text(view.source, ancestor)
                if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name) or len(units.get(name, [])) != 1:
                    raise Unsupported("J: base declaration not unique in source")
                bases.append(units[name][0])
            if len({x.start_byte for x in bases}) != len(bases):
                raise Unsupported("J: duplicate direct base")
            # Solidity gives rightmost direct bases precedence.
            direct = list(reversed(bases))
            result = [ident] + merge([linearize(x) for x in direct] +
                                    [[x.start_byte for x in direct]])
            active.remove(ident)
            memo[ident] = result
            return result
        self.chain = [by_id[i] for i in linearize(c)]
        self.members, self.hidden, self.owner = {}, {}, {}
        for depth, owner in enumerate(self.chain):
            body = owner.child_by_field_name("body")
            if body is None:
                raise Unsupported("J: missing ancestor body")
            for node in body.named_children:
                if owner.type == "interface_declaration":
                    if node.type == "state_variable_declaration" or (
                        node.type == "function_definition" and node.child_by_field_name("body") is not None):
                        raise Unsupported("J: interface with executable body/storage")
                name = node.child_by_field_name("name")
                if name is None:
                    continue
                name = text(view.source, name)
                self.owner[node.start_byte] = owner
                private = any(x.type == "visibility" and text(view.source, x) == "private"
                              for x in node.named_children)
                (self.hidden if depth and private else self.members).setdefault(name, []).append(node)
        self.evidence = {
            "scope": "closed same-source hierarchy; lexical declaration identity",
            "source_sha256": view.sha256,
            "chain": [{"name": text(view.source, x.child_by_field_name("name")),
                       "kind": x.type, "start": x.start_byte, "end": x.end_byte}
                      for x in self.chain],
            "linearization": "Solidity rightmost-first C3, checked for consistency",
            "dispatch": "no override/overload selection or interprocedural summaries",
            "import_resolution": "none present",
        }
