"""Bind new external journals and the authorized additional solc calls to individual CP5.2 units."""
from collections import Counter
from pathlib import Path

from measure import HERE, LOCAL, emit, jsonline, load, save, sha256
from summarize_acceptance import RUN, records


def journal(group, uid, directory):
    path=directory/"invocations.jsonl"
    if not path.is_file():
        raise ValueError("Missing invocation journal: "+str(path))
    with path.open("rb") as stream:
        lines=sum(1 for line in stream)
    return dict(group=group,unit_id=uid,path=str(path),records=lines,bytes=path.stat().st_size,sha256=sha256(path))


def unit_store(path, uid):
    unit=next(d for d in Path(path).parents if d.name==uid and d.parent.name=="units")
    return unit.parents[1]


def evidence():
    yield journal("mando","846_inputs",LOCAL/"mando")
    for i in range(4):
        prefix="real_{:02d}".format(i)
        for r in records(RUN/(prefix+".jsonl"),load(RUN/(prefix+".json"))["sha256"]):
            yield journal("external",r["unit_id"],unit_store(r["result_path"],r["unit_id"]))
    for r in records(RUN/"benchmark_rerun.jsonl",load(RUN/"benchmark_rerun.json")["sha256"]):
        yield journal("benchmark/"+r["operator"],r["unit_id"],unit_store(r["result_path"],r["unit_id"]))
    for r in records(RUN/"v2_observations.jsonl",load(RUN/"v2_summary.json")["sha256"]):
        uid=r["plan"]["unit_id"]
        for stage in ("trigger","inverse","repair"):
            yield journal("moved_v2/"+stage,uid,LOCAL/"continuation/moved_v2"/uid/stage)
    for r in records(HERE/"ir_argument_differences.jsonl",load(RUN/"authorization.json")["units_sha256"]):
        uid=r["unit_id"]
        folder=LOCAL/"continuation/ir_solc"/uid
        yield dict(group="historical_cp3_solc",unit_id=uid,path=str(folder/"compilation.json"),records=1,
                   claim_sha256=sha256(folder/"claim.json"),sha256=sha256(folder/"compilation.json"))
    for cohort in ("real_dev","benchmark","cp3"):
        path=RUN/("ir_"+cohort+".jsonl")
        counts=load(RUN/("ir_"+cohort+".json"))
        assert sha256(path)==counts["sha256"]
        yield dict(group="partial_ir/"+cohort,unit_id=cohort,path=str(path),records=counts["counts"]["units"],sha256=counts["sha256"])


if __name__=="__main__":
    counts, totals=Counter(),Counter()
    with jsonline("invocation_index") as log:
        for row in evidence():
            emit(log,row)
            counts[row["group"]]+=1
            totals[row["group"]]+=row["records"]
    save(HERE/"invocation_summary.json",dict(files=counts,journal_records=totals,sha256=sha256(HERE/"invocation_index.jsonl")))
