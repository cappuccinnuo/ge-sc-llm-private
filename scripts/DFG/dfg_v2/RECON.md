# DFG v2 Prompt 0：侦察与基线核对

**结论：经用户批准复用已有 `SupportedSourceView` 后，Prompt 0 数据验收通过。** 原 `SourceView` 下访问控制合约任务的状态声明锚点率为 804/922（87.20%），曾低于90%门槛并暂停。用户明确答复“同意复用已有 SupportedSourceView（推荐）”；批准口径为872/922（94.58%）。这里保留两个口径及失败证据，不把原失败记录改成通过。未新增状态节点，未猜测编译器版本。

工作树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`；分支 `dfg-v2`；审计基础提交 `29a9b4efdedb2f897dc78c6b332a526ab9994fee`。该分支在开始时已经存在。`git fetch origin dfg-v2` 因 GitHub DNS 解析失败，未能确认远端最新状态；本地 HEAD 与缓存 origin/dfg-v2 一致，并包含文档指定的 ddg-v1.1-correctness 基线。未推送。

证据目录记为 **B**：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/recon`。机器汇总见同目录代码侧的 `recon.json`，逐文件审计在 `B/graphs/<task>.json`；报告中 R=重入，AC=访问控制。

## 1. 输入图、源码与 schema

入口为 `integration/rebuild.py::DEFAULT_MANIFEST`，引用的 manifest 及每个输入 SHA 已核对。**本批输入是作者发布的图结构/节点标签，加上本地已冻结的 tokenizer 特征。** 节点任务使用漏洞文件的 HCG（CFG+CG）子集，不能把它与作者另发的 CFG-only 图混称为同一输入。

| 任务 | 文件 | 节点 | 边 | 节点类型 | 边类型 | 原始 canonical 类型 |
| --- | --- | --- | --- | --- | --- | --- |
| reentrancy_author_contract | 142 | 18312 | 19267 | 16 | 8 | 89 |
| access_control_author_contract | 114 | 13432 | 15538 | 16 | 8 | 86 |
| reentrancy_author_node | 71 | 12036 | 11710 | 16 | 8 | 77 |
| access_control_author_node | 57 | 7710 | 8840 | 16 | 8 | 81 |

合约任务的文件/节点/边数量与仓库 `audit_author_graphs.py::PAPER` 所记录的论文表1一致：R=142/18312/19267，AC=114/13432/15538。节点任务文件数分别71、57，是上述语料的漏洞文件子集；不拿节点子集数量直接比较表1的完整语料数量，也不据此宣称标签语义已完全复现论文。

四任务均无缺失源码，source_file → 唯一路径与源码 SHA 均已核验，节点 ID 全为整数。全部原节点属性键：`code`, `label`, `method`, `node_info_vulnerabilities`, `node_source_code_lines`, `node_type`, `source_file`, `token`, `type_label`。原始 canonical 计数指 NetworkX 图中的 (源类型, 边类型, 目标类型)，不是 reflect 后的模型 schema。

### reentrancy_author_contract

- 图：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/E0/contract.gpickle`
- SHA256：`7b99f680024296f557ce9d0a16ab027f7174c26c1c9d7c621390b72b1ec92452`
- 源码清单：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/reentrancy_author_contract/sources.json`

节点类型计数：`{"contract_declaration": 412, "new_variable": 3472, "function_definition": 3651, "expression_statement": 6501, "constructor_definition": 165, "modifier_definition": 165, "return": 1245, "library_declaration": 86, "if": 1232, "end_if": 1197, "interface_declaration": 45, "struct_declaration": 70, "for": 28, "end_loop": 35, "while": 7, "continue_statement": 1}`。

边类型计数：`{"next_line": 10161, "recursive_method_call": 3981, "internal_call": 973, "first_next_line": 157, "pos_next": 578, "neg_next": 1260, "end_if": 568, "external_call": 1589}`。

每个 canonical 的边数完整保存在 `recon.json → graphs.tasks[].canonical_counts`。

### access_control_author_contract

- 图：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/E0/contract.gpickle`
- SHA256：`d66b920801c02dc53832337de719135f8c10d158b24ba403d788c1646b8f034f`
- 源码清单：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/access_control_author_contract/sources.json`

