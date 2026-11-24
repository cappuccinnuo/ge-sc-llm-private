# CompileRepair 决策记录

决策的完整内容在 `../PROMPTS.md` 第 2 节；本文件记录每个决策的当前状态与变化历史，避免不同修订号之间编号含义混淆。第 1 节在状态变化时更新；第 2、3 节只追加。

状态：已定（用户）＝用户明确决定；已定（证据）＝由证据确定，用户未反对；建议＝待用户确认；待定＝尚未讨论到；撤销。

## 1. 当前决策（PROMPTS r2.27）

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
| D22 | 依赖版本按 T1 锁定、T2 范围、T3 推断三级处理。T3 须通过路径、传递导入、pragma、符号、编译与 D3 检查，记录 inferred。 | 已定（用户） | 2026-11-23 |
| D23 | npm 发布包按带版本、大小、来源与完整性校验的清单授权；元数据查询单独获准。 | 已定（用户，限本清单） | 2026-11-23 |
| D24 | 仅将 standard JSON 包装内显式给出的 optimizer 设置传给 solc 与 Slither，runs 接受无符号 32 位十进制。 | 已定（用户转交 CP5.1） | 2026-11-23 |
| CP4 节点恢复 | 分开统计破坏时受影响节点和修复后丢失节点，按边界、字节和图事实核验恢复 | 已定（用户） | 2026-11-22 |
| CP4 分析器类别 | slither_incomplete 只用可校验历史失败及无害缺节点负例，独立报告覆盖 | 已定（用户） | 2026-11-22 |
| CP4 迁移验收 | 测试要求恰好 17 个生产文件且包含 benchmark.py，保留逐文件校验，新目录续跑生产套件 | 已定（用户） | 2026-11-22 |
| CP4 精确还原路径 | 原工作文件与实际逆向还原字节相同才可在原源路径只读编译。单项图字节与评分通过后，仅续跑未通过或未测项 | 已定（用户，本批） | 2026-11-22 |
| CP4.1 支持版本 | 96 个安装中筛选冻结的 92 个支持版本，另 4 个为历史对照 | 已定（用户） | 2026-11-22 |
| CP4.1 内部异常 | 仅有通用 std::exception 的 1 个模板使用封存诊断和文本夹具 | 已定（用户） | 2026-11-22 |
| CP4.1 原候选重判 | 对 17,432 项先核对种子、编辑、文件及收据 SHA，再根据原始实际观测重判 | 已定（用户） | 2026-11-22 |
| CP4.1 结构体数组 | 同一审查夹具交叉比较 ABI 与生产字节码，以 92 版实测拒绝集合和非 via-IR 设置筛选 | 已定（用户） | 2026-11-22 |
| CP4.1 真实包补样 | 保留 28 项，追加包内入口的 86 个已核实依赖闭包，合并抽样使用原种子及上限 | 已定（用户） | 2026-11-22 |
| CP4.1 迁移生成名称 | 保留原分，核验 TMP、REF、TUPLE 的全图对应。Yul 源文件编号另核对两份原始 solc 输出、AST 和源文件清单 | 已定 | 2026-11-22 |
| CP4.2 保留节点生成名称 | 普通修复检查对齐节点，原文件迁移同时交付逐字原分、全图结果和 kept 核验 | 已定（用户） | 2026-11-22 |
| CP4.2 移动函数 | 相邻 NatSpec 随完整声明移动。嵌入创建字节码摘要变化、Yul 名称随已核验的源码起点移动时，分别单列并保留实测分。 | 已定（用户） | 2026-11-22 |
| CP4.3 主指标与 Yul 起点 | 修复删除的完好节点留在主分母。存活诊断单列。Yul 的源码起点由组合偏移映射核验，源编号变化另需 AST。 | 已定（用户转交 CP4.3，见 §48.4） | 2026-11-22 |
| CP4.4 普通评分 | 名称冲突、缺定义及 Yul 核验失败按节点排除，源码碰撞整项保留原分。三处注释长度变化单列；仅接受 cp3_00291 已证明的历史指标差值。 | 已定（用户） | 2026-11-23 |
| CP4.5 普通评分 | 每个生成名称以唯一定义为锚。仅在获批条件成立时将显式 REF 写回、已绑定数组初始化、删除算作使用；源码碰撞整项用原分。 | 已定（用户） | 2026-11-23 |

