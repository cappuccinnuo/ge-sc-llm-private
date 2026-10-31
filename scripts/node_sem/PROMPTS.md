# MANDO-LLM 节点语义增强（NodeSem v1）：方案与 Codex 编码 Prompts

版本：r3（2026-10-31）。作者：Claude（方案与审查），实现：Codex。

**r3 相对 r2 的修改**（DFG 侧审查补充，不改变方案结构与 NS-P0）：
- 离线 GPU 任务不得与训练并行，必须检查 GPU 锁（5.1 不变量）；
- 主终点处于天花板附近，主比较另报逐折错误数与相对错误减少率（只作描述）；
- 重入另附非 SolidiFI 正例与误报的逐节点表；
- LLM 试点允许在 CPU 上运行，以便与 N-A 并行。
分支：`node-sem`（从 `dfg-v2@ffc48d79` 切出）。全部新代码、文档与产物都在 `scripts/node_sem/` 下，不与 `scripts/DFG/` 混合。

**r2 相对 r1 的主要修改：**
1. 特征接入方式改为“token 属性载体”（第 4.9 节）。dfg_v2 的模型构造、注册校验、checkpoint 绑定、输入保护和 benchmark_v2 训练器全部原样复用，作者代码与 `scripts/DFG/**` 零改动。
2. 补上一个泄漏点：DFG 边上的拼写属性是原名，主视图必须先经 8G 的文件内双射映射成匿名名（第 4.2 节）。
3. 特征配置改名为 S0–S8，避免与图存储的 F0–F3 混淆。
4. Prompt 重写到函数、数据格式、调用顺序、测试和验收这一层，并借鉴了「Mando-LLM paper analysis」中 Prompt 1–9 的细节（Oracle 用例、LLM schema、忠实性公式、蒸馏防泄漏检查等）。

---

## 1. 现状（依据仓库代码与三份记录文档）

### 1.1 仓库结构与已有修改

- **作者代码**（`process_graphs/`、`sco_models/`、`node_classifier.py`、`graph_classifier.py`）中已有本地修改，按 HANDOVER 第 2 节和 DFG 共享上下文保持原样：
  - 调用边类型恢复、end_if/end_loop 修复、EarlyStopping 消息；
  - `reflect_graph` 的 DATA_DEF_USE 特判；
  - `model_hgt` 的 GRADIENT FIX。
  
  NodeSem 不再改作者代码。
- **DFG v2**：`scripts/DFG/dfg_v2/`（约 3.2 万行），以及 `benchmark_v2/`（8D–8H 的基准 v2 执行器）。

### 1.2 DFG v2 提供的输入

- **图存储**：`graphs_v2_r1/store.json`，F0（原作者图）到 F3。
- **剖面**：G0、G1R、G2R、G3R、G3。关系名为 `DATA_DEF_USE`、`WRITES_STATE`、`READS_STATE`、`ENV_FLOW` 及各自的 `REV_*`。
- **辅助节点**：只有 `env_source`。L2 的状态变量中转点是已有的声明节点。
- **原节点属性**：`code`、`label`、`method`、`node_info_vulnerabilities`、`node_source_code_lines`、`node_type`、`source_file`、`token`、`type_label`。
  - `code` 来自作者清洗后的文件，没有注释和空行。
  - `token` 是 float32[512]，存的是 codet5p-770m 的 token ID，右侧用 0 填充。
- **节点类型**：`contract_declaration`、`function_definition`、`constructor_definition`、`modifier_definition`、`new_variable`、`expression_statement`、`return`、`if`、`end_if`、`for`、`while`、`end_loop`、`continue_statement`、`library_declaration`、`interface_declaration`、`struct_declaration`、`env_source`。
  - modifier 调用在 HCG 中没有节点；modifier 定义有节点。

### 1.3 模型与训练路径（NodeSem 接入时依赖的代码事实）

**模型构造与前向：**
- `dfg_v2/model.py::_construct`：
  - `_features(model)` 对 `inside_token` 调用 `gu.get_node_token(model.nx_graph)`，读取每个节点的 `token` 属性；
  - `in_size` 取特征维度；
  - `adapt_ws = [nn.Linear(in_size, 128)]`，按节点类型各一个。
- 作者 forward 只做 `h[ntype] = F.gelu(self.adapt_ws[n_id](G.nodes[ntype].data['inp']))`，然后经过 `gcs` 和 `classify`。

**校验链：**
- `dfg_v2/model.py::validate_registration`（被 `benchmark_v2/runtime_model.py` 和 `benchmark_v2/checkpoint.py::validate_binding` 调用）会重新执行 `_features(model)`，并与图中的 `inp` 逐位比较。
- `paper_runtime.validate_registration` 只检查 `len(adapt_ws)` 是否等于节点类型数。
- `benchmark_v2/checkpoint.py::validate_binding` 核对 binding 中的 `graph`、`folds`、`labels`、`label_view`、`feature_view`、`feature_npz` 文件 SHA。

**训练与审计：**
- `benchmark_v2/trainer.py::fit(model, parts, task, labels, config, dest, binding, original_ids, support, memory_guard)`：Adam + OneCycle，按 inner_val loss 选 best，outer_test 只在训练结束后评分。
- `benchmark_v2/support.py::gradient_audit` 会遍历 `model.gcs`。只要剖面中有带训练支持的 v2 关系，就要求 v2 消息参数有梯度，所以 0 层的模型只能用于 G0。

**执行器：**
- `benchmark_v2/execution.py` 写死了 8H 的 `DEFAULT`、`VERSION` 和 plan 结构，只能参照改写，不能直接调用它的 `load`/`construct`。
- 它绑定的运行版本 `experiment/run.py::_code_refs()` 会枚举 `scripts/DFG/**` 与 `sco_models/**` 下的全部 `.py`（不含 artifacts 和 tests）。

**两个直接后果：**
1. **任何新的 `.py` 放进 `scripts/DFG/` 都会改变旧 plan 的运行版本绑定**，导致 8B/8H 的 verify 失败。这也是把 NodeSem 放在 `scripts/node_sem/` 的硬性原因。
2. **GPU 锁**：`scripts/DFG/experiments/artifacts/dfg_v2/.training.lock`，用 `experiment/run.py::_Lock`。NodeSem 必须使用同一把锁。

### 1.4 基准 v2 协议（沿用）

- **特征**：N-anon-s。8G 已为全部 HCG 节点生成改名后的 `code`（`benchmark_v2/anon_parity.py::node_code_view`）、改名后的源码（`prepare_spelling.load_result`），以及匿名 token 特征 NPZ（original、anonymous 两个视图）。
- **折**：8D 分组嵌套折。合约任务 5 折，节点任务 10 折。
- **标签**：L-audit（C1 作为 target，C2 排除项屏蔽）。
- **其余**：seed=1，local_dev_v1。训练配置见 8H（Adam + OneCycle，50 轮，patience 7，delta 0.001，hidden 128，2 层，8 头，shared_projection，mean）。
- **初值**：constructor 种子 = 10000 + fold + 1000·[合约任务]；fit 种子 = constructor + 1000000。8H 为每个（任务、折、剖面）封存了零步初值。

### 1.5 推动节点增强的证据

**8H 结果（L-audit，best，折均 BF1%）：**

| 任务 | G0 | G3R | G3R − G0 |
|---|---:|---:|---|
| 重入节点（DFG 主终点） | 98.09 | 99.12 | +1.04，10/10 折，Holm p=0.0078 |
| 访问控制节点 | 97.71 | 98.35 | +0.64（描述） |
| 重入合约 | 93.68 | 95.02 | +1.34（描述） |
| 访问控制合约 | 91.02 | 93.01 | +1.99（描述） |

**节点特征的缺陷：**
1. 特征是原始 ID（约 0–32k），被当作浮点数直接送进线性层。
2. Prompt 5 的注意力探针显示，第一层注意力几乎是单邻居的（`next_line` 96–99%、`READS_STATE` 98.6–99.8% 的 head 最大权重 ≥0.99）。
3. 8C/8D 显示这种特征对位置变化极其脆弱。
4. 8D-A 显示访问控制有大量来自函数上下文的预测翻转：节点自身文本没变，但所在函数的名字变了，预测就变了。

**语义缺口：**
- 访问控制关键字基线 99.5，已饱和；重入关键字基线 85.6。
- 访问控制真实正例只检出 2/20。phishable 和 mycontract 中的 `require(tx.origin == owner)` 被漏掉：SolidiFI 模板用 tx.origin 与参数比较，这两个文件用它与状态变量比较。
- 图中缺少三类信息：守卫支配关系、modifier 的应用、构造函数身份。

### 1.6 记录文档中仍然存在、与本方案相关的问题

- **L-audit 只是诊断标签视图，不是金标准。** 人工依赖核验（512/111 条）尚未补齐。
- **单 seed、本机运行。** 交叉验证的各折共享训练数据；完整固定图前向属于传导式设定。
- **SolidiFI 样本占主导**（访问控制 40/57、重入 40/71 个节点任务文件）。非 SolidiFI 的正例很少（访问控制 20、重入 32/33）。
- **`gu.get_node_token` 用逐行 `torch.cat` 拼接**，复杂度是 O(n²·D)，8H 中 CPU 准备已经很慢。NodeSem 的载体维度 D 要控制在 1000 以内，并在 NS-P4 中实测。
- **WSL 中 git 推送曾因 DNS 失败**（8D 时已恢复）。Codex 不 push，除非用户要求。

### 1.7 约束

- 训练环境：Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、transformers 4.30.2、tree_sitter 0.20.4，离线运行。
- 本机 RTX 3050 4GiB。mando 环境无法运行现代 LLM 和 sentence-transformers。

---

## 2. 已确定的决策

1. **主视图**：基准 v2（N-anon-s + 分组折 + L-audit）是唯一主终点。原名视图是预先登记的次要终点，必须报告，但不据此下结论。
2. **运行位置**：全部先在本机运行（包括 3B 级 LLM 的试点），以后在服务器上复跑，两边的结果不混合。
3. **代码位置**：新文件夹 `scripts/node_sem/`，新分支 `node-sem`。只通过 import 复用 `scripts/DFG/**`，作者代码与 `scripts/DFG/**` 零修改；也不得在 `scripts/DFG/` 下新增任何文件。
4. **编译与 IR**：当前沿用 MANDO-LLM 的思路，不依赖编译。M3a 的事实提取做成可替换后端（现在只有 AST 后端）。以后有了让全部合约都能编译的组件，再加 IR 后端，输出同一份事实 schema。

---

## 3. 对节点增强原方案的修订与理由

