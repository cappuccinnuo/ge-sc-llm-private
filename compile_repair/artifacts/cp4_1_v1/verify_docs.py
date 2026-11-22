"""Run the existing Chinese documentation check over the correct append boundaries."""
from batch import *

def main():
    checkpoint=load("checkpoint_delivery.json")["latest_doc_check"]
    prefix={r["path"].replace("\\","/"):r for r in checkpoint}
    targets=[]
    editable={"compile_repair/docs/HANDOVER.md","compile_repair/docs/DECISIONS.md"}
    for name,r in prefix.items():
        path=ROOT/name
        if name in editable:
            targets.append(name)
        else:
            raw=path.read_bytes()
            if sha(raw[:r["total_bytes"]])!=r["sha256"]:
                raise ValueError("Document prefix differs from prior checkpoint: "+name)
            targets.append(name+":"+str(r["total_bytes"]))
    for path in sorted(HERE.rglob("*.md")):
        targets.append(str(path.relative_to(ROOT)))
    cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","scripts.node_sem.doc_check","--expect-cjk",*targets]
    proc=subprocess.run(cmd,cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf8")
    records=[json.loads(s) for s in proc.stdout.splitlines() if s]
    for row in records:row["sha256"]=sha((ROOT/row["path"]).read_bytes())
    result=dict(command=cmd,returncode=proc.returncode,documents=records,stderr=proc.stderr)
    if len(sys.argv)>1:saved(sys.argv[1],result)
    print(json.dumps(records,ensure_ascii=False))
    if proc.returncode or not records or not all(r["passed"] for r in records):sys.exit(1)
if __name__=="__main__":main()
