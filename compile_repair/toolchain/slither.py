"""PROMPTS 3.8/4.4: profiles, stable D3 facts and deterministic CFG/call storage.

Read crytic-compile's saved AST, never deduplicate nodes, and treat lengths as
diagnostics. The CP0 projection exists solely to verify frozen cp0_v2 evidence.
"""
import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

from compile_repair.toolchain.solc import validate_settings, verify_binary
from compile_repair.toolchain.project import project_command, slither_arguments, verify_project


# D16 approved 2026-11-13; reject every pair outside these explicit profiles.
PROFILES = {"regression_6c": ("0.8.0", "0.2.4"),
            "production": ("0.11.6", "0.4.2")}

# Only Python's qualified object repr is unstable; keep ordinary hex literals.
_OBJECT_REPR = re.compile(r"<([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+) object at 0x[0-9a-fA-F]+>")


def check_profile(name="regression_6c", installed=None):
    """Return the explicit profile and detected versions, or reject a mismatch.

    The installed argument permits pure tests without patching any module.
    Runtime callers omit it so both package versions are actually inspected.
    """
    if name not in PROFILES:
        raise ValueError("Unconfigured Slither profile: " + name)
    if installed is None:
        try:
            from importlib.metadata import version
        except ImportError:  # Python 3.7 regression environment
            from importlib_metadata import version
        installed = (version("slither-analyzer"), version("crytic-compile"))
    if tuple(installed) != PROFILES[name]:
        raise ValueError("Slither profile {} requires {}, installed {}".format(
            name, PROFILES[name], tuple(installed)))
    return {"profile": name, "slither_version": installed[0],
            "crytic_compile_version": installed[1]}


def read_mapping(mapping):
    """Normalize dict/object mappings; reject absent or unsupported containers.

    Recognized mappings may contain missing fields. Those values are retained
    for D3 diagnostics, never mistaken for a valid filename or starting offset.
    """
    if isinstance(mapping, dict):
        return {"filename": mapping.get("filename_absolute"),
                "start": mapping.get("start"), "length": mapping.get("length")}
    if all(hasattr(mapping, name) for name in ("filename", "start", "length")):
        filename = mapping.filename
        if filename is not None and not hasattr(filename, "absolute"):
            raise ValueError("Unsupported source_mapping filename object")
        return {"filename": filename.absolute if filename is not None else None,
                "start": mapping.start, "length": mapping.length}
    raise ValueError("Unsupported or absent source_mapping: " + type(mapping).__name__)


def _input_filename(filename, allowed):
    return (isinstance(filename, str) and Path(filename).is_absolute() and
            str(Path(filename).resolve()) in allowed)


def _declarations(slither):
    from slither.core.declarations.modifier import Modifier
    for contract in slither.contracts:
        for function in contract.functions_and_modifiers_declared:
            yield contract.name, function, "modifier" if isinstance(function, Modifier) else "function"
    # These are lists in the installed 0.8.0 API (recorded in CP0_1_REPORT).
    # Missing attributes are errors, not an assumed absence of free functions.
    for unit in slither.compilation_units:
        for function in unit.functions_top_level:
            yield "<top-level>", function, "top_level_function"


