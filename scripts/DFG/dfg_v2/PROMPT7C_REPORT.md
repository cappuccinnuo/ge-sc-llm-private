# Prompt 7c：local_dev_v1 与8次本地pilot验收

日期：2026-10-26（用户时区America/New_York）；实施/审查AI：Codex。
分支dfg-v2；执行起点3aac85f3243abf60b884e023a57c8010c897ccc7。新批次scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1；旧P7系列保持原样。

## 1. 结论与用户选择

8/8独立fit及逐项验收完成，0失败、0重试、0新增随机种子。全部沿用原未训练初值。新计划SHA：363814c88c3dd9e22aa61a9bf6e2f5ee5f59b7dfc7262d6685e671e287aa94e5。
用户本轮明确回复：“暂时不考虑服务器，当前实验只是在本机，就是之前配置”，以及“同意按 local_dev_v1 完成本地 8 次 pilot（推荐）”。对应完整记录在新批次local_policy_approval.json，SHA绑定进新plan；不是把无回复当成授权。
开始时读取的Prompt7c还是服务器迁移版本；同步到3aac85f后第4.9g已经改成本地8次pilot，按新文档和用户回复执行。服务器迁移推迟到第4.9h，没有新增迁移或环境安装功能。
对模板背景说明作事实限定：不同时刻的peak reserved与另一轮context差值相加超过4096MiB，不能证明已发生换出；本轮不改旧文字或伪造证据。possible_memory_spill只是时长启发式，checkpoint写盘、初始化、CPU/磁盘负载等同样可导致变慢。第一轮能跑完也不是后续一定不会OOM的保证。
实施细节：提醒基线固定为前三轮，检查从第4轮开始；resource_policy保留running_minimum_free_mib=100字段，版本明确决定其是硬门槛还是提醒。新计划额外变化的git_head/resource_origin是来源登记，训练计算不变。

## 2. 实际修改

- 新增 experiment/local_dev.py：继承现有资源观察器；只将运行期低空闲判定改为提醒。直接读取冻结trainer原有history.jsonl，每轮seconds及连续epoch身份必须有效。前3轮中位数固定，从第4轮开始严格超过2倍才标possible_memory_spill。少于3轮明确不足以形成基线。
- 修改 experiment/preflight.py：独立注册local_dev_v1；启动≥3000MiB，运行100MiB字段在新版本中为提醒阈值。旧DEFAULT策略和默认行为保持。工厂仅显式新策略时创建LocalResources。
- 修改 experiment/resource_plan.py：新增prompt7c-local-resource-plan-v1来源协议；P7c→P7b4→P7b3逐层只读验证。绑定用户批准JSON、旧plan/seal与8项身份；逐一核验旧initial文件SHA/tensor digest/optimizer_steps=0/fit_seed。仅允许资源编排相关5个运行文件变化。
- 修改 experiment/run.py：新增--resource-policy local_dev_v1及--approval-record；向资源观察器传policy/history，result和receipt绑定提醒标志，验收从原采样与history独立重算。失败任务阻止新进程跳过后继续批次，只能用户确认后显式--retry同一任务，从原未训练初值开始。
- 修改 experiment/precision_gpu.py：audit_pilot_result只在显式传入新策略时切换资源验收。新canonical梯度、heldout支持及checkpoint逐位重载要求不变，默认调用仍保留旧100MiB门槛。
- 新增tests/test_local_dev.py；追加test_resource_plan.py和test_preflight_integration.py。覆盖低显存继续/旧策略停止、基线、OOM保留与批次停止、时长突增、篡改证据拒绝、成功复用、初值/来源不一致拒绝等。
- 本轮未修改hgt_layer.py、model.py、experiment/trainer.py、experiment/resources.py、原sco_models、DDG分析器、图/标签/token/fold或任何训练数值规则。

## 3. 冻结协议与来源

