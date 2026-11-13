"""Read-only descriptive join to sealed historical compiler runs; no bit changes."""
from .common import ROOT,read,ref,write
from .ep6_common import OUT
BASE=ROOT/"scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1"

def main():
    versions=BASE/"version_inventory/versions.json";vs=versions.with_name("versions.seal.json")
    report=BASE/"slither_full/report.json";rs=report.with_name("report.seal.json")
    if read(vs)["versions_sha256"]!=ref(versions)["sha256"] or read(rs)["report_sha256"]!=ref(report)["sha256"]:
        raise ValueError("Historical compiler report seal mismatch")
    inventory=read(versions);runs=read(report);delta=read(OUT/"attribute_delta.json")
    result={}
    for task,record in delta["tasks"].items():
        historical=task.replace("_node","_contract");rows=[]
        for item in record["unknown_pre08_files"]:
            file,sha=item["file"],item["source_sha256"]
            matches=[r for r in inventory["files"] if r["task"]==historical and r["file"]==file and r["source_sha256"]==sha]
            compiled=[r for r in runs["tasks"][historical]["files"] if r["file"]==file and r["source_sha256"]==sha]
            if len(matches)!=1 or len(compiled)!=1:raise ValueError("Compiler/source identity is not unique")
            rows.append(dict(file=file,source_sha256=sha,pragma=item["pragmas"],
                bound_analysis_metadata=item["compiler_metadata"],
                historical_selection=matches[0]["selection"],historical_status=compiled[0]["status"],
                historical_version=compiled[0]["version"],
                distinction="A compiler chosen for a historical validation run is not analysis/deployment version metadata."))
        result[task]=rows
    write(OUT/"compiler_history.json",dict(tasks=result,versions=ref(versions),versions_seal=ref(vs),
        report=ref(report),report_seal=ref(rs),compilation_executed=False,attributes_changed=False))
    print({t:len(r) for t,r in result.items()},flush=True)

if __name__=="__main__":main()
