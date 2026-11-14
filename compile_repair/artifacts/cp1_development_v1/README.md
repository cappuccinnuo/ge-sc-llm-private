# CP1 开发、测试与冻结证据（修改 AI：Codex）

日期 2026-11-14；依据 PROMPTS r2.6 §4.3；起始 d5e84d39。完整解释见 ../../CP1_REPORT.md 和 ../../docs/CHANGE_LOG.md §15。

本目录包含 baseline.json、implementation_audit.json、offline_replay_*.json.gz、settings_acceptance.json、pytest_*.json 与无损压缩日志、正式测量进程收据、cwd_command_inspection.json，以及提交前的 frozen_audit/doc_check/staging/file_inventory/seal。源码、环境和全局 solc 的旧身份在 baseline 中，新实现身份在 implementation_audit 与 case seals 中。

run_checks.py 记录完整命令、环境、耗时和日志哈希；production、mando、dfg 分别运行两环境模块测试与冻结 DFG；sample、historical 调用同目录的两个正式测量脚本。audit_frozen.py 只读复查旧文件与代码引用。所有输出使用排他创建，失败不自动重试；本目录已存在的批次不能再次运行并覆盖。

实测：生产 546 passed / 6 skipped，mando 116 passed / 436 skipped，DFG 2653 passed / 9 warnings；两个离线归档各 846 条，升降序都等于 CP0，归档内容跨环境相同；设置自动重试 6/6。归档时发现 pytest current 符号链接别名，排除别名后读取原结果，没有重跑或变更标准。

原始 .log 和 tmp_pytest_* 只保留本地，提交压缩日志、收据及所需验收归档。读取 gzip 可无损重现原输出并核验 log_sha256。所有拟提交文件由 file_inventory.json 精确列出，三个顶层 seal 的哈希在 seal_hashes.json；本目录封存排除 seal 自身、哈希索引、提交清单和本地临时树，避免自引用。

交接文档的 WSL 启动中断与恢复核验另存 documentation_interruption.json；四文件 SHA 未变后分批写入，未重复追加或重跑实验。
