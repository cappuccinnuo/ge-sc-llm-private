# MANDO-LLM DFG v2：仓库审查、方案合并与 Codex 编码 Prompts

审查对象：`cappuccinnuo/ge-sc-llm-private`，`main@e76285a` 与 `ddg-v1.1-correctness@e7bcb84`（2026-10-22）。审查方式是通读代码与文档；云端环境装不上 tree-sitter 0.20.4，测试没有在这里运行。

使用方法：每次给 Codex 开新会话，先贴第 4.1 节"共享上下文"，再贴一个 Prompt。按 P0 → P1 → P1b → P2 … → P6 → P6b → P6c → P6d → P6d.1 →（如有缺陷 P6e）→ P7 … → P9 顺序执行，每一步验收通过后再进行下一步。P6 可以和 P7 并行。

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
| `REV_*`（上面四个关系的反向） | 反向 | 两端交换 | 与对应正向关系同层，主剖面都包含 |

剖面定义：
- G0：原作者 HCG 的精确副本
- G1R = G0 + L1（正向 + 反向）
- G2R = G1R + L2（正向 + 反向）
- G3R = G2R + L3（正向 + 反向），主方案
- G3 = 与 G3R 同一张图，但只有正向关系，用作方向消融

**为什么主剖面用双向（2026-10-23 修订）**：HGT 的消息只沿边的方向传递。
- 原 MANDO 的 CFG/CG 边全部经 `reflect_graph` 加了反向，只让数据流边单向会造成两类边处理不对称。
- 只有正向时，定义语句收不到"它的值流向哪里"，写状态变量的语句收不到"这个变量在哪里被读"。
- 影响最大的是 `env_source`：它只有出边，没有入边，原 `HGTLayer` 给无入边的节点类型零消息，它的表示只来自自己固定的 token 特征。同一个键（如 `msg.sender`）在所有文件里的表示完全相同，起不到"汇总并分发本文件使用情况"的中转作用，只相当于一个静态标记。
- 反向不能交给原 `reflect_graph`：两端类型相同时，它会把反向边并进同一个关系、共用参数，方向信息丢失；两端类型不同时，反射出的边会与真实存在的反方向边落进同一个 canonical 关系。因此用带类型的显式 `REV_*` 关系，它们有独立参数，并保留方向信息。这与 Allamanis 等人（ICLR 2018）在程序图 GGNN 中为每种边加一种独立反向边类型的做法一致。
- 双向不保证更好，所以保留 G3（只有正向）作为消融。

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

- 环境键（14 个，固定顺序）：`msg.sender`、`msg.value`、`msg.data`、`msg.sig`、`tx.origin`、`tx.gasprice`、`block.timestamp`、`block.number`、`block.difficulty`、`block.coinbase`、`block.gaslimit`、`blockhash`、`gasleft`、`this.balance`。名字被局部或成员遮蔽时跳过。
- **同一个运行时值的不同写法合并为一个键（2026-10-24 修订）**：`now` → `block.timestamp`，`msg.gas` → `gasleft`，`block.blockhash(...)` → `blockhash`，`address(this).balance` → `this.balance`。写法记在边属性 `spellings` 中。
  - 理由：env_source 的作用是在本文件内汇总并分发某个环境值的使用情况。`now` 与 `block.timestamp` 是同一个值，拆成两个节点会把一个中转点拆成两半，同一文件里混用两种写法的语句就无法经由同一个节点互相影响。
  - 不损失信息：语句节点自己的 token 仍含原写法。
  - 原版本把 `now` 与 `block.timestamp` 列为两个键、却把 `block.blockhash` 并入 `blockhash`，口径不一致；修订后统一按"值"合并。
- 每个文件中，每个至少连到一个语句的键建一个 `env_source` 节点，再加边 `ENV_FLOW`（环境源 → 使用语句）。只出现在没有 HCG 节点的语句（emit/revert）中的键不建节点。
- 这些节点不参与节点监督、不计入指标、不参与合约池化。

### 3.5 HGT 接入

- 原有关系仍交给原 `reflect_graph` 处理，所以 G0 与历史完全一致。
- v2 新增的关系不经过 `reflect_graph`，按正向直接加入；剖面中包含对应 `REV_*` 时，再显式加入端点互换的反向关系。
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
| 主矩阵 | G0、G1R、G2R、G3R、G3 × 30 | 150 | 约 7 小时 | 必跑 |
| 聚合诊断 | G0M、G3RM（非空关系平均）× 30 | 60 | 约 2.8 小时 | 可选，主矩阵后决定 |
| 补种子 | G0 与 G* 再跑 seed 2、3：2 × 2 × 30 | 120 | 约 5.5 小时 | 按内层验证结果预先登记的条件触发（见下） |

耗时按 guard_extension_v1 在你本机 RTX 3050 4GiB 上的实测（30 次共 82.7 分钟，约 165 秒/次）估算，该批最大显存占用约 2.9GiB。G3 多了 env_source 节点，Prompt 7 会实测后再更新估计。

**G* 的选择与补种子触发（2026-10-23 按 Prompt 0 审查修订，预先写进 plan）**：
- G* 只用**内层验证集**选：每个剖面在每折 best checkpoint 上的内层验证 Buggy-F1，先对折取平均，再对四个任务取平均；候选为 G1R、G2R、G3R、G3；与第二名差距小于 0.1pp 时选关系更少的那个。外层测试分数不参与选择。
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
- 2026-10-23 修订：主剖面改为双向（G1R/G2R/G3R），原 Prompt 1 已实现的 G1/G2 剖面名由 Prompt 1b 修改。

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
  G1R = {DATA_DEF_USE, REV_DATA_DEF_USE}
  G2R = G1R ∪ {WRITES_STATE, READS_STATE, REV_WRITES_STATE, REV_READS_STATE}
  G3R = G2R ∪ {ENV_FLOW, REV_ENV_FLOW}（并新增 env_source 节点），主方案
  G3  = {DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW}，只有正向，方向消融
  REV_ 只在模型输入阶段生成，NetworkX 图里只有正向关系；正向关系集合相同的剖面共用同一张 NetworkX 图（G3 与 G3R）。
  以后若要做逐层的单向对照，只需在 PROFILES 中加 G1 = {DATA_DEF_USE}、G2 = G1 ∪ {WRITES_STATE, READS_STATE}，代码不需要改。

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
- L3 环境键按运行时值合并写法（now 并入 block.timestamp 等，见第 3.4 节与 Prompt 4）。
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
  c. 对每个正向 v2 canonical (s, R, t)，只要 REVERSE_OF[R] 属于该剖面，就加入 (t, REV_R, s)，端点交换。（原文写的是"profile 为 G3R 时"，已由 Prompt 1b 修订。）
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
  - G0/G1R/G2R 没有辅助节点，结果应与原实现一致。
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
- 手工加两条 DATA_DEF_USE 边（端点同类型、不同类型各一条）：只有正向的剖面中它们是单向的。（原文要求固化"原 reflect 会把同类型 DATA_DEF_USE 变成双向"，但当前 graph_utils.reflect_graph 已对 DATA_DEF_USE 特判为单向；经用户同意，测试改为固化当前真实行为。）
- 含 REV_ 的剖面：每个正向 canonical 都有对应的 REV_，端点交换；冲突输入报错。
- 手工加一个 env_source 节点和一条 ENV_FLOW 边：节点监督 mask 不含它；合约池化的行不含它；新节点类型有自己的 adapt_ws。
- 前向与反向传播可运行；v2 关系的 relation_msg 有非零梯度。
- 同 seed 下，用 make_model 构造的 G0 模型，与 e23_pilot.model.make_model 构造的模型，state_dict 逐张量相等。
- nonempty_mean：构造一个每个目标节点在每个 canonical 关系上都有入边的小图，HGTLayerNonEmptyMean 与 HGTLayer 输出一致（误差 ≤ 1e-6）；再构造一个有零入度关系的图，验证分母只计入度 > 0 的关系。

## 验收
测试全部通过；PROGRESS.md 列出每个测试覆盖的性质。

（状态：2026-10-23 已完成并验收，提交 4ec8806。）
```

### 4.3b Prompt 1b：主剖面改为双向（修订 Prompt 1）

主剖面统一用"正向 + 显式 REV_ 关系"，只保留 G3 作为只有正向的方向消融。理由见第 3.1 节。改动只在 dfg_v2 内。

```text
# Prompt 1b：把反向关系从"只在 G3R"改为按剖面声明

前置：Prompt 1 已完成（提交 4ec8806）。先 git pull --ff-only origin dfg-v2，读第 3.1 节"为什么主剖面用双向"。

## 1. dfg_v2/__init__.py
PROFILES 改为：
  G0  = {}
  G1R = {DATA_DEF_USE, REV_DATA_DEF_USE}
  G2R = G1R ∪ {WRITES_STATE, READS_STATE, REV_WRITES_STATE, REV_READS_STATE}
  G3R = G2R ∪ {ENV_FLOW, REV_ENV_FLOW}
  G3  = {DATA_DEF_USE, WRITES_STATE, READS_STATE, ENV_FLOW}
删除 G1、G2 两个名字。新增：
- forward_relations(profile)：该剖面中的正向关系（构图用）；
- has_reverse(profile, relation)：REVERSE_OF[relation] 是否属于该剖面；
- PROFILES 的校验：任一 REV_X 出现时，对应的正向 X 也必须在同一剖面中，否则导入时报错。

## 2. dfg_v2/model_input.py::materialize
- 不再判断 profile == "G3R"。对每个正向 v2 canonical (s, R, t)，只要 has_reverse(profile, R)，就加入 (t, REV_R, s)，端点交换。
- 其余规则不变：原边仍交给原 reflect_graph；v2 关系不进入 reflect_graph；canonical 冲突、输入中出现 REV_*、出现剖面外的正向关系都报错。
- build_dgl：env_source 只允许出现在正向关系含 ENV_FLOW 的剖面（G3、G3R）。