| # | 项目 | 原方案 | 修订后 | 理由 |
|---|---|---|---|---|
| 1 | 基础图与关系 | “G2 图”、`data_dep` 等 | 使用 F3 图的四种 v2 关系；特征实验在 G0 和 G3R 上做 | 与已实现的 DFG v2 一致。G3R 是预先登记的 DFG 主终点剖面；G\*=G3 只作参考 |
| 2 | 协议 | 5 seed、普通 KFold | 基准 v2：分组嵌套折、L-audit、seed=1、只用内层验证做选择、Holm 校正 | 与 DFG 结果可比 |
| 3 | token 核查 | 第一步 | 删除 | 已在 Prompt 0/4/5 证实 |
| 4 | 新增 S1 | 无 | 可学习的 token 嵌入加掩码平均池化 | 区分增益来自“正确处理 ID”还是来自预训练知识 |
| 5 | 文本视图 | 原代码 | 主视图用 N-anon-s；次要视图用原文 | 去掉 SolidiFI 的名字通道 |
| 6 | 边上的拼写 | 未考虑 | 主视图中经 8G 的文件内双射映射成匿名名；加全文本泄漏测试 | DFG 边上的拼写属性是原名，不映射就会把名字重新带回来 |
| 7 | 位置信息 | 绝对行号 `@L57` | 只写函数内的相对距离 | 绝对行号可能与注入位置相关 |
| 8 | M2 后继（图片方案） | 只有 `FROM` | 新增 `TO`，并按汇点类型标注（调用参数、调用金额、守卫、状态写、返回） | 重入与访问控制需要知道“值流向哪里” |
| 9 | 守卫 | owner 类名字的正则 | 改为操作数的结构类别及比较组合 | 改名视图里没有“owner”；“tx.origin 对状态变量”与“tx.origin 对参数”正好区分 phishable 与 SolidiFI 模板 |
| 10 | modifier 与构造函数 | 只有“受修饰器保护” | 新增 modifier 解析、modifier 体内基于发送者的守卫、构造函数身份 | 8B/8C 证实这三类信息在图中缺失 |
| 11 | 语法袋（图片方案） | 无 | M3a 增加约 12 维 | 便宜、确定、与名字无关 |
| 12 | 辅助节点 | 占位文本加零向量 | `env_source` 的文本就是它的键 | 与 8G 的做法一致 |
| 13 | 存在位与 LayerNorm | 无 | 每个模态一个存在位；连续模态先过 LayerNorm | 区分缺失与真的为零；避免重蹈原始 ID 尺度导致注意力饱和的覆辙 |
| 14 | PCA | 每折拟合 | 取消，改为可学习的逐模态投影 | 每个任务约 1.3–1.8 万节点，显存不是问题 |
| 15 | 接入方式 | 修改 `model_hgt` 的 forward 与训练脚本 | 把拼接后的向量写进内存图副本的 `token` 属性，只替换 `adapt_ws` 的模块，作者代码零修改 | 现有的注册校验、checkpoint、输入保护、训练器原样可用（第 4.9 节） |
| 16 | 初值 | 未规定 | `gcs`、`classify` 从 8H 同一（任务、折、剖面）的零步初值复制；新模块用按名字派生的种子初始化 | 配对初值 |
| 17 | 无图对照（ORACAL） | 只列为风险 | S4-noG：G0 图、0 层 HGT | 检验图结构是否仍然有贡献 |
| 18 | LLM | 本地 7B，经 OpenAI 兼容接口 | 本机用 3B GGUF Q4（llama.cpp + JSON schema 语法约束）做试点；服务器换更大的模型 | 4GiB 显存放不下 7B |
| 19 | LLM 输入 | 函数源码 | 改名并在 AST 上去注释，函数内再按首次出现顺序重新编号；相对行号由 AST 生成并保存到节点的映射 | 8G 的改名源码保留注释；重新编号后跨文件的重复函数可以共用缓存 |
| 20 | 提取环境 | 未规定 | 编码器、LLM、句向量在离线环境 nodesem 中运行，只输出带 SHA 的文件 | mando 环境被 py3.7 限制 |
| 21 | G0 上的 S3/S4 | 未说明 | 明确：S3/S4 的特征来自 DFG 分析。所以 G0 上的 S3/S4 表示“DFG 信息以特征形式进入、而不是以边的形式”；交互项要按此解读 | 避免把 G0+S4 误读为不含 DFG 信息 |
| 22 | 不采纳 | — | IR（本版）、RAG、按中心性选节点、把安全分析字段放进主方案（只作 S7 对照）、边描述（留给第三个创新点） | 见第 2 节第 4 条；以及泄漏与范围方面的考虑 |

---

## 4. NodeSem v1 方案

### 4.1 总体结构

```
F3 图（DFG v2）+ 源码 AST（主视图 N-anon-s；次要视图原文）
 ├─ M0 token ID（8G 匿名特征，512）──→ 可学习嵌入 + 掩码平均池化（S1）
 ├─ M1 节点代码文本 → 冻结代码编码器 → e_code（256）
 ├─ M2 DFG 上下文（结构化字段）→ 同一编码器 → e_ctx（256）
 ├─ M3a 静态行为画像（AST 后端，以后可加 IR 后端）→ b_static（约 75）
 └─ M3b 函数级 LLM 描述 → 句向量 t_sem（384，教师，只在训练期使用）
       M3c 按折训练的学生 MLP([e_ctx; b_static]) → s_sem（384）
 → 拼接为载体向量 x_v = [存在位 | 各模态]，写进内存图副本的 token 属性
 → make_model 原样构造 → 只把 adapt_ws 换成 NodeSemAdapter → 原 HGT（G0 或 G3R）→ 节点/合约分类
```

### 4.2 通用规则

- **允许读取的节点属性**：`code`、`node_type`、`source_file`、`node_source_code_lines`（只用于对齐，不作为特征），以及图的边和边属性。
  - 禁止读取 `label`、`type_label`、`node_info_vulnerabilities`、`method`、任何标签或预测文件。
  - 用白名单实现，并写扰动测试：修改这些禁止属性后，特征必须逐位不变。
- **主视图文本**：节点文本来自 8G 的 `node_code_view`，源码来自 8G 的改名结果。
  - **DFG 边上的拼写属性**（例如 `spellings`）是原名。主视图中必须用该文件的 8G 双射（原拼写 → vN）映射后才能使用。
  - **全文本泄漏测试**：主视图的每一段特征文本和每一个 LLM 提示中，凡是 identifier token，都必须是保留名，或者属于该文件的匿名名集合。出现原名就失败。
- **任何特征文本中都不出现绝对行号或文件名**，只用函数内的相对距离 `@-k`、`@+k`。
- **AST 事实**一律经 `ProjectionView` + `Projector` 按 AST 身份投影到节点。不按行号或“最近节点”猜测；投影不到的事实丢弃并计数。
- **每个模态的产物**：NPZ（只含一个数组 `features`，float32）加 manifest。manifest 记录：
  - 版本、视图、任务、行身份与顺序（`original_graph_node_id`，辅助节点为 `env:<文件>:<键>`）；
  - 每行的 code SHA、维度、实现文件 SHA、模型资产 SHA；
  - 输入文本文件的 SHA。
- **缓存键**：文本 SHA + 编码器或 LLM 资产 SHA + 提示模板 SHA。

### 4.3 M0 / S1：可学习的 token 嵌入

- 输入是 8G 匿名视图的 512 个 token ID。浮点值不是精确非负整数，或超出词表，就报错。
- `nn.Embedding(V, 128, padding_idx=0)`，按非零位置做掩码平均。V 从冻结 tokenizer 资产的词表大小读取并核对，不写死。
- 全为填充的行输出 0，并把该模态的存在位置 0。

### 4.4 M1：节点代码编码

**编码文本按节点类型截取：**

| 节点类型 | 编码文本 |
|---|---|
| `expression_statement`、`new_variable`、`return`、`continue_statement`、`struct_declaration` | 完整文本 |
| `if`、`while` | `if ( <cond> )` / `while ( <cond> )` |
| `for` | `for ( <init> ; <cond> ; <update> )`，不含 body |
| `function_definition`、`constructor_definition`、`modifier_definition` | 签名（名称、参数、可见性、可变性、modifier 调用、returns），不含函数体 |
| `contract_declaration`、`library_declaration`、`interface_declaration` | 头部，如 `contract v3 is v7` |
| `end_if`、`end_loop` | `<END_IF>`、`<END_LOOP>` |
| `env_source` | 环境键，如 `msg.sender` |

- 截取通过 AST 身份完成。失败时回退为完整文本，并按类型计数。
- 统一做空白规范化：连续空白合并为一个空格。只在特征文本上做，不改源码。
- **编码器**：
  - 主编码器：`Salesforce/codet5p-110m-embedding`（256 维）；
  - 备选：`microsoft/unixcoder-base`（768 维，均值池化），以后作为对照；
  - 冻结，fp16 推理，最大长度 128，相同文本只编码一次，输出 float32。
  - 权重由用户下载，Codex 不得联网。

### 4.5 M2：DFG 上下文（结构化字段，在 nodesem 中按优先级截断）

mando 侧为每个节点输出一个 JSON 对象（字段固定，缺失写 `"-"`），nodesem 侧再拼成文本，并用编码器自己的 tokenizer 按优先级截断。例：

```
[STMT] v12 . v3 -= v9 ;
[FUNC] function v4 ( uint v9 ) public payable
[DEF] v12.v3:state
[USE] v12:local@-1 | v9:param
[FROM] @-1: var v12 = v2 [ msg.sender ] ;
[TO] -
[STATE_R] -
[STATE_W] v3
[ENV] -
[PRE_EXT_CALL] @-2: msg.sender.call.value ( v9 ) ( )
[GUARD] require; env==state; @-3
```

| 字段 | 内容 | 来源 |
|---|---|---|
| `STMT` | M1 的截取文本 | 节点 |
| `FUNC` | 所在函数的签名（M1 规则） | AST 函数归属 |
| `DEF`、`USE` | 变量及类别（state、local、param、env）；局部变量和参数带上其来源语句的相对距离 | `DATA_DEF_USE` 边与拼写属性（主视图需映射）+ AST 参数表 + L2/L3 边 |
| `FROM` | 来源语句，最多 2 条（相对距离 + STMT 文本） | `DATA_DEF_USE` 入边 |
| `TO` | 去向，最多 2 条，汇点类型取 `call_arg`、`call_value`、`guard`、`state_write`、`return`、`other` | `DATA_DEF_USE` 出边 + 目标节点的 AST 角色 |
| `STATE_R`、`STATE_W` | 读写的状态变量 | `READS_STATE`、`WRITES_STATE` |
| `ENV` | 环境键 | `ENV_FLOW` |
| `PRE_EXT_CALL` | 同函数内、控制流上能到达本语句的最近外部调用（不含自身） | 函数内 CFG 反向 BFS |
| `GUARD` | 支配本语句的最近守卫：类型（require、assert、if、while、modifier）、操作数类别组合、相对距离 | 函数内 CFG 支配树 |

**截断顺序**（按编码器 tokenizer 计数，上限 256）：
1. `TO` 只留 1 条；
2. `FROM` 只留 1 条；
3. `GUARD` 只留类型和组合；
4. `PRE_EXT_CALL` 只留相对距离；
5. 每类变量最多 3 个；
6. `FUNC` 只留可见性和 modifier 个数；
7. 最后才截断 `STMT`。

`STMT`、`DEF`、`USE` 的字段标签永远保留。记录每个节点的截断级别。

辅助节点、合约/库/接口声明节点、`end_if`、`end_loop`：只有 `STMT`。

