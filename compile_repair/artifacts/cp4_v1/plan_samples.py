"""Freeze applicability and all seeded draws before observing a single mutation outcome."""
from collections import Counter, defaultdict
from functools import lru_cache
import time
from batch import ART, LOCAL, OUT, SEED, checked, frozen, json, load, receipt_rows, receipt_stream, save, sha
from compile_repair.evaluation.benchmark import OPERATORS, SourceLayout, base_contents, mutation_sites, stratified_sample
from pathlib import Path

@lru_cache(maxsize=96)
def layout(raw):
    return SourceLayout(raw)


def sites_for(base):
    sources=base_contents(base)
    facts={n:layout(raw) for n,raw in sources.items()}
    imports=json.loads(Path(base["result"]["result_path"]).with_name("project.json").read_bytes())["imports"] if base["project_root"] else []
    return sources,mutation_sites(base,sources,facts,imports)


def run():
    start=time.monotonic()
    assert load("control_acceptance.json")["passed"]==200
    approved=load("authorization.json")
    assert approved["request_sha256"]==sha((OUT/"design_review_request.json").read_bytes())
    routes=json.loads(frozen(ART/"cp3_2_v1/d6_cp4_final.json"))["categories"]
    required={r["category"] for r in routes if r.get("cp4_operator")}
    assert required==set(OPERATORS)|{"slither_incomplete"} and len(OPERATORS)==approved["remaining_source_operators"]
    bases={r["unit_id"]:r for r in receipt_rows("bases.jsonl.gz")}
    avail=defaultdict(list);counts=defaultdict(Counter)
    with receipt_stream("applicability.jsonl.gz") as emit:
        for uid,base in bases.items():
            _,sites=sites_for(base); corpus,series=base["corpus"],base["series"]
            emit(dict(unit_id=uid,group=base["group"],split=base["split"],corpus=corpus,series=series,
                      applicable=sorted(sites),not_applicable={op:"no qualifying site: "+OPERATORS[op]
                                                               for op in OPERATORS if op not in sites}))
            for op in OPERATORS:
                key=(op,corpus,series);counts[key]["bases"]+=1
                if op in sites:
                    counts[key]["applicable"]+=1;avail[op,corpus].append(base)
                else:counts[key]["not_applicable"]+=1
    plan=[]
    for op,corpus in sorted(avail):
        selected=stratified_sample(avail[op,corpus],200,SEED,op)
        for base in selected:
            counts[(op,corpus,base["series"])]["sampled"]+=1
            plan.append(dict(unit_id=base["unit_id"],operator=op,corpus=corpus,series=base["series"],
                             split=base["split"],group=base["group"],seed=SEED))
    with receipt_stream("sample_plan.jsonl.gz") as emit:
        for r in plan:emit(r)
    save("sampling.json",dict(seed=SEED,per_operator_corpus_cap=200,planned=len(plan),
         rows=[dict(operator=op,corpus=c,series=v,**counts[op,c,v]) for op,c,v in sorted(counts)],
         historical_only=["slither_incomplete"],without_operator={r["category"]:r["no_source_corruption_operator_reason"]
                         for r in routes if not r["cp4_operator"]},
         applicability_sha256=sha((OUT/"applicability.jsonl.gz").read_bytes()),
         plan_sha256=sha((OUT/"sample_plan.jsonl.gz").read_bytes()),elapsed_seconds=round(time.monotonic()-start,3)))
    print("bases",len(bases),"planned",len(plan),"strata",len(counts),flush=True)


if __name__=="__main__":
    run()
