# cp3_2_review_v1：CP3.2 审查证据（Claude，2026-11-22）

审查对象：`compile-repair@7336436e7`（Codex 的 CP3.2：`toolchain/project.py` 的 `solidity_snippet_evidence`、`_input_json`、`_source_wrapper`、`_vyper_basis`、`input_format_evidence`，`pipeline.repair_unit`，`evaluation/report.py` 的输入阶段与 `parseable_version_blockers`，`tests/test_cp32.py`，产物 `cp3_2_v1/`）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12.13、Slither 0.11.6。CP3.1 审查时按用户批准的本地研究范围取得的 22 个 Trace on-chain 文件与 1 个包装示例（SHA 与清单一致）只在审查工作区使用，不提交。

## 文件

| 文件 | 内容 |
|---|---|
| `probe_language.py` | 对文件或目录逐个调用 `input_format_evidence`，记录状态、依据、语言与包装元数据（不含源名称与内容） |
| `adversarial/` | 审查手写的 11 个边界输入：NatSpec 与字符串中的 Vyper 字样、块注释中的 Vyper 片段、顶层 struct、空文件、纯注释、带 BOM 的包装、只有 urls 的包装、Yul 包装、无版本与声明的 Vyper、`# pragma version ^0.4.0` 的 Vyper、带游离 `#` 行的 Solidity |
| `probe_language_adversarial.json` | 上述 11 例的结果 |
| `probe_language_real.json` | `experiments/ge-sc-data/source_code` 全部 .sol（含 MANDO 846）、`tests/fixtures`、22 个 Trace Vyper 文件与 1 个包装示例的结果 |

## 结论

1. **Codex 偏离 r2.15 的方案是正确的**：4.5c 节要求“不是 JSON 且词法证据为非 Solidity → non_solidity_input”，并以“原成功单元全部判为 Solidity”为硬判据。Codex 实测发现 8 个原成功单元（3 个空文件、4 个纯注释文件、1 个只有顶层 struct 的文件；solc rc 0、D3 为真、图为 0 个节点）会被误排除，于是在改生产代码前停下咨询。用户批准三态判定：只有明确的其他语言证据（JSON 的 language、Vyper 版本指令、或 Vyper 修饰器 + 函数 + 声明同时出现）才排除，证据不足为 unknown 并照常编译。原方案的规则过严，三态判定既满足硬判据，也覆盖审查发现的 22 个 Vyper。
2. **实现成立**（`probe_language_adversarial.json`）：注释、NatSpec 与字符串中的 Vyper 字样不影响 Solidity 判定；空文件、纯注释、顶层 struct 为 unknown；BOM 包装与只有 urls 的包装识别为包装，后者记 `content_missing`；Yul 包装与 `# pragma version` 的 Vyper 判为非 Solidity。无版本注释、也无 event/public 声明的 Vyper 为 unknown，会进入编译（Codex 已列为已知限制）。
3. **真实输入成立**（`probe_language_real.json`）：源码目录全部 .sol（含 MANDO 846）与测试夹具共 1,694 个全部判为 Solidity，没有 unknown；22 个 Trace Vyper 全部判为非 Solidity（16 个版本指令、5 个 JSON 语言、1 个修饰器 + 函数 + 声明）；包装示例的 20 个源与 6 个 settings 键与 CP3.1 审查一致。Codex 报告的第 23 个排除项 cp3_25855 是 CP3 中归为 unbalanced_structure 的 Vyper 文件。
4. **统计一致**：31,307 = 31,284 放行 + 23 排除；31,284 = 21,223 成功 + 9,825 失败 + 236 未测；parser_error_other 279 → 257（−22）、unbalanced_structure 56 → 55（−1），与 23 个排除项的原主因相符。`parseable_version_blockers` 的规则与 4.5c 节第 3 节一致。
5. **测试**：审查环境运行 `test_cp32.py`、`test_cp31.py`、`test_diagnostics.py`、`test_cp3_report.py`，132 项全部通过。
6. **带入后续 CP 的已知限制（不阻塞 CP4）**：（a）缺少正证据的其他语言输入（如无版本、无声明的 Vyper）为 unknown，会进入修复阶段，CP8 的第一阶段应在只有解析类错误且语言为 unknown 时先做一次语言核对再调用 LLM；（b）SOChecker 236 个 unknown 输入在 CP3 统计中未测，CP10 的外部语料评估中运行；（c）空文件、纯注释、只有类型声明的文件“成功”时图为 0 个节点，CP4 的基础单元必须排除 0 节点图。

## 复现

```bash
python3 -I probe_language.py <repo> probe_language_adversarial.json adversarial
python3 -I probe_language.py <repo> probe_language_real.json experiments/ge-sc-data/source_code <22 个 Vyper 文件目录> <包装示例> compile_repair/tests/fixtures
```
