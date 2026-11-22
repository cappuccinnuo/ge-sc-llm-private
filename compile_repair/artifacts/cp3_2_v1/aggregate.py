"""Reconcile CP3.1 receipts with CP3.2 input-only replacements and additional blocker statistics."""
import argparse
from collections import Counter, defaultdict
import gzip
from itertools import groupby
import json
from pathlib import Path

from classify_inputs import BATCH, write_json, write_rows
from input_census import ART, BASE, OLD, ROOT, digest, frozen
from compile_repair.evaluation.report import aggregate_attributions, classify_record, parseable_version_blockers
from compile_repair.toolchain.solc import diagnostic_template, parse_diagnostics, version_tuple


def load_rows(raw):
    rows = [json.loads(s) for s in gzip.decompress(raw).splitlines()]
    by_id = {r["unit_id"]:r for r in rows}
    assert len(by_id)==len(rows)
    return by_id


def examples_for_signatures(rows, signatures):
    result = []
    for key, items in sorted(signatures.items(),key=lambda x:(-len(x[1]), x[0]))[:3]:
        row = rows[items[0]]
        ref = row["selected_result"]
        payload = Path(ref["result_path"]).read_bytes()
        assert digest(payload)==ref["result_sha256"]
        record = json.loads(payload)
        seen = defaultdict(list)
        for attempt in record["attempts"]:
            if attempt.get("solc"):
                seen[attempt["version"]].append(attempt["solc"])
        groups = []
        for labels, group in groupby(key,key=lambda v:v[1]):
            versions = [v for v,_ in group]
            evidence = set()
            for call in seen[versions[0]]:
                evidence.update((d["kind"],diagnostic_template(d["message"])) for d in parse_diagnostics(call["stderr"])
                                if d["kind"]!="Warning")
            groups.append(dict(versions=versions,categories=labels,example_version=versions[0],
                               example_diagnostics=[dict(kind=k,template=v) for k,v in sorted(evidence)[:8]]))
        result.append(dict(units=len(items),by_corpus=Counter(rows[u]["corpus"] for u in items),
                           example_unit=items[0],example_sha256=row["entry_sha256"],selected_result=ref,
                           blockers=row["parseable_blockers"],groups=groups))
    return result


