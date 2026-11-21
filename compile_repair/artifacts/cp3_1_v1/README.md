# CP3.1 复核入口

2026-11-21，修改 AI：Codex。基线为 `compile-repair@61c94e00`，对应 PROMPTS r2.14 §4.5b。生产代码五处文件有改动，生产模块共 16 个。代码、统计和文档随本地提交交付，原始运行资料在仓库外的 `compile-repair-local/cp3_1_v1/`。

| 要复核的结论 | 本目录证据 |
|---|---|
| D21、矩阵语法拒绝、缺少 AST 的统计口径 | d21_request / authorization、pragma_syntax_request / pragma_authorization、ast_coverage_request / ast_coverage_authorization |
| CP3 原始 31,071 条结果及其两种分类 | baseline_survey.py、baseline_classification.json |
| 31,307 个输入中的包装形态与原类别 | wrapper_scan.json；wrapper_premises.json 另有三个解包探针 |
| AST 统计及无法判定的单元 | ast_census.json；按 hash 绑定仓库外的 ast_invocations.jsonl |
| 92 版本 × 82 表达式 | matrix_invocations.jsonl.gz、pragma_oracle.json、pragma_matrix_check.json |
| 旧表达式及 846 个输入的双向计划等价 | pragma_equivalence.json |
| 510 条新结果的逐项替换 | replacement_provenance.json，包括旧新结果路径及 SHA |
| 逐项主因、任一候选类别、选用哪个结果 | unit_attributions.jsonl.gz，每行一个有效单元 |
| 两张分类表、版本组合与后续顺序 | failure_summary.json、taxonomy.json、d6_cp4_final.json |
| MANDO 最终独立回归、测试与保护 | mando_regression_final.json、production_tests_final.json、mando_tests_final.json、dfg_tests.json、scope_audit.json |
| 文档及交付文件哈希 | doc_check.json、acceptance.json、delivery_inventory.json |

主因按输入格式或计划或项目组装、成功编译版本的 Slither 失败、所有候选持续出现的类别依次判定。最后一种交集为空时保留每个版本的类别，归入统计桶 `version_dependent`。两表的分母都是 9,848 个剩余失败单元，每类按单元计一次，可多标签。

AST 统计覆盖 24,549 个项目编译单元，18,389 个可判定，其中 12 个确认重名。6,160 个还缺足够的 AST，原状态均为未修复。正式替换只涉及确认重名的 12 个、之前无法求值的 88 个及 410 个包装输入。包装内源码的解包样本仅作 CP5 前提验证。

首轮矩阵脚本将 4 个历史对照计入版本数，在调用编译器前停下。按支持区间核对后，矩阵在第 3,681 次调用遇到实际的语法拒绝。用户明确批准单列，续段只覆盖剩余 3,863 个组合。两个阶段的原始合约均为手写空合约，调用日志可在此目录核对。MANDO 驱动初次错将仓库外已展开的 seal 当作 Git 对象，正式运行前改按历史 README 登记的 SHA 校验。初次两环境测试定位到一条旧测试仍要求拒绝 `0.5`，现同时检查冻结旧结果与获准的新结果。最终生产代码还可读取 Slither 构造失败后 CryticCompile 保留的定义证据。更新后用新目录重新执行 MANDO 审计和两环境测试，原记录保留。范围检查在 mando 中读取 DFG 引用，在 Python 3.10 中归属变更行，相关记录含第一次环境导入失败的原因。

每个正式实验目录独占创建。复核可直接读收据及 SHA。本批次费用为 0 美元，未进行外部语料下载、软件安装或模型调用。
