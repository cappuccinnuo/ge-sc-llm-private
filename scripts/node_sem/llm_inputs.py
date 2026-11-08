"""NS-P7 original-source -> canonical prompts. Labels never enter this producer."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from scripts.DFG.frontend import parse, walk
from scripts.DFG.projection import Projector
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.DFG.dfg_v2.benchmark_v2.feature_view import graph_fingerprint
from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from .facts_ast import FUNCTIONS, CONTRACTS, key
from .llm_protocol import VERSION, digest, cache_key, messages, template
from .p3_prepare import load_accepted, write_jsonl
from .facts_io import load_context
from .text_view import PLACEHOLDERS

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "scripts/node_sem/artifacts/facts_v1/CURRENT.json"
MARKERS = ("re_ent", "txorigin", "intou", "tmstmp", "TOD", "unchk", "bug_")


def ancestor(node, types):
    while node is not None:
        if node.type in types:
            return node
        node = node.parent
    return None


def no_comments(source):
    raw = source.encode("utf8")
    tree = parse(source)
    nodes = list(walk(tree.root_node))
    if any(n.type == "ERROR" or n.is_missing for n in nodes):
        raise ValueError("Input grammar ERROR/MISSING")
    for node in sorted((n for n in nodes if "comment" in n.type),
                       key=lambda n: n.start_byte, reverse=True):
        part = raw[node.start_byte:node.end_byte]
        # Keep newlines as whitespace, preserving exact byte and line coordinates.
        raw = raw[:node.start_byte] + bytes(b if b in (10, 13) else 32 for b in part) + raw[node.end_byte:]
    result = raw.decode("utf8")
    other = parse(result)
    if any(n.type == "ERROR" or n.is_missing for n in walk(other.root_node)):
        raise ValueError("Comment removal changes parse validity")
    return raw, other


def canonical_piece(raw, node, mapping):
    tokens = [x for x in walk(node) if x.type == "identifier"]
    before = raw[node.start_byte:node.end_byte]
    after = before
    edits = []
    for token in sorted(tokens, key=lambda x: x.start_byte):
        name = raw[token.start_byte:token.end_byte].decode("utf8")
        if not reserved(name):
            mapping.setdefault(name, "a" + str(len(mapping) + 1))
            edits.append((token.start_byte - node.start_byte, token.end_byte - node.start_byte, name, mapping[name]))
    for start, end, old, new in reversed(edits):
        if after[start:end].decode("utf8") != old:
            raise ValueError("Identifier byte span differs")
        after = after[:start] + new.encode("ascii") + after[end:]
    # Inverse uses recorded occurrence positions, never regex over string literals.
    restored = after
    delta, inverse_edits = 0, []
    for start, end, old, new in edits:
        inverse_edits.append((start + delta, start + delta + len(new), old, new))
        delta += len(new) - (end - start)
    for start, end, old, new in reversed(inverse_edits):
        if restored[start:end].decode("utf8") != new:
            raise ValueError("Inverse identifier span differs")
        restored = restored[:start] + old.encode("utf8") + restored[end:]
    if restored != before or len(set(mapping.values())) != len(mapping):
        raise ValueError("Canonical spelling bijection failed")
    return after.decode("utf8"), dict(original=before.decode("utf8"), edits=edits)


def function_unit(raw, fn, declarations):
    # Function occurrences take precedence, as specified in section 4.7.
    mapping = {}
    canonical, evidence = canonical_piece(raw, fn, mapping)
    state_parts = [canonical_piece(raw, n, mapping)[0] for n in declarations]
    lines, physical = [], {}
    for index, line in enumerate(canonical.splitlines()):
        if line.strip():
            physical[index] = len(lines) + 1
            lines.append(line)
    # Renaming never changes newlines.
    body = fn.child_by_field_name("body")
    signature = raw[fn.start_byte:(body.start_byte if body is not None else fn.end_byte)].decode("utf8")
    # Prefix of canonical function has the same number of tokens; take bytes via body-relative prefix edits.
    if body is not None:
        prefix = raw[fn.start_byte:body.start_byte]
        for start, end, old, new in reversed(evidence["edits"]):
            if end <= len(prefix):
                prefix = prefix[:start] + new.encode("ascii") + prefix[end:]
        signature = prefix.decode("utf8").strip()
    else:
        signature = canonical.strip()
    content = "\n".join(state_parts + [canonical])
    for marker in MARKERS:
        if marker in content:
            raise ValueError("Preserved literal/reserved text contains prohibited marker: " + marker)
    return dict(state_vars="\n".join(state_parts), lines=lines, physical=physical,
        signature=signature, inverse={new: old for old, new in mapping.items()},
        canonical=canonical, restoration=evidence)


def produce(task_id, graph, sources, texts, fact_rows):
    """Exact AST join patterned after ctx_alignment.enrich; no coordinate search."""
    before = graph_fingerprint(graph)
    text_by = {r["row_key"]: r for r in texts}
    fact_by = {r["row_key"]: r["facts"] for r in fact_rows}
    if len(text_by) != len(texts) or set(text_by) != set(fact_by):
        raise ValueError("Text/fact row identities differ")
    refs, functions = [], []
    owned = {}
    for filename, source in sorted(sources.items()):
        view = ProjectionView(source, filename)
        ids = [n for n, a in graph.nodes(data=True)
               if a["source_file"] == filename and a["node_type"] != "env_source"]
        projector = Projector(graph.subgraph(ids).copy(), view)
        inverse = defaultdict(list)
        for raw_key, compat in view.mapping.items():
            inverse[compat].append(raw_key)
        by_id = {ident: k for k, ident in view.compat_ids.items()}
        projected = defaultdict(list)
        for ast_id, nid in projector.by_ast.items():
            candidates = inverse.get(by_id[ast_id], [])
            if len(candidates) != 1:
                raise ValueError("LLM row has no unique raw AST identity")
            raw_node = view.raw_nodes[candidates[0]]
            owner = ancestor(raw_node, FUNCTIONS)
            if owner is not None:
                projected[key(owner)].append((nid, raw_node.start_point[0], key(raw_node) == key(owner)))
        clean, tree = no_comments(source)
        for fn in (n for n in walk(tree.root_node) if n.type in FUNCTIONS):
            owner = ancestor(fn.parent, CONTRACTS)
            body = owner.child_by_field_name("body") if owner is not None else None
            declarations = [] if body is None else [
                n for n in body.named_children if n.type == "state_variable_declaration"]
            unit = function_unit(clean, fn, declarations)
            identity = digest([hashlib.sha256(source.encode("utf8")).hexdigest(), list(key(fn))])
            lines = defaultdict(list)
            fn_rows = []
            for nid, absolute, is_fn in projected.get(key(fn), []):
                if is_fn:
                    fn_rows.append(nid)
                elif graph.nodes[nid]["node_type"] not in PLACEHOLDERS:
                    relative = unit["physical"].get(absolute - fn.start_point[0])
                    if relative is None:
                        raise ValueError("AST target starts on removed blank line")
                    lines[relative].append(nid)
            length = len(unit["lines"])
            segments = [(1, length)] if length <= 120 else [
                (start, min(start + 59, length)) for start in range(1, length + 1, 60)]
            segments_out = []
            for segment, (lo, hi) in enumerate(segments):
                targets = sorted(x for x in lines if lo <= x <= hi)
                rendered = "\n".join("L{}| {}".format(i, unit["lines"][i-1]) for i in range(lo, hi+1))
                if len(segments) > 1:
                    rendered = unit["signature"] + "\n" + rendered
                item = dict(state_vars=unit["state_vars"], function_with_lines=rendered,
                    target_lines=targets, function_id=identity, segment=segment,
                    segment_count=len(segments), function_lines=length, line_start=lo, line_end=hi)
                segments_out.append(item)
                for line in targets:
                    for nid in lines[line]:
                        if nid in owned:
                            raise ValueError("Target row belongs to several function segments")
                        owned[nid] = identity
                        refs.append(dict(text_by[nid], task_id=task_id, function_id=identity,
                            segment=segment, relative_line=line, target_kind="statement",
                            prompt_map=unit["inverse"]))
            for nid in fn_rows:
                if nid in owned:
                    raise ValueError("Duplicate function row")
                owned[nid] = identity
                refs.append(dict(text_by[nid], task_id=task_id, function_id=identity, segment=0,
                    relative_line=None, target_kind="function", prompt_map=unit["inverse"]))
            functions.append(dict(function_id=identity, source_sha256=view.sha256, file=filename,
                span=list(key(fn)), segments=segments_out, task_id=task_id,
                inverse=unit["inverse"], restoration=unit["restoration"]))
    for text in texts:
        if text["row_key"] not in owned:
            refs.append(dict(text, task_id=task_id, target_kind="excluded",
                reason="no_function_statement_target", relative_line=None, function_id=None))
    if len(refs) != len(texts) or len({r["row_key"] for r in refs}) != len(texts):
        raise ValueError("LLM row coverage differs")
    by_row = {r["row_key"]: r for r in refs}
    if graph_fingerprint(graph) != before:
        raise AssertionError("Prompt producer mutated graph")
    return functions, [by_row[r["row_key"]] for r in texts]


def prepare(output, asset_sha, parameters, tasks=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    current = read(CURRENT)
    tasks = sorted(current["tasks"]) if tasks is None else tasks
    unique, occurrences, task_refs, inputs = {}, [], {}, {}
    for task in tasks:
        facts, texts, fm, tm, accepted = load_accepted(task)
        context = load_context(task)
        fs, rows = produce(task, context["graphs"]["F3"], context["source_text"], texts, facts)
        keys = {}
        for fn in fs:
            occurrences.append({k: v for k, v in fn.items() if k != "segments"})
            for segment in fn["segments"]:
                prompt = {k: segment[k] for k in ("state_vars", "function_with_lines", "target_lines")}
                k = cache_key(prompt, asset_sha, parameters)
                keys[(fn["function_id"], segment["segment"])] = k
                if k not in unique:
                    unique[k] = dict(prompt, cache_key=k, messages=messages(prompt),
                        prompt_sha256=digest(messages(prompt)), occurrences=[])
                unique[k]["occurrences"].append(dict(task_id=task, function_id=fn["function_id"],
                    file=fn["file"], source_sha256=fn["source_sha256"], segment=segment["segment"],
                    segment_count=segment["segment_count"], function_lines=segment["function_lines"]))
        for row in rows:
            if row["function_id"] is not None:
                row["cache_key"] = keys[(row["function_id"], row["segment"])]
        path = output / (task + "_rows.jsonl")
        write_jsonl(path, rows)
        task_refs[task] = ref(path)
        inputs[task] = dict(accepted=accepted, text_manifest=accepted["text_manifest"],
            facts_manifest=accepted["facts_manifest"], profiles=tm["profiles"], sources=tm["sources"])
    units_path, maps_path = output / "units.jsonl", output / "prompt_maps.jsonl"
    write_jsonl(units_path, [unique[k] for k in sorted(unique)])
    write_jsonl(maps_path, occurrences)
    segmented_ids = {o["function_id"] for u in unique.values() for o in u["occurrences"] if o["segment_count"] > 1}
    manifest = dict(version=VERSION, stage="inputs", view="original",
        prompt_naming="function_local_a_k_only", asset_sha256=asset_sha, parameters=parameters,
        template=template("describe_v1"), template_sha256=digest(template("describe_v1")),
        units=ref(units_path), prompt_maps=ref(maps_path), tasks=task_refs, inputs=inputs,
        implementation={str(p.relative_to(ROOT)): ref(p) for p in
            (Path(__file__), Path(__file__).with_name("llm_protocol.py"))},
        statistics=dict(function_occurrences=len(occurrences),
            unique_source_functions=len({f["function_id"] for f in occurrences}),
            unique_prompts=len(unique), prompt_occurrences=sum(len(u["occurrences"]) for u in unique.values()),
            segmented_functions=len(segmented_ids)))
    write(output / "manifest.json", manifest)
    write(output / "manifest.seal.json", dict(manifest=ref(output / "manifest.json")))
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--asset-sha", required=True)
    ap.add_argument("--parameters", required=True)
    args = ap.parse_args()
    print(json.dumps(prepare(args.out, args.asset_sha, read(args.parameters))["statistics"], indent=2))


if __name__ == "__main__":
    main()
