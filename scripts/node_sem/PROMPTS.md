# MANDO-LLM 节点语义增强（NodeSem v1）：方案与 Codex 编码 Prompts

版本：r23（2026-11-08）。作者：Claude（方案与审查），实现：Codex。

**r23 相对 r22 的修改**：按用户要求完成 NS-P7（LLM 描述）的完整设计（第 5.10 节），并按当前状态更新第 4.7 节：提示由原名源码生成、在提示层统一改名为 a_k（与视图无关）；增加试点的预先登记通过标准、非 SolidiFI 分层抽样、教师向量的只读诊断。凡是我建议但尚未实施的事项，统一标注为【建议·未实施】，集中列在 NS-P7 末尾与第 4.12 节之后，需用户逐项决定。

**r22 相对 r21 的修改**：NS-P6c2 审查通过（第 5Q 节），不需要纠正。诊断阶段结束；下一步由用户在“NS-P7（LLM 描述）”与“针对 STATIC 的小批次”之间决定。

**r21 相对 r20 的修改**：NS-P6c 审查（第 5P 节）。新增 CPU 小修 **NS-P6c2**（第 5.9c2 节）：冗余探针改为只在各字段的适用节点上计算（原探针在全部节点上计算，把“识别节点种类”混进了 AUC），并为非 SolidiFI 信号探针加只含语句/条件节点的敏感性分析。NS-P7 继续暂缓。

**r20 相对 r19 的修改**：NS-P6（N-B）审查（第 5O 节）。新增只做评估、不训练的诊断 Prompt **NS-P6c**（第 5.9c 节）：更正 N-A 权重缺失的原因记录（用户主动删除），规定权重保留与 Git 体积规则，并用已有 N-B 检查点检验“门控无效”与“信息冗余”两种解释。NS-P7 在评估口径确定前暂缓。

**r19 相对 r18 的修改**：NS-P5A（N-A 240 次训练）审查通过（第 5N 节）。NS-P6 按 N-A 的结果补充执行细节与事后描述项（明确标为事后、只作描述）。

**r18 相对 r17 的修改**：NS-P5A 增加第 0b 节（不改变结果的耗时优化与执行顺序）与第 0c 节（与 Codex 会话、网络无关的后台运行、睡眠防护与中断恢复）。依据：8H 实测每个 fit 墙钟约 143 秒（训练约 102 秒）；NS-P4b 的阶段日志显示 NodeSem 在 reentrancy_contract/S4 上训练前的构造与校验约 90 秒、移到 GPU 与绑定约 27 秒、训练后验收约 18 秒；8H 第一次运行曾因 Windows 睡眠约 80 分钟在 71/170 处中断。

**r17 相对 r16 的修改**：NS-P5 审查通过（第 5M 节）。NS-P5A 补充：正式 worker 的绑定方式（执行修订记录，不改已封存 plan）、禁止沿用冒烟的 1 epoch 覆盖、本机批次与服务器批次的关系。

**r16 相对 r15 的修改**：NS-P4b 审查通过（第 5L 节）。按 EXPERIMENT_POLICY（原名为主）改写第 4.12 节的批次与预先登记、NS-P5、NS-P5A、NS-P6：S0 不再复用匿名 8H，改为新跑原名 S0o；N-A 为 {S0o,S1o,S2,S4}×{G0,G3R}=240 次；N-B 加入 S4m 名字对照；所有比较要求同一设备类型与相同 TF32 设置；SolidiFI/非 SolidiFI 分层为预先登记的描述项。

**r15 相对 r14 的修改**：NS-P4 审查（第 5K 节）。新增 **NS-P4b**（第 5.6b 节，NS-P5 之前完成）：修正我在 NS-P4 中设定的绝对 100 MiB 显存门槛（8H 的 S0 本身在同一任务上最低空闲只有 44–74 MiB），改为相对 8H 的门槛并补完 GPU 功能验收；模态 dropout 的种子加入节点类型。

**r14 相对 r13 的修改**：NS-P3b2 审查通过（第 5J 节），下一步为 NS-P4；NS-P4 第 3 节补充原名视图的 S0o/S1o 配置登记与核对（原名为主时的配对基线所需）。

**r13 相对 r12 的修改**：NS-P3b 审查（第 5I 节）。新增小范围纠正 Prompt **NS-P3b2**（第 5.5b2 节，NS-P4 之前完成）：把已批准但未编码的“一层检查运算”写入 STATIC，组级未知时保留已由确定证据得出的 true 位，CTX 中参数来源不再写成 unknown。NS-P4 的配置维度改为以载体为准，并登记 masked CTX 的对照配置。

**r12 相对 r11 的修改**：NS-P3a3 审查通过（第 5H 节），下一步为 NS-P3b；视图口径的建议见第 5H 节，待用户决定。

**r11 相对 r10 的修改**（NS-P3a2 审查后，见第 5G 节）：新增小范围纠正 Prompt **NS-P3a3**（第 5.5a3 节，NS-P3b 之前完成）：修正冻结语法误解析导致的合取型发送者守卫漏判、`throw` 被当成未解析状态名、汇总字段未知的三值逻辑与 K 组未知的作用目标，以及一处依赖 networkx 版本的写法。NS-P3b 按当前 EXPERIMENT_POLICY（原名视图）与 facts v1.1 的逐字段 unknown_fields 改写，并增加不含变量名的 CTX 对照。

**r10 相对 r9 的修改**（NS-P3a 审查后，见第 5F 节）：新增纠正性 Prompt **NS-P3a2**（第 5.5a2 节，NS-P3b 之前完成）：修正状态事实“未知”被整函数扩散的错误、修正守卫对“全部为发送者比较的析取”的处理，并补充名字无关性测试。NS-P3a 期间写入的 EXPERIMENT_POLICY.md（改为只用原名视图）与本文件的主终点设计冲突，见第 5F 节，等待用户确认。

**r9 相对 r8 的修改**（NS-P3 交付前的设计复查）：用 7 类漏洞的真实源码核对 M2/M3a 设计后发现，原设计主要围绕重入与访问控制，其余 5 类的核心模式无法表达。重写第 4.5、4.6 节与 NS-P3：
- M3a 改为通用设计（约 200 维）：新增调用目标/金额/数据类别、未被调用的 `.call.value(x)`、返回值在 require 与 if 中检查的区分、循环内外部调用、数组长度变化、哈希与 ecrecover、环境量的用途（算术、哈希、守卫、状态写、调用）、算术操作数的类型宽度与来源及 `unchecked` 块、授权变量（与名字无关）、状态变量声明节点（K 组）、函数汇总（L 组）、合约汇总（M 组）、自身条件（D3 组）、统一的未知位（N 组）；
- 守卫规则补充 5′（`if (msg.sender == owner) _;` 形式的 modifier）与 6（一层内部检查函数）；`||` 不计入有效相等组合；
- 明确原则：代码不得出现漏洞类别名；不加入编译器版本特征（与数据来源相关，是捷径），版本特有写法统一成同一事实；未知与否定分开；唯一的名字例外是“函数名与合约名仅大小写不同”；
- M2 新增 CALL、LOOP、COND、STATE_DECL、FN_SUMMARY、CONTRACT 字段与更多 TO 汇点类型；
- NS-P3 拆成 NS-P3a（事实与测试，含其余 5 类源码的冒烟）与 NS-P3b（M2 编码、M3a 向量、模态文件），中间交审查。

**r8 相对 r7 的修改**（NS-P2b 审查后，见第 5E 节）：NS-P2b 验收通过，进入 NS-P3。更正第 5D 节中关于残留名字原因的错误说法；共享上下文中的文档校验命令写成 doc_check 的实际用法（`--expect-cjk` 与 `路径:追加前字节数`）。

**r7 相对 r6 的修改**（NS-P2 审查后，见第 5D 节）：NS-P2 的数据与代码经复核成立；但 NS-P2 写入的四处文档（NS_P2_REPORT.md、PROGRESS.md 的 NS-P2 节、HANDOVER.md 的 NS-P2 节、training_changes §74）中所有中文都被写成了字面的 `?`，内容无法恢复。新增纠正性 Prompt **NS-P2b**（第 5.4b 节，NS-P3 之前完成）：重写这四处文档、加文档写入校验，并做一项编号影响的只读诊断。共享上下文增加文档编码不变量。M2 的匿名文本沿用 8G 的逐文件编号（第 4.5 节）。

**r6 相对 r5 的修改**（NS-P1b 审查后，见第 5C 节）：NS-P1b 验收通过，可以进入 NS-P2。更正 r5 中对 r4 初始尺度的表述（不能断言 r4 “无法学习”）；NS-P2 补充模态 manifest 必须满足的载体契约，以及“生产者代码改动后必须重新生成特征”的规则。

**r5 相对 r4 的修改**（NS-P1 审查后，见第 5B 节）：
- NS-P1 的 S0 等价、60 个初值摘要和 3 项用户批准的处理方式经复核成立；新增纠正性 Prompt **NS-P1b**（第 5.3b 节），必须在 NS-P2 之前完成：
  1. **运行版本绑定拆分**：`execution.load` 现在要求 `scripts/node_sem` 下全部 .py 与封存时逐字相同，只要 NS-P2 新增一个文件，NS-P1 的验收计划就无法再只读核验；以后 N-B 引用 N-A 结果、汇总报告时也会失败（8H 正是因此需要两次运行修订）。改为“启动新 fit 要求运行版本完全相同；只读核验已完成的 fit 不比较当前代码，改为核对封存时记录的运行版本与每个 fit 启动记录一致”，并把 NodeSem 运行版本限定为训练路径上的模块清单。
  2. **S1 初始尺度**：r2–r4 规定 EmbeddingBag 用 N(0, 0.02)，这是方案的错误。均值池化后每个节点向量的标准差约为 0.02/√L（L 为该节点 token 数），再经 Xavier 的 Linear(64,128) 后约为 10⁻³ 量级；而训练是全图训练，每个 epoch 只有 1 次 Adam 更新，50 轮里学习率从 0.0002 起步。S1 会在前若干轮几乎没有输入信号，在早停（patience 7）下对 S1−S0 比较不公平。改为 EmbeddingBag 默认初始化 N(0,1)（第 0 行置 0），池化后接一个共享的 LayerNorm(64)。这一决定在任何 S1 训练之前做出，不依赖任何结果。
- 特征扰动验收的重点移到特征生产者（NS-P2/P3/P7）：载体只复制预先算好的向量，载体上的扰动测试证明力有限（第 4.2 节）。
- G0 与 G3R 共用同一份特征 manifest（以 F3 节点为全集，G0 只取原节点），在 NS-P2 中实现（第 4.2 节）。

**r4 相对 r3 的修改**（NS-P0 审查后；NS-P0 验收通过，见第 5A 节）：
- 采纳 NS-P0 提出的三个设计问题，并给出决定（第 4.2、4.5、4.6 节，NS-P3）：
  - NS-Q1：`label` 是生成器的结构性 DOT 标签（代码文本 + AST 锚点），不是漏洞标签。只允许冻结 Projector 用它做 AST 身份对齐，禁止进入任何特征文本；
  - NS-Q2：变量名只从已封存的 F3 L1 证据（Symbol.name、Symbol.kind）和 L2 边的 state_vars 读取，再经 8G 双射映射；禁止使用 Symbol.id、跨度、文件路径；
  - NS-Q3：守卫改为 AST 词法规则（require/assert 前置、if 分支包含、提前退出的 if、modifier 前缀），带极性；不再用 if/while 条件支配推断守卫。CFG 只用于顺序与可达性，不支持的函数记为 unknown。
- 修正方案自身的三处错误：
  - S1 的嵌入改为全模型共享的一个 `EmbeddingBag(V, 64, mode="mean")`。r3 的“每种节点类型一个 Embedding(V,128)”有 17×410 万 ≈ 7000 万参数，掩码平均还要展开 N×512×128 的中间张量，本机放不下；
  - 层数回退必须写成 `cfg.layers if spec.layers is None else spec.layers`（r3 中的 `spec.layers or cfg.layers` 会把 0 层变成 2 层）；
  - 8H 运行版本核对改为通过 `benchmark_v2.execution.load` 的生效修订链（runtime_resume_v2），而不是与原 plan 的 runtime 字面相等。
- 去掉 HCG 自身 CFG 边作后备（它有跨函数的边：88/1/147/67）。
- NS-P1 开头补做 60 个初值的 tensor digest 独立重算（NS-P0 因审批限制没做）；需要用户在 Codex 中明确批准对 SHA 已核对的本地文件使用 torch.load。
- NS-P4 增加一次 GPU 显存探针（需授权），因为 8H 中重入合约 G3R 的整卡最小空闲只有 44 MiB。

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
 ├─ M3a 静态行为画像（AST 后端，以后可加 IR 后端）→ b_static（约 200）
 └─ M3b 函数级 LLM 描述 → 句向量 t_sem（384，教师，只在训练期使用）
       M3c 按折训练的学生 MLP([e_ctx; b_static]) → s_sem（384）
 → 拼接为载体向量 x_v = [存在位 | 各模态]，写进内存图副本的 token 属性
 → make_model 原样构造 → 只把 adapt_ws 换成 NodeSemAdapter → 原 HGT（G0 或 G3R）→ 节点/合约分类
