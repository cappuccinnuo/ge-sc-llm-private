# Prompt 8B GitHub 结果归档

日期：2026-10-28；归档 AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2 分支。

本次在本地完成提交 22a57fc 的基础上归档阶段 B 结果与 Prompt 8B.0 验收证据，沿用阶段 A 的文本产物归档方式。新增90次正式拟合（G1R/G2R/G3各30），复用已归档的阶段A 60次，总计150次。不重新训练，不修改原产物、旧seal或原始预测。

## 上传范围

共 2811 个结果/证据文件、871490009 字节（约 831.12 MiB），详见[逐文件SHA清单](github_archive_prompt8b_2026-10-28.json)。包括全部新增fit的best/last元数据、内外层预测、history、梯度、资源和收据，完整最终报告与15张CSV，G*选择与seal，阶段B授权及验收，独立复核与测试记录，以及此前未跟踪的8B.0性能验收文本。

模型和训练代码已在此前提交中；本次没有新增或修改生产代码。

## 超限汇总的无损归档

以下两个文件超过本次90 MiB归档上限，保留本地原文件并上传gzip副本。压缩副本位于 prompt8b_v1/github_archive/，清单记录原路径、压缩路径及两种SHA；已实际解压校验。无需修改旧收据中的原始文件摘要。

- scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/summary.json：原文件 292.26 MiB → gzip 19.00 MiB；解压 SHA256 与原文件一致。
- scripts/DFG/experiments/artifacts/dfg_v2/prompt8b0_v1/stage_A_final_full_verification.json：原文件 97.23 MiB → gzip 6.24 MiB；解压 SHA256 与原文件一致。

## 保留在本地

.pt权重与临时锁不提交；输入图、token与源码资产不因本次归档自动上传。部分排除项为8B.0验收探针文件，不计入150次正式拟合。克隆仓库可以审阅结果，但完整重载/复跑仍需相应二进制资产。原图和封存结果未改变，归档提交不替代训练时的计算版本绑定。

WSL直接访问GitHub仍存在DNS解析失败；本次沿用已验证的Windows Git联网＋WSL gh凭据助手，命令临时配置、不输出凭据、不改全局网络设置。仅正常推送dfg-v2，不force push、不修改其他分支。

## 结果入口

- [结果解释与限制](../scripts/DFG/dfg_v2/PROMPT8B_REPORT.md)
- [完整自动报告](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/REPORT.md)
- [best均值](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/best_fold_means.csv)
- [last均值](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/last_fold_means.csv)
- [逐折结果](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/fold_metrics.csv)
- [配对差值](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/paired.csv)

最终实验仍计划在显存充足服务器单独执行；当前结果来自本机，不与未来服务器批次混合。

归档核验：2811个Git暂存blob的SHA256与清单及原文件逐一相同，三份文档保持旧正文前缀不变。默认git diff --check对既有CSV的CRLF、历史测试日志/XML中的行尾空白和已封存自动报告末尾空行提出格式提示；为保持封存SHA，不修剪原产物。新写说明文档的diff --check单独通过。
