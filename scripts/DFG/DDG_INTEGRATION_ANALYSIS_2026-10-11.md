# DDG 接入分析报告

- 分析日期：2026-10-11。
- 分析与编写 AI：Codex。
- 状态：**接入设计已分析，等待用户确认后实施。本文不是已实现功能说明。**
- 本轮范围：读取附件、两份方案、当前实现、历史实验记录与外部一手资料；只新增本报告和审查清单，不修改原算法、训练代码、标签、图或权重。
- 工作目录：/home/zhao/SmartContract/ge-sc-llm。
- 目录约定：采用已经存在的 scripts/DFG/，不另建仓库根目录 DFG/。
- 基线：当前工作树，而非干净的 upstream。当前已有构图、分类器等本地修改，实施时必须在其上做增量修改，不覆盖或回退既有工作。
- 当前 Git HEAD、阅读时关键文件 SHA256 见 [审查清单](audit/review_manifest_2026-10-11.json)。

## 1. 结论与用户要求的对应关系

本方案技术上可行。目标是向现有 HCG 增加函数内、语句级的直接定义—使用关系，不建立新变量图、不增加第二个 GNN、不更换 tokenizer、HGT 或标签体系。

~~~text
基础输入 G0 = (V, Ebase, X, Y)
增强输入 G1 = (V, Ebase ∪ Edata, X, Y)
~~~

严格固定 V 的身份、顺序、节点类型、文件归属、源码位置、特征和标签；Ebase 的边类型、端点、平行边重数也保留。唯一算法变量是额外的 Edata。增加 canonical relation 会增加 HGT 关系参数，不能声称模型参数量完全不变。

建议采用以下接入：

1. scripts/DFG/ 中实现独立的源码分析、语义 CFG、到达定义、节点投影和附边工具。
2. 对已有冻结图附边，保留全部节点、特征和标签。新图写入 DFG 自己的产物目录，不覆盖原图。
3. 原项目**预计只需修改 sco_models/graph_utils.py 的 reflect_graph 一个函数**：两个保留的 DDG 关系不再被同名反射。其他原关系保持逐项原行为。
4. 第一阶段完成固定图上的合约分类、节点分类和 checkpoint 复评接入。任意新合约的端到端级联预测存在额外接口限制，不能顺便宣称已支持。
5. 首先验证依赖正确性、节点投影和加载后方向，再运行训练；不以提高或降低 F1 代替正确性验收。

依据是 [原详细指南](MANDO_LLM_DDG_Code_Design_Guide.md)、[第一阶段文字说明](MANDO_LLM_第一阶段_DFG融合_方案文字说明.md) 和本次附件。附件第 20 节要求“等待我确认后再开始实现”；所以本文列出的模块、接口和测试均为拟实施项目。

## 2. 当前项目的实际调用链（A）

### 2.1 不应把所有名为 CFG 的文件当作纯 CFG

当前 tree-sitter 路线在 CFGGraph_solidity 内同时增加控制流连接和部分调用相关连接（L476 扫描函数，L501–503 附加 dummy/call 边）。它没有完整照搬前身“独立生成 CG、再与 CFG 融合”的调用链。文件夹名 cfg 不能直接判定图里没有调用关系。

论文描述 AST→CFG/CG→融合图，是方法层面的描述；当前代码怎样实现，要看实际入口和边属性。论文的构图说明见 [MANDO-LLM §5.1](https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf)。

| 环节 | 当前真实位置 | 与 DDG 有关的实际行为 |
|---|---|---|
| 批量源码入口 | [gen_reentrancy_cfg.py](../gen_reentrancy_cfg.py)，main，L69 起 | 遍历 .sol，调用 generate_cfg_from_file，再写单文件 DOT/gpickle |
| 文件／字符串入口 | [generator.py](../../process_graphs/tree_sitter_codeviews/generator.py)，generate_cfg_from_source / generate_cfg_from_file，L41、50 | 通过现有 CFG driver 构图，并补 source_file、code、edge_type 等字段 |
| 预处理 | [parser_driver.py](../../process_graphs/tree_sitter_codeviews/tree_parser/parser_driver.py)，L25；[preprocessor.py](../../process_graphs/tree_sitter_codeviews/utils/preprocessor.py) | 去空行、去注释会改变字符、字节和行坐标；现有节点位置首先属于预处理文本 |
| 语法树与 AST ID | [custom_parser.py](../../process_graphs/tree_sitter_codeviews/tree_parser/custom_parser.py)，L97–114 | tree-sitter 解析 UTF-8；named node 遍历从 5 开始编号；索引键是 start_point、end_point、AST type |
| Solidity 节点内容 | [solidity_nodes.py](../../process_graphs/tree_sitter_codeviews/utils/solidity_nodes.py) | 生成声明、函数、语句等不同类型；函数节点 code 可能包含整个函数体 |
| 控制流与调用相关边 | [CFG_solidity.py](../../process_graphs/tree_sitter_codeviews/codeviews/CFG/CFG_solidity.py) | 函数内分支／循环与 add_dummy_edges、add_function_call_edges 位于同一构图器；函数入口附近也有非真实调用的归属连接 |
| NetworkX 图 | [CFG.py](../../process_graphs/tree_sitter_codeviews/codeviews/CFG/CFG.py) 及 generator | 中间图使用 MultiDiGraph；允许同端点不同关系以及平行边 |
| 节点字段和边字段规范化 | [generator.py](../../process_graphs/tree_sitter_codeviews/generator.py)，_annotate_cfg_graph，L17 | 图上使用 node_type、source_file、code、node_source_code_lines；边最终必须有 edge_type |
| 加标签、汇总多个文件 | [build_labeled_graph.py](../build_labeled_graph.py)，main，L168 起 | 读取单文件图，按策略映射标签，多文件不相交合并会再次编号；不是增加 DDG 的地方 |
| 后续标签版本 | [labeling_v2/build.py](../labeling_v2/build.py)，L72–106；[label_pipeline/build_dataset.py](../../Test_code/label_pipeline/build_dataset.py)，L140–212 | 读取已有图改标签；后者明确 graph_was_regenerated=False，并另存 line_node_ids.json；前者采用 original_node_id，适配时不能混为同一格式 |
| token 特征 | [encode_tokenizer_features.py](../encode_tokenizer_features.py)，L98–135 | 读取节点 code，生成 token 数组写回同一个 node_id；当前常用 CodeT5p-770m 的 512 长度 token ID |
| 行级输入 | [make_linelevel_graphs.sh](../make_linelevel_graphs.sh) → [filter_buggy_contracts.py](../filter_buggy_contracts.py) | 取漏洞文件对应子图；与合约级图的样本范围不同，需要各自冻结身份和顺序 |

