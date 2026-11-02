# NodeSem 实施进度

## 2026-11-01 NS-P0：只读侦察完成（修改 AI：Codex）

**输入与范围**：node-sem，起始 HEAD 489cebe29181bddbd9fa6170fc4498f082fc9ac7；开始时 pull --ff-only origin node-sem 返回 Already up to date。完整阅读设计第1—4节、共享上下文5.1及NS-P0。只实现侦察，不提前创建NodeSemAdapter、特征/训练模块或NS-P1测试目录。

**新增文件**：RECON.md、recon.json，以及recon/inputs.py、carrier_probe.py、text_ast.py、cfg.py、run.py。另追加根HANDOVER和docs/training_changes_2026-10-07.md。原DFG目录、HGT/tokenizer、图/特征/标签/折/初值/plan/seal均未改。

**验收数字**：
- 60/60份G0/G3R成功收据、2137个唯一文件SHA，四任务30折完整；每折配置、prepared初值与receipt绑定一致。
- 真实重入节点G3R 12223节点/23703边：512→600维构造8.462→9.494秒，参数5111012→5302500；17个Linear(600,128)替换、注册与临时binding通过；篡改manifest正确拒绝。
- G0 layers=0节点/合约前向反向与梯度审计通过，独立公式逐位一致；0优化器更新、原图/参数不变。A/B没有做真实600维HGT前向，尚未验证完整NodeSemAdapter。
- 四任务原节点匿名文本全覆盖：18312/12036/13432/7710；删除注释后ERROR/MISSING仍0、执行token不变。覆盖的是文本与AST身份，不等于所有DDG支持。
- legacy→v2 CFG可构造3135/3404、1964/2045、2797/3148、1859/1958；这是CFG覆盖，不是完整RD支持。

**实际命令与结果**：在mando、CPU，设置PYTHONDONTWRITEBYTECODE=1、OMP/MKL线程2、TREE_SITTER_LIB_DIR为既有linux-x86_64库。
- python -B -m scripts.node_sem.recon.run：全量侦察断言通过，169.64秒；详细JSON含代码/输入SHA和逐函数/逐节点证据。
- python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests：2653通过，9条既有弃用警告，171.91秒。
- python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py：223通过，29警告，4.16秒。
- 合计2876项唯一测试、0失败/跳过；5份新脚本Python3.7语法通过。回归内部沿用合成fixture训练，未启动新的真实数据fit。

**用户批准与差异处理**：用户明确同意NS-P0用侦察断言和两套既有回归，专用NodeSem tests目录延至NS-P1。8H旧plan.runtime不是当前实际运行版本：此前已批准cache/resume修订，当前_code_refs与runtime_resume_v2一致且原execution.load通过；保留全部旧seal，不新增豁免。checkpoint的torch.load被自动审批拒绝后，仅做文件SHA及非执行ZIP/pickletools静态头检查，没有绕过；state_sha256跨JSON引用一致，未独立重算tensor digest或重载60个模型。

**待下一阶段征询，尚未更改方案**：
1. Projector需结构性label作AST身份，但特征白名单禁止任何label；需明确身份边界及扰动验收。
2. 所有DATA_DEF_USE边不直接带变量名；M2需明确绑定既有L1 sidecar和8G匿名化。
3. if/while条件支配不等于守卫通过；当前CFG无分支极性/显式require异常出口，NS-P3应区分未知。
另提醒后续配置必须保留layers=0，不能使用layers or default。

资源外推N-A/B/C/D仅历史fit计算约4.814/2.473/3.475/1.738小时，不包括特征编码/LLM/蒸馏、构造验收和新适配器；不是运行时承诺。最终实验按用户安排在显存充足服务器执行，当前RTX3050 4GiB仅是本机开发限制。

本轮结束于NS-P0验收与本地NS-P0提交；不自动推进NS-P1、正式训练或GitHub推送。


## 2026-11-01 NS-P1：载体与执行骨架完成（修改 AI：Codex）

起始HEAD 27ea6617fd9fc81d9d60cf068122b8d8c996d930，node-sem，pull --ff-only已是最新。完整读取r4介绍与共享上下文后实施。新增FeatureSpec、S0/S1配置、严格载体、单份共享EmbeddingBag适配器、模型组合、确定性初值、SHA受限加载、独立执行器与CPU等价入口/修订入口，以及tests。原DFG、HGT、tokenizer、输入图/匿名特征/标签/划分和8H产物未改。

