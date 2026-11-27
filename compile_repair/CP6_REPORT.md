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

## CP6.1 本地复核

2026-11-24，修改 AI 为 Codex。在 `compile-repair@593feb057a8fa373c2d60880caaa63a799522cab` 依照 PROMPTS r2.29 §4.6l 运行。第 3 步运行器中止，CP6.1 本地验收未通过，等待 Claude 审查。

### 本机测试与 MANDO

| 核验 | 文档预期 | 实测 |
|---|---|---|
| production | 1,183 passed、6 skipped | 1183 passed, 6 skipped in 99.62s (0:01:39) |
| mando | 686 passed、503 skipped | 686 passed, 503 skipped in 22.43s |
| DFG v2 | 2,653 passed | 2653 passed, 9 warnings in 176.00s (0:02:55) |
| MANDO 846 个输入 | 843 份成功图等于 v5 且 D3(c) 为真、历史失败 3、真值上触发第 2–4 步 0 次 | 逐项相符，差异 0 个，耗时 221.45 秒 |

### 第 5 步破坏与修复

本机按要求执行每个算子 100 个基。DAppSCAN 单文件目录表第 10 项 `cp3_00111` 与第 27 项 `cp3_00290` 的输入 SHA256 都是 `f9abece5eeaac19c34242ecb7ef2255e3134b03ef91cdc3c45d38da64f445154`。运行器使用同一哈希前 16 位拼接 `f9abece5eeaac19c/truth`，第二次独占创建该路径时触发 FileExistsError，退出码 1，未生成正式 summary.json。原目录和日志均保留。这两个条目对应不同的 CP4 单元，完整内容哈希也相同。后续审查可考虑在运行目录名中加入单元标识，同时保留原抽样顺序与 SHA256。此建议未实施。

本表的统计范围为中止前已完成的样本；从保存的图与编辑收据只读复算，并与原始日志逐算子核对严格评分，不含未运行样本。已完成 78 个算子样本，修复成功 78 个，严格 exact 72 个，按运行器屏蔽元数据哈希后 exact 78 个。

| CP4 算子 | 完成 | 修复成功 | 字节完全还原 | 严格 exact | 屏蔽元数据哈希后 exact |
|---|---:|---:|---:|---:|---:|
| `duplicate_definition` | 26 | 26 | 0 | 24 | 26 |
| `unterminated_pragma` | 26 | 26 | 26 | 24 | 26 |
| `pragma_missing_semicolon_candidate` | 26 | 26 | 26 | 24 | 26 |

重复定义规则将后面的副本替换为空格以保留偏移。每个严格 exact 为假的基及涉及算子列在下表。JSON 逐节点记录两侧图哈希、IR 中的变化和对内嵌 Solidity CBOR 元数据的独立只读核查。

| 入口 SHA256 | 严格评分存在差异的算子 | 节点 IR 差异仅为经核验的内嵌元数据哈希 |
|---|---|---|
| `cccebb9ed96bcf62af37d07180c816e8003727ca4428a5f860b7972efe451c7a` | duplicate_definition、unterminated_pragma、pragma_missing_semicolon_candidate | 是 |
| `f9abece5eeaac19c34242ecb7ef2255e3134b03ef91cdc3c45d38da64f445154` | duplicate_definition、unterminated_pragma、pragma_missing_semicolon_candidate | 是 |

### 真实单元

第 4 步未启动，未选择或运行 42 个真实单元。云端记录的 11 个成功单元尚未获得本机复核；本轮不能据此判断本机修复率。

### 归档与范围

仓库内汇总位于 `artifacts/cp6_1_v1/local/`。tests.json、mando_check.json、mini_benchmark.json、real_check.json 保存各步状态、实际命令与耗时，已运行的原始日志保存在仓库外 `compile-repair-local/cp6_1_v1/`。压缩逐样本表同时登记压缩前后 SHA256。基准使用 DAppSCAN 固定提交 66a56619 和封存的 CP4 单文件基。启动前核对 19 个生产模块、全部已跟踪测试及夹具、原先获准保留的 32,005 个未跟踪路径。DFG 的 354 个代码引用与冻结基线一致。没有改动生产或运行脚本，CPU 本地执行，下载、LLM 调用、训练和费用均为 0。

