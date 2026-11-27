# CompileRepair CP9 报告：第二阶段多代理（修改 AI：Claude，2026-11-27）

规格：PROMPTS r2.40 §4.9；记录：docs/CHANGE_LOG.md §86；证据：artifacts/cp9_v1/；接口说明：docs/AGENT_INTERFACE.md。

## 实现
- 新增 `agents/stage2.py`（Stage2、AgentChain、agents_from_config）；修改 `agents/prompt.py`（分析、上下文扩展、交流）、`agents/patch.py`（步骤标签）、`agents/llm.py`（共享预算与记录）、`agents/stage1.py`（属性、反馈格式；配置构造移到 stage2.py）、`pipeline.py`（票数排序、`agent_round` / `agent_end`）。
- 新增 `tests/test_cp9.py`（11 项）；修改 `tests/test_cp8.py`（新配置格式与步骤名）、`tests/test_cp1_1.py`（文件数 29）。
- 新增 `docs/AGENT_INTERFACE.md`（模型 API 要求、配置、运行、记录）。
- 与 PROMPTS 的差异：3.6 第 2 条的“上下文代理”实现为由失败分析驱动的确定性工具步骤（不另调用模型），理由见 DECISIONS CP9 表。

## 真实验收

| 项 | 预期 | 实际 | 来源 |
|---|---|---|---|
| 交流轮只在全部失败时出现 | 是 | 测试 test_exchange_round…、test_failed_exchange… | tests/test_cp9.py |
| 生产测试 | 全部通过 | 1,346 passed / 6 skipped | artifacts/cp9_v1/production_tests_cloud.json |
| MANDO（不传代理） | 843 个图不变 | passed=true | artifacts/cp9_v1/mando_check_cloud.json |
| 两阶段模拟运行 40 个真实单元 | 0 泄露 | 0 泄露，最大提示 34,300 字符 | artifacts/cp9_v1/dry_run_cloud.json |
| 与“第一阶段同等额外预算”的对照 | 报告修复率与费用 | 未运行（等 D12 接入模型） | — |

## 测试与开发记录
上下文扩展测试起初预期错误（超出字符上限的声明文件被跳过后选了另一个文件），按“声明文件优先、上限内”的行为改写测试；文件数测试 28 → 29。

## 归档与复现
`artifacts/cp9_v1/`；模拟运行：`python -B compile_repair/artifacts/cp8_v1/dry_run.py <targets.json> <知识目录> <输出目录> <summary.json> [单元数]`。

## 停止位置与后续边界
代码与模拟验收完成；真实运行与对照在接入模型后进行。下一步 CP10（评估与消融；消融开关已在配置中：analysis、exchange、单模型提议者、candidates、知识来源）。
