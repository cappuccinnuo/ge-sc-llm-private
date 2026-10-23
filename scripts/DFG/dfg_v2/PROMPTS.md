# MANDO-LLM DFG v2：仓库审查、方案合并与 Codex 编码 Prompts

审查对象：`cappuccinnuo/ge-sc-llm-private`，`main@e76285a` 与 `ddg-v1.1-correctness@e7bcb84`（2026-10-22）。审查方式是通读代码与文档；云端环境装不上 tree-sitter 0.20.4，测试没有在这里运行。

使用方法：每次给 Codex 开新会话，先贴第 4.1 节"共享上下文"，再贴一个 Prompt。按 P0 → P9 顺序执行，每一步验收通过后再进行下一步。P6 可以和 P7 并行。

## 1. 仓库现状

### 1.1 代码结构

| 部分 | 位置 | 说明 |
|---|---|---|
| 原作者建图 | `process_graphs/tree_sitter_codeviews/` | `generator.py` → `CFG_driver` → `CFG_solidity.py`，节点由 `utils/solidity_nodes.py` 生成。`ParserDriver` 会先删空行和注释，图里的行号与字节位置都基于预处理后的源码 |
| 原作者模型 | `sco_models/` | `model_hgt.py`（HGTLayer，跨关系 `cross_reducer='mean'`），`graph_utils.py`（`generate_hetero_graph_data`、`reflect_graph`） |
| 原作者训练与推理 | `node_classifier.py`、`graph_classifier.py`、`infer_smart_contract.py` | 推理走 `extend_forward`，只支持 nodetype 特征 |
| 作者代码中已有的本地修改 | 同上 | `reflect_graph` 的 `DATA_DEF_USE` 特判（Codex 10-12）、`model_hgt` 合约池化的 GRADIENT FIX、`CFG_solidity`/`solidity_nodes` 的 end_if 行号与调用边类型修复 |
| 第一阶段 DDG | `scripts/DFG/*.py`（两个分支都有） | 符号表、读写提取、独立语义 CFG、到达定义、AST 精确投影 |
| 后续 DDG | 只在 `ddg-v1.1-correctness`：`scripts/DFG/state/`、`control_dependency/`、`integration/`、`experiments/`（约 167 个文件） | 状态分析 Stage E/F/J/K、控制依赖、统一入口、实验与封存体系 |
| 数据 | `experiments/ge-sc-data/source_code/<类>/source_files` | 7 类源码，数量 142/114/120/92/88/100/190，与论文表 1 一致 |
| 本地专有资产 | 不在 Git 中 | 作者图、token、标签、折文件、checkpoint 被 `.gitignore` 排除，新 clone 无法复现实验 |

作者图的 schema（来自 `Test_code/author_graph_audit/audit_result.json`）：
- **节点类型**：`function_definition`、`expression_statement`、`new_variable`、`if`、`end_if`、`return`、`contract_declaration`、`modifier_definition`、`constructor_definition`、`library_declaration`、`interface_declaration`、`struct_declaration`、`for`、`while`、`end_loop`、`continue_statement`。没有 emit/revert 节点。
- **边类型**：`next_line`、`pos_next`、`neg_next`、`end_if`、`first_next_line`、`internal_call`、`external_call`、`recursive_method_call`。

本地 `process_graphs` 生成器产生的边类型是 `next`、`if_true`、`if_false`、`function_call` 等，与作者图不同。

运行环境：WSL，conda mando，Python 3.7.12，PyTorch 1.8.1+cu111，DGL 0.6.1，RTX 3050 4GiB。

### 1.2 已完成的工作

| 阶段 | 内容 | 新增关系 |
|---|---|---|
| 第一阶段（10-12） | 声明身份与作用域、读写事件、独立语义 CFG、到达定义不动点、AST 精确投影 | `DATA_DEF_USE` |
| v1.1（10-13） | DOT 序列化比较、if/else 注释误判修复 | 同上 |
| Stage E/F（10-14） | 函数内状态到达定义、简单 mapping、调用 HAVOC、访问顺序 | `STATE_DEF_USE`、`STATE_ACCESS_ORDER`、`EXTERNAL_CALL_BEFORE_STATE_WRITE` |
| Stage J/K（10-19） | 同文件 C3 继承、单个无参前缀 modifier、版本域修复。只作用于状态层 | 同上 |
| Guard（10-20） | 后支配控制依赖 | `CONTROL_DEPENDENCE` |
| Integration（10-21） | 统一 profile（baseline/scalar/full/full_guard）、方向 adapter、归档核验 | 五个关系 |

实验只做了重入（R）和访问控制（AC）两类，合约级 5 折、节点级 10 折，每折单种子，在 CV 验证折上报告。下表是 best 的 Buggy-F1：

| 任务 | HCG | +DDG | +DDG+控制依赖 |
|---|---|---|---|
| R 合约 | 94.16 | 94.16 | 94.16 |
| AC 合约 | 93.56 | 93.56 | 93.56 |
| R 节点 | 96.06 | 96.10 | 96.12 |
| AC 节点 | 95.97 | 95.89 | 95.92 |

工程质量很好：不变量检查、分析器与标签隔离、输入 SHA 绑定、封存与复核都做到了。

### 1.3 存在的问题

**P1 覆盖率低。**
- 标量层：R 合约任务 3404 个函数中只支持 2035 个（约 60%），AC 为 2128/3148。
- 状态层：R 为 1316/3404（39%），AC 为 1299/3148。
- 原因有三个：
  1. `symbol_table.py::_scalar_type` 遇到任何非标量的局部变量或参数，就放弃整个函数。
  2. `semantic_cfg.py::CFGBuilder` 遇到任何 modifier 也放弃整个函数。Stage J 的 modifier 恢复只接在状态层；`integration/pipeline.py` 仍然先跑旧的标量层，所以带 modifier 的函数没有 `DATA_DEF_USE`。
  3. `frontend.py::scope_mode` 在 pragma 缺失或跨越 0.5 版本边界时放弃整个文件。

**P2 没有跨函数的状态流。** `STATE_DEF_USE` 只在函数内部分析。节点图里一共只有 4/5 条这类边，而且都在构造器里。像"deposit 写 balances → withdraw 读 balances"这样的依赖完全没有被表示。

**P3 环境量没有边。** `state/access.py` 提取了 `ENVIRONMENT` 事件，但没有任何代码把它变成边。`msg.sender`、`tx.origin`、`now` 恰恰是访问控制和时间操纵两类漏洞最关键的输入。

**P4 方向只做了一种。** 所有新增关系都只有正向，从来没有和显式反向做过对照。仓库自己的 09-18 方案第八节把"HCG + 正向及反向 DDG"列为三组基本实验之一，这组没有做。

**P5 跨关系取平均带来副作用。** `HGTLayer` 用 `cross_reducer='mean'` 合并各关系的消息。新增一个关系，同一目标节点类型下的所有节点，聚合时的分母都会变，即使某个节点本身没有新增入边。Codex 10-21 的诊断显示 R 合约有 6879 个节点受影响。因此"新关系带来的信息"和"分母变化"两种效应混在一起，现有结果无法区分。

**P6 部分事实无法投影。** 作者图没有 emit/revert 节点，落在这些语句上的事实只能丢弃（控制依赖构图时有 798/134/730/60 条缺投影）。在不新增节点的前提下只能接受这一损失。

**P7 评估设计有缺陷。**
- 同一个 CV 验证折既用来选 best checkpoint，又用来报告结果。
- 每折只跑一个种子，只覆盖两类漏洞。
- 节点级 F1 已经在 96 左右，剩下的错误主要集中在标签存疑的文件上（R/AC 的 buggy_18 等）。

**P8 缺少外部正确性验证。** 没有和 Slither/solc 做对照。12 个函数的 Oracle 是 Codex 自己审阅的。

**P9 工程复杂度高。** 实验层大量用 `types.FunctionType(fn.__code__, 新globals)` 重新绑定函数字节码（`e23_pilot/training.py`、`overall_cv/training.py`、`guard_extension/model.py`、`state/stage_k/pipeline.py`）。调用链 `overall_cv → e23_pilot → paper_run → stage_f` 很难维护。

**P10 推理入口不可用。** `infer_smart_contract.py` 只支持 nodetype 特征，并且调用原 `reflect_graph`。本地生成器的 schema 和作者图不同，用作者图训练的模型不能直接对本地生成的图做推理。这是原有问题，不是 DDG 引入的。

## 2. 两套方案的对比与取舍

"对话方案"指 Mando-LLM paper analysis 对话中的设计（`ddg_solidity.py` 三层 + Prompt 0–6）；"仓库方案"指 `scripts/DFG/MANDO_LLM_第一阶段_DFG融合_方案文字说明.md`（09-18）与 Codex 的实现。

