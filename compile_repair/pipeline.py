"""PROMPTS 3.1: one compiler, project assembly and dependency repair entry.

Files, snippets and CP3 project closures share one version/settings loop.
Copies and invocation records live in an exclusive store. Tool integrity failures stop the batch without retry.
"""
import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

from compile_repair.core.model import CompilationUnit, ManifestRecord, Patch, SourceFile
from compile_repair.core.provenance import apply_patches, mark_span, verify_provenance
from compile_repair.core.store import ArtifactStore, emit, sha256
from compile_repair.agents.stage1 import agent_from_config
from compile_repair.rules.dependencies import (OfflineIndex, build_index, dependency_choices,
    chain_relative_issues, relative_repairs)
from compile_repair.rules.normalize import migration_versions, normalization_repairs, slither_compat_repairs, slither_rewrite_applicable
from compile_repair.rules.stubs import structure_repairs, stub_repairs
from compile_repair.rules.environment import (disjunction_plan, make_plan, mando_known_version,
    codegen_only_retry, ordered_candidates, pragma_patches, settings_retry)
from compile_repair.toolchain.solc import (classify_diagnostic, compile_ast_only, compile_file, load_trusted_compilers,
    version_tuple,
    parse_diagnostics)
from compile_repair.toolchain.slither import check_profile, run_slither
from compile_repair.toolchain.project import (compile_project, materialize_project,
    verify_project, resolve_project, ProjectIndex, parse_remapping, input_format_evidence,
    assembly_remappings, unpack_sources)
from scripts.DFG.models import Unsupported


# Selected on the CP5.1 development split. Explicit None leaves calibration uncapped.
DEFAULT_DEPENDENCY_POLICY = "oldest"
DEFAULT_DEPENDENCY_LIMIT = 21
RELATIVE_CHAIN_LIMIT = 4


