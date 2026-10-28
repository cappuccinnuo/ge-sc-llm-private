# Prompt 8B：完成阶段 B 与五剖面完整实验报告

日期：2026-10-28（America/New_York）；实施与记录 AI：Codex。
工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11；分支 dfg-v2；本轮运行起点 220d258f284dacd52374ba95c7284f461005a23e。

## 1. 完成范围与总体判断

阶段 B 的 G1R/G2R/G3 共 **90/90** 项正式训练完成；原阶段 A 的 G0/G3R **60/60** 项只读复用，完整矩阵 **150/150** 已验收。每项都是 attempt_001，0 失败、0 重试。G* 已按封存的 inner_val 规则选定，完整报告与 CSV 已生成。

本轮没有修改 DDG、HGT、tokenizer、图、标签、折划分、初始化、优化器或早停；没有因分数下降删除折或换用 last。实际工作是调用已有编排、校验、选型和报告入口，新增阶段授权、产物、审计与文档。

**结果具有任务差异：重入节点出现小幅而较一致的改善；合约级均值虽有提高，但收益集中在少数折；访问控制节点的四种增强剖面 best 均值均低于 G0。不能据此宣称完整 DFG 在所有任务上都有效，也不能因某个任务下降就认定数据依赖普遍无效。**

## 2. 协议与剖面身份

继续使用原150项plan（SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de）及原seal；Prompt8B.0 amendment SHA为 d2c255fb50636f91066cd2a7503715619f5bdb422af3c884727557d261631c8f，新建本轮90项授权 SHA为 5437695492ebacfde65f111275cb4d5ad0e60e7a86c3f609fb8f7fbbd8558f41。未修改旧授权、旧plan/seal或旧A产物来通过验收。

沿用 dfg-v2-nested-v1、seed 1，合约外层 5 折、节点外层 10 折。inner_train 更新参数；inner_val 早停、按严格最低 loss 选 best，并用于 G* 选择；outer_test 在训练后评分。预注册主对比仍是 **G3R − G0 的 best 外层 Buggy-F1**；G2R被选为G*并不替换这一主终点。其他剖面对G0和方向比较按冻结消融矩阵报告；last 单独作为辅助结果。

完整固定任务图参与前向，因此这里将外层文件标签留出，但完整固定图仍参与前向，不能称为完全归纳的新图/外部数据测试；也不同于旧 paper_kfold 的 CV validation。节点指标按原 HCG 节点计算，env_source 不计入监督和评分，并非源码行去重 F1。

| 剖面 | 本批含义 |
| --- | --- |
| G0 | 原作者固定 HCG（CFG+CG），没有 v2 新关系 |
| G1R | G0 + L1 标量 DATA_DEF_USE 及显式 REV_DATA_DEF_USE |
| G2R | G1R + L2 WRITES_STATE / READS_STATE 及显式反向关系；利用原图声明节点中转 |
| G3R | G2R + L3 ENV_FLOW/env_source 及显式反向关系 |
| G3 | 完整 L1/L2/L3 的正向版本，用于与 G3R 做方向消融 |

原 HCG 节点属性、标签、特征、基础边均保留；只有 G3/G3R 增加获准的 env_source 节点。本轮并未重新构图。

保持 shared_projection/mean、512 维 inside_token、hidden128、2层、8头；Adam、OneCycle 每轮一步，最多50轮、patience7、delta0.001。合约 lr=0.0005/max_lr=0.01/weight_decay=5e-6；节点 lr=0.0002/max_lr=0.005/weight_decay=0。共有 G0 参数按语义对齐；新增关系仍采用已批准的各剖面 Xavier 范围规则，不能声称所有新增关系跨剖面初值数值都相同。

## 3. best 主结果

下表为 Buggy-F1（百分数）的等权折均值 ± 样本标准差；差值单位为百分点。折间标准差不是多 seed 重复实验的方差。

| 任务 | G0 | G1R | G2R | G3R | G3 |
| --- | --- | --- | --- | --- | --- |
| 重入合约级 | 92.7326 ± 5.4566 | 94.8490 ± 6.3676 | 94.8490 ± 6.3676 | 94.1612 ± 6.3579 | 94.8490 ± 6.3676 |
| 访问控制合约级 | 94.6066 ± 1.6532 | 95.4037 ± 0.2268 | 95.4075 ± 3.2189 | 95.4075 ± 3.2189 | 95.4733 ± 0.3447 |
| 重入节点级 | 96.4276 ± 6.5918 | 96.4492 ± 6.6020 | 96.9420 ± 6.6318 | 96.9344 ± 6.6127 | 96.8842 ± 6.6348 |
| 访问控制节点级 | 96.1753 ± 6.2062 | 96.0510 ± 6.0462 | 95.6227 ± 5.9501 | 95.9716 ± 6.1255 | 95.9405 ± 6.0831 |

