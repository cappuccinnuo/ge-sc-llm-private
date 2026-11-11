# CompileRepair 实施进度

## 方案 r1（Claude，2026-11-11）

- 分支 `compile-repair` 从 `node-sem@306c135b` 切出（与 `edge-sem` 相同起点）。本次只新增 `scripts/compile_repair/` 下的文档与证据，没有生产代码，没有修改任何已有文件。
- 新增文件：`PROMPTS.md`（方案 v2 与 CP0–CP2）、`PROGRESS.md`（本文件）、`REPORT_TEMPLATE.md`、`artifacts/cr_pre_v1/`（证据脚本、结果 JSON、solc 探针与 README）。
- 证据要点（详见 `artifacts/cr_pre_v1/README.md`）：846 个 source_files 0 个 import；规则 A 下 39 个不通过，全部可在合取区间内同一小版本系列换版本后编译；Slither 0.8.0 在 solc 0.4.11 时缺文件名、0.4.12 起正常；两个版本之间 key4 与 SlithIR 39/39 相同。
- 证据环境与用户 `mando` 环境不同（GitHub 静态 solc、Python 3.8、直接调用 solc），所有数字须由 CP0 在用户环境复核。
- 下一步：用户确认 D1、D2 后执行 CP0。

## 方案 r2（Claude，2026-11-11）

- 目录从 `scripts/compile_repair/` 移到仓库根目录 `compile_repair/`（git mv，21 个文件，内容不变）。r1 的 PROGRESS 记录保留原路径，不改旧文。
- `PROMPTS.md` 改为 r2：范围扩大到任意合约与项目（DAppSCAN 为主要评估语料）；一条流水线；九步确定性方法先于代理；第一阶段单代理 + RAG、第二阶段多代理；改动记录与图标记；代码结构规范（3.10 节，非测试 .py 文件上限 30）；Prompt 重排为 CP0–CP10（CP0–CP3 完整，CP4–CP10 给出范围与验收）。
- 新增 `artifacts/cr_pre_v2/`：DAppSCAN、SOChecker 评估片段、Trace 数据集的只读结构统计（未编译）。
- 待用户确认：D5（版本策略细节）、D6 阈值、D9（审查代理只作消融）、D10（LLM 视图匿名化与注释遮蔽）；待定：D12（模型、API、费用上限）、D13。
- 下一步：执行 CP0。