训练用的“大图”通常包含多个源文件的互不相交图。一个 source_file 还可能声明多个 Solidity contract，所以“文件样本”和“语言中的合约声明”必须分开记录。

前身 Slither 路线实存在同级 ge-sc-transformer 的 control_flow_graph_generator.py、call_graph_generator.py、combination_call_graph_and_control_flow_graph_helper.py。当前 ge-sc-llm 的 slither_reader.py 不能当成这整套构图流程。第一阶段不切换到前身构图器。

### 2.2 ID 至少存在三层，不是一个整数通用到底

1. 单文件 AST ID：对预处理后的语法树遍历得到；只在相同源码、预处理器和语法版本下可复现。
2. 汇总图的 NetworkX ID：多个文件合并后可以重编号，不等于 AST ID。
3. 训练加载后的全局整数 ID、每类型局部 ID：load_hetero_nx_graph 再次编号，add_hetero_ids 建立节点类型内 ID。

因此侧表必须明确记录：

~~~text
file identity + raw source digest
  ↔ original source byte span / syntax role
  ↔ preprocessed AST anchor
  ↔ frozen NetworkX node ID + iteration position
  ↔ model global ID + type-local ID
~~~

不能把“同样叫 31 的节点”跨文件、跨图版本直接视为同一节点。不能把节点 ID 当源码行号。

### 2.3 图进入模型的链路

| 环节 | 当前位置 | 接入要求 |
|---|---|---|
| 加载及重编号 | [graph_utils.py](../../sco_models/graph_utils.py)，read_gpickle / load_hetero_nx_graph，L335、342 | 保留既有节点迭代顺序；不在增强器中再随意 relabel |
| 类型内 ID | 同文件 add_hetero_ids，L13 | 特征、标签、输出散回都依赖这套映射 |
| 元关系构建 | 同文件 generate_hetero_graph_data，L361 | 每条边按 (src.node_type, edge_type, dst.node_type) 分类 |
| 补反向边 | 同文件 reflect_graph，L426 | 当前所有关系都同名补反向，必须对 DDG 适配 |
| 节点模型 | [model_hgt.py](../../sco_models/model_hgt.py)，HGTVulNodeClassifier，L217 起 | L238 反射，L241 构 DGL 图，L258 建关系字典，L320 读 inside_token |
| 合约模型 | 同文件 HGTVulGraphClassifier，L435 起 | L459 反射，L462 构 DGL 图，L484 建关系字典，L533 读 inside_token |
| 关系参数 | 同文件 HGTLayer，L45–70 | 按 canonical triple 数量分配参数，而不是只按 edge_type 字符串个数 |
| 节点输出顺序 | 同文件 forward，L420 | 按 node_ids_dict 散回全局节点顺序 |
| 合约输出 | 同文件 forward，L590 | 按 source_file 集合汇聚节点并分类 |
| 节点监督 | [graph_utils.py](../../sco_models/graph_utils.py)，get_node_label，L174 | 读取 node_info_vulnerabilities；现有实现对 None 和非 None 的区分必须保持，不能私自把空列表与 None 互换 |
| 合约监督 | [dataloader.py](../../sco_models/dataloader.py)，L36 起 | 单独 JSON 中 contract_name / targets，DDG 不改该文件 |

inside_token 分支实际按输入 tensor 最后一维读取维度，不能只看残留的 embedding_dim=512 就断言代码强制了 512。DDG 的前置审计应显式要求当前实验 token.shape=(512,)，并验证内容、dtype 不变。DDG 阶段不重新执行 tokenizer。

### 2.4 序列化和信任边界

原批量入口使用 nx.write_gpickle；原训练加载器仍有普通 pickle 路径。DFG 产物建议复用 [safe_graph.py](../labeling_v2/safe_graph.py) 的受限 read_graph 和 protocol 4 write_graph：