节点类型计数：`{"library_declaration": 76, "function_definition": 3398, "if": 365, "end_if": 325, "return": 1151, "new_variable": 1462, "expression_statement": 5813, "contract_declaration": 358, "constructor_definition": 167, "modifier_definition": 158, "interface_declaration": 40, "struct_declaration": 42, "for": 29, "end_loop": 38, "while": 9, "continue_statement": 1}`。

边类型计数：`{"next_line": 8107, "recursive_method_call": 3723, "pos_next": 389, "neg_next": 396, "end_if": 399, "first_next_line": 156, "internal_call": 1036, "external_call": 1332}`。

每个 canonical 的边数完整保存在 `recon.json → graphs.tasks[].canonical_counts`。

### reentrancy_author_node

- 图：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/E0/node.gpickle`
- SHA256：`91c3bd89af18af073162648b95747319b644dd2555cfcff394d251f626bbf77c`
- 源码清单：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/reentrancy_author_node/sources.json`

节点类型计数：`{"contract_declaration": 165, "new_variable": 2631, "function_definition": 2124, "expression_statement": 4312, "library_declaration": 29, "if": 1055, "end_if": 1025, "return": 433, "constructor_definition": 67, "modifier_definition": 56, "interface_declaration": 20, "struct_declaration": 50, "for": 27, "end_loop": 34, "while": 7, "continue_statement": 1}`。

边类型计数：`{"next_line": 6355, "recursive_method_call": 2247, "internal_call": 464, "pos_next": 408, "neg_next": 1083, "end_if": 379, "first_next_line": 67, "external_call": 707}`。

每个 canonical 的边数完整保存在 `recon.json → graphs.tasks[].canonical_counts`。

### access_control_author_node

- 图：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/E0/node.gpickle`
- SHA256：`c3bdfa00bd112581fd4900ac59ab192ad32a9a26df94dc87209e1ba900208488`
- 源码清单：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build/access_control_author_node/sources.json`

节点类型计数：`{"library_declaration": 28, "function_definition": 2048, "if": 209, "end_if": 180, "return": 433, "new_variable": 702, "expression_statement": 3731, "contract_declaration": 129, "constructor_definition": 73, "modifier_definition": 61, "interface_declaration": 20, "struct_declaration": 25, "for": 26, "end_loop": 35, "while": 9, "continue_statement": 1}`。

边类型计数：`{"next_line": 4614, "recursive_method_call": 2182, "pos_next": 232, "neg_next": 239, "end_if": 221, "first_next_line": 73, "internal_call": 591, "external_call": 688}`。

每个 canonical 的边数完整保存在 `recon.json → graphs.tasks[].canonical_counts`。

## 2. 状态声明锚点与源码版本策略

| 任务 | 声明总数 | 原 SourceView | 批准 SupportedSourceView | 验证文件 | ordinary_nodes_checked |
| --- | --- | --- | --- | --- | --- |
| reentrancy_author_contract | 2369 | 2236 (94.39%) | 2360 (99.62%) | 140/142 | 16992 |
| access_control_author_contract | 922 | 804 (87.20%) | 872 (94.58%) | 108/114 | 12476 |
| reentrancy_author_node | 1788 | 1682 (94.07%) | 1788 (100.00%) | 71/71 | 10977 |
| access_control_author_node | 403 | 376 (93.30%) | 403 (100.00%) | 57/57 | 7495 |

锚点链为原源码 AST 字节身份 → view.mapping → compat_ids → Projector.by_ast；所有已验证声明的目标类型都是 `new_variable`。未验证项保留在分母中；四任务无解析失败，已验证文件中没有“状态声明确无对应节点”的案例。合约任务残余 R=9、AC=50 个声明属于版本/视图无法确认，不能把它们写成“原图丢失声明节点”。

原视图原因及计数、批准视图原因及计数均保留在 `recon.json`。批准口径的文件级回退如下：

