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


## 4. 2026-11-12 CompileRepair CP0：前置核验与工具封装，按必需版本缺口停止（修改 AI：Codex）

### 4.1 任务、依据与范围

按用户要求先读更新的 PROMPTS r2.1，特别是 §4.1 共享上下文，再从 CP0 开始；读 docs/HANDOVER §0–5、CHANGE_LOG 最新 §3、记录模板与决策表。独立工作树 `/home/zhao/SmartContract/ge-sc-llm-compile`，分支 compile-repair，起始 HEAD `068433d0cfa3367fe09cd1f94f78319eeff3c6d0`。`git pull --ff-only origin compile-repair` 退出 1（Could not resolve host: github.com）；通过连接的 GitHub 工具核对远端分支 SHA 与本地相同，未改网络配置，不把替代核验记为 pull 成功。

新增代码与测试完整清单：

- `compile_repair/__init__.py`
- `compile_repair/cli.py`
- `compile_repair/core/__init__.py`
- `compile_repair/core/model.py`
- `compile_repair/evaluation/__init__.py`
- `compile_repair/evaluation/survey.py`
- `compile_repair/toolchain/__init__.py`
- `compile_repair/toolchain/slither.py`
- `compile_repair/toolchain/solc.py`
- `compile_repair/tests/test_layering.py`
- `compile_repair/tests/test_survey.py`
- `compile_repair/tests/test_toolchain.py`
- `compile_repair/tests/fixtures/counter.sol`

