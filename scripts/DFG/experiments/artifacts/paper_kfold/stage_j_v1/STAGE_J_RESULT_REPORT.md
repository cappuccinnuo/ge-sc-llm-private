# Stage J：DDG整体构图模块与覆盖恢复验收

时间：2026-10-19；实现、测试、分析：Codex。开发树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`；HEAD保持 `021a6f55ac9e3f94fc70feb441ff48b51b6a92ea`。本批没有新模型训练。

## 1. 已完成什么

已形成可运行的“源码/版本身份→声明与作用域→独立语义CFG→标量与状态事实→精确原HCG投影→多关系融合→schema与模型接口→配置、CLI和审计”闭环。

新增核心在 `scripts/DFG/state/stage_j/`；真实数据入口在 `scripts/DFG/experiments/stage_j_coverage/`。新增受限同源C3继承及前置modifier恢复；原成功函数分析直接复用，只重试原回退函数。保留原节点集合、node ID、源码映射、token、作者标签、CFG/CG及冻结E2标量边。

这相当于在同一语句节点空间融合CFG、CG和数据依赖关系；不是新增变量图，也不是三个图编码器分别学习后拼接。两阶段任务和HGT不变。对原HCG开启add_scalar复用原标量构图；本批输入为冻结E2，不重建标量边。

四种增强关系仍是 DATA_DEF_USE、STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE。没有加反向或控制依赖。

## 2. 真实图结果

从冻结e23输入manifest取得图、源文件和标签版本；为四任务分别生成 frozen / inheritance / modifiers，共12图。frozen与旧E3b的状态关系集合完全一致；后两组没有丢失上一组关系。所有基础图指纹和实际DGL正向计数检查通过。

下表对比frozen与modifiers。恢复函数为原函数级回退变成可分析子集，并不表示函数含有新依赖或全部Solidity语义已支持。

| 任务 | 文件/节点 | 可分析函数：前→后 | 恢复函数（其中运行时） | 新增关系 | 有新增上游节点上下文的目标 |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 142 / 18,312 | 1,316→2,033 | 717（700） | 863 | 464 |
| 访问控制合约 | 114 / 13,432 | 1,299→2,045 | 746（738） | 70 | 123 |
| 重入节点 | 71 / 12,036 | 899→1,372 | 473（470） | 806 | 415 |
| 访问控制节点 | 57 / 7,710 | 965→1,482 | 517（514） | 40 | 89 |

最终三种状态关系数量：

| 任务 | STATE_DEF_USE | STATE_ACCESS_ORDER | EXTERNAL_CALL_BEFORE_STATE_WRITE |
|---|---:|---:|---:|
| 重入合约 | 9 | 1,388 | 866 |
| 访问控制合约 | 14 | 100 | 0 |
| 重入节点 | 4 | 1,322 | 859 |
| 访问控制节点 | 5 | 55 | 0 |

仅继承恢复已经贡献重入节点773条新增关系；再加入modifier增加33条。访问控制节点对应7条和33条。因此模块确实恢复了此前未分析的路径，但主要增长仍在顺序关系。两个节点任务新增加的各1条STATE_DEF_USE均在buggy_16构造器，不能宣称已解决运行时状态Def–Use稀疏问题。

本批四任务可分析前端中的函数总体为3388/3043/2045/1958，与accepted F1结果逐文件完全一致。旧Stage I静态表3404/3148多出的16/105条，是2/6个版本证据不足或跨作用域版本边界文件中的file_fallback记录，未进入函数分析。对应文件及节点一直保留；见function_population_note.json。报告不混用这两个分母。

## 3. 与已知错误是否重合

这部分只将历史E2/E3b的best CV validation预测与新图结构对齐，不产生新预测。严格按task、file、sourceSHA、原nodeID及原target核对，不用CSV行序。标签只用于构图完成后的审计。

| 节点任务 | 旧E3b错误 | 进入新增边两层局部范围 | 真正增加上游节点身份上下文 |
|---|---:|---:|---:|
| 重入 | 425 | 39 | 6 |
| 访问控制 | 196 | 0 | 0 |

以旧E2为参照则重入439个错误中39个在局部范围内、8个有新上下文；访问控制206个错误均在范围外。新增边即使不带来新上游节点，也可能改变关系语义和聚合；反之结构覆盖不保证纠错。新增canonical schema与共享参数训练还可能影响局部范围之外，不能将此表当作收益上下界。

困难文件：
- 重入buggy_18：新增17条关系、恢复18函数；原275个错误中37个进入局部范围，6个增加上游上下文。
- 重入buggy_36：新增12条关系；原58个错误均未增加局部范围覆盖。
- 访问控制buggy_18、buggy_26：分别恢复33/30函数，但未增加模型状态关系，原94/42个错误仍未覆盖。

这说明恢复绑定瓶颈合理，但“让更多函数可分析”与“为困难错误提供有效新信息”是两步不同的验收。

## 4. 源码证据抽查

以下为Codex对导出的源码/声明/路径证据核对，不宣称独立人工Oracle或编译验证。

- 重入buggy_18，SHA前缀b9e23563，claimReward_re_ent18：第249行读取redeemableEther_re_ent18[msg.sender]，第251行清零。新增STATE_ACCESS_ORDER从node2778到2780；后者是旧错误并获得1个新上游节点。没有把后续清零倒连为之前读取的定义。
- 两类buggy_16不是同一源码：重入SHA前缀52d8e426，访问控制01c1a4b4。构造器_totalSupply赋值→balances[owner]读取_totalSupply各恢复1条STATE_DEF_USE，端点原本已近邻。
- 访问控制buggy_17，SHA前缀78816048：onlyOwner第63行require读取owner，transferOwnership第68行写owner，新增STATE_ACCESS_ORDER node11954→11957。这是同状态位置访问顺序，不是权限控制依赖，目标原本预测正确。

完整新边证据在opportunity_v2/new_edge_cases.json，含函数ID、源码SHA、原始行号、源语句、声明、CFG见证、原nodeID；函数回退原因在remaining_fallbacks.csv。

## 5. 测试与历史保护

| 核验 | 实际结果 |
|---|---|
| 新Stage J回归 | 54项，包含在下行总数中 |
| 原标量/状态/Stage F/Stage J DDG测试 | 377通过，0失败/跳过，28条既有DGL/NetworkX弃用警告 |
| 原项目tests | 25通过，0失败/跳过，7条既有TensorBoard/DGL/NetworkX弃用警告 |
| 四任务三模式真实图 | 12/12生成并通过SHA、不变量、schema方向、旧关系复现检查 |
| 原HGTLayer合成接口 | 真实前向/反向有限非零关系梯度及checkpoint重载通过，optimizer_steps=0 |
| H1只读归档 | 52新+8复用=60完整 |
| H2只读归档 | 26新+4复用=30完整 |

首次DDG全套收集出现同名test_pipeline模块冲突，给新增tests目录补__init__.py后377项通过，没有删除/放宽断言。后处理v1在混合合约/节点CSV写表时列集不一致；保留失败脚本/日志，v2采用列并集生成独立目录，没有改变统计或图。

原有183项代码/用户文件保持SHA；两工作树4份文档仅追加。原用户auto_version_solc.py保持SHA bf3365c32f65f4c51932478eb54687a53c6aaad932f8f56a4d58687aaa493f31。最终详见protected_after.json与delivery_manifest.json。无Git写操作；旧图、checkpoint、plan/seal未覆盖。

## 6. 交付与使用

- 整体入口与参数：scripts/DFG/state/stage_j/README.md。
- 详细设计/限制：同目录DESIGN_AND_ACCEPTANCE.md。
- 四任务实际运行命令：scripts/DFG/experiments/stage_j_coverage/README.md。
- 图：本批build/<task_id>/<frozen|inheritance|modifiers>/enhanced.gpickle。
- 每图audit.json、manifest.json；批次plan/seal、输入摘要及receipt.json。
- summary.csv、files.csv、functions.csv与opportunity_v2错误覆盖审计。
- 两工作树training_changes第24节与HANDOVER追加Codex记录。

状态增强图必须用四关系正向adapter。旧通用训练入口可能反射状态边，不可直接替换旧训练文件；现有e23模型接口已具备适配，但新训练仍须独立图SHA/schema/初始化计划绑定。此处没有启动新的fold0或完整K折。

## 7. 剩余限制与下一步

已完成有明确边界的构图模块，不是完整Solidity DDG。保守回退仍包括复杂storage/数组/struct、重载和import解析、带参数/多重/后缀modifier、未知版本绑定、跨函数/交易摘要及完整路径条件。当前未实现CONTROL_DEPENDENCE，也没有凭onlyOwner名称添加边。

新增源码与图规则无漏洞类别分支，具备复用于其他类别的接口；实际数据只验收重入和访问控制，不能据此断言七类都有覆盖或检测收益。

更有依据的下一步是先审查新modifier与顺序事实、困难函数的剩余缺口；若进行效果实验，应冻结新的候选图版本、固定原划分和共同初始化，先单折短检查。访问控制的主要错误没有被新状态关系触及，独立权限控制依赖值得先做小型语义Oracle，不应为追求边数伪造STATE_DEF_USE。本轮没有正式训练，故没有新的F1或泛化结论。

未执行solc编译（遵守不下载/执行新外部编译器的约束）、七类全量构图、GPU正式训练、反向关系或新模型扩展。新增Solidity夹具属于解析/静态语义测试。
