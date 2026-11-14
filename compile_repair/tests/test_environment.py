"""CP1 policy tests: frozen matrix replay, general inputs and diagnostic gates."""
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from compile_repair.core.model import Compilation, Compiler
from compile_repair.rules.environment import (FEATURE_RULES, candidate_versions, code_only,
    infer_interval, make_plan, mando_known_version, ordered_candidates, pragma_interval,
    pragma_patches, select_version, settings_retry)
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import read_checked_json
from compile_repair.toolchain.solc import CP0_SHA256
from scripts.DFG.models import Unsupported

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ['0.4.11', '0.4.12', '0.4.17', '0.4.24', '0.4.25', '0.4.26', '0.5.0', '0.5.17', '0.8.0']


@pytest.mark.parametrize('pragmas,expected', [
    ('^0.4.11', ((0,4,11),(0,5,0))), ('~0.4.17', ((0,4,17),(0,5,0))),
    ('=0.4.17', ((0,4,17),(0,4,18))), ('>=0.4.12 <0.5.0', ((0,4,12),(0,5,0))),
    ('>0.4.12 <=0.4.17', ((0,4,13),(0,4,18)))])
def test_cp1_intervals(pragmas, expected):
    assert pragma_interval([('pragma solidity '+pragmas+'; contract C {}').encode()]) == expected


def test_unit_intersection_no_pragma_and_invalid_constraints():
    assert pragma_interval([b'contract C {}', b'pragma solidity ^0.4.12; pragma solidity >=0.4.17;']) == ((0,4,17),(0,5,0))
    assert pragma_interval([b'// pragma solidity 0.5.0;\ncontract C {}']) is None
    for sources in [[b'pragma solidity ^0.4.0 || ^0.5.0;'],
                    [b'pragma solidity 0.4.12;', b'pragma solidity 0.5.0;']]:
        with pytest.raises(Unsupported):
            pragma_interval(sources)


@pytest.mark.parametrize('known,first,flag', [
    ('0.4.24','0.4.24',None), ('0.5.0','0.4.12','known_version_outside_interval'),
    ('0.4.11','0.4.12','known_version_below_slither_floor'), (None,'0.4.12',None),
    ('0.4.18','0.4.12','known_version_unavailable')])
def test_known_version_constraints(known, first, flag):
    plan = make_plan([b'pragma solidity ^0.4.0; contract C {}'], VERSIONS, known)
    assert next(ordered_candidates(plan)) == first
    assert not plan.override
    if flag:
        assert flag in plan.flags


@pytest.mark.parametrize('rule,positive,negative', [
    ('throw_removed', b'contract C { function f() { throw; } }', b'contract C { function f() { revert(); } }'),
    ('var_removed', b'contract C { function f() { var a = 1; } }', b'contract C { uint a; }'),
    ('unchecked_introduced', b'contract C { function f() public { unchecked { uint a = 1; } } }', b'contract C { uint a; }')])
def test_every_documented_feature_positive_negative_comments_and_literals(rule, positive, negative):
    assert rule in {r['name'] for r in infer_interval([positive])[1]}
    assert rule not in {r['name'] for r in infer_interval([negative])[1]}
    masked = b'/* '+positive+b' */ contract C { string x = "'+positive+b'"; } // '+positive
    assert infer_interval([masked])[1] == ()
    found = next(r for r in FEATURE_RULES if r['name'] == rule)
    assert found['source'].startswith('https://docs.soliditylang.org/en/v') and found['entry']


def test_inference_flags_and_regression_configuration_only():
    source = b'contract C {}'
    normal = make_plan([source], VERSIONS)
    regression = make_plan([source], VERSIONS, regression='mando')
    assert normal.origin == 'no_pragma_guess' and normal.priority is None
    assert regression.priority == '0.4.25'
    assert normal.groups == regression.groups and normal.inference == regression.inference
    assert make_plan([b'contract C { function f() { throw; } }'], VERSIONS).origin == 'no_pragma_inferred'
    assert make_plan([b'contract C {}', b'pragma solidity ^0.5.0;'], VERSIONS).interval == ((0,5,0),(0,6,0))


def test_series_order_and_d3_failures_only_advance_after_exhaustion():
    plan = make_plan([b'pragma solidity >=0.4.24;'], VERSIONS)
    calls = []
    def probe(v):
        calls.append(v)
        return {'d3': v == '0.5.0'}
    assert select_version(plan, probe) == '0.5.0'
    assert calls == ['0.4.24','0.4.25','0.4.26','0.5.0']
    calls.clear()
    assert select_version(plan, lambda v: calls.append(v) or {'d3': True}) == '0.4.24'
    assert calls == ['0.4.24']
    desc = make_plan([b'pragma solidity >=0.4.24;'], VERSIONS, order='descending')
    assert list(ordered_candidates(desc))[:3] == ['0.4.26','0.4.25','0.4.24']


