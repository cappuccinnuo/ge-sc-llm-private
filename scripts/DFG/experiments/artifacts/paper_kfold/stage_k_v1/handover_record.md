
## 2026-10-19 Stage K：版本域修复及整体DDG单折训练完成（Codex）

- 已按用户要求将修复和整体实验直接落地，不为每个小恢复点分别训练。开发树仍ge-sc-llm-ddg-v11/021a6f55；新增核心state/stage_k/，实验入口experiments/stage_k_pilot/，独立批次artifacts/paper_kfold/stage_k_v1。旧DDG/Stage F/J、HGT、tokenizer、标签、原训练脚本和旧seal不改。
- 修复开放pragma导致“无限未来版本无法确认内建调用”的覆盖瓶颈。先原有版本/声明/作用域检查，再与分析器声明的[0.4.0,0.9.0)取交集并记完整证据；不伪造solc版本、不改源码、不要求编译成功。未知绑定/跨作用域版本仍回退，此修复是状态前端旁路。
- 四任务新图已生成；相对Stage J新增重入合约/节点各428边、访问控制各7边。最终相对旧E3b新增1291/77/1234/47边。原nodeID/标签/特征/基础边不变。节点STATE_DEF_USE仍4/5，版本修复主要增加顺序关系。
- 完成两个节点任务原fold0各B0/B1，共4次新正式训练，均attempt_001、0失败/重试/OOM。B0=旧E3b图重新成对初始化，不是无DDG原MANDO或H1旧分数；B1=Stage J整体恢复＋K版本修复。原512维特征、HGT、学习率、早停、best规则和划分不变，结果均CV validation/HCG节点口径。
- best：重入BF1 99.6487→99.5904（−0.0583pp），MF1 99.5195→99.4391；访问控制BF1 99.1119、MF1 99.1635均持平。last访问控制BF1 99.1119→99.2883，但不能取代主best。重入best新增1误报，访问控制best类别完全相同；主要仍是概率变化。
- 重入历史错误的新上下文覆盖6→36；访问控制仍0。本折不包含既有困难文件，不能声称已纠错。访问控制新增状态边都在train，val状态边数未增。87项增强canonical有训练支持且观察到非零有限message梯度；8 checkpoint重载及独立指标复算通过。
- 联合421测试通过、31条既有警告；H1 60/H2 30归档通过。4fit耗时合计648.27秒，最大allocated1761.38MiB，最低整卡free65MiB；未改配置、切CPU或关闭用户程序。未执行solc编译。
- 主要报告STAGE_K_RESULT_REPORT.md，完整结果results.csv，训练支持training_audit.json，逐条修改见两树training_changes第25节。旧197项代码/用户文件SHA不变，文档仅追加；原auto_version_solc.py用户修改保留。
- 当前整体方案已可运行，但单折主结果未显示提升。后续若继续评估，做固定整体B0/B1原10折对照即可，不需要每个小点单独消融；本轮没有自动启动剩余折、七类、更多seed或控制依赖。修改、执行与分析AI：Codex。
