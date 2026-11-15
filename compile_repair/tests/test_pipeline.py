"""CP1 orchestration, strict D3 continuation and real settings repair tests."""
import hashlib
import io
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from compile_repair.cli import main
from compile_repair.core.model import Compilation, CompilationUnit, Compiler, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair, repair_unit
from compile_repair.rules.environment import make_plan, ordered_candidates
from compile_repair.tests.test_production import FEATURES, production_required, trusted_compilers


def unit_for(raw, path='arbitrary.sol', known=None, regression=None):
    return CompilationUnit('test_input',(SourceFile(path,hashlib.sha256(raw).hexdigest(),raw),),known,regression)


def run_fake(tmp_path, raw, solc_ok, d3_ok, versions=('0.4.12','0.4.17','0.5.0'), error='D3(a) incomplete'):
    compilers={v:Compiler(v,'/unused/'+v,'unused') for v in versions}
    events=[]
    def compile_fn(path, compiler, settings=()):
        events.append(('solc',compiler.version,settings))
        success=solc_ok(compiler.version)
        return Compilation(str(path),hashlib.sha256(path.read_bytes()).hexdigest(),compiler,[],str(tmp_path),
                           0 if success else 1,None if success else 'Error: rejected','' if success else 'Error: rejected',
                           '',0,False,settings=settings)
    def slither_fn(compilation, profile):
        assert profile=='production'
        events.append(('slither',compilation.compiler.version,compilation.settings))
        ok=d3_ok(compilation.compiler.version)
        return {'d3':ok,'profile':profile,'d3_a':ok,'d3_b':ok,'error_first_line':None if ok else error,
                'exception_type':None if ok else 'FixtureD3Failure',
                'graph':{'schema':'compile-repair-graph-v1','declarations':[],'nodes':[], 'cfg_edges':[], 'calls':[]},
                'nodes':[{'key5':['C','f()','ENTRYPOINT',0,1],'length':1,'ir':[],'declaration_kind':'function'}] if ok else []}
    store=ArtifactStore(tmp_path/'run')
    record=repair_unit(unit_for(raw),compilers,store,io.StringIO(),compile_fn=compile_fn,slither_fn=slither_fn)
    return record,events,store


@pytest.mark.parametrize('diagnostic',['missing_filename','missing_start','contract_mismatch','ir_object_repr_unresolved'])
def test_pipeline_continues_on_each_d3_failure(tmp_path, diagnostic):
    record,events,_=run_fake(tmp_path,b'pragma solidity ^0.4.12; contract C {}',lambda v:True,
                            lambda v:v=='0.4.17',error=diagnostic)
    assert record.selected_version=='0.4.17'
    assert events==[('solc','0.4.12',()),('slither','0.4.12',()),('solc','0.4.17',()),('slither','0.4.17',())]
    assert record.attempts[0]['slither']['error_first_line']==diagnostic
    assert record.provenance['arbitrary.sol'].level=='none'


@pytest.mark.parametrize('solc_ok,expected',[(False,'all_solc_candidates_failed'),(True,'slither_side_failure')])
def test_failed_candidates_do_not_override_declared_pragma(tmp_path, solc_ok, expected):
    record,_,_=run_fake(tmp_path,b'pragma solidity ^0.4.12; contract C {}',lambda v:solc_ok,lambda v:False)
    assert record.status=='unrepaired' and record.reason==expected
    assert 'pragma_overridden' not in record.flags and 'crossed_minor' not in record.flags
    assert [a['version'] for a in record.attempts]==['0.4.12','0.4.17']


def test_no_candidate_never_crosses_series_for_override(tmp_path):
    record,events,_=run_fake(tmp_path,b'pragma solidity 0.6.0; contract C {}',lambda v:True,lambda v:True)
    assert record.reason=='no_candidate_compiler' and events==[]


