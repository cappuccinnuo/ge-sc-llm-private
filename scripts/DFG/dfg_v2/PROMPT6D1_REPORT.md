# Prompt 6d.1：语句级计数、全量分类和实证复核

实施与复核：Codex。记录时间：2026-10-25 14:15 UTC。起始分支 dfg-v2，HEAD 2e7d21554521cc81a06e815f708b035198b01e77；git pull --ff-only origin dfg-v2 返回已最新。已先阅读更新后的 §4.1 及 Prompt 6d.1；Prompt 6b 复用已完成结果，不重复实现。

## 结论与验收边界

本轮完成规定的验证工具修改、六例直接实证、旧172条重分类、剩余other全查及五类各5条抽查。**没有新确认的 v2_defect，分析器和已有图未修改；这不等于全部DDG语义已经证明正确。**

L2单位修正消除了255条能够明确追溯到“同语句重复计数”的旧FP：重入135、访问控制120。773条旧other由255条已解决重复、517条新机械判据和1条仍未解释的rubixi状态循环组成。全部13,553条当前差异有机械分类；规定的剩余other已查1/1，未查other为0，但该1条判定仍是unclear。

合并旧重分类、剩余other、新判据样例共198条审阅记录，包含不同审阅目的对同一事件的重复记录：60 comparator_artifact、50 v2_scope_limit、72 slither_convention、16 unclear、0 v2_defect。16条unclear对应15个独立差异身份。另有76条绑定差异独立逐条核验。当前13,553条差异中，去重后203条做过逐条审阅，**13,350条未逐条语义判定**；五类新判据517条中126条已逐条查看，391条只做了机械分类。不得把“other清空到仅1条”写成“全部差异均已人工验证”。

固定图存储继续为 graphs_v2_r1/store.json，是后续Prompt7/8的固定输入，不创建新图版本。但当前审查状态为 unresolved_analyst_findings，仍有下述证据缺口；未自动开始Prompt7/8或训练，也未宣称无争议语义验收。

## 实际改动

- slither_units.py：仅验证端将L2按(文件、Unit语句跨度/角色、callable、变量名、READ/WRITE)归并；同键不同声明报错。保留全部词法出现、原证据及旧ID→新Unit映射。优先语句区间，必要时用statement与occurrence并集回退；缺statement不猜最近节点。
- slither_align.py：v4.2复用封存6c输出，L1仍为IR事件；L2参考仍是Slither CFG节点的变量集合。保留v3指标并重放原FP身份，区分重复归并和跨度匹配变化；集成新类别和绑定原因。旧v3版本、同一6c报告SHA、store、源码、实证及seal均校验。
- slither_patterns.py：五类精确AST/声明谓词；不按变量名直接判断。只在旧类别未命中时应用；L1/L2循环实证独立门控。suggested_verdict仅是机械建议，不能替代审阅结果。
- slither_review.py：保留旧v1读取；新增prepare-followup和五类verdict。独立冻结旧重分类、剩余other及每谓词5例。绑定完整事件/邻近证据/源码SHA/旧判定；scope需文档原句，convention需固定探针JSON定位，已解决artifact需新报告精确映射。
- slither_conventions.py及convention_cases/：六个固定手写文件，已有可信solc 0.5.11，保存Slither 0.8.0节点集合、IR/SSA、源码与编译器摘要。
- 新增三份测试：test_slither_units、test_slither_patterns、test_slither_conventions；扩展test_slither_review。
- 本报告和三份历史文档只新增/追加。本轮未改L1/L2/L3、pipeline、HGT、tokenizer、标签、fold、训练脚本或旧报告/人工边表。

没有采用需要替换用户设计的方案；发现的两个工具错误在本轮允许的比较器范围内修复。原批准选择继续保留，没有执行新的分析范围扩展。

## 单位修正前后指标

下表是**读写事件集合一致性，不是Buggy-F1，不是DDG边precision/recall**。参考文件集合与6c相同：重入131/142可比较；访问控制108/114可比较。原11编译失败和6映射不可比文件仍按原记录排除比较，但模型图中的样本不删除。6c原行集合指标原封不动。

|任务|层|版本|候选/参考/匹配|FP/FN|Precision %|Recall %|
|---|---|---|---|---|---:|---:|
|重入|L1|v3|12345/10215/8974|3371/1241|72.6934|87.8512|
|重入|L1|v4.2|12345/10215/8974|3371/1241|72.6934|87.8512|
|重入|L2|v3|7658/8563/7368|290/1195|96.2131|86.0446|
|重入|L2|v4.2|7485/8563/7368|117/1195|98.4369|86.0446|
|访问控制|L1|v3|14359/10024/8719|5640/1305|60.7215|86.9812|
|访问控制|L1|v4.2|14359/10024/8719|5640/1305|60.7215|86.9812|
|访问控制|L2|v3|3994/4425/3802|192/623|95.1928|85.9209|
|访问控制|L2|v4.2|3863/4425/3802|61/623|98.4209|85.9209|