| 维度 | 对话方案 | 仓库方案 | v2 采用 | 理由 |
|---|---|---|---|---|
| 节点 | 不新建 DFG 节点，可选 env/state 辅助节点 | 不新建节点 | 不新建，环境层例外 | 新节点会影响节点标签与对齐 |
| 到达定义所用的 CFG | HCG 的函数内子图 | 独立的语义 CFG | 仓库方案 | HCG 中存在 `return → end_if → 下一句` 的虚假路径（`DDG_INTEGRATION_ANALYSIS_2026-10-11.md` §3.2） |
| KILL 的依据 | 同名变量 | 声明身份 | 仓库方案 | 正确处理同名遮蔽 |
| 非标量局部变量（struct/数组/var/string） | 对基变量做弱定义 | 整个函数回退 | 对话方案 | 提高覆盖率；论文图 1 的 MY_BANK 例子依赖这一点 |
| modifier | 没有专门处理 | 标量层回退，状态层受限恢复 | 两层都用 Stage J 恢复 | P1 |
| 状态变量 | 以声明节点为中转点，`reads_state`/`writes_state`，跨函数两跳可达 | 函数内 `STATE_DEF_USE` + 访问顺序 | 对话方案为主 | 跨函数是相对 ORACAL 的差异点；仓库方案实际只产生 4/5 条边 |
| 环境量 | `env_source` 节点 + `env_flow` | 没有 | 对话方案 | P3 |
| 方向 | 依赖 `reflect_graph` 自动加反向 | 只保留正向，反向留作消融 | 仓库方案，再把显式 `REV_*` 作为一组实验 | 原 `reflect_graph` 对两端同类型的关系会变成无向；对两端不同类型的关系，生成的反向边会和真实的反向边混进同一个 canonical 关系 |
| 接入方式 | 改 `generator.py`，加 `ddg_level` 后重建图 | 在冻结的作者图上旁路叠加 | 仓库方案；推理入口另做（P9） | 作者图、标签、token 都不动，原作者代码零修改 |
| 正确性验证 | Slither 对照 + 30 个合约人工抽查 | 12 个函数的 Oracle | 两者都用 | P8 |
| 实验 | 7 类 × G0–G3 × 5 种子，Wilcoxon/A12 | 2 类，单种子，CV 验证折 | 先做 R/AC、单种子起步，其余 5 类预留接口；改为嵌套验证 | P7 |
| 聚合方式 | 没有考虑 | 发现了问题但没有对照 | 加一组诊断实验 | P5 |

`EXTERNAL_CALL_BEFORE_STATE_WRITE` 与 `CONTROL_DEPENDENCE` 表达的是执行顺序和控制约束，不是数据流，所以不纳入 v2 的主线。它们仍然可以通过 integration 的 `full`/`full_guard` profile 使用，历史结果保留不动。

## 3. DFG v2 方案

### 3.1 关系与剖面

| 关系 | 方向 | 端点 | 层 |
|---|---|---|---|
| `DATA_DEF_USE` | 定义语句 → 使用语句 | HCG 语句节点 | L1 |
| `WRITES_STATE` | 写语句 → 状态变量声明节点 | 语句 → 状态变量的 `new_variable` 节点 | L2 |
| `READS_STATE` | 状态变量声明节点 → 读语句 | 状态变量的 `new_variable` 节点 → 语句 | L2 |
| `ENV_FLOW` | 环境源 → 使用语句 | `env_source`（新节点）→ 语句 | L3 |
| `REV_*`（上面四个关系的反向） | 反向 | 两端交换 | 只在 G3R 中出现 |

剖面定义：
- G0：原作者 HCG 的精确副本
- G1 = G0 + L1
- G2 = G1 + L2
- G3 = G2 + L3
- G3R = G3 + 四个 `REV_*` 关系

### 3.2 L1（函数内定义—使用的扩展）

- **复用**：沿用第一阶段的符号表、读写提取、语义 CFG、到达定义和投影；用 Stage J 的方法恢复带 modifier 和继承的函数。
- **新增**：非标量的局部变量和参数也作为可追踪的符号。
  - 对变量整体赋值是强定义。
  - `x.f = …`、`x[i] = …`、`x.push(…)`、`delete x.f` 是弱定义：产生新定义，但不 KILL 旧定义。
  - 读取成员或下标，算作对 x 的使用。
- **验收**：旧标量层已经支持的函数，产生的边必须与旧版逐条相同。

### 3.3 L2（以状态变量声明为中转点）

- 不做流分析，也不依赖 L1 是否成功分析了该函数。
- **收集范围**：对每个 HCG 语句节点，只收集"它自己范围内"的状态变量读写。if 只看条件；for 只看 init/condition/update；不进入有自己节点的子语句。
- **名字绑定**：
  - 本函数里出现同名的参数、返回值或局部声明，就把这个名字当作局部变量（保守处理）。
  - 否则在同文件的 C3 继承链中查找唯一的 `state_variable_declaration`。
  - 找不到或有歧义，只跳过这一处出现，不放弃整个函数。
- **写**：赋值、复合赋值、`++`/`--`、`delete` 左侧链的根；`push`/`pop`；通过 storage 引用的写。复合赋值和 `++` 同时也算读。
- **读**：除写以外的其他出现。
- `constant` 状态变量默认排除。
- 构造器、modifier 体、状态变量的初始化表达式都包括在内。

### 3.4 L3（环境源）

- 环境键：`msg.sender`、`msg.value`、`msg.data`、`msg.sig`、`tx.origin`、`tx.gasprice`、`block.timestamp`、`now`、`block.number`、`block.difficulty`、`block.coinbase`、`block.gaslimit`、`blockhash`、`gasleft`、`this.balance`。名字被局部或成员遮蔽时跳过。
- 每个文件中，每个实际用到的键建一个 `env_source` 节点，再加边 `ENV_FLOW`（环境源 → 使用语句）。
- 这些节点不参与节点监督、不计入指标、不参与合约池化。

### 3.5 HGT 接入

- 原有关系仍交给原 `reflect_graph` 处理，所以 G0 与历史完全一致。
- v2 新增的关系不经过 `reflect_graph`，按正向直接加入；G3R 再显式加入 `REV_*`。
- 原 `HGTLayer` 不修改。聚合方式的诊断用 `dfg_v2` 中的子类实现，只用于诊断组。

### 3.6 实验设计

**协议：嵌套验证。**
- 外层折（合约 5 折、节点 10 折，沿用已冻结的划分）作为测试集。
- 内层从外层训练文件中取 20% 作为验证集，用于早停和选 best（`freeze_splits.py` 已支持 `inner_fraction`）。
- 结果报告在外层测试折上。
- 训练的数值规则沿用 `paper_run.fit_variant`。

**当前范围：只做重入（R）和访问控制（AC）。** 每个剖面跑一遍是 2 类 ×（合约 5 折 + 节点 10 折）= 30 次训练。其余 5 类只预留接口（见 3.8）。

**种子：先用 1 个（seed 1）。** 同一个（任务, 折）下，所有剖面共享参数的初值逐张量相同。

| 批次 | 内容 | 次数 | 预计耗时 | 何时跑 |
| --- | --- | --- | --- | --- |
| 主矩阵 | G0、G1、G2、G3、G3R × 30 | 150 | 约 7 小时 | 必跑 |
| 聚合诊断 | G0M、G3M（非空关系平均）× 30 | 60 | 约 2.8 小时 | 可选，主矩阵后决定 |
| 补种子 | G0 与 G* 再跑 seed 2、3：2 × 2 × 30 | 120 | 约 5.5 小时 | 按内层验证结果预先登记的条件触发（见下） |

耗时按 guard_extension_v1 在你本机 RTX 3050 4GiB 上的实测（30 次共 82.7 分钟，约 165 秒/次）估算，该批最大显存占用约 2.9GiB。G3 多了 env_source 节点，Prompt 7 会实测后再更新估计。

**G* 的选择与补种子触发（2026-10-23 按 Prompt 0 审查修订，预先写进 plan）**：
- G* 只用**内层验证集**选：每个剖面在每折 best checkpoint 上的内层验证 Buggy-F1，先对折取平均，再对四个任务取平均；候选为 G1、G2、G3、G3R；与第二名差距小于 0.1pp 时选关系更少的那个。外层测试分数不参与选择。
- 补种子的触发条件同样只看内层验证：G* 与 G0 的四任务平均内层验证 Buggy-F1 差的绝对值 ≥ 0.2pp 就跑，否则不跑。
- 运行器先执行 select（只读内层验证指标，写出并封存 selection.json），之后 summarize 才输出外层测试结果。全部五个剖面的外层测试结果都报告，G* 的外层分数在报告中标明"选择基于内层验证"。

**统计方法：**
- 每个（类, 任务, 剖面）报告各折的均值 ± 标准差；补种子之后再报告种子间的均值 ± 标准差。
- 配对单位是折（补种子后为（折, 种子）），做 Wilcoxon 双侧检验并报告 Vargha-Delaney A12，4 个"剖面 vs G0"比较做 Holm 校正。合约任务只有 5 折，配对 Wilcoxon 的最小 p 值为 0.0625，单种子下只能作描述性比较。
- 另外报告 pooled OOF 指标，以及排除标签争议文件后的敏感性结果。

**特征**：主实验用 inside_token（与历史一致）；nodetype 作为可选补充。

### 3.7 对原作者代码的改动

**零改动。** 所有新代码都放在 `scripts/DFG/dfg_v2/`，通过 import 或子类化复用原有代码。Codex 已经封存的代码同样不修改。

### 3.8 扩展到其余五类的接口

现在只实现和验收 R/AC，但所有代码不写死类别名：
- **任务注册表** `dfg_v2/tasks.py`：每个类别一条记录，字段为类别名、合约级与节点级作者图路径和 SHA、源码目录或源码清单、标签文件、折文件。R/AC 两条现在填好；其余 5 类（arithmetic、denial_of_service、front_running、time_manipulation、unchecked_low_level_calls）只在注释中列出，不填。
- **分析器**：L1/L2/L3 不读取类别信息，对任何源码都一样运行。
- **构图、训练、统计**：全部以 `--tasks` 参数接收任务名列表，默认 R/AC 四个任务。
- **新增一类的流程**写进 `dfg_v2/EXTENDING.md`：（1）在注册表加一条记录；（2）跑 Prompt 0 中针对该类的锚点与 token 核对；（3）用 `freeze_splits.py`（seed=1, inner_fraction=0.2）生成折文件并封存；（4）`cli build --tasks <新类>`；（5）用已选出的 G* 与 G0 跑 `run plan --tasks <新类>`。不需要改任何分析或模型代码。
- 测试里加一条：用一个虚构的第三类别（复用 R 的一个小子集改名）走完注册 → 构图 → 构造模型 的流程，证明接口不依赖类别名。

## 4. Codex Prompts

### 4.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文

