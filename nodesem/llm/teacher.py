"""TODO docstring."""
import hashlib
import statistics
from collections import Counter

import numpy as np
from nodesem.llm.post import role_agreement


# ----------------------------------------------------------------------
# node_sem/llm_teacher (picked: present_row, teacher_text, quality)
def present_row(row):
    """Preserve the v2 score/flags; change only the explicitly authorized policy."""
    item = dict(row, flags=list(row["flags"]), old_present=bool(row["present"]))
    blocked = any("blacklist" in x for x in item["flags"])
    kind = item["target_kind"]
    if kind == "function":
        item["present"] = bool(item["intent"]) and not blocked
        item["unverified"] = item["present"]  # Intent has no static prose reference.
    elif kind == "statement":
        valid = bool(item["summary"]) and not blocked and not any(
            f in item["flags"] for f in ("missing", "parse_failed", "skipped_no_body"))
        score = item["faithfulness"]
        item["present"] = valid and (score is None or score >= .5)
        item["unverified"] = item["present"] and score is None
    else:
        item["present"] = False
        item["unverified"] = False
    return item

def teacher_text(row):
    if not row["present"]:
        return ""
    if row["target_kind"] == "function":
        return "function: " + row["intent"]
    return "{}. function: {}".format(row["summary"], row["intent"])

def quality(rows, facts):
    statement = [r for r in rows if r["target_kind"] == "statement"]
    scores = [r["faithfulness"] for r in statement if r["faithfulness"] is not None]
    return dict(rows=len(rows), statement_nodes=len(statement),
        present=sum(r["present"] for r in rows), old_present=sum(r["old_present"] for r in rows),
        statement_present=sum(r["present"] for r in statement),
        unverified_statements=sum(r["unverified"] for r in statement),
        unverified_fraction=sum(r["unverified"] for r in statement)/len(statement) if statement else None,
        unverified_function_intents=sum(r["unverified"] for r in rows if r["target_kind"]=="function"),
        verifiable=len(scores), faithfulness_median=statistics.median(scores) if scores else None,
        faithfulness_distribution=dict(
            minimum=min(scores) if scores else None, maximum=max(scores) if scores else None,
            mean=statistics.mean(scores) if scores else None,
            counts={str(value):scores.count(value) for value in sorted(set(scores))}),
        unverified_fraction_of_present_statements=(
            sum(r["unverified"] for r in statement)/sum(r["present"] for r in statement)
            if any(r["present"] for r in statement) else None),
        verifiable_ge_half_fraction=sum(s>=.5 for s in scores)/len(scores) if scores else None,
        blacklist_nodes=sum(any("blacklist" in f for f in r["flags"]) for r in statement),
        blacklist_fraction=sum(any("blacklist" in f for f in r["flags"]) for r in statement)/len(statement) if statement else None,
        flags=dict(Counter(f for r in rows for f in r["flags"])),
        roles=role_agreement(statement,facts))


# ----------------------------------------------------------------------
# node_sem/teacher_vectors (picked: scatter)
def scatter(rows, unique, vectors, dimension=384):
    vectors=np.asarray(vectors)
    if vectors.dtype!=np.float32 or vectors.shape!=(len(unique),dimension) or not np.isfinite(vectors).all():
        raise ValueError("Teacher vector shape/dtype/nonfinite")
    if len(set(unique))!=len(unique):raise ValueError("Duplicate unique text")
    if len(vectors) and not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-5,rtol=0):
        raise ValueError("Teacher vectors not normalized")
    lookup={s:i for i,s in enumerate(unique)}
    values=np.zeros((len(rows),dimension),dtype=np.float32)
    identities=[];seen=set()
    for i,row in enumerate(rows):
        key=row["row_key"]
        if key in seen:raise ValueError("Duplicate teacher row")
        seen.add(key)
        if type(row["present"]) is not bool or bool(row["text"])!=row["present"]:
            raise ValueError("Teacher text/presence mismatch")
        if row["text_sha256"]!=hashlib.sha256(row["text"].encode("utf8")).hexdigest():
            raise ValueError("Teacher text SHA differs")
        if row["present"]:values[i]=vectors[lookup[row["text"]]]
        item={k:row[k] for k in ("row_key","file","node_type","source_sha256","code_sha256","present")}
        item.update(unverified=row["unverified"],vector_sha256=hashlib.sha256(values[i].tobytes()).hexdigest())
        identities.append(item)
    return values,identities
