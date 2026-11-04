import json,hashlib,subprocess
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.experiment.run import _code_refs
from scripts.node_sem.p4b_acceptance import unchanged_history
from scripts.node_sem.batch_na import load, require_launch_authorization, DEFAULT
root=Path.cwd();out=Path(__file__).resolve().parent
old=root/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1'
h8.load(old/'plan.json')
runtime=json.loads((old/'runtime_resume_v2.json').read_text())['runtime']
assert _code_refs()==runtime
plan=load(DEFAULT/'plan.json',mode='launch',deep=False)
assert len(plan['jobs'])==240 and plan['execution_authorized'] is False
try:
    require_launch_authorization(DEFAULT/'plan.json')
except PermissionError as e:
    denied=str(e)
else:
    raise AssertionError('Unapproved launch was not rejected')
before=json.loads((out/'before.json').read_text())
for name,entry in before['documents'].items():
    assert hashlib.sha256((root/name).read_bytes()[:entry['bytes']]).hexdigest()==entry['sha256']
changed=subprocess.check_output(['git','diff','--name-only'],universal_newlines=True).splitlines()
assert all(n.startswith('scripts/node_sem/') or n in before['documents'] for n in changed)
assert not list(DEFAULT.glob('runs/**/*'))
result=dict(passed=True,code_refs=len(runtime),h8_load=True,effective_runtime_equal=True,
    old_p4_attempt2_unchanged=unchanged_history(),document_prefixes_unchanged=True,
    changed_tracked_files=changed,launch_denied=denied,formal_fits=0,plan_sha256=hashlib.sha256((DEFAULT/'plan.json').read_bytes()).hexdigest())
with (out/'final_check.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))
