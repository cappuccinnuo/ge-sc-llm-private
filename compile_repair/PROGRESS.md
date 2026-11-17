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


## CP0.1 B、C 审查与方案 r2.5（Claude，2026-11-13）

- B 审查通过；59 个编译器与官方索引一致。C 的停止源于方案中探针下界错误（未考虑默认编译设置），Codex 处理正确。
- 新发现：Slither 0.11.6 的 IR 文本含对象内存地址（4 个文件），须规范化。
- PROMPTS r2.5：新增 1.8 节、3.3 节第 3a 条（编译设置，CP1 实现）、4.2c 节 CP0.1 C 续。证据 `artifacts/cp0_1bc_review_v1/`；记录 `docs/CHANGE_LOG.md` §12。
- 下一步：Codex 执行 4.2c 节，不需要新授权。


## 2026-11-13 CP0.1 C 续完成本机验收（修改 AI：Codex）

按 PROMPTS r2.5 §4.2c 在 3742fb75e535b5517ded58659e78737a01b51000 上执行。生产修改 core/model.py、toolchain/solc.py、toolchain/slither.py；测试修改 test_production.py、新增 test_settings.py。settings 元组、两类白名单参数、崩溃 what 消息、production 同参数构造、regression 拒绝设置和 IR 对象地址规范化均已实现，CP0 投影及 fixture 未变。证据为 artifacts/cp0_1_env_v2/、cp0_1_compilers_v2/；完整文件清单在前者 file_inventory.json。

| 验收项 | 预期与实测 | 证据（artifacts 下） |
|---|---|---|
| 两次生产编译/D3 | 各 846 次 solc rc0；各 843 D3，通过同一组文件；另 3 个 0.4.24 AssertionError 与 B 完全相同 | cp0_1_env_v2/production_run1.json、production_run2.json |
| 两次指纹 | 843/843 逐文件 node_facts_v2_sha256 相同；各 110,996 个成功节点 | production_run2.json counts |
| 与 B 归档比较 | 839 个成功文件逐组相同；另 4 个审查指定文件各只变 1 行 IR，类型/偏移/序号/length/声明种类不变 | 两次 production_run*.json 的 changed；cp0_1bc_review_v1/ir_object_repr.json |
| 地址残留/归档哈希 | 四份新归档共 2,208 组，残留 object at 0x 为 0；重算指纹与归档记录差异 0 | cp0_1_env_v2/archive_audit.json |
| mando 抽样回归 | 按 SHA256 排序后 Random(0).sample(...,20)；20/20 D3 且指纹与 A 归档相同，3,267 节点，规范化替换 0 次 | regression_sample_plan.json、regression_sample.json |
| 兼容性计划与执行 | 496 原组合 + 5 设置正对照 = 501；501/501 符合预期，未运行 0；按版本升序，未自动重试 | cp0_1_compilers_v2/compatibility_plan.json、compatibility.json |
| 默认设置正例 | 491/491 solc rc0、production D3 通过 | compatibility.json counts |
| 默认设置负对照 | 4 个 0.8.24 Cancun 探针 rc1、1 个 0.8.26 require 自定义错误探针 rc2，诊断与 r2.5 一致；均未运行 Slither | compatibility_invocations.jsonl、archive_audit.json |
| 设置正对照 | 四组 0.8.24 + --evm-version cancun、一组 0.8.26 + --via-ir，5/5 rc0、D3；Slither 记录同样的设置 | compatibility.json results |
| 上次成功组 | 原 C 的 224/224 结果、输入/编译器身份、节点内容与指纹全部相同 | compatibility.json previous_224_equal |
| 覆盖口径 | 可信支持快照 0.4.12–0.8.38 已安装 92/92；本次矩阵覆盖新增的 59 版，59/59 版计划完成 | cp0_1_compilers_v2/coverage.json、compatibility.json per_version |

| 检查 | 实测 | 原始日志 |
|---|---|---|
| 新逻辑与分层（production / mando） | 各 27 passed | unit_production.log、unit_mando.log |
| 完整模块（production） | 506 passed，6 skipped，28.69 秒 | pytest_production.log |
| 完整模块（mando） | 83 passed，429 skipped，6.60 秒 | pytest_mando.log |
| 冻结 DFG v2（mando） | 2653 passed，9 warnings，181.50 秒 | pytest_dfg.log |

测试命令与跳过说明见 CP0_1_REPORT C 续.3；使用两环境 python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests，以及 mando 同参数的 scripts/DFG/dfg_v2/tests，完整 argv 在 test_summary.json。

本轮没有非预期验收结果，没有测试失败后重跑，也没有方案外算法变更。读取阶段 WSL 未安装 rg，按现有 Python/sed 完成只读检查；ir_object_repr.json 实际是两个连续 JSON 对象，首次单对象 json.loads 报 Extra data 后按原格式分别 raw_decode，原文件不改。这属于证据格式适配，不改变 4 文件/4 行预期。生产原始诊断保留已知断言的源码缩进，以无损 gzip 提交并逐字节回读校验，原日志留在本地，SHA 与压缩对应关系见 log_compression.json。

