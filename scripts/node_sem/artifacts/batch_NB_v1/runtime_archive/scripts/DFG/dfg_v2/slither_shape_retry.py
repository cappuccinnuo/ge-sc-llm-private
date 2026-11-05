"""Explicit retry of only the failed 0.5.11 supplemental constant cast.

No successful result is rerun. The revised source differs only in byte(1)
being replaced by the size-explicit bytes1(uint8(1)) conversion.
"""
import argparse
import contextlib
import io
import json
import logging
import shutil
from pathlib import Path

from . import slither_shape_supplement as supplement
from . import slither_targeted_probes as base
from .slither_conventions import collect_nodes, sha, write_json
from .validate_slither import inspect_environment

VERSION="dfg-v2-prompt6d2-shape-cast-retry-v1"


def checked_failure(path):
    path=Path(path).resolve()
    seal=json.loads(path.with_name("report.seal.json").read_text())
    if sha(path)!=seal["report_sha256"]:
        raise ValueError("Supplement failed-report seal mismatch")
    report=json.loads(path.read_text())
    if report["version"]!="dfg-v2-prompt6d2-shape-supplement-v1" or report["slither_invocations"]!=2:
        raise ValueError("Unexpected supplemental observation batch")
    failed=[c for c in report["cases"] if c["compiler_version"]=="0.5.11"]
    succeeded=[c for c in report["cases"] if c["compiler_version"]=="0.4.24"]
    if (len(failed)!=1 or failed[0]["status"]!="failed"
        or "Explicit type conversion not allowed" not in failed[0].get("error","")
        or "bytes1" not in failed[0].get("error","")
        or len(succeeded)!=1 or succeeded[0]["status"]!="compiled"):
        raise ValueError("Retry only applies to the recorded 0.5.11 constant-cast failure")
    original=path.parent/"sources"/"ShapeSupplement.sol"
    if sha(original)!=failed[0]["source"]["sha256"]:
        raise ValueError("Archived source SHA mismatch")
    return original


def run(output,trusted_path,failed_path):
    output,trusted_path,failed_path=map(lambda p:Path(p).resolve(),(output,trusted_path,failed_path))
    if output.exists():
        raise ValueError("Refuse to overwrite supplemental syntax retry")
    original=checked_failure(failed_path)
    source=supplement.case_path()
    if source.read_bytes()!=original.read_bytes().replace(b"byte(1)",b"bytes1(uint8(1))"):
        raise ValueError("Supplement retry may only correct the constant cast")
    env=inspect_environment()
    compiler=base.checked_compilers(trusted_path,env)["0.5.11"]
    runtime={str(Path(p).resolve()):sha(p) for p in (__file__,supplement.__file__,base.__file__)}
    output.mkdir(parents=True)
    (output/"sources").mkdir()
    shutil.copyfile(str(source),str(output/"sources"/source.name))
    src=dict(path=str(source),sha256=sha(source))
    invocation=dict(version=VERSION,source=src,original_source=dict(path=str(original),sha256=sha(original)),
                    failed_report=dict(path=str(failed_path),sha256=sha(failed_path)),
                    compiler=compiler,environment=env,runtime_sha256=runtime,
                    trusted_manifest=dict(path=str(trusted_path),sha256=sha(trusted_path)),
                    explicit_retry=True,successful_cases_repeated=0,
                    compiler_source_versions=["0.5.11"],dataset_contracts_invoked=0,
                    compiler_installation_attempted=False,network_requested=False)
    write_json(output/"invocation.json",invocation)
    from slither.slither import Slither
    stdout,stderr=io.StringIO(),io.StringIO()
    handler=logging.StreamHandler(stderr)
    logging.getLogger().addHandler(handler)
    try:
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            analysis=Slither(str(source),solc=compiler["path"],solc_disable_warnings=True)
            nodes=collect_nodes(analysis,source)
            functions=base.collect_functions(analysis)
        case=dict(case="ShapeSupplement.sol",fixture_name=source.name,compiler_version="0.5.11",
                  status="compiled",source=src,nodes=nodes,functions=functions)
    except Exception as exc:
        case=dict(case="ShapeSupplement.sol",fixture_name=source.name,compiler_version="0.5.11",
                  status="failed",source=src,error_type=type(exc).__name__,error=str(exc))
    finally:
        logging.getLogger().removeHandler(handler)
    (output/"0.5.11.stdout.txt").write_text(stdout.getvalue())
    (output/"0.5.11.stderr.txt").write_text(stderr.getvalue())
    write_json(output/"0.5.11.nodes.json",case)
    for p,digest in runtime.items():
        if sha(p)!=digest:raise ValueError("Retry runtime changed")
    if sha(source)!=src["sha256"] or sha(compiler["path"])!=compiler["sha256"]:
        raise ValueError("Source or compiler changed")
    observed=supplement.observations([case])
    report=dict(version=VERSION,cases=[case],observations=observed,compiler=compiler,
                slither_invocations=1,dataset_contracts_invoked=0,
                passed_files=int(case["status"]=="compiled"),
                failed_files=int(case["status"]!="compiled"),
                missing_observations=sum(o["status"]!="observed" for o in observed["0.5.11"].values()),
                failed_report=invocation["failed_report"],successful_cases_repeated=0)
    write_json(output/"report.json",report)
    write_json(output/"report.seal.json",dict(
        version=VERSION,report_sha256=sha(output/"report.json"),
        files={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob("*"))
               if p.is_file() and p.name!="report.seal.json"},runtime_sha256=runtime))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True)
    parser.add_argument("--trusted-compilers",required=True)
    parser.add_argument("--failed-report",required=True)
    args=parser.parse_args()
    result=run(args.output,args.trusted_compilers,args.failed_report)
    print(json.dumps({k:result[k] for k in ("passed_files","failed_files","slither_invocations","missing_observations")},indent=2))
    return 1 if result["failed_files"] or result["missing_observations"] else 0


if __name__=="__main__":
    raise SystemExit(main())
