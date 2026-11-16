"""Layer L3: ``env_source`` nodes for environment values and their ``ENV_FLOW`` edges."""
import copy
import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from numbers import Integral

import networkx as nx
import numpy as np

from dfg.analysis.frontend import span, text, walk
from dfg.analysis.ir import Unsupported
from dfg.analysis.units import iter_statement_regions, projected_node
from dfg.graph.audit import fingerprint
from dfg.graph.binding import StateBinder, unwrap
from dfg.graph.projection import ProjectionView, Projector
from dfg.graph.state import context, describe, identity
from dfg.model.registration import assert_disconnected_files
from dfg.schema import ENV_FLOW, ENV_SOURCE, VERSION


# ----------------------------------------------------------------------
# dfg_v2/env
# L3 source-only environment occurrences in statement-owned AST regions.
#
# Keys represent values, not syntax spellings. The extractor does not inspect
# HCG attributes, labels or features, and does not claim compilation or runtime
# path feasibility. Deprecated spellings follow the explicit Prompt 4 table.
ENV_KEYS = (
    "msg.sender", "msg.value", "msg.data", "msg.sig",
    "tx.origin", "tx.gasprice",
    "block.timestamp", "block.number", "block.difficulty", "block.coinbase",
    "block.gaslimit", "blockhash", "gasleft", "this.balance",
)

SPELLINGS = {
    "msg.sender": "msg.sender",
    "msg.value": "msg.value",
    "msg.data": "msg.data",
    "msg.sig": "msg.sig",
    "tx.origin": "tx.origin",
    "tx.gasprice": "tx.gasprice",
    "block.timestamp": "block.timestamp",
    "block.number": "block.number",
    "block.difficulty": "block.difficulty",
    "block.coinbase": "block.coinbase",
    "block.gaslimit": "block.gaslimit",
    "blockhash(...)": "blockhash",
    "gasleft()": "gasleft",
    "this.balance": "this.balance",
    "now": "block.timestamp",
    "msg.gas": "gasleft",
    "block.blockhash(...)": "blockhash",
    "address(this).balance": "this.balance",
}

_ASSEMBLY = frozenset(("assembly_statement", "inline_assembly_statement"))

_NON_REGIONS = frozenset((
    "function_body", "block_statement", "block", "if_statement",
    "for_statement", "while_statement", "do_while_statement", "try_statement",
    "function_definition", "constructor_definition", "modifier_definition",
    "fallback_receive_definition",
))

_NON_EXPRESSIONS = frozenset((
    "variable_declaration", "variable_declaration_tuple", "parameter",
    "type_name", "primitive_type", "user_defined_type", "struct_declaration",
    "struct_member", "visibility", "string_literal", "string",
    "hex_string_literal", "number_literal", "boolean_literal",
    "throw_statement", "break_statement", "continue_statement",
))

@dataclass(frozen=True)
class EnvOccurrence:
    key: str
    spelling: str
    span: object

def _top_level_names(view):
    """Known file-level names, including syntactically explicit imports only."""
    result = set()
    for node in view.tree.root_node.named_children:
        name = node.child_by_field_name("name")
        if name is not None:
            result.add(text(view.source, name))
        if node.type != "import_directive":
            continue
        pending = None
        for index, child in enumerate(node.children):
            field = node.field_name_for_child(index)
            if field == "import_name":
                if pending is not None:
                    result.add(pending)
                pending = text(view.source, child)
            elif field == "alias":
                # Alias replaces the imported source name; * as X and
                # import "file" as X have no preceding import_name.
                result.add(text(view.source, child))
                pending = None
            elif child.type in (",", "}", ";"):
                if pending is not None:
                    result.add(pending)
                    pending = None
        if pending is not None:
            result.add(pending)
    return result

