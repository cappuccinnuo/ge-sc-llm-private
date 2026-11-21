"""At most three local-only premise probes, outside the formal replacement runs."""
from batch import *
from compile_repair.toolchain.project import resolve_project, ProjectIndex, compile_project, standard_json_input
from compile_repair.toolchain.slither import run_slither,check_profile
from compile_repair.toolchain.solc import load_trusted_compilers,version_tuple
from compile_repair.rules.environment import pragma_interval,FLOOR,CEILING
from pathlib import PurePosixPath
from scripts.DFG.models import Unsupported
compilers,_,_=load_trusted_compilers()
profile=check_profile('production')
units,refs=members()
hits=saved('wrapper_scan.json')['hits']
indexed={i['unit_id']:i for i in units}
selected=['cp3_23864']
for uid in sorted(hits,key=lambda u:(indexed[u]['entry_sha256'],u)):
    if all(indexed[u]['entry_sha256']!=indexed[uid]['entry_sha256'] for u in selected):
        selected.append(uid)
    if len(selected)==3:break
details=[]
for uid in selected:
    item=indexed[uid]
    raw=verified(item['path'],item['entry_sha256'])
    obj=raw.strip()
    if obj.startswith(b'{{') and obj.endswith(b'}}'):obj=obj[1:-1]
    parsed=json.loads(obj)
    info=standard_json_input(raw)
    sources=parsed['sources'] if 'sources' in parsed and sorted(parsed['sources'])==info['source_names'] else parsed
    folder=LOCAL/'wrapper_premises'/uid
    folder.mkdir(parents=True)
    for name,entry in sources.items():
        dest=folder/name
        if not name or PurePosixPath(name).is_absolute() or any(part in ('.','..','') for part in name.split('/')) or '\\' in name or folder not in dest.resolve().parents:
            raise ValueError('Unsafe archive member '+uid)
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(entry['content'].encode())
    index=ProjectIndex(folder)
    if uid=='cp3_23864':
        known=json.loads(committed(ART/'cp3_review_v1/wrapper_unpack_probe.json'))
        project=resolve_project(folder,known['entry'],index=index)
        versions=['0.8.24','0.8.38']
    else:
        projects=[resolve_project(folder,path,index=index) for path in index.entries]
        if not projects:
            details.append(dict(unit_id=uid,source_count=len(sources),outcome='no .sol entry'));continue
        project=sorted(projects,key=lambda p:(bool(p.issues),-len(p.files),p.entry))[0]
        try:bounds=pragma_interval([s.content for s in project.files])
        except Unsupported:bounds=None
        available=[v for v in compilers if FLOOR<=version_tuple(v)<CEILING and (bounds is None or bounds[0]<=version_tuple(v)<bounds[1])]
        versions=[max(available,key=version_tuple)] if available else []
    row=dict(unit_id=uid,source_sha256=item['entry_sha256'],source_count=len(sources),entry=project.entry,closure=len(project.files),issues=len(project.issues),calls=[])
    for v in versions:
        c=compile_project(project,compilers[v])
        a=run_slither(c,profile='production',project=project) if c.returncode==0 else None
        row['calls'].append(dict(version=v,solc_rc=c.returncode,command=c.command,solc_sha256=c.compiler.sha256,solc_seconds=c.elapsed_seconds,error_first_line=c.error_first_line,constructed=a['constructed'] if a else None,d3=a['d3'] if a else None,graph_usable=a['graph_usable'] if a else None,slither_command=a['command'] if a else None,slither_seconds=a['elapsed_seconds'] if a else None,slither_error=a['error_first_line'] if a else None,cost_usd=0))
    details.append(row)
save('wrapper_premises.json',dict(selection='review example, followed by two distinct inputs in ascending SHA order',formal_results=False,cases=details,profile=profile))
print([(r['unit_id'],[(a['version'],a['solc_rc'],a['constructed']) for a in r.get('calls',[])]) for r in details])
