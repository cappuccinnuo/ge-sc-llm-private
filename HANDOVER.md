# MANDO-LLM 复现 — 交接文档

> 2026-10-08 Codex update: the current verified state, training changes and labeling_v2 inputs are in section 11 below. Earlier sections are historical and may contain superseded conclusions.


> 目标：从 Solidity 源码开始，完整复现 MANDO-LLM（TOSEM 2026）论文，当前只做 **reentrancy** 一类漏洞。
> 论文方案说明见 `scripts/mando-llm.md`；论文结果表见下文「与论文的差距」一节。
>
> **最重要的一句话**：流程已全部打通且构图与论文逐位吻合，但**当前指标不可信** ——
> 一张代码查找表就能拿到 98.69 Buggy-F1，与完整模型的 98.98 在噪声内无法区分。
> 在修正评估口径之前，不要用现有数字做任何模型侧的结论。

---

## 0. 环境（必读，有几个坑）

```bash
conda activate mando          # Python 3.7.12 / torch 1.8.1+cu111 / dgl 0.6.1 / transformers 4.30.2
cd ~/SmartContract/ge-sc-llm
export TREE_SITTER_LIB_DIR=$PWD/build/linux-x86_64    # 见下方「坑 1」
```

GPU：RTX 3050 Laptop 4 GiB。CodeT5p-770m 在 batch=16 下可跑。

### 坑 1：仓库自带的 `.so` 是 macOS 库
`process_graphs/tree_sitter_codeviews/build/my-languages.so` 是 **Mach-O arm64**，Linux 加载报
`invalid ELF header`。已重新编译 Linux 版到 `build/linux-x86_64/`，通过 `TREE_SITTER_LIB_DIR`
环境变量指向它（**没有覆盖仓库原文件**，可回退）。

### 坑 2：grammar 是孤儿 submodule
`vendor/tree-sitter-solidity` 以 gitlink 提交但**没有 `.gitmodules`**，clone 后是空目录。
从 gitlink 挖出 SHA `9004b86531cb424bd379424cf7266a4585f2af7d`，确认属于
**JoranHonig/tree-sitter-solidity**，已拉取到位（`scripts/fetch_grammar.sh`）。

### 坑 3：Windows 侧 Git Bash 会吞掉 shell 变量
本会话中助手通过 `wsl.exe` 访问 WSL，循环变量/URL 常被路径转换破坏。
**凡是带变量的多行命令，一律写成 `scripts/*.sh` 再执行**，不要内联。

---

## 1. 仓库原始状态的诊断结论

`MANDO-Project/ge-sc-llm` **不是开箱即用的**。`.gitignore` 排除了 `*.gpickle` / `*.json` / `data/`，
且多处关键代码被作者注释掉。已查明的缺失与缺陷：

| 项 | 状态 |
|---|---|
| 压缩图 `*.gpickle`、标签 `*.json` | 被 gitignore，**全部缺失**，需自行构建 |
| 批量「目录 → CFG」的驱动脚本 | **仓库从未提交**，只有库函数和单测 |
| 写入 `node['token']` 的生产脚本 | **全仓库零处** |
| `generator.py` 的 `end_if` 行号解析 | **缺陷**：把 `(行,列)` 当作 `(首行,末行)` |
| `end_loop` 节点 | **label 无行号，被静默删除**（35 个） |
| 调用边类型 | `internal_call`/`external_call` 等**全被注释**，塌缩成 `next` |
| `visualize_*` 调用 | **两个分类器里都被注释**，且会先 `rmtree` 日志目录 |
| 逐 epoch 输出 | 16 处 `# print` 被注释 |
| `EarlyStopping.save_checkpoint` | 改善时保存的调用**被注释**，消息谎报 `inf --> x` |
| `NODE_RUNTIME_DEFAULTS` | 除 `num_heads` 外**全部不生效**（装饰性死配置） |

---

## 2. 已改动的仓库文件（8 个）

```
auto_version_solc.py                         91 +/-   （Slither 路线遗留，本路线未用，可还原）
graph_classifier.py                          72 +/-
node_classifier.py                           84 +/-
process_graphs/.../CFG/CFG_solidity.py       49 +/-   ← 恢复调用边类型
process_graphs/.../utils/solidity_nodes.py   28 +/-   ← 修 end_if / end_loop label
sco_models/classifier_cli.py                 12 +/-   ← 新增 --verbose_epochs / --no_progress
sco_models/tools.py                          30 +/-   ← EarlyStopping 消息如实化
sco_models/visualization.py                 138 +/-   ← 修复两个本就崩溃的函数
```

改动性质：**训练逻辑、超参、k 折方式、损失函数、评估口径全部未动**，只修 bug + 补显示 + 恢复被注释的类型标注。
唯一的超参改动是合约级学习率 `0.00005 → 0.0005`（按论文附录 A，用户明确要求）。

### 刻意保留的偏离
**最优权重保存未实现**。查证 MANDO（ge-sc）与 MANDO-HGT（ge-sc-transformer）**均无 EarlyStopping、
一律保存末轮权重**，是 MANDO 系列一贯做法，改了会脱离论文口径。

---

## 3. 数据流水线（全部脚本化，在 `scripts/`）

```
source_files/*.sol
  │  gen_reentrancy_cfg.py           tree-sitter → 每合约一个 CFG（含调用边）
  ▼
/tmp/reentrancy_cfg_full/*.gpickle
  │  build_labeled_graph.py          disjoint_union 合并 + 漏洞标注
  ▼  （依赖 line_mapping.py 做行号映射，见「坑 4」）
hcg_compressed_graphs.gpickle        18,312 节点 / 19,267 边
  │
  ├─ make_graph_labels.py       →  graph_labels.json（142 合约，71/71）
  │
  ├─ encode_tokenizer_features.py →  tokenizer_ids_*.gpickle（512 维，论文方法）
  │  encode_llm_tokens.py         →  encode_token_*.gpickle（Encoder，论文的对照基线）
  │
  └─ filter_buggy_contracts.py  →  linelevel_*.gpickle（12,036 节点 / 71 合约）
```

### 坑 4：tree-sitter 的行号不是原文件行号
`parser_driver.py:27-28` 在解析前会 `remove_empty_lines` + `remove_comments`，
所以 `node_source_code_lines` 是**预处理后**的行号，而漏洞标注是**原文件**行号。
`scripts/line_mapping.py` 做字符级溯源映射（跨行 `/* */` 会合并多行，不能用固定偏移）。
**未做这个映射时，8 个合约零命中、其余 63 个在错误节点上命中。**
映射后 71/71 全部正确命中。节点上同时保留 `node_source_code_lines_original`。

---

## 4. 与论文的核对结果

### ✅ 逐位吻合的部分（附录 C, Reentrancy 行）

| 指标 | 论文 | 我们 |
|---|---|---|
| Total / Buggy Contracts | 142 / 71 | 142 / 71 |
| **Nodes** | **18,312** | **18,312** |
| **Edges** | **19,267** | **19,267** |
| Buggy Nodes | 6,570 | **6,978** ❌ +408 |

另有三个独立佐证：
- 行级图 **12,036** 节点 == 作者遗留的 `node2vec_cfg_cg_compressed_graphs.pkl` 行数
- 合约级 **18,312** == `node2vec_coarse_grained_cfg_cg_compressed_graphs.pkl` 行数
- CodeT5p-770m tokenizer 词表 **32,100** == 论文附录 B
- 运行时 `Etype dict: 147` 个元关系，落在论文 §5.2「几十到几百」区间

### 参数（附录 A）全部对齐
512 维节点特征 / hidden 128 / 2 层 / 8 头 / 合约级 5-fold + LR 0.0005→0.01 /
行级 10-fold + LR 0.0002→0.005 / patience 7 / delta 0.001 / Cross-Entropy。

---

## 5. 实验结果（**全部为单次，不可靠，见第 6 节**）

### 论文 Table 5（Reentrancy 行级 Buggy-F1）
```
MANDO-HGT 最佳                85.06
LLMs Encoder (Codet5p-770m)   84.96
MANDO-LLM (Codet5p-770m)      96.78   ← 对标目标
```

### Phase 2 行级（10-fold，71 buggy 合约，12,036 节点）
| 节点特征 | Buggy F1 | Macro F1 |
|---|---|---|
| `nodetype`（纯结构） | 87.84 | 83.68 |
| **Tokenizer `ids`（论文方法）** | **98.87 ~ 99.10**（6 次，均值 98.98） | ~98.85 |
| Tokenizer `ids_norm` | 97.19 | 96.71 |
| Tokenizer `hashed_bow` | 99.32 | 99.24 |

### Phase 1 合约级（5-fold，142 合约，1:1）
| 节点特征 | Buggy F1 | Macro F1 |
|---|---|---|
| `nodetype` | 92.64 | 92.18 |
| Tokenizer `ids` | 90.09 | 90.13 |

### 两阶段级联（`scripts/cascade_detect.py`）
```
Phase 1: 142 合约 → 筛出 65
Phase 2: 65 个中定位 63 个
对照真值: TP 61  FP 4  FN 10  TN 67
  ← 10 个真实有漏洞的合约在第一阶段被过滤，永远到不了 Phase 2（级联固有代价）
```
实现要点：两阶段训练于不同的图（147 vs 132 个元关系），HGT 的 `relation_*` 参数第一维即元关系数，
无法直接 `load_state_dict`。已按**元关系三元组重映射**：共享的 132 个精确迁移，
完整图独有的 15 个保持初始化并在输出中标记 `untrained_relation`。

---

## 6. ⚠️ 当前最大的问题：指标不可信

### 6.1 运行间波动 ±0.12
同一条命令、同一图文件、同一 `--seed 1`，6 次结果：
```
99.0043  98.9415  98.9438  98.9924  99.1047  98.8653     极差 0.24
```
`torch.manual_seed` 只固定权重初始化和 KFold shuffle，**cuDNN 内核选择与 DGL 消息传递里的
非确定性 scatter-add 未固定**。

**因此所有小于 ~0.5 分的对比结论作废**，包括：
- 「恢复异构边类型带来 +0.26」→ 噪声
- 「收窄 end_if 后 +0.05」→ 噪声
- 「MANDO-LLM 相对查表多 0.31 分」→ **噪声，即无可测量优势**

### 6.2 代码片段跨折重复 → 指标衡量的是记忆
```
纯字典查表（代码字符串 → 训练折多数标签，无模型/无图/无 HGT/无 LLM）
  P 0.9988   R 0.9752   Buggy-F1 98.69
```
机制：12,036 节点只有 **3,077 个不同代码片段**（25.6%），83.8% 的节点其片段重复出现，
**76.5% 的验证节点在自己那一折的训练集里有完全相同的代码 + 完全相同的标签**。
SolidiFI 把一小撮模板注入 40 个合约，最高的片段重复 **322 次**：
```
x322  'if( ! (msg.sender.send(10 ether) ) ){ revert(); }'
x312  'if( ! success ){ revert(); }'
x232  'if( ! (msg.sender.send(1 ether) ) ){ revert(); }'
```
按合约切折能防止同一合约的节点跨越，**防不住同一段代码跨越**。

