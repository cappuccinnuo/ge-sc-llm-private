"""Real-data loss-mask and one-epoch CPU G0P acceptance; no formal result."""
import copy
from pathlib import Path
import torch
from torch.nn import functional as F
from .acceptance import DEFAULT,authorize
from .prepare import read,write,ref,checked
from .spelling_features import assemble
from .runtime_model import make_model,make_placebo
from .audit_supervision import bind_rows,AuditSupervision
from .support import model_support
from .checkpoint import build_binding,StopMonitor
from .input_guard import FitInputGuard
from .trainer import fit
from ..diagnostics8c.placebo import numerical_denominator_proof,EMPTY_PREFIX
from ..experiment.init import seeds
from ..tasks import read_labels
from scripts.DFG.experiments.common import seed_all,tensor_digest,metrics

def run():
    out=DEFAULT/"acceptance";authorize(out/"real_mask.json")
    source=read(DEFAULT/"authorization.json")["source_plan"];plan=read(checked(source))
    tid="reentrancy_node";t=plan["tasks"][tid];cfg=copy.deepcopy(t["effective_config"])
    cfg.update(device="cpu",maximum_training_epochs=1,mode="acceptance_placebo_one_epoch")
    torch.set_num_threads(cfg["threads"])
    split=read(checked(t["folds"]))["folds"][0]
    sf=seeds("node",0,1);seed_all(sf["constructor"])
    feature=t["feature_view"]["anonymous"]
    graph=assemble(checked(t["profiles"]["G0"]["graph"]),feature)
    base=make_model("node",graph,"G0","cpu",hidden_size=cfg["hidden_size"],layers=cfg["layers"],heads=cfg["heads"],reducer="mean",layer_impl="shared_projection")
    table=bind_rows(base,tid,plan["bound_artifacts"]["label_views"])
    base.eval();checks={};labels=read_labels(t["original_record"]["labels"])
    with torch.no_grad():all_logits=base()
    for role in ("inner_train","inner_val","outer_test"):
        part=AuditSupervision(base,"node",split[role+"_files"],table)
        logits=all_logits.detach().clone().requires_grad_(True)
        loss=F.cross_entropy(logits[part.mask],part.targets(base,labels));loss.backward()
        excluded=part.audit_targets.clone()
        selected_excluded=torch.tensor([i in part.all_full_ids and i not in part.full_ids for i in range(base.total_nodes)])
        excluded[selected_excluded]=1-excluded[selected_excluded]
        altered_loss=F.cross_entropy(logits[part.mask],excluded[part.mask])
        pred=logits[part.mask].argmax(1).tolist()
        before=metrics(part.targets(base,labels).tolist(),pred)
        after=metrics(excluded[part.mask].tolist(),pred)
        a,b=StopMonitor(7,.001),StopMonitor(7,.001)
        decision_a=a.step(float(loss));decision_b=b.step(float(altered_loss))
        checks[role]=dict(masked_nodes=int(selected_excluded.sum()),included_nodes=len(part.full_ids),
            direct_excluded_logit_gradient_zero=bool((logits.grad[~part.mask]==0).all()),
            loss_bitwise_equal=torch.equal(loss,altered_loss),metrics_equal=before==after,
            best_choice_equal=decision_a==decision_b and a.best==b.best)
        if not all(checks[role][k] for k in ("direct_excluded_logit_gradient_zero","loss_bitwise_equal","metrics_equal","best_choice_equal")):raise AssertionError("Real mask failed")
    write(out/"real_mask.json",dict(passed=True,task=tid,fold=0,checks=checks,optimizer_steps=0,
        interpretation="Zero direct loss contribution only; graph messages through masked nodes are retained"))
    model=make_placebo(base,plan["G0P"]["schemas"][tid]["target_counts"])
    initial={k:v.detach().clone() for k,v in model.state_dict().items()}
    initial_path=out/"placebo_untrained_initial.pt"
    torch.save(dict(kind="untrained_initial",optimizer_steps=0,state_dict=initial,state_sha256=tensor_digest(initial)),str(initial_path))
    counts=model_support(model,split)
    binding=build_binding(model,task_id=tid,fold=0,seed=1,profile="G0P",reducer="mean",
        graph_ref=t["profiles"]["G0"]["graph"],fold_ref=t["folds"],label_ref=t["original_record"]["labels"],
        initial_sha256=ref(initial_path)["sha256"],config=cfg,split=split,support=counts)
    binding.update(label_policy="L-audit",label_view=plan["bound_artifacts"]["label_views"],
        feature_view=feature,feature_npz=read(checked(feature))["data"],initial_state_sha256=tensor_digest(initial))
    parts={r:AuditSupervision(model,"node",split[r+"_files"],table) for r in ("inner_train","inner_val","outer_test")}
    seed_all(sf["fit"])
    with FitInputGuard(model,binding,parts,labels) as guard:
        result=fit(model,guard.wrap_parts(),"node",labels,cfg,out/"placebo_fit",binding,model.original_graph_node_ids,counts)
        guard.finish()
    extras=[c for c in model.etypes_dict if c[1].startswith(EMPTY_PREFIX)]
    for i,layer in enumerate(model.gcs):
        for name in ("relation_att","relation_msg","relation_pri"):
            tensor=getattr(layer,name)
            for c in extras:
                idx=model.etypes_dict[c]
                if tensor.grad is not None and tensor.grad[idx].count_nonzero():raise AssertionError("Empty relation has supervised gradient")
                if not torch.equal(tensor.detach()[idx],initial["gcs.%d.%s"%(i,name)][idx]):raise AssertionError("Empty relation parameter changed")
    proof=numerical_denominator_proof()
    write(out/"placebo_smoke.json",dict(passed=True,task=tid,epochs=1,formal_fits=0,
        empty_relations=len(extras),empty_edges=0,empty_gradients_zero=True,empty_parameters_unchanged=True,
        numerical_denominator=proof,source_plan=source,feature_view=feature,
        guard=guard.summary(),checkpoint_roundtrip=result["checkpoint_roundtrip_exact"]))
    print("real mask and G0P smoke PASSED",flush=True)
if __name__=="__main__":run()
