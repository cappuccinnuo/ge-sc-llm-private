# cp0_1_review_v1：CP0.1 审查证据（Claude，2026-11-13）

审查对象：`compile-repair@18940a8a`（Codex 的 CP0.1 A：`toolchain/slither.py`、`evaluation/survey.py`、`cli.py`、测试与 `artifacts/cp0_1_v1/`、`cp0_1_development_v1/`）。本目录是独立复核与 D16 补充测量的证据，不是生产代码，任何 Prompt 都不导入这里的脚本。

## 环境

沿用 `cp0_review_v1` 的 5 个 Slither 环境（0.8.0 / 0.8.3 用 Python 3.8.20 + crytic-compile 0.2.4；0.9.6 / 0.10.4 用 Python 3.12.13 + crytic-compile 0.3.11；0.11.6 用 Python 3.12.13 + crytic-compile 0.4.2）与 GitHub 发布页的静态 solc（cp0_v2 升序选定的 24 个版本与用户环境逐字节相同，见 `cp0_review_v1/README.md`）。用户环境（Python 3.7.12 / 3.8 / 3.10）中的数字须由 CP0.1 B 复核。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_cp01.py` / `verify_cp01.json` | 从 `cp0_1_v1` 的 seal、journal 与 gzip 节点归档独立重算全部验收数字；把 1,546 组节点（key5 + 有序 IR）与 Claude 自己的 Slither 0.8.0 导出（`cp0_review_v1/node_dump.py` 的输出，按 Slither 节点顺序独立编序号）逐组比较 |
| `port_probe.py` | 在任一 Slither 环境中直接调用 Codex 的 `node_facts` 与 `contract_coverage`（不经 profile 检查），检查代码对 dict / 对象两种 source_mapping 与 crytic-compile 0.2.4 / 0.3.11 / 0.4.2 的 AST 接口是否可用 |
| `probes/*.sol`、`extended_probes.jsonl` | 19 个 0.7.1–0.8.29 语法探针（含 `cp0_review_v1` 的 6 个），全部经 solc 0.8.38 编译 rc0；每个在 5 个 Slither 版本上用 Codex 的 D3 代码判定 |
| `codex_d3_batch.py`、`compare_prod.py`、`compare_prod.json` | 用 Codex 的 D3 代码在 Slither 0.9.6 与 0.11.6 下重跑 846 个文件（cp0_v2 升序选定版本），按 key5 与 `cp0_1_v1` 的 0.8.0 归档比较 |
| `feature_prevalence.py`、`toplevel_event.py`、`prev_*.json` | 在 DAppSCAN、Trace、MANDO 的 .sol 文件（按 SHA256 去重）中按文本统计会使某些 Slither 版本失败的写法；只是文本启发式上界，不是编译结果 |
| `rewrite/orig.sol`、`rewrite/rw.sol` | 0.11.6 失败写法的语义等价改写试验（`reentrancy_bonus.sol` 第 19 行） |
| `check_install_request.py` / `check_install_request.json` | Codex 的 D18 请求（59 个编译器）与官方 solc-bin `linux-amd64/list.json` 的逐项比较 |

## 结论（数字均来自上述文件）

1. **CP0.1 A 的数字全部可复现**：seal 中 4 个文件哈希一致；1,546 组归档节点的自身指纹 1,546/1,546 一致；与 Claude 独立导出的 key5 + 有序 IR **1,546/1,546 相同**；每组内 key5 无重复；solc 1,546 次 rc0；Slither 1,546 次构造成功、D3 与 D3(b) 全部通过，profile 全部为 regression_6c（0.8.0 / 0.2.4）；所用（源文件, 版本）对 1,369 个，与 cp0_v2 的升序选定及最低/最高端点集合完全相同（缺 0、多 0）；CP0 投影与 cp0_v2 的 `node_facts_sha256` 1,546/1,546 相同；节点总数 201,044。AST 格式：compact 1,500 组、legacy 46 组，两种都被读取。
2. **Codex 的代码可直接用于新版 Slither**：`port_probe.py` 在 0.8.0、0.8.3、0.9.6、0.11.6 下对三元表达式、自由函数、0.4.24 与 0.5.17 fixture 的结果一致（三元表达式序号 1/2，自由函数计入顶层函数，D3(b) 名称集合相同）。在 0.9.6 与 0.11.6 下对 846 个文件运行，D3(a)/(b) 没有因接口差异失败的情况。唯一的环境依赖：`check_profile` 导入 `importlib_metadata`（第三方包），Python ≥ 3.8 的标准库是 `importlib.metadata`；Codex 的 B 安装清单已列入 `importlib-metadata 4.13.0`，也可在代码中先尝试标准库。
3. **Codex 登记的 transient 待核对项成立**：0.8.24 只增加了 Yul 内置函数 `tload`/`tstore`（官方 0.8.24 发布说明）；0.8.27 解析器接受 transient 状态变量，0.8.28 才能为其生成字节码（官方 0.8.28 发布说明）。r2.3 写“0.8.24 transient”而审查 fixture 用 0.8.28 的高级语法，是方案错误（Claude）。
4. **原 D16 推荐（0.9.6）依据的探针集太窄**。扩展到 19 个探针后（`extended_probes.jsonl`）：

| Slither | 19 个探针通过 | 失败的探针 |
|---|---:|---|
| 0.8.0 | 4 | 顶层 using、全局运算符、自定义错误、UDVT、abi.encodeCall/string.concat、event.selector、block.prevrandao、文件级 event、require(条件, 自定义错误)、error.selector、Yul prevrandao/blob/mcopy/tload/basefee（15 个） |
| 0.8.3 | 9 | 顶层 using、全局运算符、event.selector、block.prevrandao、文件级 event、Yul prevrandao/blob/mcopy/tload/basefee |
| 0.9.6 | 13 | event.selector（0.8.15）、文件级 event（0.8.22）、Yul `basefee`（0.8.7）、`mcopy`/`blobhash`·`blobbasefee`/`tload`·`tstore`（0.8.24） |
| 0.10.4 | 18 | event.selector |
| 0.11.6 | 19 | 无 |

   0.9.6 的失败都是合法源码上的“unresolved reference to identifier …”或“Top level EventDefinition not supported”，本模块无法通过修复源码解决。

5. **846 个文件（Codex 的 D3 代码）**（`compare_prod.json`）：

| Slither | D3 通过 | 失败 | 与 0.8.0 的 key5 结构差异 |
|---|---:|---|---|
| 0.9.6 | 846 | 0 | 23 个文件，只少 Slither 合成的 slitherConstructorConstantVariables()/slitherConstructorVariables() 的 48 个入口节点（743 个不同源文件上为 22 个、47 个） |
| 0.11.6 | 843 | 3 个 0.4.24 文件 `AssertionError` | 435 个文件；多 2,182 个 RETURN（有返回值函数的隐式返回）与 128 个 ENDASSEMBLY，少 48 个合成入口节点与 6 个重数变化的 EXPRESSION |

6. **0.11.6 的失败写法与改写**：3 个文件都是 0.4.x 中 `(bool success, ) = x.call.value(v)("")`（0.4 的 `.call` 只返回 bool）。改写为 `bool success = x.call.value(v)("");` 后 solc 0.4.24 rc0、0.11.6 D3 通过；但 0.8.0 下节点数也从 11 变为 10，改写会改变图，须作为 rewrite 记录并标记。
7. **语料中的出现频率**（文本上界，`prev_*.json`、`toplevel_event.py`）：DAppSCAN 15,485 个不同文件中，0.9.6 失败类写法只有 1 个（Yul basefee），文件级 event 0 个；0.11.6 失败类写法 6 个（2,189 个 0.4 文件中）。Trace 7,407 个文件中，Yul tload/tstore 2、prevrandao 5、mcopy 1、文件级 event 2。MANDO 中 0.11.6 失败类写法 6 个文件（含 source_files 外的副本）。两个候选在现有评估语料上的失败都很少；区别在于 0.4 写法不会再有新代码，而 0.8.7 起的语法会随新合约增加，且只有仍在维护的 Slither 版本会继续加入支持（0.11.6 发布于 2026-07-28，是 PyPI 上的最新版本）。
8. **D18 请求正确**：59 个版本的 URL、SHA256、Keccak256 与官方 solc-bin `linux-amd64/list.json`（GitHub 镜像，文件 SHA256 b44c1d0e…，与 Codex 缓存的官方索引逐字节相同）全部一致；加上已安装的 33 个，正好是 0.4.12–0.8.38 的 92 个正式版本。
9. **环境请求**：Codex 的 B 清单（Python 3.8.20、Slither 0.9.6、crytic-compile 0.3.11、tree-sitter 0.20.4、importlib-metadata 4.13.0）与 r2.3 的推荐一致，tree-sitter 0.20.4 与 mando 相同（`baseline.json`）。若改选 0.11.6：Slither 0.11.6 要求 Python ≥ 3.10、crytic-compile ≥ 0.4.2、web3 7.x；tree-sitter 0.20.4 有 cp310 manylinux 轮子；crytic-compile 0.4.2 只要求 solc-select ≥ 1.0.4，可固定 1.0.4 与 mando 相同。
10. **测试**：在 Claude 的 Python 3.8 + Slither 0.8.0 环境中，不依赖 tree_sitter 与 pycryptodome 的模块测试 30 passed、5 skipped（用户环境专用编译器）；4 个失败均为本环境缺少 pycryptodome，与代码无关。Codex 在用户环境的 55 passed 未在此复现。

## 复现

```bash
python3 -I verify_cp01.py <repo> <cp0_review 的 node_dump 输出目录> <nodetype_venv38.json>
python -I port_probe.py <repo> <file.sol> <solc>                 # 每个 Slither 环境
python -I codex_d3_batch.py <repo> <jobs.jsonl> <solc 目录> <out.jsonl>
python3 -I compare_prod.py <repo> <out_096.jsonl> <out_0116.jsonl>
python3 -I feature_prevalence.py <语料目录> <名称>
python3 -I check_install_request.py <list.json> <compiler_installation_request.json>
```