def test_pragma_override_eligibility_nearest_series_and_byte_positions():
    raw = '// 非 ASCII\r\npragma solidity\n 0.4.11; contract C {}\r\n'.encode()
    plan = make_plan([raw], VERSIONS)
    assert plan.override and list(ordered_candidates(plan)) == ['0.4.12','0.4.17','0.4.24','0.4.25','0.4.26']
    copy, evidence = apply_patches(raw, pragma_patches(raw))
    assert evidence.level == 'rewrite' and len(copy) == len(raw)
    assert copy.index(b'contract') == raw.index(b'contract')
    assert [i for i,v in enumerate(copy) if v in (10,13)] == [i for i,v in enumerate(raw) if v in (10,13)]
    assert copy[:raw.index(b'pragma')] == raw[:raw.index(b'pragma')]
    assert not make_plan([b'pragma solidity ^0.4.11;'], VERSIONS).override
    absent = make_plan([b'pragma solidity 0.5.10;'], ['0.4.26','0.6.0'])
    assert list(ordered_candidates(absent)) == []  # never crosses the minor boundary
    near = make_plan([b'pragma solidity 0.5.10;'], ['0.5.8','0.5.11','0.5.9'])
    assert list(ordered_candidates(near)) == ['0.5.9','0.5.11','0.5.8']


def test_filename_directory_and_comment_changes_cannot_select_versions(tmp_path):
    raw = b'pragma solidity >=0.4.24 <0.6.0; contract C {}'
    plans = []
    for folder, filename in [('safe','0.8.38.sol'), ('buggy','known0.4.11.sol')]:
        path = tmp_path/folder/filename
        path.parent.mkdir()
        path.write_bytes(raw)
        plans.append(make_plan([path.read_bytes()], VERSIONS))
    assert plans[0] == plans[1] == make_plan([raw+b' // unchecked { throw; var x = 1;'], VERSIONS)


def test_frozen_846_ascending_descending_without_compiling(tmp_path):
    cp0 = read_checked_json(ROOT/'compile_repair/artifacts/cp0_v2/recon.json', CP0_SHA256)
    assert len(cp0['compilers']) == 37 and len(cp0['inputs']) == 846
    rows = []
    for row in cp0['inputs']:
        source = (ROOT/row['path']).read_bytes()
        assert hashlib.sha256(source).hexdigest() == row['sha256']
        def probe(v):
            observed = row['selection']['observed_d3_versions']
            assert v in row['matrix']
            if row['matrix'][v]['returncode'] == 0:
                # Never infer unobserved interior Slither outcomes from solc rc0.
                assert v in observed or v in row.get('selected_slither', {}).get('failed_versions', [])
            return {'d3': row['matrix'][v]['returncode'] == 0 and v in observed}
        actual = {}
        for order in ('ascending', 'descending'):
            known = row['metadata']['version'] if row['metadata'] else None
            plan = make_plan([source], cp0['compilers'], known, 'mando', order)
            actual[order] = select_version(plan, probe)
            assert actual[order] == row['selection'][order], row['path']
        rows.append({'path': row['path'], 'sha256': row['sha256'], **actual})
    (tmp_path/'offline_replay.json').write_text(json.dumps(rows,indent=2))


def test_settings_gate_uses_exact_error_version_and_location():
    source = b'contract C { function f() public { blobhash(1); } }'
    column = source.index(b'blobhash') + 1
    stderr = 'Error: Undeclared identifier. Did you mean "blockhash"?\n --> /ignored/path.sol:1:%d:\n' % column
    result = Compilation('/irrelevant','x',Compiler('0.8.24','x','x'),[],'.',1,stderr.splitlines()[0],stderr,'',0,False)
    assert settings_retry(result,source)['settings'] == ('--evm-version','cancun')
    assert settings_retry(replace(result,settings=('--evm-version','cancun')),source) is None
    assert settings_retry(replace(result,compiler=Compiler('0.8.23','x','x')),source) is None
    assert settings_retry(replace(result,stderr='Error: something else'),source) is None
    assert settings_retry(result,source.replace(b'blobhash',b'notfound')) is None
    assert settings_retry(result,b'//'+source) is None
    assert settings_retry(replace(result,returncode=0),source) is None
