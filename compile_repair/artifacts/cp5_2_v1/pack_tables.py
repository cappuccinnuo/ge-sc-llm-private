"""Seal per-unit tables for Git while preserving local logs and original paths."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent


def sha(path):
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    packed=HERE/"packed"
    packed.mkdir()
    rows={}
    for src in sorted(HERE.rglob("*.jsonl")):
        rel=src.relative_to(HERE)
        dest=packed/rel.parent/(rel.name+".gz")
        dest.parent.mkdir(parents=True,exist_ok=True)
        count=0
        digest=hashlib.sha256()
        with src.open("rb") as source, dest.open("xb") as raw, gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as out:
            for line in source:
                json.loads(line)
                count+=1
                digest.update(line)
                out.write(line)
        restored=hashlib.sha256()
        with gzip.open(dest,"rb") as f:
            for block in iter(lambda:f.read(1024*1024),b""):
                restored.update(block)
        assert restored.digest()==digest.digest()
        rows[rel.as_posix()]=dict(rows=count,bytes=src.stat().st_size,sha256=digest.hexdigest(),
            packed=dest.relative_to(HERE).as_posix(),packed_bytes=dest.stat().st_size,packed_sha256=sha(dest))
    logs={p.relative_to(HERE).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
          for p in sorted(HERE.rglob("*.log"))}
    with (HERE/"record_archives.json").open("x",encoding="utf8") as f:
        json.dump(dict(tables=rows,local_log_hashes=logs),f,sort_keys=True,indent=2);f.write("\n")


if __name__=="__main__":
    main()
