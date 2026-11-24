# CompileRepair 交接文档

> 本轮先读第 0–5 节、CP5_REPORT.md 的 CP5.2 节、CHANGE_LOG §59 及 artifacts/cp5_2_v1/README.md。

## 0. 一句话

CP5.2 完成验收，v2 移动样本 363/400 通过 D3、359/400 达到 exact，950 个包装样本全部达到 exact。全量外部语料 5882/9,138 通过 D3。下一步为 CP5.2 审查，部分 IR 是否纳入 D3 由用户决定。

## 1. 当前状态

| 项目 | 结果 |
|---|---|
| 方案与决定 | PROMPTS r2.24；D22–D24 用户已定；D25 待定（CP5.2 测量后）；D19 建议；D9/D10 待确认、D12/D13 待定 |
| CP0–CP5 检查点 | 已审查通过 |
| CP5.1 | 审查成立部分见 1.27 节；留五个问题由 CP5.2 解决 |
| 已知限制 | declaration_error 0 纳入；创建码哈希常量；每包至多 12 个代表发布版；test_cp5*.py 依赖用户本机编译器目录 |
| 分支 | 继续在 compile-repair；5080 主线上的导入改动迁移时再合并 |
| CP5.2 | 313 项漏修归因、有限链、文件评分及部分 IR 测量完成，843 个 MANDO 图等于 v5 |
| 下一步 | 审查 CP5.2，用户评估 D25，然后按计划开展 CP6 |

## 2. 分支与工作树

专用工作树 /home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair。本轮从 06ad69c2 开始。新证据在 compile_repair/artifacts/cp4_v1/，外部源码副本和完整工具收据在 /home/zhao/SmartContract/compile-repair-local/cp4_v1/。首次运行与两次限定续跑各有独立目录或收据。

CP4.1 从 e8ec530d 开始。续作以 0f690e6f 为检查点，新结果在 artifacts/cp4_1_v1/migration_continuation/。逐项完整编译、图和 solc 原始输出在仓库外 compile-repair-local/cp4_1_v1/。

CP4.2 输入提交 30df6664，证据目录 artifacts/cp4_2_v1；完整工具输出和图在同级仓库外 compile-repair-local/cp4_2_v1。

CP4.3 起点为 09a8355e。新批次在 artifacts/cp4_3_v1，真实夹具及临时测试目录在同级仓库外 compile-repair-local/cp4_3_v1。

CP4.4 以 8739c653 为基线。新结果在 artifacts/cp4_4_v1，真实手写夹具和工具输出位于同级仓库外 compile-repair-local/cp4_4_v1。

CP4.5 从 c8ca807a 开始。首轮及逐项差异证据在 artifacts/cp4_5_v1；最终重验在其 continuation 子目录。

CP5.1 从 `5fe7671f` 开始。新证据在 `artifacts/cp5_1_v1/`，语料、离线索引和编译工作副本见该批 README。

CP5.2 基线为 fba94f1d，使用独立 compile-repair 工作树，证据及续作均位于 artifacts/cp5_2_v1。

## 3. 环境

生产采用 Python 3.10、Slither 0.11.6、crytic-compile 0.4.2 和 92 版本 solc 快照。mando 的 Python 3.7、Slither 0.8.0 承担兼容与 DFG 测试。工具身份以 execution_settings.json 及前序授权信任清单为准。CPU 本地执行，费用 0 美元。

2026-11-22 美东 08:34 的检查定位到 Hyper-V 新通道的 512 KiB 连续物理内存分配失败。原有用户会话保留。09:28、09:34 与 09:44 的独立新命令均返回 UID 1000，耗时分别为 0.356、0.402、0.305 秒。详见 runtime_recovery.json。晚间同类超时曾复发，已有 Bash 完成了生产和回归。美东 21:20 的四次独立新命令分别耗时 0.344、0.343、0.312、0.359 秒。晚间诊断和临时内存整理收据在 migration_continuation/wsl_recovery.json。

CP4.2 在两个既有 Python 环境执行。三个最终套件的命令与结果在本批 final_tests 下。

CP4.3 手写夹具使用现有 production 环境的 solc 0.8.38、Slither 0.11.6 和 crytic-compile 0.4.2。200 项移动、14,196 项精确还原和 114 项迁移只复算评分。

CP4.4 用既有 production 环境的 0.8.38 编译器生成审查夹具。历史对比直接读取原图，模块和 DFG 回归的完整命令位于本批 suites。

CP4.5 历史核验只读已封存的图；手写夹具回归运行于既有生产环境，mando 执行另一组模块回归及 DFG v2。

CP5.1 在生产环境运行 solc、Slither 及基准。归档传输固定使用已有 WSL 代理，补传的停点及离线配置验证见 `guard_stop.json`。模块与 DFG 套件的命令和版本见 `checkpoint_audit.json`。

CP5.2 的 18 个生产文件在三套回归前后逐项核验。WSL 恢复和实测代理保护的依据在本批 network_recovery.json 与 launcher_continuity.json。

## 4. 必读与下一步

复核先核对 CP4_REPORT.md、seal.json、archives.json 和三个授权文件。用 sample_plan.jsonl.gz 与 sample_receipts.jsonl.gz 按算子和单元匹配。对照检查原版本、设置和图，评分用首轮通过的 4,315 行及 identity_continuation 的 7,543 行。抽查 cp3_23979 的原始 IR 差异和同路径探针，确认评分保留了完整 metadata。后续开发使用 dev，test 只用于报告。此前的 D21、AST 不足和语言未定等限制仍记在 CP3_REPORT.md。（2026-11-22 Claude 更新：CP4 审查发现四个问题，CP5 之前执行 CP4.1，见 PROMPTS §4.6b。）

本次审查先读 CP4_REPORT.md 的最终验收与 migration_continuation/README.md，再按 acceptance.json、packages.tsv 对回各阶段的通过行。抽查 cp3_03927 的元组使用、cp3_00706 的两份源文件清单和 AST、cp3_15161 的数组分配定义，并核对 8 个先尝试两版再成功的项目。

审查先读 acceptance.json 和 CP4_REPORT 的 CP4.2 最终表，抽查 measured_differences.json 及 moves_completed.jsonl，再核对四份授权与检查点。

复核 CP4.3 时先按批次 README 只读核对封存哈希，再查 fixtures.json 内的两个分母、Yul 位移与错一字节的反例。对照 moves 中的 cp3_00291、cp3_21529，核验主指标、存活指标以及已知限制。

审查 CP4.4 时按 README 核验封存哈希；查看 review_scores.json 和 fixture_facts.json 中每个场景的参与与退出节点；最后对照 moves_summary.json 的原停点、movement_difference.json 的三个节点与一个调用，以及用户随后确认的范围。

CP4.5 复核先查两份授权、comparison_stop_seal 与最终 acceptance，再检查三个旧名节点的身份、删除与数组写入的绑定证据及三组完整重算。

