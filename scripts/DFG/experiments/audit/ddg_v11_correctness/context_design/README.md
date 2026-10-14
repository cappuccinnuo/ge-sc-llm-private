
# D2/D3 上下文审计与状态依赖设计

修改 AI：Codex；2026-10-13。所在工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。

本目录在 D1_REGRESSION_RESULTS.json 状态 passed 后执行 D2。只读封存作者图、预测、标签和训练划分；借助 v1.1 精确 Projector 做源码身份校验。未将修复版 E2 边混入封存 E1 覆盖/评分，未训练、未编译 Solidity、未实现状态 DDG。

结果：12 案例；480 个固定训练文件精确重复来源；447 个完成全函数回映，33 个因多个 pragma 保守记录未回映。918 项原始字节跨度检查和121个输入摘要检查通过。审计工具13项测试通过。

- D2_CONTEXT_REVIEW.md：中文结论、完整函数与分级事实。
- D2_LABEL_AMBIGUITY.md：公共 CSV/SmartBugs 与作者图标签差异，禁止自动改标。
- results/D2_CASE_AUDIT.csv：包括状态读写、权限/修饰器、缺失语义、人工复核要求。
- results/D2_TRAIN_DUPLICATES.json：训练匹配源文件、原节点 ID、源码 SHA、标签和完整函数。
- results/D2_CASE_EVIDENCE.json / D3_SOURCE_CONTEXTS.json：完整精确证据。
- D2_FINAL_VALIDATION.json：最终原输入/字节跨度/测试核验。
- D3_STATE_AWARE_DDG_DESIGN.md：中文建议与位置/别名/强弱KILL/未知入口/调用失效接口。
- D3_ORACLE_SPEC.md / D3_ORACLE_CANDIDATES.json：9项真实源码候选、5项合成规格；独立批准数0、编译验证数0。
- D3_IMPLEMENTATION_PLAN.md：未来分阶段门槛和 E0/E1/E2/E3/E4 消融设计，本轮未运行。

执行记录：

1. python -B -m scripts.DFG.experiments.audit.ddg_v11_correctness.context_design.context_audit --d1-gate scripts/DFG/experiments/audit/ddg_v11_correctness/D1_REGRESSION_RESULTS.json
2. python -B -m scripts.DFG.experiments.audit.ddg_v11_correctness.context_design.render_context
3. python -B -m scripts.DFG.experiments.audit.ddg_v11_correctness.context_design.render_oracles
4. python -B -m scripts.DFG.experiments.audit.ddg_v11_correctness.context_design.finalize_context

使用既有 mando Python，并设置 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64 与 PYTHONDONTWRITEBYTECODE=1。这些生成器拒绝覆盖已有主要结果；复跑前应使用新的隔离输出版本，不删除旧记录。root级 D2/D3 文档是此处最终文档的交付副本，链接已调整。

没有证明标签错误、状态增强必然提升 F1、完整 Solidity DDG 或精确 EVM storage slot。下一步应先人工复核候选 Oracle 和小范围可投影信息增量，再决定实现/训练。
