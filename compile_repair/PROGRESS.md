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
