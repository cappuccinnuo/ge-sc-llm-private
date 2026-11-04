import hashlib,json,subprocess
from pathlib import Path
root=Path.cwd();out=root/'scripts/node_sem/artifacts/ns_p5'
inventory=json.loads((out/'delivery_inventory.json').read_text())
rows=inventory['files']; files=[root/r['path'] for r in rows]
for r,p in zip(rows,files):
 assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],str(p)
files.extend([out/'delivery_inventory.json',Path(__file__).resolve()])
wanted={str(p.relative_to(root)) for p in files}
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines())
assert staged<=wanted
assert all(p.suffix not in ('.pt','.npz','.bin','.safetensors') and p.stat().st_size<100*1024**2 for p in files)
for i in range(0,len(files),80):
 subprocess.run(['git','add','-f','--']+[str(p.relative_to(root)) for p in files[i:i+80]],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
checks=['git','diff','--cached','--check','--','.',':(exclude)scripts/node_sem/artifacts/batch_NA_v1/runtime_archive/**',':(exclude)scripts/node_sem/artifacts/batch_NA_v1/inputs/**',':(exclude)scripts/node_sem/artifacts/ns_p5/*.log']
r=subprocess.run(checks,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
if r.returncode:raise RuntimeError(r.stdout)
staged=set(subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines());assert staged==wanted
with (out/'commit_validation.json').open('x',encoding='utf8') as f:
 json.dump(dict(passed=True,staged_files_before_validation=len(staged),bytes=sum(p.stat().st_size for p in files),format_check_command=checks,immutable_archives_exempt_from_whitespace_normalization=True,binaries_included=False,first_stage_attempt=dict(exit_code=1,reason='blanket .gitignore *.json; inspected and added only SHA-inventoried metadata with -f; no training/plan/input changes')),f,indent=2);f.write('\n')
subprocess.run(['git','add','-f','--',str((out/'commit_validation.json').relative_to(root))],check=True)
print(json.dumps(dict(staged_files=len(staged)+1,metadata_mib=sum(p.stat().st_size for p in files)/2**20,passed=True)))
