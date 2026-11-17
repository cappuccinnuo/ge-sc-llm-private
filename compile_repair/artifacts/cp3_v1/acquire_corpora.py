"""Fetch only authorized corpus subtrees; never execute corpus code or fetch dependencies."""
import fnmatch
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
CORPORA=Path("/home/zhao/SmartContract/corpora")
PROXY="http://172.18.144.1:17897"

def write(path,value):
    with path.open("x",encoding="utf8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,sort_keys=True)
        stream.write("\n")

def run(name,step,arguments,cwd):
    command=["git","-c","http.proxy="+PROXY,"-c","submodule.recurse=false"]+arguments
    env=dict(os.environ,GIT_TERMINAL_PROMPT="0",GIT_LFS_SKIP_SMUDGE="1",
        HTTP_PROXY=PROXY,HTTPS_PROXY=PROXY,http_proxy=PROXY,https_proxy=PROXY)
    started=time.monotonic()
    result=subprocess.run(command,cwd=str(cwd),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
    folder=OUT/"acquisition"/name
    for suffix,raw in (("stdout",result.stdout),("stderr",result.stderr)):
        with (folder/(step+"."+suffix)).open("xb") as stream:stream.write(raw)
    row=dict(corpus=name,step=step,command=command,cwd=str(cwd),returncode=result.returncode,
        elapsed_seconds=time.monotonic()-started,cost_usd=0,
        stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
    with (OUT/"corpus_acquisition_invocations.jsonl").open("a",encoding="utf8") as stream:
        stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps(dict(corpus=name,step=step,returncode=result.returncode)),flush=True)
    if result.returncode or b"filtering not recognized" in result.stderr.lower():
        raise RuntimeError("Acquisition stopped at "+name+"/"+step+": "+result.stderr.decode("utf8",errors="replace")[-1500:])
    return result.stdout

def execute():
    auth=json.loads((OUT/"authorization.json").read_text())
    assert auth["status"]=="approved" and auth["cost_cap_usd"]==0
    assert hashlib.sha256((ROOT/auth["request_path"]).read_bytes()).hexdigest()==auth["request_sha256"]
    (OUT/"acquisition").mkdir()
    rows=[]
    try:
        for item in auth["corpora"]:
            name=item["name"];target=Path(item["destination"])
            assert target.parent.resolve()==CORPORA.resolve()
            assert not target.exists(),str(target)
            target.mkdir()
            folder=OUT/"acquisition"/name;folder.mkdir()
            run(name,"init",["init",str(target)],CORPORA)
            run(name,"origin",["remote","add","origin",item["source"]+".git"],target)
            run(name,"promisor",["config","remote.origin.promisor","true"],target)
            run(name,"filter",["config","remote.origin.partialclonefilter","blob:none"],target)
            run(name,"sparse_init",["sparse-checkout","init","--no-cone"],target)
            pattern="/"+item["prefix"]
            run(name,"sparse_set",["sparse-checkout","set","--no-cone",pattern],target)
            run(name,"fetch",["-c","protocol.version=2","fetch","--filter=blob:none","--depth=1","--no-tags","origin",item["commit"]],target)
            run(name,"checkout",["checkout","--detach",item["commit"]],target)
            head=run(name,"head",["rev-parse","HEAD"],target).decode().strip()
            assert head==item["commit"]
            prefix=item["prefix"].split("*")[0]
            tree=run(name,"tree",["ls-tree","-r","-z","-l","--full-tree","HEAD","--",prefix],target)
            metadata=[]
            for entry in tree.split(b"\0"):
                if not entry:continue
                fields,path=entry.split(b"\t",1)
                mode,kind,blob,size=fields.split()
                relative=path.decode("utf8")
                if "*" in item["prefix"] and not fnmatch.fnmatchcase(relative,item["prefix"]):continue
                if kind!=b"blob" or mode not in (b"100644",b"100755"):
                    raise ValueError("Unsupported authorized subtree entry "+relative)
                local=target/relative
                if local.is_symlink() or not local.is_file():
                    raise ValueError("Missing/non-regular acquired input "+relative)
                raw=local.read_bytes()
                actual_blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
                if len(raw)!=int(size) or actual_blob!=blob.decode():
                    raise ValueError("Git object mismatch "+relative)
                metadata.append(dict(corpus=name,repository=item["repository"],commit=head,path=relative,
                    absolute_path=str(local),bytes=len(raw),git_blob_sha1=actual_blob,
                    sha256=hashlib.sha256(raw).hexdigest(),mode=mode.decode()))
            physical=[]
            for directory,dirs,files in os.walk(str(target)):
                if Path(directory)==target:dirs[:]=[d for d in dirs if d!=".git"]
                for filename in files:
                    physical.append(str((Path(directory)/filename).relative_to(target)))
            assert set(physical)=={r["path"] for r in metadata},"Unexpected checked-out paths"
            assert len(metadata)==item["files"],"File count differs from approved tree estimate"
            assert sum(r["bytes"] for r in metadata)==item["bytes"],"Byte count differs from approved tree estimate"
            manifest=folder/"manifest.jsonl.gz"
            with manifest.open("xb") as stream:
                with gzip.GzipFile(filename="",mode="wb",fileobj=stream,mtime=0) as zipped:
                    for row in sorted(metadata,key=lambda r:r["path"]):
                        zipped.write((json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n").encode("utf8"))
            record=dict(name=name,commit=head,destination=str(target),files=len(metadata),
                total_bytes=sum(r["bytes"] for r in metadata),sol_files=sum(r["path"].endswith(".sol") for r in metadata),
                manifest=str(manifest.relative_to(ROOT)),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                all_git_objects_verified=True,all_file_sha256_recorded=True,
                source_content_statistics="not_run_before_taxonomy",passed=True)
            write(folder/"receipt.json",record);rows.append(record)
            print(json.dumps(record,ensure_ascii=False),flush=True)
        write(OUT/"corpus_acquisition_status.json",dict(passed=True,completed=len(rows),corpora=rows,cost_usd=0))
    except Exception as exc:
        write(OUT/"corpus_acquisition_status.json",dict(passed=False,completed=len(rows),corpora=rows,
            exception_type=type(exc).__name__,error=str(exc),cost_usd=0))
        raise

if __name__=="__main__":
    execute()
