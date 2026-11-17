"""Execute one new CP2.4 phase, preserving logs and exact command receipts."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def execute(phase):
    specs = {"reproduction": ("compile-repair-production", "reproduce.py"),
             "regression": ("compile-repair-production", "run_corpus.py"),
             "probes": ("compile-repair-production", "audit_tests.py")}
    environment, script = specs[phase]
    command = ["/home/zhao/miniconda3/envs/" + environment + "/bin/python", "-B", str(OUT / script)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
               TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
    started = time.monotonic()
    path = OUT / (phase + ".log")
    with path.open("xb") as stream:
        result = subprocess.run(command, cwd=str(ROOT), env=env, stdout=stream, stderr=subprocess.STDOUT)
    raw = path.read_bytes()
    with (OUT / (phase + ".log.gz")).open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
            zipped.write(raw)
    receipt = dict(command=command, cwd=str(ROOT), environment=environment,
                   returncode=result.returncode, elapsed_seconds=time.monotonic()-started,
                   log_bytes=len(raw), log_sha256=hashlib.sha256(raw).hexdigest(), cost_usd=0, llm_calls=0)
    with (OUT / (phase + "_invocation.json")).open("x", encoding="utf8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
    print(raw.decode("utf8", errors="replace")[-2500:], flush=True)
    print(json.dumps(receipt), flush=True)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    execute(sys.argv[1])
