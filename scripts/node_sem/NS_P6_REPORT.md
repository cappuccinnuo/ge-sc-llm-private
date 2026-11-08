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


## 2026-11-05 NS-P6 正式执行与汇报完成（Codex）

本节为准备报告之后的完成记录，原记录保留。用户后续已明确授权训练；本轮“完成汇报”没有新增fit。N-B120/120正式结果验收，按封存收据引用N-A240个历史结果，共360个正式结果、720组best/last指标。另完成90次只读best前向，其中30次提供S4g门控，没有参数更新。

### 1. 协议与配置

主视图original，L-audit标签，8D固定分组折，seed=1。合约5折、节点10折；inner_train更新参数，inner_val早停并以严格最低loss选best，outer_test仅在训练结束评分。这里是完整图传导式grouped outer evaluation，不是早期paper_kfold的同一验证集评分，也不是独立外部测试。节点指标按HCG节点计算。Adam/OneCycle、各任务实际学习率、最多50轮、patience7/delta0.001和默认TF32保持；best为主、last单列。

S2=CODE；S3=CODE+CTX；S4=CODE+CTX+STATIC拼接融合；S4g为门控融合；S4m仅遮蔽CTX名称，CODE原名保留；S4-noG使用G0且0层，但保留DFG派生CTX/STATIC。STATIC为冻结245维。S4-noG不是完全无依赖信息基线。

### 2. best折均Buggy-F1（%，±样本标准差）

|任务|S2|S3|S4|S4g|S4m|S4-noG|
|---|---:|---:|---:|---:|---:|---:|
|重入合约|97.2348 ± 1.5550|97.2414 ± 1.5421|96.5977 ± 2.3579|97.1903 ± 1.5746|96.5517 ± 0.0000|97.2414 ± 1.5421|
|访问控制合约|92.9578 ± 2.4789|92.9578 ± 2.4789|92.2245 ± 3.3468|90.2767 ± 3.5966|91.0606 ± 0.3388|93.5893 ± 2.4525|
|重入节点|99.8265 ± 0.1151|99.8308 ± 0.1441|99.7721 ± 0.1885|99.7663 ± 0.1384|99.8437 ± 0.1010|98.1741 ± 0.6996|
|访问控制节点|99.5595 ± 0.2334|99.5758 ± 0.3270|99.5074 ± 0.3519|99.5715 ± 0.3023|99.5976 ± 0.3168|99.4514 ± 0.5903|

逐折BF1/Macro-F1/Precision/Recall及混淆矩阵见reports/fold_counts.csv；全部G0对照也保留。等权折均与pooled OOF另表，不混用。

### 3. 配对差值：best/last分开

|任务|左减右|best均差pp|升/平/降|last均差pp|
|---|---|---:|---|---:|
|重入合约|G3R/S3−G3R/S2|+0.00659|1/3/1|+0.00000|
|重入合约|G3R/S4−G3R/S3|-0.64368|0/4/1|-2.70754|
|重入合约|G3R/S4g−G3R/S4|+0.59259|1/4/0|+2.70754|
|重入合约|G3R/S4−G3R/S4m|+0.04598|1/3/1|-2.75862|
|重入合约|G3R/S4−G0/S4-noG|-0.64368|0/4/1|-3.49754|
|访问控制合约|G3R/S3−G3R/S2|+0.00000|0/5/0|-0.24845|
|访问控制合约|G3R/S4−G3R/S3|-0.73333|1/2/2|+0.86580|
|访问控制合约|G3R/S4g−G3R/S4|-1.94783|0/3/2|-3.60640|
|访问控制合约|G3R/S4−G3R/S4m|+1.16390|2/2/1|+3.74779|
|访问控制合约|G3R/S4−G0/S4-noG|-1.36480|2/1/2|+0.62394|
|重入节点|G3R/S3−G3R/S2|+0.00428|3/5/2|+0.00639|
|重入节点|G3R/S4−G3R/S3|-0.05866|3/2/5|-0.05801|
|重入节点|G3R/S4g−G3R/S4|-0.00580|3/3/4|+0.05639|
|重入节点|G3R/S4−G3R/S4m|-0.07156|2/2/6|-0.09340|
|重入节点|G3R/S4−G0/S4-noG|+1.59808|10/0/0|+1.57454|
|访问控制节点|G3R/S3−G3R/S2|+0.01637|3/5/2|-0.01389|
|访问控制节点|G3R/S4−G3R/S3|-0.06841|2/4/4|-0.01677|
|访问控制节点|G3R/S4g−G3R/S4|+0.06403|4/3/3|-0.01780|
|访问控制节点|G3R/S4−G3R/S4m|-0.09018|2/5/3|-0.01304|
|访问控制节点|G3R/S4−G0/S4-noG|+0.05601|3/4/3|-0.00153|