## 项目
你在 MANDO-LLM 私有仓库上实现 DFG v2：在原作者 HCG（CFG+CG 异构图）上叠加数据流关系，供原 HGT 做合约级与节点级漏洞检测。

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。远端已有分支 dfg-v2（基于 ddg-v1.1-correctness，只多了 scripts/DFG/dfg_v2/PROMPTS.md 这份文档）。第一次开始前执行：
  git fetch origin dfg-v2
  git checkout -b dfg-v2 origin/dfg-v2
之后的提交都在 dfg-v2 上。不要 push，除非用户明确要求。本文档的完整内容就在 scripts/DFG/dfg_v2/PROMPTS.md，有疑问先查它。

当前范围：只实现和验收重入（reentrancy）与访问控制（access_control）两类，合约级 5 折、节点级 10 折。其余 5 类只预留接口（见 PROMPTS.md 第 3.8 节），代码中不写死类别名。

环境（WSL）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
  export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、tree_sitter 0.20.4、RTX 3050 4GiB。
代码必须兼容 Python 3.7：不要用 :=、list[str]/dict[str, int] 运行时注解、dict | dict、dataclass(slots=...)。

## 新代码位置
- 全部新代码：scripts/DFG/dfg_v2/（含 __init__.py）
- 测试：scripts/DFG/dfg_v2/tests/
- 实验与构图产物：scripts/DFG/experiments/artifacts/dfg_v2/<批次名>/，拒绝覆盖已存在目录
- 进度文档：scripts/DFG/dfg_v2/PROGRESS.md。每个 Prompt 结束追加一节：做了什么、文件清单、测试命令与结果、验收数字、遗留问题
- 同时在 HANDOVER.md 和 docs/training_changes_2026-10-07.md 末尾追加简短记录（只追加，不改旧文）

## 禁止修改
1. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py。这些文件中已有的本地修改（reflect_graph 的 DATA_DEF_USE 特判、model_hgt 的 GRADIENT FIX、CFG_solidity 的 end_if/调用边修复）保持原样。
2. 已封存的 Codex 代码：scripts/DFG/ 下除 dfg_v2/ 以外的所有 .py（含 state/、control_dependency/、integration/、experiments/）。历史批次的 seal 绑定了这些文件的 SHA。
3. 所有已有产物、图、标签、折文件、checkpoint、plan/seal。
需要复用时用 import、子类化或组合。
禁止使用 types.FunctionType(fn.__code__, 新globals) 重新绑定字节码。如果必须改变一个冻结函数的行为，就把它复制到 dfg_v2，在文件头写明来源路径和原文件 SHA256，并加一条测试，证明它在旧输入上与原函数输出相同。

## 不变量（每一步都要保持）
- 原 HCG 的节点、节点顺序、节点属性（含 token、node_info_vulnerabilities、source_file、label、code）、原边及其 key/属性完全不变。可参考 scripts/DFG/graph_audit.py 与 scripts/DFG/integration/pipeline.py::assert_preserved。
- 分析器不读取标签、预测或 token。
- 投影只依据 AST 身份（复用 scripts/DFG/projection.py::Projector），不按行号或"最近节点"猜测。投影不到的事实丢弃并计数。
- 不能可靠分析的部分只丢弃对应事实，不删除样本或文件。
- 新增模型节点只允许 G3/G3R 剖面中的 env_source。

## 可复用模块（先读再用）
- scripts/DFG/frontend.py：SourceView（原源码视图 + 与作者预处理一致的兼容视图）、parse_source、walk、text、span
- scripts/DFG/symbol_table.py、access_extractor.py、semantic_cfg.py、reaching_definitions.py、ddg_builder.py、projection.py、pipeline.py：第一阶段标量 DDG
- scripts/DFG/state/stage_j/analyzer.py::StageJCFGBuilder（modifier 前缀 + 继承）
- scripts/DFG/state/stage_j/binding.py::ClosedScopeJ（同文件 C3 继承链；members：名字 → 声明节点列表）
- scripts/DFG/state/stage_f/frontend.py::StageFSourceView
- scripts/DFG/state/stage_k/profile.py::SupportedSourceView
- scripts/DFG/state/stage_f/binding.py::StageFCallResolver
- scripts/DFG/integration/pipeline.py（build_graph、assert_preserved、computation_fingerprint）
- scripts/DFG/integration/io.py（read_json、checked、read_sources、write_bundle）
- scripts/DFG/integration/rebuild.py::DEFAULT_MANIFEST（R/AC 四个任务的原 HCG 与源码清单入口）
- scripts/DFG/experiments/paper_run.py（fit_variant、effective_config）、paper_runtime.py（Supervision、validate_registration）、protocol.py（make_fold_document）、freeze_splits.py、e23_cv/prepare.py（seeds、select_split）、e23_pilot/model.py::_construct（按冻结图构造模型的参考实现）
- scripts/DFG/state/stage_f/initialization.py::initialize_pair（共同初值的参考实现）

## 关系名（在 dfg_v2/__init__.py 中定义为常量）
DATA_DEF_USE、WRITES_STATE、READS_STATE、ENV_FLOW；
反向：REV_DATA_DEF_USE、REV_WRITES_STATE、REV_READS_STATE、REV_ENV_FLOW；
辅助节点类型：ENV_SOURCE = "env_source"。
剖面 PROFILES：
  G0  = {}
  G1  = {DATA_DEF_USE}
  G2  = G1 ∪ {WRITES_STATE, READS_STATE}
  G3  = G2 ∪ {ENV_FLOW}（并新增 env_source 节点）
  G3R = G3 ∪ 四个 REV_ 关系（REV_ 只在模型输入阶段生成，NetworkX 图与 G3 相同）

## 工作方式
- 每个 Prompt 只做该 Prompt 的范围。代码事实与本文描述不一致时，以代码为准，在 PROGRESS.md 记录差异和你的处理方式。
- 每个 Prompt 结束时运行：该 Prompt 的新测试、scripts/DFG/dfg_v2/tests 全部测试，以及
  python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
  全部通过后 git commit，提交信息写明 Prompt 编号。
- 除 Prompt 7 的小规模验收和用户确认后的 Prompt 8 以外，不启动任何训练。
- 文档记录：每个 Prompt 结束都向 PROGRESS.md、HANDOVER.md、docs/training_changes_2026-10-07.md 末尾追加记录。这三个文件的追加不受任何 Prompt 中"不修改已有文件"的限制（该限制指代码、数据、产物和历史文档正文）。
- 新的实验产物目录（scripts/DFG/experiments/artifacts/dfg_v2/...）是允许出现在 git status 里的未跟踪路径；验收时只要求已跟踪文件中除上述三份文档和 dfg_v2/ 外没有改动。
- 开始每个 Prompt 前先 git pull --ff-only origin dfg-v2，读取最新的 PROMPTS.md；本文档可能在两个 Prompt 之间被修订。

## 已确定的决策（Prompt 0 审查之后）
- L1（Prompt 2）的新分析路径使用 scripts/DFG/state/stage_k/profile.py::SupportedSourceView 及源码清单中已绑定的版本元数据；旧标量对照仍使用原 SourceView 和原 pipeline。
- L2/L3（Prompt 3/4）只需要 AST 身份映射，不需要词法作用域模式，使用 Prompt 3 第 0 部分定义的 ProjectionView。
- G* 只按内层验证选择（见 Prompt 8）。
- 训练 checkpoint 改用已有的 nested 格式 scripts/DFG/experiments/checkpoint.py，由 dfg_v2 包装 schema 与协议绑定；不使用 paper_checkpoint.py（见 Prompt 7）。
```

### 4.2 Prompt 0：侦察与基线核对（只读）

```text
# Prompt 0：侦察与基线核对（只读，不写算法代码）

目标：确认 v2 依赖的事实，产出 scripts/DFG/dfg_v2/RECON.md 与 recon.json。不修改任何已有文件。

## 1. 作者图清单
- 找出 R/AC 的作者合约级图和节点级（行级）图的本地路径、SHA256、节点数、边数、文件数：从 integration/rebuild.py::DEFAULT_MANIFEST 指向的 manifest 取，并与 Test_code/author_graph_audit/audit_author_graphs.py 中的 PAPER 常量（论文表 1）对照。
- 其余 5 类只记录作者图与源码目录的本地路径（参考 audit_author_graphs.py），写进 RECON.md 的"以后扩展"小节，不做后续检查。
- 每类每个任务统计节点类型、边类型、canonical 关系 (src_type, edge_type, dst_type) 的计数，并列出原节点的完整属性键集合（后面新增节点时需要）。
- 用已有源码清单确认图中每个 source_file 都能找到唯一的源码文件；对每个文件构建 Projector（不加边），统计 ordinary_nodes_checked 和文件级 Unsupported 原因的分布。
- 确认节点 ID 的类型（是否都是整数）。

## 2. 状态变量声明节点（L2 的锚点，最关键）
- 对每类每个任务：解析源码，列出所有 state_variable_declaration；通过 SourceView.mapping/compat_ids 与 Projector.by_ast，判断每个声明是否有对应的 HCG 节点（node_type 应为 new_variable）。
- 报告：声明总数、有节点的数量与比例、没有节点的样例（文件、行、文本）。合约级与节点级分开报告（节点级图是漏洞文件的子集，节点可能被裁剪过）。
- 如果任何类别的锚点比例低于 90%，在 RECON.md 第一段醒目写出，然后停止，等待用户决定。不要自行改成新增 state 节点。

## 3. 语句节点覆盖
- 统计每类 HCG 中有节点的 AST 语句类型（expression_statement、variable_declaration_statement、if_statement、for/while/do、return_statement、emit_statement、revert_statement、throw、modifier 体内语句、构造器体内语句、for 的 update 是否有独立节点），以及源码中这些语句没有节点的数量。
- 用 tree-sitter 打印 legacy 写法 `var acc = Acc[msg.sender];` 在当前 grammar 中的 AST 结构（字段名、子节点类型），写进 RECON.md，Prompt 2 会用到。

