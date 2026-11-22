"""Apply the approved production decision to every SHA-checked entry; never compile."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
import io
import json
from pathlib import Path
import time

from input_census import ART, BASE, INVENTORY, OLD, REVIEW, ROOT, WRAPPERS, digest, frozen
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.toolchain.project import input_format_evidence, resolve_project

BATCH = Path(__file__).resolve().parent


def write_json(path, data):
    with path.open("x", encoding="utf8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write("\n")


def write_rows(path, rows):
    with path.open("xb") as f, gzip.GzipFile(filename="", fileobj=f, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode())


def blocked_tool(*args, **kwargs):
    raise RuntimeError("Input-stage replacement reached a tool")


def main(out, local):
    start = time.monotonic()
    units = [json.loads(line) for line in frozen(INVENTORY).splitlines()]
    past = {r["unit_id"]:r for r in (json.loads(s) for s in gzip.decompress(frozen(OLD)).splitlines())}
    reviewed = {r["unit_id"] for r in json.loads(frozen(REVIEW))}
    past_wrappers = set(json.loads(frozen(WRAPPERS))["hits"])
    approval = json.loads((BATCH/"authorization.json").read_bytes())
    assert approval["request_sha256"] == digest((BATCH/"decision_request.json").read_bytes())
    facts, cache, counts = {}, {}, defaultdict(Counter)
    for unit in units:
        uid = unit["unit_id"]
        raw = Path(unit["path"]).read_bytes()
        sha = digest(raw)
        assert sha == unit["entry_sha256"] and uid not in facts, uid
        if sha not in cache:
            cache[sha] = input_format_evidence(raw)
        language, wrapper = cache[sha]
        old = past.get(uid)
        if old:
            assert (unit["corpus"], sha) == (old["corpus"], old["entry_sha256"])
        else:
            assert unit["corpus"] == "SOChecker" and not unit["language_evidence"]["is_solidity"]
        counts[unit["corpus"]][language["status"]] += 1
        facts[uid] = dict(unit_id=uid, corpus=unit["corpus"], entry_sha256=sha, language=language,
                          wrapper=wrapper, previous_status=old["status"] if old else "historically_excluded")
    foreign = {uid for uid,r in facts.items() if r["language"]["status"] == "non_solidity"}
    wrapped = {uid for uid,r in facts.items() if r["wrapper"] is not None}
    prior_successes = [u for u,r in past.items() if r["status"] == "success"]
    old_excluded = set(facts)-set(past)
    changes = foreign | (wrapped-past_wrappers)
    summary = dict(original_units=len(units), distinct_sha256=len(cache), language_by_corpus=counts,
                   successes_admitted=sum(u not in foreign and u not in wrapped for u in prior_successes),
                   successful_unknown=sum(facts[u]["language"]["status"]=="unknown" for u in prior_successes),
                   mando_positive=counts["MANDO"]["solidity"], previous_excluded=len(old_excluded),
                   prior_excluded_now_unmeasured=len(old_excluded-foreign),
                   prior_excluded_now_foreign=len(old_excluded&foreign),
                   review_confirmed_foreign=len(reviewed&foreign), original_wrappers=len(past_wrappers),
                   wrappers=len(wrapped), wrapper_added=sorted(wrapped-past_wrappers),
                   wrapper_lost=sorted(past_wrappers-wrapped), elapsed_seconds=round(time.monotonic()-start,3))
    evidence_path = out/"language_classifications.jsonl.gz"
    write_rows(evidence_path, facts.values())
    summary["observations_sha256"] = digest(evidence_path.read_bytes())
    write_json(out/"language_acceptance.json", summary)
    assert len(facts)==31307 and len(past)==31071 and len(old_excluded)==236 and len(prior_successes)==21223
    assert summary["successes_admitted"]==21223 and summary["mando_positive"]==846
    assert len(reviewed)==22 and reviewed<=foreign and past_wrappers<=wrapped
    store = ArtifactStore(local)
    links, records = {}, []
    for unit in units:
        uid = unit["unit_id"]
        if uid not in changes:
            continue
        row = facts[uid]
        path = Path(unit["path"])
        project = resolve_project(unit["project_root"], path) if unit["project_root"] else None
        raw = path.read_bytes()
        assert digest(raw)==row["entry_sha256"]
        sources = project.files if project else (SourceFile(str(path), row["entry_sha256"], raw, unit["kind"]),)
        journal = io.StringIO()
        result = repair_unit(CompilationUnit(uid,sources), {}, store, journal, project=project,
                             compile_fn=blocked_tool, project_compile_fn=blocked_tool, slither_fn=blocked_tool)
        reason = "non_solidity_input" if uid in foreign else "standard_json_input"
        assert result.reason==reason and result.plan is None and not journal.getvalue()
        assert result.inputs[0]["language_evidence"]==row["language"] and len(result.attempts)==1
        new_path = local/"units"/uid/"result.json"
        assert json.loads(new_path.read_bytes())["inputs"][0]["sha256"]==row["entry_sha256"]
        old = past.get(uid)
        old_ref = old["selected_result"] if old else None
        if old_ref:
            assert digest(Path(old_ref["result_path"]).read_bytes())==old_ref["result_sha256"]
        new_ref = dict(kind="cp3_2_input_format",result_path=str(new_path),result_sha256=digest(new_path.read_bytes()))
        links[uid] = dict(old=old_ref, new=new_ref, entry_sha256=row["entry_sha256"], reason=reason,
                          previous_primary=old["primary"]["categories"] if old else [], corpus=unit["corpus"])
        records.append(json.loads(new_path.read_bytes()))
    write_rows(out/"input_results.jsonl.gz",records)
    write_json(out/"replacement_provenance.json",dict(rows=links, historical_input=BASE,
               previous_attributions_sha256=digest(OLD.read_bytes()), observed_tools=0,
               reused_previous=len(set(past)-changes), original_exclusions_without_previous_results=len(old_excluded)))
    print(json.dumps(summary), "new records",len(links), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=BATCH)
    parser.add_argument("--local", type=Path, default=ROOT.parent/"compile-repair-local"/BATCH.name/"input_results")
    args = parser.parse_args()
    main(args.out, args.local)
