# DDG统一工程版实现与验收

日期：2026-10-21。实施、源码审阅、验收与记录AI：Codex。

## 结论

上一轮推荐的正确性修复、统一入口、四任务等价验证、有限Oracle和一次模型利用机制诊断已完成。交付的是当前受限语义范围内可运行的完整工程闭环，不是完整Solidity静态分析器，也不是已经取得稳定F1增益的新方法。

最新代码在 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/integration/`。原编辑树保留原代码，两树文档同步追加。HEAD保持 `021a6f55ac9e3f94fc70feb441ff48b51b6a92ea`；原编辑树HEAD保持 `f3dfc17908029355c5fc45d6d3932f203068fcf5`。未pull/checkout/reset/commit/push。

本轮没有新fit，没有改标签、tokenizer、HGT、原训练规则、fold、已封存图或历史seal。230个事前记录的旧生产Python文件SHA均不变，包含原编辑树用户已修改的auto_version_solc.py。历史结果继续属于原运行版本。

## 实际变更

| 新文件/目录 | 作用与修改理由 |
| --- | --- |
| integration/__init__.py | baseline/scalar/full/full_guard能力配置与五关系集合 |
| integration/control_v2.py | receiver副作用/嵌套调用保护、modifier证据字段说明、可配置迭代上限；旁路复用旧算法 |
| integration/pipeline.py | 串联原scalar、Stage K状态/顺序、新control；检查节点、原边、标签、特征与输入不变 |
| integration/io.py、cli.py | 源码SHA清单、非覆盖输出、图roundtrip、统一构图入口 |
| integration/model.py | 绑定既有五关系正向adapter，原HGT/mean读出；输入校验 |
| integration/rebuild.py | 从已封存原图清单重建四任务，比较图、模型输入及有序DGL端点 |
| integration/archive.py | 按历史记录名单核验旧运行，允许新增旁路文件但不放宽旧文件SHA |
| integration/oracle.py | 先封存12函数，再按预设验证事实、投影和回退 |
| integration/tests/ | 67项新增接口、语义与保护测试 |
| experiments/integration_diagnostics/ | CPU共同初值聚合诊断及7项测试 |
| integration/README.md | 完整方案范围、架构、实用命令、模型adapter与限制 |

原有生产Python不直接打补丁的原因：这些文件已被多个实验seal绑定。用子类与私有FunctionType命名空间复用旧函数，不做全局monkeypatch，使旧实验仍可复核；新入口明确使用新版控制分析。两树DFG README增加当前入口说明，开发树overall_cv README增加只读归档命令。此前训练变更第1—36节保留，新增第37节。

## 已完成的整体能力

1. 源码/元数据身份核验，独立语义CFG和声明/作用域绑定。
2. 标量DEF/USE、KILL、分支union、循环fixpoint，正向DATA_DEF_USE。
3. 同合约受限状态/简单mapping、ENTRY_UNKNOWN、别名与写覆盖、调用HAVOC、STATE_DEF_USE。
4. STATE_ACCESS_ORDER和EXTERNAL_CALL_BEFORE_STATE_WRITE；它们是顺序证据，不是伪造的def-use。
5. 已有受限继承、modifier恢复及CONTROL_DEPENDENCE。控制依赖也不等同于数据依赖。
6. 语义事实精确投影原HCG，保留节点ID、类型、源码映射、标签、token和原CFG/CG。不能投影则留证，不按最近行猜边。
7. 五类增强关系全部保持正向，同端点不同关系可共存；HGT真实读取canonical关系。
8. baseline完整恢复原图；缺源码/不支持分析不删除样本；错误身份直接报错。
9. 统一构图与模型装配，图/特征/标签绑定、构图审计、历史归档核验。

没有增加变量节点或把独立语义CFG替换为模型CFG。控制分析回退时不提交该函数的不确定控制事实，已经独立确认的原图/其他分析阶段结果不删除。

## receiver修复证据

旧 `control_dependency/cfg.py` 的成员调用处理对地址转换接收者缺少递归效果核验；接收者内部含未知或有控制效果的调用时，可能仍沿普通外部调用路径生成控制事实。不能用Tree-sitter能解析来证明绑定或执行语义已经正确。

新ControlCFGBuilderV2首先检查成员接收者表达式，遇嵌套call、赋值、更新、new等当前不能可靠建CFG的情况，整函数回退并记录表达式/位置/原因。裸内建终止调用规则未重新设计，普通to、msg.sender及支持的纯地址转换不受影响。未知与同名用户声明的嵌套调用都不能被当成纯接收者。

`control_v2_before_after.json`保存同一安全断言的前后证据：旧路径未知receiver仍分析并产生2条事实，安全断言失败；新版回退、IR=None、0事实，断言通过。测试还覆盖正常调用、嵌套已声明调用、原HCG保留与无残留。未执行solc；仅用于解析器健壮性的未知函数样例不称语言合法样例。

modifier审计把旧prefix-only阶段的 `control_dependence_edges=false` 重命名为 `legacy_prefix_profile_control_dependence_edges`，另记新版控制分析身份，避免被误读为最终图未加控制关系。

收尾审查发现新统一参数 `max_iterations` 最初只传scalar/state，已在新control wrapper内统一；默认100000保持原行为。audit记requested/effective值，未启用阶段None。低上限1回归验证整函数无残留回退，默认与原模板图和事实精确一致。

## 四任务实际重建

使用原作者固定HCG、原标签与已准备的512维inside_token；不是另用本地narrow标签。先从原HCG重新计算scalar，再状态/顺序和新版控制。输入均通过原manifest取得并核验SHA；最后再次核验源码未变。

| 任务 | 文件 | 节点 | 原边 | DATA_DEF_USE | STATE_DEF_USE | STATE_ACCESS_ORDER | CALL_BEFORE_WRITE | CONTROL_DEPENDENCE | 最终边 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 |142|18,312|19,267|3,561|9|1,573|1,109|3,086|28,605|
| 访问控制合约 |114|13,432|15,538|4,032|14|107|0|1,929|21,620|
| 重入节点 |71|12,036|11,710|1,894|4|1,507|1,102|2,421|18,638|
| 访问控制节点 |57|7,710|8,840|2,836|5|62|0|1,384|13,127|

四任务共用 `rebuilt/manifest.json`，各任务有独立hcg.gpickle、audit/inputs/manifest/comparison。累计四图构造计时342.09秒，非完整阶段墙钟时长。

全部通过：原节点及属性精确相同、原边精确保留、typed-edge重数相同、类型局部节点ID相同、canonical schema相同、实际DGL有序端点相同。

两个合约任务完整图fingerprint也相同。两个节点任务完整图fingerprint不同，仅 `ddg_fact_indices` 重编号，分别影响1885和2455条DATA_DEF_USE边；端点和关系没变。旧节点图继承先前流水线的事实编号，新入口仅遍历本任务文件重新编号。证据在 `rebuild_metadata_comparison.json`，不把这种差异隐瞒为文件字节相同。

最终默认control参数包装再对四图复算，图fingerprint全部精确一致，见 `final_default_control_check.json`。重建入口已补reference manifest seal启动核验；当前引用SHA与seal吻合。重建产物生成在该接口收尾之前，最终默认语义复核另存，未覆盖原audit或谎称所有产物由最终源码重跑。

**等价结论只说明模型输入未改变，不等于本轮重做训练，也不能改旧checkpoint的完整输入fingerprint来加载新图。** 旧结果留在旧runtime/输入绑定中；新图后续须使用自己的manifest。

## 有限Oracle

按源码身份/语义预先选定两个类别各6函数，selection与seal早于分析，未按标签、预测或涨分挑样本。

- 正例4：重入buggy_18.add标量→require、simple_dao.withdraw外部调用→状态写入；访问控制buggy_18.sendto_txorigin21控制约束→transfer、buggy_26.add标量→return。各1条预期事实且精确投影。
- 应无特定状态DU4：queryCredit、donate、DynamicPyramid、totalSupply；函数入口读或单次写/RMW不应凭空连成函数内先定义后使用。
- 应回退4：airDrop多modifier、approveAndCall的bytes memory、proxy.forward的delegatecall/bytes、name的string返回。均无部分不确定事实残留。

最终12/12符合预设。权威结果 `oracle/validation_v2/results.json` 及 `verification_receipt.json`。初版新Oracle substring误将函数入口全文当成目标语句而多计1事实，保留初版记录，仅修工具为精确语句匹配，并补回归；没换样本或修改预设。

审阅者Codex，未取得独立人工签署、未运行solc、未验证漏洞ground truth。有限样例不能外推成全语料正确性证明。

## 真实模型聚合诊断

CPU读取四任务fold0已经保存的未训练共同初值，optimizer_steps=0；不重初始化后假称相同，不用训练后E0参数。共同语义参数精确对齐，29个不同输入/初值/清单文件SHA前后相同。

A：原HCG；B：增强schema、五类新增relation_msg仅在内存置零；C：原增强初值。通过原HGT的a_linears前向钩子读取真实聚合张量，并记录两层隐藏表示与logit/margin。没有改HGT源码或保存被干预权重。

| 任务 | 有新增关系入边节点 | 无新增入边但分母改变 | 其中首层聚合实际改变 |
| --- | ---: | ---: | ---: |
| 重入合约 |5,571|6,879|6,056|
| 访问控制合约 |4,450|4,350|3,866|
| 重入节点 |3,776|4,655|3,945|
| 访问控制节点 |3,078|2,006|1,647|

四任务第一层均满足：B约等于A乘以“原入向canonical数/增强入向canonical数”，最大绝对误差9.5367e-7。重入expression_statement由18类入向canonical变为31，原消息会受到18/31缩放，即使某节点没有增强边。

这是实际模型的机制证据；第二层还包含传播，C−B还混有参数与聚合作用，不能称纯依赖语义的因果效应。这些是未训练初值诊断，不能声称已量出训练后DDG利用率、准确率变化或低收益的确定主因。诊断170.31秒；输出CSV/NPZ不报告F1。

诊断完成后补了孤立类型0/0应记ratio1的防御分支；真实四任务所有实际节点类型均有入向canonical，输出不受影响；执行/最终源码SHA和核查保留在post_run_edge_case_check.json。

## 验收及失败记录

- 定向receiver19项通过；接口初始21项通过；新增迭代上限11项；Oracle9项；archive3项；rebuild4项；诊断7项。新增共74项。
- 最终联合测试：**613 passed，0 failed/skipped，31 warnings，9.71秒**。其中旧相关测试539项；这是全部DDG相关目录和列出的项目接口回归，不冒称运行整个仓库所有测试。
- 原HGT真实CPU前向/反向测试覆盖node和contract，五关系均读取且取得监督梯度；训练未见关系不是必须强求非零梯度的情形，本测试特意提供关系支持。
- 首次新接口测试有Path夹具类型错误，仅修调用类型；首轮全套测试因两个test_projection.py同名收集冲突失败，改pytest调用为importlib，未删测试或放宽断言。旧日志保留。收尾后最终命令和日志在regression_003.log。
- 只读归档核验overall_cv：60个成功fit收据完整，689个记录文件身份吻合；checkpoint文件SHA核验，本轮未全部重载。未改旧plan/seal。
- 旧生产Python230个SHA保持；用户原auto_version_solc修改保留；两树训练变更与HANDOVER仅追加并核验原字节前缀。

重现命令集中见 [统一README](../../../integration/README.md)；路径也可直接使用 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/integration/README.md`。

## 当前结果与停止位置

历史mean/best主链HCG / full / full_guard：重入合约94.1593/94.1593/94.1593；访问控制合约93.5590/93.5590/93.5590；重入节点96.0580/96.1027/96.1210；访问控制节点95.9723/95.8887/95.9171。均为原CV validation，节点按HCG节点评分，非独立测试或去重源码行F1。

本轮工程收尾不会把这些数值变成稳定增益证据。正确关系确实接入、会改变消息，关系越多并不保证任务改善。受限state DU仅4/5条的现象也不等于实现错误；Oracle已说明入口读与单次写本来就没有函数内def-use。

本批结束于统一工程版、语义验收和诊断报告。保留mean，attention负结果仍归档；没有新正式训练、solc下载/编译、额外seed、七类扩展、跨函数摘要或新关系。若继续研究，最有依据的是单独定义并验证“在保留原HCG消息尺度时接入增量关系”的一个候选；这会改变聚合，须明确作为新方法与原HGT基线受控比较，不能伪装本轮bug修复，更不能预先保证F1上升。独立评估与独立人工语义复核仍缺。
