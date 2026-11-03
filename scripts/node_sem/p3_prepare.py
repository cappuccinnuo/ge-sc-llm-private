"""NS-P3b preparation: accepted facts -> CTX and STATIC, no model training."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from .facts_io import PLAN, STORE, load_context
from .facts_verify import sealed_manifest, read_jsonl, discover_original_text, verify_task
from .ctx_alignment import enrich
from .ctx_fields import ctx_fields, VERSION
from .static_profile import encode, load_schema, column_names
from .carrier import vector_sha, MODALITY_VERSION

ROOT=Path(__file__).resolve().parents[2]
CURRENT=ROOT/"scripts/node_sem/artifacts/facts_v1/CURRENT.json"


def refs():
    return {str(p.relative_to(ROOT)):ref(p) for p in
        [Path(__file__).with_name(name) for name in
         ("p3_prepare.py","ctx_alignment.py","ctx_fields.py","static_profile.py","behavior_schema.json")]}


def load_accepted(task,current_path=CURRENT):
    current=read(current_path)
    verification=read(checked(current["verification_seal"]))
    validation=read(checked(current["validation"]))
    if verification["final_validation"]!=current["validation"] or not validation["passed"]:
        raise ValueError("Accepted facts validation/seal differs")
    if verification["runtime_closure"]!=current["runtime_closure"]:
        raise ValueError("Accepted runtime closure differs")
    checked(current["runtime_closure"])
    manifest_path=checked(current["tasks"][task])
    text_entry=discover_original_text(ROOT/"scripts/node_sem/artifacts/text_v1/original")[task]
    proof=verify_task(manifest_path,text_entry,read(PLAN),read(STORE))
    manifest=sealed_manifest(manifest_path)
    facts=read_jsonl(checked(manifest["facts"]))
    text_manifest=text_entry[1]
    texts=read_jsonl(checked(text_manifest["input_text"]))
    return facts,texts,manifest,text_manifest,dict(current=ref(current_path),
        facts_manifest=ref(manifest_path),text_manifest=ref(text_entry[0]),proof=proof)


def write_jsonl(path,rows):
    with Path(path).open("x",encoding="utf8") as stream:
        for row in rows:stream.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n")


def field_stats(rows):
    fields=sorted({key for row in rows for key in row["fields"]})
    result={}
    for key in fields:
        values=[row["fields"][key] for row in rows if key in row["fields"]]
        count=len(values)
        result[key]=dict(applicable=count,total=len(rows),
            nonempty=sum(value!=["-"] for value in values),
            unknown=sum(any("unknown" in item for item in value) for value in values))
        result[key]["nonempty_rate"]=result[key]["nonempty"]/count
        result[key]["unknown_rate"]=result[key]["unknown"]/count
    return result


def prepare(task,ctx_out,static_out):
    ctx_out,static_out=Path(ctx_out).resolve(),Path(static_out).resolve()
    if ctx_out.exists() or static_out.exists():raise FileExistsError("NS-P3b output exists")
    started=time.monotonic()
    facts,texts,fact_manifest,text_manifest,accepted=load_accepted(task)
    context=load_context(task)
    if context["profiles"]!=text_manifest["profiles"]:raise ValueError("CTX graph profiles differ")
    enriched=enrich(context["graphs"]["F3"],context["source_text"],texts,facts)
    implementation=dict(text_manifest["implementation"])
    implementation.update(fact_manifest["implementation"])
    implementation.update(refs())
    ctx_out.mkdir(parents=True,exist_ok=False)
    static_out.mkdir(parents=True,exist_ok=False)
    write(ctx_out/"started.json",dict(accepted=accepted,implementation=implementation,view="original"))
    outputs={}
    for mode,filename in (("original","ctx_fields"),("masked","ctx_fields_masked")):
        rows=[]
        for f,t in zip(facts,enriched):
            identity={k:t[k] for k in ("row_key","file","node_type","source_sha256","code_sha256")}
            fields=ctx_fields(f,t,mode)
            identity.update(fields=fields,field_order=list(fields),names=mode)
            identity["fields_sha256"]=hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(",",":")).encode()).hexdigest()
            rows.append(identity)
        path=ctx_out/(filename+".jsonl")
        write_jsonl(path,rows)
        manifest=dict(version=VERSION,view="original",task_id=task,names=mode,
            rows=rows,input_text=ref(path),sources=text_manifest["sources"],profiles=text_manifest["profiles"],
            implementation=implementation,accepted=accepted,statistics=field_stats(rows))
        dest=ctx_out/(filename+".manifest.json")
        write(dest,manifest)
        write(dest.with_suffix(".seal.json"),dict(manifest=ref(dest)))
        outputs[mode]=ref(dest)
    schema=load_schema()
    values=np.stack([encode(row,schema) for row in facts]).astype(np.float32)
    data=static_out/"static.npz"
    with data.open("xb") as stream:np.savez_compressed(stream,features=values)
    identities=[]
    for row,value in zip(texts,values):
        identity={k:row[k] for k in ("row_key","file","node_type","source_sha256","code_sha256")}
        identity.update(vector_sha256=vector_sha(value),present=True)
        identities.append(identity)
    manifest=dict(version=MODALITY_VERSION,modality="static",view="original",task_id=task,
        rows=identities,feature_shape=list(values.shape),feature_dtype="float32",data=ref(data),
        sources=text_manifest["sources"],profiles=text_manifest["profiles"],
        implementation=implementation,assets={},input_text=fact_manifest["facts"],accepted=accepted)
    write(static_out/"manifest.json",manifest)
    write(static_out/"manifest.seal.json",dict(manifest=ref(static_out/"manifest.json")))
    for reference in implementation.values():checked(reference)
    checked(accepted["current"])
    stats=dict(task=task,view="original",rows=len(texts),static_dimension=values.shape[1],
        static_one_rates=dict(zip(column_names(schema),values.mean(axis=0,dtype=np.float64).tolist())),
        ctx_manifests=outputs,static_manifest=ref(static_out/"manifest.json"),
        preparation_seconds=time.monotonic()-started,anonymous_inputs_loaded=False,
        optimizer_steps=0,graph_unchanged=True)
    write(ctx_out/"preparation.json",stats)
    return stats


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task",required=True)
    parser.add_argument("--ctx-out",required=True)
    parser.add_argument("--static-out",required=True)
    args=parser.parse_args()
    result=prepare(args.task,args.ctx_out,args.static_out)
    print(json.dumps({k:v for k,v in result.items() if k!="static_one_rates"},indent=2))


if __name__=="__main__":main()
