# EdgeSem v1：MANDO-LLM 第三个创新点（边语义增强）方案与 Codex Prompts

版本：r2（2026-11-10）。分支：`edge-sem`，从 `node-sem@306c135b` 切出。
设计文档（可评论）：MANDO-LLM Edge Semantic Enhancement — Design v3（https://claude.ai/artifact/DoZLiFncW2mrxWJwWfKaFn）。本文第 1–3 节是该设计在代码层面的落地版本；两者不一致时以本文为准，并在 PROGRESS.md 记录。

**r2 相对 r1 的修改**（独立复核“Mando-LLM node-augmentation scheme”对话最后一条消息提出的 11 项问题；逐项对照代码或封存数据核实后修改；其中第 6、9 项经实测不成立或被高估，只做记录或缩小范围）：
1. 共享参数复制：`copy_common_layer_parameters` 要求锚模型的全部关系键都在新模型中，typed 模式下被反射出的 `(B, e, A)` 键会消失并报错；它还把新关系行填 0（`relation_pri` 填 1），与“按名字种子初始化”矛盾。改为 edge_sem 自己的映射复制函数（EP1）。
2. 稀疏关系共享从未接入 `HGTLayer`（每个关系键一行参数），本地阶段取消，`min_edges = 0`，只报告计数。
3. 名字不变性闸门改为在图节点空间比较：`anon_binding.replace_spans` 把名字换成长度不同的 `vN`，字节锚点必然偏移。
4. 统计检验更正为 `experiment/stats.py` 实际使用的双侧 zsplit Wilcoxon；每个联合假设的 p 值取两项中的较大者，再对 H1、H2 做 Holm。
5. H1 改为 G4R 对 G3R-T（而不是 G3R），去掉方向修正的混杂；G3R-A 改为 G3R-TA（建在 G3R-T 上）。
6. GUARDS 扇出：封存事实实测每条语句约 1.0 条守卫记录（reentrancy_node 6956/6635，access_control_node 4537/4664，最多 13），不构成问题；保留“守卫 → 全部被保护语句”，因为只连敏感语句会漏掉受算术边界检查保护的语句。
7. 增加 5 个未知位（unk_cfg、unk_dfg、unk_order、unk_state、unk_guard）：封存事实中 order 为 unknown 的语句占 5.6–9.6%，dfg 占 6.6–11.4%；规则基线排除 guard_status 为 unknown 的语句并报告数量。
8. 核心位由 EP4 的端点检验在训练前确定：对每个源节点的全部出边（或每个目标节点的全部入边）恒定的位视为端点事实，移入上下文组。预计调用位与被调函数位会移出。
9. P2 的理由只保留“完成退火阶段”：按本协议计算，50 步的累积 Adam 步长约 0.26，现行停止点为 0.11–0.24，P2 不会显著改变零初始化参数能移动的幅度，也不是“零初始化必然无效”的补救。EP7 增加一折试点，报告 u、U 的范数。
10. D1–D3 在 EP7 之前必须有用户确认记录；未确认不得开始训练。
11. 措辞修正（recursive_method_call 一句）；u 按关系键各一行。

使用方式：每次开新会话，先贴第 4.1 节共享上下文，再贴一个 Prompt。顺序：EP0 → EP1 → EP2 → EP3 → EP4 → EP5 → EP6 → EP7 → EP8 → EP9。每个 Prompt 结束后先交审查，通过后再进下一个。

---

## 1. 现状（2026-11-10 逐项核对代码与数据）

### 1.1 作者图的边类型（不是“几乎全是 next”）

benchmark v2 训练使用的是作者预编译图（DFG v2 的 F0，F3 = F0 + DFG v2 关系）。`scripts/DFG/dfg_v2/RECON.md` 记录的重入合约任务边计数：

| 边类型 | 数量 | 含义 |
|---|---:|---|
| next_line | 10161 | 顺序控制流（循环回边也在其中） |
| neg_next / pos_next | 1260 / 578 | 假分支 / 真分支 |
| end_if | 568 | 分支汇合 |
| first_next_line | 157 | 函数入口 → 第一条语句 |
| external_call / internal_call | 1589 / 973 | 函数 → 函数调用（不同合约 / 同一合约） |
| recursive_method_call | 3981 | 合约 → 函数的归属边（数量 = 函数 3651 + 构造函数 165 + 修饰器 165） |

仓库里的 tree-sitter 建图器 `process_graphs/.../CFG_solidity.py` 确实把多数边写成 `next`，但只有用它重建图时才有影响，不属于本阶段。

### 1.2 方向丢失

`sco_models/graph_utils.py::reflect_graph`（426–446 行）：两端节点类型相同时，正反向边拼进同一关系；类型不同时，反向边用同名 `(B, e, A)`，与图中本就存在的同名正向关系合并。只有 `DATA_DEF_USE` 被本地补丁豁免。DFG v2 的 `model_input.py::materialize` 为自己的四种关系加了 `REV_*`，基础边仍走 `reflect_graph`。

### 1.3 模型路径

- G3R 基线固定为 `layer_impl="shared_projection"`、`reducer="mean"`（`experiment/batch_plan.py` 第 57、200、273 行），对应 `dfg_v2/hgt_layer.py::HGTLayerSharedProjection`。
- `dfg_v2/model.py::_construct` 调用 `materialize(edge_data(nx), profile)`，`profile` 必须在 DFG v2 的 `PROFILES` 中；`validate_registration` 会重新 `materialize` 并逐条比较端点，还检查 `type(layer) is expected_layer`。所以新剖面不能直接走 `make_model`。
- 可直接借鉴的先例：8H 的 G0P 安慰剂（`benchmark_v2/runtime_model.py`）。它从新鲜的 G0 锚模型深拷贝，换图数据，按新 etypes 重建层，用 `diagnostics8c/placebo.py::copy_common_layer_parameters` 复制共享参数，再用自己的 `validate_registration`（非 G0P 时委托原函数）。EdgeSem 的派生模型完全照此模式。
- 视图：`benchmark_v2/feature_view.py` 只替换 token 数组；节点、节点顺序、边在原名与 N-anon-s 视图下完全相同。所以边与边属性只需在原图上计算一次。

### 1.4 训练协议（8H）

Adam + OneCycle，`schedule_epochs`=50，`maximum_training_epochs`=50，initial_lr 0.0005，max_lr 0.01，div_factor 20，final_div_factor 1，patience 7，delta 0.001，hidden 128，2 层，8 头，seed=1，节点任务 10 折、合约任务 5 折，每个 epoch 一次全图更新，按 inner_val loss 选 best（`experiments/checkpoint.py::StopMonitor` 保存每一个严格的新最小值，patience 大于 50 即等于不早停）。早停使节点任务停在第 18–37 轮，退火阶段基本不执行。统计检验：`experiment/stats.py` 对节点任务用双侧、zsplit、不校正连续性的 Wilcoxon（mode=auto）。

### 1.5 可复用的语义事实（NodeSem）

