"""Independently check the CP5 preflight streams, coverage denominators and production scope."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from measurement import OUT, read, sha, write

ROOT=OUT.parents[2]
BASE="26f44492c093311257f7b3de41ba3bee2e703ea3"


def main():
    s=read(OUT/"self_summary.json")
    assert s["passed"]==s["checked"]==16136 and not s["untested"] and s["stopped_at"] is None
    assert sha((OUT/"self_scores.jsonl.gz").read_bytes())==s["stream_sha256"]
    catalog=OUT.parent/"cp4_v1/bases.jsonl.gz"
    assert sha(catalog.read_bytes())==s["base_catalog_sha256"]
    with gzip.open(OUT/"self_scores.jsonl.gz","rt") as fp,gzip.open(catalog,"rt") as bp:
        ids=set()
        for line in bp:
            base=json.loads(line);r=json.loads(next(fp));x=r["score"];proof=x["counter_correspondence"]
            assert base["unit_id"]==r["unit_id"] and r["unit_id"] not in ids and r["graph_sha256"]==base["graph_sha256"]
            assert x["exact"] and proof["status"]=="identical" and proof["nodes"]["name_mismatch"]==proof["nodes"]["disputed"]==0
            ids.add(r["unit_id"])
        assert next(fp,None) is None and len(ids)==16136
    m=read(OUT/"measurement.json")
    stream=OUT/"measurement_units.jsonl.gz"
    assert sha(stream.read_bytes())==m["units_sha256"]
    units=list(map(json.loads,gzip.open(stream,"rt")))
    attrs=OUT.parent/"cp4_1_v1/cp3_attributions.jsonl.gz"
    assert sha(attrs.read_bytes())==m["inputs"]["attributions_sha256"]
    target=set(m["selected_by_primary"])
    selected={u["unit_id"] for u in map(json.loads,gzip.open(attrs,"rt"))
              if target.intersection(set(u["any_categories"])|set(u["primary"]["categories"]))}
    assert {u["unit_id"] for u in units}==selected and len(units)==len(selected)==9144
    assert sum(m["by_corpus"].values())==9144
    checked_counts={}
    missing_sets=[frozenset(u["pending"]) for u in units if u["pending"]]
    frequencies=Counter(k for p in missing_sets for k in p)
    ordered=sorted(frequencies,key=lambda k:(-frequencies[k],k))
    for n in (5,10,20,40,len(ordered)):
        val=sum(not (p-set(ordered[:n])) for p in missing_sets)
        assert m["coverage"]["pending_all_prefixes"][str(n) if n!=len(ordered) else "all"]["fully_covered"]==val
        checked_counts[n]=val
    assert {k for e in m["importer_pragmas"].values() for k in e} and set(frequencies)==set(m["importer_pragmas"])
    by_tier=defaultdict(set)
    for u in units:
        if u["project_root"]:by_tier[u["tier"]].add(u["project_root"])
    sources=read(OUT.parent/"cp4_5_v1/continuation/scope.json")["production_sha256"]
    assert len(sources)==17 and all(sha((ROOT/n).read_bytes())==h for n,h in sources.items())
    tracked=subprocess.check_output(["git","ls-files","compile_repair/*.py"],cwd=ROOT).decode().splitlines()
    assert {p for p in tracked if "/tests/" not in p and "/artifacts/" not in p}==set(sources)
    frozen=read(OUT.parent/"cp3_continue_v1/baseline.json")["code_refs"]
    cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-c",
         "import json;from scripts.DFG.dfg_v2.experiment.run import _code_refs;print(json.dumps(_code_refs()))"]
    assert json.loads(subprocess.check_output(cmd,cwd=ROOT))==frozen
    assert not subprocess.check_output(["git","diff",BASE,"--name-only","--",".",":(exclude)compile_repair"],cwd=ROOT).strip()
    write(OUT/"measurement_verification.json",dict(base=BASE,observations=len(units),self_comparisons=len(ids),
          observed_prefixes_total=len(frequencies),units_with_pending_prefixes=len(missing_sets),
          independent_coverage=checked_counts,projects_with_at_least_one_unit_of_each_tier={t:len(rs) for t,rs in by_tier.items()},
          frozen_production_files=len(sources),frozen_dfg_refs=len(frozen),prompt_sha256=sha((ROOT/"compile_repair/PROMPTS.md").read_bytes())))
    print("16136 self comparisons, 9144 measurement rows,",len(sources),"production modules,",len(frozen),"DFG references checked")

if __name__=="__main__": main()
