# MANDO-LLM + DDG：代码实现设计指南

> 目标：在 **MANDO-LLM** 原有 `Tree-sitter → AST → CFG/CG → HCG → Meta Relations + Node Features → HGT → Two-Phase Detector` 流程上，加入**语句级数据依赖图（DDG, Data Dependency Graph）**，显式表示定义—使用（Definition–Use）关系，同时尽量保持原节点体系、LLM tokenizer 节点特征、HGT 主干和两阶段漏洞检测流程不变。
>
> 本文档用于指导代码设计与实现。文中“新增/建议”部分属于本项目的设计方案；MANDO-LLM 原始结构以论文实现为基线。

---

## 0. 设计结论

本项目第一阶段建议采用：

```text
Solidity Source
      │
      ▼
  Tree-sitter
      │
      ▼
     AST
   ┌──┴───────────────┐
   │                  │
   ▼                  ▼
  CFG                 CG
   │                  │
   └───────┬──────────┘
           │
           ▼
      Original HCG
           │
           ├──────────────► Node Features Extractor
           │                 （保持原 tokenizer 流程）
           │
           ▼
     DDG Extractor   ← 新增
   ├─ Scope/Symbol Resolution
   ├─ DEF/USE Extraction
   └─ Reaching Definitions
           │
           ▼
     def_use edges
           │
           ▼
       HCG+ / eHCG
   （HCG + DDG edges）
           │
           ├──────────────► Meta Relations Extractor
           │                 （自动产生含 def_use 的新 meta-relations）
           │
           ▼
      MANDO-LLM HGT
        （结构不变）
           │
           ▼
  Two-Phase Vulnerability Detector
   ├─ Contract-level
   └─ Line-level
```

核心原则：

1. **第一版不新增变量节点。**
2. **第一版不改原始 tokenizer 节点特征。**
3. **第一版不改 HGT 的核心计算结构。**
4. **第一版只在原图上新增数据依赖边。**
5. **DDG 必须基于作用域和到达定义分析，不允许“同名变量直接连边”。**
6. **CFG 的执行方向用于数据流分析；HGT 的反向消息边不能反过来参与 reaching-definitions。**
7. **先做函数内 DDG，再逐步扩展到函数间状态依赖。**
8. **无法可靠解析的数据依赖宁可不连，也不要生成大量错误边。**

推荐把增强图记为：

\[
G^{+}=(V,\ E_{HCG}\cup E_{DDG},\ \tau,\ \phi^{+})
\]

其中：

- \(V\)：沿用 MANDO-LLM 原有节点；
- \(E_{HCG}\)：原 CFG/CG 融合后的边；
- \(E_{DDG}\)：新增数据依赖边；
- \(\tau(v)\)：节点类型；
- \(\phi(e)\)：边类型。

---

# 1. 为什么选择“语句级 DDG”而不是独立变量级 DFG

## 1.1 原始 MANDO-LLM 的图表示

原始 MANDO-LLM 的主要结构信息来自：

```text
CFG：函数内部控制流
CG ：函数之间调用关系
```

二者融合为 HCG。

节点与源码 statement / line 保持对应，因此后续可以直接进行 node classification，实现行级漏洞定位。

---

## 1.2 本方案需要补充的信息

原始 CFG/CG 可以回答：

```text
“下一步可能执行哪个语句？”
“哪个函数调用哪个函数？”
```

但没有显式回答：

```text
“当前语句使用的变量值由哪条语句定义？”
“某个值从哪里产生并传播到哪里？”
```

因此新增：

```text
Definition  ──def_use──>  Use
```

示例：

```solidity
uint amount = balances[msg.sender];      // S1: DEF amount
(bool ok,) = msg.sender.call{
    value: amount
}("");                                   // S2: USE amount, DEF ok
require(ok);                              // S3: USE ok
```

新增：

```text
S1 ──def_use(amount)──> S2
S2 ──def_use(ok)──────> S3
```

---

## 1.3 为什么第一版不建立独立变量节点

如果引入变量级 DFG：

```text
Statement → Variable → Statement
```

会同时引入：

- 新节点类型；
- 新节点初始化方法；
- 新节点与源码行的映射；
- HGT relation schema 扩张；
- node-level vulnerability label 对齐问题；
- 大量变量节点增加图规模。

而第一阶段最重要的是验证：

> **显式数据依赖关系本身是否能提升 MANDO-LLM。**

因此第一版采用：

