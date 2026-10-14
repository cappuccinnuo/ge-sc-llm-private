# Stage E 交付入口

修改 AI：Codex。2026-10-14。

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。状态核心在 scripts/DFG/state/；原 ge-sc-llm 冻结训练代码未升级。

阅读顺序：
1. [实现与验收报告](IMPLEMENTATION_REPORT.md)
2. [Oracle审核](ORACLE_REVIEW.md) / [预期及独立审核状态](ORACLE_EXPECTATIONS.json)
3. [状态位置与接口](STATE_LOCATION_SPEC.md)
4. [别名/HAVOC审计](STATE_ALIAS_AND_HAVOC_AUDIT.md)
5. [两类后续计划](TWO_PILOT_EXPERIMENT_PLAN.md)
6. [最终测试](REGRESSION_RESULTS.json) / [独立结果重算](INDEPENDENT_RESULT_CHECK.json)

最终数据使用 results_attempt_002/，attempt_001 保留。重点文件：
- SUMMARY.json、INPUT_MANIFEST.json、GRAPH_MANIFEST.json
- STATE_ACCESS_AUDIT.csv、STATE_REACHING_DEF_RESULTS.json、CORPUS_STATE_RESULTS.json
- STATE_PROJECTION_AUDIT.csv、E2_E3_INFORMATION_INCREMENT.csv
- 四个 *_E3a_selected_*.gpickle（本轮与E2字节相同，真实新增状态边0）

## 运行测试

在 WSL Ubuntu 已有 mando 环境：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/tests

python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/state/tests scripts/DFG/tests scripts/DFG/experiments/tests tests \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'
```

原绝对资源测试在原目录运行（不修改路径断言）：

```bash
cd /home/zhao/SmartContract/ge-sc-llm
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs
```

## 重跑源码审计，不训练

以下示例新输出目录必须不存在；脚本拒绝覆盖：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
python -B scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/run_stage_e.py \
  --output scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/results_manual_001
```

审计只在重入3个与访问控制4个预选文件中分析函数；保留完整E2任务图其他文件。不能作为全语料增强完成版。旧训练入口尚未接入正向状态关系适配；本轮不提供或执行E3正式训练命令。

没有改标签、token、划分、HGT、旧训练器或DDG v1/v1.1核心。所有模型收益判断待后续合格实验；本轮不报告新F1。
