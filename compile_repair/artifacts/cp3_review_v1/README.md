# cp3_review_v1：CP3 审查证据（Claude，2026-11-21）

审查对象：`compile-repair@6d7043e8b`（Codex 的 CP3：`toolchain/solc.py` 诊断与分类、`toolchain/project.py`、`toolchain/slither.py` 的项目身份与绑定检查、`pipeline.py`、`evaluation/report.py`、`evaluation/survey.py`、`cli.py`，测试与夹具，产物 `cp3_*`，CP3_REPORT 与四份记录）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Slither 0.11.6（Python 3.12.13、crytic-compile 0.4.2）；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同（0.4.11–0.5.17 全部，0.8.0、0.8.4、0.8.8、0.8.24–0.8.27、0.8.38）。外部语料只在用户本机；审查按用户“仅本地研究使用”的批准，从 BugmakerCC/Trace 固定提交 `4260215b` 取了 1 个文件（SHA256 与 CP3 清单一致），只在审查工作区使用，不提交。

## 文件

| 文件 | 内容 |
|---|---|
| `probe_mando_versions.py` / `.json` | MANDO 三个 Slither 侧失败文件在 0.4.12–0.4.26 每个候选版本的 solc rc 与首条错误 |
| `inspect_wrapper.py` / `trace_wrapper_example.json` | Trace on-chain 单元 cp3_23864（CP3 归为 parser_error_other）的结构：只记录哈希、JSON 键、源文件数与名称 |
| `wrapper_unpack_probe.json` | 把该文件解包为 20 个源文件后，solc 0.8.24/0.8.38 与生产 Slither 的结果 |
| `probe_alias_cast.py` / `.json`、`alias_cast/` | 两个文件各有 `contract C`，Main 用 `import {C as A}`、`import {C as B}`，通过类型转换 `A(x).f()`、`B(y).f()` 与 `new B()` 调用；对照 solc AST 引用、生产 Slither 的调用目标与 `project_bindings` 的结论 |
| `probe_pragma_forms.py` / `.json` | solc 接受的 pragma 写法（通配符、缺补丁号）与 `pragma_interval` 的结果 |

## 结论

1. **成立的部分**：诊断解析覆盖旧式与箭头两种位置格式，不把 `Error` 猜成具体类型；pragma 子类（`||`、未结束、缺分号吞入下一条指令、空交集、无法解析）按 r2.12/r2.13 区分；`project.py` 只读解析闭包，未解析的导入只记录不补，solc 与 Slither 共用入口、工作目录、remapping 与绝对 `--allow-paths`；项目图以“相对文件名 + key5”为身份，单文件格式不变；连字符入口与允许目录两项修正正确。审查环境中 `test_diagnostics.py`、`test_cp3_report.py` 70 项通过；`test_project.py` 在本机之外导入即失败（已登记的路径依赖）。
2. **问题一：类别统计把所有候选版本的错误并在一起**（`evaluation/report.py::classify_record` 与 `aggregate_failures`）。一个单元只要在任一候选版本出现某类诊断就计入该类。MANDO 三个文件（`pragma ^0.4.0`）在 0.4.12–0.4.23 都 solc 失败（0.4.12–0.4.15 `Undeclared identifier`，0.4.16–0.4.23 `Expected token Comma got 'Identifier'`），0.4.24–0.4.26 rc 0，真正的失败只是 Slither 侧（`probe_mando_versions.json`）；CP3 却把它们同时计入 `undeclared_identifier`（3）与 `parser_error_other`（3）。即版本不支持某语法造成的错误与源码本身的错误混在一起，类别频率（用于排列 CP5–CP6 的实现顺序）因此失真。
3. **问题二：Etherscan 标准 JSON 输入包装被当作 Solidity 源码**（`trace_wrapper_example.json`）。cp3_23864 不是源码，而是 `{{ "language": "Solidity", "settings": …, "sources": {…} }}` 形式的包装（20 个源文件、optimizer 与 evmVersion 设置），以 .sol 保存；模块直接交给 solc，CP3 记为 parser_error_other。Trace on-chain 的 5,000 个单元中 432 个计入 parser_error_other，此例是其中之一；其余多少属于包装未核实。解包后 solc 0.8.24、0.8.38 rc 0，生产 Slither 构建成功（20 个合约、265 个函数，`wrapper_unpack_probe.json`）。分类表没有这一输入格式类别，D6 没有对应路线；而这是确定性、不改源码的输入处理。
4. **问题三：项目绑定检查只覆盖声明的合约类型变量**（`toolchain/slither.py::project_bindings`）。`probe_alias_cast.json`：solc AST 中 `A` 引用 A.sol、`B` 引用 B.sol；生产 Slither 把 `A(x).f()` 与 `B(y).f()` 的调用目标都绑定到 B.sol。该函数没有任何合约类型变量，检查条目为 0，`complete` 为 true，图会被接受，其中一条调用边指向错误文件。Codex 的变量用例错到 A.sol，这里错到 B.sol，说明 Slither 只是在同名合约中取其一，与引用方式无关。
5. **问题四：solc 接受的通配符与缺补丁号的 pragma 被拒**（`probe_pragma_forms.json`）。`0.4.x`、`0.4.X`、`0.5.*`、`^0.5` 由 solc rc 0，模块抛 `F: unsupported pragma expression`，不编译。这与 CP2.3、CP2.4 同类（拒绝可编译的输入），来自冻结求值只接受三段版本号。CP3 的 unsupported_expression 92 个单元（DAppSCAN 18、SOChecker 73、Trace on-chain 1）中有多少属于此类未核实。
6. **问题五：流水线改写后没有 MANDO 图的字节对照**。`pipeline.py` 改动约 180 行；CP3 只核对 MANDO 846 个单元 843 成功、3 个 Slither 侧失败（`cp3_binding_v1/mando_subset_acceptance.json`），没有与 `cr_store_mando_v5` 的图与记录逐字节比较。
7. **执行中的问题处理**：SOChecker 897/846 子集、跨文件同名 key5、同名合约错绑、连字符入口、0.4.12–0.4.17 的允许目录、探针脚本漏建目录、驱动比较误报、汇总寻找错误 seal——都先停下、保留失败记录、请求批准或只读修正，再在新批次继续；批准后的修改与方案一致。问题三是批准的绑定检查范围不足，不是执行错误。

## 复现

```bash
python3 -I probe_mando_versions.py <repo> <solc 目录> probe_mando_versions.json
python -I probe_alias_cast.py <repo> alias_cast <solc-0.8.38> probe_alias_cast.json     # Slither 0.11.6 环境
python -I probe_pragma_forms.py <repo> <solc 目录> probe_pragma_forms.json               # 同上
python3 -I inspect_wrapper.py <Trace on-chain 文件> trace_wrapper_example.json
```
