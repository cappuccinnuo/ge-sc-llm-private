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
