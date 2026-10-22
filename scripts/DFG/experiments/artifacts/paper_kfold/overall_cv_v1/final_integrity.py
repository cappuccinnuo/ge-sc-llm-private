from pathlib import Path
import hashlib,json,datetime,subprocess,sys
B=Path(__file__).resolve().parent
R=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
O=Path('/home/zhao/SmartContract/ge-sc-llm')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
report=json.loads((B/'report.json').read_text())
assert report['status']=='complete' and report['formal_fits']==60
assert (B/'OVERALL_CV_RESULT_REPORT.md').exists()
before=json.loads((B/'protected_before.json').read_text());records=[]
for name,info in before.items():
 p=Path(name)
 if info['rule']=='unchanged':good=sha(p)==info['sha256']
 else:
  data=p.read_bytes();good=len(data)>=info['bytes'] and hashlib.sha256(data[:info['bytes']]).hexdigest()==info['sha256']
 records.append(dict(path=name,rule=info['rule'],passed=good,sha256=sha(p)))
assert all(x['passed'] for x in records),[x for x in records if not x['passed']]
heads={}
for root,expected in [(R,'021a6f55ac9e3f94fc70feb441ff48b51b6a92ea'),(O,'f3dfc17908029355c5fc45d6d3932f203068fcf5')]:
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(root)).decode().strip();assert head==expected;heads[str(root)]=head
write(B/'protected_after.json',dict(status='passed',checked=len(records),unchanged_files=sum(x['rule']=='unchanged' for x in records),append_only_documents=sum(x['rule']=='append_only' for x in records),heads=heads,files=records))
files=[p for p in (R/'scripts/DFG/experiments/overall_cv').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='.execution.lock']
files += [p for p in B.rglob('*') if p.is_file() and p.name not in ('delivery_manifest.json','.execution.lock')]
write(B/'delivery_manifest.json',dict(created_at=datetime.datetime.utcnow().isoformat()+'Z',version='ddg-overall-paper-cv-v1',formal_fits=60,files=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(files))]))
print('PROTECTED',len(records),'FILES; DELIVERY',len(set(files)),'FILES')
