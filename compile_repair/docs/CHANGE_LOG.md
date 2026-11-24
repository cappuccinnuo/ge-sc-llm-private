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


> 合并说明（修改 AI：Codex）：以下 r2.2 记录来自上游 54ecc927 的 §4。为避免与本地既有 CP0 §4 重号，导入时仅将标题编号改为 §5/§5.x；正文保留。上游原文可由该提交核对。

---

## 5. 2026-11-12 CompileRepair 方案 r2.2：面向检测时任意输入，去除对训练数据集的依赖（修改 AI：Claude）

### 5.1 任务、依据与范围

用户说明（2026-11-12）：本方案不只修复当前训练数据集中的问题，还要修复将来用模型检测时输入的损坏合约，因此不必只针对当前数据集中的问题，方案不限于该数据集。

起始：`compile-repair@068433d0`，工作区干净。逐项检查 `PROMPTS.md` r2.1 中依赖某个数据集的设计（`grep` 关键词：阈值、metadata、0.4.25、--corpus、按 CP3 观察、846），找到以下几处：D6 用语料出现频率（≥ 1% 或 ≥ 20 个编译单元）决定是否实现规则；版本策略第 2 条只读取 DFG v2 的 SolidiFI metadata；第 4 条无 pragma 时以 MANDO 的 0.4.25 为默认；CLI 只有 `--files` 与 `--corpus mando`；CP0 只检查 846 个文件需要的编译器；CP3 的分类类别与 CP4 的破坏算子只来自已观察到的失败；CP6 只实现“达到阈值”的规则。

修改：`compile_repair/PROMPTS.md`（r2.1 → r2.2）。记录：本节、`docs/HANDOVER.md`（第 0、1、4 节更新与第 6 节新记录）、`docs/DECISIONS.md`（D2、D5、D6 更新，新增 D16，历史 4 行）、`PROGRESS.md`。没有修改其他文件。

### 5.2 实施方式和重要选择

- 适用范围：0 节新增一段，写明面向检测时的任意输入（单文件、扁平化文件、多文件项目、片段），版本 0.4.12–0.8.x；语料只用于测试、评估与排列实现顺序。下限 0.4.12 来自证据 5（Slither 0.8.0 在 solc 0.4.11 时节点缺文件名）。
- D6：覆盖范围改为由与语料无关的失败分类表决定。分类表的来源限定为有文档依据的内容。为此核对了 Solidity 文档“Using the compiler”页（docs.soliditylang.org v0.7.6；latest 版本页面不在本会话的抓取允许列表中，因此使用 v0.7.6）的“Error types”一节：13 种类型为 JSONError、IOError、ParserError、DocstringParsingError、SyntaxError、DeclarationError、TypeError、UnimplementedFeatureError、InternalCompilerError、Exception、CompilerError、FatalError、Warning；standard JSON 错误对象中 type、component、severity、message 为必有字段，sourceLocation、errorCode、formattedMessage 为可选字段。因此分类以错误类型与消息模板为主，errorCode 有则记录。
- 判定准则：某类失败只要存在可确定性实施、且能被 D3 与 D7 机械检查验证的修复，就实现为规则；否则交给代理。出现频率只决定实现顺序。这比频率门槛更符合“检测时任意输入”的目标：门槛会让在训练或评估语料中少见、但在检测输入中可能出现的类别永远只能交给代理。代价是 CP6 的工作量可能增加，由 CP3 的分类表给出具体规模。分类表这种做法由 Claude 提出，用户可以调整。
- 版本策略：第 2 条改为调用方可选提供的已知版本（Etherscan 验证记录、构建配置、MANDO 回归中的 SolidiFI metadata 都是实例），标志名改为 `known_version_below_slither_floor`。第 4 条无 pragma 时先用同一编译单元其他文件的 pragma，再按版本特征语法推断区间；特征只能来自官方 changelog 与 breaking changes 文档并逐条注明出处，举例中的 0.5.0（显式可见性与数据位置、移除 `throw`/`var`）与 0.8.0（默认检查算术）是这些文档中的条目。0.4.25 默认值保留为 MANDO 回归配置，以便与 6c 对照。
- D16（新增）：6c 使用 Slither 0.8.0。它对较新 0.8.x 编译器输出的支持没有在本项目中验证过，所以不在方案中假定可用或不可用；CP0 第 5b 节用每个版本系列的小型手写合约测出，结果交用户决定（升级会使结果与 6c 不能直接对照）。
- 入口：`cli repair <路径>...`，`--snippet`、`--known-version`、`--regression mando`；检测与评估同一入口，语料名只作统计标签与回归配置。这与 D1（一条流水线、不分模式）一致：`--regression mando` 只改变已知版本来源与无 pragma 默认值，不改变流程。
- Prompt：CP0 改为“工具基线（全版本范围）与 MANDO 回归基线”，新增 5b 节；CP1 前提加入 D16，测试加入已知版本与版本特征推断；CP2 改为 MANDO 回归运行；CP3 新增第 0 节“失败分类表”，并要求不得删除有文档依据但语料中未出现的类别；CP4 破坏算子覆盖分类表中每个可构造的类别；CP6 实现分类表中判定为可确定性修复的全部类别。
- D10 与共享上下文不变量中的“已校验的版本 metadata”统一改为“调用方提供的已知编译器版本（可选）”。
- 更正：`HANDOVER.md` 第 1 节状态表在 r2.1 提交（068433d0）中仍写 r2，未随修订更新；本轮改为 r2.2，并在交接记录中写明。

### 5.3 实测与数据结论

本轮没有编译、Slither 或 LLM 运行。只做了文档核对：

| 核对项 | 结果 | 来源 |
|---|---|---|
| solc 错误类型 | 13 种，名称见 4.2 | docs.soliditylang.org/en/v0.7.6/using-the-compiler.html |
| standard JSON 错误字段 | 必有 type、component、severity、message；可选 sourceLocation、errorCode、formattedMessage | 同上 |
| `PROMPTS.md` 中剩余“阈值”“--corpus”“已校验的版本 metadata” | 0 处 | `grep` |

未证明：Slither 0.8.0 在 0.6–0.8 各版本上的可用性（D16，留给 CP0）；各类失败在检测输入中的真实分布（只能用评估语料近似）。

### 5.4 用户批准、原文差异与待确认设计

- 用户 2026-11-12 的说明是本轮修改的依据：D2 改为语料只用于测试与评估；D6 原则（不只针对当前数据集）视为用户决定，分类表方式与判定准则由 Claude 提出，用户可调整。
- 仍待确认：D5（版本策略细节，本轮内容有更新）、D9、D10。待定：D12、D13、D16。原 D6 的阈值问题随本轮取消，不再需要确认。
- 设计中其他部分（修复循环、两阶段代理、RAG、改动记录、代码结构）不变。

### 5.5 验收、资源、未执行事项与停止

- `python3 -B -m scripts.node_sem.doc_check --expect-cjk compile_repair/PROMPTS.md compile_repair/docs/HANDOVER.md compile_repair/docs/DECISIONS.md compile_repair/docs/CHANGE_LOG.md:18665 compile_repair/PROGRESS.md:2817`：5 个文件全部 passed=True（`HANDOVER.md`、`DECISIONS.md` 本轮既有更新也有追加，按整文件检查；`CHANGE_LOG.md`、`PROGRESS.md` 只追加，按追加前字节数检查）。写入本条后再次运行，结果相同才提交。
- `PROMPTS.md` 中“阈值”“--corpus”“已校验的版本 metadata” 剩余 0 处。
- 未执行：模块代码；任何运行。
- 本轮提交并 push 到 `compile-repair`；不修改其他分支。下一步仍为 CP0。


## 6. 2026-11-12 CompileRepair CP0 续作：授权补齐编译器并完成 r2.2 基线调查（修改 AI：Codex）

### 6.1 任务、依据与范围

用户批准原 0.4.17 下载请求，并询问是否覆盖所有 solc；同步 PROMPTS r2.2 后，另批准十个系列边界探针版本。先阅读共享上下文 §4.1、CP0 §4.2、版本策略 §3.3、docs/README 和当前交接；起始 `compile-repair@8fb81ed91a189405df8e8ee7a06a2c3eb3249e47`。本轮只补完 CP0，不实施 CP1、通用 repair、语料修复、图存储或 Slither 升级。`pull --ff-only` 拉取到上游 `54ecc927c6b277ffcca962c13838cbadcdfa1192`，因双方各有提交而不能快进；随后合并并保留历史，详见 `cp0_continue_v1/pull.json`、`merge_start.json`、`merge_resolution.json`。

生产代码修改完整清单：`compile_repair/cli.py`、`toolchain/solc.py`、`evaluation/survey.py`。测试修改：`tests/test_survey.py`、`tests/test_toolchain.py`。新增 fixture：`tests/fixtures/compat_04.sol`、`compat_05.sol`、`compat_06.sol`、`compat_07.sol`、`compat_08.sol`、`compat_08_errors.sol`。记录文件：`PROMPTS.md`（完整采用上游 r2.2）、`PROGRESS.md`、`RECON.md`、`CP0_REPORT.md`、`docs/CHANGE_LOG.md`、`docs/HANDOVER.md`、`docs/DECISIONS.md`、`artifacts/cp0_continue_v1/README.md`。新增产物目录为 `cp0_compiler_install_v1`、`cp0_compatibility_install_v1`、`cp0_continue_v1`、`cp0_matrix_smoke_v1`、`cp0_matrix_smoke_v2`、`cp0_v2`，均位于本模块 artifacts。没有修改 scripts/**、原作者代码、输入语料、6c 文件、旧封存产物或仓库根目录两份记录文档。

### 6.2 实施方式和重要选择

1. 信任链：原 26 个 6c 编译器身份原样保留，11 个获批版本使用官方 Linux amd64 索引中精确发布路径，下载后先核验 SHA256/Keccak256，再安装至既有 solc-select 目录并执行 `--version`。不切换全局选择。独立追加清单绑定授权、发布快照及二进制身份，加载器拒绝覆盖旧身份、版本与授权不符或哈希异常。所有网络请求强制走已有代理，无直连回退；未改网络配置。
2. 编译与 D3：复用冻结函数和 crytic-compile 的参数生成，不复制冻结代码。每份源码仅在原路径只读编译，记录实际 solc rc、命令、SHA、首条错误与耗时，再经 Slither API 构造并检查全部声明函数/修饰器节点。每文件/版本观测只运行一次后复用；预期候选失败记入矩阵，全部候选无成功或基础设施异常停止。日志逐调用 flush，最终 seal 绑定全部正式结果文件；不写图存储。
3. 选版对照：先验证 metadata（本语料实际来自 SmartBugs），有效且 ≥0.4.12 时两种顺序均优先；MANDO 无 pragma 保留 0.4.25 优先。初始候选按 lower-bound 系列，后续系列仅在本系列全部 D3 失败后启用。同时找最低/最高 D3 端点，避免 metadata 优先版本被误称为数值最低版本。D5 只作 CP0 实验性调查，通用推断留在 CP1。
4. 兼容性：每个已安装版本都运行适用的手写 fixture；0.4 四个低于支持下限的历史版本作为负对照。common 特征包括状态读写、内部调用、修饰器、事件、外部调用、继承；try/catch 从 0.6 起、unchecked 从 0.8 起、自定义错误单独从 0.8.4 起测试。版本语法出处保存在正式报告 feature_sources 及 RECON §8，只核对官方网页，未下载文档语料。
5. 开发问题与处理：solc-select 旧客户端访问索引返回 HTTP 403，确认尚未创建二进制后，改用已成功读取同一官方索引的显式代理 requests 客户端完成同一已授权安装，保留失败日志；Python 3.7 的 `Path.write_text(newline=...)` 不可用，使用 `Path.open`；开发小样本首次从 JSON 读回区间时出现 list/tuple 比较 TypeError，在 `candidate_versions` 统一端点类型并补测试，首轮现场保留、另建 v2 验证。上游文档合并冲突用追加与编号说明解决，没有抹除本地停止记录；一次只读定位脚本使用错误标题字符串后，改按实际编号章节读取。细节集中在 `cp0_continue_v1/development_issues.json`。

冻结函数的来源与 SHA256 沿用 CP0_REPORT 首轮来源表，并由本轮 `_code_refs()` 再次核对。没有新增生产模块，仍为目录表内 9 个文件；层次检查包含在 CP0 测试中。


### 6.3 实测与数据结论

正式输入身份、环境与每条结论均绑定到 `artifacts/cp0_v2/recon.json`，SHA256 `bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6`。seal SHA256 `16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b` 同时绑定全部调用日志与跨版本差异。正式运行只一次，内部 928.330 秒，CLI 总 932.935 秒，退出码 2、状态 `awaiting_d16`；不是测试崩溃或自动重试。

| 事项 | 数量与结论 | 来源 |
|---|---|---|
| 已授权编译器 | 新装 11（4,600,648 + 94,225,936 字节），总 37；原 26 身份不变 | 两份追加清单、verified JSON |
| 目标范围发布/安装/未安装 | 92 / 33 / 59；另 4 个低于下限历史版本 | 官方索引 SHA `b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac`；release_coverage |
| 身份 | 输入 846、metadata 43、6c 对应 256，全部通过 | recon inputs/metadata/historical_comparison |
| MANDO 调用 | solc 5,391 次（5,254 rc0、137 rc1）；Slither 1,546 次全 D3 通过 | invocations.jsonl、final_findings.json |
| 输入级 D3 | 846/846，缺 filename 节点 0、空 CFG 文件 0；旧 6c 异常 17/17 通过 | matrix_summary、inputs |
| 规则 A | 821 passed、22 failed、3 unavailable；合取区间外 2 | matrix_summary；旧环境转移计数在 final_findings |
| 选版差异 | 升降序不同 617，moved 44，crossed_minor 0 | matrix_summary |
| 双端比较 | 678 个双 D3 输入，key4/IR 678/678 相同，length 650/678 相同；其余 168 不在分母 | cross_version.jsonl |
| key4 重复 | 55 份输入存在重复，已保留重数，没有去重 | invocations.jsonl；selected_duplicate_key4_files |
| 兼容性探针 | 37 版共 39 组，solc 全 rc0，D3 33 passed/6 failed | compatibility.results |
| 兼容性失败 | ≤0.4.11 四组各缺 10 filename；0.8.4 和 0.8.38 自定义错误两组 ErrorDefinition 解析失败 | compatibility；slither_failure_diagnosis/final_findings |
| CP2 时间依据 | 所选 solc 80.853 秒 + Slither 228.587 秒，约 309.440 秒 | cp2_runtime_estimate |

这些数字不证明所有补丁、所有语法或任意项目可修复，也不证明图边及行为语义相等。CP2 时间只覆盖编译/分析，未包含未来存储、序列化和比较。范围内 33 个已装版本都通过基线特征，但其中 0.8.4 与 0.8.38 未通过全部适用语法，不能用一个连续版本上界概括能力。

### 6.4 用户批准、原文差异与待确认设计

- 2026-11-12 用户“可以下载”批准原单个 0.4.17 清单；用户“批准这 10 个探针版本（推荐）”追加批准 0.4.12、0.4.26、0.5.17、0.6.0、0.6.12、0.7.0、0.7.6、0.8.0、0.8.4、0.8.38。授权落盘后才获取对应二进制；范围不含升级 Slither、下载全部补丁或其他包。D17 更新为安装完成，D16 保留兼容性决策含义。
- r2.2 已由上游提供，本轮完整采用而未自行重设计。早期 metadata 的 SolidiFI 误称继续以实际 SmartBugs 证据更正；两份额外清单及其 metadata 引用读取沿用既有 D15 用户批准。原 `cp0_v1` 不可覆盖，因此使用 `cp0_v2`；追加记录解释历史状态，没有抹去第一次停止。
- D16 实质结论：当前 Slither 0.8.0 不处理 ErrorDefinition，两个已测自定义错误合约不能通过 D3；依据 CP0 §5b 停止。建议独立环境评估新 Slither 并保留 6c 环境，是待用户确认的后续方案；没有选择或安装新版本。若用户选择保留现有工具链，声明的支持范围必须包含语法限制，不能只写 0.8.x。
- D4/CP2：55 份 key4 重复要求保留节点重数；不直接用 key4 去重作唯一主键。6c 报告的可观察 occurrence 多重集合与本次 key4/IR 的证明范围不同。可考虑独立图内节点编号并保留 key4 作比较属性，但此建议未实施，需用户审查。
- D5：本步只调查既有建议；通用无 pragma 推断、精确 pragma 覆盖与声明区间边界仍留 CP1，不自行解决原文冲突。原 D6 频率阈值问题已由 r2.2 撤销，本轮不再作为待确认项。


### 6.5 验收、资源、未执行事项与停止

- CP0 测试最终 **32 passed、0 failed、0 skipped**（pytest 0.83 秒），初轮 31 passed。DFG v2 **2653 passed、9 warnings**（174.88 秒），仅既有 dgl/networkx 弃用提示。命令为 `python -B -m pytest -q -p no:cacheprovider compile_repair/tests` 及 `python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests`，实际另带独立 basetemp；精确命令、退出码与进程耗时见 `cp0_continue_v1/tests_cp0_v1.json`、`tests_cp0_v2.json`、`tests_dfg_v2_v1.json` 及对应日志。
- 六份开发边界输入在 `cp0_matrix_smoke_v2` 全通过（6.970 秒），第一轮 JSON 区间 TypeError 的现场保留。正式 cp0_v2 只执行一次，CLI rc2 是 D16 触发的受控停止；允许范围内的全部调查已运行，不把 D16 或用户审查写成已通过。
- 最终不变量审计：`_code_refs()` 354/354 未变，846/846 源码未变，9 个生产文件 ≤30、layering 通过；实现与七个 fixture 哈希仍与正式运行一致，正式 seal 校验通过，原 cp0_v1 report/seal 不变；Slither 0.8.0、crytic-compile 0.2.4、solc-select 1.0.4 与全局选择状态不变。`git diff --check HEAD` 无错误，未解决冲突 0，已跟踪变更全部在 compile_repair/；证据 `final_audit.json`。六份记录文档的历史保留检查全部为 true，PROMPTS 与上游 r2.2 字节相同。
- 文档检查 v1：八份文件 **8/8 passed=True**、UTF-8 有效、中文检查通过，日志和命令在 `cp0_continue_v1/doc_check_v1.log/json`。追加检查偏移为 PROGRESS:5062、RECON:12137、CP0_REPORT:7686、CHANGE_LOG:28237；PROMPTS、HANDOVER、DECISIONS 和新 README 全文检查。命令使用 `python -B -m scripts.node_sem.doc_check --expect-cjk`。写入本段后用同参数再次检查，v2 机器记录保存在 `doc_check_v2.log/json`，仅在八项仍全通过时提交。
- 本轮只使用 CPU，OMP_NUM_THREADS=2、MKL_NUM_THREADS=2；未启动 HGT 训练，未读写 GPU 锁。下载费用上限及 LLM 费用均为 0 美元，LLM 调用 0 次。没有升级包、切换全局 solc、下载其余版本/外部语料/文档包、修改语料、写图存储或进入 CP1。
- 提交范围只包含本模块代码、文档与显式证据清单，不整体添加 pytest 临时目录。正式结果及失败现场均保留；全部检查后在 compile-repair 本地提交，信息为 `CP0 complete regression and compatibility survey; await D16`，提交号可用 `git log -1 --format=%H` 定位，并在最终答复给出；不 push。该提交保留本地 8fb81ed9 与上游 54ecc927 两个父历史。停止位置为 CP0 审查和 D16，未获得后续工具链变更批准。


## 7. 2026-11-12 CompileRepair CP0 审查与方案 r2.3（修改 AI：Claude）

### 7.1 任务、依据与范围

用户要求（2026-11-12）：Codex 已完成 CP0 并推送；执行中出现的问题记录在交接文档及 CP0_REPORT、RECON、PROGRESS、CHANGE_LOG 中，部分由 Codex 处理（是否正确待核实），部分未解决。审查方案、代码与产物，核实数据，判断处理是否正确；对错误或未解决的问题制定计划交给 Codex；全部核实后才进入 CP1。要求独立、以证据为依据，不猜测。

起点 `compile-repair@ac2b3465`（Codex 的 8fb81ed9 与合并后的续作）。审查对象：9 个生产文件（`cli.py`、`core/model.py`、`toolchain/solc.py`、`toolchain/slither.py`、`evaluation/survey.py` 等）、32 个测试、`artifacts/cp0_v2/` 的 recon.json、invocations.jsonl、cross_version.jsonl、seal.json，以及 CP0_REPORT、RECON §1–11、PROGRESS、CHANGE_LOG §4、§6、HANDOVER、DECISIONS。

修改：`PROMPTS.md`（r2.2 → r2.3）；新增 `artifacts/cp0_review_v1/`；记录：本节、`docs/HANDOVER.md`（第 0、1、4、5 节重写与第 6 节新记录）、`docs/DECISIONS.md`（D3、D4、D5、D16 更新，新增 D18，历史 6 行）、`PROGRESS.md`。没有修改模块代码与 CP0 产物。

### 7.2 实施方式和重要选择

- 复核方式：不复用 Codex 的代码，另写 `verify_cp0.py` 从 `cp0_v2` 的原始调用日志重算所有汇总数字，并逐条检查 1,692 个选定版本（升序与降序）是否有 rc0 编译记录与 D3 通过记录、是否在合取区间内、是否与下界同一小版本系列、是否 ≥ 0.4.12。另在云端用 GitHub 静态 solc 与 Slither 0.8.0 重跑 846 个文件（743 个不同源文件），用 `node_dump.py` 按 CP0 口径计算指纹，与 `invocations.jsonl` 的 `node_facts_sha256` 比较。本环境 30 个编译器中 29 个与 cp0_v2 可信清单逐字节相同，24 个升序选定版本全在其中。
- D3：CP0 的 `node_facts` 只遍历 `functions_and_modifiers_declared`。用 0.7.1 起的自由函数探针确认顶层函数在 `compilation_unit.functions_top_level` 中（0.8.0、0.8.3、0.11.6），不在上述集合中；且合约漏解析时节点为空也会“通过”。这是 r2.2 方案的缺口，不是 Codex 的实现错误。r2.3 加入顶层函数与“Slither 合约名称集合 = solc AST ContractDefinition 名称集合”。
- D4：key4 在 55 个文件中重复；以 `access_control/0x000c1000…sol` 的 `min`（`return a < b ? a : b;`）确认原因是 Slither 把三元表达式拆成两个共享起始偏移的 RETURN 节点。可选方案是加入 source length（会被跨版本长度变化破坏，28 对不同）或加入节点在 Slither 顺序中的序号；测得序号身份 678/678 稳定，选后者为 key5。
- pragma 覆盖：r2.2 的 3.2 第 6 行写“越过声明区间禁止”，3.3 第 6 条却规定在区间内无可用编译器时使用，这时必然越过区间，两处自相矛盾（Claude 的错误）。r2.3 改为：这是唯一允许离开区间的情形，只在下界所在小版本系列内、按与下界的距离从近到远，记 rewrite。
- D16：CP0 只测了 Slither 0.8.0。补测 0.8.3、0.9.6、0.10.4、0.11.6 在相同编译器上的语料结构与 6 个特征探针，节点类型按各版本 `NodeType` 枚举名归一后比较。由于冻结的 `validate_slither._mapping` 只认 dict，新版 Slither 不能直接用冻结代码抽取，所以 6c 回归改为在 0.8.0 下精确重放，生产工具链单独选择。
- 新增 D18：补齐编译器后，pragma 覆盖只剩官方没有构建或低于 0.4.12 的精确 pragma 会用到。
- CP1：要求版本策略只实现在 `rules/environment.py`，CP0 中 `evaluation/survey.py` 的选版代码改为调用它，避免两份实现；验收为复现 cp0_v2 的 846 个升序选定版本。
- 新增 CP0.1（4.2b 节），分 A（代码与 mando 重验，无需授权）、B（D16 环境，需授权）、C（D18 编译器，需授权）三部分，缺授权时做到前一部分停下。

### 7.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 输入 SHA256 与 git 语料 | 846 个，0 差异 | verify_cp0.json |
| 规则 A | 821 通过、22 失败、3 未安装 | 同上 |
| 升降序 / 移动 / 跨系列 | 617 / 44 / 0 | 同上 |
| 1,692 个选定版本检查 | 违例 0 | 同上 |
| 跨版本 678 对 | key4 678、IR 678、length 650 相同 | 同上 |
| 168 个无第二端点文件 | 全部是精确 pragma | 同上 |
| 与 cr_pre_v1 对账 | ok→passed 806、ok→unavailable 1、fail→failed 10、unavailable→passed 15 / failed 12 / unavailable 2；与 RECON §9 一致 | 同上 |
| 6c 的 17 个异常 | 集合相同，全部在升序选定版本上通过 D3 | 同上 |
| Slither 0.8.0 指纹 | 743/743 与 Codex 相同 | ordinal_and_s083_analysis.json |
| 序号身份 | 678/678 稳定（含 IR）；含重复节点的 31 对全部稳定 | 同上 |
| 6c 版本 | 239 个已比较文件中 238 个与当前升序选定相同；239 个版本全部已安装 | recon.json 与 6c 报告对照 |

Slither 版本（743 个不同源文件；slither_versions_corpus.json、feature_probes.jsonl）：

| Slither | 结构与 0.8.0 相同 | 结构差异 | 有序 IR 相同 | 失败 | 特征探针 |
|---|---:|---|---:|---:|---|
| 0.8.3 | 743 | 无 | 482 | 0 | 4/6 |
| 0.9.6 | 721 | 只缺合成的 slitherConstructorConstantVariables() 的 47 个入口节点 | 62 | 0 | 6/6 |
| 0.10.4 | 369 | 多 1,999、少 47 | — | 3 | 6/6 |
| 0.11.6 | 369 | 多 1,999、少 50 | 51 | 3 | 6/6 |

0.8.0 自身 6 个特征中失败 4 个（自定义错误、UDVT、顶层 using、全局运算符）；Codex 测得的 `ErrorDefinition` 失败与此一致。transient 探针在所有版本都构造成功，不说明正确建模。Slither 的使用者只有 `scripts/DFG/dfg_v2/` 的验证脚本。

未证明：以上 0.8.3 及更新版本的数字在用户环境（Python 3.7/3.8、solc-select 安装的编译器）是否相同，由 CP0.1 B 部分复核；0.9.6 在新环境中导入冻结 `versioning.py`（依赖 tree_sitter）是否可行。

### 7.4 用户批准、原文差异与待确认设计

- Codex 处理正确的部分：metadata 来源更正为 SmartBugs `versions.csv`（核对 `recorded_version` 读取的列）；重复 key4 保留多重集合而不去重；D16 未决时停下；安装只限用户批准的 11 个版本；把本地安装请求改编号为 D17。
- 方案中的错误（Claude）：1.2 节 metadata 来源；D3 缺顶层函数与合约覆盖；D4 key4 不唯一；3.2 第 6 行与 3.3 第 6 条矛盾。均已在 r2.3 更正。
- 合并遗留：`DECISIONS.md` “合并 r2.2 的上游历史”表中 D2、D5、D6、D16 四行引用 “CHANGE_LOG §4”，以及 `HANDOVER.md` r2.2 交接记录末尾与 `PROGRESS.md` r2.2 一节中的 “§4”，合并改号后应为 §5；记录只追加，在 DECISIONS 历史中加一行更正，不改旧文。`HANDOVER.md` 第 4 节在合并时丢失的条目已在本轮重写中恢复。
- 待用户决定：D5（建议确认升序）、D16（推荐 0.9.6 独立环境，0.8.0 只做 6c 重放）、D18（建议补齐 59 个编译器）。D9、D10 待确认，D12、D13 待定。

### 7.5 验收、资源、未执行事项与停止

- `python3 -B -m scripts.node_sem.doc_check --expect-cjk compile_repair/PROMPTS.md compile_repair/docs/HANDOVER.md compile_repair/docs/DECISIONS.md compile_repair/docs/CHANGE_LOG.md:46726 compile_repair/PROGRESS.md:8269 compile_repair/artifacts/cp0_review_v1/README.md`：6 个文件全部 passed=True（HANDOVER、DECISIONS 本轮有重写，按整文件检查；CHANGE_LOG、PROGRESS 只追加，按追加前字节数检查）。
- 资源：云端 CPU；5 个 Python 虚拟环境（只在本会话临时目录）；没有 LLM 调用，费用 0。
- 未执行：模块代码修改；用户环境中的任何运行；编译器或包安装（用户环境）。
- 停止：CP1 不能开始。顺序为用户决定 D5、D16、D18 → Codex 执行 CP0.1 → Claude 审查 → CP1。本轮提交并 push 到 `compile-repair`。

## 8. 2026-11-12 CompileRepair CP0.1 A：D3 加强、key5 与固定版本重验（修改 AI：Codex）

### 8.1 任务、依据与范围

用户要求先细读更新的 PROMPTS §4.1 与全文，在既有实现上执行 CP0.1，重要不合理处登记，替代方案先咨询，并持续写交接和训练/运行改变文档。按 r2.3 §4.2b 完成无需新授权的 A1/A2/A3；B/C 缺 D16/D18 授权，未执行。起点 compile-repair@61a3cb6a944140108763442999bbfd4199f53ca3，pull --ff-only 返回 Already up to date，工作树 /home/zhao/SmartContract/ge-sc-llm-compile。

文件完整清单（相对 compile_repair/）：修改 toolchain/slither.py、evaluation/survey.py、cli.py、tests/test_toolchain.py；新增 tests/test_slither_v2.py、tests/fixtures/ternary.sol、free_function.sol、CP0_1_REPORT.md；更新本节、docs/HANDOVER.md 当前区与交接、docs/DECISIONS.md 当前表与历史、PROGRESS.md。新增证据 cp0_1_v1/、cp0_1_development_v1/，逐文件清单见 seal 和 artifact_index.json。生产文件 9、测试文件 4、fixture 9，无表外生产模块。

模块面向未来任意合约，MANDO 回归不决定覆盖范围。scripts/**、原作者代码、原始输入、EdgeSem 文件、旧 CP0 产物/报告、PROMPTS、根目录交接/训练文档均未修改。未读取新的标签/图/模型，没有图存储或训练。

### 8.2 实施方式和重要选择

- read_mapping 统一 dict/对象形式；不支持的映射显式失败，缺 filename/start 使 D3(a) 失败。检查声明函数/修饰器与 compilation_units.functions_top_level。原始 nodes 顺序内编号后再排序，key5 使用 NodeType 枚举名，保留重数与有序 IR；node_facts_v2 写明声明种类，length 只诊断。
- D3(b) 从 crytic-compile 已保存 AST 读取合约、接口、库名称重数，支持旧式 ContractDefinition/attributes.name 与 compact nodeType/name；缺输入 AST 或非法结构拒绝。与 D3(a) 独立记录。使用保存 AST 而不另跑 solc 是 A1 允许的选择，直接绑定本次解析输入且减少一次调用，不是替代方案。
- 先用真实 0.4.12/0.8.0 检查本机 API：Slither.compilation_units 与 unit.functions_top_level 均为 list；crytic unit.asts 键为绝对路径字符串。0.7.6 自由函数正例验证真实遍历，未导入审查证据脚本。
- profile 仅配置 regression_6c 0.8.0/0.2.4，实际版本不符或 production 未配置则拒绝。CP0 投影保留旧 key4、str(node.type)、IR、length、排序与 JSON 编码，仅用于 cp0_v2；新指纹另写 node_facts_v2_sha256。
- import 复用 validate_slither._compile，冻结文件 SHA256 为 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8；没有复制/monkeypatch。versioning.py、frontend.py 未变，SHA 分别为 130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18、cfe6ee2a975abeb374e2ce17f0f7c47c400e823cfa8ca05c96d3e4657d161207。
- 新重验先校验 CP0 seal/绑定文件和全部输入 SHA，只跑原选定版本与两端点，相同文件/版本缓存，不失败重试。gzip 保留完整节点供 B 使用；每次调用和全部差异归档。旧调查入口的后续输出标为 v3，避免 key5 内容冒用 CP0 v2 schema。
- 编辑过程：同目标 delete/add patch 被拒绝，两次 JavaScript 模板分隔符错误发生在执行前，Windows apply_patch 又因 WSL reparse point 无法读目标。改用显式 wsl.exe Python UTF-8 写入及安全模板解决，均未修改冻结文件；见 development_notes.json、document_write_note.json。无测试失败或正式运行失败，无自动重试。

### 8.3 实测与数据结论

输入为已核验 cp0_v2/recon.json（SHA256 bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6），旧 seal 为 16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b。846 个源文件 SHA 一致，使用原 ascending/lowest_d3/highest_d3，不重新选版。环境 mando Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4，37 个编译器身份再次核验。

| 指标 | 实测 | 来源 |
|---|---:|---|
| 新 D3 / 旧投影相同 | 846/846、846/846 | cp0_1_v1/revalidation.json |
| D3(a)/(b) 失败、顶层函数 | 0/0、0 | summary |
| 跨版本 key5 / 有序 IR | 678/678、678/678 | cross_version.jsonl |
| 重复 key4 双端文件 / 相同 | 31/31 | 跨版本记录 |
| 选定版本重复 key4 文件 | 55 | 逐文件记录 |
| length 相同/不同 | 650/28 | 仅诊断 |
| 直接 solc / Slither | 各 1,546 次均成功 | invocations.jsonl；独立重新计数 |
| 归档节点 / 重复 key5 组数 | 201,044 / 0 | revalidation_audit.json |
| 正式 / 外层进程耗时 | 609.965 / 616.665 秒 | revalidation.json、a3_run.json |
| 所选 solc / Slither 累计 | 81.413 / 236.891 秒 | runtime |
| B / C | 未执行 | 缺授权 |

新 seal SHA256 为 c28b7c7bc5269d2892027542c14724b1063a043c6d3322996a88f0146d186ff2；revalidation.json 为 97876bfd95e931058efa2c45f5675e6158bf551594a35ee150ae56adc5283ff3。节点 gzip 3,635,155 字节，1,546 组指纹全部与调用 journal 一致。DFG 测试与 A3 部分重叠，耗时只描述本次观测；生产/CP2 时间、全部语法、图边与任意项目语义未证明。

真实 fixture：三元 RETURN 共用 start=127、序号 1/2；0.7.6 有 1 个自由函数且 D3 通过；0.4.12 旧式和 0.8.0 compact AST 都通过并复现旧探针投影。0.4.11 虽编译/构造成功，但 5 个节点缺 filename，D3(a)/(b) 均失败；0.4.13 同输入通过。见 fixture_results.json。

### 8.4 用户批准、原文差异与待确认设计

用户明确要求执行 CP0.1；按原文 A 无需新授权。此前两次批准只覆盖已装的 11 个 solc，不扩张解释为新环境或其余 59 个版本。D3 更新本机 A 验证完成，D4 补入本机 key5 证据；D16/D18 仍待用户决定，没有伪造 approved 的 authorization.json。

具体请求已列：environment_installation_request.json 为独立 Python 3.8.20、Slither 0.9.6、crytic-compile 0.3.11、tree-sitter 0.20.4 环境，含工具版本、来源与传递依赖留档要求；compiler_installation_request.json 为缓存官方快照 0.4.12–0.8.38 缺少的 59 个精确版本，含 URL、SHA256、Keccak256。两者费用上限 0 美元，C 只在 B 通过后执行。支持范围内当前 33/92，另 4 个旧负对照不算覆盖；未联网刷新目录。

待核对：B 原文“0.8.24 transient”与审查 f0828_transient.sol 的 >=0.8.28 高级变量语法边界不同，执行 B 前核对官方文档；如需拆探针或改原文，先咨询用户。这里仅登记差异，未实施替代，未修改 PROMPTS，也未因此阻碍 A。A 无偏离原文的验收项。

CP1 仍需 D5/D16/D18 决定与 CP0.1 审查。精确 pragma 指向缺失版本、官方无构建或低于 0.4.12 等情形仍可能触发未来第 6 步；本次 846 文件已有区间内成功版本，未做 rewrite。不从回归集成功推导任意输入均可修复。

### 8.5 验收、资源、未执行事项与停止

- A1/A2/A3 预期与实测全部相同，0 个差异；B/C 未执行。正式运行一次，CLI rc0 仅代表 A 完成；状态为 complete_a_awaiting_b_authorization，不等于整个 CP0.1 完成。
- python -B -m pytest -q -p no:cacheprovider compile_repair/tests：55 passed、0 failed、0 skipped，4.79 秒；同参数运行 scripts/DFG/dfg_v2/tests：2653 passed、0 failed、0 skipped、9 warnings，188.01 秒。先行工具链测试 37 passed、1.02 秒。实际另带新 basetemp，完整命令/日志在 pytest_*.json/log；layering 通过，生产文件 9 个，未超过 30。
- 最终不变量与文档检查在提交前完成，结果追加在本段末尾；依据 final_audit.json、doc_check_v*.json/log。追加区间使用 baseline.json 的原始字节数，不能只看 doc_check 进程退出码。
- 仅 CPU，OMP_NUM_THREADS=2、MKL_NUM_THREADS=2。无包/编译器安装升级卸载、LLM 调用、HGT 训练、GPU 锁操作、源码改写、外部语料获取或图存储；成本 0 美元。mando 和全局 solc 状态不变。
- 全部检查通过后本地提交，标题 CP0.1 complete A revalidation; await D16/D18 authorization，提交号由包含本节的提交确定并在最终答复给出；不 push。旧 CP0 ac2b3465 已按此前用户要求推送，本轮从上游 61a3cb6a 开始，HANDOVER §2 当前状态已更正，旧历史不回写。停止在 B/C 授权前。

- 终审补记：第一次历史保留审计因 PowerShell 默认 OutputEncoding 损坏中文标题字面量，在查找标题时抛 ValueError，未生成审计结果、未改文档。保留 audit_attempt_v1_failure.json；改为 ASCII 标题前缀定位原始字节后完成核对，不放宽判据，也未重跑 A3。此为检查脚本编码问题，不是代码/语料验收差异。
- 最终审计通过：354/354 冻结代码引用、846/846 输入、37/37 编译器不变；全部旧模块证据未漂移，4 份记录历史逐字保留；生产代码与 A3 SHA 一致，9 个生产文件，未解决冲突 0，git diff --check 通过，跟踪变更均在 compile_repair/。包版本及未设置的全局 solc 状态不变。依据 final_audit.json。
- 文档检查 v1 的 6/6 项 passed=True、UTF-8/中文全部通过。检查命令为 python -B -m scripts.node_sem.doc_check --expect-cjk，目标为 CP0_1_REPORT、HANDOVER、DECISIONS、开发 README 全文，以及 CHANGE_LOG:54883、PROGRESS:9269 追加区间。写入本补记后按同参数执行 v2，逐项检查 passed；日志与精确命令保存在 doc_check_v2.log/json，仅在 6 项仍全通过时提交。


## 9. 2026-11-13 CompileRepair CP0.1 A 审查与方案 r2.4（修改 AI：Claude）

### 9.1 任务、依据与范围

用户要求（2026-11-13）：Codex 已完成 CP0.1 并推送；执行中的问题记录在交接文档与 CP0_1_REPORT、PROGRESS、CHANGE_LOG、DECISIONS 中，部分已处理（是否正确待核实），部分未解决。审查方案、代码与产物，核实数据，判断处理是否正确；对错误或未解决的问题制定计划交给 Codex；全部核实后才进入 CP1。要求独立、以证据为依据，不猜测。

起点 `compile-repair@18940a8a`。审查对象：`toolchain/slither.py`（248 行）、`evaluation/survey.py` 的 `load_cp0_baseline`、`revalidate_cp0`、`cli.py` 的 `revalidate-cp0`、`tests/test_slither_v2.py` 与两个新 fixture；`artifacts/cp0_1_v1/`（seal、invocations、cross_version、revalidation、node_facts_v2.jsonl.gz）与 `cp0_1_development_v1/`（两份安装请求、baseline、final_audit）；CP0_1_REPORT 与 CHANGE_LOG §8。

修改：`PROMPTS.md`（r2.3 → r2.4）；新增 `artifacts/cp0_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（第 0、1 节重写，第 4 节第 15 条改写、新增第 16 条，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（D16、D18 更新，历史 4 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 9.2 实施方式和重要选择

- 复核方式：另写 `verify_cp01.py`，从 seal、journal 与 gzip 归档重算全部验收数字，并把 1,546 组节点与 Claude 在 CP0 审查时用 `node_dump.py` 独立导出的 Slither 0.8.0 节点（按 Slither 节点顺序自行编序号，节点类型按枚举名归一）逐组比较。两边代码互不依赖，结果相同才能说明 key5 的实现与归档正确。
- 代码兼容性：用 `port_probe.py` 在 0.8.0、0.8.3、0.9.6、0.11.6 下直接调用 Codex 的 `node_facts` 与 `contract_coverage`，检查对象形式 source_mapping 与 crytic-compile 0.3.11、0.4.2 的 AST 接口，为 B 部分提前排除接口问题。
- transient：查官方 0.8.24 与 0.8.28 发布说明核实 Codex 登记的边界问题，确认是方案错误。
- D16 重新测量：r2.3 的推荐只依据 6 个探针。为核实 B 部分的预期，把探针扩展到 19 个（0.7.1–0.8.29 的有文档的语法，含 Yul 内置函数、文件级 event、selector、require 自定义错误、layout at），并用 Codex 的 D3 代码在 0.9.6、0.11.6 下重跑 846 个文件。结果改变了推荐：0.9.6 不能分析 6 种 0.8.7 起的合法写法，且不会再更新；0.11.6 的失败只在 0.4.x 的一种写法上，这类代码不会再新增。模块目标是检测时的任意输入，因此推荐 0.11.6；由于代价（3 个 MANDO 文件、图结构变化、Python ≥ 3.10）真实存在，保留 0.9.6 作为备选，由用户决定。
- 失败频率：用文本启发式统计 DAppSCAN、Trace、MANDO 中两类失败写法的出现次数，作为决定的参考；这只是上界，不是编译结果。
- 0.11.6 的失败写法：在工作副本上试验语义等价改写，确认可行但会改变节点数，因此在 3.2 节新增第 10 行（rewrite 等级、只在 D16 选 0.11.6 时适用，CP6 实现），CP3 分类表增加“Slither 侧失败”一类；B 部分只试验、不实现规则。
- B 部分：按 D16 的两种选择分别给出环境、预期与停止条件；增加 production profile、`importlib.metadata` 回退与 crytic-compile 平台记录；固定 solc-select 1.0.4，不在新环境运行 install/use，避免影响 mando 共用的 `~/.solc-select`。
- D18 请求：从 GitHub 上的官方 solc-bin 仓库取得 `linux-amd64/list.json`（binaries.soliditylang.org 在审查环境中不可达），其 SHA256 与 Codex 缓存的官方索引逐字节相同，再逐项比较 59 个版本。

### 9.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| cp0_1_v1 seal | 4 个文件哈希一致 | verify_cp01.json |
| 归档自身指纹 | 1,546/1,546 | 同上 |
| key5 + 有序 IR 与独立导出 | 1,546/1,546 相同 | 同上 |
| 组内重复 key5 | 0 | 同上 |
| solc rc0 / Slither 构造 / D3 / D3(b) | 1,546 / 1,546 / 1,546 / 1,546 | 同上 |
| 所用（源文件, 版本）对 | 1,369，与 cp0_v2 选定与端点集合缺 0、多 0 | 同上 |
| CP0 投影 | 1,546/1,546 与 cp0_v2 相同 | 同上 |
| 节点总数 | 201,044 | 归档 |
| AST 格式 | compact 1,500、legacy 46 | verify_cp01.json |
| 19 个探针通过数 | 0.8.0 4、0.8.3 9、0.9.6 13、0.10.4 18、0.11.6 19 | extended_probes.jsonl |
| 846 个文件 D3（0.9.6 / 0.11.6） | 846 / 843（3 个 0.4.24 AssertionError） | compare_prod.json |
| 与 0.8.0 结构差异（0.9.6） | 23 个文件，只少 48 个合成入口节点 | 同上 |
| 与 0.8.0 结构差异（0.11.6） | 435 个文件：多隐式 RETURN 2,182、ENDASSEMBLY 128；少合成入口节点 48、重数变化 EXPRESSION 6 | 同上 |
| D18 请求 | 59 个版本 URL、SHA256、Keccak256 与官方索引 0 差异；加已装 33 个 = 92 | check_install_request.json |
| 文本频率（上界） | DAppSCAN：0.9.6 失败类 1、0.11.6 失败类 6；Trace：0.9.6 失败类至多 5 | prev_*.json |

未证明：用户环境（Python 3.10、solc-select 安装的编译器）中的上述数字，由 CP0.1 B 复核；0.11.6 改写规则的语义等价性须在 CP6 逐类论证；Codex 环境中 55 个测试在 Claude 环境只复现了不依赖 tree_sitter 与 pycryptodome 的 30 个（4 个失败是本环境缺 pycryptodome）。

### 9.4 用户批准、原文差异与待确认设计

- Codex 处理正确的部分：A 的实现与验收；对 A1 中“AST 取得方式由你决定”的选择（使用 crytic-compile 已保存的 AST，不额外调用 solc）合理，并有两种 AST 格式的实证；缺授权时停在 B、C 之前；把 transient 边界问题登记为待核对而不自行改方案；两份安装请求内容正确。
- 方案中的错误（Claude）：4.2b B 的“0.8.24 transient”；D16 推荐依据的探针太窄。均在 r2.4 更正。
- 记录小问题：Codex 的交接记录与 CHANGE_LOG §8.5 写“不 push”，实际提交已推送到远端；以本节为准，不改旧文。
- 待用户决定：D5（建议确认升序）、D16（推荐 0.11.6，备选 0.9.6）、D18（建议补齐 59 个）。选 0.11.6 时，Codex 已提交的环境请求须改写后再授权。

### 9.5 验收、资源、未执行事项与停止

- `python3 -B -m scripts.node_sem.doc_check --expect-cjk compile_repair/PROMPTS.md compile_repair/docs/HANDOVER.md compile_repair/docs/DECISIONS.md compile_repair/docs/CHANGE_LOG.md:64515 compile_repair/PROGRESS.md:11189 compile_repair/artifacts/cp0_1_review_v1/README.md`：6 个文件全部 passed=True（HANDOVER、DECISIONS 有重写，按整文件检查；CHANGE_LOG、PROGRESS 只追加，按追加前字节数检查）。
- 资源：云端 CPU，沿用 5 个 Python 虚拟环境；只读访问 PyPI 与 GitHub 上的官方 solc-bin 索引；没有 LLM 调用，费用 0。
- 未执行：模块代码修改；用户环境中的任何运行；任何安装。
- 停止：CP1 不能开始。顺序为用户决定 D5、D16、D18 并授权 → Codex 执行 CP0.1 B、C → Claude 审查 → CP1。本轮提交并 push 到 `compile-repair`。


## 10. 2026-11-13 CompileRepair 用户决定 D5、D16、D18（修改 AI：Claude）

### 10.1 任务、依据与范围

用户 2026-11-13：“I have followed the approach you recommended.”（针对 r2.4 的三项推荐）。只修改记录：`docs/DECISIONS.md`（当前表 D5、D16、D18 与历史 3 行）、`docs/HANDOVER.md`（第 0、1 节与第 6 节新记录）、本节、`PROGRESS.md`。

### 10.2 实施方式和重要选择

- D5：区间内升序。D16：生产 Slither 0.11.6 + crytic-compile 0.4.2，Python 3.10.x、solc-select 1.0.4、tree-sitter 0.20.4 独立环境；mando 中的 0.8.0 只做 6c 精确重放。D18：安装 59 个编译器，B 通过后执行（C 的原有前提）。
- Codex 在 `cp0_1_development_v1/environment_installation_request.json` 中的 0.9.6 请求不再适用；按 4.2b 节 B 部分，Codex 先写 0.11.6 的请求与授权文件再安装。

### 10.3 实测与数据结论

本轮没有运行；依据的数字见 §9.3。

### 10.4 用户批准、原文差异与待确认设计

用户批准上述三项。D9、D10 仍待确认，D12、D13 待定。

### 10.5 验收、资源、未执行事项与停止

doc_check 全部 passed 后提交并 push。下一步 Codex 执行 CP0.1 B、C。


## 11. 2026-11-13 CompileRepair CP0.1 B 完成；C 安装完成、兼容性失配停止（修改 AI：Codex）

### 11.1 任务、依据与范围

用户要求先 pull --ff-only，再阅读 PROMPTS r2.4 全文、共享上下文、HANDOVER §0–5、DECISIONS 与本文件 §9/§10，只执行 CP0.1 B、C，不重做 A。起始 compile-repair@897fbd03116040ddbc8d106db1b844624f512091，pull 返回 Already up to date；D5、D16、D18 已由用户于 2026-11-13 明确批准。授权在 cp0_1_env_v1/authorization.json、cp0_1_compilers_v1/authorization.json 先行记录，C 另以全部 B 门槛通过为前提。

文件清单：生产代码仅 toolchain/slither.py；修改 tests/test_slither_v2.py 与 tests/test_toolchain.py，新增 tests/test_production.py；tests/fixtures/features/ 原字节新增以下 19 个文件：f0807_free_function.sol, f0813_using_global.sol, f0819_user_operator.sol, f0828_transient.sol, f084_custom_error.sol, f088_udvt.sol, h0811_encodecall.sol, h0815_event_selector.sol, h0818_prevrandao.sol, h0822_file_event.sol, h0824_blob.sol, h0826_require_error.sol, h0829_layout_at.sol, h084_error_selector.sol, y0818_prevrandao_asm.sol, y0824_blob_asm.sol, y0824_mcopy.sol, y0824_tstore_asm.sol, y087_basefee.sol。文档追加 CP0_1_REPORT.md 的 B/C（A 不变）、PROGRESS.md、本节，更新 docs/HANDOVER.md §0–5 并追加 §6 四段交接，更新 docs/DECISIONS.md 当前状态并追加历史。新证据仅 cp0_1_env_v1/ 与 cp0_1_compilers_v1/，各自 README 与 cp0_1_env_v1/file_inventory.json 提供完整文件清单。未修改 PROMPTS、scripts/**、原作者代码、任何原输入、旧产物、根目录交接/训练改变文档；未实现 CP1 或 CP6 第 10 行规则。

### 11.2 实施方式和重要选择

toolchain/slither.py 增加 production=(0.11.6,0.4.2)，保留显式版本拒绝；check_profile 在 Python 3.10 使用标准库 importlib.metadata，在 3.7 回退 importlib_metadata，两条路径由各自真实环境验证。production 采用公开 CryticCompile 与 Slither 组合，传入与原调用相同的 solc 绝对路径和 solc_disable_warnings，以便 Slither 解析失败时仍保留实际平台；其余 D3/key5 实现未改。regression_6c 继续复用冻结 _compile，原文件 validate_slither.py SHA256 为 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8；没有复制或 monkeypatch，真实构造等价测试按 key5、有序 IR、length 一致。

独立环境采用获批 Python 3.10.x 中的 3.10.21，复用并校验缓存的 32 个 conda 包，--offline --copy 安装，不改 mando。六个直接包精确固定为 slither-analyzer 0.11.6、crytic-compile 0.4.2、solc-select 1.0.4、tree-sitter 0.20.4、pycryptodome 3.20.0、pytest 7.4.4；必要依赖经 PyPI 解析后锁定 URL/版本/SHA，再按 --no-deps --require-hashes 安装，全部包与来源见 environment.json、pip_freeze.txt 和锁文件。第一次只解析时发现用户 site-packages 混入，尚未安装，改为仅新环境设置 PYTHONNOUSERSITE=1 后重新解析，未修改用户包；isolation_adjustment.json 与两份原始解析均保留。生产环境 57 个 Python distribution 均来自新 prefix，pip check 通过。

19 个 probe 从审查目录原字节复制，按源码 pragma 下界选择适用版本；f0807_free_function 实际 >=0.7.1，h0811_encodecall 实际 >=0.8.12，未按简写文件名推断。冻结 frontend.parse/versioning.interval 在两套环境分别处理 846 个输入，不重新编译 A；语言库路径与 SHA 完全相同。三个 reentrancy 工作副本仅在新 artifacts/rewrite/ 试验单处 bool 标量改写，按原要求记录前后 SHA、字节位置与节点差异，不形成生产规则。

B 门槛写入 B_acceptance.json 后才下载 C 的 59 个官方二进制；先核官方 SHA256/Keccak256，再排他创建新目录/文件并检查 --version，独立追加信任清单，复用 load_additions 再验链。全程不运行 solc-select install/use，不改已有 ~/.solc-select 文件或全局选择，不改网络配置，联网只经既有代理。开发中一次新测试 regex 双转义导致收集错误，修正转义后通过，失败日志保留，未改变验收条件；初始受限 WSL 读调用 E_ACCESSDENIED 改为获审显式 WSL 调用解决，未遇到无法绕开的自动审批拒绝。正式 B 无非预期结果，C 在首个非预期结果停止，均未自动重试。

### 11.3 实测与数据结论

| 测量 | 结果 | 证据 |
|---|---|---|
| 输入/选版身份 | cp0_v2 的 846 文件与 selection.ascending；逐次绑定源码/二进制 SHA | production_invocations.jsonl |
| 区间等价 | 846/846；tree-sitter 0.20.4；库 SHA f424e0d52ebcdda4932a973af5357874fedd0348c78d87b1575bf15ee539d967 | interval_equivalence.json |
| B 直接 solc / D3 | 846 rc0；843 D3；三个指定 0.4.24 AssertionError | production_comparison.json |
| B 实际平台 | 846/846 solc，含三次解析断言失败 | production_invocations.jsonl |
| B 结构 | 435 文件不同；+2182 RETURN、+128 ENDASSEMBLY、−48 合成入口、−6 EXPRESSION；均符合审查 | structure_differences.json |
| B 有序 IR | key5+IR 全同 56；共有 key5 上 783 文件、24823 节点不同；列前 20 例，仅统计 | ir_differences.json |
| B 特征 | 19 特征、当前 23 组合全通过 | feature_probes_B.json |
| B 工作副本 | 两套环境各 3/3 D3；节点 11→10、11→10、6→5 | rewrite_production.json、rewrite_regression_6c.json |
| B 耗时 | wall 292.588 秒；solc 75.771 秒、Slither 189.683 秒 | production_comparison.json |
| C 安装 | 59/59 双哈希和版本通过；722168656 字节；335.193 秒 | installation_summary.json |
| C 安装覆盖 | 支持快照 92/92；总 96 含 4 个历史负对照 | coverage.json |
| C 验证 | 计划 496，执行 225：224 过、1 失败、271 未运行；wall 12.224 秒 | compatibility.json |
| C 完整版本矩阵 | 45 版全过；0.8.24 部分失败；13 版未开始 | compatibility.json.per_version |
| 不变量 | 模块外 27845 文件、旧产物 204、旧 solc 37、mando 元数据 205 差异 0；code_refs 354 项不变 | cp0_1_env_v1/frozen_audit.json |

C 失败为 h0824_blob.sol 在 solc 0.8.24 下 rc1，Error: Undeclared identifier. Did you mean "blockhash"? 指向 blobhash(0)，因此未运行 Slither。源码 SHA c9e90c95e2aa4ff6fca95636caf80ceca31c2ba40cdefdfcfa204b18de141cf2，二进制 SHA fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f；完整命令与 stderr 见 compatibility_invocations.jsonl。成功编译和 D3 不证明 transient 或全部图边的语义正确，安装 92/92 也不证明整个特征矩阵通过。CP2 可参考固定版本编译/D3 265.454 秒的本次观测，不包含选版、修复、存储、跨版本或 6c 重放。

### 11.4 用户批准、原文差异与待确认设计

用户 2026-11-13 原话“I have followed the approach you recommended.”对应 r2.4 三项推荐，本轮又明确指定版本、环境路径、59 版清单、B 通过再 C、0 美元上限及禁止操作。本次执行完全在该授权范围内；D5 升序仍留给 CP1 实现，D16 的旧 0.9.6 请求作废但保留未改，D18 的安装已完成。没有增设新模型、LLM、外部语料、文档下载、包升级或全局 solc 操作。

与原文不一致的验收只有 C 的首个 0.8.24+h0824_blob 结果。按用户“与预期不符时按原文停下报告，不要放宽判据或自行换方案”以及 §4.1“失败就停，保留现场，不自动重试”，余下 271 组停止，未改源码、probe、版本下界、EVM 参数或成功标准。当前异常发生在 solc 阶段，不是 Slither 的 D3 映射失败；不能用后者的已知 3 份断言例外掩盖。

待审查建议（未实施）：核对 h0824_blob 高级语法引入版本与 EVM 配置，以及同类 probe 下界证据；需要任何参数或下界修订时先向用户确认，确认后以新批次验证剩余及受影响组合。不能仅凭该错误断言“加 EVM 参数即可解决”。B 通过、C 安装完成、C 兼容性未通过的状态分别保留，CP0.1 整体未通过，CP1 不开始。

### 11.5 验收、资源、未执行事项与停止

B 的 profile、冻结导入/846 区间等价、固定版本 846 对照、23 特征组合、3 个工作副本、实际 solc 平台和环境不变检查均通过 B_acceptance.json 门槛。C 安装验收全部通过，兼容性验收失败后停止；未执行 271 组，未重跑 A/CP0 或改写原源码，未实现 CP1/CP6。所有命令为 CPU，OMP/MKL=2，无训练、GPU 锁、图存储、LLM，费用 0 美元。

B 阶段的模块测试命令为各环境 python -B -m pytest -q -ra -p no:cacheprovider compile_repair/tests，实际另带新批次专属 basetemp，生产运行还带 -x；production 77 passed/6 skipped（8.31 秒），mando 58 passed/25 skipped（1.96 秒）。production 跳过一项 Python 3.7 路径及五项 0.8.0 专属检查，mando 跳过一项标准库路径及 24 项 production 检查；与 profile 无关测试均通过。mando 的 scripts/DFG/dfg_v2/tests 同参数为 2653 passed/9 warnings（193.29 秒），均为既有弃用警告，test_layering 通过。上述测试在 C 新装 59 版之前执行；C 停止后没有把未执行的扩大矩阵或后续重测记为通过。

强制文档共七份：CP0_1_REPORT、PROGRESS、CHANGE_LOG 按原字节偏移检查新增区；HANDOVER/DECISIONS 因当前表更新检查整文件；两个新 README 检查整文件。doc_check 的实际结果及最后检查在本节后续追加，不凭进程退出码单独判定。仅 compile_repair/ 允许变更，生产 Python 仍 9/30；全部记录与最终审计后以 CP0.1 开头本地提交，不 push，提交号在最终答复给出。


文档检查实测：doc_check_v1.jsonl 的七行均为 passed=true，逐行解析确认（进程 rc0），追加前偏移分别为 CP0_1_REPORT 10942、PROGRESS 12241、CHANGE_LOG 73084 字节；HANDOVER、DECISIONS 和两个 README 检查整文件。写入本段后再按相同目标执行 doc_check_v2，并保留完整输出与逐行判定；最终结果见 final_audit.json。git diff --check 已通过，A 前缀及历史保留检查通过后再封存和本地提交。


暂存检查补记：全部 112 个初始清单文件暂存后，git diff --cached --check 在 production_batch.stderr.log 的 554、562、571 行报告三处“space before tab in indent”。它们是 Slither 三个已知 AssertionError 诊断打印的原始 Solidity 行，不是本轮源码格式错误；为保持证据字节，日志不裁剪、不改写。保留完整检查 rc2 和三条诊断，另对除该单一原始日志之外的全部暂存文件运行同一检查，rc0，见 final_staging_audit.json；未改变 D3、C 的停止标准或编译参数。该补记与最终清单写入后再做七份 doc_check_v3；最终封存为两批 seal_v2.json，原 seal.json 保留为第一次封存快照，完整提交清单为 file_inventory_v2.json。


## 12. 2026-11-13 CompileRepair CP0.1 B、C 审查与方案 r2.5（修改 AI：Claude）

### 12.1 任务、依据与范围

用户要求（2026-11-13）：Codex 已按推荐方案完成修改；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后才进入 CP1。起点 `compile-repair@33c23a3b`。审查对象：`toolchain/slither.py` 的 production 改动、`tests/test_production.py`、19 个特征 fixture、`artifacts/cp0_1_env_v1/`、`cp0_1_compilers_v1/`，CP0_1_REPORT 的 B、C 节与 CHANGE_LOG §11。

修改：`PROMPTS.md`（r2.4 → r2.5）；新增 `artifacts/cp0_1bc_review_v1/`；记录：本节、`docs/HANDOVER.md`（第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 4 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 12.2 实施方式和重要选择

- B 复核：重算 production_invocations 与 seal_v2；把 production 归档与 Claude 在上一轮审查中用 Slither 0.11.6 独立运行的 846 个文件逐组比较；核对两环境区间文件逐条相同。
- C 复核：59 个新编译器的可信清单与官方 solc-bin 索引逐项比较；从 GitHub 发布页取得 solc 0.8.24–0.8.27（哈希与官方索引一致，0.8.24 与 Codex 失败记录的编译器相同），在默认设置与 `--evm-version cancun`、`--via-ir` 下编译全部适用探针，并用 Slither 0.11.6 判定 D3。官方 0.8.25、0.8.26、0.8.27 发布说明分别确认默认 EVM 改为 cancun、require 自定义错误只在 IR 管线支持、0.8.27 起旧管线支持。
- 处理方式：探针下界改为“默认设置可编译的最低版本”，原下界版本上的默认设置组合改为负对照，另加带设置的正对照，这样既不放宽判据，也保留了设置依赖的证据。
- 设计：精确 pragma 的真实输入可能只能在非默认设置下编译，换版本无效，因此版本策略加入编译设置（3.3 节第 3a 条）。只在有文档依据的错误出现时触发，同一版本先试设置再换版本（与 D5 取最低版本一致），只允许两种选项，不改源码，Slither 用相同设置。放在 CP1 实现，CP0.1 C 续只做 toolchain 支持与验证。
- IR 文本：发现 4 个文件的 IR 含对象内存地址后，统计两个归档（0.8.0 归档 0 处），要求在 node_facts 中规范化并用两次完整运行验证确定性。CP0 投影不改，以保持与 cp0_v2 的对照。

### 12.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| production 调用 | solc 846、Slither 846；profile 0.11.6 / 0.4.2；平台 solc 846 | production_invocations.jsonl |
| production D3 | 843；失败 3 个 0.4.24 文件，AssertionError | 同上 |
| production 节点 | 110,996 | production_node_facts_v2.jsonl.gz |
| seal_v2 | 74 个文件哈希一致 | seal_v2.json |
| 区间 | 两环境 846 行完全相同 | intervals_*.json |
| 与 Claude 独立 0.11.6 运行 | 839/843 key5 + 有序 IR 相同；4 个只差 1 行 IR（对象内存地址） | ir_object_repr.json |
| 59 个编译器 | SHA256、Keccak256 与官方索引 0 差异 | trusted_compilers_addition.json |
| 0.8.24 默认设置 | 4 个 Cancun 探针 solc 失败；加 `--evm-version cancun` 后 rc 0、D3 通过 | floor_matrix.jsonl、slither_settings_0116.jsonl |
| 0.8.26 默认设置 | h0826 solc rc 2（UnimplementedFeatureError）；加 `--via-ir` 后 rc 0、D3 通过 | 同上 |
| 0.8.25、0.8.27 默认设置 | 适用探针 16、17 组全部 solc rc 0、D3 通过 | 同上 |

未证明：0.8.28–0.8.37 上探针的结果（C 续中运行）；设置表在真实语料上的触发频率（CP3）。

### 12.4 用户批准、原文差异与待确认设计

- Codex 处理正确：B 全部门槛、平台记录方式（公开 API 组合，结果与 `Slither(path)` 一致）、安装与信任链、C 遇首个失配即停、不改参数与探针、只登记建议。
- 方案错误（Claude）：r2.4 的探针下界未考虑默认编译设置，且只在 0.8.38 上验证过。
- 新增设计：3.3 节第 3a 条编译设置；IR 文本规范化。均按用户已批准的“先确定性环境方法”原则，不需要新的决策编号；记在 D5、D16 的历史中。
- 无需用户新授权：C 续不安装、不下载。

### 12.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp0_1bc_review_v1/README 全文，CHANGE_LOG:84141、PROGRESS:14829 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；从 GitHub 下载 4 个官方 solc 到会话临时目录（只用于审查）；没有 LLM 调用，费用 0。
- 停止：CP1 不能开始。顺序为 Codex 执行 4.2c 节 → Claude 审查 → CP1。本轮提交并 push 到 `compile-repair`。


## 13. 2026-11-13 CompileRepair CP0.1 C 续：设置支持、指纹稳定与 501 组验收完成（修改 AI：Codex）

### 13.1 任务、依据与范围

用户要求执行 PROMPTS r2.5 §4.2c，先快进同步，逐项验收、遇非预期或需下载安装即停。起始 compile-repair@3742fb75e535b5517ded58659e78737a01b51000，pull 为 Already up to date；已读 r2.5 全文、共享上下文、HANDOVER §0–5、DECISIONS、§11/§12 和审查 README。修改文件为 core/model.py、toolchain/solc.py、toolchain/slither.py、tests/test_production.py，新增 tests/test_settings.py；文档为 CP0_1_REPORT、PROGRESS、本节、HANDOVER、DECISIONS 以及两批新 README。新证据仅 cp0_1_env_v2 与 cp0_1_compilers_v2；完整文件及 SHA 清单见 file_inventory.json。未改 PROMPTS、scripts/**、原作者代码、语料、任何旧 artifacts、原可信清单和根目录交接/训练记录。

### 13.2 实施方式和重要选择

生产代码只修改 `core/model.py`、`toolchain/solc.py`、`toolchain/slither.py`。Compilation 增加默认空的有序 settings 元组，保留原有位置参数兼容性。compile_file/command 仅允许 --evm-version 后跟单个名称和 --via-ir，保持调用方顺序并追加到命令末尾；拒绝未知选项、重复选项与包含空白的名称。错误首行解析在崩溃时把原 banner 与 std::exception::what 消息一起记录，完整 stderr 仍原样保存，因而不会丢失 0.8.26 的 via-ir 原因。

production 把同一个 settings 通过 solc_args 同时传给公开 CryticCompile 与 Slither 构造器，空设置不传；regression_6c 对非空设置显式抛错，冻结 _compile 不改。node_facts 把限定形式的 Python 对象 repr 规范化为模块/类名，counts 增加 ir_object_repr_replacements 与 ir_object_repr_unresolved；仍有对象地址时 D3(a) 失败，并给出 key5、IR 行号和原文诊断。只处理该 repr 模式，普通十六进制字面量保留，CP0 投影函数 AST 与起始提交完全相同。

测试修改 `tests/test_production.py`，新增 `tests/test_settings.py`。既有 feature 参数化保留全部原组合，把 r2.5 指定的 5 个默认失败组合改为严格负对照，并加入对应设置正对照，没有 xfail 或放宽 D3；另测试参数白名单、命令及记录、regression 拒绝、真实错误文本、替身 IR 的稳定结果/替换次数/残留失败。28 个 Solidity fixture（包括 19 个特征探针）未改字节。生产 Python 仍为 9 个，测试文件现为 6 个；文件表与分层遵守 §3.10。

复用冻结 validate_slither._compile 的原 SHA 为 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8；沿用公开 CryticCompile/Slither 组合与既有 load_additions 信任校验，不复制或 monkeypatch 冻结函数。生产命令默认参数保持一致，新增参数只使用文档白名单；旧成功组必须逐组比较，不能仅比较总数。

本轮没有非预期验收结果，没有测试失败后重跑，也没有方案外算法变更。读取阶段 WSL 未安装 rg，按现有 Python/sed 完成只读检查；ir_object_repr.json 实际是两个连续 JSON 对象，首次单对象 json.loads 报 Extra data 后按原格式分别 raw_decode，原文件不改。这属于证据格式适配，不改变 4 文件/4 行预期。生产原始诊断保留已知断言的源码缩进，以无损 gzip 提交并逐字节回读校验，原日志留在本地，SHA 与压缩对应关系见 log_compression.json。

### 13.3 实测与数据结论

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

输入为 cp0_v2 的 846 个源码 SHA 和 selection.ascending；每次运行绑定可信二进制 SHA。两次生产耗时 309.983 / 282.392 秒，回归样本 12.248 秒，兼容性 28.131 秒。时间来自 production_run*.json、regression_sample.json、compatibility.json；未把旧产物当成本轮新运行。两个环境与固定源码均为 CPU 工作，OMP/MKL=2。

### 13.4 用户批准、原文差异与待确认设计

用户本轮明确要求执行 r2.5 §4.2c，并规定需要安装/下载或验收不符即停。本次未发生上述停止条件；没有新增授权请求，没有安装、下载编译器/语料/文档、LLM 调用、全局 solc 切换或 HGT 训练，费用 0 美元。A、B 结论、旧产物和既有 C 失败现场均保留。本步只完成工具链接口与验证：按错误自动触发设置、版本升序选择和两行设置表属于 CP1；第 10 行源码改写属于 CP6，均未实现。CP0.1 C 续已完成本机验收，仍须审查通过后才能开始 CP1。

CP1 输入参数：production 固定 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2；regression_6c 固定 mando 0.8.0 / 0.2.4。可信编译器沿用 cp0_v2/recon.json 中 37 个身份与 cp0_1_compilers_v1/trusted_compilers_addition.json 中 59 个新增身份，其中 92 个在支持区间、4 个历史负对照低于下限，必须经原信任链校验。设置表第 1 行是 0.8.24 中 Cancun 内置函数/全局量未找到或未声明时加 --evm-version cancun（4/4 正负对照验证）；第 2 行是 Require with a custom error is only available using the via-ir pipeline. 时加 --via-ir（0.8.26 的 1/1 正负对照验证）。依据仍为 PROMPTS §1.8、§3.3 第 3a 条和审查中已核对的官方发布说明，本步不额外下载文档。

口径限制：501 组是明确批准的 59 个新增版本矩阵，不是对 92 个版本、每一种语法或完整 CFG/CG 语义的穷举证明。另 33 个先前安装版本的原证据保留在 cp0_v2 与 cp0_1_env_v1，不为扩大结论而重跑 A/B。三个合法旧合约的 Slither AssertionError 仍是已知问题；没有把它们写成已修复。

本轮没有需要替代原方案的设计调整或新增待批准事项；设置参数支持与 IR 规范化均是 r2.5 已明确要求的内容。D5 的自动设置表与尝试顺序尚未实现，不把手工指定的 5 个验证对照说成自动修复模块已完成。

### 13.5 验收、资源、未执行事项与停止

| 检查 | 实测 | 原始日志 |
|---|---|---|
| 新逻辑与分层（production / mando） | 各 27 passed | unit_production.log、unit_mando.log |
| 完整模块（production） | 506 passed，6 skipped，28.69 秒 | pytest_production.log |
| 完整模块（mando） | 83 passed，429 skipped，6.60 秒 | pytest_mando.log |
| 冻结 DFG v2（mando） | 2653 passed，9 warnings，181.50 秒 | pytest_dfg.log |

各日志位于 cp0_1_env_v2，完整 argv、解释器、环境变量、rc 与日志 SHA 在同名 json 中。两个模块测试使用 -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests；冻结测试使用同样参数运行 scripts/DFG/dfg_v2/tests；均使用各自新的 --basetemp。test_layering 通过，CP0 投影未改、Python 3.7 语法和 9/30 文件检查通过（implementation_audit.json）。

强制文档为 7 份：CP0_1_REPORT、PROGRESS、CHANGE_LOG 检查本轮追加区，HANDOVER、DECISIONS 因当前状态更新检查全文，两个 README 检查全文。提交前执行冻结审计、doc_check 与暂存格式检查，实测结果在本节末尾追加；任何失败都不得提交。只作以 CP0.1 开头的本地提交，本任务不 push。停止于等待审查，CP1 未开始。


验收补记（修改 AI：Codex）：冻结审计已实测通过：模块外 27,845 个已跟踪文件、302 个旧产物、28 个 Solidity fixture、205 个 mando 元数据文件、88 个 production 元数据文件与 96 个 solc 文件均 0 差异；code_refs 354 项不变，未新增/删除 solc 文件，全局选择环境不变；报告/进度/变更记录旧前缀与交接/决策历史保持原字节（frozen_audit.json）。首轮 doc_check_v1 的 7 行均 passed=true，rc0；追加前偏移为 CP0_1_REPORT 25224、PROGRESS 15396、CHANGE_LOG 88986 字节，另外四份检查全文。初次精确暂存 54 个文件后，git diff --cached --check 返回 0，没有排除任何已暂存文件；原始 stderr 以无损 gzip 提交并回读核验，未删改诊断文本（staging_check.json、log_compression.json）。本补记追加后按相同目标执行 doc_check_v2 作为最终检查，实际七行结果和命令保存在 doc_check_v2.jsonl 与 doc_check_v2_invocation.json；全部通过后再封存、核对最终清单和暂存格式并本地提交。


## 14. 2026-11-14 CompileRepair CP0.1 C 续审查与方案 r2.6（修改 AI：Claude）

### 14.1 任务、依据与范围

用户要求（2026-11-14）：Codex 已按推荐方案完成修改；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP1。起点 `compile-repair@08337158`。审查对象：`core/model.py`、`toolchain/solc.py`、`toolchain/slither.py` 的差异，`tests/test_settings.py`、`tests/test_production.py`，产物 `cp0_1_env_v2/`、`cp0_1_compilers_v2/`，CP0_1_REPORT 的“C 续”节与 CHANGE_LOG §13。

修改：`PROMPTS.md`（r2.5 → r2.6）；新增 `artifacts/cp0_1c2_review_v1/`；记录：本节、`docs/HANDOVER.md`（第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 14.2 实施方式和重要选择

- 数据复核：`verify_c2.py` 独立重算两次生产运行、B 与 A 归档、回归样本、兼容性计划与调用记录；生产归档与 Claude 上一轮独立的 0.11.6 运行比较时，对 Claude 的数据按同一规则规范化对象地址。另核对两个 seal 中全部产物、实现文件与文档的哈希。
- 代码复核：逐行审查差异；在 Claude 的 0.11.6 环境中直接调用 Codex 的 `compile_file` 与 `run_slither(production)` 跑设置的正反例与白名单拒绝；查 crytic-compile 0.4.2 源码确认传入 `solc_args` 后仍补 `--allow-paths`。
- 进入 CP1 前通读 CP1 提示，发现三处与当前状态不符：选版复现测试没写明用 cp0_v2 的编译器集合；小样本验收按 0.8.0 与 37 个编译器写成“与 CP0 预测相同、D3 失败 0”；“用 0.4.11 构造缺文件名”假定了一个未在生产工具链上验证的现象。为核实第三点，在 4 种工作目录下测了 0.4.11 的文件名映射。
- 处理：复现测试固定输入集合；小样本验收改为可归因比较，并加入 3 个已知 Slither 侧失败合约作为预期未修复项；0.4.11 测试改为替身对象，真实情形放到 CP1 第 6 节只测量、不改下限；pipeline 的未修复原因分类加入“Slither 侧失败”。

### 14.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 两次生产运行 | 743/743 个不同源文件节点与指纹相同；自身指纹 1,486/1,486；对象地址残留 0 | verify_c2.json |
| 与 B 归档 | 739 相同；4 个规范化后相同（审查指定文件）；其他 0 | 同上 |
| 与 Claude 独立 0.11.6 运行 | 740/740 相同（规范化后） | 同上 |
| 回归样本 | 20/20 与 A 相同 | 同上 |
| 兼容性 | 501 组；496 原组合逐组保留；solc 非零 5 个均为负对照，错误文本与 r2.5 一致；Slither 496 次 D3 全部通过，5 次带设置；旧 224 组相同 | 同上；compatibility.json |
| seal | cp0_1_env_v2 41 个、cp0_1_compilers_v2 8 个产物；实现 9、文档 7 个文件哈希全部一致 | 审查时核对 |
| 设置通路（Claude 环境） | 0.8.24 默认失败、加 cancun 通过；0.8.26 默认失败、加 via-ir 通过；0.8.25、0.8.27 默认通过；`--optimize` 被拒 | settings_e2e.jsonl |
| 0.4.11 文件名 | Slither 0.8.0：工作目录为仓库根或文件目录时 5/5 缺失，`/` 或无关目录时 0；0.11.6：4 种情形都 0 | github_0411_cwd.jsonl |

未证明：用户环境中官方 solc-bin 的历史编译器在生产工具链下的 D3（CP1 第 6 节）；3 个重入合约在 0.4.24 以外的 0.4 版本上的生产 Slither 结果（CP1 第 5 节记录）。

### 14.4 用户批准、原文差异与待确认设计

- Codex 处理正确：全部 4.2c 节要求；按原格式读取审查给出的两段 JSON；没有提前实现 CP1 的自动设置选择或 CP6 的改写。
- 方案修正（Claude）：CP1 的三处与当前状态不符的写法，见 §14.2。
- 不需要用户新决定或授权。D9/D10 待确认，D12/D13 待定；≤ 0.4.11 下限是否扩展，等 CP1 第 6 节结果后再提交用户决定。

### 14.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp0_1c2_review_v1/README 全文，CHANGE_LOG:99372、PROGRESS:20047 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；沿用会话中的虚拟环境与编译器；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP0.1 完成；下一步 Codex 执行 CP1。本轮提交并 push 到 `compile-repair`。


## 15. 2026-11-14 CompileRepair CP1：核心层与环境修复入口完成（修改 AI：Codex）

### 15.1 任务、依据与范围

用户要求执行 PROMPTS r2.6 §4.3，先同步和通读全文、HANDOVER §0–5、DECISIONS、§13/14 及 cp0_1c2_review_v1/README，按 §4–6 验收，记录后本地提交。起始 compile-repair@d5e84d39fe876ea1b4b00a8bb26dee47ca9e18a5，pull --ff-only 为 Already up to date。范围为任意单文件/片段的环境第 1、6 步；MANDO 只作回归。

新增 core/provenance.py、core/store.py、rules/__init__.py、rules/environment.py、pipeline.py；修改 core/model.py、toolchain/solc.py、evaluation/survey.py、cli.py；新增 test_core.py、test_environment.py、test_pipeline.py。产物为 cp1_development_v1、cp1_sample_v1、cp1_historical_v1；文档为 CP1_REPORT、三个 README、本节、HANDOVER、DECISIONS、PROGRESS。完整清单见 file_inventory.json。PROMPTS、CP0/CP0.1 报告/产物、scripts/**、原作者代码、语料、根目录记录保持不变。

### 15.2 实施方式和重要选择

核心层记录编译单元、字节补丁、偏移分段与清单。补丁校验当前副本原文，保存 old/new/step/round；最终重放必须完全复现副本和映射。additive 按原字节身份/顺序核验，不只查子序列；等长 rewrite 保留位置对应，删除/非等长替换可映射为 None，跨来源边界或删除拼接点的节点为 rewritten。存储排他创建、拒绝路径逃逸/符号链接，JSONL 逐条 flush；seal 绑定全部产物、工具与实际代码身份。失败保存副本/清单/调用证据，不生成成功节点文件。

选版策略唯一实现在 environment.py，survey 只作委托并保留 CP0 无 pragma 的调查窗口。直接 import versioning.interval，冻结文件 SHA256 为 130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18，未复制或 monkeypatch。已知版本优先；普通候选先耗尽下界系列再推进；降序只反转系列内顺序。无 pragma 推断只加入有官方版本依据的 throw/var 移除和 unchecked 引入，注释/字符串遮蔽；未出现特征不反推作者意图。MANDO 配置才按源码 hash 匹配 SmartBugs metadata，并通过 recorded_version 复查源码/CSV/唯一行，无 pragma 优先 0.4.25。

默认失败后只按两行表在同一版本重试：0.8.24 Cancun、0.8.26 via-IR；核对类型/消息/版本，未命名标识符另核对源位置。Slither 使用相同有序设置，清单保留触发错误与出处。只有区间内无可信支持候选才覆盖 pragma，候选限下界同系列、距离优先；替换 directive 等长字节，保留换行和同一行其他代码。候选耗尽区分无候选、所有 solc 失败、Slither 侧失败。完整 CFG 边/调用存储留 CP2，目录/闭包留 CP3，兼容源码改写留 CP6。

solc.py 只追加本地固定 SHA 信任加载器，复用已授权追加清单校验；原函数 AST 保持相同，Slither 文件不改。代码封存扫描跳过旧 artifacts/临时树，避免无关 IO。归档辅助检查首次把 pytest 实际目录和 current 符号链接算作两份结果而退出，确认别名后只排除符号链接，读取原通过结果，没有重跑测试或改标准（offline_replay_audit.json）。

写最后四份记录时，WSL 启动命令返回 Wsl/Service/0x8007274c。先只读查 WSL 状态、UNC 文件与主机资源；四文件 SHA256 全部仍等于 baseline，证明未开始写入，随后短 stat 命令恢复。分批继续写记录，没有重启服务、改网络或重跑验收；根因未确定，不推测为代码失败。证据 documentation_interruption.json；普通沙箱读取受限时使用既有获准的显式 WSL/只读权限，不新增安装。

正式 case 源码副本 95 份中 57 份有原有行尾空白；保留副本/原 seal，852 文件（12,212,867 字节）打包为 cases.tar.gz，逐成员回读哈希/长度相同后提交压缩包与 case_archive_index，原目录只保留本地。没有删改源码空白、重写 case 或放宽 git 暂存检查；这是无损证据归档，不改变生产存储格式。

### 15.3 实测与数据结论

| 项 | 实测 | 证据（artifacts 下） |
|---|---|---|
| 冻结重放 | 两环境各升序 846/846、降序 846/846；固定 CP0 37 版与旧 rc/D3，不重新编译 | cp1_development_v1/offline_replay_*.json.gz |
| 自动设置 | 六个真实副本全部默认失败后同版设置 D3 通过，含 ^0.8.24 不先换版本 | settings_acceptance.json |
| 小样本 | 规则 A 非通过 25 + 七类各 10 个通过；三指定失败已在 25 份内，合计 95 | cp1_sample_v1/sample_plan.json |
| 小样本验收 | 92 成功，3 个预期 Slither 侧失败，其他未修复 0；197 solc、101 Slither，347.413 秒 | acceptance_summary.json |
| 选版对账 | 91 相同，1 因新增更低 0.5.5（旧 0.5.6）；无法归因 0，无覆盖/跨系列 | archive_audit.json、cases/082/manifest.jsonl |
| 原字节与节点 | 95 文件 level=none；11,822 成功节点全部 original；95 case seal 回验通过 | archive_audit.json |
| 历史测量 | 23 次前置 solc 全 rc0，46 次生产 Slither；0.4.11 两 CWD 各 5/5，其他三版失败 | cp1_historical_v1/results.json、counts.json |
| 冻结保护 | 27,845 模块外文件、363 旧产物、28 fixture、117 mando/144 production 元数据、96 solc 均相同；354 code_refs 不变 | frozen_audit.json |

唯一选版差异输入 SHA 为 f0028ebd798334727aa07d9857bc3996563b8dc250b899882cb1346fc5d24014，0.5.5 在原区间且 rc0/D3 通过，属于第 5 节 (a)。样本实际 metadata 命中 0、无 pragma 1，不能写成重跑全部 43 份 metadata；已知优先级由冻结 846 离线重放覆盖。三个已知重入文件各在 0.4.12–23 solc 非零，0.4.24/25/26 rc0 后 AssertionError，完整尝试链保留。

历史每个 CWD 的（输入数、D3 通过、缺 filename 节点）：0.4.0=(10,0,287)、0.4.2=(5,0,50)、0.4.9=(3,0,362)、0.4.11=(5,5,0)。两个 CWD 逐版相同，合计 10/46 D3 通过、缺 filename 1,398；36 个 D3 失败是规定测量值，不是额外小样本失败。前置编译在仓库根，run_slither 才分别在根与 /；测量 3.887 秒，含加载进程 7.351 秒。

### 15.4 用户批准、原文差异与待确认设计

本轮授权 CP1 编码、已有工具运行、记录与本地提交；未授权新安装/下载或 push，实际均未执行。没有修改方案、放宽标准或更换实现范围。生产 Slither 使用 production，6c 相关测试只用 regression_6c；CP0/CP0.1 原结论与产物不重做。

只登记两项审查事项，未实施替代方案：（1）0.4.11 五份输入通过不证明任意源码/图语义，建议保持 0.4.12，扩展需审查与用户决定。（2）既有 command() 用字符串截取相对路径，在 cwd=/ 时产生 ome/...；只读构造证据在 cwd_command_inspection.json，未作额外编译或修改原函数。建议经确认后用路径函数并补 / 与相似目录前缀测试。当前 CLI 从项目工作目录运行；第 6 节前置编译在仓库根，测量未受影响。

### 15.5 验收、资源、未执行事项与停止

生产模块 546 passed/6 skipped（41.79 秒），mando 模块 116 passed/436 skipped（13.38 秒），冻结 DFG 2653 passed/9 个已有警告（196.02 秒）。参数 -q -ra -x -p no:cacheprovider，新 basetemp；精确 argv/环境/rc/哈希及原始无损压缩日志见 pytest_*.json/log.gz。14/30 生产文件、9 测试文件、28 fixture；分层和 Python 3.7 语法通过，正式运行后代码身份未变。

frozen_audit passed=true：28,236 份冻结文件、旧报告/PROMPTS、环境与全局选择均相同；Compiler/Compilation、所有原 solc 函数 AST 相同，Slither 整文件不改，模块外无跟踪改动。CPU，OMP/MKL=2；无下载/安装、LLM、训练、GPU 锁或外部语料获取，费用 0。完整图/项目/依赖/其他规则与 CP6 改写未运行。

提交前对 CP1_REPORT、PROGRESS:20625、CHANGE_LOG:103907、HANDOVER、DECISIONS 和三个 README 共 8 份执行 doc_check；前两份历史追加记录按原字节边界，其余全文，逐行 passed 与命令写入 artifact。最终结果在本节末补记。完成封存、精确暂存和 git diff --cached --check 后本地 CP1 提交，不 push；停于待审查，CP2 不开始。


最终验收补记（修改 AI：Codex）：doc_check_v1 的 8 行全部 passed=true、rc0；历史字节审计确认 PROGRESS/CHANGE_LOG 原前缀与 HANDOVER/DECISIONS 旧历史不变（documentation_history_audit.json）。原始 case 无损归档 852/852 成员 SHA/长度通过，原 seal 保留。首次精确暂存 57 文件，git diff --cached --check 返回 0（staging_check.json），未排除任何已暂存文件。补记和归档说明完成后执行 doc_check_v2，再封存三个批次、生成 seal_hashes/file_inventory、核对最终暂存字节和完整格式检查，成功后本地提交；最终八行结果及命令收据为 doc_check_v2.jsonl / doc_check_v2_invocation.json。


## 16. 2026-11-14 CompileRepair CP1 审查与方案 r2.7（修改 AI：Claude）

### 16.1 任务、依据与范围

用户要求（2026-11-14）：Codex 已按推荐方案完成 CP1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP2。起点 `compile-repair@3497af24`。审查对象：14 个生产 Python 文件中的新增与改动（core/model、core/provenance、core/store、rules/environment、pipeline、cli、evaluation/survey、toolchain/solc），3 个新测试文件，产物 cp1_development_v1、cp1_sample_v1（含 cases.tar.gz）、cp1_historical_v1，CP1_REPORT 与 CHANGE_LOG §15。

修改：`PROMPTS.md`（r2.6 → r2.7）；新增 `artifacts/cp1_review_v1/`；记录：本节、`docs/HANDOVER.md`（第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（新增 D19，历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 16.2 实施方式和重要选择

- 代码审查：逐行读 rules/environment.py 与 pipeline.py，对照 3.3 节（含第 3a 条与第 6 条）与 4.3 节检查候选集合、系列顺序、已知版本、无 pragma 推断、覆盖条件、设置重试与 Slither 侧失败的处理。
- 数据复核三层：重放文件与 cp0_v2 逐个比较；解包 cases.tar.gz 审计 95 个 case 的封存、计划与尝试；用 Claude 的独立工具链（GitHub 静态 solc、`Slither(path)`）按同一候选顺序重算选定版本。
- 端到端：为在 Claude 环境中运行 Codex 的 environment.py，安装 tree-sitter 0.20.4 并用仓库内的 tree-sitter-solidity 构建语言库；对覆盖、推断、交集三种情形直接调用 repair_unit。
- `command()`：Codex 报告了 `/` 的情形；Claude 用直接调用与流水线两种方式复现，并发现字符前缀相同的兄弟目录同样失败。修复方式选“按路径组件判断，在目录内用相对路径，否则用绝对路径”，并要求证明 846 个 MANDO 文件与兼容性 fixture 的 argv 不变，因此不需要重跑 CP1 样本。regression_6c 的 Slither 经冻结代码进入 crytic-compile 0.2.4，其内部有同样写法而不能修改，所以只加防护，遇到会出错的工作目录时拒绝运行。
- 健壮性：检测时会批量处理任意输入，单个输入的 solc 超时不应停止整个批次；模块也可能不在 git 工作树中运行。两项放入 CP1.1。`||` pragma 与 Slither 进程内无超时涉及设计，放入 CP3 分类表先统计频率。
- CP2 提示：原文写“失败数不为 0 就停下”“与 0.8.0 按 key5 比较”，与生产工具链和 92 个编译器的现状不符；改为预期 3 个已知失败、两次运行确定性、与同版本生产归档逐组相同，并写明存储内容与序列化要求。
- D19：0.4.11 在生产工具链上可用，但加入候选会改变大量 `^0.4.x` 文件的选定版本，收益只有精确 0.4.11 pragma，建议维持 0.4.12，由用户最终决定。

### 16.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 冻结选版重放 | 两环境升序、降序各 846/846 与 cp0_v2 相同 | offline_replay_*.json.gz |
| 样本封存 | 95 个 case、757 个文件哈希一致；14 个实现文件与提交相同 | verify_cp1_cases.json |
| 样本计划与尝试 | 候选集合、顺序、成功位置、区间与下限问题 0；92 成功、3 Slither 侧失败；solc 197、Slither 101 | 同上 |
| 选定版本 | 与 cp0_v2 相同 91；case 082 选 0.5.5（cp0_v2 未装），归因 (a) | 同上 |
| 独立重算 | 95/95 选定版本与尝试版本序列相同 | indep_select.jsonl |
| 节点标记 | 92 个成功 case 11,822 个节点全部 original | 审查时计数 |
| 端到端 | 精确 0.4.10 → 覆盖 → 0.4.12 成功、字节数不变、4 个节点 original；无 pragma（throw/var）→ [0.4.12, 0.5.0)；两条 pragma → [0.5.0, 0.5.3) | pipeline_cwd.json |
| `command()` 缺陷 | 工作目录 `/`：`mp/…` not found；字符前缀兄弟目录：`2/units/…` not found；流水线记为 all_solc_candidates_failed；两环境都复现 | command_cwd.jsonl、pipeline_cwd.json |
| 历史编译器 | 0.4.11 两种目录 5/5；0.4.0/0.4.2/0.4.9 缺文件名 287/50/362（每种目录） | cp1_historical_v1 |

未证明：CP1.1 修复后的行为（由 CP1.1 验证）；`||` pragma 与 Slither 挂起在真实语料中的频率（CP3）。

### 16.4 用户批准、原文差异与待确认设计

- Codex 处理正确：CP1 全部要求；对 `command()` 只登记不擅改；历史测量只记录不改下限。
- 新发现：`command()` 缺陷的范围比登记的大（字符前缀兄弟目录）；两处健壮性问题。
- 待用户确认：D19（建议维持 0.4.12）。D9/D10 待确认，D12/D13 待定。CP1.1 不需要新授权。

### 16.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp1_review_v1/README 全文，CHANGE_LOG:113014、PROGRESS:22951 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；在会话虚拟环境中安装 tree-sitter 0.20.4（只用于审查）；没有 LLM 调用，费用 0。
- 停止：CP2 不能开始。顺序为 Codex 执行 CP1.1 → Claude 审查 → CP2。本轮提交并 push 到 `compile-repair`。


## 17. 2026-11-14 CompileRepair CP1.1：路径边界、输入超时与无 Git 封存（修改 AI：Codex）

### 17.1 任务、依据与范围

用户明确要求执行 PROMPTS r2.7 §4.3b，先 pull --ff-only origin compile-repair，通读全文，重点 §1.10、§4.1、§4.3b，以及 HANDOVER §0–5、DECISIONS、§15/16 和 cp1_review_v1/README。起始 d4f4b48a2484591dc185b90475f775f6c9f5498d，pull 返回 Already up to date。实现仅修改 compile_repair/toolchain/solc.py、toolchain/slither.py、pipeline.py；新增 tests/test_cp1_1.py。非测试生产 .py 数保持 14，测试文件为 10；原 28 个 fixture 保留。

新增证据仅 artifacts/cp1_1_v1，包括基线、测试收据/压缩日志/新增测试结果、CLI 计划/调用/九个独立输出、三份测试副本、审计脚本与 README；提交完整清单见 file_inventory.json。文档在 CP1_REPORT 追加 CP1.1，PROGRESS 追加进度，本节五段记录，HANDOVER §0–5 更新及 §6 追加，DECISIONS 当前状态同步与历史追加。PROMPTS、旧报告的既有字节、CP0–CP1 正式产物、scripts/**、语料、模型与根目录记录不改。

### 17.2 实施方式和重要选择

command 使用 pathlib 的路径组件包含关系：relative_to 成功才用相对路径，目录外捕获 ValueError 保留绝对路径，参数顺序与 _build_options 保持。旧字符截取只作为测试内参照，来源为起始提交 toolchain/solc.py（SHA256 711d29b346585d7bb0330ce227e4c2986709dc4ea8155eb97bf46408d6226be7），没有在生产代码保留第二套实现。846 个 MANDO 文件使用冻结的升序选定版本，兼容性使用 C 续全部 501 个计划项含 settings，逐项比较新旧 argv；这不是重跑语料或旧兼容性正式产物。

regression_6c 的前置检查拒绝 / 与错误字符前缀目录；仍 import 冻结 validate_slither._compile（文件 SHA256 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8），不复制、不 monkeypatch、不修改 crytic-compile 0.2.4。production 保留现有 CryticCompile/Slither 通路。测试对危险 cwd 使用不存在的源码和编译器，若防护没有提前发生则会以不同异常失败，保证拒绝前没有工具调用。

pipeline 对 timed_out 先写完整调用，再退出该输入的两个候选循环并封存 solc_timeout；最后的普通失败分类不得覆盖这个原因。正常批次继续，信任/完整性异常仍沿原停止路径。repair 只增加 compile_fn 的可选注入，默认调用不变；取 Git HEAD 用小型私有函数，仅将无 git/无 HEAD 的两类错误转换为 None。无 Git 测试把本模块 14 文件和两个固定清单复制到 /tmp，冻结依赖仍从原仓库只读 import；第二种情况仅在子进程清空可执行搜索路径，没有修改主环境。

开发中 WSL 无 rg，改用已有 Python/sed/grep；只读检索一次命中不存在的 test_solc.py 后改读实际 test_toolchain.py。三次 pytest 与九组 CLI 均首次运行通过；没有失败重跑、放宽标准或方案外调整。日志压缩前后保留哈希，临时树留 /tmp 不提交、不清理；JSON 产物按交付清单精确 force-add，不扩展到旧临时树。

### 17.3 实测与数据结论

| 项 | 实测 | 来源（cp1_1_v1 下） |
|---|---|---|
| argv 不变 | production / mando 各 MANDO 846/846、兼容性 501/501 | module_acceptance.json、test_evidence_*.json.gz |
| 真实 solc 路径 | 两环境各 5/5 rc0，solc 0.5.17；二进制 SHA 与冻结信任相同 | path_invocation.json 的归档 |
| 6c 前置拒绝 | / 与前缀兄弟，两环境均通过；没有调用冻结编译 | test_cp1_1.py 与 pytest 收据 |
| 单输入超时 | 三种位置两环境各 3/3；不重试，末次 timed_out、未修复原因正确 | module_acceptance.json |
| 批次/信任 | 超时后下一输入成功；信任异常停止、不调用第二输入 | production 测试 batch summary/manifest 归档 |
| 无 Git | 非 Git 分发目录、PATH 无 Git，两组 CLI complete，seal commit=null、14 文件 SHA 正常 | production relocated_cli 与 seal 归档 |
| 三目录 CLI | 9/9 成功；状态、版本、设置、key5+IR+标记逐个相同；90 个节点全 original | cli_acceptance.json |
| CLI 工具调用 | 12 次前置 solc、9 次生产 Slither；每例 10 节点；case seal 全部回读通过 | cli_invocations.jsonl、cwd/out2/* |
| 原始输入 | 三 fixture 及输入副本 SHA 不变；0.4.10 工作副本只有 pragma 覆盖 | cli_plan / acceptance、case provenance |

三个选定版本分别为 0.5.0、0.8.24 + cancun、0.4.12。0.4.10 副本改动等级 rewrite，但 pragma 不在节点跨度内，故节点标记 original 与 D7 一致。只证明这三种规定探针在三个工作目录下等价，不推广为所有 Solidity 输入的完整语义证明。没有重跑 CP1 的 95 样本或更改已审查结论；argv 相同性覆盖规定的原工作目录。

### 17.4 用户批准、原文差异与待确认设计

2026-11-14 用户明确批准按 r2.7 §4.3b 实现这三项修复、完成记录与本地提交；本次没有安装/下载或 push 授权请求。要求的 git 同步已完成；其他安装、编译器或语料下载未执行。与 PROMPTS 的实施范围和验收标准无差异，无需替代方案；未自行改变 D5/D16/D18，D19 仍为建议，0.4.12 下限不变。

DECISIONS 当前表标题从滞留的 r2.6 同步为 r2.7，D5 的“待审查”同步为已有 CP1 审查通过，不改历史。已知 || pragma 与 Slither 进程内无超时继续留 CP3，未在 CP1.1 扩展；D9/D10、D12/D13 状态保持。下一步必须先审查 CP1.1，再进入 CP2。

### 17.5 验收、资源、未执行事项与停止

production 模块 562 passed/6 skipped（pytest 60.88 秒；整命令 61.301 秒），mando 模块 128 passed/440 skipped（13.18/13.421 秒），mando DFG v2 2653 passed/9 个原有警告（160.19/160.965 秒）。完整命令均为 python -B -m pytest -q -ra -x -p no:cacheprovider 加目标和新 basetemp，见 pytest_*.json；未重复运行已通过检查。分层测试和 Python 3.7 实际导入/执行通过；production 专用测试的跳过不能算 mando 验收结果。

提交前必须通过 frozen_audit、doc_check、历史字节检查与暂存 diff --check。doc_check 覆盖 CP1_REPORT:13921、PROGRESS:23643、CHANGE_LOG:118369 的追加区间，HANDOVER/DECISIONS 和 cp1_1_v1/README 全文，共 6 份；结果随后在本节追加并封存。所有计算使用 CPU，OMP/MKL=2；无 HGT 训练、GPU 锁、LLM 调用、环境升级或全局 solc 切换，费用 0。CP2、CP3、CP6 与旧 CP1 样本未运行。全部记录通过后本地 CP1.1 提交，不自动 push；提交号以 git log 和最终答复为准。


开发记录补记（修改 AI：Codex）：冻结审计辅助脚本第一次从文件路径启动时，在执行检查前因未把仓库根加入 sys.path 而报 ModuleNotFoundError: scripts；没有生成 frozen_audit.json，没有实际冻结判据失败。保留 frozen_audit_launch_error.json 后，只给本批次辅助脚本补齐仓库导入路径，再执行冻结核验。生产代码、验收标准、已通过的三轮 pytest 和九组 CLI 没有修改或重跑；这是证据脚本启动问题，不是编译器或环境缺包，也未安装任何内容。


最终检查补记（修改 AI：Codex）：frozen_audit.json 的 passed=true，28,323 个受保护跟踪文件、354 个 code_refs、96 个 solc 文件及 mando/production 的 117/144 份包元数据均未变化；模块外跟踪改动为 0，生产文件仍 14，未授权的工具链函数 AST 变化为 0。旧 CP1_REPORT、PROGRESS、CHANGE_LOG 前缀及 HANDOVER/DECISIONS 历史原字节保留，14 个实现哈希与测试时两份封存相同。doc_check_v1 的 6 行全部 passed=true、rc0；本补记写入后按相同目标运行 doc_check_v2，最终收据为 doc_check_v2.jsonl / doc_check_v2_invocation.json。随后封存证据、按 file_inventory 精确暂存并检查 git diff --cached --check，成功后提交 CP1.1；本步不 push。


无损交付归档补记（修改 AI：Codex）：首次暂存清单 123 文件，内容 SHA 检查通过，但 git diff --cached --check 返回 2：三个精确 0.4.10 case 的 pragma_overridden.sol 第 3 行是按方案要求生成的等长空格，触发行尾空白检查。该空格不能删除，否则会改变字节偏移与既有 case seal。沿用 CP1 的交付方式，把九组 CLI 输出的 84 个文件无损打包为 cli_cases.tar.gz，逐成员 SHA256/长度回读 84/84 一致；原文件和九个 case seal 在本地保留不改。未放宽 Git 检查，未重新运行 CLI，未修改生产存储格式。

CLI 归档 SHA256 为 bec8f18cdc4510bf066d4bf79abe4489ab8d70c8c8e61a263b60ee63f1cf844b，大小 95,681 字节，archive_audit.json 保存成员清单。前文 cwd/out2/* 路径现在表示归档内成员，替代此前“按原目录提交”的交付说明。首次 seal.json、file_inventory.json、final_validation.json 均保留原字节，作为归档前阶段快照；当时的六份文档保存于 prepackaging_documents.tar.gz，与初版文档哈希完全一致。最终交付以 delivery_seal.json、delivery_inventory.json 为准，它们绑定最终文档及两个压缩包；不得将初版快照误当最终提交清单。失败现场为 staging_failure.json，当前原始目录只留本地，不删除、不提交重复副本。

归档说明纳入 CP1_REPORT、PROGRESS、CHANGE_LOG §17.5、HANDOVER 和本批次 README；追加记录遵守历史字节边界。doc_check_v1/v2 均已 6/6 通过，归档补记后按相同六目标再检查并保存新收据，完成后重新核对精确暂存范围和格式，再本地提交；编译、测试与 CLI 的已通过结果保持。


交付检查结果补记（修改 AI：Codex）：归档补记后的 doc_check_v3 为 6/6 passed、rc0；改用无损压缩包暂存后 git diff --cached --check 返回 0（staging_check_v2.json），没有放宽判据，也没有删改空格或原 case seal。此补记再由相同六目标的 doc_check_v4 核对；最终证据使用 delivery_seal.json / delivery_inventory.json，旧 seal 与初版清单保留为阶段记录。最终精确暂存字节核验通过后提交 CP1.1，不 push。


## 18. 2026-11-14 CompileRepair CP1.1 审查与方案 r2.8（修改 AI：Claude）

### 18.1 任务、依据与范围

用户要求（2026-11-14）：Codex 已完成 CP1.1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP2。起点 `compile-repair@27aa46fe`。审查对象：`toolchain/solc.py`、`toolchain/slither.py`、`pipeline.py` 的差异，`tests/test_cp1_1.py`，产物 `artifacts/cp1_1_v1/`（含 cli_cases.tar.gz），CP1_REPORT 的 CP1.1 节与 CHANGE_LOG §17。

修改：`PROMPTS.md`（r2.7 → r2.8）；新增 `artifacts/cp1_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 18.2 实施方式和重要选择

- 代码审查：逐行读三个文件的差异，确认 `Path.relative_to` 的边界判断、regression_6c 防护的两个条件、超时只结束当前输入且不被后续原因覆盖、`_code_commit` 只处理两类异常。
- 复测缺陷：用审查 CP1 时的同一探针（4 种目录 × 2 个环境）与同一流水线脚本（3 个输入 × 3 种目录）重跑，与修复前的结果对照。
- argv 不变：独立写脚本，在仓库根对 846 个 MANDO 文件与 501 个兼容性组合比较新 argv 与旧算法，避免只依赖 Codex 的测试。
- CLI case：解包 `cli_cases.tar.gz`，核对 9 个 case 的封存与三种目录下的节点哈希。
- CP2 提示：进入 CP2 前核对 Slither 0.11.6 的 SlithIR 调用类层次，发现 LibraryCall 继承 HighLevelCall，按 isinstance 顺序分类会把库调用记成 high-level；Send、Transfer 等其他 Call 子类在原提示中没有去处；CFG 边没有分支种类。r2.8 把这三点写进存储格式与测试要求。原第 2 节“6c 版本不同的 1 个文件另行重跑”在生产工具链与 92 个编译器下不再适用，改为列出归因。

### 18.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| `command()` 4 种目录 × 2 环境 | 8/8 solc rc 0（修复前 `/` 与字符前缀兄弟目录 rc 1） | command_cwd_after.jsonl |
| argv 不变 | 1,347/1,347 相同（846 + 501，两个环境各一次） | argv_equality.jsonl |
| 流水线三种目录 | 3 个输入状态、选定版本、节点哈希逐个相同，全部成功 | cwd_equivalence.json |
| Codex CLI case | 9 个封存一致；每个 fixture 三种目录节点哈希相同 | 同上 |
| Slither 0.11.6 类层次 | LibraryCall 的父类为 HighLevelCall；Transfer、EventCall 不是 OperationWithLValue | 审查时核对 `__mro__` |

未证明：CP2 全量运行的结果与耗时（由 CP2 验证）。

### 18.4 用户批准、原文差异与待确认设计

- Codex 处理正确：4.3b 节全部要求；遇到 `git diff --check` 对等长空格的报错时没有删除空格，而是打包保留原字节。
- 方案补充（Claude）：CP2 存储格式三点、第 2 节改写、运行时间估计。
- 待用户确认：D19（建议维持 0.4.12）。D9/D10 待确认，D12/D13 待定。CP2 不需要新授权。

### 18.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp1_1_review_v1/README 全文，CHANGE_LOG:128713、PROGRESS:28555 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP1.1 审查通过；下一步 Codex 执行 CP2。本轮提交并 push 到 `compile-repair`。


## 19. 2026-11-14 CompileRepair CP2：生产图确定性通过，6c 精确重放首差停止（修改 AI：Codex）

### 19.1 任务、依据与范围

用户要求执行 PROMPTS r2.8 §4.4 CP2。已通读全文与共享上下文 §4.1、HANDOVER §0–5、DECISIONS、CHANGE_LOG §17/18、cp1_review_v1 和 cp1_1_review_v1 的 README。在 /home/zhao/SmartContract/ge-sc-llm-compile 的 compile-repair 分支执行 git pull --ff-only origin compile-repair，从 27aa46fe 快进至 d56c6e0874bd30a004d7a5c7b4ce9e361d28ed18。

生产仅修改 toolchain/slither.py、pipeline.py、cli.py；测试修改 tests/test_pipeline.py，新增 tests/test_graph.py、tests/fixtures/graph_calls.sol。仍为 14 个生产 .py，11 个测试、29 个 fixture（原 28 个保留）。新增 CP2_REPORT；PROGRESS 追加；HANDOVER 更新 §0–5 且 §6 追加；DECISIONS 同步 r2.8 标题并追加授权和停止状态。新增产物仅 cp2_development_v1、cr_store_mando_v1、cr_store_mando_v2、cp2_6c_v1；全部交付文件见 delivery_inventory.json。本节沿用 NodeSem 五段式训练改变记录，没有实际训练改动。

旧 CP0–CP1.1 报告/产物与结论、PROMPTS、原 fixture、scripts/**、语料、模型、根交接/训练文档、EdgeSem、环境和编译器不改。生产使用 production profile 与既有 92 支持版本；6c 只在 mando 中从本仓库根运行冻结函数。不实施 CP3/CP6/LLM，不安装或下载。

### 19.2 实施方式和重要选择

graph_facts 按 Slither 的声明/节点/sons/IR 顺序保存 key5、length、类型、规范化 IR、CFG true/false/next 与调用点/目标。用确切操作类映射，LibraryCall 不会归为 HighLevelCall；其他 Call 子类按类名全部保留。目标能解析成 Function 时记录声明合约与 full_name，否则存规范化文本；重复 key5、跨函数端点或残留对象地址直接抛错。旧 node_facts、D3、CP0 投影函数不变，只有 production D3 通过才增加图，regression_6c 不走此新路径。

pipeline 写 graph.json、应用既有 provenance 标记、保存图 SHA，nodes.json 保持旧投影；日志避免重复整图。cli 仅传可选 result_check 回调，在单输入清单 flush 后验收，异常由现有停止/封存处理；回调不参与选版。正式 runner 使用共同 cli.main 的 repair --regression mando，已知失败与归因只用于验收。手写探针覆盖 10 类调用、modifier/自由函数；测试验证重复节点序号、sons 顺序、真实两次图及首差后不启动第二输入。

6c 直接 import 冻结 validate_slither._compile / slither_full_facts，文件 SHA256 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8，无复制或 monkeypatch。唯一重放前已核对 239 个原报告目标路径，均位于 ge-sc-llm/experiments/ge-sc-data/source_code，SHA 与当前副本一致；保留旧 target 以符合既有 0.4.11 路径敏感结论，从本仓库根调用。这是运行前选择，不是失败后换路径重试。

开发工具问题及处理：UNC 读被拒后使用 scoped WSL；两次只读 Python 引号错误在写文件前改用 base64；WSL 无 rg，用已有 grep/sed/Python；基线 code_refs 在 production 缺 torch，在基线创建前改由已有 mando 导入，无安装。停止后的文档读取一次自动审批超时，工具允许的一次只读重试成功。一次合并文档写命令超过 Windows 长度上限（os error 206），进程未创建、文件未写，改为分文档短命令；详见 baseline、post_stop_tool_issue、documentation_write_issue。没有因这些辅助问题重试正式验收。

沿用旧任务的无损 tar 交付：三个 store.tar.gz 的 4,229/4,229/93 成员（均含原 seal）逐个回读 SHA 相同，原散文件保留不改；日志压缩保留原字节 SHA。开发阶段 evidence_seal 的 awaiting_attribution_review 保持原时点含义，授权和正式结果另追加，最终交付由 delivery_seal/inventory 绑定。

### 19.3 实测与数据结论

| 项目 | 实测 | 证据（cp2_development_v1 下，另注明除外） |
|---|---|---|
| 两次生产 | 各 846 输入，843 success / 3 规定 unrepaired | ascending1/2_receipt、invocation |
| 确定性 | 843/843 图字节相同；846/846 状态/版本相同 | ascending2_acceptance |
| 规模 | 每轮 110,996 节点、87,645 CFG 边、45,565 调用，全 original | cp2_summary |
| CP0 对照 | 842 同版、1 项 (a)；同版生产归档 key5+IR 842/842 相同 | ascending1_acceptance |
| 与 6c 选版 | 238 同、1 已批准的既有下限差异 | cp2_summary、attribution_authorization |
| 6c 精确重放 | 87 已运行：86 同、1 差后停止；152 未运行 | cp2_6c_v1 的 summary/comparison |
| 降序跨版本 | 未运行 | cp2_summary.descending |
| 手写调用探针 | 7 声明、41 节点、36 边、15 调用，全部 10 类 | test_evidence_production.json.gz |
| 归档 | 4,229/4,229/93 成员均无损 | *_archive_audit |

规定失败均为 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol，没有节点/图产物。两次生产 CLI 返回 2 表示三个 unrepaired，验收 wrapper 确认预期集合后返回 0；6c 则返回 2 且 stopped，未转换为通过。生产主阶段 275.856/276.572 秒、完整命令 276.722/277.496 秒；这是实测，未证明与方案 50–60 分钟估计差异的原因。首次 948 次前置 solc、852 次 Slither，累计 70.651/170.138 秒，版本/SHA/参数/结果齐全。

CP0 唯一变动为 unchecked_low_level_calls/source_files/0x366cf49c6bc3986b20ecf4fd7c05f0c617332e8c.sol（SHA f0028ebd798334727aa07d9857bc3996563b8dc250b899882cb1346fc5d24014），0.5.6 → 0.5.5；后者在 CP0.1 已安装、CP0 的 37 版中没有，本轮 rc0、D3=true，符合 (a)。842 个同版本只比 key5+规范化 IR，不按 length 判差。按目录的来源、系列、flags 全表在 CP2_REPORT / cp2_summary，不读标签。

6c 停止文件 buggy_43.sol 的 SHA 为 7e0232977cf6d105598c2b137ffa185bd4bac95da9cf4e40925957c4744f77f2，solc 0.5.0 的 SHA 为 c1bb15b520f5076aebd7aa9ef4ce5fa245b6f210a91cbd2064b9e383e6510e08，均与旧身份相同；编译 rc0、构造成功、两边 325 CFG 节点、46 重复上下文且 comparable。旧 252 occurrence、本次 251，仅旧报告多 Post 继承上下文的 L1 [162,out,DEF]，canonical_name=MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash).out，函数/节点/声明起点为 4887/5154/4989，tags=[inheritance]，重数 1；节点原文为循环条件 i < 32。

停止后独立离线核对包含 filename/end/context_index 的完整原始行，251 行全相同，仍仅这一条旧记录；函数表只 Post 的 occurrences 从 15 变 14，其余摘要相同。冻结代码直接从 local_variables_written 生成 L1 DEF，故可定位到旧原始提取层；本次键投影与 CP2 图不是造成这条差异的环节。SSA/继承写集合构造只是未证实假设，归档未含所需 SSA 状态，底层根因未证明；replay_discrepancy_analysis 保存所有差异。未再次编译、删除事实或改旧提取器。

### 19.4 用户批准、原文差异与待确认设计

2026-11-14 用户回复“允许单列既有下限差异，记录后继续”。授权仅在 CP2 对 6c 的选版归因中单列 SHA 5ec2ee307684c021492194d5e63593834e164bcf878d1cddb48a0b1e1ad13237 的旧 0.4.11 → CP0/本轮 0.4.12；这不是新装低版本、Slither 升级或设置重试。正式运行前已写 attribution_authorization、DECISIONS 和报告。CP2 对 CP0 三类、D3、239/239 精确重放及 0.4.12 下限保持，PROMPTS 未改。

请求字段曾把 96 个可信安装标为 supported，保留原记录并通过 compiler_count_clarification 澄清 92 支持 + 4 历史。需要处理的实质事项为：旧下限归因已批准；新 6c 抽取差异未解决，不能把前项批准扩大成放宽重放。D5/D16/D18 不变，D19 仍为建议；没有替代方案实施。

建议下一步先独立审查 Post 局部写差异；如需新探针、再次运行或方案改变，先提出具体可审查范围并咨询用户，再建新批次。本轮未执行该建议；CP3 的前提不满足。

### 19.5 验收、资源、未执行事项与停止

production 模块 567 passed/6 skipped（pytest 54.56 秒；整命令 54.988 秒），mando 模块 130/443（12.85/13.063 秒），mando DFG v2 2653 passed/9 个既有 warnings（159.05/159.806 秒）。各环境 python -B -m pytest -q -ra -x -p no:cacheprovider 加 compile_repair/tests 或 scripts/DFG/dfg_v2/tests 与新 /tmp basetemp，完整 argv/环境/日志在 pytest_*.json。三轮首次通过；production 专属 skip 不能算 mando 通过，测试后实现未改并用封存 SHA 核对。

真实验收停在 §4.4 第 2 节：两次全量、同版归档、版本归因与分布通过，239/239 重放未满足，87 已运行中的 86 同 / 1 差；剩余 152、降序、CP3 均未运行。没有重试、改键或改旧产物。CP2 整体未完成，后续仅离线分析、归档、强制记录和提交检查。

CPU、OMP/MKL=2、费用 0 美元；无安装、下载、LLM、HGT 训练、GPU 锁、包升级或全局 solc 切换。最终核验冻结跟踪文件、354 code_refs、96 solc、包元数据、旧历史字节与 14 实现哈希；doc_check 覆盖 CP2_REPORT 全文、PROGRESS:29100、CHANGE_LOG:132329、HANDOVER/DECISIONS 全文与四个新 README，共 9 份，结果在本段后补记。全部记录与检查通过后按要求本地提交 CP2 停止现场，不自动 push；准确提交号以 git log 的 CP2 条目与最终答复为准。


最终保护与文档检查补记（修改 AI：Codex）：frozen_audit.json 的 passed=true；28,373 个受保护跟踪文件不变（模块外 27,845、旧产物 473、旧 fixture 28），354 code_refs、96 solc 文件、239 原重放源码均相同。本轮登记的 mando 90 份与 production 114 份包元数据文件没有变化；该数字是本轮基线实际纳入的元数据文件数，不替换旧批次的环境统计口径。14 个实现 SHA 与测试时封存相同，原 Slither 函数 AST 除授权的 run_slither 接入外均保持，PROGRESS/CHANGE_LOG 前缀及 HANDOVER/DECISIONS 历史字节保留，未预期跟踪改动为 0。

doc_check_v1 对全部 9 份目标 passed=true、rc0；本补记写入后用同一目标再运行 doc_check_v2，作为最终文档收据，并保存各文档完整 SHA。冻结审计和文档通过不表示 6c 239/239 通过；CP2 的停止结论保持。最终交付精确清单为 delivery_inventory，seal 绑定文件/文档/归档；git diff --cached --check 和暂存字节核验结果保存 staging_check.json，随后再次核对加入交付清单本身后的暂存范围再本地提交，不 push。


## 20. 2026-11-14 CompileRepair CP2 审查与方案 r2.9（修改 AI：Claude）

### 20.1 任务、依据与范围

用户要求（2026-11-14）：Codex 已完成 CP2；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP3。起点 `compile-repair@3dfb347d`。审查对象：`toolchain/slither.py` 的 `graph_facts` 与 `_callee`、`pipeline.py`、`cli.py`、`tests/test_graph.py`，两份生产存储与 6c 重放归档（解包核对），`cp2_development_v1/` 的差异分析，CP2_REPORT 与 CHANGE_LOG §19。

修改：`PROMPTS.md`（r2.8 → r2.9）；新增 `artifacts/cp2_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（新增 D20，历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 20.2 实施方式和重要选择

- 生产存储：解包两份 store.tar.gz，独立统计并比较图、节点与同版本归档；另检查每个条件节点的出边种类，发现 `IF:true,true` 86 个，读 `graph_facts` 确认原因是用 `son is node.son_true` 判断，空体 if 中 son_true 与 son_false 为同一节点。
- 6c 差异：Codex 只能把差异定位到旧抽取层。Claude 在自己的 Slither 0.8.0 环境中（solc 0.5.0 与 6c 字节相同）复现：新进程首次 254；PYTHONHASHSEED 0–7 都是 254；同一进程连续 10 次在 252–254 之间变化；按 6c 顺序先跑 86 个文件后为 252，与 6c 报告相同。由此判断 6c 报告的这一事实是不确定过程的一次采样，任何重放都不能保证逐条相同。
- 判据：逐条相同在这种情况下不可达；只放宽到“不稳定事实”，稳定事实仍须相同，且不稳定事实的参考值必须在实测样本范围内，不满足仍停下。改变 CP2 原有判据需要用户批准，记为 D20。
- 生产工具链：对同一文件用 Slither 0.11.6 同进程连续 10 次，确认节点与图不受此影响。
- 降序比较原本在 6c 之后，因停止未运行，放入 CP2.1。

### 20.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 两份存储 seal | 各 4,228 个文件哈希一致 | verify_cp2.json |
| 状态与图 | 843 成功、3 已知失败；846/846 状态与版本相同；843/843 图字节相同 | 同上 |
| 计数 | 节点 110,996（全部 original）、边 87,645、调用 45,565；与 Codex 报告相同 | 同上 |
| 调用与引用 | LibraryCall 误分 0；悬空引用 0 | 同上 |
| 同版本节点 | 842/842 相同；1 个 0.5.5 | 同上 |
| 条件节点边 | IF 一 true 一 false 5,145；IFLOOP 276；IF 两 true 86（40 个文件） | if_edge_kinds.json |
| 旧工具链 buggy_43.sol | 新进程 5/5 为 254；哈希种子 0–7 都为 254；同进程 10 次：254、254、252、252、253、254、253、253、252、253；6c 顺序第 87 个为 252 | legacy_*.json(l) |
| 生产工具链 buggy_43.sol | 同进程 10 次节点与图哈希相同；循环条件局部写为空 | production_repeat_in_process.jsonl |

未证明：旧工具链不确定性的代码位置；239 个文件中不稳定事实的规模（CP2.1 给出）；对 6c（DFG v2）已有结论的影响。

### 20.4 用户批准、原文差异与待确认设计

- Codex 处理正确：生产部分全部要求；6c 首差即停，没有重试或放宽；把 0.4.11 → 0.4.12 的单列先请用户批准；归档方式保留原字节。
- 新发现：空体 if 的边种类缺陷（Codex 的测试未覆盖空体 if）；6c 参考事实本身不确定。
- 待用户批准：D20（6c 稳定事实判据）。待确认：D19。D9/D10 待确认，D12/D13 待定。
- 提示用户：6c 的 L1 参考事实来自不确定的旧工具链，可能影响 DFG v2 以 6c 为固定参考的结论；本模块不改动 6c。

### 20.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp2_review_v1/README 全文，CHANGE_LOG:143123、PROGRESS:32407 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP3 不能开始。顺序为用户批准 D20 → Codex 执行 CP2.1 → Claude 审查 → CP3。本轮提交并 push 到 `compile-repair`。


## 21. 2026-11-14 CompileRepair CP2.1：修复条件边并按 D20 停止 6c 验收（修改 AI：Codex）

### 21.1 任务、依据与范围

用户要求执行 PROMPTS r2.9 §4.4b，明确 D20 已于 2026-11-14 获批，原话“同意 D20”。先完成 git pull --ff-only origin compile-repair（Already up to date），起始 HEAD=1ed79a6708f505ecb9aa80b157a43f9e07608c9f；通读 r2.9 全文，尤其 §1.12/4.4/4.4b、共享上下文、分层和强制记录规则，阅读 HANDOVER §0–5、DECISIONS、本文 §19/20、cp2_review_v1/README、docs/README 与 REPORT_TEMPLATE。实现前捕获 baseline.json 并写入 authorization.json；DECISIONS D20 更新为已定。

生产文件仅 toolchain/slither.py，修改限定 graph_facts；新增 tests/test_graph_branches.py 与 tests/fixtures/graph_branches.sol。记录文件为 CP2_REPORT.md（只追加 CP2.1）、PROGRESS.md、docs/CHANGE_LOG.md、docs/HANDOVER.md（当前 §0–5 与末尾历史）、docs/DECISIONS.md。新开发/验收证据在 artifacts/cp2_1_v1：run_corpus.py、run_replay.py、run_checks.py、launch_phase.py、package_store.py、summarize.py、audit_replay.py、audit_frozen.py、check_docs.py；另有 baseline/authorization/evidence_seal、实际调用和测试日志、逐份验收、汇总、归档审计、只读复算、文档与保护检查、交付清单及 README。新正式批次为 cr_store_mando_v3/v4 和 cp2_6c_v2，各交付 README 与无损 store.tar.gz；精确文件清单见 delivery_inventory.json。

CP0–CP2 旧产物、审查产物、PROMPTS、既有 fixture、原始语料、scripts、根 HANDOVER 和根 training_changes 均未改。源码与环境也未另行修补；生产 Python 文件数维持 14，层级不变。cp2_desc_v1 因停止未创建。

### 21.2 实施方式和重要选择

graph_facts 先验证每个 son 都属于当前函数，再按 node.sons 原顺序消费 son_true/son_false 两条分支 occurrence。目标相同的两次出现按 true、false 各一次输出；目标不同则保留 sons 本身的顺序，不额外排序。非条件节点全部 next；缺少、重复或多出条件分支均抛 ValueError。没有改节点身份、IR、length、调用归类或 D3。18 个新测试用例验证 merged target、反向 sons、空体 if/else、带 else、while/for 与损坏端点；原 graph 和全套功能测试同步通过。

生产验收复用 CLI 的 result_check，在记录 flush 后逐份校验，再封存；与旧 v1 逐个完整 JSON 比较，只允许审查 if_edge_kinds.json 中 40 文件/86 IF 的第二条同目标边从 true 变 false。两次各检查所有 IF/IFLOOP 一 true 一 false、无跨函数边，第二次另核对图原字节。原 CP2 驱动适配到新目录，无任何旧批次覆写；同版本生产归档与既有 CP0 版本归因继续检查。

6c 复用 scripts/DFG/dfg_v2/validate_slither.py 的 _compile、slither_full_facts（原 SHA256 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8），不复制或修改冻结实现，不 import 审查脚本。occurrence_keys 和 historical_target 与旧 CP2 驱动保持相同 AST，完整键、重数、原始路径、版本与 CWD 不变。main 保持 239 原顺序；差异只在独立子进程连续做 10 次，再与 main 合为 11 次按每键 min/max 判定。先用 12 个合成边界检查验证稳定不等、参考独有、范围端点与样本数错误均被正确处理。

实际问题是第 227 份 buggy_44.sol 的 reference_only 键，D20 明确要求失败；已停止而未尝试改 seed、GC、键或采样数。audit_replay.py 从已封存原始字节独立复算 227 个 main 与四组固定样本，确认驱动判定一致，新增提取为 0。版本汇总显式只统计成功选择，三个 selected_version=null 的失败独立统计。WSL 调用沿用 UTF-8/base64，文档拆短命令；无安装、依赖错误或自动审批拒绝，本轮无开发测试失败和验收重跑。

### 21.3 实测与数据结论

语料身份沿用 cp0_v2/recon.json 的 846 源文件 SHA，6c 原始路径 239 个逐一绑定；基线完整源/代码/环境清单见 baseline.json。两次 production 支持 92 版，均 843 成功/3 预期失败；全部成功图原字节 843/843 相同。每次 110,996 节点、87,645 CFG 边、45,565 调用；76,631 next、5,507 true、5,507 false。与旧 v1 只差 86 个指定标记，节点、调用、其余边完全相同。同版本生产归档 842/842 相同，1 个既有新增编译器导致 0.5.6→0.5.5，仍归 (a)，没有新归因调整。

| 运行 | 实测 | 耗时（驱动/测试计时） | 证据 |
|---|---|---|---|
| production 升序 v3 | 843 success、3 unrepaired，846 验收通过 | 262.80 秒 | ascending1_receipt、acceptance |
| production 升序 v4 | 843/3；843 图重复一致 | 271.14 秒 | ascending2_receipt、acceptance |
| regression_6c v2 | 227/239 已测；223 main 精确、3 D20 通过、1 D20 失败 | 135.41 秒，外层 140.85 秒 | summary、comparison、replay_invocation |
| 生产模块测试 | 585 passed/6 skipped | 63.99 秒 | pytest_production |
| mando 模块测试 | 147 passed/444 skipped | 12.61 秒 | pytest_mando |
| 冻结 DFG | 2653 passed/9 既有 warnings | 152.21 秒 | pytest_dfg |

四个主运行差异为顺序 87 access_control/buggy_43.sol、207 reentrancy/buggy_24.sol、226 reentrancy/buggy_43.sol、227 reentrancy/buggy_44.sol。各一个新进程、10 次追加，共 40 次；总提取 267 次。前 3 个差异文件按 D20 通过，最后 1 个失败。全部 9 个波动键及逐次重数列在 CP2_REPORT 的 CP2.1：均 L1 DEF，L1 其他 kind 与 L2 各 kind 均 0；5 继承上下文、4 非继承。未证明内部根因。

唯一失败键源 SHA=8e037273ea617a302b2db77c278ba36931dd57474df202f78aa3c4b0ba815f86、solc=0.5.0，函数 MultiHashWrapper._combineMultiHash(MultiHashWrapper.MultiHash)，声明上下文 MultiHashWrapper、inherited=false，node start=9337、declaration start=9172、function start=9070，fact=[282,out,DEF]、tags=[]。参考重数=1，main+10 次全为 0。完整键及参考原始行见 captured_replay_audit.json，样本见 cp2_6c_v2 归档 extractions/0227、additional/0227。该文件 Feed 上下文另有一个波动键，不得合并替代缺失键；总 occurrence 相同也不能替代逐键判定。

生产新 tar 各 4,229 成员，6c 停止 tar 309 成员，逐成员 SHA 回读均通过，原散文件保留。归档 SHA：v3=29a4ccba5612d2a6a1df896647a66d4babd7f6e175b424ece695f152eddba513；v4=54f9f53d666df7e6bc51ee9954843aaec9bdfc34290fea891add03aaee7a75e5；6c=6dee59c464bf066930b55546f2d1c7a704fddefab2f132284797b6374c7beae0。seal SHA 和全部编译器路径/身份/argv 见 CP2_REPORT 与 tar 内 seal/trust/invocations。类别和成功版本分布见 cp2_1_summary.json。

### 21.4 用户批准、原文差异与待确认设计

用户 2026-11-14 原话“同意 D20”，授权仅按 r2.9 执行固定采样及稳定事实判据；authorization.json 保存日期、来源、原话、费用上限 0、禁安装/下载和未授权额外变化。D20 当前状态已定，不因本次失败而回退为待批；D3/D5/D16 以及 CP2 已批准的既有下限归因均保持。没有偏离 §4.4b 的采样、停止条件或目录范围；尚未执行降序是遵守停止条件，不能写成全部验收完成。

登记的问题及建议（未实施）：固定 11 样本未覆盖参考键，现有材料不能定位内部原因，也不能证明更多运行中绝不会出现。建议先独立复核封存原始行及运行契约，任何补测、改变样本数/键/判据或修补旧 Slither 的方案，都必须先提供具体范围并获用户确认。本轮没有实施替代方案，未改变旧 DFG/6c 历史结论。

### 21.5 验收、资源、未执行事项与停止

§4.4b 第 1、2 项及第 5 项测试已通过；第 3 项在第 227 份不通过，第 4 项未运行。12 个 D20 边界检查通过；对已保存 227+40 次提取的只读复算通过，criterion_passed=false，明确区分证据审计和任务验收。三个已知 production 失败仍如预期，无成功空图。当前整体 CP2.1 未通过，剩余 12 个 6c、全部降序和 CP3 未运行；无新增采样或重跑。

使用现有 CPU 环境，OMP/MKL 均 2，未测峰值资源；生产 Python 3.10.21/Slither 0.11.6/crytic-compile 0.4.2，mando 3.7.12/0.8.0/0.2.4。96 可信 solc 中支持 92 版；无安装、下载、LLM、HGT 训练、GPU 锁或全局 solc 选择改变，费用 0。最终 doc_check 与 frozen_audit 结果在本段末尾追加；所有强制记录和检查完成后本地提交，标题以 CP2.1 开头，准确提交号由 git log 获取，不自动 push。


最终检查补记（仍属 §21.5，修改 AI：Codex）：doc_check v1 对全部 9 份文档通过，追加偏移为 CP2_REPORT=20093、PROGRESS=32940、CHANGE_LOG=147458；其余全文检查。补记后的最终同范围复检保存在 doc_check_v2.jsonl 与 doc_check_v2_invocation.json。frozen_audit 通过：28,451 个受保护跟踪文件（其中模块外 27,845、旧产物 546、旧 fixture 29）、8,548 个旧 seal 成员、239 原始 6c 目标、354 代码引用、96 solc 文件均未变；mando 118 / production 145 份包与 conda 元数据集合及内容相同，全局选择环境相同。graph_facts 之外的 11 个既有 Slither 函数、occurrence_keys 和 historical_target 的 AST 均保持；生产 14 文件与测试封存的实现 SHA 一致，五份文档旧历史全部保留。没有验收重试或审批拒绝。提交仅包含 delivery_inventory 所列的新批次、允许代码和记录，正式旧批次不暂存；当前停止结论不变，本地提交后不 push。


## 22. 2026-11-14 CompileRepair CP2.1 审查与方案 r2.10（修改 AI：Claude）

### 22.1 任务、依据与范围

用户要求（2026-11-14）：Codex 已完成 CP2.1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP3。起点 `compile-repair@63a1510b`。审查对象：`toolchain/slither.py` 的 `graph_facts` 差异，`tests/test_graph_branches.py`，两份新生产存储（解包核对）与 v1 的比较，`cp2_6c_v2` 与 `cp2_1_v1/captured_replay_audit.json`，CP2_REPORT 的 CP2.1 节与 CHANGE_LOG §21。

修改：`PROMPTS.md`（r2.9 → r2.10）；新增 `artifacts/cp2_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（新增 D20a，历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 22.2 实施方式和重要选择

- 图：读代码差异；解包 v1、v3、v4，逐个比较 graph.json，检查边差异是否正好等于上轮审查列出的 86 个节点，并统计边种类。
- 6c：核对 Codex 记录的失败键（reference-only，声明上下文 MultiHashWrapper 的 `[282, out, DEF]`），在 Claude 的 Slither 0.8.0 环境中对同一文件同进程连续抽取 40 次。该键出现 18 次，证明它不稳定；再查看 10 个不稳定键的源码行，都是 for 循环体内按下标写入的数组、DEF 记在循环条件行，属于同一类。
- 判据：D20 以固定 11 个样本界定不稳定，低概率事实会被误判。可选做法有：（a）追加采样直到观察到参考重数；（b）按“循环条件上的数组 DEF”这一类别豁免；（c）放弃 6c 重放。选择（a）：它不依赖对旧工具链内部机制的推断，只用观测；设上限 100 次并保留停止条件；稳定键与键定义不变。（b）需要从 6c 参考行推断节点类型，依据不足；（c）会丢掉已经得到的 223 个逐条相同的证据。改变判据需要用户批准，记为 D20a。
- 续跑：第 228–239 个文件在新进程中运行。D20 与 D20a 都是逐文件判定，不依赖主运行的进程历史。

### 22.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| v3/v4 seal | 各 4,228 个文件哈希一致 | 审查时核对 |
| 图 | 843/843 字节相同；节点、调用与 v1 843/843 相同；边差异 86 条，全部 true → false，集合与 if_edge_kinds.json 相同 | 同上 |
| 边计数 | next 76,631、true 5,507、false 5,507 | 同上 |
| buggy_44.sol 40 次 | MultiHashWrapper 上下文 18 次（单独 6、与 Feed 同时 12）、Feed 30 次、都没有 4 次；总数 357/358/359 为 4/24/12 次 | legacy_buggy44_repeat40.jsonl |
| 不稳定键 | 10 个，全部 L1 DEF；变量 `out` 或 `records`，在 for 循环体内按下标写入；记在循环条件行 | CP2_REPORT、源码 |

未证明：用户环境（Python 3.7）中该键的出现频率；旧工具链不确定性的代码位置；DFG v2 以 6c 为固定参考的结论受影响的程度。

### 22.4 用户批准、原文差异与待确认设计

- Codex 处理正确：图修复与两次生产重跑；6c 停止后没有追加样本、改种子或改键；用审计脚本重算了全部已运行比较。
- 新发现：第 227 个文件的停止是采样不足；不稳定键属于同一类。
- 待用户批准：D20a。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 22.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp2_1_review_v1/README 全文，CHANGE_LOG:157183、PROGRESS:34700 追加区间，6 个文件全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP3 不能开始。顺序为用户批准 D20a → Codex 执行 CP2.2 → Claude 审查 → CP3。本轮提交并 push 到 `compile-repair`。


## 23. 2026-11-14 CompileRepair CP2.2：完成 D20a、6c 续跑与降序比较（修改 AI：Codex）

### 23.1 任务、依据与范围

用户要求执行 PROMPTS r2.10 §4.4c，并给出 2026-11-14 原话“同意 D20a”。先 git pull --ff-only origin compile-repair，Already up to date，起始 HEAD=36c6109fa9271608feb8f4634eca6ab7ff6a192a；完整阅读 PROMPTS，重点 §1.12/1.13/4.4/4.4b/4.4c 和共享上下文，读 HANDOVER §0–5、DECISIONS、本文 §21/22、cp2_1_review_v1/README、docs/README、REPORT_TEMPLATE。先写 authorization.json、baseline.json，DECISIONS 当前 D20a 改为用户已定并追加历史。

生产文件和测试文件均不修改。新脚本位于 artifacts/cp2_2_v1：run_replay.py、audit_replay.py、run_corpus.py、run_checks.py、launch_phase.py、summarize.py、package_store.py、audit_frozen.py、check_docs.py；对应授权/基线/计划、invocations、逐份验收、汇总、测试日志、归档审计、最终检查和交付清单均在该新批次，精确文件名由 delivery_inventory.json 列全。正式新批次 cp2_6c_v3、cp2_desc_v1 各交付 README 与 store.tar.gz；本地散文件保留。文档修改仅 CP2_REPORT.md（追加 CP2.2）、PROGRESS.md、docs/CHANGE_LOG.md、HANDOVER.md（第 0–5 节当前状态及第 6 节末尾）、DECISIONS.md。CP0–CP2.1 旧产物、PROMPTS、scripts、原始语料、根交接和训练改变文档不改。

### 23.2 实施方式和重要选择

run_replay import 复用 cp2_1_v1 的 occurrence_keys、historical_target、ranges、archive_extraction；冻结 validate_slither._compile 与 slither_full_facts 原 SHA256=4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8，不修改、不 monkeypatch，不导入 Claude 审查脚本。参考报告与 seal 先按 PROMPTS 的 SHA 校验，再只读；239 原始目标路径先绑定 SHA。重放沿用 mando/regression_6c、原版本、原 target 和仓库根 CWD。

先检查旧 cp2_6c_v2 seal，前 226 的比较行原样复用，227 的 main+10 样本只读加载。D20a 另启新进程，每次完整抽取并记录所有失败键重数；每个键必须实际出现参考值，不能以扩大的范围替代；全部目标首次满足即结束，最多 100。D20 判定保留，追加新波动单列。合成检查覆盖参考独有、上限、参考 0、范围含参考但未实际观察、多个键不同次出现及原稳定键变化。只读 audit_replay 以独立计数实现复算所有现存样本，验证首个可通过样本后没有继续抽取，并导出全部源码行和计数。

227 通过后新进程按原序续跑 228–239；差异文件另起新进程连续 10 次，按原 D20 判据裁定。全部通过才启动 production 降序。新 run_corpus 调用原 CLI 的 result_check 逐份检查，完整 846 输入只允许三份已知 Slither 侧失败；同版本仍核对节点/IR，防止掩盖异常。与 v3 比较按 key5 和规范化有序 IR，length 仅诊断。旧 CP2.1 未执行的降序分支只计划 843 成功输入，本轮按现行 r2.10 把三份已知失败也纳入，不改生产实现或 D5。

运行问题处理：WSL 无 rg，改用已有 git ls-files 与 Python 定向读取，未安装工具；初次文档写入封装因 Markdown 反引号触发 JavaScript 语法错误，工具代码未执行、文件未变，改成普通 UTF-8 文本与缩进命令段。正式验收和测试无失败、无重试；没有自动审批拒绝。Windows/WSL 用既有代理完成 Git 同步，未改变 fail-closed 网络设置。

### 23.3 实测与数据结论

| 项目 | 实测 | 证据 |
|---|---|---|
| D20a 第 227 份 | 新进程第 1 次观察到参考重数 1，立即停止 | cp2_6c_v3/d20a/0227 |
| 6c 合计 | 239/239 通过：234 精确、4 D20、1 D20a | cp2_6c_v3/summary.json |
| 本轮抽取 | 23 = 12 主运行 + 10 D20 + 1 D20a；旧 227 主样本不重跑 | captured_replay_audit.json |
| 不稳定键 | 12，均 L1 DEF；5 继承、7 非继承 | 同上 unstable_facts |
| 降序全量 | 843 success、3 已知 slither_side_failure；92 支持版 | descending_receipt.json |
| 升降序节点/IR | 229 同版、614 不同版，843/843 key5 + IR 同，差异 0 | descending_comparison.json |
| length 诊断 | 815 同、28 不同，不影响 D4 验收 | descending_acceptance.jsonl |
| production 模块 | 585 passed/6 skipped，64.70 秒 | pytest_production |
| mando 模块 | 147 passed/444 skipped，13.29 秒 | pytest_mando |
| 冻结 DFG | 2653 passed/9 既有 warnings，160.04 秒 | pytest_dfg |

第 227 源 SHA=8e037273ea617a302b2db77c278ba36931dd57474df202f78aa3c4b0ba815f86，solc 0.5.0，MultiHashWrapper._combineMultiHash 的非继承 out DEF，第 282 行，function/node/declaration start=9070/9337/9172，参考 1、旧 11 次全 0、追加第 1 次 1。Feed 继承键追加为 0，保持独立键。第 239 份 spank_chain_payment.sol 的 result/b DEF 波动分别在 for/while 条件上，10 次附加后满足 D20；全部逐次重数及原行源码在 CP2_REPORT 的 CP2.2 表和 captured_replay_audit.json，不以总 occurrence 数代替逐键比较。

614 个版本差异均在同一小版本系列，完整列表见 descending_comparison.json；例如 0.4.12→0.4.26 的 26 份、0.5.0→0.5.17 的 124 份均节点/IR 不变。different_entries=[]，没有实际 IR 文本差异可进一步归因。按类别统计来源/系列/标志已导出，不读取标签。CLI 返回 2 代表三份预期失败，验收驱动返回 0；未修复输入不写 graph。

6c 驱动用时 28.14 秒，外层 33.57；降序 265.68 秒，外层 267.45。两 tar 回读通过：cp2_6c_v3 57 成员、318121 字节、SHA b432b70257e061a5b57bc19a80f8754fdd1d03e27f2bcee3e64b64084d2a724b；cp2_desc_v1 4229 成员、14207625 字节、SHA 02ccc74dce4a9acde715d0d8a133d87d87345cbb9fcbba7951a3bc82d4ceb2c1。完整 seal 和成员清单在对应 archive_audit，散文件保留，不覆盖旧批次。

### 23.4 用户批准、原文差异与待确认设计

用户 2026-11-14 原话“同意 D20a”，authorization.json 记录来源、日期、profile 精确版本、费用上限 0、最多 100 与提前停止、禁下载/安装和保护边界；DECISIONS 已定。D20 其他部分、occurrence 键、源路径/CWD/版本、D3/D5/D16 和旧历史不变。本轮按 r2.10 完成，没有方案外调整，不需要新的安装或授权。原 CP2.1 按 D20 停止的结论保留，新授权的 D20a 通过不回写旧结果。

只登记的证据边界：有限样本通过不证明旧工具链全局确定性或内部根因；新增 while 观测也说明上轮十键的 for 类描述不是所有波动键的必要条件。本轮没有提出或实施替代判据，没有按语法类别豁免差异。D19、D9/D10、D12/D13 的既有待定状态保持；CP3 仍须先审查 CP2.2。

### 23.5 验收、资源、未执行事项与停止

§4.4c D20a、239 份重放、降序比较以及两环境模块/DFG 测试全部完成并通过；11 个合成边界检查、239 份只读复算及 843 份独立跨版本复算通过，没有新增抽取用于审计。强制测试命令及 rc/环境/临时目录见 pytest_*.json；CPU OMP/MKL=2，未测峰值资源。mando Python 3.7.12/Slither 0.8.0/crytic-compile 0.2.4；production 3.10.21/0.11.6/0.4.2；可信 96 版中 92 支持、4 历史，不改全局 solc。

doc_check 按 baseline 的追加前字节偏移检查 CP2_REPORT=32299、PROGRESS=35191、CHANGE_LOG=161129；HANDOVER、DECISIONS 和三个新 README 全文，共 8 份。实际结果和最终保护检查在本段末尾补记，检查通过前不提交。当前准备本地提交，实际提交号由 git log 获取；不自动 push。CP3、额外抽样和重跑 CP0–CP2.1 均未运行；无安装、依赖/语料/文档下载、LLM、HGT、GPU 锁、全局 solc 或网络配置改变，费用 0。


最终检查补记（仍属 §23.5，修改 AI：Codex）：doc_check v1 全部 8 份通过，追加偏移为 CP2_REPORT=32299、PROGRESS=35191、CHANGE_LOG=161129；其余全文检查。补记后的同范围最终复检写入 doc_check_v2.jsonl 与 doc_check_v2_invocation.json。frozen_audit 通过：28,512 受保护跟踪文件（模块外 27,845、旧产物 604、旧 fixture 30）、17,315 旧 seal 成员、239 原始目标、354 DFG 引用和 96 solc 文件均未变；mando 118 / production 145 份包与 conda 元数据集合及内容相同。全部 14 个生产文件字节不变，并与实际测试 seal 相同；Slither 全部 12 个函数及旧 occurrence/D20 helper 复用保持，五份文档旧历史保留。git diff --check 通过，受跟踪改动仅五份允许记录。最终按 delivery_inventory 精确暂存新批次及文档，核对暂存字节后本地提交，不 push；CP2.2 本机验收完成，待独立审查。


## 24. 2026-11-17 CompileRepair CP2.2 审查与方案 r2.11（修改 AI：Claude）

### 24.1 任务、依据与范围

用户要求（2026-11-17）：Codex 已完成 CP2.2；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP3。起点 `compile-repair@0e6830edc`。审查对象：CP2_REPORT 的 CP2.2 节、HANDOVER、DECISIONS、CHANGE_LOG §23、PROGRESS，`cp2_6c_v3` 与 `cp2_desc_v1` 两个归档（解包核对），`cp2_2_v1` 的授权与记录；另核对 CP2.2 之后仍在生产代码中的版本读取路径，以及 CP3 依赖的诊断前提。

修改：`PROMPTS.md`（r2.10 → r2.11）；新增 `artifacts/cp2_2_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节第 15 条补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 24.2 实施方式和重要选择

- 生产代码：`git diff --stat 36c6109fa 0e6830edc` 在 artifacts 之外只有五份记录，CP2.2 没有改代码与测试，因此没有重跑测试。
- 降序：解包 v3 与 cp2_desc_v1，独立比较状态、版本对、节点 key5/IR/类型/改动标记、边与调用，并统计 graph.json 字节差异落在哪些字段。
- 6c：参考报告只在用户本机，审查复算重放侧：三个 seal、D20a 样本中失败键的次数、续跑 12 个文件的提取总数与 SHA、第 239 个文件 11 次样本的逐键变化；再在 Claude 的 Slither 0.8.0 环境中用冻结抽取对第 239 个文件同进程连续 30 次，独立确认两个键的波动。
- 版本读取：CP2.2 的结论成立后，检查模块面对任意输入时 CP3 之前的路径。把 19 个特性夹具与一个注释含 Latin-1 字节的合约送入 `pragma_interval`，并用 solc 与生产 Slither 对照。发现两个缺陷后读 `pipeline.repair_unit`，确认两种异常都会记为 unsupported_version_constraints 并直接返回。
- 处理选择：（a）在 CP3 中顺带修复；（b）单独 CP2.3 修复后再 CP3。选择（b）：用户要求问题先解决并核实；CP3 的失败分类以第 1、6 步之后的结果为输入，不先修复会把可编译的输入统计进版本约束类。修复只换指令定位方式，表达式语义不变，用 MANDO 846 个文件与夹具上的等价测试和一次与 v3 字节对比的回归来证明。
- CP3 前提：探测三个含错夹具在 0.4.12–0.8.38 的命令行与 standard JSON 输出；在生产 Slither 上对三个 Slither 侧失败文件试 3.2 节第 10 行的改写。

### 24.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 降序 seal | 两个存储各 4,228 个文件一致 | verify_desc.json |
| 降序状态与版本 | 843 成功 + 3 slither_side_failure，两次相同；229 同版、614 不同版，跨系列 0 | 同上 |
| 降序节点与图 | 843/843 key5、IR、边、调用相同；graph.json 815 个字节相同，28 个只在 87 个节点的 length 上不同 | 同上 |
| 6c seal | cp2_6c_v3、continuation、d20a/0227 三个 seal 0 不一致 | verify_6c.json |
| 第 227 个文件 D20a | 1 个样本，失败键出现 1 次（MultiHashWrapper 非继承） | 同上 |
| 第 228–239 个文件 | 提取总数与记录相同、SHA 相同；11 个等于参考总数，第 239 个 754 对 755 | 同上 |
| 第 239 个文件 11 次样本 | `result` DEF 0,0,0,0,0,0,0,0,0,0,1；`b` DEF 1,1,0,1,1,1,1,1,1,1,1；其余键不变 | 同上 |
| 第 239 个文件独立 30 次 | `result` 7 次、`b` 缺失 9 次；总数 753/754/755 为 8/17/5 次 | legacy_spank_repeat30.jsonl |
| 版本读取：新语法 | 19 个特性夹具中 5 个 `Unsupported: Solidity parser ERROR/MISSING`；同样的文件 solc 0.8.38 rc 0，生产 Slither 成功 | probe_inputs.json |
| 版本读取：非 UTF-8 | UnicodeDecodeError；solc 0.4.24、0.5.17、0.8.0、0.8.38 rc 0，生产 Slither 成功 | 同上 |
| 诊断格式 | 命令行只写 `Error:`；位置格式 0.5.17 及以前与 0.8.0 起不同；standard JSON 在 0.4.12 内部错误、0.4.12/0.4.17 无位置；措辞随版本变化 | probe_diagnostics.json |
| 第 10 行改写 | 3 个文件在 0.4.24、0.4.26 由 AssertionError 变为成功；0.4.12 原文 solc 失败、改写后成功 | probe_slither_compat.json |

未证明：6c 参考侧数字（报告只在用户本机）；用户环境（Python 3.7）中第 239 个文件的波动频率；0.6、0.7 的诊断格式；新语法与非 UTF-8 输入在外部语料中的数量（CP3 统计）。

### 24.4 用户批准、原文差异与待确认设计

- Codex 处理正确：按 D20a 只追加到首次观察即停；续跑在新进程中按原顺序；第 239 个文件按 D20 判定；降序覆盖全部 846 个输入；没有改代码、键或判据。执行中的问题（WSL 没有 rg、文档写入封装的引号错误、旧驱动只列 843 个成功输入）处理得当，没有影响结果。
- 新发现：两个版本读取缺陷（自 CP1 起存在，CP1–CP2.1 审查漏掉）。修复不改变已定决策的语义，只改实现方式，不需要新的用户批准。
- 分支：CP2.3 与 CP3 继续在 compile-repair；5080 主线上本模块的导入改动留到迁移时合并。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 24.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp2_2_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP3 不能开始。顺序为 Codex 执行 CP2.3 → Claude 审查 → CP3。本轮提交并 push 到 `compile-repair`。


## 25. 2026-11-17 CompileRepair CP2.3：修复字节级版本读取并保持回归（修改 AI：Codex）

### 25.1 任务、依据与范围

用户要求执行更新后的 CP2.3，先读共享上下文、通读 PROMPTS；实质方案改变先咨询并记录。执行 r2.11 §4.4d；起点 compile-repair@361772f74b28b4dce0ad094907dc3dbf27a17794，git pull --ff-only origin compile-repair 为 Already up to date。已读 PROMPTS 全文、HANDOVER §0–5、DECISIONS、本文 §23/24、docs/README、REPORT_TEMPLATE 与 cp2_2_review_v1 的 README/probe_inputs。先记录 baseline，再复现旧代码，随后修改。

生产只改 rules/environment.py、pipeline.py；新增 tests/test_pragma_bytes.py 和 tests/fixtures/pragma_inputs 下 latin1_comment、no_pragma_latin1、masked_pragma、two_pragmas、nested_pragma、union_pragma 六个 .sol。新驱动仅在 artifacts/cp2_3_v1：reproduce.py、launch_phase.py、run_checks.py、audit_tests.py、run_corpus.py、package_store.py、audit_frozen.py、check_docs.py、write_documents.py。新正式存储 cr_store_mando_v5。文档为 CP2_REPORT 追加 CP2.3、PROGRESS、本文、HANDOVER §0–5 与历史追加、DECISIONS 历史追加、两个新 README。完整新增证据文件由 delivery_inventory 列出。CP0–CP2.2 旧产物、旧夹具/测试、PROMPTS、scripts、语料、根交接及训练改变文档不改；不迁移分支。

### 25.2 实施方式和重要选择

复用 code_only 等长遮盖后按字节识别顶层 pragma，花括号深度屏蔽合约/函数体；新增 _pragma_spans 为 interval/patches 的唯一定位函数。表达式求值从冻结 scripts/DFG/state/stage_f/versioning.py:10–23 复制为 _expression_interval，来源 SHA256=130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18。选择复制表达式而不调用冻结 interval，是因为后者要求整文件 AST；遵循 Prompt 的明确授权，不改其表达式语义。冻结构造只在本轮测试中导入。Latin-1 无损解码不改源码字节，infer_interval 同步处理；pragma_patches 保留逆序、换行和等长空格。pipeline 的异常分支仅保留 Unsupported；MANDO metadata 路径仍按 UTF-8 和哈希校验。

run_corpus 沿用同一 CLI/result_check，846 个输入顺序和升序回归参数与 v3 相同，每份验收状态、reason、选定版本、settings、flags 和完整 graph 字节，首个差异即停止。正式运行一次。run_checks/package_store 由上轮证据驱动改写到新目录，来源 SHA 见 reuse_sources.json；未导入审查脚本。已成功 CLI 测试不重跑，audit_tests 只读复算并无损打包 58 成员的两个探针存储。最终 v5 的 4,229 成员也逐个回读哈希，原文件保留。

问题处理：基线扫描误用了 cp0_1_compilers_v1 的首次 seal；README 已登记其被 seal_v2 替代。核对 README 与既有跟踪基线及 seal_v2 均一致后，沿用上一轮已审计结果集合并加入 CP2.2；所有旧跟踪文件仍逐一保护，未改历史封存。development_issues.json 保存原异常和证据，不作为本轮验收豁免。Windows/WSL 继续使用既有代理完成 Git pull；文件定位用已有 git ls-files/Python，未安装工具；UTF-8 文档用 Python 写入。首次整段文档命令超过 Windows 命令行长度（os error 206），未创建进程或修改文档；改为分块写入新 write_documents.py 再执行。该 OS 长度错误不是审批拒绝。

### 25.3 实测与数据结论

| 项目 | 结果 | 证据（cp2_3_v1） |
|---|---|---|
| 修改前复现 | 6/6 CLI 被拒，5 Unsupported + 1 UnicodeDecodeError | reproduction.json |
| 编译工具对照 | 9/9 solc rc0、production D3；Latin-1 覆盖四个指定版本 | reproduction_invocations.jsonl |
| 冻结等价 | production/mando 各 846 输入 + 28 可解析夹具全部同；8 个旧路径无法处理者明列 | equivalence.json |
| 新 CLI 正/负例 | 9 成功、1 并集按预期拒绝，无重复编译审计 | probes.json |
| v5 全量 | 843 成功、3 已知 Slither 侧失败，92 支持版本 | regression.json |
| v3 对比 | 各记录字段 846/846 同，843/843 图字节同，差异 0 | regression_acceptance.jsonl |
| 生产文件 | 14；仅两份修改，共 +73/-16 | code_change_summary.json |
| production 测试 | 607 passed/6 skipped，69.72 秒 | pytest_production |
| mando 测试 | 167 passed/446 skipped，13.33 秒 | pytest_mando |
| DFG v2 测试 | 2653 passed/9 既有 warnings，150.01 秒 | pytest_dfg |

原始输入身份取自 cp0_v2/recon.json（SHA256=bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6），846 源码逐一验哈希；回归原参照 v3 seal 首先验全体成员。新 v5 用时 239.81 秒，外层 241.22 秒；3 个失败仍是 reentrancy_bonus/reentrancy_cross_function/reentrancy_insecure，不写 graph。CLI rc2、验收驱动 rc0 均符合预期。v5 seal=db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b；tar=de29da390672b53d185c920bb994cbcee62b6dd53fd76510d952c92880d2c622，14148449 字节、4,229 成员。每次调用的路径/版本/参数/耗时与失败记录均封存。

五个新语法 CLI 选择 0.8.13/0.8.19/0.8.28/0.8.22/0.8.29，Latin-1 选择 0.4.24；另外三个正例为 0.5.0/0.5.1/0.4.16。新源码未改写。全部受测正例成立不代表所有未来输入或图语义已经穷举；非法嵌套 pragma 只检验定位忽略，不声称可编译。

### 25.4 用户批准、原文差异与待确认设计

本轮依据用户 2026-11-17 的 CP2.3 指令实施已有 r2.11 方案，没有替代方案或额外下载/安装请求；D3/D5/key5/settings、D20/D20a、已知版本读取和既有决策状态不改。DECISIONS 只追加实现证据。基线 seal 选择的问题是证据版本识别，不改变任何 CP2.3 验收判据。

实质限制只登记两项既有缺口：双竖线 pragma 不支持、Slither 进程内没有超时，按 CP3 既定安排分类和提出后续方案，本轮不实现。D19 与 D9/D10 等待定状态保持。没有发现需要先咨询的新方案调整。

### 25.5 验收、资源、未执行事项与停止

§4.4d 的复现、指定修复、等价/边界测试、生产 CLI 正负例、两环境模块/DFG 测试与 846 全量验收全部符合预期。非测试文件 14，分层测试通过；只在当前两份生产文件改功能。环境为 production Python 3.10.21/Slither 0.11.6/crytic-compile 0.4.2 与 mando 3.7.12/0.8.0/0.2.4。CPU OMP/MKL=2，费用 0，峰值未测。

doc_check 使用追加前字节数 CP2_REPORT=43516、PROGRESS=38417、CHANGE_LOG=175780；HANDOVER、DECISIONS 和两个新 README 全文检查。最终结果在本节末尾补记。实际测试命令为各环境 python -B -m pytest -q -ra -x -p no:cacheprovider，加独立 --basetemp；详见 pytest_*.json。完整性审计核对旧跟踪内容、旧 seal 成员、源码、环境、solc、DFG _code_refs、函数保护与运行/测试代码指纹；最终结果见 frozen_audit。

CP2.3 本机验收通过后等待独立审查；CP3 未开始，6c 未重放。未安装、下载编译器/依赖/语料/文档、调用 LLM、训练、申请 GPU 锁或修改全局 solc、网络配置。强制记录/最终检查通过后本地提交，提交号见 git log；不自动 push。


最终检查补记（2026-11-17，修改 AI：Codex）：首次 frozen_audit.json 的实现指纹项未通过，原因是新收集的证据包含旧 settings 测试手工创建的 6 个空实现指纹 seal（code_commit=test），并非生产代码差异。test_seal_diagnosis.json 逐条列出；保留首次结果和 audit_frozen_initial.py，审计明确验证恰好这 6 个手工 seal，再核对全部 3 个真实 CLI seal 的 14 文件指纹，最终 frozen_audit_v2.json 全部通过。测试、生产代码与正式回归没有重跑或修改，未改变验收标准。其余保护项两次均通过：28,574 受保护跟踪文件（模块外 27,845、旧产物 668、旧夹具 30）、21,599 旧结果成员、239 原始目标、354 DFG 引用、96 solc 文件与两环境元数据集合/内容（production 145、mando 118）均未变；12 个非目标函数 AST 保持，生产文件仍 14 且仅两份获授权修改，测试与 v5 实现指纹相同，文档旧历史保留。

doc_check v1 的 7 份文档全部通过；本补记与新目录说明更新后的最终复检记录在 doc_check_v2.jsonl 和 doc_check_v2_invocation.json。git diff --check 已通过。按精确 delivery_inventory 暂存并核对字节后本地提交，不 push；CP2.3 本机验收完成，独立审查尚未进行。


暂存检查补记（修改 AI：Codex）：首次 git diff --cached --check 指出新 v5 README 文件末尾多一个空白行，记录于 staging_attempt1.json。只删除该冗余换行，正式存储/tar 与生产代码字节不变；前一版 evidence_seal.json 保留为文档格式整理前的快照，最终交付使用 evidence_seal_v2.json 和 delivery_seal.json。处理已登记 development_issues，七份文档最终再检结果见 doc_check_v3；提交前重新核对全部暂存字节与空白格式。


## 26. 2026-11-17 CompileRepair CP2.3 审查与方案 r2.12（修改 AI：Claude）

### 26.1 任务、依据与范围

用户要求（2026-11-17）：Codex 已完成 CP2.3；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP3。起点 `compile-repair@76a2cc810`。审查对象：`rules/environment.py` 与 `pipeline.py` 的差异，`tests/test_pragma_bytes.py` 与新夹具，`cr_store_mando_v5` 与 `cli_probe_stores.tar.gz`（解包核对），CP2_REPORT 的 CP2.3 节、HANDOVER、DECISIONS、CHANGE_LOG §25、PROGRESS 与 development_issues.json。

修改：`PROMPTS.md`（r2.11 → r2.12）；新增 `artifacts/cp2_3_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节第 11 条补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 26.2 实施方式和重要选择

- 代码：逐行对照 `_expression_interval` 与冻结 `versioning.py` 第 7–23 行；读 `_pragma_spans` 与 `code_only` 的遮盖正则，确认遮盖等长、字符串先于注释匹配。
- 等价：自写脚本对 1,659 个文件（`source_code` 全部、`tests/fixtures`、审查边界用例）比较新实现与 CP2.3 之前的实现（git 中的原文件）及冻结函数。初次只传入两个类别目录，发现与 846 不符，改为整个 `source_code` 后覆盖 846/846。
- 存储：解包 v5，与 v3 逐个比较记录字段与图字节；解包 CLI 探针存储，核对状态、版本、标志、改动与 seal。
- 边界：为“任意输入”的目标另写 10 个合约，用 solc 与生产 Slither 判定哪些应被接受。两例与目标不符（见 26.3）。
- 处理选择：两个遗留都是一两行的修改，但用户要求问题在 CP3 之前解决，且第二项直接影响 CP3 的分类，所以单列 CP2.4。验收用 846 个输入上 make_plan 结果全同代替全量生产重跑：选版只由 make_plan 决定，其余代码不改。
- 测试：审查环境没有 pytest，从 Slither 0.8.0 环境以符号链接借用（不安装）。`test_environment.py` 20/20 通过；`test_pragma_bytes.py` 等 6 个模块在本机之外收集失败（读取 `/home/zhao/...`），以独立等价比较代替，并登记为既有的可移植性问题。

### 26.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 求值代码 | 与冻结第 7–23 行逐行相同 | 代码对照 |
| 与原实现 | 原实现能读取的 1,646 个文件：区间 1,646/1,646、补丁区间 1,648/1,648；MANDO 846/846 | verify_equivalence.json |
| 新实现多接受 | 5 个新语法、2 个 Latin-1、合约体内 pragma 夹具，及两个 solc 本身报错的审查用例 | 同上 |
| v5 | seal 4,228 一致；846/846 状态、原因、版本、SHA、设置、标志与 v3 相同；843/843 图字节相同 | 内联核对 |
| CLI 探针 | 9 个正例 success、无改动、seal 一致；`||` 负例 unrepaired、不调用编译器 | 同上 |
| pragma 内注释 | solc 0.8.0（块注释）与 0.5.17（行注释）rc 0，生产 Slither 成功；模块抛 Unsupported | edge_cases |
| 缺分号 | solc 0.5.17 报解析错误；模块信息与 `||` 相同 | 同上 |

未证明：用户环境（Python 3.10）中的测试结果之外，本审查没有运行 `test_pragma_bytes.py`；遗留两项在外部语料中的数量（CP3 统计）。

### 26.4 用户批准、原文差异与待确认设计

- Codex 处理正确：实现符合 4.4d 节；等价、回归与 CLI 验收完整；四个执行问题只涉及记录过程，保留了首次结果，没有放宽判据。
- 新发现：两个继承自冻结语义的同类遗留；测试可移植性（既有）。CP2.4 的修复只在冻结实现抛异常的输入上偏离冻结语义，不改变已定决策，不需要新的用户批准。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 26.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp2_3_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP3 不能开始。顺序为 Codex 执行 CP2.4 → Claude 审查 → CP3。本轮提交并 push 到 `compile-repair`。


## 27. 2026-11-17 CompileRepair CP2.4：读取 pragma 注释并区分未结束指令（修改 AI：Codex）

### 27.1 任务、依据与范围

用户明确要求执行更新 PROMPTS 的 CP2.4，先读 §4.1、通读全文，若有实质替代方案须先咨询并记录。已执行 git pull --ff-only origin compile-repair，返回 Already up to date，起始 7e32d85c6d02049fd606a9410759dbfb9f18fb7a；已读 r2.12 全文、HANDOVER §0–5、DECISIONS、本文 §25/26、docs/README、REPORT_TEMPLATE 和 cp2_3_review_v1 的 README/edge_cases。工作树保持 ge-sc-llm-compile；先建立 baseline 并复现，再改生产代码。

生产只改 rules/environment.py。测试新增 test_pragma_comments.py，既有 test_pragma_bytes.py 只为新注释夹具显式登记冻结异常边界；新增 fixtures/pragma_comments/{comment_inside,line_comment_inside,missing_semicolon}.sol。新证据全部在 artifacts/cp2_4_v1；驱动为 reproduce、launch_phase、run_checks、audit_results、audit_frozen、check_docs、write_documents，另保留测试专用的 environment_cp23.py 原代码快照。文档为 CP2_REPORT 追加 CP2.4、PROGRESS、本文、HANDOVER §0–5 更新及历史追加、DECISIONS 历史追加、新批次 README。完整证据清单见 delivery_inventory.json。CP0–CP2.3 旧产物、scripts、语料、PROMPTS、根交接和训练改变文档不改。

### 27.2 实施方式和重要选择

_pragma_spans 的定位和范围不变，只在分号前遇花括号/EOF 时用专门的 F: unterminated pragma directive。pragma_interval 将表达式切片的来源从 raw 改为 code_only(raw)，保持同一字节区间与 Latin-1 无损解码，再调用未修改的 _expression_interval。pragma_patches 仍截取原始字节；对两个新注释夹具也与 CP2.3 的完整 Patch 相同。生产两函数共 +5/-4 行（含 docstring），其他函数不改。

本轮等价对象是 CP2.3 实现，参照快照由起始工作树原文件复制，SHA256=f0d4f4b9274532c0b3760d67341f37dba7f2f81430d9aad091f42644483429e0，测试先校验再加载。846 输入按 cp0_v2 已封存 SHA 验证；版本表为 96 个可信版本，其中 92 个属于支持范围。MANDO 按既有 metadata known version 和 mando 配置，夹具按一般入口，升降序各比较完整 EnvironmentPlan 八字段。没有编译回归语料，符合 §4.4e 的明确验收安排。

新增测试同时覆盖注释中的伪分号/花括号、CRLF、Latin-1、原始补丁字节和无工具调用的拒绝路径。新注释夹具在冻结 interval 路径上会抛异常，本来就不属于“原实现可读取输入”；旧冻结测试的例外按这两份文件精确登记并断言旧异常，新测试证明修复行为，未删除旧比较。三个新夹具与审查字节相同，来源见 fixture_sources.json。

运行器由 CP2.3 证据驱动复制到新批次改写，reuse_sources.json 保存来源 SHA；未导入审查脚本。已成功的 CLI 只读审计、打包，不为写报告重复运行。Windows rg 的 UNC 读取报拒绝访问，改用 WSL Python/git 读取；无自动审批拒绝，无权限或代理设置变化。没有实现失败或验收失败；全部处理见 development_issues.json。

### 27.3 实测与数据结论

| 项目 | 结果 | 证据（cp2_4_v1） |
|---|---|---|
| 修改前复现 | 块/行注释 solc 0.8.0/0.5.17 rc0、D3；旧模块拒绝。缺分号为 solc 解析错误；旧 CLI 四例同报 unsupported pragma expression | reproduction.json、reproduction_invocations.jsonl |
| CP2.3 等价 | 每环境 846 MANDO + 35 可读取夹具，interval/Patch/完整 plan 全同；每环境升降序共 1,762 份 plan；两环境明细全同 | equivalence.json、test_evidence_*.json.gz |
| 排除旧失败输入 | 4 个明确列出：新注释两份、未结束 pragma、旧 union；其当前行为均单独验收 | equivalence.json、pytest 日志 |
| 生产 CLI | 两注释选 0.8.0 / 0.5.0，D3 成立，零源码改动；缺分号/union 两个错误区分，二者均无工具调用 | cli_acceptance.json |
| 调用与归档 | 新 CLI 2 次 solc + 2 次 Slither；归档 21 成员回读一致，SHA 见 CP2_REPORT | cli_acceptance_store.tar.gz |
| production | 622 passed / 6 skipped，80.43 秒 | pytest_production |
| mando | 181 passed / 447 skipped，21.12 秒 | pytest_mando |
| DFG v2 | 2653 passed / 9 既有 warnings，155.25 秒 | pytest_dfg |
| 代码 | 生产 14 文件，只改 environment.py 两函数，+5/-4 行 | code_change_summary.json |

结果均为首轮执行，具体命令、退出码、运行时间和临时目录保存在 pytest_*.json。上述 pragma 注释直接工具复现耗时与调用记录见 reproduction_invocation.json；完整生产验收复用测试所运行的 CLI。runtime.json 现场确认两个环境与固定 profile，未改变任何包或编译器。有限输入验收不等于所有未来源码已穷举；未重跑全量、6c 或训练，未重新声称历史图比较为本轮测量。

### 27.4 用户批准、原文差异与待确认设计

用户 2026-11-17 的 CP2.4 请求授权本轮 r2.12 既定修改，没有新的方案或下载授权。与冻结实现的有意差异正是 §4.4e 指定的两项：接受 pragma 内注释；未结束指令仍为 unsupported_version_constraints，但 error_first_line 单列。按要求写入 DECISIONS 历史，不修改既有决定表或 D3/D5/key5。没有计划外替代方案或判据变更，因而没有额外咨询请求。

只登记既有缺口：六个测试模块的本机绝对路径依赖，在 CI/迁移阶段处理；并集 pragma 和 Slither 无超时按 CP3 分类，当前不实现。D19 建议、D9/D10 待确认和 D12/D13 待定保持。

### 27.5 验收、资源、未执行事项与停止

PROMPTS §4.4e 的修改前复现、明确修复、原可读取输入的区间/补丁/全字段计划等价、两正两负 CLI、两个环境模块与 DFG 测试均通过。分层测试通过，生产文件数保持 14。最终完整性审计见 frozen_audit.json：保护旧跟踪/封存内容、环境、solc、DFG _code_refs、非目标函数及文档历史。doc_check 检查六份文档，初次通过后在本节补记，再复检最终字节并保存哈希；执行结果以 doc_check_v*_invocation.json 为准。

文档追加前字节数：CP2_REPORT 55034、PROGRESS 41137、CHANGE_LOG 189391；HANDOVER、DECISIONS 与新 README 全文检查。实际测试命令为各环境 python -B -m pytest -q -ra -x -p no:cacheprovider，目标分别为 compile_repair/tests、scripts/DFG/dfg_v2/tests，并使用独立 --basetemp；完整命令见 pytest_*.json。所有运行在 CPU，OMP/MKL=2，费用 0，峰值未测。

未安装、下载、LLM 调用、HGT 训练或读写 GPU 锁；未改变全局 solc、网络配置或旧产物。846 全量编译未运行，按文档以 make_plan 全同验收；6c 未重放；CP3 未开始。全部记录和检查通过后本地提交，提交信息以 CP2.4 开头，提交号见 git log，不自动 push。停止于 CP2.4 本机验收完成、等待独立审查。

最终检查补记（2026-11-17，修改 AI：Codex）：doc_check v1 六份文档全部 passed=True；本补记后的最终六份文档复检和哈希记录在 doc_check_v2.jsonl、doc_check_v2_invocation.json。frozen_audit 全部通过：28,675 个受保护跟踪文件（模块外 27,845、旧产物 762）、25,828 个旧封存成员、96 个 solc 文件、两环境元数据集合与内容（production 145、mando 118）、354 个 DFG _code_refs 均未变；environment.py 除两目标函数外的 13 个函数 AST 不变，生产文件仍 14。新 CLI seal 的实现指纹与当前代码一致，旧文档历史前缀保持。git diff --check 通过；按 delivery_inventory 精确暂存后核对暂存字节与格式再本地提交，不 push。


## 28. 2026-11-17 CompileRepair CP2.4 审查与方案 r2.13（修改 AI：Claude）

### 28.1 任务、依据与范围

用户要求（2026-11-17）：Codex 已完成 CP2.4；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP3。起点 `compile-repair@9fdc96e13`。审查对象：`rules/environment.py` 的差异，`tests/test_pragma_comments.py` 与新夹具，`cli_acceptance_store.tar.gz`（解包核对），`environment_cp23.py` 参照副本，CP2_REPORT 的 CP2.4 节、HANDOVER、DECISIONS、CHANGE_LOG §27、PROGRESS 与 development_issues.json；另通读 4.5 节 CP3 提示，核对其与已有实测是否一致。

修改：`PROMPTS.md`（r2.12 → r2.13）；新增 `artifacts/cp2_4_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节第 12 条补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 28.2 实施方式和重要选择

- 代码：读差异，确认只有两处修改；用 cmp 确认 Codex 的 CP2.3 参照副本与 git 中 `76a2cc810` 的文件逐字节相同。
- 等价：自写脚本比较新实现与 CP2.3 实现：1,663 个文件的区间（含异常信息）与补丁区间；MANDO 846 个输入在升序、降序下的完整 make_plan（92 个官方支持版本，known version 取自 v5 输入记录，regression=mando）。
- 存储：解包 CLI 验收存储，核对归档与 seal 的 SHA256 前缀、seal、各单元结果与原因、调用记录。
- 边界：再写三个缺分号的合约（后接 import、pragma、library），与 solc 0.5.17 对照。后接 import 或 pragma 时 solc 本身把两行读成一条 pragma，报版本不符；模块与 solc 读法一致，所以不改代码，只在 CP3 分类中单列。
- CP3 提示：通读后发现第 2 节要求“standard-json 输入组装”，与 r2.11 的实测（0.4.12 内部错误，0.4.12/0.4.17 不给位置）矛盾，且生产 Slither 经 crytic-compile 的命令行路径编译。查看 crytic-compile 0.4.2 的 solc 平台，确认支持 `solc_working_dir`、`solc_remaps`、`solc_args`，改为命令行路径，同一组参数同时用于 solc 与 Slither；要求先用三文件夹具在 4 个版本上确认，某版本不支持某参数时停下报告。3.2 节表第 2 行与 3.10 节的文件说明同步修改。

### 28.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 参照副本 | 与 `76a2cc810` 的 environment.py 逐字节相同 | cmp |
| 区间与异常信息 | CP2.3 能读取的 1,656 个文件全同；补丁区间 1,661/1,661 | verify_cp24.json |
| 有意的不同 | 两份块注释、两份行注释现在接受；两份缺分号信息改为 unterminated | 同上 |
| make_plan | MANDO 846 个输入升降序 1,692/1,692 全同 | 同上 |
| CLI 验收存储 | 归档 `ff5bc10faded5855…`、seal `802cdd364105afcf…`，20 个文件 0 不一致；4 条调用都属于两个成功输入 | 内联核对 |
| 测试 | 34 通过；1 个失败为 `production_required()` 读取 `/home/zhao/...` | 审查环境 pytest |
| 缺分号后接指令 | 后接 import、pragma：模块 unsupported pragma expression，solc 报版本不符；后接 library：模块 unterminated，solc 报缺分号 | edge_cases/ |

未证明：多文件命令行路径在 0.4.12–0.8.x 上的参数兼容性（CP3 用夹具确认）；外部语料中各类的数量（CP3 统计）。

### 28.4 用户批准、原文差异与待确认设计

- Codex 处理正确：实现与 4.4e 节一致；按规定以 make_plan 全同代替全量重跑；冻结等价测试只对两个注释夹具显式例外，其余保留；执行问题只涉及只读检查方式。
- 方案修正：CP3 第 2 节的编译路径（由 Claude 早先写入的 standard JSON 改为命令行）。这是方案内部不一致的修正，不改变已定决策。
- CP3 第 1 节的语料获取需要用户书面授权；Codex 写出授权请求后停下。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 28.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp2_4_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP2 系列结束，可以开始 CP3。本轮提交并 push 到 `compile-repair`。


## 29. 2026-11-17 CompileRepair CP3 前置核查：停在资料获取授权（修改 AI：Codex）

### 29.1 任务、依据与范围

用户最新要求执行 CP3，并在替代方案或设计调整前咨询。起点 compile-repair@0d39c3546dbb8d456ef7c2fd5534143dcef92c94，git pull --ff-only origin compile-repair 返回 Already up to date；先读 §4.1，再核对 PROMPTS r2.13 更新、当前 §4.5 全节、HANDOVER §0–5、DECISIONS、最新变更及 cp2_4_review_v1/README、cr_pre_v2/README、记录模板。当前任务明确是 CP3；先前 CP3.4 的歧义已由用户新指令消除，没有据旧编号实施。

本轮只做 CP3 获取前准备。新增 CP3_REPORT.md 和 artifacts/cp3_preflight_v1；旧文档仅追加本节、PROGRESS 的 CP3 节、HANDOVER §6，并更新 HANDOVER §0–5 的当前状态。批次包括授权请求、元数据/本地可用性证据、baseline/runtime、run_checks 与 verify_preflight、问题记录、测试/审计收据、README、封存和交付清单；完整逐文件清单与 SHA256 以 delivery_inventory.json 为准。未修改生产实现、测试、PROMPTS、DECISIONS、CP0–CP2.4 产物、CP2_REPORT、冻结 scripts、原始语料或根目录两份记录。

### 29.2 实施方式和重要选择

- 先核对仓库、约定的 /home/zhao/SmartContract/corpora 与语料目录、/tmp 与用户缓存一级目录。未找到所需官方文档或三套外部语料，也未找到 CP3 获取授权；检查范围和未命中记录在 local_availability.json，不推断整台机器都没有副本。
- 用 GitHub connector 只读仓库身份、Git tree、tag/ref 元数据，生成具体版本、路径和大小请求；没有读取源码 blob 或文档正文。DAppSCAN 整仓 recursive tree 被截断，改查已列出的 contracts 子树，确认 truncated=false 后再统计。未用截断结果当作完整清单。
- 官方 ethereum/solidity API 返回 Moved Permanently。核对 repository id=40892817 对应 argotorg/solidity，记录同一仓库迁移而不是替换非官方来源；十份文档均锁定标签解析出的完整 commit 和 blob SHA1。正文获取及 SHA256 留待授权后。
- 一次调试输出过长，最初特殊模式汇总还包含普通可执行 blob；未写入正式证据。改为只统计 mode=120000 的符号链接、仅输出聚合信息；项目统计按 contracts 第一级目录，结果 608。完整处理见 development_issues.json。
- 请求保存为 authorization_request.json，status=pending_user_authorization；不创建伪批准的 authorization.json。语料限定指定子目录并放仓库外；SOChecker 只以 input 字段为后续分类输入，897 条及四文件一致性先核对，发现不同不自行合并或去重。
- 复用 cp2_4_v1/run_checks.py 的检查驱动，仅改标题和临时目录前缀；来源 SHA256 在 runner_provenance.json。verify_preflight.py 只负责本批次文档与完整性，不是生产功能模块，没有复制冻结函数或改变分层。

### 29.3 实测与数据结论

| 项目 | 本轮结果 | 来源 |
|---|---|---|
| DAppSCAN 获取范围 | 21,495 个 blob、109,776,516 字节；608 个项目目录、21,457 个 .sol | remote_metadata.json 的完整 contracts 子树 |
| SOChecker 获取范围 | 4 个 JSON、3,762,624 字节；input 内容计数未核验 | 同上，固定提交 evaluation/RQ1 |
| Trace 获取范围 | 8,112 个 blob、122,296,616 字节；on-chain 5,000 / repo-level 83 项目 3,092 .sol / CVEs 15 | 同上，datasets 子树 |
| 三语料合计 | 235,835,756 字节，约 224.91 MiB | authorization_request.json |
| 官方文档 | 10 份、188,817 字节，约 184.39 KiB | 同上的 docs 列表 |
| production 模块测试 | 622 passed、6 skipped，驱动 71.10 秒 | pytest_production.json 与日志 |
| mando 模块测试 | 181 passed、447 skipped，驱动 20.86 秒 | pytest_mando.json 与日志 |
| 冻结 DFG v2 | 2653 passed、9 既有 warnings，驱动 154.89 秒 | pytest_dfg.json 与日志 |

体量是 Git tree 未压缩 blob 字节数，不是实测网络流量，不含 Git/传输/文件系统开销。目录数量与 cr_pre_v2 对应结构数字一致，但尚未验证源码 SHA256、import、pragma、SOChecker input 数量或内容；不能写成已完成语料核验。所有测试都是已有测试，不能写成 CP3 taxonomy、导入闭包、四版本三文件探针或语料分类通过。这些 CP3 事项均未实现/未运行。

起始基线包含 28,753 个跟踪文件 SHA256、354 个 DFG code refs、14 个生产文件、96 个编译器文件；旧 seal 索引引用 25,828 个文件，见 baseline.json。runtime.json 现场核对 production Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2，mando Python 3.7.12 / Slither 0.8.0 / crytic-compile 0.2.4，其他包版本见收据。

### 29.4 用户批准、原文差异与待确认设计

最新用户要求授权执行 CP3 本身，但 §4.1、§4.5 明确把新文档/语料下载单列为用户批准后才能执行；历史 solc 与环境授权不覆盖本清单。本轮没有收到 CP3 获取批准，没有产生新已定决策，因此 DECISIONS 不变。

待用户批准的具体范围：十份官方文档、三套固定提交的指定目录、零美元费用上限、本地研究与只读编译分类用途；逐条来源、保存路径、版本与请求说明在 authorization_request.json/README.md。三个固定提交根目录元数据未列出 LICENSE，这一事实不等于所有嵌入源码都无单独许可；依原文由用户决定使用范围。

未提出或实施替代方案，也没有降低验收标准。已知 || pragma 与 Slither 进程内无超时仍按 §4.5 后续统计/建议处理，本轮未改实现。CP3 批次时长上限尚未由用户指定；若需上限或抽样，先在资料与规定探针可用后给出估时依据，不擅自指定已批准时长。需要获取授权不是自动审批拒绝，也不是 skill 追加的限制，而是 PROMPTS 明确条款。

### 29.5 验收、资源、未执行事项与停止

三组既有测试各首次运行 rc0，完整命令见 pytest_*.json：对应环境 python -B -m pytest -q -ra -x -p no:cacheprovider，模块目标 compile_repair/tests，冻结目标 scripts/DFG/dfg_v2/tests，每轮使用新的 /tmp basetemp；无失败重试。跳过原因是原有 production/regression/Python 版本边界，详见 test_acceptance.json 与日志。

提交前检查五份 UTF-8 文档：新 CP3_REPORT、批次 README、HANDOVER 全文，CHANGE_LOG 与 PROGRESS 仅从 baseline 保存的追加前字节数起检查。并核对跟踪文件/旧封存产物、两环境元数据、solc、_code_refs、生产文件数和文档历史前缀。文档检查和完整性实际结果在本节末尾补记；只有全部通过才提交，不将尚未执行检查写成通过。

全部 CPU，外部 LLM API 0 次、费用 0 美元。网络操作仅同步已授权分支与只读仓库元数据；未下载语料或文档正文、安装/升级包、运行 CP3 分类、修改全局 solc、启动 HGT、操作 GPU 锁或 push。停止点是 §4.5 第 0、1 节的获取授权；CP3 未完成，不能进入 CP4。本地提交信息以 CP3 开头，实际提交号由 git log 和最终答复给出。


本轮终审补记：doc_check v1 对五份文档全部 passed=True、rc0，详见 doc_check_v1_invocation.json；冻结审计 passed=True。28,750 个保护跟踪文件（其中模块外 27,845、旧产物 829）与 25,828 个旧封存文件均 0 变化，354 个 code refs、96 个编译器文件、两环境 145/118 份元数据与 14 个生产文件全同，三份历史记录前缀保留，详见 frozen_audit.json。本补记后以 doc_check v2 复查最终五份文档；最终结果和文档 SHA256 见 doc_check_v2_invocation.json，未通过不得提交。精确交付清单与 seal 完成后只提交本地 CP3 前置检查点，获取授权仍待用户决定。


## 30. 2026-11-17 CompileRepair CP3 续：授权获取完成，SOChecker 子集差异后停止（修改 AI：Codex）

### 30.1 任务、依据与范围

承接用户对已提交 88b499e7 的资料请求的批准，继续 PROMPTS r2.13 §4.5 CP3；原话“批准全部资料，仅本地研究使用（推荐）”，日期2026-11-17。共享上下文、方案全文/完整更新差异、HANDOVER §0–5、DECISIONS、§29及CP2.4审查在前置阶段已读，本轮复核 CP3、分层、D3/D6/D7 和官方文档。起点 compile-repair@88b499e714883066b3bc1379f42a5a89ce8ba1d6；前置 pull --ff-only 已同步，本轮为同一任务的授权续做。

新增 artifacts/cp3_v1 的授权/基线、获取与核验驱动、逐文件清单、文档初表、结构核对、前提探针、待确认请求和审计收据；新增三份 tests/fixtures/cp3_project 手写合约。追加 CP3_REPORT、PROGRESS、本日志；更新 HANDOVER §0–5并追加历史；DECISIONS记录授权和待确认差异。完整文件清单和SHA256见 delivery_inventory.json。生产代码及14个生产文件、既有测试、旧批次、冻结scripts、原作者代码、原始输入、根目录两份记录均不改；不创建通用project.py或分类器。

### 30.2 实施方式和重要选择

先写 authorization.json，再获取10份官方文档和三个固定提交的指定子树；使用已有代理与Git部分获取/sparse-checkout，不下载子模块、不执行语料代码、不补依赖。每个文件核对Git blob身份、大小及SHA256，清单压缩保存，外部源码保存在仓库外，授权范围与费用上限不扩张。旧请求和前置提交不改，授权来源与请求SHA绑定。

taxonomy.json先于语料内容统计建立，记录29类和四次breaking changes共125条，所有条目有来源行与候选修复/D3/D7依据；缺少实测的版本范围保持为空。Warning、运行语义变化、接口变化单独说明性质，避免当作编译错误计数。覆盖检查首次发现0.6文档的两个嵌套fallback/receive条目未列，补齐后覆盖全部条目；这是初表生成时的校验修正，没有改变已发布分类或验收标准。

按原文先运行三文件四版本前提探针，relative target、cwd、remapping和--allow-paths .同时传给solc与crytic-compile，Slither用production。结构核对独立复现cr_pre_v2的regex文本口径，不导入冻结证据脚本，也不用于CP3新版本区间选择。读取core/types.py路径失误按实际core/model.py纠正；默认WSL调用受沙箱限制改用既有授权WSL方式，未改系统网络；过长显示改为JSON字段核对，正式结论不依赖截断文本。详见development_issues.json。

### 30.3 实测与数据结论

10份文档188,817字节、29,611语料文件235,835,756字节均身份/字节/哈希通过。DAppSCAN 21,495文件（21,457 .sol）/109,776,516字节；SOChecker4文件/3,762,624字节；Trace8,112文件（8,107 .sol）/122,296,616字节。资料清单见document_manifest与acquisition/*/manifest.jsonl.gz；字节是源文件大小，不是网络流量。

分类初表29类、125条变化分别59/23/22/21；初始SHA为7096c70be45debbbd671919674ee2afd63dc59e3bf08c969ed977353299832bb。三文件探针在0.4.12、0.4.24、0.5.17、0.8.38均solc rc0、Slither构造和D3(a/b)通过，映射覆盖三文件且输入未改（4/4），见project_probe_acceptance。未据此宣称闭包生产功能已经实现。

DAppSCAN的summary、首版本文本系列、import前25项和608项目明细与旧JSON全同：473项目含导入、405项目有静态未解析导入、相对找到38,122、缺失1,094。Trace的5,000/83项目与3,092/15全同。SOChecker三份897条完全同序、历史子串计数656；ours+GPT.json只有846条、子串计数621，是严格子集，缺51条、无新增或重复input。structure_acceptance总passed=false，差异SHA清单和建议见structure_review_request；这是停止条件，未放宽标准或重试下载。

### 30.4 用户批准、原文差异与待确认设计

当前授权允许十份文档与三指定目录的本地研究获取，零美元；无安装、库下载或LLM授权扩展。三仓根目录无LICENSE的事实已在原请求说明，用户批准限定用途。authorization.json SHA256为f42f045ba9c235674cc3fea3a4b42a7d28945daaf56b1b43ba9ae8aef869a87a；原请求SHA256为1862b4aa6deafca0267ef168b4b358738f4d1635fcc983fc5bc2925a09433808。

获批请求after_approval规定内容核验计数不符时保留并停止，PROMPTS §4.5.1要求不一致时报告，故暂停后续实施。具体待确认建议：仍采用原定ours.json的897条唯一输入，将ours+GPT的846条登记为附属子集，只作来源核对，不合并、不去重、不补数据；接受这项一致性假设差异后按原计划继续。建议尚未执行，原下载批准仍有效；没有更改D3/D5/D7、版本范围、编译参数或修复方案。DECISIONS记录此待确认事项，其他已定/待定决定保持。

### 30.5 验收、资源、未执行事项与停止

新批次的run_checks.py沿用已提交前置驱动，仅改说明和独立临时目录前缀；source SHA在runner_provenance。命令为对应环境python -B -m pytest -q -ra -x -p no:cacheprovider，目标compile_repair/tests或scripts/DFG/dfg_v2/tests，日志、命令、rc和计时写pytest_*。doc_check对全部新文档和追加内容执行；结果与冻结审计在本节末尾终审补记。检查点提交前必须通过这些完整性检查，但structure mismatch不会被改成通过。

当前停在语料内容核验差异，未运行生产分类器/项目闭包实现、语料编译与类别统计、0.6/0.7格式探针、tuple-call复核、重复声明/许可证/pragma与AST-only/codegen前提、CP4最终算子验收。仅已有探针和初表，CP3未完成；||和Slither无超时未修复，未自行抽样或设定用户时长上限。资源为CPU、费用0，无安装/升级、额外获取、LLM、6c重放、HGT训练、GPU锁、全局solc变更或push。完成记录与检查后只本地提交，续做使用新批次。


终审补记（2026-11-17，修改 AI：Codex）：本轮 production 622 passed/6 skipped（驱动79.93秒）、mando 181 passed/447 skipped（20.26秒）、DFG v2 2653 passed/9既有warnings（152.65秒），各执行一次且rc=0，见test_acceptance与pytest_*。首次汇总收据的数字正则转义错误只影响日志解析，改为读取已有末行的词项后正确汇总，未重跑测试、未改验收判据，详见development_issues。

六份doc_check v1全部通过。frozen_audit通过：28,779个保护跟踪文件、25,828个旧封存文件无变化；354个code refs、96个编译器文件、production/mando的145/118份环境元数据、14个生产文件均保持；29,611语料文件与10份文档复核无变化。五份既有文档的历史字节段保持。补记后的doc_check v2记录最终文档SHA256，通过后按delivery_inventory精确本地提交；结构核验差异仍未解决，CP3仍未完成，不将该项改记为通过。


交付补记（2026-11-17，修改 AI：Codex）：暂存后的 git diff --cached --check 报告三份 Git init 原始 stderr 的提示行尾空格，以及 solc 0.8.38 原始 stderr 的末尾空行。为保持取证原字节，未修改四份日志或已封存 cp3_v1；仅将这四个精确日志路径排除后，其余全部文件的同一空白检查通过。该处理不排除代码、文档或任何CP3验收项；SOChecker的结构差异仍为未通过。

另建 artifacts/cp3_delivery_v1 保存原始报错、四日志SHA、检查命令和上次doc_check对应的文档快照。最终文档检查与提交清单改以该交付批次的 doc_check_final_invocation.json、delivery_inventory.json 为准；cp3_v1/evidence_seal.json 原样保留。没有重跑编译或测试，也没有改变生产实现、授权范围或待确认建议；本地检查点提交后仍等待对846/897子集差异的处理确认。


交付终检补记（修改 AI：Codex）：七份 doc_check_delivery_v1 全部通过；本条补记后再次检查的最终文档哈希见 cp3_delivery_v1/doc_check_final_invocation.json。四份原始工具日志按精确路径保留并豁免空白检查，其余文件检查通过；编译验收和 SOChecker 待确认状态均未改变。

## 31. 2026-11-17 CompileRepair CP3 续做：项目管线与原生调用绑定缺口（修改 AI：Codex）

### 31.1 任务、依据与范围

本轮是用户批准结构差异后的同一 CP3 任务继续，分支 compile-repair，起点 dc6c5fb44041e1023daef1bfd7d9760f534c7f0a。遵循已读 PROMPTS r2.13 全文、§4.1/§4.5、HANDOVER 0–5、DECISIONS、既有 CHANGE_LOG 与 CP3 授权清单；此前任务已 pull，本轮无重复拉取。旧 CP0–CP2.4 和 cp3_preflight_v1/cp3_v1/cp3_delivery_v1 保持只读。

新增生产文件 toolchain/project.py、evaluation/report.py；修改 toolchain/solc.py、toolchain/slither.py、pipeline.py、cli.py、evaluation/survey.py；测试新增 test_diagnostics.py、test_project.py、test_cp3_report.py 与 cp3_diagnostics/cp3_alias/cp3_alias_calls，调整 test_pipeline.py、test_cp1_1.py、test_pragma_comments.py。文档更新 CP3_REPORT、PROGRESS、HANDOVER、DECISIONS 和本节；证据全部在新批次 cp3_continue_v1。旧规则、core、scripts、原作者代码、根交接/训练文件和原语料未修改。

### 31.2 实施方式和重要选择

stderr 分类使用消息与实际位置，standard JSON 只用于类型/errorCode辅助探针。项目闭包只读取批准项目内的文件，不执行构建脚本、不补库、不用 basename 候选自动替换；CLI 与 Slither 共用相对入口、cwd、remaps、allow-paths。统一 repair_unit 复用原 make_plan、ordered_candidates、settings_retry、apply_patches/verify_provenance；没有复制或修改冻结版本策略。项目文件身份经批准后加入外层命名空间，单文件行为通过旧测试验证。

片段语言检测只作词法证据判断，统计按单元与类别去重，保留零观察类别和 other 模板。源码、批量图和原始stderr留仓库外；Git只收身份和统计。DAppSCAN项目口径保持608个根，不能用更深层682个子目录替代。

开发问题包括：类型消息中的expected type误匹配parser，修为行首模式；导入名改为UTF-8解码；手写Missing测试误引用Absent已修正；旧搬迁测试两处14模块假设更新为16且核对完整清单；旧pragma测试只增加五个已知不支持负向夹具，846输入与可读夹具的精确等价标准不变。一次工具脚本字符串引用失败没有执行写入，修正后运行；旧报告路径误写docs/后按实际根路径读取。失败日志均保留。新的原生类型错绑没有自行修复或转成跳过。

### 31.3 实测与数据结论

taxonomy_verified保留29类和125条breaking changes，记录30个观察模板。诊断探针548次combined-json、84次standard JSON、6组tuple前提；92版格式切换0.6.0，重复相同SPDX MIT从0.8.8拒绝，重复相同Solidity pragma均接受。codegen探针12次compiler/2次Slither，0.8.38的via-ir+optimizer通过所测Stack too deep夹具D3；未加入生产设置重试。

输入清单31,307条，SOChecker236条无声明证据单列，31,071条进入完整序列；29,611取得文件的SHA核验完成。首段120条47.744秒正常结束；加权估计全量2.415小时，未抽样。后段752条后受控中断，rc=-2、304.657秒；另cp3_30208有9条记录调用。872完整单元临时结果为599旧D3成功/273失败、11,900次solc/599次Slither，冻结parse失败而新读取成功92；逐类数量、比例、SHA示例及7个other模板见partial_failure_summary。中断现场200,545,035字节已有哈希清单，不能当正常封存或最终统计。

alias_call_probe中compiler AST的a/b分别指向A.sol id37、B.sol id48，Slither0.11.6原生类型对象和调用都落在A.sol；原D3(a/b)同时通过。证据不依赖本模块图序列化，说明现有D3不能保证这类调用目标正确。未证明所有同名合约均出错，也未用语料频率决定是否处理。

### 31.4 用户批准、原文差异与待确认设计

用户2026-11-17原话“同意，继续使用原定897条（推荐）”，对应authorization.json中保留的精确原文（含空格）；只接受附属846严格子集差异，不合并或重下载。随后原话“批准项目图使用文件名 + key5（推荐）”，对应project_identity_authorization；这是有证据、有授权的D4项目身份扩展，已实施并记录。

待确认仅为alias_binding_review_request：增加项目AST/Slither类型绑定接受检查，保留D3事实，错绑或无法验证拒绝可用图输出、记工具限制；不改Slither安装或合法源码。该条件超出现有D3及文件名+key5批准范围，已按§4.1询问并停止。||并集、Slither子进程超时、codegen设置候选和tuple语义等价改写留后续CP，均未实现。

### 31.5 验收、资源、未执行事项与停止

生产完整套件v4为714 passed/6 skipped，mando268 passed/452 skipped，DFG2653 passed/9既有warnings；驱动耗时分别69.246、22.342、164.070秒，命令与rc见pytest收据。定向v2为110passed；随后项目补充验收24passed/1failed，真实类型错绑仍未通过，不能将旧完整测试通过当作当前全部验收通过。doc_check和冻结审计在本节后续补记记录实际结果。

全量已停止，无自动重试。最终全量分类和CP3结束验收未完成。当前新增测试未通过，不满足PROMPTS“全部通过后提交”，本批次暂不提交、未push。没有下载、安装、升级、LLM、HGT训练、GPU锁或全局solc变更，CPU、0美元。若用户批准新检查，应先完成并验收，再用新批次处理受影响项目与中断/未执行单元；旧现场只读保留。


交付检查补记（2026-11-17，修改 AI：Codex）：六份 doc_check_v1 全部通过；frozen_audit 检查28,908份保护跟踪文件、25,828份旧封存文件、354项code refs、96份编译器文件、production/mando的145/118份环境元数据、29,611份语料和10份文档，均未变化。生产文件16个，历史文档字节段保留。tracked git diff --check通过，新增代码/文档无空白问题；仅322份逐一列明且SHA固定的原始工具输出保留其原空白，见whitespace_review，不豁免代码或验收项。本条追加后的最终doc_check收据为doc_check_final_invocation.json。上述记录和范围检查不代表新增绑定测试通过；24passed/1failed与待确认状态保持，本批次未提交、未push。


测量边界补记（修改 AI：Codex）：另有三次交互式诊断检查和一次初始项目 smoke check 未保留完整逐调用耗时/输出哈希；exploratory_observations.json 明确以 null 标示缺项，不混入正式548/84诊断矩阵及前提验收计数。development_issues.json登记了全部实质问题与解决或停止方法。新增绑定检查仍待确认，失败测试状态未变。

## 32. 2026-11-17 CompileRepair CP3 续：项目绑定检查与全量恢复（修改 AI：Codex）

### 32.1 任务、依据与范围

收到用户“批准项目图绑定检查（推荐）”后继续同一CP3任务。PROMPTS r2.13 SHA保持f1505a4c623dc91174dfd61910870f94d73acf3e45e3c4364e81cbacbad92c83；分支compile-repair、HEAD dc6c5fb4。获批请求见旧alias_binding_review_request，新授权、基线与所有本次证据写cp3_binding_v1。旧cp3_continue_v1的seal与762成员全部核对，旧现场不修改。没有重新pull或push。

### 32.2 实施方式、问题与处理

生产只在slither.py新增直接合约类型检查，并调整pipeline.py成功条件和evaluation/report.py归类。按每个编译单元的AST引用ID找ContractDefinition，再用文件和字节起点核对原生类型，不按名称猜测。覆盖状态变量、参数、返回值、局部变量、结构字段、事件与自定义错误参数；数组/映射/表达式/函数类型内部不属于本次直接类型检查。旧/新AST形态均支持；缺失、歧义或无法核验会拒绝。保留D3(a/b)事实，项目graph_usable另行判定，拒绝时不保存成功图；继续既有候选版本，不改策略或安装包。

旧失败测试按获批门槛改成精确拒绝断言：b应指B.sol而原生为A.sol，D3仍true但没有graph.json。新增四版本正例核对七条声明及A/B两条调用；合成新旧AST缺失原生变量/AST用例验证拒绝。检查函数型参数时发现其内部声明不属于直接变量容器，遍历显式止于FunctionTypeName，避免扩大检查范围；图节点及原序号不去重。一次只读记录路径误写docs外已按实际路径纠正，没有文件改动；Windows直接UNC读取被权限层拒绝后沿用已授权WSL访问。

### 32.3 实测与续跑口径

手写合法项目0.4.12与0.8.38均solc rc0、原生对象位置可核对，完整记录在binding_api_inspection。定向32passed，完整production723passed/6skipped（82.98秒pytest；83.296秒包装器）。mando及DFG检查进行中，最终结果后补。

continuation_plan逐文件核对旧两段4,716份保存证据，872条完成记录与原序列前缀全同。343条项目全部新批次重验；529条单文件按原SHA复用，单文件成功体AST未改。余下30,199条从原第873条cp3_30208继续，原中断的9次编译单列保留，不伪造原段正常完成。

### 32.4 授权、方案差异与限制

本轮调整就是用户刚批准的额外项目图接受检查，无其他替代方案。D3不改写为false来掩盖错绑，工具限制不交代理改写合法源码。检查只是已知直接类型绑定的有限验证，不保证所有表达式、IR或嵌套类型语义。旧文件名+key5授权保持；源码、Slither安装与全局solc保持不动。

### 32.5 验收、资源与当前状态

全量完成统计、D6/CP4结论与最终保护审计待续跑后记录。本轮截至本段无下载、安装、LLM、HGT、GPU锁、全局solc或网络设置更改，费用0美元。测试/运行使用已批准production，兼容性/DFG用mando；CPU参数与原批次相同。全部强制记录与验收通过后本地提交，不自动push。


32.3/32.5 阶段状态补记（修改 AI：Codex）：三套完整v1回归均已完成，production723passed/6skipped，mando271/458，DFG2653passed/9既有warnings，退出码均0；包装器耗时分别83.296、21.607、153.925秒，pytest_*_v1.json为准。HANDOVER当前表的“DFG进行中”同步为已完成，旧历史不改。

343项目复验230成功/113未修复，outcome/选版/settings/flags保持，见revalidation_acceptance。既有MANDO846观察为843成功/3原有Slither侧失败，准确集合核对旧CP2_REPORT，见mando_subset_acceptance，未单独重跑。四组语料完成的阶段记录见completed_corpora_checkpoint_v1；DAppSCAN和Trace on-chain仍运行，这不代表整体CP3已完成。

runtime_estimate_v2在7,703条有效观察时估计剩余2.388小时，只作运行说明，不设时限、不抽样、不改变原序列。schedule_verification核对新旧完整顺序hash及30,199条后缀完全相同。最终汇总、规定的任务结束无缓存检查、doc_check、保护审计与提交尚未执行。


32.3/32.5 全量补记（修改 AI：Codex）：完整清单31,307条，其中SOChecker236条无Solidity声明证据单列；进入固定完整序列31,071条，成功21150、剩余失败9921。529个单文件观察复用，343个旧项目以新批次结果替换，再完成30,199条续跑；每单元只计一次，无抽样。

有效结果对应solc调用115771次、Slither调用21298次；原中断9次编译与被替换的旧项目335次编译/230次Slither不计入有效结果调用数，原始记录保留。旧整文件parse失败而新pragma读取成功1012个单元；unsupported_disjunction为1个。项目Slither调用15771次，直接合约类型绑定核对34973条；D3为true但绑定检查拒绝的调用0次。

343项目复验230成功/113未修复，状态、选版、设置与flags全部与原记录相同，230个成功项目均通过新增绑定门槛。三套完整回归通过：production723/6、mando271/458、DFG2653/9既有warnings；定向32通过。单文件导入缺字段仅在最终只读统计补计，12个已保存实例核对通过；生产/原结果未改。复核脚本一度把slither=null当dict，已修正读法，失败的启动前置检查没有创建运行；无实验重试，见development_issues。

D6与CP4逐类清单完成，29类/125变化保留；最终统计与SHA来源在failure_summary、result_provenance、d6_cp4_final。强制doc_check与frozen_audit待随后补记，不提前写为通过；本地提交须在全部记录与检查通过后，未push。


完整分类文档记录时间：2026-11-18T00:18:10-05:00（America/New_York，EST；依据本次脚本系统时间）。授权日期仍为2026-11-17。


最终复核暂停（2026-11-18，修改 AI：Codex）：完整观测统计已生成，但CP3最终验收尚未通过。11个DAppSCAN项目入口以连字符开头，project_command与slither_arguments原样传入入口；315次solc调用将路径当选项拒绝。该问题属于参数组装，不属于源码损坏，原9,921个剩余失败包含这11项，当前统计仅为修正前观察。具体清单、命令与SHA、限定./前缀方案及新批次11单元重验请求见leading_dash_review_request.json；已向用户询问，尚未修改参数或重跑。当前批次、所有旧产物及其统计保持，修正后应另建批次、仅替换这11条观察，不把现有数字写成最终接受结果。

三套最终无缓存回归均通过，但它们未覆盖本次发现的连字符入口问题，不能据此放行CP3。读取完成收据的自动审批一度超时，按工具允许仅重试一次只读检查后成功；随后WSL新命令暂报Wsl/Service/0x8007274c，使用只读UNC检查并在最小连接探测恢复后继续，没有重启WSL或修改网络。诊断提取首次漏读reason字段，随后只遍历续跑批次得10项；补入项目复验批次后确认共11项。这些是只读提取修正，没有重试编译。


#### 32.5.1 完整观测检查与待确认暂停（2026-11-18，修改 AI：Codex）


本批次收尾检查（修改 AI：Codex；时间：2026-11-18T00:21:18-05:00，America/New_York/EST）：完整31,071单元观察与两个新运行seal全部核验，复验批次2,385文件、续跑批次193,136文件，运行实现SHA与当前16模块一致。三套最终无缓存回归均通过：production723passed/6skipped（88.344秒）、mando271passed/458skipped（21.392秒）、DFG2653passed/9既有warnings（164.618秒），数据见pytest_*_final_v1.json。定向32passed沿用本轮既有收据，没有再次重跑。

doc_check_v1检查7份正文，全部UTF-8/CJK通过；本次补记完成后以doc_check_v2.json复查最终字节。frozen_audit通过：28,908份受保护跟踪文件、25,828份旧封存文件、753份上一检查点受保护成员、29,611份外部语料文件和10份资料无变化；96个solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither类型解析器SHA保持。文档历史前缀全部保留。这些是分别定义的检查范围，可能重叠，不能相加作为独立文件总数。

全量中34,973条直接合约类型声明被核对；D3为true但新增绑定检查拒绝的调用为0。139次未获绑定认证的项目调用全部属于Slither未构造成功，不能表述为139次错绑；手写alias用例独立证明已知错绑会拒绝图。原D3事实、源码和安装包均保持。

CP3最终验收仍暂停：11个连字符入口被误当solc选项（315次调用），修正请求见leading_dash_review_request.json，尚未批准、未修改project.py、未重验。当前统计为修正前完整观察，不能宣称CP3已完成。按PROMPTS的中途停止记录要求整理本地检查点；提交身份以包含本条记录的CP3提交为准，未push。无安装、下载、LLM、训练、GPU锁、全局solc或网络修改。所有原始数据与本轮新运行证据保留，后续修正须使用新批次。


2026-11-18收尾检查补记（修改 AI：Codex）：doc_check_v2七份正文全部通过；whitespace_review_v2通过，仅沿用旧批次322份精确SHA绑定的原始工具输出空白，没有新增代码或正文豁免。检查器v1误把git diff --no-index的正常差异退出码1当作空白错误，诊断输出实际为空；已保留v1，v2只修正退出码解释，所有实际空白诊断和异常仍拒绝，没有用v1暂存。该调整不改生产代码、不重跑测试或编译。本文补记后的最终字节由doc_check_v3核验；CP3仍等待11入口参数修正授权。


## 33. 2026-11-18 CompileRepair CP3：连字符入口限定修正与探针初始化停止（修改 AI：Codex）

### 33.1 任务、依据与范围

用户批准“批准限定修正与 11 个单元重验（推荐）”，对应已封存 cp3_binding_v1/leading_dash_review_request.json，SHA256 720b82ed018f97f1fe321585a218a23c362426408e0b18008b1d1336ea4c4bdf。沿用已读 PROMPTS r2.13 §4.1/§4.5，本次继续同一 CP3，不重复 pull。起始分支 compile-repair、HEAD e3fb634f86fe10723cb9f4c49f517c84b26b1b22，先将授权、848成员基线和代码/文档快照写入新批次 cp3_entry_v1。生产只修改 toolchain/project.py；测试修改 tests/test_project.py，新增 tests/fixtures/cp3_leading_dash/-contracts/Entry.sol 与 lib/Dependency.sol；记录修改本 CHANGE_LOG、HANDOVER、DECISIONS、PROGRESS、CP3_REPORT，并新增本批次运行脚本、请求和收据。cp3_binding_v1及更早产物不改写、不覆盖。

### 33.2 实施方式和问题处理

project.py 新增一个共享入口参数函数，仅当 project.entry 以 - 开头时加 ./；project_command 与 slither_arguments 都调用它。普通入口、源文件内容、版本候选、设置、D3 与项目绑定检查保持。新增两文件手写项目包含相对导入、直接合约类型变量及跨文件调用；四个参数化测试使用已安装的 0.4.12、0.4.24、0.5.17、0.8.38，检查共同目标、编译退出码、D3、绑定和调用文件身份。生产模块数仍为16。

Codex 编写的 run_entry_probes.py 漏建仓库外输出父目录，pytest 在首个普通入口测试初始化 tmp_path 时抛 FileNotFoundError。该错误发生在任何编译前，不是 solc/Slither 兼容性结论。已保留脚本、stdout/stderr、entry_probes.json；没有自动重试或重验语料。准备好的 run_entry_probes_v2.py 只补创建授权范围内的父目录，并改用新日志、证据与临时目录，不改测试/版本/验收条件；其执行等待 probe_setup_retry_request.json 对应答复。

### 33.3 实测与数据结论

首轮命令为生产 Python -B -m pytest -q -x -p no:cacheprovider compile_repair/tests/test_project.py -k 'leading_dash_entry_same_target or production_project_same_parameters'，完整命令和基目录见 entry_probes.json。退出码1、0 passed、1 setup error、27 deselected，包装器耗时4.196043秒；0次 solc、0次 Slither、0个语料重验，四版本探针与普通入口检查均未执行成功。这个数来自收据、pytest输出和不存在的仓库外输出根目录核验。现有31,071单元、21,150成功/9,921剩余失败仍是修正前观察，未生成或冒充新最终统计；其中11个调用错误待获准续跑并通过探针后再新批次重验。

### 33.4 用户批准、原文差异与待确认设计

2026-11-18 已定入口修正授权在 authorization.json，原用户原话与请求哈希完整保存。未修改既有 D3、D4、D5 或绑定门槛，没有提出额外替代修复方案。PROMPTS §4.1“失败就停，保留现场，不自动重试”适用于本次探针初始化失败，因此另行请求仅一次修正脚本后的八项检查；通过后沿用既有11单元重验批准，不重复索取该批准。费用上限0美元，不安装、不下载、不调用LLM，不修改全局solc。

### 33.5 验收、资源、未执行事项与停止

当前为停止检查点，入口代码已修改但四版本运行验收未通过，CP3尚未完成。完整production/mando/DFG回归本批次未运行；前批次723/6、271/458、2653/9warnings只能证明旧检查点，不能替代本次验证。11单元重验、新汇总和最终D6频率更新均未运行。正在完成中途停止要求的文档与范围检查，doc_check及保护结果在后续补记；此处不预写通过。没有新的安装、下载、LLM、HGT或GPU锁操作，不自动push。


2026-11-18 停止检查点验收补记（修改 AI：Codex）：doc_check_v1对六份正文及五份原文快照共11份全部通过；本补记后的最终字节由doc_check_v2再次核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、841份上一检查点保护成员、29,611份语料和10份资料均未变化；96份solc相关文件、两环境145/118份元数据、354条DFG代码引用和原生Slither解析器SHA保持。这些检查集合可能重叠，不相加计数。Python3.7语法解析与tracked diff --check通过，记录static_review；这些都是范围/静态检查，不能代替未完成的四版本运行验收。

本轮仍停在探针初始化错误后的续跑确认，没有再次运行pytest、solc、Slither或11单元语料。将按中途停止记录要求提交本地检查点，实际提交号以包含本补记的CP3提交及仓库外提交收据为准，未push。现有失败脚本和输出封存；若用户随后允许续跑，须把已准备且SHA固定的run_entry_probes_v2.py原字节复制到新证据批次执行，维持旧批次只读，不覆盖任何旧文件。该脚本按自身目录写入新证据，并使用新的v2临时目录；测试、版本、条件和原11项批准范围保持。


## 34. 2026-11-18 CompileRepair CP3：获准续跑探针，发现旧版允许路径问题（修改 AI：Codex）

### 34.1 任务、依据与范围

用户原话“允许修正脚本并续跑一次（推荐）”，来源为本轮异步回复call_ebfb49ec13754cc68d14041407f8d757。按PROMPTS r2.13 §4.1/§4.5继续同一CP3，起始compile-repair/8900abe8d5587524366e32e7092a43f4b932ee31；不重复pull，不改旧批次。先核对前两个交付清单的879个合并成员，再在cp3_entry_resume_v1保存authorization、baseline和五份文档快照。本轮没有修改任何生产文件、测试或夹具；新增证据脚本、收据、只读影响分析和未应用的建议补丁，并修改CHANGE_LOG、HANDOVER、DECISIONS、PROGRESS、CP3_REPORT及新README。

### 34.2 实施方式和重要选择

先将旧run_entry_probes_v2.py按原字节存为run_entry_probes_v2_approved.py；执行前静态核对发现pytest会创建current符号链接，原收据glob会重复收集末次测试。实际执行副本只增加跳过测试目录符号链接，不改八项测试、版本、夹具或验收门槛，也没有先运行后重试；具体两份SHA与理由在pre_execution_review.json。这是证据收集错误修正，前条交接中“执行原字节脚本”的准备安排有此明确差异，不隐去原版或伪称二者相同。

一次续跑使用生产Python、-x、无pytest缓存，普通入口四版本检查先全部通过。首个连字符探针0.4.12使用./-contracts/Entry.sol，入口已不再被当选项，但其../lib/Dependency.sol导入被拒绝，报File outside of allowed directories。已停止，未改夹具路径、未移动依赖来绕过失败、未改变D3或继续其他三个连字符版本。只读检查证明两个文件都存在于物化项目根内且SHA匹配夹具；错误出自--allow-paths .的目录许可效果，而非缺少源码。

建议补丁仅把project.py两处允许路径参数改为解析后的项目根绝对路径，solc argv与Slither solc_args保持一致，原./目标处理不变。补丁仅保存为proposed_project_allowed_paths.diff，未应用。已下载且SHA核验的0.4.12官方using-the-compiler第32行以绝对路径示例说明允许目录；这支持方案方向，但不能代替四版本实测，也不声称已证明新参数成功。未调用网络或下载新资料。

### 34.3 实测与数据结论

entry_probes_v2.json/stdout记录退出码1、4passed/1failed/27deselected，包装器4.440440秒；剩余三个连字符版本因-x未运行。按测试控制流，发生5次显式compile_project和4次run_slither调用（4个普通入口通过、1个连字符编译失败）；原生库内部额外子进程次数未独立计量，不混同于该API次数。失败编译的完整命令、0.4.12可执行SHA、cwd、退出码、stderr和源SHA保存于probes_v2/test_leading_dash_entry_same_t0/compiled.json。没有运行任何语料重验。

allowed_paths_existing_evidence只读核对旧result_provenance的31,071个结果SHA，耗时15.003687秒，发现92个单元含同一目录拒绝诊断、共521次保存的编译观察，版本为0.4.12–0.4.17；79个单元后来换版本成功，13个仍unrepaired。allowed_paths_source_verification核对这些调用中的1,473条诊断路径，全部文件存在且解析后仍在各自工作项目根内；这是诊断出现次数，不是独立文件数。92项与原11项互不重叠，建议新重验范围共103项，精确清单在allowed_paths_review_request。旧21,150成功/9,921剩余仍仅为修正前观察，79项成功也须重验以确定是否恢复更早合法候选；不能仅重跑13个失败项目，也不能提前计算新的成功率。

### 34.4 用户批准、原文差异与待确认设计

一次探针续跑批准已执行完毕，原失败和新失败均保留。原11单元批准仍是条件授权，八项探针未全部通过，所以没有进入语料阶段。目录参数修正超出原仅入口./前缀范围；额外92项的重验也没有既有授权。按§4.5第2节参数不兼容停下报告和§4.1不得自动重试，提交allowed_paths_review_request（SHA256 141e6bc425aee16c4c2198d2881f3d5b1187cff1667b00d74bf32fc72a08d43d）等待用户决定。

具体待确认方案是保持现有八项测试与失败夹具，新增四版本普通嵌套入口/兄弟导入检查，共12项全部通过后，仅重验92+11=103项；其他观察保留，在新汇总逐项绑定替换来源。候选顺序、设置政策、原始源码、D3与项目绑定门槛不变，物理允许根仍是同一个项目根。未提出删除或放宽验收的替代方案；绝对路径能否解决问题尚未验证。

### 34.5 验收、资源、未执行事项与停止

本轮探针验收未通过，CP3未完成，完整production/mando/DFG回归未运行。没有修改生产代码或测试，没有语料重验、新全量汇总或新的成功率。只读证据核对不属于实验重试；范围保护和doc_check结果后补，不预写通过。所有新记录、方案与失败现场按中途停止规则整理后本地提交，不自动push。无安装、下载、LLM、HGT、GPU锁或全局solc改动，费用0美元。


2026-11-18 停止检查点核验补记（修改 AI：Codex）：doc_check_v1对六份正文与五份文档快照共11份全部通过，最终补记字节另由doc_check_v2核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、874份上一检查点保护成员、29,611份语料和10份资料未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA不变。这些范围可能重叠，不相加作总文件数。生产仍16模块，本轮生产/测试/夹具均未修改。

Python3.7语法与未应用补丁的git apply --check通过，静态检查不替代四版本运行。tracked diff空白检查通过；唯一保留的是建议补丁.diff的四条空源行上下文，其单个前导空格属于统一diff格式，文件SHA与行号精确绑定于whitespace_review，不豁免生产代码、测试或正文的空白问题。补丁仍未应用。

一次探针续跑已经使用，后续三个连字符版本与任何语料均未继续。当前等待allowed_paths_review_request对应参数及103项范围批准；完整回归、新汇总和最终验收未运行，CP3未完成。按中途停止要求提交本地证据检查点，提交号以包含本条记录的CP3提交及仓库外收据为准，未push。后续批准后须在新批次继续，不向本批次或任何旧批次覆盖写入。


## 35. 2026-11-18 CompileRepair CP3：绝对允许路径修正、103项重验与最终分类（修改 AI：Codex）

### 35.1 任务、依据与范围

用户批准“批准参数修正、探针与103项重验（推荐）”，对应cp3_entry_resume_v1/allowed_paths_review_request.json，SHA256 141e6bc425aee16c4c2198d2881f3d5b1187cff1667b00d74bf32fc72a08d43d。沿用PROMPTS r2.13全文及§4.1/§4.5，起始compile-repair/967d0890b99de849a31de589ec0b08e12e52aa8b，同一任务未重复pull。先核对912个前序交付成员，授权、基线与快照写新批次cp3_paths_v1。生产只改toolchain/project.py；tests/test_project.py追加普通嵌套入口四版本测试，原八项与两文件夹具保持。记录修改CHANGE_LOG、HANDOVER、DECISIONS、PROGRESS、CP3_REPORT，新增批次README、证据脚本、授权、运行/检查收据和汇总；精确交付路径在本批次delivery_inventory。

### 35.2 实施方式和问题处理

应用已批准的两处参数补丁：solc argv及Slither solc_args使用解析后的项目根绝对路径作为--allow-paths；物理允许根仍是同一个项目根。保留连字符入口./前缀、普通目标字符串、源码、候选升序与设置政策、D3和直接类型绑定门槛。新测试从原手写夹具复制相同源字节，仅采用普通嵌套入口路径，核对兄弟导入、完整图和跨文件调用；没有移动依赖绕过原失败。

12项探针通过后执行精确103项清单。首个cp3_05901已成功保存图，但运行脚本误将内存EnvironmentPlan的tuple字段与旧JSON的list直接比较，导致“Candidate plan changed”误报；保存的新旧JSON计划和输入逐字段全同。保留首段停止收据与seal，只读恢复该成功结果的分类，接着在新目录执行尚未运行的102项，首项没有重复编译。比较器改在JSON序列化边界核对全部字段，未删除字段或放宽候选条件。原首段summary的0计数是尚未追加分类条目的计数，实际已有1次显式编译和1次Slither；driver_comparison_recovery单独更正，不覆写原记录。首项分类未保存精确单元结束时间，elapsed_seconds置null并注明原因，不捏造时间。

最终只读汇总首次误认为历史中断段有正常seal.json；该段真实身份是此前已封存的interrupted_segment_preservation.json。修正汇总器，对这个精确历史路径使用已登记且核对SHA的保全清单，正常完成段仍查seal。第一次汇总失败及修正依据保留，第二次汇总无编译调用。运行脚本执行前另将schedule文字从“前缀/续段”改为“精确批准ID”，只新增v2脚本，选择列表未变。以上均属证据/脚本问题，未修改生产判据、重试已执行实验或扩展批准清单。

### 35.3 实测与数据结论

path_probes：12passed/27deselected，5.097138秒；四版本为0.4.12、0.4.24、0.5.17、0.8.38，普通根入口、连字符嵌套入口和普通嵌套入口均满足检查。原八项断言及夹具保留。首段包装器18.600598秒，102项续段73.017230秒；合计103个不同单元各执行一次，manifest唯一性在runtime_acceptance验证。

103项由原79成功/24未修复变为89成功/14未修复：10项新增成功，原79项保持成功且均恢复更早版本（0.4.18→0.4.12共35项、→0.4.13共2项、→0.4.15共9项、→0.4.16共33项）。14项剩余为12项Slither工具限制、1项类型错误、1项未声明标识符，真实源码/工具问题未通过改判掩盖。新观察453次显式编译、265次Slither；被替换旧观察1032/187次保留并从有效统计剔除，另保留此前335/230次旧项目观察和9次中断编译。

最终31,071有效单元为21,160成功/9,911剩余失败，另236条非Solidity单列；每项只计一次。仅103条来源替换，其他30,968条结果与原provenance逐字段保持，不假称全量都用新实现重新运行。有效编译115,192次、Slither21,376次；旧parse失败而新pragma读取成功1012项，|| pragma 1项。项目Slither调用15,849次、直接合约类型声明核对34,980条；207次未获绑定认证全部为Slither未构造，D3为true但绑定拒绝仍0次。

failure_summary保留每类计数、失败分母比例、语料分布、最多3个SHA例证、包/路径与候选统计、23种other模板。D6/CP4清单仍含29类与125条breaking changes，10个零频类别保持，频率只更新实现优先次序，不删除规则候选。完整数字、版本迁移和替换路径见runtime_acceptance、replacement_summary、result_provenance、failure_summary与d6_cp4_final；汇总包装器31.164432秒，无新编译。

### 35.4 用户批准、原文差异与待确认设计

参数修正及103项范围均已明确批准，authorization保留原话、日期、原请求SHA和精确ID。没有新的方案偏离或待批准执行事项；D3、D4项目身份、D5选版与已批准绑定检查保持。恢复首项结果后仅继续102个未执行ID属于原103项批准，没有实验重试。官方资料与语料仍只作本地只读研究；原下载、项目图身份与绑定检查等历史授权保持可追溯。

当前已知限制仍是||区间尚未实现、Slither进程内无强制超时、直接绑定检查不覆盖全部IR语义；D19下限维持0.4.12，6个原区间允许0.4.11而不允许0.4.12的单元已登记，未扩展支持范围。CP3只分类并提出D6规则和CP4算子，不实现依赖补全、tuple改写、LLM或CP4基准运行。

### 35.5 验收、资源与交付

三套最终无缓存回归均通过：production731passed/6skipped（72.332530秒），mando271passed/466skipped（20.864750秒），DFG2653passed/9既有warnings（156.669927秒），完整命令、cwd、返回码和计数在pytest_*_final_v1收据。定向12项与103唯一单元验收通过；原79成功无回退，输入/序列化计划逐项全同，最终观察中不再有已识别的允许目录拒绝。保护审计、doc_check及提交身份后补，未预写最终文档检查通过。

本轮0美元，无安装、下载、LLM、HGT、GPU锁或全局solc更改。CPU线程设置沿用2，运行原始证据在仓库外compile-repair-local/cp3_paths_v1；不提交外部语料源码，不清理旧临时目录。文档与范围核验通过后本地提交，不自动push；CP3实验与回归已完成，最终交付检查收尾后交独立审查。


2026-11-18 最终交付核验补记（修改 AI：Codex）：frozen_audit通过，28,908份保护跟踪文件、25,828份旧封存文件、905份上一检查点保护成员、29,611份外部语料及10份官方资料均未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA保持。这些检查集合可能重叠，不相加作总文件数。历史文档均保留，生产仍16模块。Python3.7语法检查、tracked diff空白检查及本批次新文件空白检查通过，没有新增豁免。

doc_check_v1对六份正文与五份原文快照共11份通过；本补记及当前状态更新后的最终字节由doc_check_v2再次核验，提交以该收据通过并绑定各文档SHA为前置条件。新证据由evidence_seal与delivery_inventory封存，acceptance_status汇总最终门槛。完整回归与保护检查已通过，此后只补交付记录，没有再跑实验或修改生产代码。

CP3本地实施与验收完成，后续交独立审查。仅本地提交compile-repair，实际提交号以包含本记录的CP3提交及仓库外delivery_commit_receipt为准；本轮未push，未实施CP4或新增修复规则。参数修正及103项批准全部落实，无新增待批准执行事项；已知工具与版本边界继续按本报告保留。


## 36. 2026-11-21 CompileRepair CP3 审查与方案 r2.14（修改 AI：Claude）

### 36.1 任务、依据与范围

用户要求（2026-11-21）：Codex 已完成 CP3；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP4。起点 `compile-repair@6d7043e8b`（CP3 的六次提交 88b499e71…6d7043e8b）。审查对象：`toolchain/solc.py`、`toolchain/project.py`、`toolchain/slither.py`、`pipeline.py`、`evaluation/report.py`、`evaluation/survey.py`、`cli.py` 的差异，新测试与夹具，`cp3_paths_v1` 的汇总与 `cp3_binding_v1` 的 MANDO 验收，CP3_REPORT 全文、HANDOVER、DECISIONS、CHANGE_LOG §29–§35、PROGRESS。

修改：`PROMPTS.md`（r2.13 → r2.14）；新增 `artifacts/cp3_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节第 1 条补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（新增 D21，历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 36.2 实施方式和重要选择

- 代码：逐个读新函数。诊断解析与 pragma 子类符合 r2.11–r2.13；project.py 只读解析闭包，未解析导入不编译；slither.py 的项目身份与绑定检查、pipeline 的多文件路径与单文件路径分开。
- 统计口径：读 report.py 后发现类别按所有候选版本合并。只靠语料统计看不出影响大小，因为每单元的结果只在用户本机；改用仓库内的 MANDO 三个文件逐版本编译证明机制：它们在 0.4.24–0.4.26 rc 0，真正失败在 Slither，却被计入两个源码类。处理选择：增加“主因”口径而不是替换原口径——主因按阶段与跨版本持续性确定，原口径保留以便对照；只需重新汇总已保存结果，不重新编译。
- Trace on-chain：5,000 个经过验证的链上合约中 432 个计入 parser_error_other，不合常理。按用户“仅本地研究使用”的批准，从固定提交取 CP3 给出的示例文件（SHA 与清单一致），确认它是 Etherscan 标准 JSON 输入包装；解包后用与模块相同的参数编译与构建 Slither，确认是不改源码的输入处理。处理选择：CP3.1 只新增类别、判定与统计，解包实现留 CP5（第 2 步项目组装），与 CP3“只分类不修复”的范围一致。
- 绑定检查：用户已批准的检查只看合约类型变量。自写类型转换与 new 的用例，确认生产 Slither 同样按名称错绑，而检查 0 条时判为通过。可选做法：（a）扩展检查到所有 AST 引用并与 IR 逐一对照；（b）闭包含同名合约即判图不可用。选择（b）：判定只依赖 AST 中的定义名称，机械且保守；（a）需要把每个引用与 Slither IR 对应，容易出现新的漏检。它比已批准的条件更严，记为 D21 待用户批准。
- pragma 写法：DAppSCAN 的 18 个 unsupported_expression 来自真实项目，自测常见写法，发现通配符与缺补丁号被拒。以真实 solc 逐版本作为判据，避免凭记忆实现 semver 规则。
- MANDO：pipeline.py 改动约 180 行，CP3 只核对计数；补一次与 v5 的字节对照。

### 36.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 诊断与报告测试 | 审查环境 70 项通过；test_project.py 在本机之外导入失败（路径依赖） | pytest |
| MANDO 三个文件逐版本 | 0.4.12–0.4.15 Undeclared identifier，0.4.16–0.4.23 Expected token Comma，0.4.24–0.4.26 rc 0；CP3 计入 undeclared_identifier 与 parser_error_other | probe_mando_versions.json |
| Trace cp3_23864 | `{{…}}` 包装，language Solidity，20 个源文件，optimizer 开、evmVersion paris | trace_wrapper_example.json |
| 解包后 | solc 0.8.24、0.8.38 rc 0；Slither 20 个合约、265 个函数 | wrapper_unpack_probe.json |
| 类型转换错绑 | solc：A→A.sol、B→B.sol；Slither：两次调用都→B.sol；绑定检查 0 条、complete=true | probe_alias_cast.json |
| pragma 写法 | `0.4.x`、`0.4.X`、`0.5.*`、`^0.5` solc rc 0、模块拒绝；`^ 0.5.0`、`=0.5.12`、`~0.4.24` 等正常 | probe_pragma_forms.json |
| MANDO 验收 | 只有 843 成功、3 个 Slither 侧失败的计数；无图字节对照 | cp3_binding_v1/mando_subset_acceptance.json |

未证明：Trace on-chain 432 个解析错误中包装格式所占数量；92 个 unsupported_expression 中可由通配符扩展解决的数量；闭包含同名合约的项目数量；主因口径下的类别频率。以上由 CP3.1 统计。

### 36.4 用户批准、原文差异与待确认设计

- Codex 处理成立的部分：诊断、项目闭包、身份扩展、连字符入口、允许目录；执行中的 SOChecker 子集、同名 key5、同名错绑、连字符、允许目录、探针与驱动脚本错误都按共享上下文停下并经批准继续。
- 新发现：五个问题，见 36.3。其中统计口径与 pragma 扩展不改变已定决策（前者只增加口径，后者只在原实现拒绝的表达式上改变结果）；输入格式是新增类别；同名合约的判定比已批准的接受条件更严，需要用户批准 D21。
- 待用户批准：D21。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 36.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp3_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；从 Trace 固定提交取 1 个文件（约 94 KB，用户已批准的本地研究范围，不提交）；没有安装或 LLM 调用，费用 0。
- 停止：CP4 不能开始。顺序为用户决定 D21 → Codex 执行 CP3.1 → Claude 审查 → CP4。本轮提交并 push 到 `compile-repair`。


## 37. 2026-11-21 CompileRepair CP3.1：主因分类、包装识别、项目图与版本回归（修改 AI：Codex）

### 37.1 任务、依据与范围

CP3.1 以 `compile-repair@61c94e00` 和 PROMPTS r2.14 §4.5b 为基线。结果逐项联系旧 CP3 与新批次。31,071 个有效单元中 21,223 成功、9,848 未修复，另有 236 个非 Solidity 输入。相对 CP3 新增 63 项成功。510 项有新结果，30,561 项沿用经哈希核对的 CP3 结果。

先快进同步 6d7043e8 至 61c94e00，查阅共享上下文、§1.17、§3.10、§4.5b、交接 0–5、§35–36、DECISIONS 及 cp3_review_v1。生产改动为 evaluation/report.py、toolchain/project.py、toolchain/slither.py、pipeline.py 和 rules/environment.py。新增 tests/test_cp31.py、三份 cp31_alias_cast 手写夹具，更新 test_project.py 与 test_pragma_bytes.py。还更新 CP3_REPORT、PROGRESS、本节、HANDOVER 和 DECISIONS。结果在 artifacts/cp3_1_v1，完整文件清单见该批 delivery_inventory.json。外部语料原文和完整运行存储保存在仓库外。

### 37.2 实施方式和重要选择

主因使用早期阶段、可编译版本的 Slither 结果以及跨编译器类别交集；保留旧任一候选表、版本组合与逐项来源。标准 JSON 包装只需解析输入、检查 Solidity 语言及源内容类型，即可在版本计划前结束。先从 solc 闭包 AST 统计定义名称，再与原 D3、变量绑定事实并列记录。若 Slither 构造失败，CryticCompile 仍持有 AST 时也能给出重名原因。原始语料仅用于测量。部分版本号使用实测的上下界求值，`||` 沿用拒绝路径。模块与函数的变更行数、16 个生产文件的最终 SHA 见 scope_audit.json 和 CP3_REPORT。

矩阵预检最初把 4 个历史负对照也计入，调用 solc 前停止。选择 92 个支持版本后，前 3,681 对发现旧 solc 的语法拒绝，收到确认后只测剩余 3,863 对。旧版 solc 的 --help 可在显示帮助后返回 1，AST 测量按实际帮助文本选择是否支持 stopAfter。正式回归的最初读入脚本误以为 v5 的 seal 单独受 Git 跟踪，改按受跟踪 README 登记的 seal SHA 核验，并对每个对照成员再核对 SHA。两环境首轮 suite 各有一条旧 `0.5` 负例失败，更新为同时验证冻结旧行为和新版预期。最终又核验了保留 CryticCompile AST 的生产实现。DFG 的代码引用取自已有 mando 环境，最初在 production 导入 torch 失败的范围检查日志也已保留。一次查询 WSL 运行日志遇到短时服务超时，随后读取同一运行的终态收据完成核对。

### 37.3 实测与数据结论

- 31,071 个旧结果在读取时逐一核对 SHA，原分类表全部类别的单元数得到复现。3 个 MANDO 工具侧失败的主因均只有 slither_incomplete。最终主因表有 221 个 version_dependent 单元。两表各类单元数、比例、分语料数量与 SHA 示例见 failure_summary.json 及 CP3_REPORT。
- 31,307 个原始输入中识别出 410 个包装，全部来自 Trace on-chain，旧类别均只有 parser_error_other。它们在正式流程中停在 input_format。3 个前提样本共 4 组解包后工具运行，solc 与生产 Slither 均成功。30 类分类表与 125 条 breaking changes 均入 D6/CP4 文档，CP5 包装处理等级为 none。
- 24,549 个项目单元中旧 AST 可直接核实 15,642 项，其余 8,907 项各一次只生成 AST 的调用。合并同源 SHA 的定义证据，18,389 项可判定，其中 12 项有重名，旧成功数 0；6,160 项资料不足。12 项限定重验维持未修复。
- 82 × 92 的区间测量共 7,544 对，全数与获准的实际接受判据一致。137,792 次旧可求值表达式出现的结果保持，846 个 MANDO 输入的升降计划均相同。88 个旧拒绝单元获得候选，63 个成功，其中 DAppSCAN 18、SOChecker 45。其余 25 项有后续诊断。
- 510 项替换实际调用 solc 1,050 次、Slither 63 次，逐项绑定原结果和新结果。生产 MANDO 回归 846/846 的状态、原因、选定版本、设置、标志与输入相同，843/843 图逐字节一致，另外 3 个已知失败无图。

### 37.4 用户批准、原文差异与待确认设计

2026-11-21 收到“同意 D21”、“同意按实测语法拒绝单列并继续”、“同意单列 AST 不足”。三项授权绑定原请求 SHA，分别见 authorization.json、pragma_authorization.json、ast_coverage_authorization.json。矩阵遇到的 360 次语法拒绝均为相同的 parser token 错误，原文仅看版本错误字符串会误计为适用。AST 未知单列后，全体重名数量只能给出至少 12 项，已知成功项目中的数量可精确给出为 0。D21 的保守性及此统计边界均在报告保留。D19 等既有待定项另行处理。

### 37.5 验收、资源、未执行事项与停止

production 模块 758 passed / 6 skipped，mando 模块 295 passed / 469 skipped，mando DFG v2 为 2,653 passed / 9 个既有警告。完整命令、耗时、最终运行与首轮问题均在批次收据。最终 MANDO 使用 CLI repair、原 846 路径、--regression mando、--order ascending，CLI 2 对应已核验的 3 项未修复。主要原始运行、额外 AST 调用和三个包装解包样本均在仓库外。费用 0 美元，未安装、下载或调用 LLM，未训练或操作 GPU 锁。

保护核验通过，包括 354 条 DFG 引用、25,828 个历史封存成员、29,611 份外部语料、10 份官方文档、96 份 solc 文件和两环境的 145/118 份元数据。文档 UTF-8/CJK 检查以批次 doc_check.json 的最终字节哈希、命令和返回码为准，全部通过后提交。CP3.1 本地完成后交独立审查，未启动 CP4。本轮仅本地提交，提交标识由包含本节的 CP3.1 提交给出。

2026-11-21 文档核验补记（修改 AI：Codex）。本节、交接、决策、进度、CP3 报告和批次 README 共六份文档均已通过 doc_check。最后追加本条记录后再次检查六份文件，最终字节与 SHA 见 doc_check.json。


## 38. 2026-11-22 CompileRepair CP3.1 审查与方案 r2.15（修改 AI：Claude）

### 38.1 任务、依据与范围

用户要求（2026-11-22）：Codex 已完成 CP3.1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP4。起点 `compile-repair@1ba841cbc`。审查对象：`evaluation/report.py`、`toolchain/project.py`、`toolchain/slither.py`、`rules/environment.py`、`pipeline.py` 的差异，`tests/test_cp31.py` 等测试，`cp3_1_v1` 的汇总、MANDO 回归收据与 pragma 矩阵，CP3_REPORT 的 CP3.1 节、HANDOVER、DECISIONS、CHANGE_LOG §37、PROGRESS。

修改：`PROMPTS.md`（r2.14 → r2.15）；新增 `artifacts/cp3_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 38.2 实施方式和重要选择

- 代码：逐个读新函数，对照 4.5b 节的六节要求。
- pragma：不复用 Codex 的矩阵，另写 20 个表达式（通配符、缺补丁号、`^0`、`0.x`、组合比较）在审查环境 37 个版本上与真实 solc 对照，并在当前提交上重跑一次。
- 包装：用 12 个手写正负例检查 standard_json_input，发现 BOM 与只有 urls 两个边界。
- 剩余的 Trace 解析错误：410 个包装之外还有 22 个 on-chain 单元计为 parser_error_other。按用户批准的本地研究范围从固定提交取这 22 个文件，只记录结构特征（不复制内容），确认全部是 Vyper。读代码发现 SOChecker 的非 Solidity 判定只在清单脚本中使用，生产流水线没有语言判定。处理选择：把已批准的同一规则移到生产输入阶段并统一使用，而不是为 Vyper 另写规则——这样不引入新的判定依据，并以“已成功单元全部判为 Solidity”作为硬判据。
- version_dependent：最常见的组合与 0.7.1 起允许文件级函数一致。主因口径不改，只增加“可解析版本上的阻碍”一列，供 D6 排序参考。
- MANDO：读 `mando_regression_final.json` 的 846 条逐项检查结果。

### 38.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 主因规则 | 与 4.5b 节第 1 节一致；MANDO 三个单元只有 slither_incomplete | 代码、CP3_REPORT |
| pragma 独立判据 | 20 式 × 37 版 = 740 组，0 不一致（含 `0.x` 在 0.4 系列被拒、`^0` 从 0.5.14 起接受） | oracle_pragma.json |
| 包装正负例 | 双花括号、标准 JSON、多文件映射、空白识别；ABI、Yul、截断、NaN、源码不识别；BOM 与只有 urls 不识别 | probe_wrapper_detect.json |
| 剩余 22 个 Trace 解析错误 | 5 个 Vyper 标准 JSON 包装、16 个带版本注释的 Vyper 源码、1 个无版本注释的 Vyper 源码；都不含 `pragma solidity`；SHA 与清单一致 | trace_parser_units.json |
| MANDO | 843 条七项检查全部为真；3 条预期失败其余字段相同 | mando_regression_final.json |

未证明：0.6、0.7 系列上的 pragma 判据（只由 Codex 的矩阵覆盖）；BOM 与只有 urls 的包装在语料中的数量；词法规则在全部语料上的误判数（CP3.2 统计）。

### 38.4 用户批准、原文差异与待确认设计

- Codex 处理正确：CP3.1 六节全部实现；D21、语法拒绝单列、AST 不足单列都先经用户批准；旧测试的断言改为同时断言新旧行为并保留两次结果。
- 新发现：Vyper 输入被当作 Solidity 解析错误（生产没有语言判定）；包装的两个边界；version_dependent 缺少阻碍。语言判定沿用已批准的规则，不需要新的用户决定。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 38.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp3_1_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；从 Trace 固定提交取 22 个文件（用户已批准的本地研究范围，不提交）；没有安装或 LLM 调用，费用 0。
- 停止：CP4 不能开始。顺序为 Codex 执行 CP3.2 → Claude 审查 → CP4。本轮提交并 push 到 `compile-repair`。


## 39. 2026-11-22 CompileRepair CP3.2 生产输入判定与版本依赖阻碍（修改 AI：Codex）

### 39.1 任务、依据与范围

用户要求阅读最新 PROMPTS，先 §4.1 再执行 CP3.2，任何替代方案先咨询并记录。工作树 compile-repair 已通过 `git pull --ff-only origin compile-repair` 同步至 992bec09。依据为 r2.15 §1.18、§3.10、§4.5c、HANDOVER 第 0–5 节、DECISIONS、CHANGE_LOG §37–38、cp3_1_review_v1 的 README、Trace 记录与包装探针结果。语料只读，CP0–CP3.1 产物只读。

生产修改为 toolchain/project.py、evaluation/survey.py、pipeline.py、evaluation/report.py；测试为 tests/test_cp32.py。报告与记录为 CP3_REPORT.md、PROGRESS.md、docs/HANDOVER.md、docs/DECISIONS.md 和本节。新批次 artifacts/cp3_2_v1 包含原判定及停止证据（input_census、input_gate、input_observations、explain_gate、decision_request）、授权 authorization、生产判定与替换（classify_inputs、language_acceptance、language_classifications、input_results、replacement_provenance）、归因与统计（aggregate、unit_attributions、non_solidity、unmeasured、version_blockers、failure_summary、taxonomy、d6_cp4_final）、测试和保护（run_suite、三个配置的测试日志与收据、scope_check、audit_results、verification）、README、doc_check 和 seal。扩展名与完整文件清单见批次 seal 和 git 提交。没有改动 scripts、根交接、原作者代码或标签。

### 39.2 实施方式和重要选择

先用原函数做只读普查，逐入口校验原 SHA，碰到相同内容只复用语言判定，每个单元仍单独记账。全集对照发现 8 个 D3 成功单元会被拒，因而在接入生产前停下。复核了这 8 项旧清单、图以及一个无任何词元的 SOChecker 历史排除项。证据和建议单独存为 decision_request.json，获批后执行新口径。两次普查分别保存，旧文件不覆盖。

完整移动 evaluation/survey.py 原词法函数，函数文本 SHA256 为 569b75cc5964c7ad30eec2eb4ce75952c52ce153b603fff4e61c9265c4fbee94。生产仅以入口字节判断 JSON、原 Solidity 正证据及 Vyper 语法。可验证的 Vyper 线索包括版本指令，或修饰器、函数和类型声明的组合。调用现有 lexical_tokens 核对线索在非注释、非字符串区域。BOM 处理保留原始 SHA，缺正文条目记录数量。入口未定状态写入 manifest 后可继续选版。历史 236 项的放行与编译结果分列，归因阶段依据已保存来源替换 23 条，其余观测保持原引用。版本阻碍只从无两种解析错误的候选取交集，主因与 D6 排序依据均保留。

### 39.3 实测与数据结论

| 核对项目 | 原值或预期 | 实测及依据 |
|---|---|---|
| 原词法硬判据 | 21,223 个成功都须判为 Solidity | 21,215。3 空、4 纯注释和 1 个仅含 struct 的文件被误排，8 条原成功记录及图均核对，见 input_gate、decision_request |
| 批准后的判据 | 原成功完整放行，MANDO 全部有 Solidity 证据 | 21,223/21,223、846/846；全量 31,307 项逐项见 language_classifications |
| 失败统计 | 原 31,071 个有效、9,848 个失败 | 有测量的 31,048 项中 21,223 成功、9,825 失败。23 项非 Solidity 均在 Trace on-chain，236 项未测均在 SOChecker，见 failure_summary 和 non_solidity |
| 输入原因与包装 | 审查 Vyper 22 项；原包装 410 | 原 22 项及另 1 项旧结构不平衡均为 Vyper。5 项 JSON、17 项版本指令、1 项无版本注释。两个包装边界探针通过，全量新增命中 0 |
| 版本依赖 | 增加可解析版本上的阻碍并保持主因 | 221 项均重核原诊断，183 项存在共同阻碍，38 项为 none。前三种完整组合 113、23、14 项，见 version_blockers |
| D6 与证据 | 按主因排顺序，旧结果不覆盖 | 缺包 8,454、缺相对文件 412、包装 410、其他解析错误 257。31 类、125 个变更项。核对旧清单 31,071 条、642,763,760 字节及 354 个 DFG 引用，见 verification |

输入清单 SHA256 为 `8d015af6a11df71293b38a64022901b33e0546ed360cc46b0b1b6dd21ba39295`。原归因存档 SHA256 为 `fa03bed0f429e8db902422ff750e6221e1dce478f688dade5f85b996f81a0bd9`。每个原始入口、旧结果和新替换的具体 SHA 可从本批归因或来源表取得。未测单元没有新的编译成功率结论。

### 39.4 用户批准、原文差异与待确认设计

2026-11-22 用户原话“批准三态判定及新旧统计口径”。相应调整是 §4.5c 第 1 节对语言未定输入和对历史 236 项的处理。源文件不含充分词法证据时放行，明确其他语言才排除。全部原成功项必须继续获准通过，同一套规则应用于所有来源。本次无需补编译，沿用 236 项历史排除口径，同时单列新口径的 236 项未测。原规则停止与新授权完整留存，DECISIONS 已记入当前状态与历史。对没有正证据的其他语言，生产仍可能进入编译；覆盖边界见报告。本轮没有新的待确认调整。

### 39.5 验收、资源、未执行事项与停止

两套模块和 DFG v2 全部运行，执行命令、环境和临时目录见各自 `*_tests.json`。从仓库根使用生产 Python 3.10 跑模块得到 796 通过、6 跳过（89.80 秒）；mando Python 3.7 跑模块 333 通过、469 跳过（26.84 秒），跑 DFG v2 得到 2,653 通过与 9 个警告（186.80 秒）。全量输入判定用 CPU，原规则扫描 21.818 秒，获批判定扫描 23.247 秒，最终独立数据核验 35.731 秒。生产模块仍 16 个，4 个有改动。冻结代码对照通过。

doc_check 用 `python -B -m scripts.node_sem.doc_check --expect-cjk` 检查 6 份文档。HANDOVER、DECISIONS、批次 README 检查全文，CHANGE_LOG、PROGRESS、CP3_REPORT 从追加前的 270618、72228、85753 字节检查。六份均 passed=True，命令、SHA 和结果在本批 doc_check.json。费用 0 美元，无安装、下载、LLM 或 HGT 训练。没有重编译语料或重跑 MANDO；现有模块测试按其原有设计使用小型工具夹具。本轮以 `CP3.2` 开头的信息本地提交，提交号由 git 日志和交付消息提供。CP4 等独立审查。


## 40. 2026-11-22 CompileRepair CP3.2 审查与方案 r2.16（修改 AI：Claude）

### 40.1 任务、依据与范围

用户要求（2026-11-22）：Codex 已完成 CP3.2；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP4。起点 `compile-repair@7336436e7`。审查对象：`toolchain/project.py`、`pipeline.py`、`evaluation/report.py`、`evaluation/survey.py` 的差异，`tests/test_cp32.py`，`cp3_2_v1` 的汇总、决定请求与授权，CP3_REPORT 的 CP3.2 节、HANDOVER、DECISIONS、CHANGE_LOG §39、PROGRESS。

修改：`PROMPTS.md`（r2.15 → r2.16）；新增 `artifacts/cp3_2_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 40.2 实施方式和重要选择

- 偏离方案的判断：r2.15 要求“无 Solidity 证据即排除”，Codex 实现为三态。读决定请求与授权，确认是硬判据（原成功单元全部放行）首次失败后停下咨询、用户批准的结果。失败的 8 个单元是空文件、纯注释与只有顶层 struct 的文件，solc 接受、图为 0 个节点，说明原规则把“没有声明证据”当成了“不是 Solidity”。三态判定只在有正证据时排除，既满足硬判据，也覆盖全部 22 个 Vyper；判断为 Codex 的做法正确、原方案应修正。
- 独立核对：自写 11 个边界输入（注释、NatSpec、字符串中的 Vyper 字样，BOM、urls、Yul 包装等）与真实输入（源码目录全部 .sol、测试夹具、22 个 Vyper、包装示例），逐个调用 `input_format_evidence`；核对汇总中的加减关系；在审查环境运行 CP3.x 测试。
- CP4 提示：§4.6 原只有范围。按 CP3.2 的 cp4_common_protocol 与 23 个类别的 cp4_operator 细化：基础单元条件（排除 0 节点图与 unknown）、项目分组与固定哈希划分、AST 定位的确定性编辑、规模上限与分层抽样、触发判定（以环境步骤后的主因为准，换版本即可解决的样本单列）、评分函数（两段偏移映射组合后比较 kept 节点、边、调用，检查 lost 与 added），以及“精确还原必须满分、故意错误必须检出”的自检。评分函数放在 CP4，是为了 CP5 以后的每个修复阶段用同一把尺子。

### 40.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 边界输入 | 11 例全部符合预期；无版本无声明的 Vyper 为 unknown（已知限制） | probe_language_adversarial.json |
| 真实输入 | 1,694 个 Solidity 全部判为 solidity；22 个 Vyper 全部 non_solidity；包装示例 20 源、6 个 settings 键 | probe_language_real.json |
| 统计 | 31,307 = 31,284 + 23；31,284 = 21,223 + 9,825 + 236；parser −22、unbalanced −1 | CP3_REPORT、failure_summary.json |
| 测试 | 132 项通过 | 审查环境 pytest |

未证明：236 个 SOChecker unknown 输入的编译结果；缺少正证据的其他语言输入在检测时的数量。

### 40.4 用户批准、原文差异与待确认设计

- Codex 处理正确：按硬判据停下、在改生产代码前咨询、保留首次失败记录；批准后实现与批准一致。
- 原方案修正：r2.15 第 4.5c 节第 1 节的排除规则过严，以用户批准的三态判定为准。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。CP4 不需要新的用户决定或授权。

### 40.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp3_2_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP3 系列结束，可以开始 CP4。本轮提交并 push 到 `compile-repair`。


## 41. 2026-11-22 CompileRepair CP4 破坏样本、真值图与评分验收（修改 AI：Codex）

### 41.1 任务、依据与范围

在 compile-repair 分支 fast-forward 同步至 06ad69c26fcb13c163a55333ab95738bfaf71fdd，先读共享 §4.1，再读 r2.16 全文、CP3.2 独立审查、交接和变更。新增 evaluation/benchmark.py、tests/test_benchmark.py、CP4_REPORT.md 与 artifacts/cp4_v1/。修改 core/provenance.py、cli.py、tests/test_cp1_1.py、PROGRESS.md 及 docs 的 CHANGE_LOG、HANDOVER、DECISIONS。批次内脚本、收据、压缩明细和日志按 seal.json 枚举。冻结语料、既有产物与根目录记录均按原身份读取，未安装、下载依赖或训练。

### 41.2 实施方式和重要选择

在共享层增加 compose_offsets，以两段实际字节编辑核验偏移和恢复位置。评分按映射后的 key5 比对节点类型和规范化 IR，按重数比较 CFG 边和调用，记录受影响、最终丢失与新增节点及位置。复用 toolchain/solc.py 的 lexical_tokens 和 compile_file（文件 SHA256 362a6e8fad7159e8c277d50c96966c280615bca52208900f6cffd76a73f14c3e）、pipeline.py 的 repair_unit（3d0a27d7789dd73fcaa2549d15387cda22ac4b7fcbe48de84143a3af60112655）以及生产 run_slither。按编译器次版本分层抽取，先固定计划再运行。每个编辑字节、受损闭包和实际调用均有可校验的本地收据。Windows 新建 WSL 客户端间歇出现 0x8007274c 时，从共享文件核对原作业进展并保留原进程。

精确逆编辑按样本验证，同一基础单元恢复出相同闭包后共用实际生产图。首轮 cp3_23979 精确还原只有 298/299 个节点一致，比较实际图和工具收据把差异定位到创建代码中的 IPFS 摘要。经授权，同路径只读观察验证图字节一致，原失败留存，续跑收据另建 identity_continuation。迁移测试也按 r2.16 的 17 文件要求更新了旧断言。

### 41.3 实测与数据结论

初始 31,307 项，21,223 项有成功历史。排除 5,087 个空图后，16,136 个基础单元通过门槛，分为 6,012 组。MANDO 843 份成功图与 v5 逐字节一致。200 个对照全部保持原版本、设置与图。17,432 个候选中纳入 11,858（dev 2,460、test 9,398），环境解决 743，未触发 4,831。17 类有真实纳入样本，另五类的零值、原因及 506 行语料/版本分层见 CP4_REPORT.md、benchmark_counts.json 和 strata.tsv。

全部 11,858 个精确逆编辑均达到 kept、CFG、调用比例 1，最终丢失与新增为 0。22 个实际编译的错误修复和一个缺节点图均检出，另核对 24 个历史失败单元。候选执行 831.451 秒，选定版本单独调用 11,560 次 solc，环境步骤 172,620 次 solc、743 次 Slither，这些次数只统计候选阶段。其余阶段耗时与 SHA 见本批各阶段收据。

### 41.4 用户批准、原文差异与待确认设计

2026-11-22 用户原话“同意分别统计并验证恢复”“同意单列历史回放”。前者区分破坏影响与修复后的缺失，后者限定分析器类别使用历史收据与无害负例。用户随后回复“同意更新断言并续跑测试”和“同意先做同路径复核，通过后续跑”。前一次只调整测试文件清单，后一次保留 4,315 项通过结果，在新批次复核已失败的一项及 7,542 个未测项。metadata 和图评分要求完整保留。四项决定及证据见 DECISIONS 和本批三个授权文件。

### 41.5 验收、资源、未执行事项与停止

三个套件通过。生产 815 passed, 6 skipped in 87.16s (0:01:27)。mando 352 passed, 469 skipped in 53.89s。DFG v2 2653 passed, 9 warnings in 227.31s (0:03:47)。 各自命令和首次失败另有完整日志与 JSON。生产文件 16 → 17，新增/修改生产文件为 cli.py、provenance.py、benchmark.py，DFG 冻结代码引用 354 项一致。模块外已跟踪文件与旧批次均无改动。六份本轮文档通过 scripts.node_sem.doc_check --expect-cjk，详见 cp4_v1/doc_check.json。CPU 本机运行、费用 0 美元，LLM、训练、安装均为 0。证据封存 23fa2d392f9a776fe1c4636e2ddc7c8a36e96b1c8dfc67de5cbb70f0dbaeec7c。提交在本地 compile-repair，提交号可由 git log --format=%H -1 -- compile_repair/CP4_REPORT.md 查询。本步结束于 CP4 独立审查之前。


## 42. 2026-11-22 CompileRepair CP4 审查与方案 r2.17（修改 AI：Claude）

### 42.1 任务、依据与范围

用户要求（2026-11-22）：Codex 已完成 CP4；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP5。起点 `compile-repair@812f8ea01`。审查对象：`evaluation/benchmark.py`、`core/provenance.py::compose_offsets`、`cli.py`，`tests/test_benchmark.py`，`cp4_v1` 的计数、分类替换、示例、精确还原与身份请求，CP4_REPORT、HANDOVER、DECISIONS、CHANGE_LOG §41、PROGRESS。

修改：`PROMPTS.md`（r2.16 → r2.17）；新增 `artifacts/cp4_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 4 节补注，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 42.2 实施方式和重要选择

- 0 纳入的五类：从 `benchmark_counts.json` 的 category_substitutions 看出 unbalanced_structure 与 declaration_error 的样本大多被归为 other、encoding 全部归为 parser_error_other。为区分“算子错”与“分类器错”，写 8 个最小夹具，在 0.4.24、0.5.17、0.8.0、0.8.38 上编译，并用模块自己的 `parse_diagnostics` 与 `classify_diagnostic` 分类。结论：右花括号与同名函数是分类器缺少模板（消息不以 Expected 开头；依赖命令行不输出的类型）；encoding 与 unimplemented_feature 是算子位置或写法不对（字符串内的非法字节、结构体数组复制才产生目标错误）。
- 分类器的影响范围：查 CP3 已保存的 other 模板，确认同样的消息出现在真实语料中（例如 17 个单元的右花括号消息、158 个单元的文件级函数可见性），所以修复分类器并重新汇总 CP3，而不只修基准。类型依据用 standard JSON（只用于定类，不改编译路径，与 r2.11 的结论不冲突）。
- 缺包依赖：它占真实失败 86%，没有基准样本会使 CP5 无法用真值评测。选择“把以相对路径引入的已知包目录改为包导入并删除文件”，而不是合成假包名：前者对应 CP5 离线库索引要处理的真实情形。
- 创建码：读身份请求，确认差异只在元数据 CBOR 的 IPFS 摘要。原路径重编只适用于精确还原；真实修复必然改变源字节，所以评分时按 solc 元数据格式规范化，graph.json 本身不改。

### 42.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 右花括号缺失 | 4 个版本都报 `Function, variable, struct or modifier declaration expected.`，模块归为 other | probe_operator_messages.json |
| 同名函数 | 0.5.17、0.8.0、0.8.38 报同名消息，模块归为 other | 同上 |
| 字符串内非法 UTF-8 | 0.4.24、0.5.17 `contains invalid UTF-8 sequence`，0.8.0、0.8.38 `Invalid character in string.`，模块归为 encoding；标识符内为 parser_error_other | 同上 |
| 嵌套动态数组参数 | 0.4.24、0.5.17 需要实验 ABI 编码器（other），0.8.x 编译成功 | 同上 |
| 结构体数组复制 | 0.4.24、0.5.17、0.8.0 UnimplementedFeatureError，模块归为 unimplemented_feature；0.8.38 成功 | 同上 |
| 真实语料 other 模板 | 含右花括号消息 17、同名函数 1、ABI 编码器 v2 5 + 5、文件级函数可见性 158、文件级常量 7 等 | cp3_binding_v1/failure_summary.json |
| 创建码差异 | 11,199 字节中只有末尾 53 字节 CBOR 的 IPFS 摘要不同 | cp4_v1/restoration_identity_request.json |

未证明：结构体数组复制开始支持的版本（审查环境没有 0.6、0.7 与大部分 0.8）；基础单元中含包目录子树的项目数；IR 含创建码常量的单元数（CP4.1 统计）。

### 42.4 用户批准、原文差异与待确认设计

- Codex 处理正确：精确还原首次失败即停、定位、经批准后原路径重编；迁移测试与分析器类别的处理都先经用户批准。
- 新发现：四个问题，见 42.2。分类表新增类别与评分规范化不改变已定决策，不需要新的用户批准。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 42.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 不能开始。顺序为 Codex 执行 CP4.1 → Claude 审查 → CP5。本轮提交并 push 到 `compile-repair`。


## 43. 2026-11-22 CompileRepair CP4.1 诊断清点与 WSL 启动故障（修改 AI：Codex）

### 43.1 任务、依据与范围

专用分支 `compile-repair` 已快进同步至 `e8ec530d81908b5f9cd592d3f1ecae89aa3e63a6`。已读 PROMPTS r2.17 全文、共享上下文 §4.1、§1.20、§4.6b、CP4 审查、交接和决策记录。本节记录 CP4.1 进行中的工作，以及用户要求优先排查的新命令启动超时。

工作树中的实现草稿位于 `toolchain/solc.py`、`evaluation/benchmark.py`、`evaluation/report.py`。手写输入清单位于 `tests/fixtures/cp4_1/diagnostics.json`。在 `artifacts/cp4_1_v1/` 中，清点和探针脚本为 `batch.py`、`preflight.py`、`preflight_supported.py`、`inventory_diagnostics.py`、`make_fixtures.py`、`oracle.py`、`probe_compilers.py`、`survey_packages.py`、`replay.py`。清点、授权和故障证据为 `inventory_diagnostics.log`、`old_other_templates.json`、`preflight_authorization.json`、`authorization.json`、`wsl_startup_diagnosis.json`。交接、决策、进度和 CP4 报告同步记录本检查点。

### 43.2 实施方式和重要选择

清点脚本对照基线中的分类器，逐条读取 CP3 有效结果及 CP4 的环境和选定版本收据，按 `diagnostic_template` 聚合旧 `other`。新重判脚本从原种子、原修改区间、文件字节及 SHA256 重建工作副本，并通过 `classify_record`、`primary_causes` 和 `classify_trigger` 计算结果。修正后的预检分别核对 96 个可信安装和 92 个受支持版本。首轮预检将两个数字等同，在首个编译调用前停止。

评分草稿为经过校验的 solc 元数据和项目文件改名保留单独的比较记录。编码算子草稿从 Solidity 字符串内部选取偏移。分类器已写入三个具名类别及历史内部异常的识别分支。上述改动的生产验收尚待运行。

### 43.3 实测与数据结论

清点覆盖 31,071 条 CP3 有测量的结果、17,432 条 CP4 环境结果和 11,560 次选定版本调用。三个范围内被旧分类器记为 `other` 的诊断出现次数分别为 13,321、59,569、3,004，合并去重得到 96 个模板。其中 1 个内部异常仅涉及 3 个 CP3 单元，另有 95 个模板已写手工输入。计数单位为诊断出现次数及模板，来源为 `old_other_templates.json`。

美东 08:31:46 与 08:34:10，两次新命令分别通过普通管道和终端启动，30.145 秒与 30.253 秒后返回 `Wsl/Service/0x8007274c`。这两个时刻的 Ubuntu 内核日志均记录 `hvs_probe → vmbus_open → vmbus_alloc_ring` 的 order-7 页分配失败。DMA32、Normal 两个内存区均无 512 KiB 或更大的连续空闲块。同一时段 `MemAvailable` 为 7,361,876 KiB，`oom_kill` 为 0，WSL 管理查询和已有 SSH 服务仍可响应。能定位到新通道的分配失败，形成碎片的具体工作负载仍无法确定。带时间的调用、日志摘录和空闲块计数见 `wsl_startup_diagnosis.json`。

### 43.4 用户批准、原文差异与待确认设计

2026-11-22，用户原话“同意按冻结的 92 版继续”“同意单列内部异常的历史证据”“同意旧样本按原始观测重判”。旧候选沿用已实测的原始观测，仅做重新分类。新增候选、须执行的精确还原以及迁移还原仍须实际运行。新命令发生超时后，用户要求“你先审查以下现在还存在超时吗，排查原因”。本次仅开展系统诊断，三项工程决定分别登记在两份授权中。

### 43.5 验收、资源、未执行事项与停止

96 个模板的原始清点已完成。92 版测量、95 个源码夹具的类型观测、17,432 个候选重判、新样本与图评分、双环境模块测试和 DFG v2 测试均未运行。CP4.1 尚未验收。费用 0 美元，下载、安装、训练、LLM 调用、系统重启和内核参数修改均为 0。现有用户 Bash 会话保留。文档检查收据为 `artifacts/cp4_1_v1/checkpoint_doc_check.json`。

文档检查已在 Windows 本机 Python 3.7 上运行仓库原有的 UTF-8 检查器，五份文档全部通过。交接与决策全文检查，其他三份检查本轮追加区间。生产验收仍待 WSL 命令启动恢复。

本地检查点提交在暂存前遇到 Git 工作树索引锁。本轮保留锁文件，检查点留在工作树。生产文件按仓库测试口径计数为 17，17 个模块文件及 9 个批次脚本通过 Python 3.7 语法检查。交付状态和最终文档校验见本批 checkpoint_delivery.json。

## 44. 2026-11-22 CompileRepair CP4.1 生产测量、真实包补样与迁移审查（修改 AI：Codex）

### 44.1 任务、依据与范围

按 PROMPTS r2.17 §4.6b 续做 §43 中断的工作。生产改动限于 toolchain/solc.py、evaluation/report.py、evaluation/benchmark.py。测试在 tests/test_cp41.py 和 tests/fixtures/cp4_1/。逐函数行数见 artifacts/cp4_1_v1/migration_stop_scope.json。采样、核验脚本与观测保存在同一新批次，逐项目源码、图及原始命令保存在仓库外。报告和交接入口见 CP4_REPORT.md、PROGRESS.md、docs/HANDOVER.md、docs/DECISIONS.md 与本批 README。

### 44.2 实施方式和重要选择

以 standard JSON 的实际类型、获批历史证据及可验证的同类消息给旧诊断归因。版本拒绝保留逐候选记录。D6 最终表沿用既有 route 与 change_level 词表，ABI coder 的无冲突 pragma 按 additive 处理，文件级成员仅在归属可证明时补附加作用域。按原种子及 SHA 读取已经实际发生的两阶段观测。新候选实际按生产流水线调用。项目装配先报告缺导入时，该阶段 solc 调用数为 0。

对比图时校验字节码末尾 CBOR 的完整结构与已知 solc 字段，保存每个样本的规范化标志。文件改名映射作用于节点、CFG 两端和调用目标。缺包样本保持包名与发布布局可证，首批 28 项与补充 86 项的并集同原种子分层抽样匹配。

### 44.3 实测与数据结论

95 份源码夹具运行 642 次 standard JSON，加上历史证据共核查 96 个模板，1 个模板保留 other。CP3 有历史测量的 31,071 项重新归因后，主因 other 从 36 到 0，任一候选含 other 的单元从 202 到 2。冻结的旧候选 17,432 项新增纳入 952，新增候选 1,922 项纳入 1,386，全量纳入 14,196 项。两个创建码阳性例按规范化比分别为 299/299、6/6。各数的原始表在 diagnostic_mapping.json、cp3_before_after.json、population.json 和 creation_*.json。

原 11,858 项重新评分、952 项新晋候选实编精确还原全部满分。首轮新候选完成了 1,274 项全部评分。两批新候选实际写出 1,281 份精确还原图和 9 份迁移图，停止时在途进程结束后均已按 SHA 登记，见 migration_stop_inventory.json。用户授权的 114 个缺包候选全部触发，迁移完整通过数仍待确认。

### 44.4 用户批准、原文差异与待确认设计

用户原话“同意交叉核对及条件口径”“同意补齐 86 项并保留原收据”。审查的 0.8.38 命令只请求 ABI，生产要求字节码。对同一审查夹具的两次调用得到不同结果。92 个支持版本在标准生产字节码设置下均拒绝目标结构体操作，选中的基础单元必须满足候选版本均在实测拒绝集合且未启用 via-IR。两份授权见 struct_codegen_authorization.json、package_sampling_authorization.json。

cp3_15167、cp3_15136 分别因文件迁移后 Slither 自动编号改变而停止。对两组封存图进行只读核验，所见差异均可由双向唯一的编号映射解释。扩展迁移评分仍待用户确认。已保存原评分、原图、只读核对明细和 migration_counter_review.json。

### 44.5 验收、资源、未执行事项与停止

production 测试为 1,016 通过、6 跳过。mando 测试为 553 通过、469 跳过。DFG v2 为 2,653 通过、9 条告警。最终版本的局部测试为 201 通过。生产文件共 17 个，354 项冻结 DFG 代码引用匹配，底稿见 final_tests/、package_focused_tests.log、migration_stop_scope.json。运行使用 CPU，费用 0 美元。安装、下载、LLM 调用和训练均为 0。

WSL 的 VMBus 建连曾在高负载下再次超时。保留的原生 Bash 完成了生产实验。对已读取的历史任务数据做有限文件缓存回收提示后，三次独立普通新命令均在 0.41 秒内成功。系统重启和内核参数写入均为 0。缓存提示与恢复的因果关系尚无独立对照。停止的原因及待确认项为迁移评分。

六份中文文档通过仓库 doc_check。交接、决策与批次说明按全文检查，CHANGE_LOG、PROGRESS 和 CP4_REPORT 校验原先封存的前缀后检查此次追加区间。最终校验明细见 artifacts/cp4_1_v1/migration_stop_doc_check.json。


## 45. 2026-11-22 CompileRepair CP4.1 缺包迁移与全量验收（修改 AI 为 Codex）

### 45.1 任务、依据与范围

从 compile-repair 的 `0f690e6f` 继续 PROMPTS r2.17 §4.6b。代码只修改 evaluation/benchmark.py 和 tests/test_cp41.py。之前 128 份已封存的批次文件再次核验 SHA。续作结果在 artifacts/cp4_1_v1/migration_continuation，项目源码、原始图和编译器 stdout 继续存放在仓库外。全量基准、编译器快照和控制组均沿用原计划。

### 45.2 实施方式和重要选择

文件迁移的原分单列保存。先验证节点源文件、字节偏移、声明和文件改名，再逐条核对 SlithIR。TMP、REF、TUPLE 的定义与使用须形成同族双向映射，还须排除源码标识符、转义字面量和相邻字面量碰撞。全图检查带类型的操作、两端点、调用文本及重数。生成名称有差异时，只允许导入路径引起的源码字节变化。Yul 的文件编号额外要求原始编译器 stdout、AST、源文件清单及实际源码区间均相符。

首次收据核对把 Slither 的绝对输入路径与样本的相对路径直接比较，在调用工具前停止。按记录的项目根解析并逐一校验 124 个文件之后，复用 9 对已有图。数组分配曾因赋值号前有两个空格而漏认两个定义，随后按实际格式识别，图比较仍保留空格。最终汇总初稿误以为一张图只会尝试一个编译器。按 D5 和实际调用日志，8 个单元的两个位置都尝试了 0.8.0、0.8.1、0.8.2，最后一版通过。最终脚本逐项对照版本计划、调用记录和每次返回码，保留了原汇总的报错日志。[路径核验](../artifacts/cp4_1_v1/migration_continuation/initial_receipt_check.json) · [汇总程序](../artifacts/cp4_1_v1/migration_continuation/final_acceptance_v2.py)

### 45.3 实测与数据结论

19,354 个候选中的 14,196 个纳入项逐项匹配，精确还原全部通过，200 个对照的原收据验证通过。114 个缺包样本有 DAppSCAN 112 项与 Trace_repo 2 项。迁移时 53 项原分满分，另有 61 项经生成名称核验后满分。61 项涉及 TMP、32 项涉及 REF、2 项涉及 TUPLE。其中 1 项还用 solc 证实了 Yul 源文件编号。所有迁移均核对了完整声明、节点、CFG 和调用。四份通过清单分别为 21、19、11、63 行。105 对新图实际使用 242 次 solc、210 次 Slither，另有 2 次核对 Yul AST 的 solc 调用。旧 9 对图复用了既有 18 次 solc 和 18 次 Slither 的收据。[全量统计](../artifacts/cp4_1_v1/migration_continuation/acceptance.json) · [逐项表](../artifacts/cp4_1_v1/migration_continuation/packages.tsv)

### 45.4 用户批准、原文差异与待确认设计

用户分别批准 TMP/REF 的严格核验、TUPLE 的相同核验、仅针对 Yul 源文件编号的最多 4 次见证，以及数组分配空格识别修正后的续跑。每次变更前的停点、用户原话和所授权的未完成范围均写入 DECISIONS、批次请求及授权文件。复用已通过和已生成的图，后续运行只补缺项。本步验收已完成，下一步为独立审查。[决定与证据清单](../artifacts/cp4_1_v1/migration_continuation/README.md)

### 45.5 验收、资源、未执行事项与停止

局部测试 253 通过。最终 production 模块 1,068 通过、6 跳过。mando 模块 605 通过、469 跳过。mando 的 DFG v2 为 2,653 通过、9 条告警。生产文件 17 个，354 项 DFG 代码身份逐项一致。本次只使用本地 CPU，费用 0 美元，安装、下载、训练和 LLM 调用均为 0。相对本轮检查点，benchmark.py 增 315 行、删 5 行，test_cp41.py 增 290 行。CP4.1 相对 e8ec530d 的逐函数差异见 final_scope.json。[测试记录](../artifacts/cp4_1_v1/migration_continuation/definition_continuation/suites/) · [范围核验](../artifacts/cp4_1_v1/migration_continuation/final_scope.json)

WSL 的新通道数次因 512 KiB 连续页分配失败而超时。保留的原生 Bash 执行了全部生产测试和样本。晚间完成一次临时内存整理，随后仍观测到一次普通新命令超时。验收完成后对已封存的 684 个只读结果文件发送缓存释放提示，最后四次新命令用时 0.312–0.359 秒，均返回 UID 1000。各措施对恢复的独立贡献尚未测量。[WSL 实测](../artifacts/cp4_1_v1/migration_continuation/wsl_recovery.json)

六份中文文档通过仓库 doc_check。HANDOVER、DECISIONS 和批次 README 按全文检查，CHANGE_LOG、CP4_REPORT 和 PROGRESS 先核对检查点原字节，再检查各自本轮的追加内容。逐份字节数和汉字数随本批封存。[文档检查](../artifacts/cp4_1_v1/migration_continuation/doc_check.json)


## 46. 2026-11-22 CompileRepair CP4.1 审查与方案 r2.18（修改 AI：Claude）

### 46.1 任务、依据与范围

用户要求（2026-11-22）：Codex 已完成 CP4.1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP5。起点 `compile-repair@6950dc7b8`。审查对象：`toolchain/solc.py`、`evaluation/benchmark.py`、`evaluation/report.py` 的差异，`tests/test_cp41.py`，`cp4_1_v1` 的 operators.tsv、cp3_before_after.json、same_name_types.json、struct_codegen_crosscheck.json、migration_continuation/acceptance.json，CP4_REPORT 的 CP4.1 节、HANDOVER、DECISIONS、CHANGE_LOG §43–§45、PROGRESS。

修改：`PROMPTS.md`（r2.17 → r2.18）；新增 `artifacts/cp4_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 46.2 实施方式和重要选择

- 计数：用 operators.tsv 与 acceptance.json 逐项核对加减关系。
- 分类器：用 CP4.1 的分类器重新运行 CP4 审查的 8 个夹具。
- 结构体数组：Codex 的报告与审查 CP4 时的结论不同，因此在审查环境分别输出 abi 与 bin 复核，确认审查当时的探针只请求 abi，生产路径要求字节码，以 Codex 的结论为准。
- 迁移核验：读 `_counter_correspondence`、`_verified_migration`、`_guard_migration_sources` 与 `score_graphs`，确认核验严格，但只在有文件改名映射时运行。为判断这是否影响普通修复，写端到端探针：用模块的 `graph_facts` 与 `score_graphs` 比较“原位置恢复被删函数”与“把同一函数插到合约开头”。
- 处理方案的选择：考虑过在每个函数内按首次出现顺序重新编号。没有采用，因为同一函数内新增语句也会改变首次出现顺序；而沿用已批准的核验规则、只用 kept 节点推导一一对应，不受新增与删除节点影响，故意错误也仍被检出。

### 46.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 候选与纳入 | 19,354 = 17,432 + 1,922；14,196 = 11,858 + 952 + 1,386；1,386 = 114 + 511 + 761 = 1,300 + 86 | operators.tsv、acceptance.json |
| 分类器 | 删除右花括号 4 个版本 → unbalanced_structure；嵌套动态数组 0.4.24、0.5.17 → abi_coder_required；同名函数 0.5.17 以后 → syntax_error | probe_operator_messages_cp41.json |
| 结构体数组 | 0.8.38 输出 abi 时 rc 0，输出 bin 时 rc 1（legacy 代码生成不支持） | struct_copy_bin.json |
| 测试 | test_cp41.py 与 test_benchmark.py 共 272 项通过 | 审查环境 pytest |
| 编号平移 | 原位置恢复 kept 1.0；插到开头 kept 0.5，g() 的 TMP_0…2 → TMP_4…6、REF_0、1 → REF_1、2 | probe_counter_shift.json |

未证明：真实修复中编号平移的发生比例（CP4.2 的移动自检给出）；Yul switch 名称在普通修复中的平移情况。

### 46.4 用户批准、原文差异与待确认设计

- Codex 处理正确：遇到结构体数组、迁移编号与 Yul 源编号时停下、给出证据并经批准后处理；没有改用合成包名。
- 审查自身的错误：CP4 审查 README 第 3 条“0.8.38 编译成功”只基于 abi 输出，已在 cp4_1_review_v1 更正（不改旧证据目录）。
- 新的设计点：把已批准的迁移核验规则推广到所有评分（DECISIONS 记为 Claude 建议）。规则本身已经用户批准，推广只改变适用范围；如用户不同意，CP4.2 只保留 raw 分数并在 CP5 报告中标出受影响样本。
- 已知限制：declaration_error 0 个基准样本。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 46.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_1_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 不能开始。顺序为 Codex 执行 CP4.2 → Claude 审查 → CP5。本轮提交并 push 到 `compile-repair`。


## 47. 2026-11-22 CompileRepair CP4.2 保留节点的 SlithIR 评分（修改 AI 为 Codex）

### 47.1 任务、依据与范围

基线为 compile-repair 的 `30df6664`。依据 PROMPTS r2.18 §1.21、§4.1 和 §4.6c，以及 Claude 的 cp4_1_review_v1 夹具。生产只改 evaluation/benchmark.py。测试增加 tests/test_cp42.py，并将 tests/test_cp41.py 中普通修复的旧预期更新为同时检查原分及核验分。全部新结果位于 artifacts/cp4_2_v1。依赖的历史源码、图、修复编辑和封存记录按 SHA256 读取。

### 47.2 实施方式和重要选择

score_graphs 在普通修复上先算原分，再从共同存在、按偏移映射对齐的保留节点推导 TMP、REF、TUPLE 的定义与使用。若任一节点的事实、指令、类型、操作数或双射发生冲突，该项整体采用原分并给出原因。检查所有输入文件中的标识符和解码字面量。删除的真值起点与重新插入的新节点分别进入 lost 与 added，名称核验只改变保留节点及其关系的计分。文件改名时继续保留全图证明。部分修复无法通过全图证明时，仍可为它的保留节点给出实际得分。Yul 使用既有 solc 见证约束。调用方可通过 raw 和 counter_correspondence 复查结果。

全量迁移汇总初稿要求每个证明字段与历史记录的数值完全相同。第 5 行停止，初批的证明曾只清点 TMP 和 REF，后来才加入 TUPLE。复核初批全部 21 行，7 行另有未改名元组。按初批实际覆盖范围重新推导原字段，保留已有的 5 行，再评分余下 109 行，同时记录前后两个计数。逐字原分与全图验收分逐项一致。[汇总证据](../artifacts/cp4_2_v1/migration_summary.json)

### 47.3 实测与数据结论

14,196 个精确还原和 114 个迁移均与 CP4.1 的分数相同。普通修复的审查夹具原位恢复时状态 identical，将函数插到主体开头时原 kept 为 0.5，核对五个名称后 kept、CFG、调用比例均为 1。22 个错误修复与缺节点负例均检出，两个只改变计数名用法的错误也被检出。[精确还原](../artifacts/cp4_2_v1/exact_summary.json) · [夹具](../artifacts/cp4_2_v1/review_fixture.json) · [负例](../artifacts/cp4_2_v1/negative.json)

首轮第 60 个单元的参数注释遗留在旧位置，solc 拒绝新的声明关联。核对 200 个原始声明，有 45 个带相邻 NatSpec。按授权保留 46 项首轮有效收据，重新测量带完整注释的函数和当时未测的单元。第 76 项 CP3 单元 00291 的创建码实际有 32 个摘要字节不同，两个 EVM Keccak 值也不同。正式 kept 261/264、调用 132/133。第 79 项 CP3 单元 21529 的三个 Yul switch 名称中的起点各移动两字节，正式 kept 616/622，592 条边和 244 个调用相同。前 79 份中 77 份三个比例均为 1。两份低分都保留全部原始事实与分母。[79 项检查点](../artifacts/cp4_2_v1/checkpoint_79.json)

### 47.4 用户批准、原文差异与待确认设计

用户于 2026-11-22 先后确认“保留迁移全图结果，另列 kept 核验”“同意连同注释移动并限定续跑”和“同意单列实质差异，继续 124 项”。第三项允许保留可以证明来自嵌入创建字节码摘要的原分。三个决定及各自的审查凭据都在本批次中。Yul 新停点来自起点字段，CP4.1 只核验文件序号。根据 §4.6c 保留 Yul 原分，并单独征求将该类别计入移动实验最终验收的意见。[已定事项](DECISIONS.md) · [Yul 源码段证据](../artifacts/cp4_2_v1/observed_yul_positions.json)

### 47.5 验收、资源、未执行事项与停止

两套环境从仓库根执行模块回归，production 1,073 项通过、6 跳过，mando 608 项通过、471 跳过。mando 的 DFG v2 回归有 2,653 项通过、9 条告警。代码范围核对为 17 个生产文件、354 个 DFG 引用。CPU 本地运行，费用 0 美元，训练与 LLM 调用均为 0。第 79 项编译、D3 与图哈希核验通过。余下 121 项在本检查点尚未执行，CP5 待独立审查。[最终套件](../artifacts/cp4_2_v1/final_tests/) · [范围](../artifacts/cp4_2_v1/final_scope.json)

本检查点六份中文文档经 doc_check 通过。CHANGE_LOG、PROGRESS 与 CP4_REPORT 在检查前核对基线的完整字节前缀，检查本次追加区间；交接、决定和新批 README 检查全文。79 个已测单元的原始 kept 有 38 个低于 1。收据和本地代码、文档哈希在本批检查点封存文件中。[文档检查](../artifacts/cp4_2_v1/checkpoint_doc_check.json)

**第 79 项检查点后的最终验收。** 用户于 2026-11-22 回复“同意保留 Yul 原分并继续剩余 121 项”。正式评分规则沿用 §4.6c，保留前 79 项编译、D3 和图收据，余下单元在 position_continuation 单独目录运行。200 项固定 dev 函数移动全部编译并通过 D3，其中 198 项保留节点、CFG 边和调用全部相等。逐字 kept 低于 1 的有 81 项。核验后仍低于 1 的包括 1 项嵌入创建字节码变化、1 项 Yul 源码起点变化。所有低分均按实际数值计入 200 项分母。项目单元共 87 个。按语料计数为 DAppSCAN 44、MANDO 44、SOChecker 21、Trace_CVEs 5、Trace_on_chain 43、Trace_repo 43。生成名称核验状态为 identical 119 项、verified 79 项、rejected 2 项。三个回归套件均在最终生产代码上运行。临时副本只作诊断。独立审查待执行。详见本批验收、四份授权和 CHANGE_LOG §47.1–47.4。[验收](../artifacts/cp4_2_v1/acceptance.json) · [低分明细](../artifacts/cp4_2_v1/measured_differences.json) · [最后一次续跑授权](../artifacts/cp4_2_v1/yul_authorization.json)

最终六份文档经 doc_check 通过，检查范围与前一检查点相同。四批移动实验共保存 214 份 solc 收据和 213 份 Slither 收据，按运行顺序分别为 60/59、30/30、3/3、121/121。首轮一项 NatSpec 关联错误在运行 Slither 前被编译器拒绝。214 包含首轮和重新带上注释的测量，最终分母为 200 个不同单元。14,196 个精确还原及 114 个迁移只从封存图重算。CPU 本地验收结束，独立审查待进行。[文档检查](../artifacts/cp4_2_v1/doc_check.json) · [最终封存](../artifacts/cp4_2_v1/seal.json)


## 48. 2026-11-22 CompileRepair CP4.2 审查与方案 r2.19（修改 AI：Claude）

### 48.1 任务、依据与范围

用户要求（2026-11-22）：Codex 已完成 CP4.2；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP5。起点 `compile-repair@1bb69b7ff`。审查对象：`evaluation/benchmark.py` 的差异，`tests/test_cp42.py`、`tests/test_cp41.py` 的改动，`cp4_2_v1` 的 moves_final.jsonl、observed_yul_positions.json、migration_summary.json、migration_review.json、authorization.json，CP4_REPORT 的 CP4.2 节、HANDOVER、DECISIONS、CHANGE_LOG §47、PROGRESS。

修改：`PROMPTS.md`（r2.18 → r2.19）；新增 `artifacts/cp4_2_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 48.2 实施方式和重要选择

- 读差异时注意到 `_score_facts` 新增的分支：未破坏且字节被修复删除的节点计入 lost，不进入 kept。它满足 r2.18 移动自检的字面要求，但适用于所有评分。为判断后果，写端到端探针：修复原位恢复被删的 `h()`，同时删除未破坏的 `u()`；在 `30df6664b`（CP4.2 之前）的只读工作树与当前代码上分别打分。
- 处理方案：不把移动自检的需要放进主指标，而是恢复 CP4 的 kept 定义，另加 removed_by_repair 与只用于诊断的 surviving 块。这样“删除原代码”在主指标中下降，移动自检仍能用 surviving 判断编号核验是否正确。
- Yul switch：读 observed_yul_positions.json，名称中的起点是源码字节偏移；评分已有把真值起点映射到修复坐标的组合映射，用同一映射对齐是可核验的，不需要新的假设。
- 创建码哈希常量：哈希无法从修复后的数据还原，规范化没有可靠依据，接受用户已作的决定。

### 48.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 修复删除未破坏函数（5 个节点） | CP4.2 之前 kept 2/7、边 1/6、调用 1/2、missing_kept 5、lost 2；之后 kept 2/2、边 1/1、调用 1/1、missing_kept 0、lost 7；exact 都为 false | probe_repair_deletes_kept.json |
| CP4.1 审查夹具 | 插到开头的修复 kept 2/2 | ../cp4_1_review_v1/probe_counter_shift.py 重跑 |
| 移动自检 | moves_final.jsonl 中 lost 等于 expected_moved_nodes，即被移动函数的节点经新分支计入 lost | moves_final.jsonl |
| Yul 起点 | 三个名称起点各 +2（15484 → 15486 等），长度与其余部分不变 | observed_yul_positions.json |
| 测试 | test_cp42.py、test_cp41.py、test_benchmark.py 共 275 项通过、2 项跳过 | 审查环境 pytest |

未证明：真实语料中含 Yul switch 的基础单元数；CP5 修复中删除原代码的发生比例。

### 48.4 用户批准、原文差异与待确认设计

- Codex 处理正确：两项低分停下、给出证据并按用户决定保留实测；迁移按用户决定保留全图结论并另列 kept 核验。
- 方案自身的错误：r2.18 §4.6c 的“计为 lost”应只用于移动自检的判断，没有限定范围，导致通用规则改变。以 §4.6d 为准。
- 需用户确认：Yul switch 起点对齐改变了 CP4.2 中“单列原分”的处理；用户把 CP4.3 交给 Codex 即视为同意，否则 CP4.3 只做第 1 节。
- 已知限制：declaration_error 0 个样本；创建码哈希常量。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 48.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_2_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 不能开始。顺序为 Codex 执行 CP4.3 → Claude 审查 → CP5。本轮提交并 push 到 `compile-repair`。


## 49. 2026-11-23 CompileRepair CP4.3 修复删除评分和 Yul 源码起点（修改 AI 为 Codex）

### 49.1 任务、依据与范围

用户于 2026-11-22 转交 CP4.3。专用分支 `compile-repair` 执行 `git pull --ff-only origin compile-repair` 后为 `09a8355e`。先读 §4.1，再核对 r2.19 全部修订、§1.22、§3.7、§3.10、§4.6d、交接第 0–5 节、决定、CP4.2 报告及变更 §47–48，并查阅 CP4.2 的审查探针与收据。生产文件为 evaluation/benchmark.py，测试为 tests/test_cp43.py 与 tests/test_cp42.py。证据在 artifacts/cp4_3_v1，另追加 CP4_REPORT、PROGRESS、交接、决定和本节。既有批次按原始哈希核对。[输入及审查文件 SHA256](../artifacts/cp4_3_v1/acceptance.json)

### 49.2 实施方式和重要选择

修复中被删的完好字节影响两个结果。主指标保留真值节点和相关边、调用作为分母，诊断块仅选取仍能映射的原始节点。对应字节存在但图节点缺失时，两种分母都保留它。解析到声明的调用用文件、合约和函数全名识别目标，诊断时排除原节点字节全部消失的函数。文本型调用依据调用点的 IR 校验。四类修复事实分别通过 removed_by_repair、missing_kept、lost、added 追查。完整真值来自既有图，范围对应来自 core/provenance.py 的 compose_offsets。[生产文件与源码哈希](../artifacts/cp4_3_v1/scope.json)

Yul 名称通过与节点相同的组合偏移映射对齐。对起点平移要求完整单段、源内容相同、后缀与操作数相同、具有定义和使用，并核对源码标识符和解码字面量。变更源编号复用 CP4.1 的 AST 核验。历史负例使用 SHA 已核对的 CP4.2 驱动与原有工具收据。默认沙箱第一次查询 WSL Git 时返回 E_ACCESSDENIED，随后在受管 WSL 权限下完成核对。工具层因终端输入过大拒绝过一次编辑，该输入未执行，随后将分母与 Yul 的局部修改分开写入工作树。实验验收均在首轮完成。

### 49.3 实测与数据结论

审查中的错误修复现为 kept 2/7、CFG 1/6、调用 1/2；5 个修复删除与 2 个破坏区丢失可独立计数。手写 Yul 夹具中 97 → 152 的起点映射通过，两种伪造起点均拒绝。200/200 项主 kept 均小于 1，修复删除节点合计 933 个，每项均等于预期的移动节点数。199/200 项的存活节点、CFG 边和调用三个比例均为 1。14,196 个精确还原的主指标和 exact 均与 CP4.2 一致，名称状态全部为 identical。114 个迁移的主指标、raw 和全图结果也逐项相同。两组的 removed_by_repair 全部为 0。 对原 22 个错误修复、新删函数错误，以及既有缺节点控制分别核验。cp3_21529 存活 kept 为 622/622，cp3_00291 为 261/264。三个重算任务的耗时以进程输出日志创建至汇总写成的秒数估计，具体计数、采样身份和收据在验收文件中。[数据汇总](../artifacts/cp4_3_v1/acceptance.json) · [错误修复](../artifacts/cp4_3_v1/negative.json)

### 49.4 用户批准、原文差异与待确认设计

按 §48.4 对用户转交 CP4.3 的确认方式，Yul 起点可以通过可核验的源码映射得到核验分，同时记录原分。创建字节码摘要的既有决定继续生效。移动自检按 r2.19 分别报告主指标及存活诊断；相对于 r2.18 的处理原因见 §48。执行中采用了规范要求的判据，无新增设计待决定。[授权](../artifacts/cp4_3_v1/authorization.json) · [决策](DECISIONS.md)

### 49.5 验收、资源、未执行事项与停止

两套环境执行 `python -B -m pytest -x -q -p no:cacheprovider compile_repair/tests`，mando 执行相同命令的 `scripts/DFG/dfg_v2/tests` 目标，分别使用独立 basetemp。production 1,076 项通过、6 项跳过，mando 609 项通过、473 项跳过，DFG v2 2,653 项通过、9 条告警。生产文件 17 个，354 项 DFG 引用相同。CPU 本地运行，费用 0 美元，未安装或下载依赖，训练与 LLM 调用均为 0。CP4.3 本地提交，进入独立审查。CP5 尚未开始。[实际测试命令、日志和退出状态](../artifacts/cp4_3_v1/suites/) · [科学证据封存](../artifacts/cp4_3_v1/evidence_seal.json)

六份中文文档已通过 `doc_check --expect-cjk`。对 CP4_REPORT、PROGRESS 和 CHANGE_LOG 先校验起始提交的字节前缀，再检查追加区间；HANDOVER、DECISIONS 和新批次 README 检查全文。移动、精确还原、文件迁移三次只读重算分别约用 9、364、8 秒，计时依据和 SHA 均在 acceptance.json。两套模块测试与 DFG v2 用时分别为 130.99、53.14、225.64 秒。[文档核验](../artifacts/cp4_3_v1/doc_check.json) · [最终封存](../artifacts/cp4_3_v1/seal.json)


## 50. 2026-11-23 CompileRepair CP4.3 审查与方案 r2.20（修改 AI：Claude）

### 50.1 任务、依据与范围

用户要求（2026-11-23）：Codex 已完成 CP4.3；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP5。起点 `compile-repair@868d814c9`。审查对象：`evaluation/benchmark.py` 的差异（`_edges_and_calls`、`_mapped_switch`、`_align_switches`、`score_graphs`、`_score_facts`），`tests/test_cp43.py`，`cp4_3_v1` 的 moves.jsonl.gz、exact_summary.json、migration_summary.json，CP4_REPORT 的 CP4.3 节、HANDOVER、DECISIONS、CHANGE_LOG §49、PROGRESS。

修改：`PROMPTS.md`（r2.19 → r2.20）；新增 `artifacts/cp4_3_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 50.2 实施方式和重要选择

- 重跑 CP4.1、CP4.2 审查的两个探针，核对 kept 分母、removed_by_repair、surviving 与名称状态。
- Codex 的 Yul 夹具只有一个 switch；审查另写含嵌套 switch 的夹具，并加入“汇编块内加注释”和“改错 case 常量”两种修复。前者被整体放弃，提示对应规则可能过严。
- 为确认是否普遍，写第二个探针：中性插入之外再改动另一个函数中的一个常量。结果 kept 由 7/7 跌到 3/7，原因是 `_counter_correspondence` 遇到第一个不符节点即抛出。这是 r2.18 §4.6c 写明的规则，Codex 照此实现，问题在方案。
- 处理方案：结构不同的节点本来就不相等，排除它们不会使任何节点被错误地计为相等；冲突与无法核验定义的名称只排除相关节点。被计为相等的节点仍须在一个全局一一对应下逐条相同，保证与原规则相同。源码中出现涉及名字时仍整体放弃。迁移的全图核验按用户决定不变。

### 50.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 修复删除未破坏函数 | kept 2/7、边 1/6、调用 1/2、missing_kept 5、removed_by_repair 5、lost 2、exact false；surviving 1 | cp4_2_review_v1 探针重跑 |
| 插到开头夹具 | kept 2/2，removed_by_repair 0，verified | cp4_1_review_v1 探针重跑 |
| Yul 嵌套 switch | 插到开头 11/16 → 16/16（2 个 switch）；加注释 11/16（node_facts_differ）；改错常量 11/16（switch_span_not_preserved） | probe_yul_switch.json |
| 一个节点真实改动 | 中性插入 7/7；加改动 3/7（rejected）；原位恢复加同一改动 6/7（rejected，无改名） | probe_partial_change.json |
| 移动重算 | 200 项；removed_by_repair 合计 933，逐项等于 expected_moved_nodes；surviving 为 1 的 199 项；cp3_00291 为 rejected | moves.jsonl.gz |
| 测试 | test_cp43/42/41、test_benchmark 共 276 项通过、4 项跳过 | 审查环境 pytest |

未证明：CP5 真实修复中“插入并改动个别节点”的发生比例。

### 50.4 用户批准、原文差异与待确认设计

- Codex 处理正确：按 r2.19 实现并逐项验收；用户转交即确认 Yul 起点对齐。
- 方案自身的错误：r2.18 §4.6c“只要有一个 kept 节点不满足，就整体不改名”过严；以 §4.6e 为准。
- 新设计点（DECISIONS 记为 Claude 建议）：按节点排除与 partial 状态；用户转交 CP4.4 即视为同意。
- 已知限制：declaration_error 0 个样本；创建码哈希常量。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 50.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_3_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 不能开始。顺序为 Codex 执行 CP4.4 → Claude 审查 → CP5。本轮提交并 push 到 `compile-repair`。


## 51. 2026-11-23 CompileRepair CP4.4 局部名称对应与评分比例性（修改 AI 为 Codex）

### 51.1 任务、依据与范围

用户指示从 §4.1 共享上下文开始实施 CP4.4。分支 `compile-repair` 快进同步后已是最新提交 `8739c653`。在已读 r2.19 的基础上核对了 r2.20 全部修订、§1.23、§4.6e、交接第 0–5 节、决定、变更 §49–50 及 CP4.3 的两类审查探针。生产只修改 evaluation/benchmark.py，修改 tests/test_cp42.py、tests/test_cp43.py，新增 tests/test_cp44.py。新产物为 artifacts/cp4_4_v1。本次另更新 CP4_REPORT、PROGRESS、HANDOVER、DECISIONS 及本节。[冻结输入 SHA256](../artifacts/cp4_4_v1/acceptance.json)

### 51.2 实施方式和重要选择

先用既有评分器和生产工具链生成两个审查夹具的八份真值或修复图，保存源码、solc、Slither 和图的哈希；实施后在同一组图上比较。普通评分只用节点事实、IR 数量与逐条非生成名称内容均相同的节点推导对应。冲突的两侧一起退出，定义丢失的使用节点也须退出；重算至稳定后，仅在参与节点及对应的文本调用上替换名称。源码碰撞使整项退回原分。Yul 的单次起点与范围核验复用同一个函数，文件迁移仍使用原来的全图流程。P 的各类移出数互斥，首次移出时计数。[逐函数变更](../artifacts/cp4_4_v1/scope.json)

比例性夹具将三个入口字节在破坏阶段标记，并在每个方案中原位恢复，从而使每个 kept 节点都含有可真正改动的常量。另用跨节点定义与使用图验证局部冲突、级联移出、反转遍历顺序、源码转义字面量碰撞。长度变化和创建码的疑问均先记录证据再征求用户意见。[比例性](../artifacts/cp4_4_v1/proportionality.json) · [夹具与负例](../artifacts/cp4_4_v1/fixture_facts.json)

### 51.3 实测与数据结论

普通夹具 A/B/C 为 7/7、6/7、6/7，含注释和错误 case 的 Yul 三方案为 16/16、16/16、14/16。比例性对照为 3/3，三个单点改动均为 2/3，两个跨节点错误均为 2/6。既有 22 个错误修复与缺节点对照全部检出。14,196 个精确还原和 114 个迁移的历史指标全部匹配，迁移全图证明逐项相同。200 项移动中只有 cp3_00291 的部分指标改善，两个创建码差异仍保留。该样本的存活 kept 为 262/264，合约哈希输入的变化仍可见。移动、精确还原、迁移的只读重算分别用时 7.264、343.289、4.374 秒。[验收汇总](../artifacts/cp4_4_v1/acceptance.json) · [移动比较停点](../artifacts/cp4_4_v1/moves_summary.json)

### 51.4 用户批准、原文差异与待确认设计

按 §50.4，用户转交 CP4.4 即确认普通评分采用逐节点排除。实际编译表明 Yul 注释只使 3 个节点的源码长度增加 20 字节，类型与 IR 相同。用户回复“保留主指标，另列长度变化节点”。全部移动项按 §4.6e 比较后，单元 cp3_00291 的三个 TMP 改名恢复一个节点和一个调用，主 kept 由 261/267 到 262/267，存活调用由 120/121 到 121/121。比较在原门槛以退出码 2 停止。用户回复“接受这一个差值，继续验收”。最终核验精确限制到这个单元、这些指标和已保存的证据；已有评分和停点文件均可追查。[决策及证据哈希](../artifacts/cp4_4_v1/acceptance_authorization.json)

### 51.5 验收、资源、未执行事项与停止

从仓库根运行两套环境的 `python -B -m pytest -x -q -p no:cacheprovider compile_repair/tests`，另由 mando 运行同样命令的 `scripts/DFG/dfg_v2/tests` 目标，每次使用独立 basetemp。生产 1,080 通过、6 跳过，108.27 秒；mando 612 通过、474 跳过，45.71 秒；DFG v2 2,653 通过、9 条告警，191.22 秒。生产文件 17 个，354 个 DFG 引用一致。历史重算直接使用封存图，训练、LLM 调用及本次费用均为零。CP5 待独立审查后再开始。[套件结果](../artifacts/cp4_4_v1/suites/) · [科学证据封存](../artifacts/cp4_4_v1/evidence_seal.json)

六份中文文档经 `doc_check --expect-cjk` 检查通过。CP4_REPORT、PROGRESS 和本文件先与起始提交核对原始字节前缀，再检查追加区间；HANDOVER、DECISIONS 与新批次 README 检查全文。封存同时覆盖 4 份生产或测试代码交付文件及 5 份模块文档。[文档检查](../artifacts/cp4_4_v1/doc_check.json) · [最终封存](../artifacts/cp4_4_v1/seal.json)


## 52. 2026-11-23 CompileRepair CP4.4 审查与方案 r2.21（修改 AI：Claude）

### 52.1 任务、依据与范围

用户要求（2026-11-23）：Codex 已完成 CP4.4；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP5。起点 `compile-repair@2355afad1`。审查对象：`evaluation/benchmark.py` 的差异（`_switch_proof`、`_ordinary_node_names`、`_prune_name_nodes`、`_ordinary_correspondence`、`score_graphs`），`tests/test_cp44.py` 与 CP4.2、CP4.3 测试的断言改动，`cp4_4_v1` 的 moves.jsonl.gz 与 movement_difference.json，CP4_REPORT 的 CP4.4 节、HANDOVER、DECISIONS、CHANGE_LOG §51、PROGRESS。

修改：`PROMPTS.md`（r2.20 → r2.21）；新增 `artifacts/cp4_4_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 1 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 52.2 实施方式和重要选择

- 重跑 CP4.3 审查的两个探针，并逐项对比 CP4.3 与 CP4.4 的 200 项移动结果。
- 读 `_prune_name_nodes`：冲突时冲突双方名称所在的节点全部移出，之后这些节点用原样比较。考虑到编号平移时字面相同并不代表读同一个值，写手写图探针（不调用编译器，以便精确控制名称）：定义节点平移正确、使用节点保留旧名。四个场景各写明真正正确的节点数，与评分对比。
- 处理方案：冲突本身无法从图上判断哪一方错，但每个生成名称在函数中只定义一次，定义处给出它的映射。以定义为锚，使用处与锚不一致即不相等，与节点顺序无关，也不需要原样比较。没有锚的名称只在不与已锚名称冲突时按原名接受，覆盖未平移的情形。被改节点定义、其他节点使用的名称在平移时无法核验，使用节点也计为不相等；这是数据流上的真实依赖，报告中单列。
- 原样比较兜底从 CP4.2（r2.18 §4.6c）起就在，高估不是 CP4.4 引入的；CP4.4 的按节点推导本身没有错误。

### 52.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 正确平移 | 3/3，verified | probe_stale_name.json |
| 一个旧名使用节点 | 2/3（正确 2），但被计为相等的是错误的使用节点，定义节点被计为不相等 | 同上 |
| 三个旧名使用节点 | 4/5（正确 2），高估；原分为 3/5 | 同上 |
| 未平移的错误使用 | 2/3（正确 2），identical | 同上 |
| CP4.3 审查探针 | 7/7、6/7、6/7；Yul 16/16、16/16、14/16 | 重跑 |
| 移动重算 | 200 项中只有 cp3_00291 改变（kept 262/267、调用匹配 133）；surviving 为 1 的 199 项 | cp4_3_v1、cp4_4_v1 的 moves.jsonl.gz |
| 测试 | test_cp44 到 test_benchmark 共 279 项通过、5 项跳过 | 审查环境 pytest |

未证明：真实修复中出现旧名使用节点的频率（真实图由 Slither 重新编号，这类情形只在修复改变数据流时出现）。

### 52.4 用户批准、原文差异与待确认设计

- Codex 处理正确：按 r2.20 实现；cp3_00291 的差值按原门槛停下，经用户核对后接受。
- 方案自身的错误：r2.18 §4.6c 与 r2.20 §4.6e 规定移出的节点“按原样比较”，在编号平移时不可靠；以 §4.6f 为准。
- 新设计点（DECISIONS 记为 Claude 建议）：以定义为锚；用户转交 CP4.5 即视为同意。
- 已知限制：declaration_error 0 个样本；创建码哈希常量。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 52.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_4_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 不能开始。顺序为 Codex 执行 CP4.5 → Claude 审查 → CP5。本轮提交并 push 到 `compile-repair`。


## 53. 2026-11-23 CompileRepair CP4.5 定义与使用一致性评分（修改 AI 为 Codex）

### 53.1 修改与范围

按 r2.21 §4.6f 修改 `evaluation/benchmark.py`，以候选节点中的唯一定义建立生成名称对应。删除旧的冲突节点迭代排除函数。Kept 节点使用显式核验结果，记录结构差异、名称不一致、争议及定义改变后无法核验的使用。变动函数及行数见 CP4_REPORT 的 CP4.5 和 `artifacts/cp4_5_v1/continuation/scope.json`。

### 53.2 排查经过与解决方法

冻结中性夹具中有三处 REF 的定义与显式写回被旧正则同时识别为定义。用户批准区分后，中性插入为 7/7。首轮历史重算又发现同节点数组初始化和删除会使用未带写回标记的左值。678 个精确还原样本的真值图与复原图 SHA256 完全相同，争议仍导致降分。逐项取回两侧指令，核对数组引用的先前绑定及删除操作数指向的容器。依用户第二次批准，在普通图识别这两个具体形式，补充真绑定、错用和重复定义探针，在新批次重验。

### 53.3 实测与证据

旧名审查探针按原序和反序均准确选出 3、2、2、2 个节点。六个生产图修复为 7/7、6/7、6/7 和 16/16、16/16、14/16。22 个编译或输入类故意错修复及一个缺节点对照均被检出。首轮差异为移动 4 项、精确还原 678 项；最终 200 项移动、14,196 项精确还原、114 项文件迁移逐项对齐 CP4.4。首轮原因按单元及变异 SHA256 可查。见 `cp4_5_v1/{moves,exact}_causes.jsonl.gz`、`continuation/fixture_comparison.json` 和 `acceptance.json`。

### 53.4 用户决定与原文差异

用户原话为“同意区分引用定义和显式写回（推荐）”及“批准限定识别和新批次重验（推荐）”。前者限定处理显式写回，后者只覆盖能验证先前绑定的数组初始化和删除。逐处使用和多定义仍受定义锚约束。首次比较按文档门槛停止并单独封存，没有将差异样本从分母中移除。两项批准、证据哈希分别在根批次和 continuation 的 authorization.json。D19 和 D9/D10/D12/D13 的状态沿用。

### 53.5 验收、资源与交接

生产环境模块测试 1,102 项通过、6 项跳过；mando 634 项通过、474 项跳过；DFG v2 2,653 项通过、9 条告警。生产文件 17 个，仅 1 个变动；354 个冻结 DFG 引用一致。历史比对读取已有收据和图，模块测试使用本地工具，CPU、0 美元。无安装、下载、LLM 调用或训练。六份中文文档的检查结果及逐文件 SHA256 见 doc_check.json 和 seal.json。本轮为本地提交，提交身份用 Git 历史中的 CP4.5 前缀核对。等待独立审查。


## 54. 2026-11-23 CompileRepair CP4.5 审查与方案 r2.22（修改 AI：Claude）

### 54.1 任务、依据与范围

用户要求（2026-11-23）：Codex 已完成 CP4.5；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；全部核实后进入 CP5。起点 `compile-repair@0b5fd600b`。审查对象：`evaluation/benchmark.py` 的差异（`_bound_reference_write`、`_ordinary_definition`、`_ordinary_node_names`、`_definition_anchors`、`_ordinary_correspondence`、`score_graphs`、`_score_facts`），`tests/test_cp45.py` 与 CP4.2–CP4.4 测试的断言改动，`cp4_5_v1` 与 `continuation/` 的 moves、exact、migration 结果与 write_semantics_request.json，CP4_REPORT 的 CP4.5 节、HANDOVER、DECISIONS、CHANGE_LOG §53、PROGRESS。

修改：`PROMPTS.md`（r2.21 → r2.22：修改说明、1.25 节、D22 与 D23、4.6g 节 CP5）；新增 `artifacts/cp4_5_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 2 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 54.2 实施方式和重要选择

- 核验：在 CP4.5 评分器上重跑 CP4.1–CP4.4 审查的全部探针；读名称核验输出确认被判为不一致的是旧名使用节点；读 `score_graphs` 确认相等计数取自核验集合，不再原样比较；逐项比较 CP4.4 与 CP4.5 续跑的 200 项移动，检查 14,196 项精确还原。
- 写回形式：Codex 按观察到的写法识别。判断为可以接受：未覆盖的写法只会低估；但精确还原只覆盖抽样单元，所以 CP5 先在全部基础单元上做真值自比。这一步不需要编译，代价很小。
- CP5 提示的选择：
  - 先测量后下载。包有 158 个前缀，前 10 个占去重导入的 83%（cp3_binding_v1），但单元级覆盖率、清单文件与锁文件的存在情况都没有统计；下载范围与版本身份规则依赖这些数据，所以第 1 节测量后停下请用户决定。
  - 版本身份（D22）：D6 路线要求“可确定版本/身份”时才确定性补全，而语料“几乎没有构建配置”。没有清单时，代理掌握的信息并不比离线索引多，所以建议 T3 在兼容检查通过时也由规则补全，标记 inferred，由下游按 D1 决定是否使用；多个候选时的选择规则在 dev 划分上用基准真值确定。这是新的设计点，交用户确认。
  - 代码位置：索引的构建、校验与读取放在 rules/dependencies.py（3.10 节已有此文件），以后 rag 只读索引的磁盘格式，不导入 rules，因而不新增文件；生产文件 17 → 18。
  - standard JSON 解包放在第 2 步（D6 路线为 deterministic、改动等级 none），沿用 r2.13“编译用命令行”的结论，只把 remapping 与已支持的编译设置映射过来。

### 54.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 旧名场景 | 3/3、2/3、2/5、2/3，均等于真正正确的节点数 | rerun_review_probes.json |
| 其余探针 | 7/7、6/7、6/7；Yul 16/16、16/16、14/16；删除未破坏函数 2/7；插到开头 2/2 | 同上 |
| 移动 | 200 项与 CP4.4 逐项相同 | cp4_4_v1、cp4_5_v1/continuation 的 moves.jsonl.gz |
| 精确还原 | 14,196 项 exact、identical | continuation/exact.jsonl.gz |
| 测试 | test_cp45 到 test_benchmark 共 301 项通过、5 项跳过 | 审查环境 pytest |
| 包分布 | 158 个前缀、13,264 个去重导入；前 5 个占 70%，前 10 个 83%，前 40 个 96% | cp3_binding_v1/failure_summary.json |

未证明：单元级的包覆盖率、清单与锁文件的存在比例、离线索引能补全的单元数（CP5 第 1 节测量）。

### 54.4 用户批准、原文差异与待确认设计

- Codex 处理正确：首轮差异按门槛停下，两次请求批准，保留首轮结果并另建续跑。
- 新决定：D22（建议）与 D23（待授权），CP5 第 1 节后停下请求。
- 已知限制：declaration_error 0 个样本；创建码哈希常量；写回形式覆盖待第 0 节核验；源码含生成名称时退回原分。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 54.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp4_5_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP4 系列结束，可以开始 CP5；CP5 第 1 节之后须停下等用户决定 D22、D23。本轮提交并 push 到 `compile-repair`。


## 55. CP5 项目组装、依赖版本与传输检查点（2026-11-23，修改 AI 为 Codex）

### 55.1 任务、依据与范围

在 `compile-repair@26f44492` 执行 PROMPTS r2.22 §4.6g。先按 §4.1 核对前置图和现有语料，再开发项目组装、离线依赖补全与缺相对文件搜索。产物单列于 `artifacts/cp5_v1/`，详细验收见 `CP5_REPORT.md`。

### 55.2 实施方式和重要选择

`toolchain/project.py` 将包装中的全部源单元交给同一 solc 和 Slither，校验源路径与内容，为项目内唯一目录生成 remapping。`rules/dependencies.py` 构建并校验只读索引，按包清单约束、导入闭包、pragma 和导入符号选择候选。第 4 步把改写限定在导入路径的原字节区间。`pipeline.py` 记录候选、每轮错误数及接受条件，按实际成功编译器比较候选。单文件的本地搜索范围限于调用方提供的源码。新增 `cli dependency-index` 与基准汇总接入。具体函数、行数和 SHA 见 `checkpoint_audit.json`。

### 55.3 实测与数据结论

16,136 个真值图自比全部 exact。9,144 个不同单元进入测量，五类主因涉及其中 9,138 个。8,469 个有待补包的单元中，73 个的依赖全部能由锁文件确定，8,396 个至少有一项须推断。410 个包装含 5,829 个源。真实 MANDO 回归的 843 个成功图与 v5 字节完全相同，均在第 1 步结束。3 个历史失败状态一致。基准 2,264 个样本的成员和划分已核对。四个开发探针中包装达到 exact，其余三个保留未修复。全部四项的 removed_by_repair 为 0。计数见 `measurement.json`、`mando_regression.json`、`benchmark_inventory.json` 和 `dev_probes.jsonl`。

### 55.4 用户批准、原文差异与待确认设计

用户分别确认“同意 D22 三级规则（推荐）”“批准限定的元数据查询（推荐）”“批准这 172 版及硬上限（推荐）”。授权分别记录在 `authorization.json` 与 `d23/authorization.json`。172 份官方 HEAD 均未提供压缩长度。D23 以逐包与累计上限约束下载和解包。280 个包装设置 optimizer，当前共享参数白名单与 §4.6g 的映射要求冲突。限定修改验证器的建议见 `optimizer_request.json`，等待用户确认。首批下载在 HTTP 状态前断开。剩余 23 版的限定续传另见 `d23/transport_stop.json`，同样等待确认。

### 55.5 验收、资源、未执行事项与停止

生产环境模块 1,126 项通过、6 项跳过，mando 模块 651 项通过、481 项跳过，DFG v2 为 2,653 项通过、9 条警告。生产模块 18 个，DFG 的 354 个代码引用均与基线一致。官方元数据传输 3,132,219 字节，已收取的 149 份归档共 80,004,759 字节，重新核验全部双哈希。完整索引、开发策略冻结、基准全量评分与外部语料重跑未运行。LLM 调用 0，费用 0 美元。测试命令与执行时间见 `implementation_checks/`、`dfg_tests.json` 和 `checkpoint_audit.json`。

文档检查覆盖 CP5_REPORT、PROGRESS、CHANGE_LOG、DECISIONS、HANDOVER 和本批 README，共 6 份，全部通过。两份只追加的文档同时核对了提交前旧文本的逐字节前缀。初次及写入本段后的完整结果分别保存在 `checkpoint_doc_before_result.json`、`checkpoint_doc_check.json`。

候选选择测试完成后按待提交代码再次运行 MANDO。18 个生产文件与运行 seal 的 SHA 全部吻合，843 个成功图逐字节相同，三个历史失败状态一致。证据见 `final_mando/summary.json`。补入最终回归收据后，六份文档再次通过检查，最终结果见 `checkpoint_doc_final.json`。

两个 MANDO 控制台日志中包含编译器原样引用的既有源码行，行首空格与 Tab 触发 Git 空白检查。交付采用无损 gzip，经解压逐字节比对，两份原件均保留在本地。原 SHA 与压缩文件 SHA 见 `log_archives.json`。交付版全部文件通过暂存区检查，文档终检见 `checkpoint_doc_delivery.json`。


## 56. 2026-11-23 CompileRepair CP5 检查点审查与方案 r2.23（修改 AI：Claude）

### 56.1 任务、依据与范围

用户要求（2026-11-23）：Codex 已完成 CP5；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP6。起点 `compile-repair@3c7ae7ee5`。Codex 的报告写明这是检查点。审查对象：`rules/dependencies.py`（`relative_repairs`、`_release_sources`、`dependency_choices`）、`toolchain/project.py` 与 `pipeline.py` 的差异，`tests/test_cp5.py`，`cp5_v1` 的 self_summary、historical_status、measurement、measurement_units、d23_download_request、d23/download.jsonl、transport_stop、optimizer_request、multi_input_probe、dev_probes，CP5_REPORT、HANDOVER、DECISIONS、CHANGE_LOG §55、PROGRESS。

修改：`PROMPTS.md`（r2.22 → r2.23：修改说明、1.26 节、D22/D23 状态、D24、3.3 节第 3a 条注明 D24 例外、4.6h 节 CP5.1）；新增 `artifacts/cp5_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 56.2 实施方式和重要选择

- 数据：核对第 0 节与测量的加减关系；逐包比较批准清单与已下载收据。
- 代码：读第 3、4 步的主要函数与 pipeline 的选择循环；“closest”规则的距离在 pipeline 中计算，确认三条规则都有实现与对照测试。
- 第 4 步：读 CP4 的算子，确认缺相对文件算子删除文件、io_error 算子改为不存在的路径；结合两个开发探针的 `unresolved_imports`，判断第 4 步在基准上没有可评测样本。D6 路线写“删除或移动”，因此补“移动”变体。
- 第 3 步：用下载清单与测量的待补包计算组合上限。计划中曾考虑“剩余错误都在项目文件里就停止尝试其他版本”，没有采用：发布版的选择会改变项目自身文件中的错误（新版本删除了项目调用的函数时，错误落在项目文件），按位置判断会漏掉可以成功的版本。改为先测量、再按测量设上限。
- 规则选择：dev 只有 8 个缺包基准样本，加入 dev 划分真实单元的成功数作为主要依据；73 个 T1 单元来自同一项目，只作参考。
- optimizer：图来自 AST，不受 optimizer 影响；104 个包装使用 viaIR，不开 optimizer 更容易出现 Stack too deep。包装自带的是作者的设置，同意 Codex 的方案，限定只用于包装自带设置，作为 3.3 节第 3a 条的例外（D24）。
- 测试：`tests/test_cp5.py` 在收集时读取用户本机编译器目录与授权文件，审查环境无法运行（已知的可移植性限制）；临时路径映射后仍因编译器清单与官方发布不一致而失败，已撤除，以 Codex 记录为准。

### 56.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 自比 | 16,136/16,136 exact、identical | self_summary.json |
| 测量 | 8,469 = 73 + 0 + 8,396；9,308 个主因计数去重 9,138，加 6 个只在候选中出现，共 9,144 | measurement.json |
| 下载 | 批准 172 个（20 个包，每包至多 12 或 13 个代表版本）；已核对 149 个 | d23_download_request.json、d23/download.jsonl |
| 组合上限 | 单元待补包中在清单内的：1 个包 5,139、2 个 1,101、3 个 228、4 个 35；上限 ≥ 100 的 783 个、≥ 1,000 的 184 个、最大 13,824 | cp5_review_v1/combination_bound.json |
| 开发探针 | 包装 cp3_00775 exact（kept 分母 0，418 个节点在破坏区间内全部恢复）；缺相对文件与 io_error 为 unresolved_imports；pragma 冲突为 no_candidate_compiler | dev_probes.jsonl |
| 算子 | 缺相对文件为 delete_file；io_error 为 `file:cp4_nonexistent_dependency.sol` | evaluation/benchmark.py |

未证明：第 3 步实际编译的组合数；真实缺相对文件单元中项目内有同名候选的比例；三条规则的优劣（CP5.1 测量）。

### 56.4 用户批准、原文差异与待确认设计

- Codex 处理正确：第 1 节后停下请求 D22、D23 与元数据查询；下载失败即停、没有部分文件；optimizer 与方案冲突时停下请求。
- 方案自身的不足：4.6g 没有规定第 3 步的候选上限、第 4 步的评测样本与包装样本的评分口径；以 4.6h 补齐。
- 新决定：D24（建议，转交 CP5.1 即确认）；续传在 D23 范围内。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 56.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp5_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP6 不能开始。顺序为 Codex 执行 CP5.1 → Claude 审查 → CP6。本轮提交并 push 到 `compile-repair`。

## 57. CP5.1 依赖组合、文件移动与完整索引（2026-11-23，修改 AI 为 Codex）

### 57.1 任务、依据与范围

在 `compile-repair` 上以 `git pull --ff-only origin compile-repair` 同步至 `5fe7671f`，按 PROMPTS r2.23 §4.1、§4.6g 和 §4.6h 续作。参照 `cp5_review_v1/README.md` 与 `combination_bound.json`。生产改动位于 `toolchain/solc.py`、`rules/dependencies.py`、`pipeline.py`、`evaluation/benchmark.py`、`evaluation/report.py`。测试为 `tests/test_settings.py`、`tests/test_cp51.py`。新实验、脚本与每种停点收据在 `artifacts/cp5_1_v1/`。详细结果追加到 `CP5_REPORT.md`。

### 57.2 实施方式和重要选择

共享设置验证器接受包装声明的优化器及 uint32 的 runs，保留原诊断逻辑。项目修复按一次实际进入 solc 的依赖组合记一个序号，多版和设置重试共用该序号。达到上限后遇到下一个需要编译的组合才记截断，清单保留已尝试版本。锁版本参照保留清单中的包别名，遮蔽锁文件与范围。新增移动算子固定目标目录，保存内容 SHA、原路径和新路径，将两次物理路径对应到 CP4.1 的文件改名评分。包装统计直接使用恢复节点、丢失节点、新增节点和 exact。复用的评分函数、改动函数及行数按输入提交核对，见 `checkpoint_audit.json`。

### 57.3 实测与数据结论

归档 172/172 通过双哈希。索引验证覆盖 13,073 份 Solidity 文件。9,138 个主因目标分为开发 2,316 和测试 6,822，来源分组在 CP4 的 16,136 份基础记录上逐项相符。移动算子按语料抽取 400 项，全部触发且全部通过精确逆操作。真实缺相对文件 412 项中 137 项有唯一同名候选，I/O 的 28 项中有 8 项。对照 `population.json`、`moved_summary.json`、`path_census.json`。缺包开发基准每种规则均有 7/8 成功，23 份库文件中最新与最近各恢复 1 份，最旧恢复 2 份，见 `package_dev_summary.json`。

### 57.4 用户批准、原文差异与待确认设计

D24 和 23 版续传按转交提示确认。TLS 中断后按用户原话“批准仅续传这 5 版一次”限定范围。一次新 WSL 启动超时，自动审批拒绝直接改用已有会话。取得“允许已运行会话按上述保护执行一次”后，执行时因遗漏代理环境变量，停在第一个版本的预登记，尚无网络调用。离线复核归档与五个代理目标后，取得“批准按已核验配置执行一次”，新批次各发一次 GET 并全部成功。三项授权的来源、日期、作用域及旧现场哈希已写入 DECISIONS 和批次文件。`@chainlink/contracts` 的精确锁版本加入代表抽样后为 13 版，采用 D23 已批准的具体清单。

实测边界见 `assembly_only_example.json`。`cp3_09664` 的最新优先规则在第 3 步物化 1,280 个仍缺导入的组合，solc 调用 0 次，用时 148.84 秒。一次候选减少错误，随后组装通过 D3。K 维持原文的实际编译计数，组装耗时单列。

### 57.5 验收、资源、未执行事项与停止

生产回归 1,147 通过、6 跳过，mando 环境 667 通过、486 跳过，DFG v2 2,653 通过、9 条警告。MANDO 的 843 张图与 v5 相同，3 项历史失败一致。源码引用核对 354 项，生产 Python 文件保持 18 个。命令、耗时、工作树 SHA 与环境见 `checkpoint_audit.json`。共下载 8,882,233 个新增压缩字节，总存量 88,886,992 字节。CPU 本地执行，LLM 调用 0，费用 0 美元。

开发集的生产 Slither 报告 readOracle 生成 IR 中断，cp3_19463 的三份成功收据仍有 D3(a)/(b) 和源码节点。已核对原始日志、三个图 SHA256 及 Slither 捕获异常的代码。选版和测试集在决定前暂停。用户确认“沿用 D3，单列 IR 缺失（推荐）”，随后恢复原流程。报告单列观察范围，计数和生产图代码沿用冻结定义。证据见 cp5_1_v1/partial_ir_review.json 和 partial_ir_decision.json。

开发测量中断时，6,940 份收据与冻结计划前缀一致。cp3_30233 / oldest 已有 31 份编译器收据，另 7 个组合尚未开始。后续启动器健康检查出现 Wsl/Service/0x8007274c，退出原因尚未确定。用户批准核验和封存 6,940 份后只补齐八项。旧的调用记录与新单元耗时分开统计。见 development_interrupt.json、development_continuation/authorization.json。

经用户批准，仅重启 Ubuntu-22.04。重启前复核四个空闲会话并保存完整前缀。Windows 和 WSL 的代理出口与直连阻断均按活动连接验证，普通用户无法读取 Windows 全部出站例外。首次用户服务启动缺少会话总线，尚未启动任何观测；改用已有 tmux 的专属套接字后，WSL 网络探针通过，受保护的续作进程按原清单启动。见 development_continuation/recovery_summary.json。

独立运行器遗漏了已登记的 TREE_SITTER_LIB_DIR，两个解释器的首轮回归在同一个等价性测试停止。冻结库与 CP0 SHA256 一致。用户批准在新目录各补跑一次完整套件，所有后续子进程沿用该环境变量。选版证据、参数、图判据与首轮收据继续保留，见 test_environment_resume_v2/。

基于已封存的移动清单与正式基准收据，逐项核验 400 个目标。189 个 D3 成功单元的导入都指向实际移动位置。另列图事实与编辑邻近范围对 exact 的影响，评分与开发规则均沿用原定义。见 verify_moved_targets.py 和 moved_path_outcomes.json。

首轮生产与 mando 的两份 pytest 日志在第 24、25、28 行带有 pytest 输出的行尾空格，原始 SHA256 与续跑申请逐一吻合。交付时以 Git 暂存字节复核这两份日志，其余文件照常检查空白。

全量运行时新 WSL 命令再次返回 0x8007274c，独立的 /bin/true 在 30.14 秒后报告同一错误，内核仍记录 Relay 等待 vsock。原 tmux 中两个分片继续写入。通过共享目录恢复只读核验，并核对 Windows Git 所见分支、基线提交、仓库身份设置和生产文件哈希。该通道可在保留现有会话的条件下完成本地交付。详见 test_environment_resume_v2/launcher_recurrence.json。

真实外部语料按冻结的项目组划分后，开发集通过 D3 的单元为 1,131/2,316，测试集为 4,749/6,822。14 个达到组合上限的单元都在测试集。逐项匹配入口 SHA256 后，开发集 2,316 项的 D3 成败均与最旧优先的无上限测量一致。两张原始表的哈希与分组计数见 external_split_summary.json。

最终验收采用冻结后的默认设置。正式默认规则为 `oldest`，K=21。 真实语料 5880/9,138 通过 D3，其中 14 个触发编译组合上限。基准开发集 236/550、测试集 1004/2114 通过编译和 D3。 外部全量与基准合计核验 24766 个候选轮，包含被拒绝的轮次。其中新增文件编辑 267614 次，导入字符串改写 1029 次。未改变的输入按原始文件 SHA 复核。各阶段和逐项调用收据索引见 `*_provenance.json`、`invocation_seals.json`。 两个分片按冻结输入顺序合并，逐行核验 9,138 个不同身份。最终测试与生产文件变化见 `final_audit.json`，详细表格见 `CP5_REPORT.md`。本轮本地提交，下一步为独立复核。


## 58. 2026-11-23 CompileRepair CP5.1 审查与方案 r2.24（修改 AI：Claude）

### 58.1 任务、依据与范围

用户要求（2026-11-23）：Codex 已完成 CP5.1；核实数据，判断已处理的问题是否正确，对错误或未解决的问题制定计划交给 Codex；问题解决并对照项目目标核实后才进入 CP6。起点 `compile-repair@41c685fca`。审查对象：CP5_REPORT 的 CP5.1 节；`rules/dependencies.py::relative_repairs` 与 pipeline 的第 4 步接入；`evaluation/benchmark.py::relative_move_site`；`cp5_1_v1` 的 packed/benchmark.jsonl.gz、packed/real_full.jsonl.gz、path_census.jsonl、moved_path_outcomes.json、partial_ir_*.json；HANDOVER、DECISIONS、CHANGE_LOG §57、PROGRESS；Slither 0.11.6 的 IR 生成异常处理。

修改：`PROMPTS.md`（r2.23 → r2.24：修改说明、1.27 节、D24 状态、D25、4.6i 节 CP5.2）；新增 `artifacts/cp5_1_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 58.2 实施方式和重要选择

- 移动样本：按状态、原因与接受步骤统计 400 个样本；读 `relative_move_site`，确认算子把文件原样移到 `.cp5_moved/`，没有改写被移动文件自己的相对导入。结合 3.1 节的接受条件，推测改写导入方后错误数不减少而被拒绝；7 个两轮第 4 步成功的样本与此相符。没有逐项读取仓库外的修复记录（审查环境没有），因此作为待诊断项，并规定诊断与推测不符时以诊断为准。
- 真实语料：把 path_census 的候选与 real_full 的结果按单元对齐，发现 102 个至少一个缺失相对导入有唯一符号候选却未通过 D3，说明漏修不只是基准问题。链式改写是对 3.1 节接受条件的有限扩展：链结束时仍须错误数严格减少，否则整条回滚。
- 包装：统计 950 个样本的 exact 分解，550 个 raw 迁移评分为 exact，被迁移名称核验以 graph_metadata_differ 拒绝；审查环境没有图文件，所以要求先列出差异字段，涉及语义时停下。
- 部分 IR：读 Slither 源码，合约函数 IR 生成的 AttributeError 会把合约标记为 is_incorrectly_constructed，顶层函数只记日志；两个信号都可以逐图记录。为保持 MANDO 图字节不变，只写入结果记录。是否改 D3 由用户决定（D25）。
- 规则选择：oldest 与另两条只差 1 个单元，但 73 个 T1 参照中 oldest 选中锁版本 70 个、另两条 8 个，方向一致，接受。

### 58.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 移动样本 | 成功 189（第 4 步一轮 182、两轮 7）；未修复 211（第 4 步未接受 194、接受一轮后仍未解析 17）；no_compatible_candidate 32 | outcome_tallies.json |
| 真实缺相对文件 | 412 个中：全部缺失相对导入都有唯一符号候选且通过 D3 27；同类未通过 35；部分有唯一候选通过 2、未通过 67；没有唯一候选 281（其中通过 D3 13）；合计 412 | 同上 |
| 包装 exact | 400 exact；550 raw 迁移 exact 但 graph_metadata_differ | 同上 |
| 规则 | 开发集 1,130 / 1,130 / 1,131；T1 参照选中锁版本 8 / 8 / 70 | CP5_REPORT、policy.json |
| 外部语料 | 5,880 / 9,138；缺包主因 8,454 → 2,804 | real_full_summary.json、external_summary.json |
| Slither | `log_incorrect_parsing` 设置 is_incorrectly_constructed；顶层函数失败只记日志 | slither/solc_parsing/slither_compilation_unit_solc.py 第 818–846 行 |

未证明：移动样本与真实单元漏修的逐项原因；包装元数据差异的字段；部分 IR 的比例。

### 58.4 用户批准、原文差异与待确认设计

- Codex 处理正确：传输、环境与测试环境问题逐次停下并请求批准；保留中断现场；规则在测试集之前冻结。
- 方案自身的不足：4.6h 的移动算子没有同时更新被移动文件的导入；以 4.6i 的 v2 为准。
- 新设计点：链式改写与文件级 exact 邻域（Claude 建议，用户转交 CP5.2 即确认）；D25 待定。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 58.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp5_1_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP6 不能开始。顺序为 Codex 执行 CP5.2 → Claude 审查 → CP6。本轮提交并 push 到 `compile-repair`。


## 59. 2026-11-24 CompileRepair CP5.2 相对导入链、文件级评分与部分 IR 测量（修改 AI 为 Codex）

### 59.1 任务、依据与范围

本轮在 `compile-repair` 上以 `fba94f1d` 为起点，先同步分支，阅读 PROMPTS r2.24 §4.1、§1.27、§3.1、§4.6i 及上一轮报告、审查、决定与交接。任务包括漏修归因、移动算子 v2、有限的第 4 步改写、文件破坏评分、标准 JSON 包装身份和生产 Slither 的部分 IR 观测。历史证据的哈希和文档追加边界登记在 `artifacts/cp5_2_v1/baseline.json`。语料用于评价能够处理后续项目的规则，划分、选版和离线依赖策略继承已冻结的方案。

### 59.2 实施方式和重要选择

代码集中在 `rules/dependencies.py`、`pipeline.py`、`evaluation/benchmark.py` 与 `toolchain/slither.py`，增加测试 `tests/test_cp52.py`。第 4 步逐条证明选中导入已解析到预期的物理文件，仅在新入闭包的文件中继续处理新出现的缺失相对导入。工作副本和补丁溯源随整条链提交或回滚，链长上限为 4，清单分别记录链起点和每次试探的错误数。v2 移动对被移动文件的出向相对导入按字节重定位；文件级 exact 从真值闭包读取引用受损文件的导入字面量。生产 Slither 使用本次调用的局部日志处理器统计顶层函数错误，并在构造结束后移除。合约标记和计数进入结果收据。

### 59.3 实测与数据结论

逐项诊断 211 个旧移动失败与 102 个真实失败。移动失败中 180 个与移入文件自身的出向导入有关，其中 141 个符合继续条件。真实失败中四类原因分别有 12、59、4、27 个单元。各自的候选、排除原因、轮次哈希和逐项类别见 `diagnosis.jsonl`、`diagnosis_details.jsonl`、`filter_breakdown.json`。1,464 份历史结果按同一图和修复重新评分，旧移动 exact 为 1→181 / 400，包装为 400→950 / 950，缺包为 2→2 / 114。原有和新评分成对保存于 `benchmark_scores.jsonl`。面向外部语料的冻结全集为 9,138 项，其中缺相对文件或 I/O 错误的并集为 424 项，其余 8,714 项逐个核对 D3 和图 SHA256。原分母与 CP5.1 的成功数取自 `external_population.json`。

400 个 v2 样本全部触发并精确逆向还原，363 项实际修复通过 D3，359 项达到新邻域 exact。旧移动样本的 D3 通过数为 CP5.1 的 189/400 与 CP5.2 的 279/400；真实缺相对文件的 D3 通过数为 CP5.1 的 42/412 与 CP5.2 的 44/412。其余 8714 个外部单元的 D3 和图 SHA256 逐项相同。 全量 D3 为 5882/9,138。部分 IR 检出的单元为真实开发集 4/1131、基准成功样本 0/1240、MANDO 0/843、CP3 基础抽样 0/1000。各自的合约实例数、顶层函数计数和全图分数见 CP5_REPORT 的 CP5.2 节与 acceptance.json。

### 59.4 用户批准、原文差异与待确认设计

用户批准对包装单文件做有限身份转换并保留原分。WSL 恢复、按原收据定位、封存源码后的回归续跑和 711 次历史参数补编均有独立授权。WSL 单独重启后实测两侧代理及直连阻断；后来个别新启动器再次超时，既有计算保持运行，原生启动方式和共享目录读取完成了复核。17 份移动收据指向最终接受轮次，核对其哈希与顶层记录相同后按登记位置读取。首轮生产用例在复制 benchmark.py 后发现工作树已更新，18 个副本均匹配封存值。另一次 IR 清单预检把导入来源路径当作工作副本路径，首个 Slither 调用前停止。独立核验全部 3,371 份清单后，按用户批准的范围在新目录续作，保留首轮数据。D25 仍待用户结合实测比例决定。

### 59.5 验收、资源、未执行事项与停止

production 回归通过 1,155 项、跳过 6 项；mando 通过 671 项、跳过 490 项；DFG v2 通过 2,653 项。843 份 MANDO 成功图等于 v5，354 个 DFG 引用与冻结值相同，生产文件保持 18 个。四个生产文件改动 278 行新增、38 行删除；见 code_audit.json。CPU 运行、无下载、无 HGT 训练、无外部 LLM 调用，费用 0 美元。文档按各自追加边界执行 doc_check，初验 6/6 通过。最终复核的命令、逐文件结果及 SHA256 见本批 final_doc_check.json。


## 60. 2026-11-24 CompileRepair CP5.2 审查、CP5 完成与工作方式变更（修改 AI：Claude）

### 60.1 任务、依据与范围

用户要求（2026-11-24）：审查 Codex 完成的 CP5.2，不正确则及时更正并先完成 CP5；从此改为 Claude 直接在 GitHub 上修改代码与测试，一次完成一个阶段，前一阶段完成并确认正确后才进行下一阶段；先评估在 GitHub 上完成编码的条件是否充分，需要下载可以直接授权；考虑是否有时间限制并合理划分阶段；代码遵守工程规范；每一小步照样写 PROMPTS、交接与变更记录。起点 `compile-repair@35310dca2`。审查对象：CP5_REPORT 的 CP5.2 节，`pipeline.py`、`rules/dependencies.py` 的差异，`cp5_2_v1` 的 v2_summary、old_move_recoveries、诊断与包装记录，HANDOVER、DECISIONS、CHANGE_LOG §59、PROGRESS。

修改：`PROMPTS.md`（r2.24 → r2.25）；新增 `artifacts/cp5_2_review_v1/`；记录：本节、`docs/HANDOVER.md`（开头、第 0、1 节重写，第 5 节加路径，第 6 节新记录）、`docs/DECISIONS.md`（历史 3 行）、`PROGRESS.md`。没有修改模块代码与已有产物。

### 60.2 实施方式和重要选择

- 审查：读链式改写的实现，确认验证、限长与整条回滚；核对报告各表的加减关系与产物中的计数。
- 不为旧移动算子扩大 exact 邻域：它的缺陷在算子本身，v2 已按真实移动的写法构造，基准以 v2 为准。
- 执行环境评估（实测）：`nproc` 为 2，内存 7 GB，可写磁盘约 13 GB；`binaries.soliditylang.org` 被出口代理拒绝，GitHub 发布与公开仓库的 git 读取可用，npm 注册表可用；审查环境已有的 38 个 solc 中 37 个与仓库保存的官方索引（cp0_compiler_install_v1/official_release_index.json）SHA256 相同，0.4.26 的 GitHub 静态构建与官方 linux-amd64 构建不同，因此官方二进制改从 ethereum/solc-bin 仓库读取；没有 LLM 密钥；生产代码中 `evaluation/survey.py` 与多数测试写死用户本机路径。

### 60.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| v2 移动 | 363 = 83 + 280；exact 359 = 83 + 276 | continuation/v2_summary.json |
| 旧移动重跑 | 189 → 279，新增 90 项与恢复清单一致 | old_move_recoveries.json |
| 外部语料 | 5,880 → 5,882；其余 8,714 个单元不变 | CP5_REPORT |
| 编译器 | 37 / 38 与官方索引相同；0.4.26 不同 | official_release_index.json 与审查环境的二进制 |

未证明：用户本机语料与 GitHub 当前版本是否逐字节相同（CP6.0 按 CP3 记录的输入 SHA 核对）。

### 60.4 用户批准、原文差异与待确认设计

- 用户新决定：工作方式与下载授权（见 DECISIONS）。
- 待用户决定：D25。根目录的 HANDOVER.md 与 docs/training_changes_2026-10-07.md 仍按此前的约束不改，模块记录继续写在 compile_repair/docs；如用户要求同步根目录文档，另行确认。待确认：D19。D9/D10 待确认，D12/D13 待定。

### 60.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp5_2_review_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：CP5 完成。CP6 之前需要用户决定 D25，并完成 CP6.0（执行环境与测试可移植性）。本轮提交并 push 到 `compile-repair`。


## 61. 2026-11-24 CompileRepair CP6.0：D25（D3(c)）与执行环境（修改 AI：Claude）

### 61.1 任务、依据与范围

用户要求（2026-11-24）：按审查建议实施 D25；Claude 在 GitHub 写代码并核验无误后写出运行步骤，用户拉取后由 Codex 在本机运行；完成后更新相关文档，注明由 Claude 修改。起点 `compile-repair@5f8a7ef81`。

修改：`toolchain/slither.py::run_slither`（D3(c)）、`toolchain/solc.py::classify_slither`（slither_partial_ir）；新增 `tests/test_cp60.py`；新增 `artifacts/cp6_0_v1/`（README、mando_check.py、fetch_solc.py、setup_cloud_env.sh、compilers_sha256.txt、production_tests_cloud.json、mando_check_cloud.json）；`PROMPTS.md` r2.25 → r2.26（修改说明、D25 状态、4.6j 节）；记录：本节、HANDOVER、DECISIONS、PROGRESS。生产文件仍为 18 个。

### 61.2 实施方式和重要选择

- D3(c) 只加在 production 分支，regression_6c 的结果结构不变，冻结的 6c 证据不受影响。判定使用 CP5.2 已经记录的两个信号（is_incorrectly_constructed 与顶层函数日志），不新增探测。不满足时不写图，流水线按原逻辑继续尝试其他候选版本，因为部分 IR 可能只在某个版本上出现。
- 分类：沿用 slither_incomplete 类别与 tool_limitation 路线，以子类 slither_partial_ir 单列，不新增顶层类别，CP3 以来的主因规则与汇总不需要改动。
- 测试：用 monkeypatch 让 Slither 把指定合约标记为不完整、或在构图期间写一条顶层函数日志，覆盖两种信号；流水线测试给两个候选版本，确认都被尝试且不产出图。
- 执行环境：soliditylang 二进制站点被出口代理拒绝，改从 ethereum/solc-bin（0.4.10 以后）与 crytic/solc（0.4.0、0.4.2、0.4.9，solc-select 的来源）读取，按仓库保存的官方索引与 cp0_v2 清单逐个核对 SHA256；记录中的绝对路径用符号链接在容器内重建（setup_cloud_env.sh），模块的 SHA256 检查不变。MANDO 的 43 个元数据输入取自 smartbugs/smartbugs-curated，versions.csv 与源文件 SHA256 与 cp0_v2 记录一致。tree-sitter 语言库由仓库内 vendor 的 tree-sitter-solidity 构建。

### 61.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 编译器 | 96 / 96 SHA256 一致 | compilers_sha256.txt |
| 生产测试（改动前，5f8a7ef81） | 1,155 passed、6 skipped，与 Codex CP5.2 相同 | production_tests_cloud.json |
| 生产测试（改动后） | 1,160 passed、6 skipped | 同上 |
| MANDO 回归 | 843 个图逐字节相同、D3(c) 为真；3 个历史失败不变；第 2–4 步 0 次；267.8 秒 | mando_check_cloud.json |

未证明：mando 环境测试与 DFG v2 测试（云端没有 Python 3.7 的 mando 环境）；4 个带标记的真实单元在新规则下的结果（云端没有 DAppSCAN 的该项目）；全量真实语料中带标记的单元数（CP6 的全量重跑给出）。

### 61.4 用户批准、原文差异与待确认设计

- 用户批准：D25；工作方式与记录方式。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 61.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp6_0_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；下载 96 个编译器（约 942 MB）与 smartbugs-curated（git 浅克隆），均在仓库外；没有 LLM 调用，费用 0。
- 停止：等待用户拉取并由 Codex 执行 PROMPTS §4.6j 的本地运行步骤，Claude 审查后进入 CP6。本轮提交并 push 到 `compile-repair`。

## 62. 2026-11-24 CompileRepair CP6.0 本地复核停在真实单元归因（修改 AI：Codex）

### 62.1 任务、依据与范围

按 PROMPTS r2.26 §4.6j 复核 Claude 的 `6faffcab`。本轮新增 CP6_REPORT.md 及 artifacts/cp6_0_v1/local/ 下的 partial_ir_check.py、tests.json、mando_check.json、partial_ir_units.json、doc_check.json。更新本节、HANDOVER、PROGRESS 和 DECISIONS。生产代码与测试沿用拉取版本。

### 62.2 实施方式和重要选择

依次运行 production、mando、DFG v2，再用官方步骤给出的 mando_check.py 比对 v5。CP5.1 原 real_dev 入口会遍历 2,316 个单元和三种策略。限定运行器只选指定四个标识，复用原始数据入口、离线索引校验和生产 repair_unit。按 §4.6j 实传 oldest、K=21，将每个候选的 D3、合约名、设置及编译器哈希与最终主因分别记录。

### 62.3 实测与数据结论

三套测试依次通过 1,160、672、2,653 项，前两套跳过 6、494 项，DFG 有 9 条警告。MANDO 的 843 个成功图逐字节相同且 D3(c) 为真，3 个历史失败一致。cp3_19463 的两个离线依赖版本各尝试 35 个 solc 版本。70 次均被识别为 slither_partial_ir，均未产图。两轮依赖变更被拒后，最终记录沿用 unresolved_package_import，与 §4.6j 期望的 slither_incomplete 不符。实测和逐版证据见 CP6_REPORT.md 与本批 local 下三份结果 JSON。

### 62.4 用户批准、原文差异与待确认设计

第 0 步因 32,005 个已登记历史未跟踪路径停止。用户批准原地保留后，按清单 SHA256 与 Git 对象复核。D25 仍为已定。真实单元的最终归因差异留给 Claude 审查，本轮没有改变 D3、依赖接受条件或报告标准。

### 62.5 验收、资源、未执行事项与停止

逐项通过三套测试与 MANDO 检查，第 4 步在第一个单元停止。另三个指定单元未运行。完整命令与耗时在 tests.json、mando_check.json、partial_ir_units.json。核对 18 个生产文件和 354 个 DFG 代码引用。CPU 运行，0 美元，无安装、语料下载、训练或外部 LLM 调用。五份文档的 doc_check 结果见 local/doc_check.json。


## 63. 2026-11-24 CompileRepair CP6.0 本地复核审查与 CP6.0.1（修改 AI：Claude）

### 63.1 任务、依据与范围

用户告知本地结果已上传（2026-11-24）。审查 Codex 的 CP6.0 本地复核（提交 6d0d0c67d：CP6_REPORT.md、artifacts/cp6_0_v1/local/、CHANGE_LOG §62），按结果修正后再交本地复核。修改：`pipeline.py::repair_unit`；`tests/test_cp60.py`（新增 3 项）；`artifacts/cp6_0_v1/`（README 的 CP6.0.1 节、production_tests_cloud_r2.json、mando_check_cloud_r2.json、local/partial_ir_check_r2.py）；`PROMPTS.md` r2.26 → r2.27（修改说明、4.6k 节）；记录：本节、HANDOVER、DECISIONS、PROGRESS。生产文件仍为 18 个。

### 63.2 实施方式和重要选择

- 审查：本地三套测试的数量与 4.6j 的预期一致（mando 672 / 494 也一致）；MANDO 843 个图一致。cp3_19463：两轮依赖候选、各 35 个版本 solc 全部成功，D3(a)、D3(b) 为真、D3(c) 为假，被标记的合约与 CP5.2 记录相同；读 `try_project`，接受条件排除 slither_side_failure，`_failure_measure` 在 solc 全部成功时返回 None，于是这两轮都未被接受，单元保留环境阶段的结果。Codex 停下并保留现场正确；预期错的是 4.6j。
- 修正方式：考虑过直接接受这类试验，但接受会改变后续步骤的起点（例如第 2 步被接受后，第 3 步只能从新状态出发），可能错过原来能成功的路径。因此只改最终归因：搜索与接受完全不变，全部步骤结束后才用第一个编译通过的 Slither 侧失败试验替换未成功的最终结果。这样成功单元与图不受影响，未成功单元的主因指向真实的阻碍。
- 影响范围：所有“修复后编译通过、但 Slither 侧失败”的未成功单元（含 D21 重名、项目绑定失败与 D3(c)），主因由原编译阻碍改为 slither_incomplete；D3 成功数不变。

### 63.3 实测与数据结论

| 核对项 | 结果 | 来源 |
|---|---|---|
| 本地复核 | production 1,160 / 6；mando 672 / 494；DFG v2 2,653；MANDO 843 一致；cp3_19463 主因 unresolved_package_import | CP6_REPORT.md、local/*.json |
| 新测试 | 3 项；“路径修正后只剩部分 IR”在修正前的流水线上失败，修正后通过 | tests/test_cp60.py |
| 云端生产测试 | 1,163 passed、6 skipped | production_tests_cloud_r2.json |
| 云端 MANDO | 843 个图逐字节相同、D3(c) 为真 | mando_check_cloud_r2.json |

未证明：4 个真实单元在修正后的结果（本地运行）；全量语料中受归因修正影响的单元数（CP6 全量重跑给出）。

### 63.4 用户批准、原文差异与待确认设计

- 原文差异：4.6j 第 4 步的预期遗漏了接受规则；以 4.6k 为准。修正属于 D25 的实现，不需要新的用户决定。
- 待确认：D19。D9/D10 待确认，D12/D13 待定。

### 63.5 验收、资源、未执行事项与停止

- doc_check：PROMPTS、HANDOVER、DECISIONS、cp6_0_v1/README 全文，CHANGE_LOG 与 PROGRESS 按追加前字节数检查追加区间，全部 passed=True 后提交。
- 资源：云端 CPU；没有下载、安装或 LLM 调用，费用 0。
- 停止：等待用户拉取并由 Codex 执行 4.6k 的本地运行步骤，Claude 审查后进入 CP6。

## 64. 2026-11-24 CompileRepair CP6.0.1 本地归因复核（修改 AI：Codex）

### 64.1 任务、依据与范围

按 PROMPTS r2.27 §4.6k 复核 compile-repair@9a498786。新增 artifacts/cp6_0_v1/local/ 下的 tests_r2.json、mando_check_r2.json 和 partial_ir_units_r2.json。在 CP6_REPORT.md 追加本机结果，并更新 HANDOVER、PROGRESS 和 DECISIONS。

### 64.2 实施方式和重要选择

按规定在新目录运行三套测试与 846 个 MANDO 输入。四单元复用 Claude 指定的 partial_ir_check.main、CP5.1 离线依赖索引、生产 profile、oldest 和 K=21。把最终单元结果与每次 Slither 观测分别记录，逐单元从 repair_steps.json 读取 accepted_outcome 的步骤、轮次和发布版，并核对被选择收据的 SHA256。

### 64.3 实测与数据结论

production 1163 passed, 6 skipped in 97.46s (0:01:37)；mando 672 passed, 497 skipped in 21.73s；DFG v2 2653 passed, 9 warnings in 165.41s (0:02:45)。843 份 MANDO 成功图与 v5 逐字节一致且 D3(c) 为真，3 个历史失败一致，真值上触发 0 次。实测 4 个真实单元，共 385 次候选观测，其中 385 次归为 slither_partial_ir。4 个单元最终主因为 slither_incomplete，0 个单元换版本成功。四单元及逐版详情见 CP6_REPORT 的 CP6.0.1 一节和本批三份 JSON。

### 64.4 用户批准、原文差异与待确认设计

第 0 步核对了原批准清单。第 3 步随附脚本要求批次目录尚不存在，与前两步共用该目录的规定冲突。用户批准按原脚本设置 OUT、直接调用同一 main，实际命令随收据保存。D25 和原验收标准沿用。没有调整生产逻辑。

### 64.5 验收、资源、未执行事项与停止

本地复核通过，等待 Claude 审查。本节规定的四个真实单元均已实测。已核对 18 个生产文件与 354 个冻结 DFG 代码引用。CP6_REPORT、PROGRESS、CHANGE_LOG、HANDOVER、DECISIONS 的五份 doc_check 回执和 SHA256 写入 tests_r2.json 的 doc_check 字段。CPU 运行，未安装、下载语料、调用 LLM 或训练，费用 0 美元。
