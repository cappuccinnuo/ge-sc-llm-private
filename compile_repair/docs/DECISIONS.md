# CompileRepair 决策记录

决策的完整内容在 `../PROMPTS.md` 第 2 节；本文件记录每个决策的当前状态与变化历史，避免不同修订号之间编号含义混淆。第 1 节在状态变化时更新；第 2、3 节只追加。

状态：已定（用户）＝用户明确决定；已定（证据）＝由证据确定，用户未反对；建议＝待用户确认；待定＝尚未讨论到；撤销。

## 1. 当前决策（PROMPTS r2.14）

| 编号 | 内容（摘要） | 状态 | 最近变化 |
|---|---|---|---|
| D1 | 一条流水线处理所有输入，不分训练/检测模式；改动记录并标记 | 已定（用户） | 2026-11-11 |
| D2 | DAppSCAN 为主要评估语料；SOChecker、Trace 与破坏-修复基准为辅；MANDO 846 为与 6c 对照的回归基线；语料只用于测试与评估，不决定覆盖范围 | 已定（用户） | 2026-11-12 |
| D3 | 成功判据：solc 退出码 0、Slither 构造成功、所有声明函数/修饰器与顶层函数的节点有属于编译单元的文件名与起始偏移、Slither 合约集合与 solc AST 合约定义相同 | 已定（证据；CP0.1 A 本机 846/846 验证通过） | 2026-11-12 |
| D4 | 保留 key5 与原序号、不去重；项目图以项目内相对文件名作为 key5 外层身份，单文件与 6c 不变；source length 只记录 | 已定；项目文件身份扩展已获用户批准，见 cp3_continue_v1/project_identity_authorization.json | 2026-11-17 |
| D5 | 版本策略细节（区间内升序；已知版本为可选输入；无 pragma 时按有文档出处的版本特征推断区间；pragma 覆盖只在区间内无可用编译器时、下界小版本系列内） | 已定（用户）；CP1 已通过独立审查；CP1.1 仅修正路径与运行健壮性，选版策略不变 | 2026-11-14 |
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
| D20 | 6c 重放判据：Slither 0.8.0 的局部写集合不确定，逐条相同不可达。改为对主运行不同的文件另取 10 个同进程样本，稳定事实（11 个样本重数相同）必须与 6c 报告相同，不稳定事实的 6c 重数必须落在样本范围内；不满足即停 | 已定（用户，2026-11-14；原话“同意 D20”） | 2026-11-14 |
| D20a | D20 补充：11 个样本判定后仍不满足的键，在新进程中对该文件追加最多 100 次同进程抽取；观察到 6c 报告的重数即判为不稳定并通过，100 次仍未观察到则停下。D20 的其他部分与键不变 | 已定（用户，2026-11-14；原话“同意 D20a”） | 2026-11-14 |
| D21 | 项目闭包中两个或更多同名合约定义（contract、interface、library）时，项目图一律不可用，归为工具限制；原变量绑定检查保留。依据：生产 Slither 对类型转换调用同样按名称错绑，而变量绑定检查覆盖不到 | 已定（用户，2026-11-21 原话“同意 D21”） | 2026-11-21 |

当前获取授权（2026-11-17，用户已定）：CP3 十份官方文档与三套固定提交指定目录已获批准，原话“批准全部资料，仅本地研究使用（推荐）”；仅本地研究与只读编译分类、费用上限 0 美元。精确来源、版本、路径与排除项见 artifacts/cp3_v1/authorization.json。既有 D1–D20a 状态和内容不变。

CP3 内容核验停止（2026-11-17）：SOChecker 的 ours+GPT.json 为846条严格子集，其他三份897条全同；建议仍用原定 ours.json 897条，接受附属子集差异后继续，尚待确认。下载授权本身仍有效，未更改 D1–D20a；见 cp3_v1/structure_review_request.json。

