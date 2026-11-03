from pathlib import Path
import hashlib,json,subprocess
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,checked,ref,write
from scripts.DFG.dfg_v2.benchmark_v2.runtime_amendment import amendment_ref
from scripts.DFG.dfg_v2.experiment.run import _code_refs
base=Path('scripts/node_sem/artifacts/ns_p4');start=read(base/'started.json')
plan=read(base/'attempt2/plan.json');path=checked(plan['source_h8_plan'])
source=h8.load(path);actual=_code_refs();amendment=amendment_ref(path,source,actual)
effective=read(checked(amendment))['runtime'] if amendment else source['runtime']
assert effective==actual
prefixes={}
for name,old in start['docs'].items():
 raw=Path(name).read_bytes()
 assert hashlib.sha256(raw[:old['bytes']]).hexdigest()==old['sha256']
 raw.decode('utf-8','strict');prefixes[name]=dict(passed=True,original_bytes=old['bytes'],new_bytes=len(raw))
changed=subprocess.check_output(['git','diff','HEAD','--name-only']).decode().splitlines()
assert all(p.startswith('scripts/node_sem/') or p in start['docs'] for p in changed),changed
assert subprocess.call(['git','diff','--check'])==0
result=dict(passed=True,h8_plan=plan['source_h8_plan'],effective_amendment=amendment,
 frozen_runtime_entries=len(actual),frozen_runtime_equal=True,document_prefixes=prefixes,tracked_changes=changed)
write(base/'final_checks.json',result)
print(json.dumps(dict(passed=True,frozen_runtime_entries=len(actual),tracked_changed=len(changed))))
