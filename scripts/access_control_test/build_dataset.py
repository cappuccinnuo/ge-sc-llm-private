"""Codex 2026-10-08: isolated Dataset A access-control graph build."""
import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for directory in [REPO, REPO / "scripts", REPO / "scripts/labeling_v2"]:
    sys.path.insert(0, str(directory))
from label_rules import hit_records, verified_annotations
from line_mapping import build_line_map, preprocessed_to_original
from safe_graph import sha256, write_graph

CATEGORY = "access_control"
CORPUS = REPO / "experiments/ge-sc-data/source_code" / CATEGORY
PAPER = {"contracts": 114, "buggy_contracts": 57, "nodes": 13432,
         "edges": 15538, "positive_nodes": 2977}


def write_json(path, value):
    with path.open("x", encoding="utf8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def code_snapshot():
    """Hash pre-existing source/docs, excluding generated data and this folder."""
    excluded = {".git", "__pycache__", "vendor", "data", "experiments",
                "outputs", "models", "logs", "log", "build", ".pytest_cache"}
    hashes = {}
    for root, dirs, names in os.walk(str(REPO)):
        base = Path(root)
        dirs[:] = [d for d in dirs if d not in excluded and (base / d).resolve() != HERE]
        for name in names:
            path = base / name
            if path.suffix in {".py", ".sh", ".md", ".toml", ".yml", ".yaml"}:
                hashes[str(path.relative_to(REPO))] = sha256(path)
    return hashes


def validate_corpus(annotations):
    positive = {name for name, records in annotations.items() if records}
    legacy = {p.stem + ".sol" for p in (CORPUS / "cfg").glob("*.dot")}
    if len(annotations) != 114 or len(positive) != 57:
        raise ValueError("Expected Dataset A: 114 files / 57 annotated files")
    if legacy != positive:
        raise ValueError("Annotated membership differs from repository buggy CFG corpus: "
                         + repr(sorted(legacy ^ positive)))
    return [{"contract_name": name, "targets": int(name in positive)}
            for name in sorted(annotations)]


def attach_labels(graph, name, source, records):
    line_map = build_line_map(source)
    for _, data in graph.nodes(data=True):
        lines = data.get("node_source_code_lines")
        if not lines or any(type(n) is not int or n < 1 or n > len(line_map) for n in lines):
            raise ValueError("Invalid preprocessed coordinates: " + name)
        original = preprocessed_to_original(lines, line_map)
        data["node_source_code_lines_original"] = original
        data["node_info_vulnerabilities"] = hit_records(original, records, CATEGORY)
        if not isinstance(data.get("code"), str):
            raise ValueError("Missing node code: " + name)
    return graph


def parse_errors(root):
    errors, pending = [], [root]
    while pending:
        node = pending.pop()
        if node.type == "ERROR" or node.is_missing:
            errors.append({"type": node.type, "missing": bool(node.is_missing),
                           "preprocessed_start": list(node.start_point),
                           "preprocessed_end": list(node.end_point),
                           "text": node.text.decode("utf8", errors="replace")[:160]})
        pending.extend(reversed(node.children))
    return errors


def tokenize_graph(graph, model):
    import numpy as np
    from transformers import AutoTokenizer
    from encode_tokenizer_features import encode_ids
    tokenizer = AutoTokenizer.from_pretrained(
        model, local_files_only=True, trust_remote_code=False)
    pad = tokenizer.pad_token_id
    if pad is None:
        pad = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
    lengths, cache = [], {}
    for index, (_, data) in enumerate(graph.nodes(data=True), 1):
        code = data["code"]
        if code not in cache:
            ids = tokenizer(code, add_special_tokens=True).input_ids
            cache[code] = (encode_ids(ids, 512, pad), len(ids))
        vector, length = cache[code]
        data["token"] = vector.copy()
        lengths.append(length)
        if index % 1000 == 0 or index == len(graph):
            print("Tokenizing {}/{} nodes".format(index, len(graph)), flush=True)
    cache_root = Path(os.environ.get("HF_HUB_CACHE",
                      str(Path.home() / ".cache/huggingface/hub")))
    model_cache = cache_root / ("models--" + model.replace("/", "--"))
    ref = model_cache / "refs/main"
    revision = ref.read_text().strip() if ref.is_file() else None
    asset_hashes = {}
    if revision:
        for name in ["config.json", "tokenizer.json", "tokenizer_config.json",
                     "special_tokens_map.json", "spiece.model", "added_tokens.json",
                     "vocab.json", "merges.txt"]:
            path = model_cache / "snapshots" / revision / name
            if path.is_file():
                asset_hashes[str(path)] = sha256(path)
    return {"model": model, "tokenizer_class": type(tokenizer).__name__,
            "scheme": "ids", "feature_size": 512, "dtype": "float32",
            "add_special_tokens": True, "padding_id": int(pad),
            "tokenizer_vocab_size": len(tokenizer),
            "local_files_only": True, "model_weights_loaded": False,
            "resolved_cache_revision": revision, "asset_hashes": asset_hashes,
            "unique_code_snippets": len(cache),
            "truncated_nodes": sum(n > 512 for n in lengths),
            "mean_length": float(np.mean(lengths)), "median_length": float(np.median(lengths)),
            "p95_length": float(np.percentile(lengths, 95)), "max_length": max(lengths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=CORPUS / "source_files")
    parser.add_argument("--smartbugs", type=Path,
                        default=REPO / "data/smartbug-dataset/vulnerabilities.json")
    parser.add_argument("--solidifi-dir", type=Path,
                        default=REPO / "data/SolidiFI-benchmark/buggy_contracts/tx.origin")
    parser.add_argument("--output", type=Path, default=HERE / "artifacts/dataset_a_source_range_v1")
    parser.add_argument("--tokenizer", default="Salesforce/codet5p-770m",
                        choices=["Salesforce/codet5p-770m"])
    args = parser.parse_args()
    output = args.output.resolve()
    if HERE not in output.parents:
        raise ValueError("Outputs must stay inside scripts/access_control_test")
    if output.exists():
        raise FileExistsError("Choose a new --output; existing data is never overwritten: " + str(output))
    library = REPO / "build/linux-x86_64/my-languages.so"
    os.environ["TREE_SITTER_LIB_DIR"] = str(
        library.parent if library.is_file() else HERE / "cache/tree_sitter")
    output.mkdir(parents=True)
    started = datetime.now(timezone.utc).isoformat()
    write_json(output / "original_code_hashes.json", code_snapshot())
    names = sorted(p.name for p in args.source_dir.glob("*.sol"))
    annotations, provenance, inputs = verified_annotations(
        args.source_dir, names, args.smartbugs, args.solidifi_dir,
        CATEGORY, lambda path: json.loads(path.read_text(encoding="utf8")))
    for path in list(args.source_dir.glob("*.sol")) + list((CORPUS / "cfg").glob("*.dot")):
        inputs[str(path)] = sha256(path)
    entries = validate_corpus(annotations)
    write_json(output / "annotations.json", annotations)
    write_json(output / "source_provenance.json", provenance)
    write_json(output / "graph_labels.json", entries)
    print("Verified 114 sources: 57 access-control positives / 57 clean candidates", flush=True)

    import networkx as nx
    from process_graphs.tree_sitter_codeviews.codeviews.CFG.CFG_driver import CFGDriver
    from process_graphs.tree_sitter_codeviews.generator import _annotate_cfg_graph
    merged, files_report, failures = nx.MultiDiGraph(), [], []
    per_contract = output / "per_contract"
    per_contract.mkdir()
    with (output / "generator.log").open("x", encoding="utf8") as log:
        for index, name in enumerate(names, 1):
            source = (args.source_dir / name).read_text(encoding="utf8")
            try:
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    driver = CFGDriver("solidity", source, output_file=None)
                errors = parse_errors(driver.root_node)
                before = len(driver.graph)
                graph = _annotate_cfg_graph(driver.graph, name)
                attach_labels(graph, name, source, annotations[name])
                if not graph:
                    raise ValueError("Empty contract graph")
                graph = nx.convert_node_labels_to_integers(
                    graph, ordering="sorted", label_attribute="file_node_id")
                write_graph(graph, per_contract / (Path(name).stem + ".gpickle"))
                merged = nx.disjoint_union(merged, graph)
                files_report.append({"file": name, "nodes": len(graph),
                                     "edges": graph.number_of_edges(),
                                     "discarded_unannotatable_nodes": before - len(graph),
                                     "parse_has_error": bool(driver.root_node.has_error),
                                     "parse_errors": errors,
                                     "positive_nodes": sum(bool(d["node_info_vulnerabilities"])
                                                           for _, d in graph.nodes(data=True))})
                print("[{}/{}] {}: {} nodes / {} edges{}".format(
                    index, len(names), name, len(graph), graph.number_of_edges(),
                    " [parser warnings]" if errors else ""), flush=True)
            except Exception as exc:
                failures.append({"file": name, "error": repr(exc),
                                 "traceback": traceback.format_exc()})
                print("[{}/{}] FAILED {}: {}".format(index, len(names), name, exc), flush=True)
    write_json(output / "generation.json", {"files": files_report, "failures": failures})
    if failures:
        raise RuntimeError("Some files failed; no training dataset emitted")
    positive_files = {e["contract_name"] for e in entries if e["targets"]}
    actual = {d["source_file"] for _, d in merged.nodes(data=True) if d["node_info_vulnerabilities"]}
    if actual != positive_files:
        raise ValueError("Annotated contracts with no positive node: " + repr(sorted(positive_files ^ actual)))
    write_graph(merged, output / "hcg_labeled.gpickle")
    tokenizer_info = tokenize_graph(merged, args.tokenizer)
    keep = [n for n, d in merged.nodes(data=True) if d["source_file"] in positive_files]
    line = nx.convert_node_labels_to_integers(
        merged.subgraph(keep).copy(), ordering="sorted", label_attribute="original_node_id")
    full_path = output / "tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle"
    line_path = output / "linelevel_tokenizer_ids.gpickle"
    write_graph(merged, full_path)
    write_graph(line, line_path)
    manifest = {"created_utc": started, "modified_by_ai": "Codex", "dataset": "A",
                "category": CATEGORY, "source_dir": str(args.source_dir.resolve()),
                "source_policy": "original-source range overlap; access_control only",
                "solidifi_policy": "[loc, loc+length-1] inclusive",
                "graph_policy": "existing local tree-sitter CFG with call relations; narrow end_if",
                "clean_label_policy": "repository selected unannotated corpus; no independent absence proof",
                "tokenizer": tokenizer_info, "input_hashes": inputs, "paper_reference": PAPER,
                "builder_hashes": {p.name: sha256(p) for p in HERE.glob("*.py")},
                "generation": {"files": len(files_report), "failures": len(failures),
                               "parser_warning_files": sum(r["parse_has_error"] for r in files_report)},
                "artifact_hashes": {p.name: sha256(p) for p in [
                    full_path, line_path, output / "hcg_labeled.gpickle",
                    output / "graph_labels.json", output / "annotations.json",
                    output / "source_provenance.json", output / "generation.json"]}}
    write_json(output / "manifest.json", manifest)
    from audit_dataset import audit_dataset, write_report
    audit = audit_dataset(output)
    write_json(output / "audit.json", audit)
    write_report(output / "audit_report.md", audit)
    print("AUDIT {}: full {}/{}; line {}/{}; positive nodes {}".format(
        "PASS" if audit["passed"] else "FAIL",
        audit["contract_level"]["nodes"], audit["contract_level"]["edges"],
        audit["line_level"]["nodes"], audit["line_level"]["edges"],
        audit["line_level"]["positive_nodes"]), flush=True)
    print("Artifacts: " + str(output), flush=True)
    if not audit["passed"]:
        raise RuntimeError("Dataset audit failed; inspect audit.json")


if __name__ == "__main__":
    main()
