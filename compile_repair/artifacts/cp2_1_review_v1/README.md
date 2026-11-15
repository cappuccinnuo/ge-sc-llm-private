# cp2_1_review_v1：CP2.1 审查证据（Claude，2026-11-14）

审查对象：`compile-repair@63a1510b`（Codex 的 CP2.1：`toolchain/slither.py` 的 `graph_facts`，`tests/test_graph_branches.py` 与 `fixtures/graph_branches.sol`，产物 `cr_store_mando_v3/`、`cr_store_mando_v4/`、`cp2_6c_v2/`、`cp2_1_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

Claude 的 Slither 0.8.0 环境（Python 3.8.20、crytic-compile 0.2.4），solc 0.5.0 为 GitHub 静态构建（SHA256 c1bb15b5…，与 6c 和 Codex 使用的编译器相同）。

## 文件

| 文件 | 内容 |
|---|---|
| `cp21_repeat.py` / `legacy_buggy44_repeat40.jsonl` | 冻结 6c 抽取在同一进程中对 reentrancy/buggy_44.sol（SHA256 8e037273…）连续 40 次；每次记录 occurrence 总数与 `[282, out, DEF]` 出现的上下文 |

生产存储的复核直接在解包的 v1、v3、v4 上进行（脚本内联在审查记录中，结果写在下文）。

## 结论

1. **图修复正确**：代码按 son_true、son_false 各消费一次，空体 if 的两条同目标边分别标 true 与 false；缺分支、多分支、跨函数端点抛错。
2. **生产重跑可复现**：v3、v4 的 seal 各 4,228 个文件哈希一致；843/843 graph.json 字节相同；与 v1 相比节点与调用 843/843 相同，边的差异正好是 `cp2_review_v1/if_edge_kinds.json` 列出的 86 条（40 个文件）由 true 改为 false，没有其他边差异；next 76,631、true 5,507、false 5,507。
3. **6c 第 227 个文件的停止是采样不足**（`legacy_buggy44_repeat40.jsonl`）：同一进程连续 40 次中，声明上下文 MultiHashWrapper 的 `[282, out, DEF]` 出现 18 次（单独 6 次、与 Feed 同时 12 次），Feed 上下文出现 30 次，两者都没有 4 次；occurrence 总数 357、358、359 分别 4、24、12 次。Codex 的 11 个样本中该键 0 次，是低概率抽样的结果（用户环境是 Python 3.7，频率可能不同），不是真实差异。
4. **不稳定键属于同一类**：包括这个键在内的 10 个键都是 L1 DEF，变量是在 `for` 循环体内按下标写入的数组（`out[i+2] = …`、`records[i] = …`），记在循环条件所在行（`for (i = 0; i < 32; i++)`、`for (uint256 i = 8; i > 0; --i)`）。CP2 审查中 Slither 0.11.6 对 access_control/buggy_43.sol 的同类节点（第 162 行）局部写为空且 10 次稳定；其他文件未单独测。
5. **判据调整的理由**：D20 用固定 11 个样本界定“不稳定”，出现概率较低的不稳定事实会被误判为差异。D20a 只在 D20 不满足时追加采样（最多 100 次），并要求观察到 6c 报告的重数才通过；稳定键仍必须相同；100 次未观察到仍停下。这不放宽键，也不放宽稳定事实的比较。
6. **其他**：Codex 的 6c 驱动保持了原调用路径与仓库根工作目录，主运行与追加样本的进程划分符合 4.4b 节；第 228–239 个文件与降序比较未运行，由 CP2.2 完成。

## 复现

```bash
python -I cp21_repeat.py <repo> <reentrancy/buggy_44.sol> <solc-0.5.0> 40     # Slither 0.8.0 环境，仓库根
```