CP5.1 复核先读 `CP5_REPORT.md` 的 CP5.1 一节与新批次 README。按 `index_verification.json` 核对索引，再查 `population.json`、`path_census.json`、`moved_summary.json` 和开发集的选版证据。

复核 CP5.2 时先看 acceptance.json、diagnosis_details.json、v2_scoring_details.json 和 IR 的四个分母，再核对 D25 的决策范围。v2_scoring_details.json 位于本批 continuation 下。

## 5. 关键路径

| 内容 | compile_repair 下的位置 |
|---|---|
| CP5.1 审查证据（Claude） | artifacts/cp5_1_review_v1/README.md、outcome_tallies.json |
| CP5.1 代码、实验与传输停点 | CP5_REPORT.md 的 CP5.1 节、artifacts/cp5_1_v1/README.md、docs/DECISIONS.md |
| CP5 检查点审查证据（Claude） | artifacts/cp5_review_v1/README.md、combination_bound.json |
| CP5 检查点 | CP5_REPORT.md、artifacts/cp5_v1/README.md、checkpoint_audit.json、d23/transport_stop.json、optimizer_request.json |
| CP4.5 审查证据（Claude） | artifacts/cp4_5_review_v1/README.md、rerun_review_probes.json |
| CP4.5 | artifacts/cp4_5_v1/README.md、comparison_stop_seal.json、continuation/、acceptance.json、seal.json |
| CP4.4 审查证据（Claude） | artifacts/cp4_4_review_v1/README.md、probe_stale_name.json |
| CP4.4 报告、批准与最终验收 | CP4_REPORT.md、artifacts/cp4_4_v1/ 的 README.md、acceptance.json、acceptance_authorization.json、movement_difference.json、scope.json、doc_check.json、seal.json |
| CP4.3 审查证据（Claude） | artifacts/cp4_3_review_v1/README.md、probe_partial_change.json、probe_yul_switch.json |
| CP4.3 报告与验收 | CP4_REPORT.md、artifacts/cp4_3_v1/ 的 README.md、acceptance.json、fixtures.json、scope.json、doc_check.json、seal.json |
| CP4.2 审查证据（Claude） | artifacts/cp4_2_review_v1/README.md、probe_repair_deletes_kept.json |
| CP4.2 最终验收与停点证据 | artifacts/cp4_2_v1/README.md、acceptance.json、seal.json、measured_differences.json、exact_summary.json、migration_summary.json、checkpoint_79.json、final_tests/ |
| CP4.1 审查证据（Claude） | artifacts/cp4_1_review_v1/README.md、probe_counter_shift.json、struct_copy_bin.json |
| CP4.1 最终验收与封存 | artifacts/cp4_1_v1/migration_continuation/ 下的 README.md、acceptance.json、packages.tsv、final_scope.json、doc_check.json、seal.json |
| CP4.1 最终生产、mando 与 DFG 回归 | 同批 definition_continuation/suites/ 下的三组命令、日志与结果 |
| CP4.1 全量触发与缺包迁移 | artifacts/cp4_1_v1/population.json、operators.tsv、migration_stop_inventory.json、migration_counter_review.json |
| CP4.1 代码、测试与 WSL 恢复 | 同批 migration_stop_scope.json、final_tests/、runtime_recovery.json |
| CP4.1 清点、授权、启动故障 | artifacts/cp4_1_v1/old_other_templates.json、preflight_authorization.json、authorization.json、wsl_startup_diagnosis.json |
| CP4 审查证据（Claude） | artifacts/cp4_review_v1/README.md、probe_operator_messages.json、fixtures/ |
| CP4 报告、逐类分层与复现 | CP4_REPORT.md、artifacts/cp4_v1/README.md、strata.tsv、benchmark_counts.json |
| CP4 样本与真值 | 同批 bases.jsonl.gz、base_exclusions.jsonl.gz、sample_plan.jsonl.gz、sample_receipts.jsonl.gz、controls.jsonl |
| CP4 评分与授权 | 同批 authorization.json、relocation_test_authorization.json、restoration_identity_authorization.json、inverse_acceptance.json、identity_continuation/、wrong_repairs.json、analyzer_history.json |
| CP4 核验与交付 | 同批 acceptance.json、archives.json、seal.json、doc_check.json |
| CP3.2 审查证据（Claude） | artifacts/cp3_2_review_v1/README.md、probe_language_adversarial.json、probe_language_real.json |
| CP3.2 依据与授权 | artifacts/cp3_2_v1/input_gate.json、decision_request.json、authorization.json |
| 三态结果与来源 | 同批 language_classifications.jsonl.gz、replacement_provenance.json、unit_attributions.jsonl.gz、unmeasured.jsonl.gz |
| 最终统计与验收 | 同批 failure_summary.json、non_solidity.json、version_blockers.json、d6_cp4_final.json、verification.json、doc_check.json、seal.json |
| CP3.2 报告与记录 | CP3_REPORT.md 的 CP3.2、docs/CHANGE_LOG.md §39 |
| CP3.1 审查证据（Claude） | artifacts/cp3_1_review_v1/README.md、oracle_pragma.json、probe_wrapper_detect.json、trace_parser_units.json |
| 报告、变更与决定 | CP3_REPORT.md 的 CP3.1、docs/CHANGE_LOG.md §37、docs/DECISIONS.md |
| 主因、任一候选及示例 | artifacts/cp3_1_v1/failure_summary.json、unit_attributions.jsonl.gz |
| 逐项替换及 AST 未知 | 同批 replacement_provenance.json、ast_census.json、ast_coverage_authorization.json |
| 包装与版本证据 | 同批 wrapper_scan.json、wrapper_premises.json、pragma_equivalence.json、pragma_matrix_check.json |
| 回归与交付 | 同批 mando_regression_final.json、scope_audit.json、acceptance.json、delivery_inventory.json |
| 旧基线与审查 | artifacts/cp3_paths_v1、artifacts/cp3_review_v1、artifacts/cr_store_mando_v5 |

---

CP5.2 的索引为 artifacts/cp5_2_v1/README.md。完整运行工作副本位于同级 compile-repair-local/cp5_2_v1/，每项压缩记录的哈希见 record_archives.json。

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


### 2026-11-17 CP3 绑定检查批准后恢复（修改 AI：Codex）

用户已批准项目绑定检查，先写新authorization/baseline再实施。生产改三文件，测试保留精确错绑证据并补正常项目用例。定向32、production723/6、mando271/458、DFG2653passed；343项目新验230成功/113未修复，529单文件身份核验后复用。剩余30,199条正在新批次执行；动态点位见progress_checkpoint_v1，未将部分结果称最终。单文件导入统计缺字段的只读补计与两个复核脚本读取错误的处理见CHANGE_LOG §32、development_issues。

本文0–5已更新批准状态、检查范围、已完成测试、续跑安排、后续验收与关键路径；原第6节历史保留。CP3_REPORT、PROGRESS、DECISIONS和CHANGE_LOG同步，不必重复询问现有三项批准。尚未提交、未push；无安装/下载/LLM/训练/全局solc操作，0美元。


