# cr_store_mando_v5：CP2.3 生产升序回归（Codex，2026-11-17）

同一 CLI 与 v3 的 846 输入顺序、--regression mando --order ascending；production profile、92 个支持编译器。843 success、3 已知 Slither 侧失败（reentrancy_bonus、reentrancy_cross_function、reentrancy_insecure）；失败没有 graph。846/846 状态、reason、选定版本、settings、flags 与 v3 相同，843/843 graph.json 字节相同。证据 ../cp2_3_v1/regression.json 与 regression_acceptance.jsonl。

store.tar.gz 是无损交付格式：4,228 个 seal 文件加 seal.json，共 4,229 成员，14148449 字节；SHA256=de29da390672b53d185c920bb994cbcee62b6dd53fd76510d952c92880d2c622。seal.json SHA256=db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b。每个成员 SHA 已回读验证，成员清单见 ../cp2_3_v1/cr_store_mando_v5_archive_audit.json。本地散文件保留，README 与 tar 属交付说明，不在运行 seal 内。

运行约 239.81 秒，CLI rc2 为三份预期未修复，外层验收驱动 rc0。编译器绝对路径/版本/哈希、源码身份、settings、profile、调用耗时和实现 SHA 在 trust、manifest、invocations、seal。旧 v3 和 CP0–CP2.2 批次不改。本批拒绝覆盖或原地重跑；6c 回归已结束，CP2.3 待独立审查，无 LLM 调用和费用。
