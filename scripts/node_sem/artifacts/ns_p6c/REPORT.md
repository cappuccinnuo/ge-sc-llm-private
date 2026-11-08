# NS-P6c：模态贡献与冗余诊断（Codex）

门控机制在工作，门控权重与投影范数的乘积已逐模型核验。同时去掉CTX和STATIC时，四任务共改变476个外层预测，其中非SolidiFI正例节点改变9个；是否使用这些输入应看各任务干预敏感性，不能只看门控权重。STATIC与CODE/CTX的可线性预测程度、非SolidiFI额外信号见下表；这些是条件性描述证据，不是语义因果证明。 STATIC位的折均AUC≥0.95数/可估位数为重入合约: code 92/118, ctx 107/118；访问控制合约: code 84/119, ctx 99/119；重入节点: code 89/115, ctx 103/115；访问控制节点: code 75/111, ctx 87/111。非SolidiFI的CODE+STATIC相对CODE平均BF1差为重入节点: 2.1818pp (10/10可估折)；访问控制节点: -0.3968pp (9/10可估折)；不能用少量可估折证明稳定增益。

本轮新增HGT训练0、参数更新0；30个N-B S4g best模型，各4次eval，共120次。S4属于N-A，其30份best已由用户删除，本轮未执行、未替代、未重训。逻辑回归属于文档明确要求的CPU诊断探针，实际拟合27708次系数，不计入HGT正式实验次数。

## 1. 来源、协议与已批准调整

依据PROMPTS.md r20 §5.1/§5.9c与c6310b6d。原名original、冻结L-audit、8D文件分组嵌套折，合约5折/节点10折，inner_train拟合探针，inner_val选C/阈值，outer_test只评分。旧N-A/N-B图、标签、折、特征、计划、收据及批次报告均不修改；报告为事后机制诊断。

用户批准三项澄清：只评估可用S4g，S4缺失单列；保留<0.1%分类变化且非SolidiFI正例不变的判据，结论收紧为未观察到明显分类敏感性；C解释为L2强度倒数，空/单类别划分不借用测试集补齐。原回复在decisions.json。当前输出排他创建，不覆盖旧批次。

N-A480个正式best/last的缺失原因已根据用户提供的文档更正为用户主动删除；具体删除时间未提供。封存预测、收据、指标和删除前注意力诊断仍保留；当前无法重载N-A，服务器批次需重新训练。旧historical_weight_availability.json未改，新说明见na_checkpoint_note.json。

## 2. 门控与有效贡献

下表先按每个任务/折/模型计算，再等权平均折。g为有该模态节点的门控均值；share为g×L2(P(normalized x))除以三模态此量之和的节点均值。没有纳入共享bias；零分母单列，不把范数份额解释为最终logit贡献，向量方向与抵消、GELU/HGT会继续影响输出。逐节点类型的完整分布、可用数量和分位数见contributions_by_type.json。

|任务|模态|g折均|有效范数折均|范数份额折均|
|---|---|---:|---:|---:|
|访问控制合约|code|0.4820|7.6052|0.5327|
|访问控制合约|ctx|0.2487|4.5452|0.2832|
|访问控制合约|static|0.2693|0.9421|0.1841|
|访问控制节点|code|0.3570|6.9627|0.3693|
|访问控制节点|ctx|0.4413|9.1019|0.4711|
|访问控制节点|static|0.2017|0.8167|0.1596|
|重入合约|code|0.4505|10.6105|0.4663|
|重入合约|ctx|0.3640|9.7396|0.3810|
|重入合约|static|0.1855|0.9396|0.1527|
|重入节点|code|0.4954|8.7748|0.5088|
|重入节点|ctx|0.3771|7.2181|0.3896|
|重入节点|static|0.1275|0.4653|0.1016|

## 3. 推理时移除

仅在内存DGL local_scope中把存在位置零，向量本身不改；门控按实际缺失重新计算。与训练modality dropout的缺失处理等价测试通过；模型为eval，无反向，无优化器。full预测与各封存best导出逐身份核对，最大概率误差为0.000000000；30个参数摘要前后相同。

