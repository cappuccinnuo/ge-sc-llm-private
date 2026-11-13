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


## DDG diagnostics archive (2026-10-13)

New diagnostic code and results are under
`scripts/DFG/experiments/audit/ddg_diagnostics_v1`.
This is frozen-checkpoint analysis, not a new training run.
Historical input_audit/final_drift records describe the completed diagnostic
session at its original HEAD; do not rewrite them after an archive commit.

Post-commit read-only diagnostic verification (requires local raw assets):
~~~bash
python -B -m scripts.DFG.experiments.audit.ddg_diagnostics_v1.aggregate_results \
  --pilot-output pilot_v2 --remaining-output remaining --validate-only
~~~
The completed training archive is verified separately by the Stage C reporter
documented above. Neither command requires rewriting the training plan.

The four large raw observation categories (message_norms.csv,
zero_message_norms.csv, rewiring_audit.json, representation_changes.csv) remain
local at every directory level. Their paths, sizes and SHA-256 digests are in
`docs/ddg_diagnostics_v1_local_assets.json`. GitHub contains scripts, reports,
predictions and other text evidence. A fresh clone lacks the raw observations,
weights and graph inputs needed for full verification.


#### 2026-10-13：DDG 诊断补记与 v1.1 正确性修复完成（修改 AI：Codex）

本条接续原封存实验及诊断归档记录，不改写此前结果。详细修改、原因、验证及限制见
docs/training_changes_2026-10-07.md 第16、17节。

- 上一轮冻结权重诊断已经完成：97项测试通过；30个配对折best及7个试点initial/last。
  DDG消息置零使四任务分类翻转分别为1、0、13、1，说明DDG确实参与计算，
  但不能据此推断已获得稳定净收益。重复片段及标注上下文、标量范围和图信息冗余均需区分。
  旧诊断目录、历史input_audit/final_drift与归档数据保留，未为当前HEAD改写。
- 本轮从359a7f1创建隔离工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11，
  修改只位于该工作树的 scripts/DFG/projection.py、semantic_cfg.py、__init__.py，
  新增定向测试及审计代码。原业务源码未升级；没有提交、推送或覆盖原图/权重/plan/seal。
  原仓库仅追加本交接文档与training_changes，旧正文的字节前缀保留。
- v1.1修复DOT源码序列化精确比较，以及if/else直接子节点comment误选为body。
  保留严格AST身份、分支、GEN/KILL及回退；额外拒绝序列化物理多行字符串歧义。
  没有更改HGT、tokenizer、标签、训练配置或标量DDG支持范围。
- 修复后的四套图独立保存为E2，旧E0/E1仍封存：

| 任务 | 原E1 DDG边 | E2 DDG边 | 恢复边 | 新canonical |
|---|---:|---:|---:|---:|
| 重入/合约 | 3363 | 3561 | 198 | 0 |
| 重入/节点 | 1711 | 1894 | 183 | 2 |
| 访问控制/合约 | 3765 | 4032 | 267 | 0 |
| 访问控制/节点 | 2632 | 2836 | 204 | 1 |

- 原节点、ID、类型、标签、token、源码映射及CFG/CG多重边完全不变；
  旧DDG端点、canonical及语义事实全部保留。投影回退恢复与新增语义事实分开统计。
  两个clean函数因注释修复恢复，节点任务主要为原事实恢复投影；未把恢复边数写成F1提升。
- D2核验12案例、480个train重复来源：447个完整函数精确回映，33个明确因多pragma未回映；
  918项源码字节跨度核验和121项原输入SHA核验通过，标签、预测与图身份明确绑定。
  R buggy_18节点2706作者为负、公共CSV覆盖、37个训练同文本为正，仍不能唯一确定作者规则。
  AC owner_txorigin部分是参数且已有DDG；纯算术误判也已有DDG，不能全归因于缺状态依赖。
  mapping_write的map是数组；权限guard→敏感操作属于控制依赖，不冒充Def–Use。
- D3仅交付状态位置、读写事件、别名、入口未知、调用HAVOC、强弱更新及投影接口设计。
  9个真实函数候选Oracle与5个合成规格已写明；独立人工批准与solc编译验证均为0。
  入口读余额→调用→清零可能没有具体函数内state Def–Use，应先核验表达价值，
  再决定状态/控制/访问顺序等独立关系。没有实施状态模块或开始E2/E3训练。
- 本轮累计399个不同测试通过。首次18个环境/绝对资源路径失败日志保留；
  使用原已有语法库SHA一致副本，原绝对路径测试在原目录执行，未放宽断言。
  原正式归档只读reporter核验四任务完成/零待办。6217项原资产及新增文件检查、
  两文档授权追加记录见新目录protected_before/after及documentation_update。
- 新目录（在隔离工作树内）：
  scripts/DFG/experiments/audit/ddg_v11_correctness/。
  README为入口；D1_FIX_REPORT与覆盖CSV、D2_CONTEXT_REVIEW/CASE_AUDIT、
  D3_STATE_AWARE_DDG_DESIGN/ORACLE_SPEC/IMPLEMENTATION_PLAN均已交付。
  新图在after/reentrancy_author/与after/access_control_author/的E2_contract/E2_node.gpickle。
- 当前仍有未支持语义回退、标签历史不明、独立人工Oracle未批准、无编译验证等限制；
  新节点canonical也可能增加参数。后续先验收小型状态原型与真实投影信息，再另建训练计划。
  本轮停止于正确性修复、审计与设计，不宣称完整Solidity DDG或检测性能提升。


### Git archive follow-up (2026-10-13)

The v1.1 correctness fixes and audit are now saved on the separate branch
`ddg-v1.1-correctness` in the private GitHub repository. The main branch keeps
the frozen original training code and only receives documentation updates.
Earlier statements saying "not committed/pushed" describe the state at delivery.
Use the v1.1 worktree for the new code and the original main worktree for frozen
experiment verification. Do not merge the fixes into a frozen batch or rewrite
its plan/seal. E2 graph binaries remain local; their provenance hashes are
recorded in the v1.1 audit.


#### 2026-10-14：Stage E 状态 DDG 原型与真实样本审计（修改 AI：Codex）

本条接续v1.1/D3设计及Git归档说明。详细修改与原因见docs/training_changes_2026-10-07.md第18节。

- 实际新代码在隔离工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11 的 scripts/DFG/state/，原工作树的DDG/HGT/tokenizer/训练器不修改。新审计入口为隔离工作树 scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/README.md。
- 本轮实现独立StateFunctionIR、声明/作用域状态位置、简单mapping键、READ/WRITE/RMW、ENTRY_UNKNOWN/HAVOC、强弱更新、分支/循环到达定义及v1.1精确投影。分析器不接收漏洞标签/预测，不按样本名定制；不增加模型节点。
- 本轮仅重入3个、访问控制4个困难文件。315函数中63完成子集分析、252回退；真实STATE_DEF_USE事实和新增模型边均0。四个E3a_selected候选图与E2字节SHA相同，无新增两层上下文。不能把候选称为全语料E3完成版。
- 零增量来自可分析样本入口读→调用→更新模式及继承/版本/modifier等覆盖限制；204个回退与继承绑定有关，不能证明状态DDG无用。32条状态访问顺序、15条外部调用到写入和15条未确认调用到写入仅留侧表，未混作数据边。
- 原9个真实Oracle+原5个合成+新增6个通用规格共20个：13子集分析、7预期回退；合成产生17事实（16EXACT/1MAY）、15物化边。独立人工批准0、编译验证0；解析通过不等于Solidity认证。
- 本版拒绝所有继承/导入；modifier、数组、嵌套mapping、storage引用、跨函数/跨交易等未支持。键不确定不强KILL，调用TOP较保守，CFG witness不证明路径谓词可满足。不得声称完整Solidity DDG。
- 原加载器会反射新STATE_DEF_USE；本轮只新增显式model_adapter，合成HGT已验证正向canonical读取及非零梯度。旧formal训练入口尚未迁移，不能直接拿旧命令跑候选图。
- 新状态测试56项通过，连同既有DDG/实验/项目回归共436个不同测试通过，0失败/0跳过。绝对资源测试在原目录单独运行。复审补emit参数重复遍历及未知事件kind保护，保留2项修复前失败证据及所有旧attempt。
- 最终审计使用results_attempt_002；attempt_001保留。原训练归档只读复核4任务complete/0pending，首次输出目录已存在的拒绝记录也保留。旧资产保护与四文档追加见protected_before/after、documentation_update。
- 未下载solc、未升级依赖、未提交/推送、未训练E2/E3、未跑其他五类，无新增F1。下一步先核验Oracle、解决有证据的覆盖瓶颈或独立访问/调用顺序语义，再决定是否具备进入正式训练的条件。

- Stage E资产核验补充：扩大扫描发现203个未纳入起始SHA清单的旧smoke路径，首次requires_review记录保留；不能以“未列入清单”认定是新增。最终protected_after_verified.json按已完整建立基线的formal/旧审计目录核验，清单外文件明确保留前后比较覆盖限制。


### Stage E Git archive follow-up (2026-10-14)

Stage E source, tests and text audit records are saved on
`ddg-v1.1-correctness`; main receives documentation only.
Earlier "not committed/pushed" statements describe the pre-archive delivery.
Generated E3a_selected graph binaries remain local with their recorded manifest
hashes. No training plan or historical seal is rewritten. Frozen training
verification remains in the original main worktree using the read-only reporter.


#### 2026-10-14：Stage F 全语料覆盖恢复与状态顺序候选（修改 AI：Codex）

接续Stage E归档，详细新增文件、原因、失败证据及命令见
docs/training_changes_2026-10-07.md 第19节。

- 实际新代码在开发工作树 ge-sc-llm-ddg-v11/scripts/DFG/state/stage_f/；
  报告入口 scripts/DFG/experiments/audit/state_aware_ddg_stage_f/README.md。
  原工作树只追加文档，旧scalar/Stage E/HGT/tokenizer/训练器及E0/E1/E2/标签/折均未修改。
- 完成两类全部冻结源码盘点：256路径/254源码SHA，合约142+114，节点71+57为子集。
  Stage E全语料原有22条EXACT事实，不能用此前7困难文件零增量代表全体。
- 受限同单元单继承链、可见性及多pragma交集恢复重入274、访问控制360函数；
  合约支持1042→1316、939→1299。27/16源码使用来源SHA一致的已有版本记录，
  没有任意选择或执行solc；多继承、modifier、数组等仍回退。
- 复审发现用户revert()解析为revert_statement时状态层遗漏HAVOC；
  新回归先1 failed，再仅修Stage F适配器后通过。Stage E冻结源码保留。
  首次比较遗漏121个前后均前端失败的函数行，已补齐6552身份，图样本一直保留。
- 接受F0_attempt_001、F1_attempt_002、F3_attempt_002，旧attempt及失败日志保留。
  新增8张独立候选图，不覆盖E2。E3a加状态Def–Use；E3b另加状态访问/调用写入顺序：

| 任务 | E3a状态边 | E3b另加访问顺序/调用→写入 | E3b新增两层节点对 |
|---|---:|---:|---:|
| 重入/合约 | 6 | 847/547 | 1546 |
| 重入/节点 | 3 | 829/547 | 1545 |
| 访问控制/合约 | 11 | 33/0 | 17 |
| 访问控制/节点 | 4 | 16/0 | 1 |

- 原节点/属性/标签/token/基础关系均保留，off等于E2，DGL不反射新关系；
  每条边可追溯源事件。语义事实→投影证据→去重边分别记录，缺emit等锚点不猜行号。
- 原7困难文件仍63/315函数支持，状态EXACT事实仍0；buggy_18宽版本/继承等限制没有消失。
  UNKNOWN调用及READ→CALL→WRITE复合模式仅侧表；结构可达不是路径可行/漏洞证明。
  权限guard/modifier的控制依赖另行验证，不冒充状态DDG。
- 20旧Oracle重查13支持/7回退；新增45项Stage F测试。完整回归481个不同测试通过，
  0失败/0跳过；旧资源绝对路径测试在原工作树单独运行。独立人工批准0、solc验证0。
- 原HGTLayer合成CPU图新关系梯度非零、输入绑定/重载输出一致、共同初始化等价；
  无优化器。F4_initial_synthetic.pt为未训练夹具状态，不是best/last。
  原正式入口尚未迁移，实际配对GPU峰值未测，不能拿旧训练命令直接跑候选。
- 13,579项起始资产完整保护及四文档字节前缀检查见protected_after.json。
  未提交推送、未改seal、未训练或产生新F1。先独立核验Oracle与候选语义、
  再迁移新入口并测真实图资源，之后才决定小折受控验证，不自动跑完整K折。


### Stage F Git archive follow-up (2026-10-14)

Stage F implementation and text audit evidence are saved on
`ddg-v1.1-correctness`; main receives only documentation.
Earlier delivery statements about no commit/push are historical.
Candidate graph binaries, pickle caches and synthetic checkpoint assets stay
local. Keep old plan/seal and frozen training code unchanged.
After archival commits, validate the new delivery in the development worktree:
~~~bash
python -B scripts/DFG/experiments/audit/state_aware_ddg_stage_f/verify_delivery.py --validate-only
~~~
Use the original main worktree's read-only Stage C reporter for old training
results. Neither command trains models; both require the relevant local assets.

#### 2026-10-14：Stage G 接入与短检查通过，正式单折进行中（修改 AI：Codex）

- 接续Stage F；新代码只在开发工作树ge-sc-llm-ddg-v11/scripts/DFG/experiments/e23_pilot/。原HGT/tokenizer/DDG算法、标签、图、折、原训练代码不变。详细变更见training_changes第20节。
- E2=v1.1标量DDG；E3a再加状态Def–Use；E3b再加状态访问/调用写入顺序。全部来自冻结D1/F3图，未重新构图或覆盖旧图。
- 有限审核20 Oracle、17状态边和16抽样顺序边，无已确认新阻断；独立人工批准/solc验证仍0。17状态边12在构造器、5在定价函数；AC fold0 val无STATE边，不能忽略覆盖限制。
- 新adapter继承原forward/HGT，原训练/保存函数code object复用，仅扩展关系与绑定处理。CPU三变体初值链E2→E3a→E3b共享语义参数相同；真实E2四任务与原分类器前向逐位一致。
- 591个不同测试通过；旧30配对折归档只读验收通过。新12次三轮smoke全部成功、0重试，50步调度不缩短，新增关系有实际训练梯度，best/last重载一致。
- GPU串行最高smoke allocated/reserved约2.646/2.811GiB，整卡曾仅余17MiB；用户确认关闭或没有其他GPU程序。发生OOM停止，不改参数或CPU回退。
- 新输出artifacts/paper_kfold/e23_pilot_v1/。本条时正式12次fold0刚开始，尚不能称全部完成；最终结果另追加。paper_kfold同val选模/评分，CV validation；节点仍HCG节点口径。
- 严格best最低val loss，last另报；失败保留、显式重试，成功哈希复用；互斥锁防重复控制器。没有自动启动剩余78次、nested/narrow/新模块。
- HGT跨关系mean本身可能改变表示，不能将全部E3差值视为依赖语义贡献；覆盖旁表coverage_note记录直接目标与val文件。完整K折和机制对照另行决定。


#### 2026-10-14：Stage G 正式12次fold0已完成并验收（修改 AI：Codex）

- 本条接续前一条“进行中”记录；正式控制器返回0，12次smoke+12次full均attempt_001完成，0失败/重试/OOM。只运行固定fold0，未启动其余78次。
- 新入口/报告在开发工作树ge-sc-llm-ddg-v11/scripts/DFG/experiments/e23_pilot/；新产物artifacts/paper_kfold/e23_pilot_v1/。详细变更和最终验收见training_changes第20.7–20.10节、IMPLEMENTATION_REPORT.md。
- 主结果严格best最低val loss，CV validation，节点按HCG节点评分；没有改DDG/HGT/tokenizer/标签/折/初始化公式/训练数值规则。

| 任务 | E2 BF/MF | E3a BF/MF | E3b BF/MF |
|---|---:|---:|---:|
| 重入合约 | 88.8889 / 89.6057 | 88.8889 / 89.6057 | 88.8889 / 89.6057 |
| 访问控制合约 | 90.0000 / 91.1538 | 90.0000 / 91.1538 | 90.0000 / 91.1538 |
| 重入节点 | 99.7071 / 99.5997 | 99.6487 / 99.5195 | 99.6491 / 99.5191 |
| 访问控制节点 | 99.2883 / 99.3306 | 99.4652 / 99.4979 | 99.4652 / 99.4979 |

- 合约级预测不变；重入E3b对E2修复1但新增2个节点错误；访问控制增强仅纠正mapping_write.sol:12964一个误报。AC val无STATE_DEF_USE，不能把该单点变化归因于验证节点新增状态依赖。
- last独立汇总，AC节点E2/E3a/E3b Buggy-F1为99.4652/98.5866/96.7185，未替换主best。不是稳定明显提升，也不是状态依赖无效的证明。
- 591个不同测试全通过；四任务新旧E2 CPU前向一致；所有checkpoint重载一致。独立指标/180正式产物SHA验收通过；12对smoke/full未训练初值及前三轮完整历史一致。
- 13710项旧资产验收通过，13706完全未变、4授权文档只追加；6个旧完整目录无增删、HEAD不变。文档phase2另核验原前缀。无提交推送。
- STATE边仍极少且主要构造器/定价；HGT跨关系mean存在结构影响，单fold/同val选模/节点天花板限制结论。独立人工批准0、solc验证0，不是完整语义认证。
- 当前封存计划只含12次；其余78次需下一批独立计划/初始化/逐折支持与资源核验，不能改旧seal或直接把现有run说成全K折入口。本轮到此停止。


### Stage G Git archive follow-up (2026-10-14)

Stage G code and text results are archived on ddg-v1.1-correctness; main
receives documentation only. Earlier no-commit statements describe delivery
before archival. Original plan/seal and runtime source remain unchanged.

After a Git commit, the original pilot control verify/summarize commands still
require the exact training HEAD. For completed archives, run in the development
worktree instead:
~~~bash
python -B -m scripts.verify_e23_archive
~~~
This read-only verifier requires descendant Git history, unchanged runtime and
frozen input hashes, and all 12 smoke plus 12 full successful receipts. It reuses
the original per-fit integrity and metric checks, without bypassing training
guards or loading a training worker. Weights, initial states, graph binaries and
process markers stay local; a fresh clone alone cannot run full verification.
Use the original main worktree's Stage C reporter for the old training archive.

#### 2026-10-14：Stage H1 独立全折计划与接入（修改 AI：Codex）

- 新代码仅开发工作树 scripts/DFG/experiments/e23_cv/，新输出 artifacts/paper_kfold/stage_h1_v1/；原e23_pilot及其plan/seal、DDG/HGT/tokenizer/图/标签/折/训练数值规则不改。详细记录见training_changes第21节。
- 本地/GitHub HEAD44e7337一致，Stage G的75份运行源码与旧封存完全一致；归档后通过旧收据与初值核验有记录复用fold0，不改旧seal。
- H1=E2/E3b各30折结果，8个Stage G fold0复用、52次新拟合；CPU准备全部fresh E2→E3a→E3b链，E3a26份未训练初值为H2保留。H2只存固定计划，不自动训练。
- 原seed1及每折派生公式、50轮、patience7/delta0.001、严格最低val loss的best、last另报；主结果CV validation，节点按HCG节点口径。
- 新控制器串行单GPU、双锁、失败停止/保留attempt/显式重试；原fit函数直接复用，不缩图/换参数/CPU回退。
- 训练前607个不同测试通过，0失败/跳过。旧E0/E1另作同折历史基线，初始化版本不同，不混称本批共同初始化对照。
- 本条写入时CPU准备与复用核验进行中，52次正式拟合尚未启动；最终完成/失败/结果另补。起始保护14253旧文件，训练期间不改封存源码。

## 2026-10-14 Stage H1 全折完成与结果（Codex）

接续本日H1准备记录。开发工作树ge-sc-llm-ddg-v11，HEAD保持44e7337；原工作树HEAD保持7fce3dd。52次新拟合+8个Stage G fold0复用=60个正式结果全部通过验收，均attempt_001，无失败/重试/OOM。未改变DDG/state、HGT、tokenizer、图/标签/折、初始化或训练数值；607个不同测试通过。H2未执行，26次E3a新拟合只保留固定计划和初值。

Best的CV validation等权均值BF1/MF1：
- 重入合约：E2=E3b 95.0140/95.0549，5折全持平。
- 访问控制合约：E2=E3b 91.5628/92.0657，5折全持平。
- 重入节点：96.0772/95.9052→96.2460/96.0506；BF1 +0.1688pp，6升/1平/3降。
- 访问控制节点：96.1983/96.9983→96.3495/97.1228；BF1 +0.1512pp，4升/4平/2降。

节点best分别净少14/10错误，主要仍是概率变化；buggy_18.sol在两类任务的275/94错误未改善。1091个有train支持的增强canonical记录均有非零梯度，29个无支持者单列；接入有效不等于普遍语义收益。访问控制节点last平均BF1反而下降1.3058pp。原E0/E1基线已比较，但跨批初始化不同，仅历史参考；访问控制合约本批低于旧E0/E1，不能宣称所有任务提升。

产物：开发树scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/，重点查看H1_RESULT_REPORT.md、summary.csv、paired_statistics.csv、file_error_analysis.csv、baseline_statistics.csv、gradient_support_detail.csv、resource_folds.csv、H2_EXECUTION_PLAN.md。详细过程已追加training_changes_2026-10-07第21.7–21.12。只读分析/报告/保护校验脚本也位于新产物目录，原文档仅追加，旧资产核验见protected_after.json。

控制器耗时约2.93小时；首个新增fit受Windows显存竞争影响，最低free14MiB，保留实际耗时，不能做公平速度结论。没有重启该fit、改参数或代关用户程序。H1已停止；建议审查有限收益与困难案例后决定完整H2消融，本轮不自动执行H2/更多seed/七类扩展。修改与分析AI：Codex。


### Stage H1 Git archive follow-up (2026-10-15)

H1 code and text results are saved on ddg-v1.1-correctness; main receives
documentation only. Historical delivery HEADs remain provenance, not the current
archive HEAD. Do not rewrite H1, H2 or Stage G plans/seals after Git commits.

In the development worktree, verify the completed H1 archive after a commit:
~~~bash
python -B -m scripts.verify_h1_archive
~~~
Expected: 52 new fits, 8 Stage G reused fits, 60 complete.
This read-only entry checks descendant Git history, sealed runtime/input hashes,
the reserved unauthorized H2 plan and original per-fit receipt/metric checks.
The original H1 training controller still requires its exact training HEAD.
H2 is not executed. For Stage G use scripts.verify_e23_archive; for the older
training results use the Stage C reporter in the original main worktree.

Weights, initial states, graphs and process markers remain local; full validation
requires these local assets and cannot be performed from a fresh clone alone.


## 2026-10-15 Stage H2 接入与启动（Codex）

用户已授权补齐26次E3a正式训练，复用4个Stage G fold0；不训练E2/E3b，不扩七类/新seed。新增scripts/DFG/experiments/e23_h2/旁路调度、初值验证、三变体汇总和必要测试，直接复用原模型/fit/checkpoint。H1旧计划与seal、预留h2_plan的execution_authorized=false均保持原样。

开发HEAD cef8fb9；H1专用只读归档核验确认82份运行源码、684项旧资产及60个H1模型一致。30份E3a初值、四个G fold0通过验证；独立H2封存89份运行源码/1525项资产。71项必要测试通过，0失败/跳过，4条既有DGL警告。旧G初值格式按原manifest绑定，不重建初值。

配置澄清：合约lr=.0005/max_lr=.01/weight_decay=5e-6；节点lr=.0002/max_lr=.005/weight_decay=0。旧H1报告的通用段落过于简略，H2沿用真实逐任务manifest，不改变训练。评分仍CV validation、HCG节点口径。

产物stage_h2_v1，实时controller.log与逐折attempt_001.log。正式26次已启动，完成结果另补；不预报收益。详细记录见training_changes_2026-10-07第22节。修改与分析AI：Codex。


## 2026-10-15 Stage H2 全折完成与三变体消融（Codex）

开发树ge-sc-llm-ddg-v11，HEAD保持cef8fb9。26次新E3a均attempt_001，0失败/重试/OOM；复用4个Stage G fold0，共30个E3a，与H1的E2/E3b合计90个正式结果。没有重训E2/E3b，没有修改DDG/HGT/tokenizer/标签/fold/初值/训练规则。71项必要测试通过，最终verify与独立汇总通过。原H1/G计划seal及预留H2 execution_authorized=false不变；新增H2独立授权计划。

Best的CV validation等权均值BF1/MF1：
- 重入合约：E2=E3a=E3b 95.0140/95.0549。
- 访问控制合约：E2=E3a=E3b 91.5628/92.0657。
- 重入节点：E2 96.0772/95.9052，E3a 96.0388/95.8613，E3b 96.2460/96.0506。
- 访问控制节点：E2 96.1983/96.9983，E3a 96.2631/97.0592，E3b 96.3495/97.1228。

E3a−E2节点BF1为−0.0384pp/+0.0648pp，E3b−E3a为+0.2072pp/+0.0865pp；重入的主要小幅收益出现在顺序关系增量，不能归因于单独状态Def–Use。访问控制没有调用→写入边。合约best类别不变，仅概率变化。两类buggy_18.sol及重入buggy_36.sol、访问控制buggy_26.sol的best错误均未改善。last方向不完全一致，访问控制节点E3b−E3a last BF1为−1.3236pp；不得据此换best规则。

新fit耗时合计4296.9452s，控制器5521.9853s；新fit最低free54MiB，无OOM/降配。1605项增强canonical梯度中1564项有train支持且非零有限，41项无train支持单列，非有限0。STATE_DEF_USE在节点图仅3/4条、val大多无支持，有限覆盖不等于完整状态依赖。单seed、同val选模评分、HCG节点口径，不是独立测试；历史E0/E1初始化不同仅作参考。

交付：scripts/DFG/experiments/artifacts/paper_kfold/stage_h2_v1/的H2_RESULT_REPORT.md、E2_E3_COMPLETE_ABLATION_REPORT.md、逐折best/last和三组差值、OOF/逐文件错误、关系/梯度/资源及plan/seal/收据。新增调度源码在e23_h2/。详细过程已追加training_changes_2026-10-07第22.5–22.10。只读校验：python -B -m scripts.DFG.experiments.e23_h2.control verify（现有mando环境、当前HEAD）；后续归档不要改旧seal。

本轮已完成并停止，不自动扩类别/seed/关系/模型。后续最有依据的是有限的顺序关系机制解释，仍需独立可靠性证据；不是已经证明七类普遍获益。修改、执行与分析AI：Codex。


### Stage H2 Git archive follow-up (2026-10-15)

H2 source and text results are archived on ddg-v1.1-correctness; main receives
matching documentation. Earlier recorded HEADs remain historical provenance.
Do not rewrite H2/H1/G plans or seals to match an archive commit.

In the development worktree, use these read-only post-commit commands:
~~~bash
python -B -m scripts.verify_h2_archive
python -B -m scripts.verify_h1_archive
~~~
Expected complete populations: H2 = 26 new + 4 reused; H1 = 52 new + 8 reused.
The H2 archive verifier retains policy, ancestry, runtime/input hash, job matrix,
reserved-plan and original per-fit receipt checks without executing training.
Original execution commands retain their exact-HEAD guard.
Weights, initial states, graph binaries and process markers stay local.
A fresh clone lacks the local assets needed for complete verification.


## 2026-10-19 Stage I 能力清单与状态消息诊断接入（Codex）

开发树ge-sc-llm-ddg-v11，HEAD 021a6f55。已新增stage_i_diagnostics旁路能力/入口文档、显式入口检查、静态证据链及固定checkpoint消息屏蔽；原DDG/state、HGT、tokenizer、图、标签、训练和旧seal不变。当前E2/E3a/E3b编号与原宏观设计编号已明确区分。状态图应走Stage F/e23_pilot；新校验须显式调用，不会拦截直接运行的旧脚本。受限modifier仍是后续候选，当前函数回退保留原图。

静态证据显示节点STATE_DEF_USE仅重入3/访问控制4条，全部构造器；重入96.13%的E2节点错误在新增边局部影响域外，访问控制域内37节点原本均正确。继承是更大的已记录回退桶，不能直接假定先做modifier能解决主要错误。静态表在stage_i_v1/static，Stage F sidecar仅本轮观察封存，不能伪称受H2 seal认证。

126项联合测试通过（4条既有DGL警告）。H1/H2归档核验通过；v1/v2预执行计划和接口错误记录保留，v3进行60模型best/last的固定权重全折诊断。四任务fold0已通过，剩余执行中；没有新增正式训练。后处理角色问题以产物目录独立修正版处理，不改封存推理。最终结果另补。详细过程见training_changes_2026-10-07第23节。修改与分析AI：Codex。


### 2026-10-19 Stage I 第1、2步完成：状态消息诊断（Codex）

