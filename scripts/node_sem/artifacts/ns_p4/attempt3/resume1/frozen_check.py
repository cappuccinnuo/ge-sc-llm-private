import json,hashlib,subprocess
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.experiment.run import _code_refs
from scripts.node_sem.p4b_acceptance import unchanged_history
root=Path.cwd();base=root/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1'
plan=h8.load(base/'plan.json')
runtime=json.loads((base/'runtime_resume_v2.json').read_text())['runtime']
assert _code_refs()==runtime
before=json.loads((Path(__file__).parent.parent/'before.json').read_text())
for name,entry in before['documents'].items():
 data=(root/name).read_bytes()[:entry['bytes']]
 assert hashlib.sha256(data).hexdigest()==entry['sha256']
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
assert all(p.startswith('scripts/node_sem/') or p in before['documents'] for p in changed)
result=dict(passed=True,code_refs=len(runtime),h8_load=True,effective_runtime_equal=True,attempt2_files_unchanged=unchanged_history(),document_prefixes_unchanged=True,tracked_changed_paths=changed)
(Path(__file__).parent/'frozen_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