```text
Statement ──def_use──> Statement
```

保持原节点不变，只增加边。

---

# 2. 与原 MANDO-LLM 的接入位置

## 2.1 原流程

```text
Source
  ↓
Tree-sitter
  ↓
AST
 ├─→ CFG ─→ HCFG
 └─→ CG  ─→ HCG
          ↓
  Heterogeneous Graph Fusion
          ↓
         HCG
      ┌────┴─────┐
      ↓          ↓
Meta Relations  Node Features
      └────┬─────┘
           ↓
          HGT
           ↓
Two-Phase Detector
```

---

## 2.2 修改后的流程

推荐：

```text
Source
  ↓
Tree-sitter
  ↓
AST
 ├─→ CFG
 ├─→ CG
 └─→ Symbol / Expression Information
          ↓
     Original HCG
          │
          ├──────────────────────────┐
          │                          │
          ▼                          ▼
     DDG Extractor              Node Features
          │                      Extractor
          ▼                          │
     def_use edges                   │
          │                          │
          ▼                          │
      Enhanced HCG (HCG+)            │
          │                          │
          ▼                          │
 Meta Relations Extractor            │
          │                          │
          └─────────────┬────────────┘
                        ▼
                       HGT
                        ↓
               Two-Phase Detector
```

### 最关键的接入点

```text
HCG Generator
     ↓
[新增 DDG Extractor]
     ↓
Meta Relations Extractor
```

即：

> **先加入 DDG 边，再抽取 meta-relation。**

不要在 meta-relation 已经生成以后再添加 DDG，否则新增数据依赖无法自然进入 HGT 的关系建模。

---

# 3. 模块划分

建议新增以下模块。

```text
ddg/
├── symbol_table.py
├── access_extractor.py
├── reaching_definitions.py
├── ddg_builder.py
├── storage_location.py          # 第二阶段可选
├── function_summary.py          # 后续扩展
├── models.py
└── tests/
```

如果不希望新增目录，也可合入现有 graph generator，但逻辑上必须保持这几个职责分离。

---

## 3.1 `symbol_table.py`

职责：

- 构建 Solidity 作用域；
- 标识变量声明；
- 区分：
  - local variable
  - function parameter
  - return parameter
  - state variable
- 为每个声明分配稳定 `symbol_id`；
- 将变量引用解析到对应声明。

建议 `symbol_id`：

```text
<contract>::<function>::<scope>::<decl_source_span>
```

示例：

```text
Wallet::withdraw::scope_3::120-131
Wallet::<state>::balances::20-44
```

禁止：

```text
symbol_id = variable_name
```

原因：

```solidity
function f(uint amount) { ... }
function g(uint amount) { ... }
```

两个 `amount` 不是同一个变量。

---

## 3.2 `access_extractor.py`

职责：

针对图中的每一个 statement node 提取：

```text
DEF(node)
USE(node)
```

推荐数据结构：

```python
@dataclass
class VariableAccess:
    symbol_id: str
    name: str
    access_kind: str      # "DEF" / "USE" / "READWRITE"
    variable_kind: str    # local / parameter / return / state
    source_span: tuple
    expression_kind: str
    storage_path: str | None
```

节点保存：

```python
node.defs: list[VariableAccess]
node.uses: list[VariableAccess]
```

---

## 3.3 `reaching_definitions.py`

职责：

在每个函数 CFG 上计算：

```text
某个 USE 点可能由哪些 DEF 点到达。
```

输入：

```text
Function CFG
+
每个节点的 DEF/USE
```

输出：

```text
ReachingDefinitionResult
```

建议：

```python
reaching_in[node_id][symbol_id]  -> set[definition_id]
reaching_out[node_id][symbol_id] -> set[definition_id]
```

---

## 3.4 `ddg_builder.py`

职责：

根据 reaching definitions 创建：

```text
DEF statement ──def_use──> USE statement
```

可选地添加：

```text
USE statement ──reverse_def_use──> DEF statement
```

反向边仅用于 GNN 双向消息传播：

```text
reverse_def_use ≠ 程序数据流
```

---

# 4. 图数据结构建议

## 4.1 Node

保持原 MANDO-LLM node identity，不新增 DDG 专属节点。

可增加分析字段：

```python
@dataclass
class ProgramNode:
    node_id: str
    node_type: str
    code: str

    start_line: int
    end_line: int

    start_byte: int
    end_byte: int

    contract_name: str | None
    function_name: str | None

    defs: list
    uses: list
```

