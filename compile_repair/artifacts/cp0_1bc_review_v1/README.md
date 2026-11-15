# cp0_1bc_review_v1：CP0.1 B、C 审查证据（Claude，2026-11-13）

审查对象：`compile-repair@33c23a3b`（Codex 的 CP0.1 B 与 C：`toolchain/slither.py` 的 production profile、`tests/test_production.py`、19 个特征 fixture、`artifacts/cp0_1_env_v1/`、`artifacts/cp0_1_compilers_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

沿用 `cp0_1_review_v1` 的 Slither 0.11.6 环境（Python 3.12.13、crytic-compile 0.4.2）。solc 0.8.24–0.8.27 取自 GitHub 发布页的 `solc-static-linux`，SHA256（`solc_0824_0827_SHA256SUMS`）与官方 solc-bin `linux-amd64/list.json` 一致；0.8.24 的 SHA256 fb03a29a… 与 Codex 失败记录中的编译器相同。

## 文件

| 文件 | 内容 |
|---|---|
| `floor_matrix.jsonl` | 19 个特征 fixture 在 solc 0.8.24–0.8.27 上（按各自 pragma 下界筛选）用 toolchain 的 `--combined-json` 命令编译：默认设置；0.8.24 另加 `--evm-version cancun`；0.8.26 另加 `--via-ir` |
| `settings_probe.py`、`slither_settings_0116.jsonl` | 同样组合在 Slither 0.11.6 下用 Codex 的 `node_facts` 与 `contract_coverage` 判定 D3（设置通过 `solc_args` 传入） |
| `ir_object_repr.py`、`ir_object_repr.json` | 统计 node_facts_v2 归档中含 Python 对象内存地址的 IR 文本 |

另有两项复核直接对已提交的产物进行，结果写在下文：production 归档与 Claude 在 `cp0_1_review_v1` 中的 0.11.6 独立运行（`codex_d3_batch.py` 的输出，未提交）逐组比较；59 个新编译器的可信清单与官方索引比较（`cp0_1_review_v1/check_install_request.py` 的方法）。

## 结论

1. **B 的数字可复现**：production_invocations 846 次 solc、846 次 Slither，profile 全部为 production（0.11.6 / 0.4.2），平台全部为 solc；D3 843，失败的正是 3 个 0.4.24 文件（AssertionError）；节点 110,996；seal_v2 的 74 个文件哈希全部一致；两环境 846 个区间逐条相同。production 归档与 Claude 独立的 0.11.6 运行比较：843 个成功文件中 839 个 key5 + 有序 IR 完全相同，其余 4 个 key5 相同、只差 1 行 IR 文本（见第 3 条）。
2. **Codex 改用 `CryticCompile` + `Slither(crytic)` 构造 production**：结果与 `Slither(path)` 一致（上一条的 839/843 与 4 个文本差异之外没有差别），改法成立。
3. **新问题：Slither 0.11.6 的 IR 文本不确定**。4 个文件（0.4.12 / 0.4.18 的 `this.balance - …` 等表达式）各有 1 行 IR 含 `<slither.core.solidity_types.elementary_type.ElementaryType object at 0x…>`，内存地址每次运行都不同，所以这些文件的 node_facts_v2 指纹不能复现（`ir_object_repr.json`；0.8.0 归档中 0 处）。B 的验收只统计 IR 差异，不受影响；但 CP2 的存储与回归需要确定的指纹，必须先把这种文本规范化。
4. **C 停止正确，原因是方案错误（Claude）**：r2.4 给探针写的“起始版本”是语法引入版本，没有考虑默认编译设置，而且审查时只在 0.8.38 上运行过。实测（`floor_matrix.jsonl`）：
   - 0.8.24 默认设置下 4 个 Cancun 探针 solc 失败：h0824_blob（rc 1，`Undeclared identifier. Did you mean "blockhash"?`）、y0824_blob_asm（`Function "blobbasefee" not found.`）、y0824_mcopy（`Function "mcopy" not found.`）、y0824_tstore_asm（`Function "tload" not found.`）；加 `--evm-version cancun` 后全部 rc 0，Slither 0.11.6 D3 通过。0.8.25 起默认 EVM 为 cancun（官方 0.8.25 发布说明）。
   - 0.8.26 默认设置下 h0826_require_error solc rc 2（`UnimplementedFeatureError`）；加 `--via-ir` 后 rc 0、D3 通过。0.8.26 的 require 自定义错误只支持 IR 管线，0.8.27 起旧管线也支持（官方 0.8.26、0.8.27 发布说明）。
   - 0.8.25 与 0.8.27 默认设置下，所有适用探针 solc rc 0、D3 通过（16 + 17 组）。
   - Codex 不改编译参数、不改探针、停下报告，符合 4.1 节规定。
5. **设计缺口**：检测时的真实合约可能只能在非默认设置下编译（例如精确 `pragma solidity 0.8.24;` 并使用 blobhash，或精确 0.8.26 并使用 `require(条件, 自定义错误)`）。这时换任何候选版本都无效，只能改编译设置（不改源码）。r2.4 的版本策略没有这一维，需要在 CP1 的环境方法中加入。
6. **C 的安装正确**：59 个新编译器的 SHA256、Keccak256 与官方索引 0 差异；支持范围 92/92。

## 复现

```bash
python -I settings_probe.py <repo> <fixture.sol> <solc> "<solc 参数>"
python3 -I ir_object_repr.py <node_facts_v2.jsonl.gz> ...
```
