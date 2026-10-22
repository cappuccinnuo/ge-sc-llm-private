# 作者 HCG＋整体 DDG＋受限控制依赖：完整结果报告

日期：2026-10-20。实施、训练、核验及报告：Codex。
工作树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`。
本批 HEAD：`021a6f55ac9e3f94fc70feb441ff48b51b6a92ea`；没有执行 pull、checkout、reset、commit 或 push。

## 1. 完成状态与主要结论

推荐的下一阶段已经实现，并完成四个任务的全部固定折：新增 `HCG_DDG_GUARD` 30 次正式拟合，验收后只读复用原 `HCG` 与 `HCG_DDG` 各 30 次结果，形成 90 个模型结果、180 组 best/last 评分。四个 fold0 是正式结果，计入 30 次，没有额外混入 smoke。所有新拟合均为 attempt_001，0 训练失败、0 重试、0 OOM。

新增控制依赖确实进入 HGT 并获得监督梯度。但是，两个节点任务相对旧 DDG 的平均 Buggy-F1 仅增加 0.0183、0.0284 个百分点；两个合约任务 best 分类完全相同。访问控制节点仍低于原 HCG。**本批证明工程接入有效，没有证明稳定的检测收益。**

全部结果为 **CV validation**：同一折 val 用于早停、选择 best 并评分；节点按 HCG 节点计分，不是按“文件＋源码行号”去重的指标，也不是独立测试结果。下表 HCG 是本地对下载作者图的训练结果，不是论文表格的原始数值。

## 2. 实际增加的内容及冻结边界

三种配置的关系是逐层追加，而不是重新构图替换旧 DDG：

1. `HCG`：下载的作者 CFG＋CG 异构图。
2. `HCG_DDG`：同一图加冻结 Stage K 整体 DDG，保留 DATA_DEF_USE、STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE。
3. `HCG_DDG_GUARD`：在第 2 项基础上，只追加正向 `CONTROL_DEPENDENCE`。这是“DDG＋控制依赖”候选，控制依赖不是新的纯 Definition–Use。

新增代码位于 `scripts/DFG/control_dependency/` 与 `scripts/DFG/experiments/guard_extension/`。控制分析采用独立语义 CFG、正常/异常/统一出口及后支配关系，输出直接控制依赖，不增加传递闭包。支持可靠绑定的 require/assert、if/else、提前 return/revert 和既有受限前置 modifier；未知语义按函数回退，该层不提交部分事实。

精确 AST/源码投影把事实落到原 HCG 节点。没有新增模型节点、变量节点或虚拟出口节点，没有最近行猜测。原 node_id、节点属性、类型、源码位置、标签、512 维 inside_token 和全部原 CFG/CG/旧 DDG 边保持不变；同端点不同关系可以共存。构图不读取预测或标签来决定连边。

新 adapter 复用原 HGT 数值实现，只注册新的正向关系；新训练入口复用原 fit 数值函数。每折从旧 HCG_DDG 保存的未训练初值扩展，共同参数按类型及 canonical relation 逐 tensor 对齐，新关系独立确定性初始化。没有使用训练后的 best/last 权重启动。

固定 paper_kfold、原文件折、fit seed、50 轮上限、patience=7、delta=0.001；best 为严格最低 val loss，last 单列。合约 initial/max LR 为 0.0005/0.01，节点为 0.0002/0.005，沿用各任务原 Adam/OneCycle。完整固定图前向，节点 mask/合约文件 batch 监督。没有改 HGT 层数、头数、隐藏维度、tokenizer 或检测任务。

## 3. 主结果：best 等权折均值

指标为百分数；差值为百分点。合约各 5 折，节点各 10 折。

| 任务 | HCG BF1 | 原整体 DDG BF1 | DDG＋控制依赖 BF1 | 新增候选−原 DDG | 新增候选−HCG | 候选 Macro-F1 |
|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | 94.1593 | 94.1593 | 94.1593 | +0.0000 | +0.0000 | 94.3452 |
| 访问控制合约 | 93.5590 | 93.5590 | 93.5590 | +0.0000 | +0.0000 | 93.8316 |
| 重入节点 | 96.0580 | 96.1027 | 96.1210 | +0.0183 | +0.0630 | 96.0643 |
| 访问控制节点 | 95.9723 | 95.8887 | 95.9171 | +0.0284 | −0.0553 | 96.8155 |

相对原整体 DDG 的逐折配对 Buggy-F1：

| 任务 | 差值均值 ± 样本标准差（pp） | 提升/持平/下降折数 |
|---|---:|---:|
| 重入合约 | 0.0000 ± 0.0000 | 0/5/0 |
| 访问控制合约 | 0.0000 ± 0.0000 | 0/5/0 |
| 重入节点 | +0.0183 ± 0.4513 | 3/2/5 |
| 访问控制节点 | +0.0284 ± 0.2871 | 3/4/3 |

这不支持稳定提升：重入节点下降折数多于提升折数，均值仍略升；不能只挑上涨的折展示。折间标准差是当前冻结划分的描述统计，不是独立 seed 重复的方差。

[RESULT_TABLES.md](RESULT_TABLES.md) 包含三变体的 best/last 均值、样本标准差、Precision、Recall、全部配对对照及 pooled OOF。逐折指标和混淆矩阵在 [fold_results.csv](fold_results.csv)，配对差值在 [paired_deltas.csv](paired_deltas.csv)。

## 4. last 与 pooled OOF 分开报告

last 等权折均值 Buggy-F1 仅作辅助，不能替换预定 best 主结果：

| 任务 | HCG last | 原 DDG last | 候选 last |
|---|---:|---:|---:|
| 重入合约 | 90.8867 | 91.0147 | 91.6169 |
| 访问控制合约 | 85.9247 | 84.6752 | 84.5429 |
| 重入节点 | 97.1504 | 96.9109 | 97.1342 |
| 访问控制节点 | 95.8010 | 94.1517 | 94.1214 |

best 的节点任务相对旧 DDG 均略升，但 last 访问控制节点略降，方向并不一致。不能因为 last 更高而改选模标准。

best pooled OOF Buggy-F1 按 HCG／原 DDG／候选依次为：重入合约 94.2857／94.2857／94.2857；访问控制合约 93.5780／93.5780／93.5780；重入节点 96.8197／96.8121／96.8538；访问控制节点 96.5014／96.4191／96.4511。它按合并样本统计，不能与等权折均值混为同一个数字；仍不是独立测试。完整混淆矩阵见 [pooled_oof.csv](pooled_oof.csv)。

## 5. 预测究竟改变了什么

相对原整体 DDG 的 best：

| 任务 | 完整评分样本数 | 类别翻转 | 纠正错误 | 新增错误 | 总错误变化 |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 142 | 0 | 0 | 0 | 8→8 |
| 访问控制合约 | 114 | 0 | 0 | 0 | 7→7 |
| 重入节点 | 12036 | 44 | 25 | 19 | 429→423 |
| 访问控制节点 | 7710 | 12 | 7 | 5 | 216→214 |

两项合约任务全部概率改变，但都没有改变 argmax 类别，因此 F1 完全一致。平均绝对正例概率变化分别为 0.004435、0.004328（概率单位），最大分别约 0.1028、0.1047。同分不等于同图、同权重或新关系没有被读取。

重入节点 44 个翻转中仅 8 个直接属于新增控制边端点；访问控制节点 12 个翻转全部不是新控制边端点。无新增控制边的文件也可能改变：共享模型参数、传播路径、优化轨迹和 best 所在轮次都属于整体干预的一部分，不能将全部纠错直接归因于某条控制边的语义。

困难文件对比采用 cohort/source SHA 身份，两个类别中的同名文件没有合并：

| 任务/文件 | 新控制边 | 原 DDG→候选 best 错误 | 说明 |
|---|---:|---:|---|
| 重入 buggy_18.sol | 74 | 252→252 | 无类别翻转 |
| 重入 buggy_36.sol | 73 | 57→59 | 新增 2 个错误，均为控制边目标 |
| 重入 simple_dao.sol | 2 | 4→4 | 无类别翻转 |
| 访问控制 buggy_18.sol | 37 | 87→87 | 无类别翻转 |
| 访问控制 buggy_26.sol | 29 | 42→42 | 无类别翻转 |
| 访问控制 parity_wallet_bug_2.sol | 0 | 3→1 | 不能解释为该文件控制边直接修复 |

重入较明显的纠错来自 spank_chain_payment.sol（9 纠错、1 退化）、buggy_20.sol（5 纠错）；buggy_24.sol 新增 5 错误。访问控制 buggy_4/6 各纠正 2 个，buggy_19 新增 2 错误。当前没有消除已有困难案例的主要问题。

完整预测位于 [oof_predictions.csv](oof_predictions.csv)。[prediction_changes.csv](prediction_changes.csv) 是稀疏变化表：仅记录概率或类别发生改变的样本，不能把其行数当评分样本数。最终 analysis_summary.json 的概率差均值已按完整身份对齐样本数计算，包含零变化样本；这是分析摘要分母修正，没有修改预测、F1、封存训练代码或 report.json。

## 6. 覆盖、梯度及原图不变量

| 任务 | 文件 | 节点不变 | 加控制边前的总边 | 新控制边 | 加后总边 | 新增两层可达对 | 新上下文目标 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 重入合约 | 142 | 18312 | 25519 | 3086 | 28605 | 1690 | 1132 |
| 访问控制合约 | 114 | 13432 | 19691 | 1929 | 21620 | 1096 | 600 |
| 重入节点 | 71 | 12036 | 16217 | 2421 | 18638 | 999 | 745 |
| 访问控制节点 | 57 | 7710 | 11743 | 1384 | 13127 | 464 | 248 |

边数指模型转换前的 HCG 图边；“加控制边前”包含原 CFG/CG 及四类 DDG，不是只统计 DDG 新边。两层可达统计采用实际 adapter 张量方向。每图新增 8 个 canonical 组合，但只新增 1 种边类型 CONTROL_DEPENDENCE。

30 折共 240 项新 canonical×fold 均有 train 支持，并有实际非零监督 message 梯度。逐轮共 5464 条新关系梯度记录，5464 条均非零，采集在 backward 后、optimizer.step 前；不是用 weight decay 或参数值变化冒充梯度证据。记录在 gradient_audit.epochs[].enhancement_relations；旧 ddg_relations 字段仅用于旧 scalar 审计。

共 8820 条投影控制边的源码 SHA、UTF-8 span 证据核验通过。图不变量检查覆盖原节点顺序/属性、全部基础边与旧 DDG；未知函数仅放弃该层新事实，不删样本或旧图。缺失投影的事实数量依次为 798/134/730/60，来自旧 HCG 没有独立 emit/revert 节点，仍保留其语义控制流。

证据：[build/manifest.json](build/manifest.json)、[source_evidence_check.json](source_evidence_check.json)、[relation_support_gradients.csv](relation_support_gradients.csv)、三个 coverage_prediction_review JSON。

## 7. 资源、完整性与测试

GPU 使用 RTX3050 Laptop 4GB，候选单模型串行运行，无自动降配、切 CPU、换 seed、删样本、删折或关闭用户程序。下表耗时是 fit 单调时钟之和，不含构图/准备/独立验收，不与历史后台负载不同的耗时作公平速度比较。

| 任务 | 候选参数量 | 较原 DDG新增参数 | fit 总秒 | 最大 allocated MiB | 最大 reserved MiB | 最低整卡空闲 MiB |
|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | 4781410 | 65664 | 976.74 | 2894.40 | 3068 | 29 |
| 访问控制合约 | 4789618 | 65664 | 692.15 | 2159.13 | 2252 | 31 |
| 重入节点 | 4625458 | 65664 | 2041.18 | 1883.61 | 2048 | 63 |
| 访问控制节点 | 4666498 | 65664 | 1249.37 | 1250.32 | 1364 | 550 |

新 fit 合计 4959.45 秒，约 82.66 分钟。显存余量低时保持原配置，未出现 OOM。逐折 best/last epoch、时间、显存见 [resources.csv](resources.csv)；文件 epoch 为零基，终端显示轮次为一基。

验证结果：

- 原 DDG/模型/项目所选回归 413 passed，0 failed/skipped，31 条既有弃用 warning。
- 新语义/投影/实验测试 73 passed，0 failed/skipped，4 条既有 DGL warning。合计 486 个所选测试通过，不声称运行了仓库所有可能测试。
- 首次新增统一测试 72 passed/1 failed（safe reader 的 Path 接口）；封存前修正调用，未放宽断言，失败日志保留。早期 grammar 与库路径失败见 IMPLEMENTATION_REPORT，未掩盖。
- final verify 与 summarize 完成；全部 30 个新 fit 的 best 对应 history 最小 val loss，last 对应末轮；loss/概率有限，类别与概率一致；60 个新 best/last checkpoint 重载预测精确一致，无评分临时建参。
- 独立从完整 OOF 的 60006 条三变体身份记录重算 180 组 best/last 指标及混淆矩阵，与 CSV 一致。报告没有把稀疏差异表当总样本。
- 旧 261 个代码/用户文件 SHA 未变；原作者图、标签、特征、旧计划/seal、旧 60 fit 未覆盖。HEAD 未变化。新计算源码、输入、初值及收据通过批次验收。

实际结果日志：[final_verify_001.log](final_verify_001.log)、[final_summary_001.log](final_summary_001.log)、[final_independent_review.json](final_independent_review.json)、[protected_after.json](protected_after.json)。

## 8. 已知范围与下一步边界

当前为显式控制/异常子集，没有完整 Solidity/EVM 隐式异常、循环/发散、跨函数终止摘要或完整 modifier；已绑定普通调用按 opaque may-return/may-revert 建模。无括号 `!msg.sender.send(amount)` 的旧 grammar 歧义保留函数回退，加括号正例通过不代表修复了原 grammar。

只读审查发现 address 转换接收者的内部调用未递归核验：`address(unresolved()).call("")` 健壮性探针可能绕过未知绑定回退。这是下一版应修的正确性问题。当前固定四任务精确扫描仅命中访问控制合约同一文件的 handleAllocation/handleWithdrawal；两函数本批已整体回退，semantic/projected/published 新事实均为 0，所有已支持函数没有命中，故当前新图不受该缺陷污染。不能据此宣布通用解析正确，也不改本批 seal 追补代码。证据：[readonly_receiver_review.json](readonly_receiver_review.json)。

旧 modifier_context 的 control_dependence_edges=False 是旧阶段字段，不能据此否定新关系；本批模型使用新事实/新 relation。字段歧义保留记录。未执行新的 solc 编译或 EVM 验证；Tree-sitter 解析通过不等于 Solidity 编译验证。

依用户决定，作者标签及已知争议保持冻结，不重新审核或修订正式真值。本批结论只适用于该固定基准。新关系也改变参数量、消息聚合及优化轨迹，不能将全部分差写成纯控制依赖语义的因果收益。

建议把当前版本收束为可交付的 DDG＋受限控制依赖整体实现，同时如实报告本批收益很小。若继续研究，应先修上述接收者绑定边界，再利用已有预测选择少量具备语义证据的正反案例；目前没有依据通过继续堆关系或反复调参保证提升。独立评估、更广类别与多 seed 是后续研究事项，本轮没有自动启动。不要把已有作者标签争议、少数折 99 分或当前微小均值变化当作普遍有效性的证据。

## 9. 文件入口与复核命令

- 实现说明：[IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md)。
- 实际入口/测试/失败恢复说明：[guard_extension/README.md](../../../guard_extension/README.md)。
- 新计划与 seal：[plan.json](plan.json)、[plan.seal.json](plan.seal.json)。plan 文件 SHA256：b621cbc44e5651a421c6417924792cf64f048d464d1b138ebeac1002d6648dd6。
- 数值附表：[RESULT_TABLES.md](RESULT_TABLES.md)；机器报告：[report.json](report.json)。
- 文档追加：两树 docs/training_changes_2026-10-07.md 第 32.8 起及 HANDOVER.md 最新 Codex 记录。旧正文保留。

以下仅验收与重算报告，不重新训练：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
conda activate mando
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.DFG.experiments.guard_extension.control verify
python -B -m scripts.DFG.experiments.guard_extension.control summarize
```

本批已完成并停止，没有启动更多 seed、其余五类、独立测试、新关系或额外正式拟合。
