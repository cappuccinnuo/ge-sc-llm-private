# CP0 续作证据说明

修改 AI：Codex。日期：2026-11-12（America/New_York）。本目录记录用户批准安装后，按 PROMPTS r2.2 继续 CP0 的开发与验收。正式调查结果另存 `../cp0_v2/`；原 `../cp0_v1/` 停止现场保持不变。

- `baseline.json`、`pull.json`、`merge_start.json`、`merge_resolution.json`：起始本地提交、文档字节数及上游合并证据。上游 r2.2 与本地 CP0 检查点分叉，未强制覆盖历史。
- `compatibility_installation_request.json`：十个边界探针版本的具体请求。用户批准原话、版本、费用上限及二进制校验结果保存在 `../cp0_compatibility_install_v1/`；单独批准的 0.4.17 保存在 `../cp0_compiler_install_v1/`。这些目录的 `trusted_compilers_addition.json` 是独立追加清单，不改 6c 清单。
- `development_issues.json`：开发问题与解决方法；两个小样本目录 `../cp0_matrix_smoke_v1/`、`../cp0_matrix_smoke_v2/` 保留失败和修正后的证据，没有覆盖首轮结果。
- `tests_*.json` 和对应 `.log`：测试命令、退出码、耗时；`survey_cp0_v2.*`：正式命令与日志；`freeze_audit_*.json`：源码、冻结代码及环境不变量检查。
- pytest 临时目录保留在本机，不整体纳入 Git。只提交明确列出的 JSON、日志和实际双编译器 D3 探针记录。二进制安装在已有 solc-select 目录，不提交二进制。

所有网络获取都经既有代理，未设置直连回退。没有安装或升级 Python 包，没有切换全局 solc。下载费用上限为 0 美元，未调用 LLM 或启动 HGT 训练。
