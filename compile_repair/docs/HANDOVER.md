# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.9（§1.12、§4.4、§4.4b CP2.1）、CP2_REPORT、DECISIONS 与 CHANGE_LOG §19、§20。第 6 节历史只追加，记录规则见 README.md。

## 0. 一句话

CP2 的生产部分已由 Claude 独立复核成立；发现空体 if 的边种类缺陷（86 个节点）。6c 重放的停止经审查证明来自 Slither 0.8.0 局部写集合本身不确定，不是本模块的问题。下一步：用户批准 D20 → Codex 执行 4.4b 节 CP2.1 → Claude 审查 → CP3。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案与决定 | PROMPTS r2.9；D5/D16/D18 已定；D19 建议；D20（6c 稳定事实判据）待用户批准；D9/D10 待确认、D12/D13 待定 | PROMPTS、DECISIONS |
| CP0–CP1.1 | 已审查通过 | 各审查目录 |
| CP2 生产 | 已复核：两次全量 843 成功 + 3 已知失败，图字节 843/843 相同，同版本 842/842 相同，LibraryCall 误分 0，悬空引用 0 | artifacts/cp2_review_v1/README.md |
| CP2 图缺陷 | 空体 if 的两条边都标 true（86 个 IF、40 个文件）；CP2.1 修复并重跑 | if_edge_kinds.json |
| 6c 重放 | 87 个中 86 相同；buggy_43.sol 的差异来自旧工具链不确定（同一进程 10 次得到 252/253/254）；CP2.1 用稳定事实判据完成 239 个 | PROMPTS 1.12、4.4b |
| 降序跨版本 | 未运行；CP2.1 完成 | PROMPTS 4.4b |
| 已知缺口 | `||` pragma；Slither 进程内无超时；项目与依赖等未实现 | 留 CP3 |
| 下一步 | 用户批准 D20 → CP2.1 → 审查 → CP3 | PROMPTS §4.4b |

## 2. 分支与工作树

/home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair；本轮 pull --ff-only 从 27aa46fe 快进至 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18。强制记录与检查后本地提交 CP2 停止现场，准确提交号看 git log；不自动 push，不在 EdgeSem 执行 git。

修改仅 toolchain/slither.py、pipeline.py、cli.py、tests/test_pipeline.py，新增 tests/test_graph.py、tests/fixtures/graph_calls.sol 与四个 CP2 批次和文档。原 CP0–CP1.1 报告/产物、PROMPTS、原 fixture、scripts、语料与环境不改。正式 store.tar.gz 无损交付，散文件仅留本地；按 delivery_inventory 精确暂存，禁止递归 force-add 旧树。

## 3. 环境

从本工作树根运行。production 环境 /home/zhao/miniconda3/envs/compile-repair-production 为 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2；mando 为 Python 3.7.12 / 0.8.0 / 0.2.4，仅冻结回归与相应测试。PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。

96 可信 solc = 92 支持 + 4 历史，既有安装/哈希/全局选择不变，不运行 solc-select install/use。完整实际命令见报告与 *_invocation/plan；当前停止状态只读查看归档，不自动重跑。需要新安装/下载时停止，网络只走既有代理。

## 4. 必读事项（当前边界）

1. 任意检测输入是模块目标，MANDO 846 只作回归；类别目录只用于统计，不作选版或漏洞判断。
2. D3 全声明/修饰器/顶层函数映射及 AST 合约覆盖不变；key5 保留序号/重数、length 只记录。CP2 图不用于 6c 精确重放。
3. D5 已知版本优先、系列内升序、耗尽后下一系列；无 pragma 只用有出处特征。MANDO 配置才启用已批准 metadata 与 0.4.25 默认。不得另建选版逻辑。
4. 同版本默认设置失败并命中规定错误才重试 cancun/via-ir，再换版；regression_6c 拒绝非空设置、只 import 冻结函数。保留原报告 target，从本仓库根运行，239 原源码身份已核验。
5. CP1.1 路径组件判断、单输入 solc 超时后续行、无 Git 时 commit=null + 实现 SHA 已审查；不重做。Slither 进程内超时尚未解决。
6. 0.4.12 下限保持；只有区间内无可用编译器才可原规则的等长 pragma 覆盖。D19 仍建议，三个旧 Slither 失败与 CP6 第 10 行改写未处理。
7. 用户“允许单列既有下限差异，记录后继续”只适用于与 6c 的选版归因，CP0 三类、D3、239/239 不变，见 attribution_authorization。
8. buggy_43.sol 旧 252/本次 251 occurrence，仅 Post 继承上下文循环条件 i < 32 的 out DEF 缺失；完整原始行离线比较也只有此项。SSA/继承原因未证明，不写成确定根因。
9. 正式运行已停；剩余 152、降序、CP3 未运行。没有重试、改键、丢事实或改旧 seal；先审查，需新执行或调整时先给具体建议并咨询。
10. result_check 在当前清单 flush 后验收，不参与选版，异常停止封存；graph_facts 异常不能变成成功空图。原输入只读，副本改动与 provenance 对应，输出拒绝覆盖。
11. 图不含时间/绝对文件路径，身份存 manifest。两次 graph 字节一致不要求整个 manifest/seal 一致；失败单元没有节点/图。
12. 两份生产 tar 各 4,229 成员、6c 停止 tar 93 成员，回读全部通过；原散文件与 /tmp 测试树不删。evidence_seal 是授权前快照，最终交付用 delivery_seal/inventory。
13. EdgeSem 读取范围沿用授权，固定 6c 报告/seal 先校验 SHA；不复制/移动/修改旧结果，不执行 git。本轮无新增 EdgeSem 读取授权。
14. 根交接与 training_changes 不改，模块记录在 docs，中途停止也完成五项记录。源码、旧语料/标签/图/模型全部保护。
15. Windows 用 scoped WSL 与 UTF-8/base64 Python；缺 rg 用现有工具。code_refs 用已有 mando，不为辅助检查安装包；长文档拆短命令。

## 5. 关键路径

| 内容（compile_repair 下） | 路径 |
|---|---|
| CP2 审查证据（Claude） | artifacts/cp2_review_v1/README.md 及 verify_cp2、if_edge_kinds、legacy_*、production_repeat_in_process |
| 完整报告、训练改变记录 | CP2_REPORT.md；docs/CHANGE_LOG.md §19 |
| 新证据入口 | artifacts/cp2_development_v1/README.md |
| 正式生产图 | artifacts/cr_store_mando_v1/store.tar.gz；cr_store_mando_v2/store.tar.gz |
| 停止现场 | artifacts/cp2_6c_v1/store.tar.gz 内 comparison.jsonl、extractions/0087.json.gz、summary.json |
| 差异定位与批准 | cp2_development_v1/replay_discrepancy_analysis.json；attribution_authorization.json |
| 源码身份、分布与版本 | historical_source_path_audit.json；cp2_summary.json；ascending1/2_acceptance |
| 测试与最终检查 | pytest_*；frozen_audit；doc_check_v*；delivery_seal/inventory |
| 已审查结果（只读） | artifacts/cp1_review_v1/README.md；cp1_1_review_v1/README.md |
| 可信编译器与生产归档（只读） | cp0_v2/recon.json；cp0_1_compilers_v1/trusted_compilers_addition.json；cp0_1_env_v2/production_run1_node_facts_v2.jsonl.gz |

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