**推论：在这个基准上，任何模型侧改进（如关系语义编码）都无法显示出效果——空间被记忆吃满了。**

---

## 6.5 调用边语义缺陷（后期发现，**影响构图正确性**）

三个缺陷已用最小示例 + 真实语料双重实证（`scripts/probe_dummy_edges.py`、
`scripts/probe_call_matching.py`、`scripts/quantify_call_defects.py`）。

### ① `recursive_method_call` 不是调用边，是「声明包含」边
根因：`CFG_solidity.function_list` 注释写「collecting method invocations」，
但判断条件是 `current_node.type in statement_types['method_type']` —— 遍历的是**函数定义**。
于是 `records['function_calls']` 的键是函数定义，值里的 parent 是最近的 `method_type` 祖先，
对顶层函数就是**合约节点**。`add_dummy_edges` 再把它连到函数。

最小示例：`contract NoCalls` 两函数互不调用 → 仍生成 2 条
`contract_declaration → function_definition` 的 `recursive_method_call`。

真实语料：3,981 条该类型边，**源节点 100% 是声明节点**
（contract 3,339 / library 410 / interface 232），**零条真正的递归调用**。占全图边的 20.7%。

### ② 重载扇出 + 子串误连
`CFG_solidity.add_function_call_edges` 的匹配规则：
```python
if '_'.join(dest_method_name.split('_')[:-1]) + '(' in code:
```
剥掉元数后缀再做裸子串匹配。后果：
- `f_1` 与 `f_2` 都变成 `f`，一个 `f(1)` 调用连向**所有同名重载**
- `'f(' in 'notf(3)'` 为真 → **名字以被调名结尾的函数被误连**

真实语料：**375** 个调用者出现重载扇出，**86** 条子串误连
（如 `transferFrom(...)` 被判为调用 `transfer`）。

### ③ 空格漏边
`+ '('` 要求名字与括号紧邻，`safeAdd (x)` 匹配不上。
最小示例：`target (7)` → **0 条边**。真实语料：**403** 处真实调用不可见。

### 由此推翻的一个决策：`add_dummy_edges` 已改为默认关闭

原决策依据是「开启后边数 15,286 → 19,267，与附录 C 精确吻合」。
**该论证无效**：边数是标量，无法区分正确边与错误边。

四条证据对照：

| 证据 | 指向 |
|---|---|
| 边**数** 19,267 吻合 | 开 |
| 边**类型数**符合论文上限 5 | **关** |
| `recursive_method_call` 100% 是从属关系 | **关** |
| 仓库原始默认 | **关** |

实测（`scripts/verify_dummy_switch.sh`）：

```
OFF: 18,312 节点 / 15,286 边 / 边类型 next, external_call, internal_call,
                                      if_true, if_false  = 正好 5 种
                                      （+ jump_next 仅 1 条，可视为噪声）
ON : 18,312 节点 / 19,267 边 / 7 种边类型，超出论文上限 5
```

关闭后的 5 种边类型与 MANDO-HGT 的设计完全对应
（CFG 的 `next`/`if_true`/`if_false` + CG 的 `internal_call`/`external_call`；
tree-sitter 路线没有 Slither 的 `solidity_call`）。

**当前默认：关闭。** 通过环境变量切换：
```bash
MANDO_DUMMY_EDGES=1 python -m scripts.gen_reentrancy_cfg ...   # 开启（旧行为）
```

⚠️ **第 5 节的全部实验结果都是在「开启」状态下跑的**，换默认后需重跑才能纵向对比。
⚠️ **3,981 条边的缺口保持未解释**，而不是用语义错误的边去填平。

---

## 6.6 折划分方式的对照实验（**记忆效应不是主因**）

新增 `--split_by {contract,snippet}`（`node_classifier.py` 与 `classifier_cli.py`，
代码块带 `ADDED` / `END ADDED` 标记，删掉即回退）。

- `contract`（**默认，论文做法**）：切合约列表再展开到节点。仓库原行为。
- `snippet`：按代码文本分组，用 `StratifiedGroupKFold` 保证同一片段整组不跨折。

每次训练结束都会打印一行，**务必核对**：
```
Split mode: <mode>   validation nodes whose exact (code, label) pair was in their
                     training fold: N/M (X%)
```

### 结果

| 配置 | 重复率 | contract 切分 | snippet 切分 |
|---|---|---|---|
| 有 dummy edges | 78.2% / 0% | 98.90 ~ 99.03 | 97.33 |
| 无 dummy edges | 78.4% / 0% | **99.07** | **97.81** |
| 论文 | — | **96.78** | — |

### 结论：**记忆效应存在但不是主因**
去重后重复率降到 **0.0%**，分数只掉 1.3~1.6 分，**仍高于论文的 96.78**。
所以 6.2 节「模型相对查表无可测量优势」的结论**只在 contract 切分下成立**；
去重后仍有 97.81，说明模型确实学到了可泛化的东西。

⚠️ **踩过的坑**：`train_linelevel.sh` / `train_contractlevel.sh` 原本**没有 `"$@"` 转发**，
`--split_by snippet` 会被静默丢弃、悄悄回落到默认。已修复。
那行 `Split mode:` 输出正是抓到这个 bug 的东西。

## 6.7 `add_dummy_edges` 的最终决定：**开启**

6.5 节曾因语义错误把它改为默认关闭，随后实测两种配置的分数：

| | 边数 | 边类型 | contract | snippet |
|---|---|---|---|---|
| ON | 19,267 | 7 | 98.90 | 97.33 |
| OFF | 15,286 | 6（主类型 5） | 99.07 | 97.81 |
| 差 | | | +0.17（噪声内） | +0.48 |

**去掉那 3,981 条边后分数不降反升**，说明模型并不依赖它们。
既然对结果无影响，**选择与论文附录 C 的 19,267 边数吻合的配置**，故改回默认开启。

```bash
MANDO_DUMMY_EDGES=0 python -m scripts.gen_reentrancy_cfg ...   # 构建 15,286 边版本
```

**但解读元关系时必须记住**：这 3,981 条 `recursive_method_call` 是
「合约声明了该函数」的**从属关系，不是调用**（源节点 100% 是声明节点），
且它使边类型达到 7 种、超出论文上限 5。

⚠️ 一个反直觉的后果：**去掉错误的边之后，我们离论文更远了**（+2.12 → +2.29）。
这否定了「结构缺陷导致虚高」这条思路。

### 从节点角度
`add_dummy_edges` **完全不影响节点**：两种配置都是 18,312 节点 / 16 种类型 / 零差异
（`external_function` 节点数为 0，那个分支在本语料从不触发）。
所以「节点数 18,312 吻合论文」这条证据**对这个开关没有证明力**，
只能证明**节点定义**正确。

### MANDO-HGT 如何处理
**它没有这个东西。** MANDO-HGT 用独立 CG + 融合，`add_new_cfg_edges_from_call_graph`
只搬运 CG 的边（`internal_call` / `solidity_call` / `external_call`），
**CG 里不存在任何「合约→函数」的从属边**。`recursive_method_call` 是 tree-sitter 路线独有的产物。

## 6.8 已排除的六个假设（+408 与 +2.2 分的成因）

| 假设 | 验证方式 | 结论 |
|---|---|---|
| 记忆效应是主因 | snippet 去重切分 | ❌ 去重后 97.81 仍高于 96.78 |
| `add_dummy_edges` 错误边撑高 | 去掉后重跑 | ❌ 反而升 0.17~0.48 |
| `end_if` 标签孪生撑高 | 收窄跨度后重跑 | ❌ +0.05，噪声内 |
| 容器节点撑高 | 按类型排除后重算 | ❌ 几乎不变（且该测量本身无效，用的是拟合值） |
| SolidiFI 标注是单行 | `--solidifi_lines start` | ❌ 跌到 1,347，range 才对 |
| 论文用了不同的标注规则 | 枚举 12 种有依据的规则 | ❌ **无一命中 6,570** |

第六项的枚举结果（`scripts/search_labeling_rule.py`）：
```
intersect (current)                 6978   +408
no contract_declaration only        6840   +270
first_line must be annotated        6784   +214
node fully inside annotated range   6758   +188
span <= 10 lines                    6821   +251
no_container                        5689   -881
reentrancy category only            6976   +406
```

---

## 6.9 拿到论文原文与作者原始图之后的决定性发现

### 新增的两份权威资料

| 资料 | 位置 |
|---|---|
| **论文 PDF + 抽取的全文** | `data/MANDO-LLM-TOSEM25.pdf` / `.txt`（30 页，`scripts/extract_paper.py` 抽取） |
| **作者的原始图**（Google Drive） | `data/upstream_mando_llm/{node_detection,graph_detection}/` |

作者的 gpickle 是 **pickle protocol 5**，Python 3.7 读不了。
已装 `pickle5` 反向移植包，并用 `scripts/convert_upstream_graphs.py` 转成 protocol 4
（含 round-trip 指纹校验，确认无损）：
```
upstream_linelevel_cfg.gpickle          11,948 节点 / 7,987 边  / buggy 6,572
upstream_contractlevel_cfg_cg.gpickle   18,312 节点 / 19,267 边 / buggy 6,570
```

### 论文确认的协议（§5.3 + §5.4，与我们**完全一致**）

```
节点特征 512 维（"double size compared with the reimplement of HGT by DGL"，即 256→512）
hidden 128（"reduced half from 256 to 128 to meet our computing resources"）
HGT 2 层 / 8 头
合约级 LR 0.0005→0.01，行级 LR 0.0002→0.005
合约级 5-fold，行级 10-fold，"average scores of all folds"
patience 7，delta 0.001
"we only use the tokenizer of the LLMs instead of passing the input through the LLMs"
```

⚠️ **我曾据 `experiments/node_classification.py` 推测论文用「重复 20 次取 top 50%」，这是错的**。
那是 MANDO-HGT 时代的遗留脚本（路径全是 `buggy_curated`/`curated`/`gesc_matrices`，
且无 tokenizer 分支）。论文明确用 k 折 + 全折平均。**该推测已收回。**

### 论文仍未明示的一点
**token id 序列如何变成 512 维**。§5.3 只解释了为什么选 512（DGL 的 HGT 示例是 256，翻倍），
没说构造方式。我们的截断/padding 实现仍是推断（见 7.3）。

### 两阶段：论文描述是级联，**但评估是并行的**

§4.5 描述级联：
> Phase 1 "filtering out likely clean smart contracts, **preparing them for the second phase**"
> Phase 2 "**For the smart contracts identified as potentially vulnerable in the previous phase**"

§5.1 描述评估：
> "the fine-grained line-level vulnerability detection task **focuses exclusively on the buggy contracts**"

即行级输入是**全部真实 buggy 合约（ground-truth 筛选）**，不是 Phase 1 预测出来的那批。
两阶段各自独立 k 折、各自报告平均分，**论文没有报告端到端级联的指标**。

