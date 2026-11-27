# CP9 证据：第二阶段多代理（模拟模型；修改 AI：Claude，2026-11-27）

规格见 PROMPTS r2.40 §4.9，记录见 docs/CHANGE_LOG.md §86，接入模型的说明见 docs/AGENT_INTERFACE.md。没有真实 LLM 调用，费用 0。

## 实现

- `agents/stage2.py`（新增）：`Stage2`（失败分析 → 按分析扩展上下文 → 1–3 个提议模型各写一个补丁、互不可见 → 由流水线裁决 → 全部未被接受时一轮交流，再失败则停止）；`AgentChain`（第一阶段停止后从最佳中间状态接第二阶段，带上第一阶段试过的全部补丁；语言核对否定或预算用尽时第二阶段不运行）；`agents_from_config`（多模型配置，全部模型共用一个预算与一份调用记录）。
- `agents/prompt.py`：失败分析提示与解析（CAUSE / NEED / SYMBOLS）、上下文扩展（整份项目文件优先声明点名符号者、K2、两倍 k 的 K1，字符上限）、交流段。
- `agents/patch.py`：补丁的步骤标签（stage1 / stage2）。
- `agents/llm.py`：客户端可共用预算与记录；脚本客户端可命名模型。
- `pipeline.py`：候选排序加入票数（错误数之后、改动字节之前，Agentless 规则）；轮次记为 `agent_round`（带 stage），结束记为 `agent_end`。
- 配置格式改为 `models` / `stage1` / `stage2`（旧的单模型模板删除，见 cp8_v1/README.md 更正）。
- 非测试文件 28 → 29（PROMPTS 3.10 已列 agents/stage2.py）；测试 `tests/test_cp9.py` 11 项。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,346 passed / 6 skipped（production_tests_cloud.json；CP8 为 1,335 / 6） |
| MANDO（不传代理） | passed=true：843 个图不变（mando_check_cloud.json） |
| 两个阶段的模拟运行，40 个真实失败单元（dry_run_cloud.json） | 全部 40 个都进入第二阶段并以 `stage1:stalled, stage2:exchange_failed` 结束；280 个提示，中位 18,198 字符，最大 34,300；0 个单元泄露文件名、目录路径或注释；输入不变 |

测试覆盖：第一阶段停滞后第二阶段接手并成功（provenance 步骤为 stage2）；分析读到第一阶段的被拒补丁；提议互不可见；相同补丁计票并胜过更短的单票补丁；交流轮显示自己与他人的补丁和错误并可成功；交流失败后停止且每个提议者只修订一次；无分析、无交流两种消融去掉对应调用；共享预算用尽时停止；语言核对否定时第二阶段不调用；分析解析与上下文扩展（声明文件优先、字符上限、注释仍遮蔽）；配置：异构标记、共享预算与记录、提议者 1–3 个、未知字段报错。

## 尚未运行（需要接入模型，D12）

- 真实修复率与费用；第二阶段与“第一阶段同等额外预算”的对照（做法见 docs/AGENT_INTERFACE.md 第 4 节第 5 条）。
- 第二阶段的暂定参数：rounds 2、window 20、context_limit 12,000 字符、k 5。

## 文件

- `agent_config.example.json`：多模型配置模板（预算为 0）。
- `dry_run_cloud.json`、`mando_check_cloud.json`、`production_tests_cloud.json`：上表的证据；模拟运行脚本为 `artifacts/cp8_v1/dry_run.py`（已扩展到两个阶段，`--stage1-only` 只跑第一阶段）。
