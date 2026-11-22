"""Re-attribute all measured CP3.2 units from their sealed records without invoking solc."""
from collections import Counter
from functools import lru_cache
from batch import *
from compile_repair.evaluation.report import aggregate_attributions, classify_record, primary_causes
from compile_repair.toolchain.solc import classify_diagnostic, parse_diagnostics

prior = ART/"cp3_2_v1"

@lru_cache(maxsize=12000)
def other_template(kind,message):
    item=classify_diagnostic(dict(kind=kind,message=message))
    return item["template"] if item["category"]=="other" else None

def task(unit):
    ref=unit["selected_result"]
    if ref is None:
        if unit["status"]!="unmeasured":raise ValueError(unit["unit_id"])
        return unit,{}
    record=json.loads(checked(ref["result_path"],ref["result_sha256"]))
    if record["status"] != unit["status"]:raise ValueError(unit["unit_id"])
    failures=classify_record(record)
    any_categories=sorted({r["category"] for r in failures})
    primary=primary_causes(record,failures)
    if "version_mismatch" in primary["categories"]:raise ValueError(unit["unit_id"])
    counts=Counter()
    for attempt in record["attempts"]:
        solc=attempt.get("solc")
        if not solc:continue
        for d in parse_diagnostics(solc["stderr"]):
            if d["kind"]!="Warning":
                template=other_template(d["kind"],d["message"])
                if template:counts[template]+=1
    return dict(unit,primary=primary,any_categories=any_categories),dict(counts)

def main():
    frozen(prior/"unit_attributions.jsonl.gz")
    old=json.loads(frozen(prior/"failure_summary.json"))
    routes=json.loads(frozen(prior/"d6_cp4_final.json"))
    totals=Counter();fresh=[]
    def stream():
        for n,(unit,other) in enumerate(ordered_work(task,rows(prior/"unit_attributions.jsonl.gz"),3),1):
            totals.update(other);fresh.append(unit)
            if n%5000==0:print("units",n,flush=True)
            yield unit
    output_rows("cp3_attributions.jsonl.gz",stream())
    if len(fresh)!=31307:raise ValueError("CP3 population changed")
    names={r["category"] for r in routes["categories"]}|{"abi_coder_required","file_level_member","version_mismatch"}
    current=aggregate_attributions(fresh,sorted(names))
    for k in ("total","success","remaining_failures"):
        if old["primary"][k]!=current["primary"][k]:raise ValueError("CP3 denominator changed: "+k)
    for k in ("non_solidity_by_corpus","unmeasured_by_corpus"):
        if old[k]!=current[k]:raise ValueError(k)
    saved("cp3_failure_summary.json",current)
    comparison={}
    for mode in ("primary","any_candidate"):
        def counts(col):return {r["category"]:r for r in col[mode]["category_unit_counts"]}
        left,right=counts(old),counts(current)
        comparison[mode]=[dict(category=c,old=left.get(c,{}).get("units",0),new=right.get(c,{}).get("units",0),
            old_by_corpus=left.get(c,{}).get("by_corpus",{}),new_by_corpus=right.get(c,{}).get("by_corpus",{}))
            for c in sorted(set(left)|set(right),key=lambda c:(-right.get(c,{}).get("units",0),c))]
    old_templates={r:v["counts"].get("cp3",0) for r,v in load("old_other_templates.json")["templates"].items() if v["counts"].get("cp3")}
    comparison["other_templates"]=[dict(template=t,old=old_templates.get(t,0),new=totals[t]) for t in sorted(set(old_templates)|set(totals))]
    comparison["template_denominator"]="Every non-warning diagnostic in all measured CP3.2 attempts, including failures before an accepted version."
    comparison["inputs"]=len(fresh);comparison["measured"]=sum(r["selected_result"] is not None for r in fresh)
    saved("cp3_before_after.json",comparison)
    docs=json.loads(frozen(ART/"cp3_v1/authorization.json"))["docs"]
    selected=[d for d in docs if d["path"].endswith("080-breaking-changes.rst") or d["tag"]=="v0.8.38" and "layout-of-source-files" in d["path"]]
    for d in selected:
        blob=Path(d["destination"]).read_bytes()
        if hashlib.sha1(b"blob "+str(len(blob)).encode()+b"\0"+blob).hexdigest()!=d["git_blob_sha1"]:raise ValueError(d["path"])
    additions={
      "abi_coder_required":dict(route="deterministic_rule",repair="按编译器和已有 pragma 确认可添加适用的 ABI 编码器 v2 指令；显式 v1 冲突另行判断。",change_level="additive",mechanical_checks="仅添加兼容且无冲突的 pragma，再核对编译、D3 和保留节点。",sources=[selected[0]["source_url"]]),
      "file_level_member":dict(route="conditional_rule",repair="只在片段来源能证实所属合约时重建声明作用域；语义归属不足时保留待处理。",change_level="conditional",mechanical_checks="核对片段上下文与声明作用域，保留原有函数体和成员字节，并验证 D3 与节点映射。",sources=[selected[-1]["source_url"]]),
      "version_mismatch":dict(route="environment_observation",repair="记录区间外候选拒绝版本的观测，沿用现有选版流程。",change_level="none",mechanical_checks="保留逐版本和任一候选统计，主因排除该标签。",sources=[selected[-1]["source_url"]])}
    existing={q["category"]:q for q in routes["categories"]}
    for name,data in additions.items():existing[name]=dict(data,category=name,implementation_in_cp3=False,cp4_operator=None,fallback="manual_review_if_ambiguous",
        no_source_corruption_operator_reason="CP4.1 updates these diagnostic routes; no separate source operator is specified.")
    a={r["category"]:r for r in current["primary"]["category_unit_counts"]}
    z={r["category"]:r["units"] for r in current["any_candidate"]["category_unit_counts"]}
    out=[]
    for name,row in existing.items():
        obs=a.get(name,{});out.append(dict(row,observed_units=obs.get("units",0),fraction_remaining_failures=obs.get("fraction_remaining_failures",0),any_candidate_units=z.get(name,0)))
    out.sort(key=lambda x:(-x["observed_units"],x["category"]))
    saved("d6_priority.json",dict(schema="cp4.1-frequency",categories=out,source_documents=selected,
        priority=[x["category"] for x in out],basis="CP3.2 measured eligible failures re-attributed in CP4.1; observation noise counted only in any-candidate.",
        new_repair_rules_implemented=False,old_routes_sha256=sha((prior/"d6_cp4_final.json").read_bytes())))
    print("population",len(fresh),"others",sum(old_templates.values()),sum(totals.values()),flush=True)

if __name__=="__main__":main()
