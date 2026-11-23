"""D23 acquisition only. Save authorized tarballs outside Git; repair and indexing run offline."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent))
from registry_metadata import HOST, connection, digest, journal, read, route, write


def main():
    req=read(OUT.parent/"d23_download_request.json");auth=read(OUT/"authorization.json")
    assert auth["status"]=="approved" and auth["request_sha256"]==digest((OUT.parent/"d23_download_request.json").read_bytes())
    root=Path(auth["storage"]);root.mkdir(exist_ok=False)
    archives=root/"archives";archives.mkdir()
    conn=connection();total=0;records=[];start=time.monotonic()
    with (OUT/"download.jsonl").open("x") as log:
        for name,data in req["by_package"].items():
            assert data["versions"]==auth["exact_releases"][name]
            for release in data["releases"]:
                url=release["registry_url"];path=route(url);version=release["version"]
                assert "/-/" in path
                dest=archives/(digest((name+"@"+version).encode())+".tgz")
                conn.request("GET",path,headers={"Host":HOST,"User-Agent":"CompileRepair-CP5/1","Accept-Encoding":"identity"})
                response=conn.getresponse();ts=time.monotonic()
                info=dict(package=name,version=version,url=url,path=str(dest),http_status=response.status,expected_integrity=release["integrity"])
                if response.status!=200:
                    journal(log,info);raise ValueError("Tarball HTTP "+str(response.status))
                n=0;h256=hashlib.sha256();h512=hashlib.sha512()
                limit=min(auth["per_release_packed_limit_bytes"],auth["total_packed_limit_bytes"]-total)
                declared=response.getheader("Content-Length")
                if declared is not None and int(declared)>limit:
                    journal(log,dict(info,reason="declared_size_over_limit"));raise ValueError("Tarball over D23 cap")
                with dest.open("xb") as fp:
                    while n<limit:
                        chunk=response.read(min(1024**2,limit-n))
                        if not chunk:break
                        fp.write(chunk);h256.update(chunk);h512.update(chunk);n+=len(chunk)
                if not response.isclosed() and n>=limit:
                    journal(log,dict(info,reason="transfer_limit",packed_bytes=n));raise ValueError("D23 transfer limit")
                response.close();total+=n
                sri="sha512-"+base64.b64encode(h512.digest()).decode()
                ok=sri==release["integrity"] and (release["packed_bytes"] is None or release["packed_bytes"]==n)
                row=dict(info,integrity=sri,sha256=h256.hexdigest(),packed_bytes=n,registry_unpacked_bytes=release["unpacked_bytes"],
                         verified=ok,elapsed_seconds=round(time.monotonic()-ts,3))
                journal(log,row)
                if not ok:raise ValueError("Release identity or length mismatch")
                records.append(row)
                if len(records)%20==0:print("verified",len(records),total,flush=True)
    conn.close();assert len(records)==req["releases"]==172
    record=dict(schema=1,authorization_sha256=digest((OUT/"authorization.json").read_bytes()),packages=req["packages"],
                releases=records,total_packed_bytes=total,per_release_unpacked_limit_bytes=auth["per_release_unpacked_regular_file_limit_bytes"],
                total_unpacked_limit_bytes=auth["total_unpacked_regular_file_limit_bytes"],elapsed_seconds=round(time.monotonic()-start,3),cost_usd=0)
    write(root/"archives.json",record)
    write(OUT/"download_summary.json",dict(releases=len(records),packages=req["packages"],packed_bytes=total,elapsed_seconds=record["elapsed_seconds"],
         local_catalog=str(root/"archives.json"),catalog_sha256=digest((root/"archives.json").read_bytes()),cost_usd=0))
    print("verified",len(records),"archives",total,"bytes",flush=True)
if __name__=="__main__":main()
