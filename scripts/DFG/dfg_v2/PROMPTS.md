# MANDO-LLM DFG v2：仓库审查、方案合并与 Codex 编码 Prompts

审查对象：`cappuccinnuo/ge-sc-llm-private`，`main@e76285a` 与 `ddg-v1.1-correctness@e7bcb84`（2026-10-22）。审查方式是通读代码与文档；云端环境装不上 tree-sitter 0.20.4，测试没有在这里运行。

使用方法：每次给 Codex 开新会话，先贴第 4.1 节"共享上下文"，再贴一个 Prompt。按 P0 → P1 → P1b → P2 … → P6 → P6b → P6c → P6d → P6d.1 → P6d.2 →（如有缺陷 P6e）→ P7 → P7b → P7b.1 → P7b.2 → P7b.3 → P7b.4 → P7c（本地 pilot）→ P8（本地，计划与准备）→ P8A（阶段 A 与中间报告）→ P8B.0（执行器性能修订）→ P8B（阶段 B 与完整报告）→（以后）服务器迁移 4.9h … → P9 顺序执行，每一步验收通过后再进行下一步。P6 可以和 P7 并行。

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

（6d.1 状态：2026-10-25 已完成，提交 a32caa2。L2 改为语句级计数后 FP 482→178，L2 精确率 98.44%/98.42%，L1 与全部 FN 不变；全部 13,553 条差异有机械类别，other 只剩 rubixi 的 1 条。198 条审阅记录：0 v2_defect、16 unclear（15 个事件）。6 个手写 Slither 实证完成；76 条绑定差异全部是 state_name_ambiguous（v2_scope_limit），"ClosedScopeJ 失败导致继承状态找不到"在真实语料中为 0。Codex 将状态记为 unresolved_analyst_findings，未宣布 graphs_v2_r1 为最终图存储。收尾工作见 Prompt 6d.2。）

### 4.8f Prompt 6d.2：剩余机制的定向实证与验证门槛的收尾

```text
# Prompt 6d.2：定向实证、类别级验收与门槛结论

前置：Prompt 6d.1 已完成（提交 a32caa2）。先 git pull --ff-only origin dfg-v2。
本步只做验证：不改分析器、pipeline、图，不改 alignment_v4_r2 的分类结果（第 3 部分的判据修正除外）。Slither 调用只允许用于第 1 部分的手写合约，使用 trusted_compilers_complete.json 中已有的编译器。输出：artifacts/dfg_v2/prompt6d2_v1/。

## 0. 验收标准（本步要明确达到的终点）
"13,350 条未逐条判定"本身不是缺陷：按设计定义的机械类别不需要逐条人工判定。需要的是每个类别同时满足下面三条：
(a) 有机械判据（已有）；
(b) 判据在随机样本上成立：每个非空类别用 seed=0 随机抽 10 条（不足则全部），逐条确认判据确实成立；6d/6d.1 已做过的抽查可以计入，但必须是随机抽取的，按出现顺序取前 5 条的示例不算；
(c) 有成立的理由：v2_scope_limit 引用第 3.2–3.4 节原文或已批准偏离；slither_convention 有直接实证（第 1 部分或 6d.1 的手写合约）。
三条都满足的类别记为 accepted。剩余 unclear 必须由第 1 部分的实证消解，或按第 4 部分的规则处理。

## 1. 定向实证（新增手写合约，放在 convention_cases/ 下）
每个合约用两个编译器各跑一次：0.4.24（若不在可信清单中，用清单里最接近的 0.4.x）与 0.5.11。语料以 0.4.x 为主，只用 0.5.11 的实证不能直接推到 0.4.x。
1. 状态变量循环与外部调用（对应 rubixi 的 1 条）。
   推测：rubixi 循环体内有 send 外部调用，Slither 的 SSA 在外部调用后重新定义状态变量，循环头的 Phi 因此合并出 balance 的写；6d.1 的 whileState 循环体里没有外部调用，所以看不到这个写。
   用例：while (balance > x) { a.send(1); balance -= 1; }，以及去掉 send 的对照版本。观察循环条件节点的 state_variables_written。
2. storage 数组/引用的循环合并写（对应 aggregate/storage 循环的 unclear）。
   用例：for (uint i = 0; i < n; i++) { arr[i] = v; }（arr 为状态数组）；S storage p = m[k]; while (p.x < n) { p.x += 1; }。观察条件节点的读写集合。
3. 状态结构体/成员链赋值的基读取（对应 write_base_read 中 241 条成员链）。
   用例：s.f = v；m[k].f = v；arr[i].f = v；s.inner.g = v。对照 6d.1 已有的 m[k] = v（只写）与 delete m[k]（读+写）。观察是否记 s/m/arr 的 READ。
4. storage 引用局部的成员写（对应 aggregate_base_use 中 storage 引用的 unclear）。
   用例：S storage p = m[k]; p.f = v; 以及 legacy 写法 var p = m[k]; p.f = v;（0.4.24）。观察局部 p 的读写与状态 m 的读写。
5. alias 类别（117/61 条 FP，2/2 条 FN，此前没有逐条判定）。
   用例：Box storage ref = first; ref.value = 7;；Box storage ref = first; ref = second; ref.value = 7;。观察 Slither 把写记到 first、second、两者，还是只记局部 ref。
每个用例保存源码、编译器版本与 SHA、Slither 的节点集合与 IR/SSA 原文、结论。结论写成"在版本 X 下观察到 Y"，不外推。

## 2. 用实证回看对应类别
- 实证支持的，把对应类别或子集标为 slither_convention 并引用实证。
- 实证与 6d.1 的解释相反的，重新判定受影响的事件（逐条，不抽样），并检查是否构成 v2_defect。
- alias：结合实证，把 alias FP 拆成"Slither 不把经 storage 引用的写算到状态变量"与"v2 的流不敏感并集多出的根"（第 3.3 节已声明的近似，属于 v2_scope_limit）两部分，分别计数；无法归入二者的逐条判定。

## 3. 大类别的形状分布与随机抽查
- 对每个非空类别输出源码形状直方图：按规范化后的语句文本模板（变量名替换为占位符）统计前 10 种形状及其数量。
- 重点：访问控制 L1 bare_expression_use 有 340 条，而重入只有 2 条，差别很大。逐一确认这 340 条的语句确实是"单独的标识符"或"没有调用括号的成员链"（例如 to.call.value(amount); 没有后面的 ()）；若有任何一条实际上是被调用的表达式（源码中有调用括号），说明判据过宽，修正判据并重新归类，那些事件逐条判定。
- 对第 0 部分 (b) 要求的每个类别完成随机抽查，记录抽中的 difference_id 与逐条结论。

## 4. 门槛结论
- 若出现 v2_defect：停下，给出最小复现、受影响事件数与建议改法，由用户决定是否执行 Prompt 6e。
- 若全部类别 accepted，且 unclear 为 0：在报告中写明"验证门槛通过，graphs_v2_r1/store.json 是 Prompt 7/8 的最终图存储"。
- 若仍有少量 unclear：只有同时满足以下条件才可通过——总数 ≤ 20 个事件；全部是 FN（Slither 有、v2 没有，即不会在图中引入错误边）；逐条列出并写明已做过的实证。否则停下报告。
- 结论写进 dfg_v2/PROMPT6D2_REPORT.md，并在 PROGRESS.md 中登记最终图存储。

## 5. 测试与不变量
- 新的判据修正（若有）各配正例与反例测试。
- dfg_v2/tests 全部、旧 DDG 回归通过；所有已有产物保留；不训练。
```

（6d.2 状态：2026-10-25 已完成，提交 4a6d52b。28 个非空类别随机抽查 242 条，25 个 accepted、3 个 accepted_with_residual；残留 10 个事件，全部是 FN（9 个聚合变量循环条件处的 Slither 合并写，1 个 rubixi 状态循环条件写），条件表达式均为纯比较、无赋值，且已核对它们不影响 L1 的定义覆盖与已有依赖。门槛结论 passed_with_bounded_FN_residuals：graphs_v2_r1/store.json 定为 Prompt 7/8 的最终图存储。用户批准的调整：残留门槛加"定义覆盖/KILL 影响核查"；补声明控制用例；alias 按实际 READ 细分；补一个形状实证合约。验证阶段（Prompt 6 系列）到此结束。）

### 4.9 Prompt 7：训练接入与小规模验收

