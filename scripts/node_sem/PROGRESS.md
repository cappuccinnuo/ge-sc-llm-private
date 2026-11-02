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


## 2026-11-01 NS-P2 完成（2026-11-02 NS-P2b 校正，修改 AI：Codex）

本节替换原先字面问号的损坏内容；原字节已归档，前后内容均逐字保留。以下数字是 NS-P2 的历史验收，不冒充 NS-P2b 重跑。

新增 text_view.py、p2_acceptance.py、offline/asset_registry.py、offline/encode.py、offline/assets.json/seal、依赖锁和 README、configs/S2.json，以及 test_text_view.py、test_p2_acceptance.py、offline_checks.py；修改 carrier._aligned 与对应配置测试。模型权重与 NPZ 保留本地，不纳入 Git。

文本使用冻结 ProjectionView/Projector/node_code_view 的兼容 AST 身份截取。if/while 为条件、for 为头部；函数/构造器/modifier 为签名，合约/库/接口为头部，语句和 struct 为对应完整片段。end 节点使用占位符，env_source 使用环境键。空白规范化；锚点损坏直接拒绝，不猜行号。原/匿名两视图切片模式一致，逆改名后原文相同。

carrier._aligned 允许以 F3 为全集的 manifest 供 F0/F3 共用：F0 只省略经身份核验的辅助行，其余严格按原图顺序。原 TOKEN_IDS/S0/S1 保持。CODE manifest 含 dtype/shape、row_key、file、source/code/vector SHA、presence、F0/F3 图指纹、生产者和资产引用；产物与源码摘要不符则拒绝。S2 只注册 CODE/256/concat，真正 concat 训练仍留 NS-P4。

离线编码使用冻结 CodeT5、eval/inference_mode、GPU fp16、输出 float32、max_length=128、batch_size=32，模型自身输出归一化的 256 维向量；按模型摘要＋长度＋pooling＋文本去重，再按长度排序分批。GPU 使用既有 .training.lock，不与训练并行。没有修改 DFG/HGT/tokenizer、图、标签、折或训练计算。

用户明确批准 Codex 创建独立 nodesem 并安装依赖，覆盖模板原先要求用户自行准备环境的限制；模型下载也已授权。实际 Python 3.10.21，torch 2.6.0+cu118，CUDA runtime 11.8，transformers 4.46.3，sentence-transformers 3.3.1。来源为本地官方快照及逐文件 SHA 校验，安装/下载记录在 artifacts/ns_p2/environment/，大文件位于 E 盘承载的 WSL；mando 不改。

安装初期 pip 看到了 Python 3.10 user-site，移除了 filelock 3.32.6, tqdm 4.70.1, typing_extensions 4.16.0；已按原版本与校验 wheel 恢复。后续统一 python -s/PYTHONNOUSERSITE=1；nodesem 激活禁用 user-site，encoder 拒绝在 user-site 启用时运行。此副作用不得写成“从未触及用户环境”，详细见 installation_scope.json 与 restore_user_site2.log。WSL 网络不稳定时经既有 Windows 代理获取下载文件，截断或摘要错误不能算完成。

清理记录仅删除 8 个自己产生的重复安装/临时文件，共 161907029 字节；模型/特征删除数为 0。没有删除用户其他资料。

| model | revision |
| --- | --- |
| BAAI/bge-small-en-v1.5 | 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a |
| Salesforce/codet5p-110m-embedding | d9f3a534af4252f04b10cd9f78e05037542d10f6 |
| microsoft/unixcoder-base | 5604afdc964f6c53782a6813140ade5216b99006 |

加载 local_files_only=True，CodeT5 自定义代码文件也核验 SHA，权重使用 weights_only=True。只有 CodeT5 完成全量编码，UniXcoder 的 masked mean 有单测但未做全量对照，BGE 留到后续教师阶段。

