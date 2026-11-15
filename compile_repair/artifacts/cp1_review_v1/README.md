# cp1_review_v1：CP1 审查证据（Claude，2026-11-14）

审查对象：`compile-repair@3497af24`（Codex 的 CP1：`core/model.py`、`core/provenance.py`、`core/store.py`、`rules/environment.py`、`pipeline.py`、`cli.py`、`evaluation/survey.py` 与 `toolchain/solc.py` 的改动、3 个新测试文件，产物 `cp1_development_v1/`、`cp1_sample_v1/`、`cp1_historical_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

Claude 的 Slither 0.11.6 环境（Python 3.12.13、crytic-compile 0.4.2；为端到端测试另装 tree-sitter 0.20.4，并用仓库内 `process_graphs/tree_sitter_codeviews/vendor/tree-sitter-solidity` 构建语言库）与 Slither 0.8.0 环境；solc 为 GitHub 发布页的静态构建（0.4.11–0.5.17 全部，另有 0.8.x 若干）。输出中的本机路径替换为 `<repo>`、`<scratch>`。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_cp1_cases.py` / `verify_cp1_cases.json` | 解开 `cases.tar.gz` 后审计 95 个 case：封存文件哈希、计划候选集合是否等于“区间 ∩ 92 个支持版本”、尝试顺序是否为计划顺序的前缀、成功是否在最后一次、选定版本是否在区间内且 ≥ 0.4.12、与 cp0_v2 的差异 |
| `indep_select.py` / `indep_select.jsonl` | Claude 的独立选版：按同一候选顺序，用 GitHub 静态 solc（工作目录 `/`、直接调用）判断退出码，用 `Slither(path)` 构造并用 D3 判定，求第一个成功版本 |
| `e2e_pipeline.py`、`inputs/*.sol`、`pipeline_cwd.json` | 在 Claude 环境中直接调用 Codex 的 `repair_unit`：精确 `pragma solidity 0.4.10;`（CRLF、同行代码）、无 pragma（throw/var）、两条 pragma；并在不同工作目录下重跑 |
| `cmd_probe.py` / `command_cwd.jsonl` | 直接调用 Codex 的 `command()` 并执行，4 种工作目录 × 2 个环境 |

## 结论

1. **冻结选版重放成立**：两环境的离线重放各 846 行，升序、降序与 cp0_v2 的 selection 逐个相同（846/846、846/846）。
2. **小样本审计无问题**（`verify_cp1_cases.json`）：95 个 case 的 757 个封存文件哈希一致；95 个 case 都封存了 92 个支持版本；候选集合、尝试顺序、成功位置、区间与下限检查的问题数为 0；92 成功、3 未修复（Slither 侧失败）；solc 197 次、Slither 101 次；与 cp0_v2 相同 91，另 1 个（case 082）选 0.5.5，0.5.5 不在 cp0_v2 的 37 个编译器中，归因 (a) 成立。14 个实现文件的 SHA256 与提交 3497af24 中的文件相同。92 个成功 case 的 11,822 个节点全部 original，输入、工作副本与节点文件的 SHA256 一致。
3. **独立选版 95/95 相同**（`indep_select.jsonl`）：选定版本（含 3 个 None）与尝试的版本序列都与 Codex 相同。
4. **端到端行为正确**（`pipeline_cwd.json` 的正常目录部分）：精确 0.4.10 → 覆盖后 0.4.12 成功，覆盖副本与原文件字节数相同，CRLF 与同行的 `contract A {` 保留，4 个节点全部 original；无 pragma 含 throw/var → 推断区间 [0.4.12, 0.5.0)，0.4.12 成功；两条 pragma → 交集 [0.5.0, 0.5.3)，0.5.0 成功。
5. **缺陷：`command()` 的相对路径**（`command_cwd.jsonl`、`pipeline_cwd.json`）。`source[len(cwd)+1:]` 只按字符前缀判断：
   - 工作目录为 `/` 时去掉了两个字符（`/tmp/…` → `mp/…`），合法合约 solc 返回 1、“not found”；
   - 工作目录与输入路径只有字符前缀相同（`…/ou` 与 `…/out2/…`）时得到 `2/units/…`，同样失败；
   - 在两个环境中都复现。经流水线运行时，同一合约在这两种目录下记为 `all_solc_candidates_failed`，在正常目录下成功。CP1 的所有正式运行都在仓库根、输入在其下，不受影响。crytic-compile 0.2.4 内部有同样写法（regression_6c 的 Slither 会受影响），0.4.2 改用了 `--allow-paths .,<文件目录>`。
6. **历史编译器测量与 Claude 的观察一致**：用户环境中 0.4.11 在两种工作目录下 5/5 通过；0.4.0、0.4.2、0.4.9 全部缺文件名（crytic-compile 对 0.4.0–0.4.10 不加 `--allow-paths`，这几个版本在 0.11.6 中也缺）。Codex 建议维持 0.4.12 的理由成立。
7. **其他审查意见**：单个输入的 solc 超时会停止整个批次（检测时一个异常输入会中断全部）；`repair()` 在非 git 工作树中取提交号会抛错；`||` pragma 按冻结语义判为不支持；Slither 在进程内运行没有超时。前两项在 CP1.1 修复，后两项进入 CP3 分类表。

## 复现

```bash
python3 -I verify_cp1_cases.py <解包后的 cases 目录> <repo> <jobs.json>
python -I indep_select.py <repo> <jobs.json> <solc 目录> <out.jsonl>                     # Slither 0.11.6 环境
TREE_SITTER_LIB_DIR=<语言库目录> python -I e2e_pipeline.py <repo> <solc 目录> <新输出目录> inputs/*.sol
(cd <工作目录> && python -I cmd_probe.py <repo> <solc-0.5.17> <合约> <工作目录>)
```