- `scripts/node_sem/facts.py::extract(task_id)` 输出每个节点的 `StatementFacts`（`facts_schema.py`）：`external`（调用种类、带值、返回值处理）、`state`（读写）、`dfg`（defs/uses 的 kind，to 的 sink）、`order`（外部调用前后）、`arith`（运算符、unchecked）、`loop`、`function_ctx`、`fn_summary`（函数级：写状态、外部调用等）、`env`、`guards`。
- `extract` 只允许 `view="original"`（实验政策）。`extract_source(source_text, ...)` 接受任意源码文本，可用于名字不变性闸门。
- 守卫：`facts_guards.GuardAnalyzer.for_node(node)` 返回守卫记录，`kind` ∈ {require, if_branch, early_exit, loop_cond, modifier, internal_check}，含 `operand_classes`、`is_sender_guard`，以及内部字段 `_anchor`（守卫条件的 AST 节点）。修饰器守卫的 `_anchor` 位于修饰器体内；序列化时 `facts.py::_relative` 要求同一 owner，所以修饰器守卫的 `offset` 为 None——**从序列化事实无法恢复修饰器守卫的源节点**，GUARDS 必须在进程内用 `GuardAnalyzer` 构建。
- `facts_io.load_context(task_id)` 读取 8H plan 与 `graphs_v2_r1/store.json` 的 F0/F3 图、源码和 L1–L3 证据，全部带 SHA 校验。
- 修饰器解析统计：`GuardAnalyzer.audit`（modifier_resolved / modifier_unresolved / modifier_inherited）。

### 1.6 尚未具备的条件（影响七类推广）

DFG v2 图存储、benchmark v2（分组折、L-audit、匿名化）与 NodeSem 事实只覆盖重入与访问控制。其余五类（算术、拒绝服务、抢先交易、时间操纵、未检查低级调用）需要在服务器阶段先完成 E-C0 移植，包括对 `_intou`、`_tmstmp`、`_TOD`、`_unchk` 等 SolidiFI 注入名做匿名化。本文的 EP0–EP9 不包含 E-C0。

---

## 2. 决策

| 编号 | 决策 | 状态 |
|---|---|---|
| D1 | 主终点视图：N-anon-s（与 DFG 8H 一致），原名视图仅在服务器阶段作描述性次要终点。注意：这与 NodeSem 阶段用户选定的“原名为主视图”不同 | 建议；EP7 之前必须有用户确认记录，未确认不得训练 |
| D2 | 训练协议 P2：跑满 50 轮，保留 inner_val loss 最好的 checkpoint；其他配置与 8H 相同；G3R 基线在 P2 下重跑，不复用 8H 结果。理由只是完成退火阶段、不在学习率峰值附近选模型 | 建议；EP7 之前必须有用户确认记录 |
| D3 | 通用性规则：EP9 结束后冻结关系列表、属性布局和超参数，原样用于七类，不做按类别的特征选择或调参 | 建议；EP7 之前必须有用户确认记录 |
| D4 | 节点特征：主比较用 S0（8H 的匿名 token 特征），NodeSem 特征不进入本阶段；服务器阶段加 S2 臂 | 已定 |
| D5 | 新关系只有 MOD_APPLY、CALL_SITE、GUARDS 三种；不加“外部调用后写状态”这类单一漏洞规则边 | 已定 |
| D6 | E3 两项（注意力偏置、加性边消息）全部零初始化；不使用乘性 FiLM | 已定 |

---

## 3. EdgeSem v1 方案

### 3.1 E0：方向

- **typed 反向**：每个基础关系 `(A, e, B)` 额外生成 `(B, "REV_" + e, A)`，正反向永不合并。模式 `merge` 调用作者 `reflect_graph`，必须与 G3R 逐元素一致；模式 `typed` 是新行为。DFG v2 的四种关系及其 `REV_*` 保持 DFG v2 的处理。
- **cf_back（可选）**：在 DFG v2 语义 CFG 上用支配关系识别循环回边（目标支配源），把对应的 `next_line` 改为 `cf_back`；不得用行号。EP0 统计数量，少于 50 条/任务则不启用，记录理由。
- **参数初始化（r2）**：`HGTLayer` 为每个关系键分配一行 `relation_att`/`relation_msg`/`relation_pri`。typed 模型的参数由锚模型（G3R）映射得到：typed 键 `(A, e, B)` 与 `(B, REV_e, A)` 都从 G3R 中承载这些边的合并键复制（同类型两端时是 `(A, e, A)`，不同类型时分别是 `(A, e, B)` 与 `(B, e, A)`）；DFG v2 关系逐键复制；只有 G3R 中没有对应来源的新关系（E1 及其 REV_）才按 sha256(规范键字符串) 派生的种子做与 `HGTLayer` 相同的初始化（att、msg 用 xavier_uniform，pri 为 1）。
- **稀疏关系共享**：本地阶段不启用（`min_edges = 0`，每个关系键一行参数）；EP0 报告每关系边数，服务器阶段若需要再单独设计并登记。

### 3.2 E1：三种新关系（各带 REV_）

| 关系 | 方向 | 构建方式 |
|---|---|---|
| MOD_APPLY | 函数/构造函数定义节点 → 被应用的修饰器定义节点 | 函数头 `modifier_invocation`，按 `GuardAnalyzer._modifiers` 同样的规则解析（含继承）；解析失败不建边并计数 |
| CALL_SITE | 含内部调用的语句节点 → 被调函数定义节点 | `AstSemantics` 的调用解析；只连到同一文件内能唯一解析的 function/modifier/constructor 定义；外部合约调用、低级调用、库调用不建边 |
| GUARDS | 守卫条件所在节点 → 它保护的语句节点 | 进程内 `GuardAnalyzer.for_node`，把每条守卫记录的 `_anchor` 经 Projector/AST 身份映射到图节点；修饰器守卫直接连到被修饰函数内的语句；映射不到的守卫丢弃并计数。目标包括全部被保护语句（封存事实中每条语句约 1.0 条守卫记录，最多 13），不只连状态写或外部调用 |

自环、重复边：同一 (源, 目标, 关系) 只保留一条，计数。

### 3.3 E2：边属性（uint8[73]）

准入规则：(1) 在同一关系内会变化；(2) 描述两端的关系而不是单个端点；(3) HGT 两层内难以从拓扑恢复。0–54 与 68–72 是**核心候选**，55–67 是节点上下文组（只在剖面 G4R-AC 中启用）。核心候选是否真正进入核心，由 EP4 的端点检验在任何训练之前决定（见下文），结果写入 attrs manifest 的 `core_indices` 并在 EP9 冻结。反向边复制正向边的向量。

