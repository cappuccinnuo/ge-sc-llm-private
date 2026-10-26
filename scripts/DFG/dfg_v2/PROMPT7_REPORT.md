# Prompt 7：嵌套训练接入与小规模验收报告

日期：2026-10-26（用户时区 America/New_York）。实施、测试和记录：Codex。
分支：dfg-v2；开始 HEAD：44f714c。执行了 git pull --ff-only origin dfg-v2，返回已最新。

**结论：训练接入代码与 CPU 验收通过；Prompt 7 的 GPU 验收未通过，已按显存门槛停止。不能进入 Prompt 8。**
真实 R 合约 fold0 的 G3R 只完成第一轮，整卡最低空闲 12 MiB，低于100 MiB门槛。没有 OOM 报告，没有成功正式 fit，没有重试。全部8个任务均尚无成功收据。

## 1. 先读后写：依赖与最小适配

|原依赖|不兼容点/核验结果|本轮处理|
|---|---|---|
|paper_run.py::fit_variant|paper train/val、CV validation评分、只审计DATA_DEF_USE|复制到experiment/trainer.py，头部记录源SHA；保留Adam/OneCycle/每轮单step/post-update eval/无权CE；切换三部分监督和全部v2关系审计|
|paper_runtime.Supervision|无v2辅助节点约束|复用已完成DfgV2Supervision，保留原HGT前向；env_source不监督、不池化、不输出预测|
|graph_schema_and_support|原reflect_graph，只有train/val|experiment/support.py用v2 materialize，按三个文件分区统计全部canonical|
|gradient_audit|只有DATA_DEF_USE|逐canonical统计四种正向及显式REV_*的msg/att梯度，训练有边与仅保留集有边分开|
|checkpoint.StopMonitor/save/restore/snapshot|通用ddg-controlled-v1适用；paper_checkpoint写死协议不适用|包装通用checkpoint，绑定协议/角色/图/标签/折/初值/schema/profile/reducer；不改原文件|
|model_validation.capture_model_input|env_source和REV_*可确定序列化；不会自行记录reducer|复用，补外部binding，测试特征/标签/字典/掩码/实际边不一致被拒绝|
|stage_f.initialize_pair|要求同节点类型及state_dict键，无法直接处理env_source|新initialize_family按节点名和canonical对齐；保存未经训练初值|
|RECON §5与历史task.json|合约、节点学习率不同|读取各任务已绑定config，不统一覆盖；constructor/fit种子规则保留并明确扩展seed公式|

源训练器文件SHA：babbc0fb0f3c040bcee1282973a01745d183a5fc47ffe650077d51daed20d3e0。
HGT源码、DDG分析器、tokenizer、原训练脚本、图、标签、折、旧plan/seal均不修改。

## 2. 用户明确批准的两处选择

1. 初始化要求存在“所有同名共同参数相等”与“新增行按各剖面整块Xavier范围”冲突。用户批准后者：**与G0共有参数逐张量完全一致**；新增关系使用独立语义随机数，按各自完整关系库的Xavier范围缩放。新增关系在两个增强剖面间可能不逐位相同，不能宣称完全相同。env_source同名参数仍可跨G3/G3R相同。初始化版本为dfg-v2-semantic-family-own-bank-v1，独立于协议版本。
2. 文档“仅8次训练”与CPU两次/GPU一次各3轮等价性检查冲突。用户批准三次短检查单列为数值验收、不计正式实验；先CPU等价性，再G3R显存门槛，再GPU历史对照及其余pilot。**显存门槛失败后停止全部后续GPU运行**。实际只完成两次CPU短检查，GPU历史对照未执行。

完整固定任务图前向会计算保留文件的表示；严格隔离的是监督行/目标/损失及选best。没有跨文件边，outer_test.targets/forward只在训练完成、last保存后调用。没有把全图前向伪称为只前向训练子图。

## 3. 新文件与实现

新增experiment/下：__init__.py、protocol.py、support.py、init.py、checkpoint.py、resources.py、trainer.py、run.py、equivalence.py、README.md。
新增tests/下：test_experiment_protocol.py、test_experiment_init.py、test_experiment_trainer.py、test_experiment_run.py、test_experiment_resources.py。

- run支持plan/execute/verify/select/summarize；仅合成测试API允许CPU，正式CLI固定CUDA。
- plan只读核验store，绑定代码、包版本、图/特征/标签/折、配置及逐任务未训练初值；不重采样。
- 单进程锁与单模型GPU执行；每个job恢复原fit seed。成功收据核验复用；失败保留完整attempt，显式--retry从同一初值重跑整次fit。
- verify检查实际checkpoint payload和sidecar、权重摘要、binding、best/last epoch，预测逐文件/原节点身份与冻结真值核对，再独立重算指标。不能仅检查CSV行数或指标自洽。
- select只读内层预测；summarize必须有封存selection。只有fold0/不完整候选的pilot不可触发补种子，不作F1改善结论。
- GPU显存0.5秒采样并在同步检查点核验；当前采样失败拒绝使用旧读数。资源检查不会降配或切CPU。

## 4. 冻结图、划分和初始化

最终store仍为graphs_v2_r1/store.json，SHA：
ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
cli verify通过4任务、16图、20记录schema；该核验不构造HGT、不前向、不训练。6d.2有界残留和既有范围限制继续保留。

|任务|inner_train/inner_val/outer_test文件数|G0/G3R参数量|G0/G3R canonical数|G3R训练新增关系边数（含REV）|
|---|---|---|---|---:|
|重入合约|90/23/29|4,526,962 / 5,283,380|165 / 233|23,060|
|重入节点|50/13/8|4,371,010 / 5,111,012|146 / 212|16,040|
|访问控制合约|72/19/23|4,510,546 / 5,299,796|163 / 235|15,032|
|访问控制节点|40/11/6|4,428,466 / 5,217,716|153 / 225|12,070|

