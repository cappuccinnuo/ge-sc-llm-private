# EP7：执行器、P2 与 G3R 基线

记录日期：2026-11-11。依据：PROMPTS.md r15；起始提交 `2cd3dbf339d8de337f7dd05166968b8a8a20569d`，分支 `edge-sem`。

## 当前完成情况

执行器、G4R-P、P2 登记、CPU 接入验收和训练前封存已完成。三套回归共 **4318 项通过，0 失败、0 跳过**。本报告此版本没有训练成绩：GPU 探针 **0/8**、范数试点 **0/1**、正式 G3R **0/20**。D1–D3 与本轮 GPU/训练授权尚待用户确认，原 plan 内的 execution_authorized=false 保留。

证据目录：`artifacts/ep7_v1/`；登记：`artifacts/protocol_p2/registration.json`。执行命令见 [EP7_README.md](EP7_README.md)。

## 1. 代码与接入

- `model_relations.py`、`placebo.py`、`model.py`：G4R-P 使用构造器种子，在文件和规范关系内保持逐节点度数的随机 E1；独立 add_placebo_edges 只接受非语义安慰剂行，未放宽真实边的证据校验。
- `execution.py`：独立 plan/seal/authorization、构造、绑定、单次 fit、结果核验及串行控制器；训练前加载封存零步初值。成功结果核验后复用；失败保留，不自动重试。
- `checkpoint.py`、`support.py`、`input_guard.py`、`supervision.py`：EdgeSem 注册/关系审计分派；绑定 edge_profile、key_map、F4/attrs 引用、core/实际选列、Api 置换与 P 随机化审计；原配置、输入和身份核验保留。
- `trainer.py`：经用户批准的最小适配副本，标明冻结来源和 SHA。仅替换校验/审计导入；正式 `_fit/fit` 的 AST 与冻结实现相同。
- `pilot.py`：GPU 单轮探针与独立仅训练范数试点；后者只建立 inner_train 监督，不选择 best，不读取 inner_val/outer_test 指标。冻结装配仍核验完整图及标签身份，不把这一完整性检查称为“从未访问任何标签”。
- `runtime.py`：明确绑定 27 个 EdgeSem 运行模块，连同 354 个冻结引用共 381 项。历史只读核验检查封存源码快照，不要求当前 EdgeSem 文件与历史运行版本相同。
- `protocol_p2.py`、`analysis_ep7.py`、`recon/ep7_*.py`：登记、准备、授权接入、逐进程串行调度和完整 20 折后汇总。不会自行授予训练权限。

冻结 DFG、NodeSem、作者代码及历史图/标签/折/产物未修改；旧 plan/seal 未覆盖。

## 2. 已批准的两项调整

用户回复 `call_fa9553b4bee0410b8b1dfa2fcc7c490b`：

1. 冻结 trainer 直接导入旧 checkpoint/gradient_audit，无法用原 fit 兼容 EdgeSem，且不能 monkeypatch。批准在 EdgeSem 保存带来源 SHA 的最小适配副本。小型 CPU 三轮测试逐位比较参数、损失、预测、Adam、OneCycle 状态；通过。
2. 原 fit 必然读取验证损失并评分，无法满足范数试点的禁用指标要求。批准独立 train_only，保留相同初值、inner_train、Adam/OneCycle 和 50 次更新；只记录范数、梯度及资源。正式 20 次仍使用完整 P2 规则。

这两项批准是实现方式确认，不是尚未发出的 D1–D3/GPU 训练授权。原始答复见 `approved_adaptations.json`。

## 3. G4R-P 真实 CPU 闸门

| 任务 | 改变边数 / E1 总数 | 比例 | 无法交换分组 / 总分组 |
|---|---:|---:|---:|
| reentrancy_node | 5834 / 7669 | 76.0725% | 195 / 487 |
| access_control_node | 3487 / 5261 | 66.2802% | 184 / 393 |

