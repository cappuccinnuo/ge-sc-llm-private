# CP2.2 6c 续跑封存（2026-11-14，修改 AI：Codex）

执行 PROMPTS r2.10 §4.4c，授权在 ../cp2_2_v1/authorization.json。store.tar.gz 无损封存 57 个成员（含 seal），SHA256 b432b70257e061a5b57bc19a80f8754fdd1d03e27f2bcee3e64b64084d2a724b；逐成员回读见 ../cp2_2_v1/cp2_6c_v3_archive_audit.json。散文件保留，旧批次不改。

plan.json 绑定旧计划和 seal；comparison.jsonl 包含 239 个判定并标记 evidence_batch/reused。第 1–226 份沿用旧结论，第 227 份沿用旧 main+10，在 d20a/0227 新进程追加 1 次；其余 12 份在 continuation 的一个新进程主运行，第 239 份另起新进程连续抽取 10 次。extraction、命令、编译器 SHA、逐次计数、receipt 与子 seal 均保留。前 227 份的原始提取依赖既有 cp2_6c_v2/store.tar.gz，没有复制 EdgeSem 报告。

结果 239/239 通过：234 精确、4 D20、1 D20a；本轮新增 23 次提取。独立复算见 ../cp2_2_v1/captured_replay_audit.json，列出 12 个 L1 DEF 波动键全部计数和源码行。不能由此证明旧工具链全局确定性或内部根因。审查读取现有产物，不能原地重跑或增加样本。
