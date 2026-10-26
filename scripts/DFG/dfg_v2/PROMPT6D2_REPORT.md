# Prompt 6d.2：类别级验证与残留影响验收

实施与审查：Codex；日期：2026-10-25。分支dfg-v2，开始HEAD 95775d3abee50c368070f33de48b6668fea8a8b7。按共享上下文pull --ff-only，从已完成6d.1的a32caa2前进到更新模板。本轮只增加验证工具和记录。

## 1. 结论与验收范围

**通过用户批准后收紧的有界FN门槛：passed_with_bounded_FN_residuals。graphs_v2_r1/store.json确定为Prompt7/8最终图存储，携带本报告的10条残留及范围限制。** 这不是“所有差异清零”或“完整Solidity DDG已证明正确”。

原13,553条差异及alignment_v4_r2分类未改。按任务×层×方向×类别分28个非空组，各用独立Random(0)从排序身份抽10条/不足全取，共242条，逐条审阅机械判据。样本判断：129 slither_convention、110 v2_scope_limit、3 unclear。类别：25 accepted、3 accepted_with_residual。样本中3条未决对应全量10条，不能只报3条。

全量残留为9条聚合循环合并事件FN＋1条rubixi状态条件WRITE FN；当前弱定义抽象下定义覆盖/KILL及已有依赖影响已逐条核验，未确认v2_defect。分析器、pipeline、HGT、tokenizer、原图、token、标签、折、训练代码未改；无真实语料Slither重跑、依赖安装、图重建或正式训练。

原6d.1的16条unclear记录对应15个唯一事件：9个storage下标写获得实证解释；5个循环事件＋rubixi仍未解释。全量又纳入4个同类循环事件，最终残留10个；旧决定未覆盖。

图存储SHA：ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
原对齐报告SHA：487640ab0b6a0993615f7a1f9fb39ccde426f244e411e3a5da1e884a713244e4。

## 2. 已征求并采纳的调整

|调整|原因与用户选择|实际执行|
|---|---|---|
|收紧残留门槛|用户同意：≤20且全FN外，还须核查定义覆盖/KILL和已有依赖；漏写可能使旧定义错误传播|对10条逐项核验，validator和反例测试均实现|
|增加声明控制|原五组机制未直接覆盖入口、无初始化声明和状态初始化；用户同意在原fixture补极小控制|参数、具名返回、未初始化局部、局部/状态显式初始化，原11个case/version身份不变|
|alias按实际READ细分|模板按WRITE解释，但178个FP全为READ；用户同意补引用读取及复合赋值|旧分类不改，新182条逐项审计，无伪造WRITE|
|补形状实证|struct成员写不是storage数组下标写；scalar Phi不能直接解释bytes循环|用户批准额外1个小fixture两版各一次；负观察照实保留，不重跑真实语料|

按28个分层而非把类别跨R/AC或FP/FN混合抽样，是较严格的实现；不换seed挑样本。只有上述四项实质调整需征求并已获得用户同意。

## 3. 实际代码、文件和逻辑

新增7个验证.py，均在scripts/DFG/dfg_v2：

- slither_targeted_probes.py：固定fixture白名单和两个已有可信版本，保存源码/编译器SHA、节点读写、IR/SSA及声明元数据，拒绝覆盖。
- slither_composite_retry.py：只允许记录中的保留词失败两个版本，按字节约束修复后重试。
- slither_shape_supplement.py、slither_shape_retry.py：获准的补形状验证，以及唯一失败版本的受限转换语法修复。
- slither_alias_audit.py：182条alias事件的AST、声明、初始化来源、唯一状态根/重复局部名身份检查，不运行原分析器。
- slither_bare_audit.py：穷尽342条bare表达式的AST形状，区分option setter与实际外层调用。
- slither_category_audit.py：固定抽样和前10形状直方图，验证文档quote、探针JSON pointer/value、事件身份、源码清单、残留影响及最终门槛。

新增5个对应测试：test_slither_targeted_probes.py、test_slither_shape_supplement.py、test_slither_alias_audit.py、test_slither_bare_audit.py、test_slither_category_audit.py。convention_cases/p6d2下9个fixture含失败原件和修正件；未来默认入口只选择合法修正件。

