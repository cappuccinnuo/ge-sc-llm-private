"""Archive Prompt8D text evidence unchanged; exclude model/input binaries."""
from pathlib import Path
import hashlib,json,re,subprocess
R=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
A=R/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1'
OUT=A/'github_archive'
TEXT={'.json','.jsonl','.csv','.log','.md','.py','.xml'}
EXCLUDE={'.pt','.npz','.pyc'}
PATTERNS=[
 re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
 re.compile(r'\bgithub_pat_[A-Za-z0-9_]{40,}\b'),
 re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
 re.compile(r'(?i)https?://[^\s/:]+:[^\s/@]+@github\.com'),
]
def digest(data):return hashlib.sha256(data).hexdigest()
def main():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(R),text=True).strip()=='5f31a66aa7d42c4b995ce69692e94480e45ab7fd'
 assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=str(R),text=True)
 files=[];excluded=[];seen=set()
 for p in sorted(A.rglob('*')):
  if not p.is_file():continue
  if OUT in p.parents:continue
  if p.is_symlink():raise ValueError('Symlink '+str(p))
  if p.suffix in EXCLUDE:
   excluded.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'reason':'model_or_binary_feature_or_cache'});continue
  if p.suffix not in TEXT:raise ValueError('Unexpected format '+str(p))
  data=p.read_bytes()
  if len(data)>=90*1048576:raise ValueError('Text exceeds archive ceiling '+str(p))
  content=data.decode('utf-8')
  for pattern in PATTERNS:
   if pattern.search(content):raise ValueError('Credential-shaped content requires review: '+str(p))
  name=str(p.relative_to(R))
  assert name not in seen;seen.add(name)
  files.append({'path':name,'bytes':len(data),'sha256':digest(data)})
 script=Path(__file__).resolve()
 files.append({'path':str(script.relative_to(R)),'bytes':script.stat().st_size,'sha256':digest(script.read_bytes())})
 olddocs={}
 for n in ['HANDOVER.md','docs/training_changes_2026-10-07.md','scripts/DFG/dfg_v2/PROGRESS.md']:
  data=(R/n).read_bytes();olddocs[n]={'bytes':len(data),'sha256':digest(data)}
 manifest={'version':'prompt8d-github-text-archive-v1','date':'2026-10-29','ai':'Codex','source_commit':'5f31a66aa7d42c4b995ce69692e94480e45ab7fd','branch':'dfg-v2','repo':'cappuccinnuo/ge-sc-llm-private',
 'inference_results':300,'formal_fit_count':0,'acceptance_cpu_optimizer_steps':2,'new_training_authorized':False,
 'files':files,'count':len(files),'bytes':sum(x['bytes'] for x in files),'excluded':excluded,
 'documentation_before_append':olddocs,'original_files_unchanged':True,
 'network_note':'WSL Git ls-remote succeeded on this date; normal non-force push only',
 'limits':'Text evidence only; model weights and binary feature assets stay local; F proposal is unauthorized and retains the documented selective-idN risk.'}
 out=R/'docs/github_archive_prompt8d_2026-10-29.json'
 with out.open('x',encoding='utf-8') as h:json.dump(manifest,h,ensure_ascii=False,indent=2)
 print(json.dumps({'manifest':str(out),'count':len(files),'MiB':manifest['bytes']/1048576,'excluded':len(excluded)},indent=2))
if __name__=='__main__':main()
