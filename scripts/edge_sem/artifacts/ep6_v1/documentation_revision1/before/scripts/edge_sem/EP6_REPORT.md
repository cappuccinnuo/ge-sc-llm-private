# EP6：边感知 HGT 与 r14 前置修正验收

基于 bd81a2bdd7c2f6385261341d336cb100c562038c，按 PROMPTS.md r14 完成。本轮只有 CPU 构造、前向/反向验收，optimizer_steps=0；没有正式训练、GPU 检查或新评分。

## 授权与历史边界

用户批准 call_1c4fc0064fb94266be56b656e6399928：用冻结 sem.sink(目标 AST, 精确封存符号) 补齐参数入口缺失的 dfg.to；已有记录必须一致。授权见 artifacts/ep6_v1/decisions.json。原图、冻结 NodeSem/DFG/作者模型与旧产物均保留。
新边写入 artifacts/f4_v2，属性写入 artifacts/ep6_v1/attributes。manifest 的 v1 表示存储格式，批次由路径、源码 SHA 和输入引用区分。生产加载器仍要求当前源码 SHA；旧 EP2 回归通过显式归档路径读取准确的旧源码快照，旧 seal 未修改。

## F4 重建与属性差值

|任务|旧 E1 行|新 E1 行|新增 fallback MOD_APPLY|
|---|---:|---:|---:|
|access_control_contract|9871|9871|0|
|access_control_node|5261|5261|0|
|reentrancy_contract|12036|12036|0|
|reentrancy_node|7669|7669|0|

节点任务 edge_keys 完全相同；仅旧 no_exact_dfg_to_for_this_edge 的 DATA_DEF_USE 上，第22–29/37–40位发生0→1，其余列逐位相同。

|位|含义|重入：旧→新（参数入口新增）|访问控制：旧→新（参数入口新增）|
|---:|---|---:|---:|
|22|use_context_condition|514→1161（628）|149→1677（1508）|
|23|use_context_call|390→793（403）|172→1209（1037）|
|24|use_context_arithmetic|32→124（92）|14→104（90）|
|25|use_context_state_write_value|52→597（543）|55→301（244）|
|26|use_context_return|103→145（42）|96→138（42）|
|27|arith_op_additive|31→76（45）|12→55（43）|
|28|arith_op_multiplicative|1→48（47）|1→48（47）|
|29|arith_op_exponent|0→0（0）|1→1（0）|
|37|call_low_level|5→181（176）|1→2（1）|
|38|call_delegatecall|0→0（0）|0→1（1）|
|39|call_sends_value|190→387（197）|12→534（522）|
|40|call_return_checked|44→239（195）|19→33（14）|

access_control_node：变化2941条边 / 3571位；已有sink集合比较756条边，全一致；DATA_DEF_USE仍有496条边无第22–26位映射，保留冻结分类与unknown规则。

reentrancy_node：变化1727条边 / 2389位；已有sink集合比较1480条边，全一致；DATA_DEF_USE仍有651条边无第22–26位映射，保留冻结分类与unknown规则。

新端点检验已重算，core_indices仍50位、context_indices仍26位；合并去重为73位（第15位停用），相对EP5均无变化。完整端点统计见 attributes/selection.json。

第61位每任务8个文件无法由绑定pragma/metadata判定 <0.8 或 ≥0.8。pragma分布均为 >=0.5.9：1、>=0.5.1：2、>=0.5.11：5，当前source metadata未绑定精确分析版本。按任务、文件、源码SHA对齐封存6c报告，这16个文件实例都有历史pragma_derived编译选择记录；历史验证所选编译器不能反推分析/部署版本，本轮不注入属性。详见 compiler_history.json。

## 名字不变性与覆盖

128文件全部通过：54个实际改名，74个原文回退对照。匿名侧用翻译后的封存符号计算sink。原图及原证据未改。