N-B全部只作描述，不做显著性检验或Holm。S3−S2整体保留历史登记身份，r19新增分层/逐节点分析为事后，只计算一次。折间SD不是独立seed方差。

### 4. 非SolidiFI节点子集

|任务|配置|TP|FP|FN|pooled BF1 %|
|---|---|---:|---:|---:|---:|
|重入节点|G3R/S2|25|5|7|80.6452|
|重入节点|G3R/S3|24|5|8|78.6885|
|重入节点|G3R/S4|25|7|7|78.1250|
|重入节点|G3R/S4g|24|6|8|77.4194|
|重入节点|G3R/S4m|24|6|8|77.4194|
|重入节点|G0/S4-noG|25|99|7|32.0513|
|访问控制节点|G3R/S2|2|9|18|12.9032|
|访问控制节点|G3R/S3|3|5|17|21.4286|
|访问控制节点|G3R/S4|2|10|18|12.5000|
|访问控制节点|G3R/S4g|1|3|19|8.3333|
|访问控制节点|G3R/S4m|4|4|16|28.5714|
|访问控制节点|G0/S4-noG|2|3|18|16.0000|

固定正例重入32、访问控制20个按task/fold/file/source SHA/node身份对齐，概率见nonSolidifi_positive_nodes.csv；误报也单列。这些是正例节点数，不是独立漏洞数。Wilson仅P/R，BF1只报点估计；L-audit不宣称金标准。

### 5. 门控和注意力

90/90 G3R best只读前向、0 optimizer step、权重摘要前后相同。S4g30个模型按节点类型和模态统计可用行均值、标准差、分位数及权重≥0.9比例；不把缺失行混入均值。S2没有可学习门控，不编造CODE门控值；S4-noG没有注意力，标为不适用。

|任务|CODE平均权重|CTX平均权重|STATIC平均权重|CODE≥0.9占比|
|---|---:|---:|---:|---:|
|重入合约|0.4505|0.3640|0.1855|37.53%|
|访问控制合约|0.4820|0.2487|0.2693|32.87%|
|重入节点|0.4954|0.3771|0.1275|39.33%|
|访问控制节点|0.3570|0.4413|0.2017|24.87%|

以上为可用节点×模型观测加权汇总，同一节点在不同折模型重复出现，不作为独立样本。逐类型分布见gates.csv。注意力沿用已验证的首层观察器，单邻居权重1是结构结果，多邻居目标单列；门控/注意力不等于因果贡献。

### 6. 完整性、恢复与复现限制

N-B120份成功收据与全部产物SHA通过，240个best/last文件当前可验证；训练期checkpoint重载/预测一致性通过。诊断加载前核对best SHA，再核对state digest和binding。原plan/seal、图、特征、标签、折、初值和训练代码不改。

唯一正式失败：访问控制节点S4m fold8 attempt_001的显存采样读数失败（15轮记录，cuda_oom=false），不是OOM、数值错误或指标下降。用户独立授权“从中断启动后面的”，manual_resume_20261105_v1封存授权；attempt_002从同一零步初值重跑，之前115项成功复用，失败现场保留。恢复worker计算主体AST与原worker相同，不称新seed或epoch续训。

