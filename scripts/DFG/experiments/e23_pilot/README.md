# Stage G：E2/E3a/E3b 固定 fold 0 试验

修改 AI：Codex；日期：2026-10-14。

本入口位于开发工作树 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11`。
仅运行重入、访问控制的合约/节点四任务，每任务三个模型，共 12 次正式拟合。
原图、标签、tokenizer、DDG 算法、HGT、原训练脚本和旧归档不修改。

| 配置 | 固定输入 |
|---|---|
| E2 | 作者 HCG/标签 + 已核验 512 维 tokenizer IDs + v1.1 修复后的标量 DATA_DEF_USE |
| E3a | E2 + Stage F 已生成的 STATE_DEF_USE |
| E3b | E3a + STATE_ACCESS_ORDER + EXTERNAL_CALL_BEFORE_STATE_WRITE |

顺序关系不是 Def–Use，也不是漏洞证明。关系方向使用 Stage F 显式适配器；
继承原分类器 forward 和 HGT 核心。新增模型不会把状态关系反射成反向边。
三者共同参数按节点类型和 canonical relation 对齐；
全部未训练初值在 CPU 封存，E2→E3a→E3b 顺序复制共同参数。
这不是从训练完成的 E2 暖启动 E3。

## 运行方式

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
```

默认输出：
`scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/`。

`prepare` 和 `seal` 只在新批次首次调用；已经存在的初始化和计划拒绝覆盖。
封存前需全部新测试及原回归通过，且 `integration_tests.json` 记录成功。

```bash
python -B -m scripts.DFG.experiments.e23_pilot.control prepare
python -B -m scripts.DFG.experiments.e23_pilot.control seal
python -B -m scripts.DFG.experiments.e23_pilot.control smoke
python -B -m scripts.DFG.experiments.e23_pilot.control run
python -B -m scripts.DFG.experiments.e23_pilot.control verify
python -B -m scripts.DFG.experiments.e23_pilot.control summarize
```

在本轮已经完成的输出上，通常只需 `verify` / `summarize`。
不要重新 prepare、seal 或改旧 plan；不要并行启动两个控制器。
运行版本 HEAD 或代码变化时校验拒绝，不能为了重跑而改写 seal。

## 保持的计算规则

- paper_kfold / ddg-paper-kfold-v1；仅冻结 fold 0，seed 1。
- 完整固定任务图前向，节点 mask 或合约文件监督；train 更新参数。
- 同一 CV val 用于最低 loss 选择 best、早停和评分；结果称 **CV validation**。
- 最大 50 epoch，patience 7、delta 0.001；严格最小 loss 存 best。
- 三轮 smoke 保持 50 步 OneCycleLR，正式拟合重新加载同一未训练初值。
- 合约 initial LR 0.0005 / max LR 0.01；节点 0.0002 / 0.005。
- best/last 分开导出。节点指标按 HCG 节点计算，不冒称去重源码行 F1。
- 所有库版本由 worker 实测并与冻结配置对比；每模型 GPU 峰值单独重置。
- 验证独有关系可以有零训练梯度；记录支持量，不临时创建或借用参数。

## 恢复、产物与限制

一个 worker 仅加载一个 GPU 模型。OOM 或其他错误立即停止，禁止自动改超参、
删图、切 CPU 或无限重试。成功 attempt 完整校验后复用；失败保留日志、
异常、部分权重，诊断后才显式用 `--retry TASK_ID/VARIANT` 重跑该模型。
不是 epoch 断点恢复。smoke 和正式输出位于不同目录。

每次拟合有 best.pt / last.pt、有效配置、模型输入、支持与梯度审计、
绑定、逐轮历史、验证预测、资源记录及收据。汇总器独立按冻结标签重算指标，
分别输出 summary.csv、last_summary.csv、paired_deltas.csv、error_changes.csv。

`review/` 保存有限静态审查：20 Oracle、17 条合约图 STATE_DEF_USE、
各 8 条分层抽样顺序边。独立人工批准和 solc 编译验证均未完成；
这是明确披露的限制，不将 Tree-sitter 解析通过当成 Solidity 编译验证。
单折内部探索不能证明泛化收益或七类漏洞均有效；未授权其余 78 次训练。

## 本批完成状态

12次正式fold0已完成并验收。结果、限制与剩余78次的计划边界见[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)。当前run不会启动其他折。