**CP3.2 输入语言与统计口径（用户已定，2026-11-22）**　显式其他语言 JSON 或 Vyper 正证据在输入阶段排除。缺少语言证据的输入标记未定并继续原流水线。沿用 236 项旧排除供对照，新口径中没有历史编译结果的放行项单列未测。授权和反例见 artifacts/cp3_2_v1/authorization.json、decision_request.json。

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


### CP3.1 审查与 r2.15（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | 输入语言 | CP3 已批准的 SOChecker 词法证据规则移到生产输入阶段，统一用于所有语料；JSON 包装的 language 不是 Solidity 时同样判为非 Solidity；规则本身不变 | CHANGE_LOG §38.2；cp3_1_review_v1/trace_parser_units.json | Claude |


### CP3.2 输入语言与统计口径（修改 AI：Codex）

| 日期 | 决定 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | 用户原话“批准三态判定及新旧统计口径” | §4.5c 的硬验收改为所有原成功项均获准放行。原词法函数保留，确证其他语言才排除，语言未定进入原流水线。236 项旧排除单列供对照，缺历史测量的放行项不进入成功或失败分母。本次无语料补编译 | cp3_2_v1/input_gate.json、decision_request.json、authorization.json，CHANGE_LOG §39 | Codex |


### CP3.2 审查与 r2.16（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | CP4 基准 | 基础单元排除 0 节点图与 unknown 语言；项目分组 dev/test = 20%/80%（按组 ID 的哈希）；每个算子每个语料最多 200 个样本；纳入以环境步骤后的主因为准，环境步骤已成功的样本单列 | PROMPTS §4.6a；CHANGE_LOG §40.2 | Claude |


### CP4 评分、历史回放和两个实际停止现场（修改 AI：Codex）

| 日期 | 用户原话 | 影响及依据 | 记录者 |
|---|---|---|---|
| 2026-11-22 | 同意分别统计并验证恢复 | 两段编辑按边界、真实字节和图事实核验，保留破坏影响及最终丢失。cp4_v1/authorization.json | Codex |
| 2026-11-22 | 同意单列历史回放 | 22 个源码或输入算子，分析器类别验证历史收据和缺节点负例。cp4_v1/authorization.json | Codex |
| 2026-11-22 | 同意更新断言并续跑测试 | 迁移测试按 17 文件并包含 benchmark.py 检查，原失败与新日志分开。relocation_test_authorization.json | Codex |
| 2026-11-22 | 同意先做同路径复核，通过后续跑 | 通过同路径的严格图字节与评分探针后重验失败的一项，并执行 7,542 个未测项。其余 4,315 个原通过样本和 200 个对照原样沿用。restoration_identity_authorization.json 和 identity_continuation/probe.json | Codex |


### CP4 审查与 r2.17（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | 分类表 | 新增 abi_coder_required、file_level_member、version_mismatch（后者只作版本噪声）；other 模板逐个按 standard JSON 类型与文档归类 | CHANGE_LOG §42.2；cp4_review_v1/probe_operator_messages.json | Claude |
| 2026-11-22 | CP4 评分 | 比较 IR 时去掉嵌入字节码末尾的 solc 元数据 CBOR；graph.json 不改；评分增加文件改名映射 | CHANGE_LOG §42.2 | Claude |

### CP4.1 清点与实测范围（2026-11-22，修改 AI：Codex）

| 用户原话 | 处置 | 依据 |
|---|---|---|
| 同意按冻结的 92 版继续 | 将安装总数 96 与支持数 92 分别核对 | cp4_1_v1/preflight_authorization.json |
| 同意单列内部异常的历史证据 | 仅对 1 个通用内部异常模板使用历史文本证据，其余 95 个使用源码夹具 | cp4_1_v1/authorization.json |
| 同意旧样本按原始观测重判 | 对旧样本使用原始诊断和已有调用结果，新增样本与还原仍需实测 | cp4_1_v1/authorization.json |

