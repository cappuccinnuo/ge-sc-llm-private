"""NS-P0 read-only text/AST inventory, not a production feature extractor.

Existing sources, graphs, labels, tokens, plans and naming records are untouched.
Temporary anonymous code views and comment removal exist only in memory.
Projector's structural label anchor is identity evidence, never a feature value.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time
import numpy as np
from tree_sitter import Language, Parser
from scripts.labeling_v2.safe_graph import read_graph
from scripts.DFG.frontend import FUNCTION_TYPES, leaves, library_path, walk
from scripts.DFG.projection import Projector, code_equal
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.anon_parity import node_code_view
from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import load_result
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import reserved
from scripts.DFG.dfg_v2.diagnostics8d.stratification import synthetic_owner
from process_graphs.tree_sitter_codeviews.utils.solidity_nodes import return_if_root

SAMPLE_TYPES = ("if", "for", "while", "function_definition",
                "constructor_definition", "modifier_definition",
                "contract_declaration", "new_variable")
HEADER_TYPES = {"function_definition", "constructor_definition",
                "modifier_definition", "fallback_receive_definition",
                "contract_declaration", "library_declaration", "interface_declaration"}
CALLABLE_TYPES = set(FUNCTION_TYPES) | {"modifier_definition"}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(value.encode("utf8")).hexdigest()

def checked(reference):
    path = Path(reference["path"])
    if sha(path) != reference["sha256"]:
        raise ValueError("Frozen input SHA mismatch: " + str(path))
    return path

def read(reference):
    return json.loads(checked(reference).read_text(encoding="utf8"))

def evidence(function):
    path = Path(inspect.getsourcefile(function)).resolve()
    source, line = inspect.getsourcelines(function)
    return dict(path=str(path), sha256=sha(path), function=function.__qualname__,
                first_line=line, last_line=line + len(source) - 1)

def all_nodes(root):
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.children))

def raw_parse(source):
    parser = Parser()
    parser.set_language(Language(str(library_path()), "solidity"))
    tree = parser.parse(source.encode("utf8"))
    nodes = list(all_nodes(tree.root_node))
    return tree, dict(errors=sum(n.type == "ERROR" for n in nodes),
                      missing=sum(n.is_missing for n in nodes),
                      root_has_error=tree.root_node.has_error)

def strip_comments(source, tree):
    """Diagnostic only: blank AST comment bytes; preserve newlines/boundaries."""
    raw = bytearray(source.encode("utf8"))
    comments = [n for n in walk(tree.root_node) if "comment" in n.type]
    for node in comments:
        for position in range(node.start_byte, node.end_byte):
            if raw[position] not in (10, 13):
                raw[position] = 32
    return raw.decode("utf8"), comments

def normalized_function(raw, function):
    """Lexical first-occurrence normalization, not declaration resolution."""
    names, tokens = {}, []
    for node in leaves(function):
        token = raw[node.start_byte:node.end_byte].decode("utf8")
        if node.type == "identifier" and not reserved(token):
            if token not in names:
                names[token] = "a" + str(len(names) + 1)
            token = names[token]
        tokens.append([node.type, token])
    return digest(json.dumps(tokens, ensure_ascii=False, separators=(",", ":"))), len(names)

def source_inventory(source, result):
    anonymous = result["rewritten"]
    tree, baseline = raw_parse(anonymous)
    clean, comments = strip_comments(anonymous, tree)
    after, stripped = raw_parse(clean)
    raw, clean_raw = anonymous.encode("utf8"), clean.encode("utf8")
    if ([raw[n.start_byte:n.end_byte] for n in leaves(tree.root_node)] !=
            [clean_raw[n.start_byte:n.end_byte] for n in leaves(after.root_node)]):
        raise AssertionError("Comment blanking changed executable tokens")
    functions, roles = [], Counter()
    for node in walk(tree.root_node):
        if node.type not in CALLABLE_TYPES:
            continue
        name = node.child_by_field_name("name")
        name_text = raw[name.start_byte:name.end_byte].decode("utf8") if name else None
        owner = node.parent
        while owner is not None and owner.type not in {
                "contract_declaration", "library_declaration", "interface_declaration"}:
            owner = owner.parent
        owner_name = owner.child_by_field_name("name") if owner else None
        owner_text = (raw[owner_name.start_byte:owner_name.end_byte].decode("utf8")
                      if owner_name else None)
        role = node.type
        if role == "function_definition" and name_text and name_text == owner_text:
            role = "legacy_constructor_name_match"
        normalized, count = normalized_function(raw, node)
        roles[role] += 1
        functions.append(dict(ast_type=node.type, role=role,
            start_byte=node.start_byte, end_byte=node.end_byte,
            start_line=node.start_point[0]+1, end_line=node.end_point[0]+1,
            lines=node.end_point[0]-node.start_point[0]+1,
            has_body=node.child_by_field_name("body") is not None,
            anonymous_code_sha256=digest(raw[node.start_byte:node.end_byte].decode("utf8")),
            first_occurrence_normalized_sha256=normalized,
            renamed_distinct_identifiers=count))
    return dict(anonymous_source_sha256=digest(anonymous),
        comment_count=len(comments), comment_types=dict(Counter(n.type for n in comments)),
        comment_bytes=sum(n.end_byte-n.start_byte for n in comments),
        parse_before=baseline, parse_after_comment_blanking=stripped,
        executable_tokens_unchanged=True, newline_and_byte_offsets_preserved=True,
        functions=functions, function_roles=dict(roles))

def extract_shape(node, view):
    """Probe AST slice boundaries; diagnostic excerpts are never model input."""
    if node.type in ("if_statement", "while_statement"):
        child = node.child_by_field_name("condition")
        if child is None:
            return None, "missing_condition_field"
        return view.compat[child.start_byte:child.end_byte].decode("utf8"), "condition"
    if node.type == "for_statement":
        body = node.child_by_field_name("body")
        if body is None:
            return None, "missing_for_body_field"
        return view.compat[node.start_byte:body.start_byte].decode("utf8").strip(), "for_header"
    if node.type in HEADER_TYPES:
        body = node.child_by_field_name("body")
        end = body.start_byte if body is not None else node.end_byte
        return view.compat[node.start_byte:end].decode("utf8").strip(), (
            "header_without_body" if body is not None else "declaration_without_body")
    return view.compat[node.start_byte:node.end_byte].decode("utf8"), "complete_ast_subtree"

def run(repo_root):
    started = time.monotonic()
    root = Path(repo_root).resolve()
    plan_path = root / "scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf8"))
    preparation = read(plan["source_preparation"])
    naming_ref = preparation["bound_artifacts"]["spelling_naming"]
    naming = read(naming_ref)
    sources = read(naming["artifacts"]["sources"])
    output = dict(version="nodesem-ns-p0-text-ast-v1", read_only=True,
        plan=dict(path=str(plan_path), sha256=sha(plan_path)), naming=naming_ref,
        evidence={f.__name__: evidence(f) for f in (node_code_view, load_result,
            Projector, ProjectionView, synthetic_owner, return_if_root, reserved)}, tasks={},
        notes=["Diagnostic code slices are not production text_view or persisted model features.",
               "Projector reads saved label AST anchors only for identity; target/prediction labels are unused.",
               "First-occurrence normalization is a lexical estimate, not a binding proof or final LLM cache key.",
               "Dedup ignores comments and token spacing, preserves literals; state context is not included.",
               "Constructor name equality is syntactic evidence, not compiler verification.",
               "Tree-sitter ERROR=0 does not establish Solidity compilation."])
    source_cache = {}
    for tid, task in plan["tasks"].items():
        print("text_ast: " + tid, file=sys.stderr, flush=True)
        graph_ref = task["profiles"]["G0"]["graph"]
        graph = read_graph(checked(graph_ref))
        feature_rows = {row["original_graph_node_id"]: row
                        for row in read(task["feature_view"])["rows"]}
        samples = {typ: [] for typ in SAMPLE_TYPES}
        mapping, synthetic = defaultdict(Counter), Counter()
        synthetic_examples, files, all_functions = [], [], []
        elseif_examples = []
        ordinary_total, code_count, exact_codes = 0, 0, 0
        population = Counter(a["node_type"] for _, a in graph.nodes(data=True))
        for file, source_ref in sorted(task["record"]["sources"].items()):
            identity = task["category"] + "/" + file
            row = sources[identity]
            if row["source"] != source_ref:
                raise ValueError("Frozen source identity differs: " + identity)
            if identity not in source_cache:
                source, result = load_result(row)
                source_cache[identity] = (source, result, source_inventory(source, result))
            source, result, inventory = source_cache[identity]
            ids = [n for n, a in graph.nodes(data=True) if a["source_file"] == file]
            base = graph.subgraph(ids).copy()
            codes, proof = node_code_view(base, file, source, result)
            if set(codes) != set(base):
                raise AssertionError("Anonymous code does not cover all original nodes")
            for nid, code in codes.items():
                if digest(code) != feature_rows[nid]["rewritten_code_sha256"]:
                    raise AssertionError("Anonymous code differs from frozen feature view")
            code_count += len(codes)
            temporary = base.copy()
            for nid, code in codes.items():
                temporary.nodes[nid]["code"] = code
            view = ProjectionView(result["rewritten"], file)
            projector = Projector(temporary, view)
            inverse = {nid: ast_id for ast_id, nid in projector.by_ast.items()}
            by_id = {ast_id: view.compat_nodes[key] for key, ast_id in view.compat_ids.items()}
            before = ProjectionView(source, file)
            before_ids = {ast_id: before.compat_nodes[key] for key, ast_id in before.compat_ids.items()}
            ordinary_total += len(inverse)
            by_proof = {entry["node"]: entry for entry in proof}
            for nid, attrs in temporary.nodes(data=True):
                typ = attrs["node_type"]
                mapping[typ]["total"] += 1
                if nid in inverse:
                    ast_node, mode = by_id[inverse[nid]], "ordinary_projector_identity"
                    original_node = before_ids[inverse[nid]]
                    whole = code_equal(base.nodes[nid]["code"], before.compat[
                        original_node.start_byte:original_node.end_byte].decode("utf8"))
                    if not whole:
                        raise AssertionError("Original code differs from full AST subtree")
                    exact_codes += 1
                elif typ in ("end_if", "end_loop"):
                    ast_node, mode = synthetic_owner(attrs, view)
                    whole = None
                    synthetic[typ + ":" + mode] += 1
                    if ast_node is not None and ast_node.type == "if_statement":
                        root_node = return_if_root(ast_node)
                        if root_node.start_byte != ast_node.start_byte:
                            synthetic["else_if_uses_return_if_root_start"] += 1
                            if len(elseif_examples) < 10:
                                elseif_examples.append(dict(file=file, node=nid,
                                    own_compat_line=ast_node.start_point[0]+1,
                                    saved_root_compat_line=root_node.start_point[0]+1,
                                    rule="exact role/root-start/code identity; not nearest line"))
                    if len(synthetic_examples) < 12 or ast_node is None:
                        synthetic_examples.append(dict(file=file, node=nid, node_type=typ,
                            identity_status=mode, node_code_proof=by_proof[nid]))
                else:
                    ast_node, whole, mode = None, None, "missing_identity"
                if ast_node is not None:
                    mapping[typ]["ast_identity_success"] += 1
                    if typ in ("end_if", "end_loop"):
                        excerpt, extraction = "<" + typ.upper() + ">", "synthetic_end_sentinel"
                    else:
                        excerpt, extraction = extract_shape(ast_node, view)
                    if excerpt is None:
                        mapping[typ]["extraction_failed:" + extraction] += 1
                    else:
                        mapping[typ]["extraction_success"] += 1
                        mapping[typ]["extraction_rule:" + extraction] += 1
                else:
                    mapping[typ]["ast_identity_failure:" + mode] += 1
                    excerpt, extraction = None, "unresolved"
                if typ in samples and len(samples[typ]) < 10:
                    code = base.nodes[nid]["code"]
                    samples[typ].append(dict(file=file, source_sha256=source_ref["sha256"],
                        node=nid, original_code_sha256=digest(code),
                        original_code_preview=code[:400], stored_characters=len(code),
                        pydot_outer_quotes=code.startswith('"') and code.endswith('"'),
                        full_ast_subtree=whole, identity_mode=mode,
                        ast_type=ast_node.type if ast_node is not None else None,
                        extraction=extraction,
                        anonymous_excerpt_preview=excerpt[:400] if excerpt else excerpt))
            files.append(dict(identity=identity, source=source_ref, naming_result=row["result"],
                              original_nodes=len(ids), anonymous_code_nodes=len(codes), **inventory))
            all_functions.extend(dict(identity=identity, **f) for f in inventory["functions"])
        lengths = [f["lines"] for f in all_functions]
        bodies = [f for f in all_functions if f["has_body"]]
        output["tasks"][tid] = dict(graph=graph_ref, nodes=len(graph), files=len(files),
            anonymous_code_nodes=code_count, anonymous_code_all_original_nodes=code_count == len(graph),
            anonymous_code_sha_matches_frozen_features=True,
            ordinary_projector_nodes=ordinary_total, original_full_ast_subtree_nodes=exact_codes,
            type_population=dict(population), mapping_by_type={k: dict(v) for k, v in mapping.items()},
            sample_selection="first up to 10/type in sorted file order; label-independent",
            samples=samples, sample_shortfalls={t: 10-len(v) for t, v in samples.items() if len(v)<10},
            synthetic_identity_counts=dict(synthetic), synthetic_examples=synthetic_examples,
            synthetic_elseif_examples=elseif_examples,
            source_inventory=files,
            source_summary=dict(comments=sum(f["comment_count"] for f in files),
                files_with_comments=sum(f["comment_count"]>0 for f in files),
                parse_errors_before=sum(f["parse_before"]["errors"] for f in files),
                parse_errors_after=sum(f["parse_after_comment_blanking"]["errors"] for f in files),
                parse_missing_before=sum(f["parse_before"]["missing"] for f in files),
                parse_missing_after=sum(f["parse_after_comment_blanking"]["missing"] for f in files),
                executable_tokens_unchanged=all(f["executable_tokens_unchanged"] for f in files),
                callables_including_bodyless=len(all_functions), callables_with_body=len(bodies),
                callable_roles=dict(Counter(f["role"] for f in all_functions)),
                unique_anonymous_function_texts=len({f["anonymous_code_sha256"] for f in all_functions}),
                unique_first_occurrence_normalized_functions=len({f["first_occurrence_normalized_sha256"] for f in all_functions}),
                unique_normalized_body_functions=len({f["first_occurrence_normalized_sha256"] for f in bodies}),
                function_line_quantiles=dict(median=float(np.median(lengths)),
                    p95=float(np.percentile(lengths,95)), maximum=max(lengths)) if lengths else None),
            original_graph_file_sha_unchanged=sha(graph_ref["path"]) == graph_ref["sha256"])
    output["elapsed_seconds"] = time.monotonic()-started
    output["unique_source_identities"] = len(source_cache)
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    args = parser.parse_args()
    print(json.dumps(run(args.repo), ensure_ascii=False, indent=2))
