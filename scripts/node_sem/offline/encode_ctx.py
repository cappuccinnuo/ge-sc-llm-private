"""NS-P3b CTX encoder: independent entry preserving all sealed M1 producer SHAs.

Encoding primitives come from unchanged encode.py. Model construction follows
its run() configuration exactly; no HGT, target or graph imports are made.
"""
import argparse
from collections import OrderedDict, Counter
import hashlib
import json
import os
from pathlib import Path
import site
import sys
import time

from encode import gpu_lock, encode_unique, cache_key, GPU_LOCK, DEFAULT_ASSETS, MODALITY_VERSION
from asset_registry import checked, load_model_entry, read, reference, write
from ctx_budget import truncate, VERSION as BUDGET_VERSION

VERSION="nodesem-ctx-encoder-v1"


def load_fields(path):
    path=Path(path).resolve()
    manifest_path=path.with_suffix(".manifest.json")
    manifest=read(manifest_path)
    if read(manifest_path.with_suffix(".seal.json"))["manifest"]!=reference(manifest_path):
        raise ValueError("CTX manifest seal differs")
    if manifest["version"]!="nodesem-ctx-fields-v1" or checked(manifest["input_text"])!=path:
        raise ValueError("Unexpected CTX input")
    if manifest["view"] not in ("original","anonymous") or manifest["names"] not in ("original","masked"):
        raise ValueError("Unknown view/name policy")
    for value in manifest["implementation"].values():checked(value)
    for value in manifest["sources"].values():checked(value)
    rows=[json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    if rows!=manifest["rows"] or not rows:raise ValueError("CTX row order or content differs")
    seen=set()
    for row in rows:
        key=(type(row["row_key"]).__name__,row["row_key"])
        if key in seen:raise ValueError("Duplicate CTX row identity")
        seen.add(key)
        digest=hashlib.sha256(json.dumps(row["fields"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if row["fields_sha256"]!=digest:raise ValueError("CTX fields digest differs")
        if len(set(row["field_order"]))!=len(row["field_order"]) or set(row["field_order"])!=set(row["fields"]):
            raise ValueError("CTX field order incomplete")
        if row["source_sha256"]!=manifest["sources"][row["file"]]["sha256"]:raise ValueError("CTX source differs")
    return rows,manifest,reference(manifest_path)


def run(path,out,model_name="codet5p-110m-embedding",assets_path=DEFAULT_ASSETS,
        device="cuda",batch_size=32,limit=256,lock_path=GPU_LOCK):
    if site.ENABLE_USER_SITE:raise RuntimeError("Run python -s for environment isolation")
    if batch_size<=0 or limit!=256:raise ValueError("CTX requires positive batch size and frozen 256 token budget")
    import numpy as np
    started=time.monotonic()
    output=Path(out).resolve()
    if output.exists():raise FileExistsError(str(output))
    rows,manifest,text_ref=load_fields(path)
    entry=load_model_entry(assets_path,model_name)
    if model_name!="codet5p-110m-embedding":raise ValueError("NS-P3b uses the same primary M1 model only")
    implementations=dict(manifest["implementation"])
    for name in ("encode.py","encode_ctx.py","ctx_budget.py","asset_registry.py"):
        implementations["offline/"+name]=reference(Path(__file__).with_name(name))
    output.mkdir(parents=True,exist_ok=False)
    write(output/"started.json",dict(version=VERSION,input_manifest=text_ref,device=device,
        model=model_name,batch_size=batch_size,implementation=implementations))
    try:
        with gpu_lock(lock_path,device):
            cache=output/"hf_cache"
            os.environ["HF_HOME"]=str(cache)
            os.environ["HF_MODULES_CACHE"]=str(cache/"modules")
            import torch
            import transformers
            if device!="cpu" and not torch.cuda.is_available():raise RuntimeError("CUDA unavailable; no CPU fallback")
            torch.manual_seed(1)
            torch.set_num_threads(2)
            torch.use_deterministic_algorithms(True)
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
            torch.backends.cudnn.benchmark=False
            dtype=torch.float16 if device!="cpu" else torch.float32
            entry=load_model_entry(assets_path,model_name)
            tokenizer=transformers.AutoTokenizer.from_pretrained(entry["directory"],
                local_files_only=True,trust_remote_code=True,cache_dir=str(cache),use_fast=True)
            model=transformers.AutoModel.from_pretrained(entry["directory"],
                local_files_only=True,trust_remote_code=True,cache_dir=str(cache),
                torch_dtype=dtype,attn_implementation="eager",weights_only=True).to(device)
            model.eval()
            model.requires_grad_(False)
            unique,lookup,indices,budgets=[],{},[],[]
            budget_cache={}
            for row in rows:
                key=row["fields_sha256"]
                if key not in budget_cache:
                    fields=OrderedDict((k,row["fields"][k]) for k in row["field_order"])
                    budget_cache[key]=truncate(fields,tokenizer,limit)
                text,budget=budget_cache[key]
                key=cache_key(text,entry["asset_sha256"],limit,entry["pooling"])+BUDGET_VERSION
                if key not in lookup:
                    lookup[key]=len(unique);unique.append(text)
                indices.append(lookup[key])
                budgets.append(dict(row_key=row["row_key"],text=text,
                    text_sha256=hashlib.sha256(text.encode()).hexdigest(),**budget))
            first,diag=encode_unique(unique,tokenizer,model,device,limit,entry["pooling"],batch_size,entry["dimension"])
            second,again=encode_unique(unique,tokenizer,model,device,limit,entry["pooling"],batch_size,entry["dimension"])
            error=float(np.max(np.abs(first-second))) if first.size else 0.0
            if diag!=again or error>1e-6:raise ValueError("CTX repeated inference differs above 1e-6")
            if diag["truncated_unique"]!=0:raise ValueError("CTX exceeded budget before model tokenizer")
            values=first[indices].copy()
            identities=[]
            for row,value in zip(rows,values):
                item={k:row[k] for k in ("row_key","file","node_type","source_sha256","code_sha256")}
                item.update(vector_sha256=hashlib.sha256(value.tobytes()).hexdigest(),present=True)
                identities.append(item)
            suffix="_masked" if manifest["names"]=="masked" else ""
            data=output/("emb_ctx"+suffix+"_"+model_name+".npz")
            with data.open("xb") as stream:np.savez_compressed(stream,features=values)
            with (output/"encoded_text.jsonl").open("x",encoding="utf8") as stream:
                for item in budgets:stream.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
            assets=dict(entry["files"])
            assets["registry"]=reference(assets_path)
            assets["registry_seal"]=reference(Path(assets_path).with_suffix(".seal.json"))
            for value in implementations.values():checked(value)
            if reference(text_ref["path"])!=text_ref:raise ValueError("CTX input changed during encoding")
            checked(manifest["input_text"])
            result=dict(version=MODALITY_VERSION,modality="ctx",view=manifest["view"],
                names=manifest["names"],task_id=manifest["task_id"],feature_dtype="float32",
                feature_shape=list(values.shape),data=reference(data),rows=identities,
                profiles=manifest["profiles"],sources=manifest["sources"],input_text=manifest["input_text"],
                text_manifest=text_ref,implementation=implementations,assets=assets,
                encoded_text=reference(output/"encoded_text.jsonl"),
                encoding=dict(version=VERSION,model=model_name,revision=entry["revision"],
                    model_sha256=entry["asset_sha256"],pooling=entry["pooling"],normalized=entry["normalized"],
                    max_length=limit,budget_version=BUDGET_VERSION,inference_dtype=str(dtype),
                    output_dtype="float32",device=device,torch_version=torch.__version__,
                    transformers_version=transformers.__version__,python_version=sys.version,
                    rows=len(rows),unique_texts=len(unique),cache_hits=len(rows)-len(unique),
                    deduplication_rate=1-len(unique)/len(rows),repeat_passes=2,
                    repeat_bitwise=bool(np.array_equal(first.view(np.uint32),second.view(np.uint32))),
                    repeat_max_abs_error=error,diagnostics=diag,
                    stages=dict(Counter(x["stage"] for x in budgets)),
                    fallback_rows=sum(x["stage"]==8 for x in budgets),
                    local_files_only=True,frozen=True,optimizer_steps=0,
                    gpu_lock=str(lock_path) if device!="cpu" else None,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated() if device!="cpu" else None,
                    elapsed_seconds=time.monotonic()-started))
            write(output/"manifest.json",result)
            write(output/"manifest.seal.json",dict(manifest=reference(output/"manifest.json")))
            return result
    except Exception as exc:
        write(output/"failure.json",dict(error_type=type(exc).__name__,message=str(exc),
            automatic_retry=False,elapsed_seconds=time.monotonic()-started))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields",required=True)
    parser.add_argument("--out",required=True)
    parser.add_argument("--model",default="codet5p-110m-embedding")
    parser.add_argument("--assets",default=str(DEFAULT_ASSETS))
    parser.add_argument("--device",choices=("cuda","cpu"),default="cuda")
    parser.add_argument("--batch-size",type=int,default=32)
    args=parser.parse_args()
    result=run(args.fields,args.out,args.model,args.assets,args.device,args.batch_size)
    print(json.dumps(dict(task=result["task_id"],names=result["names"],shape=result["feature_shape"],
        repeat_bitwise=result["encoding"]["repeat_bitwise"],
        stages=result["encoding"]["stages"],elapsed=result["encoding"]["elapsed_seconds"]),indent=2))


if __name__=="__main__":main()