沿用dfg-v2-nested-v1，不是此前paper_kfold。完整固定任务图前向；inner_train监督更新参数，inner_val早停并按严格最低loss保存best，结束后才计算outer_test。外层标签不参与训练或选择，但由于全图特征/拓扑参与前向，不能称完全归纳的未知图测试。节点按原HCG节点计分，env_source不参与监督/池化评分/预测输出。
实际配置从原plan逐项继承：shared_projection、mean聚合、hidden128、2层、8头、dropout0.2、inside_token、seed1/fold0、Adam/OneCycle、每轮一次step、最多50轮、patience7、delta0.001。合约initial/max LR=0.0005/0.01、weight_decay=5e-6；节点=0.0002/0.005、weight_decay=0。没有统一误填学习率，不使用smoke或上次partial best起跑。
新source_plan_comparison.json证明仅git_head, resource_origin, resource_policy, runtime变化；prepared/initial输入引用完全相同。graphs_v2_r1/store.json SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。新计划无重建图、无新随机初始化。运行时源码在封存后保持不变。

## 4. 逐项运行与验收

表内显存单位MiB；epoch按终端1起算，JSON原始为0起算；进程秒含启动、装配、fit和子进程完整验收，不含父进程额外验收。

| 任务/剖面 | best/last轮 | 启动free | peak allocated/reserved | 最低free | 进程秒 |
| --- | --- | --- | --- | --- | --- |
| 重入合约/G0 | 8/15 | 3725 | 1229.7/1484 | 707 | 448.75 |
| 重入合约/G3R | 8/15 | 3538 | 1893.5/2148 | 81 | 415.64 |
| 重入节点/G0 | 17/24 | 3712 | 807.8/1002 | 1189 | 382.70 |
| 重入节点/G3R | 18/25 | 3709 | 1258.0/1494 | 662 | 455.54 |
| 访问控制合约/G0 | 9/16 | 3645 | 919.6/1118 | 976 | 316.81 |
| 访问控制合约/G3R | 9/16 | 3607 | 1401.1/1610 | 478 | 344.87 |
| 访问控制节点/G0 | 13/20 | 3611 | 561.4/640 | 1447 | 210.46 |
| 访问控制节点/G3R | 16/23 | 3601 | 850.4/946 | 1049 | 288.45 |

8次进程耗时相加2863.21s（47.72分钟），不是每轮GPU纯计算时间。全部按原早停结束。
唯一memory_tight=true是重入合约G3R，最低81MiB；所有possible_memory_spill=false。8项均无CUDA OOM、非有限损失、采样错误。上下文前后free变化为1284–1297MiB，仅为阶段观测，不归因为其他程序或证明换出。
逐轮seconds完整保留history.jsonl及resources.epoch_timing；资源guard_seconds和整个子进程walltime分开保留。

| G3R任务 | 训练支持canonical | 仅留出canonical | 非零训练梯度 | best/last重载 |
| --- | --- | --- | --- | --- |
| 重入合约 | 66 | 2 | 全部通过 | 全部逐位一致 |
| 重入节点 | 62 | 4 | 全部通过 | 全部逐位一致 |
| 访问控制合约 | 68 | 4 | 全部通过 | 全部逐位一致 |
| 访问控制节点 | 70 | 2 | 全部通过 | 全部逐位一致 |

四个G0均无新增关系，新增canonical梯度条件不适用。G3R共266个“任务×训练支持canonical”检查全部首轮relation_msg梯度非零，另12个仅留出canonical单列且梯度为0；这些不是去重跨任务关系总数。
8项best/last在inner_val及outer_test重载后logits逐位一致。正式验收重算预测指标、核对file/node身份与固定标签、核查env_source排除、checkpoint SHA/tensor digest/binding、实际config/schema/initial及收据哈希。完整结果pilot_matrix_verification.json，逐项acceptance_*.json。
运行顺序为R合约G3R→AC合约G0/G3R→AC节点G0/G3R→R合约G0→R节点G0/G3R。每项新进程，单GPU串行，执行argv与进程耗时在execution_records.json。没有复用失败权重。

## 5. Prompt8本地时长估算，未执行

按同一seed1的全部矩阵计数：2×(5+10)×5=150次；阶段A G0/G3R=60，阶段B G1R/G2R/G3=90。以下中间剖面只是估计：