def main(out):
    prior = load_rows(frozen(OLD))
    prior_summary = json.loads(frozen(ART/"cp3_1_v1/failure_summary.json"))
    assert prior_summary["source_artifact_sha256"]==digest(OLD.read_bytes())
    facts = load_rows((out/"language_classifications.jsonl.gz").read_bytes())
    links = json.loads((out/"replacement_provenance.json").read_bytes())["rows"]
    replacements = load_rows((out/"input_results.jsonl.gz").read_bytes())
    assert set(links)==set(replacements)
    taxonomy = json.loads(frozen(ART/"cp3_1_v1/taxonomy.json"))
    routes = json.loads(frozen(ART/"cp3_1_v1/d6_cp4_final.json"))
    foreign = "non_solidity_input"
    taxonomy["previous_taxonomy_sha256"] = digest((ART/"cp3_1_v1/taxonomy.json").read_bytes())
    taxonomy["sources"]["input_language"] = dict(section="PROMPTS 4.5c.1",decision="cp3_2_v1/authorization.json")
    taxonomy["categories"].append(dict(category=foreign,solc_error_types=[],message_templates=[],error_codes=[],
                cause="Explicit foreign JSON language or positive source-language evidence.",sources=["input_language"],
                candidate_repair="Out of scope; stop at input format.",change_level="none",
                verification=["Entry identity and positive language evidence; zero tool calls."],verified_versions=[],
                cp4_operator=None,observed_templates=[],d6_route_status="out_of_scope"))
    taxonomy["input_format_stage"]="CP3.2 tri-state language screen before version plan; unknown proceeds."
    write_json(out/"taxonomy.json",taxonomy)
    categories=[r["category"] for r in taxonomy["categories"]]
    rows, excluded, unmeasured, signatures = {}, [], [], defaultdict(list)
    for uid,fact in facts.items():
        old = prior.get(uid)
        row = dict((k,fact[k]) for k in ("unit_id","corpus","entry_sha256"))
        row["language"] = fact["language"]
        if uid in links:
            link=links[uid]
            assert link["old"]==(old["selected_result"] if old else None) and row["entry_sha256"]==link["entry_sha256"]
            record=replacements[uid]
            raw=Path(link["new"]["result_path"]).read_bytes()
            assert digest(raw)==link["new"]["result_sha256"] and json.loads(raw)==record
            labels=sorted({f["category"] for f in classify_record(record)})
            assert labels==[link["reason"]]
            row.update(status=record["status"],selected_result=link["new"],source="cp3_2",
                       primary=dict(categories=labels,by_version={}),any_categories=labels)
            if labels==[foreign]:
                excluded.append(dict(row,prior_primary=old["primary"]["categories"] if old else [],
                                     prior_any=old["any_categories"] if old else [],previous_result=link["old"]))
        elif old:
            assert all(row[k]==old[k] for k in ("unit_id","corpus","entry_sha256"))
            row.update({k:old[k] for k in ("status","primary","any_categories","selected_result","source")})
        else:
            assert fact["previous_status"]=="historically_excluded" and fact["language"]["status"]!="non_solidity"
            row.update(status="unmeasured",selected_result=None,source="historical_exclusion",
                       primary=dict(categories=[],by_version={}),any_categories=[])
            unmeasured.append({k:row[k] for k in ("unit_id","corpus","entry_sha256","language")})
        if "version_dependent" in row["primary"]["categories"]:
            versions=row["primary"]["by_version"]
            row["parseable_blockers"]=parseable_version_blockers(versions)
            key=tuple((v,tuple(versions[v])) for v in sorted(versions,key=version_tuple))
            signatures[key].append(uid)
        rows[uid]=row
    write_rows(out/"unit_attributions.jsonl.gz",rows.values())
    write_json(out/"non_solidity.json",dict(units=len(excluded),by_corpus=Counter(r["corpus"] for r in excluded),
               by_previous_primary=Counter(c for r in excluded for c in r["prior_primary"]),rows=excluded))
    write_rows(out/"unmeasured.jsonl.gz",unmeasured)
    tables=aggregate_attributions(rows.values(),categories)
    for table,labels in (("primary",lambda r:r["primary"]["categories"]),("any_candidate",lambda r:r["any_categories"])):
        example_ids=defaultdict(list)
        for r in sorted(rows.values(),key=lambda r:(r["entry_sha256"],r["unit_id"])):
            if r["status"]=="unmeasured" or r["language"]["status"]=="non_solidity":
                continue
            for name in labels(r):
                if len(example_ids[name])<3:
                    example_ids[name].append({k:r[k] for k in ("unit_id","entry_sha256","corpus","selected_result")})
        for item in tables[table]["category_unit_counts"]:
            item["unit_examples"]=example_ids[item["category"]]
    blockers=tables["version_dependent_blockers"]
    blockers["top_three_version_signatures"]=examples_for_signatures(rows,signatures)
    for cell in blockers["category_unit_counts"]:
        sample=[r for r in rows.values() if "parseable_blockers" in r and cell["category"] in (r["parseable_blockers"] or ["none"])]
        cell["example_units"]=[{k:r[k] for k in ("unit_id","corpus","entry_sha256","selected_result")} for r in sample[:3]]
    write_json(out/"version_blockers.json",blockers)
    tables.update(original=len(rows), historically_eligible=len(prior),previous_excluded=len(facts)-len(prior),
                  old_basis={key:prior_summary[key] for key in ("primary","any_candidate")},
                  old_summary_sha256=digest((ART/"cp3_1_v1/failure_summary.json").read_bytes()),
                  original_attributions_sha256=digest(OLD.read_bytes()),
                  approved_attributions_sha256=digest((out/"unit_attributions.jsonl.gz").read_bytes()),
                  excluded=len(excluded),unmeasured=len(unmeasured),reused=len(set(prior)-set(links)),replaced=len(links))
    total=sum(tables["primary"]["total"].values())
    success=sum(tables["primary"]["success"].values())
    failed=sum(tables["primary"]["remaining_failures"].values())
    assert len(rows)==total+len(excluded)+len(unmeasured)==31307 and total==success+failed and success==21223
    assert len(excluded)==sum(tables["non_solidity_by_corpus"].values())
    assert len(unmeasured)==sum(tables["unmeasured_by_corpus"].values())
    assert tables["primary"]["remaining_failures"]==tables["any_candidate"]["remaining_failures"]
    write_json(out/"failure_summary.json",tables)
    routes["categories"].append(dict(category=foreign,route="out_of_scope",repair=None,change_level="none",
        mechanical_checks="Positive input language evidence; do not call tools.",cp4_operator=None,
        fallback=None,sources=["input_language"],implementation_in_cp3=False,
        no_source_corruption_operator_reason="Foreign input is outside Solidity repair scope.",excluded_units=len(excluded)))
    pc={r["category"]:r for r in tables["primary"]["category_unit_counts"]}
    ac={r["category"]:r for r in tables["any_candidate"]["category_unit_counts"]}
    for route in routes["categories"]:
        name=route["category"]
        route.update(observed_units=pc[name]["units"],fraction_remaining_failures=pc[name]["fraction_remaining_failures"],
                     any_candidate_units=ac[name]["units"])
    routes.update(schema="cp3.2-d6-priority",status="complete_cp3.2_routes_and_cp4_operator_inventory",
        count_basis="Primary causes on measured, eligible failures; non-Solidity and unmeasured inputs reported separately.",
        implementation_priority_by_frequency_only=sorted((n for n in categories if n!=foreign),key=lambda k:(-pc[k]["units"],k)),
        zero_frequency_categories_retained=sorted(k for k in categories if not pc[k]["units"]),
        basis_sha256=digest((out/"taxonomy.json").read_bytes()),frequency_summary_sha256=digest((out/"failure_summary.json").read_bytes()),
        blocker_table="version_blockers.json")
    assert len(routes["categories"])==len(categories)==31 and len(routes["breaking_changes"])==125
    write_json(out/"d6_cp4_final.json",routes)
    print("measured",total,"success",success,"failures",failed,"foreign",len(excluded),"unmeasured",len(unmeasured),
          "supplementary blocker population",blockers["units"])


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=BATCH)
    main(p.parse_args().out)
