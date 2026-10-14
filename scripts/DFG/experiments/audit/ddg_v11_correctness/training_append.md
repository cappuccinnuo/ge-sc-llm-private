
## 16. 2026-10-13：冻结权重 DDG 原因诊断补记（修改 AI：Codex）

**16.1 时间、目的与历史边界**

本节补记上一轮已完成且已归档的诊断，不改写历史第15节。诊断执行时 HEAD 为3fb3fbcaed34c5c97976b570aac484935aa81484，随后用户归档到359a7f13d94fb2c7d8d5d4656d76a94a967e10e4。训练基646e9b3不变。历史input_audit/final_drift是当时的验收记录，不为当前HEAD重写。

新增内容全部位于scripts/DFG/experiments/audit/ddg_diagnostics_v1/。没有修改原DDG、HGT、tokenizer、训练器、标签、图、折、参数、早停和checkpoint。未重新训练，也未把固定权重置零诊断称为E0重新拟合。

**16.2 已新增代码及作用**

| 文件/组 | 作用与原因 |
|---|---|
| archive_audit.py、validate_runner_inputs.py | 按plan/state/receipt定位验收资产，原归档只读复核、保护摘要；不运行要求HEAD相等的formal verify |
| static_analysis.py | 冻结标量分析器内存重放，事实/投影/模型真实反射拓扑距离、错误覆盖和train-only重复统计 |
| posthoc_duplicate_strata.py | 按节点类型复核重复率，区分结构节点和表达式，标签只作事后分组 |
| interventions.py | 局部包装原forward；N等价、Z在两层跨关系聚合前置零实际DDG消息；恢复参数及图状态 |
| rewiring.py | 同文件/函数/canonical有向双边交换，保持度数与基础平行边；种子101/102/103 |
| diagnostic_common.py、run_diagnostics.py | 严格输入绑定、串行单模型GPU前向、一致性门槛、试点initial/best/last |
| aggregate_results.py | 从原ID对齐导出预测独立重算指标、混淆矩阵、翻转及消息概要 |
| write_report.py | 证据分级报告；不加载模型、不改变原成绩 |
| test_archive/test_runner/test_static/test_interventions/test_rewiring/test_runtime_compatibility/test_aggregate_results | 正常等价、Z语义、恢复、R约束、标签独立、指标重算和拒绝路径 |

记录与结果包括README、input_audit、coverage/edge_increment/sensitivity、rewiring_audit、message_norms、parameter_scales、representation_changes、case_studies、diagnostic_report及阶段日志。完整路径与大文件SHA已由后续归档写入docs/ddg_diagnostics_v1_local_assets.json。Git归档不等于完整本地大资产备份。

**16.3 实际诊断与结果**

全部30个配对折best完成；7个预定试点另测initial/last，共88次checkpoint状态评估。主观察使用原CV validation，节点单位为原HCG节点。N包装器与同设备原生forward逐位一致；归档概率使用预先声明的atol1e-6/rtol1e-5，未因失败放宽。

| 任务 | 正常E1 Buggy-F1 | 同权重DDG消息置零 | 分类翻转 |
|---|---:|---:|---:|
| 重入/合约 | 93.5157 | 92.8260 | 1/142 |
| 访问控制/合约 | 93.5590 | 93.5590 | 0/114 |
| 重入/节点 | 96.0740 | 96.0140 | 13/12036 |
| 访问控制/节点 | 95.8130 | 95.7955 | 1/7710 |

DDG参与计算，对部分预测有益，但未取得稳定E1−E0净收益。R全部种子无分类翻转，但节点任务通常8–9折没有val语义边扰动，不能据此判定依赖语义无用。节点DDG超出原两跳端点比例25.31%/10.22%；参数和入口来源占主导。状态、mapping内容、modifier和跨过程未覆盖。

节点正例stored-code在本折train精确重复率99.79%/99.03%，并有同文本异标签；这不是标签错误或泄漏的自动证明。总消息/残差范数不是普遍近零：节点两层约0.59–0.71、0.66–0.67；不能将首个弱消息试点外推全体。全4D bank Xavier与关系mean为候选机制，未完成因果分离。

**16.4 测试、失败和保护**

最终97 passed、0 failed、0 skipped、4条依赖弃用警告；独立重复分层210项一致性断言。5387份当时保护文件及HEAD未变。首次pilot因torch1.8 CUDA未初始化时查询显存失败，修复仅诊断脚本初始化顺序，旧失败目录保留，成功输出pilot_v2。静态统计初稿修正保留于draft_v1，不改原图或标签。没有solc安装/执行、模型训练、标签修订或状态分析实现。

**16.5 诊断后的决策**

先修复精确DOT投影与if/else注释两处确定缺陷并审计恢复量，同时核查难例上下文；不承诺增加边即可提高F1。这个建议在本节之后的新隔离版本实施，旧诊断目录保持不变。

## 17. 2026-10-13：DDG v1.1 正确性修复、D2上下文审查及D3设计（修改 AI：Codex）

