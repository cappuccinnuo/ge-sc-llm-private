1. 研究目标与核心思想

MANDO-LLM 的目标是利用 异构程序图 + HGT + LLM Tokenizer 节点语义特征进行智能合约漏洞检测，并同时支持：

合约级检测（coarse-grained contract-level detection）：判断整个智能合约是否存在某类漏洞；

行级检测（fine-grained line-level detection）：在已判定为可疑的合约中进一步定位具体漏洞语句或代码行。

该方法并不是直接将 Solidity 源码输入完整的大语言模型，也不是仅仅将 CFG 输入普通 GNN，而是将程序结构信息和代码语义信息分开建模后再融合：

Solidity Source Code
        │
        ▼
    Tree-sitter
        │
        ▼
        AST
        │
        ├───────────────┐
        ▼               ▼
       CFG              CG
        │               │
        └───────┬───────┘
                ▼
     Heterogeneous Graph Fusion
                │
                ▼
              HCG
                │
        ┌───────┴────────┐
        ▼                ▼
 Meta Relations      Node Code Snippets
        │                │
        │                ▼
        │         LLM Tokenizer
        │                │
        │                ▼
        │          Node Features
        └───────┬────────┘
                ▼
          MANDO-LLM GNN
              (HGT)
                │
                ▼
         Node Embeddings
                │
        ┌───────┴─────────┐
        ▼                 ▼
 Contract-level       Line-level
 Classification      Classification

MANDO-LLM 的关键点在于：

使用 Tree-sitter 从源码构造 AST，降低对 Solidity 编译环境和具体编译器版本的依赖；

将 CFG 和 CG 转换为异构图并融合为 HCG；

动态抽取 <源节点类型, 边类型, 目标节点类型> 元关系；

不使用完整 LLM Encoder，而只使用预训练 LLM 的 Tokenizer 为每个图节点的代码片段生成节点特征；

使用 HGT 学习异构节点、异构边和代码语义之间的关系；

使用同一套 HGT 节点表示支撑合约级检测和行级定位。

2. MANDO-LLM 的五个核心组件

论文将整体框架划分为五个组件：

HCG Generator

Meta Relations Extractor

Node Features Extractor

MANDO-LLM GNN

Two-Phase Vulnerability Detector

下面按照实际实现顺序展开。

3. HCG Generator：从 Solidity 源码生成异构合约图

3.1 输入

HCG Generator 的输入为一个或多个 Ethereum Solidity 智能合约源码文件。

论文采用 Tree-sitter 及其增量解析能力，将 Solidity 源码首先解析为 AST。

Solidity
   │
   ▼
Tree-sitter
   │
   ▼
AST

与依赖 Solidity 编译器的静态分析前端相比，这种方式的主要目的在于降低：

Solidity 编译器版本冲突；

工程依赖缺失；

项目编译环境配置成本。

3.2 从 AST 构造异构 CFG（HCFG）

从 AST 中提取预定义的程序语句类型作为节点，并按照控制流建立有向边，从而形成每个函数对应的 CFG。

论文强调这里构造的不是普通同构 CFG，而是 Heterogeneous CFG（HCFG）：

G = (V, E, τ, φ)

其中：

V：节点集合；

E：边集合；

τ(v)：节点类型映射；

φ(e)：边类型映射。

因此，不同语句类型在图中仍然保持各自的 node type，而不是全部退化成同一种 statement node。

一个简化示例如下：

function withdraw(uint amount) public {
    if (balances[msg.sender] >= amount) {
        msg.sender.call{value: amount}("");
        balances[msg.sender] -= amount;
    }
}

可抽象为：

FunctionDefinition
        │
        ▼
   IfStatement
    /       \
 TRUE       FALSE
  │
  ▼
ExternalCall
  │
  ▼
Assignment

因此 CFG 同时保留：

语句本身的程序结构；

节点类型；

顺序和分支控制关系。

论文说明 HCFG 是按函数生成的，即每一个函数首先形成自己的局部控制流图。

3.3 从 AST 构造异构 CG

