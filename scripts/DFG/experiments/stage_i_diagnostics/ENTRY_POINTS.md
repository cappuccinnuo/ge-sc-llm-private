# DDG 图的入口与方向约束

日期：2026-10-19；Codex。本说明为第 1 步入口整理；不修改原加载器或冻结实验。

## 1. 哪个入口支持什么图

| 入口名称（旁路校验参数） | 实际实现 | 允许的增强图 |
|---|---|---|
| `legacy` | 原训练入口经 `sco_models/graph_utils.py:426–445 reflect_graph` | 原 CFG/CG 和仅 DATA_DEF_USE 的 E1/E2 |
| `stage_f` | `scripts/DFG/state/stage_f/model_adapter.py:4–21` | 原图、E2、E3a、E3b；只负责图方向适配，不是完整训练器 |
| `e23_pilot` | `scripts/DFG/experiments/e23_pilot/model.py:19,49–51,97–103` | 当前正式 E2/E3a/E3b 模型装配；H1/H2复用此模型与fit |

`scripts/DFG/state/model_adapter.py` 是较早 Stage E 版本，本校验不把它冒充为支持全部顺序关系的 Stage F 入口。

原 `reflect_graph` 在第 432 行只对 `DATA_DEF_USE` 特判保持正向，其他关系按原方式反射。因此，直接给旧训练脚本传入 E3a/E3b，可能在同名状态关系下加入反向消息。Stage F 先分离四类新增关系，仅对基础边使用原反射，再原样加入正向增强关系。

四类关系来自现有 `scripts/DFG/state/stage_f/__init__.py:3`：
- DATA_DEF_USE
- STATE_DEF_USE
- STATE_ACCESS_ORDER
- EXTERNAL_CALL_BEFORE_STATE_WRITE

## 2. 新增旁路 API

```python
from scripts.DFG.experiments.stage_i_diagnostics.entry_validation import validate_entry
audit = validate_entry(graph, "e23_pilot")
```

检查项：
1. 有向 multigraph，每个节点具有 node_type，每条边具有 edge_type；
2. 普通 CFG/CG 关系保留，不要求固定基础关系白名单，不删除边；
3. 未支持的保留增强前缀（DATA_/STATE_/REV_/EXTERNAL_CALL_）拒绝；
4. 状态关系图给 legacy 拒绝；未知入口拒绝；
5. 输出 JSON-safe 的关系计数、canonical关系和方向策略，原图保持不变。

**这是显式调用的旁路 API，不是对原脚本的全局拦截。** 直接运行原训练脚本会绕过本检查。本轮不修改旧训练脚本来强行接入，因此不存在“现在所有旧命令都已安全”的保证。

该函数只判断关系方向兼容性，不代替现有标签/特征/源码 SHA、字典、模型输入、checkpoint 和 receipt 校验。普通关系名称由原图提供，其具体语义不由本函数重新认证。

## 3. 冻结实验和本轮诊断入口

- 历史 Stage G：`scripts.DFG.experiments.e23_pilot`。
- 历史 H1：`scripts.DFG.experiments.e23_cv.control`；H2：`scripts.DFG.experiments.e23_h2.control`。
- 已完成90次结果；本轮不能重新 seal 或重新运行训练作为诊断。
- 本轮诊断代码仅在 `scripts/DFG/experiments/stage_i_diagnostics/`；具体执行命令见该目录 README。
- 仅使用已有 checkpoint，恢复原 canonical 字典，不在评分阶段新建模型参数。
- 消息置零保留 relation 注册/聚合分母；它和删除边不是同一种干预，也不等于将 E3b 变回重新训练的 E3a。

## 4. 校验测试

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
conda activate mando
PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/stage_i_diagnostics/tests/test_entry_validation.py
```

测试包含真实 Stage F 与旧 reflect_graph 对照：普通边保留旧反射、DATA_DEF_USE 正向、三个状态/顺序关系在 Stage F 正向，而旧加载器会反射。另验证未知入口、未知增强关系、缺元数据、有向多重图、平行边、原图不变与 JSON 安全输出。

2026-10-19 executable test result: **25 passed, 0 failed, 0 skipped**; 4 existing DGL distutils deprecation warnings. The test does not modify model/training files.