```text
# Prompt 7：训练接入、嵌套协议、共同初值与小规模验收（不跑正式矩阵）

前置：Prompt 6d.2 已完成（提交 4a6d52b），最终图存储为 artifacts/dfg_v2/graphs_v2_r1/store.json。先 git pull --ff-only origin dfg-v2，并运行 cli verify。
新代码放在 scripts/DFG/dfg_v2/experiment/（含 __init__.py）。本步只允许第 6 部分的 8 次训练；其余全部在 CPU 上用小图测试。

## 0. 先读、后写（结果记入 PROGRESS）
逐个阅读并列出与 v2 不兼容的依赖及处理方式：
- scripts/DFG/experiments/paper_run.py::fit_variant（训练循环）；
- paper_runtime.py 的 Supervision、validate_registration、graph_schema_and_support、gradient_audit；
- checkpoint.py 的 StopMonitor、save_checkpoint、restore_checkpoint、snapshot_input；
- scripts/DFG/model_validation.py::capture_model_input（确认它对含 env_source 与 REV_* 的 v2 模型给出确定的指纹；不支持就写包装，不改原文件）；
- state/stage_f/initialization.py::initialize_pair；
- RECON.md 第 5 节记录的配置（学习率、OneCycle、50 轮、patience=7、delta=0.001、best 取验证损失严格最小）与种子派生规则。
已知必须处理的点：
- fit_variant 的 gradient_audit 与 ddg_message_update_l1 只统计 DATA_DEF_USE；v2 要覆盖全部 v2 关系与 REV_*。
- graph_schema_and_support 按原 reflect_graph 计算 schema，且只接受 train/val 两部分；v2 要用 model_input.materialize，并接受 inner_train/inner_val/outer_test 三部分。
- paper_checkpoint.py 写死了 paper_kfold 的协议名与 CV validation，不能用；改用 checkpoint.py（格式 ddg-controlled-v1）。
- initialize_pair 要求两个模型的节点类型集合与 state_dict 键完全相同；G3/G3R 多了 env_source，adapt_ws、k/q/v/a_linears、norms、skip 的键和下标都不同。

## 1. 训练器 dfg_v2/experiment/trainer.py
- 把 fit_variant 复制为 trainer.fit，文件头注明来源路径与 SHA256。数值规则逐行保持：Adam、OneCycleLR（total_steps=schedule_epochs）、每轮一次全图前向、一次 optimizer.step、一次 scheduler.step、之后 eval 前向计算验证损失；StopMonitor 的 best/patience 规则不变；CrossEntropyLoss 不加权。
- 只替换与 schema 和协议有关的部分：
  - Supervision → dfg_v2.supervision.DfgV2Supervision；
  - validate_registration → dfg_v2.model.validate_registration；
  - schema/support → 新函数 support(graph, profile, parts)：按 materialize 后的 canonical 统计每个关系在各部分文件中的边数；
  - gradient_audit → 覆盖全部 v2 关系与 REV_*，按 canonical 记录 relation_msg/relation_att 的梯度 L1，并区分"训练文件中有边"与"只在内层验证/外层测试文件中有边"；
  - 检查点 → dfg_v2/experiment/checkpoint.py（见第 2 部分）；
  - 历史行中的 cv_validation_* 字段改名为 inner_val_*。
- 训练结束后：对 best 与 last 各在内层验证集和外层测试集上评估一次；重载检查点后 logits 必须逐位一致（沿用原 roundtrip 检查）。外层测试只在这里出现，训练循环中不得前向外层测试的监督行。
- result.json 记录：best_epoch、last_epoch、best_inner_val_loss、best 与 last 在内层验证和外层测试上的 Buggy-F1/Macro-F1/Precision/Recall/混淆矩阵、梯度审计、检查点 SHA、初值 SHA、显存与耗时。
- 预测导出：outer_test_predictions.json 与 inner_val_predictions.json，带原图节点 ID（节点任务）或文件名（合约任务）、真值、best/last 预测与正类概率。env_source 行不得出现。

## 2. 检查点包装 dfg_v2/experiment/checkpoint.py
直接 import checkpoint.py 的 StopMonitor、save_checkpoint、restore_checkpoint、snapshot_input。保存前与恢复后调用 dfg_v2 的 validate_registration 与 binding 校验。binding 包含：协议名与版本、score_role="outer_test"、selection_role="inner_val"、task、fold、seed、profile、reducer、canonical 列表（按名字排序）、辅助节点类型、图文件 SHA 与 fingerprint、折文件与标签文件 SHA、初值 SHA。

## 3. 嵌套协议 dfg_v2/experiment/protocol.py
- 从 inputs/manifest.json 中登记的冻结 nested 折文件读取每折的 inner_train_files、inner_val_files、outer_test_files；检查三者互不相交、并集等于任务的全部文件。
- 训练只用 inner_train 的监督行；早停与 best 只看 inner_val；outer_test 只在训练结束后评估。
- 指标：Buggy-F1（正类=有漏洞）、Macro-F1、Precision、Recall、混淆矩阵。节点任务只统计原 HCG 节点。
- 这是与原 paper 协议（在 CV 验证折上选择并报告）不同的协议，PROGRESS 中写明差异；历史 F1 不能与本协议的外层测试结果直接比较。

## 4. 共同初值 dfg_v2/experiment/init.py
initialize_family(models, anchor_seed)，models 为 profile → 新构造、未训练的模型：
- 以 G0 为锚，所有剖面中同名同形状的参数逐张量相同：
  - 节点类型相关的参数（adapt_ws、k/q/v/a_linears、norms、skip 的行）按节点类型名对齐；
  - relation_att/relation_msg/relation_pri 的行按 canonical 名对齐（各剖面 etypes_dict 的下标可能不同，不能按下标）；
  - 分类头相同。
- 只在部分剖面存在的参数（新 canonical 的 relation 行、env_source 的各层参数）：用由 (anchor_seed, 参数名, canonical 或节点类型名) 派生的独立生成器初始化。这样某个参数的初值只取决于它自己的名字，不取决于同一次调用里还有哪些剖面；加入或去掉一个剖面不会改变其他剖面的初值。
- 分布与该剖面自己的构造函数相同。注意：relation_att/relation_msg 用 xavier_uniform_ 初始化整块张量，界限依赖关系总数；因此新增行用该剖面自己的关系总数计算界限，共享行沿用 G0 的值。在文档中写明这一点。
- 种子：anchor_seed 沿用 RECON 第 5 节的派生规则（constructor = 10000 + fold，合约任务另加 1000），fit_seed（dropout 等）= constructor + 1000000；同一 (任务, 折, 种子) 下所有剖面用同一 anchor_seed 和 fit_seed。多种子（Prompt 8 批次 3）时 constructor 另加 100000 × (seed − 1)，使 seed 1 与历史规则完全一致、不同种子互不重叠；把这条规则写进 plan。
- 测试：共有参数逐张量相等；重复调用结果相同；G0 不被修改；某个剖面的初值不受同一次调用中其他剖面的影响。

## 5. 运行器 dfg_v2/experiment/run.py
命令：
  python -B -m scripts.DFG.dfg_v2.experiment.run plan --store <graphs_v2_r1/store.json> --tasks <任务列表> --profiles <剖面列表> --seeds <种子列表> [--folds <折列表>] [--reducer mean|nonempty_mean] --output <新批次目录>
  python -u -B -m scripts.DFG.dfg_v2.experiment.run execute --plan <批次>/plan.json [--only task/fold/seed/profile] [--retry]
  python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan <批次>/plan.json
  python -B -m scripts.DFG.dfg_v2.experiment.run select --plan <批次>/plan.json
  python -B -m scripts.DFG.dfg_v2.experiment.run summarize --plan <批次>/plan.json
- plan：先 cli verify；写死任务、剖面、种子、折、配置、所有输入 SHA 与预先登记的选择规则（Prompt 8），写 plan.seal.json。--tasks 默认 R/AC 四个任务，--seeds 默认 1；任务名只从注册表读取。
- execute：GPU 串行、单进程锁；每个 job 一个目录（history.jsonl、best.pt、last.pt、预测、result.json、receipt.json）；成功的 job 直接复用，失败的保留 attempt 并停止，需显式 --retry；不自动降配、不改参数、不切换到 CPU；按 receipt 断点续跑。每个 job 开始前 torch.cuda.reset_peak_memory_stats，结束后记录 max_memory_allocated/max_memory_reserved，并用 nvidia-smi 或 pynvml 记录整卡最低空闲。
- select 只读内层验证指标，写并封存 selection.json；summarize 在 selection.json 不存在时拒绝运行。
- verify：核对每个 job 的 receipt、检查点 SHA、binding 与 plan。

## 6. 测试（全部在 CPU、小图上）
- 训练器等价性（必须通过才能做第 7 部分）：在 R 合约 fold0 的 G0 图上，用原 fit_variant 与新 trainer.fit，从同一初值、同一 (train, val) 文件划分各跑 3 轮。两边用同一划分是为了只比较训练引擎，协议差异另测。CPU 上逐轮 train/val 损失差 ≤ 1e-6。
- 再在 GPU 上用新 trainer 跑同样 3 轮，与 overall_cv_v1 历史 history.jsonl 的前 3 轮对比。DGL 在 GPU 上的消息聚合使用原子加，结果可能有极小差异：记录最大绝对差，≤ 1e-4 视为一致，超过则停下报告。
- 嵌套协议：三部分互不相交；外层测试监督行在训练循环中从不参与前向的损失计算（用 hook 或计数断言）。
- 共同初值：见第 4 部分。
- 端到端：用 Prompt 5 测试中的 20 个合成文件，plan → execute（CPU，2 轮）→ verify → select → summarize 走通；summarize 在 select 之前被拒绝。
- env_source 不出现在任何预测与指标中。

## 7. 小规模验收（本步唯一允许的训练）
- 显存探针最先跑：R 合约 fold0、G3R、seed 1。它是边数最多的任务与剖面（36,256 条 NetworkX 边，G3R 新增 68 个 canonical）。历史上 R 合约 G0 已用到 reserved 3068MiB、整卡最低空闲只剩 29MiB，G3R 很可能更紧。
  - 若 OOM 或整卡最低空闲 < 100MiB：停下报告，不自动降配。报告中列出下面几种不改变数值语义的做法，由用户选择：
    a) PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:<值>，减少显存碎片；
    b) 每个 job 用独立进程运行，job 之间释放 CUDA 上下文；
    c) 关闭桌面或其他占用 GPU 的进程后重测；
    d) 其他做法（混合精度、减少层数或隐藏维度、子图采样等）会改变模型或数值，不在本方案中使用。
- 探针通过后：R 与 AC 各自的合约 fold0 与节点 fold0，剖面 G0 与 G3R，seed 1，完整训练到早停，共 8 次（含探针）。
- 检查并写入 PROGRESS：
  - 训练文件中有边的每个新 canonical，relation_msg 的梯度在第一轮非零；只在内层验证或外层测试文件中出现的 canonical 单独列出数量，不要求梯度；
  - env_source 不出现在任何指标与预测导出中；
  - best/last 重载后 logits 逐位一致；
  - 每次的最大 allocated/reserved、整卡最低空闲、每轮耗时与总耗时、停止轮数；
  - 按实测耗时估算 Prompt 8 批次 1（150 次）的总时长。
- 不报告这 8 次的 F1 比较结论（只有 1 折，不能说明差异）。
```


（Prompt 7 状态：2026-10-26 部分完成，提交 204dfb9。训练接入代码、CPU 测试（1495 passed）、R 合约 fold0 的 CPU 引擎对照（每轮损失差 0.0）通过。GPU 显存探针 R 合约 fold0 G3R 第 1 轮后整卡最低空闲 12 MiB（peak allocated 3300 MiB、reserved 3536 MiB），触发 100 MiB 门槛停止，没有 OOM；0/8 成功，GPU 历史对照未运行。用户批准的两处选择：新增关系行按各剖面自己关系库的 Xavier 界限独立抽取；三次短数值检查单列、不计入 8 次。剩余工作见 Prompt 7b。）

### 4.9b Prompt 7b：显存——等价的共享投影 HGT 层，并完成 Prompt 7 的 GPU 验收

