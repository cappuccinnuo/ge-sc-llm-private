# Prompt 8E GitHub 结果归档

日期：2026-10-29；归档 AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2。

代码、测试、主报告与三份记录文档已在 96aa742060cb4e9aad760ab57d4bc0bb6ebd577f 提交。本次按用户“推送github”请求，追加归档 Prompt 8E 的全部 64 个 JSON/日志文件，共 101824681 字节（约 97.11 MiB）。逐文件路径、字节数和 SHA256 见[清单](github_archive_prompt8e_2026-10-29.json)。

归档包括名称池、4807 个名称映射、封存协议、160 项任务×文件语义核验、P1/P2/P3 与关键字诊断、独立复算、验收决定、测试日志和实现期检查记录。结果原字节保持不变，文件均小于 16 MiB，无需压缩替代。没有新增模型权重或特征 NPZ；历史大权重、输入图和其他阶段资产不重复上传。

**当前验收仍未通过：** 访问控制 P2 两项和 P3 总体 AUC 未达到预定门槛。状态保持 blocked_by_preregistered_leakage_gate；HGT 正式训练 0 次，P3 诊断逻辑回归 15 次。没有启动新 170-fit 计划，也未改变映射、阈值或历史实验。acceptance_decision.seal 只封存停止决定，不是可运行训练计划。

保留开发期检查及后续更正：protected_before_docs.json 针对旧运行列表的失败不删除，protected_current_runtime.json 使用实际 8B.0 修订后的运行摘要核验。local_commit_receipt.json 的 pushed=false 是本次推送前的历史状态，不重写。实时推送完成情况以远端分支 SHA 与本地 HEAD 相同为准。

实施阶段已通过 2678 项测试；本次只验证 UTF-8/JSON 格式、凭据模式、三份 seal、逐文件 SHA 和暂存范围，不重复训练或探针。三份文档只追加，原正文与结果保持不变。使用 WSL Git 正常推送 origin/dfg-v2，不 force、不修改上游作者仓库。

最终正式实验仍按用户安排在显存充足服务器运行；当前 4GiB 是本机开发限制，服务器尚未实际验收。

入口：[Prompt 8E 报告](../scripts/DFG/dfg_v2/PROMPT8E_REPORT.md)、[探针汇总](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/probes/summary.json)、[验收决定](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8e_v1/acceptance/acceptance_decision.json)。
