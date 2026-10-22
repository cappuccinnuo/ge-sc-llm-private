# DDG加入后合约F1持平的运行复核（Codex）

用户质疑两个合约任务全部折的best F1持平是否意味着错图、错权重或DDG失效。本轮只进行既有产物检查和已训练模型推理；未训练新模型，未修改DDG/HGT/tokenizer/标签/划分/训练配置及历史结果。

## 复核结果

- 两个合约任务共10对、20个best checkpoint，在原CUDA设备逐个重新构造实际模型并加载对应权重。
- 20次重算概率与原GPU导出概率的最大绝对差均为0；分类也完全相同。
- 每对实际图SHA、best checkpoint SHA均不同；图路径/绑定与各自冻结manifest一致。
- 重入模型参数量4,526,962→4,715,746，新增6,252条正向DDG边、23个DDG canonical relation。
- 访问控制模型参数量4,510,546→4,723,954，新增4,153条正向DDG边、26个DDG canonical relation。
- 共同语义参数的训练后张量每折至少707项（重入）/734项（访问控制）不同，不是同一份训练权重。
- 冻结历史plan/seal/report/delivery manifest和20份best checkpoint在本次检查前后SHA不变。

## 为什么F1可以完全相同

F1取决于最终类别构成的TP/FP/FN，不直接使用概率大小。当前二分类使用argmax，正例概率跨过0.5才会改变类别（恰好平局按原argmax规则处理）。改变概率但不跨界，可以使F1完全相同；即使类别改变，在另一些情形下混淆矩阵计数相同也可能同F1。本批合约属于前一种：逐个类别确实完全相同，不只是四舍五入或平均抵消。

| 任务 | 合约数 | best概率变化数 | best类别变化数 | 平均概率绝对变化 | 最大概率绝对变化 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 142 | 142 | 0 | 1.20915个百分点 | 23.98611个百分点 |
| 访问控制合约 | 114 | 114 | 0 | 0.73557个百分点 | 3.83490个百分点 |

真实例子（正例概率）：

| 合约 | 原HCG | HCG+DDG | 两次类别 |
| --- | --- | --- | --- |
| reentrancy/spank_chain_payment.sol | 76.4798% | 87.4936% | 都为漏洞，均正确 |
| reentrancy/reentrancy_bonus.sol | 44.4136% | 40.8495% | 都为正常，均漏报 |
| access_control/mycontract.sol | 15.2843% | 19.1192% | 都为正常，均漏报 |

原预测详见raw_probability_audit.json；重载后逐文件数值见probability_examples.csv。

## DDG是否真正参与计算

沿实际worker、StageG适配器及生产HGT前向检查：
- worker按variant选择graph/initial/checkpoint绑定。
- 模型构造把新canonical relation写入DGL图并创建对应relation参数。
- sco_models/model_hgt.py:80遍历图canonical relations；第98行用relation_msg变换消息；第116行聚合；合约第606行mean和609行stack保持梯度。
- 历史正式训练记录中，有训练支持的668个增强canonical/fold记录全部观察到非零message梯度，无支持17项单列。

本轮对每个已训练增强模型做额外诊断：保留原图、schema及全部参数结构，仅在内存中将DDG关系的relation_msg切片置零，eval前向后立即恢复原state_dict。
- 10/10模型logits改变；重入每折最大绝对logit变化0.21835–1.36658，访问控制0.21268–0.59024。
- 恢复权重后10/10前向逐值恢复。
- 此诊断中两类共256个合约的类别仍不变。说明当前best决策在该扰动下未跨界，不能据此声称DDG无全局作用或训练期间完全没用。
- 消息置零保留关系及聚合分母，不能当作重新训练的无DDG基线，不能作为新的正式性能消融。没有新的拟合成绩。

## 首次CPU检查和限制

第一次CPU推理复核在重入fold0/HCG上出现概率最大误差3.477931e-5，超过预设1e-5容差，脚本停止；原脚本和run.log保留。随后使用原CUDA设备、不放宽容差核验，20个模型最大误差均0。这是CPU路径与原GPU路径的数值不一致，不是本批正式GPU导出与checkpoint不一致的证据。记录见cpu_attempt_note.json、run_gpu.log。

本轮已排除已检查范围内的错图、同checkpoint误复用、预测文件与已保存best不符，以及DDG消息完全未进入前向等解释。仍不能据此保证完整Solidity语义已实现，或认定全部新增关系的设计都有效。合约均值池化可能削弱局部改变，但本轮没有独立量化其因果贡献。

持平只针对两个合约任务的best；节点best已经有正负差异，合约last也有变化。总体结论保持：目前整体DDG没有表现出稳定分类增益，不应通过改阈值、选更高last或删困难折制造提升。

## 文件与执行

新增内容仅在scripts/DFG/experiments/artifacts/paper_kfold/overall_ddg_recheck_20261020_v1/：
recheck.py（保留首次CPU尝试）、recheck_gpu.py、run.log、run_gpu.log、cpu_attempt_note.json、raw_probability_audit.json、recheck.json、probability_examples.csv及本README。progress.json是推理复核中间记录。

复核命令（已有mando环境，CUDA；不会调用fit）：

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
conda activate mando
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
python -u -B scripts/DFG/experiments/artifacts/paper_kfold/overall_ddg_recheck_20261020_v1/recheck_gpu.py
~~~

该命令只覆盖本复核目录的诊断输出；不改正式训练产物。实施/审查AI：Codex。
