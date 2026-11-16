"""Per-task NodeSem feature store.

Layout (``root`` is usually ``data/nodesem``)::

    <root>/<dataset>/<category>/<task>/rows.jsonl        F3 row identities, in F3 order
                                      /facts.jsonl       statement facts per row
                                      /text.jsonl        CODE text per row
                                      /ctx.jsonl         CTX fields (original and masked names)
                                      /teacher.jsonl     teacher text and presence per row
                                      /features.npz      static, code, ctx, ctx_masked, teacher
                                      /summary.json
    <root>/llm_cache/<cache key>/response.json           LLM responses, shared by all tasks

Every matrix has one row per F3 row. Stages fill the store incrementally:
``analyze`` (rows, facts, text, ctx, static), ``encode`` (code, ctx, ctx_masked),
``describe`` (teacher text), ``encode --teacher`` (teacher vectors).
"""
import json
from pathlib import Path

import numpy as np

from nodesem.pipeline import IDENTITY

MATRICES = ("static", "code", "ctx", "ctx_masked", "teacher")


def task_dir(root, dataset, category, task):
    return Path(root) / dataset / category / task


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf8") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf8") as stream:
        return [json.loads(line) for line in stream]


class TaskStore:
    def __init__(self, root, dataset, category, task):
        self.path = task_dir(root, dataset, category, task)

    def exists(self, name):
        return (self.path / name).exists()

    def rows(self):
        return read_jsonl(self.path / "rows.jsonl")

    def matrices(self):
        if not (self.path / "features.npz").exists():
            return {}
        with np.load(self.path / "features.npz", allow_pickle=False) as archive:
            return {k: archive[k].copy() for k in archive.files}

    def put_matrices(self, **values):
        current = self.matrices()
        n = len(self.rows())
        for name, value in values.items():
            if name not in MATRICES and name != "teacher_present":
                raise ValueError("Unknown matrix " + name)
            value = np.asarray(value)
            if len(value) != n:
                raise ValueError("%s has %d rows, store has %d" % (name, len(value), n))
            current[name] = value
        tmp = self.path / "features.tmp.npz"
        np.savez_compressed(tmp, **current)
        tmp.replace(self.path / "features.npz")

    def write_analysis(self, analysis, summary):
        self.path.mkdir(parents=True, exist_ok=True)
        write_jsonl(self.path / "rows.jsonl", [{k: r[k] for k in IDENTITY} for r in analysis["text"]])
        write_jsonl(self.path / "text.jsonl", analysis["text"])
        write_jsonl(self.path / "facts.jsonl", analysis["facts"])
        write_jsonl(self.path / "ctx.jsonl", [dict(row_key=o["row_key"], original=o, masked=m)
                                             for o, m in zip(analysis["ctx"], analysis["ctx_masked"])])
        if (self.path / "features.npz").exists():
            (self.path / "features.npz").unlink()
        self.put_matrices(static=analysis["static"])
        self.write_summary(summary)

    def write_summary(self, update):
        path = self.path / "summary.json"
        current = json.loads(path.read_text()) if path.exists() else {}
        current.update(update)
        path.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")

    def summary(self):
        return json.loads((self.path / "summary.json").read_text())

    def modalities(self, ctx_view="original", student=None):
        """Modality tables for ``features.carry`` (CTX view per configuration)."""
        rows, matrices = self.rows(), self.matrices()
        identity = dict(row_keys=[r["row_key"] for r in rows], file=[r["file"] for r in rows],
                        node_type=[r["node_type"] for r in rows], code_sha256=[r["code_sha256"] for r in rows])
        everywhere = [True] * len(rows)
        out = {"static": dict(identity, values=matrices["static"].astype(np.float32), present=everywhere)}
        if "code" in matrices:
            out["code"] = dict(identity, values=matrices["code"].astype(np.float32), present=everywhere)
        ctx = "ctx" if ctx_view == "original" else "ctx_masked"
        if ctx in matrices:
            out["ctx"] = dict(identity, values=matrices[ctx].astype(np.float32), present=everywhere)
        if "teacher" in matrices:
            out["teacher"] = dict(identity, values=matrices["teacher"].astype(np.float32),
                                  present=[bool(x) for x in matrices["teacher_present"]])
        if student is not None:
            out["student"] = dict(identity, values=student.astype(np.float32), present=everywhere)
        return out
