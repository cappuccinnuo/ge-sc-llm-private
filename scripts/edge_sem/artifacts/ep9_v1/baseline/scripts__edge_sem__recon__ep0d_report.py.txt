"""EP0d tables: preserve EP0c identities and explain every changed binding."""
import re
from collections import Counter
from .common import ROOT, ref, read, write, checked
from .ep0d_common import OUT, EP0C, TASKS


def edge_key(row):
    return (row["file"], row["source_sha256"], row["source_node"],
            row["target_node"], row["edge_key"])


def call_key(row):
    return (row["file"], row["source_sha256"], tuple(row["call_anchor"]))


def pair_key(row):
    return (row["file"], row["source_sha256"], row["source_node"], row["target_node"])


def compare(previous, current):
    old_edges = {edge_key(r): r for r in previous["reference_edges"]}
    new_edges = {edge_key(r): r for r in current["reference_edges"]}
    assert set(old_edges) == set(new_edges)
    transitions, changed_edges = [], []
    for ident, row in new_edges.items():
        old = old_edges[ident]
        item = dict(file=row["file"], source_sha256=row["source_sha256"],
            source_node=row["source_node"], target_node=row["target_node"],
            edge_key=row["edge_key"], source_anchor=row["source_anchor"],
            target_anchor=row["target_anchor"], before=old["reference_class"],
            after=row["reference_class"], covered_before=old["r5_covered"],
            covered_after=row["r5_covered"])
        transitions.append(item)
        if item["before"] != item["after"]:
            changed_edges.append(dict(identity=item, previous=old, current=row))
    old_calls = {call_key(r): r for r in previous["raw_calls"]}
    new_calls = {call_key(r): r for r in current["raw_calls"]}
    assert set(old_calls) == set(new_calls)
    changed_calls = []
    for ident, row in new_calls.items():
        old = old_calls[ident]
        if old["status"] == "resolved":
            assert row == old, ("prior resolved call changed", ident)
        if row != old:
            changed_calls.append(dict(previous=old, current=row))
    old_pairs = {pair_key(r): r for r in previous["projected_call_sites"]}
    new_pairs = {pair_key(r): r for r in current["projected_call_sites"]}
    assert set(old_pairs) <= set(new_pairs)
    for ident, old in old_pairs.items():
        row = new_pairs[ident]
        assert old["owner_node"] == row["owner_node"]
        assert old["statement_anchor"] == row["statement_anchor"]
        assert old["target_anchor"] == row["target_anchor"]
        assert set(old["kinds"]) <= set(row["kinds"])
        assert set(map(tuple, old["call_anchors"])) <= set(map(tuple, row["call_anchors"]))
    added = [r for k, r in new_pairs.items() if k not in old_pairs]
    counts = Counter((r["before"], r["after"]) for r in transitions)
    return dict(
        reference_edge_transitions=transitions, changed_reference_edges=changed_edges,
        transition_counts=[dict(before=a, after=b, count=n) for (a,b),n in sorted(counts.items())],
        changed_calls=changed_calls, added_call_sites=added,
        added_by_kind=dict(Counter(k for r in added for k in r["kinds"])),
        previous_candidate_count=len(old_pairs), current_candidate_count=len(new_pairs),
        prior_resolved_calls_unchanged=True, prior_candidate_pairs_preserved=True,
        raw_call_transition_counts=[dict(before=a, after=b, reason=c, count=n)
            for (a,b,c),n in sorted(Counter(
                (r["previous"]["status"], r["current"]["status"], r["current"]["reason"])
                for r in changed_calls).items())])


def collect():
    data = {t: read(OUT/("calls_"+t+".json")) for t in TASKS}
    differences = {}
    equivalence = {}
    review = {}
    for task, d in data.items():
        previous = read(checked(d["ep0c_ref"]))
        differences[task] = compare(previous, d)
        eq = d["binding_equivalence"]
        equivalence[task] = dict(
            files=len(eq), prior_calls=sum(r["prior_calls"] for r in eq),
            eligible=sum(r["eligible"] for r in eq),
            ineligible=sum(r["ineligible"] for r in eq),
            all_equal=all(r["all_equal"] for r in eq))
        rows = d["reference_edges"]
        unknown = [r for r in rows if r["reference_class"] == "undetermined"]
        review[task] = dict(
            unknown_edges=unknown,
            unknown_edge_reason_counts=dict(Counter(
                "|".join(sorted(set(c["reason"] for c in r["expression_candidates"])))
                for r in unknown)),
            unprojected_confirmed=[r for r in rows
                if r["reference_class"] == "internal_confirmed" and not r["r5_covered"]],
            rebinding_edges=[r for r in rows if r["reference_class"] == "rebinding"],
            no_corresponding_hcg_edges=[r for r in d["projected_call_sites"] if r["absent_from_hcg"]],
            no_expression_edges=[r for r in rows if r["reference_class"] == "no_expression"])
    tests = {}
    for name in ("edge_tests", "nodesem_tests", "dfg_tests"):
        receipt_path = OUT/("execution/"+name+".json")
        receipt = read(receipt_path)
        assert receipt["exit_code"] == 0
        counts = re.findall(r"(?m)^(\d+) passed", checked(receipt["log"]).read_text())
        assert len(counts) == 1
        tests[name] = dict(passed=int(counts[0]), receipt=ref(receipt_path))
    write(OUT/"ep0c_comparison.json", differences)
    write(OUT/"gap_review.json", review)
    before = read(OUT/"before.json")
    sources = [ROOT/"scripts/edge_sem/call_resolve.py",
               ROOT/"scripts/edge_sem/tests/test_call_resolve.py"]
    sources += sorted((ROOT/"scripts/edge_sem/recon").glob("ep0d_*.py"))
    summary = dict(
        task_summaries={t:d["summary"] for t,d in data.items()},
        comparisons={t:{k:v for k,v in r.items() if k not in (
            "reference_edge_transitions", "changed_reference_edges", "changed_calls", "added_call_sites")}
            for t,r in differences.items()},
        binding_equivalence=equivalence, tests=tests,
        test_total=sum(r["passed"] for r in tests.values()),
        gate_pass=all(d["summary"]["gate_pass"] for d in data.values()),
        stop_after="EP0d", no_automatic_ep1=True, training_executed=False,
        evidence_refs=[ref(OUT/("calls_"+t+".json")) for t in TASKS]
            + [ref(OUT/"ep0c_comparison.json"), ref(OUT/"gap_review.json"),
               ref(OUT/"adjustment_approval.json")],
        current_source_refs=[ref(p) for p in sources], prior_head=before["head"], prompt=before["prompt"],
        coarse_count_provenance=dict(
            historical_r5="Retained as historical rough_expected/rough_delta in census; not a current acceptance target.",
            r6="Corrects unconfirmed conversion_new_or_wrapper exclusions; only proven excluded kinds counted.",
            corrected_reference={t:d["summary"]["rough_observed"] for t,d in data.items()}),
        limitations=[
            "Projection coverage is conditional on this resolver, not independent semantic recall or precision.",
            "Raw calls, parallel HCG function edges and deduplicated statement pairs have different denominators.",
            "Same-arity overloads, super and unsupported receivers remain unresolved; no new dispatch rules.",
            "Approved receiver adapter only classifies address builtins; it never creates a function target.",
            "No new graph, attribute vector, label/fold/feature change or formal training."])
    write(OUT/"summary.json", summary)
    print("EP0d report data saved; gate", summary["gate_pass"], "tests", summary["test_total"], flush=True)


if __name__ == "__main__":
    collect()
