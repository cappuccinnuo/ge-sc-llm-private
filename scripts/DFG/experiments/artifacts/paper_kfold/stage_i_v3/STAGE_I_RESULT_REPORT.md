# Stage I：能力清单与固定权重状态消息诊断完成报告

日期：2026-10-19。实施与分析：Codex。工作树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`，HEAD `021a6f55ac9e3f94fc70feb441ff48b51b6a92ea`。

本轮完成授权的第1步（能力清单、版本编号和入口约束）及第2步（既有证据链与checkpoint消息诊断）。新增60个模型的只读诊断记录，每个读取best/last，共120份checkpoint、720个评分条件；新增训练次数为0。没有实施modifier、控制依赖、反向关系或其他模型扩展。

## 1. 结论

新关系已经被实际HGT读取，既不是“只存进图文件”，也不是完全没有训练支持。问题主要是现有关系对主要错误的覆盖很少，很多消息只改变置信度，不改变分类。少量正向案例存在，但不足以证明稳定提升或七类泛化。

本轮固定权重干预与H2的重新训练消融回答不同问题：前者检验已训练模型当前依赖哪些消息；后者同时包含关系语义、参数、聚合和优化轨迹变化。不能把屏蔽后的E3b等同于重训E3a/E2，也不能以本轮小差值否定关系在训练过程中的影响。

所有指标仍为CV validation，节点计分单位为HCG节点，不是去重源码行；单seed、同一val选择best并评分。pooled与等权折均值分开，没有独立测试。

## 2. 第1步：能力与入口核对

详见[能力矩阵](../../../stage_i_diagnostics/CAPABILITIES.md)、[入口说明](../../../stage_i_diagnostics/ENTRY_POINTS.md)及[modifier说明](../../../stage_i_diagnostics/modifier_scope.md)。

当前E2=修复版标量DATA_DEF_USE；E3a=E2+STATE_DEF_USE；E3b=E3a+STATE_ACCESS_ORDER+EXTERNAL_CALL_BEFORE_STATE_WRITE。早期宏观方案中E2/E3曾指反向关系/内部调用摘要，不能据当前编号宣称这些旧候选已完成。

现有实现涵盖声明/作用域身份、函数内标量DEF/USE、语义CFG和到达定义、保守状态位置与HAVOC、三类状态/顺序关系、精确原HCG投影。没有完整Solidity类型/别名系统、跨函数或跨交易摘要、modifier组合及独立控制依赖。

发现并显式约束的入口风险：旧graph_utils只保护DATA_DEF_USE不被反射；状态图应走Stage F/e23_pilot四类正向关系adapter。新增entry_validation.py拒绝状态图误入legacy及未知增强关系。此检查是旁路显式调用，不能拦截用户直接运行旧脚本；未修改旧训练代码。

## 3. 第2步：执行方法与验收

六条件：N正常；Z_D屏蔽STATE_DEF_USE；Z_S屏蔽STATE_ACCESS_ORDER；Z_C屏蔽EXTERNAL_CALL_BEFORE_STATE_WRITE；Z_SC同时屏蔽两类顺序；Z_ALL屏蔽全部三类状态增强。原标量DATA_DEF_USE始终保留。

使用原HGT注意力和聚合计算，在canonical消息聚合前置零选中消息；保留边、节点、schema、参数和cross-mean分母。eval+no_grad，无optimizer/backward。无对应关系时要求严格无效操作；退出干预恢复原输出。每个checkpoint均检查图/标签/特征/schema、参数对象及权重摘要。全部120份正常概率与历史结果完全一致，恢复与native逐位一致，optimizer_steps=0。

消息审计覆盖41,660项canonical×layer×checkpoint观察，其中1,020项状态关系正常消息全部非零；Z_ALL下选中有效消息全部为0，cross-mean分母全部保持。范数是全固定图按canonical目的节点SUM的Frobenius L2，不是逐边、逐节点因果份额；train/val支持是边计数，不是分训练/验证的消息范数。第二层基础消息可能因第一层隐藏表示变化而变化，这是干预的后续传播。

## 4. 覆盖与错误区域

| 任务 | STATE_DEF_USE | STATE_ACCESS_ORDER | CALL_BEFORE_WRITE | 两层潜在影响节点 | 获得新上游节点身份 |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 6 | 847 | 547 | 1379 | 576 |
| 访问控制合约 | 11 | 33 | 0 | 74 | 12 |
| 重入节点 | 3 | 829 | 547 | 1338 | 575 |
| 访问控制节点 | 4 | 16 | 0 | 37 | 1 |

两个节点任务共7条状态Def–Use全在构造器；合约图17条中12条在构造器，5条在getCurrentTokenPrice。不同粒度重复的事实不能相加当独立证据。访问控制节点20条增强边的端点在E2已有两跳可达，E3b相对E3a没有新增上游节点身份；这不等于新关系类型语义必然无用。

重入节点E2 best共439错，422错（96.13%）在增强关系潜在影响域外；域内1338节点仅17错，575个新上下文节点仅4错。访问控制E2的206错全部在域外，37个潜在影响节点和1个新上下文节点本来都判对。不能只靠增加这些位置的消息期待大幅F1变化。

既有独立训练的E3b−E2变化多数位于域外，可能通过共享参数/优化过程发生；本轮固定权重诊断的所有节点概率及类别变化均位于各自两层潜在影响域内。单关系条件使用整个变体增强范围作为保守上界，不伪称精确关系级因果域。

## 5. best主诊断结果

以下均为Z_ALL−N，负数表示屏蔽使结果变差，即保留消息对该checkpoint有益。概率变化阈值为1e-8；翻转/错误为汇总全折的样本计数。未给E0/E1重新训练。

| 任务 | 变体 | N BF1 | 屏蔽后BF1 | 等权ΔBF1/ΔMF1(pp) | 类别翻转 | 纠正/新增错误 | 概率变化数 |
|---|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | E3a | 95.0140 | 95.0140 | +0.000000 / +0.000000 | 0 | 0 / 0 | 5 |
| 重入合约 | E3b | 95.0140 | 95.0140 | +0.000000 / +0.000000 | 0 | 0 / 0 | 61 |
| 访问控制合约 | E3a | 91.5628 | 91.5628 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制合约 | E3b | 91.5628 | 91.5628 | +0.000000 / +0.000000 | 0 | 0 / 0 | 24 |
| 重入节点 | E3a | 96.0388 | 96.0335 | -0.005299 / -0.006401 | 1 | 0 / 1 | 4 |
| 重入节点 | E3b | 96.2460 | 96.2346 | -0.011342 / -0.008748 | 1 | 0 / 1 | 1331 |
| 访问控制节点 | E3a | 96.2631 | 96.2631 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制节点 | E3b | 96.3495 | 96.3495 | +0.000000 / +0.000000 | 0 | 0 / 0 | 37 |

两个合约任务所有六条件、best/last均无类别变化。访问控制节点也全部无类别变化；E3b best只有37/7710节点概率变化。重入E3b best有1331/12036概率变化，但Z_ALL只新增1个漏报，来自buggy_42.sol节点12245。

重入E3b best单Z_D产生2个新增错误，等权BF1 −0.010593pp；Z_S不改类别，Z_C/Z_SC/Z_ALL各新增1错、−0.011342pp。联合干预不等于单项相加，不能据Z_ALL翻转更少认定STATE_DEF_USE没有作用。

## 6. last辅助诊断

| 任务 | 变体 | N BF1 | 屏蔽后BF1 | 等权ΔBF1/ΔMF1(pp) | 类别翻转 | 纠正/新增错误 | 概率变化数 |
|---|---|---:|---:|---:|---:|---:|---:|
| 重入合约 | E3a | 90.2265 | 90.2265 | +0.000000 / +0.000000 | 0 | 0 / 0 | 5 |
| 重入合约 | E3b | 90.2265 | 90.2265 | +0.000000 / +0.000000 | 0 | 0 / 0 | 59 |
| 访问控制合约 | E3a | 86.1731 | 86.1731 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制合约 | E3b | 86.1731 | 86.1731 | +0.000000 / +0.000000 | 0 | 0 / 0 | 21 |
| 重入节点 | E3a | 96.9309 | 96.9256 | -0.005294 / -0.006403 | 1 | 0 / 1 | 4 |
| 重入节点 | E3b | 96.8440 | 96.9044 | +0.060467 / +0.041503 | 4 | 2 / 2 | 1338 |
| 访问控制节点 | E3a | 96.0594 | 96.0594 | +0.000000 / +0.000000 | 0 | 0 / 0 | 6 |
| 访问控制节点 | E3b | 94.7358 | 94.7358 | +0.000000 / +0.000000 | 0 | 0 / 0 | 33 |

last仅辅助报告，不取代最低验证loss选择的best。重入E3b last Z_ALL纠正2错、引入2错：等权BF1 +0.060467pp，但pooled BF1 −0.000666pp。折样本权重与F1非线性不同，出现反向是允许的；不能挑有利口径。完整逐折、样本SD、P/R、混淆矩阵及其他干预条件见CSV。

## 7. 真实案例和困难文件

完整身份、源SHA、原node ID、概率、路径及训练支持见[case_review.md](case_review.md)。

- **保留已有正确**：重入buggy_32.sol构造器节点4167，E2本就正确。E3a best正常概率0.334572，屏蔽状态Def–Use后0.764275成为误报。4167→STATE_DEF_USE→4168，再经原模型反射的next_line返回4167，符合两层作用范围。对应canonical train2/val1且34轮均有非零梯度。证明消息被依赖，不证明比E2新增能力。
- **best局部增量**：重入buggy_42.sol节点12245，计数器更新语句，E2/E3a best概率约0.4846均漏报；E3b正常0.512159判对，Z_C后0.490741又漏报。它是新增边直接目标，获得4个新上游身份，有训练支持。只是一处接近阈值的单seed案例；E2 last原已判对，不能扩大解释。
- **顺序关系联合效应**：buggy_24.sol的end_if节点1554/1587，E3b last单屏蔽任一顺序关系均正确，联合屏蔽才漏报。节点不是直接新边目标，而是通过原基础边接收两层影响。
- **非线性补偿**：buggy_32节点4167在E3b last单Z_D变错，Z_ALL反而仍正确。不能将各单项差值直接相加。

困难文件的所有干预均无类别变化：重入buggy_18/buggy_36、访问控制buggy_18/buggy_26。历史best三变体分别仍为275/58/94/42个节点错误。重入两文件只各有8条新边，访问控制buggy_18仅1条，buggy_26无新边；大量困难语义未进入本次状态分析，不宜归因于网络完全学不会状态关系。

已有源码分析记录的继承类回退约占54%–62%，modifier约9%–14%。这是首先触发的原因，不是修复后保证可恢复的函数数；也不能由文件级数量推断每个错误节点的根因。Stage F侧表与其delivery摘要匹配，但该delivery未纳入旧H2 frozen_files；本轮仅将它作为观察封存的历史旁证，不伪称被旧seal认证。

## 8. “受限modifier”解释与后续顺序

受限是限制**分析器支持的语法/语义子集**，不是把modifier理解为某一种漏洞。未来可先考虑：声明唯一、实参/形参绑定明确、一个可确定执行位置的下划线占位符、控制结构及副作用均能解释。复杂继承/组合/多个占位符先回退，不能按onlyOwner字符串猜。

例如onlyOwner中的require可能位于函数显式正文之外；modifier还可能更新重入锁、记录状态。忽略它会漏掉真实执行上下文。当前semantic_cfg及Stage F analyzer遇到modifier调用主动函数级回退，保留原HCG，不是偷偷忽略。解析modifier的执行顺序与生成guard到操作的控制依赖是两项工作；不能把权限检查强行命名为STATE_DEF_USE。

原始两份宏观方案没有modifier专项设计；后续DDG_INTEGRATION_ANALYSIS_2026-10-11.md明确要求适配其绑定/控制影响，不可靠则回退。当前建议是解决已知范围限制的一种分期方法，并非原第一版已实现。本轮没有编码该扩展。Solidity语义参考：[官方函数修饰器说明](https://docs.soliditylang.org/en/latest/contracts.html#function-modifiers)。

下一步先在现成困难函数中核对首个阻断原因、错误节点上下文与可用HCG锚点，确定受限继承/绑定或modifier哪一项能恢复有用语义，再小范围实现并做正反例、回退及投影验收。不得按标签筛选实际构图规则。新覆盖应先与现有错误区域核对，随后才决定新的受控训练；本轮不自动执行该阶段、不承诺F1提升。

## 9. 版本、测试、修订及未执行事项

- 核心新增旁路：stage_i_diagnostics下能力/入口文档、entry_validation、evidence、interventions、common/run、aggregate和测试。冻结DDG/HGT/tokenizer/训练器没有修改。
- v1计划在执行前修正验收描述问题后保留；v2在创建模型前遇read_graph的Path接口错误，修复并补回归，旧日志/计划不覆盖；v3为实际完整批次。
- 封存aggregate.py仍使用旧评分角色检查，故默认run summarize拒绝新诊断角色。保留失败日志与封存源码，使用产物目录aggregate_stage_i.py修正角色绑定；附来源SHA和diff，指标公式及预测不改。README给出实际可用命令，不声称旧默认入口已经修好。
- 主接入/相关回归126项通过，后处理36项通过，共162项、0失败/跳过；两次测试各有4条同类既有DGL distutils弃用警告。日志完整保留。
- 60项回放全部成功，无OOM或训练重试；预检错误不计为模型训练失败。没有升级依赖、外部solc下载或编译验证；没有重跑全部历史DDG语义测试和正式训练。
- 原图、标签、512维特征、fold、历史模型、旧plan/seal保持。原工作树auto_version_solc.py已有用户改动保留。两工作树文档均仅追加，未pull/checkout/reset/commit/push。

本轮60项推理/校验记录耗时合计3319.838秒（约55.33分钟）；最高allocated 706.573 MiB、reserved 742.0 MiB，整卡最低采样空闲1335 MiB，采样错误0。这含加载、哈希、重复前向和范数同步，不是训练耗时，也不是连续监控显存的绝对最小值。

完成后H1只读归档复核52新+8复用=60、H2复核26新+4复用=30，均通过。当前计划/源码/输入/静态证据摘要及60份回放收据均通过。最终文档前缀及用户改动保护清单见protected_after.json。

## 10. 复核入口及产物

在现有mando环境、开发工作树中执行；这些是只读复核/后处理，不启动训练：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.verify_h1_archive
python -B -m scripts.verify_h2_archive
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v3/verify_delivery.py
```

后处理实际命令、测试及可验证复用入口见[README](../../../stage_i_diagnostics/README.md)。不重新prepare封存目录，不调用默认旧summarize。

主要产物：
- plan/seal、60项replays收据、120份预测/审计、fold0_gate与replay_verification；
- intervention_fold_metrics/statistics/pooled/file_changes、changed_predictions；
- message_norm_summary/by_fold与message_edge_effectiveness；
- prediction_context下逐文件、困难文件、上下文区域、来源摘要；
- case_review、资源CSV、测试/归档日志、protected_after及delivery_manifest。

本轮至第1、2步完成后停止。以上诊断不改变原90次三变体正式实验结果。
