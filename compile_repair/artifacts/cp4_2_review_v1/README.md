# cp4_2_review_v1：CP4.2 审查证据（Claude，2026-11-22）

审查对象：`compile-repair@1bb69b7ff`（Codex 的 CP4.2：提交 387bb0040、1bb69b7ff；`evaluation/benchmark.py` 增 63 行、删 20 行，`tests/test_cp42.py`，产物 `cp4_2_v1/`，CP4_REPORT 的 CP4.2 节、四份记录与 CHANGE_LOG §47）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12，Slither 0.11.6 + crytic-compile 0.4.2，solc 0.8.38（GitHub 发布的静态构建）。“CP4.2 之前”的评分器取自 `30df6664b` 的只读工作树，用后删除。

## 文件

| 文件 | 内容 |
|---|---|
| `probe_repair_deletes_kept.py` / `.json` | 用模块自己的 `graph_facts` 与 `score_graphs`：破坏删除 `h()`，修复原位恢复 `h()`，同时删除一个未破坏的函数 `u()`（5 个节点）；分别用 CP4.2 之前与之后的评分器打分 |

## 结论

1. **成立的部分**
   - 生成名称对应已推广到所有评分，只用 kept 且存在的节点推导，条件与迁移相同，任一失败整体使用原分；raw 并列保留。审查夹具（`../cp4_1_review_v1/probe_counter_shift.py`）在新评分器下插到开头的修复 kept 为 2/2。
   - 重算：精确还原 14,196/14,196 全部 identical，与 CP4.1 相同；迁移 114/114 原分与全图分相同（kept 推导 58 identical、56 verified，与 CP4.1 的 53/61 之差由 7 个此前未计入的未改名元组解释，`migration_summary.json`）。
   - 移动自检 200 项：198 项 kept、边、调用改名后为 1；2 项低分有实测原因（cp3_00291 合约对嵌入创建码求 Keccak-256，元数据变化使哈希常量改变；cp3_21529 的 Yul switch 名称含源码起点，后移两字节）。
   - 测试：审查环境运行 `test_cp42.py`、`test_cp41.py`、`test_benchmark.py`，275 项通过、2 项跳过。
2. **新问题：修复删除未破坏的原代码时，kept、边与调用比例仍为 1**（`probe_repair_deletes_kept.json`）。
   - CP4.2 在 `_score_facts` 中加入：未破坏的真值节点若其字节被修复删除，计入 lost，不再进入 kept 分母。它的来源是 r2.18 §4.6c 的移动自检要求“被移动函数的节点计为 lost”，这句要求写得不准确，Codex 把它实现成了所有评分的通用规则。
   - 实测：修复删除了 5 个节点的 `u()`。CP4.2 之前 kept 2/7、边 1/6、调用 1/2、missing_kept 5；CP4.2 之后 kept 2/2、边 1/1、调用 1/1、missing_kept 0，删除只体现在 lost（7 = 破坏区 2 + 修复删除 5）中，exact 仍为 false。
   - 影响：CP5 以后最需要发现的错误之一就是“为了编译通过删掉原代码”。主指标 kept、边与调用在这种情况下不再下降，lost 又混合了破坏区节点与修复删除的节点，无法区分。
3. **可以解决的已知低分：Yul switch 名称中的源码起点。** 名称形如 `switch_expr_<起点>_<长度>_<源编号>_<函数>_asm_<n>`；起点可以用评分已有的组合偏移映射从真值坐标映射到修复坐标（与节点起点的映射相同）。CP5 的修复经常在汇编块之前插入字节，这类低分会重复出现。
4. **接受的已知限制：对嵌入创建码求哈希的常量。** 哈希值无法规范化；用户已决定按实测低分计入。CP5 报告中单列这类样本。

## 处理

CP4.3（PROMPTS §4.6d）：恢复 kept 分母的 CP4 定义，新增“修复删除的未破坏节点”计数与“存活节点”诊断指标；Yul switch 起点按组合偏移映射对齐；重算移动自检并把审查探针加入测试。

## 复现

```bash
python3 -I probe_repair_deletes_kept.py <repo> <solc-0.8.38 路径>
```
