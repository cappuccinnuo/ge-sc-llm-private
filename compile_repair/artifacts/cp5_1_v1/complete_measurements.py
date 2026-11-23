"""Run each remaining offline stage once after the complete uncapped development measurements."""
import ast
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from population import ART, LOCAL, OUT, ROOT, load, save, sha256

PRODUCTION = "/home/zhao/miniconda3/envs/compile-repair-production/bin/python"
MANDO = "/home/zhao/miniconda3/envs/mando/bin/python"


def record(fp, value):
    fp.write(json.dumps(dict(value, unix_time=time.time()), ensure_ascii=False, sort_keys=True)+"\n")
    fp.flush()
    os.fsync(fp.fileno())


def run_group(plans, log, concurrency=2):
    queue = deque(plans)
    live = {}
    failed = None
    while queue or live:
        while not failed and queue and len(live) < concurrency:
            name, command, output, env = queue.popleft()
            fp = output.open("x", encoding="utf8")
            record(log, dict(stage=name, status="start", command=command, output=str(output)))
            try:
                proc = subprocess.Popen(command, cwd=ROOT, env=dict(os.environ, **env),
                                        stdout=fp, stderr=subprocess.STDOUT)
            finally:
                fp.close()
            live[name] = proc, time.monotonic(), output
        if not live:
            break
        time.sleep(2)
        for name, (proc, started, output) in list(live.items()):
            code = proc.poll()
            if code is None:
                continue
            record(log, dict(stage=name, status="complete" if code == 0 else "stopped", returncode=code,
                             seconds=time.monotonic()-started, output_sha256=sha256(output)))
            del live[name]
            if code and failed is None:
                failed = name
                save(OUT/"evaluation_stop.json", dict(stage=name, returncode=code, output=str(output),
                     reason="Stage failed. No new stages started. In-flight evaluation stops at a unit boundary."))
    if failed:
        raise RuntimeError("Stopped stage: "+failed)


def program(name, script, *arguments):
    return (name, [PRODUCTION, "-B","-u",str(OUT/script)]+list(arguments), OUT/(name+".log"), {})