### r2.30 补跑

2026-11-24，修改 AI 为 Codex。拉取 `fdcf75444c249eccc0dbf955e3495b1bc43658a4` 后，按 §4.6l 只运行第 3、4 步。CP6.1 本地验收通过，等待 Claude 审查。

#### 按不同内容抽样的破坏与修复基准

三个算子合计实测 300 项，300 项修复成功，严格 exact 为 294/300，仅屏蔽内嵌 Solidity 元数据哈希后为 300/300。扫描过程中跳过 17 个重复内容条目，涉及 17 个不同的 SHA256。本批共有 100 个不同的受测内容。算子样本按“内容 × 算子”计数。上次中止前的 78 项保留在旧记录，本表只使用新批次。

| CP4 算子 | 样本 | 修复成功 | 源码字节还原 | 严格 exact | 屏蔽元数据哈希后 exact |
|---|---:|---:|---:|---:|---:|
| `duplicate_definition` | 100 | 100 | 0 | 98 | 100 |
| `unterminated_pragma` | 100 | 100 | 100 | 98 | 100 |
| `pragma_missing_semicolon_candidate` | 100 | 100 | 100 | 98 | 100 |

下表逐个列出严格 exact 未通过的入口。用已保存的图对照节点 IR，解析 Solidity CBOR 段并核对长度与哈希字段。逐节点见证与两侧图 SHA256 见 `artifacts/cp6_1_v1/local/mini_benchmark.json` 的 strict_exceptions。

| 入口 SHA256 | 涉及算子 | IR 差异仅为内嵌元数据哈希 |
|---|---|---|
| `cccebb9ed96bcf62af37d07180c816e8003727ca4428a5f860b7972efe451c7a` | duplicate_definition、unterminated_pragma、pragma_missing_semicolon_candidate | 是 |
| `f9abece5eeaac19c34242ecb7ef2255e3134b03ef91cdc3c45d38da64f445154` | duplicate_definition、unterminated_pragma、pragma_missing_semicolon_candidate | 是 |

#### 真实单元

在 42 个单元中实测成功 11 个，11 个接受了第 5 步改写，corpus_unchanged=True。其中 DAppSCAN 有 24 个单元，SOChecker 有 18 个。成功项来自 2 个 DAppSCAN 项目和 2 个不同内容的 SOChecker 片段。逐单元核对 status、reason 和 primary_now，差异共 0 项。成功单元清单与云端一致。

成功单元为 `cp3_03213`、`cp3_03214`、`cp3_03215`、`cp3_03216`、`cp3_03217`、`cp3_03218`、`cp3_03220`、`cp3_03221`、`cp3_20464`、`cp3_29802`、`cp3_30104`。按成功单元计，8 项消除重复 SPDX，2 项处理逐字节相同的重复声明，1 项在文件末尾补 pragma 分号（cp3_29802 的 accepted 步骤记载补丁原因为 pragma terminator before end of file）。逐项收据及完整对照见 real_check.json。

#### 归档及边界

保留原先的 mini/；本次工作副本位于仓库外 compile-repair-local/cp6_1_v1/mini_r2/ 与 real/（仅在第 4 步启动时创建）。第 3 步用时 174.949 秒。新汇总的顶层字段给出此次结果，previous_run 保留原停点记录及 SHA256。各步命令、耗时与逐项压缩表见本批 local/mini_benchmark.json、local/real_check.json。第 1、2 步沿用 §67 的三套测试与 843 份成功图回归；已核对其收据。19 个生产文件所属实现沿用拉取版本，DFG 354 个代码引用与基线一致。CPU 本地运行，安装、额外下载、LLM 调用、训练及费用均为 0。


## CP6.2 本地复核（修改 AI：Codex，2026-11-24）

本机验收通过，等待 Claude 审查。基线 `2dbab6dcf21d158235e796995e01de9def9735cf`，执行 PROMPTS r2.31 §4.6m。工作树的 32,005 个历史未跟踪路径与已批准清单逐字节相同。新批次从空目录开始。

### 测试和 MANDO

