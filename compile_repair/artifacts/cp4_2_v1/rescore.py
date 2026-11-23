"""Rescore frozen CP4.1 receipts from their checked graph and edit bytes."""
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ART = OUT.parent
OLD = ART/"cp4_v1"
CP41 = ART/"cp4_1_v1"
MIG = CP41/"migration_continuation"
sys.path.insert(0,str(CP41))
from batch import checked, rows, sha
from replay import restore_sample
from restore_scores import verify_graph
from compile_repair.evaluation.benchmark import base_contents, score_graphs


def source_rows():
    seal = json.loads((CP41/"migration_stop_seal.json").read_bytes())["batch_files_excluding_this_seal"]
    for file in ("original_reclassified","new_observations","supplement_observations","retained_scores",
                 "promoted_scores","new_scores"):
        name=file+".jsonl.gz"
        checked(CP41/name,seal[name]["sha256"])
    for f in ("retained_scores","promoted_scores","new_scores"):
        yield from (r for r in rows(CP41/(f+".jsonl.gz")) if r["operator"]!="unresolved_package_import")
    receipt=json.loads((MIG/"acceptance.json").read_bytes())
    for stage,h in receipt["packages"]["score_sha256"].items():
        path=MIG/stage/"package_scores.jsonl"
        checked(path,h)
        yield from rows(path)


def score(row):
    m=mode=="migration"
    k=(row["operator"],row["unit_id"],row["mutation_sha256"])
    base=bases[row["unit_id"]]
    source=base_contents(base)
    ref=row["migration_graph" if m else "graph"]
    actual,_=verify_graph(base,ref["result_path"],ref["result_sha256"],ref["graph_sha256"])
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    manifest,damaged,fixed,d,r=restore_sample(base,source,observations[k],migration=m)
    witness=None
    if m and row["migration"]["migration_counters"].get("yul_switches"):
        witness={}
        for side in ("truth","repaired"):
            v=json.loads((MIG/"yul_continuation/witnesses"/row["unit_id"]/side/"verified.json").read_bytes())
            witness[side]=dict(result=json.loads(checked(v["old_result_path"],v["old_result_sha256"])),
                               combined_json=checked(v["output_path"],v["stdout_sha256"]))
    current=score_graphs(truth,actual,source,damaged,fixed,d,r,ref["solc_returncode"],ref["d3"],
                         file_renames=manifest["file_renames"] if m else None,migration_compilations=witness)
    baseline=row["migration" if m else "score"]
    same=all(current.get(k)==v for k,v in baseline.items())
    return dict(unit_id=k[1],operator=k[0],mutation_sha256=k[2],graph_sha256=ref["graph_sha256"],
                matches_prior=same,score=current)


def main():
    global mode,bases,observations
    mode=sys.argv[1]
    bases={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    observations={(r["operator"],r["unit_id"],r["mutation_sha256"]):r for file in
                  ("original_reclassified","new_observations","supplement_observations")
                  for r in rows(CP41/(file+".jsonl.gz")) if r["outcome"]=="included"}
    assert len(observations)==14196
    seen=set()
    statuses=Counter()
    with (OUT/(mode+".jsonl.gz")).open("xb") as stream, gzip.GzipFile(fileobj=stream,mode="wb",mtime=0,filename="") as fp:
        for r in source_rows():
            if mode=="migration" and r["operator"]!="unresolved_package_import":continue
            k=(r["operator"],r["unit_id"],r["mutation_sha256"])
            assert k not in seen
            seen.add(k)
            result=score(r)
            fp.write((json.dumps(result,sort_keys=True,separators=(",",":"))+"\n").encode())
            status=result["score"]["counter_correspondence"]["status"]
            statuses[status]+=1
            if not result["matches_prior"] or not result["score"]["exact"] or (mode=="exact" and status!="identical"):
                raise ValueError((k,status,result["matches_prior"]))
            if len(seen)%1000==0: print(len(seen),flush=True)
    assert len(seen)==(114 if mode=="migration" else 14196)
    summary=dict(units=len(seen),by_status=statuses,all_prior_fields_equal=True,source="existing checked graph and compilation receipts",
                 sha256=sha((OUT/(mode+".jsonl.gz")).read_bytes()))
    with (OUT/(mode+"_summary.json")).open("x") as fp:json.dump(summary,fp,indent=2);fp.write("\n")
    print(summary,flush=True)


if __name__=="__main__":main()
