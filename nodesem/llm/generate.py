"""LLM description stage: prompt units across tasks, cached llama.cpp generation, teacher rows.

Every function of every task becomes one or more prompt units (`prompts.produce`);
identical prompts are generated once. Responses are cached on disk by
`protocol.cache_key` (prompt + model file SHA-256 + decoding parameters), so a run
resumes, and a cache from an earlier run on the same sources is reused as is.
Units for functions without a body and without target lines are skipped.
"""
import hashlib
from collections import defaultdict
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


def generate(units, schedule, cache_dir, backend=None, model_cache=None, log=print,
             asset_sha=MODEL["sha256"], parameters=PARAMETERS, limit=None):
    """Generate every non-skipped unit (cached); returns {key: result}.

    ``limit`` generates at most that many new responses and returns only the
    results obtained so far (for smoke tests); teacher text then cannot be built.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results, pending = {}, [k for k in sorted(units) if not schedule[k]
                                and not (cache_dir / k / "response.json").exists()]
    if pending and backend is None:
        backend = LlamaBackend(model_path(model_cache), parameters)
    log("LLM units: %d, skipped %d, cached %d, to generate %d" % (
        len(units), sum(schedule.values()), len(units) - sum(schedule.values()) - len(pending), len(pending)))
    fresh = 0
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


def teacher_rows(rows, facts, units, results):
    """Aligned, checked teacher text per F3 row (absent where no faithful description exists)."""
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("cache_key")].append(row)
    output = {}
    for key, group in groups.items():
        if key is None:
            answer, _ = align(group, facts, dict(target_lines=[]), dict(parsed=None))
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
