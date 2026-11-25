"""CP6 check on real corpus units: records steps 5 and 8 (acceptance, D27 phase progress) per unit.

Usage: python -B real_check.py <targets.json> <output dir> <summary.json>
targets.json rows (from select_targets.py): unit_id, corpus, primary, any, path (entry file),
project_root (null for a file or snippet, which is repaired without a project).
Runs the production pipeline without an offline dependency index; reads corpora only.
"""
import collections
import hashlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from compile_repair.core.store import ArtifactStore  # noqa: E402
from compile_repair.evaluation.report import primary_causes  # noqa: E402
from compile_repair.pipeline import repair_unit  # noqa: E402
from compile_repair.core.model import CompilationUnit, SourceFile  # noqa: E402
from compile_repair.toolchain.project import ProjectIndex, resolve_project  # noqa: E402
from compile_repair.toolchain.solc import load_trusted_compilers  # noqa: E402
from dataclasses import asdict  # noqa: E402

targets, out, summary_path = json.load(open(sys.argv[1])), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=False)
compilers, _, _ = load_trusted_compilers()
rows = []
for t in targets:
    start = time.monotonic()
    entry = Path(t["path"])
    root = Path(t["project_root"]) if t.get("project_root") else None
    files = list(root.rglob("*.sol")) if root else [entry]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    store = ArtifactStore(out / t["unit_id"])
    if root:
        index = ProjectIndex(root)
        project = resolve_project(index.root, entry.resolve(), (), index)
        record = repair_unit(CompilationUnit(t["unit_id"], project.files), compilers, store, io.StringIO(),
                             project=project, project_index=index)
    else:
        # A file or snippet without a project root: the pipeline searches no other local files.
        raw = entry.read_bytes()
        record = repair_unit(CompilationUnit(t["unit_id"], (SourceFile(str(entry), hashlib.sha256(raw).hexdigest(), raw),)),
                             compilers, store, io.StringIO())
    steps = json.loads((store.path / "units" / t["unit_id"] / "repair_steps.json").read_bytes()) \
        if (store.path / "units" / t["unit_id"] / "repair_steps.json").exists() else []
    unchanged = all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in before.items())
    rows.append(dict(unit_id=t["unit_id"], corpus=t["corpus"], cp3_primary=t["primary"], status=record.status,
                     reason=record.reason, selected_version=record.selected_version,
                     primary_now=primary_causes(asdict(record))["categories"],
                     rule_steps=[dict(step=s["step"], accepted=s.get("accepted"), accepted_by=s.get("accepted_by"),
                                      status=s.get("status"), errors_before=s.get("errors_before"),
                                      errors_after=s.get("errors_after"), phase_before=s.get("phase_before"),
                                      phase_after=s.get("phase_after"),
                                      evidence=s.get("normalization") or s.get("structure"))
                                 for s in steps if s["step"] in (5, 8)],
                     levels=sorted({p.level for p in record.provenance.values()}) if record.provenance else [],
                     corpus_unchanged=unchanged, seconds=round(time.monotonic() - start, 2)))
    print(t["unit_id"], record.status, rows[-1]["primary_now"], flush=True)
summary = dict(units=len(rows), success=sum(r["status"] == "success" for r in rows),
               step5_accepted=sum(any(s["accepted"] and s["step"] == 5 for s in r["rule_steps"]) for r in rows),
               step8_accepted=sum(any(s["accepted"] and s["step"] == 8 for s in r["rule_steps"]) for r in rows),
               phase_advanced=sum(any(s["accepted_by"] == "phase_advanced" and s["accepted"] for s in r["rule_steps"])
                                  for r in rows),
               primary_now=dict(collections.Counter(c for r in rows if r["status"] != "success"
                                                    for c in r["primary_now"]).most_common()),
               corpus_unchanged=all(r["corpus_unchanged"] for r in rows), rows=rows)
summary_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf8")
print(json.dumps({k: v for k, v in summary.items() if k != "rows"}))
