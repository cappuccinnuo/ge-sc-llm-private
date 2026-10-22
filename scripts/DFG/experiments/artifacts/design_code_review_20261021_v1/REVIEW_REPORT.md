# DDG 方案、代码与已完成实验审查

日期：2026-10-21。审查与记录：Codex。

本次是代码、设计及结果复核，没有修改分析算法、HGT、tokenizer、训练规则、正式图或标签，没有启动正式训练，没有修改旧 plan/seal。新增独立审计 JSON/日志及本报告；按既有要求向两工作树 training_changes 和 HANDOVER 追加记录。

## 1. 结论

当前已完成的是**在固定作者 HCG 上追加受限标量、状态与控制关系的实验系统**，并非完整 Solidity 数据依赖分析器。工程接入和结果计算已经形成闭环；尚未证明该增强能稳定改善两类漏洞的检测。

没有发现“DDG 未进入 HGT”“梯度被整体切断”“best/last 混用”或指标算错等足以解释当前低增益的实现故障。仍确认一项控制依赖接收者解析缺陷，另有旧入口与新能力不一致、历史验证入口及元数据问题。新增关系同时改变 HGT 聚合缩放，这是需要说明的设计归因限制，不能简单把所有分差解释成依赖语义收益。

当前开发树是 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11`，HEAD `021a6f55ac9e3f94fc70feb441ff48b51b6a92ea`。编辑器中的原树 `/home/zhao/SmartContract/ge-sc-llm`，HEAD `f3dfc17908029355c5fc45d6d3932f203068fcf5`，不含最新 state/control/后续实验旁路。原树用户修改的 auto_version_solc.py 保留。

## 2. 具体发现，按影响排序

### F1 — P2：地址转换接收者内的调用未完整核验

位置：`scripts/DFG/control_dependency/cfg.py:149–172,191–196,241–244`。

`address_receiver()` 只确认 cast 为 address；`call_effect()` 检查实际参数中的嵌套调用；表达式遍历遇外层 call 后直接返回，遗漏 receiver 内部调用。

独立探针 `require(ok); address(unresolved()).call(""); x=1;` 当前被判为 analyzed，生成2条控制事实；未知名字应按现有策略使整个函数回退。有已声明但内部 revert 的 target()，作为 `address(target()).call(...)` 接收者也会遗漏其求值控制语义。无需实现完整跨函数摘要；最小修复是递归核验接收者，无法建模则函数级无残留回退。

上述样例未执行 solc：未知名字样例仅为解析器健壮性测试；已声明 target 样例也不能声称通过编译。

对冻结四任务按 manifest 进行独立扫描：256个来源路径/SHA通过；广义40处 receiver 内含调用（含 ERC20(...) 等非缺陷模式）均已有函数回退，semantic/projected/published facts 都为0。精确 address-cast 缺陷模式只命中访问控制合约 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` 的 handleAllocation/handleWithdrawal，两者已因其他条件回退。**没有发现本批增强图污染；缺陷影响未来新增源码可靠性，不能用它解释本批低增益。**

证据：`state_control/receiver_binding_recheck.json`。

### F2 — P2：完整能力尚未整合到统一入口，误用旧训练入口会改变关系方向

位置：`scripts/DFG/README.md:3,10,78`、`cli.py:94`、`configuration.py:15`、`sco_models/graph_utils.py:426–445`。

主 CLI 的 use_ddg 仍只调用标量 pipeline。原训练 reflect_graph 仅给 DATA_DEF_USE 保留正向，其余关系仍走旧反射规则。独立两节点探针确认：STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE、CONTROL_DEPENDENCE 的0→1在旧入口会变成0→1和1→0。

正式实验使用 `state/stage_f/model_adapter.py` 和 `experiments/guard_extension/model.py`，独立探针确认五类新增边都保持正向。故**问题是通用使用入口和交付尚未统一，不是已完成实验漏接入或错误反射**。

最小后续处理：先提供明确的完整 profile/adapter 入口及方向断言，标记旧 CLI 为 scalar-only；不要直接改旧批次源码或 seal。也不能把原 README 的示例命令当作最新版完整方案。

证据：`legacy_adapter_probe.json`、`experiments/experiment_review.json`。

### F3 — 设计限制：新增 canonical relation 会改变原消息缩放

位置：`sco_models/model_hgt.py:104–117`，各关系内 attention 后，跨 canonical 使用 `cross_reducer='mean'`。

