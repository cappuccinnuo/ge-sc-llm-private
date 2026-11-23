"""LLM prompt protocol: system/user templates, output schema, response parsing, cache
keys (prompt + model file SHA-256 + decoding parameters) and the response cache.
"""
import hashlib
import json
import time
from pathlib import Path




# ----------------------------------------------------------------------
# node_sem/llm_protocol_v2
# NS-P7 immutable prompt contracts; standard library only, both environments.
VERSION = "nodesem-llm-v2"

ROLES = ("input_validation", "access_check", "state_read", "state_update",
         "value_transfer", "external_call", "computation", "event_emit", "control", "other")

SYSTEM = """You describe what Solidity code does. You never assess security.
Rules:
1. Describe behavior only: what each statement reads, writes, computes, calls or checks, and its role in the function.
2. Do not judge safety. Never use these words or their variants: vulnerability, vulnerable, reentrancy, reentrant, exploit, attack, attacker, unsafe, insecure, risk, risky, bug, flaw, overflow, underflow, malicious, dangerous, safe, secure.
3. Identifiers have been renamed (a1, a2, ...). Do not guess their original names.
4. If unsure, write "unknown".
5. Output JSON only, matching the schema exactly.
6. reads and writes list root identifiers only (for x[i] or x.f write x), plus environment values such as msg.sender or block.timestamp exactly as written. Identifiers used inside an index count as reads.
7. state_update means the statement writes one of the listed contract state variables. Assigning a local variable is computation.
8. A statement that sends ether (transfer, send, call with value) has role value_transfer and external true. A call to another contract has role external_call and external true. Calls to functions of the same contract are not external.
9. Return exactly one entry for every listed line, in the given order; do not describe lines that are not listed."""

SCHEMA_TEXT = '{"function_intent": "<= 25 words", "statements": [{"line": int, "role": one of [input_validation, access_check, state_read, state_update, value_transfer, external_call, computation, event_emit, control, other], "summary": "<= 20 words", "reads": [str], "writes": [str], "external": bool}]}'

USER = """{contract_header}
Contract state variables:
{state_vars}
Function:
{function_with_lines}
Describe the statements at these lines: {line_list}
Schema: """

TEMPLATES = ("describe_v2", "judge_v2")

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf8")).hexdigest()

def template(mode):
    if mode not in TEMPLATES:
        raise ValueError("Unknown LLM template")
    system, schema = SYSTEM, SCHEMA_TEXT
    if mode == "judge_v2":
        lines = system.splitlines()
        lines[0] = "You describe what Solidity code does and may note possible weaknesses."
        lines[3] = "2. You may add a short security_note (<= 20 words) describing possible weaknesses."
        system = "\n".join(lines)
        schema = schema.replace('"external": bool}', '"external": bool, "security_note": "<= 20 words"}')
    return dict(version=mode, system=system, user=USER, schema=schema)

def messages(unit, mode="describe_v2"):
    spec = template(mode)
    content = USER.format(contract_header=unit["contract_header"], state_vars=unit["state_vars"],
        function_with_lines=unit["function_with_lines"],
        line_list=", ".join(str(x) for x in unit["target_lines"])) + spec["schema"]
    return [dict(role="system", content=spec["system"]), dict(role="user", content=content)]

def cache_key(unit, asset_sha, parameters, mode="describe_v2"):
    return digest(dict(version=VERSION, template=template(mode), asset_sha256=asset_sha,
                       parameters=parameters, messages=messages(unit, mode)))

def output_schema(mode="describe_v2"):
    template(mode)
    properties = dict(line={"type": "integer"}, role={"type": "string", "enum": list(ROLES)},
        summary={"type": "string"}, reads={"type": "array", "items": {"type": "string"}},
        writes={"type": "array", "items": {"type": "string"}}, external={"type": "boolean"})
    if mode == "judge_v2":
        properties["security_note"] = {"type": "string"}
    return dict(type="object", additionalProperties=False, required=["function_intent", "statements"],
        properties=dict(function_intent={"type": "string"}, statements=dict(type="array", items=dict(
            type="object", additionalProperties=False, required=list(properties), properties=properties))))

def parse_response(text, mode="describe_v2"):
    """Strict types/shape; line vocabulary, roles and word limits are postprocessing."""
    template(mode)
    obj = json.loads(text)
    if not isinstance(obj, dict) or set(obj) != {"function_intent", "statements"}:
        raise ValueError("Response root schema differs")
    if not isinstance(obj["function_intent"], str) or not isinstance(obj["statements"], list):
        raise ValueError("Response root types differ")
    expected = {"line", "role", "summary", "reads", "writes", "external"}
    if mode == "judge_v2":
        expected.add("security_note")
    for item in obj["statements"]:
        if not isinstance(item, dict) or set(item) != expected:
            raise ValueError("Statement schema differs")
        if type(item["line"]) is not int or type(item["external"]) is not bool:
            raise ValueError("Line/external types differ")
        for key in ("role", "summary") + (("security_note",) if mode == "judge_v2" else ()):
            if not isinstance(item[key], str):
                raise ValueError("Statement string field differs")
        for key in ("reads", "writes"):
            if not isinstance(item[key], list) or not all(isinstance(x, str) for x in item[key]):
                raise ValueError("Statement variable list differs")
    return obj


# ----------------------------------------------------------------------
# node_sem/llm_cache_v2 (picked: read, reference, write, generate_cached)
def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def reference(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())

def write(path, value):
    with Path(path).open("x", encoding="utf8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

class ContextOverflow(ValueError):
    """The prompt alone does not fit the model's context window (raised by a backend)."""


def generate_cached(unit, backend, output, asset_sha, parameters, mode="describe_v2"):
    """Reuse sealed completed responses; an interrupted unit needs explicit recovery.

    A prompt longer than the context window can never be generated under the decoding
    contract; it is sealed once with status ``context_overflow`` and no response.
    """
    key = cache_key(unit, asset_sha, parameters, mode)
    if mode == "describe_v2" and unit.get("cache_key") != key:
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
            try:
                response = backend.generate(sent, output_schema(mode))
            except ContextOverflow as exc:
                attempts.append(dict(attempt=attempt, messages=sent, response=None, error=str(exc)))
                break
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
            parsed=parsed, status="ok" if parsed is not None else (
                "context_overflow" if attempts and attempts[-1].get("error") else "parse_failed"), cache_hit=False)
        write(result_path, result)
        write(result_path.with_suffix(".seal.json"), dict(response=reference(result_path)))
        return result
    except Exception as exc:
        write(directory / "failure.json", dict(error=repr(exc), elapsed_seconds=time.monotonic()-started))
        raise