def node_facts(slither, inputs, project_root=None):
    """Return node_facts_v2 and D3(a) diagnostics for every declared CFG node.

    Assign ordinals in original function.nodes order before sorting records.
    NodeType.name is stable across supported API styles; str(NodeType) is not.
    Unsupported mappings raise. Missing mappings or residual object addresses
    fail D3(a); normalized object repr counts and diagnostics are retained.
    """
    allowed = {str(Path(p).resolve()) for p in inputs}
    rows, counts, ir_diagnostics = [], Counter(), []
    for owner, function, kind in _declarations(slither):
        counts["declarations"] += 1
        counts[kind + "s"] += 1
        ordinals = Counter()
        for node in function.nodes:
            mapping = read_mapping(node.source_mapping)
            filename, start = mapping["filename"], mapping["start"]
            counts["nodes"] += 1
            if not filename:
                counts["missing_filename"] += 1
            elif not isinstance(filename, str) or not Path(filename).is_absolute():
                counts["invalid_filename"] += 1
            elif not _input_filename(filename, allowed):
                counts["foreign_filename"] += 1
            if start is None:
                counts["missing_start"] += 1
            node_type = getattr(node.type, "name", str(node.type))
            ordinals[(node_type, start)] += 1
            key5 = [owner, function.full_name, node_type, start, ordinals[(node_type, start)]]
            ir_lines = []
            for index, ir in enumerate(node.irs):
                text, replacements = _OBJECT_REPR.subn(r"<\1>", str(ir))
                counts["ir_object_repr_replacements"] += replacements
                residual = text.count(" object at 0x")
                counts["ir_object_repr_unresolved"] += residual
                if residual:
                    ir_diagnostics.append({"key5": key5, "ir_index": index,
                                           "reason": "Residual object address in IR", "ir": text})
                ir_lines.append(text)
            rows.append({"key5": key5, "ir": ir_lines,
                         "length": mapping["length"], "declaration_kind": kind})
            if project_root is not None:
                rows[-1]["filename"] = _project_filename(filename, project_root)
    for key in ["nodes", "declarations", "functions", "modifiers", "top_level_functions",
                "missing_filename", "invalid_filename", "foreign_filename", "missing_start",
                "ir_object_repr_replacements", "ir_object_repr_unresolved"]:
        counts.setdefault(key, 0)
    key_counts = Counter(json.dumps(r["key5"][:4]) for r in rows)
    return {"node_facts_schema": "node_facts_v2",
            "mapping_complete": not any(counts[k] for k in [
                "missing_filename", "invalid_filename", "foreign_filename", "missing_start",
                "ir_object_repr_unresolved"]),
            "ir_diagnostics": ir_diagnostics,
            "counts": dict(counts), "empty_cfg": counts["nodes"] == 0,
            "duplicate_key4": {k: v for k, v in key_counts.items() if v > 1},
            "nodes": sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))}


def contract_coverage(slither, inputs):
    """Check D3(b) against saved legacy/compact solc AST contract multisets.

    Include interfaces and libraries. Every input needs an observed SourceUnit
    AST; absent or malformed AST data raises instead of yielding an empty pass.
    Names retain their multiplicities across files and compilation units.
    """
    allowed = {str(Path(p).resolve()) for p in inputs}
    expected, actual, seen, evidence = Counter(), Counter(), set(), []
    for unit in slither.crytic_compile.compilation_units.values():
        for filename, tree in unit.asts.items():
            if not _input_filename(filename, allowed):
                continue
            path = str(Path(filename).resolve())
            seen.add(path)
            compact = isinstance(tree, dict) and "nodeType" in tree
            root_kind = tree.get("nodeType" if compact else "name") if isinstance(tree, dict) else None
            children = tree.get("nodes" if compact else "children") if isinstance(tree, dict) else None
            if root_kind != "SourceUnit" or not isinstance(children, list):
                raise ValueError("Missing or malformed SourceUnit AST: " + path)
            names = []
            for child in children:
                if not isinstance(child, dict):
                    raise ValueError("Malformed AST child: " + path)
                if child.get("nodeType" if compact else "name") == "ContractDefinition":
                    name = child.get("name") if compact else child.get("attributes", {}).get("name")
                    if not isinstance(name, str) or not name:
                        raise ValueError("ContractDefinition has no name: " + path)
                    names.append(name)
            expected.update(names)
            evidence.append({"path": path, "format": "compact" if compact else "legacy",
                             "contracts": dict(Counter(names)),
                             "ast_sha256": hashlib.sha256(json.dumps(tree, sort_keys=True).encode("utf8")).hexdigest()})
    if allowed - seen:
        raise ValueError("Input AST not observed: " + ", ".join(sorted(allowed - seen)))
    for contract in slither.contracts:
        mapping = read_mapping(contract.source_mapping)
        if _input_filename(mapping["filename"], allowed):
            actual[contract.name] += 1
    return {"complete": actual == expected, "ast_source": "crytic_compile.compilation_units[*].asts",
            "expected": dict(expected), "actual": dict(actual),
            "missing": dict(expected - actual), "unexpected": dict(actual - expected),
            "asts": evidence}



def _ast_nodes(value):
    """Walk saved compiler nodes, independent of compact versus legacy shape."""
    if isinstance(value, dict):
        if "nodeType" in value or "name" in value:
            yield value
        if value.get("nodeType", value.get("name")) != "FunctionTypeName":
            for child in value.values():
                yield from _ast_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _ast_nodes(child)