### 2026-11-18 CP3 项目绑定检查与完整分类（修改 AI：Codex）

完整清单31,307条，其中SOChecker236条无Solidity声明证据单列；进入固定完整序列31,071条，成功21150、剩余失败9921。529个单文件观察复用，343个旧项目以新批次结果替换，再完成30,199条续跑；每单元只计一次，无抽样。

本轮按用户授权增加项目直接合约类型检查，保留D3并增加graph_usable；错绑/无法核验不存成功图。定向32、production723/6、mando271/458、DFG2653passed；旧检查点与中断现场保持。单文件包统计缺字段通过最终只读、位置与SHA核验补计。更新本文0–5的当前状态、已定授权、运行完成状态、测试、下一步与证据入口；第6节既有历史保留。报告、CHANGE_LOG §32、PROGRESS与DECISIONS同步；最终文档/保护检查后本地提交，未push。没有安装、下载、LLM、训练或全局solc改动。


完整分类文档记录时间：2026-11-18T00:18:10-05:00（America/New_York，EST；依据本次脚本系统时间）。授权日期仍为2026-11-17。


最终复核暂停（2026-11-18，修改 AI：Codex）：完整观测统计已生成，但CP3最终验收尚未通过。11个DAppSCAN项目入口以连字符开头，project_command与slither_arguments原样传入入口；315次solc调用将路径当选项拒绝。该问题属于参数组装，不属于源码损坏，原9,921个剩余失败包含这11项，当前统计仅为修正前观察。具体清单、命令与SHA、限定./前缀方案及新批次11单元重验请求见leading_dash_review_request.json；已向用户询问，尚未修改参数或重跑。当前批次、所有旧产物及其统计保持，修正后应另建批次、仅替换这11条观察，不把现有数字写成最终接受结果。

三套最终无缓存回归均通过，但它们未覆盖本次发现的连字符入口问题，不能据此放行CP3。读取完成收据的自动审批一度超时，按工具允许仅重试一次只读检查后成功；随后WSL新命令暂报Wsl/Service/0x8007274c，使用只读UNC检查并在最小连接探测恢复后继续，没有重启WSL或修改网络。诊断提取首次漏读reason字段，随后只遍历续跑批次得10项；补入项目复验批次后确认共11项。这些是只读提取修正，没有重试编译。


### 2026-11-18 CP3 完整观察与入口参数问题暂停（修改 AI：Codex）


本批次收尾检查（修改 AI：Codex；时间：2026-11-18T00:21:18-05:00，America/New_York/EST）：完整31,071单元观察与两个新运行seal全部核验，复验批次2,385文件、续跑批次193,136文件，运行实现SHA与当前16模块一致。三套最终无缓存回归均通过：production723passed/6skipped（88.344秒）、mando271passed/458skipped（21.392秒）、DFG2653passed/9既有warnings（164.618秒），数据见pytest_*_final_v1.json。定向32passed沿用本轮既有收据，没有再次重跑。

doc_check_v1检查7份正文，全部UTF-8/CJK通过；本次补记完成后以doc_check_v2.json复查最终字节。frozen_audit通过：28,908份受保护跟踪文件、25,828份旧封存文件、753份上一检查点受保护成员、29,611份外部语料文件和10份资料无变化；96个solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither类型解析器SHA保持。文档历史前缀全部保留。这些是分别定义的检查范围，可能重叠，不能相加作为独立文件总数。

全量中34,973条直接合约类型声明被核对；D3为true但新增绑定检查拒绝的调用为0。139次未获绑定认证的项目调用全部属于Slither未构造成功，不能表述为139次错绑；手写alias用例独立证明已知错绑会拒绝图。原D3事实、源码和安装包均保持。

CP3最终验收仍暂停：11个连字符入口被误当solc选项（315次调用），修正请求见leading_dash_review_request.json，尚未批准、未修改project.py、未重验。当前统计为修正前完整观察，不能宣称CP3已完成。按PROMPTS的中途停止记录要求整理本地检查点；提交身份以包含本条记录的CP3提交为准，未push。无安装、下载、LLM、训练、GPU锁、全局solc或网络修改。所有原始数据与本轮新运行证据保留，后续修正须使用新批次。

更新本文0–5为实际完整观察、测试/审计结果、未完成状态与待确认修正范围；第6节既有历史字节保持。


### 2026-11-18 最终记录检查补记（修改 AI：Codex）


2026-11-18收尾检查补记（修改 AI：Codex）：doc_check_v2七份正文全部通过；whitespace_review_v2通过，仅沿用旧批次322份精确SHA绑定的原始工具输出空白，没有新增代码或正文豁免。检查器v1误把git diff --no-index的正常差异退出码1当作空白错误，诊断输出实际为空；已保留v1，v2只修正退出码解释，所有实际空白诊断和异常仍拒绝，没有用v1暂存。该调整不改生产代码、不重跑测试或编译。本文补记后的最终字节由doc_check_v3核验；CP3仍等待11入口参数修正授权。

更新本文第1节检查状态；此前第6节历史保持。


### 2026-11-18 CP3 连字符入口修正已批准，探针初始化停止（修改 AI：Codex）

分支compile-repair，起始e3fb634f，沿用PROMPTS r2.13与本任务已读资料。先写cp3_entry_v1授权及基线，再仅修改project.py共享入口参数；test_project.py新增四版本测试，两文件夹具覆盖相对导入和合约类型调用。旧封存批次、全量结果与原源码保持。本次同步更新0–5节的状态、阻塞、授权、下一步和路径，第6节历史只追加。

用户批准原话“批准限定修正与 11 个单元重验（推荐）”。首次定向命令因Codex脚本漏建临时目录父目录而在pytest初始化失败，0passed/1setup error，无solc/Slither调用，无语料重验；收据为entry_probes.json。准备v2脚本补父目录并换新输出位置，检查内容和门槛不改。依据§4.1无自动重试，已请求仅一次续跑；本条时尚未执行。

当前31,071项与21,150/9,921仍属原观察，不是新验收数字。CP3未完成，本轮完整production/mando/DFG回归、新汇总及11项重验未运行。记录、doc_check和保护审计结果后补，本轮没有安装、下载、LLM、训练、全局solc或网络变更，费用0美元，不自动push。


2026-11-18 停止检查点验收补记（修改 AI：Codex）：doc_check_v1对六份正文及五份原文快照共11份全部通过；本补记后的最终字节由doc_check_v2再次核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、841份上一检查点保护成员、29,611份语料和10份资料均未变化；96份solc相关文件、两环境145/118份元数据、354条DFG代码引用和原生Slither解析器SHA保持。这些检查集合可能重叠，不相加计数。Python3.7语法解析与tracked diff --check通过，记录static_review；这些都是范围/静态检查，不能代替未完成的四版本运行验收。

