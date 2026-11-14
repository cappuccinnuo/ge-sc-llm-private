# cp2_review_v1：CP2 审查证据（Claude，2026-11-14）

审查对象：`compile-repair@3dfb347d`（Codex 的 CP2：`toolchain/slither.py` 的 `graph_facts`、`pipeline.py`、`cli.py`，`tests/test_graph.py`，产物 `cr_store_mando_v1/`、`cr_store_mando_v2/`、`cp2_6c_v1/`、`cp2_development_v1/`）。本目录是独立复核证据，不是生产代码。

## 环境

Claude 的 Slither 0.8.0（Python 3.8.20、crytic-compile 0.2.4）与 0.11.6（Python 3.12.13、crytic-compile 0.4.2）环境；solc 0.5.0 为 GitHub 静态构建，SHA256 c1bb15b5…，与 6c 和 Codex 重放使用的编译器相同。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_cp2.py` / `verify_cp2.json` | 解包两份生产存储后独立核对：seal、状态与版本、图字节、节点/边/调用计数、LibraryCall 是否误分、悬空引用、与 cp0_1_env_v2 同版本归档的节点比较 |
| `if_edge_kinds.json` | 每个 IF/IFLOOP 节点的出边种类统计与 86 个异常节点清单 |
| `cp2rev_probe.py`、`legacy_fresh_process.jsonl`、`legacy_hashseed.jsonl` | 冻结 6c 抽取对 buggy_43.sol 的单次运行（每次新进程）：默认 5 次；PYTHONHASHSEED 0–7 各 1 次 |
| `cp2rev_repeat.py`、`legacy_repeat_in_process.jsonl` | 同一进程内对 buggy_43.sol 连续抽取 10 次 |
| `cp2rev_seq.py`、`legacy_sequence_87.json` | 按 6c 重放计划的顺序，在同一进程中先抽取前 86 个文件，再抽取 buggy_43.sol |
| `cp2rev_prod_repeat.py`、`production_repeat_in_process.jsonl` | 生产工具链（Slither 0.11.6）同一进程内对 buggy_43.sol 连续 10 次：节点与图哈希、争议循环条件节点的局部写 |

## 结论

1. **生产部分可复现**（`verify_cp2.json`）：两份存储 seal 各 4,228 个文件哈希一致；843 成功、3 个已知 Slither 侧失败；846/846 状态与版本两次相同；843/843 graph.json 字节相同；110,996 个节点全部 original；87,645 边、45,565 调用，计数与 Codex 报告相同；LibraryCall 误分 0；边与调用的悬空引用 0；842/842 与同版本生产归档相同，1 个选 0.5.5。
2. **图缺陷：空体 if 的边种类**（`if_edge_kinds.json`）：`if (!x.send(…)) {}` 这类空体条件中，Slither 的 son_true 与 son_false 是同一个 ENDIF 节点，`node.sons` 中出现两次；`graph_facts` 用“是不是 son_true”判断，两条边都标为 true。共 86 个 IF 节点、40 个文件；其余 5,145 个 IF 与 276 个 IFLOOP 正确。true 5,593 与 false 5,421 的差值 172 正是这 86 个节点各多一条 true、少一条 false。
3. **6c 重放差异的原因：Slither 0.8.0 的局部写集合不确定**：
   - 新进程中首次抽取 5/5 为 254 条，争议事实（`MultiHashWrapper._combineMultiHash` 中 `out` 在第 162 行循环条件 `i < 32` 上的 L1 DEF）出现在 MultiHashWrapper、ProofHash、Post 三个上下文；
   - 同一进程连续 10 次：254、254、252、252、253、254、253、253、252、253，争议事实出现的上下文组合每次不同；
   - 按 6c 顺序先跑 86 个文件后为 252（只在 Post），与 6c 报告相同；Codex 的重放为 251（0 个上下文）。
   结论：6c 报告的这一条是不确定过程的一次采样，CP2 重放的差异不是本模块或重放方法的错误。根因位置未在审查中证明（只观测到结果随进程内状态变化）；在 PYTHONHASHSEED 0–7 的新进程中结果不变，说明不是字符串哈希随机化。
4. **生产工具链确定**：Slither 0.11.6 对同一文件同一进程连续 10 次，node_facts 与 graph_facts 哈希完全相同，该循环条件节点的局部写在三个上下文中都为空（`i < 32` 本身不写 `out`）。生产存储不使用 SSA 局部写集合。
5. **对 6c（DFG v2）的提示**：6c 的 L1 参考事实来自 Slither 0.8.0 的局部写集合，至少在本文件中不确定。这影响以 6c 报告作为固定参考的做法，CP2.1 的重放会给出 239 个文件中不稳定事实的规模；对 DFG v2 已有结论的影响由用户判断，本模块不改动 6c。
6. **其他核对**：调用解析对自由函数记 `<top-level>`、对内建与动态调用保留规范化文本，符合 r2.8；用户批准的 0.4.11 → 0.4.12 单列项合理（6c 当时的工作目录使 0.4.11 映射完整，现在的下限是 0.4.12）。

## 复现

```bash
python3 -I verify_cp2.py <repo> <解包的 v1 存储> <解包的 v2 存储> <out.json>
python -I cp2rev_repeat.py <repo> <buggy_43.sol> <solc-0.5.0> 10        # Slither 0.8.0 环境
python -I cp2rev_seq.py <repo> <cp2_6c_v1 的 plan.json> <solc 目录> 87   # 同上
python -I cp2rev_prod_repeat.py <repo> <buggy_43.sol> <solc-0.5.0> 10   # Slither 0.11.6 环境
```