合约initial_lr/max_lr/div_factor/weight_decay = 0.0005/0.01/20/5e-6；
节点为0.0002/0.005/25/0。共同：OneCycle总50步、final_div_factor=1、cycle_momentum=true、最多50轮、patience7、delta0.001，strict-min inner loss best。完整有效配置在plan与prepared中。

种子：constructor=10000+fold+(合约1000)+100000*(seed-1)，fit=constructor+1000000。当前seed1。每组G0共有语义参数摘要相同，G0不被改写，独立新增参数不依赖家族构造顺序/候选子集。

## 5. 实际测试与数值对照

|检查|结果|
|---|---|
|新增初始化|25 passed|
|新增协议/支持|33 passed|
|新增训练器/checkpoint|37 passed|
|新增runner|14 passed|
|新增资源门槛|4 passed|
|全部v2|1272 passed，8条既有warning，118.64s|
|旧DDG + graph_utils|223 passed，29条既有warning，4.66s|
|总计|1495 passed，0 failed，0 skipped|

警告为已有DGL/distutils和NetworkX gpickle弃用提示。初始化初次fixture遗漏TREE_SITTER_LIB_DIR曾出现invalid ELF设置错误；使用现有已记录库路径后通过，未安装依赖/更换解析器。

合成20文件完成plan→execute（2轮CPU）→verify→select→summarize；包括拒绝select前summarize、成功复用、失败保留/显式重试、payload/标签/身份/输入篡改、三分区mask、辅助节点排除。node/contract小图原/新引擎3轮损失≤1e-6，最终权重逐位相同。

真实R合约fold0 CPU对照使用历史113/29 paper划分，两引擎同初值、同fit seed、50步调度仅运行3轮；**每轮train/val损失最大绝对差=0.0**。这是一项数值检查，不是nested实验结果。历史未训练初值文件SHA 2f5c51836a12499cc0884f15431c5f87240285039ccaf79c33910834414814fe，tensor SHA 43ea285456a411190eaeaa46cf9bc1a03b0e5a0345efcfbf0bcc2228fdd57504。CPU best/last重载logits逐位一致。

## 6. GPU探针及停止原因

独立plan有8个job：四任务fold0，G0/G3R，seed1。唯一启动：
reentrancy_contract/0/1/G3R。

- 完成epoch0（第1轮），history中的轮耗时23.5301秒。
- Resources监控区间56.2470秒，包含GPU搬移/检查点/同步与采样等，不能把它当每轮纯训练耗时。
- peak allocated：3299.8477 MiB；peak reserved：3536 MiB。
- 整卡最低空闲：**12 MiB**；76次采样，采样错误0。
- epoch0后同步检查触发MemoryGateError；未报告CUDA OOM，未自动改模型/图/训练配置。
- 保留partial best.pt/best.json、history、binding、监督清单、资源与failure/started记录。没有last.pt、完整result或成功receipt；不能使用该partial best作为正式成绩。
- 外部只读监控也观察到16 MiB；尝试发送SIGINT前进程已自动退出，未实际发送任何信号/关闭其他程序。随后显存已释放。
- 0/8成功fit，1个失败attempt，0次重试；其余7个未启动，GPU三轮历史对照未启动。
- 每新canonical的GPU第一轮梯度明细在原实现完成fit后写出；本次提前停止未持久化完整梯度审计，不能宣称GPU全部新关系已通过非零梯度验收。CPU小图梯度集成测试已通过。

因此本轮没有8次F1比较结论，也没有依据更新150次主矩阵的可靠耗时估算。

## 7. 待用户决定的资源方案

模板中的选择保留，但不能假定一定有效：
- 关闭不需要的GPU程序后，明确授权从同一初值重试失败fit。Codex不会关闭用户程序。
- allocator的max_split_size_mb选项需先核实该旧PyTorch版本支持。对本地1.8.1的五个CUDA/c10库只读检查，未检出该选项或PYTORCH_CUDA_ALLOC_CONF字符串；这不是完整支持性证明，不能承诺设环境变量就有效。本轮未设置/升级。
- 每job独立进程有助于释放跨job上下文；本探针已经在独立execute进程且只有一个fit，因此它不能单独解决首次探针的固有峰值。
- 更大显存的兼容GPU可保持模型配置；迁移环境仍需另行验收。
- 混合精度、降维、减少层数/删边/采样会改变模型或数值，不属于本轮自动补救。

Prompt 7尚未全部验收；未经用户选择，不重试、不开展Prompt 8。

## 8. 产物与实际命令

O = scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/。
其中before_tracked.json、store_verify.log、plan_acceptance.json、v2_tests/legacy_tests的log/XML、cpu_equivalence/、pilot/、gpu_probe.log、allocator_option_probe.json均保留在WSL。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.cli verify \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py

python -u -B -m scripts.DFG.dfg_v2.experiment.equivalence \
  --manifest scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/reentrancy_author_contract/fold_0/task.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/cpu_equivalence --device cpu

python -B -m scripts.DFG.dfg_v2.experiment.run plan \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node \
  --profiles G0,G3R --seeds 1 --folds 0 \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot

python -u -B -m scripts.DFG.dfg_v2.experiment.run execute \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json \
  --only reentrancy_contract/0/1/G3R
~~~

上述输出已存在，不可覆盖。未经用户决定不加--retry。正式verify会因8个job未完成而拒绝完整验收，这是正确行为；只读verify(require_complete=False)可汇报进度。

只向三份记录文档追加；原11233跟踪文件写文档前SHA均不变，最终核验另存。代码/README/本报告/三文档本地提交；运行原件不加入Git，不自动push。
