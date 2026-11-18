# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.13（§4.1、§4.5）、CP3_REPORT 最新续节、artifacts/cp3_continue_v1/README.md、alias_binding_review_request.json、DECISIONS 与 CHANGE_LOG §31。第 6 节历史只追加。

## 0. 一句话

CP0–CP2.4 保持原结论。CP3 已实现诊断分类、项目闭包与生产管线接入；用户已接受 SOChecker 897/846 来源差异并批准项目图文件名 + key5。新增调用图测试发现 Slither 原生同名合约类型错绑，现有 D3 不能检出；全量已暂停，待确认新增项目绑定检查，CP3 尚未完成。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 决策 | D5/D16/D18/D20/D20a 保持；项目图文件身份已获批；绑定检查待确认 | DECISIONS；两个 project/alias review request |
| CP0–CP2.4 | 原产物与结论保留，不重放 6c | 既有审查目录 |
| 来源差异 | 用户已同意继续 ours.json 897 条；附属 846 条不并入 | cp3_continue_v1/authorization.json |
| 实现 | 16 个生产模块；新增 project.py、evaluation/report.py，其余在允许分层内 | test_layering；implementation 清单 |
| 分类表 | 保留 29 类、125 条 breaking changes；新增 30 个实测模板 | taxonomy_verified.json |
| 探针 | 92 版格式边界为 0.6.0；重复 SPDX 的同形探针边界 0.8.8；tuple 与 codegen 前提已测 | diagnostic/codegen 收据 |
| 输入清单 | 31,307 条，SOChecker 236 条无声明证据单列，31,071 条进入计划序列 | unit_inventory_summary.json |
| 运行 | 完成 120 + 752 个完整单元，另 1 个被中断；均为部分证据 | segment receipts；interrupted_segment_preservation |
| 测试 | 原完整生产套件 714/6，mando 268/452，DFG 2653；追加项目检查 24 passed/1 failed | pytest_*；失败仍保留 |
| 阻塞 | a、b 在 AST 中指向不同文件，Slither 原生对象却都指向 A.sol；新增接受条件尚未批准 | alias_call_probe.json |
| 提交 | 本批次未提交、未 push；当前新增测试未通过，不满足“全部通过后提交” | git status；PROMPTS §4.1 |

## 2. 分支与工作树

工作树 /home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair，当前起点 dc6c5fb44041e1023daef1bfd7d9760f534c7f0a。本轮是既有 CP3 下载与结构核验任务收到批准后的继续；此前已完成 pull，未重新拉取或推送。历史前置 88b499e7、获取检查点 dc6c5fb4 均在本地，旧批次保持不变。

新批次 artifacts/cp3_continue_v1；外部工作副本、原始日志和图位于仓库外 /home/zhao/SmartContract/compile-repair-local/cp3_continue_v1。原语料 corpora/ 只读。历史未跟踪产物不清理、不纳入提交；本轮交付按精确清单处理。

## 3. 环境

production=/home/zhao/miniconda3/envs/compile-repair-production：Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2。mando：Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。沿用 96 个编译器文件，其中支持范围 92 版；未安装、升级、切换全局 solc。

从仓库根运行，PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2，TREE_SITTER_LIB_DIR 使用既有 linux-x86_64 目录。仅 CPU，0 美元；没有 LLM、HGT 或 GPU 锁操作。本轮无新网络下载。

## 4. 必读事项（当前边界）

1. 面向未来任意检测输入，语料仅作评估。保留所有文档类别及未观察类别，Warning 与纯运行语义变化不当作编译失败。
2. 来源差异与文件名 + key5 已批准，不应再次询问；两份 authorization 分别绑定原请求 SHA 与用户原话。
3. alias_binding_review_request 尚待批准，不能擅自新增判据、修 Slither 包或改写合法源码。仅追加相对文件名不能纠正原生类型错绑。
4. 部分运行按现有 D3 得到的成功数不是图语义保证。partial_failure_summary 明确为临时结果，不能当全量或抽样验收。
5. 全量序列未抽样；用户未设置时限。首段按语料加权估计约 2.415 小时，遇到新测试失败后主动停止，未自动重试。
6. 首段正常封存；后段被 SIGINT 中断，没有正常 pipeline seal。interrupted_segment_preservation 保存全部现场哈希；不要补造正常完成状态。
7. 若批准绑定检查，先实现有限的 AST/Slither 一致性接受检查与拒绝案例测试，再在新批次继续。原始事实、D3(a/b) 测量与旧证据保留；受影响项目和中断单元的处理须按已批准请求记录。
8. 同一个 repair_unit 负责文件、片段和项目的版本/设置循环。项目 D3 覆盖所有闭包文件，solc 与 Slither 共用相对入口、cwd、remaps、--allow-paths .；不切换 standard JSON 主路径。
9. || pragma 与 Slither 进程内无超时仍仅登记缺口，未实现并集或子进程截止时间。当前 599 次完成的 Slither 调用未观察挂起，不能推断已提供超时保护。
10. 分片来源语言判定是词法证据，记录 pragma、声明或函数片段；部分语言共享语法无法仅凭词法完全排除。
11. 不下载库、不执行语料脚本、不再分发语料源码。source/working provenance 按文件分别保存；包导入、缺失相对文件候选只统计，不修复。
12. scripts、原作者代码、根目录交接/训练文档、EdgeSem 工作树、旧产物保持禁止修改；模块上限 30、Python3.7 和分层规则保持。所有记录写本模块 docs，待确认项不得写成通过。

## 5. 关键路径

| 内容（compile_repair 下） | 路径 |
|---|---|
| 最新状态 | CP3_REPORT；artifacts/cp3_continue_v1/README.md |
| 已定来源授权 | cp3_continue_v1/authorization.json |
| 已定项目身份授权 | cp3_continue_v1/project_identity_authorization.json |
| 当前待确认方案 | cp3_continue_v1/alias_binding_review_request.json |
| 原生错绑证据 | cp3_continue_v1/alias_call_probe.json；probe_alias_calls.py |
| 文档分类与实测模板 | cp3_v1/taxonomy.json；cp3_continue_v1/taxonomy_verified.json |
| 手写前提 | cp3_continue_v1/diagnostic_invocations.jsonl；codegen_probe_summary.json |
| 全部输入/部分运行 | unit_inventory_summary.json；partial_failure_summary.json；两个 segment receipts |
| 中断现场清单 | cp3_continue_v1/interrupted_segment_preservation.json |
| 验收、问题与保护核验 | cp3_continue_v1/pytest_*；frozen_audit；doc_check 收据 |
| 运行/训练改变记录 | docs/CHANGE_LOG §31；PROGRESS 最新续节 |

---

## 6. 交接记录

### 2026-11-11 CompileRepair 方案 r1 完成（修改 AI：Claude）

在 `node-sem@306c135b` 上新建 `compile-repair` 分支，新增 `scripts/compile_repair/`（PROMPTS r1、PROGRESS、REPORT_TEMPLATE 与 `artifacts/cr_pre_v1/` 证据），提交 39b78108（2026-11-11 06:29:57 EST）并 push；没有修改任何已有文件，其他分支头不变。

证据在云端临时环境中取得：MANDO 七类 `source_files` 共 846 个文件 0 个 import；按 `auto_version_solc.py` 规则 807 通过、10 失败、29 个所选版本 ≤ 0.4.10 不可得；在各自合取 pragma 区间内同一小版本系列换版本后 39/39 可编译，不改源码；Slither 0.8.0 在 39 个文件 × 2 个版本上全部成功，节点键与 SlithIR 39/39 相同，source length 36/39 相同；solc 0.4.11 时节点缺文件名；三个 solc 行为探针（等长 pragma 替换保持偏移、基类须先定义、无函数体声明可编译）通过。

r1 据此把方案收缩为确定性版本策略，LLM 层列为有触发条件的扩展。该收缩在当天被用户否定（需要覆盖更多编译问题、面向检测与 DAppSCAN 等真实语料），由 r2 替代；r1 的证据仍然有效。

本轮没有模块代码、没有在用户环境运行、没有下载语料到仓库；solc 二进制与 Python 3.8 环境只存在于 Claude 的临时环境中。详见 `CHANGE_LOG.md` §1。

### 2026-11-11 CompileRepair 方案 r2 完成（修改 AI：Claude）

按用户要求把模块目录从 `scripts/compile_repair/` 移到仓库根目录 `compile_repair/`（`git mv`，21 个文件内容不变），并把 `PROMPTS.md` 改为 r2；新增 `artifacts/cr_pre_v2/`（外部语料结构统计）。提交 bfd23e83（2026-11-11 09:00:39 EST）并 push，`edge-sem` 等分支头不变。

