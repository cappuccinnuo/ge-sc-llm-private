"""Run the two authorized suite retries and the unstarted CP5.1 evaluations under their frozen inputs."""
from pathlib import Path
from collections import Counter
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import time
import traceback
import urllib.request

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from population import ART, LOCAL, OUT, ROOT, load, save, sha256

WORK=LOCAL/"test_environment_resume_v2"
CONTROL=LOCAL/"control_v2"
SOCKET=CONTROL/"worker.sock"
SESSION="cp51formalv2"
PYTHON="/home/zhao/miniconda3/envs/compile-repair-production/bin/python"
MANDO="/home/zhao/miniconda3/envs/mando/bin/python"
STOP='OUT/"test_environment_resume_v2/evaluation_stop.json"'
PART_STOP='OUT/"test_environment_resume_v2/full_partition_stop.json"'


def record(stream,**item):
    stream.write(json.dumps(dict(time=time.time(),**item),sort_keys=True)+"\n")
    stream.flush()
    os.fsync(stream.fileno())


def environment_probes(grant):
    grammar=Path(grant["grammar"]["path"])
    assert sha256(grammar)==grant["grammar"]["sha256"]
    os.environ["TREE_SITTER_LIB_DIR"]=str(grammar.parent)
    program=("import hashlib,json,sys;from scripts.DFG.frontend import parse,library_path;"
             "p=library_path();t=parse('contract CompileRepairProbe { uint value; }');"
             "print(json.dumps(dict(python=sys.version.split()[0],library=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),"
             "root=t.root_node.type,has_error=t.root_node.has_error)))")
    probes={}
    for name,python in (("production",PYTHON),("mando",MANDO)):
        run=subprocess.run([python,"-B","-c",program],cwd=ROOT,capture_output=True,text=True)
        if run.returncode:
            raise RuntimeError(name+" neutral grammar probe failed: "+run.stderr[-650:])
        result=json.loads(run.stdout)
        assert result["library"]==str(grammar) and result["sha256"]==grant["grammar"]["sha256"]
        assert not result["has_error"]
        probes[name]=result
    save(HERE/"grammar_preflight.json",dict(probes=probes,library_dir=str(grammar.parent),compilations=0))


def verify_boot():
    old=OUT/"development_continuation"
    proven=load(old/"wsl_guard_live.json")
    assert proven["wsl_direct_blocked"] and proven["wsl_proxy_expected_egress"]
    boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    previous=load(old/"controller_claim.json")["boot_id"]
    data=dict(boot_id=boot,previous_boot=previous,existing_receipt_sha256=sha256(old/"wsl_guard_live.json"))
    if previous!=boot:
        config=json.loads(Path("/mnt/c/ProgramData/ClaudeClashGuard/config.json").read_text(encoding="utf-8-sig"))
        gateway=subprocess.check_output(["ip","route","show","default"],text=True).split()[2]
        assert gateway==config["BridgeHost"] and subprocess.check_output(["systemctl","is-active","claude-clash-guard.service"],text=True).strip()=="active"
        proxy="http://"+gateway+":17897"
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({"https":proxy,"http":proxy}))
        with opener.open("https://www.cloudflare.com/cdn-cgi/trace",timeout=18) as response:
            match=re.search(r"^ip=([^\r\n]+)",response.read(16384).decode(),re.M)
        denied=False
        try:
            with socket.create_connection(("1.1.1.1",443),timeout=4):pass
        except OSError:
            denied=True
        data.update(wsl_direct_blocked=denied,expected_egress=bool(match and match.group(1)==config["PreflightIP"]))
        assert data["wsl_direct_blocked"] and data["expected_egress"]
    save(HERE/"runtime_guard.json",data)


