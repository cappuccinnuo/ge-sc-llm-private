from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2 import execution as e
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,ref,write,checked
from scripts.DFG.dfg_v2.experiment.run import _code_refs
r=Path("scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1")
p=e.load(r/"plan.json");revision=read(r/"runtime_resume_v2.json")
print("revision_keys",list(revision))
print("load_jobs",len(p["jobs"]),"frozen_sources",len(_code_refs()))

assert _code_refs()==revision["runtime"]
write(Path("scripts/node_sem/artifacts/batch_NB_v1/analysis_checks/frozen_integrity.json"),dict(passed=True,frozen_sources=354,h8_load_jobs=len(p["jobs"]),runtime=ref(r/"runtime_resume_v2.json"),runtime_matches=True))