本轮仍停在探针初始化错误后的续跑确认，没有再次运行pytest、solc、Slither或11单元语料。将按中途停止记录要求提交本地检查点，实际提交号以包含本补记的CP3提交及仓库外提交收据为准，未push。现有失败脚本和输出封存；若用户随后允许续跑，须把已准备且SHA固定的run_entry_probes_v2.py原字节复制到新证据批次执行，维持旧批次只读，不覆盖任何旧文件。该脚本按自身目录写入新证据，并使用新的v2临时目录；测试、版本、条件和原11项批准范围保持。


### 2026-11-18 CP3 一次探针续跑后发现允许路径问题（修改 AI：Codex）

分支compile-repair，起始8900abe8，沿用已读PROMPTS r2.13和本任务资料。先核对879成员并在cp3_entry_resume_v1记录一次续跑授权，原批次保持。执行前发现pytest current符号链接重复收集问题，实际脚本仅过滤别名；原版SHA与执行副本SHA均记录。本轮无生产、测试、夹具改动，0–5节同步当前结果、待确认参数方案、精确范围及证据路径，第6节只追加。

一次pytest结果4passed/1failed/27deselected，普通入口四版本通过；连字符0.4.12在识别./目标后拒绝兄弟目录现存文件。其余三版本与所有语料未运行。只读核对旧31,071结果SHA，另有92项/521次目录拒绝，79后来成功、13未修复；1473条相关路径均位于工作根内。旧全量计数仍不是新验收数字。

建议项目允许目录统一使用根绝对路径，补丁未应用；保留原八项再加四项普通嵌套入口检查，通过后仅重验92+11=103项，请求已提出。参数和重验范围超出原入口前缀批准，按§4.5/§4.1停下等答复，不自动换方案。生产门槛、原源码和旧历史均保持，完整回归与新汇总未运行，CP3未完成。

文档和保护检查结果后补，按中途停止要求保存本地检查点，未push。本轮没有安装、下载、LLM、训练、GPU锁或全局solc操作，费用0美元。


2026-11-18 停止检查点核验补记（修改 AI：Codex）：doc_check_v1对六份正文与五份文档快照共11份全部通过，最终补记字节另由doc_check_v2核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、874份上一检查点保护成员、29,611份语料和10份资料未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA不变。这些范围可能重叠，不相加作总文件数。生产仍16模块，本轮生产/测试/夹具均未修改。

Python3.7语法与未应用补丁的git apply --check通过，静态检查不替代四版本运行。tracked diff空白检查通过；唯一保留的是建议补丁.diff的四条空源行上下文，其单个前导空格属于统一diff格式，文件SHA与行号精确绑定于whitespace_review，不豁免生产代码、测试或正文的空白问题。补丁仍未应用。

一次探针续跑已经使用，后续三个连字符版本与任何语料均未继续。当前等待allowed_paths_review_request对应参数及103项范围批准；完整回归、新汇总和最终验收未运行，CP3未完成。按中途停止要求提交本地证据检查点，提交号以包含本条记录的CP3提交及仓库外收据为准，未push。后续批准后须在新批次继续，不向本批次或任何旧批次覆盖写入。


### 2026-11-18 CP3 参数修正、103项重验及最终分类完成实验验收（修改 AI：Codex）

分支compile-repair，起始967d0890，依据PROMPTS r2.13及用户“批准参数修正、探针与103项重验（推荐）”。先核验912成员并写cp3_paths_v1授权，生产仅project.py两处--allow-paths变为绝对项目根；test_project.py追加四版本普通嵌套入口检查，原八项/夹具保持。本文0–5节已更新授权落实、最终数字、脚本问题、后续边界与关键路径，第6节历史只追加。

12项探针全通过；103项各一次，89成功/14未修复，原79成功全保持且改选更早版本，另10项新成功。有效全量为31,071项、21,160成功/9,911剩余，236条非Solidity单列。只替换103条，30,968条原来源保持；完整分类、包路径统计、29类/125条breaking changes与CP4算子清单均已更新。

首项已成功但脚本tuple/list比较误报，保存计划和输入逐字段全同，恢复已封存结果后仅继续102个未执行ID，未重试首项。历史中断段缺正常seal是原真实状态，汇总使用原已封存保全清单并核对SHA；失败收据保留，不制造seal。问题与解决方法见CHANGE_LOG §35，本次没有未经批准的方案或接受门槛变更。

production731passed/6skipped、mando271passed/466skipped、DFG2653passed/9既有warnings全部通过；最终文档和保护检查后补。准备本地提交并交独立审查，不自动push，后续CP尚未开始。0美元，无安装、下载、LLM、训练、GPU锁或全局solc改动。


### 2026-11-18 CP3 最终交付核验完成（修改 AI：Codex）

本补记更新第0节当前结论、第1节检查状态、第4节第8条及第5节收据入口；其余历史逐字保留。


2026-11-18 最终交付核验补记（修改 AI：Codex）：frozen_audit通过，28,908份保护跟踪文件、25,828份旧封存文件、905份上一检查点保护成员、29,611份外部语料及10份官方资料均未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA保持。这些检查集合可能重叠，不相加作总文件数。历史文档均保留，生产仍16模块。Python3.7语法检查、tracked diff空白检查及本批次新文件空白检查通过，没有新增豁免。

doc_check_v1对六份正文与五份原文快照共11份通过；本补记及当前状态更新后的最终字节由doc_check_v2再次核验，提交以该收据通过并绑定各文档SHA为前置条件。新证据由evidence_seal与delivery_inventory封存，acceptance_status汇总最终门槛。完整回归与保护检查已通过，此后只补交付记录，没有再跑实验或修改生产代码。

CP3本地实施与验收完成，后续交独立审查。仅本地提交compile-repair，实际提交号以包含本记录的CP3提交及仓库外delivery_commit_receipt为准；本轮未push，未实施CP4或新增修复规则。参数修正及103项批准全部落实，无新增待批准执行事项；已知工具与版本边界继续按本报告保留。


### 2026-11-21 CompileRepair CP3 审查与方案 r2.14（修改 AI：Claude）

用户要求审查 Codex 完成的 CP3（最终提交 6d7043e8b）。新增证据目录 `artifacts/cp3_review_v1/`，修改 `PROMPTS.md`（r2.13 → r2.14）。本文开头、第 0、1 节换成审查结论，第 4 节第 1 条补注，第 5 节加入证据路径。

结论：诊断解析、pragma 子类、项目闭包与共用参数、文件名 + key5、连字符入口与绝对允许目录成立；执行中的问题都先停下、保留记录、经批准后在新批次继续。五个问题：（1）类别统计把所有候选版本的错误合并，MANDO 三个 Slither 侧失败被计入两个源码类；（2）Trace on-chain 中至少一个单元是 Etherscan 标准 JSON 包装，被计为解析错误，解包后可编译、Slither 成功；（3）类型转换调用的同名错绑不在绑定检查范围内，检查 0 条时判为通过；（4）`0.4.x`、`0.5.*`、`^0.5` 被拒而 solc 接受；（5）MANDO 图未与 v5 字节对照。新增 4.5b 节 CP3.1 与 D21（待批准）。