|任务|条件|BF1折均 %|分类改变/评分数|非SolidiFI正例改变|概率MAE折均|
|---|---|---:|---:|---:|---:|
|访问控制合约|code_only|85.7096|13/114|5|0.123345|
|访问控制合约|full|90.2767|0/114|0|0.000000|
|访问控制合约|no_ctx|87.8954|8/114|5|0.083312|
|访问控制合约|no_static|91.2187|3/114|1|0.047906|
|访问控制节点|code_only|97.5178|130/7289|3|0.023752|
|访问控制节点|full|99.5715|0/7289|0|0.000000|
|访问控制节点|no_ctx|99.3493|20/7289|1|0.004727|
|访问控制节点|no_static|99.5543|5/7289|3|0.001421|
|重入合约|code_only|89.3319|10/142|6|0.094019|
|重入合约|full|97.1903|0/142|0|0.000000|
|重入合约|no_ctx|93.6292|6/142|2|0.059798|
|重入合约|no_static|95.3519|5/142|1|0.028907|
|重入节点|code_only|97.5653|323/11806|6|0.032991|
|重入节点|full|99.7663|0/11806|0|0.000000|
|重入节点|no_ctx|99.1251|115/11806|4|0.011751|
|重入节点|no_static|99.7155|10/11806|3|0.001865|

逐折指标及改变比例见removal_folds.csv。nonSolidifi_changes.json保留全部重入32、访问控制20个正例，及任一条件下出现的非SolidiFI误报，包含文件、source SHA、节点身份及四种概率。这里的数量为HCG节点或合约文件，不是独立漏洞个数。

移除干预改变了训练后模型的输入条件，不等于重训后的组件消融。分类不变仍可能有概率变化或冗余补偿；分类变化也不单独证明该模态提供了额外、正确的漏洞语义；存在位置零还会重归一其余模态的门控权重，因此测量包含模态内容移除与融合比例变化的联合效应。原<0.1%规则按每个模型记录，不据此修改配置。

## 4. STATIC冗余探针

每任务STATIC可用行中取1比例在[1%,99%]的位；这是文档指定的全任务无漏洞标签筛选，属于传导式特征审计，不冒充纯归纳特征选择。标准化只在inner_train拟合。liblinear L2逻辑回归，C∈{0.01,0.1,1,10}，tol=1e-4、max_iter=1000、seed=1；按inner_val AUC选C，平局取较小C。不把inner_val并回训练；测试BA阈值0.5。单类别train/val不可估，单类别test的AUC/BA为null。所有位的逐折结果在本地probes目录，Git以SHA索引与生成命令归档。

|任务|输入|符合比例的位|至少一折可估|折均AUC≥0.95位|占可估位比例|所有折可估位|
|---|---|---:|---:|---:|---:|---:|
|访问控制合约|code|119|119|84|0.7059|119|
|访问控制合约|ctx|119|119|99|0.8319|119|
|访问控制节点|code|111|111|75|0.6757|97|
|访问控制节点|ctx|111|111|87|0.7838|97|
|重入合约|code|118|118|92|0.7797|117|
|重入合约|ctx|118|118|107|0.9068|117|
|重入节点|code|115|115|89|0.7739|110|
|重入节点|ctx|115|115|103|0.8957|110|

各A–N父组见redundancy_groups.csv；A1/D3等原子组在redundancy_bits.json保留。高AUC按该位可估折的等权均值判断，同时披露可估折数；不是把重复节点当独立样本。状态计数：{"ok": 6800, "outer_test_single_class_auc_undefined": 70, "not_estimable_inner_val_single_or_empty": 20}。
高可预测性支持表示冗余解释，但不证明目标漏洞信号已被模型有效利用；低线性可预测性也不能证明没有非线性冗余。

## 5. 非SolidiFI信号探针

仅两个节点任务的L-audit包含行，CODE/STATIC共有可用节点，固定文件折。C仍按inner_val AUC选择；BF1阈值在inner_val最大化，平局距0.5最近、再取更小阈值。空/单类别折不从outer_test借样本或调参。详细逐折AUC/BF1、阳性数、状态、阈值、C和预测在signal_results.json。

