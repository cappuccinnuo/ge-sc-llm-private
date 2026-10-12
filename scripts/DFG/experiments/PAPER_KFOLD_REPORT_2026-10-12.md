# paper_kfold 主协议实施与验收记录（2026-10-12）

修改 AI：Codex。记录时间：2026-10-12T12:56:45.050158+00:00。本轮依据实际源码、README、可读 JSON 记录实施；不把工作区已有修改计为本轮修改。

## 1. 本轮范围与旧记录核验

新增主协议 `paper_kfold / ddg-paper-kfold-v1`。旧 `ddg-nested-paired-v1` 通过 `nested_strict` 旁路保留，旧实现、严格支持策略及结果不覆盖。所有新增运行逻辑、测试与实验产物位于 `scripts/DFG/experiments/`。原 DDG、HGT、tokenizer、原训练脚本未改；仅追加 README 和既有训练/交接文档说明。

`REPORT_2026-10-12.md` 的原始文件是合法 UTF-8，6458 字节，其中 2602 个字面量 ASCII 问号、0 个汉字。不能通过换解码方式找回中文。原文件保留，字节备份和编码证据保存在 `audit/paper_kfold_v1/`。原始 SHA-256：
`ff20d660b7d38e67c4ecfc75befa6c9bdc7ce19f0322a41012b8594efca4fd0c`。
本报告是依据源码和 JSON 新写的记录，不是对损坏正文的猜测恢复。

## 2. 最小修改清单及实现

| 新增文件 | 关键接口与理由 |
|---|---|
| paper_protocol.py | convert_document/validate_document 精确转换冻结划分；独立协议版本与摘要；initialize_pair 包装旧语义初始化算法但不改变随机抽样 |
| paper_runtime.py | Supervision 完整图前向加 mask/文件监督；validate_registration 检查模型与 HGT 层字典、参数库、DGL ID 和端点；graph_schema_and_support 分离注册与训练实例支持；gradient_audit 分类记录 DDG 梯度 |
| paper_checkpoint.py | 新格式 ddg-paper-cv-checkpoint-v1；复用 model_validation；保存/恢复前校验协议、schema、输入和状态摘要 |
| paper_run.py | 新单层 CV 训练编排；复用现有模型、配置来源、StopMonitor、CE、Adam、OneCycleLR；保存 best/last 及 CV 预测 |
| run_experiment.py | 默认 paper_kfold；nested_strict 直接调用旧 run_pair.run，不改变旧阻断逻辑 |
| audit_paper.py | 在不训练的条件下检查全部折；实际原 HGT 构造 schema 与结构统计交叉核对 |
| summarize_paper.py | CV 专用 JSON/CSV 导出；拒绝混合 nested/outer 评分或静默忽略不完整折 |
| tests/test_paper_protocol.py | 转换、版本、摘要、协议目录与初始化版本测试 |
| tests/test_paper_runtime.py | 稀有类型/关系、字典错误、mask、原生前向/梯度、跨文件连接测试 |
| tests/test_paper_run.py | 真实小 HGT 训练、val-only DDG、best/last、输入绑定、预测身份及旁路回归 |
| tests/test_paper_reporting.py | 主结果角色、输出命名和混合协议拒绝测试 |

已有实验 Python 文件全部保留；已有 README 在顶部新增主协议说明，历史 nested 正文完整保留。训练变更文档与 HANDOVER 只追加记录，并保存追加前字节备份。

## 3. 主协议的实际行为

1. 合约任务仍为文件级 StratifiedKFold 5 折，节点任务为文件级 KFold 10 折，沿用旧排序和 seed1。
2. 新 train 严格等于旧 inner_train 与 inner_val 的并集；新 val 严格等于旧 outer_test。新 JSON 嵌入旧完整清单及摘要；重新计算摘要也无法绕过“精确转换”检查。不另抽样、不挑 seed、不丢折。
3. 只对 train 监督反传。每轮更新后执行 eval/no_grad，在 val 上计算 loss，复用 patience=7、delta=0.001；每次严格更低 loss 更新 best，patience 的显著改进阈值另行计数；结束时保存 last。
4. best 和 last 都在同一 val 评分，因此结果叫 **CV validation**。这不是 independent outer test，也不是嵌套交叉验证的外层泛化估计。
5. 节点模型每次调用原 model()，在完整固定节点任务图前向，然后按 train/val mask 取行。合约模型调用原 model(files)，内部仍在完整固定合约任务图前向，仅指定文件 batch 接受监督。本次 Dataset A 的 train 文件能放入单个完整文件 batch。
6. E0 从 E0 全任务图注册；E1 从 E1 全任务图注册。模型间按节点类型名称和 canonical relation 对齐共同初始参数。E0 不增加空 DDG 关系；不同类型/关系不合并或借用参数；不用训练过的 E0 初始化 E1。
7. 初始化算法单独记录为 `semantic-paired-native-xavier-v1`，调用旧 paired_initialize 原实现，保留原随机数与 native full-bank Xavier 尺度；初始化版本不再冒充实验协议版本。
8. 模型注册完整 schema 不等于每种关系都有训练实例。已注册且只出现在 val 的类型/关系允许预测并列入支持审计。未注册、字典错位、参数库不匹配、图端点/特征/标签或 checkpoint 绑定不一致仍报错。
9. 跨文件连接直接报错，不删连接或样本来“通过”审计；训练和评分期间不创建参数。语义 CFG/DDG 分析、标签构建、tokenizer 都没有重跑或改变。
10. DDG 支持为 0 时允许监督梯度为 0；支持非零但观测到零梯度会显式记为诊断，不能仅凭一次零值断言断图。HGT 整体梯度断开、支持关系参数库断开和错误字典仍会报错。contract 的 Adam weight_decay 可能改变无监督支持的参数，不能把这种变化当成关系受到训练监督的证据。