def _environment(unit, compilers, store, journal, order, compile_fn, slither_fn, project,
                 project_compile_fn, prefix, initial_settings=(), origins=None, allow_override=True, already_copied=False,
                 permit_compile=True):
    """Attempt one file or project using the same version/settings policy.

    Project imports are assembled without dependency repair. All input copies,
    provenance maps and D3 checks cover the closure, not only the entry file.
    """
    if project is None and len(unit.sources) != 1:
        raise ValueError("Multiple sources require an explicit project context")
    if project is not None:
        verify_project(project)
        if tuple(unit.sources) != project.files:
            raise ValueError("Unit sources differ from resolved project")
    source = unit.sources[0]
    inputs = [{"path": f.path, "sha256": f.sha256, "bytes": len(f.content), "kind": f.kind}
              for f in unit.sources]
    for f in unit.sources:
        if hashlib.sha256(f.content).hexdigest() != f.sha256:
            raise ValueError("Input record SHA256 mismatch")
    working, maps, originals = {}, {}, {}
    for f in unit.sources:
        name = Path(f.path).relative_to(project.root).as_posix() if project else f.path
        original, patches = (origins or {}).get(name, (f.content, ()))
        working[f.path], maps[f.path] = apply_patches(original, patches)
        originals[f.path] = original
        if working[f.path] != f.content:
            raise ValueError("Candidate contents differ from the recorded changes")
    record = ManifestRecord(unit.unit_id, inputs, "unrepaired", "no_candidate_compiler",
                            None, None, (), [], [], dict(maps))
    language, wrapper = input_format_evidence(source.content)
    inputs[0]["language_evidence"] = language
    if wrapper is not None or language["status"] == "non_solidity":
        record.reason = "standard_json_input" if wrapper is not None else "non_solidity_input"
        details = wrapper if wrapper is not None else language
        record.attempts.append(dict(details, stage="input_format"))
        return record
    if project is not None:
        store.write_json(prefix + "project.json", project.manifest())
        if project.issues:
            record.reason = "unresolved_imports"
            record.attempts.append({"stage": "project_assembly", "issues": project.issues})
            return record
        work_project = project if already_copied else materialize_project(project, store, prefix + "input_project", working)
        path = Path(work_project.root) / project.entry
    else:
        path = store.write_bytes(prefix + "input.sol", working[source.path])
    try:
        plan = make_plan([f.content for f in unit.sources], compilers,
                         unit.known_version, unit.regression, order)
    except Unsupported as exc:
        plan, error = None, exc
        if any(b"||" in f.content for f in unit.sources):
            # D6 unsupported_disjunction (CP6.5): union of the alternatives; a malformed
            # alternative keeps the frozen reader's rejection.
            try:
                plan = disjunction_plan([f.content for f in unit.sources], compilers, unit.known_version, order)
            except Unsupported:
                plan = None
        if plan is None:
            record.flags.append("unsupported_version_constraints")
            record.attempts.append({"stage": "environment_plan", "exception_type": type(error).__name__,
                                    "error_first_line": str(error).splitlines()[0]})
            return record
    record.plan = plan
    record.flags.extend(plan.flags)
    if plan.override and not allow_override:
        record.attempts.append(dict(stage="environment_plan", error_first_line="No supported compiler in the declared intersection"))
        return record
    if plan.override and any(plan.groups):
        count = 0
        for f in unit.sources:
            patches = pragma_patches(f.content)
            count += len(patches)
            # In a repair trial the file already carries earlier changes: record the override
            # after them, against the original bytes (CP6.4).
            name = Path(f.path).relative_to(project.root).as_posix() if project else f.path
            original, previous = (origins or {}).get(name, (f.content, ()))
            working[f.path], maps[f.path] = apply_patches(original, tuple(previous) + tuple(patches))
            verify_provenance(original, working[f.path], maps[f.path])
        if not count:
            raise ValueError("Override plan has no Solidity pragma to replace")
        if project is not None:
            work_project = materialize_project(project, store, prefix + "pragma_overridden_project", working)
            path = Path(work_project.root) / project.entry
        else:
            path = store.write_bytes(prefix + "pragma_overridden.sol", working[source.path])
        record.flags.append("pragma_overridden")
        record.provenance.update(maps)
    relative_maps = ({Path(f.path).relative_to(project.root).as_posix(): maps[f.path]
                      for f in unit.sources} if project is not None else {})
    any_solc_success = False
    base_series = tuple(plan.effective_interval[0][:2])
    for version in ordered_candidates(plan):
        if not permit_compile:
            record.reason = "dependency_combination_limit"
            return record
        crossed = not plan.override and version != plan.priority and version_tuple(version)[:2] != base_series
        if crossed and "crossed_minor" not in record.flags:
            record.flags.append("crossed_minor")
        settings, retry, output = initial_settings, None, "combined_json"
        for retry_number in range(3):
            if output == "ast_only":
                # Step 9 (CP6.4): the same sources without code generation.
                compiled = compile_ast_only(path, compilers[version],
                                            project=work_project if project is not None else None)
            else:
                compiled = (project_compile_fn(work_project, compilers[version], settings=settings)
                            if project is not None else compile_fn(path, compilers[version], settings=settings))
            attempt = {"version": version, "settings": settings, "output": output, "stage": "environment",
                       "round": len(record.attempts) + 1, "settings_retry": retry,
                       "crossed_minor": crossed, "solc": asdict(compiled), "slither": None}
            record.attempts.append(attempt)
            emit(journal, dict(kind="solc", unit_id=unit.unit_id, **asdict(compiled)))
            if compiled.timed_out:
                record.reason = "solc_timeout"
                break
            if compiled.returncode == 0:
                any_solc_success = True
                analysis = (slither_fn(compiled, profile="production", project=work_project)
                            if project is not None else slither_fn(compiled, profile="production"))
                emit(journal, dict(kind="slither", unit_id=unit.unit_id,
                                  **{k: v for k, v in analysis.items() if k != "graph"}))
                attempt["slither"] = {k: v for k, v in analysis.items() if k not in ("nodes", "graph")}
                if analysis["d3"] and (project is None or analysis["graph_usable"]):
                    def mark(node):
                        provenance = relative_maps[node["filename"]] if project is not None else maps[source.path]
                        return dict(node, provenance=mark_span(provenance, node["key5"][3], node["length"]))
                    marked = [mark(node) for node in analysis["nodes"]]
                    graph = dict(analysis["graph"])
                    graph["nodes"] = [mark(node) for node in graph["nodes"]]
                    graph_path = store.write_json(prefix + "graph.json", graph)
                    attempt["slither"]["graph_sha256"] = sha256(graph_path)
                    nodes = {"schema": "cp1-marked-node-facts-v1", "input_sha256": source.sha256,
                             "working_sha256": compiled.source_sha256, "nodes": marked,
                             "note": "Ordered CFG edges and calls are stored in graph.json"}
                    if project is not None:
                        nodes.update(schema="cp3-project-marked-node-facts-v1",
                                     input_files=inputs, working_files=work_project.manifest()["files"])
                    store.write_json(prefix + "nodes.json", nodes)
                    record.status, record.reason = "success", None
                    record.selected_version, record.settings = version, settings
                    if output == "ast_only":
                        record.flags.append("ast_only_compilation")
                    elif retry is not None:
                        record.flags.append("compiler_settings_retry")
                    break
                break
            retry_source = working[source.path]
            if project is not None:
                # Existing location-sensitive retry must inspect the file that
                # owns the first located error, never an unrelated entry token.
                located = next((d for d in parse_diagnostics(compiled.stderr)
                                if d["kind"] != "Warning" and d["filename"]), None)
                retry_source = b""
                if located:
                    target = (Path(work_project.root) / located["filename"]).resolve()
                    retry_source = next((f.content for f in work_project.files
                                         if Path(f.path).resolve() == target), b"")
            retry = settings_retry(compiled, retry_source) if retry_number == 0 else None
            if retry is None or retry["settings"][0] in initial_settings:
                retry = codegen_only_retry(compiled) if output == "combined_json" else None
                if retry is None:
                    break
                output, settings = "ast_only", ()
                continue
            settings = initial_settings + tuple(retry["settings"])
        if record.status == "success" or record.reason == "solc_timeout":
            break
    if record.status != "success" and record.attempts and record.reason != "solc_timeout":
        record.reason = "slither_side_failure" if any_solc_success else "all_solc_candidates_failed"
        if any_solc_success:
            record.flags.append("Slither 侧失败")
    for f in unit.sources:
        current = (Path(work_project.root) / Path(f.path).relative_to(project.root)).read_bytes() if project is not None else path.read_bytes()
        verify_provenance(originals[f.path], current, maps[f.path])
    if project is not None:
        verify_project(project)
    return record


_DEPENDENCY_FAILURES = {"unresolved_package_import", "missing_relative_file", "standard_json_input",
                        "io_error", "closure_version_conflict"}
# Categories with a step-5 rule (CP6.1); they also open the deterministic repair loop.
_NORMALIZATION_FAILURES = {"duplicate_definition", "multiple_license_or_pragma", "abi_coder_required",
                           "unterminated_pragma", "pragma_missing_semicolon_candidate",
                           "docstring_error"}
