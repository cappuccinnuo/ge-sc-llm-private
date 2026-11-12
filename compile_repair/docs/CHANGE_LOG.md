# CompileRepair 运行与改动记录

本文件记录 CompileRepair 模块每一次编码任务的详细内容，格式沿用仓库根目录 `docs/training_changes_2026-10-07.md` 中 NodeSem 的五段式小节（任务与范围 / 实施与选择 / 实测与结论 / 批准与差异 / 验收与停止）。本模块没有 HGT 训练，“运行”指编译、Slither、LLM 调用与评估。记录规则见 `README.md`。

日期与时间使用 America/New_York（11 月起为 EST，UTC−05:00）；提交时间取自 `git log --date=iso-strict`。本文区分“已经修改”与“建议、尚未实施”。只追加，不改写旧小节；更正以新小节追加。

§1、§2 是 2026-11-12 建立本文件时按当时的提交、证据文件与对话记录补记的，内容以提交 39b78108、bfd23e83 中的文件为准。

---

## 1. 2026-11-11 CompileRepair 方案 r1：MANDO 语料编译证据与版本策略方案（修改 AI：Claude）

### 1.1 任务、依据与范围

用户要求复核此前在对话中提出的编译修复方案（v1：版本选择 → 依赖补全 → 规则桩 → LLM 多智能体 + RAG），确认无误后写出第二版方案、设计模板、建分支并推送到 GitHub，参照 EdgeSem 的组织方式，并要求每一点都有依据、不作臆测。

起点：私有仓库 `cappuccinnuo/ge-sc-llm-private`。读取了 `edge-sem` 分支 `scripts/edge_sem/` 的 PROMPTS（含 r1 原始版本）、PROGRESS、RECON、EP 报告的结构，以及 `scripts/DFG/dfg_v2/PROMPT6BC_REPORT.md`、`PROGRESS.md`（2026-10-25 节）、`scripts/DFG/state/stage_f/versioning.py`、`scripts/DFG/dfg_v2/inputs.py`、`validate_slither.py`、`auto_version_solc.py`、`scripts/edge_sem/artifacts/ep6_v1/compiler_history.json`。

分支选择：`main` 不含 `scripts/DFG/dfg_v2`；`node-sem@306c135b` 含 dfg_v2、validate_slither 与 versioning，且是 `edge-sem` 的祖先，所以从它切出 `compile-repair`，与 EdgeSem 起点相同而不含进行中的 EdgeSem 代码。

新增文件（提交 39b78108，21 个文件）：`scripts/compile_repair/PROMPTS.md`、`PROGRESS.md`、`REPORT_TEMPLATE.md`；`artifacts/cr_pre_v1/` 下 `README.md`、`corpus_stats.py/.json`、`compile_repro.py/.json`、`slither_probe.py/.json`、`cross_version.py/.json`、`solc_github_static_SHA256SUMS`、`probes/` 下 7 个 `.sol` 与 `RESULTS.txt`。没有修改任何已有文件。

### 1.2 实施方式和重要选择

