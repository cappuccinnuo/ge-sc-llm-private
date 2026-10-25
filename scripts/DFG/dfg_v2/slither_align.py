"""Prompt 6d: additional byte-span comparison of sealed 6c read/write evidence.

No compiler, analyzer, graph builder, tokenizer or training code is invoked.
L1 counts IR events; L2 candidates count (statement Unit, variable, READ/WRITE).
Slither references remain CFG-node variable sets. These are NOT 6c line sets.
Within each name/kind group, candidates and references are sorted by
(start,entry-last-on-equal-start,end,stable identity); each candidate takes the first unused overlapping
reference. Inherited-context copies of the same source event are unioned.
This greedy diagnostic is not binding proof and not DDG-edge precision/recall.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re
from pathlib import Path

from scripts.DFG.frontend import parse, walk, library_path
from .validate_slither import _sha, _json, _checked, _write_json, _load_inputs

from .slither_units import normalize_l2_units, unit_comparison
from .slither_patterns import classify_pattern, audit_binding_unresolved, PATTERN_CATEGORIES

VERSION = "dfg-v2-slither-statement-alignment-v4.2"
L2_CATEGORIES = ("constant_excluded", "state_initializer", "write_base_read",
                 "modifier_inlining", "alias", "v2_binding_unresolved",
                 "assembly", "push_pop_skipped", "loop_header_merge_write", "legacy_alias_unconfirmed", "other")
L1_CATEGORIES = ("entry_initialization", "v2_fallback", "unreachable_ir",
                 "named_return_implicit", "declaration_without_initializer",
                 "tuple_or_var_declaration", "modifier_body_unanalyzed", "loop_header_merge_write",
                 "aggregate_base_use", "bare_expression_use", "other")
EXCLUSIONS = {"alias", "modifier_inlining"}


def overlap(a, b):
    """Half-open UTF-8 byte intervals; empty nodes overlap nothing."""
    return a[0] < b[1] and b[0] < a[1] and a[0] < a[1] and b[0] < b[1]


def _span(obj, size):
    if not isinstance(obj, dict):
        raise ValueError("Missing byte span")
    a, b = obj.get("start"), obj.get("end")
    if type(a) is not int or type(b) is not int or not 0 <= a <= b <= size:
        raise ValueError("Invalid raw byte span: " + repr(obj))
    return [a, b]


def _dump(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _id(value):
    return hashlib.sha256(_dump(value).encode("utf8")).hexdigest()


def _ordered(events):
    return sorted(events, key=lambda e: (e["span"][0],
        int("entry_initialization" in e.get("tags", [])), e["span"][1], e["event_id"]))


def match_spans(candidate, reference):
    """One-to-one deterministic greedy matching; never transitive closure."""
    groups = defaultdict(list)
    for ref in reference:
        groups[(ref["name"], ref["kind"])].append(ref)
    for key in groups:
        groups[key] = _ordered(groups[key])
    used, matches, extra = set(), [], []
    for cand in _ordered(candidate):
        eligible = [ref for ref in groups[(cand["name"], cand["kind"])]
                    if ref["event_id"] not in used and overlap(cand["span"], ref["span"])]
        if not eligible:
            extra.append(cand)
            continue
        ref = eligible[0]
        used.add(ref["event_id"])
        matches.append((cand, ref))
    missing = [ref for ref in _ordered(reference) if ref["event_id"] not in used]
    return matches, extra, missing


def metrics(candidate, reference, matches):
    c, r, m = len(candidate), len(reference), len(matches)
    return dict(candidate_count=c, reference_count=r, matched=m,
                extra=c-m, missing=r-m, precision=m/c if c else None,
                recall=m/r if r else None)


def _scope(start, functions):
    matches = [f for f in functions if f["start"] == start]
    if len(matches) > 1:
        raise ValueError("Ambiguous function identity in sealed inventory")
    if not matches:
        return "unmapped"
    return "supported" if matches[0]["status"] == "supported" else "fallback"


def _normalize(rows, side, layer, raw, functions, ast=None):
    """Collapse only identical source event identities, retaining all evidence."""
    groups = {}
    for row in rows:
        if side == "v2":
            if layer == "L1":
                interval = _span(row["declaration"] if row["event_kind"] == "entry"
                                 else row["event_anchor"], len(raw))
                name, kind = row["name"], row["kind"]
                decl = _span(row["declaration"], len(raw))
                function_start = row["function_start"]
                tags = row["tags"]
                line = row["line"]
            else:
                interval = _span(row["occurrence"], len(raw))
                name = row["state"]["name"]
                kind = {"READS_STATE": "READ", "WRITES_STATE": "WRITE"}[row["relation"]]
                decl = _span(row["state"], len(raw))
                function_start = int(row["callable"].rsplit(":", 1)[1])
                tags = (["alias"] if row.get("via_alias") else []) + (
                    ["modifier_inlining"] if row.get("callable_kind") == "modifier_definition" else [])
                line = raw[:interval[0]].count(b"\n") + 1
        else:
            interval = _span(row["node"], len(raw))
            line, name, kind = row["fact"]
            decl = _span(row["declaration"], len(raw)) if row.get("declaration") else None
            function_start = row["function"]["start"] if row.get("function") else None
            tags = row["tags"]
        raw[interval[0]:interval[1]].decode("utf8")
        original_name = name
        normalization = None
        if side == "slither" and ast is not None:
            normalization = ast.reference_name(name, decl)
            if normalization is not None:
                name = normalization["source_name"]
        ir_event_id = row["event_id"] if side == "v2" and layer == "L1" else None
        key = (side, layer, tuple(interval), name, kind,
               tuple(decl) if decl is not None else None, function_start, ir_event_id)
        if key not in groups:
            groups[key] = dict(event_id=_id(key), side=side, layer=layer,
                span=interval, name=name, kind=kind, line=line, declaration=decl,
                function_start=function_start, function_scope=_scope(function_start, functions),
                tags=[], evidence=[], name_normalizations=[], original_names=[], ir_event_id=ir_event_id, source_text=raw[interval[0]:interval[1]].decode("utf8"))
        item = groups[key]
        if original_name not in item["original_names"]:
            item["original_names"].append(original_name)
        if normalization is not None and normalization not in item["name_normalizations"]:
            item["name_normalizations"].append(normalization)
        item["tags"] = sorted(set(item["tags"]) | set(tags))
        if row not in item["evidence"]:
            item["evidence"].append(row)
    return _ordered(list(groups.values()))


class SourceFacts:
    """Mechanical AST facts used only to classify already-unmatched events."""
    def __init__(self, source):
        self.source = source
        self.raw = source.encode("utf8")
        self.tree = parse(source)
        self.nodes = list(walk(self.tree.root_node))
        self.states = [n for n in self.nodes if n.type == "state_variable_declaration"]
        self.assembly = [n for n in self.nodes if n.type in
                         ("assembly_statement", "inline_assembly_statement")]
        self.by_span = defaultdict(list)
        for node in self.nodes:
            self.by_span[(node.start_byte, node.end_byte)].append(node)

    def text(self, node):
        return self.raw[node.start_byte:node.end_byte].decode("utf8")

    @staticmethod
    def interval(node):
        return [node.start_byte, node.end_byte]

    def named_declaration(self, event, state=False):
        if event["declaration"] is None:
            return None
        types = ("state_variable_declaration",) if state else ("parameter", "variable_declaration")
        a, b = event["declaration"]
        found = []
        for node in (self.states if state else self.nodes):
            if node.type not in types:
                continue
            # Slither declaration spans may include their initializer. Exact
            # common start is accepted; never search the nearest declaration.
            if not ((node.start_byte <= a and b <= node.end_byte) or
                    (node.start_byte == a and node.end_byte <= b)):
                continue
            name = node.child_by_field_name("name")
            if name is not None and self.text(name) == event["name"]:
                found.append(node)
        return min(found, key=lambda n: n.end_byte-n.start_byte) if found else None

    def reference_name(self, name, declaration):
        """Normalize Slither scope renaming only with exact AST declaration start.

        Slither declarations may include the initializer while tree-sitter's
        variable_declaration ends at the identifier. Their starts must agree;
        no nearest-location search or blind suffix stripping is allowed.
        """
        if declaration is None:
            return None
        a, b = declaration
        matches = []
        for node in self.nodes:
            if node.type not in ("variable_declaration", "state_variable_declaration", "parameter"):
                continue
            if node.start_byte != a or not overlap([a, b], self.interval(node)):
                continue
            identifier = node.child_by_field_name("name")
            if identifier is not None:
                matches.append((self.text(identifier), self.interval(node)))
        if len(matches) != 1:
            return None
        source_name, ast_declaration = matches[0]
        if source_name == name:
            return None
        if not re.fullmatch(re.escape(source_name) + r"_scope_[0-9]+", name):
            return None
        return dict(original_name=name, source_name=source_name,
                    reference_declaration=declaration, ast_declaration=ast_declaration,
                    predicate="unique_exact_AST_declaration_start_and_Slither_scope_rename")

    def root_is_chain(self, event):
        """A confirmed v2 WRITE occurrence is a chain rooted at this name."""
        for evidence in event["evidence"]:
            occurrence = evidence.get("occurrence", {})
            for node in self.by_span.get((occurrence.get("start"), occurrence.get("end")), []):
                if node.type == "identifier":
                    # Some frozen L2 accesses store the delete operand rather
                    # than the full unary expression. Only its exact direct
                    # AST parent (through expression wrappers) can prove delete.
                    current, parent = node, node.parent
                    while (parent is not None and parent.type in
                           ("expression", "parenthesized_expression") and
                           len(parent.named_children) == 1):
                        current, parent = parent, parent.parent
                    operator = parent.child_by_field_name("operator") if parent is not None else None
                    argument = parent.child_by_field_name("argument") if parent is not None else None
                    if not (parent is not None and parent.type == "unary_expression" and
                            operator is not None and operator.type == "delete" and
                            argument is not None and argument.start_byte == current.start_byte and
                            argument.end_byte == current.end_byte):
                        continue
                    node = parent
                if node.type not in ("array_access", "member_expression", "unary_expression"):
                    continue
                cursor = node
                while cursor.type in ("array_access", "member_expression", "unary_expression"):
                    if cursor.type == "unary_expression":
                        operator = cursor.child_by_field_name("operator")
                        if operator is None or operator.type != "delete":
                            cursor = None
                            break
                        cursor = cursor.child_by_field_name("argument")
                    else:
                        cursor = cursor.child_by_field_name(
                            "base" if cursor.type == "array_access" else "object")
                    if cursor is None:
                        break
                    while cursor.type in ("expression", "parenthesized_expression") and len(cursor.named_children) == 1:
                        cursor = cursor.named_children[0]
                if cursor is not None and cursor.type == "identifier" and self.text(cursor) == event["name"]:
                    return True
        return False

    def in_node(self, event, node):
        a, b = event["span"]
        return node.start_byte <= a and b <= node.end_byte

    def named_return(self, event):
        node = self.named_declaration(event)
        return (node is not None and node.type == "parameter" and
                node.parent is not None and node.parent.type == "return_type_definition")

    def return_site(self, event):
        return any(n.type == "return_statement" and overlap(event["span"], self.interval(n))
                   for n in self.nodes)

    def declaration_statement(self, event):
        node = self.named_declaration(event)
        while node is not None:
            if node.type == "variable_declaration_statement":
                return node
            if node.type in ("function_definition", "constructor_definition"):
                break
            node = node.parent
        return None


def _access_overlaps(candidate, span):
    """Classify access locations, not a control Unit's enclosing body range."""
    locations = [r["occurrence"] for r in candidate.get("evidence", [])
                 if r.get("occurrence") is not None]
    if locations:
        return any(overlap([r["start"], r["end"]], span) for r in locations)
    return overlap(candidate["span"], span)