```text
# Prompt 7b：共享投影 HGT 层（数值等价）、GPU 对照与 8 次小规模验收

前置：Prompt 7 已完成到显存门槛（提交 204dfb9）。先 git pull --ff-only origin dfg-v2。
本步需要用户先批准第 1 部分的做法（它改变了训练时使用的层实现，但不改变模型的数学定义与参数）。批准记录写入 PROGRESS。

## 背景：显存花在哪里
sco_models/model_hgt.py::HGTLayer.forward 对每个 canonical 关系都重新计算一次
  k_linear(h[srctype])、v_linear(h[srctype])、q_linear(h[dsttype])，
计算对象是该节点类型的全部节点，而不是只有这条关系的端点；之后再与该关系的 relation_att/relation_msg 做 einsum。于是每个 canonical 都在显存里保留 3 份 N_type×128 的线性输出与 2 份 einsum 输出，还要为反向传播保留它们。显存因此随 canonical 数 × 节点数增长，而不是随边数增长。G0 有 165 个 canonical，G3R 有 233 个。历史上 R 合约 G0 已经只剩 29 MiB 空闲，按现在的 100 MiB 门槛连 G0 也通不过。其中重复的线性投影是原实现的冗余（新增关系本身的 einsum、注意力与消息张量仍有代价，见 Prompt 7b.1 的更正）。

## 1. 共享投影层 dfg_v2/hgt_layer.py（新类，不改原文件）
- HGTLayerSharedProjection(HGTLayer)：只重写 forward。每层先对每个节点类型各算一次 k_linear、v_linear、q_linear（同一个线性层作用于同一个输入），再在每个 canonical 里复用这些结果，做 relation_att/relation_msg 的 einsum 与后续的注意力、消息、cross_reducer='mean'、a_linear、skip、norm，其余一行不变。
- HGTLayerSharedProjectionNonEmptyMean：同样的改动应用到 Prompt 1 的 HGTLayerNonEmptyMean（批次 2 的 G0M/G3RM 使用）。
- 两个新类与原类的 __init__ 完全相同（直接继承，不加参数），因此 state_dict 键、参数形状、构造时的随机数消耗都不变；Prompt 7 的共同初值、检查点格式都不受影响。
- dfg_v2/model.py 的 make_model 增加参数 layer_impl ∈ {"original", "shared_projection"}，默认 "original"（保留 Prompt 1 的全部等价性测试）。layer_impl 写入 binding、plan 与 result。
- 原理上前向是逐位相同的：每个节点类型的线性输出与原来逐关系重复计算时完全一样，后续运算的输入与顺序都没有变。反向传播中，同一线性层的梯度从"多次分别回传后累加"变成"先在共享输出上累加再一次回传"，浮点累加顺序不同，梯度可能有末位差异。

## 2. 等价性验收（必须全部通过，才可用于实验）
在 CPU 上，用相同权重的两份模型（original 与 shared_projection），任务与图取 R 合约 fold0 的 G0 与 G3R、AC 节点 fold0 的 G0 与 G3R：
a) eval 模式前向：每层 HGT 输出与最终 logits 逐位相等（torch.equal）。若不相等，停下报告，不要放宽成容差。
b) 一次反向：每个参数的梯度最大绝对差与最大相对差；要求最大相对差 ≤ 1e-5，并逐参数记录。
c) 训练轨迹：用 trainer.fit、同一初值、同一 fit seed、nested fold0 划分各跑 3 轮；逐轮 train/inner_val 损失最大绝对差 ≤ 1e-6。
d) nonempty_mean 两个类做同样的 a)–c)（只用 R 合约 fold0 的 G0 与 G3R）。

## 3. GPU 对照（改在显存充足的任务上做）
R 合约在原实现下显存已经贴近上限，不适合做 GPU 数值对照。改用 AC 节点 fold0（7,710 个原节点）：
a) 原实现、G0：用新 trainer 跑 3 轮，与 overall_cv_v1 中 access_control_author_node fold_0 的历史 history.jsonl 前 3 轮对比，最大绝对差 ≤ 1e-4（DGL 在 GPU 上的原子加导致的差异）。若该任务没有对应历史记录，改用 Prompt 7 的 CPU 对照结论并写明原因。
b) 同一初值下，original 与 shared_projection 在 GPU 上各跑 3 轮，逐轮损失最大绝对差 ≤ 1e-4。
c) 两者的 peak allocated/reserved 与整卡最低空闲。

## 4. 显存探针重做
- 用 shared_projection，R 合约 fold0、G3R、seed 1，完整训练到早停（这是 8 次中的第一次）。
- 门槛不变：整卡最低空闲 ≥ 100 MiB，且没有 OOM。另外报告余量；若余量 < 300 MiB，在报告中提醒"其他程序占用显存时可能失败"，但不阻止继续。
- 若仍低于 100 MiB：停下报告，并给出第二级做法供用户决定——只为有边的端点计算 k/v（按边而不是按全部节点做 einsum）。它不再逐位相同，需要按第 2 部分的 b)、c) 用容差验收。本步不实施第二级。
- 同时报告同一 job 用 original 实现时的显存（从 Prompt 7 的失败记录读取，不重跑）与每轮耗时的对比。

## 5. 小规模验收（8 次）
- 新建 plan 目录 artifacts/dfg_v2/prompt7b_v1/pilot/（Prompt 7 的 pilot/ 及其失败 attempt 保留，不用 --retry 复用旧 plan，因为 layer_impl 变了）。
- R 与 AC 的合约 fold0 与节点 fold0，G0 与 G3R，seed 1，全部使用 shared_projection，共 8 次。G0 也用 shared_projection，保证配对比较只差在关系上。
- 检查并写入 PROGRESS：
  - 训练文件中有边的每个新 canonical（含 REV_*），第一轮 relation_msg 梯度非零；只在内层验证或外层测试文件中出现的 canonical 单独计数；
  - env_source 不出现在任何指标与预测中；
  - best/last 重载后 logits 逐位一致；
  - 每次的 peak allocated/reserved、整卡最低空闲、每轮耗时、停止轮数、总耗时；
  - 用 8 次的实测耗时估算 Prompt 8 批次 1 的总时长（按任务分别估算：合约 5 折 × 5 剖面、节点 10 折 × 5 剖面）。Prompt 7 中 R 合约 G3R 第 1 轮 23.5 秒，比历史均值慢很多，原因可能是显存贴近上限；以新的实测为准。
- 不报告这 8 次的 F1 比较结论。

## 6. 文档与后续
- Prompt 8 的所有剖面（含 G0）统一使用 shared_projection，并在 plan 中登记；报告中写明：G0 与历史结果不可直接比较（协议不同、层实现的反向浮点累加顺序不同）。
- dfg_v2/tests 全部、旧 DDG 回归通过；新增测试覆盖第 2 部分的 a)、b) 在小图上的情形，以及 layer_impl 不同时 binding 不一致被拒绝。
```


（Prompt 7b 状态：2026-10-26 部分完成，提交 50ff30b。共享投影层已实现并接入（layer_impl，默认 original）。CPU 上 5 组静态对照的逐层输出与 logits 全部逐位相同；mean 四组梯度在用户批准的门槛内；但四组 3 轮损失差 2.9e-6–2.3e-5，超过 1e-6；nonempty_mean 的 R/G0 有一个梯度张量（绝对差 1.59e-8）超过门槛，按规定停止。GPU 对照、显存探针、8 次 pilot 均未执行。用户批准：梯度门槛采用 1e-8 + 1e-5 × 张量尺度的组合公式。审查结论与修订后的验收方法见 Prompt 7b.1。）

### 4.9c Prompt 7b.1：用 float64 证明数学等价，按实验环境的噪声水平验收 float32 轨迹

```text
# Prompt 7b.1：修订共享投影的数值验收，并完成 Prompt 7b 的剩余步骤

前置：Prompt 7b 已完成到 CPU 数值门槛（提交 50ff30b）。先 git pull --ff-only origin dfg-v2。
不修改 HGTLayerSharedProjection*、trainer、优化器与任何数值规则。Prompt 7b 的失败记录全部保留。

## 背景：为什么 7b 的两个门槛设错了（方案作者的错误，不是实现的问题）
- 7b 已经观察到：前向在全部节点、两层输出与 logits 上逐位相同。共享投影唯一的改动是反向传播中同一线性层梯度的累加顺序。float32 下这只会造成舍入级差异（观察到的梯度差约 1e-8，与 float32 机器精度一致）。
- "3 轮损失差 ≤ 1e-6"假定训练轨迹也逐位相同，这在累加顺序改变后不可能成立：Adam 对每个参数按梯度的均方根归一化，梯度接近 0 的元素会因为舍入差异得到符号不同的、大小约为学习率的更新（7b 观察到的最大参数差 8.35e-4 正是学习率的量级）。这种放大在 GPU 上同一份代码重复运行时同样存在（DGL 的原子加使每次累加顺序不同），Prompt 7 本身已经接受 GPU 上 1e-4 的差异。
- nonempty_mean 那个超标的梯度张量，尺度 2.3e-5、绝对差 1.6e-8，是许多大项相互抵消后剩下的小值，舍入误差相对它显得大；"1e-5 × 张量尺度"的相对门槛在这种情况下过严。
因此需要换一种能区分"舍入"与"逻辑错误"的验收方法：
- float64 下舍入误差约 1e-16。若两种实现只差累加顺序，梯度差应在 1e-12 以下；若有逻辑错误（漏掉一项、梯度断开等），差异不会因为换成 float64 而消失。
另外更正：PROMPTS 第 4.9b 背景中"这不是 v2 关系本身的代价"说得过强。共享投影只去掉了重复的线性投影；新增关系仍有自己的 einsum 输出、注意力与消息张量。

## 1. float64 数学等价检查（主门槛，CPU）
- 先确认 DGL 0.6.1 在 CPU 上支持 float64 的 edge_softmax、u_mul_e/sum、v_dot_u 与 multi_update_all。用小图测试；不支持就停下报告，改用第 2 部分作为唯一证据，并说明原因。
- 对 6 个组合（R 合约 fold0 与 AC 节点 fold0 的 G0、G3R，reducer=mean；R 合约 fold0 的 G0、G3R，reducer=nonempty_mean）：
  - 构造同一初值的 original 与 shared_projection 模型，把参数和输入特征都转成 float64（model.double()；不改变图与标签）。
  - a) eval 前向：逐层输出与 logits 最大绝对差，要求 ≤ 1e-12（期望为 0）。
  - b) 一次训练模式前向与反向（关闭 dropout，或两边用同一个 fit seed 的 dropout 掩码）：每个参数张量的 max|Δg| / max(max|g|, 1e-30)，要求全部 ≤ 1e-10。
  - c) 用 trainer.fit 各跑 3 轮（float64，同一初值、同一 fit seed、nested fold0）：逐轮 train/inner_val 损失最大绝对差，要求 ≤ 1e-9。
- 同时记录：同一组合下 float32 的 original 与 shared 之差（7b 已有，直接引用），以及 float32 original 与 float64 original 之差。这可以说明 float32 下两种实现的误差同在舍入量级。
- 任何一项不满足：停下报告，不放宽门槛。这时差异不是舍入造成的，需要查实现。

## 2. 实验环境下的噪声水平（GPU，AC 节点 fold0，显存充足）
- original 实现、G0 与 G3R 各从同一初值、同一 fit seed 在 GPU 上跑两次 3 轮：记录两次之间逐轮损失的最大绝对差（同一代码、同一输入，只因 GPU 原子加的累加顺序不同）。若两次逐位相同，写明 GPU 在该规模上恰好是确定的。
- shared_projection 在 GPU 上跑一次 3 轮：与两次 original 的逐轮损失最大差。
- 门槛：shared 与 original 的差 ≤ max(1e-4, 3 × original 两次之间的差)。1e-4 是 Prompt 7 已登记的 GPU 容差。
- 再按 Prompt 7b 第 3 部分 a)：原实现 G0 用 experiment/equivalence.py（--device cuda，paper 划分 51/6）与 overall_cv_v1 中 access_control_author_node fold_0 的历史 history.jsonl 前 3 轮对比，≤ 1e-4。
- 记录 original 与 shared 在 AC 节点上的 peak allocated/reserved 与整卡最低空闲。

## 3. float32 CPU 轨迹的重新判定
7b 中四组 mean 的 3 轮损失差（2.9e-6–2.3e-5）不再按 1e-6 判定。第 1 部分 b)、c) 通过且第 2 部分通过时，记为"舍入级差异，低于实验环境的 GPU 噪声容差"。原记录保留，报告中两种判定都列出。nonempty_mean 的静态梯度在第 1 部分 b) 中重新判定；R/G3R nonempty_mean 的静态对照在第 1 部分中补做。

## 4. 继续 Prompt 7b 的剩余步骤（第 1、2 部分都通过后）
- 第 4 部分显存探针：shared_projection，R 合约 fold0，G3R，seed 1，完整训练到早停；门槛与停止规则不变（整卡最低空闲 ≥ 100 MiB、无 OOM；余量 < 300 MiB 时提醒）。仍低于 100 MiB 就停下报告，第二级做法（只为有边的端点计算 k/v）留给用户决定。
- 第 5 部分 8 次 pilot：新 plan 目录 artifacts/dfg_v2/prompt7b_v1/pilot/，全部剖面 shared_projection，检查项与 Prompt 7b 第 5 部分相同。
- 按实测耗时估算 Prompt 8 批次 1 的总时长（按任务分开）。

## 5. 测试与记录
- 小图上：float64 下两种实现的前向差为 0、梯度相对差 ≤ 1e-10 的单元测试；人为在共享实现里去掉一个关系的贡献时，float64 检查必须失败（证明这项检查能抓到逻辑错误）。
- dfg_v2/tests 全部、旧 DDG 回归通过。结论写进 PROMPT7B1_REPORT.md 与三份记录文档。
```


