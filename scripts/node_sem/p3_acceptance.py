"""Read-only NS-P3b acceptance: no target parsing, model construction or fit."""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import re
import numpy as np
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from . import facts_schema as fs
from .carrier import carry, load_modality
from .feature_spec import FeatureSpec
from .facts_verify import sealed_manifest, read_jsonl, verify_frozen_snapshot
from .facts_io import PLAN, load_context
from .p3_prepare import ROOT, CURRENT, load_accepted, field_stats
from .ctx_fields import FIELD_ORDER, ID_RE
from .static_profile import encode, load_schema, column_names, unknown

ARTIFACTS = ROOT / "scripts/node_sem/artifacts"
LITERAL = re.compile(r""" "(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*' """.strip())
PLACEHOLDER = re.compile(r"(?:STATE|PARAM|LOCAL|IDENT|FUNC|TYPE)[1-9][0-9]*$")


def _vocabulary():
    words = set(FIELD_ORDER)
    def visit(value):
        if isinstance(value, str):
            words.update(ID_RE.findall(value))
        elif isinstance(value, dict):
            for k, v in value.items():
                visit(k); visit(v)
        elif isinstance(value, (tuple, list, set)):
            for item in value: visit(item)
    for key, value in vars(fs).items():
        if key.isupper(): visit(value)
    for kind in fs.NODE_KINDS: visit(fs.new_facts(kind))
    for field in load_schema()["fields"]:
        visit(field["name"]); visit(field["values"])
    words.update(("state local param parameter return env unknown entry none true false visibility guards "
                  "kinds target value data bound external_call kind polarity eq additional operands "
                  "early_exit shape scalar public constant_immutable has_initializer auth read_functions "
                  "write_functions only_constructor_writes unguarded_write_functions END_IF END_LOOP").split())
    return words


def masked_identifiers(fields, allowed=None):
    """Scan lexical identifiers, excluding Solidity string literals and numbers."""
    allowed = _vocabulary() if allowed is None else allowed
    residual = Counter()
    for values in fields.values():
        for value in values:
            text = LITERAL.sub(" ", value)
            text = re.sub(r"\b0x[0-9a-fA-F]+\b|\b[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b", " ", text)
            for word in ID_RE.findall(text):
                if word not in allowed and not reserved(word) and not PLACEHOLDER.fullmatch(word):
                    residual[word] += 1
    return residual


def verify_static(facts, values, schema):
    expected = np.stack([encode(row, schema) for row in facts]).astype(np.float32)
    if not np.array_equal(values, expected):
        raise ValueError("STATIC differs from accepted facts")
    if not np.isin(values, [0, 1]).all():
        raise ValueError("STATIC is not binary")
    for i, row in enumerate(facts):
        f = row["facts"]
        for field in schema["fields"]:
            applicable = f["node_kind"] in field["applicable"]
            missing = applicable and field["unknown"] and unknown(f, field["unknown"])
            bits = values[i, field["start"]:field["stop"]]
            if field["encoding"] == "one_hot" and bits.sum() != (0 if missing else 1):
                raise ValueError("STATIC one-hot / unknown rule violated")
            if (not applicable or (missing and field["unknown_policy"]=="zero")) and field["encoding"] != "one_hot" and bits.any():
                raise ValueError("STATIC unknown / inapplicable value leaked")


def sealed_fields(path):
    path = Path(path)
    if read(path.with_suffix(".seal.json"))["manifest"] != ref(path):
        raise ValueError("CTX fields seal differs")
    return read(path)


def _encoding_stats(meta):
    result = dict(meta)
    diagnostics = dict(result["diagnostics"])
    for key, value in list(diagnostics.items()):
        if isinstance(value, list):
            diagnostics[key] = dict(count=len(value), minimum=min(value) if value else None,
                                    maximum=max(value) if value else None)
    result["diagnostics"] = diagnostics
    return result


