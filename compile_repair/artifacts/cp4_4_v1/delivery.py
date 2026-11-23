"""Audit official CP4.4 results against the frozen CP4.3 run and the two approved decisions."""
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
MODULE=OUT.parents[1]
ROOT=MODULE.parent
BASE="8739c653408e9da9f3a7da27dbe944d1fc14415c"
DOCS=("CP4_REPORT.md","PROGRESS.md","docs/CHANGE_LOG.md","docs/DECISIONS.md","docs/HANDOVER.md")
CODE=("evaluation/benchmark.py","tests/test_cp42.py","tests/test_cp43.py","tests/test_cp44.py")
MANDO="/home/zhao/miniconda3/envs/mando/bin/python"

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def write(path,value):
    with path.open("x",encoding="utf8") as fp:json.dump(value,fp,ensure_ascii=False,indent=2,sort_keys=True);fp.write("\n")
def frozen(n):
    return subprocess.check_output(["git","show",BASE+":compile_repair/"+n],cwd=ROOT)
def records(file):
    with gzip.open(file,"rt",encoding="utf8") as fp:
        yield from map(json.loads,fp)

def audit():
    approval=read(OUT/"acceptance_authorization.json")
    assert all(sha(OUT/n)==v for n,v in approval["evidence_sha256"].items())
    assert [x["user_quote"] for x in approval["decisions"]]==["保留主指标，另列长度变化节点","接受这一个差值，继续验收"]
    old=OUT.parent/"cp4_3_v1"
    sealed=read(old/"seal.json")["batch"]
    assert all(sha(old/n)==v for n,v in sealed.items())
    summaries={}
    for mode,target in (("exact",14196),("migration",114),("moves",200)):
        f=mode+".jsonl.gz";meta=read(OUT/(mode+"_summary.json"))
        assert sha(OUT/f)==meta["sha256"] and meta["units"]==target and meta["solc_runs"]==meta["slither_runs"]==0
        ids=set();deltas=[]
        for before,now in itertools.zip_longest(records(old/f),records(OUT/f)):
            assert before and now
            key=tuple(now.get(n) for n in ("unit_id","operator","mutation_sha256"))
            assert key==tuple(before.get(n) for n in ("unit_id","operator","mutation_sha256")) and key not in ids
            ids.add(key)
            assert before["graph_sha256"]==now["graph_sha256"]
            prior,s=before["score"],now["score"]
            diffs={k:dict(cp43=prior[k],cp44=s[k]) for k in prior.keys()|s.keys()
                   if (k!="counter_correspondence" or mode=="migration") and prior[k]!=s[k]}
            if diffs:deltas.append(dict(unit_id=key[0],fields=diffs))
            assert sorted(diffs)==now["changed_fields"]
            if mode in ("exact","migration"):
                assert s["exact"] and s["removed_by_repair"]==0
            if mode=="exact":assert s["counter_correspondence"]["status"]=="identical"
        assert len(ids)==target
        if mode=="moves":
            assert len(deltas)==len(meta["differences"])==1 and deltas[0]["unit_id"]=="cp3_00291"
            detail=read(OUT/"movement_difference.json")
            assert deltas[0]["fields"]==detail["changed_fields"]==meta["differences"][0]["fields"]
            assert set(deltas[0]["fields"])=={"calls","kept","surviving"}
            assert len(detail["nodes"])==3 and sum(x["matches_after"] for x in detail["nodes"])==1
            assert len(detail["calls"])==1 and len(detail["renamed"])==3
            assert meta["status"]=="comparison_stop" and meta["counts"]["surviving_all_equal"]==199
        else:
            assert not deltas and not meta["differences"] and meta["status"]=="passed"
        summaries[mode]=dict(units=target,differing_units=len(deltas),elapsed_seconds=meta["elapsed_seconds"],
                             counts=meta["counts"],sha256=meta["sha256"])
    review=read(OUT/"review_scores.json"); facts=read(OUT/"fixture_facts.json")
    for kind,expected in (("partial",[(7,"verified"),(6,"verified"),(6,"identical")]),
                          ("yul",[(16,"verified"),(16,"verified"),(14,"partial")])):
        for key,(count,status) in zip("ABC",expected):
            s=review[kind][key]["score"];p=s["counter_correspondence"]
            assert s["kept"]["equal"]==count and p["status"]==status
            assert sum(p["nodes"].values())==s["kept"]["units"]-s["missing_kept"]
            assert len(facts[kind][key]["unequal"])==s["kept"]["units"]-count
    b=review["yul"]["B"]
    assert b["score"]["counter_correspondence"]["nodes"]["structural"]==len(b["non_ir_differences"])==3
    assert all(x["fields"]==["length"] and x["new_length"]-x["old_length"]==20 and x["raw_equal"] for x in b["non_ir_differences"])
    assert not review["yul"]["C"]["score"]["exact"]
    wrong=read(OUT/"negative.json")
    assert wrong["wrong_repairs_detected"]==22 and wrong["missing_node_detected"]==1
    assert len(wrong["rows"])==23 and all(not row["score"]["exact"] for row in wrong["rows"])
    assert len(facts["wrong_counter_uses"])==2 and all(not s["exact"] for s in facts["wrong_counter_uses"].values())
    tests={n:read(OUT/("suites/"+n+"_tests.json")) for n in ("production","mando","dfg")}
    assert all(r["returncode"]==0 for r in tests.values())
    scratch=Path(next(s for s in tests["production"]["command"] if s.startswith("--basetemp=")).split("=",1)[1])
    prop,=[p for p in scratch.glob("test_one_constant_edit_per_kep*/proportionality.json") if not p.parent.is_symlink()]
    proportional=read(prop)
    assert {k:s["kept"]["equal"] for k,s in proportional.items()}=={"neutral":3,"11":2,"22":2,"33":2}
    external={}
    for p in sorted(prop.parent.glob("*/*.json")):
        if p.name in ("solc.json","slither.json"):external[str(p)]=sha(p)
    write(OUT/"proportionality.json",dict(scores=proportional,external_receipts=external,score_sha256=sha(prop)))
    review_receipts=read(OUT/"review_inputs.json")
    review_root=ROOT.parent/"compile-repair-local"/OUT.name/"review"
    compilers=set()
    for kind,items in review_receipts.items():
        for k,refs in items.items():
            base=review_root/kind/k
            assert all(sha(base/n)==h for n,h in refs.items())
            sol,sl=read(base/"solc.json"),read(base/"slither.json")
            assert sol["returncode"]==0 and sl["d3"] and sl["profile"]=="production"
            compilers.add((sol["compiler"]["version"],sol["compiler"]["sha256"],sl["slither_version"],sl["crytic_compile_version"]))
    assert len(compilers)==1
    scope=read(OUT/"scope.json")
    assert scope["production_files"]==17 and scope["unchanged_dfg_code_refs"]==354
    assert all(sha(ROOT/n)==v for n,v in scope["production_sha256"].items())
    inputs=["PROMPTS.md","docs/HANDOVER.md","docs/CHANGE_LOG.md","docs/DECISIONS.md","CP4_REPORT.md",
            "artifacts/cp4_3_v1/seal.json"]+["artifacts/cp4_3_review_v1/"+n for n in
              ("README.md","probe_partial_change.py","probe_partial_change.json","probe_yul_switch.py","probe_yul_switch.json")]
    write(OUT/"acceptance.json",dict(base=BASE,self_check="passed_with_two_user_decisions",history=summaries,
        review={k:{i:v["score"]["kept"] for i,v in ss.items()} for k,ss in review.items()},
        profiles=list(compilers),tests={n:r["summary"] for n,r in tests.items()},prior_batch_files_verified=len(sealed),
        frozen_inputs_sha256={n:hashlib.sha256(frozen(n)).hexdigest() for n in inputs},wrong_cp4=22,missing_control=1,
        new_wrong_counter_uses=2,cost_usd=0,llm_calls=0,training_runs=0,independent_review="pending"))
    scientific={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob("*") if p.is_file() and p.suffix!=".md"}
    write(OUT/"evidence_seal.json",dict(files=scientific,code={n:sha(MODULE/n) for n in CODE}))

