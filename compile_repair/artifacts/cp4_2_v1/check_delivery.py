"""Check the joined evidence before delivery, then check documentation or seal the batch."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
BASE="30df6664b2b042685a5a8134278f80915a5cb58e"
MANDO="/home/zhao/miniconda3/envs/mando/bin/python"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT/name).read_bytes())


def write(name,data):
    with (OUT/name).open("x",encoding="utf8") as fp:
        json.dump(data,fp,indent=2,ensure_ascii=False);fp.write("\n")


def audit():
    exact=read("exact_summary.json")
    assert digest(OUT/"exact.jsonl.gz")==exact["sha256"] and exact["by_status"]=={"identical":14196}
    migration=read("migration_summary.json")
    assert migration["raw_and_accepted_scores_equal"]==migration["reconstructed_historical_full_proofs_equal"]==114
    moves=read("move_summary.json")
    paths=OUT/moves["rows_file"]
    assert digest(paths)==moves["rows_sha256"]
    exceptions={r["unit_id"]:r for r in read("known_creation_differences.json")}
    assert len(exceptions)==moves["counts"]["verified_creation_literal_difference"]
    assert read("literal_authorization.json")["stop"] in exceptions
    planned=read("move_plan.json")["rows"]
    ids=set()
    for line in paths.read_bytes().splitlines():
        r=json.loads(line);uid=r["unit_id"];assert uid not in ids;ids.add(uid)
        assert r["split"]=="dev" and all(digest(Path(r[n]))==r[h] for n,h in (
            ("solc_result","solc_result_sha256"),("slither_result","slither_result_sha256"),("graph_path","graph_sha256")))
        sc=r["score"]
        if uid in exceptions:
            assert r["outcome"]=="verified_creation_literal_difference"
            proof=exceptions[uid]
            assert proof["unchanged_official_score"]==sc and all(v==1 for v in proof["diagnostic_ratios"].values())
            assert proof["changes"] and sc["kept"]["ratio"]<1
        else:
            assert all(sc[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
        assert sc["compiled"] and sc["lost"]==r["expected_moved_nodes"]==sc["added"] and not sc["missing_kept"]
        assert all(sc[k]==sc["raw"][k] for k in ("compiled","lost","added","change_level"))
    assert len(ids)==200 and ids=={r["unit_id"] for r in planned}
    tests={n:read("final_tests/"+n+"_tests.json") for n in ("production","mando","dfg")}
    assert all(r["returncode"]==0 for r in tests.values())
    assert read("negative.json")["wrong_repairs_detected"]==22
    docs=["PROMPTS.md","docs/README.md","docs/HANDOVER.md","docs/DECISIONS.md","docs/CHANGE_LOG.md",
          "CP4_REPORT.md","PROGRESS.md","artifacts/cp4_1_review_v1/README.md","artifacts/cp4_1_review_v1/probe_counter_shift.py",
          "artifacts/cp4_1_review_v1/probe_counter_shift.json"]
    frozen={n:hashlib.sha256(subprocess.check_output(["git","show",BASE+":compile_repair/"+n],cwd=ROOT)).hexdigest() for n in docs}
    write("acceptance.json",dict(self_check="passed",exact=exact["units"],exact_identical=exact["by_status"]["identical"],migrations=migration["units"],
          moves=moves,tests={n:r["summary"] for n,r in tests.items()},wrong_repairs=22,missing_node_control=1,
          new_counter_use_negatives=2,final_code_scope=read("final_scope.json"),input_revision=BASE,input_documents_sha256=frozen,cost_usd=0))


def doc_check(name):
    targets=["compile_repair/docs/HANDOVER.md","compile_repair/docs/DECISIONS.md",(OUT/"README.md").relative_to(ROOT).as_posix()]
    for filename in ("compile_repair/docs/CHANGE_LOG.md","compile_repair/CP4_REPORT.md","compile_repair/PROGRESS.md"):
        previous=subprocess.check_output(["git","show",BASE+":"+filename],cwd=ROOT)
        assert (ROOT/filename).read_bytes().startswith(previous)
        targets.append(filename+":"+str(len(previous)))
    cmd=[MANDO,"-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+targets
    r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    checks=[json.loads(x) for x in r.stdout.splitlines()]
    write(name,dict(command=cmd,returncode=r.returncode,records=checks,stderr=r.stderr.decode()))
    assert r.returncode==0 and len(checks)==6 and all(x["passed"] for x in checks)
    print("6 documents passed")


def seal():
    assert read("doc_check.json")["returncode"]==0
    assert read("acceptance.json")["self_check"]=="passed"
    files={}
    for p in sorted(OUT.rglob("*")):
        assert not p.is_symlink() and "__pycache__" not in p.parts
        if p.is_file():files[p.relative_to(OUT).as_posix()]=digest(p)
    src=["evaluation/benchmark.py","tests/test_cp41.py","tests/test_cp42.py","CP4_REPORT.md","PROGRESS.md",
         "docs/CHANGE_LOG.md","docs/DECISIONS.md","docs/HANDOVER.md"]
    write("seal.json",dict(stage="CP4.2",base=BASE,batch_files_excluding_seal=files,
                           deliverables_sha256={n:digest(ROOT/"compile_repair"/n) for n in src}))
    print("Sealed",len(files),"batch files")
if __name__=="__main__":
    if sys.argv[1]=="audit":audit()
    elif sys.argv[1]=="docs":doc_check(sys.argv[2])
    elif sys.argv[1]=="seal":seal()