def verify(output, encoding_index, prepared_root=None, snapshot_path=None, mutable_paths=()):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    index_path = Path(encoding_index).resolve()
    if read(index_path.with_suffix(".seal.json"))["index"] != ref(index_path):
        raise ValueError("Encoding index seal differs")
    index = read(index_path)["tasks"]
    schema = load_schema()
    ctx_root = (Path(prepared_root)/"fields/original" if prepared_root else ARTIFACTS/"ctx_v1/original")
    static_root = (Path(prepared_root)/"static/original" if prepared_root else ARTIFACTS/"ns_p3/static/original")
    tasks = sorted(read(CURRENT)["tasks"])
    if set(index) != set(tasks) or any(set(x) != {"original", "masked"} for x in index.values()):
        raise ValueError("Incomplete CTX encoding index")
    summaries, assemblies, references, scans = {}, [], {}, {}
    for task in tasks:
        facts, texts, _, _, accepted = load_accepted(task)
        context = load_context(task)
        code_path = ARTIFACTS / "ns_p2/encoded/original" / task / "manifest.json"
        code = sealed_manifest(code_path)
        load_modality(ref(code_path))
        static_path = static_root / task / "manifest.json"
        static = sealed_manifest(static_path)
        static_vectors = load_modality(ref(static_path))
        keys = [row["row_key"] for row in texts]
        if list(static_vectors) != keys or not all(r["present"] for r in static["rows"]):
            raise ValueError("STATIC identity/order/presence differs")
        values = np.stack([static_vectors[k] for k in keys])
        verify_static(facts, values, schema)
        task_stats = dict(rows=len(keys), static_dimension=schema["dimension"],
            static_one_rates=dict(zip(column_names(schema), values.mean(axis=0, dtype=np.float64).tolist())),
            preparation=read(ctx_root / task / "preparation.json"),
            names={})
        references[task] = dict(accepted=accepted, code=ref(code_path), static=ref(static_path), ctx={})
        for mode in ("original", "masked"):
            suffix = "" if mode == "original" else "_masked"
            fields_path = ctx_root / task / ("ctx_fields"+suffix+".manifest.json")
            fields_manifest = sealed_fields(fields_path)
            fields = read_jsonl(checked(fields_manifest["input_text"]))
            ctx_path = checked(index[task][mode])
            ctx = sealed_manifest(ctx_path)
            vectors = load_modality(ref(ctx_path))
            if list(vectors) != keys or not all(r["present"] for r in ctx["rows"]):
                raise ValueError("CTX identity/order/presence differs")
            if ctx["names"] != mode or ctx["view"] != "original":
                raise ValueError("CTX policy differs")
            for key in ("model", "revision", "model_sha256", "pooling", "normalized", "inference_dtype"):
                if ctx["encoding"][key] != code["encoding"][key]:
                    raise ValueError("CTX differs from frozen CODE encoder: "+key)
            if ctx["input_text"] != fields_manifest["input_text"]:
                raise ValueError("CTX input reference differs")
            if ctx["encoding"]["repeat_max_abs_error"] > 1e-6 or ctx["encoding"]["optimizer_steps"] != 0:
                raise ValueError("CTX repeat/frozen inference failed")
            budget_rows = read_jsonl(checked(ctx["encoded_text"]))
            if [r["row_key"] for r in budget_rows] != keys:
                raise ValueError("Encoded CTX row identities differ")
            for row, budget in zip(fields, budget_rows):
                if budget["retained_fields"] != row["field_order"] or budget["final_tokens"] > 256:
                    raise ValueError("CTX lost fields / exceeded budget")
                if hashlib.sha256(budget["text"].encode()).hexdigest() != budget["text_sha256"]:
                    raise ValueError("Encoded CTX text digest differs")
                for field in row["field_order"]:
                    if not any(line.startswith("["+field+"] ") for line in budget["text"].splitlines()):
                        raise ValueError("CTX field label missing")
            if dict(Counter(str(r["stage"]) for r in budget_rows)) != ctx["encoding"]["stages"]:
                raise ValueError("Truncation statistics differ")
            if mode == "masked":
                residual = Counter()
                allowed = _vocabulary()
                for row in fields: residual.update(masked_identifiers(row["fields"], allowed))
                scans[task] = dict(rows=len(fields), unexpected=dict(residual),
                    excludes_string_and_numeric_literals=True)
                if residual: raise ValueError("Unmasked identifiers: "+repr(residual))
            task_stats["names"][mode] = dict(fields=field_stats(fields), encoding=_encoding_stats(ctx["encoding"]))
            references[task]["ctx"][mode] = ref(ctx_path)
            for graph_name, graph in context["graphs"].items():
                before = graph_fingerprint(graph)
                mods = [dict(name="code", dim=code["feature_shape"][1], manifest=ref(code_path), normalize=True),
                        dict(name="ctx", dim=ctx["feature_shape"][1], manifest=ref(ctx_path), normalize=True)]
                for name in ("S3", "S4"):
                    items = mods if name == "S3" else mods + [dict(name="static",
                        dim=schema["dimension"], manifest=ref(static_path), normalize=False)]
                    spec = FeatureSpec(name, "original", items, "none", "concat")
                    carried, record = carry(graph, spec, task)
                    assert all(np.asarray(attrs["token"]).shape == (spec.carrier_dim(),)
                               for _, attrs in carried.nodes(data=True))
                    assert graph_fingerprint(graph) == before
                    assemblies.append(dict(task=task, names=mode, profile=graph_name,
                        spec=spec.to_json(), rows=len(graph), dimension=spec.carrier_dim(),
                        graph_fingerprint=before, original_unchanged=True,
                        carrier_graph_fingerprint=record["carrier_graph_fingerprint"]))
                    del carried, record
        summaries[task] = task_stats
        write(output/(task+".json"), dict(passed=True, rows=len(keys), refs=references[task]))
        print(task+": passed", flush=True)
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    load(PLAN)
    if _code_refs() != read(PLAN.with_name("runtime_resume_v2.json"))["runtime"]:
        raise ValueError("Historical effective runtime changed")
    snapshot = read(snapshot_path or ARTIFACTS/"ns_p3/started.json")["tracked_sha256"]
    mutable_docs = {"HANDOVER.md", "docs/training_changes_2026-10-07.md",
                    "scripts/node_sem/PROGRESS.md", "scripts/node_sem/EXPERIMENT_POLICY.md"}
    mutable_docs.update(mutable_paths)
    changed = [p for p, digest in snapshot.items() if p not in mutable_docs
               and ref(ROOT/p)["sha256"] != digest]
    if changed: raise ValueError("Frozen tracked content changed: "+repr(changed))
    legacy = verify_frozen_snapshot(ARTIFACTS/"facts_v1/started.json")
    stats = dict(version="nodesem-p3b-stats-v1", view="original", tasks=summaries,
        target_grouping=False, training_executed=False)
    write(output/"stats.json", stats)
    result = dict(passed=True, tasks=references, total_rows=sum(x["rows"] for x in summaries.values()),
        static_dimension=schema["dimension"], ctx_manifests=8, static_manifests=4,
        original_code_manifests_revalidated=4, masked_scan=scans, assemblies=assemblies,
        historical_8h_load=True, historical_runtime_equal=True, frozen_snapshot=legacy,
        tracked_files_checked=len(snapshot)-len(mutable_docs), training_executed=False,
        anonymous_inputs_loaded=False, checkpoint_deserialization=False,
        implementation=ref(Path(__file__)), encoding_index=ref(index_path), stats=ref(output/"stats.json"))
    write(output/"validation.json",result)
    write(output/"validation.seal.json",dict(validation=ref(output/"validation.json"),
        stats=ref(output/"stats.json")))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True)
    parser.add_argument("--encoding-index",required=True)
    args=parser.parse_args()
    result=verify(args.out,args.encoding_index)
    print("passed; rows={}; assemblies={}".format(result["total_rows"],len(result["assemblies"])))


if __name__=="__main__": main()