production 1,202 项通过、6 项跳过，mando 700 项通过、508 项跳过，DFG v2 2,653 项通过、9 条警告。MANDO 的 846 个输入中，843 份成功图与 v5 逐字节相同，843 项通过 D3(c)，成功样本触发修复步骤 0 次，3 项重现历史失败。具体命令、用时、日志 SHA256 见 tests.json 和 mando_check.json。

### 右花括号破坏与修复

DAppSCAN 的 100 个不同内容中，68 个修复成功，68 个通过 graph_equal，68 个通过严格 exact。抽样时跳过 17 个重复内容条目。逐个从 CP4 所选顶层定义定位右花括号，核对原文件 SHA256，并验证删除该字节能逐字节得到实际送入流水线的受损文件。按其后是否还有词法记号判定位置，空白和注释不计。逐项位置、状态和图判定见 mini_positions.json.gz。

| 被删右花括号的位置 | 修复状态 | graph_equal | 数量 |
|---|---|---|---:|
| 较早定义 | unrepaired | 无图 | 32 |
| 末尾定义 | success | true | 68 |

68 个成功样本都只补入一个右花括号。新旧位置在 66 项中仅隔空白，另 2 项还隔着注释。68 项的图都通过严格 exact，逐字节还原源码为 0 项。32 个较早定义的试验都在 solc 解析阶段被拒，最终均无图。

### 真实单元与交付

真实单元共 522 个（DAppSCAN 83、SOChecker 439），修复成功 40 个，涉及 40 份不同的 SOChecker 片段。第 8 步获接受 185 个，其中按 D27 阶段进展接受 145 个，第 5 步获接受 0 个。逐单元核对 status、reason、primary_now，差异 0 处。源码哈希复核 corpus_unchanged=True。其中 145 项虽推进了编译阶段，最终仍为未修复。证据在 `artifacts/cp6_2_v1/local/`，完整工作副本在仓库外 `compile-repair-local/cp6_2_v1/`。本地核验复用了发布的生产实现、评分器和运行器。20 个生产文件与启动时一致，354 个 DFG 引用与 CP0.1 基线一致。CPU 执行，费用 0 美元。


## CP6.3 本地复核（修改 AI：Codex，2026-11-25）

本地验收通过，等待 Claude 审查。基线 `f33b7d47acbf659bdf7916f7dfd26de72a716c34`，按 PROMPTS r2.32 §4.6n 在独立目录执行。各步骤的命令、耗时和日志哈希见 `artifacts/cp6_3_v1/local/`。

### 回归

production 1,215 项通过、6 项跳过，mando 709 项通过、512 项跳过，DFG v2 2,653 项通过、9 条警告。MANDO 的 843 份成功图与 v5 逐字节相同，843 项通过 D3(c)，成功输入触发修复 0 次，另 3 项重现历史失败。

### 声明缺失基准

事件声明缺失和本地基类缺失各测 100 个不同内容。事件组成功 52 项，其中 50 项图相等、41 项严格 exact。基类组成功 17 项。事件组有 9 项的节点、边和调用均通过比较，但新增声明离原删除位置较远。已知工厂合约的元数据哈希差异经 CBOR 字段、长度和其余 IR 核验，共 2 项。

基类组逐个比较原图与修复图中各合约的节点数。11 个样本存在合约节点数下降，11 个样本出现新增节点。在 40 个新增节点中，40 个节点的源码区间全部位于新增修饰器或构造函数桩。成功样本中 removed_by_repair 大于零的有 0 项。节点数下降的 11 项都仅涉及所删基类，其余合约的节点数持平或只因桩而增加。桩用来补足编译所需的声明，被删基类的原始逻辑仍缺失。逐项验收差异为 0。

| 算子 | 未修复单元的 reason | 第 7 步的 reason（按次） | stubs 证据中的 reason（按条） | 无第 7 步记录 / 无证据 reason 的单元 |
|---|---|---|---|---|
| missing_base_contract | all_solc_candidates_failed × 83 | all_solc_candidates_failed × 76、no_applicable_stub × 21 | mixed_or_unknown_use × 20、unknown_or_disagreeing_types × 3 | 0 / 63 |
| undeclared_identifier | all_solc_candidates_failed × 48 | no_applicable_stub × 46、all_solc_candidates_failed × 2 | mixed_or_unknown_use × 26、unknown_or_disagreeing_types × 16 | 0 / 6 |