Macro-F1、Precision、Recall 的完整均值/标准差见 [best_fold_means.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/best_fold_means.csv)；逐折四项指标、TP/FP/TN/FN 见 [fold_metrics.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/fold_metrics.csv)。

### 3.1 各增强剖面相对 G0 的 best 配对比较

| 任务 | 剖面 | Δ均值 ± SD | 95% bootstrap 区间 | 提升/持平/下降 | A12 | 原始p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 重入合约级 | G1R | 2.1164 ± 3.1801 | [0.0000, 4.9735] | 2/3/0 | 0.6800 | — | — |
| 重入合约级 | G2R | 2.1164 ± 3.1801 | [0.0000, 4.9735] | 2/3/0 | 0.6800 | — | — |
| 重入合约级 | G3R | 1.4286 ± 3.1944 | [0.0000, 4.2857] | 1/4/0 | 0.6000 | — | — |
| 重入合约级 | G3 | 2.1164 ± 3.1801 | [0.0000, 4.9735] | 2/3/0 | 0.6800 | — | — |
| 访问控制合约级 | G1R | 0.7971 ± 1.7824 | [0.0000, 2.3913] | 1/4/0 | 0.6600 | — | — |
| 访问控制合约级 | G2R | 0.8009 ± 4.6092 | [-2.5974, 5.0000] | 1/3/1 | 0.5800 | — | — |
| 访问控制合约级 | G3R | 0.8009 ± 4.6092 | [-2.5974, 5.0000] | 1/3/1 | 0.5800 | — | — |
| 访问控制合约级 | G3 | 0.8667 ± 1.9379 | [0.0000, 2.6000] | 1/4/0 | 0.6800 | — | — |
| 重入节点级 | G1R | 0.0216 ± 0.4066 | [-0.2225, 0.2565] | 5/0/5 | 0.5000 | 0.9219 | 0.9219 |
| 重入节点级 | G2R | 0.5145 ± 0.4178 | [0.2928, 0.7829] | 10/0/0 | 0.6500 | 0.0020 | 0.0078 |
| 重入节点级 | G3R | 0.5068 ± 0.5033 | [0.2515, 0.8416] | 10/0/0 | 0.6400 | 0.0020 | 0.0078 |
| 重入节点级 | G3 | 0.4566 ± 0.4513 | [0.2006, 0.7353] | 10/0/0 | 0.6400 | 0.0020 | 0.0078 |
| 访问控制节点级 | G1R | -0.1243 ± 0.4299 | [-0.4126, 0.0914] | 2/4/4 | 0.4700 | 0.5048 | 1.0000 |
| 访问控制节点级 | G2R | -0.5526 ± 1.1050 | [-1.2703, -0.0159] | 2/1/7 | 0.3550 | 0.1029 | 0.4117 |
| 访问控制节点级 | G3R | -0.2037 ± 0.7030 | [-0.6734, 0.0950] | 2/5/3 | 0.4650 | 0.6056 | 1.0000 |
| 访问控制节点级 | G3 | -0.2348 ± 0.5577 | [-0.6106, 0.0459] | 3/2/5 | 0.4600 | 0.1849 | 0.5546 |

合约5折仅描述，不给推断p值。节点使用双侧 Wilcoxon、zero_method=zsplit；Holm 家族严格对应同一个 task/checkpoint/metric 下 G1R/G2R/G3R/G3 对 G0 的四项比较，不是把所有任务和所有指标合成一个总家族，也不据此宣称整体所有指标显著。配对折 bootstrap 10000次、seed0。交叉验证训练集相互重叠，区间和检验按预登记口径描述，不能当作独立试验的大样本证明。完整 Macro-F1/P/R 配对结果见 [paired.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/paired.csv) 和 [holm.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/holm.csv)。

### 3.2 方向消融：G3R − G3

