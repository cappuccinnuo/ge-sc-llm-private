# Prompt 7b.3：受内存保护的轨迹验收、近零梯度分类与 GPU/pilot 检查

日期：2026-10-26。实施、复核与记录 AI：Codex。基线 `07a0846`，分支 `dfg-v2`。
已先读更新后的 §4.1 和 Prompt 7b.3，并执行 `git pull --ff-only origin dfg-v2` 核验最新版本。

**最终状态：实现与回归通过；更新后的 CPU 放行政策、G0/G3R GPU 数值对照和历史重放均通过。重入合约 G3R 完整训练显存探针在第 1 轮后因整卡空闲仅 66 MiB（要求 ≥100）停止。pilot 完成 0/8，其余 7 项未启动；Prompt 7b.3 尚未整体验收通过，不进入 Prompt 8。**

## 1. 本轮范围及方案依据

本轮按用户更新模板授权的内存策略执行，没有放宽原数值门槛：

- 六组真实图 float64 静态证据全部复用、只读重新核验；不重新做六组前向/反向。
- 复用已通过的 R 合约 G0 mean 三轮轨迹。
- 依次补跑 AC 节点 G0 mean、AC 节点 G3R mean、R 合约 G0 nonempty_mean；每组独立进程，每 2 秒采样 RSS。
- 子进程 RSS 超过 6.5 GiB 时由守护脚本终止该组，记录 `skipped_cpu_memory`，不重试。
- R 合约 G3R mean 保留上轮内核 OOM 失败，另写“本轮不再运行”策略记录；R 合约 G3R nonempty_mean 是未运行的策略跳过，两者不能混为成功或实际 RSS 采样。
- AC/G3R mean 与 R/G0 nonempty_mean 至少一项轨迹完成，且所有实际数值/执行失败都会阻止下一阶段。此次由 AC/G3R mean 满足覆盖条件。

新政策独立命名为 `prompt7b3-cpu-release-v1`，清单与 seal 位于新目录 `prompt7b3_v1/cpu/`。旧六组静态＋六组轨迹政策仍严格保留；旧 Prompt 7、7b、7b.1、7b.2 失败、partial 和 seal 均不改写。

这一调整是更新模板在运行前给出的授权，不是看到本轮结果后改变验收规则。六个有限案例提供数值一致性证据，不能被表述为对任意图、初值、设备、dtype 的普遍数学证明。

## 2. 新增与修改文件

| 文件（均相对 dfg_v2/） | 操作 | 内容 |
|---|---|---|
| experiment/precision_guard.py | 新增 | 三组允许案例的独立子进程、RSS 保护、原始日志、终止和输入绑定 |
| experiment/precision_policy.py | 新增 | 新放行版本、两类策略跳过、旧证据与冻结计划校验 |
| experiment/precision_zero.py | 新增 | 仅按图结构与参数名描述六组近零梯度 |
| tests/test_precision_guard.py | 新增 | 44 项：采样、主动终止、外部失败区分、证据与命令绑定 |
| tests/test_precision_policy.py | 新增 | 48 项：缺失/错误跳过、失败、覆盖不足、输入/源码漂移与旧规则 |
| tests/test_precision_zero.py | 新增 | 38 项：单来源多重边、监督可达性、类别优先级与未证明近零 |
| experiment/precision_gpu.py | 最小修改 | 显式识别新政策 schema；旧无 schema 清单仍走原严格分支 |
| PROMPT7B3_REPORT.md | 新增 | 本报告；记录数值验收通过与 pilot 资源停止 |

hgt_layer.py、model.py、trainer.py、model_validation.py、生产 HGT、DDG、tokenizer、优化器和 scheduler 数值规则、图、标签、fold、旧 checkpoint 均不改。不调整 WSL 内存、swap、系统配置或模型大小。

RSS 保护不把内核杀进程自动认作成功跳过。只有脚本记录了超限样本、对应主动信号和退出码，才能归为资源跳过；`failed_trajectory_gate`、`execution_error` 优先保留为失败。守护进程在子进程运行期间只用标准库，避免额外导入 Torch 占用内存。

## 3. CPU 数值门槛与实际轨迹

静态仍沿用 Prompt 7b.2：前向最大绝对差 ≤1e-12，梯度使用固定全局尺度混合容差，参考和候选近零集合一致。六组旧证据全部重新验证，通过；两层输出和全部 logits 的历史差值仍为 0。三轮 train/inner_val 损失最大绝对差门槛保持 1e-9。