**17.1 工作位置、版本和最小变更策略**

实际原HEAD=359a7f13d94fb2c7d8d5d4656d76a94a967e10e4，原已跟踪文件无未提交更改；已有未跟踪资产全部保留。新建detached worktree：
/home/zhao/SmartContract/ge-sc-llm-ddg-v11。
原业务代码仍为封存版本，不把新代码直接替换到原运行目录。原目录只按用户本轮授权追加本文件和HANDOVER，两份旧字节前缀保存并验证。没有commit/push/reset/pull。

新版本ddg-v1.1-correctness-fix；包版本0.1.1。主产物目录：
scripts/DFG/experiments/audit/ddg_v11_correctness/（在新worktree内）。
原图、源码、标签、token、checkpoint、receipt、plan/seal、折及原诊断都是只读输入。详细说明及实际命令见该目录README。

**17.2 核心修改：位置、旧行为、修复原因**

| 新worktree文件 | 旧行为/风险 | 新行为 |
|---|---|---|
| scripts/DFG/projection.py | 源码用Python literal_eval解码DOT；合法反斜杠源码投影失败，部分其他转义可能被错误接受 | 原文相等或与实际pydot.quote_if_necessary精确相等；保留AST ID/类型/端点/唯一性；对序列化物理多行字符串歧义保守拒绝 |
| scripts/DFG/semantic_cfg.py | 分支间comment被语法树标成body，旧第二body选中comment导致函数回退 | _if_bodies过滤直接子节点comment，严格验证condition/then/else数量与顺序；额外body、未知结构继续回退 |
| scripts/DFG/__init__.py | 0.1.0 | 0.1.1，明确新图来源 |

没有修改pipeline、access_extractor、symbol_table、reaching_definitions、HGT、tokenizer或原训练脚本。pydot的编码非完全单射：额外守卫针对解析器反例，不声称恢复了作者历史源码哈希。没有最近行、空白归一化或相似文本匹配。原始代码可在主工作树及Git起点读取，无需反向覆盖恢复。

**17.3 新增代码与测试位置**

| 位置 | 内容 |
|---|---|
| scripts/DFG/tests/test_projection_v11.py | 21项DOT正反向、锚点、歧义回归 |
| scripts/DFG/tests/test_semantic_cfg_v11.py | 25项分支/合流/KILL/终止/图不变量回归 |
| scripts/DFG/tests/test_semantic_cfg_conditions_v11.py | 6项条件注释与参数读取回归 |
| 新审计/protect_assets.py | 原资产前后摘要；新增文件检测；只允许两文档追加 |
| 新审计/coverage_rebuild.py | 从同一冻结E0用原/新代码重放，输出新图与事实差异 |
| 新审计/finalize_d1.py | 只允许3个核心差异、保留旧事实、逐事实恢复归因、D2门槛 |
| 新审计/test_audit_guards.py | 6项新增文件/非授权核心改动/伪造边事实的拒绝测试 |
| 新审计/context_design/context_audit.py及测试 | 精确文件/原nodeID/sourceSHA/作者标签/训练重复来源绑定，完整性错误不得降级成普通回退 |
| 新审计/context_design/文档和Oracle | D2语义审查、D3接口/状态位置/回退/实验设计；不执行状态分析算法 |

回归前后测试文件SHA一致。投影新测试原实现7失败/14通过，修复后加原投影测试30通过。语义新25测试原实现18失败/7通过；修复后通过，另6条件测试通过。不将Tree-sitter解析成功视为Solidity编译认证。

**17.4 四任务修复恢复量**

| 任务 | 支持函数 前→后 | 提取facts 前→后 | 投影facts 前→后 | DDG边 前→后 | 新边 | 新canonical |
|---|---:|---:|---:|---:|---:|---:|
| 重入/合约 | 2034→2035 | 5400→5415 | 4510→4822 | 3363→3561 | 198 | 0 |
| 重入/节点 | 1210→1210 | 2636→2636 | 2083→2380 | 1711→1894 | 183 | 2 |
| 访问控制/合约 | 2127→2128 | 6139→6145 | 5197→5624 | 3765→4032 | 267 | 0 |
| 访问控制/节点 | 1550→1550 | 4101→4101 | 3529→3858 | 2632→2836 | 204 | 1 |

投影失败文件3/3/5/2→0；前端文件回退6/2/12/2保持。注释修复恢复calculateTokens和getCurrentTokenPrice两个clean文件函数，所以节点任务函数和提取facts不变，仅投影恢复。

旧DDG端点/canonical/事实全部保留，0删除；原节点、ID、类型、标签、token、源码映射和基础多重边/key完全相同。DDG语义未变文件138/142、68/71、108/114、55/57；不包括新版本号和全局事实索引元数据必须逐字节相同的承诺。

新增边有原AST锚点与definition/use证据。文件级回退标签与逐事实恢复原因分开，详见D1_RECOVERY_ATTRIBUTION。独立审查后补强新增资产检查；没有用“只查旧文件哈希”代替完整保护范围的新文件检测。

