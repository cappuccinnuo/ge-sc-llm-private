# cp1_1_review_v1：CP1.1 审查证据（Claude，2026-11-14）

审查对象：`compile-repair@27aa46fe`（Codex 的 CP1.1：`toolchain/solc.py`、`toolchain/slither.py`、`pipeline.py` 的改动，`tests/test_cp1_1.py`，产物 `artifacts/cp1_1_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

与 `cp1_review_v1` 相同：Claude 的 Slither 0.8.0 与 0.11.6 环境、GitHub 静态 solc、本地构建的 tree-sitter-solidity 语言库。输出中的本机路径替换为 `<repo>`、`<scratch>`。

## 文件

| 文件 | 内容 |
|---|---|
| `cmd_probe.py` / `command_cwd_after.jsonl` | 修复后直接调用 `command()` 并执行 solc 0.5.17：工作目录 `/`、字符前缀兄弟目录、包含输入的目录、无关目录，两个环境 |
| `argv_eq.py` / `argv_equality.jsonl` | 工作目录为仓库根时，846 个 MANDO 文件（cp0_v2 升序版本）与 cp0_1_compilers_v2 的 501 个兼容性组合：新 argv 与旧算法得到的 argv 逐个比较 |
| `e2e_pipeline.py`、`cwd_equivalence.json` | Claude 环境中直接调用 `repair_unit`，3 个输入（`cp1_review_v1/inputs/`）分别在正常目录、`/`、字符前缀兄弟目录下运行；另解包 Codex 的 `cli_cases.tar.gz`，比较 9 个 case |

## 结论

1. **路径缺陷已修复**：修复后 8 次调用（4 种目录 × 2 个环境）solc 全部 rc 0（修复前 `/` 与字符前缀兄弟目录为 rc 1）。
2. **已有结果不受影响**：两个环境中 1,347/1,347 个 argv 与旧算法相同，所以 CP0–CP1 在仓库根下的运行结果不变，无需重跑。
3. **流水线在三种目录下结果相同**：Claude 的 3 个输入（精确 0.4.10 覆盖、无 pragma 推断、两条 pragma）在三种目录下都成功，节点内容哈希逐个相同；修复前后两种目录为 `all_solc_candidates_failed`。Codex 的 9 个 CLI case 封存全部一致，同一 fixture 的三种目录节点哈希相同（compat_05 → 0.5.0；精确 0.8.24 → 默认失败后加 `--evm-version cancun` 成功；精确 0.4.10 → 覆盖后 0.4.12）。
4. **代码审查**：regression_6c 防护正确识别 `/` 与“字符前缀相同但不包含输入”；超时处理只结束当前输入、不改写原因为 Slither 侧或全部失败、批次继续；`_code_commit` 只吞掉 git 不存在与非工作树两种异常。改动只在三个生产文件与一个新测试文件。
5. **CP2 前的方案补充**（r2.8）：Slither 0.11.6 中 `LibraryCall` 是 `HighLevelCall` 的子类（本环境用 `__mro__` 核对），存储分类必须先判断 LibraryCall；其他 Call 子类（InternalDynamicCall、Send、Transfer、SolidityCall、EventCall、NewContract）不能丢弃；CFG 边须带 true / false / next 种类。

## 复现

```bash
(cd <工作目录> && python -I cmd_probe.py <repo> <solc-0.5.17> <合约> <工作目录>)
python -I argv_eq.py <repo>
(cd <工作目录> && TREE_SITTER_LIB_DIR=<语言库目录> python -I e2e_pipeline.py <repo> <solc 目录> <新输出目录> ../cp1_review_v1/inputs/*.sol)
```
