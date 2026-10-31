# MANDO-LLM 节点语义增强（NodeSem v1）：方案与 Codex 编码 Prompts

日期：2026-10-31。作者：Claude（方案与审查），实现：Codex。
分支：`node-sem`（从 `dfg-v2@ffc48d79` 切出）。全部新代码、文档与产物都在 `scripts/node_sem/` 下，不与 `scripts/DFG/` 混合。

本文依据：
- 「Mando-LLM paper analysis」对话中的节点增强原方案（M1 代码编码、M2 数据流上下文、M3a 静态画像、M3b LLM 描述、M3c 蒸馏、M4 融合）。
- 当前对话对原方案的审查，以及其中采纳的图片方案、ORACAL 要点。
- `dfg-v2` 分支上已完成的 DFG v2 代码、Prompt 0–8H 的报告，以及 `REVIEW_8B_LABELS_AND_LEAKAGE.md`。
- 用户 2026-10-31 的决定（第 2 节）。

---

## 1. 与节点增强有关的现状

### 1.1 DFG v2 已经提供的输入

- **图**：`graphs_v2_r1/store.json`，按正向关系分为 F0–F3。F0 直接引用原作者图。
- **剖面**：G0、G1R、G2R、G3R、G3。G3R = 四种正向关系（`DATA_DEF_USE`、`WRITES_STATE`、`READS_STATE`、`ENV_FLOW`）加各自的 `REV_*`。
- **辅助节点**：只有 `env_source` 一种。L2 的状态变量中转点是**已有的声明节点**，不是新增节点（原审查中“state_variable 辅助节点”的说法有误，此处更正）。
- **原节点属性**共 9 个：`code`、`label`、`method`、`node_info_vulnerabilities`、`node_source_code_lines`、`node_type`、`source_file`、`token`、`type_label`。其中 `code` 来自作者清洗后的文件（去掉了注释和空行）。
- **节点类型**：`contract_declaration`、`function_definition`、`constructor_definition`、`modifier_definition`、`new_variable`、`expression_statement`、`return`、`if`、`end_if`、`for`、`while`、`end_loop`、`continue_statement`、`library_declaration`、`interface_declaration`、`struct_declaration`，以及辅助节点 `env_source`。
- **模型**：`dfg_v2/model.py::make_model` 构造模型，`node_feature` 只支持 `inside_token` 和 `nodetype`。前向沿用作者代码：`h = gelu(adapt_ws[ntype](inp))`。

### 1.2 基准 v2 协议（8D–8H 建立，本方案沿用）

- **特征视图 N-anon-s**：文件内按拼写一一对应的全标识符改名，保留表中的名字（msg、sender、tx、origin、call、value、transfer 等）不改。8G 已为全部 HCG 节点生成改名后的 `code`（`benchmark_v2/anon_parity.py::node_code_view`）和改名后的源码。
- **折**：8D 的分组外层折（重复与近重复样本分在同一组）及冻结的内层 train/val。合约任务 5 折，节点任务 10 折。
- **标签 L-audit**：节点任务的 target 使用 C1；`C2_include=false` 的节点不进入 loss、早停、best 选择和主指标。合约标签不变。
- **执行器**：`benchmark_v2/execution.py`（plan、seal、授权、每个 fit 一个独立进程、receipt、verify）。初值由 `experiment/init.py::initialize_family` 按语义对齐共有参数。训练配置见 8H：Adam + OneCycle，50 轮，patience 7。
- **资源**：seed=1，本机 RTX 3050 4GiB，资源策略 local_dev_v1。170 个 fit 的纯训练时间约 4.8 小时。

### 1.3 推动节点增强的证据

**8H 结果（L-audit，best，折均 BF1%）：**

| 任务 | G0 | G3R | G3R − G0 |
|---|---:|---:|---|
| 重入节点（DFG 主终点） | 98.09 | 99.12 | +1.04，10/10 折提升，Holm p=0.0078 |
| 访问控制节点 | 97.71 | 98.35 | +0.64（只作描述） |
| 重入合约 | 93.68 | 95.02 | +1.34（只作描述） |
| 访问控制合约 | 91.02 | 93.01 | +1.99（只作描述） |

G\*（按内层验证选出）是 G3。

**节点特征的已知缺陷：**
1. 现有特征是 token ID 序列，被当作 512 维浮点数直接送进线性层，取值约 0–32k。
2. Prompt 5 的注意力探针显示，第一层注意力几乎是单邻居的：`next_line` 96–99%、`READS_STATE` 98.6–99.8% 的 head 最大权重 ≥0.99。
3. 8C/8D 显示这种特征对位置变化极其脆弱：只换一个名字的长度，F1 就从约 96% 降到 10–38%。

**语义缺口（8B 审查与 8H）：**
- 访问控制关键字基线 BF1=99.5（已饱和），重入为 85.6。
- 访问控制真实正例只检出 2/20。phishable 和 mycontract 中的 `require(tx.origin == owner)` 被漏掉：SolidiFI 模板用 tx.origin 与**参数**比较，这两个文件用它与**状态变量**比较。
- 图中缺少三类信息：
  - 守卫对敏感操作的支配关系；
  - modifier 的应用关系（modifier 调用在 HCG 中没有节点）；
  - 构造函数身份（构造函数名写错的漏洞）。

### 1.4 约束

- 训练环境：Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、transformers 4.30.2、tree_sitter 0.20.4，离线运行。
- 本机 4GiB 显存。现代 LLM 推理无法在 mando 环境中运行。

---

## 2. 已确定的决策

1. **主视图**：基准 v2（N-anon-s + 分组折 + L-audit）是唯一主终点。原名视图是预先登记的次要终点，必须报告，但不据此下结论（DFG 对话第 98 轮的建议，用户 2026-10-31 确认“不设为共同主终点”）。
2. **运行位置**：全部先在本机运行，包括 LLM 部分的小模型试点。正式实验以后在服务器上复跑，本机与服务器的结果不混合。
3. **代码位置**：新文件夹 `scripts/node_sem/`，新分支 `node-sem`。只通过 import 复用 `scripts/DFG/**`，不修改其中任何文件。
4. **编译与 IR**：当前沿用 MANDO-LLM 的思路，不依赖编译。以后计划做一个让全部合约都能编译的组件。M3a 的事实提取设计为可替换后端：现在用 AST 后端；有了编译组件后，可以加 IR（如 SlithIR）后端，输出同一份事实 schema。本版不实现 IR 后端。

---

## 3. 对原方案的修订与理由