| 任务／剖面／reducer | 本轮行为 | 最大三轮损失差 | 本轮采样峰值 RSS（GiB） | 结论 |
|---|---|---:|---:|---|
| R 合约 G0 mean | 只读复用上轮完成轨迹 | 1.5543122344752192e-15 | 未重新采样 | 通过，非本轮新 fit |
| R 合约 G3R mean | 不重试上轮 OOM | — | 无本轮采样 | 策略跳过；旧 OOM 仍是失败 |
| R 合约 G3R nonempty_mean | 本轮未运行 | — | 无采样 | 策略跳过 |
| AC 节点 G0 mean | 原／共享各 3 轮 | 1.1102230246251565e-16 | 4.105278 | 通过 |
| AC 节点 G3R mean | 原／共享各 3 轮 | 2.5868196473766147e-14 | 5.849632 | 通过 |
| R 合约 G0 nonempty_mean | 启动后主动终止 | 未得到完整对比 | 6.953140 | RSS 保护跳过，未重试 |

R/G0 nonempty_mean 在约 58.07 秒的采样中超过 6.5 GiB，由守护器发送 SIGTERM，返回 -15。2 秒离散采样意味着峰值可以超过阈值后才被检测到；不能把采样阈值描述成绝不会超过的硬内存配额。原部分 `trajectory.json` 保留 running 现场，独立 `guard.json` 记录终止事实，不能将其解释为仍在后台运行。

本轮完成两对 float64 轨迹，即 4 次完整诊断 fit、12 个 epoch；第三对只启动了部分执行，不计作完成 fit。旧 R/G0 mean 的 2 次 fit 只读复用，不重复训练。两项策略跳过不伪造 argv、RSS 样本、损失或成功计数。

CPU 接受清单重新核对六组静态原始数值、文件 SHA、冻结 plan/seal、prepared、图/标签/初值、配置、split、源码摘要及轨迹原始输出。它放行的是更新后的有界诊断政策，并不意味着“六组轨迹全部完成”。

主要证据：
- `cpu/acceptance.json` 与 `acceptance.seal.json`；
- `cpu/guard/<case>/guard.json`、`rss_samples.jsonl`、stdout/stderr、partial 或完成的轨迹；
- `cpu/policy_skips/` 两份明确区分原因的记录；
- 上轮 `prompt7b2_v1/resource_failure.json`、kernel 日志及原成功轨迹原样保留。

## 4. 六组近零梯度的结构描述

仅使用冻结图结构、canonical 关系、训练监督可达路径和参数名，不构造模型，不新增前向、反向或优化器步骤。分类是解释性记录，不影响数值验收门槛。

- a：key bias，softmax 平移不变；
- b：相关目标在该关系上只有一个不同来源，包括同源多重边；
- c：G3R 最后一层中没有训练监督路径的目标参数；
- d：不满足上述结构证明，保留“数值上接近零”，初始注意力饱和仅是可能原因。

| 案例 | a | b | c | d | 合计 |
|---|---:|---:|---:|---:|---:|
| AC 节点 G0 mean | 32 | 32 | 0 | 18 | 82 |
| AC 节点 G3R mean | 34 | 24 | 6 | 17 | 81 |
| R 合约 G0 mean | 32 | 34 | 0 | 10 | 76 |
| R 合约 G0 nonempty_mean | 32 | 34 | 0 | 10 | 76 |
| R 合约 G3R mean | 34 | 28 | 6 | 6 | 74 |
| R 合约 G3R nonempty_mean | 34 | 28 | 6 | 6 | 74 |
| 合计 | 198 | 180 | 18 | 67 | 463 |

463 是六个案例中的张量观测数，包含同一参数名跨案例出现，不是 463 个独立实验。67 项 d 没有新增动态证明，不统一改称“饱和已确认”。上轮 R/G0 和 AC/G0 的动态取证原件只读引用。

这里的“无梯度／近零”指当前监督损失产生的梯度。它不排除优化器 weight decay 引入更新，也不等于参数在所有训练状态下一直不变。证据位于 `zero_classification/summary.json` 及逐案例 JSON。

## 5. GPU 已通过项与显存停止

### 5.1 七次 GPU 数值诊断均完成

AC 节点 fold0 的 G0、G3R 各 original 两次＋shared 一次，共 6 次三轮诊断。共享实现同时与两次原实现比较，原始损失重新计算，best/last 文件 SHA、元数据、图/配置/初值/划分绑定和重载一致性均核验。另完成 1 次原实现历史三轮重放，共 7 次诊断 fit／21 个 epoch，不计入 pilot。

