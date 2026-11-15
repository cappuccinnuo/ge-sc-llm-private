"""CP1 frozen integrity audit; read existing files only and exclusively record results."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def execute():
    base=json.loads((OUT/'baseline.json').read_text())
    changed=[p for p,h in base['frozen'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    old_reports=[p for p,h in base['old_reports'].items() if sha(ROOT/p)!=h]
    metadata={name:[p for p,h in refs.items() if not Path(p).is_file() or sha(Path(p))!=h]
              for name,refs in base['environment'].items()}
    current_solc={str(p):sha(p) for p in (Path.home()/'.solc-select').rglob('*') if p.is_file()}
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    refs=_code_refs()
    protected={}
    for relative,objects in [('compile_repair/core/model.py',['Compiler','Compilation']),
                             ('compile_repair/toolchain/solc.py',None)]:
        original=subprocess.check_output(['git','show',base['head']+':'+relative],cwd=str(ROOT)).decode('utf8')
        before={n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        after={n.name:ast.dump(n) for n in ast.parse((ROOT/relative).read_text()).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
        protected[relative]={name:before[name]==after.get(name) for name in (objects or before)}
    slither='compile_repair/toolchain/slither.py'
    protected[slither]={'entire_file':hashlib.sha256(subprocess.check_output(['git','show',base['head']+':'+slither],cwd=str(ROOT))).hexdigest()==sha(ROOT/slither)}
    impl=json.loads((OUT/'implementation_audit.json').read_text())
    implementation_changed=[p for p,entry in impl['files'].items() if sha(ROOT/p)!=entry['sha256']]
    tracked_changes=subprocess.check_output(['git','diff','--name-only'],cwd=str(ROOT)).decode().splitlines()
    unexpected=[p for p in tracked_changes if not p.startswith('compile_repair/')]
    result={'frozen_files':len(base['frozen']),'outside_module_files':sum(not p.startswith('compile_repair/') for p in base['frozen']),
            'old_artifacts':sum(p.startswith('compile_repair/artifacts/') for p in base['frozen']),
            'fixtures':sum(p.startswith('compile_repair/tests/fixtures/') for p in base['frozen']),
            'changed_frozen':changed,'old_reports_changed':old_reports,'metadata_counts':{k:len(v) for k,v in base['environment'].items()},
            'metadata_changed':metadata,'solc_files':len(current_solc),'solc_all_equal':current_solc==base['solc'],
            'code_refs_count':len(refs),'code_refs_equal':refs==base['code_refs'],
            'global_selection_equal':{k:os.environ.get(k) for k in base['selection_environment']}==base['selection_environment'],
            'protected_cp0_1_functions':protected,'implementation_changed_since_tests':implementation_changed,
            'outside_module_tracked_changes':unexpected}
    result['passed']=not(changed or old_reports or any(metadata.values()) or implementation_changed or unexpected) and all(
        result[k] for k in ['solc_all_equal','code_refs_equal','global_selection_equal']) and all(v for d in protected.values() for v in d.values())
    with (OUT/'frozen_audit.json').open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True)
    print(json.dumps(result,indent=2),flush=True)
    if not result['passed']:raise SystemExit(2)


if __name__=='__main__':execute()