CFG 只描述函数内部控制流，无法完整表达跨函数调用，因此 MANDO-LLM 同时构造 Call Graph。

论文区分两类主要函数调用：

Internal Call：同一个智能合约内部函数之间的调用；

External Call：跨合约的函数调用。

CG 用于描述：

Caller Function
      │
      └──────── call ───────► Callee Function

同时，为了区分合约、合约内函数、外部函数和 fallback，论文在 CG 中保留不同类型的节点。

特别地，论文显式强调 fallback 函数节点，因为 fallback 与多类 Ethereum 漏洞尤其是重入行为存在紧密关联。

一个简化例子：

Contract
 ├── withdraw()
 │      │
 │      ├── internal call ──► check()
 │      │
 │      └── external call ──► ExternalFunction
 │
 └── fallback()

4. CFG + CG 异构融合：生成 HCG

4.1 为什么必须融合

单独的 CFG 只能看到函数内部控制流；单独的 CG 只能看到函数之间调用关系。但漏洞模式通常同时依赖这两种信息。

例如重入漏洞可能需要同时理解：

withdraw()
   │
   ├── 调用了外部函数
   │
   └── 外部调用之后仍有状态更新

所以仅看单个函数的 CFG 或单纯的函数调用关系都不足以覆盖完整上下文。

4.2 融合方式

论文中的 Heterogeneous Graphs Fusion 通过连接 CFG 与 CG 中代表同一函数的 function 节点完成融合。

抽象表示：

CG:

withdraw() ─────────► transfer()
   │                    │
   │                    │
fusion                fusion
   │                    │
   ▼                    ▼

CFG-withdraw        CFG-transfer

withdraw()           transfer()
   │                    │
   ▼                    ▼
 statement           statement
   │                    │
   ▼                    ▼
 statement           statement

融合以后：

HCG = HCFG + heterogeneous CG + function-node alignment

最终得到一张统一的 Heterogeneous Contract Graph（HCG）。

该图能够同时编码：

函数内部控制流；

跨函数调用；

跨合约外部调用；

不同程序实体的节点类型；

不同关系的边类型。

论文默认后续实验采用 CFG + CG 的融合图形式，而不是仅使用某一种单独图。

5. Meta Relations Extractor：动态构造异构关系

5.1 Meta Relation 定义

对于一条有向边：

s ──e──► t

MANDO-LLM 不仅记录 edge_type，而是将：

源节点类型；

边类型；

目标节点类型；

组成一个三元关系：

< τ(s), φ(e), τ(t) >

例如可抽象为：

<IfStatement, TRUE, Expression>
<Expression, NEXT, Expression>
<FunctionDefinition, InternalCall, FunctionDefinition>
<FunctionDefinition, ExternalCall, ExternalFunction>

因此即使两条边使用相同 edge type，只要源节点类型或目标节点类型不同，它们在 HGT 中仍可成为不同的 canonical/meta relation。

5.2 为什么使用动态 Meta Relation

传统 heterogeneous graph 方法经常需要手工预定义 metapath。

MANDO-LLM 不手工枚举所有路径，而是根据当前实际合约图中出现的节点类型和边类型动态发现 meta relation。

论文给出的规模上限为：

最大 Node Types = 18
最大 Edge Types = 5

因此理论最大元关系数量：

18 × 5 × 18 = 1620

但一个具体合约实际只会出现其中一小部分，论文观察到每张图实际可能只有几十到几百种 unique meta relations。

这些关系在训练过程中动态抽取，并直接作为 HGT 层的结构输入。

5.3 Reflective Relations

MANDO-LLM 还会针对相邻节点引入反向/reflective relation。

如果存在：

A ──r──► B

则还考虑相反方向的关系：

B ──r'──► A

目的不是修改程序真实执行语义，而是增强 HGT 消息传播，让节点能够从更多邻居获得信息。

论文指出 HCG 大体具有树状结构，仅存在少量由循环相关语句产生的 back-edge。若不补充反向关系，大量只有单个源邻居的节点在 HGT 信息传播中可能得不到充分利用。