|任务|输入|有BF1折数/10|BF1折均 %|有AUC折数/10|AUC折均|
|---|---|---:|---:|---:|---:|
|重入节点|code|10/10|87.0563|10/10|0.9338|
|重入节点|static|10/10|89.2381|10/10|0.9727|
|重入节点|code_static|10/10|89.2381|10/10|0.9730|
|访问控制节点|code|9/10|15.8730|9/10|0.5804|
|访问控制节点|static|9/10|30.1852|9/10|0.7224|
|访问控制节点|code_static|9/10|15.4762|9/10|0.7829|

|任务|CODE+STATIC−CODE BF1平均差pp|有效配对折|AUC平均差|有效配对折|
|---|---:|---:|---:|---:|
|重入节点|2.1818|10/10|0.0392|10/10|
|访问控制节点|-0.3968|9/10|0.2024|9/10|

样本少，某些折没有足够正例，不能把可估子集的均值写成完整10折成功验证。BF1与AUC方向可能不同，不能挑其中更有利者。逐折差见signal_paired.csv，只有描述统计，无显著性检验。

## 6. 代码、验证与不变量

新增p6c_core.py、p6c_run.py、p6c_probes.py、p6c_report.py、p6c_finalize.py、p6c_parallel.py、两个仅报告修订入口和tests/test_p6c.py。冻结NodeSemAdapter、载体装配、模型构造与checkpoint_io直接复用；训练路径和DFG/作者源码零修改。

定向16项包含在NodeSem977项中，不重复计数；DFGv2 2653、原DDG/graph_utils223，合计3853通过、0失败/跳过、42条既有DGL/distutils及NetworkX弃用警告。8H load170项及354份冻结源码与生效修订一致。三份记录及NS_P6_REPORT只追加，旧字节前缀核验。

本次N-B成功best120份逐文件SHA核验并保留；S4g每次加载前核验文件SHA及tensor digest，binding与封存收据相符，full前向复现历史预测，干预前后参数摘要不变。S4未执行为已批准的缺失项；不补跑N-A，不更改旧availability。

## 7. 实际命令与存储

在原mando环境、项目根目录，设置PYTHONDONTWRITEBYTECODE=1、TREE_SITTER_LIB_DIR、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、OPENBLAS_NUM_THREADS=2。CPU命令另设CUDA_VISIBLE_DEVICES=''。

~~~bash
python -B -m scripts.node_sem.p6c_run prepare
python -B -m scripts.node_sem.p6c_run eval --only <plan中的job_id>  # 30个，GPU串行
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_probes --task <task_id>  # 首次串行attempt，现场保留
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_parallel prepare
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_parallel run  # 经用户批准的29折调度修订
python -B -m scripts.node_sem.p6c_finalize_v2
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

以上生成命令拒绝覆盖；重现应指定新的--out，并重新封存而不是写入本批目录。本批未训练新权重、未重编码特征；CPU调度生成了只读特征缓存，缓存和逐行/逐折明细留WSL，用artifact_inventory.json记录路径、大小和SHA。Git只归档代码、计划、封存、收据、报告、紧凑汇总与索引，不改写历史。运行前共享Git目录为809223604字节（771.74 MiB）。

最终实验按用户安排在显存充足服务器开展；本机4GiB仅当前限制，服务器尚需实测并另建批次。不合并设备结果、不自动进入NS-P7、不启动新HGT训练、新seed或新模型。


报告拼装修订（2026-11-08，Codex）：首个报告入口因metrics和预测变化统计都含样本数n而报重复关键字错误。失败发生在写出汇总前，不涉及评估或探针。原入口、原plan/seal与finalization_binding保留；v2报告入口先断言两边n相同，再合并字段，对样本数不一致及意外重叠字段补回归。仅重新执行报告生成，未重跑任何模型或探针。报告修订绑定见reporting_revision.json。


CPU调度修订：用户批准保留首轮现场，复用已完成的访问控制节点fold0，其余29折并行执行。原plan/seal与p6c_core.logistic_probe不变；特征缓存逐位相同，调度入口输出与原函数逐项相同测试通过。旧4个串行CPU进程经明确授权终止，未完成的中间计算不进入结果；表中探针拟合次数仅指进入最终报告的已完成C候选。修订、原进程与文件SHA、日志在cpu_parallel_revision/，不称新seed重复或HGT续训。