validator不自动推断语义verdict。Codex逐条决定独立存JSON；测试覆盖源码/身份/quote/pointer/value篡改、抽样遗漏/重复、虚构residual或defect、隐藏unclear、FP残留、21个FN，以及缺少KILL/已有事实影响证据的拒绝。

仅新增报告PROMPT6D2_REPORT.md，并在HANDOVER、training_changes、PROGRESS末尾追加。原training_changes正文按before SHA快照引用，避免本轮追加使历史scope引用失效。

## 4. 两版本实证和真实失败记录

**实际16次Slither尝试＝13次成功＋3次保留的语法失败；13个不同case/version成功身份；真实语料调用0、下载/安装0。** 使用可信清单中的0.4.24、0.5.11，legacy var只在0.4.24。

- 原11次中9成功、2失败：手写fixture函数名误用了保留词indexed。只改为arrayWrite，独立目录重试失败的两版，原9个成功未重跑。
- 批准的补充2次中0.4.24成功、0.5.11因byte(1)转换语法失败；仅改成bytes1(uint8(1))，只重试失败的0.5.11一次。没有改循环体来追求Phi结果。
- 最初两个shell/PATH preflight失败发生在实际编译前，不计16次；补齐已有mando PATH后继续，没有安装依赖。
- 原失败源、报告、异常、seal和执行版本SHA全部保留。执行源归档为.py.txt，避免被原_runtime()的*.py全树扫描当作计算模块；relocation记录旧→新路径，未改旧seal。
- 文档首次写入调用出现JS字符串语法错误，脚本未执行、无文件写入；修正调用后才写文档，不影响测试或实验。

|机制|0.4.24与0.5.11实测|结论边界|
|---|---|---|
|balance循环有send/无send|条件都没有状态balance WRITE|未复现rubixi猜测|
|storage引用p循环|局部p有Phi/WRITE，状态根无条件WRITE|仅对该形状成立，不外推records/out|
|s.f、m[k].f、arr[i].f、s.inner.g赋值|状态根READ＋WRITE|支持成员链write_base_read差异|
|scalar mapping赋值 / delete|前者仅WRITE，后者READ＋WRITE|保留两者差别|
|storage p.f=v|局部p READ＋WRITE，状态根WRITE|不能声称所有storage基变量都无READ|
|storage数组/bytes下标赋值|局部基变量WRITE但无READ|对应真实25条下标写base-use|
|records/out循环条件|只有计数器i的Phi/WRITE，无records/out|真实9条聚合条件合并事件继续unclear|
|引用读取/复合赋值|状态READ缺失，复合赋值仍记状态WRITE|支持实际178条alias READ差异|
|引用重绑定后写|只写second，不写first|实际数据中没有多根并集FP|
|bare identifier/无外层调用option setter|目标READ缺失|对应穷尽核查的342条形状|
|参数/具名返回/未初始化局部|有声明元数据，入口/未初始化处无对应DEF IR|与v2入口/隐式初始化事件口径不同|
|自身状态初始化|Slither合成构造器计WRITE|v2按既有政策不计自身声明写/自环|

结论只对绑定的版本和形状成立。能被Tree-sitter解析不等于编译成功；这里区分13个成功身份、3次失败原件和未重新编译的真实语料。

## 5. 全量重点核对及类别分布

alias FP：R117、AC61，全为单根状态READ（227原始occurrences）；状态WRITE缺失FP0、多根并集FP0。位置、局部声明、初始化来源、唯一状态根逐条匹配。

alias FN：R2、AC2，都是各自buggy_24.sol::calcDynamicCommission。不同for块中有2个storage和1个memory同名user；当前binder按callable整体拒绝重复局部名。目标块实际唯一storage声明，因此这是§42.3已记录的保守范围，**不是Solidity语言自身歧义**。L2不执行RD/KILL，不会因此让L1旧定义传播。

bare342：AC340＝334条to.call.value(amount);（没有最后的外层调用括号）＋6个独立标识符；R2均独立标识符。零实际外层调用、零判据错误，未触发修改旧分类。334条均0.5.x；8个identifier中7个0.4.x、1个0.5.x，补实证覆盖两版本族。

