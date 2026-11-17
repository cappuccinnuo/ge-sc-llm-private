# cp2_4_review_v1：CP2.4 审查证据（Claude，2026-11-17）

审查对象：`compile-repair@9fdc96e13`（Codex 的 CP2.4：`rules/environment.py` 的 `_pragma_spans` 与 `pragma_interval`，`tests/test_pragma_comments.py`、`tests/fixtures/pragma_comments/`，`tests/test_pragma_bytes.py` 的两项例外，产物 `cp2_4_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

Claude 的云端环境：Slither 0.11.6（Python 3.12.13、crytic-compile 0.4.2）、tree-sitter 0.20.4 与 MANDO 语法库；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同。pytest 从 Slither 0.8.0 环境以符号链接借用，没有安装。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_cp24.py` / `verify_cp24.json` | 新实现与 CP2.3 实现（`git show 76a2cc810:compile_repair/rules/environment.py`）比较：`source_code` 全部 .sol、`tests/fixtures`、`cp2_3_review_v1/edge_cases` 上的 `pragma_interval`（含异常信息）与 `pragma_patches`；MANDO 846 个输入在升序与降序下的 `make_plan`（92 个支持版本，known version 取自 v5 的输入记录，regression=mando） |
| `edge_cases/` | 缺分号后接 `import`、`pragma`、`library` 的三个合约（及被导入的 `b.sol`） |

CLI 验收存储、调用次数与测试的复核内联执行，结果写在下文。

## 结论

1. **修改与方案一致**：生产只改 `_pragma_spans` 的一条异常信息与 `pragma_interval` 的表达式来源（从 `code_only` 遮盖后的同一区间读取），+5/−4 行；`pragma_patches` 与其余函数不变，生产文件 14 个。Codex 保存的 CP2.3 参照 `environment_cp23.py` 与 git 中 `76a2cc810` 的原文件逐字节相同。
2. **与 CP2.3 等价**（`verify_cp24.json`）：1,663 个文件中 CP2.3 能读取的 1,656 个，区间与异常信息 1,656/1,656 相同，补丁区间 1,661/1,661 相同；不同的只有两份“pragma 内块注释”“pragma 内行注释”（现在接受）与两份“缺分号”（信息改为 `F: unterminated pragma directive`）。MANDO 846 个输入的 `make_plan` 在升序与降序下 1,692/1,692 相同，因此选版不变，不需要全量重跑（与 4.4e 节的验收方式一致）。
3. **CLI 验收成立**（解包 `cli_acceptance_store.tar.gz`，SHA256 前缀 `ff5bc10faded5855`，seal 前缀 `802cdd364105afcf`，20 个文件 0 不一致）：块注释选 0.8.0、行注释选 0.5.0，都 success、有图、无源码改动；缺分号与 `||` 都是 unrepaired、`unsupported_version_constraints`，`error_first_line` 分别为 `F: unterminated pragma directive` 与 `F: unsupported pragma expression`。`invocations.jsonl` 共 4 条，只属于两个成功输入；两个拒绝输入没有调用工具。
4. **测试**：审查环境运行 `test_pragma_comments.py` 与 `test_environment.py`，34 通过，1 个失败为 `test_real_cp24_cli_comments_and_errors`，原因是 `production_required()` 读取 `/home/zhao/...` 的授权文件（已登记的可移植性问题）。与 `test_pragma_bytes.py` 不同，新模块把本机依赖放在单个测试内，其余测试在本机之外也能运行。
5. **执行中的问题处理得当**：Windows 的 rg 不能读 WSL 路径，改用 WSL 内的 Python 与 git 只读；冻结等价测试对两个注释夹具改为显式例外（先断言冻结函数拒绝，再验证新结果），其余夹具的冻结比较全部保留，没有放宽验收。
6. **缺分号后接其他指令（不是缺陷，CP3 分类细节）**（`edge_cases/`）：`pragma solidity ^0.5.0` 后直接接 `import "…";` 或 `pragma experimental …;` 时，分号属于下一条指令，模块读到的表达式含 `import`/`pragma`，记为 `F: unsupported pragma expression`；solc 0.5.17 同样把两行读成一条 pragma，报 `Source file requires different compiler version`。模块与 solc 的读法一致，所以不修改；但真实原因是缺分号，CP3 分类时应能识别。后接 `library L {}` 时遇到 `{`，模块报 `F: unterminated pragma directive`，solc 报 `Expected ';' but got end of source`。

## 复现

```bash
git show 76a2cc810:compile_repair/rules/environment.py > env_cp23.py
python -I verify_cp24.py <repo> env_cp23.py <list.json> <解包的 cr_store_mando_v5> verify_cp24.json experiments/ge-sc-data/source_code compile_repair/tests/fixtures compile_repair/artifacts/cp2_3_review_v1/edge_cases   # Slither 0.11.6 环境，TREE_SITTER_LIB_DIR
```