**仓库代码与论文的评估协议一致**（两个脚本完全独立、无筛选环节）。
`scripts/cascade_detect.py` 是**超出论文范围**的补充，它测出 Phase 1 会漏掉 10 个真实
有漏洞的合约——这个代价论文的评估方式完全绕开了。

### 作者的两张图：**独立构建，不是裁剪关系**

用边内容而非文件名判定（`scripts/verify_upstream_graph_kinds.py`）：

| | 行级 node_detection | 合约级 graph_detection |
|---|---|---|
| 边类型 | `next_line` / `neg_next` / `pos_next` / `end_if`（**4 种**） | 上述 + `recursive_method_call` / `internal_call` / `external_call` / `first_next_line`（**8 种**） |
| call 类边 | **NONE** | 有 |
| 函数→函数的边 | **0 条** | 2,502 条 |
| 合约 | 71（clean 0 个） | 142（71 clean） |
| buggy 节点 | **6,572** | **6,570** |

buggy 数不同（6,572 vs 6,570）证明是两条独立构建路径。
仓库自己的 `classifier_cli.py` 路径解析器也印证：行级→`cfg`，合约级→`cfg_cg`。

⚠️ **论文 §4.5 说 Phase 2 用 HCG（CFG+CG），但发布的资产是纯 CFG。这是实打实的不一致，无法消除。**

### 与我们的图逐项对拍（`scripts/diff_against_upstream.py`）

**合约级：节点完全一致，边类型体系不同**
```
节点 18,312 == 18,312    16 种类型逐类型数量【全部精确相同】
合约 142，标签 71/71，逐合约标签【零分歧】
recursive_method_call 3,981 == 3,981   internal_call 973 == 973   external_call 1,589 == 1,589
```
→ **节点定义与调用边我们都是对的。** `recursive_method_call` 作者确实保留，
所以把它改回开启（6.7 节）是正确的。

**但控制流边错了**：作者把 `next` 细分为 `next_line`(10,161)/`end_if`(568)/`first_next_line`(157)，
我们全塌缩进 `next`(12,035)；且作者 `neg_next` **1,260** 而我们 `if_false` 仅 **110**，
差 1,150 ≈ 上面的 1,149。**大量本该是 `neg_next` 的边被我们错标成了 `next`。**

**行级：+408 的成因终于定位**
```
contract_declaration      +138   ← 作者该类型 buggy 数为 0，我们 138
expression_statement       +72
function_definition        +66
new_variable               +54
if                         +52
end_if                     +26
                          ─────  +408
```
**作者不给合约级容器节点打漏洞标签**，这一项占 138；其余 270 是标注宽度差异。
另外**作者的行级图没有任何声明类节点**（contract/library/interface/struct/modifier/constructor 全 0），
而合约级图有（412/86/45/70/165/165）——仓库里没有能产出这种图的代码路径。

### 用作者的原图训练：**差距只缩小一半，且 nodetype 方向相反**

| 配置 | 我们的图 | **作者的图** | 论文 Table 5 |
|---|---|---|---|
| 行级 `nodetype` | 87.84 | **80.16** | 85.06（MANDO-HGT） |
| 行级 Tokenizer | 98.90 | **97.87** | **96.78** |
| 合约级 `nodetype` | 92.64 | 88.23 | — |
| 合约级 Tokenizer | 90.09 | 87.72 | — |

**同一张图、同一套训练代码，tokenizer 偏高 1.1、nodetype 偏低 4.9——方向相反。**
所以差距不是单一原因，**构图只解释了约一半**（2.12 → 1.09）。

（注：85.06 那行标的是 MANDO-HGT 最佳成绩，而 MANDO-HGT 用 Slither 构图，
所以 nodetype 那一列**本来就不可直接对照**。）

**副产品**：作者图上的片段重复率 77.3%/75.7%，与我们图上的 78.2% 几乎相同
→ **记忆效应是数据集固有属性，不是我们构图引入的。**

## 6.10 README 的 Form-A / Form-B 是 MANDO-HGT 遗留，**不属于 MANDO-LLM**

README 的 Results 目录列了三种配置，三条证据表明它是继承内容：

1. 引用的 4 张结果图**全部不存在**（`assets/` 只有 `MANDO-LLM-full.png/pdf`），全是坏链
2. 链接指向 `anonymous.4open.science/r/ge-sc-FE31`——MANDO-HGT 双盲投稿地址
3. **论文 30 页全文没有 `Form-A`/`Form-B` 这两个词**，只讲 HCG 一种融合

三种配置的含义：

| 配置 | 含义 | 代码 |
|---|---|---|
| **Form-A**（HCFGs+HCGs） | CFG 与 CG **合并成一张图**（靠 `FUNCTION_NAME` 对齐） | `combination_..._helper.py` |
| **HCFGs only** | 只用 CFG | 直接用 `cfg_compressed_graphs.gpickle` |
| **Form-B**（CFGs+CGs） | **不合图**，堆叠两层 HAN：HCFG 层的输出作为 HCG 层的节点特征 | `--node_feature han` + `--cfg_feature_extractor` |

README 第 277 行原文："We also **stack 2 HAN layers** for function-level detection ...
(**It will be deprecated in a future version**)" —— MANDO-LLM 就是那个未来版本。

粒度对应：Form-A/HCFGs-only 的节点是**语句**→行级；Form-B 第二层跑在 HCG 上、节点是**函数**→函数级。

**我们做的对应 Form-A，与论文一致。Form-B 与 HCFGs-only 都不需要复现。**

## 6.11 Slither vs tree-sitter：论文没有对照实验

论文换 tree-sitter 的理由**纯工程性**（§2）：
> Slither "required the **compilation** of smart contracts, which occasionally precipitate
> **version conflicts** and the **absence of necessary libraries** ... needs **more human effort**"

结论只强调 **compiler independence** 与**跨语言可扩展性**。
**通篇没有声称 tree-sitter 语义更丰富，也没声称带来性能提升。**

Table 5 的 MANDO-HGT 85.06 vs MANDO-LLM 96.78 **不能用来回答这个问题**——
图生成与节点特征**两个变量同时变了**（Slither+传统特征 vs tree-sitter+LLM tokenizer）。
§5.5 的消融比较的是「有无 LLM 特征」，不是「Slither vs tree-sitter」。

从实际产物看，**Slither 语义明显更丰富**：

| | Slither | tree-sitter |
|---|---|---|
| **中间表示 IR** | ✅ `node_irs`（SSA 操作序列） | ❌ 仅原始文本 |
| 表达式解析 | ✅ `node_expression` | ❌ |
| 合约/函数归属 | ✅ `contract_name`+`function_fullname` | 仅 `method` 字符串 |
| 语义层级 | 编译后 CFG（基本块、数据流） | 语法树推导 CFG |
| IF 节点粒度 | 仅条件行 | 整个 if 块 |
| 调用解析 | 真正解析 | 裸子串匹配（见 6.5 的三个缺陷） |
| 编译依赖 | 需对应版本 solc | 无 |

**但有个反向因素**：MANDO-LLM 框架里语义主要由 LLM tokenizer 从 `code` 文本提取，
而 `code` 两种路线都有——Slither 的 IR 优势可能被 LLM 特征覆盖，这也许正是作者敢换掉它的原因。

**要做单变量对照实验需要**：装多版本 solc（`auto_version_solc.py` 已改好）+
拉上游三个构图脚本 + 对 142 合约跑 Slither（编译失败率是风险）+ 同样的 tokenizer 特征和 10 折。
**尚未做。**

---

## 7. 未解决的问题

### 7.1 buggy 节点 +408（6,978 vs 6,570）
已测试并**证伪**的三个假设：

| 假设 | 做法 | 结果 |
|---|---|---|
| `end_if` 跨度过宽 | 收窄到闭合行 | 7,026 → 6,978，只补回 48 |
| SolidiFI 标注是单行 | `lines=[loc]` 而非 `range(loc, loc+length)` | 1,347，**偏低 5,223**，证明 range 才对 |
| 容器节点不该标注 | 查上游 Slither 真实产物 | 上游 **FUNCTION_NAME 确实标注**（20/112 buggy，跨度覆盖整个函数） |

上游 Slither 产物 vs 我们的标注率对比（`scripts/compare_upstream_labeling.py`）：
```
上游 (access_control/curated)     我们 (reentrancy 行级)
  FUNCTION_NAME  17.9%              function_definition   54.2%
  EXPRESSION      5.9%              expression_statement  52.5%
  IF              0.0% (跨度单行)    if                    79.7% (跨度整块)
  END_IF          0.0%              end_if                77.4%
  无合约级节点                        contract_declaration  83.6%
  总计            8.1%              总计                  58.0%
```
两处结构差异：**上游无合约级节点**；**上游 IF 只覆盖条件行**，我们覆盖整个 if 块。
但这是 tree-sitter 与 Slither 的固有粒度差异，而我们的节点/边数与论文逐位吻合，
说明图结构就是论文的 —— **+408 的来源仍未定位**。

**重要**：已验证**修好 408 也不会降低 F1**（收窄 end_if 使 buggy −48，F1 反而 +0.05，在噪声内）。
标注数量偏差与 F1 偏高是**两件独立的事**。

### 7.2 与论文 96.78 差 2.2 分（超出噪声，差距真实）
关键矛盾：**论文 96.78 低于查表基线 98.69**。若用同一数据同一切分，不可能低于查表。
推测他们的**折划分方式不同**（可能按代码片段去重），但这无法从 `mando-llm.md` 推断，
需要论文正文的实验设置章节或他们实际的划分代码。

旁证：我们的 `nodetype` 基线 87.84 vs 论文 MANDO-HGT 85.06，**也高 2.8 分**。
两种完全不同的特征偏高幅度相当 → **偏差在数据/标签层，不在特征或模型层**。

### 7.2b 两个 line-level 图文件的区别（容易混淆）

| 文件 | `end_if` 跨度 | buggy 节点 | 与论文 6,570 |
|---|---|---|---|
| `linelevel_tokenizer_ids.gpickle` | 整个 if 语句块 | 7,026 | +456 |
| `linelevel_narrow.gpickle` | **仅闭合行** | 6,978 | +408 |

**图结构完全相同**（12,036 节点 / 11,710 边 / 节点类型分布一致），
**唯一差别是 48 个 `end_if` 节点的标签**。

- 第 5 节的全部结果用的是**宽跨度版** `linelevel_tokenizer_ids.gpickle`
- `linelevel_narrow.gpickle` 只跑过一次（99.0510），是验证「end_if 标签孪生是否撑高分数」的对照
- **narrow 更正确**：`end_if` 是控制流汇合点而非 if 语句本身；宽跨度导致 1025 个 `end_if`
  与相邻 `if` **跨度完全相同、标签完全重复**（841 个双方均为 buggy），
  而上游 Slither 的 `END_IF` 跨度（`[107,108]`、`[129]`）与 `IF` 并不相同