事件组的 52 项成功中，47 项实际接受第 7 步，5 项受损输入无需改写便已成功；基类组的 17 项成功均接受了第 7 步。两组各自按源码 SHA256 去重。同一源码可以在两个算子中各出现一次。逐合约节点数、插入区间、图哈希及原因明细见 mini_checks.json.gz，原始评分见 mini_summary.json.gz。

### 真实单元与交付

550 个真实单元（DAppSCAN 95、SOChecker 455）中成功 49 个。第 7 步获接受 14 个，其中 9 个最终成功。第 8 步获接受 191 个，按阶段进展接受 146 个，第 5 步获接受 0 个。语料哈希复核 corpus_unchanged=True。与云端逐单元对照 status、reason、primary_now，共 0 处差异。CP6.2 的 40 个历史成功项中有 0 项退出成功集合，本批新增成功 9 项。按入口 SHA256 去重，成功项来自 DAppSCAN 的 1 个内容和 SOChecker 的 48 个片段。

20 个生产文件与启动时的 SHA256 相同，354 个 DFG 引用与 CP0.1 封存相同。完整工作副本和工具日志位于仓库外 compile-repair-local/cp6_3_v1/。本批使用 CPU，费用 0 美元。


## CP6.4 本地（修改 AI：Codex，2026-11-25）

mando 测试通过。D26 全量在第 73 个单元 cp3_06775 的第 3 步发布版证据处按 §4.6o 停止，等待审查。基于 `09dc052753da3dede00c9cd990f9ee6d01ea12d7` 执行 PROMPTS r2.33 §4.6o。本机 mando 测试为 721 passed、521 skipped，计数完全符合预期。生产测试、DFG 测试与 MANDO 图回归按本节范围沿用前序记录。

### D26 全量选择与部分实测

原选择器得到 1,539 个不同单元。所有单元均命中 openzeppelin-solidity-2.3.0，其中 63 个同时命中 @chainlink/contracts-0.0.10。OpenZeppelin 涉及 9 个项目名、10 个物理根，Chainlink 涉及 6 个项目名、7 个物理根。Aloith 项目在 DAppSCAN 与 Trace 中各有 199 个入口，相对路径、入口哈希及命中前缀逐项一致。沿用原清单分别测量。

已完成 73 项，73 项修复成功并接受第 3 步。72 项满足本步的全部发布版证据要求，1 项触发停点。另 1,466 项未启动。已完成样本中没有编译未修复项，当前主因分布为空。

| 项目 | 语料 | 选中 | 完成 | 成功 | 第 3 步接受 |
|---|---|---:|---:|---:|---:|
| Chainsulting-SPICE | DAppSCAN | 105 | 26 | 26 | 26 |
| Iosiro-Synthetix Alkaid Release Smart Contract Audit | DAppSCAN | 69 | 18 | 18 | 18 |
| Iosiro-Synthetix Alnitak Release Smart Contract Audit | DAppSCAN | 478 | 29 | 29 | 29 |
| Iosiro-Synthetix Aloith Release Smart Contract Audit | DAppSCAN | 199 | 0 | 0 | 0 |
| Iosiro-Synthetix Didpha Release Smart Contract Audit | DAppSCAN | 1 | 0 | 0 | 0 |
| Iosiro-Synthetix Fomalhaut Release Smart Contract Audit | DAppSCAN | 151 | 0 | 0 | 0 |
| Iosiro-Synthetix Shaula Release Smart Contract Audit | DAppSCAN | 321 | 0 | 0 | 0 |
| Iosiro-Thales Airdrop and Staking Smart Contract Audit | DAppSCAN | 1 | 0 | 0 | 0 |
| PeckShield-Kalmar | DAppSCAN | 15 | 0 | 0 | 0 |
| Iosiro-Synthetix Aloith Release Smart Contract Audit | Trace_repo | 199 | 0 | 0 | 0 |

### 第 3 步发布版与停点

