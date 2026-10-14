# MANDO-LLM + DDG 冻结权重原因诊断

执行者：Codex。日期：2026-10-13。
新增内容全部位于本目录；不修改原 DDG、HGT、tokenizer、训练逻辑、图、标签、划分、checkpoint 或已封存报告。最终结论见 diagnostic_report.md；完成状态以 input_audit.json 和各 stage/completion.json 为准。

## 输入与边界

- 归档 HEAD：3fb3fbcaed34c5c97976b570aac484935aa81484。
- 封存训练基：646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc。
- 正式实验：scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c。
- prepared 图、权重和标签由 plan/state/receipt/manifest 定位，不靠文件名猜测。
- 正式任务：重入/访问控制 × 合约/节点，共30个配对折。原指标为 CV validation；节点单位仍为原 HCG 节点。
- 新协议：frozen-checkpoint-ddg-diagnostics-v1；评分角色 exploratory_cv_validation_sensitivity。这是固定权重敏感性诊断，不是重训练消融或独立测试。
- 保护集合包括5387份既有文件。完整边界见 archive/protection_scope.json；不声称备份了整个仓库所有无关 ignored 输出和 Git 元数据。
- 不执行 formal verify，也不修改旧 plan 使其适配归档 HEAD。

## 环境

WSL Ubuntu-22.04；使用 /home/zhao/miniconda3/envs/mando/bin/python。
实际 Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1。
GPU：RTX 3050 Laptop，4 GiB。环境及查询结果见 environment.json。
模型 eval() + no_grad()；串行构造 E0/E1，每次仅一套模型和必要图驻留 GPU。没有 optimizer、backward、参数更新、训练重试、依赖安装或下载。

## 诊断模块

- archive_audit.py / validate_runner_inputs.py：归档、绑定、输入摘要及最终零漂移检查。
- static_analysis.py：冻结分析器内存重放；覆盖、事实、投影、实际模型两跳信息增量、错误覆盖、train-only 精确重复索引。
- interventions.py：运行时观察原 HGT；N保持原计算，Z仅将两层实际 DDG 消息置零。
- rewiring.py：文件/可确认函数/canonical 内有向双边交换，保持各节点该关系入出度及基础边。
- run_diagnostics.py：严格加载 checkpoint、原生一致性门槛、N/Z/R和试点初始/best/last输出。
- aggregate_results.py：从导出预测独立重算指标，并汇总全部30对；不会加载模型。

Z保留拓扑、attention、canonical编号和跨关系mean分母。第一层屏蔽后隐藏表示改变，第二层基础消息的数值可以随输入改变；这不是删改基础边或基础消息公式。Z不等于重新训练的E0。

R固定种子101/102/103，只表示扰动种子。报告原边集合实际替换量，不把EID顺序交换算作语义变化。全图与val文件的扰动量分开；不能把缺乏有效交换的结果解释为依赖语义无用。

## 实际命令

以下是执行记录，不是覆盖既有输出的命令；程序拒绝覆盖已有 stage 和汇总文件。命令均在项目根目录、mando环境中运行。

~~~bash
export PYTHONDONTWRITEBYTECODE=1
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2

python -B scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/report_stage_c.py \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c \
  --output /tmp/ge-sc-llm-ddg-diagnostic-archive-check-5056b40357ad

python -u -B scripts/DFG/experiments/audit/ddg_diagnostics_v1/static_analysis.py

python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/audit/ddg_diagnostics_v1

python -u -B -m scripts.DFG.experiments.audit.ddg_diagnostics_v1.run_diagnostics \
  --stage pilot --output-name pilot_v2 --device cuda:0

python -u -B -m scripts.DFG.experiments.audit.ddg_diagnostics_v1.run_diagnostics \
  --stage remaining --pilot-output pilot_v2 --device cuda:0

python -B -m scripts.DFG.experiments.audit.ddg_diagnostics_v1.aggregate_results \
  --pilot-output pilot_v2 --remaining-output remaining
~~~

仅复核现有导出预测可在最后一条加 --validate-only，不进行模型前向。

预定7个试点为四任务fold0，以及重入节点fold8、访问控制节点fold7/fold8。其initial/best/last只用于量级比较；主诊断仅best。其余23对不重算已完成试点，不扩展到全部last。

## 一致性与数值口径

- 原生预测和混淆矩阵必须与归档完全相同；四指标绝对误差不超过1e-10。
- 原生CUDA正类概率与归档比较，预先固定 atol=1e-6、rtol=1e-5。
- N包装器与同设备原生输出逐位相等；退出干预后正常输出也必须逐位恢复。
- 节点按 source_file + 原始节点ID显式对齐；合约按文件对齐，不按最近行猜测。
- 概率差输出由保存的float32 logits在CPU softmax计算，供独立重算；原生CUDA归档门槛另行核验，不能混为逐位相同的概率口径。
- 消息norm为每节点展平heads/hidden后L2，按层/type/file记录mean/median/p95等；分母小于等于1e-8时从比值分母中剔除并单列。
- 所有节点类型合并时按node count加权均值；不从类型分位数伪造全局median/p95。范数包含完整前向图，评分仅val。
- 关系bank std是实际矩阵slice的population std；初始共享E1关系源自E0参数库，新DDG来自E1库。4D bank和单矩阵Xavier理论尺度分别记录。

## 开发过程的透明记录

- DGL0.6.1异常路径的local_scope缺乏finally保护；独立包装器保存并恢复原node/edge frame引用，原DGL和HGT未修改。
- 第一次 forward/pilot 在模型构造前因 CUDA 尚未初始化时调用 reset_peak_memory_stats 失败。小探针证实这不是模型/数据错误；新诊断显式先初始化CUDA后查询统计。失败目录和pilot_execution.log保留，正式前向使用独立pilot_v2。没有放宽门槛。详见 diagnostic_compatibility_issue.json。
- D1初稿的mapping语法计数、文件回退函数分母与CSV空字段统计经过诊断自身修正；初稿及修正记录保存在static/draft_v1和static/diagnostic_statistics_corrections.json。原图、原事实、原标签均未改动。

## 产物定位

input_audit.json：归档与前后摘要；coverage.csv、edge_increment.csv：D1；
sensitivity.csv：逐折逐条件指标及差异；rewiring_audit.json / rewiring_validation.csv：重连充分性；
message_norms.csv / message_global_by_fold.csv：消息量级；parameter_scales.csv：试点初始化与权重；
representation_changes.csv：LayerNorm前后表示变化；
aggregate_summary.json：四任务汇总；case_studies.md：具体源码/原标签/预测；
diagnostic_report.md：最终证据分级及下一项最小实验建议。

所有后续建议仅列入报告，本轮结束后不自动修复原算法、不扩展状态/modifier/跨过程分析，也不启动训练。