### 4.6 M3a：静态行为画像（约 75 维）

字段表固定在 `behavior_schema.json`，并提供 `explain(vec) → 字段名列表`。

| 组 | 字段 | 编码 | 约维度 |
|---|---|---|---|
| A 外部交互 | 低层 call、delegatecall、staticcall、send、transfer、成员调用（目标未知）、附带 value | 多热 | 7 |
| A' 转账 | call 带 value、send、transfer | 1 位 | 1 |
| B 状态访问 | 写（0/1/多）、写 mapping/数组元素、写标量、读（0/1/多）、读 mapping/数组元素 | 独热 + 多热 | 9 |
| C 顺序 | 可从同函数外部调用到达；被外部调用支配；本语句写状态且之后有外部调用；本语句是外部调用且之后有写状态 | 多热 | 4 |
| D 守卫方式 | 无、require/assert、if 条件、所在函数应用了 modifier、modifier 体内有基于 msg.sender/tx.origin 的守卫 | 多热 | 5 |
| D' 守卫操作数 | msg.sender、tx.origin、状态变量、参数、局部变量、字面量、时间戳/区块号、调用结果 | 多热 | 8 |
| D'' 比较组合 | env 对状态变量、env 对参数、env 对字面量、状态变量对参数 | 多热 | 4 |
| E 环境量 | msg.sender、msg.value、tx.origin、时间戳、区块号、其他（L3 的 14 个键归入这 6 组） | 多热 | 6 |
| F 调用返回值 | 不适用、被检查、被赋值未检查、被忽略 | 独热 | 4 |
| G 算术 | + − × ÷/% **；是否作用于状态变量 | 多热 | 6 |
| H 循环 | 不在循环内、常量边界、状态变量或数组长度边界、参数或局部变量边界 | 独热 | 4 |
| I 函数上下文 | public、external、internal、private；payable；view/pure；是构造函数（constructor 关键字，或函数名等于所在合约名）；应用了 modifier | 独热 + 多热 | 8 |
| J 语法袋 | `=`、`+=`、`-=`、其他复合赋值、delete、emit、selfdestruct/suicide、成员访问深度 ≥2、下标访问、字面量、new、三元 | 多热 | 12 |

- **辅助节点**只置 E 组，独热组分别置为“无 / 不适用 / 不在循环内”；可见性组全为 0。
- **合约/库/接口声明节点、end_if、end_loop**：只置独热组的默认值。
- **两个视图必须逐位相同**：M3a 不依赖任何保留名以外的具体名字。函数名等于合约名、modifier 解析这两项依赖名字相等关系，而 N-anon-s 是文件内双射，所以也必须相同。
- **后端接口**：`FactBackend.extract(file_ctx) → {node_id: StatementFacts}`，现在只实现 `AstBackend`。

### 4.7 M3b：LLM 行为描述（只描述，不下判断）

- **单位**：每个函数（含 modifier、构造函数、fallback）调用一次。
- **输入**：
  - 主视图的改名源码，在 AST 上去掉 comment 节点；
  - 函数内按首次出现顺序把非保留标识符重新编号为 `a1, a2, …`；
  - 加上同一合约的状态变量声明（使用同一套编号）；
  - 每行加函数内相对行号 `L1|`、`L2|`、……
  - 需要描述的语句，按 HCG 节点给出相对行号列表。映射关系保存在 `prompt_map`：相对行号 → 节点 id，编号 → 匿名名。
  - 超过 120 行的函数，按 60 行分段调用，每段都附签名。
- **缓存键**：sha256(提示模板版本 + 模型资产 SHA + 提示全文)。
- **后端**：llama.cpp（llama-cpp-python 或 llama-server），GGUF Q4 的 3B 级代码指令模型。温度 0，固定 seed，n_ctx 4096，输出受 JSON schema 语法约束。
- **Schema**：
  - `function_intent`：≤25 词；
  - `statements[]`：`line`（必须是给定行之一）、`role`（取值：`input_validation`、`access_check`、`state_read`、`state_update`、`value_transfer`、`external_call`、`computation`、`event_emit`、`control`、`other`）、`summary`（≤20 词）、`reads[]`、`writes[]`、`external`（布尔）。
- **系统提示**：原文写成模块常量，见 NS-P7。
- **过滤与校验**：
  - 解析失败时重试 1 次；行号不在列表内的条目丢弃；同一行取第一条；
  - role 不在词表内改为 `other`；
  - 黑名单（大小写不敏感，词边界，含常见变形）命中的 summary 和 intent 置空，并标记；
  - **忠实性**：把名字按 `prompt_map` 还原后，与 StatementFacts 比较：
    - `faithfulness = (Jaccard(reads) + Jaccard(writes) + 1[external 一致]) / 3`；两侧都为空时 Jaccard 记 1；
    - 成员访问 `a.b` 同时接受 `a.b` 与 `a`；
    - 低于 0.5 的节点标记 unfaithful。
- **教师向量**：只对有效节点计算（解析成功、行号有效、忠实、summary 非空），文本为 `role: <role>. <summary>. function: <intent>`，用 `BAAI/bge-small-en-v1.5`（normalize）编码，得到 384 维。无效节点的存在位为 0。
- **S7 对照**：模板 `judge_v1`，允许 `security_note`（≤20 词），不做黑名单过滤，编码为 `t_judge`。manifest 标注 `control_judgement`。
- **本机流程**：先试点 50 个函数（固定抽样种子），报告耗时、解析成功率、黑名单命中率、忠实性分布；用户确认后再全量运行。原名视图的 LLM 运行留到服务器。

### 4.8 M3c：按折蒸馏的学生

- **每个（视图、任务、外层折）一个学生**：
  - 训练节点：该折 inner_train 文件中、教师有效的节点；
  - 早停节点：inner_val 文件中、教师有效的节点；
  - outer_test 节点的教师向量绝不进入训练或早停。
- **结构**：`e_ctx` 按维标准化（均值与方差只用训练节点估计，并保存）后，与 `b_static` 拼接 → `Linear(→512)` → GELU → Dropout 0.1 → `Linear(512→384)` = `s_sem`；另有一个角色头 `Linear(384→10)`。
- **损失**：`1 − cos(s_sem, t)` + 0.3 × CE(role)。
- **训练**：AdamW（lr 1e-3，wd 1e-4），batch 1024，最多 30 轮，早停监控 inner_val 余弦损失（patience 5）。CPU 运行，种子由 parameter_seed(fit 种子, "student", task/fold) 派生。
- **导出**：给该任务全部节点（含辅助节点）生成 `s_sem`。
- **防泄漏断言**（导出前强制执行，失败即报错）：
  1. 训练节点和早停节点全部来自该折的 inner_train 或 inner_val 文件；
  2. 没有任何 outer_test 节点；
  3. 学生代码没有读取标签。
- **诊断**：outer_test 有效节点上学生与教师的平均余弦（只记录，不参与选择）。

### 4.9 M4：载体与融合（核心接入方式）

**为什么用 token 属性作载体：** 模型构造、`validate_registration` 中的特征比对、checkpoint 输入快照、FitInputGuard、trainer 都通过 `_features(model)` → `get_node_token(nx_graph)` 读取 `token` 属性。只要把 NodeSem 的拼接向量写进内存图副本的 `token`，这些代码就会自动把新向量当作“冻结特征”来构造、校验和保护，不需要改任何一行。

**构造流程**（`node_sem/model.py::make_nodesem_model`）：
1. 读取 8H 中该（任务、剖面）所用的图引用（G0 = F0 原图，G3R = F3）。
2. 主视图：调用 `benchmark_v2.spelling_features.assemble(graph, 8G anonymous view)`，得到带匿名 token ID 的内存副本（S0/S1 需要；env_source 的 token 保持不变）。次要视图用 8G 的 original view。
3. `node_sem.carrier.carry(graph, spec, view, task)`：再做一次深拷贝，每个节点的 `token` ← 载体向量 `x_v` = [存在位 (M) | 模态 1 | …]（float32，有限值）。行由各模态 manifest 按 node id 查找；辅助节点按 `env:<文件>:<键>` 查找。核对每行的 code SHA。原图指纹前后一致。
4. `dfg_v2.model.make_model(task, carried, profile, "cpu", node_feature="inside_token", hidden_size=128, layers=spec.layers or cfg.layers, heads=8, reducer, layer_impl)`：原样构造，`adapt_ws[i] = Linear(D, 128)`，注册校验通过。
5. S0：不做替换（就是 8H 的模型）。其他配置：`model.adapt_ws = nn.ModuleList([NodeSemAdapter(spec, ntype) for ntype in 按 ntypes_dict 顺序])`，长度不变。
6. 加载 NodeSem 零步初值（见下），核对 tensor_digest。
7. `node_sem.model.validate(model, spec)`：适配器的类型、数量和布局正确，D 与 manifest 一致；然后调用 `dfg_v2.model.validate_registration(model)`。

**NodeSemAdapter**（`node_sem/adapter.py`）：
- 按 spec 的布局切分 `inp`：前 M 列是存在位，之后依次是各模态。
- token 模态（S1）：Embedding 加掩码平均池化。连续模态：LayerNorm 后接 `Linear(d_m, 128)`。`b_static`：直接 `Linear(75, 128)`。
- 融合方式：
  - `concat`（默认）：`Σ_m p_m · z_m + b`；
  - `gated`：`g = softmax(mask(W_g [p_1 z_1; …]))`，存在位为 0 的模态 logit 置为 −inf；全部缺失时输出 `b`，不得出现 NaN；`h = Σ g_m z_m + b`。`last_gates` 只读保存。
- 输出交给作者 forward 中原有的 `gelu`。
- 模态 dropout（只在 `self.training` 时生效）：每个节点每个模态以 p=0.1 的概率把存在位置 0。随机数来自一个按（fit 种子、"modality_dropout"）派生的 CPU generator，掩码再移到设备上，不消耗全局随机数。

**初值**（`node_sem/init.py`）：
- 从 8H 同一（任务、折、剖面）的零步初值文件（SHA 封存）复制所有非 `adapt_ws.*` 的键（`gcs.*`、`classify.*`）。形状必须一致，否则报错。
- `adapt_ws.*` 的新参数：Linear 用 Xavier uniform，Embedding 用 N(0, 0.02)（padding 行置 0），LayerNorm 用 1/0。随机数一律来自 `torch.Generator().manual_seed(parameter_seed(constructor 种子, 参数名, [task_id, fold, profile, spec_digest]))`。
- 记录 state SHA。S0 时必须与 8H 初值逐位相同。

**S4-noG**：G0 图，`layers=0`。作者 forward 在 0 层时直接把 `h` 送进 classify，合约任务照常池化；`gradient_audit` 在 G0 上没有 v2 关系，可以通过。NS-P0 和 NS-P4 要实际验证这一点。

### 4.10 执行器（`node_sem/execution.py`，参照 benchmark_v2/execution.py 改写）

