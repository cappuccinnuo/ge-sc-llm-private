"""Losslessly package sealed CP2.2 stores; retain original local files."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import sys

OUT=Path(__file__).resolve().parent
ART=OUT.parent


def package(name):
    assert name in ("cp2_6c_v3","cp2_desc_v1")
    source=ART/name
    seal=json.loads((source/"seal.json").read_text())
    members=dict(seal["files"])
    members["seal.json"]=hashlib.sha256((source/"seal.json").read_bytes()).hexdigest()
    for relative,expected in members.items():
        if hashlib.sha256((source/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError("Sealed file changed: "+relative)
    archive=source/"store.tar.gz"
    with archive.open("xb") as raw:
        with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as zipped:
            with tarfile.open(mode="w",fileobj=zipped,format=tarfile.PAX_FORMAT) as tar:
                for relative in sorted(members):
                    data=(source/relative).read_bytes()
                    info=tarfile.TarInfo(relative)
                    info.size=len(data);info.mode=0o644;info.mtime=0
                    tar.addfile(info,io.BytesIO(data))
    observed={}
    with tarfile.open(archive,"r:gz") as tar:
        for member in tar:
            if not member.isfile() or member.name in observed:
                raise ValueError("Nonregular/duplicate archive member")
            observed[member.name]=hashlib.sha256(tar.extractfile(member).read()).hexdigest()
    if observed!=members:raise ValueError("Archive readback changed bytes")
    result={"store":name,"files":len(members),"raw_bytes":sum((source/p).stat().st_size for p in members),
            "archive_bytes":archive.stat().st_size,"archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
            "member_sha256":members,"readback_equal":True,"original_files_retained":True}
    with (OUT/(name+"_archive_audit.json")).open("x",encoding="utf8") as stream:
        json.dump(result,stream,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!="member_sha256"}),flush=True)


if __name__=="__main__":
    package(sys.argv[1])
