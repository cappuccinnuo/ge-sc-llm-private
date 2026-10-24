"""Prompt 3 archive, invariant, identity-statistic and CPU-schema guards."""
import copy
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from scripts.DFG.dfg_v2 import DATA_DEF_USE, READS_STATE, WRITES_STATE
from scripts.DFG.dfg_v2.l2_build import (
    assert_l2_only, coverage_summary, model_schema, run, sample_edges, verify_l1,
)
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.integration.io import read_json, sha256, write_json


def archive(tmp_path):
    root = tmp_path/"l1"
    root.mkdir()
    tid = "synthetic_author_node"
    taskdir = root/tid
    taskdir.mkdir()
    original = tmp_path/"original.gpickle"
    original.write_bytes(b"original fixture; validation here checks identities only")
    graph = taskdir/"hcg.gpickle"
    graph.write_bytes(b"frozen L1 fixture; no unpickle during archive guard")
    task_path, source_path = tmp_path/"task.json", tmp_path/"sources.json"
    original_ref = dict(path=str(original),sha256=sha256(original))
    write_json(task_path,dict(graphs={"HCG":original_ref}))
    write_json(source_path,dict(sources={}))
    inputs = dict(original_graph=original_ref,task_manifest=str(task_path),
        task_manifest_sha256=sha256(task_path),source_manifest=str(source_path),
        source_manifest_sha256=sha256(source_path),sources={},missing_sources=[])
    documents = dict(inputs=inputs,audit={},acceptance={},model_schema={})
    for key,value in documents.items():
        write_json(taskdir/(key+".json"),value)
    bundle = dict(version="dfg-v2",layer="L1",profile="G1R",training_executed=False,
        graph=dict(path=str(graph),sha256=sha256(graph),fingerprint="fixture",
                   computation_fingerprint="fixture"),
        files={key:sha256(taskdir/(key+".json")) for key in documents})
    write_json(taskdir/"manifest.json",bundle)
    frozen = tmp_path/"frozen"
    frozen.mkdir()
    manifest = frozen/"manifest.json"
    write_json(manifest,dict(tasks=[dict(task_id=tid,task="node",
        source_task_manifest=str(task_path),source_task_sha256=sha256(task_path),
        source_metadata_manifest=str(source_path),source_metadata_sha256=sha256(source_path))]))
    write_json(frozen/"manifest.seal.json",dict(sha256=sha256(manifest)))
    baseline = tmp_path/"baseline.json"
    write_json(baseline,dict(frozen=True))
    runtime = {"historical/fixture.py":"original-code-sha"}
    summary=dict(profile="G1R",all_acceptance_passed=True,training_executed=False,
        runtime=runtime,tasks=[dict(task_id=tid,task="node",bundle=bundle)])
    write_json(root/"summary.json",summary)
    write_json(root/"run_inputs.json",dict(runtime=runtime,manifest=str(manifest),
        manifest_sha256=sha256(manifest),prompt0_baseline=str(baseline),
        prompt0_baseline_sha256=sha256(baseline)))
    write_json(root/"receipt.json",dict(status="accepted",training_executed=False,
        optimizer_steps=0,runtime=runtime,summary_sha256=sha256(root/"summary.json"),
        manifest_sha256=sha256(manifest),prompt0_baseline_sha256=sha256(baseline),
        task_manifests={tid:sha256(taskdir/"manifest.json")}))
    return root,taskdir


def test_existing_output_never_overwritten(tmp_path):
    output=tmp_path/"existing"
    output.mkdir()
    (output/"sentinel").write_text("keep")
    with pytest.raises(FileExistsError,match="Refusing to overwrite"):
        run(output,tmp_path/"missing")
    assert (output/"sentinel").read_text()=="keep"


