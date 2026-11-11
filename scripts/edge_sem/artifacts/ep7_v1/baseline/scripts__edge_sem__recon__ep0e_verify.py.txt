"""EP0e integrity and recount verifier; coverage failure remains a failure.

HCG recount logic adapted from scripts/edge_sem/recon/ep0d_verify.py.
Frozen source SHA256: ac473d9ceb050b12a7d759aa8529d7d6e98ebdd4077ced9e737f406b631b1241
Only this new EdgeSem verifier is changed; old artifacts stay immutable.
"""
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from .common import ROOT, ref, read, checked, write
from .ep0e_common import OUT, TASKS, EP0B, EP0D
from scripts.edge_sem.call_resolve import FROZEN_AST_SHA256

def verify_ep0d_delta(task, current, summary):
    previous = read(checked(current["ep0d_ref"]))
    assert checked(current["ep0d_ref"]) == EP0D/("calls_"+task+".json")
    comparison = read(OUT/"ep0d_comparison.json")[task]
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
                assert row["reason"] == "typed_receiver" and row["kind"] == "library"
            elif row["status"] in ("call_option", "builtin"):
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



def verify_using(task, current, summary):
    rows = current["using_candidates"]
    raw = {(r["file"],r["source_sha256"],tuple(r["call_anchor"])):r for r in current["raw_calls"]}
    seen = set()
    candidates, matched, outside, ambiguous = [], [], [], []
    for row in rows:
        ident = (row["file"],row["source_sha256"],tuple(row["call_anchor"]))
        assert ident not in seen
        seen.add(ident)
        original = raw[ident]
        for name in ("status","kind","target_anchor","reason","expression"):
            assert row[name] == original[name]
        structure = row["structural"]
        assert structure["extension_member"]
        targets = {tuple(r["function_anchor"]) for r in structure["declarations"]}
        expected = list(next(iter(targets))) if len(targets)==1 else None
        assert structure["reason"] == ("unique_candidate" if len(targets)==1 else
                                      ("ambiguous_candidates" if targets else "no_candidate"))
        assert row["expected_target"] == expected
        assert row["candidate"] == (expected is not None)
        correct = expected is not None and row["status"]=="resolved" and row["target_anchor"]==expected
        assert row["matched"] == correct
        extraneous = (row["status"]=="resolved" and row["kind"]=="library"
                      and (expected is None or row["target_anchor"]!=expected))
        assert row["outside_candidate"] == extraneous
        if row["candidate"]:
            candidates.append(row)
            if correct:
                matched.append(row)
                assert row["miss_reason"] is None
            else:
                assert row["miss_reason"] is not None
        if extraneous:
            outside.append(row)
        if len(targets)>1:
            ambiguous.append(row)
    s = current["using_summary"]
    assert s["candidate_calls"] == len(candidates)
    assert s["matched_calls"] == len(matched)
    ratio = len(matched)/len(candidates) if candidates else None
    assert s["recall"] == ratio
    assert s["outside_candidate_calls"] == len(outside)
    assert s["ambiguous_structural_candidates"] == len(ambiguous)
    assert s["misses_by_reason"] == dict(Counter(r["miss_reason"] for r in candidates if not r["matched"]))
    assert set(s["per_shape"]) == {"identifier","mapping_subscript","array_subscript",
                                   "parenthesized","chained_call","struct_member","other"}
    for shape, group in s["per_shape"].items():
        part = [r for r in candidates if r["receiver_shape"]==shape]
        n = sum(r["matched"] for r in part)
        assert group == dict(candidates=len(part),matched=n,recall=n/len(part) if part else None)
    assert sum(r["candidates"] for r in s["per_shape"].values()) == len(candidates)
    files = current["using_files"]
    sources = {r["file"]:r["source"]["sha256"] for r in current["files"]}
    assert len(files)==len(sources) and {r["file"] for r in files}==set(sources)
    equality, old_count = [], 0
    previous = read(checked(current["ep0d_ref"]))
    prior = {(r["file"],r["source_sha256"],tuple(r["call_anchor"])):r for r in previous["raw_calls"]}
    for file_row in files:
        name, sha = file_row["file"],file_row["source_sha256"]
        assert sha == sources[name]
        originals = {ident:r for ident,r in prior.items() if ident[0]==name}
        assert file_row["prior_call_count"] == len(originals)
        assert file_row["resolved_unchanged"] == sum(r["status"]=="resolved" for r in originals.values())
        old_count += file_row["resolved_unchanged"]
        local = file_row["using_equivalence"]
        assert len({tuple(r["call_anchor"]) for r in local})==len(local)
        for row in local:
            ident = (name,sha,tuple(row["call_anchor"]))
            assert ident in originals and ident in seen
            assert row["receiver_type"] in ("identifier","array_access")
            assert row["equal"] == (row["frozen_target"]==row["adapter_target"])
            assert row["binding_rules_equal"] == (row["frozen_target"]==row["rule_only_target"])
            assert row["unexpected_mismatch"] == (not row["equal"] and not row["approved_wildcard_exception"])
            if row["approved_wildcard_exception"]:
                candidate = next(r for r in rows if (r["file"],r["source_sha256"],tuple(r["call_anchor"]))==ident)
                assert any(d["wildcard"] for d in candidate["structural"]["declarations"])
            else:
                assert row["binding_rules_equal"]
        equality.extend(local)
    assert s["using_equivalence_count"] == len(equality)
    assert s["using_equivalent"] == sum(r["equal"] for r in equality)
    assert s["wildcard_exceptions"] == sum(r["approved_wildcard_exception"] for r in equality)
    unexpected = sum(r["unexpected_mismatch"] for r in equality)
    assert s["unexpected_equivalence_mismatches"] == unexpected
    assert s["prior_resolved_unchanged"] == old_count
    assert s["recall_gate_pass"] == bool(ratio is not None and ratio>=.9)
    assert s["no_outside_gate_pass"] == (not outside)
    assert s["gate_pass"] == bool(s["recall_gate_pass"] and not outside and not unexpected and not ambiguous)
    assert s == summary["using_summaries"][task]
    review = read(OUT/"gap_review.json")[task]
    assert review["using_misses"] == [r for r in candidates if not r["matched"]]
    assert review["outside_candidates"] == outside
    evidence = read(OUT/"residual_evidence.json")[task]
    checked(evidence["input"])
    assert [r["identity"] for r in evidence["misses"]] == review["using_misses"]
    assert evidence["residual_option_shapes"] == review["residual_call_options"]
    # Counts are independently re-derived here; this is not another resolver run.
    old_pairs = {(r["source_node"],r["target_node"]) for r in previous["projected_call_sites"]}
    sites = {(r["file"],r["source_sha256"],tuple(r["call_anchor"])):r for r in current["call_sites"]}
    counts, pair_counts = Counter(), Counter()
    new_raw = [r for key,r in raw.items() if r["status"]=="resolved" and prior[key]["status"]!="resolved"]
    for row in new_raw:
        site = sites.get((row["file"],row["source_sha256"],tuple(row["call_anchor"])))
        if site is None:
            counts["absent_from_statement_calls"] += 1
        elif not site["projected"]:
            counts["unprojected"] += 1
        elif (site["source_node"],site["target_node"]) in old_pairs:
            counts["already_existing_pair"] += 1
        else:
            counts["new_pair_call"] += 1
            pair_counts[(site["source_node"],site["target_node"])] += 1
    assert summary["projection_delta"][task] == dict(newly_resolved_calls=len(new_raw),
        disposition=dict(counts),unique_new_pairs=len(pair_counts),
        coalesced_extra_calls=sum(n-1 for n in pair_counts.values()))
    return dict(candidates=len(candidates),matched=len(matched),recall=ratio,outside=len(outside),
                equivalence_count=len(equality),gate_pass=s["gate_pass"])


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
    approval = read(OUT/"wildcard_approval.json")
    assert approval["question_id"] == "call_982fd66328c84073a4f93e960177fb2d"
    assert approval["frozen_code_modified"] is False
    audit = read(OUT/"audit_plan.json")
    assert audit["library_recall_minimum"] == .9 and audit["outside_candidate_maximum"] == 0
    assert audit["hcg_projection_minimum"] == .8 and audit["hcg_unknown_to_confirmed_maximum"] == .2
    assert audit["graphs_written"] == 0 and not audit["training_executed"]
    for source_ref in audit["sources"]:
        checked(source_ref)
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
        delta_receipt=verify_ep0d_delta(task,d,summary)
        using_receipt=verify_using(task,d,summary)
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
                                delta=delta_receipt,using=using_receipt)

    test_total=0
    for name,r in summary["tests"].items():
        receipt=read(checked(r["receipt"]))
        assert receipt["exit_code"]==0
        text=checked(receipt["log"]).read_text()
        assert re.findall(r"(?m)^(\d+) passed",text)==[str(r["passed"])]
        test_total+=r["passed"]
    assert test_total==summary["test_total"]
    assert summary["hcg_gate_pass"] == all(r["gate_pass"] for r in task_receipts.values())
    assert summary["library_gate_pass"] == all(r["using"]["gate_pass"] for r in task_receipts.values())
    assert summary["gate_pass"] == (summary["hcg_gate_pass"] and summary["library_gate_pass"])
    sets = []
    for task in TASKS:
        rows = read(OUT/("calls_"+task+".json"))["using_candidates"]
        sets.append({(r["file"],r["source_sha256"],tuple(r["call_anchor"]),tuple(r["expected_target"]))
                     for r in rows if r["candidate"]})
    overlap = summary["candidate_identity_overlap"]
    assert overlap["equal"] == (sets[0]==sets[1])
    assert overlap["common_exact_identities"] == len(sets[0] & sets[1])
    assert summary["stop_after"] == "EP0e" and summary["no_automatic_ep1"]
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
    write(OUT/"verification.json",dict(passed=True, scope="EP0e implementation integrity and independently recounted gates; passed is integrity, not progression",
        archived_8h_load_passed=True, all_frozen_hashes_unchanged=True,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        input_reference_count=len(prior["input_refs"]),prior_artifact_count=len(before["prior_artifacts"]),
        task_checks=task_receipts,test_total=test_total,documents=documents,
        summary=ref(OUT/"summary.json"),report=ref(ROOT/"scripts/edge_sem/RECON.md"),
        cuda_initialized=False,training_executed=False,call_gate_pass=summary["gate_pass"],
        hcg_gate_pass=summary["hcg_gate_pass"],library_gate_pass=summary["library_gate_pass"],
        historical_source_snapshots_verified=True,
        prior_edge_source_count=len(before["prior_edge_sources"]),
        changed_sources=[dict(before=r["original"],after=ref(r["original"]["path"]))
                         for r in before["authorized_source_changes"]],
        approval=ref(OUT/"wildcard_approval.json")))
    print("EP0e integrity verified:",test_total,"tests; call gate",summary["gate_pass"],flush=True)


if __name__=="__main__":
    verify()
