# CompileRepair 代理接口：如何接入一个模型（修改 AI：Claude，2026-11-27）

本文说明 LLM 代理（第一阶段 agents/stage1.py、第二阶段 agents/stage2.py）需要什么样的模型 API、配置文件怎么写、运行后留下什么记录。模型尚未选定（D12）：选定后只需按第 3 节填写一个 JSON 文件，不需要改代码。设计依据见 PROMPTS 3.5、3.6 与 4.8、4.9 节。

## 1. 代理在流程中的位置

`compile_repair repair <路径> --output <目录> --agent-config <配置.json>`

- 不给 `--agent-config` 时不调用任何 LLM，流程与 CP7 完全相同（MANDO 回归核对）。
- 给出时：确定性规则不再改动后进入第一阶段（单模型、N 个候选、编译择优）；第一阶段停止后进入第二阶段（失败分析 → 扩展上下文 → 2–3 个模型独立提议 → 编译器裁决 → 至多一轮交流）。任何一个被接受的改动都让单元回到规则循环。
- 模型只看到 D10 视图：文件名换成 F1、F2…，注释换成等长空格，编译器消息中的路径换成编号。模型的回答只能是 REPLACE / INSERT 补丁块（格式写在提示里，见 agents/prompt.py `FORMAT`），由 agents/patch.py 逐行核对原文后才会被编译。输入文件永远不被修改。

## 2. 对模型 API 的要求

| 要求 | 说明 |
|---|---|
| 文本输入、文本输出 | 一个 system 提示加一条 user 消息，回答为纯文本；不需要工具调用、函数调用或 JSON 模式 |
| 上下文长度 | 云端模拟运行中最长的提示约 34,300 字符（第二阶段带整份项目文件时），约 1 万令牌；加上回答上限 2,048 令牌，模型上下文至少约 16k 令牌 |
| 采样参数 | 支持 temperature（默认 0.8，用于让 N 个候选不同） |
| 用量返回 | 每次响应必须返回输入与输出令牌数（用于记账；见下表字段） |
| 认证 | 密钥放在一个环境变量中；配置文件只写该变量的名字 |
| 网络 | 运行机器能访问该 API 地址（云端会话的网络有白名单，真实调用通常在本机运行） |

已实现的两种协议（agents/llm.py `HttpClient`）：

| `api` | 默认地址 | 请求 | 读取的响应字段 |
|---|---|---|---|
| `anthropic` | `https://api.anthropic.com/v1/messages` | 头：`x-api-key`、`anthropic-version: 2023-06-01`；体：`model`、`max_tokens`、`temperature`、`system`、`messages=[{role:user}]`。N 个候选发 N 次请求 | `content[].text`（type 为 text 的块）、`usage.input_tokens`、`usage.output_tokens` |
| `openai` | `https://api.openai.com/v1/chat/completions` | 头：`authorization: Bearer <key>`；体：`model`、`n`、`max_tokens`、`temperature`、`messages=[system, user]` | `choices[].message.content`、`usage.prompt_tokens`、`usage.completion_tokens` |

OpenAI 兼容协议也适用于提供同样接口的其他服务或本地服务（如 vLLM、Ollama 的兼容端点）：把 `base_url` 设成它的地址即可。若服务不支持 `n`，只会返回一个候选；这时把第一阶段的 `candidates` 设为 1，或改用 anthropic 协议的逐次请求方式。

接入第三种协议：在 agents/llm.py 中给 `HttpClient._send` 加一个分支（或写一个 `Client` 子类），实现 `_send(system, prompt, n) -> (texts, input_tokens, output_tokens)`，并把新名字加入 `api` 的允许值。预算、缓存与记录由基类 `Client.complete` 统一处理，子类不需要关心。

## 3. 配置文件

示例：`artifacts/cp9_v1/agent_config.example.json`（预算为 0，任何调用都会在发送前被拒）。字段（未知字段一律报错；任何形如 `sk-…` 的值被当作密钥而拒绝整个配置）：