r4决策：NS-Q1结构label只由冻结Projector用于AST身份；NS-Q2未来名字从封存L1证据/状态与环境属性经8G映射；NS-Q3未来guard采用AST词法规则。后两项本轮未提前实现。S0仍原512维Linear；S1载体513维，只注册一份V×64 EmbeddingBag，各类型Linear(64,128)，保留显式layers=None/0。

用户批准：
1. 仅对批准的8H初值/checkpoint和NodeSem封存文件，在紧邻加载前核对SHA后使用torch.load；60/60初值独立tensor_digest补验通过（7.25秒）。PyTorch1.8 pickle风险已明确，没有扩大范围。
2. 扰动验收分离输入完整性与特征不变性：原manifest拒绝改图，仅测试manifest重绑定图指纹；特征/行/source不变，损坏AST锚点仍拒绝。
3. scheduler.anneal_func是绑定方法，两个实例直接比较不同；批准核验同一OneCycleLR类与函数实现，其余字段继续逐位比较。原失败/seal/38个重入CPU产物保留，独立acceptance_revision1复验后继续，不重训重入。

真实验收：
- 16组载体（四任务×G0/G3R×S0/S1）通过。真实重入G3R S1词表32100、17节点类型、6190564参数、唯一嵌入2054400参数，CPU有限前向通过，无S1正式训练。
- 60/60历史S0收据完整只读验收通过（76.90秒），不重新训练。
- 重入节点fold0/G3R与访问控制合约fold0/G0，两侧各2轮，共4次CPU短检查；初值/输入/字典/非特征绑定、逐轮loss、最终及best/last参数、Adam、scheduler数值、inner/outer预测逐位一致。scheduler方法按已批准身份规则核验。
- 原/新构造秒：重入15.969/30.813；访问控制15.040/31.461。仅maximum_training_epochs改2，schedule_epochs仍50；实际设备CPU，无正式fit。
- NodeSem最终184通过；DFG v2 2653通过；原回归223通过，共3060唯一测试，0失败/跳过。命令与警告详见NS_P1_REPORT和tests_revision1.json。最终NodeSem4警告，旧套件9/29警告，均已有弃用信息。

工程问题如实保留：准备阶段漏建specs目录，在0封存计划/0fit时失败；修复后补回归。审查另发现fit父目录需显式创建，已在开训前修复。没有放宽数值断言或删除失败证据。新生产Python仍全部在NodeSem，原8H runtime_resume_v2只读核验通过。

产物：artifacts/ns_p1_initial_digests、ns_p1_acceptance、ns_p1_equivalence。最终equivalence.json引用acceptance_revision1/batch/plan.json；最初batch/seal只作归档。详细实施/选择见training_changes§72，概览见NS_P1_REPORT.md。三份文档仅追加。

范围限制：M1/M2、教师/学生、多模态融合、GPU验证和正式K折尚未开展；未来F3特征用于G0时须明确profile行集合。S0等价不是S1效果提升证明。最终实验按用户安排上显存充足服务器，本机RTX3050 4GiB只是开发限制。本轮产物留WSL；提交NS-P1后停止，不自动push或推进NS-P2。


## 2026-11-01 NS-P1b：运行版本拆分与S1初始尺度修正完成（修改 AI：Codex）

已读取r5共享上下文与审查，node-sem输入0b1152b，快进同步无新变更。新增p1b_acceptance.py、test_runtime.py、test_p1b_acceptance.py及NS_P1B_REPORT；修改__init__/execution/adapter/model/init及对应测试。旧DFG/HGT/tokenizer、输入和NS-P1/8H产物保持不变；详细见training_changes§73。