- 已完成能力/版本编号/入口约束清单，以及60个E3a/E3b模型、120份best/last checkpoint、720条件的只读诊断；新增训练0。实现位于开发树scripts/DFG/experiments/stage_i_diagnostics，主报告位于artifacts/paper_kfold/stage_i_v3/STAGE_I_RESULT_REPORT.md。
- 正常输出与历史概率全相同；图、标签、特征、参数、schema及聚合分母保持。1,020项状态canonical-layer消息正常均非零，说明确实进入HGT。
- E3b best屏蔽全部状态消息：两个合约任务与访问控制节点均0类别变化；重入节点1331概率变化、仅1新增漏报，等权BF1−0.011342pp。不是新训练消融结果。
- 状态DU在节点任务仅3/4条且都在构造器；重入96.13%的E2错误处于新增关系潜在影响域外，访问控制全部E2错误在域外。困难文件干预后仍无类别变化。支持“覆盖与主要错误重合少”，不支持“所有DDG无用”或“已证明泛化”。
- case_review.md给出构造器补偿、顺序联合效应、buggy_42直接目标正向案例；单关系和联合屏蔽不可相加。last单独保留，不改变best规则。
- 162项测试通过；120 checkpoint输入/恢复验收、H1 60与H2 30历史归档复核通过。旧summarize评分角色错误保留，使用README中的独立后处理脚本；旧seal和数据不改。
- 受限modifier尚未实现：初稿未展开，后续接入分析提出适配/回退；当前仍函数级回退。候选是先支持唯一绑定、明确参数与单一占位符执行顺序的子集，不能按onlyOwner名字猜，也不等同控制依赖。
- 详细修改/资源/限制见training_changes第23节、STAGE_I_RESULT_REPORT.md及protected_after.json。原工作树用户auto_version_solc.py改动保留。修改与分析AI：Codex；完成本轮后停止，未启动新训练/关系扩展。


## 2026-10-19 Stage J：DDG整体构图入口与受限覆盖恢复（Codex）

- 已完成源码绑定→语义CFG→标量/状态事实→原HCG精确投影→多关系融合→schema/配置/审计的旁路入口。新增代码在开发树scripts/DFG/state/stage_j/，批量入口experiments/stage_j_coverage/。原DDG/Stage F、HGT、tokenizer、训练器、作者标签和旧实验均不修改。
- 本次新增同源唯一基类/C3多继承及菱形校验、一个无参数且末尾单占位符的前置modifier。只重试原回退函数，原成功分析复用；未知函数无部分事实残留，原样本保留。不支持完整modifier/复杂storage/import/跨函数/控制依赖。
- Stage I文档“modifier尚未实现”是此前快照；现在Stage J仅实现上述受限子集，旧入口默认行为仍不改变。标量DDG范围未扩展，本批冻结E2边保留。四类增强关系保持正向，没有新节点/反向边。
- stage_j_v1/build已生成四任务×frozen/inheritance/modifiers共12图。基线状态关系完全复现旧E3b，基础节点/属性/标签/token/CFG/CG不变。恢复函数：重入合约717、访问控制合约746、重入节点473、访问控制节点517；新增状态关系分别863/70/806/40。
- 新增运行时覆盖不等于性能改善：重入旧E3b 425错误中39进入新边两层范围、6有新上游节点；访问控制196旧错误仍均在范围外。新增节点STATE_DEF_USE各1条仍在构造器。没有新预测/F1，没有新训练。
- 真实例子：onlyOwner中require读取owner→函数体写owner可生成STATE_ACCESS_ORDER，不能声称已实现权限控制依赖。重入buggy_18恢复了部分顺序上下文，buggy_36和访问控制两个困难文件主要错误仍未覆盖。完整证据见opportunity_v2。
- DDG语义/集成377项通过（含新增54），原项目25项通过；H1 60/H2 30历史归档通过。首次pytest收集同名模块问题及后处理混合CSV列问题均记录并修复，旧失败日志保留。未做solc编译，测试解析成功不等于编译通过。
- 文档：state/stage_j/README.md、DESIGN_AND_ACCEPTANCE.md、stage_j_coverage/README.md；结果：artifacts/paper_kfold/stage_j_v1/STAGE_J_RESULT_REPORT.md。详细变更见training_changes第24节。图在build/<task>/<mode>/enhanced.gpickle。
- 旧通用训练加载器不保证状态边方向，不直接套train_node/train_contractlevel；原e23适配可复用但新图需独立计划、schema和初始化绑定。关闭DDG精确复制输入，恢复baseline要传原baseline图。
- 183项原代码/用户文件SHA不变，文档仅追加；原auto_version_solc.py用户修改保留。开发HEAD仍021a6f55，未Git写操作、未自动训练或扩七类。保护/交付清单见同批JSON。实施、审查与分析AI：Codex。


## 2026-10-19 Stage K：版本域修复及整体DDG单折训练完成（Codex）

- 已按用户要求将修复和整体实验直接落地，不为每个小恢复点分别训练。开发树仍ge-sc-llm-ddg-v11/021a6f55；新增核心state/stage_k/，实验入口experiments/stage_k_pilot/，独立批次artifacts/paper_kfold/stage_k_v1。旧DDG/Stage F/J、HGT、tokenizer、标签、原训练脚本和旧seal不改。
- 修复开放pragma导致“无限未来版本无法确认内建调用”的覆盖瓶颈。先原有版本/声明/作用域检查，再与分析器声明的[0.4.0,0.9.0)取交集并记完整证据；不伪造solc版本、不改源码、不要求编译成功。未知绑定/跨作用域版本仍回退，此修复是状态前端旁路。
- 四任务新图已生成；相对Stage J新增重入合约/节点各428边、访问控制各7边。最终相对旧E3b新增1291/77/1234/47边。原nodeID/标签/特征/基础边不变。节点STATE_DEF_USE仍4/5，版本修复主要增加顺序关系。
- 完成两个节点任务原fold0各B0/B1，共4次新正式训练，均attempt_001、0失败/重试/OOM。B0=旧E3b图重新成对初始化，不是无DDG原MANDO或H1旧分数；B1=Stage J整体恢复＋K版本修复。原512维特征、HGT、学习率、早停、best规则和划分不变，结果均CV validation/HCG节点口径。
- best：重入BF1 99.6487→99.5904（−0.0583pp），MF1 99.5195→99.4391；访问控制BF1 99.1119、MF1 99.1635均持平。last访问控制BF1 99.1119→99.2883，但不能取代主best。重入best新增1误报，访问控制best类别完全相同；主要仍是概率变化。
- 重入历史错误的新上下文覆盖6→36；访问控制仍0。本折不包含既有困难文件，不能声称已纠错。访问控制新增状态边都在train，val状态边数未增。87项增强canonical有训练支持且观察到非零有限message梯度；8 checkpoint重载及独立指标复算通过。
- 联合421测试通过、31条既有警告；H1 60/H2 30归档通过。4fit耗时合计648.27秒，最大allocated1761.38MiB，最低整卡free65MiB；未改配置、切CPU或关闭用户程序。未执行solc编译。
- 主要报告STAGE_K_RESULT_REPORT.md，完整结果results.csv，训练支持training_audit.json，逐条修改见两树training_changes第25节。旧197项代码/用户文件SHA不变，文档仅追加；原auto_version_solc.py用户修改保留。
- 当前整体方案已可运行，但单折主结果未显示提升。后续若继续评估，做固定整体B0/B1原10折对照即可，不需要每个小点单独消融；本轮没有自动启动剩余折、七类、更多seed或控制依赖。修改、执行与分析AI：Codex。


## 2026-10-19 原始HCG与整体DDG完整实验接入（Codex）

- 用户已授权下一步，新增开发树scripts/DFG/experiments/overall_cv/，独立产物overall_cv_v1。比较作者原始CFG+CG（HCG）与同图加冻结Stage K整体DDG（HCG_DDG），两个漏洞、合约5折/节点10折，共60次新拟合。
- 旧K基线B0是E3b；旧B1初值以E3b为锚，与新HCG锚定的共同初始化不同，不能仅因同图同fold0就复用。历史结果不覆盖，记录初值摘要对比。两个新分支共用既有训练修复。
- DDG/HGT/tokenizer/标签/原折/有效学习率/早停/best规则均不改。结果为CV validation，节点仍按HCG节点口径；不扩类别/seed/关系或逐小点消融。
- 新增23项测试通过；联合回归727通过、1个历史路径绑定失败，该项在资源报告所属原树通过。保留失败日志，未改旧规则。详细记录见training_changes第26节。
- 本条写入时CPU准备进行中，尚不报训练成绩。随后首个正式配对折验收，再顺序执行四任务；最终结果另补。实施AI：Codex。


### 2026-10-19 整体对照封存与首对完成（Codex）

- overall_cv_v1封存30对初值/60任务、186源码/503资产。四任务HCG原前向与现有模型逐值一致；节点/作者标签/token/原CFG+CG边不变，增强仅加冻结DDG。
- 重入合约fold0两fit完成并验收，best BF1/MF1均84.6154/86.0577；last BF1为92.8571/88.8889，按预定规则不择高替换。4 checkpoint重载一致，增强关系梯度有效，无失败/OOM。
- 已启动剩余58次串行正式训练，当前结果仅是首对，完整四任务结果另补。旧K节点初值摘要与本批不同，不混用；仅复用本批首对。
- 原176项代码/用户文件不变，详细图数量、支持及资源见training_changes第26.6节。修改、执行与分析AI：Codex。


## 2026-10-20 原始HCG与整体DDG完整对照完成（Codex）

- overall_cv_v1已完成60次新正式fit，30配对折，全部attempt_001、0训练失败/重试/OOM。重入及访问控制合约各5折、节点各10折；两分支共同新初值，以原HCG为锚，不混用旧K B1或H1/H2成绩。

| 任务 | 折 | HCG BF1 | HCG_DDG BF1 | ΔBF1(pp) | HCG MF1 | HCG_DDG MF1 | BF1升/平/降 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 重入合约 | 5 | 94.1593 | 94.1593 | +0.0000 | 94.3452 | 94.3452 | 0/5/0 |
| 访问控制合约 | 5 | 93.5590 | 93.5590 | +0.0000 | 93.8316 | 93.8316 | 0/5/0 |
| 重入节点 | 10 | 96.0580 | 96.1027 | +0.0447 | 96.0088 | 96.0441 | 7/1/2 |
| 访问控制节点 | 10 | 95.9723 | 95.8887 | -0.0837 | 96.8764 | 96.8063 | 2/4/4 |

- 主结果全部为CV validation，按最低val loss选best；节点按HCG节点，last及OOF分表。两个合约best类别完全相同。重入节点平均BF1仅+0.0447pp，纠正33/新增34；困难文件buggy_18仍252错误，buggy_36 60→57。访问控制节点best BF1−0.0837pp，纠正2/新增7，buggy_18/26仍87/42错误；两个节点pooled OOF均略降。本批未证实稳定增益。last及完整误差另报。

- 原DDG算法/HGT/tokenizer/作者标签/原折/学习率/早停未改。60历史轮次/配置与120份checkpoint重载验收通过，节点/特征/原基础边不变量通过。状态DU仍很少，访问控制无调用→写入边；不能把概率变化当作分类收益或证明七类泛化。

- 约10小时监控UTC间隔与fit单调耗时不一致，保留timing_gap_observation.json，原因未确定；受影响fit正常完成，无重训或自动降配，不拿该时间作为公平速度基准。

- 新23测试通过；联合727通过+1历史路径失败，该项在原树通过。保护/交付见protected_after.json与delivery_manifest.json，原用户文件保留、文档仅追加。完整详细记录training_changes第26.7–26.10节。

- 入口scripts/DFG/experiments/overall_cv/README.md；产物scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/OVERALL_CV_RESULT_REPORT.md及逐折/误差/关系/资源CSV。此批停止，未自动扩类别、seed、关系或新训练。实施、执行、分析AI：Codex。


## 2026-10-20 合约F1持平专项复核（Codex）

- 用户质疑运行错误后，独立重载两个合约任务全部10对/20个best，在原CUDA重算概率与原导出逐值一致；两组实际图/权重SHA及训练后共同参数均不同。
- 重入142/访问控制114个合约的best概率全部变化，但类别均未跨二分类边界。平均绝对概率变化1.20915/0.73557pp，因此同F1不等于同模型或同输出。
- 10个增强模型的DDG relation_msg在内存置零后，10个logits均改变；恢复state_dict后逐值恢复。该推理诊断不是新训练/正式消融；类别仍不变，当前best决策对该扰动未跨界。
- 首次CPU路径出现3.48e-5概率差超过1e-5容差，保留失败记录；原CUDA复验20个误差均0，未放宽容差。原图、权重文件、DDG/HGT/tokenizer/训练和标签都没改，无新fit。
- 报告与脚本：artifacts/paper_kfold/overall_ddg_recheck_20261020_v1/README.md、recheck.json、probability_examples.csv；详细记录training_changes第27节。主实验仍未证明稳定收益，不调整阈值/择高checkpoint。实施/复核AI：Codex。

## 2026-10-20 下一步设计前的数据与实验复核（Codex）

- 新产物：开发树scripts/DFG/experiments/artifacts/next_step_review_v1/{audit.py,audit.json,NEXT_STEP_DESIGN.md,verify.log}。本轮没有改算法/图/标签/训练，也没有新fit。
- 原control verify再验收60fit/30对、186源码/503冻结资产通过。独立复算120组best/last指标、16组均值/SD、16组pooled OOF均与报告一致；文件划分、身份、配置、初值绑定和选模无漂移。668条有train支持的canonical×fold记录均有正message梯度，17条未见关系保留。
- 新交叉证据：重入HCG428错误中199位于作者/public既有标签分歧，访问控制211中125位于分歧；整体DDG对应仍199/125。重入buggy_18分歧214/计错197；访问控制buggy_18为93/83、buggy_26为42/42。不能直接把这些都归为DDG缺依赖，也不能直接宣布public标签是真值。
- 节点正例文本在训练折重叠率重入99.79%、访问控制99.03%；非完整合约重复率，不单独证明记忆效应。主结果仍CV validation，节点不是去重源码行。
- 下一步先对5个已知分歧类别/文件对象定点语义核验，冻结当前DDG。之后才按无争议案例评估受限guard控制依赖；这属于DDG+控制依赖，尚未实现。若全部数据/配置/共同初值保持，可复用现有基线，仅新增整体候选30fit；改变标签/划分则重新立实验，不能混用。
- 本轮仅设计，不启动新训练或扩七类。首次新审查脚本误计attempt日志已修正并保留失败，正式训练无失败。详见training_changes第28节。执行时间UTC2026-10-20，用户时区2026-10-19；修改与分析AI：Codex。


## 2026-10-20 buggy_18作者标注跨版本核验（Codex）

- 新证据在开发树scripts/DFG/experiments/artifacts/buggy18_hgt_llm_comparison_v1/。HGT六个源码/CSV/JSON文件与提交f791a855字节一致；两类HGT/LLM本地源码相同，HGT标注集合等于CSV注入区间并集。
- 同预处理坐标：重入HGT300行、LLM82行，41条LLM标注越界；访问控制148/46，23条越界。最大840/687分别超过当前源码738/560行槽。
- 同一LLM图端点复放：重入作者35正例对HGT标注249，214节点不同；访问控制17对110，93不同。249/110不是HGT原生Slither图节点数。作者自身端点复放零差异。
- 差异不是近期DDG造成；历史源码/标注版本或转换问题仍待作者生成输入核实。未改正式标签/图/代码，未重训。详见training_changes第29节。审查与记录AI：Codex。


## 2026-10-20 五文件定点标签核验完成（Codex）

- 产物在开发树scripts/DFG/experiments/artifacts/targeted_label_review_v1/，报告TARGETED_LABEL_REVIEW.md；正式图、标签、训练不变。
- 1127节点中1032普通节点AST锚点/正文/端点全对应，95合成节点marker核对；353个分歧与旧审计逐节点一致。三个SolidiFI作者记录有越界/缺失；0x627是外来unchecked_low_level_calls记录挂到changeOwner；parity已有两个公共标注函数节点但作者标签全空。
- 公开CSV也有范围疑点：105区间中7条；按可见注入块边界作旁路候选只改3个节点，不能解释353差异。访问控制buggy_18的普通allowed声明被区间覆盖。未采用候选为正式真值。
- 32项标注测试通过、无警告；新审计脚本语法错误已修复并留证。输入SHA不变，数据定位阶段完成，历史生成原因及最小漏洞语义仍待核实；不启动训练或DDG扩展。详见training_changes第30节。审阅与记录AI：Codex。

## 2026-10-20 固定作者图继续创新的收束设计（Codex）

- 用户决定暂不追查标签；主实验继续固定作者CFG+CG、标签、token及原折，现有争议只列限制，不删样本或按标签连边。
- 当前Stage K四关系整体DDG已工程闭环，但完整结果未证明稳定收益。下一候选是保留全部v1关系再加受限CONTROL_DEPENDENCE；明确属于DDG＋控制依赖，不冒充状态Def–Use，不先扩跨函数/反向/HGT。
- 源码核对发现：旧语义IR缺guard失败出口/统一EXIT/分支信息；旧方向adapter只识别四关系；旧verify扫描整个DFG源码集合。后续分别采用旁路控制IR、显式正向adapter、按旧plan清单的只读归档核验，不能直接套用或改旧seal。
- 一次整体语义/投影/覆盖验收后，若旧图/标签/特征/折/训练数值/共同未训练初值绑定通过，可复用旧60fit，仅新增候选30fit；固定四任务fold0计入，无逐小点F1消融、不以涨分挑折。
- 详细设计：开发树scripts/DFG/AUTHOR_GRAPH_NEXT_STAGE_DESIGN_2026-10-20.md；变更记录第31节。本轮只设计/文档，无新实现、构图、测试或训练。修改与分析AI：Codex。
## 2026-10-20 作者图上的DDG＋受限控制依赖实现（Codex）

- 新增开发树control_dependency/及experiments/guard_extension/旁路；仅追加正向CONTROL_DEPENDENCE，保留作者全部节点/标签/token/CFGCG及Stage K四类DDG。261旧代码SHA未变，HGT和原训练数值函数不修改。
- 核心采用带正常/异常出口的分析CFG及后支配直接控制依赖，支持可靠guard/if/提前退出/既有前置modifier子集，函数回退无残留。旧图无revert/emit节点则不猜投影。是DDG＋控制依赖，不是纯Def–Use。
- 四任务新增边3086/1929/2421/1384，真实新增两层pairs1690/1096/999/464；原图不变量通过，每图8新canonical，各折有train支持。未知复杂语义/循环/完整modifier仍受限。
- 原回归413、新测试73，共486通过；首次summary Path错误已修并保留日志，旧grammar的无括号!send解析歧义保持回退。没有solc验证。
- 旧60fit只读归档核验通过；新候选准备30个保存初值，四任务fold0计入30，条件通过后完成剩余26。GPU串行，旧基线不重训，沿用原各任务配置/best规则。当前先记录实现，正式结果另补，不预报提升。
- 产物artifacts/paper_kfold/guard_extension_v1/，详见IMPLEMENTATION_REPORT.md及training_changes第32节。实施、审查、记录AI：Codex。
## 2026-10-20 控制依赖候选四fold0验收与全折放行（Codex）

- 四个正式fold0已验收；best BF1按重入合约/访问控制合约/重入节点/访问控制节点为84.6154/90.0000/99.6487/99.4652。相对旧DDG三个持平，重入节点下降0.1757pp，仍按冻结方案继续剩余26，不挑成绩。
- 独立检查best最小loss、last末轮、概率与类别、监督梯度、best/last重载；新关系梯度在enhancement_relations字段，实际非零。GPU单模型串行，旧60fit及四fold0复用，完整结果待追加。
- 只读交叉审查发现address接收者内嵌调用漏检边界。四任务精确扫描中仅两个函数命中，且二者本批原已fallback/零事实；当前图未受污染，下一版本待修，不修改本批seal。另有旧modifier_context字段歧义，按新relation证据判断。
- 证据guard_extension_v1/{fold0_independent_review.json,readonly_receiver_review.json,full_controller_001.log}；详细training_changes第32.6–32.7节。实施、核验、记录AI：Codex。
## 2026-10-20 作者HCG＋DDG＋控制依赖全折完成（Codex）

- guard_extension_v1已完成30次候选正式fit，四fold0计入；旧HCG/整体DDG各30fit只读复用，联合90模型。全部新任务attempt_001，0失败/重试/OOM，没有改作者图/标签/token、旧DDG、HGT或原数值训练规则。
- 三配置是作者HCG→同图整体DDG→继续追加正向CONTROL_DEPENDENCE。控制关系是真实接入，不是替换旧DDG；属于DDG＋控制依赖，不能称纯Def–Use。

| 任务 | HCG best BF1 | 原DDG best BF1 | 候选best BF1 | 候选−DDG(pp) | 相对DDG升/平/降 |
| --- | --- | --- | --- | --- | --- |
| 重入合约 | 94.1593 | 94.1593 | 94.1593 | +0.0000 | 0/5/0 |
| 访问控制合约 | 93.5590 | 93.5590 | 93.5590 | +0.0000 | 0/5/0 |
| 重入节点 | 96.0580 | 96.1027 | 96.1210 | +0.0183 | 3/2/5 |
| 访问控制节点 | 95.9723 | 95.8887 | 95.9171 | +0.0284 | 3/4/3 |

- 均为CV validation、等权折均值、最低val loss的best；节点按HCG节点计分。HCG是本地作者图复跑基线，不是论文原数字。last/OOF独立报告，不换成更有利checkpoint。候选访问控制节点仍低于HCG，当前没有稳定改善证据。
- 两合约概率全部变化但类别相同。重入节点25纠错/19退化、总错429→423；访问控制7/5、216→214。两类buggy_18及AC buggy_26不变，R buggy_36退化2；parity无新控制边却纠错2，不能全归为控制边直接语义收益。
- 30折240项新canonical×fold都有train支持与实际监督梯度，5464条逐轮梯度非零；60新best/last重载精确一致。独立重算180组指标/混淆矩阵通过；261旧代码SHA及HEAD未变。所选回归413+新测试73=486通过，35条既有warning，无solc验证。
- 30fit合计4959.45秒约82.66分钟，最大allocated2894.40MiB，最低整卡free29MiB，保持单模型GPU串行。receiver嵌套调用边界仍待下版修复，但本批命中函数均已回退/零事实；不改本批seal。
- 最终产物：artifacts/paper_kfold/guard_extension_v1/RESULT_REPORT.md、RESULT_TABLES.md、report.json、逐折/配对/OOF/错误/关系/资源CSV及验收JSON。完整预测与稀疏变化表口径分开；辅助摘要分母已按完整样本修正，不改正式F1。
- 两树训练变更文档第32.8–32.11节详细记录；旧文档只追加。当前实现和全折实验已收束，不自动扩seed、七类、新关系或继续训练。实施、执行、核验与记录AI：Codex。

## 2026-10-20 标签上下文与合约读出诊断完成（Codex）

- 新增旁路readout_diagnostics/，产物artifacts/readout_diagnostics_v1/；图/作者标签/token/DDG/HGT/原训练和旧seal不变，0新fit。源码、命令、报告详见README及DIAGNOSTIC_REPORT.md，训练变更第33节。
- 节点按参考一致/争议/未审计分层，1127已审计、353分歧、18619未审计。GUARD best重入错误55/199/169，访问控制5/125/84。三个困难文件仍252/87/42错，其中197/83/42落在标签分歧；公共投影不是已认证真值，不能把全部错误归标签。
- 30个已有合约best串行复放通过，768文件/95232贡献记录；512个配置配对概率全部变化但类别0变化。最大历史概率误差1.1921e-7。难节点文件合约预测均TP，粒度不要混淆。
- 全部漏报有正局部证据，但HCG正确良性也有重入65/68、访问控制56/56。重入漏报图平均仅14.6节点，不能简单归为大图均值稀释或直接采用最大节点分数。
- 新诊断attempt001的高精度参考/GPU margin混检失败已保留，attempt002以原后端head精确重放＋float64参考恒等式＋独立数值残差通过；未放宽历史预测要求、未改原精度。33tests通过，0失败/跳过；30目标加2额外核验前向，0训练。
- 成功诊断总670.16秒，峰值allocated631.81MiB。NEXT_STAGE_DESIGN.md仅设计单一零初值attention读出2×2对照，条件满足时新增20次合约fit；候选尚未编码，本轮没有启动。保持CV validation与HCG节点口径，未扩seed/七类。旧receiver绑定边界仍独立待修，当前冻结图已核验不受影响。
- 本轮代码与详细结果仅在开发树；两树文档仅追加。实施、诊断、审查与记录AI：Codex。
## 2026-10-20 固定作者图的合约attention读出实现（Codex）

- 开发树新增experiments/readout_attention/旁路，独立批次paper_kfold/readout_attention_v1。仅将每文件mean替为softmax(h @ a)加权求和，a全零128维；HGT层/原分类头、图/标签/token/DDG/control、原折和训练数值规则不改。
- 两任务各5折，HCG/GUARD两图各attention，共20新fit；20历史mean只读复用。旧权重从每折optimizer_steps=0初值逐张量复制、恢复原fit_seed，不从训练后checkpoint继续。新runs的HCG/GUARD均是attention，graph_kind与readout分开绑定。
- 36新测试+57已有回归=93通过，4条既有warning。四个真实零步GPU预检通过：HGT输出精确、pool误差≤2.384e-7、logit≤2.1249e-5；HGT/readout梯度分别有效，初值未更新。独立审查917文件SHA、20初值和10对共同参数通过。
- 先4正式fold0门槛再余16，不以F1上涨放行；新plan冻结692资产、207旧代码、15新源码。当前重入两fold0已完成、访问控制运行中，完整结果后补。单GPU串行，free最低34MiB，无自动降配/改图/切CPU。
- 详细第34节、README及独立preflight/初始化审查JSON；只追加文档，保留用户修改/旧seal。无节点新fit、七类扩展或新seed。修改、实施与记录AI：Codex。
### 2026-10-20 attention四fold0通过并进入完整五折（Codex）

- 四候选/8checkpoint及逐轮早停、LR、梯度、身份与独立指标验收通过；R best84.6154两图、AC90两图，与mean持平，不择分放行。
- 已继续余16次正式fit，复用四fold0。全部保持原配置，记录full_controller_001.log；完整结果稍后追加。独立核验20初值的7240共享tensor精确一致，HCG未加入空增强关系。
- 审阅CPU reduction线程微差已按原2线程核对，不改训练或容差。详见training_changes34.6及fold0_independent_review.json。执行与记录AI：Codex。
## 2026-10-20 合约attention完整五折实验完成（Codex）

- readout_attention_v1完成20新attention fit，只读复用20历史mean，联合40模型/80组best-last指标。全部attempt_001，0失败/重试/OOM；40新checkpoint、逐轮早停/OneCycle、输入/初值/预测及独立指标核验通过。
- 唯一模型变化是文件内softmax(h @ a)加权读出，新增全零初始化128参数；图/标签/512 token/DDG/control/HGT/原训练规则及原折不改。新目录HCG/GUARD都是attention，历史mean不覆盖。

| 合约任务 | HCG mean BF1 | HCG attention BF1 | 增强mean BF1 | 增强attention BF1 |
| --- | --- | --- | --- | --- |
| 重入 | 94.1593 | 93.5157 | 94.1593 | 94.1593 |
| 访问控制 | 93.5590 | 92.7619 | 93.5590 | 90.5564 |

- 主结果均最低val loss的best/CV validation。重入增强attention纠正1误报又新增1误报，F1持平但预测不同；HCG attention新增1误报。AC两attention均新增1误报，增强attention再漏报proxy.sol/rubixi.sol。原两任务5/6个漏报均未纠正。
- best交互重入+0.6437pp来自HCG attention退化，增强未超过mean；AC−2.2055pp。last同序R90.8867/93.0421/91.6169/92.3525，AC85.9247/80.7818/84.5429/82.5007；不择高替换best。节点模型未训练，buggy18/26节点争议未由本批解决。
- 93相关测试通过、4既有warning；315epoch读出梯度全部连接非零，增强316条有train支持的canonical审计均有message梯度，9未见关系保留。20fit累计3285.44秒，最大allocated2894.40MiB，最低free21MiB，GPU串行。
- 结果与代码在开发树ge-sc-llm-ddg-v11；主报告artifacts/paper_kfold/readout_attention_v1/RESULT_REPORT.md、RESULT_TABLES.md及全部CSV/独立审计JSON。详细training_changes第34.7–34.10节。两树文档仅追加，原代码/输入SHA不变。
- 结论：该attention候选无稳定收益，保留mean主方案，旁路负结果归档。完成本批后停止，不扩seed/七类/新关系；不能据此判定DDG整体无效。实施、执行、分析与记录AI：Codex。
**完成时间补记（2026-10-21，Codex）**：本阶段跨日执行，上述2026-10-20标题表示阶段开始日期；完整五折训练验收和最终报告交付完成于美国东部2026-10-21。UTC及文件时间另记delivery_manifest.json，不将54.76分钟的累计fit计时冒充完整阶段墙钟耗时。
## 2026-10-21 DDG方案与已完成实验审查（Codex）