下一步：用户决定 D21，Codex 执行 CP3.1，Claude 审查后进入 CP4。本轮没有模块代码改动或安装；按用户批准的本地研究范围从 Trace 固定提交取 1 个文件，只在审查工作区使用。详见 CHANGE_LOG §36。


### 2026-11-21 CompileRepair CP3.1 本地验收（修改 AI：Codex）

从 compile-repair@61c94e00 执行 r2.14 §4.5b，已更新本交接第 0–5 节。新增主因归属、输入包装记录、D21 保守门槛与部分版本表达式支持。报告、逐项替换及保护证据在新批次 cp3_1_v1。

核对原 31,071 个有效结果，重验 510 个受影响单元，21,223 个成功，其中新增 63 个。D21 明确确认 12 项重名，另有 6,160 项没有完整 AST。新的 MANDO 生产回归 846/846 字段相同、843/843 图字节相同。两环境模块与 DFG 测试通过。

用户“同意 D21”、“同意按实测语法拒绝单列并继续”、“同意单列 AST 不足”。包装的 3 个解包样本仅用于已验证的前提，正式处理仍在 CP5。下一步由独立审查据上述证据评估 CP3.1。

问题处理与命令、全部验收数字见 CHANGE_LOG §37、CP3_REPORT 和本批 README。0 美元，无安装、下载、LLM 或训练。本轮本地提交，未 push。


### 2026-11-22 CompileRepair CP3.1 审查与方案 r2.15（修改 AI：Claude）

用户要求审查 Codex 完成的 CP3.1（提交 1ba841cbc）。新增证据目录 `artifacts/cp3_1_review_v1/`，修改 `PROMPTS.md`（r2.14 → r2.15）。本文开头、第 0、1 节换成审查结论，第 4 节补注，第 5 节加入证据路径。

结论：CP3.1 成立。主因规则与 4.5b 节一致，MANDO 三个单元只剩 slither_incomplete；包装判定只用 JSON 解析，410 个命中；D21 只读定义名称，确认重名 12 项、原成功 0 项；审查自写 20 个 pragma × 37 个版本共 740 组与 solc 0 处不一致；MANDO 843/843 图字节与 v5 相同。

遗留：Trace on-chain 剩余 22 个 parser_error_other 全部是 Vyper（审查按用户批准的本地研究范围取这 22 个文件核对，SHA 与清单一致）；SOChecker 用的词法证据规则只在清单脚本中，生产流水线没有语言判定。另补两处：包装的 BOM 与 urls 边界；version_dependent 的阻碍。新增 4.5c 节 CP3.2，不需要新的用户决定。

下一步：Codex 执行 CP3.2，Claude 审查后进入 CP4。本轮没有模块代码改动或安装。详见 CHANGE_LOG §38。


### 2026-11-22 CompileRepair CP3.2 完成（修改 AI：Codex）

本步从 compile-repair@992bec09 开始，先读取共享 §4.1、完整 r2.15、CP3.1 审查和交接。修改 toolchain/project.py、evaluation/survey.py、pipeline.py、evaluation/report.py，增加 tests/test_cp32.py，另建 artifacts/cp3_2_v1。本文更新导读及第 0、1、2、4、5 节，第 3 节环境继续适用。

原词法规则在 31,307 项只读核对中误排 8 个已通过 D3 的入口。用户批准三态后，21,223 个原成功项全部获准通过，MANDO 846 项均有 Solidity 证据。23 项 Vyper 输入已单列，31,048 项既有测量完整沿用，236 项保留旧排除记录并按新口径列为未测。包装数量为 410，原有 221 个版本依赖主因均已重核诊断。数据见本批 language_acceptance.json、failure_summary.json 与 verification.json。

用户 2026-11-22 原话“批准三态判定及新旧统计口径”。授权明确涉及对未知输入的放行和旧排除项的分母。原判据停止现场与新口径各有独立文件，生产不依赖数据集身份。下一步是独立审查，236 项尚无编译结果。

两环境完整模块和 DFG v2 测试通过。三套日志分别为 production_tests.log、mando_tests.log、dfg_tests.log。对语料本身没有重新调用 solc 或 Slither，没有训练、安装、下载或 LLM 调用。CP3.2 仅在本地提交。


### 2026-11-22 CompileRepair CP3.2 审查与方案 r2.16（修改 AI：Claude）

用户要求审查 Codex 完成的 CP3.2（提交 7336436e7）。新增证据目录 `artifacts/cp3_2_review_v1/`，修改 `PROMPTS.md`（r2.15 → r2.16）。本文开头、第 0、1 节换成审查结论，第 4 节补注，第 5 节加入证据路径。

结论：CP3.2 成立。Codex 按硬判据发现 r2.15 的规则会误排除 8 个原成功单元，停下咨询后按用户批准的三态判定实现；审查确认原方案过严、三态判定正确。11 个边界输入、1,694 个真实 Solidity 输入与 22 个 Vyper 的判定都正确，统计相互一致，132 项测试通过。CP3 系列结束。

新增 4.6a 节 CP4 的完整提示。带入后续的三项已知限制写在 r2.16 修改说明第 3 条与 CP8 行。

下一步：Codex 执行 CP4，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §40。


### 2026-11-22 CompileRepair CP4 完成（修改 AI：Codex）

在 compile-repair 的 06ad69c2 同步后，先阅读共享 §4.1 和 r2.16 全文、CP3.2 审查及交接。新增 evaluation/benchmark.py 与 tests/test_benchmark.py，修改 core/provenance.py、cli.py、tests/test_cp1_1.py。报告为 CP4_REPORT.md，证据在 artifacts/cp4_v1，交接导读和第 0–5 节均已更新。

16,136 个合格单元来自六套语料，MANDO 843 份成功图与 v5 字节相同。200 个对照通过，17,432 个候选中纳入 11,858。严格还原全部通过，22 个实际编译的错误修复和一个缺节点图均被检出。506 行分层计数保留五类零覆盖，24 条历史分析器失败单列。

用户批准分计受影响与最终丢失节点，并批准分析器历史回放。迁移测试遇到旧 16 文件断言，获准精确调整为 17 并检查 benchmark.py。精确还原的首个偏差来自嵌入字节码的 metadata 摘要，经批准在历史源路径逐字节核验、只读重编，单项探针通过后完成 7,543 项续跑。详情与原话见 CHANGE_LOG §41、DECISIONS 和三个授权文件。

生产 815 通过、6 跳过，mando 352 通过、469 跳过，DFG v2 2,653 通过、9 条警告。生产文件 17 个，354 项 DFG 引用一致，文档检查见本批 doc_check.json。CP4 本地提交，待独立审查，本轮无 GitHub 推送、训练、安装或 LLM 调用。


### 2026-11-22 CompileRepair CP4 审查与方案 r2.17（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4（提交 812f8ea01）。新增证据目录 `artifacts/cp4_review_v1/`，修改 `PROMPTS.md`（r2.16 → r2.17）。本文开头、第 0、1 节换成审查结论，第 4 节补注，第 5 节加入证据路径。

