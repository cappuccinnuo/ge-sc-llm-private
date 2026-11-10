"""Independently recompute EP0c counts and check immutable historical inputs."""
import hashlib
import re
import subprocess
from collections import Counter, defaultdict
from .common import ROOT, ref, read, checked, write
from .ep0c_common import OUT, TASKS, EP0B
from .ep0b_verify import refs
from scripts.edge_sem.call_resolve import FROZEN_AST_SHA256


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
                assert site["target_node"] is None or site["source_node"] is None
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
            if any(c["status"]=="resolved" and c["target_anchor"]==row["target_anchor"] for c in cs):
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
        task_receipts[task]=dict(edges=len(rows),sites=len(projected),gate_pass=s["gate_pass"])

    test_total=0
    for name,r in summary["tests"].items():
        receipt=read(checked(r["receipt"]))
        assert receipt["exit_code"]==0
        text=checked(receipt["log"]).read_text()
        assert re.findall(r"(?m)^(\d+) passed",text)==[str(r["passed"])]
        test_total+=r["passed"]
    assert test_total==summary["test_total"]
    assert not summary["gate_pass"] and summary["stop_after"]=="EP0c"
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
    write(OUT/"verification.json",dict(passed=True, scope="EP0c implementation/evidence; progression gate failed",
        archived_8h_load_passed=True, all_frozen_hashes_unchanged=True,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        input_reference_count=len(prior["input_refs"]),prior_artifact_count=len(before["prior_artifacts"]),
        task_checks=task_receipts,test_total=test_total,documents=documents,
        summary=ref(OUT/"summary.json"),report=ref(ROOT/"scripts/edge_sem/RECON.md"),
        cuda_initialized=False,training_executed=False,call_gate_pass=False))
    print("EP0c verified:",test_total,"tests; progression gate remains failed",flush=True)


if __name__=="__main__":
    verify()
