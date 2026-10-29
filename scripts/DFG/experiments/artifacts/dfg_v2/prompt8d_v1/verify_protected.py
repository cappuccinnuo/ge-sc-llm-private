"""Read-only final Prompt8D preservation check; exclusive output."""
from pathlib import Path
import hashlib, json, subprocess, sys, time
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
A=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def run(output):
 from scripts.DFG.dfg_v2.diagnostics8c.common import historical_runtime, checked_plan
 start=json.loads((A/'protected_start.json').read_text())
 began=time.monotonic()
 differences=[p for p,d in start['references'].items() if sha(p)!=d]
 if differences:raise AssertionError(differences)
 plan_path=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json'
 with historical_runtime(plan_path,checked_plan(plan_path)) as binding:
  runtime=len(binding['runtime'])
 old_changes=subprocess.check_output(['git','diff','--name-only',start['head']],cwd=str(ROOT)).decode().splitlines()
 allowed=set(start['docs'])
 unexpected=[n for n in old_changes if n not in allowed and n!='scripts/DFG/dfg_v2/PROMPT8D_REPORT.md']
 if unexpected:raise AssertionError(unexpected)
 docs={}
 for name,digest in start['docs'].items():
  prior=subprocess.check_output(['git','show',start['head']+':'+name],cwd=str(ROOT))
  assert hashlib.sha256(prior).hexdigest()==digest
  current=(ROOT/name).read_bytes()
  if not current.startswith(prior):raise AssertionError('Historical document prefix changed: '+name)
  docs[name]={'original_sha256':digest,'original_bytes':len(prior),'current_bytes':len(current),'prefix_preserved':True}
 result={'status':'passed','protected_references':len(start['references']),
  'historical_runtime_files':runtime,'differences':differences,'old_tracked_changes':old_changes,
  'documents':docs,'source_head':start['head'],'source_plan_sha256':sha(plan_path),
  'seconds':time.monotonic()-began,'formal_training_count':0}
 with Path(output).open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps(result,indent=2))
if __name__=='__main__':run(sys.argv[1])
