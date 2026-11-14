# cr_store_mando_v1 运行归档（修改 AI：Codex）

生产全量已完成：846 个输入、843 成功图、3 个预期 Slither 侧未修复；两次图逐字节一致。

本目录的 store.tar.gz 无损保存原始运行输出 4229 个成员（含原 seal.json），逐成员 SHA256 回读一致。原始散文件仅留本地且未改动；tar 和本 README 属于交付包装，不在原运行 seal 中。完整成员清单见 ../cp2_development_v1/cr_store_mando_v1_archive_audit.json；报告见 ../../CP2_REPORT.md。

归档 SHA256：246bd09d1eddc4167b1caf951742d2e0578d77ec6cc0a937778f983dcd0f8d86。

原 seal SHA256：6a677dbac2d113a973cb0f652d500c9f69dcf5194b3e296952e4175b02933c31。

CP2 整体验收未通过；差异现场在 cp2_6c_v1，原因边界在 replay_discrepancy_analysis.json。当前不得自动重跑，不覆盖旧输出。可用 tar -tzf 查看清单，用 tar -xOzf 读取具体成员，不需要编译或安装。