- 但换版本**不改变任何结论**：F1 99.0043 → 99.0510，在 ±0.12 噪声内

**建议后续统一用 narrow**。

### 7.3 论文未明示、由我推断的实现
**token id → 512 维的做法**。论文只说「用 Tokenizer 生成 node feature」，没说怎么变成 512 维。
已实现三种（`--scheme`），默认 `ids`（截断/padding 到 512，用户指定）：

| scheme | 做法 | 信息完整性 | 单次 F1 |
|---|---|---|---|
| **ids**（默认） | token id 序列截断/补齐到 512 | 无损（6278 特征 == 6278 片段） | 98.98 |
| ids_norm | 同上，除以 vocab_size | 无损 | 97.19 |
| hashed_bow | 哈希到 512 桶计数 | **有损**（25 组冲突） | 99.32 |

选 `ids` 的依据：512 读作「序列预算」最贴合 `MAX_INPUT_LENGTH=516` 与 `embedding_dim=512` 两处线索。
**不是按分数选的**（那是向指标拟合）。

---

## 8. 常用命令

```bash
conda activate mando && cd ~/SmartContract/ge-sc-llm
export TREE_SITTER_LIB_DIR=$PWD/build/linux-x86_64

# ---- 重建数据（已有则跳过）----
python -m scripts.gen_reentrancy_cfg \
  --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
  --output_dir /tmp/reentrancy_cfg_full
python scripts/build_labeled_graph.py --cfg_dir /tmp/reentrancy_cfg_full \
  --output experiments/ge-sc-data/source_code/reentrancy/hcg_compressed_graphs.gpickle
python scripts/encode_tokenizer_features.py --scheme ids
python scripts/make_graph_labels.py --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files
bash scripts/make_linelevel_graphs.sh

# ---- 训练 ----
# Phase 2 行级（10-fold，buggy-only）
bash scripts/train_linelevel.sh \
  experiments/ge-sc-data/source_code/reentrancy/linelevel_tokenizer_ids.gpickle \
  inside_token tok_ids
# Phase 1 合约级（5-fold，1:1）
bash scripts/train_contractlevel.sh \
  experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle \
  inside_token tok_ids
# 纯结构基线
bash scripts/train_linelevel.sh   .../linelevel_hcg.gpickle nodetype hcg_nodetype
bash scripts/train_contractlevel.sh .../hcg_compressed_graphs.gpickle nodetype hcg_nodetype

# ---- 级联推理 ----
python scripts/cascade_detect.py

# ---- 校验 ----
python scripts/validate_pipeline.py            # 4 项流水线自洽性校验
python scripts/verify_source_correspondence.py # 图 vs 源文件逐节点对拍
python scripts/measure_fold_leakage.py         # 折间代码重复 + 查表基线
python scripts/repeat_linelevel.sh 3           # 测运行间波动

tensorboard --logdir logs/linelevel_tok_ids
```

---

## 9. 脚本清单（`scripts/`）

**数据构建**：`gen_reentrancy_cfg.py` `build_labeled_graph.py` `line_mapping.py`
`filter_buggy_contracts.py` `make_graph_labels.py` `make_linelevel_graphs.sh`

**节点特征**：`encode_tokenizer_features.py`（论文方法，Tokenizer-only）
`encode_llm_tokens.py`（论文基线，Encoder）`transplant_tokens.py`

**训练/推理**：`train_linelevel.sh` `train_contractlevel.sh` `run_all_linelevel.sh`
`run_all_contractlevel.sh` `cascade_detect.py` `verify_inference.sh` `repeat_linelevel.sh`

**校验/诊断**：`validate_pipeline.py` `verify_source_correspondence.py` `verify_token_interface.py`
`review_tokenizer_features.py` `measure_fold_leakage.py` `diagnose_inflation.py`
`eval_by_nodetype.py` `compare_upstream_labeling.py` `probe_*.py` `cmp_*.py`

**环境/外部资源**：`fetch_grammar.sh` `fetch_model.sh` `fetch_vuln_labels.sh` `fetch_upstream.sh`

---

## 10. 下一步（按优先级）

### 🔴 P0'' — 修控制流边类型（6.9 节新发现，最有依据的一条）
-1. 我们把 `next` / `next_line` / `end_if` / `first_next_line` 全塌缩成 `next`，
    且 `neg_next`(作者 1,260) 被我们错标成 `next`（我们 `if_false` 仅 110，差 1,150）。
    这是与作者图唯一确定的结构性差异，且**节点与调用边已证明完全一致**，
    所以这是目前唯一值得改的构图问题。

### 🔴 P0' — 构图侧：重跑基线
0. `add_dummy_edges` 默认已关闭（见 6.5），第 5 节所有结果都是开启状态下跑的，
   **需用新默认 + `linelevel_narrow` 重跑一遍**，否则纵向不可比。
   注意：重跑后 F1 大概率仍在 98.9 附近 —— 记忆效应（6.2 节）与边语义是两回事。

### 🔴 P0 — 必须先做，否则一切结论无效
1. **按代码片段去重切折**，保证同一片段不跨训练/验证。这最可能解释论文的 96.78，
   也是让基准重新具备区分力的前提。
2. **所有实验改为多种子重复（≥5 次）+ 报告均值±标准差**，用仓库自带的 `t_test.py` 做显著性检验。
   当前 ±0.12 的噪声让任何小于 0.5 分的对比都无意义。

### 🟡 P1 — 补全论文覆盖面
3. 扩展到其余 6 类漏洞（流程已全部脚本化，主要是机时），
   同时可与附录 C 的其余 6 行统计逐位对账，并验证「96.78 是否为 7 类平均」的猜想。
4. 补 Solidity-T5 / StarCoder 两个 tokenizer（论文的三方对比）。

### 🟢 P2 — 功能补全
5. **单合约端到端检测**：给一个新 `.sol` 直接出结果。当前 `infer_smart_contract.py` 走的是
   旧 tree-sitter CFG + `nodetype`，与 HCG + Tokenizer 特征**不兼容**，需改造。
6. 继续定位 buggy 节点 +408（优先级低：已验证不影响 F1）。

### ⛔ 暂不要做
**关系语义编码等模型侧创新**。在 P0 完成之前，基准被记忆效应饱和在 98.98，
而查表基线就有 98.69 —— 任何改进都无从体现。

---

## 附：数据来源

- 语料：`experiments/ge-sc-data/source_code/reentrancy/source_files/` 142 个 `.sol`
  （71 buggy = 31 SmartBugs Curated + 40 SolidiFI；71 clean = SmartBugs Wild）
- 标注：`data/smartbug-dataset/vulnerabilities.json`（已 clone）
  + `data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/BugLog_*.csv`（已 clone）
- 上游参考：`/tmp/mando-upstream/ge-sc/` 与 `/tmp/mando-upstream/ge-sc-transformer/`（sparse clone，重启后需重拉）

**已验证**：语料中的 `buggy_20.sol` 与 SolidiFI 官方文件 MD5 一致，BugLog 行号可直接使用，
`lines = range(loc, loc+length)` 语义经实证确认。语料内仅 1 对重复合约
（`buggy_22.sol` == `buggy_36.sol`）。

##当前的方案既包括contract方式也包括snippet方式


## 11. Codex 近期训练修改与标注工具交接（2026-10-08）

修改 AI：**Codex**。本节是截至2026-10-08的新交接结论；前面的阶段性叙述保留为历史，不应覆盖本节实测证据。详细修改位置、时间、验证和回退见 docs/training_changes_2026-10-07.md，尤其第10、11节。

### 11.1 之前已经完成的训练修改

- 合约池化从 .tolist()/torch.tensor 改为保留张量并 torch.stack，恢复分类损失到HGT的梯度。仅合约分类该池化路径；不是节点训练新补丁。
- 当前合约/节点 patience=7、delta=0.001；OneCycle合约0.0005→0.01→0.0005、节点0.0002→0.005→0.0002。曲线细节是实现选择，不宣称论文给出了完整调度。
- 节点验证改为参数更新后 eval()+no_grad() 重新前向；下一轮恢复train()。
- 每折以最低验证loss保存best.pt；结束保存last.pt，再恢复best重新评估。best与delta/patience计数独立；last只在折结束写，不是每轮完整续训包。
- 日志实时输出与逐轮参数记录沿用当前入口。更早本地构图/标注修改并非全部由Codex实施，不重新归属。

### 11.2 审计结论更新

- 原仓库支持行级CFG和CFG+CG，论文主方案描述融合图；不能固定说“行级只能CFG”。
- 本地narrow与作者全量混合图18,312个节点、19,267条边已逐项对齐，规范化后的节点内容和无类型边连接一致。不同的是控制流类型、标签，以及原始字符串/token表示；不等于全套论文实验已经一致。
- 调用匹配缺陷双方共有；不能用它解释这两份现成混合图的连接差异。
- 410个节点标签不同，净差408，已用端点行为和恢复标注重放解释；旧文“408无法查/不影响F1”的断言不再成立。标签影响F1的独立贡献仍需固定折消融。
- 作者buggy_18标注存在越界；与作者资产一致不等于与当前源码更正确。71个漏洞文件有68份可恢复标注与本地一致，3份不同。
- 上文“96.78可能是7类平均”不成立：它是论文表5 Dataset A 重入CodeT5p的单项结果。旧文把512截断特征称为“无损”也过强。
- 旧文“默认关闭dummy”不是当前状态；当前CFG_solidity.py默认 MANDO_DUMMY_EDGES=1。本轮未改它。

### 11.3 最新已完成的作者混合图实验

| 实验tag | Buggy-F1 | Macro-F1 |
| --- | --- | --- |
| author_hcg_contract_v1 |94.8089%|95.0137%|
| author_hcg_line_v1 |96.8931%|97.0788%|

作者行级混合图由作者完整CFG+CG抽取同一批71漏洞文件得到。更早upstream_best_20261008_v1的行级96.8031%使用的是作者单独CFG文件，不要混用。

### 11.4 本轮新增：scripts/labeling_v2/

所有新增实现、测试和输出都在这个文件夹；没有修改其他既有代码。修改AI为Codex。

- author_compat：使用作者端点/单行记录重放标签，6570个正例、相对narrow翻转410个，保留作者异常及1个其他类别正例以便兼容。
- source_range：使用源码核验过的JSON/CSV，只取reentrancy，保留narrow范围，6976个正例；去掉旧版2个仅属其他类别的正例。
- 两版均保留本地7类边和原token，未改为作者完整8类关系，未重做特征。
- 输出 scripts/labeling_v2/artifacts/labels_v1/<模式>/{contractlevel.gpickle,linelevel.gpickle,graph_labels.json,manifest.json,...}。全量18312/19267，行级12036/11710。
- 全量图节点标注变化所以另存；合约级有效监督输入没有变化，通常无需重跑合约训练。行级监督变化，需要新实验。
- 每节点标签、非标签属性不变量、真实训练标签读取与保存重载通过；12项回归测试通过。四份源码仅同位置pragma变化单独记录。
- 本轮未启动新训练。命令见 scripts/labeling_v2/README.md；建议先用labels_author_compat_v1，再用labels_source_range_v1，顺序运行。
- 当前折划分随机性、模板重复、最佳权重使用同一留出折等评估限制仍存在；未因新增标签工具而解决。