- 完整报告/独立证据：开发树scripts/DFG/experiments/artifacts/design_code_review_20261021_v1/REVIEW_REPORT.md。最新实现仍在ge-sc-llm-ddg-v11，原编辑树不含所有后续state/control/实验入口。本轮无算法/图/标签/HGT/训练修改，无新fit，旧seal保留。
- 已完成受限标量、状态/简单mapping、访问顺序、受限继承/modifier与控制依赖的图增强及完整两类K折。未完成完整跨函数/交易摘要、任意storage别名/完整modifier/异常、一站式任意源码推理、七类/多seed/独立评估；反向DDG有意暂缓。
- 确认控制cfg.py的address转换receiver内嵌调用漏检，独立样例会错误产事实。当前冻结数据命中函数都已因其他条件回退，未发现发布图污染，下一版待最小修复。旧modifier_context false字段有歧义。
- 主cli仍scalar-only；旧reflect_graph除DATA_DEF_USE外会反射其他新关系，不能当完整方案入口。当前正式旁路五类关系方向正确。旧overall verify因新增文件集合报drift，应采用已有只读归档核验，不改seal。
- 新机制证据：HGT跨canonical mean使新增val-only relation也可能缩放无新边train节点的原消息（小图1→0.5）；不是标签泄漏，尚不能认定为低收益主因。分差同时包含语义/聚合/参数/优化变化。
- 同一主链best BF1：R合约94.1593三配置相同、AC合约93.5590相同；R节点HCG/DDG/GUARD=96.0580/96.1027/96.1210，AC=95.9723/95.8887/95.9171。未证明稳定增益；attention未改善，保留mean。STATE_DEF_USE节点仅R4/AC5，不能称完整状态依赖已验证无用。
- 本轮539所选pytest通过、0失败/跳过、43旧弃用warning；首次grammar环境失败另留证。9标量探针、receiver复现、方向和聚合探针；独立重算380组best/last指标一致，222运行源码seal匹配。未跑solc/正式GPU训练/全部checkpoint重载。详细training_changes第35节；审查和记录AI：Codex。
## 2026-10-21 下一阶段收束方案（Codex）

- 根据完整K折与第35节审查，下一步先修receiver绑定、明确modifier证据与统一完整profile/正向adapter/归档入口。保留mean、原图标签与旧结果，不继续扩关系或attention；方案详见training_changes第36节。
- 修复后核对四任务规范化图/特征/标签摘要。图与计算等价则不重训；旧结果仍归旧运行版本。若改变，单列影响并另建批次，不能覆盖历史seal。
- 然后只做一次有限机制诊断：实际消息/canonical均值影响/新增上下文；最多12个固定源码函数正反与回退样例。区分不存在依赖、范围外、缺投影和已接入无收益，不为每小点跑K折。推理干预不是训练消融。
- 前两阶段新增正式fit均0。只有明确诊断支持一个新方法假设后才设计单一受控候选；不自动启动60/90次、七类或多seed。当前仅方案记录，未修改代码或执行新测试/训练。设计与记录AI：Codex。
## 2026-10-21 DDG统一工程版与验收完成（Codex）

- 当前代码在ge-sc-llm-ddg-v11/scripts/DFG/integration/；新增baseline/scalar/full/full_guard构图、精确投影不变量、五关系正向模型adapter与只读archive入口。原树代码未迁移，两树README明确入口，训练变更第37节详细记录。实施、审阅与记录AI：Codex。
- 修receiver嵌套调用/副作用保护：未知语义相关控制分析整函数回退，无部分控制facts；同一断言旧2facts失败、新fallback/0facts通过。modifier字段区分旧prefix阶段；max_iterations三阶段统一，默认100000。旧230个生产Python SHA未改，用户auto_version_solc修改保留，旧seal不动。
- 四个真实任务从原作者HCG重建，输出artifacts/integration_release_v1/rebuilt/。节点18312/13432/12036/7710，最终边28605/21620/18638/13127；节点标签/token/原边/schema/实际DGL有序端点全部等价。两个节点任务仅ddg_fact_indices重编号（1885/2455边属性），不能当完整fingerprint相同；旧checkpoint绑定不改。最终control默认四图fingerprint复核通过。
- 12函数Oracle预先封存后验证全过，4正例投影/4无特定关系/4范围外回退；Codex源码审阅，非独立人工认证，未执行solc。最终oracle/validation_v2/results.json；保留初版工具计数失败及修复记录。
- 四任务保存的未训练共同初值CPU诊断：无新增入边但canonical分母变化6879/4350/4655/2006节点；其中首层聚合实际改变6056/3866/3945/1647。R表达式入向canonical18→31；第一层缩放公式最大误差9.5367e-7。此为机制证据，不是训练后收益或低收益原因定论。
- 最终613相关pytest通过，0失败/跳过、31既有warning；原overall_cv只读核验60fit/60收据/689记录文件，checkpoint以SHA核验未全部重载。本轮0正式fit、0新F1，不改HGT/token/标签/fold/训练规则，不启动七类或更多seed。
- 当前受限工程流程闭环完成，未宣称完整Solidity DDG；任意跨函数/交易、storage别名及复杂modifier/异常仍不支持。旧整体结果无稳定收益，mean保留，attention负结果保留。若继续研究，只考虑有机制证据的单一增量聚合候选，需另行验证，不能保证提升。
- 入口与命令：integration/README.md；完整报告：experiments/artifacts/integration_release_v1/IMPLEMENTATION_REPORT.md；旧审查/方案保留第35—36节。两树交接与训练文档只追加，本轮停止于工程收束与诊断。


### Git archive and consistency check (2026-10-21)

The current integration/state/control/experiment implementations and text
evidence are archived on ddg-v1.1-correctness. Main retains historical code.
The DFG README first paragraphs deliberately differ: main points to the
development worktree; development links its local integration entry point.
HANDOVER and training_changes remain byte-identical across both worktrees.
The main-only auto_version_solc.py change consists of three leading blank lines.

Upload/local-only scope is recorded in docs/github_archive_2026-10-21.json.
Large raw text and binary graph/checkpoint assets stay local; original receipts
and manifests retain their binding identities. A fresh clone is not a complete
experiment-data backup. No historical plan/seal is rewritten.

After archival commits, validate each completed modern batch in development:
~~~bash
python -B -m scripts.DFG.integration.archive --batch scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1 --output /tmp/overall-archive-UNIQUE.json
python -B -m scripts.DFG.integration.archive --batch scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1 --output /tmp/guard-archive-UNIQUE.json
python -B -m scripts.DFG.integration.archive --batch scripts/DFG/experiments/artifacts/paper_kfold/readout_attention_v1 --output /tmp/attention-archive-UNIQUE.json
~~~
Choose fresh output filenames. These verify recorded source/input/checkpoint
hashes and receipts without training or changing execution guards.

## 2026-10-23 DFG v2 Prompt 0完成及三文档补记（Codex）

- 当前开发树为 `ge-sc-llm-ddg-v11`，分支 `dfg-v2`。Prompt 0审计已提交为 `085eb86e14f9d13f19a4f6ba937fb3fce279e13b`；基础为 `29a9b4e`，保留既有DDG实现与实验。该提交只增加侦察脚本及报告，没有实现v2新算法、没有开始Prompt 1，也没有新增训练。
- 本轮按用户明确要求，补齐本交接文档、`docs/training_changes_2026-10-07.md`第38节（详细决策/实施/验证）及 `scripts/DFG/dfg_v2/PROGRESS.md`。旧正文保留；上一条“Prompt 0不修改旧文档”是当时的执行边界，本次授权后已完成追加，不再表示当前旧文档尚未更新。修改、审阅与记录AI：Codex。
- 唯一已批准的方案选择：v2后续统一复用已有 `state/stage_k/profile.py::SupportedSourceView` 与源码SHA绑定的既有版本元数据；未知版本继续回退，不新建状态节点、不猜编译器版本。原SourceView下AC合约锚点804/922=87.20%曾触发暂停；经用户批准后为872/922=94.58%。另外R合约2360/2369=99.62%，R节点1788/1788、AC节点403/403均100%。保留原视图失败证据，不改原始审计JSON为通过。
- 输入是作者CFG+CG结构/标签加本地已冻结的CodeT5p-770m tokenizer ID；节点任务是漏洞文件的HCG子集，不是下载的另一套CFG-only图。四任务文件/节点/边为R合约142/18312/19267、AC合约114/13432/15538、R节点71/12036/11710、AC节点57/7710/8840。token抽样800/800逐元素相同，float32[512]，未加载LLM encoder。
- 原标量对照仍调用未修改的 `integration.pipeline.build_graph(profile="scalar")`，没有套用新视图来改变对照。四任务支持函数/源码总函数为2035/3404、2128/3148、1210/2045、1550/1958；新增DATA_DEF_USE边3561/4032/1894/2836。新基线图只写入新产物目录，不替换任何旧图。
- Prompt 0回归223 passed、0 failed、29条现有弃用warning；5个审计/汇总脚本Python3.7语法与拒绝覆盖检查通过。原11063个受保护已跟踪文件SHA当时全部一致；本轮仅允许三个文档追加，不把历史保护快照改写成新时点结果。
- 已有四任务nested内层名单，在内存重新生成与冻结内容4/4一致。v2拟使用nested协议；历史paper_kfold仍是CV validation，不重命名历史成绩。G*外层测试选型问题及nested checkpoint绑定适配只是待确认建议，尚未实施；后续改方案先征求用户。
- 完整证据见 `scripts/DFG/dfg_v2/RECON.md`、`recon.json`、`PROGRESS.md` 和 `scripts/DFG/experiments/artifacts/dfg_v2/recon/`。下一步为Prompt 1，当前尚未启动。
- **GitHub同步待办**：WSL访问origin时DNS解析失败；Windows Git尝试也未取得有效认证，未成功读取远端引用、未推送。用户随后明确要求“先不推送，等解决后再推送”，本轮停止网络排查，仅保留本地提交。不声称本地与GitHub已一致。之后应先fetch核对远端分支，再正常推送 `dfg-v2` 并检查双方commit SHA相同；不force push，不把该分支合入main或ddg-v1.1-correctness。

### 2026-10-23 DFG v2推送恢复补记（Codex）

用户重新授权尝试后，已通过Windows Git＋WSL既有 `gh auth git-credential` 完成fetch与正常快进push：origin/dfg-v2由29a9b4e更新到e76eec1，包含Prompt 0代码085eb86和三文档补记e76eec1。没有force push，也没有GitHub分支保护/审批策略拒绝。此前障碍是WSL DNS解析失败，以及Windows Git无法直接找到WSL的凭据助手；WSL本身的DNS问题尚未修复。

凭据助手仅以本次Git命令的临时配置调用，不读取/输出token，不改全局Git、DNS或代理设置。原“待推送”条目保留为历史快照，当前P0与三文档更新已经上传；本次状态补记也纳入同一dfg-v2分支，最终以本地HEAD与实时ls-remote SHA相同验收。其他分支和本地实验二进制保持不变。修改与核验AI：Codex。


## 2026-10-23 DFG v2 Prompt 1完成（Codex）

- 开发树ge-sc-llm-ddg-v11、分支dfg-v2，从远端修订1f2a308开始，pull --ff-only确认最新。仅新增dfg_v2下5个模块和3个测试文件，旧DDG/HGT/tokenizer/训练脚本/图/标签/折/产物不改。
- 已打通G0–G3R输入→DGL→原节点/合约分类器。原边保留原reflect，新正向单向；G3R显式REV仅在模型输入生成。env_source有独立类型参数，排除节点监督和合约mean池化；标签哨兵不写回图。
- 默认mean仍用原HGT；可选nonempty_mean诊断只改变跨关系分母。复制来源有SHA，无FunctionType，主forward直接继承。
- “旧DATA_DEF_USE被反射”的测试预期已先征求用户并获同意，改为验证真实已修复行为，旧代码与PROMPTS不改。新PROMPTS的SupportedSourceView、G* inner选型及nested checkpoint决策已明确，后续阶段才实施。
- 新测试65通过，原DDG+graph_utils223通过，共288；0失败/跳过，分别8/29条DGL/NetworkX弃用警告。G0两任务初值/RNG/前向与旧模型精确一致，新关系在HGT中有实际message梯度，aux不监督/不池化和图不变量通过。
- 11060个冻结已跟踪文件SHA不变，三文档仅追加；证据artifacts/dfg_v2/prompt1_v1/，详细training_changes第39节及dfg_v2/PROGRESS.md。
- 只做CPU小图接口验收，无训练、程序分析、真实v2语义图生成或GPU预检。旧extend_forward未作为v2新图推理验收。Prompt 1本地提交后停止，未push、未开始Prompt 2。实施与记录AI：Codex。


## 2026-10-23 DFG v2 Prompt 1b双向主配置完成（Codex）

- 用户已明确采用双向，基于0449355执行最新Prompt 1b；pull --ff-only确认起点已同步。主配置变为G1R→G2R→G3R，G0原HCG、G3正向对照保留，默认G1/G2移除且不静默变义。旧P1记录和产物保持历史含义。
- 只修改dfg_v2/__init__.py、model_input.py及两个对应测试文件。REV按关系配置生成，不再只识别G3R名称；NetworkX只存正向，模型输入为独立REV canonical。env_source资格由ENV_FLOW决定。原DDG/HGT/tokenizer、模型forward、监督/池化和训练代码不变。
- 验证原reflect会混合同类型WRITES_STATE方向及异类型反射/真实反向；v2显式REV隔离该问题。当前原DATA_DEF_USE单向特判保留。G0初值/RNG/前向等价、错误输入拒绝、辅助节点不监督/不池化、新关系梯度均通过。
- 新验收86 passed，旧DDG+graph_utils223 passed，共309；0失败/跳过，8/29条已有弃用警告。两文件环境干预在同一profile同初值下执行：G3环境表示不受使用处改变，G3R实际收到使用上下文，且不跨文件传播。这不证明F1提升。
- 11072个受保护已跟踪文件SHA一致，三文档仅追加。证据artifacts/dfg_v2/prompt1b_v1/；详细方案选择、实现、数值、命令和限制见training_changes第40节及dfg_v2/PROGRESS.md。固定token不等于隐藏表示不学习，“环境收益最大”尚无效果证据。
- CPU小图接口验证，无新训练、真实v2语义图、GPU/solc验收；未开始Prompt 2。依共享约定本地提交后停止，本轮未push。修改、复核与记录AI：Codex。


## 2026-10-24 DFG v2 Prompt 2 L1扩展完成（Codex）

- 基于dfg-v2@5526009，pull --ff-only确认最新，新增v2内7个生产模块和4个测试文件；旧DDG/HGT/tokenizer、P1/P1b、标签、固定折和历史产物不改。无替代方案变更，沿用已批准SupportedSourceView。
- L1支持聚合局部/参数、legacy单变量var、强/弱定义以及Stage J受限modifier/继承。旧成功函数直接保留；仅回退函数重试。不同来源视图精确投影，函数级失败无残留，保留所有原HCG节点/属性/基础边，只加正向DATA_DEF_USE；G1R在模型输入加显式REV。
- 四任务支持数：R合约2035→3128/3404，AC合约2128→2791/3148，R节点1210→1960/2045，AC节点1550→1856/1958；对应DDG边3561→5659、4032→5713、1894→3419、2836→3889。6923个旧成功任务内函数实例solver全字段一致，原事实和边逐项保留；modifier事实过滤均0。
- 四个CPU G1R模型注册通过，512维特征保持。最终v2 182＋旧回归223＝405项通过，0失败/跳过，8/29条既有弃用warning。11077个受保护文件SHA不变，三文档只追加。
- 实际grammar的delete/前缀update下标形状做v2顶层AST适配；未改parser。无名称聚合声明的恢复route审计已修正；首轮产物不覆盖，最终图/报告在artifacts/dfg_v2/l1_build/final_route_audit/。两轮图计算摘要和投影事实相等，仅route证明信息变化。
- 详细记录见training_changes第41节与dfg_v2/PROGRESS.md；测试/构图/比较/保护收据在artifacts/dfg_v2/prompt2_v1/。依旧是基变量近似，ordinary call引用副作用不跟踪，复杂modifier/版本不明/assembly等仍回退；覆盖提升不代表F1提升。
- 未训练、未执行solc、未开始Prompt 3/L2或L3。按共享约定本地提交Prompt 2后停止，本轮未push。实施、复核与记录AI：Codex。


## 2026-10-24 DFG v2 Prompt 3 L2状态声明中转关系完成（Codex）

- 起点为dfg-v2@80afa66681ba46f848472895eae6871957a3c7ec，已核对远端同一提交。按最新版共享上下文与Prompt 3实施，新增8个生产文件、8个测试文件；既有代码只在v2/l1_access.py提取共享AST形状识别函数。旧DDG、HGT、tokenizer、标签、固定折和历史产物不变。
- L2在Prompt 2最终L1图上增加WRITES_STATE（语句→已有状态声明）与READS_STATE（声明→语句），不新建节点。G2R通过既有adapter生成显式REV；NetworkX只存正向。局部遮蔽按整个callable保守处理，同文件C3唯一声明绑定，有限storage别名取并集，不做调用摘要或跨函数到达定义。
- ProjectionView仅去掉词法作用域版本门槛，保留预处理token一致性与精确AST映射。四任务362个原SourceView成功文件实例映射一致；额外恢复8个文件的59个状态锚点，四任务锚点全部100%。L1仍使用既有视图；四任务L1完整图与计算fingerprint重建均相同。
- 用户明确批准收紧push/pop：仅确认接收者为动态数组或bytes时记录读＋写；合约对象同名方法和类型不明者按普通调用记录可确认读取，审计跳过写入原因。核验实际被访问的字段/元素类型与alias指向类型，不只看根变量名。修复前2项回归失败，修复后相关72项通过。

| 任务 | 原节点 | WRITES_STATE | READS_STATE | L1回退函数中有L2的数量/总数 | 来自回退函数的L2边 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 18312 | 3108 | 4314 | 182/276 | 480 |
| 访问控制合约 | 13432 | 1609 | 2208 | 224/357 | 707 |
| 重入节点 | 12036 | 2254 | 3070 | 51/85 | 195 |
| 访问控制节点 | 7710 | 767 | 1091 | 72/102 | 284 |

- 四个CPU G2R模型构造/schema通过，512维特征保持；没有真实图前向、训练、优化器更新或F1结果。原节点顺序/属性/标签/token、原CFG/CG及L1边/key/证据全部保留。无对应节点的读写只审计丢弃，四任务unmapped出现数219/228/101/93。
- 新增162项测试；全部v2 344项＋旧DDG/graph_utils 223项＝567 passed，0失败/跳过；8/29条既有弃用warning。每任务seed=0抽20条，共80条边经独立Codex源码复核（85处出现、5条alias边），未发现具体错误；不等同专家标注或solc编译验证。
- 最终图和manifest/audit/acceptance/model_schema/edge_sample在artifacts/dfg_v2/l2_build/；前后证据、测试日志/XML、投影比较和复核在artifacts/dfg_v2/prompt3_v1/。旧push_pop_review顶层source字段误被后续语料覆盖，已保留原件并另写corrected审计，源码身份与70处语料出现重新核验；未因此改变图或标签。
- 详细文件、选择、命令和限制见training_changes第42节；20条完整端点源码见dfg_v2/PROGRESS.md。L2为流不敏感的基变量中转关系，不证明执行可达、别名精确或检测收益。未开展L3/Prompt 4、外部编译或训练；按共享约定本地提交后停止，本轮未push。实施、复核与记录AI：Codex。


## 2026-10-24 Prompt 4.0：L2三个正确性修订与独立重建（Codex）

按更新后的PROMPTS.md（47f3f2c）先完成Prompt 4第0部分，未改变方案，也未提前加入L3文件。修改state_access.py让struct_field_assignment只访问value字段，避免把call选项名value/gas误读为状态；state_binding.py把精确string/bytes类型计入有版本证据的legacy局部storage引用，bytes1…bytes32不纳入；units.py增加try_statement的attempt区域，缺HCG节点计unmapped，不挂函数节点。l2.py/projection_view.py/tests/test_l2.py仅删除末尾多余空行。

新增test_prompt4_zero.py共20项，实际grammar先行核验。相同测试修复前10 failed/10 passed；修复后连相关既有测试126 passed。最终全v2 364 passed、旧DDG+graph_utils 223 passed，共587项，0失败/跳过，8/29条既有弃用warning。测试包含版本不确定、显式memory/calldata、var字符串/字节引用、名字字段和接收者读取、try独立归属及图不变量。仅解析器/语义测试，未执行solc。

四任务已重建至artifacts/dfg_v2/l2_build_r1/，原l2_build/只读保留。逐任务新增/删除边均0，边属性变化均0，完整图fingerprint全部一致。unmapped仍219/228/101/93，alias绑定仍45/29/42/29，WRITES/READS仍3108/4314、1609/2208、2254/3070、767/1091。说明这些反例缺陷确实已由回归覆盖，但本批真实图未触发改变投影结果的情况；不能据“图相同”认为修复无效。

后续L3及G2R使用l2_build_r1/。不重跑L1：本次修改的units/state_binding/state_access不在L1导入路径，l1*.py与其旧依赖SHA均保持，EOF清理无计算改变。P2最终L1作为输入仅核验manifest/SHA，不覆盖。原标签/token、CFG/CG、HGT和训练逻辑保持。

实际命令（环境同§4.1）：
~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES= python -B -u -m scripts.DFG.dfg_v2.l2_build --output scripts/DFG/experiments/artifacts/dfg_v2/l2_build_r1
~~~
输出已存在，禁止覆盖重跑。证据在artifacts/dfg_v2/prompt4_v1/p4zero/，包括grammar_probe、before/after、全回归日志/XML、rebuild.log和逐任务comparison.json（边差异证据列表为空）。本阶段单独本地提交“Prompt 4.0”，随后才实现第1–5部分；未push、未训练。实施、复核与记录AI：Codex。


## 2026-10-24 Prompt 4 L3实施中：等待一项已确认的AST适配决策（Codex）

阶段4.0已提交71f19dc，后续实现目前尚未提交、未封存L3正式产物。新增env.py/tokens.py/l3.py/l3_build.py/l3_forward.py及test_env.py/test_tokens.py/test_l3.py/test_l3_build.py。已完成14键/18写法、词法遮蔽和明确import别名、辅助节点旁路叠加、离线冻结token编码、L2链式绑定及隔离CPU前向验收入口。未修改HGT、tokenizer原逻辑、训练脚本或原图标签。

独立定向测试：env 63项、tokens 42项、archive/forward guards 24项通过；L3集成除下述待决策反例外23项通过（1项明确deselected，不计作全套通过）。重入合约原图token离线抽样20/20逐位一致。首次集成测试另有5项因共享合成夹具正例缺category而失败，现仅补齐新测试夹具schema；没有修改真实标签、模型或降低断言。真实L3四任务构图和8次CPU前向尚未执行，无训练。

阻断反例：实际grammar把msg.gas + gasleft()解析成call_expression(function=binary_expression(...,gasleft))；this.balance + address(this).balance的最外member对象也可能是binary_expression。按文档仅识别裸function/direct object会漏识别合法写法。完整20例探针在prompt4_v1/env/call_precedence_probe.json。保留test_spellings_merge_per_file_and_edge_not_per_occurrence的失败断言，没有用改写源码或删测试掩盖问题。

已通过异步问题请求用户批准“受限AST后缀适配”：仅沿已确认的未加括号binary右侧/unary参数恢复已知ENV调用/成员，继续检查遮蔽；不越过显式计算括号，不修改grammar、源码、HCG或模型。此项超出文档字面AST匹配规则，按用户“替代方案须先征求同意”要求暂未应用。备选是保留规则并明确漏识别限制。待答复后继续完成测试、真实图验收、详细记录和Prompt 4第二次提交。状态证据在prompt4_v1/pending_decision.json。实施与记录AI：Codex。


## 2026-10-24 DFG v2 Prompt 4 L3完成补记（Codex）

- 第0部分已单独提交71f19dc；第44节对应的待决策记录保留。用户已批准受限AST后缀适配：仅已确认的binary.right/unary.argument、保持遮蔽与显式复合括号边界；新增可审计原/leaf跨度。相同84项测试从13失败修复至全部通过。
- 新增env.py、tokens.py、l3.py、l3_build.py、l3_forward.py及4个测试文件。14键/18写法按文件合并env_source，只向精确投影的原Unit节点加ENV_FLOW；REV在模型adapter生成。原节点、标签/token、CFG/CG/L1/L2全部保持；aux不监督、不池化。离线固定tokenizer重编码80/80逐位一致。

| 任务 | 文件 | 原节点 | env节点 | ENV_FLOW | unmapped出现 | L1回退中有ENV的函数/回退总数 | 回退贡献ENV边 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 重入合约 | 142 | 18312 | 298 | 3857 | 288 | 56/276 | 108 |
| 访问控制合约 | 114 | 13432 | 261 | 2536 | 314 | 97/357 | 160 |
| 重入节点 | 71 | 12036 | 187 | 3200 | 126 | 26/85 | 42 |
| 访问控制节点 | 57 | 7710 | 182 | 1948 | 121 | 37/102 | 58 |

- 四任务8次CPU eval/no_grad前向全部finite；G3每层同键跨文件差异0，G3R确实获得使用上下文。不代表检测F1提升。部分不同邻域仍在1e-6内容差相同，已逐对记录并作静态解释；未确认原因明确保留，不宣称全部已解释。
- 最终v2 538＋旧DDG/graph_utils 223＝761 passed，0失败/跳过；8/29条既有弃用warning。独立验收365 runtime SHA、L2/L1绑定、不变量、80边/84处源码和8前向收据通过；11095个保护文件及历史文档prefix不变。
- 最终图：artifacts/dfg_v2/l3_build/；L2输入：l2_build_r1/；验收/审批/前后测试/只读静态复核：prompt4_v1/。详细选择和命令见training_changes第45节，PROGRESS附每任务20条共80条样本。
- 本轮只完成Prompt 4，不训练、不算F1、不测GPU、不执行solc、不开始Prompt 5；按共享要求本地提交后停止，未push。实施、复核与记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 5.0 完成（Codex）

新增attention_probe/grammar_shape_audit及两份测试；旧分析器、HGT、特征、图、标签和训练逻辑保持。四次CPU诊断的8层重算误差全部0，1070对历史观测均重现。第一层多邻居注意力高度集中，第二层没有相同的饱和现象；731对实际是非零但1e-6容差内接近，不能将全部对称作one-hot导致完全相同，也未额外实测G0。grammar覆盖384文件实例：吞push/pop与表达式user_defined_type候选均0，无分析器修订阻断。新审计器补齐空白前缀及metadata资产校验，最终证据在prompt5_v1/grammar_shape_audit_r1/与attention_probe/。

用户已批准后续“清单加载一次、各层调用一次复用图”和“20个合成身份进行5/10折通用性测试”两项调整，真实fold和旧解析器不变。详细选择、指标与限制见training_changes第46节，测试执行结果见PROGRESS本轮记录。按要求先本地提交Prompt5.0，之后继续统一入口，未push/训练/solc。修改AI：Codex。


Final verification: v2 597 passed (8 existing warnings), legacy DDG/graph_utils 223 passed (29 existing warnings); 820 passed, 0 failed/skipped. Grammar targeted 42 passed, attention targeted 17 passed. Logs: prompt5_v1/phase0_final_v2.log and phase0_final_legacy.log. All 11114 protected tracked file SHAs and all three original document prefixes verified unchanged. Grammar r1 task JSON SHAs equal the prior scan; only audit input guards improved.


## 2026-10-25 DFG v2 Prompt 5 统一入口完成（Codex）

- 新增pipeline、tasks/inputs、store/cli及EXTENDING与测试，旧L1/L2/L3、HGT、tokenizer、标签、折和训练代码不变。两项用户批准选择已落实：每任务源码加载一次、各层调用一次复用；20合成身份验证原5/10折。额外固定source_metadata引用，保留原版本证据。
- 四任务12张新增图的完整/计算指纹全部与历史产物一致；4个F0原文件引用保持，4/4 F3去aux等于F2。新store登记16个图项与20个模型schema。源码384实例全部可用；原标签、token和fold没有改变。
- 最终699 v2＋223旧回归＝922 passed，0失败/跳过，8/29条既有弃用warning；三组新增定向43/31/28项。真实图构建只做20次CPU schema构造，未训练。F0原路径/SHA直引，F3供G3/G3R共用；REV只在adapter。
- 产物inputs/、graphs_v1/；验收日志与历史12图比较在prompt5_v1/；后续读新store。verify核验数据与schema，允许无关代码新增；build期间runtime必须一致。详细选择和实际命令见training_changes第47节与PROGRESS。按要求本地提交，未push/执行下一Prompt。修改AI：Codex。


Final acceptance: cli build exited 0; independent cli verify exited 0 (16 graph entries, 20 recorded schemas, 0 verification HGT constructions/forwards). Actual runtime SHA map still matches build-time; original 11114 protected files and historical document prefixes verified unchanged. Proof: prompt5_v1/final_acceptance.json.


## 2026-10-25 DFG v2 Prompt 6 正确性验证完成（Codex）

