"""CPU-only fixed-source acceptance orchestration for NS-P3a."""
import argparse
from collections import Counter
import json
from pathlib import Path
from .facts import extract_source, write_task, statistics, ROOT
from .facts_io import PLAN
from scripts.DFG.models import Unsupported
from scripts.DFG.dfg_v2.benchmark_v2.prepare import ref, read, write

COHORTS = ("arithmetic", "denial_of_service", "front_running", "time_manipulation", "unchecked_low_level_calls")


def smoke(output):
    results = {}
    base = ROOT / "experiments/ge-sc-data/source_code"
    for cohort in COHORTS:
        folder = base / cohort / "source_files"
        paths = sorted(folder.glob("*.sol"), key=lambda p:p.name)
        marked = [p for p in paths if p.stem.startswith("buggy_")][:5]
        ordinary = [p for p in paths if not p.stem.startswith("buggy_")][:5]
        if len(marked) != 5 or len(ordinary) != 5:
            raise ValueError("Fixed smoke source strata lack five files each")
        files, all_rows, failures = [], {}, []
        for i, path in enumerate(marked + ordinary):
            try:
                rows, audit = extract_source(path.read_text(encoding="utf8"), path.name)
                all_rows.update({str(i)+":"+str(k):v for k,v in rows.items()})
                files.append(dict(source=ref(path), functions=sum(r["node_kind"] in ("function","modifier") for r in rows.values()),
                                  rows=len(rows), stats=statistics(rows), modifiers=audit["modifiers"]))
            except Unsupported as exc:
                failures.append(dict(source=ref(path),reason=str(exc)))
        results[cohort] = dict(files=files,parse_failures=failures,exceptions=0,
            stats=statistics(all_rows),functions=sum(f["functions"] for f in files))
        print(cohort, len(files), "files", len(failures), "parse failures", flush=True)
    path = Path(output)/"cross_category_smoke.json"
    if path.exists():
        raise FileExistsError(str(path))
    write(path,dict(view="original",results=results,trained=False,uses_graphs=False,uses_targets=False,
                    note="AST smoke only; unknown DFG/CFG is intentional, parsing is not compilation"))
    return results


def tasks(output):
    summaries = {}
    for task in read(PLAN)["tasks"]:
        print("Fact extraction",task,flush=True)
        summaries[task] = write_task(task,output)["stats"]
        print(task,summaries[task]["rows"],flush=True)
    write(Path(output)/"stats.json",dict(view="original",tasks=summaries))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("smoke","tasks"))
    p.add_argument("--out",required=True)
    args=p.parse_args()
    (smoke if args.mode=="smoke" else tasks)(args.out)


if __name__=="__main__":
    main()