主协议保留了此前已修复的梯度、eval 和最优权重逻辑。协议名字说明本轮按用户要求恢复单层 K 折、完整图前向和同 val 选模/评分，**不代表恢复了作者未公开的折清单，也不保证所有训练实现细节与作者历史执行一致**。

## 4. 数据、schema 与划分

使用两类作者标签 prepared 图；没有混入 local narrow 标签。节点任务图是在同一原图中按图级标签选出的 buggy 文件集合，当前已有 prepared 不重建。

| 数据/任务 | 文件数 | 节点数 | E0 原边 | E1 新增正向 DDG | 漏洞节点 |
|---|---:|---:|---:|---:|---:|
| 重入/合约 | 142 | 18312 | 19267 | 3363 | 6570 |
| 重入/节点 | 71 | 12036 | 11710 | 1711 | 6570 |
| 访问控制/合约 | 114 | 13432 | 15538 | 3765 | 2977 |
| 访问控制/节点 | 57 | 7710 | 8840 | 2632 | 2977 |

以上边数是 prepared HCG 边数；原模型的基础关系反射行为照旧，新 DDG 不添加反向关系。所有任务均有 16 种节点类型。模型实际注册的 canonical relations：

| 任务 | E0 | E1 | fold0 train/val 文件 |
|---|---:|---:|---:|
| 重入/合约 | 165 | 179 | 113/29 |
| 重入/节点 | 146 | 158 | 63/8 |
| 访问控制/合约 | 163 | 179 | 91/23 |
| 访问控制/节点 | 153 | 168 | 51/6 |

固定特征为已核验的 Salesforce/codet5p-770m tokenizer ID、inside_token、float32[512]；原 stored code（包含作者 DOT 序列化形式）不改。本轮不调用完整 LLM，不重新编码。

## 5. 测试与结构审计

按阶段先测试再进入下一阶段：

| 阶段 | 验证 | 结果 |
|---|---|---|
| 划分与初始化 | 新协议 + 旧 protocol 测试 | 24 passed |
| 完整图运行 | 新 runtime + 旧 runtime | 36 passed，4 个依赖弃用警告 |
| 训练与 checkpoint | 新 run + 旧 run_pair + 旧 checkpoint | 18 passed，4 个依赖弃用警告 |
| 实验全套 | experiments/tests | 95 passed，4 warnings |
| DDG 全套 | scripts/DFG/tests | 170 passed，28 warnings |
| 原项目全套 | tests（当前同四个测试文件） | 25 passed，7 warnings |
| 主折结构审计 | 两类 × (5+10) 折，E0/E1 配对 | 30/30 pass，0 blocked |

阶段测试有重叠，不能把表内各行相加。最终三套回归总计 **290 passed，0 failed，0 skipped**，其中新增实验测试 42 项。警告是现有 DGL/TensorBoard distutils 与 NetworkX read_gpickle 弃用提示，未升级依赖。合成图测试不等于 Solidity 编译验证。

实际命令和完整日志保存于 `audit/paper_kfold_v1/test_results.json` 与 experiments.log/ddg.log/project.log。命令为 mando 环境的：

~~~bash
python -B -m pytest scripts/DFG/experiments/tests -q
python -B -m pytest scripts/DFG/tests -q
python -B -m pytest tests -q
~~~

30 折中 **21 折存在完整图已注册但 train 未出现的类型或关系**，均保留；所有 E1 折都至少存在一些训练 DDG 边。审计不仅统计 NetworkX：每个完整任务图实际构造原 HGT，核对其注册 schema 和 model_validation 输入摘要，再对每折计算支持统计。没有对 30 折做完整训练。

## 6. 四任务 fold0 短检查

CPU，threads=2，固定 seed1，hidden128、2 层、8 头、norm、dropout0.2。每个 E0/E1 3 个 epoch，使用 50-step OneCycle 计划；没有把调度压缩到 3 步。

- 节点：Adam initial_lr=0.0002，max_lr=0.005，div_factor=25，weight_decay=0。
- 合约：Adam initial_lr=0.0005，max_lr=0.01，div_factor=20，weight_decay=5e-6。
- 共用 final_div_factor=1、cycle_momentum=True、无权重交叉熵。