L1匹配数量和全部指标完全不变。L2重入词法候选减少173（7658→7485），访问控制减少131（3994→3863）；匹配数量及FN不变。旧FP总数482→178，净减少304。其中255条旧FP已明确对应一个原本有匹配词法事件的同一Unit；余49是仍未匹配的alias Unit内部的重复归并。**净减少304与已匹配语句内消除255是不同口径，不能混写。** 本批因扩大跨度单独解决的旧FP为0。逐项证据在每文件unit_comparison.old_fp_resolution及units中。

语句Unit的if/loop AST跨度可能包含子语句，因此跨度匹配本身不能证明绑定/依赖正确；报告保留这一限制。分类时读取/写入是否位于某语句，必须改用实际occurrence位置，不能用整个外层Unit跨度推断。

## 全量互斥类别

单元格为该任务、层、方向内的“数量（比例%）”。FP/FN只是相对于Slither参考的额外/缺失项，不自动表示v2语义错误。解释列区分候选原因与逐条判定，不把未审项强制赋成convention。

### L1

|类别|重入FP|重入FN|访问控制FP|访问控制FN|标签/证据状态|
|---|---:|---:|---:|---:|---|
|entry_initialization|3347 (99.29%)|0 (0.00%)|5278 (93.58%)|0 (0.00%)|入口建模差异；未逐条赋最终语义标签|
|v2_fallback|0 (0.00%)|1162 (93.63%)|0 (0.00%)|1240 (95.02%)|回退范围诊断；不等于所有回退都已验证合理|
|unreachable_ir|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|named_return_implicit|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|declaration_without_initializer|9 (0.27%)|0 (0.00%)|10 (0.18%)|0 (0.00%)|声明建模差异；未新增专项实证|
|tuple_or_var_declaration|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|modifier_body_unanalyzed|0 (0.00%)|44 (3.55%)|0 (0.00%)|29 (2.22%)|v2_scope_limit（抽查5条）|
|loop_header_merge_write|0 (0.00%)|35 (2.82%)|0 (0.00%)|36 (2.76%)|标量局部实证支持；aggregate/storage循环仍unclear|
|aggregate_base_use|13 (0.39%)|0 (0.00%)|12 (0.21%)|0 (0.00%)|memory实证支持；storage引用仍unclear|
|bare_expression_use|2 (0.06%)|0 (0.00%)|340 (6.03%)|0 (0.00%)|slither_convention（抽查5条；限定已确认地址调用形状）|
|other|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|1条rubixi状态循环WRITE，unclear|

### L2

|类别|重入FP|重入FN|访问控制FP|访问控制FN|标签/证据状态|
|---|---:|---:|---:|---:|---|
|constant_excluded|0 (0.00%)|342 (28.62%)|0 (0.00%)|363 (58.27%)|明确排除常量的范围差异；机械类别|
|state_initializer|0 (0.00%)|613 (51.30%)|0 (0.00%)|158 (25.36%)|状态初始化范围差异；机械类别|
|write_base_read|0 (0.00%)|185 (15.48%)|0 (0.00%)|70 (11.24%)|14 delete有实证；241成员写未获得对应最小实证|
|modifier_inlining|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|alias|117 (100.00%)|2 (0.17%)|61 (100.00%)|2 (0.32%)|别名关联口径；未逐条判定|
|v2_binding_unresolved|0 (0.00%)|53 (4.44%)|0 (0.00%)|23 (3.69%)|76条逐条核验为v2_scope_limit|
|assembly|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|push_pop_skipped|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|未命中|
|loop_header_merge_write|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|标量局部实证支持；aggregate/storage循环仍unclear|
|legacy_alias_unconfirmed|0 (0.00%)|0 (0.00%)|0 (0.00%)|6 (0.96%)|v2_scope_limit（旧6条＋新固定5条核验）|
|other|0 (0.00%)|0 (0.00%)|0 (0.00%)|1 (0.16%)|1条rubixi状态循环WRITE，unclear|

## 审查记录、实证及仍有争议项

旧172条只改新判定与解释，原selection、decisions、source/excerpt/primary/nearby完整保留。最终旧172为60 artifact、40 scope、61 convention、11 unclear；初稿把3条array/storage-reference循环与标量Phi混用，root交叉检查声明后收紧为unclear，草稿仍保留。新25条谓词抽查全部predicate_verified=true，但10 scope、11 convention、4 unclear，不能把“谓词成立”当作“约定机制已证明”。rubixi额外的1条判为unclear。

|手写实证|直接观察|可支持的范围|
|---|---|---|
|while/for局部i|IF_LOOP含local WRITE和SSA Phi|支持标量局部循环合并写；不自动推广到storage引用|
|while状态s|条件仅READ，无state WRITE/Phi|未证明L2循环合并写|
|m[k]=v|只写m|不能解释所有结构体成员写的base读取|
|delete m[k]|读＋写m|支持14条同形状delete差异解释|
|m[k]+m[k]、s+s|同CFG节点只记一次对应READ|直接支持语句级去重|
|memory a[i]=v|只写a，不读a|支持memory数组base-use口径差异|
|带参modifier|条件节点归属modifier自身|支持上下文区别；不证明v2已内联modifier|
|x; / 未调用to.call.value(amount);|前者不读x；后者读to、不读amount|限定裸表达式/已确认地址低级调用选项；真正调用会读to和amount|

