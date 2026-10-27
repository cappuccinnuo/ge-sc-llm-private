# DFG v2 实施记录

## 2026-10-23 · Prompt 0 · Codex

范围：仅侦察、输入核验与原标量层基线复跑。未开始 Prompt 1，未实现新 DFG 算法，未训练模型。

### 新文件

- `recon_graphs.py`：源码身份、AST精确投影、图/schema计数与原/支持视图分别核验。
- `recon_tokens.py`：离线冻结抽样、800个token向量重新编码逐元素比较与来源核验。
- `recon_protocol.py`：实际配置、冻结内外层划分、历史90次fit的资源记录核验。
- `recon_scalar.py`：调用未修改的旧scalar profile，保留文件级失败分母及回退原因。
- `recon_report.py`：将已有证据渲染为报告，拒绝覆盖已有报告，不包含分析算法。
- `RECON.md`、`recon.json`：人可读与机器可读验收结果。
- `PROGRESS.md`：本记录。完整审计与新基线图位于 `scripts/DFG/experiments/artifacts/dfg_v2/recon/`。

### 批准的调整

原 SourceView 的AC合约锚点仅804/922=87.20%，已按门槛暂停并询问。用户批准复用已有 SupportedSourceView 及绑定的版本元数据；批准后872/922=94.58%。R合约2360/2369=99.62%，R节点1788/1788、AC节点403/403。未知版本仍回退，不新增状态节点。原视图失败证据保留；旧 scalar 对照不采用这个变更。

### 验收结果

- token：每任务200个，800/800逐元素一致；实际是本地补入的CodeT5p-770m tokenizer ID，float32[512]，没有加载encoder。
- 原scalar四任务新增边3561/4032/1894/2836，支持函数2035/3404、2128/3148、1210/2045、1550/1958。
- 回归：`python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py`，223 passed，29个现有弃用警告，0 failed。
- 4/4原nested划分可由现有算法在内存精确重现；没有改写冻结名单。
- 11063个受保护的已跟踪文件SHA保持一致，PROMPTS.md不变；旧15个未跟踪路径保留。新产物是文档明确指定路径，未清理旧工作区。

### 处理与限制

- 当前分支已是dfg-v2，无需重新checkout。fetch因DNS失败，不能声称核验了远端最新；不push、不reset、不迁移。
- Prompt 0要求“不修改任何已有文件”与共享上下文要求追加旧HANDOVER/training_changes冲突。本轮按具体Prompt0限制只写新记录；旧文档未改。
- 未做solc编译、模型训练或v2模型构造；不把解析通过写成编译通过。
- 不保证缺失emit/revert投影能恢复；不对作者标签的语义正确性作新结论。
- 后续协议建议（G*使用outer-test选型、nested checkpoint适配）详见RECON；尚未实施，先征求用户。

### 下一步

Prompt 0数据与回归验收通过，下一步是Prompt 1骨架及模型输入；本轮停止，不自动展开后续阶段。

## 2026-10-23 · Prompt 0三文档补齐与GitHub同步暂缓 · Codex

### 本次授权与当前状态

用户在P0验收后明确要求更新HANDOVER、详细training_changes和本PROGRESS，并更新GitHub；随后因WSL无法解析GitHub，明确要求先不推送、等网络解决再推送。已停止网络排查，本次只完成文档与本地提交。

上一节“旧文档未改/不push”是P0初次执行的历史边界。当前已按新的明确授权向旧文档追加；旧段落保留，不删除历史过程。P0代码提交为 `085eb86e14f9d13f19a4f6ba937fb3fce279e13b`，分支 `dfg-v2`。本次没有开始Prompt 1，没有修改新旧分析算法或训练规则。

### 三份文档的分工

- `HANDOVER.md` 新增“2026-10-23 DFG v2 Prompt 0完成及三文档补记”：简要说明版本、已批准选择、验收结果、限制和下一步。
- `docs/training_changes_2026-10-07.md` 第38节：按既有格式详细记录12小节，包含8个新增文件职责、方案选择表、暂停/批准过程、两种源码视图的数值差异、输入图身份、token编码、实际学习率/早停、冻结划分、scalar对照、测试、历史资源及同步暂停原因。
- 本 `PROGRESS.md`：更新当前实施状态并指向上述详细记录。三个文档仅追加，旧字节前缀核验；正文编码为UTF-8。

### 决策与数值对齐

唯一已批准调整仍是已有SupportedSourceView＋记录的版本元数据，未知情况回退。AC合约由原SourceView804/922=87.20%变为批准视图872/922=94.58%；R合约2360/2369=99.62%，节点R1788/1788、AC403/403。原失败证据不改；原scalar对照仍使用旧pipeline。token800/800一致，旧回归223通过。G*外层测试选型与nested checkpoint适配仍是未实施、待确认建议。

本轮只做文档一致性/保护检查，不重复执行已完成的223项代码回归，不将旧测试时间冒充本轮重跑结果。详细出处仍为RECON.md、recon.json及artifacts/dfg_v2/recon/，新增文档核验收据在同批 `documentation_update_20261023_v1/`。原保护快照不改写为本次文档变更后的状态。

### 待推送状态与下一步

WSL fetch因DNS失败；Windows只读连接尝试因认证助手不可用失败，均未成功核验实时远端。未push、不force、不迁移/覆盖旧实验；用户要求暂停后没有继续访问远端。完成本地提交后保持待推送，不能声称本地/远端一致。后续恢复时先fetch核对远端，再推dfg-v2并验证commit SHA一致。仅本开发分支更新，未改其他工作树文档或合并到main。

下一实施阶段仍为Prompt 1；本次文档整理不授权自动开始后续算法或完整训练。修改、审阅与记录AI：Codex。

## 2026-10-23 · GitHub推送恢复 · Codex

用户重新授权后已成功将Prompt 0提交085eb86和三文档提交e76eec1正常推送到origin/dfg-v2。原“暂缓/待推送”段落表示此前状态，现由本条补记更新；详情见training_changes第38.13节。

原因核查：WSL仍无法解析github.com；Windows Git可以联网，但需要显式调用WSL现有gh凭据助手。临时Git命令配置解决认证调用后fetch/push成功，没有出现分支保护或审批策略拒绝，不是本地commit未成功。未修改全局设置、DNS、代理，也未输出凭据。

本状态补记同样在dfg-v2提交并推送，最终按本地HEAD与实时远端SHA一致验收；不合并其他分支、不上传未跟踪实验资产。Prompt 1仍未开始，代码/图/标签/训练规则不变。修改与核验AI：Codex。


## 2026-10-23 · Prompt 1骨架、模型输入与模型构造完成 · Codex

### 版本、范围与批准记录

本轮从远端修订1f2a3088d3f5299a89e18b4f8e203412cf2faaaa开始，先读第4.1节共享上下文与Prompt 1。通过已有Windows Git操作同一WSL工作树，pull --ff-only origin dfg-v2返回Already up to date；无checkout/reset或全局配置修改。仅做Prompt 1，未开始Prompt 2、程序分析或训练。

唯一方案偏差：文档要求测试“原reflect会把同类型DATA_DEF_USE变双向”，但当前graph_utils已修复为单向。先询问，用户明确选择“同意按当前代码事实修正测试（推荐）”。新测试固定真实行为：DATA_DEF_USE单向、普通next_line反射、G3R另生成显式REV_DATA_DEF_USE。旧代码与PROMPTS正文不改。

新版PROMPTS已确定SupportedSourceView、ProjectionView、G*只按inner val选择、nested checkpoint包装。P0中“待确认建议”是历史状态；本轮遵循新文档，尚未实施这些后续Prompt。

### 文件与核心逻辑

新增8个文件，均位于dfg_v2：

- __init__.py：VERSION、4个正向关系、4个REV关系、env_source及G0–G3R常量。
- model_input.py：原边沿用原reflect；新正向不反射；G3R仅在模型输入生成REV。拒绝不允许的profile/关系、REV输入、冲突及类型内行号错位。
- model.py：继承原节点/合约forward；按原顺序创建adapt_ws→gcs→classify；支持inside_token/nodetype；复用旧schema检查，另核对v2端点、特征、标签和辅助掩码。
- supervision.py：固定图文件监督；节点mask排除env_source，合约池化排除env_source。辅助行内部-1只是忽略哨兵，不写回图或伪造clean标签。
- hgt_layer.py：可选nonempty_mean诊断，保留原构造及除跨关系聚合外的forward；按DGL canonical ID对齐stack与逐节点入度掩码。默认mean仍用原HGTLayer。
- tests/test_model_input.py、test_model.py、test_hgt_layer.py：分别32、28、5项测试。

复制来源均有路径与完整SHA；无FunctionType重绑定。原HGT已有无入关系时零消息处理，无须为env_source修改冻结核心。

### 测试覆盖与结果

| 测试组 | 通过 | 覆盖性质 |
| --- | --- | --- |
| model_input | 32 | G0键顺序/张量与原reflect及Stage F一致；DDG同/异类型单向；4类REV交换端点；非法输入拒绝；孤立节点、平行边及图fingerprint保持；批准后的历史反射行为 |
| model | 28 | G0两任务state_dict/RNG/eval与train forward/监督manifest等值；nodetype与原生产构造等值；G1–G3R前后向及新关系梯度；aux不监督/不池化、独立adapt_ws及行对齐；错字典/特征/标签拒绝；诊断显式启用 |
| hgt_layer | 5 | dense两种norm输出误差≤1e-6及反向一致；初值/RNG一致；稀疏分母、空关系、零入度、无入边环境节点与local_scope |
| 原DDG+graph_utils | 223 | 既有回归不退化 |

使用minimal.sol经原生成器产生小HCG，512维float32零token，手工边仅验接口。v2合跑65 passed、0 failed/skipped、8条弃用warning；旧回归223 passed、0 failed/skipped、29条既有warning。共288通过，不代表全仓库测试全集。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

证据：scripts/DFG/experiments/artifacts/dfg_v2/prompt1_v1/的before.json、两组完整log/JUnit、validation.json。11060个受保护已跟踪文件SHA与PROMPTS不变，三份记录只追加并核验旧字节前缀；详见training_changes第39节。

### 限制与下一步

只打通已有关系→DGL→原HGT→监督/反向。L1/L2/L3语义分析、新env token编码、真实图覆盖、nested训练/checkpoint、GPU显存验收和新图推理未在本步完成或运行。继承的旧extend_forward不是已验收v2推理入口，后续按Prompt 9单独实现；诊断聚合不替换主mean。

未发现本步阻断；不据小图通过声称完整DFG或效果提升。按共享上下文完成Prompt 1本地提交，未push，停止于Prompt 1。实施、复核与记录AI：Codex。


## 2026-10-23 · Prompt 1b双向主剖面完成 · Codex

### 选择与版本

用户明确选择双向并要求执行Prompt 1b。本轮基于0449355cb1b644869a45b747ad76198250783ef1，先读共享上下文与最新Prompt，pull --ff-only origin dfg-v2确认Already up to date。没有checkout/reset或覆盖历史批次。P1的G1/G2配置和“仅G3R显式反向”是历史状态；本条更新当前实现，不改旧记录。

默认配置现为G0、G1R、G2R、G3R、G3。主增强链为G1R→G2R→G3R，G3保留完整正向作为方向对照。移除默认G1/G2，不加静默别名；临时注册单向G1后模型无须改代码，两个任务与冻结Stage G模型初值/前向精确一致。

### 文件与规则

- 修改__init__.py：新PROFILES、forward_relations、has_reverse；导入和动态读取均校验REV有正向配对。
- 修改model_input.py：逐关系按配置生成反向，env_source资格按ENV_FLOW声明。NetworkX只存正向，REV只在模型输入产生。
- 修改tests/test_model_input.py：43项，覆盖新配置、同图G3/G3R、原WRITES_STATE同/异类型反射混淆、错误配置/输入拒绝、节点与基础边保留。
- 修改tests/test_model.py：38项，覆盖两任务关系梯度、双向aux排除监督/池化、临时G1、相同初值下环境上下文干预。
- test_hgt_layer.py没有G1/G2引用，保留原5项并重跑；model.py、supervision.py、hgt_layer.py、原DDG/HGT/tokenizer/训练代码均未修改。

G3/G3R同一NX图只差REV canonical；新反向与正向参数按独立canonical注册。原DATA_DEF_USE单向特判和普通CFG/CG reflect不变。保留所有非法输入、跨文件连接、特征/标签/字典错位拒绝以及G0基线等价测试。

### 验收结果与证据

| 集合 | 通过 | 失败/跳过 | 警告 |
| --- | --- | --- | --- |
| v2全套：43输入＋38模型＋5诊断 | 86 | 0/0 | 8 |
| 原DDG＋graph_utils | 223 | 0/0 | 29 |

合计309项，不重复计算定向运行，不声称全仓库测试全集。警告仅为已有DGL/NetworkX弃用。沿用mando、CPU、2线程和已有grammar：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

新增证据目录artifacts/dfg_v2/prompt1b_v1/：before.json、两组log/XML、environment_context_probe.json、validation.json。11072个受保护已跟踪文件SHA不变，三文档只追加并核验旧字节前缀；详细变更和选择见training_changes第40节。

环境测试在各profile内部用同权重仅改second.sol使用向量，并读取真实两层HGT输出。两任务均：G3两文件同键env差为0，使用处扰动不改变env；G3R两层env差0.22999882698，扰动文件env变化0.23695075512，未扰动文件变化0。按文件＋类型内行号定位，验证实际信息接入而非仅检查新增边存在。

### 表述限制与停止点

固定的是输入token；无入边env仍有可学习投影/偏置/残差/norm，不能说每层就是固定原始token。单向只限制相应关系的消息路径，原节点仍可能经CFG/CG收到其它上下文。“ENV_FLOW收益最大”及F1改善均尚未验证；同文件共享环境节点也不是相同交易/调用者证明。以上仅澄清理由，不修改用户已批准方案。

没有fit、optimizer.step、GPU预检、solc、真实v2语义图生成或新成绩；手工特征小图只验路由，不证明分析器完整性。未开始Prompt 2。按共享上下文本地提交Prompt 1b后停止；本轮未push。实施、复核、记录AI：Codex。


## 2026-10-24 · Prompt 2 L1扩展与四任务验收完成 · Codex

### 版本与范围

起点55260099dc53603d5cc6f5a7a803d77fd5d77f98，先读取共享上下文/P2及现有模块，pull --ff-only确认最新。Prompt 1b此前已推送；本轮仅新增v2内11个代码/测试文件并追加三份记录，未改旧DDG、HGT、tokenizer、标签、固定折或已有模型输入代码。无训练、solc或Prompt 3实施。

### 实现和选择

- l1_symbols.py、l1_models.py、l1_access.py：冻结V2Event、聚合符号附加信息、声明/作用域身份、整体强写及成员/下标/push/pop/delete弱写。
- l1_cfg.py：只替换Stage J的table/access，继承原CFG和受限modifier/继承/终止调用处理；构造复制来源有SHA。
- l1_rd.py：复制有SHA的原solver，弱写只GEN、强写KILL，块内顺序重放一致，兼容旧IR。
- l1.py：旧成功函数直接复用，失败函数才重试；整体失败无残留；每条事实按产生视图投影、去重、过滤共享modifier锚点并保留证据。
- l1_build.py：冻结输入/P0绑定、旧逐函数/逐边/solver/Projector验收、新G1R CPU模型注册、不覆盖输出。
- tests/test_l1_access.py、test_l1_rd.py、test_l1.py、test_l1_build.py：最终分别38/30/19/9项。

未提出或实施替代设计。必要兼容处理：grammar把delete a[i]解析成array_access(base=unary(delete,a), index=i)，v2只适配顶层AST目标链，保持锚点；嵌套/索引写仍回退，原parser不改。ordinary call聚合参数只记读，是文档已明确的近似，不分析引用副作用或跨函数alias。

### 真实数据验收

| 任务 | 旧支持→新支持/全部函数 | 支持率前→后 | scalar边→L1边 |
| --- | --- | --- | --- |
| 重入合约 | 2035→3128 / 3404 | 59.78%→91.89% | 3561→5659 |
| 访问控制合约 | 2128→2791 / 3148 | 67.60%→88.66% | 4032→5713 |
| 重入节点 | 1210→1960 / 2045 | 59.17%→95.84% | 1894→3419 |
| 访问控制节点 | 1550→1856 / 1958 | 79.16%→94.79% | 2836→3889 |

