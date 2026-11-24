"""Freeze the paired v2 move sample and verify its damage, actual inverse, and repair."""
from collections import Counter, defaultdict
from pathlib import Path

from benchmarks import old_directory
from measure import (HERE, LOCAL, OLD, active, bases, check_profile, emit, jsonline, load,
                     read_checked_json, save, sha256, typed_record, verified_index)
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches, verify_provenance
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import (_materialize_closure, assess_mutation, base_contents, build_mutation,
    dependency_repair_observation, environment_observation, relative_move_site, relative_move_v2_site,
    score_dependency_repair, score_graphs, stratified_sample)
from compile_repair.toolchain.project import resolve_project
from compile_repair.toolchain.solc import load_trusted_compilers

OP = "missing_relative_file_moved_v2"
OLD_OP = "missing_relative_file_moved"
SEED = 20261122


def plan(catalog):
    pools = defaultdict(list)
    sites = {}
    for uid,base in catalog.items():
        if not base["project_root"]:
            continue
        root = Path(base["project_root"])
        ref = base["result"]
        record = read_checked_json(ref["result_path"],ref["result_sha256"])
        sources = {Path(f["path"]).relative_to(root).as_posix():f["sha256"] for f in record["inputs"]}
        imports = load(Path(ref["result_path"]).with_name("project.json"))["imports"]
        site = relative_move_site(base,sources,imports)
        if site is None:
            continue
        name = site[0]
        assert sha256(root/name) == sources[name]
        sources[name] = (root/name).read_bytes()
        updated = relative_move_v2_site(base,sources,imports,site)
        if updated:
            pools[base["corpus"]].append(base)
            sites[uid] = {"filename":name,"destination":updated[3]["destination"],"edits":len(updated[3]["paths"])}
    rows = []
    for corpus, pool in sorted(pools.items()):
        for base in stratified_sample(pool,200,SEED,OLD_OP):
            uid = base["unit_id"]
            rows.append(dict(unit_id=uid,corpus=corpus,series=base["series"],split=base["split"],
                             group=base["group"], **sites[uid]))
    old_plan = read_checked_json(OLD/"moved_plan.json",load(OLD/"moved_sampling.json")["plan_sha256"])
    save(HERE/"v2_plan.json",dict(seed=SEED,rank_namespace=OLD_OP,cap_per_corpus=200,
        eligible={k:len(v) for k,v in pools.items()}, paired=len({r["unit_id"] for r in rows}&{r["unit_id"] for r in old_plan}),
        rows=rows))
    return rows


def measure():
    check_profile("production")
    catalog=bases()
    selected=plan(catalog)
    compilers, versions, _ = load_trusted_compilers()
    db=verified_index()
    counts=Counter()
    with jsonline("v2_observations") as out:
        for row in selected:
            active()
            uid=row["unit_id"]
            base=catalog[uid]
            original=base_contents(base)
            truth_layout=load(Path(base["result"]["result_path"]).with_name("project.json"))
            site=relative_move_v2_site(base,original,truth_layout["imports"])
            old,new=row["filename"],row["destination"]
            assert site[0]==old and site[3]["destination"]==new
            folder=LOCAL/"moved_v2"/uid
            observed=assess_mutation(base,OP,SEED,original,site,compilers,versions,folder/"trigger")
            work, patches, damage=build_mutation(base,original,site,OP)
            manifest=read_checked_json(observed["mutation_path"],observed["mutation_sha256"])
            assert len(patches)==row["edits"]==len(manifest["edits"])
            damaged_root=folder/"trigger/damaged"
            moved_project=resolve_project(damaged_root,new,base["remappings"])
            truth_root=Path(base["project_root"])
            incoming={(r["importer"],r["path"]) for r in truth_layout["imports"]
                      if r["resolved"] and Path(r["target_path"])==truth_root/old}
            assert all((r["importer"],r["path"]) in incoming for r in moved_project.issues)
            assert all(r["resolved"] for r in moved_project.imports if r["importer"]==new)
            result=dict(plan=row,trigger=observed)
            counts["selected"]+=1
            counts[observed["outcome"]]+=1
            if observed["outcome"]=="included":
                logical=dict(work)
                logical[old]=logical.pop(new)
                verify_provenance(original[old],logical[old],damage)
                inverse=[Patch(c.start,c.start+len(c.new),c.new,c.old,"inverse") for c in reversed(damage.changes)]
                restored=dict(logical)
                restored[old], second = apply_patches(logical[old],inverse)
                assert restored==original
                store=ArtifactStore(folder/"inverse")
                entry,project=_materialize_closure(base,restored,store,"input")
                assert not project.issues
                with store.journal("invocations.jsonl") as journal:
                    rec=environment_observation(base,entry,project,compilers,versions,store,journal,"inverse")
                record=store.path/"units/inverse/result.json"
                assert rec.status=="success" and rec.selected_version==base["version"] and list(rec.settings)==base["settings"]
                last=rec.attempts[-1]
                truth=read_checked_json(base["graph_path"],base["graph_sha256"])
                graph=read_checked_json(record.with_name("graph.json"),last["slither"]["graph_sha256"])
                inverse_score=score_graphs(truth,graph,original,logical,restored,{old:damage},{old:second},
                                           last["solc"]["returncode"],last["slither"]["d3"])
                result["inverse"]=dict(score=inverse_score,version=rec.selected_version,result_sha256=sha256(record),
                                       graph_sha256=last["slither"]["graph_sha256"])
                assert inverse_score["exact"] and all(inverse_score[k]["ratio"]==1 for k in ("kept","cfg_edges","calls"))
                repaired=dependency_repair_observation(base,manifest,original,work,{old:damage},damaged_root,
                                                       compilers,versions,db,"oldest",folder/"repair",dependency_limit=21)
                directory=folder/"repair"
                stable=typed_record(load(directory/"units"/uid/"result.json"))
                prior=score_dependency_repair(base,manifest,original,work,{old:damage},directory,stable,"oldest",21,
                                              file_level=False)
                result.update(repair=repaired,old_neighbourhood_score=prior["score"])
                counts["inverse_exact"]+=1
                counts["repaired"]+=repaired["status"]=="success"
                counts["new_exact"]+=repaired["score"]["exact"]
                counts["old_exact"]+=prior["score"]["exact"]
            emit(out,result)
            if counts["selected"]%25==0:
                print("v2",counts,flush=True)
    save(HERE/"v2_summary.json",dict(counts=counts,sha256=sha256(HERE/"v2_observations.jsonl")))


if __name__=="__main__":
    measure()