## 4. token 特征的来源（L3 新节点需要）
- 阅读 scripts/encode_tokenizer_features.py、scripts/encode_llm_tokens.py、scripts/review_tokenizer_features.py、scripts/verify_token_interface.py，确定作者图 token 属性的生成方式：tokenizer 名称、输入文本取哪个节点属性、是否加特殊 token、长度、填充值、dtype。
- 按确定的方式，对每类随机 200 个节点（seed=0）重新编码，与图中的 token 逐元素比较，报告完全一致的比例。
- 不是 100% 就写出差异样例并停止，等待用户决定。

## 5. 训练协议现状
- 阅读 scripts/DFG/experiments/paper_run.py（fit_variant、effective_config、nested_config）、paper_runtime.py（Supervision、validate_registration）、protocol.py（make_fold_document、paired_initialize）、freeze_splits.py、e23_cv/prepare.py（seeds、select_split）、overall_cv/prepare.py。
- 写出每个任务的：优化器、学习率与调度器参数、最大轮数、早停规则、best 选择规则、损失函数、折文件位置与格式、是否已有内层验证列表、种子派生方式。
- 写出 R/AC 四个任务的冻结折文件与标签文件路径，以及折文件中是否已有内层验证列表。

## 6. 现有覆盖基线
- 用 integration/pipeline.py::build_graph(profile="scalar") 在 R/AC 四个任务上跑一遍，输出到 scripts/DFG/experiments/artifacts/dfg_v2/recon/（新目录）。
- 统计：函数总数、支持数、回退原因 Top 10（按原因字符串聚合）、DATA_DEF_USE 边数。这是 L1 扩展的对照基线。

## 7. 耗时与显存
- 从 artifacts/paper_kfold/guard_extension_v1 与 overall_cv_v1 的记录中，统计每次 fit 的耗时（按任务分组的中位数）和显存峰值，用于后续估算。

## 验收
RECON.md 回答以上 7 项，每项给出数字和证据文件路径；recon.json 机器可读；已跟踪文件中除 dfg_v2/ 与三份记录文档外没有改动。

（状态：2026-10-23 已完成并验收，提交 085eb86。）
```

### 4.3 Prompt 1：骨架、模型输入与模型构造

```text
# Prompt 1：dfg_v2 骨架、关系注册、模型输入与模型构造

前置：Prompt 0 验收通过。

本步不做任何程序分析。先把"带任意 v2 关系的图 → DGL 异构图 → 原 HGT"这条路打通并测试好，后面每一层只需要往图上加边。

## 1. dfg_v2/__init__.py
定义：
- VERSION = "dfg-v2"
- 共享上下文中的全部关系常量与 ENV_SOURCE
- PROFILES（dict：名称 → frozenset(关系)）
- FORWARD_RELATIONS（四个正向关系）
- REVERSE_OF（正向 → REV_ 名称）
- AUX_NODE_TYPES = frozenset({ENV_SOURCE})

## 2. dfg_v2/model_input.py
- edge_data(nx_graph)：直接调用 sco_models.graph_utils.generate_hetero_graph_data，返回 canonical → (src_tensor, dst_tensor)。
- materialize(edge_data, profile)：
  a. edge_type 不属于 v2 关系的部分，交给原 sco_models.graph_utils.reflect_graph 处理（与 G0 历史行为完全一致）。
  b. 该 profile 允许的 v2 正向关系原样加入，不反射。
  c. profile 为 G3R 时，对每个正向 v2 canonical (s, R, t)，加入 (t, REV_R, s)，端点交换。
  d. 以下情况直接报错：canonical 冲突；输入中出现 REV_* 边；出现不属于该 profile 的 v2 关系。
- build_dgl(nx_graph, profile, device)：
  - 参考 scripts/DFG/state/stage_f/model_adapter.py::build_dgl。
  - num_nodes_dict 用 sco_models.graph_utils.get_number_of_nodes。
  - 断言每个节点的类型内行号等于 node_hetero_id。

## 3. dfg_v2/model.py
- class DfgV2NodeClassifier(HGTVulNodeClassifier) 与 class DfgV2GraphClassifier(HGTVulGraphClassifier)。
  - 以 scripts/DFG/experiments/e23_pilot/model.py::_construct 为参考重写构造函数（不要用 FunctionType 重绑）。
  - 与参考实现的差别只有：用 model_input.build_dgl 构图；记录 self.dfg_profile；支持 node_feature ∈ {"inside_token", "nodetype"}。
  - 模块创建顺序和随机数消耗顺序必须与 _construct 一致（adapt_ws → gcs → classify），这样同 seed 下 G0 与历史模型的初值相同。
- 辅助节点的处理：
  - 节点任务：self.supervised_node_mask 只包含不在 AUX_NODE_TYPES 中的节点。
  - 合约任务：重写 self.node_ids_by_filename，排除辅助节点，原 forward 的 mean 池化因此不含它们。
  - G0/G1/G2 没有辅助节点，结果应与原实现一致。
- make_model(task, graph_or_path, profile, device, node_feature="inside_token", hidden_size=128, layers=2, heads=8, reducer="mean")
- reducer="nonempty_mean" 只用于诊断组：
  - 在 dfg_v2/hgt_layer.py 中实现 class HGTLayerNonEmptyMean(HGTLayer)。
  - forward 除跨关系聚合外，与原 HGTLayer.forward 逐行相同。
  - 跨关系聚合改为：对该节点入度 > 0 的 canonical 关系求平均；所有关系入度都为 0 的节点，消息为 0。
  - 实现方式：cross_reducer="stack"，再按每个 canonical 的入度掩码求和、除以计数。
  - 模型构造时，按 reducer 选择 HGTLayer 或 HGTLayerNonEmptyMean 填入 gcs（模块顺序不变）。

## 4. dfg_v2/supervision.py
class DfgV2Supervision：接口与 scripts/DFG/experiments/paper_runtime.py::Supervision 相同（targets、forward、manifest、mask、full_ids）。
- 节点任务：mask 额外要求节点类型不在 AUX_NODE_TYPES 中。
- 合约任务：不变（池化已经排除了辅助节点）。

## 5. 测试
文件：scripts/DFG/dfg_v2/tests/test_model_input.py、test_model.py
测试图：用 scripts/DFG/tests/fixtures/minimal.sol，经原生成器 process_graphs.tree_sitter_codeviews.generator.generate_cfg_from_source 建一个小 HCG；token 用 512 维全零向量。
- G0：materialize 的结果与 reflect_graph(generate_hetero_graph_data(g)) 完全相同（键顺序与张量逐元素）。
- 手工加两条 DATA_DEF_USE 边（端点同类型、不同类型各一条）：G1 中它们是单向的。再写一条测试固化"原 reflect 路径下同类型那条会变成双向"这一事实。
- G3R：每个正向 canonical 都有对应的 REV_，端点交换；冲突输入报错。
- 手工加一个 env_source 节点和一条 ENV_FLOW 边：节点监督 mask 不含它；合约池化的行不含它；新节点类型有自己的 adapt_ws。
- 前向与反向传播可运行；v2 关系的 relation_msg 有非零梯度。
- 同 seed 下，用 make_model 构造的 G0 模型，与 e23_pilot.model.make_model 构造的模型，state_dict 逐张量相等。
- nonempty_mean：构造一个每个目标节点在每个 canonical 关系上都有入边的小图，HGTLayerNonEmptyMean 与 HGTLayer 输出一致（误差 ≤ 1e-6）；再构造一个有零入度关系的图，验证分母只计入度 > 0 的关系。

## 验收
测试全部通过；PROGRESS.md 列出每个测试覆盖的性质。
```

### 4.4 Prompt 2：L1 函数内定义—使用的扩展

```text
# Prompt 2：L1 函数内定义—使用的扩展

目标：在不修改旧标量模块的前提下，把 DATA_DEF_USE 的覆盖范围扩大到：
  (a) 带一个前缀 modifier 的函数；
  (b) 含有 struct、数组、mapping 引用、string、bytes、var 类型局部变量或参数的函数。
旧标量层已支持的函数，输出必须与旧版逐条相同。

## 1. 符号表 dfg_v2/l1_symbols.py
class ExtendedSymbolTable(SymbolTable)（父类在 scripts/DFG/symbol_table.py）。
- 覆盖 _add：先尝试原来的 _scalar_type；失败时，如果是以下类型，就照常登记（kind 仍为 parameter/return/local，type_name 为源码文本）：
  - 用户定义类型（struct/contract/enum 名）、数组 T[] / T[k]、mapping、string、bytes；
  - var（legacy 写法，没有显式类型，只在 legacy 模式允许，type_name="var"。AST 结构见 RECON.md 第 3 项）；
  - 带数据位置（memory/storage/calldata）的声明，记录位置。
  - 函数类型和其他无法识别的类型仍然 Unsupported。
- Symbol 是 frozen dataclass，不要修改它的定义。把附加信息放在 self.aggregate_info：symbol_id → {"aggregate": bool, "location": str 或 None, "type": str}。
- modern 模式下初始化表达式自引用的检查保持原样。

## 2. 读写提取 dfg_v2/l1_access.py
- 在 dfg_v2/l1_models.py 中新定义 frozen dataclass V2Event：id、function、anchor、reads、writes、weak_writes、kind。
- class ExtendedAccessExtractor(AccessExtractor)，产出 V2Event。targets(node) 的规则：
  - identifier：强写（原规则）。
  - member_expression / array_access 链：取链根标识符 r。
    - r 解析到 aggregate 符号：r 记为弱写；r 本身和链上所有 index 表达式记为读（x[i] = v 读 i；x.f[i] += v 读 x 和 i）。
    - r 不是本地符号（状态变量或未知名字）：只记读，不产生定义（原规则）。
  - tuple_expression：逐个元素处理；重复目标仍 Unsupported（原规则）。