CP3 来源差异已获批准（2026-11-17）：用户“同意，继续使用原定 897 条（推荐）”。SOChecker分类仍只用ours.json的897条，ours+GPT的846条严格子集仅记录来源，不合并、不去重。前述待确认项现已解决；原资料授权和D3/D5/D7保持，续做批次cp3_continue_v1。

CP3 项目图绑定检查已获批准（2026-11-17）：用户原话“批准项目图绑定检查（推荐）”，授权与原请求SHA在 artifacts/cp3_binding_v1/authorization.json。项目图增加独立于D3的直接合约类型绑定检查，对照保存的solc AST与Slither原生变量类型；错绑或无法验证时拒绝该次图/成功状态并记工具限制。原D3测量、单文件、6c、合法源码与安装包保持；原批次封存，受影响项目在新批次重新验证。此前待确认项现已解决。


CP3 绝对允许路径与103项重验已获批准并完成实验验收（2026-11-18，修改 AI：Codex）：用户原话“批准参数修正、探针与103项重验（推荐）”，授权在cp3_paths_v1/authorization.json。生产仅project.py统一两类工具的允许目录为项目根绝对路径；12项探针通过，103项各执行一次，89成功/14未修复，原79成功全保持并恢复更早候选。最终21,160成功/9,911剩余，其他30,968条来源保持；生产/mando/DFG回归均通过。此前参数及范围待确认项已解决，无新的执行审批待办，D3/绑定/选版政策不变。最终文档与保护收据见本批次，交付后交独立审查。

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


### CP1.1 执行与边界（2026-11-14，修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | CP1.1 | 用户明确要求执行 r2.7 §4.3b；原登记的路径缺陷及超时/无 Git 两项健壮性现已修复并验收，待独立审查；未改变版本策略 | 对话；CP1_REPORT 的 CP1.1；CHANGE_LOG §17 | Codex |
| 2026-11-14 | D5 当前状态 | 同步上一节已有的 CP1 审查通过结论；当前表原“待审查”仅为状态滞后，历史不改；D16/D18/D19 保持 | CHANGE_LOG §16/17；module_acceptance.json | Codex |


### CP1.1 审查与 r2.8（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | 缺陷 | `command()` 路径缺陷已修复并经独立复核；仓库根下 argv 1,347/1,347 不变 | CHANGE_LOG §18.3；argv_equality.jsonl、cwd_equivalence.json | Claude |
| 2026-11-14 | 存储 | CP2 存储格式补充：CFG 边种类、调用按确切类型分类（LibraryCall 先于 HighLevelCall）、其他 Call 子类不丢弃 | CHANGE_LOG §18.2 | Claude |


### CP2 既有下限差异的归因授权（2026-11-14，修改 AI：Codex）

用户回复“允许单列既有下限差异，记录后继续”。只在 CP2 与 6c 的选定版本比较中，单列 SHA256 5ec2ee307684c021492194d5e63593834e164bcf878d1cddb48a0b1e1ad13237 已有的 0.4.11 → 0.4.12 下限差异；CP2 与 cp0_v2 的三类归因、D3 与 239/239 occurrence 精确重放标准不变。没有修改 PROMPTS 原文、版本策略或下限。证据与授权分别在 cp2_development_v1/attribution_review_request.json、attribution_existing_production.json、attribution_authorization.json；该请求的编译器计数字段名称另由 compiler_count_clarification.json 澄清为 96 个可信安装、92 个支持版本、4 个历史对照。正式运行在获得本授权之后开始。


### CP2 实测停止与既有决定保持（2026-11-14，修改 AI：Codex）

两次 production 各 843 成功 / 3 预期未修复，843 图字节相同、842 同版生产归档相同；但 regression_6c 第 87 个 buggy_43.sol 的原始 occurrence 多重集合不一致（86 同 / 1 差），已停止。剩余 152 与降序未运行，CP2 未通过，CP3 前提未满足。下一步仅建议独立审查，新探针、重放或方案改变先提出具体范围并咨询用户。证据 CP2_REPORT、CHANGE_LOG §19、cp2_6c_v1、replay_discrepancy_analysis.json。