P0分母与输入身份逐SHA一致；原节点/属性/标签/token/CFG/CG边完全不变。6923个旧成功任务内函数实例的完整RDResult相同，旧投影事实/边逐项相同；包括零投影事实函数569/286/382/159。两种视图by_ast一致文件实例136/102/69/55，modifier锚点事实丢弃数均0。

四个G1R CPU模型schema通过，inside_token宽度512；DATA_DEF_USE正向canonical为21/22/21/22，显式REV同数，总42/44/42/44。新关系清单及各边数见model_schema.json。未在真实图上forward、训练或计算F1。

### 审计修正、最终路径与测试

首轮恢复route遗漏无名称聚合参数/返回值，因为没有Symbol ID。已改为检查成功接受的声明类型，并为前缀AST兼容记录v2_access_shape；添加2个回归。修正只影响审计routes，不改事实或模型计算。

首轮artifacts/dfg_v2/l1_build/不覆盖；最终产物为其final_route_audit/子目录。四任务重新验收，首轮与最终的computation_fingerprint及投影事实身份完全一致，证明不涉及重新选择更有利结果。

最终v2 182 passed、旧DDG+graph_utils 223 passed，共405；0失败/跳过，8/29条已有弃用warning。证据artifacts/dfg_v2/prompt2_v1/包含完整log/XML、两轮构图日志、route_correction_comparison.json及validation.json。11077个受保护文件SHA不变，三文档仅追加。详细代码、选择、route交叉表/Top10解释和命令见training_changes第41节。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l1_build --output scripts/DFG/experiments/artifacts/dfg_v2/l1_build/final_route_audit
~~~

以上是实际执行命令；输出已存在，重跑需要新路径。完整逐函数记录和旧原因→新route/仍回退原因在最终audit与summary JSON。

### 限制和下一步

仍回退276/357/85/102个函数，原样本/HCG保留。主要为复杂modifier、无可靠版本、assembly/new/inline-array/嵌套写。var tuple仍回退。聚合基变量合并字段/元素，不代表精确别名或完整Solidity数据流；扩大覆盖不保证F1提升。所有本轮Solidity测试均未独立编译。

Prompt 2已完成；下一步Prompt 3的L2状态锚点尚未开始，L3和训练也未开展。按共享约定本地提交后停止，本轮未push。实施、复核与记录AI：Codex。


## 2026-10-24 Prompt 3：L2状态声明中转关系完成

起点dfg-v2@80afa66681ba46f848472895eae6871957a3c7ec，远端同一HEAD。沿用最新§4.1，原作者代码、冻结DDG、HGT、tokenizer、训练规则、标签、折和旧产物不变。实施、复核与记录AI：Codex。

### 实现和已批准的调整

新增projection_view.py、units.py、access_shape.py、state_binding.py、state_access.py、l2.py、l2_projection_audit.py、l2_build.py及8个同名测试文件。既有代码仅l1_access.py将前缀delete/update形状识别抽到共享纯函数；原行为以四任务L1重建逐fingerprint证明保持。三文档只追加，详细逐文件说明与选择在training_changes第42节。

ProjectionView保留原SourceView的token一致性及raw/compat映射，只不推断lexical scope mode；L1不使用它。Units只分析节点自己的表达式区域；if/while只看条件，for独立子节点自己负责，未映射emit/revert不挂父节点。StateBinder按整个callable保守遮蔽，唯一C3状态绑定，Unsupported时当前合约唯一声明回退，常量默认排除；storage别名只支持直接状态根及有限多目标并集。

用户批准（call_813c0a5a2e4e40c890a79d25c61b0f9a）不按名字把所有push/pop认作状态写入。现核验实际接收者类型，只有动态数组/bytes写入；合约对象、固定数组、未知类型等保留可确认读取并记录跳过原因。字段/元素/alias使用选中位置的类型，避免只看根状态变量。legacy隐式storage仅限有版本证据的局部引用，不泛化至参数/返回值。revert_arguments实际AST包装的读取遍历已修正；缺HCG节点仍unmapped。

修复前2项push/pop回归失败，修复后相关72项通过。初次push_pop_review顶层source字段被后续语料覆盖，旧记录保留；corrected记录给出正确反例SHA、旧事件和修复后重探，重新核验70处语料出现。它是审计说明修正，不是图或标签修改。

### 真实数据验收

| 任务 | 文件/原节点 | 原Supported锚点→当前锚点 | WRITES | READS | L1回退中有L2/总数 | 回退函数贡献边 |
| --- | --- | --- | ---: | ---: | --- | ---: |
| 重入合约 | 142 / 18312 | 2360/2369→2369/2369 | 3108 | 4314 | 182/276 | 480 |
| 访问控制合约 | 114 / 13432 | 872/922→922/922 | 1609 | 2208 | 224/357 | 707 |
| 重入节点 | 71 / 12036 | 1788/1788→1788/1788 | 2254 | 3070 | 51/85 | 195 |
| 访问控制节点 | 57 / 7710 | 403/403→403/403 | 767 | 1091 | 72/102 | 284 |

SourceView可用文件的mapping/compat_ids/compat_nodes全部相同，四任务136/102/69/55个文件实例，共362。ProjectionView恢复8文件59锚点，失败文件0。锚点100%不代表全部访问可投影。unmapped出现219/228/101/93，anchor_missing均0；原图节点/key/属性/标签/token、原CFG/CG与5659/5713/3419/3889条L1边全部保留。

| 任务 | 跨callable写读对 | alias边/比例 | L2 canonical含REV | G2R参数量 |
| --- | ---: | --- | ---: | ---: |
| 重入合约 | 10667 | 231 / 3.1124% | 16 | 5003026 |
| 访问控制合约 | 7009 | 148 / 3.8774% | 18 | 5019442 |
| 重入节点 | 7692 | 223 / 4.1886% | 16 | 4847074 |
| 访问控制节点 | 3974 | 148 / 7.9656% | 18 | 4937362 |

跨callable对仅表示同声明共享的写读上下文，排除initializer，不保证可行执行路径。Top10声明读出度/写入度及完整unresolved分布见各任务summary.json；所有canonical和边数见model_schema.json。热点不截断，REV逐关系与正向边数一致。四个CPU G2R模型构造/schema通过，512维特征不变；真实图未前向或训练。

### 测试、保护和产物

新增162项回归；全部v2 344 passed、旧DDG+graph_utils 223 passed，合计567；0失败/跳过，8/29条既有弃用warning。log/XML及修复前后证据在artifacts/dfg_v2/prompt3_v1/。L1四图完整与计算fingerprint均和P2最终图相同。独立只读复核355项runtime SHA与四任务输入/图/源码链式摘要通过。

最终产物为artifacts/dfg_v2/l2_build/，每任务含hcg.gpickle、audit、inputs、acceptance、model_schema、edge_sample、manifest、summary；批次receipt绑定runtime和所有任务。ProjectionView普查在prompt3_v1/projection_audit/。输入为P2的l1_build/final_route_audit/，无覆盖。最终validation另核对11087个受保护已跟踪文件和三文档旧字节前缀；提交SHA在独立commit_receipt记录。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES= python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_projection_audit --output scripts/DFG/experiments/artifacts/dfg_v2/prompt3_v1/projection_audit
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_build --l1-directory scripts/DFG/experiments/artifacts/dfg_v2/l1_build/final_route_audit --output scripts/DFG/experiments/artifacts/dfg_v2/l2_build
~~~

命令输出已存在，再运行须换新目录。未执行solc编译，测试不等同语言合法性已验证。L2不做精确字段/别名/callee摘要或跨函数RD；没有原HCG节点的事实继续丢弃计数。尚无检测效果结论。Prompt 3完成后本地提交，未push，未进入Prompt 4/L3或训练。

### 固定抽样端点源码（20条）

各任务分别seed=0抽20条unique L2边，共80条；独立Codex对80条边/85处出现（5条alias边）做源码与证据复核，没有发现具体错误。下面按固定任务顺序各取其既定样本前5条，共20条，完整展示两端源码，不按结果挑例。完整80条及审核身份保留在edge_sample.json和manual_edge_review.json。此为AI辅助复核，仍待领域专家确认。

源码从inputs绑定的文件、audit中的精确AST字节跨度提取。if节点源码可能包含函数体片段，但READ/WRITE只来自其condition region，不会因展示完整AST文本而纳入子语句。source/target ID是已有HCG节点身份。

#### P3 sample 1: reentrancy_author_contract / buggy_20.sol / WRITES_STATE

- HCG: 7386 -> 7381; via_alias=False; source SHA256=76d607594dc5be00d665f8948c880d9823ae65efe29e27cedb811d3abb670af5

Source (raw lines 479-479, bytes 16780-16823):

~~~solidity
jackpot_re_ent2    = address(this).balance;
~~~

Target (raw lines 474-474, bytes 16601-16622):

~~~solidity
uint jackpot_re_ent2;
~~~

#### P3 sample 2: reentrancy_author_contract / buggy_23.sol / READS_STATE

- HCG: 5677 -> 5680; via_alias=False; source SHA256=0ea2e8d84a5c1f18db073809e603c2c5743af4f0f139dd613c168982b339fa56

Source (raw lines 368-368, bytes 13439-13475):

~~~solidity
address payable lastPlayer_re_ent30;
~~~

Target (raw lines 371-372, bytes 13551-13619):

~~~solidity
if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
        revert();
~~~

#### P3 sample 3: reentrancy_author_contract / 0x634446285f22aa660b36424ecd27455ab9bde51c.sol / WRITES_STATE

- HCG: 3780 -> 3776; via_alias=False; source SHA256=147024d9c713ee84dfb8fc252636d3ecabebb61708af7d8471b917f9d0e0f255

Source (raw lines 435-435, bytes 11304-11321):

~~~solidity
symbol = _symbol;
~~~

Target (raw lines 430-430, bytes 11164-11185):

~~~solidity
string public symbol;
~~~

#### P3 sample 4: reentrancy_author_contract / buggy_19.sol / WRITES_STATE

- HCG: 94 -> 80; via_alias=False; source SHA256=20ff5ab2123fdff3afefefc8e3c7abd3b292fe329badcd552b4c08fc10018d08

Source (raw lines 94-94, bytes 2324-2341):

~~~solidity
owner = newOwner;
~~~

Target (raw lines 64-64, bytes 1511-1532):

~~~solidity
address public owner;
~~~

#### P3 sample 5: reentrancy_author_contract / buggy_34.sol / READS_STATE

- HCG: 6880 -> 7134; via_alias=False; source SHA256=2182dadd5be822e13020b02e918d2d0eddaf942f26fc11ca9c5af2104b3d6dc4

Source (raw lines 161-161, bytes 4768-4823):

~~~solidity
mapping (address => transferMapping) private _balances;
~~~

Target (raw lines 669-669, bytes 22249-22314):

~~~solidity
_balances[account].amount = _balances[account].amount.sub(value);
~~~

#### P3 sample 6: access_control_author_contract / buggy_24.sol / WRITES_STATE

- HCG: 728 -> 490; via_alias=True; source SHA256=1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b

Source (raw lines 596-596, bytes 22563-22610):

~~~solidity
user.currentStaticCommissionWithdrawAmount = 0;
~~~

Target (raw lines 272-272, bytes 9083-9129):

~~~solidity
mapping (address => User) private userMapping;
~~~

#### P3 sample 7: access_control_author_contract / 0x0e5632feb2c2619dba9c7e2dc5a7ed3fd14969da.sol / READS_STATE

- HCG: 6329 -> 6358; via_alias=False; source SHA256=20bb5bcde2e3db6ac2d2ba1a76d9fcda049716f273324f9e437ec09377c723f5

Source (raw lines 146-146, bytes 4611-4663):

~~~solidity
mapping(address => uint256[]) private ownedAuctions;
~~~

Target (raw lines 216-216, bytes 7345-7386):

~~~solidity
ownedAuctions[_from].push(lastAuctionId);
~~~

#### P3 sample 8: access_control_author_contract / 0x1b6ab9d402d37e99e453b0eca8254075922e289d.sol / WRITES_STATE

- HCG: 4902 -> 4886; via_alias=False; source SHA256=ee88135813a8224b7c9455c79f335d64116c772850184403b8bc1734e9e396ef

Source (raw lines 172-172, bytes 6039-6106):

~~~solidity
_allowed[from][msg.sender] = _allowed[from][msg.sender].sub(value);
~~~

Target (raw lines 106-106, bytes 3274-3341):

~~~solidity
mapping (address => mapping (address => uint256)) private _allowed;
~~~

#### P3 sample 9: access_control_author_contract / 0x0c7b8eedd028f3730e7b0f3dc032e916302f09b4.sol / WRITES_STATE

- HCG: 8880 -> 8856; via_alias=False; source SHA256=9338961d1813f14219e9c09d12788804f5f5a8ef6ace1b884ff104d363104a05

Source (raw lines 49-49, bytes 987-1000):

~~~solidity
locked=false;
~~~

Target (raw lines 7-7, bytes 280-306):

~~~solidity
bool public locked = true;
~~~

#### P3 sample 10: access_control_author_contract / buggy_50.sol / READS_STATE

- HCG: 7154 -> 7224; via_alias=False; source SHA256=c90006c8a348d37e9fca70098a17e57bcccf6e314a4f6cc640d2e32d887dcf26

Source (raw lines 14-14, bytes 324-356):

~~~solidity
address payable private manager;
~~~

Target (raw lines 147-147, bytes 4305-4320):

~~~solidity
return manager;
~~~

#### P3 sample 11: reentrancy_author_node / buggy_40.sol / WRITES_STATE

- HCG: 10821 -> 10732; via_alias=False; source SHA256=f530b30562180ec1150773025b7f45856c96a44121c5bc3bcdbf25be4cc03f64

Source (raw lines 429-429, bytes 15018-15068):

~~~solidity
_balances[sender] = _balances[sender].sub(amount);
~~~

Target (raw lines 224-224, bytes 7893-7940):

~~~solidity
mapping (address => uint256) private _balances;
~~~

#### P3 sample 12: reentrancy_author_node / buggy_48.sol / WRITES_STATE

- HCG: 13903 -> 13883; via_alias=False; source SHA256=1eacdda7fa2de58517083454d8de92932b7a0dec0eccfa1ac3a3081c085bf887

Source (raw lines 195-195, bytes 7634-7655):

~~~solidity
newOwner = _newOwner;
~~~

Target (raw lines 164-164, bytes 6770-6794):

~~~solidity
address public newOwner;
~~~

#### P3 sample 13: reentrancy_author_node / spank_chain_payment.sol / READS_STATE

- HCG: 12933 -> 12982; via_alias=False; source SHA256=15724a9aecd227749e4e3441bf408892ead6639d7c2830b116014183fb537d09

Source (raw lines 378-378, bytes 14625-14669):

~~~solidity
mapping(bytes32 => Channel) public Channels;
~~~

Target (raw lines 471-479, bytes 18908-19377):

~~~solidity
if (Channels[_lcID].partyAddresses[0] == recipient) {
             if(isToken) {
                 require(Channels[_lcID].token.transferFrom(msg.sender, this, _balance),"deposit: token transfer failure");
                 Channels[_lcID].erc20Balances[2] += _balance;
             } else {
                 require(msg.value == _balance, "state balance does not match sent value");
                 Channels[_lcID].ethBalances[2] += msg.value;
             }
         }
~~~

#### P3 sample 14: reentrancy_author_node / buggy_23.sol / READS_STATE

- HCG: 5619 -> 5622; via_alias=False; source SHA256=0ea2e8d84a5c1f18db073809e603c2c5743af4f0f139dd613c168982b339fa56

Source (raw lines 234-234, bytes 7931-7981):

~~~solidity
mapping(address => uint) redeemableEther_re_ent32;
~~~

Target (raw lines 238-238, bytes 8142-8209):

~~~solidity
uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
~~~

#### P3 sample 15: reentrancy_author_node / buggy_18.sol / WRITES_STATE

- HCG: 2893 -> 2774; via_alias=False; source SHA256=b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec

Source (raw lines 406-406, bytes 14895-14921):

~~~solidity
rewardEra = rewardEra + 1;
~~~

