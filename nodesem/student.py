"""Per-fold student: predicts the teacher vector from CTX + STATIC (S5), so deployment needs
no LLM. Trained with 1-cosine loss on teacher-present inner_train rows, early-stopped on
inner_val; outer-test teachers are never read. S8 permutes student vectors within node types."""
import copy
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from dfg.train.init import parameter_seed

VERSION = "nodesem-student-v1"
ROLES = ("inner_train", "inner_val", "outer_test")
POLICY = dict(hidden=512, output=384, dropout=.1, lr=.001, weight_decay=.0001,
              batch_size=1024, max_epochs=30, patience=5, loss="1-cosine",
              selection="strict minimum inner_val mean cosine loss",
              scaler="population mean/variance on teacher-present inner_train only")

def student_seed(fit_seed, task, fold):
    return parameter_seed(fit_seed, "student", [task, fold])

def split_indices(files, split, present):
    files = np.asarray(files)
    present = np.asarray(present)
    if present.dtype != np.bool_ or present.shape != files.shape:
        raise ValueError("Invalid teacher presence")
    sets = [set(split[r + "_files"]) for r in ROLES]
    if any(len(s) != len(split[r + "_files"]) for s, r in zip(sets, ROLES)):
        raise ValueError("Duplicate split file")
    if any(sets[i] & sets[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError("File split leakage")
    if set(files) != set.union(*sets):
        raise ValueError("Split must cover exactly all input files")
    return {r:np.flatnonzero(np.isin(files, list(s)) & present) for r,s in zip(ROLES,sets)}

def validate_selection(files, split, present, indices):
    expected = split_indices(files, split, present)
    if set(indices) != set(ROLES):
        raise ValueError("Wrong role keys")
    for role in ROLES:
        if not np.array_equal(indices[role], expected[role]):
            raise ValueError("Split leakage or changed teacher population: " + role)
    if not len(expected["inner_train"]) or not len(expected["inner_val"]):
        raise ValueError("Empty student training/early-stopping population")
    return expected

class Student(nn.Module):
    def __init__(self, input_dim, output_dim=384):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(input_dim,512), nn.GELU(),
                                 nn.Dropout(.1), nn.Linear(512,output_dim))
    def forward(self,x):
        return self.net(x)

def _finite(a, n, name):
    if a.dtype != np.float32 or a.ndim != 2 or len(a) != n or not np.isfinite(a).all():
        raise ValueError("Invalid " + name)

def fit_student(ctx, static, teacher, present, files, split, seed, max_epochs=30,
                indices=None):
    """Fit train/val only; inspect outer teacher only after best selection/export."""
    n = len(files)
    for name, a in (("ctx",ctx),("static",static),("teacher",teacher)):
        _finite(a,n,name)
    if teacher.shape[1] != 384 or not (1 <= max_epochs <= 30):
        raise ValueError("Wrong output or epoch limit")
    ix = split_indices(files,split,present) if indices is None else indices
    validate_selection(files,split,present,ix)
    train, val = ix["inner_train"], ix["inner_val"]
    if np.any(np.linalg.norm(teacher[np.concatenate((train,val))],axis=1) == 0):
        raise ValueError("Present teacher has zero norm")
    mean = ctx[train].astype(np.float64).mean(0)
    variance = ctx[train].astype(np.float64).var(0)
    scale = np.sqrt(variance)
    scale[scale == 0] = 1.
    x = torch.from_numpy(np.concatenate((((ctx-mean)/scale).astype(np.float32),static),axis=1))
    y = torch.from_numpy(teacher)
    if not bool(torch.isfinite(x).all()):
        raise ValueError("Nonfinite standardized student input")
    # Restore caller RNG and never initialize CUDA.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = Student(x.shape[1])
        opt = torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.0001)
        gen = torch.Generator(device="cpu"); gen.manual_seed(seed)
        best_loss = math.inf; best_state = None; stale = 0; history=[]; steps=0
        def evaluate(ids):
            model.eval()
            with torch.no_grad():
                return float(torch.cat([1-F.cosine_similarity(model(x[ids[i:i+1024]]),
                    y[ids[i:i+1024]],dim=1) for i in range(0,len(ids),1024)]).mean())
        for epoch in range(1,max_epochs+1):
            model.train(); total=0.
            order = train[torch.randperm(len(train),generator=gen).numpy()]
            for i in range(0,len(order),1024):
                idx=order[i:i+1024]; opt.zero_grad()
                loss=(1-F.cosine_similarity(model(x[idx]),y[idx],dim=1)).mean()
                if not bool(torch.isfinite(loss)): raise ValueError("Nonfinite student loss")
                loss.backward()
                if any(p.grad is not None and not bool(torch.isfinite(p.grad).all()) for p in model.parameters()):
                    raise ValueError("Nonfinite student gradient")
                opt.step(); steps+=1; total+=float(loss.detach())*len(idx)
            vl=evaluate(val)
            if not math.isfinite(vl): raise ValueError("Nonfinite student validation loss")
            improved=vl<best_loss
            if improved:
                best_loss=vl; best_state=copy.deepcopy(model.state_dict()); best_epoch=epoch; stale=0
            else: stale+=1
            history.append(dict(epoch=epoch,train_loss=total/len(train),inner_val_loss=vl,selected=improved))
            if stale>=5: break
        model.load_state_dict(best_state,strict=True); model.eval()
        validate_selection(files,split,present,ix)
        with torch.no_grad():
            values=torch.cat([model(x[i:i+1024]) for i in range(0,n,1024)]).numpy().copy()
        _finite(values,n,"student export")
        if np.any(np.linalg.norm(values,axis=1)==0): raise ValueError("Zero student output")
        outer=ix["outer_test"]
        outer_cos=float(F.cosine_similarity(torch.from_numpy(values[outer]),y[outer],dim=1).mean()) if len(outer) else None
        return dict(values=values,state={k:v.detach().cpu().numpy().copy() for k,v in best_state.items()},
            mean=mean,variance=variance,scale=scale,indices=ix,
            diagnostics=dict(seed=seed,counts={r:len(ix[r]) for r in ROLES},epochs=len(history),
                best_epoch=best_epoch,early_stopped=len(history)<max_epochs,optimizer_steps=steps,
                inner_val_mean_cosine=1-best_loss,outer_test_mean_cosine=outer_cos,
                outer_teacher_used_for_selection=False,all_nodes_exported=n,
                teacher_missing_exported=int((~present).sum()),history=history,policy=POLICY))

def permute(values, node_types, task, fold, fit_seed):
    """One immutable matrix per task/fold; no cross-type or cross-task movement."""
    if values.ndim!=2 or len(values)!=len(node_types): raise ValueError("Wrong permutation rows")
    types=np.asarray(node_types); mapping=np.arange(len(values))
    for kind in sorted(set(node_types)):
        idx=np.flatnonzero(types==kind)
        seed=parameter_seed(fit_seed,"student_permutation",[task,fold,kind])
        gen=torch.Generator(device="cpu");gen.manual_seed(seed)
        mapping[idx]=idx[torch.randperm(len(idx),generator=gen).numpy()]
    if sorted(mapping.tolist())!=list(range(len(values))) or np.any(types!=types[mapping]):
        raise AssertionError("Permutation crossed node types")
    return values[mapping].copy(),mapping

def s8_gate(fold_mean_bf1_delta):
    if isinstance(fold_mean_bf1_delta,bool) or not isinstance(fold_mean_bf1_delta,(int,float)) or not math.isfinite(fold_mean_bf1_delta):
        raise ValueError("Finite preregistered reentrancy_node best delta required")
    return fold_mean_bf1_delta > 0
