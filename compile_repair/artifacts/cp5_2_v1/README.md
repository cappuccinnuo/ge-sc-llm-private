# CP5.2 验收证据

本批次对应 PROMPTS r2.24 §4.6i，基线为 `compile-repair` 的 `fba94f1d6a0c556202bfa7dd48672eaba8f55973`。修改 AI 为 Codex。完整编译工作副本、生成的 Solidity 输入和原始工具日志保存在仓库外的 `/home/zhao/SmartContract/compile-repair-local/cp5_2_v1/`。最终验收及其状态见同模块的 `CP5_REPORT.md`。

## 第 4 步诊断

用 `diagnosis.jsonl` 查看 211 项旧移动失败与 102 项真实失败的每轮候选、筛选、收据哈希及新增错误。`diagnosis_details.jsonl` 把明确指向项目根之外的相对导入单独识别出来，保留工程上允许继续改写的严格子集。`filter_breakdown.json` 按单元与导入两种分母计数，区分大小写匹配、符号、pragma 与同优先级候选。不同导入可以在同一单元遇到不同筛选结果。

## 文件与图的评分

`wrapper_graph_pairs.jsonl` 按单元保存 550 对图的身份、哈希和各类图事实的原始差异。`wrapper_representation_review.json` 记录唯一涉及创建字节码的样本及其元数据边界。`benchmark_scores.jsonl` 同时保存旧分与新分，覆盖 950 个包装、400 个旧移动和 114 个缺包样本。这里使用 CP5.1 原有的修复输出。新工具链的修复结果在续作批次中独立测量。

## 工具、环境和续作

`production_tests.log` 和 `production_suite_stop.json` 保存首轮源码封存测试的失败。`frozen_suites/` 保存 18 个模块的 SHA256、每套回归的运行命令、输出与前后源文件核对。`code_audit.json` 核对模块分层边界内的代码变化及 DFG 的 354 个引用。`mando/` 逐项保存 846 个输入的结果，包括 843 份与 v5 相同的图及各自的部分 IR 标记。

开发集测量首次停在项目路径比较，详见 `measurement_stop.json`。历史工作副本的导入清单保留来源路径。`ir_manifest_preflight.jsonl` 对 3,371 个单元逐项核对，`ir_argument_differences.jsonl` 列明 711 个 CP3 项目的原参数和当前参数。`continuation/authorization.json` 登记用户原话及清单哈希。该批次的 `*_start.json`、`*_exit.json` 和逐项记录保存实际执行边界。带有相同单元编号的不同测量范围各有自己的分母。

`baseline.json` 记录起始文档边界和输入哈希。工作副本由 production profile 使用原有的 92 个受支持 solc 处理，依赖选择沿用 oldest 与 K=21。mando 环境承担兼容性与 DFG 测试。本批 CPU 评估的费用为 0 美元，LLM 调用为 0。

## 最终结果入口

`acceptance.json` 汇集四个测量范围、真实语料分母、逐算子回归和 v2 全图指标。`record_archives.json` 登记原始逐项表及其 gzip 文件的 SHA256 和行数，Git 中的可移植副本在 `packed/`。在新的检出中，可按清单将 gzip 副本解压到原相对路径并核验原始 SHA256。完整手写夹具、编译器输出、图及工具日志保存在本机。文档核验见 `final_doc_check.json`。