- 按要求先封存20组手写Oracle源码/期望（提交aded502），再新增oracle_check、validate_slither、review_sheet、score_review及测试（提交f80073f）。L1/L2/L3、HGT、tokenizer、图、标签和训练代码均未修改；11128个受保护文件SHA及三份历史文档前缀保持。
- 用户批准tuple按现有语句节点验证：检查定义→tuple→使用及声明身份/禁止边，明确未验证tuple内部逐元素值流，不增加节点或改分析器。此选择已详记training_changes第48节。
- 最终Oracle 20例全部执行，17例与封存期望完全一致；8个差异逐项分类为7个期望问题、1个L1实现覆盖缺口。for更新已有独立HCG节点；gasleft的实际拼写为gasleft()。真实缺口为call{value: x}中的struct_expression使L1函数级回退、漏掉x的读取。原函数/图仍保留，无部分DDG残留。本轮未修复，作为Prompt 6b输入；原期望未改。
- v2测试765＋旧DDG/graph_utils测试223＝988 passed，0失败/跳过，8/29条既有弃用warning。测试通过不代表Oracle全部匹配或完整Solidity语义已验证。
- 人工空表：scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv，R/AC各15文件、共512条边。只填写verdict（correct/wrong/unsure）和note；其他列、顺序和行数保持。空表/来源/封存均已保存，AI未填写判定。
- Slither可用，但无获准的离线solc，且部分清单缺精确版本；R 142/AC 114文件全部明确跳过，未执行编译、下载或安装。L1外部对照仅有已投影端点证据，不宣称完整事件级召回。
- 详细结论见scripts/DFG/dfg_v2/PROMPT6_REPORT.md；审计产物在artifacts/dfg_v2/prompt6_v1/。本轮新增中文段落曾受PowerShell管道编码影响，已按UTF-8重写并验证历史前缀未变。仅本地三阶段提交，未push、训练或开始Prompt 6b/7/8。实施、复核与记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 6b 完成（Codex）

- 仅在v2的ExtendedAccessExtractor.reads补call选项与经用户批准的new_expression类型名处理；原分析器/HGT/tokenizer/标签/折不改。修复提交f270ed6，审计与新分类提交c09bbbc。
- 四任务重建通过verify与完整store_diff_r2：重入合约/节点、访问控制合约/节点分别恢复7/4/6/3个函数，新增DATA_DEF_USE 51/50/60/34条；旧边消失0，L2/L3、节点/标签/token保持。真实恢复均来自new_expression，不能全部归因于call选项语法。
- 两项验收调整均先获用户同意：只允许ddg_fact_indices编号重排且解析事实逐条相同；仍fallback且无事实/无残留的函数允许回退原因推进并单列。R两个任务各3个原因推进，未算恢复。其他属性和身份严格。
- 原review_v1的512条边全部保持语义，76行仅引用换号；合约任务新增111条不在旧抽样范围。空表仍未人工填写，评分已通过--equivalence绑定新store，不能据空表声称精确率。
- Oracle18/20匹配；16_call_option_fields已修复，剩余7项仍为原期望问题。CLASSIFICATIONS_v2绑定修复提交，原Oracle/CLASSIFICATIONS不改。最终共同回归886 v2+223旧=1109 passed；8/29条既有warning。
- 后续入口为scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json。首次graphs_v2因临时.py被runtime扫描导致封存失败，原件保留；同输入独立重建r1，387个运行文件摘要一致。不得使用失败目录或覆写旧graphs_v1。
- 详细选择、命令和SHA见training_changes第49节与PROGRESS；11,172个非授权修改的原跟踪文件SHA保持。未训练、未push。实施、复核和记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 6c：真实Slither对照完成（Codex）

- 用户明确允许安装/下载solc，覆盖模板“仅用户自行安装”限制。新增solc-select 1.0.4、pycryptodome 3.20.0，原包版本保持；26个编译器逐个校验SHA256/Keccak和版本，未修改全局solc版本。源码版本来源为43 metadata、207 pragma_derived、6 fallback_default；最后一类经用户批准单列，不因编译失败换版本。
- 新增l1_occurrences.py及两份测试，扩展validate_slither.py；只读复用L1实际分析路由，导出未投影事件集合。入口初始化、回退、继承上下文及声明身份均可追溯；不能映射的整文件不报部分P/R。没有修改L2/L3、图、标签、HGT或训练。
- 256文件：239可比较，11 solc编译失败，6旧编译器CFG缺文件名不可比较；Slither分析失败/unknown/工具跳过均0。重入L1 P/R=72.946%/88.961%，L2=98.902%/86.946%；访问控制L1=60.526%/87.871%，L2=98.299%/85.417%。这是读写事件集合一致性，不是漏洞F1或DDG边召回。
- L1 extra主要是Slither集合没有对应项的入口DEF，missing主要来自保留的回退函数。支持函数内召回99.573%/99.646%仅作诊断，不替换主分母。已核验L2一例初始化范围差异及两例多行位置差异（实际边存在）；其余不一致尚未逐一人工判断。
- 实现提交7918427；最终886 v2＋223旧回归=1109通过，0失败/跳过，8/29条既有弃用警告。11,172个其他原跟踪文件及历史文档前缀不变。完整结果与封存位于prompt6c_v1/slither_full/，独立复核result_review.json；大报告和编译器保留本地，不纳入普通Git提交。
- 详细记录见training_changes第50节、PROGRESS及PROMPT6BC_REPORT.md。当前可用图仍为graphs_v2_r1/store.json；人工512边表未填写，Oracle样例未做编译验证。未启动Prompt7/8或模型训练，未push。实施、复核与记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 6d 完成（Codex）

- 先核验更新文档、dfg-v2/f14194b、旧store及6c seal。新增slither_align/slither_mapping/slither_review/review_supplement和测试；唯一分析器改动为new_expression直接call_argument读取。四任务该形状均0，未重做6b或扩展DDG。
- 修正比较器的IR事件合并、Slither内部scope重命名、entry抢配和delete分类，保留v1/v2/v3。最终13,857差异逐条机械分类；773 other固定seed0抽172，逐条核对未发现支持范围内的v2_defect，不能推广为全部DDG正确。6c原指标不变；新增跨度P/R与漏洞F1无关。
- 6个缺filename文件254节点，仅76精确、98无独立文本、80文本不等，整文件门槛均未过，继续not_comparable。111条新增边已导出review_v1b（51/60），人工verdict/note全空，未报告人工precision。
- 临时cli build成功：四任务12张增强图完整/计算指纹均与graphs_v2_r1一致；16图项文件SHA相同，4个F0引用及20个schema不变。只删除本轮临时重复图约0.84GB，保留比较证明和日志；原图、标签、token、CFG/CG/HGT/训练代码不变。graphs_v2_r1继续作为Prompt7/8输入。
- 最终970项v2＋223项旧DDG/graph_utils＝1193 passed，0失败/跳过，8/29条已有弃用warning。详细选择、命令、全部分类和证据见training_changes第51节、PROMPT6D_REPORT.md与PROMPT6D_CATEGORY_EXAMPLES.md。
- 执行偏差如实保留：辅助复核超范围运行2文件共3次只读Slither，发现后停止，未并入正式统计；没有安装下载或改变样本。另5条modifier初读判断已撤回，封存产物未改。
- 本轮停在6d：未训练、未开始Prompt7/8、未push。实施、复核与记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 6d.1 完成（Codex）

- 已读更新§4.1/6d.1并pull --ff-only确认最新；6b复用。本轮仅修改验证工具，不改分析器/pipeline/HGT/tokenizer/图/标签/划分/训练。新增slither_units、slither_patterns、slither_conventions及六个手写例/测试，扩展slither_align和slither_review。
- L2改为(Unit,变量,READ/WRITE)计数：R候选7658→7485、FP290→117；AC3994→3863、FP192→61，匹配/FN不变。明确消除同一已匹配Unit中的重复FP135/120，共255；净FP减少304还含49个未匹配alias Unit内的重复归并。L1完全不变，指标是事件一致性而非漏洞F1。
- 原773 other=255重复已解决+517新谓词+1 rubixi状态循环未解释。五类各5例谓词核查全部成立；旧172重分类+剩余1+新25共198审查记录：60artifact、50scope、72convention、16unclear，0确认v2_defect。16unclear对应15身份；另76绑定差异全部state_name_ambiguous→scope_limit，没有真实继承回退丢状态的命中。
- 已有可信solc0.5.11运行6手写文件，6/6成功；无真实语料Slither重跑/下载。局部标量循环Phi与L2状态循环证据不相同；storage/reference不以memory探针强推。241个状态成员链write_base_read尚缺对应最小机制实证，不能称全部convention。
- 最终1075 v2+223旧=1298 passed，0失败/跳过，8/29既有warning。中间转义/集成错误、Unit跨度分类修订及输入SHA绑定修订均留日志，不覆盖旧报告。最终alignment_v4_r2、review_r2、binding_review及final_acceptance在prompt6d1_v1/。
- 图仍是graphs_v2_r1。全部13553差异中203逐条审阅、13350未逐条语义判定；新谓词517中391未逐条审阅。剩余other未查0不等于所有差异已证明正确；review gate仍unresolved_analyst_findings。原512/111边人工表未填，不训练/不开始6e、7、8。详细见training_changes§52、PROMPT6D1_REPORT.md。实施、复核与记录AI：Codex。


## 2026-10-25 DFG v2 Prompt 6d.2 验证收尾（Codex）

修改与审查AI：Codex。开始95775d3，分支dfg-v2；仅新增验证工具、测试与记录，原分析器、HGT、图/特征/标签/折不变。详细选择、尝试和命令见training_changes§53及dfg_v2/PROMPT6D2_REPORT.md。

最终gate为passed_with_bounded_FN_residuals。28非空组固定随机242样本全部谓词成立；25组accepted、3组带残留。全量仍10个FN（9聚合loop＋rubixi1），按用户同意附加条件核查无真实body写遗漏、无定义覆盖/KILL及已有依赖污染（限当前抽象），不宣称机制全部查明。**graphs_v2_r1/store.json确定为Prompt7/8最终图存储**，SHA ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4。

alias178FP实际全为READ，0多根FP；4FN为callable内同名局部的保守范围。bare342、initializer771、fallback2402、aggregate25已全量身份/形状核验。批准补两版shape probe；总16尝试13成功3语法失败，失败保留且只重试失败项，无语料重编译/安装。旧分类和512/111人工表未改。

全部1159v2＋223旧＝1382 passed，0失败/跳过；16图20schema只读校验通过。新增7验证.py、5测试、9fixture及报告；三文档仅追加。运行产物在WSL的prompt6d2_v1，本地提交代码/报告，不自动push，不开始训练或Prompt7。


## 2026-10-26 DFG v2 Prompt 7：接入通过，GPU验收受显存阻断（Codex）

修改、复核与记录AI：Codex。新增dfg_v2/experiment/及5测试文件，保留旧实现。新协议dfg-v2-nested：inner_train监督、inner_val早停和strict-min best、outer_test训练后评分；完整固定图前向，env_source不进入监督/池化/指标。支持seal/初值/实际checkpoint/原节点预测身份核验及成功复用、失败显式retry。

用户批准两处选择：G0共同参数精确对齐，新增关系用各剖面原Xavier界限；原/新CPU及GPU各3轮短检查单列，先过G3R显存门槛。详见training_changes§54、PROGRESS和PROMPT7_REPORT.md。

1495测试通过（1272v2+223旧），0失败/跳过；真实R合约fold0两引擎CPU三轮train/val损失最大差0。4任务16图20schema核验通过，最终图仍graphs_v2_r1。

8job计划已封存于artifacts/dfg_v2/prompt7_v1/pilot。首个R合约G3R在第1轮后因最低空闲12MiB<100停止（allocated3299.85/reserved3536MiB；非OOM）。0/8成功，1失败，0重试；partial best及失败/资源记录保留。其余7job、GPU历史对照与完整GPU验收未执行，不报告F1提升，不进入Prompt8。未修改模型/图/超参，未自动切CPU/降配/关闭其他程序。

模板allocator方案在旧torch1.8.1上尚未确认支持；当前probe已独立进程。需用户决定资源措施后再显式重跑该失败fit。代码和记录本地提交，原始运行产物留WSL，不自动push。


## 2026-10-26 DFG v2 Prompt 7b：接入完成，CPU 数值验收未通过（Codex）

实施、复核与记录AI：Codex。基于60aa23e，新增共享K/Q/V层及nonempty_mean版本，默认original保留；layer_impl进入模型、plan、初值、checkpoint/result，跨实现恢复被拒绝。原HGT/DDG/tokenizer/图/标签/fold及优化器数值规则未改。

用户批准：相对梯度按参数张量尺度计算，同时报告逐元素差；小图近零梯度纯相对门槛失败后增加1e-8绝对容差。前向逐位一致、CPU三轮损失1e-6门槛未放宽。新增94项；全部1366v2+223旧=1589通过，0失败/跳过，8/29条既有警告。

四组mean真实CPU前向/梯度通过，三轮损失差均超过1e-6；R/G0/nonempty_mean前向一致，但一个query权重梯度差1.593e-8>允许1.023e-8，随后停止。共5组静态、4对/8次CPU三轮诊断（24epoch）；最后一组和nonempty轨迹未跑。CPU best/last重载一致；不混计为8次GPU pilot。

未发现AC/G0初值/监督/优化器混用；证据符合反向累加与Adam放大解释，但无逐步轨迹不能认定唯一原因。0次GPU诊断、0/8pilot，新pilot plan未封存，旧P7失败记录不改。不能宣称显存已解决，不开始Prompt8。

详见PROMPT7B_REPORT.md、training_changes§55；产物prompt7b_v1留WSL。冻结范围外11061个跟踪文件SHA一致，固定4任务16图校验通过；三文档旧正文仅追加。代码/报告本地提交，不自动推送。


## 2026-10-26 DFG v2 Prompt 7b.1：严格float64预检停止（修改AI：Codex）

在dfg-v2@c079e3a新增隔离数值验收入口及27测试；原HGT/shared层、trainer、优化器、特征、图、标签、折不改。DGL支持float64且小图前向逐位相同；但近零key bias残差的相对差0.13316>1e-10（绝对差2.76e-18），严格验收仍失败。未放宽门槛，未启动真实图fit/GPU/8次pilot。

漏关系负例可检出：两种reducer前向差0.0695/0.1032、各9个非bias梯度失败。新27测试、全v2 1393＋旧223＝1616通过；数值门槛失败和工具测试通过分别记录。11251旧跟踪文件、前批164文件SHA不变，旧文仅追加。最初诊断注入的shape错误与修正日志保留，未改关键断言。

详见scripts/DFG/dfg_v2/PROMPT7B1_REPORT.md、PROGRESS.md和training_changes§56；产物prompt7b1_v1留WSL。下一步须确认近零梯度的混合容差及隔离float64输入适配，不能直接宣布等价或进入Prompt8。本轮仅本地提交，不自动推送。


## 2026-10-26：DFG v2 Prompt 7b.2 数值验收与CPU OOM停止（修改AI：Codex）

- 新增3诊断模块/3测试；原HGT/model/trainer/优化器/DDG/token/图/标签/fold不改。按新模板登记全局尺度梯度容差，旧失败保留。
- 六真实静态前向逐位一致/梯度通过；R/G0/mean三轮差1.55431e-15通过。
- R/G3R/mean的float64原实现被WSL内核OOM杀死(-9，匿名RSS约7.24GiB；WSL7865MiB+2GiBswap)，这是CPU内存，不是RTX3050显存。剩余4轨迹对、全部GPU/pilot未跑；无新pilot计划，不进入Prompt8、不自动重试。
- 零梯度并非只有key bias；单来源/无监督末层/初始饱和均存在。两组额外项已取证，其余4组解释待完成。
- 新138含于全量：1531v2+223旧=1754通过，0失败/跳过。11,254旧文件、184旧产物、固定16图/20schema不变；新GPU验收另补best/last实际SHA检查。
- 详情PROMPT7B2_REPORT.md、PROGRESS.md、training_changes §57；产物prompt7b2_v1含resource_failure/kernel。先确认WSL资源方案再显式新attempt；本地commit，不自动push。


## 2026-10-26：DFG v2 Prompt 7b.3 数值通过、pilot显存门槛停止（修改AI：Codex）

- 新增RSS守护、新版CPU放行和近零梯度静态分类；原HGT/model/trainer/DDG/token/图/标签/fold不改。六静态复用，补跑AC/G0与AC/G3R float64三轮通过；R/G0nonempty实际RSS超6.5GiB主动终止。两R/G3R按更新模板不运行，旧OOM失败保留，新清单不覆盖旧政策。
- 7次GPU三轮诊断完成：G0/G3R共享相对原实现最大差7.6294e-6／3.5763e-7，历史重放差0；best/last验收通过。全部1884测试通过（1661v2＋223旧）。
- 新8项pilot计划/初值/输入已封存。第一项R合约G3R shared在第1轮后整卡最低空闲66MiB<100停止，allocated1824.086／reserved2048MiB，无CUDAOOM。0/8完成，其余7未跑，不修改门槛、不重试、不启动Prompt8。partial best不是完整成绩。
- 三份记录已追加，详见PROMPT7B3_REPORT.md、training_changes §58；运行产物prompt7b3_v1留现有WSL。旧246诊断产物、图/标签/折/源码绑定不变，本地提交但未自动push。下一步先由用户决定显存方案；单模型独立进程串行本轮已经使用。


## 2026-10-26：最终实验设备安排及Prompt 7b.4启动（修改AI：Codex）

用户明确最终实验会迁移到显存充足的服务器；当前4GiB RTX3050仅为本地开发/验收环境，不将本地显存限制作为最终实验规模约束。服务器型号/环境尚未核验，届时仍须绑定图、初值、配置和设备记录，不能仅凭计划宣称已经完成服务器验收。

Prompt 7b.4按用户批准增加启动基线与逐任务独立进程；原模型/图/训练数学不改，旧失败保留。统计名称改为“PyTorch分配器之外的未归属占用估计”，不能用整卡减reserved推断其他进程占用。详细选择与最终结果将追加到training_changes §59及PROGRESS；当前只是执行前登记。


## 2026-10-26：DFG v2 Prompt 7b.4资源核验与停止（修改AI：Codex）

- 新增启动前显存检查及资源计划，仅最小改run.py；旧HGT/model/trainer/DDG/图/特征/标签/fold/数值规则不改。用户批准逐任务独立进程与“未归属占用估计”名称，旧计划行为保持。新8项plan直接引用旧未训练初值。
- 实测CUDA前free3526MiB，初始化CUDA/DGL后2234MiB，1292MiB差额不在Torch reserved内。因此旧“约2GiB来自其他程序”的归因不成立。训练peak allocated1824.086/reserved2048，minimum free76<100，第1轮后按门槛停止；无CUDAOOM。
- pilot0/8：1失败、7未启动，无自动retry。partial best保留，无last/最终结果/完整梯度与重载验收；不进入Prompt8、不用单轮估计150fit时长。
- 全1725v2+223旧=1948测试通过；新增64包含其中。旧538产物、原计算文件/图/标签/初值/计划及三文档旧正文保留。详细见PROMPT7B4_REPORT.md、PROGRESS及training_changes §59。运行产物prompt7b4_v1留WSL，源码/报告本地commit，不自动push。
- **最终实验将放到显存充足的服务器；现在只是本地RTX3050 4GiB受限。** 尚未实际验收服务器，后续应先核验环境、路径和冻结输入身份，再继续验收；本轮不自动改模型或降低资源门槛。


## 2026-10-26：DFG v2 Prompt 7c 本机8项pilot完成（修改AI：Codex）

- 用户明确选择先留本机，并批准local_dev_v1：启动≥3000MiB不变；运行中<100MiB仅提醒，OOM/非有限/其他错误仍停止。旧策略与P7b4失败现场保留。新增local_dev及最小资源计划/入口/验收接入；HGT/model/trainer/DDG/图/token/标签/fold不改。
- 新plan 363814c88c3dd9e22aa61a9bf6e2f5ee5f59b7dfc7262d6685e671e287aa94e5，只读引用P7b4→P7b3的原8份未训练初值；shared_projection、fold0/seed1、nested协议与各任务参数不变。
- 8/8完成并验收、0失败/重试；best/last重载logits逐位一致、预测身份/env_source排除通过。G3R训练支持canonical共266个任务检查非零梯度，留出12个单列；G0不适用新增关系条件。
- R合约G3R最低81MiB，memory_tight=true；其余最低478–1447MiB。全部无OOM/非有限/采样错误，possible_memory_spill=false。时长提醒并不能证明换出。
- 全1792v2+223旧=2015测试通过（新增67包含其中），旧582产物与原计算文件不变。报告PROMPT7C_REPORT.md，详记training_changes §60；产物prompt7c_v1留现有WSL。
- 仅排期估计：Prompt8阶段A60次约5.83h、B90次约8.95h、总150次约14.79h；来自8次单折及canonical插值，不保证其他折耗时。没有启动Prompt8或比较F1优劣。
- **最终正式实验仍计划在显存充足服务器运行；本机4GiB只是当前开发限制。** 用户本轮暂不迁移，服务器环境尚未实际核验。等待后续确认再开展下一阶段；本地commit，不自动push。


## 2026-10-26：DFG v2 Prompt 8完整计划准备（修改AI：Codex）

- 新增批次计划/串行调度/统计/报告模块，最小接入v2 run；原DDG、HGT、tokenizer、trainer、图/标签/折/初始化及训练数学不变。用户批准独立准备授权及统计解释，旧8pilot批准和产物保留。
- 150个正式任务（A60 G0/G3R；B90 G1R/G2R/G3）、30家族及150份新初值完成封存；实际tensor摘要、零步数、共同G0参数全部通过。plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de。正式训练仍0/150，不复用pilot成绩。
- 最终1967 v2+223旧=2190测试通过，0失败/跳过；817旧产物及三文档原文保留。修复报告入口接口不匹配、完整汇总分发与失败恢复边界，未改训练数值。
- 总空间预计26.35GiB、门槛52.70GiB，E盘实际空闲248.15GiB；产物仍在E盘承载WSL。A约5.83h、B约8.95h是估计。阶段A须审阅计划后确认启动，A中间报告后再确认B；无自动重试/选折/扩展seed。
- 本轮使用nested协议：inner_val早停，结束后outer_test评分；全图前向、原HCG节点指标，不能直接比较旧paper_kfold。best主、last辅；节点zsplit，5折合约描述性，A的Holm等待B，G*只在完整矩阵后由inner选择。
- **最终实验计划在显存充足的服务器整批完成；当前4GiB只是本机开发限制。** 尚未部署服务器，未来整批重跑并核验环境，不混合本地/服务器成绩。
- 详见scripts/DFG/dfg_v2/PROMPT8_REPORT.md、PROGRESS.md和training_changes §61；本轮仅本地commit，不自动push。代码与计划准备完成不等于DDG有效性已得到证明。


## 2026-10-26：DFG v2 Prompt 8A 阶段 A 启动记录（修改AI：Codex）

- 本节是执行中登记，尚不代表60项训练或中间报告完成；最终状态另行追加。按更新§4.1/8A读取并pull同步至6dd5d986bf6fa1fade1bc8b247a9fd3035712385；生产代码不改。
- 继续使用prompt8_v1/batch1原150项计划和已保存初值。plan SHA 07f1dbc950a8ca0098e60415f4c5564d89c1dcbde49ab486692dc6afe8ff02de、seal SHA 55aebf929cd578a4a9cd6df4956a4cc3816af010d1963b57a52a1559db5a59f8保持。用户本轮8A请求已排他写入stage_A_authorization.json，只授权A的G0/G3R共60任务；B未授权，旧准备授权不修改。
- 前置图store核验通过；150份已存初值和30个初始化家族逐值验收通过。文档“初始batch verify报告0/150”与现有完整阶段CLI不符，改用已有run.verify(require_complete=False)只读清点，前置时0/150；未修改验证器或放宽结束验收。定向175包含于全部1967 v2，加223旧回归共2190通过，0失败/跳过。
- 已按冻结顺序启动独立子进程串行训练；60项全部验收通过之前只看进度、耗时和资源，不查看或汇总F1。local_dev_v1保持：启动free≥3000MiB，运行低于100MiB只记memory_tight；OOM、非有限值或校验错误停止整批，不自动重试。启动前GPU free3524MiB，Windows E盘实际free264104554496字节。
- 新辅助核验、测试与执行记录在prompt8a_v1；模型产物仍在原计划指定目录，不迁移或覆盖旧实验。详情见training_changes §62及PROGRESS。阶段A完成后生成固定G3R−G0中间报告并停止，不执行B、不计算G*。
- **最终实验将按用户安排在显存充足的服务器整批重跑；当前RTX3050 4GiB只是本机限制。** 服务器尚未实际部署或验收，不混合本机和未来服务器成绩。实施、核验与记录AI：Codex。


## 2026-10-27：DFG v2 Prompt 8A 阶段 A 完成与中间结果（修改AI：Codex）

- 阶段A的60项G0/G3R正式fit全部完成并验收，0失败、0重试，均为attempt_001；执行、独立verify和interim命令退出码均0。B的90项未执行，G*未计算，中间报告完成后停止。没有修改生产代码或冻结plan/seal/图/标签/初值；起点仍6dd5d98。
- 以下为nested outer_test、best主终点的Buggy-F1，单位百分数，均值±样本标准差；节点按原HCG节点，非源码行去重指标。

| 任务 | G0 Buggy-F1 | G3R Buggy-F1 | G3R−G0（pp） | 提升/持平/下降折 |
| --- | --- | --- | --- | --- |
| 重入合约 | 92.7326 ± 5.4566 | 94.1612 ± 6.3579 | +1.4286 | 1/4/0 |
| 重入节点 | 96.4276 ± 6.5918 | 96.9344 ± 6.6127 | +0.5068 | 10/0/0 |
| 访问控制合约 | 94.6066 ± 1.6532 | 95.4075 ± 3.2189 | +0.8009 | 1/3/1 |
| 访问控制节点 | 96.1753 ± 6.2062 | 95.9716 ± 6.1255 | -0.2037 | 2/5/3 |

- last辅助差值依次为：重入合约+3.5417pp、重入节点+0.0741pp、访问控制合约−1.7325pp、访问控制节点+0.7999pp；完整均值与标准差在training_changes §62及报告，不用last替换best。重入节点best的10折方向一致、原始p=0.001953125；访问控制节点best下降、p=0.6055766163。两项合约收益集中在个别折，不能宣称普遍稳定改善。
- 全60项checkpoint身份、原节点预测、env_source排除和best/last重载证据通过；1986条任务折级有训练支持的新增canonical首轮消息梯度>0，94条仅留出关系梯度0并保留。定向175含于v2 1967，加旧223共2190 distinct tests通过，0失败/跳过。
- 控制器实际33548.08秒（9.32h）；fit内累计16202.67秒（4.50h，含验证/保存/重载/导出）；另verify208.23秒、interim432.69秒。启动前重复核验所有已有成功任务，存在二次增长的CPU/I/O校验开销，不是打印短日志造成。前31项定点审计只说明该样本范围，不将其计时外推成全批精确归因；本批冻结流程未更改。
- 峰值allocated/reserved=1893.47/2148MiB，整卡最低free18MiB；5项memory_tight，1项possible_memory_spill（R合约G3R fold2），仅为提醒，未发生OOM/数值/验收失败，不据此断言换出。
- 中间报告：prompt8_v1/batch1/reports/interim_A/REPORT_INTERIM_A.md，SHA 55933fa880ef9e4f26c6c1d502f4f959d469d0a8fc7aba734403d8a589443b51；15份CSV及JSON均由batch_records/interim_A.json绑定。详见dfg_v2/PROMPT8A_REPORT.md及training_changes §62.7起。
- 仍为单seed、共享训练数据的K折；全固定图前向，并非完全归纳测试，不直接与旧paper_kfold分数比较。人工512/111边表未填，Holm等待B，不归因到单独语义层，不修改争议标签。最终服务器显存充足是用户后续安排，尚未实际验收；需整批重跑，不混本机成绩。实施、复核与记录AI：Codex。

## 2026-10-27：Prompt 8A GitHub 结果归档（修改 AI：Codex）

按用户“将所有结果推送github”的要求，将Prompt8准备与Prompt8A阶段A的1721份文本结果/预测/日志/验收原样纳入Git；没有修改计算代码或原产物。270份.pt（约11.41GiB）与临时锁仍留本地，SHA及范围见docs/github_archive_prompt8a_2026-10-27.json，说明见同名.md。60项已完成，B未执行。只克隆仓库仍需另配输入图/token及模型资产才能重跑。


## 2026-10-27：DFG v2 Prompt 8B.0 性能修订完成（修改 AI：Codex）

