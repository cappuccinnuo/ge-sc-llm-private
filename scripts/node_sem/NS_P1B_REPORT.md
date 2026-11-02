# NS-P1b 验收报告

实施：Codex，2026-11-01。分支 node-sem；输入 HEAD：0b1152b3083f068d94308f6244c47807a5f01c50，已快进同步 r5 文档。

**NS-P1b 已完成：运行版本绑定已拆分，r5 S1 初始尺度已修正，全部 CPU 验收通过。本轮没有正式训练或效果比较。**

## 实际改动

- `__init__.py` 增加 8 个训练路径模块的显式 RUNTIME_MODULES；非训练生产者/侦察/验收脚本不进入 execution runtime。未来生产者实现由模态 manifest 绑定，新增训练模块必须显式登记。
- `execution.py` 升级 nodesem-execution-v2。execute 默认要求当前运行源码完全一致；verify 核验历史 plan/seal/authorization、启动记录 runtime、收据及产物 SHA。v1 只能 verify，不改写旧计划；v1 启动记录比较完整历史 runtime，不裁剪成新清单。
- 新 v2 完成收据另有 receipt.seal.json，避免收据中未用于数值计算的字段被改动后仍通过。完整 verify_one 继续核对输入、checkpoint、监督身份、资源和独立重算指标。S0 仍通过 8H 自己的有效运行版本链核验。
- `adapter.py/model.py/init.py` 为 S1 增加唯一模型级 LayerNorm(64)，仅归一化非空池化行；空行仍为零，适配器输出为对应 Linear 偏置。嵌入 N(0,1)、第0行零；LayerNorm 权重1/偏置0；Linear仍Xavier/偏置0。初始化版本独立升级 v2，parameter_seed 来源不变。
- S0仍原512→128 Linear，没有 nodesem_shared；原DFG、HGT、tokenizer、图、标签、折和8H产物未变。

新增 `p1b_acceptance.py` 只做 CPU 验收，并将验收脚本 SHA 单独封存。r4 路径仅用于所要求的无训练诊断，不作为可选正式模型。

## 初始尺度

任务均为重入节点 fold0 G3R，三个零步模型各一次 eval 前向。

| 诊断 | S0 | S1 r4 | S1 r5 |
|---|---:|---:|---:|
| h0 全部元素标准差 | 673.8923 | 0.002196 | 0.459034 |
| 各类型 h0 标准差范围 | 161.273–1981.992 | 0.001617–0.004121 | **0.433297–0.540383** |
| 第一层归一化前标准差范围 | 43.373–533.391 | 0.034600–0.040775 | 0.122679–0.149280 |
| 第一层归一化后标准差范围 | 1.000000–1.000000 | 0.995850–0.997006 | 0.999657–0.999774 |
| 多入邻居的 head 最大权重≥0.99 | 88.8918% | 0% | 0% |

h0 = gelu(adapt_ws(inp))。r5全部17类型通过预定[0.05,5]门槛。完整逐类型均值/标准差/绝对值99分位及逐canonical注意力见 [init_scale.json](artifacts/ns_p1b/init_scale.json)。注意力比例按目标节点×canonical relation×head计算；多邻居共30680项，避免把单邻居必然权重1当作注意力集中。若计入单邻居，三者为98.8328%、89.4926%、89.4926%。

真实r5嵌入大小32100×64，非padding权重经验标准差0.999573，第0行全零；LayerNorm初值符合要求。模型参数6190692，比r4仅增加128。

需要收紧模板中的解释：r4输入确实很小，但经过冻结HGT的偏置/残差/归一化后输出尺度仍接近1；不能只凭尺度断言“无法学习”或“必然提前停止”。本轮未做r4/r5训练效果对比，r5决定早于诊断和S1训练，不按分数选择。

## 获批的标签边界

冻结 make_model/validate_registration 会读取图内标签做装配和完整性核验。用户批准保留它们，要求尺度/注意力统计及r5门槛不使用标签，也不读取评分结果。本轮没有另造模型或更换输入。

诊断JSON中的 labels_read、metrics_read、score_or_label_access=false，仅指诊断计算；不代表冻结装配从未读取标签。完整说明和用户原答见 [diagnostic_scope_approval.json](artifacts/ns_p1b/diagnostic_scope_approval.json)。这一边界已在诊断启动前封存。

## CPU 验收

- **S0等价通过**：旧/新入口各2轮，初值、输入、字典、节点身份、非特征binding、逐轮loss、最终/best/last权重、Adam、scheduler数值及预测逐位相同。scheduler方法沿用已批准的同类同实现核验。构造耗时16.693/30.823秒，fit耗时37.330/34.629秒；仅maximum_training_epochs改2，schedule_epochs仍50。见 [s0_equivalence.json](artifacts/ns_p1b/s0_equivalence.json)。
- **S1单轮冒烟通过**：train loss 0.85484159，inner-val loss 0.82609999，均有限。共享bag、norm的权重/偏置以及17个Linear的权重/偏置全部有非零有限梯度，共37个参数张量；gcs/classify初值与8H完全相同。best/last重载在inner-val/outer-test均一致。见 [s1_smoke.json](artifacts/ns_p1b/s1_smoke.json)。
- **旧计划归档核验通过**：acceptance_revision1的60个S0结果全部只读验收；current_code_equality=not_required指NodeSem当前源码，8H自身有效运行版本仍严格核验。见 [historical_verify.json](artifacts/ns_p1b/historical_verify.json)。
- 原NS-P1三个产物目录共118个文件逐SHA保留。临时等待确认的记录 progress_pending.json 保留作过程证据，最终状态以 completed.json 为准。

本轮合计3次CPU fit、5个epoch、0正式fit、0 GPU；短检查分数不进入正式结果。

## 测试与命令

198项NodeSem、2653项DFG v2、223项原回归，共 **3074通过、0失败、0跳过**。已有DGL distutils/NetworkX gpickle弃用警告分别4/9/29。初次新空行测试出现批量Linear与单向量Linear舍入差异，改为相同批量形状后仍用逐位比较；失败证据保留，未放宽阈值。

以下命令使用既有mando环境，CUDA_VISIBLE_DEVICES为空、OMP/MKL=2、PYTHONDONTWRITEBYTECODE=1，以及既有TREE_SITTER_LIB_DIR：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -B -m scripts.node_sem.p1b_acceptance prepare
python -B -m scripts.node_sem.p1b_acceptance archive
# 获批诊断边界后，依次运行：
python -B -m scripts.node_sem.p1b_acceptance scale
python -B -m scripts.node_sem.p1b_acceptance s0
python -B -m scripts.node_sem.p1b_acceptance smoke
```

这些验收阶段已执行，拒绝覆盖/自动重试。只读复核历史结果的命令为：

```bash
python -B -m scripts.node_sem.execution verify --plan scripts/node_sem/artifacts/ns_p1_equivalence/acceptance_revision1/batch/plan.json
```

## 范围与交付

详细变更见[训练变化§73](../../docs/training_changes_2026-10-07.md)，摘要已追加[PROGRESS](PROGRESS.md)与[HANDOVER](../../HANDOVER.md)，注明修改AI为Codex。旧文件正文保持不变。

未运行正式K折/GPU/其他seed，未推进NS-P2或评估S1检测收益。后续特征生产者仍须完成独立的泄漏扰动验收；本轮载体测试不能代替它。最终实验按用户计划在显存充足服务器开展，当前RTX3050 4GiB仅属本地开发限制；本轮未部署或测试服务器。

产物保存在WSL。代码和文本证据本地提交，NPZ及checkpoint保留本地，不自动推送GitHub。
