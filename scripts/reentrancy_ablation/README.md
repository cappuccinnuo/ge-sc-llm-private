# 重入固定折对照实验

由 **Codex** 于 2026-10-08 新建。所有新代码、图、折清单、权重和报告仅保存在本目录，不修改原训练器、构图器、标注器或交接文档。

正式实验已完成：**14组、105折，seed=1**。请先看 [结果分析](ANALYSIS.md) 和 [完整CSV](artifacts/v1/summary.csv)。原有代码和输入文件的完整性检查均通过。

## 目的与边界

逐项区分本地与作者重入实验之间的标签、边关系、节点特征、梯度、验证计算、学习率和选轮方式差异。这里的作者参照是公开下载图，不是作者提供的完整可重复训练包。

- 合约：作者 HCG 全图，142 文件 / 71 漏洞文件，18,312 节点 / 19,267 边，5 折。
- 节点：同一全图中 71 漏洞文件的完整诱导子图，12,036 节点 / 11,710 边，10 折。
- 作者节点标签 6,570；本地 source_range 标签 6,976。
- 使用现有两次作者 HCG 运行中保存的 selection.json 折清单，按文件名冻结。这些不是论文作者未公开的原始折清单。
- 固定折不消除模板跨折重复。报告是交叉验证成绩，不是独立外层测试成绩。
- 本轮为 seed=1 的受控初始实验，不宣称多随机种子稳定性或统计显著性。

## 文件职责

| 文件 | 作用 |
|---|---|
| common.py | 路径边界、限制图加载、哈希、随机数和指标 |
| freeze_folds.py | 从历史 selection.json 冻结每折文件名；检查覆盖、不交叉 |
| prepare_variants.py | 构造四个单因素图版本并断言其余内容不变 |
| audit_features.py | 核验 token 与实际编码文本的对应关系 |
| run_experiment.py | 独立训练循环，复用现有 HGT 模型，显式配置各项行为 |
| run_suite.py / run.sh | 顺序运行实验，逐轮写实时日志，可跳过完整结束的折 |
| summarize_results.py | 从逐样本留出预测复算 F1，输出 CSV、JSON 和 RESULTS.md |
| audit_weight_updates.py | 检查保存权重是否按梯度开关更新 |
| audit_scheduler.py | 导出实际学习率和 Adam beta1 曲线 |
| probe_injected_names.py | 固定注入标识符规则的诊断，不参与训练或选轮 |
| audit_labels_and_overlap.py | 标签分歧与仅使用训练折的代码片段查表诊断 |
| plot_results.py | 绘制实验均值及逐折标签对照图 |
| test_ablation.py | 折隔离、单因素数据、初始化和梯度切换测试 |

## 数据对照

A_author：作者结构/8 类边/标签 + 之前在作者图上本地生成的原始 Token ID。

B_local_labels：只将 source_range 节点标签按已验证双射转移到 A，其余不变。

C_local_relations：只替换成本地 7 类关系；边端点及重数不变，标签、token 不变。关系矩阵数量因此改变，不能声称完整模型参数相同；共有非关系参数和具有相同 canonical etype 的关系参数均复用 A 的初始化。新增关系使用已固定种子构造的初始化，详细 schema 写入每折结果。

D_local_features：只将本地已有 token 转移到 A；A 的 code 字段、结构、标签均不变。作者和本地节点经 source_file/node_type/规范化 code/AST 锚点唯一对齐，禁止近似匹配。

**特征文字审计**：作者原始图没有 token 属性。A 编码的是作者图中保存的 DOT 字符串，包括外层引号和转义换行；D 使用本地源码文本生成的 token。两套特征均是本地重建，不能把 A 称为作者提供的特征。feature_text_audit.json 给出全量重新编码核验结果。

## 训练对照

每组最多 50 轮，patience=7。当前模式 delta=.001，实际 hidden=128、HGT=2 层、8 头、dropout=.2、LayerNorm=True。合约 Adam weight_decay=5e-6，节点为0。