注意：

```text
defs / uses 只用于构图和调试。
```

第一版不要直接将其拼入 512 维节点 feature。

这样才能保证实验：

```text
Baseline vs +DDG
```

只改变图结构。

---

## 4.2 Edge

建议统一：

```python
@dataclass
class ProgramEdge:
    src: str
    dst: str
    edge_type: str

    # 以下属性供调试/解释使用
    symbol_id: str | None = None
    variable_kind: str | None = None
    confidence: str | None = None
```

第一版 edge type：

```text
原 MANDO-LLM edge types
+
def_use
```

可选：

```text
reverse_def_use
```

---

## 4.3 不要把变量名变成 edge type

错误：

```text
def_use_amount
def_use_balance
def_use_owner
```

正确：

```text
edge_type = def_use
edge.symbol_id = ...
```

否则 meta-relation 种类会随变量名数量爆炸。

---

# 5. DEF / USE 识别规则

下面给出第一版应覆盖的核心 Solidity 表达式。

---

## 5.1 普通赋值

```solidity
x = y;
```

```text
DEF = {x}
USE = {y}
```

---

## 5.2 二元表达式

```solidity
x = y + z;
```

```text
DEF = {x}
USE = {y, z}
```

---

## 5.3 复合赋值

```solidity
x += y;
```

必须：

```text
DEF = {x}
USE = {x, y}
```

不能只认为：

```text
DEF = {x}
USE = {y}
```

因为复合赋值读取旧 `x`。

---

## 5.4 自增 / 自减

```solidity
x++;
--x;
```

```text
DEF = {x}
USE = {x}
```

---

## 5.5 条件表达式

```solidity
if (balance > amount)
```

```text
USE = {balance, amount}
DEF = {}
```

---

## 5.6 require / assert

```solidity
require(owner == msg.sender);
```

```text
USE = {owner, msg.sender}
```

其中：

```text
msg.sender
block.timestamp
msg.value
tx.origin
```

建议作为 builtin/source symbol 处理，而不是普通本地变量。

可设计固定 symbol：

```text
BUILTIN::msg.sender
BUILTIN::msg.value
BUILTIN::block.timestamp
BUILTIN::tx.origin
```

---

## 5.7 函数参数

```solidity
function withdraw(uint amount) public {
```

函数入口视为：

```text
DEF amount
```

实现上可以：

### 方案 A：参数节点本身作为 DEF 节点

若原图已有参数对应节点，直接使用。

### 方案 B：FUNCTION_DEFINITION 作为入口定义

如果现有图没有独立参数节点，则把函数入口节点作为 parameter definition origin。

第一版优先复用原节点，避免新增节点。

---

## 5.8 返回值

```solidity
uint x = foo();
```

对 caller：

```text
DEF = {x}
```

对 `foo()` 内部返回值的精确传播属于：

```text
Interprocedural Data Flow
```

第一版可以先不做。

---

# 6. 状态变量的读写建模

这是 Solidity DDG 最重要、也最容易出错的部分之一。

---

## 6.1 简单状态变量

```solidity
uint public total;

function f() {
    uint x = total;
}
```

对于 `total`：

```text
USE state::total
```

---

## 6.2 状态变量写

```solidity
total = x;
```

```text
DEF state::total
USE x
```

---

## 6.3 Mapping

```solidity
balances[msg.sender] = amount;
```

不能简单视为：

```text
DEF balances
USE amount
```

建议内部表示：

```text
storage_path =
    balances[index=msg.sender]
```

该语句：

```text
DEF balances[msg.sender]
USE msg.sender
USE amount
```

注意：

```text
计算 storage location 本身需要读取 msg.sender。
```

但：

```text
balances[msg.sender] = amount
```

通常不代表读取旧 `balances[msg.sender]` 值。

---

## 6.4 Mapping 复合更新

```solidity
balances[msg.sender] -= amount;
```

应该：

```text
USE balances[msg.sender]
USE msg.sender
USE amount

DEF balances[msg.sender]
```

---

## 6.5 第一版状态位置匹配策略

建议分级：

### EXACT

```text
balances[msg.sender]
↔
balances[msg.sender]
```

可认为位置相同。

### POSSIBLE_ALIAS

```text
balances[user]
↔
balances[msg.sender]
```

如果不能证明 `user == msg.sender`：

```text
不要当成精确相同 location。
```

可暂时：

```text
不生成精确 def_use
```

或保留：

