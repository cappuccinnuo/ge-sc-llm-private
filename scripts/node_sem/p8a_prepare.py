"""NS-P8a CPU-only preparation. Reuses NodeSem carrier, constructors and initialization."""
import argparse
import copy
import gc
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import numpy as np
import torch
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.support import model_support
from scripts.DFG.experiments.common import seed_all, tensor_digest, digest
from . import batch_nc1 as batch
from . import batch_na as na
from .nc1_history import audit
from .nc1_init import baseline_state, paired_state, VERSION
from .init import checked_initial
from .feature_spec import FeatureSpec
from .carrier import write_carrier
from .model import make_nodesem_model
from .execution import _validate_carrier
from .na_carrier import load_carrier, construct_carried
from .p6_prepare import device_policy

BASE = batch.ROOT / "scripts/node_sem"


def compare_carriers(old_job, new_job, old_spec, new_spec):
    old = read(checked(old_job["feature_view"]))
    new = read(checked(new_job["feature_view"]))
    if [(r["row_key"],r["original_graph_node_id"]) for r in old["rows"]] != [
            (r["row_key"],r["original_graph_node_id"]) for r in new["rows"]]:
        raise ValueError("Carrier row order differs")
    with np.load(str(checked(old_job["feature_npz"])), allow_pickle=False) as a:
        previous = a["features"].copy()
    with np.load(str(checked(new_job["feature_npz"])), allow_pickle=False) as a:
        values = a["features"]
    for name, part in old_spec.layout().items():
        newer = new_spec.layout()[name]
        if (not np.array_equal(previous[:, part["start"]:part["stop"]], values[:, newer["start"]:newer["stop"]])
                or not np.array_equal(previous[:, part["presence"]], values[:, newer["presence"]])):
            raise ValueError("Old S4 modality or presence changed")
    return dict(passed=True, rows=len(values), S4_modalities_bitwise=True,
                S4_dimension=old_spec.carrier_dim(), S6_dimension=new_spec.carrier_dim())