| 任务 | 文件 | 原因 | 声明数 | 示例原始行 |
| --- | --- | --- | --- | --- |
| reentrancy_author_contract | 0x488690160a80702e6b8e47c7d62ec2779eb5f240.sol | F: no version evidence for lexical scope | 2 | 2 |
| reentrancy_author_contract | 0xa9f5ccdd11178ac90746ad76153bb9d0915edd9f.sol | F: interval crosses lexical scope boundary | 7 | 22 |
| access_control_author_contract | 0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol | F: no version evidence for lexical scope | 6 | 120 |
| access_control_author_contract | 0x0c7b8eedd028f3730e7b0f3dc032e916302f09b4.sol | F: no version evidence for lexical scope | 6 | 7 |
| access_control_author_contract | 0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol | F: interval crosses lexical scope boundary | 7 | 22 |
| access_control_author_contract | 0x0e24191da2f58dcf792d0bf5e2b14e2b6a205e36.sol | F: no version evidence for lexical scope | 7 | 102 |
| access_control_author_contract | 0x0f1ed66c251bcb52ecf7e67ac64bb72482048adb.sol | F: no version evidence for lexical scope | 8 | 28 |
| access_control_author_contract | 0x1b5d56bfe749e492ae226cf9aa23c1426f828b7b.sol | F: no version evidence for lexical scope | 16 | 6 |

对应声明全文、字节范围、原始行号在 `recon.json → unverified_anchor_examples` 和逐文件 JSON 中。多 pragma 的恢复复用 Stage K 的版本区间处理与已有 source SHA 绑定元数据；不把 pragma 范围伪装成一个确定的 solc 版本。未确认部分保留回退。批准只涉及 v2 的后续视图策略，本次旧标量对照依旧使用未修改的原 pipeline。

## 3. 语句节点覆盖与 legacy AST

以下为批准视图口径，每格依次是 **精确匹配 / 无独立精确节点 / 视图未确认**。分类直接来自当前 grammar AST；modifier/constructor 行是上面语句集合的上下文子集，不能重复相加。

| AST/上下文 | R 合约 | AC 合约 | R 节点 | AC 节点 |
| --- | --- | --- | --- | --- |
| constructor_definition:emit_statement | 0/32/1 | 0/36/1 | 0/13/0 | 0/13/0 |
| constructor_definition:expression_statement | 351/2/6 | 407/2/7 | 178/2/0 | 182/2/0 |
| constructor_definition:for_statement | 2/0/0 | 2/0/0 | 2/0/0 | 2/0/0 |
| constructor_definition:if_statement | 5/0/0 | 5/0/0 | 5/0/0 | 5/0/0 |
| constructor_definition:revert_statement | 0/1/0 | 0/1/0 | 0/1/0 | 0/1/0 |
| constructor_definition:variable_declaration_statement | 1/2/0 | 5/2/0 | 1/2/0 | 1/2/0 |
| do_while_statement | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| emit_statement | 0/602/6 | 0/579/12 | 0/244/0 | 0/230/0 |
| expression_statement | 6414/30/37 | 5566/31/197 | 4269/29/0 | 3687/28/0 |
| for_statement | 28/0/0 | 29/0/0 | 27/0/0 | 26/0/0 |
| for_update | 26/2/0 | 29/0/0 | 25/2/0 | 26/0/0 |
| if_statement | 1232/0/0 | 313/0/52 | 1055/0/0 | 209/0/0 |
| modifier_definition:expression_statement | 335/0/2 | 300/0/20 | 116/0/0 | 124/0/0 |
| modifier_definition:if_statement | 3/0/0 | 4/0/8 | 1/0/0 | 4/0/0 |
| modifier_definition:revert_statement | 0/1/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| modifier_definition:variable_declaration_statement | 6/0/0 | 4/0/0 | 3/0/0 | 3/0/0 |
| return_statement | 1235/0/10 | 1058/0/93 | 433/0/0 | 433/0/0 |
| revert_statement | 0/694/0 | 0/24/0 | 0/683/0 | 0/14/0 |
| throw_statement | 0/0/0 | 0/0/0 | 0/0/0 | 0/0/0 |
| variable_declaration_statement | 1099/26/4 | 519/27/21 | 843/25/0 | 299/24/0 |
| while_statement | 7/0/0 | 9/0/0 | 7/0/0 | 9/0/0 |

`emit_statement` 与 `revert_statement` 在已验证文件中均无独立 HCG 锚点。`do_while_statement`、`throw_statement` 是本次 AST 类型枚举未观察到的类型，不等同于断言原始文本没有其他语法表示。构造器上下文仅统计 grammar 的 `constructor_definition`，没有把老式同合约名 function 自动推断为构造器。for-update 单列的是 update AST 自身是否有独立精确节点；不按最近行猜映射。缺独立语句节点不直接等于整个语句的所有子事实都无法映射，后续应按事实精确投影计数。

