# cp2_6c_v1 运行归档（修改 AI：Codex）

6c 精确重放已停止：87/239 已运行，86 相同、1 不同；剩余 152 未运行。

本目录的 store.tar.gz 无损保存原始运行输出 93 个成员（含原 seal.json），逐成员 SHA256 回读一致。原始散文件仅留本地且未改动；tar 和本 README 属于交付包装，不在原运行 seal 中。完整成员清单见 ../cp2_development_v1/cp2_6c_v1_archive_audit.json；报告见 ../../CP2_REPORT.md。

归档 SHA256：a4a90b5c76aab316a734bce3de682fc7b501c45086c789f78cb4be002673dea1。

原 seal SHA256：28fbe6fe70787536f0becba9976c6f273101d237ee456324bf246020ba906132。

CP2 整体验收未通过；差异现场在 cp2_6c_v1，原因边界在 replay_discrepancy_analysis.json。当前不得自动重跑，不覆盖旧输出。可用 tar -tzf 查看清单，用 tar -xOzf 读取具体成员，不需要编译或安装。
