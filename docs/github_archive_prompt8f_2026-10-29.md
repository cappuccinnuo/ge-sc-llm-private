# Prompt 8F GitHub 结果归档

日期：2026-10-29；归档 AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2。

代码、测试、主报告与三份记录文档已在9ab9080a886dfcb2cd604807d9572cf463d44989提交。本次按用户“推送github”请求，归档Prompt8F全部322个JSON/日志/源码快照，共18097340字节（约17.26MiB）。逐文件路径、大小与SHA256见[清单](github_archive_prompt8f_2026-10-29.json)。

归档包括256个源码身份的命名决定、三轮语义核验、合成节点投影阻断证据、固定政策和manifest/seal、最终接受决定、测试日志、源码快照、完整性/清理记录及本地提交收据。最大单文件小于1MiB，无需压缩。没有新增权重或特征NPZ；其他批次的未跟踪文件不纳入。

当前状态仍是blocked_by_binding_or_semantic_gate：87个源码身份全部核验通过，159个整文件绑定回退，10个投影阻断；384个任务文件引用为132通过、233回退、19投影阻断。不是完整可训练N-anon基准。正式HGT拟合0，诊断分类器拟合0，未执行P2/P3、新特征编码或170-fit计划。接受决定seal不是训练plan。

实施阶段2713项测试通过。本次仅做归档格式、常见凭据模式、seal/来源、最终运行代码SHA、历史8E产物和暂存blob核验；不重跑分析、探针或训练。开发期检查器更正与临时目录setup失败日志原样保留。implementation_snapshots可重建早期收据所绑定的新模块版本；旧seal不改。local_commit_receipt中的pushed=false表示收据生成时未推送，不重写成当前状态。

本次三份记录只追加；正式结果逐字节保留。使用WSL Git正常推送origin/dfg-v2，不force，不写入作者upstream仓库。完成以远端refs/heads/dfg-v2 SHA与本地HEAD一致为依据。

最终实验按用户安排使用显存充足服务器；当前本机4GiB只是开发限制。本轮正确性阻断与显存无关，服务器尚未实际验收。

入口：[Prompt 8F报告](../scripts/DFG/dfg_v2/PROMPT8F_REPORT.md)、[最终语义核验](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/semantic_final/summary.json)、[接受决定](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8f_v1/acceptance/acceptance_decision.json)。

归档格式补充：完整git diff --check检出早期pytest失败日志v2_tests.log中的行尾空格。这是原始诊断输出，保留原字节以保证SHA，不修剪日志；非日志文档/源码快照的差异检查单独通过。没有忽略代码或文档的空白错误。
