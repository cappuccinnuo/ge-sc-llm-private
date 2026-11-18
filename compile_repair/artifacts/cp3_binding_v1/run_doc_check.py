"""Run the prescribed document check against every changed prose file."""
import hashlib, json, re, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).resolve().parent
label=sys.argv[1]
assert re.fullmatch(r"v[1-9][0-9]*", label)
previous=json.loads((B.with_name("cp3_continue_v1")/"doc_check_delivery_invocation.json").read_text())
assert previous["passed"]
targets=previous["command"][previous["command"].index("--expect-cjk")+1:]+[
    "compile_repair/artifacts/cp3_binding_v1/README.md"]
argv=[sys.executable,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
prefix="doc_check_"+label
start=time.monotonic()
result=subprocess.run(argv,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
for suffix,data in [(".stdout",result.stdout),(".stderr",result.stderr)]:
    with (B/(prefix+suffix)).open("xb") as f:f.write(data)
rows=[json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
paths=[target.rpartition(":")[0] if target.rpartition(":")[2].isdigit() else target for target in targets]
receipt={"command":argv,"returncode":result.returncode,"elapsed_seconds":time.monotonic()-start,
    "passed":result.returncode==0 and len(rows)==len(targets) and all(r["passed"] for r in rows),
    "document_sha256":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
    "checks":rows,
    "scope":"All changed/new authored Markdown. before/ snapshots are immutable historical byte evidence, not new prose."}
with (B/(prefix+".json")).open("x") as f:json.dump(receipt,f,indent=2,ensure_ascii=False);f.write("\n")
print(json.dumps(receipt,ensure_ascii=False))
sys.exit(0 if receipt["passed"] else 2)