- 语料统计（`corpus_stats.py`）：只读遍历 `experiments/ge-sc-data/source_code/<七类>/source_files/*.sol` 及同级其他目录；统计 pragma 形式、首个版本号的小版本系列、文件名类型、SmartBugs 风格标签注释、import。
- 编译复现（`compile_repro.py`）：A 为 `auto_version_solc.py` 规则（pragma 中第一个 x.y.z，无 pragma 用 0.4.25，只试一次）；B 为 A 不通过时在合取 pragma 区间内尝试所有可用版本。区间语义按 `versioning.py::interval` 重写（未导入，因为证据环境没有该模块依赖的 tree-sitter 设置），只用于证据，不是生产代码。直接调用 `solc <文件>`，以退出码判定，不经 crytic-compile。
- 语料在复制件上运行（字节相同），原仓库目录不写入。
- 编译器来源：GitHub 发布页 `ethereum/solidity` 的 `solc-static-linux`。尝试 0.4.10–0.4.26、0.5.0–0.5.17：0.4.10 返回 404，其余 34 个版本可用，SHA256 记入 `solc_github_static_SHA256SUMS`。用户 6c 使用的是 solc-select 从 binaries.soliditylang.org 安装的版本，来源不同。
- Slither 环境：先在 Python 3.13 上安装 slither-analyzer 0.8.0 失败（依赖 pysha3 无法构建）；改用 uv 安装 Python 3.8.20，装 slither-analyzer 0.8.0、crytic-compile 0.2.4（与 6c 相同版本），再装 setuptools<70 提供 pkg_resources 后可运行。用户环境为 Python 3.7.12，二者不同。
- Slither 探针（`slither_probe.py`）：对 A 不通过的 39 个文件，用 B 中最低与最高可编译版本各运行一次。
- 跨版本比较（`cross_version.py`）：key4 =（合约、函数 full_name、节点类型、起始偏移），key5 = key4 + 排序后的 SlithIR 字符串，另比较 source length。先用 key5 含 length 比较时得到“不同”，再拆开后确认差异只来自 length，因此 D4 规定节点身份不含 length。
- solc 行为探针：等长空格替换 pragma 行、基类后定义、无函数体声明在基类先出现，分别在 0.4.25 与 0.5.11 上编译。
- 提交时 `.gitignore` 的 `*.json`、`*.txt` 规则使 JSON 结果与 `RESULTS.txt` 未被加入；参照 EdgeSem 用 `git add -f` 提交产物的做法补入，并在 push 前修正同一提交（amend），远端只有修正后的提交。

### 1.3 实测与数据结论

| 项 | 结果 | 来源 |
|---|---|---|
| 文件数 | 七类 `source_files` 共 846（114/120/92/88/142/100/190） | corpus_stats.json |
| import | 0 | corpus_stats.json |
| 无 pragma | 22 | corpus_stats.json |
| 两条不同 pragma | 15 | corpus_stats.json |
| 规则 A | 807 通过、10 失败、29 所选版本 ≤ 0.4.10 不可得（0.4.0×21、0.4.2×4、0.4.9×2、0.4.10×1、0.4.6×1） | compile_repro.json |
| 10 个失败的原因 | pragma 下界早于代码语法（`^0.4.11` 下 `view`/`pure`；`^0.4.13`–`^0.4.20` 下在 `(` 处解析错误）；2 个文件两条 pragma 时规则版本落在自身合取区间之外 | compile_repro.json 的错误首行 |
| 规则 B | 39/39 在区间内且同一小版本系列找到可编译版本；按退出码 846/846 可编译 | compile_repro.json |
| 重入 + 访问控制 | A 不通过 17，与 6c 的 11 + 6 总数相同；逐文件对应未核对 | compile_repro.json、PROMPT6BC_REPORT.md |
| Slither | 39 × 2 次全部成功；solc 0.4.11 时节点 `filename_absolute`/`filename_used` 为 None，0.4.12 起正常 | slither_probe.json |
| 跨版本 | key4 39/39 相同；key5 39/39 相同；source length 36/39 相同 | cross_version.json |
| 静默风险 | 规则 A 可编译但版本 ≤ 0.4.11 的文件 4 个 | compile_repro.json |
| 探针 | 等长替换可编译且字节数不变；基类后定义报 “Definition of base has to precede definition of derived contract”；先定义的无函数体声明可编译；`^0.4.24` 文件替换 pragma 后可被 0.5.11 编译 | probes/RESULTS.txt |

结论（r1 当时）：在 MANDO 语料上，不可编译全部来自版本选择，不需要改源码。该结论只对这 846 个文件成立；没有证明外部语料同样如此。

### 1.4 用户批准、原文差异与待确认设计

- r1 把对话中的 v1 方案收缩为确定性版本策略，LLM 层、依赖补全与规则桩列为有触发条件的扩展，决策 D1（846 个文件范围）、D2（升序选版本）待用户确认，D8（下游用途）待定。
- 同日用户否定了只做版本修复的范围，要求覆盖更多编译问题、面向检测与 DAppSCAN 等真实语料，并不得区分两种运行模式。r1 由 r2 替代（§2）；r1 的证据与探针结论仍然有效并被 r2 引用。
- 用户在该轮消息末尾写有“3.”但没有内容，已在回复中询问，未得到补充。

