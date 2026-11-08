"""Read-only NS-P6c estimands and leakage-free diagnostic logistic probes."""
import warnings
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, balanced_accuracy_score, f1_score
from sklearn.exceptions import ConvergenceWarning

C_GRID = (0.01, 0.1, 1.0, 10.0)
ROLES = ("inner_train", "inner_val", "outer_test")


def removed_input(inp, spec, removed):
    layout = spec.layout()
    if set(removed) - set(layout):
        raise ValueError("Unknown modality")
    result = inp.clone()
    for name in removed:
        result[:, layout[name]["presence"]] = 0
    return result


def contribution_arrays(projected, gates, presence):
    if projected.ndim != 3 or gates.shape != projected.shape[:2] or presence.shape != gates.shape:
        raise ValueError("Contribution shape mismatch")
    if not torch.isfinite(projected).all() or not torch.isfinite(gates).all():
        raise ValueError("Nonfinite contribution")
    if not ((presence == 0) | (presence == 1)).all():
        raise ValueError("Nonbinary presence")
    if ((gates < 0) | (gates > 1)).any() or (gates[presence == 0] != 0).any():
        raise ValueError("Invalid gates")
    if not torch.allclose(gates.sum(1), (presence.sum(1)>0).to(gates.dtype), atol=1e-6, rtol=0):
        raise ValueError("Unnormalized gates")
    effective = gates * projected.norm(dim=-1)
    total = effective.sum(1, keepdim=True)
    share = torch.where(total > 0, effective / total.clamp(min=1e-30), torch.zeros_like(effective))
    return effective, share, total[:, 0] > 0


def distribution(values):
    a = np.asarray(values, dtype=float)
    if not np.isfinite(a).all():
        raise ValueError("Nonfinite distribution")
    return dict(n=int(a.size), mean=float(a.mean()) if a.size else None,
        sd=float(a.std(ddof=1)) if a.size > 1 else None,
        quantiles=np.percentile(a, [0,5,25,50,75,95,100]).tolist() if a.size else [])


def split_indices(files, split, available=None):
    files = np.asarray(files)
    available = np.ones(len(files), dtype=bool) if available is None else np.asarray(available, dtype=bool)
    if available.shape != files.shape:
        raise ValueError("Availability shape mismatch")
    groups = {r: set(split[r+"_files"]) for r in ROLES}
    if any(len(groups[r]) != len(split[r+"_files"]) for r in ROLES):
        raise ValueError("Duplicated split file")
    if any(groups[a] & groups[b] for i,a in enumerate(ROLES) for b in ROLES[i+1:]):
        raise ValueError("Overlapping split")
    if set(files) - set.union(*groups.values()):
        raise ValueError("Unassigned file")
    return {r: np.flatnonzero(np.isin(files, list(groups[r])) & available) for r in ROLES}


def choose_threshold(y, probability):
    # Train/val only. Include all-positive and all-negative decisions.
    candidates = np.unique(np.r_[0.0, probability, np.nextafter(1.0, 2.0), 0.5])
    return float(min(candidates, key=lambda t: (-f1_score(y, probability >= t, zero_division=0), abs(t-.5), t)))


def logistic_probe(x, y, indices, select_threshold=False):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y)
    if x.ndim != 2 or y.shape != (len(x),) or not np.isfinite(x).all() or not np.isin(y,[0,1]).all():
        raise ValueError("Invalid probe data")
    if set(indices) != set(ROLES):
        raise ValueError("Wrong probe roles")
    sets = [set(map(int, indices[r])) for r in ROLES]
    if any(len(s)!=len(indices[r]) for s,r in zip(sets,ROLES)) or any(min(s,default=0)<0 or max(s,default=0)>=len(x) for s in sets):
        raise ValueError("Invalid probe row index")
    if any(sets[i] & sets[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError("Probe leakage")
    tr, va, te = (np.asarray(indices[r], dtype=int) for r in ROLES)
    counts = {r: dict(n=len(indices[r]), positive=int(y[indices[r]].sum())) for r in ROLES}
    for role, idx in (("inner_train",tr),("inner_val",va)):
        if len(idx)==0 or len(np.unique(y[idx]))<2:
            return dict(status="not_estimable_"+role+"_single_or_empty", counts=counts)
    if len(te)==0:
        return dict(status="not_estimable_outer_test_empty", counts=counts)
    scaler = StandardScaler().fit(x[tr])
    train, val = scaler.transform(x[tr]), scaler.transform(x[va])
    candidates=[]
    for c in C_GRID:
        model = LogisticRegression(C=c, penalty="l2", solver="liblinear", tol=1e-4,
            max_iter=1000, random_state=1)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            model.fit(train, y[tr])
        if any(issubclass(w.category, ConvergenceWarning) for w in caught):
            raise RuntimeError("Probe did not converge; no automatic solver/parameter change")
        prob = model.predict_proba(val)[:,1]
        auc = float(roc_auc_score(y[va],prob))
        candidates.append((auc,c,model,prob,int(model.n_iter_.max())))
    best = min(candidates, key=lambda t: (-t[0],t[1]))
    threshold = choose_threshold(y[va],best[3]) if select_threshold else .5
    probability = best[2].predict_proba(scaler.transform(x[te]))[:,1]
    pred = (probability >= threshold).astype(int)
    two = len(np.unique(y[te]))==2
    return dict(status="ok" if two else "outer_test_single_class_auc_undefined",
        counts=counts, selected_C=best[1], inner_val_auc=best[0], threshold=threshold,
        candidates=[dict(C=c,inner_val_auc=a,iterations=n) for a,c,_,_,n in candidates],
        auc=float(roc_auc_score(y[te],probability)) if two else None,
        balanced_accuracy=float(balanced_accuracy_score(y[te],pred)) if two else None,
        buggy_f1=float(f1_score(y[te],pred,zero_division=0)),
        probabilities=probability.tolist(), predictions=pred.tolist(),
        scaler_fit_role="inner_train", model_fit_role="inner_train", selection_role="inner_val",
        outer_used_in_selection=False)
