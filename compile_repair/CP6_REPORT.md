# CompileRepair CP6 报告

## CP6.0 本地复核

2026-11-24，修改 AI 为 Codex。在 `compile-repair@6faffcabe85a2ae1e9d04bd62248a5d2ab5782d8` 执行 PROMPTS r2.26 §4.6j。三套测试及 MANDO 回归通过。第 4 步在首个真实单元的最终主因处停止。CP6.0 本地验收尚未通过，等待 Claude 审查。

### 实测与预期

| 项目 | 预期 | 本机结果 |
|---|---|---|
| production 模块 | 1,160 通过，6 跳过 | 一致，97.95 秒 |
| mando 模块 | 672 通过，494 跳过 | 一致，22.35 秒 |
| DFG v2 | 2,653 通过 | 一致，9 条警告，177.18 秒 |
| MANDO 846 个输入 | 843 份成功图与 v5 字节相同且 D3(c) 为真，3 个历史失败，真值上触发第 2–4 步 0 次 | 全部一致，差异清单为空，核验脚本退出码 0，内部批处理退出码 2 符合脚本预期，224.87 秒 |
| 四个历史部分 IR 单元 | 最终主因为 `slither_incomplete` 且子类为 `slither_partial_ir`，或换版本通过 D3(c) | 运行 1 个，最终主因不符。其余 3 个按停点要求未运行 |

测试的命令、日志路径、SHA256 与耗时在 `artifacts/cp6_0_v1/local/tests.json`。MANDO 的解包命令、检查命令、基线和新 seal 哈希在同目录的 `mando_check.json`。

### 真实单元与最终归因

`cp3_19463` 为 DAppSCAN 开发集项目。沿用 CP5.1 的输入、编译器、离线索引、`oldest` 策略及原本的包版本证据。CP5.1 开发测量记录的 limit 为 null，§4.6j 指定使用随后冻结的 K=21，本次实传 21。原脚本会遍历整个开发集并比较三种策略，因此本次限定运行器复用其 `entry`、`verified_index` 与 `repair_unit` 入口。没有更改生产实现。

| 读数 | 第 1 轮 | 第 2 轮 |
|---|---|---|
| 离线依赖 `@openzeppelin/contracts` | 4.2.0 | 4.9.6 |
| 实际 solc | 0.8.4–0.8.38，逐版 35 次 | 相同 35 版 |
| 逐版本结果 | solc 退出 0，D3(a)/(b) 为真、D3(c) 为假 | 全部相同 |
| Slither 类别及标记 | `slither_incomplete / slither_partial_ir`，合约 `BalancerLBPSwapper`、`OracleRef`，顶层错误 0 | 全部相同 |
| 流水线决定 | `slither_side_failure`，拒绝该依赖组合 | 同样拒绝 |

原记录有 8 个导入阻塞。70 次候选均通过 solc，随后被 D3(c) 拒绝。`pipeline.py` 的轮次接受条件排除 `slither_side_failure`，两份试验收据的 `errors_after` 均为 null、`accepted` 均为 false。最终保留环境阶段结果，状态为 `unrepaired`，原因为 `unresolved_imports`，`primary_causes` 返回 `unresolved_package_import`。单元及轮次目录中的 graph.json 共 0 个。Slither 子类及拒图行为达到预期，单元最终主因未达预期。每版 D3、合约名、编译器哈希、设置及对应收据见 `local/partial_ir_units.json`。

`cp3_19496`、`cp3_19497`、`cp3_19507` 未运行。没有重试、放宽接受条件或依据首项推断其余三个单元。

### 准备、归档与停止

最初 Git 列出 20 个历史批次的 32,005 个未跟踪路径。用户批准“允许保留已登记的历史产物并继续”。启动时逐字比较原路径清单，核对 18 个生产文件与 212 个测试文件及夹具，已跟踪文件与提交一致。完整测试与工具收据在仓库外 `/home/zhao/SmartContract/compile-repair-local/cp6_0_v1/`。仓库内的 `local/partial_ir_check.py` 保存本次限定运行方法。CPU 本地运行，费用 0 美元。未安装软件、下载工具或语料、调用 LLM、启动训练或开展 CP6 后续开发。

## CP6.0.1 本地复核