- 文件头写明来源 `scripts/DFG/dfg_v2/benchmark_v2/execution.py` 及其 SHA256。
- **自己的 VERSION、plan、seal、authorization**，产物放在 `scripts/node_sem/artifacts/<批次>/`。
- **binding** 沿用 `benchmark_v2.checkpoint.build_binding`，`protocol` 仍是 `dfg-v2-grouped-nested`（实验协议相同）。另加：
  - `nodesem_version`；
  - `feature_spec` 及其 digest；
  - `feature_view` = 该配置的载体 manifest；
  - `feature_npz` = 载体 NPZ；
  - `label_view`、`label_policy`、`source_preparation`，与 8H 相同。
- **直接 import 复用**：
  - `benchmark_v2.trainer.fit`、`input_guard.FitInputGuard`、`audit_supervision.make_part`、`protocol.validate_parts`、`support.model_support`；
  - `checkpoint.validate_binding`；
  - `experiment.preflight.run_preflight`、`initialize_context`、`make_observed_resources`、`LOCAL_DEV_POLICY`；
  - `experiment.run._Lock`（锁路径与 8H 相同）；
  - `tasks.read_labels`。
- **运行版本**：`plan["runtime"]` = `experiment.run._code_refs()` 加上 `scripts/node_sem/**/*.py`（不含 tests 和 artifacts）的 SHA。每个 fit 开始前都要比对。
- **S0 复用**：plan 中 S0 × {G0, G3R} 引用 8H 的 60 个 receipt（路径与 SHA），不重跑。报告直接读取它们的预测。
- **失败策略**：每个 fit 一个独立进程，串行执行。失败就停，保留现场，不自动重试；重试必须经用户批准，并沿用 8H 的 attempt_00k 规则。

### 4.11 环境与存储

| 环境 | 用途 | 谁准备 |
|---|---|---|
| mando（现有） | 文本视图、事实、M2 字段、M3a、载体装配、学生、训练、统计 | 已有 |
| nodesem（新） | M1/M2 编码、M3b（llama.cpp）、教师句向量 | 用户按 NS-P2 第 0 节与 NS-P7 第 0 节准备；Codex 只核验，不安装、不联网 |

- nodesem 的代码只放在 `scripts/node_sem/offline/`，可以用 Python 3.10 的语法；mando 代码不得 import 它们。两边只通过带 SHA 的文件交换数据。
- 产物：`scripts/node_sem/artifacts/<批次名>/`，拒绝覆盖已存在的目录。

### 4.12 实验设计

**特征配置**（S0–S8；图为 G0 或 G3R）：

| 编号 | 模态 | 推理时用 LLM | 回答的问题 |
|---|---|---|---|
| S0 | 原始 token ID（8H，复用） | 否 | 基线 |
| S1 | 可学习 token 嵌入 | 否 | 只修正 ID 的处理方式，能提升多少 |
| S2 | e_code | 否 | 预训练代码知识 |
| S3 | S2 + e_ctx | 否 | DFG 上下文 |
| S4 | S3 + b_static（**确定性主方案**） | 否 | 静态行为画像 |
| S4g | S4，gated 融合 | 否 | 融合方式 |
| S4-noG | S4，G0 图，0 层 | 否 | 图结构是否仍然有贡献 |
| S5 | S4 + s_sem（**LLM 主方案**） | 否 | 蒸馏后的意图语义 |
| S6 | S4 + t_sem | 是 | 上限 |
| S7 | S4 + t_judge | 是 | 判断性内容有多少是泄漏 |
| S8 | S5，但 s_sem 在同任务同节点类型内随机置换 | 否 | 增益是否来自真实语义 |

**批次**（本机，seed=1，四个任务共 30 折；每个 fit 约 100 秒，以 NS-P4 的实测为准）：

| 批次 | 内容 | fit 数 |
|---|---|---:|
| N-A | {S1, S2, S4} × {G0, G3R}（S0 复用 8H） | 180 |
| N-B | S3 × G3R、S4g × G3R、S4-noG | 90 |
| N-C | {S5, S6, S7, S8} × G3R（本机 LLM 试点版） | 120 |
| N-D | 原名视图 {S0, S4} × G3R | 60 |

**预先登记（写进 plan，以后不改）：**
- **主终点**：重入节点、G3R、S4 − S0（L-audit，best，外层 BF1，10 折配对，双侧 Wilcoxon）。
- **N-A 的 Holm 家族**（重入节点、G3R）：S4−S0、S1−S0、S2−S0、S4−S2。
- **交互项**（描述）：(S4−S0)\_G3R − (S4−S0)\_G0，按第 3 节第 21 条解读。
- **N-B**：全部只作描述。
- **N-C 的 Holm 家族**（重入节点、G3R）：S5−S4（主比较）、S6−S5、S7−S6、S5−S8。注明这是本机试点版本，正式结论以服务器复跑为准。
- **访问控制节点与两个合约任务**：只作描述。访问控制另附 20 个非 SolidiFI 正例的逐节点概率表；重入另附 32 个非 SolidiFI 正例（以及全部非 SolidiFI 误报）的逐节点概率表。
- **天花板说明**（r3 新增）：8H 中重入节点 G3R 的 S0 已达 99.12，10 折合计只有 120 个错误（每折 5–23 个）。主终点的预期效应很小，因此对主比较另报逐折错误数（FP+FN）及相对错误减少率 1 − err(S4)/err(S0)。这一项只作描述，不进入 Holm 家族，也不改变主终点。
- **S\***：按 8H 的规则用 inner_val 选择，只作参考。

**每个批次的报告必须包含：**
- 原标签、全部原 HCG 节点上的辅助结果；
- last 检查点的辅助结果；
- SolidiFI 与非 SolidiFI 分层（非 SolidiFI 只报 pooled 计数和 Wilson 区间）；
- 与关键字基线和 8H 的对照；
- 第一层注意力 head 最大权重的分布（复用 `attention_probe.py` 的方法，只做 eval 前向）；
- 主比较的逐折错误数与相对错误减少率（见上方“天花板说明”）；
- gated 配置下的门控权重；
- 资源与耗时。

### 4.13 风险与应对

1. **编码器可能见过公开基准。** 主视图是改名后的代码，可以减轻但不能消除，写进局限部分。
2. **3B LLM 的描述质量可能不足**，S5≈S4。这不影响 N-A 的结论，服务器复跑时换更大的模型。
3. **语义特征压过结构**：用 S4-noG 和模态 dropout 来检验。
4. **访问控制已经饱和**：结论只能来自重入；访问控制只看 20 个真实正例的定性表。
5. **单 seed、传导式设定、SolidiFI 占主导**：与 DFG 相同，论文结论需要服务器上的多 seed 复跑。
6. **M3a 可能被质疑“针对标签设计”**：字段都是通用的语句行为，不读取标签；两个视图逐位一致的校验，以及 S4−S3 的消融，都写进论文。
7. **`get_node_token` 很慢**：控制 D（S4 约 590 维，S5 约 975 维），在 NS-P4 中实测构造时间。

---

## 5. Codex Prompts

使用方式：每次开新会话，先贴 5.1 共享上下文，再贴一个 Prompt。按 NS-P0 → P1 → P2 → P3 → P4 → P5 → P5A → P6 → P7 → P8 → P9 的顺序执行。每个 Prompt 结束后先交审查，通过后再进下一个。

### 5.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文（NodeSem v1）

## 项目
在 MANDO-LLM 私有仓库上实现节点语义增强（NodeSem v1）：在已完成的 DFG v2（scripts/DFG/dfg_v2，包括 benchmark_v2 执行器）之上，为 HCG 节点构建新的输入特征，并用 8H 的基准 v2 协议评估。方案全文在 scripts/node_sem/PROMPTS.md（第 1–4 节是设计，第 5 节是各 Prompt），有疑问先查它。

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。第一次开始前：
  git fetch origin node-sem
  git checkout -b node-sem origin/node-sem
之后的提交都在 node-sem 上。不要 push，除非用户明确要求。每个 Prompt 开始前先 git pull --ff-only origin node-sem，读取最新的 PROMPTS.md（两个 Prompt 之间可能被修订）。

训练与图处理环境（WSL）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
  export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、transformers 4.30.2、tree_sitter 0.20.4、RTX 3050 4GiB。
mando 环境中的代码必须兼容 Python 3.7：不要用 :=、list[str]/dict[str,int] 这类运行时注解、dict | dict、dataclass(slots=...)、match。
离线提取环境 nodesem 由用户准备。它的代码只放在 scripts/node_sem/offline/，mando 代码不得 import 它；两边只通过带 SHA 的文件交换数据。

## 新代码位置
- 代码：scripts/node_sem/（含 __init__.py；离线脚本在 scripts/node_sem/offline/）
- 测试：scripts/node_sem/tests/（fixtures 在 scripts/node_sem/tests/fixtures/）
- 产物：scripts/node_sem/artifacts/<批次名>/，拒绝覆盖已存在的目录。未跟踪的产物目录允许出现在 git status 中。
- 进度：scripts/node_sem/PROGRESS.md，每个 Prompt 结束追加一节（做了什么、文件清单、测试命令与结果、验收数字、遗留问题、与本文不一致之处及处理方式）。同时在 HANDOVER.md 与 docs/training_changes_2026-10-07.md 末尾追加简短记录。这三份文件只追加，不改旧文。