# Categories with a step-7 rule (CP6.3).
_STUB_FAILURES = {"undeclared_identifier", "missing_base_contract"}
# Categories with a step-8 rule (CP6.2).
_STRUCTURE_FAILURES = {"unbalanced_structure", "parser_error_other", "file_level_member"}
# D27: the compiler phase that reports a category. solc stops at the first failing phase,
# so an error in a later phase means the earlier phases now pass. Categories without a
# fixed phase (other, internal errors) never count as phase progress.
_PHASES = dict.fromkeys(("input_format", "environment_plan", "unresolved_package_import", "missing_relative_file",
                         "standard_json_input", "io_error", "closure_version_conflict", "version_mismatch",
                         "json_error", "unsupported_disjunction", "unsupported_expression",
                         "unterminated_pragma", "pragma_missing_semicolon_candidate", "version_dependent"), 0)
_PHASES.update(dict.fromkeys(("parser_error_other", "unbalanced_structure", "encoding", "multiple_license_or_pragma",
                              "file_level_member"), 1))
_PHASES.update(dict.fromkeys(("syntax_error", "visibility", "docstring_error"), 2))
_PHASES.update(dict.fromkeys(("declaration_error", "undeclared_identifier", "duplicate_definition",
                              "missing_base_contract"), 3))
_PHASES.update(dict.fromkeys(("type_error_other", "abi_coder_required"), 4))
_PHASES.update(dict.fromkeys(("codegen_only", "unimplemented_feature", "compiler_exception"), 5))


def _diagnostics_by_file(record, names):
    """Classified solc errors of a record's failed attempts, keyed by project-relative file name (None: unlocated).

    The same diagnostic reported by several candidate versions is kept once, with
    the versions that reported it.
    """
    grouped, seen = {}, {}
    for attempt in record.attempts:
        compiled = attempt.get("solc")
        if not compiled or compiled["returncode"] in (0, None) or compiled["timed_out"]:
            continue
        for row in parse_diagnostics(compiled["stderr"]):
            if row["kind"] == "Warning":
                continue
            name = None
            if row["filename"]:
                # Newer solc reports some file-level errors (e.g. repeated SPDX) without a line.
                path = Path(row["filename"])
                name = (path.relative_to(compiled["cwd"]) if path.is_absolute() and Path(compiled["cwd"]) in path.parents
                        else path).as_posix()
                if name not in names and len(names) == 1:
                    name = next(iter(names))
                if name not in names:
                    continue
            classified = classify_diagnostic(row)
            identity = (name, classified.get("category"), classified.get("line"), classified.get("column"),
                        classified.get("message"))
            if identity in seen:
                seen[identity]["versions"].append(attempt["version"])
                continue
            seen[identity] = dict(classified, versions=[attempt["version"]])
            grouped.setdefault(name, []).append(seen[identity])
    return grouped


def _failure_phase(record):
    """D27: the latest compiler phase any attempt reached, from its earliest blocking error (None if unknown)."""
    from compile_repair.toolchain.solc import classify_constraints, classify_diagnostic
    if record.status == "success":
        return None
    reached = []
    for attempt in record.attempts:
        stage = attempt["stage"]
        if stage in ("input_format", "project_assembly"):
            reached.append(0)
        elif stage == "environment_plan":
            sources = [Path(f["path"]).read_bytes() for f in record.inputs if Path(f["path"]).is_file()]
            reached.append(_PHASES.get(classify_constraints(attempt["error_first_line"], sources)["category"], 0))
        elif attempt.get("solc"):
            result = attempt["solc"]
            if not result["returncode"] or result["timed_out"]:
                continue
            phases = [_PHASES.get(classify_diagnostic(d)["category"])
                      for d in parse_diagnostics(result["stderr"]) if d["kind"] != "Warning"]
            if phases and None not in phases:
                reached.append(min(phases))
    return max(reached) if reached else None


def _failed_diagnostics(record):
    """Non-warning solc diagnostics of failed attempts, each with the version that reported it."""
    rows = []
    for attempt in record.attempts:
        compiled = attempt.get("solc")
        if compiled and compiled["returncode"] not in (0, None) and not compiled["timed_out"]:
            rows += [dict(d, versions=[attempt["version"]]) for d in parse_diagnostics(compiled["stderr"])
                     if d["kind"] != "Warning"]
    return rows


def _slither_failures(record):
    """Distinct Slither failure messages of attempts whose solc run succeeded."""
    messages = []
    for attempt in record.attempts:
        analysis = attempt.get("slither")
        if analysis and not analysis.get("d3") and (analysis.get("error_first_line") or analysis.get("exception_type")):
            # The exception type is kept: Slither's AssertionError carries no message (CP6.5).
            message = "{}: {} [solc {}]".format(analysis.get("exception_type") or "D3", analysis.get("error_first_line") or "",
                                                attempt.get("version"))
            if message not in messages:
                messages.append(message)
    return messages


def _slither_failed_version(record):
    """First version whose solc run passed but whose Slither analysis failed D3 (CP6.5)."""
    for attempt in record.attempts:
        analysis = attempt.get("slither")
        if analysis and not analysis.get("d3") and attempt.get("version"):
            return attempt["version"]
    return None


