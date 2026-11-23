"""Resume the remaining D23 URLs once after the recorded pre-response disconnect."""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent))
from registry_metadata import HOST, connection, digest, journal, read, route, write


def main():
    auth=read(OUT/"authorization.json");stop=read(OUT/"transport_stop.json")
    assert read(OUT/"resume_authorization.json")["stop_sha256"]==digest((OUT/"transport_stop.json").read_bytes())
    req=read(OUT.parent/"d23_download_request.json")
    assert digest((OUT.parent/"d23_download_request.json").read_bytes())==auth["request_sha256"]
    prior=(OUT/"download.jsonl").read_bytes();assert digest(prior)==stop["prior_journal_sha256"]
    records=list(map(json.loads,prior.splitlines()));total=sum(r["packed_bytes"] for r in records)
    releases=[(n,r) for n,p in req["by_package"].items() for r in p["releases"]]
    root=Path(auth["storage"]);archives=root/"archives"
    assert len(records)==stop["verified_releases"]==len(list(archives.glob("*.tgz")))
    for (name,release),r in zip(releases,records):
        raw=Path(r["path"]).read_bytes()
        assert r["package"]==name and r["version"]==release["version"] and digest(raw)==r["sha256"]
        assert "sha512-"+base64.b64encode(hashlib.sha512(raw).digest()).decode()==release["integrity"]
    begin=time.monotonic()
    with (OUT/"download_remaining.jsonl").open("x") as log:
        for name,release in releases[len(records):]:
            url=release["registry_url"];version=release["version"];path=route(url)
            conn=connection();t=time.monotonic()
            dst=archives/(digest((name+"@"+version).encode())+".tgz")
            row=dict(package=name,version=version,url=url,path=str(dst),expected_integrity=release["integrity"])
            try:
                conn.request("GET",path,headers={"Host":HOST,"Connection":"close","Accept-Encoding":"identity","User-Agent":"CompileRepair-CP5/1"})
                resp=conn.getresponse();row["http_status"]=resp.status
                if resp.status!=200:raise ValueError("Tarball HTTP "+str(resp.status))
                limit=min(auth["per_release_packed_limit_bytes"],auth["total_packed_limit_bytes"]-total)
                if int(resp.getheader("Content-Length") or 0)>limit:raise ValueError("D23 declared size cap")
                with dst.open("xb") as f:
                    n=0
                    while n<limit:
                        part=resp.read(min(1024**2,limit-n))
                        if not part:break
                        f.write(part);n+=len(part)
                    if n>=limit and not resp.isclosed():raise ValueError("D23 byte cap")
                raw=dst.read_bytes();sri="sha512-"+base64.b64encode(hashlib.sha512(raw).digest()).decode()
                if sri!=release["integrity"] or (release["packed_bytes"] is not None and release["packed_bytes"]!=n):
                    raise ValueError("Release integrity or size mismatch")
                row.update(integrity=sri,sha256=digest(raw),packed_bytes=n,registry_unpacked_bytes=release["unpacked_bytes"],verified=True)
                total+=n;records.append(row)
            except Exception as e:
                journal(log,dict(row,verified=False,error=type(e).__name__,detail=str(e)))
                raise
            finally:conn.close()
            row["elapsed_seconds"]=round(time.monotonic()-t,3)
            journal(log,row)
    assert len(records)==auth["releases"] and total<=auth["total_packed_limit_bytes"]
    record=dict(schema=1,authorization_sha256=digest((OUT/"authorization.json").read_bytes()),packages=auth["packages"],releases=records,
                total_packed_bytes=total,per_release_unpacked_limit_bytes=auth["per_release_unpacked_regular_file_limit_bytes"],
                total_unpacked_limit_bytes=auth["total_unpacked_regular_file_limit_bytes"],cost_usd=0)
    write(root/"archives.json",record)
    write(OUT/"download_summary.json",dict(releases=len(records),packages=auth["packages"],packed_bytes=total,
          resumed=len(records)-stop["verified_releases"],continuation_seconds=round(time.monotonic()-begin,3),
          successful_transfer_seconds=round(sum(r["elapsed_seconds"] for r in records),3),
          local_catalog=str(root/"archives.json"),catalog_sha256=digest((root/"archives.json").read_bytes()),cost_usd=0))
    print("verified",len(records),"archives",total,"bytes")
if __name__=="__main__":main()