结论：基础筛选、组哈希划分、分层抽样、两阶段触发判定、对照 200/200、精确还原 11,858/11,858 与故意错误 22/22 成立；精确还原首次失败时的停止与原路径重编处理正确。五个 0 纳入类别中，审查用 8 个手写夹具在 4 个版本上复现了原因：删除右花括号与同名函数的消息被分类器归为 other；encoding 与 unimplemented_feature 的算子没有产生目标错误；缺包依赖在合格基础单元中不存在。另外，嵌入创建码的元数据哈希随源路径与内容变化，CP5 以后的真实修复会被误判。新增 4.6b 节 CP4.1。

下一步：Codex 执行 CP4.1，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §42。

### 2026-11-22 CompileRepair CP4.1 原始诊断清点与 WSL 故障定位（修改 AI：Codex）

工作树从 e8ec530d 执行 PROMPTS r2.17 §4.6b。第 0–5 节已补充进行中的阶段、批次、环境故障、必读事项及证据路径。三个生产文件中已有部分改动，逐项清单见 CHANGE_LOG §43.1。

旧诊断去重得到 96 个模板，已准备 95 份源码夹具。剩余 1 个模板仅有通用内部异常消息，用户批准用历史收据验证。用户也批准从原始调用重判旧候选，17,432 项仍待执行。

用户要求优先排查 WSL。普通管道和真实终端均在约 30 秒后超时，两个时刻均出现 VMBus 新通道的 order-7 分配失败。当前保留用户的现有会话，压缩内存和重启均未执行。

本轮未执行两套模块测试、DFG v2 或新 solc/Slither 运行。CP4.1 尚未提交验收。文档检查与实际状态分别见 checkpoint_doc_check.json 和 wsl_startup_diagnosis.json。

### 2026-11-22 CP4.1 全量触发与缺包迁移停止点（修改 AI：Codex）

第 0–5 节已更新验收状态、分支基线、生产与 mando 环境、WSL 启动实测、续作条件与证据路径。两个环境及 DFG v2 的全部实测见新批次 final_tests/。生产文件共 17 个，354 项 DFG 代码身份匹配。

原候选重判新增 952 项，新的编码、结构体数组和缺包算子纳入 511、761、114 项。原 200 个对照核对通过。两批的失败单元分别是 cp3_15167、cp3_15136。读取保存图可证明两个实例的差异都局限于 Slither 计数器编号。原计分与待确认的替代方案分别留在停止收据与迁移核验请求中。完整数字见 CP4_REPORT.md、population.json 与 migration_stop_inventory.json。


### 2026-11-22 CP4.1 迁移评分与全量验收交接（修改 AI 为 Codex）

第 0–5 节更新了结论、状态、分支检查点、WSL 实测、审查顺序和最终证据路径。检查点后的生产代码位于 evaluation/benchmark.py，回归夹具在 tests/test_cp41.py。批次 migration_continuation 保存四份授权、每次停点的两侧原始哈希、沿用既存图的记录和核验结果。

14,196 项精确还原、114 项额外迁移全部通过。迁移逐字原分通过 53 项，生成名称按证据对齐后另有 61 项通过。前 9 对图直接沿用，补齐 105 对图实际调用 solc 242 次、Slither 210 次。两份 Yul AST 的来源另用 2 次 solc 原命令验证。程序首次使用错误路径口径时未启动工具，后来发现汇总脚本误设每图只试一个版本，两次现场均保留，详见 CHANGE_LOG §45.2。

三个最终测试结果为 production 1,068/6、mando 605/469（通过/跳过）和 DFG 2,653 通过、9 条告警。运行与文档检查的完整收据在同批 definition_continuation/suites/ 和 doc_check.json。


### 2026-11-22 CompileRepair CP4.1 审查与方案 r2.18（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4.1（提交 0f690e6f2、6950dc7b8）。新增证据目录 `artifacts/cp4_1_review_v1/`，修改 `PROMPTS.md`（r2.17 → r2.18）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：计数相互一致；8 个审查夹具在新分类器下归类正确；结构体数组复制的生产路径结论正确（审查 CP4 时只测了 abi 输出，说法有误）；迁移核验严格；272 项相关测试在审查环境通过。未解决：生成名称对应只在有文件改名映射时使用，普通修复把编号平移的节点算作改变（实测 kept 0.5）。新增 4.6c 节 CP4.2。

下一步：Codex 执行 CP4.2，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §46。

### 2026-11-22 CompileRepair CP4.2 函数移动检查点（修改 AI 为 Codex）

基线为 compile-repair 的 30df6664，按 PROMPTS r2.18 §4.1、§4.6c 和 CP4.1 审查夹具执行。生产仅修改 evaluation/benchmark.py，更新 tests/test_cp41.py，新增 tests/test_cp42.py。证据在 artifacts/cp4_2_v1，本文第 0–5 节更新本次状态、证据位置与审查顺序。

14,196 个精确还原与 114 个迁移复评分数一致。函数移动检查点为 79/200，77 份三个比例均为 1。cp3_00291 的实际哈希输入变化，cp3_21529 的另一个函数含三个 Yul switch 名称因源码起点移动而变化，六个节点正式保留原分。创建字节码、NatSpec 与迁移的三项用户决定可由 DECISIONS 追查，Yul 后续验收另待确认。每份收据均保留输入、输出身份和实测分数。

生产与 mando 两套模块测试分别通过 1,073 与 608 项，DFG v2 通过 2,653 项。成本 0 美元，CP5 待审查。完整命令、范围与封存记录见 CHANGE_LOG §47 以及本批 README。

### 2026-11-22 CompileRepair CP4.2 完成本地验收（修改 AI 为 Codex）

从检查点 387bb004 承接全部已有测量。用户确认 Yul 源码起点变化保留原分后，按原函数、版本和种子测量剩余 121 项。200 项固定 dev 函数移动全部编译并通过 D3，其中 198 项保留节点、CFG 边和调用全部相等。逐字 kept 低于 1 的有 81 项。核验后仍低于 1 的包括 1 项嵌入创建字节码变化、1 项 Yul 源码起点变化。所有低分均按实际数值计入 200 项分母。

本次更新第 0–5 节的状态、复核顺序与路径。17 个生产文件及三个回归套件见本批 final_scope.json 和 final_tests/。审核者可用 README 的只读命令核对封存哈希，按 CP4_REPORT 最终表验证低分。所有工作本地执行，0 美元，阶段结束待独立审查。[最终验收](../artifacts/cp4_2_v1/acceptance.json)


