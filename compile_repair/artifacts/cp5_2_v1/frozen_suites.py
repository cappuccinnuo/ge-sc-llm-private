"""Guard both sides of each regression run with the approved production-file snapshot."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORK = ROOT.parent / "compile-repair-local" / OUT.name
SUITES = OUT / "frozen_suites"
STOP = OUT / "production_suite_stop.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    with path.open("x", encoding="utf8") as f:
        json.dump(obj, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def snapshot():
    paths = [p for p in (ROOT/"compile_repair").rglob("*.py")
             if not {"artifacts","tests"} & set(p.relative_to(ROOT).parts)]
    assert len(paths) == 18
    return {p.relative_to(ROOT).as_posix():digest(p) for p in paths}


def main():
    authorization = OUT / "production_suite_authorization.json"
    write(authorization, dict(quote="批准冻结源码后限定续跑", source="user reply to production_suite_stop.json",
          utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), first_run_sha256=digest(STOP),
          allowed="One fresh complete production suite, then the first planned mando and DFG suites. Same tests and assertions. Guard all 18 production modules before and after each suite.", cost_usd=0))
    SUITES.mkdir()
    initial = snapshot()
    write(SUITES / "source_freeze.json", dict(modules=initial, authorization_sha256=digest(authorization)))
    env = dict(os.environ,CP4_OUTPUT=str(SUITES),CP4_SCRATCH=str(WORK/"frozen_suites"))
    for suite, profile in (("production","compile-repair-production"),("mando","mando"),("dfg","mando")):
        assert snapshot() == initial
        python = Path.home()/"miniconda3/envs"/profile/"bin/python"
        ran = subprocess.run([str(python),"-B",str(OUT.parent/"cp4_v1/run_suite.py"),suite],cwd=ROOT,env=env)
        final = snapshot()
        write(SUITES/(suite+"_guard.json"),dict(returncode=ran.returncode, all_18_equal=final==initial,
              hashes=final, suite_record_sha256=digest(SUITES/(suite+"_tests.json"))))
        if ran.returncode or final != initial:
            raise SystemExit(ran.returncode or 2)


if __name__ == "__main__":
    main()