Target (raw lines 244-244, bytes 8337-8359):

~~~solidity
uint public rewardEra;
~~~

#### P3 sample 16: access_control_author_node / buggy_50.sol / WRITES_STATE

- HCG: 7230 -> 7154; via_alias=False; source SHA256=c90006c8a348d37e9fca70098a17e57bcccf6e314a4f6cc640d2e32d887dcf26

Source (raw lines 157-157, bytes 4613-4631):

~~~solidity
manager = newmngr;
~~~

Target (raw lines 14-14, bytes 324-356):

~~~solidity
address payable private manager;
~~~

#### P3 sample 17: access_control_author_node / buggy_21.sol / READS_STATE

- HCG: 5105 -> 5153; via_alias=False; source SHA256=a56027eab5cd86b394c4af105aa36f7fc91f24aefa636eaa2b640eb164a0402f

Source (raw lines 142-142, bytes 4542-4587):

~~~solidity
mapping(address=>uint256) public withdrawfee;
~~~

Target (raw lines 212-212, bytes 7457-7558):

~~~solidity
require(amount>0 && amount <= userDetails[msg.sender][address(0)] && withdrawfee[address(0)]<amount);
~~~

#### P3 sample 18: access_control_author_node / buggy_34.sol / WRITES_STATE

- HCG: 4544 -> 4518; via_alias=False; source SHA256=afe641e5e3e75ae90778bb8e27ca9b0af76c4d3f30ec4615b051a718f4646eb2

Source (raw lines 200-200, bytes 6394-6434):

~~~solidity
_maxTotalSupply = 1000000000 * 10 ** 18;
~~~

Target (raw lines 159-159, bytes 4939-4970):

~~~solidity
uint256 public _maxTotalSupply;
~~~

#### P3 sample 19: access_control_author_node / parity_wallet_bug_2.sol / WRITES_STATE

- HCG: 9516 -> 9610; via_alias=False; source SHA256=3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e

Source (raw lines 259-259, bytes 9473-9502):

~~~solidity
m_txs[o_hash].value = _value;
~~~

Target (raw lines 405-405, bytes 14314-14353):

~~~solidity
mapping (bytes32 => Transaction) m_txs;
~~~

#### P3 sample 20: access_control_author_node / buggy_4.sol / READS_STATE

- HCG: 5571 -> 5607; via_alias=False; source SHA256=1c963c08a66e6516d74a296676631091f82a275d88a8a1539eb7de6ba119114e

Source (raw lines 86-86, bytes 2766-2786):

~~~solidity
address public team;
~~~

Target (raw lines 141-149, bytes 4617-5136):

~~~solidity
if(msg.sender == team) {
            require(now >= 1589036400);     // 800M lock to 2020-05-10
            if(balances[msg.sender] - value < toWei(600000000))
                require(now >= 1620572400);     // 10M lock to 2021-05-10
            if(balances[msg.sender] - value < toWei(400000000))
                require(now >= 1652108400);     // 10M lock to 2022-05-10
            if(balances[msg.sender] - value < toWei(200000000))
                require(now >= 1683644400);     // 10M lock to 2023-05-10
        }
~~~


提交前补充：对新增文件执行暂存区格式检查时，发现 l2.py、projection_view.py、tests/test_l2.py 各多一个文件末尾空行；未发现其他格式问题。为保持已验收源码与四任务产物的 SHA 绑定，不再改动这三个文件。最终格式检查仅在该次命令中关闭 blank-at-eof 提示（未修改 Git 配置），其余空白错误检查仍启用；默认检查输出及此处理记入 staging_validation.json。这是格式提示，不涉及计算或测试结果。


## 2026-10-24 Prompt 4.0：L2三个正确性修订与独立重建（Codex）

按更新后的PROMPTS.md（47f3f2c）先完成Prompt 4第0部分，未改变方案，也未提前加入L3文件。修改state_access.py让struct_field_assignment只访问value字段，避免把call选项名value/gas误读为状态；state_binding.py把精确string/bytes类型计入有版本证据的legacy局部storage引用，bytes1…bytes32不纳入；units.py增加try_statement的attempt区域，缺HCG节点计unmapped，不挂函数节点。l2.py/projection_view.py/tests/test_l2.py仅删除末尾多余空行。

新增test_prompt4_zero.py共20项，实际grammar先行核验。相同测试修复前10 failed/10 passed；修复后连相关既有测试126 passed。最终全v2 364 passed、旧DDG+graph_utils 223 passed，共587项，0失败/跳过，8/29条既有弃用warning。测试包含版本不确定、显式memory/calldata、var字符串/字节引用、名字字段和接收者读取、try独立归属及图不变量。仅解析器/语义测试，未执行solc。

四任务已重建至artifacts/dfg_v2/l2_build_r1/，原l2_build/只读保留。逐任务新增/删除边均0，边属性变化均0，完整图fingerprint全部一致。unmapped仍219/228/101/93，alias绑定仍45/29/42/29，WRITES/READS仍3108/4314、1609/2208、2254/3070、767/1091。说明这些反例缺陷确实已由回归覆盖，但本批真实图未触发改变投影结果的情况；不能据“图相同”认为修复无效。

后续L3及G2R使用l2_build_r1/。不重跑L1：本次修改的units/state_binding/state_access不在L1导入路径，l1*.py与其旧依赖SHA均保持，EOF清理无计算改变。P2最终L1作为输入仅核验manifest/SHA，不覆盖。原标签/token、CFG/CG、HGT和训练逻辑保持。

实际命令（环境同§4.1）：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_build --output scripts/DFG/experiments/artifacts/dfg_v2/l2_build_r1
~~~
输出已存在，禁止覆盖重跑。证据在artifacts/dfg_v2/prompt4_v1/p4zero/，包括grammar_probe、before/after、全回归日志/XML、rebuild.log和逐任务comparison.json（边差异证据列表为空）。本阶段单独本地提交“Prompt 4.0”，随后才实现第1–5部分；未push、未训练。实施、复核与记录AI：Codex。


## 2026-10-24 Prompt 4 L3实施中：等待一项已确认的AST适配决策（Codex）

阶段4.0已提交71f19dc，后续实现目前尚未提交、未封存L3正式产物。新增env.py/tokens.py/l3.py/l3_build.py/l3_forward.py及test_env.py/test_tokens.py/test_l3.py/test_l3_build.py。已完成14键/18写法、词法遮蔽和明确import别名、辅助节点旁路叠加、离线冻结token编码、L2链式绑定及隔离CPU前向验收入口。未修改HGT、tokenizer原逻辑、训练脚本或原图标签。

独立定向测试：env 63项、tokens 42项、archive/forward guards 24项通过；L3集成除下述待决策反例外23项通过（1项明确deselected，不计作全套通过）。重入合约原图token离线抽样20/20逐位一致。首次集成测试另有5项因共享合成夹具正例缺category而失败，现仅补齐新测试夹具schema；没有修改真实标签、模型或降低断言。真实L3四任务构图和8次CPU前向尚未执行，无训练。

阻断反例：实际grammar把msg.gas + gasleft()解析成call_expression(function=binary_expression(...,gasleft))；this.balance + address(this).balance的最外member对象也可能是binary_expression。按文档仅识别裸function/direct object会漏识别合法写法。完整20例探针在prompt4_v1/env/call_precedence_probe.json。保留test_spellings_merge_per_file_and_edge_not_per_occurrence的失败断言，没有用改写源码或删测试掩盖问题。

已通过异步问题请求用户批准“受限AST后缀适配”：仅沿已确认的未加括号binary右侧/unary参数恢复已知ENV调用/成员，继续检查遮蔽；不越过显式计算括号，不修改grammar、源码、HCG或模型。此项超出文档字面AST匹配规则，按用户“替代方案须先征求同意”要求暂未应用。备选是保留规则并明确漏识别限制。待答复后继续完成测试、真实图验收、详细记录和Prompt 4第二次提交。状态证据在prompt4_v1/pending_decision.json。实施与记录AI：Codex。


## 2026-10-24 Prompt 4验收完成（Codex，接续待审批记录）

用户已批准 call_a73e5a2e373d45e8984d39d0f0d288e0 的受限AST后缀适配；pending_decision保留为历史，approved_decision单独记录。先前“未完成”的条目在此得到完成续记。P4.0已提交71f19dc，第1–5部分独立本地提交，不push。

新增文件：env.py、tokens.py、l3.py、l3_build.py、l3_forward.py，以及tests/test_env.py、test_tokens.py、test_l3.py、test_l3_build.py。旧计算文件无进一步修改。完整实施选择、函数职责、修复理由和边界见training_changes第45节。

关键约定：14键/18写法；每文件每键一个有已投影用途的env_source；保留原9属性并仅加dfg_v2_aux；token float32 ndarray[512]按固定离线tokenizer完整编码再裁剪/右补0；原节点hetero行顺序/标签/token及基础/L1/L2边完全不变。env_source不在节点监督或合约池化，实际训练读取路径不调用需要source_path的函数；method空及源码行空符合当前十属性schema。REV仅在模型输入生成，G3/G3R共享前向NetworkX图。

测试：获批后缀84项修复前13失败、修复后全通过，集成原强断言保持；最终v2 538 passed/8 warnings，旧DDG+graph_utils 223 passed/29 warnings，0失败/跳过。所有warning为既有DGL/NetworkX弃用提示。四任务token抽20条共80/80逐位一致，全部图不变量和独立来源核验通过；8次真实图CPU eval/no_grad、无loss/backward/optimizer。完整命令与路径见第45.8节，下方再列测试入口。

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l3_build --l2-directory scripts/DFG/experiments/artifacts/dfg_v2/l2_build_r1 --output scripts/DFG/experiments/artifacts/dfg_v2/l3_build
~~~

构图命令已完成，已有输出拒绝覆盖。设置环境沿用§4.1的mando/TREE_SITTER_LIB_DIR/PYTHONDONTWRITEBYTECODE/OMP_NUM_THREADS/MKL_NUM_THREADS。
| 任务 | 文件 | 原节点 | env节点 | ENV_FLOW | unmapped出现 | L1回退中有ENV的函数/回退总数 | 回退贡献ENV边 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 142 | 18312 | 298 | 3857 | 288 | 56/276 | 108 |
| 访问控制合约 | 114 | 13432 | 261 | 2536 | 314 | 97/357 | 160 |
| 重入节点 | 71 | 12036 | 187 | 3200 | 126 | 26/85 | 42 |
| 访问控制节点 | 57 | 7710 | 182 | 1948 | 121 | 37/102 | 58 |

| 任务 | profile | 参数量 | 输出形状 | 前向秒（含hook） | 进程峰值RSS MiB | 两层同键跨文件最大差异 |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 重入合约 | G3 | 5004308 | [142, 2] | 3.2534 | 2034.66 | 0.00000000 / 0.00000000 |
| 重入合约 | G3R | 5283380 | [142, 2] | 4.2754 | 2167.25 | 0.49534172 / 0.49247390 |
| 访问控制合约 | G3 | 5004308 | [114, 2] | 2.4988 | 1806.25 | 0.00000000 / 0.00000000 |
| 访问控制合约 | G3R | 5299796 | [114, 2] | 3.1733 | 1899.18 | 0.43592823 / 0.42361152 |
| 重入节点 | G3 | 4840148 | [12223, 2] | 2.3031 | 1734.73 | 0.00000000 / 0.00000000 |
| 重入节点 | G3R | 5111012 | [12223, 2] | 2.7119 | 1835.71 | 0.44532990 / 0.43481565 |
| 访问控制节点 | G3 | 4922228 | [7892, 2] | 1.8451 | 1561.85 | 0.00000000 / 0.00000000 |
| 访问控制节点 | G3R | 5217716 | [7892, 2] | 1.9676 | 1610.03 | 0.36489880 / 0.36927533 |

**Prompt 4 零/容差内文件对静态补充（不再前向）**

原前向报告中未解析的1,970个“任务×层×键×文件对”里，900对满足token与canonical归一化邻域的参数无关充分条件，解释精确算术下的表示等价；另外1,070对仍未解析。此计数不是独立实验次数，也不是所有零差异对的总数。每对及原forward SHA保存在zero_pair_static_review/，原forward JSON保持不变。

| 任务 | 第一层：静态充分条件 / 未解析 | 第二层：静态充分条件 / 未解析 |
| --- | ---: | ---: |
| 重入合约 | 0 / 68 | 7 / 4 |
| 访问控制合约 | 435 / 44 | 11 / 435 |
| 重入节点 | 0 / 65 | 4 / 4 |
| 访问控制节点 | 435 / 105 | 8 / 345 |

例如访问控制buggy_11与buggy_14的this.balance分别接7条、4条相同token的_recipient.transfer(address(this).balance);，同canonical消息值相同，softmax加权和不会仅因重复次数改变。这适用于第一层，不能直接推广至第二层；其余不同输入但输出≤1e-6的情况可能涉及注意力集中、聚合或数值消差，但本轮没有保存attention权重，不将推测写成已证原因。900对的静态充分条件也不等于浮点计算的逐位因果证明。

数据限制：unmapped四任务288/314/126/121均为emit读取，无可投影用途时不建hub，不猜映射；assembly跳过15/14/12/9。真实语料shadow/unknown均0，仍由合成测试覆盖；6个键在本批无出现，不等于没有实现。grammar恢复20/22/14/14次，保留每次来源。未进行专家Oracle或solc验证，尚未训练或证实F1收益；未开始Prompt 5。

### Prompt 4固定ENV_FLOW抽样（每任务20条，seed=0，共80条）

下面目标code按原图存储原样展示，不去引号或重新编码。完整出现字节跨度、Unit范围、source SHA见同任务audit.json/inputs.json。独立复核80边/84处出现全部通过精确AST归属和原节点投影；这属于AI辅助核验。

#### 重入合约 / reentrancy_author_contract

**1 / buggy_47.sol / 18578 -> 9136 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: e883200a181e6df6fb29e78558d591c539fc59d55d766c97b9174576fe67b37a; evidence: [4087]

~~~solidity
"jackpot_re_ent37    = address(this).balance;"
~~~

**2 / buggy_20.sol / 18507 -> 7395 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 76d607594dc5be00d665f8948c880d9823ae65efe29e27cedb811d3abb670af5; evidence: [1952]

~~~solidity
"jackpot_re_ent30    = address(this).balance;"
~~~

**3 / buggy_42.sol / 18565 -> 12268 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: a9fd9daea7ecd533097b164b791977b949d9a00ffc2190675df56becb4050095; evidence: [3784]

~~~solidity
"balances_re_ent3[msg.sender] -= _weiToWithdraw;"
~~~

**4 / buggy_6.sol / 18587 -> 5190 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 3dc08fe3140eee0e3f9d85d00a917678e30eedbcef6708a4bb10c8ec408e96e7; evidence: [4421]

~~~solidity
"balances_re_ent36[msg.sender] = 0;"
~~~

**5 / buggy_22.sol / 18511 -> 6466 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb; evidence: [2138]

~~~solidity
"require(redeemableEther_re_ent4[msg.sender] > 0);"
~~~

**6 / 0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol / 18343 -> 18245 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 72f2f65fabb1882b877cd469def4062297f1127c0e99ea355a34d5fd57f053ef; evidence: [212]

~~~solidity
"_transfer(msg.sender, to, value);"
~~~

**7 / buggy_16.sol / 18490 -> 15913 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 52d8e426ad01e71771b316b6635c0116efacb7b38c19d25c7ac5d4eae561d4ea; evidence: [1378]

~~~solidity
"if( ! (msg.sender.send(1 ether) ) ){\n            revert();\n        }"
~~~

**8 / buggy_27.sol / 18526 -> 4840 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: e47d29695de23df62ebfb68db99311a6b01b28f3844f78a37936277f3efc8043; evidence: [2568]

~~~solidity
"uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];"
~~~

**9 / buggy_26.sol / 18524 -> 3860 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: c3f36ced6b7f8b8481716b60acf85e3e77f2f579e65cbb67a3255b0822025182; evidence: [2441, 2442]

~~~solidity
"(bool success,)= msg.sender.call.value(userBalance_re_ent26[msg.sender])(\"\");"
~~~

**10 / buggy_22.sol / 18511 -> 6211 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb; evidence: [2061]

~~~solidity
"balances_re_ent15[msg.sender] = 0;"
~~~

