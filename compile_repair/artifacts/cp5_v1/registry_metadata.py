"""Acquire only the authorized npm metadata. Never request a release body."""
import base64
import gzip
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit

OUT = Path(__file__).resolve().parent
LOCAL = OUT.parents[3]/"compile-repair-local"/"cp5_v1"/"registry_metadata"
HOST = "registry.npmjs.org"
STABLE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
MIB = 1024**2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(p):
    return json.loads(p.read_bytes())


def write(p,v):
    with p.open("x",encoding="utf8") as fp:json.dump(v,fp,indent=2,ensure_ascii=False,sort_keys=True);fp.write("\n")


def journal(fp,v):
    fp.write(json.dumps(v,sort_keys=True,ensure_ascii=False)+"\n")
    fp.flush()


def approved():
    req=read(OUT/"registry_metadata_request.json")
    auth=read(OUT/"authorization.json")
    assert any(d["id"]=="registry_metadata" and d["status"]=="approved" and
               d["request_sha256"]==digest((OUT/"registry_metadata_request.json").read_bytes()) for d in auth["decisions"])
    assert len(req["packages"])==auth["package_get_limit"]==141 and auth["release_head_limit"]==500
    assert auth["tarball_payload_limit_bytes"]==0 and auth["domain"]=="https://"+HOST
    return req,auth


def connection():
    proxy=urlsplit(os.environ["CP5_HTTPS_PROXY"])
    if proxy.scheme!="http" or not proxy.hostname or not proxy.port or proxy.username:
        raise ValueError("Expected the configured unauthenticated local HTTP CONNECT bridge")
    conn=http.client.HTTPSConnection(proxy.hostname,proxy.port,context=ssl.create_default_context(),timeout=40)
    conn.set_tunnel(HOST,443)
    return conn


def route(url):
    u=urlsplit(url)
    if u.scheme!="https" or u.netloc!=HOST or u.query or u.fragment or not u.path.startswith("/"):
        raise ValueError("URL outside approved host and scheme")
    return u.path


def fetch():
    req,auth=approved()
    LOCAL.mkdir(parents=True,exist_ok=False)
    transferred=decoded=0
    conn=connection();start=time.monotonic()
    with (OUT/"registry_gets.jsonl").open("x",encoding="utf8") as log:
        for i,item in enumerate(req["packages"]):
            name,url=item["name"],item["registry_url"]
            path=route(url)
            if "/-/" in path:raise ValueError("GET is restricted to package metadata")
            t=time.monotonic()
            conn.request("GET",path,headers={"Host":HOST,"User-Agent":"CompileRepair-CP5/1",
                         "Accept":"application/vnd.npm.install-v1+json","Accept-Encoding":"gzip"})
            resp=conn.getresponse()
            info=dict(name=name,url=url,http_status=resp.status,date=resp.getheader("Date"),
                      etag=resp.getheader("ETag"),encoding=resp.getheader("Content-Encoding") or "identity")
            left=auth["wire_body_limit_bytes"]-transferred
            if int(resp.getheader("Content-Length") or 0)>left:
                journal(log,info);raise ValueError("Metadata transfer cap before body")
            raw=resp.read(left)
            if not resp.isclosed():
                if transferred+len(raw)>=auth["wire_body_limit_bytes"]:
                    journal(log,info);raise ValueError("Metadata wire cap")
                resp.close()
            transferred+=len(raw)
            info.update(wire_bytes=len(raw),wire_sha256=digest(raw))
            if resp.status not in (200,404):
                journal(log,info);raise ValueError("Registry returned HTTP "+str(resp.status))
            left=auth["decoded_metadata_limit_bytes"]-decoded
            if info["encoding"]=="gzip":
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:data=g.read(left+1)
            elif info["encoding"]=="identity":data=raw
            else:raise ValueError("Unexpected registry encoding")
            if len(data)>left:raise ValueError("Decoded metadata cap")
            decoded+=len(data)
            obj=json.loads(data)
            record=LOCAL/("{:03d}.response".format(i))
            with record.open("xb") as fp:fp.write(raw)
            versions=obj.get("versions",{})
            info.update(local_path=str(record),json_sha256=digest(data),decoded_bytes=len(data),
                        canonical_name=obj.get("name"),published_versions=len(versions),
                        stable_versions=sum(bool(STABLE.fullmatch(v)) for v in versions),
                        seconds=round(time.monotonic()-t,3))
            journal(log,info)
            if (i+1)%20==0:print("metadata",i+1,flush=True)
    conn.close()
    result=dict(requests=len(req["packages"]),transferred_bytes=transferred,decoded_bytes=decoded,
                elapsed_seconds=round(time.monotonic()-start,3),tarball_body_bytes=0,cost_usd=0,
                journal_sha256=digest((OUT/"registry_gets.jsonl").read_bytes()))
    write(OUT/"registry_get_summary.json",result)
    print(result,flush=True)


def integrity512(dist):
    for part in str(dist.get("integrity","")).split():
        if part.startswith("sha512-"):
            try:
                if len(base64.b64decode(part[7:],validate=True))==64:return part
            except ValueError:pass
    return None


def load_packument(row):
    raw=Path(row["local_path"]).read_bytes()
    assert digest(raw)==row["wire_sha256"]
    data=gzip.decompress(raw) if row["encoding"]=="gzip" else raw
    assert digest(data)==row["json_sha256"]
    return json.loads(data)


if __name__=="__main__":
    fetch()