新图：
after/reentrancy_author/E2_contract.gpickle、E2_node.gpickle；
after/access_control_author/E2_contract.gpickle、E2_node.gpickle。
E0引用原prepared，不重复生成。新schema和SHA见D1_PROVENANCE；未创建新训练plan，不改旧seal。E2节点canonical增加，不能认为参数量必然与E1相同。

**17.5 D2真实案例与标签边界**

核查12个原验证节点，绑定原作者图标签、sourceSHA、AST原行号、完整函数与旧E0/E1 best预测；追溯480个训练重复节点，447个得到完整精确函数上下文，33个因已知多pragma等前端限制记录为D级未回映。源码SHA或图身份错误会中止，而非吞掉。

D2只使用修复Projector建立源码对应；DDG覆盖、标签、预测仍来自封存E1，不把新E2边与旧预测混合解释。全部标签原样保留。

确认的代表性情况：
- R buggy_18外部调用节点2706作者标签0、公共CSV范围覆盖，同文本37个train节点全为1；这说明标签上下文/构造口径有疑问，不能由FP直接宣布标签错误。
- R buggy_18的send节点2675已有参数DDG但仍FN；R buggy_36乘法节点5961有DDG且E1纠正；另有无直接DDG路径却新增错误或被纠正的节点。
- mapping_write.sol的map是uint256[]数组，不是mapping；arbitrary_location_write_simple的公开标注行27对应长度检查而非直接行28自减。
- AC buggy_18/26部分owner_txoriginXX是参数，现有DDG已覆盖；不能把这批错误全归因于缺状态owner。
- AC26的to.call.value(amount);没有最终调用括号，不擅自叙述成已发生ETH转账。
- 有些纯算术节点已有完整局部依赖仍误判；modifier权限控制也不等价于state DEF→USE。

D2_CONTEXT_REVIEW、D2_CASE_AUDIT、D2_LABEL_AMBIGUITY、D2_MISSING_DEPENDENCIES及全函数证据保存在context_design。证据区分A身份/图事实、B语义解释、C标注歧义、D材料/映射不足。没有正式人工漏洞认证，也不根据预测重标注。

**17.6 D3方案：只设计，不实现**

采用源码声明与作用域身份的Storage-location abstraction，不伪称精确EVM slot。不用同名变量或相同键文本判断位置：mapping键关联局部定义版本、类型常量或调用帧内已确认builtin；MUST位置身份与may-reaching路径事实分开。

最小原型先支持直接声明的标量状态与可证明位置的简单mapping键。ENTRY_UNKNOWN和外部调用HAVOC从第一版就必须有；未知调用/别名不能保留不合理的强定义。强KILL仅用于确定单一位置；弱更新、分支union、循环fixpoint与未投影写入仍覆盖必须测试。state回退保留原HCG与标量DDG，不提交部分不可信状态边。

原HCG不加变量/状态节点。拟用独立StateFunctionIR旁表引用原分析CFG，不替换模型CFG/CG。提议STATE_DEF_USE与标量DATA_DEF_USE语义分开；require对敏感写入是控制约束，modifier执行另立项；同位置先读后写、回调/调用事件不是传统def-use。

特别是入口余额读取→外部调用→余额清零，后面的写不能倒连成前面读的definition；仅增加函数内state DEF→USE可能合法地新增0条边。应先用Oracle检查真实信息增量再决定是否实现更广关系，不能为了增加边数改语义。

未来E0原HCG、E1封存标量、E2正确性修复、E3经Oracle验收的状态增强、E4单独融合/初始化；同标签/折/特征/训练规则，共同参数按语义对齐，记录新canonical和参数量。paper_kfold结果仍称CV validation；跨模板/独立测试仅旁路。本轮不运行这些实验。

**17.7 验证、环境修正、保护和停止点**

第一次全量372通过/18失败：17个为worktree缺失硬编码本地语法库，1个为原绝对路径资源绑定。复制已有库且SHA相同，路径测试在原目录执行，其实现/断言不变。保留第一次失败日志，不改旧资源或测试期望。

正式分区回归389通过（1项另跑）+原目录1通过；后续审计/context19通过，其中10项与主回归重复，因此399个不同测试通过。无最终失败或跳过；警告为依赖弃用。完整实际命令、返回码与日志在新审计JSON内；单元测试中的合成模型检查不是新Dataset A拟合。

原归档reporter先验收4任务完成/0待办。6217个既有保护文件前后摘要以及原目录新增文件检测由protected_before/after记录；仅两份文档追加是明确授权例外，保留旧前缀。修改版core diff check通过。未进行solc编译、安装升级、真实模型训练或新状态算法。

后续只有在正确性、Oracle、边来源/未知覆盖和新schema验收后，才应另建E2/E3训练计划。本轮结束于新图审计和设计报告，不能声称F1提高。

D2最终完整性：918项源码字节跨度与121项原输入SHA核验通过。D3交付9个真实函数候选Oracle和5个合成规格；独立人工批准和编译验证数均为0。
