# 固定作者图的合约注意力读出：完整五折结果

实施、执行、独立核验与记录：Codex。阶段开始于美国东部2026-10-20，完整训练验收与交付于2026-10-21完成；产物同时保留UTC时间。

本阶段已完成20次新attention拟合，并只读复用20个历史mean结果。两个任务各5折、两种固定图、两种读出，合计40模型、80组best/last指标。全部为 **CV validation**；每折同一validation用于早停、选best和评分，不是独立测试。

**结论：这个预先固定的attention读出没有带来稳定合约级提升。重入增强图的主F1持平，访问控制明显下降。保留mean作为当前主方案，attention作为独立旁路保留完整负结果。不能将本轮推广成“所有DDG、所有读出或七类漏洞均无效”。**

## 1. 实际实现与比较对象

- HCG：下载作者CFG+CG融合图上的本地复跑基线，不是直接引用论文数值。
- Enhanced / HCG_DDG_GUARD：同一作者图，加已冻结的整体DDG及CONTROL_DEPENDENCE。所有原节点、标签、512维inside_token、原CFG/CG边与原折保留。
- mean：历史overall_cv_v1和guard_extension_v1各10个合约结果，完成来源、初值、配置与预测核验后引用，没有重训。
- attention：HGT输出后，每个源码文件内alpha=softmax(h @ a)，合约表示为sum(alpha*h)，后接原二分类层。a为全零128维向量，仅增加128参数，不使用节点标签、漏洞类型规则、top-k或额外MLP。

代码在开发树scripts/DFG/experiments/readout_attention/，不改原模型文件、HGT层计算、DDG语义、tokenizer或原训练脚本。新runs/HCG和runs/HCG_DDG_GUARD都是attention模型，目录名只标识图。

每折旧权重从保存的optimizer_steps=0初值逐张量精确复制；7240个共有张量验真，10组跨图共同参数按语义对齐。fit前恢复原fit_seed，没有从mean训练后权重或smoke继续。零初值数学等价mean，预检单列有限精度reduce误差，不用零向量特殊分支绕过梯度。

两任务实际配置保持512输入、hidden128、2层8头、dropout0.2/use_norm=True；Adam initial LR0.0005、OneCycle max LR0.01、div20/final_div1、cycle_momentum=True、weight_decay5e-6、原每轮step数、最大50轮、patience7/delta0.001。best严格选最低post-update eval validation loss；last独立保存。原FIT代码对象复用，只替换旁路模型、checkpoint绑定及观察性审计handlers。

## 2. 主结果：best，等权五折均值

单位为百分数；完整样本标准差、Precision/Recall、逐折及混淆矩阵见RESULT_TABLES.md和CSV。

| 任务 | HCG mean BF1 | HCG attention BF1 | 增强图 mean BF1 | 增强图 attention BF1 |
| --- | --- | --- | --- | --- |
| 重入合约 | 94.1593 | 93.5157 | 94.1593 | 94.1593 |
| 访问控制合约 | 93.5590 | 92.7619 | 93.5590 | 90.5564 |

| 任务 | HCG mean MF1 | HCG attention MF1 | 增强图 mean MF1 | 增强图 attention MF1 |
| --- | --- | --- | --- | --- |
| 重入合约 | 94.3452 | 93.6245 | 94.3452 | 94.3452 |
| 访问控制合约 | 93.8316 | 92.9588 | 93.8316 | 91.1449 |

| 任务/图 | attention−mean BF1(pp) | 差值样本SD | 提升/持平/下降折数 | 纠正/新增错误 |
| --- | --- | --- | --- | --- |
| 重入/HCG | −0.6437 | 1.4393 | 0/4/1 | 0/1 |
| 重入/增强图 | +0.0000 | 0.0000 | 0/5/0 | 1/1 |
| 访问控制/HCG | −0.7971 | 1.7824 | 0/4/1 | 0/1 |
| 访问控制/增强图 | −3.0026 | 4.8066 | 0/3/2 | 0/3 |

交互项定义为(增强attention−HCG attention)−(增强mean−HCG mean)。重入best为+0.6437pp，来自HCG attention退化，而不是增强attention超过原mean；只在fold2呈现这一差值。访问控制best为−2.2055pp，仅fold1下降，其余4折持平。不能只选择正交互而忽略四格实际表现。

## 3. 哪些文件改变

所有对照按task/fold/file/source SHA对齐，不能按CSV行号或单独文件名猜测；两个漏洞中同名buggy文件分开。

重入best：

- HCG attention在fold2新增0x67793426747f8c79332520c1291c4fc6443c8407.sol误报；阳性概率从mean的0.470997到0.713032。
- 增强attention纠正fold2的0x12345678979f29ebc99e00bdc5693ddea564ca80.sol旧误报（0.707791→0.436846），同时新增上述0x677934...误报（0.367810→0.563387）。总错误仍8，F1相同并不意味着预测相同。
- 原5个漏报modifier_reentrancy.sol、reentrancy_bonus.sol、reentrancy_simple.sol、simple_dao.sol、etherstore.sol在四格中均未纠正。

访问控制best：

- 两种attention在fold3均新增0x0c7b8eedd028f3730e7b0f3dc032e916302f09b4.sol误报。
- 增强attention在fold1额外漏报proxy.sol和rubixi.sol，造成该折相对HCG attention的BF1下降11.0276pp，五折均值下降2.2055pp。
- 原6个漏报parity_wallet_bug_2.sol、phishable.sol、FibonacciBalance.sol、mycontract.sol、multiowned_vulnerable.sol、unprotected0.sol在四格中均未纠正。

