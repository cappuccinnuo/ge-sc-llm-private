"""Independent EP3 provenance, evidence-sequence and immutable archive checks."""
import hashlib
import json
import re
import subprocess
from collections import Counter,defaultdict
import torch
from .common import ROOT,read,checked,ref,write,key
from .ep3_common import OUT,TASKS,contexts,file_views
from .ep3_archive import load_ep2_edges,EP2
from scripts.edge_sem.build_f4 import load_edges,add_edges
from scripts.edge_sem.guard_source import modifier_guard_sources,public_record
from scripts.node_sem.facts import STATEMENTS
from scripts.node_sem.facts_guards import GuardAnalyzer
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def ordered(rows):
    return [json.dumps(r,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        for r in sorted(rows,key=lambda x:(x["relation"],x["src"],x["dst"]))]


def verify():
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.node_sem.doc_check import check
    before=read(OUT/"before.json");summary=read(OUT/"summary.json")
    assert _code_refs()==before["dfg_code_refs"]
    for r in before["frozen_code"]+before["prior_edge_sources"]+before["prior_artifacts"]:checked(r)
    for name in ("plan","seal","prompt","historical_verification"):checked(before[name])
    for r in before["authorized_source_changes"]:
        checked(r["snapshot"]);assert r["original"]["sha256"]==r["snapshot"]["sha256"]
    load(before["plan"]["path"])
    original=read(ROOT/"scripts/edge_sem/artifacts/ep0b_v1/verification.json")
    for r in original["input_refs"]:checked(r)
    for r in summary["source_refs"]+summary["evidence_refs"]:checked(r)
    assert summary["gate_pass"] and summary["historical_ep0e_gate_pass"] is False
    assert read(ROOT/"scripts/edge_sem/artifacts/ep0e_v1/summary.json")["gate_pass"] is False
    assert not summary["gpu_executed"] and not summary["training_executed"]
    assert summary["optimizer_steps"]==summary["graphs_written"]==0 and not summary["ep4_started"]
    details={}
    for task in TASKS:
        context=contexts(task);graph=context["graphs"]["F3"];fp=graph_fingerprint(graph)
        manifest=read(OUT/task/"manifest.json");rows=load_edges(OUT/task/"manifest.json")
        audit=read(checked(manifest["audit"]));prior=load_ep2_edges(EP2/task/"manifest.json")
        assert manifest["original_fingerprint"]==fp and manifest["source_view"]=="original"
        assert ordered([r for r in rows if r["relation"]!="GUARDS"])==ordered(prior)
        assert len({(r["relation"],r["src"],r["dst"]) for r in rows})==len(rows)
        assert manifest["counts_by_relation"]==dict(Counter(r["relation"] for r in rows))
        by_file=defaultdict(list)
        for row in rows:by_file[row["file"]].append(row)
        files={r["file"]:r for r in audit["files"]}
        assert set(files)==set(context["sources"]) and len(files)==len(audit["files"])
        records=Counter();mapped=Counter();target_count=0;unknown=0;expected_pairs=set()
        node_incoming=Counter();multi=Counter();constructor_descriptions=0
        for file,source,sub,sem,raw,inverse in file_views(context):
            a=files[file]["guards"];analyzer=GuardAnalyzer(sem)
            for e in by_file[file]:
                assert e["source_sha256"]==context["sources"][file]["sha256"]
                assert inverse[tuple(e["src_anchor"])]==e["src"] and inverse[tuple(e["dst_anchor"])]==e["dst"]
                assert graph.nodes[e["src"]]["source_file"]==file==graph.nodes[e["dst"]]["source_file"]
            actual={(e["src"],e["dst"]):e for e in by_file[file] if e["relation"]=="GUARDS"}
            target_audit={t["node"]:t for t in a["targets"]}
            assert set(target_audit)=={nid for nid,node in raw.items() if node.type in STATEMENTS}
            wanted=defaultdict(list);source_anchors={};target_anchors={};sources={}
            local_records=Counter();local_mapped=Counter();missing_count=0;skipped=0
            for nid,node in raw.items():
                if node.type not in STATEMENTS:continue
                result=analyzer.for_node(node);owner=sem.owner(node);target_count+=1
                unknown+=int(result["guard_status"]=="unknown")
                t=target_audit[nid]
                assert t["guard_status"]==result["guard_status"] and t["unresolved"]==result["unresolved"]
                assert t["records"]==len(result["guards"]) and tuple(t["anchor"])==key(node)
                own=key(owner)
                if own not in sources:sources[own]=[] if owner is None else modifier_guard_sources(analyzer,owner)
                ms=sources[own];gs=[g for g in result["guards"] if g["kind"]=="modifier"]
                assert [public_record(g) for g in gs]==[g["record"] for g in ms]
                assert not gs or result["guards"][-len(gs):]==gs
                mi=0
                for g in result["guards"]:
                    kind=g["kind"];local_records[kind]+=1
                    evidence=public_record(g).copy()
                    evidence["source"]="modifier" if kind=="modifier" else "lexical"
                    if kind=="modifier":
                        srcnode=ms[mi]["inner_anchor"];evidence["invocation_anchor"]=list(key(ms[mi]["invocation"]));mi+=1
                    else:srcnode=g["_anchor"]
                    src=inverse.get(key(srcnode))
                    if src is None or srcnode.type not in STATEMENTS:
                        missing_count+=1;assert kind=="modifier"
                        continue
                    local_mapped[kind]+=1
                    if src==nid:skipped+=1;continue
                    wanted[(src,nid)].append(evidence)
                    source_anchors[(src,nid)]=list(key(srcnode))
                    target_anchors[(src,nid)]=list(key(node))
            assert missing_count==len(a["missing"]) and skipped==a["counts"].get("self_skipped",0)
            assert dict(local_records)==a["kind_records"] and dict(local_mapped)==a["kind_mapped"]
            assert set(actual)==set(wanted)
            for ident,evidence in wanted.items():
                row=actual[ident]
                assert row["rule"]=="E1-GUARD-1" and row["evidence"]==evidence
                assert row["kind"]==sorted(set(e["kind"] for e in evidence))
                assert row["src_anchor"]==source_anchors[ident] and row["dst_anchor"]==target_anchors[ident]
                expected_pairs.add(ident);node_incoming[ident[1]]+=1
                if len(evidence)>1:multi["+".join(row["kind"])]+=1
            records.update(local_records);mapped.update(local_mapped)
            # Independently reproduce the reported excluded constructor bindings.
            nodes={key(n):n for n in sem.nodes}
            for item in files[file]["unresolved_modifier_declarations"]:
                inv=nodes[tuple(item["invocation_anchor"])]
                parts=[n for n in inv.named_children if "comment" not in n.type]
                resolved=sem.resolve_identifier(parts[0]);decl=resolved["declaration"]
                assert item["declaration_types"]==([] if decl is None else [decl.type])
                assert item["declaration_anchors"]==([] if decl is None else [list(key(decl))])
                constructor_descriptions+=int(item["function_anchor"][2]=="constructor_definition")
        guard=audit["guards"]
        assert sum(records.values())==guard["counts"]["records"]
        assert dict(records)==guard["kind_records"] and dict(mapped)==guard["kind_mapped"]
        assert target_count==guard["counts"]["targets"] and unknown==guard["counts"]["unknown_targets"]
        assert dict(multi)==guard["multi_evidence_kinds"]
        assert len(expected_pairs)==manifest["counts_by_relation"]["GUARDS"]
        assert len(guard["incoming_by_node"])==graph.number_of_nodes()
        for n,row in zip(graph,guard["incoming_by_node"]):
            assert row["node"]==n and row["guards"]==node_incoming[n]
        assert all(r["equal"] for r in guard["per_file_reproduction"])
        assert guard["reproduction_pass"] and guard["nonmodifier_mapping_pass"] and audit["hard_conditions_pass"]
        enriched=add_edges(graph,rows);assert graph_fingerprint(graph)==fp
        new=[(s,t,k) for s,t,k,d in enriched.edges(keys=True,data=True)
             if d.get("edge_type") in ("MOD_APPLY","CALL_SITE","GUARDS")]
        assert len(new)==len(rows)
        enriched.remove_edges_from(new);assert graph_fingerprint(enriched)==fp
        for r in context["provenance"]["graphs"].values():checked(r)
        probe=summary["tasks"][task]["probe"]
        assert probe["edge_rows"]==len(rows) and probe["optimizer_steps"]==0 and not probe["cuda_initialized"]
        expected_canon=Counter()
        for e in rows:
            c=(graph.nodes[e["src"]]["node_type"],e["relation"],graph.nodes[e["dst"]]["node_type"])
            expected_canon[c]+=1;expected_canon[(c[2],"REV_"+c[1],c[0])]+=1
        reported={tuple(r["canonical"]):r["edges"] for r in probe["canonical_counts"]}
        assert all(reported[c]==n for c,n in expected_canon.items())
        assert probe["new_canonical_rows"]==len(expected_canon)
        assert probe["added_since_ep2"]==[dict(canonical=list(c),edges=n) for c,n in sorted(expected_canon.items())
                                            if c[1] in ("GUARDS","REV_GUARDS")]
        for flag in ("empty_matches_typed_bitwise","forward_backward_finite","common_parameters_equal",
                     "new_rows_match_relation_seed","repeated_initialization_equal","graph_unchanged","source_file_unchanged"):
            assert probe[flag]
        details[task]=dict(files=len(files),edge_count=len(rows),guard_edges=len(expected_pairs),
            guard_records=sum(records.values()),guard_target_count=target_count,guard_unknown_targets=unknown,
            ep2_rows_equal=True,all_guard_evidence_exact=True,original_graph_preserved=True,
            constructor_descriptions=constructor_descriptions)
    total=0
    for row in summary["tests"].values():
        receipt=read(checked(row["receipt"]));assert receipt["exit_code"]==0
        assert re.findall(r"(?m)^(\d+) passed",checked(receipt["log"]).read_text())==[str(row["passed"])]
        total+=row["passed"]
    assert total==summary["test_total"]
    docs=[]
    for name,r in before["documents"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()[:r["bytes"]]).hexdigest()==r["sha256"]
        docs.append(check(ROOT/name,r["bytes"],expect_cjk=True))
    docs.append(check(ROOT/"scripts/edge_sem/EP3_REPORT.md",expect_cjk=True))
    receipt=read(OUT/"execution/doc_check.json");assert receipt["exit_code"]==0;checked(receipt["log"])
    changed=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    assert all(n in before["documents"] or n.startswith("scripts/edge_sem/") for n in changed)
    subprocess.run(["git","diff","--check"],cwd=str(ROOT),check=True)
    assert not torch.cuda.is_initialized()
    write(OUT/"verification.json",dict(passed=True,gate_pass=True,
        frozen_code_count=len(before["frozen_code"]),dfg_code_refs_count=len(before["dfg_code_refs"]),
        prior_edge_source_count=len(before["prior_edge_sources"]),prior_artifact_count=len(before["prior_artifacts"]),
        input_reference_count=len(original["input_refs"]),historical_8h_load=True,
        tasks=details,test_total=total,documents=docs,report=ref(ROOT/"scripts/edge_sem/EP3_REPORT.md"),
        summary=ref(OUT/"summary.json"),gpu_executed=False,training_executed=False,ep4_not_started=True,
        historical_ep0e_gate_pass=False))
    print("EP3 verified:",total,"tests; all GUARDS evidence and original graph identities exact",flush=True)


if __name__=="__main__":verify()