6. Node Features Extractor：利用 LLM Tokenizer 构造节点语义

6.1 为什么还需要节点特征

HCG 给出了结构信息：

node type
edge type
meta relation

但仅有图结构并不能充分反映节点对应代码的语义。

例如下面两个节点虽然可能同为 expression_statement：

balances[msg.sender] = 0;

和：

msg.sender.call{value: amount}("");

其安全语义完全不同。

因此 MANDO-LLM 将节点对应的源码片段作为语义输入。

6.2 不使用完整 LLM Encoder

这是 MANDO-LLM 非常重要的设计选择。

论文没有把节点代码送入完整 LLM Encoder，而是只使用：

LLM Tokenizer

原因是完整 Encoder 参数量大、显存和计算成本高，并且微调新语言/新任务成本高。

因此方法采用：

Node Code Snippet
       │
       ▼
LLM Tokenizer
       │
       ▼
Token-based Node Attribute Feature

即利用预训练 tokenizer 的词表和分词机制增强节点代码表示，同时避免完整 LLM 推理。

6.3 三种 Tokenizer

Solidity-T5

Solidity 专用模型；

SentencePiece BPE；

vocabulary size：32,100；

在 Solidity 数据上训练，因此领域适配性较强。

StarCoder

面向 80+ 编程语言；

原始 BPE；

论文方法章节给出的 vocabulary size：49,152；

其预训练语言范围更广。

CodeT5p-770m

CodeT5 系列；

code-specific BPE；

vocabulary size：32,100；

主要从大规模代码语料学习代码 token 结构。

7. MANDO-LLM GNN：HGT 异构消息传播

7.1 输入

HGT 的输入不是原始 Solidity，也不是单独 CFG，而是：

HCG topology
+
Node Types
+
Edge Types
+
Meta Relations
+
Node Features

即：

结构信息 + 节点代码语义

共同进入 HGT。

7.2 HGT 的核心思想

对于目标节点 t 和邻居节点 s1, s2, ...，HGT 需要同时考虑：

源节点类型
目标节点类型
关系类型
节点当前表示

论文将每个 target node 看作 Transformer 中的 Query，将邻居节点看作 Key，并在不同 relation 下计算 attention。

经过多层 HGT 后，每个节点得到 Node Embedding。

该向量不再只是该节点自己的代码语义，而是融合了：

自身代码特征；

邻居语义；

控制流上下文；

函数调用上下文；

node type；

edge/meta-relation type。

8. HGT Layer 的三个子模块

8.1 Heterogeneous Mutual Attention

该模块计算目标节点和邻居节点之间的关系相关注意力。

概念上：

Target node
    │
    └── Query

Source node
    │
    └── Key

并将 relation-specific 参数引入 attention 计算。

因此：

Expression --CFG--> Expression

与：

Function --Call--> Function

即使连接节点数量相同，其注意力过程也可以使用不同关系参数。

8.2 Heterogeneous Message Passing

在注意力之外，每个源节点还会产生 relation-aware message。

抽象表示：

Source Node Embedding
        │
        ▼
Node-type Transformation
        │
        ▼
Relation-specific Transformation
        │
        ▼
Message

不同节点类型和边关系生成不同分布的消息，从而保留异构语义。

8.3 Target-Specific Heterogeneous Message Aggregation

目标节点收集来自邻居的信息，并将 attention 和 relation message 进行聚合。

论文使用 MLP 进行目标相关聚合，并使用：

ELU

作为该阶段激活函数。

最终输出目标节点的 contextualized representation：

h_t^(l)

经过多层 HGT 后得到最终：

h_t^(L)

即最终 Node Embedding。

9. Node Embedding 的意义

假设一个合约图包含：

N1, N2, N3, N4

初始节点特征：

x1, x2, x3, x4

经过 HGT：

x1 ──► h1
x2 ──► h2
x3 ──► h3
x4 ──► h4

hi 就是 Node Embedding。

它表示的不是简单的“这一行源码”，而是：

当前代码节点自身语义
+
相邻程序节点语义
+
控制流结构
+
调用结构
+
节点类型
+
关系类型