def classify(event, direction, ast, candidate, diagnostics):
    """First satisfied predicate in Prompt 6d order, with replayable evidence."""
    layer = event["layer"]
    tags = set(event["tags"])
    if layer == "L1":
        if direction == "FP" and "entry_initialization" in tags:
            return "entry_initialization", {"predicate": "sealed_entry_initialization_tag"}
        if direction == "FN" and event["function_scope"] == "fallback":
            return "v2_fallback", {"predicate": "exact_function_start_status_fallback"}
        if "unreachable_ir" in tags:
            return "unreachable_ir", {"predicate": "sealed_unreachable_ir_tag"}
        if ast.named_return(event):
            if ((event["kind"] == "USE" and ast.return_site(event)) or
                    (event["kind"] == "DEF" and event["declaration"] is not None and
                     event["declaration"][0] <= event["span"][0] and
                     event["span"][1] <= event["declaration"][1])):
                return "named_return_implicit", {"predicate": "named_return_declaration_and_return_use_or_declaration_DEF",
                                                "declaration": event["declaration"]}
        statement = ast.declaration_statement(event)
        if statement is not None and event["kind"] == "DEF" and ast.in_node(event, statement):
            if statement.child_by_field_name("value") is None:
                return "declaration_without_initializer", {
                    "predicate": "DEF_in_exact_declaration_statement_without_value",
                    "statement": ast.interval(statement),
                    "origin": sorted({r.get("origin", "reference") for r in event["evidence"]})}
        if statement is not None and ast.in_node(event, statement):
            if any(n.type in ("variable_declaration_tuple", "variable_declaration_tuple_initial_value")
                   for n in walk(statement)):
                return "tuple_or_var_declaration", {"predicate": "exact_tuple_declaration_AST",
                                                     "statement": ast.interval(statement)}
        return "other", {"predicate": "no_prior_mechanical_predicate"}

    declaration = ast.named_declaration(event, state=True)
    if direction == "FN":
        constant = any(r.get("is_constant") is True for r in event["evidence"])
        if declaration is not None:
            constant = constant or any(c.type == "constant" for c in declaration.children)
        if constant:
            return "constant_excluded", {"predicate": "is_constant_or_exact_constant_declaration",
                                           "declaration": event["declaration"]}
        constructor = any(r.get("function_name", "").split(".")[-1].startswith("slitherConstructor")
                          for r in event["evidence"])
        init_node = next((n for n in ast.states if ast.in_node(event, n)), None)
        if constructor or init_node is not None:
            return "state_initializer", {"predicate": "synthetic_constructor_or_state_declaration_span",
                                           "state_span": ast.interval(init_node) if init_node is not None else None}
        if event["kind"] == "READ":
            writes = [c for c in candidate if c["name"] == event["name"] and c["kind"] == "WRITE"
                      and _access_overlaps(c, event["span"]) and ast.root_is_chain(c)
                      and (c["declaration"] is None or event["declaration"] is None or
                           c["declaration"][0] == event["declaration"][0])]
            reads = [c for c in candidate if c["name"] == event["name"] and c["kind"] == "READ"
                     and _access_overlaps(c, event["span"])]
            if writes and not reads:
                return "write_base_read", {"predicate": "same_node_chain_root_WRITE_without_READ",
                                          "write_event_ids": [c["event_id"] for c in writes]}
    for tag in ("modifier_inlining", "alias"):
        if tag in tags:
            return tag, {"predicate": "sealed_6c_tag", "tag": tag}
    if direction == "FN":
        binding = [d for d in diagnostics if
                   d.get("kind") in ("state_binding_unresolved", "state_binding_excluded")
                   and d.get("name") == event["name"]
                   and overlap([d["start"], d["end"]], event["span"])]
        if binding:
            return "v2_binding_unresolved", {"predicate": "same_name_overlapping_sealed_binding_diagnostic",
                                             "diagnostics": binding}
        assembly = [n for n in ast.assembly if ast.in_node(event, n)]
        if assembly or any(r.get("node_type") == "INLINE ASM" for r in event["evidence"]):
            return "assembly", {"predicate": "INLINE_ASM_or_AST_assembly_containment",
                                "assembly_spans": [ast.interval(n) for n in assembly]}
        skipped = [d for d in diagnostics if d.get("reason", "").startswith("push_pop_write_skipped")
                   and overlap([d["start"], d["end"]], event["span"])]
        if skipped:
            return "push_pop_skipped", {"predicate": "overlapping_sealed_push_pop_write_skipped",
                                       "diagnostics": skipped}
    return "other", {"predicate": "no_prior_mechanical_predicate"}