| 索引 | 名称 | 适用边 | 来源 |
|---|---|---|---|
| 0 | ctrl_src_dominates_dst | 控制边 | 语义 CFG 支配树 |
| 1 | ctrl_dst_postdominates_src | 控制边 | 语义 CFG 后支配树 |
| 2 | ctrl_branch_contains_ext_call | pos_next/neg_next | 分支内语句 `external.kinds` 非空 |
| 3–6 | var_kind {state, local, parameter, environment} | 数据边 | `dfg.uses/defs[].kind`；ENV_FLOW 为 environment |
| 7–14 | value_shape {mapping, array, address, integer, bool, bytes_string, struct_contract, other} | 数据边 | `facts_schema.SHAPES`（变量的声明类型） |
| 15 | def_weak_update | DATA_DEF_USE、WRITES_STATE | DFG v2 L1 证据中的 strong/weak；若证据中没有该字段，此位恒 0 并在 EP0 报告 |
| 16–19 | def_kind {assign, compound, decl_or_param, incdec_or_delete} | DATA_DEF_USE | 定义语句的 `syntax` |
| 20 | def_loop_carried | DATA_DEF_USE | def 到 use 的语义 CFG 路径经过回边 |
| 21 | use_path_crosses_ext_call | DATA_DEF_USE、READS_STATE | 存在外部调用语句 x：x 从 def 可达且 use 从 x 可达（同一函数） |
| 22–26 | use_context {condition, call, arithmetic, state_write_value, return} | 数据边 | `dfg.to[].sink`：guard/loop_bound→condition；call_arg/call_target/call_value/value→call；arith→arithmetic；state_write/state→state_write_value；return→return |
| 27–29 | arith_op {additive, multiplicative, exponent} | 数据边（use_context 含 arithmetic） | `arith.ops` |
| 30–33 | write_shape {scalar, mapping, array, struct_member} | WRITES_STATE | `state.writes` 与声明形态 |
| 34–36 | write_op {assign, increase, decrease} | WRITES_STATE | `syntax`：assign / add_assign / sub_assign |
| 37 | call_low_level | use_context=call 的数据边 | `external.kinds` ∩ {call, send, delegatecall, staticcall} |
| 38 | call_delegatecall | 同上 | `external.kinds` |
| 39 | call_sends_value | 同上 | `external.value_attached` |
| 40 | call_return_checked | 同上 | `external.return_handling` ∈ {checked_in_require, checked_in_if, assigned_checked} |
| 41 | call_callee_writes_state | CALL_SITE、internal_call、external_call | 被调函数 `fn_summary.state_write` |
| 42 | call_callee_external_call | 同上 | 被调函数 `fn_summary.external_call` |
| 43–48 | guard_kind {require, if_branch, early_exit, loop_cond, modifier, internal_check} | GUARDS；MOD_APPLY（修饰器内守卫的并集） | 守卫记录 `kind` |
| 49–54 | guard_operands {caller_identity, block_time, amount_balance, external_result, hash, state} | 同上 | `operand_classes`：msg.sender/tx.origin→caller_identity；timestamp/block→block_time；msg.value/balance→amount_balance；external_result；hash；state |
| 55 | ctx_src_is_ext_call | 全部 | 源节点 `external.kinds` 非空 |
| 56 | ctx_dst_is_ext_call | 全部 | 目标节点 |
| 57 | ctx_src_after_ext_call | 全部 | 源节点 `order.reachable_from_ext_call` |
| 58 | ctx_dst_after_ext_call | 全部 | 目标节点 |
| 59 | ctx_in_loop | 全部 | 目标节点 `loop.bound` ≠ none |
| 60 | ctx_leads_to_exit | 控制边 | 目标节点 `syntax` 含 exit 或 return |
| 61 | ctx_unchecked_arith | 数据边 | 目标节点 `arith.in_unchecked` 或文件 pragma < 0.8 |
| 62 | ctx_fn_externally_visible | 全部 | 目标节点 `function_ctx.visibility` ∈ {public, external, default} |
| 63 | ctx_call_in_loop | 全部 | 目标节点 `order.ext_call_in_loop` |
| 64–67 | env_kind {caller_identity, value, block_time_number, blockhash} | ENV_FLOW | env_source 节点的 `code` |
| 68 | unk_cfg | 用到支配、后支配或可达性的边 | 所在函数不在语义 CFG 覆盖范围内，或端点映射不到语义 CFG |
| 69 | unk_dfg | 数据边 | 任一端点 `dfg.status` = unknown |
| 70 | unk_order | 用到 order 字段的位所在的边 | 相关端点 `order.status` = unknown |
| 71 | unk_state | WRITES_STATE、READS_STATE | 相关端点 `state.status` = unknown |
| 72 | unk_guard | GUARDS、MOD_APPLY，以及所有以 guard_status 为 unknown 的语句为目标的边 | `guard_status` = unknown |

**未知值规则（r2）**：某一位依赖的事实为 unknown 时，该位写 0，同时对应的 unk 位写 1；不得把 unknown 当作 false 用在规则基线中。规则基线“没有 caller_identity GUARDS 入边的状态写语句”排除 guard_status 为 unknown 的语句，并报告被排除的数量。封存事实中 order 为 unknown 的语句约 5.6–9.6%，dfg 约 6.6–11.4%，guard 为 12 条（每任务）。

**端点检验（r2，EP4 执行，训练前完成）**：对每个核心候选位 b 和每种关系，计算“对每个源节点的全部出边取值恒定”的源节点比例与“对每个目标节点的全部入边取值恒定”的目标节点比例（只统计至少有 2 条该关系边的节点）。任一比例 ≥ 99% 的位判定为端点事实，从核心移入上下文组。阈值 99% 现在登记，不得根据结果调整。预计调用位（37–42）与守卫操作数位（49–54）会被移出；守卫种类位（43–48）不一定，因为同一个修饰器内的 `require` 对修饰器内语句是 require、对被修饰函数的语句是 modifier。未知位（68–72）不参加端点检验：每个未知位进入它所限定的位所在的组（限定的位分属两组时两组都含它）。

`recursive_method_call` 边的全部位为 0；其他每种边只填表中“适用边”列包含它的位，其余为 0。名称常量写成 `EDGE_FEATURE_NAMES`（长度 73）；核心位的索引列表 `core_indices` 由端点检验决定，不写成常量。不允许读取任何标识符拼写来计算任何一位。

### 3.4 E3：边感知层

`EdgeAwareHGTLayer(HGTLayerSharedProjection)`：文件头写明来源 `scripts/DFG/dfg_v2/hgt_layer.py` 与 `sco_models/model_hgt.py` 的 SHA256，并在导入时核对。

- 共享编码器（模型级一个，各层共用，每次前向每个关系计算一次）：`φ_e = W2·GELU(W1·a_e)`，a_e 为 float（uint8 转换），只取 `core_indices`（G4R-AC 时再加上下文组），隐层 32，输出 16，dropout 0.1。
- 每层每个关系 r：注意力 `s̃_e = s_e + u_rᵀ φ_e`（u_r：16×heads，每个关系键一行，不共享），在 `edge_softmax` 之前加；消息 `m_e = α̃_e · (v_src W_r^MSG + U_{f(r)} φ_e)`，U 按关系族共享（族：control、call、data、guard、structure），16 → heads×d_k。
- u_r、U 全部零初始化；W1、W2 用默认初始化，但在零初始化下不影响输出。
- 实现：把原来的 `fn.u_mul_e('v_%d', 't', 'm')` 换成 `apply_edges` 逐边算 `m`，再 `multi_update_all({etype: (fn.copy_e('m','m'), fn.sum('m','t'))}, cross_reducer='mean')`。共享投影、残差、dropout、LayerNorm 与父类逐行相同。
- 闸门：关闭边特征时必须走父类 forward（逐位相同）；开启且处于初始化状态时，输出与父类最大绝对差 ≤ 1e-6。

### 3.5 剖面

| 剖面 | 内容 |
|---|---|
| G3R | DFG v2 基线（merge），P2 下重跑 |
| G3R-T | G3R + typed 反向（+ cf_back，若启用） |
| G4R | G3R-T + MOD_APPLY、CALL_SITE、GUARDS |
| G4R-P | G4R，但三种新关系的边换成同类型、同数量、按文件与 (源类型, 目标类型) 保度数的随机边（种子固定） |
| G4R-A | G4R + E2 核心 + E3 |
| G4R-Aπ | G4R-A，属性向量在同一关系的边之间随机置换（种子固定） |
| G4R-AC | G4R-A + 节点上下文组（服务器阶段） |
| G3R-TA | G3R-T + E2 核心 + E3（只用已有关系，建在 typed 方向之上） |

### 3.6 实验与统计

| 阶段 | 地点 | 剖面 | 任务 | fit 数 |
|---|---|---|---|---:|
| E-A | 本机 | G3R、G3R-T、G4R、G4R-P | reentrancy_node、access_control_node | 80 |
| E-B | 本机 | G4R-A、G4R-Aπ、G3R-TA | 同上 | 60 |
| E-C0 | 服务器 | 数据移植（见 1.6） | 五类 | 0 |
| E-C | 服务器 | G3R、G3R-T、G4R、G4R-A、两种安慰剂；S0 与 S2 | 七类，节点与合约，5 个种子 | E-B 后定 |
| E-D | 服务器 | G4R−r、G4R-A−g、G4R-AC、门控与解释 | 七类 | E-C 后定 |

