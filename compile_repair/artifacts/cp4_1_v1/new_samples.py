"""Execute the frozen CP4.1 sample draw once with the unchanged production pipeline."""
from collections import Counter
from batch import *
from new_plan import SEED, sites_for, signature
from compile_repair.evaluation.benchmark import assess_mutation
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

def perform(row):
    base=BASES[row["unit_id"]]; op=row["operator"]
    sources,sites=sites_for(base)
    if signature(sites[op])!=row["site_sha256"] or row["seed"]!=SEED:
        raise ValueError("Frozen site differs: "+base["unit_id"])
    result=assess_mutation(base,op,SEED,sources,sites[op],COMPILERS,FROZEN,LOCAL/"samples"/op/base["unit_id"])
    return dict(result,cohort="new",package=row.get("package"),site_sha256=row["site_sha256"])

def main():
    global BASES, COMPILERS, FROZEN
    check_profile("production")
    trusted,FROZEN,_=load_trusted_compilers()
    identity=load("baseline.json")["compiler_sha256"]
    COMPILERS={v:trusted[v] for v,d in identity.items() if trusted[v].sha256==d}
    if len(COMPILERS)!=92:raise ValueError("Compiler registry differs")
    BASES={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    spec=load("new_sampling.json");checked(OUT/"new_plan.jsonl.gz",spec["plan_sha256"])
    plan=list(rows(OUT/"new_plan.jsonl.gz"))
    assert spec["planned"]==len(plan)==len({(r["operator"],r["unit_id"]) for r in plan})
    counts=Counter()
    def collect():
        for i,row in enumerate(ordered_work(perform,plan,4),1):
            counts[row["operator"],row["outcome"]]+=1
            if i%100==0:print("new observations",i,"/",len(plan),flush=True)
            yield row
    output_rows("new_observations.jsonl.gz",collect())
    saved("new_execution.json",dict(completed=sum(counts.values()),planned=len(plan),profile="production",
        observations_sha256=sha((OUT/"new_observations.jsonl.gz").read_bytes()),
        counts=[dict(operator=o,outcome=s,units=n) for (o,s),n in sorted(counts.items())]))
    print("new samples",len(plan),dict(counts),flush=True)
if __name__=="__main__":main()