用户本轮明确要求执行 r2.5 §4.2c，并规定需要安装/下载或验收不符即停。本次未发生上述停止条件；没有新增授权请求，没有安装、下载编译器/语料/文档、LLM 调用、全局 solc 切换或 HGT 训练，费用 0 美元。A、B 结论、旧产物和既有 C 失败现场均保留。本步只完成工具链接口与验证：按错误自动触发设置、版本升序选择和两行设置表属于 CP1；第 10 行源码改写属于 CP6，均未实现。CP0.1 C 续已完成本机验收，仍须审查通过后才能开始 CP1。

报告、五段 CHANGE_LOG §13、HANDOVER 四段交接/当前状态、DECISIONS 状态及历史、两批 README 均同步更新；doc_check 与封存审计结果见 CHANGE_LOG §13.5 的最终补记。与 r2.5 的验收差异 0，未放宽判据。


## CP0.1 C 续审查与方案 r2.6（Claude，2026-11-14）

- C 续审查通过（两次生产 743/743 指纹相同；与独立运行 740/740 相同；兼容性 501/501；seal 全部一致）。CP0.1 完成。
- PROMPTS r2.6：新增 1.9 节；CP1 选版复现固定用 cp0_v2 的 37 个编译器；小样本验收改为可归因比较并加入 3 个已知 Slither 侧失败合约；0.4.11 缺文件名测试改为替身，新增 CP1 第 6 节测量历史编译器。
- 证据 `artifacts/cp0_1c2_review_v1/`；记录 `docs/CHANGE_LOG.md` §14。下一步 Codex 执行 CP1。


## 2026-11-14 CP1：核心层与环境方法完成（修改 AI：Codex）

按 PROMPTS r2.6 §4.3 从 d5e84d39 同步后实现一般文件/片段 repair、core provenance/store、唯一 environment 策略和设置表；survey 委托，原 solc 函数与 Slither 不改。新增生产 5 文件（core/provenance、store，rules/__init__、environment，pipeline），修改 4 文件（core/model、toolchain/solc、evaluation/survey、cli）；新增 test_core/test_environment/test_pipeline。生产 14/30 文件、9 测试、28 fixture 不变。完整清单见 CP1_REPORT 与 file_inventory.json。

两个环境固定 37 个编译器和 CP0 rc/D3，离线升/降序各 846/846，不重跑 CP0；六个真实设置副本自动同版本重试通过。95 样本 92 成功、仅 3 指定 Slither 侧失败；91 个选版相同，1 从 0.5.6 改选新增 0.5.5，有区间/rc0/D3 依据；无无法归因差异、覆盖或跨系列。197 solc、101 Slither；95 源文件无改动，11,822 成功节点均 original。样本实际 metadata 命中 0、无 pragma 1；不能混算为全部 metadata 重跑。证据 cp1_sample_v1/acceptance_summary.json、archive_audit.json。

历史 23 组合、23 rc0 编译、46 次生产 Slither；0.4.11 在两个 CWD 各 5/5，0.4.0/2/9 仍缺映射，保持 0.4.12。三个重入文件在 0.4.24/25/26 均 rc0 后 AssertionError，未提前改写。另登记原 command() 在 cwd=/ 的路径边界，只读确认；建议审查/用户确认后再修正，历史测量前置编译在仓库根。pytest 归档遇 current 符号链接重复，排除别名读取原结果，没有重跑测试。最后记录写入前 WSL 连接超时，四文件 SHA 未变、短命令恢复后分批写入，没有重启或重跑；见 documentation_interruption.json。

命令 python -B -m pytest -q -ra -x -p no:cacheprovider：生产模块 546 passed/6 skipped，mando 116/436，DFG 2653 passed/9 warnings；收据/压缩日志在 cp1_development_v1/pytest_*。冻结 28,236 文件、354 code_refs、96 solc 与环境元数据相同，分层/Python 3.7 语法通过。八份文档检查及暂存记录同目录保存。交接/训练改变记录为 docs/HANDOVER、CHANGE_LOG §15；方案未改，未下载安装、LLM、训练、全局切换或 push。本地 CP1 提交后等待审查，CP2 不开始。


## CP1 审查与方案 r2.7（Claude，2026-11-14）

- CP1 审查：实现与验收成立；冻结重放 846/846；样本 95 个审计无问题、独立重算 95/95 相同；端到端（覆盖、推断、交集）正确。
- 缺陷：`command()` 相对路径按字符前缀截取，工作目录为 `/` 或字符前缀相同的目录时合法合约判为失败。另有 solc 超时停止批次、无 git 时崩溃两处健壮性问题。
- PROMPTS r2.7：新增 1.10 节、4.3b 节 CP1.1、D19（建议维持 0.4.12）；CP2 提示更新；CP3 加入 `||` pragma 与 Slither 超时。
- 证据 `artifacts/cp1_review_v1/`；记录 `docs/CHANGE_LOG.md` §16。下一步 Codex 执行 CP1.1。


