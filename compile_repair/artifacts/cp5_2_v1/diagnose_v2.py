"""Read the CP5.1 repair receipts and explain each unsuccessful relative-path repair."""
from collections import Counter, defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ART = OUT.parent
OLD = ART / "cp5_1_v1"
ROOT = ART.parents[1]
sys.path.insert(0, str(ROOT))
from compile_repair.rules.dependencies import (
    _suffix_rank, compatible_compilers, import_symbols, package_spec, source_declarations,
)
from compile_repair.toolchain.project import project_entries
from compile_repair.toolchain.solc import lexical_tokens


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def contents(path, expected=None):
    raw = Path(path).read_bytes()
    if expected is not None and digest(raw) != expected:
        raise ValueError("Receipt hash mismatch: " + str(path))
    return raw


def records(name, seal):
    raw = contents(OLD/name, seal[name]["sha256"])
    if name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return [json.loads(line) for line in raw.splitlines()]


def write(name, obj):
    with (OUT/name).open("x", encoding="utf8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


@lru_cache(maxsize=48)
def names_in(root):
    names = defaultdict(list)
    for p in project_entries(root):
        names[p.name.casefold()].append(p)
    return names


@lru_cache(maxsize=1536)
def exported(raw):
    return frozenset(source_declarations(raw)[0])


@lru_cache(maxsize=512)
def words(raw):
    return {v.decode("ascii") for _, _, kind, v in lexical_tokens(raw) if kind == "word" and v.isascii()}


def rel(file, root):
    return Path(file).relative_to(root).as_posix()


def issue_key(row):
    return (row.get("importer", ""), row.get("line"), row.get("path", ""), row["category"])


def expanded(keys):
    return [dict(importer=i, line=l, path=p, category=c) for i,l,p,c in sorted(keys.elements(),key=repr)]


def filtered(project, origin, search, versions, overlays):
    """Reproduce the per-stage exclusions for a terminal empty or ambiguous search."""
    physical = dict(project["source_units"])
    body = {rel(f["path"],project["root"]):contents(f["path"],f["sha256"]) for f in project["files"]}
    available = dict(overlays)
    available.update(body)
    known = set().union(*(exported(v) for v in available.values()))
    details = []
    for obs in search:
        if obs.get("selected"):
            continue
        issues = [i for i in project["issues"] if (i.get("importer"),i.get("line"),i.get("path"))==
                  (obs["importer"],obs["line"],obs["path"])]
        if not issues:
            raise ValueError("Missing historical import " + str(obs))
        row=issues[0]
        name=physical[row["importer"]]
        raw=body[name]
        leaf=Path(row["path"]).name
        paths=[p for p in names_in(origin).get(leaf.casefold(),()) if p!=origin/name and p.resolve()==p and origin in p.parents]
        required=import_symbols(raw,row)
        candidates=[]
        symbol_matches=0
        for p in paths:
            key=p.relative_to(origin).as_posix()
            data=available[key] if key in available else contents(p)
            declared=exported(data)
            needed=required or (words(raw)&declared-known)
            if not needed or not needed<=declared:continue
            symbol_matches+=1
            if not compatible_compilers(list(body.values())+[data],versions):continue
            candidates.append([list(_suffix_rank(row["path"],key)), key, sorted(needed)])
        candidates.sort()
        same=candidates==obs["candidates"]
        rank=needed_count=None
        if candidates:
            rank=candidates[0][0]
            needed_count=sum(v[0]==rank for v in candidates)
        if not same: reason="recorded_candidate_set_differs_from_replay"
        elif not paths:reason="no_casefold_basename"
        elif not symbol_matches:reason="required_symbols_not_supported"
        elif not candidates:reason="no_common_supported_pragma"
        else:reason="ambiguous_best_suffix"
        details.append(dict(importer=row["importer"],line=row["line"],path=row["path"],casefold_names=len(paths),
            exact_case_names=sum(p.name==leaf for p in paths),symbol_matches=symbol_matches,pragma_matches=len(candidates),
            best_count=needed_count,best_rank=rank,replay_matches_receipt=same,filter=reason))
    return details


def diagnose(kind, row, proof, versions):
    uid=row["unit_id"]
    unit=Path(proof["unit_store"])/"units"/uid
    hashes=proof["receipts"]
    selected_path=Path(row["result_path"])
    selected_key=selected_path.relative_to(unit).as_posix()
    accepted_paths=[s["receipt"] for s in json.loads(contents(unit/"repair_steps.json",hashes["repair_steps.json"])) if s.get("accepted")]
    intended=(Path(proof["unit_store"])/accepted_paths[-1]) if kind=="moved" and accepted_paths else unit/"result.json"
    assert selected_path==intended
    assert hashes[selected_key]==hashes["result.json"]==row["result_sha256"]
    contents(selected_path,row["result_sha256"])
    final=json.loads(contents(unit/"result.json",hashes["result.json"]))
    steps=json.loads(contents(unit/"repair_steps.json",hashes["repair_steps.json"]))
    first_path=unit/"project.json"
    project=json.loads(contents(first_path))
    initial_hash=digest(contents(first_path))
    origin=Path(project["root"])
    overlays={}
    rounds=[]
    flags=set()
    accepted4=False
    # Promotion is recorded on exactly the selected attempt, including a deferred step 3.
    for step in steps:
        if "receipt" not in step and step["step"]!=4:continue
        other=None
        if "receipt" in step:
            path=Path(proof["unit_store"])/step["receipt"]
            key=path.relative_to(unit).as_posix()
            result=json.loads(contents(path,hashes[key]))
            assert result["status"]==step["status"] and result["reason"]==step["reason"]
            pp=path.with_name("project.json")
            if pp.is_file():other=json.loads(contents(pp))
        if step["step"]==4:
            search=step.get("path_search",[])
            chose=[s for s in search if s.get("selected")]
            old=Counter(map(issue_key,project["issues"]))
            new=Counter(map(issue_key,other["issues"])) if other is not None else old
            added=new-old
            old_members=set(dict(project["source_units"]).values())
            members=dict(other["source_units"]) if other else dict(project["source_units"])
            new_members=set(members.values())-old_members
            edits=[i for i in project["issues"] if any((x["importer"],x["line"],x["path"])==
                   (i.get("importer"),i.get("line"),i.get("path")) for x in chose)]
            edited_disappeared=bool(edits) and not any(issue_key(i) in new for i in edits)
            fresh_relative=bool(added) and all(members.get(i) in new_members and c=="missing_relative_file"
                and p.startswith(("./","../")) and package_spec(p) is None for i,_,p,c in added)
            rejected=bool(chose) and not step["accepted"] and step.get("reason")=="unresolved_imports" and (
                step.get("errors_before") is not None and step.get("errors_after") is not None and step["errors_after"]>=step["errors_before"])
            chain=rejected and edited_disappeared and fresh_relative
            filters=filtered(project,origin,search,versions,overlays)
            evidence=dict(accepted=step["accepted"],round=step.get("round"),selected=len(chose),errors_before=step.get("errors_before"),
                          errors_after=step.get("errors_after"),reason=step.get("reason"),filters=filters,
                          new_issues=expanded(added),remaining_issues=expanded(new),new_physical_files=sorted(new_members),
                          selected_disappeared=edited_disappeared,all_added_errors_relative_in_new_files=fresh_relative,
                          rejected_equal_or_worse=rejected,chain_condition=chain,
                          chosen=[dict(importer=x["importer"],line=x["line"],old_path=x["path"],target=x["selected"]) for x in chose])
            if other is not None:
                evidence.update(receipt=key,receipt_sha256=hashes[key],project_sha256=digest(contents(pp)))
            if chain:flags.add("a")
            if filters:flags.add("b")
            rounds.append(evidence)
            accepted4=accepted4 or step["accepted"]
        if step.get("accepted") and other is not None:
            project=other
            for f in other["files"]:
                name=rel(f["path"],other["root"])
                if name.startswith(".compile_repair/deps/") or (step["step"]==4 and any(x.get("importer")==name and x.get("selected") for x in step.get("path_search",[]))):
                    overlays[name]=contents(f["path"],f["sha256"])
    final_cats=row.get("primary") or sorted({i["category"] for i in project["issues"]})
    if accepted4 and final["reason"]=="all_solc_candidates_failed" and not project["issues"]:
        group="c"
        detail="accepted_rewrite_remaining_compiler_diagnostics"
    elif "a" in flags:
        group="a";detail="rejected_rewrite_new_relative_imports_in_entering_files"
    elif rounds and rounds[-1]["filters"] and not rounds[-1]["selected"]:
        group="b";detail="terminal_search_has_no_unique_supported_target"
    else:
        group="d"
        if not rounds: detail="no_step4_record"
        elif not rounds[-1]["selected"] and not rounds[-1]["filters"]:detail="no_eligible_relative_import_in_final_project"
        elif rounds[-1]["selected"] and rounds[-1]["accepted"]:detail="accepted_rewrite_with_remaining_import_errors"
        else:detail="rejected_rewrite_not_explained_by_new_relative_errors_alone"
    return dict(unit_id=uid,kind=kind,split=row["split"],corpus=row["corpus"],group=group,detail=detail,
                stages_seen=sorted(flags),accepted_step4=accepted4,final_reason=final["reason"],final_categories=final_cats,
                final_issues=expanded(Counter(map(issue_key,project["issues"]))),rounds=rounds,
                origin_project_sha256=initial_hash,result_sha256=hashes["result.json"],steps_sha256=hashes["repair_steps.json"])


def main():
    baseline=json.loads(contents(OUT/"baseline.json"))
    old_seal=baseline["sources"]["compile_repair/artifacts/cp5_1_v1/seal.json"]
    seal=json.loads(contents(OLD/"seal.json",old_seal))["files_excluding_this_seal"]
    benchmarks=records("packed/benchmark.jsonl.gz",seal)
    real=records("packed/real_full.jsonl.gz",seal)
    census=records("path_census.jsonl",seal)
    relevant={r["unit_id"] for r in census if "missing_relative_file" in r["categories"] and
              any(len(i["symbols"])==1 for i in r["imports"] if i["category"]=="missing_relative_file")}
    selected=[("moved",r) for r in benchmarks if r["operator"]=="missing_relative_file_moved" and r["status"]!="success"]
    selected.extend(("real",r) for r in real if r["unit_id"] in relevant and not r["d3"])
    assert Counter(kind for kind,_ in selected)=={"moved":211,"real":102}
    receipts={(r["stage"],r["operator"],r["unit_id"]):r for r in records("invocation_seals.jsonl.gz",seal)
              if r["stage"] in ("benchmark","real_full") and r["operator"] in (None,"missing_relative_file_moved")}
    versus=json.loads(contents(ART/"cp0_1_compilers_v1/coverage.json"))
    versions=[v for series in versus["series"].values() for v in series["installed"]]
    assert len(set(versions))==92
    evidence=[]
    for kind,r in selected:
        proof=receipts[("benchmark",r["operator"],r["unit_id"])] if kind=="moved" else receipts[("real_full",None,r["unit_id"])]
        evidence.append(diagnose(kind,r,proof,versions))
    counts={kind:dict(Counter(r["group"] for r in evidence if r["kind"]==kind)) for kind in ("moved","real")}
    missing=[(r["kind"],r["unit_id"],s["filter"]) for r in evidence for v in r["rounds"] for s in v["filters"] if not s["replay_matches_receipt"]]
    output=OUT/"diagnosis.jsonl"
    with output.open("x",encoding="utf8",newline="\n") as f:
        for item in evidence:f.write(json.dumps(item,sort_keys=True,ensure_ascii=False)+"\n")
    summary=dict(counts=counts,rows=len(evidence),table_sha256=digest(contents(output)),filter_replay_differences=missing,
                 examples={kind:{g:next(r["unit_id"] for r in evidence if r["kind"]==kind and r["group"]==g)
                           for g in group} for kind,group in counts.items()},
                 reason_counts={kind:dict(Counter(r["detail"] for r in evidence if r["kind"]==kind)) for kind in counts},
                 filter_occurrences={kind:dict(Counter(s["filter"] for r in evidence if r["kind"]==kind for v in r["rounds"] for s in v["filters"])) for kind in counts},
                 eligible_chain_requires="All rewritten errors disappear, all newly introduced errors are relative imports in entering files, error count does not fall and the candidate was rejected.",
                 old_seal=old_seal)
    write("diagnosis_summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