| # | 项目 | 原方案 | 修订后 | 理由 |
|---|---|---|---|---|
| 1 | 基础图与关系名 | “G2 图”，`data_dep`/`reads_state` 等 | 用 F3 图的 `DATA_DEF_USE`/`READS_STATE`/`WRITES_STATE`/`ENV_FLOW` 边；特征实验在 G0 和 G3R 上做 | 与已实现的 DFG v2 一致。G3R 是预先登记的 DFG 主终点剖面；G\*=G3 只作参考 |
| 2 | 协议 | 5 seed、`folds_s.json`、全部做 Wilcoxon | 基准 v2：分组嵌套折、L-audit、seed=1、只用内层验证做选择；节点任务做 Wilcoxon，合约任务只描述；Holm 校正 | 与 DFG 结果可比，避免事后挑选 |
| 3 | token ID 核查 | 第一步核查 | 已经确认是原始 ID，删除这一步 | Prompt 0/4/5 已证实 |
| 4 | 新增基线 F1 | 无 | 可学习的 token 嵌入加掩码平均池化 | DFG 对话中提出的最小修正。能区分两件事：增益来自“正确处理 ID”，还是来自预训练知识 |
| 5 | 文本视图 | 原代码 | 主视图用 N-anon-s 改名后的文本；次要视图用原文 | 去掉 SolidiFI 的 `re_ent`/`txorigin` 名字通道 |
| 6 | 位置信息 | M2 中写绝对行号（`@L57`） | 不写绝对行号，只写函数内的相对距离 | 绝对行号可能与注入位置相关，构成捷径 |
| 7 | M2 后继（图片方案） | 只有来源 `FROM` | 新增 `TO`：本语句定义的值流向哪里，并按汇点类型标注（调用金额或参数、守卫条件、状态写、返回） | “值成为转账金额”“值进入 require”正是重入与访问控制需要的信号。REV 边让 HGT 看到邻居，但看不到邻居中的角色 |
| 8 | 守卫的操作数类别 | 守卫涉及 owner 类变量 | 改为结构类别：env（msg.sender/tx.origin）、状态变量、参数、局部变量、字面量、调用结果，并记录比较双方的类别组合 | 改名视图里没有“owner”这个名字。“tx.origin 对状态变量”与“tx.origin 对参数”正好区分 phishable 与 SolidiFI 模板 |
| 9 | modifier 与构造函数 | 只有“受修饰器保护” | 新增：函数应用了哪些 modifier（同文件内按拼写解析到 modifier 定义）、该 modifier 体内是否有基于 msg.sender/tx.origin 的守卫；函数名是否等于合约名、是否使用 constructor 关键字 | 8B/8C 指出这三类信息在图中完全缺失。N-anon-s 是文件内双射，名字相等关系保留 |
| 10 | 局部语法（图片方案） | 无 | M3a 增加约 12 维 AST 语法袋（赋值种类、delete、emit、selfdestruct、成员访问深度、下标、字面量、new、三元） | 便宜、确定、与名字无关 |
| 11 | 辅助节点 | 占位文本加零向量 | `env_source` 的文本就是它的键（如 `msg.sender`）；M3a 只置“环境量”字段 | 与 8G 中 env_source 特征不变的做法一致 |
| 12 | 存在位 | 无 | 每个模态一个存在位；缺失时为 0，模态 dropout 时也置 0 | 区分“缺失”与“真的为零” |
| 13 | 归一化 | 无 | 每个模态先过 LayerNorm 再投影 | 原始 ID 的尺度导致注意力饱和，新特征不能重复这个问题 |
| 14 | PCA | 每折用 PCA 降到 128 | 取消 PCA，改为融合模块中可学习的逐模态线性投影 | 每个任务约 1.3–1.8 万节点，显存不是问题；也省去按折拟合 PCA |
| 15 | 融合接入点 | 修改 forward | 用一个按模态切分输入的模块替换 `adapt_ws[ntype]`；forward、HGT 层、池化全部不改 | 作者 forward 只调用 `adapt_ws[n_id](inp)`，替换模块即可，不需要复制或改写 forward |
| 16 | 初值 | 未规定 | 共有参数（gcs、classify）从 8H 同一（任务、折、剖面）的零步初值复制；新模块用按名字派生的种子初始化 | 与 8H 的配对初值设计一致，特征对比更干净 |
| 17 | 无图对照（ORACAL） | 只列为风险 | 正式配置：HGT 层数为 0，只有融合加分类层 | ORACAL 只用增强文本时效果很差；需要验证图结构仍然有贡献 |
| 18 | LLM 环境 | 本地 7B | 本机用 3B 级代码指令模型（GGUF 4-bit，llama.cpp，JSON 语法约束）做试点；服务器换更大的模型，代码不变 | 4GiB 显存放不下 7B；mando 环境（py3.7）也无法运行现代 LLM |
| 19 | LLM 输入 | 函数源码 | 主视图用改名并去注释后的函数，在函数内再按首次出现顺序重新编号；提示中的相对行号由 AST 生成，并保存行号到节点的映射 | 8G 的改名源码保留注释，需要另外去掉；函数内重新编号后，跨文件的重复函数可以共用缓存 |
| 20 | 提取环境 | 未规定 | 特征提取（编码器、LLM、句向量）在用户准备的离线环境 `nodesem` 中运行，只输出带 SHA 的文件；训练仍在 mando 环境，只读取这些文件 | 不改 mando 环境，也不被 py3.7 限制 |
| 21 | 不采纳：IR | — | 本版不用，后端接口留空 | 见第 2 节第 4 条 |
| 22 | 不采纳：RAG、ORACAL 的安全分析字段、按中心性选 50 个节点 | — | RAG 不用；安全分析字段只作为 F7 对照；不选节点，全量覆盖 | RAG 检索漏洞知识会把描述推向判断；函数级调用已经让全量覆盖可负担 |
| 23 | 不采纳：边描述 | — | 留给第三个创新点（边语义增强） | 属于边的范围 |

---

## 4. NodeSem v1 方案

### 4.1 总体结构

```
F3 图（DFG v2）+ 源码 AST（N-anon-s 视图；次要视图为原文）
 ├─ M0 token ID（现有 512 维）──────────────→ 可学习嵌入 + 掩码平均池化（F1）
 ├─ M1 节点代码文本 → 冻结代码编码器 → e_code
 ├─ M2 DFG 上下文序列化文本 → 同一编码器 → e_ctx
 ├─ M3a 静态行为画像（AST 后端；以后可加 IR 后端）→ b_static（约 75 维）
 └─ M3b 函数级 LLM 行为描述 → 句向量 → t_sem（教师，只在训练期使用）
       M3c 按折训练的学生 MLP([e_ctx; b_static]) → s_sem
 → M4 按模态切分的融合模块（替换 adapt_ws）→ 原 HGT（2 层，G0 或 G3R）→ 节点/合约分类
```

### 4.2 通用规则

- **允许读取的节点属性只有：** `code`、`node_type`、`source_file`、`node_source_code_lines`（只用于对齐，不作为特征）。
  - 禁止读取 `label`、`type_label`、`node_info_vulnerabilities`、`token` 以外的 token 派生值、任何预测。
  - 用白名单实现，并写测试：对这些禁止属性做随机扰动，特征必须逐位不变。
- **主视图的文本**一律来自 8G 的改名结果（`node_code_view` 和改名后的源码）。次要视图来自原文。两个视图使用同一套代码，只有输入不同。
- **任何特征文本中都不出现绝对行号或文件名。** 位置一律用函数内的相对距离表示。
- **分析器只基于源码 AST**，经 `scripts/DFG/projection.py::Projector`（或 `dfg_v2/projection_view.py`）按 AST 身份投影到 HCG 节点。不按行号或“最近节点”猜测；投影不到的事实丢弃并计数。
- **特征文件**：每个（视图、任务）一份 NPZ，加一份 manifest。
  - manifest 记录行顺序（与 `original_graph_node_id` 一一对应）、每行的 code SHA、维度、dtype、实现文件 SHA、模型资产 SHA。
  - 装配方式参照 `benchmark_v2/spelling_features.py::assemble`：核对图指纹、行身份与顺序，不改原图。
