"""Independent EP0b completeness checks without rerunning analysis or training."""
import hashlib
import re
import subprocess
from collections import Counter
from .common import ROOT, ref, read, checked, write
from .ep0b_common import OUT, EP0, TASKS
from scripts.edge_sem.guard_source import FROZEN_SOURCE_SHA256


def refs(value):
    if isinstance(value,dict):
        if isinstance(value.get("path"),str) and isinstance(value.get("sha256"),str):
            yield value
        for child in value.values():
            for row in refs(child):
                yield row
    elif isinstance(value,list):
        for child in value:
            for row in refs(child):
                yield row


def verify():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.doc_check import check
    import torch
    before=read(OUT/"before.json")
    summary=read(OUT/"summary.json")
    assert _code_refs()==before["dfg_code_refs"]
    for row in before["frozen_code"]+before["prior_artifacts"]:
        checked(row)
    checked(before["prompt"])
    checked(before["plan"])
    checked(before["seal"])
    checked(before["input_inventory"])
    load(before["plan"]["path"])
    assert ref(ROOT/"scripts/node_sem/facts_guards.py")["sha256"]==FROZEN_SOURCE_SHA256
    historical=read(EP0/"inputs.json")
    inputs={}
    # The old r3 PROMPTS snapshot is not a computational input; current r4 is
    # separately bound above. Check every immutable task input and receipt ref.
    for row in refs(historical["tasks"]):
        identity=(row["path"],row["sha256"])
        if identity not in inputs:
            inputs[identity]=ref(checked(row))
    for name in ("plan","seal","store","store_seal","source_preparation","feature_root","naming"):
        checked(historical[name])

    total_functions=0
    for task in TASKS:
        guard=read(OUT/("guards_"+task+".json"))
        assert guard["all_sequences_equal"] and guard["input_graph_unchanged"]
        assert guard["graphs_written"]==guard["production_edges_written"]==0
        original=read(EP0/(task+".json"))
        assert guard["unique_nonmodifier"]==original["prospective_relations"]["GUARDS"]["unique_forward"]
        functions=sum(len(f["functions"])for f in guard["files"])
        total_functions+=functions
        assert functions==guard["counts"]["functions_checked"]
        public_records=sum(len(fn["records"])for f in guard["files"]for fn in f["functions"])
        assert public_records==guard["counts"]["modifier_records_per_function"]
        for row in guard["files"]:
            for fn in row["functions"]:
                assert fn["sequence_equal"]
            pairs=[(p["source"],p["target"])for p in row["prospective_pairs"]]
            assert len(pairs)==len(set(pairs))==row["unique_combined"]
            assert sum(row["incoming_distribution"].values())==row["statement_count"]
            assert sum(int(k)*v for k,v in row["incoming_distribution"].items())==len(pairs)
        assert sum(r["unique_combined"]for r in guard["files"])==guard["unique_combined"]
        assert summary["guards"][task]["unique_combined"]==guard["unique_combined"]
    assert total_functions==summary["guard_equivalence"]["function_instances"]==12285

    classifications=read(EP0/"call_classification.json")
    for task in TASKS[:2]:
        calls=read(OUT/("calls_refined_"+task+".json"))
        old=read(OUT/("calls_"+task+".json"))
        assert calls["input_graph_unchanged"] and calls["production_edges_written"]==0
        assert calls["ep0_call_sites"]==old["ep0_call_sites"]
        assert len(calls["edges"])==len(old["edges"])
        for a,b in zip(old["edges"],calls["edges"]):
            assert all(a[k]==b[k]for k in ("file","relation","source_node","target_node","edge_key","covered"))
            if a["category"]!=b["category"]:
                assert a["category"]=="no_call_expression" and b["category"]=="other"
        sites=calls["ep0_call_sites"]
        counted=Counter(r["category"]for r in sites)
        for k,v in counted.items():
            assert classifications[task]["total"][k]==v
        unique={(r["source_node"],r["target_node"])for r in sites if r["projected"]}
        assert len(unique)==classifications[task]["unique_projected_edges"]
        for relation in ("internal_call","external_call"):
            selected=[e for e in calls["edges"]if e["relation"]==relation]
            c=Counter(e["category"]for e in selected)
            n=sum(e["covered"]for e in selected)
            r=calls["summary"][relation]
            assert dict(c)==r["categories"] and len(selected)==r["edges"] and n==r["covered"]
            denominator=len(selected)-c["no_call_expression"]
            assert denominator==r["adjusted_denominator"]
            assert r["adjusted_coverage"]==n/denominator
            for e in selected:
                if e["covered"]:
                    assert any(x["owner_node"]==e["source_node"] and x["target_node"]==e["target_node"] and x["projected"]for x in e["call_sites"])
        assert not calls["summary"]["internal_call"]["gate_80_percent_pass"]
        attrs=read(OUT/("attributes_"+task+".json"))
        assert attrs["attribute_vectors_written"]==attrs["production_edges_written"]==0
        assert attrs["input_graph_unchanged"]
        recomputed={}
        definitions={}
        def add(name,value):
            recomputed.setdefault(name,Counter())[value]+=1
        for edge in attrs["data_edges"]:
            for ev in edge["evidence"]:
                add(edge["relation"]+"_value_shape",ev["resolution"]["status"])
                if "def_kind" in ev:
                    add("def_kind_edge_evidence",ev["def_kind"])
                    definitions[(edge["file"],edge["source_node"],ev["symbol_identity"])]=ev["def_kind"]
                if "write_access" in ev:
                    add("write_access_event",ev["write_access"])
                    add("write_op_event",ev["write_op"])
        recomputed["def_kind_unique_node_variable"]=Counter(definitions.values())
        assert {k:dict(v)for k,v in recomputed.items()}==attrs["counts"]
    for row in refs(summary["evidence_refs"]):
        checked(row)
    revision=read(checked(summary["revisions"]))
    assert revision["current_source_sha256"]==ref(ROOT/"scripts/edge_sem/recon/ep0b_calls.py")["sha256"]
    assert revision["previous_source_sha256"]==ref(OUT/"revisions/call_diagnostic_v1.py")["sha256"]

    documents=[]
    for name,original in before["documents"].items():
        raw=(ROOT/name).read_bytes()
        assert hashlib.sha256(raw[:original["bytes"]]).hexdigest()==original["sha256"],name
        documents.append(check(ROOT/name,original["bytes"],expect_cjk=True))
    doc_receipt=read(OUT/"execution/doc_check.json")
    assert doc_receipt["exit_code"]==0
    checked(doc_receipt["log"])
    test_total=0
    for name,row in summary["tests"].items():
        receipt=read(checked(row["receipt"]))
        assert receipt["exit_code"]==0
        log=checked(receipt["log"]).read_text()
        counts=re.findall(r"(?m)^(\d+) passed",log)
        assert counts==[str(row["passed"])]
        test_total+=row["passed"]
    assert test_total==summary["test_total"]==4040

    # Earlier EdgeSem analysis source and recon.json remain byte-identical.
    prior_names=subprocess.check_output(["git","ls-tree","-r","--name-only",before["head"],
        "scripts/edge_sem/recon","scripts/edge_sem/recon.json"],cwd=str(ROOT),text=True).splitlines()
    for name in prior_names:
        blob=subprocess.check_output(["git","show",before["head"]+":"+name],cwd=str(ROOT))
        assert (ROOT/name).read_bytes()==blob,name
    changed=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    assert all(n in before["documents"] or n.startswith("scripts/edge_sem/")for n in changed)
    subprocess.run(["git","-c","core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
                    "diff","--check"],cwd=str(ROOT),check=True)
    assert not torch.cuda.is_initialized()
    implementations=[ROOT/"scripts/edge_sem/guard_source.py"]
    implementations+=sorted((ROOT/"scripts/edge_sem/recon").glob("ep0b_*.py"))
    implementations+=sorted((ROOT/"scripts/edge_sem/tests").glob("test_ep0b_*.py"))
    result=dict(passed=True,scope="EP0b acceptance; CALL_SITE gate failed, no next stage",
        archived_8h_load_passed=True,frozen_code_count=len(before["frozen_code"]),
        dfg_code_refs_count=len(before["dfg_code_refs"]),prior_artifact_count=len(before["prior_artifacts"]),
        all_frozen_hashes_unchanged=True,input_reference_count=len(inputs),
        input_refs=list(inputs.values()),ep0_sources_unchanged=True,
        functions_compared=total_functions,call_gate_pass=False,test_total=test_total,
        documents=documents,doc_check_receipt=ref(OUT/"execution/doc_check.json"),
        implementations=[ref(p)for p in implementations],summary=ref(OUT/"summary.json"),
        report=ref(ROOT/"scripts/edge_sem/RECON.md"),cuda_initialized=False,training_executed=False,
        planned_commit_prefix="EP0b")
    write(OUT/"verification.json",result)
    print("EP0b verified: {} tests, {} functions; CALL_SITE gate remains failed".format(test_total,total_functions),flush=True)


if __name__=="__main__":
    verify()
