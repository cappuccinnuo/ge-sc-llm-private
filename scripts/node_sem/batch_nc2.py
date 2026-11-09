"""N-C2 admission: 30 S5 plus 30 prespecified, outcome-gated S8 jobs."""
import copy
from pathlib import Path
import torch
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,ref,checked
from scripts.DFG.dfg_v2.benchmark_v2.protocol import validate_parts
from scripts.DFG.dfg_v2.experiment.init import parameter_seed
from scripts.DFG.experiments.common import digest,tensor_digest
from . import batch_nc1 as parent
from . import batch_na as na
from .feature_spec import FeatureSpec
from .init import checked_initial
from .nc1_history import verify_index
from .nc2_init import VERSION as INIT_VERSION,baseline_state
from .student import s8_gate

ROOT=parent.ROOT
DEFAULT=na.ARTIFACTS/"batch_NC2_v1"
VERSION="nodesem-nc2-plan-v1"
TASK_FOLDS=parent.TASK_FOLDS
PROTOCOL_NAME=parent.PROTOCOL_NAME
PROTOCOL_VERSION=parent.PROTOCOL_VERSION
LOCAL_DEV_POLICY=parent.LOCAL_DEV_POLICY
MODULES=("student.py","student_artifacts.py","p8b_students.py","nc2_init.py","nc2_carrier.py",
         "batch_nc2.py","p8b_prepare.py","batch_nc2_worker.py","batch_nc2_controller.py","nc2_gate.py",
         "nc1_reporting.py","reporting.py","nb_reporting.py")

def runtime():
    result=parent.runtime()
    for n in MODULES:
        p=ROOT/"scripts/node_sem"/n
        result[str(p.relative_to(ROOT))]=ref(p)["sha256"]
    return result

def matrix():
    return [dict(task_id=t,granularity=t.rsplit("_",1)[-1],fold=f,seed=1,profile="G3R",
                 name=name,view="original",reuse_8h=False)
            for name in ("S5","S8") for t,n in TASK_FOLDS for f in range(n)]

def validate_matrix(jobs):
    if len(jobs)!=60 or [na.key(j) for j in jobs]!=[na.key(j) for j in matrix()]:
        raise ValueError("N-C2 requires 30 ordered S5 and 30 conditional S8")
    for j in jobs:
        if type(j["fold"]) is not int or type(j["seed"]) is not int or j["view"]!="original" or j["reuse_8h"] is not False or j["granularity"]!=j["task_id"].rsplit("_",1)[-1]:
            raise ValueError("Invalid N-C2 identity")

def statistics_spec():
    value=copy.deepcopy(parent.statistics_spec())
    value["primary"]["comparison"]=["S5","S4"]
    value["descriptive"]["positive_comparison"]="S4/S5/S6/S8 by source SHA, file and node identity"
    value["continuation"]=dict(task_id="reentrancy_node",checkpoint="best",score_role="outer_test",
        comparison=["S5","S4"],metric="buggy_f1",aggregate="equal fold mean",
        operator="strictly > 0",then="execute all 30 S8",otherwise="skip all S8")
    value["conditional_test"]=dict(comparison=["S5","S8"],task_id="reentrancy_node",
        checkpoint="best",correction="Holm jointly with S5-S4 only if S8 executed",
        selection_limitation="S8 is outcome-gated; Holm does not remove exploratory selection")
    value["teacher_gap"]="Report S5-S6 and S5-S4 in pp; retention ratio only if S6-S4 > 0, otherwise not interpretable"
    value["limitations"] += ["S5/S8 use identical all initial tensors and RNG identities; only student rows are permuted",
        "Student outer teacher cosine is diagnostic, never a fit or stopping input"]
    return value

def make_spec(s4,student_ref,name):
    if name not in ("S5","S8") or s4.name!="S4" or s4.view!="original" or s4.fusion!="concat":
        raise ValueError("Invalid student feature configuration")
    value=s4.to_json();value["name"]=name
    value["modalities"].append(dict(name="student",dim=384,normalize=True,manifest=student_ref))
    return FeatureSpec.from_json(value)

def execution_order(jobs):
    validate_matrix(jobs)
    from .batch_na_worker import job_id
    return [job_id(j) for j in jobs]

validate_device_comparisons=parent.validate_device_comparisons

def validate_envelope(plan,seal,reference):
    if (plan.get("version")!=VERSION or seal.get("version")!=VERSION or seal.get("plan")!=reference
            or seal.get("jobs")!=60 or seal.get("matrix_sha256")!=digest(plan["jobs"])):
        raise ValueError("N-C2 seal differs")
    if (plan.get("execution_authorized") is not False or plan.get("view")!="original"
        or plan.get("label_policy")!="L-audit" or plan.get("protocol")!=PROTOCOL_NAME
        or plan.get("protocol_version")!=PROTOCOL_VERSION or plan.get("statistics")!=statistics_spec()
        or plan.get("resource_policy")!=LOCAL_DEV_POLICY or plan.get("initialization_version")!=INIT_VERSION):
        raise ValueError("N-C2 protocol differs")
    validate_matrix(plan["jobs"]);validate_device_comparisons(plan["jobs"])
    if plan["device_families"]!={j["task_id"]:j["device_policy"] for j in plan["jobs"]}:
        raise ValueError("Device family differs")
    return True