class EnvExtractor:
    """Independent L3 lexical occurrences; diagnostics accumulate per owner."""

    def __init__(self, binder):
        self.binder = binder
        self.view = binder.view
        self.top_level_names = _top_level_names(self.view)
        self.diagnostics = []
        self._events = []
        self._seen = set()
        self._seen_diagnostics = set()

    def _diagnostic(self, node, kind, reason, key=None, spelling=None, **evidence):
        identity = (node.start_byte, node.end_byte, kind, reason, key, spelling)
        if identity in self._seen_diagnostics:
            return
        self._seen_diagnostics.add(identity)
        self.diagnostics.append({
            "kind": kind, "reason": reason, "key": key, "spelling": spelling,
            "file": self.view.file, "callable": self.binder.callable_id,
            "start": node.start_byte, "end": node.end_byte, "ast_type": node.type,
            **evidence,
        })

    def _shadow_reason(self, name):
        if name in self.binder.locals:
            return "callable_local_name"
        if name in self.binder.members:
            return "contract_member_name"
        if name in self.top_level_names:
            return "file_top_level_name"
        return None

    def _emit(self, node, spelling, checked_name=None):
        key = SPELLINGS[spelling]
        reason = self._shadow_reason(checked_name) if checked_name is not None else None
        if reason is not None:
            self._diagnostic(node, "shadowed", reason, key, spelling)
            return
        identity = (node.start_byte, node.end_byte, key, spelling)
        if identity not in self._seen:
            self._seen.add(identity)
            self._events.append(EnvOccurrence(key, spelling, span(self.view.file, node)))

    def _excluded_position(self, node):
        cursor = node
        while cursor is not None:
            if cursor.type in ("type_name", "primitive_type", "user_defined_type"):
                return True
            parent = cursor.parent
            if parent is not None:
                if parent.child_by_field_name("name") == cursor:
                    return True
                if parent.type == "member_expression" and parent.child_by_field_name("property") == cursor:
                    return True
            cursor = parent
        return False

    @staticmethod
    def _assembly_owner(node):
        while node is not None:
            if node.type in _ASSEMBLY:
                return node
            node = node.parent
        return None

    def _this_balance_spelling(self, receiver):
        receiver = unwrap(receiver)
        if receiver is None:
            return None
        if receiver.type == "identifier" and text(self.view.source, receiver) == "this":
            return "this.balance"
        if receiver.type != "type_cast_expression":
            return None
        children = [c for c in receiver.named_children if "comment" not in c.type]
        if len(children) != 2 or children[0].type != "primitive_type":
            return None
        if text(self.view.source, children[0]) != "address":
            return None
        argument = unwrap(children[1])
        if argument is not None and argument.type == "identifier" and text(self.view.source, argument) == "this":
            return "address(this).balance"
        return None

    @staticmethod
    def _postfix_leaf(node):
        """Recover only unparenthesized trailing binary/unary operands.

        The installed grammar can put a + gasleft in call.function and
        a + address(this) in member.object. Solidity postfix operators
        bind more tightly. Explicit parentheses are a hard boundary: never
        reinterpret (a + gasleft)() or (a + msg).sender.
        """
        cursor, steps = node, []
        while cursor is not None and cursor.type in ("binary_expression", "unary_expression"):
            field = "right" if cursor.type == "binary_expression" else "argument"
            child = cursor.child_by_field_name(field)
            if child is None or child.end_byte != cursor.end_byte:
                return None, ()
            steps.append({
                "ast_type": cursor.type, "field": field,
                "start": cursor.start_byte, "end": cursor.end_byte,
            })
            cursor = child
        return (cursor, tuple(steps)) if steps else (None, ())

    def _known_member(self, receiver, property_name):
        receiver = unwrap(receiver)
        if receiver is not None and receiver.type == "identifier":
            root = text(self.view.source, receiver)
            if root in ("msg", "tx", "block"):
                spelling = root + "." + property_name
                if spelling == "block.blockhash":
                    spelling = "block.blockhash(...)"
                if spelling in SPELLINGS:
                    return spelling, root
        if property_name == "balance":
            spelling = self._this_balance_spelling(receiver)
            if spelling is not None:
                return spelling, None
        return None

    def _record_recovery(self, node, leaf, steps, spelling, checked_name):
        self._diagnostic(
            node, "grammar_shape_recovered",
            "postfix_after_unparenthesized_binary_or_unary",
            SPELLINGS[spelling], spelling,
            original_span=asdict(span(self.view.file, node)),
            leaf_span=asdict(span(self.view.file, leaf)),
            leaf_text=text(self.view.source, leaf),
            steps=list(steps), checked_name=checked_name,
            shadow_reason=self._shadow_reason(checked_name) if checked_name else None,
        )

    def _visit(self, node):
        if node is None or "comment" in node.type:
            return
        assembly = self._assembly_owner(node)
        if assembly is not None:
            self._diagnostic(assembly, "assembly_skipped", "assembly_access_not_interpreted")
            return
        if self._excluded_position(node):
            return
        kind = node.type
        if kind in _NON_REGIONS:
            self._diagnostic(node, "region_skipped", "non_expression_region_requires_unit_selection")
            return
        if kind in _NON_EXPRESSIONS:
            return
        if kind == "identifier":
            if text(self.view.source, node) == "now":
                self._emit(node, "now", "now")
            return
        if kind == "member_expression":
            receiver = unwrap(node.child_by_field_name("object"))
            prop = node.child_by_field_name("property")
            property_name = text(self.view.source, prop) if prop is not None else ""
            if receiver is not None and receiver.type == "identifier":
                root = text(self.view.source, receiver)
                if root in ("msg", "tx", "block"):
                    spelling = root + "." + property_name
                    if spelling == "block.blockhash":
                        spelling = "block.blockhash(...)"
                    if spelling in SPELLINGS:
                        self._emit(node, spelling, root)
                    else:
                        reason = self._shadow_reason(root)
                        self._diagnostic(
                            node, "shadowed" if reason else "unknown_env_member",
                            reason or "member_not_in_env_table",
                            "unregistered:" + spelling, spelling,
                        )
                    return
            if property_name == "balance":
                spelling = self._this_balance_spelling(receiver)
                if spelling is not None:
                    # this and the address cast are reserved in the contract
                    # syntax and deliberately not checked against user names.
                    self._emit(node, spelling)
                    return
            # Keep the raw receiver: unwrapping a composite parenthesized
            # receiver here would incorrectly reinterpret (a + msg).sender.
            raw_receiver = node.child_by_field_name("object")
            leaf, steps = self._postfix_leaf(raw_receiver)
            recovered = self._known_member(leaf, property_name) if leaf is not None else None
            if recovered is not None:
                spelling, checked_name = recovered
                self._record_recovery(node, leaf, steps, spelling, checked_name)
                self._emit(node, spelling, checked_name)
            # Retain all reads in left operands and nested receivers; the
            # synthetic postfix match itself is not revisited as an AST node.
            self._visit(raw_receiver)
            return
        if kind == "call_expression":
            callee = node.child_by_field_name("function")
            recognized = False
            if callee is not None and callee.type == "identifier":
                name = text(self.view.source, callee)
                spelling = {"blockhash": "blockhash(...)", "gasleft": "gasleft()"}.get(name)
                if spelling is not None:
                    self._emit(node, spelling, name)
                    recognized = True
            if not recognized:
                leaf, steps = self._postfix_leaf(callee)
                if leaf is not None and leaf.type == "identifier":
                    name = text(self.view.source, leaf)
                    spelling = {"blockhash": "blockhash(...)", "gasleft": "gasleft()"}.get(name)
                    if spelling is not None:
                        self._record_recovery(node, leaf, steps, spelling, name)
                        self._emit(node, spelling, name)
                        # Do not mark the entire binary/unary callee consumed:
                        # its other operands can contain independent ENV uses.
            for child in node.named_children:
                if child == callee and recognized:
                    continue
                self._visit(child)
            return
        if kind in ("variable_declaration_statement", "state_variable_declaration"):
            self._visit(node.child_by_field_name("value"))
            return
        if kind in ("call_struct_argument", "struct_field_assignment"):
            self._visit(node.child_by_field_name("value"))
            return
        if kind == "revert_statement":
            # A custom error's name is not a value occurrence. Arguments
            # survive even though the author HCG normally cannot project it.
            error = node.child_by_field_name("error")
            for child in node.named_children:
                if child != error or child.type == "parenthesized_expression":
                    self._visit(child)
            return
        for child in node.named_children:
            self._visit(child)

    def extract(self, regions):
        """Return only current occurrences, deduplicated by exact AST span."""
        if hasattr(regions, "regions"):
            regions = regions.regions
        if not isinstance(regions, (list, tuple)):
            regions = [regions]
        self._events, self._seen, self._seen_diagnostics = [], set(), set()
        for region in regions:
            self._visit(region)
        return list(self._events)


