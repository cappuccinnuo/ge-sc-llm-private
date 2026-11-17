# Prompt 8D GitHub 结果归档

日期：2026-10-29；归档AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2。

代码、测试、主报告与三份记录文档已在 5f31a66 中提交。本轮按用户“推送github”请求，追加归档 Prompt 8D 的结果证据；不训练、不修改旧图/标签/计划/seal或推断结果。

共1176个结果/证据文件，452461387字节（约431.50 MiB）；实际字节数以[逐文件SHA清单](github_archive_prompt8d_2026-10-29.json)为准。包括300份推断结果与状态/日志、完整指标CSV/JSON、A/D/E审计、F候选计划/特征元数据/分组划分、命名风险证据、独立复核、测试记录和开发期预检证据。全部文本保持原字节；单文件均小于90 MiB，不需要转换或压缩副本。

18个二进制资产（4个CPU等价性验收checkpoint、14个特征NPZ）保留本地。原作者图、历史大权重等资产不因本次归档重新上传。克隆仓库可审阅代码与结果，完整重载仍需要对应二进制输入。旧8C产物不在本次8D归档范围内。

工程验证：2643测试已在实施阶段通过，本次仅做归档SHA、UTF-8、格式、凭据模式与Git范围检查，不重复模型训练或推断。暂存blob必须与清单摘要一致；三份文档只追加，历史正文不改。既有CSV/日志可能带CRLF、行尾空白或末尾空行，为保持原SHA不修剪；新写文档独立检查格式。

本次WSL Git已能直接访问GitHub，使用正常非force推送；不改全局DNS、代理或凭据配置。最终是否完成以远端dfg-v2 SHA与本地HEAD一致为准。

F的170次正式拟合仍未授权；选择性idN命名保留注入标记的限制不因归档而解决。最终实验将按用户安排在显存充足服务器运行，当前4GiB只是本机开发限制，不混合两地结果。

入口：[Prompt 8D报告](../scripts/DFG/dfg_v2/PROMPT8D_REPORT.md)、[300结果汇总](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/BC_run/summary/summary.json)、[命名风险](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F_naming_risk/CAVEAT.md)。
