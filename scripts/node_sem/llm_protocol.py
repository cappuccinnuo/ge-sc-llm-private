"""NS-P7 immutable prompt contracts; standard library only, both environments."""
import hashlib
import json

VERSION = "nodesem-llm-v1"
ROLES = ("input_validation", "access_check", "state_read", "state_update",
         "value_transfer", "external_call", "computation", "event_emit", "control", "other")
SYSTEM = """You describe what Solidity code does. You never assess security.
Rules:
1. Describe behavior only: what each statement reads, writes, computes, calls or checks, and its role in the function.
2. Do not judge safety. Never use these words or their variants: vulnerability, vulnerable, reentrancy, reentrant, exploit, attack, attacker, unsafe, insecure, risk, risky, bug, flaw, overflow, underflow, malicious, dangerous, safe, secure.
3. Identifiers have been renamed (a1, a2, ...). Do not guess their original names.
4. If unsure, write "unknown".
5. Output JSON only, matching the schema exactly."""
SCHEMA_TEXT = '{"function_intent": "<= 25 words", "statements": [{"line": int, "role": one of [input_validation, access_check, state_read, state_update, value_transfer, external_call, computation, event_emit, control, other], "summary": "<= 20 words", "reads": [str], "writes": [str], "external": bool}]}'
USER = """Contract state variables:
{state_vars}
Function:
{function_with_lines}
Describe the statements at these lines: {line_list}
Schema: """
TEMPLATES = ("describe_v1", "judge_v1")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf8")).hexdigest()


def template(mode):
    if mode not in TEMPLATES:
        raise ValueError("Unknown LLM template")
    system, schema = SYSTEM, SCHEMA_TEXT
    if mode == "judge_v1":
        lines = system.splitlines()
        lines[3] = "2. You may add a short security_note (<= 20 words) describing possible weaknesses."
        system = "\n".join(lines)
        schema = schema.replace('"external": bool}', '"external": bool, "security_note": "<= 20 words"}')
    return dict(version=mode, system=system, user=USER, schema=schema)


def messages(unit, mode="describe_v1"):
    spec = template(mode)
    content = USER.format(state_vars=unit["state_vars"],
        function_with_lines=unit["function_with_lines"],
        line_list=", ".join(str(x) for x in unit["target_lines"])) + spec["schema"]
    return [dict(role="system", content=spec["system"]), dict(role="user", content=content)]


def cache_key(unit, asset_sha, parameters, mode="describe_v1"):
    return digest(dict(version=VERSION, template=template(mode), asset_sha256=asset_sha,
                       parameters=parameters, messages=messages(unit, mode)))


def output_schema(mode="describe_v1"):
    template(mode)
    properties = dict(line={"type": "integer"}, role={"type": "string", "enum": list(ROLES)},
        summary={"type": "string"}, reads={"type": "array", "items": {"type": "string"}},
        writes={"type": "array", "items": {"type": "string"}}, external={"type": "boolean"})
    if mode == "judge_v1":
        properties["security_note"] = {"type": "string"}
    return dict(type="object", additionalProperties=False, required=["function_intent", "statements"],
        properties=dict(function_intent={"type": "string"}, statements=dict(type="array", items=dict(
            type="object", additionalProperties=False, required=list(properties), properties=properties))))


def parse_response(text, mode="describe_v1"):
    """Strict types/shape; line vocabulary, roles and word limits are postprocessing."""
    template(mode)
    obj = json.loads(text)
    if not isinstance(obj, dict) or set(obj) != {"function_intent", "statements"}:
        raise ValueError("Response root schema differs")
    if not isinstance(obj["function_intent"], str) or not isinstance(obj["statements"], list):
        raise ValueError("Response root types differ")
    expected = {"line", "role", "summary", "reads", "writes", "external"}
    if mode == "judge_v1":
        expected.add("security_note")
    for item in obj["statements"]:
        if not isinstance(item, dict) or set(item) != expected:
            raise ValueError("Statement schema differs")
        if type(item["line"]) is not int or type(item["external"]) is not bool:
            raise ValueError("Line/external types differ")
        for key in ("role", "summary") + (("security_note",) if mode == "judge_v1" else ()):
            if not isinstance(item[key], str):
                raise ValueError("Statement string field differs")
        for key in ("reads", "writes"):
            if not isinstance(item[key], list) or not all(isinstance(x, str) for x in item[key]):
                raise ValueError("Statement variable list differs")
    return obj