def _failure_measure(record):
    """Count blocking observations within one attempt; also retain eligibility for CP5."""
    from compile_repair.toolchain.solc import classify_constraints, classify_diagnostic
    if record.status == "success":
        return 0, set()
    categories, counts = set(), []
    for attempt in record.attempts:
        stage = attempt["stage"]
        if stage == "input_format":
            categories.add(record.reason)
            counts.append(1)
        elif stage == "project_assembly":
            issues = attempt["issues"]
            categories.update(r["category"] for r in issues)
            counts.append(len(issues))
        elif stage == "environment_plan":
            sources = [Path(f["path"]).read_bytes() for f in record.inputs if Path(f["path"]).is_file()]
            categories.add(classify_constraints(attempt["error_first_line"], sources)["category"])
            counts.append(1)
        elif attempt.get("solc"):
            result = attempt["solc"]
            if not result["returncode"] or result["timed_out"]:
                continue
            errors = [d for d in parse_diagnostics(result["stderr"]) if d["kind"] != "Warning"]
            categories.update(classify_diagnostic(d)["category"] for d in errors)
            if errors:
                counts.append(len(errors))
    return min(counts) if counts else None, categories


def repair_unit(unit, compilers, store, journal, order="ascending",
                compile_fn=compile_file, slither_fn=run_slither, project=None,
                project_compile_fn=compile_project, *, project_index=None, offline_index=None,
                dependency_policy=DEFAULT_DEPENDENCY_POLICY, environment_only=False,
                dependency_limit=DEFAULT_DEPENDENCY_LIMIT, mask_versions=False, agent=None, group=None):
    """Run environment selection, then deterministic project repairs on exclusive working copies.

    With an agent (agents/stage1.py), rounds of LLM candidates follow whenever the rules
    change nothing; an accepted candidate sends the unit back through the rules (PROMPTS
    3.1). `group` is the unit's project group for K3 leave-one-project (default: the
    project root, or the source path of a single file). Without an agent nothing changes.
    """
    if dependency_limit is not None and (type(dependency_limit) is not int or dependency_limit < 1):
        raise ValueError("dependency_limit must be a positive integer or None")
    prefix = "units/" + unit.unit_id + "/"
    tools = dict(order=order, compile_fn=compile_fn, slither_fn=slither_fn, project_compile_fn=project_compile_fn)
    record = _environment(unit, compilers, store, journal, project=project, prefix=prefix, **tools)
    if environment_only or record.status == "success" or not compilers or record.reason == "solc_timeout":
        store.write_json(prefix + "result.json", record)
        return record
    before, categories = _failure_measure(record)
    if agent is None and not categories.intersection(_DEPENDENCY_FAILURES | _NORMALIZATION_FAILURES | _STUB_FAILURES
                                   | _STRUCTURE_FAILURES) and not slither_rewrite_applicable(_slither_failures(record)) \
            and migration_versions(_failed_diagnostics(record)) is None:
        store.write_json(prefix + "result.json", record)
        return record
    store.write_json(prefix + "environment_result.json", record)
    # A unit whose declared versions have no installed compiler compiles only under the step-6
    # pragma override; repair trials of that unit may use the same override (CP6.4).
    trial_override = "pragma_overridden" in record.flags
    steps = []
    settings, wrapper = (), None
    original_project = project
    if record.reason == "standard_json_input":
        try:
            project, settings, wrapper = unpack_sources(unit.sources[0].content, store, prefix + "wrapper_sources")
        except (ValueError, UnicodeError, RecursionError) as exc:
            steps.append(dict(step=2, accepted=False, reason=str(exc)))
            store.write_json(prefix + "repair_steps.json", steps)
            store.write_json(prefix + "result.json", record)
            return record
        project_index = ProjectIndex(project.root, [Path(project.root) / n for n, _ in project.source_units])
        steps.append(dict(step=2, operation="unpack", wrapper=wrapper))
    elif project is None:
        # A file or snippet supplies one source. Only a caller-provided project
        # root or wrapper can authorize searching other local files.
        source_path = store.write_bytes(prefix + "standalone/input.sol", unit.sources[0].content)
        project_index = ProjectIndex(source_path.parent, (source_path,))
        project = resolve_project(project_index.root, source_path, index=project_index)
    index = project_index or ProjectIndex(project.root)
    if group is None:
        group = str(original_project.root) if original_project is not None else unit.sources[0].path
    llm_records_start = len(agent.client.records) if agent is not None else 0
    if agent is not None:
        agent.reset()
    originals = {}
    overlays, origins, existing_releases = {}, {}, {}
    attempts = 0
    compiled_combinations = 0
    first_success = None
    truncated = False
    accepted_prefix = None
    # First trial whose compile blockers are gone but whose graph fails on the Slither side.
    # It never changes the search; it only fixes the final attribution (CP6.0.1).
    compile_clean = None
    # D27: the phase of the current state and the latest phase ever accepted by phase progress.
    phase = _failure_phase(record)
    phase_reached = phase

    def select(result, step_record):
        nonlocal record, before, accepted_prefix, phase, phase_reached
        step_record["accepted"] = True
        record, before = result, step_record["errors_after"]
        phase = step_record["phase_after"]
        if phase is not None and (phase_reached is None or phase > phase_reached):
            phase_reached = phase
        accepted_prefix = step_record["receipt"][:-len("result.json")]

    def try_project(step, candidate, maps, details, defer=False):
        nonlocal attempts, compile_clean
        attempts += 1
        branch = prefix + "round_{:03d}/".format(attempts)
        for f in candidate.files:
            name = Path(f.path).relative_to(candidate.root).as_posix()
            if name in maps:
                expected, patches = maps[name]
                current, evidence = apply_patches(expected, patches)
                verify_provenance(expected, current, evidence)
                if current != f.content:
                    raise ValueError("Proposed repair differs from provenance for " + name)
                if not Path(f.path).exists() and evidence.level == "additive":
                    continue
            else:
                expected = f.content
            digest = hashlib.sha256(expected).hexdigest()
            if originals.setdefault(f.path, digest) != digest or sha256(f.path) != digest:
                raise ValueError("Project source changed during repair: " + name)
        copy = materialize_project(candidate, store, branch + "input_project")
        # A step-10 rewrite answers a Slither failure on a version that solc already accepted:
        # that version is tried first, so the rewrite does not also move the compiler (CP6.5).
        known = (_slither_failed_version(record) or unit.known_version) if step == 10 else unit.known_version
        next_unit = CompilationUnit(unit.unit_id, copy.files, known, unit.regression)
        result = _environment(next_unit, compilers, store, journal, project=copy, prefix=branch,
                              initial_settings=settings, origins=maps, allow_override=trial_override,
                              already_copied=True, permit_compile=(step != 3 or dependency_limit is None
                                  or compiled_combinations < dependency_limit), **tools)
        after, _ = _failure_measure(result)
        after_phase = _failure_phase(result)
        known = phase is not None and after_phase is not None
        eligible = result.reason not in ("slither_side_failure", "solc_timeout")
        # PROMPTS 3.1: fewer blocking errors, without falling back to an earlier compiler phase.
        fewer = (eligible and before is not None and after is not None and 0 < after < before
                 and not (known and after_phase < phase))
        # D27: a later compiler phase than any state accepted so far, whatever the error count.
        advanced = eligible and known and after is not None and after > 0 and after_phase > max(phase, phase_reached)
        accepted = result.status == "success" or fewer or advanced
        steps.append(dict(step=step, round=attempts, errors_before=before, errors_after=after, accepted=False,
                          phase_before=phase, phase_after=after_phase,
                          accepted_by="success" if result.status == "success" else "fewer_errors" if fewer
                          else "phase_advanced" if advanced else None,
                          status=result.status, reason=result.reason, receipt=branch + "result.json", **details))
        store.write_json(branch + "result.json", result)
        if result.reason == "slither_side_failure" and compile_clean is None:
            compile_clean = (result, steps[-1])
        if accepted and not defer:
            select(result, steps[-1])
        return accepted, result

    def agent_round():
        """One first-stage round (PROMPTS 3.5): candidates, trial compiles, best by errors then bytes."""
        nonlocal project, overlays, origins
        contents = {n: f.content for n, f in ((Path(f.path).relative_to(project.root).as_posix(), f)
                                            for f in project.files) if not n.startswith(".compile_repair/")}
        contents.update({n: raw for n, raw in overlays.items() if n in contents})
        diagnostics = _diagnostics_by_file(record, set(contents))
        versions = [a["version"] for a in record.attempts
                    if a.get("solc") and a["solc"]["returncode"] not in (0, None) and not a["solc"]["timed_out"]]
        version = versions[0] if versions else record.selected_version
        # The prompt shows the errors of one compiler version: the first one tried.
        diagnostics = {n: [r for r in rows if version in r["versions"]] for n, rows in diagnostics.items()}
        diagnostics = {n: rows for n, rows in diagnostics.items() if rows}
        # Errors that are not solc diagnostics: unresolved imports and version-constraint failures.
        for issue in project.issues or ():
            if issue.get("importer") in contents:
                diagnostics.setdefault(issue["importer"], []).append(dict(
                    kind="ImportError", message='Source "%s" not found' % issue.get("path"), line=issue.get("line"),
                    category=issue.get("category") or "unresolved_import", versions=[version]))
        for attempt in record.attempts:
            if attempt.get("stage") == "environment_plan" and attempt.get("error_first_line"):
                diagnostics.setdefault(None, []).append(dict(kind="VersionError", message=attempt["error_first_line"],
                                                             line=None, category="version_constraints"))
        # Verified dependency release files (step 3) are never edited.
        fixed = {n for n, (_, ps) in origins.items() if any(p.step == "dependency" for p in ps)}
        editable = set(contents) - fixed
        entry = Path(project.entry)
        entry = (entry.relative_to(project.root) if entry.is_absolute() else entry).as_posix()
        status = (record.inputs[0].get("language_evidence") or {}).get("status", "solidity")
        rows = [r for rows in diagnostics.values() for r in rows]
        parser_only = bool(rows) and all(_PHASES.get(r.get("category")) == 1 for r in rows)
        candidates, evidence = agent.propose(contents, entry, diagnostics, version, editable, project.issues, group,
                                             attempts + 1, status, parser_only)
        steps.append(dict(step=11, operation="stage1_round", **evidence))
        trials = []
        for edits, patches, summary in candidates:
            maps = dict(origins)
            for name, extra in patches.items():
                original, previous = maps[name] if name in maps else ((Path(project.root) / name).read_bytes(), ())
                maps[name] = original, previous + extra
            working = dict(overlays)
            working.update(edits)
            candidate = resolve_project(project.root, project.entry, project.remappings, index,
                                        project.additional_entries, working)
            improves, result = try_project(11, candidate, maps, dict(stage1={k: v for k, v in summary.items()
                                                                              if k != "text"}), defer=True)
            errors = steps[-1]["errors_after"]
            rank = (result.status != "success", errors if errors is not None else float("inf"),
                    summary["changed_bytes"], summary["candidate"])
            trials.append((rank, improves, result, steps[-1], candidate, working, maps, summary))
        chosen = min((t for t in trials if t[1]), key=lambda t: t[0], default=None)
        outcomes = []
        for trial in trials:
            if trial is not chosen:
                rows = _failed_diagnostics(trial[2])
                outcomes.append((trial[7]["text"], "not accepted: %s" % (trial[2].reason or trial[2].status),
                                 ["%s: %s" % (r["kind"], r["message"]) for r in rows][:5]))
        if chosen is not None:
            _, _, result, measurement, project, overlays, origins, _ = chosen
            select(result, measurement)
        agent.observe(chosen is not None, outcomes)
        if not agent.active():
            steps.append(dict(step=11, operation="stage1_end", reason=agent.stopped))
        return chosen is not None, record.status == "success" or record.reason == "solc_timeout"

    needs_assembly = wrapper is not None or original_project is None
    while True:
        changed = False
        remaps, evidence = assembly_remappings(project, index)
        if remaps or needs_assembly:
            assembled = resolve_project(project.root, project.entry, project.remappings + remaps,
                                        index, project.additional_entries, overlays)
            accepted, result = try_project(2, assembled, origins, dict(remapping_evidence=evidence))
            needs_assembly = False
            if accepted:
                project, changed = assembled, True
            if result.status == "success" or result.reason == "solc_timeout":
                break
        else:
            steps.append(dict(step=2, accepted=False, remapping_evidence=evidence, reason="no_applicable_remapping"))
        if isinstance(offline_index, (str, Path)):
            offline_index = OfflineIndex(offline_index)
        if offline_index is not None and project.issues and not truncated:
            started = time.monotonic()
            evidence = []
            best, best_rank, timed_out = None, None, False
            try:
                base_plan = make_plan([f.content for f in project.files], compilers, unit.known_version, unit.regression, order)
                preferred = next(ordered_candidates(base_plan), None)
            except Unsupported:
                preferred = None
            for candidate, additions, releases in dependency_choices(
                    project, index, offline_index, compilers, overlays, dependency_policy, evidence, preferred,
                    existing_releases, mask_versions=mask_versions):
                maps = dict(origins)
                for name, data in additions.items():
                    if name not in origins:
                        maps[name] = (b"", (Patch(0, 0, b"", data, "dependency", attempts+1, "verified release file"),))
                manifest = {name: hashlib.sha256(data).hexdigest() for name, data in additions.items()}
                release_facts = {name: dict(fields, inferred=False) for name, fields in releases.items()}
                improves, result = try_project(3, candidate, maps, dict(releases=release_facts, files=manifest), defer=True)
                measurement = steps[-1]
                success = result.status == "success"
                measurement["d3_verified"] = success
                if result.reason == "dependency_combination_limit":
                    truncated = True
                    break
                if any(a.get("solc") is not None for a in result.attempts):
                    compiled_combinations += 1
                    measurement["combination_ordinal"] = compiled_combinations
                    if success and first_success is None:
                        first_success = compiled_combinations
                if result.reason == "solc_timeout":
                    timed_out = True
                    break
                if not improves:
                    continue
                distance = (abs(version_tuple(result.selected_version)[1] - version_tuple(preferred)[1])
                            if success and preferred and dependency_policy == "closest" else 0)
                # Compare actual D3 selections. A partial diagnostic improvement
                # never displaces a successful release combination.
                rank = (not success, distance if success else measurement["errors_after"])
                if best is None or rank < best_rank:
                    best_rank = rank
                    best = (result, measurement, candidate, maps, additions)
                if success and (dependency_policy != "closest" or distance == 0):
                    break
            if best is not None and not timed_out:
                result, measurement, project, origins, additions = best
                select(result, measurement)
                overlays.update(additions)
                existing_releases = measurement["releases"]
                changed = True
            steps.append(dict(step=3, operation="candidate_checks", policy=dependency_policy,
                              preferred_compiler=preferred, evidence=evidence, limit=dependency_limit,
                              compiled_combinations=compiled_combinations, first_d3_combination=first_success,
                              truncated=truncated, elapsed_seconds=time.monotonic() - started))
            if record.status == "success" or timed_out:
                break
        else:
            reason = "index_unavailable" if offline_index is None else "no_unresolved_imports"
            steps.append(dict(step=3, accepted=False, reason="dependency_combination_limit" if truncated else reason))
        # Keep overlays and provenance private until the chain improves on its initial state.
        staged, working, maps = project, dict(overlays), dict(origins)
        issues, chain, prior_count = None, [], before
        stop = False
        for depth in range(1, RELATIVE_CHAIN_LIMIT + 1):
            edits, patches, choices = relative_repairs(staged, index, compilers, working, attempts+1, issues)
            if not edits:
                steps.append(dict(step=4, accepted=False, path_search=choices, reason="no_unique_compatible_path"))
                break
            for name, extra in patches.items():
                original, previous = maps[name] if name in maps else ((Path(staged.root) / name).read_bytes(), ())
                maps[name] = original, previous + extra
            working.update(edits)
            candidate = resolve_project(staged.root, staged.entry, staged.remappings, index, staged.additional_entries, working)
            improves, result = try_project(4, candidate, maps, dict(path_search=choices), defer=True)
            trial = steps[-1]
            chain.append(trial)
            trial.update(errors_before=prior_count, chain_start_errors=before, chain_depth=depth,
                         chain_limit=RELATIVE_CHAIN_LIMIT, chain_outcome="rolled_back")
            stop = result.status == "success" or result.reason == "solc_timeout"
            if improves:
                for member in chain:
                    member.update(accepted=True, chain_outcome="committed")
                select(result, trial)
                project, overlays, origins, changed = candidate, working, maps, True
                break
            if stop or result.reason != "unresolved_imports":
                break
            issues = chain_relative_issues(staged, candidate, choices)
            if not issues:
                break
            trial["new_relative_errors"] = [dict(importer=r["importer"], path=r["path"], line=r["line"])
                                            for r in issues]
            staged, prior_count = candidate, trial["errors_after"]
        # Steps 5 (CP6.1), 7 (CP6.3) and 8 (CP6.2): source rules proposed from the current best
        # record's diagnostics. Verified dependency releases (step 3) are never edited. A fragment
        # wrapped by step 8 gets its stubs from step 7 in the next pass of the loop.
        for step, propose, key, idle in ((5, normalization_repairs, "normalization", "no_applicable_normalization"),
                                         (7, stub_repairs, "stubs", "no_applicable_stub"),
                                         (8, structure_repairs, "structure", "no_applicable_structure"),
                                         (10, slither_compat_repairs, "slither_compat", "no_applicable_rewrite")):
            if stop:
                break
            contents = {n: f.content for n, f in ((Path(f.path).relative_to(project.root).as_posix(), f)
                                                for f in project.files) if not n.startswith(".compile_repair/")}
            contents.update({n: raw for n, raw in overlays.items() if n in contents})
            # Step 10 reads the Slither failures of compile-clean attempts, not solc diagnostics.
            diagnostics = ({None: [dict(category="slither_incomplete", message=m) for m in _slither_failures(record)]}
                           if step == 10 else _diagnostics_by_file(record, set(contents)))
            if step == 10 and not slither_rewrite_applicable([r["message"] for r in diagnostics[None]]):
                continue
            edits, patches, evidence = propose(contents, diagnostics, attempts + 1)
            if not edits:
                steps.append({"step": step, "accepted": False, key: evidence, "reason": idle})
                continue
            maps = dict(origins)
            for name, extra in patches.items():
                original, previous = maps[name] if name in maps else ((Path(project.root) / name).read_bytes(), ())
                maps[name] = original, previous + extra
            working = dict(overlays)
            working.update(edits)
            candidate = resolve_project(project.root, project.entry, project.remappings, index,
                                        project.additional_entries, working)
            accepted, result = try_project(step, candidate, maps, {key: evidence})
            if accepted:
                project, overlays, origins, changed = candidate, working, maps, True
            stop = result.status == "success" or result.reason == "solc_timeout"
        if stop:
            break
        while not changed and agent is not None and agent.active():
            changed, stop = agent_round()
            if stop:
                break
        if stop or not changed:
            break
    if (compile_clean is not None and record.status != "success"
            and record.reason not in ("slither_side_failure", "solc_timeout")):
        # Every repair was explored from the same states as before; report the
        # Slither-side blocker instead of the compile blocker it already removed.
        result, measurement = compile_clean
        measurement["accepted_outcome"] = "compiled_slither_side_failure"
        if measurement.get("chain_outcome") == "rolled_back":
            measurement["chain_outcome"] = "compiled_slither_side_failure"
        select(result, measurement)
    if truncated:
        record.flags.append("dependency_search_truncated")
    if original_project:
        verify_project(original_project)
    if any(sha256(name) != digest for name, digest in originals.items()):
        raise ValueError("Original project changed during repair")
    for step in steps:
        if step.get("accepted"):
            for release in step.get("releases", {}).values():
                release["inferred"] = release["tier"] == "T3"
    if record.status == "success":
        for name in ("graph.json", "nodes.json"):
            store.write_bytes(prefix + name, (store.path / (accepted_prefix + name)).read_bytes())
    store.write_json(prefix + "repair_steps.json", steps)
    if agent is not None:
        # Every LLM call of this unit (PROMPTS invariants); keys never enter the records.
        store.write_json(prefix + "llm_calls.json", dict(calls=agent.client.records[llm_records_start:],
                                                         budget=agent.client.budget.snapshot(),
                                                         stopped=agent.stopped))
    store.write_json(prefix + "result.json", record)
    return record


