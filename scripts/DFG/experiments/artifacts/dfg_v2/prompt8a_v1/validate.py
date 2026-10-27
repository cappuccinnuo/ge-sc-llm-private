"""Prompt 8A existing regression suites; no new training."""
import os,sys,json,subprocess,time
from pathlib import Path
ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
os.chdir(str(ROOT))
OUT=Path(__file__).resolve().parent
commands=[
 ('store_verify',['-m','scripts.DFG.dfg_v2.cli','verify','--store','scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json']),
 ('targeted_tests',['-m','pytest','-q','-p','no:cacheprovider','scripts/DFG/dfg_v2/tests/test_batch.py','scripts/DFG/dfg_v2/tests/test_batch_plan.py','scripts/DFG/dfg_v2/tests/test_reporting.py','scripts/DFG/dfg_v2/tests/test_stats.py']),
 ('v2_tests',['-m','pytest','-q','-p','no:cacheprovider','scripts/DFG/dfg_v2/tests']),
 ('legacy_tests',['-m','pytest','-q','-p','no:cacheprovider','scripts/DFG/tests','tests/test_graph_utils.py'])]
for name,args in commands:
 argv=[sys.executable,'-B']+args
 if 'tests' in name:argv+=['--junitxml',str(OUT/(name+'.xml'))]
 start=time.monotonic()
 with (OUT/(name+'.log')).open('x',encoding='utf8') as stream:
  result=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,env=os.environ.copy())
 with (OUT/(name+'.command.json')).open('x',encoding='utf8') as f:
  json.dump(dict(argv=argv,returncode=result.returncode,seconds=time.monotonic()-start),f,indent=2)
 print(name,'exit',result.returncode,'seconds',round(time.monotonic()-start,2),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
print('ALL VALIDATION COMMANDS PASSED',flush=True)
