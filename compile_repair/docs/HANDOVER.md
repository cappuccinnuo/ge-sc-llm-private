# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.3（尤其 1.6 节与 4.2b 节）、DECISIONS 和 CHANGE_LOG §7。第 6 节保留历史，只追加；记录规则见 README.md。

## 0. 一句话

CP0 已由 Claude 独立复核，全部数字可复现；审查发现 D3 漏顶层函数与合约覆盖、key4 不唯一、pragma 覆盖规则自相矛盾、Slither 版本未定四个问题，方案改为 r2.3。下一步是 CP0.1（4.2b 节）；CP1 必须等 CP0.1 通过且用户决定 D5、D16、D18。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案 | PROMPTS r2.3（CP0 审查后修订） | CHANGE_LOG §7 |
| 模块 | 9 个生产 Python 文件、3 个测试文件、7 个 fixture（CP0） | CP0_REPORT |
| CP0 | 已审查：数字全部复现（846 输入、规则 A 821/22/3、1,692 个选定版本 0 违例、678 对 key4/IR 678/678）；调查结论成立 | artifacts/cp0_review_v1/README.md、verify_cp0.json |
| 审查发现的问题 | D3 未覆盖顶层函数、可空通过；key4 在 55 个文件中重复（改 key5，序号 678/678 稳定）；3.2 第 6 行与 3.3 第 6 条矛盾；CP0 的 toolchain 只认 dict 形式 source_mapping | PROMPTS 1.6 节、r2.3 修改说明 |
| D16 | 已测 Slither 0.8.0/0.8.3/0.9.6/0.10.4/0.11.6；推荐 0.9.6 独立环境做生产、0.8.0 只做 6c 重放；待用户决定 | PROMPTS 1.6 节、slither_versions_corpus.json、feature_probes.jsonl |
| 编译器 | 总安装 37；0.4.12–0.8.38 正式版本 33/92 已安装；D18 建议补齐其余 59 个，待用户决定 | cp0_v2 release_coverage；DECISIONS D18 |
| 测试 | CP0 32 passed；DFG v2 2653 passed、9 warnings（Codex 环境） | cp0_continue_v1 测试日志 |
| 下一步 | 用户决定 D5、D16、D18 → Codex 执行 CP0.1（A 部分无需授权，可先做）→ Claude 审查 → CP1 | PROMPTS 4.2b 节 |
| 其他决策 | D9/D10 待确认，D12/D13 待定 | DECISIONS |

## 2. 分支与工作树

