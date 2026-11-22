# CP4.1 实测与迁移评分检查点

2026-11-22，修改 AI 为 Codex。输入提交为 `e8ec530d81908b5f9cd592d3f1ecae89aa3e63a6`，规范为 PROMPTS r2.17 §4.6b。完整报告见 [CP4_REPORT.md](../../CP4_REPORT.md)。本目录保留首次运行、停止现场、用户授权及后续独立批次的收据。

| 核查对象 | 可复核的结果 |
|---|---|
| 诊断模板与分类 | `old_other_templates.json`、`standard_json_observations.jsonl.gz`、`diagnostic_mapping.json` 将原始模板、证据强度及剩余原因逐一对应。 |
| 结构体数组边界 | `struct_support.json` 含 92 次生产字节码调用。`struct_codegen_crosscheck.json` 含同一 0.8.38 二进制及审查夹具的 ABI 和生产输出。 |
| CP3 归因与 D6 | `cp3_before_after.json` 含完整主因、任一候选和旧 other 模板对照。`d6_routes.json` 是使用原有 D6 词表的分类路线，频率排序取自 `d6_priority.json`。 |
| CP4 样本 | `original_reclassified.jsonl.gz` 逐项保留原种子、编辑和两阶段观测收据。`new_plan.jsonl.gz` 为首批，`package_union_plan.jsonl.gz`、`supplement_plan.jsonl.gz` 为用户批准的真实包完整抽样及其追加部分。 |
| 数量与分层 | [operators.tsv](operators.tsv)、[strata.tsv](strata.tsv) 和 `population.json` 可核对 22 个算子的旧纳入、重判变化、新增、语料、版本系列与划分。样本身份含批次、算子、单元及编辑收据。 |
| 创建码评分 | `creation_archived_and_fresh.json` 与 `creation_manual.json` 含原分和规范化分数。`new_sampling.json` 的 embedded_bytecode 区分 creationCode、runtimeCode 和已校验尾部。 |
| 精确还原 | `retained_scores.jsonl.gz`、`promoted_scores.jsonl.gz` 逐样本记录完整图比对和发生过的元数据规范化。`new_scores.jsonl.gz` 与 `supplement_scores.jsonl.gz` 保留到各自首次差异为止。 |
| 两处评分差异 | `new_restoration_stop.json`、`supplement_restoration_stop.json` 为原始评分。相应的 `*_migration_difference.json` 独立比较已保存图。`migration_stop_inventory.json` 及其压缩清单还记录停止时已完成的并行任务。 |
| 环境与代码 | `baseline.json`、`migration_stop_scope.json`、`final_tests/` 与 `runtime_recovery.json` 记录工具、每个变更函数的增删行、三套测试和 WSL 新命令启动实测。 |

## 复核顺序

在工作树根使用 production 的 Python 3.10，生产 Slither 0.11.6、crytic-compile 0.4.2。mando 的 Python 3.7 运行兼容与 DFG 回归。启动命令形如 `$CP41_PY -B compile_repair/artifacts/cp4_1_v1/<脚本>.py`。运行脚本以独占创建方式写入输出，重复研究使用新的 `CP41_OUTPUT` 与 `CP41_SCRATCH` 目录。大体积原始收据及第三方仓库保存在工作树之外。

1. 先核对 `baseline.json` 中的编译器身份和 CP4 封存输入。诊断的顺序为 `inventory_diagnostics.py`、`oracle.py`、`map_diagnostics.py`、`reaggregate_cp3.py`。95 份手写源码位于测试夹具目录，通用内部异常使用历史诊断。
2. 用 `probe_compilers.py`、`struct_codegen_crosscheck.py` 和 `creation_validation.py` 核对编译输出差异与创建码比较。原收据重判使用 `replay.py`。新候选用 `new_plan.py`、`new_samples.py`，真实包的追加抽样、触发及还原由 `package_supplement.py` 执行。
3. `restore_scores.py retained` 使用已成功的原还原图逐项重算分数。`promoted` 和 `new` 对新增纳入项实际编译已恢复的字节。缺包项目另以包路径及 remapping 运行 Slither。每条编译与图收据都保留路径和 SHA256。
4. `population.py` 独立复核去重、原划分、全部触发数和原 200 项对照。`inspect_migration.py` 和 `index_migration_stop.py` 只读已保存收据。两处编号差异的审批依据为 `migration_counter_review.json`。
5. 两套模块测试使用 `python -B -m pytest -x -q -p no:cacheprovider compile_repair/tests`。DFG 使用 mando 从仓库根执行 `python -B -m pytest -x -q -p no:cacheprovider scripts/DFG/dfg_v2/tests`。各轮的临时目录分开保存。