**11 / buggy_7.sol / 18589 -> 6756 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 4745c8d488084c7e7004857903e3b82e68753a5bf6379bc97061277bc0f2f6ec; evidence: [4552]

~~~solidity
"require(balances_re_ent31[msg.sender] >= _weiToWithdraw);"
~~~

**12 / buggy_43.sol / 18568 -> 11649 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 1c5706bcd9dee3ac66c4ce60a2f396906ad830191d52fb9db7cccdf6a6c30584; evidence: [3917]

~~~solidity
"require(Operated.isActiveOperator(msg.sender), \"only active operator\");"
~~~

**13 / buggy_47.sol / 18575 -> 9240 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: e883200a181e6df6fb29e78558d591c539fc59d55d766c97b9174576fe67b37a; evidence: [4123]

~~~solidity
"uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];"
~~~

**14 / buggy_18.sol / 18497 -> 2753 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec; evidence: [1581]

~~~solidity
"require(msg.sender == newOwner);"
~~~

**15 / buggy_25.sol / 18520 -> 573 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: f6f9402e91da66253215c19f8603252a7de8b5006e38367007b82789e0f2b337; evidence: [2397]

~~~solidity
"redeemableEther_re_ent32[msg.sender] = 0;"
~~~

**16 / buggy_2.sol / 18503 -> 5040 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: b6401bf3a4be6e2ce35cb53091fc04a306a57983e8b7e24488d619be13c27f9f; evidence: [1835]

~~~solidity
"msg.sender.transfer(transferValue_re_ent32);"
~~~

**17 / buggy_30.sol / 18536 -> 2508 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: e980c9dc84521ae5f3b610bd5eb94b6114a2cddc6b77ea9b4c498582caf23464; evidence: [2926]

~~~solidity
"userBalance_re_ent19[msg.sender] = 0;"
~~~

**18 / buggy_6.sol / 18587 -> 5211 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 3dc08fe3140eee0e3f9d85d00a917678e30eedbcef6708a4bb10c8ec408e96e7; evidence: [4429]

~~~solidity
"_owner = msg.sender;"
~~~

**19 / buggy_7.sol / 18589 -> 6599 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 4745c8d488084c7e7004857903e3b82e68753a5bf6379bc97061277bc0f2f6ec; evidence: [4503]

~~~solidity
"userBalance_re_ent40[msg.sender] = 0;"
~~~

**20 / buggy_11.sol / 18484 -> 15390 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: ecad8ee7cc70794da610ae66c76de0fd8f7befe9c606a2c8a33106f9bdd3cba1; evidence: [1186]

~~~solidity
"redeemableEther_re_ent4[msg.sender] = 0;"
~~~

#### 访问控制合约 / access_control_author_contract

**1 / buggy_30.sol / 13586 -> 1156 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: afbb76650f23d7e9fc5ba07e735c08c4ff6a80ca914ae5fc33491a4f47ef05a9; evidence: [1965]

~~~solidity
"require(tx.origin == owner_txorigin35);"
~~~

**2 / buggy_34.sol / 13599 -> 4462 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: afe641e5e3e75ae90778bb8e27ca9b0af76c4d3f30ec4615b051a718f4646eb2; evidence: [2114]

~~~solidity
"require(tx.origin == owner_txorigin24);"
~~~

**3 / 0x0a7073207bac23865e0e3b204615364b5a9d3783.sol / 13451 -> 3108 / msg.value**

- spellings: ["msg.value"]; source SHA256: ad119b2bfe3abf641327a053947f8834b4ff83e3bded59444f63736c1990aa24; evidence: [200]

~~~solidity
"uint256 amount = msg.value;"
~~~

**4 / buggy_20.sol / 13545 -> 4841 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 05c8e66580eea0f1c776a153e2ca3cbda486d4e70d5b8ed5689ba3479940ffc9; evidence: [1397]

~~~solidity
"require(tx.origin == owner_txorigin39);"
~~~

**5 / buggy_43.sol / 13629 -> 8355 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 7e0232977cf6d105598c2b137ffa185bd4bac95da9cf4e40925957c4744f77f2; evidence: [2577]

~~~solidity
"require(tx.origin == owner_txorigin36);"
~~~

**6 / buggy_40.sol / 13622 -> 7758 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 41b0d0180a5e0d00a61616c6cf79c387f0fd5aa685d44b87bc3c455eb007d7d3; evidence: [2448]

~~~solidity
"require (tx.origin == owner_txorigin37);"
~~~

**7 / buggy_33.sol / 13594 -> 2700 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 5df3b24de3ddded0edafe8a337916892b86f0d87ab78ffa15fd0618588594bc0; evidence: [2085]

~~~solidity
"require(token.balanceOf(msg.sender) >= stakeTokens + findOnePercent(stakeTokens));"
~~~

**8 / buggy_24.sol / 13562 -> 777 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b; evidence: [1625]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**9 / buggy_4.sol / 13617 -> 5616 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 1c963c08a66e6516d74a296676631091f82a275d88a8a1539eb7de6ba119114e; evidence: [2437]

~~~solidity
"if(balances[msg.sender] - value < toWei(200000000))\n                require(now >= 1683644400);"
~~~

**10 / buggy_29.sol / 13577 -> 12567 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: ca020711c077a3052a10499a2f49209f52e39384409016f57d06e767020fbdb8; evidence: [1874]

~~~solidity
"require(raffleContract.allowance(msg.sender, address(this)) >= initialAmount, \"Allowance is to small (increase allowance)!\");"
~~~

**11 / buggy_6.sol / 13655 -> 3366 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 42ff356fd98fd142cec6d65382226a716f579e5465ad72b78b295e1cee0ec948; evidence: [2894]

~~~solidity
"require(tx.origin == owner_txorigin19);"
~~~

**12 / buggy_19.sol / 13537 -> 139 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 4acf0d793c74383045ccc83d6b8da68992a1fe3a9970975f4ef5601686d2fa43; evidence: [1289]

~~~solidity
"require(msg.sender == owner, \"only owner can use this method\");"
~~~

**13 / buggy_43.sol / 13630 -> 8328 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 7e0232977cf6d105598c2b137ffa185bd4bac95da9cf4e40925957c4744f77f2; evidence: [2571]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**14 / 0x1b5d56bfe749e492ae226cf9aa23c1426f828b7b.sol / 13507 -> 2111 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 5ba33ed867cf8870b8eaeddd07d9db1ed26d95acd09c3376ca4aa57665a9c456; evidence: [867]

~~~solidity
"if (msg.sender != upgradeMaster) throw;"
~~~

**15 / buggy_22.sol / 13552 -> 4109 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4; evidence: [1494]

~~~solidity
"require(tx.origin == owner_txorigin40);"
~~~

**16 / 0x1b5d56bfe749e492ae226cf9aa23c1426f828b7b.sol / 13507 -> 2147 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 5ba33ed867cf8870b8eaeddd07d9db1ed26d95acd09c3376ca4aa57665a9c456; evidence: [869]

~~~solidity
"owner = msg.sender;"
~~~

**17 / 0x0e5632feb2c2619dba9c7e2dc5a7ed3fd14969da.sol / 13483 -> 6396 / block.timestamp**

- spellings: ["now"]; source SHA256: 20bb5bcde2e3db6ac2d2ba1a76d9fcda049716f273324f9e437ec09377c723f5; evidence: [582]

~~~solidity
"auctions[_auctionId].stopTime = now + (_duration * 1 minutes);"
~~~

**18 / wallet_04_confused_sign.sol / 13690 -> 9869 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 5ec3d85c76b1f1a15ec1295085087f1d969742bdc2aaf9c6fb1a79bfffa8735d; evidence: [3048]

~~~solidity
"require(creator == msg.sender);"
~~~

**19 / buggy_20.sol / 13546 -> 4777 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 05c8e66580eea0f1c776a153e2ca3cbda486d4e70d5b8ed5689ba3479940ffc9; evidence: [1380]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**20 / buggy_45.sol / 13636 -> 7077 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 20a5500adf14cb8eeeb3edb432413408ede4b46cba01d459f1ca6ef24cd25382; evidence: [2664]

~~~solidity
"require(tx.origin == owner_txorigin14);"
~~~

#### 重入节点 / reentrancy_author_node

**1 / buggy_29.sol / 18419 -> 17224 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 118efce476d6db982437b4440bfa9dd7e7bd210c252a46c2d9c80f35f8c47bfe; evidence: [1804]

~~~solidity
"redeemableEther_re_ent4[msg.sender] = 0;"
~~~

**2 / buggy_7.sol / 18478 -> 6756 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 4745c8d488084c7e7004857903e3b82e68753a5bf6379bc97061277bc0f2f6ec; evidence: [3618]

~~~solidity
"require(balances_re_ent31[msg.sender] >= _weiToWithdraw);"
~~~

**3 / buggy_30.sol / 18425 -> 2480 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: e980c9dc84521ae5f3b610bd5eb94b6114a2cddc6b77ea9b4c498582caf23464; evidence: [1980]

~~~solidity
"require(balances_re_ent3[msg.sender] >= _weiToWithdraw);"
~~~

**4 / 0xbaf51e761510c1a11bf48dd87c0307ac8a8c8a4f.sol / 18362 -> 3103 / msg.value**

- spellings: ["msg.value"]; source SHA256: 59ebd4fa5520fb501e02a072751299037ef827a8efef1ca06dcb23ce1e862510; evidence: [166]

~~~solidity
"if(msg.value > MinDeposit)\n        {\n            balances[msg.sender]+=msg.value;\n            TransferLog.AddMessage(msg.sender,msg.value,\"Deposit\");\n        }"
~~~

**5 / buggy_22.sol / 18400 -> 6439 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb; evidence: [1199]

~~~solidity
"msg.sender.transfer(transferValue_re_ent32);"
~~~

**6 / buggy_35.sol / 18438 -> 8117 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: ef0be568a9870bd223f6a8665f09384d4458d3f0c41c716b6062219a131cc2a0; evidence: [2426]

~~~solidity
"msg.sender.transfer(transferValue_re_ent4);"
~~~

**7 / buggy_34.sol / 18435 -> 7053 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 2182dadd5be822e13020b02e918d2d0eddaf942f26fc11ca9c5af2104b3d6dc4; evidence: [2293]

~~~solidity
"require(balances_re_ent38[msg.sender] >= _weiToWithdraw);"
~~~

**8 / buggy_3.sol / 18423 -> 3539 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 9eaa874f037cc6ee0f642d250d199a4722d3f8265e1654d9a33565a1237ca21a; evidence: [1904]

~~~solidity
"userBalance_re_ent40[msg.sender] = 0;"
~~~

**9 / buggy_24.sol / 18405 -> 1990 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb; evidence: [1407]

~~~solidity
"balances_re_ent8[msg.sender] = 0;"
~~~

**10 / buggy_34.sol / 18435 -> 6899 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 2182dadd5be822e13020b02e918d2d0eddaf942f26fc11ca9c5af2104b3d6dc4; evidence: [2242]

~~~solidity
"balances_re_ent10[msg.sender] -= _weiToWithdraw;"
~~~

**11 / buggy_27.sol / 18415 -> 4946 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: e47d29695de23df62ebfb68db99311a6b01b28f3844f78a37936277f3efc8043; evidence: [1675]

~~~solidity
"if( ! (msg.sender.send(10 ether) ) ){\n            revert();\n        }"
~~~

**12 / buggy_40.sol / 18452 -> 10815 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: f530b30562180ec1150773025b7f45856c96a44121c5bc3bcdbf25be4cc03f64; evidence: [2786]

~~~solidity
"if( ! (msg.sender.send(10 ether) ) ){\n            revert();\n        }"
~~~

**13 / buggy_20.sol / 18394 -> 7330 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 76d607594dc5be00d665f8948c880d9823ae65efe29e27cedb811d3abb670af5; evidence: [1004]

~~~solidity
"require(msg.sender.send(_weiToWithdraw));"
~~~

**14 / buggy_35.sol / 18438 -> 8043 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: ef0be568a9870bd223f6a8665f09384d4458d3f0c41c716b6062219a131cc2a0; evidence: [2382]

~~~solidity
"balances_re_ent3[msg.sender] -= _weiToWithdraw;"
~~~

**15 / buggy_18.sol / 18386 -> 2695 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec; evidence: [629]

~~~solidity
"msg.sender.transfer(transferValue_re_ent11);"
~~~

**16 / buggy_24.sol / 18407 -> 1884 / block.timestamp**

- spellings: ["now"]; source SHA256: 56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb; evidence: [1382]

~~~solidity
"addInvestRecord(msg.sender, now, investAmount, investCycle);"
~~~

**17 / buggy_18.sol / 18386 -> 2700 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec; evidence: [631, 632]

~~~solidity
"(bool success,) =msg.sender.call.value(balances_re_ent1[msg.sender ])(\"\");"
~~~

**18 / buggy_7.sol / 18478 -> 6721 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 4745c8d488084c7e7004857903e3b82e68753a5bf6379bc97061277bc0f2f6ec; evidence: [3608]

~~~solidity
"require(redeemableEther_re_ent4[msg.sender] > 0);"
~~~

**19 / buggy_16.sol / 18379 -> 15860 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 52d8e426ad01e71771b316b6635c0116efacb7b38c19d25c7ac5d4eae561d4ea; evidence: [426]

~~~solidity
"if( ! (msg.sender.send(10 ether) ) ){\n            revert();\n        }"
~~~

**20 / buggy_43.sol / 18457 -> 11548 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 1c5706bcd9dee3ac66c4ce60a2f396906ad830191d52fb9db7cccdf6a6c30584; evidence: [2956]

~~~solidity
"require(balances_re_ent31[msg.sender] >= _weiToWithdraw);"
~~~

#### 访问控制节点 / access_control_author_node

**1 / buggy_49.sol / 13251 -> 9889 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 00fdccd8d219a6a854ccee41e813bff6c8a1a8aaf98177c9be40a3036400e23d; evidence: [1918]

~~~solidity
"require(tx.origin == owner_txorigin31);"
~~~

**2 / buggy_27.sol / 13176 -> 2778 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 9303069fc1046277df405eae6053f9a09e8bd536e2859702de1edce333c76e23; evidence: [816]

~~~solidity
"require(tx.origin == owner_txorigin34);"
~~~

**3 / buggy_45.sol / 13238 -> 7015 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 20a5500adf14cb8eeeb3edb432413408ede4b46cba01d459f1ca6ef24cd25382; evidence: [1748]

~~~solidity
"require(msg.sender == owner);"
~~~

**4 / buggy_7.sol / 13263 -> 4264 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 0a5d21c387405e2a5ad6ac20dfa11099fc3eaf41c87cc3e35c9e73d3a08b0b9e; evidence: [2029]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**5 / buggy_28.sol / 13179 -> 12865 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 491b8f8cc3f11bdea6b745a5e878ac6ea9f84cc61739456456a031a339b7af44; evidence: [915]

~~~solidity
"require(tx.origin == owner_txorigin23);"
~~~

**6 / buggy_15.sol / 13124 -> 12389 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 5b114255f8da2572ff28770d772ba9f6b7404f2e1544ea45ce89d71c51869520; evidence: [98]

~~~solidity
"balanceOf[msg.sender] = totalSupply;"
~~~

**7 / buggy_22.sol / 13155 -> 4128 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4; evidence: [602]

~~~solidity
"require(msg.sender == chairmanAddress);"
~~~

**8 / buggy_32.sol / 13196 -> 2520 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 850f1b2de2a4bea0030726cee6cc81eeba108af2b53f129d5b7f4755ba15e674; evidence: [1132]

~~~solidity
"require(tx.origin == owner_txorigin14);"
~~~

**9 / buggy_30.sol / 13190 -> 1187 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: afbb76650f23d7e9fc5ba07e735c08c4ff6a80ca914ae5fc33491a4f47ef05a9; evidence: [1076]

~~~solidity
"require (tx.origin == owner_txorigin25);"
~~~

**10 / buggy_28.sol / 13178 -> 12879 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 491b8f8cc3f11bdea6b745a5e878ac6ea9f84cc61739456456a031a339b7af44; evidence: [919, 920]

~~~solidity
"_balances[msg.sender] = _balances[msg.sender].sub(value);"
~~~

**11 / parity_wallet_bug_2.sol / 13279 -> 9588 / block.timestamp**

