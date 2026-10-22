# 固定图上的合约注意力读出对照

本轮实施：Codex。入口为独立旁路，不修改原 DDG、HGT 核心、tokenizer、标签或原训练脚本。

## 实验含义

两个任务：重入与访问控制的合约级检测，各原固定5折。节点分类模型不使用合约pooling，本轮不重复节点训练。

| 图 | mean | attention |
| --- | --- | --- |
| 作者 HCG | overall_cv_v1 的10个合约结果 | 本批新增10次 |
| 作者 HCG + DDG + CONTROL_DEPENDENCE | guard_extension_v1 的10个合约结果 | 本批新增10次 |

注意：本批 `runs/.../HCG/` 和 `HCG_DDG_GUARD/` 中都是新的 attention 模型；名称表示图类型，读出由独立 plan/checkpoint binding 指明。旧 mean 目录不覆盖、不改 seal。

## 唯一模型改动

原 HGT 完整图前向后，对每文件节点使用 `alpha=softmax(h @ a)`，合约向量为 `sum(alpha*h)`，再用原二分类线性层。a是128维零向量，新增128参数，无score bias、MLP、top-k、节点标签规则或额外关系。初始数学上等价mean；有限精度reduce误差单独核验，禁止用零向量分支绕开attention梯度。

新向量与全部旧权重参与训练。旧权重从各graph/fold保存的 `optimizer_steps=0` 初值逐张量精确复制，不能从best/last继续训练。按原 fit_seed 在fit前恢复随机状态。原Adam、OneCycle、每轮一步、最大50轮、patience7/delta0.001、严格最低validation loss选best与同val评分均保持。全部结果称CV validation。

原训练函数代码对象复用，新增handlers仅负责模型、checkpoint binding、观察性梯度和结果审计。HGT与a梯度分别检查；合法零梯度允许，更新量不把a冒充HGT。

## 验收与恢复

- 原20个mean结果、输入图/标签/特征/折/源码身份和初值归档SHA只读核验。
- 新计划引用旧源plan、初值、manifest和成功收据；增加readout版本、方向/schema、有效配置、独立checkpoint格式。
- 四个真实fold0零步预检：每次GPU只加载一个模型，原HGT结果一致、初始pool近似一致、梯度连接、初值不变和显存可用。
- 四个正式fold0通过后再跑余16次；这些fold0计入20次，不重复挑选分数。
- 同一GPU锁用于预检和正式调度；成功折核验后复用。失败保留全部attempt，停止，无自动降维/删图/CPU回退/无限重试。
- `--retry task/fold_n/variant` 仅用于已排查后的显式整次fit重试，不是epoch续训或新seed。

## 实际命令

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1
python -B -m unittest discover -s scripts/DFG/experiments/readout_attention/tests -v
python -B -m scripts.DFG.experiments.readout_attention.control prepare
python -B -m scripts.DFG.experiments.readout_attention.control preflight
python -u -B -m scripts.DFG.experiments.readout_attention.control run --fold0
python -B -m scripts.DFG.experiments.readout_attention.control verify --fold0
python -u -B -m scripts.DFG.experiments.readout_attention.control run
python -B -m scripts.DFG.experiments.readout_attention.control verify
python -B -m scripts.DFG.experiments.readout_attention.control summarize
```

默认产物目录：`scripts/DFG/experiments/artifacts/paper_kfold/readout_attention_v1/`。prepare/preflight不能覆盖旧输出；可用真实支持的`--output`另指定新批次目录。已有成功结果可通过run核验复用，不会再次训练。

实时日志示例（这是本批的HCG+attention）：

```bash
tail -F scripts/DFG/experiments/artifacts/paper_kfold/readout_attention_v1/runs/reentrancy_author_contract/fold_0/HCG/attempt_001.log
```

## 结果解释

按任务分开报告完整五折，best/last分开，包含指标、误差、OOF、概率、关系/读出梯度、参数/时间/显存。关键交互是 `(增强attention−HCG attention)−(增强mean−HCG mean)`。两图同时提高只能支持读出改进；新增参数和优化变化不能当成纯DDG语义因果收益。不会自动扩展更多seed、七类、新关系或独立测试。
## 本批已完成

20次新attention训练及20历史mean引用已验收；完整结果见`../artifacts/paper_kfold/readout_attention_v1/RESULT_REPORT.md`和`RESULT_TABLES.md`。主best重入HCG attention比mean低0.6437pp、增强图持平；访问控制分别低0.7971/3.0026pp。保留mean主方案，该候选不作为稳定提升结论。完整逐折、best/last、错误变化、OOF、资源和独立验收均已保存。

已有批次可以直接`control verify`或`control summarize`；不需要再次prepare或重训。20新fit全部attempt_001，0失败/重试/OOM。详细变更记录见两树training_changes第34节，执行AI为Codex。