r2 的设计：一条流水线处理所有输入；九步确定性方法先于代理；第一阶段单代理（一个修复模板、RAG、带原文校验的补丁、多候选、按编译结果择优）；第二阶段多代理（失败分析、上下文扩展、2–3 个异构模型独立提议、工具裁决、至多一轮基于编译结果的交流）；改动记录与节点标记；代码结构规范（分层目录，非测试 `.py` 上限 30）；Prompt 重排为 CP0–CP10，CP0–CP3 写全，CP4–CP10 给出范围与验收。

外部语料只读统计：DAppSCAN 608 个项目、21,457 个 `.sol`，405 个项目有仓库内无法解析的 import，1,094 条相对导入目标缺失，606/608 个项目没有构建配置，版本跨 0.4–0.8；SOChecker 897 条片段中 656 条含 `contract `/`function `；Trace on-chain 5,000、repo-level 83 个项目 3,092 个文件、CVEs 15。这些数字说明依赖补全与项目组装是外部语料的主要工作量。

待用户确认 D5、D6 阈值、D9、D10，待定 D12、D13；CP0 不受影响。本轮没有模块代码。详见 `CHANGE_LOG.md` §2。

### 2026-11-12 CompileRepair 文档目录建立（修改 AI：Claude）

按用户要求参照 NodeSem 的记录方式，在 `compile_repair/docs/` 新建 `README.md`（文件用途、每个编码任务必须完成的记录、交接与详细记录模板）、`HANDOVER.md`（本文件）、`CHANGE_LOG.md`（编号五段式详细记录，补记 r1、r2 与本轮）、`DECISIONS.md`（决策当前表与历史表）。