### 1.5 验收、资源、未执行事项与停止

- 四份文档通过 `python3 -B -m scripts.node_sem.doc_check --expect-cjk`。
- push 后核对：`compile-repair` 头 39b78108，父提交 306c135b；与 `node-sem` 的差异只在 `scripts/compile_repair/`；其他五个分支头不变（`edge-sem` 仍为 2cd3dbf3）。
- 未执行：用户环境中的任何运行；任何模块代码；与 6c 逐文件核对（6c 完整报告只在用户本地）。
- 资源：全部运行在 Claude 的云端临时环境，CPU；没有 GPU、没有 LLM 调用。

---

## 2. 2026-11-11 CompileRepair 方案 r2：目录移到仓库根目录、完整修复设计与外部语料统计（修改 AI：Claude）

### 2.1 任务、依据与范围

用户要求：（1）写入讨论后确定的完整设计，并先把 `compile_repair` 文件夹移到与 `scripts` 同级；（2）给 Codex 的代码生成 Prompt 必须遵守功能内聚、分层目录、适度模块化、受控文件数（不含 tests）。

起始：`compile-repair@39b78108`，工作区干净。实际原目录是 `scripts/compile_repair`（不在 `scripts/DFG` 内），已在回复中说明。

修改（提交 bfd23e83）：`git mv scripts/compile_repair compile_repair`（21 个文件内容不变）；`compile_repair/PROMPTS.md` 改写为 r2；`REPORT_TEMPLATE.md` 与 `artifacts/cr_pre_v1/README.md` 更新路径；`PROGRESS.md` 追加 r2 节；新增 `artifacts/cr_pre_v2/README.md`、`dappscan_stats.py`、`dappscan_stats.json`。

### 2.2 实施方式和重要选择

设计内容来自 2026-11-11 对话中逐项确定的结论：

- 一条流水线处理所有输入，不区分训练与检测模式（用户决定）；改动记录与节点标记由下游决定用法。
- 确定性方法先于代理（用户决定）。九步：编译器版本、项目组装、依赖补全、缺失文件搜索、源码规范化、同系列 pragma 覆盖、规则桩、结构补全、只在代码生成阶段出现的失败。第 2–9 步按 D6 阈值在 CP3 测得数据后决定是否实现。
- 提示设计：核对了 8 个 LLM 编译修复系统（SmCFixer、SOChecker、Trace、CompileAgent 的发布代码；RustAssistant、Byam、PhantomRun、Google 构建修复的论文），都不按错误类别分模板，因此只用一个修复模板，差异来自定位与检索。
- 第二阶段多代理：核对了多代理辩论的实证研究（ICML 2024 “Should we be going MAD?”、ACL 2024 Wang 等）与 Agentless（SWE-bench Lite 32.00%、每题 0.70 美元）。编译修复有精确裁判（编译器），所以不用讨论投票，改为失败分析、上下文扩展、异构模型独立提议、工具裁决、至多一轮基于编译结果的交流（用户采纳）。
- RAG：K1 版本对应的 Solidity 文档、K2 离线库索引、K3 修复记忆（留一项目防泄漏）；先精确键后 BM25，嵌入检索只作消融。
- 代码结构（3.10 节）：core → toolchain → {rules, rag} → agents → pipeline → {cli, evaluation} 六层；29 个计划的非测试 `.py`，上限 30；禁止 utils/helpers/common；导入方向由 `tests/test_layering.py` 检查。
- 外部语料统计（`dappscan_stats.py`）：只读遍历 DAppSCAN `DAppSCAN-source/contracts`，跳过 node_modules；统计 import 种类、相对导入目标是否存在、构建配置文件、pragma 版本系列。SOChecker 与 Trace 只做文件计数与简单文本统计。没有编译外部语料。
- `dappscan_stats.json` 同样需要 `git add -f`。

### 2.3 实测与数据结论

