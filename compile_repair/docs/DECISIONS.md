# CompileRepair 决策记录

决策的完整内容在 `../PROMPTS.md` 第 2 节；本文件记录每个决策的当前状态与变化历史，避免不同修订号之间编号含义混淆。第 1 节在状态变化时更新；第 2、3 节只追加。

状态：已定（用户）＝用户明确决定；已定（证据）＝由证据确定，用户未反对；建议＝待用户确认；待定＝尚未讨论到；撤销。

## 1. 当前决策（PROMPTS r2.6）

| 编号 | 内容（摘要） | 状态 | 最近变化 |
|---|---|---|---|
| D1 | 一条流水线处理所有输入，不分训练/检测模式；改动记录并标记 | 已定（用户） | 2026-11-11 |
| D2 | DAppSCAN 为主要评估语料；SOChecker、Trace 与破坏-修复基准为辅；MANDO 846 为与 6c 对照的回归基线；语料只用于测试与评估，不决定覆盖范围 | 已定（用户） | 2026-11-12 |
| D3 | 成功判据：solc 退出码 0、Slither 构造成功、所有声明函数/修饰器与顶层函数的节点有属于编译单元的文件名与起始偏移、Slither 合约集合与 solc AST 合约定义相同 | 已定（证据；CP0.1 A 本机 846/846 验证通过） | 2026-11-12 |
| D4 | 节点身份用 key5（key4 + 同一函数内相同类型与起始偏移的序号）；不去重；source length 只记录 | 已定（证据：key5 本机 678/678 稳定，含重复 key4 的 31/31） | 2026-11-12 |
| D5 | 版本策略细节（区间内升序；已知版本为可选输入；无 pragma 时按有文档出处的版本特征推断区间；pragma 覆盖只在区间内无可用编译器时、下界小版本系列内） | 已定（用户）；CP1 已实现自动策略及同版设置，冻结重放和小样本通过，待审查 | 2026-11-14 |
| D6 | 确定性方法先于代理；覆盖范围由与语料无关的失败分类表决定，有可确定性实施并能机械验证的修复就实现，频率只排顺序 | 原则已定（用户）；分类表方式由 Claude 提出，用户可调整 | 2026-11-12 |
| D7 | 允许新增与改写；改写只在编译错误定位行；记录改动等级并标记节点 | 已定 | 2026-11-11 |
| D8 | 第一阶段单代理 + RAG；第二阶段多代理（失败分析、上下文扩展、异构模型独立提议、工具裁决、至多一轮交流） | 已定（用户） | 2026-11-11 |
| D9 | 审查代理不进主流程，只作消融 | 建议 | 2026-11-11 |
| D10 | LLM 视图中路径与文件名匿名化、注释遮蔽 | 建议 | 2026-11-11 |
| D11 | 代码结构规范（PROMPTS 3.10 节） | 已定（用户） | 2026-11-11 |
| D12 | LLM 模型、API 与费用上限 | 待定（CP8 前） | 2026-11-11 |
| D13 | 哪个创新点使用这些图、是否存数据依赖 | 待定（CP10 后） | 2026-11-11 |
| D14 | 记录只写在 `compile_repair/docs/`，不修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md` | 已定（Claude 提出，用户可撤销） | 2026-11-12 |
| D15 | 6c 固定报告/seal/可信清单只读；用户另批准两个冻结 contract sources.json 及其 metadata 引用源码/CSV，先校验哈希 | 已定（用户；精确范围见 metadata_read_authorization.json） | 2026-11-12 |
| D16 | 生产工具链：Slither 0.11.6 + crytic-compile 0.4.2，独立环境（Python 3.10.x、solc-select 1.0.4、tree-sitter 0.20.4），不改 mando；Slither 0.8.0（mando）只做 6c 精确重放；0.4.x 元组 call 写法按 3.2 节第 10 行处理 | 已定（用户）；CP0.1 已审查；CP1 样本 92/95，余 3 个为预期 Slither 侧失败 | 2026-11-14 |
| D17 | 按两次明确批准安装 0.4.17 及十个系列探针版本；独立追加信任、双哈希，不切换全局版本（原本地 D16） | 已定（用户），11 版已安装并校验 | 2026-11-12 |
| D18 | 编译器获取：补齐 0.4.12–0.8.38 其余 59 个官方正式版本（Codex 请求清单），双哈希、独立追加信任清单；检测时不自动下载 | 已定（用户）；安装与 C 续已审查，支持快照 92/92；CP1 无新安装 | 2026-11-14 |
| D19 | Slither 下限维持 0.4.12（CP1 测得 0.4.11 在生产工具链两种工作目录 5/5 通过、0.4.0–0.4.10 缺文件名；扩展会改变大量 `^0.4.x` 文件的选定版本，受益只有精确 0.4.11 pragma） | 建议（可由用户改）；CP3 按语料频率复议 | 2026-11-14 |

## 2. r1 的决策编号（已被 r2 重新编号，只作历史对照）

| r1 编号 | r1 内容 | 去向 |
|---|---|---|
| D1 | 范围限于七类 `source_files` 846 个文件 | 被 r2 的 D2 取代（外部语料为主） |
| D2 | 版本策略：metadata 优先，区间内升序 | 并入 r2 的 D5 |
| D3 | 成功判据 | r2 的 D3（范围从单文件扩展到编译单元） |
| D4 | key4 节点身份 | r2 的 D4 |
| D5 | v1 不改源码、不调用 LLM | 撤销（用户 2026-11-11 要求覆盖更多编译问题） |
| D6 | 策略只读 pragma、metadata 与运行结果 | 并入 r2 共享上下文不变量与 D10 |
| D7 | 产物写入新的版本化存储 | 并入 r2 的 3.8 节 |
| D8 | 下游用途 | r2 的 D13 |

## 3. 变化历史

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-11 | r1 D1–D8 | 建立（r1） | 提交 39b78108 | Claude |
| 2026-11-11 | r1 D5 | 撤销：用户要求修复不只限于版本问题 | 对话；CHANGE_LOG §1.4 | Claude |
| 2026-11-11 | D1 | 已定（用户）：不设计两种运行模式 | 对话；CHANGE_LOG §2.4 | Claude |
| 2026-11-11 | D6 | 原则已定（用户）：确定性方法先于代理 | 对话；CHANGE_LOG §2.4 | Claude |
| 2026-11-11 | D8 | 已定（用户）：采纳第二阶段多代理设计 | 对话；CHANGE_LOG §2.4 | Claude |
| 2026-11-11 | D11 | 已定（用户）：代码结构四项原则 | 对话；CHANGE_LOG §2.1 | Claude |
| 2026-11-11 | D1–D13 | 按 r2 重新编号建立 | 提交 bfd23e83 | Claude |
| 2026-11-12 | D14、D15 | 新增 | CHANGE_LOG §3.2、§3.4 | Claude |

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-12 | D15 | 用户回复“允许这些必要的只读校验（推荐）”；范围扩至两份冻结 source manifests 及 metadata 引用源码/CSV，不含标签/图/模型 | 对话；CHANGE_LOG §4.4；metadata_read_authorization.json | Codex |
| 2026-11-12 | D16 | 登记必需 0.4.17 安装请求，尚未批准；不能从 D15 推导安装授权 | cp0_v1/recon.json；compiler_installation_request.json | Codex |


### 合并 r2.2 的上游历史

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-12 | D2 | 明确语料只用于测试与评估，MANDO 846 为回归基线 | 用户：方案要修复检测时的任意输入，不只针对当前数据集；CHANGE_LOG §4 | Claude |
| 2026-11-12 | D5 | 已知版本改为可选输入；无 pragma 按文档出处推断区间（仍为建议） | CHANGE_LOG §4 | Claude |
| 2026-11-12 | D6 | 取消频率阈值，改为按失败分类表逐类判定（分类表方式由 Claude 提出） | 同 D2 的用户说明；CHANGE_LOG §4 | Claude |
| 2026-11-12 | D16 | 新增 | CHANGE_LOG §4 | Claude |

| 2026-11-12 | D16 / D17 | 保留 r2.2 的 D16 作为 Slither 兼容性决策；此前本地安装请求 D16 改用 D17，旧历史不回写。用户“可以下载”批准此前单个 0.4.17 请求，未授权下载所有版本 | 对话；cp0_compiler_install_v1/authorization.json | Codex |


### CP0 续作的批准与证据（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-12 | D17 | 原单个 0.4.17 请求获“可以下载”批准；双哈希与版本输出通过，旧客户端 HTTP 403 现场保留 | cp0_compiler_install_v1/authorization.json、verified_compiler.json | Codex |
| 2026-11-12 | D17 | 用户“批准这 10 个探针版本（推荐）”：0.4.12、0.4.26、0.5.17、0.6.0、0.6.12、0.7.0、0.7.6、0.8.0、0.8.4、0.8.38；全部安装校验完成，未授权其余补丁或包升级 | cp0_compatibility_install_v1/authorization.json、trusted_compilers_addition.json | Codex |
| 2026-11-12 | D16 | 39 组探针中两个范围内失败：自定义错误 ErrorDefinition；停在 awaiting_d16，用户未决定升级或限定范围 | cp0_v2/recon.json.compatibility；RECON §10 | Codex |
| 2026-11-12 | D4 / CP2 | 55 份存在重复 key4，本步保留多重集合；图内唯一主键及 6c 可观察回归契约待审。未修改既有 D4 原则或实现替代标识方案 | cp0_v2/invocations.jsonl；RECON §9 | Codex |
| 2026-11-12 | D5 | 升降序实测不同 617 份，moved 44，crossed_minor 0；只作调查，通用选择策略及精确 pragma 边界仍待确认 | cp0_v2/recon.json.matrix_summary；CHANGE_LOG §6.4 | Codex |


### CP0 审查与 r2.3（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-12 | D3 | 加入顶层函数与合约覆盖（防空通过） | CHANGE_LOG §7.2；cp0_review_v1 结论 8 | Claude |
| 2026-11-12 | D4 | key4 改为 key5（加序号） | CHANGE_LOG §7.3；cp0_review_v1 结论 6、7 | Claude |
| 2026-11-12 | D5 | pragma 覆盖边界改写，消除 3.2 第 6 行与 3.3 第 6 条的矛盾；建议确认升序 | CHANGE_LOG §7.2 | Claude |
| 2026-11-12 | D16 | 补测 4 个 Slither 版本，给出推荐，仍待用户决定 | CHANGE_LOG §7.3；slither_versions_corpus.json | Claude |
| 2026-11-12 | D18 | 新增（建议） | CHANGE_LOG §7.2 | Claude |
| 2026-11-12 | 更正 | 上方“合并 r2.2 的上游历史”表中 D2、D5、D6、D16 四行的依据 “CHANGE_LOG §4” 应为 §5（合并时 r2.2 记录由 §4 改编为 §5）；旧行不回改 | CHANGE_LOG §7.4 | Claude |

### CP0.1 A 本机验证与后续请求（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-12 | D3 | A 本机新 D3 846/846，(a)/(b) 失败均 0；包含顶层函数与 AST 名称多重集合检查 | CP0_1_REPORT；cp0_1_v1/revalidation.json | Codex |
| 2026-11-12 | D4 | key5/有序 IR 678/678 稳定，含重复 key4 的 31/31；1,546 组 201,044 条节点无重复 key5 组 | revalidation_audit.json | Codex |
| 2026-11-12 | D16 | 独立环境请求已列，0.9.6/0.3.11、Python 3.8.20、tree-sitter 0.20.4；仍待批准，未安装，production 不可运行 | cp0_1_development_v1/environment_installation_request.json | Codex |
| 2026-11-12 | D18 | 59 版 URL/双哈希已列，0 美元；仍待批准，未安装；B 通过后才执行 | cp0_1_development_v1/compiler_installation_request.json | Codex |
| 2026-11-12 | 待核对 | B 的 transient 0.8.24 文案与审查 >=0.8.28 高级变量 fixture 需核对语法边界；如调整先咨询用户，未实施变更 | CHANGE_LOG §8.4；f0828_transient.sol | Codex |


### CP0.1 A 审查与 r2.4（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-13 | D3、D4 | CP0.1 A 的本机验证经独立复核成立（key5 + 有序 IR 1,546/1,546 与独立导出相同） | CHANGE_LOG §9.3；verify_cp01.json | Claude |
| 2026-11-13 | D16 | 推荐由 0.9.6 改为 0.11.6，备选 0.9.6；原推荐依据的 6 个探针不足（19 个探针：0.9.6 通过 13、0.11.6 通过 19） | CHANGE_LOG §9.2、§9.3；extended_probes.jsonl、compare_prod.json | Claude |
| 2026-11-13 | D18 | 59 个编译器请求与官方 solc-bin 索引逐项一致 | check_install_request.json | Claude |
| 2026-11-13 | 更正 | Codex 登记的 transient 待核对项成立：r2.3 的“0.8.24 transient”错误；r2.4 拆为 0.8.24 Yul tload/tstore 与 0.8.28 transient 状态变量两个探针 | CHANGE_LOG §9.4 | Claude |


### 用户决定 D5、D16、D18（记录者：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-13 | D5 | 已定：区间内升序 | 用户 2026-11-13：“I have followed the approach you recommended.” 对应 r2.4 推荐 | Claude |
| 2026-11-13 | D16 | 已定：生产 Slither 0.11.6（crytic-compile 0.4.2，Python 3.10）；0.8.0 只做 6c 重放 | 同上 | Claude |
| 2026-11-13 | D18 | 已定：安装 59 个编译器，B 通过后执行 | 同上 | Claude |


### CP0.1 B/C 本机执行与停止（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-13 | D5 | 区间升序沿用已批准决定；本轮只用冻结选定版本，不提前实现 CP1 | 用户明确指令；production_comparison.json | Codex |
| 2026-11-13 | D16 | 生产 0.11.6/0.4.2、Python 3.10.21 独立环境已建立，全部 B 门槛通过；mando 不变 | cp0_1_env_v1/authorization.json、B_acceptance.json | Codex |
| 2026-11-13 | D16 旧请求 | 0.9.6/0.3.11 请求作废并保留原字节；由本次 0.11.6 请求与明确授权替代 | environment_installation_request.json、frozen_audit.json | Codex |
| 2026-11-13 | D18 | B 全通过后，59 个官方 solc 全部下载、双哈希与版本校验通过；独立追加信任，支持快照 92/92 | cp0_1_compilers_v1/trusted_compilers_addition.json、installation_summary.json | Codex |
| 2026-11-13 | C 停止边界 | 0.8.24+h0824_blob 默认编译 rc1，blobhash 未声明；224 过、1 失败、271 未运行；不改标准、不自动重试 | compatibility.json、final_status.json；用户要求与 PROMPTS §4.1 | Codex |
| 2026-11-13 | 待审查，未变更方案 | 需审查该 probe 的最低语法版本及 EVM 设置；任何下界/参数调整先咨询用户，在新批次续验；CP1 不开始 | CP0_1_REPORT C.3；CHANGE_LOG §11.4 | Codex |


### CP0.1 B、C 审查与 r2.5（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-13 | D16 | 生产环境与 B 验收经独立复核成立；新增要求：IR 文本中的对象内存地址必须规范化 | CHANGE_LOG §12.3；ir_object_repr.json | Claude |
| 2026-11-13 | D18 | 59 个编译器经复核与官方索引 0 差异，92/92 | CHANGE_LOG §12.3 | Claude |
| 2026-11-13 | D5 | 版本策略加入编译设置（3.3 节第 3a 条）：同一版本先默认设置，再按有文档依据的设置表重试，然后才换版本；不改源码 | CHANGE_LOG §12.2；floor_matrix.jsonl | Claude |
| 2026-11-13 | 更正 | r2.4 的特征探针下界未考虑默认编译设置：Cancun 探针默认下界 0.8.25、h0826 默认下界 0.8.27 | CHANGE_LOG §12.4 | Claude |


### CP0.1 C 续本机验收（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-13 | D5 | 用户明确要求执行 r2.5 §4.2c；settings 白名单/透传及两种设置正负对照通过。自动错误匹配和同版本重试仍留 CP1，未提前实现 | 对话；CHANGE_LOG §13.2/§13.4；compatibility.json | Codex |
| 2026-11-13 | D16 | 沿用 0.11.6/0.4.2 独立环境；两次生产 843/843 指纹一致，各只规范化审查指定 4 行 IR；20/20 mando 与 A 指纹相同 | production_run1/2.json、regression_sample.json | Codex |
| 2026-11-13 | D18 | 不安装、不下载；501 组全部符合预期（496 正例、5 负对照），旧 224 组指纹一致；支持快照可信已安装 92/92，矩阵覆盖新增 59 版 | cp0_1_compilers_v2/compatibility.json、coverage.json | Codex |
| 2026-11-13 | CP1 前提 | C 续已完成本机验收，等待审查；未把已知三份旧合约断言或完整 CFG/CG 语义写成已修复/已穷举 | CP0_1_REPORT C 续；PROMPTS §4.3 | Codex |


### CP0.1 C 续审查与 r2.6（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | D3 | 0.4.12 下限的依据（缺文件名）只在 Slither 0.8.0 中出现且与工作目录有关；生产工具链下限暂不变，CP1 第 6 节测量 | CHANGE_LOG §14.3；github_0411_cwd.jsonl | Claude |
| 2026-11-14 | D5 | CP1 选版复现以 cp0_v2 的 37 个编译器为输入；小样本验收改为可归因比较 | CHANGE_LOG §14.2 | Claude |
| 2026-11-14 | D16 | 生产指纹确定性与设置通路经独立复核成立；CP0.1 完成 | CHANGE_LOG §14.3；verify_c2.json | Claude |


### CP1 本机实现与审查边界（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | D5 | 按 r2.6 实现唯一环境策略；固定 CP0 37 版升降序各 846/846；设置自动重试 6/6；95 样本符合预期，仍待审查 | CP1_REPORT；CHANGE_LOG §15 | Codex |
| 2026-11-14 | D3 下限 | 0.4.11 五个输入两 CWD 均通过；0.4.0/2/9 仍失败。保持 0.4.12，不自行扩展 | cp1_historical_v1/counts.json；用户明确边界 | Codex |
| 2026-11-14 | D16 / D18 | 同步上表已有审查结论；CP1 沿用 production 0.11.6/0.4.2、92 支持版本，没有环境或编译器变更 | frozen_audit.json；CHANGE_LOG §14/15 | Codex |
| 2026-11-14 | 待审查问题 | 原 command() 在 cwd=/ 的相对路径错误只登记；建议确认后用路径函数并补边界测试，尚未实施 | cwd_command_inspection.json；CP1_REPORT | Codex |


### CP1 审查与 r2.7（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | D5 | CP1 的版本策略经独立复核成立（重放 846/846；样本 95/95 独立重算相同） | CHANGE_LOG §16.3；verify_cp1_cases.json、indep_select.jsonl | Claude |
| 2026-11-14 | D19 | 新增（建议）：下限维持 0.4.12 | CHANGE_LOG §16.2；cp1_historical_v1 | Claude |
| 2026-11-14 | 缺陷 | `command()` 按字符前缀求相对路径，工作目录为 `/` 或字符前缀相同的目录时合法合约判为失败；CP1.1 修复 | CHANGE_LOG §16.3；pipeline_cwd.json | Claude |