def test_archive_verification_preserves_history_without_requiring_current_runtime(tmp_path):
    root,taskdir=archive(tmp_path)
    before={str(p):sha256(p) for p in root.rglob("*") if p.is_file()}
    tasks,binding=verify_l1(root)
    assert list(tasks)==["synthetic_author_node"]
    assert binding["runtime"]=={"historical/fixture.py":"original-code-sha"}
    assert before=={str(p):sha256(p) for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("artifact",["summary.json","inputs.json","audit.json","hcg.gpickle"])
def test_tampered_l1_artifacts_rejected_before_output(tmp_path,artifact):
    root,taskdir=archive(tmp_path)
    path=root/artifact if artifact=="summary.json" else taskdir/artifact
    path.write_bytes(path.read_bytes()+b" ")
    output=tmp_path/"new"
    with pytest.raises(ValueError,match="SHA256"):
        run(output,root)
    assert not output.exists()


def test_rejected_l1_receipt_cannot_be_reused(tmp_path):
    root,_=archive(tmp_path)
    receipt=read_json(root/"receipt.json")
    receipt["status"]="failed"
    write_json(root/"receipt.json",receipt)
    with pytest.raises(ValueError,match="accepted nontraining"):
        verify_l1(root)


def test_frozen_input_manifest_change_is_rejected(tmp_path):
    root,_=archive(tmp_path)
    manifest=Path(read_json(root/"run_inputs.json")["manifest"])
    manifest.write_text("{}")
    with pytest.raises(ValueError,match="SHA256"):
        verify_l1(root)


def graphs():
    base=nx.MultiDiGraph()
    for node,kind,code in [(1,"new_variable","uint balance;"),
                           (2,"expression_statement","balance += x;"),
                           (3,"return","return balance;")]:
        base.add_node(node,node_type=kind,source_file="same.sol",code=code,
            token=np.zeros(512,dtype=np.float32),node_info_vulnerabilities=None,
            node_source_code_lines=[node],label=str(node),method="",
            type_label=kind)
    base.add_edge(1,2,edge_type="next")
    base.add_edge(2,3,edge_type=DATA_DEF_USE,evidence_indices=[0],custom={"frozen":True})
    enhanced=copy.deepcopy(base)
    for s,t,r,alias in [(2,1,WRITES_STATE,True),(1,2,READS_STATE,False),(1,3,READS_STATE,False)]:
        enhanced.add_edge(s,t,edge_type=r,state_vars=["balance"],via_alias=alias,
                          evidence_indices=[0])
    return base,enhanced


def audit_fixture():
    def ev(s,t,rel,callable,alias=False):
        return dict(source=s,target=t,relation=rel,callable=callable,
                    via_alias=alias,status="projected",file="same.sol")
    audit=dict(files={"same.sol":dict(
        declarations=[dict(file="same.sol",name="balance",node_id=1,
                           start=10,end=23,line=1,status="matched")],
        callables={"same.sol:30":{},"same.sol:80":{}},units=3,
        occurrences={"READ":2,"WRITE":2},unresolved_reasons={},unmapped=0,anchor_missing=0)},
        evidence=[ev(2,1,WRITES_STATE,"same.sol:30"),
                  ev(2,1,WRITES_STATE,"same.sol:30",True),
                  ev(1,2,READS_STATE,"same.sol:30"),
                  ev(1,3,READS_STATE,"same.sol:80")])
    l1=dict(files={"same.sol":dict(analysis=dict(functions=[
        dict(function="same.sol:30",file="same.sol",status="fallback"),
        dict(function="same.sol:80",file="same.sol",status="supported")]))})
    return audit,l1


def test_l2_only_addition_preserves_parallel_relations_keys_labels_tokens_and_l1_attributes():
    base,enhanced=graphs()
    before=fingerprint(base)
    report=assert_l2_only(base,enhanced)
    assert fingerprint(base)==before
    assert report["L1_DATA_DEF_USE_attributes_exact"]
    assert report["added_by_relation"]=={WRITES_STATE:1,READS_STATE:2}
    assert enhanced.number_of_edges(1,2)==2


@pytest.mark.parametrize("mutation",["label","L1","base_edge","self","duplicate"])
def test_changed_baseline_or_invalid_l2_edge_rejected(mutation):
    base,enhanced=graphs()
    if mutation=="label":
        enhanced.nodes[2]["node_info_vulnerabilities"]=[{"changed":True}]
    elif mutation=="L1":
        next(d for _,_,d in enhanced.edges(data=True)
             if d["edge_type"]==DATA_DEF_USE)["custom"]["frozen"]=False
    elif mutation=="base_edge":
        enhanced.remove_edge(1,2,0)
    elif mutation=="self":
        enhanced.add_edge(1,1,edge_type=READS_STATE)
    else:
        enhanced.add_edge(1,3,edge_type=READS_STATE)
    with pytest.raises(AssertionError):
        assert_l2_only(base,enhanced)


def test_coverage_uses_unique_edges_and_exact_function_identity():
    _,graph=graphs()
    audit,l1=audit_fixture()
    report=coverage_summary(graph,audit,l1)
    assert report["L1_fallback_functions"]==1
    assert report["L1_fallback_functions_with_L2"]==1
    assert report["L1_fallback_L2_edges"]==2
    assert report["L2_edges"]=={WRITES_STATE:1,READS_STATE:2}
    assert report["alias_edges"]==1
    assert report["alias_edge_fraction"]==pytest.approx(1/3)
    assert report["cross_callable_pairs"]==1
    assert report["top10_READS_STATE_outdegree"][0]["degree"]==2
    assert report["top10_WRITES_STATE_indegree"][0]["degree"]==1


def test_graph_edges_without_corresponding_evidence_are_rejected():
    _,graph=graphs()
    audit,l1=audit_fixture()
    audit["evidence"]=[ev for ev in audit["evidence"] if ev["target"]!=3]
    with pytest.raises(AssertionError,match="evidence"):
        coverage_summary(graph,audit,l1)


def test_seeded_sample_is_deterministic_and_has_real_endpoint_code():
    _,graph=graphs()
    first=sample_edges(graph,{},count=2,seed=0)
    assert first==sample_edges(graph,{},count=2,seed=0)
    assert len(first["edges"])==2
    for edge in first["edges"]:
        assert edge["source_code"]==graph.nodes[edge["source"]]["code"]
        assert edge["target_code"]==graph.nodes[edge["target"]]["code"]


@pytest.mark.parametrize("task",["node","contract"])
def test_cpu_g2r_model_registers_explicit_reverse_without_training(task):
    _,graph=graphs()
    before=fingerprint(graph)
    report=model_schema(graph,task)
    assert report["profile"]=="G2R"
    assert report["input_width"]==512
    assert report["optimizer_steps"]==0
    assert report["model_forward_executed"] is False
    assert report["relation_edges"]=={
        WRITES_STATE:1,READS_STATE:2,"REV_WRITES_STATE":1,"REV_READS_STATE":2}
    assert fingerprint(graph)==before


def test_unresolved_categories_and_policy_exclusions_remain_separate():
    _,graph=graphs()
    audit,l1=audit_fixture()
    record=audit["files"]["same.sol"]
    record["unresolved_reasons"]={"ambiguous_state":2}
    record["alias_unresolved_reasons"]={"no_version_evidence":3}
    record["access_unresolved_reasons"]={"unsupported_ast":1}
    record["diagnostics"]=[dict(kind="state_binding_excluded",reason="constant_excluded")]
    record["alias_bindings"]=2
    report=coverage_summary(graph,audit,l1)
    assert report["binding_unresolved_occurrences"]==2
    assert report["alias_unresolved_occurrences"]==3
    assert report["access_unresolved_occurrences"]==1
    assert report["binding_excluded_occurrences"]==1
    assert report["alias_bindings"]==2
    assert "constant_excluded" not in report["unresolved_reasons"]


def test_state_initializer_does_not_count_as_cross_callable_reader():
    _,graph=graphs()
    audit,l1=audit_fixture()
    audit["evidence"][-1]["callable_kind"]="state_variable_declaration"
    report=coverage_summary(graph,audit,l1)
    assert report["cross_callable_pairs"]==0