- 仅新增/最小接入experiment编排与校验：完整验收缓存、可信父进程ticket、fit三次完整输入检查及保存/重载快速检查；原trainer/HGT/DDG/图/token/标签/folds/初值/早停/统计不改。用户批准增加DGL边索引副本内容比较，补足共享视图_version不联动的漏洞。
- 2个AC节点fold0证明（G0/G3R）与阶段A逐位一致：全部逐轮损失差0，best/last权重与inner/outer预测完全相同；不算正式训练。2108项v2＋223项旧回归通过，0失败/跳过；最终重新完整核验A的60/60通过，B仍0。
- 新证明进程100.26/136.50秒，旧A对应537.60/582.93秒；两者启动验收量不同，不能外推统一提速。真实缓存完整验收1.861秒→命中约2.2毫秒；新best保存均值0.443/0.549秒。旧函数计时缺失，报告明确代理与实测区别。
- 新独立prompt8b0_v1/stage_B_amendment.json及seal已封存，execution_authorized=false；原plan/seal/A结果不改。B暂作3–6小时工程预算，另留15–30分钟验收/报告（保守预留6–8小时），仍需独立授权。未跑B、未选G*，不自动push。
- 详见scripts/DFG/dfg_v2/PROMPT8B0_REPORT.md与training_changes §63。快速缓存有元数据局限，阶段结束仍做完整SHA；三份文档只追加。最终实验按用户安排在显存充足服务器整批运行，当前4GiB只是本机限制；服务器尚未实际验收，不混用本机成绩。


## 2026-10-28：Prompt 8B 阶段B授权与启动准备（修改 AI：Codex）

读取更新§4.1/8B并pull同步至220d258f284dacd52374ba95c7284f461005a23e。本轮明确授权原计划阶段B的G1R/G2R/G3共90项，独立stage_B_authorization.json绑定plan、seal、8B.0修订、中间报告receipt和用户请求原文；旧A授权与修订execution_authorized=false保持原样。准备记录prompt8b_v1/，冻结生产代码不改，先回归测试再原控制器逐任务独立进程串行；运行中只查进度/资源，不汇总F1。失败停止、不自动重试，不因分数挑折。

本节只登记启动，不代表90项完成。完成后按文档全量verify→inner_val select→summarize；A的60项只读复用，G*不看outer_test，额外seed即使触发也不执行。最终正式实验按用户安排在显存充足服务器整批运行，当前RTX3050 4GiB只是本机限制；服务器尚未实际验收，不混用本机成绩。


## 2026-10-28：DFG v2 Prompt 8B 完整结果与选型（修改 AI：Codex）

- 阶段B90项全成功，复用A60项，完整150/150通过完整验收，0失败、0重试；原计算代码298文件SHA及图/标签/特征/划分/初始化/超参保持不变。
- 预注册主对比仍为G3R−G0的best BF1，四任务差值+1.4286/+0.5068/+0.8009/−0.2037pp；重入节点该家族Holm p=.0078125，AC节点未改善。
- 内层验证选出G*=G2R（局部DDG+状态读写及显式REV），内层相对G0+0.831863pp；满足补seed条件但没有执行授权，本轮不继续训练。
- best主终点BF1均值（百分数，四任务顺序为重入合约/重入节点/AC合约/AC节点）：G0=92.7326/96.4276/94.6066/96.1753；G2R=94.8490/96.9420/95.4075/95.6227。重入节点10折全提升，AC节点反而下降；不能宣称全面有效。其余剖面与标准差、MF1/P/R、last、OOF、配对统计及敏感性表全部保留。
- 本轮为dfg-v2-nested-v1：inner_train更新参数，inner_val选择best和全局G*，outer_test只作结束评分；完整固定任务图前向，节点按原HCG节点计分且排除env_source。不是旧paper_kfold的CV validation，也不是新的外部独立数据测试。G0是作者下载图在本地冻结协议下训练所得基线，非论文表格原始数字。 last在部分任务与best方向相反，不替换预定主终点；G2R未解决AC buggy_18/26主要错误。
- 测试2331通过（2108v2+223旧，0失败/跳过）；150项best/last重载一致。独立复算及A历史结果不变性核验通过；新增Holm家族、方向消融和G*机制表属于完整报告预定内容。人工依赖边512/111条抽查仍未填，不宣称完整语义或泛化已验证。
- B执行4.614小时，fit内部2.429小时另计口径；峰值allocated/reserved1829.03/2026MiB、最低整卡free53MiB，7项memory_tight，均无OOM/失败。最终核验/报告耗时详见command.json，不混作额外训练。
- 报告scripts/DFG/dfg_v2/PROMPT8B_REPORT.md；完整CSV/JSON在scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/reports/final/。详细记录training_changes§64、PROGRESS已追加；本地提交，尚未push，无新seed/其他类别/服务器迁移。
- 最终实验将按用户安排在显存充足的服务器整批运行；当前RTX3050 4GiB只约束本机。服务器尚未部署或实际验收，后续不能混合本机与服务器成绩。


### 2026-10-28 Prompt 8B GitHub结果归档（Codex）

用户要求推送GitHub。沿用阶段A方式，归档新增90个正式结果、完整150结果报告、预测/收据及8B.0与8B验收文本，原产物不变。共2811个文件（831.12 MiB）；两个超限JSON保留原文件并提供SHA一致的gzip副本；权重与输入图仍在本地。详见 docs/github_archive_prompt8b_2026-10-28.md / .json。生产代码没有改动，训练无需重跑。推送目标仅origin/dfg-v2，使用此前Windows Git＋WSL gh方式；最终推送是否成功以实时远端SHA核验为准。


## 2026-10-28/29：DFG v2 Prompt 8C完成（修改AI：Codex）


本轮新增diagnostics8c十模块、README、8组测试和PROMPT8C_REPORT.md。生产DDG/HGT/tokenizer/训练器、冻结图/标签/折/150结果/plan/seal/selection不改。三项已批准选择：100节点orig/C1/C2与50合约orig分开；Wilson仅P/R；G0P保留G0节点并限定逐层分母证明。

150结果验收和独立重评分全部通过。80CSV固定Git对象一致，128源码及19746节点身份核验通过。疑似缺失正例Rbuggy18=214，ACbuggy18/26=93/42；附带作者标注还有高行号，不能推断作者遇CSV重叠停止。参考脚本424项比较422一致，两处buggy35注释正则计数差异已解释。C1/C2仅诊断假设，不改真值。

最重要发现：不学习的名称规则在C1已有约99% BF1。100/100best名称置换前向完成，另1项不改名门槛与归档逐位一致；训练0次。R G0 BF1 96.43→35.61，G3R96.93→38.49；AC G0 96.18→10.70，G3R95.97→10.53，主要增加漏报。测试时置换含分布变化，不能宣称纯因果或部署性能。非SolidiFI分类/概率全部不变；D原指标80项与B完全一致。

两类buggy22/36均精确重复且跨折；38近重复对/22连通簇。实际图没有独立modifier调用节点，不能称不存在节点为孤立；结构两跳不等于守卫执行。G0P20fit计划/seal/授权模板及CPU分母证明已准备，execution_authorized=false；没有训练、没有把G0P接入训练CLI。当前折不改，未来分组折只写方案。

最终2455测试通过（2232v2+223旧，0失败/跳过），8/29条既有弃用警告。3480受保护引用和298历史计算SHA一致。100worker内部合计2324.03s，最大allocated/reserved572.07/588MiB，0正式失败/重试。开发期诊断接口修复和验证记录详见training_changes§65；产物在scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1/。

最终正式实验按用户安排在显存充足服务器整批运行；当前RTX3050 4GiB只约束本机。服务器尚未部署/实测，不混合两地成绩。512/111条人工依赖审查仍未完成。仅本地提交，未push，停在E授权点，不自动开始新seed/其余五类/新关系。


## 2026-10-29：DFG v2 Prompt 8D完成（修改AI：Codex）

新增诊断与候选分组基准旁路，原算法/图/标签/历史折/150结果/8C不改。按用户批准完成300次best推断（全量同长标记名、匹配标记子集、匹配普通名，各100）；0正式训练。下表为orig节点BF1等权折均值（%），不是新特征重训成绩。

|任务|剖面|原特征|8C idN|B全量同长|B匹配标记|C匹配普通名|
|---|---|---:|---:|---:|---:|---:|
|重入节点|G0|96.4276|35.6136|60.1317|95.3652|96.3192|
|重入节点|G3R|96.9344|38.4866|67.7559|95.8106|96.9344|
|访问控制节点|G0|96.1753|10.7029|90.1299|95.9495|96.1753|
|访问控制节点|G3R|95.9716|10.5259|93.3903|95.7184|95.9526|

**正式训练前的阻断项：只把注入名改为idN仍保留可识别标记。** 原文本中idN为0；改名后无学习idN规则在SolidiFI C2上AC99.983625、R99.977786 BF1。已记录证据，未静默换方案或修改F seal；必须先征求用户对普通/注入名称一致处理等替代策略的意见。C1/C2本身也只是诊断假设。


A/D/E已完成；没有证据认定作者附带行列表来自buggy24。完整P/R/翻转/概率、独立复核及资源见PROMPT8D_REPORT。匹配覆盖不同，不作纯因果解读。

最终2643测试通过（2420v2+223旧），0失败/错误/跳过，8/29条既有弃用警告。4071历史引用和298计算文件SHA一致，三份文档旧正文只追加。F170计划、30个分组嵌套折、51490行特征复核与恒等视图证明已准备，execution_authorized=false。两分支各1CPU epoch共2次验收optimizer更新，正式fit=0；scheduler地址比较首份失败保留，数值复核未重训。详细结果/选择/命令见PROMPT8D_REPORT.md、training_changes§66及README。
最终正式实验将按用户安排在显存充足服务器整批运行，当前RTX3050 4GiB只是本机限制；服务器未部署/实测，不混合两地成绩。当前停在F，不执行170fit、加seed或扩展五类。512/111人工依赖核验仍未完成。本轮本地提交，不push。


### 2026-10-29 Prompt 8D GitHub结果归档（Codex）

按用户推送请求，在5f31a66代码/报告提交之后，追加1176个Prompt8D文本结果和证据文件（约431.50MiB），覆盖300推断、汇总、审计、测试、候选分组计划及idN命名风险；文件清单见docs/github_archive_prompt8d_2026-10-29.json，说明见同名.md。原文件逐字节保留，4个CPU验收checkpoint和14个特征NPZ留在本地，不修改旧seal/图/标签或重跑模型。三份文档只追加。本次WSL Git直接连接GitHub已成功，正常推送dfg-v2，最终以本地/远端SHA核验一致为完成依据。F170仍未授权，命名替代方案尚需讨论。最终实验使用显存充足服务器的安排保持，当前本机限制与服务器结果不混用。


## 2026-10-29：DFG v2 Prompt 8E 验收执行并按失败门槛停止（修改 AI：Codex）

新增 benchmark_v2 五个命名/探针/验收旁路模块、两组测试及 PROMPT8E_REPORT.md。原 DDG、HGT、tokenizer、训练器、图/标签/特征/折/旧结果不改。用户批准仅在内存 code 改写副本上复用分析器作事实与投影验收；正式图不改，临时结果丢弃。旧 8D/F 在新目录单独标记 superseded，原 plan/seal/特征保留。

128 源码、80 SolidiFI 文件、4807 个文件内标记名映射到同角色真实名；872 个不同替换拼写均有普通代码证据，语法/AST 拓扑检查通过。80 文件×合约/节点两粒度共160项 L1/L2/L3 证据/端点核验全部通过。

**命名门槛没有通过，不能称新基准已准备完可训练。** N-real P2 的 SolidiFI pooled BF1：重入 orig/C1=64.7050/67.8373，比全正低10.3122/8.6960pp；访问控制=67.7445/69.4994，比全正高9.4670/9.3613pp，超过5pp门槛。P3 N-real AUC=0.643159>0.60（原名0.999430、idN0.998474）。映射、协议事先封存，没有换种子/调名字/门槛后重测。指标已独立重算。

保存 acceptance_decision/seal 和 execution_authorized=false 模板；没有生成新的NPZ视图或可运行170计划，也未执行后续特征装配/恒等验收、N-anon或正式训练。P3有15次CPU逻辑回归诊断，HGT正式fit=0。不能把验收决定的seal当训练plan seal。

2678个唯一测试通过（2455 v2，其中8项验收测试在全套后单独执行；223旧回归），0失败/跳过，8/29条既有弃用警告。337绑定引用及8B.0修订后的298历史计算文件SHA一致。详细选择、限制、命令、结果见 training_changes §67 和 PROMPT8E_REPORT.md。

最终正式实验按用户安排在显存充足服务器运行；当前 RTX3050 4GiB 仅限制本机开发，服务器尚未实际验收，两地结果不混报。本轮本地提交、不自动push。后续先讨论新的命名协议/研究口径，不自动为追求过门槛反复试验。


### 2026-10-29 Prompt 8E GitHub 结果归档（修改 AI：Codex）

按用户推送请求，在 96aa7420 代码/报告提交之后，追加归档全部 64 个 Prompt 8E JSON/日志结果（97.11 MiB），包括名称映射、160 项语义核验、探针、验收决定和测试证据。清单与说明见 docs/github_archive_prompt8e_2026-10-29.{json,md}。原结果和 seal 字节不变；开发期失败检查及更正、推送前历史收据一并保留。当前命名门槛仍未通过，正式 HGT 训练 0 次，不自动启动新计划。使用 WSL Git 正常推送 origin/dfg-v2，最终以本地/远端 SHA 一致核验。最终服务器实验安排不变。


## 2026-10-29：DFG v2 Prompt 8F 绑定与投影核验完成，全量计划阻断（修改 AI：Codex）

- 新增声明绑定匿名化、内存 code 副本核验及停止入口（benchmark_v2/anon_binding.py、anon_parity.py、prepare_anon.py），新增35项测试、README和PROMPT8F_REPORT.md。原DDG/HGT/tokenizer/训练器、图/标签/折及旧产物不改。
- 两项用户批准：51处旧式构造函数与所属合约共用匿名名；存在整文件回退时先完成核验，阻止全量探针/特征/可运行170-fit计划封存。不能保留原名混入N-anon，也不能删掉回退样本。
- 256个类别/文件/源码身份中，97个绑定可改写（4025个声明级匿名映射、9594处替换），159个整文件回退；最终87个通过依赖/投影核验，另10个有合成节点来源歧义。四任务384个文件引用对应132通过、233回退、19投影阻断。通过子集不代表完整N-anon。
- 主要回退涉及接口/继承覆盖、重载、成员绑定、assembly和版本证据。10个投影阻断文件涉及36个end_if/end_loop合成节点：同文本对应不同声明，不能按最近行号猜映射。没有改原节点或删除原CFG边。
- 新检查器修正通用反向替换误把analysis_path中的v2当作匿名名的问题，只恢复明确声明字段；前两版检查记录和源码摘要保留。最终2490项v2＋223项旧回归＝2713通过，0失败/错误/跳过。首次测试临时父目录遗漏产生的setup errors也保留。
- acceptance_decision/seal为blocked_by_binding_or_semantic_gate，不是训练计划。P2/P3、特征NPZ、模型装配、新170-fit计划均未执行；本轮正式训练及诊断分类器拟合均0。未做solc编译验证。
- 清理本轮专用测试临时树和一个被正式清单取代的开发汇总，共约205.03MiB；重要日志、正式结果、旧实验和用户数据保留。产物仍在WSL的prompt8f_v1，不另写C盘。
- 详情见PROMPT8F_REPORT.md、PROGRESS.md和training_changes §68；三份旧文仅追加。先讨论同文件接口/覆盖绑定与合成节点来源的可靠解决办法，不自动扩展或重训。本轮本地提交，不自动push。
- **最终实验按用户安排在显存充足服务器整批运行；本机RTX3050 4GiB仅为开发限制。** 服务器尚未部署/实测，本轮停止是正确性门槛，与显存不足无关。


### 2026-10-29 Prompt 8F GitHub 代码与结果归档（修改 AI：Codex）

按用户“推送github”要求，在9ab9080a代码/报告提交之后追加归档322个Prompt8F JSON、日志和实现快照（18097340字节，约17.26MiB），含全量命名/投影/依赖核验、开发期失败及更正、测试、清理、最终停止决定和本地提交收据。清单与说明见docs/github_archive_prompt8f_2026-10-29.{json,md}。原结果/seal逐字节保持，其他阶段未跟踪数据不纳入；没有新权重或NPZ。历史pushed=false表示当时未推送，不改历史收据。

UTF-8/JSON、常见凭据模式、来源/最终实现SHA及旧8E文件核验通过；暂存范围与blob须逐项对照清单。实施阶段2713测试通过，本次不重跑。状态仍blocked_by_binding_or_semantic_gate（87通过、159绑定回退、10投影阻断），没有启动170-fit或解除门槛。三文档仅追加，正常推送origin/dfg-v2，最后核对本地/实时远端SHA一致。最终显存充足服务器实验安排不变。


## 2026-10-29/30：DFG v2 Prompt 8G准备完成，170项计划待授权（修改 AI：Codex）

- 按更新§4.1/8G新增六个benchmark_v2匿名化/语义/探针/特征/计划模块、六组83项测试、报告与README。用户明确指定由8F声明绑定改为文件内AST identifier拼写双射；不是补齐Solidity绑定器。旧DDG/HGT/tokenizer/训练、图/标签/fold/结果/8F代码与seal不改。
- 全256源码身份完成17159个文件内拼写映射、66213处identifier替换，0回退；384任务×文件的归档/原文/改名L1/L2/L3事实、证据、投影全部一致；此前36个合成节点歧义全部消除，未按最近行号猜来源。
- P2四项门槛通过；P3 AUC=0.52610144≤0.60，角色子集也完整记录，单类别角色不捏造AUC。关键词预测逐节点不变，SolidiFI AC原标签关键词BF1仍95.6238%，因此AC节点继续只作描述，不声称已消除全部捷径。P3为5次CPU逻辑回归诊断，正式HGT训练0。
- 51490行原token逐位复现，48527行匿名token改变；新旧共8个NPZ，env_source不变。最终model_proof_attempt2含20项剖面检查/28次CPU eval，四G0恒等logits逐位一致，全部参数不变。中断model_proof保留3任务旧收据/日志，新目录完整重验并确认旧三任务一致，不覆盖或冒称续训。
- plan/plan.json及seal、false授权模板已封存：170项=150五剖面+20节点G0P；继承8D grouped-nested分组折/标签选项/规则。标签、seed、位置尚未选择；旧CLI尚不支持新特征/标签mask/折绑定，后续须先接入验收并创建新零步初值。不是可直接启动的训练命令。历史本机估算约8.2791小时另加编排开销，非匿名特征实测。
- 最终2573v2+223旧回归=2796唯一测试通过，0失败/跳过；9/29条DGL/NetworkX弃用警告。690旧Python及4文档追加前SHA一致，322旧8F归档不变；三文档只追加。只清理本轮测试临时数据337.71MiB，重要日志/正式特征/用户文件保留。
- 39个enum_value、75个yul_identifier按预定规则不改，外部成员改名也不保证ABI；“全identifier改名”不等于全部语言名字、编译等价或完整DDG语义证明。人工512/111依赖审查仍待完成，无新HGT F1。
- 详见scripts/DFG/dfg_v2/PROMPT8G_REPORT.md、PROGRESS.md和training_changes§69；产物prompt8g_v1/，计划SHA be66792cbd43978588761393f354f1df89f1a181104bbee5d567252aae57536a。本轮本地提交，不自动push，停在标签/seed/位置授权点。
- **最终实验按用户安排在显存充足服务器整批运行；当前RTX3050 4GiB仅为本机开发限制。** 服务器尚未实际配置/验收，不混合本机与服务器结果；当前等待执行授权，与显存不足无关。


### 2026-10-30 Prompt 8G GitHub代码与结果归档（修改 AI：Codex）

按用户“推送github”请求，在68e6ce12实现提交之后，追加归档349份Prompt8G文本产物，118831490字节（约113.33MiB），含全部命名/语义/探针/特征清单、完成与中断验收、170项false授权计划、测试/清理/独立核验记录；原文件与seal字节不变。8个NPZ（约2.84MiB）沿用之前方式保留本地，路径/SHA在docs/github_archive_prompt8g_2026-10-30.json，同名.md说明范围。

归档前重新核验全部来源、计划及语义门槛、代码SHA、322份旧8F归档、UTF-8/JSON/常见凭据模式；暂存blob与清单逐项比对。本次不重跑2796测试或模型，正式HGT fit仍0，170计划尚未授权，不能将归档理解为开始训练。历史pushed=false收据保留其原始时间含义。

WSL直连DNS失败，使用Windows Git＋现有Windows代理＋WSL gh凭据助手正常连接，远端62b73866为本地祖先；未改持久配置、未受分支保护拒绝，不force push，目标仅origin/dfg-v2。推送完成以实时远端SHA与本地HEAD一致核验。最终显存充足服务器实验安排不变。


## 2026-10-30：Prompt 8H 执行器与开训验收（修改 AI：Codex；运行中记录）

- 从 dfg-v2@39801a87 开始；读取更新的共享上下文和8H。用户在文档明确授权：L-audit、seed=[1]、本机local_dev_v1、170项。新批次为 scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1，旧8G准备计划、旧图/标签/特征与seal不改。
- 新增benchmark_v2执行/监督/绑定/输入保护/归档验收/统计模块；原训练器、HGT和tokenizer未修改。节点主监督用C1且C2_include=false不进入loss、best选择和主指标；原标签辅助分数覆盖全部原HCG节点。屏蔽只作用于直接监督，保留完整图消息传播。
- 用户批准的唯一方案调整：旧8B.0的全目录运行清单不能接受新Python文件，因此采用只读归档核验，逐一校验历史绑定源码SHA、输入、计划/修订和收据；新代码单独绑定，旧训练入口及旧seal不放宽。已核验150个历史结果。
- 真实重入节点旧输入CPU两路径各2轮逐位一致；完整GPU历史复验best epoch和全部分类一致。真实C1/C2掩码梯度检查、G0P一轮CPU冒烟及按层分母证明通过；29项定向测试通过。首次CPU检查因缺少import失败（新分支零步），修复后在新目录重验；测试临时父目录漏建已修正，均无正式训练成绩冒用。
- 正在运行全套回归并准备170份新零步初值。随后先运行重入合约fold0 G0、重入节点fold0 G3R，作为正式结果复用，再按冻结顺序完成全矩阵；每项独立进程，失败停止，运行期间不汇总F1。此条不代表170项已完成，后续追加最终数量和结果。
- **最终实验按用户安排在显存充足服务器运行；本机RTX3050 4GiB只是当前开发资源限制。** 本轮170项明确授权在本机执行，服务器尚未部署/实测；不将两地成绩混合。本轮产物留WSL，不写C盘；只清理本轮可确认的测试临时数据，正式收据/权重/必要日志保留。


### 2026-10-30 Prompt 8H CPU准备优化补充（修改 AI：Codex）

用户新增批准：先证明参数逐位一致，再复用从未训练的CPU剖面结构。新增benchmark_v2/initial_preparation.py，仅缓存G1R/G2R/G3R/G3结构；每折G0仍按原constructor seed新建，所有增强参数通过原initialize_family完整重写，G0P保持逐折新建。正式worker仍独立进程、各自封存零步初值、恢复fit seed。以第一轮已保存的逐折新建初值作只读参照；比较证据保存acceptance/structure_reuse.json，通过后才能封存第三次准备。旧两次未封存准备与停止原因保留，均不是正式fit失败或epoch续训。

另修正新执行器锁路径为旧入口共用的.training.lock，回归验证能阻止跨协议同时训练。新增测试目前41通过，含原30项与11项结构复用测试；全套先前2602 v2+223旧回归已通过。复用测试首次错误使用不同原节点集合的独立fixture，按原已有同一HCG增强fixture修正，断言未放宽。正式170fit仍未开始，后续追加状态；最终服务器安排不变。


Prompt 8H CPU准备补充验收（Codex）：真实3折×5剖面共15项、5562张量/74068122参数值与逐折新建初值逐位一致，acceptance/structure_reuse.json通过。已开始prepared_attempt3最终准备，正式170fit尚未开始。该优化仅CPU结构装配，不改正式训练计算。


Prompt 8H最终回归补充（Codex）：2614 v2＋223旧回归＝2837唯一测试通过，0失败/跳过；703个原Python SHA不变（起始707项含4个md）。只清理本轮两个pytest临时树共444.72MiB，保留正式产物与必要证据。此时仍处最终初值准备，正式训练数量另行追加。


Prompt 8H计划已封存并启动正式试点（Codex）：170份初值/30折全部完成；新plan SHA cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c。六项开训验收通过。正在执行重入合约fold0 G0，随后重入节点fold0 G3R；通过后按计划串行完成170，任一失败停止并保留。源码/超参/数据已冻结，运行中不改代码或提交Git。正式完成数与结果另行追加。


### 2026-10-30 Prompt 8H试点后缓存阻断（修改 AI：Codex）

首个重入合约fold0 G0完成19轮，best第12轮、last第19轮；checkpoint/预测重载及重新执行完整verify_one均通过。正式完成1/170，第二个试点及169项未启动。控制器缓存失败并停止：旧cache读了采样仍运行时的result.json资源SHA，新执行器final_result.json与完整采样日志SHA一致；这是新增接口缺陷，非DDG/模型或OOM。最小free400MiB、allocated峰1230.84MiB、reserved1410MiB。

已保留现场和cache_failure_diagnosis.json，未修改封存代码/旧seal，未自动重训。已请求批准仅做8H final_result缓存适配并新增运行版本修订，补回归后复用首个fit继续169。当前等待确认，不能称完整8H完成；PROMPT8H_REPORT已明确状态与测试缺口。最终显存充足服务器安排保持，本次停止与本机显存不足无关。


### 2026-10-30 Prompt 8H缓存修复获批（修改 AI：Codex）

用户批准仅修复缓存接入并继续剩余169次。新增8H专用acceptance_cache/runtime_amendment，读取final_result而不更改中间result或原缓存，严格保留采样原文SHA/缓存库存校验。execution仅调整缓存导入与修订元数据，数值训练不改；旧plan/seal和首个成功fit保留，独立修订封存后复用首个结果。真实35依赖SHA与目录不变证明已通过；96定向/相关测试、223旧回归通过，完整v2回归进行中。批准与实施证据在cache_fix_v1，详细见training_changes§70.11。正式恢复尚待这些检查完成，最终服务器安排不变。


### 2026-10-30 Prompt 8H 缓存修复验收通过、获批恢复（修改 AI：Codex）

用户已明确批准“修复缓存接入并继续剩余169次”。定向/相关96通过（包含在全量内），v2全量2632通过、原项目223通过，共2855项唯一测试，0失败/跳过。警告分别为4/9/29条既有依赖/弃用警告，完整日志与SHA保存在cache_fix_v1/equivalence_proof.json。真实首个fit完整verify_one、final_result依赖缓存创建及缓存命中全部通过，new_fits=0；没有重训或修改该结果。

独立修订runtime_cache_fix_v1.json SHA：7a1e4ed3a280a40b881332ba0abbd01a5c9e5e3813c1c89c2b6660f4b37c0b22。原plan SHA仍为cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c，原seal、缓存及停止现场保留。修订仅允许execution.py五处接入/审计调整和两个新模块；数值循环及原模型/数据/初值未变。旧成功收据仅限清单中首个结果可没有新修订字段，后续fit必须绑定修订。

接下来串行执行pilots，再all，最后reporting。首个重入合约fold0 G0复用；第二试点重入节点fold0 G3R通过后进入剩余矩阵。总目标170，恢复时已完成1，不将恢复称为完成169。新控制器日志/状态使用resume_v1名称，旧停止记录不覆盖；失败停止且不自动重试。完整验收前只记录进度，不汇总F1。运行期间冻结Python文件，不自动push。

最终实验按用户安排在显存充足的服务器执行，本批仍按明确授权在本机local_dev_v1运行，不混用两个环境结果。


Prompt 8H正式恢复进度（Codex，2026-10-30）：独立修订和代码提交00c731e6生效；原首个成功fit完整复用，第二试点重入节点fold0 G3R通过，acceptance/pilots.json已封存。控制器已进入全部170项串行矩阵，目前2项完成；这是启动进度记录，不是最终结果。旧orchestration_status保留失败历史，新状态为orchestration_resume_v1_status.json。另清理本批cache_fix_v1/_test_tmp可重建临时树211615457字节（约201.81MiB），未跟随600个符号链接，不删除正式产物；cleanup_test_tmp.json留证。运行期无计算源码修改，尚未push。


### 2026-10-30 Prompt 8H 外部中断后的显式恢复准备（修改 AI：Codex）

用户在获知训练中断后明确要求“继续训练”。已完成71/170（重入合约25、重入节点46）全部重新完整verify_one通过；第72项重入节点fold7/G3的attempt_001停在第32轮，无成功receipt。Windows有约80分钟睡眠记录，末次采样仍有984MiB空闲；未找到OOM/Python异常/明确退出码，终止原因尚不确定，不将睡眠或显存认定为已证实根因。

现有执行器硬编码attempt_001并拒绝任何未完成尝试。为落实本次明确恢复指令，新增retry.py，最小调整execution的尝试选择、reporting的唯一成功收据定位、acceptance_cache依赖和runtime_amendment的修订链。原训练数值try主体、construct/binding_parts/prepared的AST保持一致；原trainer/DDG/HGT/tokenizer/特征/标签/折和初值不改。旧attempt_001及全部路径不迁移、不覆盖；仅指定失败任务可从封存零步初值重跑为attempt_002。已有71个成功结果复用，剩余99个正式结果待生成；不是从第32轮续训，也不是新seed。

