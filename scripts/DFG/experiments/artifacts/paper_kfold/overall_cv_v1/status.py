from pathlib import Path
import json,datetime,subprocess
b=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1')
print(datetime.datetime.utcnow().isoformat()+'Z')
print('prepared',len(list((b/'prepared').rglob('task.json'))),'sealed',(b/'plan.seal.json').exists())
for tid in ('reentrancy_author_contract','access_control_author_contract','reentrancy_author_node','access_control_author_node'):
 p=b/'runs'/tid
 receipts=list(p.glob('fold_*/*/attempt_*/receipt.json'))
 print(tid,'complete',len(receipts))
 active=[x for x in p.glob('fold_*/*/attempt_*.log') if not (x.with_suffix('')/'receipt.json').exists()]
 for x in sorted(active,key=lambda x:x.stat().st_mtime)[-2:]:
  print(str(x.relative_to(b)));print(x.read_text()[-650:])
for n in ('prepare_001.log','controller_first_pair.log','controller_full.log'):
 p=b/n
 if p.exists():print(n,p.read_text()[-500:])
print(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader']).decode().strip())
print('failures',[str(p.relative_to(b)) for p in (b/'runs').rglob('*.failure.json')])