- **缓存键**：文本 SHA + 编码器或 LLM 资产 SHA + 提示 SHA。

### 4.3 M0 / F1：可学习的 token 嵌入

- 输入就是现有的 512 个 token ID（N-anon-s 视图的特征，见 8G NPZ）。浮点值必须是精确整数，否则报错。
- 结构：`Embedding(32100, 128, padding_idx=0)`，按非零位置做掩码平均。
  - 第一个位置是特殊符号，保留，不单独处理。
  - 全为填充的行输出零向量，并把存在位置 0。
- 词表大小从冻结的 tokenizer 资产读取并核对，不写死数字。

### 4.4 M1：节点代码编码

**编码文本按节点类型截取：**

| 节点类型 | 编码文本 |
|---|---|
| `expression_statement`、`new_variable`、`return`、`continue_statement` | 完整语句 |
| `if`、`while`、`for` | 只取条件（for 取 init;cond;update 头部），不含 body |
| `function_definition`、`constructor_definition`、`modifier_definition` | 签名（含可见性、modifier 列表、returns），不含函数体 |
| `contract_declaration`、`library_declaration`、`interface_declaration` | 头部，如 `contract v3 is v7` |
| `struct_declaration` | 完整声明（通常很短） |
| `end_if`、`end_loop` | 固定文本 `<END_IF>`、`<END_LOOP>` |
| `env_source` | 环境键文本，如 `msg.sender` |

- 截取用 AST 身份完成：在对应视图的 ProjectionView 上找到节点的 AST，取条件或签名子节点的范围。
- Prompt 0 先核实 `if`、`function_definition` 等节点的 `code` 是否确实是整棵子树。截取失败时回退为完整 `code`，并计数报告。

**编码器：**
- 主编码器：`Salesforce/codet5p-110m-embedding`（256 维，与 MANDO-LLM 的 codet5p tokenizer 同族，专为代码检索训练）。
- 备选编码器：UniXcoder（768 维），在以后的批次中作为对照。
- 编码器冻结，最大长度 128，fp16 推理，相同文本只编码一次。
- 模型权重由用户下载到本地并登记 revision 和文件 SHA。Codex 不得联网下载。

### 4.5 M2：DFG 上下文序列化

字段顺序固定，内容全部来自 F3 图的边和源码 AST，确定性生成，不用 LLM：

```
[STMT] v12 . v3 -= v9 ;
[FUNC] function v4 ( uint v9 ) public payable
[DEF] v12.v3 : state
[USE] v12 : local @-1 | v9 : param
[FROM] @-1 : var v12 = v2 [ msg.sender ] ;
[TO] -
[STATE_R] -
[STATE_W] v3
[ENV] -
[PRE_EXT_CALL] @-2 : msg.sender.call.value ( v9 ) ( )
[GUARD] require ; env:msg.sender==state ; @-3
```

| 字段 | 内容 | 来源 |
|---|---|---|
| `STMT` | M1 的截取文本 | 节点 |
| `FUNC` | 所在函数的签名 | AST 函数归属 |
| `DEF`、`USE` | 变量及类别（state、local、param、env） | `DATA_DEF_USE` 边的拼写属性 + AST 参数表 + L2/L3 边 |
| `FROM` | 来源语句，最多 2 条，按函数内相对距离标注 | `DATA_DEF_USE` 入边 |
| `TO` | 去向，最多 2 条；按汇点类型标注：`call_arg`、`call_value`、`guard`、`state_write`、`return` | `DATA_DEF_USE` 出边 + 目标节点的 AST 角色 |
| `STATE_R`、`STATE_W` | 读写的状态变量 | `READS_STATE`、`WRITES_STATE` |
| `ENV` | 环境键 | `ENV_FLOW` |
| `PRE_EXT_CALL` | 同一函数内、控制流上在本语句之前的外部调用 | 函数内 CFG 可达性 |
| `GUARD` | 支配本语句的最近一个守卫（require/assert/if/modifier），及其操作数类别组合 | 函数内 CFG 支配关系 |

- **CFG**：优先复用 `scripts/DFG/semantic_cfg.py` 或 `dfg_v2/l1_cfg.py` 的 AST 级 CFG，经投影映射到节点。Prompt 0 先确认它们能否给出语句级的后继关系和函数入口。不能时，用 HCG 自身的 CFG 边（`next_line`、`pos_next`、`neg_next` 等）作后备，并在 PROGRESS 中说明。
- **长度预算**：256 个 token（按编码器自己的 tokenizer 计数）。超出时按以下顺序截断：
  1. 删 `TO` 的第二条；
  2. 删 `FROM` 的第二条；
  3. `GUARD` 只保留类型与类别组合；
  4. `FUNC` 只保留可见性和 modifier 个数。
  
  `STMT`、`DEF`、`USE` 永远保留。每类变量最多 5 个。
- **编码**：与 M1 用同一个编码器，得到 `e_ctx`。

### 4.6 M3a：静态行为画像（AST 后端，约 75 维）

全部由 AST 和 F3 图的边算出。用独热或多热编码；计数类字段用 0/1/多个三档。

| 组 | 字段 | 约维度 |
|---|---|---|
| A 外部交互 | 无；低层 call；delegatecall；staticcall；send；transfer；成员调用（目标未知）；附带 value | 8 |
| B 状态访问 | 写状态（0/1/多）；写的是 mapping/数组元素还是标量；读状态（0/1/多） | 8 |
| C 顺序 | 可从同函数的外部调用到达；被外部调用支配；本语句写状态且之后有外部调用；本语句是外部调用且之后有写状态 | 4 |
| D 守卫 | 被 require/assert 支配；被 if 条件支配；所在函数应用了 modifier；该 modifier 体内有基于 msg.sender/tx.origin 的守卫；无守卫；守卫操作数含 msg.sender、tx.origin、状态变量、参数、字面量、时间戳/区块号；比较组合为 env 对状态变量、env 对参数 | 14 |
| E 环境量 | msg.sender、msg.value、tx.origin、时间戳、区块号、其他（按 L3 的 14 个键分组） | 6 |
| F 调用返回值 | 不适用、被检查、被赋值未检查、被忽略 | 4 |
| G 算术 | + − × ÷ ** %；是否作用于状态变量 | 7 |
| H 循环 | 不在循环内、常量边界、状态变量或数组长度边界、参数边界 | 4 |
| I 函数上下文 | 可见性（4 类）；payable；view/pure；是构造函数（constructor 关键字，或函数名等于所在合约名）；应用了 modifier | 8 |
| J 语法袋 | `=`、`+=`、`-=`、其他复合赋值、delete、emit、selfdestruct/suicide、成员访问深度 ≥2、下标访问、字面量、new、三元 | 12 |

- **“函数名等于合约名”**在 N-anon-s 下仍然可算，因为改名是文件内双射。测试要覆盖这一点：原文和改名视图得到的 M3a 必须逐位相同。
  - 例外：如果某个字段依赖保留名以外的拼写，Prompt 3 必须列出并说明。
  - 按设计，M3a 不应依赖任何具体名字，所以两个视图的 M3a 应完全一致，这是一条强校验。
- **modifier 解析**：在同一文件的 AST 中，按拼写把函数头中的 modifier 调用解析到 modifier 定义；继承链复用 `stage_j/binding.py::ClosedScopeJ`。解析不到的计为“unknown”，不猜测。
- **后端接口**：`FactBackend.extract(file) → StatementFacts`（schema 固定，见 Prompt 3）。现在只实现 `AstBackend`。以后的 IR 后端只需输出同一个 schema。

