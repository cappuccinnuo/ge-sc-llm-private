from argparse import Namespace
from pathlib import Path
import pytest
from scripts.DFG.experiments import paper_run, formal_worker
from scripts.DFG.experiments.formal_checks import verify_fold
from scripts.DFG.experiments.common import write_json,sha256,code_hashes,read_json
from scripts.DFG.experiments.tests.test_runtime import graph_fixture
from scripts.labeling_v2.safe_graph import write_graph


@pytest.mark.parametrize("task",["contract","node"])
def test_full_tiny_hgt_with_telemetry_and_independent_artifact_acceptance(tmp_path,monkeypatch,task):
    prepared=tmp_path/"prepared"
    prepared.mkdir()
    graphs={v:graph_fixture(v=="E1") for v in ("E0","E1")}
    paths={v:prepared/(v+".gpickle") for v in graphs}
    for v in graphs:
        write_graph(graphs[v],paths[v])
    labels={f:1 for f in ("train.sol","valid.sol","test.sol")}
    label_path=prepared/"labels.json"
    write_json(label_path,[dict(contract_name=f,targets=y) for f,y in labels.items()])
    manifest={"cohort":"fixture","graph_labels":{"path":label_path.name,"sha256":sha256(label_path)},
              "graphs":{v:{task:{"path":paths[v].name,"sha256":sha256(paths[v])}} for v in graphs}}
    write_json(prepared/"manifest.json",manifest)
    splits={"seed":1,"folds":[{"fold":0,"train_files":["train.sol"],"val_files":["test.sol","valid.sol"]}]}
    split_path=tmp_path/"splits.json"
    write_json(split_path,splits)
    monkeypatch.setattr(paper_run,"load_inputs",lambda *a:(manifest,splits,paths,label_path,labels,graphs,{}))
    monkeypatch.setattr(paper_run,"protocol_output",lambda p:Path(p))
    out=tmp_path/"out"
    args=Namespace(prepared=str(prepared),splits=str(split_path),output=str(out),task=task,
                   fold=0,device="cpu",threads=1,mode="full",epochs=50,smoke_epochs=3,seed=1)
    result=formal_worker.execute(args)
    job={"id":"fixture_"+task+"_fold0","cohort":"fixture","task":task,"fold":0,
         "prepared":str(prepared),"splits":str(split_path)}
    plan={"device":"cpu","threads":1,"runner_code_sha256":code_hashes()}
    accepted=verify_fold(out,job,plan)
    assert accepted["status"]=="passed"
    assert accepted["variants"]["E1"]["ddg_train_edges"]==3
    assert accepted["variants"]["E1"]["ddg_gradient_l1_sum"]>0
    # Deliberately corrupt checkpoint; integrity must fail before accepting metrics.
    checkpoint=out/"fold_0"/"E1"/"best.pt"
    with checkpoint.open("ab") as f:
        f.write(b"corrupt")
    with pytest.raises(ValueError,match="Checkpoint file changed"):
        verify_fold(out,job,plan)