这些节点 embedding 随后被同时用于合约级和行级检测。

10. Two-Phase Vulnerability Detector

MANDO-LLM 最后采用两阶段检测。

10.1 Phase 1：Coarse-Grained Contract-Level Detection

目标：

判断一个合约是否存在某类漏洞

输入为整个合约的 HCG 及其学习后的图表示。

通过 MLP 对整个 HCG 进行二分类：

HCG
 │
 ▼
HGT
 │
 ▼
Graph Representation
 │
 ▼
MLP
 │
 ▼
Clean / Vulnerable

对于特定漏洞类型，如果模型给出的 confidence score：

> 0.5

则判定为 buggy。

第一阶段首先过滤大量 clean contracts，再将潜在有漏洞的合约交给第二阶段进行细粒度检测。

10.2 Phase 2：Fine-Grained Line-Level Detection

对于第一阶段判定为潜在 buggy 的合约，第二阶段直接利用 HGT 生成的 Node Embeddings 进行节点分类。

例如：

h1 ──► clean
h2 ──► clean
h3 ──► buggy
h4 ──► clean

当某节点对目标漏洞类型的 confidence：

> 0.5

则该节点被判定为 vulnerable node。

由于图节点与源码的语句/代码行保持映射关系，所以可以进一步映射回 source file 和 source line，从而完成具体漏洞位置定位。

因此 MANDO-LLM 的两阶段任务本质上共享同一个 HGT 表示学习基础：

              Node Embeddings
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
  Contract-level           Line-level
  graph classification     node classification

11. 分类器与训练目标

论文在图分类和节点分类阶段均使用 MLP。

分类输出采用：

Softmax

训练损失使用：

Cross-Entropy Loss

模型通过：

Back-propagation
+
Gradient-based optimization

训练。

注意：论文正文没有明确给出具体 Optimizer 名称，因此不能仅依据论文声称一定使用 Adam 或 AdamW。

12. 从源码开始复现 MANDO-LLM 的完整实现顺序

如果目标是从 Solidity 源码开始完整复现，而不是直接加载作者训练好的 .pth，可将论文流程整理为以下实现步骤：

STEP 1  准备 Solidity 数据和标签
    │
    ├── buggy contracts
    ├── clean contracts
    ├── contract-level labels
    └── line-level labels
    │
    ▼
STEP 2  Tree-sitter 解析源码
    │
    ▼
STEP 3  生成 AST
    │
    ├──────────────┐
    ▼              ▼
STEP 4          STEP 5
构建 HCFG       构建异构 CG
    │              │
    └──────┬───────┘
           ▼
STEP 6  CFG + CG Heterogeneous Fusion
           │
           ▼
          HCG
           │
      ┌────┴─────┐
      ▼          ▼
STEP 7        STEP 8
Meta          Node Features
Relations     Extractor
Extractor         │
      │           ├── Solidity-T5
      │           ├── StarCoder
      │           └── CodeT5p-770m
      │           │
      └─────┬─────┘
            ▼
STEP 9   HGT Input
            │
            ▼
STEP 10  HGT Layer × 2
            │
            ▼
       Node Embeddings
            │
      ┌─────┴──────────┐
      ▼                ▼
STEP 11             STEP 12
Graph-level          Node-level
Classification       Classification
      │                │
      ▼                ▼
Clean / Buggy      Vulnerable Lines

13. 数据集构造

13.1 SmartBugs Curated

143 个 annotated contracts；

208 个 tagged vulnerabilities；

原始数据包含 9 类漏洞。

13.2 SolidiFI-Benchmark

350 个不同智能合约；

9,369 个注入漏洞；

7 类漏洞。

13.3 DAppSCAN

39,904 个 Solidity 文件；

来自 682 个真实 DApp 项目；

包含 1,618 个 SWC weaknesses；

映射到论文统一七类漏洞后，得到 614 个 buggy Solidity files。

13.4 SmartBugs Wild Clean Contracts

SmartBugs Wild 原始包含：