- RUNTIME_MODULES只含8个训练模块。新计划nodesem-execution-v2：execute默认严格比较当前代码；verify核验封存绑定、started完整runtime、receipt与产物SHA，不要求当前NodeSem代码相同。v1只能verify；S0继续走8H自身核验。v2独立receipt seal补全收据完整性。
- S1增加一份共享LayerNorm(64)，只作用非空池化行，空行仍为零；嵌入N(0,1)、pad0、norm1/0、Linear仍Xavier/0，语义随机源不变；初始化v2。S0原512维Linear完全不变。
- 用户批准保留冻结装配中的标签核验；诊断统计/注意力/r5门槛不使用标签或评分。JSON的labels_read=false仅指诊断计算，非整个装配调用链。批准已在scale前封存。
- 真实重入节点fold0/G3R：h0全局std为S0 673.8923、r4 0.002196、r5 0.459034；r5逐类型0.433297–0.540383，通过[0.05,5]。多邻居注意力集中比例88.8918%/0%/0%。r4第一层归一化后std也接近1，不能仅据此断言无法学习。r5非pad嵌入std0.999573，参数6190692（比r4+128）。
- S0原/新各2轮CPU全部逐位等价（scheduler方法按已批准同类同实现比较）；S1一轮CPU loss有限，共享bag/norm和17种Linear共37个参数张量均有非零有限梯度，gcs/classify初值复制与best/last重载通过。合计3fit/5epoch，0正式训练、0GPU。
- 旧acceptance_revision1的60项S0完整只读验收通过；旧118个产物SHA未改。等待批准的progress_pending记录保留，最终看completed.json。
- 测试198 NodeSem+2653 DFG v2+223原回归=3074通过，0失败/跳过，警告4/9/29均为既有弃用信息。新空行测试曾因批量/单行Linear舍入差异失败，改为相同形状仍逐位断言，失败记录保留。

命令：python -B -m pytest -q -p no:cacheprovider 后接三套目录；python -B -m scripts.node_sem.p1b_acceptance prepare/archive/scale/s0/smoke（分别执行，均已完成，拒绝覆盖）。完整命令和证据见NS_P1B_REPORT.md及artifacts/ns_p1b。

最终实验按用户安排使用显存充足服务器，目前RTX3050 4GiB只是本地开发限制，服务器尚未部署实测。只本地提交NS-P1b，不自动push，不推进NS-P2；未评估S1正式检测收益。


## 2026-11-01 NS-P2????????????????? AI?Codex?

??node-sem@c3657236?r6???????????5.1/5.4???text_view.py?p2_acceptance.py?offline/asset_registry.py/encode.py/assets.json/seal/README/requirements-nodesem-lock.txt?configs/S2.json?3??????NS_P2_REPORT???carrier._aligned???????DFG/????????????????

- ??????compat AST??????????????????????/??????cut_mode??????identifier??????8?0???
- ???/F3?????12036/12223???????7710/7892?????18312/18610???????13432/13693??????/??????24???????????????/??/??/??/????214/7614/2247/1089/1059?177/5074/2182/244/215?543/11587/3981/1267/1232?474/8730/3723/403/363?
- ????52418?????104836?float32?256?CodeT5????????fp16 GPU????8/8?????max??0????????0fit???????2846/2567/5636/4762???76.716/67.473/69.715/65.223%???7223/5115/12014/9484???40.906/35.188/35.443/30.738%????????4????3??????????218.937??peak allocated??419.496MiB?
- ??manifest????F0/F3?carrier?????????????????8????16??????S0/S1????????S2???CODE/concat?????????
- ?????Codex??????????????? nodesem ????????????Python3.10.21/torch2.6.0+cu118/transformers4.46.3????revision?SHA???????????????????????WSL????????????pip??user-site???3???????????????python -s/PYTHONNOUSERSITE???encoder????????????????????training_changes?74??????????????
- ?????8????????/????161907029????????????????????????E?WSL?

???mando????python -B -m pytest -q -p no:cacheprovider???scripts/node_sem/tests?216??scripts/DFG/dfg_v2/tests?2653??scripts/DFG/tests tests/test_graph_utils.py?223??nodesem python -s -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests/offline_checks.py?18???3110???0??/?????4/9/29/0??????????p2_acceptance texts/verify?8?encode???offline/README?encoding_plan?8H load???runtime_resume_v2????????????????????

???artifacts/text_v1/<view>/<task>?artifacts/ns_p2/encoded/<view>/<task>???text_acceptance/acceptance/validation.json?encoding_summary.csv????NS-P2????????push?M2/????????LLM/??????????????????????????4GiB??????????????????