def staged_drivers():
    # Preserve the original scripts and stop files. Only control paths and the final suite location differ.
    patches={
        "complete_measurements.py":[('OUT/"evaluation_stop.json"',STOP,2)],
        "evaluate_units.py":[('OUT/"evaluation_stop.json"',STOP,1),('OUT/"full_partition_stop.json"',PART_STOP,2)],
        "evaluate_benchmark.py":[('OUT/"evaluation_stop.json"',STOP,1)],
        "merge_partitions.py":[('OUT/"full_partition_stop.json"',PART_STOP,1)],
        "audit.py":[('"frozen_suites" if final','"test_environment_resume_v2/suites" if final',1)],
    }
    directory=WORK/"drivers"
    directory.mkdir(parents=True,exist_ok=False)
    generated={}
    evidence={}
    for name,changes in patches.items():
        source=OUT/name
        code=source.read_text(encoding="utf8")
        for old,new,count in changes:
            assert code.count(old)==count,(name,old)
            code=code.replace(old,new)
        # The existing helpers resolve inputs and deliverables from the original registered batch.
        first,rest=code.split("\n",1)
        code=first+"\nimport sys\nsys.path.insert(0,"+repr(str(OUT))+")\n"+rest
        compile(code,name,"exec")
        target=directory/name
        with target.open("x",encoding="utf8") as out:out.write(code)
        generated[name]=target
        evidence[name]=dict(original_sha256=sha256(source),generated_sha256=sha256(target),
                            changes=changes,generated=str(target))
    save(HERE/"driver_paths.json",evidence)
    spec=importlib.util.spec_from_file_location("cp51_control_v2",generated["complete_measurements.py"])
    control=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(control)
    return generated,control


def run():
    grant=load(HERE/"authorization.json")
    request=load(HERE/"environment_request.json")
    assert sha256(HERE/"environment_request.json")==grant["request_sha256"]
    assert sha256(OUT/"evaluation_stop.json")==request["prior_stop_sha256"]
    assert sha256(OUT/"stage_runs.jsonl")==request["original_stage_log_sha256"]
    assert sha256(OUT/"policy.json")==grant["retain_policy_sha256"]
    assert sha256(ROOT/"compile_repair/pipeline.py")==load(OUT/"policy_application.json")["pipeline_sha256"]
    for name,initial in request["test_results"].items():
        assert sha256(OUT/"frozen_suites"/(name+"_tests.log"))==initial["log_sha256"]
        assert sha256(OUT/"frozen_suites"/(name+"_tests.json"))==initial["status_sha256"]
    verify_boot()
    environment_probes(grant)
    generated,control=staged_drivers()
    def program(stage,script,*args):
        return stage,[PYTHON,"-B","-u",str(generated.get(script,OUT/script)),*args],OUT/(stage+".log"),{}
    suites=HERE/"suites"
    suites.mkdir(exist_ok=False)
    env=dict(CP4_OUTPUT=str(suites),CP4_SCRATCH=str(WORK/"suite_scratch"))
    with (HERE/"stage_runs.jsonl").open("x",encoding="utf8") as log:
        control.run_group([(n+"_frozen_v2_tests",[py,"-B",str(ART/"cp4_v1/run_suite.py"),n],suites/(n+"_driver.log"),env)
                          for n,py in [("production",PYTHON),("mando",MANDO),("dfg",MANDO)]],log)
        control.run_group([("frozen_mando",[PYTHON,"-B","-u",str(OUT/"frozen_mando.py")],LOCAL/"frozen_mando.log",{}),
                 program("benchmark","evaluate_benchmark.py","full"),program("real_full_part0","evaluate_units.py","full0"),
                 program("real_masked","evaluate_units.py","masked"),program("real_full_part1","evaluate_units.py","full1")],log)
        control.run_group([program("merge_full","merge_partitions.py")],log)
        control.run_group([program("final_aggregation","evaluate_benchmark.py","summarize")],log)
        control.run_group([program(name+"_provenance","check_provenance.py",name)
                          for name in ("real_dev","benchmark","real_full","real_masked")],log)
        control.run_group([program("render_results","render_results.py")],log)
    save(OUT/"measurement_completion.json",dict(status="complete",policy_sha256=sha256(OUT/"policy.json"),
        external_summary_sha256=sha256(OUT/"external_summary.json"),benchmark_summary_sha256=sha256(OUT/"benchmark_summary.json"),
        tables_sha256=sha256(OUT/"final_tables.md"),stages_sha256=sha256(HERE/"stage_runs.jsonl"),
        stages_relative_to_batch="test_environment_resume_v2/stage_runs.jsonl",first_attempt_stages_sha256=sha256(OUT/"stage_runs.jsonl")))
    final=[("audit",generated["audit.py"],"final"),("ir",OUT/"review_ir_logs.py"),
           ("invocations",OUT/"seal_results.py","units"),("archives",OUT/"record_archives.py","pack"),
           ("documentation",OUT/"finish_docs.py"),("doc_check",OUT/"check_docs.py","final_doc_check"),("seal",OUT/"seal_results.py","batch")]
    with (WORK/"finalization.jsonl").open("x",encoding="utf8") as journal:
        for name,script,*args in final:
            target=WORK/(name+".log")
            record(journal,stage=name,status="start")
            with target.open("xb") as capture:
                job=subprocess.run([PYTHON,"-B","-u",str(script),*args],cwd=ROOT,stdout=capture,stderr=subprocess.STDOUT)
            record(journal,stage=name,status="complete" if job.returncode==0 else "stopped",returncode=job.returncode,
                   log_sha256=sha256(target))
            if job.returncode:return job.returncode
    return 0