（Prompt 7b.1 状态：2026-10-26 停止，提交 8cfb10d。DGL 0.6.1 在 CPU 上支持所需的 float64 运算；小图前向逐位相同，全部参数梯度最大绝对差 1.5e-16；但 k_linears.0.bias 的梯度在数学上恒为 0（softmax 平移不变），两边只剩约 1e-17 的抵消残差，纯相对差 0.133，超过 1e-10，按规定停止。故障注入（去掉一个关系的消息）在 mean 与 nonempty_mean 下都被前向与梯度门槛检出。真实图、GPU、显存探针与 pilot 均未运行。收尾工作见 Prompt 7b.2。）

### 4.9d Prompt 7b.2：修正梯度判据、真实图 float64 诊断的数据类型处理，并完成剩余步骤

```text
# Prompt 7b.2：float64 梯度判据修正、真实图诊断与 GPU/显存/pilot

前置：Prompt 7b.1（提交 8cfb10d）。先 git pull --ff-only origin dfg-v2。
不修改 hgt_layer.py、model.py、trainer.py、model_validation.py、优化器与任何生产数值规则；7b/7b.1 的失败记录保留。

## 背景：7b.1 的梯度判据为什么不成立（方案作者的错误）
对同一 canonical、同一目标节点与注意力头，k_linear 的 bias 经过 relation_att 后，给该目标所有入边的注意力分数加上同一个常数；softmax(z + c) = softmax(z)，所以这个 bias 的精确梯度恒为 0，两种实现都只剩浮点抵消残差（约 1e-17）。用残差作分母的纯相对差没有意义，7b 中"近零 key bias"失败也是同一原因。Codex 在 7b.1 中的数学分析正确，按规定停止也正确。
"float64 下任何失败都说明是实现错误"的说法过强，同样更正。

## 1. 修正后的判据（先写入代码与 PROGRESS，再运行任何真实图）
对每个案例：
- 前向：逐层输出与 logits 的 maxabs 差 ≤ 1e-12（不变）。
- 梯度：令 G = 该案例所有参数张量中 maxabs(g_original) 的最大值（全局梯度尺度）。每个参数张量满足
    maxabs(g_shared − g_original) ≤ 1e-12 × G + 1e-10 × maxabs(g_original)。
  绝对项取全局尺度的 1e-12，是因为恒为 0 的梯度上残差的大小由经过该路径的梯度量级决定，而不是由该张量自己的值决定；不用固定常数，避免依赖量纲。
- 同时输出每个张量的纯相对差（只报告，不判定），以及"结构性零梯度"清单：maxabs(g) ≤ 1e-12 × G 的张量。预期只有各层的 k_linears.*.bias；两种实现在这些张量上都必须 ≤ 1e-12 × G。清单之外出现结构性零梯度时，逐个说明原因。
- 7b.1 的小图预检按新判据重新判定（不重跑也可，用已有的梯度记录重算），原失败结论保留。
- 故障注入负例必须在新判据下仍被拒绝（7b.1 的数据显示前向差约 0.07–0.10，远超 1e-12，应当仍然拒绝）。

## 2. 真实图 float64 诊断的数据类型处理（只在诊断代码中，不改生产路径）
在新文件 experiment/precision_real.py 中实现，生产的构造、校验与训练代码一律不动：
- 先用正常流程构造 float32 模型（全部原校验照常通过），再深拷贝出诊断模型：
  - model64.double()；
  - 把 symmetrical_global_graph 每种节点类型的 data['inp'] 转为 float64；
  - 检查：float32 → float64 是无损转换，转换后的 inp 与 state_dict 逐元素等于原 float32 值；记录原 float32 摘要与转换后的 float64 摘要两种身份。
- 原 forward 中 torch.zeros 未指定 dtype：诊断前向在 torch.set_default_dtype(torch.float64) 的上下文中执行，退出时恢复为 float32，并用测试证明恢复。
- 诊断模型不调用 model_validation 与 trainer 的 float32 身份校验（它们按设计会拒绝 float64），也不改它们。改为在 precision_real.py 中做等价的身份检查：两种实现的诊断模型来自同一个 float32 源模型、同一转换。
- 3 轮轨迹不用 trainer.fit：在 precision_real.py 中写一个最小循环，逐项沿用 trainer 的数值规则（Adam 与 OneCycleLR 的参数取该任务的冻结配置、每轮一次全图前向与 step、eval 前向算 inner_val 损失、同一 fit seed、同一 nested fold0 监督行）。两种实现用同一个循环，所以这个循环是否与 trainer.fit 逐行相同不影响等价性结论；在报告中写明这一点。

## 3. 运行顺序与门槛（按顺序，任一失败即停）
1. 6 个真实案例的静态检查（R 合约 fold0 与 AC 节点 fold0 的 G0、G3R，reducer=mean；R 合约 fold0 的 G0、G3R，reducer=nonempty_mean）：第 1 部分的前向与梯度判据。
2. 同 6 个案例的 3 轮 float64 轨迹：逐轮 train/inner_val 损失 maxabs 差 ≤ 1e-9（不变）。
3. GPU（float32，AC 节点 fold0，Prompt 7b.1 第 2 部分）：original 两次的噪声水平、shared 一次，门槛 max(1e-4, 3 × 噪声)；历史对照改用 projection_validation.py::run_gpu_diagnostic（equivalence.py 只支持重入合约），≤ 1e-4；记录显存。
4. 显存探针：shared_projection，R 合约 fold0，G3R，seed 1，完整训练到早停；整卡最低空闲 ≥ 100 MiB、无 OOM；余量 < 300 MiB 时提醒。仍不足就停下，第二级做法（只为有边的端点算 k/v）由用户决定。
5. 8 次 pilot：新 plan 目录 artifacts/dfg_v2/prompt7b2_v1/pilot/，全部剖面 shared_projection；检查项同 Prompt 7b 第 5 部分；按实测耗时分任务估算 Prompt 8 批次 1 的总时长。

## 4. 测试与记录
- 新判据的边界测试：恒零梯度张量在两种实现残差不同时通过；把某个非零梯度张量人为放大 1+1e-8 时被拒绝；故障注入负例被拒绝。
- dtype 上下文测试：退出后默认 dtype 恢复为 float32；生产路径构造的模型仍是 float32，原校验照常拒绝 float64 输入。
- dfg_v2/tests 全部、旧 DDG 回归通过。结论写进 PROMPT7B2_REPORT.md 与三份记录文档。
```


（Prompt 7b.2 状态：2026-10-26 停止，提交 6f5deb1。6 个真实案例的 float64 静态检查全部通过：逐层输出与 logits 差 0，梯度最大差 1.7e-16 至 4.2e-16 量级，最大占用门槛的 0.025%。R/G0/mean 的 3 轮 float64 轨迹通过（最大差 1.55e-15）。R/G3R/mean 的 float64 轨迹在 CPU 上被 WSL 内核 OOM 终止（匿名驻留约 7.24 GiB，WSL 可见内存 7.9 GiB），其余 4 组未启动；GPU、显存探针、pilot 未运行。收尾工作见 Prompt 7b.3。）

### 4.9e Prompt 7b.3：按证据收窄 float64 轨迹范围，完成 GPU 与 pilot

```text
# Prompt 7b.3：收窄 float64 轨迹、补零梯度结构归类、完成 GPU 对照、显存探针与 8 次 pilot

前置：Prompt 7b.2（提交 6f5deb1）。先 git pull --ff-only origin dfg-v2。
不修改 hgt_layer.py、model.py、trainer.py、model_validation.py 与任何生产数值规则；7b.2 的全部产物与失败记录保留。

## 背景：为什么可以不再要求 6 组 float64 轨迹全部完成
- 等价性的核心证据已经齐全：6 个真实案例覆盖两个任务、G0/G3R、mean/nonempty_mean，前向逐位相同，全部参数梯度的差在 float64 舍入量级（≤ 4.2e-16）。共享投影只改变前向中投影的计算位置，代码路径与关系、reducer 无关，因此"梯度函数相同"已在所有用到的关系与 reducer 上得到检验。
- 优化器是同一份代码；梯度相同、参数相同，下一步参数也相同。3 轮轨迹只是对这一推理的数值确认，R/G0/mean 已经确认（差 1.55e-15）。
- float64 让内存翻倍，R/G3R（233 个 canonical、18,610 个节点）在 WSL 的 7.9 GiB 内存中放不下。为此去调整 WSL 内存不划算，也不必要。
因此改为：在内存放得下的案例上补齐轨迹，覆盖剩下的维度（G3R 关系集合、nonempty_mean）；R/G3R 的两组轨迹记为"因 CPU 内存不运行，以静态检查为证据"，并在报告中写明理由。

## 1. 补齐的 float64 轨迹（每组独立进程，依次运行）
- AC 节点 fold0 G0 mean；AC 节点 fold0 G3R mean；R 合约 fold0 G0 nonempty_mean。门槛不变：逐轮 train/inner_val 损失差 ≤ 1e-9。
- 内存保护：每组启动前记录可用内存；运行时每 2 秒采样进程 RSS，超过 6.5 GiB 就由脚本自己终止该组并记为 skipped_cpu_memory（不是失败，不重试）。7b.2 中 AC/G3R 的取证前向曾因内存压力中止，若 AC/G3R 轨迹也被跳过，照实记录。
- 不运行：R 合约 G3R mean、R 合约 G3R nonempty_mean（理由见背景）。
- 门槛：已运行的组全部通过，且至少 AC/G3R mean 与 R/G0 nonempty_mean 中有一组完成（保证 G3R 关系集合或 nonempty_mean 至少有一个被轨迹覆盖；最好两组都完成）。若两组都因内存被跳过，停下报告。
- 修改 precision_gpu.py 的 CPU 放行条件（这是 7b.2 新增的文件，允许修改）：从"6 组静态 + 6 组轨迹"改为"6 组静态全部通过 + 本部分规定的轨迹集合"；被跳过的组必须有 skipped_cpu_memory 记录，不能缺失。新的放行清单单独封存，7b.2 的清单不改。

## 2. 近零梯度的结构归类（文档项，不影响门槛）
这些张量已经通过门槛：两种实现上都 ≤ 1e-12 × G。下面的归类只用于说明，不作为等价性证据。
- 对 6 个案例都只用图结构与参数名做静态归类，不需要额外前向：
  a) key bias（softmax 平移不变）；
  b) 目标节点在该关系上只有一个不同的来源节点（含同源多重边）的 key/query 相关参数；
  c) G3R 最后一层中没有监督路径的目标（如 env_source）的参数；
  d) 不属于以上三类的，记为"数值上接近零（可能是初始注意力饱和）"，只列出，不再做前向取证。
- 7b.2 已完成的 R/G0、AC/G0 动态取证结果原样保留。

## 3. GPU（float32，AC 节点 fold0）
按 Prompt 7b.2 第 3 部分第 3 步执行：original 两次的噪声水平与 shared 一次（门槛 max(1e-4, 3 × 噪声)），用 projection_validation.py::run_gpu_diagnostic 与历史 history.jsonl 对照（≤ 1e-4），记录显存。

## 4. 显存探针与 8 次 pilot
按 Prompt 7b.2 第 3 部分第 4、5 步执行：
- 探针：shared_projection，R 合约 fold0，G3R，seed 1，完整训练到早停；整卡最低空闲 ≥ 100 MiB、无 OOM；余量 < 300 MiB 时提醒。仍不足就停下，第二级做法由用户决定。
- pilot：新 plan 目录 artifacts/dfg_v2/prompt7b3_v1/pilot/，全部剖面 shared_projection，8 次；检查项同 Prompt 7b 第 5 部分。
- 按实测耗时分任务估算 Prompt 8 批次 1 的总时长（合约 5 折 × 5 剖面，节点 10 折 × 5 剖面），写进 PROGRESS。

## 5. 测试与记录
- 新的放行条件测试：缺少 skipped 记录、跳过了规定之外的组、已运行的组超门槛时都被拒绝。
- RSS 保护测试：模拟超过上限时进程被脚本终止并写出 skipped 记录。
- dfg_v2/tests 全部、旧 DDG 回归通过。结论写进 PROMPT7B3_REPORT.md 与三份记录文档。
```


