# Prompt 7b：共享投影接入与数值验收报告

日期：2026-10-26。实施、审查、测试与记录 AI：Codex。
基线：`dfg-v2@60aa23e`；已读共享上下文与更新后的 Prompt 7b，执行 `git pull --ff-only origin dfg-v2` 确认最新。

## 1. 结论与停止位置

**共享投影代码接入及回归测试完成，但 CPU 数值验收未通过；Prompt 7b 尚未全部完成。GPU 对照、显存探针、8 次 pilot 和 Prompt 8 均未启动。**

四组 mean 对照的初始逐层输出和 logits 逐位一致，逐参数梯度通过用户批准的门槛；但三轮 train/inner-val 损失差都超过原定 1e-6。随后 R 合约 G0 的 nonempty_mean 虽前向逐位一致，一个 query 权重梯度超标，按门槛停止，未训练该组，也未运行最后一组。

实际完成的是 **8 次 CPU 三轮数值诊断 fit（4 对，24 epoch）**，不是要求的 8 次 GPU pilot。后者为 0/8。代码测试 1366 项 v2＋223 项旧 DDG/graph_utils＝1589 passed，0 失败/错误/跳过，其中新增94项；测试通过不等于真实数值验收通过。

## 2. 实际修改文件与理由

- `hgt_layer.py`：新增 `HGTLayerSharedProjection` 和 `HGTLayerSharedProjectionNonEmptyMean`。直接继承构造器；每层每种节点类型只计算一次 k/v/q，再在各 canonical 中复用。关系 einsum、attention、聚合、残差、dropout、norm 保持原顺序。源码结构对照测试约束除投影放置外的 forward。原 `sco_models/model_hgt.py` 不改。
- `model.py`：新增 `layer_impl=original|shared_projection`，默认仍为 original；校验字段与实际层类相符。参数名/形状、构造时 RNG 均保持并有测试。
- `experiment/init.py`：记录 layer_impl，拒绝不同实现混在同一个初始化家族；语义共同初值算法不变。
- `experiment/checkpoint.py`、`trainer.py`：绑定实现，拒绝跨实现恢复；新增配置检查和结果字段，Adam/OneCycle/早停/best 数值循环不改。
- `experiment/run.py`：新增计划参数 `--layer-impl`，写入 plan/config/job/prepared/initial/receipt；旧文件缺省字段仅解释为 original，不修改或重封历史产物。
- `experiment/projection_validation.py`：独立 CPU/GPU 数值验收入口。复用 trainer.fit、冻结初值和划分，记录逐参数误差，拒绝 NaN/Inf、轮号错误和相互矛盾的汇总；资源记录覆盖 setup/fit/异常/退出。GPU 路径本轮未执行。
- 新增3个测试文件：`test_shared_projection.py`、`test_layer_impl_binding.py`、`test_projection_validation.py`；更新 experiment/README.md、本报告及三份实施记录。

没有修改 DDG 语义、tokenizer、原 HGT、图/特征/标签/fold、模型超参数或冻结训练规则。共享投影的数学定义等价，不代表浮点反向或多轮优化轨迹逐位相等。

## 3. 用户批准的选择与原失败证据

1. 用户明确要求执行更新后的 Prompt 7b，因此按第1部分实现可选共享投影层，保留 original 与全部历史批次。
2. 文档未定义“最大相对梯度差”的分母。用户批准按每个参数张量计算 `max(abs(new-old))/max(max(abs(old)),max(abs(new)))`，并另外记录逐元素相对差。两边都为零时比值为零，不用人为的大 epsilon 隐藏差异。
3. 小图纯相对门槛出现16项失败、25项通过；失败参数为近零 key bias，绝对差约1e-10～1.9e-9。原日志保留在 `shared_projection_original_gate.log`。用户随后批准固定公式：

```text
max_abs_gradient_difference <= 1e-8 + 1e-5 * max(max_abs_old, max_abs_new)
```

真实数据开始前已冻结上述公式。前向仍须 torch.equal，CPU三轮损失门槛仍为1e-6，GPU对照为1e-4，整卡最低空闲显存为100 MiB。本轮没有因真实结果失败继续提高这些阈值。

## 4. 真实 CPU 验收结果

| 任务 | 剖面 | reducer | 三轮最大损失绝对差 | 结果 |
|---|---|---|---:|---|
| reentrancy_contract | G0 | mean | 2.92062759e-06 | 轨迹门槛失败 |
| reentrancy_contract | G3R | mean | 7.03334808e-06 | 轨迹门槛失败 |
| access_control_node | G0 | mean | 8.82148743e-06 | 轨迹门槛失败 |
| access_control_node | G3R | mean | 2.31862068e-05 | 轨迹门槛失败 |
| reentrancy_contract | G0 | nonempty_mean | — | 梯度门槛失败，未训练 |
| reentrancy_contract | G3R | nonempty_mean | — | 此前门槛失败，未执行 |


所有已执行的5组静态对照，逐层输出与最终 logits 都逐位一致。四组 mean 梯度通过；R/G0/nonempty_mean 的失败参数是 `gcs.0.q_linears.7.weight`：绝对差1.5931533425828093e-8，梯度尺度2.279119689774234e-5，允许差1.0227911968977424e-8，张量相对差0.0006990214。因此在静态阶段停止，不能声称“所有梯度通过”。

