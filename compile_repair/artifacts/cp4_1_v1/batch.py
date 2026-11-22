"""CP4.1 local evidence. Run scripts from the dedicated repository root."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ART = HERE.parent
BASE = "e8ec530d81908b5f9cd592d3f1ecae89aa3e63a6"
OUT = Path(os.environ.get("CP41_OUTPUT", str(HERE))).resolve()
LOCAL = Path(os.environ.get("CP41_SCRATCH", str(ROOT.parent / "compile-repair-local" / HERE.name))).resolve()
OLD = ART / "cp4_v1"
sys.path.insert(0, str(ROOT))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(path, digest):
    raw = Path(path).read_bytes()
    if sha(raw) != digest:
        raise ValueError("SHA256 mismatch: " + str(path))
    return raw


def frozen(path):
    raw = Path(path).read_bytes()
    git = subprocess.check_output(["git","show",BASE+":"+str(Path(path).relative_to(ROOT))],cwd=str(ROOT))
    if git != raw:
        raise ValueError("Frozen file differs: " + str(path))
    return raw


def saved(name, data):
    with (OUT/name).open("x",encoding="utf8") as fp:
        json.dump(data,fp,ensure_ascii=False,indent=2)
        fp.write("\n")


def load(name):
    return json.loads((OUT/name).read_bytes())


def rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path,"rt",encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def output_rows(name, records):
    with (OUT/name).open("xb") as fp, gzip.GzipFile(filename="",fileobj=fp,mode="wb",mtime=0) as gz:
        for row in records:
            gz.write((json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode())


def ordered_work(function, values, workers):
    """Bound in-flight work and emit in the frozen input order; do not resubmit failed work."""
    from collections import deque
    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context
    from itertools import islice
    items = iter(values)
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("fork")) as pool:
        pending = deque(pool.submit(function, x) for x in islice(items, workers))
        while pending:
            yield pending.popleft().result()
            for item in islice(items, 1):
                pending.append(pool.submit(function, item))
