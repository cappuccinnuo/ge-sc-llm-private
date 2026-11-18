"""CP3 continuation protected-file audit; explicit implementation/test allowlist."""
import gzip,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from scripts.DFG.dfg_v2.experiment.run import _code_refs
B=Path(__file__).resolve().parent
before=json.loads((B.with_name("cp3_continue_v1")/"baseline.json").read_text())
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(1048576),b""):h.update(block)
 return h.hexdigest()
allowed=set(before["docs"])|{
 "compile_repair/toolchain/project.py","compile_repair/tests/test_project.py",
 "compile_repair/toolchain/solc.py","compile_repair/toolchain/slither.py",
 "compile_repair/pipeline.py","compile_repair/cli.py","compile_repair/evaluation/survey.py",
 "compile_repair/tests/test_pipeline.py","compile_repair/tests/test_cp1_1.py",
 "compile_repair/tests/test_pragma_comments.py"}
protected={p:h for p,h in before["tracked"].items() if p not in allowed}
changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
ref=before["old_sealed_reference"]
assert sha(ROOT/ref["path"])==ref["sha256"]
old_sealed=json.loads((ROOT/ref["path"]).read_text())["old_sealed"]
old_changes=[p for p,h in old_sealed.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
envs={}
for name in before["environment"]:
 base=Path("/home/zhao/miniconda3/envs")/name
 files=set(base.glob("lib/python*/site-packages/*.dist-info/METADATA"))
 files.update(base.glob("conda-meta/*.json"));files.add(base/"conda-meta/history")
 envs[name]={str(p):sha(p) for p in files if p.is_file()}
solc={str(p):sha(p) for p in (Path.home()/".solc-select").rglob("*") if p.is_file()}
impl={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"compile_repair").rglob("*.py")
 if not {"tests","artifacts"} & set(p.relative_to(ROOT/"compile_repair").parts)}
history={}
for name in before["docs"]:
 old=subprocess.check_output(["git","show",before["head"]+":"+name],cwd=str(ROOT))
 now=(ROOT/name).read_bytes()
 if name.endswith("HANDOVER.md"):
  marker=b"## 6. ";history[name]=now[now.index(marker):].startswith(old[old.index(marker):])
 elif name.endswith("DECISIONS.md"):
  marker=b"## 2. ";history[name]=now[now.index(marker):].startswith(old[old.index(marker):])
 else:history[name]=now.startswith(old)
external_count=0;external_changes=[]
for manifest in (ROOT/"compile_repair/artifacts/cp3_v1/acquisition").glob("*/manifest.jsonl.gz"):
 with gzip.open(manifest,"rt") as f:
  for line in f:
   row=json.loads(line);p=Path(row["absolute_path"]);external_count+=1
   if not p.is_file() or sha(p)!=row["sha256"]:external_changes.append(str(p))
docs=json.loads((ROOT/"compile_repair/artifacts/cp3_v1/document_manifest.json").read_text())["files"]
doc_changes=[r["destination"] for r in docs if sha(Path(r["destination"]))!=r["sha256"]]
tracked=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
result={"protected_tracked_files":len(protected),"protected_changes":changed,
 "old_sealed_files":len(old_sealed),"old_sealed_changes":old_changes,
 "environment_equal":envs==before["environment"],"environment_counts":{k:len(v) for k,v in envs.items()},
 "solc_equal":solc==before["solc"],"solc_files":len(solc),"code_refs_equal":_code_refs()==before["code_refs"],
 "code_refs_count":len(before["code_refs"]),"production_file_count":len(impl),
 "implementation_sha256":impl,"documentation_history_preserved":history,
 "unexpected_tracked_changes":[p for p in tracked if p not in allowed],
 "selection_environment_equal":{k:os.environ.get(k) for k in before["selection_environment"]}==before["selection_environment"],
 "acquired_corpus_files":external_count,"acquired_corpus_changes":external_changes,
 "acquired_documents":len(docs),"acquired_document_changes":doc_changes,
 "note":"CP3 approved entry normalization; probe setup stopped, acceptance is recorded separately."}
current_baseline=json.loads((B/"baseline.json").read_text())
current_allowed={
 "compile_repair/toolchain/project.py", "compile_repair/tests/test_project.py",
 "compile_repair/docs/DECISIONS.md", "compile_repair/docs/HANDOVER.md",
 "compile_repair/docs/CHANGE_LOG.md", "compile_repair/PROGRESS.md", "compile_repair/CP3_REPORT.md"}
current_protected={p:v["sha256"] for p,v in current_baseline["files"].items() if p not in current_allowed}
current_changes=[p for p,h in current_protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
result["previous_checkpoint_protected_files"]=len(current_protected)
result["previous_checkpoint_changes"]=current_changes
result["previous_working_inventory_unchanged"]=sha(B.with_name("cp3_binding_v1")/"delivery_inventory.json")==current_baseline["previous_inventory_sha256"]
current_history={}
for rel in ["docs/HANDOVER.md","docs/DECISIONS.md","docs/CHANGE_LOG.md","PROGRESS.md","CP3_REPORT.md"]:
 old=(B/"before"/rel).read_bytes();now=(ROOT/"compile_repair"/rel).read_bytes()
 marker=b"## 6. " if rel.endswith("HANDOVER.md") else b"## 2. " if rel.endswith("DECISIONS.md") else None
 current_history[rel]=now[now.index(marker):].startswith(old[old.index(marker):]) if marker else now.startswith(old)
result["previous_checkpoint_history_preserved"]=current_history
native=json.loads((B.with_name("cp3_continue_v1")/"alias_binding_review_request.json").read_text())["installed_source_evidence"]
result["native_slither_type_parser_unchanged"]=sha(Path(native["path"]))==native["sha256"]
result["native_slither_type_parser_sha256"]=sha(Path(native["path"]))
result["passed"]=not any([changed,old_changes,external_changes,doc_changes,result["unexpected_tracked_changes"]]) and all(
 result[k] for k in ["environment_equal","solc_equal","code_refs_equal","selection_environment_equal"]) and all(history.values()) and len(impl)<=30 and not current_changes and result["previous_working_inventory_unchanged"] and all(current_history.values()) and result["native_slither_type_parser_unchanged"]
with (B/"frozen_audit.json").open("x") as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write("\n")
print(json.dumps({k:v for k,v in result.items() if k!="implementation_sha256"},ensure_ascii=False))
sys.exit(0 if result["passed"] else 2)
