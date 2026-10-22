# 固定作者图上的下一阶段设计：完成 DDG v1，验证受限控制依赖增量

日期：2026-10-20。分析与记录：Codex。
开发树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11；核对 HEAD：021a6f55ac9e3f94fc70feb441ff48b51b6a92ea。
本轮是设计审查，未修改算法、图、标签、模型或训练；没有新训练、构图、GPU前向或测试执行。

## 1. 用户当前决策与方案边界

暂不追查作者与公共标注的差异。后续主实验继续固定已下载的作者CFG+CG图、原作者标签、现有512维inside_token、原文件折和训练规则。已发现的标注差异只保留为研究限制，不替换标签、不删除困难文件、不据作者标签或模型预测决定连边。

当前整体DDG已形成可运行的v1，不再以“尚未融合完成”为由重新实现DFG。它已包含DATA_DEF_USE、STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE四种正向关系，以及受限同源继承、前置modifier、版本支持域恢复。工程完成不等于完整Solidity依赖分析，也不等于分类收益已证实。

下一步推荐只评估一个整体候选：在冻结v1上增加受限CONTROL_DEPENDENCE。它属于DDG＋控制依赖/程序依赖增强，不是新的Def–Use关系。若研究命名必须严格限制为纯数据依赖，应收束v1，不能通过改名将控制依赖混入。

## 2. 本轮依据的完整结果

来自artifacts/paper_kfold/overall_cv_v1/OVERALL_CV_RESULT_REPORT.md；最低验证loss的best，CV validation，等权折均值，节点按HCG节点计分。

|任务|原HCG Buggy-F1|整体DDG Buggy-F1|差值pp|
|---|---:|---:|---:|
|重入合约5折|94.1593|94.1593|0|
|访问控制合约5折|93.5590|93.5590|0|
|重入节点10折|96.0580|96.1027|+0.0447|
|访问控制节点10折|95.9723|95.8887|-0.0837|

两个节点任务pooled OOF均略降；重入纠错33/新增错误34，访问控制纠错2/新增错误7。因此不宣称稳定提升。不能用接近99的单折代替全折结果，也不能与不同初始化的历史E2/E3b直接相减。

现有记录证明新增关系被HGT使用：668条有train支持的canonical×fold记录均有正message梯度；两个合约任务概率变化但类别不变。这不是本轮重新执行的测试。节点STATE_DEF_USE仅重入4条、访问控制5条；访问控制调用→状态写入边为0。关系覆盖有限且新增信息与主要错误重合少，是合理解释之一，不能确定为唯一原因。

## 3. 新增关系解决什么问题

例：require(msg.sender == owner); 后执行 recipient.transfer(amount)。条件读取owner，后续操作不必读写owner，因此两者未必存在同一状态位置的Def–Use或访问顺序关系。控制依赖表达的是后续语句的执行受到条件分支约束。原CFG可能已间接或直接连接它们，新增关系的价值必须分别统计：新端点连接、已有端点的新语义类型、缩短消息路径；不能把每条新增边都算成新上下文。

首版只新增一种正向CONTROL_DEPENDENCE，方向为控制条件→被控制语句。分支真/假、调用上下文、语义证据保存侧表；首版HGT不因此获得未接入的额外边特征，不宣称它能从同一种relation直接辨别分支极性。

通用规则覆盖已确认内建require/assert、普通if/else、提前return/revert及当前已支持的无参前置modifier。不能根据onlyOwner名称、漏洞类别、CSV或预测筛边。不把状态写入之前的所有条件都默认连边，不加入控制依赖传递闭包。

反例：if (ok) { x = 1; } y = 2; 中，x受ok分支控制，正常汇合后的y不应因此被连为直接控制依赖。require失败退出与普通if汇合必须区分。控制关系描述执行约束，并不单独证明授权正确或漏洞存在。

## 4. 真实源码差异及最小接入

本轮源码复核发现三个不能略过的接入问题：

1. scripts/DFG/semantic_cfg.py的if仅保存successors，require/assert仍是普通表达式；models.py的Block/FunctionIR没有统一EXIT、分支角色和完整控制锚点。原IR不应未经适配直接用于后支配控制依赖计算。新建旁路控制分析IR，显式记录正常/异常出口、条件分支和AST锚点，复用声明/版本/作用域证据。分析用虚拟EXIT不进入作者HCG，不改冻结DDG事实或模型中的CFG/CG。
2. state/stage_f/model_adapter.py的FORWARD_RELATIONS只识别现有四种增强关系，新关系直接走旧adapter会被当普通关系reflect。应新增最小旁路adapter/注册配置，保留旧实现，明确CONTROL_DEPENDENCE为正向；测试实际DGL canonical relation端点和HGT消息梯度。不能为了省接入把控制边伪装为STATE_DEF_USE。
3. experiments/overall_cv/common.py按当前整个scripts/DFG下的.py集合核验。新增旁路代码可能使旧control verify报Runtime drift，即使原训练文件没有变化。新增只读归档核验，应按旧plan列出的源码/输入/收据逐项验SHA并核对新候选复用的数值训练实现；不得改旧seal、忽略已有文件变化或仅用HEAD相同证明结果可复用。

建议新增目录（本轮尚未创建实现）：
- scripts/DFG/control_dependency/：分析IR、后支配/直接控制依赖、精确投影、融合、测试。
- scripts/DFG/experiments/guard_extension/：方向adapter、历史复用核验、初始化/计划绑定及调度。

