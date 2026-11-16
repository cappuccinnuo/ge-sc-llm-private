"""TODO docstring."""
import re
import statistics
from collections import Counter

from nodesem.llm.protocol import ROLES




# ----------------------------------------------------------------------
# node_sem/llm_post
# NS-P7 response alignment and conservative evidence checks; no new AST facts.
BLACKLIST = re.compile(
    r"\b(?:vulnerabilit\w*|vulnerabl\w*|reentran\w*|exploit\w*|attack\w*|"
    r"unsafe\w*|insecur\w*|risk\w*|bug\w*|flaw\w*|overflow\w*|underflow\w*|"
    r"malicious\w*|dangerous\w*|safe\w*|secur\w*)\b", re.I)

IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")

def restore_name(text, mapping):
    return IDENTIFIER.sub(lambda m: mapping.get(m.group(0), m.group(0)), text.strip())

def jaccard(predicted, expected):
    # Match members to an explicitly supplied root, but never equate msg.sender
    # and msg.value just because both have the root msg. Each item matches once.
    predicted = sorted({v.strip() for v in predicted if v.strip()})
    expected = sorted({v.strip() for v in expected if v.strip()})
    if not predicted and not expected:
        return 1.0
    assigned = {}
    def place(i, visited):
        choices = sorted(range(len(expected)), key=lambda j: predicted[i] != expected[j])
        for j in choices:
            p, e = predicted[i], expected[j]
            agrees = p == e or p == e.split(".", 1)[0] or e == p.split(".", 1)[0]
            if not agrees or j in visited:
                continue
            visited.add(j)
            if j not in assigned or place(assigned[j], visited):
                assigned[j] = i
                return True
        return False
    matches = sum(place(i, set()) for i in range(len(predicted)))
    return matches / (len(predicted) + len(expected) - matches)

def fact_sets(facts):
    if (facts["dfg"].get("status") != "supported"
            or facts["state"].get("status") != "supported"):
        return None
    reads = {x["var"] for x in facts["dfg"]["uses"]} | {x["var"] for x in facts["state"]["reads"]}
    reads.update(facts["env"].get("keys", []))
    writes = {x["var"] for x in facts["dfg"]["defs"]} | {x["var"] for x in facts["state"]["writes"]}
    return reads, writes, bool(facts["external"].get("kinds"))

def faithfulness(statement, facts, mapping):
    expected = fact_sets(facts)
    if expected is None:
        return None, None
    reads, writes, external = expected
    components = dict(reads=jaccard([restore_name(x, mapping) for x in statement["reads"]], reads),
        writes=jaccard([restore_name(x, mapping) for x in statement["writes"]], writes),
        external=float(statement["external"] == external))
    return sum(components.values()) / 3.0, components

def clean_response(parsed, target_lines, mode):
    """Keep first duplicate, discard out-of-target lines, preserve all audit flags."""
    if parsed is None:
        return None, {}, {"parse_failed": 1}
    totals = Counter()
    intent = parsed["function_intent"].strip()
    intent_flags = []
    if mode == "describe_v1" and BLACKLIST.search(intent):
        intent_flags.append("intent_blacklist")
        totals["intent_blacklist"] += 1
        intent = ""
    if len(intent.split()) > 25:
        intent_flags.append("intent_word_limit")
        totals["intent_word_limit"] += 1
        intent = ""
    selected = {}
    for raw in parsed["statements"]:
        line = raw["line"]
        if line not in target_lines:
            totals["invalid_line"] += 1
            continue
        if line in selected:
            totals["duplicate_line"] += 1
            continue
        item = dict(raw, flags=list(intent_flags), intent=intent)
        if item["role"] not in ROLES:
            item["flags"].append("role_normalized")
            item["role"] = "other"
        summary = item["summary"].strip()
        if mode == "describe_v1" and BLACKLIST.search(summary):
            totals["summary_blacklist"] += 1
            item["flags"].append("summary_blacklist")
            summary = ""
        if len(summary.split()) > 20:
            item["flags"].append("summary_word_limit")
            summary = ""
        item["summary"] = summary
        selected[line] = item
    return dict(intent=intent, flags=intent_flags), selected, dict(totals)