def _aggregate(metrics_rows):
    result = {key: sum(r[key] for r in metrics_rows)
              for key in ("candidate_count", "reference_count", "matched", "extra", "missing")}
    result["precision"] = result["matched"]/result["candidate_count"] if result["candidate_count"] else None
    result["recall"] = result["matched"]/result["reference_count"] if result["reference_count"] else None
    return result


def compare_file(task, record, raw, audit, source_path, conventions=None, prior_diffs=None):
    functions = record["v2_scope"]["L1"]["functions"]
    ast = SourceFacts(raw.decode("utf8"))
    diagnostics = audit["layers"]["L2"]["files"].get(record["file"], {}).get("diagnostics", [])
    result = dict(file=record["file"], source_sha256=record["source_sha256"],
                  version=record["version"], version_origin=record["version_origin"],
                  status=record["status"], layers={})
    differences = []
    binding_audits = audit["layers"]["L2"]["files"].get(record["file"], {}).get("binding_audits", {})
    for layer in ("L1", "L2"):
        cr = (record["v2_scope"]["L1"]["occurrences"] if layer == "L1" else [
            e for e in audit["layers"]["L2"]["evidence"] if e["file"] == record["file"]])
        rr = [e for e in record["slither_extraction"]["occurrences"] if e["layer"] == layer]
        candidate = _normalize(cr, "v2", layer, raw, functions, ast)
        lexical = candidate
        if layer == "L2":
            candidate = normalize_l2_units(lexical, raw)
        reference = _normalize(rr, "slither", layer, raw, functions, ast)
        matches, extra, missing = match_spans(candidate, reference)
        metric = metrics(candidate, reference, matches)
        # Auxiliary only: comparable alias/modifier-free event sets.
        cc = [e for e in candidate if not (set(e["tags"]) & EXCLUSIONS)]
        rc = [e for e in reference if not (set(e["tags"]) & EXCLUSIONS)]
        cm, _, _ = match_spans(cc, rc)
        line_new = [(c, r) for c, r in matches if c["line"] != r["line"]]
        old_extra = {tuple(f) for f in record["comparison"][layer]["extra"]}
        old_missing = {tuple(f) for f in record["comparison"][layer]["missing"]}
        formerly_both = [(c, r) for c, r in matches
                         if (c["line"], c["name"], c["kind"]) in old_extra and
                            any(tuple(e["fact"]) in old_missing for e in r["evidence"])]
        scopes = {}
        for scope in ("supported", "fallback", "unmapped"):
            scoped_c = [c for c in candidate if c["function_scope"] == scope]
            scoped_r = [r for r in reference if r["function_scope"] == scope]
            scoped_m, _, _ = match_spans(scoped_c, scoped_r)
            scopes[scope] = metrics(scoped_c, scoped_r, scoped_m)
        result["layers"][layer] = dict(
            metrics=metric, excluding_alias_modifier=metrics(cc, rc, cm),
            reference_name_normalizations=[dict(event_id=e["event_id"], evidence=e["name_normalizations"])
                                           for e in reference if e["name_normalizations"]],
            scopes=scopes, line_6c_unchanged={k:v for k,v in record["comparison"][layer].items()
                                         if k not in ("extra", "missing", "excluded")},
            differing_start_line_matched_pairs=len(line_new),
            prior_extra_and_missing_now_matched_pairs=len(formerly_both),
            matches=[dict(candidate=c["event_id"], reference=r["event_id"],
                          candidate_span=c["span"], reference_span=r["span"],
                          name=c["name"], kind=c["kind"], candidate_line=c["line"],
                          reference_line=r["line"],
                          declaration_identity_equal=c["declaration"] == r["declaration"],
                          function_identity_equal=c["function_start"] == r["function_start"])
                     for c,r in matches])
        if layer == "L2" and prior_diffs is not None:
            result["layers"][layer]["unit_comparison"] = unit_comparison(
                lexical, candidate, reference, matches,
                [d for d in prior_diffs if d["layer"] == "L2" and d["direction"] == "FP"])
        for direction, events in (("FP", extra), ("FN", missing)):
            for event in events:
                category, basis = classify(event, direction, ast, candidate, diagnostics)
                suggested_verdict = None
                if category == "other":
                    pattern = classify_pattern(event, direction, ast, candidate, reference,
                                               diagnostics, conventions)
                    if pattern is not None:
                        category, basis, suggested_verdict = pattern
                if category == "v2_binding_unresolved":
                    basis["binding_subtypes"] = audit_binding_unresolved(
                        event, ast, diagnostics, binding_audits)
                    if basis["binding_subtypes"] and all(
                            b["verdict"] == "v2_scope_limit" for b in basis["binding_subtypes"]):
                        suggested_verdict = "v2_scope_limit"
                # Categories remain mechanical descriptions. They are not final
                # semantic verdicts, even where a probe supports the pattern.
                near_c = [e for e in candidate if overlap(e["span"], event["span"])]
                near_r = [e for e in reference if overlap(e["span"], event["span"])]
                ident = _id([task, record["file"], record["source_sha256"], layer, direction, event["event_id"]])
                differences.append(dict(
                    difference_id=ident, task=task, file=record["file"],
                    source_path=str(source_path), source_sha256=record["source_sha256"],
                    version=record["version"], version_origin=record["version_origin"],
                    layer=layer, direction=direction, category=category,
                    event_id=event["event_id"], span=event["span"], name=event["name"],
                    kind=event["kind"], line=event["line"], function_scope=event["function_scope"],
                    source_excerpt=event["source_text"], primary=event,
                    nearby_candidate=near_c, nearby_reference=near_r,
                    classification_evidence=basis, suggested_verdict=suggested_verdict, human_verdict=None))
    return result, differences


