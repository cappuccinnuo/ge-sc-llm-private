"""Prompt 5.0 read-only raw-AST grammar-shape audit.

This module never invokes an augmenter, model, compiler, tokenizer, graph
deserializer or trainer. It records candidates, not corrected semantics. Known
declaration/type contexts are excluded explicitly; source names are classified
with the existing conservative StateBinder only to prioritize review.
"""
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from scripts.DFG.frontend import text, walk
from scripts.DFG.models import Unsupported
from scripts.DFG.state.stage_f.versioning import recorded_version
from scripts.DFG.integration.io import checked, read_json, sha256, write_json
from .projection_view import ProjectionView
from .state_binding import StateBinder, CALLABLE_TYPES, chain_root

VERSION = "dfg-v2-grammar-shape-audit-v1"
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/l3_build"
DEFAULT_OUTPUT = ROOT / "scripts/DFG/experiments/artifacts/dfg_v2/prompt5_v1/grammar_shape_audit"
SLOTS = {
    "call_expression": "function",
    "member_expression": "object",
    "array_access": "base",
}
WRAPPERS = {"binary_expression": "right", "unary_expression": "argument"}
TYPE_CONTEXTS = frozenset((
    "type_name", "primitive_type", "inheritance_specifier", "using_directive",
    "override_specifier", "modifier_invocation", "import_directive",
    "struct_member", "enum_value", "event_parameter", "error_parameter",
))
DECLARATIONS = frozenset((
    "variable_declaration", "parameter", "state_variable_declaration",
    "constant_variable_declaration", "function_definition",
    "struct_declaration", "contract_declaration", "library_declaration",
    "interface_declaration", "modifier_definition",
))


def describe(view, node):
    return dict(file=view.file, start=node.start_byte, end=node.end_byte,
                line=node.start_point[0] + 1, column=node.start_point[1] + 1,
                end_line=node.end_point[0] + 1, ast_type=node.type,
                text=text(view.source, node),
                parent_type=node.parent.type if node.parent is not None else None)


def owner_of(node):
    while node is not None:
        if node.type in CALLABLE_TYPES or node.type == "state_variable_declaration":
            return node
        node = node.parent
    return None


def operator(view, node):
    op = node.child_by_field_name("operator")
    if op is not None:
        return text(view.source, op)
    return "unknown"


def trailing_operand(node):
    """Audit exact unparenthesized tail shapes, without normalizing the tree."""
    steps = []
    while node is not None and node.type in WRAPPERS:
        field = WRAPPERS[node.type]
        child = node.child_by_field_name(field)
        if child is None or child.end_byte != node.end_byte:
            return None, steps
        steps.append(node)
        node = child
    return node, steps


def _postfix_chain_contains(node, target):
    while node is not None:
        if node == target:
            return True
        field = {"member_expression": "object", "array_access": "base"}.get(node.type)
        if field is None:
            return False
        node = node.child_by_field_name(field)
    return False


def swallowed_push_pop(view, outer, shaped_slot):
    """Find affected method-call candidates; names alone do not prove arrays."""
    found = {}
    if outer.type == "call_expression":
        tail, _ = trailing_operand(shaped_slot)
        if tail is not None and tail.type == "member_expression":
            prop = tail.child_by_field_name("property")
            if prop is not None and text(view.source, prop) in ("push", "pop"):
                found[(outer.start_byte, outer.end_byte)] = (outer, tail)
    cursor = outer
    while cursor.parent is not None:
        parent = cursor.parent
        if parent.type == "call_expression" and parent.child_by_field_name("function") == cursor:
            if cursor.type == "member_expression":
                prop = cursor.child_by_field_name("property")
                if prop is not None and text(view.source, prop) in ("push", "pop"):
                    if _postfix_chain_contains(cursor, outer):
                        found[(parent.start_byte, parent.end_byte)] = (parent, cursor)
            break
        if (parent.type in ("member_expression", "array_access")
                and parent.child_by_field_name(SLOTS[parent.type]) == cursor):
            cursor = parent
            continue
        break
    return list(found.values())


