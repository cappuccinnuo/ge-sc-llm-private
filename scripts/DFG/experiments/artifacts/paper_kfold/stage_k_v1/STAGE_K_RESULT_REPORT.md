# Stage K：整体DDG修复与成对单折训练结果

2026-10-19，实施与分析：Codex。工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。
批次：scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1。

## 结论

已完成版本域修复、四份增强图生成、两个节点任务固定fold0的四次正式训练，以及checkpoint/预测验收。工程接入有效，主结果尚未显示检测提升：重入Buggy-F1下降0.0583个百分点，访问控制持平。没有按小修复分别训练消融，没有改标签、挑折、换seed或调整模型求更高成绩。

## 改了什么

开放pragma如>=0.5.9被旧分析器解释为无限未来区间，而内建语义表只支持0.9.0之前，导致已知调用无法确认、函数回退或UNKNOWN_CALL HAVOC。新增state/stage_k/profile.py将“源码允许版本”与“分析器支持域”分开：先执行原版本/作用域/声明检查，再取[0.4.0,0.9.0)交集并完整记录证据。

没有指定假的solc版本，没有修改pragma，不要求编译成功；只在声明支持的区间内作静态分析。无法确定绑定、跨作用域版本或超出支持域仍回退。旧state/stage_f、stage_j和封存历史不改。受限继承/modifier恢复与本次修复合并为一个整体版本，核心逻辑与测试位于scripts/DFG/state/stage_k/。

## 对照定义

- **B0**：旧冻结E3b图，已有标量DDG及旧状态/顺序关系；不是完全无DDG的原MANDO。
- **B1**：冻结E2标量图加Stage J继承/modifier恢复，再加Stage K版本域修复后的状态关系。
- 两者从新鲜未训练初值开始，共同参数按语义对齐；不读取旧训练权重。B0不是直接复制H1的旧分数。
- 使用两个原固定node fold0。paper_kfold完整图前向、train mask监督，同val选模及评分。512维inside_token、原HGT、50epoch上限、patience7/delta0.001、原Adam/OneCycle、原标签/划分均不变。
- **全部为CV validation，计分单位HCG节点；不是独立测试或去重源码行指标。**

## 正式结果

| 任务 | checkpoint | B0 Buggy-F1 | B1 Buggy-F1 | 差值pp | B0 Macro-F1 | B1 Macro-F1 |
|---|---|---:|---:|---:|---:|---:|
| 重入节点 | best（主） | 99.6487 | 99.5904 | −0.0583 | 99.5195 | 99.4391 |
| 访问控制节点 | best（主） | 99.1119 | 99.1119 | 0 | 99.1635 | 99.1635 |
| 重入节点 | last | 99.6487 | 99.5904 | −0.0583 | 99.5195 | 99.4391 |
| 访问控制节点 | last | 99.1119 | 99.2883 | +0.1764 | 99.1635 | 99.3306 |

主best按最低val loss，不以访问控制更高的last替换。重入best多一个误报：buggy_28.sol原node17439；访问控制best没有类别变化。两任务所有验证节点的概率都改变；重入best平均绝对概率差0.01915，访问控制0.00094。last的重入新误报位于另一个节点buggy_47.sol/9332；相同F1不意味着完全相同的预测。

原固定fold0没有buggy_18/36/26等既有困难文件，本批不能判断它们是否被模型纠正。B0本身在这个折已99%以上，不能将单折分数直接与旧10折均值约96%或论文表格比较。

## 覆盖与训练支持

| 任务 | 节点/最终边 | 可分析函数J→K | 相对旧E3b新增边 | 其中本次版本修复新增 |
|---|---:|---:|---:|---:|
| 重入合约 | 18312/25519 | 2033→2189 | 1291 | 428 |
| 访问控制合约 | 13432/19691 | 2045→2058 | 77 | 7 |
| 重入节点 | 12036/16217 | 1372→1528 | 1234 | 428 |
| 访问控制节点 | 7710/11743 | 1482→1495 | 47 | 7 |

合约候选图已生成，但本轮没有合约训练。所有图保留原node_id、类型、源码映射、作者标签、token和CFG/CG边，也保留Stage J已有typed边；没有新增变量节点或反向关系。

本次版本修复主要增加顺序边，STATE_DEF_USE数量没有增加。重入历史425错误中有新上游上下文者从Stage J的6增至36；访问控制196历史错误仍0。该指标来自构图后的旧预测审计，不参与构图，也不等于本轮纠错。

重入B1的STATE_ACCESS_ORDER train/val为1292/215，调用→写入959/143；原B0分别711/118和457/90。访问控制B1的状态顺序58/4，原B0为12/4，新增状态关系全部在训练文件，本折验证结构未增加状态边。四fit的87个增强canonical均有训练支持并观察到有限非零message梯度，证明新边进入模型；不能由此推出预测必然变好。

## 测试、资源与保护

- 联合测试421通过、0失败/跳过，31条既有弃用警告；早期测试夹具错误及修正保留在日志和change_record.md。
- 四fit全部attempt_001，0失败/重试/OOM，8份best/last重载预测精确一致，指标从冻结标签独立复算一致。
- fit耗时合计648.27秒；最高allocated1761.38MiB、reserved1906MiB；整卡最低free65MiB。单GPU单模型串行，未改参数或代关程序。
- 重入两模型4559794参数；访问控制4592626→4600834，新增8208参数。关系schema/优化轨迹的变化也应计入解释。
- H1的60结果、H2的30结果只读归档核验通过。原197项代码/用户文件不变，训练变更文档与HANDOVER仅追加，未Git写操作。
- 未下载/执行新solc；静态语义测试不等于编译合法性验证。

## 接下来如何收束实验

当前可将这个整体修复版固定为候选，不必继续为每个小点单独训练。若要判断总体效果，后续只需完成B0/B1同一套原10折整体对照，保留本次fold0结果并按身份核验复用。单折没有提升，既不能宣称创新效果已成立，也不能据此否定整个DDG方向。

访问控制主要缺口仍是权限guard对敏感操作的控制约束，不能通过多加状态顺序边冒充已实现。复杂storage/别名/参数modifier/跨函数摘要也仍有限。本轮没有继续增加这些功能，没有运行剩余折、七类、新seed或独立测试。

## 文件与命令

- [逐项变更记录](change_record.md)
- [完整指标](results.csv)、[配对差值](paired_results.json)、[预测变化](prediction_changes.csv)
- [支持与梯度审计](training_audit.json)、[资源](resource_summary.csv)
- [构图统计](graph_summary.json)、[困难上下文覆盖](coverage_summary.json)
- prepared/<task>/B1.gpickle；runs/<task>/<B0或B1>/attempt_001/下的best.pt、last.pt、history、预测和收据。
- 代码与运行说明：scripts/DFG/experiments/stage_k_pilot/README.md。
- 既有docs/training_changes_2026-10-07.md第25节和HANDOVER.md已追加Codex记录。

现有mando环境，在开发树中：
~~~bash
export PYTHONPATH="$PWD"
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.experiments.stage_k_pilot.control verify
python -B -m scripts.DFG.experiments.stage_k_pilot.control summarize
~~~
prepare/run已执行，不需重训；prepare拒绝覆盖旧批次。未来HEAD变化仍应按归档方式核验，不能修改旧seal绕过。