def summarize(files, differences):
    result = {}
    for layer in ("L1", "L2"):
        records = [r["layers"][layer] for r in files]
        categories = L1_CATEGORIES if layer == "L1" else L2_CATEGORIES
        summary = dict(metrics=_aggregate([r["metrics"] for r in records]),
            excluding_alias_modifier=_aggregate([r["excluding_alias_modifier"] for r in records]),
            scopes={scope: _aggregate([r["scopes"][scope] for r in records])
                    for scope in ("supported", "fallback", "unmapped")},
            differing_start_line_matched_pairs=sum(r["differing_start_line_matched_pairs"] for r in records),
            prior_extra_and_missing_now_matched_pairs=sum(r["prior_extra_and_missing_now_matched_pairs"] for r in records),
            differences={})
        for direction in ("FP", "FN"):
            rows = [d for d in differences if d["layer"] == layer and d["direction"] == direction]
            summary["differences"][direction] = {
                c: dict(count=sum(d["category"] == c for d in rows),
                        fraction=sum(d["category"] == c for d in rows)/len(rows) if rows else None,
                        example_ids=[d["difference_id"] for d in rows if d["category"] == c][:5])
                for c in categories}
        result[layer] = summary
    return result


def validate_prior_binding(prior, store_sha256, reference_report_sha256):
    if prior.get("version") != "dfg-v2-slither-span-alignment-v3":
        raise ValueError("Expected the immutable v3 alignment as baseline")
    if prior["inputs"]["store"]["sha256"] != store_sha256:
        raise ValueError("Prior alignment store mismatch")
    if prior["inputs"]["report"]["sha256"] != reference_report_sha256:
        raise ValueError("Prior alignment references a different 6c report")