- spellings: ["now"]; source SHA256: 3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e; evidence: [2101]

~~~solidity
"return now / 1 days;"
~~~

**12 / buggy_47.sol / 13242 -> 6536 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: eac2fdbab5e24c8d8e6889afc0e4d8d9c1dfb6b8181c6ffd9c0e84dfe5d4d348; evidence: [1802]

~~~solidity
"require(balances[msg.sender] >= tokens && tokens > 0);"
~~~

**13 / buggy_48.sol / 13248 -> 10304 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: f59bf750df27f14f4657dce4b7876fd4308f5d6202974962c6bd55393bea07e1; evidence: [1869]

~~~solidity
"require(tx.origin == owner_txorigin38);"
~~~

**14 / buggy_24.sol / 13165 -> 680 / block.timestamp**

- spellings: ["now"]; source SHA256: 1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b; evidence: [706]

~~~solidity
"user.currentInvestTime = now;"
~~~

**15 / buggy_30.sol / 13190 -> 1054 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: afbb76650f23d7e9fc5ba07e735c08c4ff6a80ca914ae5fc33491a4f47ef05a9; evidence: [1044]

~~~solidity
"require(tx.origin == owner_txorigin16);"
~~~

**16 / buggy_26.sol / 13172 -> 2470 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: 129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74; evidence: [805, 806]

~~~solidity
"_approve(msg.sender, spender, _allowances[msg.sender][spender].add(addedValue));"
~~~

**17 / buggy_35.sol / 13210 -> 5368 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: cbceb18bb70b1400dee01790610b829e7eae7b6be8588d39b75b16aefbb6d209; evidence: [1296]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**18 / buggy_7.sol / 13263 -> 4359 / this.balance**

- spellings: ["address(this).balance"]; source SHA256: 0a5d21c387405e2a5ad6ac20dfa11099fc3eaf41c87cc3e35c9e73d3a08b0b9e; evidence: [2053]

~~~solidity
"_recipient.transfer(address(this).balance);"
~~~

**19 / incorrect_constructor_name1.sol / 13264 -> 7884 / msg.sender**

- spellings: ["msg.sender"]; source SHA256: d918731cebddf34ad385dd799691237e0ec1aab09f34ce7eb6bbe83ec86cd8c8; evidence: [2058]

~~~solidity
"require(msg.sender==owner);"
~~~

**20 / buggy_20.sol / 13149 -> 4704 / tx.origin**

- spellings: ["tx.origin"]; source SHA256: 05c8e66580eea0f1c776a153e2ca3cbda486d4e70d5b8ed5689ba3479940ffc9; evidence: [465]

~~~solidity
"require (tx.origin == owner_txorigin37);"
~~~


## 2026-10-25 Prompt 5.0：诊断完成（Codex）

文件：新增attention_probe.py、grammar_shape_audit.py、tests/test_attention_probe.py、tests/test_grammar_shape_audit.py；旧实现不改。

四任务各一次CPU eval/no_grad，八层精确重算误差0，1070/1070对重现。第一层ENV多邻居head max>=.99依次85.82%/62.04%/76.48%/54.68%，READS_STATE98.62–99.77%、next_line96.35–98.91%；第二层均0%。70对消息及残差输入完全同，269对最高value同但不足以全部归因，731对是第二层非零的容差内接近，未发现模型接入错误。G0没有独立测量，不把推测写成实证。详表及解释边界见training_changes第46节和prompt5_v1/attention_probe/。

grammar四任务384实例/256唯一源码身份；直接binary/unary后缀槽363/296/218/164次，吞push/pop与表达式user_defined_type均0。最终grammar_shape_audit_r1补充新审计器空白前缀与metadata外部资产校验，不修改分析器。原审计产物保留。

用户批准call_5b82ed0af4c443a8ad73d74579bde566的两项最小调整已存approved_interface_adjustments.json：源码清单只加载/校验一次、各层调用一次复用中间图；通用性测试用20个合成身份以满足原5/10折。后续不复写真实划分或冻结分析器。

命令：python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests；同命令目标scripts/DFG/tests tests/test_graph_utils.py。真实诊断命令与产物路径见training_changes第46节。最终数量见下方补记。未训练、未GPU测量、未solc、未push；本阶段先单独本地提交。


Final verification: v2 597 passed (8 existing warnings), legacy DDG/graph_utils 223 passed (29 existing warnings); 820 passed, 0 failed/skipped. Grammar targeted 42 passed, attention targeted 17 passed. Logs: prompt5_v1/phase0_final_v2.log and phase0_final_legacy.log. All 11114 protected tracked file SHAs and all three original document prefixes verified unchanged. Grammar r1 task JSON SHAs equal the prior scan; only audit input guards improved.


## 2026-10-25 Prompt 5 第1–5部分完成（Codex）

新增pipeline.py、tasks.py、inputs.py、store.py、cli.py、EXTENDING.md，以及test_pipeline.py、test_tasks.py、task_fixtures.py、test_cli.py。只组合既有层；F0原文件引用，F1/F2/F3正向集合推导，G3/G3R共用F3。每任务源码加载一次与各层内部独立parse的差异按用户批准记录；20合成身份支持真实5/10折函数。版本元数据独立引用不丢失，注册表不含类别分支。

定向43+31+28项通过；最终全v2 699＋旧DDG/graph_utils 223＝922 passed，0失败/跳过，8/29条已有弃用warning。命令与失败记录见training_changes第47节，日志phase1_final_v2/phase1_final_legacy。各真实nested折与原文件逐字段一致。

四任务源码清单共384个实例（142/71/114/57），无缺源码；inputs与store分别独立seal。F0四项均为原路径与原文件SHA直引，未新建F0的hcg文件。默认构建得到12张新图+4个F0引用，共16项，记录20个CPU模型schema；无真实图前向、loss或训练。构图开始/结束runtime一致。独立读取12张新图的两种指纹均与历史P2/P3/P4参照一致，4/4 F3去辅助节点后精确等于F2；原节点、原边与各前层属性逐项保持。历史bundle/receipt/图SHA也重新核验，原产物没有覆盖。

实际每任务耗时包含加载、分析、序列化和schema构造；RSS为同一进程截至任务结束的累计高水位，不是各任务独立峰值：

| 任务 | 总秒数 | 进程累计峰值 MiB |
| --- | ---: | ---: |
| reentrancy_contract | 280.51 | 2293.73 |
| reentrancy_node | 175.84 | 2293.73 |
| access_control_contract | 200.96 | 2293.73 |
| access_control_node | 99.88 | 2293.73 |

验收绑定与产物：

- `inputs/manifest.json`: `a5d7f7a080a617dcda1ffc56804e581fa5b6ce2850c8d82f62ee47be75d23edf`
- `inputs/manifest.seal.json`: `81d36660f044ebc71921aaf98f165104a880bb2e3eced14354f2b4afe4d5c786`
- `graphs_v1/store.json`: `43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b`
- `graphs_v1/store.seal.json`: `ca6c7ea13cc7304a2de863c14ed9e6fbbac31ec554350894d61a5839197d46fb`
- `prompt5_v1/independent_graph_comparison.json`: `a5ed87cfd41d72cab51a05d55cf8f395e904aae9cdc636ceba980305e0145513`

完整build_summary.csv（与封存文件同内容，cumulative_seconds为该任务从开始到该层的累计耗时；new_canonical为对应剖面的最大新增数，方向区别见new_canonical_by_profile）：

~~~csv
task_id,graph_key,profiles,nodes,edges,DATA_DEF_USE,WRITES_STATE,READS_STATE,ENV_FLOW,env_nodes,new_canonical,new_canonical_by_profile,L1_functions,L1_supported,L1_support_fraction,state_declarations,anchored_state_declarations,state_anchor_fraction,cumulative_seconds
reentrancy_contract,F0,G0,18312,19267,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,44.49224733401206
reentrancy_contract,F1,G1R,18312,24926,5659,0,0,0,0,42,"{""G1R"": 42}",3404,3128,0.918918918918919,0,0,,110.59969158700551
reentrancy_contract,F2,G2R,18312,32348,5659,3108,4314,0,0,58,"{""G2R"": 58}",3404,3128,0.918918918918919,2369,2369,1.0,177.51898770302068
reentrancy_contract,F3,"G3R,G3",18610,36205,5659,3108,4314,3857,298,68,"{""G3"": 34, ""G3R"": 68}",3404,3128,0.918918918918919,2369,2369,1.0,278.6237832000188
reentrancy_node,F0,G0,12036,11710,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,24.43905459198868
reentrancy_node,F1,G1R,12036,15129,3419,0,0,0,0,42,"{""G1R"": 42}",2045,1960,0.9584352078239609,0,0,,65.26113055300084
reentrancy_node,F2,G2R,12036,20453,3419,2254,3070,0,0,58,"{""G2R"": 58}",2045,1960,0.9584352078239609,1788,1788,1.0,109.0333901779959
reentrancy_node,F3,"G3R,G3",12223,23653,3419,2254,3070,3200,187,66,"{""G3"": 33, ""G3R"": 66}",2045,1960,0.9584352078239609,1788,1788,1.0,174.89089208998485
access_control_contract,F0,G0,13432,15538,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,30.342772722011432
access_control_contract,F1,G1R,13432,21251,5713,0,0,0,0,44,"{""G1R"": 44}",3148,2791,0.886594663278272,0,0,,79.46025053001358
access_control_contract,F2,G2R,13432,25068,5713,1609,2208,0,0,62,"{""G2R"": 62}",3148,2791,0.886594663278272,922,922,1.0,127.71584202800295
access_control_contract,F3,"G3R,G3",13693,27604,5713,1609,2208,2536,261,72,"{""G3"": 36, ""G3R"": 72}",3148,2791,0.886594663278272,922,922,1.0,199.33407922001788
access_control_node,F0,G0,7710,8840,0,0,0,0,0,0,"{""G0"": 0}",0,0,,0,0,,14.905203856003936
access_control_node,F1,G1R,7710,12729,3889,0,0,0,0,44,"{""G1R"": 44}",1958,1856,0.947906026557712,0,0,,38.528895382012706
access_control_node,F2,G2R,7710,14587,3889,767,1091,0,0,62,"{""G2R"": 62}",1958,1856,0.947906026557712,403,403,1.0,62.25203139000223
access_control_node,F3,"G3R,G3",7892,16535,3889,767,1091,1948,182,72,"{""G3"": 36, ""G3R"": 72}",1958,1856,0.947906026557712,403,403,1.0,99.24081490701064
~~~

11114个开始前受保护文件SHA和三份历史文档前缀均保持。新代码摘要见phase1_code_inventory.json；独立验收见independent_graph_comparison.json。具体输入/构图/verify命令日志在prompt5_v1/，完整schema与参数量在graphs_v1/store.json。

已执行cli build的参数：--manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs/manifest.json --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node --graph-keys F1,F2,F3 --output scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1。已有目录禁止覆盖。可重复执行只读验收：python -B -m scripts.DFG.dfg_v2.cli verify --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v1/store.json。

未修改历史代码/数据/图/标签/特征/模型，未启动真实图训练或Prompt6–8，未执行solc或GPU预检。本轮只完成统一图存储与等价验收，不能据此宣称F1提升。两次本地提交按Prompt要求分开，未push。实施与记录AI：Codex。


Final acceptance: cli build exited 0; independent cli verify exited 0 (16 graph entries, 20 recorded schemas, 0 verification HGT constructions/forwards). Actual runtime SHA map still matches build-time; original 11114 protected files and historical document prefixes verified unchanged. Proof: prompt5_v1/final_acceptance.json.


## 2026-10-25 Prompt 6：封存 Oracle、可选外部对照与人工抽查（Codex）

### 本轮实现和顺序

起点f5e1260，dfg-v2分支，开始时pull --ff-only确认已同步。先独立编写20对.sol/.expected.json并提交aded5023a0adb759cb458b2e238ccdc480be1d35，再写SEAL及比较器；工具/测试/分类记录提交f80073f34d6747a9e94fa67c0a1fefa93e231bc9。原始期望未按运行结果修改。

新增oracle_check.py、validate_slither.py、review_sheet.py、score_review.py；测试test_oracle_check.py、test_validate_slither.py、test_review_sheet.py；oracle/SEAL.json、CLASSIFICATIONS.json。这里只验证，不改分析器/pipeline/HGT/tokenizer/标签/既有图。

用户批准的调整：tuple在原HCG中为一个语句节点；验证x/y定义→tuple、tuple→a/b使用，附声明身份和禁止边检查。明确不验证tuple内部逐元素值流，不新增节点、不调整分析器。Slither的L1对照另外标记为partial：冻结audit只有投影端点，不能冒充完整def/use出现集合。

### Oracle验收与Prompt 6b输入

最终报告：scripts/DFG/experiments/artifacts/dfg_v2/prompt6_v1/oracle_run_v2/summary.json。20例执行，17例完全匹配、3例存在差异；85条期望关系事实、32条禁止项，禁止边违反数为0。24个有意近似条目独立标记。所有样例未执行编译验证，Tree-sitter解析成功不等于编译通过。

| 关系 | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| DATA_DEF_USE | 47 | 4 | 3 | 92.16% | 94.00% |
| WRITES_STATE | 8 | 0 | 0 | 100% | 100% |
| READS_STATE | 15 | 0 | 0 | 100% | 100% |
| ENV_FLOW | 12 | 0 | 0 | 100% | 100% |

以上为对原封存期望的原始比较，包含期望本身的错误，不能当作全数据集真实正确率。8项差异全部有分类和证据：

- 04_for_update：6项期望错误。原CFG_solidity.py在621–627、654–656行已创建/连接独立update节点，不能把i++投影到整个for；保留原期望，记录代码与语言循环顺序依据。
- 18_environment_synonyms：1项期望拼写错误。期望属性gasleft应与源码的gasleft()区别；真实msg.gas和gasleft()均被识别并合并到同一环境键。没有改期望或分析器。
- 16_call_option_fields：1项实现覆盖缺口。L1对call{value: x}的struct_expression未识别，函数级回退漏掉x定义→调用的读取边。定位scripts/DFG/access_extractor.py::AccessExtractor.reads及dfg_v2/l1_access.py::V2AccessExtractor.reads。原HCG、函数保留，无部分事实提交。L2仍正确读取target，value/gas/salt字段名不被当成变量。Prompt 6b应修复此项后另建graphs_v2并复验；本轮未修复/重构图。

比较器除边集合还检查spellings/via_alias属性、env计数、禁止边、encoder无关及执行错误；执行失败不会作为空成功样例计入。v1原报告保留，强化检查后的v2为最终依据。分类文件绑定最终报告SHA。

### 外部对照及待人工填写内容

Slither0.8.0/crytic_compile0.2.4已安装；无solc-select与获准离线编译器。重入142文件（27有精确版本、115缺精确版本）、访问控制114文件（16有精确版本、98缺精确版本）全部跳过，编译次数0、比较次数0，P/R为null。见prompt6_v1/slither/report.json。未联网安装或执行新编译器。

交给用户的空表：scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv（UTF-8 BOM）。seed=0，R/AC各15文件，共512边：DATA_DEF_USE 132、WRITES_STATE 122、READS_STATE 129、ENV_FLOW 129。只填verdict为correct/wrong/unsure及note；不要修改其他列、顺序或行数。AI未填写判定。原始空表、字节定位来源与SHA封存齐全。按关系统计correct/(correct+wrong)和Wilson95%，unsure/空白单列；全空表返回null，不会伪报100%。

~~~bash
python -B -m scripts.DFG.dfg_v2.score_review \
  --csv scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv \
  --seal scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.seal.json
~~~

### 测试、不变量与停止位置

在mando环境及共享上下文变量下：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

最终765＋223＝988 passed，0 failed/skipped；8/29条既有DGL distutils、NetworkX gpickle弃用warning。定向Oracle19、Slither19、review28项通过。11128个保护文件SHA及三份历史文档前缀保持；store.json SHA仍为43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b。证据prompt6_v1/final_acceptance.json。

验收范围是“所有不一致项已归类”，不是Oracle全绿或完整Solidity验证。人工判定与外部编译对照尚未完成。Prompt 6b缺口修复后需新图/新报告，不能覆盖graphs_v1。中文新增段落的管道编码问题已修复，历史前缀未变。按要求本地三次提交后停止，未push、训练或开始Prompt 6b/7/8。详细实施见training_changes第48节和PROMPT6_REPORT.md。