47,398 contracts

作者利用 11 个 SmartBugs 集成检测工具筛选，得到：

2,742 clean contracts

作为 clean contract pool。

14. 七种目标漏洞

论文统一检测以下七类漏洞：

Access Control

Arithmetic

Denial of Service

Front Running

Reentrancy

Time Manipulation

Unchecked Low-Level Calls

MANDO-LLM 本身不依赖针对每种漏洞手工定义图模式，而是针对不同漏洞数据重新训练分类器。

15. Dataset A 与 Dataset B

Dataset A

Buggy 来源：

SmartBugs Curated
+
SolidiFI-Benchmark

再随机加入 SmartBugs Wild 中筛选出的 clean contracts。

Dataset B

Buggy 来源：

DAppSCAN
+
SolidiFI-Benchmark

同样再随机加入 SmartBugs Wild clean contracts。

16. Coarse 与 Fine 数据构造差异

Contract-level

保持：

Clean : Buggy = 1 : 1

目的是使图分类任务类别平衡。

Line-level

只使用：

buggy contracts

因为该阶段目标是在已知含漏洞的智能合约中定位漏洞节点。

论文报告：

Dataset A buggy nodes ≈ 33.14%
Dataset B buggy nodes ≈ 26.07%

因此节点级任务仍然存在明显类别不平衡。

17. Evaluation Metrics

论文主要使用：

Buggy-F1
Macro-F1

其中：

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)

F1 = 2 × Precision × Recall / (Precision + Recall)

Buggy-F1 指针对 vulnerable / buggy 类单独计算的 F1；Macro-F1 则是不同类别 F1 的平均值。

论文虽然讨论 EXAM、Top-N Accuracy、Mean Average Rank、Mean First Rank 和 RImp 等 fault-localization 指标，但实际主要报告 F1 系列指标。

18. Baselines

论文用于对比的基线包括：

Conventional GNN

GAE

LINE

node2vec

Conventional RNN

Vanilla-RNN

LSTM

GRU

LLM Encoder-only

Solidity-T5

StarCoder

CodeT5p-770m

这组 baseline 与 MANDO-LLM 不同：这里会使用预训练模型 Encoder 得到代码表示，再微调最终 hidden representation 对接分类器。

Previous Framework

MANDO-HGT

Conventional Smart Contract Analysis Tools

行级实验中还比较：

Manticore

Mythril

Oyente

Securify

Slither

SmartCheck

Industrial LLM Prompting

Dataset B 上还比较：

DeepSeek

GPT-4.0

Gemini Pro

附录 A：MANDO-LLM 实验参数总表

参数类别

参数

Contract-level

Line-level

论文设置

输入

Node feature size

512

512

所有模型统一

HGT

Hidden size

128

128

从 HGT 重实现中的 256 降低为 128

HGT

Number of HGT layers

2

2

两层

HGT

Attention heads

8

8

八头注意力

Learning Rate

LR range

0.0005 → 0.01

0.0002 → 0.005

Adaptive learning rate

Cross Validation

K-fold

5-fold

10-fold

最终结果取所有 folds 平均

Early Stopping

Patience

7

7

连续 7 次

Early Stopping

Delta

0.001

0.001

loss 改善阈值

Loss

Loss function

Cross-Entropy

Cross-Entropy

图分类/节点分类

Classifier

Prediction head

MLP

MLP

Softmax 输出

Detection

Confidence threshold

0.5

0.5

>0.5 判 buggy

Node Feature

Feature extractor

LLM Tokenizer

LLM Tokenizer

不使用完整 LLM Encoder

Dataset

Clean : Buggy

1 : 1

不使用 clean contracts

coarse/fine 数据策略不同

Hardware

GPU

2 × A100-PCIE-80GB

2 × A100-PCIE-80GB

论文实验服务器

Runtime

CUDA

11.2

11.2

论文实验环境

附录 B：Tokenizer 设置

Tokenizer

类型

Vocabulary Size

特点

Solidity-T5

SentencePiece BPE

32,100

Solidity 专用

StarCoder

BPE

