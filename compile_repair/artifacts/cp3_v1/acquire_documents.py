"""Authorized CP3 document acquisition; preserve exact bytes and stop on error."""
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PROXY="http://172.18.144.1:17897"

def write(name,value):
    with (OUT/name).open("x",encoding="utf8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,sort_keys=True)
        stream.write("\n")

def execute():
    authorization=json.loads((OUT/"authorization.json").read_text())
    assert authorization["status"]=="approved" and authorization["cost_cap_usd"]==0
    assert authorization["request_sha256"]==hashlib.sha256((ROOT/authorization["request_path"]).read_bytes()).hexdigest()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({"http":PROXY,"https":PROXY}))
    rows=[]
    for item in authorization["docs"]:
        target=Path(item["destination"])
        assert not target.exists(),str(target)
        target.parent.mkdir(parents=True,exist_ok=True)
        start=time.monotonic()
        row=dict(tag=item["tag"],commit=item["commit"],source_url=item["source_url"],
            destination=str(target),expected_bytes=item["bytes"],expected_git_blob_sha1=item["git_blob_sha1"],
            cost_usd=0,proxy=PROXY)
        try:
            request=urllib.request.Request(item["source_url"],headers={"User-Agent":"CompileRepair-CP3-authorized-acquisition"})
            with opener.open(request,timeout=45) as response:
                raw=response.read(item["bytes"]+1)
                row.update(http_status=response.status,final_url=response.geturl())
            row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                git_blob_sha1=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest())
            if row["bytes"]!=item["bytes"] or row["git_blob_sha1"]!=item["git_blob_sha1"]:
                raise ValueError("Authorized size or Git blob identity mismatch")
            with target.open("xb") as stream:
                stream.write(raw)
            row["passed"]=True
        except Exception as exc:
            row.update(passed=False,error_type=type(exc).__name__,error=str(exc))
        row["elapsed_seconds"]=time.monotonic()-start
        rows.append(row)
        with (OUT/"document_acquisition.jsonl").open("a",encoding="utf8") as stream:
            stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
        print(json.dumps({k:row.get(k) for k in ("tag","destination","bytes","sha256","passed","error")}),flush=True)
        if not row["passed"]:
            write("document_acquisition_status.json",dict(passed=False,completed=sum(x["passed"] for x in rows),attempts=len(rows),stopped_at=row))
            raise SystemExit(2)
    write("document_manifest.json",dict(passed=True,files=rows,documents=len(rows),total_bytes=sum(r["bytes"] for r in rows)))
    write("document_acquisition_status.json",dict(passed=True,completed=len(rows),attempts=len(rows),cost_usd=0))

if __name__=="__main__":
    execute()