### CP4.1 生产输出边界、真实依赖抽样与迁移差异（2026-11-22，修改 AI：Codex）

| 用户原话或状态 | 处理与依据 |
|---|---|
| 同意交叉核对及条件口径 | 同一 0.8.38 二进制在仅请求 ABI 时成功，在生产字节码设置下失败。92 个支持版本都拒绝结构体数组算子，按实测集合与现有设置限制抽样。见 struct_codegen_authorization.json、struct_codegen_crosscheck.json。 |
| 同意补齐 86 项并保留原收据 | 保留入口并移除可单独迁移的相对依赖，使用原种子重建完整 114 项清单，核对旧 28 个样本签名。见 package_sampling_authorization.json、supplement_sampling.json。 |
| 迁移评分待确认 | 两份真实项目图仅出现 Slither 自动计数器换号。原分已保存，所提核验同时约束全图对应、命名冲突与其他图事实。见 migration_counter_review.json。 |


### CP4.1 迁移评分及续跑决定（2026-11-22，修改 AI 为 Codex）

| 用户原话 | 已定范围 | 授权位置（artifacts/cp4_1_v1/migration_continuation 下） |
|---|---|---|
| 批准严格的一一对应核验并续跑 | 文件迁移时保留原分，TMP、REF 必须在整图中同族、双向唯一、存在定义，声明、类型、操作、CFG 与调用完整匹配并排除源码和字面量碰撞。 | authorization.json |
| 批准纳入 TUPLE_N 并续跑 | 对元组采用同一判据，逐项核对定义、解包顺序与索引。 | tuple_continuation/authorization.json |
| 批准限定核验和最多 4 次 solc 调用，继续 | 仅对批准的两个候选验证 YulSwitch 源文件编号。旧 stdout、AST、闭包、字节及两份源文件清单均须吻合。实用 2 次，接收 1 项。 | yul_continuation/authorization.json |
| 允许修正空格识别并续跑 | 按实际空格识别 NewArray 的临时变量定义，两侧指令的字符比较仍逐字执行。保留 51 项、复用停点的两张图，执行其余 62 对。 | definition_continuation/authorization.json |


### CP4.1 审查与 r2.18（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | 评分中的生成名称 | 用户已批准的迁移核验规则推广到所有评分，只作用于 kept 节点；不满足即整体用原样分数；raw 分数并列保留（Claude 建议，CP4.2 实施） | CHANGE_LOG §46.2；cp4_1_review_v1/probe_counter_shift.json | Claude |
| 2026-11-22 | declaration_error | 0 个基准样本，接受为已知限制，D6 中注明 | CHANGE_LOG §46.4 | Claude |


### CP4.2 保留节点评分及函数移动范围（修改 AI 为 Codex，2026-11-22）

| 用户原话 | 已定范围 | 证据（artifacts/cp4_2_v1 下） |
|---|---|---|
| 保留迁移全图结果，另列 kept 核验 | 普通修复从有位置对应的保留节点推导同族双射。文件迁移继续保存逐字原分和 CP4.1 全图结论，额外报告 kept 核验。61 份迁移记录的逐字 lost 与全图 lost 不同。 | migration_review.json、authorization.json |
| 同意连同注释移动并限定续跑 | 选定的 200 个单元和函数固定。45 项随函数移动前置 NatSpec，46 项沿用已通过的收据，154 项在新目录测量。 | natspec_request.json、natspec_authorization.json |
| 同意单列实质差异，继续 124 项 | 能逐字节证实嵌入创建字节码差异且其余图事实一致的样本按实测分单列，保留在原 200 项分母。 | creation_literal_request.json、literal_authorization.json、observed_creation_hashes.json |
| 同意保留 Yul 原分并继续剩余 121 项 | 复用前 79 项收据。Yul 名称内的起点如能按源码字节与编辑映射验证且其余事实完全吻合，可列明原因，正式分仍用原值。 | observed_yul_positions.json、yul_authorization.json |


