"""Finalize Stage E protection without changing old assets."""
from pathlib import Path
import hashlib,json,subprocess,datetime,time
A=Path(__file__).resolve().parent
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 t=time.perf_counter()
 before=json.loads((A/'protected_before.json').read_text())
 docs={x['path']:x for x in json.loads((A/'documentation_update_002.json').read_text())['updates']}
 changes=[];missing=[];matched=0
 for name,expected in before['files'].items():
  p=Path(name)
  if not p.is_file():missing.append(name);continue
  actual=sha(p)
  if name in docs:
   assert expected['sha256']==docs[name]['before_sha256']
   assert actual==docs[name]['after_sha256']
   backup=A/(('worktree_' if 'ge-sc-llm-ddg-v11/' in name else 'original_')+p.name+'.before')
   assert p.read_bytes().startswith(backup.read_bytes())
   continue
  if actual!=expected['sha256']:changes.append({'path':name,'before':expected['sha256'],'after':actual})
  else:matched+=1
 roots=[
 '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c',
 '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1',
 '/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/audit/ddg_diagnostics_v1',
 '/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/audit/ddg_v11_correctness']
 new_assets=[]
 for root in roots:
  for p in Path(root).rglob('*'):
   if p.is_file() and str(p) not in before['files']:new_assets.append(str(p))
 git=[]
 for root,head in before['heads'].items():
  actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()
  tracked=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=root).decode().splitlines()
  check=subprocess.run(['git','diff','--check'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  git.append({'root':root,'head':actual,'expected_head':head,'tracked_changes':tracked,'diff_check_exit':check.returncode,'diff_check_output':check.stdout.decode()})
  assert actual==head
  assert set(tracked)=={'HANDOVER.md','docs/training_changes_2026-10-07.md'}
  assert check.returncode==0
 result={'utc':datetime.datetime.utcnow().isoformat()+'Z','seconds':time.perf_counter()-t,
 'checked_existing':len(before['files']),'unchanged_existing':matched,'authorized_doc_appends':list(docs),
 'missing':missing,'unexpected_changed':changes,'protected_roots_new_files':new_assets,'new_file_scan_roots':roots,'git':git,
 'expanded_scan_unbaselined_paths':json.loads((A/'protected_after.json').read_text())['protected_roots_new_files'],
 'expanded_scan_limit':'No start SHA for these 203 paths; do not infer newness or byte stability; original attempt retained',
 'status':'passed' if not(missing or changes or new_assets) else 'requires_review'}
 with (A/'protected_after_verified.json').open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps({k:v for k,v in result.items() if k!='expanded_scan_unbaselined_paths'},indent=2),flush=True)
 assert result['status']=='passed'
if __name__=='__main__':main()
