"""Source-only AST semantics (declarations, operators, bindings) and bounded boolean
repair of conditions, using original token spellings only internally.
"""
import re
from types import SimpleNamespace

from dfg.analysis.frontend import scope_mode
from dfg.analysis.ir import Unsupported
from dfg.analysis.state import ClosedScopeJ
from dfg.graph.env import EnvExtractor


# ----------------------------------------------------------------------
# node_sem/facts_ast
# Source-only AST semantics. Declaration identity stays internal.
#
# Parsing is not compilation. No graph label, target or prediction is read.
FUNCTIONS = frozenset(("function_definition", "constructor_definition", "modifier_definition", "fallback_receive_definition"))

CONTRACTS = frozenset(("contract_declaration", "library_declaration", "interface_declaration"))

LOOPS = frozenset(("for_statement", "while_statement", "do_while_statement"))

ARITH = frozenset(("+", "-", "*", "/", "%", "**"))

HASHES = frozenset(("keccak256", "sha3", "sha256", "ripemd160"))

def key(node):
    return None if node is None else (node.start_byte, node.end_byte, node.type)

def walk(node):
    if node is not None:
        yield node
        for child in node.named_children:
            if "comment" not in child.type:
                yield from walk(child)

def contains(outer, inner):
    return outer is not None and inner is not None and outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte

def unwrap(node):
    while node is not None and node.type in ("parenthesized_expression", "call_argument", "expression_statement"):
        children = [x for x in node.named_children if "comment" not in x.type]
        if len(children) != 1: break
        node = children[0]
    return node

def operator(node):
    named = node.child_by_field_name("operator")
    if named is not None: return named.text.decode("utf8")
    return next((x.type for x in node.children if not x.is_named and x.type in ARITH | {"=", "+=", "-=", "*=", "/=", "%=", "++", "--", "delete"}), "")

def shape(type_name):
    name = " ".join(type_name.split())
    if name.startswith("mapping"): return "mapping"
    if "[" in name: return "array"
    if name.startswith("address"): return "address"
    if re.fullmatch(r"u?int[0-9]*", name): return "integer"
    if name == "bool": return "bool"
    if re.fullmatch(r"bytes[0-9]*|string", name): return "bytes_string"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*", name): return "struct_contract"
    return "other"

