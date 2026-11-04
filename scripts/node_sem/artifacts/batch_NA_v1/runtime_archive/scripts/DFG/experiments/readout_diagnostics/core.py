"""Float64 linear reference decomposition with separately audited backend residuals."""
import math
import torch
POOL_ATOL=1e-5
LOGIT_ATOL=1e-4
RTOL=1e-5
PROBABILITY_ATOL=1e-5

def finite(x,name):
    if not torch.isfinite(x).all(): raise ValueError("Nonfinite "+name)

def capture_forward(model,files):
    """Observe the original full-graph forward without changing outputs."""
    if model.training: raise ValueError("Requires eval mode")
    if not files or len(files)!=len(set(files)): raise ValueError("Empty/duplicate files")
    if any(f not in model.node_ids_by_filename for f in files): raise ValueError("Unknown file")
    captures={};calls={"h":0,"pool":0}
    def h_hook(module,args,output):
        calls["h"]+=1
        captures["h"]={k:v.detach().cpu().clone() for k,v in output.items()}
        return None
    def pool_hook(module,args):
        calls["pool"]+=1;captures["pool"]=args[0].detach().cpu().clone()
        return None
    handles=[model.gcs[-1].register_forward_hook(h_hook),model.classify.register_forward_pre_hook(pool_hook)]
    try:
        with torch.no_grad(): logits,pooled=model(files)
        logits=logits.detach().cpu().clone();pooled=pooled.detach().cpu().clone()
    finally:
        for handle in handles: handle.remove()
    if calls!={"h":1,"pool":1}: raise ValueError("Unexpected hook calls")
    if not torch.equal(pooled,captures["pool"]): raise ValueError("Actual classifier input mismatch")
    # Same device, dtype, batch shape and unchanged precision flags as the original head.
    with torch.no_grad():
        replay=torch.nn.functional.linear(captures["pool"].to(model.classify.weight.device),
            model.classify.weight,model.classify.bias).detach().cpu()
    if not torch.equal(replay,logits): raise ValueError("Actual head replay mismatch")
    h=torch.empty((model.total_nodes,model.hidden_size),dtype=pooled.dtype);seen=set()
    if set(captures["h"])!=set(model.node_ids_dict): raise ValueError("Type mapping mismatch")
    for typ,ids in model.node_ids_dict.items():
        vals=captures["h"][typ]
        if len(ids)!=len(set(ids)) or seen.intersection(ids): raise ValueError("Duplicate hidden-row mapping")
        if vals.shape!=(len(ids),model.hidden_size): raise ValueError("Hidden shape mismatch")
        if any(i<0 or i>=model.total_nodes for i in ids): raise ValueError("Hidden-row range mismatch")
        h[ids]=vals;seen.update(ids)
    if seen!=set(range(model.total_nodes)): raise ValueError("Incomplete row mapping")
    expected=torch.stack([h[model.node_ids_by_filename[f]].double().mean(0) for f in files])
    if not torch.allclose(expected,pooled.double(),atol=POOL_ATOL,rtol=RTOL): raise ValueError("Captured mean mismatch")
    for name,x in [("hidden",h),("pooled",pooled),("logits",logits)]:finite(x,name)
    return h,pooled,logits,float((expected-pooled.double()).abs().max()),replay