没有新增或放宽 D3/D5/D16/D18/D19；当前表仅把滞留的 r2.7 标题同步为实际 r2.8。上面的批准只改单项版本归因，不能据此改变 239/239 或下限。本轮无安装、下载、LLM 或全局 solc 变更；旧决策历史字节保留。


### CP2 审查与 r2.9（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | 存储 | 空体 if 的边种类缺陷（86 个节点）；CP2.1 修复：条件节点按 son_true、son_false 各输出一条边 | CHANGE_LOG §20.3；if_edge_kinds.json | Claude |
| 2026-11-14 | D20 | 新增（建议，待批准）：6c 重放改为稳定事实判据 | CHANGE_LOG §20.2；legacy_repeat_in_process.jsonl | Claude |


### CP2.1 D20 授权（2026-11-14，修改 AI：Codex）

用户明确批准 D20，原话“同意 D20”；授权原文、日期与执行边界保存于 artifacts/cp2_1_v1/authorization.json。239 文件主运行保持 CP2 顺序；每个主运行差异文件只另启一个新进程，在该进程连续提取 10 次，与主运行合计 11 次判定稳定事实及不稳定重数区间。沿用原 occurrence 键、原始路径、版本与仓库根工作目录，任何不满足项即停，不追加采样。D3 与其他既有决定不变。审查证据仅证明旧版运行存在事实波动，没有定位其内部根因。


### CP2.1 实测停止，D20 判据保持（2026-11-14，修改 AI：Codex）

graph_facts 空体条件边修复通过两轮 production 验收：各 843/3，843 图字节一致，仅指定 86 条边变化。D20 主运行在第 227 份 reentrancy/buggy_44.sol 停止：223 精确同、3 个差异文件满足固定 11 样本判据、1 个 reference_only 键失败。该键为非继承 MultiHashWrapper 上下文的第 282 行 out DEF，6c 重数 1、11 次全 0。没有改变键、顺序、设置或样本数；剩余 12 份及降序未运行，CP2.1/CP3 前提未满足。

观察到的 9 个波动键全部为 L1 DEF，5 个继承、4 个非继承；只读复算确认原判定，无新增提取。D20 当前表保留“已定（用户）”，它是已授权的判据，并非验收通过状态。建议下一步仅先审查已封存差异，任何新增实验或方案调整仍需确认；本轮没有实施替代方案。证据：CP2_REPORT 的 CP2.1、CHANGE_LOG §21、cp2_1_v1/captured_replay_audit.json、cp2_6c_v2/store.tar.gz。


### CP2.1 审查与 r2.10（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-14 | 存储 | 条件边修复经独立复核成立（只差 86 条 true → false） | CHANGE_LOG §22.3 | Claude |
| 2026-11-14 | D20a | 新增（建议，待批准）：对 D20 不满足的键追加最多 100 次采样 | CHANGE_LOG §22.2；legacy_buggy44_repeat40.jsonl | Claude |


### CP2.2 D20a 授权（2026-11-14，修改 AI：Codex）

用户明确批准 D20a，原话“同意 D20a”；授权内容、日期、来源与费用上限 0 保存于 artifacts/cp2_2_v1/authorization.json。D20 的固定 11 样本结论和 occurrence 键不变；仅对仍不满足的键在新进程最多追加 100 次同进程抽取，每个键观察到参考重数后提前停止。先处理旧第 227 份，前 226 份沿用封存结果；通过后新进程续跑 228–239，再执行生产降序比较。稳定事实仍须相同，任何未满足停止条件不放宽；生产代码、旧产物和环境均不修改。


### CP2.2 D20a 执行与验收（2026-11-14，修改 AI：Codex）

D20a 已按用户授权执行：第 227 份另起进程，第 1 次观察到 MultiHashWrapper 声明上下文 out DEF 的参考重数 1 即停止。旧 D20 的 11 次判定保留；前 226 份不重跑。续跑 228–239 后，合计 234 精确、4 D20、1 D20a，239/239 通过；只读复算确认。降序 843 成功/3 预期失败，843/843 key5 与有序 IR 同，生产代码不改。