```

### 4.2 通用规则

- **允许读取的节点属性**：`code`、`node_type`、`source_file`、`node_source_code_lines`（只用于对齐，不作为特征），以及图的边和边属性。
  - `label` 是作者生成器的结构性 DOT 标签（节点代码文本 + `-{AST id}-{类型}-{首行}-{末行}` 锚点），不是漏洞标签（漏洞标签是 `node_info_vulnerabilities`）。**只允许冻结的 `Projector`/`node_code_view` 读取它做 AST 身份对齐**；NodeSem 自己的代码不得读取它，它的任何部分（包括锚点中的绝对行号）都不得进入特征。
  - 禁止读取 `type_label`、`node_info_vulnerabilities`、`method`、任何标签或预测文件。
  - **扰动验收**（每个产生特征的模块都要有）：(a) 修改 `node_info_vulnerabilities`、`type_label`、`method` → 输出逐位不变；(b) 只替换 `label` 中锚点之前的文本 → 输出逐位不变；(c) 破坏 `label` 锚点 → 明确报错，不得静默产出。
  - **扰动验收要落在特征生产者上**（r5）：载体与 8G `assemble` 用整图指纹做完整性校验，扰动后会直接拒绝，这是正确的生产行为；NS-P1 在载体上用“临时重绑指纹”的测试只能证明载体不读这些属性。真正可能泄漏的是生产者（NS-P2 的 text_view、NS-P3 的 facts/ctx_fields/static_profile、NS-P7 的 llm_inputs）。它们的扰动测试必须是：对图的深拷贝施加 (a)(b) 扰动，直接调用生产函数（不经过载体），比较输出的行内容与数组逐位相同；manifest 中记录的输入图指纹允许不同。
- **行集合**（r5）：特征生产者以 F3 图的节点为全集输出 manifest（原节点 + env_source），manifest 的 `profiles` 同时登记 F0（G0）与 F3（G0 之外的剖面）的图指纹。载体用于 G0 时只取原节点行，并核对被略去的行恰好是辅助节点；用于 G3R 时取全部行。DFG 不变量保证原节点在 F0 与 F3 中属性相同，NS-P2 要用测试确认这一点。
  - 用白名单实现，并写扰动测试：修改这些禁止属性后，特征必须逐位不变。
- **主视图文本**：节点文本来自 8G 的 `node_code_view`，源码来自 8G 的改名结果。
  - **变量名的来源（NS-Q2 决定）**：`DATA_DEF_USE` 边本身不带变量名，只有 `ddg_fact_indices`，它指向已封存的 F3 存储中 `audit.layers.L1.evidence`；每条证据的 `symbol` 是一个 Symbol（`name`、`kind`、`type_name`、`function`、`declaration` 跨度、`id`）。L2 边带 `state_vars`（原名）。L3 边的 `spellings` 是保留的环境表达式。
    - 只允许使用 Symbol 的 `name` 和 `kind`，以及由 `type_name` 归类得到的形状类别（mapping、array、address、uint/int、bool、bytes/string、struct/contract、other）；**禁止使用 `id`、`function`、`declaration`、任何跨度、文件路径或原始 `type_name` 文本**。
    - 名字在主视图中按该文件的 8G 双射（`prepare_spelling.load_result(row)["mapping"]`）逐个标识符映射（成员链 `a.b` 按点拆开，保留名不变）。遇到既不是保留名、也不在双射中的标识符，直接报错，不得原样输出。
    - 证据文件按 store 中的引用核对 SHA，并写进每个模态的 manifest。
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
- **全模型共享一个** `nn.EmbeddingBag(V, 64, mode="mean")`，注册在模型上（`model.nodesem_shared["token_bag"]`），只占约 205 万参数；池化后接一个同样共享的 `nn.LayerNorm(64)`（`model.nodesem_shared["token_norm"]`，只作用于非空行，空行保持 0）；每种节点类型的适配器只持有它们的未注册引用，再接自己的 `Linear(64, 128)`。
  - 初始化（r5）：EmbeddingBag 用 N(0, 1)（PyTorch 默认，第 0 行置 0），LayerNorm 用 1/0。r2–r4 的 N(0, 0.02) 会使输入信号在训练初期接近 0（见 r5 说明）。
  - 不得为每种节点类型各建一个 `Embedding(V,128)`（约 7000 万参数），也不得先展开 N×512×d 的张量再做掩码平均（重入合约约 1.8 万节点时，这一中间张量就超过 1 GB）。
  - 前向：从 `inp` 的 token 列取出每行的非零 ID（ID 0 是填充，右侧连续），拼成一维 `input` 加 `offsets` 交给 EmbeddingBag。空行得到零向量。每次前向都从 `inp` 现算，使 FitInputGuard 对 `inp` 的保护也覆盖这一路输入。
  - CUDA 上 EmbeddingBag 的反向使用原子加，不保证逐位确定，这一点与 8H 的散射累加相同，写进 manifest。
- V 从冻结 tokenizer 资产的词表大小读取并核对，不写死。
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

- 截取通过 AST 身份完成，文本取自对应视图 ProjectionView 的 compat 文本（作者预处理后的版本，没有注释）；不得从带注释的原始源码切片。失败时回退为完整文本，并按类型计数。
- 统一做空白规范化：连续空白合并为一个空格。只在特征文本上做，不改源码。
- **编码器**：
  - 主编码器：`Salesforce/codet5p-110m-embedding`（256 维）；
  - 备选：`microsoft/unixcoder-base`（768 维，均值池化），以后作为对照；
  - 冻结，fp16 推理，最大长度 128，相同文本只编码一次，输出 float32。
  - 权重由用户下载，Codex 不得联网。

### 4.5 M2：DFG 上下文（结构化字段，在 nodesem 中按优先级截断）

mando 侧为每个节点输出一个 JSON 对象（字段固定，缺失写 `"-"`，无法判断写 `"unknown"`），nodesem 侧再拼成文本，并用编码器自己的 tokenizer 按优先级截断。字段内容全部来自 StatementFacts（NS-P3），不读取标签。例（语句节点）：

```
[STMT] v12 . v3 -= v9 ;
[FUNC] function v4 ( uint v9 ) public payable | guards:modifier
[DEF] v12.v3:state
[USE] v12:local@-1 | v9:param
[FROM] @-1: var v12 = v2 [ msg.sender ] ;
[TO] -
[STATE_R] -
[STATE_W] v3:mapping
[ENV] -
[CALL] -
[LOOP] -
[PRE_EXT_CALL] @-2: msg.sender.call.value ( v9 ) ( )
[GUARD] require + sender==state @-3 (+1)
```

**相对距离** `@±k`：同一函数（或 modifier）内，按 AST 先序排列的 HCG 语句节点（含条件节点，不含 END 占位与函数节点本身）中相隔的个数。不写绝对行号。

| 字段 | 适用节点 | 内容 | 来源 |
|---|---|---|---|
| `STMT` | 全部 | M1 的截取文本 | 节点 |
| `FUNC` | 函数内节点 | 所在函数签名（M1 规则）+ 该函数的守卫方式摘要 | AST 函数归属 + 守卫规则 |
| `DEF`、`USE` | 语句 | 变量及类别（state、local、param、env）；局部变量和参数带上其来源语句的相对距离；函数不受 L1 支持时写 `unknown` | `DATA_DEF_USE` → `ddg_fact_indices` → 封存的 L1 证据（Symbol.name/kind，主视图经 8G 双射映射）+ L2 `state_vars` + L3 环境键 |
| `FROM` | 语句 | 来源语句，最多 2 条（相对距离 + STMT 文本） | `DATA_DEF_USE` 入边 |
| `TO` | 语句 | 去向，最多 2 条，按汇点类型标注：`call_target`、`call_value`、`call_arg`、`guard`、`state_write`、`arith`、`hash_input`、`array_index`、`loop_bound`、`return`、`other` | `DATA_DEF_USE` 出边 + 目标节点中该变量所处的 AST 角色 |
| `STATE_R`、`STATE_W` | 语句 | 读写的状态变量及形状（mapping、array、scalar）；写的是“授权变量”时加 `:auth` | `READS_STATE`、`WRITES_STATE` + 合约级授权变量集合（第 4.6 节 B 组） |
| `ENV` | 语句 | 环境键及用途（arith、hash、guard、state_write、call） | `ENV_FLOW` + AST 角色 |
| `CALL` | 含外部调用的语句 | 调用类型；目标类别；金额类别；数据类别；返回值处理 | 第 4.6 节 A、F 组 |
| `LOOP` | 循环内语句 | 循环边界类别；是否在循环体内发生外部调用 | 第 4.6 节 H 组 |
| `PRE_EXT_CALL` | 语句 | 同函数内、控制流上能到达本语句的最近外部调用（不含自身）；函数 CFG 不受支持时写 `unknown` | 函数内语义 CFG 反向 BFS |
| `GUARD` | 语句 | 最近守卫：类型、极性、有效比较组合、相对距离；另外的适用守卫只给个数 | 守卫规则（第 4.6 节） |
| `COND` | require/assert/if/while/for 节点 | 本节点自身条件的操作数类别与有效比较组合；是否为提前退出的 if | 同上（对自身条件求值） |
| `STATE_DECL` | 状态变量声明节点 | 形状、可见性、是否常量、是否有初值、是否授权变量、读取它的函数数、写入它的函数数（0/1/多）、是否只在构造函数中写、未受发送者守卫保护的写入函数数 | L2 证据 + 守卫规则 |
| `FN_SUMMARY` | 函数/构造函数/modifier/fallback 节点 | 第 4.6 节 L 组的摘要（外部调用、写状态、发送者守卫方式、写授权变量、selfdestruct、delegatecall、循环、循环内外部调用、使用时间戳、使用 tx.origin） | 函数内事实的汇总 |
| `CONTRACT` | 合约/库/接口声明节点 | 种类、有无显式构造函数、有无 payable fallback/receive、授权变量个数 | 合约内事实的汇总 |

辅助节点（env_source）与 `end_if`、`end_loop`：只有 `STMT`。

**匿名编号**（r7 决定）：主视图沿用 8G 的逐文件随机编号（vN），不在节点或上下文文本内部重新编号。理由：S0/S1 与全部 DFG 结果都用这套编号，改用局部规范编号会把“编号方式”与“预训练知识”混在 S2−S0 的比较里；局部规范编号还会让不同文件中相同的 SolidiFI 注入语句变成完全相同的字符串，增加模板记忆。NS-P2b 已量化其影响（同一原句变体的平均余弦 0.90–0.92，不同原句约 0.60–0.64），不改变本决定。LLM 输入（NS-P7）按函数内首次出现重新编号是为了缓存与提示稳定，属于另一场景。

**截断顺序**（按编码器 tokenizer 计数，上限 256；逐级执行，每级后重新计数）：
1. `TO`、`FROM` 各只留 1 条；
2. `FN_SUMMARY`、`CONTRACT`、`STATE_DECL` 只留前 4 项；
3. `GUARD` 只留类型与比较组合，`COND` 只留比较组合；
4. `PRE_EXT_CALL` 只留相对距离；`CALL` 只留类型与目标类别；
5. 每类变量最多 3 个；
6. `FUNC` 只留可见性与守卫摘要；
7. 最后才截断 `STMT`。

`STMT`、`DEF`、`USE` 的字段标签永远保留。记录每个节点的截断级别。

### 4.6 M3a：静态行为画像（约 200 维，精确维度以 behavior_schema.json 为准）

**设计原则（r9，对全部 7 类漏洞通用）：**
1. **通用语义，不按类别设计**：每个字段都是 Solidity 语句或声明的一般性质（调用、状态、守卫、环境量、算术、循环、函数与合约结构），代码与 schema 中不得出现任何漏洞类别名，也不得按类别分支。字段与 7 类漏洞的对应关系只写在 `behavior_coverage.md`（供论文与审查，代码不读取）。
2. **与名字无关**：除一个明确列出的例外（I 组的“函数名与合约名仅大小写不同”），字段不依赖任何拼写；两个视图的 M3a 必须逐位相同。
3. **与版本无关**：不加入 pragma 版本、编译器区间等文件级特征（它们与 SolidiFI/非 SolidiFI 来源高度相关，是捷径）。版本特有的写法统一成同一事实：`throw`/`revert()`/`require(false)` → 退出语句；`sha3`/`keccak256` → 哈希；`suicide`/`selfdestruct` → 自毁；`now`/`block.timestamp`、`address(this).balance`/`this.balance` → 同一环境键（沿用 L3 的合并规则）；`.value(x)`/`{value: x}` → 附带金额；`callcode`/`delegatecall` → 委托调用；`constant` 函数/`view`/`pure` → 只读函数。
4. **未知与否定分开**：凡依赖 L1 支持、CFG 支持、modifier 解析或投影的事实，不能确定时置 N 组对应的“未知”位，不得写成 0。
5. **按节点种类适用**：语句类节点（expression_statement、函数内 new_variable、return、continue_statement、if/while/for 条件节点）使用 A–J 组；状态变量声明节点使用 K 组（以及 E、J 中适用的位）；函数/构造函数/modifier/fallback 节点使用 I、L 组；合约/库/接口声明节点使用 M 组；env_source 只置 E 组；end_if/end_loop 只置各独热组的默认值。不适用的组全为 0，独热组置“不适用”位。

| 组 | 字段（编码） | 约维度 |
|---|---|---|
| A 外部交互 | 低层 call；delegatecall/callcode；staticcall；send；transfer；成员调用（目标为外部合约，类型未知）；`new` 创建合约；selfdestruct/suicide；`.call.value(x)` 形成但未被调用（多热） | 9 |
| A1 附带金额 | 是/否 | 1 |
| A2 调用目标类别 | msg.sender；tx.origin；参数；状态变量；局部变量；字面量/常量地址；this；其他表达式（多热，只对外部调用） | 8 |
| A3 金额类别 | 无；字面量；参数；状态变量；msg.value；this.balance；局部变量；算术表达式（独热，取主来源） | 8 |
| A4 调用数据类别 | 无；msg.data；参数；其他（独热） | 4 |
| B 状态访问 | 写（0/1/多，独热）；写 mapping/数组元素；写标量；读（0/1/多，独热）；读 mapping/数组元素；写授权变量；读授权变量；数组长度变化（push/pop/length 赋值/delete 整个数组） | 12 |
| C 顺序 | 可从同函数外部调用到达；被外部调用支配；本语句写状态且之后可到达外部调用；本语句是外部调用且之后可到达写状态；外部调用位于循环体内 | 5 |
| D 守卫方式（全部适用守卫） | 无守卫；require/assert 前置；处于 if 分支内；提前退出的 if；循环条件；modifier 守卫；内部检查函数（规则 6）；其中至少一个是发送者守卫（操作数含 msg.sender 或 tx.origin 的有效相等比较） | 8 |
| D1 守卫操作数（并集） | msg.sender；tx.origin；状态变量；参数；局部变量；字面量；时间戳/区块号；区块哈希/难度等其他区块量；msg.value；余额（this.balance 或 x.balance）；外部调用结果；哈希结果 | 12 |
| D2 有效相等比较组合（并集，按极性换算） | 发送者类 env 对状态变量；发送者类 env 对参数；发送者类 env 对字面量；状态变量对参数；哈希结果对状态变量/字面量；时间戳类 env 对状态变量/参数 | 6 |
| D3 自身条件（只对 require/assert/if/while/for 节点） | 是守卫节点；自身操作数类别（同 D1 的 12 类）；自身有效相等组合（同 D2 的 6 类）；是提前退出的 if | 20 |
| E 环境量 | msg.sender；msg.value；msg.data/msg.sig；tx.origin；tx.gasprice；block.timestamp；block.number；block.difficulty/coinbase/gaslimit；blockhash；gasleft；this.balance（按 L3 的 14 个键合并） | 11 |
| E1 环境量用途 | 用于算术；用于哈希输入；用于守卫条件；流向状态写；流向调用目标或金额 | 5 |
| F 调用返回值（独热，只对外部调用；其余为“不适用”） | 不适用；在 require/assert 中检查；在 if 条件中检查；赋值后在后续条件中检查；赋值但未检查；被忽略 | 6 |
| G 算术 | +；−；×；÷；%；**；作用于状态变量；操作数含小于 256 位的整数类型；操作数来自参数；操作数含环境量；结果流向状态写/守卫/调用金额；位于 `unchecked {}` 块内 | 12 |
| H 循环 | 不在循环内；常量边界；状态变量或数组长度边界；参数或局部变量边界（独热） | 4 |
| I 函数上下文（语句与函数节点） | 可见性 public/external/internal/private（独热）；payable；只读函数；是构造函数（constructor 关键字或与合约名完全相同的旧式名）；是 fallback/receive；应用了 modifier；函数名与所在合约名仅大小写不同（例外项，见下） | 10 |
| J 语法袋 | `=`；`+=`；`-=`；其他复合赋值；delete；emit；三元；下标访问；成员访问深度 ≥2；字面量；哈希内建（keccak256/sha3/sha256/ripemd160）；ecrecover；abi.encode 系列；退出语句（throw/revert/require(false)）；return；内联 assembly | 16 |
| K 状态变量声明 | 形状（mapping、数组、address、整数、bool、bytes/string、struct/合约类型、其他，独热）；public；constant/immutable；有初值；是授权变量；写入函数数（0/1/多，独热）；只在构造函数中写；存在未受发送者守卫保护的写入函数；在守卫条件中被读；被用作调用金额或目标 | 19 |
| L 函数汇总（函数/构造函数/modifier/fallback 节点） | 含外部调用；写状态；有发送者守卫（任一规则）；写授权变量；含 selfdestruct；含 delegatecall；含循环；循环内有外部调用；使用时间戳；使用 tx.origin；写状态后可到达外部调用；外部调用后可到达写状态 | 12 |
| M 合约声明 | 种类 contract/library/interface（独热）；有显式构造函数；有 payable fallback/receive；含 selfdestruct；有授权变量 | 7 |
| N 未知位 | 定义—使用未知（函数不受 L1 支持）；顺序未知（函数 CFG 不受支持）；守卫未知（modifier 无法解析或没有 `_;`）；状态绑定未知（L2 未解析）；投影缺失 | 5 |

**定义：**
- **授权变量**（与名字无关）：在同一合约及其同文件基类中，出现在任一发送者守卫（规则 1、3、5、6 中，与 msg.sender 或 tx.origin 做有效相等比较）里的状态变量。先算完所有守卫，再算授权变量，再回填 B、K、L、M 组。
- **外部调用**：只计入真正被调用的表达式。`x.call.value(v)` 后面没有调用括号时不发生调用，记为 A 组最后一位，不计入其他外部调用位、C 组与 F 组。
- **成员调用**：`x.f(...)` 中，x 不是 this、super、msg、block、tx、abi，也不能解析为本文件中声明的库或本合约（及其同文件基类）的成员时，记为对外部合约的调用。能解析为本文件库函数的调用不算外部调用。
- **金额主来源**（A3）：`value` 参数或 `send/transfer` 参数表达式中，按 字面量 < 参数 < 局部 < 状态 < msg.value < this.balance 的顺序取最后出现的类别；是算术表达式时记“算术表达式”。

**守卫规则**（NS-Q3 决定，r9 补充规则 5′ 与规则 6；纯 AST 词法，不依赖 CFG 覆盖）。对语句节点 S（其 AST 语句为 s，所在函数为 f），适用守卫是以下各项的集合：
1. **require/assert 前置**：表达式语句 R 是对内置 `require`/`assert` 的调用（同一文件中没有声明同名函数，且不是成员调用），并且 R 是 s 的某个外围块（从 s 所在块一直到 f 的函数体）中位于 s 之前的语句。极性 +。
2. **处于 if 分支内**：s 位于某个 if C 的 consequence 内（极性 +）或 alternative 内（极性 −），C 在 f 内。
3. **提前退出的 if**：if C 没有 else，consequence 是单条退出语句（throw、revert(...)、return、require(false)），或以其中之一结尾的块；并且 C 是 s 的某个外围块中位于 s 之前的语句。极性 −。
4. **循环条件**：s 位于 while/for 的 body 内，极性 +，类型 loop_cond（只计入 D 组，不计入 D1/D2）。
5. **modifier 前缀守卫**：f 应用的 modifier 能解析到定义（同文件，经 ClosedScopeJ 处理继承），并且在其函数体中第一个 `_;` 之前，存在满足规则 1 或 3 的守卫。极性按规则换算。
5′. **modifier 条件占位**：在 modifier 体内，`_;` 位于某个 if C 的 consequence 内（如 `if (msg.sender == owner) _;`），C 对 f 的函数体是守卫，极性 +；位于 alternative 内则极性 −。
6. **内部检查函数**（只追一层）：s 的某个外围块中、位于 s 之前，有一条表达式语句只调用一个能按拼写解析到同文件（含基类）内部或私有函数 g 的调用，并且 g 的函数体在顶层（不进入分支）含有满足规则 1 或 3 的守卫；g 中的这些守卫对 s 适用，类型 internal_check。不追第二层，不追外部合约。
- 规则 5、5′ 中 modifier 不能解析，或者体内找不到 `_;` 时，记 N 组“守卫未知”，不得记为无守卫。规则 6 中调用名不能解析时不记守卫，也不记未知（否则任何未解析调用都会使守卫变成未知）。
- **有效比较**：守卫条件中的 `==`/`!=`（包括 `!(a == b)`、`a != b` 嵌在 `!` 中）按极性换算成有效的相等或不等，D2/D3 只记录有效相等两侧的类别组合。例如 `if (msg.sender != owner) throw;` 在规则 3 下得到有效 `msg.sender == owner`，组合为发送者类 env 对状态变量。`&&` 连接的各子条件分别求值；`||` 连接的子条件不计入有效相等组合（任一成立即可通过）。
- **最近守卫**（M2 的 GUARD 字段）：按 AST 距离取最近的一个（最内层分支、最近的前置语句），modifier 与内部检查最后；D、D1、D2 取所有适用守卫的并集。
- 不使用 if/while 条件的 CFG 支配关系推断守卫：if 结束之后的语句同样被条件节点支配，但并不受它保护。

**名字相关的唯一例外**：I 组“函数名与所在合约名仅大小写不同”（例如合约 `Wallet` 中的函数 `wallet`，这是错误构造函数名漏洞的本质特征）。该位在两个视图中都用原始拼写计算（主视图经 8G 双射还原），只输出一个布尔值。8G 的改名是按拼写的双射，`Wallet` 与 `wallet` 会得到不同的 vN，主视图中无法从匿名名得出这一关系，所以必须用原拼写；它不携带名字内容，也不是 SolidiFI 的注入标记。behavior_coverage.md 与报告中要明确写出这一例外。

- **两个视图必须逐位相同**：除上述例外外，M3a 不依赖任何保留名以外的具体名字；名字相等关系（modifier 解析、内部函数解析、旧式构造函数）在文件内双射下保持。
- **后端接口**：`FactBackend.extract(file_ctx) → {row_key: StatementFacts}`，现在只实现 `AstBackend`；以后的 IR 后端输出同一 schema。

### 4.7 M3b：LLM 行为描述（只描述，不下判断）

- **单位**：每个函数（含 modifier、构造函数、fallback）调用一次。
- **输入**：
  - 原名源码（r23：按 EXPERIMENT_POLICY 取原名视图；提示中全部非保留标识符随后改为 a_k，因此提示内容与视图无关）；在 AST 上把 comment 节点的字节范围替换成等长空白（NS-P0 已验证这样做 ERROR/MISSING 仍为 0、执行 token 不变），渲染提示时再去掉只含空白的行，行号映射以替换后的源码为准；
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
- **本机流程**：先试点 50 个函数单元（按任务 × SolidiFI/非 SolidiFI 分层，固定抽样种子），按 NS-P7 第 4 节预先登记的标准判定是否通过；用户确认后再全量运行。由于提示在 a_k 改名后与视图无关，一次运行同时服务于原名与匿名两种视图，不需要按视图分别运行。

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
4. `dfg_v2.model.make_model(task, carried, profile, "cpu", node_feature="inside_token", hidden_size=128, layers=(cfg.layers if spec.layers is None else spec.layers), heads=8, reducer, layer_impl)`：原样构造，`adapt_ws[i] = Linear(D, 128)`，注册校验通过。
5. S0：不做替换（就是 8H 的模型）。其他配置：
   - 如果 spec 含 TOKEN_IDS（embed_pool），先注册 `model.nodesem_shared = nn.ModuleDict({"token_bag": nn.EmbeddingBag(V, 64, mode="mean"), "token_norm": nn.LayerNorm(64)})`（r5 加入 token_norm）；
   - `model.adapt_ws = nn.ModuleList([NodeSemAdapter(spec, ntype, shared=model.nodesem_shared) for ntype in 按 ntypes_dict 顺序])`，长度不变。适配器用 `object.__setattr__` 保存对共享模块的引用，使其参数只在 `nodesem_shared.*` 下注册一次。
6. 加载 NodeSem 零步初值（见下），核对 tensor_digest。
7. `node_sem.model.validate(model, spec)`：适配器的类型、数量和布局正确，D 与 manifest 一致；然后调用 `dfg_v2.model.validate_registration(model)`。

**NodeSemAdapter**（`node_sem/adapter.py`）：
- 按 spec 的布局切分 `inp`：前 M 列是存在位，之后依次是各模态。
- token 模态（S1）：共享的 EmbeddingBag 与共享的 LayerNorm(64)（第 4.3 节，LayerNorm 只作用于非空行）后接本类型的 `Linear(64, 128)`。连续模态：LayerNorm 后接 `Linear(d_m, 128)`。`b_static`：直接 `Linear(d_static, 128)`。
- 融合方式：
  - `concat`（默认）：`Σ_m p_m · z_m + b`；
  - `gated`：`g = softmax(mask(W_g [p_1 z_1; …]))`，存在位为 0 的模态 logit 置为 −inf；全部缺失时输出 `b`，不得出现 NaN；`h = Σ g_m z_m + b`。`last_gates` 只读保存。
- 输出交给作者 forward 中原有的 `gelu`。
- 模态 dropout（只在 `self.training` 时生效）：每个节点每个模态以 p=0.1 的概率把存在位置 0。随机数来自一个按（fit 种子、"modality_dropout"）派生的 CPU generator，掩码再移到设备上，不消耗全局随机数。

**初值**（`node_sem/init.py`）：
- 从 8H 同一（任务、折、剖面）的零步初值文件（SHA 封存）复制 `gcs.*` 与 `classify.*` 的全部键。形状必须一致，否则报错。其余键（`adapt_ws.*`、`nodesem_shared.*`）都是新参数。
- 新参数：Linear 用 Xavier uniform（偏置 0），EmbeddingBag 用 N(0, 1)（第 0 行置 0），LayerNorm 用 1/0。随机数一律来自 `torch.Generator().manual_seed(parameter_seed(constructor 种子, 参数名, [task_id, fold, profile, spec_digest]))`。
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
| N-A | {S0o, S1o, S2, S4} × {G0, G3R}（原名视图，r16；S0o 新跑，不复用匿名 8H） | 240 |
| N-B | S3 × G3R、S4g × G3R、S4-noG（G0）、S4m × G3R（名字对照） | 120 |
| N-C | {S5, S6, S7, S8} × G3R（本机 LLM 试点版） | 120 |
| N-D | 匿名视图复核 {S0（复用 8H）, S4-anon} × G3R：需先接通匿名 CTX（8G 双射映射 names），目前未实现，由用户决定是否执行 | 30 |

**预先登记（写进 plan，以后不改）：**
- **视图**（r16）：按 EXPERIMENT_POLICY，主实验使用原名视图；S0 指原名 S0o（图上未改名的 token ID）。匿名 8H 的 S0 成绩只作历史参考，不参与任何配对比较。
- **主终点**：重入节点、G3R、S4 − S0o（L-audit，best，外层 BF1，10 折配对，双侧 Wilcoxon）。
- **N-A 的 Holm 家族**（重入节点、G3R）：S4−S0o、S1o−S0o、S2−S0o、S4−S2。
- **交互项**（描述）：(S4−S0o)\_G3R − (S4−S0o)\_G0，按第 3 节第 21 条解读。
- **名字泄漏的必报项**（描述，r16）：每个配置按 SolidiFI（buggy_*）与非 SolidiFI 文件分层报告 BF1、TP/FP/FN 与 Wilson 区间；N-B 中 S4−S4m（只换 CTX 的名字，CODE 仍为原名）。原名 CTX 中约 39%–49% 的节点行含 SolidiFI 标记子串（第 5I 节），结论必须结合分层结果解读。
- **设备与数值一致性**（r16）：同一比较中的两个配置（含 S0o）必须在同一设备类型、同一 torch/CUDA 版本、相同的 TF32 设置下运行；plan 记录 torch.backends.cuda.matmul.allow_tf32 与 cudnn.allow_tf32 的取值，每个 receipt 记录实际取值与 GPU 型号，不一致则拒绝汇总。
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
7. **`get_node_token` 很慢**：控制 D（r9 后 S4 约 715 维，S5 约 1100 维），在 NS-P4 中实测构造时间。NS-P0 实测：真实重入节点 G3R 从 512 维到 600 维，构造时间 8.46→9.49 秒。
8. **显存余量**：8H 中 reentrancy_contract G3R 的整卡最小空闲只有 44 MiB。S1 必须用共享 EmbeddingBag（第 4.3 节）；NS-P4 第 4b 节做 GPU 探针。
9. **CFG 覆盖不完整**：legacy→V2 语义 CFG 支持的含体函数为 3135/3404、1964/2045、2797/3148、1859/1958（NS-P0）。不受支持的函数，顺序事实记为 unknown；守卫采用 AST 词法规则，不受此影响。

---

## 5. Codex Prompts

使用方式：每次开新会话，先贴 5.1 共享上下文，再贴一个 Prompt。按 NS-P0 → P1 → P1b → P2 → P2b → P3a → P3a2 → P3a3 → P3b → P3b2 → P4 → P4b → P5 → P5A → P6 → P6c → P7 → P8 → P9 的顺序执行。每个 Prompt 结束后先交审查，通过后再进下一个。

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
- 特征提取只允许读取节点的 code、node_type、source_file、node_source_code_lines（只用于对齐）以及图的边与边属性。label 是结构性 DOT 标签（代码文本 + AST 锚点），只允许冻结的 Projector/node_code_view 读取它做 AST 身份对齐，NodeSem 代码不得读取，它的任何部分都不得进入特征。禁止读取 type_label、node_info_vulnerabilities、method、任何标签或预测文件。扰动验收按 PROMPTS.md 第 4.2 节 (a)(b)(c) 三项。
- 变量名只能来自已封存 F3 存储中 L1 证据的 Symbol.name/Symbol.kind（经 ddg_fact_indices 定位）、L2 边的 state_vars、L3 边的保留环境表达式；主视图中逐个标识符经 8G 双射映射，映射不到的非保留标识符直接报错。禁止使用 Symbol.id、function、declaration、跨度、文件路径和原始 type_name 文本。
- 配置中的层数回退必须写成 `cfg.layers if spec.layers is None else spec.layers`，不能写 `spec.layers or cfg.layers`。
- 主视图（anonymous）的文本来自 8G 的改名结果；DFG 边上的拼写属性必须先经该文件的 8G 双射映射。主视图的任何特征文本或 LLM 提示中，identifier 只能是保留名或该文件的匿名名，有测试保证这一点。
- 任何特征文本中都不出现绝对行号或文件名，只用函数内相对距离 @-k/@+k。
- AST 事实一律经 ProjectionView + Projector 按 AST 身份投影到节点，投影不到的事实丢弃并计数，不按行号猜测。
- 训练沿用基准 v2 协议：8D 分组折、L-audit、seed=1、local_dev_v1、8H 训练配置，outer_test 只在训练结束后评分。只在 inner_val 上做选择。
- 使用与 8H 相同的 GPU 锁：scripts/DFG/experiments/artifacts/dfg_v2/.training.lock（experiment.run._Lock）。
- 文档编码（r7）：所有 .md/.json/.jsonl 一律以 UTF-8 写入，不得经 Windows 标准输入管道传递中文（NS-P2 因此把全部中文写成了 `?`）。用 Python 脚本写文件（中文可用 \u 转义写在脚本里），写完运行 `python -B -m scripts.node_sem.doc_check --expect-cjk <文件>:<追加前字节数> ...`（新建的文件不带字节数）：文件必须能按 UTF-8 严格解码，新写入部分不得出现连续 3 个及以上的 `?` 或 U+FFFD，并且必须含有中文字符。不通过就不得提交。nodesem 环境中所有使用 GPU 的离线任务（M1/M2 编码、llama.cpp、教师句向量）不得与训练并行。离线脚本启动前必须以非阻塞方式检查该锁文件：被占用就直接退出并报告；不得在训练期间抢占 GPU。CPU 模式的离线任务不受此限制。

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
  另外核对：git status 中，除 scripts/node_sem/ 与三份记录文档外，没有已跟踪文件的改动；benchmark_v2.execution.load(8H plan) 只读通过（它按已批准的生效修订 runtime_resume_v2.json，SHA f18dd07d…，核对运行版本；不要求与原 plan 的 runtime 字面相等），且 experiment.run._code_refs() 与该生效修订记录的运行版本相同。
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

## 0. 开工前（先做，结果写进 PROGRESS）
1. 记录 r4 对 NS-Q1/Q2/Q3 的决定（PROMPTS.md 第 4.2、4.6 节），作为后续实现依据。
2. **torch.load 的使用边界（需要用户在本会话中明确批准后才能执行）**：只允许对“紧接着加载前已核对 SHA256 与封存引用一致”的本地文件调用 torch.load，范围限于 prompt8h_v1/prepared_attempt3 的零步初值、prompt8h_v1/runs 下的 checkpoint，以及 NodeSem 自己生成并封存的文件。torch 1.8 没有 weights_only，这与 8H 执行器现有做法相同。未获批准就停下等待，不要绕过。
3. 获批后，补做 NS-P0 缺的一项：对 60 个 G0/G3R 零步初值逐个加载，独立重算 tensor_digest，与 prepared、initialization_ref、binding 中的 state_sha256 比较。结果写入 artifacts/ns_p1_initial_digests/digests.json。任何不一致就停下报告。

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
- embed_pool：使用模型级共享的 nn.EmbeddingBag(V, 64, mode="mean")（第 4.3、4.9 节），每个适配器只加自己的 Linear(64,128)。
  - 前向：token 列转成 long 前，检查是否为精确非负整数且 < V；检查非零 ID 构成右侧填充的连续前缀（中间出现 0 就报错）；拼成一维 input 与 offsets 调用 EmbeddingBag；空行得到零向量。
  - V 用 TokenEncoder 的 tokenizer 词表大小，并核对 8G 特征的最大 ID < V。
  - 禁止为每种节点类型各建一个 Embedding，禁止展开 N×512×d 的中间张量。
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
- 加载前核对文件 SHA（见第 0 节的 torch.load 边界），加载后独立重算 tensor_digest 并与 state_sha256 比较；
- 复制 gcs.* 与 classify.* 的全部键（形状必须一致）；
- 其余键（adapt_ws.*、nodesem_shared.*）都是新参数，按第 4.9 节的规则初始化，随机数来自 parameter_seed(constructor 种子, 参数全名, [task_id, fold, profile, spec.digest()])；
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
- 构造：分别用 benchmark_v2.execution.construct（8H plan）与 node_sem.execution.construct（S0 spec）构造模型。node_sem 侧在调用 make_model 之前同样执行 seed_all(constructor 种子)，在 fit 之前同样执行 seed_all(fit 种子)。比较 state_dict、每种节点类型的 inp、etypes_dict、binding 中与特征无关的字段，要求逐位相同。
- 训练：两边都用 benchmark_v2.trainer.fit 在临时目录跑 2 个 epoch（config 只把 maximum_training_epochs 改为 2，并写明这是等价检查配置）。比较每轮 loss、最终参数、Adam 状态、scheduler 状态，以及 inner_val/outer_test 预测，要求逐位相同。
- 结果写入 scripts/node_sem/artifacts/ns_p1_equivalence/equivalence.json。

## 9. 测试（CPU，使用 dfg_v2/tests 中已有的小 fixture 或同源 fixture）
- FeatureSpec：to_json/from_json 往返；digest 稳定；S0 的约束；layout 的列区间。
- carrier：行顺序、行身份、code SHA、图指纹、NPZ 数组名、维度、dtype、非有限值，任一项被篡改都会被拒绝；禁止属性扰动后载体不变；原图未被修改。
- adapter：EmbeddingBag 平均与逐行手算的平均一致（误差 ≤1e-6，含全填充行）；非整数、越界 ID、填充不连续都报错；17 个适配器共享同一个 EmbeddingBag（named_parameters 中只出现一次）；S0 不替换 adapt_ws；S1 的总参数增量与按公式计算的一致。
- init：S0 与 8H 初值逐位相同；S1 中 gcs.* 与 classify.* 与 8H 相同；同样的输入两次生成逐位一致。
- layers 回退：spec.layers=0 时实际构造 0 层，spec.layers=None 时用 cfg.layers。
- 扰动验收：第 4.2 节 (a)(b)(c) 三项。
- model：替换 adapt_ws 后 validate 与 validate_registration 都通过；适配器数量错误被拒绝。

## 验收
测试与第 8 节的证明通过；PROGRESS.md 记录（含构造耗时）；提交 NS-P1。不跑正式训练。
```

