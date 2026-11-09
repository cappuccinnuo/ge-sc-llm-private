"""NS-P7c frozen BGE encoding; no graph, labels, HGT, or training imports."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import site
import sys
import time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from asset_registry import checked,load_model_entry,read,reference,write
from encode import gpu_lock,GPU_LOCK,DEFAULT_ASSETS
from scripts.node_sem.teacher_vectors import scatter

VERSION="nodesem-teacher-encoder-v1"


def run(base,device="cuda",batch_size=32):
    if site.ENABLE_USER_SITE:raise RuntimeError("Run python -s")
    if batch_size<=0:raise ValueError("Invalid batch size")
    import numpy as np
    base=Path(base).resolve()
    index=read(checked(read(base/"post/index.seal.json")["index"]))
    tasks={}
    unique=[];seen=set()
    implementation={"teacher_vectors.py":reference(ROOT/"scripts/node_sem/teacher_vectors.py"),
        "offline/teacher_encode.py":reference(__file__),
        "offline/asset_registry.py":reference(Path(__file__).with_name("asset_registry.py")),
        "offline/encode.py":reference(Path(__file__).with_name("encode.py"))}
    for task,ref in index["tasks"].items():
        meta=read(checked(ref))
        if read(Path(ref["path"]).with_name("manifest.seal.json"))["manifest"]!=ref:
            raise ValueError("Teacher input seal differs")
        for value in meta["implementation"].values():checked(value)
        for value in meta["sources"].values():checked(value)
        rows=[json.loads(s) for s in checked(meta["input_text"]).read_text(encoding="utf8").splitlines()]
        for row in rows:
            if row["present"] and row["text"] not in seen:
                seen.add(row["text"]);unique.append(row["text"])
        tasks[task]=(meta,rows,ref)
    entry=load_model_entry(DEFAULT_ASSETS,"bge-small-en-v1.5")
    out=base/"teacher";out.mkdir(exist_ok=False)
    write(out/"started.json",dict(version=VERSION,index=reference(base/"post/index.json"),
        assets=reference(DEFAULT_ASSETS),device=device,batch_size=batch_size,implementation=implementation))
    start=time.monotonic()
    try:
        with gpu_lock(GPU_LOCK,device):
            os.environ["HF_HOME"]=str(out/"hf_cache")
            os.environ["HF_HUB_OFFLINE"]="1";os.environ["TRANSFORMERS_OFFLINE"]="1"
            os.environ["CUBLAS_WORKSPACE_CONFIG"]=":4096:8"
            import torch
            import sentence_transformers
            from sentence_transformers import SentenceTransformer
            if device!="cpu" and not torch.cuda.is_available():raise RuntimeError("CUDA unavailable")
            torch.manual_seed(1);torch.set_num_threads(2)
            torch.use_deterministic_algorithms(True)
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
            torch.backends.cudnn.benchmark=False
            # Use the downloaded sentence-transformers CLS pooling + normalization.
            model=SentenceTransformer(entry["directory"],device=device,local_files_only=True,
                trust_remote_code=False,model_kwargs={"torch_dtype":torch.float32,
                    "attn_implementation":"eager","weights_only":True})
            model.eval();model.requires_grad_(False)
            if model.get_sentence_embedding_dimension()!=384:raise ValueError("BGE dimension differs")
            lengths=[len(model.tokenizer.encode(s,add_special_tokens=True,truncation=False)) for s in unique]
            if lengths and max(lengths)>model.max_seq_length:
                raise ValueError("Teacher text exceeds frozen BGE maximum length")
            args=dict(batch_size=batch_size,show_progress_bar=False,convert_to_numpy=True,normalize_embeddings=True)
            first=model.encode(unique,**args).astype(np.float32) if unique else np.zeros((0,384),dtype=np.float32)
            second=model.encode(unique,**args).astype(np.float32) if unique else first.copy()
            if not np.array_equal(first.view(np.uint32),second.view(np.uint32)):
                raise ValueError("Two teacher encoding passes are not bitwise identical")
            model_max_length=model.max_seq_length
            del model
            manifests={}
            for task,(meta,rows,source_ref) in tasks.items():
                values,identities=scatter(rows,unique,first)
                d=out/task;d.mkdir()
                with (d/"teacher.npz").open("xb") as stream:np.savez_compressed(stream,features=values)
                provenance=dict(meta["implementation"]);provenance.update(implementation)
                for value in provenance.values():checked(value)
                assets=dict(entry["files"]);assets.update(registry=reference(DEFAULT_ASSETS),
                    registry_seal=reference(DEFAULT_ASSETS.with_suffix(".seal.json")))
                result=dict(version="nodesem-modality-v1",modality="teacher",view="original",task_id=task,
                    feature_dtype="float32",feature_shape=list(values.shape),data=reference(d/"teacher.npz"),
                    rows=identities,sources=meta["sources"],profiles=meta["profiles"],
                    input_text=meta["input_text"],text_manifest=source_ref,assets=assets,implementation=provenance,
                    encoding=dict(version=VERSION,model="bge-small-en-v1.5",revision=entry["revision"],
                        model_sha256=entry["asset_sha256"],dimension=384,pooling="downloaded sentence-transformers CLS",
                        normalized=True,device=device,inference_dtype="float32",repeat_passes=2,repeat_bitwise=True,
                        max_length=int(model_max_length),max_observed_tokens=max(lengths,default=0),
                        text_policy="summary_function_only_3B_r26",roles_encoded=False,optimizer_steps=0,
                        torch_version=torch.__version__,sentence_transformers_version=sentence_transformers.__version__,
                        batch_size=batch_size,total_unique_texts=len(unique)))
                write(d/"manifest.json",result);write(d/"manifest.seal.json",dict(manifest=reference(d/"manifest.json")))
                manifests[task]=reference(d/"manifest.json")
            done=dict(version=VERSION,tasks=manifests,unique_texts=len(unique),repeat_bitwise=True,
                rows=sum(len(v[1]) for v in tasks.values()),elapsed_seconds=time.monotonic()-start,
                peak_allocated_bytes=torch.cuda.max_memory_allocated() if device!="cpu" else None,
                peak_reserved_bytes=torch.cuda.max_memory_reserved() if device!="cpu" else None,
                optimizer_steps=0,source=reference(base/"post/index.json"),assets=reference(DEFAULT_ASSETS))
            write(out/"index.json",done);write(out/"index.seal.json",dict(index=reference(out/"index.json")))
            return done
    except Exception as exc:
        write(out/"failure.json",dict(error_type=type(exc).__name__,error=str(exc),automatic_retry=False))
        raise


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",required=True)
    ap.add_argument("--device",choices=("cuda","cpu"),default="cuda");ap.add_argument("--batch-size",type=int,default=32)
    a=ap.parse_args();print(json.dumps(run(a.out,a.device,a.batch_size),indent=2))