## 3. 测试（修改 test_model_input.py、test_model.py、test_hgt_layer.py 中用到 G1/G2 的用例）
- G1R/G2R/G3R：每个正向 v2 canonical 都有端点互换的 REV_ canonical，边数相同；G3 中没有任何 REV_。
- G3 与 G3R 用同一个 NetworkX 图构造，二者只差 REV_ canonical。
- 新增：直接用原 sco_models.graph_utils.reflect_graph 处理一条两端同类型的 WRITES_STATE，断言正反两个方向被并进同一个 canonical 键；处理一条两端不同类型的 WRITES_STATE，断言反射出的键与"反方向的真实 WRITES_STATE canonical"同名。这两条测试用来说明为什么 v2 关系不能交给原反射。
- 新增（eval 模式）：G3 中 env_source 节点在两层后的表示，对同一个键在两个不同文件中完全相同（没有入边）；G3R 中两个文件的使用语句不同，表示也不同。
- 自定义剖面：在测试里临时注册 G1 = {DATA_DEF_USE}，确认单向剖面无需改代码即可构造模型（证明以后做逐层单向对照可行）。
- G0 与原模型的等价测试、诊断层测试保持不变并重新通过。

## 4. 验收
dfg_v2 全部测试与原有回归通过；PROGRESS.md、HANDOVER.md、training_changes 追加"Prompt 1b"记录，写明剖面名变更与原因。

（状态：2026-10-23 已完成并验收，提交 5526009。）
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
- StageJCFGBuilder 需要 StageFSourceView。统一使用 scripts/DFG/state/stage_k/profile.py::SupportedSourceView（加载源码清单中绑定的版本元数据，与 Prompt 0 相同）；构造失败的文件，退回旧的 frontend.parse_source + 旧 CFGBuilder（只为保住旧的标量结果），并在审计中标出。
- V2CFGBuilder 产生的事件要兼容父类内部对 self.access.event(anchor, reads, writes, kind) 和 self.access.entry(...) 的调用（循环条件、入口事件等），weak_writes 默认为空。

## 4. 到达定义 dfg_v2/l1_rd.py
- solve_v2(ir, max_iterations)：复制 scripts/DFG/reaching_definitions.py::solve 的算法，文件头注明来源路径与 SHA256。
- 新增的处理：weak_writes 产生新定义，但不 KILL 同一符号的其他定义；块内按事件顺序重放时同样处理。
- IR 校验要同时检查 weak_writes 引用的符号。
- 等价性测试：对所有 weak_writes 为空的 IR，solve_v2 的 facts、in/out 集合、iterations 与原 solve 完全相同。测试中用 fixtures 验证；真实数据验收时在 R/AC 四个任务的全部旧支持函数上再跑一次。

## 5. 分析与投影 dfg_v2/l1.py
analyze_file(source, file, metadata, max_iterations) -> (facts, diagnostics, stats)：
- 先用旧路径（scripts/DFG/ddg_builder.py::DDGBuilder.analyze_source）得到旧结果。
- 对旧路径回退的函数，用 V2CFGBuilder + solve_v2 重试。旧路径整个文件回退时（例如多 pragma），该文件全部函数都进入重试。
- route 记录为旧回退原因与新路径用到的恢复手段的组合，至少区分：legacy（旧路径成功）、v2_modifier、v2_inheritance（Stage J 的 ClosedScopeJ/StageFCallResolver 解决了旧的 inheritance_binding_not_supported）、v2_version（SupportedSourceView 解决了 builtin_not_guaranteed_over_pragma_interval 或多 pragma）、v2_aggregate；多个手段同时用到时记录列表。审计中给出"旧回退原因 → 新 route / 仍回退原因"的交叉表。
- 旧路径成功的函数不重新计算（保证超集性质）。
- 事实的 def 或 use 锚点落在 modifier_definition 体内时丢弃并计数（modifier 体的 HCG 节点被所有使用它的函数共享，不能挂函数私有的数据依赖）。按当前 Stage J 规则（前缀不允许局部声明、modifier 不接受参数）该计数应为 0；不为 0 时在 PROGRESS.md 列出样例。

augment_l1(graph, sources, metadata, max_iterations) -> (graph, audit)：
- 投影与边的物化复用 scripts/DFG/projection.py::Projector 和 DDGBuilder.projected_edges 的规则：同端点合并为一条、不加自环、保留 ddg_fact_indices 属性。
- 事实用产生它的那个视图投影：旧路径事实用旧 SourceView 构造的 Projector，新路径事实用 SupportedSourceView 构造的 Projector。测试：两种视图都能构造的文件上，两个 Projector 的 by_ast 完全相同。
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
在 R/AC 四个任务上构建只含 L1 的图（供 G1R 使用），输出到 artifacts/dfg_v2/l1_build/：
- 旧支持函数上的边与 integration 的 scalar 剖面逐边一致，不一致即失败。
- 报告：函数支持率（前 → 后，分母沿用 Prompt 0 的全部源码函数：3404/3148/2045/1958）、route 分布、"旧回退原因 → 新结果"交叉表、新增边数、新的 canonical 关系、回退原因 Top 10 的变化。Prompt 0 中占比最大的旧回退原因是 modifier（441/370/127/145）、inheritance_binding_not_supported（374/23/363/10）和 string/bytes/var 等非标量类型，报告要说明这几类各恢复了多少。
- 用 Prompt 1 的 make_model（CPU，不训练，profile="G1R"）在四个 L1 图上各构造一次节点或合约模型，确认 schema 能被接受，并列出新增的 canonical 关系及其边数。
完成后更新 PROGRESS.md 并提交。

（状态：2026-10-24 已完成并验收，提交 d8abc4d。L1 图在 artifacts/dfg_v2/l1_build/final_route_audit/；函数支持率 R 合约 59.78%→91.89%、AC 合约 67.60%→88.66%、R 节点 59.17%→95.84%、AC 节点 79.16%→94.79%。）
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
在每个 Unit 的 regions 内分类。

**语法树形状（Prompt 2 发现）**：当前 grammar 把 `delete a[i]` 解析为 array_access(base=unary_expression(delete, a), index=i)，前缀 `++a[i]`/`--a[i]` 同理。Prompt 2 在 l1_access.py::ExtendedAccessExtractor._prefix_access_event 中只按 AST 字段处理了这种顶层形状。L2 必须用同一规则识别写目标，否则 `delete balances[msg.sender]` 会被误判为只读。做法：把该形状识别抽成 dfg_v2 内一个纯函数（输入 AST 节点，返回 (运算符, 被操作的访问链, 下标列表) 或 None），l1_access 改为调用它（行为不变，用 Prompt 2 全部测试与四任务 L1 图 computation_fingerprint 不变来证明），L2 也调用它。测试加入 `delete balances[msg.sender];`、`++counts[k];`、`delete holders[i].amount;` 三种写法。

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
在 R/AC 四个任务上构建 L1 + L2 的图（供 G2R 使用），输出到 artifacts/dfg_v2/l2_build/：
- 输入是 Prompt 2 最终的 L1 图（artifacts/dfg_v2/l1_build/final_route_audit/，先核对其 manifest 与 SHA）；L2 只追加 WRITES_STATE/READS_STATE，L1 的 DATA_DEF_USE 边及属性逐条不变。
- 不变量全部通过（原节点、原边不变，只多出 v2 关系）。
- L2 覆盖要和 L1 的函数支持情况分开报告：特别列出在 L1 中仍回退的函数（Prompt 2 中 276/357/85/102 个）里产生了多少 L2 边，用来确认 L2 确实不依赖 L1。
- 中转节点的度分布：每个任务列出 READS_STATE 出度、WRITES_STATE 入度最大的 10 个状态变量（变量名、所在文件、度数）。度数很高的变量（例如 owner、balances）是正常现象，只记录，不截断；它们是 Prompt 7 显存估计的输入。
- 用 Prompt 1/1b 的 make_model（CPU，不训练，profile="G2R"）在四个图上各构造一次，列出新增的 canonical 关系及边数（正向与 REV_ 各自计数）。
- 报告每类：状态变量声明数、锚点命中率、WRITES/READS 边数、跨函数连通对数（同一个 decl 的写语句与读语句位于不同 callable 的对数）、经别名的边的比例、unresolved 原因分布。
- 固定 seed=0 抽 20 条边，打印两端代码，写进 PROGRESS.md 供人工检查。
```

（状态：2026-10-24 已完成并验收，提交 a37acf4。状态声明锚点四任务均 100%；WRITES/READS 边 R 合约 3108/4314、AC 合约 1609/2208、R 节点 2254/3070、AC 节点 767/1091；L1 回退函数中产生 L2 边的 182/276、224/357、51/85、72/102。审查后的三处小修订放在 Prompt 4 第 0 部分。）

### 4.6 Prompt 4：L3 环境源（含 Prompt 3 的小修订）

```text
# Prompt 4：L3 环境源 ENV_FLOW 与 env_source 节点

前置：Prompt 3 已完成（提交 a37acf4）；Prompt 0 第 4 项 token 重编码一致率为 100%（已满足）。先 git pull --ff-only origin dfg-v2，读第 3.4 节（本次修订了环境键的合并规则）。
本 Prompt 分两次提交：第 0 部分单独提交（提交信息写 "Prompt 4.0"），第 1–5 部分再提交一次。

## 0. Prompt 3 小修订（先做）
审查 a37acf4 后发现下面几处。都只涉及 Prompt 3 新增的 dfg_v2 文件，不在 L1 路径上（l1*.py 不 import units/state_binding/state_access），所以不需要重跑 L1；在 PROGRESS 中写明这一理由。

1. struct_field_assignment 的字段名被当作标识符读取。
   - 现状：grammar 把 a.call{value: x, gas: g}("") 解析为 call_expression(function=struct_expression(type=a.call, struct_field_assignment(name=value, value=x), ...))。state_access.py::_visit 对 struct_field_assignment 没有专门分支，通用递归会访问 name 字段的 identifier。合约里若恰好有名为 value、gas、salt 的状态变量，就会多出一条错误的 READS_STATE。
   - 改法：加 struct_field_assignment 分支，只访问 value 字段（与现有 call_struct_argument 分支相同）。struct_expression 的 type 字段照常访问，所以 a 是状态变量时仍记 READ。
   - 测试：先用真实解析器确认上面的形状并在测试中断言；uint value; function f(address a, uint x) public { a.call{value: x}(""); } 不产生 decl(value) 的边；把 a 换成状态变量时有 decl(a) → 该语句。
