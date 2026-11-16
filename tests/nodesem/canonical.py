"""Canonical, order- and id-independent digests of NodeSem analysis rows."""
import collections
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def strip(obj, drop=("provenance",)):
    if isinstance(obj, dict):
        return {k: strip(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [strip(v, drop) for v in obj]
    return obj


def canon(obj):
    """Lists become sorted multisets (evidence order follows graph edge order)."""
    if isinstance(obj, dict):
        return {k: canon(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return sorted((canon(v) for v in obj), key=lambda z: json.dumps(z, sort_keys=True))
    return obj


def renode(obj, mapping):
    """Replace node-id references by [file, index within file]."""
    if isinstance(obj, dict):
        return {k: (mapping.get(v, ["?", v]) if k in ("node", "nearest_node") and isinstance(v, int)
                    else renode(v, mapping)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [renode(v, mapping) for v in obj]
    return obj


def positions(keys_files):
    """[(row key, file)] of original rows in order -> {row key: [file, index within file]}."""
    out, seen = {}, collections.Counter()
    for key, f in keys_files:
        out[key] = [f, seen[f]]
        seen[f] += 1
    return out


def per_file(text_rows, values):
    """{file: digest of that file's original-row values in order}; env rows separately."""
    groups, env = collections.defaultdict(list), []
    for row, value in zip(text_rows, values):
        (env if row["node_type"] == "env_source" else groups[row["file"]]).append(
            [row["file"], row.get("text"), value] if row["node_type"] == "env_source" else value)
    return dict({f: digest(v) for f, v in sorted(groups.items())}, __env__=digest(sorted(env, key=json.dumps)))


def analysis_digests(text_rows, facts, ctx, static_shas):
    """Per-file digests comparable across graphs with different global node ids."""
    originals = [(r["row_key"], r["file"]) for r in text_rows if r["node_type"] != "env_source"]
    mapping = positions(originals)
    text = [{k: r[k] for k in r if k not in ("row_key", "source_sha256")} for r in text_rows]
    return dict(text=per_file(text_rows, text),
                facts=per_file(text_rows, [canon(renode(strip(f), mapping)) for f in facts]),
                ctx=per_file(text_rows, [canon(c) for c in ctx]),
                static=per_file(text_rows, static_shas))
