"""Independently recompute CP2.2 from saved extractions; never compile or sample."""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
ART=OUT.parent
sys.path.insert(0,str(ROOT))
from compile_repair.evaluation.survey import checked_json,SIX_C,REPORT_SHA,SEAL_SHA


def read(p):
    return json.loads(p.read_text(encoding="utf8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def counter(extraction,target,digest):
    result=Counter()
    assert extraction["comparability"]["status"]=="comparable"
    for row in extraction["occurrences"]:
        for field in ("function","node","declaration"):
            assert row[field] is None or row[field]["filename"]==target
        fields=[row["layer"],row["function_name"],
            row["function"]["start"] if row["function"] else None,row["modifier"],
            row["context_contract"],row["context_declarer"],row["inherited_context"],
            row["node"]["start"] if row["node"] else None,
            row["declaration"]["start"] if row["declaration"] else None,
            row["canonical_name"],row["fact"],row["tags"]]
        result[json.dumps([digest,fields],sort_keys=True)]+=1
    return result


def load_sample(folder,row,job):
    raw=gzip.decompress((folder/row["extraction"]).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==row["extraction_sha256"]
    return counter(json.loads(raw),job["replay_source"],job["source_sha256"])


def original_decision(expected,samples):
    assert len(samples)==11
    unstable,failed=[],[]
    stable=0
    for key in sorted(set(expected).union(*(set(s) for s in samples))):
        values=[s.get(key,0) for s in samples]
        lo,hi=min(values),max(values)
        ref=expected.get(key,0)
        row=dict(key=key,counts=values,minimum=lo,maximum=hi,reference=ref)
        if lo==hi:
            stable+=1
            if lo!=ref:
                failed.append(dict(row,reason="reference_only" if hi==0 else "stable_mismatch"))
        else:
            f=json.loads(key)[1]
            row.update(layer=f[0],function_name=f[1],inherited_context=f[6],
                       kind=f[10][2],context_contract=f[4],context_declarer=f[5])
            unstable.append(row)
            if not lo<=ref<=hi:
                failed.append(dict(row,reason="outside_observed_range"))
    return dict(passed=not failed,samples=11,stable_keys=stable,unstable_keys=unstable,failing_keys=failed)


def execute():
    new=ART/"cp2_6c_v3"; old=ART/"cp2_6c_v2"
    for folder in (old,new):
        seal=read(folder/"seal.json")
        assert all(sha(folder/p)==h for p,h in seal["files"].items())
    plan=read(old/"plan.json")
    assert plan==read(ART/"cp2_6c_v1/plan.json")==read(new/"plan.json")["original_plan"]
    report=checked_json(SIX_C/"slither_full/report.json",REPORT_SHA)
    assert checked_json(SIX_C/"slither_full/report.seal.json",SEAL_SHA)["report_sha256"]==REPORT_SHA
    refs=[r for _,task in sorted(report["tasks"].items()) for r in task["files"] if r["status"]=="compared"]
    rows=[json.loads(s) for s in (new/"comparison.jsonl").read_text().splitlines()]
    prior=[json.loads(s) for s in (old/"comparison.jsonl").read_text().splitlines()]
    assert len(rows)==239
    unstable,files,pids=[],[],{}
    for index,(row,ref,job) in enumerate(zip(rows,refs,plan["jobs"]),1):
        assert row["index"]==index and row["path"]==job["source"]
        assert row["source_sha256"]==job["source_sha256"]==ref["source_sha256"]
        assert row["version"]==job["version"]==ref["version"]
        if index<=226:
            assert {k:v for k,v in row.items() if k not in ("index","evidence_batch","reused")}==prior[index-1]
        folder=old if index<=227 else new/"continuation"
        expected=counter(ref["slither_extraction"],job["replay_source"],job["source_sha256"])
        actual=load_sample(folder,dict(extraction="extractions/{:04d}.json.gz".format(index),
                                     extraction_sha256=row["extraction_sha256"]),job)
        assert row["equal"]==(expected==actual)
        assert row["only_reference"]==dict(expected-actual) and row["only_replay"]==dict(actual-expected)
        initial=[actual];added=[]
        if row["equal"]:
            assert row["criterion"]=="main_exact" and row["passed"]
        else:
            relative=row["additional_directory"] if index<=227 else row["d20_evidence"]["directory"]
            d20folder=folder/relative
            receipt=read(d20folder/"summary.json")
            assert len(receipt["samples"])==10 and receipt["status"]=="complete"
            if "pid" in receipt: pids["D20/"+str(index)]=receipt["pid"]
            assert [s["sample"] for s in receipt["samples"]]==list(range(1,11))
            initial += [load_sample(d20folder,s,job) for s in receipt["samples"]]
            decision=original_decision(expected,initial)
            assert decision==row["d20"]
            if decision["passed"]:
                assert row["criterion"]=="D20" and row["passed"]
            else:
                assert row["criterion"]=="D20a"
                parent=new if index==227 else folder
                afolder=parent/row["d20a_evidence"]["directory"]
                request=read(afolder/"request.json")
                receipt=read(afolder/"summary.json")
                assert request["job"]==job and request["cwd"]==str(ROOT) and request["maximum_samples"]==100
                targets={r["key"]:r["reference"] for r in decision["failing_keys"]}
                assert request["failing_reference_counts"]==targets
                assert 1<=len(receipt["samples"])<=100
                pids["D20a/"+str(index)]=receipt["pid"]
                seen=set()
                for count,sample in enumerate(receipt["samples"],1):
                    assert sample["sample"]==count
                    observation=load_sample(afolder,sample,job);added.append(observation)
                    assert sample["failing_key_counts"]=={k:observation.get(k,0) for k in targets}
                    seen.update(k for k,v in targets.items() if observation.get(k,0)==v)
                    assert sample["all_targets_observed"]==(seen==set(targets))
                    if count<len(receipt["samples"]):
                        assert seen!=set(targets), "Sampling continued after the earliest passing sample"
                assert seen==set(targets) and row["passed"] and receipt["status"]=="complete"
                assert row["d20a"]["original_d20_unchanged"]==decision
                for target in row["d20a"]["failing_keys"]:
                    vals=[s.get(target["key"],0) for s in added]
                    assert vals==target["added_counts"]
                    assert target["first_match"]==next(i for i,v in enumerate(vals,1) if v==target["reference"])
        keys=set(expected).union(*(set(s) for s in initial+added))
        local=[]
        for key in sorted(keys):
            values=[s.get(key,0) for s in initial];extra=[s.get(key,0) for s in added]
            combined=values+extra; ref_count=expected.get(key,0)
            if min(combined)==max(combined):
                assert combined[0]==ref_count, "Stable key differs"
                continue
            f=json.loads(key)[1]
            line=f[10][0]
            source=Path(job["replay_source"])
            assert sha(source)==job["source_sha256"]
            text=source.read_bytes().decode("utf8").splitlines()[line-1]
            item=dict(index=index,path=job["source"],key=key,source_sha256=job["source_sha256"],
                version=job["version"],reference=ref_count,main_and_d20_counts=values,d20a_counts=extra,
                layer=f[0],kind=f[10][2],variable=f[10][1],line=line,source_line=text,
                function_name=f[1],context_contract=f[4],context_declarer=f[5],inherited_context=f[6],
                first_varied_in="D20a" if min(values)==max(values) else "D20")
            unstable.append(item);local.append(item)
        files.append(dict(index=index,path=job["source"],criterion=row["criterion"],passed=row["passed"],
            main_occurrences=sum(actual.values()),reference_occurrences=sum(expected.values()),
            main_and_d20_occurrences=[sum(s.values()) for s in initial],
            d20a_occurrences=[sum(s.values()) for s in added],unstable_keys=len(local)))
    summary=read(new/"summary.json")
    assert summary["passed"] and summary["main_exact_files"]==sum(r["criterion"]=="main_exact" for r in files)
    for criterion,field in (("D20","d20_passed_files"),("D20a","d20a_passed_files")):
        assert summary[field]==sum(r["criterion"]==criterion for r in files)
    invocations=[]
    for p in sorted(new.rglob("invocations.jsonl")):
        invocations += [json.loads(s) for s in p.read_text().splitlines()]
    calls=[r for r in invocations if r["kind"]=="slither"]
    assert len(calls)==23 and Counter(r["role"] for r in calls)=={"D20a":1,"D20":10,"main_continuation":12}
    assert len({r["pid"] for r in calls if r["role"]=="main_continuation"})==1
    assert len({r["pid"] for r in calls})==3
    result=dict(schema="cp2.2-captured-replay-audit-v1",passed=True,criterion_passed=True,
        observed_files=239,reused_main_files=227,new_extractions=23,extractions_in_this_audit=0,
        main_exact_files=summary["main_exact_files"],d20_passed_files=summary["d20_passed_files"],
        d20a_passed_files=summary["d20a_passed_files"],file_227_additional_samples=summary["file_227_additional_samples"],
        unstable_keys=len(unstable),unique_keys=len({r["key"] for r in unstable}),
        by_layer_kind={l:{k:sum(r["layer"]==l and r["kind"]==k for r in unstable)
            for k in ("DEF","USE","READ","WRITE")} for l in ("L1","L2")},
        inherited=sum(r["inherited_context"] for r in unstable),
        non_inherited=sum(not r["inherited_context"] for r in unstable),
        unstable_facts=unstable,files=files,process_ids=pids,frozen_report_sha256=REPORT_SHA)
    with (OUT/"captured_replay_audit.json").open("x",encoding="utf8") as stream:
        json.dump(result,stream,ensure_ascii=False,sort_keys=True,indent=2);stream.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("unstable_facts","files")},indent=2))


if __name__=="__main__":
    execute()