## 2026-10-25 Prompt 6b：L1修复、重建与证据身份验收完成

修改AI：Codex。实际类名为ExtendedAccessExtractor；文档中的V2AccessExtractor是描述名。L1只改reads函数：struct_expression读callee/type和各value、不读字段名；用户批准补new_expression的type_name处理，不把类型名当值读取，未知形状继续回退。

新增store_diff.py、tests/test_store_diff.py、oracle/CLASSIFICATIONS_v2.json；修改l1_access.py、score_review.py、test_l1.py、test_l1_access.py、test_review_sheet.py。未改旧DDG、HGT、特征、标签、折或训练。

|任务|恢复函数|新增DATA_DEF_USE（每个F1/F2/F3）|旧引用换号边|仍fallback原因变化|
|---|---:|---:|---:|---:|
|reentrancy_contract|7|51|2709|3|
|reentrancy_node|4|50|1294|3|
|access_control_contract|6|60|2231|0|
|access_control_node|3|34|1147|0|

20是跨任务函数实例数，不是去重源码函数数。各累积图重复计边合计585，不能当成585个独立新增事实。真实恢复原因为new_expression。16个图项、20个schema完整，旧节点/属性和基础边保持，L2/L3语义和边属性逐项相同，新增边仅来自恢复函数。

用户批准两项验收调整并已记录原失败：证据索引换号必须解析为同序同重数、全字段相同事实，输出old→new映射；仍回退函数仅诊断reason可推进，事实必须为空、partial=false，身份/其他元数据不变。错指、篡改、重复引用、旧事实变化和回退残留的负例均保留。

原512条人工表全部通过语义绑定，76行只换引用，两个合约任务新增111边不在原样本内。未重采样或代填verdict/note。--equivalence实际评分通过，空表完成数0、比例null。

Oracle18/20，7项expectation_error，16_call_option_fields fixed；原20组期望/原分类不改。修复提交f270ed6，审计提交c09bbbc。定向9失败→9通过；new分支7失败/9通过→16通过；索引2失败→通过；reason1失败→通过。最终定向90 passed；与6c共同整套886 v2+223旧=1109 passed，0失败/跳过，8/29既有警告。

首次graphs_v2构图末尾被runtime摘要拒绝：临时候选.py落入全树扫描；保留失败目录，将候选改.py.txt，不改扫描器，另建graphs_v2_r1。重建891.38秒、387运行SHA前后一致；cli verify80.29秒；最终diff267.02秒，等价评分281.39秒。旧两次验收日志分别保留索引字面差异和回退原因变化，不改旧seal。

后续Prompt7/8使用graphs_v2_r1/store.json；graphs_v1仅历史，第一次graphs_v2不可用。详细SHA/命令见training_changes§49及prompt6b_v1/store_diff_r2。未执行模型前向训练或更多类别。


## 2026-10-25 Prompt 6c：完整L1事件与版本绑定的Slither验证完成

修改AI：Codex。用户本轮直接授权安装/下载编译器，故执行模板中的外部验证准备；既有分析语义不变。新增l1_occurrences.py、tests/test_l1_occurrences.py、tests/test_validate_slither6c.py，修改validate_slither.py。正式提交7918427；完整选择与证据见training_changes第50节。

版本清单覆盖256文件，26个版本；43 metadata、207 pragma_derived、6 fallback_default。用户批准六个无pragma文件沿用auto_version_solc默认0.4.25并单列来源。没有从pragma/default推导结果伪造SupportedSourceView精确元数据。新装solc-select1.0.4及pycryptodome3.20.0，原Slither0.8.0/crytic_compile0.2.4及其他包版本不变；编译器双哈希和--version核验通过，不改全局版本。逐文件预选版本只运行一次，失败不切换版本。

|任务|总数|比较|solc失败|映射不可比|L1 P/R (%)|L2 P/R (%)|
|---|---:|---:|---:|---:|---|---|
|reentrancy_contract|142|131|8|3|72.9465 / 88.9611|98.9022 / 86.9463|
|access_control_contract|114|108|3|3|60.5259 / 87.8706|98.2994 / 85.4167|

Slither分析失败、unknown异常和工具缺失跳过均0。6个不可比文件缺CFG filename，涉及0.4.0/0.4.2/0.4.9；包括simple_dao和parity_wallet_bug_2，未猜测映射。11个编译失败均属pragma_derived，详情与source SHA保留。所有原模型样本仍在图中。

“完整L1”是当前支持函数的未投影IR事件—符号集合，非逐token计数或DDG边。支持函数沿真实legacy/v2路由，只读收集reads/writes/weak_writes；回退无部分结果。Slither多继承上下文取并集并保留来源；主匹配仍为原始行/名字/读写三元组，声明身份另审计。alias/modifier排除量可见，inheritance不排除。缺CFG来源时整个文件不比较，编译异常按异常链分类而不是靠顶层SlitherError猜测。

L1额外项中入口初始化占重入98.59%、访问控制93.16%；缺失项中回退贡献96.54%/97.43%。支持函数召回99.5727%/99.6461%仅诊断，整体召回仍88.9611%/87.8706%。L2已确认一例状态声明初始化范围差别，另两例只是Slither语句首行与L2实际读取行不同且投影边存在；其余差异仍待人工判断。first20按稳定顺序展示，不是随机样本，不自动判错。

最终v2 886 passed（8条既有警告），旧DDG/graph_utils 223 passed（29条既有警告）；总1109，0失败/跳过。定向58通过，异常链专项6通过/25未选择。候选首轮NameError失败及修正过程已保留。命令：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.validate_slither \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full
~~~

上述正式输出已存在，重跑应指定新目录。实际运行219.89秒；report.json约152MB，逐事件证据及seal保留本地。可读摘要results_compact.json，独立复核result_review.json，最终不变量/测试final_acceptance.json。源码与F3/audit/store输入摘要在运行结束重新核验。

后续仍使用graphs_v2_r1/store.json。未改旧seal或人工表，未编译现代Oracle样例，未开始Prompt7/8、训练或push。外部事件一致性不能替代人工边判断和最终模型实验。


## 2026-10-25 Prompt 6d 完成（Codex）

已读更新后的§4.1和6d，git pull --ff-only返回已最新。6b/6c的批准选择保持；本轮只增加验证工具，不重新执行6b。

文件：新增slither_align.py、slither_mapping.py、slither_review.py、review_supplement.py及4个测试文件；仅修改l1_access.py的new_expression直接call_argument分支和test_l1_access.py。新增PROMPT6D_REPORT.md、PROMPT6D_CATEGORY_EXAMPLES.md，同时追加HANDOVER和training_changes第51节，历史文字保留。

最终输入仍为graphs_v2_r1/store.json。源码形状清点直接call_argument为0/0/0/0；临时重建12张F1–F3图双指纹全部相同，16个图项SHA完全相同，F0引用/20模型schema不变。临时图仅作不变量验证，未前向、训练或优化；成功后仅删除本轮31个重复临时文件，保留比较记录。

跨度一对一对照修正IR事件合并、scope重命名、entry同起点抢配和delete operand分类；旧alignment_v1/v2不覆盖。原6c指标保持；新版候选/参考/匹配：
- 重入L1：12345/10215/8974，P/R 72.6934/87.8512%；
- 重入L2：7658/8563/7368，96.2131/86.0446%；
- 访问控制L1：14359/10024/8719，60.7215/86.9812%；
- 访问控制L2：3994/4425/3802，95.1928/85.9209%。

全部13,857差异有互斥类别；773条other按固定规则抽172条，逐条AI辅助审阅，无已确认v2_defect；165条旧判断仅在完整证据相等后复用，另7条新核验。这里的保守版本/别名和modifier范围差异仍是限制，不是已经补齐的功能。未抽中部分及人工边精度未验收；原Oracle18/20不改。

六旧文件全节点严格映射仍不通过：254=76精确+98无表达式+80不等，均继续不可比较；111条新边空白表review_v1b已封存，verdict/note未填。额外2文件3次只读Slither超范围探针已停止且单列，未并入正式指标；不把该偏差记成用户批准。原5条modifier误读已记录纠正，原seal与selection未变化。

验收命令：python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests（970通过、8已有warning）；同命令路径scripts/DFG/tests tests/test_graph_utils.py（223通过、29已有warning）；总1193，0失败/跳过。比较器34、映射23、抽样16、L1/补表组合92定向测试通过（不重复计数）。实际CLI及输出见PROMPT6D_REPORT.md。

产物：artifacts/dfg_v2/prompt6d_v1/（alignment_v3、review_other_v3、mapping、tests、temporary_rebuild_comparison、final_acceptance）及review_v1b/。正式新关系、HGT、tokenizer、标签、fold和旧训练代码未改。本轮本地提交后停止，不push、不开始Prompt7/8。


## 2026-10-25 Prompt 6d.1 验证工具与规定审查完成

- 已读更新§4.1/6d.1并pull --ff-only确认最新；6b复用。本轮仅修改验证工具，不改分析器/pipeline/HGT/tokenizer/图/标签/划分/训练。新增slither_units、slither_patterns、slither_conventions及六个手写例/测试，扩展slither_align和slither_review。
- L2改为(Unit,变量,READ/WRITE)计数：R候选7658→7485、FP290→117；AC3994→3863、FP192→61，匹配/FN不变。明确消除同一已匹配Unit中的重复FP135/120，共255；净FP减少304还含49个未匹配alias Unit内的重复归并。L1完全不变，指标是事件一致性而非漏洞F1。
- 原773 other=255重复已解决+517新谓词+1 rubixi状态循环未解释。五类各5例谓词核查全部成立；旧172重分类+剩余1+新25共198审查记录：60artifact、50scope、72convention、16unclear，0确认v2_defect。16unclear对应15身份；另76绑定差异全部state_name_ambiguous→scope_limit，没有真实继承回退丢状态的命中。
- 已有可信solc0.5.11运行6手写文件，6/6成功；无真实语料Slither重跑/下载。局部标量循环Phi与L2状态循环证据不相同；storage/reference不以memory探针强推。241个状态成员链write_base_read尚缺对应最小机制实证，不能称全部convention。
- 最终1075 v2+223旧=1298 passed，0失败/跳过，8/29既有warning。中间转义/集成错误、Unit跨度分类修订及输入SHA绑定修订均留日志，不覆盖旧报告。最终alignment_v4_r2、review_r2、binding_review及final_acceptance在prompt6d1_v1/。
- 图仍是graphs_v2_r1。全部13553差异中203逐条审阅、13350未逐条语义判定；新谓词517中391未逐条审阅。剩余other未查0不等于所有差异已证明正确；review gate仍unresolved_analyst_findings。原512/111边人工表未填，不训练/不开始6e、7、8。详细见training_changes§52、PROMPT6D1_REPORT.md。实施、复核与记录AI：Codex。

实际最终命令和详细表格见PROMPT6D1_REPORT.md。旧v3与6c报告、graphs_v2_r1/store SHA不变；r1/r2全部差异精确相等后才引用审查事实。没有需要替换用户方案的设计变更；未知实证保留unclear，不为压低other而伪造确定结论。下一步必须保留这些限制，不将本轮event一致性当作Buggy-F1或人工边正确率。


## 2026-10-25 DFG v2 Prompt 6d.2：类别验证门槛通过，保留有界残留（Codex）

修改与审查AI：Codex。pull --ff-only至95775d3；仅新增7验证工具、5测试、9fixture及报告，原分析器/pipeline/HGT/token/图/标签/折/训练均不改。完整记录见training_changes§53、PROMPT6D2_REPORT.md。

- 28非空分层各seed0随机10/不足全取，242逐条：129convention、110scope、3unclear；机械谓词全部成立。25组accepted、3组accepted_with_residual。
- 全量残留10个FN（9聚合loop＋1rubixi），不是样本3个；按批准的收紧门槛逐条核查定义/KILL及已有事实影响，在当前弱定义抽象范围内通过。机制仍unclear，无确认v2_defect。
- 最终gate：passed_with_bounded_FN_residuals；**graphs_v2_r1/store.json为Prompt7/8最终图存储**（SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4），须携带残留和范围限制，不能说全部差异清零。
- alias178FP全部单根READ，0WRITE缺失/0多根FP；4FN为不同块同名user触发callable保守拒绝，不是语言自身歧义。bare342、initializer771、fallback2402、aggregate25全量身份/形状核验完成。
- 四项用户批准：附加FN影响核查；原fixture声明控制；alias按READ补实证；额外shape fixture两版各一次。真实16attempt=13success+3syntaxfail，成功13个distinct身份；保留indexed/byte转换失败，仅重试失败项。无语料重编译/安装。
- 原15unique未决中9storage下标写解释，5loop+rubixi保留，全量再加4同类loop。原分类和判断不覆盖。
- 新84测试；全部1159v2＋223旧＝1382 passed，0失败/跳过，8/29既有warning。16图20schema只读verify通过；原11208非文档文件和三文档旧前缀不变。
- 附加pickle读取被自动审批拒绝后未绕过，改用冻结JSON及图SHA；先前独立cli verify另存，不冒充未执行读取。
- 产物prompt6d2_v1：categories/validation.json与summary.csv、两类impact、全部probe/retry、followup、测试XML/log及final_acceptance。selection SHA94e545c3a56c41b9fa1d3bc967af6b928c79a2c2edd5bd0126a801420255c678。
- 实际命令见报告第8节；生成输出拒绝覆盖。代码/报告本地提交，运行原件留WSL，不push、不训练、不开始Prompt7。原人工边表未代填。


## 2026-10-26 Prompt 7：训练接入完成，GPU显存验收停止（Codex）

实施/测试/记录AI：Codex。先读更新§4.1/P7、RECON§5及依赖，再pull --ff-only确认44f714c已最新。新增experiment/训练/协议/初始化/检查点/资源/runner/等价性入口及README、5个测试文件，旧DDG/HGT/tokenizer/图/标签/折/训练脚本不变。详细见PROMPT7_REPORT.md与training_changes§54。

两项用户批准：G0共有参数完全一致，新增关系采用各剖面完整Xavier范围（新增同名行不承诺跨增强剖面相等）；三次3轮等价性检查单列、不算8次pilot，且G3R显存门槛在其他GPU运行之前。三分区full-graph forward保留，inner_train更新、inner_val选best、outer_test只在fit完成后监督评分，不再使用paper CV validation口径。capture_model_input可处理env/REV，额外绑定profile/reducer；checkpoint沿用通用ddg-controlled-v1。

- store verify：4任务16图20schema通过；graphs_v2_r1保持最终输入，6d.2范围限制不消除。
- 新113项；全部1272v2＋223旧＝1495 passed，0失败/跳过，8/29既有warning。CPU小图及20文件端到端通过。
- 真实R合约fold0原/新CPU各3轮，历史113/29相同划分/初值/fit seed；每轮train/val损失最大差0.0，CPU重载逐位一致。不是nested成绩。
- pilot plan封存4任务G0/G3R各fold0，共8job；nested文件数R合约90/23/29、R节点50/13/8、AC合约72/19/23、AC节点40/11/6。新初值按语义绑定，未复用训练权重。
- 首个R合约G3R只完成第1轮，显存minimum free12 MiB <100；allocated3299.8477/reserved3536 MiB，76次采样无错误，程序主动MemoryGateError停止，非OOM。partial best/history/failure保留，无last/result/成功receipt，0/8完成、1失败、0重试。
- GPU历史3轮对照、其他7job、完整GPU梯度和重载验收均未执行；无8次F1结论，无可靠150次耗时估算。不能进入Prompt8。
- 本地旧torch库未检出模板allocator选项字符串，不能保证max_split_size_mb有效；未设置/升级。当前probe已独立进程，需用户选择释放外部显存/核实allocator/更大兼容GPU等方案后再显式retry，不自动降配。

产物O=artifacts/dfg_v2/prompt7_v1，实际命令与失败路径见报告。三份旧文档只追加，原代码/旧产物不变；本地commit，不自动push。本轮按显存门槛停止。


## 2026-10-26 DFG v2 Prompt 7b：接入完成，CPU 数值验收未通过（Codex）