- 工作树 `/home/zhao/SmartContract/ge-sc-llm-compile`，分支 `compile-repair`；不要重复创建或在 EdgeSem 工作树执行 git。
- 本轮起点为本地 CP0 检查点 `8fb81ed91a189405df8e8ee7a06a2c3eb3249e47`。`pull --ff-only` 获取上游 `54ecc927c6b277ffcca962c13838cbadcdfa1192` 后因分叉不能快进，已合并双方历史并解释四份记录冲突的解决方法。最终本地提交用 `git log -1` 定位，提交信息以 CP0 开头；未 push。
- 仅本模块代码、文档和新证据变更。scripts/**、原作者代码、输入、6c 文件、旧产物及仓库根目录记录文档保持不变。

## 3. 环境

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
```

Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4、solc-select 1.0.4 未更改。新增 11 个获批 solc 已安装并双哈希校验，始终使用明确二进制路径，全局选择仍未设置。不要将安装成功或基线特征通过解释成完整语法支持。新包、编译器或语料获取仍需具体授权；本轮授权只覆盖已完成的 11 个版本。

Windows 侧使用 `wsl.exe -d Ubuntu-22.04 --cd ... --exec ...`；含中文的 Python 管道设置 PowerShell `$OutputEncoding = [System.Text.UTF8Encoding]::new()`。需要联网时沿用已验证代理并禁止直连回退，不修改网络配置。

## 4. 必读事项（已知的坑）

1. **6c 的本地结果只在 EdgeSem 工作树中。** `prompt6c_v1/` 下的 report、seal、可信编译器清单被 `.gitignore` 忽略；用绝对路径 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/...` 只读读取，先核对 SHA256，不复制、不修改。用户另批准两份冻结 source manifests 及 metadata 引用源码/CSV，范围见 `cp0_development_v1/metadata_read_authorization.json`，不含标签/图/模型。
2. **`.gitignore` 忽略 `*.json` 与 `*.txt`。** 需要提交的产物用 `git add -f` 逐个暂存；pytest 临时目录不要整体 add。
3. **solc ≤ 0.4.11 时 Slither 0.8.0 的节点没有文件名**，编译成功不等于可用；成功判据是 D3（r2.3 加入顶层函数与合约覆盖）。0.4.10 及更早在 GitHub 发布页没有静态 Linux 二进制。
4. **43 份 metadata 来自 SmartBugs `versions.csv`**（不是 SolidiFI BugLog；r2.3 已更正）。4 份 ≤ 0.4.11，跳过，不绕过 D3。
5. **key4 不唯一。** Slither 把三元表达式等拆成共享起始偏移的同类节点（55 个文件）；节点身份用 key5（带序号），不得去重。6c 报告的 occurrence 行没有节点类型与原始 SlithIR，CP2 的 6c 回归用冻结抽取代码精确重放后比较（r2.3 的 CP2 第 2 节）。
6. **Slither 0.9 起 source_mapping 是对象，不是 dict。** 冻结的 `validate_slither._mapping` 遇到对象返回 `{}`，所以冻结的 6c 抽取只能在 Slither 0.8.0 下使用；本模块的 toolchain 必须两种都支持（CP0.1）。顶层函数在 `compilation_unit.functions_top_level`，不在 `functions_and_modifiers_declared`。
7. **`scripts/DFG/state/stage_f/versioning.py` 经 `frontend.py` 依赖 tree_sitter 与 `TREE_SITTER_LIB_DIR`。** 新建 Slither 环境时必须装同一版本并验证区间计算逐文件相同（CP0.1 B 部分）。
8. **仓库默认规则 `auto_version_solc.py` 只取 pragma 中第一个版本号、只试一次**；在 846 个文件上 22 个失败、3 个编译器未安装（cp0_v2）。
9. **pragma 覆盖是唯一允许离开声明区间的情形**，只在区间内没有可用编译器时、在下界所在小版本系列内使用，记为 rewrite（PROMPTS 3.2 第 6 行、3.3 第 6 条，r2.3）。
10. **证据环境不同。** `cr_pre_v1`、`cr_pre_v2`、`cp0_review_v1` 是 Claude 在云端环境（GitHub 静态 solc、Python 3.8/3.12）得到的证据；`cp0_review_v1` 的 Slither 0.8.0 结果与 Codex 在用户环境的指纹 743/743 相同，其余版本的数字须由 CP0.1 在用户环境复核。
11. **外部语料仓库（DAppSCAN、SOChecker、Trace）都没有 LICENSE 文件。** 使用范围由用户决定；语料放在仓库之外，不提交。
12. **模块面向检测时的任意输入，不只修复训练数据中的问题。** 覆盖范围由与语料无关的失败分类表决定（D6）；MANDO 846 个文件只是与 6c 对照的回归基线（PROMPTS 0 节“适用范围”）。
13. **记录只写在 `compile_repair/docs/` 与模块目录**，按 NodeSem 五段式变更与四段式交接，UTF-8 写入并通过 doc_check；不修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md`。没有 HGT 训练、GPU 锁操作、LLM 调用或图存储写入。
14. **记录只追加。** CHANGE_LOG 合并时编号曾变化（r2.2 记录现为 §5，Codex 的 CP0 为 §4、§6）；旧文中引用 “§4” 指 r2.2 的地方是笔误，见 CHANGE_LOG §7.4，不回改旧文。

## 5. 关键路径

| 内容 | 路径 |
|---|---|
| 要求与完整报告 | PROMPTS.md、CP0_REPORT.md 续作、RECON.md §8–11 |
| 正式结果与全部差异 | artifacts/cp0_v2/recon.json、invocations.jsonl、cross_version.jsonl、seal.json |
| 授权及二进制身份 | artifacts/cp0_compiler_install_v1/、cp0_compatibility_install_v1/ |
| 续作开发、测试、审计 | artifacts/cp0_continue_v1/ |
| 小样本首轮失败与修正后验证 | artifacts/cp0_matrix_smoke_v1/、cp0_matrix_smoke_v2/ |
| 原停止现场 | artifacts/cp0_v1/（只读） |
| CP0 审查证据（Claude） | artifacts/cp0_review_v1/README.md 及其中脚本与 JSON |
| 记录规范与最新详细记录 | docs/README.md、docs/CHANGE_LOG.md §7 |

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
