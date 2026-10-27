# Prompt 8：完整嵌套实验准备、分阶段执行器与统计

日期2026-10-26（America/New_York），修改AI：Codex。工作树ge-sc-llm-ddg-v11，分支dfg-v2，起点4f537d9cb35952201fc70338a0091b930e782ab8。

## 1. 实际状态

已完成Prompt 8计划、分阶段调度、统计、报告及必要接入。150项CPU准备：已完成并封存（准备2172.81秒，未执行fit）；plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de；seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8；实际初值验收 150/150份通过，30个完整家族，零优化步数、实际tensor摘要、各剖面与G0共同语义参数逐值相等；独立验收20.82秒。
正式训练0/150：阶段A 0/60，阶段B 0/90。本轮批准是准备计划，阶段A仍需用户审阅具体计划、磁盘和排期后确认；阶段B还需A中间报告后的确认。未读取或报告pilot F1作为本轮实验依据。旧run verify为前置完整性验收会内部重算指标，但不将pilot分数用于选型。

## 2. 用户批准的调整

- “同意新增独立批次授权记录（推荐）”：Prompt 7c批准只绑定旧8项pilot。旧批准不改，作为local_dev_v1历史依据；新batch_authorization.json绑定本轮请求、150项及A/B，authorized_scope=prepare_batch1_150_only、execution_authorized=false。不会扩大旧批准的作用范围。
- “同意按实际统计条件报告（推荐）”：合约5折只作描述；0.0625只指通常非零差值精确双侧检验的下限，不适用于所有zsplit近似情形。节点仍双侧Wilcoxon、zsplit，A报告原始p，B四项vs G0齐全后再Holm。

训练、标签、主要终点和G*选择规则均未改变。没有未经批准的新模型设计。

## 3. 修改文件和实现

新增experiment/batch_plan.py、batch.py、stats.py、reporting.py及四个对应test文件；experiment/run.py最小接入新计划/授权/完整汇总，experiment/README.md追加命令。
batch_plan冻结150项、A/B顺序、输入SHA、原fold、实际config、initial、初始化版本、主要终点、统计/敏感性规范及批准；已有目录拒绝覆盖。pilot只提供checkpoint/initial文件大小和既有耗时，不提供选型依据。
batch每项独立子进程，单GPU串行，顺序任务→折→剖面，同折配对相邻。成功结果完整verify后可复用。失败或中断即使只产生preflight/started、没有fit目录，仍锁住批次，不能跳过。新批准绑定失败job和证据SHA后，显式--retry从原未训练初值重跑，非epoch恢复、非新seed。
stats纯函数提供折均值/样本标准差、配对差、Wilcoxon、A12、10000次seed0配对bootstrap及四比较Holm；多seed先平均折，本轮仅seed1。
reporting独立核对file/source SHA/node identity与冻结标签，重算指标及OOF；完整报告独立复算inner选择；输出排他创建并记录SHA。best和last分开，env_source不计分。
集成发现并修复两项接口错误：verify_stage返回job/attempt/result/audit包装，interim仅提取result传reporting；真实调用链测试修复前失败、之后通过。run summarize必须先识别正式批次再进入完整reporting，避免旧pilot摘要分支；同样补真实接口回归。未削弱结果校验。
未改DDG分析器、HGT/hgt_layer、model、trainer、tokenizer、原训练脚本、图/标签/token/fold或训练数学。

## 4. 矩阵、协议与初始化

| 任务 | K | A: G0/G3R | B: G1R/G2R/G3 | 总数 |
| --- | --- | --- | --- | --- |
| reentrancy_contract | 5 | 10 | 15 | 25 |
| reentrancy_node | 10 | 20 | 30 | 50 |
| access_control_contract | 5 | 10 | 15 | 25 |
| access_control_node | 10 | 20 | 30 | 50 |
| 合计 | 30任务折 | 60 | 90 | 150 |

G0=原作者固定HCG；G1R=标量依赖双向；G2R再加状态读写/REV；G3R再加ENV_FLOW/REV及env_source；G3为全部正向关系的方向消融。REV只在模型输入阶段生成。
所有剖面shared_projection、mean、inside_token、seed1。graph store SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。各任务原config逐项继承，不统一误填学习率。Adam/OneCycle、每轮一次step、最多50、patience7、delta0.001保持。
协议dfg-v2-nested-v1：inner_train更新，inner_val早停及严格最低loss选择best，训练结束后评估outer_test；last辅助。完整固定图参与前向，所以不是完全归纳的新图测试；G0也不能直接与旧paper_kfold或original层历史F1对比。
节点按原HCG节点计分，不是源码行去重指标；env_source不进入监督、池化目标和预测。
150份initial全部新生成且optimizer_steps=0，不用pilot、smoke或best/last。沿用已批准语义初始化：与G0共有参数逐值一致；新增关系语义种子一致，但按各profile自己的Xavier范围缩放，同名新增关系跨profile未必数值完全相同。未改此算法。

## 5. 资源、磁盘和停止