def worker():
    assert os.getuid()==1000 and os.environ.get("TMUX","").split(",",1)[0]==str(SOCKET)
    assert Path(sys.executable).resolve()==Path(PYTHON).resolve()
    sample=subprocess.check_output(["/usr/bin/tmux","-S",str(SOCKET),"display-message","-p","-t",os.environ["TMUX_PANE"],"#{session_name}"],text=True).strip()
    assert sample==SESSION
    with (CONTROL/"worker.log").open("xb") as target:
        os.dup2(target.fileno(),1)
        os.dup2(target.fileno(),2)
        save(HERE/"worker_claim.json",dict(pid=os.getpid(),socket=str(SOCKET),session=sample,
             script_sha256=sha256(Path(__file__)),grant_sha256=sha256(HERE/"authorization.json"),start=time.time()))
        try:
            code=run()
        except Exception:
            traceback.print_exc()
            code=1
    save(CONTROL/"worker_exit.json",dict(returncode=code,unix_time=time.time()))
    return code


def keeper():
    assert os.getuid()==1000 and not (HERE/"worker_claim.json").exists()
    assert load(HERE/"authorization.json")["limit"]==21
    CONTROL.mkdir(mode=0o700,exist_ok=False)
    save(CONTROL/"launch_claim.json",dict(pid=os.getpid(),authorization_sha256=sha256(HERE/"authorization.json")))
    cmd=["/usr/bin/tmux","-f","/dev/null","-S",str(SOCKET)]
    subprocess.run(cmd+["new-session","-d","-s",SESSION,"-c",str(ROOT),PYTHON,"-B","-u",str(Path(__file__).resolve()),"worker"],check=True)
    print("Independent CP5.1 formal evaluation worker started",flush=True)
    done=CONTROL/"worker_exit.json"
    while not done.exists():
        live=subprocess.run(cmd+["has-session","-t",SESSION],capture_output=True)
        if live.returncode and not done.exists():
            raise RuntimeError("Worker stopped without an exit receipt")
        if not done.exists():time.sleep(12)
    return load(done)["returncode"]


if __name__=="__main__":
    if sys.argv[1:]==["worker"]:raise SystemExit(worker())
    if sys.argv[1:]:raise ValueError("Unexpected arguments")
    raise SystemExit(keeper())