2. legacy 隐式 storage 别名漏掉 string 和 bytes。
   - 现状：state_binding.py::_reference_type 只认 "["、mapping 和 struct。0.4.x 中没有数据位置的 string/bytes 局部变量同样默认是 storage 引用；push/pop 判定已经把 bytes 当作动态数组，两处口径不一致。
   - 改法：类型文本恰好是 string 或 bytes 的 type_name 也算引用类型。只影响有版本证据的 legacy 局部变量（含 var 的选中类型检查）；显式 storage 的处理不变；bytes1…bytes32 不是引用类型。
   - 测试：pragma ^0.4.24 下 bytes data; function f() public { bytes b = data; b[0] = 1; } 产生对 data 的 WRITES（via_alias=True）；pragma ^0.5.0 下同样的源码不建别名（只测解析器行为，该写法在 0.5 不能编译）；bytes32 c = h; 不建别名。
3. try_statement 的 attempt 表达式不在任何区域里，其中的读写既不连边，也不计入 unmapped，审计口径漏数。
   - 改法：units.py::_regions 增加 try_statement → (attempt,)。有精确 HCG 节点就投影，没有就计入 unmapped（作者图没有 try 节点，预期全部是 unmapped）。catch/returns 参数已被局部遮蔽收集，不变。
   - 测试：try 语句中读状态变量计入 unmapped，不挂到函数节点上。
4. 删除 l2.py、projection_view.py、tests/test_l2.py 末尾多余的空行。Prompt 3 为保持 SHA 绑定没有改；本步本来就要重建 L2，绑定会重新生成。

然后：
- 跑新增测试、dfg_v2/tests 全部测试和旧 DDG 回归；
- 用 l2_build 把四个任务的 L2 图重建到新目录 artifacts/dfg_v2/l2_build_r1/（输入仍是 l1_build/final_route_audit/，不覆盖 l2_build/）；
- 与 l2_build/ 逐任务比较：新增或消失的边（逐条列出证据）、unmapped 与 alias 绑定数的变化。预期差异很小或为 0，以实测为准；
- 之后的 L3 以 l2_build_r1/ 为输入；G2R 剖面以后也使用 l2_build_r1/，l2_build/ 只作为历史记录保留。

## 1. 环境键 dfg_v2/env.py
键表示"运行时的同一个值"。同一个值的不同写法合并为一个键，写法记在边属性 spellings 中（理由见第 3.4 节）。

ENV_KEYS（固定顺序的 tuple）：
  msg.sender, msg.value, msg.data, msg.sig, tx.origin, tx.gasprice,
  block.timestamp, block.number, block.difficulty, block.coinbase, block.gaslimit,
  blockhash, gasleft, this.balance
写法 → 键（SPELLINGS 表）：
- msg.<p>、tx.<p>、block.<p>：p 与上表中的同名键一致时直接对应；
- now → block.timestamp；
- msg.gas、gasleft() → gasleft；
- blockhash(...)、block.blockhash(...) → blockhash；
- this.balance、address(this).balance → this.balance。
msg/tx/block 的其他属性（如 block.chainid、block.basefee）不建节点，按写法计入 audit 的 unknown_env_member。以后扩展只需改这两个表。

识别规则：只在 Prompt 3 的 Unit regions 内识别，区域划分直接调用 units.iter_statement_regions(view, projector)，与 L2 相同。
- member_expression：对象去括号后是裸标识符 msg、tx 或 block，property 在表中 → 对应键。对象必须是标识符，所以只匹配最内层：msg.sender.call.value(...)() 只识别一次 msg.sender。block.blockhash 在 member 这一层就匹配，外层调用不再重复匹配。
- call_expression：function 是裸标识符 blockhash 或 gasleft → 对应键。
- 标识符 now：排除下面这些位置——member_expression 的 property；任何父节点的 name 字段（call_struct_argument、struct_field_assignment、variable_declaration、parameter 等）；type_name 内部。
- this.balance：member_expression 的 property 为 balance，对象是标识符 this，或是 address(this)。address(this) 在当前 grammar 中的实际形状（type_cast_expression 或 call_expression）先用真实解析器确认，测试中断言该形状。
- 不进入 assembly（yul 中的 timestamp()、caller() 不解释），计入 audit 的 assembly_skipped。
遮蔽：
- 被检查的名字：msg/tx/block 写法检查对象名；now 检查 now；blockhash()/gasleft() 检查函数名。this 与 address 不会被遮蔽。
- 以下任一成立就跳过并计为 shadowed（按键与原因计数）：该名字在当前 owner 的局部名中（直接复用 Prompt 3 的 StateBinder(view, owner).locals，即同样的"整个 callable 保守遮蔽"）；在 binder.members 中存在（ClosedScopeJ 成员或回退后的当前合约成员，任何种类）；是文件顶层声明的名字。
- 状态变量初始化表达式同样适用（owner 是该声明，局部名为空）。

## 2. 节点与边 dfg_v2/l3.py
augment_l3(graph, sources, metadata, token_encoder) -> (graph, audit)
- 输入检查：MultiDiGraph；允许原关系与 DATA_DEF_USE、WRITES_STATE、READS_STATE；拒绝已有的 ENV_FLOW、任何 REV_*、已有的 env_source 节点；原节点 ID 必须全是整数，否则停下报告。
- 先在输入图上构造 Projector（此时还没有 env_source），收集全部出现，最后一次性加点加边。
- 节点：每个文件中，每个至少有一条已投影 ENV_FLOW 的键建一个节点。只出现在 unmapped 语句（emit、revert 等）中的键不建节点，避免孤立节点。
  属性恰好是 Prompt 0 确认的 9 个原键加 dfg_v2_aux（测试断言键集合）：
    node_type="env_source"，source_file=该文件，code=键文本，label="ENV:"+键，method=""，
    node_info_vulnerabilities=None（原 get_node_label 把 None 当 valid；监督另外按节点类型排除 env_source），
    node_source_code_lines=[]，type_label="env_source"，token=token_encoder(code)，dfg_v2_aux=True
  token 的 Python 类型、dtype、shape 与原节点 token 完全一致（先读几个原节点确认），不要混用 list、ndarray、tensor。
  逐一检查训练路径上读取节点属性的代码（sco_models/graph_utils.py 中被 model_hgt.py 与 dfg_v2/model.py、supervision.py 调用的函数）：确认 method=""、node_source_code_lines=[] 不会进入 get_function_boundaries 一类函数（它们需要 source_path 键，训练路径不调用）。结论写进 PROGRESS。
- 节点 ID：从原图最大整数 ID + 1 开始，按 (source_file 排序, ENV_KEYS 顺序) 连续分配，加在 NetworkX 图末尾。
- 边：env 节点 → Unit 节点，edge_type=ENV_FLOW，每个 (env, unit) 一条；属性 dfg_v2_version、env_key、spellings（排序）、evidence_indices。
- 不变量：原节点、原边、L1/L2 边及其 key/属性/顺序全部不变；新增节点都是 env_source，只有 ENV_FLOW 出边；各文件之间仍不连通（runtime.assert_disconnected_files）。
- audit：每个文件、每个键的出现数、已投影数、unmapped（按所在语句的 AST 类型计数，例如 emit_statement、revert_statement）、shadowed、unknown_env_member、assembly_skipped；L1 回退函数中产生的 ENV_FLOW 边数（与 Prompt 3 的独立性报告相同）。
- 提供 strip_aux(graph)：返回去掉 env_source 节点及其边的副本。以后在 L3 图上构造 Projector 之前都要先调用它（Prompt 5 的 pipeline 会用到）；测试 strip_aux(augment_l3(g)) 与 g 的 fingerprint 相同。

## 3. token_encoder dfg_v2/tokens.py
复用 scripts/DFG/experiments/prepare.py 的 TOKENIZER、REVISION、cached_tokenizer（Prompt 0 的 recon_tokens.py 已用过），设置 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，local_files_only=True。
编码：对 code 取 tokenizer(code, add_special_tokens=True) 的完整 input_ids，再交给 scripts/encode_tokenizer_features.py::encode_ids（前 512 个、右侧补 0、float32）。不要用 truncation=True。
encoder 记录 tokenizer 名称、revision 与资产 SHA（沿用任务清单中的 asset_hashes），写入 audit。
测试：每个任务用固定 seed 抽 20 个原节点，用它编码 code，与原 token 逐位相同；同一输入两次输出相同。

## 4. 测试 tests/test_env.py、tests/test_l3.py
a) require(msg.sender == owner)：ENV_FLOW(msg.sender → 该语句)；同时 L2 有 decl(owner) → 该语句。
b) require(tx.origin == owner)：产生 tx.origin 节点。
c) 同一文件中 if (now % 15 == 0) 与 if (block.timestamp > deadline)：只有一个 block.timestamp 节点，两条 ENV_FLOW，spellings 分别是 ["now"] 与 ["block.timestamp"]。
d) msg.gas 与 gasleft() 合并为 gasleft；block.blockhash(n) 与 blockhash(n) 合并为 blockhash；this.balance 与 address(this).balance 合并为 this.balance。
e) 遮蔽：参数名为 now；合约成员函数名为 gasleft；局部变量名为 msg（grammar 能解析时）。都不产生边，shadowed 计数正确。
f) 非变量位置：x.now、f({now: 1}) 中的 now 不识别；a.call{value: msg.value}("") 中字段名 value 不影响，仍识别 msg.value。
g) msg.sender.call.value(...)() 只产生一条 msg.sender 边。
h) emit Transfer(msg.sender, to, v)：作者图没有 emit 节点，计入 unmapped；若文件中别处没有 msg.sender，不建该节点。
i) 状态变量初始化 address owner = msg.sender;：ENV_FLOW(msg.sender → 该声明的 new_variable 节点)。
j) modifier 体内的 msg.sender 连到 modifier 中的语句。
k) 同一文件多处 msg.sender 只有一个节点；不同文件各一个；文件之间不连通。
l) 用 L1+L2+L3 的小图分别以 G3R、G3 构造模型（CPU）：env_source 不在节点监督 mask 中，也不在合约池化行中；G3 中 env_source 入度为 0；G3R 中有 REV_ENV_FLOW 入边；一次前向与反传后，env_source 相关参数有梯度（小图测试允许反传）。
m) 原节点的 node_hetero_id、各原节点类型内的行顺序不变；G0/G1R/G2R 用 L3 图构造时被拒绝（build_dgl 已有检查，这里补测试）。
n) 新节点属性键集合 = 9 个原键 + dfg_v2_aux。