def _binding_variables(unit):
    """Enumerate declaration variables, including unnamed parameters/returns."""
    variables = list(unit.variables_top_level)
    functions = list(unit.functions_top_level)
    structures = list(unit.structures_top_level)
    events = list(unit.events_top_level)
    errors = list(unit.custom_errors)
    for contract in unit.contracts:
        variables.extend(contract.state_variables_declared)
        functions.extend(contract.functions_and_modifiers_declared)
        structures.extend(contract.structures_declared)
        events.extend(contract.events_declared)
        errors.extend(contract.custom_errors_declared)
    for function in functions:
        variables.extend(function.variables + function.parameters + function.returns)
    for structure in structures:
        variables.extend(structure.elems_ordered)
    for event in events:
        variables.extend(event.elems)
    for error in errors:
        variables.extend(error.parameters)
    # The public containers overlap. Visit each object once; distinct native
    # objects at the same source position are all checked, never merged.
    seen = set()
    for variable in variables:
        if id(variable) not in seen:
            seen.add(id(variable))
            yield variable


def project_bindings(slither, inputs, root):
    """Check directly declared contract types against saved solc declarations.

    This additional project gate is not D3 or a proof of all Slither semantics.
    Arrays, mappings, expressions and function-type internals are outside its
    direct-type scope. An expected direct binding without inspectable evidence
    fails closed. AST IDs are used only within their own compilation unit.
    """
    from slither.core.declarations.contract import Contract
    allowed = {str(Path(p).resolve()) for p in inputs}
    seen_files, rows = set(), []

    def kind(node):
        return node.get("nodeType", node.get("name"))

    def attrs(node):
        return node if "nodeType" in node else node.get("attributes", {})

    def location(filename, node):
        parts = node["src"].split(":")
        if len(parts) != 3 or any(int(p) < 0 for p in parts):
            raise ValueError("Invalid AST source location")
        return {"filename": _project_filename(filename, root), "start": int(parts[0])}

    def native_location(obj):
        mapping = read_mapping(obj.source_mapping)
        if not isinstance(mapping["start"], int) or mapping["start"] < 0:
            raise ValueError("Missing native declaration offset")
        return {"filename": _project_filename(mapping["filename"], root),
                "start": mapping["start"]}

    for unit_index, unit in enumerate(slither.compilation_units):
        declarations, variables = {}, []
        for filename, tree in unit.crytic_compile_compilation_unit.asts.items():
            if not _input_filename(filename, allowed):
                raise ValueError("Project AST outside declared inputs")
            seen_files.add(str(Path(filename).resolve()))
            if kind(tree) != "SourceUnit":
                raise ValueError("Project binding check requires SourceUnit AST")
            for node in _ast_nodes(tree):
                if "id" in node:
                    if node["id"] in declarations:
                        raise ValueError("Ambiguous AST declaration identity")
                    declarations[node["id"]] = (filename, node)
                if kind(node) == "VariableDeclaration":
                    variables.append((filename, node))
        native = {}
        for variable in _binding_variables(unit):
            try:
                loc = native_location(variable)
            except (ValueError, AttributeError, TypeError):
                # Missing expected positions are reported below. Irrelevant
                # non-contract variables do not broaden this acceptance gate.
                continue
            native.setdefault((loc["filename"], loc["start"]), []).append(variable)
        for filename, node in variables:
            compact = "nodeType" in node
            type_node = node.get("typeName") if compact else next(
                (c for c in node.get("children", []) if kind(c) in (
                    "UserDefinedTypeName", "ElementaryTypeName", "ArrayTypeName",
                    "Mapping", "FunctionTypeName")), None)
            declared_type = (node.get("typeDescriptions", {}).get("typeString", "")
                             if compact else attrs(node).get("type", ""))
            ref = attrs(type_node).get("referencedDeclaration") if type_node else None
            if type_node and kind(type_node) == "UserDefinedTypeName":
                ref = ref if ref is not None else type_node.get("pathNode", {}).get("referencedDeclaration")
                target = declarations.get(ref)
                if target is not None and kind(target[1]) != "ContractDefinition":
                    continue
            elif type_node is None and re.fullmatch(r"contract [^\[\]()]+", declared_type):
                target = None  # Inferred old-style var: no declared reference.
            else:
                continue
            loc = location(filename, node)
            row = dict(compilation_unit=unit_index, variable=attrs(node).get("name"),
                       declaration_id=node.get("id"), location=loc,
                       referenced_declaration=ref, expected=None, actual=[], complete=False)
            if target is None:
                row["reason"] = "unresolved_ast_contract_reference"
            else:
                row["expected"] = location(*target)
                matches = native.get((loc["filename"], loc["start"]), [])
                for variable in matches:
                    contract = getattr(getattr(variable, "type", None), "type", None)
                    try:
                        actual = native_location(contract) if isinstance(contract, Contract) else None
                    except (ValueError, AttributeError, TypeError):
                        actual = None
                    row["actual"].append(actual)
                row["complete"] = bool(matches) and all(x == row["expected"] for x in row["actual"])
                if not row["complete"]:
                    row["reason"] = ("native_variable_not_observed" if not matches else
                                     "native_contract_type_unverifiable" if None in row["actual"] else
                                     "contract_binding_mismatch")
            rows.append(row)
    if allowed - seen_files:
        raise ValueError("Input AST not observed by project binding check")
    return {"schema": "project-contract-bindings-v1", "complete": all(r["complete"] for r in rows),
            "scope": "directly declared contract-typed variables",
            "checked": len(rows), "bindings": rows,
            "ast_source": "crytic_compile.compilation_units[*].asts"}


