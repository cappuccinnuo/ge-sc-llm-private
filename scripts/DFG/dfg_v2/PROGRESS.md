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
