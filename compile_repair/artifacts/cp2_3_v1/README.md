# CP2.3 本机证据（Codex，2026-11-17）

本批次实现 PROMPTS r2.11 §4.4d，起始 HEAD=361772f74b28b4dce0ad094907dc3dbf27a17794。只修改 rules/environment.py 与 pipeline.py，生产文件 14；新测试/夹具覆盖版本读取的语法与编码缺陷。详见 ../../CP2_REPORT.md 的 CP2.3 和 ../../docs/CHANGE_LOG.md §25。本目录不覆盖旧证据，不导入审查脚本。

| 证据 | 内容 |
|---|---|
| baseline.json | 开始前跟踪文件、旧结果成员、源码、环境、solc、DFG 引用及文档字节数 |
| reproduction* | 修改前 6 个 CLI 拒绝及 9 次 solc/production D3 成功对照，含调用记录 |
| code_change_summary.json、reuse_sources.json | 修改函数/行数与冻结算法/驱动来源 SHA |
| development_issues.json | 旧首次 seal 已被最终 seal_v2 替代的既有事实及处理 |
| pytest_*.json / .log.gz | production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings |
| test_evidence_*.json.gz、equivalence.json | 两环境各 846 输入 + 28 夹具等价，8 个旧路径无法解析的夹具明列 |
| probes.json、cli_probe_stores.tar.gz | 9 成功与 1 预期拒绝的真实 CLI；58 成员无损归档，审计未重复编译 |
| regression_plan/acceptance/regression | 同 v3 参数、846 逐份检查、843 图字节一致、3 已知失败 |
| cr_store_mando_v5_archive_audit.json | v5 4,229 成员逐哈希回读；tar SHA=de29da390672b53d185c920bb994cbcee62b6dd53fd76510d952c92880d2c622 |
| runtime.json、frozen_audit_v2.json | 实际版本及最终保护审计 |
| doc_check_v*、delivery_inventory/seal | 强制文档检查与本批精确交付身份 |

执行驱动均以本目录为写入范围且拒绝覆盖；launch_phase 的 reproduction/probes/regression 分别执行旧缺陷复现、已通过测试的只读审计和一次新全量回归。reproduce.py 明确要求旧生产文件哈希，因此实现后不再运行。run_checks 使用独立临时目录；probe 的完整封存存储已随 tar 交付，临时目录无需作为长期依赖。

完整命令在 CP2_REPORT 与各 invocation/pytest JSON 中。原日志和 v5 散文件保留在本地，交付时只添加清单所列文件，不清理旧未跟踪内容。本机验收完成、待独立审查；CP3 未执行，6c 不重放，无安装、下载、LLM、训练或全局 solc 操作，费用 0。

最终审计说明：frozen_audit.json 为首次现场，唯一未通过项来自把 6 个旧测试的手工空指纹 seal 计入真实 CLI；test_seal_diagnosis.json 与保留的 audit_frozen_initial.py 给出来源。最终 frozen_audit_v2.json 明确验证手工 seal 身份并核对 3 个真实 CLI seal，全项通过；未修改生产代码或验收判据，详情见 CHANGE_LOG §25 的最终补记。

交付封存版本：evidence_seal.json 保留为首次暂存前的文档快照；新 v5 README 去掉末尾冗余空行并补记处理后，最终文件清单由 evidence_seal_v2.json 与 delivery_seal.json 绑定。首次暂存空白检查现场见 staging_attempt1.json，最终文档检查见 doc_check_v3。
