import hashlib, json, subprocess
from pathlib import Path
root=Path.cwd(); out=root/'scripts/node_sem/artifacts/ns_p5'
assert json.loads((out/'final_check.json').read_text())['passed']
assert json.loads((out/'prepare_exit.json').read_text())['exit_code']==0
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='042c3c77347f83347a057d074af2421e39f53739'
assert not subprocess.check_output(['git','diff','--cached','--name-only'],text=True).strip()
fixed=['HANDOVER.md','docs/training_changes_2026-10-07.md','scripts/node_sem/PROGRESS.md','scripts/node_sem/NS_P5_REPORT.md','scripts/node_sem/batch_na.py','scripts/node_sem/p5_prepare.py','scripts/node_sem/tests/test_batch_na.py']
files=[root/p for p in fixed]
for folder in [out,root/'scripts/node_sem/artifacts/batch_NA_v1']:
 files.extend(p for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.csv','.md','.log','.jsonl','.txt'))
files=sorted(set(files)); assert not any(p.suffix in ('.pt','.npz','.bin') for p in files)
rows=[dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
with (out/'delivery_inventory.json').open('x',encoding='utf8') as f:json.dump(dict(files=rows,binaries_included=False),f,indent=2);f.write('\n')
files.append(out/'delivery_inventory.json')
for i in range(0,len(files),80):subprocess.run(['git','add','--']+[str(p.relative_to(root)) for p in files[i:i+80]],check=True)
# Byte-for-byte source archives, input snapshots and captured logs are evidence;
# retain their original formatting instead of normalizing historical bytes.
checks=['git','diff','--cached','--check','--','.',':(exclude)scripts/node_sem/artifacts/batch_NA_v1/runtime_archive/**',':(exclude)scripts/node_sem/artifacts/batch_NA_v1/inputs/**',':(exclude)scripts/node_sem/artifacts/ns_p5/*.log']
r=subprocess.run(checks,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
if r.returncode:raise RuntimeError(r.stdout)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
assert set(staged)=={str(p.relative_to(root)) for p in files}
with (out/'commit_validation.json').open('x',encoding='utf8') as f:
 json.dump(dict(passed=True,staged_files_before_validation=len(staged),bytes=sum(p.stat().st_size for p in files),format_check_command=checks,immutable_archives_exempt_from_whitespace_normalization=True,binaries_included=False),f,indent=2);f.write('\n')
subprocess.run(['git','add','--',str((out/'commit_validation.json').relative_to(root))],check=True)
print(json.dumps(dict(staged_files=len(staged)+1,bytes=sum(p.stat().st_size for p in files),passed=True)))
