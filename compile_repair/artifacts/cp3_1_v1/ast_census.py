"""Reacquire AST evidence for project entries without their own CP3 AST projection."""
from batch import *
from compile_repair.rules.environment import pragma_interval, FLOOR, CEILING
from compile_repair.toolchain.solc import load_trusted_compilers, version_tuple
from scripts.DFG.models import Unsupported

assert saved('authorization.json')['decision']=='D21'
compilers = load_trusted_compilers()[0]
versions = sorted((v for v in compilers if FLOOR<=version_tuple(v)<CEILING), key=version_tuple)
helptexts = {}
for v in versions:
    h=subprocess.run([compilers[v].path,'--help'],capture_output=True)
    helptexts[v]=h.stdout+h.stderr
units, refs = members()
direct=json.loads((LOCAL/'direct_ast.json').read_bytes())
missing=json.loads((LOCAL/'need_ast.json').read_bytes())
source_facts=json.loads((LOCAL/'source_ast.json').read_bytes())
run_members={}
empty=LOCAL/'ast_readonly_cwd'
empty.mkdir()
def manifest(path):
    run=path.parents[2]
    if run not in run_members:
        seal=run/'seal.json'
        if seal.is_file():
            run_members[run]=json.loads(seal.read_bytes())['files']
        else:
            pres=json.loads(committed(ART/'cp3_continue_v1/interrupted_segment_preservation.json'))
            assert pres['run_path']==str(run)
            run_members[run]={p:info['sha256'] for p,info in pres['files'].items()}
    return json.loads(verified(path,run_members[run][str(path.relative_to(run))]))
def ast_names(tree):
    if tree.get('nodeType')=='SourceUnit':
        return Counter(n['name'] for n in tree['nodes'] if n.get('nodeType')=='ContractDefinition')
    if tree.get('name')=='SourceUnit':
        return Counter(n['attributes']['name'] for n in tree['children'] if n.get('name')=='ContractDefinition')
    raise ValueError('Malformed AST')
rows={}
ast_cache={}
for uid, item in missing.items():
    ref=refs[uid]
    result_path=Path(ref['result_path'])
    old=json.loads(verified(result_path,ref['result_sha256']))
    project=manifest(result_path.with_name('project.json'))
    paths={str(Path(f['path']).relative_to(item['origin'])):f for f in item['inputs']}
    sources={name:verified(paths[rel]['path'],paths[rel]['sha256']) for name,rel in project['source_units']}
    ids={name:paths[rel]['sha256'] for name,rel in project['source_units']}
    allowed=[a['version'] for a in old['attempts'] if a.get('solc') and a['solc']['returncode']==0]
    if not allowed:
        try:
            bounds=pragma_interval(sources.values())
        except Unsupported:
            bounds=None
        allowed=[v for v in versions if bounds is None or bounds[0]<=version_tuple(v)<bounds[1]]
    v=max(allowed or versions,key=version_tuple)
    compiler=compilers[v]
    # Inline only the original source units in this closure. The output selection
    # requests AST only; newer solc can stop before resolving missing imports.
    settings={'outputSelection':{'*':{'':['ast']}}}
    if b'--stop-after' in helptexts[v]:
        settings['stopAfter']='parsing'
    if project.get('remappings'):
        settings['remappings']=project['remappings']
    cmd=[compiler.path,'--standard-json']
    if b'--no-import-callback' in helptexts[v]:
        cmd.append('--no-import-callback')
    # Standard JSON contains text. For non-UTF8, use the compiler's CLI AST option
    # on the original bytes instead of injecting replacement characters.
    try:
        doc={'language':'Solidity','settings':settings,'sources':{n:{'content':r.decode('utf8')} for n,r in sources.items()}}
        input_bytes=json.dumps(doc,ensure_ascii=False,sort_keys=True).encode()
        work=empty
    except UnicodeDecodeError:
        input_bytes=None;work=Path(item['origin'])
        target='./'+project['entry'] if project['entry'].startswith('-') else project['entry']
        cmd=[compiler.path,*project['remappings'],target,'--combined-json','ast','--allow-paths',str(work)]
    tick=time.monotonic()
    cp=subprocess.run(cmd,input=input_bytes,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=str(work),timeout=120)
    try:
        out=json.loads(cp.stdout)
    except (ValueError,UnicodeDecodeError):
        out={}
    facts={}
    for name,info in out.get('sources',{}).items():
        tree=info.get('ast',info.get('AST',info.get('legacyAST')))
        normalized=name[2:] if name.startswith('./') and name not in ids else name
        if tree and normalized in ids:
            counts=dict(ast_names(tree))
            if ids[normalized] in source_facts:
                assert source_facts[ids[normalized]]['definitions']==counts,uid
            facts[normalized]=counts
            ast_cache[ids[normalized]]=counts
    errors=[e.get('message','') for e in out.get('errors',[]) if isinstance(e,dict) and e.get('severity')=='error']
    row=dict(version=v,command=cmd,cwd=str(work),compiler_sha256=compiler.sha256,input_sha256=sha(input_bytes) if input_bytes else ids.get(project['entry']),output_sha256=sha(cp.stdout),rc=cp.returncode,first_error=(errors or cp.stderr.decode('utf8','replace').splitlines() or [None])[0],ast_sources=len(facts),time_seconds=time.monotonic()-tick,usd=0,source_ids=ids,definitions=facts)
    rows[uid]=row
    if len(rows)%500==0:print(len(rows),flush=True)
target=LOCAL/'ast_invocations.jsonl'
with target.open('x') as fp:
    for uid,row in rows.items():fp.write(json.dumps(dict(row,unit_id=uid))+'\n')
unknown=[];positive={};methods=Counter();present_count=0
for uid,row in rows.items():
    counts=Counter();absent=[]
    for name,digest in row['source_ids'].items():
        facts=row['definitions'].get(name, ast_cache.get(digest,source_facts.get(digest,{}).get('definitions')))
        if facts is None:absent.append(name)
        else:counts.update(facts)
    dup=sorted(k for k,v in counts.items() if v>1)
    if dup:positive[uid]=dup
    if absent:unknown.append(dict(unit_id=uid,missing=len(absent),established_duplicates=dup))
    if not absent:present_count+=1
    methods['own_ast_complete' if len(row['definitions'])==len(row['source_ids']) else 'partial_or_no_own_ast']+=1
positive.update({uid:r['duplicate_names'] for uid,r in direct.items() if r['duplicate_names']})
success=sum((direct.get(uid) or missing[uid])['status']=='success' for uid in positive)
save('ast_census.json',dict(projects=len(direct)+len(rows),existing_ast=len(direct),additional_ast_calls=len(rows),additional_known_complete=present_count,coverage=dict(methods),affected=positive,previously_successful=success,incomplete_units=unknown,additional_invocations=str(target),invocations_sha256=sha(target.read_bytes())))
print('affected',len(positive),'incomplete',len(unknown),'previous_success',success)