证据见 CP2_REPORT 的 CP2.2、CHANGE_LOG §23、cp2_2_v1/captured_replay_audit.json 与 cp2_6c_v3。D20a 当前已定，其他决定保持，无新增判据或类别豁免。有限样本的通过不能证明全局确定性或根因；本机验收完成，仍待独立审查才能进入 CP3。


### CP2.2 审查与 r2.11（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-17 | D20/D20a | 6c 回归按两项判据完成（239/239），不再重放；判据不变 | CHANGE_LOG §24.3；cp2_2_review_v1 | Claude |
| 2026-11-17 | 第 3 节第 1 条 | 版本区间只复用冻结的表达式语义；定位不依赖整文件解析、不要求 UTF-8（缺陷修复，不是策略改变） | CHANGE_LOG §24.2；probe_inputs.json | Claude |


### CP2.3 实现与回归验收（2026-11-17，修改 AI：Codex）

用户明确要求执行 PROMPTS r2.11 CP2.3。本轮仅改 pragma 定位与字节处理，不改变冻结约束求值语义或 D5；两环境各 846 输入及 28 个可解析夹具等价，9 个 CLI 正例通过。新 v5 对 v3 的状态/版本/设置/标志各 846/846 同，843 图字节同；D3/key5/settings_retry/known-version 保持。D20/D20a 的 6c 回归已经结束，本轮重放 0 次。

无新增方案决定或判据调整，当前决策表不改。并集 pragma 和 Slither 超时仍按 CP3 已定范围留待分类，未提前实现；没有安装或下载。证据 CP2_REPORT 的 CP2.3、CHANGE_LOG §25、artifacts/cp2_3_v1；本机验收通过，独立审查尚未进行。


### CP2.3 审查与 r2.12（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-17 | 第 3 节第 1 条 | 版本表达式改从遮盖注释后的字节读取；未结束的 pragma 单独记录。只在冻结实现抛异常的输入上偏离冻结语义（有意：冻结实现拒绝 solc 接受的输入） | CHANGE_LOG §26.2；cp2_3_review_v1/edge_cases | Claude |


### CP2.4 执行：冻结拒绝行为的有意偏离（2026-11-17，修改 AI：Codex）

用户明确要求执行更新后的 CP2.4；按 PROMPTS r2.12 §4.4e 和上方审查历史实施。pragma 的约束表达式从 code_only 等长遮盖字节读取，因此旧冻结实现拒绝、而 solc 接受的块/行注释输入现在通过；已识别指令在分号前遇花括号或 EOF 仍被拒绝，error_first_line 改为 F: unterminated pragma directive。标志仍为 unsupported_version_constraints，union/无法解析/空交集的原消息不变，pragma_patches 原始区间和字节保持。

此为已要求的有意偏离，不是新的策略决定：两个环境各 846 MANDO 与 35 个 CP2.3 可读取夹具，区间、完整补丁、EnvironmentPlan 八字段在升降序下全部相同。两个注释 CLI 成功且无源码改动；缺分号和 union 在编译前分别记录预期错误。证据：cp2_4_v1/equivalence.json、cli_acceptance.json；CP2_REPORT 的 CP2.4、CHANGE_LOG §27。生产仅 environment.py 两函数修改，其他决定表与历史保持，未提出额外替代方案；本机验收完成，等待独立审查，CP3 未开始。


### CP2.4 审查与 r2.13（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-17 | 3.2 节第 2 步 | 多文件单元的编译调用改为命令行 combined-json 路径（与单文件相同，参数同时传给 solc 与 crytic-compile），不用 standard JSON；方案修正，不改变已定决策 | CHANGE_LOG §28.2；cp2_2_review_v1/probe_diagnostics.json | Claude |


