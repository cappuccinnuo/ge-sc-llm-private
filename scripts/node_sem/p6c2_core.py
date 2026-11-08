"""Population-corrected CPU diagnostics; frozen logistic algorithm is reused."""
from collections import Counter
import numpy as np
from .facts_schema import NODE_KINDS
from .p6c_core import logistic_probe, split_indices


def aligned_kinds(rows, static_rows, fact_rows):
    def indexed(items):
        table = {r["row_key"]: r for r in items}
        if len(table) != len(items):
            raise ValueError("Duplicate row identity")
        return table
    sr, fr = indexed(static_rows), indexed(fact_rows)
    keys = [r["row_key"] for r in rows]
    if len(set(keys)) != len(keys) or set(keys) != set(sr) or set(keys) != set(fr):
        raise ValueError("Different row populations")
    kinds = []
    for r in rows:
        s = sr[r["row_key"]]
        if any(r[k] != s[k] for k in ("file", "node_type", "code_sha256")):
            raise ValueError("Source/code identity mismatch")
        kind = fr[r["row_key"]]["facts"]["node_kind"]
        if kind not in NODE_KINDS:
            raise ValueError("Unknown fact node kind")
        kinds.append(kind)
    return np.asarray(kinds)


def controls(kinds, static, schema):
    kinds = np.asarray(kinds)
    if set(kinds) - set(NODE_KINDS):
        raise ValueError("Unknown control kind")
    syntax = [f for f in schema["fields"] if f["name"] == "syntax"]
    if len(syntax) != 1:
        raise ValueError("Syntax field not unique")
    f = syntax[0]
    onehot = np.column_stack([kinds == k for k in NODE_KINDS]).astype(np.float32)
    result = np.concatenate((onehot, static[:, f["start"]:f["stop"]]), axis=1)
    names = ["node_kind=" + k for k in NODE_KINDS] + ["syntax=" + v for v in f["values"]]
    return result, names


def population(kinds, static, presence, schema):
    kinds = np.asarray(kinds)
    if static.shape != (len(kinds), schema["dimension"]) or not np.isin(static, [0, 1]).all():
        raise ValueError("STATIC shape/value mismatch")
    base = presence["code"] & presence["static"]
    columns = []
    for field in schema["fields"]:
        mask = base & np.isin(kinds, field["applicable"])
        n = int(mask.sum())
        for i, value in enumerate(field["values"], field["start"]):
            positive = int(static[mask, i].sum())
            ratio = positive / n if n else None
            columns.append(dict(index=i, group=field["group"], parent_group=field["group"][0],
                field=field["name"], value=value, applicable=field["applicable"],
                n=n, positive=positive, prevalence=ratio,
                eligible=ratio is not None and .01 <= ratio <= .99))
    if [c["index"] for c in columns] != list(range(schema["dimension"])):
        raise ValueError("Noncontiguous schema")
    return columns


def column_mask(kinds, presence, column):
    mask = presence["code"] & presence["static"] & np.isin(kinds, column["applicable"])
    if not presence["ctx"][mask].all():
        raise ValueError("CTX absent in the common registered population")
    return mask


def redundancy_one(parts, rows, kinds, presence, column, split, control):
    mask = column_mask(kinds, presence, column)
    ix = split_indices([r["file"] for r in rows], split, mask)
    result = {}
    for name, x in (("code", parts["code"]), ("ctx", parts["ctx"]), ("kind_syntax", control)):
        value = logistic_probe(x, parts["static"][:, column["index"]], ix)
        value.pop("probabilities", None)
        value.pop("predictions", None)
        result[name] = value
    return result, ix


def signal_population(rows, kinds, presence, labels):
    table = {(r["file"], r["original_graph_node_id"]): r for r in labels}
    if len(table) != len(labels):
        raise ValueError("Duplicate labels")
    y = np.zeros(len(rows), dtype=int)
    base = np.zeros(len(rows), dtype=bool)
    from pathlib import Path
    for i, r in enumerate(rows):
        label = table.get((r["file"], r["original_graph_node_id"]))
        if label is None:
            if kinds[i] != "env":
                raise ValueError("Original node label missing")
            continue
        if r["node_type"] != label["node_type"]:
            raise ValueError("Label identity mismatch")
        y[i] = label["L-audit_target"]
        base[i] = (label["L-audit_include"] and not Path(r["file"]).name.startswith("buggy_")
            and presence["code"][i] and presence["static"][i])
    selected = base & np.isin(kinds, ["statement", "condition"])
    return y, base, selected, dict(Counter(kinds[base & (y == 1)]))
