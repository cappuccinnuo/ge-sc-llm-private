"""CP8 dry run: the first-stage agent over real failing units with a scripted client.

Usage: python -B dry_run.py <targets.json> <knowledge dir> <out dir> <summary.json> [<max units>]
The scripted client answers with no patch, so no unit changes and nothing is spent; the
run checks, on real projects, that every prompt is built (sizes, retrieved knowledge),
that no real file name, directory or comment text reaches a prompt, and that the agent
stops after its stall rounds. Group = project root (or the snippet file), as in K3.
"""
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from compile_repair.agents.llm import ScriptedClient
from compile_repair.agents.prompt import blank_comments
from compile_repair.agents.stage1 import Stage1
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import ArtifactStore
from compile_repair.pipeline import repair_unit
from compile_repair.rag.knowledge import KnowledgeBase
from compile_repair.toolchain.project import ProjectIndex, resolve_project
from compile_repair.toolchain.solc import load_trusted_compilers

targets, kb, out, summary_path = json.load(open(sys.argv[1])), KnowledgeBase.load(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
limit = int(sys.argv[5]) if len(sys.argv) > 5 else len(targets)
out.mkdir(parents=True, exist_ok=False)
compilers, _, _ = load_trusted_compilers()
rows = []
for t in targets[:limit]:
    client = ScriptedClient(lambda s, p, i: "no change")
    agent = Stage1(client, kb)
    entry = Path(t["path"])
    root = Path(t["project_root"]) if t.get("project_root") else None
    store = ArtifactStore(out / t["unit_id"])
    if root:
        index = ProjectIndex(root)
        project = resolve_project(index.root, entry.resolve(), (), index)
        record = repair_unit(CompilationUnit(t["unit_id"], project.files), compilers, store, io.StringIO(),
                             project=project, project_index=index, agent=agent, group=str(root))
        files = [Path(f.path) for f in project.files]
    else:
        raw = entry.read_bytes()
        record = repair_unit(CompilationUnit(t["unit_id"], (SourceFile(str(entry), hashlib.sha256(raw).hexdigest(), raw),)),
                             compilers, store, io.StringIO(), agent=agent, group=str(entry))
        files = [entry]
    # Leak check: file names, directory names as path segments ("dir/"), the full path of
    # every input, and the comment texts of every input file. Directory names alone are
    # often ordinary words ("contracts", "base") that the documentation also uses.
    secrets = {p.name for p in files} | {p.parent.name + "/" for p in files} | {str(p) for p in files}
    for p in files:
        raw = p.read_bytes()
        comments = [m.group() for m in re.finditer(rb"//[^\r\n]{12,}|/\*[\s\S]{12,}?\*/", raw)]
        visible = [c for c in comments if blank_comments(c).strip()]  # inside strings: not comments
        secrets |= {c.decode("utf8", "replace").strip()[:60] for c in comments if c not in visible}
    leaks = sorted({s for s in secrets for prompt in client.prompts if s and s in prompt})
    rows.append(dict(unit_id=t["unit_id"], status=record.status, reason=record.reason, prompts=len(client.prompts),
                     prompt_chars=[len(p) for p in client.prompts], stopped=agent.stopped, leaks=leaks,
                     knowledge=sum(s.get("knowledge", []) != [] for s in json.loads(
                         (store.path / "units" / t["unit_id"] / "repair_steps.json").read_text())
                         if s.get("operation") == "stage1_round") if (store.path / "units" / t["unit_id"] /
                                                                       "repair_steps.json").exists() else 0))
    print(json.dumps(rows[-1])[:300], flush=True)
summary = dict(units=len(rows), with_prompts=sum(r["prompts"] > 0 for r in rows),
               leaking_units=[r["unit_id"] for r in rows if r["leaks"]],
               stopped={k: sum(r["stopped"] == k for r in rows) for k in sorted({str(r["stopped"]) for r in rows})},
               max_prompt_chars=max((max(r["prompt_chars"]) for r in rows if r["prompt_chars"]), default=0),
               rows=rows)
summary_path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf8")
print(json.dumps({k: v for k, v in summary.items() if k != "rows"}))
