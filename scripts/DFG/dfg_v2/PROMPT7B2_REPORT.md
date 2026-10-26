# Prompt 7b.2：数值诊断实现、静态验收与 CPU 内存停止记录

日期：2026-10-26。实施、复核与记录 AI：Codex。基线 a2957d6，分支 dfg-v2。
本轮先读更新 §4.1/P7b.2，git pull --ff-only 确认最新。

**状态：代码与回归通过；6/6 真实静态数值检查通过；1/6 三轮轨迹对通过，第二对因 WSL CPU OOM 中断。Prompt 7b.2 整体未验收通过，不进入 GPU/pilot/Prompt 8。**

## 1. 文件、范围及授权来源

仅新增以下实现/测试，未修改任何已有 Python 计算文件：

| 新文件 | 用途/测试 |
|---|---|
| experiment/precision_gate.py | 全局尺度混合容差、双端零梯度核验、小图证据重判 |
| experiment/precision_real.py | 无损 float64 副本、输入身份、静态与隔离三轮循环 |
| experiment/precision_gpu.py | 六 CPU 案例 gate、GPU 噪声与 pilot 附加验收 |
| tests/test_precision_gate.py | 53项，边界/缺失/非有限/近零/非零扰动/负例 |
| tests/test_precision_real.py | 32项，dtype恢复、双身份、监督/图绑定、循环与证据 |
| tests/test_precision_gpu.py | 53项，CPU gate、GPU规则、资源、磁盘checkpoint |

新增本报告；追加 PROGRESS.md、HANDOVER.md、docs/training_changes_2026-10-07.md（§57）。
hgt_layer.py、model.py、trainer.py、model_validation.py、DDG/tokenizer/优化器/图/标签/fold/旧计划均不改。

更新后的用户模板已授权新容差及隔离 float64 循环，运行前已登记 PROGRESS；没有事后改门槛，也没有另行替换实验方案。
审查补齐新验收器的一处缺口：GPU 汇总重新核验 best.pt/last.pt、sidecar 与 model_input 的磁盘 SHA/绑定/epoch，不只相信“重载成功”布尔记录。补了13项合成缺失/篡改测试；不改任何训练数值规则。

## 2. 固定判据与隔离路径

每案例 G=max 所有参考参数梯度的 maxabs；每张量要求：

    maxabs(g_shared - g_original)
        <= 1e-12 * G + 1e-10 * maxabs(g_original)

纯相对差保留但不单独判定。参考端 <=1e-12*G 的张量，候选端也须 <=1e-12*G；不排除 key bias。逐层/全 logits 前向差 <=1e-12，三轮 train/inner_val 损失差 <=1e-9。非有限、缺失或身份不符拒绝。

正常 float32 构造/加载/校验后深拷贝，无损拓宽权重和 DGL inp；记录 float32 原摘要与 float64 诊断摘要。NX token、节点、边、标签、mask/schema/原对象不变。
临时默认 float64 让继承 forward 中未指定 dtype 的 zeros 相容，正常/异常退出均恢复 float32。生产校验仍拒绝不符的 float64 输入。

三轮隔离循环读取任务冻结配置：Adam/OneCycle、50步schedule、patience7/delta.001、固定fit seed；full graph前向，nested inner_train更新、inner_val损失。两个实现共用此循环，所以结论是该循环内等价性；不声称以此逐行证明生产trainer的float64行为。
不访问outer标签，不写生产checkpoint，不报告漏洞F1。

## 3. 小图与六组静态结果

7b.1 小图按新规则重判通过：G=24.020718399476486，绝对项2.4020718399476484e-11。旧strict失败原件保留。
漏一个canonical消息的mean/nonempty负例仍拒绝，前向差约0.06952/0.10319。

六组两层输出及logits均逐位相同，最大绝对差0；梯度全部通过。近零双端不一致0，缺失/未用梯度0。

| 任务/剖面/reducer | 梯度最大绝对差 | 近零张量数 |
|---|---:|---:|
| 重入合约 G0 mean | 5.03141889e-17 | 76 |
| 重入合约 G3R mean | 1.00087635e-16 | 74 |
| 访问控制节点 G0 mean | 1.69510007e-16 | 82 |
| 访问控制节点 G3R mean | 5.55111512e-17 | 81 |
| 重入合约 G0 nonempty_mean | 4.22852820e-16 | 76 |
| 重入合约 G3R nonempty_mean | 1.24699700e-16 | 74 |

所有张量diff/允许门槛最大比例约0.000253323。五个有历史记录案例的图/初值身份相同；R/G3R/nonempty无旧案例。
完整逐参数证据：cpu/static/<case>/static.json。

## 4. 零梯度解释及待完成部分

模板“预期只有key bias”与真实图不符；阈值内不等于数学上恒零。
- key bias：同canonical/目标/头上加共同常数，softmax平移不变。
- 单一不同来源注意力：包括同源多重边，key/query不能改变聚合值。
- G3R最后一层未监督env/source目标：相关目标参数无最终监督路径。
- 初始softmax饱和：是很小的非零梯度，不是恒零。

静态记录逐项列清单及拓扑说明。额外只读前向完成：
- R/G0/mean额外14项：4单来源/平行边不变性，10初始饱和；不同源非胜出权重最高约2.41e-13。
- AC/G0/mean额外22项：4单来源不变性，18饱和，最高约1.20e-27。

