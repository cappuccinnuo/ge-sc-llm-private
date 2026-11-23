# CP5 中途检查点

修改 AI 为 Codex。输入提交 `26f44492`，方案 r2.22。本批次保存已完成的前置审计、注册表查询、149 份发布版收据、真实图回归和开发探针。完整报告在 [CP5_REPORT.md](../../CP5_REPORT.md)。

| 检查 | 可复核文件 |
|---|---|
| 16,136 个基础图自比、历史名称状态 | `self_summary.json`、`self_scores.jsonl.gz`、`historical_status.json` |
| 9,144 个单元及项目清单、目录与 pragma | `measurement.json`、`measurement_units.jsonl.gz`、`measurement_verification.json` |
| D22、元数据授权、D23 精确发布版与硬上限 | `authorization.json`、`registry_metadata_request.json`、`d23_download_request.json`、`d23/authorization.json` |
| 官方元数据与停止位置 | `registry_get_summary.json`、`registry_head_summary.json`、`d23/download.jsonl`、`d23/download.log`、`d23/transport_stop.json` |
| 参数范围待确认 | `optimizer_request.json` 与 `measurement.json` 中的包装设置 |
| 命名空间、附加源、三条修复路径 | `project_probe.py`、`multi_input_probe.json`、`step_probes.log`、`implementation_checks/` |
| MANDO 的 846 项逐项结果 | `mando_regression.py`、`mando_regression.jsonl`、`mando_regression.json` |
| 开发、测试划分及四个开发探针 | `benchmark_inventory.json`、`dev_probes.jsonl`、`dev_probes.log` |
| 源文件数、旧评分器、DFG 引用、SHA 与文档 | `checkpoint_audit.json`、`checkpoint_doc_check.json`、`checkpoint_seal.json` |

工作树外的 `corpora/compile-repair-npm-cp5-v1/archives/` 保存压缩包。`compile-repair-local/cp5_v1/` 保存运行副本与逐次工具输出。第 150 个 URL 在取得 HTTP 状态前断开，等待用户决定是否续传剩余 23 份。`d23/download_remaining.py` 的入口核对续传授权、原日志 SHA 和已收取的每个文件。完整发布版清单与开发规则就绪后再统计真实修复效果。

`checkpoint_seal.json` 记录本次检查点的文件 SHA256。后续结果另加独立记录。

与当前生产文件 SHA 完全对应的最终 MANDO 回归在 `final_mando/summary.json` 和 `final_mando/rows.jsonl`。完整开发集、测试集与外部主因重跑的入口是 `run_benchmark.py dev`、`run_benchmark.py test`、`run_external.py`，本次只检查了驱动语法。运行条件包括 172 个发布版的完整索引，测试与外部运行另外读取开发集冻结的策略。最终六份文档的检查见 `checkpoint_doc_final.json`。