| 语料（提交） | 结果 |
|---|---|
| DAppSCAN（66a56619c44770e05c2db600fa6468115ff0dcd5） | 608 个项目，21,457 个 `.sol`；473 个项目含 import；405 个项目至少一条仓库内无法静态解析的 import；相对导入 38,122 条可找到、1,094 条缺失；包导入前列 `@openzeppelin/contracts` 4,783、`@openzeppelin/contracts-ethereum-package` 1,181、其他裸路径 1,111、`@openzeppelin/contracts-upgradeable` 668、`openzeppelin-solidity` 597；606/608 个项目无构建配置；按文件的版本系列 0.5 6,552、0.6 5,464、0.8 4,222、0.4 3,503、0.7 1,542、无 pragma 135 |
| SOChecker（5e56d7542ac1f4d81004d05b9375c7042a506b0c） | `evaluation/RQ1/ours.json` 897 条片段，656 条含 `contract `/`function ` |
| Trace（4260215b5330293db7739d9fadeecf014ef97816） | on-chain 5,000 个单文件；repo-level 83 个项目 3,092 个 `.sol`，深度 3 以内无构建配置；CVEs 15 |
| 许可 | 三个仓库都没有 LICENSE 文件 |

结论：外部语料的主要问题是依赖缺失与项目组装，版本跨 0.4–0.8；只覆盖 OpenZeppelin（DAI 的范围）不够。这是文件结构统计，失败类别的真实分布须由 CP3 编译后测得。

### 2.4 用户批准、原文差异与待确认设计

- 用户在 2026-11-11 的讨论中确定：不分两种模式；确定性方法先于代理；采纳第二阶段多代理设计；要求文献证据支持提示设计；代码结构四项原则。
- 待确认：D5（版本策略细节）、D6 阈值（建议占环境层后剩余失败 ≥ 1% 或 ≥ 20 个编译单元）、D9（审查代理只作消融）、D10（LLM 视图中路径匿名化与注释遮蔽）。待定：D12（模型、API、费用上限，CP8 前）、D13（下游用途，CP10 后）。
- 外部语料的许可由用户决定。

### 2.5 验收、资源、未执行事项与停止

- 五份文档通过 `doc_check`（`PROGRESS.md` 以追加前 999 字节检查）。
- push 后核对：`compile-repair` 头 bfd23e83；远端 `scripts/compile_repair` 下 0 个文件，`compile_repair` 下 24 个文件；与 `node-sem` 的差异只在 `compile_repair/`；其他分支头不变。
- 未执行：模块代码；外部语料编译；任何 LLM 调用。

---

## 3. 2026-11-12 CompileRepair 文档目录：交接、改动记录与决策记录（修改 AI：Claude）

### 3.1 任务、依据与范围

用户要求：参照 NodeSem 的做法，在编译模块的文档目录（不存在则新建）中加入交接文档与训练/改动记录，内容要详细；以后每完成一个编码任务都必须提供详细记录；格式沿用 NodeSem 的文档；必要时可增加其他类型的文档。

起始：`compile-repair@bfd23e83`，工作区干净。读取了 `node-sem` 分支根目录 `HANDOVER.md`（NodeSem 交接记录 2026-11-01 至 2026-11-09，例如 NS-P0、NS-P1、NS-P1b、NS-P9）与 `docs/training_changes_2026-10-07.md`（文件头与 §71–§72）。NodeSem 自己的目录 `scripts/node_sem/` 没有 docs 子目录，交接与训练记录写在仓库根目录这两份文件中。

新增：`compile_repair/docs/README.md`、`HANDOVER.md`、`CHANGE_LOG.md`（本文件）、`DECISIONS.md`。修改：`compile_repair/PROMPTS.md`（r2 → r2.1，只改记录位置与 6c 本地文件读取方式，设计不变）、`compile_repair/REPORT_TEMPLATE.md`（指向 docs）；`compile_repair/PROGRESS.md` 追加一节。

### 3.2 实施方式和重要选择

