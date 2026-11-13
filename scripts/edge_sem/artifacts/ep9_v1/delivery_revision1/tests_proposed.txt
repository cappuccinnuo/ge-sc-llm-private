
"""Lossless EP9 Git delivery, path safety, and non-overwriting restoration."""
import gzip
import hashlib
import json
from pathlib import Path
import pytest
from scripts.edge_sem.recon import ep9_run as driver


def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True)+"\n",encoding="utf8")


@pytest.fixture
def delivery(tmp_path,monkeypatch):
    root=tmp_path/"scripts/edge_sem/artifacts/ep9_v1"
    root.mkdir(parents=True)
    monkeypatch.setattr(driver,"ROOT",tmp_path)
    monkeypatch.setattr(driver,"DEFAULT_ROOT",root)
    monkeypatch.setattr(driver,"write",put)
    put(root/"delivery_revision1/approval.json",{"approval":"fixture"})
    return root


def bundle(root):
    large=root/"preparation/index.json";raw=json.dumps({"complete":["中文"*10]*10000}).encode("utf8")
    large.parent.mkdir();large.write_bytes(raw)
    small=root/"plan.seal.json";small.write_text('{"small":true}\n',encoding="utf8")
    selected,manifest=driver.delivery_bundle(root,[large,small],threshold=64)
    return large,raw,small,selected,manifest


def reseal(path,value):
    put(path,value)
    put(path.with_suffix(".seal.json"),dict(manifest_name=path.name,
        sha256=driver.ref(path)["sha256"],bytes=path.stat().st_size))


def test_bundle_keeps_raw_and_restores_exact_bytes_without_overwrite(delivery):
    large,raw,small,selected,manifest=bundle(delivery)
    base=driver.ROOT
    assert large.read_bytes()==raw and str(large.relative_to(base)) not in selected
    assert str(small.relative_to(base)) in selected
    m=driver.read(manifest);assert len(m["rows"])==1
    row=m["rows"][0]
    blob=base/row["gzip_path"]
    assert gzip.decompress(blob.read_bytes())==raw
    assert driver.restore_delivery(manifest)["restored"]==0
    # Remove only this synthetic fixture to exercise restoring a clean clone.
    large.unlink()
    assert driver.restore_delivery(manifest)["restored"]==1
    assert large.read_bytes()==raw and driver.restore_delivery(manifest)["restored"]==0
    assert not list(large.parent.glob("*.tmp"))


def test_deterministic_gzip_and_no_duplicate_objects(delivery):
    large,raw,small,selected,manifest=bundle(delivery)
    one=driver.read(manifest)["rows"][0]
    _,second=driver.delivery_bundle(delivery,[large,small],threshold=64)
    two=driver.read(second)["rows"][0]
    assert one==two
    assert len(list((delivery/"github_delivery/objects").glob("*.gz")))==1
    assert len(list((delivery/"github_delivery").glob("manifest_*.json")))==4


def test_existing_changed_json_is_not_overwritten(delivery):
    large,raw,_,_,manifest=bundle(delivery)
    large.write_bytes(b"changed local data")
    with pytest.raises(ValueError,match="will not overwrite"):driver.restore_delivery(manifest)
    assert large.read_bytes()==b"changed local data"


@pytest.mark.parametrize("damage",["blob","manifest","expanded_size","expanded_sha","traversal","absolute","symlink"])
def test_tampering_and_unsafe_paths_are_refused(delivery,damage):
    large,raw,_,_,manifest=bundle(delivery)
    value=driver.read(manifest);row=value["rows"][0]
    if damage=="blob":
        p=driver.ROOT/row["gzip_path"];p.write_bytes(p.read_bytes()+b"tampered")
    elif damage=="manifest":
        manifest.write_text(manifest.read_text()+" ")
    elif damage=="expanded_size":
        row["source_bytes"]-=1;reseal(manifest,value)
    elif damage=="expanded_sha":
        row["source_sha256"]="0"*64;reseal(manifest,value)
    elif damage=="traversal":
        row["source_path"]="../elsewhere.json";reseal(manifest,value)
    elif damage=="absolute":
        row["source_path"]="/tmp/elsewhere.json";reseal(manifest,value)
    else:
        large.unlink();large.symlink_to(delivery/"plan.seal.json")
    with pytest.raises(ValueError):driver.restore_delivery(manifest)
    if damage!="symlink":assert large.read_bytes()==raw


def test_unexpected_delivery_root_refused(delivery):
    with pytest.raises(ValueError,match="Unexpected"):
        driver.delivery_bundle(delivery/"other",[])


def test_absolute_size_and_digest_checks(delivery):
    _,raw,_,_,manifest=bundle(delivery)
    row=driver.read(manifest)["rows"][0];blob=driver.ROOT/row["gzip_path"]
    assert driver._gzip_content_digest(blob,len(raw))==hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):driver._gzip_content_digest(blob,len(raw)+1)


def test_commit_uses_explicit_force_add_and_excludes_weight_files(delivery,monkeypatch):
    for name in ("HANDOVER.md","docs/training_changes_2026-10-07.md","scripts/edge_sem/PROGRESS.md"):
        p=driver.ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text("fixture\n")
    (delivery/"weights").mkdir()
    for name in ("initial.pt","features.npz","cache.npy"):
        (delivery/"weights"/name).write_bytes(b"not delivery")
    large,raw,_,_,_=bundle(delivery)
    calls=[]
    monkeypatch.setattr(driver.subprocess,"check_output",lambda *a,**k:b"")
    monkeypatch.setattr(driver.subprocess,"run",lambda cmd,**kw:calls.append(cmd))
    driver.commit_delivery(delivery,"EP9 fixture")
    command=next(c for c in calls if c[:2]==["git","add"])
    assert "-f" in command
    path=Path(next(c.split("=",1)[1] for c in command if c.startswith("--pathspec-from-file=")))
    names=path.read_bytes().decode().split("\0")
    assert not any(n.endswith((".pt",".npz",".npy")) for n in names)
    assert str(large.relative_to(driver.ROOT)) not in names
    assert any(n.endswith(".json.gz") for n in names)