def type_position_reason(node):
    """Discard type/declaration syntax, not arbitrary enclosing declarations.

    Stop at expression wrappers; a variable initializer remains an expression
    even though its owner is a declaration. A modifier argument similarly is
    not the modifier-name field.
    """
    cursor = node
    while cursor.parent is not None:
        parent = cursor.parent
        if parent.type in TYPE_CONTEXTS:
            return "declaration_or_type_parent:" + parent.type
        if parent.child_by_field_name("name") == cursor:
            return "name_field:" + parent.type
        if parent.type in DECLARATIONS and parent.child_by_field_name("type") == cursor:
            return "declared_type_field:" + parent.type
        if parent.type == "new_expression":
            return "new_type_expression"
        if parent.type not in ("user_defined_type", "identifier"):
            break
        cursor = parent
    return None


def _prefix(view, node, binder):
    identifiers = [n for n in walk(node) if n.type == "identifier"]
    first = text(view.source, identifiers[0]) if identifiers else text(view.source, node).split(".")[0].strip()
    # A dotted user-defined-type path has identifier segments even when
    # legal whitespace/comments separate the dot; raw startswith misses it.
    env = first in ("msg", "tx", "block") and len(identifiers) > 1
    local = bool(binder is not None and first in binder.locals)
    states = (binder.members.get(first, ()) if binder is not None else ())
    state = any(n.type == "state_variable_declaration" for n in states)
    alias = bool(binder is not None and first in binder.aliases)
    shadow = local or bool(states)
    return dict(first_segment=first, environment_prefix=env,
                state_name_prefix=state, local_name_prefix=local,
                storage_alias_prefix=alias, environment_shadowed=env and shadow,
                possible_L1=local,
                possible_L2=state or alias,
                possible_L3=env and not shadow)


def audit_source(source, file, metadata=None):
    """Read only one source with ProjectionView's original/raw AST."""
    view = ProjectionView(source, file)
    binders = {}
    def binder_for(node):
        owner = owner_of(node)
        if owner is None:
            return None
        key = (owner.start_byte, owner.end_byte, owner.type)
        if key not in binders:
            binders[key] = StateBinder(view, owner, metadata=metadata)
        return binders[key]
    shapes, types, exclusions, push_pop = [], [], Counter(), {}
    for node in walk(view.tree.root_node):
        field = SLOTS.get(node.type)
        target = node.child_by_field_name(field) if field is not None else None
        if target is not None and target.type in WRAPPERS:
            tail, steps = trailing_operand(target)
            record = dict(describe(view, node), slot=field,
                          slot_span=describe(view, target),
                          wrapper_type=target.type, operator=operator(view, target),
                          tail=describe(view, tail) if tail is not None else None,
                          wrapper_chain=[dict(describe(view, n), operator=operator(view, n))
                                         for n in steps],
                          push_pop_calls=[])
            for call, member in swallowed_push_pop(view, node, target):
                identity = (call.start_byte, call.end_byte)
                prop = member.child_by_field_name("property")
                receiver = member.child_by_field_name("object")
                binder = binder_for(call)
                confirmed, reason = (binder.array_receiver(receiver) if binder is not None
                                     else (False, "no_callable_or_state_owner"))
                root = chain_root(receiver)
                entry = push_pop.setdefault(identity, dict(
                    describe(view, call), method=text(view.source, prop),
                    receiver=describe(view, receiver),
                    receiver_root=text(view.source, root) if root is not None else None,
                    existing_array_receiver_confirmed=confirmed,
                    existing_array_receiver_reason=reason,
                    affected_shapes=[],
                    requires_review=True,
                    note="Method spelling candidate, not proof of a legal storage mutation"))
                entry["affected_shapes"].append(dict(start=node.start_byte, end=node.end_byte,
                                                     ast_type=node.type, slot=field))
                record["push_pop_calls"].append(dict(start=call.start_byte, end=call.end_byte))
            shapes.append(record)
        if node.type != "user_defined_type":
            continue
        exclusion = type_position_reason(node)
        if exclusion is not None:
            exclusions[exclusion] += 1
            continue
        flags = _prefix(view, node, binder_for(node))
        owner = owner_of(node)
        types.append(dict(describe(view, node), **flags,
                          callable_start=owner.start_byte if owner is not None else None,
                          callable_type=owner.type if owner is not None else None))
    shape_counts = Counter((r["ast_type"], r["wrapper_type"], r["operator"]) for r in shapes)
    possible_types = [r for r in types if r["possible_L2"] or r["possible_L3"]]
    return dict(file=file, source_sha256=view.sha256, raw_ast=True,
                postfix_shapes=shapes,
                shape_counts=[dict(outer_type=k[0], wrapper_type=k[1], operator=k[2], count=v)
                              for k,v in sorted(shape_counts.items())],
                swallowed_push_pop=list(push_pop.values()),
                expression_user_defined_types=types,
                user_defined_type_excluded=dict(sorted(exclusions.items())),
                summary=dict(
                    postfix_shapes=len(shapes), swallowed_push_pop=len(push_pop),
                    expression_user_defined_types=len(types),
                    environment_prefix=sum(r["environment_prefix"] for r in types),
                    state_name_prefix=sum(r["state_name_prefix"] for r in types),
                    local_name_prefix=sum(r["local_name_prefix"] for r in types),
                    storage_alias_prefix=sum(r["storage_alias_prefix"] for r in types),
                    possible_L1=sum(r["possible_L1"] for r in types),
                    possible_L2=sum(r["possible_L2"] for r in types),
                    possible_L3=sum(r["possible_L3"] for r in types),
                    possible_L2_L3_types=len(possible_types),
                    requires_user_decision=bool(push_pop or possible_types)),
                labels_used=False, features_used=False, graph_loaded=False,
                compiler_validation="not_performed")


