"""Join the original frozen candidate plan, admissions and verified exact/migration receipts without tool reruns."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

DEST = Path(__file__).resolve().parent
sys.path.insert(0, str(DEST.parent))
from batch import HERE, OLD, checked, rows, sha
from resume_migrations import load_inputs

OP = "unresolved_package_import"
STAGES = ("results","tuple_continuation","yul_continuation","definition_continuation")


def key(row):
    phase = "original" if row["cohort"] in ("retained","promoted") else row["cohort"]
    return (phase, row["operator"], row["unit_id"], row["mutation_sha256"])


def exact(score, graph):
    assert score["exact"] and score["compiled"] and graph["d3"] is True and graph["solc_returncode"]==0
    assert all(score[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
    assert score["lost"]==score["added"]==score["missing_kept"]==0


def main():
    population=json.loads((HERE/"population.json").read_bytes())
    frozen=json.loads((HERE/"migration_stop_seal.json").read_bytes())["batch_files_excluding_this_seal"]
    for name,ref in frozen.items():
        checked(HERE/name,ref["sha256"])
    expected, total = {}, 0
    for f in ("original_reclassified","new_observations","supplement_observations"):
        for row in rows(HERE/(f+".jsonl.gz")):
            total+=1
            if row["outcome"]=="included":
                k=key(row)
                assert k not in expected
                expected[k]=(row["corpus"],row["split"],row["series"])
    assert total==population["totals"]["sampled"]==19354 and len(expected)==population["totals"]["final_included"]==14196
    got, by_operator, groups, metadata = set(),Counter(),Counter(),Counter()
    def add(row):
        k=key(row)
        assert k in expected and k not in got and expected[k][0]==row["corpus"] and expected[k][2]==row["series"]
        got.add(k)
        exact(row["score"],row["graph"])
        by_operator[row["operator"]]+=1
        groups[row["cohort"]]+=1
        metadata["exact_graph_scores_with_metadata"]+=int(row["score"]["metadata_normalized"])
    for name in ("retained_scores","promoted_scores","new_scores"):
        for row in rows(HERE/(name+".jsonl.gz")):
            if row["operator"]!=OP:add(row)
    assert len(got)==14082
    keys,_,_,initial=load_inputs()
    ids, corpus, proof_counts, families, tools, calls_by_stage = set(),Counter(),Counter(),Counter(),Counter(),Counter()
    splits, pkg_rows, witnessed = Counter(), [], set()
    candidate_paths = Counter()
    digests = {}
    stage_counts={}
    for stage in STAGES:
        path=DEST/stage/"package_scores.jsonl"
        digests[stage]=sha(path.read_bytes())
        stage_counts[stage]=0
        for r in rows(path):
            uid=r["unit_id"]
            assert uid not in ids;ids.add(uid)
            add(r);exact(r["migration"],r["migration_graph"])
            stage_counts[stage]+=1
            corpus[r["corpus"]]+=1;splits[r["split"]]+=1
            m=r["migration"];proof=m["migration_counters"];raw=m["raw_migration_score"]
            assert proof["status"] in ("identical","verified") and expected[key(r)][1]==r["split"]
            proof_counts[proof["status"]]+=1
            proof_counts["raw_exact"]+=raw["exact"]
            proof_counts["changed_from_raw"]+=not raw["exact"]
            assert (not raw["exact"]) <= (proof["status"]=="verified")
            types=sorted({n.split("_")[0] for n in proof["renamed"]})
            for family in types:families[family]+=1
            yul=len(proof.get("yul_switches",()))
            if yul:witnessed.add(uid)
            metadata["migrated_graph_scores_with_metadata"]+=int(m["metadata_normalized"])
            for mode,field in (("exact","graph"),("migration","migration_graph")):
                g=r[field]
                checked(g["graph_path"],g["graph_sha256"])
                result=json.loads(checked(g["result_path"],g["result_sha256"]))
                a=result["attempts"][-1]
                assert a["solc"]["returncode"]==0 and a["slither"]["d3"] and a["slither"]["graph_sha256"]==g["graph_sha256"]
                j=checked(g["journal_path"],g["journal_sha256"])
                journal=list(map(json.loads,j.splitlines()))
                inv=Counter(x["kind"] for x in journal)
                measured=[x for x in journal if x["kind"]=="solc"]
                actual=[x["solc"] for x in result["attempts"]]
                assert [{k:v for k,v in x.items() if k not in ("kind","unit_id")} for x in measured]==actual
                versions=tuple(x["compiler"]["version"] for x in measured)
                planned=[v for group in result["plan"]["groups"] for v in group]
                assert list(versions)==planned[:len(versions)] and versions[-1]==g["compiler"]
                assert all(x["returncode"]!=0 for x in measured[:-1]) and measured[-1]["returncode"]==0
                assert inv==g["invocations"] and inv["slither"]==1 and inv["solc"]==len(actual)
                candidate_paths[",".join(versions)]+=1
                existed=mode in initial[uid]
                for kind,n in inv.items():
                    tools[("old_" if existed else "new_")+kind]+=n
                    calls_by_stage[stage+"_"+kind]+=n
            pkg_rows.append(dict(unit_id=uid,cohort=r["cohort"],corpus=r["corpus"],split=r["split"],package=r["package"],
                                 original_solc=r["graph"]["compiler"],exact=1,raw_migration_exact=int(raw["exact"]),
                                 verified_migration_exact=1,counter_families=",".join(types),yul_switches=yul,
                                 nodes=proof["nodes"],cfg_edges=proof["cfg_edges"],calls=proof["calls"],stage=stage,
                                 original_graph_sha256=r["truth_graph_sha256"],migration_graph_sha256=r["migration_graph"]["graph_sha256"]))
    assert set(keys)==ids and set(expected)==got and len(got)==14196
    assert dict(by_operator)=={r["operator"]:r["final_included"] for r in population["by_operator"] if r["final_included"]}
    assert len(ids)==114 and corpus=={"DAppSCAN":112,"Trace_repo":2}
    assert tools["old_solc"]==tools["old_slither"]==18 and tools["new_slither"]==210
    control=OLD/"controls.jsonl"
    control_rows=[json.loads(raw) for raw in checked(control,population["old_control_sha256"]).splitlines()]
    assert len(control_rows)==population["old_control_passes"]==200 and all(r["passed"] for r in control_rows)
    receipts=list((DEST/"yul_continuation"/"witnesses").glob("*/*/verified.json"))
    invocations=list((DEST/"yul_continuation"/"witnesses").glob("*/*/invocation.json"))
    assert len(receipts)==len(invocations)==len(witnessed)*2<=4
    for p in receipts:
        r=json.loads(p.read_bytes())
        assert p.parent.parent.name in witnessed
        checked(r["output_path"],r["stdout_sha256"])
    with (DEST/"packages.tsv").open("x",encoding="utf8",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=pkg_rows[0].keys(),delimiter="\t",lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(pkg_rows,key=lambda r:r["unit_id"]))
    summary=dict(complete=True,prior_sealed_files_rechecked=len(frozen),population=population["base_population"],
                 sampled=total,triggered=len(expected),exact_passed=len(got),exact_by_cohort=groups,
                 exact_by_operator=dict(by_operator),controls_passed=len(control_rows),controls_sha256=population["old_control_sha256"],
                 packages=dict(expected=114, passed=len(ids), by_corpus=corpus, by_split=splits, phases=stage_counts,
                               proof_counts=proof_counts, packages_by_renamed_family=families,
                               witnessed_yul_units=sorted(witnessed), score_sha256=digests),
                 graph_invocations=tools,actual_candidate_paths=candidate_paths, added_ast_compiler_calls=len(receipts), scores_with_metadata=metadata,
                 package_table_sha256=sha((DEST/"packages.tsv").read_bytes()), training_runs=0,llm_calls=0,cost_usd=0)
    with (DEST/"acceptance.json").open("x",encoding="utf8") as fp:
        json.dump(summary,fp,indent=2,ensure_ascii=False);fp.write("\n")
    print(len(got),len(ids),proof_counts,tools,"AST witnesses",len(receipts))
if __name__=="__main__":main()