def test_crossed_minor_only_after_first_series_failures(tmp_path):
    record,events,_=run_fake(tmp_path,b'pragma solidity >=0.4.12; contract C {}',lambda v:v=='0.5.0',lambda v:True)
    assert record.selected_version=='0.5.0' and 'crossed_minor' in record.flags
    assert [e[1] for e in events if e[0]=='solc']==['0.4.12','0.4.17','0.5.0']
    assert [a['crossed_minor'] for a in record.attempts]==[False,False,True]


def test_pragma_override_work_copy_is_auditable(tmp_path):
    raw=b'pragma solidity 0.4.11; contract C {}'
    record,_,store=run_fake(tmp_path,raw,lambda v:True,lambda v:True)
    assert record.selected_version=='0.4.12' and 'pragma_overridden' in record.flags
    evidence=record.provenance['arbitrary.sol']
    assert evidence.level=='rewrite' and evidence.changes[0].old==b'pragma solidity 0.4.11;'
    assert (store.path/'units/test_input/input.sol').read_bytes()==raw
    assert len((store.path/'units/test_input/pragma_overridden.sol').read_bytes())==len(raw)
    nodes=json.loads((store.path/'units/test_input/nodes.json').read_text())['nodes']
    assert nodes[0]['provenance']=='rewritten'


def test_directory_cli_nonzero_and_no_output(tmp_path, capsys):
    with pytest.raises(SystemExit) as failure:
        main(['repair',str(tmp_path),'--output',str(tmp_path/'output')])
    assert failure.value.code!=0 and '暂不支持' in capsys.readouterr().err
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize('fixture,pragma,version,settings',[
    ('h0824_blob.sol','0.8.24','0.8.24',('--evm-version','cancun')),
    ('y0824_blob_asm.sol','0.8.24','0.8.24',('--evm-version','cancun')),
    ('y0824_mcopy.sol','0.8.24','0.8.24',('--evm-version','cancun')),
    ('y0824_tstore_asm.sol','0.8.24','0.8.24',('--evm-version','cancun')),
    ('h0826_require_error.sol','0.8.26','0.8.26',('--via-ir',)),
    ('h0824_blob.sol','^0.8.24','0.8.24',('--evm-version','cancun'))])
def test_real_same_version_setting_retry_before_higher_compiler(tmp_path,fixture,pragma,version,settings):
    production_required()
    raw=re.sub(rb'pragma solidity[^;]+;',('pragma solidity '+pragma+';').encode(),(FEATURES/fixture).read_bytes(),count=1)
    store=ArtifactStore(tmp_path/'real')
    with store.journal('invocations.jsonl') as journal:
        record=repair_unit(unit_for(raw),trusted_compilers(),store,journal)
    assert record.status=='success' and record.selected_version==version
    assert record.settings==settings and record.provenance['arbitrary.sol'].level=='none'
    assert [(a['version'],a['settings']) for a in record.attempts]==[(version,()),(version,settings)]
    assert record.attempts[0]['solc']['returncode']!=0
    assert record.attempts[1]['slither']['settings']==settings
    assert record.attempts[1]['settings_retry']['trigger_error']==record.attempts[0]['solc']['error_first_line']
    store.seal({'profile':'production'},'test')


def test_cli_multiple_files_and_snippet_share_production_entry(tmp_path):
    production_required()
    raw=b'pragma solidity 0.4.12; contract C { function f() public returns(uint) { return 1; } }'
    a,b,snippet=tmp_path/'a.sol',tmp_path/'b.sol',tmp_path/'snippet.txt'
    for p in (a,b,snippet):p.write_bytes(raw)
    output=tmp_path/'batch'
    assert main(['repair',str(a),str(b),'--snippet',str(snippet),'--known-version','0.4.12',
                 '--order','ascending','--output',str(output)])==0
    records=[json.loads(x) for x in (output/'manifest.jsonl').read_text().splitlines()]
    assert len(records)==3 and all(r['selected_version']=='0.4.12' for r in records)
    assert all(r['attempts'][0]['slither']['profile']=='production' for r in records)
    assert all(p.read_bytes()==raw for p in (a,b,snippet))
    assert (output/'seal.json').exists()