state_initializer771：全部是明确RHS初始化对自身声明的WRITE，符合原“不计自写/自环”要求；包括初始化表达式不等于加自身写边。v2_fallback2402：精确函数、原因、零events/occurrences/facts、partial_facts_published=false均核对。接受范围不等于恢复这些函数。aggregate_base_use25：12个storage固定结构体数组＋13个memory bytes，都是下标写，已全量复核而非套用p.f结论。

76个绑定差异、705个constant排除、6个无版本依据legacy别名等按原scope及随机样本验收。没有伪造编译器版本或修改标签。模板前10种形状及数量见categories/selection.json.histograms；仅用于描述，不驱动分类或分析。

|任务|层/方向|类别|总数|随机检查|状态|残留|
|---|---|---|---:|---:|---|---:|
|AC|L1 FN|loop_header_merge_write|36|10|accepted_with_residual|4|
|AC|L1 FN|modifier_body_unanalyzed|29|10|accepted|0|
|AC|L1 FN|v2_fallback|1240|10|accepted|0|
|AC|L1 FP|aggregate_base_use|12|10|accepted|0|
|AC|L1 FP|bare_expression_use|340|10|accepted|0|
|AC|L1 FP|declaration_without_initializer|10|10|accepted|0|
|AC|L1 FP|entry_initialization|5278|10|accepted|0|
|AC|L2 FN|alias|2|2|accepted|0|
|AC|L2 FN|constant_excluded|363|10|accepted|0|
|AC|L2 FN|legacy_alias_unconfirmed|6|6|accepted|0|
|AC|L2 FN|other|1|1|accepted_with_residual|1|
|AC|L2 FN|state_initializer|158|10|accepted|0|
|AC|L2 FN|v2_binding_unresolved|23|10|accepted|0|
|AC|L2 FN|write_base_read|70|10|accepted|0|
|AC|L2 FP|alias|61|10|accepted|0|
|R|L1 FN|loop_header_merge_write|35|10|accepted_with_residual|5|
|R|L1 FN|modifier_body_unanalyzed|44|10|accepted|0|
|R|L1 FN|v2_fallback|1162|10|accepted|0|
|R|L1 FP|aggregate_base_use|13|10|accepted|0|
|R|L1 FP|bare_expression_use|2|2|accepted|0|
|R|L1 FP|declaration_without_initializer|9|9|accepted|0|
|R|L1 FP|entry_initialization|3347|10|accepted|0|
|R|L2 FN|alias|2|2|accepted|0|
|R|L2 FN|constant_excluded|342|10|accepted|0|
|R|L2 FN|state_initializer|613|10|accepted|0|
|R|L2 FN|v2_binding_unresolved|53|10|accepted|0|
|R|L2 FN|write_base_read|185|10|accepted|0|
|R|L2 FP|alias|117|10|accepted|0|

## 6. 十条残留及逐项影响证据

下表为**事件级FN，不是漏洞预测FN**。显示原始源码行，完整身份另含任务、文件SHA、声明和字节跨度；两类同名文件不能互换。完整证据在categories/category_decisions.json.residuals。

|任务|文件:原始行|变量|difference_id|
|---|---|---|---|
|R|buggy_24.sol:584|records|bc2926a02d4819e771eb18df8cc5e8120e80d4da9a00dc5419b07d4c67220895|
|R|buggy_24.sol:603|records|67752ea17725fdf910124558b448965e7a9478d3509e2e2bed5e4fe9359b8ac3|
|R|buggy_24.sol:620|records|d4992669d5b84e89772f1a96ddce3d8abbc389f5a4bfdd751504d8dce31046de|
|R|buggy_44.sol:282|out|5a3ba584c12b02fd45be60d690984736aec3a36704cfc4fbe3716f18baa53163|
|R|spank_chain_payment.sol:174|result|fb9ff767395025afb989b3209b96e05f68becabe57ac3e80de853f57c76b8fbc|
|AC|buggy_24.sol:484|records|2536e13abf586058374adc721247526bd552ebc9dfd97662cd335acc05c17d8b|
|AC|buggy_24.sol:497|records|032fbd78293a5c0e6c6a007a7a60c61341f5878226a0b7916527ec79a3ec6b97|
|AC|buggy_24.sol:509|records|1befae2915f10cbb22a96faf871123cb74e874545fd4ea847fed4aaccc16cca5|
|AC|buggy_43.sol:162|out|e215076b432233f2e6d39b891b87077cb4e0fb8bc1319839d2b3922191fc299b|
|AC|rubixi.sol:72|balance|bdf6280be639984106343991a13d0856cf2a2c0e25f534010c61da49455ab5cf|