### 4.7 M3b：LLM 行为描述（只描述，不下判断）

- **调用粒度**：每个函数（含 modifier、构造函数）调用一次，一次返回该函数内所有语句的描述。
- **输入**：
  - 主视图：改名且去掉注释的函数文本（去注释在 AST 上做，不用正则），再在提示内按首次出现顺序重新编号为 `a1, a2, …`；
  - 加上同一合约的状态变量声明，用同一套重新编号；
  - 每行加函数内相对行号前缀。行号到 HCG 节点的映射由 AST 生成并保存。
- **缓存**：以“重新编号后的提示文本 SHA + 模型资产 SHA + 提示模板 SHA”为键。跨文件的重复函数（SolidiFI 模板）只调用一次。
- **输出**：JSON，由 llama.cpp 的 JSON schema 语法约束。
  - `function_intent`（≤20 词）；
  - 每条语句：`line`、`role`（固定词表，与原方案相同）、`summary`（≤20 词）、`reads`、`writes`、`external`。
- **系统提示的硬约束**：
  1. 只描述代码做什么；
  2. 禁止使用 vulnerability、reentrancy、exploit、attack、unsafe、risk、bug、overflow、insecure、malicious、vulnerable、secure 等词；
  3. 不确定时写 `"unknown"`；
  4. 只输出 JSON。
- **过滤**：
  - 黑名单命中的条目丢弃，并记录比例；
  - 解析失败或行号对不上的条目丢弃；
  - 忠实性：`reads`/`writes`/`external` 与 M2/M3a 的事实比对（名字按重新编号的映射还原，只在至少一方非空的字段上计分），一致率低于 0.5 的节点教师向量置空。
  - 以上各项比例写进 stats.json，作为论文数据。
- **教师向量**：`role + summary + function_intent` 拼接后，用 `BAAI/bge-small-en-v1.5` 编码（384 维），不降维。
- **F7 对照**：另一个提示模板，允许增加 `security_note` 字段，不做黑名单过滤，编码为 `t_judge`。只用于 S7 对照，文件名和 manifest 上明确标注 `control_judgement`。
- **本机试点**：
  - 3B 级代码指令模型的 GGUF Q4（例如 Qwen2.5-Coder-3B-Instruct），llama.cpp（llama-cpp-python 或 llama-server），n_ctx 4096，温度 0，固定 seed；
  - 先在 50 个函数上做试点，统计耗时、解析成功率、黑名单命中率和忠实性，再决定是否全量运行；
  - 服务器上换成 7B–14B 的模型，代码不变，只换资产和 manifest。
- **原名视图的 LLM 运行**留到服务器。本机只跑主视图。

### 4.8 M3c：按折蒸馏的学生

- 对每个（视图、任务、外层折）单独训练学生：
  - 只用该折 inner_train 节点的教师向量训练；
  - 用 inner_val 节点做早停；
  - 训练完成后给该任务全部节点生成 `s_sem`。outer_test 节点的教师向量从不进入训练。
- **结构**：MLP `[e_ctx; b_static] → 512 → 384`，GELU，dropout 0.1。
- **损失**：余弦距离；加上从 `s_sem` 预测 `role` 的交叉熵，权重 0.3。教师为空的节点不参与。
- **训练**：AdamW，lr 1e-3，最多 30 轮，按 inner_val 余弦损失早停。在 mando 环境的 CPU 上运行即可，种子由（任务、折）确定。
- **报告**：每折 outer_test 节点上学生与教师的余弦（只作诊断，不参与选择）。如果余弦很低，预期 F5≈F4。

### 4.9 M4：融合（替换 adapt_ws，不改 forward）

- **输入布局**：`inp = [存在位 (M 维) | 模态 1 | 模态 2 | …]`。模态的顺序和维度由 FeatureSpec 决定，写进 manifest 和 checkpoint binding。
- **NodeSemAdapter**（每种节点类型一个，代替 `nn.Linear`）：
  - 按布局切分 `inp`；
  - token ID 模态走 M0 的嵌入池化，其余模态先 LayerNorm（二值的 b_static 不归一化）再 `Linear(d_m, 128)`；
  - 融合方式：
    - `concat`（默认）：`Σ_m p_m · z_m + b`，`p_m` 是存在位。数学上等价于对拼接特征做一次线性变换；
    - `gated`：`g = softmax(W_g [p_1 z_1; …; p_M z_M])`，存在位为 0 的模态 logit 置为 −inf 后再归一化；全部模态都缺失时输出零向量，不得出现 NaN；`h = Σ g_m z_m`。保存 `last_gates` 供分析；
  - 输出交给作者 forward 中原有的 `gelu`。
- **模态 dropout**（只在训练时）：每个节点每个模态以 0.1 的概率把存在位置 0。node_type 不作为模态，因为 `adapt_ws` 本身就按节点类型分开。随机数由 fit 种子派生，可复现。
- **F0 等价**：FeatureSpec 只含原始 token ID 模态、`raw_linear` 方式时，NodeSemAdapter 必须退化为与原 `Linear(512,128)` 完全相同的计算和参数布局，用来做与 8H 的逐位等价证明。
- **初值**：
  - `gcs.*`、`classify.*` 从 8H 同一（任务、折、剖面）的零步初值复制；
  - 新模块的参数用 `experiment/init.py::parameter_seed(anchor_seed, 名字, 身份)` 派生的生成器初始化，不消耗全局随机数；
  - 记录每个初值的 SHA。
- **无图对照 F4-noG**：基于 G0 图构造（不含辅助节点），同一个融合模块，`layers=0`（`h` 直接进 classify；合约任务照常池化）；classify 从 8H 的 G0 初值复制。Prompt 1 先确认作者 forward 在 0 层时能正确运行；不能时，在 node_sem 中写一个最小子类，只改层数循环，并给出等价测试。

### 4.10 环境与存储

| 环境 | 用途 | 谁准备 |
|---|---|---|
| mando（现有） | 文本视图与 M2/M3a 事实（tree-sitter）、装配、训练、学生、统计 | 已有 |
| nodesem（新） | M1/M2 编码（transformers + torch 2.x）、M3b（llama.cpp）、教师句向量 | 用户按 Prompt 2/7 的清单准备；Codex 只核验，不安装、不联网 |

- `scripts/node_sem/offline/` 下的脚本在 nodesem 环境运行，可以用较新的 Python 语法，但 mando 环境的代码不得 import 它们。两边只通过带 SHA 的文件交换数据。
- 产物目录：`scripts/node_sem/artifacts/<批次名>/`，拒绝覆盖已存在的目录。

### 4.11 实验设计

**特征配置**（主视图；图为 G0 或 G3R）：

