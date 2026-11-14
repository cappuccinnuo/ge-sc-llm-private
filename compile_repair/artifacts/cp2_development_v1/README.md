# CP2 开发与验收证据（修改 AI：Codex）

本批次基于 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18，PROMPTS r2.8 §4.4。状态为停止待审查：两次 production 全量各 843 成功 / 3 个已知失败，843 个图逐字节相同；6c 重放第 87 个文件 buggy_43.sol 的 occurrence 不一致（86 相同 / 1 不同），剩余 152 和降序未运行。完整报告见 ../../CP2_REPORT.md。

| 文件 | 用途 |
|---|---|
| baseline.json、audit_frozen.py、frozen_audit.json | 起始身份、原文件/环境/编译器/历史字节保护 |
| attribution_review_request.json、attribution_authorization.json、attribution_existing_production.json | 已批准只单列旧 0.4.11 → 0.4.12 选版差异，重放标准不改 |
| compiler_count_clarification.json | 保留原请求并澄清 96 可信、92 支持、4 历史 |
| pytest_*.json、pytest_*.log.gz、test_evidence_*.json.gz | production 567/6、mando 130/443、DFG 2653/9 既有 warnings |
| ascending1/2_plan、acceptance、receipt、invocation | 846 输入实际 argv、逐输入检查、封存和命令结果 |
| *.stdout.log.gz、*.stderr.log.gz | 无损原始运行日志；明文重复副本仅留本地 |
| historical_source_path_audit.json | 239 个旧目标路径与源码哈希绑定；只读 |
| replay_invocation.json、replay_discrepancy_analysis.json | 唯一重放命令和停止后的原始行独立比较 |
| cp2_summary.json | 分布、图计数、所有版本差异、停止状态 |
| *_archive_audit.json、package_store.py | 三份运行存储无损 tar；逐成员校验，原文件保留 |
| run_checks.py、run_corpus.py、run_replay.py、launch_phase.py | 本次实际运行脚本；无重试，输出存在即拒绝 |
| summarize.py、check_docs.py、doc_check_v* | 离线汇总与全部 9 份文档检查 |
| delivery_inventory.json、delivery_seal.json | 最终交付文件和哈希；封存自身不自引用 |

evidence_seal.json 是开发完成、等待归因授权时的原始快照，status 保留为 awaiting_attribution_review；后续授权与正式输出另追加，不覆盖该文件。三份 store.tar.gz 在 ../cr_store_mando_v1、../cr_store_mando_v2、../cp2_6c_v1，已各自校验全部 4,229、4,229、93 个成员。交付保留压缩日志和正式归档；不提交本地重复明文日志、散文件、/tmp 测试目录，也不删除它们。

6c 差异的原始提取层已有 252 对 251 的差异，不是比较键造成；仅旧 Post 继承上下文的 [162, out, DEF] 缺失，其他 251 行逐字段相同。底层 SSA/继承构造原因尚未证明。不得据两次生产图确定性将 CP2 宣称通过，不得重跑剩余文件或降序来掩盖首个不符。没有下载、安装、LLM 或全局 solc 修改；费用 0。最终检查结果在 CHANGE_LOG §19.5；按强制记录完成后本地提交，不自动 push。

最终检查：frozen_audit 已通过，doc_check_v1 为 9/9；最终文档用 v2 收据及完整 SHA 绑定。staging_check.json 保存首次精确暂存核验；加入 delivery_inventory/seal 后再核对全部暂存字节与 diff --check 才提交。包元数据计数以本轮 baseline/frozen_audit 的 mando 90、production 114 文件为准。
