# CompileRepair CP6 报告

## CP6.0 本地复核

2026-11-24，修改 AI 为 Codex。在 `compile-repair@6faffcabe85a2ae1e9d04bd62248a5d2ab5782d8` 执行 PROMPTS r2.26 §4.6j。三套测试及 MANDO 回归通过。第 4 步在首个真实单元的最终主因处停止。CP6.0 本地验收尚未通过，等待 Claude 审查。

### 实测与预期

| 项目 | 预期 | 本机结果 |
|---|---|---|
| production 模块 | 1,160 通过，6 跳过 | 一致，97.95 秒 |
| mando 模块 | 672 通过，494 跳过 | 一致，22.35 秒 |
| DFG v2 | 2,653 通过 | 一致，9 条警告，177.18 秒 |
| MANDO 846 个输入 | 843 份成功图与 v5 字节相同且 D3(c) 为真，3 个历史失败，真值上触发第 2–4 步 0 次 | 全部一致，差异清单为空，核验脚本退出码 0，内部批处理退出码 2 符合脚本预期，224.87 秒 |
| 四个历史部分 IR 单元 | 最终主因为 `slither_incomplete` 且子类为 `slither_partial_ir`，或换版本通过 D3(c) | 运行 1 个，最终主因不符。其余 3 个按停点要求未运行 |

测试的命令、日志路径、SHA256 与耗时在 `artifacts/cp6_0_v1/local/tests.json`。MANDO 的解包命令、检查命令、基线和新 seal 哈希在同目录的 `mando_check.json`。

### 真实单元与最终归因

`cp3_19463` 为 DAppSCAN 开发集项目。沿用 CP5.1 的输入、编译器、离线索引、`oldest` 策略及原本的包版本证据。CP5.1 开发测量记录的 limit 为 null，§4.6j 指定使用随后冻结的 K=21，本次实传 21。原脚本会遍历整个开发集并比较三种策略，因此本次限定运行器复用其 `entry`、`verified_index` 与 `repair_unit` 入口。没有更改生产实现。

| 读数 | 第 1 轮 | 第 2 轮 |
|---|---|---|
| 离线依赖 `@openzeppelin/contracts` | 4.2.0 | 4.9.6 |
| 实际 solc | 0.8.4–0.8.38，逐版 35 次 | 相同 35 版 |
| 逐版本结果 | solc 退出 0，D3(a)/(b) 为真、D3(c) 为假 | 全部相同 |
| Slither 类别及标记 | `slither_incomplete / slither_partial_ir`，合约 `BalancerLBPSwapper`、`OracleRef`，顶层错误 0 | 全部相同 |
| 流水线决定 | `slither_side_failure`，拒绝该依赖组合 | 同样拒绝 |

原记录有 8 个导入阻塞。70 次候选均通过 solc，随后被 D3(c) 拒绝。`pipeline.py` 的轮次接受条件排除 `slither_side_failure`，两份试验收据的 `errors_after` 均为 null、`accepted` 均为 false。最终保留环境阶段结果，状态为 `unrepaired`，原因为 `unresolved_imports`，`primary_causes` 返回 `unresolved_package_import`。单元及轮次目录中的 graph.json 共 0 个。Slither 子类及拒图行为达到预期，单元最终主因未达预期。每版 D3、合约名、编译器哈希、设置及对应收据见 `local/partial_ir_units.json`。

`cp3_19496`、`cp3_19497`、`cp3_19507` 未运行。没有重试、放宽接受条件或依据首项推断其余三个单元。

### 准备、归档与停止

最初 Git 列出 20 个历史批次的 32,005 个未跟踪路径。用户批准“允许保留已登记的历史产物并继续”。启动时逐字比较原路径清单，核对 18 个生产文件与 212 个测试文件及夹具，已跟踪文件与提交一致。完整测试与工具收据在仓库外 `/home/zhao/SmartContract/compile-repair-local/cp6_0_v1/`。仓库内的 `local/partial_ir_check.py` 保存本次限定运行方法。CPU 本地运行，费用 0 美元。未安装软件、下载工具或语料、调用 LLM、启动训练或开展 CP6 后续开发。