def frozen_inputs(directory):
    """Bind source inputs to accepted L3 receipt without deserializing graphs."""
    directory = Path(directory).resolve()
    receipt_path = directory / "receipt.json"
    receipt = read_json(receipt_path)
    if receipt.get("status") != "accepted" or receipt.get("training_executed") is not False:
        raise ValueError("Expected accepted nontraining L3 receipt")
    if receipt.get("optimizer_steps") != 0:
        raise ValueError("Expected zero optimizer steps")
    summary_path = checked(directory / "summary.json", receipt["summary_sha256"])
    summary = read_json(summary_path)
    if summary.get("all_acceptance_passed") is not True or summary.get("profiles") != ["G3","G3R"]:
        raise ValueError("Expected accepted G3/G3R summary")
    tasks = {}
    rows = {r["task_id"]:r for r in summary["tasks"]}
    if len(rows) != len(summary["tasks"]) or set(rows) != set(receipt["task_manifests"]):
        raise ValueError("L3 task matrix differs")
    for task, digest in receipt["task_manifests"].items():
        td = directory / task
        manifest_path = checked(td / "manifest.json", digest)
        manifest = read_json(manifest_path)
        if manifest != rows[task]["bundle"] or manifest.get("layer") != "L3":
            raise ValueError("Task manifest differs from accepted L3 summary")
        input_path = checked(td / "inputs.json", manifest["files"]["inputs"])
        inputs = read_json(input_path)
        checked(inputs["source_manifest"], inputs["source_manifest_sha256"])
        checked(inputs["task_manifest"], inputs["task_manifest_sha256"])
        sources = inputs["sources"]
        if not isinstance(sources, dict) or not sources:
            raise ValueError("Missing exact source identities")
        records = {}
        for file, ref in sources.items():
            source_path = checked(ref["path"], ref["sha256"])
            metadata = ref.get("metadata")
            metadata_assets = {}
            if metadata is not None:
                if not isinstance(metadata, dict):
                    raise ValueError("Version metadata must be a mapping")
                for prefix in ("csv", "source"):
                    path_key, sha_key = prefix + "_path", prefix + "_sha256"
                    if path_key not in metadata or sha_key not in metadata:
                        raise ValueError("Missing version metadata asset: " + prefix)
                    asset = checked(metadata[path_key], metadata[sha_key])
                    metadata_assets[prefix] = dict(path=str(asset), sha256=metadata[sha_key])
                if metadata["source_sha256"] != ref["sha256"]:
                    raise ValueError("Version evidence belongs to a different source")
                # Do not let StateBinder's conservative fallback hide invalid
                # CSV rows/path identities behind mode=None during the audit.
                recorded_version(source_path.read_bytes().decode("utf8"), metadata)
            records[file] = dict(ref, path=str(source_path), metadata_assets=metadata_assets)
        tasks[task] = dict(sources=records, manifest=str(manifest_path),
                           manifest_sha256=digest, inputs=str(input_path),
                           inputs_sha256=manifest["files"]["inputs"])
    return tasks, dict(directory=str(directory), receipt_sha256=sha256(receipt_path),
                       summary_sha256=receipt["summary_sha256"],
                       task_manifests=receipt["task_manifests"])


