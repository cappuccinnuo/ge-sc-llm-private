"""Independently recompute EP0d counts, EP0c deltas and frozen inputs."""
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from .common import ROOT, ref, read, checked, write
from .ep0d_common import OUT, TASKS, EP0B, EP0C
from scripts.edge_sem.call_resolve import FROZEN_AST_SHA256

def verify_ep0c_delta(task, current, summary):
    previous = read(checked(current["ep0c_ref"]))
    assert checked(current["ep0c_ref"]) == EP0C/("calls_"+task+".json")
    comparison = read(OUT/"ep0c_comparison.json")[task]
    ekey = lambda r: (r["file"], r["source_sha256"], r["source_node"], r["target_node"], r["edge_key"])
    ckey = lambda r: (r["file"], r["source_sha256"], tuple(r["call_anchor"]))
    pkey = lambda r: (r["file"], r["source_sha256"], r["source_node"], r["target_node"])
    old_edges = {ekey(r):r for r in previous["reference_edges"]}
    new_edges = {ekey(r):r for r in current["reference_edges"]}
    assert len(old_edges) == len(previous["reference_edges"])
    assert len(new_edges) == len(current["reference_edges"])
    assert set(old_edges) == set(new_edges)
    ledger, changed = [], []
    for ident, row in new_edges.items():
        old = old_edges[ident]
        for field in ("source_anchor", "target_anchor", "target_file", "ep0_covered", "ep0b_category"):
            assert row[field] == old[field]
        item = dict(file=row["file"], source_sha256=row["source_sha256"],
            source_node=row["source_node"], target_node=row["target_node"],
            edge_key=row["edge_key"], source_anchor=row["source_anchor"],
            target_anchor=row["target_anchor"], before=old["reference_class"],
            after=row["reference_class"], covered_before=old["r5_covered"], covered_after=row["r5_covered"])
        ledger.append(item)
        if item["before"] != item["after"]:
            changed.append(dict(identity=item, previous=old, current=row))
        assert [c["call_anchor"] for c in old["expression_candidates"]] == [
            c["call_anchor"] for c in row["expression_candidates"]]
    assert ledger == comparison["reference_edge_transitions"]
    assert changed == comparison["changed_reference_edges"]
    counts = Counter((r["before"], r["after"]) for r in ledger)
    assert comparison["transition_counts"] == [
        dict(before=a, after=b, count=n) for (a,b),n in sorted(counts.items())]
    old_calls = {ckey(r):r for r in previous["raw_calls"]}
    new_calls = {ckey(r):r for r in current["raw_calls"]}
    assert set(old_calls) == set(new_calls)
    changed_calls = []
    for ident, row in new_calls.items():
        old = old_calls[ident]
        for field in ("expression", "owner_anchor", "source_line"):
            assert row[field] == old[field]
        if old["status"] == "resolved":
            assert row == old, ("old resolved target changed", ident)
        if row != old:
            changed_calls.append(dict(previous=old, current=row))
            if row["status"] == "resolved":
                assert row["reason"] == "postfix_callee"
            elif row["status"] == "address_builtin":
                assert row["target_anchor"] is None and row["target_node"] is None
    assert changed_calls == comparison["changed_calls"]
    call_counts = Counter((r["previous"]["status"], r["current"]["status"], r["current"]["reason"])
                          for r in changed_calls)
    assert comparison["raw_call_transition_counts"] == [
        dict(before=a, after=b, reason=c, count=n) for (a,b,c),n in sorted(call_counts.items())]
    old_pairs = {pkey(r):r for r in previous["projected_call_sites"]}
    new_pairs = {pkey(r):r for r in current["projected_call_sites"]}
    assert set(old_pairs) <= set(new_pairs)
    for ident, old in old_pairs.items():
        row = new_pairs[ident]
        for field in ("owner_node", "statement_anchor", "target_anchor"):
            assert row[field] == old[field]
        assert set(old["kinds"]) <= set(row["kinds"])
        assert set(map(tuple, old["call_anchors"])) <= set(map(tuple, row["call_anchors"]))
    added = [r for k,r in new_pairs.items() if k not in old_pairs]
    assert added == comparison["added_call_sites"]
    assert dict(Counter(k for r in added for k in r["kinds"])) == comparison["added_by_kind"]
    assert len(old_pairs) == comparison["previous_candidate_count"]
    assert len(new_pairs) == comparison["current_candidate_count"]
    assert comparison["prior_resolved_calls_unchanged"] and comparison["prior_candidate_pairs_preserved"]
    short = {k:v for k,v in comparison.items() if k not in (
        "reference_edge_transitions", "changed_reference_edges", "changed_calls", "added_call_sites")}
    assert short == summary["comparisons"][task]

    eq = current["binding_equivalence"]
    assert {r["file"] for r in eq} == {r["file"] for r in current["files"]}
    assert len(eq) == len(current["files"])
    for file_row in eq:
        originals = {tuple(r["call_anchor"]):r for r in previous["raw_calls"] if r["file"] == file_row["file"]}
        assert len(originals) == file_row["prior_calls"]
        assert file_row["eligible"] == len(file_row["rows"])
        assert file_row["prior_calls"] == file_row["eligible"] + file_row["ineligible"]
        assert file_row["all_equal"]
        assert len({tuple(r["call_anchor"]) for r in file_row["rows"]}) == file_row["eligible"]
        for item in file_row["rows"]:
            assert tuple(item["call_anchor"]) in originals
            assert originals[tuple(item["call_anchor"])]["source_sha256"] == file_row["source_sha256"]
            assert item["callee_type"] in ("identifier", "member_expression")
            assert item["equal"] and item["frozen_target"] == item["adapter_target"]
    eq_summary = dict(files=len(eq), prior_calls=sum(r["prior_calls"] for r in eq),
        eligible=sum(r["eligible"] for r in eq), ineligible=sum(r["ineligible"] for r in eq),
        all_equal=all(r["all_equal"] for r in eq))
    assert eq_summary["prior_calls"] == len(previous["raw_calls"])
    assert eq_summary == summary["binding_equivalence"][task]
    return dict(changed_reference_edges=len(changed), added_call_sites=len(added),
                changed_calls=len(changed_calls), equivalent_calls=eq_summary["eligible"])