| 任务 | best ΔBF1 | 差值SD | 提升/持平/下降 | 原始p |
| --- | --- | --- | --- | --- |
| 重入合约级 | -0.6878 | 1.5380 | 0/4/1 | — |
| 访问控制合约级 | -0.0658 | 2.9461 | 1/3/1 | — |
| 重入节点级 | 0.0503 | 0.3676 | 3/3/4 | 0.9592 |
| 访问控制节点级 | 0.0311 | 0.2846 | 4/3/3 | 0.7206 |

方向消融单独列出，其原始p不属于上表四项对G0的Holm家族。这是完整增强图显式双向与正向版本的比较。反向关系同时改变参数和聚合路径，差值不是“纯方向语义”的单独因果效应；不能从局部任务的正差值推断双向在所有任务上必然更好。

在重入节点上，G1R相对G0只有约+0.0216pp，G2R为+0.5145pp，G3R为+0.5068pp；G2R/G3R/G3在该任务均为10/10折提升，对G0的best BF1 Holm校正p均为0.0078125；本批较明显的均值变化伴随L2状态读写关系接入，新增L3环境层没有继续提高该任务的best均值。访问控制节点上则四种增强均下降。它说明增添语义关系没有形成单调增益，但涉及关系参数、聚合和优化轨迹共同变化，不能将差值全部解释为某种依赖语义的纯因果贡献。

## 4. last 辅助结果

| 任务 | G0 | G1R | G2R | G3R | G3 |
| --- | --- | --- | --- | --- | --- |
| 重入合约级 | 92.1620 ± 3.0510 | 94.9699 ± 4.2352 | 94.9699 ± 4.2352 | 95.7037 ± 4.7257 | 94.3262 ± 4.1789 |
| 访问控制合约级 | 86.6580 ± 6.9124 | 84.2008 ± 5.6772 | 84.8065 ± 5.9793 | 84.9255 ± 5.7693 | 83.9763 ± 5.2135 |
| 重入节点级 | 97.0827 ± 6.6227 | 96.8179 ± 6.6368 | 97.3801 ± 6.6268 | 97.1568 ± 6.4290 | 97.3428 ± 6.5011 |
| 访问控制节点级 | 93.9087 ± 5.7938 | 94.1699 ± 6.4748 | 95.4570 ± 5.7513 | 94.7086 ± 5.9949 | 94.7351 ± 6.0385 |

完整辅助 Macro-F1/P/R 见 [last_fold_means.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/last_fold_means.csv)。best 与 last 多处方向不同：访问控制合约增强 best 均值高于 G0，但 last 均值均低于 G0；访问控制节点则 best 均值均下降，而 last 均值均提高。重入节点的不同剖面 last 增量也弱于或不同于 best。不能择优更换 checkpoint 后汇报一致收益。

## 5. G* 选择与补种子条件

G* = **G2R**。依据是各任务 inner_val 的 best Buggy-F1 折均值再对四任务等权平均，outer_test_used=false。这是汇总所有折内层验证后选出的全局剖面，不是每一外层折单独重新选型；本批没有新增外部独立测试，不能将G*成绩表述为已证明对未知语料泛化。

| 剖面 | inner_val 四任务等权均值 |
| --- | --- |
| G0 | 95.6626 |
| G1R | 95.8731 |
| G2R | 96.4945 |
| G3R | 96.2482 |
| G3 | 95.9229 |

与 G0 的内层差值为 **0.8319pp**。封存规则将距最高均值小于0.1pp的候选视为近似持平，再选 canonical relation 总数更少者，最后按名称；不能依据外层表格重新选型。

additional_seed_condition_met = **true**，additional_seed_execution_authorized=false。完整候选集和矩阵已齐全；是否满足绝对差值≥0.2pp的条件只作记录，本轮没有启动其他 seed、批次2/3或服务器训练。选择记录与 seal 位于原批次根目录 selection.json / selection.seal.json。

## 6. pooled OOF、预测变化与困难文件

pooled OOF 将每个外层样本的预测合并后重新计算，与等权折均值分开；不能把两种统计择优混用。