def run(output=DEFAULT_OUTPUT, l3_directory=DEFAULT_INPUT):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Refusing to overwrite " + str(output))
    tasks, binding = frozen_inputs(l3_directory)
    runtime = {str(p.relative_to(ROOT)):sha256(p) for p in (
        Path(__file__).resolve(),
        ROOT/"scripts/DFG/frontend.py",
        ROOT/"scripts/DFG/dfg_v2/projection_view.py",
        ROOT/"scripts/DFG/dfg_v2/state_binding.py",
        ROOT/"scripts/DFG/state/stage_j/binding.py",
        ROOT/"scripts/DFG/state/stage_f/versioning.py",
    )}
    output.mkdir(parents=True)
    write_json(output/"inputs.json", dict(L3=binding, tasks=tasks, runtime=runtime,
                                         graph_deserialized=False))
    all_rows = []
    identities = set()
    findings = []
    for task, rec in tasks.items():
        print(task + ": raw AST grammar audit", flush=True)
        records, errors = {}, []
        for file, ref in sorted(rec["sources"].items()):
            path = checked(ref["path"], ref["sha256"])
            identities.add((str(path), ref["sha256"]))
            try:
                record = audit_source(path.read_bytes().decode("utf8"), file, ref.get("metadata"))
            except (Unsupported, UnicodeError) as exc:
                errors.append(dict(file=file, source_sha256=ref["sha256"], reason=str(exc)))
                continue
            if record["source_sha256"] != ref["sha256"]:
                raise ValueError("Decoded source differs from frozen source")
            records[file] = record
            if record["summary"]["requires_user_decision"]:
                findings.append(dict(task=task, file=file, summary=record["summary"]))
                print("REVIEW REQUIRED: " + task + "/" + file, flush=True)
        counts = Counter()
        shape_counts = Counter()
        for rec_file in records.values():
            for name, value in rec_file["summary"].items():
                if name != "requires_user_decision":
                    counts[name] += value
            for shape in rec_file["shape_counts"]:
                shape_counts[(shape["outer_type"],shape["wrapper_type"],shape["operator"])] += shape["count"]
        data = dict(task_id=task, source_files=len(rec["sources"]), audited_files=len(records),
                    failures=errors, records=records, counts=dict(counts),
                    shape_counts=[dict(outer_type=k[0],wrapper_type=k[1],operator=k[2],count=v)
                                  for k,v in sorted(shape_counts.items())],
                    requires_user_decision=bool(errors or any(
                        r["summary"]["requires_user_decision"] for r in records.values())))
        path = output / (task + ".json")
        write_json(path, data)
        all_rows.append(dict(task_id=task, source_files=len(rec["sources"]), audited_files=len(records),
                             failures=len(errors), counts=dict(counts),
                             requires_user_decision=data["requires_user_decision"],
                             report=str(path), report_sha256=sha256(path)))
    # Source bytes and bound metadata are checked again; no mutable input
    # changes are hidden behind a successful audit receipt.
    tasks_after, binding_after = frozen_inputs(l3_directory)
    if tasks_after != tasks or binding_after != binding:
        raise ValueError("Frozen audit inputs changed during audit")
    for name,digest in runtime.items():
        checked(ROOT/name,digest)
    summary = dict(version=VERSION, tasks=all_rows, unique_source_path_sha_pairs=len(identities),
                   task_file_instances=sum(r["source_files"] for r in all_rows),
                   requires_user_decision=any(r["requires_user_decision"] for r in all_rows),
                   findings=findings, labels_used=False, features_used=False,
                   graph_deserialized=False, analysis_modified=False,
                   training_executed=False, optimizer_steps=0,
                   compiler_validation="not_performed", runtime=runtime)
    write_json(output/"summary.json", summary)
    write_json(output/"receipt.json", dict(
        version=VERSION, status="requires_user_decision" if summary["requires_user_decision"] else "completed_no_blocking_candidates",
        L3=binding, inputs_sha256=sha256(output/"inputs.json"),
        summary_sha256=sha256(output/"summary.json"), runtime=runtime,
        training_executed=False, optimizer_steps=0, graphs_modified=False,
        analyzers_modified=False))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--l3-directory", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    result = run(args.output, args.l3_directory)
    print(json.dumps({k:result[k] for k in ("task_file_instances","unique_source_path_sha_pairs","requires_user_decision")}, indent=2))
    return 2 if result["requires_user_decision"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