## 5. 真实数据验收（不训练）
输入：第 0 部分的 artifacts/dfg_v2/l2_build_r1/（先核对 receipt、manifest 与 SHA，方式同 l2_build.verify_l1）。输出 artifacts/dfg_v2/l3_build/，G3 与 G3R 共用这一张图。
- 不变量全部通过；L1/L2 边与属性逐条不变。
- 每个任务、每个键：env 节点数（即用到该键的文件数）、ENV_FLOW 边数、unmapped 出现数（按语句类型）、shadowed 数、合并前各写法的数量（例如 now 与 block.timestamp 各多少）、unknown_env_member 分布。
- 每个任务：env 节点总数、ENV_FLOW 总数、新增 canonical（正向与 REV_ 各自计数）、G3R 与 G3 的参数量；L1 回退函数中的 ENV_FLOW 边数。
- 真实图上的模型检查（只允许下面这些）：每个任务分别构造 G3 与 G3R 模型（CPU、eval()、torch.no_grad()），各做一次前向；不算损失、不反传、不建优化器。用 forward hook 取每层 HGT 输出中的 env_source 行，按键分组，报告不同文件之间的最大差异：
  - G3：同一个键在各文件应完全相同（容差 1e-6），因为 env_source 没有入边，表示只取决于它自己的 token；
  - G3R：一般应不同；差异为 0 的键与文件对逐一列出并说明原因。
  这是第 3.1 节双向理由在真实图上的验证。同时报告输出形状、是否全部有限、单次前向耗时和进程峰值内存（RSS）。不做 GPU 显存测量（留给 Prompt 7）。
- 固定 seed=0 每个任务抽 20 条 ENV_FLOW 边，打印键、spellings 与目标语句代码，写进 PROGRESS.md。
```

（状态：2026-10-24 已完成并验收，提交 71f19dc（4.0）与 8f8702c。L2 重建到 l2_build_r1/，与 l2_build/ 逐图相同；env 节点 / ENV_FLOW：R 合约 298/3857、AC 合约 261/2536、R 节点 187/3200、AC 节点 182/1948；真实图 CPU 前向中 G3 同键跨文件差异为 0，G3R 不为 0。用户批准的偏离：grammar 会让二元/一元表达式吞掉后缀（a + gasleft() 解析为 (a + gasleft)()），L3 沿未加括号的 binary.right/unary.argument 恢复已知写法，不越过显式括号。遗留的两项只读诊断放在 Prompt 5 第 0 部分。）

### 4.7 Prompt 5：统一构图入口、任务注册表与输入清单

```text
# Prompt 5：统一构图入口、任务注册表、输入清单与图存储

前置：Prompt 4 已完成（提交 71f19dc、8f8702c）。先 git pull --ff-only origin dfg-v2。
本 Prompt 分两次提交：第 0 部分单独提交（提交信息写 "Prompt 5.0"），第 1–5 部分再提交一次。

目标：用一个入口从原始冻结输入重建全部剖面的图，并证明它与 Prompt 2–4 分阶段产物逐图相同。此后 Prompt 6–8 只读取本步生成并封存的图存储（graph store），不再读取 l1_build/、l2_build_r1/、l3_build/。

## 0. Prompt 4 审查遗留的两项只读诊断（先做，不改任何已有代码与图）

1. 解释 G3R 中"邻域不同、但表示在 1e-6 内相同"的 1,070 个文件对。
   - 推测原因：inside_token 特征是 token ID 原值（0 到约 32100 的 float32），经 adapt_ws 线性层与 gelu 后数值很大，HGT 的注意力分数 q·k/√d_k 随之极大，edge_softmax 在初始化时几乎是 one-hot。env_source 的消息于是近似只取每个 canonical 中得分最高的那一个邻居。两个文件只要各 canonical 的得分最高邻居表示相同（例如同样文本的 require(msg.sender == owner);），输出就相同，其余邻居的差异被抹掉。
   - 新文件 dfg_v2/attention_probe.py：CPU、eval()、torch.no_grad()，每个任务对 l3_build 的图构造一次 G3R 模型并前向一次。不训练、不算损失、不反传。
   - 用 forward hook 拿到每层 HGTLayer 的输入 h 与输出。对每个以 env_source 为目标的 canonical，用该层自身的参数按 sco_models/model_hgt.py::HGTLayer.forward 的公式重算注意力（k/q/v 线性层、relation_att/relation_msg/relation_pri、edge_softmax(norm_by='dst')、fn.sum、跨关系 mean、a_linear、skip）。不 monkeypatch、不改原代码。
   - 正确性检查：用重算结果拼出的 env_source 输出与 hook 拿到的真实输出最大差 ≤ 1e-5，否则停下报告，不使用重算结论。
   - 报告：
     - 每层 adapt_ws 之后各节点类型 h 的绝对值均值与最大值；
     - env_source 每个目标行、每个 canonical 的最大注意力权重分布（≥0.99 的比例、中位数）；
     - 对 Prompt 4 记录为"未解析"的每个文件对：各 canonical 的得分最高邻居表示是否逐位相同。
     - 同样统计 READS_STATE 的目标（语句节点）和一个原关系（next_line）的最大注意力权重，作为对照。
   - 结论写进 PROGRESS 和 training_changes。如果确认是注意力饱和，这是原作者 inside_token 特征本身的性质，G0 同样存在。不改特征、不加归一化（会破坏 G0 与历史的一致性）；只作为 Prompt 8 解释结果时的已知事实。
2. 当前 grammar 的表达式形状对 L1/L2/L3 是否还有遗漏。
   - 背景：Prompt 4 发现二元/一元表达式可能吞掉后缀（a + gasleft() 解析成 (a + gasleft)()）。L1/L2 按"根变量与出现集合"工作，这种形状不改变它们看到的标识符集合；写操作来自赋值（优先级最低，不受影响）、delete/++ 前缀（Prompt 2/3 已按同一现象处理）和 push/pop。理论上只有"二元/一元表达式吞掉 x.push(...)/x.pop()"会让 L2 漏掉一次写入。
   - 另一个未核实的风险：grammar 的 _primary_expression 包含 user_defined_type（点分标识符路径）。如果某处 msg.sender 或 s.field 被解析为 user_defined_type 而不是 member_expression，L2 与 L3 都会把它当作类型名跳过，不留任何诊断。
   - 新文件 dfg_v2/grammar_shape_audit.py：对 R/AC 四个任务的全部源码（用 l3_build 输入清单中的源码与 SHA），用 ProjectionView 的 raw 树统计：
     (a) call_expression.function、member_expression.object、array_access.base 是未加括号的 binary_expression/unary_expression 的次数，按外层类型与运算符分类；其中被吞掉的后缀是 push/pop 成员调用的次数，并逐条列出；
     (b) 出现在表达式位置的 user_defined_type（父节点不是 type_name、inheritance_specifier、using_directive、override_specifier、modifier_invocation、import 等声明/类型位置），逐条列出文本、位置和父节点类型；其中文本以 msg./tx./block. 开头，或第一段是状态变量名、局部变量名的，单独计数。
   - 只读，不改分析器。若 (a) 中 push/pop 或 (b) 中有可能影响 L2/L3 的条目大于 0，停下报告条目和建议改法，由用户决定是否修订（修订会使 L2/L3 重建）；若都为 0，记录结论后继续。

## 1. 统一入口 dfg_v2/pipeline.py
build(graph, sources, metadata, layers, token_encoder=None, max_iterations=100000) -> (graph, audit)
- layers 取 ()、("L1",)、("L1","L2")、("L1","L2","L3") 之一，按 L1 → L2 → L3 依次调用已有的 l1.augment_l1、l2.augment_l2、l3.augment_l3。只组合、不复制、不修改它们。
- 图键（graph key）按正向关系集合命名：F0={}、F1={DATA_DEF_USE}、F2=F1∪{WRITES_STATE, READS_STATE}、F3=F2∪{ENV_FLOW}。剖面到图键：G0→F0，G1R→F1，G2R→F2，G3R/G3→F3（以后的 G1/G2 也分别映射到 F1/F2）。映射由 PROFILES 的 forward_relations 推导，不手写第二份表；推导出的正向集合不是这四个之一就报错。
- F0 不重建：直接引用原 HCG 路径与 SHA（不复制、不重新序列化），保证 G0 与历史逐字节相同。
- 结束检查：原节点/原边/属性不变；v2 关系无自环、无重复；每条 v2 边都能追溯到 evidence；没有跨文件的边；env_source 只出现在 F3；NetworkX 图中没有 REV_*。
- audit：版本、图键、对应剖面、各层 audit 的汇总、输入/输出 fingerprint 与 computation_fingerprint（复用 integration/pipeline.py）、源码 SHA、tokenizer provenance、labels_used_for_analysis=False。

## 2. 任务注册表与输入清单 dfg_v2/tasks.py、dfg_v2/inputs.py
- tasks.py：每个类别一条记录。字段：类别名；合约级与节点级各自的冻结任务清单引用（integration/rebuild.py::DEFAULT_MANIFEST 中的 source_task_manifest 与 SHA，内含原 HCG 与源码清单）；graph_labels.json 路径与 SHA；nested 折文件路径与 SHA。路径与 SHA 取 RECON.md 第 5 节已核对的值，构造时逐个 checked()。
  - 现在只填 reentrancy 与 access_control。其余 5 类（arithmetic、denial_of_service、front_running、time_manipulation、unchecked_low_level_calls）只在注释中列出。
  - 任务名格式 <类别>_<contract|node>。代码中不出现类别名分支。
- inputs.py：为选中的任务生成 artifacts/dfg_v2/inputs/manifest.json 与 manifest.seal.json。内容：每个任务的原 HCG 路径与 SHA、源码清单（file → path、sha256、metadata）、标签文件、折文件、tokenizer 的 feature 记录（含 asset_hashes）。之后的步骤只读这份清单。
- make_folds(category)：调用 scripts/DFG/experiments/protocol.py::make_fold_document（seed=1、inner_fraction=0.2；合约级 5 折，节点级为 10 折且只含 buggy 文件），与 freeze_splits.py 用的是同一个函数。现在不对其余 5 类运行它。测试：对 R/AC 四个任务在内存中重建，与冻结的 nested 折文件逐字段相同（Prompt 0 已确认 4/4 一致）。
- 写 scripts/DFG/dfg_v2/EXTENDING.md：新增一类的五个步骤（注册 → Prompt 0 中该类的锚点与 token 核对 → make_folds 生成并封存折 → cli build --tasks → run plan --tasks），并写明不需要改任何分析或模型代码。

