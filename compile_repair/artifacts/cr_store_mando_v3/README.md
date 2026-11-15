# cr_store_mando_v3：CP2.1 新批次（修改 AI：Codex）

production 升序全量：843 成功、3 既有失败。v3/v4 的 843 个 graph.json 字节相同，仅修正审查指定的 86 条边。

日期 2026-11-14，起始 HEAD 1ed79a6708f505ecb9aa80b157a43f9e07608c9f，依据 PROMPTS r2.9 §4.4b 与 D20 授权。完整说明见 ../../CP2_REPORT.md 的 CP2.1、../cp2_1_v1/README.md。

store.tar.gz 包含 4229 个原始成员，SHA256 29a4ccba5612d2a6a1df896647a66d4babd7f6e175b424ece695f152eddba513；seal.json 位于归档内，逐成员回读全部一致。编译器、路径、命令、源码与实现身份记录在归档内 plan/trust/invocations/seal。本地原始散文件保留，旧 CP0–CP2 批次不改。

当前 CP2.1 整体因 D20 失败停止；不要覆写本目录或直接重跑，续验需另行明确范围和新批次。归档仅封存实测内容，不代表全部验收通过。
