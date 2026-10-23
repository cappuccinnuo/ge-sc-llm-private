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
