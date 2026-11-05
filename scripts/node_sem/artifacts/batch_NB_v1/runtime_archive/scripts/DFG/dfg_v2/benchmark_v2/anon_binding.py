"""Prompt 8F: bounded declaration-based alpha conversion, never spelling replacement.

No labels, HCG, tokens, compiler downloads, or performance scores are read.
Unknown binding invalidates the whole file: no partial edits are committed.
Old-style constructor names alias their owning contract (user-approved).
This is a conservative source transformation, not a full Solidity type checker.
"""
import hashlib
import random
import re
from collections import Counter, defaultdict

from scripts.DFG.frontend import parse, walk
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.versioning import effective_interval, mode_for
from ..diagnostics8d.renaming import EXCLUDED_NAMES

VERSION = "prompt8f-declaration-anon-v1"
RESERVED = EXCLUDED_NAMES | frozenset(("gasprice", "solidity", "_"))
KEYWORD_STRINGS = ("tx.origin", "msg.sender", ".call.value(", ".send(", ".transfer(")
CONTAINERS = frozenset(("contract_declaration", "interface_declaration", "library_declaration"))
CALLABLES = frozenset(("function_definition", "modifier_definition", "constructor_definition",
                       "fallback_receive_definition"))
ROLES = {
    "contract_declaration": "contract", "interface_declaration": "interface",
    "library_declaration": "library", "function_definition": "function",
    "modifier_definition": "modifier", "event_definition": "event",
    "struct_declaration": "struct", "struct_member": "field",
    "enum_declaration": "enum", "enum_value": "enum_member",
    "state_variable_declaration": "state", "parameter": "parameter",
    "event_parameter": "parameter", "event_paramater": "parameter",
    "variable_declaration": "local", "error_declaration": "error",
}
TYPE_ROLES = frozenset(("contract", "interface", "library", "struct", "enum"))


def key(n):
    return (n.start_byte, n.end_byte, n.type)


def word(n):
    return n.text.decode("utf8")


def inside(parent, child):
    return parent.start_byte <= child.start_byte and child.end_byte <= parent.end_byte


def ancestor(n, kinds):
    n = n.parent
    while n is not None and n.type not in kinds:
        n = n.parent
    return n


def reserved(name):
    return name in RESERVED or bool(re.fullmatch(r"(?:u?fixed)[0-9]+x[0-9]+", name))


def shape(tree):
    return [(n.type, len(n.children), n.is_named, n.is_missing) for n in walk(tree.root_node)]


def replace_spans(source, edits):
    raw = source.encode("utf8")
    out, end = [], 0
    for e in sorted(edits, key=lambda x: x["start"]):
        a, b = e["start"], e["end"]
        if a < end or raw[a:b].decode("utf8") != e["old"]:
            raise ValueError("Overlapping/stale declaration-bound edit")
        out.extend((raw[end:a], e["new"].encode("utf8")))
        end = b
    out.append(raw[end:])
    return b"".join(out).decode("utf8")


class BindingError(ValueError):
    pass