def decompose(hidden,weight,bias,actual_logits,actual_pool=None,replayed_logits=None):
    """Float64 identity; actual GPU residual is not assigned to nodes or bias.

    A non-exact backend reference requires the separately verified same-backend
    head replay from capture_forward. Actual logits always define predictions.
    """
    h,w,b,z=[x.detach().cpu().double() for x in (hidden,weight,bias,actual_logits)]
    if h.ndim!=2 or not len(h) or w.shape!=(2,h.shape[1]) or b.shape!=(2,) or z.shape!=(2,): raise ValueError("Invalid readout dimensions")
    for name,x in [("h",h),("w",w),("b",b),("z",z)]:finite(x,name)
    reconstructed=w.mv(h.mean(0))+b
    old_logits_ok=torch.allclose(reconstructed,z,atol=LOGIT_ATOL,rtol=RTOL)
    if (actual_pool is None)!=(replayed_logits is None):raise ValueError("Both pool and head replay required")
    if replayed_logits is None:
        if not old_logits_ok:raise ValueError("Linear readout reconstruction mismatch")
        pooled=h.mean(0)
    else:
        if not torch.equal(replayed_logits.detach().cpu(),actual_logits.detach().cpu()):raise ValueError("Actual head replay mismatch")
        pooled=actual_pool.detach().cpu().double();finite(pooled,"actual pool")
        if pooled.shape!=(h.shape[1],) or not torch.allclose(pooled,h.mean(0),atol=POOL_ATOL,rtol=RTOL):raise ValueError("Captured mean mismatch")
    signed=h.mv(w[1]-w[0]);contribution=signed/len(h);intercept=float(b[1]-b[0]);margin=float(z[1]-z[0])
    reference_margin=float(reconstructed[1]-reconstructed[0])
    identity_error=float(contribution.sum())+intercept-reference_margin
    if not math.isclose(identity_error,0.0,abs_tol=1e-10):raise ValueError("Float64 contribution identity mismatch")
    pooled_logits=w.mv(pooled)+b;pooled_margin=float(pooled_logits[1]-pooled_logits[0])
    pool_residual=pooled_margin-reference_margin;head_residual=margin-pooled_margin;total_residual=margin-reference_margin
    if not math.isclose(pool_residual+head_residual,total_residual,abs_tol=1e-10,rel_tol=1e-10):raise ValueError("Residual accounting mismatch")
    local=signed+intercept
    stats=dict(nodes=len(h),bias_margin=intercept,margin=margin,reference_margin=reference_margin,
        float64_identity_error=identity_error,pooling_margin_residual=pool_residual,head_margin_residual=head_residual,
        actual_minus_reference_margin=total_residual,
        old_logit_tolerance_passed=bool(old_logits_ok),
        old_margin_tolerance_passed=math.isclose(float(contribution.sum())+intercept,margin,abs_tol=LOGIT_ATOL,rel_tol=RTOL),
        reference_actual_class_agree=int(reconstructed.argmax())==int(z.argmax()),
        mean_node_score=float(signed.mean()),
        positive_contribution_mass=float(contribution[contribution>0].sum()),negative_contribution_mass=float(contribution[contribution<0].sum()),
        absolute_contribution_mass=float(contribution.abs().sum()),positive_score_nodes=int((signed>0).sum()),
        positive_local_margin_nodes=int((local>0).sum()),negative_local_margin_nodes=int((local<0).sum()),
        max_local_margin=float(local.max()),min_local_margin=float(local.min()),local_margin_std=float(local.std(unbiased=False)),
        reconstruction_max_abs_error=float((reconstructed-z).abs().max()))
    return signed,contribution,local,stats

def author_node_target(attrs):
    # Frozen original loader semantics; no new labels are constructed here.
    return int(attrs.get("node_info_vulnerabilities") is not None)

def validate_export(files,predictions,sources,targets):
    rows={}
    for row in predictions:
        if row["file"] in rows:raise ValueError("Duplicate prediction file")
        if row.get("score_role")!="cv_validation":raise ValueError("Wrong scoring role")
        for checkpoint in ("best","last"):
            key=checkpoint+"_positive_probability"
            if key not in row or not math.isfinite(row[key]) or not 0<=row[key]<=1:raise ValueError("Invalid historical probability")
            if row.get(checkpoint) not in (0,1):raise ValueError("Invalid historical class")
        if row.get("target") not in (0,1):raise ValueError("Invalid target")
        rows[row["file"]]=row
    if set(rows)!=set(files):raise ValueError("Held-out population mismatch")
    for f in files:
        if f not in sources or not sources[f].get("sha256"):raise ValueError("Missing source identity")
        if f not in targets or rows[f]["target"]!=targets[f]:raise ValueError("Frozen graph label mismatch")
    return rows
