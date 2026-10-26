# Prompt 7b.4：启动基线与显存探针报告

实施、复核、记录：Codex。日期：2026-10-26（America/New_York）。
开始HEAD 54f21b5；按模板 pull --ff-only 到 c97d737，分支 dfg-v2。
状态：**接入与测试通过；启动基线通过；完整探针因运行显存门槛停止，pilot 0/8。**

## 1. 结论与边界

本轮仅完成资源观测、启动检查、新计划和一次完整配置的训练尝试。重入合约 fold0/G3R 在第1轮后最低空闲76MiB，小于原100MiB门槛，停止；不是CUDA OOM。其余7项没有启动，无自动重试，未进入Prompt8。

已通过的7b–7b.3数值等价检查没有重跑。没有修改HGT/shared投影层、model、trainer、DDG、图、特征、标签、fold、初值、优化器、学习率或早停。没有结束任何Windows/WSL程序，也没有修改系统/驱动/allocator设置。

最终实验将按用户安排放到显存充足的服务器上。当前RTX3050 4GiB是本地开发与验收限制，不是最终研究模型规模上限。服务器型号/软件环境尚未核验，不将计划写成已完成的服务器验收。

## 2. 对模板假设的核验与获准调整

模板把 total − peak reserved − minimum free 叫作“进程外占用”，并推断首个任务前已有约2GiB外部占用。实际证据不支持这种归因：

- 旧resources.json没有total字段。4096MiB来自独立设备查询；不能冒称从旧resources读取。
- P7b3的启动前记录为total4096/used464/free3512MiB；不是已经占用2GiB。
- peak reserved与minimum free来自不同瞬间。差额还包括本进程CUDA/DGL/driver及后续惰性库分配。
- 本轮只读清点：WSL计算进程列表为空；初次查询used457/free3519MiB。Windows GPU计数器中较大者为dwm约247MiB、Code约111MiB、chrome约72MiB；这些是另一种计数口径，不与nvidia-smi直接相加，不证明不存在其他图形开销。未结束任何程序。
- nvidia-smi原始total−used−free为120MiB，原样保存，不强行使三项相等。

用户明确同意：
1. 改称“PyTorch分配器之外的未归属占用估计”，保留原公式、基线、context前后读数，增加有时间窗口的近同时刻采样。
2. 新策略每次只允许一个--only任务、新进程执行；8项由外部串行调用。旧计划没有resource_policy时行为保持。

符合文档要求的实现选择：新plan直接引用P7b3已经封存的prepared/initial文件，不重新随机初始化。新增来源、Git与资源策略绑定；四个top-level变化为runtime/git_head/resource_origin/resource_policy。其余字段完全相同。未修改PROMPTS原文，以本报告及三份追加记录保留纠正依据。

## 3. 文件和关键逻辑

| 文件 | 改动 |
|---|---|
| experiment/preflight.py | 新增。stdlib nvidia-smi基线；单GPU UUID与有限读数核验；passed/blocked/error收据；CUDA初始化前后观测；组合继承原Resources增加原始采样。 |
| experiment/resource_plan.py | 新增。旧plan/seal只读校验；仅允许run.py与两个新资源模块变化；逐项比较原输入/配置/初值；核验资源记录和任务/PID/计划/原始采样绑定。 |
| experiment/run.py | 最小接入。--from-plan、登记baseline阈值；新策略强制--only；预检通过后才创建attempt；context在CPU模型构造前落盘；成功/失败都保留资源引用。 |
| tests/test_preflight.py | 新增41项；基线不创建CUDA、低显存和查询错误拒绝、边界值、原100MiB门槛、context/采样等。 |
| tests/test_resource_plan.py、test_preflight_integration.py | 新增23项；旧计划路径、准确初值复用、篡改拒绝、失败保留与显式retry、完整收据绑定。 |
| PROMPT7B4_REPORT.md | 本报告。HANDOVER、training_changes §59、PROGRESS仅追加。 |

默认新策略：baseline free>=3000MiB，运行minimum free>=100MiB；baseline阈值可在建新plan时登记，运行门槛固定。nvidia-smi不可用、非单GPU或读数异常均报错停止，不默认放行。
低基线写preflight_blocked，不创建训练attempt；查询错误写preflight_error。旧无策略分支仍遵守原源码SHA校验；“行为保持”不代表修改运行源码后可以绕过旧plan的hash限制。成功任务核验后复用，不再次启动；训练失败仍保留旧attempt，须显式--retry，不能当作epoch续训。
CUDA/DGL观测仅使用1元素torch.empty与1节点1边DGL图，不抽随机数、不进行HGT计算；释放后sample reserved/allocated均为0。它不是对全部后续CUDA库初始化的穷尽。
采样保留UUID、原始total/used/free、allocated/reserved与查询前后时间，目标等待间隔0.5秒，另有查询耗时。实际配对窗口0.202–0.378秒，不能称严格同时采样。100MiB是已有合作式检查门槛，不是实时硬显存配额。

## 4. 计划与冻结输入

新目录：
scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot/

旧来源：
scripts/DFG/experiments/artifacts/dfg_v2/prompt7b3_v1/pilot/plan.json