| task | F0 | env | F3 | header | full | signature | condition | placeholder | fallback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | 12036 | 187 | 12223 | 214 | 7614 | 2247 | 1089 | 1059 | 0 |
| access_control_node | 7710 | 182 | 7892 | 177 | 5074 | 2182 | 244 | 215 | 0 |
| reentrancy_contract | 18312 | 298 | 18610 | 543 | 11587 | 3981 | 1267 | 1232 | 0 |
| access_control_contract | 13432 | 261 | 13693 | 474 | 8730 | 3723 | 403 | 363 | 0 |

| task | view | rows | unique | dedup % | truncated | seconds | peak MiB | bitwise | max error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | original | 12223 | 2846 | 76.716 | 4 | 23.938 | 419.496 | True | 0.0 |
| reentrancy_node | anonymous | 12223 | 7223 | 40.906 | 3 | 28.778 | 392.980 | True | 0.0 |
| access_control_node | original | 7892 | 2567 | 67.473 | 4 | 16.761 | 380.050 | True | 0.0 |
| access_control_node | anonymous | 7892 | 5115 | 35.188 | 3 | 23.355 | 408.177 | True | 0.0 |
| reentrancy_contract | original | 18610 | 5636 | 69.715 | 4 | 28.952 | 418.792 | True | 0.0 |
| reentrancy_contract | anonymous | 18610 | 12014 | 35.443 | 3 | 40.036 | 372.825 | True | 0.0 |
| access_control_contract | original | 13693 | 4762 | 65.223 | 4 | 23.729 | 404.237 | True | 0.0 |
| access_control_contract | anonymous | 13693 | 9484 | 30.738 | 3 | 33.388 | 367.049 | True | 0.0 |

8 组均进行了两次独立完整编码，repeat_bitwise=true，最大误差为 0；没有优化器更新。原名视图每任务 4/4/4/4 行超过 max_length，匿名每任务 3/3/3/3 行；截断属于已记录输入限制。总墙钟 218.936 秒，包含编码流程，不是纯 kernel 时间；PyTorch peak allocated 为 367.049–419.496 MiB，仅对应离线编码，不等同于 HGT 显存。

历史测试合计 3110 通过、0 失败/跳过；完整命令与告警见 validation.json。NS-P2 原载体验收为 8 个模态加载、16 个 F0/F3 选择对齐通过；8H execution.load 与 _code_refs 对批准的 runtime_resume_v2 运行版本一致。原测试命令、时间、警告和日志引用见 artifacts/ns_p2/validation.json；这些是历史结果。本轮新的测试和只读复验另记 NS-P2B 报告，不修改旧 JSON。

未运行 HGT 训练，无 F1 或收益结论；M2、concat、LLM 和蒸馏未实现。代码节点文本是按既有 AST 与 8G 文件级拼写双射产生，不能声称完成 Solidity 语义绑定/编译验证，或跨文件编号不变性。

最终实验按用户计划在显存充足服务器执行；当前 RTX3050 4 GiB 仅为本地开发限制，服务器尚未部署实测。复现命令见 offline/README.md；所有旧输入只读，新跑必须使用新目录，修改生产者后必须新生成特征，不能更改旧 manifest 来绕过校验。


## 2026-11-02 NS-P2 文档编码复核与可读更正（修改 AI：Codex）

上节 2026-11-01 的 NS-P2 中文已被写成 ASCII 问号。保留该历史段落，本节和 NS_P2_REPORT.md 的可读修订替代它的文字说明，不将损坏原句当作证据。根因路径已复现：PowerShell $OutputEncoding=us-ascii，“中文”经管道进入 WSL 成为 3f3f0d0a；f049d18e 的 Git blob 也受影响。此前只验字节一致，漏验了可读性。