### 5.3b Prompt NS-P1b：运行版本绑定拆分与 S1 初始尺度修正（NS-P2 之前必须完成）

```text
# NS-P1b：运行版本绑定拆分（执行/只读核验）与 S1 初始尺度修正

前置：NS-P1（792ebeed）。NS-P1 的产物（ns_p1_initial_digests、ns_p1_acceptance、ns_p1_equivalence，包括 acceptance_revision1）全部只读保留，不覆盖、不重签。新产物写入 artifacts/ns_p1b/。不跑正式训练，不使用 GPU。

## 背景（审查结论，写进 PROGRESS）
1. execution.load 要求 plan["runtime"] == runtime_refs()，而 runtime_refs() 包含 scripts/node_sem 下除 tests/artifacts 外的全部 .py（连 recon/ 也在内）。NS-P2 一旦新增 text_view.py，NS-P1 报告中给出的只读核验命令就会失败；以后 N-B/N-C 引用 N-A 的结果、汇总报告时同样会失败。这与 8H 需要 runtime_cache_fix_v1、runtime_resume_v2 两次修订的原因相同。
2. S1 的 EmbeddingBag 按 r4 用 N(0,0.02) 初始化。均值池化后向量标准差约 0.02/√L，经 Linear(64,128) 后约 10⁻³ 量级；全图训练每个 epoch 只有 1 次 Adam 更新，50 轮、学习率从 0.0002 起步，S1 在训练初期几乎没有输入信号。这是方案（不是实现）的错误。

## 1. 运行版本绑定拆分（execution.py）
- 在 scripts/node_sem/__init__.py 中定义 RUNTIME_MODULES：训练路径上的 NodeSem 模块清单（现在是 __init__.py、feature_spec.py、carrier.py、adapter.py、model.py、init.py、checkpoint_io.py、execution.py）。以后新增的训练路径模块（例如 NS-P4 的融合模块）必须显式加入；特征生产者（text_view、facts、offline/ 等）不进入运行版本，它们的实现 SHA 通过各模态 manifest 的 implementation 字段绑定到特征上。
- runtime_refs() = experiment.run._code_refs() ∪ {RUNTIME_MODULES 中每个文件的 SHA}。清单中的文件缺失就报错。
- load(path, mode)：
  - mode="execute"（worker、all、execute 默认）：与现在相同，要求 plan["runtime"] == runtime_refs()；
  - mode="verify"（verify 命令、报告、跨批次引用）：不比较当前代码。改为核对 plan/seal/authorization 的绑定、每个已完成 fit 的 started.json 中的 runtime 与 plan["runtime"] 相同、receipt 与全部产物 SHA，并在结果中写明 "current_code_equality": "not_required"。
- VERSION 升为 "nodesem-execution-v2"。新计划用 v2；v1 计划（NS-P1 的 batch 与 acceptance_revision1）只允许以 verify 模式读取，且按 v1 当时的 runtime 定义核对 started.json。
- controller(path) 的 "all" 用 execute 模式；"verify" 子命令用 verify 模式。
- S0 复用核验继续调用 8H 自己的 load（只依赖 scripts/DFG 与 sco_models），不变。

## 2. S1 初始尺度（adapter.py、model.py、init.py）
- model.nodesem_shared 增加 "token_norm": nn.LayerNorm(64)（elementwise_affine=True）。NodeSemAdapter.forward：pooled = token_bag(...)；只对非空行做 token_norm，空行保持 0；再接本类型的 Linear(64,128)。适配器同样只持有未注册引用；validate 检查 state_dict 中 token_bag 与 token_norm 各只出现一次。
- init.py：EmbeddingBag 权重用 N(0,1)（第 0 行置 0），LayerNorm 权重 1、偏置 0；Linear 仍为 Xavier uniform、偏置 0。随机数来源不变（parameter_seed）。
- 不改 S0 路径：S0 仍不注册 nodesem_shared，仍用原 Linear(512,128)。

## 3. 初始尺度的诊断（只做 CPU 前向，不训练，不读取任何标签或指标）
在 reentrancy_node fold0 G3R 上，分别构造 S0、S1（r4 初始化，N(0,0.02)，无 LayerNorm）、S1（r5），加载各自零步初值后做一次 eval 前向，记录：
- 每种节点类型 h0 = gelu(adapt_ws(inp)) 的均值、标准差、绝对值的 99 分位；
- 第一层 HGT 输出（经 LayerNorm 前、后）的标准差；
- 第一层注意力 head 最大权重 ≥0.99 的比例（方法同 dfg_v2/attention_probe.py）。
写入 artifacts/ns_p1b/init_scale.json。这一步只是记录，r5 的决定不依赖这些数字；如果 r5 的 h0 标准差不在 [0.05, 5] 区间内，停下报告。

## 4. 回归与等价
- 对 reentrancy_node fold0 G3R 重做一次 S0 的 CPU 等价检查（新旧入口各 2 个 epoch，比较方式与 NS-P1 第 8 节及已批准的 scheduler 规则相同），证明 execution.py 的改动没有影响 S0 路径。结果写入 artifacts/ns_p1b/s0_equivalence.json。
- 用新代码以 verify 模式只读核验 NS-P1 的 acceptance_revision1 计划，应当通过。
- 用 S1（r5）在 reentrancy_node fold0 G3R 上调用 benchmark_v2.trainer.fit 跑 1 个 epoch（CPU，maximum_training_epochs=1，写明是冒烟配置）：loss 有限；token_bag、token_norm、各 Linear 都有非零梯度；gcs/classify 初值与 8H 相同。不计入任何结果。

## 5. 测试
- runtime：新增一个与训练无关的 node_sem 文件后，verify 模式仍然通过，execute 模式也通过（该文件不在 RUNTIME_MODULES）；修改 RUNTIME_MODULES 中的任一文件后，execute 模式拒绝、verify 模式对已完成的 fit 仍然通过；篡改任一 receipt、产物或 started.json 中的 runtime，verify 模式拒绝；RUNTIME_MODULES 中的文件缺失时报错。
- S1：token_norm 只作用于非空行（空行输出为偏置）；共享模块在 named_parameters 与 state_dict 中各只出现一次；初值确定性（两次生成逐位一致）；r5 初值的 EmbeddingBag 第 0 行为 0、其余行的经验标准差在 1±0.05。
- 全部 node_sem 测试、dfg_v2 测试与原回归。

## 验收
以上全部通过；PROGRESS.md、HANDOVER.md、docs/training_changes_2026-10-07.md 追加记录；提交 NS-P1b。不推进 NS-P2。
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
- 行集合：以 F3 图节点为全集（含 env_source），manifest 的 profiles 登记 F0 与 F3 的图指纹；先用测试确认原节点在 F0 与 F3 中的 9 个属性逐项相同。同时扩展 carrier._aligned：manifest 行集合可以是图节点的超集，但被略去的行必须全部是辅助节点，且顺序按图节点顺序取出（加正反测试）。
- 生产者扰动测试：对图的深拷贝施加第 4.2 节 (a)(b) 扰动后直接调用 build_text_view，text.jsonl 的行内容逐位相同；(c) 报错。不得用载体上的测试代替。
- 两个视图的 cut_mode 逐行相同；
- 用 8G 的双射把主视图文本还原后，与次要视图的文本逐字相同（保留名不变）；
- 主视图文本中的 identifier 只能是保留名或该文件的匿名名；
- 文本中没有绝对行号或文件名；
- 用手写 fixture 检查每种节点类型的截取结果（精确字符串）：带 modifier 和 returns 的函数签名、else-if 链、for 头部、合约继承头部、struct。

## 2b. 模态 manifest 契约（offline/encode.py 输出必须满足 carrier._load，先读该函数再写）
- version = carrier.MODALITY_VERSION（"nodesem-modality-v1"）；modality = CODE（M1）或 CTX（M2）；view；task_id；feature_dtype = "float32"；feature_shape = [行数, 维度]；data = NPZ 引用（数组名只能是 features）；
- rows：每行 row_key、file、node_type、source_sha256、code_sha256、vector_sha256、present（布尔；present=false 的行必须全为 0）；行集合按第 4.2 节（F3 全集）；
- profiles：登记 F0 与 F3 的 graph_fingerprint；sources：源码引用；input_text：text.jsonl 引用；
- implementation：生产者源码引用（至少 text_view.py 与 offline/encode.py）；assets：模型文件引用（来自 offline/assets.json）。
- 载体在装配时会逐个核对 implementation 与 assets 的 SHA。因此生产者代码（text_view.py、encode.py 等）一旦修改，旧特征就不能再用于启动新的 fit，必须重新生成特征、写新 manifest、封存新计划；不得在批次进行中修改生产者。只读核验已完成的 fit 不受影响（NS-P1b 的 verify 模式）。

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

### 5.4b Prompt NS-P2b：文档重写、写入校验与编号影响诊断（NS-P3 之前必须完成）

```text
# NS-P2b：重写 NS-P2 的四处文档、加入文档写入校验、编号影响诊断（只读）

前置：NS-P2（f049d18e）。NS-P2 的代码、文本视图、编码产物与环境记录全部只读保留。新产物写入 artifacts/ns_p2b/。不训练，不使用 GPU，不改任何特征或代码（doc_check.py 除外）。

