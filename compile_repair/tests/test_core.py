"""CP1 byte provenance and exclusive artifact guarantees."""
import json
from dataclasses import replace

import pytest

from compile_repair.core.model import Patch
from compile_repair.core.provenance import (apply_patches, check_additive, mark_span,
                                           original_to_new, verify_provenance)
from compile_repair.core.store import ArtifactStore, sha256


def test_insertions_preserve_utf8_bytes_and_node_boundaries():
    original = '甲abc'.encode()
    current, evidence = apply_patches(original,[Patch(3,3,b'',b'XY','stub')])
    assert current == '甲XYabc'.encode() and evidence.level == 'additive'
    assert verify_provenance(original,current,evidence) and check_additive(original,current,evidence)
    assert [original_to_new(evidence,i) for i in range(6)] == [0,1,2,5,6,7]
    assert mark_span(evidence,0,3) == 'original'
    assert mark_span(evidence,3,2) == 'added'
    assert mark_span(evidence,2,4) == 'rewritten'
    assert mark_span(evidence,8,0) == 'original'
    assert not check_additive(original,current[:-1]+b'x',evidence)
    with pytest.raises(ValueError,match='mismatch'):
        verify_provenance(original,current[:-1]+b'x',evidence)


def test_rewrite_delete_and_sequential_current_copy_coordinates():
    original = b'abcdef'
    patches=[Patch(1,3,b'bc',b'XY','rewrite'),Patch(4,5,b'e',b'','delete',2)]
    current,evidence=apply_patches(original,patches)
    assert current == b'aXYdf' and evidence.level == 'rewrite'
    assert mark_span(evidence,1,2) == 'rewritten'
    assert mark_span(evidence,3,2) == 'rewritten'  # spans deleted e
    assert original_to_new(evidence,1) == 1 and original_to_new(evidence,4) is None
    assert verify_provenance(original,current,evidence)
    with pytest.raises(ValueError,match='preimage'):
        apply_patches(original,[Patch(1,2,b'wrong',b'X','bad')])
    with pytest.raises(ValueError,match='outside'):
        mark_span(evidence,99,1)
    with pytest.raises(ValueError,match='mismatch'):
        verify_provenance(original,current,replace(evidence,level='additive'))


def test_store_exclusive_paths_and_seal_all_files(tmp_path):
    store=ArtifactStore(tmp_path/'run')
    original=store.write_bytes('unit/input.sol',b'abc')
    store.write_json('record.json',{'patch':Patch(1,1,b'',b'\xff','addition')})
    assert json.loads((store.path/'record.json').read_text())['patch']['replacement']['data']=='ff'
    for name in ['../escape','/tmp/escape']:
        with pytest.raises(ValueError):store.write_bytes(name,b'bad')
    with pytest.raises(FileExistsError):store.write_bytes('unit/input.sol',b'bad')
    with pytest.raises(FileExistsError):ArtifactStore(store.path)
    seal=store.seal({'profile':'production'},'commit',{'code.py':'digest'})
    assert seal['files']=={'record.json':sha256(store.path/'record.json'),'unit/input.sol':sha256(original)}
    assert seal['code_commit']=='commit'
    with pytest.raises(ValueError,match='sealed'):store.write_bytes('later',b'bad')
    assert original.read_bytes()==b'abc'
