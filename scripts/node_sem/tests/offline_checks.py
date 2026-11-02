"""Run separately in nodesem: pytest scripts/node_sem/tests/offline_checks.py.

Deliberately not named test_*.py: mando must never import offline encoder code.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest
import torch

OFFLINE=Path(__file__).resolve().parents[1]/"offline"
sys.path.insert(0,str(OFFLINE))
import encode
import asset_registry as assets


class Tokenizer:
    def __call__(self,texts,truncation=False,add_special_tokens=True,
                 padding=False,max_length=None,return_tensors=None):
        ids=[[ord(c)%50+1 for c in s]+[2] for s in texts]
        if truncation:ids=[v[:max_length] for v in ids]
        if return_tensors:
            width=max(len(v) for v in ids)
            return {"input_ids":torch.tensor([v+[0]*(width-len(v)) for v in ids]),
                    "attention_mask":torch.tensor([[1]*len(v)+[0]*(width-len(v)) for v in ids])}
        return {"input_ids":ids}


class Encoder(torch.nn.Module):
    def forward(self,input_ids,attention_mask):
        x=input_ids.float()
        return torch.stack([(x*attention_mask).sum(1),attention_mask.sum(1).float()],dim=1)


def test_length_batching_restores_order_and_determinism():
    texts=["abcd","a","long long","xy"]
    a,stats=encode.encode_unique(texts,Tokenizer(),Encoder(),"cpu",5,"model_default",2,2)
    b,_=encode.encode_unique(texts,Tokenizer(),Encoder(),"cpu",5,"model_default",2,2)
    assert np.array_equal(a,b)
    assert stats["truncated_unique"]==1
    for i,text in enumerate(texts):
        ids=Tokenizer()([text])["input_ids"][0][:5]
        np.testing.assert_array_equal(a[i],np.array([sum(ids),len(ids)],dtype=np.float32))
    assert encode.schedule(texts,[5,2,10,3])==[1,3,0,2]


def test_mean_pool_ignores_padding_and_handles_empty():
    hidden=torch.tensor([[[2.,4.],[4.,8.],[999.,999.]],[[4.,3.],[8.,4.],[8.,7.]]])
    mask=torch.tensor([[1,1,0],[0,0,0]])
    assert torch.equal(encode.mean_pool(hidden,mask),torch.tensor([[3.,6.],[0.,0.]]))


def test_mean_pool_path_and_nonfinite_rejection():
    class Mean(torch.nn.Module):
        def forward(self,input_ids,attention_mask):
            h=input_ids.float().unsqueeze(-1).repeat(1,1,3)
            return SimpleNamespace(last_hidden_state=h)
    v,_=encode.encode_unique(["ab","c"],Tokenizer(),Mean(),"cpu",128,"mean",2,3)
    for row,text in zip(v,["ab","c"]):
        assert np.allclose(row,np.mean(Tokenizer()([text])["input_ids"][0]))
    class Bad(Encoder):
        def forward(self,**kwargs):
            return super().forward(**kwargs)*float("nan")
    with pytest.raises(ValueError,match="Non-finite"):
        encode.encode_unique(["a"],Tokenizer(),Bad(),"cpu",128,"model_default",1,2)


def test_empty_unique_has_no_inference():
    class NoCall:
        def __call__(self,*a,**k):raise AssertionError("empty inference called")
    v,stats=encode.encode_unique([],NoCall(),NoCall(),"cpu",128,"mean",2,3)
    assert v.shape==(0,3) and v.dtype==np.float32 and stats["batch_count"]==0


@pytest.mark.parametrize("field",range(4))
def test_dedup_identity_binds_all_encoding_choices(field):
    args=["a","model-sha",128,"model_default"]
    original=encode.cache_key(*args)
    args[field]=129 if field==2 else str(args[field])+"changed"
    assert original != encode.cache_key(*args)


def test_nonblocking_lock_and_cpu_exception(tmp_path):
    import fcntl
    path=tmp_path/"shared.lock";path.touch()
    with path.open("r+") as existing:
        fcntl.flock(existing,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match="GPU lock"):
            with encode.gpu_lock(path,"cuda"):raise AssertionError("entered")
        with encode.gpu_lock(path,"cpu"):pass
    with encode.gpu_lock(path,"cuda"):pass
    assert path.read_bytes()==b""


def text_fixture(tmp_path):
    source=tmp_path/"a.sol";source.write_text("contract A {}")
    implementation=tmp_path/"producer.py";implementation.write_text("pass")
    row=dict(row_key="n",file="a.sol",node_type="contract_declaration",text="contract A",
             text_sha256=hashlib.sha256(b"contract A").hexdigest(),source_sha256=assets.sha(source))
    text=tmp_path/"text.jsonl";text.write_text(json.dumps(row)+"\n")
    m=dict(version="nodesem-text-v1",view="original",task_id="fictional_node",
           input_text=assets.reference(text),rows=[row],sources={"a.sol":assets.reference(source)},
           implementation={"producer":assets.reference(implementation)})
    path=tmp_path/"manifest.json";assets.write(path,m)
    assets.write(tmp_path/"manifest.seal.json",dict(manifest=assets.reference(path)))
    return text,m,source,implementation


@pytest.mark.parametrize("mutation",["text","source","implementation","manifest"])
def test_input_tamper_rejected(tmp_path,mutation):
    text,m,source,implementation=text_fixture(tmp_path)
    rows,_,_=encode.load_texts(text);assert len(rows)==1
    target={"text":text,"source":source,"implementation":implementation,
            "manifest":tmp_path/"manifest.json"}[mutation]
    target.write_text(target.read_text()+" ")
    with pytest.raises(ValueError):encode.load_texts(text)


def registry_fixture(tmp_path):
    root=tmp_path/"models";root.mkdir()
    index={"models":[]}
    for repo,(name,_,_,_) in assets.FAMILIES.items():
        folder=root/name;folder.mkdir()
        weights=folder/"model.bin";weights.write_bytes(b"synthetic-not-loaded")
        (folder/"REVISION").write_text("revision1")
        manifest={"status":"complete","revision":"revision1",
                  "files":[{"path":"model.bin","bytes":weights.stat().st_size,"sha256":assets.sha(weights)}]}
        assets.write(folder/"download_manifest.json",manifest)
        index["models"].append({"repo_id":repo,"directory":name,"revision":"revision1",
                               "manifest_sha256":assets.sha(folder/"download_manifest.json")})
    assets.write(root/"MODEL_MANIFEST.json",index)
    registry=tmp_path/"assets.json";assets.register(root,registry)
    return registry,root


@pytest.mark.parametrize("mutation",["weights","extra","registry"])
def test_asset_integrity_and_no_unregistered_files(tmp_path,mutation):
    registry,root=registry_fixture(tmp_path)
    name="codet5p-110m-embedding"
    assert assets.load_model_entry(registry,name)["dimension"]==256
    if mutation=="weights":(root/name/"model.bin").write_bytes(b"tampered")
    elif mutation=="extra":(root/name/"unregistered.py").write_text("pass")
    else:registry.write_text(registry.read_text()+" ")
    with pytest.raises(ValueError):assets.load_model_entry(registry,name)


def test_output_refuses_overwrite_before_model_loading(tmp_path):
    with pytest.raises(FileExistsError):
        encode.run(tmp_path/"missing","codet5p-110m-embedding",tmp_path/"missing",128,"model_default",tmp_path,"cpu")



def test_encoder_refuses_user_site_import_paths(monkeypatch,tmp_path):
    monkeypatch.setattr(encode.site,"ENABLE_USER_SITE",True)
    with pytest.raises(RuntimeError,match="python -s"):
        encode.run(tmp_path/"missing","codet5p-110m-embedding",tmp_path/"assets",
                   128,"model_default",tmp_path/"out","cpu")
