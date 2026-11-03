from pathlib import Path
import json,hashlib
base=Path('scripts/node_sem/artifacts/ns_p4')
s=json.loads((base/'summary.json').read_text())
parts=json.loads((base/'report_sections.json').read_text())
text=parts['intro']
text+='\n| Config | D | Parameters | Construct s | Fit/check s | Train loss | Inner val loss | Tensor subtotal MiB |\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for r in s['cpu']:
 text+='| {} | {} | {} | {:.2f} | {:.2f} | {:.6f} | {:.6f} | {:.2f} |\n'.format(r['name'],r['carrier_dim'],r['parameters'],r['constructor_seconds'],r['fit_seconds'],r['train_loss'],r['inner_val_loss'],r['tensor_subtotal_mib'])
text+='\n8H measured construction: {:.3f}s. S4 exceeds 3x: {}.\n'.format(s['h8_constructor_seconds'],next(r['constructor_over_3x_h8'] for r in s['cpu'] if r['name']=='S4'))
text+=parts['afterCpu']
text+='| Config | Resource gate passed | Peak allocated MiB | Peak reserved MiB | Minimum free MiB |\n|---|---|---:|---:|---:|\n'
for r in s['gpu']:
 q=r.get('resources',{})
 text+='| {} | {} | {} | {} | {} |\n'.format(r['name'],r['resource_gate_passed'],q.get('peak_allocated_mib','not run'),q.get('peak_reserved_mib','not run'),q.get('minimum_free_mib','not run'))
for r in s['gpu']:
 if r.get('failure'): text+='\n'+r['name']+' stopped: '+r['failure']['error']+'\n'
gpu=sum(r.get('resource_gate_passed',False) for r in s['gpu'])
text+='\nGPU accepted: {}/2; formal fits: 0.\n'.format(gpu)
text+=parts['ending']
with Path('scripts/node_sem/NS_P4_REPORT.md').open('x',encoding='utf-8') as f:f.write(text)
old=json.loads((base/'started.json').read_text())['docs']
gpu_note='\nGPU resource probes accepted {}/2. '.format(gpu)
for r in s['gpu']:
 q=r.get('resources',{})
 gpu_note+=r['name']+': min_free='+str(q.get('minimum_free_mib','not run'))+' MiB; '
 if r.get('failure'):gpu_note+='stopped: '+r['failure']['error']+'; '
gpu_note=gpu_note.rstrip()+'\n\n'
progress='\n\n## 2026-11-03 NS-P4 '+parts['title']+'\n\n'+parts['brief']+gpu_note+parts['tail']
handover='\n\n### 2026-11-03 NodeSem NS-P4 '+parts['title']+'\n\n'+parts['brief']+gpu_note+parts['tail']
detail='\n\n## 82. NS-P4 '+parts['title']+' (2026-11-03)\n\n'+text.split('\n',1)[1]
for i in range(1,7):detail=detail.replace('## '+str(i)+'.','### 82.'+str(i)+'.')
for name,addition in [('scripts/node_sem/PROGRESS.md',progress),('HANDOVER.md',handover),('docs/training_changes_2026-10-07.md',detail)]:
 p=Path(name);raw=p.read_bytes()
 assert len(raw)==old[name]['bytes'] and hashlib.sha256(raw).hexdigest()==old[name]['sha256']
 with p.open('ab') as f:f.write(addition.encode('utf-8'))
print('Written NS_P4_REPORT and appended three records.')