49,152

预训练于 80+ 编程语言

CodeT5p-770m

Code-specific BPE

32,100

大规模代码语料

注：论文后续结果讨论处曾出现 StarCoder vocabulary size 为 49,153 的表述，与方法章节的 49,152 相差 1。严格复现时应直接加载指定 tokenizer，而不手工固定词表大小。

附录 C：Dataset A 统计

Vulnerability

Total / Buggy Contracts

Nodes

Edges

Buggy Nodes

Access Control

114 / 57

13,432

15,538

2,977

Arithmetic

120 / 60

16,157

17,591

5,395

Denial of Service

92 / 46

12,909

14,366

4,106

Front Running

88 / 44

19,415

22,278

10,400

Reentrancy

142 / 71

18,312

19,267

6,570

Time Manipulation

100 / 50

15,699

18,564

5,800

Unchecked Low-Level Calls

190 / 95

17,525

20,952

2,352

Total

846 / 423

113,449

128,556

37,600

附录 D：Dataset B 统计

Vulnerability

Total / Buggy Contracts

Nodes

Edges

Buggy Nodes

Access Control

244 / 122

22,214

27,019

5,794

Arithmetic

372 / 186

51,138

64,166

10,306

Denial of Service

316 / 158

38,631

48,891

7,280

Front Running

252 / 126

33,007

39,629

14,486

Reentrancy

326 / 163

36,579

42,519

10,429

Time Manipulation

172 / 86

21,431

25,818

7,067

Unchecked Low-Level Calls

246 / 123

23,940

29,846

3,821

Total

1,928 / 964

226,940

277,888

59,183

附录 E：论文未明确报告的训练参数

以下参数在论文正文的 Parameter Settings 中没有给出明确数值，因此严格复现时不能将仓库默认值直接等同于“论文参数”。

参数

论文是否明确给出

Batch size

否

总 Epoch 数

否

具体 Optimizer（Adam / AdamW / SGD）

否

Weight decay

否

Dropout

否

Random seed

否

Learning-rate scheduler 具体实现

否

OneCycleLR 的内部参数

否

Gradient clipping

否

Batch normalization

否

因此在复现时应区分：

论文明确设置
        ≠
GitHub 代码当前默认值

推荐实验记录中分别建立：

Paper Settings
Implementation Settings
Local Reproduction Settings

以避免将作者公开代码的后续修改误认为论文原始实验设置。

附录 F：推荐的复现检查清单

[ ] Solidity 原始数据是否对应 Dataset A / Dataset B
[ ] clean / buggy 合约数量是否与论文一致
[ ] Tree-sitter 是否成功生成 AST
[ ] HCFG 是否按函数生成
[ ] CG 是否包含跨函数调用关系
[ ] CFG / CG 是否正确完成异构融合
[ ] node_type / edge_type 是否保留
[ ] Meta Relations 是否动态生成
[ ] 是否加入 reflective relations
[ ] 每个节点是否具有对应源码片段
[ ] Tokenizer 是否正确加载
[ ] Node feature dimension 是否为 512
[ ] HGT hidden size 是否为 128
[ ] HGT layer 数是否为 2
[ ] attention heads 是否为 8
[ ] Contract-level 是否使用 5-fold
[ ] Line-level 是否使用 10-fold
[ ] Early stopping patience 是否为 7
[ ] Early stopping delta 是否为 0.001
[ ] Contract-level 数据是否保持 1:1
[ ] Line-level 是否只使用 buggy contracts
[ ] 最终结果是否按所有 folds 取平均
[ ] 评价指标是否报告 Buggy-F1 和 Macro-F1

一句话总结

MANDO-LLM 的实现本质上是：

“用 Tree-sitter 将 Solidity 源码表示成 CFG+CG 融合的异构合约图，
动态提取节点—边—节点元关系，
再用 LLM Tokenizer 为每个程序图节点增加代码语义特征，
通过 HGT 在异构结构上进行 relation-aware 消息传播，
最后共享 HGT 节点表示分别完成合约级漏洞分类和行级漏洞定位。”