resume_v2保留用户授权、71成功收据、全部中断文件SHA、4份修改前源码与精确编辑清单。将建立独立runtime_resume_v2.json与seal，引用原plan和旧cache修订，不重签旧文件。新尝试一旦再失败仍立即停止，无自动第三次尝试。80项定向测试通过，全套回归进行中；本条尚不是恢复训练已启动声明。最终显存充足服务器安排保持，本轮仍为已授权的本机批次。


Prompt 8H显式恢复验收完成（Codex，2026-10-30）：80项定向测试已含于2653项v2全量，原回归223项，总2876唯一通过，0失败/跳过；警告分别4/9/29条既有依赖警告。原71个成功结果完整核验通过；重试初值SHA和tensor digest匹配、optimizer_steps=0、原fit_seed=1010007，真实旧结果的新修订缓存创建/命中通过。runtime_resume_v2.json独立封存，SHA f18dd07d04d4cc00e5a232818a65febe6ea4d413e4e8e81d044504ae2e1d96b4；旧plan/cache修订及其seal未改。新增21项测试确保只有被授权的002可重跑，训练数值try主体和构造/监督绑定函数AST不变。即将启动独立会话控制器，先复用71，再重跑第72项与后续任务；不是已完成99次的声明。实际进度见orchestration_resume_v2_status.json和full_matrix_resume_v2.log。


Prompt 8H恢复控制器补记（Codex，2026-10-30）：本地提交02db061c后，首次恢复控制器在只读验收到16/170时退出；新fit尚未启动，attempt_002.start不存在。原因是我同时清理已结束pytest的临时树，旧_code_refs会先rglob遍历artifacts再过滤，遇到已删除目录触发FileNotFoundError。这是操作并发冲突，不是训练数值/缓存错误；已保留full_matrix_resume_v2.log及resume_v2/controller_scan_race.json，71成功receipt和全部中断文件SHA重新核对未变，运行版本核验通过。

清理仅涉及resume_v2/_test_tmp共211184809字节（约201.40MiB），599符号链接仅删除链接、未跟随目标，正式证据和用户文件均保留。清理已结束，后续运行期间不再删除任何目录。原runtime_resume_v2修订、计划和计算源码完全不变；根据本次“继续训练”授权重新执行只读验收并继续尚未消耗的一次attempt_002，不自动重试任何新失败fit。独立后台进程新日志/状态为orchestration_resume_v3_status.json、full_matrix_resume_v3.log，原v2停止现场保留。此处v3仅表示控制器启动记录，训练计算版本仍为runtime_resume_v2。


Prompt 8H已实际恢复训练（Codex，2026-10-30）：orchestration_resume_v3控制器完成71份历史结果复用验收后，已启动第72项reentrancy_node/fold7/seed1/G3，worker PID 1333914，输出attempt_002；新start绑定runtime_resume_v2，仍使用原fit_seed=1010007。原attempt_001及其32轮历史、best.pt和日志保留原路径。后台supervisor PID 1333862采用独立会话；后续99项按原矩阵顺序串行、每项独立进程，失败停止。新计算接入已提交本地02db061c，未push；训练期间不修改代码、不再清理目录。此条只确认恢复，不代表170项完成，最终统计仍须全部验收后生成。


### 2026-10-31 Prompt 8H 全部完成（修改 AI：Codex）

Prompt 8H本批已完成170/170并生成完整报告，重入/访问控制合约各25项、节点各60项；全部成功收据与16份汇总文件SHA复核通过，当前没有训练进程。71项历史成功结果复用，99项后续完成；获准的fold7/G3 attempt_002成功，原中断尝试保留。训练计算及原封存计划未变。

L-audit主口径、best等权折均值BF1：G0→G3R，重入合约93.6807→95.0159、访问控制合约91.0199→93.0075、重入节点98.0885→99.1246、访问控制节点97.7105→98.3536。节点分别10/10折提升、9升1平。预注册主终点重入节点+1.0361个百分点，Holm p=0.0078125；仅单seed，折统计有相关性。inner验证选出的G*为G3，不用outer结果改选型。访问控制关键词pooled BF1仍99.5114，高于G3R的98.3736；nonSolidiFI仍18/20正例漏报，不能宣称数据捷径或真实样本问题已解决。

这是匿名特征、分组nested CV、L-audit诊断视图结果，非论文同协议数字、非独立外部测试；节点仍按HCG节点计分。best/last、原标签辅助与pooled分别保存。报告：scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/reports/REPORT.md；详录见training_changes§70.14。完成核验记录final_review_2026-10-31.json。未启动额外训练或push。

最终实验仍计划使用显存充足的服务器；当前批次是在本机RTX3050 4GiB上运行，显存限制属于本地开发条件。恢复前2876项唯一测试通过，完成后仅文档追加和SHA核验，未重跑整套训练。


### 2026-10-31 Prompt 8H GitHub archive (Codex)

User authorized pushing the completed work. Archive all 4959 text result
and evidence files, including 170 successful fits, together with the three
implementation/fix commits. Two oversized reports have verified lossless
gzip copies; 542 .pt files and one runtime lock remain local. Original
artifacts and seals are unchanged. Scope, SHA inventory and binary
limitations: docs/github_archive_prompt8h_2026-10-31.md and adjacent JSON.
Use existing Windows Git/proxy plus WSL credentials for a normal push to
origin/dfg-v2, then verify remote HEAD. No extra training, deletion or model
changes. Final sufficient-VRAM server plans remain; this batch is local.


### 2026-11-01 NodeSem NS-P0完成（修改 AI：Codex）

在node-sem分支完成只读侦察，已读更新后的设计介绍和5.1共享上下文。新增scripts/node_sem/RECON.md、recon.json及5份recon脚本，追加PROGRESS与训练变化§71；原DFG/HGT/tokenizer和所有冻结输入/结果未修改。

60份G0/G3R收据、2137个不同文件SHA通过；600维token载体、17个适配Linear替换后的注册/binding、G0零层节点和合约前向反向均通过。四任务原节点匿名文本全覆盖。已有回归2653+223=2876通过，0失败/跳过；按用户批准用探针断言完成NS-P0自检，专用测试目录留NS-P1。

下一阶段先澄清：结构性label只作身份的边界、M2标量变量名来自已封存L1 sidecar、普通条件支配不能等同守卫通过。仅提出建议，未自行替换方案。8H原plan/seal保留，实际运行版本按此前获批runtime_resume_v2核对，execution.load通过。自动审批拒绝torch.load后改用SHA/静态ZIP头核验，未重载历史模型或独立重算tensor digest。

最终实验按用户安排使用显存充足的服务器；当前RTX3050 4GiB限制只是本机开发条件。本轮没有新的真实训练、下载或安装；停止于NS-P0，本地提交但不自动push。详见RECON与training_changes§71。


### 2026-11-01 NodeSem NS-P1 完成（修改 AI：Codex）

在node-sem、27ea6617输入上完成r4的NS-P1。新增逻辑均在scripts/node_sem：FeatureSpec、S0/S1配置、严格载体、模型共享EmbeddingBag、适配器、初值、SHA限制加载、独立执行器及CPU等价验收。原DFG/HGT/tokenizer、图/特征/标签/划分、8H计划和结果均未改。S0保留原512维Linear；S1仅一张V=32100、64维共享表，逐类型Linear，不提前实现M1/M2、LLM或多模态融合。

用户批准SHA边界内torch.load后，60/60历史零步初值独立张量摘要通过；60/60历史S0收据完整只读验收通过。真实四任务16组载体通过。两个指定任务（重入节点fold0/G3R、访问控制合约fold0/G0）各旧/新入口2轮，共4次CPU检查：初值、输入、每轮损失、最终/best/last参数、Adam、scheduler数值和预测一致；不是新增正式成绩。

批准的验收调整均有记录：扰动测试仅在临时manifest重绑图指纹，生产校验保持；scheduler的绑定方法核验同类同实现，其余零容差。首组比较曾因Python方法对象身份停止；旧seal/failure/重入产物保留，独立acceptance_revision1复核后只补访问控制，没有重训重入。另修复两个父目录创建接入问题并补回归。详细选择、证据与命令见training_changes§72及scripts/node_sem/NS_P1_REPORT.md。

最终184 NodeSem＋2653 DFG v2＋223原回归＝3060项唯一通过，0失败/跳过。原/新CPU构造秒：重入15.969/30.813、访问控制15.040/31.461。机器证据见artifacts/ns_p1_equivalence/equivalence.json；现行验收计划在acceptance_revision1/batch，旧batch仅归档。二进制载体/短检查权重保留本地，源码与文本验收记录随本轮本地提交；未自动push。

最终实验按用户安排在显存充足服务器执行；目前RTX3050 4GiB仅是本机开发限制，服务器尚未部署实测。尚无S1正式效果或GPU显存结论。停止在NS-P1，不自动推进NS-P2。


### 2026-11-01 NodeSem NS-P1b完成（修改 AI：Codex）

按r5修正两点：显式8模块训练runtime，execute严格核当前代码、verify核历史启动/收据/产物；新计划v2，旧v1只读保留，S0仍核8H有效运行版本。S1改为N(0,1)共享EmbeddingBag＋仅作用非空行的共享LayerNorm(64)，仅增加128参数；S0原路径不变。代码与新产物全部在scripts/node_sem，旧DFG/作者代码/图/标签/折/8H及NS-P1产物未改。

3074项测试通过。重入节点fold0/G3R的r5 h0逐类型std 0.433–0.540，通过尺度门槛；S0旧/新各两轮CPU严格等价，S1单轮CPU的37个输入参数张量梯度有限且非零、checkpoint重载通过。合计3次CPU fit/5轮，非正式结果。60个旧S0结果只读核验通过，原118个产物SHA未改。

用户批准保留冻结装配中的标签完整性读取，诊断统计与门槛不使用标签/评分，详见diagnostic_scope_approval.json。r4输入小但第一层归一化后std也接近1，本轮不据此断言其无法学习或宣称S1提升。完整实施/选择见training_changes§73、PROGRESS及NS_P1B_REPORT.md。新空行单测的矩阵形状舍入问题已修，未放宽逐位断言。

最终实验按用户安排使用显存充足服务器，本机RTX3050 4GiB仅为当前开发限制，未部署实测服务器。本轮仅本地NS-P1b提交，不自动push或推进NS-P2；权重和NPZ留本地WSL，代码与文本证据提交。


### 2026-11-01 NodeSem NS-P2 完成（2026-11-02 NS-P2b 校正，修改 AI：Codex）

本节原中文损坏，已归档原始字节后替换；该节前后内容保持不变。实现 AST 节点文本、独立 CodeT5 离线编码、F3 全集 manifest 对 F0/F3 的载体超集对齐与 S2 配置。代码、测试、资产清单与说明均在 scripts/node_sem；原 DFG/HGT、标签、折和 8H 产物未改。

用户已批准创建独立 nodesem，实际 Python 3.10.21/torch 2.6.0+cu118/transformers 4.46.3，mando 不变。安装时涉及的 user-site 三包已按原版本恢复，后续 python -s/PYTHONNOUSERSITE=1；官方资产、revision 与 SHA 清单和副作用记录完整保留。

四任务×原名/匿名共 8 组，F3 行数为 12223/7892/18610/13693；共 104836 行向量，0 截取回退。两遍独立编码逐位一致，max error=0，编码墙钟合计 218.936 秒，peak allocated 最大 419.496 MiB。24 项生产者检查、8 模态加载/16 行对齐通过；原验收 3110 测试通过。逐任务截取分布、去重率、截断、显存、耗时与命令见 NS_P2_REPORT.md 及 training_changes 第 74 节。

本阶段不训练 HGT，S2 concat 在 NS-P4 实现；未完成 M2、LLM 或蒸馏。最终实验拟在显存充足服务器进行，本机 RTX3050 4 GiB 仅为开发限制，未部署实测服务器。


### 2026-11-02 NodeSem NS-P2 编码问题核验与更正（修改 AI：Codex）

前一条 NS-P2 记录和独立报告的中文已写成 ASCII 问号，f049d18e 推送的版本同样受影响；不是仅终端显示问题。已复现 PowerShell ASCII 管道替换，原报告为 2,058 个问号、0 中文字符。此前字节一致性检查未检查可读性，属于 Codex 文档验收遗漏。本条保留旧文，补充可读记录；独立 NS_P2_REPORT.md 根据源码/JSON/CSV 重写，原报告保留在 Git 历史中。

NS-P2 实际完成 8 组文本/CodeT5 256 维向量，104,836 行、0 截取回退、两次编码逐位一致；原验收 3110 测试通过。独立 nodesem 安装获用户批准，mando 不变；安装时涉及的 3 个 user-site 包已按原版本恢复，详细选择与副作用记录见 training_changes 第 75 节及 environment/installation_scope.json。未运行 HGT 训练，S2 concat 尚待 NS-P4。

本次 75 个 JSON/JSONL、33 个封存引用、全部文本行及 8 个向量文件 SHA 核验通过；跨任务 19,746 组相同源码节点无文本冲突。跨文件同语句的匿名编号不同是冻结 8G 文件级规则的结果，未修改方案；这仍是特征可比较性的限制，不能推断模型收益。审计见 scripts/node_sem/artifacts/ns_p2_review_20261102/；本轮只改文档与新增审计记录，未改代码或封存产物，未自动推送。

最终实验按用户计划在显存充足服务器执行；本机 RTX 3050 4 GiB 仅为当前开发限制，服务器尚未部署实测。


### 2026-11-02 NodeSem NS-P2b 完成（修改 AI：Codex）

四处损坏文档已归档原字节并原位重写；用户批准保留三份历史文档损坏节前后的全部字节。新增 doc_check（不进入训练 runtime），对 UTF-8、连续问号、替换字符及显式 --expect-cjk 做校验，21 项定向测试通过。保护写入采用纯 ASCII 转义载荷＋Python UTF-8，不再将中文直接经 Windows stdin 传输。

CPU 编号诊断：四任务同语句匿名变体余弦均值依次 0.903835/0.922279/0.902175/0.912641，同类型不同原文随机对照 0.601283/0.624942/0.615706/0.637461；原名同语句向量逐位相同、余弦为 1。编号有可量化影响，但不足以推断 F1 或改变冻结 8G 决定。

残留词统计：四任务的非 vN、非保留代码名称均为 0，没有 re_ent/txorigin 标记；data/number/min/max/sig/interfaceId 实际是 identifier 且位于保留表，并非模板所说的“不是 identifier”，已在报告更正。字符串词汇单列。

3113 passed; 0 failed; 0 skipped; 42 warnings. 8 个旧模态与 8H 只读核验通过，原代码/特征/计划保持不变；本地提交、不自动推送、不推进 NS-P3。详细记录见 training_changes 第 76 节、NS_P2B_REPORT.md 和 artifacts/ns_p2b/。最终实验拟在显存充足服务器开展；本机 RTX3050 4 GiB 仅为当前开发限制。


提交前补充：通用 `git diff --cached --check` 对原始 `preexisting_document_edits.patch` 的空白上下文行报尾空格。这是原始 diff 语法的一部分；为保留归档字节，仅该历史归档免于尾空格格式检查，其 SHA 与暂存字节仍严格核验。其余新增代码、可读文档和 JSON 的暂存格式检查通过。原失败与限定复核记录保存于 artifacts/ns_p2b/commit_validation.json；未改算法或实验产物。


### 2026-11-02 NodeSem NS-P3a 完成（修改 AI：Codex）

完成原名 StatementFacts：AST声明/作用域、通用行为、词法守卫、一层运算检查、冻结L1/L2/L3精确证据、语义CFG顺序和声明/函数/合约汇总。新代码和测试仅在scripts/node_sem；原DFG/HGT/tokenizer、图、标签、折、8H计划/结果不变。用户明确后续用original，旧匿名结果仅留历史；后续需原名S0配对基线。详情及批准选择见training_changes§77、EXPERIMENT_POLICY.md。

最终事实路径为scripts/node_sem/artifacts/facts_v1/accepted_attempt2/，由CURRENT.json指向；根original/首次产物已被替代但保留。四任务52418行与原名text_v1身份/顺序/SHA一致；另外五类50源码、2098函数冒烟0异常。全套3372测试通过，42条既有警告；22813冻结文件与8H生效runtime核验通过。报告：NS_P3A_REPORT.md。

修复了共享继承授权与完整性、未知modifier、库调用分类、缺失状态写和别名导致的顺序误判。未知仍明确保留，不能声称完整Solidity分析；未执行编译验证、向量编码或训练，无F1结论，不推进NS-P3b。最终实验按用户安排在显存充足服务器执行，本机RTX3050 4GiB仅是开发限制；服务器尚未部署实测。本轮CPU、本地提交、不自动推送。

### 2026-11-02 NodeSem NS-P3a2 完成（修改 AI：Codex）

修复 L2 非状态诊断导致整函数未知、未投影节点导致整组汇总未知的问题；加入逐字段 unknown_fields、全 AST 汇总和析取发送者守卫。冻结 DFG/HGT/tokenizer、原图/标签/折/8H保持不变，后续仍用original。三项用户批准调整详见 training_changes§78、NS_P3A2_REPORT.md。

accepted_attempt3 四任务52418行验收通过，非允许差异0；state unknown分别降至78/10067、32/6635、75/7858、29/4664（重入合约/节点、访问控制合约/节点）。CURRENT已切换，旧attempt2的36文件SHA保持原样。3463测试通过，另五类50文件冒烟0异常；22813冻结文件、8H运行版本与所有输入身份通过核验。

NS-P3b需按unknown_fields逐字段编码；未知别名、声明歧义、缺失投影、assembly仍保守保留。没有训练/GPU/编译或新F1，不自动推进下一阶段或推送。最终实验将在用户安排的显存充足服务器执行；当前RTX3050 4GiB限制仅来自本机开发环境，服务器尚未部署实测。

### 2026-11-02 NodeSem NS-P3a3 完成（修改 AI：Codex）

修复正极性合取漏识别发送者守卫、throw 被误计未知状态读取、K/L/M 已知证据被未知贡献覆盖，以及 K 未知作用域过宽；补齐缺少 entry 的支配树返回值兼容。用户批准保留原有非发送者有效相等组合，并将数组 base 跨布尔运算纳入误解析判据；原判据差异和源码证据均保留。

accepted_attempt4 四任务52,418行验收通过，1,400个任务内行实例有授权范围内变化，非允许差异0。state unknown变为68/22/43/21，K unknown变为105/85/33/15（重入合约/节点、访问控制合约/节点，分母同前）；buggy_2/3 changeOwner 的未保护写入函数数2→1，未改标签。CURRENT已切换，旧attempt3的23文件SHA不变。

650+2653+223=3526测试通过，0失败/跳过，42条既有警告；52 Oracle、五类50文件冒烟通过，正确分组条件一致性差异0。22,813冻结文件及8H运行版本只读验收通过。详细分母、每项影响、选择和命令见NS_P3A3_REPORT.md与training_changes§79。

后续仍使用original，NS-P3b需消费逐字段unknown_fields，原匿名8H成绩不是原名实验的配对基线。无训练/GPU/编码/编译，不自动推进下一阶段或推送。最终实验按用户安排使用显存充足服务器，RTX3050 4GiB只是本机开发限制；本轮未部署服务器。


### 2026-11-02 NodeSem NS-P3b 完成（修改 AI：Codex）

原名accepted_attempt4事实生成原名/局部masked CTX各52,418行，8套256维编码；STATIC四套243维。用户批准独立encode_ctx保留旧CODE源码SHA、只读AST签名/标识符辅助对齐、保留标签的最终限长兜底。中断后获准保留现场、复用首份成功并在新attempt完成余7项，未换模型/参数。详情见training_changes§80、decisions.json。

8套两遍编码逐位一致、max error=0；全量masked标识符残留0。S3/S4=514/758维，G0/G3R两种CTX共32次真实装配通过；3609测试通过，42条既有警告。旧CODE、8H及22,813冻结文件核验通过。报告NS_P3B_REPORT，产物CURRENT连接明确的复用/新编码索引。

仍以original为主，保留匿名接口供以后比较，masked仅局部CTX对照。checked_call摘要未在本轮字段表中、尚未消费；没有HGT训练/F1/NS-P4。最终实验按用户安排使用显存充足服务器，4GiB只是本机开发限制；本轮未部署服务器。本地提交、不自动推送。


### 2026-11-02 NodeSem NS-P3b2完成（修改 AI：Codex）

按r13完成STATIC检查运算两列与B/C/D三值修正，243→245维；CTX函数入口及参数来源unknown→entry。原名与局部masked各52418行重编码，8份均两遍逐位一致；旧facts/图/标签/DFG/HGT/tokenizer/8H不改。4任务helper=214/103/271/105，所有非授权列/文本差异为0。

3628测试通过，42条既有警告；32组合真实载体验收，S3/S4=514/760，旧CODE与8H有效runtime、22813冻结文件核验通过。新CURRENT指向ns_p3/attempt_b2，旧产物保留，详细选择、命令和失败夹具记录见training_changes§81及NS_P3B2_REPORT。重入FROM剩余468未知中439为L1回退、29为循环更新无相对距离，未伪造entry。

仍以original为主，masked仅CTX名字对照；本轮无HGT训练/新F1，不推进NS-P4，仅本地提交、不自动推送。最终实验将在用户安排的显存充足服务器执行，RTX3050 4GiB仅当前本机限制，服务器未实测。


### 2026-11-03 NodeSem NS-P4 融合与单轮验收（修改 AI：Codex）

完成原名融合配置S2/S3/S4/S4g/S4-noG、局部masked CTX对照S3m/S4m，以及原名S0o/S1o登记。concat/gated、缺失掩码、局部RNG模态dropout与layers=0已接入；旧S0/S1参数和前向路径保留。STATIC沿用NS-P3b2的245维，S3/S4载体为514/760维。

用户批准浮点数学等价与同实现逐位确定性分开验收，并授权CPU通过后的两次GPU单轮探针。四任务G0/G3R共8次原token逐位核验通过；重入节点S0o全部初值与8H S0逐位相同。7个真实重入节点fold0配置的CPU单轮检查均通过，loss有限、各模态有非零投影梯度、共同初值和best/last重载预测一致。正式拟合0次。

本轮GPU验收未通过：S1o已完成1轮训练/inner_val计算并保存best，但在随后资源检查处因最低空闲88MiB停止；last、最终评分及重载一致性验收尚未完成。PyTorch峰值allocated=1852.972MiB、reserved=2074MiB，启动前空闲3456MiB；未发生已记录的OOM。S4按规则未启动，未重试。完整现场和111次采样保留，gpu_stop_audit.json只证明停止规则正确，不代表GPU模型验收通过。

因此当前结论是“代码和CPU验收完成，GPU资源验收受阻”，不能称NS-P4全部验收通过；后续在合适资源环境中经明确安排补验，本轮不解除阈值或自动重跑。


GPU resource probes accepted 0/2. S1o: min_free=88.0 MiB; stopped: MemoryGateError('Whole-card free memory below 100 MiB: 88.0 MiB'); S4: min_free=not run MiB;

最终784+2653+223=3660测试通过，0失败/跳过，42条既有警告。夹具list+tuple错误与prepare缺少目录的失败记录保留；准备错误发生于fit之前，修复后新建attempt2。详细文件、批准选择、耗时/内存/梯度/收据和命令见NS_P4_REPORT及training_changes第82节。

原DFG/HGT/tokenizer、图、标签、划分及既有特征不改。本轮为实现验收，不据一轮结果判断提升。S4-noG仅无HGT消息传递，CTX/STATIC仍含语义信息；S3m/S4m只对CTX局部masked，CODE仍原名。正式原名计划和基线接入留给NS-P5，旧匿名8H成绩不能充当原名配对基线，不自动推进下一阶段。

最终实验将在用户安排的显存充足服务器执行；RTX3050 4GiB仅是当前本机开发限制，服务器本轮未部署或实测。产物在WSL工作树，不额外复制到C盘。三份记录仅追加，UTF-8/CJK和旧前缀SHA核验；本地提交，不自动推送。


## 2026-11-03 NS-P4b dropout修正及GPU验收（修改 AI：Codex）

按PROMPTS r15执行，输入48d83d1b。dropout种子加入ntype，保留同类型可复现/eval计数/全局RNG不变。原attempt2全部274文件保持SHA不变；新入口复用冻结fit和零步初值，不改DFG/HGT/tokenizer/原图/标签/特征/划分。旧100MiB停止门槛仅在新计划取消，改为local_dev提醒；启动仍≥3000MiB，reserved超过对应8H的1.25倍只提示，错误仍停止。

用户批准logits张量尺度相对差公式并另报逐元素差；首次S3因阶段日志create-only接入失败，训练前0步。修复JSONL追加并经明确批准在attempt3/resume2恢复，原计划/失败/初值不覆盖。6项CPU和6项节点GPU单轮全部验收通过，共同初值、模态梯度、best/last和两评分分区重载一致；S4/S4g在GPU临时关闭TF32的eval中通过两项1e-4门槛，last_gates在CPU且有效行归一化。

Contract GPU passed: 2; OOM: 0. Tests: 805+2653+223=3681 passed; 0 failed/skipped; 42 existing warnings.

完整资源差值、参数量、耗时、原始记录和命令见NS_P4B_REPORT.md、attempt3/resume2及training_changes§83。历史资源CSV与原收据SHA一致，8H生效354源码及load只读通过；启动显存并不证明无其他进程，历史资源差值也不是纯特征因果比较。仅非正式1epoch功能验收，不选择模型、不推进NS-P5。

主视图仍original，局部masked仅CTX对照，旧匿名8H成绩不是原名配对基线。最终实验按用户安排在显存充足服务器运行，RTX3050 4GiB只是本机开发限制；本轮未部署/实测服务器。三文档仅追加；WSL产物不另复制到C盘。本地提交，不自动推送。


## TF32 诊断与第二次明确恢复

恢复1的S1o/S2 GPU已成功；S4在零步默认精度前向验收失败，最大绝对差0.00106704235、张量尺度相对差0.000577034082，尚未执行训练，后五项未启动。用户授权独立诊断：1次CPU和3次GPU eval，无优化器。默认GPU重复结果逐位一致；关闭TF32后绝对差8.34465027e-7、相对差4.51261152e-7，参数digest不变，原TF32设置已恢复。这支持本例差异主要来自精度设置，不能据此宣称所有CUDA运算逐位等价。

用户先误选“停止”，随后明确更正“刚才点错了，按照你推荐的方式进行”。依据更正授权，新resume2计划保留旧失败、plan/seal及精确旧driver源码，复用6CPU和2GPU成功收据，只继续6项剩余GPU。1e-4的绝对/张量相对门槛仍保持，但验收前提改为同初值CPU与临时关闭TF32的GPU eval。默认TF32下的差异单列，不能称默认GPU也通过该门槛。训练前用finally恢复matmul/cudnn的原TF32设置（均true），完整fit后再次核验；训练计算、参数、随机种子、模型及数据保持原样，未把训练改成禁用TF32。

独立诊断入口p4b_parity_diagnostic.py未调用训练器。参数、原计划和证据保留；零步诊断与单轮fit分别计数，不作为新的seed实验。若诊断或fit出错仍停止，未自动放宽容差。


## 2026-11-03 NodeSem NS-P5：N-A原名计划完成（修改 AI：Codex）

按r16封存artifacts/batch_NA_v1：{S0o,S1o,S2,S4}×{G0,G3R}×30折=240个新fit计划；本轮训练0次、CUDA未初始化。32套载体、240份零步初值逐一CPU严格重载；32组fresh fold1证明参数逐位一致，16组原token一致。S0o全参数及其他配置共同参数取对应8H零步锚点，旧匿名分数不作原名配对基线。

用户批准本机RTX3050先导、服务器另建，以及先证明再复用未训练结构。保留分组嵌套协议、inner_val选best/outer_test最终评分、L-audit/seed1/默认TF32，同一比较族不混设备。G0+S4仍含DFG派生特征，不是无DFG对照。非SolidiFI节点正例32/20核对通过。

3722测试通过，0失败/跳过，42既有警告；8H、旧P4和三文档前缀核验通过。准备52.6分钟，正式fit名义估算8.03–8.68小时，仅假设估算；合约S4单轮最低空闲44MiB，不能保证全量稳定。

新增batch_na.py/p5_prepare.py/test_batch_na.py，旧执行器/冻结代码不变；授权模板false，NS-P5A另绑worker与授权，不改旧seal。报告NS_P5_REPORT、详细选择/命令见training_changes§84。最终实验使用用户安排的显存充足服务器，本机4GiB仅开发限制，服务器未部署实测。重产物留WSL、不额外写C盘；本地提交，不自动推送、不启动训练。


## 2026-11-03 NodeSem NS-P5A 接入与开训前检查进行中（修改 AI：Codex）