（Prompt 7b.3 状态：2026-10-26 停止，提交 54f21b5。CPU 放行政策通过：AC 节点 G0/G3R 的 float64 3 轮轨迹差 1.1e-16 与 2.6e-14；R/G0 nonempty_mean 被 RSS 保护终止，按策略记为跳过。GPU（AC 节点）：G0 与 G3R 的 original 两次重复差为 0，shared 与 original 差 7.6e-6 与 3.6e-7（门槛 1e-4），历史重放差 0，均通过。共享投影把 R 合约 G3R 的 peak allocated 从 3300 降到 1824 MiB、reserved 从 3536 降到 2048 MiB；但完整训练探针第 1 轮后整卡最低空闲 66 MiB（门槛 100 MiB），停止；pilot 0/8。等价性验收（7b–7b.3）到此结束；剩余的是资源问题，见 Prompt 7b.4。）

### 4.9f Prompt 7b.4：找出训练进程之外的显存占用，加入启动前检查，完成显存探针与 8 次 pilot

```text
# Prompt 7b.4：显存基线检查、显存探针重做与 8 次 pilot

前置：Prompt 7b.3（提交 54f21b5）。先 git pull --ff-only origin dfg-v2。
共享投影的数值等价验收已经完成，本步不再做任何数值对照。不修改 hgt_layer.py、model.py、trainer.py 与数值规则；7b.3 的失败现场保留。

## 背景：显存不足的直接原因在训练进程之外
用"总显存 − PyTorch reserved − 整卡最低空闲"估算训练进程之外的占用（包含本进程的 CUDA/DGL 上下文与其他程序），按已有记录（总量按 4096 MiB 计）：
| 运行 | reserved | 最低空闲 | 进程外占用 |
|---|---:|---:|---:|
| Prompt 7 原实现 R/G3R | 3536 | 12 | ≈ 548 |
| 7b.3 AC 节点 GPU 诊断（7 次） | 608–1594 | 407–1367 | ≈ 2089–2281 |
| 7b.3 共享投影 R/G3R 探针 | 2048 | 66 | ≈ 1982 |
Prompt 7 时进程外只占约 0.55 GB；7b.3 全程约 2.0–2.3 GB，而且在本轮第一个 GPU 任务开始前就已如此。也就是说，有约 1.5 GB 显存被训练进程以外的东西占用（另一个仍在运行的 CUDA 进程，或 Windows 中使用独显的程序，例如开启硬件加速的浏览器、视频、其他 AI 工具）。如果占用回到 Prompt 7 时的水平，共享投影下的 R/G3R 探针预计有约 1.5 GB 余量。
请先用实际记录（resources.json 中的总显存字段）重算这张表，确认或否定这个判断，写进 PROGRESS。

## 1. 用户先做的检查（Codex 不得自行结束任何进程）
- WSL 中：nvidia-smi 与 nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv；列出所有持有 CUDA 的进程。
- Windows 中：任务管理器 → 性能 → GPU（NVIDIA）→ 专用 GPU 内存；详细信息页加"专用 GPU 内存"列，找出占用大的程序。
- 关闭不需要的占用后，再运行下面的步骤。Codex 可以先执行只读查询并把结果交给用户，但不结束、不改动任何进程。

## 2. 启动前基线检查（加入 experiment/run.py）
- 每个 job 在初始化 CUDA 之前，用 nvidia-smi 子进程（本进程不建立 CUDA 上下文）读取总显存、已用、空闲，记为 baseline。
- 初始化 CUDA 与 DGL 之后、构造模型之前，再读一次，差值记为本进程上下文占用。
- 启动条件：baseline 空闲 ≥ 3000 MiB（写进 plan，可在 plan 时用参数修改，但必须登记）。不满足就不启动该 job，写出 preflight_blocked 记录并停止，提示用户检查第 1 部分。
- 每个 job 的 resources 中增加：baseline、上下文占用、进程外占用估计（总量 − 最低空闲 − peak reserved − 上下文）。
- 运行中的 100 MiB 门槛与停止规则不变。
- 这是 run.py 的改动，plan 会绑定新的代码摘要，因此建立新 plan：artifacts/dfg_v2/prompt7b4_v1/pilot/（与 7b.3 的 plan 相同的任务、剖面、折、种子、shared_projection、冻结初值；写出与 7b.3 plan 的逐项对照，证明只有代码摘要与新登记的阈值不同）。7b.3 的 plan 与失败 attempt 保留。

## 3. 显存探针与 8 次 pilot
- 先跑 reentrancy_contract/0/1/G3R（shared_projection），完整训练到早停；新 plan 中这是第一次运行，从冻结的未训练初值开始，不是续训。
- 通过（无 OOM、整卡最低空闲 ≥ 100 MiB）后，按顺序跑其余 7 项。
- 检查项同 Prompt 7b 第 5 部分：训练文件中有边的新 canonical（含 REV_*）第一轮 relation_msg 梯度非零，只在内层验证或外层测试中出现的单独计数；env_source 不出现在指标与预测中；best/last 重载 logits 逐位一致；每次的 baseline、peak allocated/reserved、整卡最低空闲、进程外占用、每轮耗时、停止轮数、总耗时。
- 若探针仍不通过：停下报告。此时进程外占用若已回到约 0.5 GB 以下，说明训练本身仍超出，再由用户决定是否实施第二级做法（只为有边的端点计算 k/v，需按 7b 的方法重新做等价性验收）。

## 4. Prompt 8 时长估算
用 8 次实测耗时，按任务分别估算批次 1：合约任务 5 折 × 5 剖面、节点任务 10 折 × 5 剖面。G1R、G2R、G3 没有实测，用 G0 与 G3R 按 canonical 数线性插值，写明这是估计。写进 PROGRESS，等用户确认后才进入 Prompt 8。

## 5. 测试与记录
- 基线检查测试：空闲不足时 job 不启动且写出 preflight_blocked；nvidia-smi 不可用时报错停止，不默认放行；基线检查本身不建立 CUDA 上下文。
- dfg_v2/tests 全部、旧 DDG 回归通过。结论写进 PROMPT7B4_REPORT.md 与三份记录文档。
```


（Prompt 7b.4 状态：2026-10-26 停止，提交 e61ffd8。启动前基线检查与新计划已实现；基线通过（CUDA 初始化前 used 450 / free 3526 MiB），完整探针第 1 轮后最低空闲 76 MiB（门槛 100），停止，pilot 0/8。Codex 核实后否定了 7b.4 背景中的推测：并不存在约 2 GB 的外部占用；最小 CUDA/DGL 初始化本身就使空闲下降 1292 MiB（PyTorch 1.8.1 + CUDA 11.1 + DGL 0.6.1 的上下文与内核），4 GiB 显卡扣除基线与上下文后只剩约 2.35 GB 给训练，R/G3R 的 reserved 2048 MiB 已接近上限。用户决定正式实验在显存充足的服务器上进行。用户批准：进程外占用改称"分配器之外的未归属占用估计"；新资源策略每次只允许一个 --only 任务、独立进程执行。）

### 4.9g Prompt 7c：在本地完成 8 次 pilot（本地开发用的显存策略）

用户决定：先在本地 RTX 3050 4 GiB 上跑，看到效果后再迁移到服务器。迁移步骤保留在第 4.9h 节，以后执行。

