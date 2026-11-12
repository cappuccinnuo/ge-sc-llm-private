"""EP0e evidence tables; failed coverage gates are reported, never tuned here."""
import re
from collections import Counter, defaultdict
from .common import ROOT, ref, read, checked, write
from .ep0e_common import OUT, EP0D, TASKS
from .ep0d_report import compare, call_key


def projection_delta(previous, current):
    old_calls = {call_key(r):r for r in previous["raw_calls"]}
    added = [r for r in current["raw_calls"] if r["status"] == "resolved"
             and old_calls[call_key(r)]["status"] != "resolved"]
    old_pairs = {(r["source_node"], r["target_node"]) for r in previous["projected_call_sites"]}
    sites = {call_key(r):r for r in current["call_sites"]}
    counts, groups = Counter(), defaultdict(list)
    for row in added:
        site = sites.get(call_key(row))
        if site is None:
            counts["absent_from_statement_calls"] += 1
        elif not site["projected"]:
            counts["unprojected"] += 1
        elif (site["source_node"], site["target_node"]) in old_pairs:
            counts["already_existing_pair"] += 1
        else:
            counts["new_pair_call"] += 1
            groups[(site["source_node"], site["target_node"])].append(row)
    return dict(newly_resolved_calls=len(added), disposition=dict(counts),
                unique_new_pairs=len(groups), coalesced_extra_calls=sum(len(v)-1 for v in groups.values()))


def collect():
    data = {t:read(OUT/("calls_"+t+".json")) for t in TASKS}
    differences, equivalence, review, projections = {}, {}, {}, {}
    identities = {}
    residual = read(OUT/"residual_evidence.json")
    for task, d in data.items():
        previous = read(checked(d["ep0d_ref"]))
        differences[task] = compare(previous, d)
        projections[task] = projection_delta(previous, d)
        eq = d["binding_equivalence"]
        equivalence[task] = dict(files=len(eq), prior_calls=sum(r["prior_calls"] for r in eq),
            eligible=sum(r["eligible"] for r in eq), ineligible=sum(r["ineligible"] for r in eq),
            all_equal=all(r["all_equal"] for r in eq))
        rows = d["reference_edges"]
        misses = [r for r in d["using_candidates"] if r["candidate"] and not r["matched"]]
        review[task] = dict(using_misses=misses,
            misses_by_file_reason=[dict(file=f,source_sha256=sha,reason=reason,count=n)
                for (f,sha,reason),n in sorted(Counter((r["file"],r["source_sha256"],r["miss_reason"])
                                                      for r in misses).items())],
            outside_candidates=[r for r in d["using_candidates"] if r["outside_candidate"]],
            unknown_edges=[r for r in rows if r["reference_class"]=="undetermined"],
            unprojected_confirmed=[r for r in rows if r["reference_class"]=="internal_confirmed" and not r["r5_covered"]],
            rebinding_edges=[r for r in rows if r["reference_class"]=="rebinding"],
            no_corresponding_hcg_edges=[r for r in d["projected_call_sites"] if r["absent_from_hcg"]],
            no_expression_edges=[r for r in rows if r["reference_class"]=="no_expression"],
            residual_call_options=residual[task]["residual_option_shapes"])
        identities[task] = {(r["file"],r["source_sha256"],tuple(r["call_anchor"]),tuple(r["expected_target"]))
                            for r in d["using_candidates"] if r["candidate"]}
    tests = {}
    for name in ("edge_tests","nodesem_tests","dfg_tests"):
        p = OUT/("execution/"+name+".json")
        receipt = read(p)
        assert receipt["exit_code"] == 0
        counts = re.findall(r"(?m)^(\d+) passed", checked(receipt["log"]).read_text())
        assert len(counts) == 1
        tests[name] = dict(passed=int(counts[0]),receipt=ref(p))
    write(OUT/"ep0d_comparison.json", differences)
    write(OUT/"gap_review.json", review)
    before = read(OUT/"before.json")
    sources = [ROOT/"scripts/edge_sem/call_resolve.py",ROOT/"scripts/edge_sem/tests/test_call_resolve.py"]
    sources += sorted((ROOT/"scripts/edge_sem/recon").glob("ep0e_*.py"))
    hcg_pass = all(d["summary"]["gate_pass"] for d in data.values())
    using_pass = all(d["using_summary"]["gate_pass"] for d in data.values())
    summary = dict(
        task_summaries={t:d["summary"] for t,d in data.items()},
        using_summaries={t:d["using_summary"] for t,d in data.items()},
        comparisons={t:{k:v for k,v in d.items() if k not in (
            "reference_edge_transitions","changed_reference_edges","changed_calls","added_call_sites")}
            for t,d in differences.items()},
        binding_equivalence=equivalence, projection_delta=projections,
        candidate_identity_overlap=dict(
            equal=identities[TASKS[0]]==identities[TASKS[1]],
            common_exact_identities=len(identities[TASKS[0]] & identities[TASKS[1]]),
            identity="file, source SHA256, call anchor, expected declaration anchor; task remains separate"),
        tests=tests,test_total=sum(r["passed"] for r in tests.values()),
        hcg_gate_pass=hcg_pass,library_gate_pass=using_pass,gate_pass=hcg_pass and using_pass,
        stop_after="EP0e",no_automatic_ep1=True,training_executed=False,
        evidence_refs=[ref(OUT/("calls_"+t+".json")) for t in TASKS]+[
            ref(OUT/"ep0d_comparison.json"),ref(OUT/"gap_review.json"),ref(OUT/"residual_evidence.json"),
            ref(OUT/"wildcard_approval.json"),ref(OUT/"audit_plan.json"),ref(OUT/"development_notes.json")],
        current_source_refs=[ref(p) for p in sources],prior_head=before["head"],prompt=before["prompt"],
        coarse_count_provenance=dict(
            corrected_reference={t:d["summary"]["rough_observed"] for t,d in data.items()},
            r7_intro="Historical approximate counts are not a gate or an alternate denominator.",
            actual_non_target=[dict(task=t,call_option=d["summary"]["call_statuses"].get("call_option",0),
                abi_builtin=sum(r["reason"]=="unshadowed_abi_builtin" for r in d["raw_calls"]),
                residual_option_shapes=len(residual[t]["residual_option_shapes"])) for t,d in data.items()]),
        limitations=[
            "Library recall uses the preregistered structural candidate set, not compiler-confirmed true calls or vulnerability labels.",
            "Method-name uniqueness in binding is stricter than name-plus-arity uniqueness in the candidate set; rules were not changed after observing the gate.",
            "Canonical strings do not equate qualified and bare struct declarations.",
            "Unbound receivers, external return types and compound parser shapes remain unknown.",
            "One prefix-wrapped call-option receiver remains unknown in access control; intermediate option classification is not outer call resolution.",
            "Same numeric summaries across tasks do not merge distinct source SHA/cohort identities.",
            "All old resolved bindings are preserved; this is not independent semantic proof of their correctness.",
            "No production graph, edge attribute vector or training was created."])
    write(OUT/"summary.json",summary)
    print("EP0e report saved; HCG gate",hcg_pass,"library gate",using_pass,"tests",summary["test_total"],flush=True)


if __name__=="__main__":
    collect()