```text
may_alias
```

供后续扩展。

### UNKNOWN

复杂 storage pointer、assembly、delegatecall 等：

```text
标记 unknown
```

第一阶段不强行添加精确 DDG。

---

# 7. Reaching Definitions

## 7.1 为什么不能“同变量名就连边”

示例：

```solidity
uint x = a;      // S1
x = b;           // S2
uint y = x;      // S3
```

错误：

```text
S1 → S3
S2 → S3
```

实际正常顺序下：

```text
S2 的定义覆盖 S1。
```

因此：

```text
S2 ──def_use──> S3
```

---

## 7.2 基本公式

对于 CFG 节点 \(n\)：

\[
IN[n] = \bigcup_{p\in Pred(n)} OUT[p]
\]

\[
OUT[n] = GEN[n] \cup (IN[n] - KILL[n])
\]

其中：

```text
GEN[n]  = 当前节点产生的新定义
KILL[n] = 当前节点覆盖掉的旧定义
```

---

## 7.3 Definition ID

建议：

```python
Definition(
    def_id=f"{node_id}:{symbol_id}",
    node_id=node_id,
    symbol_id=symbol_id
)
```

---

## 7.4 工作队列算法

伪代码：

```python
def reaching_definitions(cfg, defs_by_node):
    IN = {n: set() for n in cfg.nodes}
    OUT = {n: set() for n in cfg.nodes}

    worklist = list(cfg.nodes)

    while worklist:
        n = worklist.pop()

        new_in = union(OUT[p] for p in cfg.predecessors(n))

        killed_symbols = {
            d.symbol_id
            for d in defs_by_node[n]
        }

        survived = {
            d for d in new_in
            if d.symbol_id not in killed_symbols
        }

        gen = set(defs_by_node[n])

        new_out = survived | gen

        if new_in != IN[n] or new_out != OUT[n]:
            IN[n] = new_in
            OUT[n] = new_out

            for succ in cfg.successors(n):
                worklist.append(succ)

    return IN, OUT
```

---

## 7.5 分支

```solidity
if (c) {
    x = a;  // S1
} else {
    x = b;  // S2
}

use(x);     // S3
```

正确：

```text
S1 ──def_use──> S3
S2 ──def_use──> S3
```

因为两个定义都可能到达。

---

## 7.6 循环

必须通过 fixpoint 求解。

```solidity
while (...) {
    x = x + 1;
}
```

不要仅遍历 CFG 一次。

---

# 8. DDG 边构建

对于每个节点 `u` 中的每一个 USE：

```python
for use in uses[u]:
    candidates = reaching_in[u]

    matching_defs = [
        d for d in candidates
        if same_symbol(d.symbol_id, use.symbol_id)
    ]

    for d in matching_defs:
        add_edge(
            src=d.node_id,
            dst=u,
            edge_type="def_use",
            symbol_id=use.symbol_id
        )
```

---

## 8.1 第一版推荐只增加

```text
def_use
```

---

## 8.2 第二个消融实验可增加

```text
reverse_def_use
```

即：

```text
DEF ──def_use─────────> USE
USE ──reverse_def_use─> DEF
```

说明：

> `reverse_def_use` 只是 HGT 的消息传播关系，不代表程序真实的数据流方向。

---

# 9. 与 Meta Relations 的融合

原 MANDO-LLM：

```text
meta-relation =
<source node type, edge type, target node type>
```

加入 DDG 后，自动产生例如：

```text
<NEW_VARIABLE, def_use, EXPRESSION>
<EXPRESSION,   def_use, IF>
<EXPRESSION,   def_use, EXPRESSION>
<RETURN,       def_use, EXPRESSION>
```

实际组合取决于原项目真实 node type。

因此不需要人工枚举全部新 meta-relations。

推荐逻辑：

```python
for edge in graph.edges:
    relation = (
        node_type[edge.src],
        edge.edge_type,
        node_type[edge.dst]
    )

    meta_relation_set.add(relation)
```

---

# 10. 与 Node Features Extractor 的关系

第一阶段：

```text
完全不改。
```

保持：

```text
Node source snippet
      ↓
LLM tokenizer
      ↓
512-d node feature
```

原因：

如果第一阶段同时：

```text
+ DDG
+ Code Encoder
+ Static Attributes
```

最终性能提高后无法判断：

```text
到底是 DDG 有效，
还是新的节点语义有效。
```

因此：

```text
Experiment 1 = only change graph edges.
```

