"""Append only after successful plan verification; preserve historic prefixes."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
base=out.parent/'batch_NA_v1'
v=json.loads((base/'verification.json').read_text())
a=json.loads((base/'preparation_audit.json').read_text())
r=json.loads((base/'resource_estimate.json').read_text())
assert v['passed'] and v['jobs']==240 and v['formal_fits']==0
assert len(a['structure_proofs'])==32 and len(a['original_token_checks'])==16 and not a['cuda_initialized']
values={'@@MIN@@':format(v['preparation_seconds']/60,'.1f'),'@@SHA@@':hashlib.sha256((base/'plan.json').read_bytes()).hexdigest(),'@@LOW@@':format(r['nominal_total_hours'][0],'.2f'),'@@HIGH@@':format(r['nominal_total_hours'][1],'.2f')}
def render(name):
 s=(out/name).read_text(encoding='utf8')
 for k,val in values.items():s=s.replace(k,val)
 assert '@@' not in s
 return s
before=json.loads((out/'before.json').read_text())
for name,entry in before['documents'].items():
 b=(root/name).read_bytes()
 assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'],name
with (root/'scripts/node_sem/NS_P5_REPORT.md').open('x',encoding='utf8',newline='\n') as f:f.write(render('report.template.md'))
for name,template in [('HANDOVER.md','handover.template.md'),('docs/training_changes_2026-10-07.md','detail.template.md'),('scripts/node_sem/PROGRESS.md','progress.template.md')]:
 with (root/name).open('a',encoding='utf8',newline='\n') as f:f.write('\n\n'+render(template))
with (out/'documentation.json').open('x',encoding='utf8') as f:json.dump(dict(values=values,appended_only=True,author='Codex'),f,indent=2);f.write('\n')
print('Wrote report and appended three documents')