- 调用 x.push(v) / x.pop()：链根是 aggregate 局部时，记弱写 + 读；否则只记读。
- delete x.f / delete x[i]：链根是 aggregate 局部时记弱写。delete x（整体）记强写。
- 其余表达式沿用 AccessExtractor.reads 的规则；嵌套写、嵌套 delete 仍 Unsupported（整函数回退）。
- aggregate 局部作为参数传给任何调用：只记读。在 PROGRESS.md 中写明这是近似处理（memory 引用传给内部函数后可能被修改）。

## 3. CFG 构建 dfg_v2/l1_cfg.py
class V2CFGBuilder(StageJCFGBuilder)：
- 用 ExtendedSymbolTable 和 ExtendedAccessExtractor 替换 table 和 access；modifier 前缀、ClosedScopeJ、StageFCallResolver 以及语句、循环、分支的构造全部沿用。
- StageJCFGBuilder.__init__ 中直接 new 了 SymbolTable 与 AccessExtractor，因此 V2CFGBuilder 需要按父类的顺序重写 __init__，并在每一处与父类不同的行加注释。
- StageJCFGBuilder 需要 StageFSourceView。统一使用 scripts/DFG/state/stage_k/profile.py::SupportedSourceView；构造失败的文件，退回旧的 frontend.parse_source + 旧 CFGBuilder（只为保住旧的标量结果），并在审计中标出。

## 4. 到达定义 dfg_v2/l1_rd.py
- solve_v2(ir, max_iterations)：复制 scripts/DFG/reaching_definitions.py::solve 的算法，文件头注明来源路径与 SHA256。
- 新增的处理：weak_writes 产生新定义，但不 KILL 同一符号的其他定义；块内按事件顺序重放时同样处理。
- IR 校验要同时检查 weak_writes 引用的符号。
- 等价性测试：对所有 weak_writes 为空的 IR，solve_v2 的 facts、in/out 集合、iterations 与原 solve 完全相同。测试中用 fixtures 验证；真实数据验收时在 R/AC 四个任务的全部旧支持函数上再跑一次。

## 5. 分析与投影 dfg_v2/l1.py
analyze_file(source, file, metadata, max_iterations) -> (facts, diagnostics, stats)：
- 先用旧路径（scripts/DFG/ddg_builder.py::DDGBuilder.analyze_source）得到旧结果。
- 对旧路径回退的函数，用 V2CFGBuilder + solve_v2 重试。成功就合并事实，并记录 route ∈ {legacy, v2_modifier, v2_aggregate, v2_both}。
- 旧路径成功的函数不重新计算（保证超集性质）。

augment_l1(graph, sources, metadata, max_iterations) -> (graph, audit)：
- 投影与边的物化复用 scripts/DFG/projection.py::Projector 和 DDGBuilder.projected_edges 的规则：同端点合并为一条、不加自环、保留 ddg_fact_indices 属性。
- 边属性另加 dfg_v2_version 和 routes（route 列表）。

## 6. 测试 scripts/DFG/dfg_v2/tests/test_l1.py（使用真实 tree-sitter 解析）
每条断言写成 (定义语句文本 → 使用语句文本, 变量名)，并断言不应出现的边确实不存在。

a) 论文图 1 MY_BANK.Collect（pragma ^0.4.25）：
   struct Holder { uint unlockTime; uint balance; }
   mapping(address => Holder) public Acc;
   uint public MinSum;
   function Collect(uint _am) public payable {
       var acc = Acc[msg.sender];
       if (acc.balance >= MinSum && acc.balance >= _am && now > acc.unlockTime) {
           if (msg.sender.call.value(_am)()) {
               acc.balance -= _am;
           }
       }
   }
   期望的边：
   - var acc 声明 → 外层 if（acc）
   - var acc 声明 → acc.balance -= _am（acc）
   - 函数入口 → 外层 if（_am）
   - 函数入口 → 内层 if（_am）
   - 函数入口 → acc.balance -= _am（_am）
   另外断言：acc.balance -= _am 是 acc 的弱定义；旧路径对这个函数没有任何边。

b) 弱定义不 KILL：
   S memory s = S(1, 2);  s.a = 3;  uint y = s.b;
   期望 decl(s) → y 声明，以及 s.a = 3 → y 声明，两条都存在。

c) 整体赋值 KILL：在 b) 之后加 s = S(4, 5); uint z = s.a;
   期望 z 只连到 s = S(4, 5) 这一条。

d) storage 数组 push：
   uint[] storage arr = data; arr.push(1); uint n = arr.length;
   期望 decl(arr) → n 声明，以及 arr.push(1) → n 声明。

e) 单个前缀 modifier：
   modifier onlyOwner { require(msg.sender == owner); _; }
   function f(uint x) public onlyOwner { uint y = x; return y; }
   期望：函数入口 → uint y = x；uint y = x → return y。旧路径对该函数没有边。

f) string 参数：
   function g(string memory s, uint n) public returns (uint) { uint k = n; return k; }
   旧路径整函数回退，新路径有边。

g) 仍然回退的情况：含 assembly、嵌套赋值、两个 modifier 的函数仍回退，且没有残留事实。

h) 超集：对 scripts/DFG/tests/fixtures 中旧标量测试用过的所有合约，L1 的边集合包含旧 DATA_DEF_USE 的边集合，且在旧支持函数上完全相等。

## 7. 真实数据验收（不训练）
在 R/AC 四个任务上构建 G1 图，输出到 artifacts/dfg_v2/l1_build/：
- 旧支持函数上的边与 integration 的 scalar 剖面逐边一致，不一致即失败。
- 报告：函数支持率（前 → 后）、route 分布、新增边数、新的 canonical 关系、回退原因 Top 10 的变化。
完成后更新 PROGRESS.md 并提交。
```

### 4.5 Prompt 3：L2 状态变量中转关系

```text
# Prompt 3：L2 状态变量中转关系 WRITES_STATE / READS_STATE

前置：Prompt 0 中状态变量声明节点的锚点比例 ≥ 90%（已满足：SupportedSourceView 口径 R 合约 99.62%、AC 合约 94.58%、两个节点任务 100%）。

## 0. 不依赖作用域模式的投影视图 dfg_v2/projection_view.py
背景：Prompt 0 中 R 合约 2 个文件、AC 合约 6 个文件仍无法构造 SupportedSourceView，原因全部是"no version evidence for lexical scope"或"interval crosses lexical scope boundary"。这两个原因只影响 legacy/modern 作用域判断（L1 需要），不影响 AST 身份映射。L2 的名字绑定是保守的（见第 2 部分），L3 只识别环境量，都不需要作用域模式。
- class ProjectionView(SourceView)：复制 scripts/DFG/frontend.py::SourceView.__init__，只去掉 scope_mode 调用并令 self.mode = None；文件头注明来源与原 SHA256。保留"预处理改变可执行 token 即 Unsupported"的检查，以及 raw/compat 映射构造的全部逻辑。
- 只在 L2/L3 中使用；L1 不得使用（L1 依赖作用域模式）。
- 测试：
  - 在 R/AC 四个任务中 SourceView 能构造成功的全部文件上，ProjectionView 的 mapping、compat_ids、compat_nodes 与 SourceView 完全相同；
  - 用 ProjectionView 重新统计 Prompt 0 第 2 项的锚点比例，写进 PROGRESS.md（预期这 8 个文件的状态声明能锚定，但以实测为准）；
  - 对 ProjectionView 仍失败的文件列出原因。

目标：用 HCG 中已有的状态变量声明节点（node_type=new_variable，来自 state_variable_declaration）作为中转点，把写某个状态变量的语句和读它的语句连起来，包括跨函数的情况。这一层不做流分析，也不依赖 L1 是否成功分析了该函数。

## 1. 语句单元 dfg_v2/units.py
statement_units(view, projector) -> list[Unit]，其中 Unit = (hcg_node_id, ast_node, regions)。view 为第 0 部分的 ProjectionView。
- 遍历源码 AST 中所有在 HCG 有对应节点的 AST 节点：raw 节点 → view.mapping → compat key → view.compat_ids → projector.by_ast。
- regions 是该节点"自己的"表达式区域：
  - expression_statement / variable_declaration_statement / return_statement / emit / revert / throw：整个节点。
  - if_statement：只有 condition。
  - for_statement：initial、condition、update 中没有独立 HCG 节点的部分（Prompt 0 已确认 update 是否有独立节点；有就归它自己）。
  - while / do：condition。
  - function_definition / constructor_definition / modifier_definition：modifier_invocation 的实参；函数体不算。
  - state_variable_declaration：初始化表达式。
- 不进入本身有 HCG 节点的子语句，也不进入 block。
- 源码中有读写、但所在语句没有 HCG 节点的（例如作者图中的 emit/revert），计入 unmapped，不挂到其他节点上。
- 单元测试：if/else、for、嵌套 if、modifier、状态变量初始化各一个，断言 regions 精确。

## 2. 名字绑定 dfg_v2/state_binding.py
class StateBinder（每个 callable 一个实例）：
- 局部判定（保守）：该 callable 的参数名、返回值名、函数体内任何 variable_declaration 的名字、modifier 的参数名，都视为局部，不当作状态变量——即使出现位置在声明之前（宁可漏边）。不要求 SymbolTable 能构造成功。
- 状态判定：名字不是局部时：
  - 先用 state/stage_j/binding.py::ClosedScopeJ(view, callable).members[name]，结果必须恰好是一个 state_variable_declaration；
  - ClosedScopeJ 抛 Unsupported（import、继承不一致等）时，退回到"当前合约体内恰好一个同名 state_variable_declaration"；
  - 都不满足就记为 unresolved，跳过这一处出现。
- 只处理裸标识符 x，以及成员/下标链的根 x。this.x、Contract.x、作为成员属性的 x（a.x 中的 x）都不算。
- constant 状态变量默认跳过（配置项 include_constants=False）。