## 禁止修改（以及禁止新增）
1. scripts/DFG/** 下的任何文件，也不得在其中新增任何文件。experiment/run.py::_code_refs() 会枚举 scripts/DFG/** 与 sco_models/** 下的 .py，8B/8H 的 seal 绑定了这份清单；新增或修改都会使旧 verify 失败。
2. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py（包括其中已有的本地修改）。
3. 所有已有产物、图、标签、折、特征 NPZ、初值、checkpoint、plan/seal（包括 prompt8g_v1、prompt8h_v1）。
复用时用 import、子类化或组合。必须改变某个冻结函数的行为时，把它复制到 scripts/node_sem，在文件头写明来源路径和原文件 SHA256，并加一条测试，证明它在旧输入上与原函数输出相同。禁止用 types.FunctionType 重新绑定字节码，禁止 monkeypatch 冻结模块。

## 不变量
- 原图的节点、节点顺序、属性和边完全不变。特征只在内存深拷贝上装配，装配前后原图指纹（benchmark_v2.feature_view.graph_fingerprint）相同。
- 特征提取只允许读取节点的 code、node_type、source_file、node_source_code_lines（只用于对齐）以及图的边与边属性。禁止读取 label、type_label、node_info_vulnerabilities、method、任何标签或预测文件。有扰动测试保证这一点。
- 主视图（anonymous）的文本来自 8G 的改名结果；DFG 边上的拼写属性必须先经该文件的 8G 双射映射。主视图的任何特征文本或 LLM 提示中，identifier 只能是保留名或该文件的匿名名，有测试保证这一点。
- 任何特征文本中都不出现绝对行号或文件名，只用函数内相对距离 @-k/@+k。
- AST 事实一律经 ProjectionView + Projector 按 AST 身份投影到节点，投影不到的事实丢弃并计数，不按行号猜测。
- 训练沿用基准 v2 协议：8D 分组折、L-audit、seed=1、local_dev_v1、8H 训练配置，outer_test 只在训练结束后评分。只在 inner_val 上做选择。
- 使用与 8H 相同的 GPU 锁：scripts/DFG/experiments/artifacts/dfg_v2/.training.lock（experiment.run._Lock）。nodesem 环境中所有使用 GPU 的离线任务（M1/M2 编码、llama.cpp、教师句向量）不得与训练并行。离线脚本启动前必须以非阻塞方式检查该锁文件：被占用就直接退出并报告；不得在训练期间抢占 GPU。CPU 模式的离线任务不受此限制。

## 接入方式（第 4.9 节）
NodeSem 的拼接向量写进内存图副本中每个节点的 token 属性，然后用 dfg_v2.model.make_model(node_feature="inside_token") 原样构造模型，只把 model.adapt_ws 的每一项替换为 NodeSemAdapter。这样 validate_registration、checkpoint 绑定、FitInputGuard 和 benchmark_v2.trainer.fit 都可以原样使用，不需要修改任何冻结代码。

## 关键可复用模块（先读再用）
- dfg_v2/model.py（make_model、_construct、_features、validate_registration）、model_input.py、hgt_layer.py、__init__.py（关系名与 AUX_NODE_TYPES）
- dfg_v2/benchmark_v2/execution.py（执行器结构：plan/seal/authorization、construct、binding_parts、fit_one、verify_one、controller；只参照改写）、trainer.py（fit）、checkpoint.py（build_binding、validate_binding）、input_guard.py（FitInputGuard）、audit_supervision.py（make_part、bind_rows）、protocol.py、support.py（model_support、gradient_audit）、reporting.py（wilson、scored、stratified_score）、runtime_model.py、retry.py
- dfg_v2/benchmark_v2/spelling_features.py（assemble：NPZ + manifest 与行身份核对的范例）、anon_parity.py（node_code_view）、prepare_spelling.py（load_result）、spelling_names.py（保留表 reserved）
- dfg_v2/experiment/init.py（seeds、parameter_seed）、run.py（_Lock、_code_refs、job_id、_job_directory）、preflight.py、stats.py
- dfg_v2/attention_probe.py
- dfg_v2/projection_view.py、scripts/DFG/projection.py::Projector、scripts/DFG/frontend.py、scripts/DFG/semantic_cfg.py、dfg_v2/l1_cfg.py、dfg_v2/env.py（14 个环境键）
- scripts/DFG/state/stage_j/binding.py::ClosedScopeJ
- dfg_v2/tokens.py::TokenEncoder
- 8H 产物：scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/（plan、prepared_attempt3 零步初值、runs/*/receipt.json）

## 工作方式
- 每个 Prompt 只做该 Prompt 的范围。代码事实与本文不一致时，以代码为准，在 PROGRESS.md 记录差异与处理方式。如果差异会影响方案（例如某个接入点不成立），停下来报告，不要自行换方案。
- 每个 Prompt 结束时运行（mando 环境，CPU）：
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
  另外核对：git status 中，除 scripts/node_sem/ 与三份记录文档外，没有已跟踪文件的改动；experiment.run._code_refs() 仍等于 8H plan 中的 runtime，且 benchmark_v2.execution.load(8H plan) 只读通过。
  全部通过后 git commit，提交信息以 NS-Pn 开头。
- 除了明确写着“训练”的步骤，不启动任何 HGT 训练。正式批次必须先有用户的授权记录。
- 失败就停，保留现场，不自动重试，不自行换方案。
```

### 5.2 Prompt NS-P0：侦察（只读）

```text
# NS-P0：侦察与接入点核实（只读，不写算法代码）