|任务|实际改名文件|改名文件边 / 全部边|library CALL_SITE覆盖|
|---|---:|---:|---:|
|access_control_node|24 / 57|3158 / 21830（14.47%）|3 / 350|
|reentrancy_node|30 / 71|5171 / 31372（16.48%）|3 / 364|

coverage.json列出全部关系、CALL_SITE实际kind、GUARDS各kind及回退原因；GUARDS多kind计数可重叠。回退不算真实改名证据，不能宣称全语料已验证。新增库调用合成用例覆盖库名、方法、结构类型、接收者、重载、同名成员及不同名字长度，按AST遍历身份比较；它不能替代真实覆盖。

## E3实现及CPU验收

- hgt_edge.py导入时核验两个冻结源码SHA；父构造器先执行，再建立零初始化u和五族U。
- 单模型EdgeAttrEncoder：uint8→float，Linear(选中位数,32)→GELU→Linear(32,16)→dropout(0.1)。每次前向每个规范关系编码一次，各HGT层复用psi。
- 仅增加softmax前的关系注意力偏置和按关系族共享的消息增量；共享投影、mean聚合、残差、HGT dropout与LayerNorm保留父层行为。psi=None直接调用父层。
- G4R-A、G4R-Api、G4R-AC、G3R-TA接通；Api按constructor seed调用placebo.py置换完整属性行；AC合并索引去重。其他结构剖面保留原路径。
- 原图多重边key精确对齐实际EID，REV_复制正向uint8[74]。注册核验manifest、索引、逐边NPZ、层类型及置换来源；无事实重算或评分时建参。
- EP1新鲜结构装配先复制共享参数，自有子类接管该私有模型状态，没有monkeypatch冻结模块。新层再次严格复制共享参数；编码器在隔离的constructor seed RNG中默认初始化。

真实reentrancy_node fold0：hidden128、heads8、layers2、512维inside_token，使用冻结原始F3作结构验收。实际设备CPU；收据config中的cuda:0是引用的历史训练字段，不代表执行设备。EP7训练特征视图、监督与P2协议仍须独立绑定。

|测量|结果|
|---|---:|
|G4R参数|5619908|
|G4R-A参数|5712692|
|新增参数|92784|
|构造秒|33.756|
|CPU前向秒|1.434|
|CPU反向秒|2.281|
|零初值最大绝对差|0.0|
|编码次数 / 规范关系|274 / 274|

前后向有限，共享参数逐位相同，原图指纹不变，CUDA未初始化。进程RSS峰值3386.4MiB是整套测试进程历史峰值，不是模型独占内存或GPU显存。小图验证psi=None在eval/train固定RNG下逐位相同；零u/U的eval误差≤1e-6；非零u/U时输出改变且梯度到达u/U/编码器。u/U全零时编码器初始梯度为0符合链式法则，不是断图。模型级等价为eval检查，新增dropout后不能声称任意训练随机轨迹也相同。

## 回归与运行记录

最终4,300项独立测试通过：EdgeSem294、NodeSem1,353、DFG v2 2,653。EdgeSem首次全量288通过、4个旧EP2归档用例因更新后的测试源码SHA被拒绝；保留失败日志。扩展显式归档校验后，仅复核原4项及2个新拒绝用例，6项通过；其余成功检查和真实CPU收据复用，没有重建属性。
开发阶段修正了helper导入作用域、合成fallback图缺节点及库参数类型限定名。两套冻结回归曾合并收集，因同名test_model.py冲突而未执行；保留日志后按文档分别运行。摘要见 development_notes.json，实际命令/退出码/日志SHA见 execution/<步骤>/started.json和result.json。

## 结论与停止位置

EP6前置修正与边感知层CPU接入完成。尚无E3训练分数、检测提升或GPU资源结论；不启动EP7、新seed或其余漏洞类别。
最终实验将在显存充足的服务器运行；RTX3050 4GiB限制仅来自当前本机开发。服务器仍须做目标设备的资源与数值验收。
证据入口：artifacts/ep6_v1/summary.json、verification.json、real_cpu.json、attribute_delta.json、anonymous_gate/coverage.json。
