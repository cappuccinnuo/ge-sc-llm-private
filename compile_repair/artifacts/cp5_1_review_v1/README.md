# cp5_1_review_v1：CP5.1 审查证据（Claude，2026-11-23）

审查对象：`compile-repair@41c685fca`（Codex 的 CP5.1：`toolchain/solc.py`、`rules/dependencies.py`、`pipeline.py`、`evaluation/benchmark.py`、`evaluation/report.py`、`tests/test_cp51.py`，产物 `cp5_1_v1/`，CP5_REPORT 的 CP5.1 节与四份记录）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 文件

| 文件 | 内容 |
|---|---|
| `outcome_tallies.json` | 由 `cp5_1_v1/packed/benchmark.jsonl.gz`、`packed/real_full.jsonl.gz`、`path_census.jsonl` 计算：移动样本的状态、原因与接受步骤；包装样本 exact 的分解；真实缺相对文件单元按“是否有唯一符号候选”与结果的交叉表 |

## 成立的部分

1. 索引：172 个发布版全部经 SHA512 与 SHA256 核对，13,073 个 Solidity 文件，索引 seal。传输中断与环境故障时停下、保留现场、逐项请求批准，处理正确。
2. D24：只接受包装自带的 `--optimize` 与十进制 uint32 的 `--optimize-runs`，重复参数拒绝，solc 与 Slither 参数相同。
3. 候选上限：按“实际进入编译的组合”计数，K = 21 取自所选规则在全部成功开发单元中的最大位置；14 个截断单元都在测试集。没有按错误位置提前停止。
4. 规则：真实开发集 closest 1,130、latest 1,130、oldest 1,131 / 2,316，差异只有 cp3_20546 一个单元，按开发集指标固定 oldest。73 个 T1 单元（规则冻结后运行）中，oldest 选中锁版本 70 个，另两条规则 8 个，方向一致。
5. 外部语料：9,138 个单元中 5,880 个通过 D3；unresolved_package_import 主因 8,454 → 2,804，standard_json_input 410 → 40；开发集 2,316 项与无上限测量逐项一致。
6. 对照：删除文件、无效路径与改动 pragma 三个算子的成功数为 0，符合第 2–4 步的设计。
7. MANDO 843 个图与 v5 相同，第 2–4 步触发 0 次；生产文件 18 个。

## 问题

1. **移动算子的修复率低，原因未诊断。** 400 个移动样本中只有 189 个修复。211 个未修复的样本里，194 个第 4 步没有被接受、17 个接受一轮第 4 步后仍未解析（`outcome_tallies.json`）；`no_compatible_candidate` 只解释 32 个。算子把文件原样移到 `.cp5_moved/`，被移动文件自己的相对导入（例如 `./ERC20Basic.sol`、`../math/SafeMath.sol`）随之失效；改写导入方后错误数不会减少（一个缺失导入换成被移动文件中的缺失导入），按 3.1 节的接受条件会被拒绝。7 个两轮第 4 步成功的样本与这一解释相符，但没有逐项核实。这一缺陷来自 4.6h 对算子的写法（审查方案的不足）：真实的文件移动中，作者会同时更新被移动文件的导入。
2. **真实语料中同样的漏修。** 412 个缺相对文件单元中，有 35 个“全部缺失的相对导入都有唯一符号候选”却没有通过 D3（21 个第 4 步未被接受，14 个接受后仍失败），另有 46 个部分导入有唯一候选、第 4 步被接受后仍有未解析导入，21 个部分导入有唯一候选、第 4 步未被接受；合计 102 个至少一个缺失相对导入有唯一符号候选却未通过 D3。原因同样没有诊断。若是链式导入被接受条件拦住，这是第 4 步本身的缺口，不只是基准问题。
3. **包装样本的 exact 被元数据拒绝。** 950 个包装样本全部编译并通过 D3，lost、added 均为 0；其中 550 个的 raw 迁移评分为 exact，但迁移名称核验以 `graph_metadata_differ` 拒绝，exact 记为 false（`outcome_tallies.json`）。报告只给了 40.7% 与 42.4% 的 exact，没有说明原因，也没有列出不同的元数据字段。
4. **移动样本的 exact 定义不适合文件级破坏。** 188 个修复样本的全部图指标为满分，但修复改写的是导入方的导入行，不在破坏区间附近，exact 为 false。对删除、移动、缺包与包装这类文件级破坏，正确修复的位置就是引用该文件的导入指令。
5. **部分 IR 缺失的比例可以测量。** 报告说无法给出全部图的 IR 完整率。但 Slither 0.11.6 在合约函数生成 IR 抛出 AttributeError 时调用 `log_incorrect_parsing`，把 `contract.is_incorrectly_constructed` 设为 True（`slither/solc_parsing/slither_compilation_unit_solc.py` 第 818–824 行，`declarations/contract.py` 第 434–439 行）；顶层函数的同类失败只记日志（第 843–846 行）。逐图记录这两个信号就能得到比例。这关系到图能否用于下游，但改不改 D3 是用户的决定，应先测量。

## 处理

CP5.2（PROMPTS §4.6i）：诊断问题 1、2，修正移动算子；如确认链式导入被拦，在第 4 步中允许受限的链式改写；修正文件级破坏的 exact 邻域；列出包装的元数据差异并按结果处理；测量部分 IR 的比例。