按PROMPTS r18新增原名N-A worker、封存载体直接加载、独立进程串行控制器及最终统计/注意力入口；旧plan/seal、初值、图、特征、DFG/HGT/tokenizer/训练器不改。240项是本轮目标，尚不能称训练完成。

用户批准两个正式pilot先行，再补完主比较40项；仅确认的外部SIGTERM/SIGHUP允许保留现场后同初值重跑一次，其他错误或原因不明中断停止。决策原文在decisions_P5A.json，详细实现与命令见training_changes§85。正式配置没有P4的1epoch覆盖。

3759单元回归通过，0失败/跳过，42既有警告；32组载体及6次非正式CPU拟合验收仍在进行，正式GPU训练尚未开始。Windows已接电且自动睡眠/休眠为从不，未改电源设置。后续由tmux后台执行，status/progress保留进度，不依赖对话或网络。

最终实验按用户安排在显存充足服务器开展；本机RTX3050 4GiB仅当前开发限制。本机与服务器另建批次、不合并、不择优；服务器本轮未部署实测。原名为主，匿名8H仅零步锚点和历史参考，不作配对基线；产物留WSL，不另复制C盘。


## 2026-11-04 NS-P5A 正式批次运行中（修改 AI：Codex）

开训门槛现已全部通过：32/32 封存载体与现算载体、同种子模型逐位一致，6/6 非正式 CPU 等价 fit 通过；3759 单元回归通过，0 失败/跳过，42 既有警告。此记录补充前一时间点“尚未开训”的状态，不改旧文。

正式运行已封存 execution_revision 与独立 authorization；旧 plan/seal 未改。两个正式 pilot 均验收通过：重入节点 G3R/S4/fold0 约179.5秒，22轮，最小空闲397MiB；重入合约 G3R/S4/fold0 约218.2秒，17轮，最小空闲74MiB。两者 best/last 重载预测一致，默认TF32保持开启，计入240次。74MiB按local_dev_v1记录memory_tight，不触发未经批准的降配或停止。

截至本次追加，控制器已验收40/240次，正在重入节点G3R/S1o/fold9；进度以batch_NA_v1/controller_status.json为准。前4个重入节点fit平均约162.66秒，外推整批拟合10.84小时仅为初期估计，不包括120次训练后注意力eval；不得据此保证完成时间。训练期间不汇总F1。

训练在tmux nodesem-na-v1中单GPU串行执行，与Codex会话和网络独立；Windows已接电、交流睡眠/休眠为从不，设置未被修改。失败停止且保留现场；仅已批准并确认的外部SIGTERM/SIGHUP最多重跑一次。当前没有训练失败记录。

新增独立finish_delivery.py仅在controller complete、240个正式收据、120个注意力结果及全部引用SHA通过后写NS_P5A_REPORT并追加三份最终记录、按显式小文件清单本地提交；不启动训练、不读取中途F1、不push。收尾源码和文档前缀另由delivery_revision记录；若用户随后改变文档、HEAD或暂存区，收尾拒绝自动提交，保留结果供核对。该脚本不属于正式计算路径，不改变已封存运行源码。

最终服务器实验使用用户安排的充足显存设备，另建批次并保持相同预登记；本机RTX3050 4GiB只是当前开发限制，两批不合并、不择优。原名为主，匿名8H仅历史参考和零步锚点；本轮不运行N-B、多seed或服务器实验。产物留WSL，不另复制到C盘。


## NS-P5A N-A 全量完成（修改 AI：Codex）

<!-- NS-P5A_FINAL_DELIVERY_V1 -->

240/240 原名正式 fit、120/120 G3R best 注意力 eval 已验收；两个正式 pilot 计入 240，不重复训练。32 组载体/模型逐位证明和 6 次 CPU 等价 fit 已通过；3759 单元回归通过，0 失败/跳过，42 既有警告。正式配置与计划逐字段相同，全部 checkpoint/预测重载和设备/TF32 一致性通过。

主终点重入节点 G3R 的 S4−S0o 为 +0.1474 个百分点，提升/持平/下降 8/0/2 折；Holm 校正 p=0.0742188。S*=S2 仅按 inner_val 选择；best/last、折均值/OOF、原标签与 L-audit 分开。完整表、统计边界和命令见 NS_P5A_REPORT.md 与 batch_NA_v1/reports。

最终服务器另建批次并按相同预登记复现；本机 4GiB 仅当前限制，两批不混合、不择优。本轮没有 N-B、多 seed、七类扩展或服务器运行；没有自动 push。


## 2026-11-04 NS-P5A 收尾核验补充（修改 AI：Codex）

240次正式训练和120次注意力eval全部完成，失败/外部中断/重试均为0。独立收尾脚本已经生成报告及三文档最终记录，但本地提交在git diff --cached --check处退出：冻结CSV使用标准CRLF，Git默认将行末CR提示为trailing whitespace。使用仅本次命令的git -c core.whitespace=cr-at-eol diff --cached --check复查通过；未转换CSV、未修改训练/报告统计源码、旧seal或结果字节，也未重训。保留delivery_failure_295895.json和旧日志，另写delivery_recovery.json，再完成本地提交；不自动push。

结果解读：G3R上的S4相对S0o，重入合约/访问控制合约/重入节点/访问控制节点best折均BF1分别增加1.6789/0.3284/0.1474/0.0076个百分点。主终点重入节点8升2降，Holm p=0.07421875，不能声称通过0.05的校正显著性标准。仅CODE的S2在重入节点达到99.8265%，高于S4的99.7721%；inner_val选出的参考S*也是S2，因此现有证据未证明CTX+STATIC联合增强优于CODE。

非SolidiFI节点pool单列：重入S0o→S4为TP20→25、FP11→7、FN12→7，BF1 63.49%→78.13%；访问控制为TP0→2、FP3→10、FN20→18，BF1 0%→12.5%，仍然漏掉18/20个正例。总体99%以上不能等同真实来源文件已解决。该分层是小样本诊断，并非独立重复。best预登记主结果不因last更好而替换；重入节点last的S4−S0o为-0.0326个百分点，与best的小正向不同。


## 2026-11-04 NodeSem NS-P6计划封存完成（修改 AI：Codex）

N-B准备门槛完成：S3/S4g/S4m×G3R、S4-noG×G0（0层）共120项，16套载体与120份零步初值已CPU严格重载；16组新建/复用未训练结构和16组装配快路径逐位证明通过。N-A240份正式收据及引用只读验收；旧源码、计划、结果不改。3801测试通过，0失败/跳过，42既有警告；8H354冻结源码及生效修订保持一致。

用户已同意独立N-B调度适配，复用原construct/run_core/收据核验；S3−S2整体与r19新增事后分层按历史来源区分。主视图original，S4m仅CTX masked，S4-noG仍含依赖派生特征。详细实现和选择见training_changes§86、NS_P6_REPORT及NS_P6_README。

新批次artifacts/batch_NB_v1已保存plan/seal，授权模板false；正式fit与GPU前向均0。按PROMPTS §5.9需另行授权再开训；后续门控/注意力和N-B专用汇总仍须接入，不把120fit齐备冒充报告完成。按N-A估算拟合4.93–9.25小时，仅供资源规划。

最终实验会按用户安排在显存充足服务器开展；当前RTX30504GiB仅本机开发限制，服务器尚未实测并须另建批次，不混用结果。PT/NPZ留WSL，三文档只追加，本轮本地提交、不自动push、不推进NS-P7。


## 2026-11-05 N-A 测试权重定向清理（修改 AI：Codex）

用户要求按建议删除不需要的权重。核对后仅删除 batch_NA_v1/acceptance/cpu 下6次已完成、非正式CPU短检查的12个best/last文件，共984,787,764字节（约939.17 MiB）。删除前逐文件核验SHA、路径和完成状态；N-A/N-B JSON中没有这些文件的结构化路径引用。保留cpu_proof、预测、日志、摘要和原验收记录，原计划/执行修订不变。原CPU测试权重已释放，不能直接重载这些旧短检查；正式结果不受影响。

N-A正式best240、last240、零步初值240全部保留；N-B权重及其他数据未删除。清理后N-B仍运行，检查时48/120完成，无错误；用户此前已明确授权“训练”，启动记录在batch_NB_v1/execution_decisions、authorization及launch_execution.json。此处不是完整训练或最终报告验收。清理清单及验证见scripts/node_sem/artifacts/cleanup_NA_cpu_weights_20261105/。

空间释放发生在WSL文件系统内，未关闭WSL或压缩VHD；宿主磁盘空闲不保证立即增加。最终服务器另建批次，本机4GiB只是当前开发限制；训练期间不改计算版本、不提交或推送。


## 2026-11-05 N-A/N-B对照设计独立复核（修改 AI：Codex）

本次只评估并记录方案，不改变正在运行的N-B、配置、划分、训练计算或既有结论。依据已完成N-A的reports/report.json、NS_P5A_REPORT、两批plan/spec及init.py/adapter.py；未读取N-B中途评分作选型。

判断：S0o原输入基线、S1o简单可学习token基线、S2仅CODE强基线和S4完整方案均有独立作用；当前S3能拆解CTX与STATIC的条件增量，S4g检验融合方式，S4-noG检验消息传递必要性，S4m为局部CTX名称诊断。问题主要是对照用途层级和比较解释，而非配置数量本身。全部变体同时交叉全部图/任务会提高成本，未来不必机械扩展；本批已冻结的完整折与任务继续保留。

已核实的重要边界：S2 modality_dropout=0，S3/S4=0.1，故S3−S2同时改变输入和模态正则化；不能写成纯CTX因果贡献。HGT/分类器共用初值，但新增适配器种子包含spec.digest，不保证跨配置共同适配器逐位相同，单seed微小差异须谨慎。S4-noG仍保留DFG派生CTX/STATIC，只去除消息传递；S4m只mask CTX，CODE原名保留，不能证明整个模型不依赖名称。S4−S3仅是已有CTX条件下加入STATIC的增量，不测STATIC单独或与CTX的完整交互；目前无需自动补齐所有组合。

N-A的G3R best折均BF1中，S4−S2：重入合约−0.6371、访问控制合约−0.7333、重入节点−0.0544、访问控制节点−0.0520个百分点。这些是单seed描述，尚不能认定STATIC或CTX本身有害；但不能只报S4胜S0o而忽略强基线S2。主终点S4−S0o Holm p=0.07421875，不能声称校正显著。

建议完成本批120项并关闭扩展入口，集中判断S2→S3→S4及S4g是否有稳定、可解释的收益，原标签辅助与L-audit、best/last、两来源分层继续分开。后续服务器计划先区分主结果、组件消融、诊断附表；只在需要语义归因时申请统一相关正则化和共同适配器初始化，再独立封存，不能在当前批次静默修改。最终模型选择须基于inner_val；不可看同一outer结果不断改进后仍称独立确认。未来资源优先用于少量关键方法的复现和更有区分度的评估，任何新seed/数据或方案变更均另行授权。


## 2026-11-05 NS-P6 N-B完成汇报（修改 AI：Codex）

N-B120/120正式结果验收，引用N-A240项，共360结果；新增90次只读best诊断（含30份S4g门控），本轮新增训练0。3837项回归通过，8H354冻结源码不变。详细结果、命令和限制见scripts/node_sem/NS_P6_REPORT.md及batch_NB_v1/reports/。

S3相对S2收益很小；S4相对S3四任务best均下降；门控不一致改善；重入节点S4相对零层版提高1.5981pp，10折均升。S4m节点微升、合约下降，不代表全量匿名更优。best/last、非SolidiFI子集单列，不按outer分数重新选型。保留dropout与adapter种子混杂边界，暂停扩展。

正式唯一失败为访问控制节点S4m fold8显存采样失败，经单独授权同初值重跑一次成功，旧attempt与115项前序成功保留。当前N-A480个正式best/last权重缺失、原因未查明；收据及非权重产物SHA通过，指标据封存预测复算，不能宣称当前可重载N-A。此前12个CPU测试权重清理记录不能解释此缺失。N-B240正式checkpoint核验通过。

原计划/输入/训练计算不改，新增分析单独封存。最终服务器显存充足安排保留，但另建批次、不混合本机结果；本轮不进入NS-P7或新训练，不自动push。

补充：S4g的CODE平均门控为0.357–0.495，没有普遍退化为CODE-only；多邻居首层注意力比例已按同口径汇总，N-A部分只读历史摘要。360份训练日志再次核实best严格按最低inner_val loss选择，未按外层F1选checkpoint。详细表见NS_P6_REPORT完成节第12项。


## 2026-11-05 NS-P6c 权重来源更正（修改 AI：Codex）

根据用户提供的 PROMPTS.md r20 §5.9c 中的说明，N-A 的480个正式 best.pt/last.pt 是用户本人为节省空间主动删除的。此前“原因未查明”记录保留为当时检查事实，本条补充后续确认的原因，不追溯修改旧文。删除的具体时刻未提供，不编造时间。N-A的收据、预测和指标仍有SHA绑定，已报告数值不因删除权重而改变；注意力诊断在删除前已完成并封存。当前不能重载N-A模型，服务器批次需重新训练。batch_NB_v1/historical_weight_availability.json保持原样，新说明在artifacts/ns_p6c/na_checkpoint_note.json。

### 后续权重保留和 Git 固定规则

N-B best 权重至少保留到 NS-P6c 诊断完成，完成后仍由用户决定是否删除；本轮不删除。删除前必须生成逐文件路径、大小、SHA256索引并核对，删除后追加实际范围和不可重载的限制。当前120份成功N-B best已索引，旧失败attempt中的文件仍保留，不当作新的正式模型。

以后Git只归档代码、计划/封存、收据、报告与SHA索引。逐行载体manifest、百万行索引等可重建大JSON保留本地，Git记录其SHA和生成命令；权重、NPZ和预训练模型不上传。不改写既有Git历史、不自动清理旧产物。检查时共享.git实际体积809,223,604字节（约771.74 MiB），这不是本工作树全部运行产物的大小。

最终正式实验按用户安排在显存充足的服务器开展；本机RTX3050 4GiB只限制当前本地开发与先导实验。服务器仍须另行核验并封存独立批次，不将本机和服务器结果混合或择优。


## 2026-11-08 NS-P6c 完成（修改 AI：Codex）

门控机制在工作，门控权重与投影范数的乘积已逐模型核验。同时去掉CTX和STATIC时，四任务共改变476个外层预测，其中非SolidiFI正例节点改变9个；是否使用这些输入应看各任务干预敏感性，不能只看门控权重。STATIC与CODE/CTX的可线性预测程度、非SolidiFI额外信号见下表；这些是条件性描述证据，不是语义因果证明。 STATIC位的折均AUC≥0.95数/可估位数为重入合约: code 92/118, ctx 107/118；访问控制合约: code 84/119, ctx 99/119；重入节点: code 89/115, ctx 103/115；访问控制节点: code 75/111, ctx 87/111。非SolidiFI的CODE+STATIC相对CODE平均BF1差为重入节点: 2.1818pp (10/10可估折)；访问控制节点: -0.3968pp (9/10可估折)；不能用少量可估折证明稳定增益。

30个S4g best完成120次只读前向，原full预测复现、SHA/state/binding及前后参数一致；S4权重不可用按批准跳过。四任务冗余探针及两个节点任务非SolidiFI信号探针完成，空/单类别折明确标记，未修改划分。3853测试通过、42既有警告，8H354冻结源码不变。新增代码/命令/逐折结果和限制见scripts/node_sem/NS_P6C_REPORT.md、artifacts/ns_p6c/。用户确认的三项澄清与N-A权重删除原因已留证。

HGT新增训练0，不进入NS-P7；权重未删除，保留120份成功N-B best的SHA索引。服务器实验按用户安排另建显存充足批次，本机4GiB只属开发限制，不混合结果。


报告拼装修订（2026-11-08，Codex）：首个报告入口因metrics和预测变化统计都含样本数n而报重复关键字错误。失败发生在写出汇总前，不涉及评估或探针。原入口、原plan/seal与finalization_binding保留；v2报告入口先断言两边n相同，再合并字段，对样本数不一致及意外重叠字段补回归。仅重新执行报告生成，未重跑任何模型或探针。报告修订绑定见reporting_revision.json。


CPU调度修订：用户批准保留首轮现场，复用已完成的访问控制节点fold0，其余29折并行执行。原plan/seal与p6c_core.logistic_probe不变；特征缓存逐位相同，调度入口输出与原函数逐项相同测试通过。旧4个串行CPU进程经明确授权终止，未完成的中间计算不进入结果；表中探针拟合次数仅指进入最终报告的已完成C候选。修订、原进程与文件SHA、日志在cpu_parallel_revision/，不称新seed重复或HGT续训。


## 2026-11-08 NS-P6c2 完成（修改 AI：Codex）

按适用节点计算，CODE折均AUC≥0.95的STATIC位数/可估位数为：访问控制合约 66/136（48.53%，合格136位）；访问控制节点 67/134（50.00%，合格137位）；重入合约 81/142（57.04%，合格142位）；重入节点 85/136（62.50%，合格137位）。当前探针较弱的语义父组（组内位的折均AUC中位数最低三组）为重入合约: H=0.8214, D=0.8641, M=0.9001；访问控制合约: H=0.7761, I=0.8771, D=0.8787；重入节点: H=0.8613, D=0.9023, I=0.9106；访问控制节点: H=0.8331, C=0.8678, D=0.8921。这些低值不能证明CODE中不存在该信息；不可估组也不能称为无法预测。只保留非SolidiFI语句/条件节点后，重入节点 static minus code：BF1 2.1429pp，AUC 0.0681（10/10折）；重入节点 code_static minus code：BF1 4.1429pp，AUC 0.0442（10/10折）；访问控制节点 static minus code：BF1 -1.8519pp，AUC 0.0485（9/10折）；访问控制节点 code_static minus code：BF1 -1.0582pp，AUC 0.0650（9/10折）。这是小样本、固定seed的描述性诊断，不能直接当作HGT增益或确定的因果结论。

按schema.applicable修正旧全部行探针的节点种类混杂；CTX改称facts编码保真度。30折CPU诊断完成，未加载HGT、未新增HGT训练；旧图、特征和NS-P6c结果保持不变。3973项测试通过；详情见scripts/node_sem/NS_P6C2_REPORT.md与artifacts/ns_p6c2。最终实验在显存充足服务器另建批次，本机显存只属开发限制。NS-P7暂缓。


## 2026-11-08 NS-P7 50函数试点完成、门槛未通过（修改 AI：Codex）

在原名源码上实现LLM提示层a_k编号，原图/CODE/CTX/STATIC/HGT/标签/划分不变。254个源码SHA、7,670个唯一函数形成4,485个唯一提示。固定50函数（26非SolidiFI，含10个正例所在函数）使用本地Qwen2.5-Coder-3B-Instruct Q4_K_M完成，约242.35秒、50/50 JSON成功、0重试/0OOM。faithfulness中位0.6667、≥0.5为80/123=65.04%，external_call精确率75%、state_update72.34%，未达预定门槛，停止全量生成和后续教师/学生工作。

用户批准后端最小安装、role分母及unknown保守处理；只新增nodesem后端与本批独立CUDA库，原包与mando不变。access_check原诊断误用了保护范围guards，0%不可解释为识别准确率；更正状态见NS_P7_REPORT.md及独立审核记录。3993项最终回归通过、42条既有警告，8H及354冻结源码一致。详见scripts/node_sem/NS_P7_REPORT.md、artifacts/llm_v1。最终实验仍在显存充足服务器另建批次，本机显存只是开发限制；没有启动NS-P8。


## 2026-11-08 NS-P7b 第二次50函数试点（修改 AI：Codex）

未通过预先封存门槛。原50函数响应只作事后诊断，不改第一次未通过；新seed=2样本无源码函数SHA重叠，保持模型/后端/推理参数。新度量处理下标读取、external布尔主指标与self_condition；describe_v2补根变量口径及合约头，judge_v2仅登记。详见scripts/node_sem/NS_P7B_REPORT.md。

最终测试4033通过，旧256份产物及354份冻结源码核验一致。没有全量生成、教师编码或训练；最终实验仍在显存充足服务器另建批次，本机4GiB仅开发限制。


## 2026-11-08 NS-P7c 全量执行中（修改 AI：Codex）

按 PROMPTS r26 和用户“暂时继续当前的训练”的指令，继续现有 NS-P7c 批次，保留当前分组内外层划分、L-audit 和原名主输入设置。当前 GPU 工作为冻结 3B LLM 的 describe_v2 推理，不是 HGT 或 LLM 参数训练。两次试点未通过的结论保持，用户知情后决定全量运行。

独立后台生成 PID 718695；后续控制器 PID 719581 等待生成正常结束，再串行完成后处理、BGE 教师向量编码、CPU 岭回归与逻辑回归诊断和报告。失败停止，不自动重试、不进入 NS-P8a。当前尚未完成全量结果，不提前报告诊断分数。

本轮回归：NodeSem 1190、DFG v2 2653、旧 DDG/graph_utils 223，共4066项通过；8H只读装载与354份冻结源码核验通过。用户已批准岭回归alpha网格和逐任务teacher.npz/manifest＋总索引的接入方式。最终实验将在显存充足服务器另建批次，本机RTX3050 4GiB是当前开发限制。


## 2026-11-08 NS-P7c 完成（修改 AI：Codex）

access_control_contract 岭回归余弦 0.8790 / 同类型均值 0.8181；access_control_node 岭回归余弦 0.8772 / 同类型均值 0.8298；reentrancy_contract 岭回归余弦 0.8784 / 同类型均值 0.8162；reentrancy_node 岭回归余弦 0.8854 / 同类型均值 0.8254。access_control_node STATIC+TEACHER−STATIC：BF1 1.4815pp，AUC 0.0730；reentrancy_node STATIC+TEACHER−STATIC：BF1 2.7143pp，AUC -0.0196。

两次试点未通过的结论保持；本次按用户r26决定完成3B全量describe_v2、无role教师向量及必要CPU诊断。未训练HGT或学生，未运行judge，不进入NS-P8a。详细记录见scripts/node_sem/NS_P7C_REPORT.md。用户确认岭回归网格和逐任务教师产物布局。最终实验将在显存充足服务器另建批次，本机4GiB只属开发限制。


## 2026-11-08 NS-P8a N-C1准备与封存完成（修改 AI：Codex）

已准备30个S6/G3R任务（重入节点10、访问控制节点10、访问控制合约5、重入合约5），原名S4基础上增加384维TEACHER及存在位，载体760→1145维。30份N-A S4零步初值均存在、SHA及摘要通过；全部共同参数逐位复制核验，4组载体/快路径与新建结构证明通过。已删除的60份历史best/last仅按封存预测和收据作指标参照，不宣称可重载。

独立N-C1接入获用户批准，复用冻结训练核心；继续条件未变，未达时仅说明预登记资源停止，不称学生不可能更好。4115测试通过，8H和354份冻结源码不变。本轮正式训练0/30，authorization.template=false，按PROMPTS §5.11等待单独训练授权；NS-P8b不自动运行。详细设计、选择、限制及实际命令见scripts/node_sem/NS_P8A_REPORT.md与NS_P8A_README.md。

历史30次S4共约1.60小时，S6尚未实测；重入合约历史最低空闲44MiB，OOM按原规则停止，不调整计算。最终实验将在显存充足服务器另建批次，本机4GiB仅属当前开发限制，不混合设备结果。本轮不自动push。


## 2026-11-08 NS-P8a N-C1获授权并后台启动（修改 AI：Codex）

用户明确授权“授权训练，可以在后台训练就行”。已新建execution_decisions、execution_revision与authorization，绑定原30项plan/seal；原authorization.template=false保持不变。后台控制器PID 725002，独立WSL会话、日志重定向、单GPU锁串行；已进入重入节点G3R/S6 fold0。此处记录为启动状态，尚非30项完成或效果结论。

启动前确认插电、禁睡眠、禁休眠，GPU空闲约3391MiB；没有修改Windows电源设置。训练沿用冻结配置和零步初值，OOM等错误停止并保留attempt，不自动重试、不启动NS-P8b。进度看scripts/node_sem/artifacts/batch_NC1_v1/controller_status.json，逐项日志与收据在runs/。正式服务器实验仍另建显存充足批次，本机限制不改变本轮计算。


## 2026-11-09 NS-P8a N-C1完成（修改 AI：Codex）

30/30次S6正式训练与收据验收完成，失败0、重试0；只读引用30个S4，60份S6 best/last完整。总墙钟约1小时46分钟。best BF1折均S6−S4：重入节点−0.0490pp（主比较p=0.9592）、访问控制节点+0.1617pp、访问控制合约−0.0638pp、重入合约+0.6437pp。

预登记继续条件由重入非SolidiFI pooled BF1的+0.6629pp触发：TP25→26且FP7→8，FN7→6；错误总数不变，不能宣称稳定增益，last该子集反降2.4420pp。访问控制非SolidiFI节点BF1 12.50%→34.48%，TP2→5、FP10→4，但仍漏15/20正例。32/20正例已按源码SHA和节点身份逐一对齐，学生阶段未启动。

只读报告入口与24项回归新增，全套4139项通过；375份运行源码、旧图/输入/计划不变，UTF-8记录检查继续执行。完整数字与边界见scripts/node_sem/NS_P8A_REPORT.md及batch_NC1_v1/reports/。最终服务器实验另建显存充足批次，不混合本机结果。准备报告已原样归档；本轮本地提交，不自动push或NS-P8b。


## 2026-11-09 NS-P8b N-C2学生与计划准备完成（修改 AI：Codex）

30/30个CPU学生蒸馏、全节点导出和诊断已完成；30项S5＋30项条件S8的逐折载体、零步初值和plan/seal已封存。正式HGT训练0次，授权模板false，按PROMPTS §5.11b等待本批独立训练授权。原名视图、S4/G3R、冻结标签/划分/配置保持。

学生outer教师余弦均值：重入节点0.895862、访问控制节点0.890985、访问控制合约0.890789、重入合约0.888804，均略高于原岭回归；这是向量拟合诊断，不是漏洞检测提升。学生全部节点存在，教师仅有效描述节点存在，后续S5/S6差异含覆盖变化。

用户批准3文件两折防泄漏测试、S5/S8共享全部初值与随机起点、完整验收后复用冻结S4载体与未训练结构。4196项回归通过，8H354与N-C1原375份源码不变；失败0/重试0。S8只在重入节点best的S5−S4等权折均差>0时全体运行，否则全体跳过。详情见scripts/node_sem/NS_P8B_REPORT.md、NS_P8B_README.md及batch_NC2_v1。

最终服务器实验另建显存充足批次；本机RTX3050 4GiB仅开发限制。本轮不启动下一阶段、不自动推送。


## 2026-11-09 NS-P8b N-C2获授权并后台启动（修改 AI：Codex）

用户明确回复“授权执行”。新增execution_decisions、execution_revision、authorization，绑定原plan/seal，原准备授权模板false保留。独立WSL后台控制器PID 743872，首项为重入节点G3R/S5 fold0；此处记录启动，不代表30项已经完成。

执行30项S5，全部验收后仅当重入节点best外层BF1的S5−S4等权折均差严格大于0时执行全部30项S8，否则全部跳过。保持原名视图、冻结初值/图/划分/训练配置，单GPU串行，错误停止保留现场且不自动重试。运行状态见scripts/node_sem/artifacts/batch_NC2_v1/controller_status.json。

启动前确认插电、睡眠及休眠超时均禁用，GPU空闲3514MiB；没有修改Windows设置或关闭其他程序。最终实验仍将在显存充足服务器另建批次，本机4GiB仅开发限制，不混合设备结果。


## 2026-11-09 NS-P8b N-C2完整训练与汇总完成（修改 AI：Codex）

60/60次正式拟合及验收完成（S5/S8各30），失败0、重试0，后台墙钟约3小时35分钟。原名G3R/L-audit，30个S4及30个S6只读参照；best折均BF1的S5−S4：重入节点+0.008145pp、访问控制节点+0.177842pp、访问控制合约−0.948617pp、重入合约−0.045977pp。主比较Holm p=0.645603，S5−S8为0.273677，没有稳定主任务改善的证据。

非SolidiFI节点best：重入TP仍25、FP7→9，BF1下降；访问控制TP仍2/20、FP10→0，主要减少误报，仍漏18/20。S5未保留教师的召回收益；best与last部分方向不同。完整表、逐节点变化及资源见NS_P8B_REPORT.md和batch_NC2_v1/reports/，原准备报告已原字节归档。

新增只读nc2_reporting.py及21项报告测试；完整4217测试通过。8H/N-C1/N-C2冻结源码及旧计划不变，S4删除的60份历史权重不宣称可重载。最终显存充足服务器另建批次，本机4GiB仅开发限制；本轮停止，不自动下一阶段或push。


## 2026-11-09 NS-P9 本机NodeSem只读汇总完成（修改 AI：Codex）

汇总450次已有正式拟合、900条best/last折记录，660条历史重复引用和来源聚合逐位一致；无新训练/正式推理/LLM/特征。按用户批准将S3m标为未运行，S4-noG保留G0、零HGT层真实身份。报告见scripts/node_sem/NODESEM_REPORT.md，机器表与SHA见scripts/node_sem/artifacts/summary_NS_v1/。