## 背景（审查结论，写进 PROGRESS）
NS-P2 写入的四处文档中，所有中文都以字面 `?`（0x3F）落盘，不是显示问题，内容无法从文件恢复：
- scripts/node_sem/NS_P2_REPORT.md（全文）；
- scripts/node_sem/PROGRESS.md 中 “## 2026-11-01 NS-P2…” 一节；
- HANDOVER.md 中 “### 2026-11-01 NodeSem NS-P2…” 一节；
- docs/training_changes_2026-10-07.md 中 “## 74. …” 一节。
NS-P1 已记录过 “Windows stdin 传输需要 ASCII Unicode 转义”，NS-P2 中这一做法没有保持。JSON 证据（environment/*.json、encoding_summary.csv、各 manifest 等）是 ASCII，未受影响。

## 1. 原因与保护
- 在 PROGRESS 中写清楚这四处文档当时是怎样写入的（哪条命令、经由什么通道），以及为什么中文变成了 `?`。
- 新增 scripts/node_sem/doc_check.py（不进入 RUNTIME_MODULES）：
  - check(path, since_bytes=None)：文件必须能按 UTF-8 严格解码；若给出 since_bytes（追加前的文件长度），只检查新增部分；新增部分不得含有连续 3 个及以上的 `?`；若新增部分声明为中文段落（含 “## ” 或 “### ” 标题且标题中原本应有中文），必须至少含有一个 CJK 字符。
  - 命令行：python -B -m scripts.node_sem.doc_check <path>[:since_bytes] ...，失败时返回非零。
  - 测试：正常 UTF-8 中文通过；字面 “????” 不通过；非法 UTF-8 不通过；since_bytes 之前的旧内容不参与检查。

## 2. 重写四处文档
- 先把四处损坏内容的原始字节保存到 artifacts/ns_p2b/corrupted_docs/（每处一个文件，记录 SHA256、所在文件、起止字节位置），作为记录。
- NS_P2_REPORT.md：整份重写（UTF-8）。
- PROGRESS.md、HANDOVER.md、training_changes：只替换各自的 NS-P2 那一节（就地替换，因为原节只剩 `?`，不含可保留的信息）。替换前后，该节之前的全部字节必须逐字节相同（记录前缀 SHA），该节之后没有其他内容。
- 内容依据：NS-P2 的 JSON/CSV/manifest 证据、提交 f049d18e 的代码与 Codex 本地记录。重写的内容必须与证据一致，至少包括：做了什么、文件清单、nodesem 环境（版本、来源、user-site 副作用与恢复、PYTHONNOUSERSITE）、四个任务的文本行数与 cut_mode 分布、八次编码的去重率/截断数/耗时/峰值显存/重复确定性、测试数、载体超集改动、遗留问题。所有数字从证据文件重新读取，不凭记忆。
- 四处文件都通过 doc_check 后才能提交。

## 3. 编号影响诊断（只读，CPU，numpy 即可）
审查发现：在 reentrancy_node 中，12036 个原节点里有 8770 个的原文代码也出现在其他文件中；这 841 条跨文件共享的原文语句里，有 735 条在匿名视图中因 8G 的逐文件编号而变成不同字符串（四个任务分别为 735/841、561/669、1155/1269、893/1005）。
对每个任务、每个匿名视图的 CODE 向量（NS-P2 的 NPZ），计算：
- 组内相似度：对每条“跨文件共享、且匿名文本不止一种”的原文语句，取其各个匿名变体向量的两两余弦，报告均值、中位数、5% 分位；
- 对照一：同一节点类型内随机抽取的、原文不同的语句对的余弦（固定种子，抽样数与组内对数相同）；
- 对照二：原名视图中这些语句（同一原文的向量本应完全相同）作为上限 1.0 的检查。
写入 artifacts/ns_p2b/numbering_effect.json。只记录，不改变任何特征或决定（第 4.5 节）。

## 4. 未改名的剩余名字
用 tree-sitter 统计主视图节点文本中，既不是 vN、也不在保留表中、却以单词形式出现的名字（审查时看到 data、number、min、max、sig、interfaceId 等十余个，均因不是 identifier 语法节点而被 8G 保留）。按任务给出名字、出现次数、语法节点类型，写入 artifacts/ns_p2b/residual_names.json，并确认其中没有 SolidiFI 标记名（例如含 re_ent、txorigin 的名字）。只记录。

## 5. 测试与提交
- doc_check 的测试、全部 node_sem 测试、dfg_v2 测试与原回归。
- 只读核验：carrier.load_modality 对 8 份编码 manifest 仍然通过；8H 计划 load 仍然通过。
- PROGRESS、HANDOVER、training_changes 追加 NS-P2b 记录（同样通过 doc_check）；提交 NS-P2b。不推进 NS-P3。
```

### 5.5 Prompt NS-P3a：StatementFacts（AST 后端）、守卫与授权变量、通用性冒烟

```text
# NS-P3a：StatementFacts（AST 后端）——事实抽取、Oracle 测试与通用性验收（不生成特征向量）

前置：NS-P2b（6943c931）通过。设计依据：PROMPTS.md 第 4.2 节（读取边界、名字来源、行集合、扰动验收）、第 4.6 节（M3a 各组、定义、守卫规则 1–6、名字例外、版本归一化）与 第 4.5 节（M2 需要的事实）。本步只产出事实（facts.jsonl）与测试，不生成 M2 文本、不生成 M3a 向量、不编码、不训练、不用 GPU。

## 0. 先读、后写（结论写进 PROGRESS）
逐个阅读并记录将要复用的接口与它们的实际行为：
- scripts/node_sem/text_view.py 的上下文加载（8H plan → 8G 改名结果 → F0/F3 图），以及它如何得到每个文件两个视图的源码与 ProjectionView/Projector；
- scripts/DFG/dfg_v2/l1_cfg.py（V2CFGBuilder）与 NS-P0 recon/cfg.py 中“legacy→V2”的选择方式；
- F3 存储中 audit.layers.L1.evidence（ddg_fact_indices 的含义、Symbol 字段）、L2 证据（state、statement、via_alias、status）、L3 证据（env_key、spellings）的读取方式与 SHA 引用（dfg_v2/pipeline.py::_evidence、store.py）；
- scripts/DFG/state/stage_j/binding.py::ClosedScopeJ（同文件继承链、成员解析）；
- scripts/DFG/dfg_v2/env.py（14 个环境键与写法合并）；
- benchmark_v2/prepare_spelling.load_result 中的文件内双射（原拼写 ↔ vN），用于名字映射与 I 组例外项。
如有与本 Prompt 描述不符的接口事实，以代码为准，在 PROGRESS 中记录并说明处理；若影响设计（例如某个事实无法按 AST 身份投影），停下报告。

## 1. 事实 schema（scripts/node_sem/facts_schema.py）
定义 StatementFacts（普通类或 dict 加校验函数，兼容 Python 3.7），字段与第 4.6 节各组一一对应，取值用固定字符串枚举（不得出现漏洞类别名）：
- node_kind：statement | condition | state_decl | function | modifier | contract | env | end | other；
- external：{kinds: 集合, value_attached, uninvoked_call_value, target_classes: 集合, value_class, data_class, return_handling}；
- state：{writes: [{var, shape, auth}], reads: [...], array_size_change: bool, status: supported|unknown}；
- dfg：{defs: [{var, kind, from_offset}], uses: [...], from: [{node, offset}], to: [{node, offset, sink}], status: supported|unknown}；
- order：{reachable_from_ext_call, dominated_by_ext_call, write_then_call, call_then_write, ext_call_in_loop, status: supported|unknown}；
- guards：[{rule: 1|2|3|4|5|5p|6, kind, polarity, operand_classes, eq_pairs, is_sender_guard, offset}]、guard_status（none|present|unknown）、nearest；
- self_condition（只对 require/assert/if/while/for）：{operand_classes, eq_pairs, early_exit_if}；
- env：{keys: 集合, uses: 集合}；arith：{ops, on_state, small_int, from_param, from_env, sinks, in_unchecked}；loop：{bound}；syntax：集合；
- function_ctx：{visibility, payable, read_only, is_constructor, is_fallback, has_modifier, name_case_only_differs_from_contract}；
- state_decl（只对状态变量声明）：第 4.6 节 K 组各项；fn_summary（只对函数类节点）：L 组；contract_summary（只对合约类节点）：M 组；
- names：用于 M2 的变量名（主视图为匿名名，原名视图为原名），与其余事实分开存放；
- unresolved：{原因: 计数}；provenance：{source_sha256, store_refs, view}。
validate(facts) 检查枚举、类型与“不适用组为空”的约束。

## 2. AST 后端（scripts/node_sem/facts.py）
extract(task_id, view) -> {row_key: StatementFacts}，按文件处理，步骤固定：
1. 取该视图的源码与 ProjectionView、Projector（与 text_view 相同的加载路径）；label 只经 Projector 读取。
2. 枚举函数单元（function、constructor、modifier、fallback/receive，含无函数体的声明）；为每个函数单元建立语句节点的 AST 先序表，用于相对距离 @±k（第 4.5 节定义）。
3. 函数 CFG：按 NS-P0 的“legacy→V2”方式构造语义 CFG，经精确事件锚点投影到 HCG 节点；不受支持的函数 order.status=unknown。不得使用 HCG 自身的 CFG 边。
4. L1/L2/L3：从 F3 存储的封存证据读取（先核对 SHA）。DATA_DEF_USE 只来自 L1 支持的函数，不支持时 dfg.status=unknown。名字只取 Symbol.name/kind 与 L2 state_vars，主视图逐个标识符经 8G 双射映射，映射不到的非保留标识符直接报错。type_name 只归类为形状。
5. 外部调用、金额、目标、数据、返回值（A、F 组）：按 AST 形状判断，规则见第 4.6 节“定义”。`.call.value(x)` 未被调用时只记 uninvoked_call_value。
6. 守卫：按第 4.6 节规则 1、2、3、4、5、5′、6 计算，记录规则编号与极性；有效比较按极性换算；`&&` 拆分、`||` 不计入相等组合。
7. 授权变量：在每个合约（含同文件基类）中，收集所有发送者守卫里与 msg.sender/tx.origin 做有效相等比较的状态变量；然后回填 state.writes/reads 的 auth 标记、K/L/M 组。
8. 其余各组（E、E1、G、H、I、J、K、L、M、N）按第 4.6 节计算。版本写法按第 4.6 节原则 3 归一化。I 组名字例外：用原拼写判断“与合约名仅大小写不同”（主视图经双射还原），只输出布尔值。
9. 投影：所有 AST 结论经 Projector 映射到 HCG 节点；投影不到的记 unresolved，不得按行号猜测。env_source 行只填 env 与 node_kind。
输出 artifacts/facts_v1/<view>/<task_id>/facts.jsonl（行集合为 F3 全集，行顺序同 text_v1）与 manifest.json（版本、视图、任务、行数、F0/F3 指纹、源码引用、F3 存储与证据引用、实现文件 SHA、unresolved 汇总），并封存。

## 3. 通用性要求
- 代码、schema 与枚举中不得出现任何漏洞类别名（reentrancy、access_control、arithmetic、denial_of_service、front_running、time_manipulation、unchecked 等）；加一条测试扫描 facts.py、facts_schema.py。
- 新建 scripts/node_sem/behavior_coverage.md：逐字段写出它描述的通用 Solidity 语义，以及它与 7 类漏洞中哪些相关（只作说明，代码不读取）。写明 I 组的名字例外。
- **跨类别冒烟**（只读、只用原名视图、不用图、不读标签）：从 experiments/ge-sc-data/source_code/ 的另外 5 个类别（arithmetic、denial_of_service、front_running、time_manipulation、unchecked_low_level_calls）中，每类按文件名排序后固定取 10 个 .sol（SolidiFI 的 buggy_N 与非 SolidiFI 各 5 个），对每个函数单元直接在 AST 上计算不依赖 DFG 边的事实（A、A1–A4、D、D1–D3、E、E1 中的 AST 部分、F、G、H、I、J、K、L、M），依赖 DFG/CFG 的部分记 unknown。要求：0 个异常；报告每类的函数数、各组非零率、unknown 率、解析失败数。写入 artifacts/facts_v1/cross_category_smoke.json。这些类别还没有 F3 图，冒烟只验证事实抽取在各类别源码上能运行，不代表完整特征。

## 4. Oracle 测试（真实 tree-sitter 解析；fixture 放在 scripts/node_sem/tests/fixtures/nodesem_oracle/，先写期望 JSON 再运行）
已有用例（保留）：
a) msg.sender.call.value(_am)() 独立语句 → call、附带金额、目标 msg.sender、金额 参数、返回值 ignored；
b) if (!msg.sender.send(x)) throw; → send、返回值 checked_in_if；
c) (bool ok, ) = a.call(data); 之后不在条件中使用 ok → assigned_unchecked；
d) 在 call 之后执行 balances[msg.sender] -= amount; → 写 mapping、减法、作用于状态、reachable_from_ext_call、call_then_write（在调用语句上）；
e) require(msg.sender == owner); owner = x; → 第二句规则 1、发送者守卫、组合 env 对状态；owner 是授权变量，第二句写授权变量；
f) require(tx.origin == ownerState) 与 require(tx.origin == _param) → 组合分别为 env 对状态、env 对参数；
g) modifier onlyOwner { require(msg.sender == owner); _; } 应用到 function kill() onlyOwner { selfdestruct(owner); } → 规则 5、selfdestruct、目标 状态变量；
h) pragma 0.4.x，contract Wallet { function Wallet() public {...} } → is_constructor；
i) for (uint i = 0; i < users.length; i++) users[i].transfer(1); → transfer、循环边界 状态/数组长度、ext_call_in_loop；
j) 状态变量先写、后发生外部调用 → write_then_call；
k) if (now > deadline) {...} 内的语句 → 规则 2、极性 +、操作数含时间戳；
l) if (msg.sender != owner) throw; owner = x; → 第二句规则 3、极性 −、有效相等 env 对状态；
m) if (c) { a = 1; } b = 2; → b = 2 没有守卫；
n) 同一文件声明了 function require(bool) 时，require(...) 不视为守卫；
o) modifier 无法解析 → guard_status=unknown；
p) 函数 CFG 不受支持 → order.status=unknown，不是 false。
新增用例（覆盖其余类别中的通用模式）：
q) uint8 v = 0; v = v + p;（p 为参数）→ 加法、small_int、from_param、结果写局部；
r) uint256 amount = uint256(cnt) * _value; require(_value > 0 && balances[msg.sender] >= amount); → 乘法、操作数来自参数、结果流向 guard（TO 汇点 guard）；
s) pragma 0.8，unchecked { x -= y; } → in_unchecked；
t) for (...) { addrs[i].send(1); } 与 require(bidder.send(bid)); → ext_call_in_loop；返回值 checked_in_require；
u) for (...) { list.push(msg.sender); } 与 list.length = 0; → array_size_change、循环内写状态；
v) require(hash == sha3(solution)); msg.sender.transfer(1000 ether); → 第二句守卫操作数含哈希结果与状态，组合 哈希对状态；转账目标 msg.sender、金额 字面量；语法袋含哈希；
w) owner.transfer(reward); reward = msg.value; → 金额 状态变量；msg.value 流向状态写；call_then_write；
x) if (now % 15 == 0) { msg.sender.transfer(this.balance); } → 时间戳用于算术与守卫；金额 this.balance；
y) uint r = uint(keccak256(abi.encodePacked(block.timestamp))) % 2; → 时间戳用于哈希输入；取模；
z) pragma 0.5，function f(address payable c) public { c.call.value(1 ether); } → uninvoked_call_value=true，不计为外部调用，F 组为“不适用”；同文件中 c.send(1); 单独成句 → send、ignored；
aa) target.delegatecall(msg.data) 在 fallback 中 → delegatecall、数据 msg.data、目标 状态变量、is_fallback；
bb) modifier onlyOwner { if (msg.sender == owner) _; } → 被修饰函数中的语句为规则 5′、极性 +、发送者守卫；
cc) function _check() internal { require(msg.sender == owner); } function f() public { _check(); x = 1; } → x = 1 为规则 6（internal_check）；
dd) 同一合约中 owner 在 modifier 里与 msg.sender 比较，另有 function setOwner(address o) public { owner = o; } 无守卫 → owner 的 K 组“存在未受发送者守卫保护的写入函数”=true，setOwner 中的语句写授权变量且无守卫；
ee) contract Wallet { function wallet() public { owner = msg.sender; } } → name_case_only_differs_from_contract=true、is_constructor=false；两个视图结果相同；
ff) `if (a || msg.sender == owner) {...}` 内的语句 → 守卫存在，但有效相等组合为空（|| 不计入）；
gg) 0.4 写法 throw、sha3、suicide、now、.value() 与 0.5 写法 revert()、keccak256、selfdestruct、block.timestamp、{value:} 的对应语句 → 事实逐项相同（版本归一化）；
hh) 状态变量声明 mapping(address=>uint) public balances; 被两个函数写、一个函数读 → K 组形状 mapping、public、写入函数数“多”、读取；合约节点 M 组与函数节点 L 组的汇总正确。

## 5. 其他测试
- 视图一致性：四个任务中，两个视图的事实（names 字段除外；names 按双射还原后相同）逐节点相同。不一致必须逐条列出原因，不得放宽。
- 名字泄漏：主视图 names 中的标识符只能是保留名或该文件的匿名名；provenance 之外没有文件名与绝对行号。
- 生产者扰动（第 4.2 节）：对图的深拷贝施加 (a)(b) 扰动后直接调用 extract，facts.jsonl 逐位相同；(c) 报错。
- validate() 对全部输出通过；category 名字扫描测试通过。

## 6. 真实数据统计（不训练、不按标签分组）
按任务、视图统计：各节点种类的行数；每个事实字段的非空率；dfg.status、order.status、guard_status 为 unknown 的比例；守卫规则 1–6 各自的命中数；modifier 解析成功/失败/继承数；授权变量个数分布；uninvoked_call_value 个数；unresolved 原因分布。写入 artifacts/facts_v1/stats.json。

## 验收
测试与统计通过；PROGRESS、HANDOVER、training_changes 追加记录（doc_check --expect-cjk 通过）；提交 NS-P3a。不推进 NS-P3b。
```

### 5.5a2 Prompt NS-P3a2：状态“未知”的精确化、析取型发送者守卫、名字无关性测试（NS-P3b 之前必须完成）

```text
# NS-P3a2：修正状态事实的未知扩散与析取守卫，重新生成并验收 facts

前置：NS-P3a（bed6223f）。facts_v1/accepted_attempt2 只读保留；新结果写入 artifacts/facts_v1/accepted_attempt3/，通过后再更新 CURRENT.json。不改冻结的 DFG/L1/L2/L3 代码与证据，不新增 DDG 边，不训练，不用 GPU。视图口径按当前 EXPERIMENT_POLICY.md（original），除非用户另有指示。

## 背景（审查结论，写进 PROGRESS）
1. facts.py::_bind_layers 对每条 kind 含 "unresolved" 的 L2 诊断，把所属函数内全部语句的 state.status 置为 unknown。L2 的 state_name_missing 表示“该标识符既不是局部变量，也不是文件内作用域的成员”，内置函数与全局名（require、assert、keccak256、now 等）都会触发它。结果：reentrancy_node 有 2123 行仅因 state_name_missing 被置为 unknown，例如 reentrancy_bonus.sol 中 `rewardsForA[recipient] = 0;`（写已知状态变量）以及 SafeMath 中 `if ( a == 0 )`、`return c;`（不涉及状态）。四个任务 state unknown 比例为 66%/66%/76%/81%。
2. 同一机制下，函数内任何一个事件没有 HCG 节点（如 emit、revert），就使函数汇总（L 组）与合约汇总（M 组）成为 unknown，即使缺失的事件对汇总没有影响。
3. 守卫：`require(msg.sender == owner || msg.sender == address(this))` 被判为“不是发送者守卫”。这是方案第 4.6 节规则（|| 不计入）的错误：当析取的每一项都是对发送者（msg.sender 或 tx.origin）的相等比较时，条件必然把发送者限制在一个集合内，属于发送者守卫。

## 1. 状态未知的精确化（facts.py，必要时新增 facts_state.py）
1. **诊断分类**：对每条 L2 unresolved 诊断，按其记录的 AST 位置取出标识符及其语法角色（诊断中没有位置时，只读地重跑冻结的 L2 绑定器取回位置，不改冻结代码）。以下情形不构成状态不确定，不得置 unknown：
   - Solidity 内置函数与全局名：require、assert、revert、keccak256、sha3、sha256、ripemd160、ecrecover、addmod、mulmod、selfdestruct、suicide、now、blockhash、gasleft、type、abi，以及 msg/tx/block/this/super；
   - 用作类型或类型转换的名字：address、payable、bool、string、byte、bytes、bytesN、intN、uintN、fixed/ufixed 系列，以及 `new T(...)`、变量声明中的类型名；
   - 只出现在调用位置的被调函数名（call_expression 的 function 部分）、emit 后的事件名、函数头中的 modifier 调用名。
   其余（在读或写的取值位置上、无法解析的标识符，典型是来自文件外基类的成员）才是状态不确定。
2. **作用范围**：
   - 语句自身的 state.status：只有当该语句自身的 AST 中含有上述“状态不确定”标识符、或使用了未解析别名的局部变量、或自身有未投影的状态效应时，才置 unknown；
   - 函数级的不确定（函数内任一语句含写位置上的状态不确定标识符、未解析别名、未投影的状态写）只影响该函数的 L 组中与写状态相关的位、该函数参与的 K 组写入计数与“未受保护写入”，以及 C 组顺序（沿用现有 missing_effects 规则）；
   - L 组与 M 组的其余位直接从函数/合约的完整 AST 计算（包括没有 HCG 节点的 emit、revert 等），投影缺失不得使它们成为 unknown；K 组写入函数数使用全部 L2 证据（含未投影证据中的语句与函数信息）。
3. 保留每行的 unresolved 计数（诊断信息），只改变 status 的判定。

## 2. 析取型发送者守卫（facts_guards.py）
- 有效比较中：若一个析取（||）的每一项都是“发送者类 env（msg.sender 或 tx.origin）与某操作数的有效相等”，则该条件是发送者守卫，eq_pairs 取各项类别组合的并集，并在守卫记录中加 disjunctive=true；只要有一项不是发送者相等比较，就仍按现规则不计入相等组合。
- 极性为负时按 De Morgan 换算：`if (msg.sender != a && msg.sender != b) revert;`（规则 3）等价于有效的 `msg.sender == a || msg.sender == b`，同样是析取型发送者守卫。
- 授权变量与 K/L/M 组随之重新计算。
- 新增 Oracle 用例（先写期望再运行）：
  ii) require(msg.sender == owner || msg.sender == address(this)); x = 1; → 发送者守卫，eq_pairs 含 env 对状态，disjunctive；owner 是授权变量；
  jj) if (msg.sender != a && msg.sender != b) revert(); y = 1; → 规则 3，发送者守卫，eq_pairs 含两项（a、b 为状态变量时为 env 对状态），disjunctive；
  kk) require(msg.sender == owner || paused == false); → 不是发送者守卫（有非发送者项）；
  ll) 函数 f 中 `require(msg.sender == owner); rewards[a] = 0;` 与 `uint c = a * b; assert(c / a == b); return c;` → 两个函数中所有语句的 state.status 都是 supported（内置名不造成未知）；
  mm) 合约继承了文件外的基类，函数中读写 `inheritedVar = 1;`（该名字在文件内无声明）→ 这条语句 state.status=unknown，同函数中只写本文件状态变量的另一条语句仍为 supported；
  nn) 函数含 `emit Log(now);`（emit 没有 HCG 节点）→ 该函数 L 组“使用时间戳”为 1，L/M 组 status 为 supported。
- 已有用例 ff（`a || msg.sender == owner`）保持“无相等组合、非发送者守卫”。

## 3. 名字无关性测试
- Fixture 级（必须）：对全部 Oracle 源码，用一个确定的双射把所有非保留标识符改名（例如 n1、n2…），重新抽取事实：除 names 字段（按双射还原后相同）与 I 组“仅大小写不同”一位（该位按改名前的拼写计算，测试中显式传入还原映射）外，所有事实逐项相同。
- 真实数据级：只在用户确认视图口径后执行（见第 5F 节）；本步不读取匿名产物。

## 4. 重新生成与比较
- 四个任务重新抽取到 accepted_attempt3/original/；与 accepted_attempt2 逐行比较：
  - 预期变化只有：state.status、L/M/K 组的 status 与受影响的位、守卫的 is_sender_guard/eq_pairs/disjunctive、授权变量及其回填位；
  - 每行的 reads/writes 列表、调用、环境、算术、语法、DFG 事实必须不变；出现其他变化逐条列出原因，不得放宽。
- 报告修正前后各组 unknown 比例（分母与 NS-P3a 相同）与按原因的分布；报告析取型发送者守卫的个数与新增授权变量个数。
- 重跑跨类别冒烟（另外 5 类，原名，无图）：0 异常。

## 5. 测试与验收
全部 node_sem 测试、dfg_v2 测试与原回归通过；facts_verify 对 accepted_attempt3 通过；CURRENT.json 指向 accepted_attempt3（旧版本记为 superseded）；PROGRESS、HANDOVER、training_changes 追加记录（doc_check --expect-cjk 通过）；提交 NS-P3a2。不推进 NS-P3b。
```

### 5.5a3 Prompt NS-P3a3：合取守卫、throw、三值汇总与 K 组未知目标（NS-P3b 之前必须完成）

```text
# NS-P3a3：facts 的四处精度修正，重新生成 accepted_attempt4

前置：NS-P3a2（e2d7e195）。accepted_attempt3 只读保留；新结果写入 artifacts/facts_v1/accepted_attempt4/，通过后再更新 CURRENT.json。视图：original（EXPERIMENT_POLICY）。不改冻结 DFG/L1/L2/L3 代码、语法、图与证据；不训练；不用 GPU。

## 背景（审查结论，写进 PROGRESS）
1. 冻结语法把成员后缀挂到左边整个二元表达式上：`a && msg.sender == owner` 被解析为 `(a && msg).sender == owner`，`msg.sender==owner && msg.sender!=newOwner` 被解析为 `((msg.sender==owner) && msg).sender != newOwner`。facts_boolean 只在条件含 `||`、或含 `&&` 且为负极性/含 `!` 时启用，正极性的合取仍走旧的 AST 路径，于是两者都不是发送者守卫。真实数据：buggy_2.sol、buggy_3.sol 的 changeOwner 中 `assert(msg.sender==owner && msg.sender!=newOwner)`（7 类的 SolidiFI 底稿中都有），其后的 `owner=newOwner` 被记成对授权变量的未受保护写入，K 组 unguarded_write_functions 多计 1。
2. `throw`（0.4.x 的语句关键字）在冻结语法中被解析为 expression_statement 中的 identifier，L2 报 state_name_missing；GLOBALS 未包含它，于是被分类为 uncertain_state_value：四个任务各 10/10/32/8 次（例如 etherbank.sol 的 `{ throw; }`、reentrancy_simple.sol 的 `throw;`、多处 `if(intitalized)throw;`），所在语句 state=unknown，并使所在合约全部状态声明的 K 读字段成为未知。
3. 汇总的未知没有使用三值逻辑：已经由确定证据得出的值仍被列入 unknown_fields。例如某声明已有确定的守卫内读取（read_in_guard=true）或确定的未受保护写入（unguarded_writer=true），只因同合约存在一个不确定访问就被标成未知。reentrancy_contract 中 410 个未知 K 行里，至少 300 余行的部分未知字段已经有确定值。
4. K 组未知的作用目标过宽：targets=None 的问题（未解析名字、名字歧义、别名使用、assembly）会使同一合约（含继承）的所有状态声明的相关字段未知。但一个未解析或歧义的名字只可能指向同名的声明；存储别名只可能指向引用类型（mapping、数组、struct、string、bytes）的声明；不含 sload/sstore/delegatecall/callcode 的 assembly 不读写本合约存储。
5. facts_cfg.apply_order 依赖 networkx 2.6.3 中 immediate_dominators 含有起点的行为；networkx ≥3.5 不再包含起点，dominates() 会 KeyError（我在 networkx 3.7 下复现）。服务器环境若不同会出错。

## 1. 合取与析取的统一处理（facts_boolean.py、facts_guards.py）
- 只要条件的顶层（去掉外层括号后）含有 `&&`、`||` 或前缀 `!`，就使用基于原 AST token 的布尔分组（现有 sender_condition 的 parse），与极性无关；否则沿用原路径。
- 合取（正极性的 &&，或负极性的 ||）：任一项是发送者相等比较即为发送者守卫，eq_pairs 取各发送者相等项的并集，disjunctive=false（除非某一项本身是析取型发送者守卫）；非相等项（!=、>、普通布尔量）不贡献组合，也不否定守卫。
- 析取规则保持 NS-P3a2 的定义不变。
- 一致性检查：对全部 Oracle 与四个任务中所有不含误解析的条件（AST 中不存在 object 为 binary_expression 的 member_expression），新旧两条路径的 (eq_pairs, is_sender_guard) 必须相同；报告不同的个数（应为 0）。
- 新 Oracle（先写期望）：
  oo) assert(msg.sender == owner && msg.sender != newOwner); owner = newOwner; → 规则 1，发送者守卫，eq_pairs=[env_state]，disjunctive=false；owner 是授权变量；该写入不计入 unguarded；
  pp) require(now > deadline && msg.sender == owner); x = 1; → 发送者守卫，eq_pairs=[env_state]；
  qq) require(paused && tx.origin == owner); x = 1; → 发送者守卫（tx.origin），eq_pairs=[env_state]；
  rr) if (b > 0 && msg.sender != p) { y = 1; } → 规则 2 正极性，不是发送者守卫（!= 不构成相等组合）。

## 2. throw（facts_state.py）
- 把 `throw` 加入不构成状态不确定的语言关键字/内置名集合（与 require、revert 同类）。
- 新 Oracle ss）：0.4.x 函数中 `if (!ok) throw; balances[msg.sender] = 0;`（balances 为本文件状态变量）与 `{ throw; }` → 所有语句 state=supported，同合约状态声明 K 组无未知字段。

## 3. 三值汇总（facts_summary.py）
按 Kleene 三值逻辑决定 unknown_fields：只有当不确定的贡献可能改变字段的值时，字段才是未知。
- 布尔“存在”型字段（K：read_in_guard、used_as_call_value_or_target、unguarded_writer；L：state_write、auth_write、sender_guard、write_then_call、call_then_write；M：auth_state）：已由确定证据得出 true 时为已知 true；确定证据为 false 且存在相关不确定性时才未知。
- 计数型字段：read_functions/write_functions 已为 "many" 时已知；unguarded_write_functions、auth_state_count 在有相关不确定性时仍为未知（数值可能增加）。
- only_constructor_writes：已有确定的非构造函数写入时为已知 false；否则按现规则。
- L 组 sender_guard：本函数已有确定的发送者守卫（自身 require/early-exit 或语句守卫）时为已知 true，即使其他语句的守卫未知。
- schema 校验增加：status=="unknown" 当且仅当 unknown_fields 非空。

## 4. K 组未知的目标（facts_state.py、facts_summary.py）
每个问题记录 targets（声明身份集合），K 组只对 targets 中的声明生效：
- 未解析名字/名字歧义/uncertain_state_value（来自 identifier）：targets = 该问题所在合约作用域内（含继承的本文件基类）与该标识符同拼写的状态声明；为空集时不影响任何 K 行（该名字指向文件外的声明）；
- unresolved_alias_use：targets = 作用域内引用类型（mapping、数组、struct、string、bytes）的状态声明；
- assembly_effect：只有块内出现 yul_evm_builtin 为 sstore、delegatecall 或 callcode 时视为写；出现 sload 时视为读；两者都没有时不产生状态问题；targets = 作用域内全部状态声明；
- file_fallback、unlocated_diagnostic：保持全作用域（保守）；
- 语句级 state.status 的判定不变（仍按语句自身的问题）。
- 新 Oracle tt）：合约有 `uint a; mapping(address=>uint) m;`，函数中有一个文件外基类成员 `inherited = 1;` → a 与 m 的 K 组无未知字段；uu）同一合约中 `Rec storage r = recs[i]; r.v = 1;` 且别名无法解析 → 只有引用类型声明（recs）的写字段未知，`uint a` 不受影响；vv）只含 `extcodesize` 的 assembly → 不产生状态问题。

## 5. 版本稳健性（facts_cfg.py）
apply_order 中求得 dominators 后执行 dominators.setdefault(ir.entry, ir.entry)，并加一个测试：对 networkx 返回不含起点的字典时结果不变（可用 monkeypatch 构造）。

## 6. 重新生成与比较
- 四个任务重新抽取到 accepted_attempt4/original/，与 accepted_attempt3 逐行比较。允许的变化：guards 的 eq_pairs/is_sender_guard/disjunctive、self_condition.eq_pairs、state.status、order.status、unresolved 中的诊断范围项、K/L/M 的 status、unknown_fields 以及因守卫与授权变化而改变的位（auth、unguarded_*、sender_guard、auth_write、auth_state*）、state 读写条目的 auth 位。读写变量/形状/数量、调用、环境、算术、语法、DFG 事实严格不变。
- 报告：每项修正分别影响的行数（守卫、throw、三值、目标）；四个任务修正前后 state/K/L/M 未知比例（分母同前）；buggy_2/buggy_3 changeOwner 的前后对照（源码 SHA、row_key）；一致性检查的不同个数。
- 重跑 5 类冒烟（原名，无图）：0 异常。

## 7. 测试与验收
全部 node_sem、dfg_v2 与原回归测试通过；facts_verify 对 accepted_attempt4 通过；CURRENT.json 指向 accepted_attempt4；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；提交 NS-P3a3。不推进 NS-P3b。
```

### 5.5b Prompt NS-P3b：M2 字段与编码、M3a 向量、CTX/STATIC 模态

```text
# NS-P3b：由 facts 生成 M2 上下文字段并编码（CTX）、生成 M3a 多热向量（STATIC），写成符合载体契约的模态

前置：NS-P3a3 通过审查。输入：CURRENT.json 指向的 artifacts/facts_v1/accepted_attempt4/original/<task_id>/facts.jsonl（facts v1.1，核对 SHA 与封存）与 text_v1 的原名视图。视图口径按 EXPERIMENT_POLICY.md：只生成 original，<view> 一律为 original，不读取匿名产物。不训练；编码使用 GPU 时必须先非阻塞检查 .training.lock。

**逐字段未知（v1.1）**：K/L/M 组的 unknown_fields 必须逐字段消费：字段在 unknown_fields 中时，M2 中该字段写 "unknown"，M3a 中该字段的取值位全为 0，并把该字段的未知位置 1；不在其中的字段照常编码，不得因为组 status=unknown 而清空整组。state/order/dfg/守卫的 status 仍按第 4.6 节的 N 组 5 个未知位处理。

## 1. M2 字段（scripts/node_sem/ctx_fields.py）
ctx_fields(facts_row, text_row, names="original") -> dict：按第 4.5 节的字段、顺序与适用节点生成；缺失写 "-"，不能判断写 "unknown"；相对距离写 @±k；FROM/TO 最多各 2 条，按 |offset| 排序。字段文本只用 facts 中的枚举值与 names，不得出现文件名、绝对行号或类别名。
- names="original"：变量名为原拼写（主输出）。
- names="masked"（名字泄漏对照，必须同时生成）：每个节点的字段文本中，变量名按“在本节点字段中首次出现的顺序”与声明角色替换为 STATE1、PARAM1、LOCAL1、ENV 等占位名（同一节点内同名同占位，不跨节点保持一致）；其余字段与 original 逐字相同。理由：原名下 SolidiFI 注入名（owner_txoriginN、_re_ent、_intou、_TOD、_tmstmp、bug_unchk_send 等）几乎直接给出标签，CTX 中的名字是否起作用需要这个对照来判断。是否在训练中使用由 NS-P5 计划决定。
输出 artifacts/ctx_v1/original/<task_id>/{ctx_fields.jsonl, ctx_fields_masked.jsonl} 与 manifest（行集合 = F3 全集，行顺序同 text_v1）。

## 2. 编码（nodesem，offline/encode.py 新增 --ctx 模式）
- 读取 ctx_fields.jsonl，拼成第 4.5 节的文本格式，用主编码器的 tokenizer 按第 4.5 节的截断顺序逐级截断到 256 token，再编码（与 M1 相同的模型、池化与精度）。
- 两种 names 各编码一份。输出 artifacts/ns_p3/encoded/original/<task_id>/emb_ctx_<model>.npz、emb_ctx_masked_<model>.npz 与对应的 CTX 模态 manifest：满足 carrier._load 契约（第 5.4 节 2b）；input_text 指向 ctx_fields.jsonl；implementation 至少含 facts.py、facts_schema.py、ctx_fields.py、encode.py、text_view.py；manifest 另记每级截断的节点数。
- 同一输入重复编码一次，逐位一致或最大误差 ≤1e-6（写明是哪一种）。

## 3. M3a（scripts/node_sem/static_profile.py 与 behavior_schema.json）
- behavior_schema.json：每个字段的组、名称、编码方式（独热/多热）、列区间、适用节点种类、“不适用”默认值；总维度由 schema 决定，不写死在代码中。N 组在第 4.6 节的 5 个未知位之后，为 K/L/M 中可能出现在 unknown_fields 的每个字段各加 1 个未知位（字段清单从 facts_schema 读取，不手写）。
- encode(facts_row) -> uint8 向量；explain(vec) -> 字段名列表，保证往返一致；每个独热组恰好一个 1。
- 输出 artifacts/ns_p3/static/<view>/<task_id>/static.npz（float32 0/1）与 STATIC 模态 manifest（满足载体契约；present 对全部行为 true；input_text 指向 facts.jsonl；implementation 含 facts.py、facts_schema.py、static_profile.py、behavior_schema.json）。
- 名字无关性：对 Oracle 源码做标识符双射改名后重新抽取 facts 并编码，static 向量逐位相同（I 组“仅大小写不同”位按还原映射计算）；ctx_fields_masked 逐字相同。

## 4. 测试
- schema：列区间不重叠且覆盖全部维度；每个组的适用节点种类与第 4.6 节一致；独热组恰好一个 1；encode/explain 往返；N 组未知位在对应 status=unknown（或字段在 unknown_fields 中）时为 1 且对应事实位为 0；字段不在 unknown_fields 中时，即使组 status=unknown 也照常编码（构造用例断言）。
- M2：每种节点种类的字段集合与第 4.5 节一致；截断各级都可触发且字段标签保留（构造超长样例）；没有文件名与绝对行号；masked 文本中除保留名与占位名外没有其他 identifier（全文本扫描）；unknown_fields 中的字段写 "unknown"。
- 生产者扰动：对 facts 生成器的输入图施加 (a)(b) 扰动后，ctx_fields 与 static 输出逐位相同。
- 载体：carrier.load_modality 对全部 CTX 与 STATIC manifest 通过；carrier.carry 对 S3（TOKEN 之外的 CODE+CTX）与 S4（CODE+CTX+STATIC）在 G0 与 G3R 上能装配，维度等于 FeatureSpec.carrier_dim()（只装配，不建模、不训练；FeatureSpec 配置文件在 NS-P4 登记，此处用临时 spec）。

## 5. 统计
按任务：每个 M3a 维度的取 1 比例（不按标签分组）；M2 各字段非空率与 "unknown" 比例；截断级别分布（original 与 masked 分别）；编码去重率与耗时。写入 artifacts/ns_p3/stats.json。

## 验收
测试与统计通过；PROGRESS、HANDOVER、training_changes 追加记录（doc_check --expect-cjk 通过）；提交 NS-P3b。
```

### 5.5b2 Prompt NS-P3b2：STATIC 补项与三值编码、CTX 参数来源标签（NS-P4 之前必须完成）

```text
# NS-P3b2：在 NS-P3b 产物基础上做三处修正，重新生成 STATIC 与 CTX 并重新编码

前置：NS-P3b（aa81bcde）。facts 不变（CURRENT 仍为 accepted_attempt4）。旧 ns_p3 产物只读保留；新结果写入新目录（例如 artifacts/ns_p3/attempt_b2/），全部验收通过后再更新 artifacts/ns_p3/CURRENT.json。视图按 EXPERIMENT_POLICY（original + masked 对照）。不训练；CTX 编码使用 GPU 时先非阻塞检查 .training.lock。

## 背景（审查结论，写进 PROGRESS）
1. NS-P3a 已批准并抽取的“一层检查运算”（checked_call：语句调用同文件唯一的内部/库函数，该函数做运算并检查结果）没有进入 STATIC 与 CTX。原因是我在第 4.5/4.6 节的表中漏列了它，不是实现错误。四个任务中 supported 且 result_condition_check=true 的行有 214/103/271/105（AC 合约/节点、重入合约/节点）。它是 STATIC 中唯一与名字无关地表达“经过检查的算术”（SafeMath 一类）的位，扩展到算术等其余类别时必需。
2. STATIC 对 B（状态访问）、C（顺序）、D/D1/D2（守卫）组在组 status 为 unknown 时把全部取值位清零。但这些组里的多热位是“存在”型事实：已由确定证据得出的 true（例如 CFG 支持下已证实的 call_then_write、已解析的发送者守卫、已投影的状态写）在不确定性下仍然为真。按 NS-P3a3 对 K/L/M 采用的同一三值规则，它们应保留为 1，同时置 N 组未知位。真实数据：order 未知且已有 true 顺序位的语句行 35/31/31/31（重入合约/重入节点/AC 合约/AC 节点）；守卫未知但已有确定守卫的行 2/2/7/2；状态未知但已有确定读写条目的行 10/7/13/7。
3. CTX 中参数的来源是函数入口，facts 中其相对距离为 None，被渲染成 "unknown"（例如 `USE recipient:param:unknown`、`FROM unknown: function withdrawReward(...)`）。这与“无法判断”的 unknown 混用；stats 中 FROM 的 unknown 率因此显示为 35%，其中真正因 L1 不支持而未知的只有 439/6635（reentrancy_node）。

## 1. STATIC（static_profile.py、behavior_schema.json）
- G 组新增 `arith.checked_by_helper`（多热单值）：checked_call.status=supported 且 result_condition_check=true 时为 1；适用节点同 checked_call 的适用种类（语句与函数）。
- N 组新增 `unknown.checked_call`：checked_call.status=unknown 时为 1，此时 checked_by_helper 为 0。
- 三值编码：B 组的多热位（write_indexed、write_scalar、read_indexed、write_auth、read_auth、array_size_change）、C 组全部位、D/D1/D2 组的多热位，在组 status 为 unknown 时仍按已有确定条目取值（true 保留为 1），同时置对应 N 位；D 组的 "none" 位在守卫未知时不得置 1；B 组的 write_count/read_count 独热组在状态未知时仍全为 0。schema 中把这一规则写成字段属性（例如 unknown_policy: "keep_true" / "zero"），encode 按属性执行，不在代码中按字段名分支。
- 维度由 schema 决定（预计 243 → 245）；记录新旧列名对照。
- 测试：新增用例覆盖 checked_by_helper（SafeMath 式 `c = a + b; require(c >= a); return c;` 的一层调用 → 1；同一函数被两个同名定义歧义 → 不计入）；顺序未知但 call_then_write 已证实 → C 位为 1 且 N.order 为 1；守卫未知且另有已解析的 require 发送者守卫 → D sender 位为 1、none 位为 0、N.guard 为 1。

## 2. CTX（ctx_fields.py）
- 来源语句是函数/构造函数/modifier/fallback 节点（参数的定义处）时，距离标签写 "entry"，不写 "unknown"；DEF/USE 中参数的来源同样写 ":entry"。只有来源节点确实缺失或无法定位时才写 "unknown"。
- stats 中把 "entry" 与 "unknown" 分开计数。
- original 与 masked 两套文本都重新生成并重新编码（与 NS-P3b 相同的模型、资产、池化、精度与截断规则；两遍逐位一致）。

## 3. 重新生成与验收
- 新 STATIC 与新 CTX 写入新目录；与旧产物逐行比较：STATIC 只允许新增两列与第 1 节三值规则涉及的列变化，报告每列变化行数；CTX 文本只允许 "unknown"→"entry" 的替换（逐行 diff 验证，其余字符完全相同），列出截断级别因此改变的行数。
- carrier 对新 STATIC/CTX 全部通过；S3/S4 在 G0 与 G3R 上装配维度等于 FeatureSpec.carrier_dim()。
- 全部 node_sem、dfg_v2 与原回归测试通过；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；提交 NS-P3b2。不推进 NS-P4。
```

### 5.6 Prompt NS-P4：融合、无图对照与 CPU 冒烟

```text
# NS-P4：concat/gated 融合、模态 dropout、layers=0、S2–S4-noG 配置与 CPU 冒烟

## 1. 融合（adapter.py）
- concat：对每个连续模态 m（CODE、CTX、STUDENT、TEACHER*）做 LayerNorm(d_m) → Linear(d_m,128)；STATIC 不做 LayerNorm，直接 Linear(d_static,128)；TOKEN_IDS（如果存在）走共享 EmbeddingBag 加本类型的 Linear(64,128)。输出 h = Σ_m p_m · z_m + b（共享偏置 b，各 Linear 不带偏置）。
- gated：z_m 的计算同上；logits = W_g [p_1 z_1; …; p_M z_M]（Linear(M·128, M)）；p_m=0 的 logit 置为 −inf；全部缺失时 h=b；否则 g = softmax(logits)，h = Σ g_m z_m + b。last_gates 保存为 detach 后的 CPU 张量。
- 模态 dropout：只在 self.training 时生效。每次 forward 用一个 CPU torch.Generator 生成伯努利掩码（种子 = parameter_seed(fit 种子, "modality_dropout", [task_id, fold, profile, spec_digest]) 加上当前 forward 计数），再移到设备上。掩码作用在存在位上。全局随机数不受影响。
- 参数初始化按第 4.9 节；参数名稳定（例如 adapt_ws.3.proj.CODE.weight），写进测试。

## 2. layers=0
spec.layers=0 时，make_nodesem_model 传 layers=0 给 make_model。按 NS-P0 实验 C 的结论确认：作者 forward 可以直接使用；只在 G0 上使用；节点任务与合约任务都能前向和反向。

## 3. 配置登记
configs/S2.json、S3.json、S4.json、S4g.json、S4-noG.json（视图按 EXPERIMENT_POLICY：original；CODE 与 CTX 用主编码器），以及名字对照 S3m.json、S4m.json（CTX 用 ctx_masked，其余相同）。记录每个配置的 carrier_dim，以 FeatureSpec.carrier_dim() 与 NS-P3b2 后的 behavior_schema.json 为准（NS-P3b2 后 S3=514、S4=760）。
- 原名基线配置（EXPERIMENT_POLICY 为原名时，配对基线必须与特征视图一致）：登记 configs/S0o.json、S1o.json，TOKEN_IDS 取原名视图的 token ID（图上原有的、未经 8G 改名的 token 属性；必须核对其来源与 SHA，不从匿名特征反推）。CPU 核对：S0o 的载体与原图 token 属性逐位相同；S0o 构造出的模型除输入特征外与 8H 的 S0 初值逐位相同。找不到可核验的原名 token 来源时停下报告，不自行生成。正式是否运行 S0o/S1o 由 NS-P5 计划决定。

## 4. CPU 证明与冒烟（不是正式训练）
在 reentrancy_node fold0 上（G3R；S4-noG 用 G0）：
- 每个配置构造模型、加载初值、调用 benchmark_v2.trainer.fit 跑 1 个 epoch（config 只把 maximum_training_epochs 改为 1，写明这是冒烟配置），记录：loss 是否有限；新模块参数是否有非零梯度；gcs/classify 初值是否与 8H 相同；构造耗时；载体维度；按张量大小估算的显存。
- gated：每个节点的门控权重之和为 1（误差 ≤1e-6）；全部缺失时输出等于偏置，没有 NaN。
- 模态 dropout：p=1 时所有存在位为 0，输出等于偏置；p=0 时与关闭 dropout 逐位相同；同一 fit 种子两次运行逐位一致。
- 构造耗时：如果 S4 的构造时间超过 8H 构造时间的 3 倍，在 PROGRESS 中报告；不要自行修改 get_node_token。

## 4b. GPU 显存探针（需要用户授权；1 个 epoch；不计入正式结果）
8H 中 reentrancy_contract G3R 的整卡最小空闲只有 44 MiB。授权后，在 local_dev_v1 下、持有同一把 .training.lock，对 reentrancy_contract fold0 G3R 的 S1 与 S4 各跑 1 个 epoch，记录 peak allocated/reserved 与整卡最小空闲。任何一项 OOM 或最小空闲低于 100 MiB，就停下报告，不要自行降配。

## 5. 测试
- concat 的线性等价：把各模态拼接后做一次 Linear，结果与 Σ p_m z_m 逐位相同（不做 LayerNorm 的情形）；
- gated 的掩码与归一化；
- dropout 的确定性与“只在训练模式生效”；
- 参数名稳定；
- layers=0 的前向与反向。

## 验收
测试与冒烟通过；PROGRESS.md 记录每个配置的 D、构造耗时、冒烟结果；提交 NS-P4。
```

### 5.6b Prompt NS-P4b：GPU 功能验收（相对门槛）与 dropout 种子修正（NS-P5 之前必须完成）

```text
# NS-P4b：修正显存门槛、补完 GPU 验收、dropout 种子按节点类型区分

前置：NS-P4（3b132618）。ns_p4/attempt2 只读保留（包括 S1o 中止现场）；新结果写入 ns_p4/attempt3/。不登记正式实验，不改 HGT、训练器、图、特征与 8H。

## 背景（审查结论，写进 PROGRESS）
1. NS-P4 第 4b 节“整卡最低空闲低于 100 MiB 即停止”是我的门槛设定错误：8H 的 S0 在 reentrancy_contract/G3R 的 5 折上 peak reserved 为 2094 MiB、最低空闲 44–74 MiB，按这个门槛 8H 本身也会被判失败。S1o 的 peak allocated 1853 MiB、peak reserved 2074 MiB，均不高于 8H S0 的 1895/2094 MiB，说明 S1o 没有显存回退；停止原因是门槛不合理，不是实现问题。Codex 按规则停止、不重试、保留现场的做法正确。
2. 在本机 4 GiB 卡上，CUDA/DGL 上下文初始化即占用约 1244 MiB；S4 的输入宽 760（8H 为 512）并多出约 1.1M 参数，在 reentrancy_contract/G3R 上大概率超过本机余量。本机能验证的是 GPU 路径的功能正确性，全尺寸显存需求要在服务器上测量。
3. adapter.reset_dropout 的种子是 parameter_seed(fit_seed, "modality_dropout", [task, fold, profile, spec_digest])，不含节点类型；所有节点类型的适配器在同一 forward 计数下生成完全相同的伯努利序列，不同类型中行号相同的节点被同时保留或丢弃。这是我在 NS-P4 中给的种子定义遗漏了 ntype。

## 1. dropout 种子（adapter.py）
- 种子改为 parameter_seed(fit_seed, "modality_dropout", [task_id, fold, profile, spec_digest, ntype])。
- 测试：两个不同 ntype 的适配器在同一 forward 计数下掩码不同（构造足够行数断言不全相同）；同一 ntype 两次运行逐位相同；评估模式不推进计数；全局 RNG 不受影响。
- 重新运行 NodeSem 全部测试；CPU 冒烟只对含 dropout 的多模态配置（S3、S3m、S4、S4g、S4m、S4-noG）在 reentrancy_node fold0 上各重跑 1 epoch，写入 attempt3（旧结果保留，不比较 loss 大小）。

## 2. 显存门槛（p4_acceptance.py 的 GPU 模式）
- 去掉绝对 100 MiB 门槛。硬停止条件只有 OOM（或 CUDA 错误）。
- 相对比较：对同一任务/折/图配置，读取 8H 的 resources.csv（S0 的 peak_allocated、peak_reserved、minimum_free），报告 NodeSem 配置的差值；peak_reserved 超过 8H 的 1.25 倍时在报告中标为“显存需求明显增加”，不停止。
- 启动前空闲仍须 ≥3000 MiB（保证没有其他进程占卡），否则不启动并报告。

## 3. GPU 验收（1 epoch，非正式，持有 .training.lock）
- reentrancy_node fold0 G3R：S1o、S2、S4、S4g、S4m；S4-noG 用 G0。每项完成 1 epoch 训练、best/last 保存、inner_val/outer_test 评分与重载一致性验收（与 CPU 验收相同的检查）。
- GPU/CPU 一致性：对 S4 与 S4g，用同一初值在 eval 模式下各做一次前向（CPU 与 GPU），logits 最大绝对差 ≤1e-4（相对 ≤1e-4），并核对 last_gates 在 CPU 上、每行和为 1。
- reentrancy_contract fold0 G3R：S1o 与 S4 各 1 epoch，用于测量显存（第 2 节的相对报告）。S4 若 OOM，记录发生阶段与当时的 allocated/reserved，标为“需服务器测量”，不降配、不重试。
- 报告表：每项的 peak allocated、peak reserved、最低空闲、与 8H S0 的差值、耗时。

## 4. 验收
NodeSem、dfg_v2 与原回归测试通过；reentrancy_node 上的 GPU 功能验收全部通过（这是本步通过的必要条件）；reentrancy_contract 的显存结果如实记录（OOM 不算失败，但必须写入 NS-P5 的资源前提）；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；提交 NS-P4b。不推进 NS-P5。
```

### 5.7 Prompt NS-P5：批次 N-A 的计划与封存（不训练）

```text
# NS-P5：N-A 计划（原名视图；{S0o,S1o,S2,S4} × {G0,G3R} × 30 折 = 240 次新 fit）

依据：PROMPTS r16 第 4.12 节与 EXPERIMENT_POLICY（原名为主）。匿名 8H 的 S0 不复用、不作配对基线，只在报告中作为历史参考。

## 1. 准备
- 为每个（配置、任务、图配置）写好载体 NPZ 与 manifest：S0o/S1o 用原名 token ID（核对与图上原 token 逐位相同），S2/S4 用 NS-P3b2 的 CODE/CTX/STATIC（ns_p3/CURRENT）；核对行身份与 SHA。
- 为 240 个 job 生成零步初值（node_sem.init）：S0o 与 8H 的 S0 初值逐位相同（参数相同、只有输入不同）；其余配置共同参数与 8H 相同。记录文件 SHA 与 state SHA，在 CPU 上逐个构造并核对 digest。
- 每个 job 的 dropout 身份（fit_seed、task、fold、profile、spec_digest、ntype）可由 plan 复现。

## 2. plan（排他创建 artifacts/batch_NA_v1/）
- job：task_id、fold、seed=1、profile、spec（引用与 digest）、图引用、label_view（L-audit）、folds、初值、载体、config（与 8H 相同）、设备类型。
- 预先登记（写进 plan，以后不能改）：
  - 主终点：reentrancy_node、G3R、S4 − S0o，L-audit best 外层 BF1，10 折配对，双侧 Wilcoxon；
  - Holm 家族（reentrancy_node、G3R）：S4−S0o、S1o−S0o、S2−S0o、S4−S2；
  - 交互项（描述）：(S4−S0o)_G3R − (S4−S0o)_G0，并附第 3 节第 21 条的解读说明；
  - 必报描述项：每个配置的 SolidiFI/非 SolidiFI 分层（BF1、TP/FP/FN、Wilson 区间；分层只按文件名前缀 buggy_，不读标签）；重入另附 32 个非 SolidiFI 正例与全部非 SolidiFI 误报的逐节点概率表，访问控制附 20 个非 SolidiFI 正例的逐节点概率表；天花板说明中的逐折错误数与相对错误减少率；匿名 8H S0 的成绩只作历史参考列；
  - S* 选择规则：inner_val best BF1，先在折内平均，四个任务等权；在 S1o/S2/S4 × G3R 中选择；平局时取载体维度更小的；
  - 报告必含项：第 4.12 节全部。
- 设备：plan 写明每个比较族使用的设备类型（本机 RTX3050 或服务器，二者不能混用于同一比较）；记录 allow_tf32（matmul、cudnn）的取值，训练时不改动默认设置，但每个 receipt 记录实际值与 GPU 型号。
- 资源前提（NS-P4b 实测）：reentrancy_contract/G3R 上 S4 的 peak reserved 2194 MiB、最低空闲 44 MiB（8H S0 为 2094/44–74 MiB），本机可运行但没有余量。硬停止只在 OOM/CUDA 错误；若 N-A 中任一 fit OOM，整批停止并报告，由用户决定是否把该任务的全部配置移到服务器重跑（不得只把 OOM 的配置挪走）。
- runtime：_code_refs() ∪ node_sem 代码 SHA。
- 估算本机耗时与显存（依据 8H 的实测与 NS-P4b 的单轮数据；S0o/S1o 约同 8H，S4 每 fit 约为 8H 的 1.1–1.5 倍）。

## 3. 授权模板
authorization.template.json（execution_authorized=false；需要用户填写：标签方案 L-audit、seed=[1]、运行位置（本机或服务器）、资源策略 local_dev_v1、视图 original）。停下等用户授权。

## 测试
plan/seal 篡改检测；载体或初值 SHA 改变时拒绝；runtime 变化时拒绝启动；同一比较族出现不同设备类型或 TF32 设置时拒绝汇总。

## 验收
plan 与 seal 封存，PROGRESS.md 记录耗时与显存估计；提交 NS-P5。不训练。
```

### 5.8 Prompt NS-P5A：执行 N-A 并报告（用户授权后）

```text
# NS-P5A：执行 N-A

0. 正式 worker（r17）：NS-P5 的 plan 没有绑定执行入口（旧 execution.py 只接受匿名 S0/S1，必须继续拒绝本 plan）。新增 scripts/node_sem/batch_na_worker.py，复用 NS-P4/P4b 已验收的 run_fit 核心路径（构造 → 载体与初值核验 → FitInputGuard → 冻结 trainer.fit → best/last 评分与重载），但：
   - 不得覆盖 maximum_training_epochs、patience、学习率或任何训练配置；effective_config 必须与 plan 中该 job 的 config 逐字段相同（测试断言，冒烟用的 maximum_training_epochs=1 不能出现在正式路径中）；
   - 初值只从 plan 引用的零步文件读取，核对文件 SHA 与 state digest；
   - 每个 receipt 记录实际 GPU 型号、torch/CUDA 版本、allow_tf32（matmul、cudnn）、显存峰值与最低空闲（local_dev_v1：低于 100 MiB 只标 memory_tight，不停止；OOM/CUDA 错误停止整批）；
   - 写一份执行修订记录 artifacts/batch_NA_v1/execution_revision.json（排他创建）：绑定 plan 与 seal SHA、worker 及其新增依赖的源码 SHA，并证明 plan.runtime 中的全部模型/训练/特征源码 SHA 在执行时不变；已封存的 plan 与 seal 不改。
   - 先在 CPU 上做 worker 自检（独立目录，不计入正式结果）：reentrancy_node fold0 G3R S4，只在自检中把 maximum_training_epochs 设为 1（与 p4_acceptance.run_fit 相同），证明两者的 history、best/last 参数摘要与预测逐位相同；然后用测试证明正式调用路径中不存在这一覆盖。
0b. 耗时优化（只去掉重复的校验与验收专用步骤，不改变任何训练计算、随机数或结果）：
   - 载体：NS-P5 的准备阶段已为 32 个（任务、图配置、配置）组合写好并深度核验了载体（锚点、逐行 SHA、来源与代码 SHA）。正式 worker 直接读取该载体矩阵：核对 NPZ 文件 SHA、manifest SHA、图指纹与行顺序各一次，然后写入图副本的 token 属性；不在每个 fit 中重复 _anchor_gate、assemble、逐行 SHA 与多次深拷贝/指纹。开训前对 32 个组合各做一次证明：读取的载体与 carrier.carry() 现算的结果逐位相同（只需构造，不训练）。
   - 初值：只核对 plan 引用的零步文件 SHA 与 state digest；与 8H 零步状态的逐张量比较已在准备阶段完成并封存，不在每个 fit 中重复。
   - 正式 worker 不包含验收专用步骤：梯度审计 hook、零步 CPU/GPU 一致性前向、TF32 诊断、额外的阶段性 eval。保留 8H 协议中的全部步骤：每个 epoch 的 inner_val 评估（早停与 best 选择需要）、best/last 保存与重载一致性检查、outer_test 评分与收据。
   - 输出：每个 epoch 一行进度即可（时间、epoch、loss、inner_val loss）；不写大段调试输出。预测文件按 8H 的格式写一次，不重复写。
   - 执行顺序（写入 execution_revision，不改 plan 与 seal；每个 fit 是独立进程、种子固定，顺序不影响结果）：先运行主终点与 Holm 家族所需的 reentrancy_node × G3R × {S0o, S4, S2, S1o}（40 个），再运行其余任务与 G0。这样即使后续中断，主终点也最先完成。
   - 计时：每个 fit 的收据记录各阶段耗时（启动、载体、构造、初值、训练、评分、写出）；完成 reentrancy_node 的前 4 个 fit 后，按实测外推整批耗时并写入 progress.json。
0c. 后台运行与中断恢复（训练不依赖 Codex 会话或网络）：
   - 启动方式：由一个控制器进程串行调度全部 fit，用 setsid nohup（或 tmux 会话）启动，与 Codex 的会话、终端无关；控制器把 pid、当前 job、已完成数、最近一次心跳时间写入 artifacts/batch_NA_v1/controller_status.json（原子替换）。Codex 断开或退出不影响训练；重新连接后只读这些文件了解进度。训练过程不访问网络（编码向量已预先生成，不下载模型，不推送 GitHub）。
   - 恢复：控制器重启时只读核对已有成功收据（verify），从下一个未完成的 job 继续，不重跑已成功的 fit。
   - 被外部中断的 fit（进程被终止、机器睡眠或断电，日志中没有 Python 异常或 OOM）：按 8H 的 attempt_00k 规则处理。如果用户在授权中预先同意“外部中断的 fit 从封存零步初值重新开始一次，作为新的 attempt”，控制器可以自动执行一次；否则停下等用户批准。数值错误、OOM、输入或校验失败一律停止，不自动重试。
   - 防睡眠：8H 第一次运行在 71/170 处因 Windows 睡眠约 80 分钟而中断。开训前检查并在报告中记录：笔记本接通电源；Windows 电源计划的睡眠与休眠在训练期间设为“从不”（或使用等效的保持唤醒工具）；保持一个 WSL 终端（例如 tmux 会话）打开，避免 WSL 在没有终端时关闭虚拟机。这些是用户侧的设置，控制器只做检查与提醒，不修改 Windows 设置。
1. 把用户授权原文写入 artifacts/batch_NA_v1/authorization.json（排他创建），绑定 plan、seal 与 execution_revision 的 SHA，写明 job 数为 240（原名视图，不复用匿名 8H）、运行位置与设备族（按用户已批准的方案：本机 RTX3050 为本批的设备族，服务器另建批次）。
2. 开训前证明：
   - 用新 plan 重新执行 NS-P1 的 S0 等价检查（CPU，2 epoch），并对 S0o 核对其初值与 8H S0 逐位相同、载体与原图 token 逐位相同，作为回归；
   - 试点：完整跑 2 个正式 fit（reentrancy_node fold0 G3R S4；reentrancy_contract fold0 G3R S4，后者用于确认完整训练的显存），记录耗时、显存与 TF32 设置。试点结果计入正式产物，不重跑。
3. 按 plan 顺序串行运行剩余 fit，每项一个独立子进程。失败就停，保留现场；重试必须经用户批准（沿用 8H 的 attempt_00k 规则）。运行中只记录进度，不汇总任何 F1。
4. 完成后：verify 240/240；核对全部 receipt 的设备类型与 TF32 设置一致。
5. 报告（node_sem/reporting.py，复用 benchmark_v2.reporting 的 wilson、scored、stratified_score 与 experiment/stats.py）：
   - 先只按 inner_val 选出 S*（封存 selection.json），然后才读取 outer_test；
   - 主表：四个任务 × 配置 × 剖面的折均 BF1；SolidiFI/非 SolidiFI 分层表；匿名 8H S0 历史参考列（不做配对检验）；
   - 主终点与 Holm 家族（差值均值、95% bootstrap 区间、提升/持平/下降、A12、Wilcoxon 原始 p 与 Holm 校正后的 p）；
   - 交互项；
   - 第 4.12 节的全部必含项，包括注意力饱和诊断：对 S0o、S1o、S2、S4 × G3R 的 best checkpoint 各做一次 eval 前向，统计第一层每个关系 head 最大权重 ≥0.99 的比例（方法同 dfg_v2/attention_probe.py）；
   - 报告首页写明：本批全部在本机 RTX3050 设备族（TF32 默认开启）上完成，是按预先登记分析的本机批次；服务器批次将另行封存、使用同一预先登记，作为复现报告；两者不合并、不择优，结论不一致时两者都报告；
   - 写 artifacts/batch_NA_v1/reports/REPORT.md 与 report.json，以及 scripts/node_sem/NS_P5A_REPORT.md。然后停下。
```

### 5.9 Prompt NS-P6：批次 N-B

```text
# NS-P6：N-B（S3 × G3R、S4g × G3R、S4-noG（G0，layers=0）、S4m × G3R；四个任务，共 120 次 fit）

流程同 NS-P5 + NS-P5A：先计划与封存（artifacts/batch_NB_v1/，排他创建），停下等用户授权，再执行与报告。

## 1. 计划
- 配置：S3（CODE+CTX，concat）、S4g（CODE+CTX+STATIC，gated）、S4m（与 S4 相同，但 CTX 用 ctx_masked）均在 G3R；S4-noG 在 G0、layers=0。特征来自 ns_p3/CURRENT（NS-P3b2），载体与初值按 NS-P5 的方法准备并深度核验；S4m 的 CODE 仍为原名，必须在计划中写明。
- 训练配置、折、标签（L-audit）、seed=1、初值规则与 N-A 完全相同；设备族必须与 N-A 相同（本机 RTX3050、torch 1.8.1+cu111、TF32 默认开启），否则拒绝与 N-A 比较。
- 执行沿用 N-A 已验收的 batch_na_worker 与 batch_na_controller（载体快路径、无训练配置覆盖、tmux/setsid 后台、心跳、从已验证收据恢复、外部中断最多重跑一次需用户在授权中同意）；用执行修订记录绑定，不改 N-A 的任何文件。开训前重做电源检查。
- 顺序：先 reentrancy_node（40 个），再其余任务。
- 预先登记的比较（全部只作描述，不做 Holm）：S4−S3、S3−S2（S2 引用 N-A）、S4g−S4、S4−S4-noG（并另报 S4-noG 与 G0 上 S4 的比较）、S4−S4m。
- 事后描述项（r19，依据 N-A 结果加入，在计划中明确标为“事后、只作描述、不参与任何结论的显著性判断”）：S3−S2、S4g−S2、S4m−S2，以及 N-A 中的 S4−S1o、S2−S1o；每项都按 SolidiFI/非 SolidiFI 分层报告 pooled TP/FP/FN 与 BF1，重入节点与访问控制节点另附非 SolidiFI 正例（32/20 个）的逐节点概率对照（同一节点在各配置下的预测）。
- 报告另加：S4g 按节点类型的门控权重均值与分布（只统计有可用模态的行）；S4g 与 S2 在 CODE 门控权重上的关系（门控是否把权重几乎全部给 CODE）。
- 引用 N-A 结果时按 receipt SHA 只读核对。

## 2. 授权与执行
写 authorization.template.json（execution_authorized=false），停下等用户。授权后按 N-A 的方式执行、验收（120/120 收据逐一核验）与报告；写 NS_P6_REPORT.md；更新 PROGRESS、HANDOVER、training_changes（doc_check 通过）。完成后停下，不进入 NS-P7。
```

### 5.9c Prompt NS-P6c：记录更正与模态贡献诊断（只做评估，不训练）

```text
# NS-P6c：N-A 权重缺失原因更正、保留规则，以及 CTX/STATIC 贡献的只读诊断

前置：NS-P6（a112d2bc）。不训练、不更新任何参数、不改 N-A/N-B 的 plan、seal、收据、预测与报告；新结果写入 artifacts/ns_p6c/（排他创建）。GPU 只用于 eval 前向，先非阻塞检查 .training.lock；也可全部用 CPU。

## 1. 记录更正
- 用户已说明：N-A 的 480 个 best.pt/last.pt 是用户本人为节省空间主动删除的。在 HANDOVER、PROGRESS、training_changes 与 NS_P6_REPORT.md 末尾追加更正（只追加，不改旧文字）：缺失原因 = 用户主动删除；N-A 的结果由收据、预测与指标（均有 SHA）保存，不受影响；N-A 的注意力诊断已在删除前完成并封存；以后不能重载 N-A 模型，服务器批次将重新训练。
- batch_NB_v1/historical_weight_availability.json 不改；另写 artifacts/ns_p6c/na_checkpoint_note.json 记录用户说明原文与时间。

## 2. 权重保留与 Git 体积规则（写进 HANDOVER 的固定规则）
- N-B 的 best.pt 在本 Prompt 的诊断完成前必须保留；诊断完成后可由用户决定删除。删除前生成 SHA 索引（路径、大小、sha256），删除后在报告中注明。
- 以后提交到 Git 的只有代码、计划/封存、收据、报告与 SHA 索引；逐行载体 manifest、百万行索引等可重新生成的大 JSON 不再提交，改为提交其 SHA 与生成命令。不改写已有历史；报告当前 .git 体积。

## 3. 诊断（使用 N-B 的 S4g 与 S4、N-A 不可用的部分不做）
所有统计按（任务、折、模型）分别计算再汇总；同一节点在不同折重复出现，不当作独立样本。

3.1 有效贡献（S4g，G3R，30 个模型）
- 对每个节点类型、每个模态 m，计算 g_m · ‖P_m(x_m)‖（门控权重 × 投影后向量的 L2 范数），以及它占三项总和的比例；与只看 g_m 的结果并列报告。说明：门控权重不等于贡献。

3.2 推理时移除（S4g 与 S4，G3R，各 30 个模型）
- 四种输入：完整；去掉 CTX；去掉 STATIC；两者都去掉（只留 CODE）。“去掉”= 把该模态的存在位置 0（与训练时 modality dropout 的处理一致，不是填零向量后仍标为存在）。
- 报告每种情况下 outer_test 的 BF1、离散预测改变的节点/合约数、概率的平均绝对变化；单列重入节点 32 个、访问控制节点 20 个非 SolidiFI 正例与非 SolidiFI 误报的变化。
- 判读规则（预先写入报告）：若去掉 CTX 与 STATIC 后预测几乎不变（改变 < 0.1% 的节点且非 SolidiFI 正例无变化），则模型在功能上没有使用这两种输入。

3.3 冗余探针（不需要模型）
- 对每个 STATIC 位（只取在该任务中取 1 比例在 1%–99% 之间的位），在每个外层折的 inner_train 上用 CODE 向量拟合 L2 逻辑回归（正则系数在 inner_val 上从 {0.01,0.1,1,10} 选），在 outer_test 上报告 AUC 与平衡准确率；同样用 CTX 向量做一遍。
- 汇总：AUC ≥ 0.95 的位数与比例，按 4.6 节的组（A–N）列出。这回答“STATIC 的信息是否已经包含在 CODE/CTX 中”。

3.4 非 SolidiFI 信号探针（不需要模型）
- 只在非 SolidiFI 的节点上（重入、访问控制两个节点任务），按同样的外层折，用逻辑回归比较三种输入：CODE、STATIC、CODE+STATIC；报告 outer_test 的 AUC 与 BF1（阈值在 inner_val 上选），以及 CODE+STATIC 相对 CODE 的逐折差。样本很小，只作描述。

## 4. 报告与验收
- 写 artifacts/ns_p6c/REPORT.md 与 report.json、scripts/node_sem/NS_P6C_REPORT.md；第一段直接回答：门控在机制上是否工作（3.1）、模型在功能上是否使用了 CTX/STATIC（3.2）、STATIC 是否与 CODE 冗余（3.3）、非 SolidiFI 上 STATIC 是否有额外信号（3.4）。
- 每个模型读取前核对 best.pt 的 SHA 与 state digest；前向前后参数摘要不变；eval 模式；不写回任何 N-B 文件。
- 新增测试：存在位置 0 与 modality dropout 的行为一致；贡献计算在构造数据上与手算一致；探针的折划分只用该外层折的 inner_train/inner_val。
- 全部 NodeSem 测试通过；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；本地提交。完成后停下，不进入 NS-P7。
```

### 5.9c2 Prompt NS-P6c2：冗余探针按适用节点重算（CPU，只做评估）

```text
# NS-P6c2：修正 STATIC 冗余探针的人群，并补非 SolidiFI 信号探针的敏感性分析

前置：NS-P6c（684b8c39）。ns_p6c 产物只读保留；新结果写入 artifacts/ns_p6c2/（排他创建）。只用 CPU，不加载任何 HGT 模型，不训练。复用 p6c_core.logistic_probe、split_indices 与同一折、同一 C 网格、同一 seed，不改它们。

## 背景（审查结论，写进 PROGRESS）
1. p6c_probes.run 的冗余探针在“CODE 与 STATIC 都存在的全部行”上拟合，取 1 比例也在全部行上计算。但 behavior_schema.json 中多数字段只适用于部分节点种类（A–D、F–H：statement/condition；K：state_decl；L：function/modifier；M：contract；I：statement/condition/function/modifier），在不适用的行上恒为 0。于是对这些位，AUC 很大一部分来自“CODE 能否认出节点种类”（例如区分状态声明与语句），不是“CODE 是否包含该语义事实”。这是我在 NS-P6c 中没有规定人群造成的遗漏。
2. CTX 文本本身就是由同一套 facts 生成的（STATE_R/W、CALL、GUARD 等字段），CTX→STATIC 的高 AUC 是构造使然，不能作为冗余证据，只能作为 CTX 编码保真度的检查。
3. NS-P6c 第 1 段中的 S4 属于 N-A（模型已删除），只评估 S4g 的处理正确；那是我在 NS-P6c 中的表述错误。

## 1. 冗余探针（按适用节点）
- 对每个 STATIC 位，人群 = 该字段 schema.applicable 中的节点种类且 CODE 与 STATIC 均存在的行；取 1 比例在该人群内计算，只保留 [1%,99%] 的位。
- 其余设置与 NS-P6c 相同（inner_train 拟合与标准化，inner_val 选 C，outer_test 评分；单类别折记为不可估，不借测试集）。
- 只对 CODE 做主分析；CTX 作为“编码保真度”单列，并在表头注明“CTX 由 facts 生成，此项不是冗余证据”。
- 额外对照：在同一人群上，用“节点种类独热 + 语法种类（syntax 字段）”作为输入的探针 AUC。报告 CODE 相对这一对照的 AUC 差，以说明 CODE 是否包含超出节点/语法种类的信息。
- 报告：按 A–N 父组与原子组，列出合格位数、可估位数、AUC≥0.95 的位数与比例、折均 AUC 的中位数；与 NS-P6c 的全部行结果并排，标明差别。

## 2. 非 SolidiFI 信号探针的敏感性分析
- 先报告重入节点 32 个、访问控制节点 20 个非 SolidiFI 正例的节点种类分布。
- 在原分析之外，另做只含 statement/condition 节点的版本（其余设置不变），比较 CODE、STATIC、CODE+STATIC 的 AUC 与 BF1；同样只作描述，可估折单列。

## 3. 验收
- 测试：人群筛选与 schema.applicable 一致；取 1 比例在人群内计算；对照输入的列只来自节点种类与语法字段；所有拟合只用该外层折的 inner_train/inner_val。
- 写 artifacts/ns_p6c2/REPORT.md、report.json 与 scripts/node_sem/NS_P6C2_REPORT.md；第一段直接回答：按适用节点计算后，CODE 能线性预测的 STATIC 位比例是多少、哪些组明显不能被 CODE 预测；非 SolidiFI 上 STATIC 的信号在只含语句节点时是否仍然存在。
- 全部 NodeSem 测试通过；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；Git 只提交代码、报告、紧凑汇总与 SHA 索引；提交后停下，不进入 NS-P7。
```

### 5.10 Prompt NS-P7：M3b LLM 行为描述（本机试点 → 全量），不训练

```text
# NS-P7：LLM 行为描述管线、教师向量与只读诊断

前置：NS-P6c2 审查通过（PROMPTS r22/r23）。依据第 4.7 节。facts 用 CURRENT（accepted_attempt4），文本与行身份用 text_v1 原名视图，STATIC/CTX/CODE 用 ns_p3/CURRENT。本 Prompt 不训练 HGT、不训练学生（学生与 N-C 在 NS-P8）。所有输出排他创建在 artifacts/llm_v1/；失败保留现场、不自动重试（除第 3 节规定的一次 JSON 重试）。

## 0. 用户准备与资产登记
- 用户提供：一个 3B 级代码指令模型的 GGUF Q4 文件（建议 Qwen2.5-Coder-3B-Instruct Q4_K_M），以及在 nodesem 环境中可用的 llama-cpp-python（CUDA 版）或 llama-server。把路径告诉 Codex；不自行从网络下载模型。
- Codex 用 offline/asset_registry.py 登记：GGUF 文件 SHA、大小、许可证文本位置、llama.cpp/llama-cpp-python 版本、编译选项（是否 CUDA）、运行参数（n_ctx 4096、n_gpu_layers、temperature 0、top_k 1、seed 0、batch 大小）。bge-small-en-v1.5 已在 NS-P2 登记（commit 5c38ec7c…），直接复用并核对 SHA。
- 使用 GPU 时必须持有 .training.lock（与 HGT 训练互斥）；不得与训练同时占用 4 GiB 显存。

## 1. 提示输入（mando 环境，llm_inputs.py）
- 单位：每个 function、constructor、modifier、fallback/receive（按 facts.node_kind 与 AST 判定）。四个任务的源文件取并集（约 254 个文件、约 6900 个函数单元，其中非 SolidiFI 约 3000 个，以实际统计为准），每个单元只生成一次提示，按任务记录引用关系。
- 源码：原名源码（核对 source SHA）；按第 4.7 节把 comment 字节范围替换为等长空白，重新解析确认 ERROR=0、MISSING=0；渲染提示时去掉只含空白的行，行号映射以替换后的源码为准。
- 改名：函数内与该合约状态变量声明中的全部非保留标识符（变量、参数、函数名、事件名、合约名、用户类型名、modifier 名）按首次出现顺序改为 a1, a2, …；同一合约的状态变量与函数共用一张编号表；保留名使用 NS-P2 的 reserved 集合。字符串与数字字面量不改。
- 每行加函数内相对行号前缀 "L<k>| "；要描述的行 = 该函数内除 end_if、end_loop 与函数定义本身以外的 HCG 节点（复用 NS-P3b 的 ctx_alignment 得到节点 AST 起点，换算成相对行号）；函数节点本身对应 function_intent。
- prompt_map：{相对行号: [row_key…]}、{a_k: 原名}，与提示一起保存（原名只在 prompt_map 中，绝不进入提示）。
- 超过 120 行的函数按 60 行分段，每段附签名；记录分段。
- cache_key = sha256(模板版本 + 模型资产 SHA + 运行参数 + 提示全文)；按 cache_key 去重（SolidiFI 模板函数会大量重复），记录去重率。
- 输出：llm_v1/inputs/units.jsonl（每个唯一提示一行）、llm_v1/inputs/<task_id>_rows.jsonl（row_key → cache_key、相对行号）与 manifest（函数数、去重数、行数与 token 数分布、分段数）。
- 测试：
  - 改名是双射，按 prompt_map 还原后与去注释的原函数逐字一致；
  - 提示中的 identifier 只允许保留名与 a_k（全文扫描）；没有文件名、绝对行号；SolidiFI 标记子串（re_ent、txorigin、intou、tmstmp、TOD、unchk、bug_）在提示中出现 0 次；
  - 名字无关性：对 Oracle fixture 做任意标识符双射改名后，生成的提示逐字相同；
  - 行号到节点的映射与 AST 一致；每个需描述的 row_key 恰好出现在一个相对行号下；
  - 生产者扰动测试（第 4.2 节）：直接调用 llm_inputs，提示逐字相同。

## 2. 提示模板（模块常量）
describe_v1 原文（逐字写成模块常量）：
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
- judge_v1（只用于 S7 对照）：把 Rules 第 2 条改为 "2. You may add a short security_note (<= 20 words) describing possible weaknesses."，schema 的 statements 条目加 "security_note": "<= 20 words"；其余与 describe_v1 相同；不做黑名单过滤。
- 模板文本的 SHA 写入 manifest；修改模板必须改版本号并重新登记。

## 3. 生成（nodesem 环境，offline/llm_describe.py）
- 用 llama.cpp 的 JSON schema 语法约束输出；温度 0、top_k 1、seed 0。每个 cache_key 写一个原始响应文件（输入、输出、耗时、输入/输出 token 数、是否命中缓存、后端模式 CPU/GPU）。
- 解析失败时重试 1 次（在 user 末尾追加 "Return valid JSON only."），仍失败记为 parse_failed，不再重试。
- 运行方式沿用 N-A 的后台方式：tmux/setsid 控制器、心跳文件、从已完成的 cache_key 继续；开训前做电源检查。网络断开不影响运行。
- CPU 与 GPU 的输出不保证逐位相同：试点可以用 CPU（n_gpu_layers=0）；正式全量固定一种模式并写入 manifest，不混用。

## 4. 试点与预先登记的通过标准（停下等用户确认）
- 抽样：固定种子，从唯一函数单元中按（任务 × SolidiFI/非 SolidiFI）分层抽 50 个；其中非 SolidiFI 至少 25 个，并必须包含重入节点 32 个与访问控制节点 20 个非 SolidiFI 正例所在的函数中的至少 10 个（抽样只用文件名前缀与正例节点所在函数的身份，不把标签写进提示）。
- 报告 pilot_report.json：每单元耗时与 token 数、解析成功率、黑名单命中率、忠实性分布（第 4.7 节公式）、role 与 facts 的一致性（role=external_call 与 facts 外部调用、role=state_update 与 facts 状态写、role=access_check 与发送者守卫的一致率）、3 个完整样例（含提示与输出）、按实测吞吐外推全量 describe_v1 与 judge_v1 的本机耗时。
- 通过标准（写入 manifest，事后不改）：重试后解析成功率 ≥ 95%；节点级 faithfulness 中位数 ≥ 0.7 且 ≥ 80% 的节点 ≥ 0.5；describe_v1 黑名单命中率 ≤ 5%；role 与 facts 的一致率在外部调用与状态写两项上 ≥ 80%。
- 任一标准不满足：停下报告，列出可选方案（换更大模型、调整模板、仅在服务器运行），不得自行修改模板或阈值后重跑。
- 全部满足：仍停下，等用户确认全量运行与预计耗时（按粗略估计，本机全量可能需要十几到数十小时，以试点实测为准）。

## 5. 全量运行（用户确认后）
- 先 describe_v1，后 judge_v1；按 cache_key 去重，进度与预计剩余时间写入心跳文件。
- 完成后核对：每个需描述的 row_key 都有结果或明确的失败原因（parse_failed、missing、segment_error）。

## 6. 后处理（mando 环境，llm_post.py）
- line 必须在给定列表内；同一行取第一条；role 不在词表内改为 other；
- describe_v1 的 summary 与 intent 做黑名单过滤（命中则置空并标记）；
- 忠实性按第 4.7 节，与 accepted_attempt4 的 StatementFacts 比较（名字按 prompt_map 还原）；
- 有效节点：解析成功、行号有效、faithfulness ≥ 0.5、summary 非空；
- 输出 teacher_text.jsonl（row_key、role、summary、intent、faithfulness、flags）与 stats.json（函数数、去重调用数、token 数、耗时、parse_failed/missing/blacklist/unfaithful 比例、faithfulness 分位数、role 分布；全部按 SolidiFI/非 SolidiFI 分层）。

## 7. 教师向量（nodesem 环境，offline/teacher_encode.py）
- 文本 "role: {role}. {summary}. function: {intent}"，bge-small-en-v1.5、normalize_embeddings=True，384 维；函数节点使用 "function: {intent}"。
- 行集合与顺序 = text_v1 的 F3 全集；无效或不需描述的行（env、contract、state_decl、end 节点、失败行）写零向量，存在位为 0。
- 输出 teacher.npz（describe_v1）与 teacher_judge.npz（judge_v1，manifest 标注 control_judgement），manifest 遵守 nodesem-modality-v1，能被 carrier._load 读取；两遍编码逐位相同。
- 只在 FeatureSpec 中登记 TEACHER 与 TEACHER_JUDGE 两种模态（含维度与存在位），不登记任何训练配置（S5–S8 在 NS-P8）。

## 8. 只读诊断（CPU，不训练 HGT；沿用 NS-P6c2 的探针、折、C 网格与 seed）
- 8.1 冗余：在有效节点上，分别用 CODE、CTX、STATIC、CTX+STATIC 线性回归（岭回归，inner_val 选正则）预测教师向量，报告 outer_test 上的平均余弦相似度。说明：NS-P8 的学生只用 CTX+STATIC 作输入，若 CTX+STATIC 已能高度重建教师向量，学生不会带来超出 CTX/STATIC 的信息。
- 8.2 信号：只在非 SolidiFI 的语句/条件节点上，按 NS-P6c2 第 2 节的设定，比较 CODE、STATIC、TEACHER、STATIC+TEACHER 的 AUC 与 BF1（只作描述，可估折单列）。
- 8.3 judge 泄漏：同样设定下比较 TEACHER 与 TEACHER_JUDGE，报告 judge 版本相对 describe 版本的变化（用于判断 S7 的意义）。
- 报告第一段直接回答：教师向量能否被 CTX+STATIC 重建；在非 SolidiFI 节点上教师向量是否提供超出 STATIC 的信号。

## 9. 测试（FakeBackend，不调用真实模型）
解析与一次重试；行号校验；role 规范化；黑名单置空与计数；忠实性三种情形（完全一致=1、部分一致、完全不一致<0.5）；缓存命中时不调用后端；分段与签名；零向量与存在位；manifest 能被 carrier 读取；诊断的折划分只用该外层折的 inner_train/inner_val。

## 10. 验收
试点报告提交后停下；用户确认后全量运行；全部测试通过；PROGRESS、HANDOVER、training_changes 追加（doc_check --expect-cjk 通过）；Git 只提交代码、模板、计划、报告、紧凑汇总与 SHA 索引（原始响应、向量与缓存留在 WSL）；提交 NS-P7。完成后停下，不进入 NS-P8。

## 【建议·未实施】（Claude 的建议，本 Prompt 不执行，需用户逐项决定）
1. 【建议·未实施】STATIC 尺度处理：在 STATIC 投影前加 LayerNorm 或可学习尺度。依据：NS-P6c 中 STATIC 投影范数约为 CODE 的 1/8–1/19，移除 STATIC 只改变 3–10 个预测。会改变 S4 及之后所有配置，需要新的批次。
2. 【建议·未实施】STATIC 小批次：S2+STATIC（含第 1 项的尺度处理）× G3R × 30 折（约 1.5–2 小时），在 NS-P8 之前运行，检验非 SolidiFI 上的 STATIC 信号能否被 HGT 用上。
3. 【建议·未实施】非 SolidiFI 共同终点：在 N-C（NS-P8）的预先登记中把非 SolidiFI 分层（重入节点 32 个正例）列为与整体 BF1 并列的共同终点，而不只是描述项。
4. 【建议·未实施】S5 的基线：N-A/N-B 中 S4 不优于 S2，建议 N-C 同时登记 S2+s_sem（与 S5 = S4+s_sem 并列），避免把学生向量叠加在一个更弱的基础上。
5. 【建议·未实施】先看上限再蒸馏：NS-P8 中先运行 S6（直接用教师向量）重入节点 G3R 10 折；若 S6 不优于其基础配置，则不再训练学生与 S5/S8。
6. 【建议·未实施】匿名视图：在用户同意的前提下，用匿名 CODE（NS-P2 已编码）+ STATIC/TEACHER（与视图无关）+ 8H 的 S0 做匿名视图对照，检验去掉名字捷径后语义特征的作用。需要修改 EXPERIMENT_POLICY。
7. 【建议·未实施】多个 seed：在服务器批次中至少 3 个 seed，以分辨接近上限的微小差异。
8. 【建议·未实施】更大的 LLM：若本机 3B 模型未通过第 4 节标准或 8.2 显示无信号，服务器批次换 7B 级或更大的代码模型再评估，而不是在本机反复调整模板。
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

## 5A. NS-P0 审查记录（2026-11-01，Claude）

NS-P0 验收通过。独立核对了 GitHub 上可以复算的部分：
- 8H plan 与 seal 的 SHA；60 个 G0/G3R 成功收据逐个重算 SHA，全部一致，每个（任务、折、剖面）恰好一个，没有重复 attempt；
- resources.csv 的 22 组平均耗时、峰值显存、最小空闲，以及 N-A/B/C/D 的 4.814/2.473/3.475/1.738 小时外推，逐项一致；
- 四个任务的原节点数 18312/12036/13432/7710，以及“普通 Projector 节点 + end_if/end_loop 合成节点”的拆分（1232/1059/363/215），与 DFG RECON 中的节点类型计数逐项吻合；
- L2 边数（WRITES 3108/2254/1609/767，READS 4314/3070/2208/1091）、环境节点 298 与 ENV_FLOW 3857，与 DFG PROGRESS 一致；DATA_DEF_USE 5710（重入合约）高于 Prompt 5 时的 5659，是 6b 重建所致，6d.2 也确认了访问控制合约的 5773。

无法在仓库里复算的部分（图存储与初值权重没有上传）：600 维载体探针、0 层探针、文本与 CFG 覆盖率、初值文件 SHA。这些以 Codex 的记录为准；初值的 tensor digest 在 NS-P1 第 0 节补做。

Codex 提出的三个设计问题都成立，决定见第 4.2、4.6 节与 r4 说明。本次审查另外发现并修正了方案自身的三处错误（S1 嵌入的规模、层数回退、8H 运行版本核对的写法）。

## 5B. NS-P1 审查记录（2026-11-01，Claude）

**独立核对（在 GitHub 提交的产物上复算）：**
- S0 等价：两组 CPU 短检查（reentrancy_node fold0 G3R、access_control_contract fold0 G0）的 historical 与 nodesem 输出逐文件比较。inner_val/outer_test 预测、原标签辅助预测、梯度审计、三个分区的监督清单、优化器配置逐字节相同；history、best、last、result、validation_performance 中所有数值字段（每轮 loss、学习率、beta1、F1、混淆矩阵）都相同，差异只出现在耗时、checkpoint SHA、binding（feature_view、feature_npz、feature_spec、nodesem_version）和由 binding 派生的 input_sha256 上。
- 60 个初值的独立 tensor digest 与 NS-P0 从另一组文件记录的 state_sha256 逐个相同（60/60）。
- S1 参数：V=32100 时共享嵌入 2054400，比 S0 多 1079552，总数 6190564，与 NS-P0 的 512 维基数 5111012 一致。

**三项用户批准的处理：**
1. torch.load 边界：checkpoint_io.load_checked 对同一个打开的文件先算 SHA、再 seek(0) 加载，避免检查与加载之间被替换；限定三个根目录；加载后再核对 tensor digest。处理正确。剩余风险是 PyTorch 1.8 的 pickle 本身，已如实记录。
2. 扰动验收：生产中保留整图指纹门禁是对的（标签变化必须使旧特征失效），测试中只在一次性 fixture 上重绑指纹，并单独证明锚点损坏仍被拒绝。处理正确，但证明力有限：载体只复制预先算好的向量，本来就不读这些属性。真正需要扰动验收的是特征生产者，已写进第 4.2 节和 NS-P2/P3/P7。
3. scheduler 的 anneal_func：OneCycleLR 状态里保存的是实例绑定方法，两个实例必然不同；改为核对类与函数实现、其余字段严格比较，与 8D 的同类处理一致。处理正确；我复算的数值比较也支持这一点。

**另外发现的问题：**
1. **运行版本绑定过宽（必须修）**：见 NS-P1b 第 1 节。
2. **S1 初始尺度（方案错误，必须修）**：见 NS-P1b 第 2、3 节。
3. **G0 与 G3R 的行集合**：Codex 已指出，NS-P2 按第 4.2 节实现。
4. **构造耗时翻倍**（15→31 秒）：来自载体中的 Projector 锚点门禁、8G assemble、4 次整图指纹和 2 次深拷贝。N-A 的 180 个 fit 约多 45 分钟 CPU 时间，可以接受，暂不优化；NS-P4 实测 S4 的构造耗时后再定。
5. **CUDA 上 EmbeddingBag 反向不保证逐位确定**：与 8H 的散射累加同性质，在 N-A 的 manifest 中注明即可。

结论：NS-P1 的实现与验收成立，但在进入 NS-P2 之前，需要先完成 NS-P1b。

## 5C. NS-P1b 审查记录（2026-11-01，Claude）

**独立核对：**
- 运行版本拆分：runtime_refs 只含 RUNTIME_MODULES 中的 8 个训练模块与冻结 DFG/作者代码；execute 模式要求当前代码相同且只接受 v2 计划；verify 模式不比较当前代码，改为核对 plan/seal/authorization、每个已完成 fit 的 started.json 中的 runtime、receipt（v2 另有 receipt.seal.json）以及全部产物 SHA。已确认 verify 路径不会用当前代码重建模型，只在 SHA 校验后读取 checkpoint 并重算指标，所以确实不依赖当前模型代码。v1 计划只能 verify，并按其当时完整的 runtime 核对，没有被裁剪成新清单。实现与 r5 要求一致。
- S0 回归：s0_cpu 的 historical 与 nodesem 输出逐文件比较，预测、梯度审计、监督清单、优化器配置逐字节相同，其余文件只在耗时、SHA 与 binding 字段上不同，数值字段全部相同。
- S1（r5）：共享 LayerNorm 只作用于非空行；state_dict 与 named_parameters 中 token_bag/token_norm 各只出现一次；参数 6190692 = 6190564 + 128（LayerNorm 的 64+64）；1 轮 CPU 冒烟 loss 有限（train 0.8548，inner-val 0.8261），37 个新参数张量（bag 1 + norm 2 + 17×2 Linear）都有非零梯度。

**对 r5 表述的更正（Codex 的意见成立）：** r5 写的是 S1（r4 初始化）“训练初期几乎没有输入信号、对比较不公平”。init_scale.json 显示，经过冻结 HGT 的偏置、残差与 LayerNorm 后，r4 第一层输出的标准差仍接近 1，所以不能断言 r4 无法学习。更准确的说法是：r4 中 h0 的标准差约 0.002，而第一层 LayerNorm 之前的信号约 0.037，节点输入只占约 6%，其余来自与节点无关的偏置和残差项；r5 中 h0（约 0.46）大于 LayerNorm 前的信号（约 0.13）。这些都是跨节点、跨维度合并的统计，不能证明学习能力，只说明 r5 让节点输入在初始化时占主导。r5 的决定在任何训练之前做出，不依赖结果，因此保留。
另一个值得写进论文的观察：S0 在多邻居目标上有 88.9% 的注意力 head 最大权重 ≥0.99，S1（r4、r5）都是 0%，与 DFG Prompt 5 的饱和诊断一致。

**用户批准的诊断边界**（冻结的 make_model/validate_registration 在装配时读取图内标签，诊断统计本身不读标签与评分）：处理正确，与 NS-P1 的完整性门禁一致。

结论：NS-P1b 验收通过，没有遗留问题，进入 NS-P2。

## 5D. NS-P2 审查记录（2026-11-02，Claude）

**独立核对（在提交的 text.jsonl 与 manifest 上复算）：**
- 行数：F3 全集 12223/7892/18610/13693，其中 env_source 187/182/298/261，与 DFG 记录一致。
- cut_mode 分布由 DFG 节点类型计数逐项推出，全部吻合，例如重入合约：头部 412+86+45=543，签名 3651+165+165=3981，条件 1232+28+7=1267，END 占位 1197+35=1232，完整文本 11289 + env 298 = 11587；回退 0；全部行的 text_sha256 与文本一致；两个视图的行身份与 cut_mode 逐行相同。
- 抽样检查各类截取文本（条件、for 头部、签名含 modifier/returns、合约继承头部、struct、END 占位、环境键）均正确。
- 匿名视图中没有文件名；没有 SolidiFI 标记名。仍以原名出现的只有十余个（data、number、min、max、sig、interfaceId 以及 abi.encodePacked 等内置成员）。【r8 更正】它们是 identifier 节点，但在 8G 的保留表中（EXCLUDED_NAMES 由一段字符串加一个拼接列表组成，审查时只解析了字符串部分，漏掉了列表）；保留是按拼写进行的，所以用户自己命名为 data 的变量也会保留原名。这是 8G 视图本身的性质，NS-P2b 已按 AST 统计。
- 8 份编码 manifest：版本、模态、F0/F3 指纹、行集合、present、implementation、assets、input_text 都符合载体契约；encoding_summary 中 8 次编码重复运行逐位一致。
- carrier._aligned 的超集改动正确：原节点顺序严格一致，只允许省略辅助节点，辅助行按身份查找。
- 生产者扰动测试（两个视图，(a)(b)(c) 三项）存在于 test_text_view.py。
- nodesem 环境：Python 3.10.21、torch 2.6.0+cu118、transformers 4.46.3；pip 首次安装时动到了 Python 3.10 的 user-site（filelock、tqdm、typing_extensions），已按原版本与 wheel SHA 恢复，此后统一 PYTHONNOUSERSITE=1，编码器拒绝启用 user-site；mando 未改动。记录完整。

**问题：**
1. **四处文档的中文全部写成了 `?`（必须修）**：见 NS-P2b。
2. **逐文件编号的影响（需量化，不改决定）**：同一条语句在不同文件中被编成不同的 vN，导致匿名视图的唯一文本数是原名视图的 2–3 倍（重入节点 7223 对 2846）；跨文件共享的原文语句中约 87% 因此分裂。决定沿用 8G 编号（第 4.5 节），NS-P2b 测量其对向量的影响。
3. **implementation 绑定包含 carrier.py**：text_view 导入了载体中的函数，所以绑定是对的；但之后若修改 carrier.py，全部编码特征都要重新生成（约 4 分钟 GPU，代价不大）。

结论：NS-P2 的实现与数据成立；完成 NS-P2b 后进入 NS-P3。

## 5E. NS-P2b 审查记录（2026-11-02，Claude）

**独立核对：**
- 文档修复：四份文档各自只有一个连续区域被改动；该区域在 e5aab8d2 中全部是 ASCII（0 个非 ASCII 字节，问号 377/2203/645/2058 个），区域之前的全部字节与之后的结尾字节逐字节相同。新内容是 UTF-8 中文（中文字符 993/4697/2169/1038 个），没有连续问号。offline/README.md 中被写成问号的一个章节符号也已修复。现在这六份文件全文都能按 UTF-8 严格解码，没有任何连续 3 个问号或替换字符。
- 重写后的 NS-P2 报告中的行数、去重数、去重率、峰值显存、环境版本与证据文件一致；总耗时 218.936 秒与各任务耗时之和 218.937 的差异只是舍入。
- 编号影响：分组数、分裂组数、各组匿名变体数与两两配对数，我从提交的 text.jsonl 重新计算，全部相同（例如重入节点 841/735 组、75457 对）。余弦本身需要本地 NPZ，无法在仓库中复算，以 Codex 的结果为准。
- doc_check：严格 UTF-8 解码、按追加前字节数只检查新内容、拒绝连续问号与替换字符、`--expect-cjk` 要求中文；不在 RUNTIME_MODULES 中。实现正确。
- 用户在两轮之间另做的核查（training_changes §75 与 artifacts/ns_p2_review_20261102/）与本审查的结论一致。

**编号影响的结论：** 同一原文语句的不同匿名变体，向量平均余弦为 0.90–0.92（5% 分位约 0.80），同类型不同原文的随机对照为 0.60–0.64。编号会使向量有可见的变化，但变体之间仍远比不同语句接近。按第 4.5 节的决定保留 8G 编号。若以后要量化这部分噪声对检测的影响，可在 N-B 中加一个只作描述的对照（节点文本内规范编号的 S2），现在不加。

**更正：** 第 5D 节中“这些名字不是 identifier 节点”的说法是我的错误，Codex 的核查正确，已在 5D 中更正。

**过程问题（已妥善处理）：** `git diff --check` 对原样归档的 diff 文件报尾随空格，Codex 只对这一份归档豁免格式检查，并严格核对其 SHA。处理合理。

结论：NS-P2b 验收通过，没有遗留问题，进入 NS-P3。

## 6b. 扩展到其余 5 类的前提（r9 记录，现在不执行）

NodeSem 的代码按通用设计实现（第 4.6 节原则 1），但它的输入依赖基准 v2，而基准 v2 目前只为重入与访问控制建立。扩展到 arithmetic、denial_of_service、front_running、time_manipulation、unchecked_low_level_calls 之前，需要按顺序完成：
1. **DFG 图**：按 scripts/DFG/dfg_v2/EXTENDING.md 登记类别、封存输入、构建并核验 F1–F3 图存储。
2. **基准 v2 的三项输入**（EXTENDING.md 写于 8D 之前，没有覆盖这些）：
   - 8D 式的分组折（精确与近重复源码分在同一组）；
   - 8G 式的 N-anon-s 改名视图与泄漏探针（P2/P3、关键字基线）。这些类别的 SolidiFI 标记名（例如 `_intou`、`_TOD`、`_tmstmp`、`_unchk`）同样会被全标识符改名去掉，但探针必须重新通过；
   - L-audit 标签视图：8B/8C 的标签审计是按重入与访问控制的 SolidiFI bug log 做的，其余类别要重新做截断、溢出标签与 C1/C2 的审计。
3. **NodeSem**：在新类别上重跑 NS-P2（text_view 对未识别的节点类型回退为完整文本并计数，扩展时检查回退数）、NS-P3a/P3b（事实与特征），再按 NS-P5 的方式封存计划。
这些工作应另立 Prompt，并写进 DFG 与 NodeSem 两边的计划；本轮的冒烟（NS-P3a 第 3 节）只验证事实抽取能在这些类别的源码上运行。

**DFG 侧审查补充（2026-11-02）。** 详见 dfg-v2 分支 `scripts/DFG/dfg_v2/PROMPTS.md` 第 4.10j 节。其中与 NodeSem 直接相关的两点：
- **SolidiFI 注入片段的语义与类别名不完全吻合。**
  - denial_of_service 的注入标记是 `_unchk`，片段为 `if (!addr.send(10 ether) || 1==1) {revert();}`；
  - unchecked_low_level_calls 的注入标记是 `bug_unchk_send`，片段为 `msg.sender.transfer(1 ether);`，transfer 失败时会回滚，这并不是“未检查的低层调用”。
  - 扩展时，这两类的 SolidiFI 层与非 SolidiFI 层必须分开报告与解读。M3a 的字段设计不得为了拟合这些片段而调整。
- **算术类会因匿名化丢失 SafeMath 的名字。** N-anon-s 会把 SafeMath 及其 add/sub/mul 改成 vN。M3a/M2 需要用结构表达“经过检查的库运算”：例如在 L 组（函数汇总）中对被调用的同文件库函数或内部函数做一层汇总，记录其函数体内是否对运算结果设置了 require/assert/if 守卫。否则算术类的主视图会系统性地丢失这一合法语义。这一项应在 NS-P3a 实现事实之前决定，不依赖任何结果。

## 5F. NS-P3a 审查记录（2026-11-02，Claude）

**已核实正确的部分：**
- DFG 接口：facts_io.check_layer_edge 逐项复现 dfg_v2/pipeline._evidence 的检查（索引范围与唯一性、端点一致、L1 非自事实、L2/L3 必须已投影、关系与环境键一致）；L1 符号按封存的 route 重建冻结的 SymbolTable/ExtendedSymbolTable，按完整 ID 精确查找，不一致即报错；24681 次查找通过。图、证据、源码都先核对 SHA。
- 行数与身份：四个任务 18610/12223/13693/7892 行，与 text_v1 的 F3 全集一致。
- 守卫的关键区分在真实数据上成立：phishable.sol 与 mycontract.sol 的 `require(tx.origin == owner)` 的自身条件是 env 对状态；SolidiFI 模板 `require(tx.origin == owner_txoriginN)` 是 env 对参数；其后的转账语句带有规则 1 守卫。
- `.call.value(x)` 未被调用的语义（访问控制两个任务各 334 处）、一层同文件库/内部函数的运算检查（不依赖 SafeMath 名字，回应了 DFG 侧关于匿名化丢失 SafeMath 的意见）、using-for 库调用不计为外部调用、未解析 modifier 记为未知，这些处理都正确。
- 用户批准的五项细节（必然成立的极性、唯一一层运算检查、封存符号身份、金额与混合返回值 unknown、共享基类声明的授权汇总）合理。

**必须修正的问题（NS-P3a2）：**
1. **状态未知被整函数扩散（实现错误）**：见 NS-P3a2 背景第 1、2 条。state unknown 66%–81% 中，绝大部分由内置名触发的 state_name_missing 造成，而不是真正的状态不确定。
2. **析取型发送者守卫（方案错误）**：第 4.6 节“|| 不计入”的规则对 `msg.sender == owner || msg.sender == admin` 这类常见写法是错的，NS-P3a2 修正。
3. **名字无关性没有被检验**：原名单视图下，原计划中“两个视图逐位相同”的检验不再执行。M3a 的设计依赖于“与名字无关”，至少需要 fixture 级的改名测试。

**与方案冲突、需要用户决定的事项：EXPERIMENT_POLICY.md（只用原名视图）。**
NS-P3a 期间按用户指令写入的 EXPERIMENT_POLICY.md 规定后续实验只用原名、facts 拒绝匿名视图。这推翻了 2026-10-31 与用户确定的“匿名视图为唯一主终点、原名视图为次要终点”。若保持原名为主，需要清楚以下后果，并在 NS-P4 之前改写后续 Prompt：
- **名字泄漏**：8B–8D 已证明，原名下 SolidiFI 注入代码的名字（如 `owner_txorigin12`、`userBalance_re_ent19`）几乎直接给出标签：在访问控制节点任务上，不经学习的标识符规则（8B）达到 98.97，高于所有 GNN；8D 中只把注入标记换成 idN 的视图上，无学习规则在 SolidiFI C2 子集上也达到 99.98。其余 5 类的注入名同样带标记（`_intou`、`_TOD`、`_tmstmp`、`_unchk`、`bug_unchk_send`）。预训练代码编码器（M1/M2）与 LLM（M3b）会直接读到这些名字，原名下的 S2–S7 增益无法与“认出注入标记”区分开。M3a 按设计与名字无关（一处例外），受影响较小。
- **基线**：8H 的 S0 是匿名特征，不能作为原名实验的配对基线；需要在原名、分组折、L-audit 下重跑 S0 × {G0, G3R} 共 60 个 fit。
- **可比性**：DFG 的主结果（8H）是匿名视图，NodeSem 改为原名后，两个创新点的结果不在同一视图上。
可选方案：(A) 恢复匿名为主、原名为次（原计划）；(B) 原名为主，但预先登记必须报告的对照：原名 S0 基线、非 SolidiFI 层、按类别的标识符规则基线，以及匿名视图上的 S0/S4 作为泄漏对照；(C) 两个视图都作为主终点，共同做 Holm 校正，并预先规定结论只在两者一致时成立。facts 与 M3a 在三种方案下都可直接使用（只有 names 字段与视图有关）。

结论：NS-P3a 的大部分实现正确，DFG 接口正确；先完成 NS-P3a2，并由用户确认视图口径，再进入 NS-P3b。

## 5G. NS-P3a2 审查记录（2026-11-02，Claude）

**复核方式**：在独立环境中用仓库内的 tree-sitter-solidity 源码重新编译语法库，运行全部 facts 测试（350 通过）；逐行检查 revision_comparison.json 中各字段的变化方向；用审计中的问题位置回到原始源码核对剩余未知；对守卫逻辑构造对照用例。

**已核实正确：**
- 冻结的 DFG、HGT、tokenizer、标签与图代码没有改动（git diff 为空）；accepted_attempt2 保留。
- state 未知从 6627/4350/5947/3774 降到 78/32/75/29；剩余的来源是名字歧义（例如 ERC20 中 mapping 与同名函数 balanceOf/allowance/totalSupply）、无法解析的别名、未投影的状态效应、assembly，以及下面的 throw。
- 内置名、裸被调函数、事件名、类型名的分类正确；emit/revert 的参数被 call_argument 包裹，不会被误当成事件名。
- 所有守卫变化都是 false→true（析取型发送者守卫），没有守卫丢失；读写条目只有 auth 位变化。
- payable_fallback 在 31/20/51/34 个合约行由 false 变为 true：旧实现只看有 HCG 节点的函数，漏掉了 `function () external payable`（逐个核对 buggy_18/19/25 等源码）；这是 NS-P3a 的遗留错误，本轮的全 AST 汇总修正了它。
- 用户批准的三项调整合理：逐字段 unknown_fields 比整组 status 更准确；比较清单补入 order.status 是我写 NS-P3a2 时的遗漏；受限布尔适配是必要的（冻结语法确实误解析，见下）。

**需要修正（NS-P3a3）：**
1. 冻结语法把 `a && msg.sender == owner` 解析成 `(a && msg).sender == owner`。布尔适配只在含 `||` 或负极性时启用，正极性合取仍漏判：buggy_2/buggy_3 的 `assert(msg.sender==owner && msg.sender!=newOwner)` 不是发送者守卫，`owner=newOwner` 被计为未受保护写入。
2. `throw` 被当成未解析的状态值（10/10/32/8 次），包括 etherbank.sol 与 reentrancy_simple.sol。
3. 汇总字段的未知没有用三值逻辑：已有确定 true 或 "many" 的字段仍被标为未知。
4. K 组未知的作用目标过宽（targets=None 作用于整个合约的全部声明）。
5. dominators 的写法依赖 networkx 2.6.3 的行为。
第 3、4 项不影响已知值的正确性，只影响有多少信息被掩码；第 1、2 项是事实错误，但涉及的行数少。

**视图口径**：用户没有选择第 5F 节的 A/B/C，并继续按 EXPERIMENT_POLICY（原名）执行；本文件从 NS-P3b 起按原名改写。我仍然认为名字泄漏需要对照，因此 NS-P3b 同时生成不含变量名的 CTX（ctx_masked）；原名 S0 基线与非 SolidiFI 分层在 NS-P5 计划中登记。

结论：NS-P3a2 的主体正确，先完成 NS-P3a3，再进入 NS-P3b；NS-P4（融合与冒烟）在 NS-P3b 之后。

## 5H. NS-P3a3 审查记录（2026-11-02，Claude）

**结论：通过。** 下一步是 NS-P3b（M2/CTX 与 M3a/STATIC），NS-P4 在其后。

**复核：**
- 独立环境（重新编译的语法库）中全部 facts 测试 413 通过；在 networkx 3.7 下去掉我自己的兼容补丁后同样通过，dominators 修正有效。
- 守卫：对 15 个构造条件逐一检查（正/负极性的合取、析取、De Morgan、mapping 下标中的 msg.sender、三元表达式、混合项），结果全部符合定义；buggy_2/buggy_3 的 changeOwner 写入现在受发送者守卫保护，unguarded_write_functions 2→1。
- Codex 提出的两项调整是对的：我在 NS-P3a3 中写的“合取只保留发送者相等组合”会丢掉原有的 state_param 等组合，属于我的表述错误；误解析判据补充数组 base 跨越布尔运算（buggy_21）也是必要的。
- 逐行比较 attempt3→attempt4：调用、环境、算术、语法、DFG、读写变量与形状在四个任务中零变化；没有任何字段由已知变为未知；已知值的变化只有守卫带来的 sender_guard false→true（每任务 3）与 unguarded 计数减少。被解除掩码但取值不是 true/many 的字段，抽查后都来自目标收窄：例如 balanceOf 的歧义只再作用于 balanceOf；只含 mload/extcodesize/mstore 的 assembly（buggy_30/31/43/44、spank_chain_payment 等）不再使函数的 state_write 未知。
- 未知比例：state 68/22/43/21，K 105/85/33/15（约 4%），L 52/18/52/18，M 13/8/15/8。

**已知限制（不阻塞，保守方向）：** 别名目标判断中 `address payable` 不能被 PRIMITIVE 完整匹配，被当成可能的引用类型，SolidiFI 文件中的 `address payable lastPlayer_*` 因此被列入别名问题的目标，使少数 K 字段多被掩码。不修改，记录在案。

**视图口径（我的建议）：** 匿名视图（N-anon-s）作为主终点，原名作为次要终点。理由：(1) 四个任务中 SolidiFI 文件占 40/142、40/71、40/114、40/57，节点任务中占多数；8B–8D 已证明原名下这些文件的标签可以由名字直接读出，而且只替换注入标记的视图同样泄漏（99.98），所以部分改名不能代替全文件双射；(2) DFG 的主结果（8H）在匿名视图上，NodeSem 的增益应在同一视图、同一 S0 基线上衡量，可直接复用 8H 的 S0，不必新跑 60 个 fit；(3) M3a/STATIC 与名字无关，两种视图下相同，受影响的只是 TOKEN/CODE/CTX/LLM。原名视图的价值（预训练编码器与 LLM 能利用有意义的名字，更接近真实使用）通过次要终点与非 SolidiFI 分层来体现。若用户仍选原名为主，则必须预先登记：原名 S0 基线、非 SolidiFI 分层、ctx_masked 对照，以及关键配置在匿名视图上的复核。用户决定后，再据此调整 EXPERIMENT_POLICY.md 与 NS-P3b。

## 5I. NS-P3b 审查记录（2026-11-03，Claude）

**已核实正确：**
- 在独立环境中运行 test_ctx_static 与 test_p3_acceptance（77 通过）；用 static_profile.encode 对 accepted_attempt4 全部行重算 STATIC，取 1 比例与 stats.json 逐列相同（最大差 0），独热组没有多于一位的行。
- masked CTX：对 8 份 encoded_text 全量扫描，SolidiFI 标记（re_ent、txorigin、intou、tmstmp、TOD、unchk、bug_）在 masked 文本中为 0 行；除占位名外剩下的词都是关键字、类型、内建名与字段枚举。文件名只出现在元数据中，不进入编码文本。
- 用户批准的四项调整合理：独立的 encode_ctx.py（保护 M1 清单的 SHA 绑定）、只读 AST 辅助信息、第 8 级截断（只发生在 buggy_35 的 masked 文本）、中断后复用首份成功结果（每份编码两遍逐位相同，清单绑定 SHA）。
- “一层检查运算”未编码：Codex 如实报告并留下 unconsumed_facts.json，没有自行扩维，这是正确的做法；遗漏在我的第 4.5/4.6 节表中。

**需要修正（NS-P3b2）：** 一层检查运算进入 STATIC；B/C/D 组未知时保留已证实的 true 位；参数来源写 "entry" 而不是 "unknown"。见第 5.5b2 节。

**名字泄漏的实测规模：** 原名 CTX 中含 SolidiFI 标记子串的行：reentrancy_node 5961/12223（48.8%），reentrancy_contract 5961/18610，access_control_node 3054/7892（38.7%），access_control_contract 3054/13693；masked 中为 0。这为第 5H 节的视图建议提供了直接的数据。用户在 NS-P3b 中继续使用原名为主，因此 NS-P4 同时登记 S3m/S4m（masked CTX）对照；CODE（M1）仍是原名，masked CTX 不能消除 CODE 中的名字，这一点在 NS-P5 计划中必须处理（原名 S0 基线、非 SolidiFI 分层，或在匿名视图上复核关键配置）。

## 5J. NS-P3b2 审查记录（2026-11-03，Claude）

**结论：通过。** 下一步是 NS-P4。

**复核：**
- STATIC：用 static_profile（v2，245 维）对 accepted_attempt4 全部行重算，与 attempt_b2 的 stats 逐列相同（最大差 0）；checked_by_helper=1 的行 271/105/214/103 与 NS-P3b 记录的未消费计数一致；没有任何行同时有 checked_by_helper=1 与 unknown.checked_call=1；没有任何行在守卫未知时置 D 组 none 位；顺序未知但保留了已证实 C 位的行 39/35/35/35（含 ext_call_in_loop）。
- CTX：我独立比较新旧 8 份字段文件：变化行 3671/1942/4602/3118（原名与 masked 相同），把新文本中的 entry 换回 unknown 后与旧文本逐字相同，没有其他差异。剩余的 FROM unknown 只有 L1 不支持的行与循环更新表达式（++i、i++ 等，facts 中没有定义相对距离），参数来源已全部为 entry。
- 新测试 96 项在独立环境通过；载体维度 S3=514、S4=760。
- Codex 对测试夹具问题的处理（constructor/fallback 使用 facts 中实际的 function 类别；modifier 夹具因 L1 不支持而断言 unknown）是正确的，没有放宽生产断言。

**记录的限制（不阻塞）：**
- checked_call 的状态在语句中任一调用无法唯一解析时就是 unknown（每任务 35–115 行），其中已证实存在经检查运算的只有 7/4/6/4 行；按我在 NS-P3b2 中的规定，这些行的 checked_by_helper 为 0。严格按三值逻辑应保留为 1，但影响太小，不单独返工；以后修改 STATIC 时一并处理。
- 循环更新表达式的来源距离仍写 unknown（每任务约 30 行），原因是冻结 facts 没有为它们定义相对距离。

## 5K. NS-P4 审查记录（2026-11-03，Claude）

**已核实正确：**
- 融合实现（adapter.py）与方案一致：连续模态 LayerNorm → 无偏置投影，STATIC 不归一化；按存在位求和加共享偏置；gated 对缺失模态屏蔽、全缺失时输出偏置且不产生 NaN（先替换整行再 softmax，前向与反向都安全）；dropout 只在训练模式、用局部 CPU Generator；旧 S1 的参数名与 p=0 算术路径保留。
- model.validate 对各模态投影、归一化、门控、共享嵌入的注册逐项校验；layers=0 只允许 G0；HGT 与训练器未改。
- 线性等价改用 float64 参考加容差（最大差 3.8e-05、输出尺度 114）是正确的：不同 GEMM 累加顺序无法保证 float32 逐位相同，我原来要求逐位相同是不可实现的；同一路径重复运行仍逐位相同。
- FeatureSpec 允许 p=1 只为覆盖全缺失测试，生产配置为 0.1，合理。
- CPU 冒烟 7 个配置全部通过（有限 loss、各模态投影有非零梯度、共同初值与 8H 相同、重载一致）；S0o 载体与原图 token 逐位相同（8 项），参数摘要与 8H S0 一致。构造时间未超过 8H 的 3 倍。

**需要修正（NS-P4b）：**
1. **显存门槛是我的错误。** 8H 的 S0 在 reentrancy_contract/G3R 上最低空闲为 44–74 MiB（resources.csv），按 100 MiB 门槛同样会失败。S1o 的 peak allocated/reserved（1853/2074 MiB）不高于 8H S0（1895/2094 MiB），没有显存回退。Codex 按规则停止、保留现场、不重试，处理正确；但因此 S4 没有任何 GPU 验收，GPU 路径（设备转换、门控、dropout 掩码搬运）尚未验证。
2. **dropout 种子不含节点类型**，各类型的掩码序列相同（我的种子定义遗漏）。

**对 NS-P5 的资源前提：** S4 在 reentrancy_contract/G3R 上很可能超出本机 4 GiB 卡；正式 N-A 若含该任务的 S4，需在服务器执行，或在 NS-P5 计划中明确分设备执行。

## 5L. NS-P4b 审查记录（2026-11-03，Claude）

**结论：通过。** 下一步是 NS-P5（已按原名视图改写，见第 4.12 节与第 5.7 节）。

**复核：**
- dropout 种子加入 ntype（adapter.py 一行修改），新增测试覆盖不同类型掩码不同、同类型可复现、评估不推进计数。
- GPU 显存数据我逐项对照 resources 目录与 8H resources.csv：reentrancy_node 上 6 项 peak reserved 与 8H 之比 0.94–1.00（S4-noG 0.22）；reentrancy_contract/G3R 上 S1o 2074 MiB（0.99），S4 2194 MiB（1.048）、最低空闲 44 MiB，与 8H 该任务 5 折的最低空闲 44–74 MiB 处在同一水平。S4 在本机能跑，但没有余量。
- **TF32**：我在 NS-P4b 中给的 GPU/CPU 一致性门槛（1e-4）没有考虑 Ampere 卡默认启用 TF32（torch 1.8.1 中 matmul 与 cudnn 的 allow_tf32 默认为 true）；默认设置下 S4 的差为 1.07e-3。Codex 停止后经诊断确认：同一 GPU 默认设置下重复运行逐位相同，关闭 TF32 后差降到 8.3e-7。把一致性检查改为“临时关闭 TF32 的 GPU eval 与 CPU 比较”、训练仍用默认设置并在 finally 中恢复，是正确的：它验证的是实现等价，而训练与 8H 保持相同的数值设置。默认 TF32 下的差值单列，没有被说成通过。由此带来一条新要求：同一比较中的配置必须在相同 TF32 设置与同一设备类型上运行（已写入第 4.12 节与 NS-P5）。
- 日志接入失败（训练前，未进行优化步骤）与用户先误点“停止”后更正的两次恢复，都封存了新计划并保留旧失败现场，复用的结果有收据，处理正确。

**视图口径**：用户在 NS-P3b、NS-P3b2、NS-P4、NS-P4b 中均保持原名为主，没有选择我在第 5H 节建议的匿名主终点。因此从本版起，第 4.12 节与 NS-P5/5A/P6 按原名视图改写：S0 改为新跑原名 S0o，SolidiFI/非 SolidiFI 分层和 S4−S4m 作为预先登记的描述项。匿名复核（N-D）保留为待用户决定的选项。

## 5M. NS-P5 审查记录（2026-11-03，Claude）

**结论：通过。** 下一步是 NS-P5A（需要用户填写授权后才能训练）。

**复核：**
- 240 个 job 覆盖 {S0o,S1o,S2,S4} × {G0,G3R} × 30 折（重入/访问控制合约各 5 折、节点各 10 折），8 个（任务、图配置）组合中 4 个配置使用同一图文件，且图的 SHA 与 8H plan 中对应的 G0/G3R 完全相同（G0 为作者 E0 图，G3R 为 graphs_v2_r1 的 F3）。
- 训练配置逐任务取自 8H（例如 reentrancy_contract：lr 5e-4、OneCycle max 0.01、50 epoch、patience 7、按最小 inner_val loss 选 best），没有统一覆盖。
- 预先登记与第 4.12 节一致：主终点、Holm 四比较（Wilcoxon 双侧，zsplit，与 8H 相同）、交互项只描述、S* 只在 S1o/S2/S4×G3R 中按 inner_val 选择且不替换 S4、SolidiFI 分层只按文件名前缀（不读标签）、非 SolidiFI 正例 32/20 的逐节点表、匿名 8H 只作历史参考。
- local_dev_v1 中“运行时最低空闲 100 MiB”只产生 memory_tight 提醒（local_dev.py），不会中止 reentrancy_contract/G3R/S4（NS-P4b 实测 44 MiB）；OOM 与 CUDA 错误才停止。
- Codex 主动指出“G0 上的 S4 仍含由 DFG 生成的 CTX/STATIC，不能当作无 DFG 对照”，并写进交互项的解读，这是正确且重要的补充。

**NS-P5A 前需要明确的两点（已写入第 5.8 节）：** 正式 worker 尚未绑定，且 NS-P4 的验收入口带有 maximum_training_epochs=1 的覆盖，正式路径必须证明不带任何训练配置覆盖；用户批准的“本机先导、服务器另建批次”需要在授权与报告中写清两批的关系。

## 5N. NS-P5A（N-A）审查记录（2026-11-04，Claude）

**结论：执行与数据通过，进入 NS-P6。** 不需要纠正性 Prompt。

**复核：**
- 240 个 fit 的 resources.csv 完整（每配置 60 个），实际墙钟合计 10.48 小时（我在 r18 中估计 8–9.5 小时，偏乐观；S4 每个 fit 训练外仍有 40–85 秒开销）；最低整卡空闲 34 MiB（reentrancy_contract/S1o），只产生 memory_tight 提醒；没有失败、外部中断或重试。电源检查（交流供电、睡眠与休眠为“从不”）与 tmux 后台运行都有记录。
- 正式 worker 不覆盖训练配置（只把 maximum_training_epochs 用于完整性检查）；best/last 轮次合理（best 平均 8–23 轮，last 比 best 多 5–7 轮，与 patience 7 一致）。
- 我用 scipy 独立复算重入节点 G3R 的四项 Wilcoxon：S4−S0o p=0.0371、S2−S0o p=0.0098 与报告完全相同；S1o−S0o 与 S4−S2 含零差，报告使用的 scipy 1.7.3 以正态近似得到 0.0144 与 0.2213（我环境中的新版 scipy 给出 0.0117 与 0.2539，差别来自版本对零差的处理，不改变结论）。Holm 校正后：S2−S0o 0.039、S1o−S0o 0.043（均 <0.05），S4−S0o 0.074，S4−S2 0.221。NS_P5A_REPORT 只写了主终点的 Holm 值，没有写出另两项通过校正，应补述（见下）。
- access_control_contract 的 G0/S4 与 G3R/S4 折均值相同（92.2245）是逐折数值换位造成的巧合（逐折结果不同），不是重复运行或图引用错误。

**结果的解读（我的独立判断）：**
1. 主终点未通过：S4−S0o = +0.147 个百分点，Holm p=0.074。
2. 相对 S0o 的提升主要来自“不再把整数 token ID 直接线性输入”：只学 token 嵌入的 S1o 与只用 CODE 的 S2 都通过 Holm，而 S4 与 S1o 几乎相同（99.772 vs 99.789），S4 低于 S2（−0.054，6 降 3 升）。现有证据不支持 CTX+STATIC 在 CODE 之上带来增益。
3. 原名视图下 SolidiFI 已饱和：重入节点 G3R 中 SolidiFI 的 6751 个正例，S1o/S2/S4 全部检出（FN=0），差别只剩 11–24 个误报；整体 BF1 几乎完全由 SolidiFI 决定（占正例 99.5%）。同一任务在匿名 8H 中 S0 的 SolidiFI 为 TP 6705/FP 44/FN 46，即原名把这部分变成了“认名字”。这证实了第 5H 节的担心：在原名主终点上，语义增强几乎没有可测量的空间。
4. 有信息量的部分在非 SolidiFI（重入节点 32 个正例）：TP/FP/FN 为 S0o 20/11/12、S1o 22/1/10、S2 25/5/7、S4 25/7/7；匿名 8H S0 为 21/19/11。CODE 带来约 5 个 TP，CTX+STATIC 没有再增加；访问控制节点的非 SolidiFI 20 个正例，各配置只检出 0–2 个。这些只是小样本描述。
5. N-B 仍值得按预先登记完成（约 5–6 小时）：S4g 检验“concat 把 CODE 信号稀释”这一可能，S4m 检验 CTX 中的名字，S4-noG 检验 CTX/STATIC 能否替代 DFG 边；我在 NS-P6 中加入了明确标为事后描述的 S2/S1o 对照与逐节点对照。

**文档补述（不需要 Codex 重做）：** 第 5N 节即为补述：Holm 家族中 S2−S0o、S1o−S0o 通过 0.05，S4−S0o 与 S4−S2 未通过。

## 5O. NS-P6（N-B）审查记录（2026-11-05，Claude）

**执行与数据：通过。** 我用 fold_metrics 独立复算了 N-B 的折均值与关键差值，与报告一致（例如重入节点 S4−S4-noG = +1.598 个百分点，10 折均升）。S4m 在 reentrancy_contract 五折完全相同（每折恰好 1 个错误），属实。S4m fold8 的失败是显存采样读数失败而非 OOM，经用户授权从同一零步初值重跑，处理正确。Codex 写明的限制（S2 的 modality dropout 为 0 而多模态为 0.1；S4-noG 的 CTX/STATIC 仍含 DFG 派生事实；S4m 的 CODE 仍为原名；全部只作描述）准确。

**结果：** 在 CODE 之上加入 CTX、STATIC，或把 concat 换成门控，在四个任务上都没有带来增益；差别对应每个任务约 6–14 个节点或 1 个合约文件。非 SolidiFI 重入节点上仍以 S2 最好。重入节点上去掉消息传递（S4-noG）明显变差。

**门控是否无效：** 现有证据不支持“门控坏了”。门控权重离开了均匀初值、随节点类型变化（CODE 约 0.36–0.50，CTX 约 0.25–0.44，STATIC 约 0.13–0.27），并没有塌缩。更可能的解释是：(1) CTX/STATIC 的信息与 CODE 和图消息传递冗余（CTX 描述的数据流与 G3R 的 DFG 边相同，STATIC 的多数事实在代码文本中可见）；(2) 原名视图下 SolidiFI 已饱和，评估无法分辨小增益。门控权重不等于贡献，有效贡献是门控权重 × 投影范数。NS-P6c 用已有 N-B 检查点做只读诊断来区分这两种解释。

**N-A 权重：** 用户说明是本人为节省空间主动删除；结果不受影响（见 NS-P6c 第 1 节）。

**NS-P7 暂缓：** S5–S8 会面对同样饱和的评估。建议先确定评估口径（视图、非 SolidiFI 终点、seed 数、类别），再决定是否进行 LLM 描述。

## 5P. NS-P6c 审查记录（2026-11-08，Claude）

**已核实正确：**
- 推理时移除：我用 removal_folds.csv 复算四任务、四种条件的折均 BF1 与改变数（例如重入节点 code_only 97.5653、323/11806 改变；no_static 99.7155、10 改变），与报告一致。full 条件与封存预测逐身份一致（最大概率误差 0），参数前后不变；用存在位置 0 而不是零向量，与训练时的 modality dropout 一致。
- 只评估 S4g、S4 单列为缺失：正确。S4 属于 N-A，模型已删除；NS-P6c 把 S4 写进来是我的表述错误。
- 报告拼装的重复关键字错误发生在写出前，v2 入口先断言两边样本数相同再合并，只重做报告：处理正确。CPU 探针改为并行调度、保留首轮现场并证明输出逐项相同：处理正确。
- Codex 对解读的保留（移除不等于重训消融；门控权重不等于贡献；探针是条件性描述）准确。

**需要修正（NS-P6c2）：** 冗余探针在全部节点上计算，混入了“识别节点种类”（K 只适用于状态声明、L 只适用于函数等）；CTX→STATIC 是构造使然。见第 5.9c2 节。

**目前可以得出的结论（我的判断）：**
1. 门控在机制上工作。模型在功能上使用了 CTX：去掉 CTX 会改变较多预测（重入节点 115 个）。STATIC 几乎没有被使用：去掉 STATIC 只改变 3–10 个节点或合约，其投影范数只有 CODE 的约 1/10–1/20（0.47–0.94 对 7.0–10.6），占范数份额 10%–18%。
2. 被使用不等于有额外价值：同时去掉 CTX 与 STATIC 会明显变差（重入节点 99.77→97.57），但只用 CODE 训练的 S2 本身就有 99.83。这是冗余与可替代的典型表现：模型在训练中依赖了 CTX，但 CODE 单独训练时可以达到同样的水平。
3. 值得注意的正面信号：在非 SolidiFI 节点上单独训练的线性探针中，STATIC 比 CODE 更强（重入节点 AUC 0.973 对 0.934，BF1 89.2 对 87.1；访问控制节点 AUC 0.722 对 0.580）。也就是说，在名字不能直接给出答案的部分，STATIC 含有有用的信号，但 HGT 模型没有用上它。可能的原因：(a) 训练数据中 99.5% 的正例来自 SolidiFI，原名下名字与模板已足以拟合，模型没有动力使用 STATIC；(b) STATIC 不做归一化（这是我的方案设定），投影后的范数远小于经 LayerNorm 的 CODE/CTX。这两点都是方案层面的问题，不是实现错误。NS-P6c2 的敏感性分析用于确认这一信号不是节点种类造成的。
4. NS-P7（LLM 描述）会再加入一种与 CODE/CTX 同类的文本模态，按目前证据很可能同样冗余。建议在 NS-P6c2 之后先做评估与训练信号的决定（匿名视图或非 SolidiFI 终点；STATIC 的尺度处理），再考虑 NS-P7。

## 5Q. NS-P6c2 审查记录（2026-11-08，Claude）

**结论：通过，不需要纠正。**

**复核：** 人群按 behavior_schema.applicable 与 facts.node_kind（按 row_key、文件、代码 SHA 对齐）筛选，取 1 比例在人群内计算；对照只含节点种类独热与 syntax 字段；探针算法、折、C 网格与 seed 未改。signal_summary.csv 与报告表一致。

**诊断阶段的结论（NS-P6c + NS-P6c2）：**
1. 按适用节点计算后，CODE 能以 AUC≥0.95 线性预测的 STATIC 位为 49%–63%（不是 NS-P6c 的 68%–78%）；CODE 比“节点种类 + 语法”对照平均高约 0.16 AUC。CODE 最难预测的组是 H（循环）、D（守卫）、C（顺序）、I、M、N：这些是依赖语句之外上下文（前置 require、modifier、CFG 顺序、循环边界、合约汇总）的事实，正是 STATIC 设计要补充的部分。
2. 非 SolidiFI 重入节点只保留语句/条件后，STATIC 的线性信号更强（AUC 0.994 对 CODE 0.926；BF1 88.2 对 86.1；CODE+STATIC 90.2）。需要注意：这类 STATIC 位（外部调用、调用后写状态）接近重入的定义，强信号部分是领域知识的直接编码。
3. 访问控制：全部节点时 STATIC 优于 CODE（AUC 0.722 对 0.580），但 20 个正例中 8 个是函数节点；只保留语句/条件（12 个正例）后，三种输入都接近随机（AUC 0.52–0.59）。访问控制的可用信号主要在函数级汇总（L 组），且样本很小。
4. 与 N-A/N-B/NS-P6c 合并：STATIC 含有 CODE 不具备、且与非 SolidiFI 标签相关的信息，但训练出的 HGT 几乎不使用它（移除只改变 3–10 个预测；投影范数约为 CODE 的 1/8–1/19）。两个待检验的原因是 STATIC 未归一化造成的尺度差，以及训练正例 99.5% 来自原名下可由名字/模板拟合的 SolidiFI。

**下一步（待用户决定）：**
- 方案一：按原计划进入 NS-P7（LLM 描述，本机试点）。按目前证据，新增的文本模态很可能与 CODE/CTX 一样冗余。
- 方案二（我的建议）：先做一个针对 STATIC 的小批次：S2+STATIC（STATIC 投影前加 LayerNorm 或可学习尺度）× G3R × 30 折，约 1.5–2 小时；预先登记非 SolidiFI 分层（重入节点 32 个正例）为共同终点，同时报告整体 BF1。若用户同意使用匿名视图，再加一组匿名 CODE + STATIC（STATIC 与视图无关，匿名 CODE 已在 NS-P2 编码，S0 可复用 8H），用来检验名字捷径去掉后 STATIC 是否发挥作用。

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