两任务 fold0 均通过：与 G4R 的规范关系顺序、各关系边数、参数量与初值逐位相同；逐节点规范度数相同；重复构造相同、换 fold 边集合改变；原 F3 指纹不变；修改边、种子、fold 或审计摘要均被拒绝。无法交换的分组保留并计数，未强行重连。

## 4. P2 与封存

P2 相对各任务 8H 有效配置仅把 patience 从 7 改为 51，maximum_training_epochs/schedule_epochs 仍为 50；完整训练 50 轮，按严格最低 inner_val loss 取 best，相同 loss 保留最早 best。学习率、监督、标签视图、图、折和评分算法不变。

使用 S0 的 8H N-anon-s token 特征；此项须由 D1 确认，不能把 NodeSem 后期的原名主视图选择当作本轮批准。P2 登记保留 H1/H2、两项 Holm 族与必报项；本阶段不作 H1/H2 的完成检验。

CPU 已准备 **26 份独立零步初值**：20 份 G3R 与两任务各 3 份额外 fold0 剖面。总计 **550093510 字节**；每份记录 SHA、tensor digest、task/fold/profile、constructor/fit seed 和 optimizer_steps=0，并严格重载。三个独立计划分别含 20、8、1 项；探针和范数试点复用对应的零步文件，不共享训练后状态。

**与 8H 的初值并不相同。** 本轮按 EP1/共享上下文从同构造器种子的新鲜 G3R 锚模型生成；8H 使用其跨剖面配对初始化。每份记录明确比较结果。因此将来的 8H 对照仅为描述性比较，分数差异不能全部归因于取消早停。

封存后真实 reentrancy_node fold0 的 G3R 与 G4R-A 均再次从各自 plan 构造，初值摘要、监督行数、support 和 checkpoint 绑定通过，未执行前向训练或 GPU。

## 5. 验收结果

| 测试套件 | 通过 | 失败 | 跳过 |
|---|---:|---:|---:|
| EdgeSem | 312 | 0 | 0 |
| NodeSem | 1353 | 0 | 0 |
| DFG v2 | 2653 | 0 | 0 |
| 合计 | 4318 | 0 | 0 |

定向测试覆盖旧/新数值等价、错误绑定/输入拒绝、归档源码变化、授权/决策缺失、成功复用、失败停止、随机化篡改、初始编码器零梯度及更新后非零梯度、训练试点不评分 heldout。归档/环境校验收紧后另复跑 15 项核心/策略测试通过。

只读验收核对 **750 份冻结源码、1134 份既有产物**，DFG _code_refs 清单未变，8H load 仍通过，三份历史文档的原始字节前缀未变。收据：`cpu_acceptance.json`、`sealed_plan_cpu.json`。

开发中两项测试问题已记录：辅助函数 setup 被 pytest 误识别为钩子；向原本为 None 的字段再次赋 None 并未实际篡改。修正测试后通过；未发生正式 fit 失败或重训，记录见 `development_checks.json`。

## 6. 下一执行门槛与边界

待用户确认 D1–D3，并授权：8 个独立 GPU 单轮探针 → 1 个 50 轮 G4R-A 仅训练范数试点 → 20 个 G3R 正式拟合。P2 registration 必须先本地提交，随后新增 decisions/执行授权，不改已封存旧 plan。

GPU 探针记录 peak allocated/reserved 和整卡观察值，以 peak Torch reserved 超过 3584 MiB 为停止条件。OOM、非有限值、输入/checkpoint 错误均停止，不降配、不自动重试。范数试点要求第一次更新后编码器梯度有限且非零；所有最终 u/U 范数均低于 1e-3 时停止。每个训练任务独立进程，沿用原 GPU 锁，单模型串行。

**最终实验将在显存充足的服务器运行；当前显存限制仅来自本机 RTX 3050 4 GiB。** 本轮不自动启动 EP8/EP9、其他漏洞类别或服务器批次。当前没有检测收益结论；本地模型文件不作为普通 Git 结果文件上传。