| 实验 | 只改的行为 |
|---|---|
| A_author | 当前流程基准 |
| B_local_labels | 节点任务的标签 |
| C_local_relations | 关系类型及相应 schema |
| D_local_features | token 向量 |
| T_gradient_detached | 合约分类池化输出 detach，模拟原版梯度中断 |
| T_validation_legacy | 节点复用更新前 train/dropout logits 监控验证 |
| T_lr_legacy | 原版调度行为（学习率，以及合约任务的 Adam beta1 调度） |
| T_delta_legacy | 合约 delta 改为原公开代码 .005 |
| T_upstream_behavior | 组合原版行为，主结果用 last；不是单因素组 |

当前学习率：合约 .0005 → .01 → .0005；节点 .0002 → .005 → .0002。

OneCycle 默认 `cycle_momentum=True`，合约当前调度同时改变 Adam beta1，旧式不 step 则 beta1 固定 .95。因此 T_lr_legacy 是调度行为对照，不是严格的学习率单变量实验。`scheduler_trace.json` 记录每轮学习率和 beta1。

legacy 学习率：合约构造默认 OneCycle 后不 step，实际为 .0004；节点默认 OneCycle 下降到约 2e-8。所有实验仍使用共同折、共同初始化、50 轮上限，组合原版行为不等于恢复未公开的论文运行环境。

每次训练同时保留 best.pt 和 last.pt。best 按监控 loss 的绝对最低值选取，patience 按独立的 delta 改善参考计数。legacy validation 故意保留“用更新前 train logits 监控、保存更新后权重”的原版行为，最终 best/last 指标均重新 eval 前向计算。此差别写入 selection_note。

B 组同时报告：
1. 使用 B 自身标签的训练/验证分数；
2. 同一预测对固定作者标签的分数。
改变评判标签本身不能解释成检测能力提升。

## 初始化与运行记录

A/B/D/各训练行为组同一折完整初始 state_dict 完全一致。C 共享参数一致，关系 schema 不同部分单独列出。每折均重新构造模型和 Adam；训练前重设 Python/NumPy/Torch/CUDA 随机数。GPU DGL 原子聚合仍可能有微小非确定性。

合约总数低于原 batch_size=256，因此独立入口每轮使用完整训练折一个 batch；排列用固定文件名顺序，属于所有组共同的实验控制。节点任务使用全图前向与训练/验证节点掩码。不存在跨文件图边。

输出：
- prepared/：四套图、graph_labels.json、node_folds.json、contract_folds.json、manifest.json；
- initializations/：每任务/种子/折的参照初始化；
- runs/任务/实验/seed_1/fold_N/：best.pt、last.pt、history.jsonl、predictions.json、result.json；
- suite.log：全部实时输出；
- summary.csv、summary.json、RESULTS.md：汇总结果；
- ANALYSIS.md：完成后的人工核对分析。

## WSL 使用

先激活环境并进入项目：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
```

实时查看已启动的实验：

```bash
tail -F scripts/reentrancy_ablation/artifacts/v1/suite.log
```

查看后台状态：

```bash
python -m json.tool scripts/reentrancy_ablation/artifacts/v1/suite_seed_1.json
```

已有 prepared 数据时运行或续跑（请先确认后台任务已结束，避免同时写同一目录）：

```bash
bash scripts/reentrancy_ablation/run.sh
```

只运行一组：

```bash
python -u scripts/reentrancy_ablation/run_experiment.py \
  --task node --experiment B_local_labels --seed 1 \
  --output scripts/reentrancy_ablation/artifacts/v1/runs/node/B_local_labels/seed_1
```

汇总与测试：

```bash
python scripts/reentrancy_ablation/summarize_results.py
python scripts/reentrancy_ablation/test_ablation.py
```

prepare_variants.py 拒绝覆盖已存在的准备目录；实验 runner 拒绝将不同配置写到已有结果目录。完整结束的折直接复用，中断的折从头训练，重写该折临时日志与 checkpoint，不修改其他折。

## 论文对照口径

Dataset A / CodeT5p-770m：
- Table 3 重入合约 Buggy-F1=91.67、Macro-F1=91.49。
- Table 5 重入行级 Buggy-F1=96.78，没有 Macro-F1。
- 当前细粒度指标按节点计算，沿用公开仓库，不是展开并去重后的唯一源码行 F1。
- Table 4/6 是 Dataset B，不用于当前比较。