def docs(name):
    targets=[]
    for n in DOCS:
        filename="compile_repair/"+n
        if n in DOCS[:3]:
            prefix=frozen(n);assert (ROOT/filename).read_bytes().startswith(prefix)
            filename+=":"+str(len(prefix))
        targets.append(filename)
    targets.append((OUT/"README.md").relative_to(ROOT).as_posix())
    cmd=[MANDO,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    rows=[json.loads(line) for line in r.stdout.splitlines()]
    write(OUT/name,dict(command=cmd,returncode=r.returncode,records=rows,stderr=r.stderr.decode()))
    assert r.returncode==0 and len(rows)==6 and all(x["passed"] for x in rows)
    print("6 documents passed")

def seal():
    assert read(OUT/"doc_check.json")["returncode"]==0
    assert read(OUT/"acceptance.json")["self_check"]=="passed_with_two_user_decisions"
    paths=list(OUT.rglob("*"))
    assert all(not p.is_symlink() and "__pycache__" not in p.parts for p in paths)
    write(OUT/"seal.json",dict(base=BASE,batch={p.relative_to(OUT).as_posix():sha(p) for p in paths if p.is_file()},
                               deliverables={n:sha(MODULE/n) for n in CODE+DOCS}))
def verify():
    s=read(OUT/"seal.json")
    for base,refs in ((OUT,s["batch"]),(MODULE,s["deliverables"])):
        for n,h in refs.items():assert sha(base/n)==h,n
    print("Verified",len(s["batch"]),"batch files and",len(s["deliverables"]),"deliverables")
if __name__=="__main__":
    if sys.argv[1]=="docs":docs(sys.argv[2])
    else:{"audit":audit,"seal":seal,"verify":verify}[sys.argv[1]]()