### CP4.2 审查与 r2.19（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-22 | kept 分母 | 恢复 CP4 定义：修复删除的未破坏节点留在 kept 分母；新增 removed_by_repair 与诊断块 surviving；lost 只表示破坏区（取代 r2.18 §4.6c“计为 lost”的措辞） | CHANGE_LOG §48.2；cp4_2_review_v1/probe_repair_deletes_kept.json | Claude |
| 2026-11-22 | Yul switch 起点 | 按组合偏移映射对齐（Claude 建议；改变 CP4.2 中“单列原分”的处理，由用户转交 CP4.3 时确认） | CHANGE_LOG §48.4 | Claude |


### CP4.3 执行 r2.19 的评分决定（修改 AI 为 Codex）

| 日期 | 决定与范围 | 依据 |
|---|---|---|
| 2026-11-22 | 用户指示实施 CP4.3，依 §48.4 确认用源码映射核验 Yul 起点。CP4.2 的原分与封存证据沿用。 | artifacts/cp4_3_v1/authorization.json、PROMPTS r2.19 §4.6d |
| 2026-11-23 | 维持对创建字节码哈希常量的既有处置，CP5 报告应单列实际差异。 | CP4_REPORT 的 CP4.3 及本批 acceptance.json |


### CP4.3 审查与 r2.20（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | 生成名称对应 | 普通评分由“一处不符即整体用原分”改为“结构不同、冲突或无法核验的节点移出推导并按原样比较”；新增状态 partial；迁移全图核验不变（Claude 建议，用户转交 CP4.4 即确认） | CHANGE_LOG §50.2；cp4_3_review_v1/probe_partial_change.json | Claude |


### CP4.4 转交与两项验收决定（修改 AI 为 Codex）

| 日期 | 用户决定 | 影响与证据 |
|---|---|---|
| 2026-11-23 | 转交并实施 CP4.4 | 按 §50.4 确认普通评分按节点排除与 partial 状态。文件迁移保留全图验收。见 artifacts/cp4_4_v1/authorization.json。 |
| 2026-11-23 | 保留主指标，另列长度变化节点 | Yul 注释场景 B 有三个节点长度各增 20 字节，13 项参加推导，16 项按主指标相等。 |
| 2026-11-23 | 接受这一个差值，继续验收 | 移动 cp3_00291 的两个创建码差异保留；核验额外一个表达式和调用。其余历史单元的指标逐项一致。见 artifacts/cp4_4_v1/acceptance_authorization.json。 |


### CP4.4 审查与 r2.21（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | 生成名称对应 | 普通评分改为以定义为锚：名称映射由真值中唯一的定义处决定，使用处须一致；不一致的节点计为不相等，取消原样比较兜底；参与推导只比较节点类型与 IR（Claude 建议，用户转交 CP4.5 即确认） | CHANGE_LOG §52.2；cp4_4_review_v1/probe_stale_name.json | Claude |


### CP4.5 转交与两次 REF 写入决定（修改 AI 为 Codex）

| 日期 | 用户决定 | 依据与实施 |
|---|---|---|
| 2026-11-23 | 转交 CP4.5，按唯一定义检查每次使用 | r2.21 §4.6f、CHANGE_LOG §52.4。源码碰撞沿用整项原分，迁移沿用全图核验。 |
| 2026-11-23 | 同意区分引用定义和显式写回（推荐） | 中性夹具有三处显式 `(->目标)` 写回；作为使用后逐处核验。见 cp4_5_v1/definition_request.json 和 authorization.json。 |
| 2026-11-23 | 批准限定识别和新批次重验（推荐） | 同一节点内可核实绑定的引用数组初始化及删除计为使用。补正负例，保留首轮差异记录，按原门槛完成三组全量比对。见 cp4_5_v1/write_semantics_request.json 和 continuation/authorization.json。 |


