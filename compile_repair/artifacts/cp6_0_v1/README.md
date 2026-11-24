# cp6_0_v1：CP6.0 执行环境与 D25（Claude，2026-11-24）

修改 AI：Claude。CP6.0 由 Claude 直接实现并在云端核验；用户本机由 Codex 按 PROMPTS §4.6j 的“本地运行步骤”复核。本目录是证据与工具，不是生产代码；不含外部语料与编译器。

## 生产代码改动（D25，用户 2026-11-24 批准）

| 文件 | 函数 | 改动 |
|---|---|---|
| `toolchain/slither.py` | `run_slither` | production 构图后增加 D3(c)：Slither 没有把任何合约标记为 `is_incorrectly_constructed`、顶层函数没有 IR 生成失败日志；不满足时 `d3` 为 false、不写图，错误首行为 `D3(c): Slither partial IR: …`。regression_6c 不变（没有 `d3_c` 字段） |
| `toolchain/solc.py` | `classify_slither` | `d3_a`、`d3_b` 为真而 `d3_c` 为假时，分类为 `slither_incomplete`，子类 `slither_partial_ir`，路线 `tool_limitation` |

生产文件仍为 18 个。新增测试 `tests/test_cp60.py`（5 项）：干净的图通过 D3(c)；合约被标记、顶层函数日志两种情形都不通过且不写图；其他 Slither 失败的分类不变；流水线仍尝试全部候选版本，主因为 `slither_incomplete`，子类为 `slither_partial_ir`。

## 云端核验结果

| 项 | 结果 | 文件 |
|---|---|---|
| 编译器 | 96 个（cp0_v2 与 cp0_1 附加清单的全部版本），逐个 SHA256 与仓库保存的官方索引或清单相同；0.4.10 以后取自 ethereum/solc-bin，0.4.0、0.4.2、0.4.9 取自 crytic/solc（solc-select 的来源） | `compilers_sha256.txt`、`fetch_solc.py` |
| MANDO 元数据 | smartbugs/smartbugs-curated 的 versions.csv 与 43 个元数据源文件 SHA256 与 cp0_v2 记录相同 | `setup_cloud_env.sh` |
| 生产测试 | 改动前 1,155 passed、6 skipped（与 Codex CP5.2 相同）；改动后 1,160 passed、6 skipped | `production_tests_cloud.json` |
| MANDO 回归 | 846 个输入：843 个图与 v5 逐字节相同且 D3(c) 为真，3 个历史失败不变，第 2–4 步触发 0 次；267.8 秒 | `mando_check_cloud.json`、`mando_check.py` |

云端没有运行：mando 环境（Python 3.7、crytic-compile 0.2.4）的测试、DFG v2 测试、4 个带标记的真实单元（DAppSCAN 项目，云端未下载）。这三项由本地运行步骤完成。

## 云端环境的复现

`setup_cloud_env.sh` 在容器内重建记录中的绝对路径（/home/zhao/... 的符号链接），模块仍逐个核对 SHA256。用户本机已有这些路径，不要在本机运行它。
