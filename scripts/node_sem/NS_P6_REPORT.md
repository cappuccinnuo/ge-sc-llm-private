# NS-P6：N-B 计划与封存验收报告

修改 AI：Codex。输入版本：node-sem@a4145f3017471054ed6d0e1bbe4a4249a17c02b2，PROMPTS r19。本报告记录准备阶段；正式训练为 **0 次**，尚无 N-B F1 或收益结论。

## 1. 已完成与停止位置

已完成 120/120 份独立零步初值、16/16 组载体、16/16 组 fresh-vs-reused 未训练结构逐参数一致证明，以及16/16组封存载体快路径与原装配的输入/参数一致证明。CPU严格重载、文件SHA和tensor digest、schema、train支持、划分与标签绑定通过。准备耗时 41.01 分钟，CUDA未初始化。

N-A 的240个正式收据及所引用产物已逐一只读核验；报告产物引用也核验SHA。N-A图、特征、标签、折、配置、设备/TF32身份与新任务对应项相同。8H仍仅提供已批准的零步锚点及协议来源，匿名8H成绩不充当本批原名基线。

本批目录为 `scripts/node_sem/artifacts/batch_NB_v1/`，排他创建。plan SHA256：`df62bc0ab3e1ce6719d0739005edc54a7b629bc693057df82dbae9db6a993c0a`；seal SHA256：`955d13d4803e4740b5f5eab4efc62abbf32a2ae0d44510ad2036667a7c83ce7a`。授权模板为false，没有正式authorization或execution_revision，没有训练、GPU评估、重试或新模型下载。

PROMPTS §5.9明确要求：“先计划与封存……停下等用户授权，再执行与报告”。本轮到此门槛停止，未进入NS-P7。

## 2. 固定实验矩阵

| 配置 | 输入与融合 | 图与层数 | 新fit数 |
|---|---|---|---:|
| S3 | 原名CODE256 + 原名CTX256，concat | G3R，原2层 | 30 |
| S4g | 原名CODE256 + 原名CTX256 + STATIC245，gated | G3R，原2层 | 30 |
| S4m | 原名CODE256 + masked CTX256 + STATIC245，concat | G3R，原2层 | 30 |
| S4-noG | 原名CODE256 + 原名CTX256 + STATIC245，concat | G0，显式0层 | 30 |

四个任务分别是重入/访问控制的合约5折、节点10折，总计120。S3载体514维，其他760维，包含2或3个模态存在位。STATIC采用NS-P3b2已验收的245维，不回退到早期243维。所有特征来自封存的ns_p3/CURRENT快照，不重新编码。

主视图为original。S4m只更换CTX，CODE保留原名，不能称为完整匿名实验。S4-noG关闭HGT消息传递，但CTX/STATIC仍含DFG派生事实，不能称完全无依赖信息。零层覆盖通过spec.layers=0明确表达；job.config原值仍与N-A完全相同，没有把所有任务统一改超参。

逐组参数量与实际层数：

| task | graph | config | carrier dim | layers | parameters |
|---|---|---|---:|---:|---:|
| access_control_contract | G0 | S4-noG | 760 | 0 | 1569026 |
| access_control_contract | G3R | S3 | 514 | 2 | 5317204 |
| access_control_contract | G3R | S4g | 760 | 2 | 5869959 |
| access_control_contract | G3R | S4m | 760 | 2 | 5850324 |
| access_control_node | G0 | S4-noG | 760 | 0 | 1569026 |
| access_control_node | G3R | S3 | 514 | 2 | 5235124 |
| access_control_node | G3R | S4g | 760 | 2 | 5787879 |
| access_control_node | G3R | S4m | 760 | 2 | 5768244 |
| reentrancy_contract | G0 | S4-noG | 760 | 0 | 1569026 |
| reentrancy_contract | G3R | S3 | 514 | 2 | 5300788 |
| reentrancy_contract | G3R | S4g | 760 | 2 | 5853543 |
| reentrancy_contract | G3R | S4m | 760 | 2 | 5833908 |
| reentrancy_node | G0 | S4-noG | 760 | 0 | 1569026 |
| reentrancy_node | G3R | S3 | 514 | 2 | 5128420 |
| reentrancy_node | G3R | S4g | 760 | 2 | 5681175 |
| reentrancy_node | G3R | S4m | 760 | 2 | 5661540 |


## 3. 最小接入与用户批准的处理

新增batch_nb.py、nb_history.py、p6_prepare.py、batch_nb_worker.py、batch_nb_controller.py及tests/test_batch_nb.py。计划绑定374个运行源码摘要并保存源码副本；输入HEAD与实际逐文件摘要分别记录。

