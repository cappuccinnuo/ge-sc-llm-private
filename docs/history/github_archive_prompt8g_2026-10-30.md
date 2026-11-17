# Prompt 8G GitHub 代码与结果归档

日期：2026-10-30；归档 AI：Codex；目标：cappuccinnuo/ge-sc-llm-private 的 dfg-v2。

实现、83项新测试、报告、README和三份记录已在68e6ce122a06bb4b6003b875a9a8817583852de7提交。本次根据用户“推送github”归档全部349份Prompt8G文本产物，118831490字节（约113.33MiB）；逐文件大小/SHA见[清单](github_archive_prompt8g_2026-10-30.json)。

包含：256源码身份的拼写映射、384任务文件依赖与投影核验、36合成节点恢复、冻结探针计划/OOF预测/角色AUC/关键词基线、全部特征manifest、完整及中断模型装配收据、170项未授权计划/seal/模板、测试日志、独立审计脚本/结果、清理记录与本地提交收据。原字节保持，最大文件约11.47MiB，无需压缩替换。

沿用之前方式，8个特征NPZ（2977008字节，约2.84MiB）保留本地，SHA及路径记录在清单的excluded_local_feature_files；原图、tokenizer资产、旧零步初值也不是本次新归档内容。源码可生成特征，但仅克隆仓库仍需另配这些既有输入。其他阶段未跟踪数据不纳入，本次不删除或改动任何模型/输入。

本次重新只读核验plan/seal、全部384项语义证据、256源码、6模块实现SHA、特征及模型引用和322份旧8F归档；UTF-8、JSON及常见凭据模式检查通过。实现阶段2796项测试通过，本次没有重新运行探针/前向/训练。正式HGT fit仍0，P3 CPU诊断LR fit仍5；170项execution_authorized=false，后续标签/seed/位置和执行器接入待确定。

历史local_commit_receipt中的pushed=false表示产生该收据时的状态，保留原样；实时推送以本地/远端HEAD一致为准。代码与归档是连续两个提交，不覆盖旧seal。三份记录只追加，暂存blob逐项对照清单，不使用git add全仓库。

网络情况：WSL直连DNS解析失败，Windows代理仅监听127.0.0.1:7897，WSL无法直接访问。沿用Windows Git＋现有Windows代理＋WSL gh auth git-credential，命令级配置、不改全局设置、不暴露凭据。首次绝对/usr/bin/gh被Git Bash转换为Windows路径，改用已有gh命令后认证正常；读取远端为62b73866，属于本地祖先。没有分支保护拒绝，也不force push，只写用户origin/dfg-v2，不写作者upstream。最终成功以实际远端SHA核验为准。

最终实验按用户安排在显存充足服务器整批运行，本机4GiB仅为开发限制；服务器尚未实测，不混用两地成绩。归档成功不等于授权开训或已经获得新HGT结果。

入口：[Prompt8G报告](../scripts/DFG/dfg_v2/PROMPT8G_REPORT.md)、[执行说明](../scripts/DFG/dfg_v2/benchmark_v2/PROMPT8G_README.md)、[未授权计划](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/plan/plan.json)。