def run(store_path, report_path, output, prior_alignment, conventions_path):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing existing span comparison output: " + str(output))
    path, verification, store, manifest = _load_inputs(store_path)
    report_path = Path(report_path).resolve()
    seal_path = report_path.with_name("report.seal.json")
    seal = _json(seal_path)
    if seal["report_sha256"] != _sha(report_path):
        raise ValueError("Slither report seal mismatch")
    old = _json(report_path)
    if old["store"]["sha256"] != _sha(path) or seal["store_sha256"] != _sha(path):
        raise ValueError("Slither report belongs to a different fixed graph store")
    runtime = {str(p): _sha(p) for p in Path(__file__).parent.glob("*.py")}
    from scripts.DFG import frontend
    runtime[str(Path(frontend.__file__).resolve())] = _sha(frontend.__file__)
    parser_library = {"path": str(library_path()), "sha256": _sha(library_path())}
    inputs = {"store": {"path": str(path), "sha256": _sha(path)},
              "report": {"path": str(report_path), "sha256": _sha(report_path)},
              "report_seal": {"path": str(seal_path), "sha256": _sha(seal_path)}}
    prior_path, conventions_path = Path(prior_alignment).resolve(), Path(conventions_path).resolve()
    prior = _json(prior_path)
    prior_seal_path = prior_path.with_name("report.seal.json")
    if _json(prior_seal_path)["report_sha256"] != _sha(prior_path):
        raise ValueError("Prior alignment seal mismatch")
    validate_prior_binding(prior, _sha(path), _sha(report_path))
    conventions = _json(conventions_path)
    convention_seal = conventions_path.with_name(conventions_path.stem + ".seal.json")
    if _json(convention_seal)["report_sha256"] != _sha(conventions_path):
        raise ValueError("Convention conclusions seal mismatch")
    observation_path = _checked(conventions["observation_report"])
    observation_seal_path = _checked(conventions["observation_seal"])
    if _json(observation_seal_path)["report_sha256"] != _sha(observation_path):
        raise ValueError("Direct probe observation seal mismatch")
    inputs.update(conventions_seal=dict(path=str(convention_seal), sha256=_sha(convention_seal)),
                  convention_observations=conventions["observation_report"],
                  convention_observations_seal=conventions["observation_seal"])
    inputs.update(prior_alignment=dict(path=str(prior_path), sha256=_sha(prior_path)),
                  prior_alignment_seal=dict(path=str(prior_seal_path), sha256=_sha(prior_seal_path)),
                  conventions=dict(path=str(conventions_path), sha256=_sha(conventions_path)))
    result = dict(version=VERSION, inputs=inputs, runtime=runtime,
        parser_library=parser_library, graph_store_verification=verification,
        matching_rule=__doc__, tasks={}, differences=[],
        comparator_only=True, slither_executed=False, analyzer_executed=False,
        training_executed=False, graph_construction_executed=False,
        limitations=[
            "Additional byte-event metrics do not replace sealed 6c line-set metrics.",
            "Greedy span overlap does not establish exact declaration binding or DDG-edge correctness.",
            "L1 structural anchors may cover nested statements; matches record binding equality for audit.",
            "L2 Unit AST statement spans can cover nested bodies; broad-anchor matches remain diagnostic, not exact binding proof.",
            "L1 function_scope inventories are also attached to L2 for continuity; they are not L2 support status.",
            "No classification category alone establishes which implementation is semantically correct.",
            "Unknown/failing files remain excluded exactly as in sealed 6c."])
    for task, task_record in old["tasks"].items():
        audit_ref = store["tasks"][task]["graphs"]["F3"]["audit"]
        audit = _json(_checked(audit_ref))
        files, task_diffs = [], []
        for record in task_record["files"]:
            if record["status"] != "compared":
                continue
            source = manifest["tasks"][task]["sources"][record["file"]]
            source_path = _checked(source)
            if source["sha256"] != record["source_sha256"]:
                raise ValueError("Source identity mismatch for sealed Slither file")
            row, diffs = compare_file(task, record, source_path.read_bytes(), audit, source_path,
                conventions["conventions"], [d for d in prior["differences"] if d["task"] == task and d["file"] == record["file"]])
            files.append(row)
            task_diffs.extend(diffs)
        result["tasks"][task] = dict(
            files=files, summary=summarize(files, task_diffs),
            excluded_files=[{k:r.get(k) for k in ("file", "source_sha256", "status", "reason")}
                            for r in task_record["files"] if r["status"] != "compared"],
            line_6c_unchanged=task_record["summary"],
            by_version_origin={origin: summarize(
                [f for f in files if f["version_origin"] == origin],
                [d for d in task_diffs if d["version_origin"] == origin])
                for origin in ("metadata", "pragma_derived", "fallback_default")},
            audit=audit_ref)
        result["tasks"][task]["prior_alignment_v3_summary"] = prior["tasks"][task]["summary"]
        if result["tasks"][task]["summary"]["L1"]["metrics"] != prior["tasks"][task]["summary"]["L1"]["metrics"]:
            raise ValueError("L1 IR-event metrics changed unexpectedly")
        comparisons = [f["layers"]["L2"]["unit_comparison"] for f in files]
        result["tasks"][task]["unit_correction"] = {
            k: sum(c[k] for c in comparisons) for k in (
                "removed_lexical_event_count", "old_fp_count", "resolved_old_fp_count",
                "duplicate_counting_resolved", "anchor_or_matching_resolved")}
        result["differences"].extend(task_diffs)
        print(json.dumps(dict(task=task, compared=len(files), differences=len(task_diffs))), flush=True)
    for ref in inputs.values():
        _checked(ref)
    for task in result["tasks"]:
        _checked(result["tasks"][task]["audit"])
        for source in manifest["tasks"][task]["sources"].values():
            _checked(source)
    for p, digest in runtime.items():
        if _sha(p) != digest:
            raise ValueError("Comparator runtime changed during execution: " + p)
    _checked(parser_library)
    output.mkdir(parents=True)
    _write_json(output/"report.json", result)
    _write_json(output/"report.seal.json", dict(version=VERSION,
        report_sha256=_sha(output/"report.json"), inputs=inputs,
        runtime=runtime, parser_library=parser_library))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prior-alignment", required=True)
    parser.add_argument("--conventions", required=True)
    args = parser.parse_args(argv)
    result = run(args.store, args.report, args.output, args.prior_alignment, args.conventions)
    print(json.dumps({k:v["summary"] for k,v in result["tasks"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