def align(rows, facts_by_key, unit, result, mode="describe_v1"):
    """One cache response -> all requested HCG identities; no positional CSV join."""
    fn, statements, counts = clean_response(result["parsed"], set(unit["target_lines"]), mode)
    output = []
    for row in rows:
        kind = row["target_kind"]
        base = {k: row[k] for k in ("row_key", "file", "node_type", "source_sha256", "code_sha256")}
        item = dict(base, role="", summary="", intent="", faithfulness=None,
            present=False, target_kind=kind, flags=[], cache_key=row.get("cache_key"))
        if kind == "excluded":
            item["flags"].append("excluded")
        elif fn is None:
            item["flags"].append("parse_failed")
        elif kind == "function":
            item.update(intent=fn["intent"], flags=fn["flags"], present=bool(fn["intent"]))
        else:
            statement = statements.get(row["relative_line"])
            if statement is None:
                item["flags"].append("missing")
            else:
                score, components = faithfulness(statement, facts_by_key[row["row_key"]], row["prompt_map"])
                item.update(role=statement["role"], summary=statement["summary"],
                    intent=statement["intent"], flags=list(statement["flags"]),
                    faithfulness=score, components=components,
                    predicted_reads=statement["reads"], predicted_writes=statement["writes"],
                    predicted_external=statement["external"])
                if mode == "judge_v1":
                    item["security_note"] = statement["security_note"]
                if score is None:
                    item["flags"].append("facts_unknown")
                elif score < .5:
                    item["flags"].append("unfaithful")
                item["present"] = score is not None and score >= .5 and bool(item["summary"])
        output.append(item)
    return output, counts

def teacher_text(row):
    if not row["present"]:
        return ""
    if row["target_kind"] == "function":
        return "function: " + row["intent"]
    return "role: {}. {}. function: {}".format(row["role"], row["summary"], row["intent"])

def role_agreement(rows, facts):
    result = {}
    for role in ("external_call", "state_update", "access_check"):
        available, truth = [], []
        for row in rows:
            f = facts[row["row_key"]]
            if role == "external_call":
                known = bool(f["external"])
                yes = bool(f["external"].get("kinds"))
            elif role == "state_update":
                known = f["state"].get("status") == "supported"
                yes = bool(f["state"].get("writes"))
            else:
                known = f["guard_status"] != "unknown"
                # Existing guard facts only; this is a diagnostic, not the gate.
                yes = any(g["is_sender_guard"] for g in f["guards"])
            available.append(known)
            truth.append(yes)
        predicted = [r["role"] == role for r in rows]
        claimed = sum(p and a for p, a in zip(predicted, available))
        tp = sum(p and a and t for p, a, t in zip(predicted, available, truth))
        actual = sum(a and t for a, t in zip(available, truth))
        result[role] = dict(claimed_verifiable=claimed, correct=tp, facts_positive=actual,
            precision=tp/claimed if claimed else None, recall=tp/actual if actual else None,
            facts_unknown=sum(not a for a in available),
            claimed_unknown=sum(p and not a for p, a in zip(predicted, available)),
            missing=sum("missing" in r["flags"] or "parse_failed" in r["flags"] for r in rows))
    return result

def gates(rows, results, agreement):
    statement_rows = [r for r in rows if r["target_kind"] == "statement"]
    scores = [r["faithfulness"] for r in statement_rows if r["faithfulness"] is not None]
    n = len(statement_rows)
    parse_rate = sum(r["status"] == "ok" for r in results)/len(results) if results else 0.0
    fraction = sum(r["faithfulness"] is not None and r["faithfulness"] >= .5 for r in statement_rows)/n if n else 0.0
    blacklist = sum(any("blacklist" in f for f in r["flags"]) for r in statement_rows)/n if n else 1.0
    median = statistics.median(scores) if scores else None
    checks = dict(parse_success=parse_rate >= .95, median_faithfulness=median is not None and median >= .7,
        faithfulness_ge_half=fraction >= .8, blacklist=blacklist <= .05)
    for role in ("external_call", "state_update"):
        p = agreement[role]["precision"]
        checks[role] = p is not None and p >= .8
    return dict(passed=all(checks.values()), checks=checks, parse_success_rate=parse_rate,
        statement_nodes=n, verifiable_nodes=len(scores), verifiable_fraction=len(scores)/n if n else 0,
        faithfulness_median=median, faithfulness_ge_half_fraction=fraction, blacklist_fraction=blacklist,
        unknown_in_ge_half_denominator=True)
