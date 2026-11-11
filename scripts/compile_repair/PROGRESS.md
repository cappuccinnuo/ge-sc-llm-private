# CompileRepair 实施进度

## 方案 r1（Claude，2026-11-11）

- 分支 `compile-repair` 从 `node-sem@306c135b` 切出（与 `edge-sem` 相同起点）。本次只新增 `scripts/compile_repair/` 下的文档与证据，没有生产代码，没有修改任何已有文件。
- 新增文件：`PROMPTS.md`（方案 v2 与 CP0–CP2）、`PROGRESS.md`（本文件）、`REPORT_TEMPLATE.md`、`artifacts/cr_pre_v1/`（证据脚本、结果 JSON、solc 探针与 README）。
- 证据要点（详见 `artifacts/cr_pre_v1/README.md`）：846 个 source_files 0 个 import；规则 A 下 39 个不通过，全部可在合取区间内同一小版本系列换版本后编译；Slither 0.8.0 在 solc 0.4.11 时缺文件名、0.4.12 起正常；两个版本之间 key4 与 SlithIR 39/39 相同。
- 证据环境与用户 `mando` 环境不同（GitHub 静态 solc、Python 3.8、直接调用 solc），所有数字须由 CP0 在用户环境复核。
- 下一步：用户确认 D1、D2 后执行 CP0。