### CP4.5 审查与 r2.22（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | D22 依赖版本身份 | 新增：确定性方法可读项目清单文件；身份分 T1 锁文件、T2 清单范围、T3 无清单；T3 在兼容检查通过时由第 3 步补全并标记 inferred（建议，CP5 第 1 节后请用户确认） | PROMPTS §2、§4.6g；CHANGE_LOG §54.2 | Claude |
| 2026-11-23 | D23 库发布版下载 | 新增：按 CP5 第 1 节的测量列出下载清单，只下载 npm 发布包并双重核对（待用户授权） | PROMPTS §2、§4.6g | Claude |

### CP5 第 0–1 节测量与授权（修改 AI 为 Codex）

| 日期 | 决定 | 依据及范围 |
|---|---|---|
| 2026-11-23 | 同意 D22 三级规则（推荐） | 缺包单元中 T1 全覆盖 73 个，至少含一个 T3 的有 8,396 个。包别名按声明文件的作用域取证。见 cp5_v1/d22_request.json。 |
| 2026-11-23 | 批准限定的元数据查询（推荐） | 仅限官方 npm 注册表、已列出的 141 个候选名及最多 500 次发布包 HEAD，响应正文总限 128 MiB。发布包正文另列 D23 清单。见 cp5_v1/authorization.json。 |
| 2026-11-23 | 批准这 172 版及硬上限（推荐） | 20 个包的精确版本、来源、SHA512 与大小限额按 cp5_v1/d23_download_request.json，批准及清单 SHA256 见 d23/authorization.json。发布包置于仓库外，费用 0 美元。 |


### CP5 检查点审查与 r2.23（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | D24 包装的 optimizer | 新增：包装自带的 optimizer 映射为 --optimize 与 --optimize-runs，只用于包装自带设置（同意 Codex 的 optimizer_request；建议，转交 CP5.1 即确认） | CHANGE_LOG §56.2；cp5_v1/optimizer_request.json | Claude |
| 2026-11-23 | D23 续传 | 同意只下载清单中剩余 23 个精确 URL，沿用原上限（在 D23 授权范围内） | cp5_v1/d23/transport_stop.json | Claude |
| 2026-11-23 | 第 3 步候选上限 | 先在 dev 测量实际组合数，再按测量设上限并记录 truncated；不按错误位置提前停止 | CHANGE_LOG §56.2；cp5_review_v1/combination_bound.json | Claude |

### CP5.1 转交与 D24（2026-11-23，记录者 Codex）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | D24 与 D23 限定续传 | 用户转交 CP5.1，按 r2.23 §4.6h 第 0 节确认包装优化器白名单及 23 个指定 URL 的单次续传。费用上限 0 美元。 | artifacts/cp5_1_v1/authorization.json | Codex |

### CP5.1 最后五个发布版的传输记录（2026-11-23，记录者 Codex）

| 用户决定 | 执行范围和证据 |
|---|---|
| “批准仅续传这 5 版一次” | 原 23 项续传完成 18 项，TLS 在下一个版本握手时断开。复用 167 份已核验归档。剩余五项均为 `zeppelin-solidity`，版本为 1.6.0、1.8.0、1.9.0、1.11.0、1.12.0。见 `cp5_1_v1/last_five_authorization.json`。 |
| “允许已运行会话按上述保护执行一次” | 新 WSL 进程曾在脚本启动前超时，自动审批因重复请求风险拒绝了切换会话。用户确认使用已有会话、独占批次及 GET 前登记。执行时缺少 `CP5_HTTPS_PROXY`，留下 1.6.0 的登记，创建连接前退出。见 `launcher_authorization.json`、`guard_stop.json`。 |
| “批准按已核验配置执行一次” | 固定授权代理并在禁用网络套接字的条件下核对五个目标，新的批次绑定原登记与日志的 SHA256。五个官方 URL 各取得一次 HTTP 200。172 份重新双哈希核对，共 88,886,992 字节，费用 0 美元。见 `configured_five/authorization.json`、`configured_five/receipts.jsonl` 和 `download_summary.json`。 |

