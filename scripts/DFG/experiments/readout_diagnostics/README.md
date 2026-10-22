# 已有实验的标签上下文与合约读出诊断

实施：Codex，2026-10-20（美国东部时间）。本模块只读取已有结果和 best checkpoint，不训练、不改图/标签/tokenizer/HGT，不提供新的 pooling 训练参数。

## 三个入口

- `label_context.py`：按 cohort、文件、源码 SHA、原节点 ID 对齐既有逐节点预测，保留作者 target；分为 REFERENCE_AGREED、DISPUTED、UNREVIEWED。只有已定点审查的五个文件有前两类，未审计节点不能视为标签正确。
- `contract_readout.py`：核验旧批次归档、当前候选计划、输入和 checkpoint，逐个加载两任务各五折的三种配置，共 30 个 best。执行原完整图前向，通过 hook 捕获最终 HGT 表示及真实分类头输入，核对原预测。
- `summarize.py`：先核验每个诊断表的 receipt/hash 和合并表身份，再汇总全部 TP/TN/FP/FN、三配置文件级变化、错误合约的局部贡献。不会搜索新阈值或给未训练的新汇聚计算正式成绩。

## 贡献的含义

原合约读出是 mean(H) 后接二分类线性层。令 d=w1−w0，b=b1−b0，参考 margin 为 `mean(d·h_i)+b`。每个节点的参考贡献为 `(d·h_i)/N`，偏置单独保留。

这是当前合约分类器在上下文化隐藏表示上的内部证据，不是节点漏洞概率，不等于真实漏洞因果贡献。节点目标仅在前向完成后用于描述性分组，不参与构图、隐藏表示、贡献计算或新模型训练。

捕获的 float32 隐向量转成 float64 后，线性参考恒等式以 1e-10 核验；GPU 实际数值另有 pooling/head 残差，不能强行分配给节点。原设备、dtype、batch、权重和精度设置下的 `F.linear` 重放必须与实际 logits 逐位一致。原预测类别必须一致，历史概率绝对误差仍须小于 1e-5。记录每文件参考/实际类别一致性；类别不一致时不以参考贡献解释实际方向。

首次诊断 attempt_001 因将高精度参考与 GPU 实际 margin 直接混检而失败，保留 failure、运行源码快照和 float32_probe.json；attempt_002 独立输出。实际 logits 约 ±1，证据不支持“大公共 logit 抵消”。记录 TF32 允许标志，但没有精度切换对照，不将 TF32 单独认定为已证明原因。

## 实际命令

在 WSL 的 mando 环境与开发工作树运行：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
python -B -m unittest discover -s scripts/DFG/experiments/readout_diagnostics/tests -v
```

已经生成的结果在 `scripts/DFG/experiments/artifacts/readout_diagnostics_v1/`。以下是本轮执行命令的记录，产物存在后不能原地再次运行；要复核请使用新的独立输出目录：

```bash
python -B -m scripts.DFG.experiments.readout_diagnostics.label_context \
  --output scripts/DFG/experiments/artifacts/readout_diagnostics_v1/label_context
python -u -B -m scripts.DFG.experiments.readout_diagnostics.contract_readout \
  --output scripts/DFG/experiments/artifacts/readout_diagnostics_v1/contract_best/attempt_002
python -B -m scripts.DFG.experiments.readout_diagnostics.summarize \
  --source scripts/DFG/experiments/artifacts/readout_diagnostics_v1/contract_best/attempt_002 \
  --label-context scripts/DFG/experiments/artifacts/readout_diagnostics_v1/label_context \
  --output scripts/DFG/experiments/artifacts/readout_diagnostics_v1/analysis
```

合约诊断要求已有 CUDA，串行一个模型；不自动换 CPU。所有指标仍为 CV validation，节点单位仍为 HCG 节点。旧标签与公开端点投影一致，不代表已经认证语义真值。文档详见本批 DIAGNOSTIC_REPORT.md 与 NEXT_STAGE_DESIGN.md。