## 3. 读写分类 dfg_v2/state_access.py
在每个 Unit 的 regions 内分类：
- 写（WRITE）：
  - assignment_expression 左侧链的根；
  - augmented_assignment_expression 左侧链的根（同时也是 READ）；
  - update_expression（++/--）参数链的根（同时也是 READ）；
  - delete 参数链的根；
  - 成员调用 x.push(...) / x.pop() 的链根（同时也是 READ）；
  - 元组左侧的每个元素。
- 通过 storage 引用的别名：callable 内某个局部 p，如果满足下面任一条件：
  (a) 声明带 storage；
  (b) legacy 模式下声明没有数据位置（包括 var），类型是 struct、数组或 mapping 值类型；
  并且 p 的初始化表达式（或之后整体赋值的右侧）的链根是状态变量 S，那么：
  - 对 p 的成员/下标写，记为对 S 的 WRITE（via_alias=True）；
  - 对 p 的成员/下标读，记为对 S 的 READ（via_alias=True）。
  - 一个 p 可以对应多个 S，取并集。memory/calldata 局部不建立别名。
- 读（READ）：region 内对状态变量的其余出现，包括下标表达式中的状态变量。

## 4. 加边 dfg_v2/l2.py
augment_l2(graph, sources, metadata, include_constants=False) -> (graph, audit)：
- 每个 (Unit, S, WRITE)：边 Unit 节点 → decl(S)，edge_type=WRITES_STATE。
- 每个 (Unit, S, READ)：边 decl(S) → Unit 节点，edge_type=READS_STATE。
- decl(S) 是 S 的 state_variable_declaration 对应的 HCG 节点；没有对应节点就记为 anchor_missing 并跳过。
- 每个 (src, dst, relation) 只保留一条边。边属性：dfg_v2_version、state_vars（排序后的名字列表）、via_alias（是否有任何一处经过别名）、evidence_indices。
- 不加自环（声明自身的初始化不算对自己的写）。
- 审计记录：每个文件的 callable 数、单元数、READ/WRITE 出现数、unresolved/unmapped/anchor_missing/alias 数，按关系统计的新增边数，canonical 计数。

## 5. 测试 scripts/DFG/dfg_v2/tests/test_l2.py
a) 跨函数重入（reentrancy_simple，pragma ^0.4.24）：
   mapping(address => uint) userBalance;
   function addToBalance() public payable { userBalance[msg.sender] += msg.value; }
   function withdrawBalance() public {
       if (!(msg.sender.call.value(userBalance[msg.sender])())) { throw; }
       userBalance[msg.sender] = 0;
   }
   期望：
   - addToBalance 的语句 → decl(userBalance)（WRITES）
   - decl → addToBalance 的语句（READS，因为是 +=）
   - decl → withdrawBalance 中的 if（READS）
   - withdrawBalance 中的赋值 → decl（WRITES）
b) MY_BANK.Collect（与 Prompt 2 的 a 相同）：
   - acc.balance -= _am → decl(Acc)（WRITES，via_alias）
   - decl(Acc) → var acc 声明（READS）
   - decl(MinSum) → 外层 if（READS）
c) 访问控制：
   address owner;
   function changeOwner(address o) public { require(msg.sender == owner); owner = o; }
   期望：decl(owner) → require 语句；owner = o → decl(owner)。
d) modifier：modifier onlyOwner { require(msg.sender == owner); _; }
   期望：decl(owner) → modifier 中的 require 语句。
e) 遮蔽：函数参数名与状态变量同名时，不产生边。
f) 继承：contract A { uint x; }  contract B is A { function f() public { x = 1; } }
   期望：B.f 中的语句 → A 中 x 的声明节点。
g) memory 拷贝：S memory m = st; m.a = 1;
   期望：不产生对 st 的 WRITES，但有 decl(st) → 声明语句的 READS。
h) 常量：uint constant C = 1; 读取 C 不产生边。
i) L1 回退的函数（例如含 assembly）仍然能产生 L2 边。

## 6. 真实数据验收
在 R/AC 四个任务上构建 G2（= G1 + L2），输出到 artifacts/dfg_v2/l2_build/：
- 不变量全部通过（原节点、原边不变，只多出 v2 关系）。
- 报告每类：状态变量声明数、锚点命中率、WRITES/READS 边数、跨函数连通对数（同一个 decl 的写语句与读语句位于不同 callable 的对数）、经别名的边的比例、unresolved 原因分布。
- 固定 seed=0 抽 20 条边，打印两端代码，写进 PROGRESS.md 供人工检查。
```

### 4.6 Prompt 4：L3 环境源

```text
# Prompt 4：L3 环境源 ENV_FLOW 与 env_source 节点

前置：Prompt 0 第 4 项（token 重编码一致率）为 100%。

## 1. 环境键 dfg_v2/env.py
ENV_KEYS（固定顺序）：msg.sender, msg.value, msg.data, msg.sig, tx.origin, tx.gasprice, block.timestamp, now, block.number, block.difficulty, block.coinbase, block.gaslimit, blockhash, gasleft, this.balance。
识别规则（在 Prompt 3 的 Unit regions 内）：
- member_expression，对象是 msg/tx/block，属性在上表中 → 对应的键。
- 标识符 now → now；调用 blockhash(...) 或 block.blockhash(...) → blockhash；gasleft() → gasleft；this.balance 与 address(this).balance → this.balance。
- 遮蔽：msg/tx/block/now/blockhash/gasleft 在该 callable 的局部、合约成员（ClosedScopeJ.members）或文件顶层声明中有同名时，跳过并记为 shadowed。

## 2. 节点与边 dfg_v2/l3.py
augment_l3(graph, sources, metadata, token_encoder) -> (graph, audit)：
- 每个文件中，每个实际出现的键建一个节点，属性：
  - node_type = "env_source"
  - source_file = 该文件
  - label = "ENV:<键>"
  - code = <键>
  - node_info_vulnerabilities = None
  - node_source_code_lines = []
  - token = token_encoder(code)（方式与 Prompt 0 确定的完全一致，dtype 与长度相同）
  - method = ""
  - type_label = "env_source"
  - dfg_v2_aux = True
  Prompt 0 确认原节点属性键恰好是 code、label、method、node_info_vulnerabilities、node_source_code_lines、node_type、source_file、token、type_label；新节点必须包含这 9 个键（外加 dfg_v2_aux），测试中断言键集合。
  token 生成方式按 Prompt 0：对 code 文本先用 Salesforce/codet5p-770m tokenizer（离线、固定 revision）以 add_special_tokens=True 完整编码，再用 scripts/encode_tokenizer_features.py::encode_ids 截取前 512 个 ID、右侧补 0、float32[512]。不要改用 truncation=True。
  view 使用 Prompt 3 第 0 部分的 ProjectionView。
- 节点 ID：在原图最大整数 ID 之后，按 (source_file, ENV_KEYS 顺序) 依次分配。如果原图的 ID 不是整数，停下报告。
- 边：env 节点 → Unit 节点，edge_type=ENV_FLOW，每对一条；属性 dfg_v2_version、env_key、evidence_indices。
- 必须在 L1、L2 之后执行（Projector 会拒绝没有 AST 锚点的节点）。此后任何对 Projector 的调用，都要先过滤掉 env_source 节点。

## 3. token_encoder dfg_v2/tokens.py
按 Prompt 0 的结论封装，离线加载 tokenizer（local_files_only=True），同一输入的输出必须确定。
测试：对原图中 20 个节点用它编码，与原 token 完全相同。

## 4. 测试 scripts/DFG/dfg_v2/tests/test_l3.py
a) require(msg.sender == owner)：有 ENV_FLOW(msg.sender → 该语句)；同时 L2 有 decl(owner) → 该语句。
b) require(tx.origin == owner)：产生 tx.origin 节点。
c) if (now % 15 == 0) 与 if (block.timestamp > deadline)：产生 now 和 block.timestamp 两个节点，分别连到各自的 if。
d) 参数名为 now（或 grammar 允许的其他遮蔽写法）：被遮蔽，不产生边。
e) 同一文件中多处 msg.sender 只建一个节点；不同文件各自建一个。
f) 把 G3 图送入 Prompt 1 的模型：env_source 不在节点监督 mask 中，也不在合约池化的行中；新节点类型有梯度。
g) 原节点的 node_hetero_id、各原节点类型内的行顺序都不变。

## 5. 真实数据验收
在 R/AC 四个任务上构建 G3，输出到 artifacts/dfg_v2/l3_build/：
- 报告每类每个键的节点数、ENV_FLOW 边数、遮蔽数；
- 不变量全部通过。
```

### 4.7 Prompt 5：统一构图入口、任务注册表与输入清单

```text
# Prompt 5：统一构图入口、任务注册表、输入清单与构图审计

## 1. dfg_v2/pipeline.py
build(graph, sources, metadata, profile, token_encoder=None, max_iterations=100000) -> (graph, audit)
- profile 必须在 PROFILES 中。G0 返回深拷贝，fingerprint 与输入相同。
- 执行顺序：L1（G1 及以上）→ L2（G2 及以上）→ L3（G3 及以上）。
- G3R 的 NetworkX 图与 G3 完全相同；反向关系只在 model_input.materialize 中生成。在 audit 中写明 materialize_reverse=True。
- 结束时检查：
  - 原节点、原边不变；
  - v2 关系没有自环、没有重复；
  - 每条 v2 边都能追溯到 evidence；
  - 没有跨文件的边；
  - env_source 节点只出现在 G3/G3R。
- audit 字段：版本、profile、各层统计、输入/输出 fingerprint、computation_fingerprint（复用 integration/pipeline.py）、源码 SHA、labels_used_for_analysis=False。