```text
# Prompt 7c：本地显存策略 local_dev_v1、8 次 pilot 与 Prompt 8 本地时长估算

前置：Prompt 7b.4（提交 e61ffd8）。先 git pull --ff-only origin dfg-v2。
不修改 hgt_layer.py、model.py、trainer.py 与任何数值规则；7b.4 的失败现场保留。

## 背景：为什么可以在本地放宽运行中的显存门槛
- 100 MiB 的"整卡最低空闲"是我们自己设的合作式安全余量，不是硬件限制。R 合约 G3R 在 7b.4 中最低空闲 76 MiB，没有 OOM，第 1 轮的训练、验证与保存都正常完成。
- 显存紧张不改变数值结果。它只可能带来两种后果：一是 CUDA OOM，任务失败，失败记录保留，可以从同一初值重跑；二是在 WSL/Windows 上，驱动可能把部分显存换到系统内存（共享 GPU 内存），这只会变慢、不会算错。Prompt 7 中 reserved 3536 MiB 加上约 1.3 GB 的 CUDA/DGL 上下文已经超过 4096 MiB 却没有 OOM，说明发生过这种换出。
- 全图训练每一轮的显存模式相同，第 1 轮能完成，后面各轮通常也能完成。
所以本地改用"只在 OOM 或非有限值时停止，紧张时记录和提醒"的策略。正式实验迁移到服务器时，恢复 100 MiB 门槛（见 4.9h）。

## 1. 资源策略 local_dev_v1（新增，写进新 plan；旧策略保留不变）
- 启动前基线：空闲 ≥ 3000 MiB（不变）。
- 运行中：不再因整卡最低空闲低于 100 MiB 停止；只在 CUDA OOM、非有限损失或其他错误时停止。
- 记录与提醒：
  - 整卡最低空闲 < 100 MiB 的 job 在 receipt 中标 memory_tight=true；
  - 每轮耗时记录；若某轮耗时超过该 job 前 3 轮中位数的 2 倍，记 possible_memory_spill（只提醒，不停止），提示可能发生了显存换出；
  - 用户可在 Windows 任务管理器的 GPU 页查看"共享 GPU 内存"是否上升，作为佐证。
- OOM 时：保留失败 attempt，停止整个批次；需要用户确认后才能用 --retry 从同一初值重跑（不是续训）。
- 这项改动需要用户批准；批准记录写入 PROGRESS。

## 2. 新 plan 与 8 次 pilot
- 新 plan：artifacts/dfg_v2/prompt7c_v1/pilot/，用 run plan --from-plan 引用 prompt7b4_v1/pilot/plan.json，沿用同一 prepared/initial 文件，资源策略改为 local_dev_v1；逐项对照证明只有资源策略（以及因此变化的代码摘要）不同。
- 先跑 reentrancy_contract/0/1/G3R，之后其余 7 项；每项独立进程、--only 串行；全部 shared_projection。
- 检查项与 Prompt 7b 第 5 部分相同：训练文件中有边的新 canonical（含 REV_*）第一轮 relation_msg 梯度非零，只在内层验证或外层测试中出现的单独计数；env_source 不出现在任何指标与预测中；best/last 重载后 logits 逐位一致；每项的基线、上下文占用、peak allocated/reserved、整卡最低空闲、memory_tight、possible_memory_spill、每轮耗时、停止轮数、总耗时。
- 不报告这 8 次的 F1 比较结论。

## 3. Prompt 8 本地时长估算
- 用 8 次实测耗时按任务估算批次 1（合约 5 折 × 5 剖面，节点 10 折 × 5 剖面）；G1R、G2R、G3 没有实测，按 canonical 数在 G0 与 G3R 之间线性插值，标明是估计。
- 同时给出分阶段执行的估计：阶段 A 只跑 G0 与 G3R（60 次），阶段 B 再跑 G1R、G2R、G3（90 次）。见 Prompt 8 的分阶段说明。
- 写进 PROGRESS 后停下，等用户确认再进入 Prompt 8。

## 4. 测试与记录
- local_dev_v1：最低空闲低于 100 MiB 时不停止但标 memory_tight；模拟 OOM 时批次停止、失败保留；耗时突增时记 possible_memory_spill；旧策略的 plan 行为不变。
- dfg_v2/tests 全部、旧 DDG 回归通过。结论写进 PROMPT7C_REPORT.md 与三份记录文档。
```

### 4.9h 以后执行：迁移到服务器（本地结果出来后，由用户决定何时开始）

迁移后，Prompt 8 的全部训练（含 G0）都在服务器上重新运行，不与本地结果混用；资源策略恢复为 100 MiB 门槛。以下为迁移步骤。


```text
# 服务器迁移（以后执行）：服务器环境复现、输入迁移与身份核验、GPU 冒烟、8 次 pilot

前置：本地 Prompt 8 的结果已经出来，用户决定迁移。迁移后的全部训练（含 Prompt 8 的每一次）都在同一台服务器、同一块 GPU 型号上进行，不与本地结果混用。

## 0. 先收集服务器信息（由用户提供，写进 PROGRESS）
- GPU 型号、计算能力（sm_XX）、显存；驱动版本与 nvidia-smi 显示的最高 CUDA 版本；
- 操作系统与 glibc 版本；是否有 conda；能否联网安装包；
- 是否能独占一块 GPU（多人共用时，其他人的任务会影响显存与耗时）；
- 可用磁盘空间（需要约 10 GB 以上：图、源码、tokenizer 资产与检查点）。
兼容性先判断：PyTorch 1.8.1+cu111 与 DGL 0.6.1 cu111 的预编译库支持到 Ampere（sm_80 A100、sm_86 RTX 30xx/A6000/A40）。Ada（sm_89，RTX 40xx/L40）与 Hopper（sm_90，H100）不在其中，能否靠 PTX 即时编译运行没有保证。若服务器是这两类 GPU，先停下报告，由用户决定换卡或另立环境升级方案（升级会改变数值环境，需要单独的等价性验收）。

## 1. 环境复现
- 在本地导出：conda env export --no-builds、pip freeze、python -c 打印 torch/dgl/numpy/networkx/transformers/tokenizers/tree_sitter 的版本与 torch.version.cuda；写入 artifacts/dfg_v2/prompt7c_v1/local_env/。
- 在服务器上用同一组版本建立 conda 环境 mando（Python 3.7.12、torch 1.8.1+cu111、dgl-cu111 0.6.1 等），不升级、不替换任何包。tree-sitter 的 Solidity 动态库（build/linux-x86_64 下的 .so）从本地拷贝并核对 SHA；若服务器 glibc 不兼容导致无法加载，在服务器上用仓库 vendor 中同一份 grammar 源码重新编译，并用 Prompt 5 的 cli verify 证明解析结果不影响已冻结图（训练本身不调用解析器）。
- 写 dfg_v2/experiment/env_check.py：逐项比较服务器与本地记录的包版本，任何不同都列出；只有用户批准的差异才能继续。
- GPU 冒烟：torch.cuda.get_arch_list() 是否包含服务器 GPU 的架构；在 GPU 上用 DGL 做一个小异构图的前向与反向；HGTLayer 与 HGTLayerSharedProjection 各一次。

## 2. 输入迁移与身份核验
已封存的清单里写的是本地绝对路径（/home/zhao/SmartContract/ge-sc-llm/... 与 /home/zhao/SmartContract/ge-sc-llm-ddg-v11/...），例如 tasks.py 的注册表、inputs/manifest.json、graphs_v2_r1/store.json、各 plan。为了不改动任何已封存文件，在服务器上复现同样的绝对路径（目录不归 zhao 时可用符号链接把这两个路径指到实际位置），不要改写清单中的路径。
- 写 dfg_v2/experiment/transfer.py：
  - collect：从 graphs_v2_r1/store.json、inputs/manifest.json、prompt7b4_v1/pilot/plan.json 出发，递归收集它们引用的全部文件（原 HCG、源码与元数据 CSV、标签、nested 折、prepared 清单、tokenizer 资产、F1–F3 图、audit、plan 的 prepared/initial 文件与 seal），写出 transfer_manifest.json（绝对路径、大小、SHA256）并打包；
  - verify：在服务器上逐个核对路径与 SHA，缺一个或不符一个都失败。
- 代码：在服务器上 clone dfg-v2，检出与本地相同的提交；git 跟踪文件的 SHA 与本地 before_tracked 记录一致。
- 在服务器上运行 cli verify（store）与 run verify --plan（只读，允许未完成）。

## 3. 服务器上的数值与资源检查
- 新 plan：artifacts/dfg_v2/prompt7c_v1/pilot/，用 run plan --from-plan 引用 prompt7b4_v1/pilot/plan.json，沿用同一 prepared/initial 文件（不重新随机初始化），登记服务器的 GPU 型号、驱动、包版本与资源策略。逐项对照证明只有环境与资源字段不同。
- 共享投影与原实现的 GPU 对照（AC 节点 fold0 的 G0、G3R，3 轮）：original 两次的噪声与 shared 一次，门槛 max(1e-4, 3 × 噪声)。这验证的是服务器 GPU 上的同一结论，不是重新证明等价。
- 与本地 GPU 历史 history.jsonl 的对照只报告、不作门槛：不同 GPU 型号的浮点累加不同，3 轮后有小差异是正常的。所有正式比较都在服务器内部进行。
- 资源策略沿用：启动前基线空闲 ≥ 3000 MiB；运行中整卡最低空闲 ≥ 100 MiB；多卡机器用 CUDA_VISIBLE_DEVICES 固定一块卡，预检核对 UUID。

## 4. 8 次 pilot（服务器）
- reentrancy_contract/0/1/G3R 先跑，之后其余 7 项，每项独立进程、--only 串行。全部 shared_projection。
- 检查项与 Prompt 7b 第 5 部分相同：训练文件中有边的新 canonical（含 REV_*）第一轮 relation_msg 梯度非零，只在内层验证或外层测试中出现的单独计数；env_source 不出现在任何指标与预测中；best/last 重载后 logits 逐位一致；每项的基线、上下文占用、peak allocated/reserved、整卡最低空闲、每轮耗时、停止轮数、总耗时。
- 不报告 F1 比较结论。

## 5. Prompt 8 时长估算与停止
- 用服务器上 8 次实测耗时按任务估算批次 1（合约 5 折 × 5 剖面，节点 10 折 × 5 剖面）；G1R、G2R、G3 按 canonical 数在 G0 与 G3R 之间线性插值，标明是估计。
- 写进 PROGRESS 后停下，等用户确认再进入 Prompt 8。

## 6. 测试与记录
- transfer.py：缺文件、SHA 不符、路径不同时 verify 失败；collect 的结果覆盖 store/inputs/plan 引用的全部文件（用小型合成清单测试）。
- env_check.py：版本不同时列出差异并拒绝。
- dfg_v2/tests 全部、旧 DDG 回归分别在本地与服务器上通过。结论写进 PROMPT7C_REPORT.md 与三份记录文档。
```


（Prompt 7c 状态：2026-10-26 已完成并验收，提交 79d40da。资源策略 local_dev_v1 经用户批准；8/8 pilot 完成，0 失败、0 重试，全部从冻结的未训练初值开始。只有重入合约 G3R 标 memory_tight（最低空闲 81 MiB），无 OOM、无 possible_memory_spill。四个 G3R 共 266 个训练支持 canonical 第一轮梯度全部非零，12 个只在留出集中出现的单列；8 项 best/last 重载 logits 逐位一致；env_source 未进入任何预测。Prompt 8 本地时长估计：阶段 A 约 5.8 小时、阶段 B 约 9.0 小时、合计约 14.8 小时。Codex 对 7c 背景中"已发生显存换出"的推断作了正确的限定：不同时刻的数值相加不能证明换出。）

### 4.10 Prompt 8：R/AC 实验与统计

先按阶段 A（G0、G3R，60 次）→ 阶段 B（G1R、G2R、G3，90 次）跑完批次 1；诊断组和补种子都要你确认才跑；其余 5 类只写扩展说明。