CPU无训练、无标签小图：train文件0→1、val文件2→3各有 next；在val文件单独增加 DATA_DEF_USE 后，train节点1虽没有新增入边，其聚合值仍从1变成0.5。新增 relation 的零消息参与跨关系平均。没有跨文件边或标签泄漏。

这说明固定 HGT 源码不等于新增关系后原消息尺度不变；干预同时包括语义、参数量、聚合和优化变化。**已证明存在这种机制，没有证明它是当前实际低收益的主因。** 最终输出还经过线性层、残差与归一化，不能据1→0.5就断言真实 logits 减半。

本轮不修改 HGT。若后续要归因，可先用固定权重/小图检查聚合影响；必要时另立预注册对照，不把变更偷偷塞入已完成实验。

证据：`experiments/canonical_mean_probe.json`。

### F4 — P2/P3：文档、旧验证入口和证据字段存在漂移

- `overall_cv/common.py:18–20,35` 按整个当前 DDG 源码文件集合与旧计划比对。旧186份文件未改/未删，但新增43份旁路源码，使旧 README 的 `overall_cv.control verify` 报 Runtime drift。应使用已有只读 `guard_extension/archive.py:8–28` 按历史清单核验，不改旧 seal。
- 根 README 的140 tests、scalar-only和“未训练”等是第一阶段历史描述；experiments README也有旧范围描述，不能作为当前总状态。
- 原宏观指南将 E2 定义为反向 DDG、E3为跨函数摘要；后续授权的 H1/H2 实际 E2=修复标量，E3a=加状态DU，E3b=加顺序。后续设计调整合理，但名称应按批次解释，不能由“E3完成”推断跨函数摘要已完成。
- `state/stage_j/modifiers.py:67` 的旧 `control_dependence_edges=False` 被 `control_dependency/analysis.py:110` 复制进新控制事实。四任务302/311/143/150条 modifier 事实携带此历史字段；这是证据含义歧义，不是实际没控制边。
- H1报告配置段统一写合约LR；真实节点manifest为0.0002/0.005、weight_decay=0，合约为0.0005/0.01、weight_decay=5e-6。H2已有澄清。本轮未发现实际任务配置被错误统一。

## 3. 已实现与未完成

| 能力 | 当前状态 | 边界 |
|---|---|---|
| 声明/作用域符号身份 | 已实现并验证 | 文件/函数/声明位置，不按同名就连边 |
| 标量 DEF/USE 与 RD | 已实现 | 赋值、复合赋值、增减、参数/返回、条件；CFG正向、KILL、分支union、循环fixpoint |
| 精确投影 | 已实现 | 源码/AST/角色/端点匹配；缺锚点不猜最近行；写入先参与KILL |
| 固定图追加关系 | 已实现 | 原节点、属性、标签、token、基础CFG/CG边不变；多关系可同端点共存 |
| 简单状态/部分mapping | 已实现受限域 | 声明身份、已确认键、EXACT/MAY、强弱KILL、ENTRY_UNKNOWN、调用HAVOC |
| 状态访问/调用后写顺序 | 已实现 | 两种独立顺序关系；不是状态值Def–Use，也不是完整漏洞可利用性证明 |
| 受限继承/modifier | 已实现 | 同源闭合继承及可确认声明；无参数直线前缀、一次末尾占位符等子集 |
| 控制依赖 | 已实现受限域 | 独立控制CFG、出口、后支配直接关系；已知F1缺陷待修 |
| HGT/训练接入 | 已实现于专用旁路 | 新canonical、正向adapter、监督梯度、输入/初始化/checkpoint绑定 |
| 完整K折与三变体消融 | 两类别已完成 | 单seed；paper_kfold CV validation；非独立测试 |
| Attention合约读出 | 实现且完成对照 | 属模型读出旁路，不是DDG语义；结果未支持替换mean |
| 完整跨函数/跨交易摘要 | 未完成 | 不可用状态顺序关系冒充参数→返回或跨交易数据流 |
| 任意storage引用、复杂数组/struct/mapping、动态分派 | 未完成 | 不支持情况保守回退，不删样本 |
| 完整modifier/异常/非终止、路径可行性 | 未完成 | CFG见证是may路径，不是SMT可行性证明 |
| 任意新源码的一站式增强推理 | 未交付完整统一接口 | 当前固定图、源码身份与旁路模型已验收；不同于任意输入产品化 |
| 其余五类、多seed、独立测试、去重源码行指标 | 本批未完成 | 设计不按漏洞名硬编码，不等于七类效果已验证 |
| 反向DDG | 有意未加入 | 后续明确暂缓，不当成本轮漏实现 |

