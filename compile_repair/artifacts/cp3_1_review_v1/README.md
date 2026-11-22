# cp3_1_review_v1：CP3.1 审查证据（Claude，2026-11-22）

审查对象：`compile-repair@1ba841cbc`（Codex 的 CP3.1：`evaluation/report.py` 的主因口径、`toolchain/project.py::standard_json_input`、`toolchain/slither.py` 的 D21、`rules/environment.py::_expression_interval`、`pipeline.py` 的输入格式阶段，测试与产物 `cp3_1_v1/`）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Slither 0.11.6（Python 3.12.13）；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同（0.4.12–0.5.17 全部，0.8.0、0.8.4、0.8.8、0.8.38）；没有 0.6.x、0.7.x。外部语料只在用户本机；按用户“仅本地研究使用”的批准，审查从 BugmakerCC/Trace 固定提交 `4260215b` 取了第 4 条所列 22 个文件（SHA256 全部与 CP3 清单一致），只在审查工作区使用，不提交。

## 文件

| 文件 | 内容 |
|---|---|
| `oracle_pragma.py` / `oracle_pragma.json` | 独立判据：20 个与 Codex 不同的手写 pragma（通配符、缺补丁号、`^0`、`0.x` 等）× 审查环境 37 个版本，模块区间是否包含该版本与真实 solc 是否接受逐一对照 |
| `probe_wrapper_detect.py` / `probe_wrapper_detect.json` | `standard_json_input` 对 Trace 示例与 12 个手写正负例的结果 |
| `trace_parser_units.txt` | CP3.1 之后 Trace on-chain 仍为 parser_error_other 的 22 个单元（单元 ID、SHA256、文件名，取自 cp3_1_v1 的结果） |
| `inspect_nonsolidity.py` / `trace_parser_units.json` | 对这 22 个文件只记录结构特征：SHA 是否与清单一致、是否 `{{…}}` 包装及其 language、Vyper 版本注释、Vyper 修饰器行数、是否含 `pragma solidity` |

## 结论

1. **主因口径成立**：`primary_causes` 按“输入格式 / 版本计划 / 项目组装 → 有 solc 成功候选时只取其 Slither 侧原因 → 全部失败时取各版本交集，空交集为 version_dependent”实现，与 4.5b 节第 1 节一致；MANDO 三个单元的主因只有 slither_incomplete。两张表同分母 9,848。
2. **包装判定成立**：只用 JSON 解析，拒绝 NaN 等常量；双花括号、标准 JSON、Etherscan 多文件映射与前后空白都识别；ABI、Yul、截断 JSON、普通源码不识别（`probe_wrapper_detect.json`）。Trace on-chain 410 个命中，与 CP3 的 432 个 parser_error_other 相符（另 22 个见第 4 条）。两处边界：前置 UTF-8 BOM 的包装不识别；`sources` 只有 `urls`、没有 `content` 的标准 JSON 不识别，会被当作源码交给 solc。语料中这两种情况的数量未统计。
3. **D21 与 pragma 扩展成立**：D21 只读 AST 定义名称，alias_cast 与 cp3_alias 都被拒、不写图，确认重名 12 项、原成功 0 项。pragma：审查自写的 20 个表达式 × 37 个版本共 740 组，模块区间与 solc 接受与否 0 处不一致（`oracle_pragma.json`；在当前提交上重跑结果相同）。两条经验边界（0.4 系列不接受次版本位的字母通配；`^0` 从 0.5.14 起被接受）也在这 740 组之内得到确认。0.6、0.7 系列不在审查环境中，只由 Codex 的 92 版矩阵覆盖。
4. **遗留：Vyper 输入被当作 Solidity 解析错误**（`trace_parser_units.json`）。Trace on-chain 剩余的 22 个 parser_error_other 全部是 Vyper：5 个是 `language: Vyper` 的 `{{…}}` 标准 JSON 包装；16 个是带 `# @version` 或 `#pragma version` 注释的 Vyper 源码；1 个（cp3_22065）没有版本注释，但有 `event X:`、`name: public(String[32])`、`@external`、`def __init__():`。22 个都不含 `pragma solidity`，SHA 与清单一致。CP3 对 SOChecker 用词法证据规则（`evaluation/survey.py::solidity_snippet_evidence`）把 236 个非 Solidity 输入排除出统计，但这一规则只在清单脚本中使用，生产流水线没有语言判定。结果：Trace on-chain 的 22 个 Vyper 输入计入 Solidity 解析错误；在检测时，这类输入会进入后续的规则与 LLM 修复阶段。
5. **version_dependent 的主因缺少解释**：221 个单元（211 个来自 SOChecker），最常见的组合是 0.4.12–0.7.0 都为 parser_error_other、0.7.1 起为 other 与 undeclared_identifier（113 个）。这与“0.7.1 起允许文件级函数”的片段相符：能解析的版本给出的才是真正的阻碍（未声明的上下文），而交集规则把它们都放进 version_dependent，D6 排序看不到这部分原因。
6. **MANDO 回归成立**：`mando_regression_final.json` 846 条中 843 条状态、原因、选版、设置、标志、输入与图字节全部相同，3 条为预期失败且其余字段相同。
7. **执行中的问题处理得当**：D21 的 AST 不足单列（只给下限）、旧测试中“拒绝 `0.5`”的断言改为同时断言新旧行为并保留两次结果、语法拒绝单列，均先经用户批准，没有放宽判据。

## 复现

```bash
python -I oracle_pragma.py <repo> <solc 目录> oracle_pragma.json                         # Slither 0.11.6 环境，仓库根
python3 -I probe_wrapper_detect.py <repo> <Trace cp3_23864 文件或 -> probe_wrapper_detect.json
python3 -I inspect_nonsolidity.py <放 22 个 <unit_id>.sol 的目录> trace_parser_units.txt trace_parser_units.json
```