### CP5.1 的 D3 与 SlithIR 覆盖（2026-11-23，记录者 Codex）

用户决定“沿用 D3，单列 IR 缺失（推荐）”。本次 CP5.1 沿用冻结的 D3 和既定分母，按原计划选版、冻结 K 并评测。另列已证实的 SlithIR 缺失，记录依据、统计范围和局限。 开发单元 cp3_19463 的三个选版收据均通过 D3，Slither 却在 readOracle 的 IR 生成中报告原生异常。该函数的源码映射可以齐全而 IR 缺失。依据见 cp5_1_v1/partial_ir_review.json 与 partial_ir_decision.json。

### CP5.1 开发测量中断后的限定续作（2026-11-23，记录者 Codex）

用户决定“批准限定续跑，保留旧收据（推荐）”。6,940 份完整结果须先核验 SHA256。cp3_30233 的 oldest 在 31 次 solc 调用后中断，允许完整执行一次，其余 7 个未开始的组合各执行一次。两个批次分别计时，D3、开发选版与测试顺序沿用原定义。依据见 development_interrupt.json 与 development_continuation/authorization.json。

用户另行决定“允许仅重启 Ubuntu 并恢复（推荐）”。核验 6,940 份结果和 6,940 份步骤，复查四个空闲 Bash 后，仅重启 Ubuntu-22.04。两端代理返回预期出口，直连均被阻断，Ubuntu 两条链的默认策略均为 drop。用户服务的会话总线缺失，首次服务启动在任何实验前退出；随后通过已有 tmux 专属套接字以普通用户运行。依据见 development_continuation/recovery_summary.json 和 bootstrap_transport.json。

### CP5.1 冻结策略回归环境（2026-11-23，记录者 Codex）

用户决定“批准补环境并限定续跑（推荐）”。两套环境显式传入 CP0 冻结库的目录 TREE_SITTER_LIB_DIR。先各自解析同一个无害夹具，再在新批次各完整运行模块套件一次，随后运行原定阶段。旧测试日志、停点与 6,948 份开发收据全部保留。见 test_environment_resume_v2/environment_request.json 与 authorization.json。

### CP5.1 开发集冻结结果（记录者 Codex）

| 日期 | 决定 | 依据 |
|---|---|---|
| 2026-11-23 | 正式默认规则为 `oldest`，K=21。 | 仅用真实开发集及 8 个开发缺包样本。冻结记录见 `policy.json` 和 `policy_application.json`。 |


### CP5.1 审查与 r2.24（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-23 | 第 4 步链式改写 | 诊断确认后，允许新进入闭包文件的缺失相对导入在同一第 4 步内继续改写，至多 L 轮，链结束错误数不减少则整条回滚（Claude 建议） | CHANGE_LOG §58.2；PROMPTS §4.6i 第 3 节 | Claude |
| 2026-11-23 | 文件级破坏的 exact 邻域 | 引用被破坏文件的导入指令视为破坏邻域（Claude 建议） | PROMPTS §4.6i 第 4 节 | Claude |
| 2026-11-23 | D25 部分 IR | 新增待定：D3 是否排除 Slither 标记为不完整的图；先测量 | PROMPTS §2、§4.6i 第 6 节 | Claude |


### CP5.2 单文件身份核验与运行授权（2026-11-23 至 24 日美东时间，修改 AI 为 Codex）