- 格式对应：NodeSem 交接记录为“### 日期 NodeSem 任务 完成（修改 AI：Codex）”加 3–5 段完整句子；训练记录为“## 编号. 日期 NodeSem 任务：标题（修改 AI：Codex）”加 .1 任务、依据与范围 / .2 实施方式和重要选择 / .3 实测与数据结论 / .4 用户批准、原文差异与待确认设计 / .5 验收、资源、未执行事项与停止。本目录的 `HANDOVER.md` 与 `CHANGE_LOG.md` 采用相同标题形式与段落结构，模板写在 `README.md`。
- 文件名：本模块没有模型训练，所以详细记录命名为 `CHANGE_LOG.md`（运行与改动记录），在文件头说明它对应根目录的 `training_changes_2026-10-07.md`。
- 交接文档结构：NodeSem 根目录 `HANDOVER.md` 开头有环境与“坑”的说明，后面是追加的交接记录。本目录 `HANDOVER.md` 采用同样结构：第 0–5 节为当前状态（一句话、状态表、分支与工作树、环境、必读事项、关键路径），第 6 节为只追加的交接记录。
- 新增 `DECISIONS.md`：r1、r2 的决策编号曾经改变含义（例如 r1 的 D2 是“升序选版本”，r2 的 D2 是“语料选择”），需要一份带历史的决策记录，避免以后引用编号时混淆。
- 记录位置：NodeSem 与 EdgeSem 都向根目录两份文件末尾追加。`compile-repair` 与 `edge-sem` 并行开发，两边都追加会在合并时冲突，所以本模块只写在 `compile_repair/docs/`，并在 PROMPTS 共享上下文的禁止修改清单中加入根目录这两份文件。合并时在根目录 `HANDOVER.md` 追加一段指向本目录的说明。
- 强制记录：`README.md` 规定“编码任务”的范围、提交前必须完成的五项、记录要求与模板；PROMPTS 共享上下文改为引用这些规则，并在“工作方式”的结束检查中加入“记录已完成”。
- 6c 本地文件：核对 `edge-sem` 分支，`slither_full/report.json`、`report.seal.json`、`trusted_compilers_complete.json` 都未被跟踪，`report.json` 被 `.gitignore:24` 的 `*.json` 规则忽略，所以新建的工作树中不存在。EdgeSem 工作树路径 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11` 来自 `scripts/edge_sem/PROMPTS.md` 第 308、315 行。PROMPTS 共享上下文与 CP0 改为以该绝对路径只读读取，先核对 SHA256，不复制、不修改。此修正在 2026-11-12 的对话中提出，本轮一并写入。
- §1、§2 为补记：依据提交内容、证据文件与对话记录写成；没有当时的运行日志文件，运行命令以证据目录中的脚本与 README 为准。

### 3.3 实测与数据结论

本轮没有编译、Slither 或 LLM 运行。核对结果：

| 核对项 | 结果 |
|---|---|
| `edge-sem` 跟踪 `slither_full/report.json` | 0 |
| `edge-sem` 跟踪 `slither_full/report.seal.json` | 0 |
| `edge-sem` 跟踪 `trusted_compilers_complete.json` | 0 |
| `git check-ignore` | `.gitignore:24:*.json` 匹配 `report.json` |
| EdgeSem 工作树路径出现位置 | `scripts/edge_sem/PROMPTS.md` 第 308、315 行 |

### 3.4 用户批准、原文差异与待确认设计

- 用户要求本身即批准新建 `compile_repair/docs/` 与这些文档。
- 与 NodeSem 的差异：记录写在模块目录，不写根目录（理由见 3.2）。若用户希望仍同时写根目录，需要另行决定合并冲突的处理方式。
- 6c 本地文件的读取方式此前只在对话中提出，未得到用户明确答复；因为它是 CP0 能否执行的前提，且只涉及只读访问，本轮写入并在此登记，用户可撤销。
- 未改变任何设计决策；D5、D6 阈值、D9、D10、D12、D13 的状态不变。

### 3.5 验收、资源、未执行事项与停止

- `python3 -B -m scripts.node_sem.doc_check --expect-cjk compile_repair/docs/README.md compile_repair/docs/HANDOVER.md compile_repair/docs/CHANGE_LOG.md compile_repair/docs/DECISIONS.md compile_repair/PROMPTS.md compile_repair/REPORT_TEMPLATE.md compile_repair/PROGRESS.md:1959`：退出码 0，7 个文件全部 passed=True（`PROGRESS.md` 追加前 1,959 字节）。写入本条后再次运行，结果相同才提交。
- 路径核对：`PROMPTS.md` 与 `docs/` 中剩余的 `scripts/compile_repair` 只出现在描述 r1 的历史记录中。
- 未执行：模块代码；任何运行。
- 本轮提交并 push 到 `compile-repair`；不修改其他分支。停在文档建立完成，下一步仍为 CP0。

---

## 4. 2026-11-12 CompileRepair 方案 r2.2：面向检测时任意输入，去除对训练数据集的依赖（修改 AI：Claude）

### 4.1 任务、依据与范围

用户说明（2026-11-12）：本方案不只修复当前训练数据集中的问题，还要修复将来用模型检测时输入的损坏合约，因此不必只针对当前数据集中的问题，方案不限于该数据集。

起始：`compile-repair@068433d0`，工作区干净。逐项检查 `PROMPTS.md` r2.1 中依赖某个数据集的设计（`grep` 关键词：阈值、metadata、0.4.25、--corpus、按 CP3 观察、846），找到以下几处：D6 用语料出现频率（≥ 1% 或 ≥ 20 个编译单元）决定是否实现规则；版本策略第 2 条只读取 DFG v2 的 SolidiFI metadata；第 4 条无 pragma 时以 MANDO 的 0.4.25 为默认；CLI 只有 `--files` 与 `--corpus mando`；CP0 只检查 846 个文件需要的编译器；CP3 的分类类别与 CP4 的破坏算子只来自已观察到的失败；CP6 只实现“达到阈值”的规则。

修改：`compile_repair/PROMPTS.md`（r2.1 → r2.2）。记录：本节、`docs/HANDOVER.md`（第 0、1、4 节更新与第 6 节新记录）、`docs/DECISIONS.md`（D2、D5、D6 更新，新增 D16，历史 4 行）、`PROGRESS.md`。没有修改其他文件。

### 4.2 实施方式和重要选择

- 适用范围：0 节新增一段，写明面向检测时的任意输入（单文件、扁平化文件、多文件项目、片段），版本 0.4.12–0.8.x；语料只用于测试、评估与排列实现顺序。下限 0.4.12 来自证据 5（Slither 0.8.0 在 solc 0.4.11 时节点缺文件名）。
- D6：覆盖范围改为由与语料无关的失败分类表决定。分类表的来源限定为有文档依据的内容。为此核对了 Solidity 文档“Using the compiler”页（docs.soliditylang.org v0.7.6；latest 版本页面不在本会话的抓取允许列表中，因此使用 v0.7.6）的“Error types”一节：13 种类型为 JSONError、IOError、ParserError、DocstringParsingError、SyntaxError、DeclarationError、TypeError、UnimplementedFeatureError、InternalCompilerError、Exception、CompilerError、FatalError、Warning；standard JSON 错误对象中 type、component、severity、message 为必有字段，sourceLocation、errorCode、formattedMessage 为可选字段。因此分类以错误类型与消息模板为主，errorCode 有则记录。
- 判定准则：某类失败只要存在可确定性实施、且能被 D3 与 D7 机械检查验证的修复，就实现为规则；否则交给代理。出现频率只决定实现顺序。这比频率门槛更符合“检测时任意输入”的目标：门槛会让在训练或评估语料中少见、但在检测输入中可能出现的类别永远只能交给代理。代价是 CP6 的工作量可能增加，由 CP3 的分类表给出具体规模。分类表这种做法由 Claude 提出，用户可以调整。
- 版本策略：第 2 条改为调用方可选提供的已知版本（Etherscan 验证记录、构建配置、MANDO 回归中的 SolidiFI metadata 都是实例），标志名改为 `known_version_below_slither_floor`。第 4 条无 pragma 时先用同一编译单元其他文件的 pragma，再按版本特征语法推断区间；特征只能来自官方 changelog 与 breaking changes 文档并逐条注明出处，举例中的 0.5.0（显式可见性与数据位置、移除 `throw`/`var`）与 0.8.0（默认检查算术）是这些文档中的条目。0.4.25 默认值保留为 MANDO 回归配置，以便与 6c 对照。
- D16（新增）：6c 使用 Slither 0.8.0。它对较新 0.8.x 编译器输出的支持没有在本项目中验证过，所以不在方案中假定可用或不可用；CP0 第 5b 节用每个版本系列的小型手写合约测出，结果交用户决定（升级会使结果与 6c 不能直接对照）。
- 入口：`cli repair <路径>...`，`--snippet`、`--known-version`、`--regression mando`；检测与评估同一入口，语料名只作统计标签与回归配置。这与 D1（一条流水线、不分模式）一致：`--regression mando` 只改变已知版本来源与无 pragma 默认值，不改变流程。
- Prompt：CP0 改为“工具基线（全版本范围）与 MANDO 回归基线”，新增 5b 节；CP1 前提加入 D16，测试加入已知版本与版本特征推断；CP2 改为 MANDO 回归运行；CP3 新增第 0 节“失败分类表”，并要求不得删除有文档依据但语料中未出现的类别；CP4 破坏算子覆盖分类表中每个可构造的类别；CP6 实现分类表中判定为可确定性修复的全部类别。
- D10 与共享上下文不变量中的“已校验的版本 metadata”统一改为“调用方提供的已知编译器版本（可选）”。
- 更正：`HANDOVER.md` 第 1 节状态表在 r2.1 提交（068433d0）中仍写 r2，未随修订更新；本轮改为 r2.2，并在交接记录中写明。

### 4.3 实测与数据结论

本轮没有编译、Slither 或 LLM 运行。只做了文档核对：

| 核对项 | 结果 | 来源 |
|---|---|---|
| solc 错误类型 | 13 种，名称见 4.2 | docs.soliditylang.org/en/v0.7.6/using-the-compiler.html |
| standard JSON 错误字段 | 必有 type、component、severity、message；可选 sourceLocation、errorCode、formattedMessage | 同上 |
| `PROMPTS.md` 中剩余“阈值”“--corpus”“已校验的版本 metadata” | 0 处 | `grep` |

未证明：Slither 0.8.0 在 0.6–0.8 各版本上的可用性（D16，留给 CP0）；各类失败在检测输入中的真实分布（只能用评估语料近似）。

### 4.4 用户批准、原文差异与待确认设计

- 用户 2026-11-12 的说明是本轮修改的依据：D2 改为语料只用于测试与评估；D6 原则（不只针对当前数据集）视为用户决定，分类表方式与判定准则由 Claude 提出，用户可调整。
- 仍待确认：D5（版本策略细节，本轮内容有更新）、D9、D10。待定：D12、D13、D16。原 D6 的阈值问题随本轮取消，不再需要确认。
- 设计中其他部分（修复循环、两阶段代理、RAG、改动记录、代码结构）不变。

### 4.5 验收、资源、未执行事项与停止

- `python3 -B -m scripts.node_sem.doc_check --expect-cjk compile_repair/PROMPTS.md compile_repair/docs/HANDOVER.md compile_repair/docs/DECISIONS.md compile_repair/docs/CHANGE_LOG.md:18665 compile_repair/PROGRESS.md:2817`：5 个文件全部 passed=True（`HANDOVER.md`、`DECISIONS.md` 本轮既有更新也有追加，按整文件检查；`CHANGE_LOG.md`、`PROGRESS.md` 只追加，按追加前字节数检查）。写入本条后再次运行，结果相同才提交。
- `PROMPTS.md` 中“阈值”“--corpus”“已校验的版本 metadata” 剩余 0 处。
- 未执行：模块代码；任何运行。
- 本轮提交并 push 到 `compile-repair`；不修改其他分支。下一步仍为 CP0。