### CP3 资料获取授权（修改 AI：Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-17 | CP3 获取范围 | 用户“批准全部资料，仅本地研究使用（推荐）”；批准十份官方文档及 DAppSCAN/SOChecker/Trace 的固定提交指定目录，费用上限 0 美元，不扩大软件安装或 LLM 权限 | artifacts/cp3_v1/authorization.json；请求 SHA256 1862b4aa6deafca0267ef168b4b358738f4d1635fcc983fc5bc2925a09433808 | Codex |


### CP3 内容核验差异（2026-11-17，修改 AI：Codex）

获批请求要求内容计数不符时保留并停止；实测 ours+GPT.json 的846条严格包含于原定 ours.json 的897条，差51条，没有新增或重复 input。DAppSCAN、Trace、文件身份与哈希均通过。建议继续用原定897条唯一输入并将846条作为附属来源记录；该核验假设调整待用户确认，未改变修复判据或自动合并数据。证据 structure_acceptance.json、structure_review_request.json，记录 CHANGE_LOG §30。


### CP3 来源核验差异获批（2026-11-17，修改 AI：Codex）

用户原话“同意，继续使用原定 897 条（推荐）”，批准structure_review_request所述处理；授权先写cp3_continue_v1/authorization.json，绑定请求SHA256。旧897/846差异收据保留为真实历史，不改写为四份全同；继续以897条主输入实施CP3，不新增下载或安装，费用上限0。

### CP3 项目图文件身份扩展（2026-11-17，用户已批准）

- 用户原话：“批准项目图使用文件名 + key5（推荐）”。来源：本轮异步回复；证据与完整范围：artifacts/cp3_continue_v1/project_identity_authorization.json。
- 仅项目图使用（项目内相对文件名、原 key5）作为身份；节点、CFG 边与调用均保留文件上下文。原 key5/序号算法、单文件与 6c 输出不变，不去重；同一文件内残余冲突停止报告。D3 不变。

### CP3 项目类型绑定缺口（2026-11-17，修改 AI：Codex；待确认）

- 原生 Slither 在两个不同文件的同名 C 类型上把参数 b 错绑为 A.sol，solc AST 明确指向 B.sol；现有 D3(a/b) 均通过。证据：cp3_continue_v1/alias_call_probe.json。
- 项目文件身份扩展只解决序列化冲突，不能纠正上游类型对象。alias_binding_review_request.json 建议新增项目绑定一致性接受条件，尚未实施。全量受控中断，记录和原始字节保留，不自动重试。

### CP3 项目绑定检查授权（2026-11-17，修改 AI：Codex）

用户已批准 alias_binding_review_request 所列范围，原话“批准项目图绑定检查（推荐）”。先核对旧working_inventory的762个成员与evidence_seal，再将授权写入cp3_binding_v1；不回写原请求的历史pending状态。直接声明的合约类型通过AST引用ID确定目标，再比较原生对象文件/起始位置。检查是项目图附加接受条件，保留原D3(a/b)，不声称覆盖全部Slither语义。只改slither.py及对应pipeline/report处理；不修安装包，不改合法语料，不添加重写规则。

受影响旧项目343条在新批次重验，529条单文件核对身份与实现后复用；第873条原中断SOChecker记录在新批次重新开始，其旧9次编译保留。余下30,199条继续原完整序列，没有抽样、时限扩展或新增下载。


2026-11-18（修改 AI：Codex）：新增CP3连字符入口参数组装问题的待确认请求；11单元、315次调用、0美元、无安装/下载/LLM，等待用户决定，不自动修正或重验。


### CP3 连字符入口授权与探针启动请求（2026-11-18，修改 AI：Codex）

用户“批准限定修正与 11 个单元重验（推荐）”已登记为已定授权，绑定原请求SHA256 720b82ed018f97f1fe321585a218a23c362426408e0b18008b1d1336ea4c4bdf。生产仅project.py增加共同./前缀，测试和手写夹具按原范围；候选、设置、D3、绑定和源码不改。初次探针因Codex运行脚本未创建父目录在pytest初始化时停止，没有实际编译；按无自动重试约束提出一次修正脚本后的续跑请求。11个单元的重验批准保持，但须等待四版本和普通入口八项检查通过。


