"""Layer L2: ``WRITES_STATE`` / ``READS_STATE`` edges through per-variable state hub nodes."""
import copy
import hashlib
from collections import Counter, defaultdict
from dataclasses import asdict

from dfg.analysis.frontend import FUNCTION_TYPES, parse, span, text, walk
from dfg.analysis.ir import Unsupported
from dfg.analysis.units import ast_key, iter_statement_regions, projected_node, statement_units
from dfg.graph.audit import fingerprint, frozen
from dfg.graph.binding import StateAccessExtractor, StateBinder
from dfg.graph.projection import ProjectionView, Projector
from dfg.schema import READS_STATE, VERSION, WRITES_STATE


# ----------------------------------------------------------------------
# dfg_v2/l2
# State accesses projected onto existing HCG nodes; no new variable nodes.
#
# Flow-insensitive source analysis is independent of L1 success. No annotation,
# prediction or token is used to infer state accesses or declaration identity.
RELATIONS = frozenset((WRITES_STATE, READS_STATE))

CALLABLES = frozenset(FUNCTION_TYPES) | {"modifier_definition"}

def context(node):
    while node is not None:
        if node.type in CALLABLES or node.type == "state_variable_declaration":
            return node
        node = node.parent
    return None

def identity(file, node):
    return file + ":" + str(node.start_byte)

def describe(view, node):
    name = node.child_by_field_name("name")
    return dict(asdict(span(view.file, node)), line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                name=text(view.source, name) if name is not None else node.type)

def assert_preserved(base, output):
    """Include original L1 edge attributes/evidence in preservation checks."""
    if frozen(base.graph) != frozen(output.graph):
        raise AssertionError("Original graph attributes changed")
    if frozen(list(base.nodes(data=True))) != frozen(list(output.nodes(data=True))):
        raise AssertionError("Original node identity/order/attributes changed")
    retained = [(s, t, k, d) for s, t, k, d in output.edges(keys=True, data=True)
                if d["edge_type"] not in RELATIONS]
    if frozen(list(base.edges(keys=True, data=True))) != frozen(retained):
        raise AssertionError("Original base or L1 edge key/attributes changed")
    seen = set()
    for s, t, attrs in output.edges(data=True):
        relation = attrs["edge_type"]
        if relation not in RELATIONS:
            continue
        key = (s, t, relation)
        if s == t or key in seen:
            raise AssertionError("Duplicate/self L2 edge")
        if output.nodes[s]["source_file"] != output.nodes[t]["source_file"]:
            raise AssertionError("Cross-file state edge")
        declaration = t if relation == WRITES_STATE else s
        if output.nodes[declaration]["node_type"] != "new_variable":
            raise AssertionError("State declaration is not an existing new_variable")
        seen.add(key)
    return dict(original_nodes_exact=True, original_edges_and_attributes_exact=True,
                original_nodes=len(base), original_edges=base.number_of_edges(),
                output_edges=output.number_of_edges(),
                added_by_relation=dict(Counter(k[2] for k in seen)))

def _input(graph):
    if not graph.is_directed() or not graph.is_multigraph():
        raise ValueError("Expected directed MultiDiGraph")
    for _, data in graph.nodes(data=True):
        if not isinstance(data.get("source_file"), str) or not data.get("node_type"):
            raise ValueError("Nodes require exact source_file and node_type")
    for s, t, data in graph.edges(data=True):
        relation = data.get("edge_type")
        if not isinstance(relation, str):
            raise ValueError("Edges require edge_type")
        if relation in RELATIONS or relation.startswith("REV_"):
            raise ValueError("Expected HCG/L1 input without L2 or REV relations")
        if graph.nodes[s]["source_file"] != graph.nodes[t]["source_file"]:
            raise ValueError("Cross-file model edge")