class Resolver:
    def __init__(self, source, metadata=None):
        self.source = source
        self.tree = parse(source)
        self.nodes = list(walk(self.tree.root_node))
        if any(n.type == "ERROR" or n.is_missing for n in self.nodes):
            raise BindingError("grammar_error_or_missing")
        interval, self.version_evidence = effective_interval(source, self.tree.root_node, metadata)
        self.mode = mode_for(source, self.tree.root_node, interval)
        self.decls, self.by_span = {}, {}
        self.scope_symbols = defaultdict(lambda: defaultdict(list))
        self.cache, self.active = {}, set()
        self.issues = []
        for n in self.nodes:
            if n.type == "import_directive" or n.type.startswith("yul_"):
                self.issue(n, "unresolved_import_or_assembly")
            if n.type in ("type_name", "function_type") and any(c.type == "function" for c in n.children):
                self.issue(n, "function_type_binding_unsupported")
        self.collect()
        for symbols in self.scope_symbols.values():
            for name, ids in symbols.items():
                if len(ids) > 1 and not reserved(name):
                    self.issue(self.decls[ids[0]]["_node"], "duplicate_or_overloaded_scope:" + name)
        self.parents = {}
        for n in self.nodes:
            if n.type not in CONTAINERS:
                continue
            parents = []
            for base in n.named_children:
                if base.type != "inheritance_specifier":
                    continue
                target = base.child_by_field_name("ancestor")
                if target is None:
                    self.issue(base, "unknown_inheritance_shape")
                    continue
                candidates = self.scope_symbols[key(self.tree.root_node)].get(word(target), [])
                if len(candidates) != 1 or self.decls[candidates[0]]["role"] not in TYPE_ROLES:
                    self.issue(target, "unresolved_base_type")
                else:
                    parents.append(self.decls[candidates[0]]["_node"])
            self.parents[key(n)] = parents
        # Renaming overriding declarations independently would change dispatch.
        for n in self.nodes:
            if n.type not in CONTAINERS:
                continue
            try:
                chain = self.chain(n)
                names = defaultdict(list)
                for owner in chain:
                    for name, ids in self.scope_symbols[key(owner)].items():
                        if not reserved(name):
                            names[name].extend(ids)
                for name, ids in names.items():
                    if len(ids) > 1:
                        self.issue(n, "overload_override_or_hidden_member:" + name)
            except BindingError as exc:
                self.issue(n, str(exc))

    def issue(self, n, reason):
        self.issues.append(dict(start=n.start_byte, end=n.end_byte,
                                line=n.start_point[0]+1, name=word(n)[:160], reason=reason))

    def collect(self):
        # Containers are visited before their bodies by walk.
        for n in self.nodes:
            role = ROLES.get(n.type)
            name = n if n.type == "enum_value" else n.child_by_field_name("name")
            if role is None or name is None:
                continue
            if n.type != "enum_value" and name.type != "identifier":
                self.issue(n, "unrecognized_declaration_name")
                continue
            owner = ancestor(n, CONTAINERS)
            fn = ancestor(n, CALLABLES)
            if role == "function" and owner is not None:
                cn = owner.child_by_field_name("name")
                if cn is not None and word(cn) == word(name):
                    # The constructor name references the type, not a fresh name.
                    if self.mode != "legacy":
                        self.issue(n, "old_constructor_in_modern_scope")
                        continue
                    self.by_span[key(name)] = self.by_span[key(cn)]
                    continue
            if role in ("contract", "interface", "library"):
                scope = self.tree.root_node
            elif role in ("field", "enum_member"):
                scope = ancestor(n, frozenset(("struct_declaration", "enum_declaration")))
            elif role == "parameter":
                event = ancestor(n, frozenset(("event_definition", "error_declaration")))
                scope = event or fn
                if ancestor(n, frozenset(("return_type_definition",))) is not None:
                    role = "return"
            elif role == "local":
                if fn is None:
                    self.issue(n, "local_outside_callable")
                    continue
                scope = fn if self.mode == "legacy" else ancestor(
                    n, frozenset(("block_statement", "function_body", "for_statement")))
            else:
                scope = owner or self.tree.root_node
            if scope is None:
                self.issue(n, "declaration_without_supported_scope")
                continue
            ident = str(name.start_byte)
            visible = scope.start_byte
            if role == "local" and self.mode == "modern":
                stmt = ancestor(n, frozenset(("variable_declaration_statement",)))
                if stmt is None:
                    self.issue(n, "local_without_statement")
                    continue
                visible = stmt.end_byte
                value = stmt.child_by_field_name("value")
                if value is not None and any(x.type == "identifier" and word(x) == word(name)
                                             for x in walk(value)):
                    self.issue(n, "ambiguous_shadow_initializer")
            rec = dict(id=ident, name=word(name), role=role,
                       start=name.start_byte, end=name.end_byte,
                       declaration_start=n.start_byte, declaration_end=n.end_byte,
                       scope_start=scope.start_byte, scope_end=scope.end_byte,
                       visible=visible, preserved=reserved(word(name)),
                       _node=n, _scope=scope, _name=name, _owner=owner)
            self.decls[ident] = rec
            self.by_span[key(name)] = ident
            self.scope_symbols[key(scope)][word(name)].append(ident)

    def chain(self, owner, active=None):
        active = set() if active is None else active
        if key(owner) in active:
            raise BindingError("cyclic_inheritance")
        result = [owner]
        for parent in self.parents.get(key(owner), ()):
            for item in self.chain(parent, active | {key(owner)}):
                if key(item) not in {key(x) for x in result}:
                    result.append(item)
        return result

    def choose(self, ids, n):
        ids = list(dict.fromkeys(ids))
        if len(ids) != 1:
            raise BindingError("unresolved_or_ambiguous_binding:" + word(n))
        return ids[0]

    def lexical(self, n):
        text = word(n)
        fn = ancestor(n, CALLABLES)
        if fn is not None:
            local = [d for d in self.decls.values()
                     if d["name"] == text and d["role"] in ("parameter", "return", "local")
                     and inside(fn, d["_node"]) and inside(d["_scope"], n)
                     and n.start_byte >= d["visible"]]
            if local:
                width = min(d["scope_end"]-d["scope_start"] for d in local)
                return self.choose([d["id"] for d in local
                                    if d["scope_end"]-d["scope_start"] == width], n)
        owner = ancestor(n, CONTAINERS)
        if owner is not None:
            members = [i for c in self.chain(owner)
                       for i in self.scope_symbols[key(c)].get(text, ())]
            if members:
                return self.choose(members, n)
        return self.choose(self.scope_symbols[key(self.tree.root_node)].get(text, ()), n)

    def member(self, owner, name, at):
        if owner is None or owner[0] != "user":
            raise BindingError("unresolved_member_receiver:" + word(at))
        rec = self.decls[owner[1]]
        chain = self.chain(rec["_node"]) if rec["_node"].type in CONTAINERS else [rec["_node"]]
        ids = [i for c in chain for i in self.scope_symbols[key(c)].get(name, ())]
        return self.choose(ids, at)

    def type_node(self, n):
        if n is None:
            raise BindingError("missing_or_inferred_type")
        kids = [c for c in n.named_children if "comment" not in c.type]
        if n.type == "primitive_type":
            return ("primitive", re.sub(r"\buint\b", "uint256", re.sub(r"\bint\b", "int256", word(n))))
        if n.type in ("user_defined_type", "type_alias"):
            ids = [c for c in kids if c.type == "identifier"]
            if len(ids) == 1:
                ident = self.resolve(ids[0])
                if self.decls[ident]["role"] not in TYPE_ROLES:
                    raise BindingError("type_reference_bound_to_non_type")
                return ("user", ident)
            if len(ids) == 2:
                first = ("user", self.resolve(ids[0]))
                return ("user", self.member(first, word(ids[1]), ids[1]))
            raise BindingError("unresolved_qualified_type")
        if n.type == "type_name":
            if any(c.type == "[" for c in n.children):
                return ("array", self.type_node(next((c for c in kids if c.type == "type_name"), None)))
            val = n.child_by_field_name("value_type")
            if val is not None:
                return ("mapping", self.type_node(val))
            if len(kids) == 1:
                return self.type_node(kids[0])
        raise BindingError("unsupported_type_shape:" + n.type)

    def decl_type(self, ident):
        d = self.decls[ident]
        if d["role"] in TYPE_ROLES:
            return ("user", ident)
        return self.type_node(d["_node"].child_by_field_name("type"))

    def expr_type(self, n):
        if n is None:
            raise BindingError("missing_receiver")
        if n.type == "identifier":
            if word(n) in ("this", "super"):
                if word(n) == "super":
                    raise BindingError("super_dispatch_unresolved")
                owner = ancestor(n, CONTAINERS)
                return ("user", self.by_span[key(owner.child_by_field_name("name"))])
            if word(n) in ("now",):
                return ("primitive", "uint256")
            return self.decl_type(self.resolve(n))
        if n.type == "parenthesized_expression":
            return self.expr_type(n.named_children[0])
        if n.type == "number_literal":
            raise BindingError("literal_extension_type_unresolved")
        if n.type == "array_access":
            base = n.child_by_field_name("base") or n.named_children[0]
            t = self.expr_type(base)
            if t[0] in ("array", "mapping"):
                return t[1]
        if n.type == "member_expression":
            prop = n.child_by_field_name("property")
            if prop is not None and reserved(word(prop)):
                if word(prop) in ("sender", "origin", "coinbase"):
                    return ("primitive", "address")
                if word(prop) in ("balance", "length", "value", "timestamp", "number"):
                    return ("primitive", "uint256")
                raise BindingError("reserved_member_type_unresolved")
            return self.decl_type(self.resolve(prop))
        if n.type in ("type_cast_expression", "new_expression"):
            types = [c for c in n.named_children if c.type in ("type_name", "primitive_type", "user_defined_type")]
            if len(types) == 1:
                return self.type_node(types[0])
        if n.type == "call_expression":
            target = n.child_by_field_name("function")
            if target is not None and target.type == "identifier" and reserved(word(target)):
                if word(target) == "address":
                    return ("primitive", "address")
                raise BindingError("builtin_return_type_unresolved")
            ident = self.call_target(target)
            d = self.decls[ident]
            if d["role"] in TYPE_ROLES:
                return ("user", ident)
            ret = d["_node"].child_by_field_name("return_type")
            params = [] if ret is None else [x for x in ret.named_children if x.type == "parameter"]
            if len(params) == 1:
                return self.type_node(params[0].child_by_field_name("type"))
        raise BindingError("unresolved_expression_type:" + n.type)

    def call_target(self, n):
        if n is None:
            raise BindingError("missing_call_target")
        if n.type == "identifier":
            return self.resolve(n)
        if n.type == "member_expression":
            return self.resolve(n.child_by_field_name("property"))
        raise BindingError("computed_call_target")

    def extension(self, receiver, prop):
        owner = ancestor(prop, CONTAINERS)
        ids = []
        for c in self.chain(owner) if owner is not None else ():
            body = c.child_by_field_name("body")
            for directive in body.named_children:
                if directive.type != "using_directive":
                    continue
                alias = next((n for n in directive.named_children if n.type == "type_alias"), None)
                typ = directive.child_by_field_name("source")
                if alias is None or typ is None:
                    raise BindingError("wildcard_or_function_using_unresolved")
                if self.type_node(typ) != receiver:
                    continue
                lib = self.type_node(alias)
                try:
                    ident = self.member(lib, word(prop), prop)
                except BindingError:
                    continue
                args = [p for p in self.decls[ident]["_node"].named_children if p.type == "parameter"]
                if args and self.type_node(args[0].child_by_field_name("type")) == receiver:
                    ids.append(ident)
        return self.choose(ids, prop)

    def resolve(self, n):
        if n is None:
            raise BindingError("missing_identifier")
        k = key(n)
        if k in self.cache:
            return self.cache[k]
        if k in self.by_span:
            return self.by_span[k]
        if k in self.active:
            raise BindingError("recursive_type_resolution")
        self.active.add(k)
        try:
            parent = n.parent
            if parent.type == "member_expression" and key(n) == key(parent.child_by_field_name("property")):
                typ = self.expr_type(parent.child_by_field_name("object"))
                try:
                    ident = self.member(typ, word(n), n)
                except BindingError:
                    ident = self.extension(typ, n)
            elif parent.type == "call_struct_argument" and parent.named_children[0] == n:
                call = ancestor(n, frozenset(("call_expression",)))
                ident = self.call_target(call.child_by_field_name("function") if call else None)
                d = self.decls[ident]
                if d["role"] == "struct":
                    ident = self.member(("user", ident), word(n), n)
                else:
                    ident = self.choose(self.scope_symbols[key(d["_node"])].get(word(n), ()), n)
            elif parent.type == "user_defined_type" and len(parent.named_children) > 1 and n != parent.named_children[0]:
                base = self.resolve(parent.named_children[0])
                ident = self.member(("user", base), word(n), n)
            else:
                ident = self.lexical(n)
            self.cache[k] = ident
            return ident
        finally:
            self.active.discard(k)

    def bindings(self):
        bindings = []
        preserved_counts = Counter()
        for n in self.nodes:
            if n.type not in ("identifier", "enum_value"):
                continue
            # pragma strings/keywords are not program references.
            if ancestor(n, frozenset(("pragma_directive",))) is not None:
                continue
            if reserved(word(n)):
                preserved_counts[word(n)] += 1
                continue
            if ancestor(n, frozenset(("yul_identifier",))) is not None:
                continue
            try:
                ident = self.resolve(n)
                bindings.append(dict(start=n.start_byte, end=n.end_byte,
                                     old=word(n), declaration=ident))
            except BindingError as exc:
                self.issue(n, str(exc))
        return bindings, dict(preserved_counts)


