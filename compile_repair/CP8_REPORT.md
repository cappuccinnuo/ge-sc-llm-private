# CompileRepair CP8 报告：第一阶段代理（修改 AI：Claude，2026-11-27；本报告于同日文档核对时补写）

规格：PROMPTS r2.38–r2.39 §4.8；记录：docs/CHANGE_LOG.md §85；证据：artifacts/cp8_v1/；接口说明：docs/AGENT_INTERFACE.md。

## 实现
- `agents/llm.py`（新增）：预算在发送前检查、按请求哈希缓存、逐次调用记录；Anthropic 与 OpenAI 兼容 HTTP 客户端；测试用的脚本客户端。
- `agents/prompt.py`（新增）：D10 视图、错误窗口与声明位置、K1–K3、唯一模板、语言核对提示。
- `agents/patch.py`（新增）：REPLACE / INSERT 块、原文校验、D7 检查、写回字节补丁。
- `agents/stage1.py`（新增）：N 个候选、语言核对、被拒候选反馈、停止条件。
- `pipeline.py`、`cli.py`：只在传入代理时运行代理轮；`--agent-config`；`llm_calls.json`。
- 测试 `tests/test_cp8.py` 22 项；文件数 23 → 28。
- 用户决定（2026-11-27）：D10 确认；D12 模型与 API 暂不指定、接口保留，首次授权运行上限 US$10。

## 真实验收

| 项 | 实际 | 来源 |
|---|---|---|
| 补丁原文校验、D7、匿名化与注释遮蔽 | 测试全部通过 | tests/test_cp8.py |
| 生产测试 | 1,335 passed / 6 skipped | artifacts/cp8_v1/production_tests_cloud.json |
| MANDO（不传代理） | 843 个图不变 | artifacts/cp8_v1/mando_check_cloud.json |
| 模拟代理 40 个真实失败单元 | 全部构造提示、0 泄露 | artifacts/cp8_v1/dry_run_cloud.json |
| 基准与外部语料的修复率、费用 | 未运行（等 D12 接入模型） | — |

## 测试与开发记录
修正：入口相对路径；语言核对改按 D27 阶段表；cli 不直接依赖 agents；泄露检查改为路径形式的秘密。

## 归档与复现
`artifacts/cp8_v1/`：build_knowledge.py、dry_run.py 与云端结果；配置模板已在 CP9 改为 `artifacts/cp9_v1/agent_config.example.json`。

## 停止位置与后续边界
代码与模拟验收完成；真实小样本运行（确定 window、N、轮数并报告修复率与费用）在接入模型后进行。
