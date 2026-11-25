# CP6.2 证据：第 8 步结构补全与 D27（修改 AI：Claude，2026-11-24）

规格见 PROMPTS r2.31 §4.6m，记录见 docs/CHANGE_LOG.md §71。本目录放脚本与云端摘要；本机复核的输出写到仓库外 compile-repair-local/cp6_2_v1/。

## 先测量，再定范围

用 CP6.1 的流水线（第 1–5 步）重跑 CP3 中主因或候选类别含 undeclared_identifier、missing_base_contract、unbalanced_structure、parser_error_other、type_error_other 的 562 个未修复单元，把最终诊断按消息模板、按不同来源计数（脚本见 CHANGE_LOG §71.2）：

| 写法 | 来源 | 处理 |
|---|---|---|
| 合约成员写在文件级（片段）：以 function 开头约 200 个，另有 mapping、状态变量、struct、constructor、modifier | 约 230 个片段 | 第 8 步片段包装（本阶段） |
| 未声明标识符 / 基类找不到 | 约 23 个来源 | 第 7 步规则桩（CP6.3） |
| 括号不平衡 | 主因 55 个来源 | 第 8 步补右花括号（本阶段） |
| 文件内容只是一个相对路径（符号链接在 core.symlinks=false 时检出的样子） | 1 个项目（PeckShield-starkex，63 个单元） | 暂不做；记入后续 |
| 非 Solidity（JavaScript 等）、`...` 占位、残缺语句 | 片段 | 不处理 |

## 实现

- `rules/stubs.py`（新文件，非测试文件 20 个）：补右花括号、片段包装；只插入文本，等级 additive。
- `pipeline.py`：第 8 步与第 5 步共用一段代码；修复资格增加三个解析类别；D27 的阶段度量与接受规则，每次试验记录 phase_before、phase_after、accepted_by。
- 测试：`tests/test_cp62.py` 19 项；test_cp1_1 的文件数 19 → 20。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,202 passed / 6 skipped（production_tests_cloud.json） |
| MANDO 回归 | passed=true：843 个图与 v5 逐字节相同，d3_c 843，历史失败 3，steps_on_truths 0（mando_check_cloud.json） |
| unbalanced_structure 基准（每个算子 30 个不同内容的 DAppSCAN 单文件基） | 22 个修复成功，严格 exact 22/22；8 个未修复（mini_benchmark_cloud.json） |
| 真实单元（522 个：DAppSCAN 83、SOChecker 439） | {REAL}（real_check_cloud.json、targets_cloud.json） |

基准逐个核对被删位置：22 个成功全部是文件最后一个定义的右花括号（其后只有空白与注释）；8 个未修复全部是较早定义的右花括号，补在末尾会把后面的定义嵌进去，编译器拒绝，没有接受错误的图。

第一版把右花括号补在文件末尾（最后的换行之后）：22 个成功的图节点、CFG 边与调用全部相同，但严格 exact 只有 3 个，因为评分要求修复加入的字节靠近破坏处，而末尾换行把两者隔开。改为补在最后一个记号之后，严格 exact 22/22；评分器没有改。脚本另记 graph_equal（除字节位置外的全部条件）与 near_damage。

## 脚本

- `select_targets.py <targets.json> <类别,...> [旧前缀=新前缀 ...] [单元号 ...]`：CP6.1 选择器加上类别参数。
- `real_check.py <targets.json> <输出目录> <summary.json>`：逐单元记录第 5、8 步的接受、accepted_by 与阶段；汇总 success、step8_accepted、phase_advanced 与当前主因分布。
- `mini_benchmark.py <bases> <DAppSCAN-source> <每个算子样本数> <输出目录> <summary.json> <算子,...>`：CP6.1 运行器加上算子参数，另记 graph_equal、near_damage、added。
