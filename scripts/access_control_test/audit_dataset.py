"""Codex 2026-10-08: audit isolated access-control datasets without training."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for directory in [REPO, REPO / "scripts", REPO / "scripts/labeling_v2"]:
    sys.path.insert(0, str(directory))
from label_rules import hit_records, parse_records
from line_mapping import build_line_map, preprocessed_to_original
from safe_graph import read_graph, sha256


def read_json(path):
    return json.loads(path.read_text(encoding="utf8"))


def stats(graph):
    return {"nodes": len(graph), "edges": graph.number_of_edges(),
            "contracts": len({d["source_file"] for _, d in graph.nodes(data=True)}),
            "positive_nodes": sum(bool(parse_records(d.get("node_info_vulnerabilities")))
                                  for _, d in graph.nodes(data=True)),
            "node_types": dict(Counter(d["node_type"] for _, d in graph.nodes(data=True))),
            "edge_types": dict(Counter(d["edge_type"] for _, _, d in graph.edges(data=True)))}


def duplicate_stats(graph):
    snippets = defaultdict(list)
    for n, d in graph.nodes(data=True):
        snippets[d["code"]].append((n, d["source_file"], bool(d["node_info_vulnerabilities"])))
    cross = [items for items in snippets.values() if len({x[1] for x in items}) > 1]
    count = sum(len(items) for items in cross)
    return {"exact_code_groups": len(snippets), "code_groups_across_multiple_contracts": len(cross),
            "nodes_in_cross_contract_code_groups": count,
            "percent_nodes_in_cross_contract_code_groups": 100.0 * count / len(graph),
            "cross_contract_groups_with_conflicting_labels": sum(
                len({x[2] for x in items}) > 1 for items in cross),
            "interpretation": "Exact-code repetition, not measured fold leakage or F1."}


def audit_dataset(output):
    import numpy as np
    manifest = read_json(output / "manifest.json")
    annotations = read_json(output / "annotations.json")
    entries = read_json(output / "graph_labels.json")
    baseline = read_json(output / "original_code_hashes.json")
    generation = read_json(output / "generation.json")
    source_dir = Path(manifest["source_dir"])
    full = read_graph(output / "tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle")
    line = read_graph(output / "linelevel_tokenizer_ids.gpickle")
    raw = read_graph(output / "hcg_labeled.gpickle")
    expected_files = {e["contract_name"] for e in entries}
    positive_files = {e["contract_name"] for e in entries if e["targets"]}
    checks, failures = {}, []

    def check(name, condition, detail=None):
        checks[name] = bool(condition)
        if not condition:
            failures.append({"check": name, "detail": detail})

    check("builder_scripts_match_manifest", all(
        (HERE / name).is_file() and sha256(HERE / name) == digest
        for name, digest in manifest.get("builder_hashes", {}).items()))
    check("artifact_hashes_match_manifest", all(
        (output / name).is_file() and sha256(output / name) == digest
        for name, digest in manifest["artifact_hashes"].items()))
    check("source_and_annotation_inputs_unchanged", all(
        Path(name).is_file() and sha256(Path(name)) == digest
        for name, digest in manifest["input_hashes"].items()))
    from build_dataset import code_snapshot
    check("pre_existing_code_and_docs_unchanged", baseline == code_snapshot())
    check("114_contracts_57_buggy_57_clean", len(entries) == 114
          and len(positive_files) == 57 and len(expected_files) == 114)
    check("all_source_files_represented", expected_files
          == {p.name for p in source_dir.glob("*.sol")}
          == {d["source_file"] for _, d in full.nodes(data=True)})
    check("all_annotated_contracts_are_positive", positive_files
          == {name for name, rs in annotations.items() if rs}
          == {d["source_file"] for _, d in full.nodes(data=True) if d["node_info_vulnerabilities"]})
    check("line_graph_contains_all_57_buggy_contracts_only", positive_files
          == {d["source_file"] for _, d in line.nodes(data=True)})
    check("no_generation_failures", not generation["failures"])
    check("graph_ids_contiguous", list(full) == list(range(len(full)))
          and list(line) == list(range(len(line))))
    check("all_edges_within_source_file", all(
        full.nodes[s]["source_file"] == full.nodes[t]["source_file"] for s, t in full.edges()))
    check("tokenization_preserves_topology", list(raw) == list(full)
          and Counter(raw.edges(keys=True)) == Counter(full.edges(keys=True)))
    check("tokenization_preserves_non_feature_node_attributes", all(
        d == {k: v for k, v in full.nodes[n].items() if k != "token"}
        for n, d in raw.nodes(data=True)))
    check("tokenization_preserves_edge_attributes", all(
        d == full.edges[s, t, key] for s, t, key, d in raw.edges(keys=True, data=True)))
    mappings = {name: build_line_map((source_dir / name).read_text(encoding="utf8"))
                for name in expected_files}
    bad_coordinates, bad_labels, other_categories, bad_tokens = [], [], [], []
    endpoint_positives, endpoint_differences = 0, Counter()
    covered, statement_covered = defaultdict(set), defaultdict(set)
    parents = {"contract_declaration", "library_declaration", "interface_declaration",
               "function_definition", "modifier_definition", "constructor_definition",
               "struct_declaration", "end_if", "end_loop"}
    for n, d in full.nodes(data=True):
        name, pre, original = (d["source_file"], d["node_source_code_lines"],
                               d["node_source_code_lines_original"])
        if (not pre or any(type(x) is not int or x < 1 or x > len(mappings[name]) for x in pre)
                or original != preprocessed_to_original(pre, mappings[name])):
            bad_coordinates.append(n)
        if hit_records(original, annotations[name], "access_control") != d["node_info_vulnerabilities"]:
            bad_labels.append(n)
        if any(r["category"] != "access_control" for r in parse_records(d["node_info_vulnerabilities"])):
            other_categories.append(n)
        v = np.asarray(d["token"])
        if (v.shape != (512,) or v.dtype != np.float32 or not np.isfinite(v).all()
                or np.any(v < 0) or np.any(v >= manifest["tokenizer"]["tokenizer_vocab_size"])
                or np.any(v != np.floor(v))):
            bad_tokens.append(n)
        endpoint_label = bool(hit_records(
            [min(original), max(original)] if original else [],
            annotations[name], "access_control"))
        endpoint_positives += int(endpoint_label)
        if endpoint_label != bool(d["node_info_vulnerabilities"]):
            endpoint_differences[d["node_type"]] += 1
        covered[name].update(original)
        if d["node_type"] not in parents:
            statement_covered[name].update(original)
    check("original_source_mapping_valid", not bad_coordinates, bad_coordinates[:20])
    check("every_label_matches_original_source_range_overlap", not bad_labels, bad_labels[:20])
    check("no_other_vulnerability_category_in_labels", not other_categories, other_categories[:20])
    check("all_token_vectors_finite_float32_512", not bad_tokens, bad_tokens[:20])
    coverage, unmatched_records = [], []
    for name, records in sorted(annotations.items()):
        if not records:
            continue
        wanted = {n for r in records for n in r["lines"]}
        unmatched_records.extend({"file": name, "record": r} for r in records
                                 if not covered[name].intersection(r["lines"]))
        coverage.append({"file": name, "annotated_lines": len(wanted),
                         "lines_covered_by_any_node": len(wanted & covered[name]),
                         "lines_covered_by_non_parent_nodes": len(wanted & statement_covered[name]),
                         "lines_not_represented_by_any_node": sorted(wanted - covered[name])})
    missing_line_details = []
    for row in coverage:
        text = (source_dir / row["file"]).read_text(encoding="utf8").splitlines()
        for n in row["lines_not_represented_by_any_node"]:
            missing_line_details.append({"file": row["file"], "line": n,
                                         "blank": not text[n-1].strip(),
                                         "source": text[n-1]})
    check("all_nonblank_annotation_lines_represented",
          all(r["blank"] for r in missing_line_details), missing_line_details[:10])
    check("each_annotation_record_hits_a_node", not unmatched_records, unmatched_records[:10])
    selected = {n for n, d in full.nodes(data=True) if d["source_file"] in positive_files}
    origins = {n: d["original_node_id"] for n, d in line.nodes(data=True)}
    line_matches = set(origins.values()) == selected and len(set(origins.values())) == len(line)
    if line_matches:
        for n, d in line.nodes(data=True):
            f = full.nodes[origins[n]]
            attrs = {k: v for k, v in d.items() if k not in {"token", "original_node_id"}}
            original_attrs = {k: v for k, v in f.items() if k != "token"}
            if attrs != original_attrs or not np.array_equal(d["token"], f["token"]):
                line_matches = False
        expected_edges = Counter((s, t, k, d["edge_type"])
                                 for s, t, k, d in full.edges(keys=True, data=True)
                                 if s in selected and t in selected)
        actual_edges = Counter((origins[s], origins[t], k, d["edge_type"])
                               for s, t, k, d in line.edges(keys=True, data=True))
        line_matches = line_matches and actual_edges == expected_edges
    check("line_graph_exact_buggy_induced_subgraph", line_matches)
    import torch
    import dgl
    torch.set_num_threads(1)
    from sco_models.graph_utils import (add_hetero_ids, generate_hetero_graph_data,
                                       get_number_of_nodes, get_node_label, get_node_token)
    from sco_models.dataloader import EthIdsDataset
    ds = EthIdsDataset(str(output / "graph_labels.json"), raw_dir=str(output / "dgl_cache"))
    check("contract_training_label_reader_matches", len(ds) == 114
          and ds.graphs == [e["contract_name"] for e in entries]
          and ds.label.tolist() == [e["targets"] for e in entries])
    consumers = {}
    for tag, graph in [("contract_level", full), ("line_level", line)]:
        actual, _, _ = get_node_label(graph)
        check(tag + "_training_node_labels_match",
              actual == [int(bool(d["node_info_vulnerabilities"])) for _, d in graph.nodes(data=True)])
        g = add_hetero_ids(graph.copy())
        hg = dgl.heterograph(generate_hetero_graph_data(g), num_nodes_dict=get_number_of_nodes(g))
        features = get_node_token(g)
        check(tag + "_HGT_input_shapes_match",
              all(tuple(features[t].shape) == (hg.num_nodes(t), 512) for t in hg.ntypes)
              and hg.num_nodes() == len(graph) and hg.num_edges() == graph.number_of_edges())
        consumers[tag] = {"canonical_relation_types": len(hg.canonical_etypes),
                          "nodes": hg.num_nodes(), "edges": hg.num_edges(),
                          "feature_shapes": {t: list(features[t].shape) for t in hg.ntypes}}
    comparison, actual = {}, stats(full)
    for key, val in manifest["paper_reference"].items():
        observed = len(positive_files) if key == "buggy_contracts" else actual[key]
        comparison[key] = {"paper": val, "local": observed, "difference": observed - val}
    warnings = [
        "Labels reconstruct public SmartBugs JSON and SolidiFI CSV; not the authors' unpublished conversion.",
        "Clean labels inherit repository selection; original eleven-tool screening is not rerun.",
        "Existing call resolution / edge names are reused; correct resolution of every call is not proven.",
        "Generated inputs are not a trained two-phase detector."]
    warning_files = [r for r in generation["files"] if r["parse_has_error"]]
    if warning_files:
        warnings.append("Parser ERROR/missing nodes in {} files; inspect generation.json."
                        .format(len(warning_files)))
    missing_lines = sum(len(r["lines_not_represented_by_any_node"]) for r in coverage)
    if missing_lines:
        warnings.append("{} annotated lines have no mapped graph line ({} blank); inspect coverage."
                        .format(missing_lines, sum(r["blank"] for r in missing_line_details)))
    call_origins = Counter(full.nodes[s]["node_type"] for s, _, d in full.edges(data=True)
                           if d["edge_type"] == "recursive_method_call")
    return {"created_utc": datetime.now(timezone.utc).isoformat(), "modified_by_ai": "Codex",
            "passed": all(checks.values()), "category": "access_control", "dataset": "A",
            "checks": checks, "failures": failures, "contract_level": actual, "line_level": stats(line),
            "contract_labels": {"buggy": len(positive_files), "clean": len(expected_files - positive_files)},
            "paper_table_1_comparison": comparison, "annotation_coverage": coverage,
            "unmatched_records": unmatched_records, "unrepresented_annotation_lines": missing_lines,
            "unrepresented_annotation_line_details": missing_line_details,
            "training_consumers": consumers, "tokenizer": manifest["tokenizer"],
            "line_level_duplicates": duplicate_stats(line),
            "inherited_recursive_method_call_source_types": dict(call_origins),
            "source_range_endpoint_counterfactual": {
                "positive_nodes": endpoint_positives,
                "changed_nodes": sum(endpoint_differences.values()),
                "changed_node_types": dict(endpoint_differences),
                "difference_vs_paper": endpoint_positives - manifest["paper_reference"]["positive_nodes"],
                "interpretation": "Same public annotations / original coordinates, endpoints only. "
                                  "Diagnostic only; not the authors confirmed labeling algorithm."},
            "parser_warning_files": [r["file"] for r in warning_files],
            "pre_existing_code_files_hashed": len(baseline), "warnings": warnings}


def write_report(path, audit):
    full, line = audit["contract_level"], audit["line_level"]
    rows = ["# Dataset A 权限控制图审计", "",
            "AI：Codex；审计时间（UTC）：" + audit["created_utc"], "",
            "**自动数据一致性检查：" + ("通过" if audit["passed"] else "失败") + "**。",
            "通过检查不代表已与作者全部标签或论文实验逐项一致。", "",
            "| 项目 | 合约级输入 | 行级输入 |", "|---|---:|---:|"]
    for label, key in [("合约文件", "contracts"), ("节点", "nodes"),
                       ("边", "edges"), ("漏洞节点", "positive_nodes")]:
        rows.append("| {} | {} | {} |".format(label, full[key], line[key]))
    rows += ["", "合约标签：57 个权限控制漏洞合约、57 个仓库选定良性候选合约。",
             "行级图保留全部 57 个漏洞合约的节点与内部边，也包含正常节点。",
             "特征：CodeT5p-770m tokenizer 原始 token ID，补齐/截断至 512；未加载 LLM 权重。", "",
             "## 与论文 Table 1 的比较", "",
             "| 项目 | 论文 | 本地 | 本地减论文 |", "|---|---:|---:|---:|"]
    for key, value in audit["paper_table_1_comparison"].items():
        rows.append("| {} | {} | {} | {} |".format(
            key, value["paper"], value["local"], value["difference"]))
    rows += ["", "标签使用原始源码范围与当前类别标注求交集；SolidiFI 使用完整 CSV 注入区间。",
             "数量相同不等于节点、边类型和标注已与作者逐项对齐。", "",
             "## 自动检查", ""]
    rows.extend("- {}：{}".format(name, "PASS" if passed else "FAIL")
                for name, passed in audit["checks"].items())
    rows += ["", "## 边类型", "", "```json",
             json.dumps(full["edge_types"], ensure_ascii=False, indent=2), "```", "",
             "## 标注与重复样本", "",
             "整条记录未命中的数量：{}。".format(len(audit["unmatched_records"])),
             "没有图行号覆盖的标注行：{}；详见 annotation_coverage。"
             .format(audit["unrepresented_annotation_lines"]),
             "行级代码跨合约重复的节点占比：{:.2f}%；这不是实际折间泄漏率。"
             .format(audit["line_level_duplicates"]["percent_nodes_in_cross_contract_code_groups"]),
             "", "## 限制与待核验", ""]
    rows.extend("- " + text for text in audit["warnings"])
    endpoint = audit["source_range_endpoint_counterfactual"]
    rows += ["", "## 同标注端点对照（仅用于诊断）", "",
             "相同公开标注和原始源码坐标下，仅检查起止行得到 {} 个正类节点，"
             "比范围规则减少 {}，仍比论文多 {}。".format(
                 endpoint["positive_nodes"], endpoint["changed_nodes"],
                 endpoint["difference_vs_paper"]),
             "该对照没有修改训练图，也不是已确认的作者标注算法。",
             "", "recursive_method_call 的源节点类型统计：" +
             json.dumps(audit["inherited_recursive_method_call_source_types"], ensure_ascii=False) +
             "；这些边从声明节点发出，不能将名称理解为真实递归调用。", ""]

    rows += ["", "原有代码/文档哈希核验数量：{}；未改动检查：{}。".format(
        audit["pre_existing_code_files_hashed"], audit["checks"]["pre_existing_code_and_docs_unchanged"]), ""]
    path.write_text("\n".join(rows), encoding="utf8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=HERE / "artifacts/dataset_a_source_range_v1")
    p.add_argument("--report-prefix", default="audit_recheck")
    args = p.parse_args()
    output = args.input.resolve()
    if HERE not in output.parents or Path(args.report_prefix).name != args.report_prefix:
        raise ValueError("Reports must stay inside this test directory")
    audit = audit_dataset(output)
    (output / (args.report_prefix + ".json")).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    write_report(output / (args.report_prefix + ".md"), audit)
    print("AUDIT {}: {}".format("PASS" if audit["passed"] else "FAIL", output), flush=True)
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