```text
# Prompt 8：R/AC 实验与统计（本地，资源策略 local_dev_v1）

前置：Prompt 7c 已完成（提交 79d40da）。先 git pull --ff-only origin dfg-v2，运行 cli verify（graphs_v2_r1/store.json）与 run verify（prompt7c_v1/pilot/plan.json）。
所有训练在本机进行；以后迁移到服务器时整批重跑，不与本地结果混用。全部剖面 layer_impl=shared_projection、reducer=mean（批次 2 除外）、inside_token 特征。
协议 dfg-v2-nested-v1：inner_train 更新参数，inner_val 早停并选 best，训练结束后才评估 outer_test。这与历史 paper_kfold 协议不同，加上层实现的反向累加顺序不同，G0 的结果不能与历史 F1 直接比较；报告中写明。

## 0. 批次执行器（新增 experiment/batch.py，不改 trainer 与数值规则）
- 把 Prompt 7c 的 execute_pilot.py 整理为正式模块：python -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan <plan> --stage A|B。
- 按 plan 中登记的顺序，每个 job 一个独立子进程（调用 run execute --only），单 GPU 串行。
- 成功且 verify 通过的 job 直接跳过（可断点续跑）；任何 job 失败（OOM、非有限值、校验失败）就停止整个批次，保留失败现场，需用户确认后用 --retry 从同一未训练初值重跑。
- 日志排他创建，不覆盖。
- 顺序：阶段内按 任务 → 折 → 剖面 排列（同一折的各剖面相邻），这样中途停止时已完成的部分仍是完整的配对。

## 1. plan（一次性写入批次 1 的全部 150 次并封存）
- 命令：run plan --store graphs_v2_r1/store.json --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node --profiles G0,G1R,G2R,G3R,G3 --seeds 1 --layer-impl shared_projection --resource-policy local_dev_v1 --approval-record <prompt7c_v1/local_policy_approval.json> --output artifacts/dfg_v2/prompt8_v1/batch1
- plan 中登记：阶段划分（A：G0、G3R；B：G1R、G2R、G3）与执行顺序、第 2 部分的主要终点、第 4 部分的选择规则与补种子条件、第 5 部分的统计方法。封存后不能修改。
- 不复用 Prompt 7c 的 8 次 pilot：它们在 plan 封存之前运行，按预先登记的原则不进入正式结果；fold0 的 G0、G3R 在本批次中重新训练。pilot 的 F1 在本步结束前不打开、不报告。
- 磁盘：每次 fit 保存 best.pt 与 last.pt（含优化器状态），按 pilot 实测大小估算 150 次的总量；plan 时检查剩余空间至少是估算值的 2 倍。
- 时长：在 PROGRESS 中写出按 Prompt 7c 实测的估计（阶段 A 约 5.8 小时、阶段 B 约 9.0 小时），等用户确认后才执行 execute。

## 2. 预先登记的主要终点与中间报告
- 主要终点：G3R 相对 G0 在外层测试上的 Buggy-F1（best checkpoint），按任务报告；节点任务（10 折）做配对 Wilcoxon，合约任务（5 折，最小 p 值 0.0625）只作描述性比较。
- 阶段 A 完成后，运行 batch interim --stage A：只生成 G3R 与 G0 的对比报告（第 5 部分中与这两个剖面有关的全部表格），文件名与标题都标"中间结果"，并把报告的 SHA 写入批次记录。
- 中间报告不改变 plan、选择规则或阶段 B 的执行；G* 只在阶段 B 完成后由 select 按第 4 部分的内层验证规则计算。
- 中间报告之后停下，把结果交给用户，用户确认后再执行阶段 B。

## 3. 阶段 B 与汇总
- batch execute --stage B；完成后 run verify、run select（写并封存 selection.json）、run summarize（selection.json 不存在时拒绝）。

## 4. 预先登记的选择规则（写进 plan 后不能修改）
- G* = 四个任务的内层验证 Buggy-F1（每折取 best checkpoint 在内层验证集上的值，每个任务先对折取平均）的算术平均最高的剖面。候选只包括 G1R、G2R、G3R、G3。若与第二名的差距小于 0.1pp，选关系更少的那个。外层测试分数不参与选择。
- 补种子触发：G* 与 G0 的四任务平均内层验证 Buggy-F1 之差的绝对值 ≥ 0.2pp。
- 报告中五个剖面的外层测试结果全部列出，并注明 G* 的选择基于内层验证。

## 5. 统计 dfg_v2/experiment/stats.py（任务列表由参数传入，不写死类别）
- 每个 (任务, 剖面)：各折的均值 ± 样本标准差；多种子时先对折取平均，再报告种子间的均值 ± 标准差。best 为主表，last 另列一表。指标：Buggy-F1、Macro-F1、Precision、Recall。
- 配对比较：
  - 每个剖面 vs G0；另加 G3R vs G3（方向消融）；跑了批次 2 时加 G3RM vs G0M。
  - 配对单位为折（多种子时为 (折, 种子)）。
  - scipy.stats.wilcoxon 双侧检验，零差值用 zero_method="zsplit" 并在报告中写明；同时报告 Vargha-Delaney A12，以及配对差的均值与 95% bootstrap 置信区间（10000 次，seed 0）。
  - 每个任务内 4 个"剖面 vs G0"的比较做 Holm 校正。
  - 合约任务只有 5 折，配对 Wilcoxon 的最小 p 值为 0.0625；单种子下合约任务只作描述性比较，报告中写明。
- pooled OOF：把外层测试预测按任务汇总，计算一次总体 Buggy-F1 与 Macro-F1。
- 机制统计（节点任务）：G0 错而 G* 对、以及 G0 对而 G* 错的节点中，有多少落在 v2 新增关系的 1 跳/2 跳范围内，按关系分解。
- 标签争议文件（R buggy_18、R buggy_36、AC buggy_18、AC buggy_26，以及 artifacts/targeted_label_review_v1 中列出的文件）单独一张表；主表另给一个"排除这些文件"的敏感性结果。
- 若用户已填写 review_v1 / review_v1b，用 score_review 的结果在报告中加一节"依赖边人工抽查精确率"；未填写就写"未完成"。
- 解释上的提醒写进报告：历史 F1 已在 94%–96% 附近，单种子、5 折合约任务的差异可能很小，以置信区间与配对方向为主，不以单一点估计下结论。
- 输出 <批次>/REPORT.md（全部表格用 markdown）与对应 CSV。

## 批次 2：聚合诊断（可选，批次 1 结束后由用户决定）
- 前置检查：nonempty_mean 的共享投影在 7b.2 中只完成了 float64 静态检查，3 轮轨迹因 CPU 内存被跳过，GPU 上也没有比较过。先在 GPU 上对 AC 节点 fold0 的 G0 与 G3R 做 original 两次与 shared 一次的 3 轮对照，门槛 max(1e-4, 3 × 噪声)，通过后才执行。
- G0M 与 G3RM（G0 和 G3R 配 reducer="nonempty_mean"），seed 1，共 60 次。时长按批次 1 中 G0、G3R 的实测估计。
- G3RM − G0M 与 G3R − G0 的对比，用来区分"新关系的信息"与"跨关系平均分母变化"两种效应。

## 批次 3：补种子（由 selection.json 中预先登记的条件决定是否触发，再经用户确认执行）
- G0 与 G* 再跑 seed 2、3：2 × 2 × 30 = 120 次。种子按 Prompt 7 第 4 部分的规则派生（constructor 另加 100000 × (seed − 1)）。
- 所有种子用同一套冻结折；同一 (任务, 折, 种子) 下 G0 与 G* 共享初值。

## 可选组（用户确认后才跑）
node_feature="nodetype" 下的 G0 与 G3R，seed 1，共 60 次。需先按 Prompt 7 第 4 部分实现固定的节点类型词表。

## 以后扩展到其余 5 类（现在不执行）
在 PROGRESS.md 末尾写一段说明，按 scripts/DFG/dfg_v2/EXTENDING.md 的步骤：注册新类别 → Prompt 0 中该类的锚点与 token 核对 → 生成并封存折 → cli build --tasks <新类> → run plan --tasks <新类> --profiles G0,<G*> --seeds 1。G* 沿用 R/AC 上按上面规则选出的剖面，不在新类别上重新挑选。

## 停止条件
- 任何 job 失败、OOM 或 verify 不通过，就停下报告，不自动重试。
- 阶段 A 的中间报告之后、阶段 B 的汇总之后，都先停下，把结果交给用户；用户同意后再进入下一步。
```



（Prompt 8 准备状态：2026-10-26，提交 64f6b35。150 项 plan 已封存（plan SHA 07f1dbc9…、seal SHA 55aebf92…），150 份全新未训练初值与 30 个剖面家族验收通过；正式训练 0/150。用户批准的两项：另建本批次授权记录（不扩大 7c 批准的范围）；合约 5 折只作描述，节点用 zsplit 双侧 Wilcoxon，阶段 A 报原始 p，Holm 在阶段 B 完成后做。审查确认：选择规则的 F1 以百分数计（0.1pp 容差的单位正确）；"关系更少"实现为所有 job 的 canonical 数之和更少，再按剖面名，已随 plan 封存。）

### 4.10a Prompt 8A：执行阶段 A 并出中间报告

```text
# Prompt 8A：执行阶段 A（G0、G3R，60 次）与中间报告

前置：Prompt 8 计划已封存（prompt8_v1/batch1/plan.json，SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de）。先 git pull --ff-only origin dfg-v2，运行 cli verify 与 batch verify（应报告 0/150 完成，且计划、初值与 seal 一致）。

## 1. 授权记录
用户的阶段 A 授权原文写入 prompt8_v1/batch1/stage_A_authorization.json（新文件，排他创建），字段包括：授权原文、授权时间、plan SHA、seal SHA、stage="A"、job 数 60、资源策略 local_dev_v1、execution_authorized=true、stage_B_authorized=false。不修改 batch_authorization.json。

## 2. 执行
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A --authorization-record scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/stage_A_authorization.json
- 每项独立子进程，按 plan 中的顺序串行；任何失败（OOM、非有限值、校验失败）立即停止整批，保留现场，不自动重试，等用户确认。
- 运行中只记录进度（已完成 job 数、每项耗时、memory_tight、possible_memory_spill），不打开、不汇总任何 F1，直到 60 项全部完成并通过 verify。

## 3. 验收与中间报告
- batch verify --stage A：60 项全部通过（checkpoint、binding、初值、预测身份、env_source 排除、best/last 重载逐位一致、训练支持 canonical 的首轮梯度非零）。
- batch interim --stage A：生成 REPORT_INTERIM_A.md 与 CSV，标题与文件名标"中间结果"；只比较 G3R 与 G0；报告 SHA 写入批次收据。
- 报告内容按 Prompt 8 第 5 部分中与这两个剖面相关的部分：每任务 best/last 的折均值 ± 样本标准差（Buggy-F1、Macro-F1、Precision、Recall）、逐折配对差与提升/持平/下降计数、配对差均值与 95% bootstrap 区间、A12、节点任务的原始 Wilcoxon p（合约任务只描述）、pooled OOF、标签争议文件敏感性表、节点任务的 1/2 跳机制统计、实测耗时与显存汇总。
- 写入 PROGRESS 与三份记录文档后停下。不执行阶段 B，不计算 G*。

## 4. 停止条件
- 任何 job 失败、OOM 或 verify 不通过：停下报告。
- 中间报告完成后停下，把报告交给用户；阶段 B 需要用户另行授权。
```