NS-P2 实际完成 text_view.py、p2_acceptance.py、offline 资产/编码器、S2 配置及相应测试；carrier._aligned 支持 F3 全集供 F0/F3 取行。四任务×原名/匿名共 8 份文本和 float32/256 向量，单视图 52,418 行、合计 104,836 行；0 截取回退、24 项生产者扰动验收、8 组两遍编码逐位一致；编码墙钟合计 218.937 秒，PyTorch peak allocated 最大 419.496 MiB。具体截取分布、去重率和逐组耗时见修订报告和 encoding_summary.csv。

用户曾批准创建独立 nodesem；版本、三个模型 revision、下载 SHA 和 user-site 三包恢复记录均保留，mando 不变。历史测试为 216＋2653＋223＋18＝3110 通过、0 失败/跳过，42 警告；8 模态/16 对齐、8H 运行版本核验通过。上述为旧验收数字，本轮没有重新运行训练或全套测试。

本轮检查 75 个 JSON/JSONL 可解析，33 个封存引用 SHA 一致，104,836 行身份/text SHA 一致，8 个向量文件 SHA 一致。匿名编号按文件 SHA 固定：跨文件同文本可能不同；同源码同文本冲突为 0，跨任务重复节点身份 19,746 组冲突为 0。这个边界可能影响编号敏感性与精确去重率，不是已证明的模型退化；没有擅自改匿名化方案。

修改仅涉及可读报告、offline README 的 section 5.4 字符、三份文档追加和独立 artifacts/ns_p2_review_20261102 审计。保留旧产物/计划/seal/代码；原始损坏报告可从 f049d18e 读取。写入采用 ASCII 转义载荷＋显式 UTF-8，并核验回读中文与未改文件；详见 audit.json、correction_validation.json。NS-P2 没有 HGT fit 或 F1，S2 concat 留 NS-P4。最终实验计划迁到显存充足服务器，本机 4 GiB 仅为当前开发限制；本次不部署、不推进下一阶段、不自动推送。


## 2026-11-02 NS-P2b 完成（修改 AI：Codex）

已确认 f049d18e 中报告为 2,058 个字面 U+003F 问号、0 个中文字符；三份历史记录的 NS-P2 节也损坏。写入通道为 Windows PowerShell 字符串脚本经 stdin 到 WSL Python，调用形态是 `$s=@'…Python script…'@; $s | wsl.exe -d Ubuntu-22.04 -- python3 -`。项目未保存当时完整脚本文本，因此不能逐字复原原始命令。当前 $OutputEncoding=us-ascii；把 U+4E2D/U+6587 组成字符串经同一路径传给 od，得到 3f3f0d0a，复现了替换机制。此前核验只检查本地/Git 字节一致，没有检查中文可读性，这是 Codex 的验收遗漏。

本轮只用 ASCII 的 JSON Unicode 转义或 Base64 载荷通过该通道，在 Python 里解码并以 UTF-8 写文件。所有修订中文必须再经 doc_check --expect-cjk，不能以可解码或哈希一致代替内容检查。

用户已批准两项最小调整并予以记录：(1) 实际损坏节后已有上一轮可读更正，归档后只替换损坏节，前缀与后缀均逐字保留；(2) “标题原本应有中文”不能由纯英文内容推断，用 --expect-cjk 显式声明，本轮四份中文文档强制启用。没有改变匿名化、模型或特征设计。

新增 doc_check.py、tests/test_doc_check.py、NS_P2B_REPORT.md 及 artifacts/ns_p2b/ 诊断/归档/验收记录；生产代码和特征保持冻结。doc_check 不进入 RUNTIME_MODULES，21 项定向测试通过；对四份中文文档及新写段落强制 --expect-cjk。

| task | split/shared | pairs | within mean | median | p05 | control mean | median | p05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | 735/841 | 75457 | 0.903835 | 0.912406 | 0.804697 | 0.601283 | 0.594306 | 0.381917 |
| access_control_node | 561/669 | 36939 | 0.922279 | 0.927494 | 0.848926 | 0.624942 | 0.635369 | 0.388834 |
| reentrancy_contract | 1155/1269 | 99042 | 0.902175 | 0.912087 | 0.799734 | 0.615706 | 0.612720 | 0.386796 |
| access_control_contract | 893/1005 | 60230 | 0.912641 | 0.921694 | 0.813855 | 0.637461 | 0.643771 | 0.405901 |