六个固定.sol文件各运行一次，6/6编译及Slither成功；无真实语料Slither重跑、无安装下载、无全局solc版本切换。scoped_conclusions是同份报告的只读派生，额外Slither调用0。源码、所有节点、IR/SSA及编译器版本/SHA在slither_conventions/保存。一次编译器的最小实证不证明所有历史版本和所有类型都完全一样。

剩余不确定内容：
1. rubixi.sol（访问控制，metadata 0.4.15）while条件2456:2498记录balance WRITE；源码条件仅读，循环体后续有send及balance -=。本轮状态循环最小例无Phi，旧封存参考没有此节点SSA，不能以局部Phi推测替代直接证据。保持unclear，不把它断言为v2漏写。
2. 已审的storage数组/引用写以及array/storage循环合并写：谓词可证，完整参考机制尚缺专项实证，保留unclear。
3. 既有write_base_read的255条中，14为delete，241为状态结构体/成员链赋值。后者只是机械来源核验，不纳入“全部已证明convention”；不以普通mapping赋值的反例或delete正例直接泛化。
4. 全量alias等旧机械类别没有在本轮逐条完成语义审查；原人工512边表和新增111边表仍未填写。此轮审查是AI辅助事件差异分析，不是独立人工DDG边精度标注。

## 76条绑定差异

重入53、访问控制23，涉及116条同名且实际跨度/声明/callable对应的诊断，全部reason=state_name_ambiguous，逐条标v2_scope_limit，引用§3.3“找不到或有歧义，只跳过这一处出现，不放弃整个函数”。逐文件、变量、声明、源码SHA、原句和诊断在binding_review/final_report.json。

本批“ClosedScopeJ失败→只看当前合约→继承状态找不到”的实际命中为0；测试有该子型的正反例，但不把测试构造当成真实语料现象。未通过修改绑定器增加覆盖。

## 测试、失败记录和不变量

最终：v2 1075 passed、8条既有warning；旧DDG/graph_utils 223 passed、29条既有warning；合计1298 passed，0 failed/skipped。warning为DGL distutils与NetworkX gpickle弃用。无训练。

保留中间失败/修订：
- targeted_tests_r1：补丁换行转义导致3个收集错误，修复后149通过，未删除/放宽测试。
- alignment_v4.log：首次真实集成因binding_audits漏初始化NameError失败；补集成反例后重跑。
- alignment_v4：整Unit跨度让34条body写被条件READ影响分类；精确occurrence修正后v4_r1仅剩1 other，匹配指标不变。
- 独立审查补v3版本及同一6c report SHA校验；v4_r2为最终，任务统计和所有差异与r1逐项完全相同，有alignment_guard_only_equivalence.json证明。所有旧目录/seal未覆盖。
- 全套v2测试在各实质修订后分别1070、1071、最终1075通过，最终值不累加历史测试次数。

最终run已只读验证16个图项和20个登记schema；源码/输入/运行时摘要再核验。最终保护快照见final_acceptance.json：除本轮验证工具与文档，其他原跟踪文件及三份文档历史前缀不变；11个封存输入摘要不变。未重建图，未调用HGT前向训练来比较F1。

## 产物与实际命令

正式产物根目录：
scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/
- alignment_v4_r2/report.json、report.seal.json：最终全量证据。
- metrics.csv、categories.csv、review_coverage.json：轻量结果。
- review_r2/selection.json、decisions.json、validation.json：198条目的完整审查。
- binding_review/final_report.json：76条完整绑定核验。
- slither_conventions/及scoped_conclusions：六文件直接实证。
- before.json、final_acceptance.json、日志：不变量及测试。中间版本均保留。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -B -m scripts.DFG.dfg_v2.slither_conventions --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/slither_conventions

python -B -m scripts.DFG.dfg_v2.slither_align --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json --report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json --prior-alignment scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3/report.json --conventions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/slither_conventions_scoped_conclusions.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/alignment_v4_r2

python -B -m scripts.DFG.dfg_v2.slither_review validate --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/review_r2/selection.json --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d1_v1/review_r2/decisions.json
~~~

上面的生成目录已经存在，不能原地重跑覆盖。新实验须另设目录并按需求授权；只读validate和pytest可直接运行。prepare-followup按API/CLI绑定旧v3 selection/decisions、最终alignment和两份conventions输入；全部SHA在selection里。

## 停止位置

本轮验证工作结束，不自动执行Prompt6e、7、8，不改变模型或标签以提高成绩。没有新确认缺陷模式需立即修复，但也不凭全绿测试解除上述语义不确定性。仍采用固定graphs_v2_r1，不覆盖或迁移旧实验。本地按共享上下文提交；本轮没有推送请求，不自动push。