## 3. 命令行 dfg_v2/cli.py
build：
  python -B -m scripts.DFG.dfg_v2.cli build --manifest <inputs 清单> --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node --graph-keys F1,F2,F3 --output artifacts/dfg_v2/graphs_v1
- --tasks 默认就是这四个任务；--graph-keys 默认 F1,F2,F3（F0 只登记引用）。
- 每个任务只解析一次源码，L1 → L2 → L3 逐层构建，逐层保存：<output>/<task_id>/<图键>/hcg.gpickle 与 audit.json。F2 由 F1 的结果继续构建、F3 由 F2 继续，不从头重复 L1。
- 为每个 (任务, 剖面) 构造一次 CPU 模型（make_model，G0/G1R/G2R/G3R/G3 共 20 次），只验证 schema 并记录 canonical 数与参数量，不前向。
- 写图存储 <output>/store.json 与 store.seal.json：每个任务 → 每个图键 → 路径、SHA、fingerprint、computation_fingerprint、正向关系集合、对应剖面及各剖面是否加反向、模型 schema 摘要。G0 指向原 HCG。拒绝覆盖已有目录。
- 写 <output>/build_summary.csv，列：task_id、graph_key、profiles、nodes、edges、各 v2 关系边数、env 节点数、新 canonical 数、L1 函数支持率、状态声明锚点命中率、耗时。
verify：
  python -B -m scripts.DFG.dfg_v2.cli verify --store <store.json>
- 核对 seal、每个图文件的 SHA 与 fingerprint、输入清单 seal。Prompt 7/8 训练前调用它。
- verify 不要求当前代码树与构图时的 runtime 相同（runtime 只记录在 store 中，供追溯）。原因：以后任何无关的提交都会改变 runtime SHA；训练需要的是"图与构图记录对得上"，而不是"代码从未改过"。构图过程内部仍要求开始与结束时 runtime 相同。

## 4. 测试 tests/test_pipeline.py、tests/test_tasks.py、tests/test_cli.py
- F0 引用的就是原 HCG，SHA 与 fingerprint 相同。
- F1 ⊆ F2 ⊆ F3（按 (src, dst, edge_type) 比较边集合；F3 去掉 env_source 后 fingerprint 等于 F2）。
- 同一输入重复构建，computation_fingerprint 相同（确定性）。
- 剖面到图键的推导：G3 与 G3R 落到同一个 F3；在临时 PROFILES 中加入 G1/G2 时分别落到 F1/F2；不在四个集合中的正向集合报错。
- 缺源码的文件保留原图，并在 audit 中列出。
- 接口通用性：临时注册一个虚构类别（复用 R 的 3 个文件改名），走完 注册 → make_folds → build → make_model 前向（小图）。该测试不写入正式注册表。
- verify：篡改任一图文件或 store.json 时报错；只新增一个无关 .py 文件时不报错。

## 5. 真实数据验收
- 用 cli build 对四个任务构建 F1/F2/F3，输出到 artifacts/dfg_v2/graphs_v1/。
- 与分阶段产物逐任务比较 fingerprint 与 computation_fingerprint：F1 vs l1_build/final_route_audit，F2 vs l2_build_r1，F3 vs l3_build。必须全部相同；不同就停下，逐条列出边差异，不得用新结果覆盖旧结论。
- cli verify 通过；build_summary.csv 写进 PROGRESS.md；不变量全部通过；20 次模型构造的 schema 记录写进 store。
- 记录每任务总构图耗时（应在几分钟以内）与峰值 RSS。
```

（状态：2026-10-25 已完成并验收，提交 d6c7007（5.0）与 7f8a340。graphs_v1/store.json 登记四任务 F0–F3 共 16 个图项与 20 个模型 schema；F1/F2/F3 与 l1_build/final_route_audit、l2_build_r1、l3_build 的两种指纹全部相同。5.0 诊断：第一层注意力在多邻居目标上大多集中于一个邻居（REV_ENV_FLOW 55–86%、READS_STATE 与 next_line 96–99% 的最大权重 ≥0.99），第二层没有；1,070 对中 731 对是第二层上 1.2e-7–9.5e-7 的真实非零差（约为 float32 舍入量级），不是同一表示；吞掉的 push/pop 与表达式位置的 user_defined_type 均为 0。用户批准的两项接口调整：每任务源码只加载一次、各层各调用一次；通用类别测试改用 20 个合成文件以满足 5/10 折。）

### 4.8 Prompt 6：正确性验证

```text
# Prompt 6：依赖正确性验证（Oracle + Slither + 人工抽查表）

前置：Prompt 5 已完成（提交 d6c7007、7f8a340）。先 git pull --ff-only origin dfg-v2。所有真实图一律从 artifacts/dfg_v2/graphs_v1/store.json 读取，读取前调用 store.verify_store。

本步只做验证，不修改 L1/L2/L3 分析器、pipeline 或已有图。发现的错误记下来，修复放到单独的 Prompt 6b；6b 修复后必须用 cli build 生成新的图存储（graphs_v2/），并重新运行本步。Prompt 7/8 以最后一次通过本步的图存储为准。
本 Prompt 分三次提交：(1) 只含 oracle 源码与 expected.json（提交信息 "Prompt 6.1 oracle expectations"）；(2) 比较代码、Slither 对照与抽查表；(3) 文档。

## 1. 手写 Oracle（先封存期望，再运行）
目录 scripts/DFG/dfg_v2/oracle/，每个用例一个 <name>.sol 和 <name>.expected.json。

用例（18–20 个，每个只测少数几件事，pragma 写明版本）：
- L1：覆盖赋值后的读取（不应连旧定义）；if/else 合流（两个定义都到达）；while 循环回边（循环体末尾的赋值到达循环条件）；for 循环中的 i++；return 之后的不可达语句；tuple 赋值 (a, b) = (x, y)（x 只到 a）；结构体局部变量的成员写（弱定义，不 KILL）；带一个前缀 modifier 的函数。
- L2：跨函数写→声明→读（Prompt 3 的 reentrancy_simple）；两个合约的继承；var/storage 别名及其被重新赋值（取并集）；memory 拷贝（无 WRITES）；常量（无边）；参数遮蔽状态变量（无边）；delete balances[msg.sender] 与 ++counts[k]（写）；合约对象的同名 push（只有 READS，无 WRITES）；call 选项 a.call{value: x}("") 中的字段名不算读取；状态变量初始化表达式。
- L3：同一文件 now 与 block.timestamp 合并为一个节点；msg.gas + gasleft()（需要后缀恢复）；参数名为 now 时被遮蔽；emit 中的 msg.sender 计入 unmapped、不建节点；modifier 体内的 msg.sender。

expected.json 格式：
{
  "source_sha256": "...",
  "edges": [ {"relation": "DATA_DEF_USE", "src": "<语句文本>", "dst": "<语句文本>", "var": "a"}, ... ],
  "absent": [ 同上格式，必须不存在的边 ],
  "counts": { "unmapped_env": 1, "env_nodes": {"block.timestamp": 1} }
}
- 语句文本按"去掉多余空白后的完整语句"书写；状态变量声明用其声明文本；env 节点写成 "ENV:<键>"。每个用例中同一段语句文本只能出现一次，比较代码先断言这一点。
- 期望按本文第 3.2–3.4 节写明的语义来写，而不是按完整的 Solidity 语义。设计中有意的近似（L2 不做流分析，同一函数里"读在写之前"也会通过声明节点相连；L1 字段写是基变量弱定义）要按设计写进期望。若在用例里遇到这类近似与真实语义不一致的地方，在该条目加 "approximation": "<说明>"，单独统计。
- 写期望时不得运行任何分析器、不得查看工具输出。写完先做提交 (1)，并把这次提交的 SHA 与每个 expected.json 的 SHA 写入 oracle/SEAL.json，然后才运行比较。

比较 dfg_v2/oracle_check.py：
- 对每个用例：tests/test_l1.py::graph_for 同样的方式用 generate_cfg_from_source 生成 HCG，再调用 pipeline.build(..., layers=("L1","L2","L3"))。token_encoder 用一个确定性桩函数（返回固定的 float32[512]）；另写一条测试说明边集合与 encoder 无关。
- 用节点的 code 规范化后与 expected 比较；env 节点用 "ENV:"+code。
- 报告每个关系的精确率、召回率，以及 absent 条目中被违反的数量；不一致项逐条列出，并归入三类之一：实现错误 / 设计中的近似 / 期望写错。
- "期望写错"只有在给出语言规则依据时才能成立；修改期望要在新的提交中进行，保留原文件与原 SHA，在 PROGRESS 中写明理由。不能在看到结果后静默改期望。

## 2. Slither 对照（只在可编译的子集上做，可选）
脚本 dfg_v2/validate_slither.py：
- 先检查 slither-analyzer（requirements.txt 中是 0.8.0）与 solc-select 是否可用，离线是否已有所需的 solc 版本（版本取源码清单 metadata 中记录的 version，选择逻辑参考仓库根目录的 auto_version_solc.py）。不可用就写明原因并跳过，不要联网安装。
- 只对 R/AC 两个合约级任务的文件做（节点级任务的文件是它的子集）。
- 对每个可编译的文件，取 Slither 每个 CFG 节点的 state_variables_read / state_variables_written / local_variables_read / local_variables_written 以及源码行号。
- 对照粒度（只用于本验证，不进入构图）：
  - L2：按"原始源码行 + 状态变量名 + READ/WRITE"比较出现集合。v2 一侧取 L2 audit evidence 的 occurrence 字节区间换算成原始源码行（ProjectionView 的 raw 树就是原始源码，不要用 HCG 的 node_source_code_lines，后者基于预处理后的行号）。
  - L1：按"原始源码行 + 局部变量名 + def/use"比较。
- 报告每个任务的精确率、召回率，前 20 个不一致样例，并按原因分类：grammar 差异、别名、继承、内联汇编、modifier 内联方式、v2 的有意近似（字段汇总到基变量、流不敏感）、v2 回退的函数、其他。
- Slither 会把 modifier 内联，也会把通过 storage 引用的写算到状态变量上；这两类单独列出，不计入 v2 的错误。

