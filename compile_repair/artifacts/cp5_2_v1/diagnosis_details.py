"""Distinguish broken outgoing relative paths from the stricter chain acceptance condition."""
from collections import Counter, defaultdict
from pathlib import Path
from measure import HERE, emit, frozen, jsonline, load, read_checked_json, save, sha256
from compile_repair.evaluation.report import classify_record, primary_causes

baseline = {(r["unit_id"],"moved"):r for r in frozen("benchmark") if r["operator"]=="missing_relative_file_moved"}
baseline.update({(r["unit_id"],"real"):r for r in frozen("real_full")})
table = HERE/"diagnosis.jsonl"
assert sha256(table)==load(HERE/"diagnosis_summary.json")["table_sha256"]
import json
counts, examples, reasons = Counter(), {}, Counter()
with jsonline("diagnosis_details") as log:
    for row in map(json.loads, table.read_bytes().splitlines()):
        uid,kind = row["unit_id"], row["kind"]
        path = Path(baseline[uid,kind]["result_path"])
        unit = path.parent if path.parent.name==uid else path.parents[1]
        group,reason=row["group"],row["detail"]
        detail=[]
        for trial in row["rounds"]:
            if not trial.get("receipt"):continue
            info_path=unit/trial["receipt"]
            rec=read_checked_json(info_path,trial["receipt_sha256"])
            project=read_checked_json(info_path.with_name("project.json"),trial["project_sha256"])
            seen={(i.get("category"),i.get("importer"),i.get("line"),i.get("path")):i for i in project["issues"]}
            added=[seen[i["category"],i["importer"],i["line"],i["path"]] for i in trial["new_issues"]]
            outgoing=bool(added) and all(i.get("path","").startswith(("./","../")) and
                dict(project["source_units"]).get(i["importer"]) in trial["new_physical_files"] and
                (i["category"]=="missing_relative_file" or (i["category"]=="io_error" and i["reason"]=="import_outside_project"))
                for i in added)
            if group=="d" and trial["rejected_equal_or_worse"] and trial["selected_disappeared"] and outgoing:
                group,reason="a","outgoing_relative_imports_with_outside_project"
            if not trial["accepted"]:
                if added: detail.append(sorted(set(i["category"]+"/"+i["reason"] for i in added)))
                elif rec["reason"]!="unresolved_imports":
                    detail.append([rec["reason"]]+primary_causes(rec,classify_record(rec))["categories"])
        cats=row["final_categories"]
        cats=cats["categories"] if isinstance(cats,dict) else cats
        if group=="d" and not detail:detail=[cats]
        if group=="c":detail=[cats]
        output=dict(unit_id=uid,kind=kind,group=group,chain_eligible=row["group"]=="a",reason=reason,
                    per_unit_details=detail,source_result_sha256=row["result_sha256"],steps_sha256=row["steps_sha256"])
        emit(log,output)
        counts[kind,group]+=1
        examples.setdefault(kind+"/"+group,uid)
        if group in ("c","d"):reasons[kind,group,json.dumps(detail,sort_keys=True)]+=1
save(HERE/"diagnosis_details.json",dict(counts=[[*k,v] for k,v in sorted(counts.items())],
     examples=examples,terminal_categories=[[*k,v] for k,v in sorted(reasons.items())],
     evidence_sha256=sha256(HERE/"diagnosis_details.jsonl"),diagnosis_sha256=sha256(table)))
