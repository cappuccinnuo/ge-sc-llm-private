"""Aggregate sealed rows from CP5.2, preserving the two scoring questions and every denominator."""
from collections import Counter, defaultdict
from pathlib import Path
import json

from measure import HERE, LOCAL, load, save, sha256

RUN=HERE/"continuation"


def records(path, expected=None):
    if expected is not None and sha256(path)!=expected:
        raise ValueError("Sealed rows differ: "+str(path))
    with path.open(encoding="utf8") as log:
        yield from map(json.loads,log)


def pools(scores):
    result = {}
    for scope in ("main","surviving"):
        bucket={}
        for field in ("kept","cfg_edges","calls"):
            facts=[(r if scope=="main" else r["surviving"])[field] for r in scores]
            if field=="kept":
                num=sum(v["equal"] for v in facts)
                den=sum(v["units"] for v in facts)
                bucket[field]=dict(equal=num,units=den,pooled_ratio=num/den if den else 1)
            else:
                matched=sum(v["matched"] for v in facts)
                truth=sum(v["truth"] for v in facts)
                repaired=sum(v["repaired"] for v in facts)
                # The denominator is the multiset union across all measured units.
                den=truth+repaired-matched
                bucket[field]=dict(matched=matched,truth=truth,repaired=repaired,denominator=den,
                                   pooled_ratio=matched/den if den else 1)
        result[scope]=bucket
    for k in ("added","affected_by_damage","affected_by_deletion","lost","removed_by_repair","missing_kept"):
        result[k]=sum(r[k] for r in scores)
    return result


def benchmark():
    hist=load(HERE/"benchmark_scores.json")
    old=list(records(HERE/"benchmark_scores.jsonl",hist["sha256"]))
    assert len(old)==1464
    wrapped=[r for r in old if r["operator"]=="standard_json_input"]
    assert sum(r["score"]["exact"] for r in wrapped)==len(wrapped)==950
    data=load(RUN/"benchmark_rerun.json")
    rows=list(records(RUN/"benchmark_rerun.jsonl",data["sha256"]))
    assert len(rows)==len({(r["unit_id"],r["operator"]) for r in rows})==2664
    groups=defaultdict(list)
    for r in rows:groups[r["operator"]].append(r)
    result={}
    for k,rs in groups.items():
        if k!="missing_relative_file_moved":
            assert all(r["equal"] for r in rs)
        result[k]=dict(units=len(rs),prior_d3=sum(r["prior_status"]=="success" for r in rs),
            current_d3=sum(r["status"]=="success" for r in rs), unchanged_d3_and_graph_sha=sum(r["equal"] for r in rs),
            prior_exact=sum(r["prior_score"]["exact"] for r in rs),current_exact=sum(r["score"]["exact"] for r in rs))
    return dict(historical_scores=hist,regression=result)


def movement():
    info=load(RUN/"v2_summary.json")
    rows=list(records(RUN/"v2_observations.jsonl",info["sha256"]))
    plan=load(RUN/"v2_plan.json")
    assert len(rows)==len(plan["rows"])==400 and [r["plan"] for r in rows]==plan["rows"]
    result={}
    for label,items in [("all",rows)]+[(s,[r for r in rows if r["plan"]["split"]==s]) for s in ("dev","test")]:
        tested=[r for r in items if r["trigger"]["outcome"]=="included"]
        assert all(r["inverse"]["score"]["exact"] for r in tested)
        scores=[r["repair"]["score"] for r in tested]
        passed=[s for s in scores if s["compiled"]]
        result[label]=dict(sampled=len(items),triggers=dict(Counter(r["trigger"]["outcome"] for r in items)),
            inverse_full=len(tested),repaired=len(passed),exact=sum(s["exact"] for s in scores),
            old_neighbourhood_exact=sum(r["old_neighbourhood_score"]["exact"] for r in tested),
            all_triggered_metrics=pools(scores),successful_only_metrics=pools(passed))
    return dict(eligible=plan["eligible"],paired=plan["paired"],sampling_seed=plan["seed"],outcomes=result)