## 2026-11-14 CP1.1：路径与健壮性修复完成，待审查（修改 AI：Codex）

依据 PROMPTS r2.7 §4.3b；先 pull --ff-only 到 d4f4b48a2484591dc185b90475f775f6c9f5498d（Already up to date），通读全文与指定交接、决策、CHANGE_LOG §15/16、cp1_review_v1/README。代码仅改 toolchain/solc.py、toolchain/slither.py、pipeline.py，新增 tests/test_cp1_1.py；生产 .py 仍 14 个，测试 10 个。新增产物 artifacts/cp1_1_v1；报告只在 CP1_REPORT.md 追加 CP1.1。交接和训练改变记录分别为 docs/HANDOVER §6 与 CHANGE_LOG §17，当前 §0–5 和 DECISIONS 同步已有审查与本轮状态。

完成按路径组件生成 argv；6c 冻结分支在 / 或前缀兄弟目录提前拒绝；solc 超时记为当前输入 unrepaired / solc_timeout 后继续批次，不重试；信任/完整性错误仍停止；没有 Git/HEAD 时 commit=null、summary 标记 code_commit_unavailable，保留实现 SHA256。没有 monkeypatch、环境或全局 solc 修改，也没有替代方案或放宽验收。

实测：两环境的 MANDO 846/846 与兼容性 501/501 新旧 argv 一致；五种 cwd 真实编译各 5/5；三种超时场景各 3/3；生产批次续行/信任停止和两种无 Git 场景通过。九组 CLI 全成功，三目录下状态、版本、设置、key5+IR+标记逐个相同；共 12 次前置 solc、9 次 Slither、90 个 original 节点。三个版本分别 0.5.0、0.8.24+cancun、pragma 覆盖后的 0.4.12，详见 module_acceptance.json、cli_acceptance.json 与 CP1_REPORT 的 CP1.1。

测试命令为各环境 python -B -m pytest -q -ra -x -p no:cacheprovider <目标>，收据含完整 argv/环境/basetemp：production compile_repair/tests 562 passed/6 skipped（60.88 秒）；mando 同目标 128 passed/440 skipped（13.18 秒）；mando scripts/DFG/dfg_v2/tests 2653 passed/9 warnings（160.19 秒）。三轮均首次通过；原始结果与压缩日志保存在本批次，无失败重跑。WSL 无 rg 时使用已有 Python/sed；误检不存在 test_solc.py 后读取实际 test_toolchain.py，仅为读取操作，没有改变测试口径。

原 CP0–CP1 正式产物、旧报告既有字节、fixture、scripts 与语料保持。冻结核验与 6 份 doc_check 结果见 frozen_audit.json、doc_check_v* 以及 CHANGE_LOG §17.5；成功后本地 CP1.1 提交、不自动 push。没有重跑 CP1 样本，没有 CP2/CP3/CP6、下载、安装、训练、GPU 锁或 LLM 调用；费用 0。遗留 || pragma 和 Slither 进程内无超时按 r2.7 留 CP3，D19 仍建议维持 0.4.12；待 CP1.1 审查通过才进入 CP2。


开发记录补记（修改 AI：Codex）：冻结审计辅助脚本第一次从文件路径启动时，在执行检查前因未把仓库根加入 sys.path 而报 ModuleNotFoundError: scripts；没有生成 frozen_audit.json，没有实际冻结判据失败。保留 frozen_audit_launch_error.json 后，只给本批次辅助脚本补齐仓库导入路径，再执行冻结核验。生产代码、验收标准、已通过的三轮 pytest 和九组 CLI 没有修改或重跑；这是证据脚本启动问题，不是编译器或环境缺包，也未安装任何内容。


无损交付归档补记（修改 AI：Codex）：首次暂存清单 123 文件，内容 SHA 检查通过，但 git diff --cached --check 返回 2：三个精确 0.4.10 case 的 pragma_overridden.sol 第 3 行是按方案要求生成的等长空格，触发行尾空白检查。该空格不能删除，否则会改变字节偏移与既有 case seal。沿用 CP1 的交付方式，把九组 CLI 输出的 84 个文件无损打包为 cli_cases.tar.gz，逐成员 SHA256/长度回读 84/84 一致；原文件和九个 case seal 在本地保留不改。未放宽 Git 检查，未重新运行 CLI，未修改生产存储格式。

