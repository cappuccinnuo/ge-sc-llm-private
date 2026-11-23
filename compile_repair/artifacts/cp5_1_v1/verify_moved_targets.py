"""Check whether each moved-file benchmark used its recorded destination, without changing CP4.5 scores."""
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import posixpath

BATCH=Path(__file__).resolve().parent
LOCAL=BATCH.parents[3]/"compile-repair-local"/BATCH.name


def digest(data):
    return hashlib.sha256(data).hexdigest()


def linux_file(name):
    if os.name=="nt":
        return Path(r"\\wsl.localhost\Ubuntu-22.04")/name.lstrip("/")
    return Path(name)


def main():
    bench=BATCH/"benchmark.jsonl"
    triggers=BATCH/"moved_triggers.jsonl"
    summary=json.loads((BATCH/"benchmark_summary.json").read_bytes())
    moves=json.loads((BATCH/"moved_summary.json").read_bytes())
    assert digest(bench.read_bytes())==summary["rows_sha256"]
    assert digest(triggers.read_bytes())==moves["observations_sha256"]
    injuries={r["unit_id"]:r for r in map(json.loads,triggers.read_bytes().splitlines()) if r["outcome"]=="included"}
    observed={}
    totals=defaultdict(Counter)
    unresolved=Counter()
    with bench.open("rb") as stream:
        for row in map(json.loads,stream):
            if row["operator"]!="missing_relative_file_moved":continue
            uid=row["unit_id"]
            expected=injuries[uid]
            raw=linux_file(expected["mutation_path"]).read_bytes()
            assert digest(raw)==expected["mutation_sha256"]==row["mutation_sha256"]
            mutation=json.loads(raw)
            (old,new),=mutation["file_renames"].items()
            folder=LOCAL/"benchmark"/row["policy"]/row["operator"]/uid/"units"/uid
            step_file=folder/"repair_steps.json"
            steps=step_file.read_bytes() if step_file.exists() else b"[]"
            choices=[]
            reasons=set()
            for step in json.loads(steps):
                if step["step"]!=4:continue
                for path in step.get("path_search",[]):
                    logical=posixpath.normpath(posixpath.join(posixpath.dirname(path["importer"]),path["path"]))
                    if logical!=old:continue
                    if "selected" in path and step["accepted"]:choices.append(path["selected"])
                    if "reason" in path:reasons.add(path["reason"])
            score=row["score"]
            success=score["compiled"]
            exact_dest=bool(choices) and all(choice==new for choice in choices)
            stable=(score["kept"]["equal"]==score["kept"]["units"] and score["calls"]["ratio"]==1
                     and score["cfg_edges"]["ratio"]==1 and not any(score[k] for k in ("removed_by_repair","added","lost","missing_kept")))
            gate=score.get("migration_counters",{}).get("status")
            count=totals[row["split"]]
            count["total"]+=1
            count["d3"]+=int(success)
            count["d3_and_selected_recorded_destination"]+=int(success and exact_dest)
            count["exact"]+=int(score["exact"])
            count["d3_full_graph_metrics"]+=int(success and stable)
            count["full_graph_metrics_outside_damage_neighborhood"]+=int(success and stable and not score["added_bytes_near_damage"] and gate!="rejected")
            if not success:
                for reason in reasons:unresolved[reason]+=1
            assert uid not in observed
            observed[uid]=dict(split=row["split"],compiled=success,old=old,destination=new,
                 selected_for_old=sorted(set(choices)),reasons_for_old=sorted(reasons),
                 full_graph_metrics=stable if success else None,added_bytes_near_damage=score["added_bytes_near_damage"],
                 exact=score["exact"],migration_name_status=gate,mutation_sha256=row["mutation_sha256"],
                 repair_steps_sha256=digest(steps) if step_file.exists() else None,result_sha256=row["result_sha256"])
    assert set(observed)==set(injuries) and len(observed)==400
    out=dict(benchmark_rows_sha256=summary["rows_sha256"],moved_triggers_sha256=moves["observations_sha256"],
             splits=totals,rejection_reasons_in_unrepaired_units=unresolved,units=observed,
             interpretation="Only step-4 edits whose original import resolves to the recorded displaced file are counted. "
             "The graph-only check reports existing pooled facts per unit. The formal exact definition and all scores are retained.")
    with (BATCH/"moved_path_outcomes.json").open("x",encoding="utf8") as dst:
        json.dump(out,dst,sort_keys=True,ensure_ascii=False,indent=2)
        dst.write("\n")
    print(dict(totals),dict(unresolved),flush=True)


if __name__=="__main__":
    main()