不同文件的 vN 编号使向量不再相同，但同原句变体的平均相似度仍高于同类型不同原文对照。结果量化了编号敏感性，没有证明检测 F1 会提升或下降，也不构成改变 r7 冻结编号决定的依据。原名上限全部通过：同一原文的向量逐位相同，cosine 为 1（容许浮点舍入）。不把大量语句对当作独立实验做显著性宣称。

对冻结完整匿名源码 AST 按原切片身份统计，四任务均为 0 个非 vN 且不在保留表中的代码名称，re_ent/txorigin 原文标记匹配均为 0。字符串字面量中的普通词单列，它们不是变量名，不隐去也不误计为匿名化失败。

文档列举的 data、number、min、max、sig、interfaceId、encodePacked 在实际 grammar 中确实出现为 identifier，且 reserved(name)=true；它们未改名的原因是保留表，而非“不是 identifier”。例如 data 在 parameter、call_argument、member_expression 等上下文保留，说明保留规则是拼写级而非只保留内建绑定。此为冻结 8G 的范围限制，本轮只记录，不修改；不同任务具体次数与 grammar_type/parent_type 见 residual_names.json。

| suite | passed | failed | skipped | warnings | seconds |
| --- | --- | --- | --- | --- | --- |
| node_sem | 237 | 0 | 0 | 4 | 6.313 |
| dfg_v2 | 2653 | 0 | 0 | 9 | 152.547 |
| legacy | 223 | 0 | 0 | 29 | 3.650 |

8 份 CODE manifest 均经 carrier.load_modality 重新通过源文件、实现、资产和逐行向量校验；8H 计划 load 与生效 runtime_resume_v2 相等。未重新编码，不使用 GPU、不读取评分或预测文件。最终完整性检查与 doc_check 日志见 artifacts/ns_p2b/final_validation.json、doc_check.log；原文归档与替换字节边界见 corrupted_docs/index.json、document_rewrite.json。

本轮不训练、不使用 GPU、不推进 NS-P3。最终实验拟使用显存充足服务器；当前 4 GiB 仅为本机开发限制。实际命令见 NS_P2B_REPORT.md。


提交前补充：通用 `git diff --cached --check` 对原始 `preexisting_document_edits.patch` 的空白上下文行报尾空格。这是原始 diff 语法的一部分；为保留归档字节，仅该历史归档免于尾空格格式检查，其 SHA 与暂存字节仍严格核验。其余新增代码、可读文档和 JSON 的暂存格式检查通过。原失败与限定复核记录保存于 artifacts/ns_p2b/commit_validation.json；未改算法或实验产物。


## 2026-11-02 NS-P3a 完成：原名事实与语义验收（修改 AI：Codex）

输入 node-sem@e62d56e5、PROMPTS r9。按用户后续指令只使用 original，新 extract 拒绝 anonymous；旧8H仅定位固定原图/源码/证据，匿名产物只读保留。后续正式训练要明确原名配置和原名S0基线，不得直接复用匿名8H得分。当前政策见 EXPERIMENT_POLICY.md，旧训练入口本轮未改。

新增 facts_schema/ast/guards/cfg/io/facts/acceptance/verify，7组测试、38个手写Solidity fixture与期望、behavior_coverage.md、NS_P3A_REPORT。实现声明身份绑定、通用调用/算术/状态/环境/守卫/函数上下文、精确投影、封存证据连接、语义CFG顺序与K/L/M汇总；没有新增图节点/边、改标签/特征或HGT。绝对位置仅用于内部身份，不能进入特征。