| 任务 | 剖面 | N | best BF1 | best MF1 | TN/FP/FN/TP |
| --- | --- | --- | --- | --- | --- |
| 重入合约级 | G0 | 142 | 92.8571 | 92.9563 | 67/4/6/65 |
| 重入合约级 | G1R | 142 | 94.9640 | 95.0682 | 69/2/5/66 |
| 重入合约级 | G2R | 142 | 94.9640 | 95.0682 | 69/2/5/66 |
| 重入合约级 | G3R | 142 | 94.2857 | 94.3651 | 68/3/5/66 |
| 重入合约级 | G3 | 142 | 94.9640 | 95.0682 | 69/2/5/66 |
| 访问控制合约级 | G0 | 114 | 94.5455 | 94.7304 | 56/1/5/52 |
| 访问控制合约级 | G1R | 114 | 95.4128 | 95.6056 | 57/0/5/52 |
| 访问控制合约级 | G2R | 114 | 95.4955 | 95.6110 | 56/1/4/53 |
| 访问控制合约级 | G3R | 114 | 95.4955 | 95.6110 | 56/1/4/53 |
| 访问控制合约级 | G3 | 114 | 95.4955 | 95.6110 | 56/1/4/53 |
| 重入节点级 | G0 | 12036 | 97.3611 | 97.0303 | 5171/295/58/6512 |
| 重入节点级 | G1R | 12036 | 97.3857 | 97.0549 | 5167/299/51/6519 |
| 重入节点级 | G2R | 12036 | 97.8157 | 97.5439 | 5206/260/32/6538 |
| 重入节点级 | G3R | 12036 | 97.8243 | 97.5520 | 5203/263/28/6542 |
| 重入节点级 | G3 | 12036 | 97.7678 | 97.4837 | 5189/277/22/6548 |
| 访问控制节点级 | G0 | 7710 | 96.5791 | 97.1848 | 4581/152/55/2922 |
| 访问控制节点级 | G1R | 7710 | 96.4410 | 97.0743 | 4582/151/64/2913 |
| 访问控制节点级 | G2R | 7710 | 95.9881 | 96.6964 | 4560/173/70/2907 |
| 访问控制节点级 | G3R | 7710 | 96.3504 | 97.0040 | 4586/147/73/2904 |
| 访问控制节点级 | G3 | 7710 | 96.3147 | 96.9672 | 4573/160/63/2914 |

完整 best/last OOF 见 [pooled_oof.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/pooled_oof.csv)。

### 6.1 best 预测变化，相对 G0

| 任务 | 剖面 | 纠正错误 | 新增错误 | 分类改变数 | 概率改变数 |
| --- | --- | --- | --- | --- | --- |
| 重入合约级 | G1R | 3 | 0 | 3 | 142 |
| 重入合约级 | G2R | 3 | 0 | 3 | 142 |
| 重入合约级 | G3R | 2 | 0 | 2 | 142 |
| 重入合约级 | G3 | 3 | 0 | 3 | 142 |
| 访问控制合约级 | G1R | 1 | 0 | 1 | 114 |
| 访问控制合约级 | G2R | 2 | 1 | 3 | 114 |
| 访问控制合约级 | G3R | 2 | 1 | 3 | 114 |
| 访问控制合约级 | G3 | 1 | 0 | 1 | 114 |
| 重入节点级 | G1R | 47 | 44 | 91 | 12036 |
| 重入节点级 | G2R | 79 | 18 | 97 | 12036 |
| 重入节点级 | G3R | 80 | 18 | 98 | 12036 |
| 重入节点级 | G3 | 74 | 20 | 94 | 12036 |
| 访问控制节点级 | G1R | 10 | 18 | 28 | 7710 |
| 访问控制节点级 | G2R | 8 | 44 | 52 | 7710 |
| 访问控制节点级 | G3R | 9 | 22 | 31 | 7710 |
| 访问控制节点级 | G3 | 7 | 23 | 30 | 7710 |

改变概率不必改变 argmax；相同 F1 也不代表模型没有读到新边。按文件及 source SHA 对齐的明细见 [error_changes.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/error_changes.csv)、[changed_predictions.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/changed_predictions.csv)。

### 6.2 困难文件与标签敏感性

以下错误均是**相对作者冻结标签**，不是本轮人工确认的真实漏洞真值。


| 任务 | 文件 | source SHA前12位 | fold | G0 | G1R | G2R | G3R | G3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 重入节点级 | buggy_18.sol | b9e23563d26a | 8 | 221 | 220 | 219 | 219 | 219 |
| 访问控制节点级 | buggy_18.sol | d8505eecd2d5 | 7 | 94 | 94 | 94 | 94 | 94 |
| 访问控制节点级 | buggy_26.sol | 129a0b4301cc | 8 | 42 | 42 | 42 | 42 | 42 |
| 访问控制节点级 | parity_wallet_bug_2.sol | 3026bd9ff80d | 4 | 3 | 0 | 2 | 1 | 2 |