| 任务 | G0秒 | G1R估计秒 | G2R估计秒 | G3R秒 | G3估计秒 | 全折小时 |
| --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 448.75 | 428.30 | 420.51 | 415.64 | 432.19 | 2.98 |
| 重入节点 | 382.70 | 429.05 | 446.71 | 455.54 | 419.12 | 5.93 |
| 访问控制合约 | 316.81 | 333.96 | 340.97 | 344.87 | 330.84 | 2.32 |
| 访问控制节点 | 210.46 | 258.12 | 277.62 | 288.45 | 249.45 | 3.57 |

阶段A约5.83小时；阶段B约8.95小时；合计约14.79小时。
公式t(p)=t(G0)+(C(p)−C(G0))/(C(G3R)−C(G0))×(t(G3R)−t(G0))，C为canonical数量。20个C已独立与冻结store对齐。每任务再乘5或10折。
这是一次fold0、固定seed的排期点估计，不是保证或置信区间；早停轮数、边数/稀疏结构、写盘及显存竞争均影响实际时间。重入合约G3R实测总时长低于G0，不表示增强计算更便宜。估计按完整150fit计，未扣除8pilot；后续是否复用须另验身份并授权。资源汇总与每剖面估计在resource_summary.csv/json及prompt8_time_estimate.json。

## 6. 测试与不变量

定向184 passed/4条既有warning；全v2 1792 passed/8条warning（112.49s）；旧DDG+graph_utils 223 passed/29条warning（3.13s）。合计2015通过，0失败/跳过；新增67项包含于1792，不重复相加。warning为DGL distutils及NetworkX gpickle弃用，未升级依赖。开发阶段新增篡改测试有3个fixture setup错误，修复为finally恢复共享合成fixture，未删除或放宽断言；最终上述三组均通过。
实际测试argv/返回码/耗时、日志及JUnit均在新批次。没有重新运行已验收的float64/CPU/GPU数值等价性短实验，也没有额外smoke。
11,277个原跟踪文件按快照核验，仅本轮dfg_v2范围与3文档允许变化；582个历史P7产物SHA保持；三文档旧字节前缀不变。最终invariants.json记录逐项结果。运行产物继续放E盘承载的现有WSL，未删除旧产物或写大型数据到C盘。

## 7. 实际命令

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64

# 已执行：目录存在时plan会拒绝覆盖
python -B -m scripts.DFG.dfg_v2.experiment.run plan --from-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot/plan.json --resource-policy local_dev_v1 --approval-record scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/local_policy_approval.json --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot

# 已执行8次：每次替换为execution_order.json中的一个身份，独立进程串行
python -B -m scripts.DFG.dfg_v2.experiment.run execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot/plan.json --only reentrancy_contract/0/1/G3R

# 现在可运行的只读完整验收
python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/pilot/plan.json

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_local_dev.py scripts/DFG/dfg_v2/tests/test_preflight.py scripts/DFG/dfg_v2/tests/test_precision_gpu.py scripts/DFG/dfg_v2/tests/test_resource_plan.py scripts/DFG/dfg_v2/tests/test_preflight_integration.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

完整调度脚本execute_pilot.py保存在新批次，仅负责子进程串行、成功核验和失败停止；它不是新训练器。已执行的日志用排他创建，不能直接重跑该脚本覆盖；只读verify可重复。summarize_resources.py只读已验收结果生成资源与时长报告。

## 8. 限制与停止位置

仅完成本轮8个fold0 pilot，不报告F1比较结论，不据此认定DFG有效或无效。完整5/10折、额外seed、其他五类、Prompt8、服务器迁移均未运行。时长估计不是启动授权。
最终正式实验将按用户计划放到显存充足的服务器；目前4GiB是本机开发限制。具体服务器型号、依赖兼容性及资源尚未实测，不能把计划当作验收通过。当前按用户最新选择留本机完成pilot，下一阶段仍等用户确认。
后台采样偶发错误的旧行为未扩展：同步check采样失败立即停止，后台瞬时错误写sampling_errors；本轮8项均为0。命令中断后只读核对确认后台已完整跑完，未重启或重复任何fit。
本轮按共享上下文做本地提交，不自动push。无新增研究方案替代：仅执行已获明确批准的资源策略；对模板关于换出的推断作如上证据限定。
