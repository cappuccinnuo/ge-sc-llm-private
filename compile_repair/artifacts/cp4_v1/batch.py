"""Fixed CP4 evidence paths and exclusive output writers. Run from the repository root."""
from collections import Counter
from contextlib import contextmanager
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
ART = HERE.parent
OUT = Path(os.environ.get("CP4_OUTPUT", str(HERE))).resolve()
LOCAL = Path(os.environ.get("CP4_SCRATCH", str(ROOT.parent/"compile-repair-local"/HERE.name))).resolve()
BASE = "06ad69c26fcb13c163a55333ab95738bfaf71fdd"
SEED = 20261122


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def frozen(path):
    raw = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()
    if raw != subprocess.check_output(["git","show",BASE+":"+rel], cwd=str(ROOT)):
        raise ValueError("Frozen input changed: " + rel)
    return raw


def checked(path, expected):
    raw = Path(path).read_bytes()
    if sha(raw)!=expected:
        raise ValueError("SHA256 mismatch: " + str(path))
    return raw


def save(name, obj):
    with (OUT/name).open("x",encoding="utf8") as fp:
        json.dump(obj,fp,ensure_ascii=False,indent=2)
        fp.write("\n")


def load(name):
    return json.loads((OUT/name).read_bytes())


@contextmanager
def receipt_stream(name):
    with (OUT/name).open("xb") as file, gzip.GzipFile(filename="", fileobj=file, mode="wb", mtime=0) as gz:
        def write(row):
            gz.write((json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode())
        yield write


def receipt_rows(name):
    with gzip.open(OUT/name,"rt",encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)