上表是该文件的 FP+FN。重入 buggy_18 的错误仍占较大比例；访问控制 buggy_18/buggy_26 的主要错误未被消除。新增关系提供了信息，但未解决全部困难文件，也不能把这些错误全部归因为图构建或全部归因为标注。

争议文件全 SHA 和逐项指标见 [disputed_file_metrics.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/disputed_file_metrics.csv)；预登记 exclude_disputed 的等权折敏感性分析见 [sensitivity_fold_means.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/sensitivity_fold_means.csv)，仅作为报告分析，没有删掉训练样本或替换主结果。

## 7. 关系支持、机制与人工核验

150项模型中，首轮关系审计共有5923条“有训练支持且消息梯度非零”记录、287条“没有训练 v2 支持”记录（按 fit/canonical relation 计，不是唯一边数）；有训练支持却消息梯度为零的记录为0。未在训练部分出现但已注册的关系保留，不在评分阶段创建随机参数。完整 train/inner_val/outer_test 支持量与梯度见 [relation_support_and_gradients.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/relation_support_and_gradients.csv)。

节点任务的1/2跳机制统计使用 G*=G2R，明细见 [mechanism.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/mechanism.csv)。可达邻域与错误修正共现，只是机制描述；不能证明这些边导致了预测改善。阶段A使用预登记G3R进行机制描述，完整报告改为G*，相应行数或数值不同有明确来源。

人工抽查状态：**未完成**。review_v1 的512条和 review_v1b 的111条尚无完成的人工判断，不能把空白当正确，也不能用模型分数或合成 Oracle 代替真实边的人工精确率。见 [manual_dependency_review.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/manual_dependency_review.csv)。

## 8. 完整性与独立复算

阶段 B verify 和全部150项 run verify 均逐项重算完整文件 SHA；运行缓存不是最终验收替代。原阶段A已通过独立只读审计：18个旧报告文件、60份receipt、120个预测文件的SHA不变；13张共同表共5371行精确一致，其中32行G3R−G0配对结果及32组Holm原始p均不变。证据为 [independent_stage_a/audit.json](../experiments/artifacts/dfg_v2/prompt8b_v1/independent_stage_a/audit.json)，SHA c78b258e2633e9289e3ffd5b880b1bb4133c18e45312ab84161454d80026dbca。完整 Holm p 是新增四项家族校正，不属于原始成绩改变。自动REPORT.md前言保留了一句阶段A旧通用说明（Holm等待B），实际本批32个家族已处理：节点完整校正、合约描述性不适用；以本批holm.csv/report.json为准，不修改已经封存的自动报告。

独立指标脚本直接从标签/预测身份和二分类混淆计数重算 BF1/MF1/P/R：合约标签直接核对 SHA 验证后的 graph_labels.json；节点按冻结 G0 预测 targets 与 JSON masks 交叉核对，并按任务/类别/文件/source SHA/original_graph_node_id对齐，不按CSV行号猜测。独立脚本未再次直接反序列化图 pickle：自动审批拒绝不安全反序列化后未绕过，图/标签绑定由正式完整 verify 提供；不能把这一步称为另一套独立 pickle 标签验证。

独立重算与正式表比较通过：600条fold、3840条file、80条OOF、80条best及80条last均值/样本标准差全部匹配，最大绝对差2.842170943040401e-14。证据为 [independent_metrics/comparison.json](../experiments/artifacts/dfg_v2/prompt8b_v1/independent_metrics/comparison.json)。

本轮298个 runtime 文件摘要不变；150项 checkpoint 重载 inner_val/outer_test 的 best/last 预测均逐位一致，没有评分时创建参数，outer_test targets 不参与优化。

## 9. 资源与运行耗时

阶段 B 的90项 controller 命令总耗时 **16611.18秒（4小时36分51秒）**；result.seconds合计 **8743.10秒**。两者计时边界不同，前者含进程启动、校验和编排，不能把差额全当日志开销或纯训练时间。

