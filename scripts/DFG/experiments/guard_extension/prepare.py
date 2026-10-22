"""Seal 30 candidates from fixed graphs and saved untrained overall-CV states."""
import copy,gc,subprocess
from pathlib import Path
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.graph_audit import fingerprint,frozen
from scripts.DFG.experiments.e23_pilot.model import make_model as baseline_model
from .common import *
from .archive import verify_archive
from .model import make_model,extend_saved_initial,validate_registration,ADAPTER_VERSION,INITIALIZATION_VERSION
from .runtime import Supervision,graph_schema_and_support

def prepare(output=DEFAULT,build_manifest=None,source=SOURCE):
    output=Path(output);source=Path(source);dest=output/"prepared"
    if dest.exists() or (output/"plan.json").exists():
        raise ValueError("Immutable preparation already exists; do not overwrite")
    # Fail before producing any initial weights if historical computation changed.
    historical,audit=verify_archive(source)
    bpath=Path(build_manifest) if build_manifest else output/"build/manifest.json"
    build=read_json(bpath)
    if Path(build["source_plan_path"]).resolve()!=(source/"plan.json").resolve() or build["source_plan_sha256"]!=sha256(source/"plan.json"):
        raise ValueError("Build/source batch mismatch")
    if len(build["tasks"])!=4 or {r["task_id"] for r in build["tasks"]}!=set(TASKS):
        raise ValueError("Incomplete build task matrix")
    recorded_hashes(build["frozen_inputs"]);recorded_hashes(build["analysis_runtime"])
    dest.mkdir(parents=True);torch.set_num_threads(2)
    assets={};refs=[]
    def check(path,expected=None):
        path=Path(path).resolve();h=sha256(path)
        if expected is not None and h!=expected:raise ValueError("Input hash drift: "+str(path))
        assets[str(path)]=h;return path
    check(source/"plan.json");check(source/"plan.seal.json");check(bpath)
    for path,h in historical["frozen"].items():check(path,h)
    for path,h in build["frozen_inputs"].items():check(path,h)
    for path,h in build["analysis_runtime"].items():check(path,h)
    for rec in audit["results"]:
        rp=check(rec["receipt"],rec["receipt_sha256"])
        # Freeze referenced outputs as well as their receipt; do not copy/rewrite archives.
        for name,h in read_json(rp)["artifacts"].items():check(rp.parent/name,h)
    write_json(output/"archive_audit.json",audit);check(output/"archive_audit.json")
    for tid in TASKS:
        built=next(x for x in build["tasks"] if x["task_id"]==tid)
        gp=check(built["graph"]["path"],built["graph"]["sha256"]);graph=read_graph(gp)
        if fingerprint(graph)!=built["graph"]["fingerprint"]:raise ValueError("Build graph fingerprint drift")
        for name in ("coverage","invariants","support"):
            check(built[name+"_path"],built[name+"_sha256"])
        for fold in range(folds(tid)):
            href=task_ref(historical,tid,fold);ip=check(href["manifest"],href["sha256"]);old=read_json(ip)
            info=copy.deepcopy(old)
            oldg=read_graph(check(old["graphs"]["HCG_DDG"]["path"],old["graphs"]["HCG_DDG"]["sha256"]))
            if frozen(list(oldg.nodes(data=True)))!=frozen(list(graph.nodes(data=True))):
                raise ValueError("Candidate changed frozen node IDs/order/features/labels")
            if digest(frozen(list(graph.nodes(data=True))))!=old["graphs"]["HCG_DDG"]["node_attributes_sha256"]:
                raise ValueError("Candidate node-attribute digest mismatch")
            before={(u,v,k):frozen(a) for u,v,k,a in oldg.edges(keys=True,data=True)}
            after={(u,v,k):frozen(a) for u,v,k,a in graph.edges(keys=True,data=True)}
            if any(after.get(key)!=value for key,value in before.items()):
                raise ValueError("Candidate removed or changed a baseline edge")
            if any(graph.edges[u,v,k]["edge_type"]!="CONTROL_DEPENDENCE" for u,v,k in set(after)-set(before)):
                raise ValueError("Candidate contains an unapproved added relation")
            seed_all(old["seeds"]["constructor"])
            base=baseline_model(old["task"],oldg,"cpu")
            seed_all(old["seeds"]["constructor"])
            candidate=make_model(old["task"],graph,"cpu")
            init=old["initialization"]["HCG_DDG"]
            check(init["path"],init["sha256"]);record=torch.load(init["path"],map_location="cpu")
            if tensor_digest(record["state_dict"])!=init["state_sha256"]:
                raise ValueError("Historical initial state does not match manifest")
            pairing=extend_saved_initial(base,candidate,record,dict(task_id=tid,fold=fold,variant="HCG_DDG",
                fit_seed=old["fit_seed"],pair_version=historical["pair_version"],
                graph_sha256=old["graphs"]["HCG_DDG"]["sha256"],pairing_sha256=old["initialization_audit_sha256"]),
                seed=old["seeds"]["pair"])
            pairing.update(pair_version=PAIR_VERSION,source_initial_path=init["path"],
                           source_initial_sha256=init["sha256"],source_task_sha256=sha256(ip))
            folder=dest/tid/("fold_"+str(fold));folder.mkdir(parents=True)
            ap=folder/"initialization_audit.json";write_json(ap,pairing);check(ap)
            graph_rec=dict(built["graph"],node_attributes_sha256=old["graphs"]["HCG_DDG"]["node_attributes_sha256"])
            support=graph_schema_and_support(graph,old["split"]);validate_registration(candidate,support["schema"])
            state={k:v.detach().cpu().clone() for k,v in candidate.state_dict().items()}
            initial=dict(kind="untrained_initial",optimizer_steps=0,task_id=tid,fold=fold,variant=VARIANT,
                state_dict=state,state_sha256=tensor_digest(state),fit_seed=old["fit_seed"],pair_version=PAIR_VERSION,
                graph_sha256=graph_rec["sha256"],pairing_sha256=sha256(ap))
            initpath=folder/(VARIANT+"_initial.pt");torch.save(initial,str(initpath));check(initpath)
            info.update(graphs={VARIANT:graph_rec},initialization={VARIANT:dict(path=str(initpath),
                sha256=sha256(initpath),state_sha256=tensor_digest(state))},support={VARIANT:support},
                supervision={VARIANT:{phase:Supervision(candidate,old["task"],old["split"][phase+"_files"]).manifest
                    for phase in ("train","val")}},experiment_version=VERSION,pair_version=PAIR_VERSION,
                initialization_version=INITIALIZATION_VERSION,adapter_version=ADAPTER_VERSION,
                initialization_audit_path=str(ap),initialization_audit_sha256=sha256(ap),
                baseline_task_manifest=str(ip),baseline_task_sha256=sha256(ip),
                source_guard_manifest=str(bpath),source_guard_manifest_sha256=sha256(bpath),
                guard_forward_relations=["CONTROL_DEPENDENCE"],config=copy.deepcopy(old["config"]))
            if info["config"]!=old["config"] or info["split"]!=old["split"]:
                raise AssertionError("Config or frozen file split changed")
            path=folder/"task.json";write_json(path,info);check(path)
            refs.append(dict(task_id=tid,fold=fold,manifest=str(path),sha256=sha256(path)))
            print("PREPARED",tid,fold,"saved-untrained -> guard",flush=True)
            del base,candidate,state,initial,oldg;gc.collect()
        del graph;gc.collect()
    plan=dict(version=VERSION,pair_version=PAIR_VERSION,
       head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT)).decode().strip(),
       runtime=runtime_hashes(),historical_runtime=historical["runtime"],frozen=assets,
       jobs=expected_jobs(),tasks=refs,device="cuda:0",threads=2,maximum_epochs=50,
       execution_authorized=True,score_role="cv_validation",protocol="paper_kfold",
       initialization_version=INITIALIZATION_VERSION,source_batch=str(source),
       source_plan_sha256=sha256(source/"plan.json"),source_archive_audit_sha256=sha256(output/"archive_audit.json"),
       new_relation="CONTROL_DEPENDENCE",relation_direction="source guard -> controlled statement; forward only",
       policy="30 candidates only; four fixed fold0 gate; old60 read-only; stop on input/numeric/resource error; no F1 gate")
    write_json(output/"plan.json",plan);write_json(output/"plan.seal.json",dict(sha256=sha256(output/"plan.json")))
    verify_plan(output);return plan