- 输入必须通过图类型、字段和特征审计。
- 输出保留 MultiDiGraph，不转为会覆盖同端点关系的 DiGraph。
- write_graph 使用 xb，默认拒绝覆盖原文件。
- 图内新元数据只用基础 dict/list/string/number。
- 自定义 Definition/Use 对象、AST 对象不写进图 pickle；写成独立 JSON/JSONL 侧表。
- 安全加载不是本轮 DDG 的创新点；不因此大规模重写原 loader。

## 3. 本轮已核实的关键风险（D）

### 3.1 原 DFG 不是目标算法的完成实现

[DFG_solidity.py](../../process_graphs/tree_sitter_codeviews/codeviews/DFG/DFG_solidity.py) 中仍调用 DFG_java，存在 Java 声明节点名和按变量文本管理状态的逻辑；部分循环固定遍历两次。[DFG.py](../../process_graphs/tree_sitter_codeviews/codeviews/DFG/DFG.py) 还有按首行选 nodes[0] 的投影。

它可以提供历史实现参考，但不能直接更改关系名后作为具备作用域、覆盖定义和固定点保证的 Solidity DDG。本次拟新建模块，保留旧实现不动。

### 3.2 原训练 HCG 不能直接充当到达定义的语义 CFG：已在内存验证

本轮没有写图或训练，只调用现有 generate_cfg_from_source 处理以下小例：

~~~solidity
pragma solidity ^0.4.25;
contract C {
    function f(uint x, bool flag) public returns (uint) {
        if (flag) {
            return x;
        }
        x = 2;
        return x;
    }
}
~~~

当前输出包含：

~~~text
return x;  --next-->  end_if  --next-->  x = 2;
~~~

本次样例的相关节点 ID 为 32→64→34。它把已经返回的分支接入后继语句，不能解释为真实执行路径。另有声明归属连接被命名为 recursive_method_call，也不能直接当函数调用 CFG 边使用。

**处理方案：在 DFG 模块内建立经测试的函数内语义／事件 CFG，使用原 AST 和既有节点身份作为来源；不直接在已融合、已反射的训练大图上计算 RD。** 不在 DDG 对照中顺便修复原 HCG 的旧边，否则无法隔离新增 DDG 的贡献。内部分析允许辅助节点和出口；最终模型图仍不新增节点。

### 3.3 方向必须在 DGL 加载后验收

如果只向 gpickle 添加 DATA_DEF_USE，现有 reflect_graph 会产生同名反向边，E1 实际变成双向。添加 REV_DATA_DEF_USE 也不能解决，因为两类又会分别被反射。

验收必须检查进入模型的 canonical relations 和边 tensor，而不仅检查保存前的 NetworkX 图。

### 3.4 源码预处理不是坐标恒等变换

去注释、空行会改变行号及 UTF-8 byte offset。标签中的 node_source_code_lines 还可能是全范围、端点或经过本地窄化的版本，不能用它独自建立语义节点身份。

建议区分两个视图：

- 原源码视图：确定 pragma、声明绑定、读写事件和实际字节范围。
- 兼容视图：按基线生成器和 grammar 重现预处理 AST，用于恢复现有图的 AST anchor、类型与文本对应。

两者必须由可核验的 token／区间映射连接。[现有 coordinates.py](../../Test_code/label_pipeline/coordinates.py) L94–138 只提供预处理文本及行来源映射，不能冒充完整的 UTF-8 字节对应表。转换需要处理 Unicode、多行注释、字符串中的注释样式、CRLF。同一行可能有多个语句；只按行号或最近位置匹配必须拒绝。预处理改变了可执行 token、解析有 ERROR/MISSING 或匹配歧义时，保留原图并报告失败，不猜测。

### 3.5 现有源码库的版本语义不能忽略

Solidity 0.4 普通模式与 0.5 之后的局部作用域不同。0.4 还可能通过 experimental v0.5.0 改变语义。版本信息不仅是编译问题，也是 symbol table 和默认定义位置的依据。

不能机械实施“所有局部变量声明处默认初始化、所有大括号独立作用域”。具体适配见第 5 节。

### 3.6 作者图已有投影可行性证据，但不是全七类验收

本轮只读核验了作者融合图与本地 narrow 图的身份对齐：

- 重入：18,312 个节点可以按文件、节点类型、规范化文本、AST anchor 对齐。
- 访问控制：13,432 个节点可以按同一规则对齐。
- 上述对齐同时检查无类型边端点和重数；不表示原始边类型相同。
- 对 buggy_18.sol 额外重解析：重入的 383 个普通 AST 节点、访问控制的 273 个普通节点，与作者图中的 AST ID、文本、端点相符。
- 同一文件还有 41／11 个合成节点，不能要求存在普通 AST anchor，也不应复制所属语句的全部 DEF/USE 给它们。

对齐使用 [label_rules.align_graphs](../labeling_v2/label_rules.py) L68–95 的明确身份规则。一个实际例子是重入 buggy_18.sol 的 c = a + b;：AST anchor=31，作者图 ID=2646，本地 narrow ID=8227，预处理 byte [117,127)，原源码第 24 行。作者节点 code 有 DOT 外层引号，行字段为 [[4,4]]；本地图 code 没有外层引号，行字段为 [4]。投影可以在侧表规范化比较，但不能因此改写原节点属性。

