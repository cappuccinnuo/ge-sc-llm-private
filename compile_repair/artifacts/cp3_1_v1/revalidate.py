"""Replace just the union of the three CP3.1 impact sets, once per unit."""
from batch import *
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore,emit
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import ProjectIndex,resolve_project
from compile_repair.toolchain.solc import load_trusted_compilers
from compile_repair.toolchain.slither import check_profile
from compile_repair.evaluation.report import classify_record,primary_causes

units,refs=members()
groups={'input_format':set(saved('wrapper_scan.json')['hits']),
        'pragma':set(saved('pragma_equivalence.json')['newly_evaluable_units']),
        'duplicate':set(saved('ast_census.json')['affected'])}
selection=set.union(*groups.values())
assert saved('pragma_matrix_check.json')['passed'] and saved('ast_coverage_authorization.json')['approved']
compilers,_,trust=load_trusted_compilers()
profile=check_profile('production')
store=ArtifactStore(LOCAL/'replacements')
implementation={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in MOD.rglob('*.py') if not {'artifacts','tests'}&set(p.relative_to(MOD).parts)}
assert len(implementation)==16
store.write_json('order.json',sorted(selection))
cache={};replaced={};calls=Counter(); started=time.monotonic()
with store.journal('invocations.jsonl') as journal,store.journal('manifest.jsonl') as manifest:
    for item in units:
        uid=item['unit_id']
        if uid not in selection:continue
        assert uid not in replaced and item['corpus']!='MANDO'
        old_ref=refs[uid]
        old=json.loads(verified(old_ref['result_path'],old_ref['result_sha256']))
        raw=verified(item['path'],item['entry_sha256'])
        root=item['project_root'];project=None
        if root:
            if root not in cache:cache[root]=ProjectIndex(root)
            project=resolve_project(root,item['path'],index=cache[root])
            sources=project.files
        else:sources=(SourceFile(item['path'],item['entry_sha256'],raw,item['kind']),)
        unit=CompilationUnit(uid,sources)
        tick=time.monotonic()
        result=repair_unit(unit,compilers,store,journal,project=project)
        emit(manifest,result)
        path=store.path/'units'/uid/'result.json';new=json.loads(path.read_bytes())
        assert old['inputs']==new['inputs'],uid
        assert not (result.status=='success' and not (path.parent/'graph.json').is_file()),uid
        if uid in groups['input_format']:
            assert result.reason=='standard_json_input' and [a['stage'] for a in result.attempts]==['input_format']
        if uid in groups['pragma']:
            assert 'unsupported_version_constraints' not in result.flags,uid
        if uid in groups['duplicate']:
            assert result.status!='success' and not (path.parent/'graph.json').exists(),uid
        failures=classify_record(new)
        for a in result.attempts:
            calls['solc']+=int(a.get('solc') is not None);calls['slither']+=int(a.get('slither') is not None)
        replaced[uid]=dict(old=old_ref,new=dict(result_path=str(path),result_sha256=sha(path.read_bytes())),
                impact=[k for k,v in groups.items() if uid in v],elapsed_seconds=time.monotonic()-tick,
                corpus=item['corpus'],entry_sha256=item['entry_sha256'],old_status=old['status'],status=result.status,reason=result.reason,
                primary=primary_causes(new,failures),any_categories=sorted({f['category'] for f in failures}))
        if len(replaced)%50==0:print(len(replaced),flush=True)
assert set(replaced)==selection
seal=store.seal(dict(profile,compilers={v:asdict(c) for v,c in compilers.items()}),subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),implementation)
save('replacement_provenance.json',dict(impact={k:len(v) for k,v in groups.items()},count=len(replaced),calls=dict(calls),elapsed_seconds=time.monotonic()-started,rows=replaced,seal_path=str(store.path/'seal.json'),seal_sha256=sha((store.path/'seal.json').read_bytes())))
print('complete',len(replaced),dict(calls),Counter(r['status'] for r in replaced.values()))
