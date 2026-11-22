"""Run the designated suite in its profile, keeping the first exit and full log."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

batch = Path(__file__).resolve().parent
root = batch.parents[2]
name = sys.argv[1]
suite = {"production": "compile_repair/tests", "mando": "compile_repair/tests",
         "dfg": "scripts/DFG/dfg_v2/tests"}[name]
scratch = Path(os.environ.get("CP4_SCRATCH", str(root.parent / "compile-repair-local" / batch.name))) / ("tests_" + name)
scratch.parent.mkdir(parents=True, exist_ok=True)
assert not scratch.exists()
command = [sys.executable, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
           suite, "--basetemp=" + str(scratch)]
env = dict(os.environ, CUDA_VISIBLE_DEVICES="", PYTHONDONTWRITEBYTECODE="1",
           OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
start = time.monotonic()
output = Path(os.environ.get("CP4_OUTPUT", str(batch)))
log = output / (name + "_tests.log")
with log.open("x") as fp:
    result = subprocess.run(command, cwd=str(root), env=env, stdout=fp, stderr=subprocess.STDOUT)
last = log.read_text().splitlines()[-1]
with (output / (name + "_tests.json")).open("x") as fp:
    json.dump(dict(command=command, cwd=str(root), elapsed_seconds=round(time.monotonic()-start, 3),
                   returncode=result.returncode, summary=last), fp, indent=2)
    fp.write("\n")
print(name, last, flush=True)
sys.exit(result.returncode)
