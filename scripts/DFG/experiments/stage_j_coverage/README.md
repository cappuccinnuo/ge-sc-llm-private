# Stage J真实图构建与覆盖验收

2026-10-19；Codex。入口只构图和审计，不训练。

已完成批次：`scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/`。
四任务（重入/访问控制×合约/节点），各有 frozen、inheritance、modifiers 三个独立输出，共12图。

## 实际执行命令

在mando环境及开发树运行：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -B -m scripts.DFG.experiments.stage_j_coverage.run \
  --input-manifest scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/input_manifest.json \
  --output scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build
```

这个目录已经生成；重复执行会明确拒绝覆盖。确需另行构图请指定新的输出目录，不改旧plan/seal。原图、作者标签、512维token、E2标量边和旧E3b不会写回。

输入路径来自旧manifest；读取accepted Stage F sidecar的版本证据，校验源文件/图SHA。该sidecar是本批观察绑定的证据，不能追称已被旧H2 seal认证。

每图包含 enhanced.gpickle、audit.json、manifest.json；批次包含独立plan/seal、输入和源码摘要、summary.csv、files.csv、functions.csv、receipt.json。各task的sources.json可交给通用Stage J CLI使用。

示例候选：
`stage_j_v1/build/reentrancy_author_node/modifiers/enhanced.gpickle`。
任务名后面的contract/node表示原合约级与原HCG节点级图，没有改标签或评分粒度。

## 验收命令

```bash
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests scripts/DFG/state/tests \
  scripts/DFG/state/stage_f/tests scripts/DFG/state/stage_j/tests
python -B -m pytest -q -p no:cacheprovider tests
python -B -m scripts.verify_h1_archive
python -B -m scripts.verify_h2_archive
```

本批实际：377 DDG通过、25原项目通过；H1=60、H2=30通过。没有执行GPU模型训练。

## 后处理与限制

`stage_j_v1/audit_coverage_v2.py`是本批独立只读后处理，输出opportunity_v2；按task/file/sourceSHA/原nodeID对齐历史CV validation错误。原v1因合约/节点CSV字段不同而在写表阶段失败，旧脚本与日志保留；v2统一列集合，没有改构图或统计公式。v2已运行，重复运行同样拒绝覆盖。

历史预测只是覆盖审计依据，**没有产生新预测或F1**。模型输入构建不使用漏洞标签。新增上下文统计采用真实模型方向的两层上游节点集合；共享参数训练和canonical聚合也可能影响局部范围之外，不能把局部覆盖当作性能上下界。

不要更换旧训练plan中的图文件。新正式实验需独立计划/图SHA/schema/初值绑定；原训练器和HGT本轮没有修改。详细结论见同批STAGE_J_RESULT_REPORT.md。