def cp0_projection_sha256(slither):
    """CP0 projection ONLY for comparison with cp0_v2 invocations.jsonl.

    Preserve CP0's contract-only key4, str(node.type), IR, length, sorting and
    JSON encoding exactly. This is not a new identity or a graph-store schema.
    """
    rows = []
    for contract in slither.contracts:
        for function in contract.functions_and_modifiers_declared:
            for node in function.nodes:
                mapping = read_mapping(node.source_mapping)
                rows.append({"key4": [contract.name, function.full_name, str(node.type), mapping["start"]],
                             "ir": [str(ir) for ir in node.irs], "length": mapping["length"]})
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf8")).hexdigest()


def compare_nodes(left, right):
    """Compare key5 multisets, retaining multiplicity and ordered IR per node."""
    output = {}
    for name, fields in [("key5", ["key5"]), ("slithir", ["key5", "ir"]),
                         ("source_length", ["key5", "length"])]:
        a, b = [Counter(json.dumps([r[k] for k in fields], sort_keys=True) for r in rows)
                for rows in (left, right)]
        output[name] = {"equal": a == b, "only_low": dict(a - b), "only_high": dict(b - a)}
    return output



def _graph_text(value):
    """Normalize object reprs in graph text; fail on unresolved addresses."""
    text = _OBJECT_REPR.sub(r"<\1>", str(value))
    if " object at 0x" in text:
        raise ValueError("Residual object address in graph text")
    return text


def _project_filename(filename, root):
    """Use a project-relative filename as the approved outer key5 namespace."""
    if not isinstance(filename, str) or not Path(filename).is_absolute():
        raise ValueError("Project node requires an absolute source filename")
    return Path(filename).resolve().relative_to(Path(root).resolve()).as_posix()


def _callee(ir, project_root=None):
    from slither.core.declarations.function import Function
    function = getattr(ir, "function", None)
    if isinstance(function, Function):
        owner = getattr(function, "contract_declarer", None)
        result = {"contract": owner.name if owner is not None else "<top-level>",
                  "function": function.full_name}
        if project_root is not None:
            result["filename"] = _project_filename(read_mapping(function.source_mapping)["filename"], project_root)
        return result
    # Dynamic calls, builtins, events, public getters, and contract creation
    # need not resolve to a declared Function. Preserve their normalized IR.
    return {"text": _graph_text(ir)}