---

# 11. 与 HGT 的接入

HGT 输入仍为：

```text
Node Features
+
Node Types
+
Meta Relations
```

区别只是：

```text
Meta Relations
```

中出现了：

```text
def_use
```

相关组合。

---

## 11.1 第一版不修改

```text
Heterogeneous Mutual Attention
Heterogeneous Message Passing
Target-Specific Heterogeneous Message Aggregation
```

---

## 11.2 HGT 参数变化

由于新增 relation：

```text
relation-specific parameters
```

数量可能增加。

实验报告中必须统计：

```text
#nodes
#edges
#edge types
#meta relations
#model parameters
training time
GPU memory
```

避免性能提升只是因为参数规模增加而无法解释。

---

# 12. Two-Phase Detector

第一阶段完全不改：

```text
Phase 1:
Graph / contract classification

Phase 2:
Node / line classification
```

必须保证：

```text
新增 DDG 后 node_id 和 source-line mapping 不变化。
```

不要因为重建图导致：

```text
label ↔ node
```

映射错位。

---

# 13. 第一阶段的边界

## 必须支持

```text
✓ local variable
✓ function parameter
✓ simple assignment
✓ compound assignment
✓ ++ / --
✓ condition expression
✓ require/assert use
✓ builtin values
✓ branch reaching definitions
✓ loop fixpoint
✓ simple state variable read/write
✓ common mapping access
```

---

## 可以第二阶段再支持

```text
△ internal-call argument → parameter
△ return value → caller
△ cross-function state dependency
△ function summary
△ struct field-sensitive storage
△ array index-sensitive location
```

---

## 第一阶段不建议承诺

```text
✗ full cross-contract dataflow
✗ delegatecall precise storage semantics
✗ arbitrary inline assembly
✗ precise dynamic dispatch
✗ transaction-order dataflow
✗ callback / reentrancy exploitability
```

这些应属于后续扩展，而不是 DDG 第一版。

---

# 14. 内部函数调用：后续扩展设计

示例：

```solidity
function f(uint a) {
    uint x = g(a);
}

function g(uint p) returns (uint) {
    return p + 1;
}
```

后续可建立：

```text
caller a
   ↓
callee parameter p
   ↓
return expression
   ↓
caller x
```

但不建议简单将：

```text
f 所有变量
```

与：

```text
g 所有变量
```

连接。

---

## 14.1 Function Summary

推荐：

```python
FunctionSummary(
    parameter_to_return,
    parameter_to_state_write,
    state_read_to_return,
    state_reads,
    state_writes
)
```

示例：

```text
g:
parameter p → return
```

然后在具体 call site 实例化。

---

# 15. 跨函数状态依赖：谨慎设计

示例：

```solidity
function deposit(uint x) {
    balance = x;
}

function withdraw() {
    send(balance);
}
```

从全局语义看存在：

```text
deposit.state_write(balance)
        ↓
withdraw.state_read(balance)
```

但这通常跨越：

```text
不同 transaction
```

因此它不是普通函数内 `reaching definition`。

建议称为：

```text
state_dependency
```

而不是直接混入：

```text
def_use
```

关系类型应区别：

```text
def_use            # 函数内可证明的定义-使用
state_dependency   # 跨函数潜在状态关联
```

这对后续研究非常重要。

---

# 16. 日志与可解释性

每个 `.sol` 输出建议包括：

```json
{
  "contract": "Wallet",
  "function": "withdraw",
  "nodes": 35,
  "cfg_edges": 39,
  "call_edges": 4,
  "ddg_edges": 12,
  "unresolved_symbols": 2,
  "unknown_storage_accesses": 1
}
```

调试模式打印：

```text
[DDG]
S12 --amount--> S18
S18 --success--> S19
```

建议支持：

```text
--dump-ddg
--dump-def-use
--dump-symbol-table
```

便于人工核验。

---

# 17. DDG 正确性测试

模型训练前，必须先验证构图正确性。

---

## Test 1：普通 def-use

```solidity
function f(uint a) public {
    uint x = a;
    uint y = x;
}
```

期望：

```text
param(a) → x=a
x=a      → y=x
```

---

## Test 2：覆盖定义

```solidity
function f(uint a, uint b) public {
    uint x = a;
    x = b;
    uint y = x;
}
```

期望：

```text
x=b → y=x
```

不能：

```text
x=a → y=x
```

---

## Test 3：分支合流

