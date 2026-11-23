"""LLM description stage: prompt units across tasks, cached llama.cpp generation, teacher rows.

Every function of every task becomes one or more prompt units (`prompts.produce`);
identical prompts are generated once. Responses are cached on disk by
`protocol.cache_key` (prompt + model file SHA-256 + decoding parameters), so a run
resumes, and a cache from an earlier run on the same sources is reused as is.
Units for functions without a body and without target lines are skipped.

Interruption: a sealed response (``response.json`` + its seal) is final. A unit cut
off mid-generation leaves only ``started.json``/``attempt*.json``; the next run moves
that directory to ``<cache>/_interrupted/`` and generates the unit again from scratch,
so nothing partial is ever used. A lock file keeps two runs off one cache.

Parallel workers (``workers`` > 1): each worker process loads its own copy of the model
and generates a fixed share of the pending units (by cache key). A unit's prompt and
decoding contract do not depend on the worker, so the cache is the same as with one
process; the parent then reads every response from the cache. One 3B Q4 worker needs
about 3 GB of GPU memory.
"""
import hashlib
import json
import multiprocessing
import os
import shutil
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from nodesem.llm.checks import BLACKLIST
from nodesem.llm.post import align
from nodesem.llm.prompts import body_status, produce, skip_no_body
from nodesem.llm.protocol import cache_key, digest, generate_cached, messages, read
from nodesem.llm.teacher import present_row, teacher_text

MODEL = dict(repo_id="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF", revision="f74adce6aa16316c625447af059dbebe4983757c",
             filename="qwen2.5-coder-3b-instruct-q4_k_m.gguf", bytes=2104932800,
             sha256="724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7")
PARAMETERS = dict(n_ctx=4096, n_gpu_layers=-1, n_batch=128, n_threads=4,
                  temperature=0.0, top_k=1, seed=0, max_tokens=2048, repeat_penalty=1.0)
PROMPT_FIELDS = ("contract_header", "state_vars", "function_with_lines", "target_lines")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def model_path(cache_dir=None):
    """Download (once) the pinned GGUF and verify its size and SHA-256."""
    from hcg.sources.models import ensure
    path = ensure(MODEL["repo_id"], MODEL["revision"], cache_dir) / MODEL["filename"]
    if path.stat().st_size != MODEL["bytes"] or sha256_file(path) != MODEL["sha256"]:
        raise ValueError("Downloaded GGUF differs from the pinned model")
    return path


class LlamaBackend:
    """Greedy, JSON-schema-constrained chat completion with llama-cpp-python."""

    def __init__(self, path, parameters=PARAMETERS):
        from llama_cpp import Llama
        self.parameters = parameters
        self.mode = "gpu" if parameters["n_gpu_layers"] != 0 else "cpu"
        self.model = Llama(model_path=str(path), verbose=False,
                           **{k: parameters[k] for k in ("n_ctx", "n_gpu_layers", "n_batch", "n_threads", "seed")})

    def generate(self, prompt, schema):
        import time
        start = time.monotonic()
        result = self.model.create_chat_completion(
            messages=prompt, response_format={"type": "json_object", "schema": schema},
            **{k: self.parameters[k] for k in ("temperature", "top_k", "seed", "max_tokens", "repeat_penalty")})
        return dict(content=result["choices"][0]["message"]["content"],
                    finish_reason=result["choices"][0]["finish_reason"], usage=result["usage"],
                    elapsed_seconds=time.monotonic() - start)


def plan_units(task_inputs, asset_sha=MODEL["sha256"], parameters=PARAMETERS):
    """[(context, analysis)] -> (units by key, rows by task, schedule) for generation."""
    units, rows_by_task, body = {}, {}, {}
    for context, analysis in task_inputs:
        functions, rows = produce(context["task_id"], context["graphs"]["F3"], context["source_text"],
                                  analysis["text"], analysis["facts"])
        keys = {}
        for fn in functions:
            has_body = body_status(fn["restoration"]["original"])
            if body.setdefault(fn["function_id"], has_body) != has_body:
                raise ValueError("Conflicting body evidence")
            for segment in fn["segments"]:
                prompt = {k: segment[k] for k in PROMPT_FIELDS}
                key = cache_key(prompt, asset_sha, parameters)
                keys[(fn["function_id"], segment["segment"])] = key
                unit = units.setdefault(key, dict(prompt, cache_key=key, messages=messages(prompt),
                                                  prompt_sha256=digest(messages(prompt)), occurrences=[]))
                unit["occurrences"].append(dict(task_id=context["task_id"], function_id=fn["function_id"],
                                                file=fn["file"], segment=segment["segment"]))
        for row in rows:
            if row["function_id"] is not None:
                row["cache_key"] = keys[(row["function_id"], row["segment"])]
        rows_by_task[context["task_id"]] = rows
    schedule = {}
    for key, unit in sorted(units.items()):
        states = {body[o["function_id"]] for o in unit["occurrences"]}
        if len(states) != 1:
            raise ValueError("Deduplicated prompt has conflicting body presence")
        schedule[key] = skip_no_body(states.pop(), unit["target_lines"])
    return units, rows_by_task, schedule


def pending_units(units, schedule, cache_dir):
    """Keys still to generate, in key order."""
    return [k for k in sorted(units) if not schedule[k] and not (Path(cache_dir) / k / "response.json").exists()]


def recover_interrupted(keys, cache_dir, log=print):
    """Move directories of units cut off mid-generation to ``_interrupted/``; return their keys."""
    moved = []
    for key in keys:
        directory = Path(cache_dir) / key
        if directory.is_dir() and not (directory / "response.json").exists():
            target = Path(cache_dir) / "_interrupted" / ("%s.%d" % (key, time.time_ns()))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(directory), str(target))
            moved.append(key)
    if moved:
        log("moved %d interrupted unit(s) to %s; they are generated again" % (len(moved), Path(cache_dir) / "_interrupted"))
    return moved