本轮额外深验N-A当前checkpoint失败：240个best与240个last均不在原路径，原因未查明。N-A收据、预测、配置、资源及全部非checkpoint产物SHA通过，按NS-P6的receipt SHA历史引用要求独立复算指标；不能声称现在可重载N-A。此前cleanup_NA_cpu_weights_20261105只删除12个非正式CPU权重，其结束记录曾确认正式480个权重仍在，不能据此认定本次缺失由该清理造成。本轮没有删除权重，也不重训补造。首次失败analysis_checks/audit.*保留，historical_weight_availability.json列明全部缺失引用。

### 7. 实现、验证和命令

新增nb_diagnostics.py（冻结观察器与门控）、nb_reporting.py（复用冻结指标和标签对齐）、nb_finalize.py（独立分析封存与串行调度）、tests/test_nb_analysis.py。训练核心和旧验收入口不改；analysis_revision.json单独绑定新分析源码。

CPU回归：NodeSem961、DFGv2 2653、原DDG/graph_utils223，共3837通过，0失败/跳过、42条既有DGL/distutils与NetworkX弃用警告。36项定向包含于961，不重复累计。额外N-A权重审计失败单列，不把所有尝试写成零失败。8H load170项、354冻结源码与生效修订完全一致。

在既有mando环境和共享上下文变量下实际执行（CPU测试带CUDA_VISIBLE_DEVICES=''）：

    python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests/test_nb_analysis.py
    python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
    python -B -m scripts.node_sem.nb_finalize audit
    python -B -m scripts.node_sem.nb_finalize seal
    python -B -m scripts.node_sem.nb_finalize run
    python -B -m scripts.node_sem.nb_diagnostics --root scripts/node_sem/artifacts/batch_NB_v1 --verify

已有seal/report拒绝覆盖，不应重跑audit/seal/build生成命令；verify只读核对已有诊断。PT/NPZ留WSL，不上传权重或写入C盘副本。

### 8. 结论与停止位置

CTX相对CODE当前收益很小且不稳定；加入STATIC后S4四任务best均低于S3，完整拼接没有超越强CODE基线的证据。门控也未一致改善。重入节点S4相对零层版提高1.5981pp、10折均升，说明当前配置需要图消息传递，但不能单独归因为新增DFG边。

S4m两个节点任务微升、两个合约任务下降；CODE仍原名，不能写成全量匿名化更好或排除命名捷径。非SolidiFI访问控制仍大量漏检，总体99%不能遮盖。best/last方向有不一致，按预定best报告，不择优替换。

边界：S2 modality_dropout=0而S3/S4=0.1；新增adapter种子含spec.digest，共同HGT/分类器相同不保证adapter跨配置相同。这是系统配置比较，不是纯语义因果消融。S4−S3仅回答已有CTX时STATIC的条件增量。保留此前inner_val选出的S2参考，不依据本批outer结果重新选型；下一阶段先明确必要机制证据，不机械新增更多配置。

最终实验按用户安排将在显存充足服务器开展，当前RTX3050 4GiB仅本机限制；服务器尚未实测，另建批次且不混合择优。本轮不进入NS-P7、新seed、新关系或服务器训练。


### 9. 正式运行资源

|任务|fit数|拟合小时|进程累计小时|峰值allocated MiB|峰值reserved MiB|整卡最低free MiB|
|---|---:|---:|---:|---:|---:|---:|
|重入合约|20|0.821|1.320|2044.7|2386.0|40.0|
|访问控制合约|20|0.616|0.978|1514.3|1704.0|92.0|
|重入节点|40|1.493|2.116|1360.8|1586.0|318.0|
|访问控制节点|40|1.667|2.117|919.7|1036.0|673.0|

