"""L3 archive/provenance, parity and forward diagnostics; no real-data fit."""
import copy
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import torch

from scripts.DFG.dfg_v2.l2_build import verify_l1
from scripts.DFG.dfg_v2.l3_build import run, token_sample, verify_l2
from scripts.DFG.dfg_v2.l3_forward import compare_rows, run as forward_run
from scripts.DFG.dfg_v2.tests.test_l2_build import archive
from scripts.DFG.integration.io import read_json, sha256, write_json


def l2_archive(tmp_path):
    l1dir, _ = archive(tmp_path)
    l1, binding = verify_l1(l1dir)
    tid = next(iter(l1))
    root = tmp_path / "l2"
    td = root / tid
    td.mkdir(parents=True)
    graph = td / "hcg.gpickle"
    graph.write_bytes(b"frozen synthetic L2; archive verification never unpickles")
    original = l1[tid]
    inputs = dict(L1_graph=original["bundle"]["graph"],
        L1_bundle=str(original["directory"]/"manifest.json"),
        L1_bundle_sha256=binding["task_manifests"][tid],
        original_inputs=original["inputs"], sources={},
        source_manifest=original["inputs"]["source_manifest"],
        source_manifest_sha256=original["inputs"]["source_manifest_sha256"])
    for name, value in dict(inputs=inputs, audit={}, acceptance={},
                            model_schema={}, edge_sample={}).items():
        write_json(td/(name+".json"), value)
    bundle = dict(layer="L2",profile="G2R",training_executed=False,
        graph=dict(path=str(graph),sha256=sha256(graph),fingerprint="synthetic",
                   computation_fingerprint="synthetic"),
        files={name:sha256(td/(name+".json")) for name in
               ("inputs","audit","acceptance","model_schema","edge_sample")})
    write_json(td/"manifest.json", bundle)
    runtime_path = tmp_path/"runtime.py"
    runtime_path.write_text("# fixture calculation source\n")
    runtime = {str(runtime_path):sha256(runtime_path)}
    summary = dict(profile="G2R",training_executed=False,all_acceptance_passed=True,
        runtime=runtime,tasks=[dict(task_id=tid,task="node",bundle=bundle)])
    write_json(root/"summary.json",summary)
    write_json(root/"run_inputs.json",dict(runtime=runtime,L1=binding))
    write_json(root/"receipt.json",dict(status="accepted",training_executed=False,
        optimizer_steps=0,runtime=runtime,L1_receipt_sha256=binding["receipt_sha256"],
        summary_sha256=sha256(root/"summary.json"),
        task_manifests={tid:sha256(td/"manifest.json")}))
    return root,td,runtime_path


def refresh_summary_binding(root, summary):
    write_json(root/"summary.json", summary)
    receipt=read_json(root/"receipt.json")
    receipt["summary_sha256"]=sha256(root/"summary.json")
    write_json(root/"receipt.json",receipt)