这证明可以设计“作者图保持原标签，仅附边”的路径；尚未对全部文件、全部七类做重解析，不承诺所有节点都可唯一投影。

函数／合约容器节点的 code 包含内部全文，不能递归扫描其 code 再把整个函数体的读写算到容器上。函数入口只承接相应入口定义，条件节点只承接条件表达式事件；end_if/end_loop 等合成节点通常没有语义变量访问。

### 3.7 环境前置条件已查清，不应重复修编译问题

当前 mando 环境是 Python 3.7.12。已有：

- process_graphs/tree_sitter_codeviews/build/my-languages.so：Mach-O，不能作为 Linux ELF 加载。
- build/linux-x86_64/my-languages.so：现成 Linux ELF，可用于本次内存验证。

因此未来入口应检查并设置 TREE_SITTER_LIB_DIR 指向现有 Linux 库，记录库和 grammar 摘要；不默认覆盖仓库库文件。新模块必须兼容 Python 3.7，不能直接复制指南中 str | None 或 list[str] 等新版本语法。

## 4. 完整数据流（C）

~~~mermaid
flowchart TD
    A[冻结的源码与现有 HCG] --> B[源码版本和摘要核验]
    B --> C[原源码 AST 与作用域]
    B --> P[兼容预处理 AST 与原节点对应表]
    C --> D[定义和使用事件]
    D --> E[函数内语义事件 CFG]
    E --> F[到达定义固定点]
    F --> G[直接 def-use facts]
    G --> H[唯一投影到原 HCG 节点]
    P --> H
    H --> I[合并同关系同端点事实]
    I --> J[仅附加 DATA_DEF_USE]
    J --> K[可选显式 REV_DATA_DEF_USE]
    K --> L[增强 MultiDiGraph 与审计侧表]
    L --> M[原 meta-relation 提取]
    M --> N[基础边反射 DDG 保持方向]
    N --> O[原 HGT 与原分类器]
~~~

标签、token 和基础边从冻结图直接保留，不参与 DEF/USE 或边生成。meta-relation 提取发生在附边之后。内部分析 CFG、模型中的 HCG、HGT 反向消息边是三种不同对象。

首阶段推荐以已有、已经带 token 的图为输入做离线增强，这样不需要重跑标注和编码。在增强后的合约级图派生行级输入时，必须保持既有行级文件清单及顺序；对历史单独编号的行级图，通过显式节点映射转移 DDG，不能盲目再调用会重编号的过滤脚本。节点正例数为零、但独立合约标签为漏洞的文件也必须保留，不能用“是否含正节点”擅自重定义文件样本集合。

## 5. 第一阶段语义范围与必要调整

### 5.1 支持范围

| 项目 | 第一版要求 |
|---|---|
| 标量局部变量、参数、命名返回变量 | 用声明身份解析，不按同名字符串合并 |
| 普通赋值与纯二元表达式 | 读取 RHS 的旧定义，然后生成 LHS 新定义 |
| 复合赋值、独立 ++/-- | 读取旧值，再建立新定义 |
| if/else 合流 | 对可能前驱求并集；只有部分路径覆盖时保留旧定义 |
| while/for/do-while | 明确初始化、条件、更新、零次／至少一次路径，工作队列至固定点 |
| break/continue | 分别连接循环出口、更新或条件位置，区别 for 与 while |
| require/assert、return | 提取条件或返回值读取，区分正常继续与异常／返回终止 |
| tuple | 先支持无副作用的值类型赋值及声明；保留位置对应和省略项 |
| 短路和三元表达式 | 纯读取可分析；带写入时建立内部分支，否则明确回退，不顺序展开假定全部执行 |
| 状态、mapping、数组和引用 | 记录未知访问，不冒用局部标量的 KILL；不宣称支持完整别名分析 |
| assembly、未知控制结构、版本歧义、复杂副作用 | 该函数回退原图，不输出未经确认的部分依赖 |
| modifier、继承造成的绑定／控制影响 | 需要明确适配；首版无法可靠解析时回退，不忽略其存在 |

对于 a = stateValue，虽然状态变量的来源暂未解析，a 的这次确定赋值仍然创建新定义并覆盖旧 a；可以不生成 stateValue 的来源边，但不能漏掉对 a 的覆盖，否则后续会错误连接旧定义。

函数调用只分析调用点的已知实参读取和正常返回后的局部写入，不凭名称生成跨函数依赖。msg.sender 等环境值、owner 等状态读可以记录为外部／未支持访问，但不伪造它们的函数内定义。

### 5.2 版本敏感的作用域与默认初始化

| 版本模式 | 处理方式 |
|---|---|
| 普通 Solidity <0.5 | 局部声明具有函数级作用域；预扫描声明并建立入口默认定义；显式初始化仍在声明语句执行时发生 |
| Solidity >=0.5 | 声明后到所属块末可见；for 初始化声明的作用域包括循环本身 |
| 0.4 experimental v0.5.0 | 识别 pragma，按相应作用域模式处理 |
| 缺失／跨版本 pragma | 优先使用冻结的版本清单或显式配置；不能确认则标记 version_semantics_ambiguous 并回退 |

参数以函数入口为定义；命名返回变量有入口默认值。显式 return; 会读取命名返回值。隐式结束返回可在内部 CFG 建模，但如果没有对应的原图出口节点，应记录 unprojectable，不能为了画边新增模型节点或把出口强映射到入口。