新增 `compile_repair/RECON.md`、`CP0_REPORT.md`；追加 `PROGRESS.md` 和本节；更新 docs/HANDOVER 第 0–5 节并在第 6 节追加四段交接，更新 docs/DECISIONS 的 D15 与待批准 D16。产物为 `artifacts/cp0_v1/` 和 `artifacts/cp0_development_v1/`，选定的可复核文件逐项归档；pytest 临时回归样本不整体提交。未修改 scripts/**、作者代码、原始语料、根目录 HANDOVER/training_changes、旧产物或 EdgeSem。

### 4.2 实施方式和重要选择

core/model 仅使用 Python 3.7 兼容 dataclass。toolchain/solc 复用冻结 inspect_environment/compiler_for_selection 验证本地可信二进制，复用 crytic-compile 0.2.4 `_build_options` 并匹配默认单文件 argv，直接 subprocess 记录真实退出码、首条错误、耗时与 0 美元费用；不调用安装或全局选择。toolchain/slither 复用冻结 `_compile`，先绑定前一次成功 solc 与输入/编译器 SHA，再检查所有声明函数和修饰器的所有 CFG 节点。记录 API 构造结果，不声称观测到了 crytic 内部子进程退出码；比较器保留节点重复次数和 IR 顺序，length 只作独立诊断。

survey 使用冻结 frontend.parse、versioning.interval/recorded_version、auto_version_solc.get_solc_version；只从 tasks.py AST 读取两个 source manifest 引用，不导入标签/图加载流程。先核对 6c 报告与 seal，再按报告绑定读取 trusted manifest；用户批准后核对 sources.json 哈希并校验全部 metadata。候选只按源码区间和可信安装版本统计，类别/路径只用于证据对应与统计。发现必要版本缺口后停止编译矩阵，封存 recon/seal；完整矩阵和选版编排尚未实施，不静默跳过无候选文件。

没有复制或修改冻结函数，没有 monkeypatch。冻结来源路径与 SHA256、crytic 源文件哈希及既有 tree-sitter 库哈希保存在 source_provenance.json；354 份 `_code_refs()` 基线在 baseline.json。新工作树缺少动态库时使用 TREE_SITTER_LIB_DIR 指向既有原工作树库，不下载/编译/复制。

开发问题与处理：默认 PowerShell 相对目录/UNC 访问不适用，改用显式 WSL --cd；WSL 未安装 rg，使用 git/Python 枚举。一次探索误以为 6c 顶层有 files，改读 tasks[*].files；一次写基线时 PowerShell 默认管道编码损坏中文分隔符造成 IndexError，显式 UTF-8 后解决。第一次 CP0 pytest 的“外部目录拒绝”测试误把 artifacts 内的归档 tmp_path 当成外部目录，20 passed/1 failed；仅修正测试路径，第二轮通过。首轮文档辅助脚本误用了 Python 3.7 不支持的 Path.write_text(newline=...)，在写 HANDOVER 前报 TypeError；确认已写/未写边界后，只继续未执行的文件，使用 Path.open，未重复追加 PROGRESS。旧日志和额外测试调查现场均保留，没有自动重跑正式 cp0_v1。详情见 development_context.json、development_issues.json、development_test_fix_v1.json、document_writer_fix.json。

### 4.3 实测与数据结论

正式调查耗时 5.684 秒，命令/退出码见 survey_cp0_v1.json（退出 2，状态 blocked_missing_compilers）。输入身份、所有逐文件历史差异和缺失版本明细见 cp0_v1/recon.json，SHA256 `e4dfe405a16ca90c962b54996f117e76eb1a17656197062be17196200906bca1`；seal SHA256 `eed04a53213e62a9b1b0fc41cdbd827a6073d4451f093b4de44134b7d5c8b1d0`。

| 项目 | 实际结果 | 来源 |
|---|---|---|
| MANDO 清单 | 846；22 无 pragma；2 个旧 A 版本在合取区间外 | recon.inputs / summary |
| 6c 映射 | 256 按源码 SHA256 对应 | historical_comparison.files |
| 6c 状态 | 239 compared / 11 compile_failed / 6 not_comparable | historical_comparison.status_counts |
| 旧 A 对应 256 份 | 239 ok / 6 fail / 11 unavailable_here；异常 17 个文件完全相同 | inputs.pre_rule_a / RECON §3 |
| metadata | 43 校验通过；4 个 ≤0.4.11；全部来自 SmartBugs versions.csv | recon.metadata |
| 安装编译器 | 26/26 哈希匹配 | recon.environment / compilers |
| 无候选输入 | 1，精确 pragma 0.4.17；其他 845 仅证明有候选 | recon.blockers |
| D3 实验 | 0.4.11：rc0，5/5 节点缺 filename，失败；0.4.13：rc0，0/5 缺失，通过 | pytest_cp0_tmp_v2 下真实 probe JSON |

不能由上述结果推出本机 846/846 编译成功。旧 cr_pre JSON 不含源码哈希，只能逐项对照文件集合；6c 才提供当前匹配的 256 份输入字节身份。旧 A 的早期版本不可得、6c 的 D3 映射检查解释了其异常状态差别，未进行新的全量调用方式因果对照。未来全量 key4 相同也不能单独证明 CFG/CG 边或语义等价。

### 4.4 用户批准、原文差异与待确认设计

1. 用户于 2026-11-12 明确回复“允许这些必要的只读校验（推荐）”：只扩展读取两份冻结 contract sources.json 及 metadata 引用来源源码/CSV。先验证已登记 SHA256，不读取标签、图存储或模型产物，不修改 EdgeSem。精确授权写入 metadata_read_authorization.json；D15 更新为已定（用户）。
2. 更正 PROMPTS §1.2：43 metadata 来源均为 SmartBugs versions.csv，不是 SolidiFI BugLog。按“代码/证据优先”追加更正，不改 PROMPTS 原文，不改变验证规则。
3. CP0 §4.2.3 要求缺少必要版本时停下。本机缺少 0.4.17，唯一精确版本合约无候选。D16 只登记待批准请求：官方下载单个 0.4.17，SHA256/Keccak256 核验、独立追加信任清单、费用 0 美元、不切换全局 solc；未下载/安装。未申请其他可选缺失版本。读权限批准不包含安装。
4. 建议、未实施：6c occurrence 报告缺少 node.type 与原始 IR，CP2 的“与 6c 一致”应先明确可观察比较对象。RECON §6 提出不依赖 length 的 occurrence 多重集合键，不能声称它区分所有 CFG 节点；待 CP2 前用户审定。D4 未改。
5. 建议、未实施：精确 pragma 无可用版本时覆盖，与禁止越过原区间不能同时满足；本轮用待批准安装请求处理具体缺口，CP1 的一般规则仍需确认。D5/D6/D9/D10/D12/D13 状态未变。

### 4.5 验收、资源、未执行事项与停止

`python -B -m pytest -q -p no:cacheprovider compile_repair/tests`：第二轮 21 passed、0 failed、0 skipped，0.42 秒；首轮 20 passed、1 failed 保留。`python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests`：2653 passed、0 failed、0 skipped，9 条既有依赖弃用警告，182.50 秒。实际命令额外传新建 --basetemp 以保存现场，完整 argv/耗时见 tests_*_v*.json。测试与调查使用 mando Python 3.7.12、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2，仅 CPU；生产 .py 共 9 个，test_layering 通过，354 个冻结 refs 与 baseline 完全相同。

未执行：编译矩阵编排、全量规则 A/升降序 D3 选版、moved/crossed_minor 全量统计、全量 Slither、跨版本语料回归、CP2 时间估计；源码修复、图存储、下载/安装/升级、全局 solc 切换、HGT 训练、GPU 锁、LLM 调用。费用 0 美元。CP0 在缺少必需 0.4.17 处停止，CP1 前提未满足；待用户批准后以新批次继续。文档与最终冻结审计通过后保存本地 CP0 检查点，不 push；提交号由 git log 中对应 CP0 提交给出，避免提交自引用。

最终检查补记：doc_check_v1 对 6 份中文文档全部 passed=True、退出码 0；CHANGE_LOG 从原 18,665 字节、PROGRESS 从原 2,817 字节起检查追加部分，HANDOVER/DECISIONS 因当前状态表更新检查全文。另核对 CHANGE_LOG/PROGRESS 的旧字节前缀及 HANDOVER §6/DECISIONS §3 的历史前缀完全保留。final_audit.json 确认 846 原始输入、6c 三份引用文件、354 冻结代码引用不变，9 个生产模块哈希与正式调查快照一致，已跟踪改动仅在 compile_repair/。本补记加入后再次 doc_check，全通过才提交；最终命令和结果归档为 doc_check_v2。

暂存检查补记：`git diff --cached --check` 首次指出新建 RECON.md 末尾多一个空行，已移除；不涉及历史文档或代码。对最终 6 份文档再次运行 doc_check（doc_check_v3），全部 passed=True 后重新执行 diff --check；此前 v1/v2 文档检查日志保留。