def _code_commit(root):
    """Return the code checkout's HEAD, or None when git/HEAD is unavailable."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(root), stderr=subprocess.DEVNULL,
            universal_newlines=True).strip() or None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def repair(paths, output, snippets=(), known_version=None, order="ascending", regression=None,
           *, compile_fn=compile_file, result_check=None, remappings=(), offline_index=None,
           dependency_policy=DEFAULT_DEPENDENCY_POLICY, dependency_limit=DEFAULT_DEPENDENCY_LIMIT, agent=None):
    """Run the common production entry for files/snippets/project directories; return batch summary.

    Directories expand to one unit per .sol entry and its transitive closure.
    Empty projects, overlapping paths and missing files fail before output. Unrepaired inputs are valid records; unexpected failures stop/seal
    the partial batch. compile_fn can inject recorded compiler outcomes in
    tests. Missing git/HEAD is flagged and sealed as null, with file hashes kept.
    An optional result_check(record, output_path) may raise to stop and seal
    after a flushed per-input record; it never participates in version choice.
    No compiler download or global selection occurs; LLM calls happen only with an
    explicit agent (a Stage1, or the path of its JSON configuration), within its budget.
    """
    if order not in ("ascending", "descending") or regression not in (None, "mando"):
        raise ValueError("Unsupported repair configuration")
    if isinstance(agent, (str, Path)):
        agent = agent_from_config(agent)
    if known_version is not None:
        version_tuple(known_version)
    supplied = [(Path(p).resolve(), "file") for p in paths] + [(Path(p).resolve(), "snippet") for p in snippets]
    if not supplied:
        raise ValueError("At least one file or snippet is required")
    if len({str(p) for p, _ in supplied}) != len(supplied):
        raise ValueError("Duplicate input path")
    for remap in remappings:
        parse_remapping(remap)
    expanded = []
    for path, kind in supplied:
        if path.is_dir():
            if kind == "snippet" or regression is not None:
                raise ValueError("Project directories cannot be snippets or MANDO regression inputs")
            index = ProjectIndex(path)
            if not index.entries:
                raise ValueError("Project directory contains no .sol files")
            expanded.extend((p, "project", index) for p in index.entries)
        else:
            if not path.is_file() or kind == "file" and path.suffix != ".sol":
                raise ValueError("Expected an existing .sol file or explicit --snippet text file")
            expanded.append((path, kind, None))
    if len({str(p) for p, _, _ in expanded}) != len(expanded):
        raise ValueError("Overlapping input paths/project directories")
    store = ArtifactStore(output)
    root = Path(__file__).resolve().parents[1]
    commit = _code_commit(root)
    module = root / "compile_repair"
    code = list(module.glob("*.py")) + [p for folder in module.iterdir()
            if folder.is_dir() and folder.name not in ("artifacts", "tests", "docs")
            for p in folder.rglob("*.py")]
    implementation = {str(p.relative_to(root)): sha256(p) for p in sorted(code)}
    summary = {"schema": "cp1-repair-v1", "status": "running", "units": [], "llm_calls": 0,
               "cost_usd": 0.0, "order": order, "regression": regression, "known_version": known_version,
               "supplied": [{"path": str(p), "kind": k} for p, k in supplied]}
    if commit is None:
        summary["flags"] = ["code_commit_unavailable"]
    tools, snapshots = {}, {}
    with store.journal("invocations.jsonl") as journal, store.journal("manifest.jsonl") as manifest:
        try:
            if offline_index is None:
                default_index = root.parent / "corpora/compile-repair-npm-cp5-v1/index"
                offline_index = os.environ.get("COMPILE_REPAIR_DEPENDENCY_INDEX")
                if offline_index is None and (default_index / "seal.json").is_file():
                    offline_index = default_index
            if isinstance(offline_index, (str, Path)):
                offline_index = OfflineIndex(offline_index)
            if offline_index is not None:
                tools["dependency_index"] = offline_index.seal
                summary["dependency_policy"] = dependency_policy
                summary["dependency_limit"] = dependency_limit
            if agent is not None:
                tools["agent"] = getattr(agent, "description", dict(model=agent.client.model))
            tools.update(check_profile("production"))
            compilers, frozen_rows, evidence = load_trusted_compilers()
            tools["compilers"] = {v: asdict(c) for v, c in compilers.items()}
            store.write_json("trust.json", evidence)
            for number, (path, kind, project_index) in enumerate(expanded, 1):
                project = (resolve_project(project_index.root, path, remappings, project_index)
                           if project_index is not None else None)
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                sources = project.files if project is not None else (SourceFile(str(path), digest, raw, kind),)
                for source in sources:
                    previous = snapshots.setdefault(Path(source.path), source.sha256)
                    if previous != source.sha256:
                        raise ValueError("Input changed between compilation units")
                metadata_version, metadata = mando_known_version(raw, frozen_rows) if regression == "mando" else (None, [])
                if known_version and metadata_version and known_version != metadata_version:
                    raise ValueError("Explicit known version conflicts with validated regression metadata")
                unit = CompilationUnit("input_{:04d}".format(number), sources, known_version or metadata_version, regression)
                store.write_json("units/" + unit.unit_id + "/input_record.json", {
                    "path": str(path), "sha256": digest, "kind": kind,
                    "known_version": unit.known_version, "metadata": metadata})
                record = repair_unit(unit, compilers, store, journal, order,
                                     compile_fn=compile_fn, project=project, project_index=project_index,
                                     offline_index=offline_index, dependency_policy=dependency_policy,
                                     dependency_limit=dependency_limit, agent=agent)
                emit(manifest, record)
                if agent is not None:
                    summary["llm_calls"] = agent.client.budget.calls
                    summary["cost_usd"] = round(agent.client.budget.cost_usd, 6)
                summary["units"].append({"unit_id": unit.unit_id, "input_sha256": digest,
                    "status": record.status, "reason": record.reason, "selected_version": record.selected_version})
                print("CP1 {}/{}: {} {}".format(number, len(expanded), record.status,
                                               record.selected_version or record.reason), flush=True)
                if result_check is not None:
                    result_check(record, store.path)
            summary["status"] = "complete" if all(x["status"] == "success" for x in summary["units"]) else "unrepaired"
        except Exception as exc:
            summary.update(status="stopped", exception_type=type(exc).__name__, error=str(exc))
        changed = [str(p) for p, digest in snapshots.items() if sha256(p) != digest]
        if changed:
            summary.update(status="stopped", exception_type="InputIntegrityError", changed_inputs=changed)
    store.write_json("summary.json", summary)
    store.seal(tools, commit, implementation)
    return summary
