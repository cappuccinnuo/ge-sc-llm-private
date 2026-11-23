"""Build one category end to end and record what was built.

    [composed dataset: assemble the corpus from the committed composition]
    corpus .sol -> CFG + call graph (authors' format) -> annotations -> node labels
                -> contract labels -> line-level subset -> [tokens] -> files + manifest
                -> [comparison with the dataset's reference graphs and counts]
"""
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

import hcg
from hcg import verify
from hcg.cfg import build_corpus
from hcg.features import tokens as token_features
from hcg.labels import contract_entries, label_nodes, line_level, project_annotations, reached_summary
from hcg.sources import annotations as annotation_source
from hcg.sources import composition, repos
from hcg.store import CategoryOutput, dump_json, read_gpickle, sha256, write_gpickle

REPO = Path(__file__).resolve().parents[1]


def build_category(dataset, category, out_root, label_root, tokenizer=None, log=print):
    """Build, write and (if the dataset has one) compare; return the manifest dict."""
    category = dataset.category(category) if isinstance(category, str) else category
    out = CategoryOutput(Path(out_root) / dataset.name / category.name)
    corpus_dir = dataset.corpus(REPO, category.name)
    label_commits = repos.verify(label_root, dataset.sources)
    composed = composition.load(REPO / dataset.composition) if dataset.composition else None
    if composed is not None:
        if composed["sources"] != label_commits:
            raise SystemExit("%s was composed from other source commits" % dataset.composition)
        composition.assemble(composed, category.name, label_root, corpus_dir)
    files = sorted(corpus_dir.glob("*.sol"))
    if not files:
        raise SystemExit("no .sol files under %s" % corpus_dir)
    filenames = [p.name for p in files]

    log("[%s/%s] graphs: %d contracts" % (dataset.name, category.name, len(files)))
    graph, failures = build_corpus(files)
    if failures:
        raise SystemExit("could not parse %d contracts: %s" % (len(failures), failures[:5]))

    log("[%s/%s] labels" % (dataset.name, category.name))
    if composed is not None:
        targets = composition.targets(composed, category.name)
        records, sources, provenance = annotation_source.load_composed(
            corpus_dir, category, composition.entries(composed, category.name), label_root)
    else:
        smartbugs = annotation_source.load_smartbugs(label_root)
        targets = dataset.contract_labeler(category.name, filenames, smartbugs)
        records, sources, provenance = annotation_source.load(
            corpus_dir, category, filenames, targets, label_root, smartbugs)
    projected, texts = project_annotations(records, sources)
    positives, reached = label_nodes(graph, projected, texts, dataset.node_labels)
    entries = contract_entries(targets)
    lines, line_ids = line_level(graph, targets)

    token_info = None
    if tokenizer is not None:
        log("[%s/%s] tokens" % (dataset.name, category.name))
        longest, truncated = token_features.add_tokens(graph, tokenizer)
        for new, old in enumerate(line_ids):
            lines.nodes[new]["token"] = graph.nodes[old]["token"]
        token_info = {"tokenizer": token_features.TOKENIZER,
                      "revision": token_features.REVISION, "width": token_features.WIDTH,
                      "max_length": longest, "truncated_nodes": truncated}

    write_gpickle(graph, out.contract_level)
    write_gpickle(lines, out.line_level)
    dump_json(out.graph_labels, entries)
    dump_json(out.annotations, {"original": records, "preprocessed": projected})
    dump_json(out.line_node_ids, line_ids)

    manifest = {
        "hcg_version": hcg.__version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": dataset.name, "category": category.name,
        "corpus": {"directory": str(corpus_dir.relative_to(REPO)), "contracts": len(files),
                   "vulnerable_contracts": sum(targets.values()),
                   **({"composition": dataset.composition,
                       "composition_sha256": sha256(REPO / dataset.composition),
                       "by_source": _by_source(composition.entries(composed, category.name))}
                      if composed is not None else {})},
        "label_policy": dataset.label_policy,
        "node_label_rule": dataset.node_labels,
        "annotated_lines_reached": reached_summary(reached, None if composed is None else {
            r["name"]: r["source"] for r in composition.entries(composed, category.name)}),
        "label_sources": label_commits,
        "contract_level": _stats(graph, positives),
        "line_level": _stats(lines, positives_of(lines)),
        "tokens": token_info,
        "source_provenance": provenance,
        "environment": {"python": platform.python_version(), "networkx": nx.__version__},
    }
    manifest["checks"] = _checks(dataset, category.name, manifest, graph, entries, log)
    manifest["output_sha256"] = {p.name: sha256(p) for p in (
        out.contract_level, out.line_level, out.graph_labels, out.annotations,
        out.line_node_ids)}
    dump_json(out.manifest, manifest)
    return manifest


def positives_of(graph):
    return sum(verify.is_positive(d.get(verify.LABEL)) for _, d in graph.nodes(data=True))


def _stats(graph, positives):
    edge_types = {}
    for _, _, data in graph.edges(data=True):
        edge_types[data["edge_type"]] = edge_types.get(data["edge_type"], 0) + 1
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(),
            "contracts": len({d["source_file"] for _, d in graph.nodes(data=True)}),
            "positive_nodes": positives, "edge_types": dict(sorted(edge_types.items()))}


def _by_source(rows):
    counts = {}
    for row in rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    return dict(sorted(counts.items()))


def _checks(dataset, name, manifest, graph, entries, log):
    checks = {"failures": []}
    got = {"contracts": manifest["corpus"]["contracts"],
           "vulnerable_contracts": manifest["corpus"]["vulnerable_contracts"],
           "nodes": manifest["contract_level"]["nodes"],
           "edges": manifest["contract_level"]["edges"],
           "positive_nodes": manifest["contract_level"]["positive_nodes"]}
    reported = dataset.reported.get(name)
    if reported:
        checks["paper_counts"] = {k: {"paper": v, "built": got[k]} for k, v in reported.items()}
    expected = dataset.expected.get(name)
    if expected:
        checks["expected_counts"] = {k: {"expected": v, "built": got[k]}
                                     for k, v in expected.items()}
        checks["failures"] += ["%s: expected %s, built %s" % (k, v, got[k])
                               for k, v in expected.items() if got[k] != v]
    graph_path, labels_path = dataset.reference(REPO, name)
    if graph_path is not None and graph_path.exists():
        log("[%s/%s] comparing with %s" % (dataset.name, name, graph_path.name))
        report = verify.compare(graph, read_gpickle(graph_path))
        report["contract_label_differences"] = verify.compare_contract_labels(
            entries, json.loads(labels_path.read_text(encoding="utf8")))
        report["reference"] = str(graph_path.relative_to(REPO))
        checks["reference"] = report
        if not report["structure_identical"]:
            checks["failures"].append("structure differs from the reference graph")
        if report["contract_label_differences"]:
            checks["failures"].append("contract labels differ from the reference")
    return checks