四组 mean 每边各跑3轮，保留50-step OneCycle、patience7/delta0.001、原任务学习率、固定 nested fold0 和 fit seed；每边都从同一冻结未训练初值启动。8次诊断均完成 best/last 保存及 CPU 重载，logits 逐位一致。未使用诊断 F1 选择模型或宣称改善。

首个 AC/G0 的初版静态检查覆盖全体节点两层输出及监督行 logits；后来补充全部7710个节点的最终 logits，仍逐位一致，见 `first_full_forward_check.json`。没有重训，也没有覆盖原失败记录。补充脚本第一次因 PYTHONPATH 缺失在导入时退出，保留日志，显式项目路径后成功。

首组之后只收紧验收脚本的非有限值、历史身份和异常资源校验，并扩大静态 logits 覆盖，不改模型与 fit 数值规则。四组 mean 均完整收集，未选择性丢弃失败；nonempty_mean 静态失败时停止其训练和最后一组。报告生成脚本曾有一次 Python 引号语法错误，未写入任何报告/历史文件；随后直接按最终 JSON 生成记录，不影响计算。

## 5. 已排查的原因与结论边界

AC/G0 的只读证据见 `ac_g0_diagnosis.json` 与可复跑脚本：初值 digest 都是 `d03020d8...cb83`；三分区监督清单、optimizer_schedule、最终 Adam 参数组/step、标准化 scheduler 一致。binding 只在 layer_impl 和对应 config digest 上不同。未发现错图、错初值、错标签、错划分或优化器配置混用。

首次 backward 最大梯度绝对差2.9802322387695312e-8；362个参数中20个依靠绝对容差项通过。第三轮后265个参数张量有差异，最大参数差8.354708552360535e-4，位于 `gcs.0.q_linears.7.weight`。共享投影改变反向累加顺序，近零梯度可改变相对大小或符号；Adam 的 eps=1e-8，可能放大这种差异。这与观测相符，但没有逐步梯度/参数轨迹，不能证明它是唯一原因。

初始前向一致不能推出多轮训练满足1e-6；预测类别暂未变化也不能替代门槛。不能把这些数字直接解释为 DDG 标签/构图错误，也不能宣布整个实现已经通过等价性验收。

模板背景中“不是 v2 关系本身的代价”表述过强：重复投影可以优化，但新增关系仍有关系变换、attention、中间张量和参数成本。本轮未测共享实现 GPU 峰值，不能承诺已解决4GB显存问题。此处只记录分析，不擅自更换设计。

## 6. 测试、不变量与未执行事项

- 新增94项通过；完整v2 1366 passed（8条既有警告）；旧 DDG/graph_utils 223 passed（29条既有警告）；合计1589，0失败/错误/跳过。警告为 DGL/distutils、NetworkX gpickle 等既有弃用项。完整日志/XML留存。
- 允许修改范围外11061个已跟踪文件摘要一致；三份文档旧正文保留，只追加。旧 Prompt7 plan/seal/失败 attempt 保留，不在旧 plan 上切换实现或 retry。
- 固定图 cli verify 通过：4任务、16图、20个已记录 schema/model-construction；本次 verify 不构造模型、不前向。最终图仍为 `graphs_v2_r1/store.json`，SHA `ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4`。
- 未执行：nonempty_mean 两组三轮轨迹、最后一组静态对照、AC节点GPU历史对照、GPU新旧实现对照、R合约G3R显存探针、8次pilot、Prompt8。新pilot plan未封存；没有新的GPU峰值、完整梯度验收或可靠的Prompt8 GPU耗时估计。
- 没有实施第二级端点投影、批次化、AMP、降维/删边、优化器修改、依赖升级，未关闭用户程序。

AC节点历史记录已核验存在：51 train/6 val、constructor10000/fit1010000、原HCG与未训练初值；不能用本轮 nested 40/11/6 去比较历史损失。相关诊断代码已准备，但未真实运行 GPU。

## 7. 实际命令与产物

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json

python -u -B -m scripts.DFG.dfg_v2.experiment.projection_validation cpu-case \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json \
  --task access_control_node --profile G0 --reducer mean \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b_v1/cpu/access_control_node_G0_mean
```

上述输出已存在，不能覆盖；复查优先读取已有证据。其余实际 CPU 命令及顺序见 `run_cpu_remaining.py` 和日志，遇静态失败即停止。

产物：`scripts/DFG/experiments/artifacts/dfg_v2/prompt7b_v1/`。包含 cpu/、测试XML/log、批准选择、源码摘要、全输出补核、只读诊断、store_verify、final_acceptance。运行原件留 WSL，不写入 C 盘临时目录；代码和记录本地提交，不自动 push。

建议下一步先针对固定初值做一步梯度—Adam 更新追踪，定位数值分叉，再由用户决定保留严格门槛或修订新的验收协议。未经批准不改 eps、不调高损失阈值、不推进 GPU。本轮停止在 `implementation_tests_passed_cpu_numerical_gate_failed`。
