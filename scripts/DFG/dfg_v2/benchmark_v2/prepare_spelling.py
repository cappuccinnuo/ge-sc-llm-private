"""Prompt 8G spelling preparation and strict semantic gate; no training."""
import argparse
from collections import Counter
from pathlib import Path

from scripts.labeling_v2.safe_graph import read_graph
from ..tokens import TokenEncoder
from .prepare import read, write, ref, checked, sha
from .prepare_anon import load_names as load_8f_names
from .spelling_names import VERSION, RESERVED, KEYWORD_STRINGS, FIXED_TYPE, anonymize, validate
from .anon_binding import replace_spans
from .spelling_parity import check_file
from .leakage_probes import PROTOCOL


def implementation():
    return {p: ref(Path(__file__).with_name(p))
            for p in ("spelling_names.py", "spelling_parity.py", "prepare_spelling.py")}


def prepare_names(prior, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    old, old_rows = load_8f_names(prior)
    policy = read(checked(old["artifacts"]["policy"]))
    if set(policy["reserved_spellings"]) != set(RESERVED):
        raise ValueError("Reserved spelling policy differs from 8F")
    if policy["additional_reserved_pattern"] != FIXED_TYPE or policy["keyword_strings"] != list(KEYWORD_STRINGS):
        raise ValueError("Fixed meaning/keyword policy differs")
    formal = read(checked(old["formal_plan"]))
    expected, task_files = {}, {}
    for tid, entry in formal["tasks"].items():
        task_files[tid] = []
        record = entry["record"]
        for file, source_ref in record["sources"].items():
            ident = record["category"] + "/" + file
            if ident in expected and expected[ident]["source"] != source_ref:
                raise ValueError("Task granularities differ on source identity")
            expected[ident] = dict(file=file, category=record["category"], source=source_ref)
            task_files[tid].append(ident)
    if set(expected) != set(old_rows) or len(expected) != 256:
        raise ValueError("Frozen source population differs")
    if sum(len(v) for v in task_files.values()) != 384:
        raise ValueError("Frozen task/file population differs")
    statuses = Counter()
    for ident, row in sorted(expected.items()):
        if row["source"] != old_rows[ident]["source"]:
            raise ValueError("8F source reference differs")
        raw = checked(row["source"]).read_bytes()
        source = raw.decode("utf8")
        result = anonymize(source)
        if result["source_sha256"] != row["source"]["sha256"]:
            raise ValueError("Source byte identity differs")
        if result["status"] == "renamed":
            validate(source, result)
        del result["rewritten"]
        folder = output / row["category"]
        folder.mkdir(exist_ok=True)
        path = folder / (row["file"] + ".json")
        write(path, result)
        row.update(result=ref(path), status=result["status"])
        statuses[result["status"]] += 1
    new_policy = dict(version=VERSION, rule="exact AST identifier nodes excluding frozen reserved spellings",
        inherited_policy=old["artifacts"]["policy"], reserved_spellings=sorted(RESERVED),
        additional_reserved_pattern=FIXED_TYPE, keyword_strings=list(KEYWORD_STRINGS),
        prefix="v", scope="file-local spelling bijection, all source cohorts and task granularities",
        numbering="SHA256(version:sourceSHA) seed, permutation of sorted distinct spellings, avoid existing vN",
        declarations_resolved=False, unknown_external_members_included=True,
        non_identifier_grammar_tokens_unchanged=True, original_graph_used=True,
        parity_failure="whole-file fallback; blocks all downstream probes/features/plan; no sample removal")
    write(output / "sources.json", expected)
    write(output / "task_files.json", task_files)
    write(output / "policy.json", new_policy)
    write(output / "probe_protocol.json", PROTOCOL)
    write(output / "supersession.json", dict(prior_manifest=ref(Path(prior)/"manifest.json"),
          reason="User Prompt8G replaces declaration-bound naming with AST spelling bijection",
          old_files_modified=False, execution_authorized=False))
    manifest = dict(version=VERSION, previous_8f_manifest=ref(Path(prior)/"manifest.json"),
        old_plan=old["old_plan"], formal_plan=old["formal_plan"],
        source_identities=len(expected), task_file_references=sum(len(v) for v in task_files.values()),
        renamed_files=statuses["renamed"], fallback_files=statuses["fallback"],
        artifacts={n: ref(output/(n+".json")) for n in
                   ("sources", "task_files", "policy", "probe_protocol", "supersession")},
        implementation=implementation(), execution_authorized=False, formal_fit_count=0,
        compiler_verified=False, binding_resolution_claimed=False)
    write(output/"manifest.json", manifest)
    write(output/"manifest.seal.json", dict(manifest=ref(output/"manifest.json")))
    return manifest


def load_names(directory):
    directory = Path(directory)
    manifest = read(directory/"manifest.json")
    if manifest["version"] != VERSION or read(directory/"manifest.seal.json")["manifest"] != ref(directory/"manifest.json"):
        raise ValueError("Spelling manifest version/seal differs")
    for r in manifest["artifacts"].values():
        checked(r)
    rows = read(checked(manifest["artifacts"]["sources"]))
    for row in rows.values():
        checked(row["source"])
        checked(row["result"])
    if len(rows) != manifest["source_identities"]:
        raise ValueError("Source identity population differs")
    return manifest, rows


def load_result(row):
    source = checked(row["source"]).read_bytes().decode("utf8")
    result = read(checked(row["result"]))
    result["rewritten"] = replace_spans(source, result["edits"])
    if result["status"] == "renamed":
        validate(source, result)
    elif result["edits"] or result["mapping"] or result["rewritten"] != source:
        raise ValueError("Partial edits in whole-file fallback")
    return source, result


def verify_semantics(naming, semantic):
    manifest, sources = load_names(naming)
    path = Path(semantic)/"summary.json"
    summary = read(path)
    if read(Path(semantic)/"summary.seal.json")["summary"] != ref(path):
        raise ValueError("Semantic summary seal differs")
    if summary["naming"] != ref(Path(naming)/"manifest.json"):
        raise ValueError("Semantic and naming identity differ")
    tasks = read(checked(manifest["artifacts"]["task_files"]))
    expected = {(tid, ident) for tid, ids in tasks.items() for ident in ids}
    rows = []
    for r in summary["artifacts"].values():
        rows.extend(read(checked(r)))
    identities = [(r["task"], r["identity"]) for r in rows]
    if len(set(identities)) != len(identities) or set(identities) != expected:
        raise ValueError("Missing/duplicate semantic task-file identity")
    for r in rows:
        if r["source"] != sources[r["identity"]]["source"]:
            raise ValueError("Semantic source differs")
        if r["status"] == "semantic_pass":
            if not all(r.get(k) is True for k in
                       ("passed", "fact_counts_equal", "normalized_facts_exact",
                        "projected_endpoints_exact", "original_hcg_exact")):
                raise ValueError("Passed semantic row contradicts exact invariants")
        elif r["passed"] or not r["whole_file_fallback"] or r["committed_feature_edits"] != 0:
            raise ValueError("Failed source does not enforce whole-file fallback")
    counts = dict(Counter(r["status"] for r in rows))
    if counts != summary["counts"] or len(rows) != manifest["task_file_references"]:
        raise ValueError("Semantic count mismatch")
    resolution = read(checked(summary["synthetic_resolution"]))
    cases = resolution["nodes"]
    unique = {(r["task"], r["identity"], r["node"]) for r in cases}
    if len(unique) != len(cases) or resolution["resolved"] != len(cases):
        raise ValueError("Synthetic resolution count/identity differs")
    complete_projection = (resolution["expected"] == 36 and len(cases) == 36
                           and all(r["all_exact_candidates_agree"] for r in cases))
    if resolution["passed"] != complete_projection:
        raise ValueError("Forged synthetic-resolution flag")
    actual = (all(r["status"] == "semantic_pass" for r in rows)
              and manifest["fallback_files"] == 0 and complete_projection)
    if summary["passed"] != actual:
        raise ValueError("Forged semantic completeness flag")
    return manifest, sources, summary, rows


def require_semantic_pass(naming, semantic):
    result = verify_semantics(naming, semantic)
    if not result[2]["passed"]:
        raise ValueError("Whole-file semantic fallback blocks probes/features/170-fit plan")
    return result


def run_semantic(naming, store_path, historical_cases, output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    manifest, sources = load_names(naming)
    formal = read(checked(manifest["formal_plan"]))
    store = read(store_path)
    if read(Path(store_path).with_name("store.seal.json"))["store_sha256"] != sha(store_path):
        raise ValueError("Graph store seal differs")
    cases = read(historical_cases)
    if cases["blocking_synthetic_nodes"] != 36 or len(cases["cases"]) != 36:
        raise ValueError("Historical 36-node evidence differs")
    rows, resolved = [], []
    for tid, task in formal["tasks"].items():
        info = store["tasks"][tid]["graphs"]["F3"]
        prepared = read(checked(task["prepared"]["0/1"]))
        if info["graph"] != prepared["profiles"]["G3R"]["graph"]:
            raise ValueError("Archived semantic graph differs")
        graph = read_graph(checked(task["record"]["original_graph"]))
        archived = read_graph(checked(info["graph"]))
        audit = read(checked(info["audit"]))
        encoder = TokenEncoder(task["record"]["feature"])
        for file, reference in sorted(task["record"]["sources"].items()):
            ident = task["record"]["category"] + "/" + file
            row = sources[ident]
            if row["source"] != reference:
                raise ValueError("Task source mismatch")
            source, result = load_result(row)
            record = dict(task=tid, file=file, identity=ident, source=reference)
            if result["status"] != "renamed":
                record.update(status="syntax_fallback", passed=False, errors=result["issues"])
            else:
                ids = [n for n, a in graph.nodes(data=True) if a["source_file"] == file]
                base = graph.subgraph(ids).copy()
                try:
                    comparison = check_file(base, archived, audit, source, file, result,
                                            reference.get("metadata"), encoder)
                except (ValueError, AssertionError) as exc:
                    record.update(status="semantic_failed", passed=False, error=str(exc))
                else:
                    record.update(comparison, status="semantic_pass" if comparison["passed"] else "semantic_failed")
                    indexed = {p["node"]: p for p in comparison["node_code_proof"]}
                    for case in cases["cases"]:
                        if case["task"] != tid or case["identity"] != ident:
                            continue
                        if base.nodes[case["node"]]["code"] != case["code"]:
                            raise ValueError("Historical synthetic text differs")
                        proof = indexed[case["node"]]
                        if proof["basis"] != "all_exact_ast_text_matches_agree":
                            raise ValueError("Synthetic projection no longer follows exact matching")
                        old_ids = {c["ast_id"] for c in case["candidates"]}
                        if set(proof["compat_ast_ids"]) != old_ids:
                            raise ValueError("Synthetic candidate identities differ")
                        resolved.append(dict(task=tid, identity=ident, source=reference, node=case["node"],
                                             proof=proof, all_exact_candidates_agree=True))
            record.update(whole_file_fallback=not record["passed"], committed_feature_edits=0)
            rows.append(record)
        write(output/(tid+".json"), [r for r in rows if r["task"] == tid])
        print(tid, dict(Counter(r["status"] for r in rows if r["task"] == tid)), flush=True)
    if len(rows) != manifest["task_file_references"]:
        raise ValueError("Task/file coverage missing")
    write(output/"previous_36_nodes.json", dict(previous=ref(historical_cases),
          expected=36, resolved=len(resolved), passed=len(resolved) == 36, nodes=resolved))
    passed = all(r["passed"] for r in rows) and len(resolved) == 36
    summary = dict(naming=ref(Path(naming)/"manifest.json"), store=ref(store_path),
        implementation=implementation(), task_file_decisions=len(rows),
        counts=dict(Counter(r["status"] for r in rows)), passed=passed,
        artifacts={tid:ref(output/(tid+".json")) for tid in formal["tasks"]},
        synthetic_resolution=ref(output/"previous_36_nodes.json"),
        old_graphs_unchanged=True, no_new_model_graphs=True, no_sample_deletion=True,
        hgt_training_executed=0, classifier_fits=0, execution_authorized=False)
    write(output/"summary.json", summary)
    write(output/"summary.seal.json", dict(summary=ref(output/"summary.json")))
    return summary


def blocked_decision(naming, semantic, output):
    manifest, sources, summary, rows = verify_semantics(naming, semantic)
    if summary["passed"]:
        raise ValueError("Semantic gate passed; complete P2/P3 and feature gates before any plan")
    output = Path(output)
    output.mkdir(exist_ok=False)
    old = read(checked(manifest["old_plan"]))
    failures = [r for r in rows if not r["passed"]]
    decision = dict(status="blocked_by_semantic_gate", naming=ref(Path(naming)/"manifest.json"),
        semantic=ref(Path(semantic)/"summary.json"), failed_task_files=len(failures),
        failed_source_identities=len({r["identity"] for r in failures}),
        failures=[dict(task=r["task"], identity=r["identity"], source=r["source"],
                       detail=summary["artifacts"][r["task"]]) for r in failures],
        execution_authorized=False, ready_for_training=False, ready_for_probes=False,
        formal_fit_count=0, diagnostic_classifier_fits=0, new_features_created=False,
        new_executable_plan_created=False, no_samples_removed=True,
        future_matrix=dict(old_plan=manifest["old_plan"], fit_count=old["fit_count"],
                           grouped_folds={k:v["folds"] for k,v in old["tasks"].items()},
                           timing=old["bound_artifacts"]["timing"]),
        unexecuted=["P2/P3/role-AUC", "keyword prediction baseline", "new token features",
                    "model assembly/identity proof", "170-fit plan/seal", "formal training"],
        reason="Prompt8G section2/3 explicitly requires stop at failed gate; no policy retuning")
    write(output/"acceptance_decision.json", decision)
    write(output/"acceptance_decision.seal.json", dict(decision=ref(output/"acceptance_decision.json")))
    write(output/"authorization_template.json", dict(execution_authorized=False,
          ready_for_training=False, not_an_execution_plan=True,
          blocked_by=ref(output/"acceptance_decision.json")))
    return decision


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("names")
    p.add_argument("--prior", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("semantic")
    for name in ("naming", "store", "historical-cases", "output"):
        p.add_argument("--"+name, required=True)
    p = sub.add_parser("decision")
    for name in ("naming", "semantic", "output"):
        p.add_argument("--"+name, required=True)
    args = parser.parse_args()
    if args.command == "names":
        result = prepare_names(args.prior, args.output)
        print({k: result[k] for k in ("source_identities", "renamed_files", "fallback_files")})
    elif args.command == "semantic":
        print(run_semantic(args.naming, args.store, args.historical_cases, args.output)["counts"])
    elif args.command == "decision":
        print(blocked_decision(args.naming, args.semantic, args.output)["status"])
    else:
        parser.error("Choose names, semantic or decision")


if __name__ == "__main__":
    main()
