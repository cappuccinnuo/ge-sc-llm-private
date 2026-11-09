"""NS-P8b SHA-checked modality I/O, with no label or prediction access."""
import copy
import time
from pathlib import Path
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked,read,ref,write
from scripts.DFG.experiments.common import digest
from .carrier import _load,vector_sha
from .teacher_diagnostics import align_teacher
from .student import fit_student,student_seed,permute,VERSION,POLICY

BASE=Path(__file__).resolve().parent
SOURCES=("student.py","student_artifacts.py","carrier.py","teacher_diagnostics.py")

def inputs(spec,teacher_ref):
    refs={m["name"]:m["manifest"] for m in spec["modalities"]}
    ctx,x=_load(refs["ctx"]);static,b=_load(refs["static"]);teacher,t=_load(teacher_ref)
    for m in (static,teacher):
        if m["task_id"]!=ctx["task_id"] or m["sources"]!=ctx["sources"] or m["view"]!="original":
            raise ValueError("Student source identity mismatch")
    rows=ctx["rows"]
    b,bp=align_teacher(rows,static,b);t,tp=align_teacher(rows,teacher,t)
    if not all(r["present"] for r in rows) or not bp.all():
        raise ValueError("Student requires the frozen complete CTX/STATIC inputs")
    return ctx,x,b,t,tp,dict(ctx=refs["ctx"],static=refs["static"],teacher=teacher_ref)

def manifest(out,ctx,values,source_refs,training_ref,fold,permutation=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    with (out/"student.npz").open("xb") as f:np.savez_compressed(f,features=values)
    rows=[]
    for r,v in zip(ctx["rows"],values):
        row={k:r[k] for k in ("row_key","file","node_type","code_sha256","source_sha256")}
        row.update(present=True,vector_sha256=vector_sha(v));rows.append(row)
    meta=dict(version="nodesem-modality-v1",modality="student",view="original",
        task_id=ctx["task_id"],fold=fold,feature_dtype="float32",feature_shape=list(values.shape),
        data=ref(out/"student.npz"),rows=rows,sources=ctx["sources"],profiles=ctx["profiles"],
        input_text=ctx["input_text"],assets=source_refs,
        implementation={n:ref(BASE/n) for n in SOURCES},student_training=training_ref,
        encoding=dict(version=VERSION,dimension=384,normalized=False,
            presence="all nodes, including auxiliary and teacher-missing nodes",
            teacher_presence_not_copied=True,permutation=permutation))
    write(out/"manifest.json",meta);write(out/"manifest.seal.json",dict(manifest=ref(out/"manifest.json")))
    _load(ref(out/"manifest.json"))
    return ref(out/"manifest.json")

def build(out,task,fold,fit_seed,split,data,ridge_ref):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    ctx,x,b,t,present,source_refs=data
    if ctx["task_id"]!=task:raise ValueError("Wrong student task")
    write(out/"started.json",dict(task_id=task,fold=fold,sources=source_refs,split_sha256=digest(split),
        implementation={n:ref(BASE/n) for n in SOURCES},policy=POLICY))
    start=time.monotonic()
    result=fit_student(x,b,t,present,[r["file"] for r in ctx["rows"]],split,student_seed(fit_seed,task,fold))
    with (out/"state.npz").open("xb") as f:np.savez_compressed(f,**result["state"])
    with (out/"scaler.npz").open("xb") as f:np.savez_compressed(f,mean=result["mean"],variance=result["variance"],scale=result["scale"])
    ridge=read(checked(ridge_ref))
    if ridge["task_id"]!=task or ridge["fold"]!=fold or ridge["split_sha256"]!=digest(split):
        raise ValueError("Ridge comparison split differs")
    # The old ridge uses teacher & CTX & STATIC present. Complete CTX/STATIC above
    # makes the student and ridge populations exactly equal, verified by row keys.
    for role,ids in result["indices"].items():
        if ridge["splits"][role]["row_sha256"]!=digest([ctx["rows"][int(i)]["row_key"] for i in ids]):
            raise ValueError("Ridge/student diagnostic population differs")
    diagnostic=dict(result["diagnostics"],task_id=task,fold=fold,split_sha256=digest(split),
        state=ref(out/"state.npz"),scaler=ref(out/"scaler.npz"),source_refs=source_refs,
        ridge_result=ridge_ref,ridge_outer_mean_cosine=ridge["ridge"].get("outer_mean_cosine"),
        same_ridge_population=True,cpu_seconds=time.monotonic()-start,
        cuda_used=False,HGT_fits=0,role_head=False,
        split_rows={role:dict(count=len(ids),sha256=digest([ctx["rows"][int(i)]["row_key"] for i in ids]))
                    for role,ids in result["indices"].items()})
    write(out/"diagnostics.json",diagnostic)
    original=manifest(out/"S5",ctx,result["values"],source_refs,ref(out/"diagnostics.json"),fold)
    shuffled,mapping=permute(result["values"],[r["node_type"] for r in ctx["rows"]],task,fold,fit_seed)
    with (out/"permutation.npy").open("xb") as f:np.save(f,mapping,allow_pickle=False)
    permuted=manifest(out/"S8",ctx,shuffled,source_refs,ref(out/"diagnostics.json"),fold,
        dict(mapping=ref(out/"permutation.npy"),within="task/fold/node_type",fit_seed=fit_seed))
    done=dict(passed=True,task_id=task,fold=fold,S5=original,S8=permuted,
        diagnostics=ref(out/"diagnostics.json"),sources=source_refs,HGT_fits=0)
    write(out/"complete.json",done)
    return done