def anonymize(source, metadata=None):
    """Return an auditable whole-file decision. Failed files are exact identity."""
    digest = hashlib.sha256(source.encode("utf8")).hexdigest()
    try:
        resolver = Resolver(source, metadata)
        bindings, preserved_counts = resolver.bindings()
    except (BindingError, Unsupported) as exc:
        return dict(version=VERSION, source_sha256=digest, status="fallback",
                    issues=[dict(reason=str(exc))], declarations=[], bindings=[],
                    edits=[], rewritten=source, changed=False,
                    compilation_verified=False)
    declarations = [{k: v for k, v in d.items() if not k.startswith("_")}
                    for d in resolver.decls.values()]
    common = dict(version=VERSION, source_sha256=digest, declarations=declarations,
                  preserved_counts=preserved_counts, version_evidence=resolver.version_evidence,
                  scope_mode=resolver.mode, compilation_verified=False)
    if resolver.issues:
        return dict(common, status="fallback", issues=resolver.issues,
                    bindings=[], edits=[], rewritten=source, changed=False)
    eligible = sorted((d for d in declarations if not d["preserved"]), key=lambda d: d["start"])
    forbidden = {word(n) for n in resolver.nodes if n.type in ("identifier", "enum_value")}
    numbers, i = [], 0
    while len(numbers) < len(eligible):
        if "v" + str(i) not in forbidden:
            numbers.append(i)
        i += 1
    seed = int(hashlib.sha256((VERSION + ":" + digest).encode()).hexdigest(), 16)
    random.Random(seed).shuffle(numbers)
    names = {d["id"]: "v" + str(num) for d, num in zip(eligible, numbers)}
    edits = [dict(b, new=names[b["declaration"]]) for b in bindings]
    rewritten = replace_spans(source, edits)
    after = parse(rewritten)
    if shape(after) != shape(resolver.tree) or any(n.type == "ERROR" or n.is_missing for n in walk(after.root_node)):
        raise BindingError("Renamed AST topology differs")
    counts = {s: source.count(s) for s in KEYWORD_STRINGS}
    if counts != {s: rewritten.count(s) for s in KEYWORD_STRINGS}:
        raise BindingError("Reserved keyword substring count differs")
    # Every edit comes from a bound identifier leaf. Comments/literals untouched.
    return dict(common, status="renamed", issues=[], bindings=bindings, edits=edits,
                names=names, seed=str(seed), rewritten=rewritten, changed=bool(edits),
                rewritten_sha256=hashlib.sha256(rewritten.encode()).hexdigest(),
                ast_topology_identical=True, keyword_counts=counts)