标量关键源码：symbol_table.py:139/149；access_extractor.py:90/108/114；reaching_definitions.py:91/109/141；projection.py:63/96；graph_audit.py:26。独立9组语义/不变量探针通过。

## 4. 覆盖是否足够支撑预期收益

实际最新版图新增关系数量（不把节点任务和合约任务相加，因为样本包含关系）：

| 任务 | 标量DU | 状态DU | 状态访问顺序 | 调用→写入 | 控制依赖 |
|---|---:|---:|---:|---:|---:|
| 重入合约 |3561|9|1573|1109|3086|
| 重入节点 |1894|4|1507|1102|2421|
| 访问控制合约 |4032|14|107|0|1929|
| 访问控制节点 |2836|5|62|0|1384|

状态支持/回退函数记录依上述任务顺序：2189/1199、1528/517、2058/985、1495/463。支持不等于一定产边。

对函数内先读旧余额→外部调用→再写余额的典型重入模式，后面的写不能反向伪造为前面读的定义；函数入口状态来源未知，调用之后又可能HAVOC。因此正确的函数内STATE_DEF_USE本来就可能很少。当前方案用独立顺序关系补上下文是合理的，但不能说已经完整刻画跨交易/回调依赖。

访问控制中“谁能到达敏感操作”也不是普通Def–Use能完全回答。现有受限modifier及控制依赖已经补了一部分；复杂授权链、跨函数调用仍在范围外。模型目前统一消费CONTROL_DEPENDENCE，分支真假等更细证据未作为独立关系输入。

新控制边确实新增两层可达上下文（四任务按合约R/AC、节点R/AC为1690/1096/999/464对），所以不能说全部边是重复信息。但是否提供与当前冻结标签一致、模型可利用的信息，需要由预测证据判断。

## 5. 已完成实验与可成立的结论

| 批次 | 完成情况 | 不能混淆的内容 |
|---|---|---|
| 早期E0/E1 |30配对折、60模型|早期标量，非最新整体方案|
| Stage G/H1/H2 |12+52+26=90模型|三变体E2/E3a/E3b；复用fold0已含在总数|
| Stage K |两个节点任务fold0、4模型|小折诊断，不代表完整K折|
| overall_cv |60新模型|fresh HCG锚定，共同参数配对；与旧H1/H2初值不同|
| guard_extension |30新模型+60历史引用|不是另训练90个；增加控制依赖|
| readout_attention |20新模型+20历史mean引用|仅合约任务；没有新增节点训练|

不能跨批次相减来声称某条关系收益，因为初值锚、能力范围等不同。以下是同一整体对照链、best最低验证loss对应的等权折均值Buggy-F1：

| 任务 | 作者HCG本地训练 | 整体DDG | DDG＋控制依赖 | 完整候选−HCG(pp) |
|---|---:|---:|---:|---:|
| 重入合约 |94.1593|94.1593|94.1593|0.0000|
| 访问控制合约 |93.5590|93.5590|93.5590|0.0000|
| 重入节点 |96.0580|96.1027|96.1210|+0.0630|
| 访问控制节点 |95.9723|95.8887|95.9171|−0.0553|

来源：overall_cv_v1、guard_extension_v1的fold_statistics.csv及本轮独立OOF重算。这里“作者HCG”是本地训练作者图，不是论文原表数字。节点按HCG节点计分，不是去重源码行F1。

加控制依赖相对原整体DDG：重入节点3折上升/2持平/5下降，访问控制3/4/3。两个合约任务概率均变化，但argmax类别不变，所以F1相同是成立的，并不要求加边后F1必升或必降。

Attention未解锁合约增益：重入增强图94.1593→94.1593，访问控制93.5590→90.5564；原HCG attention也下降。重入增强分支F1相同但一纠错一新增错误，不能只比较总分。主方案宜保留mean，attention归档为完整负结果。

主best与last不能择高混用。完整候选last相对原HCG：重入合约90.8867→91.6169、访问控制85.9247→84.5429、重入节点97.1504→97.1342、访问控制95.8010→94.1214。方向并非统一，不能改选last来宣称方案成功。

## 6. 为什么困难文件和高分不能仅归因DDG