2026-11-24，修改 AI 为 Codex。按 PROMPTS r2.27 §4.6k 复核 Claude 的 `9a49878690a1c5f6adf36868187d7e158f1c64fe`。本地复核通过，等待 Claude 审查。

### 测试与 MANDO 回归

| 本机检查 | 预期 | 实测 |
|---|---|---|
| production 模块 | 1,163 通过、6 跳过 | 1163 passed, 6 skipped in 97.46s (0:01:37) |
| mando 模块 | 672 通过、497 跳过 | 672 passed, 497 skipped in 21.73s |
| DFG v2 | 2,653 通过 | 2653 passed, 9 warnings in 165.41s (0:02:45) |
| MANDO 846 个输入 | 843 份成功图与 v5 字节相同且 D3(c) 为真，3 个历史失败，真值上触发第 2–4 步 0 次 | 四个计数逐项相符，差异 0，耗时 222.43 秒 |

两套解释器的测试命令、临时目录、日志哈希与冻结检查见 `artifacts/cp6_0_v1/local/tests_r2.json`。MANDO 的解包命令、回归命令、参考及新 seal 见同目录的 `mando_check_r2.json`。检查脚本退出 0，内部批处理因含 3 个历史失败返回预期的 2。

### 四个部分 IR 单元

沿用 CP5.1 离线索引 `a02cc091f958aa78fd61f33f2f166912b870b98c77ae6e0cd810bdd704689511`、oldest 及 K=21，在生产环境逐个调用 repair_unit。实测 4 个真实单元，共 385 次候选观测，其中 385 次归为 slither_partial_ir。4 个单元最终主因为 slither_incomplete，0 个单元换版本成功。本节规定的四个真实单元均已实测。

| 单元 | 状态 | 最终主因 | 含 accepted_outcome 的步骤与发布版 | 被 Slither 标记的合约 | 部分 IR 候选次数 | 留存图数 |
|---|---|---|---|---|---:|---:|
| cp3_19463 | unrepaired | slither_incomplete | 第 3 步第 1 轮，@openzeppelin/contracts@4.2.0（T3，inferred=true） | BalancerLBPSwapper、OracleRef | 70 | 0 |
| cp3_19496 | unrepaired | slither_incomplete | 第 3 步第 1 轮，@openzeppelin/contracts@4.2.0（T3，inferred=true） | OracleRef | 70 | 0 |
| cp3_19497 | unrepaired | slither_incomplete | 第 3 步第 1 轮，@openzeppelin/contracts@4.2.0（T3，inferred=true）、@uniswap/v2-core@1.0.0（T3，inferred=true） | OracleRef、UniRef | 140 | 0 |
| cp3_19507 | unrepaired | slither_incomplete | 第 3 步第 1 轮，@openzeppelin/contracts@4.0.0（T3，inferred=true） | TribalChief | 105 | 0 |

步骤收据中 compiled_slither_side_failure 出现 4 次。候选数按环境与试验轮次收据统计。最终选中的收据在单元结果中另有引用，只计一次。每次的 solc 版本、D3(a/b/c)、被标记的合约，以及每个最终采用步骤的轮次、accepted_outcome、发布版和 inferred 标记，见 `partial_ir_units_r2.json`。本次四单元运行器用时 588.048 秒。

### 第 0 步与实际入口

快进拉取后，18 个生产文件、212 个已跟踪测试文件及夹具与 Git 对象一致。已批准的 32,005 个历史未跟踪路径与上轮清单逐字节匹配。新输出目录首次创建于 `/home/zhao/SmartContract/compile-repair-local/cp6_0_1_v1/`。旧批次继续保留。

随附的 partial_ir_check_r2.py 会用 exist_ok=False 创建批次目录，而前两步已向该目录写入回归结果。用户批准“允许直接调用同一入口并记录”。核验前两步收据、确认四单元的子目录与汇总文件均不存在后，设置同一 OUT，直接调用已提交的 partial_ir_check.main()。实际执行命令保存在 `partial_ir_units_r2.json` 的 command 字段，原运行器自行报告的命令单列。未编辑入口、生产代码或测试。全部操作使用现有 CPU 环境，运行费用 0 美元。全量外部语料与 CP6 后续开发未运行。