```solidity
if (flag) {
    x = a;
} else {
    x = b;
}

use(x);
```

期望两条：

```text
x=a → use(x)
x=b → use(x)
```

---

## Test 4：复合赋值

```solidity
x += amount;
```

期望：

```text
USE x
USE amount
DEF x
```

---

## Test 5：mapping read

```solidity
uint x = balances[msg.sender];
```

期望：

```text
USE balances[msg.sender]
USE msg.sender
DEF x
```

---

## Test 6：mapping write

```solidity
balances[msg.sender] = amount;
```

期望：

```text
USE msg.sender
USE amount
DEF balances[msg.sender]
```

---

## Test 7：mapping compound update

```solidity
balances[msg.sender] -= amount;
```

期望：

```text
USE balances[msg.sender]
USE msg.sender
USE amount
DEF balances[msg.sender]
```

---

## Test 8：Shadowing

```solidity
uint x;

function f() {
    uint x;
}
```

两个 `x` 的：

```text
symbol_id
```

必须不同。

---

# 18. 与七类漏洞的预期关系

当前七类：

```text
Access Control
Arithmetic
Denial of Service
Front Running
Reentrancy
Time Manipulation
Unchecked Low-Level Calls
```

DDG 不针对某一种漏洞写规则，而是提供通用程序数据依赖。

---

## 18.1 Access Control

可能帮助表达：

```text
msg.sender
    ↓
authorization condition
    ↓
sensitive state operation
```

但：

```text
DDG 本身不能判断权限检查是否正确。
```

---

## 18.2 Arithmetic

可能帮助：

```text
input
 ↓
arithmetic expression
 ↓
state update
```

但：

```text
DDG 不自动判断 overflow / precision / type range。
```

---

## 18.3 Denial of Service

可能帮助：

```text
external-call result
 ↓
condition/revert
```

以及：

```text
loop bound source
```

但：

```text
gas/resource semantics 仍需要其他结构。
```

---

## 18.4 Front Running

可能帮助：

```text
user input / state
 ↓
price/output
```

但：

```text
transaction ordering
```

不是普通函数内 DDG 能完整描述的。

---

## 18.5 Reentrancy

可能帮助：

```text
state read → transfer amount
external-call result → require
```

以及关键状态值传播。

但：

```text
callback reachability
state write ordering
reentrancy guard
exploitability
```

仍不能仅靠 DDG 判断。

---

## 18.6 Time Manipulation

非常适合观察：

```text
block.timestamp
      ↓
condition / arithmetic
      ↓
sensitive operation
```

---

## 18.7 Unchecked Low-Level Calls

适合表示：

```text
call()
 ↓
success
 ↓
require / if
```

但：

```text
“返回值被使用”
≠
“返回值被正确检查”
```

分类仍交给模型。

---

# 19. 实验设计

必须采用受控实验。

---

## E0：原始 MANDO-LLM

```text
CFG + CG
```

---

## E1：+ DDG

```text
CFG + CG + def_use
```

这是最重要的一组。

---

## E2：+ Bidirectional DDG

```text
CFG + CG
+ def_use
+ reverse_def_use
```

检验反向消息传播是否有价值。

---

## E3：+ Interprocedural Summary

后续：

```text
CFG + CG + DDG
+ internal-call summary
```

---

## Negative Control

加入：

```text
数量相近的随机/非语义边
```

用于验证：

> 提升不是单纯因为图变密、信息传播跳数减少。

随机边必须：

```text
固定 seed
匹配新增边数量级
尽量匹配节点度分布
```

---

# 20. 实验控制变量

比较 E0 / E1 时保持：

```text
same dataset split
same random seed set
same tokenizer
same 512-d feature
same hidden dimension
same HGT layers
same attention heads
same optimizer
same learning rate policy
same batch construction
same early stopping
```

不要同时改变：

```text
tokenizer
encoder
pooling
HGT depth
graph readout
```

---

# 21. 评估指标

模型效果：

```text
Contract-level:
- Buggy-F1
- Macro-F1
- Precision
- Recall

Line-level:
- Buggy-F1
- Macro-F1
- Precision
- Recall
```

DDG 工程质量：

```text
- DDG edge precision（人工抽样）
- unresolved symbol ratio
- unknown storage ratio
- graph construction success rate
- graph generation time
- edges/contract
- relation count
- peak memory
```

训练成本：

```text
- parameters
- training time / epoch
- GPU memory
```

---

# 22. 实施阶段