重入buggy_18节点错误252、访问控制buggy_18/26错误87/42，在三个mean图配置中均未改善；这三个文件合约分类本来为TP。旧定点审计中，它们错误里分别197/83/42落在作者与公共标注分歧，剩余55/4/0属于已审查参考一致节点。

这不证明公共标注一定正确，也不证明所有错误都是标签造成。添加DDG不会自动改变被冻结的监督目标，当前仍保留作者标注。未审计节点不能算“已确认干净”。

大量跨文件注入模板重合与单折99分并存；完整10折均值约96，并非所有结果99。训练文件隔离不能排除模板重复；重复统计本身也不足以证明模型只记忆。当前主实验同val早停/选best/评分，应称CV validation，不得当作独立测试或七类泛化结论。反复依据同一CV修改方案还会增加研究选择偏差，不能靠继续尝试直到涨分解决。

## 7. 本轮验证

| 测试组 | 通过 | 失败 | 跳过 | warning |
|---|---:|---:|---:|---:|
| 标量DDG tests |222|0|0|28|
| state + stage_f/j/k + control_dependency |215|0|0|4|
| overall_cv + guard_extension + attention接口 |83|0|0|4|
| 原项目graph_utils/imports/CLI/early_stopping |19|0|0|7|
| 合计（不重复计数） |539|0|0|43|

警告是既有DGL/Torch TensorBoard distutils及NetworkX read_gpickle弃用项。首次标量测试遗漏Linux grammar环境时188通过/34失败，均invalid ELF header；按README使用已有Linux grammar后222通过，未安装或更换二进制。state早期unittest只收集38项，已以pytest215项替代，不重复累计。

独立核验：

- 9组标量语义探针：声明遮蔽、无传递闭包、union/KILL、loop固定点、缺投影写KILL、图属性、off等价、标签置换、函数回退无残留。
- 接收者正反例及冻结数据影响扫描；测试全绿仍漏掉F1，不能用全绿替代语义审查。
- 旧/新adapter五种关系方向小图对照；跨canonical平均小图探针。
- 按task/fold/file/source SHA/node身份独立重算120+180+80=380组best/last F1、P/R、混淆矩阵，零不一致；101034导出记录含历史重复引用，不是101034独立样本或380次新训练。
- 最新计划seal及207历史+15新运行源码，共222份hash一致。新关系训练支持与实际非零message梯度证据存在，无支持关系单列保留，不在评分时建参。

命令均在开发树、mando环境、CPU下执行：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export CUDA_VISIBLE_DEVICES=
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/zhao/miniconda3/envs/mando/bin/python
$PY -B -m pytest -q -p no:cacheprovider scripts/DFG/tests
$PY -B -m pytest -q -p no:cacheprovider scripts/DFG/state/tests scripts/DFG/state/stage_f/tests scripts/DFG/state/stage_j/tests scripts/DFG/state/stage_k/tests scripts/DFG/control_dependency/tests
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 $PY -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/overall_cv/tests scripts/DFG/experiments/guard_extension/tests scripts/DFG/experiments/readout_attention/tests
$PY -B -m pytest -q -p no:cacheprovider tests/test_graph_utils.py tests/test_model_imports.py tests/test_classifier_cli.py tests/test_early_stopping.py
```

本轮没有重新加载全部大型checkpoint，没有执行solc/EVM验证、完整全部仓库历史测试、正式GPU训练或作者标签真值重认证。历史checkpoint验收记录已核对，但不能说本轮又重跑了全部GPU验收。

## 8. 建议的下一步与停止范围

1. 先在新版本最小修复F1，补receiver未知/已声明但有控制效果/正常接收者回归，维持函数级无残留回退；同时修清modifier证据字段。这是正确性修复，不以F1上涨验收。
2. 整合一个明确的完整profile入口，强制匹配相应关系adapter；标注scalar-only旧入口，给历史批次只读归档核验命令。保持已有实验、初始化、标签与seal不变。
3. 将当前DDG工程版收束，保留mean，不继续无目标堆关系或更换读出。依据已有无争议错误与真实新增依赖选择少量正反例，检查信息是否确实到达决策节点；并记录canonical均值效应。优先做无需重训的机制诊断。
4. 只有存在明确新信息与模型利用证据后，再设计一个固定的后续验证。独立评估/多seed可检验稳定性，是否做需要新的明确实验范围；不自动扩其余五类，不把本批负结果改写为“七类无效”。

本次结束于审查与记录。尚未实施上述修复，未启动新训练。