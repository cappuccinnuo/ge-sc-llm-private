"""Preserve large observation tables as deterministic gzip files for Git and verify lossless restoration."""
import gzip
import hashlib
import shutil
import sys
from pathlib import Path
from population import OUT, load, save, sha256


def pack():
    assert load(OUT/"measurement_completion.json")["status"]=="complete"
    directory=OUT/"packed"
    directory.mkdir(exist_ok=False)
    rows={}
    for p in sorted(OUT.glob("*.jsonl")):
        size=p.stat().st_size
        if size<1024**2:
            continue
        dest=directory/(p.name+".gz")
        with p.open("rb") as inp, dest.open("xb") as disk:
            with gzip.GzipFile(filename="",fileobj=disk,mode="wb",mtime=0) as output:
                shutil.copyfileobj(inp,output,length=1024**2)
        data=hashlib.sha256()
        with gzip.open(dest,"rb") as check:
            for part in iter(lambda:check.read(1024**2),b""):
                data.update(part)
        digest=sha256(p)
        assert data.hexdigest()==digest
        rows[p.name]=dict(bytes=size,sha256=digest,packed=dest.relative_to(OUT).as_posix(),
                          packed_sha256=sha256(dest),packed_bytes=dest.stat().st_size)
    save(OUT/"record_archives.json",dict(threshold_bytes=1024**2,files=rows))
    print("lossless tables",len(rows),flush=True)


def restore():
    for name, receipt in load(OUT/"record_archives.json")["files"].items():
        if Path(name).name != name or not name.endswith(".jsonl") or receipt["packed"] != "packed/"+name+".gz":
            raise ValueError("Unexpected archive member in the table inventory")
        p,dest=OUT/name,OUT/receipt["packed"]
        assert sha256(dest)==receipt["packed_sha256"]
        if p.exists():
            assert p.stat().st_size==receipt["bytes"] and sha256(p)==receipt["sha256"]
            continue
        h=hashlib.sha256()
        length=0
        with gzip.open(dest,"rb") as inp:
            for chunk in iter(lambda:inp.read(1024**2),b""):
                h.update(chunk)
                length+=len(chunk)
        assert length==receipt["bytes"] and h.hexdigest()==receipt["sha256"]
        with gzip.open(dest,"rb") as inp, p.open("xb") as output:
            shutil.copyfileobj(inp, output, length=1024**2)
        assert sha256(p)==receipt["sha256"]


if __name__=="__main__":
    {"pack":pack,"restore":restore}[sys.argv[1]]()