def freeze_defaults():
    p = load(OUT/"policy.json")
    assert p["status"]=="frozen" and p["policy"] in ("latest","oldest","closest")
    assert type(p["limit"]) is int and p["limit"] >= 1
    source=ROOT/"compile_repair/pipeline.py"
    baseline=load(OUT/"checkpoint_audit.json")["changed"]["pipeline.py"]["sha256"]
    assert sha256(source)==baseline
    old=source.read_text(encoding="utf8")
    new=old
    for needle,value in [
        ("from scripts.DFG.models import Unsupported\n",
         "from scripts.DFG.models import Unsupported\n\n\n# Selected on the CP5.1 development split. Explicit None leaves calibration uncapped.\n"
         + "DEFAULT_DEPENDENCY_POLICY = "+json.dumps(p["policy"])+"\nDEFAULT_DEPENDENCY_LIMIT = "+str(p["limit"])+"\n"),
        ('dependency_policy="latest", environment_only=False, dependency_limit=None, mask_versions=False):',
         'dependency_policy=DEFAULT_DEPENDENCY_POLICY, environment_only=False,\n'
         '                dependency_limit=DEFAULT_DEPENDENCY_LIMIT, mask_versions=False):'),
        ('dependency_policy="latest", dependency_limit=None):',
         'dependency_policy=DEFAULT_DEPENDENCY_POLICY, dependency_limit=DEFAULT_DEPENDENCY_LIMIT):')]:
        assert new.count(needle)==1
        new=new.replace(needle,value)
    ast.parse(new, feature_version=(3,7))
    staged=source.with_name(".cp5_1_frozen_pipeline.tmp")
    with staged.open("x",encoding="utf8",newline="\n") as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    assert sha256(source)==baseline
    staged.chmod(source.stat().st_mode & 0o777)
    os.replace(staged,source)
    save(OUT/"policy_application.json",dict(policy_sha256=sha256(OUT/"policy.json"),previous_pipeline_sha256=baseline,
         pipeline_sha256=sha256(source),policy=p["policy"],limit=p["limit"]))
    doc=ROOT/"compile_repair/CP5_REPORT.md"
    heading="### 使用测试集前的选版记录"
    assert heading not in doc.read_text(encoding="utf8")
    results="，".join(k+" "+str(v["real_d3"])+"/"+str(v["real_units"]) for k,v in p["comparison"].items())
    text=("\n"+heading+"\n\n真实开发集 D3 成功数为 "+results+"。按照开发集的主次指标固定 `"+
          p["policy"]+"`，每个单元最多实际编译 "+str(p["limit"])+" 个依赖版本组合。该上限覆盖所选规则在所有成功开发单元中实际尝试的组合。"
          "规则固定时的开发证据、并列情况及原始测量摘要保存在 `policy.json`，SHA256 为 `"+sha256(OUT/"policy.json")+
          "`。测试集和遮蔽锁版本的参照均在此记录之后运行。\n")
    with doc.open("a",encoding="utf8",newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def main(pid):
    assert Path(sys.executable).resolve()==Path(PRODUCTION).resolve()
    assert not (OUT/"policy.json").exists() and not (OUT/"evaluation_stop.json").exists()
    save(OUT/"completion_claim.json",dict(pid=os.getpid(),wait_for=pid,
         development_population_sha256=sha256(OUT/"population.jsonl.gz"),cost_usd=0,network=False))
    with (OUT/"stage_runs.jsonl").open("x",encoding="utf8") as log:
        while not (OUT/"real_dev_summary.json").is_file():
            command=Path("/proc")/str(pid)/"cmdline"
            if not command.is_file() or b"evaluate_units.py" not in command.read_bytes():
                raise RuntimeError("Uncapped development worker stopped before publishing a complete summary")
            time.sleep(15)
        run_group([program("policy_freeze","evaluate_benchmark.py","freeze")],log)
        freeze_defaults()
        record(log,dict(stage="apply_frozen_policy",status="complete",proof=sha256(OUT/"policy_application.json")))
        suites=OUT/"frozen_suites"
        suites.mkdir(exist_ok=False)
        env=dict(CP4_OUTPUT=str(suites),CP4_SCRATCH=str(LOCAL/"frozen_suites"))
        suite_script=str(ART/"cp4_v1/run_suite.py")
        run_group([(n+"_frozen_tests", [interp,"-B",suite_script,n], suites/(n+"_driver.log"),env)
                   for n,interp in (("production",PRODUCTION),("mando",MANDO),("dfg",MANDO))],log)
        run_group([("frozen_mando",[PRODUCTION,"-B","-u",str(OUT/"frozen_mando.py")],LOCAL/"frozen_mando.log",{}),
                   program("benchmark","evaluate_benchmark.py","full"),
                   program("real_full_part0","evaluate_units.py","full0"),
                   program("real_masked","evaluate_units.py","masked"),
                   program("real_full_part1","evaluate_units.py","full1")],log)
        run_group([program("merge_full","merge_partitions.py")],log)
        run_group([program("final_aggregation","evaluate_benchmark.py","summarize")],log)
        run_group([program(n+"_provenance","check_provenance.py",n) for n in ("real_dev","benchmark","real_full","real_masked")],log)
        run_group([program("render_results","render_results.py")],log)
        save(OUT/"measurement_completion.json",dict(status="complete",policy_sha256=sha256(OUT/"policy.json"),
             external_summary_sha256=sha256(OUT/"external_summary.json"),benchmark_summary_sha256=sha256(OUT/"benchmark_summary.json"),
             tables_sha256=sha256(OUT/"final_tables.md"),stages_sha256=sha256(OUT/"stage_runs.jsonl")))


if __name__ == "__main__":
    main(int(sys.argv[1]))
