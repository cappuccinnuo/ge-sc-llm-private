"""NS-P7b root-path evidence comparison. Old llm_post and facts remain immutable."""
from collections import Counter
import re
from . import llm_post as v1
from .llm_role_review import own_sender_condition

# Frozen L3 aliases, not new environment analysis. Keep environment values
# atomic: msg.sender and msg.value must never collapse to the same root.
ENV = re.compile(r"(?:address\s*\(\s*this\s*\)\s*\.\s*balance|"
    r"(?:msg\s*\.\s*(?:sender|value|data|sig|gas)|tx\s*\.\s*(?:origin|gasprice)|"
    r"block\s*\.\s*[A-Za-z_$][\w$]*|this\s*\.\s*balance)|now|gasleft|blockhash)(?![\w$])")
NAME = re.compile(r"[A-Za-z_$][\w$]*")
LITERAL = re.compile(r"""(?:0x[0-9a-fA-F]+|\d+(?:\.\d+)?|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")""")
ALIASES = {"now":"block.timestamp","msg.gas":"gasleft",
           "address(this).balance":"this.balance","block.blockhash":"blockhash"}
RESERVED_ATOMS = {"true","false","this"}

def _close(text, start, left="[", right="]"):
    depth, i = 1, start + 1
    while i < len(text):
        literal = LITERAL.match(text, i)
        if literal:
            i = literal.end(); continue
        if text[i] == left: depth += 1
        elif text[i] == right:
            depth -= 1
            if not depth: return i
        i += 1
    raise ValueError("Unbalanced variable path")

def _head(text, start=0):
    env = ENV.match(text, start)
    if env:
        spelling = re.sub(r"\s+", "", env.group())
        return ALIASES.get(spelling, spelling), env.end()
    name = NAME.match(text, start)
    if name: return name.group(), name.end()
    return None, start

def index_reads(text):
    """Lexical index operands; skip literals, member names and call/type names."""
    reads, i = set(), 0
    while i < len(text):
        literal = LITERAL.match(text,i)
        if literal: i=literal.end(); continue
        root, end = _head(text,i)
        if root is None: i+=1; continue
        tail=end
        while tail<len(text) and text[tail].isspace():tail+=1
        # A user function/type name is not a variable value; its args are scanned.
        if root not in RESERVED_ATOMS and not (tail<len(text) and text[tail]=="(" and root not in {"gasleft","blockhash"}):
            reads.add(root)
        i=end
        while True:
            m=re.match(r"\s*\.\s*[A-Za-z_$][\w$]*",text[i:])
            if not m:break
            i+=m.end()
    return reads

def path(value):
    """Return root and reads inside subscripts; preserve malformed/opaque claims."""
    text=value.strip()
    if not text:return None,set()
    root,i=_head(text)
    if root is None:return text,set()
    extra=set()
    try:
        while i<len(text):
            if text[i].isspace():i+=1;continue
            if text[i]=="[":
                end=_close(text,i);extra.update(index_reads(text[i+1:end]));i=end+1
            elif text[i]==".":
                m=re.match(r"\.\s*[A-Za-z_$][\w$]*",text[i:])
                if not m:return text,set()
                i+=m.end()
            elif text[i]=="(" and root in {"gasleft","blockhash"}:
                end=_close(text,i,"(",")")
                extra.update(index_reads(text[i+1:end]));i=end+1
            else:return text,set()
    except ValueError:
        return text,set()
    return root,extra

def normalize(reads,writes):
    rr,ww=set(),set()
    for collection,dest in ((reads,rr),(writes,ww)):
        for value in collection:
            root,indices=path(value)
            if root:dest.add(root)
            rr.update(indices)
    return rr,ww

def jaccard(a,b):
    a,b=set(a),set(b)
    return len(a&b)/len(a|b) if a or b else 1.0

def fact_sets(facts):
    raw=v1.fact_sets(facts)
    if raw is None:return None
    reads,writes,external=raw
    reads,writes=normalize(reads,writes)
    return reads,writes,external

def faithfulness(statement,facts,mapping):
    expected=fact_sets(facts)
    if expected is None:return None,None
    rr,ww=normalize([v1.restore_name(x,mapping) for x in statement["reads"]],
                    [v1.restore_name(x,mapping) for x in statement["writes"]])
    er,ew,external=expected
    comp=dict(reads=jaccard(rr,er),writes=jaccard(ww,ew),
              external=float(statement["external"]==external))
    return sum(comp.values())/3.0,comp

def clean_response(parsed,target_lines,mode):
    if mode not in ("describe_v1","judge_v1","describe_v2","judge_v2"):
        raise ValueError("Unknown template mode")
    return v1.clean_response(parsed,target_lines,"judge_v1" if mode.startswith("judge") else "describe_v1")

def agreement_one(rows,truths,predicted):
    claimed=sum(p and t is not None for p,t in zip(predicted,truths))
    tp=sum(p and t is True for p,t in zip(predicted,truths))
    actual=sum(t is True for t in truths)
    return dict(claimed_verifiable=claimed,correct=tp,facts_positive=actual,
        precision=tp/claimed if claimed else None,recall=tp/actual if actual else None,
        facts_unknown=sum(t is None for t in truths),
        claimed_unknown=sum(p and t is None for p,t in zip(predicted,truths)),
        missing=sum("missing" in r["flags"] or "parse_failed" in r["flags"] for r in rows))

def role_agreement(rows,facts):
    external=[bool(facts[r["row_key"]]["external"].get("kinds"))
              if facts[r["row_key"]]["external"] else None for r in rows]
    state=[bool(facts[r["row_key"]]["state"].get("writes"))
           if facts[r["row_key"]]["state"].get("status")=="supported" else None for r in rows]
    access=[own_sender_condition(facts[r["row_key"]]) for r in rows]
    return dict(
        external_call=agreement_one(rows,external,[r.get("predicted_external") is True for r in rows]),
        external_role=agreement_one(rows,external,[r["role"] in {"external_call","value_transfer"} for r in rows]),
        state_update=agreement_one(rows,state,[r["role"]=="state_update" for r in rows]),
        access_check=agreement_one(rows,access,[r["role"]=="access_check" for r in rows]))

def gates(rows,results,agreement):
    return v1.gates(rows,results,agreement)

def teacher_text(row,mode="describe_v2"):
    if not row["present"]:return ""
    if row["target_kind"]=="function":return "function: "+row["intent"]
    if mode=="judge_v2":
        return "role: {}. {}. note: {}. function: {}".format(row["role"],row["summary"],row["security_note"],row["intent"])
    return v1.teacher_text(row)

# Alignment copied from llm_post.py SHA256 e889c57f2d74d32c93ba1daf5d40372b649f609a930cb31c045805474ac0e44b; only mode dispatch changes.
def align(rows, facts_by_key, unit, result, mode="describe_v2"):
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
                if mode.startswith("judge"):
                    item["security_note"] = statement["security_note"]
                if score is None:
                    item["flags"].append("facts_unknown")
                elif score < .5:
                    item["flags"].append("unfaithful")
                item["present"] = score is not None and score >= .5 and bool(item["summary"])
        output.append(item)
    return output, counts

