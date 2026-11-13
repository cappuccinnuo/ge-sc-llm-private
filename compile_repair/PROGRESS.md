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

## 方案 r2.2（Claude，2026-11-12）

- 用户说明模块要修复检测时输入的任意损坏合约，不只针对当前训练数据集。`PROMPTS.md` 改为 r2.2：新增适用范围；D6 取消频率门槛，改为按与语料无关的失败分类表逐类判定；版本策略中已知版本改为可选输入、无 pragma 按文档出处推断；入口统一为 `cli repair <路径>`；CP0 增加全版本范围检查与 Slither 可用性探针（新增 D16）；CP2 改为 MANDO 回归运行；CP3 先建分类表；CP4、CP6 覆盖分类表全部类别。
- 记录：`docs/CHANGE_LOG.md` §4、`docs/HANDOVER.md`、`docs/DECISIONS.md`。
- 没有模块代码，没有运行。下一步仍为 CP0。


## 2026-11-12 CP0 续作：全量基线完成，停在 Slither 兼容性 D16（修改 AI：Codex）

依据 PROMPTS r2.2 §4.1/CP0；从本地 `8fb81ed9` 合并上游 `54ecc927`，保留原 CP0 停止记录及 r2.2 原文。用户批准 0.4.17 和额外十个探针版本，已完成官方双哈希校验和独立信任清单，总安装 37；范围内 33/92 个发布版本，未安装 59，不声称覆盖全部补丁。

修改文件：`cli.py`、`toolchain/solc.py`、`evaluation/survey.py`、`tests/test_survey.py`、`tests/test_toolchain.py`；新增 `tests/fixtures/compat_04.sol` 至 `compat_08.sol` 及 `compat_08_errors.sol`。文档采用上游 PROMPTS，追加 RECON、CP0_REPORT、PROGRESS、CHANGE_LOG，更新 HANDOVER/DECISIONS；新增 `cp0_continue_v1/README.md`。生产文件仍为目录表内 9 个，冻结源码与语料不变。

正式 `artifacts/cp0_v2`：846/846 找到 D3 合格版本，0 个缺 filename 节点，原 6c 的 17 个异常现在均通过；规则 A 821 通过、22 失败、3 未安装。升降序不同 617，moved 44，crossed_minor 0。678 份双版本 key4/SlithIR 相同，28 份 length 不同；55 份存在重复 key4，保留多重集合而非去重。39 组兼容探针全部 solc rc0；D3 33 通过，4 组 ≤0.4.11 缺映射负对照、2 组 0.8.4/0.8.38 自定义错误因 `Unknown contract item: ErrorDefinition` 失败。CLI 退出码 2、状态 awaiting_d16，932.935 秒，单次运行、费用 0。

测试：`python -B -m pytest -q -p no:cacheprovider compile_repair/tests` 最终 32 passed（0.83 秒）；`python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests` 为 2653 passed、9 warnings（174.88 秒）。实际命令均用独立 basetemp，日志在 `cp0_continue_v1`。开发小样本首次 JSON 区间类型失败已修复并加测试，六份边界样本在新目录全部通过；安装旧客户端 HTTP 403 等问题与解决保存在 development_issues 和 CHANGE_LOG §6。

正式 seal SHA256 `16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b`。354 冻结引用与 846 输入不变，原 cp0_v1 保留；文档检查结果见 CHANGE_LOG §6.5。与原文差异：metadata 实为 SmartBugs，已按证据更正；新批次避免覆盖；key4 重复和 6c 缺原始节点类型/IR 的边界列入待审；现代语法缺口触发原文 D16 停止条件。没有自行改方案、升级包、写图存储、训练或调用 LLM。CP0 等待用户审查与 D16 决定，不能进入 CP1。


## CP0 审查与方案 r2.3（Claude，2026-11-12）

- 独立复核 CP0：全部数字可复现（846 输入 0 SHA 差异；规则 A 821/22/3；1,692 个选定版本 0 违例；678 对 key4/IR 678/678；Slither 0.8.0 指纹 743/743 与 Codex 相同）。证据 `artifacts/cp0_review_v1/`。
- 方案问题与更正（PROMPTS r2.3）：D3 加入顶层函数与合约覆盖；D4 改 key5（序号身份 678/678 稳定）；pragma 覆盖两处规定的矛盾已消除；1.2 节 metadata 来源更正；新增 1.6 节 CP0 结果、D18 与 CP0.1（4.2b 节）；CP1 前提与 CP2 回归方法更新。
- D16 补测 Slither 0.8.3/0.9.6/0.10.4/0.11.6，推荐 0.9.6 独立环境做生产、0.8.0 只做 6c 重放，待用户决定。
- 记录：`docs/CHANGE_LOG.md` §7、`docs/HANDOVER.md`、`docs/DECISIONS.md`。旧文中指向 r2.2 的 “§4” 应为 §5（见 CHANGE_LOG §7.4）。
- 没有模块代码改动与用户环境运行。下一步：用户决定 D5、D16、D18，Codex 执行 CP0.1。

## CP0.1 A：审查修正与 mando 全量重验（2026-11-12，修改 AI：Codex）

依据 PROMPTS r2.3 §4.1、§4.2b，从 61a3cb6a944140108763442999bbfd4199f53ca3 开始，pull 已同步。A1/A2/A3 完成，B/C 未执行。模块面向未来任意输入，846 文件只作回归。

修改 toolchain/slither.py、evaluation/survey.py、cli.py、tests/test_toolchain.py；新增 tests/test_slither_v2.py、tests/fixtures/ternary.sol、free_function.sol。实现统一映射、顶层函数、保留重数的 key5、旧式/compact AST 合约名称多重集合校验、显式 regression_6c 版本门禁。旧投影仅对照 cp0_v2，新 schema 为 node_facts_v2。生产 Python 文件仍为 9 个，冻结代码与旧证据未改。