# ----------------------------------------------------------------------
# dfg_v2/l3
# L3 environment hubs on frozen HCG/L1/L2; source-only analysis.
#
# Existing nodes/edges/features/labels remain unchanged. Only successfully
# projected uses create an auxiliary node. REV relations belong to model input.
ENV_NODE_KEYS = frozenset(("node_type", "source_file", "code", "label", "method",
    "node_info_vulnerabilities", "node_source_code_lines", "type_label", "token", "dfg_v2_aux"))

def strip_aux(graph):
    """Return an independent original-node graph; never mutate the input."""
    result = copy.deepcopy(graph)
    result.remove_nodes_from([n for n, d in result.nodes(data=True)
                              if d.get("node_type") == ENV_SOURCE])
    return result

def _input(graph):
    if not isinstance(graph, nx.MultiDiGraph) or not graph:
        raise ValueError("Expected a nonempty MultiDiGraph")
    for node, data in graph.nodes(data=True):
        if not isinstance(node, Integral) or isinstance(node, bool):
            raise ValueError("Original HCG node IDs must be integers")
        if data.get("node_type") == ENV_SOURCE or data.get("dfg_v2_aux"):
            raise ValueError("Input already contains auxiliary nodes")
        if not isinstance(data.get("source_file"), str) or not data.get("node_type"):
            raise ValueError("Original nodes require source_file and node_type")
        token = data.get("token")
        if (type(token) is not np.ndarray or token.dtype != np.float32 or
                token.shape != (512,) or not np.isfinite(token).all()):
            raise ValueError("Original tokens must be float32 ndarray of shape (512,)")
    for _, _, data in graph.edges(data=True):
        relation = data.get("edge_type")
        if not isinstance(relation, str) or relation == ENV_FLOW or relation.startswith("REV_"):
            raise ValueError("Expected original/L1/L2 relations, without ENV_FLOW or REV")
    assert_disconnected_files(graph)

