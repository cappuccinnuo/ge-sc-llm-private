"""Collect CP4.3 receipts and verify the recorded, reproducible acceptance conditions."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
MODULE=OUT.parents[1]
ROOT=MODULE.parent
BASE="09a8355e4d668a2ffba9da22a6e33dfeb6a9a667"
MANDO="/home/zhao/miniconda3/envs/mando/bin/python"
DOCS=("CP4_REPORT.md","PROGRESS.md","docs/CHANGE_LOG.md","docs/HANDOVER.md","docs/DECISIONS.md")
CODE=("evaluation/benchmark.py","tests/test_cp42.py","tests/test_cp43.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,indent=2,sort_keys=True)
        f.write("\n")


def git_bytes(name):
    return subprocess.check_output(["git","show",BASE+":compile_repair/"+name],cwd=ROOT)


def capture():
    suite=read(OUT/"suites/production_tests.json")
    assert suite["returncode"]==0
    scratch=Path(next(x.split("=",1)[1] for x in suite["command"] if x.startswith("--basetemp="))).resolve()
    fixtures={}
    for label,pattern,scores in (
            ("delete_undamaged","test_repair_deleting_an_undama*","score.json"),
            ("yul_offset","test_yul_switch_offset_from_co*","scores.json"),
            ("review_top","test_review_placement_True*","score.json"),
            ("review_in_place","test_review_placement_False*","score.json")):
        folder,=[p for p in scratch.glob(pattern) if not p.is_symlink()]
        record={"score":read(folder/scores),"score_path":str(folder/scores),"score_sha256":sha(folder/scores)}
        for side in ("truth","actual"):
            sol,sl=folder/side/"solc.json",folder/side/"slither.json"
            compiler,analysis=read(sol),read(sl)
            assert analysis["d3"] is True and analysis["profile"]=="production" and compiler["returncode"]==0
            assert compiler["source_sha256"]==analysis["source_sha256"]==sha(Path(compiler["source_path"]))
            assert sha(Path(compiler["compiler"]["path"]))==analysis["compiler_sha256"]==compiler["compiler"]["sha256"]
            record[side]=dict(solc_sha256=sha(sol),slither_sha256=sha(sl),solc_receipt=str(sol),slither_receipt=str(sl),
                source_sha256=compiler["source_sha256"],compiler=compiler["compiler"],slither=analysis["slither_version"],
                crytic_compile=analysis["crytic_compile_version"],solc_elapsed_seconds=compiler["elapsed_seconds"],
                graph_nodes=len(analysis["graph"]["nodes"]),d3=analysis["d3"])
        fixtures[label]=record
    bad=fixtures["delete_undamaged"]["score"]
    assert not bad["exact"] and bad["kept"]["ratio"]==2/7 and bad["lost"]==2
    assert bad["removed_by_repair"]==bad["missing_kept"]==5 and all(m["ratio"]==1 for m in bad["surviving"].values())
    yul=fixtures["yul_offset"]["score"]
    assert yul["verified"]["counter_correspondence"]["status"]=="verified"
    assert all(v["counter_correspondence"]["status"]=="rejected" for v in yul["rejected"].values())
    assert fixtures["review_top"]["score"]["removed_by_repair"]==0 and fixtures["review_top"]["score"]["kept"]["units"]==2
    write(OUT/"fixtures.json",fixtures)


def accept():
    prior=OUT.parent/"cp4_2_v1"
    prior_seal=read(prior/"seal.json")["batch_files_excluding_seal"]
    for filename,expected in prior_seal.items():
        assert sha(prior/filename)==expected,filename
    summary={}
    for name in ("moves","exact","migration"):
        f=OUT/(name+".jsonl.gz")
        meta=read(OUT/(name+"_summary.json"))
        assert sha(f)==meta["sha256"] and meta["solc_runs"]==meta["slither_runs"]==0
        sums=Counter();exceptions=[];seen=set()
        with gzip.open(f,"rt",encoding="utf8") as fp:
            for line in fp:
                row=json.loads(line)
                uid=row["unit_id"]
                k=(uid,row.get("operator"),row.get("mutation_sha256"))
                assert k not in seen
                seen.add(k)
                s=row["score"]
                if name=="moves":
                    assert s["removed_by_repair"]==s["missing_kept"]==row["expected_moved_nodes"]>0
                    assert s["lost"]==0 and not s["exact"] and s["kept"]["ratio"]<1
                    if any(m["ratio"]!=1 for m in s["surviving"].values()):
                        exceptions.append(uid)
                    if uid in ("cp3_00291","cp3_21529"):
                        summary[uid]={k:s[k] for k in ("kept","cfg_edges","calls","surviving","removed_by_repair",
                                                       "lost","counter_correspondence")}
                else:
                    assert s["exact"] and s["removed_by_repair"]==s["raw"]["removed_by_repair"]==0
                    assert all(s[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
                sums[s["counter_correspondence"]["status"]]+=1
        assert len(seen)==meta["counts"]["units"]=={"moves":200,"exact":14196,"migration":114}[name]
        if name=="exact":assert sums=={"identical":14196}
        if name=="moves":assert exceptions==["cp3_00291"] and meta["counts"]["surviving_all_equal"]==199
        birth=int(subprocess.check_output(["stat","-c","%W",str(OUT/(name+".log"))]))
        assert 0<birth<=f.stat().st_mtime
        summary[name]=dict(meta,by_status=sums,
            approximate_elapsed_seconds=round((OUT/(name+"_summary.json")).stat().st_mtime-birth))
    negative=read(OUT/"negative.json")
    assert negative["wrong_repairs_detected"]==22 and negative["missing_node_detected"]==1
    assert len(negative["rows"])==23 and all(r["detected"] and not r["score"]["exact"] for r in negative["rows"])
    fixtures=read(OUT/"fixtures.json")
    tests={name:read(OUT/("suites/"+name+"_tests.json")) for name in ("production","mando","dfg")}
    assert all(run["returncode"]==0 for run in tests.values())
    scope=read(OUT/"scope.json")
    assert scope["production_files"]==17 and scope["unchanged_dfg_code_refs"]==354
    assert all(sha(ROOT/n)==h for n,h in scope["production_sha256"].items())
    inputs=("PROMPTS.md","docs/README.md","docs/HANDOVER.md","docs/CHANGE_LOG.md","docs/DECISIONS.md",
            "CP4_REPORT.md","artifacts/cp4_2_review_v1/README.md","artifacts/cp4_2_review_v1/probe_repair_deletes_kept.py",
            "artifacts/cp4_2_review_v1/probe_repair_deletes_kept.json","artifacts/cp4_2_v1/seal.json")
    write(OUT/"acceptance.json",dict(self_check="passed",base=BASE,summary=summary,scope_file="scope.json",
        tests={n:v["summary"] for n,v in tests.items()},prior_batch_files_verified=len(prior_seal),
        frozen_inputs_sha256={p:hashlib.sha256(git_bytes(p)).hexdigest() for p in inputs},
        compiler=fixtures["delete_undamaged"]["truth"]["compiler"],wrong_repairs=22,missing_node_control=1,
        training_runs=0,llm_calls=0,cost_usd=0,independent_review="pending"))
    # A separate scientific seal can be cited by the report without a circular hash.
    files={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob("*"))
           if p.is_file() and p.suffix!=".md" and not p.name.startswith("doc_check")}
    write(OUT/"evidence_seal.json",dict(files=files,code={n:sha(MODULE/n) for n in CODE}))


def documents(output):
    targets=[]
    for n in DOCS:
        filename="compile_repair/"+n
        if n in DOCS[:3]:
            before=git_bytes(n)
            assert (ROOT/filename).read_bytes().startswith(before)
            filename+=":"+str(len(before))
        targets.append(filename)
    targets.append((OUT/"README.md").relative_to(ROOT).as_posix())
    cmd=[MANDO,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    records=[json.loads(line) for line in r.stdout.splitlines()]
    write(OUT/output,dict(command=cmd,returncode=r.returncode,records=records,stderr=r.stderr.decode()))
    assert r.returncode==0 and len(records)==6 and all(x["passed"] for x in records)
    print("6 documents passed")


def seal():
    assert read(OUT/"doc_check.json")["returncode"]==0
    assert read(OUT/"acceptance.json")["self_check"]=="passed"
    files={}
    for p in sorted(OUT.rglob("*")):
        assert not p.is_symlink() and "__pycache__" not in p.parts
        if p.is_file():files[p.relative_to(OUT).as_posix()]=sha(p)
    write(OUT/"seal.json",dict(base=BASE,batch=files,deliverables={n:sha(MODULE/n) for n in CODE+DOCS}))


def verify():
    sealed=read(OUT/"seal.json")
    for base,records in ((OUT,sealed["batch"]),(MODULE,sealed["deliverables"])):
        for p,h in records.items():assert sha(base/p)==h,p
    print("Verified",len(sealed["batch"]),"batch files and",len(sealed["deliverables"]),"deliverables")


if __name__=="__main__":
    if sys.argv[1]=="docs":documents(sys.argv[2])
    else:{"fixtures":capture,"accept":accept,"seal":seal,"verify":verify}[sys.argv[1]]()