## 12. Claude 会话记录（2026-10-09 ~ 2026-10-10）

修改 AI：**Claude（Opus 5.5）**。本节按问答顺序记录这一轮会话的结论、结果和存疑；与前文冲突时以本节为准。
之后的问答继续追加在本节末尾的"12.12 后续问答"里。

约定（用户 2026-10-09 提出）：测试代码、不确定是否进正式代码的脚本一律放 `Test_code/`。

### 12.1 原仓库与本地补充的区分

- 基线是 `MANDO-Project/ge-sc-llm` 的 HEAD `6c8d241`，本地改动均未提交。
- 被修改的原仓库文件是 **9 个**（第 2 节写 8 个，漏了 `sco_models/model_hgt.py`）：`auto_version_solc.py`、`graph_classifier.py`、`node_classifier.py`、`CFG_solidity.py`、`solidity_nodes.py`、`classifier_cli.py`、`model_hgt.py`、`tools.py`、`visualization.py`。
- 完全新增：`scripts/`、`Test_code/`、`HANDOVER.md`、`docs/training_changes_2026-10-07.md`、`tests/test_early_stopping.py`；`data/`、所有 `*.gpickle`/`*.json`、`models/`、`logs/`、`outputs/`、`build/` 被 `.gitignore` 忽略，都是本地生成或下载的。
- `ge-sc-llm-backup/` **不是干净的原仓库**，是 9 月 16 日前后的快照，已含早期改动。要看原版用 `git show HEAD:<文件>`。
- `ge-sc-transformer/` 是前作 MANDO-HGT 的原仓库，工作区干净。

### 12.2 参数、早停、最优权重审查

| 项目 | 论文 | 原仓库 HEAD 实际行为 | 当前 |
|---|---|---|---|
| 特征 / hidden / 层 / 头 | 512 / 128 / 2 / 8 | 同 | 同 |
| 折数 | 合约 5，行级 10 | 同 | 同 |
| patience / delta | 7 / 0.001 | 行级 7/0.001；合约 10/0.005 | 均 7/0.001 |
| 合约级 LR | 0.0005–0.01 | 调度器不步进，恒定 0.0004 | 0.0005→0.01→0.0005 |
| 行级 LR | 0.0002–0.005 | 0.0002→0.005→约 2e-8 | 0.0002→0.005→0.0002 |
| epoch 上限 | **未说明** | CLI 默认 100；README 与 quickstart 示例用 50 | 脚本传 50 |

- 早停判定、best/last 保存、行级更新后重新 eval、合约级梯度修复，逐行核对后实现均正确。
- `classifier_cli.py` 中 `hidden_units=8`、`dropout=0.6`、`weight_decay=0.001` 是死配置；实际 dropout 0.2，合约级 weight decay 5e-6，行级 0。
- **"恢复最优权重"是论文和原代码都没有的做法**，原代码评估停止时的权重。两种口径差别很大，今后 best 和 last 都要报（`scripts/eval_best_last.py`）。
- 512 维特征是原始 token id 截断/补齐，未归一化；作者图里没有 token，这一步无法对照。
- 存疑：OneCycle 总步数等于 epoch 数，50 与 100 会使峰值落在不同轮次，论文无法确认。

### 12.3 折种子修复（2026-10-09，已改正式代码）

- `graph_classifier.py`：`StratifiedKFold` 加 `random_state=seed`，并在按文件名排序后的合约列表上划分。
- `node_classifier.py`：`KFold` 加 `random_state=seed`，合约列表先排序。
- 改动处标记 `FOLD SEED FIX (2026-10-09)`，原语句保留为注释。
- 第 6.1 节"torch.manual_seed 固定了 KFold shuffle"的说法是错的。修复前所有主入口运行的折都不同，彼此不可比；修复后同一 seed 完全可复现（Codex 与 Claude 两套独立运行结果逐位相同）。

### 12.4 作者发布的图（7 类已全部下载）

位置 `data/upstream_mando_llm/{graph_detection,node_detection}/`。

- `graph_detection/*_tree_sitter_cfg_cg_*`：CFG+CG 融合图，全部合约，8 种边类型。7 类的节点数、边数、漏洞节点数与论文 Table 1 **逐位相同**。
- `node_detection/*_tree_sitter_cfg_*`：纯 CFG，只有漏洞合约，4 种边类型，无声明类节点。它不是融合图的子图，是另一次独立构建。访问控制这一份未下载，也不需要。
- **论文两个阶段用的都是融合图**，行级是融合图限制到漏洞合约。依据：
  - 论文 §4.5、§5.5 的表述；
  - 仓库里作者留下的行级 node2vec 特征矩阵行数：重入 12,036、unchecked_low_level_calls 9,332，与融合图漏洞子图吻合，与纯 CFG 图（11,948 / 9,351）不吻合；
  - `experiments/token_baselines.py` 中 `GRAPH_TYPE='cfg_cg'`、`K_FOLDS=10`。
- `node_detection` 的纯 CFG 图是 quickstart / 单文件推理的演示资产（nodetype 特征），不是论文配置。早先在它上面跑出的重入 96.80 不属于论文口径。
- 存疑：行级特征矩阵只留下 2 类；MANDO-LLM 本体行级训练用的图没有直接留痕，是由论文表述加基线产物推出的。
- 行级子图应按**合约标签**选漏洞合约，不能按"有无正例节点"选。访问控制（56/57）和 unchecked_low_level_calls（94/95）各有一个漏洞合约没有任何正例节点。`scripts/filter_buggy_contracts.py` 是按后者筛的，这两类会少一个合约。

### 12.5 作者的图节点标签是怎么来的

论文只有 §5.1 一句话，没有算法；原仓库 HEAD 没有任何写入 `node_info_vulnerabilities` 的代码。从 7 张作者图还原出的通用规则：

1. 取标注行（原始行号）：SolidiFI 取 BugLog 每行的 `range(loc, loc+length)`；SmartBugs 取 `vulnerabilities.json` 的 `lines`。
2. 换算到去注释、去空行后的坐标。
3. 节点只取 `[首行, 末行]` 两个端点；`end_if`/`end_loop` 取语句的 0 基起始行（单个值）。
4. 端点命中标注行即为漏洞节点，整条记录挂到节点上。

- 第 3、4 步在 7 张融合图和 6 张 CFG 图上都是 **0 个不一致**；按整段范围算每类有 111–260 个不一致。
- 推断（未证实）：前作的标注函数是"节点行列表与漏洞行求交"，Slither 给完整行列表，换成 tree-sitter 后只存起止两个数，求交退化成端点匹配。
- 后果：跨多行节点只有首/末行被标注才是正例，作者图里 `contract_declaration` 没有正例。

作者数据里的两类问题：

- **423 个漏洞合约中有 17 个文件的标注无法由规则推出。** 13 个是 SolidiFI 的 `buggy_12/18/26.sol`，共同点是 BugLog 中有重叠的行；作者的换算从重叠处附近失效，之后的标注行全部丢失，换成了超出文件长度的行号（与 SolidiFI TOD 类 BugLog 的原始行号 67%–100% 重合）。另 4 个是 SmartBugs 文件。
- 每类的 `buggy_20.sol` 少 2 行，是同一行既有代码又有 `/* */` 注释的行未被换算。
- 存疑：13 个文件的失效位置没有还原成规则。"第一个重复行即停"只能解释其中 8 个。

数据集核查结论：本地源码、SolidiFI CSV、前作标注 JSON 互相一致；预处理文本与作者的 `cleaned_buggy_curated` 完全相同；SmartBugs JSON 本地副本与前作副本只有 2 条记录差 1–2 行。**数据集和本地构图没有问题，与作者的差异全部出在节点标签这一步。**

### 12.6 标注器（两套，核心相同）

| | `Test_code/label_pipeline`（Codex） | `Test_code/labeling_v3`（Claude） |
|---|---|---|
| 核心规则 | 上面四步 | 相同，独立写成 |
| 干净标签的 7 类正例数 | 3114 / 5722 / 4106 / 10889 / 6784 / 6020 / 2435 | `clean` 模式完全相同 |
| 作者异常标注 | 不复制，只作对照 | 另有 `author` 模式 + `author_overrides.json`（17 个文件），7 类与作者逐节点 0 差异 |
| 来源核验与测试 | 更完整 | 无单元测试 |

- 两套是先后独立写的，`clean` 部分重复。建议以 `label_pipeline` 作干净标签的基础，`labeling_v3` 只保留例外表和 `author` 模式。
- 干净标签与作者标签的节点差：access_control 137、arithmetic 327、denial_of_service 0、front_running 491、reentrancy 216、time_manipulation 220、unchecked_low_level_calls 91。
- `label_pipeline` 另外发现：重入 `BugLog_18.csv` 两行长度疑似互换；`tx.origin/BugLog_36.csv` 多一列。
- 本地图目前只有重入和访问控制；其余 5 类只在作者图节点上验证了规则，**本地构图尚未做**。

### 12.7 训练结果（seed=1，固定折）

Buggy-F1 / Macro-F1，各折平均。合约级不使用节点标签。

| 任务 | 图 | 标签 | best | last | 论文 |
|---|---|---|---|---|---|
| 重入 合约级 | 本地 | — | 94.16 / 94.35 | 89.69 / 89.40 | 91.67 / 91.49 |
| 重入 行级 | 本地 | author | 95.47 / 95.64 | 96.47 / 96.65 | 96.78 |
| 重入 行级 | 本地 | clean | 99.10 / 99.14 | 99.26 / 99.25 | — |
| 访问控制 合约级 | 本地 | — | 95.46 / 95.62 | 84.96 / 85.08 | 86.71 / 85.63 |
| 访问控制 行级 | 本地 | author | 96.40 / 97.17 | 96.10 / 96.89 | 94.53 |
| 访问控制 行级 | 本地 | clean | 99.03 / 99.17 | 98.86 / 99.01 | — |
| 访问控制 合约级 | 作者 | — | 93.56 / 93.83 | 86.29 / 85.79 | 86.71 / 85.63 |
| 访问控制 行级 | 作者 | author | 96.02 / 96.89 | 95.11 / 96.11 | 94.53 |

- 产物：`Test_code/labeling_v3/runs/v1/`、`scripts/access_control_test/runs/author_graph_v1/`。
- 合约级 last 与论文接近，best 高出 2.5–8.7 分 → 论文报告的更像是停止时的权重。
- 行级用作者标签接近论文，用干净标签到 99。
- 存疑：单种子；`author` 标签下行级各折标准差 6–11 分，合约级 4–8 分，1–2 分的差别不足以下结论。验证折同时用于早停、选轮和报分，不是独立测试成绩。

### 12.8 为什么行级是 99：基准饱和，不是代码问题