仅统计120成功结果，失败attempt、准备、排队和90次诊断单列；累计进程时间不是自然墙钟训练时长。参数量/epoch逐折见resources.csv，支持与梯度见relation_support_gradients.json。


### 10. 关系训练支持复核

90个G3R模型的已有梯度日志中，按轮次×canonical relation计：134870条有训练支持且非零梯度，6516条没有训练支持，1730条有支持但当轮零梯度。全部梯度数值有限。这些是重复观测计数，不是独立关系/样本数；不把零梯度单项自动当作错误，也不把非零梯度当作有效性的证明。

每折v2训练边（含既有正反关系）范围：重入合约21594–22650、访问控制合约14912–15942、重入节点16858–17664、访问控制节点10722–11586。已注册但无train支持的canonical关系保留；不删折、删边或评分时建参。完整逐折证据见analysis_checks/support_summary.json及reports/relation_support_gradients.json。


### 11. 概率变化与离散错误变化

访问控制合约S3−S2：114个样本的best概率全部改变，但离散预测0改变，所以F1逐折完全相同。重入合约该比较142个概率改变、4个分类改变（纠正2、新增错误2）。这不是重复使用同一预测文件。

重入节点S3−S2：11806个概率改变，12个分类改变（纠正6、新增错误6）；访问控制节点7289个概率改变，13个分类改变（纠正7、新增错误6）。S4−S3的重入节点纠正6、新增错误14；访问控制节点纠正4、新增错误8。高分背景下少量节点就可改变差值方向。完整各文件/source SHA分布和其他比较见prediction_change_summary.csv、file_error_changes.csv和prediction_changes.jsonl。


### 12. 门控结论与首层注意力汇总

S4g没有普遍退化为仅使用CODE：四任务CODE平均门控权重约0.357–0.495，CODE权重≥0.9的观测比例约24.87%–39.33%；CTX和STATIC仍有明显权重。但这没有转化成稳定F1收益，不能把门控数值直接当成有效性证明。

下表仅统计首层、每个canonical relation内入度≥2的目标，给出最大注意力权重≥0.99的“模型×关系×目标×head”观测比例。排除了单邻居必然为1的情况；同一目标可重复出现，不作为独立样本。

|任务|S2|S3|S4|S4g|S4m|
|---|---:|---:|---:|---:|---:|
|重入合约|0.7112%|1.1792%|1.0118%|0.1318%|2.1029%|
|访问控制合约|0.0000%|1.2498%|0.0370%|0.0000%|0.0000%|
|重入节点|2.8237%|6.7904%|5.0665%|0.8527%|7.2014%|
|访问控制节点|6.1971%|19.0375%|22.2237%|7.2277%|33.6008%|

S2/S4使用N-A已封存注意力摘要（逐项SHA核验），没有重载缺失的N-A权重；S3/S4g/S4m来自本轮90次读取。证据见analysis_supplement/attention_summary.json及CSV。注意力饱和比例不是性能/因果指标，不能据此修改当前模型。

另外独立复核360份history/best/last元数据，全部best等于严格最低inner_val loss所在轮，loss有限、last与日志最后一轮一致；selection_audit.json留证。这里是日志复核，不把它说成当前重载了480份缺失N-A模型。


## 2026-11-05 NS-P6c 权重来源更正（修改 AI：Codex）

根据用户提供的 PROMPTS.md r20 §5.9c 中的说明，N-A 的480个正式 best.pt/last.pt 是用户本人为节省空间主动删除的。此前“原因未查明”记录保留为当时检查事实，本条补充后续确认的原因，不追溯修改旧文。删除的具体时刻未提供，不编造时间。N-A的收据、预测和指标仍有SHA绑定，已报告数值不因删除权重而改变；注意力诊断在删除前已完成并封存。当前不能重载N-A模型，服务器批次需重新训练。batch_NB_v1/historical_weight_availability.json保持原样，新说明在artifacts/ns_p6c/na_checkpoint_note.json。
