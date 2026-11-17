"""Finish document receipts and exact local-delivery manifests; preserve CP3 evidence."""
import gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
OLD=ROOT/"compile_repair/artifacts/cp3_v1"
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name,data):
    with (OUT/name).open("x",encoding="utf8") as f:json.dump(data,f,ensure_ascii=False,indent=2,sort_keys=True);f.write("\n")
def doc_check(label):
    before=json.loads((OLD/"baseline.json").read_text())
    targets=[p+":"+str(before["docs"][p]) for p in ("compile_repair/PROGRESS.md","compile_repair/docs/CHANGE_LOG.md","compile_repair/CP3_REPORT.md")]
    targets+=["compile_repair/docs/HANDOVER.md","compile_repair/docs/DECISIONS.md",
              "compile_repair/artifacts/cp3_v1/README.md","compile_repair/artifacts/cp3_delivery_v1/README.md"]
    command=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    start=time.monotonic();run=subprocess.run(command,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[json.loads(x) for x in run.stdout.decode().splitlines() if x.strip()]
    passed=run.returncode==0 and len(rows)==7 and all(r["passed"] for r in rows)
    with (OUT/("doc_check_"+label+".jsonl")).open("xb") as f:f.write(run.stdout)
    result=dict(command=command,cwd=str(ROOT),returncode=run.returncode,all_passed=passed,rows=len(rows),
                elapsed_seconds=time.monotonic()-start,stderr=run.stderr.decode(),
                document_sha256={p.split(":")[0]:sha(ROOT/p.split(":")[0]) for p in targets})
    write("doc_check_"+label+"_invocation.json",result)
    if not passed:raise SystemExit(2)
    return result
review=json.loads((OUT/"staging_review.json").read_text())
assert sha(OLD/"evidence_seal.json")==review["original_cp3_v1_seal_sha256"]
for p,row in json.loads((OLD/"evidence_seal.json").read_text())["files"].items():assert sha(OLD/p)==row["sha256"],p
doc_check("delivery_v1")
note="\n\n交付终检补记（修改 AI：Codex）：七份 doc_check_delivery_v1 全部通过；本条补记后再次检查的最终文档哈希见 cp3_delivery_v1/doc_check_final_invocation.json。四份原始工具日志按精确路径保留并豁免空白检查，其余文件检查通过；编译验收和 SOChecker 待确认状态均未改变。\n"
for p in ("compile_repair/CP3_REPORT.md","compile_repair/PROGRESS.md","compile_repair/docs/HANDOVER.md","compile_repair/docs/CHANGE_LOG.md","compile_repair/artifacts/cp3_delivery_v1/README.md"):
    with (ROOT/p).open("a",encoding="utf8") as f:f.write(note)
final=doc_check("final")
with gzip.open(OUT/"previous_document_snapshot.json.gz","rt",encoding="utf8") as f:snapshots=json.load(f)
for p,old in snapshots.items():assert (ROOT/p).read_bytes().startswith(old.encode("utf8")),p
old_inventory=json.loads((OLD/"delivery_inventory.json").read_text())
for p,row in old_inventory["files"].items():
    if p not in snapshots:assert sha(ROOT/p)==row["sha256"],p
for p,h in review["excluded_raw_logs"].items():assert sha(ROOT/p)==h,p
subprocess.run(["git","diff","--check"],cwd=str(ROOT),check=True)
scoped=review["scoped_command"]
subprocess.run(scoped,cwd=str(ROOT),check=True)
write("final_validation.json",{"previous_seal_unchanged":True,"previous_inventory_non_document_files_unchanged":True,
  "previous_document_bytes_preserved_as_prefix_and_snapshot":True,"doc_check_passed":final["all_passed"],
  "raw_log_exclusion_only":list(review["excluded_raw_logs"]),"all_other_whitespace_check_passed":True,
  "cp3_complete":False,"structure_status":"pending_user_decision","no_test_rerun":True,"cost_usd":0})
seal={"schema":"cp3-delivery-seal-v1","files":{str(p.relative_to(OUT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(OUT.rglob("*")) if p.is_file()},
      "previous_evidence_seal_sha256":review["original_cp3_v1_seal_sha256"],
      "cp3_complete":False,"status":"stopped_on_structure_mismatch","cost_usd":0}
write("evidence_seal.json",seal)
paths=set(ROOT/p for p in old_inventory["files"]);paths.add(OLD/"delivery_inventory.json")
paths.update(p for p in OUT.rglob("*") if p.is_file())
inventory={"schema":1,"self":str((OUT/"delivery_inventory.json").relative_to(ROOT)),
 "files":{str(p.relative_to(ROOT)):{"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(paths)},
 "file_count_including_self":len(paths)+1,"evidence_seal_sha256":sha(OUT/"evidence_seal.json"),
 "staging_policy":"Exact final inventory plus self only; no source corpus or earlier untracked artifacts."}
write("delivery_inventory.json",inventory)
for p,row in inventory["files"].items():assert sha(ROOT/p)==row["sha256"]
print(json.dumps({"files":inventory["file_count_including_self"],"doc_check":final["all_passed"],"status":seal["status"],"evidence_seal_sha256":inventory["evidence_seal_sha256"]}))
