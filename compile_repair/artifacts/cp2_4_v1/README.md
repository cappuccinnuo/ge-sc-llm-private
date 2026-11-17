# cp2_4_v1：pragma 注释与未结束指令验收（修改 AI：Codex）

本批次按 PROMPTS r2.12 §4.4e 执行。旧批次只读；生产只改 environment.py，使用已有 production/mando 环境和 92 个支持版本，不安装或下载。完整说明在 CP2_REPORT 的 CP2.4、CHANGE_LOG §27，当前状态为本机验收通过、待独立审查。

| 文件 | 用途 |
|---|---|
| baseline.json、environment_cp23.py | 起始跟踪/封存/环境哈希；测试专用 CP2.3 原实现快照 |
| fixture_sources.json、reuse_sources.json | 三个原样夹具与复用驱动的来源 SHA |
| reproduce.py、reproduction.json、reproduction_invocations.jsonl、reproduction_cli/ | 修改前复现；两注释直接工具成功、旧 CLI 拒绝，缺分号与 union 旧消息相同 |
| run_checks.py、pytest_*.json / .log.gz、test_evidence_*.json.gz | 两环境模块与 DFG 测试命令、日志和明细 |
| equivalence.json | 每环境 846 MANDO + 35 可读取夹具，1,762 份完整计划全同；4 个原拒绝输入明列 |
| cli_acceptance.json、cli_acceptance_store.tar.gz | 原测试 CLI 的两正两负结果；21 成员逐个回读，无重复运行 |
| runtime.json、development_issues.json | 现场版本、开发处理与既有待处理问题 |
| audit_results.py、audit_frozen.py、code_change_summary.json、frozen_audit.json | 只读验收与保护检查，生产文件数及函数改动 |
| write_documents.py、check_docs.py、doc_check_v* | UTF-8 文档写入与检查；旧记录按字节前缀保护 |
| evidence_seal.json、delivery_inventory.json | 本轮证据与精确交付清单（不包含这些文件自身的循环哈希） |

测试：production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG 2653 passed/9 warnings。两注释 CLI 分别选 0.8.0、0.5.0，D3 成立，源码不变；缺分号和 union 保留同一 flags、不同 error_first_line，工具调用为零。原始临时目录与调用参数见 pytest_*.json，旧 846 全量生产与 6c 本轮未运行。

复现测试命令见 CP2_REPORT；从仓库根设置 PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2 和既有 TREE_SITTER_LIB_DIR。各驱动输出拒绝覆盖，后续需新建批次；reproduce.py 必须在未修改的 CP2.3 实现上运行，当前实现不能通过其旧代码哈希检查。原文件和临时结果保留，未清理历史未跟踪内容。

成本 0；无 LLM、下载、安装、训练、GPU 锁或全局 solc 选择。两项语义偏离由 CP2.4 明确授权，详见 DECISIONS；没有方案外调整。