def load(path,mode="verify",deep=False):
    if mode not in ("verify","launch"):raise ValueError("Invalid mode")
    path=Path(path);plan=read(path);validate_envelope(plan,read(path.with_name("plan.seal.json")),ref(path))
    for name,sha in plan["runtime"].items():
        checked(dict(path=str(ROOT/name),sha256=sha))
        if plan["runtime_archive"][name]["sha256"]!=sha:raise ValueError("Runtime archive differs")
        checked(plan["runtime_archive"][name])
    for k in ("decisions","prompt","experiment_policy","student_plan","students_complete","preparation_audit","authorization_template"):
        checked(plan[k])
    original=parent.load(checked(plan["nc1_plan"]))
    report=read(checked(plan["nc1_report"]))
    if report["continuation"]["continue_student"] is not True:raise ValueError("N-C1 continuation missing")
    parents=verify_index(plan["na_result_index"])
    if plan["source_h8_plan"]!=original["source_h8_plan"]:raise ValueError("8H plan changed")
    students=read(checked(plan["students_complete"]))
    if students.get("passed") is not True or students["students"]!=30:raise ValueError("Student preparation incomplete")
    by_student={}
    for r in students["records"]:
        v=read(checked(r));checked(v["diagnostics"])
        if not v["passed"]:raise ValueError("Failed student")
        by_student[(v["task_id"],v["fold"])]=v
    seen=set();by_pair={}
    for j in plan["jobs"]:
        old=parents[j["baseline_job_id"]]["job"]
        for k in ("config","graph","labels","folds","label_view","split","graph_files","h8_initial","initialization",
                  "seeds","source_preparation","support","device_policy","registered_node_types",
                  "original_graph_fingerprint","node_count"):
            if j[k]!=old[k]:raise ValueError("Frozen S4 input changed: "+k)
        if j["baseline_receipt"]!=parents[j["baseline_job_id"]]["receipt"]:raise ValueError("Baseline receipt changed")
        validate_parts(j["split"],j["graph_files"])
        for k in ("spec","feature_view","feature_npz","initial","preparation_evidence"):
            checked(j[k])
            if path.parent.resolve() not in Path(j[k]["path"]).resolve().parents:
                raise ValueError("New artifact outside N-C2")
        student=by_student[(j["task_id"],j["fold"])][j["name"]]
        spec=FeatureSpec.from_json(read(checked(j["spec"])))
        want=make_spec(FeatureSpec.from_json(read(checked(old["spec"]))),student,j["name"])
        if spec.to_json()!=want.to_json() or spec.digest()!=j["spec_sha256"]:
            raise ValueError("Wrong per-fold STUDENT or unchanged S4 modalities")
        for m in spec.modalities:na.checked_tree(read(checked(m["manifest"])),seen)
        carrier=read(checked(j["feature_view"]))
        if (carrier["data"]!=j["feature_npz"] or carrier["spec"]!=spec.to_json()
            or carrier["spec_sha256"]!=spec.digest() or carrier["task_id"]!=j["task_id"]
            or carrier["feature_shape"]!=[j["node_count"],spec.carrier_dim()]
            or carrier["original_graph_fingerprint"]!=j["original_graph_fingerprint"]
            or not carrier["original_inputs_unchanged"]):
            raise ValueError("Carrier differs")
        proof=read(checked(j["preparation_evidence"]))
        if (proof["initial"]!=j["initial"] or not proof["common_bitwise_equal"]
            or proof["baseline_state_sha256"]!=old["initial"]["state_sha256"]
            or proof["dropout"]!=j["dropout"] or proof["optimizer_steps"]!=0):
            raise ValueError("Initial pairing proof differs")
        pair=(j["task_id"],j["fold"])
        if j["name"]=="S5":
            by_pair[pair]=j
            if j["paired_random_spec_sha256"]!=spec.digest():raise ValueError("S5 RNG identity differs")
        else:
            s5=by_pair[pair]
            if (j["initial"]["state_sha256"]!=s5["initial"]["state_sha256"]
                or j["paired_random_spec_sha256"]!=s5["spec_sha256"]
                or j["dropout"]!=s5["dropout"] or j["seeds"]!=s5["seeds"]):
                raise ValueError("S5/S8 initial or random stream differs")
        expected={n:parameter_seed(j["seeds"]["fit"],"modality_dropout",
            [j["task_id"],j["fold"],j["profile"],j["paired_random_spec_sha256"],n]) for n in j["registered_node_types"]}
        if j["dropout"]["seeds"]!=expected or j["dropout"]["spec_digest"]!=j["paired_random_spec_sha256"]:
            raise ValueError("Dropout identity mismatch")
        if deep:
            p=checked_initial(j["initial"],j["task_id"],j["fold"],"G3R",spec_digest=spec.digest())
            base,_=baseline_state(old) if proof["baseline_mode"]=="existing_NA_initial" else (checked_initial(
                proof["reconstructed_initial"],j["task_id"],j["fold"],"G3R",spec_digest=old["spec_sha256"])["state_dict"],None)
            if (tensor_digest(base)!=old["initial"]["state_sha256"] or p["source"]!=old["h8_initial"]
                or p["initialization_version"]!=INIT_VERSION or p["formal_training"] is not False
                or any(k not in p["state_dict"] or not torch.equal(v,p["state_dict"][k]) for k,v in base.items())):
                raise ValueError("Shared initial state mismatch")
    auth=read(checked(plan["authorization_template"]))
    if auth["execution_authorized"] is not False or auth["unconditional_jobs"]!=30 or auth["conditional_jobs"]!=30 or auth["matrix_sha256"]!=digest(plan["jobs"]):
        raise ValueError("Authorization template mismatch")
    return plan