def prepare(out, decisions_ref, power_ref):
    out = Path(out).resolve()
    if na.ARTIFACTS.resolve() not in out.parents: raise ValueError("Wrong artifact root")
    out.mkdir(parents=True, exist_ok=False)
    write(out/"prepare.started.json",dict(pid=os.getpid(),unix_seconds=time.time(),formal_fits=0))
    start = time.monotonic()
    try:
        decisions = read(checked(decisions_ref))
        if not all(decisions.get(k) is True for k in ("independent_nc1_adapter", "operational_stop_not_impossibility")):
            raise ValueError("Approved design decisions absent")
        checked(power_ref)
        parent, index = audit(na.DEFAULT, out/"na_result_index.json")
        from scripts.DFG.dfg_v2.benchmark_v2.execution import load as load_h8
        load_h8(checked(parent["source_h8_plan"]))
        p7 = BASE/"artifacts/llm_v3"
        gate = read(p7/"finalization/complete.json")
        if not gate["passed"] or gate["HGT_training"] or gate["student_training"]:
            raise ValueError("NS-P7c incomplete")
        checked(gate["report"]); checked(gate["results"])
        teacher_ref = read(p7/"teacher/index.seal.json")["index"]
        teacher = read(checked(teacher_ref))
        if not teacher["repeat_bitwise"] or teacher["optimizer_steps"] != 0:
            raise ValueError("Teacher encoding acceptance incomplete")
        policy, hardware = device_policy()
        if any(v != policy for v in parent["device_families"].values()):
            raise ValueError("Current GPU/torch/CUDA/TF32 differs from N-A")
        inputs = out/"inputs"; inputs.mkdir()
        for name in ("PROMPTS.md", "EXPERIMENT_POLICY.md"):
            (inputs/name).write_bytes((BASE/name).read_bytes())
        code = batch.runtime(); archives = {}
        for name, sha in code.items():
            target=out/"runtime_archive"/name; target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("xb") as f:f.write((batch.ROOT/name).read_bytes())
            archives[name]=ref(target)
            if archives[name]["sha256"] != sha: raise ValueError("Runtime changed during snapshot")
        jobs=[]; groups=[]; resources=[]
        for task, folds in batch.TASK_FOLDS:
            rows=sorted((r for r in index["records"] if r["job"]["task_id"]==task),key=lambda r:r["job"]["fold"])
            if [r["job"]["fold"] for r in rows] != list(range(folds)): raise ValueError("Missing S4 folds")
            old0=rows[0]["job"]; oldspec=FeatureSpec.from_json(read(checked(old0["spec"])))
            spec=batch.make_spec(oldspec,teacher["tasks"][task])
            group=out/"prepared"/task/"G3R"/"S6"; group.mkdir(parents=True)
            write(group/"spec.json",spec.to_json())
            graph=read_graph(checked(old0["graph"])); fingerprint=graph_fingerprint(graph)
            carrier=write_carrier(spec,task,graph,group/"carrier")
            mini=dict(feature_view=carrier["manifest"],feature_npz=carrier["data"])
            preservation=compare_carriers(old0,mini,oldspec,spec)
            seed_all(old0["seeds"]["constructor"])
            model=make_nodesem_model(old0["granularity"],old0["graph"],"G3R",spec,old0["config"],"cpu",task)
            _validate_carrier(model,mini)
            parameter_count=sum(p.numel() for p in model.parameters())
            baseline_model=None
            if any(not Path(r["job"]["initial"]["path"]).exists() for r in rows):
                seed_all(old0["seeds"]["constructor"])
                baseline_model=make_nodesem_model(old0["granularity"],old0["graph"],"G3R",oldspec,old0["config"],"cpu",task)
            group_jobs=[]
            for row in rows:
                old=row["job"]; fold=old["fold"]
                for k in ("graph","config","spec","device_policy"):
                    if old[k] != old0[k]: raise ValueError("Fold structure group differs")
                baseline, mode=baseline_state(old,baseline_model)
                state, common=paired_state(model,spec,old,baseline)
                j=copy.deepcopy(old)
                j.update(name="S6",spec=ref(group/"spec.json"),spec_sha256=spec.digest(),
                    feature_view=carrier["manifest"],feature_npz=carrier["data"],
                    carrier_dim=spec.carrier_dim(),parameters=parameter_count,
                    baseline_job_id=__import__("scripts.node_sem.batch_na_worker",fromlist=["job_id"]).job_id(old),
                    baseline_receipt=row["receipt"])
                j.pop("config_template",None);j.pop("constructor_seconds",None)
                target=group/("fold_%d"%fold);target.mkdir()
                reconstructed=None
                if mode != "existing_NA_initial":
                    payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task,fold=fold,
                        seed=1,profile="G3R",constructor_seed=old["seeds"]["constructor"],
                        fit_seed=old["seeds"]["fit"],feature_spec_sha256=oldspec.digest(),
                        state_dict=baseline,state_sha256=tensor_digest(baseline),formal_training=False,
                        source=old["h8_initial"])
                    with (target/"S4_reconstructed.pt").open("xb") as f:torch.save(payload,f)
                    reconstructed=dict(ref(target/"S4_reconstructed.pt"),state_sha256=tensor_digest(baseline))
                payload=dict(kind="untrained_initial",optimizer_steps=0,task_id=task,fold=fold,
                    seed=1,profile="G3R",constructor_seed=old["seeds"]["constructor"],fit_seed=old["seeds"]["fit"],
                    feature_spec_sha256=spec.digest(),initialization_version=VERSION,state_dict=state,
                    state_sha256=tensor_digest(state),source=old["h8_initial"],formal_training=False,
                    baseline_state_sha256=old["initial"]["state_sha256"],baseline_mode=mode)
                with (target/"initial.pt").open("xb") as f:torch.save(payload,f)
                j["initial"]=dict(ref(target/"initial.pt"),state_sha256=payload["state_sha256"])
                loaded=checked_initial(j["initial"],task,fold,"G3R",spec_digest=spec.digest())
                model.load_state_dict(loaded["state_dict"],strict=True)
                if tensor_digest(model.state_dict())!=payload["state_sha256"]:raise ValueError("Reload mismatch")
                j["dropout"]=na.dropout_identity(model,j,spec)
                if model_support(model,j["split"]) != old["support"]:raise ValueError("Graph/schema/support changed")
                proof=dict(common,initial=j["initial"],baseline_mode=mode,reconstructed_initial=reconstructed,
                    dropout=j["dropout"],optimizer_steps=0,CPU_reload_exact=True,baseline_receipt=row["receipt"])
                write(target/"preparation.json",proof);j["preparation_evidence"]=ref(target/"preparation.json")
                write(target/"job.json",j);jobs.append(j);group_jobs.append(j)
                del baseline,state,payload,loaded
                print("prepared %d/30 %s fold%d S6"%(len(jobs),task,fold),flush=True)
            # Fresh constructor for fold1: prove reuse and fast carrier against the deep path.
            j=group_jobs[1]; old=rows[1]["job"]
            carried,record,fastspec=load_carrier(j)
            seed_all(j["seeds"]["constructor"])
            fresh=construct_carried(j,carried,record,fastspec)
            base,_=baseline_state(old,baseline_model)
            a,_=paired_state(model,spec,old,base);b,_=paired_state(fresh,spec,old,base)
            if set(a)!=set(b) or any(not torch.equal(a[k],b[k]) for k in a):
                raise ValueError("Fresh vs reused structure initial differs")
            for t in model.ntypes_dict:
                if not torch.equal(model.symmetrical_global_graph.nodes[t].data["inp"],fresh.symmetrical_global_graph.nodes[t].data["inp"]):
                    raise ValueError("Fast vs deep carrier model input differs")
            preservation.update(fresh_structure_initial_exact=True,fast_carrier_exact=True,
                source_nodes_unchanged=graph_fingerprint(graph)==fingerprint,parameters=parameter_count,
                parameter_delta=parameter_count-old0["parameters"])
            if not preservation["source_nodes_unchanged"]:raise ValueError("Original graph mutated")
            write(group/"group_proof.json",preservation);groups.append(ref(group/"group_proof.json"))
            seconds=sum(r["total_seconds"] for r in rows)
            resources.append(dict(task_id=task,fits=folds,historical_S4_seconds=seconds,
                scenario_hours=[seconds/3600,2*seconds/3600],not_measured_S6=True,
                parameters=parameter_count,parameter_delta=parameter_count-old0["parameters"],
                carrier_additional_bytes=len(graph)*385*4,
                historical_resources=[r["resources"] for r in rows]))
            del model,fresh,carried,record,graph,a,b,base,baseline_model;gc.collect()
        batch.validate_matrix(jobs);batch.validate_device_comparisons(jobs)
        if torch.cuda.is_initialized() or code!=batch.runtime():raise ValueError("GPU initialized or source changed")
        write(out/"preparation_audit.json",dict(passed=True,jobs=30,groups=groups,
            optimizer_steps=0,formal_fits=0,cuda_initialized=False,seconds=time.monotonic()-start,hardware=hardware))
        write(out/"resource_estimate.json",dict(groups=resources,range_hours=[
            sum(r["scenario_hours"][i] for r in resources) for i in (0,1)],
            caveat="1-2x historical S4 wall time scenario only, not measured S6 or a confidence interval",
            OOM="stop and retain attempts; report completed tasks; move whole affected comparison to new server batch"))
        families={t:copy.deepcopy(policy) for t,_ in batch.TASK_FOLDS}
        write(out/"authorization.template.json",dict(version=batch.VERSION,execution_authorized=False,
            scope="formal_NC1",jobs=30,matrix_sha256=digest(jobs),view="original",label_policy="L-audit",
            seeds=[1],planned_device_families=families,user_request=None,
            external_interrupt_retry_once=False,
            instructions="Separate explicit execution approval bound to plan/seal and revision; never edit this template"))
        plan=dict(version=batch.VERSION,protocol=batch.PROTOCOL_NAME,protocol_version=batch.PROTOCOL_VERSION,
            execution_authorized=False,view="original",label_policy="L-audit",jobs=jobs,
            source_h8_plan=parent["source_h8_plan"],source_preparation=parent["source_preparation"],
            na_result_index=ref(out/"na_result_index.json"),teacher_index=teacher_ref,
            runtime=code,runtime_archive=archives,statistics=batch.statistics_spec(),
            device_families=families,resource_policy=batch.LOCAL_DEV_POLICY,initialization_version=VERSION,
            decisions=decisions_ref,power_check=power_ref,prompt=ref(inputs/"PROMPTS.md"),
            experiment_policy=ref(inputs/"EXPERIMENT_POLICY.md"),
            preparation_audit=ref(out/"preparation_audit.json"),resource_estimate=ref(out/"resource_estimate.json"),
            authorization_template=ref(out/"authorization.template.json"),
            code_head=subprocess.check_output(["git","rev-parse","HEAD"],universal_newlines=True).strip(),
            final_server_intent="Final experiments on sufficiently provisioned server in a separate batch; current RTX3050 limit is local development only",
            execution_policy=dict(serial=True,fresh_process_per_fit=True,configuration_override=False,
                oom="stop affected task and controller; preserve and report completed tasks; no unilateral S6-only server rerun",
                failure="retain attempts, stop, no automatic retry",no_automatic_NS_P8b=True))
        write(out/"plan.json",plan);write(out/"plan.seal.json",dict(version=batch.VERSION,
            plan=ref(out/"plan.json"),jobs=30,matrix_sha256=digest(jobs)))
        batch.load(out/"plan.json",deep=True)
        write(out/"verification.json",dict(passed=True,jobs=30,plan=ref(out/"plan.json"),
            formal_fits=0,common_initial_all_exact=True,carrier_groups=4,seconds=time.monotonic()-start))
        write(out/"verification.seal.json",dict(verification=ref(out/"verification.json"),plan=ref(out/"plan.json")))
        print("N-C1 sealed and verified; 0 formal fits; separate authorization required",flush=True)
    except BaseException:
        write(out/"prepare.failure.json",dict(traceback=traceback.format_exc(),automatic_retry=False,formal_fits=0))
        raise


def main():
    ap=argparse.ArgumentParser();ap.add_argument("command",choices=("prepare","verify"))
    ap.add_argument("--out",default=str(batch.DEFAULT));ap.add_argument("--decisions");ap.add_argument("--power")
    a=ap.parse_args();torch.set_num_threads(2)
    if a.command=="prepare":
        if not a.decisions or not a.power:ap.error("--decisions and --power required")
        prepare(a.out,ref(Path(a.decisions)),ref(Path(a.power)))
    else:
        batch.load(Path(a.out)/"plan.json",deep=True);print("verified 30 S6 jobs, not trained")

if __name__=="__main__":main()