诊断脚本 `Test_code/benchmark_headroom/diagnose.py`（同一批折、同一批权重，不训练），结果在 `diagnosis.json`。

行级，各折平均 Buggy-F1：

| 实验 | 正例在 SolidiFI 文件的比例 | 验证正例在训练集有同代码正例 | HGT | 查表 | 正则 | HGT 仅 SolidiFI | HGT 仅 SmartBugs（正例数） |
|---|---|---|---|---|---|---|---|
| 重入 本地图 clean | 99.51% | 99.78% | 99.10 | 81.04 | 88.98 | 99.62 | 60.00（33） |
| 重入 本地图 author | 99.50% | 99.77% | 95.47 | 79.04 | 87.25 | 96.88 | 42.42（33） |
| 重入 作者图 author | 99.50% | 99.80% | 96.89 | 82.36 | 87.79 | 97.53 | 45.78（33） |
| 访问控制 本地图 clean | 99.29% | 98.94% | 99.03 | 99.25 | 81.97 | 99.41 | 25.81（22） |
| 访问控制 本地图 author | 99.33% | 98.99% | 96.40 | 96.68 | 80.10 | 97.18 | 14.29（20） |
| 访问控制 作者图 author | 99.33% | 98.99% | 96.02 | 96.64 | 80.11 | 96.95 | 0.00（20） |

- 查表 = "节点类型 + 代码文本 → 训练折里的多数标签"；正则 = 代码含 `re_ent数字` / `txorigin数字` 即判正。两者都不用图和神经网络。
- 访问控制上查表不低于 HGT；重入上查表 81（同一段代码在正负例里都出现，需要上下文），HGT 确有增益。
- **作者的图与本地图在这些指标上几乎一样**：数据构成相同，基线分数相差不到 2 分。这是数据集固有性质，不是本地构图引入的。
- 论文的 96.78 低于 99，是因为作者那 17 个损坏文件给分数设了上限，不是任务更难。

合约级（留出折上判对的合约数）：

| 实验 | HGT Buggy-F1 | 正则规则 | SolidiFI 漏洞合约 | SmartBugs 漏洞合约 | 干净合约 |
|---|---|---|---|---|---|
| 重入 本地图 | 94.29 | 72.07 | 40/40 | 26/31 | 68/71 |
| 重入 作者图 | 94.96 | 72.07 | 40/40 | 26/31 | 69/71 |
| 访问控制 本地图 | 95.50 | 82.47 | 40/40 | 13/17 | 56/57 |
| 访问控制 作者图 | 93.58 | 82.47 | 40/40 | 11/17 | 56/57 |

- 40 个 SolidiFI 合约一条正则就能全对，真正的难点只有 17–31 个 SmartBugs 合约。
- 审查排除了泄漏：特征只来自节点自己的代码；验证节点标签在训练时被掩掉；按合约划分，节点不跨折。

### 12.9 划分方式与两个评估改进的含义

- **当前划分**：按合约。合约级 142/114 个合约分 5 折；行级 71/57 个漏洞合约分 10 折，一个合约的全部节点在同一折。同一段注入模板可以同时出现在训练折和验证折的不同合约里。
- **按来源分开报告**：训练和划分不变，只是把留出预测按合约来源（SolidiFI 注入 / SmartBugs 真实）分别算指标，不让占 99% 的注入正例淹没真实漏洞的表现。
- **模板隔离划分**：把同一注入模板的所有出现放进同一折，使验证时遇到的模板训练时没见过。需要先把标识符里的编号归一化（如 `re_ent33` → `re_ent`），否则同一模板只差一个编号仍会跨折。第 6.6 节的 snippet 划分按原始文本分组，所以仍有 97.8。

### 12.10 创新空间

Dataset A 的总分上没有空间。可选的有区分度的口径，按成本排序：

1. 按来源分开报告（零成本；SmartBugs 正例只有 33 / 22 个节点，波动大）。
2. 跨来源评估：SolidiFI 训练，SmartBugs 测试。
3. 模板隔离划分。
4. 换 Dataset B（DAppSCAN）：论文行级重入 84.77、访问控制 71.78，本身有空间；需重新准备数据和图。

### 12.11 本轮新增文件

- 正式代码改动：仅 12.3 的折种子修复。
- `scripts/`（提出 Test_code 约定之前写的，可移走）：`eval_best_last.py`、`access_control_test/prepare_author_graph.py`、`access_control_test/run_author_graph.sh`。
- `Test_code/author_graph_audit/`：7 类作者图审计、行级用图判定。
- `Test_code/dataset_check/`：数据集与 CSV 核查、作者标注失效点探针。
- `Test_code/labeling_v3/`：标注器、例外表、带标签图 `artifacts/v1/`、训练 `runs/v1/`。
- `Test_code/benchmark_headroom/`：饱和诊断。

### 12.12 后续问答

（之后的问答追加在这里。）

#### 2026-10-10：DFG/DDG 方案可行性，以及 Slither 与 tree-sitter（仅分析，未改代码）

**问 1：`scripts/DFG/` 下的 DDG 方案可行吗？在标签不确定、F1 已到 99 的情况下怎么开展？**

方案本身（两份文档）：在原节点上只加 `def_use` 边，不加节点、不改特征、不改 HGT；基于作用域解析 + 到达定义；先做函数内，E0/E1/E2 + 随机边对照。设计是克制且可消融的，工程上可行。

审查出的风险：

- **第一版覆盖范围与漏洞模式错位。** MVP 只跟踪局部变量和形参；而重入的关键依赖是状态变量和 mapping（读余额 → 外部调用 → 写余额），文档把它放在第二阶段。只做 MVP，重入漏洞代码里几乎加不上边。访问控制（形参 → `require(tx.origin == …)`）能覆盖。
- **到达定义依赖正确的函数内 CFG，而本地 CFG 有已知缺陷**：1,150 条本应是 false 分支的边被标成 `next`；`recursive_method_call` 是"合约包含函数"而非控制流；调用边混在同一张图里。做数据流分析前必须先抽出干净的函数内 CFG 并验证分支与循环回边。
- **节点粒度粗**：`if` 节点覆盖整个 if 块，`function_definition` 覆盖整个函数；图里没有保存 AST 引用和字节区间，def/use 映射回节点需要重新从 tree-sitter 取。
- `reflect_graph` 会用同名关系补反向边，新增的 `def_use` 必须单独处理（文档已注意到）。

关于"标签不确定"：现在已经不构成障碍。

- 作者的规则已还原，17 个异常文件已定位；干净标签可由公开数据独立生成并验证。
- DDG 实验是 E0 对 E1 的**相对比较**，两组用同一套节点和标签，只差边。只要固定一套标签政策，标签的绝对正确性不影响结论。建议主结果用干净标签，再用作者标签复核方向是否一致。

关于"没有提升空间"：这是真正的障碍，必须先解决评估口径再写 DDG。

- Dataset A 行级总分 99，查表基线同样水平；合约级各折标准差 4–8 分。DDG 即使有效，在这个口径上也测不出来。
- 模型真正出错的地方是 SmartBugs 真实合约（行级 F1 60 / 26；合约级 26/31、13/17），但样本太小（33 / 22 个正例节点），单类上没有统计效力。

建议的开展顺序：

1. **先定评估口径并建立 E0 基线**（不涉及 DDG）：固定干净标签、固定折、至少 5 个种子、best 和 last 都报；除总分外固定报告按来源拆分、跨来源（SolidiFI 训练 → SmartBugs 测试）两项。把 7 类的 SmartBugs 真实合约合起来看，样本才够。
2. **估计最小可检测差异**：用多种子 E0 的波动算出"多大的提升才算数"。如果连 3–5 分的差异都测不出，就必须换 Dataset B。
3. **先做便宜的可行性探针，再做完整实现**：
   - 随机边负对照先跑：如果随便加边分数也不动，说明这个口径对图结构不敏感。
   - 在能编译的子集上用 Slither 现成的数据依赖作为"上限参考"加边。如果连 Slither 的精确依赖都没有收益，就不必投入 tree-sitter 版的到达定义分析。
4. 探针有信号后再按文档实现，且第一版就应包含状态变量和 mapping 的精确匹配，否则对重入无意义。
5. 最终主实验建议放在 Dataset B（DAppSCAN），论文在其上行级 72–92，有空间且是真实代码。

存疑：DDG 是否有收益完全未知；本地 CFG 的分支边缺陷对数据流分析的影响未量化；Dataset B 的数据和图尚未准备。

**问 2：如果用 Slither 构建 CFG+CG，结果会不会比 tree-sitter 更好？**

- **没有直接证据。** 论文没有做这个对照；Table 5 里 MANDO-HGT（Slither）85.06 对 MANDO-LLM（tree-sitter）96.78，同时换了构图和特征，不能用来回答。
- **在 Dataset A 上预计看不出差别。** 分数主要来自 token 特征识别注入模板：只换边类型的对照差 0.05 分；纯结构特征（nodetype）只有 80–88。构图质量在这个基准上不是瓶颈。
- **语义上 Slither 更准**：真正解析调用（本地是子串匹配，有重载扇出、误连、漏边）、有 IR、有现成的数据依赖、处理继承和修饰器。这些优势可能体现在真实合约和跨来源评估上，但未验证。
- **代价**：必须编译。Dataset A 需要多个 solc 版本，前作访问控制 57 个漏洞合约只生成了 56 个 Slither 图；Dataset B 的 DApp 项目依赖多，编译失败率会更高，这正是论文换 tree-sitter 的理由。
- **不可直接与论文比**：Slither 的节点划分不同（IF 只含条件行、无合约级节点），节点数和标签数都会变。
- 建议：主流程不换。把 Slither 用作可编译子集上的参考实现，一是给 DDG 做上限探针，二是做"构图质量是否重要"的单变量对照（同特征、同折、同标签政策）。

#### 2026-10-11："定评估口径"的含义，以及跨来源评估与原实验的关系（仅分析）

**问：现在不是已经有评估方法了吗？SolidiFI 训练、SmartBugs 测试不是和原实验有差别吗？**

- 现有评估方法（按合约 5 折 / 10 折，报各折平均 Buggy-F1 和 Macro-F1）不用换。"定口径"指把这个方法里还没定死的四个选项各选一个值写死，使"原图"与"原图 + DDG"可以公平比较：

| 选项 | 可选值 | 已测到的影响 |
|---|---|---|
| 节点标签 | 干净 / 作者 | 行级 2.5–3.5 分 |
| 评哪一轮权重 | best / last | 合约级 4.5–10.5 分 |
| 用哪张图 | 本地 / 作者 | 2 分以内 |
| 种子数 | 目前都是 1 个 | 各折标准差 4–11 分 |

- 用户的质疑成立：跨来源评估是**另一个实验**，不是原实验的一种算分方式。三种做法对原实验的偏离程度不同：
  - 按来源分开报告：训练和划分不变，只是多拆两行，是原实验的补充统计。
  - 跨来源评估、模板隔离划分：训练集和划分都变了，是新实验，不能与论文数字比；基线必须在新协议下重跑。
