"""Read-only EP4 integrity and semantic rechecks, independent of saved stats."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
import numpy as np
from .common import ROOT, ref, read, checked, write
from .ep4_common import OUT, TASKS
from .ep4_rebuild import F4, load_ep3_manifest, compare_edge_files
from scripts.edge_sem.build_f4 import load_edges, add_edges
from scripts.edge_sem.attr_batch import load_attributes, numeric_digest
from scripts.edge_sem.attrs import (edge_rows,endpoint_test,select_groups,EDGE_FEATURE_NAMES,
                                   GUARD_OPERANDS,GUARD_KINDS)
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint


def verify():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.facts_io import load_context
    from scripts.node_sem.doc_check import check
    before=read(OUT/"before.json")
    for r in before["frozen_code"]+before["prior_artifacts"]+before["prior_edge_sources"]:
        checked(r)
    for name in ("prompt","plan","seal","historical_verification"):checked(before[name])
    for r in before["authorized_source_changes"]:
        assert r["original"]["sha256"]==r["snapshot"]["sha256"]
        checked(r["snapshot"])
    assert _code_refs()==before["dfg_code_refs"]
    load(before["plan"]["path"])
    results={};endpoints={}
    attr_root=Path(read(OUT/"resume2.json")["out_dir"])
    for task in TASKS:
        context=load_context(task);graph=context["graphs"]["F3"]
        fp=graph_fingerprint(graph)
        f4=read(F4/task/"manifest.json");edges=load_edges(F4/task/"manifest.json")
        old=load_ep3_manifest(task)
        compare_edge_files(checked(old["edges"]),checked(f4["edges"]))
        attrs=load_attributes(attr_root/task/"manifest.json",graph,edges)
        rows=edge_rows(graph,edges)
        array=np.stack([attrs[r["key"]] for r in rows])
        assert graph_fingerprint(graph)==fp
        augmented=add_edges(graph,edges)
        assert list(augmented)==list(graph)
        assert augmented.number_of_edges()==graph.number_of_edges()+len(edges)
        added=[(s,t,k) for s,t,k,d in augmented.edges(keys=True,data=True)
               if d["edge_type"] in ("MOD_APPLY","CALL_SITE","GUARDS")]
        assert len(added)==len(edges)
        augmented.remove_edges_from(added)
        assert graph_fingerprint(augmented)==fp
        del augmented
        # Recalculate endpoint decisions solely from the saved binary matrix.
        endpoints[task]=endpoint_test(attrs,edges,graph)
        assert json.loads(json.dumps(endpoints[task]))==read(attr_root/task/"endpoint_test.json")
        audit=read(checked(f4["audit"]))
        unknown={t["node"] for f in audit["files"] for t in f["guards"]["targets"] if t["guard_status"]=="unknown"}
        expected_unknown=Counter()
        for row in rows:
            v=attrs[row["key"]]
            if row["relation"]=="recursive_method_call":
                assert not v.any()
            elif row["relation"]!="MOD_APPLY":
                assert bool(v[72])==(row["dst"] in unknown)
                expected_unknown[row["relation"]]+=int(v[72])
            if row["relation"]=="GUARDS":
                wanted=set()
                for ev in row["data"]["evidence"]:
                    wanted.add(43+GUARD_KINDS.index(ev["kind"]))
                    wanted.update(GUARD_OPERANDS[x] for x in ev["operand_classes"] if x in GUARD_OPERANDS)
                assert set(np.flatnonzero(v[43:55])+43)==wanted
            if row["relation"]=="CALL_SITE":
                assert bool(v[73])==(row["data"]["kind"]=="library")
            assert not v[15]
        stats=read(attr_root/task/"stats.json")
        assert stats["totals"]["edges"]==len(rows)
        assert stats["totals"]["all_zero_edges"]==int((array.sum(axis=1)==0).sum())
        for rel,item in stats["by_relation"].items():
            indices=[i for i,r in enumerate(rows) if r["relation"]==rel]
            m=array[indices]
            assert item["edges"]==len(indices)
            for i,name in enumerate(EDGE_FEATURE_NAMES):
                assert item["bits"][name]["ones"]==int(m[:,i].sum())
        results[task]=dict(edges=len(rows),dtype=str(array.dtype),dimension=array.shape[1],
            unknown_guard_targets=len(unknown),unk_guard_by_relation=dict(expected_unknown),
            numeric_digest=numeric_digest([r["key"] for r in rows],array),
            original_graph_unchanged=True,ep3_bytes_equal=True,attrs=ref(attr_root/task/"manifest.json"))
    selection=read(attr_root/"selection.json");recomputed=select_groups(endpoints)
    assert {k:v for k,v in selection.items() if k!="per_task"}==json.loads(json.dumps(recomputed))
    for task in ("reentrancy_contract","access_control_contract"):
        manifest=read(F4/task/"manifest.json");load_edges(F4/task/"manifest.json")
        audit=read(checked(manifest["audit"]))
        assert audit["hard_conditions_pass"] and audit["guards"]["nonmodifier_mapping_pass"]
    for name,record in before["documents"].items():
        data=(ROOT/name).read_bytes()
        assert hashlib.sha256(data[:record["bytes"]]).hexdigest()==record["sha256"]
        assert check(ROOT/name,since_bytes=record["bytes"],expect_cjk=True)["passed"]
    assert check(ROOT/"scripts/edge_sem/EP4_REPORT.md",expect_cjk=True)["passed"]
    changed=subprocess.check_output(["git","diff","--name-only"],cwd=str(ROOT),text=True).splitlines()
    assert all(p.startswith("scripts/edge_sem/") or p in before["documents"] for p in changed)
    write(OUT/"verification.json",dict(passed=True,tasks=results,selection=ref(attr_root/"selection.json"),
        frozen_source_count=len(before["frozen_code"]),dfg_code_refs=len(before["dfg_code_refs"]),
        prior_artifact_count=len(before["prior_artifacts"]),prior_edge_source_count=len(before["prior_edge_sources"]),
        documents_prefix_unchanged=True,frozen_8h_load=True,code_refs_unchanged=True,
        training_executed=False,gpu_executed=False))
    print("EP4 immutable source, archive, attributes and document verification passed",flush=True)


if __name__=="__main__":verify()