聚合循环9条：条件均纯比较；同一声明的真实body弱DEF已存在。9条都有到循环后读取的非自环事实并保留初始化定义；6条有非自环循环回传，3条memory bytes通过分析自事实体现回传（没有给模型加自边）。前驱union和弱GEN不KILL保留这些依赖，因此没有遗漏实际条件写或KILL的证据。**仅在当前基变量弱定义抽象内通过**，Slither真实条件合并原因仍未复现。详见aggregate_loop_residual_impact.json。

rubixi：真实条件无赋值/更新/delete/调用，body balance-=的READ/WRITE均已投影。冻结L1只处理_fee、payoutToSend；L2在其后独立加hub边，不把条件事件送回RD。F1/F2/F3完整L1 audit及5773条DATA_DEF_USE端点/key/属性相同。真实历史0.4.15的条件WRITE成因仍未知，本轮未重跑该文件。详见rubixi_residual_impact.json。

没有把缺边写成模型信息等价，L2缺少关系仍可能影响消息传播。未证明完整字段敏感storage alias语义，也没有把未解释事件强改为convention。

附加独立pickle读取被自动审批拒绝，理由是反序列化可能执行代码；该动作未重试或绕过，改用冻结JSON事实和图文件SHA。另一路此前完成的正式cli verify通过16图/20schema，日志独立保存，不用未执行动作冒充验收。

## 7. 测试、不变量与绑定

- 新增84测试：alias17、bare16、category28、targeted14、shape9，全部通过。
- 全部v2：1159 passed，8条既有warning，60.97秒（进程61.66秒）。
- 旧DDG＋graph_utils：223 passed，29条既有warning，3.09秒（进程3.65秒）。
- 合计1382 passed、0 failed、0 skipped；warning仅既有DGL/distutils和NetworkX gpickle弃用。
- cli verify：4任务16图20记录schema通过，验证模型构造0、模型前向0、训练0。
- 写文档前原11211个跟踪文件SHA全部相同；最终只向3份文档追加，11208个其余旧文件不变，3份旧字节前缀不变。9个选定旧报告/seal输入SHA再核对；token/标签/折资产由原store/manifest验证器核验。
- 独立审阅与测试并非全数据逐条人工图边证明。原512/111人工边表未代填，原Oracle结果未改。

最终categories/validation.json及seal：
selection SHA 94e545c3a56c41b9fa1d3bc967af6b928c79a2c2edd5bd0126a801420255c678；
decisions SHA b40a967a0dd9d27b65c4c1dbc2fb75440d2f2a163357b4c7c2ea6637008e21a5；
categories SHA 247a2379a3d61a27f71edcfcaf3c1aa798d8f521345337c2b63ab11e3d0c20cd。

## 8. 命令、产物与停止点

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.slither_category_audit validate \
  --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/selection.json \
  --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/decisions.json \
  --categories scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1/categories/category_decisions.json
python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

实际生成命令：
slither_category_audit prepare --alignment <alignment_v4_r2/report.json> --output <O>/categories；
slither_alias_audit --alignment ... --output <O>/alias_identity_audit_r2；
slither_bare_audit --alignment ... --output <O>/bare_audit。
O即scripts/DFG/experiments/artifacts/dfg_v2/prompt6d2_v1。目录已经存在，生成器拒绝覆盖，不能原地重跑。

手写入口参数：--trusted-compilers <prompt6c_v1/trusted_compilers_complete.json> --output <新目录>；
两种受限retry另需--failed-report <原失败report.json>。实际批次为probes、probes_retry1、probes_shape_supplement、probes_shape_retry1。默认runner现在选择合法修正源，未来新批次不是原失败attempt的逐字重播。

新产物在O保留before快照、执行源、全部成功/失败报告、全事件审查、直方图、旧未决followup、两类impact、测试XML/log与final_acceptance。沿用仓库惯例：运行原件留WSL本地，代码/fixture/可读报告及三文档进入本地提交。

本轮停止，不开始6e/7/8、不训练、不push。下一步可基于同一graphs_v2_r1进入Prompt7接入；本轮没有声称已经实现或执行它。
