"""Seal the deliverable and the original invocation journals without distributing contracts or compiler output."""
import gzip
import hashlib
import json
from pathlib import Path
import time

from population import LOCAL, OUT, ROOT, load, save, sha256


def folders(stage):
    observations = OUT/(stage+".jsonl")
    summary = load(OUT/(stage+"_summary.json"))
    assert sha256(observations)==summary["rows_sha256"]
    with observations.open(encoding="utf8") as stream:
        for row in map(json.loads,stream):
            if stage in ("benchmark","package_dev"):
                run=LOCAL/stage/row["policy"]/row["operator"]/row["unit_id"]
            else:
                run=Path(row["result_path"]).parents[2]
            yield row,run


def unit_seals():
    output=OUT/"invocation_seals.jsonl.gz"
    counts={}
    start=time.monotonic()
    with gzip.GzipFile(filename=str(output),mode="xb",mtime=0) as fp:
        for stage in ("real_dev","package_dev","benchmark","real_full","real_masked"):
            count=0
            for r,run in folders(stage):
                unit=run/"units"/r["unit_id"]
                steps=unit/"repair_steps.json"
                audit={"result.json":sha256(unit/"result.json")}
                if steps.is_file():
                    audit["repair_steps.json"]=sha256(steps)
                    for s in load(steps):
                        if "receipt" in s:
                            ref=run/s["receipt"]
                            audit[ref.relative_to(unit).as_posix()]=sha256(ref)
                            if s["status"]=="success":
                                c=load(ref)["attempts"][-1]["slither"]
                                assert c["d3"] and c["graph_usable"] and c["graph_sha256"]==sha256(ref.with_name("graph.json"))
                recorded=Path(r["result_path"])
                assert sha256(recorded)==r["result_sha256"]
                item=dict(stage=stage,policy=r.get("rule",r.get("policy")),operator=r.get("operator"),unit_id=r["unit_id"],
                    unit_store=str(run),journal_sha256=sha256(run/"invocations.jsonl"),receipts=audit)
                fp.write((json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n").encode())
                count+=1
            counts[stage]=count
    expected={"real_dev":6948,"package_dev":24,"benchmark":2664,"real_full":9138,"real_masked":219}
    assert counts==expected
    save(OUT/"invocation_seals.json",dict(rows=counts,sha256=sha256(output),elapsed_seconds=time.monotonic()-start))


def seal():
    assert load(OUT/"final_audit.json")["mando_implementation_matches_worktree"]
    assert load(OUT/"final_doc_check.json")["returncode"]==0 and (OUT/"invocation_seals.json").exists()
    evidence={p.relative_to(OUT).as_posix():dict(bytes=p.stat().st_size,sha256=sha256(p))
              for p in sorted(OUT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    save(OUT/"seal.json",dict(schema=1,baseline="5fe7671fb6ebe6c9393bf41e29c0cfea950861e8",
         local_only_native_logs=load(OUT/"partial_ir_summary.json")["local_only_log_paths"],
         files_excluding_this_seal=evidence,prompt_sha256=sha256(ROOT/"compile_repair/PROMPTS.md"),
         final_pipeline_sha256=sha256(ROOT/"compile_repair/pipeline.py"),cost_usd=0))
    print(len(evidence),"sealed evidence files",flush=True)


if __name__=="__main__":
    import sys
    {"units":unit_seals,"batch":seal}[sys.argv[1]]()