| 剖面 | original 重复损失最大差 | shared 对两次 original 的最大差 | 门槛 | 结果 |
|---|---:|---:|---:|---|
| G0 | 0 | 7.62939453125e-6 | 1e-4 | 通过 |
| G3R | 0 | 3.5762786865234375e-7 | 1e-4 | 通过 |

历史重放使用原 paper 划分／配置单独比较，不与新 nested 验证集混用。三轮 train/validation 损失与历史 history.jsonl 的最大差为 0（门槛 1e-4），通过；其重复验证导出不能称独立测试。

| 诊断 | peak allocated（MiB） | peak reserved（MiB） | 整卡最低空闲（MiB） | 记录耗时（秒） |
|---|---:|---:|---:|---:|
| G0／original_1 | 920.462 | 1004 | 999 | 91.82 |
| G0／original_2 | 920.462 | 1004 | 999 | 88.90 |
| G0／shared | 561.415 | 608 | 1367 | 88.30 |
| G3R／original_1 | 1459.798 | 1594 | 413 | 101.30 |
| G3R／original_2 | 1459.798 | 1594 | 407 | 100.92 |
| G3R／shared | 850.383 | 946 | 869 | 102.89 |
| G0 历史重放 original | 920.462 | 1004 | 966 | 87.85 |

资源计时覆盖模型构造/转设备、训练、评分和 checkpoint 重载；不等于单独 kernel 性能基准。整卡空闲与 PyTorch allocated/reserved 是不同统计口径，不能用 4096−allocated 代替真实空闲。两组小型节点 GPU 对照通过，不代表较大的合约探针一定通过。

### 5.2 新计划和完整训练探针

新计划封存在 prompt7b3_v1/pilot/plan.json 与 plan.seal.json，4任务×G0/G3R×fold0×seed1=8项，全部 shared_projection。固定 graphs_v2_r1 的 16 图、20 schema 校验通过。pilot_initial_alignment.json 逐项核验8组实际 tensor digest，与原 Prompt7准备一致；图/支持量、split、seed、训练配置一致，只有获准的 layer_impl 标识不同。没有使用 smoke 或训练后的权重。

先执行 reentrancy_contract/0/1/G3R，最大50轮、原早停和学习率不变。第1轮训练/inner_val/保存best完成后，trainer.py:136 的资源检查抛出 MemoryGateError：
整卡最低空闲 66 MiB <100 MiB；64次采样、无采样异常；没有 CUDA OOM。

| 探针 | peak allocated（MiB） | peak reserved（MiB） | 整卡最低空闲（MiB） | 记录耗时（秒） |
|---|---:|---:|---:|---:|
| Prompt7原实现历史探针 | 3299.848 | 3536 | 12 | 56.25 |
| 本轮 shared_projection | 1824.086 | 2048 | 66 | 44.33 |

PyTorch峰值分配下降约1475.76 MiB（44.72%），reserved下降1488 MiB；但本轮仍未达到资源门槛。两次整卡统计也受当时的驱动/桌面等占用影响，这不是严格的显存性能基准，不能将差值全部归因于单一因素。

失败现场保留 attempt_001.started.json、failure.json、resources.json、binding、model_input、history.jsonl、partial best.pt/json。仅1条完整epoch记录；last.pt、最终result、成功receipt均不存在。没有将部分best当作正式结果，没有重跑、修改门槛/模型/图或关闭其他程序。

pilot_matrix_verification.json 确认0/8完成；其余7项未启动。失败发生于首轮末，逐canonical梯度审计只在内存中尚未最终落盘，不从partial checkpoint臆测其通过。完整pilot的env排除、梯度、best/last重载、最终预测及每任务耗时验收均仍未完成；前述7次GPU诊断的重载通过单独保留。

### 5.3 停止边界与后续选择

本轮正式停止于资源门槛，不自动进入 Prompt8、重试或启动其余7项。没有足够的完整训练耗时，因此不从1轮日志外推150次正式实验时长；PROGRESS中将估算标为待完整pilot通过。

接下来需要先由用户选择资源处理方案：
- 可先核查并由用户自行释放非必要Windows GPU占用；当前数据不能保证只靠关闭程序就能满足后续峰值。
- allocator碎片参数可作为另一个单独授权的资源试验；reserved−allocated约224 MiB不等于保证可释放224 MiB，不擅自设置。
- 本轮已是独立进程、单GPU worker串行，不能再把“改成串行”当作尚未采用的解决措施。
- 更大显存设备可保留模型规模；混合精度、降低维度/层数、子图采样会改变数值或训练方案，不属于本轮授权。

若获准重试，应在原失败证据保留的前提下显式建立新attempt、从同一未训练初值开始，不叫epoch续训。这里仅列选择，没有实施。

## 6. 测试、不变量及证据保存

