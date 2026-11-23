# cp4_3_review_v1：CP4.3 审查证据（Claude，2026-11-23）

审查对象：`compile-repair@868d814c9`（Codex 的 CP4.3：`evaluation/benchmark.py` 增 81 行、删 35 行，`tests/test_cp43.py`，`tests/test_cp42.py` 的分母断言，产物 `cp4_3_v1/`，CP4_REPORT 的 CP4.3 节、四份记录与 CHANGE_LOG §49）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12，Slither 0.11.6 + crytic-compile 0.4.2，solc 0.8.38（GitHub 发布的静态构建）。

## 文件

| 文件 | 内容 |
|---|---|
| `probe_yul_switch.py` / `.json` | 含两个（嵌套）switch 的内联汇编函数；破坏删除其后的 `h()`。修复 A 把 `h()` 插到合约开头；B 另在汇编块内 switch 前加一行注释；C（故意错误）另改一个 case 常量 |
| `probe_partial_change.py` / `.json` | 破坏删除 `h()`。修复 A 把 `h()` 插到开头；B 为 A 加上改动 `k()` 中的一个常量（真实改动一个 kept 节点）；C 原位恢复 `h()` 并改同一个常量 |

## 结论

1. **成立的部分**
   - kept 分母恢复 CP4 定义：重跑 `../cp4_2_review_v1/probe_repair_deletes_kept.py`，kept 2/7、边 1/6、调用 1/2、missing_kept 与 removed_by_repair 都为 5、lost 2、exact false，surviving 三个比例为 1。CP4.1 的插到开头夹具 kept 2/2、removed_by_repair 0，名称状态 verified。
   - Yul switch 起点：独立夹具中两个 switch 名称（`switch_expr_122_144_0_f_asm_0`、`switch_expr_199_53_0_f_asm_0`）随插入平移；修复 A 的 kept 由原分 11/16 对齐为 16/16，记录 2 个 switch。故意错误 C 被拒绝（`switch_span_not_preserved`），kept 11/16，exact false。
   - 移动自检：由 `cp4_3_v1/moves.jsonl.gz` 重算，200 项，removed_by_repair 合计 933，逐项等于 expected_moved_nodes；surviving 三个比例为 1 的 199 项；唯一例外 cp3_00291（创建码哈希常量，已知限制）。
   - 精确还原 14,196 与迁移 114 的主指标、exact 不变，removed_by_repair 为 0（`exact_summary.json`、`migration_summary.json`）。
   - 测试：审查环境运行 `test_cp43.py`、`test_cp42.py`、`test_cp41.py`、`test_benchmark.py`，276 项通过、4 项跳过。
2. **未解决的问题：生成名称对应“一处不符即整体放弃”，评分不成比例**（`probe_partial_change.json`）。
   - 修复 A：kept 7/7（verified）。修复 B 只多改了 `k()` 中的一个节点，kept 却降到 3/7（rejected，`ir_operation_type_or_operand_differ`）：一个真实改动使全部编号平移的节点都按原分计为不相等。同样的改动在原位恢复（C）时为 6/7。
   - 修复 B 的汇编块内加注释也是如此：该节点长度改变，对应整体放弃，kept 11/16（`probe_yul_switch.json`）。
   - 来源是 r2.18 §4.6c 的规则“只要有一个 kept 节点不满足，就整体不改名”，Codex 照此实现。这条规则不会高估分数，但会使分数随一个无关改动跳变；CP5–CP10 要比较不同修复方法与消融，修复常常既插入代码又改动个别语句，这样的跳变会扭曲比较。
   - 另外，没有任何改名、只是有节点不同的修复（C）状态也记为 rejected，容易误读。
3. **接受的已知限制**：cp3_00291 的创建码哈希常量；declaration_error 0 个样本。

## 处理

CP4.4（PROMPTS §4.6e）：把对应关系改为“只用结构一致的 kept 节点推导，不一致的节点排除并按原样比较”，冲突与无法核验定义的名称只排除相关节点；Yul switch 同样处理；状态区分 identical、verified、partial 与 rejected。

## 复现

```bash
python3 -I probe_partial_change.py <repo> <solc-0.8.38 路径>
python3 -I probe_yul_switch.py <repo> <solc-0.8.38 路径>
```