legacy 示例（仅解析器验证，未进行 Solidity 编译验证）：

```text
variable_declaration_statement: var acc = Acc[msg.sender];
  [无字段] variable_declaration
    type: type_name -> primitive_type -> var
    name: identifier acc
  [无字段] =
  value: array_access
    base: identifier Acc
    index: member_expression
      object: identifier msg
      property: identifier sender
```

完整含标点、子节点与字段的 AST：`B/graphs/legacy_var_ast.json`。

## 4. tokenizer 特征核对

tokenizer：`Salesforce/codet5p-770m`，revision `3f7cc6e80aee6612f41253b5ee28f09f86faa35f`，`RobertaTokenizerFast`，离线缓存加载。输入为节点 `code` 原样文本，保留已有 DOT 引号/转义，不额外规范化。先 `add_special_tokens=True` 编码，再由现有 `encode_ids` 取前512个 ID、右侧补0、转为 `float32[512]`。pad/bos/eos/unk=0/1/2/3。没有加载 encoder 权重。

| 任务 | 抽样节点 | 逐元素完全相同 | 抽样中发生截断 |
| --- | --- | --- | --- |
| reentrancy_author_contract | 200 | 200 | 3 |
| access_control_author_contract | 200 | 200 | 2 |
| reentrancy_author_node | 200 | 200 | 1 |
| access_control_author_node | 200 | 200 | 2 |

独立对每个任务按 seed=0 抽200节点，800/800完全一致；全图特征 shape/dtype 也已枚举。这不是全图每个向量重新编码证明，抽样和向量已封存于 `B/token/`。输入原始作者融合图没有 token；它是此前本地补入的固定特征，不应写成作者发布的语义向量。一次839-token长文本警告发生在手动截断前；最终512维一致。不能直接改用 tokenizer 的 truncation=True 并假定长文本 EOS 行为相同。

## 5. 训练协议与冻结划分

此处记录现有数值事实，不执行训练，也没有把历史 paper_kfold 结果改称独立测试。v2 文档拟用嵌套验证；冻结外层与内层名单已经存在，不需要重抽折。

| 任务 | Adam initial LR | OneCycle max LR | div_factor | weight_decay | 折数 | fold0 train/inner val/outer test |
| --- | --- | --- | --- | --- | --- | --- |
| reentrancy_author_contract | 0.0005 | 0.01 | 20 | 5e-06 | 5 | 90/23/29 |
| access_control_author_contract | 0.0005 | 0.01 | 20 | 5e-06 | 5 | 72/19/23 |
| reentrancy_author_node | 0.0002 | 0.005 | 25 | 0.0 | 10 | 50/13/8 |
| access_control_author_node | 0.0002 | 0.005 | 25 | 0.0 | 10 | 40/11/6 |

共享配置：Adam 默认 betas=(0.9,0.999)、eps=1e-8、amsgrad=False；OneCycle cosine，50个 scheduler step，final_div_factor=1、cycle_momentum=True、base/max momentum=0.85/0.95，创建 scheduler 后 beta1=0.95，阶段结束 step=14/49。每轮一次完整 train 监督的 optimizer step，再 scheduler step，再 eval 前向验证。最多50轮，patience=7，delta=0.001；best 严格取最低验证 loss，不是最低 loss 至少差0.001才保存。delta 参与停止计数，best/last 分开。损失为不加类别权重的 cross entropy。HGT hidden=128，layers=2，heads=8，dropout=0.2。

划分文件为 JSON，paper 折键 `train_files/val_files`，保留的 nested 折键 `inner_train_files/inner_val_files/outer_test_files`。四任务原 nested 文件均存在；用现有 make_fold_document 在内存重建，4/4与冻结文件内容一致，没有改写折文件。graph_labels.json 是 contract_name/targets 记录列表，节点监督标签在冻结图节点属性中。

- `reentrancy_author_contract`：
  - paper：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/reentrancy_author/splits/contract_folds.json`
  - nested：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/contract_folds.json`
  - 合约标签：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json`

- `access_control_author_contract`：
  - paper：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/access_control_author/splits/contract_folds.json`
  - nested：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/splits/contract_folds.json`
  - 合约标签：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json`

