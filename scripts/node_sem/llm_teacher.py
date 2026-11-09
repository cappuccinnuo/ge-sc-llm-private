"""NS-P7c no-role teacher text and explicit unverified presence policy."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
from .llm_full import BASE, load, checked, read, reference, write, jsonl
from .llm_post_v2 import align, role_agreement
from .llm_post import BLACKLIST


def present_row(row):
    """Preserve the v2 score/flags; change only the explicitly authorized policy."""
    item = dict(row, flags=list(row["flags"]), old_present=bool(row["present"]))
    blocked = any("blacklist" in x for x in item["flags"])
    kind = item["target_kind"]
    if kind == "function":
        item["present"] = bool(item["intent"]) and not blocked
        item["unverified"] = item["present"]  # Intent has no static prose reference.
    elif kind == "statement":
        valid = bool(item["summary"]) and not blocked and not any(
            f in item["flags"] for f in ("missing", "parse_failed", "skipped_no_body"))
        score = item["faithfulness"]
        item["present"] = valid and (score is None or score >= .5)
        item["unverified"] = item["present"] and score is None
    else:
        item["present"] = False
        item["unverified"] = False
    return item


def teacher_text(row):
    if not row["present"]:
        return ""
    if row["target_kind"] == "function":
        return "function: " + row["intent"]
    return "{}. function: {}".format(row["summary"], row["intent"])


def quality(rows, facts):
    statement = [r for r in rows if r["target_kind"] == "statement"]
    scores = [r["faithfulness"] for r in statement if r["faithfulness"] is not None]
    return dict(rows=len(rows), statement_nodes=len(statement),
        present=sum(r["present"] for r in rows), old_present=sum(r["old_present"] for r in rows),
        statement_present=sum(r["present"] for r in statement),
        unverified_statements=sum(r["unverified"] for r in statement),
        unverified_fraction=sum(r["unverified"] for r in statement)/len(statement) if statement else None,
        unverified_function_intents=sum(r["unverified"] for r in rows if r["target_kind"]=="function"),
        verifiable=len(scores), faithfulness_median=statistics.median(scores) if scores else None,
        faithfulness_distribution=dict(
            minimum=min(scores) if scores else None, maximum=max(scores) if scores else None,
            mean=statistics.mean(scores) if scores else None,
            counts={str(value):scores.count(value) for value in sorted(set(scores))}),
        unverified_fraction_of_present_statements=(
            sum(r["unverified"] for r in statement)/sum(r["present"] for r in statement)
            if any(r["present"] for r in statement) else None),
        verifiable_ge_half_fraction=sum(s>=.5 for s in scores)/len(scores) if scores else None,
        blacklist_nodes=sum(any("blacklist" in f for f in r["flags"]) for r in statement),
        blacklist_fraction=sum(any("blacklist" in f for f in r["flags"]) for r in statement)/len(statement) if statement else None,
        flags=dict(Counter(f for r in rows for f in r["flags"])),
        roles=role_agreement(statement,facts))


def run(base=BASE):
    base=Path(base);plan=load(base)
    completed=read(checked(read(base/"run1/completed.seal.json")["completed"]))
    if completed["plan"]!=reference(base/"plan.json"):
        raise ValueError("Full completion binding differs")
    manifest=read(checked(plan["input_manifest"]))
    units={u["cache_key"]:u for u in jsonl(manifest["units"])}
    results={r["cache_key"]:r for r in completed["results"]}
    if len(results)!=len(completed["results"]) or set(results)!=set(units):
        raise ValueError("Missing/duplicate full response")
    out=base/"post";out.mkdir(exist_ok=False)
    tasks={}
    for task,row_ref in manifest["tasks"].items():
        rows=jsonl(row_ref)
        source=manifest["inputs"][task]
        fm=read(checked(source["facts_manifest"]))
        facts={r["row_key"]:r["facts"] for r in jsonl(fm["facts"])}
        text_manifest=read(checked(source["text_manifest"]))
        groups=defaultdict(list)
        for row in rows:groups[row.get("cache_key")].append(row)
        output={}
        for key,group in groups.items():
            if key is None:
                answer,_=align(group,facts,dict(target_lines=[]),dict(parsed=None))
            else:
                receipt=results[key]
                if receipt["status"]=="skipped_no_body":
                    response=dict(parsed=None)
                else:
                    response=read(checked(receipt["response"]))
                answer,_=align(group,facts,units[key],response)
                if receipt["status"]=="skipped_no_body":
                    for item in answer:item["flags"]=["skipped_no_body"]
            for item in answer:
                item=present_row(item)
                item["text"]=teacher_text(item)
                item["text_sha256"]=hashlib.sha256(item["text"].encode("utf8")).hexdigest()
                if item["present"] and BLACKLIST.search(item["text"]):
                    raise AssertionError("Teacher blacklist escaped presence policy")
                if item["row_key"] in output:raise ValueError("Duplicate post row")
                output[item["row_key"]]=item
        if set(output)!=set(facts):raise ValueError("Teacher/facts row population differs")
        ordered=[output[r["row_key"]] for r in rows]
        # Input rows originate in frozen F3 text order; establish all identities explicitly.
        expected=text_manifest["rows"]
        if len(expected)!=len(ordered):raise ValueError("F3 row count differs")
        for r,e in zip(ordered,expected):
            if any(r[k]!=e[k] for k in ("row_key","file","node_type","code_sha256","source_sha256")):
                raise ValueError("F3 row identity/order differs")
        d=out/task;d.mkdir()
        with (d/"teacher_text.jsonl").open("x",encoding="utf8") as stream:
            for r in ordered:stream.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+"\n")
        cohorts={}
        for solidifi in (False,True):
            chosen=[r for r in ordered if Path(r["file"]).name.startswith("buggy_")==solidifi]
            unit_keys={r.get("cache_key") for r in chosen if r.get("cache_key")}
            statuses=Counter(results[k]["status"] for k in unit_keys)
            called=sum(v for k,v in statuses.items() if k!="skipped_no_body")
            cohorts["solidifi" if solidifi else "non_solidifi"]=dict(
                quality(chosen,facts), unique_unit_statuses=dict(statuses),
                parse_success_fraction=statuses["ok"]/called if called else None)
        meta=dict(version="nodesem-teacher-text-v1",task_id=task,view="original",
            text_policy="summary_function_only_3B_r26", input_text=reference(d/"teacher_text.jsonl"),
            text_manifest=source["text_manifest"],facts_manifest=source["facts_manifest"],
            profiles=text_manifest["profiles"],sources=text_manifest["sources"],
            plan=reference(base/"plan.json"),completed=reference(base/"run1/completed.json"),
            implementation={n:reference(Path(__file__).parent/n) for n in
                ("llm_teacher.py","llm_post_v2.py","llm_post.py","llm_role_review.py")},
            quality=quality(ordered,facts),cohorts=cohorts)
        write(d/"manifest.json",meta);write(d/"manifest.seal.json",dict(manifest=reference(d/"manifest.json")))
        tasks[task]=reference(d/"manifest.json")
    summary=dict(version="nodesem-teacher-text-index-v1",tasks=tasks,
        generated_statuses=dict(Counter(r["status"] for r in results.values())),
        unique_prompts=len(results),prior_pilots_passed=False,full_run_authorized_by_user=True,
        judge_generated=False,teacher_roles_removed=True,student_training=False,HGT_training=False)
    write(out/"index.json",summary)
    write(out/"index.seal.json",dict(index=reference(out/"index.json")))
    return summary


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(BASE))
    print(json.dumps(run(ap.parse_args().out),indent=2))
