"""P2 registration and explicit D1--D3 decision gates."""
from pathlib import Path
import subprocess
import hashlib
from .io import ROOT,ref,read,checked,write

DECISIONS={
 "D1":"N-anon-s primary; original-name view only a descriptive server secondary endpoint",
 "D2":"P2: 50 epochs, strict minimum inner_val loss best; fresh G3R baseline, other 8H configs unchanged",
 "D3":"Freeze relationships, attribute layout and hyperparameters after EP9; reuse for seven categories without category tuning",
}

def require_decisions(path):
    data=read(path)
    if read(Path(path).with_suffix(".seal.json")).get("decisions")!=ref(path):
        raise ValueError("Decision seal differs")
    if not data.get("user_request") or not data.get("date"):raise ValueError("Missing explicit user decisions")
    if set(data.get("decisions",{}))!=set(DECISIONS):raise ValueError("D1-D3 missing")
    for name,text in DECISIONS.items():
        row=data["decisions"][name]
        if row.get("status")!="confirmed" or row.get("value")!=text:raise ValueError("Decision not confirmed: "+name)
    return data

def require_registration_commit(reference,commit):
    path=checked(reference)
    relative=str(path.relative_to(ROOT))
    blob=subprocess.check_output(["git","show",commit+":"+relative],cwd=str(ROOT))
    if hashlib.sha256(blob).hexdigest()!=reference["sha256"]:raise ValueError("P2 registration not committed exactly")
    subprocess.check_call(["git","merge-base","--is-ancestor",commit,"HEAD"],cwd=str(ROOT))

def registration(tasks,source_plan,approvals):
    diffs={}
    for tid,t in tasks.items():
        old=t["historical_config"];new=t["config"]
        diff={k:dict(before=old.get(k),after=new.get(k)) for k in sorted(set(old)|set(new)) if old.get(k)!=new.get(k)}
        if set(diff)!={"patience"} or diff["patience"]["after"]!=51:raise ValueError("P2 changes more than patience")
        diffs[tid]=diff
    return dict(version="edgesem-P2-v1",source_h8_plan=source_plan,config_diff=diffs,
        effective_config={tid:t["config"] for tid,t in tasks.items()},
        maximum_training_epochs=50,patience=51,schedule_epochs=50,best="strict minimum inner_val loss; first tie",
        training_protocol="grouped nested; inner_train supervision only; outer_test scored after training",
        seed=1,initialization="fresh G3R anchor at frozen constructor seed; EP1 semantic typed/new-relation copies",
        historical_comparison="descriptive only; do not attribute differences uniquely to stopping protocol",
        feature_policy="N-anon-s S0",label_policy="L-audit",
        primary_endpoint=dict(task="reentrancy_node",checkpoint="best",metric="Buggy-F1",view="N-anon-s"),
        hypotheses=dict(H1=dict(contrasts=["G4R-G3R-T","G4R-G4R-P"],require_positive_means=True,p="max of both two-sided zsplit Wilcoxon p values"),
                        H2=dict(contrasts=["G4R-A-G4R","G4R-A-G4R-Api"],require_positive_means=True,p="max of both two-sided zsplit Wilcoxon p values")),
        correction=dict(method="Holm",family=["H1","H2"],alpha=.05,compute_after="EP9"),
        secondary=["G3R-T-G3R","G3R-TA-G3R-T","access_control_node"],
        required_reports=["fold BF1/best epoch","non-SolidiFI positive-node TP/FP/FN",
            "persistent cases with source identity","two predefined rule baselines",
            "relation supports and gradients","peak allocated/reserved VRAM","fit time","u/U norms"],
        decisions={k:dict(status="pending",proposal=v) for k,v in DECISIONS.items()},
        approved_adaptations=approvals,
        gpu_probe=dict(tasks=list(tasks),profiles=["G3R","G3R-T","G4R","G4R-A"],fold=0,steps=1,
            threshold_mib=3584,measurement="peak Torch reserved; allocated and whole-card observations also reported",
            comparison_fit=False),
        norm_pilot=dict(task="reentrancy_node",fold=0,profile="G4R-A",epochs=50,
            inner_val_or_outer_test_scoring=False,best_selection=False,comparison_fit=False,
            first_post_update_encoder_gradient="finite and nonzero",
            stop_if="all final per-layer u and each U family Frobenius norm < 0.001"),
        ep7_formal_fits=20,execution_authorized=False,
        final_server_intent="Final experiments will use a server with sufficient VRAM; current limitation is this local computer.")
