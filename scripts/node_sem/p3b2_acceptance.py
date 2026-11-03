"""NS-P3b2 independent before/after checks; old products are read-only."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import re
import subprocess
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from . import static_profile as sp
from .facts_schema import FUNCTION_KINDS
from .facts_verify import sealed_manifest,read_jsonl
from .p3_prepare import ROOT,load_accepted
from .p3_acceptance import sealed_fields,verify
from .carrier import vector_sha

BASE=ROOT/"scripts/node_sem/artifacts/ns_p3/attempt_b2"
OLD_COMMIT="aa81bcde2dc2d17dc94bbc3f30dc920a2bd2e3db"
MUTABLE=tuple("scripts/node_sem/"+name for name in (
    "static_profile.py","behavior_schema.json","ctx_alignment.py","ctx_fields.py",
    "p3_prepare.py","p3_acceptance.py","tests/test_ctx_static.py"))


def archive_ref(reference, cache):
    """Match frozen producer bytes to the original Git blob, never reseal history."""
    path=Path(reference["path"])
    if ref(path)==reference:
        return
    rel=str(path.relative_to(ROOT))
    if rel not in MUTABLE:
        raise ValueError("Unexpected archived source mismatch: "+rel)
    if rel not in cache:
        content=subprocess.check_output(["git","show",OLD_COMMIT+":"+rel],cwd=ROOT)
        cache[rel]=dict(commit=OLD_COMMIT,sha256=hashlib.sha256(content).hexdigest())
    if cache[rel]["sha256"]!=reference["sha256"]:
        raise ValueError("Archived producer does not match its sealed SHA")


def archive_modality(path, cache):
    manifest=sealed_manifest(path)
    for value in manifest["implementation"].values():archive_ref(value,cache)
    for value in manifest["assets"].values():checked(value)
    for value in manifest["sources"].values():checked(value)
    checked(manifest["input_text"])
    with np.load(str(checked(manifest["data"])),allow_pickle=False) as archive:
        if archive.files!=["features"]:raise ValueError("Unexpected archived NPZ")
        data=archive["features"].copy()
    if data.dtype!=np.float32 or list(data.shape)!=manifest["feature_shape"]:
        raise ValueError("Archived feature shape/dtype changed")
    if any(vector_sha(v)!=r["vector_sha256"] for r,v in zip(manifest["rows"],data)):
        raise ValueError("Archived vector changed")
    return manifest,data


def compare_static(old,new,facts,old_schema,new_schema):
    old_names=sp.column_names(old_schema);new_names=sp.column_names(new_schema)
    added=set(new_names)-set(old_names)
    if added!={"arith.checked_by_helper=true","unknown.checked_call=true"}:
        raise ValueError("Unexpected STATIC columns added/removed")
    if set(old_names)-set(new_names):raise ValueError("Old STATIC column removed")
    fields={field["name"]+"="+v:field for field in new_schema["fields"] for v in field["values"]}
    summary={}; mapping=[]
    for i,name in enumerate(old_names):
        j=new_names.index(name);a,b=old[:,i],new[:,j]
        changed=np.flatnonzero(a!=b)
        field=fields[name]
        for row in changed:
            f=facts[int(row)]["facts"]
            if (field["unknown_policy"]!="keep_true" or not sp.unknown(f,field["unknown"])
                    or a[row]!=0 or b[row]!=1 or name.endswith("=none")):
                raise ValueError("Unapproved STATIC delta: "+name)
        summary[name]=int(len(changed))
        mapping.append(dict(column=name,old=i,new=j,changed_rows=int(len(changed))))
    for name in sorted(added):
        j=new_names.index(name);expected=[]
        for row in facts:
            obj=row["facts"]["checked_call"]
            expected.append(bool(obj) and ((obj["status"]=="unknown") if name.startswith("unknown.")
                else obj["status"]=="supported" and obj["result_condition_check"]))
        if not np.array_equal(new[:,j],np.asarray(expected,dtype=np.float32)):
            raise ValueError("New checked_call column differs from sealed facts")
        summary[name]=int(new[:,j].sum())
        mapping.append(dict(column=name,old=None,new=j,one_rows=summary[name]))
    return dict(columns=mapping,changes=summary,added=sorted(added),
                changed_existing_columns={k:v for k,v in summary.items() if v and k not in added})


def compare_fields(old,new,fact_rows,mode):
    facts={row["row_key"]:row["facts"] for row in fact_rows}
    if len(old)!=len(new):raise ValueError("CTX row population changed")
    changes=[]
    for before,after in zip(old,new):
        for key in set(before)-{"fields","fields_sha256"}:
            if before[key]!=after[key]:raise ValueError("CTX row identity/order changed")
        if before["fields"]==after["fields"]:continue
        f=facts[before["row_key"]];events=[]
        for field in before["fields"]:
            a,b=before["fields"][field],after["fields"][field]
            if len(a)!=len(b):raise ValueError("CTX field cardinality changed")
            for index,(x,y) in enumerate(zip(a,b)):
                if x==y:continue
                valid=False
                if field=="FROM" and x.startswith("unknown:") and y=="entry:"+x[len("unknown:"):]:
                    nearest=sorted(enumerate(f["dfg"]["from"]),key=lambda pair:(
                        pair[1]["offset"] is None,abs(pair[1]["offset"]) if pair[1]["offset"] is not None else 0,pair[0]))
                    source=nearest[index][1]
                    valid=(source["offset"] is None and facts[source["node"]]["node_kind"] in FUNCTION_KINDS)
                elif field in ("DEF","USE") and re.search(r":param:unknown$",x) and y==x[:-len("unknown")]+"entry":
                    name=x[:-len(":param:unknown")]
                    candidates=[v for v in f["dfg"]["defs" if field=="DEF" else "uses"]
                                if v["kind"] in ("parameter","param") and v["from_offset"] is None]
                    valid=bool(candidates) and (mode=="masked" or any(v["var"]==name for v in candidates))
                    valid=valid and any(z["offset"] is None and facts[z["node"]]["node_kind"] in FUNCTION_KINDS
                                        for z in f["dfg"]["from"])
                if not valid:raise ValueError("Unapproved CTX delta: "+repr((field,x,y)))
                events.append(dict(field=field,index=index,before=x,after=y))
        changes.append(dict(row_key=before["row_key"],file=before["file"],changes=events))
    return changes


def compare(base=BASE):
    base=Path(base)
    output=base/"comparison"
    output.mkdir(exist_ok=False)
    old_schema=read(base/"previous_behavior_schema.json");schema=sp.load_schema()
    old_index=read(checked(read(base/"previous_CURRENT.json")["encoding_index"]))["tasks"]
    new_index=read(base/"encoding_index.json")["tasks"]
    archive_sources={};tasks={}
    for task in sorted(new_index):
        facts,_,_,_,_=load_accepted(task)
        old_meta,old=archive_modality(ROOT/"scripts/node_sem/artifacts/ns_p3/static/original"/task/"manifest.json",archive_sources)
        new_meta=sealed_manifest(base/"static/original"/task/"manifest.json")
        with np.load(str(checked(new_meta["data"])),allow_pickle=False) as z:new=z["features"].copy()
        identity=lambda m:[{k:v for k,v in row.items() if k!="vector_sha256"} for row in m["rows"]]
        if identity(old_meta)!=identity(new_meta):raise ValueError("STATIC row identities changed")
        summary=compare_static(old,new,facts,old_schema,schema);summary["names"]={}
        for mode in ("original","masked"):
            suffix="" if mode=="original" else "_masked"
            old_fields=sealed_fields(ROOT/"scripts/node_sem/artifacts/ctx_v1/original"/task/("ctx_fields"+suffix+".manifest.json"))
            for reference in old_fields["implementation"].values():archive_ref(reference,archive_sources)
            new_fields=sealed_fields(base/"fields/original"/task/("ctx_fields"+suffix+".manifest.json"))
            changes=compare_fields(read_jsonl(checked(old_fields["input_text"])),
                                   read_jsonl(checked(new_fields["input_text"])),facts,mode)
            old_ctx,_=archive_modality(checked(old_index[task][mode]),archive_sources)
            new_ctx=sealed_manifest(checked(new_index[task][mode]))
            if identity(old_ctx)!=identity(new_ctx):raise ValueError("CTX vector identities changed")
            for key in ("model","revision","model_sha256","pooling","normalized","inference_dtype",
                        "output_dtype","max_length","budget_version","device","repeat_passes"):
                if old_ctx["encoding"][key]!=new_ctx["encoding"][key]:raise ValueError("Encoder changed: "+key)
            if not new_ctx["encoding"]["repeat_bitwise"] or new_ctx["encoding"]["repeat_max_abs_error"]!=0:
                raise ValueError("CTX repeated inference not bitwise equal")
            before=read_jsonl(checked(old_ctx["encoded_text"]))
            after=read_jsonl(checked(new_ctx["encoded_text"]))
            stage_changes=[dict(row_key=a["row_key"],before=a["stage"],after=b["stage"])
                           for a,b in zip(before,after) if a["stage"]!=b["stage"]]
            if [r["row_key"] for r in before]!=[r["row_key"] for r in after]:
                raise ValueError("Encoded text row identity/order differs")
            write(output/(task+"_"+mode+"_ctx_delta.json"),dict(changes=changes,stage_changes=stage_changes))
            summary["names"][mode]=dict(changed_rows=len(changes),changes_by_field=dict(Counter(
                e["field"] for row in changes for e in row["changes"])),stage_changed_rows=len(stage_changes),
                encoding=new_ctx["encoding"])
        tasks[task]=summary
        print("comparison passed: "+task,flush=True)
    result=dict(passed=True,tasks=tasks,old_dimension=old_schema["dimension"],new_dimension=schema["dimension"],
                archived_sources=archive_sources,old_commit=OLD_COMMIT,inputs_unchanged=True)
    write(output/"summary.json",result);write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",default=str(BASE))
    args=parser.parse_args();base=Path(args.base).resolve()
    compare(base)
    verify(base/"acceptance",base/"encoding_index.json",prepared_root=base,
           snapshot_path=base/"started.json",mutable_paths=MUTABLE)
    print("NS-P3b2 comparison and carrier acceptance passed",flush=True)

if __name__=="__main__":main()
