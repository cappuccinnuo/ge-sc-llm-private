"""Pure file cache and one-format-retry contract shared by offline runtime and tests."""
import hashlib
import json
from pathlib import Path
import time
try:
    from .llm_protocol import VERSION, cache_key, messages, parse_response, output_schema
except ImportError:
    from llm_protocol import VERSION, cache_key, messages, parse_response, output_schema


def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def write(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def generate_cached(unit, backend, output, asset_sha, parameters, mode="describe_v1"):
    """Reuse sealed completed responses; an interrupted unit needs explicit recovery."""
    key = cache_key(unit, asset_sha, parameters, mode)
    if mode == "describe_v1" and unit.get("cache_key") != key:
        raise ValueError("Unit/cache identity differs")
    output = Path(output)
    result_path = output / key / "response.json"
    if result_path.exists():
        seal = read(result_path.with_suffix(".seal.json"))
        if seal["response"] != reference(result_path):
            raise ValueError("Cached response SHA differs")
        result = read(result_path)
        if result["cache_key"] != key or result["messages"] != messages(unit, mode):
            raise ValueError("Cached prompt differs")
        return dict(result, cache_hit=True)
    directory = output / key
    directory.mkdir(parents=True, exist_ok=False)
    prompt = messages(unit, mode)
    write(directory / "started.json", dict(cache_key=key, messages=prompt, parameters=parameters))
    started = time.monotonic()
    attempts, parsed = [], None
    try:
        for attempt in range(2):
            sent = [dict(m) for m in prompt]
            if attempt:
                sent[-1]["content"] += "\nReturn valid JSON only."
            response = backend.generate(sent, output_schema(mode))
            item = dict(attempt=attempt, messages=sent, response=response)
            try:
                parsed = parse_response(response["content"], mode)
                item["parse_error"] = None
            except (ValueError, TypeError) as exc:
                item["parse_error"] = str(exc)
            attempts.append(item)
            write(directory / ("attempt{}.json".format(attempt)), item)
            if parsed is not None:
                break
        result = dict(version=VERSION, cache_key=key, template=mode, messages=prompt,
            parameters=parameters, asset_sha256=asset_sha, backend_mode=backend.mode,
            elapsed_seconds=time.monotonic()-started, attempts=attempts,
            parsed=parsed, status="ok" if parsed is not None else "parse_failed", cache_hit=False)
        write(result_path, result)
        write(result_path.with_suffix(".seal.json"), dict(response=reference(result_path)))
        return result
    except Exception as exc:
        write(directory / "failure.json", dict(error=repr(exc), elapsed_seconds=time.monotonic()-started))
        raise