### 2026-11-22 CompileRepair CP4.2 审查与方案 r2.19（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4.2（提交 387bb0040、1bb69b7ff）。新增证据目录 `artifacts/cp4_2_review_v1/`，修改 `PROMPTS.md`（r2.18 → r2.19）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：生成名称对应已推广且严格；精确还原与迁移重算与 CP4.1 相同；移动自检 198/200 为 1，两项低分原因属实；275 项相关测试在审查环境通过。发现：`_score_facts` 把修复删除的未破坏节点移出 kept 分母，删除原代码时主指标不下降（实测 kept 2/7 → 2/2）；这是 r2.18 §4.6c 措辞所致。Yul switch 起点可按组合偏移映射对齐。新增 4.6d 节 CP4.3。

下一步：Codex 执行 CP4.3，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §48。


### 2026-11-23 CompileRepair CP4.3 完成本地验收（修改 AI 为 Codex）

分支 compile-repair，起始提交 09a8355e。按 PROMPTS r2.19 §4.1 和 §4.6d、前次审查及交接实现 evaluation/benchmark.py 的分母和 Yul 起点核验。本文第 0–5 节已更新状态、工作批次、环境、审查入口与关键路径。

200/200 项主 kept 均小于 1，修复删除节点合计 933 个，每项均等于预期的移动节点数。199/200 项的存活节点、CFG 边和调用三个比例均为 1。14,196 个精确还原的主指标和 exact 均与 CP4.2 一致，名称状态全部为 identical。114 个迁移的主指标、raw 和全图结果也逐项相同。两组的 removed_by_repair 全部为 0。 修复误删完好函数的手写探针 kept 为 2/7、lost 为 2、removed_by_repair 为 5。真实字节差异继续保留原分。

用户转交 CP4.3 确认了 §48.4 中的 Yul 口径。两套模块测试与 DFG 回归按仓库根路径执行，production 1,076 项通过、6 项跳过，mando 609 项通过、473 项跳过，DFG v2 2,653 项通过、9 条告警。所有结果已本地封存，独立审查后方可进入 CP5。资源与测试命令均可由变更 §49 和批次 README 复核。[批次记录](../artifacts/cp4_3_v1/README.md)


### 2026-11-23 CompileRepair CP4.3 审查与方案 r2.20（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4.3（提交 868d814c9）。新增证据目录 `artifacts/cp4_3_review_v1/`，修改 `PROMPTS.md`（r2.19 → r2.20）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：CP4.2 审查的两个问题已正确解决；审查自写的 Yul 夹具与删除探针结果符合预期；移动、精确还原与迁移的重算数据与报告一致；276 项相关测试在审查环境通过。未解决：名称对应一处不符即整体放弃，分数不成比例。新增 4.6e 节 CP4.4。

下一步：Codex 执行 CP4.4，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §50。


### 2026-11-23 CompileRepair CP4.4 完成本地验收（修改 AI 为 Codex）

专用分支 compile-repair，起始提交 8739c653。按 PROMPTS r2.20 §4.1、§4.6e 及独立审查证据完成普通评分的按节点排除。生产仅修改 evaluation/benchmark.py，测试新增 test_cp44.py，并同步前两批测试的状态断言。本文第 0–5 节已补充状态、工作树、环境、审查顺序和证据位置。

普通 A/B/C 为 7/7、6/7、6/7，嵌套 Yul A/B/C 为 16/16、16/16、14/16。比例性测试三次均恰好少一个匹配。14,196 个精确还原与 114 个迁移保持历史指标。用户确认注释仅改变长度时单列三个节点，并接受 cp3_00291 主 kept 由 261/267 到 262/267 的差值。原始停点仍在新批次中。

生产与 mando 模块回归分别通过 1,080 与 612 项，DFG v2 通过 2,653 项。17 个生产文件、354 个冻结 DFG 引用已核对。本批本地提交，独立审查待进行，CP5 尚未运行。详见 CHANGE_LOG §51 和本批 README。[最终验收](../artifacts/cp4_4_v1/acceptance.json)


### 2026-11-23 CompileRepair CP4.4 审查与方案 r2.21（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4.4（提交 2355afad1）。新增证据目录 `artifacts/cp4_4_review_v1/`，修改 `PROMPTS.md`（r2.20 → r2.21）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：CP4.3 审查的比例性问题已解决（6/7），Yul 夹具与移动重算和报告一致，279 项测试通过。未解决：移出的节点按原样比较，错误修复中保留旧名的使用节点被计为相等，可能高估；参与推导比较的事实与主指标不一致。新增 4.6f 节 CP4.5。

下一步：Codex 执行 CP4.5，Claude 审查后进入 CP5。本轮没有模块代码改动或安装。详见 CHANGE_LOG §52。


### 2026-11-23 CP4.5 定义锚与历史验收（Codex）

从 compile-repair@c8ca807a 执行 r2.21 §4.6f。此前旧名探针能给出相同总分却选错节点，现在按节点身份核验。完整重算中出现同节点写入被统计为多个定义，已逐项取证并先后取得两次用户决定。首轮 4 个移动和 678 个精确还原差异的完整收据已封存；新批次三组指标全部一致。前后两轮的 production、mando 和 DFG v2 回归分别保留。读 CP4_REPORT 的 CP4.5、CHANGE_LOG §53、`cp4_5_v1/README.md` 与最终验收。下一步为独立审查 CP4.5。


### 2026-11-23 CompileRepair CP4.5 审查与方案 r2.22（修改 AI：Claude）

用户要求审查 Codex 完成的 CP4.5（提交 0b5fd600b）。新增证据目录 `artifacts/cp4_5_review_v1/`，修改 `PROMPTS.md`（r2.21 → r2.22）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：CP4.5 成立。审查的全部探针在新评分器上重跑，四个旧名场景都等于真正正确的节点数；200 项移动与 14,196 项精确还原的逐项数据与报告一致；301 项测试通过。首轮停点与写回形式的识别经用户批准，处理正确。两项限制带入 CP5（第 0 节自比核验、rejected 状态单列）。

新增 4.6g 节 CP5 的完整提示与 D22、D23 两项决定。下一步：Codex 执行 CP5，第 1 节后停下请用户决定。本轮没有模块代码改动或安装。详见 CHANGE_LOG §54。


### 2026-11-23 CP5 下载与项目修复检查点（修改 AI 为 Codex）

从 `26f44492` 同步 r2.22。已完成第 0–1 节、D22 确认与 D23 授权。第 2–4 步已接入流水线，在真实手写探针上通过。MANDO 的 843 个真值图逐字节相同，3 个历史失败状态一致。详见 `CP5_REPORT.md` 和 CHANGE_LOG §55。此处更新了文档开头、第 0 节、第 1 节的状态与下一步，以及第 5 节的证据路径。

继续工作先读 `artifacts/cp5_v1/d23/transport_stop.json` 和 `optimizer_request.json`。149 份已核验归档位于仓库外，剩余 23 份需在得到续传确认后保留原累计上限。参数验证器改动也在等待确认。独立的测试、真值回归、四个评分接入样本已保存。完整索引经 seal 复核后，按冻结划分在 8 个缺包开发样本比较版本选择规则，再进行测试集报告及全量外部修复。