## Phase A：先读懂原图结构

完成：

```text
[ ] 确认 node 数据结构
[ ] 确认 node_id 生成规则
[ ] 确认 CFG edge type
[ ] 确认 CG edge type
[ ] 确认 HCG fusion 实现
[ ] 确认 meta relation 抽取位置
[ ] 确认 node feature 与 node_id 对齐方式
[ ] 确认 line label 与 node 映射
```

此阶段：

```text
不要写 DDG。
```

---

## Phase B：Symbol + DEF/USE

实现：

```text
[ ] symbol table
[ ] scope resolution
[ ] local variable
[ ] parameter
[ ] state variable
[ ] builtin source
[ ] DEF extraction
[ ] USE extraction
```

单元测试全部通过。

---

## Phase C：Reaching Definitions

实现：

```text
[ ] GEN
[ ] KILL
[ ] IN
[ ] OUT
[ ] branch merge
[ ] loop fixpoint
```

---

## Phase D：DDG Builder

实现：

```text
[ ] def_use edge
[ ] edge deduplication
[ ] graph statistics
[ ] dump/debug interface
```

---

## Phase E：HCG+ 集成

确保：

```text
[ ] node count 与 baseline 基本一致
[ ] source mapping 不变
[ ] DDG 仅增加 edges
[ ] meta relations 自动扩展
[ ] HGT 可正常训练
```

---

## Phase F：E0 vs E1

先只完成：

```text
Baseline
vs
Baseline + DDG
```

如果无稳定增益：

```text
先分析 DDG 质量
```

不要立即叠加更复杂模块掩盖问题。

---

# 23. 代码接口建议

## 23.1 DDG Builder

```python
class DDGBuilder:

    def __init__(self, ast, cfg, graph_nodes):
        self.ast = ast
        self.cfg = cfg
        self.graph_nodes = graph_nodes

    def build_symbol_table(self):
        ...

    def extract_accesses(self):
        ...

    def compute_reaching_definitions(self):
        ...

    def build_edges(self):
        ...

    def build(self):
        self.build_symbol_table()
        self.extract_accesses()
        self.compute_reaching_definitions()
        return self.build_edges()
```

---

## 23.2 Graph Generator 接口

建议原：

```python
hcg = build_hcg(source)
```

改成：

```python
hcg = build_hcg(source)

if config.use_ddg:
    ddg_edges = DDGBuilder(
        ast=ast,
        cfg=cfg,
        graph_nodes=hcg.nodes
    ).build()

    hcg.add_edges(ddg_edges)
```

然后：

```python
meta_relations = extract_meta_relations(hcg)
node_features = extract_node_features(hcg)
```

关键顺序：

```text
DDG
必须发生在
Meta Relations Extractor
之前。
```

---

# 24. 配置设计

建议：

```yaml
graph:
  use_cfg: true
  use_cg: true
  use_ddg: true

ddg:
  add_reverse_edge: false
  support_state_variables: true
  support_mapping: true
  enable_internal_call_summary: false

debug:
  dump_symbol_table: false
  dump_def_use: false
  dump_ddg: false
```

便于消融实验：

```bash
--use-ddg
--no-use-ddg
--ddg-reverse
```

---

# 25. 缓存

DDG 构建应与训练解耦。

推荐缓存：

```text
graphs/
  contract_x/
    nodes.json
    cfg_edges.json
    cg_edges.json
    ddg_edges.json
    meta_relations.json
```

或保存为项目原本使用的 graph serialization 格式。

训练阶段不要每个 epoch 重新做：

```text
AST → DDG
```

---

# 26. 版本兼容

本设计继续使用：

```text
Tree-sitter
```

目标之一是尽量保持：

```text
compiler-independent
```

但必须注意：

> Tree-sitter 只提供语法树；符号绑定、作用域、DEF/USE、reaching-definitions 是本项目新增的静态分析逻辑。

因此代码中不要把：

```text
Tree-sitter parse
```

等同于：

```text
complete semantic analysis
```

---

# 27. 错误与保守策略

静态分析不确定时：

```text
prefer UNKNOWN
over incorrect edge
```

建议：

```python
enum AnalysisStatus:
    EXACT
    MAY_ALIAS
    UNKNOWN
```

第一版：

```text
EXACT      → 建 def_use
MAY_ALIAS  → 记录，不进入精确 DDG
UNKNOWN    → 记录，不建边
```

后续可以消融：

```text
EXACT only
vs
EXACT + MAY_ALIAS
```