实施、复核与记录AI：Codex。基于60aa23e，新增共享K/Q/V层及nonempty_mean版本，默认original保留；layer_impl进入模型、plan、初值、checkpoint/result，跨实现恢复被拒绝。原HGT/DDG/tokenizer/图/标签/fold及优化器数值规则未改。

用户批准：相对梯度按参数张量尺度计算，同时报告逐元素差；小图近零梯度纯相对门槛失败后增加1e-8绝对容差。前向逐位一致、CPU三轮损失1e-6门槛未放宽。新增94项；全部1366v2+223旧=1589通过，0失败/跳过，8/29条既有警告。

四组mean真实CPU前向/梯度通过，三轮损失差均超过1e-6；R/G0/nonempty_mean前向一致，但一个query权重梯度差1.593e-8>允许1.023e-8，随后停止。共5组静态、4对/8次CPU三轮诊断（24epoch）；最后一组和nonempty轨迹未跑。CPU best/last重载一致；不混计为8次GPU pilot。

未发现AC/G0初值/监督/优化器混用；证据符合反向累加与Adam放大解释，但无逐步轨迹不能认定唯一原因。0次GPU诊断、0/8pilot，新pilot plan未封存，旧P7失败记录不改。不能宣称显存已解决，不开始Prompt8。

详见PROMPT7B_REPORT.md、training_changes§55；产物prompt7b_v1留WSL。冻结范围外11061个跟踪文件SHA一致，固定4任务16图校验通过；三文档旧正文仅追加。代码/报告本地提交，不自动推送。

| 任务 | 剖面 | reducer | 三轮最大损失绝对差 | 结果 |
|---|---|---|---:|---|
| reentrancy_contract | G0 | mean | 2.92062759e-06 | 轨迹门槛失败 |
| reentrancy_contract | G3R | mean | 7.03334808e-06 | 轨迹门槛失败 |
| access_control_node | G0 | mean | 8.82148743e-06 | 轨迹门槛失败 |
| access_control_node | G3R | mean | 2.31862068e-05 | 轨迹门槛失败 |
| reentrancy_contract | G0 | nonempty_mean | — | 梯度门槛失败，未训练 |
| reentrancy_contract | G3R | nonempty_mean | — | 此前门槛失败，未执行 |

验收状态：implementation_tests_passed_cpu_numerical_gate_failed。完整文件清单、命令、批准和未执行事项见报告。


## 2026-10-26 Prompt 7b.1：小图float64严格验收失败，未启动训练（Codex）

基线c079e3a，pull --ff-only后读取§4.1和P7b.1。仅新增experiment/precision_validation.py、tests/test_precision_validation.py与PROMPT7B1_REPORT.md，三份记录追加。HGT、trainer、优化器、DDG、tokenizer、图/标签/fold均不改。

DGL所需CPU float64运算支持，正常小图前向逐位一致。正式mean/norm预检只有k_linears.0.bias未通过：绝对差2.7647e-18、参考梯度2.0762e-17、相对差0.13316>1e-10；全参数最大绝对差1.5266e-16。按模板停止，不增加atol、不排除bias。近零相消使纯相对门槛仍可能失败，不能凭此宣称实现逻辑错误。

临时图漏一个canonical消息负例：mean/nonempty_mean前向差0.06952/0.10319，各9个非bias梯度失败。最初注入移除stack槽位造成测试23通过1失败；修正仅诊断注入，断言不改，旧日志保留。新27通过；完整1393v2＋223旧=1616通过、0失败/跳过，8/29既有警告。测试通过不是数值验收通过。

原11251跟踪文件及前批164产物SHA一致，三文档旧前缀保留；固定store SHA不变。真实图float64=0、optimizer fit=0、GPU=0、pilot=0/8。未重判P7b旧失败，未新建pilot计划，不进入P8。真实float64还需诊断dtype/初值摘要适配，未擅自改校验。

详见报告、training_changes§56与产物prompt7b1_v1。建议混合float64容差需用户确认，本轮未采用。代码/文档本地commit，不自动push。


## 2026-10-26 Prompt 7b.2：运行前登记的新验收规则（Codex）

已读取更新§4.1与P7b.2，基线a2957d6，git pull --ff-only确认最新。用户要求执行新文档，授权本节阈值与隔离float64诊断路径；先登记，随后才执行真实图。本节不表示验收已经通过，完成后另追加结果。

每案例G=max所有参数maxabs(g_original)，逐张量门槛maxabs(Δg)<=1e-12*G+1e-10*maxabs(g_original)。纯相对差保留只报告；参考端maxabs(g)<=1e-12*G者逐项列出，并检查候选端也<=1e-12*G；非key-bias零梯度逐项解释，未用张量自身残差做唯一判据。前向1e-12、三轮float64轨迹1e-9不变。

实现仅新增诊断模块；不改生产HGT/model/trainer/model_validation/优化器。保留7b与7b.1失败记录。顺序：重判小图/负例→六组真实静态→六组三轮轨迹→AC节点GPU噪声与历史对照→R合约G3R显存探针→其余pilot。任一门槛失败停止；GPU100MiB门槛不变，不自动降配。新产物prompt7b2_v1，原产物不可覆盖。


## 2026-10-26 Prompt 7b.2：静态数值通过，CPU float64轨迹OOM停止（Codex）

新增precision_gate/precision_real/precision_gpu及三测试、PROMPT7B2_REPORT；既有Python计算文件均不改。详细记录training_changes §57。按更新模板授权的全局尺度混合容差执行，先登记后运行，旧7b/7b.1失败不覆盖。

小图重判通过、漏消息负例仍拒绝。六真实静态两层/logits逐位相同，最大梯度差4.22853e-16，全部通过。双端近零清单一致；除key bias还有单来源注意力、末层无监督目标、初始饱和。R/G0和AC/G0额外14/22项已取证，其余4案例额外项动态解释未完成，不全部称结构性零。

R/G0/mean三轮差1.55431e-15通过，共2完整诊断fit/6epoch。R/G3R/mean原实现被WSL内核OOM杀死(-9，anon-rss7595332KiB)，WSL7865MiB+swap2048MiB；不是GPU显存或数值失败。原partial不改，resource_failure.json记录终止。剩余4对及全部GPU/显存探针/8pilot未执行；无新pilot plan/CPU成功seal，不进入Prompt8。

新GPU验收补实际checkpoint SHA/sidecar/绑定，未跑真实GPU。新138（含于全量），1531v2+223旧=1754 passed，0失败/跳过，8/29既有warning。11,254旧非文档跟踪文件、184旧产物、34store引用SHA一致，16图/20schema不变；三文档仅追加。
产物prompt7b2_v1含内核、部分结果、静态、测试与零梯度取证（3次完成no-grad前向，1次资源终止；无optimizer）。未自动重试/改WSL/降门槛；先确认资源方案，才以新attempt继续。本地commit，不自动push。


## 2026-10-26 Prompt 7b.3：执行前登记（Codex）

基线07a0846，已读更新§4.1/P7b.3，pull --ff-only确认最新。新版模板授权收窄轨迹范围；不是运行后放宽数值阈值。保留6组旧静态与R/G0/mean已通过轨迹；按AC/G0/mean→AC/G3R/mean→R/G0/nonempty_mean补跑，各组独立进程串行，2秒采样子进程RSS，超过6.5GiB脚本终止并记录skipped_cpu_memory、不重试。R/G3R两组明确策略跳过，mean引用旧OOM、nonempty未运行，不伪造采样。

新放行版本独立封存：六静态通过，规定轨迹均有通过或合法跳过证据，AC/G3R/mean或R/G0/nonempty至少一组成功；实际数值失败不改记为内存跳过。旧六组严格策略保留可校验。新政策通过后才GPU两剖面各3次噪声诊断、1次历史对照、共享投影R合约G3R完整显存探针及8pilot（含探针）。内存/数值门槛不变，原HGT/model/trainer/优化器等不改。

零梯度仅按结构/参数名补分类，不增加前向取证；无法证明恒零者保留近零、饱和仅可能原因。有限初值案例是数值证据，不将其称为对任意输入的普遍证明。新产物prompt7b3_v1；旧产物不覆盖。系统内存/WSL/交换盘配置不变，不启动Prompt8。


## 2026-10-26 Prompt 7b.3：CPU/GPU数值通过，完整显存探针停止（Codex）

- 基线07a0846，先读§4.1／更新7b.3并pull --ff-only确认最新。新增 precision_guard／precision_policy／precision_zero 与130项测试；precision_gpu仅6行显式新schema分派，旧六轨迹政策保留。HGT/shared层/model/trainer/model_validation/优化器/DDG/token/图/标签/fold均未改。
- 更新模板直接授权：三组RSS保护轨迹、两组R/G3R策略不运行、至少一个额外维度完成后才放行；执行前已登记，无事后改数值门槛。旧6组static、R/G0mean成功轨迹及OOM记录只读复用。
- AC/G0mean三轮差1.110223e-16、峰值RSS4.105GiB；AC/G3Rmean差2.586820e-14、峰值5.850GiB，均过1e-9。R/G0nonempty在58.07s采样RSS6.953GiB>6.5，由脚本SIGTERM(-15)，未重试。两秒采样不是硬配额。覆盖条件由AC/G3R满足，新CPU清单/seal独立封存。
- 六组近零静态分类463次张量观测：a198 key bias，b180单不同来源，c18无监督末层目标，d67仅数值接近零；没有额外模型前向。不是463独立实验，d不冒称已证明饱和，监督梯度近零不排除weight decay更新。
- GPU G0/G3R各原实现2次＋shared1次三轮，通过；original重复差0，shared差7.629395e-6／3.576279e-7<1e-4。另1次原实现历史重放损失差0。共7诊断fit/21epoch，best/last与重载核验通过；不计pilot。
- 新pilot计划8项、独立目录，8组初值实际tensor digest与旧准备一致，配置/图/支持/seed/split一致（只layer_impl标识改为shared）。首项R合约G3R完成1epoch后，整卡最低空闲66MiB<100而停止；allocated1824.086MiB、reserved2048MiB、44.33s。无CUDAOOM；旧原实现探针allocated3299.848／reserved3536／free12保留。显存确实降低但门槛仍未通过，不把两次整卡差异全归因于层实现。
- 完整pilot=0/8，其余7未启动。部分best保留、last/result/成功receipt不存在；首轮canonical梯度未最终落盘，不臆报通过。没有完整每任务耗时，Prompt8的150次总时长估算待pilot完成；不从单轮外推，不启动Prompt8。
- 新130含于全部v2 1661＋旧223＝1884通过，0失败/跳过，8/29既有警告。11264旧跟踪文件仅允许4处改变，246旧产物不变；固定16图/20schema不变，三文档旧前缀保留。
- 详情PROMPT7B3_REPORT.md、training_changes §58；产物prompt7b3_v1含cpu、zero_classification、gpu_noise/history、独立pilot计划及失败收据。最终状态cpu_policy_gpu_numeric_passed_pilot_memory_stopped。本地commit，不自动push。
- 待用户选择资源方案后才显式新attempt：核查非必要GPU占用／单独allocator资源试验／更大显存设备；独立进程串行本轮已经采用。不自行修改WSL、模型或数值规则，不自动重试。


## 2026-10-26 Prompt 7b.4：执行前登记与资源统计澄清（Codex）

开始HEAD=54f21b5，按模板pull --ff-only到c97d737；阅读更新§4.1/7b.4。新增产物prompt7b4_v1，旧538个7系列产物先封存SHA。本轮不重做已经通过的数值等价检查；原HGT/shared层/model/trainer/DDG/图/token/标签/fold/初始化/优化器/早停均保持。

用户已明确批准两处调整：（1）原“进程外占用”改为“PyTorch分配器之外的未归属占用估计”，保留原公式与前后原始读数、增加近同时刻采样；（2）新策略每次必须--only一个任务、独立进程，外部串行调用8项；旧plan行为不变。实际旧resources没有total字段，4096MiB来自独立设备查询；peak reserved与最低free并非同一时刻。本进程CUDA/DGL/driver及后续惰性库分配也可进入差额，不能将约2GiB全归因于其他程序。

P7b3启动前记录used464/free3512MiB，不能支持“第一个任务前已占2GiB”。本轮只读查询used457/free3519MiB（total4096，三项差120MiB原样保留）；WSL未列出CUDA计算进程，Windows另存专用显存计数器/进程名，不将不同口径相加。未结束或修改任何程序。

新启动基线free>=3000MiB、运行最低free>=100MiB；失败即停，不降低阈值。先验证新接入，再从上一轮同一冻结初值运行R合约G3R完整探针，成功验收后才其余7项。新plan只引用旧prepared/initial，不重建随机初值；计划新增来源和资源策略绑定。若未完成8项，不生成伪精确150fit耗时估计、不启动Prompt8。

用户明确：最终实验计划在显存充足的服务器上完成；当前4GiB RTX3050限制仅是本地开发验收约束，不作为最终研究模型规模上限。尚未取得服务器具体设备/环境，迁移时仍需核验环境、输入/初值/配置身份及真实资源记录。


## 2026-10-26 Prompt 7b.4：资源接入通过、探针再次触发门槛（Codex）

新增preflight/resource_plan及64测试，run.py最小接入。用户批准未归属统计名称与逐任务新进程；旧plan行为保持。8个初值实际文件直接复用，来源比较只变runtime/git_head/resource_policy/resource_origin，其他配置/输入相同；新plan SHA e0ff577cd73f7fa1da841cf2f1fdd1e890ebc2ede27ac047cf369ff2db5c8344。

R合约G3R baseline4096/450/3526MiB，通过3000；CUDA/DGL最小初始化后4096/1742/2234，变化1292且Torch reserved=0。训练allocated1824.086/reserved2048，minfree76<100，epoch1后停止，无CUDAOOM。60个采样，0错误，原公式差额1972、减初始context观测后680，均不是其他进程归属结论。退出后free3503；“开始前就有约2GiB外部占用”无依据，旧表仅算术成立。

guard43.00s、完整子进程119.56s、完成epoch19.17s；partial best保留，无last/result/成功receipt，完整新关系梯度/重载/最终预测未验收。pilot0/8，1失败、7未启动，无重试；完整矩阵verify明确拒绝，非完整清点只报告缺失。未重复已通过数值对照，不开始Prompt8/150fit，也无完整耗时估计。

全部1725v2＋223旧=1948通过，0失败/跳过，8/29既有warning；新增64包含其中。11,271旧跟踪文件仅run.py+三文档变化、538旧产物SHA不变，原文前缀保留。HGT/shared层/model/trainer/DDG/token/图/标签/fold/优化器不变。详情PROMPT7B4_REPORT.md、training_changes §59；新产物prompt7b4_v1留WSL。

最终实验按用户计划在显存充足服务器；当前本地4GiB限制不应迫使继续改模型。服务器需另核验环境/路径/输入初值身份。本轮状态baseline_passed_pilot_memory_stopped，到资源门槛停止，本地commit、不自动push。


## 2026-10-26 Prompt 7c：本机local_dev_v1执行前登记（Codex）

开始读取26ea4cc的服务器迁移版时已询问服务器信息；同步期间文档更新到3aac85f，最新§4.9g明确改为本地8pilot，迁移移到以后§4.9h。本轮按最新文档执行；没有独立7c.4标题，包含本Prompt第4部分测试记录。WSL直接pull因DNS失败；通过用户既有Windows代理fetch，再由WSL git merge --ff-only核验，当前HEAD3aac85f。没有实施服务器迁移工具。

用户明确回复“暂时不考虑服务器，当前实验只是在本机，就是之前配置”，并批准“同意按 local_dev_v1 完成本地 8 次 pilot（推荐）”。新策略只用于新prompt7c_v1计划：基线free>=3000MiB；运行free<100只记memory_tight、不因此停止；OOM、非有限损失及其他执行/身份错误停止且不自动retry。完整批准原文、范围、8任务和直接来源plan SHA写入local_policy_approval.json，后续由plan引用。旧7b4的100MiB硬停止政策和失败产物保留，不重判成成功。

先做资源政策/计划来源链/验收最小接入和回归，再克隆原8份实际初值，R合约G3R先跑，通过完整梯度/重载/预测身份验收后其余7项独立进程串行；不重跑数值等价诊断、不改HGT/shared层/model/trainer/DDG/token/图/标签/fold/优化器/早停。
审查修正文档推测：旧跨时刻reserved与另次context之和不能证明发生显存换出；第一轮完成不保证后续不会OOM。possible_memory_spill仅耗时异常线索，保存checkpoint/系统负载也可导致；固定前3轮中位数收齐后，从第4轮起比较>2倍，不据此改训练或自动中断。