上述调整依据 Solidity 官方 [0.4.26 作用域说明](https://docs.soliditylang.org/en/v0.4.26/control-structures.html#scoping-and-declarations) 和 [0.5.17 控制结构说明](https://docs.soliditylang.org/en/v0.5.17/control-structures.html)。这不是额外追求功能，而是避免对本数据集里的旧合约产生错误依赖。

### 5.3 内部模型与固定点

拟使用 Python 3.7 可表示的记录：

- SourceIdentity：相对路径、源码 SHA256、版本模式、语法版本。
- Symbol：声明身份、作用域、类型／种类、原始字节区间。
- Definition：预先分配的 def_id、symbol_id、event_id、定义种类、可选 hcg_node_id。
- Use：use_id、symbol_id、event_id、读取位置。
- AnalysisBlock：事件顺序、语义前驱和后继；不接受模型反向边。
- DependencyFact：def_id、use_id、symbol_id、投影状态、两个冻结图节点 ID。

symbol_id 至少含文件身份、合约／函数声明身份、作用域和声明 span。重载函数不能仅用函数名区分；用声明 span 或完整签名身份。

~~~text
IN[b]  = union(OUT[p] for p in semantic_predecessors[b])
OUT[b] = GEN[b] union (IN[b] - KILL[b])
~~~

内部事件的每次静态写入在分析前固定 def_id；不能每次循环迭代重新造 ID。仅从函数入口传播到可达块，不让不可达块的 GEN 污染结果。同一块按事件顺序处理，每次 use 查看当时的定义集合。循环至状态不再变化；若设置资源上限，超限必须报告并回退，不能把未收敛结果当成功。

这里得到的是 CFG 上可能到达的直接依赖，不是路径可行性或漏洞可利用性的证明。第一版不做传递闭包、不做 taint closure、不把控制依赖混成数据依赖。

Solidity 一般表达式的子项求值顺序并非全部保证从左到右。对于 f(x++, x) 等相互影响的副作用，不得照 AST children 顺序杜撰唯一执行语义。规则依据 [Solidity 表达式求值顺序](https://docs.soliditylang.org/en/v0.5.17/control-structures.html#order-of-evaluation-of-expressions)。

## 6. 节点投影、附边与审计规则

1. 每次分析都核对原始源码摘要，不能只用 basename 查文件。相同文件名不同路径要有稳定 source identity。
2. 先解析原源码语义，再重现兼容 AST anchor。优先匹配明确 AST 身份，否则用函数、语法角色、精确区间和规范化文本联合确认。
3. 普通语句只归属最具体的执行节点；函数容器、if 条件、loop 更新表达式分别处理。
4. 只给两个端点都唯一匹配、处于同一文件和同一函数的 facts 生成模型边。
5. 以 (src, DATA_DEF_USE, dst) 去重；多个 symbol facts 留在侧表。
6. 不改变已有 CFG/CG 同端点边，不清理其平行边或 self-loop。
7. 首版不输出投影后 DDG self-loop；同语句内部 facts 保留并单独计数。
8. E2 由构建器显式产生 (dst, REV_DATA_DEF_USE, src)，该边不返回分析 CFG。
9. source_file、node_type、code、token、node_info_vulnerabilities、所有源码位置字段及迭代顺序逐项不变。
10. 改变／删除漏洞标签后的相同源码分析，应产生完全相同 DDG；可作为防止标签泄漏的测试。
11. 新图已经含 DDG 时默认拒绝重复增强；只有明确的重建模式才删除旧模块边并根据来源摘要重算。
12. sidecar 与增强图绑定输入图摘要、源码摘要、模块版本和配置，不只靠文件名识别。

stats 至少包括：原节点／边数、按原 edge_type 的计数、新增 DDG 边数、canonical relation 数、函数总数／支持数／回退数、定义与使用数、已解决使用比例、投影成功比例、函数／文件覆盖率、未解析符号、未知存储访问、内部自环 facts、重复 facts、耗时。

当前图的若干边类型存在归属或调用语义混用，不能可靠归类的基础边应列为 ambiguous/other；不要把它们强行计入“精确 CFG 数／CG 数”，也不要用 0 表示无法确定。DDG coverage 必须给分子、分母，不能只报一个不明含义的百分比。

## 7. 拟新增文件与最小原文件修改（B）

以下为建议组织，不要求逐个文件先建空壳。实现时可在保持职责清晰的前提下合并相邻小模块。

~~~text
scripts/DFG/
  MANDO_LLM_DDG_Code_Design_Guide.md                 # 保留
  MANDO_LLM_第一阶段_DFG融合_方案文字说明.md          # 保留
  DDG_INTEGRATION_ANALYSIS_2026-10-11.md              # 本报告
  audit/review_manifest_2026-10-11.json               # 本轮只读清单
  __init__.py                                       # 待实现
  models.py                                         # 身份、事件、fact、诊断
  frontend.py                                       # parser/版本/双视图/稳定坐标
  symbol_table.py                                   # 声明绑定与作用域
  access_extractor.py                               # 读取和定义事件
  semantic_cfg.py                                   # 函数内执行路径
  reaching_definitions.py                           # 固定点求解
  projection.py                                    # facts 到冻结 HCG 节点
  ddg_builder.py                                   # 附边、去重、可选反向
  graph_audit.py                                   # 不变量、模式、schema核验
  cli.py                                           # 离线增强与调试导出
  run_experiment.py                                # 显式配置、预检、复用原训练器
  tests/
    fixtures/                                      # 人工可解释 Solidity 小例
    test_symbols_and_versions.py
    test_def_use.py
    test_semantic_cfg.py
    test_reaching_definitions.py
    test_projection_and_invariants.py
    test_model_integration.py
  artifacts/<run_id>/                               # 新图、侧表、配置、统计
  training_runs/<run_id>/                           # 后续日志、权重、评分
  IMPLEMENTATION_NOTES.md                           # 实施时再建，记录真实修改
~~~

### 7.1 推荐：只改一个原函数

**文件：sco_models/graph_utils.py，reflect_graph。**

目的：当 canonical relation 中的 edge_type 精确等于 DATA_DEF_USE 或 REV_DATA_DEF_USE 时原样保留方向；其他关系执行原逻辑。

~~~text
保留关系 → 保持输入方向
其他关系 → 原有 reflect_graph 行为，逐项不变
~~~

可以采用可选 directed_relations 参数，但现有调用不传参，因此默认必须包含所约定的保留关系，或者显式从统一配置接入。不要只增加一个无人传入的参数就认为已经适配。

由 DFG 构建器决定是否生成 REV；reflect_graph 不替它创建。节点构造、合约构造和 extend_forward 三处已有调用可保持不变。将来实施时用明确 Codex 日期标记和原片段注释记录改动，避免引入训练算法修改。

增强图的 graph 元数据本身不会被现有模型自动读取，因此只写 ddg_mode=forward 不能保护方向。DFG 的预检入口必须验证有效适配版本及实际加载后边。

### 7.2 明确不需要修改的文件或功能

- 原 CFG_solidity.py、solidity_nodes.py、generator.py：第一阶段通过旁路分析、侧表投影附边，不重新设计原基础图。
- 原 DFG_solidity.py、DFG.py：保留，新增模块不依赖其近似算法的正确性。
- HGTLayer、HGT、分类头和 pooling：不重写。
- 原 tokenizer 编码器、模型名称、512 长度输入：不修改。
- 原标签构建器、CSV、vulnerabilities.json、合约 JSON：不修改。
- 当前早停、学习率、best/last 保存、梯度修复：本轮不调整。
- 现有训练图、作者图、权重、训练日志：不覆盖。
- HANDOVER.md、原两份设计文档和已有训练改动文档：本轮不修改；新增 DFG 分析和后续实施记录放本目录。

### 7.3 零修改原文件的备选及其限制

专用 DFG runner 可以在进程中替换 model_hgt 已导入的 reflect_graph，然后调用原训练器。但直接运行旧脚本或独立评估脚本会漏掉适配，默默改变方向。

因此它只作为确实要求零修改原文件时的备选，不作为推荐长期实现。相比之下，中央一个函数的精确分支更容易让训练、加载和复评保持一致。

## 8. 与训练、权重及推理的边界

### 8.1 当前训练配置要显式继承，不依赖入口默认值

scripts/train_contractlevel.sh 与 train_linelevel.sh 当前显式设置 50 epochs、patience=7、seed=1，分别为 5 折和 10 折；CLI 本身的 epoch 默认不相同。两脚本还存在重入路径默认值。

新 runner 应显式记录任务、漏洞类别、输入图、source manifest、contract label JSON、token 模式、折清单、epoch、patience、delta、LR 调度、best/last 策略及输出路径，复用现有训练逻辑，不硬编码重入数据目录。所有新输出放 DFG 下，保持实时 stdout/log 信息。

### 8.2 相同 seed 不等于共同参数初值相同

新增 canonical relations 会改变参数张量数量和随机数消耗。E0/E1/E2 应按语义三元组对齐共同关系参数，并对其他共同参数复制同一初始化、检查 hash；新增关系单独初始化。

可借鉴 [现有固定折实验初始化对齐](../reentrancy_ablation/run_experiment.py) 的方式，但不硬耦合其中的 A_author 路径或旧训练配置。记录关系数、参数量、共同参数初始摘要。

共同初始化必须在**每折模型构造时**执行：node_classifier.py L256、graph_classifier.py L191 都会每折重新创建模型，仅在调用原 main() 前初始化一次无效。DFG runner 需要通过模型构造适配或独立的每折控制完成参数复制，并确保 checkpoint 复评时不会再次初始化而覆盖已加载权重。

### 8.3 checkpoint 必须绑定 schema

当前 state_dict 不等于完整的节点／关系字典。关系数量相同但顺序或语义改变时，加载成功也可能使用错误参数。

DFG 产物需另存：

- ntypes_dict 与 ordered canonical etypes_dict；
- 原图／增强图、token、标签、fold 的摘要；
- DDG 算法与反向适配版本；
- 模式 E0/E1/E2、语义范围和 tokenizer 配置；
- checkpoint 对应的训练配置。

旧图 checkpoint 不能直接视作增强模型。实验中的共同初始化不等于在新图上使用旧训练结果。

### 8.4 第一阶段不承诺任意新合约级联推理

当前 HGTVulNodeClassifier.extend_forward 在新图特征方面主要实现 nodetype 分支，并会拒绝未见节点类型／canonical relation。inside_token 的任意新图路径不是本轮可以默认使用的完整接口。

本轮计划验收“固定增强图上的训练与 checkpoint 复评”。如果后续扩展源码级 cascade，需统一 tokenizer、原图节点规则、schema 和未知关系策略，单独列出范围。测试时临时增加未经训练的新关系参数不可接受。

固定图 K 折使用全图预先确定关系 schema 属于现有协议的一部分，需要如实记录；这不自动等同于对未知项目的归纳推理。更严格的训练集限定 schema 应作为另列实验，不能只对 E1 改协议。

## 9. 验证计划与验收门槛

### 9.1 算法测试：预先手写预期关系

必须包含附件提出的普通赋值、覆盖、分支、循环、复合赋值、自增减、参数、返回、shadowing、作用域、边去重、多关系共存、反向隔离和不支持语法回退。

额外补充下列实际需要：

| 小例 | 要验证的关键行为 |
|---|---|
| x=1; x=2; use(x); | 第一份定义被 kill，只连第二份 |
| 仅 if 真分支覆盖 | 合流后旧、新定义都可能到达 |
| if 两分支均覆盖 | 合流后不再保留进入 if 前旧定义 |
| 分支 return 后再赋值 | 返回分支不通往后续语句 |
| 循环需多轮传播的 CFG | 真正收敛；不固定迭代两次 |
| for 中 continue | 经过更新表达式再回条件 |
| do-while | 区别 while 的零次迭代路径 |
| 两个函数／重载同名变量 | 不跨声明、跨文件连边 |
| 0.4 先使用、后声明 | 绑定函数入口默认定义，不连向未来初始化 |
| 0.4 experimental v0.5.0 | 识别作用域模式差异 |
| (x,y)=(y,x) | RHS 使用更新前的定义，不顺序串改 |
| return; 与命名返回变量 | 读取相应最新定义 |
| f(x++,x) | 不强制无依据的从左至右求值 |
| Unicode、CRLF、字符串注释样式 | 字节坐标与投影准确 |
| 同行多个语句 | 不按第一个行号匹配 |
| 标签删除／打乱 | DDG facts 和边不变 |
| 同端点 CFG、DDG、多个变量 facts | CFG 保留，DDG 模型边仅一条，facts 均可追踪 |
| unsupported 函数 | 原节点、原边、原标签和样本集合完整保留 |

### 9.2 构图和模型集成验收

- 单元测试通过后才做数据集附边和训练。
- E0 经过新增工具与接入 hook 后，节点、边 multiset、类型字典、特征、标签和相同初始权重下的 eval logits 与原入口一致。
- E1 加载到 DGL 后，只有定义→使用的 DATA_DEF_USE；E2 的相反方向单独属于 REV_DATA_DEF_USE。
- 不新增跨文件、跨函数依赖，不打通原本隔离的训练／验证文件。
- 分别验证节点模型和合约模型的前向、loss backward、关系参数梯度和保存／重载结果。
- 验证无 DDG 的文件、孤立节点、仅有未知存储访问的函数仍能完整训练。
- 先少量真实合约，再重入和访问控制两类，最后推广其他类别；分析器不写漏洞类型特例。
- 人工抽查已投影边，并报告分析覆盖率；Slither 对照只在共同可编译样本上做，不把编译失败样本从主实验悄悄删除。

### 9.3 训练消融与评分

主实验 E0／E1／E2 采用同一冻结图及标签体系、文件清单、折清单、token 和训练设置。用当前 best 选轮规则作为预先确定主结果，last 另列，不按更高分切换。

作者图标签与本地标签可分别构成两套明确的对照，不能混合不同标签的分数后声称增益。先保持原节点 Buggy-F1／Macro-F1 计分口径；源码物理行去重指标如以后增加，应单独命名和报告，不能替换原指标后直接对比论文表格。

附带报告：

- 按 SolidiFI／真实漏洞来源拆分的结果；
- 每折配对变化、多随机种子稳定性、TP/FP/FN；
- DDG 覆盖率、边准确性抽查、时间和参数开销；
- 与 DDG 关系配置、边量及端点类型尽量匹配的随机边对照；
- 若测试泛化，另列完整合约的克隆／模板家族隔离协议，不能把本地 snippet 划分直接等同于无模板重合。

总体 99 分不能作为标签正确的证据，也不能为制造提升空间反向改标签。当前标签未完全恢复不阻碍固定作者标签的相对对照，但不能因此证明作者标签语义正确。

Dataset B 可作为后续更广评估，目前不能当成已经对齐、可直接训练的输入。此次新发现作者 [DASP-DAppSCAN-datasets](https://github.com/MANDO-Project/DASP-DAppSCAN-datasets) 含映射和整理标签，完整混合清单、图及 Table 2 对齐仍应单独审计，不扩大本轮 DDG 实施范围。

## 10. 外部方案与代码参考：借鉴点和不能照搬之处

| 一手资料 | 本次借鉴点 | 不作的推断 |
|---|---|---|
| [MANDO-LLM 论文](https://daoyuan14.github.io/papers/TOSEM25_MANDO-LLM.pdf) 与 [HGT 实现](https://github.com/MANDO-Project/ge-sc-llm/blob/TOSEM-release/sco_models/model_hgt.py) | 保留 CFG/CG、元关系、原特征及两种分类任务 | 论文没有实现本方案 DDG，也不证明新增边必然提高 F1 |
| [MANDO 原论文结论](https://hoanghnguyen.com/assets/pdf/nguyen2022dsaa.pdf) | 作者把数据依赖列为未来可增加的语义信息 | 这支持研究方向，不等于本方案自动具备充分创新性 |
| [GraphCodeBERT 论文](https://arxiv.org/abs/2009.08366) | 数据流能作为代码表示的结构信息；其评测针对自身任务 | 不将其结果直接套用到 Solidity 漏洞定位 |
| [GraphCodeBERT DFG.py](https://github.com/microsoft/CodeBERT/blob/master/GraphCodeBERT/codesearch/parser/DFG.py) | token／源码位置对齐与结构提取方式 | 其名字状态、部分两遍循环以及变量出现节点不等于本方案语句级固定点 RD |
| [SlithIR 文档](https://github.com/crytic/slither/wiki/SlithIR) | 操作读取、lvalue、临时变量、引用变量的区分；可编译小例的交叉核验 | 不把 Slither 当默认依赖，也不把它称为本任务绝对真值或效果上限 |
| [Slither data_dependency.py](https://github.com/crytic/slither/blob/master/slither/analyses/data_dependency/data_dependency.py) | 核实变量依赖 API 的真实语义与传递闭包 | 不直接将 transitive dependencies 重命名为直接语句 DATA_DEF_USE |
| [Solidity 0.4.26](https://docs.soliditylang.org/en/v0.4.26/control-structures.html) 与 [0.5.17](https://docs.soliditylang.org/en/v0.5.17/control-structures.html) | 版本敏感作用域、默认值、tuple、终止及求值顺序 | tree-sitter 解析成功不代表版本语义已确定 |

函数内局部 DDG 本身不是完整的重入机制建模：storage、跨函数状态、回调与权限控制依赖仍有边界。第一阶段的研究问题是“这些经过验证的额外直接依赖是否有帮助”，不能预先承诺七类都提升。

## 11. 两份原设计文档的调整清单

本轮只在报告中说明，不改动原文：

1. 统一第一阶段范围：采用附件及短文档的函数内标量、参数、命名返回值范围；长文档中状态／mapping“第一阶段必做”与后文“后续支持”的冲突按此收敛。
2. 将“节点数基本一致”提高为节点身份、顺序、属性、特征、标签完全一致。
3. 将整节点 GEN/USE 伪码落实为有序事件，防止同语句读旧写新的歧义。
4. 加入 Solidity 版本语义，修正“一律声明处默认定义”的不足。
5. 将“取原 CFG”具体化为独立验证的语义 CFG；已有 return 路径问题已复现。
6. 将“加边后 HGT 自适应”具体化为反射 hook、canonical schema 与 checkpoint 兼容校验。
7. 补齐作者图／本地图的节点侧表，不重做漏洞标签来解决投影。
8. 区分固定图训练可用与任意源码级联预测可用。
9. 将推理未知关系默认处理写为明确拒绝和诊断；未来如果要忽略关系，应单独记录降级策略，不临时增加随机参数。
10. 以实际 Python 3.7 与已存在 Linux parser 库实现，避免设计示例的版本不兼容。
11. 短文档末尾链接的“第一阶段 DFG 融合代码设计说明”文件当前不存在；实际详细依据是同目录 MANDO_LLM_DDG_Code_Design_Guide.md。

## 12. 实施顺序和本轮交付边界

确认报告后建议按以下顺序实施：

1. 前置审计：冻结输入／源码／版本／特征／标签／折清单，验证 grammar 与 Python 环境。
2. 人工小例：symbol table、事件 CFG、RD 和手写预期依赖测试。
3. 单文件投影：作者与本地图各抽样，不加训练先核验边和全部不变量。
4. 批量附边：重入、访问控制 E0/E1/E2，输出覆盖率和侧表，保留所有输入样本。
5. 最小反射接入：一个原函数；验证两个模型的方向、元关系、梯度及 checkpoint schema。
6. 短训练与复评：先确认数据正确进入模型，再运行固定折完整消融。
7. 如实汇报结果、无收益或失败原因，再决定 storage/mapping、跨函数或新数据集扩展。

**本轮没有实现上述模块，也没有生成增强图、训练模型或更改原流程。** 交付的是已经结合实际代码调整的接入分析；这满足附件第 20 节的先分析后确认安排。

## 13. 本轮核验记录

- 阅读：附件全文、两份 DFG 设计文档、当前构图／标注／加载／特征／HGT 相关入口及外部参考。
- 环境检查：Python 3.7.12；默认库为 Mach-O；现有 Linux ELF 可正常调用原生成器。
- 行为检查：在内存中复现 if 分支 return 被接回后继语句，无文件图输出。
- 对齐检查：两类作者图与本地 narrow 节点身份比对；buggy_18 的普通 AST anchor 重解析抽查。
- 未进行：新 DDG 算法单元测试、训练、全七类逐节点源码投影、Slither 全语料比较。这些属于后续实施与验收，本文不把计划写成结果。
- 原文件保护：审查清单记录 62 个相关既有代码／文档文件；写入后再次比较摘要。本轮新增文件仅在 scripts/DFG/ 内。
