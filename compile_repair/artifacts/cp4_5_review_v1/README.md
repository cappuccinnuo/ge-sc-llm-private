# cp4_5_review_v1：CP4.5 审查证据（Claude，2026-11-23）

审查对象：`compile-repair@0b5fd600b`（Codex 的 CP4.5：`evaluation/benchmark.py` 增 119 行、删 82 行，新增 `_bound_reference_write`、`_ordinary_definition`、`_definition_anchors`，删除 `_prune_name_nodes`；`tests/test_cp45.py` 与 CP4.2–CP4.4 测试断言的更新；产物 `cp4_5_v1/` 与 `cp4_5_v1/continuation/`；CP4_REPORT 的 CP4.5 节、四份记录与 CHANGE_LOG §53）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12，Slither 0.11.6 + crytic-compile 0.4.2，solc 0.8.38。

## 文件

| 文件 | 内容 |
|---|---|
| `rerun_review_probes.json` | 在 CP4.5 评分器上重跑 CP4.1–CP4.4 审查的全部探针（`../cp4_1_review_v1/probe_counter_shift.py`、`../cp4_2_review_v1/probe_repair_deletes_kept.py`、`../cp4_3_review_v1/probe_partial_change.py`、`../cp4_3_review_v1/probe_yul_switch.py`、`../cp4_4_review_v1/probe_stale_name.py`） |

## 结论

1. **CP4.4 审查的问题已正确解决。**
   - 旧名场景：正确平移 3/3，一个旧名 2/3，三个旧名 2/5（CP4.4 为 4/5），未平移错用 2/3，都等于真正正确的节点数，没有高估。一个旧名场景的名称核验记录 TMP_4 → TMP_8、TMP_5 → TMP_9，name_mismatch 为 1，即被判为不一致的是保留旧名的使用节点。
   - 其余探针结果不变：中性插入 7/7，插入并改一个常量 6/7，原位恢复加改动 6/7；Yul 插入与加注释 16/16，改错 case 常量 14/16；删除未破坏函数 kept 2/7、removed_by_repair 5；插到开头 2/2。
   - 代码：`_ordinary_correspondence` 返回被判为相等的节点集合，`_score_facts` 用它计数，不再对不一致节点做原样比较；参与推导只比较节点类型与 IR（不含 length），与主指标一致。
2. **数据核对。** 由 `cp4_4_v1/moves.jsonl.gz` 与 `cp4_5_v1/continuation/moves.jsonl.gz` 逐项比较 kept、边、调用、surviving、removed_by_repair、exact 与 raw，200 项全部相同；`continuation/exact.jsonl.gz` 14,196 项全部 exact、kept 为 1、removed_by_repair 为 0、状态 identical。测试：审查环境运行 `test_cp45.py` 到 `test_benchmark.py` 共 301 项通过、5 项跳过。
3. **首轮停点的处理正确。** 首轮 678 项精确还原与 4 项移动不等，原因是 SlithIR 的写回形式（`REF_n (->目标) :=`、引用数组初始化、`delete REF_n`）看起来像定义，同一名称出现多次“定义”而成为争议。Codex 停下、逐处核对、经用户两次批准只识别这三种形式，并保留首轮结果另建续跑。精确还原覆盖的是真实语料的图，这一结果说明在这些图中没有其他未识别的写法。
4. **带入 CP5 的两项限制（不阻塞）。**
   - 写回形式按观察到的写法识别。未覆盖的写法只会让相同的图被判为不相等（低估），不会高估。精确还原只覆盖被抽样的基础单元，CP5 第 0 节先在全部 16,136 个基础单元上做真值自比核验。
   - 源码中出现生成名称（例如标识符 `TMP_4`）时整项退回原分，这时原样比较仍可能高估。这种情况很少，CP5 报告中单列 rejected 状态的数量与原因。

## 结论与下一步

CP4.5 成立，CP4 系列结束。PROMPTS r2.22 新增 4.6g 节 CP5 的完整提示。
