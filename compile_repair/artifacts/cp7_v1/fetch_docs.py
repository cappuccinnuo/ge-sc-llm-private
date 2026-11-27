"""Fetch K1: the `docs/` reStructuredText of ethereum/solidity at each supported compiler tag.

Usage: python -B fetch_docs.py <work dir> <docs root> <manifest.json> <version> [<version> ...]
A blob-less clone of https://github.com/ethereum/solidity is made in <work dir>; for each
version, `git archive v<version> docs` is unpacked to <docs root>/<version>/docs (only
.rst files). The manifest records each tag's commit, the git tree id of its docs/
directory and the SHA-256 of every extracted file, so another machine can verify an
identical K1 without trusting this one. The documentation is not committed (GPL-3.0
upstream content; local research use).
"""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

work, root, manifest_path, versions = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:]
clone = work / "solidity"
if not clone.exists():
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                    "https://github.com/ethereum/solidity.git", str(clone)], check=True)
git = lambda *a: subprocess.run(["git", "-C", str(clone)] + list(a), check=True, capture_output=True).stdout
root.mkdir(parents=True, exist_ok=False)
manifest = dict(source="https://github.com/ethereum/solidity", versions={})
for version in versions:
    tag = "v" + version
    commit = git("rev-parse", tag + "^{commit}").decode().strip()
    tree = git("rev-parse", tag + ":docs").decode().strip()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(git("archive", tag, "docs")), mode="r") as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".rst"):
                data = tar.extractfile(member).read()
                target = root / version / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                files[member.name] = hashlib.sha256(data).hexdigest()
    manifest["versions"][version] = dict(tag=tag, commit=commit, docs_tree=tree, rst_files=len(files),
                                         files_sha256=hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest())
manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf8")
print(json.dumps(dict(versions=len(versions), rst_files=sum(v["rst_files"] for v in manifest["versions"].values()))))
