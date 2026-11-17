# cp2_3_review_v1：CP2.3 审查证据（Claude，2026-11-17）

审查对象：`compile-repair@76a2cc810`（Codex 的 CP2.3：`rules/environment.py` 的 `_pragma_spans`、`_expression_interval`、`pragma_interval`、`infer_interval`、`pragma_patches`，`pipeline.repair_unit` 一行，`tests/test_pragma_bytes.py` 与 `tests/fixtures/pragma_inputs/`，产物 `cp2_3_v1/`、`cr_store_mando_v5/`）。本目录是独立复核证据，不是生产代码。

## 环境

Claude 的云端环境：Slither 0.11.6（Python 3.12.13、crytic-compile 0.4.2）、tree-sitter 0.20.4 与 MANDO 语法库；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同。pytest 从 Slither 0.8.0 环境以符号链接借用（只含 pytest 及其纯 Python 依赖），没有安装。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_equivalence.py` / `verify_equivalence.json` | 对 `experiments/ge-sc-data/source_code` 全部 .sol（覆盖 MANDO 846 个输入）、`tests/fixtures` 与 `edge_cases/`，比较新 `pragma_interval`、`pragma_patches` 与 CP2.3 之前的实现（`git show 361772f74:compile_repair/rules/environment.py`）及冻结 `interval` |
| `edge_cases/` | 审查新写的 10 个边界合约（`line_comment_inside.sol` 在等价比较之后补写）：pragma 在合约之后、跨行、无空格、experimental 在前、注释/unicode 字符串中的伪 pragma 与未闭合块注释、pragma 内含块注释或行注释、缺分号、CRLF、多余的右花括号 |

v5 存储与 CLI 正负例的复核脚本内联执行，结果写在下文。

## 结论

1. **修复正确**：`_expression_interval` 与冻结 `versioning.py` 第 7–23 行的求值逐行相同（运算符、补丁版加一、`||`、空交集）；`_pragma_spans` 在 `code_only` 遮盖后的字节上按花括号深度找顶层指令，遮盖保持等长，字节偏移不变。`pipeline` 只把 Unsupported 记为版本约束不支持。
2. **与原实现等价**（`verify_equivalence.json`）：1,659 个文件中原实现能读取的 1,646 个，新实现的区间 1,646/1,646 相同、pragma 补丁区间 1,648/1,648 相同；MANDO 846 个输入 846/846 相同。不同的只有原实现失败的文件：5 个新语法夹具、2 个 Latin-1 夹具、合约体内 pragma 夹具（新实现只读顶层那条）、审查的 `extra_brace` 与 `masked_tricky`（这两个 solc 本身报错，由编译器判定）。
3. **v5 回归成立**：seal 4,228 个文件一致，归档 SHA256 前缀 `de29da390672b53d` 与报告一致；846/846 状态、原因、选定版本、输入 SHA、设置与标志与 v3 相同；843/843 graph.json 字节相同。
4. **CLI 正负例成立**（解包 `cli_probe_stores.tar.gz`）：9 个正例全部 success、没有源码改动、seal 一致，选定版本为 0.8.13、0.8.19、0.8.28、0.8.22、0.8.29、0.4.24、0.5.0、0.5.1、0.4.16（无 pragma 的 Latin-1 文件带 `no_pragma_guess`）；`||` 负例为 unrepaired、`unsupported_version_constraints`、未调用编译器。
5. **执行中的问题处理得当**：旧 seal 被 seal_v2 取代、Windows 命令行长度限制、6 个测试手工 seal、README 末尾空行，四项都只影响记录过程，没有改代码、产物或判据，且保留了首次结果。
6. **遗留一：pragma 内的注释被拒**（`edge_cases/comment_inside.sol`）：`pragma solidity ^0.8.0 /* note */;` 由 solc 0.8.0 编译成功（rc 0），生产 Slither 构建成功；行注释的变体（`edge_cases/line_comment_inside.sol`，注释后换行再写分号）由 solc 0.5.17 编译成功、Slither 构建成功。新实现与冻结实现都抛 Unsupported，模块不编译（行注释变体在 `verify_equivalence.json` 生成之后补写，结果由同一原因决定）。原因是表达式从原始字节而不是遮盖后的字节截取。属于与 CP2.3 同类的“拒绝可编译输入”，继承自冻结语义。
7. **遗留二：缺分号的 pragma 与 `||` 无法区分**（`edge_cases/missing_semicolon.sol`）：solc 0.5.17 报 `Expected ';' but got end of source`（源码错误，后续可修复），模块记录的异常信息与 `||` 相同（`F: unsupported pragma expression`）。CP3 按第 1、6 步之后的记录分类，无法把它归入解析类。
8. **测试可移植性（既有，非本轮引入）**：`test_pragma_bytes.py` 与 `test_cp1_1`、`test_graph`、`test_graph_branches`、`test_pipeline`、`test_production` 在用户本机之外收集即失败（导入时读取 `/home/zhao/...` 的编译器授权文件），而不是跳过；`test_environment.py` 在审查环境 20/20 通过。本轮以第 2 条的独立等价比较代替。影响以后在 CI 或他人机器上运行，不影响 Codex 在用户本机的验收。

## 复现

```bash
git show 361772f74:compile_repair/rules/environment.py > env_old.py
python -I verify_equivalence.py <repo> env_old.py verify_equivalence.json experiments/ge-sc-data/source_code compile_repair/tests/fixtures compile_repair/artifacts/cp2_3_review_v1/edge_cases   # Slither 0.11.6 环境，TREE_SITTER_LIB_DIR
```
