"""Historical bytes remain required when current EdgeSem sources evolve."""
import copy
import json
import pytest
from scripts.edge_sem.recon import ep6_common
from scripts.edge_sem.io import ref


def test_snapshot_gate_requires_exact_original_and_snapshot_sha(tmp_path,monkeypatch):
    source=tmp_path/"source.py";source.write_bytes(b"original\n")
    original=ref(source)
    snapshot=tmp_path/"snapshot.txt";snapshot.write_bytes(source.read_bytes())
    old=ref(snapshot);source.write_bytes(b"updated\n")
    (tmp_path/"before.json").write_text(json.dumps(dict(authorized_source_changes=[
        dict(original=original,snapshot=old)])))
    monkeypatch.setattr(ep6_common,"OUT",tmp_path)
    ep6_common.historical_refs([original])
    bad=copy.deepcopy(original);bad["sha256"]="0"*64
    with pytest.raises(ValueError):ep6_common.historical_refs([bad])
    snapshot.write_bytes(b"tampered\n")
    with pytest.raises(ValueError):ep6_common.historical_refs([original])


def test_unknown_changed_source_has_no_archive_exception(tmp_path,monkeypatch):
    source=tmp_path/"source.py";source.write_bytes(b"before");old=ref(source);source.write_bytes(b"after")
    (tmp_path/"before.json").write_text(json.dumps(dict(authorized_source_changes=[])))
    monkeypatch.setattr(ep6_common,"OUT",tmp_path)
    with pytest.raises(ValueError):ep6_common.historical_refs([old])
