# Prompt 7b.1：float64 严格验收与停止报告

日期：2026-10-26。实施、复核、测试和记录 AI：Codex。
基线：dfg-v2@c079e3ac934111a8e1ac8777a46fd3d716e3eeec。已读取更新后的§4.1与Prompt 7b.1，执行git pull --ff-only origin dfg-v2，结果Already up to date。

## 1. 结论与停止位置

**新增float64验收工具和回归测试完成；本轮数值验收未通过，Prompt 7b.1整体未完成。**

DGL 0.6.1 CPU支持本轮要求的float64操作。正常实现的小图前向输出逐位一致；但严格的纯相对梯度门槛在数学梯度为零的key bias上失败。按照文档“任何一项不满足：停下报告，不放宽门槛”，正式预检在第一个mean/use_norm=True案例停止，未启动6组真实图、三轮float64训练、GPU噪声重复、GPU历史对照、显存探针、8次pilot或Prompt 8。

代码回归为1393 v2＋223旧DDG/graph_utils＝1616 passed，0失败/错误/跳过；其中新增27项是子集，不能重复相加。**这些测试确认验收工具正确拒绝失败，不表示原/新HGT通过了规定的数值门槛。**

## 2. 新建和修改文件

- 新建experiment/precision_validation.py：独立CPU-only float64小图预检；执行原始公式，不引入绝对容差、不跳过bias。记录全参数梯度、前向差、权重身份、环境与源码SHA；输出拒绝覆盖、首个失败停止。
- 新建tests/test_precision_validation.py：27项检查，覆盖阈值边界、非有限值、dtype/shape、None梯度、近零相对误差失败传播、漏关系负例、拒绝覆盖与停止顺序。
- 新建本报告；仅向PROGRESS.md、HANDOVER.md、docs/training_changes_2026-10-07.md追加记录。
- 没有修改hgt_layer.py、model.py、trainer.py、优化器、旧projection_validation.py、DDG、tokenizer、图、标签、fold、历史plan/seal/checkpoint。PROMPTS.md未改。

本轮没有替代方案的实施或新的阈值批准。故障注入只作用于隔离诊断图，生产模型不包含故障注入。

## 3. 严格公式与正式预检

前向：maxabs(new-old) <= 1e-12。
梯度：maxabs(new-old) / max(maxabs(old), 1e-30) <= 1e-10。
分母按文档的参考梯度old计算，不使用上一轮的双边尺度，不添加atol。
三轮轨迹1e-9门槛未修改，但本轮未进入该阶段。

小图固定seed114、CPU threads2、8维/2head、dropout=0；先构造float32权重再.double()，两份模型state_dict完全相同，特征float64。包括共享投影的多canonical、同关系名不同类型端点、空关系、纯源/纯目标类型；执行edge_softmax、v_dot_u、u_mul_e/sum与multi_update_all。无optimizer、无训练epoch。

| 正式mean/use_norm=True预检项目 | 数值 |
|---|---:|
| 各节点类型前向最大绝对差 | 0，torch.equal全部为true |
| 全参数最大梯度绝对差 | 1.5265566588595902e-16 |
| 唯一未通过的参数 | k_linears.0.bias |
| 该参数maxabs(Δg) | 2.7647155398380363e-18 |
| 该参数maxabs(g_original) | 2.076247160309741e-17 |
| 该参数maxabs(g_shared) | 1.7997756063259374e-17 |
| 严格相对差 | 0.13315926892950392 |
| 规定上限 | 1e-10 |
| 状态 | failed_static_gate |

独立小图单元测试还检查mean/no-norm和nonempty_mean近零bias被拒绝的真实行为；这不表示剩余真实图任务通过。主预检没有在失败后进入下一验收阶段。

## 4. 为什么不能据此判定模型实现错误

对同一canonical、目标节点和attention head，key线性层的bias经过关系矩阵后，对该目标所有入边的attention logit增加同一个常量。softmax满足softmax(z+c)=softmax(z)，因此这个bias的精确梯度为零。浮点相消留下约1e-17的残差；两份残差只差约1e-18，相除仍可得到0.13。double减小绝对误差，却不能保证相对于“应为零的数值残差”的比值趋于零。

模板中“任何float64门槛失败就说明不是舍入、而是实现问题”的推断过强。同样，小图前向一致和很小的绝对梯度差不足以证明全部真实图、训练轨迹或GPU行为正确。