## 3. 人工抽查表 dfg_v2/review_sheet.py
- 从 R、AC 两个合约级任务的 F3 图中各随机抽 15 个文件（seed=0）；每个文件每种关系（DATA_DEF_USE、WRITES_STATE、READS_STATE、ENV_FLOW）最多抽 5 条边。
- 导出 artifacts/dfg_v2/review_v1/review_sheet.csv（UTF-8 带 BOM，便于 Excel 打开），列：
  review_id, task, file, relation, src_line, src_code, dst_line, dst_code, vars_or_key, via_alias, spellings, grammar_recovered, evidence_occurrence_text, verdict, note
  - 行号用原始源码行（同第 2 部分的换算）；verdict 和 note 留空。verdict 只允许填 correct / wrong / unsure。
  - 同时导出 review_sheet.seal.json（CSV 未填写时的 SHA 与抽样参数），以后可以证明抽样没有被改动。
- 评分脚本 dfg_v2/score_review.py：读取用户填好的 CSV，先核对除 verdict/note 外的列与封存版本完全相同，再按关系计算 correct 比例及 Wilson 95% 区间（unsure 单独计数，不算入分母）。本步只交付脚本和空表，不由 AI 填写 verdict。

## 4. 测试 tests/test_oracle_check.py、tests/test_review_sheet.py
- 比较代码在人为删掉一条边、多加一条边、违反一条 absent 时分别报出对应错误。
- 文本不唯一的用例被拒绝。
- 抽查表：同一 seed 两次导出逐字节相同；篡改非 verdict 列时 score_review 拒绝。
- validate_slither 在没有 slither 或 solc 时给出跳过原因，不抛出未处理异常。

## 5. 验收
- Oracle：全部通过，或每个不一致项都已归类；"实现错误"类的数量与条目写进 PROGRESS，作为 Prompt 6b 的输入（本步不修复）。
- Slither：有结果，或有明确的跳过原因。
- 抽查表与封存文件已生成；在 PROGRESS 中写明交给用户标注的文件路径与填写说明。
- 不训练，不修改 graphs_v1。
```

（状态：2026-10-25 已完成，提交 aded502（期望）、f80073f、ec6b700。Oracle 20 例中 17 例完全匹配、32 条禁止边全部满足；3 例差异已复核：04_for_update（6 项）与 18_environment_synonyms（1 项）是期望写错，16_call_option_fields（1 项）是 L1 实现缺口，交给 Prompt 6b。Slither 因缺少离线 solc 全部跳过；人工抽查表 review_v1/ 共 512 条边，等待用户标注。用户批准的偏离：tuple 赋值按语句粒度验证（输入 x/y → tuple 语句 → a/b 的使用），不验证语句内部逐元素来源。）

### 4.8b Prompt 6b：修复 L1 的 call 选项缺口并重建图存储

```text
# Prompt 6b：L1 支持 call 选项表达式，重建 graphs_v2

前置：Prompt 6 已完成（提交 ec6b700）。先 git pull --ff-only origin dfg-v2。

## 背景
Oracle 16_call_option_fields：target.call{value: x}("") 被 grammar 解析为 call_expression(function=struct_expression(type=target.call, struct_field_assignment(name=value, value=x)), 参数)。旧 AccessExtractor.reads 与 v2 的 V2AccessExtractor.reads（它最后调用 super().reads）都对 struct_expression 抛 Unsupported，整个函数回退，漏掉 x 的使用。L2/L3 已正确处理（只读 type 一侧与字段的 value，不读字段名）。

## 1. 修改 dfg_v2/l1_access.py::V2AccessExtractor.reads（只改这一个函数）
- 在调用 super().reads 之前增加一个分支：node.type == "struct_expression" 时，返回
  self.reads(node 的 type 字段) + 各个 struct_field_assignment 子节点的 self.reads(value 字段)。
  字段名（name 字段）不是读取。不要碰冻结的 scripts/DFG/access_extractor.py。
- 不改 CFG、符号表、到达定义、投影。旧路径成功的函数仍然直接复用旧结果（路由规则不变），所以它们的边不可能变化。
- new C{value: v}(...)、addr.call{value: v, gas: g}(data) 走同一分支；字段值里出现的局部变量都是使用。

## 2. 测试（tests/test_l1_access.py、tests/test_l1.py 中追加）
- target.call{value: x}("")：x 是使用；字段名 value 不是使用，即使函数里恰好有名为 value 的局部变量或参数。
- t.call{value: a, gas: b}(data)：t、a、b、data 都是使用（t 为局部 address 变量时）。
- 只含 call 选项、此前回退的函数，修复后状态为 supported，route 为 v2_retry。
- 此前已支持的函数：用 Prompt 2 的四任务 L1 比较方法证明边与证据逐条不变（见第 3 部分）。
- Oracle 16_call_option_fields 的 DATA_DEF_USE 期望现在满足。

## 3. 重建与比较
- 用 cli build 生成新的图存储 artifacts/dfg_v2/graphs_v2/（输入仍是 artifacts/dfg_v2/inputs/manifest.json，不覆盖 graphs_v1）。
- 写 dfg_v2/store_diff.py：逐任务、逐图键比较 graphs_v1 与 graphs_v2，输出新增/消失的边（按 relation 分组，逐条附 L1 证据中的函数与语句文本）、L1 函数状态从 fallback 变为 supported 的清单及原回退原因。
- 必须满足：
  - 消失的边为 0；L2、L3 的边与属性完全相同（这次修改不在它们的路径上）；
  - 新增边全部是 DATA_DEF_USE，且全部来自状态由 fallback 变为 supported 的函数；
  - 其他函数的 L1 证据逐条相同。
  任何一条不满足就停下报告。
- R/AC 数据集以 0.4/0.5 为主，call 选项可能很少甚至没有；如实报告恢复的函数数和新增边数，0 也是有效结果。

## 4. 重新运行 Prompt 6 的验证
- 在 graphs_v2 上重跑 oracle_check，输出到 prompt6b_v1/oracle_run_v3/。预期 16_call_option_fields 通过；04_for_update 与 18_environment_synonyms 仍按 oracle/CLASSIFICATIONS.json 归为期望写错（不修改原期望文件）。在 CLASSIFICATIONS.json 的新版本（新文件 CLASSIFICATIONS_v2.json，旧文件保留）中把 16 标为 fixed，并写明修复提交。
- 人工抽查表不重新抽样：review_v1 仍是唯一的标注表，避免用户重复标注。由 store_diff 证明 review_v1 中的 512 条边在 graphs_v2 中全部存在且属性不变，并报告 graphs_v2 中有多少条边不在 graphs_v1 中（这些新增边不在抽查范围内，写明这一点）。score_review 增加可选参数 --equivalence <store_diff 结果>，用于把评分结果绑定到 graphs_v2。
- Slither 仍按 Prompt 6 的结论跳过，除非用户已完成 Prompt 6c 的准备。

## 5. 验收
- 新测试、dfg_v2/tests 全部、旧 DDG 回归通过。
- cli verify graphs_v2 通过；store_diff 的约束全部满足。
- 从本步开始，Prompt 7/8 一律使用 graphs_v2/store.json；graphs_v1 只作为历史记录保留。在 PROGRESS 中写明这一点。
```

### 4.8c Prompt 6c（可选）：启用 Slither 对照

```text
# Prompt 6c（可选）：Slither 对照

只有当用户决定需要真实语料上的外部召回参照时才执行。Prompt 6 中所有文件都因缺少离线 solc 而跳过，这是目前唯一能估计 L1/L2 漏边的外部参照；Oracle 只覆盖手写用例，人工抽查表只能估计精确率。

## 0. 用户先完成的准备（需要联网，由用户本人执行，Codex 不得自行安装）
- Codex 先运行 python -B -m scripts.DFG.dfg_v2.validate_slither --list-versions，列出 R/AC 合约级任务每个文件所需的 solc 版本：有 metadata 精确版本的用 metadata；没有的（Prompt 6 中 213 个文件）用仓库根目录 auto_version_solc.py 的规则从 pragma 推出，并标注 "pragma_derived"。输出版本清单和每个版本覆盖的文件数。
- 用户在 mando 环境中安装 solc-select 并安装清单中的版本（solc-select install <版本>）。安装完成后告诉 Codex。

## 1. L1 改为完整出现集合
Prompt 6 的 L1 对照只有投影后的端点，所以召回不可计算。改为：在 validate_slither.py 中只读地调用 Prompt 2 的现有组件（V2 符号表、读写提取、CFG 构建，或 l1.analyze_file 返回的 IR 事件），导出每个已支持函数中每次局部变量读写的（原始源码行，变量名，DEF/USE）。不修改这些组件。回退的函数不计入 v2 一侧，在报告中单独列出 Slither 在这些函数里看到的读写数，作为"回退造成的漏边"。

## 2. 运行与报告
- 对每个能用对应版本编译的文件运行 Slither 0.8.0；编译失败的文件列出原因，不重试其他版本。
- 按 Prompt 6 第 2 部分的口径报告 L1/L2 的精确率和召回率、前 20 个不一致样例与原因分类；pragma_derived 版本与 metadata 版本分开统计。
- 不进入构图，不修改任何图。
```

（6b/6c 状态：2026-10-25 已完成，提交 f270ed6、c09bbbc、7918427、2aec59a。有效图存储为 graphs_v2_r1/store.json（首次 graphs_v2 因临时 .py 进入 runtime 摘要而封存失败，作废保留）。L1 恢复函数 7/4/6/3 个、每张增强图新增 DATA_DEF_USE 51/50/60/34 条，全部来自 new_expression；消失边 0，L2/L3 不变；Oracle 18/20。用户批准的偏离：补 new_expression 类型名的读取处理；store_diff 允许 ddg_fact_indices 重编号（解引用后事实逐字段相同）；仍回退函数允许回退原因推进；6 个无 pragma 文件用 0.4.25 并单列；6c 由 Codex 下载安装 solc。Slither 可比较 239/256 文件：L1 P/R 72.9/89.0（重入）、60.5/87.9（访问控制），L2 P/R 98.9/86.9、98.3/85.4；差异大部分尚未归类，见 Prompt 6d。）

### 4.8d Prompt 6d：Slither 差异的完整归类与比较口径修正（进入 Prompt 7 前的门槛）

```text
# Prompt 6d：Slither 差异归类、跨度对齐与小项加固

