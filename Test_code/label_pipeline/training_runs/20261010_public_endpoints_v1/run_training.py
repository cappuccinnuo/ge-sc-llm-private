"""Run four isolated training jobs on the newly labeled local graphs.
Created by Codex, 2026-10-10. Existing training code and input graphs are read-only.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = Path("/home/zhao/SmartContract/ge-sc-llm")
RUN = Path(__file__).resolve().parent
PYTHON = "/home/zhao/miniconda3/envs/mando/bin/python"

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json(name, obj):
    p = RUN / name
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)

def build_jobs():
    jobs = []
    for category in ("reentrancy", "access_control"):
        base = REPO / "Test_code/label_pipeline/artifacts" / ("local_" + category + "_endpoints_v1") / category
        sources = REPO / "experiments/ge-sc-data/source_code" / category / "source_files"
        if not sources.is_dir():
            raise FileNotFoundError(str(sources))
        for task, folds, entry in (("contractlevel", 5, "graph_classifier.py"), ("linelevel", 10, "node_classifier.py")):
            name = category + "_" + task
            model = RUN / "models" / name / (category + "_hgt.pth")
            graph = base / (task + ".gpickle")
            labels = base / "graph_labels.json"
            args = [PYTHON, "-u", "-B", str(REPO / entry),
                    "--compressed_graph", str(graph), "--bug_type", category,
                    "--dataset", str(sources), "--testset", str(sources),
                    "--node_feature", "inside_token",
                    "--output_models", str(model), "--log_dir", str(RUN / "tensorboard" / name),
                    "--num_epochs", "50", "--k_folds", str(folds),
                    "--patience", "7", "--seed", "1", "--verbose_epochs", "--no_progress"]
            if task == "contractlevel":
                args += ["--label", str(labels)]
            else:
                args += ["--split_by", "contract"]
            jobs.append(dict(name=name, category=category, task=task, folds=folds,
                             command=args, graph=str(graph), graph_sha256=sha(graph),
                             label_manifest=str(labels), label_sha256=sha(labels),
                             output_model=str(model), log=str(RUN / "logs" / (name + ".log"))))
    return jobs

def summarize(job):
    content = Path(job["log"]).read_text(encoding="utf-8")
    def metric(name):
        values = re.findall(r"Average " + name + r" F1 score of folds:\s*([0-9.]+)", content)
        if len(values) != 1:
            raise RuntimeError("Expected exactly one " + name + " summary")
        value = float(values[0])
        if not math.isfinite(value):
            raise RuntimeError("Non-finite metric")
        return value
    model = Path(job["output_model"])
    selections = []
    for fold in range(job["folds"]):
        folder = model.parent / (model.stem + "_fold" + str(fold))
        sel = json.loads((folder / "selection.json").read_text())
        if set(sel["train_files"]) & set(sel["val_files"]):
            raise RuntimeError("Contract overlap in fold " + str(fold))
        for kind in ("best.pt", "last.pt"):
            path = folder / kind
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError("Missing checkpoint " + str(path))
        selections.append(sel)
    row = dict(category=job["category"], task=job["task"], folds=job["folds"],
               buggy_f1_percent=metric("Buggy"), macro_f1_percent=metric("Macro"),
               wall_seconds=job["wall_seconds"], log=job["log"],
               graph=job["graph"], graph_sha256=job["graph_sha256"],
               best_epochs_zero_based=[s["best_epoch"] for s in selections],
               last_epochs_zero_based=[s["last_epoch"] for s in selections],
               fold_buggy_f1_percent=[100 * s["best_val_buggy_f1"] for s in selections],
               fold_macro_f1_percent=[100 * s["best_val_macro_f1"] for s in selections])
    for label, key in (("buggy", "Buggy"), ("macro", "Macro")):
        avg = sum(row["fold_" + label + "_f1_percent"]) / job["folds"]
        if abs(avg - row[label + "_f1_percent"]) > 0.001:
            raise RuntimeError("Checkpoint metadata and final metric disagree: " + key)
    match = re.search(r"validation nodes whose exact \(code, label\) pair was in their training fold: (\d+)/(\d+) \(([0-9.]+)%\)", content)
    if match:
        row["exact_code_label_overlap"] = dict(nodes=int(match[1]), total=int(match[2]), percent=float(match[3]))
    return row

def main():
    if (RUN / "run_manifest.json").exists():
        raise RuntimeError("This run already exists; use a new directory to avoid overwriting results")
    (RUN / "logs").mkdir()
    jobs = build_jobs()
    code_paths = [REPO / "graph_classifier.py", REPO / "node_classifier.py"]
    code_paths += sorted((REPO / "sco_models").rglob("*.py"))
    code_hashes = {str(p.relative_to(REPO)): sha(p) for p in code_paths}
    state = dict(created_by="Codex", started_at=now(), status="running", pid=os.getpid(),
                 settings=dict(max_epochs=50, patience=7, seed=1, node_feature="inside_token",
                               input_width=512, split_unit="contract", best_selection="minimum validation loss",
                               evaluation="mean validation-fold F1 after restoring best checkpoint; not independent test"),
                 code_sha256=code_hashes, jobs=jobs, results=[])
    write_json("run_manifest.json", state)
    (RUN / "commands.sh").write_text("# Generated by Codex. Exact commands used for this run.\ncd " + shlex.quote(str(REPO)) + "\n\n" +
        "\n\n".join(" ".join(shlex.quote(x) for x in j["command"]) for j in jobs) + "\n")
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1")
    for job in jobs:
        start = time.monotonic()
        job.update(status="running", started_at=now())
        write_json("run_manifest.json", state)
        print("START " + job["name"] + " LOG=" + job["log"], flush=True)
        with Path(job["log"]).open("w", buffering=1, encoding="utf-8") as log:
            log.write("COMMAND: " + " ".join(shlex.quote(x) for x in job["command"]) + "\n")
            proc = subprocess.Popen(job["command"], cwd=str(REPO), env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, bufsize=1)
            job["pid"] = proc.pid
            write_json("run_manifest.json", state)
            for line in proc.stdout:
                log.write(line)
                if any(s in line for s in ("Start training fold", "restore best epoch", "Average ", "Traceback", "Error:", "Split mode:")):
                    print(job["name"] + ": " + line.rstrip(), flush=True)
            code = proc.wait()
        job.update(exit_code=code, wall_seconds=round(time.monotonic()-start, 2), ended_at=now())
        try:
            if code:
                raise RuntimeError("Training exited with code " + str(code))
            result = summarize(job)
            for path, expected in ((job["graph"], job["graph_sha256"]), (job["label_manifest"], job["label_sha256"])):
                if sha(path) != expected:
                    raise RuntimeError("Input changed during training: " + path)
            job["status"] = "complete"
            state["results"].append(result)
            write_json("summary.json", state["results"])
            with (RUN / "summary.csv").open("w", newline="") as f:
                keys = ["category", "task", "folds", "buggy_f1_percent", "macro_f1_percent", "wall_seconds"]
                writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(state["results"])
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = repr(exc)
            print("FAILED " + job["name"] + ": " + repr(exc), flush=True)
        write_json("run_manifest.json", state)
    changed = [p for p, old in code_hashes.items() if sha(REPO / p) != old]
    state.update(status="complete" if all(j["status"]=="complete" for j in jobs) and not changed else "incomplete",
                 ended_at=now(), changed_training_files=changed)
    write_json("run_manifest.json", state)
    print("FINISHED " + state["status"], flush=True)
    print(json.dumps(state["results"], indent=2), flush=True)
    return 0 if state["status"] == "complete" else 1

if __name__ == "__main__":
    sys.exit(main())