def graph_facts(slither, project_root=None):
    """Serialize declared CFGs and every Call in original Slither order.

    Keys use D4 occurrence ordinals. Edges retain sons order and branch kind;
    calls retain node/IR order. Missing endpoints or duplicate identities raise
    rather than producing an incomplete graph. Paths and timings live outside
    this payload, in invocation/manifest records.
    """
    from slither.slithir.operations import (
        Call, InternalCall, LibraryCall, HighLevelCall, LowLevelCall)
    call_kinds = {LibraryCall: "library", InternalCall: "internal",
                  HighLevelCall: "high-level", LowLevelCall: "low-level"}
    result = {"schema": "compile-repair-graph-v1", "declarations": [],
              "nodes": [], "cfg_edges": [], "calls": []}
    if project_root is not None:
        result["schema"] = "compile-repair-project-graph-v1"
    seen = set()
    for owner, function, kind in _declarations(slither):
        result["declarations"].append({"contract": owner, "function": function.full_name,
                                       "declaration_kind": kind})
        if project_root is not None:
            result["declarations"][-1]["filename"] = _project_filename(
                read_mapping(function.source_mapping)["filename"], project_root)
        ordinals, keys = Counter(), {}
        for node in function.nodes:
            mapping = read_mapping(node.source_mapping)
            node_type = getattr(node.type, "name", str(node.type))
            start = mapping["start"]
            ordinals[(node_type, start)] += 1
            key = [owner, function.full_name, node_type, start, ordinals[(node_type, start)]]
            filename = _project_filename(mapping["filename"], project_root) if project_root is not None else None
            identity = (filename, tuple(key)) if project_root is not None else tuple(key)
            if identity in seen:
                raise ValueError("Duplicate graph key5: " + repr(identity))
            seen.add(identity)
            keys[id(node)] = {"filename": filename, "key5": key} if project_root is not None else key
            result["nodes"].append({"key5": key, "node_type": node_type,
                "length": mapping["length"], "ir": [_graph_text(ir) for ir in node.irs],
                "declaration_kind": kind})
            if project_root is not None:
                result["nodes"][-1]["filename"] = filename
        for node in function.nodes:
            key = keys[id(node)]
            sons = node.sons
            if any(id(son) not in keys for son in sons):
                raise ValueError("CFG endpoint outside its declared function")
            conditional = (key["key5"] if project_root is not None else key)[2] in ("IF", "IFLOOP")
            branches = ([(node.son_true, "true"), (node.son_false, "false")]
                        if conditional else [])
            for son in sons:
                edge_kind = "next"
                if conditional:
                    # Consume branch occurrences, not distinct target nodes:
                    # an empty branch can make true and false share a target.
                    match = next((i for i, (target, _) in enumerate(branches)
                                  if son is target), None)
                    if match is None:
                        raise ValueError("Conditional CFG must have one true and one false edge")
                    _, edge_kind = branches.pop(match)
                result["cfg_edges"].append({"source": key, "target": keys[id(son)], "kind": edge_kind})
            if branches:
                raise ValueError("Conditional CFG must have one true and one false edge")
            for index, ir in enumerate(node.irs):
                if isinstance(ir, Call):
                    # Exact type lookup intentionally prevents LibraryCall's
                    # HighLevelCall parent from swallowing library calls.
                    cls = type(ir)
                    result["calls"].append({"node": key, "ir_index": index,
                        "kind": call_kinds.get(cls, cls.__name__),
                        "operation": cls.__name__, "callee": _callee(ir, project_root)})
    return result