主假设（reentrancy_node，L-audit，best，BF1，N-anon-s；逐折配对，使用 `experiment/stats.py` 现有的双侧、zsplit Wilcoxon，与 8H 相同）：
- H1（新关系）：G4R − G3R-T 与 G4R − G4R-P 两项的均值差都为正。H1 的 p 值取两项检验 p 值中的较大者。
- H2（边属性）：G4R-A − G4R 与 G4R-A − G4R-Aπ 两项的均值差都为正。H2 的 p 值取两项中的较大者。
- 对 H1、H2 两个 p 值做 Holm 校正（α = 0.05）。
- G3R-T − G3R（方向修正）与 G3R-TA − G3R-T（只加属性）为次要对比，作为描述报告。

必报（描述性）：access_control_node 结果；两类任务的非 SolidiFI 正例逐节点表（TP/FP/FN）；scripts/node_sem/artifacts/summary_NS_v1/cases_attempt2/persistent_cases.json 中的持续漏报节点逐案例表（涉及修饰器、语句级调用或无保护状态写的案例单独标出）；规则基线（“没有任何 caller_identity GUARDS 入边的状态写语句”；“带 use_path_crosses_ext_call 的边指向状态写”）；每关系边数；峰值显存；每 fit 时间；E3 的 u_r、U 训练后范数。

---

## 4. Codex Prompts

### 4.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文（EdgeSem v1）

## 项目
在 MANDO-LLM 私有仓库上实现边语义增强（EdgeSem v1）：在 DFG v2（scripts/DFG/dfg_v2，含 benchmark_v2 执行器）之上，给 HCG 增加 typed 反向边、三种新关系（MOD_APPLY、CALL_SITE、GUARDS）、每条边的确定性属性向量和边感知 HGT 层，并用基准 v2 协议（P2 训练协议）评估。方案全文在 scripts/edge_sem/PROMPTS.md（第 1–3 节设计，第 4 节各 Prompt），有疑问先查它。

工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11。第一次开始前：
  git fetch origin edge-sem
  git checkout -b edge-sem origin/edge-sem
之后的提交都在 edge-sem 上。不要 push，除非用户明确要求。每个 Prompt 开始前先 git pull --ff-only origin edge-sem，读取最新的 PROMPTS.md。

环境（WSL）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
  export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12、PyTorch 1.8.1+cu111、DGL 0.6.1、tree_sitter 0.20.4、RTX 3050 4GiB。
代码必须兼容 Python 3.7：不要用 :=、list[str]/dict[str,int] 运行时注解、dict | dict、dataclass(slots=...)、match。

## 新代码位置
- 代码：scripts/edge_sem/（含 __init__.py）
- 测试：scripts/edge_sem/tests/（fixtures 在 scripts/edge_sem/tests/fixtures/）
- 产物：scripts/edge_sem/artifacts/<批次名>/，拒绝覆盖已存在目录。
- 进度：scripts/edge_sem/PROGRESS.md，每个 Prompt 结束追加一节（做了什么、文件清单、测试命令与结果、验收数字、遗留问题、与 PROMPTS.md 不一致之处及处理）。同时在 HANDOVER.md 与 docs/training_changes_2026-10-07.md 末尾追加简短记录。三份文件只追加，不改旧文。