def real():
    rows=[]
    for i in range(4):
        name="real_{:02d}".format(i)
        meta=load(RUN/(name+".json"))
        rows.extend(records(RUN/(name+".jsonl"),meta["sha256"]))
    assert len(rows)==len({r["unit_id"] for r in rows})==9138
    unaffected=[r for r in rows if not r["affected"]]
    assert all(r["equal"] for r in unaffected)
    out={}
    for name,subset in [("all",rows),("unaffected",unaffected),("missing_or_io",[r for r in rows if r["affected"]]),
                        ("missing_relative",[r for r in rows if "missing_relative_file" in r["primary"]]),
                        ("io_error",[r for r in rows if "io_error" in r["primary"]])]:
        out[name]=dict(units=len(subset),old_d3=sum(r["prior_d3"] for r in subset),new_d3=sum(r["d3"] for r in subset),
            improved=sum(r["d3"] and not r["prior_d3"] for r in subset),lost=sum(r["prior_d3"] and not r["d3"] for r in subset),
            d3_and_graph_equal=sum(r["equal"] for r in subset))
    causes={r["unit_id"]:r for r in records(HERE/"diagnosis_details.jsonl")
            if r["kind"]=="real"}
    out["changes"]=[]
    for r in rows:
        if r["equal"]:
            continue
        path=Path(r["result_path"]).with_name("repair_steps.json")
        steps=load(path) if path.exists() else []
        accepted=[s for s in steps if s.get("accepted") and s.get("step")==4]
        original=causes.get(r["unit_id"],{})
        out["changes"].append(dict(unit_id=r["unit_id"],corpus=r["corpus"],split=r["split"],
            prior_d3=r["prior_d3"],d3=r["d3"],old_diagnosis=original.get("group"),
            chain_depths=[s["chain_depth"] for s in accepted],prior_graph_sha256=r["prior_graph_sha256"],
            graph_sha256=r["graph_sha256"],result_sha256=r["result_sha256"],
            steps_sha256=sha256(path) if path.exists() else None))
    return out


def ir():
    result={}
    spotlight=[]
    for name in ("real_dev","benchmark","cp3","mando"):
        if name=="mando":
            meta=load(HERE/"mando/summary.json")
            assert meta["passed"] and meta["counts"]["graphs_equal"]==843
            rows=[dict(unit_id=r["unit_id"], **r["partial_ir"]) for r in records(HERE/"mando/rows.jsonl",meta["rows_sha256"])
                  if r["status"]=="success"]
        else:
            meta=load(RUN/("ir_"+name+".json"))
            rows=list(records(RUN/("ir_"+name+".jsonl"),meta["sha256"]))
        assert len(rows)=={"real_dev":1131,"benchmark":1240,"cp3":1000,"mando":843}[name]
        result[name]=dict(units=len(rows),contract_flagged_units=sum(bool(r["incorrectly_constructed_contracts"]) for r in rows),
            contracts=sum(len(r["incorrectly_constructed_contracts"]) for r in rows),
            distinct_flagged_contract_names=len({c for r in rows for c in r["incorrectly_constructed_contracts"]}),
            both_or_either_units=sum(bool(r["incorrectly_constructed_contracts"] or r["top_level_errors"]) for r in rows),
            top_level_units=sum(bool(r["top_level_errors"]) for r in rows),top_level_messages=sum(r["top_level_errors"] for r in rows))
        if name!="mando":
            result[name].update(raw_graph_facts_equal=sum(r["raw_facts_equal"] for r in rows),
                                fresh_solc=sum(r["fresh_solc"] for r in rows))
            spotlight.extend(dict(scope=name, unit_id=r["unit_id"],contracts=r["incorrectly_constructed_contracts"],
                top_level_errors=r["top_level_errors"],result_sha256=r["result_sha256"]) for r in rows if r["unit_id"]=="cp3_19463")
    assert result["cp3"]["fresh_solc"]==711
    auth=load(RUN/"authorization.json")
    plan={r["unit_id"]:r for r in records(HERE/"ir_argument_differences.jsonl",auth["units_sha256"])}
    physical=LOCAL/"continuation/ir_solc"
    assert set(plan)=={p.name for p in physical.iterdir() if p.is_dir()} and len(plan)==711
    for uid,r in plan.items():
        folder=physical/uid
        claim=load(folder/"claim.json")
        observed=load(folder/"compilation.json")
        assert claim["authorization_sha256"]==sha256(RUN/"authorization.json") and claim["unit_id"]==uid
        assert claim["old_receipt_sha256"]==r["historical_result_sha256"]
        assert claim["command"]==observed["command"]==r["new_solc"] and observed["cwd"]==r["root"]
        assert observed["compiler"]["version"]==r["version"] and observed["returncode"]==0 and not observed["timed_out"]
    return dict(cohorts=result,cp3_19463=spotlight,fresh_solc_claims_and_receipts=len(plan))


if __name__=="__main__":
    save(HERE/"acceptance.json",dict(benchmark=benchmark(),movement=movement(),real=real(),partial_ir=ir(),
         diagnosis=load(HERE/"diagnosis_details.json"),mandov5=load(HERE/"mando/summary.json")["counts"],
         source_audit_sha256=sha256(HERE/"code_audit.json"),cost_usd=0,llm_calls=0))
