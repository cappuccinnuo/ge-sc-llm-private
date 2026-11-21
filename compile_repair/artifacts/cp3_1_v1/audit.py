"""Verify protected inputs, prior seals, toolchains and complete release measurements."""
from batch import *
import ast, difflib, gzip
from scripts.DFG.dfg_v2.experiment.run import _code_refs
base=json.loads(committed(ART/'cp3_continue_v1/baseline.json'))
frozen=base['old_sealed_reference']
prior=json.loads(verified(ROOT/frozen['path'],frozen['sha256']))['old_sealed']
for path,h in prior.items():verified(ROOT/path,h)
protected=Counter()
for mf in (ART/'cp3_v1/acquisition').glob('*/manifest.jsonl.gz'):
    with gzip.open(mf,'rt') as f:
        for line in f:
            row=json.loads(line);verified(row['absolute_path'],row['sha256']);protected['acquired_corpus_files']+=1
for row in json.loads(committed(ART/'cp3_v1/document_manifest.json'))['files']:
    verified(row['destination'],row['sha256']);protected['official_documents']+=1
for name,before in base['environment'].items():
    prefix=Path('/home/zhao/miniconda3/envs')/name
    paths=set(prefix.glob('lib/python*/site-packages/*.dist-info/METADATA'))
    paths.update(prefix.glob('conda-meta/*.json'));paths.add(prefix/'conda-meta/history')
    assert {str(p):sha(p.read_bytes()) for p in paths if p.is_file()}==before,name
    protected[name+'_metadata']=len(before)
bins={str(p):sha(p.read_bytes()) for p in (Path.home()/'.solc-select').rglob('*') if p.is_file()}
assert bins==base['solc']
assert {k:os.environ.get(k) for k in base['selection_environment']}==base['selection_environment']
assert _code_refs()==base['code_refs']
protected.update(solc_files=len(bins),dfg_code_refs=len(base['code_refs']),old_sealed_files=len(prior))
native=json.loads(committed(ART/'cp3_continue_v1/alias_binding_review_request.json'))['installed_source_evidence']
verified(native['path'],native['sha256'])
updated=['toolchain/project.py','toolchain/slither.py','rules/environment.py','pipeline.py','evaluation/report.py']
files={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in MOD.rglob('*.py') if not {'artifacts','tests'}&set(p.relative_to(MOD).parts)}
assert len(files)==16
def lines_by_def(source):
    result={n:'module' for n in range(len(source.splitlines()))}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for n in range(node.lineno-1,node.end_lineno):result[n]=node.name
    return result
# Function-level line attribution uses the system Python AST (3.10).
changed={}
for rel in updated:
    rel='compile_repair/'+rel
    old=subprocess.check_output(['git','show','61c94e00:'+rel]).decode()
    new=(ROOT/rel).read_text()
    oldlines,newlines=old.splitlines(),new.splitlines()
    om,nm=lines_by_def(old),lines_by_def(new)
    counts=defaultdict(Counter)
    for op,a,z,c,e in difflib.SequenceMatcher(None,oldlines,newlines,autojunk=False).get_opcodes():
        if op=='equal':continue
        for i in range(a,z):counts[om[i]]['removed']+=1
        for i in range(c,e):counts[nm[i]]['added']+=1
    changed[rel]=dict(counts)
# Verify both original oracle journals and identify every syntax rejection explicitly.
orcl=saved('pragma_oracle.json')
logs=[(LOCAL/'pragma_oracle/invocations.jsonl',saved('pragma_syntax_request.json')['log_sha256']),
      (Path(orcl['invocations']),orcl['invocations_sha256'])]
pairs=set();syntax=Counter();accepted=Counter()
dest=B/'matrix_invocations.jsonl.gz'
with dest.open('xb') as fo,gzip.GzipFile(filename='',mode='wb',fileobj=fo,mtime=0) as gz:
    for path,h in logs:
        for ln in verified(path,h).splitlines():
            row=json.loads(ln);key=row['expression'],row['version'];assert key not in pairs;pairs.add(key)
            if row['returncode']==0:accepted['accepted']+=1
            elif row['requires_different_version']:accepted['version_rejection']+=1
            else:
                accepted['syntax_rejection']+=1
                syntax[row['first_error'] if 'first_error' in row else row['error_first_line'].split('Error:')[-1].strip()]+=1
            gz.write(ln+b'\n')
assert len(pairs)==82*92 and accepted['syntax_rejection']==360
probes=[]
for folder in (LOCAL/'tests_final_production').glob('test_duplicate_names_retain_d3*'):
    if folder.is_symlink():continue
    path=folder/'alias/units/alias/result.json'
    if not path.exists():continue
    record=json.loads(path.read_bytes())
    a=record['attempts'][0];facts=a['slither']
    probes.append(dict(sha256=sha(path.read_bytes()),version=a['version'],d3=facts['d3'],d3_a=facts['d3_a'],d3_b=facts['d3_b'],bindings_checked=facts['project_binding']['checked'],graph_usable=facts['graph_usable'],reason=facts['graph_unusable_reason'],names=facts['duplicate_contract_names'],written_graph=path.with_name('graph.json').exists(),path=str(path)))
assert len(probes)==4 and all(p['d3'] and not p['graph_usable'] and not p['written_graph'] for p in probes)
save('scope_audit.json',dict(passed=True,protected=dict(protected),native_parser_sha256=native['sha256'],
        production_count=len(files),production_sha256=files,changed_functions=changed,oracle_outcomes=accepted,
        oracle_syntax=syntax,oracle_distinct_pairs=len(pairs),duplicate_fixture_probes=probes))
print('audit passed',dict(protected),'matrix outcomes',dict(accepted))
