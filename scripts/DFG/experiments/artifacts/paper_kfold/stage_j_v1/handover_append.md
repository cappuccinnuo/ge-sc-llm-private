

## 2026-10-19 Stage J：DDG整体构图入口与受限覆盖恢复（Codex）

- 已完成源码绑定→语义CFG→标量/状态事实→原HCG精确投影→多关系融合→schema/配置/审计的旁路入口。新增代码在开发树scripts/DFG/state/stage_j/，批量入口experiments/stage_j_coverage/。原DDG/Stage F、HGT、tokenizer、训练器、作者标签和旧实验均不修改。
- 本次新增同源唯一基类/C3多继承及菱形校验、一个无参数且末尾单占位符的前置modifier。只重试原回退函数，原成功分析复用；未知函数无部分事实残留，原样本保留。不支持完整modifier/复杂storage/import/跨函数/控制依赖。
- Stage I文档“modifier尚未实现”是此前快照；现在Stage J仅实现上述受限子集，旧入口默认行为仍不改变。标量DDG范围未扩展，本批冻结E2边保留。四类增强关系保持正向，没有新节点/反向边。
- stage_j_v1/build已生成四任务×frozen/inheritance/modifiers共12图。基线状态关系完全复现旧E3b，基础节点/属性/标签/token/CFG/CG不变。恢复函数：重入合约717、访问控制合约746、重入节点473、访问控制节点517；新增状态关系分别863/70/806/40。
- 新增运行时覆盖不等于性能改善：重入旧E3b 425错误中39进入新边两层范围、6有新上游节点；访问控制196旧错误仍均在范围外。新增节点STATE_DEF_USE各1条仍在构造器。没有新预测/F1，没有新训练。
- 真实例子：onlyOwner中require读取owner→函数体写owner可生成STATE_ACCESS_ORDER，不能声称已实现权限控制依赖。重入buggy_18恢复了部分顺序上下文，buggy_36和访问控制两个困难文件主要错误仍未覆盖。完整证据见opportunity_v2。
- DDG语义/集成377项通过（含新增54），原项目25项通过；H1 60/H2 30历史归档通过。首次pytest收集同名模块问题及后处理混合CSV列问题均记录并修复，旧失败日志保留。未做solc编译，测试解析成功不等于编译通过。
- 文档：state/stage_j/README.md、DESIGN_AND_ACCEPTANCE.md、stage_j_coverage/README.md；结果：artifacts/paper_kfold/stage_j_v1/STAGE_J_RESULT_REPORT.md。详细变更见training_changes第24节。图在build/<task>/<mode>/enhanced.gpickle。
- 旧通用训练加载器不保证状态边方向，不直接套train_node/train_contractlevel；原e23适配可复用但新图需独立计划、schema和初始化绑定。关闭DDG精确复制输入，恢复baseline要传原baseline图。
- 183项原代码/用户文件SHA不变，文档仅追加；原auto_version_solc.py用户修改保留。开发HEAD仍021a6f55，未Git写操作、未自动训练或扩七类。保护/交付清单见同批JSON。实施、审查与分析AI：Codex。