1. 原N-A白名单及授权契约只支持240项，无法原样调用N-B。用户同意新增独立N-B调度适配，直接复用N-A的construct、run_core、formal_config和收据核验，不修改N-A代码、计划或产物，不重写优化器/fit/早停算法。测试确认训练核心是同一个函数对象。
2. S3−S2在模板中重复出现在预登记和事后清单。用户同意按历史来源处理：整体对照保留原身份；r19新增的分层/逐节点解释标为事后描述，一次计算、明确归类，不做显著性检验。

原始回复和英文决策记录在ns_p6_checks/decisions_verbatim.json、decisions.json。沿用先前已批准的“证明逐位一致后复用未训练结构”；每折仍单独生成、封存和严格重载初值，无已训练权重参与。

HGT/分类器共有参数精确来自相应8H零步锚点；S4-noG只保留分类器共有参数。新增adapter参数沿用nodesem-semantic-initialization-v2，其语义种子包含完整spec身份，因此不同配置的新参数并非逐位相同。参数量、融合和优化轨迹也变化，不能把分差全部归因于纯依赖语义。

## 4. 训练和报告约束

沿用当前N-A的dfg-v2-grouped-nested协议，固定文件分组折、L-audit、seed1、完整固定任务图前向。inner_train监督，inner_val选best并早停，outer_test仅训练结束后评分。最大50轮、patience7、delta0.001、Adam/OneCycle与各任务实际配置原样绑定；best/last分开，原标签只作辅助分层。

顺序为重入节点40项优先，再重入合约20、访问控制合约20、访问控制节点40。每fit独立进程、单GPU串行、原GPU锁；成功收据核验后复用。外部中断最多重跑一次必须在新授权中明确同意，OOM/数值/输入/checkpoint错误停止，不自动降配或换CPU。

统计计划已封存：S4−S3、S3−S2、S4g−S4、S4−S4-noG（同时报告G0 S4对照）、S4−S4m；r19新增对照及分层明确标为事后。均只作描述，不做Holm或显著性判断。逐折/均值样本标准差、pooled OOF、best/last、来源分层和非SolidiFI32/20个正例概率分别报告，按节点/文件身份对齐。

S4g门控只统计有可用模态的行；S2没有可学习门控，不能伪造它的“CODE门控权重”。本轮只封存这些报告要求，N-B专用汇总、门控/注意力提取仍需在执行阶段接入并绑定。控制器即使120个fit齐备，也只标记complete_training_pending_NB_report；这不是完整报告交付。

## 5. 验证

| CPU套件 | 通过 | 失败 | 跳过 | 警告 |
|---|---:|---:|---:|---:|
| NodeSem（含42项N-B定向测试） | 925 | 0 | 0 | 4 |
| DFG v2 | 2653 | 0 | 0 | 9 |
| 原DDG与graph_utils | 223 | 0 | 0 | 29 |
| 合计 | 3801 | 0 | 0 | 42 |

警告均为现有DGL/distutils、NetworkX gpickle弃用提示。中间与定向复跑保留日志，不重复累计。测试覆盖矩阵/优先顺序、masked仅CTX、0层、初值来源、跨批图/标签/折/配置/设备错配拒绝、授权拒绝、历史入口不接受新计划，以及冻结训练核心复用。

8H load及已批准runtime_resume_v2只读核验通过；354个DFG/作者冻结源码未变。N-B的374个运行源码与归档逐一相同。三份记录文档只追加，旧前缀SHA保留；UTF-8/中文检查在提交前执行。

## 6. 资源与未执行事项

从N-A同任务同图S4的实际总耗时推算，120次fit的0.8–1.5倍情景范围为4.93–9.25小时，不是置信区间或保证时间；不含准备及训练后诊断。早停和Windows GPU争用会改变耗时。历史N-A整卡最小空闲34MiB；local_dev_v1运行低显存只提醒，OOM仍停止。开训前必须重新检查电源/睡眠和显存，旧检查不复用为本次启动事实。

本批准备产物约2.43GiB，其中PT/NPZ约2.29GiB，保存在WSL；Git仅归档代码和审查元数据，不上传权重/载体。最终实验按用户安排在显存充足服务器开展；当前RTX3050 4GiB仅本机开发限制，服务器尚未实测。服务器另建批次，不把两种设备结果混合或择优替换。

未执行：120次正式fit、checkpoint训练后验收、N-B评分/门控/注意力汇总、服务器运行、NS-P7。没有新的训练结果可用于判断哪种配置最好。

## 7. 实际命令

在README所列mando/WSL环境中：

```bash
CUDA_VISIBLE_DEVICES='' python -B -u -m scripts.node_sem.p6_prepare prepare --decisions scripts/node_sem/artifacts/ns_p6_checks/decisions.json
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

prepare末尾已执行独立的load(deep=True)，逐一重验全部120项。后续只读复查可运行：

```bash
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6_prepare verify --out scripts/node_sem/artifacts/batch_NB_v1
```

详细日志、决策原文、测试记录和只读冻结检查在ns_p6_checks/；执行入口和独立授权流程见NS_P6_README.md。本次仅本地提交，不自动push。