本轮仍按原阈值判为失败，没有排除近零参数、没有因负例检出而宣布全部等价、没有把上一轮四组float32轨迹重新判为通过。

## 5. 人为漏关系负例与诊断测试修复

只在一次性诊断图的multi_update_all之前将指定canonical的v消息乘0。节点、关系列表和聚合槽位不变，模拟遗漏该关系消息贡献；退出作用域后恢复，原模型源码与初始权重不改。

| reducer | 最大前向差 | 未通过的非bias梯度张量数 |
|---|---:|---:|
| mean | 0.06951759444847261 | 9 |
| nonempty_mean | 0.10319109526590353 | 9 |

两组均同时被前向和梯度门槛拒绝，证明可检出这一指定的逻辑缺陷，不能据此推断能检测所有错误。

最初故障注入直接移除multi_update_all中的关系，造成nonempty_mean的stack槽位与mask不一致；首次新测试23 passed、1 failed，日志保留。修正仅限诊断注入：保留槽位并抑制消息。关键断言未改、未删、未xfail，最终27 passed。第一次正式小图失败也保留；最终工具另建small_preflight_final记录相同严格失败，不覆盖历史。

## 6. 后续真实图接入约束（本轮未实施）

只读复核发现，未来float64诊断需要显式处理以下问题，不能关闭原校验：

1. 冻结图token为NumPy float32数组；model.double()不会转换DGL inp。model.py和原model_validation.py仍检查它与冻结token的dtype和值完全一致。
2. 原节点/合约forward的hiddens使用未指定dtype的torch.zeros，诊断须保证中间dtype一致，退出后恢复环境。
3. trainer校验初值tensor digest；转换后的float64 digest不能冒用原float32初值，须同时保留冻结源身份与诊断转换身份。
4. 文档提到的experiment/equivalence.py当前只允许重入合约；访问控制节点已有历史核对入口是projection_validation.py::run_gpu_diagnostic。

本轮未改这些接口，未转换真实图token，未生成新的float64训练初值。后续适配需要先确认，不能弱化生产输入绑定。

## 7. 测试、身份与未执行项目

- 新测试：27 passed，4条既有DGL/distutils弃用警告，5.60s。
- 全v2：1393 passed，8条既有DGL/NetworkX弃用警告，93.01s。
- 旧DDG/graph_utils：223 passed，29条既有弃用警告，3.42s。
- 11251个旧跟踪文件（三份可追加文档除外）SHA一致；上一轮prompt7b_v1的164文件SHA一致；三份文档旧正文仅追加。
- graphs_v2_r1/store.json SHA仍为ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。本轮没有重构图或重跑全图验收，摘要检查不等于新的图语义证明。
- 新增optimizer fit=0、真实图float64案例=0、GPU运行=0、pilot完成=0/8。没有新显存峰值、GPU噪声值、训练耗时估计或F1比较。
- P7b旧失败未覆盖/重新改为通过；P7旧失败attempt未重试。本轮不启动Prompt8，不自动push。

## 8. 命令和产物

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

# 原首轮命令；目录已存在，复跑需指定新的空目录。
# 预期退出码1代表严格验收失败，不是训练成功。
python -u -B -m scripts.DFG.dfg_v2.experiment.precision_validation --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b1_v1/small_preflight

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_precision_validation.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

产物：scripts/DFG/experiments/artifacts/dfg_v2/prompt7b1_v1/。
包含small_preflight及small_preflight_final、fault_injection.json、small_probe初次失败和最终测试日志/XML、v2/legacy日志/XML、冻结文件及旧产物摘要、final_acceptance.json。
最终主预检acceptance SHA：dd10f2c786164961110ec27ac17751ae6223257d982991ef963868a2b1a22e1b。
故障注入证据SHA：7b9f97b6c76e75ed5ed9af85cf719e3666f917c0585f3d75deb930d33e1126b0。
运行产物保存在现有WSL工作树，未转存C盘。

## 9. 尚待用户决定的建议

建议事先固定float64混合绝对/相对误差规则，例如maxabs(Δg)<=1e-12+1e-10×maxabs(g_original)，保留全部参数原始纯相对误差和漏关系负例。**仅为建议，本轮未采用。** 再为真实图设计隔离、可审计的dtype转换，不改生产特征、模型或训练算法。确认后仍需完成六组真实图与GPU对照，才能决定是否推进8次pilot。

停止状态：strict_float64_small_gate_failed_tests_passed；不能称Prompt 7b.1全部完成。
