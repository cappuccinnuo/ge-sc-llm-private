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
