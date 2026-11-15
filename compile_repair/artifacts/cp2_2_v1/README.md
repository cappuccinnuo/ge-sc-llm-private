# CP2.2：D20a、6c 续跑与降序验收（2026-11-14，修改 AI：Codex）

执行 PROMPTS r2.10 §4.4c，起始 compile-repair@36c6109fa9271608feb8f4634eca6ab7ff6a192a；pull --ff-only 已同步。用户原话“同意 D20a”的授权先落盘于 authorization.json，DECISIONS 已更新为已定。生产代码与测试文件没有改动，CP0–CP2.1 产物不修改或覆盖。

6c 完成 239/239：234 个主运行精确相同、4 个 D20 通过、1 个 D20a 通过。沿用旧批次 227 个主样本（前 226 结论不变，第 227 只追加 D20a）；第 227 文件只追加 1 次即观察到参考重数并停止。剩余 12 个主运行在另一个新进程按原顺序执行，第 239 个差异另起一个进程连续抽取 10 次后通过 D20。本轮合计新增 23 次提取。全部 12 个不稳定键、原 11 次及追加计数、变量、源码行、继承上下文见 captured_replay_audit.json；5 个继承、7 个非继承，均 L1 DEF。

降序同一 CLI 覆盖 846 个输入，843 成功、3 个已知 Slither 侧失败。与 cr_store_mando_v3 比较：229 同版、614 不同版，843/843 key5 与规范化有序 IR 相同，全部差异条目为空。source length 815 同、28 不同，仅诊断；完整逐文件比较、版本对及按类别分布见 descending_comparison.json。

| 文件 | 用途 |
|---|---|
| authorization、baseline、evidence_seal | 授权、修改前身份、14 个生产文件 SHA |
| run_replay、d20a_rule_checks、replay_invocation | 冻结提取的续跑、11 个合成边界检查和实际命令 |
| audit_replay、captured_replay_audit | 独立复算全部判据、提前停止与不稳定键，不新增提取 |
| run_corpus、descending_plan/acceptance/receipt/invocation | 完整 846 文件降序 CLI 和逐份验收 |
| summarize、descending_comparison、cp2_2_summary | 独立节点/IR 比较、分布和总结果 |
| run_checks、pytest_*、test_evidence_* | 两环境模块与冻结 DFG 测试，原日志 gzip 交付 |
| package_store、*_archive_audit | 新批次打包与逐成员回读，散文件保留 |
| audit_frozen、frozen_audit | 生产文件、旧产物、语料、环境、编译器与历史保护 |
| check_docs、doc_check_v* | 8 份文档检查，追加文档使用原字节偏移 |
| delivery_inventory、delivery_seal | 最终精确交付路径和字节身份 |

生产测试 585 passed/6 skipped，mando 147/444，DFG 2653 passed/9 既有 warnings。命令、耗时和资源见各 invocation/pytest receipt。正式新产物为 ../cp2_6c_v3/store.tar.gz 与 ../cp2_desc_v1/store.tar.gz；前 227 份原始提取依赖旧 cp2_6c_v2，不复制历史样本。

本机验收完成，等待独立审查后进入 CP3。无安装、下载依赖/语料/文档、LLM、HGT 训练、GPU 锁或全局 solc 操作，费用 0；只在强制记录和最终检查通过后本地提交，不自动 push。目录和结果拒绝覆盖，实际执行命令见 CP2_REPORT 的 CP2.2，不可对已有批次直接重跑。
