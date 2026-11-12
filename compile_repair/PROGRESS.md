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

## 文档目录 r2.1（Claude，2026-11-12）

- 新增 `docs/README.md`（记录规则与模板）、`docs/HANDOVER.md`（交接文档）、`docs/CHANGE_LOG.md`（运行与改动记录，补记 r1、r2 并记录本轮）、`docs/DECISIONS.md`（决策当前表、r1 编号对照与变化历史）。格式沿用 NodeSem 在仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md` 的写法。
- `PROMPTS.md` 改为 r2.1：每个编码任务结束时必须按 `docs/README.md` 完成记录；记录只写在 `compile_repair/docs/`，禁止修改根目录两份记录文档（D14）；6c 被忽略的本地结果从 EdgeSem 工作树以绝对路径只读读取（D15）。设计不变。
- `REPORT_TEMPLATE.md` 增加指向记录规则的说明。
- 没有模块代码，没有运行。下一步仍为 CP0。详见 `docs/CHANGE_LOG.md` §3。


## 2026-11-12 CP0 前置核验与工具封装检查点（修改 AI：Codex）

依据 PROMPTS r2.1 §4.1/§4.2 在独立 compile-repair 工作树实施。新增 9 个生产模块（根 __init__/cli，core __init__/model，toolchain __init__/solc/slither，evaluation __init__/survey）、3 个测试文件和 counter.sol；新增 RECON.md、CP0_REPORT.md，按 docs/README 完成交接、五段式记录与决策历史。文件清单见 CP0_REPORT。

正式调查 cp0_v1：846 输入集合一致、256 份 6c 源码按 SHA256 对应、43 metadata 全部验证，26 编译器哈希一致；6c 的 11 编译失败+6 映射不可比与旧 A 的 17 个异常文件完全相同。43 metadata 全来自 SmartBugs versions.csv（更正 PROMPTS §1.2），其中 4 个低于 Slither 门槛。用户批准读取两个冻结 source manifests 及其 metadata 引用的来源源码/CSV；未扩大到标签、图或模型。

**CP0 尚未完成全量验收。** 发现唯一无候选文件精确声明 0.4.17，本机缺少该版本，按 CP0 要求在矩阵前停止，CLI 返回 2。全量矩阵、升降序 D3 选版和跨版本语料比较编排未实现/未运行；当前规则 A 成功率、moved/crossed_minor、CP2 运行时估计均未知。安装建议只申请必需的 0.4.17，未执行；授权请求、输入哈希、版本区间见开发产物与 RECON。

测试：`python -B -m pytest -q -p no:cacheprovider compile_repair/tests` 第二轮 21 passed；首轮测试路径假设错误造成 1 failed/20 passed，已修正并保留记录。`python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests` 一轮 2653 passed、9 warnings。实际命令带新的 --basetemp 以保存现场。0.4.11/0.4.13 真实探针均 rc0，但前者 5 个节点缺 filename 被 D3 拒绝，后者通过。354 份 code refs 不变、9 个生产文件合规。

与方案有关的待确认事项：6c 保存 occurrence 而非完整 CFG/原始 IR，CP2 应先审定可观察比较范围；精确 pragma 无可用版本时的覆盖与禁止越界条款须在 CP1 前澄清。本轮只提出建议，没有改设计。未下载、未训练、未调用 LLM，未 push；后续先获准补齐 0.4.17，再完成 CP0 并审查，不能直接进入 CP1。
