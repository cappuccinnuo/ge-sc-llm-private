"""Read-only acceptance of EP7 frozen sources, history and CPU gates."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from ..io import ROOT,read,checked,write,ref
from .ep7_common import OUT
from .common import PLAN

def frozen_inputs():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    before=read(OUT/"before.json")
    checked(before["prompt"])
    for row in before["frozen_code"]+before["prior_artifacts"]:checked(row)
    for row in before["edge_sources"]:checked(row["snapshot"])
    for name,row in before["documents"].items():
        prefix=(ROOT/name).read_bytes()[:row["bytes"]]
        if hashlib.sha256(prefix).hexdigest()!=row["sha256"]:raise ValueError("Historical documentation changed: "+name)
    if _code_refs()!=before["dfg_code_refs"]:raise ValueError("Frozen runtime list changed")
    load(PLAN)
    changes=subprocess.check_output(["git","diff","--name-only","HEAD"],cwd=str(ROOT),text=True).splitlines()
    allowed=set(before["documents"])
    if any(not p.startswith("scripts/edge_sem/") and p not in allowed for p in changes):
        raise ValueError("Tracked changes outside EdgeSem and append-only docs")
    return dict(passed=True,frozen_sources=len(before["frozen_code"]),prior_artifacts=len(before["prior_artifacts"]),
        dfg_code_refs_unchanged=True,h8_load_passed=True,historical_document_prefixes_unchanged=True,
        allowed_tracked_changes=changes)

def regression():
    result={}
    for name in ("nodesem","dfg","edgesem"):
        folder=OUT/"regression"/name
        value=read(folder/"result.json");checked(value["log"])
        if value["exit_code"]!=0:raise ValueError("Regression failed: "+name)
        tree=ET.parse(str(folder/"junit.xml")).getroot()
        suites=[tree] if tree.tag=="testsuite" else list(tree.iter("testsuite"))
        counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ("tests","failures","errors","skipped")}
        if counts["failures"] or counts["errors"]:raise ValueError("Regression XML failed: "+name)
        result[name]=dict(counts,seconds=value["seconds"],receipt=ref(folder/"result.json"),junit=ref(folder/"junit.xml"))
    return result

def acceptance():
    value=frozen_inputs()
    value["regression"]=regression()
    value["placebo_probes"]={}
    for task in ("reentrancy_node","access_control_node"):
        p=OUT/"placebo_probes"/(task+".json");r=read(p)
        if not all(r[k] is True for k in ("parameters_bitwise_equal","repeated_construct_equal",
             "different_fold_changes_edges","degree_signature_equal","graph_unchanged","tamper_rejected")):
            raise ValueError("Placebo gate failed")
        value["placebo_probes"][task]=ref(p)
    value["approved_adaptations"]=ref(OUT/"approved_adaptations.json")
    value["gpu_executed"]=False;value["formal_fits"]=0
    write(OUT/"cpu_acceptance.json",value)
    write(OUT/"cpu_acceptance.seal.json",dict(acceptance=ref(OUT/"cpu_acceptance.json")))
    return value

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("command",choices=("frozen","accept"));a=p.parse_args()
    print(frozen_inputs() if a.command=="frozen" else acceptance())