旧11,277跟踪文件与582历史7系列产物已记录SHA，三文档旧字节前缀封存。本轮产物只写新prompt7c_v1，仍在现有WSL。最终正式实验预计在显存充足服务器完成；本轮只本地开发pilot，不将本地与未来服务器结果混用。完成8项后只估算本地60/90/150fit时间，不自动进入Prompt8。


## 2026-10-26 Prompt 7c 完成：local_dev_v1与8项pilot

实施AI：Codex；用户批准已在本节执行前登记，approval JSON绑定新plan。
- 新增 experiment/local_dev.py：继承现有资源观察器；只将运行期低空闲判定改为提醒。直接读取冻结trainer原有history.jsonl，每轮seconds及连续epoch身份必须有效。前3轮中位数固定，从第4轮开始严格超过2倍才标possible_memory_spill。少于3轮明确不足以形成基线。
- 修改 experiment/preflight.py：独立注册local_dev_v1；启动≥3000MiB，运行100MiB字段在新版本中为提醒阈值。旧DEFAULT策略和默认行为保持。工厂仅显式新策略时创建LocalResources。
- 修改 experiment/resource_plan.py：新增prompt7c-local-resource-plan-v1来源协议；P7c→P7b4→P7b3逐层只读验证。绑定用户批准JSON、旧plan/seal与8项身份；逐一核验旧initial文件SHA/tensor digest/optimizer_steps=0/fit_seed。仅允许资源编排相关5个运行文件变化。
- 修改 experiment/run.py：新增--resource-policy local_dev_v1及--approval-record；向资源观察器传policy/history，result和receipt绑定提醒标志，验收从原采样与history独立重算。失败任务阻止新进程跳过后继续批次，只能用户确认后显式--retry同一任务，从原未训练初值开始。
- 修改 experiment/precision_gpu.py：audit_pilot_result只在显式传入新策略时切换资源验收。新canonical梯度、heldout支持及checkpoint逐位重载要求不变，默认调用仍保留旧100MiB门槛。
- 新增tests/test_local_dev.py；追加test_resource_plan.py和test_preflight_integration.py。覆盖低显存继续/旧策略停止、基线、OOM保留与批次停止、时长突增、篡改证据拒绝、成功复用、初值/来源不一致拒绝等。
- 本轮未修改hgt_layer.py、model.py、experiment/trainer.py、experiment/resources.py、原sco_models、DDG分析器、图/标签/token/fold或任何训练数值规则。

实际8/8通过，0失败/重试；G0/G3R四任务fold0 seed1。全部新canonical梯度、留出支持、env_source排除、预测标签身份、best/last重载通过。原50epoch/早停/学习率/初值保持；协议为dfg-v2-nested-v1，全固定图前向，不能与历史paper_kfold混写。plan SHA 363814c88c3dd9e22aa61a9bf6e2f5ee5f59b7dfc7262d6685e671e287aa94e5。

| 任务/剖面 | best/last轮 | 启动free | peak allocated/reserved | 最低free | 进程秒 |
| --- | --- | --- | --- | --- | --- |
| 重入合约/G0 | 8/15 | 3725 | 1229.7/1484 | 707 | 448.75 |
| 重入合约/G3R | 8/15 | 3538 | 1893.5/2148 | 81 | 415.64 |
| 重入节点/G0 | 17/24 | 3712 | 807.8/1002 | 1189 | 382.70 |
| 重入节点/G3R | 18/25 | 3709 | 1258.0/1494 | 662 | 455.54 |
| 访问控制合约/G0 | 9/16 | 3645 | 919.6/1118 | 976 | 316.81 |
| 访问控制合约/G3R | 9/16 | 3607 | 1401.1/1610 | 478 | 344.87 |
| 访问控制节点/G0 | 13/20 | 3611 | 561.4/640 | 1447 | 210.46 |
| 访问控制节点/G3R | 16/23 | 3601 | 850.4/946 | 1049 | 288.45 |

显存MiB、轮次1起算。唯一memory_tight为R合约G3R min81；全部possible_memory_spill=false，无OOM/非有限/采样错误；不宣称已证明无换出。后台会话中断后核对8项均已完成，未重跑。

测试定向184/4warnings；全1792v2/8warnings＋223旧/29warnings＝2015通过、0失败/跳过，新增67包含其中。命令详见PROMPT7C_REPORT与training_changes§60；测试argv/log/JUnit在新批次。
11,277原文件和582旧产物核验，三文档只追加。新增报告PROMPT7C_REPORT.md；运行产物prompt7c_v1留E盘承载WSL，无历史清理。

Prompt8时长只作估计：150fit约14.79h，阶段A60约5.83h，B90约8.95h；G1R/G2R/G3按canonical线性插值，20个schema计数与store核验一致。真实其他折早停和负载可能明显不同，不把这8次用于F1比较结论。未执行Prompt8。
最终实验按用户意向迁移足量VRAM服务器，本机限制仅当前开发；本轮先本机，服务器条件待实际核验。完成后停止并等用户确认；按共享规则本地提交，不自动push。


## 2026-10-26 Prompt 8 执行前登记（Codex）

已同步4f537d9，先读共享§4.1和最新Prompt8。用户批准保留旧8项批准记录、另建150项批次来源授权；批准5折合约仅描述性、节点zsplit、阶段A原始p且Holm待B。当前只授权准备计划，按模板在计划/磁盘/时长具体可审阅后确认执行A；B仍须中间报告后另确认。

既有16图/20schema及8pilot全部核验通过，未读取pilot F1作设计选择。新批次prompt8_v1；report_spec冻结6个带类别和源码SHA的争议文件，1/2跳按真实模型消息方向且路径含指定新增关系，人工审阅按现有表记录。统计方法细节随plan封存。150fit不复用pilot；阶段A60约5.8h，阶段B90约9.0h，均为单折插值排期估计。

本机RTX3050 4GiB仅当前开发条件，最终完整实验按用户计划在显存充足服务器整批重跑，不与本机结果混用；服务器环境尚未实际验收。


## 2026-10-26 Prompt 8：150项计划封存与训练前验收（Codex）

新增batch_plan、batch、stats、reporting及四组测试，仅最小接入run.py，README追加命令。原DDG、HGT/shared层、model/trainer、tokenizer、输入图/标签/token/fold、学习率/优化器/早停及初始化算法均不改。审批范围和统计解释采用前节用户批准的两项选择；没有改变主要终点或选型规则。

计划SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de，seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8；新批次prompt8_v1/batch1，150个全新初值、30个5剖面家族全部完成。独立只读验收150/150：optimizer_steps=0、task/fold/profile/fit_seed、文件/tensor SHA和G0共同语义参数逐值一致；正式fit=0/150，A=0/60、B=0/90。准备2172.81秒，初值验收20.82秒。新关系沿用各profile自己Xavier范围的既有批准规则，不宣称所有新增关系跨profile数值完全一致。

配置shared_projection/mean/inside_token/seed1、hidden128/2层8头；合约LR0.0005→max0.01、节点0.0002→max0.005，50轮、patience7、delta0.001保持。协议dfg-v2-nested-v1，inner_train监督、inner_val选best/早停、结束后outer_test；全固定图前向，非完全归纳测试，不直接和旧paper_kfold历史F1比较。关系支持CSV已生成，真实梯度/重载/F1尚待正式训练。

空间预估checkpoint23.42GiB+initial2.93GiB=26.35GiB，要求52.70GiB；WSL内部准备时825.96GiB，Windows E实际248.15GiB，均足够。WSL位于E:/Smartcontract/Ubuntu-22.04，实际initial2.73GiB，无C盘大型产物或旧文件删除。A约5.83h、B约8.95h只是原pilot排期估计；新150fit不复用8pilot，不打开其F1用于选择。

最终测试175定向（包含于全量）、1967 v2＋223旧=2190通过，0失败/跳过，4/8/29既有弃用警告；日志/JUnit/argv在新批次。集成修复了interim包装结果与完整summarize分发，并增加真实调用链回归；失败前置检查、中断记录、显式重试和直接入口顺序均测试。11280原跟踪文件除允许5处外不变；817历史产物、三文档前缀不变。

完整报告和逐文件实施见PROMPT8_REPORT.md、training_changes §61。A执行前仍需按§4.10第1部分确认；A中间报告固定G3R/G0，不选G*，Holm等待B；中间报告后停下再确认B。未授权执行记录不会伪造为approved，未启动GPU训练、额外seed、诊断组或其他五类。本地提交，不自动push。

未来五类按EXTENDING：注册任务→核验源码锚点/token→生成封存fold→cli build→run plan(G0与R/AC内层选择的G*)，不在新增类别重新选型；现在仅预留通用接口。最终正式实验按用户计划在显存充足服务器整批运行，当前4GiB只是本机开发约束；服务器环境/输入迁移未验收，不与本机分数混用。


## 2026-10-26 Prompt 8A：阶段 A 启动与执行中记录（Codex）

已读更新§4.1/8A并pull同步至6dd5d986bf6fa1fade1bc8b247a9fd3035712385。本节仅登记启动事实和验收准备，不代表60项完成；最终结果或阻断原因后续追加。未修改任何生产代码，旧DDG/HGT/shared层/tokenizer/trainer、固定图/标签/fold、初始化及数值训练规则保持。

继续使用prompt8_v1/batch1原计划：plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de，seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8。用户本轮8A原文已排他写入stage_A_authorization.json，明确只授权A的60项G0/G3R，B=false；不修改旧准备授权、plan或seal，不复用旧pilot成绩。

前置cli store verify通过。文档初始“batch verify报告0/150”不适用现有要求完整阶段的CLI，改调用已存在run.verify(require_complete=False)只读清点；前置时0/150，最终仍严格batch verify --stage A验收60项。150份保存初值和30个家族逐值核验通过，optimizer_steps=0、fit_seed和文件/tensor SHA一致，未重新初始化。证据preflight_acceptance.json，runtime精确匹配。

既有定向175通过（包含于v2），全v2 1967加旧223合计2190 passed，0失败/错误/跳过；实际命令与日志/JUnit在新prompt8a_v1，详见training_changes §62。新辅助preflight.py、validate.py、execute_stage.py、progress_only.py仅置该运行产物目录，不接入或更改封存计算代码。

按原plan顺序启动独立子进程串行阶段A；执行中只看epoch/耗时/资源字段，不查看/汇总F1，待全部60项通过后才生成中间报告。冻结trainer原有日志照常写文件，不tail含F1全文。OOM/非有限值/校验错误停整批、不自动retry；成功任务核验后复用，不按成绩挑折。运行free低于100MiB仅记memory_tight，启动free≥3000MiB不变。前置GPU free3524MiB；E盘实际free264104554496字节，WSL虚拟free883910905856字节，分开记录。产物仍在E盘承载WSL，不清理旧数据。

结束步骤为batch verify --stage A，再batch interim --stage A；报告REPORT_INTERIM_A.md/CSV及文件SHA绑定批次收据。只G3R−G0，best主/last辅，节点原始p、合约描述统计、Holm待B，不计算G*，完成后停下。此刻不宣称训练、完整梯度/重载验收或DDG收益已完成。

**最终实验按用户安排在显存充足服务器整批重跑，当前RTX3050 4GiB仅本机限制。** 服务器尚未部署或实际验收，未来不能混合本机/服务器成绩；本轮不开展服务器迁移或阶段B。实施、核验、记录AI：Codex；三份文档旧正文只追加保留。


## 2026-10-27 Prompt 8A 完成：60项阶段 A 与中间报告（Codex）

启动节及历史正文保留。本轮生产Python零修改，复用6dd5d98对应冻结runtime；prompt8_v1/batch1 plan SHA仍07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de，seal仍55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8。150保存初值不重建，A的60项全完成、0失败/重试、均attempt_001；B=0执行。execute、独立verify、interim均退出0，60通过后才打开F1。

best主结果（Buggy-F1百分数、等权折均值±样本SD；差值pp）：

| 任务 | G0 Buggy-F1 | G3R Buggy-F1 | G3R−G0（pp） | 提升/持平/下降折 |
| --- | --- | --- | --- | --- |
| 重入合约 | 92.7326 ± 5.4566 | 94.1612 ± 6.3579 | +1.4286 | 1/4/0 |
| 重入节点 | 96.4276 ± 6.5918 | 96.9344 ± 6.6127 | +0.5068 | 10/0/0 |
| 访问控制合约 | 94.6066 ± 1.6532 | 95.4075 ± 3.2189 | +0.8009 | 1/3/1 |
| 访问控制节点 | 96.1753 ± 6.2062 | 95.9716 ± 6.1255 | -0.2037 | 2/5/3 |

last辅助结果：

| 任务 | G0 Buggy-F1 | G3R Buggy-F1 | G3R−G0（pp） | 提升/持平/下降折 |
| --- | --- | --- | --- | --- |
| 重入合约 | 92.1620 ± 3.0510 | 95.7037 ± 4.7257 | +3.5417 | 3/1/1 |
| 重入节点 | 97.0827 ± 6.6227 | 97.1568 ± 6.4290 | +0.0741 | 8/0/2 |
| 访问控制合约 | 86.6580 ± 6.9124 | 84.9255 ± 5.7693 | -1.7325 | 0/3/2 |
| 访问控制节点 | 93.9087 ± 5.7938 | 94.7086 ± 5.9949 | +0.7999 | 3/2/5 |

协议为dfg-v2-nested-v1：inner_train监督、inner_val早停/选best、结束后outer_test评分；全固定图前向，非完全归纳评估，不直接比旧paper_kfold。原HCG节点计分，env_source不计分。重入节点best10折全改善，均值+0.506835pp、bootstrap95%[0.251500,0.841574]、原始p0.001953125；last仅+0.074054pp且p0.322265625。访问控制节点best−0.203717pp、p0.6055766163；两项合约收益集中个别折，不称全面稳定提升。四任务完整BF1/MF1/P/R、pooled OOF和敏感性表见中间报告；Holm等B，不计算G*。

验收：全部60项binding/checkpoint/预测身份/env排除及训练时best/last逐位重载证据通过；1986条任务折级训练支持canonical首轮消息梯度>0、94条heldout-only零梯度并保留。测试1967v2＋223旧=2190 distinct passed、0失败/跳过；175定向包含在v2，不重复计数。测试及结束命令日志在prompt8a_v1。

资源与耗时：execute33548.08秒（9.32h），fit内部合计16202.67秒（4.50h，含验证/保存/重载/导出）；另verify208.23秒、interim432.69秒。每个新任务启动前两遍完整验收所有前项，60项对应3540次既有结果检查，存在CPU/I/O编排成本。只读timing audit前31项启动前区间4310.60秒、子进程15966.28秒，不能外推为全批纯校验计时；本批未改控制器，也没有把打印日志等同这些检查。最大allocated/reserved1893.47/2148MiB、最低free18MiB；5项memory_tight、1项possible_memory_spill，后者只是时长提醒，不证明显存换出。无OOM/数值/验收失败。

报告prompt8_v1/batch1/reports/interim_A/REPORT_INTERIM_A.md SHA 55933fa880ef9e4f26c6c1d502f4f959d469d0a8fc7aba734403d8a589443b51，report.json＋15CSV由report_receipt及batch_records/interim_A.json绑定。详细记录training_changes §62.7–62.10及PROMPT8A_REPORT.md。人工512/111边表仍未填，完整语义/泛化/因果贡献未证明；不做B、G*、额外seed或其余五类。

最终正式实验按用户安排在足够显存服务器整批重跑；当前4GiB只约束本机，服务器环境未实际验收，不混本机和服务器成绩。阶段A中间报告交付后停止；下一阶段另行授权。实施、复核与记录AI：Codex。

## 2026-10-27：Prompt 8A 结果GitHub归档（Codex）

用户授权推送后，补充归档1721份Prompt8/8A文本结果、预测与验收记录；详细范围与SHA见docs/github_archive_prompt8a_2026-10-27.json及同名.md。270份模型/初值.pt遵循忽略规则保留本地并记录SHA；原输入仍需单独提供。没有新增训练、改变计算文件或修改历史seal，B保持未运行。