每个主要best对照，重入142/142、访问控制114/114个文件的概率都有变化。新增readout与HGT实际更新、增强关系有梯度，排除了“仅存入文件而未接入”的解释；当前变化主要未形成有利的决策变化。不能把全部差异单独归因于依赖语义，参数化、聚合方式和优化轨迹也改变。

之前讨论的两类buggy_18及访问控制buggy_26，在本批best合约四格中本来就预测正确。本轮没有训练节点模型，也没有修复其节点标签/定位争议。

## 4. last辅助结果与OOF口径

| 任务 | HCG mean BF1 | HCG attention BF1 | 增强图 mean BF1 | 增强图 attention BF1 |
| --- | --- | --- | --- | --- |
| 重入合约last | 90.8867 | 93.0421 | 91.6169 | 92.3525 |
| 访问控制合约last | 85.9247 | 80.7818 | 84.5429 | 82.5007 |

重入last的attention相对各自mean为+2.1554/+0.7356pp，提升并不稳定，且两attention相比较增强图还低0.6897pp。访问控制last相对各自mean为−5.1429/−2.0422pp；正的相对交互不代表超过原mean。best/last方向不完全一致，没有改选更有利checkpoint。

pooled_oof.csv单独按全部142/114文件汇总；等权折均值与pooled不混用。OOF仍是使用该fold验证集选模后的CV validation，不是独立测试。1024行完整四格OOF、2048行best/last文件错误记录、80条指标全部身份核验；概率平均变化分母使用完整population，不能使用稀疏变化表行数。

## 5. 正确性、测试与资源验收

- 36项新增测试、57项相关既有回归全部通过：93通过、0失败/跳过，4条既有DGL distutils弃用warning；没有声称重跑全部历史DDG测试。
- 四个真实零步预检通过：HGT输出精确一致，pool最大误差2.384e-7、logit最大2.1249e-5，初始类别相同、原初值未更新。预检不是正式成绩。
- 四个正式fold0计入20次，8个best/last核验后继续余16次，不按成绩放行、不换seed或删折。
- 20个新fit均attempt_001，0失败、0重试、0 OOM、0非有限loss。40个新checkpoint逐一验真，GPU原worker重载预测精确；独立CPU核验文件/tensor摘要、绑定、optimizer/scheduler状态和逐轮best/last、早停、OneCycle规则。
- 315条新读出epoch审计全部连接且非零，最小梯度L1为0.0001675。HGT与读出梯度/更新分开检查，不把a的更新算作HGT已连接。
- 新attention增强模型325条canonical×fold审计中316条有train支持且观察到非零message梯度；9条已注册但train未见者保留，不能强求其训练梯度非零，不在评分建参。
- 新20fit单调耗时合计3285.44秒，约54.76分钟，共315epoch；此为fit计时，不含全部准备、测试与分析，也不是纯GPU kernel时间。
- 最大allocated2894.40MiB、reserved3070MiB，最低整卡free21MiB。RTX3050 4GiB单模型串行，没有自动降维、改图、切CPU或关闭用户程序。历史背景负载不同，不据此宣称速度提升。

| 任务/图attention | 参数数 | 五折累计秒 | 峰值allocated MiB | 最小整卡free MiB |
| --- | --- | --- | --- | --- |
| 重入/HCG | 4527090 | 992.46 | 2103.31 | 23 |
| 重入/增强图 | 4781538 | 974.23 | 2894.40 | 21 |
| 访问控制/HCG | 4510674 | 636.00 | 1545.85 | 255 |
| 访问控制/增强图 | 4789746 | 682.75 | 2159.13 | 39 |

207份旧运行源码、15份新运行源码及692冻结资产末次SHA一致；另261份旧代码/用户文件保护检查不变。HEAD仍021a6f55ac9e3f94fc70feb441ff48b51b6a92ea，无Git写操作。两树文档仅追加，旧字节前缀保留。

## 6. 产物、命令与研究边界

完整结果：RESULT_TABLES.md、best_fold_results.csv、last_fold_results.csv、fold_statistics.csv、paired_deltas.csv、paired_statistics.csv、interaction_deltas.csv、interaction_statistics.csv、pooled_oof.csv、oof_predictions.csv、prediction_changes.csv、file_error_analysis.csv、resources.csv、relation_support_gradients.csv、readout_gradients.csv。

证据：plan/seal、prepared初值与manifest、20新收据及模型、mean_reuse_audit、historical_archive_audit、independent_preparation_review、fold0_acceptance/independent_review、final_independent_review、两个任务independent_analysis和delivery_manifest。原mean结果只读引用，不覆盖历史目录。每任务独立分报告位于reports/。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
python -B -m scripts.DFG.experiments.readout_attention.control verify
python -B -m scripts.DFG.experiments.readout_attention.control summarize
```

实现与从新批次执行的命令见源码README；已有成功批次不需要再prepare。运行版本、授权、数据、初始化、checkpoint和评分角色分别绑定。

本轮完成既定实验并停止。维持mean主方案，保留attention旁路用于复核；不围绕同一validation继续试多个读出直到挑到上涨。不新增训练seed、其余五类、独立测试或新关系。本批单seed、两个类别、作者标签争议和CV选模口径仍限制结论；折间SD不是独立seed方差。既有控制分析嵌套接收者绑定边界仍是另版正确性事项，当前冻结图已核验命中函数均回退，未在本批修改。