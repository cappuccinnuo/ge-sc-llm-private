"""Summarize existing CP2 outputs only; no compilation or label access."""
import json
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
ART=OUT.parent
ROOT=OUT.parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def execute():
    cp0=read(ART/"cp0_v2/recon.json")
    inputs={str((ROOT/r["path"]).resolve()):r for r in cp0["inputs"]}
    store=ART/"cr_store_mando_v1"
    records=[json.loads(line) for line in (store/"manifest.jsonl").read_text().splitlines()]
    accepted=[json.loads(line) for line in (OUT/"ascending1_acceptance.jsonl").read_text().splitlines()]
    by_path={r["inputs"][0]["path"]:r for r in records}
    audit_by_path={r["path"]:r for r in accepted}
    categories=defaultdict(lambda:{"inputs":0,"status":Counter(),"origin":Counter(),"series":Counter(),"flags":Counter()})
    call_kinds=Counter();branches=Counter();marks=Counter()
    graph_files=0
    for rec in records:
        row=inputs[rec["inputs"][0]["path"]]
        cat=categories[row["category"]]
        cat["inputs"]+=1;cat["status"][rec["status"]]+=1
        cat["origin"][rec["plan"]["origin"] if rec["plan"] else "<none>"]+=1
        if rec["selected_version"]:cat["series"][".".join(rec["selected_version"].split(".")[:2])]+=1
        cat["flags"].update(rec["flags"])
        p=store/"units"/rec["unit_id"]/"graph.json"
        if p.exists():
            graph_files+=1;graph=read(p)
            call_kinds.update(c["kind"] for c in graph["calls"])
            branches.update(e["kind"] for e in graph["cfg_edges"])
            marks.update(n["provenance"] for n in graph["nodes"])
    six_differences=[]
    for old in cp0["historical_comparison"]["files"]:
        if old["six_c_status"]!="compared":continue
        path=str((ROOT/old["path"]).resolve());rec=by_path[path]
        if rec["selected_version"]==old["six_c_version"]:continue
        attribution=audit_by_path[path]["cp0_version_attribution"]
        if old["source_sha256"]=="5ec2ee307684c021492194d5e63593834e164bcf878d1cddb48a0b1e1ad13237":
            assert old["six_c_version"]=="0.4.11" and rec["selected_version"]=="0.4.12"
            reason={"kind":"approved_existing_floor_difference","authorization":"attribution_authorization.json"}
        else:
            if attribution["kind"]=="same":raise ValueError("Unexpected 6c attribution")
            reason=attribution
        six_differences.append({"path":old["path"],"sha256":old["source_sha256"],
            "six_c_version":old["six_c_version"],"cp2_version":rec["selected_version"],"reason":reason})
    calls=Counter();elapsed=Counter()
    with (store/"invocations.jsonl").open() as stream:
        for line in stream:
            row=json.loads(line);calls[row["kind"]]+=1;elapsed[row["kind"]]+=row["elapsed_seconds"]
    result={"ascending1":read(OUT/"ascending1_receipt.json"),
      "ascending2":read(OUT/"ascending2_receipt.json") if (OUT/"ascending2_receipt.json").exists() else {"status":"not_run"},
      "replay":read(ART/"cp2_6c_v1/summary.json") if (ART/"cp2_6c_v1/summary.json").exists() else {"status":"not_run"},
      "descending":read(OUT/"descending_receipt.json") if (OUT/"descending_receipt.json").exists() else {"status":"not_run"},
      "categories":categories,"graph_files":graph_files,"calls_by_kind":call_kinds,"cfg_branches":branches,
      "node_marks":marks,"tool_calls":calls,"tool_seconds":elapsed,
      "cp0_attribution_counts":Counter(r.get("cp0_version_attribution",{}).get("kind","unrepaired") for r in accepted),
      "cp0_version_differences":[r for r in accepted if r.get("cp0_version_attribution",{}).get("kind") not in (None,"same")],
      "production_archive_equal":sum(r.get("production_archive_equal",False) for r in accepted),
      "six_c_versions_equal":239-len(six_differences),"six_c_version_differences":six_differences}
    if (OUT/"descending_acceptance.jsonl").exists():
        cross=[json.loads(line) for line in (OUT/"descending_acceptance.jsonl").read_text().splitlines()]
        result["cross_version"]={"files":len(cross),
            "key5_equal":sum(r["cross_version"]["key5"]["equal"] for r in cross),
            "ordered_ir_equal":sum(r["cross_version"]["slithir"]["equal"] for r in cross),
            "selected_versions_differ":sum(r["ascending_version"]!=r["selected_version"] for r in cross),
            "differences":[r for r in cross if not r["cross_version"]["key5"]["equal"] or not r["cross_version"]["slithir"]["equal"]]}
    with (OUT/"cp2_summary.json").open("x",encoding="utf8") as stream:json.dump(result,stream,sort_keys=True,indent=2,ensure_ascii=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ("cp0_version_differences","cross_version")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    execute()