class AstSemantics:
    def __init__(self, view, original_names=None):
        self.view = view
        self.original_names = original_names or {}
        self.nodes = list(walk(view.tree.root_node))
        self.functions = [x for x in self.nodes if x.type in FUNCTIONS]
        self.contracts = [x for x in self.nodes if x.type in CONTRACTS]
        self._scopes, self._resolve_cache, self._env_cache, self._calls_cache = {}, {}, {}, {}
        self.diagnostics = {}
        try: self.mode = scope_mode(view.source, view.tree.root_node)
        except Unsupported: self.mode = None
        self.has_import = any(x.type == "import_directive" for x in view.tree.root_node.named_children)
        self.declarations = [x for x in self.nodes if x.type in ("variable_declaration", "parameter", "state_variable_declaration")]

    def text(self, node):
        return "" if node is None else self.view.raw[node.start_byte:node.end_byte].decode("utf8")

    def owner(self, node):
        while node is not None:
            if node.type in FUNCTIONS: return node
            node = node.parent
        return None

    def contract(self, node):
        while node is not None:
            if node.type in CONTRACTS: return node
            node = node.parent
        return None

    def scope(self, node):
        fn = self.owner(node)
        if fn is None:
            contract = self.contract(node)
            fn = next((f for f in self.functions if key(self.contract(f)) == key(contract)), None)
        if fn is None: return None
        ident = key(fn)
        if ident not in self._scopes:
            try: self._scopes[ident] = ClosedScopeJ(self.view, fn)
            except Unsupported: self._scopes[ident] = None
        return self._scopes[ident]

    def members(self, node):
        scope = self.scope(node)
        if scope is not None: return scope.members
        contract = self.contract(node)
        body = contract.child_by_field_name("body") if contract is not None else None
        result = {}
        if body is not None:
            for child in body.named_children:
                name = child.child_by_field_name("name")
                if name is not None: result.setdefault(self.text(name), []).append(child)
        return result

    @staticmethod
    def _local_block(decl):
        cursor = decl.parent
        while cursor is not None:
            if cursor.type in ("function_body", "block_statement", "for_statement"): return cursor
            cursor = cursor.parent
        return None

    def _binding(self, decl, kind):
        return {"kind": kind, "declaration": decl, "name": self.text(decl.child_by_field_name("name")), "type_name": self.text(decl.child_by_field_name("type"))}

    def resolve_identifier(self, node):
        if node is None or node.type != "identifier":
            return {"kind": "unknown", "declaration": None, "name": self.text(node), "type_name": ""}
        ident = key(node)
        if ident not in self._resolve_cache: self._resolve_cache[ident] = self._resolve(node)
        return self._resolve_cache[ident]

    def _resolve(self, node):
        name = self.text(node)
        unknown = {"kind": "unknown", "declaration": None, "name": name, "type_name": ""}
        parent = node.parent
        if parent is not None and parent.type == "member_expression" and key(parent.child_by_field_name("property")) == key(node): return unknown
        fn = self.owner(node)
        candidates = []
        if fn is not None:
            for decl in self.declarations:
                if key(self.owner(decl)) != key(fn) or self.text(decl.child_by_field_name("name")) != name: continue
                if decl.type == "parameter":
                    candidates.append((fn.end_byte-fn.start_byte, self._binding(decl, "param")))
                    continue
                if decl.type != "variable_declaration": continue
                scope = self._local_block(decl)
                lexical = contains(scope, node) and decl.end_byte <= node.start_byte
                legacy = contains(fn, node)
                if self.mode is None and lexical != legacy: return unknown
                visible = legacy if self.mode == "legacy" else lexical
                if visible or key(decl.child_by_field_name("name")) == key(node):
                    candidates.append((scope.end_byte-scope.start_byte if scope is not None else 0, self._binding(decl, "local")))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                if len(candidates) > 1 and candidates[0][0] == candidates[1][0]: return unknown
                return candidates[0][1]
        members = self.members(node).get(name, [])
        if len(members) == 1:
            decl = members[0]
            if decl.type == "state_variable_declaration": return self._binding(decl, "state")
            if decl.type in FUNCTIONS: return self._binding(decl, "function")
        contracts = [x for x in self.contracts if self.text(x.child_by_field_name("name")) == name]
        if len(contracts) == 1: return self._binding(contracts[0], "contract")
        return unknown

    def root_binding(self, node):
        node = unwrap(node)
        while node is not None and node.type in ("array_access", "member_expression"):
            node = unwrap(node.child_by_field_name("base" if node.type == "array_access" else "object"))
        return self.resolve_identifier(node)

    def identifiers(self, node):
        for child in walk(node):
            if child.type == "identifier":
                parent = child.parent
                if parent is not None and (key(parent.child_by_field_name("name")) == key(child) or (parent.type == "member_expression" and key(parent.child_by_field_name("property")) == key(child))): continue
                yield child

    def builtin_call(self, node, names):
        callee = self._postfix(node.child_by_field_name("function")) if node is not None and node.type == "call_expression" else None
        if callee is None or callee.type != "identifier" or self.text(callee) not in names: return False
        name = self.text(callee)
        if any(self.text(f.child_by_field_name("name")) == name for f in self.functions): return False
        if self.resolve_identifier(callee)["kind"] != "unknown" or self.has_import: return False
        contract = self.contract(node)
        if contract is not None and any(x.type == "inheritance_specifier" for x in contract.named_children) and self.scope(node) is None: return False
        return True

    def resolve_callable(self, call):
        callee = unwrap(call.child_by_field_name("function"))
        if callee is None: return None
        if callee.type == "identifier":
            binding = self.resolve_identifier(callee)
            if binding["kind"] != "function" or self.scope(call) is None: return None
            rows = self.members(call).get(self.text(callee), [])
            if len(rows) != 1 or key(rows[0]) != key(binding["declaration"]): return None
        elif callee.type == "member_expression":
            receiver = unwrap(callee.child_by_field_name("object"))
            name = self.text(callee.child_by_field_name("property"))
            library = self.resolve_identifier(receiver).get("declaration")
            if library is None or library.type != "library_declaration":
                return self._using_callable(call, receiver, name)
            rows = [x for x in library.child_by_field_name("body").named_children if self.text(x.child_by_field_name("name")) == name]
        else: return None
        return rows[0] if len(rows) == 1 and rows[0].type == "function_definition" else None

    @staticmethod
    def _canonical_type(value):
        value=re.sub(r"\b(memory|storage|calldata|payable)\b", "", value)
        value=re.sub(r"\buint\b", "uint256", value)
        value=re.sub(r"\bint\b", "int256", value)
        return "".join(value.split())

    def _using_callable(self, call, receiver, method):
        # Only a unique same-source library declaration and receiver-compatible
        # first parameter establish a library extension. No overload guessing.
        scope=self.scope(call)
        if scope is None:return None
        binding=self.root_binding(receiver)
        receiver_type=self._canonical_type(binding["type_name"])
        if not receiver_type:return None
        if receiver.type not in ("identifier","array_access"):return None
        if receiver.type=="array_access":
            if not receiver_type.endswith("]"):return None
            receiver_type=receiver_type[:receiver_type.rfind("[")]
        matches=[]
        for contract in scope.chain:
            body=contract.child_by_field_name("body")
            for directive in body.named_children:
                if directive.type!="using_directive":continue
                source=directive.child_by_field_name("source")
                if source is not None and self._canonical_type(self.text(source))!=receiver_type:continue
                alias=next((x for x in directive.named_children if x.type=="type_alias"),None)
                if alias is None:continue
                libs=[x for x in self.contracts if x.type=="library_declaration" and self.text(x.child_by_field_name("name"))==self.text(alias)]
                if len(libs)!=1:continue
                functions=[x for x in libs[0].child_by_field_name("body").named_children if x.type=="function_definition" and self.text(x.child_by_field_name("name"))==method]
                if len(functions)!=1:continue
                fn=functions[0]
                params=[x for x in fn.named_children if x.type=="parameter"]
                if len(params)!=len(self.arguments(call))+1 or self._canonical_type(self.text(params[0].child_by_field_name("type")))!=receiver_type:continue
                matches.append(fn)
        unique={key(fn):fn for fn in matches}
        return next(iter(unique.values())) if len(unique)==1 else None

    def regions(self, node):
        if node is None: return []
        if node.type in ("if_statement", "while_statement", "do_while_statement"): return [node.child_by_field_name("condition")]
        if node.type == "for_statement": return [node.child_by_field_name(x) for x in ("initial", "condition", "update") if node.child_by_field_name(x) is not None]
        if node.type in FUNCTIONS or node.type in CONTRACTS: return []
        if node.type == "state_variable_declaration": return [node.child_by_field_name("value")]
        return [node]

    def owned_nodes(self, node):
        return [item for region in self.regions(node) for item in walk(region)]

    def env_occurrences(self, node):
        ident = key(node)
        if ident not in self._env_cache:
            fn = self.owner(node)
            locals_ = {self.text(x.child_by_field_name("name")): x for x in self.declarations if key(self.owner(x)) == key(fn) and x.type != "state_variable_declaration"}
            binder = SimpleNamespace(view=self.view, locals=locals_, members=self.members(node), callable_id="node_sem_ast")
            self._env_cache[ident] = EnvExtractor(binder).extract(self.regions(node))
        return self._env_cache[ident]

    def env_keys(self, node):
        return set() if node is None else {x.key for x in self.env_occurrences(node)}

    def _postfix(self, node):
        while node is not None and node.type in ("unary_expression", "binary_expression"):
            child = node.child_by_field_name("argument" if node.type == "unary_expression" else "right")
            if child is None or child.end_byte != node.end_byte: return node
            node = child
        return node

    @staticmethod
    def arguments(call):
        return [unwrap(x) for x in call.named_children if x.type == "call_argument"]

    def _call(self, call):
        callee = self._postfix(call.child_by_field_name("function"))
        value, args, invoked = None, self.arguments(call), True
        while callee is not None:
            if callee.type == "struct_expression":
                for item in callee.named_children:
                    if item.type in ("struct_field_assignment", "call_struct_argument") and self.text(item.child_by_field_name("name")) == "value": value = item.child_by_field_name("value")
                callee = callee.child_by_field_name("type")
                continue
            if callee.type == "call_expression":
                nested = self._postfix(callee.child_by_field_name("function"))
                if nested is not None and nested.type == "member_expression" and self.text(nested.child_by_field_name("property")) in ("value", "gas"):
                    if self.text(nested.child_by_field_name("property")) == "value":
                        values = self.arguments(callee)
                        value = values[0] if values else None
                    callee = nested.child_by_field_name("object")
                    continue
            break
        if callee is None: return None
        if callee.type == "member_expression" and self.text(callee.child_by_field_name("property")) in ("value", "gas"):
            option, base = self.text(callee.child_by_field_name("property")), callee.child_by_field_name("object")
            if base is not None and base.type in ("member_expression", "call_expression"):
                if option == "value": value = args[0] if args else None
                callee, invoked = base, False
                while callee is not None and callee.type == "call_expression":
                    fn = callee.child_by_field_name("function")
                    callee = fn.child_by_field_name("object") if fn is not None else None
                if callee is None: return None
        kind, target = None, None
        if callee.type == "new_expression": kind = "new"
        elif callee.type == "identifier" and self.builtin_call(call, ("selfdestruct", "suicide")):
            kind, target = "selfdestruct", args[0] if args else None
        elif callee.type == "member_expression":
            resolved=self.resolve_callable(call)
            if resolved is not None and self.contract(resolved).type=="library_declaration":return None
            target = unwrap(callee.child_by_field_name("object"))
            method, root = self.text(callee.child_by_field_name("property")), self.root_binding(target)
            library = root.get("declaration")
            if library is not None and library.type == "library_declaration": return None
            if method in ("push", "pop") and "[" in root["type_name"]: return None
            if self.text(target) in ("this", "super", "msg", "tx", "block", "abi"): return None
            known_contract = shape(root["type_name"]) == "struct_contract"
            if method in ("call", "delegatecall", "callcode", "staticcall", "send", "transfer") and not known_contract:
                kind = "delegatecall" if method == "callcode" else method
                if method in ("send", "transfer"): value = args[0] if args else None
            else: kind = "member"
        if kind is None or (not invoked and kind != "call"): return None
        return {"node":call,"kind":kind,"target":target,"value":value,"args":args,"invoked":invoked}

    def calls(self, node):
        ident = key(node)
        if ident in self._calls_cache: return self._calls_cache[ident]
        rows = []
        for call in self.owned_nodes(node):
            if call.type != "call_expression": continue
            parent = call.parent
            if parent is not None and parent.type == "call_expression" and key(parent.child_by_field_name("function")) == key(call): continue
            if parent is not None and parent.type == "member_expression" and key(parent.child_by_field_name("object")) == key(call) and self.text(parent.child_by_field_name("property")) in ("value", "gas"): continue
            row = self._call(call)
            if row is not None: rows.append(row)
        self._calls_cache[ident] = rows
        return rows

    def operand_classes(self, node):
        if node is None: return set()
        result = set()
        for name in self.env_keys(node):
            result.add({"msg.sender":"msg.sender","tx.origin":"tx.origin","msg.value":"msg.value","block.timestamp":"timestamp","block.number":"timestamp","this.balance":"balance"}.get(name,"block" if name.startswith("block") else ""))
        result.discard("")
        for ident in (x for region in self.regions(node) for x in self.identifiers(region)):
            kind = self.resolve_identifier(ident)["kind"]
            if kind in ("state", "param", "local"): result.add(kind)
        for item in self.owned_nodes(node):
            if "literal" in item.type: result.add("literal")
            if item.type == "member_expression" and self.text(item.child_by_field_name("property")) == "balance": result.add("balance")
            if item.type == "call_expression" and self.builtin_call(item, HASHES): result.add("hash")
        if any(x["invoked"] for x in self.calls(node)): result.add("external_result")
        return result

    classes = operand_classes

    def target_classes(self, node):
        result = self.operand_classes(node) & {"msg.sender","tx.origin","param","state","local","literal"}
        if self.text(unwrap(node)) == "this": result.add("this")
        if node is not None and node.type=="type_cast_expression":
            children=node.named_children
            if children and self.text(children[0]) in ("address","payable") and any(self.text(unwrap(c))=="this" for c in children[1:]):result.add("this")
        binding=self.root_binding(node)
        decl=binding.get("declaration")
        if binding["kind"]=="state" and decl is not None and any(self.text(c) in ("constant","immutable") for c in decl.children):
            result.discard("state")
            result.add("literal")
        return sorted(result or {"other"})

    def value_class(self, node):
        if node is None: return "none"
        if any(operator(x) in ARITH for x in walk(node)): return "arith"
        classes, result = self.operand_classes(node), "unknown"
        for kind in ("literal","param","local","state","msg.value","balance"):
            if kind in classes: result = "this.balance" if kind == "balance" and "this.balance" in self.env_keys(node) else kind
        return result if result != "balance" else "unknown"

    def _assignment_target(self, node):
        cursor = node
        while cursor is not None and cursor.type not in FUNCTIONS:
            if cursor.type in ("assignment_expression","augmented_assignment_expression") and contains(cursor.child_by_field_name("right"),node): return cursor,cursor.child_by_field_name("left")
            if cursor.type == "variable_declaration_statement": return cursor,None
            cursor = cursor.parent
        return None,None

    def return_handling(self, call):
        cursor = call.parent
        while cursor is not None and cursor.type not in FUNCTIONS:
            if cursor.type == "call_expression":
                if self.builtin_call(cursor,("require","assert")): return "checked_in_require"
                return "unknown"
            if cursor.type in ("return_statement","emit_statement"): return "unknown"
            if cursor.type in ("if_statement","while_statement","for_statement") and contains(cursor.child_by_field_name("condition"),call): return "checked_in_if"
            if cursor.type in ("expression_statement","variable_declaration_statement"): break
            cursor = cursor.parent
        assignment,target = self._assignment_target(call)
        if assignment is None: return "ignored"
        declarations = ([x for x in walk(assignment) if x.type == "variable_declaration"] if target is None else [self.resolve_identifier(x)["declaration"] for x in self.identifiers(target)])
        live = {key(x) for x in declarations if x is not None}
        if not live: return "assigned_unchecked"
        block = assignment.parent
        while block is not None and block.type not in ("function_body","block_statement"): block=block.parent
        if block is None: return "assigned_unchecked"
        for statement in block.named_children:
            if statement.start_byte <= assignment.start_byte: continue
            condition = statement.child_by_field_name("condition")
            expr = unwrap(statement)
            if expr is not None and expr.type == "call_expression" and self.builtin_call(expr,("require","assert")):
                args=self.arguments(expr)
                condition=args[0] if args else None
            condition_writes=set()
            for item in walk(condition):
                if item.type in ("assignment_expression","augmented_assignment_expression","update_expression"):
                    left=item.child_by_field_name("left") or item.child_by_field_name("argument")
                    condition_writes.update(key(self.resolve_identifier(x)["declaration"]) for x in self.identifiers(left))
            if condition is not None and not condition_writes & live and any(key(self.resolve_identifier(x)["declaration"]) in live for x in self.identifiers(condition)): return "assigned_checked"
            for item in walk(statement):
                if item.type in ("assignment_expression","augmented_assignment_expression","update_expression"):
                    left=item.child_by_field_name("left") or item.child_by_field_name("argument")
                    live -= {key(self.resolve_identifier(x)["declaration"]) for x in self.identifiers(left)}
            if not live: break
        return "assigned_unchecked"

    def function_context(self,node):
        fn=self.owner(node)
        if fn is None:return {}
        contract=self.contract(fn)
        fn_name=self.text(fn.child_by_field_name("name"))
        contract_name=self.text(contract.child_by_field_name("name")) if contract is not None else ""
        words={self.text(x) for x in fn.children if x.type in ("visibility","state_mutability","payable")}
        legacy_constant = any(x.type=="modifier_invocation" and self.text(x)=="constant" and not self.members(fn).get("constant") for x in fn.named_children)
        if legacy_constant: words.add("constant")
        return {"visibility":next((x for x in ("public","external","internal","private") if x in words),"default"),"payable":"payable" in words,"read_only":bool(words & {"view","pure","constant"}),"is_constructor":fn.type=="constructor_definition" or bool(fn_name and fn_name==contract_name),"is_fallback":fn.type=="fallback_receive_definition" or (fn.type=="function_definition" and not fn_name),"has_modifier":any(x.type=="modifier_invocation" and not (legacy_constant and self.text(x)=="constant") for x in fn.named_children),"name_case_only_differs_from_contract":bool(fn_name and contract_name and self.original_names.get(fn_name,fn_name) != self.original_names.get(contract_name,contract_name) and self.original_names.get(fn_name,fn_name).lower()==self.original_names.get(contract_name,contract_name).lower())}

    def loop_bound(self,node):
        cursor=node
        while cursor is not None and cursor.type not in FUNCTIONS:
            if cursor.type in LOOPS and contains(cursor.child_by_field_name("body"),node):
                condition=cursor.child_by_field_name("condition")
                classes=self.operand_classes(condition)
                if "state" in classes or any(x.type=="member_expression" and self.text(x.child_by_field_name("property"))=="length" for x in walk(condition)):return "state"
                condition=unwrap(condition)
                bound=condition.child_by_field_name("right") if condition is not None else None
                bound_classes=self.operand_classes(bound)
                if bound_classes and bound_classes <= {"literal"}:return "constant"
                if classes & {"param","local"}:return "param_local"
                return "unknown"
            cursor=cursor.parent
        return "none"

    def syntax(self,node):
        result=set()
        for item in self.owned_nodes(node):
            op=operator(item)
            if item.type=="assignment_expression":result.add("assign")
            if item.type=="augmented_assignment_expression":result.add({"+=":"add_assign","-=":"sub_assign"}.get(op,"compound_assign"))
            if op=="delete":result.add("delete")
            for ast,name in (("emit_statement","emit"),("ternary_expression","ternary"),("conditional_expression","ternary"),("array_access","index"),("return_statement","return")):
                if item.type==ast:result.add(name)
            if "literal" in item.type:result.add("literal")
            if "assembly" in item.type:result.add("assembly")
            if item.type in ("throw_statement","revert_statement"):result.add("exit")
            if item.type=="expression_statement" and self.text(unwrap(item))=="throw" and self.resolve_identifier(unwrap(item))["kind"]=="unknown":result.add("exit")
            if item.type=="member_expression" and item.child_by_field_name("object").type=="member_expression" and self.text(item.child_by_field_name("property")) not in ("value","gas"):result.add("deep_member")
            if item.type=="call_expression":
                if self.builtin_call(item,HASHES):result.add("hash")
                if self.builtin_call(item,("ecrecover",)):result.add("ecrecover")
                if self.builtin_call(item,("revert",)):result.add("exit")
                if self.builtin_call(item,("require",)) and self.arguments(item) and self.text(self.arguments(item)[0])=="false":result.add("exit")
                callee=item.child_by_field_name("function")
                if callee is not None and callee.type=="member_expression" and self.text(callee.child_by_field_name("object"))=="abi" and self.text(callee.child_by_field_name("property")).startswith("encode"):result.add("abi_encode")
        return sorted(result)

    def sink(self,node,symbol_name):
        # Sealed Symbol identity takes priority over spelling. The string form
        # remains useful for source-only exploratory tests, never edge joins.
        symbol = symbol_name if hasattr(symbol_name,"declaration") else None
        name = symbol.name if symbol is not None else symbol_name
        matches=[]
        for region in self.regions(node):
            for ident in self.identifiers(region):
                if self.text(ident) != name: continue
                binding=self.resolve_identifier(ident)
                declaration=binding["declaration"]
                if symbol is not None and (declaration is None or declaration.start_byte!=symbol.declaration.start or declaration.end_byte!=symbol.declaration.end):continue
                matches.append(ident)
        if not matches:return "other"
        for call in self.calls(node):
            if any(contains(call["target"],x) for x in matches):return "call_target"
            if any(contains(call["value"],x) for x in matches):return "call_value"
            if any(contains(arg,x) for arg in call["args"] for x in matches):return "call_arg"
        for item in self.owned_nodes(node):
            if item.type=="call_expression" and self.builtin_call(item,("require","assert")):return "guard"
        if node.type in ("if_statement","while_statement","for_statement"):return "loop_bound" if node.type in LOOPS else "guard"
        for item in self.owned_nodes(node):
            if item.type in ("assignment_expression","augmented_assignment_expression") and self.root_binding(item.child_by_field_name("left"))["kind"]=="state":return "state_write"
            if item.type=="call_expression" and self.builtin_call(item,HASHES):return "hash_input"
            if item.type=="array_access" and any(contains(item.child_by_field_name("index"),x) for x in matches):return "array_index"
        if node.type=="return_statement":return "return"
        if any(operator(x) in ARITH for x in self.owned_nodes(node)):return "arith"
        return "other"

    sink_for = sink
    shape = staticmethod(shape)

    def array_size_change(self,node):
        for item in self.owned_nodes(node):
            if item.type=="call_expression":
                callee=item.child_by_field_name("function")
                if callee is not None and callee.type=="member_expression" and self.text(callee.child_by_field_name("property")) in ("push","pop"):
                    binding=self.root_binding(callee.child_by_field_name("object"))
                    if binding["kind"]=="state" and "[" in binding["type_name"]:return True
            if item.type in ("assignment_expression","augmented_assignment_expression"):
                left=item.child_by_field_name("left")
                if left is not None and left.type=="member_expression" and self.text(left.child_by_field_name("property"))=="length":
                    binding=self.root_binding(left.child_by_field_name("object"))
                    if binding["kind"]=="state" and "[" in binding["type_name"]:return True
            if item.type=="unary_expression" and operator(item)=="delete":
                arg=unwrap(item.child_by_field_name("argument"))
                binding=self.root_binding(arg)
                if arg is not None and arg.type=="identifier" and binding["kind"]=="state" and "[" in binding["type_name"]:return True
        return False

    def base_facts(self,node,node_kind="statement"):
        if node_kind in ("env","end","other","contract"):return {}
        if node_kind in ("function","modifier"):return {"function_ctx":self.function_context(node)}
        items=self.owned_nodes(node)
        calls=self.calls(node)
        active=[x for x in calls if x["invoked"]]
        env=sorted(self.env_keys(node))
        op_nodes=[x for x in items if operator(x).rstrip("=") in ARITH]
        classes=set().union(*(self.operand_classes(x) for x in op_nodes)) if op_nodes else set()
        syntax=self.syntax(node)
        ops=sorted({operator(x).rstrip("=") for x in items if operator(x).rstrip("=") in ARITH})
        uses,sinks=set(),set()
        if any(self.env_keys(x) for x in op_nodes):uses.add("arith")
        if any(x.type=="call_expression" and self.builtin_call(x,HASHES) and any(self.env_keys(a) for a in self.arguments(x)) for x in items):uses.add("hash")
        if node_kind=="condition" or any(x.type=="call_expression" and self.builtin_call(x,("require","assert")) for x in items):
            if env:uses.add("guard")
            if ops:sinks.add("guard")
        for item in items:
            if item.type in ("assignment_expression","augmented_assignment_expression"):
                binding=self.root_binding(item.child_by_field_name("left"))
                if binding["kind"]=="state":
                    if env:uses.add("state")
                    if ops:sinks.add("state")
                elif ops:sinks.add("local")
            if item.type=="variable_declaration_statement" and ops:sinks.add("local")
        for call in active:
            if self.env_keys(call["target"]):uses.add("call")
            if call["value"] is not None:
                if self.env_keys(call["value"]):uses.add("call")
                if any(operator(x) in ARITH for x in walk(call["value"])):sinks.add("value")
        small=False
        for ident in (i for op_node in op_nodes for i in self.identifiers(op_node)):
            match=re.fullmatch(r"u?int([0-9]+)",self.resolve_identifier(ident)["type_name"])
            if match and int(match.group(1))<256:small=True
        in_block=False
        cursor=node
        while cursor is not None and cursor.type not in FUNCTIONS:
            if cursor.type=="block_statement":
                brace=next((x for x in cursor.children if x.type=="{"),None)
                if brace is not None and self.view.raw[cursor.start_byte:brace.start_byte].decode("utf8").strip()=="unchecked":in_block=True
            cursor=cursor.parent
        result={"env":{"keys":env,"uses":sorted(uses)},"syntax":syntax,"arith":{"ops":ops,"on_state":bool(ops and "state" in classes),"small_int":bool(ops and small),"from_param":bool(ops and "param" in classes),"from_env":any(self.env_keys(x) for x in op_nodes),"sinks":sorted(sinks),"in_unchecked":in_block}}
        if node_kind=="state_decl":
            result.pop("arith")
            return result
        primary=active[0] if active else None
        values=[self.value_class(x["value"]) for x in active if x["value"] is not None]
        priority=["none","literal","param","local","state","msg.value","this.balance","unknown","arith"]
        value_class=max(values,key=lambda x:priority.index(x)) if values else "none"
        data_nodes=[arg for call in active if call["kind"] not in ("send","transfer","selfdestruct") for arg in call["args"]]
        data_class="none"
        if data_nodes:data_class="msg.data" if any("msg.data" in self.env_keys(x) for x in data_nodes) else "param" if any("param" in self.operand_classes(x) for x in data_nodes) else "other"
        outcomes={self.return_handling(x["node"]) for x in active}
        return_handling=next(iter(outcomes)) if len(outcomes)==1 else "unknown" if outcomes else "not_applicable"
        unresolved={}
        if "unknown" in values:unresolved["call_value_class_unknown"]=values.count("unknown")
        if len(outcomes)>1:unresolved["mixed_call_return_handling"]=1
        if "unknown" in outcomes:unresolved["call_return_context_unknown"]=sum(self.return_handling(x["node"])=="unknown" for x in active)
        if unresolved:result["unresolved"]=unresolved
        result.update({"external":{"kinds":sorted({x["kind"] for x in active}),"value_attached":bool(values),"uninvoked_call_value":any(not x["invoked"] for x in calls),"target_classes":sorted({c for x in active for c in self.target_classes(x["target"])}),"value_class":value_class,"data_class":data_class,"return_handling":return_handling},"loop":{"bound":self.loop_bound(node)},"function_ctx":self.function_context(node)})
        return result


# ----------------------------------------------------------------------
# node_sem/facts_boolean
# Bounded boolean repair using original AST tokens and declaration identities.
#
# Frozen grammar can attach a member suffix across a boolean operator.
# This adapter neither reparses source nor invents declarations or graph nodes.
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