| 已接受的发布版 | 层级 | 证据 | inferred | 涉及单元 |
|---|---|---|---|---:|
| @chainlink/contracts@0.0.10 | T1 | D26_versioned_prefix | false | 5 |
| @eth-optimism/contracts@0.2.11 | T3 | no_lock_evidence | true | 1 |
| openzeppelin-solidity@2.3.0 | T1 | D26_versioned_prefix | false | 73 |

同一单元可出现多个包，各行计数有重叠。同一次已接受的第 3 步既选用了 openzeppelin-solidity@2.3.0（T1，D26_versioned_prefix，inferred=false），也选用了 @eth-optimism/contracts@0.2.11（T3，inferred=true）。后者有 3 处普通包导入，入口 SynthetixBridgeToOptimism.sol 中有 2 处，BaseSynthetixBridge.sol 中有 1 处。3 条身份记录的 manifests 均为空。solc 0.5.16 编译成功，D3(a)、D3(b)、D3(c) 均为 true。

建议审查 §4.6o 的 T1 要求应覆盖同次接受的全部包，还是仅覆盖 D26 版本前缀包，并对其他依赖按 D22 单列。此次沿用原文判据。两包的 tier、版本证据及 inferred 均保留，后续运行范围和口径待确认。

### 证据与资源

已核验 CP5.1 封存索引的 index.json 与 seal.json 哈希（20 个包、172 个发布版）。停止后再次核对全部 1,539 个入口的 CP3 SHA256，全部一致。原运行器只在全量结束时写 corpus_unchanged 和 summary.json，本批将全量语料判定登记为未测。20 个生产文件与启动时相同，354 个 DFG 代码引用与封存一致。本机 CPU 执行，费用 0 美元。命令、用时、索引及日志哈希见 `artifacts/cp6_4_v1/local/tests.json` 和 `d26.json`。逐单元 tier、证据及原生收据 SHA256 见 `d26_observed_units.jsonl.gz`，完整名单见 `d26_targets.json.gz`。工作副本与中断现场位于仓库外 `compile-repair-local/cp6_4_v1/`。


### r2.34 续跑（修改 AI：Codex，2026-11-25）

本机抽样验收通过，等待 Claude 审查。基线 `116c6ca2466ad0a0058eefb14836f6994b6414b2`。选择器按原顺序从 1,539 项取样，每个物理项目目录最多再取 20 项。跳过已完成 73 项、跨语料重复 199 项和超过每目录上限的 1110 项。9 个项目名对应 10 个目录。Aloith 在 DAppSCAN、Trace 两个目录各提供 20 个新单元，按项目名、项目内路径和入口 SHA256 核对，合并结果中没有重复。

新增 157 项，成功 155 项，第 3 步接受 157 项。合并首轮 73 项后，共运行 230 项，成功 228 项，第 3 步接受 230 项。未修复单元的当前主因为missing_relative_file 1 项、unresolved_package_import 1 项。对应单元为 cp3_08145（missing_relative_file）、cp3_09602（unresolved_package_import）。第 3 步在全部已运行单元中获接受。

| 项目（同名跨语料合并） | 首轮 | 新增 | 合计运行 | 成功 | 第 3 步接受 | 其他包 T1 / T2 / T3 |
|---|---:|---:|---:|---:|---:|---:|
| Chainsulting-SPICE | 26 | 20 | 46 | 46 | 46 | 0 / 0 / 0 |
| Iosiro-Synthetix Alkaid Release Smart Contract Audit | 18 | 20 | 38 | 38 | 38 | 0 / 0 / 0 |
| Iosiro-Synthetix Alnitak Release Smart Contract Audit | 29 | 20 | 49 | 49 | 49 | 0 / 0 / 1 |
| Iosiro-Synthetix Aloith Release Smart Contract Audit | 0 | 40 | 40 | 40 | 40 | 0 / 0 / 0 |
| Iosiro-Synthetix Didpha Release Smart Contract Audit | 0 | 1 | 1 | 0 | 1 | 0 / 0 / 0 |
| Iosiro-Synthetix Fomalhaut Release Smart Contract Audit | 0 | 20 | 20 | 20 | 20 | 0 / 0 / 0 |
| Iosiro-Synthetix Shaula Release Smart Contract Audit | 0 | 20 | 20 | 20 | 20 | 0 / 0 / 0 |
| Iosiro-Thales Airdrop and Staking Smart Contract Audit | 0 | 1 | 1 | 0 | 1 | 0 / 0 / 0 |
| PeckShield-Kalmar | 0 | 15 | 15 | 15 | 15 | 0 / 0 / 9 |
| 合计 | 73 | 157 | 230 | 228 | 230 | 0 / 0 / 10 |

