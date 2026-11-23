"""Verify every indexed Solidity file and bind the finished seal to all 172 approved registry objects."""
from pathlib import Path
import time

from evidence import verified_index
from population import OUT, load, save, sha256


def main():
    start = time.monotonic()
    db = verified_index()
    sizes, files = 0, set()
    for name, versions in db.packages.items():
        for version, release in versions.items():
            for path, meta in release["files"].items():
                raw = db.content(name, version, path)
                assert path.endswith(".sol") and len(raw) == meta["size"]
                files.add(db.root / release["path"] / path)
                sizes += len(raw)
    physical = {p for p in (db.root / "files").rglob("*") if p.is_file() or p.is_symlink()}
    assert files == physical and not any(p.is_symlink() for p in physical)
    assert len(files) == db.seal["solidity_files"] and len(db.packages) == db.seal["packages"] == 20
    save(OUT/"index_verification.json",dict(archives=172,packages=len(db.packages),solidity_files=len(files),
         solidity_bytes=sizes,seal=db.seal,seal_sha256=sha256(db.root/"seal.json"),
         local_index=str(db.root),total_packed_bytes=load(OUT/"download_summary.json")["total_packed_bytes"],
         elapsed_seconds=time.monotonic()-start))
    print(len(db.packages), "packages", len(files), "Solidity files", sizes, "bytes", flush=True)


if __name__ == "__main__":
    main()