---

# 28. 最重要的防错规则

## Rule 1

不要：

```text
相同变量名 → 连边
```

必须：

```text
同一 declaration/symbol
+
reaching definition
```

---

## Rule 2

不要：

```text
读写同一状态变量
=
def_use
```

必须检查：

```text
是否真正形成定义到使用。
```

---

## Rule 3

不要：

```text
CFG reverse edge
```

参与 reaching-definitions。

分析只用：

```text
真实执行方向 CFG。
```

---

## Rule 4

不要把：

```text
reverse_def_use
```

解释为真实数据流。

它只是：

```text
GNN reverse message edge。
```

---

## Rule 5

不要第一版就：

```text
+DDG
+Encoder
+Security Features
+New HGT
```

必须先验证：

```text
+DDG alone。
```

---

# 29. 后续创新接口

如果第一阶段 DDG 有效，后续可以自然增加：

## 29.1 Dependency-Aware Node Semantics

从：

```text
只编码 node snippet
```

扩展为：

```text
node
+
DDG predecessor context
+
DDG successor context
```

例如：

```text
Backward Data Slice
→ Code Encoder
→ contextual node embedding
```

---

## 29.2 Function Summary

实现跨过程：

```text
parameter → return
parameter → state write
state read → return
```

---

## 29.3 Dependency Path Modeling

不只使用直接边：

```text
A → B → C
```

而对重要依赖路径进行：

```text
path encoding
```

注意：

```text
不要简单添加所有 transitive closure edges。
```

---

## 29.4 Vulnerability-Aware Relation Selection

后续可研究：

```text
哪些 DDG / CFG / CG meta-relation
对不同漏洞更重要。
```

但第一阶段不要手工给七种漏洞写七套规则。

---

# 30. 推荐的第一版最终范围

建议第一版严格限定：

```text
Graph:
CFG + CG + intra-procedural DDG

Nodes:
保持 MANDO-LLM 原节点

New Edge:
def_use

Optional Ablation:
reverse_def_use

Analysis:
Tree-sitter AST
+ scope resolution
+ DEF/USE
+ reaching definitions

Node Feature:
保持原 tokenizer 512-d

GNN:
保持原 HGT

Detection:
保持 contract-level + line-level
```

即：

\[
\boxed{
MANDO\text{-}LLM
+
Statement\text{-}Aligned\ Data\ Dependency
}
\]

---

# 31. 最小可实现版本（MVP）

如果要尽快跑通：

### Step 1

只支持：

```text
local variables
parameters
simple assignment
compound assignment
if / require expressions
```

### Step 2

构造：

```text
intra-function def_use
```

### Step 3

融合进 HCG。

### Step 4

确保：

```text
meta relation extractor
```

能识别：

```text
(source_type, def_use, target_type)
```

### Step 5

跑：

```text
Baseline vs +DDG
```

### Step 6

确认确实有增益后再加入：

```text
state variables
mapping
internal-call summary
```

这样风险最低。

---

# 32. 最终实现检查表

## 图生成

```text
[ ] 原 CFG 可正常生成
[ ] 原 CG 可正常生成
[ ] 原 HCG 可正常生成
[ ] node_id 与源码映射稳定
```

## DDG

```text
[ ] symbol table
[ ] scope
[ ] DEF/USE
[ ] reaching definitions
[ ] branch
[ ] loop
[ ] shadowing
[ ] state read/write
[ ] mapping
[ ] def_use
```

## 接入

```text
[ ] DDG 加入 HCG 后再抽 meta-relation
[ ] tokenizer feature 不变化
[ ] HGT 输入维度不变化
[ ] node labels 不变化
[ ] contract labels 不变化
```

## 实验

```text
[ ] E0 baseline
[ ] E1 +DDG
[ ] E2 +reverse DDG
[ ] negative control
[ ] 固定数据划分
[ ] 固定 tokenizer
[ ] 固定 HGT 超参
```

## 质量

```text
[ ] 人工检查 DDG
[ ] unresolved ratio
[ ] unknown storage ratio
[ ] graph-size increase
[ ] training cost
[ ] 各漏洞单独效果
```

---

# 33. 一句话实现原则

> **不要把 DDG 做成另一套独立模型；先把它做成 MANDO-LLM 原异构图中的一种可靠、可解释、可消融的数据依赖关系，让原有 HGT 在 CFG、CG 与 DDG 三类程序关系上统一学习。**