| 范围 | 发布版 | 层级 | 证据 | inferred | 单元数 |
|---|---|---|---|---|---:|
| 前缀 | @chainlink/contracts@0.0.10 | T1 | D26_versioned_prefix | false | 13 |
| 前缀 | openzeppelin-solidity@2.3.0 | T1 | D26_versioned_prefix | false | 230 |
| 伴随 | @eth-optimism/contracts@0.2.11 | T3 | D22（逐项见证据表） | true | 1 |
| 伴随 | @uniswap/v2-core@1.0.0 | T3 | D22（逐项见证据表） | true | 9 |

其他依赖按每单元内不同的包和版本计，T1 为 0，T2 为 0，T3 为 10。同一单元可涉及多个包。每个已接受的前缀发布版均对照封存索引、原生身份及版本证据；普通包按 D22 记录层级与 inferred。首轮 cp3_06775 的 OpenZeppelin 2.3.0 具有版本前缀证据，T1、inferred=false；普通伴随依赖 @eth-optimism/contracts 0.2.11 为 T3、inferred=true。按更正后的 D26 和 D22 两项均通过。

新增样本的原生 corpus_unchanged=True。每个新增单元还对照了本轮开始时的项目 Solidity 文件清单和哈希。首轮沿用封存结果，并复核了 73 个结果、步骤日志和接受轮次的 SHA256。首轮没有生成全量语料标记。本轮范围是按项目抽样，合并结果覆盖原名单的 230/1,539 项。汇总与逐单元原生收据哈希见 `artifacts/cp6_4_v1/local/d26_r2.json`、`d26_r2_units.jsonl.gz`。

## CP6.5 CP6 补全（修改 AI：Claude，2026-11-25；全部云端）

### 实现
- `rules/normalize.py`：第 5 步文档迁移（`documented_migrations`）与 NatSpec `@param` 置空（`natspec_parameters`）；第 10 步元组调用改写（`tuple_call_rewrites`）。
- `rules/environment.py`：`disjunction_plan`（`||` 并集选版；冻结的 `pragma_interval` 不变）。
- `rules/stubs.py`：具名构造推出字段的结构体桩。
- `pipeline.py`：读取失败后调用并集选版；迁移门槛；第 10 步试验先用 solc 已通过的版本。
- 测试 `tests/test_cp65.py` 63 项；test_cp63 的 1 个预期与 3 个 `||` 流水线测试按 D6 路由修改（DECISIONS CP6.5 表）。非测试文件仍为 20 个。

### 真实验收

| 项 | 预期 | 实际 | 来源 |
|---|---|---|---|
| 生产测试 | 全部通过 | 1,298 passed / 6 skipped | artifacts/cp6_5_v1/production_tests_cloud.json |
| MANDO 回归 | 843 个图不变，3 个历史失败经第 10 步成功 | passed=true（graphs_equal 843，new_successes 3） | artifacts/cp6_5_v1/mando_check_cloud.json |
| 真实 319 个单元 | 不退步 | 成功 65 → 67（46 → 48 个来源），无退步，版本不变 | artifacts/cp6_5_v1/real_final_cloud.json |
| other、io_error、closure_version_conflict | 逐项诊断 | 见 cp6_5_v1/README.md 诊断表（交代理） | 同上 |

### 测试与开发记录
冻结 pragma 读取一度被改为接受 `||`（9 个测试失败），改为单独规则；第 10 步改写后 MANDO 的 3 个单元曾改用 0.4.12 编译，改为先用 solc 已通过的版本。

### 归档与复现
`artifacts/cp6_5_v1/`（README、mando_check.py、真实单元目标与逐单元结果）；命令见该 README。

### 停止位置与后续边界
CP6 完成；不需要本机运行。下一步 CP7。本节为 CP7–CP9 文档核对时补写（CHANGE_LOG §86）。