- 更正上一条的建议：跨来源评估在 Dataset A 上不适合当主战场。测试集太小（31 / 17 个合约，33 / 22 个正例节点）；两个来源代码风格差距大，分数可能接近地板；合约级需要干净合约，而干净合约都来自 SmartBugs Wild，"只用 SolidiFI 训练"在合约级上不成立。它只适合做一次性的压力测试。

修正后的顺序：

1. 主实验保持论文原协议，把四个选项定死，至少 5 个种子。
2. 固定附带按来源拆分的两行。
3. 用多种子基线估计最小可检测差异，判断 Dataset A 上是否有空间（预期没有）。
4. 没有空间就换数据集而不是换协议：Dataset B 仍用论文原协议，论文结果 72–92，有空间且可与论文直接对比。

待办 / 存疑：Dataset B（DAppSCAN）的源码和标注本地没有，`.gitignore` 排除了 `experiments/DAppSCAN/`；作者 Drive 上是否有 Dataset B 的图尚未查。

#### 2026-10-11：Dataset B 的数据和图是否可得（只读检查，脚本 `Test_code/dataset_check/check_dataset_b.py`）

**结论：作者没有发布 Dataset B 的任何东西，只能自己从 DAppSCAN 原始数据重建，且无法与论文 Table 2 逐位对齐。**

- 本地：两个仓库里没有任何 DAppSCAN / Dataset B 相关的文件。`experiments/ge-sc-data/source_code/<bug>/source_files` 的合约数全部等于 Dataset A（114/120/92/88/142/100/190），远小于论文 Table 2（244/372/316/252/326/172/246）。
- 原仓库：唯一的提及是 `.gitignore` 里的 `experiments/DAppSCAN/`，说明作者本地有这个目录但没有提交。远端只有 `TOSEM-release` 一个分支，README 不提 Dataset B。
- 作者 Drive（据 10-09 保存的目录页）：`graph_detection` 和 `node_detection` 下只有 7 类 Dataset A 的图和合约标签，没有 DAppSCAN 或 Dataset B。
- DAppSCAN 原始数据是公开的（github.com/InPlusLab/DAppSCAN）：`DAppSCAN-source` 下有 `contracts`、`audit_report`、`SWC_source`。README 称 682 个 DApp、21,457 个 Solidity 文件、1,646 个 SWC 实例；论文摘要写 39,904 个文件、1,618 个弱点，两处数字不一致。
- 作者没有公开的三步处理：SWC 类别到 7 类的映射（论文引用 MultiTagging）、614 个漏洞文件的筛选、每类配多少 SolidiFI 和哪些干净合约。所以即使重建，合约数、节点数、漏洞节点数都不会与 Table 2 相同。
- 存疑：`SWC_source` 的标注格式没有核实，不确定是否给到行号；这决定行级任务能不能做。DAppSCAN 论文自己说明这些文件可能无法直接编译，因此只能走 tree-sitter 路线。

附带发现：Drive 的两个文件夹里各有 7 个**不带 `tree_sitter` 的** `<bug>_cfg_cg_compressed_graphs.gpickle`，本地未下载。很可能是前作用 Slither 构建的 Dataset A 图（未证实）。如果是，它就是回答"Slither 与 tree-sitter 哪个好"的现成材料，不用自己装多版本 solc 去构图。

可选路径：
1. 向作者要 Dataset B 的图或处理脚本（最省事，结果可与论文直接对比）。
2. 自己从 DAppSCAN 重建一个"类 Dataset B"：先核实 `SWC_source` 标注格式，再做类别映射和构图。工作量大，且只能和自己重跑的基线比。
3. 先下载并检查 Drive 上那 7 个非 tree-sitter 图，成本最低。

#### 2026-10-11：现在就设计 DDG 的话，先做什么（仅方案，未改代码，待用户确认）

**问：暂时先做 DDG 这个点，方案怎么设计，先做什么，要先做评估口径吗？**

评估口径不需要单独做完，但"冻结基线"必须在任何 DDG 实验之前完成，工作量很小：

| 项目 | 取值 |
|---|---|
| 节点标签 | 干净标签 |
| 图 | 本地构建的融合图 |
| 折 | 固定（seed 决定） |
| 种子 | 至少 5 个 |
| 权重 | best 和 last 都记 |
| 附带统计 | 按来源拆分 |

对 `scripts/DFG/` 两份文档的三处修改建议：

1. **第一版就包含函数内的状态变量和 mapping。** 只做局部变量和形参，重入代码里几乎加不上边。规则：同一函数内访问表达式文本完全相同才算同一位置，否则不连；跨函数状态依赖仍后置。
2. **到达定义只需要 CFG 的连通关系，不需要边类型。** 更正前一条的担心：1,150 条 false 分支被标成 `next` 不影响数据流分析。需要做的是剔除 `internal_call`、`external_call`、`recursive_method_call` 三类非控制流的边，并验证循环回边和 `end_if` 汇合。
3. **节点与语法树的对应是现成的。** 节点标签里带语法树节点编号（`44-function_definition-9-11` 的 44），属性里有 `file_node_id`，对同一源码重新解析即可找回。注意 `if` 节点的读取只取条件表达式；`function_definition` 节点作为形参定义点。

执行顺序：

1. 冻结基线（5 种子，重入 + 访问控制）。
2. 随机边对照先跑：加同等数量级的函数内随机边。如果分数不动，提前知道该基准对图结构不敏感。
3. 在 `Test_code/` 下实现 DDG 构建，输出只多 `def_use` 边的新图，节点、标签、特征不变。
4. 训练前验证边：文档的 8 个单元测试 + 人工抽查。
5. 正式对比：基线 / +正向 `def_use` / +正向和独立命名的反向边，同折同种子，报配对差值。

预期：Dataset A 总分上看不出效果；值得看的是 SmartBugs 真实合约那一行和合约级 SmartBugs 判对数，但样本小。这一轮的现实目标是把边做对并摸清上限，证明效果仍需要有空间的数据集。

待用户决定：第一版是否包含函数内状态变量；是否启动第 1、2 步训练。

#### 2026-10-11：冻结基线是否同时做"自己的图 + 标签"和"作者的图 + 标签"（方案，待确认）

用户提议两套都做以便对比。结论：应该做，并建议做成三套，因为两套之间同时差了标签、边类型、token 输入文本三样，无法归因。

| 配置 | 图 | 标签 | 用途 |
|---|---|---|---|
| A | 作者的图 | 作者标签 | 复现锚点，对论文 |
| B | 本地图 | 作者标签（`labeling_v3` author 模式） | A 对 B 只差构图；B 对 C 只差标签 |
| C | 本地图 | 干净标签 | DDG 实验的基线 |

- B、C 的图已在 `Test_code/labeling_v3/artifacts/v1/`。
- 三套合约文件名相同，同一 seed 得到同一组折，可逐折配对。重入的作者图旧运行是折种子修复前跑的，需重跑。
- 作者图的行级输入要按合约标签重选（访问控制应为 57 个合约，旧运行是 56 个）。
- 作者图没有 token，仍用其保存的代码文本重新编码，计入"构图差异"。
- 机时：合约级不使用节点标签，B、C 共用。每个种子 10 次训练约 1 小时；5 个种子约 5 小时。
- 状态：尚未启动，等用户确认种子数。


#### 2026-10-12：DDG 第一阶段已实施（修改 AI：Codex）

本条是当前实现状态，覆盖前面 DDG 方案中“尚未实现”“放 Test_code”“首版必须包含mapping”等历史建议；其余历史不删。用户本轮要求函数内正向 Definition–Use、只新增 DATA_DEF_USE，暂不加REV、不新增变量节点。

- 新逻辑、测试、示例、审计全部在 scripts/DFG/。原生产代码只改 sco_models/graph_utils.py::reflect_graph：精确名 DATA_DEF_USE 保持方向，旧关系反射原样保留。
- 已实现双AST/UTF-8坐标、版本作用域、标量DEF/USE、独立语义CFG、固定点到达定义、原HCG严格投影、附边不变量、use_ddg开关、旁路checkpoint输入/schema校验。
- 不改原tokenizer、HGT核心、两阶段检测逻辑、标签、早停、LR或梯度修复。保存现有节点与全部原边，复杂/不确定情况保留图并报告回退。
- 最终测试 **140 passed = DDG 121 + 原测试19**。两类HGT在inside_token下forward/backward、DDG关系梯度、参数更新及checkpoint重载通过。E0对修改前reflect的权重和eval输出逐位一致。
- 最小例用真实缓存CodeT5p-770m tokenizer及原encode_ids：11节点/12边→11节点/19边，新增7条DATA_DEF_USE；节点和合约模型各一次优化，重载逐位一致。**没有新正式F1结果**。
- 真实buggy_18单文件：重入作者/本地图均74条新增边，访问控制均114条；按原源码span对齐相同，基础属性不变。每组10个未映射facts来自5个无HCG节点的emit，未猜最近行。
- 修复审查发现的for update粒度错误：现i++映射自己的原节点，非整个for头；原HCG/CFG不变。modifier、引用类型、复杂副作用等仍回退。
- 原图生成时源码SHA通常未知；本轮记录的是提供源码摘要及节点文本/锚点一致性，不能说完整恢复了作者历史生成过程。
- 本版覆盖率仅针对受支持标量facts；没有实现完整state/mapping、跨函数、隐式返回定位、任意源码cascade或完整消融runner。保留标签只保证控制变量，不能证明标签绝对正确或DDG必然提升。
- 完整E0/E1实验仍需固定折、标签、token、best/last及种子，并在每折对齐共同初始化；原训练器不会自动调用新schema校验器。

文档/产物：
- scripts/DFG/IMPLEMENTATION_NOTES.md：十阶段逐项文件、原因、逻辑、测试、遗留问题。
- docs/training_changes_2026-10-07.md **第12节**：详细修改与回退记录。
- scripts/DFG/README.md：验证、开关、附边和训练接入命令。
- scripts/DFG/artifacts/minimal_20261012_v1/result.json：最小端到端结果；audit/phase*.log为阶段日志。
- scripts/DFG/audit/real_projection_probe.json：两类作者/本地真实图单文件审计。
- scripts/DFG/audit/implementation_before_2026-10-12.json 与 implementation_after_2026-10-12.json：本轮范围/摘要核验，原代码和文档快照同目录。

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py
~~~

最简回退：使用原图/--no_ddg，原反射函数无需撤回。若必须撤回代码接入，核对文件摘要后只移除 DDG FORWARD FIX 精确分支，勿整文件 git restore。两份最初方案文档和2026-10-11分析报告保持历史原文未改。


#### 2026-10-12：DDG 主协议 paper_kfold 已接入（修改 AI：Codex）

本条为最新实验协议状态。旧 ddg-nested-paired-v1 保留为 nested_strict 旁路；不覆盖旧结果、不改变旧严格支持策略。默认入口改为新增的 scripts.DFG.experiments.run_experiment，默认 protocol=paper_kfold。