def assert_preserved(base, output):
    if fingerprint(strip_aux(output)) != fingerprint(base):
        raise AssertionError("Original HCG/L1/L2 changed")
    if list(output)[:len(base)] != list(base):
        raise AssertionError("Original node insertion order changed")
    added = [n for n in output if n not in base]
    if added != list(range(int(max(base)) + 1, int(max(base)) + 1 + len(added))):
        raise AssertionError("Auxiliary node allocation is not consecutive")
    seen = set()
    for node in added:
        data = output.nodes[node]
        if set(data) != ENV_NODE_KEYS or data["node_type"] != ENV_SOURCE or data["dfg_v2_aux"] is not True:
            raise AssertionError("Unexpected auxiliary attributes")
        key = (data["source_file"], data["code"])
        if data["code"] not in ENV_KEYS or key in seen:
            raise AssertionError("Unknown/duplicate file environment hub")
        seen.add(key)
        if output.in_degree(node) != 0 or output.out_degree(node) == 0:
            raise AssertionError("Environment hubs require outgoing uses only")
        if data["node_info_vulnerabilities"] is not None or data["node_source_code_lines"] != []:
            raise AssertionError("Auxiliary nodes cannot carry source labels")
        for _, target, attrs in output.out_edges(node, data=True):
            if target not in base or attrs["edge_type"] != ENV_FLOW:
                raise AssertionError("Unexpected auxiliary edge")
    edges = [(s, t, d) for s, t, d in output.edges(data=True) if d["edge_type"] == ENV_FLOW]
    if len({(s, t) for s, t, _ in edges}) != len(edges):
        raise AssertionError("Duplicate ENV_FLOW edge")
    if any(s not in added or t not in base for s, t, _ in edges):
        raise AssertionError("Unexpected environment endpoints")
    assert_disconnected_files(output)
    return dict(original_graph_exact=True, original_node_order_exact=True,
                L1_L2_edges_exact=True, added_nodes=len(added), added_edges=len(edges))

def _inside_assembly(node):
    while node is not None:
        if node.type == "assembly_statement":
            return True
        node = node.parent
    return False