def test_verified_l2_archive_read_only_with_bound_l1_provenance(tmp_path):
    root,td,_=l2_archive(tmp_path)
    before={str(p):sha256(p) for p in tmp_path.rglob("*") if p.is_file()}
    tasks,binding=verify_l2(root)
    assert list(tasks)==[td.name]
    assert tasks[td.name]["l1"]["bundle"]["profile"]=="G1R"
    assert binding["receipt_sha256"]==sha256(root/"receipt.json")
    assert before=={str(p):sha256(p) for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("name",["summary.json","audit.json","inputs.json",
                                  "model_schema.json","hcg.gpickle"])
def test_l2_tampering_rejected_before_new_output(tmp_path,name):
    root,td,_=l2_archive(tmp_path)
    path=(root if name=="summary.json" else td)/name
    path.write_bytes(path.read_bytes()+b" changed")
    output=tmp_path/"new_l3"
    with pytest.raises(ValueError,match="SHA256"):
        run(output,root)
    assert not output.exists()


@pytest.mark.parametrize("field,value",[("status","failed"),("training_executed",True),
                                        ("optimizer_steps",1)])
def test_nonaccepted_or_training_l2_receipt_rejected(tmp_path,field,value):
    root,_,_=l2_archive(tmp_path)
    receipt=read_json(root/"receipt.json")
    receipt[field]=value
    write_json(root/"receipt.json",receipt)
    with pytest.raises(ValueError,match="nontraining"):
        verify_l2(root)


def test_hash_valid_but_failed_summary_is_not_accepted(tmp_path):
    root,_,_=l2_archive(tmp_path)
    summary=read_json(root/"summary.json")
    summary["all_acceptance_passed"]=False
    refresh_summary_binding(root,summary)
    with pytest.raises(ValueError,match="G2R|accept"):
        verify_l2(root)


def test_runtime_change_after_l2_r1_requires_rebuild(tmp_path):
    root,_,runtime_path=l2_archive(tmp_path)
    runtime_path.write_text("# changed calculation\n")
    with pytest.raises(ValueError,match="SHA256"):
        verify_l2(root)


def test_l1_provenance_mismatch_is_not_treated_as_new_input(tmp_path):
    root,_,_=l2_archive(tmp_path)
    inputs=read_json(root/"run_inputs.json")
    inputs["L1"]["receipt_sha256"]="not-the-bound-l1"
    write_json(root/"run_inputs.json",inputs)
    with pytest.raises(ValueError,match="provenance"):
        verify_l2(root)


def test_duplicate_task_identity_in_hash_valid_summary_rejected(tmp_path):
    root,_,_=l2_archive(tmp_path)
    summary=read_json(root/"summary.json")
    summary["tasks"].append(copy.deepcopy(summary["tasks"][0]))
    refresh_summary_binding(root,summary)
    with pytest.raises(ValueError,match="task IDs must be unique"):
        verify_l2(root)


def test_existing_l3_output_never_overwritten(tmp_path):
    output=tmp_path/"existing"
    output.mkdir()
    sentinel=output/"sentinel"
    sentinel.write_text("preserve")
    with pytest.raises(FileExistsError,match="Refusing to overwrite"):
        run(output,tmp_path/"absent")
    assert sentinel.read_text()=="preserve"


def token_graph():
    graph=nx.MultiDiGraph()
    for n in range(25):
        graph.add_node(n,source_file="file.sol",code="expr_"+str(n),
                       token=np.full(512,n,dtype=np.float32))
    return graph


class MatchingEncoder:
    provenance={"tokenizer":"synthetic"}
    def __call__(self,code):
        return np.full(512,int(code.rsplit("_",1)[1]),dtype=np.float32)


def test_token_sample_exact_deterministic_twenty_original_nodes():
    graph=token_graph()
    encoder=MatchingEncoder()
    a=token_sample(graph,encoder)
    b=token_sample(graph,encoder)
    assert a==b and a["matched"]==20 and a["seed"]==0
    assert all(row["exact"] and row["repeat_exact"] for row in a["selected"])


@pytest.mark.parametrize("defect",["values","dtype","shape","nondeterministic"])
def test_token_sample_rejects_encoding_mismatch_and_nondeterminism(defect):
    graph=token_graph()
    class BadEncoder(MatchingEncoder):
        calls=0
        def __call__(self,code):
            result=super().__call__(code)
            self.calls+=1
            if defect=="values":return result+1
            if defect=="dtype":return result.astype(np.float64)
            if defect=="shape":return result.reshape(1,512)
            if self.calls%2==0:result[0]+=1
            return result
    with pytest.raises(ValueError,match="tokenizer parity"):
        token_sample(graph,BadEncoder())


def test_compare_rows_groups_by_key_and_uses_type_local_row_identity():
    rows=[dict(key="msg.sender",file="b.sol",row=2),
          dict(key="msg.sender",file="a.sol",row=0),
          dict(key="tx.origin",file="c.sol",row=1)]
    captured=torch.tensor([[1.0,2.0],[100.0,200.0],[1.5,2.0]])
    report=compare_rows(rows,captured,{0:"a",1:"c",2:"b"})
    assert report["msg.sender"]["pairs"]==1
    assert report["msg.sender"]["max_abs_diff"]==pytest.approx(0.5)
    assert report["msg.sender"]["zero_or_within_tolerance_pairs"]==[]
    assert report["tx.origin"]["pairs"]==0
    assert report["tx.origin"]["no_comparison_reason"]=="single_file_only"


@pytest.mark.parametrize("same_signatures",[True,False])
def test_compare_rows_equal_outputs_report_actual_signature_evidence(same_signatures):
    rows=[dict(key="gasleft",file="a.sol",row=0),dict(key="gasleft",file="b.sol",row=1)]
    report=compare_rows(rows,torch.zeros(2,3),{0:"same",1:"same" if same_signatures else "different"})
    pair=report["gasleft"]["zero_or_within_tolerance_pairs"][0]
    assert pair["files"]==["a.sol","b.sol"] and pair["max_abs_diff"]==0
    assert ("identical_incoming" in pair["reason"])==same_signatures
    if not same_signatures:
        assert "not_resolved" in pair["reason"]


def test_forward_rejects_input_sha_before_loading_graph(tmp_path):
    graph=tmp_path/"bad.gpickle"
    graph.write_bytes(b"not a pickle and must not be loaded")
    with pytest.raises(ValueError,match="SHA256"):
        forward_run(graph,"wrong","node","G3",tmp_path/"out.json")
    assert not (tmp_path/"out.json").exists()


def test_forward_preserves_existing_receipt_before_reading_input(tmp_path):
    output=tmp_path/"out.json"
    output.write_text("historical")
    with pytest.raises(FileExistsError):
        forward_run(tmp_path/"absent","wrong","node","G3R",output)
    assert output.read_text()=="historical"