共3次完成的no-grad前向（R首次按边、细化为不同源、AC一次），0backward/optimizer，初值前后相同。AC/G3R取证因内存压力主动SIGTERM，保留日志；它不是后来的正式轨迹OOM。
其余4案例额外近零项尚未逐项完成动态解释，保留numerical-zero/待核验，不套用G0饱和结论。OOM后未继续取证。zero_audit/保留脚本、结果与attempt_inventory/resource_stop。

## 5. 三轮轨迹与资源停止

先运行R/G0/mean，再运行R/G3R/mean；第二对失败后另四对未启动。

R/G0/mean原/共享各完成3epoch：
- train差每轮0；
- inner_val差1.11022302e-16、7.77156117e-16、1.55431223e-15；
- 最大1.5543122344752192e-15 <1e-9，通过；
- 循环耗时68.88/26.20秒，不含构造；不是性能基准。

26项身份核验后，仅描述这个完成案例的历史对照：
原float32 vs原float64最大损失差1.4534227625873086e-6；旧float32原/共享差2.9206275939941406e-6；新float64原/共享差1.5543122344752192e-15。
支持此案例的浮点累加解释，但不改写7b旧失败，也不替代剩余CPU/GPU门槛；其余缺失/未完成明确单列。

**R/G3R/mean在original三轮诊断中被内核OOM killer杀死，returncode=-9。**
内核2026-10-26 04:43:42：Out of memory: Killed process ... anon-rss:7595332kB。
WSL可见RAM7865MiB、swap2048MiB；被杀进程匿名驻留约7.24GiB。这是CPU/WSL系统内存不足，不是CUDA OOM，也不是梯度/损失门槛失败。
Windows宿主约16GiB，故障后可用约4.14GiB，不能未经核实就承诺给WSL分配更多物理内存。

未写出original.json，shared未开始；具体完成epoch没有持久化证据，不臆报。SIGKILL不能被Python捕获，partial trajectory.json保留running现场；独立resource_failure.json绑定其SHA、cpu_execution_state与cpu_oom_kernel.log，明确终止，不能解释为仍在后台训练。
未重试、改模型/门槛、切设备、调整WSL或重启服务。短暂WSL service超时随内存释放恢复。

## 6. 未执行事项与后续门槛

新GPU入口要求六组CPU static+trajectory的SHA清单及seal，并重算原始数值/核对源码、输入、初值、配置、分区后才放行。
噪声门槛max(1e-4,3*original重复差)，资源最低100MiB、低于300提醒；pilot仍调用原runner/fit/receipt。真实GPU功能尚未验收，只有合成测试通过。

本轮实际：
- 6静态案例/12次forward-backward，0参数更新；
- 1轨迹对成功（2完整诊断fit/6个完成epoch），1对中断，4对未启动；
- GPU噪声/历史fit=0；显存探针=0；pilot=0/8；无新pilot plan；
- 无“CPU全部通过”seal，没有跳过gate；
- 无正式F1、GPU显存改善或Prompt8总时长结论。

后续需先经用户同意处理WSL内存/交换空间，或另行批准仅诊断路径的内存方案，再用新attempt完成失败与未执行项；不覆盖旧目录，不把重跑称epoch续训。四组零梯度动态解释也待补。不能直接跳到pilot。

## 7. 测试与不变量

| 检查 | 通过 | 失败/跳过 | 警告 |
|---|---:|---:|---:|
| 新测试（已包含在下一行） | 138 | 0/0 | 4 |
| 全部dfg_v2/tests | 1531 | 0/0 | 8 |
| 旧DDG与graph_utils | 223 | 0/0 | 29 |

不重复计数总计1754 passed。已有DGL distutils/NetworkX read_gpickle弃用警告。v2耗时98.89s、旧回归3.22s。测试通过不等于真实训练门槛全通过；中间版本日志保留。

11,254个非三文档旧跟踪文件SHA相同；7b/7b.1共184旧产物相同；固定store34引用SHA相同，覆盖16图/20schema。
store SHA：ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
三文档只追加、旧前缀核验另存；新代码/报告本地commit，不自动push，已有未跟踪产物不提交。

## 8. 实际命令及产物

已执行命令示例；已有输出拒绝覆盖，不可直接重跑同一目录。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
O=scripts/DFG/experiments/artifacts/dfg_v2/prompt7b2_v1
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json
python -u -B -m scripts.DFG.dfg_v2.experiment.precision_real static --plan "$PLAN" --task reentrancy_contract --profile G0 --reducer mean --output "$O/cpu/static/reentrancy_contract_G0_mean"
python -u -B -m scripts.DFG.dfg_v2.experiment.precision_real trajectory --plan "$PLAN" --task reentrancy_contract --profile G0 --reducer mean --static-report "$O/cpu/static/reentrancy_contract_G0_mean/static.json" --output "$O/cpu/trajectory/reentrancy_contract_G0_mean"
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_precision_gate.py scripts/DFG/dfg_v2/tests/test_precision_real.py scripts/DFG/dfg_v2/tests/test_precision_gpu.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

O在现有WSL工作树。static_commands.json、trajectory_commands.json、test_commands.json保存实际argv；trajectory清单六行是计划，实际只启动前两对，不能以清单数充当完成数。
small_rejudgment、cpu/static、cpu/trajectory、resource_failure/kernel/state、float32_float64_comparison、zero_audit、*_tests_final.log/xml、invariants_before_docs及final_acceptance保存本轮证据。
最终状态以resource_failure/final_acceptance补充partial原件，不重写原始文件来伪装成功。
