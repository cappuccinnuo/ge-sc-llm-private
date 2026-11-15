"""Read-only final CP2.2 summaries from sealed runs and test receipts."""
import json
from collections import Counter
from pathlib import Path
import sys
import hashlib

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
ART=OUT.parent


def read(p):
    return json.loads(p.read_text(encoding="utf8"))


def write(name,value):
    with (OUT/name).open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")


def rows(p):
    return [json.loads(s) for s in p.read_text().splitlines()]


def execute():
    replay=read(ART/"cp2_6c_v3/summary.json")
    audit=read(OUT/"captured_replay_audit.json")
    desc=read(OUT/"descending_receipt.json")
    assert replay["passed"] and audit["passed"] and desc["passed"]
    ascstore=ART/"cr_store_mando_v3"; descstore=ART/"cp2_desc_v1"
    asc={r["inputs"][0]["path"]:r for r in rows(ascstore/"manifest.jsonl")}
    descending={r["inputs"][0]["path"]:r for r in rows(descstore/"manifest.jsonl")}
    acceptance=rows(OUT/"descending_acceptance.jsonl")
    assert len(asc)==len(descending)==len(acceptance)==846
    comparisons=[];distribution={};pairs=Counter()
    for r in acceptance:
        path=r["path"];a=asc[path];d=descending[path]
        assert r["selected_version"]==d["selected_version"]
        cat=Path(path).parts[-3]
        group=distribution.setdefault(cat,{"files":0,"status":Counter(),"origins":Counter(),
            "versions":Counter(),"series":Counter(),"flags":Counter()})
        group["files"]+=1;group["status"][r["status"]]+=1
        group["origins"][str(r["origin"])]+=1;group["flags"].update(r["flags"])
        if r["status"]!="success":
            assert d["reason"]==a["reason"]=="slither_side_failure"
            continue
        group["versions"][r["selected_version"]]+=1
        group["series"][".".join(r["selected_version"].split(".")[:2])]+=1
        ag=read(ascstore/"units"/a["unit_id"]/"graph.json")
        dg=read(descstore/"units"/d["unit_id"]/"graph.json")
        def keys(g):
            return Counter(tuple(n["key5"]) for n in g["nodes"])
        def with_ir(g):
            return Counter((tuple(n["key5"]),tuple(n["ir"])) for n in g["nodes"])
        samekeys=keys(ag)==keys(dg); sameir=with_ir(ag)==with_ir(dg)
        assert samekeys==r["cross_version"]["key5"]["equal"]
        assert sameir==r["cross_version"]["slithir"]["equal"]
        sameversion=a["selected_version"]==d["selected_version"]
        assert not sameversion or (samekeys and sameir)
        pairs[a["selected_version"]+" -> "+d["selected_version"]]+=1
        comparisons.append(dict(path=path,source_sha256=r["source_sha256"],
            ascending_version=a["selected_version"],descending_version=d["selected_version"],
            same_version=sameversion,key5_equal=samekeys,ordered_ir_equal=sameir,
            source_length_equal=r["cross_version"]["source_length"]["equal"],
            differences=r["cross_version"] if not (samekeys and sameir) else None))
    result=dict(passed=True,source="production profile; cr_store_mando_v3 vs cp2_desc_v1",
        successful_files=len(comparisons),same_version=sum(r["same_version"] for r in comparisons),
        different_version=sum(not r["same_version"] for r in comparisons),
        key5_equal=sum(r["key5_equal"] for r in comparisons),
        key5_and_ir_equal=sum(r["key5_equal"] and r["ordered_ir_equal"] for r in comparisons),
        different_entries=[r for r in comparisons if not (r["key5_equal"] and r["ordered_ir_equal"])],
        source_length_equal=sum(r["source_length_equal"] for r in comparisons),
        version_pairs=dict(sorted(pairs.items())),distribution=distribution,files=comparisons,
        compilation_calls_in_audit=0)
    assert len(comparisons)==843 and result["key5_and_ir_equal"]==desc["key5_and_ir_equal"]
    write("descending_comparison.json",result)
    tests={}
    for mode in ("production","mando","dfg"):
        r=read(OUT/("pytest_"+mode+".json"))
        assert r["returncode"]==0
        lines=(OUT/("pytest_"+mode+".log")).read_text().splitlines()
        tests[mode]=dict(returncode=0,elapsed_seconds=r["elapsed_seconds"],
            summary=next(s for s in reversed(lines) if " passed" in s),
            command=r["command"],log_sha256=r["log_sha256"])
    write("cp2_2_summary.json",dict(schema="cp2.2-summary-v1",acceptance_passed=True,
        replay=replay,replay_audit={k:v for k,v in audit.items() if k not in ("files","unstable_facts")},
        descending={k:v for k,v in result.items() if k not in ("files","distribution")},
        descending_elapsed_seconds=desc["elapsed_seconds"],descending_status_counts=desc["observed_status_counts"],
        tests=tests,production_code_modified=False,old_artifacts_modified=False,
        downloads=0,installations=0,llm_calls=0,cost_usd=0,
        note="Acceptance complete; independent review still required before CP3."))
    print(json.dumps({"replay":replay,"descending":{k:v for k,v in result.items() if k not in
        ("files","distribution","version_pairs")},"tests":tests},ensure_ascii=False,indent=2))


if __name__=="__main__":
    execute()