原Projector和源码身份校验继续复用：条件和受控语句都须对应已有HCG节点；不按最近行号猜映射、不新增变量节点、不更改node_id、token或标签。同端点不同relation允许共存。

使用CFG后支配及显式分支计算直接控制依赖。对副作用短路、未知异常/调用绑定、不支持循环或modifier上下文，不为了覆盖强行解释。函数级回退仅放弃该函数本次新增控制关系，保留全部冻结HCG和v1 DDG，不残留部分新边、不删除样本。共享modifier节点的不同调用上下文保留证据，不串联成跨函数顺序；无法安全投影时记录回退。

## 5. 一次实现、一次语义验收，不逐小点训练

实现时先固定正反例：guard通过/失败、普通if汇合、提前返回、嵌套分支、同名非内建函数、已有受限modifier、缺失投影端点、未知控制流回退。断言包括正确/错误边、函数无残留、原节点/标签/特征/全部基础边和四类DDG逐项不变。

然后在重入与访问控制四个固定任务图上进行一次全量构图和覆盖统计：可分析/回退函数数、可投影控制边数、已有端点与新增端点数量、实际新增一/两跳上下文、每折train/val支持和新canonical关系数。样例语义核验不以模型预测或标签决定是否生成边，不开展新的标签重建。

语义或不变量失败先修正；若新候选没有可投影有效信息，则停止训练并报告。若通过，不以fold0的F1必须上涨作为后续折的准入条件。训练阶段仅按输入/数值/checkpoint/资源错误停止，不因某折下降挑折。

## 6. 训练只新增一个候选，复用条件先验收

保留三行可解释对照：
- HCG：作者原CFG+CG，无本地DDG；引用现有overall_cv结果。
- HCG_DDG：当前冻结Stage K四关系v1；引用现有overall_cv结果。
- HCG_DDG_GUARD：同一v1图增加受限CONTROL_DEPENDENCE；仅新候选需训练。

不得接着任何best/last训练。逐task/fold读取保存的HCG_DDG未训练初值，对共同节点类型和canonical关系按语义逐项复制和验tensor digest；真正新增关系单独确定性初始化。保持原fit_seed、监督、batch顺序、任务各自学习率/OneCycle、50轮上限、patience7/delta0.001和最低val loss选best。新schema多出的参数与聚合/优化变化也可能影响分数，差值不是纯依赖语义的因果估计。

旧基线复用须同时通过原图/标签/token/折/配置/共同初值/训练数值代码的绑定核验。若必须改变上述共同条件，不静默复用或自动重跑60次，先说明差异及所需实验变更。

条件满足时新增总数为2个漏洞×(合约5折＋节点10折)=30次fit。先四任务固定fold0共4次完成正式接入检查；通过的4次计入30，不重新训练。然后串行完成剩余26次，不为require、if、modifier各跑一套。合约级保留，即使当前持平也不删除该任务。

结果仍标记CV validation；best/last、等权折均值/pooled OOF分开，报告全部折、纠错/新增错误、关系支持/梯度及显存。已有RTX3050 4GiB余量较小，先预检，不自动缩图/降维/改层/切CPU。语义测试和验收不要求每个仅val出现关系有训练梯度，不在评分时建参。

## 7. 本轮暂不开展的路线及理由

- 不继续追作者标注，不改为本地narrow，不改变paper_kfold来追求更低或更高F1。
- 不先做跨函数/跨交易状态Def–Use：相同状态变量不等于一次写入确实到达另一次读取，仍需要可靠调用目标、参数/返回、上下文和别名摘要。当前普通调用HAVOC不能直接替代这些能力。
- 不加入反向关系、变量节点、LLM encoder、HGT新层或新分类头；避免同时改变多个来源而无法解释结果。
- 不把已审计的困难文件作为新的独立测试，不将本批结果宣称七类泛化。规则保持类别无关，但首批仍仅重入和访问控制。

## 8. 完成标准与停止点

工程完成标准：原作者资产不变；新增关系有可审查的执行约束语义；方向/投影/模型读取正确；一个统一入口和可复核实验报告。不是必须达到某个提升数值，也不是支持完整Solidity。

研究验证：主报告同时比较GUARD−DDG、GUARD−HCG，完整报告负结果。若这一个整体候选仍无稳定改善，就收束目前模块和局限，不自动继续堆关系或重复训练；更广类别、跨模板/独立评估或纯DDG跨函数摘要另立任务。

本轮只完成方案与文档记录，不创建执行授权，不启动新30次拟合。原60次结果和全部旧seal保持。

## 9. 参考依据与本轮核查

- Solidity 0.5.17控制结构/require异常：https://docs.soliditylang.org/en/v0.5.17/control-structures.html 。用于确认失败出口、调用异常和普通分支区别，不跨版本假设完整行为。
- Solidity 0.4.26 modifier：https://docs.soliditylang.org/en/v0.4.26/contracts.html#function-modifiers 。当前仅复用已支持的前置子集，不声称处理后缀/多占位符。
- LLVM/Clang ControlDependencyCalculator：https://clang.llvm.org/doxygen/classclang_1_1ControlDependencyCalculator.html 及官方Dominators.h。参考其CFGPostDomTree方法，不直接套用其语言前端。
- 本地：整体CV报告、next_step_review_v1/NEXT_STEP_DESIGN.md、Stage J/K设计与源码、overall_cv初始化与封存实现。并行只读审查复核了IR/关系方向/历史核验三个接口差异。

本轮未重复全套单元测试或加载图/权重执行模型；引用的梯度和预测验收是已有封存证据，不冒充新执行结果。