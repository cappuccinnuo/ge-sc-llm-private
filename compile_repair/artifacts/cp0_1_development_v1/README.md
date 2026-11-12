# CP0.1 A 开发、测试与待批准清单（修改 AI：Codex）

本目录保存 PROMPTS r2.3 §4.2b 的 A 部分开发证据。正式重验写在相邻的 `cp0_1_v1/`，完整解释见 `../../CP0_1_REPORT.md`。旧 CP0 产物与报告保持只读。

| 文件 | 用途 |
|---|---|
| `baseline.json` | 起始 HEAD、354 个冻结代码引用、旧模块文件 SHA256、文档追加偏移、环境与全局 solc 状态 |
| `api_probe_solc_*.json`、`api_probe_slither_*.json` | 先于实现的真实 0.4.12/0.8.0 API 检查：旧式/compact AST 和 compilation_units 属性 |
| `fixture_results.json` | 从最终模块测试临时目录整理的六次真实编译/Slither 结果；含 0.4.11 负对照 |
| `pytest_toolchain_v1.log/json` | 37 项针对性测试，保留首次运行结果 |
| `pytest_compile_repair_v1.log/json` | 全部 55 项模块测试的命令、退出码与耗时 |
| `pytest_dfg_v2_v1.log/json` | 冻结 DFG v2 回归：2653 passed、9 warnings；与 A3 部分重叠运行 |
| `a3_run.log/json` | `revalidate-cp0` 的完整命令、进度与进程退出码 |
| `environment_installation_request.json` | D16/B 的具体待批准请求；没有创建新环境，没有下载/安装 |
| `compiler_installation_request.json` | D18/C 的 59 个精确版本、官方 SHA256/Keccak256 与 URL；没有下载/安装 |
| `development_notes.json` | WSL 文件编辑工具问题及解决方法；transient 探针版本边界的待核对项 |
| `final_audit.json` | 完成时的代码、输入、旧证据、运行产物和环境不变量核对 |
| `doc_check_v*.log/json` | UTF-8/中文检查的逐文件结果；不能只看工具进程退出码 |
| `artifact_index.json` | 本目录本次显式归档文件及 SHA256；pytest 临时树留在本地、不整体提交 |

`cp0_1_v1/revalidation.json` 是 A3 逐文件报告；`invocations.jsonl` 保存所有直接 solc 与 Slither 调用；`cross_version.jsonl` 保存全部跨版本差异（包括只作诊断的 length）；`node_facts_v2.jsonl.gz` 保留完整节点记录，供获批后的 B 对照；`seal.json` 绑定这些文件。节点记录仅是验证证据，本轮未写 CP2 图存储。

所有测试与编译使用现有 mando Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4，OMP_NUM_THREADS=2、MKL_NUM_THREADS=2。两项待批准请求的费用上限均为 0 美元；批准之前不得把 pending 状态改成 approved。B/C 按 PROMPTS 明确要求暂停，A 的代码与文档检查完成后先作本地提交，不推送。
