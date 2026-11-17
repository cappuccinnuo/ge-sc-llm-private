# cp2_2_review_v1：CP2.2 审查证据（Claude，2026-11-17）

审查对象：`compile-repair@0e6830edc`（Codex 的 CP2.2：`artifacts/cp2_2_v1/`、`cp2_6c_v3/`、`cp2_desc_v1/` 与五份记录）。本目录是独立复核证据，不是生产代码。CP2.2 没有修改生产代码与测试（`git diff --stat 36c6109fa 0e6830edc` 在 `artifacts/` 之外只有五份记录）。

## 环境

Claude 的云端环境：Slither 0.8.0（Python 3.8.20、crytic-compile 0.2.4）与 Slither 0.11.6（Python 3.12.13、crytic-compile 0.4.2）；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同（0.4.11–0.5.17 全部，0.8.0、0.8.4、0.8.8、0.8.24–0.8.27、0.8.38）；没有 0.6.x、0.7.x。tree-sitter 0.20.4 与 MANDO 语法库。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_desc.py` / `verify_desc.json` | 解包 `cr_store_mando_v3` 与 `cp2_desc_v1` 后独立比较：seal、状态、版本对、节点 key5 与 IR、边与调用、graph.json 字节差异的字段 |
| `verify_6c.py` / `verify_6c.json` | 解包 `cp2_6c_v3` 后复算：三个 seal、第 227 个文件 D20a 样本中失败键的出现次数、第 228–239 个文件的提取总数与 SHA、第 239 个文件 11 次样本中逐键的变化 |
| `cp22_repeat.py` / `legacy_spank_repeat30.jsonl` | Claude 的 Slither 0.8.0 环境中，用冻结 6c 抽取对 reentrancy/spank_chain_payment.sol（solc 0.4.23）同进程连续 30 次 |
| `probe_inputs.py` / `probe_inputs.json` | 对 solc 接受的输入运行 `rules/environment.py::pragma_interval`、solc 与生产 Slither |
| `probe_diagnostics.py` / `probe_diagnostics.json` | 三个含错夹具在 0.4.12–0.8.38 的命令行 stderr 与 standard JSON 错误字段 |
| `probe_slither_compat.py` / `probe_slither_compat.json` | MANDO 三个 Slither 侧失败文件：原文与“`(bool x, ) = …call…;` → `bool x = …call…;`”改写后，在 0.4.12、0.4.24、0.4.26 的 solc rc 与生产 Slither 结果（改写只写入临时目录） |
| `fixtures/` | 探针用的四个手写合约（Latin-1 注释、重复定义与未声明标识符、解析错误、缺失基类） |

## 结论

1. **降序比较成立**（`verify_desc.json`）：两个存储 seal 各 4,228 个文件一致；846 个输入的状态两次相同（843 成功、3 个 slither_side_failure）；229 同版、614 不同版，全部在同一小版本系列内；843/843 节点 key5、IR、类型与改动标记相同，边与调用 843/843 相同。graph.json 字节 815 个相同，28 个不同；不同的只有节点 `length` 字段（87 个节点，例如一个 ASSEMBLY 节点在两个编译器下长度为 84 与 60）。与 Codex 报告一致。
2. **6c 续跑成立**（`verify_6c.json`）：三个 seal 一致；第 227 个文件的 D20a 只有 1 个样本，其中失败键（MultiHashWrapper 声明上下文、非继承、`[282, out, DEF]`）出现 1 次，等于 6c 参考重数；第 228–239 个文件的提取总数与记录相同、SHA 相同，11 个与参考总数相同，第 239 个比参考少 1 条。第 239 个文件 11 次样本中只有两个键变化：`result` DEF（第 174 行）为 0,0,0,0,0,0,0,0,0,0,1，`b` DEF（第 156 行）为 1,1,0,1,1,1,1,1,1,1,1，与 Codex 的表相同。6c 参考报告只在用户本机，参考侧的数字没有独立复核；复核的是重放侧的计数与 Codex 记录的一致性。
3. **第 239 个文件的波动在 Claude 环境中独立复现**（`legacy_spank_repeat30.jsonl`）：同进程 30 次，`result` DEF 出现 7 次，`b` DEF 缺失 9 次，总数 753/754/755 为 8/17/5 次。两个变量都是在循环体内按下标写入的数组（`b[i--] = …` 在 `while` 体内，`result[i - _startIndex] = …` 在 `for` 体内），DEF 记在循环条件行。Codex 指出的“不只 `for`”成立；上轮审查把这一类描述为“循环体内按下标写入、DEF 记到循环条件节点”，这一描述仍覆盖全部 12 个键。
4. **遗留缺陷一：版本区间读取依赖整文件解析**（`probe_inputs.json`）：`pragma_interval` 与 `pragma_patches` 先用 MANDO 时代的 tree-sitter 语法解析整个文件。19 个特性夹具中 5 个（`using … global`、用户定义运算符、`transient`、文件级 `event`、`layout at`）抛 `Unsupported: Solidity parser ERROR/MISSING`，`pipeline.repair_unit` 记为 `unsupported_version_constraints` 并直接返回 unrepaired；同样的文件 solc 0.8.38 rc 0，生产 Slither 构建成功。这些文件的 pragma 都是简单的 `>=0.8.x <0.9.0`。这一缺陷自 CP1 起存在，CP1–CP2.1 的审查没有发现：MANDO 语料没有这些语法，特性夹具只在编译器探测中直接编译，没有经过 `make_plan`。
5. **遗留缺陷二：要求 UTF-8**（同上）：注释中含 Latin-1 字节的合约在 `pragma_interval` 抛 `UnicodeDecodeError`，同样记为 `unsupported_version_constraints`；solc 0.4.24、0.5.17、0.8.0、0.8.38 rc 0，生产 Slither 在 0.4.24 与 0.8.0 构建成功。`infer_interval`（无 pragma 推断）同样先按 UTF-8 解码。MANDO 846 个文件全部是合法 UTF-8，所以回归没有暴露。
6. **CP3 诊断的前提**（`probe_diagnostics.json`）：命令行 stderr 在全部已测版本（0.4.12–0.8.38）只写 `Error:`，不写错误类型；位置格式在 0.5.17 及以前为 `file:line:col: Error: msg`，0.8.0 起为 `Error: msg` 下一行 ` --> file:line:col:`（0.6、0.7 未测）。standard JSON 有类型（0.8 有 errorCode），但 0.4.12 对“缺失基类”抛 InternalCompilerError，0.4.12 与 0.4.17 对解析错误与缺失基类不给 sourceLocation。同一错误的措辞随版本变化：0.4.12、0.4.17 为 `Expected token Semicolon got 'RBrace'`，0.4.24 起为 `Expected ';' but got '}'`。
7. **3.2 节第 10 行的改写可行**（`probe_slither_compat.json`）：三个 Slither 侧失败文件各有 1 处 `(bool success, ) = ….call.value(…)("");`。原文在 0.4.24、0.4.26 solc rc 0 而生产 Slither 抛 AssertionError；改写为 `bool success = …;` 后两个版本都构建成功。0.4.12 下原文 solc 就失败，改写后成功。0.4.x 的 `call` 只返回 bool，两种写法语义相同。

## 复现

```bash
python3 -I verify_desc.py <解包的 cr_store_mando_v3> <解包的 cp2_desc_v1> verify_desc.json
python3 -I verify_6c.py <解包的 cp2_6c_v3> verify_6c.json
python -I cp22_repeat.py <repo> <spank_chain_payment.sol> <solc-0.4.23> 30          # Slither 0.8.0 环境
python -I probe_inputs.py <repo> <solc 目录> probe_inputs.json <文件:版本> ...      # Slither 0.11.6 环境，TREE_SITTER_LIB_DIR
python3 -I probe_diagnostics.py <solc 目录> probe_diagnostics.json fixtures/diag_*.sol
python -I probe_slither_compat.py <solc 目录> probe_slither_compat.json 0.4.12,0.4.24,0.4.26 <三个文件>   # Slither 0.11.6 环境
```
