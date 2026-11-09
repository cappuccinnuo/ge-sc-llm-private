"""NS-P7c CPU diagnostics. Estimation/selection use train/val only."""
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from .p6c_core import ROLES

ALPHA_GRID=(.01,.1,1.,10.)


def validate_indices(indices,n):
    if set(indices)!=set(ROLES):raise ValueError("Wrong split roles")
    sets=[]
    for role in ROLES:
        idx=np.asarray(indices[role])
        if idx.ndim!=1 or (idx.size and not np.issubdtype(idx.dtype,np.integer)):
            raise ValueError("Invalid indices")
        s=set(map(int,idx))
        if len(s)!=len(idx) or min(s,default=0)<0 or max(s,default=0)>=n:
            raise ValueError("Invalid or duplicate split indices")
        sets.append(s)
    if any(sets[i]&sets[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError("Split leakage")


def cosine(a,b):
    a,b=np.asarray(a,dtype=np.float64),np.asarray(b,dtype=np.float64)
    if a.shape!=b.shape or a.ndim!=2:raise ValueError("Cosine shape differs")
    den=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
    return np.divide((a*b).sum(1),den,out=np.zeros(len(a)),where=den>0)


def ridge_probe(x,y,kinds,indices):
    x,y=np.asarray(x,dtype=np.float64),np.asarray(y,dtype=np.float64)
    kinds=np.asarray(kinds)
    if x.ndim!=2 or y.ndim!=2 or len(x)!=len(y) or len(kinds)!=len(x):
        raise ValueError("Probe shape differs")
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError("Nonfinite probe data")
    validate_indices(indices,len(x))
    counts={r:len(indices[r]) for r in ROLES}
    for r in ROLES:
        if not counts[r]:return dict(status="not_estimable_"+r+"_empty",counts=counts)
    tr,va,te=(np.asarray(indices[r],dtype=int) for r in ROLES)
    scaler=StandardScaler().fit(x[tr])
    train,val=scaler.transform(x[tr]),scaler.transform(x[va])
    candidates=[]
    for alpha in ALPHA_GRID:
        model=Ridge(alpha=alpha,solver="cholesky",fit_intercept=True)
        model.fit(train,y[tr])
        score=float(cosine(model.predict(val),y[va]).mean())
        candidates.append((score,alpha,model))
    best=min(candidates,key=lambda v:(-v[0],v[1]))
    prediction=best[2].predict(scaler.transform(x[te]))
    scores=cosine(prediction,y[te])
    means={kind:y[tr[kinds[tr]==kind]].mean(0) for kind in sorted(set(kinds[tr]))}
    valid=np.asarray([k in means for k in kinds[te]])
    baseline=np.asarray([means[k] for k in kinds[te][valid]])
    base_scores=cosine(baseline,y[te][valid]) if valid.any() else np.asarray([])
    return dict(status="ok",counts=counts,selected_alpha=best[1],inner_val_mean_cosine=best[0],
        candidates=[dict(alpha=a,inner_val_mean_cosine=s) for s,a,_ in candidates],
        outer_mean_cosine=float(scores.mean()),outer_cosines=scores.tolist(),
        baseline_n=int(valid.sum()),baseline_unseen_types=sorted(set(kinds[te][~valid])),
        baseline_unseen_rows=int((~valid).sum()),
        baseline_mean_cosine=float(base_scores.mean()) if valid.any() else None,
        ridge_on_baseline_population=float(scores[valid].mean()) if valid.any() else None,
        baseline_cosines=base_scores.tolist(),baseline_outer_indices=np.flatnonzero(valid).tolist(),
        zero_predictions=int((np.linalg.norm(prediction,axis=1)==0).sum()),
        scaler_fit_role="inner_train",model_fit_role="inner_train",
        baseline_fit_role="inner_train",selection_role="inner_val",
        outer_used_in_selection=False,seed=1,solver="Ridge cholesky (deterministic)")


def align_teacher(rows,manifest,values):
    source=manifest["rows"]
    if len(source)!=len(values) or len({r["row_key"] for r in source})!=len(source):
        raise ValueError("Duplicate teacher identity")
    indexed={r["row_key"]:(i,r) for i,r in enumerate(source)}
    if set(indexed)!={r["row_key"] for r in rows}:raise ValueError("Different teacher populations")
    indices=[];present=[]
    for r in rows:
        i,t=indexed[r["row_key"]]
        for key in ("file","node_type","code_sha256"):
            if r[key]!=t[key]:raise ValueError("Teacher/source identity differs")
        if "source_sha256" in r and r["source_sha256"]!=t["source_sha256"]:
            raise ValueError("Teacher source SHA differs")
        indices.append(i);present.append(t["present"])
    return values[indices].copy(),np.asarray(present,dtype=bool)