用户已批准：严格布尔极性；唯一同文件一层运算检查；从封存完整symbol ID精确重建声明表；金额/混合返回处理unknown；共享基类声明按确认身份汇总授权而函数/合约保持作用域。选择详情与实际接口见 training_changes§77、decisions.json。审查修复已确认库调用误归外部、未知modifier误计无保护、未投影状态写/继承完整性、++/delete及未知storage alias的顺序unknown传播；未扩展冻结分析器。

最终输入目录是 artifacts/facts_v1/accepted_attempt2/original，CURRENT.json指向它；旧根original/与首次smoke保留superseded。四任务事实依次18610/12223/13693/7892，共52418行，与原名text_v1身份/顺序/源码SHA一致；24681次L1完整身份查找通过。CPU全量183.048秒。原稿对比1183行仅授权/完整性/unknown原因变化，无节点/真实依赖变化。

另外五类固定50源码、2098函数、8016行，0解析失败/异常，16.296秒；纯源码DFG/CFG事实unknown。不是五类完整图特征或编译验证。state未知率较高，仍受冻结L2绑定/别名和保守函数传播限制，不能把unknown解释为无漏洞、无读写或无保护。

最终测试496 NodeSem＋2653 DFG v2＋223原回归＝3372通过，0失败/跳过，42条既有弃用警告。命令见accepted_attempt2/final_tests.json；8H有效runtime只读核验通过，22813冻结文件字节不变。runtime_closure/final_validation/verification.seal绑定输入、完整代码依赖与四份产物。详细覆盖、统计分母、剩余边界见NS_P3A_REPORT。

本轮无GPU、训练、编码、solc编译、CTX/STATIC，不推进NS-P3b。最终实验按用户计划使用显存充足服务器，本机RTX3050 4GiB仅为开发限制；尚未部署服务器。本地提交，不自动推送；三份文档仅追加并做UTF-8/CJK校验。

## 2026-11-02 NS-P3a2 完成：状态支持精确化与析取守卫（修改 AI：Codex）

原实现把 L2 的 require/assert/now 等非状态名字诊断传播为整个函数 state unknown，并把未投影 emit 等缺口传播到整组 K/L/M。本轮按原 AST 角色/位置限定未知作用范围，完整 AST 计算非状态汇总，K 使用全部封存 L2 访问（含未投影）。原图与读写/DFG事实不变。

新增 facts_state、facts_summary、facts_boolean、facts_revision_audit，修改 facts/schema/ast/guards，增加 ii–nn Oracle 和 precision/names 测试。schema 升至 v1.1，K/L/M unknown_fields 必须由后续编码逐字段消费。用户批准逐字段掩码、补齐 order.status/诊断允许差异、受限布尔 token 分组适配；具体选择与理由见 training_changes§78、NS_P3A2_REPORT 与 decisions.json。

四任务52,418行 accepted_attempt3 已通过逐行比较，非允许变化0；旧attempt2全部36文件SHA不变。state unknown（重入合约/重入节点/访问控制合约/访问控制节点）从6627/4350/5947/3774降至78/32/75/29，分母仍10067/6635/7858/4664。析取守卫记录14/14/23/16，新授权声明图节点2/2/4/4；跨任务有重叠，不能相加当独立源码样本。旧逐行state诊断计数保留，精确原因另存。

最终587+2653+223=3463测试通过，0失败/跳过，42条既有警告；44 Oracle名字双射及6份封存层对照通过。另五类50源码、2098函数、8016行冒烟0异常。facts_verify核验22813冻结文件及8H生效运行版本通过。CURRENT指向attempt3，旧产物只读保留；详细表、执行命令与限制见报告。

生产仅original，不读取匿名特征/评分，不做真实语料改名；没有GPU、训练、编译、M2/STATIC编码或NS-P3b，无新的F1结论。最终实验计划使用显存充足服务器，本机RTX3050 4GiB仅为开发限制，服务器未在本轮部署。三文档只追加、UTF-8/CJK校验；本地提交，不自动推送。