## 2. 任务注册表与输入清单 dfg_v2/tasks.py、dfg_v2/inputs.py
- tasks.py：任务注册表，每个类别一条记录，字段为类别名、合约级与节点级作者图路径和 SHA、源码清单、标签文件、折文件。现在只填 reentrancy 与 access_control；其余 5 类（arithmetic、denial_of_service、front_running、time_manipulation、unchecked_low_level_calls）只在注释中列出。任务名格式 <类别>_<contract|node>。
- inputs.py：按注册表为选中的任务生成 artifacts/dfg_v2/inputs/manifest.json，内容包括原 HCG 的路径与 SHA、源码清单（file → path, sha256, metadata）、标签文件、折文件。R/AC 一律用已冻结的折与标签。
- 为以后扩展预留：inputs.py 提供 make_folds(category)，内部调用 scripts/DFG/experiments/freeze_splits.py 的同一个函数与同样的参数（seed=1, inner_fraction=0.2）。现在不对其余 5 类运行它。若 Prompt 0 确认 R/AC 的冻结折就是由该函数生成，测试它能逐文件复现；否则只测试它能对 R/AC 生成合法折文件，并在 PROGRESS.md 记录差异。
- 清单生成后写 manifest.seal.json（记录 SHA）。之后的步骤只读这个清单。
- 写 scripts/DFG/dfg_v2/EXTENDING.md：新增一类的五个步骤（注册 → Prompt 0 中该类的锚点与 token 核对 → 生成并封存折 → cli build --tasks → run plan --tasks），并写明不需要改任何分析或模型代码。

## 3. 命令行 dfg_v2/cli.py
python -B -m scripts.DFG.dfg_v2.cli build --manifest <清单> --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node --profiles G0,G1,G2,G3 --output <新目录>
（--tasks 默认就是这四个任务。）
- 输出 <output>/<task_id>/<profile>/hcg.gpickle 与 audit.json；拒绝覆盖已有目录。
- 写 <output>/build_summary.csv，列：task_id, profile, nodes, edges, 每个 v2 关系的边数, 新 canonical 数, 函数支持率, 锚点命中率, 耗时。

## 4. 测试
- G0 的 fingerprint 与输入相同。
- G1 ⊆ G2 ⊆ G3（按 (src, dst, edge_type) 比较边集合）。
- 同一输入重复构建，computation_fingerprint 相同（确定性）。
- 缺源码的文件保留原图，并在 audit 中列出。
- 接口通用性：在注册表中临时注册一个虚构类别（复用 R 的 3 个文件改名），走完 注册 → 构图 → make_model 前向，证明代码不依赖类别名；该测试不写入正式注册表。
- make_folds 的测试见本节第 2 条。

## 5. 验收
R/AC 四个任务 × 4 个剖面全部构建成功；build_summary.csv 写入 PROGRESS.md；不变量全部通过。
```

### 4.8 Prompt 6：正确性验证

```text
# Prompt 6：依赖正确性验证（Oracle + Slither + 人工抽查表）

本步只做验证，不修改分析算法。发现的错误记下来，修复放到单独的 Prompt 6b，修复后重新运行本步。

## 1. 手写 Oracle（先封存期望，再运行）
在 scripts/DFG/dfg_v2/oracle/ 下放 12–16 个最小合约。覆盖 Prompt 2/3/4 测试中的例子，并补充：
- for 循环中的 i++
- if/else 合流
- 循环回边
- return 之后的不可达语句
- tuple 赋值
- 状态变量的初始化表达式
- 两个合约的继承
- storage 别名被重新赋值

每个合约配一个 expected.json，列出期望的 (relation, src 语句文本, dst 语句文本, 变量)。先单独提交 expected.json（一次独立的 commit），再运行比较，避免看到结果后改期望。
报告精确率、召回率和不一致清单。

## 2. Slither 对照（只在可编译的子集上做，可选）
脚本 scripts/DFG/dfg_v2/validate_slither.py：
- 先检查 slither-analyzer（requirements.txt 中是 0.8.0）与 solc-select 是否可用，离线是否有所需的 solc 版本（版本选择参考 auto_version_solc.py）。不可用就写明原因并跳过，不要联网安装。
- 对每个可编译的合约，取 Slither 每个 CFG 节点的 state_variables_read / state_variables_written / local_variables_read / local_variables_written 以及源码行号。
- 对照粒度（只用于本验证，不进入构图）：
  - 按"语句起始行 + 变量名"比较 L2 的 READ/WRITE 出现集合；
  - 按同样粒度比较 L1 的 def/use 出现集合。
  注意 Slither 基于原始源码行号，HCG 基于预处理后的行号；用 SourceView 的 raw 视图行号对齐。
- 报告每类的精确率、召回率，前 20 个不一致样例，并按原因分类（grammar 差异、别名、继承、内联汇编、modifier 内联方式等）。
- Slither 会把 modifier 内联，也会把 storage 引用的写算到状态变量上。统计时把这两类分开列出。

## 3. 人工抽查表
从 R、AC 两类中各随机抽 15 个合约（seed=0）；每个合约每种关系最多抽 5 条边，导出 CSV，列为：
task, file, relation, src_line, src_code, dst_line, dst_code, vars, via_alias, 判定（留空）, 备注（留空）
供用户人工标注。

## 4. 验收
- Oracle 全部通过，或者每个不一致项都有归因；
- Slither 对照有结果，或者有明确的跳过原因；
- 抽查表已生成。
```

### 4.9 Prompt 7：训练接入与小规模验收

```text
# Prompt 7：训练接入、嵌套协议与小规模验收（不跑正式矩阵）

## 1. 训练器 dfg_v2/experiment/trainer.py
- 复用 scripts/DFG/experiments/paper_run.py::fit_variant 的数值规则：优化器、学习率与调度、最大轮数、patience、delta、损失、best = 验证损失严格最小、last 另存。
- fit_variant 依赖 paper_runtime 的 Supervision、validate_registration、gradient_audit，以及 paper_checkpoint 的 StopMonitor、snapshot_input、save_checkpoint、restore_checkpoint。其中有些按原 reflect_graph 检查 schema，与 v2 不兼容（逐个检查，在 PROGRESS.md 列出哪些需要替换）。不要用 FunctionType 重绑。做法是：
  - 把 fit_variant 复制为 trainer.fit，文件头注明来源路径与 SHA256；
  - 只替换与 schema 和协议有关的依赖：Supervision → DfgV2Supervision；validate_registration → dfg_v2 版本（按 model_input.materialize 检查 canonical 与端点）；paper_checkpoint 的 save/restore/validate_binding → dfg_v2/experiment/checkpoint.py。
  - paper_checkpoint.py 不能用于 nested：它的 validate_binding 写死了 paper_protocol 的 NAME/VERSION/FORWARD_SCOPE/SCORE_ROLE（paper_kfold、CV validation），并调用基于原 reflect_graph 的 paper_runtime.validate_registration。
  - 改为复用已有的 scripts/DFG/experiments/checkpoint.py（格式 ddg-controlled-v1，monitor 字段即 best_inner_val_loss，save/restore 本身不绑定协议名）：直接 import 其 StopMonitor、save_checkpoint、restore_checkpoint、snapshot_input。
  - dfg_v2/experiment/checkpoint.py 只做一层包装：保存前和恢复后调用 dfg_v2 的 validate_registration 与 binding 校验；binding 字典包含 dfg_v2 协议名与版本、score_role="outer_test"、selection_role="inner_val"、profile、reducer、canonical 列表、辅助节点类型、输入图与折文件 SHA。
  - 其他依赖原样 import。
- 等价性测试（必须通过才能继续）：
  - 取 G0 图、R 合约 fold0 与 R 节点 fold0，使用 overall_cv_v1 保存的 HCG 未训练初值和 fit_seed，用新 fit 跑 3 轮；
  - 逐轮的训练与验证损失必须与原 fit 一致：在同一设备上，同时用原 fit 与新 fit 从同一初值跑 3 轮对比；CPU 上允许 1e-6 误差，GPU 上与历史 history.jsonl 的前 3 轮对比。

## 2. 嵌套协议 dfg_v2/experiment/protocol.py
- 外层折：沿用 Prompt 5 清单中的冻结折。
- 内层：从外层训练文件中取冻结的 inner 验证列表（protocol.make_fold_document 已生成），用于早停和选 best。外层测试折只在训练结束后，对 best 和 last 各评估一次。
- 输出指标：外层测试的 Buggy-F1、Macro-F1、Precision、Recall、混淆矩阵。节点任务排除辅助节点。
- 同时导出逐节点/逐文件的预测（带原图节点 ID），供配对比较与 OOF 统计使用。

## 3. 共同初值 dfg_v2/experiment/init.py
initialize_family(models, seed)，models 是 profile → model 的映射：
- 以 G0 模型为锚，所有剖面共有的参数（同名同形状）逐张量相同。
- 只在部分剖面存在的参数（新 canonical 的 relation_att/relation_msg/relation_pri，新节点类型的 adapt_ws、k/q/v/a_linears、norms、skip），用 seed 派生的独立随机数生成器确定性地初始化，分布与原 HGTLayer/HGT 构造时相同。
- 参考 scripts/DFG/state/stage_f/initialization.py::initialize_pair 推广到多个剖面。注意 initialize_pair 要求两边节点类型集合相同，而 G3 多了 env_source，需要扩展。
- HGTLayer 的 relation_* 张量第一维按 etypes_dict 排列，不同剖面中同一个 canonical 的下标可能不同；共享参数必须按 canonical 名和节点类型名对齐，不能按下标对齐。
- 测试：共有参数逐张量相等；重复调用结果相同；G0 不被修改。

## 4. 运行器 dfg_v2/experiment/run.py
命令：
  python -B -m scripts.DFG.dfg_v2.experiment.run plan --manifest <Prompt 5 清单> --build <Prompt 5 构图目录> --tasks <任务列表> --profiles <剖面列表> --seeds <种子列表> [--reducer mean|nonempty_mean] --output <新批次目录>
  python -u -B -m scripts.DFG.dfg_v2.experiment.run execute --plan <批次>/plan.json [--only task/fold/seed/profile]
  python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan <批次>/plan.json
  python -B -m scripts.DFG.dfg_v2.experiment.run select --plan <批次>/plan.json
  python -B -m scripts.DFG.dfg_v2.experiment.run summarize --plan <批次>/plan.json
