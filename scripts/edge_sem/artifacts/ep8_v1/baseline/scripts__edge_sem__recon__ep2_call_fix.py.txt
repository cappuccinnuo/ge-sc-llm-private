"""EP2 section 0: re-evaluate the frozen EP0e candidate set before building edges."""
import argparse
from collections import Counter,defaultdict
from .common import ROOT,read,write,ref,key
from .ep2_common import OUT,TASKS,contexts,file_views,anchor
from .ep0e_calls import serial,census_sites,classify_reference
from scripts.edge_sem.call_resolve import resolve_call
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint

PRIOR=ROOT/"scripts/edge_sem/artifacts/ep0e_v1"


def identity(row):
    return row["file"],tuple(row["call_anchor"])


def run(task):
    old_path=PRIOR/("calls_"+task+".json")
    old=read(old_path)
    context=contexts(task);graph=context["graphs"]["F3"]
    fingerprint=graph_fingerprint(graph)
    previous={identity(r):r for r in old["raw_calls"]}
    current,sites={},[]
    for file,source,sub,sem,raw,inverse in file_views(context):
        resolved={key(n):resolve_call(sem,n) for n in sem.nodes if n.type=="call_expression"}
        for call in (n for n in sem.nodes if n.type=="call_expression"):
            row=dict(file=file,source_sha256=context["sources"][file]["sha256"],
                     owner_anchor=anchor(sem.owner(call)),**serial(sem,call,inverse,resolved[key(call)]))
            current[identity(row)]=row
        for row in census_sites(sem,inverse,resolved):
            sites.append(dict(file=file,source_sha256=context["sources"][file]["sha256"],**row))
    assert set(current)==set(previous)
    stable=[];changed=[]
    for ident,prior in previous.items():
        now=current[ident]
        if prior["status"]=="resolved":
            stable.append(dict(file=ident[0],call_anchor=list(ident[1]),equal=prior==now))
        if prior!=now:
            changed.append(dict(file=ident[0],call_anchor=list(ident[1]),
                source_sha256=now["source_sha256"],
                before={k:v for k,v in prior.items() if k!="expression"},
                after={k:v for k,v in now.items() if k!="expression"}))
    using=[];new_bindings=[]
    for prior in old["using_candidates"]:
        now=current[identity(prior)]
        expected=prior["expected_target"]
        matched=bool(expected is not None and now["status"]=="resolved" and now["target_anchor"]==expected)
        outside=bool(now["status"]=="resolved" and now["kind"]=="library" and
                     (expected is None or now["target_anchor"]!=expected))
        row=dict(file=prior["file"],source_sha256=prior["source_sha256"],call_anchor=prior["call_anchor"],
            candidate=prior["candidate"],expected_target=expected,matched=matched,outside_candidate=outside,
            prior_matched=prior["matched"],status=now["status"],kind=now["kind"],
            target_anchor=now["target_anchor"],reason=now["reason"],
            prior_miss_reason=prior["miss_reason"])
        using.append(row)
        if matched and not prior["matched"]:new_bindings.append(row)
    by_owner=defaultdict(list)
    for row in sites:
        if row["projected"]:by_owner[(row["owner_node"],row["target_node"])].append(row)
    references=[]
    for prior in old["reference_edges"]:
        candidates=[current[(prior["file"],tuple(c["call_anchor"]))] for c in prior["expression_candidates"]]
        supported=prior["reason"]!="function_endpoint_not_projected_in_same_file"
        category,reason=classify_reference(prior["target_anchor"],candidates,supported)
        references.append(dict(file=prior["file"],source_sha256=prior["source_sha256"],
            source_node=prior["source_node"],target_node=prior["target_node"],edge_key=prior["edge_key"],
            prior_class=prior["reference_class"],reference_class=category,reason=reason,
            covered=bool(by_owner[(prior["source_node"],prior["target_node"])])))
    counts=Counter(r["reference_class"] for r in references)
    confirmed=[r for r in references if r["reference_class"]=="internal_confirmed"]
    coverage=sum(r["covered"] for r in confirmed)/len(confirmed)
    unknown=counts["undetermined"]/len(confirmed)
    candidates=[r for r in using if r["candidate"]]
    assert len(candidates)==old["using_summary"]["candidate_calls"]==347
    outside=[r for r in using if r["outside_candidate"]]
    matched=sum(r["matched"] for r in candidates)
    assert graph_fingerprint(graph)==fingerprint
    # These are the pre-building hard conditions; the old 90% recall gate
    # is not reclassified or used to claim prospective confirmation.
    hard=all(r["equal"] for r in stable) and not outside and coverage>=.8 and unknown<=.2
    summary=dict(candidate_calls=len(candidates),prior_matched=312,matched=matched,
        descriptive_recall=matched/len(candidates),additional_bindings=len(new_bindings),
        outside_candidate_calls=len(outside),prior_resolved=len(stable),
        prior_resolved_unchanged=sum(r["equal"] for r in stable),
        reference_classes=dict(counts),projection_coverage=coverage,
        undetermined_to_confirmed=unknown,ep0d_gates_pass=coverage>=.8 and unknown<=.2,
        hard_conditions_pass=hard,historical_ep0e_gate_pass=False,
        prior_unknown_reasons=dict(Counter(r["reason"] for r in previous.values() if r["status"]=="unknown")),
        current_unknown_reasons=dict(Counter(r["reason"] for r in current.values() if r["status"]=="unknown")),
        status_changes=dict(Counter(r["before"]["status"]+"->"+r["after"]["status"] for r in changed)),
        unique_call_site_candidates=len({(r["source_node"],r["target_node"]) for r in sites if r["projected"]}))
    output=dict(task_id=task,prior=ref(old_path),summary=summary,using_candidates=using,
        added_bindings=new_bindings,changes=changed,prior_resolved_comparisons=stable,
        references=references,sites=[{k:v for k,v in r.items() if k!="expression"} for r in sites],
        graph_unchanged=True,source_refs=[ref(__file__),ref(ROOT/"scripts/edge_sem/call_resolve.py")],
        provenance=context["provenance"],training_executed=False,edges_built=0,
        interpretation="Post-result r9 correction; EP0e historical 90% gate remains failed.")
    write(OUT/"call_fix"/(task+".json"),output)
    print(task,summary,flush=True)
    if not hard:raise ValueError("EP2 call-fix hard condition failed; stop before building edges")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--task",choices=TASKS,required=True)
    run(parser.parse_args().task)