- `reentrancy_author_node`：
  - paper：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/reentrancy_author/splits/node_folds.json`
  - nested：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/node_folds.json`
  - 合约标签：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared/graph_labels.json`

- `access_control_author_node`：
  - paper：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/access_control_author/splits/node_folds.json`
  - nested：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/splits/node_folds.json`
  - 合约标签：`/home/zhao/SmartContract/ge-sc-llm/scripts/DFG/experiments/artifacts/20261012_v1/access_control_author/prepared/graph_labels.json`

种子：split=1；inner=seed×1009+fold+1；constructor=10000+fold（合约另加1000）；pair=constructor+77；fit=constructor+1000000。所有路径、SHA、每折名单数量、实际配置见 `B/protocol/protocol_resources.json`。历史90份 fit 记录的 config 与任务 manifest 核对一致。

## 6. 未修改原标量层的覆盖基线

实际调用 `integration.pipeline.build_graph(profile="scalar")`，仅将结果写入新目录。没有用批准的新视图悄悄替换原标量对照。函数总数按原始 AST 中带函数体的 FUNCTION_TYPES 统计；文件级回退的函数也在总数中，避免只报告分析成功文件导致分母变小。

| 任务 | 总函数 | 可进入旧文件分析 | 支持函数 | 支持/全部 | 文件门槛排除 | 新增 DATA_DEF_USE |
| --- | --- | --- | --- | --- | --- | --- |
| reentrancy_author_contract | 3404 | 3166 | 2035 | 59.78% | 238 | 3561 |
| access_control_author_contract | 3148 | 2745 | 2128 | 67.60% | 403 | 4032 |
| reentrancy_author_node | 2045 | 1917 | 1210 | 59.17% | 128 | 1894 |
| access_control_author_node | 1958 | 1832 | 1550 | 79.16% | 126 | 2836 |

### reentrancy_author_contract 回退 Top 10

| 函数回退原因（原字符串） | 次数 |
| --- | --- |
| Modifier execution is outside phase-one scope | 441 |
| inheritance_binding_not_supported | 374 |
| Unsupported non-scalar or inferred type: string | 103 |
| Unsupported non-scalar or inferred type: bytes | 49 |
| builtin_not_guaranteed_over_pragma_interval | 49 |
| Unsupported non-scalar or inferred type: Role | 26 |
| Unsupported non-scalar or inferred type: var | 15 |
| Unsupported non-scalar or inferred type: address[] | 11 |
| Unsupported non-scalar or inferred type: ERC20Basic | 5 |
| Unsupported non-scalar or inferred type: ERC20 | 5 |

文件级回退：`{"Multiple Solidity pragmas require version intersection verification": 4, "Missing supported pragma; supply recorded scope mode": 1, "Pragma crosses scope-semantics boundary": 1}`。

### access_control_author_contract 回退 Top 10

| 函数回退原因（原字符串） | 次数 |
| --- | --- |
| Modifier execution is outside phase-one scope | 370 |
| Unsupported non-scalar or inferred type: string | 88 |
| Unsupported non-scalar or inferred type: bytes | 49 |
| inheritance_binding_not_supported | 23 |
| Unsupported non-scalar or inferred type: Role | 16 |
| Unsupported non-scalar or inferred type: address[] | 11 |
| Unsupported non-scalar or inferred type: ERC20Basic | 7 |
| Unsupported non-scalar or inferred type: ERC20Interface | 5 |
| Unsupported non-scalar or inferred type: ERC20 | 5 |
| Nested delete expression | 4 |

文件级回退：`{"Multiple Solidity pragmas require version intersection verification": 6, "Missing supported pragma; supply recorded scope mode": 5, "Pragma crosses scope-semantics boundary": 1}`。

### reentrancy_author_node 回退 Top 10

| 函数回退原因（原字符串） | 次数 |
| --- | --- |
| inheritance_binding_not_supported | 363 |
| Modifier execution is outside phase-one scope | 127 |
| Unsupported non-scalar or inferred type: string | 68 |
| builtin_not_guaranteed_over_pragma_interval | 49 |
| Unsupported non-scalar or inferred type: bytes | 40 |
| Unsupported non-scalar or inferred type: var | 14 |
| Unsupported non-scalar or inferred type: address[] | 9 |
| Unsupported non-scalar or inferred type: Token | 4 |
| Unsupported non-scalar or inferred type: Proposal | 4 |
| Nested delete expression | 3 |

文件级回退：`{"Multiple Solidity pragmas require version intersection verification": 2}`。

### access_control_author_node 回退 Top 10

| 函数回退原因（原字符串） | 次数 |
| --- | --- |
| Modifier execution is outside phase-one scope | 145 |
| Unsupported non-scalar or inferred type: string | 44 |
| Unsupported non-scalar or inferred type: bytes | 39 |
| Unsupported non-scalar or inferred type: address[] | 11 |
| inheritance_binding_not_supported | 10 |
| Unsupported non-scalar or inferred type: Token | 4 |
| Unsupported non-scalar or inferred type: Proposal | 4 |
| Nested delete expression | 3 |
| Unsupported non-scalar or inferred type: Role | 3 |
| Unsupported non-scalar or inferred type: var | 3 |

文件级回退：`{"Multiple Solidity pragmas require version intersection verification": 2}`。

每个新 bundle 的 `audit.json` 含原节点、属性、基础边不变量核验；图/输入/审计 SHA 在 `B/scalar/<task>/manifest.json`，单独输出新 `hcg.gpickle`。四份图均保留全部原节点与边。函数支持不保证每个事实都有可投影节点，也不等于预测质量。

## 7. 历史耗时与显存

统计 overall_cv_v1 实际60次 fit 与 guard_extension_v1 实际30次新 fit；不把引用的历史结果重复计数。

| 批次/变体 | 任务 | fit数 | 耗时中位数(s) | 最大 allocated(MiB) | 最大 reserved(MiB) | 最低整卡空闲(MiB) |
| --- | --- | --- | --- | --- | --- | --- |
| overall_cv_v1/HCG | access_control_author_contract | 5 | 128.83 | 1545.84 | 1658.00 | 316 |
| overall_cv_v1/HCG_DDG | access_control_author_contract | 5 | 140.51 | 2020.64 | 2116.00 | 19 |
| overall_cv_v1/HCG | access_control_author_node | 10 | 105.76 | 920.45 | 1004.00 | 1135 |
| overall_cv_v1/HCG_DDG | access_control_author_node | 10 | 98.10 | 1162.33 | 1262.00 | 886 |
| overall_cv_v1/HCG | reentrancy_author_contract | 5 | 184.68 | 2103.30 | 2270.00 | 40 |
| overall_cv_v1/HCG_DDG | reentrancy_author_contract | 5 | 204.89 | 2709.92 | 2878.00 | 40 |
| overall_cv_v1/HCG | reentrancy_author_node | 10 | 186.22 | 1351.31 | 1458.00 | 572 |
| overall_cv_v1/HCG_DDG | reentrancy_author_node | 10 | 189.72 | 1761.38 | 1906.00 | 119 |
| guard_extension_v1/HCG_DDG_GUARD | access_control_author_contract | 5 | 133.74 | 2159.13 | 2252.00 | 31 |
| guard_extension_v1/HCG_DDG_GUARD | access_control_author_node | 10 | 117.42 | 1250.32 | 1364.00 | 550 |
| guard_extension_v1/HCG_DDG_GUARD | reentrancy_author_contract | 5 | 179.75 | 2894.40 | 3068.00 | 29 |
| guard_extension_v1/HCG_DDG_GUARD | reentrancy_author_node | 10 | 209.44 | 1883.61 | 2048.00 | 63 |

guard 新30次总计82.66分钟，平均165.32秒；overall 60次总计157.77分钟。这些是历史运行记录，包含各折不同早停轮数及设备状态，不是 v2/G3 的显存保证。原“150次约7小时”可作为粗估，需 Prompt 7 的实测再更新。证据：`B/protocol/fit_records.json`、`resource_summary.csv`。

## 以后扩展：其余五类仅记录路径

- `arithmetic`：
  - author_hcg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/graph_detection/arithmetic_tree_sitter_cfg_cg_compressed_graphs.gpickle`
  - author_cfg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/node_detection/arithmetic_tree_sitter_cfg_compressed_graphs.gpickle`
  - sources：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/experiments/ge-sc-data/source_code/arithmetic/source_files`

