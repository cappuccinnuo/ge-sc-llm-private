"""CP1 mandatory UTF-8/CJK checks, with frozen append offsets and receipts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
version=sys.argv[1]
if version not in ('v1','v2'):raise SystemExit('Use a new named check version')
targets=['compile_repair/CP1_REPORT.md','compile_repair/PROGRESS.md:20625',
         'compile_repair/docs/CHANGE_LOG.md:103907','compile_repair/docs/HANDOVER.md',
         'compile_repair/docs/DECISIONS.md','compile_repair/artifacts/cp1_development_v1/README.md',
         'compile_repair/artifacts/cp1_sample_v1/README.md','compile_repair/artifacts/cp1_historical_v1/README.md']
command=[sys.executable,'-B','-m','scripts.node_sem.doc_check','--expect-cjk']+targets
result=subprocess.run(command,cwd=str(ROOT),env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
name='doc_check_'+version
with (OUT/(name+'.jsonl')).open('xb') as f:f.write(result.stdout)
with (OUT/(name+'_stderr.log')).open('xb') as f:f.write(result.stderr)
rows=[json.loads(line) for line in result.stdout.decode().splitlines() if line.strip()]
passed=result.returncode==0 and len(rows)==8 and all(r['passed'] for r in rows)
with (OUT/(name+'_invocation.json')).open('x') as f:json.dump({'command':command,'returncode':result.returncode,'rows':len(rows),'all_passed':passed,'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()},f,indent=2)
print(json.dumps({'returncode':result.returncode,'rows':len(rows),'all_passed':passed,'checks':rows},ensure_ascii=False))
if not passed:raise SystemExit(2)