正式 cp0_1_v1：新 D3 846/846，(a)/(b) 失败均 0，顶层函数 0，CP0 投影 846/846 一致；678 组 key5 与有序 IR 全同，含重复 key4 的 31 组也全同。solc/Slither 各 1,546 次均成功，201,044 条节点、重复 key5 组数 0。length 650 同、28 异，仅诊断。正式耗时 609.965 秒，seal 为 c28b7c7bc5269d2892027542c14724b1063a043c6d3322996a88f0146d186ff2。

python -B -m pytest -q -p no:cacheprovider compile_repair/tests：55 passed；同参数运行 scripts/DFG/dfg_v2/tests：2653 passed、9 个既有 warnings。实际另带独立 basetemp，日志/命令在 cp0_1_development_v1/pytest_*.log/json。CP0_1_REPORT、CHANGE_LOG §8、HANDOVER 和 DECISIONS 记录本次工作；文档和不变量结果见 §8.5。

WSL reparse-point 与编辑模板问题已用显式 WSL Python 写入解决，过程保留。B 的 transient 0.8.24 文案与审查 >=0.8.28 fixture 待核对语法边界，如需调整先咨询用户，没有自行改方案。D16/B 与 D18/C 的来源、版本、0 美元上限分别列在两份 installation_request.json，仍为 pending。按原文停在授权前，未安装、未进入 CP1，仅本地提交、不 push。


## CP0.1 A 审查与方案 r2.4（Claude，2026-11-13）

- 独立复核 CP0.1 A：验收数字全部可复现；1,546 组节点的 key5 + 有序 IR 与 Claude 独立导出逐组相同；CP0 投影 1,546/1,546。证据 `artifacts/cp0_1_review_v1/`。
- Codex 登记的 transient 问题成立，r2.4 更正 B 部分探针。D18 的 59 个编译器请求与官方 solc-bin 索引一致。
- D16 扩展测量（19 个探针、846 个文件）后推荐改为 Slither 0.11.6，备选 0.9.6；3.2 节新增第 10 行 Slither 兼容改写；CP3 分类表增加 Slither 侧失败。
- 记录：`docs/CHANGE_LOG.md` §9、`docs/HANDOVER.md`、`docs/DECISIONS.md`。
- 没有模块代码改动与用户环境运行。下一步：用户决定 D5、D16、D18 并授权，Codex 执行 CP0.1 B、C。


## 用户决定 D5、D16、D18（Claude，2026-11-13）

- 用户采纳 r2.4 推荐：D5 升序；D16 生产 Slither 0.11.6（Python 3.10 独立环境）；D18 安装 59 个编译器。记录见 `docs/CHANGE_LOG.md` §10。下一步 Codex 执行 CP0.1 B、C。


## CP0.1 B 完成；C 安装完成、兼容性失配停止（2026-11-13，修改 AI：Codex）

- 起点 897fbd03116040ddbc8d106db1b844624f512091，pull --ff-only 已同步；依 PROMPTS r2.4 与用户明确 D5/D16/D18 授权，只执行 B/C，未重做 A。
- 实现与文件：toolchain/slither.py 的 production、metadata 回退和实际平台；tests/test_production.py、两个既有测试的 profile 跳过；19 个原字节 features fixture。文档与完整产物清单见 CHANGE_LOG §11.1、cp0_1_env_v1/file_inventory.json，两批 README 含复现方式。
- B：Python 3.10.21、Slither 0.11.6/crytic 0.4.2 独立环境已建立；区间 846/846 一致；D3 843/846、指定 3 份断言失败；结构 435 份差异及 +2182 RETURN/+128 ENDASSEMBLY/−48 合成入口/−6 EXPRESSION 全吻合。23 组特征全过，三份工作副本两环境全过；详见 B_acceptance.json、production_comparison.json。
- C：B 全通过后才安装 59 版，全部官方双哈希/版本校验；快照范围 92/92。496 组计划仅执行 225：224 过、0.8.24+h0824_blob 的 blobhash 未声明导致 1 个 rc1、271 组未运行；Slither 未进入，已按原文停止，详见 final_status.json。
- 测试命令：python -B -m pytest -q -ra -p no:cacheprovider compile_repair/tests，另带独立 basetemp；B production 77 passed/6 skipped，mando 58 passed/25 skipped。同参数 scripts/DFG/dfg_v2/tests 为 2653 passed/9 warnings；C 停止后未扩大或重测矩阵。初次新测试正则收集错误已修正并保留；初次包解析 user-site 混入在安装前隔离解决。
- 不变量：frozen_audit.json 核对模块外文件 27845、旧产物 204、已有编译器 37、mando 元数据 205、code_refs 354 项不变；A 报告前缀及旧 0.9.6 请求未改。生产文件仍 9 个，分层通过，费用 0，无 LLM/训练/全局选择。
- 与 PROMPTS 不一致：仅 C 首个特征结果未达预期；未放宽判据、换参数、改下界或自动重试。建议先审查语法最低版本与 EVM 设置，任何修订先咨询用户，再用新批次续验；C 与 CP0.1 未通过，CP1 不开始。
- 强制记录、doc_check 与本地提交边界见 CHANGE_LOG §11.5；本轮不 push。第 10 行改写只做工作副本试验，规则未实现。

最终记录补充：原始 Slither 日志的三处空白格式诊断按原字节保留；除该日志外的暂存检查通过。见 CHANGE_LOG §11.5、final_staging_audit.json；最终提交清单为 file_inventory_v2.json，最终封存为两批 seal_v2.json，第一次清单/封存不覆盖。