### 2026-11-23 CompileRepair CP5 检查点审查与方案 r2.23（修改 AI：Claude）

用户要求审查 Codex 完成的 CP5（提交 3c7ae7ee5，报告写明为检查点）。新增证据目录 `artifacts/cp5_review_v1/`，修改 `PROMPTS.md`（r2.22 → r2.23）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：已完成部分成立；CP5 未完成。发现四个问题；同意 optimizer 方案（新增 D24）与 23 个发布版的续传。新增 4.6h 节 CP5.1，完成索引、候选上限、规则选择、第 4 步评测与全量评估。

下一步：Codex 执行 CP5.1，Claude 审查后进入 CP6。本轮没有模块代码改动、下载或安装。详见 CHANGE_LOG §56。

### 2026-11-23 CP5.1 完整依赖索引与开发评估（修改 AI 为 Codex）

本轮更新第 0–1 节的当前状态与 D24、第 2–3 节的工作树和环境、第 4–5 节的复核顺序及批次路径。172 份归档全部复核。两处环境停点、请求前的独占登记及限定续作均保存在 `cp5_1_v1` 下。先核对 `index_verification.json` 和 `population.json`，然后按 `moved_summary.json` 对回 400 个真实逆操作。库文件字节恢复和 D3 成功分别见 `package_dev_summary.json`，完整规则选择依据以开发集结果为准。操作及变更见 CHANGE_LOG §57。

解释图结果时应一并核对 partial_ir_review.json 和 partial_ir_decision.json。cp3_19463 在三个规则下的 D3 均通过，Slither 仍报告同一函数生成 IR 中断。用户已确认 CP5.1 沿用 D3，将已证实的局限单列。后续复核须区分节点源码映射覆盖与函数的 IR 是否生成。

开发阶段的原始 6,940 份与剩余 8 份由 development_interrupt.json 和 development_continuation/ 授权及清单衔接。核对原始前缀 SHA256，再按单元和规则核对新记录。原进程退出时的 31 份 solc 调用独立保留。后续阶段在选版冻结后启动。

恢复环境的依据在 development_continuation/recovery_summary.json。6,940 份结果和 6,940 份步骤共 474,552,564 字节，哈希均通过。原 Windows / WSL 代理与直连阻断经过实测，普通 Windows 身份无权逐条列出全部出站例外。后续工作在专属 tmux 中运行，持有独占登记。

冻结规则后的首轮模块测试因缺少 TREE_SITTER_LIB_DIR 停止。CP0 登记路径为 /home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64，库 SHA256 为 f424e0d52ebcdda4932a973af5357874fedd0348c78d87b1575bf15ee539d967。首轮完整证据保存在 frozen_suites/，环境修正与两套回归另存 test_environment_resume_v2/。

移动算子另有逐单元目标核对。189 个 D3 成功样本都指向原计划的移动位置，其中 187 个虽满足已记录的全部图指标，仍因编辑位置超出原损坏区间邻近范围而未达到 exact。核对 moved_path_outcomes.json 与 moved_inverse.jsonl 可分别复现路径结果和精确逆操作自检。

首轮生产与 mando 的两份 pytest 日志在第 24、25、28 行带有 pytest 输出的行尾空格，原始 SHA256 与续跑申请逐一吻合。交付时以 Git 暂存字节复核这两份日志，其余文件照常检查空白。

全量运行时新 WSL 命令再次返回 0x8007274c，独立的 /bin/true 在 30.14 秒后报告同一错误，内核仍记录 Relay 等待 vsock。原 tmux 中两个分片继续写入。通过共享目录恢复只读核验，并核对 Windows Git 所见分支、基线提交、仓库身份设置和生产文件哈希。该通道可在保留现有会话的条件下完成本地交付。详见 test_environment_resume_v2/launcher_recurrence.json。

真实外部语料按冻结的项目组划分后，开发集通过 D3 的单元为 1,131/2,316，测试集为 4,749/6,822。14 个达到组合上限的单元都在测试集。逐项匹配入口 SHA256 后，开发集 2,316 项的 D3 成败均与最旧优先的无上限测量一致。两张原始表的哈希与分组计数见 external_split_summary.json。

完成全量后，第 0–1 节同步为最终状态。正式默认规则为 `oldest`，K=21。 真实语料 5880/9,138 通过 D3，其中 14 个触发编译组合上限。基准开发集 236/550、测试集 1004/2114 通过编译和 D3。复核从 `policy.json`、`benchmark_summary.json`、`external_summary.json` 和 `frozen_mando/summary.json` 开始。


### 2026-11-23 CompileRepair CP5.1 审查与方案 r2.24（修改 AI：Claude）

用户要求审查 Codex 完成的 CP5.1（提交 41c685fca）。新增证据目录 `artifacts/cp5_1_review_v1/`，修改 `PROMPTS.md`（r2.23 → r2.24）。本文开头、第 0、1 节换成审查结论，第 5 节加入证据路径。

结论：已完成部分成立；未解决五个问题，新增 4.6i 节 CP5.2 与待定决定 D25。移动算子的缺陷来自 4.6h 的写法（没有同时更新被移动文件的导入）。

下一步：Codex 执行 CP5.2，Claude 审查后进入 CP6。本轮没有模块代码改动、下载或安装。详见 CHANGE_LOG §58。

### 2026-11-24 CompileRepair CP5.2 完成（修改 AI 为 Codex）

专用工作树以 fba94f1d 为起点，执行 PROMPTS r2.24 §4.6i。生产改动集中于四个既有模块，细节及函数清单见 code_audit.json。本次更新交接第 0–5 节的状态、环境、阅读顺序及证据路径。

400 个 v2 移动样本均通过触发和逆向对照。363 项通过实际修复，359 项达到 exact。旧移动样本的 D3 通过数为 CP5.1 的 189/400 与 CP5.2 的 279/400；真实缺相对文件的 D3 通过数为 CP5.1 的 42/412 与 CP5.2 的 44/412。其余 8714 个外部单元的 D3 和图 SHA256 逐项相同。 原 950 份包装结果均经验证达到 exact。

部分 IR 检出的单元为真实开发集 4/1131、基准成功样本 0/1240、MANDO 0/843、CP3 基础抽样 0/1000。17 份移动收据使用已接受轮次的位置，按原指针核对双份哈希后完成诊断。用户批准保留包装原分，并在验证唯一源身份后转换图表示。首份 IR 清单保留导入来源绝对路径，逐项核对逻辑目标后恢复原清单；711 个旧参数项目按原目录另行编译。D25 仍待用户决定。

全部 843 份 MANDO 成功图与 v5 相同，另 3 项保留原失败。首轮回归因测试复制源码时评分函数仍在编辑而停止；冻结 18 个生产文件后在新目录通过全部三套回归，354 个 DFG 引用核验完成。WSL 单独重启后验证了代理和直连阻断；后续启动器间歇超时时保留运行中的作业，通过原生启动方式和共享目录核验收据。CPU 评估费用 0 美元，未执行下载或训练。
