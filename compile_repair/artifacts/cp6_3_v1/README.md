# CP6.3 证据：第 7 步声明桩（修改 AI：Claude，2026-11-25）

规格见 PROMPTS r2.32 §4.6n，记录见 docs/CHANGE_LOG.md §74。本目录放脚本与云端摘要；本机复核的输出写到仓库外 compile-repair-local/cp6_3_v1/。

## 先测量，再定范围

读取 CP6.2 两次运行中最终记录的诊断位置处的标识符与它所在的行（180 个来源，185 个单元），按用法与不同来源计数：

| 用法 | 来源 | 处理 |
|---|---:|---|
| 普通变量（`owner`、`_totalSupply`，也有 `msg.sendor` 这类拼写错误） | 84 | 不加桩：用法给不出类型 |
| 限定名（`x.length`、`Game.Teams`） | 35 | 不加桩 |
| 普通调用（`f(...)`，多为继承来的函数或基类构造函数） | 32 | 只有构造函数头中的基类调用加桩 |
| 类型（`IERC20 token`、结构体名） | 32 | 接口桩；`X memory` 一类（结构体、数组）不加 |
| 基类（`is Owned`） | 14 | 合约桩 |
| 修饰器（`onlyOwner`） | 11 | 修饰器桩 |
| 事件（`emit Transfer(...)`） | 8 | 事件桩 |
| 转换后调用（`IERC20(a).transfer(...)`） | 5 | 接口桩 |

180 个来源中 172 个是片段，项目只有 8 个，且缺失的名字在项目内没有恰好一处定义，所以没有做“补导入”。`virtual`、`override` 在旧编译器下也报未声明，属于版本问题，不加桩。

## 实现

- `rules/stubs.py`：第 7 步（非测试文件仍为 20 个）。规则见 PROMPTS §4.6n；只插入文本，等级 additive，步骤名 stub。
- `pipeline.py`：修复资格增加 undeclared_identifier、missing_base_contract；第 5、7、8 步按此顺序在同一轮运行。
- 测试：`tests/test_cp63.py` 13 项。

开发中发现并改正的两处：一是普通调用 `f(x)` 起初被当作类型用法，会产生接口桩，类型检查失败却因阶段前进（名称解析 → 类型检查）被 D27 接受；改为转换后必须接成员调用才算类型用法。二是 solc 每个作用域一次只报一个未声明的名字，只为被报的名字加桩时错误数 1 → 1、阶段不变，永远不被接受；改为同一次提案也为处在明确位置（基类列表、emit、函数头修饰器位置）、项目中没有任何文件声明过的其他名字加桩。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,215 passed / 6 skipped（production_tests_cloud.json） |
| MANDO 回归 | passed=true：843 个图与 v5 逐字节相同，历史失败 3，steps_on_truths 0（mando_check_cloud.json） |
| undeclared_identifier 基准（删去一个事件声明，30 个不同内容） | 18 个成功；graph_equal 16，严格 exact 12；graph_equal 而不 exact 的 4 个只差 near_damage（桩在合约开头）；另 2 个是已知的两个工厂合约（只差内嵌元数据哈希） |
| missing_base_contract 基准（删去一个本地基类，30 个） | 8 个成功：逐合约比较节点数，节点变少的只有被删的基类（Ownable、owned，各 10–24 个），多出的节点全部在插入的桩文本内（每个收到 onlyOwner 桩的合约 2 个），其余合约不变；22 个未修复，派生合约用到被删基类的成员 |
| 真实单元（550 个：DAppSCAN 95、SOChecker 455） | 49 个成功（49 个不同来源；CP6.2 为 40），第 7 步接受 14 个（9 个最终成功），没有退步；仍以未声明标识符为主因的单元中 52 个只有普通变量或普通调用（按设计不加桩）；语料不变（real_check_cloud.json、targets_cloud.json） |

## 脚本

- `select_targets.py`、`real_check.py`、`mini_benchmark.py`：同 cp6_2_v1；real_check 另记第 7 步（rule_steps 中 step 7 与 step7_accepted）。
