"""CP3 mandatory three-file precondition: exact combined-json and Slither kwargs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from compile_repair.toolchain.solc import load_trusted_compilers, verify_binary, error_first_line
from compile_repair.toolchain.slither import check_profile, node_facts, contract_coverage, read_mapping
from crytic_compile import CryticCompile
from crytic_compile.platform.solc import _build_options, CompilerVersion
from slither import Slither

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path,value):
    with path.open("x",encoding="utf8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,sort_keys=True)
        stream.write("\n")

def emit(row):
    with (OUT/"project_probe_invocations.jsonl").open("a",encoding="utf8") as stream:
        stream.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n")

def execute():
    output=OUT/"project_probe"
    output.mkdir()
    root=ROOT/"compile_repair/tests/fixtures/cp3_project"
    inputs=sorted(root.rglob("*.sol"))
    hashes={str(p):sha(p) for p in inputs}
    assert len(inputs)==3
    profile=check_profile("production")
    compilers,_,_=load_trusted_compilers()
    rows=[]
    for version in ("0.4.12","0.4.24","0.5.17","0.8.38"):
        compiler=compilers[version]
        verify_binary(compiler)
        folder=output/version
        folder.mkdir()
        remaps=["@vendor/=vendor/"]
        target="Main.sol"
        options=_build_options(CompilerVersion("solc",version,False),False)
        command=[compiler.path]+remaps+[target,"--combined-json",options,"--allow-paths","."]
        start=time.monotonic()
        run=subprocess.run(command,cwd=str(root),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        elapsed=time.monotonic()-start
        (folder/"solc.stdout").write_bytes(run.stdout)
        (folder/"solc.stderr").write_bytes(run.stderr)
        diagnostic=run.stderr.decode("utf8",errors="replace")
        compilation=dict(kind="solc",version=version,compiler_sha256=compiler.sha256,command=command,
            cwd=str(root),returncode=run.returncode,error_first_line=error_first_line(diagnostic) if run.returncode else None,
            elapsed_seconds=elapsed,cost_usd=0,stdout_sha256=hashlib.sha256(run.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(run.stderr).hexdigest(),inputs=hashes)
        emit(compilation)
        row=dict(version=version,solc=compilation,slither=None,passed=False)
        if run.returncode==0:
            kwargs=dict(solc=compiler.path,solc_disable_warnings=True,solc_working_dir=str(root),
                solc_remaps=remaps,solc_args="--allow-paths .")
            analysis=dict(profile,kind="slither",version=version,compiler_sha256=compiler.sha256,
                command=dict(api="CryticCompile then Slither",target=target,kwargs=kwargs),
                equivalent_solc_argv=command,cwd=str(root),api_subprocess_returncodes_observed=False,
                constructed=False,d3=False,cost_usd=0)
            start=time.monotonic()
            try:
                crytic=CryticCompile(target,**kwargs)
                analysis["crytic_compile_platform"]=crytic.platform.NAME
                slither=Slither(crytic,**kwargs)
                analysis["constructed"]=True
                facts=node_facts(slither,inputs)
                coverage=contract_coverage(slither,inputs)
                observed=set()
                for contract in slither.contracts:
                    for function in contract.functions_and_modifiers_declared:
                        for node in function.nodes:
                            name=read_mapping(node.source_mapping)["filename"]
                            if name:
                                observed.add(str(Path(name).resolve()))
                analysis.update(node_facts=facts,contract_coverage=coverage,
                    observed_cfg_files=sorted(observed),expected_files=sorted(hashes),
                    all_closure_files_have_cfg_nodes=observed==set(hashes),
                    d3=facts["mapping_complete"] and coverage["complete"])
            except Exception as exc:
                analysis.update(exception_type=type(exc).__name__,error_first_line=str(exc).splitlines()[0] if str(exc) else type(exc).__name__,detail=str(exc))
            analysis["elapsed_seconds"]=time.monotonic()-start
            emit(analysis)
            row["slither"]=analysis
            row["passed"]=analysis["constructed"] and analysis["d3"] and analysis.get("all_closure_files_have_cfg_nodes",False)
        row["inputs_unchanged"]={str(p):sha(p) for p in inputs}==hashes
        row["passed"]=row["passed"] and row["inputs_unchanged"]
        write(folder/"result.json",row)
        rows.append(row)
        print(json.dumps(dict(version=version,solc_rc=run.returncode,passed=row["passed"],
            slither_error=row["slither"].get("error_first_line") if row["slither"] else None)),flush=True)
        if not row["passed"]:
            write(OUT/"project_probe_acceptance.json",dict(passed=False,completed=len(rows),planned=4,rows=rows,stop_reason="CP3 mandatory project precondition mismatch; no alternative parameters attempted"))
            raise SystemExit(2)
    write(OUT/"project_probe_acceptance.json",dict(passed=True,completed=len(rows),planned=4,rows=rows))

if __name__=="__main__":
    execute()