同时修订 `PROMPTS.md` r2 的共享上下文与 CP0：记录改写到 `compile_repair/docs/`，并禁止修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md`（与 EdgeSem 并行追加会在合并时冲突）；写明 6c 被 git 忽略的本地结果只在 EdgeSem 工作树中，CP0 以绝对路径只读读取。修订记为 r2.1，设计内容不变。

本轮没有模块代码、没有运行编译或 LLM。全部新文档通过 `doc_check`。详见 `CHANGE_LOG.md` §3。


### 2026-11-12 CompileRepair CP0 前置核验检查点（修改 AI：Codex）

在独立 compile-repair 工作树、起始 HEAD 068433d0 上，先读 PROMPTS r2.1 §4.1 与 docs 当前交接/最新变更，再实现 CP0 前置调查和 solc/Slither 封装。新增 9 个生产模块、3 个测试和 1 个 fixture，完整清单见 CP0_REPORT。根目录记录、冻结 scripts、源码语料、旧证据和 EdgeSem 文件未修改。本次更新本文第 0–5 节的当前状态、工作树、环境、已知问题与关键路径；第 6 节此前记录逐字保留。

cp0_v1 正式调查一次：846 输入集合核对、256 份 6c SHA256 对应、43 metadata 来源校验、26 安装编译器 SHA256 核验通过，耗时 5.684 秒。6c 的 17 个异常文件与旧规则 A 异常集合完全相同。发现唯一精确要求 0.4.17 的输入没有本地候选，调查以退出码 2 停止；其他 845 份仅证明有候选，未证明能编译。真实 fixture 测试中 0.4.11 和 0.4.13 都 rc0，但前者 5 个缺 filename 节点被 D3 拒绝，后者通过。

用户已批准读取两份冻结 sources.json 及 metadata 引用的原始源码/CSV，D15 更新为明确授权，未读取标签/图/模型。43 份来源都是 SmartBugs versions.csv，更正了 PROMPTS 的 SolidiFI 描述。待批准 D16 只请求补齐必需 0.4.17，不包括可选端点；CP2 完整图比较的证据不足和精确 pragma 覆盖边界只登记建议，未改设计。停止位置是 CP0 前置门槛，矩阵编排尚未完成，不能进入 CP1。

CP0 测试第二轮 21 passed，首轮 1 failed/20 passed 是测试路径假设错误，已修正并保留日志；冻结 DFG v2 一轮 2653 passed、9 warnings。354 份 code refs 不变，9 个生产文件满足上限和分层；文档/最终审计结果见 CHANGE_LOG §4.5。本轮准备保存本地 CP0 检查点，不 push；实际提交号可由 git log 查询。没有下载、安装、全局 solc 切换、语料修复、图存储、HGT 训练、GPU 锁操作或 LLM 调用。


> 上游交接导入说明：下文来自 54ecc927；其中 CHANGE_LOG §4 指上游 r2.2 记录，在本地合并文档中编号为 §5。上文 CP0 的本地安装决策 D16 已映射为 D17；r2.2 D16 指 Slither 兼容性。

### 2026-11-12 CompileRepair 方案 r2.2：面向检测时任意输入，去除对训练数据集的依赖（修改 AI：Claude）

用户说明本方案不只修复当前训练数据集中的问题，还要修复将来模型检测时输入的任意损坏合约，不应只针对当前数据集设计。据此把 `PROMPTS.md` 从 r2.1 改为 r2.2，只修改该文件；同时按记录规则更新本文件、`CHANGE_LOG.md`、`DECISIONS.md` 与 `PROGRESS.md`。

主要修改：0 节新增“适用范围”（检测时的任意输入，0.4.12–0.8.x）；D6 取消“占剩余失败 ≥ 1% 或 ≥ 20 个编译单元”的频率门槛，改为按与语料无关的失败分类表逐类判定（有可确定性实施并能机械验证的修复就实现，否则交给代理，频率只排顺序）；分类表来源限定为 solc 文档的 13 种错误类型（已核对 v0.7.6 文档“Error types”一节）与 0.5–0.8 各版本 breaking changes 等有文档依据的内容；版本策略中“metadata”改为调用方可选提供的已知版本，无 pragma 时按文档有出处的版本特征推断区间，MANDO 的 0.4.25 默认值只作回归配置；入口统一为 `cli repair <路径>`；CP0 增加全版本范围编译器清单与 Slither 可用性探针，CP2 改为 MANDO 回归运行，CP3 先建分类表，CP4 破坏算子覆盖分类表中每个可构造类别。

新增 D16：Slither 0.8.0（6c 使用的版本）能否处理较新 0.8.x 编译器的输出未验证，由 CP0 测出后用户决定。顺带更正：本文件第 1 节状态表在 r2.1 提交中仍写着 r2，本轮改为 r2.2；第 0、1、4 节（一句话、状态表、必读事项第 8–10 条）均已更新。

本轮没有模块代码、没有编译或 LLM 运行，所有文档通过 `doc_check`。下一步仍为 CP0。详见 `CHANGE_LOG.md` §4。


### 2026-11-12 CompileRepair CP0 续作调查完成，停在 D16（修改 AI：Codex）

本轮位于独立 compile-repair 工作树，起始 HEAD 8fb81ed9，先阅读 PROMPTS 共享上下文及 CP0，并同步上游 r2.2。因本地检查点与 54ecc927 分叉，保留双方历史合并，原安装 D16 改编号为 D17，Slither 兼容性沿用上游 D16。扩展 solc、survey 和 CLI，补测试及六个版本特征 fixture，仍是 9 个生产文件。本文第 0–5 节已更新当前阻塞、版本覆盖、测试、分支、路径与下一步，旧交接记录全部保留。

cp0_v2 在 846/846 输入上找到 D3 合格版本，旧 6c 的 17 个异常全部通过。678 份双版本的 key4 和有序 SlithIR 一致，28 份 source length 不同；55 份有重复 key4，保留重数而不去重。官方快照目标范围 92 版，33 版已装，另有四个历史负对照，总 37 版；39 组探针全部编译成功，但六组 D3 失败。四组早期负对照缺映射，另两组为 0.8.4/0.8.38 自定义错误解析失败，正式状态 awaiting_d16、CLI rc2，依据见 RECON §9–10 与封存结果。

用户“可以下载”批准 0.4.17，随后“批准这 10 个探针版本（推荐）”追加批准十个明确版本，授权、官方索引和二进制双哈希全部落盘。未把该授权扩展为安装全部补丁或升级 Python/Slither；原 26 份信任记录、全局版本选择保持原样。当前停在 PROMPTS CP0 §5b 要求的 D16，建议独立评估新版工具链但尚未实施。D4/CP2 的重复节点及报告可观察范围、D5 的精确 pragma 边界均列为审查项，没有自行更换设计。

CP0 最终 32 passed，冻结 DFG v2 为 2653 passed、9 warnings；开发首轮区间反序列化错误已在新小样本和新增测试中验证修复，失败现场保留。354 个冻结引用与 846 份输入不变，正式运行后不改实现，文档检查与最终审计结果见 CHANGE_LOG §6.5。全部验收后本地提交，以 CP0 开头，提交号由 git log -1 与最终答复给出，不 push。没有通用 repair、源码修复、图存储、外部语料获取、HGT 训练、GPU 锁或 LLM 调用。


### 2026-11-12 CompileRepair CP0 审查与方案 r2.3（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0（提交 8fb81ed9、ac2b3465）：核对方案、代码、产物与四份记录中的问题，判断 Codex 的处理是否正确，对错误或未解决的问题给 Codex 写计划；全部核实后才能进入 CP1。起点 `compile-repair@ac2b3465`。新增证据目录 `artifacts/cp0_review_v1/`（独立复核脚本、5 个 Slither 版本的语料与特征对照），修改 `PROMPTS.md`（r2.2 → r2.3）。本文第 0、1、4、5 节已重写：一句话与状态表换成审查结论；第 4 节恢复 r2.2 中被合并丢失的条目（证据环境不同、外部语料无许可证、检测时任意输入、0.4.10 无静态二进制），并加入 key5、source_mapping 两种形式、tree_sitter 依赖、pragma 覆盖边界与编号笔误；第 5 节加入审查证据路径。

结论：CP0 的数字全部可复现，SHA256、规则 A、升降序、1,692 个选定版本的区间与 D3 记录、678 对跨版本比较都与 Codex 一致；本环境 Slither 0.8.0 的节点指纹与 Codex 743/743 相同。Codex 的处理中，metadata 来源的更正、按多重集合保留重复 key4、停在 D16 都正确。问题在方案本身：D3 漏了顶层函数且没有合约覆盖检查；key4 不唯一（序号身份 678/678 稳定，改为 key5）；pragma 覆盖两处规定互相矛盾；CP0 的 toolchain 只能读 dict 形式 source_mapping，新版 Slither 下会报错。

D16 补测：0.8.3 结构与 0.8.0 完全相同但不支持顶层 using 与全局运算符；0.9.6 六个特征全部通过、MANDO 无失败、只缺合成的常量构造函数节点；0.10.4/0.11.6 在 3 个 0.4.24 重入合约上崩溃且结构大幅变化。推荐 0.9.6 独立环境做生产，0.8.0 只做 6c 精确重放。新增 D18（补齐其余 59 个官方编译器）。

下一步：用户决定 D5、D16、D18；Codex 执行 CP0.1（A 部分不需要授权，可先做）；Claude 审查后再进入 CP1。本轮没有模块代码改动、安装或 LLM 调用。详见 CHANGE_LOG §7。

### 2026-11-12 CompileRepair CP0.1 A 完成，B/C 待授权（修改 AI：Codex）

在 compile-repair 从已同步的 61a3cb6a944140108763442999bbfd4199f53ca3 开始，先读 PROMPTS r2.3 §4.1、全文及当前交接/最新记录，再执行 A。修改 Slither 封装、survey、CLI、旧测试，新增映射/key5/覆盖/profile 测试与两个 fixture，生产文件仍为 9 个。冻结代码、输入、旧产物、CP0 报告和根文档未改。本次更新交接第 0、1、2、4、5 节状态、下一步与路径，第 6 节历史逐字保留。

846 文件全部通过新 D3，(a)/(b) 失败均 0，CP0 投影 846/846 一致，语料顶层函数 0。678 组跨版本 key5 与有序 IR 全同，其中重复 key4 的 31 组也全同；55 个选定版本文件的重数保留。solc 与 Slither 各 1,546 次成功，201,044 条节点中无重复 key5 组，完整证据在 cp0_1_v1。length 的 28 组差异仅诊断，生产环境和完整图边语义未验证。

按 §4.2b，B 需 D16 决定与环境授权，C 需 D18 决定与编译器授权，因此完成 A 后停止。两份具体清单已在 cp0_1_development_v1 列出，均 pending、费用上限 0 美元；此前 11 个 solc 批准不扩张使用。另登记 transient 0.8.24 文案与审查 >=0.8.28 高级变量 fixture 的边界待核对，如需改方案先咨询，没有自行实施替代。CP1 仍需完整 CP0.1 审查及 D5/D16/D18 决定。

模块 CPU 测试 55 passed，冻结 DFG v2 测试 2653 passed、9 个既有警告，无失败/跳过；文档和最终审计见 CHANGE_LOG §8.5。编辑工具的 WSL 路径与模板问题已解决并保留说明，无正式运行重试。本轮检查通过后只作本地提交，标题以 CP0.1 complete A 开头、不 push；旧 CP0 ac2b3465 在此前已按用户要求推送，当前区据此更正。没有新增下载/安装、LLM、HGT 训练、GPU 锁操作、输入改写或图存储。
终审首轮因 PowerShell 中文字面量编码导致标题定位失败，已保留现场并改用 ASCII 前缀；最终确认 354 个冻结代码引用、846 个输入、37 个编译器与四份历史记录均未改变，文档 6/6 通过后提交。


### 2026-11-13 CompileRepair CP0.1 A 审查与方案 r2.4（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0.1（提交 18940a8a）：核对方案、代码、产物与记录中的问题，判断处理是否正确，对错误或未解决的问题给 Codex 写计划；全部核实后才能进入 CP1。新增证据目录 `artifacts/cp0_1_review_v1/`，修改 `PROMPTS.md`（r2.3 → r2.4）。本文第 0、1 节换成审查结论，第 4 节第 15 条改写（transient 待核对项已核实），第 5 节加入审查证据路径。

结论：CP0.1 A 正确。验收数字全部可复现；1,546 组（源文件, 版本）节点的 key5 与有序 IR 和 Claude 用独立脚本按 Slither 节点顺序导出的结果逐组相同；所用版本与 cp0_v2 的选定和端点集合完全一致；CP0 投影 1,546/1,546。Codex 的代码在 Slither 0.9.6、0.11.6 下也能正确处理对象形式的 source_mapping 与 AST。Codex 登记的 transient 问题成立：0.8.24 只有 Yul tload/tstore，transient 状态变量从 0.8.28 起才能编译，r2.3 写错了。D18 的 59 个编译器请求与官方 solc-bin 索引逐项一致。

新发现：r2.3 推荐 Slither 0.9.6 只依据 6 个探针。扩展到 19 个后，0.9.6 有 6 种 0.8.7 起的合法写法无法分析，0.11.6 全部通过；846 个文件上 0.9.6 全部通过，0.11.6 有 3 个 0.4.24 文件崩溃，可用语义等价改写处理。推荐改为 0.11.6，备选 0.9.6；若选 0.11.6，Codex 已提交的 0.9.6 环境请求需要改写。

下一步：用户决定 D5、D16、D18 并授权；Codex 执行 CP0.1 B、C（4.2b 节 r2.4 版）；Claude 审查后再进入 CP1。本轮没有模块代码改动、安装或 LLM 调用。详见 CHANGE_LOG §9。


### 2026-11-13 用户决定 D5、D16、D18（修改 AI：Claude）

用户采纳 r2.4 的推荐：D5 区间内升序；D16 生产工具链用 Slither 0.11.6 + crytic-compile 0.4.2（Python 3.10 独立环境，0.8.0 只做 6c 重放）；D18 安装其余 59 个官方编译器。已更新本文第 0、1 节与 DECISIONS。Codex 的 0.9.6 环境请求作废，B 开始时按 4.2b 节重写为 0.11.6 版本并落盘授权。没有代码改动或运行。详见 CHANGE_LOG §10。


### 2026-11-13 CompileRepair CP0.1 B 完成、C 安装完成后遇兼容性失配停止（修改 AI：Codex）

本轮在 compile-repair@897fbd03116040ddbc8d106db1b844624f512091 开始，pull --ff-only 已同步，阅读完整 r2.4 及必读记录后按用户新授权执行 B/C。生产代码只在 toolchain/slither.py 增加 production、metadata 回退与实际平台记录，新增对应测试和原字节的 19 个 probe。A 未重跑，CP0/A 归档、旧 0.9.6 请求、原输入、mando 和旧 solc 文件未修改。当前第 0–5 节已更新为 B 实测完成、C 安装完成但兼容性停止的状态，并替换旧待授权环境信息与下一步边界。

B 的 846 份区间与 mando 全同，固定版本 D3 为 843/846，指定的三个 0.4.24 AssertionError 和 435 份结构差异全部吻合审查。23 组当前特征组合全部通过，三个工作副本在两套环境中均通过，节点数 11→10、11→10、6→5，具体见 CP0_1_REPORT B 与 cp0_1_env_v1。B 门槛通过后才安装 59 个 solc，全部双哈希和 --version 通过，支持范围达到快照 92/92。C 的 496 组只执行了 225：224 过、1 失败、271 未运行，见 compatibility.json。

用户本轮明确批准 D5 升序、D16 0.11.6/0.4.2 独立环境与 D18 的 59 版下载，费用上限 0 美元，授权在两个批次中先行写入。C 首个失配为 0.8.24 编译 h0824_blob.sol 时 blobhash 未声明，rc1 且未运行 Slither，已按原文停止并保留现场。没有放宽判据、变更编译参数、修改 probe 或自动重试；后续应先审查最低语法版本及 EVM 设置，任何方案调整须先咨询用户。C 与 CP0.1 整体尚未通过，CP1 不开始，第 10 行改写规则仍留给 CP6。

生产模块测试 77 passed/6 skipped，mando 模块 58 passed/25 skipped，冻结 DFG 2653 passed/9 warnings；两套 metadata 路径和平台组合等价均验证。初始 user-site 依赖混入在安装前用新环境专属隔离解决，开发正则收集错误已修正并保留失败日志，均未改变验收判据。frozen_audit 核对模块外 27845 文件、旧产物 204、旧编译器 37、mando 元数据 205 以及 code_refs 354 项不变，doc_check 与最终审计见 CHANGE_LOG §11.5。本轮在全部强制记录之后本地提交，不 push；无 LLM、训练、GPU 锁、图存储或范围外安装。


### 2026-11-13 CompileRepair CP0.1 B、C 审查与方案 r2.5（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0.1 B、C（提交 33c23a3b）。新增证据目录 `artifacts/cp0_1bc_review_v1/`，修改 `PROMPTS.md`（r2.4 → r2.5）。本文第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节 Codex 写的 18 条保留（第 16、17 条的待处理事项由 4.2c 节处理）。

结论：B 正确。生产运行的 846 次调用、843 个 D3 通过、3 个 0.4.24 失败、435 个结构差异文件都与审查预期相同；与 Claude 独立的 0.11.6 运行比较，839/843 个文件的 key5 与有序 IR 完全相同。59 个编译器的哈希与官方索引 0 差异。C 停在 0.8.24 + h0824_blob 是方案错误：r2.4 写的探针下界是语法引入版本，审查时只在 0.8.38 上运行过；实测默认设置下 4 个 Cancun 探针从 0.8.25 起可编译（0.8.24 需要 `--evm-version cancun`），h0826 从 0.8.27 起可编译（0.8.26 需要 `--via-ir`），加设置后 Slither 0.11.6 D3 通过。Codex 不改参数、停下报告是正确的。

新发现：其余 4 个文件的差异来自 Slither 0.11.6 在 IR 文本中输出 Python 对象内存地址，指纹不能复现，CP2 前必须规范化。设计缺口：精确 pragma 0.8.24 或 0.8.26 的真实合约只能靠编译设置编译，r2.5 在 3.3 节加入第 3a 条（设置表、同一版本重试、Slither 使用相同设置），在 CP1 实现。

下一步：Codex 执行 4.2c 节（不需要新的安装或授权）；Claude 审查后进入 CP1。本轮没有模块代码改动或安装。详见 CHANGE_LOG §12。


### 2026-11-13 CompileRepair CP0.1 C 续完成本机验收（修改 AI：Codex）

本轮在 compile-repair@3742fb75e535b5517ded58659e78737a01b51000 上执行 PROMPTS r2.5 §4.2c，pull --ff-only 返回 Already up to date。完整阅读共享上下文、最新交接、DECISIONS、CHANGE_LOG §11/§12 和审查 README 后，修改三个工具链/数据文件、一个测试文件并新增一个测试文件。新产物只写 cp0_1_env_v2 与 cp0_1_compilers_v2，旧报告只追加 C 续，A/B/原 C 证据不变。本次更新本文第 0、1 节状态，第 2 节起点/提交边界，第 3 节环境限制，第 4 节设置/IR/覆盖事项和第 5 节新证据路径。

两次生产各 843/846 D3，失败仍为相同 3 个 0.4.24 AssertionError；843/843 指纹跨运行相同。与 B 比较，839 个成功文件完全相同，另外 4 个文件各只规范化 1 行 IR；四份新节点归档无对象地址残留（archive_audit.json）。按 SHA256 排序后 Random(0) 抽样的 20/20 在 mando 与 A 指纹一致。兼容性 501/501 符合预期，含 491 默认正例、5 设置正例、5 默认负对照；原 224 成功组逐组一致，59 个新增版本均完成计划。

本轮严格使用 r2.5 新批准的参数与预期，没有方案外替代或放宽判据。读取审查 JSON 时发现其为连续两个对象，按实际格式读取并记录，原证据不改；原始 stderr 无损压缩保留。92/92 是可信安装口径，本次 501 组是新增 59 版的矩阵，不宣称穷举全部语法。设置的自动触发/升序策略留给 CP1，源码改写留给 CP6；下一步必须审查本轮之后才能开始 CP1。

两环境新增逻辑与分层各 27 passed；完整模块 production 506 passed/6 skipped、mando 83 passed/429 skipped，冻结 DFG v2 为 2653 passed/9 个既有弃用警告。全部命令与 rc 见 test_summary.json 和同名日志，UTF-8/doc_check 与冻结审计见 CHANGE_LOG §13.5 最终补记。完成记录和检查后按要求本地提交，本任务不 push。没有训练、GPU 锁操作、安装、下载或 LLM API 调用，费用 0 美元。


### 2026-11-14 CompileRepair CP0.1 C 续审查与方案 r2.6（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0.1 C 续（提交 08337158）。新增证据目录 `artifacts/cp0_1c2_review_v1/`，修改 `PROMPTS.md`（r2.5 → r2.6）。本文第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节 Codex 写的条目保留。

结论：C 续正确。两次生产运行指纹 743/743 个不同源文件相同、对象地址残留 0；与 B 归档只差审查指定的 4 个文件；与 Claude 独立的 0.11.6 运行规范化后 740/740 相同；回归样本 20/20；兼容性 501/501（496 原组合逐组保留、5 个负对照错误文本与 r2.5 一致、5 个设置正对照通过）；seal 中 49 个产物、9 个实现文件、7 份文档的哈希全部一致。Codex 的设置代码在 Claude 环境中端到端验证通过。CP0.1 完成。

新发现：0.4.11 缺文件名只在 Slither 0.8.0 中、且与工作目录有关；0.11.6 未出现。r2.6 因此把 CP1 中“0.4.11 缺文件名”测试改为替身测试，并在 CP1 第 6 节测量生产工具链在历史编译器上的 D3（只记录）。另外，CP1 小样本原来的验收（选定版本与 CP0 预测相同、D3 失败 0）是按 0.8.0 与 37 个编译器写的，改为可归因比较，并加入 3 个已知 Slither 侧失败的合约。

下一步：Codex 执行 CP1。本轮没有模块代码改动或安装。详见 CHANGE_LOG §14。


### 2026-11-14 CompileRepair CP1 完成，等待审查（修改 AI：Codex）

在 compile-repair@d5e84d39 同步后通读 r2.6 全文及交接/决策/§13/14/C 续审查，实现核心层、唯一环境策略和 repair。新增生产 5 文件、修改 4 文件、新增 3 份测试；旧 solc 函数 AST、Slither 整文件、旧报告/产物均不改。新证据仅三个 cp1 批次；本文第 0–5 节更新为当前实现、验收、命令、已知问题和路径，第 6 节此前字节保留。

两个环境固定 37 编译器离线升降序各 846/846，六组真实设置自动重试通过。95 样本 92 成功、3 预期 Slither 侧失败；91 选版相同、1 因新增更低 0.5.5 而变化，原文件均不改。23 历史组合、46 Slither 测量中 0.4.11 两 CWD 各 5/5，其他三老版本仍失败，下限保持 0.4.12。数字见 CP1_REPORT/acceptance/counts；冻结 28,236 文件、354 code_refs、96 solc 与环境元数据通过。

没有更换方案或放宽标准。只登记原 command() 在 cwd=/ 的路径问题，待审查和用户确认后处理，历史前置编译在仓库根未受影响。归档排除 pytest current 符号链接别名读取原通过结果；末轮 WSL 超时经文件 SHA 未变和短命令恢复核验后分批写记录，未重跑测试/实验或重启服务。CP1 仍需审查，CP2/CP6 未开始。

生产模块 546 passed/6 skipped，mando 116/436，DFG 2653 passed/9 warnings；分层、Python 3.7、旧代码保护通过。八份 doc_check 与精确暂存结果保存到本轮 artifact，全部完成后本地 CP1 提交，不 push。没有下载安装、全局 solc 切换、LLM、训练或 GPU 锁，费用 0；训练改变记录只写模块 docs。


### 2026-11-14 CompileRepair CP1 审查与方案 r2.7（修改 AI：Claude）

用户要求审查 Codex 完成的 CP1（提交 3497af24）。新增证据目录 `artifacts/cp1_review_v1/`，修改 `PROMPTS.md`（r2.6 → r2.7）。本文第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节 Codex 写的条目保留。

结论：CP1 的实现与验收成立。冻结选版重放两环境升降序 846/846；95 个样本 case 的封存、候选集合、尝试顺序与结果审计无问题；Claude 用 GitHub 静态 solc 与自己的 Slither 0.11.6 独立重算，95/95 选定版本与尝试序列相同；唯一差异（0.5.5）归因成立；pragma 覆盖（CRLF、同行代码）、无 pragma 推断与多 pragma 交集在 Claude 环境中端到端正确。Codex 登记的 `command()` 问题属实，且比登记的范围大：除 `/` 外，字符前缀相同的兄弟目录也会使合法合约判为失败，经流水线复现为 `all_solc_candidates_failed`。

处理：新增 4.3b 节 CP1.1（路径边界修复与 argv 相同性证明、regression_6c 的防护、solc 超时按输入记录、无 git 时的封存）；CP2 提示按生产工具链与 92 个编译器更新（预期 3 个 Slither 侧失败、存储格式、两次运行确定性、与同版本生产归档逐组相同、生产工具链上的跨版本比较）；D5/D16/D18 状态改为已定；新增 D19 建议维持 0.4.12；CP3 加入 `||` pragma 与 Slither 超时两项缺口。

下一步：Codex 执行 CP1.1；Claude 审查后进入 CP2。本轮没有模块代码改动或安装。详见 CHANGE_LOG §16。


### 2026-11-14 CompileRepair CP1.1 完成，待审查（修改 AI：Codex）

在 compile-repair@d4f4b48a 起按用户指令先 pull --ff-only，读取 PROMPTS r2.7 全文、本文 §0–5、DECISIONS、CHANGE_LOG §15/16 和 cp1_review_v1/README。只修改 solc.py、slither.py、pipeline.py，新增 test_cp1_1.py，生产文件仍 14。当前 §0–5 全部更新：替换下一步、测试数字、路径修复/超时/无 Git 的新行为与证据路径。第 6 节历史及 CP1 报告旧字节保留，原产物不改。

两环境各 846+501 项新旧 argv 相同，五种 cwd 真实 solc 各 5/5，三种超时场景各 3/3。production 的超时批次续行、信任停止和两种真实无 Git 封存通过，14 个实现 SHA 保持可核验。九组 CLI 均成功，各 10 节点；同一 fixture 的状态、版本、设置及 key5+IR+标记在三个目录逐项相同，90 个节点均 original。证据在 cp1_1_v1/module_acceptance.json、cli_acceptance.json 与各 case seal。

本轮没有偏离 PROMPTS，没有替代方案或追加安装授权。D5 当前表同步既有 CP1 审查通过结论，D19 仍为建议，保持 0.4.12。|| pragma 与 Slither 进程内无超时仍留 CP3，三份旧重入兼容改写仍留 CP6。下一步先审查 CP1.1，再进入 CP2。

production 模块 562 passed/6 skipped，mando 128 passed/440 skipped，DFG 2653 passed/9 warnings，三轮均首次通过。按 CHANGE_LOG §17.5 完成冻结检查、6 份 doc_check 和精确暂存后本地提交 CP1.1，不自动 push。没有重跑 CP1 样本、下载安装、LLM、训练或 GPU 锁操作，费用 0。完整提交号以 git log 的 CP1.1 条目为准。


开发记录补记（修改 AI：Codex）：冻结审计辅助脚本第一次从文件路径启动时，在执行检查前因未把仓库根加入 sys.path 而报 ModuleNotFoundError: scripts；没有生成 frozen_audit.json，没有实际冻结判据失败。保留 frozen_audit_launch_error.json 后，只给本批次辅助脚本补齐仓库导入路径，再执行冻结核验。生产代码、验收标准、已通过的三轮 pytest 和九组 CLI 没有修改或重跑；这是证据脚本启动问题，不是编译器或环境缺包，也未安装任何内容。


最终检查补记（修改 AI：Codex）：frozen_audit.json 的 passed=true，28,323 个受保护跟踪文件、354 个 code_refs、96 个 solc 文件及 mando/production 的 117/144 份包元数据均未变化；模块外跟踪改动为 0，生产文件仍 14，未授权的工具链函数 AST 变化为 0。旧 CP1_REPORT、PROGRESS、CHANGE_LOG 前缀及 HANDOVER/DECISIONS 历史原字节保留，14 个实现哈希与测试时两份封存相同。doc_check_v1 的 6 行全部 passed=true、rc0；本补记写入后按相同目标运行 doc_check_v2，最终收据为 doc_check_v2.jsonl / doc_check_v2_invocation.json。随后封存证据、按 file_inventory 精确暂存并检查 git diff --cached --check，成功后提交 CP1.1；本步不 push。


无损交付归档补记（修改 AI：Codex）：首次暂存清单 123 文件，内容 SHA 检查通过，但 git diff --cached --check 返回 2：三个精确 0.4.10 case 的 pragma_overridden.sol 第 3 行是按方案要求生成的等长空格，触发行尾空白检查。该空格不能删除，否则会改变字节偏移与既有 case seal。沿用 CP1 的交付方式，把九组 CLI 输出的 84 个文件无损打包为 cli_cases.tar.gz，逐成员 SHA256/长度回读 84/84 一致；原文件和九个 case seal 在本地保留不改。未放宽 Git 检查，未重新运行 CLI，未修改生产存储格式。

CLI 归档 SHA256 为 bec8f18cdc4510bf066d4bf79abe4489ab8d70c8c8e61a263b60ee63f1cf844b，大小 95,681 字节，archive_audit.json 保存成员清单。前文 cwd/out2/* 路径现在表示归档内成员，替代此前“按原目录提交”的交付说明。首次 seal.json、file_inventory.json、final_validation.json 均保留原字节，作为归档前阶段快照；当时的六份文档保存于 prepackaging_documents.tar.gz，与初版文档哈希完全一致。最终交付以 delivery_seal.json、delivery_inventory.json 为准，它们绑定最终文档及两个压缩包；不得将初版快照误当最终提交清单。失败现场为 staging_failure.json，当前原始目录只留本地，不删除、不提交重复副本。

归档说明纳入 CP1_REPORT、PROGRESS、CHANGE_LOG §17.5、HANDOVER 和本批次 README；追加记录遵守历史字节边界。doc_check_v1/v2 均已 6/6 通过，归档补记后按相同六目标再检查并保存新收据，完成后重新核对精确暂存范围和格式，再本地提交；编译、测试与 CLI 的已通过结果保持。


### 2026-11-14 CompileRepair CP1.1 审查与方案 r2.8（修改 AI：Claude）

用户要求审查 Codex 完成的 CP1.1（提交 27aa46fe）。新增证据目录 `artifacts/cp1_1_review_v1/`，修改 `PROMPTS.md`（r2.7 → r2.8）。本文开头的阅读顺序、第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节保留。

结论：CP1.1 正确。修复后 `command()` 在 `/`、字符前缀兄弟、包含与无关目录下两个环境 8/8 rc 0；仓库根下 846 个 MANDO 文件与 501 个兼容性组合的 argv 与旧算法 1,347/1,347 相同（两个环境），CP0–CP1 结果不受影响；Claude 的 3 个输入与 Codex 的 9 个 CLI case 在三种目录下状态、版本与节点哈希逐个相同；超时、无 git 与 regression_6c 防护的代码符合 4.3b 节。

方案补充：核对 Slither 0.11.6 的类层次后，r2.8 在 CP2 存储格式中写明 LibraryCall 先于 HighLevelCall 判断、其他 Call 子类按类名记录、CFG 边带 true/false/next；CP2 第 2 节不再对“6c 版本不同的文件”重跑，改为列出归因；给出运行时间估计。

下一步：Codex 执行 CP2。本轮没有模块代码改动或安装。详见 CHANGE_LOG §18。


### 2026-11-14 CompileRepair CP2 生产图完成、6c 首差停止（修改 AI：Codex）

本轮先 pull --ff-only 至 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18，通读 PROMPTS r2.8 与指定交接/审查。修改 cli、pipeline、toolchain/slither 及替身测试，新增图测试和调用 fixture，仍 14 个生产 .py；新增四个 CP2 批次、CP2_REPORT 和强制记录。本文 §0 改停止结论、§1 改状态数字、§2 改实现与交付范围、§3 改现用环境和命令边界、§4 改图/授权/差异/封存事项、§5 改证据路径；第 6 节旧历史字节保留。旧 CP0–CP1.1 结论/产物、scripts、原语料、环境与根记录不改。

两次 production 各 843 成功/3 规定失败，843 图字节一致；每轮 110,996 节点、87,645 边、45,565 调用。CP0 842 同版且归档 key5+IR 一致，1 项 (a) 0.5.6→0.5.5；6c 版本 238 同/1 旧下限差异，证据 cp2_summary、acceptance/receipt。主阶段 275.856/276.572 秒；6c 第 87 个 buggy_43.sol 停止，86 同/1 差，旧报告仅多 Post 继承上下文 i < 32 的 [162,out,DEF]。离线原始行核验确认，底层原因未证明；剩余 152 与降序未运行，CP2 未通过，CP3 前提不满足。

用户于 2026-11-14 批准“允许单列既有下限差异，记录后继续”，仅改版本归因，D3、CP0 三类与 239/239 标准保持；授权先落盘再运行。未重试重放、改键或改旧提取器；下一步先独立审查，需新执行/改方案时先提具体建议咨询。96/92 字段澄清、前置工具/审批超时/文档超长命令问题与处理全部在 CHANGE_LOG §19 和证据，无补装依赖。

三轮 pytest 为 production 567 passed/6 skipped、mando 130/443、DFG 2653 passed/9 既有 warnings，首次通过，完整命令/日志在 pytest_*.json。正式存储 tar 各 4,229/4,229/93 成员全部回读相同，原现场保留；9 份 doc_check、冻结与提交检查见 CHANGE_LOG §19.5。按要求记录后本地提交，不 push；无安装、下载、LLM、训练、GPU 锁或全局 solc 变更，费用 0。

保护检查补记（修改 AI：Codex）：frozen_audit 已通过，28,373 受保护跟踪文件、354 code_refs、96 solc、239 原始源码及本轮登记的 90/114 份环境元数据不变，14 个实现与测试封存相同。doc_check_v1 为 9/9，最终补记用 v2 收据绑定；验收停止结论不变，交付精确暂存后本地提交。


### 2026-11-14 CompileRepair CP2 审查与方案 r2.9（修改 AI：Claude）

用户要求审查 Codex 完成的 CP2（提交 3dfb347d）。新增证据目录 `artifacts/cp2_review_v1/`，修改 `PROMPTS.md`（r2.8 → r2.9）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节保留。

结论：生产部分成立（两次全量与图字节确定、同版本 842/842、调用分类与引用完整）。新发现空体 if 的边种类缺陷：son_true 与 son_false 为同一节点时两条边都标 true，共 86 个节点。6c 重放停在 buggy_43.sol：Claude 证明 Slither 0.8.0 的局部写集合不确定——同一进程连续 10 次得到 252、253、254 三种结果，按 6c 顺序先跑 86 个文件后得到与 6c 报告相同的 252，Codex 得到 251；生产 Slither 0.11.6 连续 10 次完全相同。Codex 停下并且没有放宽判据，处理正确。

处理：新增 4.4b 节 CP2.1——修复边种类并重跑两次生产全量；6c 重放改用“稳定事实必须相同、不稳定事实落在 11 个样本的范围内”的判据（D20，需用户批准）；完成降序跨版本比较。

下一步：用户批准 D20 后由 Codex 执行 CP2.1。本轮没有模块代码改动或安装。详见 CHANGE_LOG §20。


### 2026-11-14 CompileRepair CP2.1 生产修复通过，D20 触发停止（修改 AI：Codex）

从 compile-repair@1ed79a6708f505ecb9aa80b157a43f9e07608c9f 开始，pull --ff-only 已同步并通读 PROMPTS r2.9 与指定记录。生产只改 toolchain/slither.py 的 graph_facts，新增 18 个条件边测试和 graph_branches.sol，非测试 Python 文件数仍为 14。本次更新本文第 0–5 节的状态、起始 HEAD、范围、D20 边界与证据入口；第 6 节已有内容原字节保留，CP2_REPORT、PROGRESS、CHANGE_LOG 只追加。所有新结果在 cp2_1_v1、cr_store_mando_v3/v4、cp2_6c_v2，原 CP0–CP2 产物不覆盖。

两轮生产各 843 成功/3 已知失败，843 图字节一致，与旧 v1 仅 40 文件 86 个指定条件边标记变化，节点、调用、其他边不变。6c main 在第 227 份 reentrancy/buggy_44.sol 停止：223 精确同、3 个差异符合 D20、1 失败；4 个差异文件各新进程连续 10 次，加 main 共 267 次提取。失败键为非继承 MultiHashWrapper 上下文的第 282 行 out DEF，参考重数 1，但固定 11 次全 0，完整键与原始行见 CP2_REPORT 的 CP2.1 和 captured_replay_audit.json。9 个观察到的波动键均 L1 DEF，其中 5 继承、4 非继承，未写成确定根因。

用户于 2026-11-14 原话“同意 D20”，开始前已写授权并把当前决策改为已定；本次停止严格遵守原判据，没有额外采样或替代方案。只读复算全部已保存比较与 D20 计数一致，新增提取 0。剩余 12 个 6c、降序以及 CP3 未运行，整体 CP2.1 未通过；先独立审查封存材料，任何新增实验或方案改变仍先咨询用户。D3、D5、D16、旧下限归因与冻结 DFG 结论均保持。

production 模块 585 passed/6 skipped，mando 147/444，DFG 2653 passed/9 既有 warnings；D20 边界 12 项通过，三份 tar 逐成员回读通过。最终冻结审计、doc_check 及精确交付记录见 CHANGE_LOG §21.5 和 cp2_1_v1。本轮完成强制记录和检查后本地提交 CP2.1 停止现场，准确提交号见 git log，不自动 push；无安装、下载、LLM、HGT 训练、GPU 锁或全局 solc 变更。


### 2026-11-14 CompileRepair CP2.1 审查与方案 r2.10（修改 AI：Claude）

用户要求审查 Codex 完成的 CP2.1（提交 63a1510b）。新增证据目录 `artifacts/cp2_1_review_v1/`，修改 `PROMPTS.md`（r2.9 → r2.10）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节保留。

结论：图修复正确；v3、v4 的 843 个图字节相同，与 v1 相比只有审查指定的 86 条边由 true 改为 false，节点与调用不变。6c 重放在第 227 个文件停止：6c 报告中有一个键在 Codex 的 11 个样本中没有出现。Claude 对该文件同进程连续抽取 40 次，该键出现 18 次，说明它与已判为不稳定的 9 个键同类（数组在 for 循环体内按下标写入，DEF 时有时无地记到循环条件行），只是没有被抽中。Codex 按 D20 停下、没有追加样本，处理正确。

处理：新增 D20a（待用户批准）——D20 不满足的键追加最多 100 次同进程抽取，观察到 6c 的重数才通过，否则停下；新增 4.4c 节 CP2.2：第 227 个文件按 D20a 判定、续跑第 228–239 个文件、完成降序比较。

下一步：用户批准 D20a 后由 Codex 执行 CP2.2。本轮没有模块代码改动或安装。详见 CHANGE_LOG §22。


### 2026-11-14 CompileRepair CP2.2 本机验收完成（修改 AI：Codex）

在 compile-repair 工作树 pull --ff-only 后起始 HEAD=36c6109fa9271608feb8f4634eca6ab7ff6a192a，完整读 PROMPTS r2.10、指定交接/决策/CHANGE_LOG §21/22 与 cp2_1_review_v1/README。先记录 D20a 授权和基线，新驱动仅写 cp2_2_v1，正式结果 cp2_6c_v3/cp2_desc_v1；生产 14 文件、测试和旧产物不改。本文第 0–5 节同步为本轮当前状态、环境边界、完整结果与证据入口，第 6 节旧文逐字保留。

6c 合计 239/239：234 精确、4 D20、1 D20a。第 227 追加第 1 次观察到参考重数即停，前 227 主样本全部复用；其余 12 在新进程按原序运行，第 239 再取固定 10 次满足 D20。本轮新增 23 次抽取，独立只读复算确认。12 个 L1 DEF 波动键中 5 继承/7 非继承，全部计数与行源码已报告。

生产降序 843 成功/3 既有 Slither 侧失败；229 同版、614 不同版，843/843 key5+有序 IR 同；length 差 28 只诊断。两新 tar 的 57/4229 个成员回读均通过。D20a 已定，旧 D20 停止记录不回写，有限样本不证明全局确定性；没有实施方案外调整。

production 测试 585/6、mando 147/444、DFG 2653 passed/9 既有 warnings，11 个边界检查通过。doc_check/保护审计按强制要求完成后本地提交，提交号见 git log，不自动 push；没有安装、下载依赖/语料/文档、LLM、训练、GPU 锁或全局 solc 操作。下一步独立审查 CP2.2，CP3 尚未开始。

CP2.2 最终检查补记（修改 AI：Codex）：8 份文档 doc_check v1 通过，补记后的 v2 见 cp2_2_v1；frozen_audit 确认生产 14 文件、28,512 保护跟踪文件、17,315 旧 seal 成员、239 源路径、354 DFG 引用、96 solc 及两环境元数据全部未变。旧历史保留，git diff --check 通过；按精确交付清单本地提交，未 push。


### 2026-11-17 CompileRepair CP2.2 审查与方案 r2.11（修改 AI：Claude）

用户要求审查 Codex 完成的 CP2.2（提交 0e6830edc）。新增证据目录 `artifacts/cp2_2_review_v1/`，修改 `PROMPTS.md`（r2.10 → r2.11）。本文开头、第 0、1 节换成审查结论，第 4 节第 15 条更新，第 5 节加入证据路径。

结论：CP2.2 成立。降序 843/843 节点 key5、IR、边与调用相同，graph.json 只在 28 个文件的 87 个节点 length 上不同；6c 续跑的重放侧计数、SHA 与第 239 个文件的逐键计数和记录一致，第 239 个文件的两个波动键在 Claude 的 Slither 0.8.0 环境中同进程 30 次独立复现（`result` 出现 7 次、`b` 缺失 9 次）。6c 参考报告只在用户本机，参考侧数字未独立复核。

新发现两个缺陷：版本区间读取先用 MANDO 时代的 tree-sitter 语法解析整个文件，19 个特性夹具中 5 个解析失败；读取前要求 UTF-8，注释含 Latin-1 字节的合约同样被拒。这些文件 solc 与生产 Slither 都接受，模块却记为 unsupported_version_constraints。缺陷自 CP1 起存在，此前审查没有发现。新增 4.4d 节 CP2.3 修复；CP3 的诊断前提按实测修改。

下一步：Codex 执行 CP2.3，Claude 审查后进入 CP3。本轮没有模块代码改动或安装。详见 CHANGE_LOG §24。


### 2026-11-17 CompileRepair CP2.3 本机验收完成（修改 AI：Codex）

在 compile-repair 工作树 pull --ff-only 后起始 HEAD=361772f74b28b4dce0ad094907dc3dbf27a17794，先读共享上下文再通读 PROMPTS r2.11 及当前记录/审查证据。先写基线和复现，再仅修改 environment.py、pipeline.py；新增一个测试文件与六个夹具，生产文件仍 14。本文开头与第 0–5 节已同步当前状态、边界、证据和下一步，第 6 节旧历史逐字保留。

旧缺陷 6/6 复现，直接工具对照 9/9 成立；两个环境各 846 输入与 28 可解析夹具等价，9 个新 CLI 正例成功、1 个负例按预期拒绝。v5 全量 843 成功/3 已知失败，846 记录字段与 v3 同、843 图字节同；原图与旧存储不改。新存储 4,229 成员和探针存储 58 成员无损打包、哈希回读相同，详见 CP2_REPORT 与 CHANGE_LOG §25。

没有改变冻结约束语义、D3/D5/key5、settings 或已定决策，6c 不重放。基线初次选到历史首次 seal 的问题，按原 README 指定的 seal_v2 验证后解决，未改旧文件或放宽验收。并集 pragma 与 Slither 超时继续留 CP3；本机验收通过仍待独立审查，CP3 未开始。

production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings。强制记录、doc_check 和最终保护检查后本地提交，实际提交号见 git log，不自动 push；没有安装/下载、LLM、训练、GPU 锁、全局 solc 或网络配置变更，费用 0。最终检查结果在本段后补记。


最终检查补记（2026-11-17，修改 AI：Codex）：首次 frozen_audit.json 的实现指纹项未通过，原因是新收集的证据包含旧 settings 测试手工创建的 6 个空实现指纹 seal（code_commit=test），并非生产代码差异。test_seal_diagnosis.json 逐条列出；保留首次结果和 audit_frozen_initial.py，审计明确验证恰好这 6 个手工 seal，再核对全部 3 个真实 CLI seal 的 14 文件指纹，最终 frozen_audit_v2.json 全部通过。测试、生产代码与正式回归没有重跑或修改，未改变验收标准。其余保护项两次均通过：28,574 受保护跟踪文件（模块外 27,845、旧产物 668、旧夹具 30）、21,599 旧结果成员、239 原始目标、354 DFG 引用、96 solc 文件与两环境元数据集合/内容（production 145、mando 118）均未变；12 个非目标函数 AST 保持，生产文件仍 14 且仅两份获授权修改，测试与 v5 实现指纹相同，文档旧历史保留。

doc_check v1 的 7 份文档全部通过；本补记与新目录说明更新后的最终复检记录在 doc_check_v2.jsonl 和 doc_check_v2_invocation.json。git diff --check 已通过。按精确 delivery_inventory 暂存并核对字节后本地提交，不 push；CP2.3 本机验收完成，独立审查尚未进行。


暂存检查补记（修改 AI：Codex）：首次 git diff --cached --check 指出新 v5 README 文件末尾多一个空白行，记录于 staging_attempt1.json。只删除该冗余换行，正式存储/tar 与生产代码字节不变；前一版 evidence_seal.json 保留为文档格式整理前的快照，最终交付使用 evidence_seal_v2.json 和 delivery_seal.json。处理已登记 development_issues，七份文档最终再检结果见 doc_check_v3；提交前重新核对全部暂存字节与空白格式。


### 2026-11-17 CompileRepair CP2.3 审查与方案 r2.12（修改 AI：Claude）

用户要求审查 Codex 完成的 CP2.3（提交 76a2cc810）。新增证据目录 `artifacts/cp2_3_review_v1/`，修改 `PROMPTS.md`（r2.11 → r2.12）。本文开头、第 0、1 节换成审查结论，第 4 节第 11 条补注，第 5 节加入证据路径。

结论：CP2.3 成立。复制的求值与冻结函数逐行相同；原实现能读取的 1,646 个文件中区间与补丁区间全部相同，MANDO 846/846；v5 与 v3 的 846 个记录与 843 个图字节相同；9 个 CLI 正例成功、`||` 负例不调用编译器。Codex 记录的四个执行问题都只涉及记录过程，处理得当。

审查新写 10 个边界合约，发现两个继承自冻结语义的同类遗留：pragma 内含注释时模块拒绝而 solc 接受；缺分号的 pragma 与 `||` 的异常信息相同，CP3 无法区分。另登记测试可移植性（6 个模块在本机之外收集失败，既有）。新增 4.4e 节 CP2.4。

下一步：Codex 执行 CP2.4，Claude 审查后进入 CP3。本轮没有模块代码改动或安装。详见 CHANGE_LOG §26。


### 2026-11-17 CompileRepair CP2.4 完成（修改 AI：Codex）

在 compile-repair@7e32d85c6d02049fd606a9410759dbfb9f18fb7a 开始，pull --ff-only 为 Already up to date，先读共享上下文和 PROMPTS r2.12 全文、HANDOVER §0–5、DECISIONS、CHANGE_LOG §25/26 与审查 README/edge_cases。生产只改 environment.py 两函数，共 +5/-4 行，生产文件仍为 14；新增三个 pragma_comments 夹具与 test_pragma_comments.py，旧 test_pragma_bytes.py 精确登记新注释夹具的冻结异常边界。所有新证据写 cp2_4_v1，旧产物/语料/scripts 不变。本轮更新本文开头、第 0 节摘要、第 1 节状态、第 2 节起点与批次、第 3 节环境依据、第 4 节当前边界、第 5 节关键路径；此前第 6 节原字节保留。

旧模块拒绝两类 solc/Slither 可接受注释输入、且缺分号与 union 消息相同，均已复现。修改后两注释生产 CLI 成功（0.8.0/0.5.0）并保持源码原字节；两种拒绝消息正确且不调用编译器。两环境各 846 MANDO 与 35 个 CP2.3 可读取夹具的区间、完整补丁与 EnvironmentPlan 八字段全部相同，升降序共每环境 1,762 份计划；四个旧拒绝输入明确单列。证据见 equivalence.json、cli_acceptance.json，CLI 归档 21 成员回读一致。

r2.12 明确要求的有意偏离已记入 DECISIONS；既有决定状态、失败标志和策略不改。没有新的替代方案或验收偏差；开发文件访问处理与测试例外说明已记录于 development_issues.json、CHANGE_LOG §27。六模块测试可移植性、union 和 Slither 超时仍是既有后续事项，不提前实现。停止于本机验收完成、待独立审查；CP3 尚未开始。

production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG 2653 passed/9 warnings；完整命令和耗时见 pytest_*.json。六份文档按 doc_check 核验，最终结果及完整性记录见 doc_check_v*、frozen_audit.json；强制记录通过后本地提交，提交号见 git log，不自动 push。无下载、安装、LLM、训练、GPU 锁或全局 solc/网络改动。按 §4.4e 不重跑全量生产，6c 已完成且不重放。


### 2026-11-17 CompileRepair CP2.4 审查与方案 r2.13（修改 AI：Claude）

用户要求审查 Codex 完成的 CP2.4（提交 9fdc96e13）。新增证据目录 `artifacts/cp2_4_review_v1/`，修改 `PROMPTS.md`（r2.12 → r2.13）。本文开头、第 0、1 节换成审查结论，第 4 节第 12 条补注，第 5 节加入证据路径。

结论：CP2.4 成立。与 CP2.3 在其能读取的 1,656 个文件上区间与异常信息全同，补丁区间 1,661/1,661 全同，MANDO 846 个输入的 make_plan 升降序 1,692/1,692 全同；CLI 验收存储的 seal 与调用记录核对一致；审查环境 34 个测试通过，1 个失败是已登记的本机路径依赖。缺分号的 pragma 后接 import 或 pragma 时，模块与 solc 都把两行读成一条 pragma，读法一致，不改代码，只在 CP3 分类中单列。

CP3 提示的修正：第 2 节原写“standard-json 输入组装”，与 r2.11 对 standard JSON 的实测矛盾，改为与单文件相同的命令行路径，参数同时传给 solc 与 crytic-compile。

下一步：Codex 执行 CP3。本轮没有模块代码改动或安装。详见 CHANGE_LOG §28。


### 2026-11-17 CompileRepair CP3 前置核查，停在获取授权（修改 AI：Codex）

在 compile-repair@0d39c3546dbb8d456ef7c2fd5534143dcef92c94 开始，pull --ff-only 已同步。按最新用户指令执行 CP3，先读取共享上下文与最新 r2.13/交接/审查，再核查资料。新增 CP3_REPORT 和 cp3_preflight_v1，本文第 0–5 节全部更新为当前待授权状态、环境、边界与关键路径；第 6 节旧记录逐字保留，生产代码/测试/旧产物不变。

指定本地位置未找到官方文档与三套语料，故依据 §4.5 第 0、1 节形成精确获取请求。十份文档 188,817 字节、三语料指定目录 235,835,756 字节，均由固定 Git tree 元数据估算；DAppSCAN 608 项目/21,457 .sol、Trace 5,000 / 83 项目 3,092 .sol / 15 的目录计数与旧证据一致。源码 SHA256、import、pragma 与 SOChecker input 内容数量未核验，未创建 taxonomy 或执行 CP3 探针，不能记为 CP3 通过。

authorization_request.json 明确 pending_user_authorization，费用上限 0 美元，完整提交/路径与本地研究使用范围待用户批准。DAppSCAN 元数据截断通过限定完整子树解决，Solidity 仓库迁移通过 repository id 确认同一来源；没有方案替换。没有新决策状态变化，DECISIONS 不改；后续批准先保存用户原话与请求 SHA256，再获取并按 CP3 原顺序推进。

既有 production 模块 622 passed/6 skipped、mando 模块 181/447、DFG v2 2653 passed/9 warnings，收据在 pytest_* 和 test_acceptance.json。完整性和文档检查结果见 CHANGE_LOG §29.5 及批次收据，通过后按精确清单作本地提交，不 push。没有下载官方正文或语料、安装/升级、LLM、HGT、GPU 锁或全局 solc 修改；停止在明确获取授权门槛，CP3/CP4 的后续前提尚未满足。


### 2026-11-17 CP3 续：资料获批获取，SOChecker 子集差异后停止（修改 AI：Codex）

在 compile-repair@88b499e7 上承接同一 CP3 任务的用户授权，依据 PROMPTS r2.13 §4.1/§4.5、新旧交接和决策实施。新增 cp3_v1、三个 cp3_project 手写夹具，生产代码及14个生产文件保持；前置批次和旧产物不改。已更新本交接 §0–5 的全部当前状态、授权、停止原因、必读项与路径，旧 §6 历史保持并追加本段。

资料授权先落盘再下载，10文档/188,817字节、29,611语料文件/235,835,756字节全部身份和哈希通过。初表29类/125条变化先于内容统计；三文件四版本 solc/production Slither/D3及三文件映射4/4通过，证据在 cp3_v1。DAppSCAN与Trace的历史结构计数相同；SOChecker三份897条完全同序，ours+GPT846条严格子集少51条，触发获批请求的内容不一致停止条件。

用户原话“批准全部资料，仅本地研究使用（推荐）”已记 authorization 与 DECISIONS；当前授权未撤销。待确认建议是保留原定 ours.json 897条唯一分类输入，846条附属子集只记录来源差异，不合并、不去重；未擅自实施该建议。通用分类器/闭包、语料编译统计和其余CP3前提探针未完成，CP3未验收。

本轮规定测试由 run_checks.py 执行，最终结果见 test_acceptance 与下方终审补记；文档及保护核验收据在 cp3_v1。完成全部记录与检查后只本地提交，没有push。没有安装/升级、额外资料/编译器/库下载、全局solc修改、LLM、HGT训练或GPU锁操作，费用0美元。


本轮终审补记（Codex）：production 622/6、mando 181/447、DFG 2653 passed/9既有warnings；六份doc_check v1通过，补记后以v2收据为准。冻结审计确认28,779个保护跟踪文件、25,828个旧封存文件、354个引用、96个编译器、两套环境及14个生产文件不变；29,611份语料文件和10份文档哈希保持。SOChecker差异仍待确认，CP3未完成，仅本地检查点提交。收据数字解析的转义错误已在development_issues记录并从既有日志纠正，无测试重跑。


交付补记（2026-11-17，修改 AI：Codex）：暂存后的 git diff --cached --check 报告三份 Git init 原始 stderr 的提示行尾空格，以及 solc 0.8.38 原始 stderr 的末尾空行。为保持取证原字节，未修改四份日志或已封存 cp3_v1；仅将这四个精确日志路径排除后，其余全部文件的同一空白检查通过。该处理不排除代码、文档或任何CP3验收项；SOChecker的结构差异仍为未通过。

另建 artifacts/cp3_delivery_v1 保存原始报错、四日志SHA、检查命令和上次doc_check对应的文档快照。最终文档检查与提交清单改以该交付批次的 doc_check_final_invocation.json、delivery_inventory.json 为准；cp3_v1/evidence_seal.json 原样保留。没有重跑编译或测试，也没有改变生产实现、授权范围或待确认建议；本地检查点提交后仍等待对846/897子集差异的处理确认。


交付终检补记（修改 AI：Codex）：七份 doc_check_delivery_v1 全部通过；本条补记后再次检查的最终文档哈希见 cp3_delivery_v1/doc_check_final_invocation.json。四份原始工具日志按精确路径保留并豁免空白检查，其余文件检查通过；编译验收和 SOChecker 待确认状态均未改变。

### 2026-11-17 CompileRepair CP3 续做暂停（修改 AI：Codex）

本轮从 compile-repair@dc6c5fb4 承接 PROMPTS r2.13 §4.5，接受用户对897条SOChecker输入的处理确认。实现诊断分类、项目闭包、统一管线、项目文件名+key5及片段判定/统计，生产模块16个。当前区0–5全部更新：状态、必读、关键路径、两个已定授权、新待确认问题、部分运行与未提交边界；第6节旧历史保持原文。

29类、125条breaking changes保留，92版诊断格式边界为0.6.0；手写tuple、重复声明/指令和codegen前提已测，详见cp3_continue_v1。31,071条完整运行序列中872条已记录完成，另1条中断；599个旧D3成功不是新的图语义验收。原始数据留仓库外，第二段受控中断现场有逐文件哈希，未伪造正常seal。

用户已批准来源差异和项目文件身份。新alias_call_probe证明原生Slither对不同文件同名合约类型错绑，原D3仍通过；新增项目绑定检查已请求但尚未实施，不能靠序列化纠正。按§4.1停止全量，不自动重试，不将新增失败测试改为通过。

完整production714/6、mando268/452、DFG2653passed；后续项目补验24passed/1failed。最终doc_check、范围保护核验见后续补记及收据。当前不满足全部通过后提交的条件，未提交本批次、未push；无新下载、安装、LLM、训练或GPU锁，0美元。


交付检查补记（2026-11-17，修改 AI：Codex）：六份 doc_check_v1 全部通过；frozen_audit 检查28,908份保护跟踪文件、25,828份旧封存文件、354项code refs、96份编译器文件、production/mando的145/118份环境元数据、29,611份语料和10份文档，均未变化。生产文件16个，历史文档字节段保留。tracked git diff --check通过，新增代码/文档无空白问题；仅322份逐一列明且SHA固定的原始工具输出保留其原空白，见whitespace_review，不豁免代码或验收项。本条追加后的最终doc_check收据为doc_check_final_invocation.json。上述记录和范围检查不代表新增绑定测试通过；24passed/1failed与待确认状态保持，本批次未提交、未push。
