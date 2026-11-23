"""Validate both runs and seal the approved continuation with the first run's evidence."""
from collections import Counter
import gzip
from itertools import zip_longest
import json
from pathlib import Path
import sys

import delivery

OUT=delivery.OUT
LAST=OUT/"continuation"
OLD=OUT.parent/"cp4_4_v1"

def read(p):
    return json.loads(p.read_bytes())

def rows(p):
    with gzip.open(p,"rt",encoding="utf8") as f:yield from map(json.loads,f)

def check_initial():
    import hashlib
    first=read(OUT/"comparison_stop_seal.json")
    assert read(LAST/"authorization.json")["previous_seal_sha256"]==delivery.sha(OUT/"comparison_stop_seal.json")
    for n,h in first["artifacts"].items():
        if n=="initial_code.patch":
            assert hashlib.sha256(gzip.decompress((OUT/(n+".gz")).read_bytes())).hexdigest()==h
        else:assert delivery.sha(OUT/n)==h,n
    initial_counts=read(OUT/"write_semantics_request.json")["counts"]
    assert initial_counts==dict(moves=dict(REF_delete_reference=4,REF_array_initialization=3),
                                 exact=dict(REF_delete_reference=1394,TMP_delete_reference=1,REF_array_initialization=51))
    assert read(OUT/"exact_causes.json")["different_samples"]==678
    assert read(OUT/"moves_causes.json")["different_samples"]==4

def audit():
    check_initial()
    comparisons={}
    sealed=read(OLD/"seal.json")["batch"]
    for mode,target in (("moves",200),("exact",14196),("migration",114)):
        name=mode+".jsonl.gz"
        assert delivery.sha(OLD/name)==sealed[name]
        meta=read(LAST/(mode+"_summary.json"))
        assert meta["units"]==target and not meta["differences"] and meta["status"]=="passed"
        assert meta["sha256"]==delivery.sha(LAST/name)
        count=0; statuses=Counter()
        for a,b in zip_longest(rows(OLD/name),rows(LAST/name)):
            assert a and b
            assert all(a.get(k)==b.get(k) for k in ("unit_id","operator","mutation_sha256","graph_sha256"))
            x,y=a["score"],b["score"]
            assert not b["changed_fields"] and {k:v for k,v in x.items() if k!="counter_correspondence"}=={
                k:v for k,v in y.items() if k!="counter_correspondence"}
            if mode=="migration":assert x==y
            if mode=="exact":assert y["exact"] and y["counter_correspondence"]["status"]=="identical"
            statuses[y["counter_correspondence"]["status"]]+=1
            count+=1
        assert count==target
        comparisons[mode]=dict(count=count,statuses=statuses,changed=0,sha256=meta["sha256"])
    fixtures=read(LAST/"fixture_comparison.json")
    assert len(fixtures)==39
    data=read(LAST/"review_scores.json")
    assert all(r["cp44"]["kept"]==r["cp45"]["kept"] for cases in data.values() for r in cases.values())
    assert data["yul"]["B"]["cp45"]["counter_correspondence"]["nodes"]["candidate"]==16
    assert not data["yul"]["C"]["cp45"]["exact"]
    assert sum(k.startswith("negative_") and not r["cp45"]["exact"] for k,r in fixtures.items())==23
    previous=read(OLD/"proportionality.json")
    assert delivery.sha(OLD/"proportionality.json")==sealed["proportionality.json"]
    for k,old in previous["scores"].items():
        assert old==fixtures["proportionality_"+k]["cp44"]
        assert fixtures["proportionality_"+k]["cp45"]["kept"]["equal"]==(3 if k=="neutral" else 2)
    scope=read(LAST/"scope.json")
    assert scope["production_files"]==17 and scope["unchanged_dfg_code_refs"]==354
    assert all(delivery.sha(delivery.ROOT/n)==v for n,v in scope["production_sha256"].items())
    suites={n:read(LAST/("suites/"+n+"_tests.json")) for n in ("production","mando","dfg")}
    assert all(r["returncode"]==0 for r in suites.values())
    assert "22 passed" in (LAST/"anchor_tests.log").read_text()
    proof=dict(status="passed_after_authorized_continuation",comparisons=comparisons,suites=suites,
               changed_production=scope["changed_production"],initial_stop_seal=delivery.sha(OUT/"comparison_stop_seal.json"),
               authorizations={n:delivery.sha(OUT/n) for n in ("authorization.json","continuation/authorization.json")})
    delivery.write("acceptance.json",proof)
    delivery.write("evidence_seal.json",{p.relative_to(OUT).as_posix():delivery.sha(p) for p in OUT.rglob("*")
                                         if p.is_file() and p.name not in ("README.md","initial_code.patch")})
    print({k:v["count"] for k,v in comparisons.items()})

def seal():
    assert read(OUT/"doc_check.json")["returncode"]==0 and read(OUT/"acceptance.json")["status"].startswith("passed")
    check_initial()
    assert all(delivery.sha(OUT/k)==h for k,h in read(OUT/"evidence_seal.json").items())
    files=sorted(p for p in OUT.rglob("*") if p.is_file() and p.name!="initial_code.patch")
    assert not any(p.is_symlink() or "__pycache__" in p.parts for p in files)
    delivery.write("seal.json",dict(base=delivery.BASE,batch={p.relative_to(OUT).as_posix():delivery.sha(p) for p in files},
                                    deliverables={n:delivery.sha(delivery.MODULE/n) for n in delivery.CODE+delivery.DOCS}))
if __name__=="__main__":
    {"docs":delivery.docs,"audit":audit,"seal":seal,"verify_index":delivery.verify_index}[sys.argv[1]]()