（Prompt 8A 状态：2026-10-27 已完成，提交 a26f801、dc909c7。阶段 A 60/60 通过逐项与整阶段验收，0 失败、0 重试；中间报告 REPORT_INTERIM_A.md（SHA 55933fa8…）已封存，结果文本已归档到 Git，.pt 权重留在本地。主要终点（best 外层 Buggy-F1，G3R − G0，百分点）：重入合约 +1.43（1 升 4 平 0 降，只描述）、重入节点 +0.51（10 折全部提升，原始 Wilcoxon p = 0.00195）、访问控制合约 +0.80（1/3/1，只描述）、访问控制节点 −0.20（2/5/3，p = 0.61）。审查已按逐折表复算全部均值与差值，并按混淆矩阵复算 pooled OOF，数字一致。耗时：execute 墙钟 9.32 小时，其中真正的训练轮次计算约 1 小时，其余主要是重复验收与检查点处的深度校验，见 Prompt 8B.0。）

### 4.10b Prompt 8B.0：去除重复验收与重复深度校验（不改训练数值），并为阶段 B 登记修订

```text
# Prompt 8B.0：执行器性能修订与等价性证明

前置：Prompt 8A 已完成（提交 dc909c7）。先 git pull --ff-only origin dfg-v2。
本步不训练正式 job，不修改 trainer 的数值规则、HGT 层、模型、初始化、优化器、图、标签与折。

## 背景：阶段 A 的 9.3 小时花在哪里（审查根据已归档的 process/started/result/history 记录计算）
| 部分 | 秒 | 占比 | 是否必要 |
|---|---:|---:|---|
| 子进程启动后、写 attempt.started 之前（主要是对此前所有 job 的重复验收） | 14,467 | 43% | 绝大部分不必要 |
| 训练结束后的评估与 8 次检查点重载（每次重载前后都做深度校验） | 7,265 | 22% | 大部分不必要 |
| 每次保存 best 时额外的校验与写盘（764 次，中位每次约 7.3 秒，图越大越慢） | 约 5,200 | 16% | 大部分不必要 |
| 训练轮次本身（1,271 轮，不保存的轮中位约 2.9 秒） | 约 3,700 | 11% | 必要 |
| 模型构造等其他进程内时间 | 2,251 | 7% | 部分必要 |
| 父进程在 job 之间的验收 | 409 | 1% | 可保留 |
日志不是原因：每个 job 的终端日志只有 15–25 行。

三个具体原因：
1. 重复验收随 job 数线性增长。每个新 job 启动时，batch.authorize_job 对同阶段此前的每个 job 调用 _accept → run._completed → _verify_attempt；随后 run.execute 在 local_dev_v1 下又对 plan 中所有已启动的 job 调用一次 _completed。_verify_attempt 会重新计算该 job 所有产物的 SHA256，包括每个约 60–80 MB 的 best.pt 与 last.pt。阶段 A 中这段时间从第 1 个 job 的 14 秒增加到第 60 个的 400 秒，斜率约每个已完成 job 6.9 秒。阶段 B 照此运行时，run.execute 还会扫描阶段 A 的全部 60 个 job，仅这一项估计约 13–14 小时。
2. 每次保存检查点都做整图深度校验。experiment/checkpoint.py::save_checkpoint 先调用 validate_binding（其中 dfg_v2.model.validate_registration 的 deep 分支会重新从 NetworkX 图生成边数据、标签、文件池化行，并调用 sco_models.graph_utils.get_node_token，它对每个节点做一次 torch.cat，耗时随节点数平方增长；同时重新计算图、折、标签文件的 SHA），再调用 native.snapshot_input 重新计算整个模型输入的指纹。这些输入在训练中不会变化，但每次 val loss 创新低都要重做一遍。
3. 训练结束后，inner_val 与 outer_test 各对 best、last 重载两次（共 8 次），每次 restore_checkpoint 前后各做一次 validate_binding，native.restore_checkpoint 内部还会 assert_model_input，同样是整图深度校验。

## 1. 修订内容（只改 experiment/ 下的编排与校验代码）
a) 验收结果缓存：
   - 某个 job 第一次通过完整的 _verify_attempt 与 audit 后，写 acceptance_seal.json（排他创建），内容为：receipt.json 的 SHA、全部产物的路径/SHA/字节数/mtime_ns、验收代码版本、验收时间。
   - 之后需要确认"此 job 已成功"时：核对 seal 文件自身的 SHA、receipt 的 SHA，以及每个产物的字节数与 mtime_ns 与 seal 一致；不再重新计算大文件的 SHA。任一不一致就回退到完整验收。
   - 阶段结束时的 batch verify、run select、run summarize 仍对每个 job 做完整验收（重新计算全部 SHA），保证最终结论的证据强度不变。
b) 去掉 run.execute 中重复的已启动 job 扫描：失败检测只需要判断"有 attempt_*.started.json 而没有成功 receipt"，不需要对成功的 job 重做完整验收；成功的 job 使用 a) 的缓存。authorize_job 与 run.execute 不再各自扫描一遍。
c) 一个进程内只做一次深度校验：
   - fit 开始前照常做完整的 validate_binding 与 snapshot_input，并记下模型输入相关张量（各类型 inp、图的边索引、监督 mask、标签张量）的 data_ptr 与 _version 计数，以及 graph/folds/labels 文件的 SHA（本进程只计算一次）。
   - 之后每次保存与重载前后，只核对这些张量的 data_ptr 与 _version 没有变化，以及 schema 与 binding 字段相同；任何变化就立刻做完整校验并报错。
   - 训练结束后、开始评估前，再做一次完整校验；评估完成后、写 receipt 前再做一次。这样每个 fit 有三次完整校验（开始、训练后、结束），而不是约 20–30 次。
   - native.restore_checkpoint 内部的 assert_model_input 不改原文件；在 dfg_v2 的包装中改为：读取检查点后核对其中保存的 model_input 与本进程开始时的 snapshot 完全相同（字典比较，不重算指纹），再加载 state_dict。
d) 可选，先测再决定：GPU 显存采样间隔从 0.5 秒改为 1 秒，各测一个 job 比较耗时；差异小于 2% 就保持 0.5 秒不变。
不做：不改 best 的保存规则与检查点格式（仍在每次 val loss 创新低时写 best.pt）；不改 patience、轮数与评估方式；不复用进程（仍然每个 job 一个新进程）。

## 2. 等价性证明（必须全部通过）
- 选两个阶段 A 已完成的 job：access_control_node/0/1/G0 与 access_control_node/0/1/G3R（Prompt 7b.3 中 AC 节点在本机 GPU 上重复运行的损失差为 0）。
- 在一个新的、仅用于证明的目录中，用新代码、同一份冻结初值、同一 fit seed 重新训练这两个 job（不写入 batch1，不计入正式结果）。
- 要求：history.jsonl 中每一轮的 train/inner_val 损失、best_epoch、last_epoch 与阶段 A 记录完全相同；best/last 的 state_dict 张量摘要与阶段 A 相同；inner_val 与 outer_test 预测逐行相同。若 GPU 在这两个 job 上不是逐位确定的，改为与"旧代码在同一证明目录中再跑一次"的结果比较，并报告两者差异与 7b.3 噪声水平的关系；不能逐位相同时停下报告。
- 计时对比：新旧代码各自在这两个 job 上的总耗时、启动前时间、保存检查点的平均额外时间、训练后评估时间。
- 再用合成 20 文件批次测试：缓存命中、产物被改动（字节数或 mtime 变化）时回退到完整验收并报错、seal 被篡改时报错、张量 _version 变化时报错；stage 结束的完整 verify 仍重新计算全部 SHA。

## 3. 阶段 B 的计划修订登记
- 阶段 B 仍使用同一个 plan（prompt8_v1/batch1/plan.json）的 job 列表、初值、配置、选择规则与统计方法，不重新随机初始化，不改动任何预先登记的内容。
- 因为编排与校验代码变了，写 stage_B_amendment.json（排他创建），内容：修订原因（上表）、变更的文件清单与新旧 SHA、证明"训练计算相关文件逐字节未变"（trainer.py、model.py、hgt_layer.py、model_input.py、init.py、protocol.py、support.py、supervision.py 以及 sco_models 下被导入的文件）、第 2 部分的等价性证明结果的 SHA、用户批准原文。
- batch 执行器在阶段 B 读取并核对该修订记录，再检查 plan 绑定的 runtime 中，只有修订清单里的文件发生了变化；其余任何文件变化都拒绝执行。阶段 A 的结果不重新运行。
- 用实测的新耗时重新估计阶段 B 的总时长，写进 PROGRESS，等用户授权。

## 4. 测试与记录
- 新增测试见第 2 部分末尾；dfg_v2/tests 全部、旧 DDG 回归通过。
- 结论写进 PROMPT8B0_REPORT.md 与三份记录文档。
```

### 4.10c Prompt 8B：执行阶段 B、选择 G* 与完整报告

```text
# Prompt 8B：阶段 B（G1R、G2R、G3，90 次）、select、summarize

前置：Prompt 8B.0 已完成，修订记录 stage_B_amendment.json 已获用户批准；用户的阶段 B 授权原文写入 prompt8_v1/batch1/stage_B_authorization.json（排他创建，绑定 plan 与 seal 的 SHA、修订记录的 SHA、job 数 90、资源策略 local_dev_v1）。

## 1. 执行
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage B --authorization-record <stage_B_authorization.json> --amendment <stage_B_amendment.json>
- 每项独立子进程、按 plan 顺序串行；任何失败就停止整批，保留现场，等用户确认后才 --retry。
- 运行中只记录进度，不打开、不汇总任何 F1。

## 2. 验收、选择与完整报告
- batch verify --stage B，然后 run verify（150/150，完整重算全部 SHA）。
- run select：按封存规则只读内层验证选出 G*，写并封存 selection.json。
- run summarize：生成完整 REPORT.md 与 CSV，内容按 Prompt 8 第 5 部分：
  - 五个剖面的 best/last 折均值 ± 样本标准差（Buggy-F1、Macro-F1、Precision、Recall）；
  - 每个剖面 vs G0 的配对比较（提升/持平/下降、配对差均值与 95% bootstrap 区间、A12、节点任务的 Wilcoxon 原始 p 与每任务 4 个比较的 Holm 校正 p）；G3R vs G3 方向消融；
  - pooled OOF、错误变化、标签争议文件敏感性、节点任务 1/2 跳机制统计（用 G*）；
  - 若阶段 A 中间报告的 G3R − G0 与完整报告的 G3R − G0 有任何差别，说明原因（应完全相同，因为是同一批 fit）；
  - 人工抽查表若已填写，加入精确率一节；未填写写"未完成"；
  - 是否满足补种子条件（只记录，不执行）。
- 写入 PROGRESS 与三份记录文档后停下，把完整报告交给用户。批次 2、批次 3 与服务器迁移都需要用户另行决定。
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
