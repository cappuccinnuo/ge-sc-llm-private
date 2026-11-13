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