### CP3 一次探针续跑批准与允许路径问题（2026-11-18，修改 AI：Codex）

用户“允许修正脚本并续跑一次（推荐）”已写新批次authorization，绑定原请求SHA；没有重新请求原11项的批准。一次执行4passed/1failed后即停，余下三版本/语料未运行；执行前收据只修正pytest current别名重复收集，原八项与失败夹具保持。该证据收集差异与原版/执行版SHA已记录，不伪称执行文件与原准备版本字节全同。

新问题是--allow-paths .在旧版拒绝工作根内现存文件，原31,071结果中92项/521次调用受影响，其中79项后来成功、13项失败；与原11项并集103项。建议仅project.py把两类工具的允许目录同步为项目根绝对路径，保留原探针并补普通嵌套入口四版本验证，通过后再新批次重验103项。此项尚待确认，未应用补丁或扩大运行，见allowed_paths_review_request.json；成功判据不放宽。


### CP3 绝对项目根参数及103项授权落实（2026-11-18，修改 AI：Codex）

用户“批准参数修正、探针与103项重验（推荐）”已记录，原请求SHA绑定于cp3_paths_v1/authorization.json。应用批准的两处参数补丁，原八项探针/夹具保持，加四项普通嵌套入口检查后12项通过；103个不同ID每个一次。首项候选误报来自内存tuple与JSON list比较，保存字段完全一致，恢复已封存成功结果并仅续跑102个未执行ID；没有重试原实验或改候选门槛。历史中断段按原封存保全清单核对，不伪造正常完成seal。

原79成功保持并全部恢复更早版本，另10项新增成功；剩余14项保留真实源码或Slither工具限制。最终31,071有效观察为21,160成功/9,911剩余，236非Solidity单列，其他30,968条原来源不改。D6的29类、125条breaking changes及零频类别保持，频率只排顺序；无额外方案变更或待批准执行事项。并集pragma、Slither超时和后续修复规则仍留后续CP，不在本轮自行实施。


### CP3 审查与 r2.14（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-21 | D21 | 新增（建议，待批准）：同名合约的项目图不可用 | CHANGE_LOG §36.3；cp3_review_v1/probe_alias_cast.json | Claude |
| 2026-11-21 | 第 3 节第 1 条 | pragma 求值扩展到 solc 接受的通配符与缺补丁号写法，以真实 solc 逐版本为判据；只在原实现拒绝的表达式上改变结果 | CHANGE_LOG §36.2；probe_pragma_forms.json | Claude |
| 2026-11-21 | CP3 统计口径 | 类别频率增加“主因”口径（D6 实现顺序按主因），原“任一候选”口径保留 | CHANGE_LOG §36.2；probe_mando_versions.json | Claude |


### CP3.1 项目同名合约门槛（2026-11-21，修改 AI：Codex）

用户回复“同意 D21”。项目的 AST 闭包包含重名定义时，保留 D3 与直接变量绑定事实，将图标为不可用并登记工具限制。请求与授权见 artifacts/cp3_1_v1/d21_request.json 和 authorization.json。

2026-11-21，修改 AI：Codex。用户原话“同意按实测语法拒绝单列并继续”。在 §4.5b 第 4 节的矩阵中，返回码 0 是接受，语法拒绝与版本拒绝分别计数。证据为 pragma_authorization.json 及 matrix_invocations.jsonl.gz。全部 7,544 对中有 360 次语法拒绝，82 种写法的接受集合均能表示为一个区间或空集。

用户原话“同意单列 AST 不足”。D21 仍只按 AST 定义判定。跨项目复用同源文件的定义计数时核对原始内容 SHA。补取 AST 后仍缺证据的 6,160 项单列未知，已确认 12 项是全体的已证实下限。原先成功的项目均可判定且未发现重名。授权与覆盖边界见 ast_coverage_authorization.json、ast_census.json。D19 等其他决策状态沿用。