产出 scripts/node_sem/RECON.md 与 scripts/node_sem/recon.json。每条结论都附命令、文件路径、SHA 或计数。除这两个文件、scripts/node_sem/recon/*.py（只读脚本）和三份记录文档的追加外，不写任何文件。

## 1. 输入身份
- 8H：prompt8h_v1 的 plan.json 与 plan.seal.json 的 SHA；四个任务的 G0/G3R 图引用（F0/F3 路径与 SHA）；label_view；分组折文件；8G anonymous/original 两个视图的特征 manifest 与 NPZ。
- 8H 中 G0、G3R 两个剖面在 30 折上的成功 receipt（attempt 目录、receipt SHA），数量应为 60；对应的零步初值文件路径、state_sha256。确认可以按引用复用。
- 8H 的训练配置（task["config"]）逐项列出。

## 2. 载体接入点实测（CPU，小 fixture 与 1 个真实任务）
- 逐行引用：dfg_v2/model.py::_features、_construct 中 in_size 与 adapt_ws 的创建、validate_registration 中的特征比较；作者 forward 中 adapt_ws 的调用。
- 实验 A：取 reentrancy_node 的 G3R 图，在内存副本中把每个节点的 token 换成随机 float32[600]，调用 make_model(node_feature="inside_token") 是否成功；validate_registration 是否通过；记录构造耗时（与 512 维的耗时比较）。
- 实验 B：把 model.adapt_ws 替换为同长度的 ModuleList（内容为 Linear(600,128)），再调用 runtime_model.validate_registration、checkpoint.build_binding、validate_binding（用临时 binding 与临时文件），确认都通过。
- 实验 C：G0 图、layers=0 能否构造；节点任务与合约任务的 forward/backward 是否成功；support.gradient_audit 在 G0 上是否通过。
- 以上只用 CPU，不调用 trainer.fit，不写正式产物。

## 3. 节点文本与 AST 映射
- 四个任务中，各抽 10 个 if、for、while、function_definition、constructor_definition、modifier_definition、contract_declaration、new_variable 节点：code 是否为整棵子树文本；是否带 pydot 引号。
- 用 node_code_view 得到主视图的节点文本，确认覆盖全部原节点。
- 用 ProjectionView(改名源码) + Projector 找到每个节点的 AST 节点，按类型统计以下各项的成功数和失败数：if/while 条件子节点、for 头部、函数签名范围（不含函数体）、合约头部。
- end_if/end_loop 及合成 else-if 节点的映射方式（参照 8D A_v2 的 return_if_root 规则）。

## 4. DFG 边与拼写
- F3 图中四种关系的方向（源与目标的 node_type 分布）、边属性键与 5 个示例。
- 拼写属性是否为原名；8G 改名结果中是否有“原拼写 → vN”的文件内映射，在哪里，怎样读取。
- env_source 节点的属性、键文本，以及每个文件中的数量。

## 5. CFG 与支配
- scripts/DFG/semantic_cfg.py 与 dfg_v2/l1_cfg.py：能否给出语句级后继与函数入口，能否映射到 HCG 节点；能覆盖多少函数（按任务统计）。
- HCG 自身的 CFG 边类型（next_line、pos_next、neg_next、end_if 等）与覆盖率，作为后备。给出建议：采用哪一个，为什么。
- modifier：每个任务中 modifier_definition 节点的数量；函数头中的 modifier 调用按拼写在同文件中能否解析到定义（成功、失败、经继承解析，各多少）。

## 6. 源码、注释与函数
- 8G 改名源码中注释的数量；在 AST 上删除 comment 节点后重新解析是否 ERROR=0（按任务统计）。
- 函数总数（含 modifier、构造函数、fallback）；按函数内首次出现顺序重新编号后去重的函数数；函数行数的分布（中位数、95 分位、最大值）。

## 7. 资源与耗时
- 8H 每个 fit 的训练时间与峰值显存，按任务和剖面汇总。
- 由此估算 N-A、N-B、N-C、N-D 的本机耗时。

## 验收
RECON.md 与 recon.json 完整；第 2 节三个实验的结论明确。如果载体方式或 layers=0 不成立，停下来报告原因和可选方案，不要自行换方案。PROGRESS.md 追加记录，提交 NS-P0。
```

### 5.3 Prompt NS-P1：骨架、FeatureSpec、载体、适配器、初值、执行器与 S0 等价

```text
# NS-P1：骨架、FeatureSpec、载体装配、NodeSemAdapter（embed_pool）、初值、执行器与 S0 等价证明

## 1. 骨架
scripts/node_sem/__init__.py：VERSION = "nodesem-v1"；模态名常量 TOKEN_IDS、CODE、CTX、STATIC、STUDENT、TEACHER、TEACHER_JUDGE；视图名 ANON = "anonymous"、ORIG = "original"。

## 2. FeatureSpec（feature_spec.py）
用普通类或 namedtuple（兼容 py3.7）。字段：
- name（如 "S1"）；view；
- modalities：有序列表，每项 {name, dim, manifest(ref), normalize(bool)}；
- token_mode：raw_linear | embed_pool | none；
- fusion：raw_linear | concat | gated；
- modality_dropout（float）；layers（None 表示用 8H 配置；0 表示无图）。
方法：to_json()、from_json()、digest()（sha256 规范化 JSON）、layout()（返回每个模态在载体向量中的列区间，第 0..M-1 列是存在位）、carrier_dim()。
校验：S0 必须是 {TOKEN_IDS, raw_linear} 且没有存在位（D=512，与 8H 完全相同）；raw_linear 只能和单一 TOKEN_IDS 模态一起使用。
登记 configs/S0.json、configs/S1.json。其他配置在后续 Prompt 中登记。

## 3. 载体装配（carrier.py）
- load_modality(manifest_ref)：参照 spelling_features.assemble 核对版本、视图、任务、行身份与顺序、数组形状、dtype、有限值、文件 SHA；返回 {row_key: vector}。row_key：原节点为 original_graph_node_id，辅助节点为 "env:<file>:<key>"。
- carry(graph, spec, task_id)：
  1. 深拷贝；
  2. 对每个节点按 row_key 取各模态向量，拼成 [存在位 | 模态...]，写入副本的 token（numpy float32 一维数组）；
  3. 核对节点的 code SHA 与 manifest 中的一致；
  4. 原图指纹前后相同。
  返回副本，以及 carrier 记录（逐行 SHA、D、spec digest）。
- write_carrier(spec, task_id, graph, out_dir)：把载体矩阵按图节点顺序写成 carrier.npz 与 carrier_manifest.json，供 binding 的 feature_npz 和 feature_view 使用。
- S0/S1 的 TOKEN_IDS 模态：通过 benchmark_v2.spelling_features.assemble(graph, 8G 视图) 读取 token，不从别处复制。

## 4. NodeSemAdapter（adapter.py）
- S0（token_mode=raw_linear）不替换 adapt_ws，保留 make_model 创建的 nn.Linear(512,128)；NodeSemAdapter 不实现 raw_linear。carry() 对 S0 直接返回 spelling_features.assemble 的结果（D=512，没有存在位）。
- embed_pool：nn.Embedding(V,128,padding_idx=0)。输入列转成 long 前，检查是否为精确非负整数且 < V。按非零位置掩码平均；全为填充的行输出 0。V 用 TokenEncoder 的 tokenizer 词表大小，并核对 8G 特征的最大 ID < V。
- concat、gated、模态 dropout 的接口先保留（抛 NotImplementedError），在 NS-P4 中实现。
- forward(inp) 只返回线性输出，gelu 由作者 forward 负责。

## 5. 模型构造与校验（model.py）
make_nodesem_model(task, graph_ref, profile, spec, config, device="cpu")：按第 4.9 节第 1–7 步实现。
validate(model, spec)：
- S0：每个 adapt_ws 都是 nn.Linear(512,128)；其他配置：每个都是 NodeSemAdapter；数量等于节点类型数；
- 载体维度等于 spec.carrier_dim()；
- 然后调用 dfg_v2.model.validate_registration(model)。

## 6. 初值（init.py）
initial_state(model, spec, task_id, fold, profile, h8_initial_ref)：
- 读取 8H 零步初值（核对文件 SHA、state_sha256、kind=untrained_initial、optimizer_steps=0、task/fold/profile 一致）；
- 复制全部非 adapt_ws.* 的键；
- adapt_ws.* 的新参数按第 4.9 节的规则初始化，随机数来自 parameter_seed(constructor 种子, 参数全名, [task_id, fold, profile, spec.digest()])；
- 返回 state_dict 与 tensor_digest。
S0：返回值必须与 8H 初值逐位相同。

## 7. 执行器（execution.py，参照 benchmark_v2/execution.py 改写）
文件头写明来源路径与 SHA256。实现：
- create(batch_dir, matrix, authorization_template)：写 plan.json/plan.seal.json。每个 job 包括 task_id、fold、seed、profile、spec 引用与 digest、图引用、label_view、folds、零步初值（路径、state SHA）、载体 manifest/NPZ、config。
  - S0 的 job 标记 reuse_8h=true，并带上 8H receipt 引用。
  - plan["runtime"] = _code_refs() ∪ node_sem 代码 SHA。
- load(plan)：核对 seal、authorization、runtime。
- construct(plan, job, device)：make_nodesem_model → 加载初值 → 核对 digest → model_support 与 plan 一致。
- binding_parts：build_binding(...)，并补充 label_view、label_policy、feature_view（载体 manifest）、feature_npz（载体 NPZ）、source_preparation、nodesem_version、feature_spec、feature_spec_sha256；parts 用 audit_supervision.make_part。
- fit_one / verify_one / controller：结构与 8H 相同（preflight、资源观测、FitInputGuard、trainer.fit、final_result、receipt、verify）。使用相同的 _Lock 路径。S0 的 job 只做 verify（读取 8H receipt），不训练。

## 8. S0 等价证明（必须全部通过；CPU；不计入正式结果）
任选 8H 的两个 job：reentrancy_node fold0 G3R、access_control_contract fold0 G0。
- 构造：分别用 benchmark_v2.execution.construct（8H plan）与 node_sem.execution.construct（S0 spec）构造模型，比较 state_dict、每种节点类型的 inp、etypes_dict、binding 中与特征无关的字段，要求逐位相同。
- 训练：两边都用 benchmark_v2.trainer.fit 在临时目录跑 2 个 epoch（config 只把 maximum_training_epochs 改为 2，并写明这是等价检查配置）。比较每轮 loss、最终参数、Adam 状态、scheduler 状态，以及 inner_val/outer_test 预测，要求逐位相同。
- 结果写入 scripts/node_sem/artifacts/ns_p1_equivalence/equivalence.json。

## 9. 测试（CPU，使用 dfg_v2/tests 中已有的小 fixture 或同源 fixture）
- FeatureSpec：to_json/from_json 往返；digest 稳定；S0 的约束；layout 的列区间。
- carrier：行顺序、行身份、code SHA、图指纹、NPZ 数组名、维度、dtype、非有限值，任一项被篡改都会被拒绝；禁止属性扰动后载体不变；原图未被修改。
- adapter：embed_pool 的掩码平均（含全填充行）；非整数或越界 ID 报错；S0 不替换 adapt_ws。
- init：S0 与 8H 初值逐位相同；S1 中非 adapt_ws 的键与 8H 相同；同样的输入两次生成逐位一致。
- model：替换 adapt_ws 后 validate 与 validate_registration 都通过；适配器数量错误被拒绝。

## 验收
测试与第 8 节的证明通过；PROGRESS.md 记录（含构造耗时）；提交 NS-P1。不跑正式训练。
```

### 5.4 Prompt NS-P2：节点文本视图与 M1 编码

```text
# NS-P2：节点文本视图（mando）与 M1 代码编码（nodesem）

## 0. 用户先完成的准备（Codex 不得自行安装或下载）
用户在 WSL 中新建 conda 环境 nodesem（Python 3.10，torch 2.x + CUDA，transformers，sentence-transformers），并把以下模型下载到本地目录：
- Salesforce/codet5p-110m-embedding（记录 revision）
- microsoft/unixcoder-base（备选）
- BAAI/bge-small-en-v1.5（NS-P7 用）
然后把环境名、模型目录与 revision 告诉 Codex。Codex 计算每个模型文件的 SHA256，写入 scripts/node_sem/offline/assets.json；在 nodesem 中只以 local_files_only=True 加载。

## 1. 节点文本（mando，text_view.py）
build_text_view(task_id, view) -> rows：
- 原节点：按第 4.4 节的规则截取。截取在对应视图的 ProjectionView 上用 AST 身份完成；失败时回退为完整 code，并记录 fallback_reason。
- 主视图的输入：node_code_view 的节点文本与 8G 改名源码。次要视图的输入：原 code 与原源码。
- 辅助节点（env_source）：文本是环境键，row_key = "env:<file>:<key>"。
- 空白规范化：连续空白合并为一个空格。
- 每行输出：row_key、node_type、text、text_sha256、cut_mode（ast_condition、ast_signature、ast_header、full、placeholder、fallback）。
输出 artifacts/text_v1/<view>/<task_id>/text.jsonl 与 manifest.json（行顺序与 8G 特征行顺序一致，辅助节点按 (file, key) 排序附在后面）。

## 2. 泄漏与一致性测试（mando）
- 两个视图的 cut_mode 逐行相同；
- 用 8G 的双射把主视图文本还原后，与次要视图的文本逐字相同（保留名不变）；
- 主视图文本中的 identifier 只能是保留名或该文件的匿名名；
- 文本中没有绝对行号或文件名；
- 禁止属性扰动后输出不变；
- 用手写 fixture 检查每种节点类型的截取结果（精确字符串）：带 modifier 和 returns 的函数签名、else-if 链、for 头部、合约继承头部、struct。

## 3. M1 编码（nodesem，offline/encode.py）
python offline/encode.py --texts <text.jsonl> --model <assets.json 中的名称> --max-length 128 --pooling model_default|mean --out <dir>
- 去重：key = sha256(模型 SHA + max_length + pooling + text)；按长度排序分批；fp16 推理，输出 float32；
- codet5p-110m-embedding 使用模型自带的输出（256 维，按模型卡说明决定是否归一化，并写进 manifest）；unixcoder 用均值池化（768 维）；
- 输出 emb_code_<model>.npz（数组 features，行顺序与 text.jsonl 一致）与 manifest（模型 SHA、revision、max_length、pooling、是否归一化、去重前后的数量、截断数量、耗时、torch/transformers 版本）；
- 确定性：同一输入运行两次，逐位一致或最大误差 ≤1e-6（写明是哪一种）。

## 4. 装配检查（mando）
登记 configs/S2.json（{CODE, concat}）。只用 carrier.load_modality 核对形状与行对齐，不训练（concat 在 NS-P4 实现）。

## 验收
两个视图、四个任务的 text.jsonl 与主编码器的向量齐全，测试通过；PROGRESS.md 记录截取方式分布、回退数、去重比例、耗时；提交 NS-P2。
```

### 5.5 Prompt NS-P3：事实、M2 字段与 M3a

```text
# NS-P3：StatementFacts（AST 后端）、M2 上下文字段、M3a 多热向量

## 1. 事实 schema 与后端（facts.py）
StatementFacts（每个节点一个，可 JSON 序列化）：
- external_kinds（集合：call、delegatecall、staticcall、send、transfer、member_call）、value_attached（bool）、is_external_call（bool）；
- state_reads、state_writes（[{var, shape: mapping|array|scalar}]）；
- defs、uses（[{var, kind: state|local|param|env, from_offset}]）；
- from_nodes（[{node, offset}]）、to_nodes（[{node, offset, sink}]）；
- reachable_from_ext_call、dominated_by_ext_call、write_then_later_call、call_then_later_write（bool）；
- guard：{kind: none|require|assert|if|while|modifier, operand_classes: 集合, pairs: 集合, offset} 或 None；
- func：{visibility, payable, view_pure, is_constructor, modifiers: [{name, resolved: bool, has_sender_guard: bool}]}；
- env_keys、return_handling（na|checked|assigned_unchecked|ignored）、arith（集合）、arith_on_state（bool）、loop_bound（none|const|state|param_local）、syntax_bag（集合）；
- unresolved（{原因: 计数}）。
FactBackend 接口：extract(task_id, file, view) -> {row_key: StatementFacts}。只实现 AstBackend：
- 函数内 CFG：按 NS-P0 的结论选择 semantic_cfg/l1_cfg（经投影映射），或用 HCG CFG 边作后备；只保留两端在同一函数内的边。入口是函数定义节点。
- 外部调用判定：
  - is_external_call(ast_node, ctx) -> (bool, kinds)：.call(、.call.value(、.call{、.delegatecall(、.staticcall(、.send(、.transfer( 都按 AST 形状判断；
  - 成员调用 x.f(...)：x 不是 this、super、msg、block、tx、abi，也不是本文件中声明的库名时，记为 member_call；
  - value_attached：.value(...) 或 {value: ...}。
- PRE_EXT_CALL：在函数内 CFG 上从本节点做反向 BFS，第一个外部调用节点（层数最小，同层取相对距离最小）；本节点自身不算。reachable_from_ext_call 由同一次搜索得到。
- 支配：networkx.immediate_dominators(函数子图, 入口)。dominated_by_ext_call、guard 都沿支配链向上取最近的一个：
  - require/assert 来自支配链上的 expression_statement；
  - if/while 来自支配链上的条件节点；
  - 都没有时，如果函数应用了 modifier，guard.kind = modifier。
  - operand_classes 由守卫条件的 AST 标识符分类得到：msg.sender、tx.origin 来自 env.py 的键；状态变量来自 L2 边或合约体声明；参数来自 AST 参数表；其余为局部变量、字面量、时间戳/区块号、调用结果。pairs 只记录比较运算两侧的类别组合。
- write_then_later_call / call_then_later_write：在函数内 CFG 上做正向可达性判断。
- DEF/USE/FROM/TO：来自 F3 图的 DATA_DEF_USE 边（拼写属性在主视图中经 8G 双射映射）；变量类别来自 L2 边（state）、L3 边（env）、AST 参数表（param），其余为 local。TO 的汇点类型由目标节点的 AST 角色判断：调用参数、value、守卫条件、对状态变量的赋值、return。
- STATE_R/W：READS_STATE/WRITES_STATE 边；shape 由声明类型判断（mapping、数组、其他）。
- ENV：ENV_FLOW 边。
- modifier 解析：在同一文件 AST 上，按拼写把函数头中的 modifier 调用解析到 modifier_definition；继承用 ClosedScopeJ。解析不到时 resolved=false，不猜测。has_sender_guard：modifier 体内存在操作数含 msg.sender 或 tx.origin 的 require/if。
- is_constructor：constructor 关键字，或者函数名与所在合约名的拼写相同。
- 所有 AST 结论都经投影映射到节点；投影不到的记入 unresolved。

## 2. M2 字段（ctx_fields.py）
ctx_fields(facts, text_view) -> 每个节点一个 JSON 对象：
{STMT, FUNC, DEF, USE, FROM, TO, STATE_R, STATE_W, ENV, PRE_EXT_CALL, GUARD}，字段顺序与格式按第 4.5 节，缺失写 "-"；相对距离写成 @-k/@+k；FROM/TO 最多各 2 条，按 |offset| 排序。
输出 artifacts/ctx_v1/<view>/<task_id>/ctx_fields.jsonl 与 manifest。
nodesem 侧 offline/encode.py 新增 --ctx 模式：读取字段，用编码器 tokenizer 按第 4.5 节的顺序逐级截断到 256 个 token，再编码。manifest 记录每级截断的数量；输出 emb_ctx_<model>.npz。

## 3. M3a（static_profile.py）
- behavior_schema.json：字段名、组、编码方式（独热或多热）、列区间。总维度写进 schema，不写死在代码里。
- encode(facts) -> uint8 向量；输出时转成 float32 写入 static.npz。
- explain(vec) -> 字段名列表，并保证 encode/explain 往返一致。
- 辅助节点与非语句节点的默认值按第 4.6 节。

## 4. 测试（必须使用真实 tree-sitter 解析，fixture 放在 tests/fixtures/nodesem_oracle/，先写期望 JSON 再运行）
至少覆盖以下用例：
a) msg.sender.call.value(_am)() 独立语句 → call、value_attached、转账、返回值 ignored；
b) if (!msg.sender.send(x)) throw; → send、返回值 checked；
c) (bool ok, ) = a.call(data); 之后不在条件中使用 ok → assigned_unchecked；
d) 在 call 之后执行 balances[msg.sender] -= amount; → 写 mapping、减法、作用于状态变量、reachable_from_ext_call、msg.sender；
e) require(msg.sender == owner); owner = x; → 第二句 guard=require，operand 含 msg.sender 与状态变量，pairs 含 env 对状态变量；
f) require(tx.origin == owner_state) 与 require(tx.origin == _param) → pairs 分别为 env 对状态变量、env 对参数（phishable 与 SolidiFI 模板的区别）；
g) modifier onlyOwner { require(msg.sender == owner); _; } 应用到 function kill() onlyOwner { selfdestruct(owner); } → modifier 解析成功、has_sender_guard、guard.kind=modifier、语法袋含 selfdestruct；
h) pragma 0.4.x，contract Wallet { function Wallet() public {...} } → is_constructor；函数名与合约名不同时为 false；
i) for (uint i = 0; i < users.length; i++) users[i].transfer(1); → transfer，循环边界为状态变量或数组长度；
j) 状态变量先写、后发生外部调用 → write_then_later_call；
k) if (now > deadline) {...} 内的语句 → guard 操作数含时间戳。
另加：
- 视图一致性：四个任务中，主视图与次要视图的 StatementFacts（名字按双射还原后）和 M3a 向量逐节点相同。不一致必须逐条列出原因，不得放宽；
- M2 字段的泄漏测试：主视图中只出现保留名或匿名名；没有绝对行号；
- 禁止属性扰动后输出不变；
- 独热组每个节点恰好一个 1。

## 5. 真实数据统计（不训练）
按任务统计：各字段的非空率；unresolved 的原因分布；CFG 后备使用比例；modifier 解析的成功、失败、继承比例；guard 各类型比例；截断级别分布；M3a 每一维的取 1 比例（只做描述，不按标签分组，不用于调参）。

## 验收
测试与统计通过；PROGRESS.md 记录；提交 NS-P3。
```

### 5.6 Prompt NS-P4：融合、无图对照与 CPU 冒烟

```text
# NS-P4：concat/gated 融合、模态 dropout、layers=0、S2–S4-noG 配置与 CPU 冒烟

## 1. 融合（adapter.py）
- concat：对每个连续模态 m（CODE、CTX、STUDENT、TEACHER*）做 LayerNorm(d_m) → Linear(d_m,128)；STATIC 不做 LayerNorm，直接 Linear(75,128)；TOKEN_IDS（如果存在）走 embed_pool。输出 h = Σ_m p_m · z_m + b（共享偏置 b，各 Linear 不带偏置）。
- gated：z_m 的计算同上；logits = W_g [p_1 z_1; …; p_M z_M]（Linear(M·128, M)）；p_m=0 的 logit 置为 −inf；全部缺失时 h=b；否则 g = softmax(logits)，h = Σ g_m z_m + b。last_gates 保存为 detach 后的 CPU 张量。
- 模态 dropout：只在 self.training 时生效。每次 forward 用一个 CPU torch.Generator 生成伯努利掩码（种子 = parameter_seed(fit 种子, "modality_dropout", [task_id, fold, profile, spec_digest]) 加上当前 forward 计数），再移到设备上。掩码作用在存在位上。全局随机数不受影响。
- 参数初始化按第 4.9 节；参数名稳定（例如 adapt_ws.3.proj.CODE.weight），写进测试。

## 2. layers=0
spec.layers=0 时，make_nodesem_model 传 layers=0 给 make_model。按 NS-P0 实验 C 的结论确认：作者 forward 可以直接使用；只在 G0 上使用；节点任务与合约任务都能前向和反向。

## 3. 配置登记
configs/S2.json、S3.json、S4.json、S4g.json、S4-noG.json（主视图，CODE 与 CTX 用主编码器）。记录每个配置的 carrier_dim（预期 S4 约 590）。

## 4. CPU 证明与冒烟（不是正式训练）
在 reentrancy_node fold0 上（G3R；S4-noG 用 G0）：
- 每个配置构造模型、加载初值、调用 benchmark_v2.trainer.fit 跑 1 个 epoch（config 只把 maximum_training_epochs 改为 1，写明这是冒烟配置），记录：loss 是否有限；新模块参数是否有非零梯度；gcs/classify 初值是否与 8H 相同；构造耗时；载体维度；按张量大小估算的显存。
- gated：每个节点的门控权重之和为 1（误差 ≤1e-6）；全部缺失时输出等于偏置，没有 NaN。
- 模态 dropout：p=1 时所有存在位为 0，输出等于偏置；p=0 时与关闭 dropout 逐位相同；同一 fit 种子两次运行逐位一致。
- 构造耗时：如果 S4 的构造时间超过 8H 构造时间的 3 倍，在 PROGRESS 中报告；不要自行修改 get_node_token。

## 5. 测试
- concat 的线性等价：把各模态拼接后做一次 Linear，结果与 Σ p_m z_m 逐位相同（不做 LayerNorm 的情形）；
- gated 的掩码与归一化；
- dropout 的确定性与“只在训练模式生效”；
- 参数名稳定；
- layers=0 的前向与反向。

## 验收
测试与冒烟通过；PROGRESS.md 记录每个配置的 D、构造耗时、冒烟结果；提交 NS-P4。
```

### 5.7 Prompt NS-P5：批次 N-A 的计划与封存（不训练）

```text
# NS-P5：N-A 计划（{S1,S2,S4} × {G0,G3R} × 30 折 = 180 次新 fit，另外引用 S0 的 60 个 8H 结果）

## 1. 准备
- 为每个（配置、任务）写好载体 NPZ 与 manifest（主视图）；核对行身份。
- 为 180 个 job 生成零步初值（node_sem.init），记录文件 SHA 与 state SHA；在 CPU 上逐个构造并核对 digest。
- S0 × {G0,G3R} × 30：只写入对 8H receipt 与初值的引用，并逐个只读 verify。

## 2. plan（排他创建 artifacts/batch_NA_v1/）
- job：task_id、fold、seed=1、profile、spec（引用与 digest）、图引用、label_view、folds、初值、载体、config（与 8H 相同）。
- 预先登记（写进 plan，以后不能改）：
  - 主终点：reentrancy_node、G3R、S4 − S0，L-audit best 外层 BF1，10 折配对，双侧 Wilcoxon；
  - Holm 家族（reentrancy_node、G3R）：S4−S0、S1−S0、S2−S0、S4−S2；
  - 交互项（描述）：(S4−S0)_G3R − (S4−S0)_G0，并附第 3 节第 21 条的解读说明；
  - 其余任务和比较只作描述；访问控制附 20 个非 SolidiFI 正例的逐节点概率表；
  - S* 选择规则：inner_val best BF1，先在折内平均，四个任务等权；在 S1/S2/S4 × G3R 中选择；平局时取载体维度更小的；
  - 报告必含项：第 4.12 节全部。
- runtime：_code_refs() ∪ node_sem 代码 SHA。
- 估算本机耗时与显存（依据 8H 的实测和 NS-P4 的冒烟）。

## 3. 授权模板
authorization.template.json（execution_authorized=false；需要用户填写：标签方案 L-audit、seed=[1]、运行位置、资源策略 local_dev_v1）。停下等用户授权。

## 测试
plan/seal 篡改检测；S0 引用的 receipt 被修改时拒绝；runtime 变化时拒绝启动。

## 验收
plan 与 seal 封存，PROGRESS.md 记录耗时估计；提交 NS-P5。不训练。
```

### 5.8 Prompt NS-P5A：执行 N-A 并报告（用户授权后）

```text
# NS-P5A：执行 N-A

1. 把用户授权原文写入 artifacts/batch_NA_v1/authorization.json（排他创建），绑定 plan 与 seal 的 SHA，写明 job 数为 180（另有 60 个复用）。
2. 开训前证明：
   - 用新 plan 重新执行 NS-P1 的 S0 等价检查（CPU，2 epoch），作为回归；
   - 试点：完整跑 2 个正式 fit（reentrancy_node fold0 G3R S4；reentrancy_contract fold0 G0 S1），记录耗时与显存。试点结果计入正式产物，不重跑。
3. 按 plan 顺序串行运行剩余 fit，每项一个独立子进程。失败就停，保留现场；重试必须经用户批准（沿用 8H 的 attempt_00k 规则）。运行中只记录进度，不汇总任何 F1。
4. 完成后：verify 180/180，并只读核对 60 个 S0 引用。
5. 报告（node_sem/reporting.py，复用 benchmark_v2.reporting 的 wilson、scored、stratified_score 与 experiment/stats.py）：
   - 先只按 inner_val 选出 S*（封存 selection.json），然后才读取 outer_test；
   - 主表：四个任务 × 配置 × 剖面的折均 BF1；
   - 主终点与 Holm 家族（差值均值、95% bootstrap 区间、提升/持平/下降、A12、Wilcoxon 原始 p 与 Holm 校正后的 p）；
   - 交互项；
   - 第 4.12 节的全部必含项，包括注意力饱和诊断：对 S0、S1、S2、S4 × G3R 的 best checkpoint 各做一次 eval 前向，统计第一层每个关系 head 最大权重 ≥0.99 的比例（方法同 dfg_v2/attention_probe.py）；
   - 写 artifacts/batch_NA_v1/reports/REPORT.md 与 report.json，以及 scripts/node_sem/NS_P5A_REPORT.md。然后停下。
```

### 5.9 Prompt NS-P6：批次 N-B

```text
# NS-P6：N-B（S3 × G3R、S4g × G3R、S4-noG（G0，layers=0），共 90 次 fit）

流程同 NS-P5 + NS-P5A：先计划与封存，等授权，再执行与报告。目录 artifacts/batch_NB_v1/。
- 预先登记的比较（全部只作描述）：S4−S3、S3−S2（S2 引用 N-A 的结果）、S4g−S4、S4−S4-noG（S4-noG 与 G3R 上的 S4 比较，并另报与 G0 上 S4 的比较）。
- 报告另加：S4g 中按节点类型统计的门控权重均值与分布。
- 引用 N-A 结果时，按 receipt SHA 只读核对。
```

### 5.10 Prompt NS-P7：M3b LLM 描述（本机试点）

```text
# NS-P7：LLM 行为描述管线（本机试点）

## 0. 用户准备
在 nodesem 环境中安装 llama-cpp-python（CUDA 版本），或准备 llama-server；下载一个 3B 级代码指令模型的 GGUF Q4 文件（例如 Qwen2.5-Coder-3B-Instruct 的 Q4_K_M）。把路径告诉 Codex。Codex 记录 SHA、llama.cpp 版本与运行参数（n_ctx 4096、n_gpu_layers、temperature 0、seed 0）。

## 1. 提示输入（mando，llm_inputs.py）
对每个函数单元（function、constructor、modifier、fallback）：
- 从主视图改名源码中取出函数的 AST 范围；在 AST 上删除 comment 节点，重新解析检查 ERROR=0；
- 函数内按首次出现顺序把非保留 identifier 重新编号为 a1, a2, …；同一合约的状态变量声明用同一张编号表；
- 每行加 "L<相对行号>| " 前缀。需要描述的语句：该函数内除 end_if、end_loop 和函数定义本身以外的 HCG 节点，按节点 AST 起始位置换算成相对行号；
- 保存 prompt_map：{相对行号: [row_key...]}、{a_k: 匿名名}；
- 超过 120 行的函数按 60 行分段，每段附签名；
- cache_key = sha256(模板版本 + 模型 SHA + 提示全文)；按 cache_key 去重。
输出 artifacts/llm_v1/inputs/<task_id>.jsonl 与 manifest（函数数、去重数、行数分布）。
测试：重新编号是双射，还原后与原函数逐字一致；去注释后 ERROR=0；行号到节点的映射与 AST 一致；提示中的 identifier 只能是保留名或 a_k；提示中没有原名和绝对行号。

## 2. 提示模板（写成模块常量，模板版本 describe_v1）
SYSTEM:
You describe what Solidity code does. You never assess security.
Rules:
1. Describe behavior only: what each statement reads, writes, computes, calls or checks, and its role in the function.
2. Do not judge safety. Never use these words or their variants: vulnerability, vulnerable, reentrancy, reentrant, exploit, attack, attacker, unsafe, insecure, risk, risky, bug, flaw, overflow, underflow, malicious, dangerous, safe, secure.
3. Identifiers have been renamed (a1, a2, ...). Do not guess their original names.
4. If unsure, write "unknown".
5. Output JSON only, matching the schema exactly.
USER:
Contract state variables:
{state_vars}
Function:
{function_with_lines}
Describe the statements at these lines: {line_list}
Schema: {"function_intent": "<= 25 words", "statements": [{"line": int, "role": one of [input_validation, access_check, state_read, state_update, value_transfer, external_call, computation, event_emit, control, other], "summary": "<= 20 words", "reads": [str], "writes": [str], "external": bool}]}
judge_v1（只用于 S7）：在 Rules 第 2 条处改为要求增加 "security_note": "<= 20 words, possible weaknesses"，schema 加上该字段。

## 3. 生成（nodesem，offline/llm_describe.py）
- 用 JSON schema 语法约束输出；温度 0，seed 0；每个 cache_key 写一个原始响应文件（含耗时、输入和输出 token 数）。
- 解析失败时重试 1 次（在 user 末尾追加 "Return valid JSON only."），仍然失败就标记 parse_failed。
- 先跑试点：用固定种子抽 50 个函数单元（按任务分层），输出 pilot_report.json（耗时、token 数、解析成功率、黑名单命中率、忠实性分布、3 个完整样例）。停下等用户确认，再全量运行 describe_v1 和 judge_v1。
- 试点允许使用 llama.cpp 的 CPU 模式（n_gpu_layers=0）运行，这样可以与 N-A 训练并行，尽早发现 3B 模型质量不足的风险。CPU 与 GPU 的输出不保证逐位相同；正式全量运行固定一种模式，并写进 manifest。

## 4. 后处理（mando，llm_post.py）
- 校验 line 在列表内；同一行取第一条；role 规范化；
- 黑名单正则过滤 summary 与 intent（只用于 describe_v1）；
- 忠实性：把名字按 prompt_map 还原为匿名名，再与 NS-P3 的 StatementFacts 比较。公式见第 4.7 节；
- 有效节点：解析成功、行号有效、faithfulness ≥ 0.5、summary 非空；
- 输出 teacher_text.jsonl（row_key、role、summary、intent、faithfulness、flags）与 stats.json（函数数、去重调用数、token 数、耗时、parse_failed、missing、judgement_filtered、unfaithful 的比例、faithfulness 分位数、role 分布）。

## 5. 教师向量（nodesem，offline/teacher_encode.py）
文本 "role: {role}. {summary}. function: {intent}"，用 bge-small-en-v1.5（normalize_embeddings=True）编码，得到 384 维。无效节点写零向量，并在 manifest 中把存在位标记为 0。输出 teacher.npz；judge_v1 的结果另存为 teacher_judge.npz（manifest 标注 control_judgement）。

## 测试（使用 FakeBackend，不调用真实模型）
解析与重试；行号校验；role 规范化；黑名单置空与计数；忠实性的三种情形（完全一致 = 1、部分一致、完全不一致 < 0.5）；缓存命中时不调用后端。

## 验收
试点报告提交并停下；用户确认后全量运行；PROGRESS.md 记录 stats.json 的关键数字；提交 NS-P7。
```

### 5.11 Prompt NS-P8：学生蒸馏与批次 N-C

```text
# NS-P8：按折蒸馏学生；N-C（{S5,S6,S7,S8} × G3R × 30 折 = 120 次 fit）计划与封存

## 1. 学生（mando CPU，student.py）
按第 4.8 节实现 train_student(task_id, fold, view)：
- 训练节点：该折 inner_train 文件中、教师有效的原节点；早停节点：inner_val 文件中、教师有效的原节点（文件划分读取 8D 冻结折）；
- 导出前执行防泄漏断言：
  1. 训练集与早停集中没有 outer_test 文件的节点；
  2. 训练集与早停集不相交；
  3. 学生代码没有读取标签（白名单加扰动测试）；
- 导出全部节点（含辅助节点）的 s_sem，写成 student_<task_id>_fold<k>.npz 与 manifest。manifest 记录训练节点数、早停轮次、inner_val 余弦、outer_test 有效节点上的余弦（只作诊断）、角色准确率、学生权重 SHA。

## 2. S8 置换
在同一任务、同一折、同一节点类型内，用固定种子（parameter_seed(fit 种子, "S8", [task_id, fold])）对 s_sem 的行做置换；manifest 记录置换。

## 3. 载体与配置
S5（S4 + STUDENT，按折）、S6（S4 + TEACHER）、S7（S4 + TEACHER_JUDGE）、S8（S4 + 置换后的 STUDENT）。注意：S5 和 S8 的载体按折生成（feature_view 与 feature_npz 也按 job 分别引用）。

## 4. 计划与封存
目录 artifacts/batch_NC_v1/。预先登记：
- Holm 家族（reentrancy_node、G3R）：S5−S4（主比较）、S6−S5、S7−S6、S5−S8；S4 引用 N-A 的结果；
- 注明这是本机 3B 试点版本，正式结论以服务器复跑为准。
写授权模板，停下。执行与报告同 NS-P5A，另加 LLM 成本表与学生诊断表。

## 测试
小数据（2 个文件、2 折）上训练并导出，覆盖全部节点；人为注入一个 outer_test 节点时断言抛出；同种子两次导出逐位一致。
```

### 5.12 Prompt NS-P9：原名视图（次要终点）与汇总

```text
# NS-P9：N-D（原名视图 {S0,S4} × G3R × 30 折 = 60 次 fit）与 NodeSem 汇总报告

- 原名视图的 S0 使用 8G 的 original view token；S4 使用 NS-P2/P3 中原名视图的特征（M3a 与主视图逐位相同，CODE/CTX 是原名文本的编码）。
- 流程同 NS-P5 + NS-P5A，目录 artifacts/batch_ND_v1/。所有比较只作描述，不进入任何统计家族。
- 汇总报告 scripts/node_sem/NODESEM_REPORT.md：
  - N-A 到 N-D 的主表；
  - 主终点与各 Holm 家族；
  - 交互项及其解读；
  - 访问控制 20 个真实正例的逐节点概率表（S0、S4、S5）；
  - 注意力饱和与门控分析；
  - LLM 成本与忠实性；
  - 与 8H 的对照；
  - 局限：单 seed、本机、传导式设定、SolidiFI 占主导、访问控制饱和、3B 试点模型、L-audit 不是金标准。
```

### 5.13 以后执行：服务器复跑

```text
# 服务器复跑（本机结果出来后由用户决定何时开始）
- 环境复现、输入迁移与 SHA 核验（参照 DFG PROMPTS.md 第 4.9h 节）。
- 用更大的 LLM 重跑 NS-P7（新的模板版本号与缓存），更新教师与学生；多 seed 重跑 N-A 与 N-C 的关键配置。
- 服务器结果单独封存，不与本机结果混合。
```

---

## 6. 里程碑

| 里程碑 | 包含 | 产出 | 需要用户决定的点 |
|---|---|---|---|
| M1 | NS-P0 | RECON.md、载体接入点的实测结论 | 接入点不成立时 |
| M2 | NS-P1–P4 | 特征管线、S0 等价证明、CPU 冒烟 | 准备 nodesem 环境与模型（NS-P2 第 0 节） |
| M3 | NS-P5/5A | N-A 的结果（主终点） | 授权 N-A |
| M4 | NS-P6 | N-B 的消融 | 授权 N-B |
| M5 | NS-P7–P8 | LLM 试点与 N-C | 准备 LLM；试点后确认全量运行；授权 N-C |
| M6 | NS-P9 | 原名视图与汇总报告 | 授权 N-D |
| 以后 | 服务器 | 正式多 seed 结果 | 何时迁移 |

即使 LLM 部分受阻，M3 和 M4（完全不依赖 LLM）也足以支撑一个完整的节点增强创新点：可学习嵌入、预训练代码向量、DFG 上下文和静态画像四个层次的消融，加上与 DFG 的互补性分析。