六配置共同漏报：重入6、访问控制15个HCG正例；访问控制S5相对S4去掉10个非SolidiFI误报但仍漏18/20正例。21例均核对源码AST、STATIC/facts、标签来源、G3R消息路径及每折训练支持，不能统一归因于缺边：有的缺modifier/调用效果，有的已有敏感操作和状态信息。初步分类不是因果结论，也不改标签。

S2对S0o在原主终点Holm p=0.03906；S4对S0o p=0.07422；S5对S4 p=0.64560，未证明稳定学生增益。保留原家族，不新增检验；S0o/S2/S4/S5/S6仅列为下一基线候选，由用户决定。三套回归、冻结8H/354计算源码与UTF-8检查记录随批次交付。

最终实验将在显存充足服务器另建批次；当前4GiB限制仅属本机。N-A权重已删除，只引用封存预测。本轮本地提交后停止，不自动push、训练或扩展关系。

验收补记（Codex）：最终1353+2653+223=4229项回归通过，新增NS-P9测试12项；独立summary_verify.py重新核对899份来源（1,982,269,021字节）、原节点身份及折、概率、旧文档前缀和354份冻结计算源码。新增验证入口未加载任何正式模型；合成回归中的前向不计为新增正式实验。


## 2026-11-10 EdgeSem EP0侦察完成（修改 AI：Codex）

按scripts/edge_sem/PROMPTS.md r3完成输入、四任务语义覆盖和CPU接入侦察；已获用户授权快进同步edge-sem至ce8fa93a。EP0仅新增侦察脚本/报告与记录，无正式训练、GPU运行、optimizer step或F4图生成；DFG、NodeSem、作者代码和旧产物保持。

重入/访问控制节点：merge→typed关系数212→220、225→234；每层增加32832/36936参数。可投影next_line回边26/29，按50门槛均不启用cf_back；L1无strong/weak字段，第15位保持0。MOD_APPLY预计178/195正向边，CALL_SITE180/186；当前可映射GUARDS6305/3787。modifier守卫616/715条全部无法映射：冻结_anchor实际指向modifier_invocation，非修饰器体内守卫。

A原样重建state/前向逐位一致；B typed前后向和梯度通过，但旧checkpoint深验不接受typed拓扑；C随机同文件边仅估算CPU规模，峰值RSS约2878.14MiB，不代表GPU显存或完整G4R上界。384/384匿名临时代码副本映射一致，未改变主视图政策。

报告RECON.md/recon.json列出六项接口/来源差异；后续需确认modifier来源、独立绑定适配和属性来源规则，本轮停在EP0，不自动进入EP1。D1匿名主视图、D2跑满50轮、D3七类冻结仍未获本轮批准。测试与哈希见artifacts/ep0_v1/verification.json；本地提交，不自动push。

最终实验将在显存充足的服务器另建批次；当前RTX3050 4GiB只限制本机开发，服务器尚未在本轮部署或验收，不混合两处成绩。


## 2026-11-10 EdgeSem EP0b完成，CALL_SITE门槛未通过（修改 AI：Codex）

按PROMPTS r4完成modifier内层来源、调用覆盖和属性计数。guard_source.py与冻结_modifiers在四任务12285个函数实例上记录序列、unresolved/audit完全一致；两节点任务616/715条modifier守卫均精确映射，预计GUARDS正向总数6921/4502（只计数）。

internal_call覆盖178/464、197/591；扣除无表达式76/76后45.88%/38.25%，低于预登记80%。停在EP0b，不自动实现后续调用边或训练；需审查范围排除、AST形状和HCG对应关系。诊断分类修正了取反/组合上下文调用的定位，首轮输出、源码与逐条变化均保留，EP0候选和门槛不改。

r4类型解析成功率89.57%–99.03%，未确认项保留unknown；真实shape_safe差异为空，反例测试通过。34+1353+2653=4040项测试通过，冻结代码/输入与EP0产物保持。详见RECON.md§9、ep0b_v1/summary.json与verification.json。

最终实验在显存充足服务器另建批次，本机RTX3050 4GiB仅限制开发；本轮未部署服务器、未训练。本地提交，不自动推送。


## 2026-11-10 EdgeSem EP0c完成，未知比例门槛未通过（修改 AI：Codex）

按 PROMPTS r5 完成 call_resolve.py（冻结绑定＋库函数＋裸标识符重载参数个数消歧）及两个节点任务的只读参照集审计。独立产物 scripts/edge_sem/artifacts/ep0c_v1；RECON.md §10 给出完整口径。未生成 F4、属性向量或训练结果。

重入/访问控制：参照集 internal_confirmed 221/229，r5 投影覆盖 219/221=99.10%、227/229=99.13%；但 unknown 占比 54/221=24.43%、53/229=23.14%，超过20%，因此停止 EP1 准入。约99%只是已解析集合内的投影覆盖，不是语义召回。主要缺口是复合 callee、同参数数目重载及 super；没有自行扩大解析或改门槛。

语句级候选322/321，较EP0增加142/135（库139/132＋重载3/3）；只计数不写边。各2条已绑定调用在emit语句缺精确投影。r5粗分类208/329未完整复现，严格对照181/301；原粗分类逐边清单未提供，报告保留全部1055条新旧类别与身份，不虚构对应差异。

59+1353+2653=4065项CPU回归通过，旧DFG、NodeSem、作者代码和历史输入/产物保持。开发AST接口失败日志与初版源码保留；正式核验无自动重试。详细选择、限制和命令见训练变更文档§101与verification.json。本轮本地提交，不自动推送。

最终实验将在显存充足的服务器另建批次；RTX3050 4GiB仅是当前本机限制，本轮未部署服务器。D1/D2/D3及进一步解析扩展仍须后续审查。


## 2026-11-10 EdgeSem EP0d完成，调用覆盖门槛通过（修改 AI：Codex）

按PROMPTS r6完成复合callee后缀绑定，并按用户批准增加受限address_builtin接收者适配。冻结NodeSem/DFG/作者代码未改，EP0c产物保留，新证据写入scripts/edge_sem/artifacts/ep0d_v1，报告RECON.md §11。

重入/访问控制分别有38/39条原未确定HCG调用边得到准确目标；已确认参照集259/268，投影覆盖257/259=99.23%、266/268=99.25%，未确定比例16/259=6.18%、14/268=5.22%。80%/20%两项原门槛均通过。候选360/354，较EP0c新增38/33；旧候选与旧成功绑定全部保留。99%是已确认集合内的投影覆盖，不是语义召回或检测F1。

6707项普通callee绑定与冻结解析器完全一致；完整CPU回归75+1353+2653=4081通过。首次receiver测试失败及获批修复保留，详细选择见训练变更文档§102。剩余同参数个数重载、super、少量接收者不确定项和emit投影缺口没有猜测补边。

本轮没有建图/属性向量/正式训练，完成本地提交后停止，不自动EP1或push。最终实验在显存充足服务器另建批次，本机RTX3050 4GiB仅限制当前开发。


## 2026-11-10 EdgeSem EP0e实现与审计完成，库召回门槛未通过（修改 AI：Codex）

按 edge-sem 最新 r7（起点 `6e95c9d7`）实现受限接收者类型、using-for 解析、call_option 和 ABI 分类。用户批准只修正 `using L for *` 的 source 比较，首参数类型等约束不变，冻结 NodeSem/DFG 未改；授权与例外均已记录。

两个节点任务各绑定 **312/347＝89.9135%**，未达预登记 90%，候选集外绑定均为 0。各新增 188 个语句级 CALL_SITE 候选，旧已解析目标保持不变，EP0d 两项覆盖门槛仍通过。停止在 EP0e，不自动进入 EP1；不能把本轮称为阶段准入通过。

三套 CPU 回归共 **4,121 passed**。详细结果与剩余 35 项原因见 `scripts/edge_sem/RECON.md` §12，证据见 `scripts/edge_sem/artifacts/ep0e_v1/`。本轮无训练、无生产图或属性向量，历史产物、输入与四份旧文档内容保持不变；按共享流程本地提交，本轮不推送。

最终实验将使用显存充足的服务器；当前 RTX3050 4GiB 仅为本机开发限制。本轮产物仍在 WSL，不向 C 盘另存大文件。


## 2026-11-10 EdgeSem EP1结构接入与等价闸门完成（修改 AI：Codex）

依据 PROMPTS r8、起点 a71b2bc1，实现8剖面注册、typed显式REV_、语义参数复制与独立模型深校验。重入节点fold0/9关闭增强时，规范键、端点、全部参数和eval前向逐位复现原G3R；两任务G3R-T均完成CPU前后向且有限，未训练、optimizer step=0、未用GPU。

重入typed关系220、参数5,176,676；访问控制234、参数5,291,588。三套回归149+1353+2653=4155通过。详见scripts/edge_sem/EP1_REPORT.md、artifacts/ep1_v1及PROGRESS中的完整低支持关系清单。首次新registry漏if_true/if_false的失败日志保留，修复仅增加control别名。

旧DFG/NodeSem/作者代码、输入和历史产物不改；三文档只追加。8H N-anon-s仅作为本次等价验收的历史夹具，不决定后续主视图。dfg_profile=G3R记录锚来源，edge_profile记录实际结构；typed不绕过冻结checkpoint，正式绑定留EP7。

EP0e 312/347的历史库召回门槛仍未通过；r8允许独立EP1，本轮没有实施或批准EP2的解析调整。属性/安慰剂模型仅注册且当前入口拒绝构造，cf_back仍禁用。按流程本地提交，停在EP1，不自动push或训练。

最终实验将在显存充足服务器进行；RTX3050 4GiB仅为当前本机开发限制，本轮不部署服务器。产物保留WSL，不向C盘另写大型缓存。


## 2026-11-10 EdgeSem EP2完成：修饰器应用与调用站点边（修改AI：Codex）

按PROMPTS r9完成调用解析修正及MOD_APPLY/CALL_SITE构建，报告scripts/edge_sem/EP2_REPORT.md，独立证据artifacts/ep2_v1。重入71个文件实例生成178+570=748条正向边；访问控制57个文件实例生成195+564=759条。原节点、原边、属性、F3文件和所有冻结代码/历史产物保持。

冻结using候选各从312/347增至334/347（96.2536%），候选集外绑定0，旧成功绑定558/558及552/552不变；EP0d两项门槛继续通过。r9预计18个直接修复，既有递归类型推断自然另恢复4个链式调用，用户已批准保留实际22个新增与13个剩余。历史EP0e门槛仍记失败，新值只作事后描述。

用户另批准冻结Projector仅读取label中的AST结构身份；建边不使用漏洞标签或预测。add_edges返回独立深拷贝，JSONL保留精确锚点、kind与重复调用证据。每任务2个绑定调用缺图节点、9个modifier绑定失败等均留审计，不猜测补边。三次开发测试失败现场与修正记录保留，详见训练变更文档§105。

两任务G4R空E1与G3R-T逐位等价；加边后canonical数232/246、参数5,275,172/5,390,084，共享参数与新关系语义种子均通过，CPU前后向有限、optimizer step=0。三套回归177+1353+2653=4183通过。8H特征只作历史等价夹具，不重新决定匿名主视图。

本轮没有训练或GPU运行，尚不判断检测改善；GUARDS、边属性与后续模型/训练接入待各自Prompt，停在EP2。本地提交，不自动push。最终实验将在显存充足服务器另建批次；当前RTX3050 4GiB仅为本机开发限制。本轮产物留WSL，未另占C盘大文件。


## 2026-11-10 EdgeSem EP3完成：GUARDS接入（修改AI：Codex）

按PROMPTS r10完成GUARDS构建。重入71个文件实例得到6921条GUARDS，访问控制57个文件实例得到4502条；6956/4537条记录逐文件复现EP0/RECON，非修饰器和修饰器均100%精确映射，无自环或映射缺失。EP2的MOD_APPLY/CALL_SITE逐行不变，完整E1共7669/5261条正向边。

每任务31条多证据边均为internal_check，35条重复记录保留在evidence。12个unknown目标未被过滤，其中2个仍保留已确认边；9个未解析modifier应用均确认为基类构造调用，只补描述。全部F3节点GUARDS平均入度0.566228/0.570451，中位0，最大13；最大值都在各任务buggy_24.sol的invest，source SHA不同，报告已分开列出。

用户批准显式EP2归档核验（call_77a0cd9dcd464ce3b3ab20d7ad8bb54f），核对旧收据与改动前源码快照，旧manifest/seal不改，默认生产加载仍严格检查当前源码SHA。第一次小测试的构造函数描述查询错误已修正，失败现场保留；冻结解析器及边选择规则未变。

两任务G4R规范关系274/292、参数5,619,908/5,767,652；空E1逐位等价、共享参数、新关系语义种子和有限前后向全部通过。完整CPU回归共4204项通过，optimizer step=0，未用GPU。旧图、标签、特征、DFG/NodeSem/作者代码及历史产物保持。

详见scripts/edge_sem/EP3_REPORT.md、artifacts/ep3_v1和训练变更文档§106。GUARDS仍是有界词法证据，不证明访问控制或检测收益；边属性与EdgeAware层留后续，停在EP3。本地提交，不自动push。最终实验将在显存充足服务器另建批次，当前RTX3050 4GiB仅为本机开发限制；本轮产物留WSL。


## 2026-11-10 EdgeSem EP4完成：通用F4与74维属性（修改AI：Codex）

按PROMPTS.md r11完成EP4：通用F4构建、74维边属性、两任务端点检验与共同核心位。属性从原名源码、冻结事实和封存L1–L3证据计算；反向边留模型接入时复制正向向量。本轮未训练、未用GPU，没有检测性能或显存结论。旧图、标签、折、特征、初值、checkpoint和计划不改。

| 任务 | 属性行 | 全零行 | 全零比例 | 诊断行 |
|---|---|---|---|---|
| access_control_node | 21830 | 2728 | 12.497% | 9530 |
| reentrancy_node | 31372 | 2786 | 8.881% | 14562 |

核心46维，上下文26维，unknown位可共享。两个节点任务F4与EP3逐字节一致，两合约任务只作构建冒烟。两次属性失败保留，用户批准后在第三目录完成；全部调整、统计与命令见scripts/edge_sem/EP4_REPORT.md及训练变更文档§107。

冻结代码/历史产物、8H load与DFG引用核验通过，三套CPU回归和文档检查完成。后续EP5/EP6未执行，D1–D3尚待训练前确认。最终实验将在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机限制；产物留WSL。本地提交，不自动push。


## 2026-11-11 EdgeSem EP5完成：不变性、可达性与安慰剂（修改AI：Codex）

完成EP5，未训练或用GPU。第20位重入311→61、访问控制322→68；edge_keys及其他73列严格不变。核心46→50，新增全零候选6/14/33/38，上下文26维不变；后续EP6–EP9读取ep5_v1/attributes。

128个实例均检查通过：54个实际改名、74个原文回退；回退不作为非平凡不变性证据。用户批准状态初始化callable和唯一neg_next/AST锚定end_if适配，冻结模块未改。49条循环头上下文例外保留；统计按历史store双摘要修复后在新目录恢复。所有失败、快照和批准记录保留。

21例中，重入modifier_reentrancy.sol节点8498及reentrancy_bonus.sol节点12各增加2个两跳证据节点；其余19个不变，访问控制15个均无增量。仅为路径诊断，不证明检测改善。两种安慰剂分别保持逐节点canonical度数和关系内属性多重集，未变化的分组和向量均披露。

三套CPU回归4274项通过。详见EP5_REPORT.md、训练变更§108及ep5_v1/verification.json。最终实验在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机限制；产物留WSL。停在EP5，本地提交，不自动push。


### EP5 收尾验收修正与恢复批准（2026-11-11，Codex）

报告写入曾两次遇到自动审批服务超时；经正常审批的短WSL命令及临时文件写入/回读/删除成功，改为分段写入后已恢复。未修改审批、沙箱或代理设置，服务端根因没有证据，不能称审批服务本身已修复。

最终验收首次因逐文件数字摘要的行顺序不同而停止：原闸门使用文件子图遍历顺序，验收器错误使用整图过滤顺序。只读核对发现80/128个文件顺序不同；恢复原生成顺序后128/128份封存摘要全部匹配，边身份和向量不变。新增3项定向回归通过，覆盖顺序差异、向量篡改/缺失及空文件。原三套回归4274项通过记录保留。

用户批准保留首次验收收据、旧验收器及诊断，在verify_attempt2收据下继续最终验收和本地提交。批准见ep5_v1/verification_resume1.json；最终结果见execution/verify_attempt2.json和verification.json。未重算属性、未重跑匿名闸门、未训练。EP5_REPORT.md及initial summary保持写入时字节；本段补充其后发生的验收修正。


## EP6完成：r14前置修正与边感知HGT（2026-11-11）

已完成四任务f4_v2、两节点任务新属性和名字不变性核验，接通G4R-A / G4R-Api / G4R-AC / G3R-TA。用户批准call_1c4fc0064fb94266be56b656e6399928，按封存符号调用冻结sink补齐参数入口，已有记录严格比对。原图、旧产物与冻结实现保留。报告：scripts/edge_sem/EP6_REPORT.md。

四任务F4边集合均不变；访问控制合约的1个fallback修饰器绑定成功，但冻结投影为not_in_graph，因此未加边。补齐重入1,727条、访问控制2,941条边；仅指定列0→1，其余逐位相同。实际改名54文件通过，74回退只作原文对照；core/context仍50/26位。

真实重入fold0 CPU：新增92,784参数、零初值最大差0、前向1.43秒、反向2.28秒，共享参数逐位一致，optimizer_steps=0，未用GPU。最终4,300项测试通过（EdgeSem294、NodeSem1353、DFG2653）；归档SHA失败保留，修复只读快照核验后定向复核。没有正式训练或检测收益结论。

最终实验将在显存充足的服务器运行；当前限制仅来自本机。EP7须独立计划与授权，本轮本地提交，不自动推送。


## 2026-11-11 — EdgeSem EP7 实现与训练前封存

已完成 G4R-P、P2 执行器及训练前 CPU 验收；报告 scripts/edge_sem/EP7_REPORT.md，命令 scripts/edge_sem/EP7_README.md。尚未启动 GPU：探针0/8、范数试点0/1、正式G3R 0/20，D1–D3和本轮训练授权待确认。registration.json须先提交；计划保持execution_authorized=false，批准后另建decisions和执行授权，不修改旧seal。

用户批准call_fa9553b4bee0410b8b1dfa2fcc7c490b的两项接入调整：冻结trainer无校验替换接口，允许EdgeSem中带来源SHA的最小适配副本（只换校验/审计导入）；范数试点另设train_only，禁止验证/测试评分及best选择。正式_fit/fit的AST与原版相同，小图CPU三轮参数、损失、预测、Adam及OneCycle状态逐位一致。冻结源码、图、标签、折和历史产物未改。

三套回归4318通过（EdgeSem312、NodeSem1353、DFG2653）。两任务G4R-P逐节点规范度数保持，初值与G4R逐位相同；改边5834/7669与3487/5261。26份零步初值已封存并重载，约524.6 MiB，本地权重不纳入普通Git上传。核验750份冻结源码、1134份历史产物，8H入口仍通过，历史文档前缀不变。

本轮新鲜G3R锚初值与8H配对初值不同，按原设计保留；将来与8H只作描述性对照，不能把差异全归因于P2取消早停。P2有效配置只改patience 7→51，完整50轮、严格最低inner_val loss选best。D1提案为N-anon-s主视图（不是沿用NodeSem原名主视图的授权）；D2为P2及新G3R基线；D3为EP9后冻结并供七类复用。

最终实验将在显存充足的服务器运行，当前限制仅来自本机RTX3050 4GiB。后续若获授权，依次运行8个单轮显存探针、1个50轮仅训练范数试点、20个G3R正式fit；资源/数值/输入错误即停，不自动重试，不自动进入EP8/9。只进行本地提交，未获推送指令。


## 2026-11-11 — EP7改为原名主视图并获顺序训练授权

用户在call_f3878be032dc4782ae2d23b4a5711b9b选择“先调整主视图，再封存执行方案”，同时授权8个GPU探针→1个50轮范数试点→20个G3R正式fit。结合此前明确的原名主视图要求，D1改为original S0；D2的P2与D3的EP9冻结规则保留。匿名接口保留，本轮不执行匿名计划。原始答复与解释见ep7_original_v1/user_decision.json。

新建scripts/edge_sem/artifacts/ep7_original_v1，保留ep7_v1及旧registration/plan/seal/初值不变。原名特征从8H封存source_preparation索引取得，复用冻结assemble；两任务分别12036/7710行，其中11224/7436行向量相对匿名视图改变。图、节点、标签、划分、边属性、配置和种子不变。26项原名准备全部证明新构造参数与旧零步初值逐位一致，直接复用26份旧初值，没有新增权重文件。

原4318项回归保留，本轮26项定向测试通过；封存后G3R和G4R-A真实CPU装配/绑定通过。旧3个匿名计划只读核验通过，299份旧EP7文件、750份冻结源码和1134份更早产物均不变。新runtime共382项（28 EdgeSem+354冻结）。新P2登记提交后另写decisions/执行授权，再实际启动；不需要重复索取本轮顺序训练授权。

报告：scripts/edge_sem/EP7_ORIGINAL_REPORT.md。与8H比较同时涉及视图、初值、停止规则差异，只能描述，不作单因素归因。最终实验在显存充足的服务器运行，当前限制仅来自本机；未自动授权EP8/9或GitHub推送。


## EP7 原名主视图执行完成（2026-11-11）

8/8显存探针、1/1 G4R-A 50轮范数试点、20/20正式G3R全部完成验收。正式各50轮，共1000轮，无训练失败/重试。原名S0主视图，匿名接口备用。best BF1十折均值±样本SD：重入99.729±0.206%、访问控制99.203±1.080%；last分别99.788±0.171%、99.568±0.269%，主结果仍取best。

报告：scripts/edge_sem/EP7_ORIGINAL_REPORT.md；逐折/OOF：scripts/edge_sem/artifacts/ep7_original_v1/results/；资源、独立复算和完整性收据：同批次completion_attempt2/。当前是后续边增强需要的新G3R基线，尚未证明边增强分类收益。与8H差值同时受原名/匿名、初值和停止规则影响，仅描述。最终实验上显存充足的服务器，本机限制仅属本地试验。未启动EP8/EP9，未推送GitHub。


## 2026-11-11 — EP8 原名主批与匿名敏感性批：登记及准备恢复

按用户更新的 PROMPTS r16 继续 EP8。原名是唯一主终点：2个节点任务×3个剖面（G3R-T、G4R、G4R-P）×10折，新增60次；复用EP7原名G3R的20次。N-anon-s为描述性敏感性批：2×4剖面×10折，新增80次，不进入Holm族。先主批再敏感性批，独立plan/seal/authorization，不自动进入EP9。选择原文“Original + anonymized check”及来源已写入ep8_v1/decisions.json，新登记在protocol_p2/registration.json，历史EP7文件不改。

用户已批准两项接入：call_068df1e5a5b44c43930a9e7fb1018a34允许显式区分E-A主批/敏感性批，保留旧EP7校验分支；call_545e729cd68640a39272d166dc807d0e允许仅在CPU准备中从未训练原名模型安装封存匿名token，每个任务/剖面先对比完整装配，逐位核对参数、特征、边张量、图指纹、绑定及support。正式训练仍独立进程、使用原完整装配和冻结数值路径。

当前已验收EP7的20个原名基线，三套CPU回归通过：EdgeSem 340、NodeSem 1353、DFG 2653；优化后的定向测试37项通过。初始准备目录保留16份完整job记录，其中6对双视图已完成；经用户批准停止旧CPU准备，在preparation_attempt2继续，绝不覆盖旧产物。首个重入G3R-T真实装配一致性已通过，其余证明及140项准备仍在运行，尚无EP8正式fit结果。

恢复入口：python -B -m scripts.edge_sem.recon.ep8_run prepare --root scripts/edge_sem/artifacts/ep8_v1 --preparation-name preparation_attempt2。该命令已在独立后台进程运行，勿重复启动；查preparation_attempt2_process.json与同名log。完成后将写preparation_index.json指向验收通过的新索引，再封存两批计划。任何失败保留现场并停止，不自动重试。

最终实验将使用显存充足的服务器；当前显存限制仅来自本机RTX3050 4GiB。本批只做两个节点先导任务，不自动扩展合约任务、其余类别、seed或模型。当前未推送GitHub。


EP8恢复补记：同一recon入口增加finish-preparation后台衔接，等待已批准的CPU准备结束；只有六组逐位证明、80份唯一零步初值、三套回归、39项最终定向检查和冻结文件核验通过，才封存并按本轮“实现EP8、继续中断任务”的指令生成独立执行授权。登记提交在授权之前。衔接直接调用既有seal/authorize/run与执行器，不另造训练路径；失败与重复启动反例通过。全部初值及准备记录完成前不启动GPU拟合。此处记录的是执行顺序，不是结果已完成。


## EP8 GitHub 同步快照（2026-11-12 06:01 UTC）

140项初值准备及CPU验收已完成，6组真实任务/剖面的快捷装配与完整装配逐位一致。两个计划分别封存为原名主批60次和匿名敏感性批80次。后台当前正在执行原名主批；本次固定快照收录11个已完成正式拟合，匿名批为0个。该数量仅表示快照时刻，不是EP8完成结论；最终报告尚未生成。

同步范围包括已提交的EP8实现、测试及文档，以及准备索引、初值身份摘要、独立计划/seal、执行授权和上述11次的完整文本收据、预测、指标与资源记录。逐份核对收据/seal、任务归属和所有收据产物SHA（含仅留本地的权重）；没有重训或修改运行代码。未完成attempt、活动日志和锁不纳入快照；pt权重/初值张量仍保留本地，不上传。明细见 scripts/edge_sem/artifacts/ep8_v1/github_sync_20261112T060127Z.json。

后台仍按原名60次验收后再执行匿名80次的既定顺序运行，失败停止，不自动重试。最终实验将在显存充足的服务器运行；当前资源限制仅来自本机，本次未更改模型、训练设置或批次身份。


## EP8 E-A 完成验收（2026-11-13 UTC）

训练与汇总均已完成：原名主批60/60、N-anon-s敏感性批80/80，另只读复用EP7原名G3R的20份结果，总计160份正式结果。两批complete、pipeline_complete与followup_complete均为passed=true，后台进程已退出；最终报告于2026-11-12 20:27 UTC生成。本节取代前文“仍在训练”的时点状态，不改历史记录。

结果采用节点级L-audit、10折seed1、P2完整50轮，best主终点、last辅助，不是合约级或论文同协议复现。原名G4R−G3R-T的best BF1：重入+0.0188pp、访问控制+0.3986pp；匿名分别+0.3083pp、+0.1328pp。重入H1两项均值均正，但原名H1原始p=0.1996767915，匿名描述性p=0.16015625；均不能宣称H1显著，Holm等待EP9的H2，匿名不进入检验族。访问控制last不保持全部优势。匿名nonSolidiFI重入G4R pooled best BF1=63.1579，低于G3R的72.7273和G4R-P的75.0000；不能以整体高分宣称困难样本或泛化已解决。

交付：scripts/edge_sem/EP8_REPORT.md；ep8_v1/results/内的逐折、均值、配对、零差折、错误变化、pooled混淆矩阵、SolidiFI分层及Wilson P/R区间、词法与两条无学习边规则、非SolidiFI逐节点、持续案例与资源表（JSON/CSV），以及封存summary。新增最终复核记录保存本轮完成链和报告SHA；已核验160份收据/seal、汇总表及分析/评分源码SHA。CPU执行 ep8_run frozen 成功，冻结源码、历史产物、旧_code_refs及文档前缀仍保持。此前340项EdgeSem、1353项NodeSem、2653项DFG回归及39项最终定向测试的证据保留；本次收尾只追加文档和验收记录，没有改变训练代码或重复拟合。

保留所有历史attempt和已批准调整。此处停止在EP8，不自动启动EP9；EP9视图安排等待用户确认。最终七类实验将另建显存充足的服务器批次，当前资源限制仅属于本机。权重保留本地，完成报告与收尾记录本地提交，尚未进行新的GitHub推送。


## EP8 最终同步与 r17 记录更正（2026-11-13 UTC）

已合并远端PROMPTS r17审查更新。按其要求新增 github_sync_20261112T060127Z.correction.json，逐一核验并更正早期11条同步索引的剖面身份：原profile字段是DFG基础剖面job.profile，实际EdgeSem剖面为job.edge_profile。原快照字节保持不变，正式收据和分析本来即使用正确的edge_profile，因此训练与结果均不受影响。最终同步清单统一明确记录edge_profile与base_profile。

本次补齐此前未同步的129次完整文本结果，覆盖原名60次和匿名80次全部完成训练；2800份收据绑定的文本产物SHA核验通过。最终清单见 ep8_v1/github_sync_final_20261113T010949Z.json，包含剩余预测、best/last指标、审计、history、资源记录及上述更正。权重、零步张量、锁和空进程日志仍留本地；没有启动训练或修改已有计划/seal。此次仅记录层更新，不重复运行训练回归。