| 编号 | 模态 | 推理时用 LLM | 回答的问题 |
|---|---|---|---|
| F0 | 原始 token ID（8H） | 否 | 基线；直接复用 8H 的 G0/G3R 结果 |
| F1 | 可学习 token 嵌入 | 否 | 只修正 ID 的处理方式，能提升多少 |
| F2 | M1 代码向量 | 否 | 预训练知识的贡献 |
| F3 | F2 + M2 | 否 | DFG 上下文的贡献 |
| F4 | F3 + M3a（**确定性主方案**） | 否 | 静态行为画像的贡献 |
| F4g | F4，gated 融合 | 否 | 融合方式 |
| F4-noG | F4，0 层 HGT | 否 | 图结构是否仍然有贡献 |
| F5 | F4 + 学生 `s_sem`（**LLM 主方案**） | 否 | 蒸馏后的意图语义 |
| F6 | F4 + 教师 `t_sem` | 是 | 上限：F5 保留了多少 |
| F7 | F4 + 带判断的 `t_judge` | 是 | 判断性内容有多少是泄漏 |
| F8 | F5，但 `s_sem` 在同一任务同一节点类型内随机置换 | 否 | 增益是否来自真实语义 |

**批次与估计**（本机，seed=1，4 个任务共 30 折；每个 fit 约 100 秒，以 Prompt 5 的实测为准）：

| 批次 | 内容 | fit 数 |
|---|---|---:|
| N-A | {F1, F2, F4} × {G0, G3R}（F0 复用 8H） | 180 |
| N-B | F3 × G3R、F4g × G3R、F4-noG | 90 |
| N-C | {F5, F6, F7, F8} × G3R（LLM 本机试点版） | 120 |
| N-D | 原名视图 {F0, F4} × G3R（次要终点） | 60 |

**预先登记的终点：**
- **主终点（N-A）**：重入节点、G3R 上的 F4 − F0（L-audit，best，外层 BF1，10 折配对）。
- **同一 Holm 家族**：F1 − F0、F2 − F0、F4 − F2（均为重入节点、G3R）。
- **交互项（描述性）**：(F4 − F0) 在 G3R 与 G0 上的差，检验节点增强与 DFG 是否互补。
- **N-C 的主比较**：重入节点、G3R 上的 F5 − F4。同一家族：F6 − F5、F7 − F6、F5 − F8。本机试点版只作预备结果，正式结论以服务器复跑为准。
- **访问控制节点**：只作描述，因为已被关键字饱和。另外预先登记一个定性诊断：20 个非 SolidiFI 真实正例的逐节点概率表，特别是 phishable 与 mycontract 的 `require(tx.origin == owner)`。
- **两个合约任务**：只作描述。
- **F\***：用 inner_val 按 8H 的规则选择，只作参考，不替换主终点。

**每个批次的报告必须包含：**
- 原标签、全部原 HCG 节点上的辅助结果；
- last 检查点的辅助结果；
- SolidiFI 与非 SolidiFI 分层（非 SolidiFI 只报 pooled 计数和 Wilson 区间）；
- 与关键字基线的对比；
- 第一层注意力 head 最大权重的分布（复用 `dfg_v2/attention_probe.py` 的方法，只做 eval 前向）；
- gated 配置下各节点类型的门控权重；
- 资源与耗时；
- 与 8H 的对照。

### 4.12 风险与应对

1. **M1 编码器可能见过 SolidiFI 或 SmartBugs。** 主视图是改名后的代码，可以减轻但不能消除，写进局限部分。
2. **本机 3B LLM 的描述质量可能不足**，F5≈F4。这不影响 N-A 的结论。服务器复跑时换更大的模型。
3. **语义特征压过结构**：用 F4-noG 和模态 dropout 来检验。
4. **访问控制已经饱和**：结论只能来自重入；访问控制只看真实正例的定性表。
5. **单 seed、折之间共享训练数据、完整固定图前向是传导式设定**：与 DFG 相同，论文结论需要服务器上的多 seed 复跑。
6. **M3a 可能被质疑“针对标签设计”**：所有字段都是通用的语句行为，没有一个读取标签；两个视图逐位一致的校验，以及 F4 − F3 的消融，都写进论文。

---

## 5. Codex Prompts

### 5.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文（NodeSem v1）

## 项目
在 MANDO-LLM 私有仓库上实现节点语义增强（NodeSem v1），复用已完成的 DFG v2（scripts/DFG/dfg_v2，包括 benchmark_v2 执行器）。方案全文在 scripts/node_sem/PROMPTS.md，有疑问先查它。

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。第一次开始前：
  git fetch origin node-sem
  git checkout -b node-sem origin/node-sem
之后的提交都在 node-sem 上。不要 push，除非用户明确要求。每个 Prompt 开始前先 git pull --ff-only origin node-sem，读取最新的 PROMPTS.md。

环境（WSL，训练与图处理）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
  export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、transformers 4.30.2、RTX 3050 4GiB。
mando 环境中的代码必须兼容 Python 3.7：不要用 :=、list[str] 这类运行时注解、dict | dict、dataclass(slots=...)。
离线提取环境 nodesem 由用户准备（见 Prompt 2/7），其代码只放在 scripts/node_sem/offline/，mando 代码不得 import 它。

## 新代码位置
- 代码：scripts/node_sem/（含 __init__.py）
- 测试：scripts/node_sem/tests/
- 产物：scripts/node_sem/artifacts/<批次名>/，拒绝覆盖已存在的目录（允许作为未跟踪路径出现在 git status 中）
- 进度：scripts/node_sem/PROGRESS.md，每个 Prompt 结束追加一节（做了什么、文件清单、测试命令与结果、验收数字、遗留问题）。同时在 HANDOVER.md 与 docs/training_changes_2026-10-07.md 末尾追加简短记录（只追加）。