新plan SHA：e0ff577cd73f7fa1da841cf2f1fdd1e890ebc2ede27ac047cf369ff2db5c8344。
source_plan_comparison.json记录全部8个initial实际文件SHA/tensor digest、optimizer_steps=0和fit_seed。原图/标签/特征/划分/每任务effective config完全相同，不是只比较报告简化值。
最终图仍graphs_v2_r1/store.json，SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。
协议保持dfg-v2-nested-v1：inner_train更新、inner_val选择best/早停、outer_test训练后评分。本轮没有完成最终评分，不混用旧paper_kfold指标。

## 5. 新探针实测

| 观测 | MiB |
|---|---:|
| 物理总量 | 4096 |
| CUDA初始化前used/free | 450 / 3526 |
| 最小CUDA/DGL初始化后used/free | 1742 / 2234 |
| 上述阶段空闲下降 | 1292 |
| 初始化观测时Torch allocated/reserved | 0 / 0 |
| 训练peak allocated | 1824.086426 |
| 训练peak reserved | 2048 |
| 整卡minimum free | **76，未通过100门槛** |
| 原公式未归属估计4096−2048−76 | 1972 |
| 再减初始化阶段变化1292的估计 | 680 |

新的60条原始采样中，最低free=76那一条的reserved也为2048，因此本次对应点可以核对；不能据此使所有历史峰值组合也变成同时测量。采样错误0。
基线非free总量为570MiB（450已用+120读数差额）；context调整后的680与它相差110MiB。这仍可能包含惰性初始化、驱动和其他程序波动，不能宣称680全是外部进程。进程退出后独立读取4096/473/3503MiB，也符合大部分新增占用随训练进程退出消失的解释；并非逐进程内存归属证明。

重入合约G3R的执行沿用max50/patience7、原Adam/OneCycle。只完成epoch0（显示第1轮），train_loss0.7187948226928711、inner_val_loss0.6839135885238647；epoch耗时19.17s。资源guard区段43.00s，完整子进程119.56s（含启动/context/模型/输入校验），计时口径分开。
partial best.pt及sidecar已保存；last.pt、result、成功receipt和完整梯度报告均未生成。第一轮BF1不是本批最终效果，不作为DDG结论。
first-epoch新canonical梯度审计、best/last重载与最终预测验收尚未完成；不能用之前小图或其他任务通过代替这个大图探针的未完成验收。
完整矩阵校验明确拒绝8项缺失；只读非完整清点返回completed_jobs=0，未标记成功。

## 6. 历史公式重算

历史total参考独立设备4096MiB，旧records本身没有total：

| 历史运行 | reserved | minimum free | 未归属估计 |
|---|---:|---:|---:|
| P7 R/G3R original | 3536 | 12 | 548 |
| P7b3 AC/G0 original_1/2 | 1004 | 999 | 2093 |
| P7b3 AC/G0 shared | 608 | 1367 | 2121 |
| P7b3 AC/G3R original_1 | 1594 | 413 | 2089 |
| P7b3 AC/G3R original_2 | 1594 | 407 | 2095 |
| P7b3 AC/G3R shared | 946 | 869 | 2281 |
| P7b3 GPU history original | 1004 | 966 | 2126 |
| P7b3 R/G3R shared | 2048 | 66 | 1982 |

数字差额能重现，外部归因不能。保留P7/P7b3原结果，不用当前context差值倒扣旧记录，不能保证“关闭约1.5GiB其他程序后必然通过”。

## 7. 测试、证据与不变量

- 本轮新增64项：64 passed、0失败/跳过、4条已有warning。
- 全DFG v2：1725 passed、0失败/跳过、8条已有warning，114.45s。
- 旧DDG+graph_utils：223 passed、0失败/跳过、29条已有warning，3.50s。
- 合计1948通过；64已包含于1725，不重复相加。warning是已有DGL distutils、NetworkX gpickle弃用。
- 11,271个旧跟踪文件仅允许run.py及三文档变动；旧538个P7系列产物SHA不变。三文档旧字节前缀保留。原模型/计算文件和旧seal不改。
- 运行产物留现有WSL（E盘承载），未清理历史目录，未写大型文件到C盘。

新批次包含before_tracked/doc_prefixes/previous_batches_sha256、readonly_gpu_inventory、windows_gpu_inventory、historical_accounting、测试log/XML/argv、独立plan/seal/comparison、preflight/context/raw samples、failure/partialbest、probe_stop_evidence、pilot_matrix_verification及invariants。
源码/测试/报告按共享上下文做本地commit，不自动push；大运行产物不加入Git。

## 8. 实际命令与停止位置

环境：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
~~~

实际创建新计划并尝试首项（这些目录现已存在，不能再次用plan覆盖）：

~~~bash
python -B -m scripts.DFG.dfg_v2.experiment.run plan \
  --from-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b3_v1/pilot/plan.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot \
  --baseline-min-free-mib 3000

python -B -m scripts.DFG.dfg_v2.experiment.run execute \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7b4_v1/pilot/plan.json \
  --only reentrancy_contract/0/1/G3R
~~~

测试：

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests/test_preflight.py scripts/DFG/dfg_v2/tests/test_preflight_integration.py scripts/DFG/dfg_v2/tests/test_resource_plan.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

上面execute已产生失败记录，再次直接执行应拒绝；本轮不加--retry，不自动重跑。
没有完整8次实测，暂不估算Prompt8的150次训练时长。没有启动其余7项、Prompt8、其他种子/漏洞、第二级k/v端点优化、混合精度或更换模型。
建议下一步按用户既定服务器计划做环境/路径/输入身份核验，再以独立获准的运行继续验收；无需为本地4GiB限制继续扩大模型改动。本轮到此停止。