| 日期 | 用户原话 | 执行范围与证据 |
|---|---|---|
| 11-23 | “允许仅重启 Ubuntu 并恢复” | 复核四个空闲终端后重启 Ubuntu-22.04，随后实测两侧代理、直连阻断和 WSL 防火墙。见本批 `wsl_restart_authorization.json` 和 `network_recovery.json`。 |
| 11-23 | “允许按原收据继续诊断” | 313 项中有 17 项指向最后接受的轮次。验证已登记位置、选中轮次和顶层结果的 SHA256 后完成逐项诊断。见 `diagnosis_path_request.json` 和 `diagnosis_path_authorization.json`。 |
| 11-23 | “批准限定转换并保留原分” | 包装评分先验证单一物理源文件、原字节哈希和唯一对应的文件名，再转换独立图与项目图的文件标识和 schema。节点、声明、CFG 边和调用均须对齐，逐项保存原分。见 `wrapper_representation_authorization.json` 和 `benchmark_scores.json`。 |
| 11-23 | “批准冻结源码后限定续跑” | 模块封存测试复制源码期间，评分函数被抽取，18 个副本全部符合各自封存值，工作树有一份更新。保留 36 项通过、1 项失败的首轮记录；冻结 18 个最终模块后在新目录运行。见 `production_suite_stop.json` 和 `frozen_suites/`。 |
| 11-24 | “批准 711 次限定编译并续跑” | 711 个 CP3 项目原命令的允许路径为点号。保留原命令与原工作目录，用当前生产参数逐项取得真实 solc 退出码后测量 IR；其余 2,660 项沿用已核验的编译收据。逐项授权绑定 `ir_argument_differences.jsonl` 的 SHA256。见 `ir_replay_request.json` 和 `continuation/authorization.json`。 |

D25 仍待用户根据分语料测量结果决定。部分 IR 标记写入生产运行收据。图文件的结构和 D3 的接受条件沿用既有定义。本节所列路径相对于 `compile_repair/artifacts/cp5_2_v1/`。

### CP5.2 的 D25 测量结果（2026-11-24，记录者 Codex）

各范围检出的单元为真实开发集 4/1131、基准成功样本 0/1240、MANDO 0/843、CP3 基础抽样 0/1000。cp3_19463 的两个合约被标记；完整结果及合约计数见 CP5_REPORT 的 CP5.2 部分。D25 继续保留待定状态。


### CP5.2 审查与 r2.25（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-24 | 工作方式 | 用户决定：从 CP6 起由 Claude 直接在 GitHub 编写代码与测试；一次一个阶段，阶段内分小步核实；下载由用户授权 Claude 自行进行 | 用户 2026-11-24 的要求；PROMPTS r2.25 修改说明第 2 条 | Claude |
| 2026-11-24 | 旧移动算子 | 链式修复的 exact 不再扩大邻域，基准以 v2 为准 | cp5_2_review_v1/README.md | Claude |
| 2026-11-24 | D25 | 审查建议加入 D3；待用户决定 | PROMPTS §2 | Claude |


### CP6.0（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-24 | D25 | 用户批准：D3 增加 (c)，Slither 部分 IR 的图不算成功，分类为 slither_incomplete / slither_partial_ir / tool_limitation | 用户 2026-11-24“按你建议的方式”；PROMPTS §2、§4.6j | Claude |
| 2026-11-24 | 工作方式 | 用户决定：Claude 写代码并核验，写本地运行步骤；用户拉取后由 Codex 本机运行；记录注明修改 AI 为 Claude；模块记录写在 compile_repair/docs，根目录文档不改 | 用户 2026-11-24 的两条消息 | Claude |

### CP6.0 本地复核的工作树例外（2026-11-24，记录者 Codex）

用户原话“允许保留已登记的历史产物并继续”。例外限于第 0 步登记的 20 个旧目录、32,005 个未跟踪路径，清单 SHA256 为 `80058813527583455970df7d14f9a488e53d38f799ec9a4a763228f894d993ec`。所有已跟踪文件与 6faffcab 匹配，启动前另逐项核对了 18 个生产模块与 212 个测试文件及夹具。第 4 步的最终主因偏差按原文停下。D25 状态维持已定。


### CP6.0.1（修改 AI：Claude）

| 日期 | 决策 | 变化 | 依据 | 记录者 |
|---|---|---|---|---|
| 2026-11-24 | 编译通过、Slither 侧失败的归因 | 搜索与接受规则不变；单元未成功时，以第一个编译通过但 Slither 侧失败的试验为最终结果，主因为 slither_incomplete（D25 的预期要求，属于实现修正，不改变已定决策） | CHANGE_LOG §63.2；cp6_0_v1/README.md 的 CP6.0.1 节 | Claude |