```json
{
 "budget": {"max_calls": 200, "max_tokens": 2000000, "max_cost_usd": 10.0},
 "cache_dir": "/path/outside/the/repo/llm-cache",
 "knowledge": "/path/to/sealed/knowledge",
 "models": {
  "primary": {"model": "<模型 id>", "api": "anthropic", "key_env": "ANTHROPIC_API_KEY",
              "pricing": {"input_per_million": 0.0, "output_per_million": 0.0},
              "temperature": 0.8, "max_output_tokens": 2048, "timeout": 120},
  "second":  {"model": "<另一模型 id>", "api": "openai", "key_env": "OPENAI_API_KEY",
              "base_url": "https://api.openai.com/v1/chat/completions",
              "pricing": {"input_per_million": 0.0, "output_per_million": 0.0}}
 },
 "stage1": {"model": "primary", "candidates": 3, "rounds": 4, "stall_rounds": 2, "window": 10, "k": 5},
 "stage2": {"analyst": "primary", "proposers": ["primary", "second"], "rounds": 2, "window": 20, "k": 5,
            "context_limit": 12000, "analysis": true, "exchange": true}
}
```

| 字段 | 含义 |
|---|---|
| `budget` | 全部模型共用的上限：调用次数、令牌总数、美元。每次调用发送前按估算检查，超出即停止该阶段（记为 `budget_exhausted`）。用户定的第一次授权运行上限为 US$10（D12） |
| `cache_dir` | 响应缓存（按请求 SHA-256）。相同请求再次运行不计费、结果可复现。放在仓库之外 |
| `knowledge` | `artifacts/cp8_v1/build_knowledge.py` 生成的封存知识目录（K1 文档、K2 库索引、K3 修复记忆）；省略则不做检索 |
| `models.<名>.pricing` | 每百万输入与输出令牌的美元单价，按服务商价目表填写；为 0 时费用记为 0、只有调用数与令牌数限制有效 |
| `stage1` | `model` 指向 `models` 中的名字；`candidates`（N）、`rounds`、`stall_rounds`（连续多少轮未接受即停止）、`window`（错误前后行数）、`k`（每个知识来源的条数） |
| `stage2` | 省略则只运行第一阶段。`analyst` 做失败分析；`proposers` 为 1–3 个模型名（D8 要求 2–3 个不同模型；1 个只用于消融）；`context_limit` 为整份文件上下文的字符上限；`analysis`、`exchange` 为消融开关 |

`window`、`candidates`、`rounds` 目前是暂定值，由第一次授权运行在 CP4 基准 dev 划分上确定（PROMPTS 4.8）。

## 4. 运行与费用控制

1. 构建知识目录：`python -B compile_repair/artifacts/cp8_v1/build_knowledge.py <K1 文档根> <输出目录> --index <CP5 离线索引> [--memory <targets.json> <运行目录>]...`（K1 文档由 `artifacts/cp7_v1/fetch_docs.py` 获取）。
2. 在环境变量中放入密钥（例如 `export ANTHROPIC_API_KEY=...`），复制示例配置并填写模型、单价与预算。
3. 先用 `artifacts/cp8_v1/dry_run.py` 在真实单元上做零费用的模拟运行，确认提示构造与泄露检查无误。
4. 运行 `repair ... --agent-config <配置>`。预算用尽时流程照常结束，未修复的单元记为未修复。
5. 第二阶段与“给第一阶段同等额外预算”的对照（CP9 验收、CP10 消融）：同一批单元跑两份配置，A 为 stage1 + stage2，B 为只有 stage1 且 `rounds` 增加到使 `budget.max_calls` 与 A 实际用量相同；比较修复率与费用。

## 5. 运行后留下的记录

| 位置 | 内容 |
|---|---|
| `units/<id>/llm_calls.json` | 本单元的每次调用：用途（language_check、stage1_repair、stage2_analysis、stage2_propose、stage2_exchange）、模型、请求 SHA-256、是否命中缓存、输入输出令牌、费用、耗时、错误；本单元结束时的预算快照与停止原因 |
| `units/<id>/repair_steps.json` | `agent_round`：阶段、轮次、知识条目 id、被拒补丁及原因、有效候选数、第二阶段的失败分析与扩展上下文标题、票数；每个候选的试编译结果（`agent` 字段）；`agent_end` 的停止原因 |
| `result.json` 的 provenance | 被接受的代理改动，步骤为 `stage1` 或 `stage2`，等级为 rewrite（改写错误行）或 addition（插入） |
| `summary.json` | `llm_calls`、`cost_usd` 累计 |
| `seal.json` 的 `tools.agent` | 配置中的模型、阶段参数与预算（不含密钥；只有环境变量名） |

密钥从不进入请求记录、缓存文件、日志或任何产物；测试 `test_http_client_reads_the_key_from_the_environment_only` 核对这一点。