- 主划分：合约5折、节点10折；新 train=旧 inner_train∪inner_val，新 val=旧 outer_test；同 val 用于早停、选 best 和评分，明确叫 CV validation，不能称 independent outer test。
- 全固定任务图注册和前向；节点用文件对应的 node mask、合约用文件 batch 监督。E0/E1 各注册自己的 schema，语义共同初始化，不给 E0 填空 DDG。
- 训练未见但已注册的类型/关系允许预测并审计；错字典、未注册、不一致输入仍报错；验证独有 DDG 不强制非零训练梯度。不删边/文件，不换 seed。
- 所有新实现和42项新测试位于 scripts/DFG/experiments/；46个冻结核心代码文件未改，原DDG/HGT/tokenizer/训练脚本未改；旧prepared、标签、token和nested日志未改。
- 回归：实验95 + DDG170 + 原项目25 = 290 passed；0失败、0跳过。30主折结构审计全部通过，21折含已注册但train未见schema，均保留。
- 四任务fold0、E0/E1各3轮检查完成；best/last均为第3轮，重载逐位一致，预测重算一致。仅短检查，不代表完整CV成绩或DDG最终收益。

| 任务（fold0，CV validation） | E0 Buggy-F1 / Macro-F1 | E1 Buggy-F1 / Macro-F1 |
|---|---:|---:|
| 重入/合约 | 84.6154 / 86.0577 | 84.6154 / 86.0577 |
| 重入/节点 | 78.3767 / 72.0414 | 78.3767 / 72.0414 |
| 访问控制/合约 | 85.7143 / 86.8571 | 85.7143 / 86.8571 |
| 访问控制/节点 | 77.5385 / 75.4965 | 77.1822 / 74.9714 |


- 新输出：scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/。命令见该 experiments/README.md 顶部；详细报告为 PAPER_KFOLD_REPORT_2026-10-12.md；训练变更文档第13节保存详细记录。
- 旧 REPORT_2026-10-12.md 是正文中已有2602个问号、没有汉字，非显示解码问题；原件及字节副本保留，新报告不猜测恢复旧正文。
- 停止于规定的短检查。未启动60次完整训练、未运行新narrow对照、未扩展状态变量/mapping/反向DDG。作者标签历史、模板复用和主协议同val选模偏差仍需分别报告。


#### 2026-10-12：正式paper_kfold执行层及阶段B通过（修改AI：Codex）

- 新增experiments/formal.py、formal_checks.py、formal_worker.py、resource_probe.py及4个测试文件；只追加README与交接记录。原DDG/HGT/tokenizer/训练代码、prepared数据/标签/划分未改。
- E0=作者HCG/标签+核验的本地512维CodeT5p-770m tokenizer IDs（非完整LLM）；E1仅加正向DATA_DEF_USE。seed1、50epoch上限、patience7/delta0.001、语义共同初始化；不混narrow/nested。
- 新批次scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1/，两类共30配对/60次，不是7类全量。基础HEAD及origin HEAD均70c9d44，只读核验，无pull/自动提交。
- A四任务GPU探针通过。正式E1峰值2.58GiB allocated/2.78GiB reserved；4GiB整卡一度余59MiB，资源余量窄，不自行改模型。
- **B通过**：重入合约fold0，两组best第7轮/停止第14轮。best BF1/MF1均84.6154/86.0577；last E0 92.8571/93.0952、E1 88.8889/89.6057。E1 last多漏simple_dao.sol，下降保留。
- E1训练DDG支持2665边，监督梯度非零；best/last重载logits逐位一致，预测及绑定独立验收通过。仅一折CV validation，非独立测试或全CV。
- 测试：133实验+170DDG+25原项目=328 passed，0失败/跳过；67个既有文件摘要未变，文档仅追加。
- 成功折哈希检查后复用；失败保留并显式--retry-failed重跑整对，**不是epoch续训**。进程存活检查防止重复；实际再调stage-b确认无新增训练。
- **C未启动，剩29配对/58次**。用户确认后formal stage-c --confirm-stage-c；按重入合约→访问控制合约→重入节点→访问控制节点依次验收；不得自动启动。
- 单折明细：experiments/audit/formal_20261012_v1/stage_b_summary.csv；报告FORMAL_EXPERIMENT_REPORT_2026-10-12.md；命令在experiments/README.md末尾，详细变更见training_changes_2026-10-07.md第14节。
- 旧REPORT问号正文未触碰。没有扩展DDG、执行新solc或narrow/nested/多seed/随机边实验。


#### 2026-10-12：阶段 C 已授权并开始，统计旁路完成（修改 AI：Codex）

- 本条是运行中记录，非全量完成声明。用户已授权其余29配对/58次训练，按既定四任务顺序串行。
- 当前HEAD=646e9b3，旧plan=70c9d44；39运行代码和68冻结文件摘要完全相同。原formal因HEAD变化拒绝旧批次，故新建formal_20261012_v1_stage_c，只允许plan提交号/创建时间不同，未放宽校验或修改旧产物。
- 旧重入合约fold0完整复制，receipt与完整fold双验收通过，state记import_provenance；未重训、未挑分数。
- 新批次scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c/；当前fold1首次attempt运行中。不要重复启动控制器。
- 主日志audit/stage_c_20261012_v1/stage_c_controller.log；执行状态execution.json、绑定迁移migration.json。旧批次保持不变。
- 新只读统计脚本在audit/stage_c_20261012_v1/analysis/，不参与训练摘要扫描。26项新测试通过并独立复查；按任务/best/last统计四指标、成对差值std、升平降、错误转移、支持/参数/显存/耗时与attempt历史。未完整任务只列pending。
- 原DDG/HGT/tokenizer/标签/折/初始化/学习率/早停/best规则均未改；nested/narrow/多seed不在本轮范围。
- 观察到显存余量窄、训练耗时较长和WSL实时时钟回拨；精确fit时间用perf_counter，mtime不能用于精确耗时。只读strace因权限限制未取内部栈，未更改系统配置。
- 本段时无训练失败/重试；E0 fold1已18轮早停、E1进行中。完成后必须追加真实最终结果，不把运行中状态当验收通过。
- 详细变更见training_changes_2026-10-07.md第15节；前13/14节及旧交接正文保留。


#### 2026-10-13：阶段 C 四任务全部完成并验收（修改 AI：Codex）

本条接续此前“阶段C运行中”历史记录，当前状态已完成；保留前文不改写。

- paper_kfold四任务按重入合约5→访问控制合约5→重入节点10→访问控制节点10全部完成；
  30配对折、60次拟合，其中本轮58次新训练、旧重入合约fold0的2次原样复用。
  全部attempt_001，0拟合失败、0重试；控制器及最终formal verify退出码0，
  120个best/last checkpoint完整。控制器monotonic耗时8490.03秒。
- 版本迁移只改新plan的base_git_head/created_utc；39项运行代码、68项冻结文件摘要相同。
  新HEAD=646e9b3、旧HEAD=70c9d44，旧批次保留；fold0复制字节一致且双重验收，不为挑成绩重训。
- E0=作者固定HCG/标签+本地核验512维CodeT5p-770m tokenizer IDs，E1同图只加正向DATA_DEF_USE；
  DDG/HGT/tokenizer/标签/折/初始化/学习率/早停/best规则均未改变。
- 以下为**最低val loss对应best的CV validation等权折均值**，不是独立测试；
  节点任务是HCG节点指标，不是去重源码行F1。完整四指标±sample std及逐折数见最终报告。

| 任务 | E0 best BF1/MF1 | E1 best BF1/MF1 | BF1/MF1差值（百分点） |
|---|---|---|---|
| 重入/合约 | 94.1593/94.3452 | 93.5157/93.6245 | -0.6437/-0.7207 |
| 访问控制/合约 | 93.5590/93.8316 | 93.5590/93.8316 | 0.0000/0.0000 |
| 重入/节点 | 96.0580/96.0088 | 96.0740/96.0107 | 0.0161/0.0019 |
| 访问控制/节点 | 95.9723/96.8764 | 95.8130/96.7384 | -0.1593/-0.1380 |

- 重入节点best微增0.0161百分点，Buggy-F1为4升/1平/5降，尚无稳定提升证据。
  重入节点fold8低分保留；buggy_18.sol有250个best FP，说明错误集中位置，不能据此认定标签错误。
  last辅助BF1差值依次为-1.9505、-2.1152、-0.2497、-0.5698百分点，没有改用last作为主结果。
- DDG有训练支持且监督梯度非零；训练未见但已注册的关系保留，无支持的关系零梯度正常。
  E1增加参数及关系聚合结构，不能把所有变化单独归因于DDG语义。
- 新增代码仅analysis/report_stage_c.py与26项统计测试，全部通过，无GPU/模型导入；
  上轮328项测试是历史记录，本轮未冒充重跑。独立四任务预测/统计复核及最终冻结审计均通过。
- 新批次artifacts/paper_kfold/formal_20261012_v1_stage_c/；
  主日志audit/stage_c_20261012_v1/stage_c_controller.log；
  最终报告analysis/reports/final_v1/REPORT.md及6份CSV/report.json。
  详细变更、完整best/last四指标、资源/错误分析在training_changes_2026-10-07.md第15.7–15.13。
- 旧plan HEAD保护拒绝与strace OS权限拒绝分别是预检/诊断问题，不是训练失败。
  曾有资源竞争、低显存余量及WSL时钟回拨；耗时含验证/保存重载，用perf_counter；
  不把个别慢fold的E1/E0时间比解释为纯DDG开销。
- 所有主成绩CV validation；单seed、作者标签历史、模板重复和同val选模偏差限制保留。
  本轮至此停止，没有启动nested/narrow、多seed或DDG状态变量/mapping/反向边扩展；
  当前仍是函数内标量MVP，不是完整Solidity DDG。


## Completed Stage C archive and Git commits (2026-10-13)

The completed run is
`scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c`.
All 30 paired folds (60 fits) passed. Its sealed training base remains
`646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc`; do not rewrite the plan or seal
to match an archival commit.

The original `formal verify` and training commands intentionally require exact
HEAD equality. They are not the post-commit archive verification interface.
After committing results, verify the completed archive with the existing
read-only reporter (choose a fresh output directory on every invocation):

~~~bash
python -B scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/report_stage_c.py \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c \
  --output /tmp/ge-sc-llm-stage-c-archive-check-UNIQUE
~~~

Require `complete_tasks: 4` and `pending_tasks: 0`. The reporter checks the
plan seal, frozen inputs/code, receipt and artifact hashes, and recomputes
prediction metrics. It neither trains nor modifies the sealed run.
The archive commit must descend from the training base; check with
`git merge-base --is-ancestor 646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc HEAD`.

GitHub stores the code, documentation, text run artifacts, receipts and reports.
Model weights (.pt), prepared graph/data assets, process markers, locks and
temporary test directories stay local. A fresh clone alone cannot perform
full artifact verification without those local assets. This is a code/results
archive, not a replacement for a full experiment backup.
