"""Count other diagnostic templates before classifier edits; use measured records and selected probes."""
from collections import Counter, defaultdict
from functools import lru_cache
import time
from batch import *
from compile_repair.toolchain.solc import classify_diagnostic, diagnostic_template, parse_diagnostics

start=time.monotonic()
expected=sha(frozen(ROOT/"compile_repair/toolchain/solc.py"))
census=defaultdict(lambda:dict(counts=Counter(),examples={},units=defaultdict(set)))
totals=Counter()


@lru_cache(maxsize=32768)
def other(kind,message):
    # The old source-dependent branches choose between two known non-other labels.
    record=classify_diagnostic({"kind":kind,"message":message})
    return record["template"] if record["category"]=="other" else None


def check_call(call,version,scope,uid,source_ref):
    if not call:return
    totals[scope+"_calls"]+=1
    for d in parse_diagnostics(call["stderr"]):
        if d["kind"]=="Warning":continue
        totals[scope+"_diagnostics"]+=1
        template=other(d["kind"],d["message"] or "")
        if template is not None:
            row=census[template];row["counts"][scope]+=1;row["units"][scope].add(uid)
            row["examples"].setdefault(scope,dict(unit=uid,version=version,record=source_ref,kind=d["kind"]))
            totals[scope+"_other"]+=1


def inspect(record,scope,uid,ref):
    totals[scope+"_records"]+=1
    for attempt in record["attempts"]:
        check_call(attempt.get("solc"),attempt.get("version"),scope,uid,ref)


for item in rows(ART/"cp3_2_v1/unit_attributions.jsonl.gz"):
    ref=item["selected_result"]
    if ref:
        r=json.loads(checked(ref["result_path"],ref["result_sha256"]))
        inspect(r,"cp3",item["unit_id"],ref)
for item in rows(OLD/"sample_receipts.jsonl.gz"):
    path=Path(item["result_path"])
    ref={"path":str(path),"sha256":item["result_sha256"]}
    uid=item["operator"]+"/"+item["unit_id"]
    inspect(json.loads(checked(path,ref["sha256"])),"cp4_environment",uid,ref)
    if item["selected_attempted"]:
        j=Path(item["mutation_path"]).with_name("invocations.jsonl")
        data=checked(j,item["journal_sha256"])
        q=json.loads(data.split(b"\n",1)[0]);assert q["kind"]=="selected_solc"
        check_call(q,q["compiler"]["version"],"cp4_selected",uid,dict(path=str(j),sha256=item["journal_sha256"]))
for row in census.values():
    row["units"]={k:len(v) for k,v in row["units"].items()}
saved("old_other_templates.json",dict(classifier_sha256=expected,counts=totals,
    basis="All diagnostics in effective CP3.2 measured results (including failed attempts before success) and both CP4 observations.",
    templates=dict(sorted(census.items())),elapsed_seconds=round(time.monotonic()-start,3)))
print(len(census),dict(totals))