def augment_l3(graph, sources, metadata, token_encoder):
    _input(graph)
    before = fingerprint(graph)
    output = copy.deepcopy(graph)
    audit = dict(version=VERSION, layer="L3", profiles=["G3", "G3R"], files={},
                 evidence=[], source_hashes={}, labels_used_for_analysis=False,
                 original_features_changed=False, tokenizer=copy.deepcopy(
                     getattr(token_encoder, "provenance", {"source": "caller_supplied_encoder"})))
    pending = defaultdict(list)
    for file in sorted({d["source_file"] for _, d in graph.nodes(data=True)}):
        record = dict(diagnostics=[], keys={}, units=0, assembly_skipped=0,
                      unknown_env_member={}, shadowed={}, unmapped_by_statement={},
                      callables={}, binding_scopes={})
        audit["files"][file] = record
        if file not in sources:
            record["diagnostics"].append(dict(kind="file_fallback", reason="missing_exact_source"))
            continue
        source = sources[file]
        audit["source_hashes"][file] = hashlib.sha256(source.encode("utf8")).hexdigest()
        try:
            view = ProjectionView(source, file)
            projector = Projector(graph, view)
        except Unsupported as exc:
            record["diagnostics"].append(dict(kind="projection_fallback", reason=str(exc)))
            continue
        record["projector"] = dict(projector.stats)
        for node in walk(view.tree.root_node):
            if node.type == "assembly_statement":
                record["assembly_skipped"] += 1
                record["diagnostics"].append(dict(kind="assembly_skipped",
                    reason="yul_not_interpreted", file=file, start=node.start_byte, end=node.end_byte))
        extractors = {}
        for candidate in iter_statement_regions(view, projector):
            if not candidate.regions or _inside_assembly(candidate.ast_node):
                continue
            owner = context(candidate.ast_node)
            if owner is None:
                continue
            owner_id = identity(file, owner)
            if owner_id not in extractors:
                binder = StateBinder(view, owner, (metadata or {}).get(file))
                extractors[owner_id] = EnvExtractor(binder)
                record["binding_scopes"][owner_id] = dict(scope_fallback=binder.scope_fallback,
                    locals=sorted(binder.locals), members=sorted(binder.members))
            target = projected_node(view, projector, candidate.ast_node)
            record["units"] += 1
            for occurrence in extractors[owner_id].extract(candidate.regions):
                key = occurrence.key
                rec = record["keys"].setdefault(key, dict(occurrences=0, projected=0,
                    unmapped=0, spellings={}, unmapped_by_statement={}))
                rec["occurrences"] += 1
                rec["spellings"][occurrence.spelling] = rec["spellings"].get(occurrence.spelling, 0) + 1
                status = "projected" if target is not None else "unmapped"
                rec[status] += 1
                if target is None:
                    kind = candidate.ast_node.type
                    rec["unmapped_by_statement"][kind] = rec["unmapped_by_statement"].get(kind, 0) + 1
                    record["unmapped_by_statement"][kind] = record["unmapped_by_statement"].get(kind, 0) + 1
                ev = dict(file=file, callable=owner_id, callable_kind=owner.type,
                    env_key=key, spelling=occurrence.spelling, occurrence=asdict(occurrence.span),
                    statement=describe(view, candidate.ast_node), source=None, target=target,
                    status=status)
                index = len(audit["evidence"])
                audit["evidence"].append(ev)
                record["callables"].setdefault(owner_id, dict(occurrences=0, projected=0))
                record["callables"][owner_id]["occurrences"] += 1
                record["callables"][owner_id]["projected"] += int(target is not None)
                if target is not None:
                    pending[(file, key, target)].append(index)
        for extractor in extractors.values():
            record["diagnostics"].extend(extractor.diagnostics)
        for diag in record["diagnostics"]:
            if diag["kind"] == "unknown_env_member":
                spelling = diag["spelling"]
                record["unknown_env_member"][spelling] = record["unknown_env_member"].get(spelling, 0) + 1
            elif diag["kind"] == "shadowed":
                key, reason = diag["key"], diag["reason"]
                bucket = record["shadowed"].setdefault(key, {})
                bucket[reason] = bucket.get(reason, 0) + 1
    used = {(file, key) for file, key, _ in pending}
    hubs = {}
    next_id = int(max(graph)) + 1
    for file, key in sorted(used, key=lambda item: (item[0], ENV_KEYS.index(item[1]))):
        token = token_encoder(key)
        if type(token) is not np.ndarray or token.dtype != np.float32 or token.shape != (512,) or not np.isfinite(token).all():
            raise ValueError("Encoder token type/dtype/shape differs from original")
        hubs[(file, key)] = next_id
        output.add_node(next_id, node_type=ENV_SOURCE, source_file=file, code=key,
            label="ENV:" + key, method="", node_info_vulnerabilities=None,
            node_source_code_lines=[], type_label=ENV_SOURCE, token=token.copy(), dfg_v2_aux=True)
        next_id += 1
    for (file, key, target), indices in pending.items():
        source_id = hubs[(file, key)]
        for index in indices:
            audit["evidence"][index]["source"] = source_id
        output.add_edge(source_id, target, edge_type=ENV_FLOW, dfg_v2_version=VERSION,
            env_key=key, spellings=sorted({audit["evidence"][i]["spelling"] for i in indices}),
            evidence_indices=indices)
    audit["invariants"] = assert_preserved(graph, output)
    if fingerprint(graph) != before:
        raise AssertionError("L3 mutated its input")
    audit["canonical_counts"] = [dict(canonical=list(key), edges=count) for key, count in sorted(Counter(
        (output.nodes[s]["node_type"], d["edge_type"], output.nodes[t]["node_type"])
        for s, t, d in output.edges(data=True) if d["edge_type"] == ENV_FLOW).items())]
    return output, audit