@contextmanager
def cache_lock(cache_dir):
    """One describe run per cache at a time (a stale lock of a dead process is taken over)."""
    path = Path(cache_dir) / ".lock"
    if path.exists():
        pid = int(json.loads(path.read_text())["pid"])
        try:
            os.kill(pid, 0)
            alive = pid != os.getpid()
        except ProcessLookupError:
            alive = False
        except PermissionError:
            alive = True
        if alive:
            raise RuntimeError("another describe run (pid %d) uses %s; if none is running, delete %s"
                               % (pid, cache_dir, path))
    path.write_text(json.dumps(dict(pid=os.getpid())))
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def share(keys, worker, workers):
    """The worker's fixed share of the pending keys."""
    return [k for k in keys if int(k[:8], 16) % workers == worker]


def _worker(args):
    """Generate one share in a fresh process (own model instance); returns (worker, count)."""
    worker, workers, keys, units, cache_dir, model_cache, asset_sha, parameters, backend_factory = args
    backend = backend_factory() if backend_factory else LlamaBackend(model_path(model_cache), parameters)
    mine = share(keys, worker, workers)
    started = time.monotonic()
    for i, key in enumerate(mine, 1):
        generate_cached(units[key], backend, cache_dir, asset_sha, parameters)
        if i % 50 == 0 or i == len(mine):
            rate = i / max(time.monotonic() - started, 1e-9) * 60
            print("  worker %d: %d/%d (%.1f/min)" % (worker, i, len(mine), rate), flush=True)
    return worker, len(mine)


def generate(units, schedule, cache_dir, backend=None, model_cache=None, log=print,
             asset_sha=MODEL["sha256"], parameters=PARAMETERS, limit=None, workers=1, backend_factory=None):
    """Generate every non-skipped unit (cached); returns {key: result}.

    ``limit`` generates at most that many new responses and returns only the results
    obtained so far (smoke tests). ``workers`` > 1 generates the pending units in that
    many processes first (``backend_factory``, a picklable callable, replaces the
    llama.cpp backend in tests).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with cache_lock(cache_dir):
        pending = pending_units(units, schedule, cache_dir)
        recover_interrupted(pending, cache_dir, log)
        log("LLM units: %d, skipped %d, cached %d, to generate %d" % (
            len(units), sum(schedule.values()), len(units) - sum(schedule.values()) - len(pending), len(pending)))
        if workers > 1 and pending and limit is None:
            jobs = [(w, workers, pending, {k: units[k] for k in share(pending, w, workers)}, cache_dir, model_cache,
                     asset_sha, parameters, backend_factory) for w in range(workers)]
            with multiprocessing.get_context("spawn").Pool(workers) as pool:
                for worker, count in pool.imap_unordered(_worker, jobs):
                    log("  worker %d finished %d units" % (worker, count))
            pending = pending_units(units, schedule, cache_dir)
            if pending:
                raise RuntimeError("%d units still missing after the workers finished" % len(pending))
        if pending and backend is None:
            backend = backend_factory() if backend_factory else LlamaBackend(model_path(model_cache), parameters)
        results, fresh = {}, 0
        for i, key in enumerate(sorted(units)):
            if limit is not None and fresh >= limit:
                break
            if schedule[key]:
                results[key] = dict(status="skipped_no_body", cache_key=key)
                continue
            result = generate_cached(units[key], backend, cache_dir, asset_sha, parameters)
            if result["parameters"] != parameters or result["asset_sha256"] != asset_sha:
                raise ValueError("Cached response was produced under another model or decoding contract")
            results[key] = dict(status=result["status"], cache_key=key, parsed=result["parsed"])
            fresh += not result["cache_hit"]
            if not result["cache_hit"] and i % 50 == 0:
                log("  generated %d/%d" % (i + 1, len(units)))
    return results


def teacher_rows(rows, facts, units, results, partial=False):
    """Aligned, checked teacher text per F3 row (absent where no faithful description exists).

    ``partial`` (smoke runs with a generation limit): rows of units not generated yet
    are absent, flagged ``not_generated``.
    """
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("cache_key")].append(row)
    output = {}
    for key, group in groups.items():
        if key is None:
            answer, _ = align(group, facts, dict(target_lines=[]), dict(parsed=None))
        elif key not in results and partial:
            answer, _ = align(group, facts, units[key], dict(parsed=None))
            for item in answer:
                item["flags"] = ["not_generated"]
        else:
            result = results[key]
            response = dict(parsed=None) if result["status"] == "skipped_no_body" else dict(parsed=result["parsed"])
            answer, _ = align(group, facts, units[key], response)
            if result["status"] == "skipped_no_body":
                for item in answer:
                    item["flags"] = ["skipped_no_body"]
        for item in answer:
            item = present_row(item)
            item["text"] = teacher_text(item)
            item["text_sha256"] = hashlib.sha256(item["text"].encode("utf8")).hexdigest()
            if item["present"] and BLACKLIST.search(item["text"]):
                raise AssertionError("Teacher blacklist escaped presence policy")
            if item["row_key"] in output:
                raise ValueError("Duplicate post row")
            output[item["row_key"]] = item
    if set(output) != set(facts):
        raise ValueError("Teacher/facts row population differs")
    return [output[r["row_key"]] for r in rows]


def cached_result(cache_dir, key):
    """A previously generated response (for reuse checks and tests)."""
    return read(Path(cache_dir) / key / "response.json")