def verify():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.doc_check import check
    import torch
    before,summary=read(OUT/"before.json"),read(OUT/"summary.json")
    assert _code_refs()==before["dfg_code_refs"]
    for row in before["frozen_code"]+before["prior_artifacts"]+before["prior_edge_sources"]:
        checked(row)
    for name in ("prompt","plan","seal","historical_verification"):
        checked(before[name])
    for item in before["authorized_source_changes"]:
        checked(item["snapshot"])
        assert item["snapshot"]["sha256"] == item["original"]["sha256"]
    approval = read(OUT/"adjustment_approval.json")
    assert approval["question_id"] == "call_7cab29425d0b48cfb024710290cfaba9"
    assert not approval["training_authorized"]
    assert approval["current_resolver_sha256"] == ref(ROOT/"scripts/edge_sem/call_resolve.py")["sha256"]
    load(before["plan"]["path"])
    assert ref(ROOT/"scripts/node_sem/facts_ast.py")["sha256"]==FROZEN_AST_SHA256
    prior=read(EP0B/"verification.json")
    for row in prior["input_refs"]:
        checked(row)
    assert summary["prior_head"]==before["head"]
    for row in summary["current_source_refs"]+summary["evidence_refs"]:
        checked(row)

    task_receipts={}
    for task in TASKS:
        d=read(OUT/("calls_"+task+".json"))
        delta_receipt=verify_ep0c_delta(task,d,summary)
        for source_ref in d["current_source_refs"]:
            checked(source_ref)
        old=read(EP0B/("calls_refined_"+task+".json"))
        assert d["input_graph_unchanged"] and d["ep0_sites_unchanged"]
        assert d["graphs_written"]==d["production_edges_written"]==0
        assert not d["training_executed"]
        old_rows={(r["source_node"],r["target_node"],r["edge_key"]):r for r in old["edges"]
                  if r["relation"]=="internal_call"}
        rows={(r["source_node"],r["target_node"],r["edge_key"]):r for r in d["reference_edges"]}
        assert len(rows)==len(d["reference_edges"]) and set(rows)==set(old_rows)
        files={r["file"]:r["source"]["sha256"] for r in d["files"]}
        raw={(r["file"],tuple(r["call_anchor"])):r for r in d["raw_calls"]}
        assert len(raw)==len(d["raw_calls"])
        pairs=defaultdict(list)
        ep0={(r["source_node"],r["target_node"]) for r in old["ep0_call_sites"] if r["projected"]}
        for site in d["call_sites"]:
            assert site["source_sha256"]==files[site["file"]]
            original=raw[(site["file"],tuple(site["call_anchor"]))]
            for k in ("status","kind","reason","target_node","target_anchor","expression"):
                assert original[k]==site[k]
            expect=(site["status"]=="resolved" and site["source_node"] is not None
                    and site["target_node"] is not None and site["source_node"]!=site["target_node"])
            assert site["projected"]==expect
            if expect:
                pairs[(site["source_node"],site["target_node"])].append(site)
            else:
                assert site["target_node"] is None or site["source_node"] is None or site["source_node"] == site["target_node"]
        projected={(r["source_node"],r["target_node"]):r for r in d["projected_call_sites"]}
        assert set(projected)==set(pairs)
        assert ep0<=set(projected)
        owner_pairs={(s["owner_node"],s["target_node"]) for group in pairs.values() for s in group}
        hcg={(s,t) for s,t,k in rows}
        old_owner_pairs={(r["owner_node"],r["target_node"]) for r in old["ep0_call_sites"] if r["projected"]}
        for ident,row in rows.items():
            previous=old_rows[ident]
            for k in ("file","source_sha256","source_anchor","target_anchor","target_file"):
                assert row[k]==previous[k]
            assert row["source_sha256"]==files[row["file"]]
            assert row["ep0b_category"]==previous["category"]
            assert row["ep0_covered"]==previous["covered"]==((ident[0],ident[1]) in old_owner_pairs)
            assert row["r5_covered"]==((ident[0],ident[1]) in owner_pairs)
            cs=row["expression_candidates"]
            assert [c["call_anchor"] for c in cs]==[c["anchor"] for c in previous["expression_candidates"]]
            for c in cs:
                source=raw[(row["file"],tuple(c["call_anchor"]))]
                for k in ("status","kind","reason","target_anchor","target_node"):
                    assert c[k]==source[k]
            supported = (row["source_anchor"] is not None and row["target_anchor"] is not None
                and row["source_anchor"][2] in ("function_definition","constructor_definition","modifier_definition")
                and row["target_anchor"][2] in ("function_definition","constructor_definition","modifier_definition")
                and row["target_file"] == row["file"])
            if not supported:
                expected="undetermined"
            elif any(c["status"]=="resolved" and c["target_anchor"]==row["target_anchor"] for c in cs):
                expected="internal_confirmed"
            elif not cs:
                expected="no_expression"
            elif all(c["status"] in ("address_builtin","external_member","cast_member","new_contract","builtin") for c in cs):
                expected="not_internal"
            elif any(c["target_anchor"] is not None for c in cs):
                expected="rebinding"
            else:
                expected="undetermined"
            assert row["reference_class"]==expected
        counts=Counter(r["reference_class"] for r in rows.values())
        s=d["summary"]
        assert dict(counts)==s["reference_classes"]
        assert len(rows)==s["internal_hcg_edges"]
        denominator=counts["internal_confirmed"]
        confirm=[r for r in rows.values() if r["reference_class"]=="internal_confirmed"]
        assert denominator==s["confirmed_denominator"]
        assert sum(r["r5_covered"] for r in confirm)==s["r5_covered"]
        assert sum(r["ep0_covered"] for r in confirm)==s["ep0_covered"]
        assert s["r5_coverage"]==s["r5_covered"]/denominator
        assert s["ep0_coverage"]==s["ep0_covered"]/denominator
        assert s["undetermined_to_confirmed"]==counts["undetermined"]/denominator
        assert s["coverage_gate_pass"]==(s["r5_coverage"]>=.8)
        assert s["unknown_gate_pass"]==(s["undetermined_to_confirmed"]<=.2)
        assert s["gate_pass"]==(s["coverage_gate_pass"] and s["unknown_gate_pass"])
        assert len(projected)==s["unique_call_site_edges"]
        assert len(ep0)==s["ep0_unique_edges"]
        assert len(set(projected)-ep0)==s["added_edges"]
        for pair,r in projected.items():
            assert r["kinds"]==sorted({site["kind"] for site in pairs[pair]})
            assert r["added_vs_ep0"]==(pair not in ep0)
            assert r["absent_from_hcg"]==((r["owner_node"],r["target_node"]) not in hcg)
            assert set(tuple(x) for x in r["call_anchors"])=={tuple(site["call_anchor"]) for site in pairs[pair]}
        assert sum(r["absent_from_hcg"] for r in projected.values())==s["absent_from_hcg_edges"]
        assert dict(Counter(k for r in projected.values() for k in r["kinds"]))==s["unique_edges_by_kind"]
        assert summary["task_summaries"][task]==s
        assert dict(Counter(r["status"] for r in raw.values())) == s["call_statuses"]
        assert dict(Counter(r["kind"] for r in raw.values() if r["kind"])) == s["call_kinds"]
        observed = Counter()
        for row in rows.values():
            if row["reference_class"] == "no_expression":
                observed["no_expression"] += 1
            elif row["reference_class"] == "not_internal":
                statuses = {c["status"] for c in row["expression_candidates"]}
                observed["address_builtin" if statuses == {"address_builtin"} else "external"] += 1
        observed["total"] = sum(observed.values())
        assert dict(observed) == s["rough_observed"]
        assert summary["coarse_count_provenance"]["corrected_reference"][task] == dict(observed)
        task_receipts[task]=dict(edges=len(rows),sites=len(projected),gate_pass=s["gate_pass"],
                                delta=delta_receipt)

    test_total=0
    for name,r in summary["tests"].items():
        receipt=read(checked(r["receipt"]))
        assert receipt["exit_code"]==0
        text=checked(receipt["log"]).read_text()
        assert re.findall(r"(?m)^(\d+) passed",text)==[str(r["passed"])]
        test_total+=r["passed"]
    assert test_total==summary["test_total"]
    assert summary["gate_pass"] == all(r["gate_pass"] for r in task_receipts.values())
    assert summary["stop_after"] == "EP0d" and summary["no_automatic_ep1"]
    assert not summary["training_executed"]
    documents=[]
    for name,original in before["documents"].items():
        raw=(ROOT/name).read_bytes()
        assert hashlib.sha256(raw[:original["bytes"]]).hexdigest()==original["sha256"]
        documents.append(check(ROOT/name,original["bytes"],expect_cjk=True))
    receipt=read(OUT/"execution/doc_check.json")
    assert receipt["exit_code"]==0
    checked(receipt["log"])
    changed=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    assert all(n in before["documents"] or n.startswith("scripts/edge_sem/") for n in changed)
    subprocess.run(["git","-c","core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
                    "diff","--check"],cwd=str(ROOT),check=True)
    assert not torch.cuda.is_initialized()
    write(OUT/"verification.json",dict(passed=True, scope="EP0d implementation, EP0c differences and unchanged progression gates",
        archived_8h_load_passed=True, all_frozen_hashes_unchanged=True,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        input_reference_count=len(prior["input_refs"]),prior_artifact_count=len(before["prior_artifacts"]),
        task_checks=task_receipts,test_total=test_total,documents=documents,
        summary=ref(OUT/"summary.json"),report=ref(ROOT/"scripts/edge_sem/RECON.md"),
        cuda_initialized=False,training_executed=False,call_gate_pass=summary["gate_pass"],
        historical_source_snapshots_verified=True,
        prior_edge_source_count=len(before["prior_edge_sources"]),
        changed_sources=[dict(before=r["original"],after=ref(r["original"]["path"]))
                         for r in before["authorized_source_changes"]],
        approval=ref(OUT/"adjustment_approval.json")))
    print("EP0d verified:",test_total,"tests; call gate",summary["gate_pass"],flush=True)


if __name__=="__main__":
    verify()