def augment_l2(graph, sources, metadata=None, include_constants=False):
    """Return a new graph with forward L2 edges and auditable source evidence."""
    if type(include_constants) is not bool:
        raise ValueError("include_constants must be boolean")
    _input(graph)
    before = fingerprint(graph)
    output = copy.deepcopy(graph)
    audit = dict(version=VERSION, layer="L2", profile="G2R", include_constants=include_constants,
                 files={}, evidence=[], source_hashes={}, labels_used_for_analysis=False,
                 token_features_changed=False, analysis="flow-insensitive state access")
    pending = defaultdict(list)
    for file in dict.fromkeys(d["source_file"] for _, d in graph.nodes(data=True)):
        record = dict(callables={}, declarations=[], diagnostics=[], units=0, unmapped_units=0,
                      occurrences={"READ": 0, "WRITE": 0}, unmapped=0, anchor_missing=0,
                      self_accesses_skipped=0, alias_occurrences=0, binding_audits={})
        audit["files"][file] = record
        if file not in sources:
            record["diagnostics"].append(dict(kind="file_fallback", reason="missing_exact_source"))
            continue
        source = sources[file]
        audit["source_hashes"][file] = hashlib.sha256(source.encode("utf8")).hexdigest()
        try:
            tree = parse(source)
        except Unsupported as exc:
            record["diagnostics"].append(dict(kind="file_fallback", reason=str(exc)))
            continue
        nodes = list(walk(tree.root_node))
        declarations = [n for n in nodes if n.type == "state_variable_declaration"]
        for node in nodes:
            if node.type in CALLABLES and node.child_by_field_name("body") is not None:
                record["callables"][identity(file, node)] = dict(kind=node.type,
                    start=node.start_byte, end=node.end_byte, units=0, occurrences=0, projected=0)
        record["callable_count"] = len(record["callables"])
        try:
            view = ProjectionView(source, file)
            projector = Projector(graph, view)
        except Unsupported as exc:
            record["declarations"] = [dict(start=n.start_byte, end=n.end_byte,
                name=text(source, n.child_by_field_name("name")), node_id=None,
                status="view_unverified") for n in declarations]
            record["diagnostics"].append(dict(kind="projection_fallback", reason=str(exc)))
            continue
        record["projector"] = dict(projector.stats)
        for declaration in (n for n in walk(view.tree.root_node)
                            if n.type == "state_variable_declaration"):
            node_id = projected_node(view, projector, declaration)
            valid = node_id is not None and graph.nodes[node_id]["node_type"] == "new_variable"
            record["declarations"].append(dict(describe(view, declaration), node_id=node_id,
                status="matched" if valid else "no_exact_hcg_node"))
        mapped = {ast_key(u.ast_node): u for u in statement_units(view, projector)}
        record["units"] = len(mapped)
        binders, extractors = {}, {}
        for candidate in iter_statement_regions(view, projector):
            owner = context(candidate.ast_node)
            if owner is None or not candidate.regions:
                continue
            owner_id = identity(file, owner)
            owner_record = record["callables"].setdefault(owner_id, dict(kind=owner.type,
                start=owner.start_byte, end=owner.end_byte, units=0, occurrences=0, projected=0))
            if owner_id not in binders:
                binder = StateBinder(view, owner, (metadata or {}).get(file), include_constants)
                binders[owner_id] = binder
                extractors[owner_id] = StateAccessExtractor(binder)
            extractor = extractors[owner_id]
            unit = mapped.get(ast_key(candidate.ast_node))
            if unit is None:
                record["unmapped_units"] += 1
            else:
                owner_record["units"] += 1
            for access in extractor.extract(candidate.regions):
                record["occurrences"][access.kind] += 1
                owner_record["occurrences"] += 1
                record["alias_occurrences"] += int(access.via_alias)
                state = access.declaration
                state_id = projected_node(view, projector, state)
                relation = WRITES_STATE if access.kind == "WRITE" else READS_STATE
                status = "projected"
                if unit is None:
                    status = "unmapped"
                    record["unmapped"] += 1
                elif state_id is None or graph.nodes[state_id]["node_type"] != "new_variable":
                    status = "anchor_missing"
                    record["anchor_missing"] += 1
                elif unit.hcg_node_id == state_id:
                    status = "self_access_skipped"
                    record["self_accesses_skipped"] += 1
                statement_id = unit.hcg_node_id if unit is not None else None
                src, dst = ((statement_id, state_id) if relation == WRITES_STATE
                            else (state_id, statement_id))
                evidence = dict(file=file, callable=owner_id, callable_kind=owner.type,
                    relation=relation, state=describe(view, state), statement=describe(view, candidate.ast_node),
                    occurrence=asdict(access.occurrence_span), via_alias=access.via_alias,
                    reason=access.reason, source=src, target=dst, status=status)
                index = len(audit["evidence"])
                audit["evidence"].append(evidence)
                if status == "projected":
                    pending[(src, dst, relation)].append(index)
                    owner_record["projected"] += 1
        for owner_id, binder in binders.items():
            record["binding_audits"][owner_id] = binder.audit()
            diagnostics = list(binder.diagnostics) + list(extractors[owner_id].diagnostics)
            record["diagnostics"].extend(dict(d, callable=owner_id) for d in diagnostics)
        record["alias_bindings"] = sum(len(b["aliases"]) for b in record["binding_audits"].values())
    for (src, dst, relation), indices in pending.items():
        evidence = [audit["evidence"][i] for i in indices]
        output.add_edge(src, dst, edge_type=relation, dfg_v2_version=VERSION,
            state_vars=sorted({e["state"]["name"] for e in evidence}),
            via_alias=any(e["via_alias"] for e in evidence), evidence_indices=indices)
    for record in audit["files"].values():
        unresolved = [d for d in record["diagnostics"] if d.get("kind") == "state_binding_unresolved"]
        record["unresolved"] = len(unresolved)
        record["unresolved_reasons"] = dict(Counter(d["reason"] for d in unresolved))
        record["alias_unresolved_reasons"] = dict(Counter(d["reason"] for d in record["diagnostics"]
            if d.get("kind") == "state_alias_unresolved"))
        record["access_unresolved_reasons"] = dict(Counter(d["reason"] for d in record["diagnostics"]
            if d.get("kind") == "state_access_unresolved"))
    audit["invariants"] = assert_preserved(graph, output)
    audit["canonical_counts"] = [dict(canonical=list(key), edges=count) for key, count in sorted(Counter(
        (output.nodes[s]["node_type"], d["edge_type"], output.nodes[t]["node_type"])
        for s, t, d in output.edges(data=True) if d["edge_type"] in RELATIONS).items())]
    if fingerprint(graph) != before:
        raise AssertionError("L2 input graph mutated")
    return output, audit