| 任务（fold0，CV validation） | E0 Buggy-F1 / Macro-F1 | E1 Buggy-F1 / Macro-F1 |
|---|---:|---:|
| 重入/合约 | 84.6154 / 86.0577 | 84.6154 / 86.0577 |
| 重入/节点 | 78.3767 / 72.0414 | 78.3767 / 72.0414 |
| 访问控制/合约 | 85.7143 / 86.8571 | 85.7143 / 86.8571 |
| 访问控制/节点 | 77.5385 / 75.4965 | 77.1822 / 74.9714 |


指标单位为百分数。节点结果是 **HCG 节点 F1**，不是按文件+原始源码行去重后的独立行 F1。本次 8 次短训练的 best 和 last 均在第 3 轮（JSON epoch=2），两者指标相同；不是程序把 best 固定成 last，而是三轮 val loss 每次都降低。重入合约第二轮 Buggy-F1 更高，第三轮 loss 更低；按已规定的 loss 选模，所以 best 是第三轮。

每个模型的 best/last 都重载两次，eval logits 逐位一致；导出的预测重新计算指标与结果 JSON 完全相同；参数身份始终未改变。四个 E1 的首轮 DDG message 梯度 L1 与三轮 message 参数变化如下：

| task | first DDG gradient L1 | DDG weight update L1 |
|---|---:|---:|
| 重入/合约 | 0.537885 | 93.426578 |
| 重入/节点 | 0.591061 | 36.625085 |
| 访问控制/合约 | 0.532469 | 99.760648 |
| 访问控制/节点 | 1.684659 | 44.343665 |


访问控制合约 fold0 存在两个验证独有关系：
- (expression_statement, DATA_DEF_USE, while)：train 0 条、val 2 条。
- (new_variable, DATA_DEF_USE, while)：train 0 条、val 2 条。

它们的监督 message 梯度都是 0，状态为 `no_training_ddg_support`，折正常完成。这是“注册支持与训练支持分离”的真实数据证据。

前三个任务 E0/E1 的最终离散预测相同，但 loss/概率不同；访问控制节点 E1 在短检查中多 3 个 FP，Buggy-F1 低约 0.356 个百分点。**三轮短检查不能证明 DDG 有效或无效，不能把这些数当成论文对比的最终 K 折成绩。**

## 7. 输入不变性、产物与命令

末次摘要核验：46 个冻结核心代码文件全部未改变；112 个旧实验文件中只有 README 增加主协议说明，其余均未改变。旧 prepared 图、token、标签、旧 nested 结果/日志/权重保持不变。两类原输入图与标签 JSON 的摘要相符，142+114 份源码摘要也相符。证据：`audit/paper_kfold_v1/verification.json`。

新产物位置：
- `artifacts/paper_kfold/20261012_v1/<cohort>/splits/`：转换后的两种任务清单。
- `artifacts/paper_kfold/20261012_v1/structure_audit/`：30 折结构与注册输入审计。
- `artifacts/paper_kfold/20261012_v1/<cohort>/smoke_<task>/`：配置、折清单、schema 支持、共同初始化、best/last、历史和预测。
- `artifacts/paper_kfold/20261012_v1/smoke_summary/cv_validation_summary.csv`：16 行（4 任务×E0/E1×best/last）短检查结果。
- `audit/paper_kfold_v1/smoke_execution.json`：实际执行命令、退出码和耗时。

可运行命令见 README 主协议部分，包含完整的重入节点命令，无须预先设置 BASE/RUN_TAG。切换 task=contract 并改 contract_folds.json 即合约任务；切换 cohort 为 access_control_author 即访问控制。目录存在时拒绝覆盖，复跑需新输出名。旧 nested 仅通过显式 protocol=nested_strict 或旧 run_pair 命令进入，仍可能按旧规则阻断，不把旧结果重新命名成主结果。

## 8. 剩余限制与未执行事项

- 没有运行 60 次完整训练、其他折性能实验、多 seed 或 local narrow 的新训练。完成本轮规定的结构审计和短检查后停止。
- 主协议的 val 同时用于早停、选模与评分，具有选模偏差；不能称独立测试估计。若需要该估计，保留的 nested_strict 是另一协议，其阻断问题不在本轮悄悄放宽。
- 完整任务图的 schema 在训练前已知。训练未见的参数没有该关系的训练监督，预测可能依赖初值/正则项；这不是已学会该关系。
- 原 HGT 的跨关系 mean 聚合保留。完整 schema 及新增关系可能改变聚合归一化，故 E0/E1 的任何差异不能一概归因于 DDG 所携带的数据语义；本轮不增加随机边/关系数控制实验，也不改 HGT。
- 作者标签来源与历史源码身份仍不能由本轮恢复。两类的已发布标签按原样冻结，不混入 narrow。文件级切分也没有消除 SolidiFI 模板复用。
- 保留当前标量、函数内、正向 DDG 范围，不扩展状态变量、mapping、跨函数摘要、缺失 emit 节点或反向关系；不声明完整 Solidity DDG 已实现。
- 本轮没有下载/安装依赖或编译器，没有运行新的 solc 编译验证；没有 resume-training CLI 和任意新源码推理扩展。
