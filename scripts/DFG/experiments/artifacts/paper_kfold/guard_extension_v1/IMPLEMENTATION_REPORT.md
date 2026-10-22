# 作者HCG＋整体DDG＋受限控制依赖：实现与验收

日期：2026-10-20。实施、审查与记录：Codex。工作树ge-sc-llm-ddg-v11，HEAD 021a6f55ac9e3f94fc70feb441ff48b51b6a92ea。

## 本批边界

本批在作者图及冻结Stage K四关系整体DDG上追加CONTROL_DEPENDENCE；这是DDG＋控制依赖，不是纯Def–Use扩展。作者node_id、节点属性、token、标签、源码位置和全部CFG/CG/四类旧DDG边保持不变。不重新标注、不重建作者原图、不改变HGT核心和原数值训练规则。当前user要求继续完成推荐阶段；主结果仍CV validation，节点按HCG节点计分。

## 新实现

- scripts/DFG/control_dependency/models.py、cfg.py、analysis.py：独立控制分析IR，已绑定guard、if、提前退出、现有受限前置modifier；正常/异常/统一出口仅为分析虚拟节点。后支配计算直接控制依赖，无传递闭包。明确true/false裁剪不可达分支。函数级不支持回退无部分新fact。
- 同目录projection.py、pipeline.py：复用精确AST源码投影；不猜最近行，不新增模型节点。缺失revert/emit锚点仍保留语义CFG，仅不发布对应边；同端点不同relation可共存，同控制关系去重并保存上下文证据。
- experiments/guard_extension/：真实图构建、正向adapter、基于旧plan清单的只读归档校验、保存初值扩展、新批次绑定及30次候选调度。原训练FIT函数code对象复用，只替换方向/审计/checkpoint绑定。旧60fit不重训、不改seal。

## 测试与失败记录

原DDG语义、模型/项目回归413通过，31条既有弃用警告。新增统一语义/投影/实验测试73通过，4条既有DGL弃用警告，最终0失败/跳过；合计486个用例。对应old_semantic_model_regression_001.log及new_integration_tests_002.log。

新增统一测试001曾72通过1失败：summary把字符串传入需要Path的safe_graph reader，修正新report调用后全部通过，断言未放宽；001日志保留。语义早期失败揭示既有grammar将未加括号 !msg.sender.send(amount) 错误分组，当前明确回退，该形式未恢复支持；加括号形式保留正向控制边断言。原始stdout未保存，此项为执行观察记录，见[semantic_implementation_notes.json](../../guard_extension_v1/semantic_implementation_notes.json)。投影初次因未设置TREE_SITTER_LIB_DIR加载旧Windows库失败，采用项目已有Linux库后通过，无依赖升级。

没有执行solc或EVM验证，解析/静态语义测试不等于编译或漏洞利用验证。

## 真实图验收

|任务|原节点数不变|冻结DDG边数|新增控制边|增强总边|新增两层可达对|新上下文目标节点|
|---|---:|---:|---:|---:|---:|---:|
|重入合约|18312|25519|3086|28605|1690|1132|
|访问控制合约|13432|19691|1929|21620|1096|600|
|重入节点|12036|16217|2421|18638|999|745|
|访问控制节点|7710|11743|1384|13127|464|248|

两层统计以实际model adapter边张量为准，普通关系按原规则反射，全部增强关系保持正向。每图8种新canonical；全部30折的新canonical都有train支持。语义支持/回退函数分别2325/1063、2264/779、1560/485、1636/322；合约任务2/6文件整体回退仍原样保留，节点任务无文件级回退。

投影缺失事实798/134/730/60，均因原图无独立revert或emit节点。不能因此删除语义退出、按最近行映射或替换作者图。困难文件已有新边：重入buggy18为74、simple_dao为2；访问控制buggy18为37、buggy26为29、parity_wallet_bug_2仍0。这是上下文覆盖，不代表预测改善。

## 训练条件与状态

旧60fit的封存源文件、固定资产和收据只读核验通过。新批次从保存的HCG_DDG optimizer_steps=0初值扩展，所有共同参数按语义逐tensor核对；新控制关系独立确定性初始化。四任务保留各自原学习率/OneCycle、fit_seed、50轮上限、patience7/delta0.001与严格最低val loss的best；last分开。成功fold核验复用，失败保留且停止，不自动重试/缩图/改超参/换CPU。

训练状态将在正式fold0和完整结果验收后另写结果报告；本实施记录不预报分数。首轮4任务fold0计入30候选拟合，旧HCG/HCG_DDG各30结果只读引用。

## 范围限制

当前为显式控制依赖子集，不处理隐式VM异常、循环/发散、完整modifier、跨函数终止摘要或不可靠调用绑定。已确定普通调用使用保守返回/异常出口，不因此宣称完整调用语义。条件真假证据在sidecar，HGT仅接收一种CONTROL_DEPENDENCE关系，不宣称已输入分支极性特征。不能把新增参数/聚合/优化造成的差值全部解释为纯控制语义的因果贡献。

当前完整支持七类或稳定收益均未被证明；标签争议暂保留限制，不影响本批固定作者资产上的可比较性。

## 完整实验补充入口（2026-10-20，Codex）

上述为实施时快照，保持原记录。30次候选及60次旧基线引用现已完成联合验收，正式结论、限制、错误变化与资源见[RESULT_REPORT.md](RESULT_REPORT.md)和[RESULT_TABLES.md](RESULT_TABLES.md)。没有改写历史状态为预先已知结果。
