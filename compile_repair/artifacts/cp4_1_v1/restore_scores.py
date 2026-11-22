"""Rescore every included edit and physically run each newly included exact and migrated closure."""
from collections import Counter
from batch import *
from replay import restore_sample
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import _materialize_closure, base_contents, environment_observation, score_graphs
from compile_repair.toolchain.slither import check_profile
from compile_repair.toolchain.solc import load_trusted_compilers

def archive_receipts():
    cert={}
    for g,s in ((OLD/"inverse_graphs.jsonl.gz",OLD/"inverse_scores.jsonl.gz"),
                (OLD/"identity_continuation/graphs.jsonl.gz",OLD/"identity_continuation/scores.jsonl.gz")):
        frozen(g);frozen(s)
        graphs={r["unit_id"]:r for r in rows(g)}
        for sample in rows(s):
            if not sample["score"]["exact"]:continue
            k=(sample["operator"],sample["unit_id"])
            graph=graphs[sample["unit_id"]]
            if k in cert or sample["actual_graph_sha256"]!=graph["graph_sha256"]:raise ValueError(k)
            cert[k]=(sample["mutation_sha256"],graph)
    if len(cert)!=11858:raise ValueError("Frozen exact-score coverage changed")
    return cert

def verify_graph(base,path,digest,expected_graph):
    rec=json.loads(checked(path,digest));attempt=rec["attempts"][-1]
    if (rec["status"]!="success" or rec["selected_version"]!=base["version"] or rec["settings"]!=base["settings"] or
        attempt["solc"]["returncode"]!=0 or not attempt["slither"]["d3"] or not attempt["slither"].get("graph_usable",True)):
        raise ValueError("Restored bytes failed production profile: "+str(path))
    gsha=attempt["slither"]["graph_sha256"]
    if expected_graph is not None and gsha!=expected_graph:raise ValueError("Graph receipt identity differs")
    g=Path(path).with_name("graph.json")
    return json.loads(checked(g,gsha)),dict(graph_path=str(g),graph_sha256=gsha,result_path=str(path),result_sha256=digest,
                 solc_returncode=0,d3=True,compiler=rec["selected_version"],settings=rec["settings"])

def compile_restoration(base,source,obs,mode,remap=None):
    store=ArtifactStore(LOCAL/"restored"/STAGE/obs["operator"]/obs["unit_id"]/mode)
    runbase=dict(base,remappings=list(base["remappings"])+([remap] if remap and remap not in base["remappings"] else []))
    entry,project=_materialize_closure(runbase,source,store,"input")
    if project is not None:
        actual={Path(x.path).relative_to(project.root).as_posix():x.sha256 for x in project.files}
        if project.issues or actual!={k:sha(v) for k,v in source.items()}:
            store.write_json("closure_stop.json",project.manifest())
            raise ValueError("Restoration closure or remapping differs: "+str(store.path))
    with store.journal("invocations.jsonl") as journal:
        environment_observation(runbase,entry,project,COMPILERS,FROZEN,store,journal,mode)
    path=store.path/"units"/mode/"result.json"
    return verify_graph(base,path,sha(path.read_bytes()),None)

def one(obs):
    try:return evaluate(obs)
    except Exception as exc:
        return dict(unit_id=obs["unit_id"],operator=obs["operator"],corpus=obs["corpus"],
                    stop=type(exc).__name__,reason=str(exc))

def evaluate(obs):
    base=BASES[obs["unit_id"]];source=base_contents(base)
    truth=json.loads(checked(base["graph_path"],base["graph_sha256"]))
    manifest,damaged,repaired,first,second=restore_sample(base,source,obs)
    if STAGE=="retained":
        anchor,graph=ARCHIVE[(obs["operator"],obs["unit_id"])]
        if anchor!=obs["mutation_sha256"] or graph["truth_graph_sha256"]!=base["graph_sha256"]:raise ValueError("Frozen inverse identity differs")
        actual,receipt=verify_graph(base,graph["result_path"],graph["result_sha256"],graph["graph_sha256"])
    else:
        actual,receipt=compile_restoration(base,repaired,obs,"exact")
    score=score_graphs(truth,actual,source,damaged,repaired,first,second,0,True)
    result=dict(cohort=STAGE,operator=obs["operator"],unit_id=obs["unit_id"],corpus=obs["corpus"],series=obs["series"],
                mutation_sha256=obs["mutation_sha256"],graph=receipt,score=score)
    if not score["exact"]:
        result.update(stop="exact_score",reason="Lost, missing, extra or changed graph facts");return result
    if "file_renames" in manifest:
        _,middle,relocated,damage,repair=restore_sample(base,source,obs,migration=True)
        new_graph,moved_receipt=compile_restoration(base,relocated,obs,"migration",manifest["remapping"])
        m=score_graphs(truth,new_graph,source,middle,relocated,damage,repair,0,True,file_renames=manifest["file_renames"])
        result.update(migration=m,migration_graph=moved_receipt,package=manifest["package"],file_renames=manifest["file_renames"])
        if not m["exact"] or any(m[k]["ratio"]!=1 for k in ("kept","cfg_edges","calls")):
            result.update(stop="migration_score",reason="Migrated graph facts differ")
    return result

def main(stage):
    global STAGE,BASES,ARCHIVE,COMPILERS,FROZEN
    STAGE=stage
    if stage not in ("retained","promoted","new"):raise ValueError(stage)
    BASES={r["unit_id"]:r for r in rows(OLD/"bases.jsonl.gz")}
    ARCHIVE=archive_receipts() if stage=="retained" else {}
    if stage!="retained":
        check_profile("production");trusted,FROZEN,_=load_trusted_compilers()
        COMPILERS={v:trusted[v] for v in load("baseline.json")["compiler_sha256"]}
    count=Counter()
    path=OUT/("new_observations.jsonl.gz" if stage=="new" else "original_reclassified.jsonl.gz")
    candidates=[r for r in rows(path) if r["outcome"]=="included" and
                (stage=="new" or (r["old_outcome"]=="included")== (stage=="retained"))]
    def score_all():
        for row in ordered_work(one,candidates,3 if stage!="new" else 4):
            if "stop" in row:
                saved(stage+"_restoration_stop.json",row)
                raise ValueError("{} {}: {}".format(row["operator"],row["unit_id"],row["reason"]))
            count["exact"]+=1
            count["normalized_exact"]+=int(row["score"]["metadata_normalized"])
            if "migration" in row:
                count["migration"]+=1;count["normalized_migration"]+=int(row["migration"]["metadata_normalized"])
            if count["exact"]%500==0:print(stage,count["exact"],"/",len(candidates),flush=True)
            yield row
    output_rows(stage+"_scores.jsonl.gz",score_all())
    saved(stage+"_score_acceptance.json",dict(expected=len(candidates),counts=count,passed=count["exact"]==len(candidates),
           scores_sha256=sha((OUT/(stage+"_scores.jsonl.gz")).read_bytes()),new_compilations=(stage!="retained")))
    print(stage,dict(count),flush=True)
if __name__=="__main__":main(sys.argv[1])