CLI 归档 SHA256 为 bec8f18cdc4510bf066d4bf79abe4489ab8d70c8c8e61a263b60ee63f1cf844b，大小 95,681 字节，archive_audit.json 保存成员清单。前文 cwd/out2/* 路径现在表示归档内成员，替代此前“按原目录提交”的交付说明。首次 seal.json、file_inventory.json、final_validation.json 均保留原字节，作为归档前阶段快照；当时的六份文档保存于 prepackaging_documents.tar.gz，与初版文档哈希完全一致。最终交付以 delivery_seal.json、delivery_inventory.json 为准，它们绑定最终文档及两个压缩包；不得将初版快照误当最终提交清单。失败现场为 staging_failure.json，当前原始目录只留本地，不删除、不提交重复副本。

归档说明纳入 CP1_REPORT、PROGRESS、CHANGE_LOG §17.5、HANDOVER 和本批次 README；追加记录遵守历史字节边界。doc_check_v1/v2 均已 6/6 通过，归档补记后按相同六目标再检查并保存新收据，完成后重新核对精确暂存范围和格式，再本地提交；编译、测试与 CLI 的已通过结果保持。


## CP1.1 审查与方案 r2.8（Claude，2026-11-14）

- CP1.1 审查通过：路径缺陷修复（8/8 rc 0）、argv 1,347/1,347 不变、三种工作目录结果相同；超时、无 git、regression_6c 防护符合要求。
- PROMPTS r2.8：新增 1.11 节；CP2 存储格式补充边种类与调用分类（LibraryCall 先于 HighLevelCall、其他 Call 子类不丢弃）；第 2 节改为列出归因；给出运行时间估计。
- 证据 `artifacts/cp1_1_review_v1/`；记录 `docs/CHANGE_LOG.md` §18。下一步 Codex 执行 CP2。


## 2026-11-14 CP2：生产图存储通过，6c 首差停止待审查（修改 AI：Codex）

按 PROMPTS r2.8 §4.4，先 pull --ff-only 至 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18，完整阅读方案与指定交接/审查记录。修改 toolchain/slither.py、pipeline.py、cli.py、tests/test_pipeline.py，新增 tests/test_graph.py、tests/fixtures/graph_calls.sol；仍 14 个生产 .py。实现 key5/有序 IR/标记、CFG 分支与全部 Call 存储、逐输入 flush 后验收停止回调，不改 D3/选版。四个新批次为 cp2_development_v1、cr_store_mando_v1/v2、cp2_6c_v1；完整文件清单 delivery_inventory。报告 CP2_REPORT，交接 HANDOVER §6，训练改变记录 CHANGE_LOG §19，DECISIONS 记录授权与停止状态。

2026-11-14 用户回复“允许单列既有下限差异，记录后继续”，仅在与 6c 的选版归因中单列旧 0.4.11 → 0.4.12，CP2 对 CP0 三类及 239/239 精确重放标准保持。请求 96/92 计数字段另以 compiler_count_clarification 澄清为 92 支持 + 4 历史，保留原记录。6c 唯一运行前核对 239 原目标路径及源码 SHA；保留旧目标，从本仓库根只 import 冻结编译和提取函数。

两次 production 各 846 输入、843 成功 / 3 规定失败，843 图字节相同、846 状态和版本相同；每轮 110,996 节点、87,645 边、45,565 调用，节点全 original。主阶段 275.856/276.572 秒、完整命令 276.722/277.496 秒，不能沿用估计时间。CP0 842 同版且生产归档 key5+IR 842/842 相同，1 项 (a) 0.5.6 → 0.5.5；与 6c 选版 238 同、1 已批准下限差异。来源 cp2_summary、逐输入 acceptance/receipt；按目录来源/系列/flags 表见 CP2_REPORT，不读标签。

6c 第 87 个 buggy_43.sol 首差停止：86 同 / 1 差，旧 252、本次 251 occurrence，仅旧 Post 继承上下文的 [162,out,DEF]，节点起点 5154 为循环条件 i < 32。停止后离线逐字段核对也只有此差异，底层根因未证明，未重复编译或改键。剩余 152、降序与 CP3 未运行；CP2 整体未完成。完整现场在 cp2_6c_v1，分析在 replay_discrepancy_analysis，下一步先独立审查，新执行或改方案先咨询。

各环境 python -B -m pytest -q -ra -x -p no:cacheprovider 加目标与新 /tmp basetemp：production compile_repair/tests 567 passed/6 skipped（54.56 秒）、mando 同目标 130/443（12.85 秒）、mando DFG v2 2653 passed/9 既有 warnings（159.05 秒），收据 pytest_*.json。三轮首次通过，手写探针全部 10 类调用和停止/确定性测试通过。前置读 UNC、引号、缺 rg、code_refs 依赖分别用 scoped WSL/base64/现有工具/已有 mando 处理；停止后一次只读审批超时允许的一次重试成功，一次超长文档命令未创建进程，拆成短命令，均已记录，未安装内容或重试正式验收。

三个正式存储无损 tar 分别 4,229/4,229/93 成员，逐成员回读通过，散文件保留不删。最终 frozen_audit、9 份 doc_check、交付与暂存核验见 CHANGE_LOG §19.5；完成强制记录后本地提交，不自动 push。旧 CP0–CP1.1 产物/结论、scripts、输入、环境、编译器和根记录保护不改。没有安装、下载、LLM、HGT 训练、GPU 锁或全局 solc 改动，费用 0。


## CP2 审查与方案 r2.9（Claude，2026-11-14）

- CP2 生产部分复核成立：两次全量确定，同版本 842/842，调用分类与引用完整。
- 缺陷：空体 if 的两条边都标 true（86 个节点）。
- 6c 重放停止的原因：Slither 0.8.0 局部写集合不确定（同进程 10 次得到 252/253/254）；生产 0.11.6 确定。
- PROMPTS r2.9：新增 1.12 节、4.4b 节 CP2.1、D20（稳定事实判据，待用户批准）。证据 `artifacts/cp2_review_v1/`；记录 `docs/CHANGE_LOG.md` §20。


## CP2.1：生产边修复通过，6c D20 停止（2026-11-14，修改 AI：Codex）

执行 PROMPTS r2.9 §4.4b，起始 compile-repair@1ed79a6708f505ecb9aa80b157a43f9e07608c9f；D20 已按用户“同意 D20”落盘授权并更新 DECISIONS。只改生产文件 toolchain/slither.py 的 graph_facts，补 18 个条件边测试及新 fixture，生产文件数保持 14。所有结果写入 cp2_1_v1、cr_store_mando_v3/v4、cp2_6c_v2，旧批次不改。

两次生产均 843 成功/3 已知失败，843 图字节相同；与 v1 仅 40 文件 86 条已审查分支标记变化。每轮 110,996 节点、87,645 边、45,565 调用；5,507 true、5,507 false，其他边、节点和调用不变。同版本生产归档 842/842 相同，另 1 份沿用 CP0 归因 (a)。数据见 cp2_1_summary.json、ascending1/2_acceptance.jsonl。

6c 在第 227 份 reentrancy/buggy_44.sol 按 D20 停止：223 份精确同、3 份仅波动差异通过、1 失败。四份主运行差异各在一个新进程连续提取 10 次，没有第 12 个样本。失败键为 MultiHashWrapper 声明上下文的第 282 行 out DEF（L1、非继承），6c 重数 1，但 11 次均 0；全部计数和参考原始行见 CP2_REPORT 的 CP2.1 及 captured_replay_audit.json。观察到 9 个不稳定键，均 L1 DEF，其中 5 继承、4 非继承；未归因内部根因。

production 模块 585 passed/6 skipped，mando 模块 147/444，冻结 DFG 2653 passed/9 warnings；D20 边界 12 项和停止现场离线复算均通过。剩余 12 份、降序比较和 CP3 未运行，整体 CP2.1 未通过。doc_check、保护审计及强制记录完成后本地提交；无安装、下载、LLM、训练或 push。下一步先审查已封存证据，改变方案仍需用户确认。


## CP2.1 审查与方案 r2.10（Claude，2026-11-14）

- CP2.1 图修复与生产重跑复核成立（只差审查指定的 86 条边）。
- 6c 第 227 个文件的停止是采样不足：同进程 40 次中该键出现 18 次；10 个不稳定键同属“for 循环体内按下标写入的数组、DEF 记在循环条件行”。
- PROMPTS r2.10：新增 1.13 节、4.4c 节 CP2.2、D20a（待用户批准）。证据 `artifacts/cp2_1_review_v1/`；记录 `docs/CHANGE_LOG.md` §22。


## 2026-11-14 CP2.2：D20a 与剩余验收完成（修改 AI：Codex）

执行 PROMPTS r2.10 §4.4c，pull --ff-only 后 HEAD=36c6109fa9271608feb8f4634eca6ab7ff6a192a。通读全文及指定 HANDOVER/DECISIONS/CHANGE_LOG §21/22、cp2_1_review_v1/README。用户“同意 D20a”的授权于运行前写入 artifacts/cp2_2_v1/authorization.json，DECISIONS 改为已定；baseline 先记录全部保护身份。

新增脚本和审计只在 cp2_2_v1：run_replay、audit_replay、run_corpus、run_checks、launch_phase、summarize、package_store、audit_frozen、check_docs；新正式结果为 cp2_6c_v3、cp2_desc_v1。修改文档仅 CP2_REPORT（追加 CP2.2）、本文件、docs/CHANGE_LOG、HANDOVER（0–5 当前状态及末尾记录）、DECISIONS。完整新文件清单见 delivery_inventory.json；生产 14 文件及全部测试文件均不改。

6c 合计 239/239：234 精确、4 D20、1 D20a。旧 227 主样本全部复用；第 227 追加第 1 次观察到参考重数即停，其余 12 份在新进程按原顺序运行，第 239 另取固定 10 次后 D20 通过。本轮新增 23 次提取；只读独立复算通过。12 个波动键均 L1 DEF，5 继承、7 非继承；全部键、源码行与逐次计数在 captured_replay_audit.json。新增 while 条件观测，不推断内部根因。

降序全量 843 成功/3 已知 Slither 侧失败；229 同版、614 不同版，843/843 key5 与规范化有序 IR 相同；length 815 同、28 差仅诊断。descending_comparison.json 保存全部逐文件结果和类别分布，不读标签。两个正式新 tar 分别 57/4,229 成员，逐成员回读通过，散文件保留。

测试由 run_checks.py 依次运行 production、mando、dfg；实际命令为相应环境 python -B -m pytest -q -ra -x -p no:cacheprovider，模块目标 compile_repair/tests，DFG 目标 scripts/DFG/dfg_v2/tests，使用新 /tmp basetemp。结果 production 585/6、mando 147/444、DFG 2653 passed/9 既有 warnings；11 个 D20a 合成边界通过。具体命令、rc、时间和 SHA 在 pytest_*、replay_invocation、descending_invocation 中。

无方案外改变。WSL 无 rg 改用 git ls-files/Python；一次文档封装 JS 引号解析失败发生在工具执行前、没有文件操作，改为普通 UTF-8 文本后完成。旧未执行的降序驱动只列成功输入，本轮新驱动遵循 r2.10 对全部 846 输入验收；未改生产策略。强制记录、doc_check 与保护审计后本地提交，不自动 push。CP3 未运行，等待独立审查；无安装、下载依赖/语料/文档、LLM、HGT、GPU 锁或全局 solc 修改，费用 0。


## CP2.2 审查与方案 r2.11（Claude，2026-11-17）

- CP2.2 复核成立：降序 843/843 节点、IR、边、调用相同（28 个文件只差 length）；6c 239/239，回归结束；第 239 个文件的波动在 Claude 环境独立复现。
- 新发现两个缺陷：版本读取依赖整文件解析（0.8 新语法失败）且要求 UTF-8；可编译的合约被记为版本约束不支持。
- PROMPTS r2.11：新增 1.14 节、4.4d 节 CP2.3，CP3 第 0 节补充诊断前提与第 10 行改写的实测。证据 `artifacts/cp2_2_review_v1/`；记录 `docs/CHANGE_LOG.md` §24。


## 2026-11-17 CP2.3：版本读取修复与回归通过（修改 AI：Codex）

执行 PROMPTS r2.11 §4.4d，先 pull --ff-only origin compile-repair，起点 361772f74b28b4dce0ad094907dc3dbf27a17794；通读 PROMPTS、指定当前状态/审查证据和记录规范。旧缺陷先复现：6 个 CLI 输入被拒、直接 solc/production D3 9/9 通过。仅改 rules/environment.py 的字节定位/表达式求值/Latin-1 推断和 pipeline.py 的异常捕获，共 +73/-16；生产文件仍 14。新增一个测试文件和六个夹具，已有产物、测试和源码不变。

两个环境各 846 个输入与 28 个可解析夹具的区间及补丁字节范围均与冻结实现相同；其余 8 个夹具按真实异常明列。9 个 CLI 正例全部成功、1 个并集负例仍拒绝；新增探针与合约体内 pragma、CR/LF/偏移等边界都已测试。v5 全量一次：843 成功、3 已知 Slither 侧失败；846/846 记录字段与 v3 同，843/843 graph 字节同。证据 cp2_3_v1 与 cr_store_mando_v5，详见 CP2_REPORT 的 CP2.3。

测试 production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings。v5 耗时 239.81 秒，tar 4,229 成员逐哈希回读通过；探针存储 58 成员无损交付。基线准备遇到旧首次 seal 已被 seal_v2 替代的情况，核验既有 README/最终 seal 后使用登记的结果集合并保持所有旧字节，见 development_issues；正式验收无意外失败或重试。

已更新交接、训练改变记录（模块 CHANGE_LOG §25）、决策历史及报告；doc_check 与保护审计完成后本地提交，不自动 push。CP2.3 待独立审查，CP3 未开始；6c 不重放。没有方案外调整、安装/下载、LLM、训练、GPU 锁或全局 solc 变更，费用 0。


CP2.3 最终补记（Codex）：7 份 doc_check v1 通过，补记后的最终复检见 v2。最终保护审计 frozen_audit_v2 通过；首次审计把 6 个旧测试手工空指纹 seal 计入真实 CLI，原结果与驱动保留，已按真实封存证据纠正归类。3 个真实 CLI seal 与 v5 的实现指纹一致，没有改生产代码、测试或判据；完整过程见 CHANGE_LOG §25。


## CP2.3 审查与方案 r2.12（Claude，2026-11-17）

- CP2.3 复核成立：与原实现在 1,646 个可读文件上全同（MANDO 846/846）；v5 与 v3 记录与图字节相同；9 个 CLI 正例成功。
- 遗留两项（继承自冻结语义）：pragma 内注释被拒；缺分号的 pragma 与 `||` 记录相同。另登记测试可移植性（既有）。
- PROMPTS r2.12：新增 1.15 节、4.4e 节 CP2.4，CP3 第 0 节细分版本约束不支持的原因。证据 `artifacts/cp2_3_review_v1/`；记录 `docs/CHANGE_LOG.md` §26。


## 2026-11-17 CP2.4 完成：pragma 注释与未结束指令（修改 AI：Codex）

按 PROMPTS r2.12 §4.4e，起点 compile-repair@7e32d85c6d02049fd606a9410759dbfb9f18fb7a，pull 为 Already up to date。生产只改 rules/environment.py 两函数（+5/-4 行，生产文件 14），从遮盖后的字节读取版本表达式，并区分未结束 pragma。新增 test_pragma_comments.py、三个 pragma_comments 夹具，旧 test_pragma_bytes.py 显式登记两个新夹具的冻结拒绝边界；测试参照为经 SHA 校验的 CP2.3 原文件。pipeline、D3、D5、key5、settings、原始补丁区间及字节不变。

新批次 cp2_4_v1，修改前复现符合审查；两环境各 846 MANDO + 35 可读取夹具的 interval、Patch、EnvironmentPlan 八字段全同，升降序各一份，合计每环境 1,762 份计划。两个新注释 CLI 成功（0.8.0 / 0.5.0），源码不变；缺分号和 union 分别记录 unterminated pragma directive / unsupported pragma expression，均不调用编译器。验收证据为 equivalence.json、cli_acceptance.json、cli_acceptance_store.tar.gz。

production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG v2 2653 passed/9 warnings。命令均为指定环境 python -B -m pytest -q -ra -x -p no:cacheprovider，目标和独立临时目录见 pytest_*.json；没有失败后重跑。完整性与 doc_check 见 frozen_audit.json、doc_check_v*。CP2_REPORT 已追加 CP2.4；CHANGE_LOG §27、HANDOVER 与 DECISIONS 已同步，完整文件清单见 delivery_inventory.json。

与冻结实现的两项有意偏离由 r2.12 明确要求，未提出新的替代方案或放宽判据。UNC 文件访问问题通过 WSL 读取解决；旧冻结测试的两个新夹具例外明确断言并单独验收，详见 development_issues.json。既有测试可移植性、union 和 Slither 超时仍登记在后续边界。本轮不重跑全量生产或 6c，不安装/下载/LLM/训练，不切全局 solc；本地提交后待独立审查，未自动 push，CP3 未开始。


## CP2.4 审查与方案 r2.13（Claude，2026-11-17）

- CP2.4 复核成立：与 CP2.3 在可读的 1,656 个文件上全同；MANDO make_plan 升降序 1,692/1,692；CLI 两个注释输入成功、两个拒绝输入不调用工具。
- 无遗留需在 CP3 前修复。CP3 提示补两处：缺分号后接指令的分类单列；多文件单元走命令行编译路径（不用 standard JSON）。
- PROMPTS r2.13：新增 1.16 节。证据 `artifacts/cp2_4_review_v1/`；记录 `docs/CHANGE_LOG.md` §28。下一步 CP3，语料获取前等用户授权。


## 2026-11-17 CP3 前置核查：获取请求待授权（修改 AI：Codex）

从 compile-repair@0d39c3546dbb8d456ef7c2fd5534143dcef92c94 开始，pull --ff-only 已同步，按 PROMPTS r2.13 §4.1、§4.5 核对当前方案及 CP2.4 审查。最新任务明确是 CP3。尚未实施分类器、项目闭包或 CP3 探针；已停止在官方文档/外部语料下载授权处，不能把本轮称为 CP3 完成。

新增 CP3_REPORT.md、artifacts/cp3_preflight_v1；其中 authorization_request.json 是待批准请求，未创建 authorization.json。十份官方文档固定标签/提交/路径、三套语料固定提交和目标子目录、仓库外保存位置、零美元上限及建议本地研究用途均已列明。详细文件及 SHA256 见 delivery_inventory.json；交接更新 §0–5 与末尾记录，训练改变/运行记录追加 CHANGE_LOG §29，DECISIONS 状态不变。

仅获取 GitHub 仓库身份与 tree/ref 元数据，未下载源码或文档正文。三语料指定文件总 235,835,756 字节（约 224.91 MiB），文档 10 份/188,817 字节；目录计数 DAppSCAN 608/21,457 .sol、Trace 5,000 / 83 项目 3,092 .sol / 15，与 cr_pre_v2 对应项一致。源码 SHA256、import、pragma、SOChecker 897 条内容计数尚未核验，数据出处为 remote_metadata.json 和请求文件。

现有测试 production 622 passed/6 skipped，mando 181/447，DFG 2653 passed/9 既有 warnings；每轮一次，无失败重试。实际命令为相应环境 python -B -m pytest -q -ra -x -p no:cacheprovider，独立 /tmp basetemp，完整命令/rc/时长/日志哈希见 pytest_*.json。冻结完整性与文档检查在本轮末尾完成后补记；这些测试不构成 CP3 新功能验收。

前置问题是本地资料缺失、DAppSCAN 整仓目录响应截断、Solidity 仓库迁移和调试输出体量，处理分别为提出授权请求、查询完整目标子树、核对同一 repository id、改为准确聚合，见 development_issues.json。没有与 PROMPTS 不一致的方案修改。已知 || 与 Slither 无超时保留后续范围，未擅自实现。完成强制记录与检查后本地提交，不自动 push；无新下载正文/语料、安装、LLM、训练或全局 solc 改动。

CP3 前置终审补记：五份 doc_check v1 通过，冻结审计通过；28,750 个保护跟踪文件与 25,828 个旧封存文件未变，354 个 code refs、96 个编译器与 14 个生产文件不变。补记后的最终文档收据为 doc_check_v2_invocation.json；精确清单/封存分别见 delivery_inventory.json 与 evidence_seal.json。下载授权仍 pending，CP3 功能未实施。


## 2026-11-17 CP3 授权续做：资料获取与前提探针通过，内容差异后停止（修改 AI：Codex）

用户批准“批准全部资料，仅本地研究使用（推荐）”，在88b499e7基础上继续PROMPTS r2.13 CP3。先保存cp3_v1/authorization，再按固定提交获取十份官方文档和三语料指定子目录；文档188,817字节、语料29,611文件/235,835,756字节全部Git blob与SHA256核验通过，源码在仓库外且不提交。未安装或扩大获取权限，费用0。

新增cp3_v1及tests/fixtures/cp3_project三文件，生产代码/已有测试/旧证据未改，生产文件14。分类初表29类/125条breaking changes先于内容统计建立，模板与规则仍待逐类实测；四版本三文件combined-json与production Slither前提探针4/4通过，D3(a/b)和全部文件映射覆盖成立。完整清单见delivery_inventory，具体证据见taxonomy_initial_receipt、project_probe_acceptance。

结构核对DAppSCAN四类字段全部与cr_pre_v2相同（608项目/21,457.sol；相对找到38,122、缺1,094），Trace为5,000/83项目与3,092/15。SOChecker三份897条input同序，ours+GPT仅846条，是严格子集少51条，没有新增或重复input。按获批请求内容计数不符即停止，未合并/去重/补数据，证据structure_acceptance与structure_review_request。

待确认建议保持原定ours.json897条唯一分类输入，846条附属子集只记录来源差异；不是重新请求已批准下载。生产分类器/项目闭包、语料步骤1/6、失败统计、其余前提探针与最终D6/CP4判断未完成。记录更新CP3_REPORT续节、CHANGE_LOG §30、HANDOVER §0–5及追加段、DECISIONS；初表覆盖漏掉两个嵌套条目等开发问题与处理在development_issues。

规定测试用对应production/mando环境python -B -m pytest -q -ra -x -p no:cacheprovider，独立/tmp目录，模块目标compile_repair/tests，DFG目标scripts/DFG/dfg_v2/tests。最终数字与doc_check、冻结保护核验在下方终审补记和本批次收据，不把结构失败写成CP3通过。仅本地提交，未push、训练、LLM、全局solc或6c重放；后续需处理待确认项后使用新批次，禁止覆盖现有产物。


本轮终审补记（Codex）：production 622/6、mando 181/447、DFG 2653 passed/9既有warnings；六份doc_check v1通过，补记后以v2收据为准。冻结审计确认28,779个保护跟踪文件、25,828个旧封存文件、354个引用、96个编译器、两套环境及14个生产文件不变；29,611份语料文件和10份文档哈希保持。SOChecker差异仍待确认，CP3未完成，仅本地检查点提交。收据数字解析的转义错误已在development_issues记录并从既有日志纠正，无测试重跑。


交付补记（2026-11-17，修改 AI：Codex）：暂存后的 git diff --cached --check 报告三份 Git init 原始 stderr 的提示行尾空格，以及 solc 0.8.38 原始 stderr 的末尾空行。为保持取证原字节，未修改四份日志或已封存 cp3_v1；仅将这四个精确日志路径排除后，其余全部文件的同一空白检查通过。该处理不排除代码、文档或任何CP3验收项；SOChecker的结构差异仍为未通过。

另建 artifacts/cp3_delivery_v1 保存原始报错、四日志SHA、检查命令和上次doc_check对应的文档快照。最终文档检查与提交清单改以该交付批次的 doc_check_final_invocation.json、delivery_inventory.json 为准；cp3_v1/evidence_seal.json 原样保留。没有重跑编译或测试，也没有改变生产实现、授权范围或待确认建议；本地检查点提交后仍等待对846/897子集差异的处理确认。


交付终检补记（修改 AI：Codex）：七份 doc_check_delivery_v1 全部通过；本条补记后再次检查的最终文档哈希见 cp3_delivery_v1/doc_check_final_invocation.json。四份原始工具日志按精确路径保留并豁免空白检查，其余文件检查通过；编译验收和 SOChecker 待确认状态均未改变。