前置：Prompt 6b/6c 已完成（提交 2aec59a）。先 git pull --ff-only origin dfg-v2。
本步只读已有产物并改进验证工具；不修改 L1/L2/L3 分析器、pipeline 与图，除第 5 部分明确允许的一处。需要改分析器的发现一律停下报告，进入单独的 Prompt 6e。
输入：graphs_v2_r1/store.json（先 verify），prompt6c_v1/slither_full/report.json 及其 seal。不重新运行 Slither，第 4 部分除外。输出：artifacts/dfg_v2/prompt6d_v1/。

## 背景：为什么需要这一步
6c 的主指标保留不变，但它目前不能回答"v2 的读写提取有没有实现错误"：
- L2 漏掉的 1055（重入）/602（访问控制）条参考事件只核查了 3 条；L1 多出的事件中，入口初始化以外的 45/377 条、已支持函数中漏掉的 37/30 条都没有归类。
- 比较按"起始行"对齐：v2 的 L2 用出现位置所在行，Slither 用 CFG 节点起始行，跨行语句会同时产生一个假"多出"和一个假"漏掉"（6c 已确认的 3 例中有 2 例就是这种情况）。
- 有几类差异是两边约定不同，而非任何一方出错，需要用确定的判据单独计数，例如：
  - Slither 的 state_variables_read 包含 constant 状态变量，v2 按设计排除；
  - 对 m[k] = v、s.f = v、delete m[k]，Slither 的 IR 先对基变量做 Index/Member 操作，可能把 m/s 记为读取；v2 按设计只记写；
  - 状态变量初始化表达式：Slither 放在合成的构造函数中并记写，v2 不记声明对自身的写；
  - v2 的 L1 在函数入口为参数/命名返回值记定义，Slither 没有对应项。

## 1. 跨度对齐的比较（附加口径，不替换 6c 主指标）
新文件 dfg_v2/slither_align.py：
- v2 一侧：L2 用 F3 audit evidence 的 occurrence 字节区间；L1 用 l1_occurrences 导出的事件所在语句 anchor 的字节区间（入口定义用声明区间）。
- Slither 一侧：用 report.json 中每个参考事件已记录的 CFG 节点字节区间（start, length）。
- 匹配规则：变量名与读/写类型相同，且 v2 的区间与 Slither 节点区间相交；同一 (变量, 类型) 内按区间做一对一匹配（贪心按起点排序即可，写明规则）。
- 报告与 6c 相同分组（任务、版本来源、supported/fallback）的 P/R，并列出从"行口径不匹配"变为"跨度口径匹配"的事件数。

## 2. 每一条差异的确定性归类
在跨度口径的结果上，对每个 L1/L2 的多出项（FP）和漏掉项（FN）按下表顺序判定，取第一个成立的类别。每个类别的判据必须是可以从 report.json、F3 audit、l1_occurrences 和源码 AST 中机械检查的条件，写进代码和报告；不允许"看起来像"。
L2：
  1. constant_excluded（FN）：Slither 变量 is_constant 为真（若 report 未记录，用源码中该声明是否带 constant 判定）。
  2. state_initializer（FN）：Slither 事件所在函数是合成构造函数（名字以 slitherConstructor 开头），或节点区间落在一个 state_variable_declaration 内。
  3. write_base_read（FN）：Slither 记 READ 的同一节点、同一变量，v2 在相交区间有 WRITE 而没有 READ，且该写是 index/member/delete 链的根。
  4. modifier_inlining、alias：沿用 6c 的标签。
  5. v2_binding_unresolved（FN）：在该出现位置 v2 有 state_binding_unresolved/excluded 诊断（给出 reason，例如 scope fallback 后的 state_name_missing）。
  6. assembly（FN）：Slither 节点类型为 INLINE ASM，或区间落在 assembly 块内。
  7. push_pop_skipped（FN）：v2 在该位置有 push_pop_write_skipped 诊断。
  8. other。
L1：
  1. entry_initialization（FP）：沿用 6c。
  2. v2_fallback（FN）：沿用 6c。
  3. unreachable_ir：沿用 6c。
  4. named_return_implicit（FN/FP）：Slither 在 return 节点读命名返回值，或 v2/Slither 对命名返回值的隐式定义不同。
  5. declaration_without_initializer：uint x; 一类声明，两边对是否记 DEF 的约定不同（按版本：legacy 下 v2 不记）。
  6. tuple_or_var_declaration：var (a, b) = ...、(uint a, uint b) = ...。
  7. other。
- 报告每个类别的数量、占该方向差异的比例和 5 个样例（含源码行、Slither 节点文本、v2 证据）。

## 3. 剩余 other 的人工判定（AI 辅助，逐条留证据）
- 对每个任务、每层、每个方向（FP/FN），从 other 中用 seed=0 抽 30 条（不足 30 条则全部）。
- 逐条读源码与两边证据，判定为：v2_defect（v2 的提取违反第 3.2–3.4 节写明的语义）/ slither_convention（Slither 的约定与 v2 设计不同，写明是哪条约定）/ comparator_artifact（比较工具本身的问题）/ unclear。每条写一句依据。
- 发现 comparator_artifact 时修复比较工具并重算第 1、2 部分，保留修复前的结果。
- 门槛：
  - 任何 v2_defect 都要汇总成"模式"（同一语法形状算一个模式），写出最小复现源码、受影响的事件数估计（按该模式在全部 other 中的机械匹配计数）和建议改法；
  - 只要出现 v2_defect 模式，就在本步结束时停下，由用户决定是否执行 Prompt 6e（修分析器、重建 graphs_v3、重跑 6/6c/6d）。Prompt 7 不能在此之前开始。
  - 没有 v2_defect 时，在报告中写明 graphs_v2_r1 是 Prompt 7/8 的最终图存储。

## 4. 六个不可比较文件的可证明映射（可选，推荐）
6c 中 0.4.0/0.4.2/0.4.9 编译的 6 个文件，Slither 节点缺 filename。只有同时满足以下条件时才把缺 filename 的节点归到目标文件：
- 源码中没有 import 指令（单文件编译，没有其他来源）；
- 每个这样的节点的 (start, length) 落在目标文件字节范围内，且该区间的源码文本与 Slither 记录的节点表达式/源码文本一致（逐个核对）；
- 任何一个节点不满足就保持 not_comparable。
满足的文件在新的报告中加入比较，单独列出其 P/R，不并入 6c 的封存结果。

## 5. 小项加固
1. new_expression 的防御（唯一允许的分析器改动，且必须证明不改变任何图）：grammar 的 new_expression 规则允许直接带调用参数。当前 ExtendedAccessExtractor.reads 对 new_expression 返回 []，依赖"参数在外层 call_expression 中"这一实测形状。改为：若 new_expression 自己带 call_argument 子节点，就读取这些子节点；否则行为不变。
   - 先统计四任务源码中 new_expression 直接带 call_argument 子节点的次数。预期为 0；若为 0，用 cli build 重建到临时目录，证明 F1–F3 两种指纹与 graphs_v2_r1 完全相同，graphs_v2_r1 继续有效，临时目录只保留比较记录。若不为 0，停下报告（这会改变图）。
   - 补测试：new uint[](n)、new bytes(len)、new string(len)、new C(a, b) 中的 n、len、a、b 都是使用；new_expression 的类型名不是使用。
2. 新增 111 条边的补充抽查表：6b 恢复函数在两个合约任务 F3 中新增的 111 条 DATA_DEF_USE 不在 review_v1 中。用 review_sheet 的同一格式导出 review_v1b/（全部 111 条，不抽样），单独封存；score_review 可分别评分，也可在报告中合并。不由 AI 填写 verdict。

## 6. 报告与验收
- 写 dfg_v2/PROMPT6D_REPORT.md：6c 主指标（原样）、跨度口径指标、每个类别的数量与比例、人工判定结果、v2_defect 模式清单（或"没有"的结论及依据）、第 4/5 部分结果。
- 测试：类别判据各一个正例和一个反例；跨度匹配的一对一性质；第 4 部分在有 import 或文本不一致时拒绝映射。
- dfg_v2/tests 全部、旧 DDG 回归通过；所有已有产物不被覆盖。
```

（6d 状态：2026-10-25 已完成，提交 bb337ae。跨度口径下全部 13,857 条差异各归一类，other 773 条；分层抽样 172 条逐条判定，0 条 v2_defect。new_expression 直接参数防御分支在语料中触发 0 次，临时重建的 16 个图项文件 SHA 与 graphs_v2_r1 逐字节相同。六个旧编译器文件映射证明不成立，仍不可比较。补充抽查表 review_v1b（111 条）已导出。执行偏差：对 buggy_43.sol、buggy_30.sol 做了 3 次计划外的只读 Slither 探针，未并入统计，已如实记录。审查后需要补的工作见 Prompt 6d.1。）

### 4.8e Prompt 6d.1：把抽样得到的约定变成全量判据，修正比较单位与标签

```text
# Prompt 6d.1：other 全量机械归类、比较单位修正与 Slither 约定实证

前置：Prompt 6d 已完成（提交 bb337ae）。先 git pull --ff-only origin dfg-v2。
本步只改验证工具，不改分析器、pipeline、图。输入：graphs_v2_r1/store.json、prompt6c_v1/slither_full/report.json、prompt6d_v1/alignment_v3/report.json 与 review_other_v3/。输出：artifacts/dfg_v2/prompt6d1_v1/。所有旧产物保留不覆盖。

