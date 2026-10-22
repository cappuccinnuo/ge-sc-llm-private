# DDG 当前能力矩阵与版本解释

日期：2026-10-19；审查与整理：Codex。工作树：`ge-sc-llm-ddg-v11`。这是现有源码的能力说明，不是新增算法或实验成绩。

## 1. 以实际实现为准

最初方案要求在原 CFG+CG HCG 的同一节点集合上增加直接定义—使用边，不新建变量图，不用标签决定连边。原方案文字说明第 11–27、39–45、65–77 行明确了这条主线。后续增加状态关系是分期扩展，不等于所有 Solidity 数据依赖都已实现。

| 能力 | 当前实现 | 边界或尚未完成部分 |
|---|---|---|
| 输入身份、原节点/标签/特征/基础边保持 | 已有图指纹、来源、初始化、checkpoint、receipt 绑定；Stage F materialize 保持原 E2 | 不等于确认公开标签的语义真值，也不能跨不同标签版本直接比较 |
| 声明与作用域身份 | symbol_table、call_binding；历史版本作用域及终止内建绑定保护 | 无完整 Solidity 类型系统；绑定不确定时按函数回退 |
| 标量 DEF/USE | 参数、显式标量声明与赋值、复合赋值、自增减、纯读取、显式 return | 元组的精确值对应/隐式返回值传递不能宣称完整；复杂表达式副作用受限 |
| 独立语义 CFG | 正向执行路径；分支、循环、终止；只作分析中间表示 | 不替换模型原 CFG/CG，不用模型反射边计算 reaching definitions |
| 标量 reaching definitions | KILL、分支 union、循环固定点；直接 Def–Use | 无 transitive closure；不是完整跨函数污点传播 |
| 状态位置 | 同源可明确绑定的状态标量、简单 mapping；受限继承和版本证据 | 非完整 storage slot、struct、array、复杂引用与别名分析 |
| 状态 reaching definitions | EXACT/MAY/UNKNOWN、入口未知、强/弱覆盖、调用 HAVOC | 只有符合投影规则的确定位置事实物化；入口未知不伪造为某个跨函数定义 |
| STATE_DEF_USE | 函数内到达写入→读取，要求状态位置证据 | 无跨交易/跨函数摘要；CFG 可达见证不等于 SMT 路径条件可满足证明 |
| STATE_ACCESS_ORDER | 同一状态位置的访问顺序及见证 | 是顺序关系，不是 Def–Use，也不自动表明漏洞 |
| EXTERNAL_CALL_BEFORE_STATE_WRITE | 支持范围内外部调用→后续状态写入顺序 | 两类顺序关系的联合实验不能区分各自单独贡献；访问控制固定图无此边 |
| 原 HCG 投影 | AST/预处理身份验证；精确端点；同关系同端点合并并保留事实侧表 | 缺原节点不能按最近行号猜；同节点事实不额外制造模型自环 |
| 模型接入 | Stage F 四关系保持正向；e23_pilot 使用原 HGT 核心并注册 canonical schema | 旧原训练入口直接运行可能误反射状态边；见 ENTRY_POINTS.md |
| 实验 | 两类漏洞、合约 5 折/节点 10 折、E2/E3a/E3b 完整单 seed CV validation | 未证明独立泛化或七类普遍收益；节点按 HCG 节点评分 |
| modifier / 控制依赖 | 当前遇 modifier invocation 回退；独立控制依赖未实现 | 候选后续工作，须先确认绑定、执行次序和可投影性 |
| 跨函数摘要 / 反向 DDG / 独立编码器 | 尚未实施的候选 | 不是本轮第 1、2 步必须实现的内容 |

主要源码证据：
- `scripts/DFG/symbol_table.py`、`access_extractor.py`、`semantic_cfg.py`、`reaching_definitions.py`、`projection.py`。
- `scripts/DFG/state/locations.py`、`access.py`、`reaching_definitions.py:8–21,43–71`。
- `scripts/DFG/state/stage_f/binding.py:7–48`、`analyzer.py:14–38,83–94`。
- `scripts/DFG/state/stage_f/projection.py:10–18,19–46,47–58`。
- `scripts/DFG/state/stage_f/model_adapter.py:4–21`、`experiments/e23_pilot/model.py:29–81`。

## 2. E 编号的历史变化

| 文档/实验阶段 | E0 | E1 | E2 | E3 / E3a / E3b |
|---|---|---|---|---|
| 原宏观 Code Design Guide，第 1730–1767 行 | 原 CFG+CG | 增加 DDG | 计划增加反向 DDG | E3 计划内部调用摘要 |
| 最初正式标量实验 | 固定原 HCG | 最初标量 DATA_DEF_USE | 不适用此阶段编号 | 不适用 |
| 后续 Stage G/H 已完成实验 | E0/E1只作历史参考 | 同左 | 修复版标量 DATA_DEF_USE | E3a=E2+STATE_DEF_USE；E3b=E3a+两类顺序关系 |

当前 Stage H 的 E2/E3 完成，**不能写成早期“反向 DDG/跨函数摘要”已完成**。当前四种增强关系均正向，不含 REV_DATA_DEF_USE。历史 E0/E1 初始化算法不同，只能作为注明条件的历史参照。

## 3. 当前结果允许得出的结论

完整 90 个模型结果见 `../artifacts/paper_kfold/stage_h2_v1/E2_E3_COMPLETE_ABLATION_REPORT.md`。合约 best 类别无变化，节点平均增益小且跨 best/last 不稳定。阶段覆盖记录中节点状态 Def–Use 很稀疏且集中于构造函数；“状态依赖少”和“状态依赖没有价值”不是同一结论。

下一步先审计现有关系是否覆盖真实行为、是否投影、能否通过实际消息方向到达目标，再做固定权重关系贡献干预。干预不改变标签、不重训，不等同于全量关系训练消融。不得据当前分数直接增加反向关系、改 HGT 或扩大到其余五类。

## 4. 本轮改动范围

本文件、ENTRY_POINTS.md、modifier_scope.md 和 entry_validation.py 是旁路说明/校验。原设计文档、原 README、冻结训练代码、输入图、label、token、fold、plan 与 seal 均不修改。
