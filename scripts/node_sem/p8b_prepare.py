"""N-C2 CPU plan preparation after all 30 students; no HGT fit is launched."""
import argparse
import copy
import gc
from pathlib import Path
import subprocess
import time
import traceback
import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.experiments.common import seed_all,tensor_digest,digest
from . import batch_nc2 as batch,batch_na as na
from .nc1_history import verify_index
from .nc2_init import baseline_state,paired_state,VERSION
from .nc2_carrier import extend,compare_deep
from .carrier import carry
from .feature_spec import FeatureSpec
from .init import checked_initial
from .na_carrier import load_carrier,construct_carried
from .model import make_nodesem_model
from .p6_prepare import device_policy

BASE=Path(__file__).resolve().parent

def prepare(root=batch.DEFAULT):
    root=Path(root).resolve()
    # Student phase owns exclusive root creation; this phase is also exclusive.
    (root/"prepared").mkdir(exist_ok=False)
    write(root/"prepare.started.json",dict(unix_seconds=time.time(),HGT_fits=0))
    start=time.monotonic()
    try:
        students=read(root/"students_complete.json")
        if not students["passed"] or students["students"]!=30:raise ValueError("Incomplete student fits")
        source=read(checked(students["plan"]))
        for r in source["sources"].values():checked(r)
        parent=batch.parent.load(checked(source["parent_plan"]))
        parents=verify_index(source["na_result_index"])
        by_student={}
        for r in students["records"]:
            done=read(checked(r));by_student[(done["task_id"],done["fold"])]=done
        decisions=read(root/"preparation_decisions.json")
        if not decisions.get("fast_carrier_and_untrained_structure_approved"):
            raise PermissionError("Fast carrier preparation approval absent")
        policy,hardware=device_policy()
        if any(p!=policy for p in parent["device_families"].values()):raise ValueError("Device family differs")
        inputs=root/"inputs";inputs.mkdir()
        for name in ("PROMPTS.md","EXPERIMENT_POLICY.md"):
            (inputs/name).write_bytes((BASE/name).read_bytes())
        code=batch.runtime();archives={}
        for name,sha in code.items():
            p=root/"runtime_archive"/name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open("xb") as f:f.write((batch.ROOT/name).read_bytes())
            archives[name]=ref(p)
            if archives[name]["sha256"]!=sha:raise ValueError("Runtime changed while snapshotting")
        jobs=[];proofs=[]
        for task,n in batch.TASK_FOLDS:
            rows=sorted((r for r in parents.values() if r["job"]["task_id"]==task),key=lambda r:r["job"]["fold"])
            graph=read_graph(checked(rows[0]["job"]["graph"]))
            model=None;basemodel=None
            for row in rows:
                old=row["job"];fold=old["fold"];pairdir=root/"prepared"/task/("fold_%d"%fold)
                pairdir.mkdir(parents=True)
                oldspec=FeatureSpec.from_json(read(checked(old["spec"])))
                if not Path(old["initial"]["path"]).exists() and basemodel is None:
                    basemodel=make_nodesem_model(old["granularity"],old["graph"],"G3R",oldspec,old["config"],"cpu",task)
                baseline,mode=baseline_state(old,basemodel)
                reconstructed=None
                if mode!="existing_NA_initial":
                    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task,fold=fold,seed=1,
                        profile="G3R",constructor_seed=old["seeds"]["constructor"],fit_seed=old["seeds"]["fit"],
                        feature_spec_sha256=oldspec.digest(),state_dict=baseline,state_sha256=tensor_digest(baseline),
                        formal_training=False,source=old["h8_initial"])
                    with (pairdir/"S4_reconstructed.pt").open("xb") as f:torch.save(payload,f)
                    reconstructed=dict(ref(pairdir/"S4_reconstructed.pt"),state_sha256=tensor_digest(baseline))
                state=None;s5=None;common=None
                for name in ("S5","S8"):
                    d=pairdir/name;d.mkdir()
                    student=by_student[(task,fold)][name]
                    spec=batch.make_spec(oldspec,student,name)
                    write(d/"spec.json",spec.to_json())
                    carrier=extend(old,graph,spec,student,d/"carrier")
                    j=copy.deepcopy(old)
                    j.update(name=name,spec=ref(d/"spec.json"),spec_sha256=spec.digest(),
                        feature_view=carrier["manifest"],feature_npz=carrier["data"],
                        carrier_dim=spec.carrier_dim(),
                        parameters=next(x["parameters"] for x in parent["jobs"] if x["task_id"]==task),
                        baseline_job_id=__import__("scripts.node_sem.batch_na_worker",fromlist=["job_id"]).job_id(old),
                        baseline_receipt=row["receipt"])
                    j.pop("config_template",None);j.pop("constructor_seconds",None)
                    # First task/fold: compare complete AST-gated assembler before reusing the fast carrier.
                    if fold==0:
                        _,deep=carry(graph,spec,task);compare_deep(carrier,deep)
                    if model is None:
                        carried,record,_=load_carrier(j)
                        seed_all(old["seeds"]["constructor"])
                        model=construct_carried(j,carried,record,spec)
                    if name=="S5":
                        state,common=paired_state(model,spec,old,baseline)
                        j["paired_random_spec_sha256"]=spec.digest()
                        j["dropout"]=na.dropout_identity(model,j,spec)
                    else:
                        j["paired_random_spec_sha256"]=s5["spec_sha256"]
                        j["dropout"]=copy.deepcopy(s5["dropout"])
                    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task,fold=fold,seed=1,
                        profile="G3R",constructor_seed=old["seeds"]["constructor"],fit_seed=old["seeds"]["fit"],
                        feature_spec_sha256=spec.digest(),state_dict=state,state_sha256=tensor_digest(state),
                        initialization_version=VERSION,source=old["h8_initial"],formal_training=False,
                        baseline_state_sha256=old["initial"]["state_sha256"],baseline_mode=mode,
                        paired_random_spec_sha256=j["paired_random_spec_sha256"])
                    with (d/"initial.pt").open("xb") as f:torch.save(payload,f)
                    j["initial"]=dict(ref(d/"initial.pt"),state_sha256=payload["state_sha256"])
                    loaded=checked_initial(j["initial"],task,fold,"G3R",spec_digest=spec.digest())
                    model.load_state_dict(loaded["state_dict"],strict=True)
                    if tensor_digest(model.state_dict())!=payload["state_sha256"]:raise ValueError("Reload mismatch")
                    if model_support(model,j["split"])!=old["support"]:raise ValueError("Support changed")
                    fresh_exact=None
                    if fold==1 and name=="S5":
                        carried,record,_=load_carrier(j)
                        seed_all(j["seeds"]["constructor"])
                        fresh=construct_carried(j,carried,record,spec)
                        other,_=paired_state(fresh,spec,old,baseline)
                        fresh_exact=all(torch.equal(state[k],other[k]) for k in state) and set(state)==set(other)
                        if not fresh_exact:raise ValueError("Fresh versus reused initial mismatch")
                        del fresh,other,carried,record
                    proof=dict(common,initial=j["initial"],baseline_mode=mode,reconstructed_initial=reconstructed,
                        optimizer_steps=0,CPU_reload_exact=True,dropout=j["dropout"],
                        fresh_structure_initial_exact=fresh_exact,complete_carrier_exact=fold==0,
                        student_manifest=student,student_diagnostics=by_student[(task,fold)]["diagnostics"],
                        S5_S8_full_state_equal=name=="S8" and j["initial"]["state_sha256"]==s5["initial"]["state_sha256"])
                    write(d/"preparation.json",proof);j["preparation_evidence"]=ref(d/"preparation.json")
                    write(d/"job.json",j);jobs.append(j);proofs.append(j["preparation_evidence"])
                    if name=="S5":s5=j
                    del loaded,payload
                del baseline,state
                print("prepared %s fold%d S5/S8 (%d/60)"%(task,fold,len(jobs)),flush=True)
            del model,graph,basemodel;gc.collect()
        order={(j["task_id"],j["name"],j["fold"]):i for i,j in enumerate(batch.matrix())}
        jobs.sort(key=lambda j:order[(j["task_id"],j["name"],j["fold"])])
        batch.validate_matrix(jobs)
        if torch.cuda.is_initialized() or code!=batch.runtime():raise ValueError("GPU initialized or runtime changed")
        write(root/"preparation_audit.json",dict(passed=True,jobs=60,students=30,unconditional=30,conditional=30,
            HGT_fits=0,proofs=proofs,complete_carrier_checks=8,fresh_structure_checks=4,
            seconds=time.monotonic()-start,hardware=hardware,cuda_initialized=False))
        families={t:copy.deepcopy(policy) for t,_ in batch.TASK_FOLDS}
        write(root/"authorization.template.json",dict(version=batch.VERSION,execution_authorized=False,
            scope="formal_NC2",unconditional_jobs=30,conditional_jobs=30,jobs=60,matrix_sha256=digest(jobs),
            view="original",label_policy="L-audit",seeds=[1],user_request=None,
            conditional_rule=batch.statistics_spec()["continuation"],external_interrupt_retry_once=False,
            instructions="Separate explicit authorization; never edit this template"))
        plan=dict(version=batch.VERSION,protocol=batch.PROTOCOL_NAME,protocol_version=batch.PROTOCOL_VERSION,
            execution_authorized=False,view="original",label_policy="L-audit",jobs=jobs,
            source_h8_plan=parent["source_h8_plan"],source_preparation=parent["source_preparation"],
            nc1_plan=source["parent_plan"],nc1_report=source["parent_report"],na_result_index=source["na_result_index"],
            teacher_index=source["teacher_index"],student_plan=ref(root/"student_plan.json"),
            students_complete=ref(root/"students_complete.json"),runtime=code,runtime_archive=archives,
            statistics=batch.statistics_spec(),device_families=families,resource_policy=batch.LOCAL_DEV_POLICY,
            initialization_version=VERSION,decisions=ref(root/"preparation_decisions.json"),
            prompt=ref(inputs/"PROMPTS.md"),experiment_policy=ref(inputs/"EXPERIMENT_POLICY.md"),
            preparation_audit=ref(root/"preparation_audit.json"),authorization_template=ref(root/"authorization.template.json"),
            code_head=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip(),
            final_server_intent="Separate sufficiently provisioned server batch; RTX3050 limits local work only",
            execution_policy=dict(serial=True,fresh_process_per_fit=True,maximum_formal_fits=60,
                unconditional=30,conditional=30,automatic_retry=False,OOM="stop, retain, no resizing or CPU fallback"))
        write(root/"plan.json",plan);write(root/"plan.seal.json",dict(version=batch.VERSION,
            plan=ref(root/"plan.json"),jobs=60,matrix_sha256=digest(jobs)))
        batch.load(root/"plan.json",deep=True)
        write(root/"verification.json",dict(passed=True,jobs=60,students=30,HGT_fits=0,
            plan=ref(root/"plan.json"),common_initial_exact=True,S5_S8_initial_exact=True,
            seconds=time.monotonic()-start))
        print("N-C2 sealed; 30 students, 0 HGT fits; awaiting separate execution authorization",flush=True)
    except BaseException:
        write(root/"prepare.failure.json",dict(traceback=traceback.format_exc(),automatic_retry=False))
        raise

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(batch.DEFAULT));a=p.parse_args()
    torch.set_num_threads(2);prepare(a.root)