| 范围 | fit数 | result.seconds合计 | peak allocated MiB | peak reserved MiB | 整卡最小free MiB | memory_tight fit | possible_memory_spill fit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A历史60项 | 60 | 16202.6655 | 1893.4678 | 2148.0000 | 18.0000 | 5 | 1 |
| B新增90项 | 90 | 8743.0991 | 1829.0293 | 2026.0000 | 53.0000 | 7 | 0 |
| 全部150项 | 150 | 24945.7646 | 1893.4678 | 2148.0000 | 18.0000 | 12 | 1 |

阶段B参数量范围4,715,746–5,019,442，完整矩阵4,371,010–5,299,796。每项 best/last epoch、参数量、耗时与资源见 [fit_resources.csv](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/fit_resources.csv)。best_epoch/last_epoch沿用产物的0-based编号，例如last_epoch=14表示完成15轮。memory_tight是local_dev_v1的记录信号，低于100MiB不触发自动缩图或改超参；本批没有OOM/非有限值失败。possible_memory_spill 是耗时诊断提示，不是已经证实发生换页。

**最终正式实验按用户计划将在显存充足的服务器开展；当前4GiB限制来自本地电脑。服务器尚未部署或核验，本轮没有迁移。未来服务器批次须独立绑定环境与结果，不能混合本地/服务器部分折作为同一次固定计算批次。**

## 10. 测试与复核命令

在mando环境、PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2和原TREE_SITTER_LIB_DIR下执行：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

v2 **2108 passed**，旧DDG/graph_utils **223 passed**，合计 **2331 passed**，0 failed/errors/skipped；运行前和最终回归均通过。37条警告为既有DGL/distutils/NetworkX弃用提示，不是新增失败。原日志与JUnit见prompt8b_v1的*_preflight和*_final产物。

实际完整流程（路径相对仓库）：

```bash
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json
AMEND=scripts/DFG/experiments/artifacts/dfg_v2/prompt8b0_v1/stage_B_amendment.json
AUTH=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/stage_B_authorization.json
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan "$PLAN" --stage B --authorization-record "$AUTH" --amendment "$AMEND"
python -u -B -m scripts.DFG.dfg_v2.experiment.batch verify --plan "$PLAN" --stage B --amendment "$AMEND"
python -u -B -m scripts.DFG.dfg_v2.experiment.run verify --plan "$PLAN" --amendment "$AMEND"
python -u -B -m scripts.DFG.dfg_v2.experiment.run select --plan "$PLAN" --amendment "$AMEND"
python -u -B -m scripts.DFG.dfg_v2.experiment.run summarize --plan "$PLAN" --amendment "$AMEND"
```

以上是已执行命令的记录，select/summarize为排他创建，不能把重复运行理解为覆盖已有报告。完整命令、返回码与耗时收据保存在prompt8b_v1。

### 10.1 完整执行及终验耗时

| 入口 | 秒 | 返回码 | 命令收据 |
| --- | --- | --- | --- |
| batch execute | 16611.1790 | 0 | stage_B_execute.command.json |
| batch verify | 361.2214 | 0 | stage_B_final_verify.command.json |
| run select | 745.3575 | 0 | select.command.json |
| run verify | 542.5140 | 0 | all_150_verify.command.json |
| run summarize | 1358.1180 | 0 | summarize.command.json |

select与summarize保留冻结实现的完整验收；summarize在run入口先verify150，随后reporting.build_report再次进行独立选择和逐项_completed核验，传入verified_results只比对、不跳过。这解释了报告阶段较长耗时，本轮没有为提速修改冻结代码或放宽验收，也不把这些重复终验耗时归因于普通日志打印。

## 11. 交付与剩余边界

完整生成报告为 [REPORT.md](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/REPORT.md)，机器可读正文为 [report.json](../experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/report.json)；本文件是提交到仓库的解释性总结。所有150项产物、初值、checkpoint、预测和本轮审计仍在WSL项目产物目录，没有迁移到C盘或清理旧结果。

下一步是否追加seed或服务器整批实验由用户另行决定。本轮不扩展其余五类、不做新聚合或DDG语义修改、不自动运行更多训练。当前能支持的是两类漏洞、一个seed、固定作者标签和固定图上的受控结果；还缺人工依赖精确率、独立seed稳定性及外部/归纳数据验证，不能写成完整Solidity数据依赖分析已被证明正确或七类漏洞均有效。

本轮未推送GitHub；代码与历史报告不改，文档由主代理复核后本地提交，等待用户明确推送请求。