## 禁止修改（以及禁止新增）
1. scripts/DFG/** 下的任何文件，也不得在其中新增文件（experiment/run.py::_code_refs() 枚举其中的 .py，8B/8H 的 seal 绑定了这份清单）。
2. scripts/node_sem/** 下的任何文件（NodeSem 已封存；只允许 import）。
3. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py（含已有本地修改）。
4. 所有已有产物、图、标签、折、特征 NPZ、初值、checkpoint、plan/seal。
复用时用 import、子类化或组合。必须改变冻结函数的行为时，复制到 scripts/edge_sem，文件头写明来源路径与原文件 SHA256，并加测试证明在旧输入上与原函数输出相同。禁止 monkeypatch 冻结模块，禁止重新绑定字节码。

## 不变量
- 原图（F3）的节点、节点顺序、节点属性、原有边完全不变。新边与边属性只在内存深拷贝或 scripts/edge_sem/artifacts 下的新图文件中出现；装配前后原图指纹（benchmark_v2.feature_view.graph_fingerprint）相同。
- 边的构建与属性计算只允许使用：AST 结构与内置名（msg、tx、block、this 等）、NodeSem StatementFacts、GuardAnalyzer 守卫记录、DFG v2 已封存的 L1–L3 证据与语义 CFG、编译器 pragma 版本。禁止读取任何标识符拼写来决定边或属性；禁止读取 type_label、node_info_vulnerabilities、method、label 文本、任何标签或预测文件。
- 名字不变性：同一文件用原名源码与 8G 匿名源码分别运行边构建器，得到的新边与属性向量必须逐位相同（EP5 闸门）。
- 每条新边都有出处记录：关系、源节点、目标节点、规则编号、AST 锚点字节范围（不写源码文本），以及解析失败的计数。
- 关闭全部 EdgeSem 开关时，模型与 dfg_v2.model.make_model(profile="G3R") 在规范关系键、端点张量、初值与前向输出上逐位相同（EP1 闸门）。
- 训练沿用基准 v2：8D 分组折、L-audit、seed=1、8H 训练配置；只有 P2 一处不同（跑满 50 轮，按 inner_val loss 选 best，不早停）。outer_test 只在训练结束后评分。
- 构造器种子与 8H 相同（constructor = 10000 + fold + 1000·[合约任务]，fit = constructor + 1000000）。派生模型的共享参数从同种子的新鲜 G3R 锚模型复制；新关系参数按 sha256(关系名) 派生的种子初始化；E3 的 u_r、U 为零。
- 使用与 8H 相同的 GPU 锁：scripts/DFG/experiments/artifacts/dfg_v2/.training.lock（experiment.run._Lock）。
- 文档一律 UTF-8 写入，用 Python 写文件；写完运行 python -B -m scripts.node_sem.doc_check --expect-cjk <文件>:<追加前字节数> ...（新文件不带字节数），不通过不得提交。

## 接入方式
照 benchmark_v2/runtime_model.py 中 G0P 的模式：先用 dfg_v2.model.make_model 构造同种子的新鲜 G3R 锚模型，再由 edge_sem 派生：深拷贝锚模型，用 edge_sem 的 materialize 得到新图数据，按新 etypes 重建层（EdgeAwareHGTLayer 或 HGTLayerSharedProjection），用 diagnostics8c/placebo.py::copy_common_layer_parameters 复制共享参数，并提供 edge_sem 自己的 validate_registration（剖面不属于 EdgeSem 时委托 dfg_v2.model.validate_registration）。执行器参照 scripts/node_sem/execution.py（它本身改写自 benchmark_v2/execution.py）。

## 关键可复用模块（先读再用）
- dfg_v2：__init__.py（关系名、PROFILES、AUX_NODE_TYPES）、model.py（make_model、_construct、_features、validate_registration）、model_input.py（edge_data、materialize、build_dgl）、hgt_layer.py（HGTLayerSharedProjection）、l1_cfg.py、env.py
- dfg_v2/benchmark_v2：runtime_model.py（G0P 派生先例）、execution.py、trainer.py、checkpoint.py、input_guard.py、audit_supervision.py、support.py、reporting.py、feature_view.py、spelling_features.py、prepare_spelling.py、anon_binding.py
- dfg_v2/diagnostics8c/placebo.py（make_placebo_data、copy_common_layer_parameters）
- dfg_v2/experiment：init.py（种子）、run.py（_Lock、_code_refs）、stats.py
- node_sem：facts.py（extract、extract_source、kind_of）、facts_io.py（load_context）、facts_ast.py（AstSemantics）、facts_guards.py（GuardAnalyzer）、facts_cfg.py（FileCFG）、facts_schema.py、execution.py（执行器先例）、carrier.py（row_key）
- scripts/DFG/projection.py::Projector、dfg_v2/projection_view.py、scripts/DFG/semantic_cfg.py

## 工作方式
- 每个 Prompt 只做它的范围。代码事实与本文不一致时以代码为准，在 PROGRESS.md 记录；如果影响方案（某个接入点不成立），停下来报告，不自行换方案。
- 每个 Prompt 结束时运行（CPU）：
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
  CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
  并核对：git status 中除 scripts/edge_sem/ 与三份记录文档外没有已跟踪文件改动；benchmark_v2.execution.load(8H plan) 只读通过；experiment.run._code_refs() 未变化。
  全部通过后 git commit，提交信息以 EPn 开头。
- 除了明确写着“训练”的步骤，不启动任何 HGT 训练。正式批次必须先有用户授权记录（scripts/edge_sem/artifacts/<批次>/authorization.json）。
- 失败就停，保留现场，不自动重试。
```

### 4.2 EP0：侦察（只读）

```text
# EP0：侦察（只读，不写算法代码）

产出 scripts/edge_sem/RECON.md 与 scripts/edge_sem/recon.json；只读脚本放 scripts/edge_sem/recon/*.py。每条结论附命令、路径、SHA 或计数。

## 1. 输入身份
- 8H plan/plan.seal 的 SHA；graphs_v2_r1/store.json 与 store.seal.json；reentrancy_node、access_control_node（以及两个合约任务，只作记录）的 F0/F3 图路径与 SHA；N-anon-s 特征 manifest/NPZ；分组折；label_view。
- 8H 的训练配置逐项列出（确认 schedule_epochs、maximum_training_epochs、patience、delta、max_lr、layer_impl、reducer）。
- 8H 节点任务 G3R 各折实际停止轮数与 best 轮数分布（用于 P2 成本估计）。

## 2. 基础边与方向
- 每个任务 F3 图的规范关系 (源类型, 边类型, 目标类型) 及边数（反射前）。
- 用 reflect_graph 反射后：每个关系的边数；其中“同类型两端合并”的关系与“反向键与已有正向键合并”的关系，各列出数量与边数。
- typed 模式下的关系总数与每关系边数分布（边数 < 20 的关系单列）。本地阶段不做稀疏共享，只报告。
- 每层 HGT 新增参数量（typed 相对 merge）。

## 3. 循环与支配
- 各任务 for/while/do 节点数；用 DFG v2 语义 CFG（scripts/DFG/semantic_cfg.py 或 dfg_v2/l1_cfg.py，哪个能映射到 HCG 节点就用哪个，说明理由）识别的回边数，以及它们在 HCG 中对应的 next_line 边数。按 3.1 规则给出 cf_back 是否启用。
- 支配树与后支配树能覆盖的函数比例；映射不到 HCG 的语句数。

## 4. 新关系的可行性（只统计，不写边）
- MOD_APPLY：函数头修饰器调用总数；解析成功、失败、经继承解析的数量（与 GuardAnalyzer.audit 对照）；修饰器定义节点能在图中找到的比例。
- CALL_SITE：语句中内部调用总数；能唯一解析到同文件定义节点的数量；无法解析的原因分类。
- GUARDS：每种守卫 kind 的记录数；_anchor 能映射到图节点的比例（分 kind 统计，修饰器守卫单列）；每条语句的守卫数分布。
- 预计每种新关系（含 REV_）的边数。

## 5. 属性来源核对
- 逐项核对 3.3 表中每个来源字段在 StatementFacts 中确实存在、取值范围与本文假设一致：dfg.uses/defs[].kind 的取值；dfg.to[].sink 的取值；SHAPES；syntax 的取值；external.return_handling；arith.ops；fn_summary 字段。
- DFG v2 L1 证据中是否有 strong/weak 更新标记（字段名、位置）。没有就写明，第 15 位将恒为 0。
- env_source 节点 code 的取值集合与每文件数量。
- 编译器 pragma：每个文件的版本约束，能否判定 < 0.8。
- 8G 匿名源码是否已经物化（路径），若没有，prepare_spelling.load_result / anon_binding.replace_spans 能否在内存中重建。

## 6. 接入点核实（CPU）
- 逐行引用 runtime_model.py::make_placebo 与其 validate_registration、checkpoint.py::validate_binding 中与 profile、etypes、layer 类型有关的检查；说明 EdgeSem 派生模型要通过 checkpoint 绑定需要哪些字段（例如 dfg_profile 取值）。
- 实验 A：对 reentrancy_node 某一折，构造 G3R 锚模型，深拷贝后用 reflect_graph 的结果原样重建图与层并复制共享参数，前向输出是否与锚模型逐位相同。
- 实验 B：在实验 A 的模型上，把关系换成 typed 模式（只用反射数据，不训练），能否构造并完成一次 forward/backward；gradient_audit（support.py）是否通过或需要什么输入。
- 实验 C：在 CPU 上估计 G4R 规模（按第 4 节预计边数加随机边）下一次前向的内存峰值；GPU 显存探针留到 EP7。

## 7. 结论
- 列出与本文第 1–3 节不一致之处；每一处说明是否影响方案。影响方案的，停下报告。
- 给出 cf_back 是否启用、第 15 位是否可用、GUARDS 映射率、MOD_APPLY 与 CALL_SITE 的解析率、8G 匿名源码能否经 ProjectionView + Projector 投影到与原名源码相同的图节点（逐文件统计），作为 EP1–EP5 的参数。
```

### 4.3 EP1：关系注册与 materialize（E0）

```text
# EP1：关系注册、typed 反向与等价闸门

## 1. scripts/edge_sem/__init__.py
- VERSION = "edgesem-v1"
- NEW_RELATIONS = ("MOD_APPLY", "CALL_SITE", "GUARDS")；REVERSE_PREFIX = "REV_"
- RELATION_FAMILY：给出每个基础边类型、DFG v2 关系、新关系所属的族（control、call、data、guard、structure）。recursive_method_call 属于 structure。
- PROFILES：G3R、G3R-T、G4R、G4R-P、G4R-A、G4R-Aπ（代码中写成 "G4R-Api"）、G4R-AC、G3R-TA，每个剖面声明：direction_mode（merge/typed）、cf_back（bool）、new_relations（集合）、edge_features（none/core/core_context）、placebo（none/relations/attributes）。
- 剖面校验：G4R 系列必须 typed；edge_features ≠ none 时必须使用 EdgeAwareHGTLayer。

## 2. scripts/edge_sem/materialize.py
materialize(data, profile) -> (symmetrical_data, rel_meta)
- data 来自 dfg_v2.model_input.edge_data(nx_graph)（保持原插入顺序）。
- DFG v2 关系（DATA_DEF_USE 等）与它们的 REV_* 按 dfg_v2.model_input.materialize 的规则处理（调用它处理这部分，不要重写）。
- 基础边：merge 模式调用 gu.reflect_graph；typed 模式对每个 (A, e, B) 生成正向键与 (B, "REV_"+e, A)，同键多次出现时按原迭代顺序拼接。
- 新关系：正向键与 REV_ 键，任何键与已有键冲突就报错。
- rel_meta：{canonical: {"base": 基础类型, "reverse": bool, "family": 族}}。
- 不实现稀疏关系共享（r2：本地阶段每个关系键一行参数）。

## 3. scripts/edge_sem/model.py（本步只做结构，不含 E3）
make_edge_model(task, graph_or_path, profile, device, fold, ...)：
- 用 dfg_v2.model.make_model(profile="G3R", layer_impl="shared_projection", reducer="mean", 8H 的其余配置) 构造锚模型，种子按 dfg_v2/experiment/init.py 的 8H 规则。
- 按 runtime_model.make_placebo 的模式派生：深拷贝，用 edge_sem.materialize 的结果建 DGL 图（节点特征 inp 从锚模型复制），重建 etypes_dict 与 edges[c].data["id"]，按新 etypes 重建 gcs（本步一律 HGTLayerSharedProjection）。
- 参数复制：不要直接用 copy_common_layer_parameters（它要求锚模型的全部关系键都在新模型中，typed 模式下被反射出的 (B, e, A) 键会消失而报错；它还把新关系行填 0/1）。写 edge_sem/init.py::copy_typed_layer_parameters(anchor_layer, new_layer, key_map)，文件头写明参考来源 diagnostics8c/placebo.py 与其 SHA256：
  * key_map 由 materialize 给出：每个新键 → 锚模型中承载这些边的键（typed 正向键 (A,e,B) → G3R 的 (A,e,B)；(B,REV_e,A) → 同类型两端时 G3R 的 (A,e,A)，不同类型时 G3R 的 (B,e,A)；DFG v2 关系 → 同名键；merge 模式 → 同名键）；没有来源的键（E1 及其 REV_）不在 key_map 中。
  * 非关系参数逐个复制，形状不同就报错；relation_att/msg/pri 按 key_map 逐行复制；无来源的行用 torch.Generator 以 int(sha256(规范键字符串)[:16], 16) 为种子，att、msg 做 xavier_uniform（与 HGTLayer 相同的 fan 计算），pri 置 1。不消耗全局 RNG。
  * 复制后断言：每个有来源的行与来源逐位相同；锚模型的全部非关系参数逐位相同。
- model.edge_profile = profile；model.dfg_profile 的取值按 EP0 第 6 节的结论设定，使 checkpoint 绑定可用。
- validate_registration(model, ...)：edge_profile 为 G3R 时委托 dfg_v2.model.validate_registration；否则复用其中与剖面无关的检查（复制时写明来源与 SHA），并用 edge_sem.materialize 重新计算期望的规范键与端点逐条比较。

## 4. 测试 scripts/edge_sem/tests/test_materialize.py、test_model_equivalence.py
- 小图：节点类型 X、Y；基础关系 (X,next_line,X)×3、(X,a,Y)×2、(Y,a,X)×1；DFG 关系 (X,DATA_DEF_USE,X)×1。merge 模式与 dfg_v2.model_input.materialize(…, "G3R") 的键和端点逐元素相同；typed 模式下每个 REV_ 关系的边恰好是正向边的反转，正向关系中没有混入反向边。
- 新关系与已有键冲突时报错。
- copy_typed_layer_parameters：用小图构造 merge 与 typed 两个层，检查 key_map 覆盖、逐行复制、无来源行的确定性（两次调用逐位相同、不同键不同）与不消耗全局 RNG（调用前后 torch.random.get_rng_state() 相同）。
- merge 模式派生模型经 copy_typed_layer_parameters 后与锚模型逐位相同（key_map 为恒等映射）。
- 闸门 1（真实任务 reentrancy_node，fold 0 与 fold 9，CPU）：make_edge_model(profile="G3R") 与 dfg_v2.model.make_model(profile="G3R") 的规范键、端点、全部参数张量逐位相同，eval 模式下一次前向逐位相同。
- G3R-T 模型能构造，typed 后关系数与 EP0 的统计一致，forward/backward 成功。

## 验收
测试通过；PROGRESS.md 记录 G3R-T 的关系数、参数量、构造耗时，以及边数 < 20 的关系清单。
```

### 4.4 EP2：F4 边构建器（MOD_APPLY、CALL_SITE）

```text
# EP2：F4 边构建器——MOD_APPLY 与 CALL_SITE

## 1. scripts/edge_sem/build_f4.py
build_task(task_id, out_dir) -> manifest
- 输入：node_sem.facts_io.load_context(task_id) 的 F3 图、源码与证据。只读。
- 对每个 source_file：用 node_sem.facts_ast.AstSemantics 与 ProjectionView/Projector 建立 “AST 节点身份 → 图节点” 映射（与 facts.py 相同的方法，可调用其内部函数；需要改行为就复制并写明来源 SHA）。
- MOD_APPLY：对每个 function_definition/constructor_definition 节点，取函数头的 modifier_invocation，按 GuardAnalyzer._modifiers 的解析规则（含继承、参数绑定检查）找到唯一的 modifier_definition，映射到图节点后建边。解析失败的按原因计数（unresolved / not_unique / not_in_graph）。
- CALL_SITE：对每个语句节点，枚举其 AST 子树中的 call_expression，用 AstSemantics 的调用解析找到唯一的同文件 function/modifier/constructor 定义；外部合约调用、低级调用（external.kinds 非空的成员调用）、库与接口调用、事件 emit 不建边，分类计数。同一语句到同一定义只建一条边。
- 输出：out_dir/f4_edges.jsonl，每行 {"relation", "src", "dst", "rule", "src_anchor": [start_byte, end_byte, type], "dst_anchor": [...], "file"}；out_dir/f4_audit.json（各类计数）；out_dir/manifest.json（输入 SHA、实现文件 SHA、行数、jsonl 的 SHA）。不写新的 gpickle；模型侧按 jsonl 在内存副本上加边。
- add_edges(nx_graph_copy, edges) -> nx_graph_copy：只在深拷贝上加边，edge_type 为关系名；加边前后原图指纹不变。

## 2. 测试 scripts/edge_sem/tests/test_build_f4_calls.py
fixtures（tests/fixtures/*.sol，自写小合约）：
- 带两个修饰器的函数（其中一个继承自父合约）→ 两条 MOD_APPLY；修饰器名拼写不存在 → 计入 unresolved，不建边。
- 语句 `x = helper(a);` 调用同文件 helper → 一条 CALL_SITE 到 helper 定义；`token.transfer(a, b)` 与 `msg.sender.call.value(v)("")` → 不建边，分别计入 external 与 low_level。
- 同一语句两次调用同一函数 → 一条边。
- 真实文件：reentrancy 数据中的 reentrancy_bonus、access_control 中的 rubixi 与 unprotected0（按 source_file 名在 F3 中查找；找不到就报告），人工核对后把期望边写成测试。

## 验收
两个节点任务全部文件运行完成；PROGRESS.md 记录每种关系的边数、解析率与失败原因分布，与 EP0 第 4 节的预计对照。
```

### 4.5 EP3：F4 边构建器（GUARDS）

```text
# EP3：GUARDS

## 1. build_f4.py 增加 GUARDS
- 对每个语句与条件节点，调用 node_sem.facts_guards.GuardAnalyzer(semantics).for_node(ast_node)，逐条取守卫记录的 _anchor（守卫条件的 AST 节点），映射到图节点（守卫条件所在的语句或 if/while 节点）。映射规则：先找 AST 身份完全相同的图节点；没有就找包含该 AST 节点的最小语句节点；都没有就丢弃并按 kind 计数。
- 建边：守卫节点 → 被保护语句节点，edge_type = GUARDS。修饰器守卫的源节点位于修饰器体内，目标是被修饰函数内的语句，不经过 MOD_APPLY。
- 同一 (守卫节点, 语句) 只保留一条边；边记录中保留该守卫的 kind、operand_classes、is_sender_guard（供 EP4 计算属性），以及 rule 编号。
- loop_cond 守卫也建边（覆盖拒绝服务与循环），kind 记为 loop_cond。
- 守卫节点自身不连自己。

## 2. 测试 scripts/edge_sem/tests/test_build_f4_guards.py
fixtures：
- require(msg.sender == owner); owner = n; → GUARDS(require 语句 → 赋值)，kind=require，operands 含 caller_identity。
- if (now > deadline) { x = 1; } → GUARDS(if → x=1)，kind=if_branch，operands 含 block_time。
- if (!ok) revert(); y = 2; → early_exit 守卫连到 y=2。
- 修饰器 onlyOwner 内 require(msg.sender == owner); _; 应用于函数 f → 修饰器内 require 语句 → f 内每条语句各一条 GUARDS，kind=modifier。
- 内部检查函数 _check() 中的 require 被调用 → kind=internal_check 的记录能映射时建边；映射不到时计数。
- require(a + b >= a) → operands 不含 caller_identity。
- for (i = 0; i < arr.length; i++) { arr[i].transfer(1); } → loop_cond 守卫连到循环体语句。

## 验收
两个节点任务全部完成；PROGRESS.md 记录每种 kind 的记录数、映射率（修饰器单列）、GUARDS 边数，以及每个原节点的入边 GUARDS 数分布。
```

### 4.6 EP4：E2 边属性

```text
# EP4：边属性（uint8[73]）与端点检验

## 1. scripts/edge_sem/attrs.py
- EDGE_FEATURE_NAMES（长度 73，顺序与 PROMPTS.md 3.3 表完全一致）；CORE_CANDIDATES（0–54 与 68–72）；CONTEXT（55–67）；GROUPS（名称 → 索引列表）；ONE_HOT_GROUPS（var_kind、value_shape、def_kind、write_shape、write_op 为单热：适用时恰好一个 1，不适用时全 0）。
- compute_attributes(context, f3_graph, f4_edges, facts) -> {edge_key: uint8[73]}
  - edge_key = f"{source_file}::{src}->{dst}::{edge_type}::{k}"，k 为同一对节点同一类型的多重边序号（按 nx 的 key 排序编号）。
  - facts 来自 node_sem.facts.extract(task_id)（原名视图）；守卫字段来自 EP3 的边记录。
  - 支配、后支配、可达性用 EP0 选定的语义 CFG，按函数缓存。
  - 每一位严格按 3.3 表的来源计算；表中写“若没有就恒为 0”的位按 EP0 结论处理。依赖的事实为 unknown 时按 3.3 的未知值规则写对应 unk 位。
  - 不读取任何标识符拼写。代码审查要求：attrs.py 中不得出现对节点 code/label 文本的字符串匹配；env_kind 只能比较保留环境表达式（与 dfg_v2/env.py 的 14 个键对应）。
- reverse 边不在这里计算；模型侧复制正向边的向量。
- explain_edge(vec) -> list[str]；validate_vector(vec, relation) 检查单热组合法、不适用组为 0。
- endpoint_test(attrs, f4_edges, f3_graph) -> {bit: {relation: (源恒定比例, 目标恒定比例, 节点数)}}，按 3.3 的端点检验规则（阈值 99%，只统计至少 2 条该关系边的节点）给出 core_indices。
- write_attributes(task_id, out_dir)：输出 attrs.npz（edge_keys 与 uint8 矩阵）、manifest.json（输入与实现 SHA，以及两个节点任务合并后的端点检验结果与 core_indices；两个任务的检验都在这一步完成，core_indices 取两任务都判定为非端点的位）、stats.json（每一位在每种关系上取 1 的比例，以及在正样本目标节点入边与负样本目标节点入边中的比例——只作描述，读取标签只允许在这个统计函数中，并且该函数的输出不得被任何特征代码 import）。

## 2. 测试 scripts/edge_sem/tests/test_attrs.py
- len(EDGE_FEATURE_NAMES) == 68；单热组校验对合法/非法向量判断正确；explain_edge 往返一致。
- 每个核心组至少一个 fixture 用例：
  * 重入样例 var acc = Acc[msg.sender]; if (acc.balance >= _am) { if (msg.sender.call.value(_am)()) { acc.balance -= _am; } }：从读取 acc.balance 的语句到 acc.balance -= _am 的数据边 use_path_crosses_ext_call=1；WRITES_STATE 边 write_op=decrease；指向 call 语句的数据边 call_low_level=1、call_sends_value=1、use_context=call。
  * 循环 i++ 到 i < n 的数据边 def_loop_carried=1。
  * unchecked { c = a * b; } 或 pragma ^0.4.24 下的 c = a * b：数据边 arith_op=multiplicative；ctx_unchecked_arith=1（上下文组）。
  * (bool ok, ) = a.call(d); 后续无条件使用：指向调用的边 call_return_checked=0；if (!a.send(x)) revert(); → 1。
  * require(msg.sender == owner) 的 GUARDS 边：guard_kind=require，guard_operands 含 caller_identity。
  * CALL_SITE 到写状态的 helper：call_callee_writes_state=1。
- 未知值：构造 dfg.status=unknown 的语句，相关位为 0 且 unk_dfg=1；guard_status=unknown 的语句作为目标时 unk_guard=1。
- 端点检验：构造一个位只依赖目标节点的小图，判定为端点；一个位随边变化的小图，判定为非端点。
- 名字无关性（快速版，正式闸门在 EP5）：把 fixture 中所有非保留标识符改名后重算，向量逐位相同。

## 验收
两个节点任务的 attrs.npz 生成完成；PROGRESS.md 贴 stats.json 的关键数字（每关系每组的非零比例；全零向量的边占比）。
```

### 4.7 EP5：闸门与边统计（只读）

```text
# EP5：名字不变性、可达性与边统计

## 1. 名字不变性闸门
- 对两个节点任务的每个 source_file：用 8G 匿名源码（EP0 第 5 节给出的来源）调用 node_sem.facts.extract_source 与 edge_sem 的构建器（GUARDS、MOD_APPLY、CALL_SITE、attrs），与原名结果比较。比较必须在图节点空间进行：新边集合按 (源图节点, 目标图节点, 关系) 比较，属性向量按同一键比较，逐位相同。不得比较 AST 字节锚点（anon_binding.replace_spans 改变标识符长度，字节偏移必然不同）。匿名源码投影不到同一图节点的文件按 EP0 的结论处理：列出并停下报告。
- 任何差异：列出文件、边、差异位，停下报告，不得继续 EP6。

## 2. 两跳可达
- scripts/node_sem/artifacts/summary_NS_v1/cases_attempt2/persistent_cases.json 中的持续漏报节点（重入与访问控制），在 G3R、G3R-T、G4R 三种图上（反射后）计算：从该节点出发两跳内能到达的“证据节点”（外部调用语句、状态写、守卫条件、修饰器定义）数量。输出逐案例表。
- 这是描述性检查，不改变方案；只在 G4R 相对 G3R 对任何案例都没有增加可达证据时，在 PROGRESS.md 标红。

## 3. 边统计
- 每任务：每种关系的边数、每节点平均入度（按节点类型）、反射后关系数；G4R-P 的随机边生成函数（保持文件内、(源类型, 目标类型) 与度数）及其统计与 G4R 的对照。
- G4R-Aπ 的置换函数（同一关系内置换，种子固定）。两个安慰剂函数写在 scripts/edge_sem/placebo.py，带测试：边数、类型分布、每节点度数保持不变；置换后每个关系内向量的多重集不变。

## 验收
闸门通过；PROGRESS.md 记录可达表与统计；安慰剂测试通过。
```

### 4.8 EP6：E3 边感知层

```text
# EP6：EdgeAwareHGTLayer

## 1. scripts/edge_sem/hgt_edge.py
- 导入时核对 scripts/DFG/dfg_v2/hgt_layer.py 与 sco_models/model_hgt.py 的 SHA256（写成常量），不一致就报错。
- class EdgeAttrEncoder(nn.Module)：__init__(in_dim, hidden=32, out_dim=16, dropout=0.1)；forward(a_uint8[E, in_dim]) -> [E, 16]。模型级一个实例。
- class EdgeAwareHGTLayer(HGTLayerSharedProjection)：
  - __init__ 先调用父类（参数分配顺序与 RNG 消耗与父类完全相同），之后才创建 u（[R, 16, heads]，零）与 U（ModuleDict 或参数，按族，[16, heads*d_k]，零），R 为关系数。
  - forward(G, h, psi=None)：psi 为 None 时直接 return super().forward(G, h)。否则复制父类 forward（写明来源行号），只做两处改动：(1) edge_softmax 之前 attn += (psi_r @ u[e_id])；(2) 消息改为逐边 m = attn * (v_src + (psi_r @ U[family]).view(-1, heads, d_k))，用 apply_edges 写入 edata，再 multi_update_all({etype: (fn.copy_e("m","m"), fn.sum("m","t"))}, cross_reducer="mean")。其余（共享投影、残差、dropout、LayerNorm）与父类逐行相同。
- model.py：G4R-A、G4R-Api、G4R-AC、G3R-TA 剖面用 EdgeAwareHGTLayer 重建 gcs（共享参数照 EP1 复制），图上写入 edges[c].data["ea"]（uint8，按 edge_key 对齐；REV_ 边复制正向边；无属性的关系全零）；前向时先算一次 psi 再传给每层。需要包一层 forward 时，按 runtime_model 的方式复制作者 forward 并写明来源 SHA。
- validate_registration 增加：ea 张量与 attrs.npz 逐行一致；层类型与剖面一致。

## 2. 测试 scripts/edge_sem/tests/test_hgt_edge.py
- 闸门 2a：同一输入，EdgeAwareHGTLayer(psi=None) 与 HGTLayerSharedProjection 输出逐位相同（参数从同一 state_dict 加载）。
- 闸门 2b：psi 非空、u 与 U 为零时，最大绝对差 ≤ 1e-6（CPU，float32）。
- u、U 非零时输出改变，且梯度能流到 u、U、EdgeAttrEncoder。
- 属性与端点对齐：构造每条边属性唯一编码的小图，经 typed 反向后，检查每条 REV_ 边的属性等于其正向边的属性。
- 真实任务 reentrancy_node fold 0：G4R-A 构造、validate_registration、一次 forward/backward（CPU）。

## 验收
测试通过；PROGRESS.md 记录 G4R-A 新增参数量与 CPU 前向时间。
```

### 4.9 EP7：执行器、P2 与 G3R 重跑（训练）

```text
# EP7：执行器、P2 协议与 G3R 基线（训练）

## 1. scripts/edge_sem/execution.py
参照 scripts/node_sem/execution.py 改写（文件头写明来源与 SHA）：plan/seal/authorization、construct（调用 edge_sem.model.make_edge_model）、binding（新增 edge_profile、f4 manifest SHA、attrs manifest SHA、core_indices、P2 标识）、fit_one、verify_one、controller。训练函数 benchmark_v2.trainer.fit 原样调用；P2 通过配置实现：patience = maximum_training_epochs + 1（StopMonitor 在 patience ≥ 1 时接受任意值，并保存每一个严格的新最小值，所以不会早停，best 仍按 inner_val loss 选择）；不得复制或修改 trainer。
- 节点特征：N-anon-s 的 S0（8H 匿名 token NPZ），装配方式与 8H 相同。
- 运行版本：只绑定 scripts/edge_sem 下训练路径上的模块清单（照 NS-P1b 的做法），只读核验已完成 fit 时比较封存记录，不比较当前代码。

## 2. P2 登记
在任何训练之前写 scripts/edge_sem/artifacts/protocol_p2/registration.json：P2 的定义、与 8H 配置的逐项差异、主假设 H1/H2、Holm 族、必报项、D1–D3 的状态。提交后才能开始训练。

## 3. 显存探针（GPU，需授权）
reentrancy_node 与 access_control_node 各一折：G3R、G3R-T、G4R、G4R-A 的峰值显存；超过 3.5 GiB 时停下报告，按 3.1 的共享规则或分块计算 psi 提出方案。

## 4. 用户确认（r2）
训练前必须存在 scripts/edge_sem/artifacts/protocol_p2/decisions.json，逐项记录 D1–D3 的用户决定（确认或改为何种方案）与日期。没有这份文件，或任何一项不是“确认”且没有对应的替代方案，就停下，不得训练。

## 5. 边参数试点（训练，单折，只看范数）
reentrancy_node 第 0 折训练一次 G4R-A（P2）。只报告每层 u、U 的 Frobenius 范数随 epoch 的变化与最终值，不读取、不报告任何 outer_test 或 inner_val 指标；该 fit 不进入任何比较。预先登记的规则：若全部 u、U 的最终范数 < 1e-3，停下报告；否则照常进行。

## 6. 训练
G3R × 2 个节点任务 × 10 折 = 20 fits（P2）。授权文件就绪后执行。完成后报告逐折 BF1、best 轮数分布，并与 8H 的 G3R 对照（只作描述）。

## 验收
20 个 fit 全部成功并只读核验通过；PROGRESS.md 记录显存、每 fit 时间与结果。
```

### 4.10 EP8：阶段 E-A（训练）

```text
# EP8：阶段 E-A（G3R-T、G4R、G4R-P；训练）

- 2 个节点任务 × 3 个剖面 × 10 折 = 60 fits，P2，授权后执行。G4R-P 的随机边种子 = 构造器种子。
- 分析脚本 scripts/edge_sem/analysis_ea.py：按 3.6 计算 H1（G4R − G3R 与 G4R − G4R-P，reentrancy_node），G3R-T − G3R 次要对比，access_control_node 描述性结果；逐折错误数与相对错误减少率；非 SolidiFI 正例逐节点表；持续漏报案例逐案例表；两条规则基线（只用 F4 边与 attrs，无学习）的 BF1。
- 输出 scripts/edge_sem/EP8_REPORT.md。Holm 校正时 H2 尚无结果，按登记的两项族在 EP9 统一校正；这里先报告未校正 p 值。

## 验收
60 个 fit 成功并核验；报告完成。不论结果如何，都不修改已登记的假设与剖面。
```

### 4.11 EP9：阶段 E-B 与冻结（训练）

```text
# EP9：阶段 E-B（G4R-A、G4R-Aπ、G3R-TA；训练）与方案冻结

- 2 个节点任务 × 3 个剖面 × 10 折 = 60 fits，P2，授权后执行。
- 分析：H2（G4R-A − G4R 与 G4R-A − G4R-Aπ，取较大 p 值），H1/H2 两项 Holm 校正；G3R-TA − G3R-T；训练后 u_r 与 U 的范数（按关系与族）；注意力偏置 u_rᵀφ_e 在正负样本目标节点入边上的分布（描述）。
- 输出 scripts/edge_sem/EP9_REPORT.md 与 scripts/edge_sem/EDGESEM_REPORT.md（汇总 E-A 与 E-B）。
- 冻结：写 scripts/edge_sem/artifacts/frozen_schema/schema.json，包含关系列表、EDGE_FEATURE_NAMES、core_indices、E3 超参数、P2 定义，以及所有实现文件的 SHA。服务器阶段（E-C0、E-C、E-D）只能使用这份冻结内容；任何改动都要新版本号与理由。

## 验收
60 个 fit 成功并核验；两份报告完成；冻结文件提交。
```
