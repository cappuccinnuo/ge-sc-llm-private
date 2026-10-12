# Dataset A 权限控制图审计

AI：Codex；审计时间（UTC）：2026-10-08T11:55:14.284172+00:00

**自动数据一致性检查：通过**。
通过检查不代表已与作者全部标签或论文实验逐项一致。

| 项目 | 合约级输入 | 行级输入 |
|---|---:|---:|
| 合约文件 | 114 | 57 |
| 节点 | 13432 | 7710 |
| 边 | 15538 | 8840 |
| 漏洞节点 | 3236 | 3236 |

合约标签：57 个权限控制漏洞合约、57 个仓库选定良性候选合约。
行级图保留全部 57 个漏洞合约的节点与内部边，也包含正常节点。
特征：CodeT5p-770m tokenizer 原始 token ID，补齐/截断至 512；未加载 LLM 权重。

## 与论文 Table 1 的比较

| 项目 | 论文 | 本地 | 本地减论文 |
|---|---:|---:|---:|
| contracts | 114 | 114 | 0 |
| buggy_contracts | 57 | 57 | 0 |
| nodes | 13432 | 13432 | 0 |
| edges | 15538 | 15538 | 0 |
| positive_nodes | 2977 | 3236 | 259 |

标签使用原始源码范围与当前类别标注求交集；SolidiFI 使用完整 CSV 注入区间。
数量相同不等于节点、边类型和标注已与作者逐项对齐。

## 自动检查

- builder_scripts_match_manifest：PASS
- artifact_hashes_match_manifest：PASS
- source_and_annotation_inputs_unchanged：PASS
- pre_existing_code_and_docs_unchanged：PASS
- 114_contracts_57_buggy_57_clean：PASS
- all_source_files_represented：PASS
- all_annotated_contracts_are_positive：PASS
- line_graph_contains_all_57_buggy_contracts_only：PASS
- no_generation_failures：PASS
- graph_ids_contiguous：PASS
- all_edges_within_source_file：PASS
- tokenization_preserves_topology：PASS
- tokenization_preserves_non_feature_node_attributes：PASS
- tokenization_preserves_edge_attributes：PASS
- original_source_mapping_valid：PASS
- every_label_matches_original_source_range_overlap：PASS
- no_other_vulnerability_category_in_labels：PASS
- all_token_vectors_finite_float32_512：PASS
- all_nonblank_annotation_lines_represented：PASS
- each_annotation_record_hits_a_node：PASS
- line_graph_exact_buggy_induced_subgraph：PASS
- contract_training_label_reader_matches：PASS
- contract_level_training_node_labels_match：PASS
- contract_level_HGT_input_shapes_match：PASS
- line_level_training_node_labels_match：PASS
- line_level_HGT_input_shapes_match：PASS

## 边类型

```json
{
  "next": 8947,
  "recursive_method_call": 3723,
  "internal_call": 1036,
  "external_call": 1332,
  "if_true": 389,
  "if_false": 110,
  "jump_next": 1
}
```

## 标注与重复样本

整条记录未命中的数量：0。
没有图行号覆盖的标注行：52；详见 annotation_coverage。
行级代码跨合约重复的节点占比：68.26%；这不是实际折间泄漏率。

## 限制与待核验

- Labels reconstruct public SmartBugs JSON and SolidiFI CSV; not the authors' unpublished conversion.
- Clean labels inherit repository selection; original eleven-tool screening is not rerun.
- Existing call resolution / edge names are reused; correct resolution of every call is not proven.
- Generated inputs are not a trained two-phase detector.
- 52 annotated lines have no mapped graph line (52 blank); inspect coverage.

## 同标注端点对照（仅用于诊断）

相同公开标注和原始源码坐标下，仅检查起止行得到 3114 个正类节点，比范围规则减少 122，仍比论文多 137。
该对照没有修改训练图，也不是已确认的作者标注算法。

recursive_method_call 的源节点类型统计：{"contract_declaration": 3190, "library_declaration": 320, "interface_declaration": 213}；这些边从声明节点发出，不能将名称理解为真实递归调用。


原有代码/文档哈希核验数量：127；未改动检查：True。