- `denial_of_service`：
  - author_hcg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/graph_detection/denial_of_service_tree_sitter_cfg_cg_compressed_graphs.gpickle`
  - author_cfg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/node_detection/denial_of_service_tree_sitter_cfg_compressed_graphs.gpickle`
  - sources：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/experiments/ge-sc-data/source_code/denial_of_service/source_files`

- `front_running`：
  - author_hcg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/graph_detection/front_running_tree_sitter_cfg_cg_compressed_graphs.gpickle`
  - author_cfg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/node_detection/front_running_tree_sitter_cfg_compressed_graphs.gpickle`
  - sources：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/experiments/ge-sc-data/source_code/front_running/source_files`

- `time_manipulation`：
  - author_hcg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/graph_detection/time_manipulation_tree_sitter_cfg_cg_compressed_graphs.gpickle`
  - author_cfg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/node_detection/time_manipulation_tree_sitter_cfg_compressed_graphs.gpickle`
  - sources：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/experiments/ge-sc-data/source_code/time_manipulation/source_files`

- `unchecked_low_level_calls`：
  - author_hcg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/graph_detection/unchecked_low_level_calls_tree_sitter_cfg_cg_compressed_graphs.gpickle`
  - author_cfg：`/home/zhao/SmartContract/ge-sc-llm/data/upstream_mando_llm/node_detection/unchecked_low_level_calls_tree_sitter_cfg_compressed_graphs.gpickle`
  - sources：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11/experiments/ge-sc-data/source_code/unchecked_low_level_calls/source_files`

以上仅确认路径存在；本轮未加载、核验或分析其余五类图。

## 验收、范围与待用户确认的建议

1. 批准口径四任务锚点均≥90%；token抽样800/800一致；原标量四任务均完成；输入SHA未变。
2. 回归命令：`python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py`；**223 passed，0 failed，29 warnings，4.03s**。警告为现有 DGL distutils 与 NetworkX gpickle 弃用提示。
3. 未新增分析算法，因此本阶段没有新增 DFG 语义单元测试；审计脚本用现有 Python3.7 运行，已有输出目录拒绝覆盖。编译验证、训练、v2模型构造均未执行，它们不属于本阶段。
4. 11063个受保护的已跟踪文件 SHA 未变，PROMPTS.md 未变；原有15个未跟踪路径保留。新源码/文档只在 dfg_v2 下；另有 Prompt 0 明确要求的新产物目录 B。因此 git status 中还会出现原有未跟踪路径与该产物目录，不能为了满足“只显示v2新文件”而清理它们。
5. 本轮优先遵循 Prompt 0 的“不修改任何已有文件”，没有向旧 HANDOVER/training_changes 追加，记录集中在新 PROGRESS.md；这与共享上下文的每轮追加要求有冲突，明确保留此处理记录。

**以下建议尚未实施，进入相应阶段前需要用户确认：**

- 文档按四任务 outer-test F1 选 G*，会让外层测试参与方案选择。建议改成内层选择，或固定报告全部剖面并把 G* 排名仅作探索性观察；不能继续称选出的 G* 分数是未参与选择的独立测试。
- P7 不能直接复用 paper_checkpoint 的协议绑定：它写死 paper_kfold/CV validation。建议在 v2 旁路适配 checkpoint 的协议、评分角色、辅助节点/schema 绑定，保留训练数值规则；原保存器不修改。无训练支持关系的非零梯度断言也应按训练支持量解释。

本次唯一已获批准的方案调整是 SupportedSourceView。下一阶段是 Prompt 1；本轮到此停止。

## 复跑命令（每次换一个全新的输出目录）

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m scripts.DFG.dfg_v2.recon_graphs --output /tmp/dfg-v2-p0-new/graphs
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -B -m scripts.DFG.dfg_v2.recon_tokens --output /tmp/dfg-v2-p0-new/token --sample-size 200 --seed 0
python -B -m scripts.DFG.dfg_v2.recon_protocol --output /tmp/dfg-v2-p0-new/protocol
python -B -m scripts.DFG.dfg_v2.recon_scalar --output /tmp/dfg-v2-p0-new/scalar
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```