| 检查 | 通过 | 失败／跳过 | 警告 |
|---|---:|---:|---:|
| 本轮新增测试（已包含于下一行） | 130 | 0／0 | 见各定向日志 |
| 全部 dfg_v2/tests | 1661 | 0／0 | 8 |
| 旧 DDG＋graph_utils 回归 | 223 | 0／0 | 29 |

不重复计数共 **1884 项通过**。警告为既有 DGL distutils、NetworkX gpickle 等弃用提醒。单元测试全通过不等于完整pilot已验收；本轮GPU数值通过而pilot资源门槛失败，二者分开记录。

阶段性 invariants_runtime.json 核对11,264个旧跟踪文件无意外改动，246个旧诊断产物SHA不变。最终追加三文档并用 invariants_final.json 复核：只允许三文档和 precision_gpu.py 改变；其余旧文件及历史产物摘要一致，三文档旧前缀完整保留。固定store SHA仍为 ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。

Prompt 6b、6c、6d 系列原产物、graphs_v2_r1、已有人工审查/有界残留结论均未被本轮替换。近零说明与数值诊断不消除图语义覆盖限制或人工 Oracle 尚未完成的部分。

## 7. 命令与输出位置

输出根目录为现有 WSL 工作树下 `scripts/DFG/experiments/artifacts/dfg_v2/prompt7b3_v1/`。已有目录和收据拒绝覆盖；以下为实际调用形式，重跑不能继续使用同一输出路径，也不应未经授权重试资源跳过项。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json
OLD=scripts/DFG/experiments/artifacts/dfg_v2/prompt7b2_v1
O=scripts/DFG/experiments/artifacts/dfg_v2/prompt7b3_v1

python -u -B -m scripts.DFG.dfg_v2.experiment.precision_guard \
  --plan "$PLAN" --task access_control_node --profile G0 --reducer mean \
  --static-report "$OLD/cpu/static/access_control_node_G0_mean/static.json" \
  --output "$O/cpu/guard/access_control_node_G0_mean"

python -u -B -m scripts.DFG.dfg_v2.experiment.precision_zero \
  --static "$OLD/cpu/static/access_control_node_G0_mean/static.json" \
  --output "$O/zero_classification/access_control_node_G0_mean.json"

python -u -B -m scripts.DFG.dfg_v2.experiment.precision_gpu noise-fit \
  --plan "$PLAN" --profile G0 --repeat original_1 \
  --cpu-acceptance "$O/cpu/acceptance.json" \
  --output "$O/gpu_noise/G0/original_1"
python -u -B -m scripts.DFG.dfg_v2.experiment.precision_gpu noise-summary \
  --output "$O/gpu_noise/G0"

python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

其余两个 CPU 案例、六组结构分类和 GPU repeat 的实际 argv 由相应 guard/run 收据记录。`gpu_execution.jsonl` 记录本轮串行执行事件；实际完成数量以成功收据为准，不能以计划数量代替。

CPU 新放行通过 `precision_policy.build_acceptance` 写入独立清单/seal；代码和源摘要由该清单绑定。旧原件、原失败和新跳过记录分开保留。本轮已停止，最终状态见第5、8节及 final_acceptance.json；三文档已追加，本地提交后不自动推送。

## 8. 本轮收据与交付状态

final_acceptance.json 明确记录 cpu_policy_gpu_numeric_passed_pilot_memory_stopped；probe_stop_evidence.json 绑定失败现场全部文件SHA。CPU guard中两组成功、一组资源跳过；策略跳过和历史复用单列。没有新的静态前向/反向；新增CPU完整fit4、部分fit1，GPU诊断fit7，pilot部分fit1、完整fit0。

测试共1884通过，0失败/跳过（数值执行的内存跳过不是pytest skip）；全v2耗时97.44秒、旧回归3.09秒。修改代码运行测试后未再变动，只补报告和三文档。三文档为 PROGRESS.md、HANDOVER.md（注明Codex）和 docs/training_changes_2026-10-07.md §58。按共享上下文本地提交，不自动push。

新增pilot命令已实际执行；失败后没有追加retry：

~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.run plan   --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json   --profiles G0,G3R --folds 0 --seeds 1 --layer-impl shared_projection   --output "$O/pilot"
python -u -B -m scripts.DFG.dfg_v2.experiment.run execute   --plan "$O/pilot/plan.json" --only reentrancy_contract/0/1/G3R
~~~

产物保存在现有WSL工作树，未改到C盘另存模型；所在WSL文件系统约828GiB可用。所有旧失败与旧partial保持原样，不删除日志掩盖未通过阶段。
