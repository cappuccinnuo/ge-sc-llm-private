"""Provenance verifier rejection tests use synthetic identities only."""
import copy
import hashlib
import json
from pathlib import Path
import pytest
from scripts.node_sem.facts_schema import new_facts
from scripts.node_sem.facts_verify import (validate_row_identity, verify_frozen_snapshot,
    sealed_manifest, discover_original_text, byte_sha)
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, write


def rows():
    fact=new_facts("statement")
    fact["provenance"]["source_sha256"]="a"*64
    text={"row_key":1,"file":"a.sol","node_type":"expression_statement",
        "source_sha256":"a"*64,"code_sha256":"b"*64,"text":"x=1;",
        "text_sha256":hashlib.sha256(b"x=1;").hexdigest()}
    return [{"row_key":1,"facts":fact}],[text],{"a.sol":{"sha256":"a"*64}}


def test_row_identity_verifies_source_and_order():
    facts,text,sources=rows()
    result=validate_row_identity(facts,text,sources)
    assert result["rows"]==1 and result["source_files"]==1
    assert len(result["identity_order_sha256"])==64


@pytest.mark.parametrize("mutation",["id","id_type","source","view","text","population","file"])
def test_row_identity_rejects_changed_input(mutation):
    facts,text,sources=rows()
    if mutation=="id":facts[0]["row_key"]=2
    if mutation=="id_type":facts[0]["row_key"]=True
    if mutation=="source":facts[0]["facts"]["provenance"]["source_sha256"]="c"*64
    if mutation=="view":facts[0]["facts"]["provenance"]["view"]="other"
    if mutation=="text":text[0]["text"]="x=2;"
    if mutation=="population":facts=[]
    if mutation=="file":text[0]["file"]="other.sol"
    with pytest.raises(ValueError):validate_row_identity(facts,text,sources)


def test_duplicate_row_rejected_even_if_expected_duplicate():
    facts,text,sources=rows()
    with pytest.raises(ValueError,match="Duplicate"):
        validate_row_identity(facts+facts,text+text,sources)


def test_swapped_order_rejected():
    facts,text,sources=rows()
    second_facts,second_text=copy.deepcopy(facts),copy.deepcopy(text)
    second_facts[0]["row_key"]=2
    second_text[0]["row_key"]=2
    with pytest.raises(ValueError,match="order"):
        validate_row_identity(facts+second_facts,second_text+text,sources)


def test_auxiliary_identity_rejected():
    facts,text,sources=rows()
    text[0]["node_type"]="env_source"
    with pytest.raises(ValueError,match="Auxiliary"):
        validate_row_identity(facts,text,sources)


def test_frozen_snapshot_permits_only_scoped_changes(tmp_path):
    original=tmp_path/"frozen.py"
    original.write_text("fixed",encoding="utf8")
    allowed=tmp_path/"scripts/node_sem/PROGRESS.md"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("before",encoding="utf8")
    snapshot=tmp_path/"start.json"
    write(snapshot,{"tracked_sha256":{"frozen.py":byte_sha(original),"scripts/node_sem/PROGRESS.md":byte_sha(allowed)}})
    allowed.write_text("after",encoding="utf8")
    result=verify_frozen_snapshot(snapshot,tmp_path)
    assert result["frozen_files_checked"]==1
    assert set(result["allowed_changes"])=={"scripts/node_sem/PROGRESS.md"}
    original.write_text("changed",encoding="utf8")
    with pytest.raises(ValueError,match="Frozen"):
        verify_frozen_snapshot(snapshot,tmp_path)


def test_frozen_missing_file_rejected(tmp_path):
    snapshot=tmp_path/"start.json"
    write(snapshot,{"tracked_sha256":{"gone.py":"a"*64}})
    with pytest.raises(ValueError,match="missing"):
        verify_frozen_snapshot(snapshot,tmp_path)


def test_seal_and_text_discovery_reject_changes(tmp_path):
    directory=tmp_path/"task"
    directory.mkdir()
    path=directory/"manifest.json"
    write(path,{"version":"nodesem-text-v1","view":"original","task_id":"unit"})
    write(directory/"manifest.seal.json",{"manifest":ref(path)})
    assert set(discover_original_text(tmp_path))=={"unit"}
    path.write_text("{}",encoding="utf8")
    with pytest.raises(ValueError,match="seal"):
        sealed_manifest(path)


def test_text_discovery_rejects_duplicate_task(tmp_path):
    for name in ("a","b"):
        directory=tmp_path/name
        directory.mkdir()
        path=directory/"manifest.json"
        write(path,{"version":"nodesem-text-v1","view":"original","task_id":"unit"})
        write(directory/"manifest.seal.json",{"manifest":ref(path)})
    with pytest.raises(ValueError,match="Duplicate"):
        discover_original_text(tmp_path)