## 禁止修改
1. scripts/DFG/** 下的全部文件（包括 dfg_v2 与 benchmark_v2，其中多个 seal 绑定了源码 SHA）。
2. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py。
3. 所有已有产物、图、标签、折、特征、初值、checkpoint、plan/seal（包括 prompt8h_v1）。
复用时用 import、子类化或组合。必须改变某个冻结函数的行为时，把它复制到 scripts/node_sem，在文件头写明来源路径和原文件 SHA256，并加一条测试，证明它在旧输入上与原函数输出相同。禁止用 types.FunctionType 重新绑定字节码。

## 不变量
- 原图的节点、节点顺序、属性、边完全不变。特征只在内存副本上装配。
- 特征提取只允许读取 code、node_type、source_file、node_source_code_lines（只用于对齐）以及图的边。禁止读取 label、type_label、node_info_vulnerabilities、任何预测或标签文件。有测试保证这一点。
- 任何特征文本中都不出现绝对行号或文件名。
- AST 事实按 AST 身份投影到节点，投影不到的事实丢弃并计数，不按行号猜测。
- 主视图文本来自 8G 的 N-anon-s 改名结果；次要视图来自原文。两个视图用同一套代码。
- 训练沿用基准 v2 协议：8D 分组折、L-audit 标签、seed=1、local_dev_v1、8H 的训练配置。outer_test 只在训练结束后评分。

## 关键可复用模块
- scripts/DFG/dfg_v2/model.py（make_model、_construct、validate_registration）、model_input.py、hgt_layer.py
- scripts/DFG/dfg_v2/benchmark_v2/execution.py（create/load/construct/binding_parts/fit_one/verify_one/controller）、trainer.py、audit_supervision.py、grouping.py、reporting.py、runtime_model.py、checkpoint.py
- scripts/DFG/dfg_v2/benchmark_v2/spelling_features.py（build_features、assemble：特征 NPZ 与 manifest 的格式范例）、anon_parity.py::node_code_view、prepare_spelling.py（load_result、改名源码）、spelling_names.py（保留表）
- scripts/DFG/dfg_v2/experiment/init.py（initialize_family、parameter_seed、seeds）、stats.py
- scripts/DFG/dfg_v2/attention_probe.py
- scripts/DFG/dfg_v2/projection_view.py、scripts/DFG/projection.py::Projector、scripts/DFG/frontend.py、scripts/DFG/semantic_cfg.py、dfg_v2/l1_cfg.py
- scripts/DFG/state/stage_j/binding.py::ClosedScopeJ（同文件继承链）
- scripts/DFG/dfg_v2/tokens.py::TokenEncoder

## 工作方式
- 每个 Prompt 只做该 Prompt 的范围。代码事实与本文不一致时，以代码为准，在 PROGRESS.md 记录差异与处理方式。
- 每个 Prompt 结束时运行：scripts/node_sem/tests、scripts/DFG/dfg_v2/tests，以及
  python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
  全部通过后 git commit，提交信息写明 Prompt 编号（NS-Pn）。
- 除了明确写着“训练”的步骤，不启动任何 HGT 训练。正式批次必须先有用户的授权记录。
- 失败就停，保留现场，不自动重试，不自行换方案。
```

### 5.2 Prompt NS-P0：侦察（只读）

```text
# NS-P0：侦察（只读，不写算法代码）

在 scripts/node_sem/RECON.md 中写清以下事实，每条都附命令、文件路径与 SHA。

## 1. 输入身份
- 8H 计划 prompt8h_v1/plan/plan.json 的 SHA、四个任务的 G0/G3R 图引用、8G 特征 manifest（original/anonymous 两个视图）、L-audit 标签视图、分组折文件。
- 8H 中 F0 = {G0, G3R} × 30 折的 receipt 与零步初值：位置、数量（应为 60）与 SHA。确认可以按引用复用。

## 2. 节点文本
- 在四个任务中，各抽查 if、for、while、function_definition、constructor_definition、modifier_definition、contract_declaration 节点：code 是否为整棵子树文本，是否带 pydot 引号。
- 用 node_code_view 得到 N-anon-s 视图的节点文本，确认覆盖全部原节点（每个任务的数量）。
- 用 ProjectionView 加 Projector 找到每个节点的 AST，统计能否取到 if/while/for 的条件子节点、函数签名范围（按类型统计成功数和失败数）。

## 3. DFG 边的属性
- F3 图中 DATA_DEF_USE、READS_STATE、WRITES_STATE、ENV_FLOW 的方向（源与目标的节点类型）、边属性键（例如 spellings、via_alias）与示例。
- env_source 节点的属性与键文本。

## 4. CFG 来源
- semantic_cfg.py 或 dfg_v2/l1_cfg.py 能否给出“语句级后继 + 函数入口”，并映射到 HCG 节点；覆盖多少函数。
- HCG 自身 CFG 边的类型与覆盖率，作为后备。
- modifier_definition 节点是否存在于四个任务中；函数头中的 modifier 调用能否按拼写在同文件 AST 中解析到定义（统计成功、失败、继承）。

## 5. 源码与注释
- 8G 改名后的源码是否保留注释（预期保留）；
- 用 tree-sitter 的 comment 节点去注释后，重新解析是否 ERROR=0；
- 统计函数总数（含 modifier、构造函数），以及按函数内首次出现顺序重新编号后去重的函数数（主视图）。

## 6. 训练路径的接入点
- 作者 forward 中 adapt_ws 的调用方式（逐行引用）；reset_parameters 对 adapt_ws 的处理。
- layers=0 时作者 forward 能否运行（只读分析，可以在小 fixture 上 CPU 构造验证，不训练）。
- benchmark_v2 中特征如何进入模型（assemble → token 属性 → _features），以及 checkpoint binding 中与特征有关的字段（feature_view、feature_npz）。
- initialize_family 对 node_feature 与参数名的限制，以及 parameter_seed 的签名。

## 7. 资源
- 8H 每个 fit 的训练时间与峰值显存（按任务和剖面汇总）。
- 由此估算第 4.11 节各批次的耗时。

## 验收
RECON.md 完整，PROGRESS.md 追加记录。不修改任何已有文件。
```

### 5.3 Prompt NS-P1：骨架、FeatureSpec、融合适配器与 F0 等价、F1

```text
# NS-P1：骨架、FeatureSpec、NodeSemAdapter、F0 等价证明、F1 可学习嵌入

## 1. 骨架
scripts/node_sem/__init__.py：VERSION、模态名常量（TOKEN_IDS、CODE、CTX、STATIC、STUDENT、TEACHER、TEACHER_JUDGE）。

## 2. FeatureSpec（feature_spec.py）
字段：view（anonymous / original）、modalities（有序列表，每项 name、dim、npz 引用、normalize）、token_mode（raw_linear / embed_pool / none）、fusion（raw_linear / concat / gated）、modality_dropout、layers_override（None 或 0）。
- to_json / from_json / digest。
- F0 = {TOKEN_IDS, raw_linear}；F1 = {TOKEN_IDS, embed_pool}。其他配置在后续 Prompt 中登记。

## 3. 输入装配（assemble.py）
- 读取各模态的 NPZ 与 manifest，参照 spelling_features.assemble 核对图指纹、行顺序、code SHA、dtype 与维度；拼接为 inp = [存在位 | 各模态]。
- env_source 行：TOKEN_IDS 用图中原有 token；其他模态按各自 manifest 中的辅助行；没有就存在位为 0、值为 0。
- 只改内存副本；原图指纹前后一致。

## 4. NodeSemAdapter（adapter.py）
- 按 FeatureSpec 切分输入。
  - raw_linear：与 nn.Linear(512,128) 完全相同的参数名、形状和计算。
  - embed_pool：Embedding(V, 128, padding_idx=0)，按非零位置掩码平均。V 从冻结的 tokenizer 资产读取。浮点 ID 不是精确整数时报错。
  - concat 与 gated 的接口先留空，NS-P4 实现。
- 模态 dropout 的接口（训练模式才生效，随机数由传入的 generator 决定）。

## 5. 模型构造（model.py）
make_nodesem_model(task, graph, profile, spec, device, ...)：
- 调用 dfg_v2.model.make_model 构造（node_feature="inside_token"），然后：
  - 把 graph 中各类型的 inp 替换为装配结果；
  - 把 model.adapt_ws 的每一项替换为 NodeSemAdapter；
  - 在 node_sem 的 validate_registration 中，复用原有检查，并改为对新 inp 核对。
- 不修改任何 dfg_v2 代码。
- 初值（init.py）：
  - gcs.*、classify.* 从 8H 同一（任务、折、剖面）的零步初值逐张量复制，并核对形状与 SHA；
  - 新模块用 parameter_seed 派生的 torch.Generator 初始化；
  - F0 时整个 state_dict 必须与 8H 初值逐位相同。

## 6. F0 等价证明（必须全部通过）
- CPU：任选 2 个 8H 的 fit（重入节点 fold0 G3R、访问控制合约 fold0 G0），分别用 8H 执行器与 node_sem 路径（F0）各跑 2 个 epoch，loss、参数、优化器状态、预测逐位一致。
- 为此在 node_sem 中写一个执行入口（execution.py）：复用 benchmark_v2 的 plan/binding/fit/verify 流程，只在构造模型处分派到 make_nodesem_model。checkpoint binding 增加 feature_spec 及其 digest 和各模态 NPZ 引用。

## 7. 测试（CPU、小 fixture）
- F0 适配器与 nn.Linear 逐位相同；
- embed_pool 的掩码平均（含全填充行）；
- 装配时，对行顺序、SHA、图指纹的篡改都会被拒绝；
- 禁止属性扰动后特征不变（白名单）；
- 初值复制与 SHA 校验。

## 验收
测试与第 6 节的等价证明通过；PROGRESS 记录。不跑正式训练。
```

### 5.4 Prompt NS-P2：文本视图与 M1 编码

```text
# NS-P2：节点文本视图（mando）与 M1 代码编码（nodesem）

## 0. 用户先完成的准备（Codex 不得自行安装或下载）
用户在 WSL 中新建 conda 环境 nodesem（Python 3.10，torch 2.x + CUDA，transformers，sentence-transformers），并下载：
- Salesforce/codet5p-110m-embedding（固定 revision）
- microsoft/unixcoder-base（备选）
- BAAI/bge-small-en-v1.5（NS-P7 用）
把模型目录与 revision 告诉 Codex。Codex 计算文件 SHA，写入 scripts/node_sem/offline/assets.json。

## 1. 节点文本（mando 环境，text_view.py）
- 对两个视图、四个任务，按第 4.4 节的规则为每个节点生成编码文本：截取通过 AST 身份完成，失败时回退为完整 code 并计数。
- env_source 节点的文本是环境键。
- 输出 text_<view>.jsonl 与 manifest：行顺序、node id、code SHA、文本、截取方式。
- 测试：
  - 原文视图与改名视图的截取方式逐节点相同；
  - 两个视图的文本在“改名双射还原”后逐字相同；
  - 不读取禁止属性。

## 2. M1 编码（nodesem 环境，offline/encode.py）
- 输入 text_<view>.jsonl，输出 emb_code_<encoder>_<view>.npz 与 manifest（资产 SHA、max_length=128、pooling、fp16、去重统计）。
- 同一文本只编码一次；输出 float32。
- 确定性检查：同一输入运行两次，逐位一致或最大误差 ≤1e-6（写明是哪一种）。

## 3. 装配检查（mando）
用 NS-P1 的 assemble 装配 F2 = {CODE, concat 占位}，只检查形状与行对齐，不训练。

## 验收
两个视图、四个任务的文本与主编码器向量齐全；PROGRESS 记录耗时与去重比例。
```

### 5.5 Prompt NS-P3：M2 上下文与 M3a 静态画像

```text
# NS-P3：StatementFacts（AST 后端）、M2 序列化、M3a 多热向量

## 1. 事实 schema 与后端（facts.py）
FactBackend.extract(file_view) -> {node_id: StatementFacts}。StatementFacts 包含：
- external_kind、value_attached；state_reads、state_writes（含 mapping/标量）；
- def_vars、use_vars（带类别）、from_nodes、to_nodes（带汇点类型）；
- reachable_from_ext_call、dominated_by_ext_call、write_before_later_call、call_before_later_write；
- guard（类型、操作数类别集合、比较组合、相对距离）、func_modifiers（解析结果）、modifier_has_sender_guard；
- env_keys、return_handling、arith_ops、loop_bound、visibility、payable、view_pure、is_constructor、syntax_bag；
- unresolved 计数。
只实现 AstBackend：
- CFG 按 NS-P0 的结论选择 semantic_cfg/l1_cfg，或用 HCG 后备；
- 支配关系用标准迭代算法；
- DEF/USE/STATE/ENV 来自 F3 图的边；
- modifier 解析复用 ClosedScopeJ，解析不到计为 unknown；
- 投影一律用 AST 身份。

## 2. M2 序列化（ctx_serializer.py）
- 按第 4.5 节的字段与顺序生成文本，相对距离写成 @-k / @+k，不写绝对行号。
- 长度预算按编码器 tokenizer 计数（用 nodesem 环境导出的 tokenizer 文件；mando 侧只做字符级上限，最终截断在 offline/encode.py 中按 token 完成，并记录截断级别）。
- 输出 ctx_<view>.jsonl。编码复用 NS-P2 的 offline/encode.py，得到 emb_ctx_<encoder>_<view>.npz。

## 3. M3a 多热向量（static_profile.py）
- 按第 4.6 节编码，固定字段表（behavior_schema.json：字段名、维度区间、取值）；
- 输出 static_<view>.npz（float32 0/1）与 manifest。

## 4. 测试（必须使用真实 tree-sitter 解析）
- 手写 Oracle 合约（放在 scripts/node_sem/tests/fixtures/，先写好期望再运行）。至少覆盖：
  - 低层 call 后写状态（重入）；
  - transfer 前写状态；
  - require(tx.origin == 状态变量)；require(tx.origin == 参数)；require(msg.sender == owner)；
  - 带 onlyOwner modifier 的函数（modifier 体内 require(msg.sender == owner)）；
  - 0.4 版本中函数名等于合约名的构造函数；
  - selfdestruct；未检查的 send 返回值；循环的状态变量边界；mapping 写与标量写。
- 视图一致性：四个任务中，原文与改名视图的 StatementFacts（名字按双射还原）和 M3a 向量逐节点相同。不一致必须逐条列出原因，不得放宽。
- 不读取禁止属性；输出中没有绝对行号。

## 5. 真实数据统计（不训练）
各字段在四个任务中的覆盖率、unresolved 比例、CFG 后备使用比例、modifier 解析成功率。

## 验收
测试与统计通过；PROGRESS 记录。
```

### 5.6 Prompt NS-P4：融合、无图对照与 CPU 证明

```text
# NS-P4：concat/gated 融合、模态 dropout、layers=0 对照、F1–F4 的 FeatureSpec 与 CPU 冒烟

## 1. 融合
- concat：每个模态先 LayerNorm（STATIC 不归一化）再 Linear(d_m, 128)，乘以存在位后求和，加偏置；
- gated：softmax 门控，存在位为 0 的模态 logit 置为 −inf；last_gates 只读保存；
- 模态 dropout：只在 model.training 时生效，用由 fit 种子派生的独立 generator，不消耗全局随机数。

## 2. 无图对照
layers_override=0：按 NS-P0 的结论，使用作者 forward 或最小子类；节点任务和合约任务都要能前向和反向。

## 3. 登记配置
F1、F2、F3、F4、F4g、F4-noG 的 FeatureSpec JSON 放在 scripts/node_sem/configs/。

## 4. CPU 证明与冒烟（不是正式训练）
- 每个配置在重入节点 fold0 G3R 上跑 1 个 epoch：
  - loss 有限；新模块参数有非零梯度；
  - gcs/classify 的初值与 8H 相同；
  - 记录显存估计（CPU 上用张量大小估算）。
- gated：每个节点的门控权重之和为 1；
- 模态 dropout：p=1 时所有模态的存在位都为 0，适配器输出只剩偏置项；gated 在全部模态缺失时输出零向量（加偏置），不得出现 NaN；
- 同一 fit 种子下，两次运行逐位一致。

## 验收
测试与冒烟通过；PROGRESS 记录。
```

### 5.7 Prompt NS-P5：批次 N-A 的计划与封存（不训练）

```text
# NS-P5：批次 N-A（{F1,F2,F4} × {G0,G3R}，180 个 fit）计划、封存与授权模板

- plan：任务、折、seed=1、剖面、FeatureSpec digest、各模态 NPZ 引用、初值（零步、记录 SHA），以及 F0 对 8H receipt 的引用（60 个，不重跑）。
- 预先登记（写进 plan，以后不能改）：
  - 主终点：重入节点、G3R、F4 − F0；
  - Holm 家族：F4−F0、F1−F0、F2−F0、F4−F2；
  - 交互项与其余任务只作描述；
  - F* 的选择规则（inner_val、各任务等权、平局取模态更少者）；
  - 报告的必含项（第 4.11 节）。
- 本机耗时与显存估计（基于 8H 实测与 NS-P4 冒烟）。
- 写出 authorization 模板（execution_authorized=false），停下等用户授权。
```

### 5.8 Prompt NS-P5A：执行 N-A 并报告

```text
# NS-P5A：执行 N-A（用户授权后）

- 把用户授权原文写入 authorization.json（排他创建），绑定 plan 与 seal 的 SHA。
- 开训前：在新 plan 上完整跑 2 个试点（重入节点 fold0 G3R 的 F4、重入合约 fold0 G0 的 F1），记录耗时与显存。试点结果计入正式产物。
- 串行运行剩余 fit，每项一个子进程。失败就停；运行中不汇总 F1。
- 完成后：verify 180/180；按预先登记的口径出 REPORT.md（含第 4.11 节的全部必含项，以及注意力饱和诊断）。然后停下。
```

### 5.9 Prompt NS-P6：批次 N-B

```text
# NS-P6：N-B（F3 × G3R、F4g × G3R、F4-noG，共 90 个 fit）

流程同 NS-P5/P5A：先计划与封存，等授权，再执行与报告。
预先登记的比较（全部只作描述）：F4 − F3、F3 − F2、F4g − F4、F4 − F4-noG。
另外报告 gated 配置下按节点类型的门控权重。
```

### 5.10 Prompt NS-P7：M3b LLM 描述（本机试点）

```text
# NS-P7：LLM 行为描述管线（nodesem 环境，本机试点）

## 0. 用户准备
在 nodesem 环境中安装 llama-cpp-python（CUDA 版本），或准备 llama-server；下载一个 3B 级代码指令模型的 GGUF Q4 文件。告诉 Codex 文件路径。Codex 记录 SHA 与运行参数。

## 1. 提示输入（mando 侧生成，llm_inputs.py）
- 对每个函数（含 modifier、构造函数）：
  - 主视图的改名源码，在 AST 上去掉注释；
  - 函数内按首次出现顺序重新编号为 a1…（保留表中的名字不改），加上同一合约的状态变量声明（使用同一套编号）；
  - 每行加函数内相对行号；保存（相对行号 → HCG 节点）的映射与编号映射。
- 按重新编号后的提示文本 SHA 去重。

## 2. 生成（offline/llm_describe.py）
- 温度 0，固定 seed，n_ctx 4096，用 JSON schema 语法约束输出；
- 提示模板 describe_v1（禁止判断）与 judge_v1（允许 security_note，只用于 F7）分别缓存；
- 先在 50 个函数上试点：报告耗时、解析成功率、黑名单命中率、忠实性分布。停下等用户确认后再全量运行。

## 3. 后处理（mando 侧，llm_post.py）
- 解析、行号映射、黑名单过滤、忠实性计算（与 StatementFacts 比对，名字按编号映射还原）；
- 输出 teacher_text_<view>.jsonl 与 stats.json。

## 4. 教师向量（offline/teacher_encode.py）
bge-small-en-v1.5 编码 role+summary+intent，得到 teacher_<view>.npz（384 维，缺失行的存在位为 0）。judge_v1 的结果另存为 teacher_judge_<view>.npz。

## 测试
- 去注释后重新解析 ERROR=0；
- 编号映射是双射，还原后与原函数一致；
- 行号到节点的映射与 AST 一致；
- 黑名单与忠实性计算使用固定 fixture。
```

### 5.11 Prompt NS-P8：M3c 学生与批次 N-C

```text
# NS-P8：按折蒸馏学生；N-C（{F5,F6,F7,F8} × G3R，120 个 fit）计划与封存

## 1. 学生（student.py，mando 环境 CPU）
- 按第 4.8 节实现。每个（视图、任务、外层折）一个学生：只用 inner_train 的教师向量训练，inner_val 早停；输出 student_<view>_<task>_fold<k>.npz。
- 断言：训练集与早停集中不含 outer_test 文件的节点；学生不读取标签。
- 诊断：outer_test 节点上学生与教师的余弦（只记录）。

## 2. F8 置换
在同一任务、同一节点类型内，用固定种子对 s_sem 行做置换；输出单独的 NPZ，并在 manifest 中记录置换。

## 3. 计划与封存
- 预先登记：主比较为重入节点、G3R 上的 F5 − F4；Holm 家族为 F5−F4、F6−F5、F7−F6、F5−F8。注明这是本机试点版本，正式结论以服务器复跑为准。
- 写授权模板，停下。执行流程同 NS-P5A。
```

### 5.12 Prompt NS-P9：原名视图（次要终点）与汇总

```text
# NS-P9：N-D（原名视图 {F0,F4} × G3R，60 个 fit）与 NodeSem 汇总报告

- 原名视图的 F0 使用 8G 的 original NPZ；F4 使用 NS-P2/P3 中原文视图的特征。
- 流程同 NS-P5/P5A。
- 汇总报告 NODESEM_REPORT.md：
  - N-A、N-B、N-C、N-D 的主表；
  - 主终点与各 Holm 家族的结果；
  - 交互项；
  - 访问控制的 20 个真实正例的逐节点概率表；
  - 注意力饱和与门控分析；
  - LLM 成本（调用次数、token 数、耗时）与忠实性；
  - 局限：单 seed、本机、传导式设定、SolidiFI 占主导、访问控制饱和、3B 试点模型。
- 原名视图只作描述性对照，不进入任何统计家族。
```

### 5.13 以后执行：服务器复跑

```text
# 服务器复跑（本机结果出来后由用户决定何时开始）
- 环境复现、输入迁移与 SHA 核验（参照 DFG PROMPTS.md 第 4.9h 节）。
- 用更大的 LLM 重跑 NS-P7，更新教师与学生；多 seed 重跑 N-A 与 N-C 的关键配置。
- 服务器结果单独封存，不与本机结果混合。
```

---

## 6. 里程碑

| 里程碑 | 包含 | 产出 | 需要用户决定的点 |
|---|---|---|---|
| M1 | NS-P0 | RECON.md | 截取或投影失败率过高时 |
| M2 | NS-P1–P4 | 特征管线、F0 等价证明、CPU 冒烟 | 准备 nodesem 环境与模型（NS-P2 第 0 节） |
| M3 | NS-P5/5A | N-A 的结果（主终点） | 授权 N-A |
| M4 | NS-P6 | N-B 的消融 | 授权 N-B |
| M5 | NS-P7–P8 | LLM 试点与 N-C | 准备 LLM；试点后确认全量运行；授权 N-C |
| M6 | NS-P9 | 原名视图与汇总报告 | 授权 N-D |
| 以后 | 服务器 | 正式多 seed 结果 | 何时迁移 |

即使 LLM 部分受阻，M3 和 M4（完全不依赖 LLM）也足以支撑一个完整的节点增强创新点：可学习嵌入、预训练代码向量、DFG 上下文和静态画像四个层次的消融，加上与 DFG 的互补性分析。
