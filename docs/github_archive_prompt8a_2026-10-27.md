# Prompt 8 / Prompt 8A GitHub 结果归档

日期：2026-10-27；归档 AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2 分支。

本次归档在已完成的本地文档提交 a26f801 基础上补充结果文件，不重训、不修改已封存图、计划、收据或预测。阶段 A 60/60 成功；阶段 B 未执行。

## 已纳入 Git

原路径下的 prompt8_v1 与 prompt8a_v1 全部文本产物，共1721个文件、321382664字节（约306.5 MiB）。包括：

- Prompt 8 的计划、seal、准备清单、150份初值身份与摘要、批准记录和测试记录。
- Prompt 8A 的60次正式拟合结果、best/last元数据、内外层逐样本预测、逐轮history、梯度与schema审计、资源采样、执行与验收收据。
- 阶段A完整中间报告、15张CSV、report.json与报告收据。
- 本轮预检、测试XML/日志、最终来源核验与重复验收计时证据。

逐文件相对路径、字节数和SHA256见[归档清单](github_archive_prompt8a_2026-10-27.json)。未改任何原产物字节；没有把旧的无关实验目录一并暂存。

## 仍保留在本地的文件

270个.pt文件合计12254508170字节（约11.41 GiB），包括150份未训练初值与120份best/last权重，遵循已有.gitignore保留在WSL的E盘存储；各文件SHA256已列在清单。另排除1个空的临时锁文件。

原图、token、源码等输入也没有因本次归档自动上传。只克隆Git仓库可以阅读本批结果与证据，不能直接重新训练或重载模型；仍须取得匹配的输入和权重资产。本归档不等同全部二进制实验资产备份。

## 入口

- [实施与结果摘要](../scripts/DFG/dfg_v2/PROMPT8A_REPORT.md)
- [阶段A完整中间报告](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/REPORT_INTERIM_A.md)
- [best均值](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/best_fold_means.csv)
- [last均值](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/last_fold_means.csv)
- [逐折结果](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/fold_metrics.csv)
- [配对差与统计](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/interim_A/paired.csv)
- [最终来源验收](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8a_v1/final_provenance_acceptance.json)

归档提交仅改变Git跟踪范围与说明文档。原训练计算仍绑定运行时6dd5d986及其文件SHA，不通过修改旧seal适配新文档提交。完整实验后续在显存充足服务器单独执行，不能将本机与服务器批次混合统计。
