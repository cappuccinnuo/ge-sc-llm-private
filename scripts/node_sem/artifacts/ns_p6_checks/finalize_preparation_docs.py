"""Finalize NS-P6 preparation documentation only after all sealed checks pass."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
BASE=ROOT/'scripts/node_sem'
CHECK=BASE/'artifacts/ns_p6_checks'
BATCH=BASE/'artifacts/batch_NB_v1'

def read(p): return json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def reference(p): return dict(path=str(p),sha256=sha(p))
def new_json(p,v):
    with p.open('x',encoding='utf8') as f: json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def new_text(p,v):
    with p.open('x',encoding='utf8') as f:f.write(v)
def append(p,text,prefix):
    data=p.read_bytes()
    if len(data)!=prefix['bytes'] or hashlib.sha256(data).hexdigest()!=prefix['sha256']:
        raise ValueError('Documentation changed concurrently: '+str(p))
    with p.open('ab') as f:f.write(text.encode('utf8'))

def main():
    plan=read(BATCH/'plan.json');seal=read(BATCH/'plan.seal.json')
    verification=read(BATCH/'verification.json');audit=read(BATCH/'preparation_audit.json')
    regressions=read(CHECK/'regressions_final.json');frozen=read(CHECK/'frozen_runtime_verification.json')
    assert seal['plan']==reference(BATCH/'plan.json')
    assert verification['passed'] and verification['jobs']==120 and verification['formal_fits']==0
    assert audit['passed'] and audit['zero_step_states']==120 and audit['optimizer_steps']==0
    assert audit['cuda_initialized'] is False and len(audit['structure_proofs'])==16
    assert len(audit['fast_carrier_proofs'])==16
    assert regressions['total_passed']==3801 and regressions['total_failed']==0 and regressions['total_skipped']==0
    assert frozen['passed'] and frozen['frozen_runtime_files']==354
    assert not (BATCH/'authorization.json').exists() and not (BATCH/'execution_revision.json').exists()
    assert plan['execution_authorized'] is False
    assert not (BATCH/'prepare.failure.json').exists()
    assert len(list(BATCH.glob('prepared/**/initial.pt')))==120
    assert len(list(BATCH.glob('runs/**/receipt.json')))==0
    for p in audit['structure_proofs']+audit['fast_carrier_proofs']:
        assert sha(Path(p['path']))==p['sha256'] and read(Path(p['path']))['passed']
    # Keep prior document bytes, plans and logs; only append/new files.
    prefixes=read(CHECK/'document_prefixes.json')
    for path,record in prefixes.items():
        assert sha(ROOT/path)==record['sha256'] and (ROOT/path).stat().st_size==record['bytes']
    with (BATCH/'regressions.json').open('xb') as f:f.write((CHECK/'regressions_final.json').read_bytes())
    resources=read(BATCH/'resource_estimate.json')
    sections=read(CHECK/'delivery_text.json')
    groups={}
    for j in plan['jobs']:
        k=(j['task_id'],j['profile'],j['name'])
        groups[k]=dict(dim=j['carrier_dim'],parameters=j['parameters'],layers=0 if j['name']=='S4-noG' else j['config']['layers'])
    table='| task | graph | config | carrier dim | layers | parameters |\n|---|---|---|---:|---:|---:|\n'
    for (task,profile,name),r in sorted(groups.items()):
        table+='| {} | {} | {} | {} | {} | {} |\n'.format(task,profile,name,r['dim'],r['layers'],r['parameters'])
    fingerprints={str(i):j['original_graph_fingerprint'] for i,j in enumerate(plan['jobs'])}
    disk=dict(files=0,bytes=0,initial_bytes=0,carrier_bytes=0)
    for p in BATCH.rglob('*'):
        if p.is_file():
            size=p.stat().st_size;disk['files']+=1;disk['bytes']+=size
            if p.suffix=='.pt':disk['initial_bytes']+=size
            if p.suffix=='.npz':disk['carrier_bytes']+=size
    values=dict(plan_sha=sha(BATCH/'plan.json'),seal_sha=sha(BATCH/'plan.seal.json'),
        minutes=round(verification['preparation_seconds']/60,2),
        hours_low=round(resources['total_hours'][0],2),hours_high=round(resources['total_hours'][1],2),
        runtime_files=len(plan['runtime']),table=table,
        disk_gib=round(disk['bytes']/1024**3,3),heavy_gib=round((disk['initial_bytes']+disk['carrier_bytes'])/1024**3,3))
    def fill(text):
        for k,v in values.items(): text=text.replace('{{'+k+'}}',str(v))
        return text
    new_text(BASE/'NS_P6_REPORT.md',fill(sections['report']))
    append(BASE/'PROGRESS.md',fill(sections['progress']),prefixes['scripts/node_sem/PROGRESS.md'])
    append(ROOT/'HANDOVER.md',fill(sections['handover']),prefixes['HANDOVER.md'])
    append(ROOT/'docs/training_changes_2026-10-07.md',fill(sections['training']),prefixes['docs/training_changes_2026-10-07.md'])
    new_json(CHECK/'delivery_verification.json',dict(passed=True,plan=reference(BATCH/'plan.json'),
        seal=reference(BATCH/'plan.seal.json'),initials=120,groups=16,historical_receipts=240,
        regressions=reference(BATCH/'regressions.json'),frozen_runtime=reference(CHECK/'frozen_runtime_verification.json'),
        training_fits=0,cuda_initialized=False,execution_authorized=False,
        artifact_sizes=disk,document_prefixes=prefixes,
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    print(json.dumps(values,ensure_ascii=True))
if __name__=='__main__':main()