## 背景（审查 6d 后发现的三处不足）
1. 比较单位不一致被记成了 Slither 约定。L2 一侧按每个词法出现计数，Slither 按 CFG 节点的变量集合计数；同一语句里两次读取 balances 会在 v2 一侧多出一条。这是比较工具选择的计数单位造成的，按 Prompt 6d 第 3 部分应归为 comparator_artifact 并修复，而不是 slither_convention。v2 模型边本身按 (语句, 声明, 关系) 去重，所以语句粒度才是与图一致的比较单位。
2. 标签混用。172 条判定把"v2 有意不支持的范围"（例如不单独分析 modifier 体、版本证据不足时不建 legacy 隐式别名）也记为 slither_convention。这两者含义不同：前者是 v2 的已声明限制，后者是参考工具的约定。论文与后续解释需要分开。
3. other 只抽查了 172/773 条。访问控制 L1 多出项中的 other 有 352 条（占 6.24%），只抽查了 30 条。抽样 0 缺陷在这个规模上不能排除几十条同类问题。抽样中已经识别出 5 种模式，应把它们写成机械判据作用到全部 773 条，使剩余部分小到可以全部人工判定。
另外，"循环条件处 Slither 记写"的解释只基于阅读 Slither 源码，没有直接观察到具体节点上的读写集合。

## 1. 比较单位修正（slither_align 新版本，旧版本输出保留）
- L2 候选按 (v2 语句单元, 变量名, 读/写) 去重，跨度取该语句单元在 evidence 中的语句区间（与 occurrence 区间的并集作为备用）；参考仍是 Slither CFG 节点的变量集合。
- L1 保持按 IR 事件（它本身已在语句内对同一符号去重）。
- 重算第 6d 的全部表格，并与 alignment_v3 对照，列出因单位修正而消失的 FP 数。

## 2. 标签拆分
VERDICTS 改为：v2_defect / v2_scope_limit / slither_convention / comparator_artifact / unclear。
- v2_scope_limit：v2 按第 3.2–3.4 节或已批准偏离有意不覆盖的情形，必须写明对应的条文或批准记录（例如"L1 不单独分析 modifier 体"、"无版本证据时不建 legacy 隐式别名"）。
- slither_convention：参考工具的口径不同，必须写明是哪条约定，并在第 4 部分有实证。
- 172 条已有判定按新标签重新归类（只改标签与依据，不改事实），旧 decisions.json 保留。

## 3. 抽样模式的全量机械化
把 6d 抽样中识别的模式写成可机械检查的判据，加入第 2 部分的分类顺序（排在 other 之前），作用于全部差异：
- L1 modifier_body_unanalyzed（FN）：Slither 事件属于 modifier 上下文，且该 modifier 没有被任何 L1 已支持函数内联（v2 事件中没有落在该 modifier 体内的）。→ v2_scope_limit
- L1/L2 loop_header_merge_write（FN）：Slither 节点类型为 IF_LOOP/循环条件，记录的 DEF/WRITE 在该条件表达式源码中没有对应赋值，且该变量在循环体内被写。→ slither_convention（需第 4 部分实证）
- L1 aggregate_base_use（FP）：v2 的 USE 位于对同一局部变量的成员/下标写语句中（x.f = …、x[i] = …），Slither 同节点只记该变量的写。→ slither_convention（v2 按第 3.2 节把这类写视为对 x 的使用加弱定义）
- L1 bare_expression_use（FP）：语句是单独的标识符或未调用的成员链（x;、to.call.value(amount);），Slither 节点没有对应读取。→ slither_convention
- L2 legacy_alias_unconfirmed（FN）：该位置 v2 有 legacy_alias_version_unconfirmed 诊断。→ v2_scope_limit
- 其余 6d 中出现、可写成判据的模式同样处理；每个判据写一个正例、一个反例的单元测试。
然后：
- 若剩余 other ≤ 150 条，全部逐条判定（不抽样）；否则每个任务×层×方向再抽 30 条，并在报告中写明剩余量。
- 机械判据不能自动说明 v2 正确：对每个新判据，从其命中集合中再随机抽 5 条人工核对判据确实成立，记入报告。

## 4. Slither 约定的直接实证（允许的 Slither 调用仅限这里）
用已在 trusted_compilers_complete.json 中的编译器，对 4–6 个手写最小合约运行 Slither，记录目标节点的 local/state variables read/written：
- while (i < n) { i = i + 1; } 与 for 循环：条件节点是否记 i 的写；
- 状态 mapping 的 m[k] = v 与 delete m[k]：是否记 m 的读；
- 同一语句两次读同一状态变量：是否只记一次；
- 局部 memory 数组 a[i] = v：是否记 a 的读；
- 带参数的 modifier：modifier 体节点归属哪个函数上下文。
合约源码、编译器版本、Slither 输出原文、结论存入 prompt6d1_v1/slither_conventions/。结论与第 3 部分判据对不上的，回到第 3 部分修正判据。

## 5. 绑定未解析的细分
L2 v2_binding_unresolved（53/23 条 FN）按诊断 reason 细分，尤其区分"ClosedScopeJ 失败后只看当前合约导致继承状态找不到"与其他原因；逐条列出文件与变量。属于已声明保守范围的标 v2_scope_limit；不属于的进入第 3 部分判定。

## 6. 门槛与报告
- 写 dfg_v2/PROMPT6D1_REPORT.md：单位修正前后的指标；每个类别（含新判据）的数量、比例、标签；第 3 部分判定结果；第 4 部分实证；v2_defect 模式清单。
- 出现任何 v2_defect 模式：停下报告最小复现、影响事件数与建议改法，由用户决定是否执行 Prompt 6e。
- 没有 v2_defect：在报告中写明 graphs_v2_r1 是 Prompt 7/8 的最终图存储，并给出"仍未逐条判定的差异数"（应为 0 或明确的抽样剩余量）。
- dfg_v2/tests 全部、旧 DDG 回归通过。不训练。
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
- nodetype 特征（仅可选组使用）：原 _nodetype2onehot 的维度等于该图的节点类型数，G3 多了 env_source，而 DGL 的节点类型按名字排序，env_source 会插在中间，使 G0 与 G3 的 one-hot 维度和位置都不同，adapt_ws 无法共享初值。实验中 nodetype 模式改用固定词表：所有剖面都用"原 16 种类型 + env_source"排序后的同一词表生成 one-hot（make_model 增加 nodetype_vocab 参数，默认 None 时保持原行为，以保留 Prompt 1 中与原构造函数的等价测试）。

## 4. 运行器 dfg_v2/experiment/run.py
命令：
  python -B -m scripts.DFG.dfg_v2.experiment.run plan --store <Prompt 6d 确认的最终图存储，目前为 graphs_v2_r1/store.json>（先调用 cli verify） --tasks <任务列表> --profiles <剖面列表> --seeds <种子列表> [--reducer mean|nonempty_mean] --output <新批次目录>
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
R 与 AC 各自的合约 fold0 与节点 fold0，剖面 G0 和 G3R，seed 1，完整训练到早停，共 8 次。其中 R 合约 fold0 的 G3R 同时是显存探针（边数最多的任务与剖面；历史 guard 批次在该任务上已用到 reserved 3068MiB、整卡最低只剩 29MiB），建议最先运行。检查：
- 在训练文件中有边的新 canonical 关系，relation_msg 梯度非零；只出现在内层验证或外层测试文件中的 canonical 不要求梯度，单独列出其数量；
- env_source 不出现在任何指标和预测导出中；
- best/last 重新加载后 logits 逐位一致；
- 显存峰值（allocated/reserved）、整卡最低空闲与耗时写入 PROGRESS.md，用于估算 Prompt 8 批次 1。G3R 探针若 OOM 或整卡空闲低于 100MiB，停下报告，不自动降配。
不要报告这 8 次的 F1 比较结论。
```

### 4.10 Prompt 8：R/AC 实验与统计

先用 1 个种子跑 5 个剖面（150 次，约 7 小时），之后的诊断组和补种子都要你确认才跑；其余 5 类只写扩展说明。

```text
# Prompt 8：R/AC 实验与统计

前置：Prompt 6 与 Prompt 7 都验收通过。先在 PROGRESS.md 写出按 Prompt 7 实测耗时计算的预计总时长，等用户回复确认后再执行 execute。

## 批次 1：主矩阵（必跑）
- 任务：reentrancy_contract（5 折）、reentrancy_node（10 折）、access_control_contract（5 折）、access_control_node（10 折）。
- 剖面：G0、G1R、G2R、G3R、G3；种子只用 seed 1。
- 共 30 × 5 = 150 次。按 Prompt 7 实测耗时估算总时长（参考：此前在 RTX 3050 4GiB 上约 165 秒/次，约 7 小时）。
- 命令示例：run plan --tasks <四个任务> --profiles G0,G1R,G2R,G3R,G3 --seeds 1 --output <新批次>

## 批次 2：聚合诊断（可选，批次 1 结束后由用户决定）
- G0M 与 G3RM（分别是 G0 和 G3R 配 reducer="nonempty_mean"），seed 1，共 60 次，约 2.8 小时。
- G3RM − G0M 与 G3R − G0 的对比，用来区分"新关系的信息"与"跨关系平均分母变化"两种效应。反向关系会让关系总数翻倍，这个诊断放在双向主方案上做。

## 批次 3：补种子（由 selection.json 中预先登记的内层验证条件决定是否触发，再经用户确认执行）
- G0 与 G* 再跑 seed 2、3：2 × 2 × 30 = 120 次，约 5.5 小时。
- 所有种子用同一套冻结折；同一 (任务, 折, 种子) 下 G0 与 G* 共享初值。

## 可选组（用户确认后才跑）
node_feature="nodetype" 下的 G0 与 G3R，seed 1，共 60 次。

## 预先登记的选择规则（写进批次 1 的 plan.json 后不能修改）
- G* = 四个任务的内层验证 Buggy-F1（每折取 best checkpoint 在内层验证集上的值，每个任务先对折取平均）的算术平均最高的剖面。候选只包括 G1R、G2R、G3R、G3。如果与第二名的差距小于 0.1pp，选关系更少的那个。外层测试分数不参与选择。
- 补种子触发：G* 与 G0 的四任务平均内层验证 Buggy-F1 之差的绝对值 ≥ 0.2pp。
- 由 run select 计算并封存 selection.json 后，才允许 summarize 输出外层测试结果。报告中五个剖面的外层测试结果全部列出，并注明 G* 的选择基于内层验证。

## 统计 dfg_v2/experiment/stats.py（任务列表由参数传入，不写死类别）
- 每个 (类, 任务, 剖面)：各折的均值 ± 样本标准差；多种子时先对折取平均，再报告种子间的均值 ± 标准差。best 为主表，last 另列一表。
- 配对比较：
  - 每个剖面 vs G0；另加 G3R vs G3（方向消融）；跑了批次 2 时加 G3RM vs G0M。
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