def run_slither(compilation, profile="regression_6c", cp0_projection=False, project=None):
    """Construct Slither after observed solc rc=0; report D3(a) and D3(b).

    Regression reuses frozen _compile unchanged. Production retains its
    CryticCompile object to observe the platform even if Slither parsing fails.
    Slither/crytic subprocess return codes are
    not exposed: bind the observed preceding solc result, never invent a code.
    Profile, integrity and unsafe regression_6c working directories raise
    before execution; analysis failures return diagnostics.
    """
    settings = validate_settings(compilation.settings)
    if project is not None:
        if profile != "production":
            raise ValueError("Project compilation requires production profile")
        verify_project(project)
        if list(compilation.command) != project_command(project, compilation.compiler, settings):
            raise ValueError("Project Slither parameters differ from observed solc")
    if profile == "regression_6c" and settings:
        raise ValueError("regression_6c does not accept compiler settings")
    if profile == "regression_6c":
        cwd = Path.cwd().resolve()
        source = Path(compilation.source_path).resolve()
        if cwd == Path(cwd.anchor) or (
                str(source).startswith(str(cwd)) and cwd not in source.parents):
            raise ValueError(
                "regression_6c refuses unsafe working directory for frozen "
                "crytic-compile 0.2.4: " + str(cwd))
    versions = check_profile(profile)
    if cp0_projection and profile != "regression_6c":
        raise ValueError("CP0 projection requires regression_6c")
    if compilation.returncode != 0 or compilation.timed_out:
        raise ValueError("D3 requires an observed successful solc invocation")
    from scripts.DFG.dfg_v2.validate_slither import _compile
    path, compiler = Path(compilation.source_path), compilation.compiler
    if hashlib.sha256(path.read_bytes()).hexdigest() != compilation.source_sha256:
        raise ValueError("Slither input differs from compiled source")
    verify_binary(compiler)
    result = dict(versions, source_path=str(path), source_sha256=compilation.source_sha256,
                  version=compiler.version, compiler_sha256=compiler.sha256, settings=settings,
                  command={"api": "Slither", "target": str(path),
                           "solc": compiler.path, "solc_disable_warnings": True},
                  equivalent_solc_argv=compilation.command,
                  preceding_observed_solc_returncode=compilation.returncode,
                  api_subprocess_returncodes_observed=False, cost_usd=0.0,
                  crytic_compile_platform=None, crytic_compile_platform_class=None,
                  constructed=False, d3=False, d3_a=False, d3_b=False, nodes=[],
                  node_facts_schema="node_facts_v2")
    if settings:
        result["command"]["solc_args"] = " ".join(settings)
    inputs = [Path(f.path) for f in project.files] if project is not None else [path]
    project_root = project.root if project is not None else None
    if project is not None:
        target, kwargs = slither_arguments(project, compiler, settings)
        result["command"].update(target=target, **kwargs)
        result["project"] = project.manifest()
    start = time.monotonic()
    try:
        if profile == "production":
            # Compose the same public constructors/kwargs as Slither(str(path)).
            # Retain the compiled object so a known parser AssertionError does
            # not erase evidence of the platform actually used.
            from crytic_compile import CryticCompile
            from slither import Slither
            if project is None:
                target = str(path)
                kwargs = {"solc": compiler.path, "solc_disable_warnings": True}
                if settings:
                    kwargs["solc_args"] = result["command"]["solc_args"]
            crytic = CryticCompile(target, **kwargs)
            result["crytic_compile_platform"] = crytic.platform.NAME
            result["crytic_compile_platform_class"] = type(crytic.platform).__module__ + "." + type(crytic.platform).__name__
            result["command"]["construction"] = "CryticCompile(target, **kwargs); Slither(crytic, **kwargs)"
            slither = Slither(crytic, **kwargs)
        else:
            slither = _compile(path, compiler.path)
            result["crytic_compile_platform"] = slither.crytic_compile.platform.NAME
            result["crytic_compile_platform_class"] = type(slither.crytic_compile.platform).__module__ + "." + type(slither.crytic_compile.platform).__name__
        result["constructed"] = True
        # Check both clauses independently, retaining either diagnostic even
        # when the other cannot be inspected (e.g. an unreadable node mapping).
        errors = []
        for clause, inspect in [("a", lambda: node_facts(slither, inputs, project_root)),
                                ("b", lambda: contract_coverage(slither, inputs))]:
            try:
                facts = inspect()
                if clause == "a":
                    result.update(facts)
                    result["d3_a"] = facts["mapping_complete"]
                else:
                    result["contract_coverage"] = facts
                    result["d3_b"] = facts["complete"]
                if not result["d3_" + clause]:
                    errors.append("D3(" + clause + ") incomplete")
                    if clause == "a" and facts["ir_diagnostics"]:
                        errors.append("D3(a): residual object address in IR; see ir_diagnostics")
            except (ValueError, AttributeError, TypeError) as exc:
                errors.append("D3({}): {}: {}".format(clause, type(exc).__name__, str(exc)))
        if cp0_projection and result["d3_a"]:
            result["cp0_projection_sha256"] = cp0_projection_sha256(slither)
        result["d3"] = result["d3_a"] and result["d3_b"]
        result["error_first_line"] = errors[0].splitlines()[0] if errors else None
        result["validation_errors"] = errors
    except Exception as exc:
        result.update({"d3": False, "exception_type": type(exc).__name__,
                       "error_first_line": str(exc).splitlines()[0] if str(exc) else type(exc).__name__,
                       "detail": str(exc)})
    if project is not None:
        result["project_binding"] = {"complete": False, "reason": "slither_not_constructed"}
        if result["constructed"]:
            try:
                result["project_binding"] = project_bindings(slither, inputs, project_root)
            except (ValueError, AttributeError, TypeError, KeyError) as exc:
                result["project_binding"] = {
                    "complete": False, "reason": "binding_check_unverifiable",
                    "exception_type": type(exc).__name__, "detail": str(exc)}
        result["graph_usable"] = result["d3"] and result["project_binding"]["complete"]
    if profile == "production" and result["d3"] and result.get("graph_usable", True):
        result["graph"] = graph_facts(slither, project_root)
    result["elapsed_seconds"] = time.monotonic() - start
    if hashlib.sha256(path.read_bytes()).hexdigest() != compilation.source_sha256:
        raise ValueError("Source changed during Slither analysis")
    if project is not None:
        verify_project(project)
    verify_binary(compiler)
    return result