- select 只读取内层验证指标，按 plan 中登记的规则写出并封存 selection.json（G* 与补种子是否触发）；summarize 在 selection.json 不存在时拒绝运行。
- plan：写死任务列表、剖面、种子、折、配置、输入 SHA，以及预先登记的选择规则（见 Prompt 8），然后写 plan.seal.json。
- --tasks 默认是 R/AC 四个任务，--seeds 默认是 1；任务名只从任务注册表读取，不在运行器里写死类别。
- execute：
  - GPU 串行，单进程锁；
  - 每个 job 一个目录（history.jsonl、best.pt、last.pt、predictions、receipt.json）；
  - 成功的 job 直接复用；失败的保留 attempt 并停止，需显式 --retry 才重跑；
  - 不自动降配、不改参数、不切换到 CPU；
  - 按 receipt 判断断点续跑。

## 5. 小规模验收（本步唯一允许的训练）
R 与 AC 各自的合约 fold0 与节点 fold0，剖面 G0 和 G3，seed 1，完整训练到早停，共 8 次；另加 R 合约 fold0 的 G3R 1 次作为显存探针（这是边数最多的任务与剖面；历史 guard 批次在该任务上已用到 reserved 3068MiB、整卡最低只剩 29MiB）。共 9 次。检查：
- 在训练文件中有边的新 canonical 关系，relation_msg 梯度非零；只出现在内层验证或外层测试文件中的 canonical 不要求梯度，单独列出其数量；
- env_source 不出现在任何指标和预测导出中；
- best/last 重新加载后 logits 逐位一致；
- 显存峰值（allocated/reserved）、整卡最低空闲与耗时写入 PROGRESS.md，用于估算 Prompt 8 批次 1。G3R 探针若 OOM 或整卡空闲低于 100MiB，停下报告，不自动降配。
不要报告这 9 次的 F1 比较结论。
```

### 4.10 Prompt 8：R/AC 实验与统计

先用 1 个种子跑 5 个剖面（150 次，约 7 小时），之后的诊断组和补种子都要你确认才跑；其余 5 类只写扩展说明。

```text
# Prompt 8：R/AC 实验与统计

前置：Prompt 6 与 Prompt 7 都验收通过。先在 PROGRESS.md 写出按 Prompt 7 实测耗时计算的预计总时长，等用户回复确认后再执行 execute。

## 批次 1：主矩阵（必跑）
- 任务：reentrancy_contract（5 折）、reentrancy_node（10 折）、access_control_contract（5 折）、access_control_node（10 折）。
- 剖面：G0、G1、G2、G3、G3R；种子只用 seed 1。
- 共 30 × 5 = 150 次。按 Prompt 7 实测耗时估算总时长（参考：此前在 RTX 3050 4GiB 上约 165 秒/次，约 7 小时）。
- 命令示例：run plan --tasks <四个任务> --profiles G0,G1,G2,G3,G3R --seeds 1 --output <新批次>

## 批次 2：聚合诊断（可选，批次 1 结束后由用户决定）
- G0M 与 G3M（分别是 G0 和 G3 配 reducer="nonempty_mean"），seed 1，共 60 次，约 2.8 小时。
- G3M − G0M 与 G3 − G0 的对比，用来区分"新关系的信息"与"跨关系平均分母变化"两种效应。

## 批次 3：补种子（由 selection.json 中预先登记的内层验证条件决定是否触发，再经用户确认执行）
- G0 与 G* 再跑 seed 2、3：2 × 2 × 30 = 120 次，约 5.5 小时。
- 所有种子用同一套冻结折；同一 (任务, 折, 种子) 下 G0 与 G* 共享初值。

## 可选组（用户确认后才跑）
node_feature="nodetype" 下的 G0 与 G3，seed 1，共 60 次。

## 预先登记的选择规则（写进批次 1 的 plan.json 后不能修改）
- G* = 四个任务的内层验证 Buggy-F1（每折取 best checkpoint 在内层验证集上的值，每个任务先对折取平均）的算术平均最高的剖面。候选只包括 G1、G2、G3、G3R。如果与第二名的差距小于 0.1pp，选关系更少的那个。外层测试分数不参与选择。
- 补种子触发：G* 与 G0 的四任务平均内层验证 Buggy-F1 之差的绝对值 ≥ 0.2pp。
- 由 run select 计算并封存 selection.json 后，才允许 summarize 输出外层测试结果。报告中五个剖面的外层测试结果全部列出，并注明 G* 的选择基于内层验证。

## 统计 dfg_v2/experiment/stats.py（任务列表由参数传入，不写死类别）
- 每个 (类, 任务, 剖面)：各折的均值 ± 样本标准差；多种子时先对折取平均，再报告种子间的均值 ± 标准差。best 为主表，last 另列一表。
- 配对比较：
  - 每个剖面 vs G0；另加 G3R vs G3；跑了批次 2 时加 G3M vs G0M。
  - 配对单位为折（多种子时为 (折, 种子)）。
  - scipy.stats.wilcoxon 双侧检验，零差值用 zero_method="zsplit" 并在报告中写明；同时报告 Vargha-Delaney A12，以及配对差的均值和 95% bootstrap 置信区间（10000 次，seed 0）。
  - 4 个"剖面 vs G0"的比较做 Holm 校正。
  - 合约任务只有 5 折，配对 Wilcoxon 的最小 p 值为 0.0625；单种子下合约任务只作描述性比较，报告中要写明。
- pooled OOF：把外层测试预测按任务汇总，计算一次总体 Buggy-F1 与 Macro-F1。
- 机制统计：每个任务中，G0 错而 G* 对的节点、以及 G0 对而 G* 错的节点，有多少落在 v2 新增关系的 1 跳/2 跳范围内，按关系分解。
- 标签争议文件（R buggy_18、R buggy_36、AC buggy_18、AC buggy_26，以及 artifacts/targeted_label_review_v1 中列出的文件）单独一张表；主表另给一个"排除这些文件"的敏感性结果。
- 输出 <批次>/REPORT.md（全部表格用 markdown）和对应的 CSV。

## 以后扩展到其余 5 类（现在不执行）
在 PROGRESS.md 末尾写一段说明，按 scripts/DFG/dfg_v2/EXTENDING.md 的步骤：注册新类别 → Prompt 0 中该类的锚点与 token 核对 → 生成并封存折 → cli build --tasks <新类> → run plan --tasks <新类> --profiles G0,<G*> --seeds 1。G* 沿用 R/AC 上按上面规则选出的剖面，不在新类别上重新挑选。

## 停止条件
- 任何 job 失败、显存溢出或 verify 不通过，就停下报告，不自动重试。
- 每个批次结束后先停下，把 summarize 结果交给用户；用户同意后再生成下一个批次的 plan。
```

### 4.11 Prompt 9（可选）：新源码的端到端推理

```text
# Prompt 9（可选）：新源码的端到端推理

目标：给定一个 .sol 文件和 Prompt 8 产生的某个 checkpoint，输出节点级与合约级预测。

## 1. 基础图的 schema 对齐
原作者图与本仓库 process_graphs 生成器的边类型不同：作者图是 next_line/pos_next/neg_next/end_if/first_next_line 等，本地生成器是 next/if_true/if_false/function_call 等。
- 先写 dfg_v2/infer_schema.py：用本地生成器对作者源码建图，与作者图比较节点类型、边类型、canonical 集合，以及逐文件的节点对应关系。
- 先阅读 scripts/convert_upstream_graphs.py、scripts/compare_upstream_labeling.py、scripts/diff_against_upstream.py，看是否已有相关工作。
- 如果能在不修改原生成器的前提下，用一个确定的映射把本地图转换为作者 schema：实现 to_author_schema(graph)，并在 R/AC 全部源码上验证转换结果与作者图的节点集合、边集合的一致率。一致率不是 100% 就列出差异类型，停下等用户决定。
- 做不到就停在报告，不要硬做推理。

## 2. 推理入口（1 通过之后）
dfg_v2/infer.py 的流程：
  源码 → 本地生成器 → to_author_schema → token 编码（tokens.py）→ pipeline.build(profile = checkpoint 对应的剖面) → model_input.materialize → 加载 checkpoint → 前向 → 输出 JSON（每个节点：行号、代码、概率；合约：概率）
加载 checkpoint 前先核对 schema：
- ntypes 和 canonical 必须与 checkpoint 一致；
- 训练中没有出现过的 canonical 关系丢弃并报告；
- 未知的节点类型直接报错。

## 3. 测试
对训练集中的一个文件，用 infer 得到的 logits 与训练图上同一文件节点的 logits 一致（误差 ≤ 1e-5）。
```

## 5. 里程碑与停止点

| 里程碑 | 包含 | 产出 | 需要用户决定的点 |
|---|---|---|---|
| M1 | P0 | RECON.md | 锚点比例或 token 一致率不达标时 |
| M2 | P1–P5 | R/AC 四个任务 × 4 剖面的构图与覆盖统计、任务注册表与扩展说明 | 无 |
| M3 | P6 | Oracle/Slither/抽查表 | 人工标注抽查表 |
| M4 | P7 | 训练器等价性与 8 次小规模训练 | 确认批次 1 的耗时 |
| M5 | P8 批次 1 | 5 个剖面 × 1 种子的 REPORT.md 与 G*（约 7 小时） | 是否跑聚合诊断、是否补种子 |
| M6 | P8 批次 2/3（可选） | 聚合诊断（约 2.8 小时）、补种子（约 5.5 小时） | 无 |
| 以后 | 按 EXTENDING.md | 其余 5 类的 G0 vs G* | 何时扩展 |
| 可选 | P9 | 推理入口 | schema 不一致时 |

M2 结束时，即使还没有训练，也已经能回答"v2 比现有实现多覆盖了多少依赖"。这部分覆盖统计本身就可以写进论文的方法与分析章节。
