"""CP3 preflight local evidence runner; stops on the first failed command."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def write(name, value):
    with (OUT / name).open("x", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def execute(mode):
    names = {"production": ("compile-repair-production", "compile_repair/tests"),
             "mando": ("mando", "compile_repair/tests"),
             "dfg": ("mando", "scripts/DFG/dfg_v2/tests")}
    environment, target = names[mode]
    temp_parent = Path(tempfile.mkdtemp(prefix="cp3_preflight_" + mode + "_"))
    temp = temp_parent / "pytest"
    command = ["/home/zhao/miniconda3/envs/" + environment + "/bin/python", "-B", "-m", "pytest",
               "-q", "-ra", "-x", "-p", "no:cacheprovider", target, "--basetemp=" + str(temp)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2",
               TREE_SITTER_LIB_DIR="/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64")
    if mode == "production":
        env["PYTHONNOUSERSITE"] = "1"
    started = time.monotonic()
    log = OUT / ("pytest_" + mode + ".log")
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=str(ROOT), env=env, stdout=stream, stderr=subprocess.STDOUT)
    raw = log.read_bytes()
    with (OUT / (log.name + ".gz")).open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw)
    receipt = dict(command=command, cwd=str(ROOT), returncode=result.returncode,
                   elapsed_seconds=time.monotonic() - started, temporary_directory=str(temp),
                   environment={k:env.get(k) for k in ("PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
                       "OMP_NUM_THREADS", "MKL_NUM_THREADS", "TREE_SITTER_LIB_DIR")},
                   log_sha256=hashlib.sha256(raw).hexdigest(), log_bytes=len(raw),
                   log_gzip_sha256=hashlib.sha256((OUT / (log.name + ".gz")).read_bytes()).hexdigest())
    write("pytest_" + mode + ".json", receipt)
    if mode != "dfg":
        prefixes = ("test_cp24_equivalence", "test_real_cp24_cli", "test_real_all_call", "test_real_graph_storage", "test_acceptance_callback", "test_real_empty_branches", "test_frozen_equivalence_all", "test_real_byte_inputs_cli", "test_real_union_stays", "test_production_feature_d3", "test_real_same_version_setting")
        files = {}
        for folder in sorted(temp.iterdir()):
            if folder.is_symlink() or not folder.is_dir() or not folder.name.startswith(prefixes):
                continue
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path.suffix in (".json", ".jsonl") and "distribution" not in path.parts:
                    files[str(path.relative_to(temp))] = path.read_text(encoding="utf8")
        data = json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf8")
        with (OUT / ("test_evidence_" + mode + ".json.gz")).open("xb") as stream:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
                compressed.write(data)
    print(raw.decode("utf8", errors="replace")[-5000:], flush=True)
    print(json.dumps(receipt), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    execute(sys.argv[1])
