import os,subprocess,json,time
from pathlib import Path
base=Path(__file__).resolve().parent
suites=[('nodesem',['scripts/node_sem/tests']),('dfg_v2',['scripts/DFG/dfg_v2/tests']),('legacy',['scripts/DFG/tests','tests/test_graph_utils.py'])]
results=[]
for name,paths in suites:
 start=time.monotonic()
 cmd=['/home/zhao/miniconda3/envs/mando/bin/python','-B','-m','pytest','-q','-p','no:cacheprovider']+paths
 with (base/(name+'.log')).open('xb') as stream:
  rc=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT).returncode
 results.append(dict(suite=name,command=cmd,returncode=rc,seconds=time.monotonic()-start))
 (base/'progress.json').write_text(json.dumps(results,indent=2))
 if rc:break
(base.parent/'regressions.json').write_text(json.dumps(dict(passed=len(results)==3 and all(r['returncode']==0 for r in results),suites=results),indent=2))
