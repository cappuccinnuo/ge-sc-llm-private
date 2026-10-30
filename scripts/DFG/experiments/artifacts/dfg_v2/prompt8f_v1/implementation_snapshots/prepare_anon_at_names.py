"""Prompt 8F names/parity/decision entry point; no training or partial-view probes.

The user approved stopping before all-population probes/features/planning when
whole-file fallbacks remain. No file is dropped or silently kept under N-anon.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.labeling_v2.safe_graph import read_graph
from ..tokens import TokenEncoder
from .anon_binding import VERSION, RESERVED, KEYWORD_STRINGS, anonymize, replace_spans
from .anon_parity import check_file
from .prepare import read, write, ref, checked, verify_prepared, sha


def load_names(directory):
    directory = Path(directory)
    manifest = read(directory/"manifest.json")
    if read(directory/"manifest.seal.json")["manifest"] != ref(directory/"manifest.json"):
        raise ValueError("Anonymous-name manifest seal differs")
    for path in manifest["artifacts"].values():
        checked(path)
    rows = read(checked(manifest["artifacts"]["sources"]))
    for row in rows.values():
        checked(row["source"])
        checked(row["result"])
    return manifest, rows


def require_complete(manifest, rows):
    if len(rows) != manifest["source_identities"] or any(
            read(checked(row["result"]))["status"] != "renamed" for row in rows.values()):
        raise ValueError("Whole-file fallbacks forbid full N-anon probes/features/plan")
    if manifest["fallback_files"] or not manifest["binding_complete"]:
        raise ValueError("Binding coverage not complete")


def prepare_names(old_plan_path, old8e_manifest, output):
    output = Path(output); output.mkdir(exist_ok=False)
    verify_prepared(old_plan_path)
    old = read(old_plan_path)
    formal_ref = old["bound_artifacts"]["historical_plan"]
    formal = read(checked(formal_ref))
    e = read(old8e_manifest)
    if e["formal_plan"] != formal_ref:
        raise ValueError("8E/formal input binding differs")
    if read(Path(old8e_manifest).with_name("manifest.seal.json"))["manifest"] != ref(old8e_manifest):
        raise ValueError("8E naming seal differs")
    refs = {}
    task_files = {}
    for tid, task in formal["tasks"].items():
        task_files[tid] = []
        category = task["record"]["category"]
        for file, reference in task["record"]["sources"].items():
            ident = category + "/" + file
            if ident in refs and refs[ident]["source"] != reference:
                raise ValueError("Contract/node source or metadata differs")
            refs.setdefault(ident, dict(file=file, category=category, source=reference))
            task_files[tid].append(ident)
    if len(refs) != 256 or sum(len(v) for v in task_files.values()) != 384:
        raise ValueError("Frozen source/task-file population differs")
    statuses, issue_files, role_counts, preserved = Counter(), Counter(), Counter(), Counter()
    for ident, row in sorted(refs.items()):
        source = checked(row["source"]).read_text(encoding="utf8")
        result = anonymize(source, row["source"].get("metadata"))
        if result["source_sha256"] != row["source"]["sha256"]:
            raise ValueError("Source decoding changed bytes")
        # Reconstruct from spans; do not duplicate full plaintext source in artifacts.
        if replace_spans(source, result["edits"]) != result["rewritten"]:
            raise AssertionError("Edit reconstruction differs")
        del result["rewritten"]
        statuses[result["status"]] += 1
        issue_files.update({v["reason"].split(":")[0] for v in result["issues"]})
        role_counts.update(d["role"] for d in result["declarations"])
        preserved.update(result.get("preserved_counts", {}))
        folder = output/row["category"]
        folder.mkdir(exist_ok=True)
        path = folder/(row["file"]+".json")
        write(path, result)
        row["result"] = ref(path)
        row["status"] = result["status"]
    policy = dict(version=VERSION, prefix="v", reserved_spellings=sorted(RESERVED),
        additional_reserved_pattern="(?:u?fixed)[0-9]+x[0-9]+",
        keyword_strings=list(KEYWORD_STRINGS), all_roles_share_prefix=True,
        numbering="source-SHA seeded random permutation, unique declaration identity; avoid existing vN",
        constructor_exception="old-style constructor aliases its owning contract; explicitly user approved",
        fallback="entire file identity; no committed edits; never included as a successful N-anon view",
        completion_gate="user approved: any fallback blocks full probes, features and runnable 170-fit seal",
        unknown_binding="same-source conservative resolver; no dispatch/overload/assembly guessing",
        old_N_real_read_only=True, models_or_labels_read_by_binding=False)
    write(output/"sources.json", refs); write(output/"policy.json", policy)
    write(output/"task_files.json", task_files)
    write(output/"preserved_counts.json", dict(preserved))
    manifest = dict(version=VERSION, old_plan=ref(old_plan_path),
        old8e_manifest=ref(old8e_manifest), formal_plan=formal_ref,
        source_identities=len(refs), task_file_references=sum(len(v) for v in task_files.values()),
        renamed_files=statuses["renamed"], fallback_files=statuses["fallback"],
        binding_complete=statuses["fallback"] == 0, issue_files=dict(issue_files),
        declaration_roles=dict(role_counts), artifacts={k: ref(output/(k+".json"))
            for k in ("sources","policy","task_files","preserved_counts")},
        implementation={p: ref(Path(__file__).with_name(p)) for p in
                        ("anon_binding.py","anon_parity.py","prepare_anon.py")},
        execution_authorized=False, training_executed=0, feature_views_written=False)
    write(output/"manifest.json", manifest)
    write(output/"manifest.seal.json", dict(manifest=ref(output/"manifest.json")))
    return manifest


def run_semantic(naming, store_path, output):
    output=Path(output); output.mkdir(exist_ok=False)
    manifest, sources=load_names(naming)
    formal=read(checked(manifest["formal_plan"]))
    store=read(store_path)
    if read(Path(store_path).with_name("store.seal.json"))["store_sha256"] != sha(store_path):
        raise ValueError("Store seal differs")
    rows=[]
    for tid, task in formal["tasks"].items():
        info=store["tasks"][tid]["graphs"]["F3"]
        prepared=read(checked(task["prepared"]["0/1"]))
        if info["graph"] != prepared["profiles"]["G3R"]["graph"]:
            raise ValueError("Archived semantic graph differs")
        graph=read_graph(checked(task["record"]["original_graph"]))
        archived=read_graph(checked(info["graph"]))
        audit=read(checked(info["audit"]))
        encoder=TokenEncoder(task["record"]["feature"])
        for file, reference in sorted(task["record"]["sources"].items()):
            ident=task["record"]["category"]+"/"+file
            row=sources[ident]
            if row["source"] != reference:
                raise ValueError("Source identity differs")
            result=read(checked(row["result"]))
            source=checked(reference).read_text(encoding="utf8")
            record=dict(task=tid, file=file, identity=ident, source=reference)
            if result["status"] == "fallback":
                if result["edits"] or result["bindings"]:
                    raise ValueError("Partial edits survived whole-file fallback")
                record.update(status="binding_fallback", passed=False,
                              source_identity_unchanged=True, no_partial_edits=True,
                              reason_categories=sorted({v["reason"].split(":")[0] for v in result["issues"]}),
                              semantic_comparison_executed=False)
            else:
                result["rewritten"]=replace_spans(source,result["edits"])
                ids=[n for n, attrs in graph.nodes(data=True) if attrs["source_file"]==file]
                base=graph.subgraph(ids).copy()
                try:
                    comparison=check_file(base,archived,audit,source,file,result,
                                          reference.get("metadata"),encoder)
                except (ValueError, AssertionError) as exc:
                    record.update(status="semantic_check_failed",passed=False,
                                  error=str(exc),semantic_comparison_executed=True)
                else:
                    record.update(comparison,status="semantic_pass" if comparison["passed"] else "semantic_check_failed",
                                  semantic_comparison_executed=True)
            rows.append(record)
        write(output/(tid+".json"),[v for v in rows if v["task"]==tid])
        print(tid,dict(Counter(x["status"] for x in rows if x["task"]==tid)),flush=True)
    if len(rows) != manifest["task_file_references"]:
        raise ValueError("Missing task/file parity decision")
    summary=dict(naming=ref(Path(naming)/"manifest.json"),store=ref(store_path),
                 task_file_decisions=len(rows),counts=dict(Counter(x["status"] for x in rows)),
                 all_files_anonymous_and_equal=all(x["passed"] for x in rows),
                 artifacts={tid:ref(output/(tid+".json")) for tid in formal["tasks"]},
                 original_inputs_changed=False,original_graphs_rebuilt=False,
                 temporary_analysis_outputs_discarded=True,hgt_training_executed=0)
    write(output/"summary.json",summary)
    write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    return summary


def decide(naming, semantic, output):
    output=Path(output);output.mkdir(exist_ok=False)
    manifest, sources=load_names(naming)
    sem_path=Path(semantic)/"summary.json"
    sem=read(sem_path)
    if read(Path(semantic)/"summary.seal.json")["summary"] != ref(sem_path):
        raise ValueError("Semantic summary seal differs")
    if sem["naming"] != ref(Path(naming)/"manifest.json"):
        raise ValueError("Semantic/name manifests differ")
    for v in sem["artifacts"].values():
        checked(v)
    old=read(checked(manifest["old_plan"]))
    blocked=bool(manifest["fallback_files"]) or not sem["all_files_anonymous_and_equal"]
    if not blocked:
        raise ValueError("Binding complete: full original P2/P3 and feature gates still required; cannot seal training here")
    decision=dict(status="blocked_by_binding_or_semantic_gate",execution_authorized=False,
        ready_for_probes=False,ready_for_training=False,naming=ref(Path(naming)/"manifest.json"),
        semantic=ref(sem_path),fallback_files=manifest["fallback_files"],counts=sem["counts"],
        formal_training=0,diagnostic_classifier_fits=0,
        future_matrix=dict(old_plan=manifest["old_plan"],fit_count=old["fit_count"],
                           grouped_folds={k:v["folds"] for k,v in old["tasks"].items()},
                           timing=old["bound_artifacts"]["timing"],
                           label_policy_default=old["label_policy_default"],
                           not_a_new_executable_plan=True),
        unexecuted=["P2/P3/role-AUC","keyword model baseline","TokenEncoder new feature NPZ",
                    "identity/anonymous model assembly","new 170-fit plan and seal","formal training"],
        no_samples_dropped=True,no_old_artifacts_changed=True,
        approved_stop="user explicitly approved blocking full-population plan when file fallbacks remain",
        interpretation="No partial renamed subset is represented as a completed N-anon benchmark.")
    write(output/"acceptance_decision.json",decision)
    write(output/"acceptance_decision.seal.json",
          dict(decision=ref(output/"acceptance_decision.json")))
    write(output/"authorization_template.json",dict(execution_authorized=False,
          ready_for_training=False,blocked_by=ref(output/"acceptance_decision.json"),
          requested_choices_later=["label_policy","seed_count","execution_location"],
          not_an_execution_plan=True))
    return decision


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command")
    a=sub.add_parser("names")
    a.add_argument("--old-plan",required=True);a.add_argument("--old8e-manifest",required=True)
    a.add_argument("--output",required=True)
    a=sub.add_parser("semantic")
    a.add_argument("--naming",required=True);a.add_argument("--store",required=True)
    a.add_argument("--output",required=True)
    a=sub.add_parser("decision")
    a.add_argument("--naming",required=True);a.add_argument("--semantic",required=True)
    a.add_argument("--output",required=True)
    args=p.parse_args()
    if args.command=="names":
        result=prepare_names(args.old_plan,args.old8e_manifest,args.output)
        print({k:result[k] for k in ("source_identities","renamed_files","fallback_files")})
    elif args.command=="semantic":
        print(run_semantic(args.naming,args.store,args.output)["counts"])
    elif args.command=="decision":
        print(decide(args.naming,args.semantic,args.output)["status"])
    else:
        p.error("Choose names, semantic or decision")


if __name__=="__main__":
    main()