A约5.83h，B约8.95h，共14.79h。中间三个剖面按canonical数在P7c G0/G3R耗时之间插值；早停、负载、写盘和稀疏结构导致不确定性，这是排期而非保证。150项全部新fit，不扣8pilot。
磁盘实数：checkpoint 23.42 GiB、初值估计2.93 GiB、总计26.35 GiB，两倍门槛52.70 GiB；准备时WSL内部空闲825.96 GiB。Windows CIM另核验承载盘E实际空闲248.15 GiB，WSL注册路径E:/Smartcontract/Ubuntu-22.04；两种容量口径分开，均通过。生成的初值实际2.73 GiB。逐任务取pilot G0/G3R实际best+last及initial最大字节，乘fit数量；准备前空闲至少是二者总估计2倍。余量用于JSON/日志/预测/临时写盘，不覆盖无限重试。CPU准备记录MemAvailable和5模型序列化权重上界；上界不含图/复制tensor/allocator，不等于RAM实测峰值。
RTX3050 4GiB，local_dev_v1启动free≥3000MiB；运行<100MiB仅memory_tight提醒；后续轮次>前三轮中位数2倍仅possible_memory_spill提示，不证明paging。OOM、非有限值、采样/验收错误仍停止；不自动缩图、降维、改超参、换CPU或关闭程序。
A报告后停止，用户确认才B；不因成绩好坏换折或改规则。失败保留，确认后整fit重试，不自动无限重试。

## 6. 预登记统计与选择

主终点每任务best outer-test Buggy-F1的G3R−G0。A中间REPORT_INTERIM_A.md固定对比G3R/G0，不选G*，报告SHA写批次收据。
完整B后G*只读取inner_val best预测：各任务折均值后四任务等权；候选G1R/G2R/G3R/G3；与最优差<0.1pp按更少canonical、再profile名决定。所选G*−G0内层均值绝对差≥0.2pp仅记录补seed条件，不自动训练。完整报告必须有selection seal且独立复算一致，外层不参与选择。
按任务报告best/last、折均值±样本SD、配对提升/持平/下降、差值95%bootstrap、A12、原始及Holm p。G3R−G3方向消融单列。折共享训练数据，不能当独立seed；不将大量节点当独立试验。
pooled OOF与等权折均值分开，多seed各自列OOF，不复制样本充当额外独立数据。主结果始终不改标签、不删困难文件。
敏感性集合预登记六个category/file/source SHA：R buggy_18、buggy_36、0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol；AC buggy_18、buggy_26、parity_wallet_bug_2。来自targeted_label_review_v1五文件与模板R buggy_36并集。同名文件不跨类别混淆；另列排除结果。若过滤后某fold空，明确完整K折均值不可用，不静默删折。
机制统计按实际消息方向、每个新增canonical，计算含该关系的≤1/≤2边路径终点中纠错/新增错误节点数；REV独立，env可为中间点但不计分。A用固定G3R，完整B用inner选的G*。只描述关联，不证明语义因果；关系参数、聚合和优化轨迹也变化。
review_v1/review_v1b仍空白，精确率写“未完成”。不把空白当正确，不再开启全面标签修改。

## 7. 验证与限制

最终定向175通过（含在v2中）、全部v2 1967通过、旧DDG+graph_utils223通过，合计2190，0失败/跳过；警告依次4/8/29，为既有DGL distutils与NetworkX gpickle弃用。未升级依赖。命令、日志、JUnit、返回码在prompt8_v1/*_final.*。
前置store及P7c完整verify通过。新统计报告只经合成数据与真实调用接口测试，尚无本轮真实训练结果；未新增GPU smoke/等价性训练。
旧11280跟踪文件、817历史产物及三文档前缀最终核验：通过（原文件只允许run.py、experiment/README.md与三份记录文档改变；817个历史产物SHA及三文档原字节前缀不变），结果保存invariants.json。新产物在E盘承载WSL，未删旧文件、未向C盘写大模型。
最终实验按用户计划在显存充足服务器进行；4GiB是本机开发限制。尚未服务器部署/验收；迁移整批重新绑定/训练，不混本机成绩。
未执行A/B正式训练、聚合诊断、补seed、其他五类、服务器迁移、Prompt9。测试通过不代表DDG增益、完整Solidity语义或泛化已证明。

## 8. 命令与后续

完整准备命令见experiment/README.md；包含旧资源批准ref、新batch_authorization、report_spec及全150矩阵，输出prompt8_v1/batch1。现有目录拒绝覆盖。
阶段A命令（未执行，需实际新批准）：
~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A --authorization-record <APPROVED_STAGE_A_JSON>
python -B -m scripts.DFG.dfg_v2.experiment.batch verify --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
python -B -m scripts.DFG.dfg_v2.experiment.batch interim --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
~~~
B完成后才run verify→run select→run summarize。当前完整run verify应报告训练矩阵未完成，不修改验收以伪造通过。
其他五类未来按EXTENDING.md：注册类别→锚点/token核验→封存fold→cli build→run plan(G0与R/AC内层选定G*)。不在新类别重新择优；当前不执行。
本轮停止于代码验收、真实计划准备及排期交付，等A确认；本地commit，不自动push。


实际配置补充：hidden=128、layers=2、heads=8、512维inside_token输入保持；合约initial/max LR=0.0005/0.01、weight_decay=5e-6；节点initial/max LR=0.0002/0.005、weight_decay=0。新计划只继承逐任务配置，不统一覆盖学习率。
全部150份初值、30份家族绑定和关系train/inner_val/outer_test支持量已验收/导出：prepared_acceptance.json与prepared_relation_support.csv。本轮未执行新的反向传播、正式梯度审计、best/last checkpoint重载或实际外层F1；这些须每个真实fit完成后再验收。
计划以起点HEAD加runtime逐文件SHA绑定本轮计算，随后仅追加文档并本地提交；提交哈希变化不等于计算文件变化，最终再次核对runtime。150份initial与plan/seal等运行产物留WSL，不把模型大文件自动加入Git。
