"""Read resource/progress fields only; never expose scores while stage A runs."""
import json,time,subprocess
from pathlib import Path
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
OUT=Path(__file__).resolve().parent
P=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1'
def read(p):return json.loads(p.read_text())
executions=P/'batch_records/executions/A'
invocations=sorted(executions.glob('invocation_*'))
answer=dict(stage='A',total_jobs=60,accepted=0,stage_B_started=False)
if invocations:
 inv=invocations[-1]
 accepted=sorted(inv.glob('*.acceptance.json'))
 reused=sorted(inv.glob('*.reused.json'))
 answer['accepted']=len(accepted)+len(reused)
 active=sorted(inv.glob('*.active_job.json'))
 if active:
  record=read(active[-1]);identity=record['job']
  answer['current_job']=identity;answer['job_elapsed_seconds']=round(time.time()-record['started_unix'],1)
  task,fold,seed,profile=identity.split('/')
  job=P/'runs'/task/('fold_'+fold)/('seed_'+seed)/profile
  histories=sorted(job.glob('attempt_*/history.jsonl'))
  if histories:
   rows=[json.loads(s) for s in histories[-1].read_text().splitlines() if s.strip()]
   answer['completed_epochs']=len(rows)
   answer['last_epoch_seconds']=round(rows[-1]['seconds'],2) if rows else None
   if len(rows)>=3:
    import statistics
    median=statistics.median([r['seconds'] for r in rows[:3]])
    answer['possible_memory_spill']=any(r['seconds']>2*median for r in rows[3:])
  samples=sorted(job.glob('attempt_*.memory_samples.jsonl'))
  if samples:
   values=[]
   for line in samples[-1].read_text().splitlines():
    try:values.append(json.loads(line)['free_mib'])
    except (ValueError,KeyError):pass
   if values:
    answer['minimum_free_mib']=min(values)
    answer['memory_tight']=min(values)<100
 if (inv/'failure.json').exists():
  failed=read(inv/'failure.json')
  answer['controller_failure']=True
  answer['failure_evidence']=str(inv/'failure.json')
 if (inv/'complete.json').exists():answer['stage_complete']=True
if (OUT/'stage_A_execute.command.json').exists():
 answer['batch_returncode']=read(OUT/'stage_A_execute.command.json')['returncode']
if (P/'batch_records/interim_A.json').exists():answer['interim_report_sealed']=True
answer['stage_B_started']=(P/'batch_records/executions/B').exists()
print(json.dumps(answer,ensure_ascii=False),flush=True)
