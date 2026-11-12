# CompileRepair：智能合约编译修复模块方案与 Codex Prompts

版本：r2.3（2026-11-12；r2.2、r2.1 同日，r2 为 2026-11-11）。分支：`compile-repair`，从 `node-sem@306c135b` 切出（与 `edge-sem` 的起点相同；不含进行中的 EdgeSem 代码）。
模块目录：仓库根目录下的 `compile_repair/`（与 `scripts/` 同级）。
证据：`compile_repair/artifacts/cr_pre_v1/`（MANDO 语料的编译与 Slither 证据）、`compile_repair/artifacts/cr_pre_v2/`（外部语料结构统计）。每个目录的 README 列出环境、脚本、结果与复现命令。本文与证据不一致时以证据为准，并在 PROGRESS.md 记录。

使用方式：每次开新会话，先贴第 4.1 节共享上下文，再贴一个 Prompt。顺序：CP0 → CP1 → … → CP10。每个 Prompt 结束后先交审查，通过后再进下一个。CP4 起的 Prompt 在本版只给出范围与验收，CP3 的数据出来后再逐个细化（与 EdgeSem 按审查修订 PROMPTS.md 的方式相同）。

**r2 相对 r1 的修改**：
1. 目录从 `scripts/compile_repair/` 移到仓库根目录 `compile_repair/`；全部路径随之修改。
2. 目标从“只服务 MANDO 训练语料的版本选择”扩大为“任意合约（单文件或多文件项目）的编译修复”。主要评估语料为 DAppSCAN；MANDO 语料是输入之一。理由：检测与评估阶段面对的是真实合约（证据见 1.4）。
3. 一条流水线处理所有输入，不区分训练与检测两种模式（用户决定）。所有改动都记录并在图中标记，由下游决定如何使用。
4. 修复顺序：确定性方法（9 步，3.2 节）先于 LLM；LLM 分两阶段：单代理 + RAG（3.5 节），失败后进入多代理第二阶段（3.6 节）。
5. 文献核对结论写入设计：被核对的 8 个 LLM 编译修复系统都没有按错误类别设计不同提示模板（1.5 节），所以只用一个修复模板，差异来自检索内容与定位到的代码；多代理第二阶段不采用“提议后讨论投票”，而采用失败分析、上下文扩展、异构模型独立提议、由编译器裁决（1.5 节）。
6. 新增代码结构规范（3.10 节）：功能内聚、分层目录、适度模块化、非测试代码文件数受控。
7. Prompt 重新编号：CP0–CP2 沿用 r1 内容（路径更新、按 3.10 节组织代码）；新增 CP3（外部语料获取与失败分类）至 CP10。

**r2.1 相对 r2 的修改**（设计不变）：
1. 新增 `compile_repair/docs/`：`README.md`（记录规则与模板）、`HANDOVER.md`（交接文档）、`CHANGE_LOG.md`（运行与改动记录）、`DECISIONS.md`（决策记录）。格式沿用 NodeSem 在仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md` 中的写法。
2. 每个编码任务结束时必须按 `docs/README.md` 完成记录；记录只写在 `compile_repair/docs/`，禁止修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md`（与 EdgeSem 并行追加会在合并时冲突；决策 D14）。
3. 6c 的本地结果被 `.gitignore` 忽略，只存在于 EdgeSem 工作树；CP0/CP2 以绝对路径只读读取（决策 D15）。

**r2.2 相对 r2.1 的修改**（用户 2026-11-12：模块不只修复当前训练数据中的问题，还要修复将来检测时输入的任意损坏合约，不应只针对当前数据集的问题设计）：
1. 设计目标改为检测时的任意输入；所有语料（MANDO、DAppSCAN、SOChecker、Trace）只用于测试与评估，不决定模块覆盖哪些问题。MANDO 846 个文件降为与 6c 对照的回归基线（0 节“适用范围”、D2）。
2. D6 改写：确定性方法覆盖的范围由与语料无关的失败分类表决定（solc 文档列出的 13 种错误类型 × 有文档依据的原因），某类失败只要存在可确定性实施且能被机械检查验证的修复就实现，不再以某个语料中的出现频率为门槛；频率只决定实现顺序（3.2 节、CP3）。
3. 版本策略一般化（3.3 节）：“已知编译器版本”改为可选输入（MANDO 的 SolidiFI metadata 只是其中一种）；无 pragma 时按有文档依据的版本特征语法推断区间，MANDO 的 0.4.25 默认值只在回归运行中使用；支持范围为 0.4.12 至 0.8.x。
4. 新增 D16：Slither 0.8.0 能否处理较新的 0.8.x 编译器输出尚未验证，由 CP0 探针测出；需要升级 Slither 时须用户决定（升级会使结果与 6c 不可直接对照）。
5. 输入接口一般化：`cli repair <路径>` 接受单个文件、项目目录或片段文本（3.1 节、CP1）。CP0 增加全版本范围的编译器与 Slither 基线检查；CP2 改称 MANDO 回归运行；CP3 建立分类表；CP4 的破坏算子来自分类表而非只来自已观察到的失败。

**r2.3 相对 r2.2 的修改**（CP0 审查；证据 `artifacts/cp0_review_v1/README.md`）：
1. CP0（提交 ac2b3465）的全部数字已独立复核，可以复现；结论见新增 1.6 节。CP0 本身的调查结论成立，但审查发现方案中有四处错误或缺口，须先由 CP0.1 处理，CP1 才能开始（新增 4.2b 节）。
2. 更正 1.2 节：43 份 metadata 来自 SmartBugs `versions.csv`，不是 SolidiFI `BugLog_*.csv`（Codex 的更正成立）。
3. D3 加强：节点覆盖范围加入顶层函数（`compilation_unit.functions_top_level`；0.7.1 起的自由函数不在 `functions_and_modifiers_declared` 中），并要求 Slither 解析出的合约与 solc AST 中输入文件的合约定义一一对应（防止漏解析时“空通过”）。
4. D4 改为 key5 =（合约名或 `<top-level>`、函数 full_name、节点类型、起始偏移、序号）。key4 在 55 个文件中重复（例如三元表达式拆成共享起始偏移的两个 RETURN 节点）；序号是 Slither 节点顺序中相同（类型、起始偏移）的第几个，678 对跨编译器版本比较中 678/678 稳定。
5. 修正 3.2 节第 6 行与 3.3 节第 6 条的矛盾：前者写“越过声明区间禁止”，后者恰是在区间内无可用编译器时才使用，必然越过区间（例如精确 pragma）。改为：这是唯一允许离开声明区间的情形，只能在下界所在的小版本系列内，记为 rewrite 并标记。新增 D18（编译器获取范围）。
6. D16 有了完整测量（1.6 节）：Slither 0.8.0 不能处理 0.8.4 起的多种语法；给出 0.8.3、0.9.6、0.10.4、0.11.6 的对照与推荐方案，等待用户决定。
7. CP2 的 6c 回归改为“精确重放”：在 `mando` 环境用冻结的 6c 抽取代码在 6c 使用的版本上重跑 239 个文件，与 6c 报告逐文件比较（238/239 的版本与当前选定相同，239 个版本全部已安装）。
8. CP1 前提增加：CP0.1 通过；D5、D16、D18 已决定。版本策略只实现在 `rules/environment.py`，`evaluation/survey.py` 中 CP0 的选版代码改为调用它；验收为在 846 个文件上复现 `cp0_v2` 的升序选定版本。

---

## 0. 方案概述

适用范围：模型检测阶段用户提供的任意 Solidity 合约，形式可以是单个文件、扁平化文件、多文件项目（有或没有 Hardhat/Truffle/Foundry 配置）或代码片段，版本 0.4.12 至 0.8.x。训练语料只是输入之一。模块的覆盖范围按与语料无关的失败分类表设计（D6）；各语料用于测试、评估与确定实现顺序。

输入：一个 Solidity 文件，或一个项目中的一个编译单元（一个 `.sol` 文件及其传递导入闭包），或一段片段文本（作为单文件处理）。
输出：能被 solc 编译且 Slither 0.8.0 能生成完整 CFG/CG/SlithIR 的源码集合（原文件不修改，改动作用在副本上）；逐字节的改动记录；每个文件的改动等级（无改动 / 只增加 / 改写）；Slither 图中来自新增或改写代码的节点标记；一条清单记录。

流程（3.1 节）是一个循环：编译并读取错误 → 先试确定性方法（换编译器、补依赖、规范化、规则桩、结构补全）→ 仍失败时调用第一阶段代理（单模板 + RAG + 多个候选 + 以编译结果择优）→ 预算用尽仍失败时调用第二阶段多代理 → 每接受一个改动都重新进入循环（确定性方法会再跑一遍）→ 成功后用 Slither 判定（D3）并记录。

---

## 1. 现状（2026-11-11 逐项核对代码与数据）

### 1.1 MANDO 语料（证据：`cr_pre_v1/corpus_stats.json`）

`experiments/ge-sc-data/source_code/<类别>/source_files/*.sol`，七类共 846 个文件：

| 类别 | 文件 | 无 pragma | 地址命名 | `buggy_` 前缀 | 其他命名 | SmartBugs 风格标签注释 |
|---|---:|---:|---:|---:|---:|---:|
| access_control | 114 | 5 | 57 | 40 | 17 | 17 |
| arithmetic | 120 | 3 | 60 | 45 | 15 | 15 |
| denial_of_service | 92 | 1 | 46 | 40 | 6 | 6 |
| front_running | 88 | 1 | 44 | 40 | 4 | 4 |
| reentrancy | 142 | 1 | 91 | 40 | 11 | 31 |
| time_manipulation | 100 | 4 | 50 | 45 | 5 | 5 |
| unchecked_low_level_calls | 190 | 7 | 140 | 45 | 5 | 50 |
| 合计 | 846 | 22 | 488 | 295 | 63 | 128 |

- `import` 语句 0 条。首个版本号的小版本系列只有 0.4 与 0.5。15 个文件含两条不同的 `pragma solidity`。
- 合取区间上界（824 个有 pragma 的文件）：0.6.0 387，0.5.0 207，0.4.25 99，开放上界（只有 `>=`/`>`）62，0.4.22 21，0.4.24 16，其余较少。
- “标签注释”指 `<yes> <report>`、`@vulnerable_at_lines`、`@source`、`@author` 等 SmartBugs curated 头注释。

### 1.2 DFG v2 Prompt 6c 的版本与 Slither 结果（证据：`scripts/DFG/dfg_v2/PROMPT6BC_REPORT.md`、`scripts/DFG/dfg_v2/PROGRESS.md` 2026-10-25 节）

- 范围：重入 142、访问控制 114，共 256 个文件；26 个 solc 版本（solc-select 1.0.4，SHA256 与 Keccak256 双校验）；Slither 0.8.0、crytic-compile 0.2.4。
- 版本来源：43 metadata（SmartBugs `data/smartbug-dataset/versions.csv` 的 `compiled version` 列，由 `scripts/DFG/state/stage_f/versioning.py::recorded_version` 校验；r2.2 及以前误写为 SolidiFI `BugLog_*.csv`，CP0 更正）、207 pragma_derived（`auto_version_solc` 规则）、6 fallback_default（无 pragma，用户批准沿用 0.4.25）。每文件只试一个版本。
- 结果：重入 131 可比较 / 8 solc 失败 / 3 映射不可比；访问控制 108 / 3 / 3。11 个 solc 失败全部是 pragma_derived；6 个不可比文件使用 0.4.0/0.4.2/0.4.9，Slither 输出缺 CFG filename（含 simple_dao、parity_wallet_bug_2）。Slither 分析失败 0。
- 完整报告只在用户本地：`scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json`（151,967,233 字节，SHA256 `db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6`），seal `report.seal.json`（SHA256 `91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c`）。数字来自 `edge-sem` 分支 `scripts/edge_sem/artifacts/ep6_v1/compiler_history.json`。
- 可信编译器清单：`scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json`（本地）；`validate_slither.py::inspect_environment` 读取 `~/.solc-select/artifacts`。
- 以上 `report.json`、`report.seal.json`、`trusted_compilers_complete.json` 在 `edge-sem` 分支中都未被跟踪（`.gitignore` 第 24 行 `*.json`），新建的 `compile-repair` 工作树中不存在；只能从 EdgeSem 工作树 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/` 下的同一相对路径只读读取（D15）。

### 1.3 MANDO 语料的编译复现（证据：`cr_pre_v1/`；环境与 6c 不同：GitHub 静态 solc 0.4.11–0.5.17、Python 3.8、直接 `solc <文件>`，须由 CP0 在用户环境复核）

| 编号 | 事实 |
|---|---|
| 证据 1 | 846 个文件 0 个 `import` |
| 证据 2 | 规则 A（auto_version_solc，一次）：807 通过，10 失败，29 个所选版本 ≤ 0.4.10 在此不可用。10 个失败：pragma 下界早于代码使用的语法（`^0.4.11` 下 `view`/`pure`；`^0.4.13`–`^0.4.20` 下在 `(` 处解析错误），或两条 pragma 时规则取第一条（2 个文件的规则版本不在自身合取区间内） |
| 证据 3 | 规则 B（合取区间内全部可用版本）：39/39 找到可编译版本，且都与规则版本同一小版本系列；按退出码 846/846 可编译 |
| 证据 4 | 重入 + 访问控制：A 不通过 17 个，与 6c 的 11 + 6 = 17 总数相同；逐文件对应未核对 |
| 证据 5 | Slither 0.8.0：39 文件 × 2 版本全部成功；节点缺文件名只出现在 solc 0.4.11；0.4.12 起正常 |
| 证据 6 | 两个版本之间：key4（合约、函数 full_name、节点类型、起始偏移）39/39 相同；加 SlithIR 39/39 相同；source length 36/39 相同 |
| 证据 7 | 规则 A 下可编译但版本 ≤ 0.4.11 的文件 4 个（会在 Slither 中静默缺文件名） |
| 证据 8 | 0.4.25、0.5.11：等长空格替换 pragma 行可编译（警告）且字节数不变；基类后定义报错；先定义的无函数体声明可编译；`^0.4.24` 文件替换 pragma 后能被 0.5.11 编译（越过声明区间） |

### 1.4 外部语料（证据：`cr_pre_v2/`；只读统计，未编译）

| 语料 | 规模 | 关键事实 |
|---|---|---|
| DAppSCAN（`DAppSCAN-source/contracts`，提交 66a56619） | 608 个项目，21,457 个 `.sol` | 473 个项目含 import；405 个项目至少有一条仓库内无法静态解析的 import；1,094 条相对导入指向不存在的文件；606/608 个项目没有任何构建配置，没有 node_modules；版本跨 0.4–0.8（按文件：0.5 6,552、0.6 5,464、0.8 4,222、0.4 3,503、0.7 1,542） |
| SOChecker 评估片段（提交 5e56d754） | 897 条 Stack Overflow 片段 | 656 条含 `contract `/`function `；其余混有非 Solidity 内容 |
| Trace 数据集（提交 4260215b） | on-chain 5,000 单文件；repo-level 83 个项目 3,092 个 `.sol`；CVEs 15 | repo-level 深度 3 以内没有构建配置 |

含义：外部语料的主要问题是依赖缺失与项目组装，而且版本跨 0.4–0.8。只覆盖 OpenZeppelin（DAI 的范围）不够。三个仓库都没有 LICENSE 文件，仅作研究用途，使用前由用户确认。

### 1.6 CP0 结果（2026-11-12 审查；证据 `artifacts/cp0_v2/`、`artifacts/cp0_review_v1/`）

| 项 | 结果 |
|---|---|
| 输入与身份 | 846 个文件，SHA256 与 git 语料 0 差异；43 份 metadata 校验通过，其中 4 份 ≤ 0.4.11 |
| 编译器 | 37 个可信版本（原 26 + 用户批准新增 11）；0.4.12–0.8.38 官方快照的 92 个正式版本中已安装 33 个 |
| 规则 A（auto_version_solc） | 821 通过、22 失败、3 未安装；与云端旧证据（cr_pre_v1）的差异逐项对账一致 |
| 升序选定 | 846/846 满足（r2.2 的）D3；1,692 个升/降序选定版本逐条检查：都有 rc0 编译与 D3 通过记录、在合取区间内、与下界同一小版本系列、≥ 0.4.12；违例 0 |
| 升序与降序 | 617 个文件选定版本不同；相对规则 A 移动 44 个；0 个跨小版本系列 |
| 6c 的 17 个异常文件 | 与旧证据集合相同，现在全部在升序选定版本上通过 D3 |
| 跨版本 | 678 个文件有两个以上 D3 版本：key4 与有序 SlithIR 678/678 相同，source length 650/678；其余 168 个全部是精确 pragma |
| key4 重复 | 55 个文件；Slither 把三元表达式等拆成共享起始偏移的多个同类节点；序号身份 678/678 稳定（D4） |
| 6c 版本 | 239 个已比较文件中 238 个的 6c 版本与当前升序选定相同；239 个 6c 版本全部已安装 |
| 顶层函数 | 不在 `functions_and_modifiers_declared` 中，r2.2 的 D3 与 CP0 指纹都未覆盖（MANDO 语料无此语法，不影响 CP0 数字） |

Slither 版本对照（743 个不同源文件，同一批编译器；节点类型按各版本枚举名归一；特征探针为 solc 0.8.38 上的 6 个语法：自由函数、自定义错误、UDVT、顶层 using、全局用户定义运算符、transient）：

| Slither | Python 要求 | 结构与 0.8.0 相同 | 结构差异 | 有序 IR 与 0.8.0 相同 | 旧合约失败 | 特征探针 |
|---|---|---:|---|---:|---:|---|
| 0.8.0（当前） | ≥ 3.6 | — | — | — | 0 | 2/6（自定义错误、UDVT、顶层 using、全局运算符失败） |
| 0.8.3 | ≥ 3.6 | 743 | 无 | 482 | 0 | 4/6（顶层 using、全局运算符失败） |
| 0.9.6 | ≥ 3.8 | 721 | 只缺 Slither 合成的 `slitherConstructorConstantVariables()` 的 47 个入口节点 | 62 | 0 | 6/6 |
| 0.10.4 | ≥ 3.8 | 369 | 多 1,999、少 47 | — | 3 | 6/6 |
| 0.11.6 | ≥ 3.10 | 369 | 多 1,999、少 50 | 51 | 3 | 6/6 |

- 0.10.4、0.11.6 的 3 个失败是 `(bool success, ) = msg.sender.call.value(x)("")`（solc 0.4.24）在 `expression_to_slithir` 中触发的 `AssertionError`。
- `transient` 探针在所有版本都构造成功，包括早于该语法的 0.8.0，只说明不崩溃，不说明正确建模。
- 冻结的 6c 抽取（`validate_slither._mapping`）假定 source_mapping 是 dict；Slither 0.9 起是对象，冻结抽取在新版下会静默丢失映射。因此 6c 回归只能在 Slither 0.8.0 下做。
- 当前只有 `scripts/DFG/dfg_v2/` 的验证脚本使用 Slither；NodeSem、EdgeSem 模型不读取 Slither 图。版本选择影响的是 6c 回归与本模块存储的未来使用者（D13）。

### 1.5 文献核对（对话中逐一读论文与发布代码）

**确定性方法与编译环境**

| 来源 | 结论 |
|---|---|
| CompileAgent（ACL 2025，Ch3nYe/AutoCompiler） | 借鉴“先修环境、外部检查器判定成功、代理自报不算”。发布代码不能直接复用（导入失败、C/C++ 专用、无源码保护） |
| DAppSCAN（TSE 2024）与 solc-DApp | 发布的编译工具只取 pragma 第一个版本、无重试；依赖只按前缀映射到已存在的 node_modules |
| DAI（SANER-C 2024，无代码） | 依赖兼容性两步检查：路径一致、pragma 一致；只覆盖 `@openzeppelin/contracts`，不支持 0.4；57 个项目中 50 个成功，7 个因文件缺失失败 |
| SOChecker（ISSTA 2024） | LLM 补全后由脚本补括号，再逐个尝试编译器版本；Llama-2 微调模型加 GPT 作为第二次尝试，可编译片段从 795 增至 889（共 897） |
| SmartBugs 2.0（2023） | 0.4.11 以下编译器难以获取 |

**LLM 修复的提示设计**：核对的 8 个系统都只用一个修复模板（或一个微调指令），没有按错误类别分模板：SmCFixer（发布代码一个模板，按错误检索 top-1/top-3 知识）、SOChecker（3,818 条微调数据只有 1 种指令）、Trace（补全与自我反思两个通用提示）、CompileAgent（每轮一个讨论模板）、RustAssistant（ICSE 2025，一个模板；错误类别只用于分析结果）、Byam（一个基础模板加可选槽位）、PhantomRun（MSR 2026，一个模板；分类只用于分析）、Google 构建修复（微调模型，一种输入格式）。提升主要来自定位（RustAssistant 消融：只要求变更记录 10.74%，加行号、原代码定位与修复说明后 73.70%）、检索内容与编译反馈。

**多代理**：多代理辩论在原始设置下一般不优于成本更低的自洽采样，调参后才可能胜出且难以迁移（Should we be going MAD?，ICML 2024）；带示例的单代理与最好的讨论框架相当，讨论在无示例或模型异构时才有帮助，常见失败是放弃正确答案而跟随错误共识（Wang 等，ACL 2024）；Agentless（定位 → 约 40 个候选补丁 → 运行测试验证 → 选择）在 SWE-bench Lite 上以每题 0.70 美元解决 32.00%，优于多个更昂贵的代理系统。编译修复有精确的裁判（编译器），不需要用讨论判断对错。Trace 在明确禁止改动原函数的提示下，仍有 212/4263（5.0%）补全改动了原函数，说明“提示里禁止”不能代替机械检查。

---

## 2. 决策

| 编号 | 决策 | 状态 |
|---|---|---|
| D1 | 一条流水线处理所有输入，不分训练/检测模式；所有改动记录并标记，由下游决定使用方式 | 已定（用户） |
| D2 | 语料：DAppSCAN 为主要评估语料；SOChecker 片段、Trace（on-chain、repo-level、CVEs）与破坏-修复基准为辅；MANDO 846 个文件是与 6c 对照的回归基线。所有语料只用于测试与评估，不决定覆盖范围 | 已定（用户；2026-11-12 明确语料不决定范围） |
| D3 | 成功判据：编译单元在选定 solc 下退出码 0；Slither 构造成功；（a）所有声明的函数与修饰器以及所有顶层函数（`compilation_unit.functions_top_level`）的每个 CFG 节点 source_mapping 的文件名属于该编译单元的输入文件、start 不为 None；（b）Slither 解析出的合约（含接口与库）名称集合与 solc AST 中编译单元输入文件的 ContractDefinition 名称集合相同 | 已定（证据 5；r2.3 加入顶层函数与合约覆盖，1.6 节） |
| D4 | 节点身份用 key5 =（合约名，顶层函数为 `<top-level>`；函数 full_name；节点类型；起始字节偏移；序号）。序号为同一函数内按 Slither 节点顺序、相同（类型, 起始偏移）的第几个（从 1 开始）。不得去重；source length 只记录 | r2.3 改定（key4 在 55 个文件中重复；序号 678/678 跨版本稳定，1.6 节） |
| D5 | 版本策略细节（3.3 节）：区间内升序；已知版本作为可选输入；无 pragma 时按版本特征语法推断区间 | 建议，待用户确认 |
| D6 | 确定性方法先于代理。覆盖范围由与语料无关的失败分类表决定（CP3 建立：solc 文档的 13 种错误类型 × 有文档依据的原因，来源为 Solidity 各版本 breaking changes 文档、导入解析规则、项目结构与截断）；某类失败只要存在可确定性实施、且能被 D3 与 D7 机械检查验证的修复，就实现为规则，否则交给代理。语料中的出现频率只决定实现顺序，不作门槛 | 原则已定（用户）；2026-11-12 起取消频率门槛（用户：不只针对当前数据集）；分类表方式由 Claude 提出，用户可调整 |
| D7 | 允许新增与改写；改写只允许出现在编译错误定位到的行；每个文件记录改动等级（none / additive / rewrite），图中标记来自新增或改写字节的节点 | 已定 |
| D8 | 第一阶段：单代理、一个模板、RAG、带原文校验的补丁格式、多候选、编译择优；第二阶段：失败分析、上下文扩展、2–3 个异构模型独立提议、工具裁决、至多一轮基于编译结果的交流 | 已定（用户） |
| D9 | 审查代理（判断改写是否保持原行为）：不进入主流程，只作为 CP10 的消融项 | 建议，待用户确认 |
| D10 | 决策输入：确定性方法只读源码文本、编译器与 Slither 结果、调用方提供的已知编译器版本（3.3 节第 2 条，可选）；LLM 输入中文件路径与文件名替换为匿名编号，注释在 LLM 视图中遮蔽（不改文件） | 建议，待用户确认 |
| D11 | 代码结构规范（3.10 节） | 已定（用户） |
| D12 | LLM 模型、API 与费用上限 | 待定，CP8 之前由用户指定 |
| D13 | 哪个创新点使用这些图，以及是否存数据依赖 | 待定，CP10 之后再议 |
| D16 | Slither 版本（测量见 1.6 节）。推荐：生产工具链用 Slither 0.9.6，放在独立环境（Python ≥ 3.8，不改 `mando`）；Slither 0.8.0（`mando`）只用于 6c 精确重放回归。理由：0.9.6 通过全部 6 个特征探针，在 MANDO 上无失败，用户代码的图结构与 0.8.0 相同（只差合成的常量构造函数）；0.8.3 不支持 0.8.13 起的顶层 using 与全局运算符；0.10.4、0.11.6 在 3 个旧合约上崩溃并大幅改变图结构。代价：新环境需要授权；toolchain 须同时支持 dict 与对象两种 source_mapping；0.9.6 的 SlithIR 文本与 0.8.0 不同（训练与检测用同一版本即可） | 证据已齐，待用户决定 |
| D18 | 编译器获取：推荐一次性安装 0.4.12 至官方快照最新版本（当前 0.8.38）的全部正式版本（尚缺 59 个），双哈希校验，独立追加信任清单；之后的新发布按授权追加。检测时不自动下载。安装后 3.3 节第 6 条 pragma 覆盖只用于官方没有可用构建或低于 0.4.12 的精确 pragma（例如 `pragma solidity 0.4.10;`） | 建议，待用户决定 |

---

## 3. 方案

### 3.1 修复循环（pipeline.py）

```
编译单元 ─► 编译（选定或候选 solc）──► 成功？──是──► Slither 判定（D3）──► 记录改动、标记节点、写清单
                 ▲                      │否
                 │                      ▼
                 │        依次尝试确定性方法（3.2 节第 1–9 步，按代价从低到高）
                 │                      │仍失败
                 │                      ▼
                 │        第一阶段代理（3.5 节）── 预算用尽 ──► 第二阶段多代理（3.6 节）── 预算用尽 ──► 记为未修复
                 │                      │每个被接受的改动
                 └──────────────────────┘（回到编译；确定性方法再跑一遍）
```

- 接受一个改动的条件：通过补丁校验（3.5 节）与 D7 规则，且编译错误数严格减少，或错误全部消失。错误数不再减少的轮次计入预算。
- 所有改动作用在工作副本上；原文件只读。每个改动记录为（文件、原字节区间、新字节、来源步骤、轮次）。
- Slither 判定失败（编译成功但节点缺文件名或偏移）视为失败，继续循环（通常由第 1 步换版本解决，证据 5）。
- 输入形式：单个 `.sol` 文件；目录（按项目处理，由第 2 步确定编译单元）；片段文本（写入工作副本后按单文件处理）。检测时与评估时走同一入口 `cli repair <路径>`，不按语料分支；语料名只作为可选的统计标签与回归配置（例如 MANDO 回归使用 6c 的无 pragma 默认值）。

### 3.2 确定性方法

| 步骤 | 处理的问题 | 改动等级 | 证据状态 | 代码位置 |
|---|---|---|---|---|
| 1 | 编译器版本：按 3.3 节在声明区间内选择；Slither 需要 ≥ 0.4.12 | none | 已验证（证据 2、3、5） | rules/environment.py |
| 2 | 项目组装：为编译单元构造导入闭包、remapping 与 solc standard-json 输入 | none | 需要（1.4：几乎没有构建配置）；算法待 CP3 数据 | toolchain/project.py |
| 3 | 依赖补全：包导入映射到兼容的库发布版（DAI 两步检查，扩展到 0.4 与更多包），离线库索引 | additive | 需要（1.4：405 个项目有无法解析的 import） | rules/dependencies.py |
| 4 | 缺失文件搜索：相对导入目标在项目内其他位置（移动、改名、大小写） | rewrite（只改导入路径） | 未测量；1,094 条相对导入缺失 | rules/dependencies.py |
| 5 | 源码规范化：扁平化产生的逐字节相同的重复定义、重复许可证或 pragma 行、编码问题 | rewrite（只删逐字节相同的重复） | 哪些情况被 solc 拒绝须按版本核实 | rules/normalize.py |
| 6 | pragma 覆盖：区间内没有可用编译器时（3.3 节第 6 条），在下界所在的小版本系列内用等长空格替换 pragma 行。这是唯一允许离开声明区间的情形，不得跨小版本系列 | rewrite（只改 pragma 行） | 已验证保持偏移（证据 8）；r2.3 修正与 3.3 节第 6 条的矛盾 | rules/environment.py |
| 7 | 规则桩：未声明的接口、合约、事件、结构体、修饰器，签名能从使用处推出；缺失基类 | additive | 已验证无函数体声明可编译、基类须先定义（证据 8） | rules/stubs.py |
| 8 | 结构补全：括号不平衡时在文件末尾补齐 | additive | SOChecker 使用 | rules/stubs.py |
| 9 | 只在代码生成阶段出现的失败（例如 Stack too deep） | none | 未验证：Slither 能否只用 AST，或编译设置能否避免 | rules/environment.py |

第 1、6 步在 CP1 实现。第 2–9 步以及表中没有列出的其他失败类别，按 CP3 建立的分类表（D6）逐类判定：有可确定性实施并能机械验证的修复就实现，否则交给代理；表中“证据状态”只表示已有的验证，不表示只处理已观察到的问题。

### 3.3 版本策略（第 1、6 步，D5）

1. 合取区间 I：编译单元内所有文件的所有 `pragma solidity` 取交集，语义与 `scripts/DFG/state/stage_f/versioning.py::interval` 相同（`||` 与无法解析的表达式视为不支持）。实现时先 import 复用；不能复用时按共享上下文规则复制并做等价测试。
2. 已知版本（可选输入）：调用方可以为输入提供已知的编译器版本（例如 Etherscan 验证记录、构建配置中的版本、MANDO 回归中经 `versioning.py::recorded_version` 校验的 SmartBugs `versions.csv` metadata）。在 I 内时作为第一候选；≤ 0.4.11 时记 `known_version_below_slither_floor` 并继续。没有已知版本时跳过此步。
3. 候选 C = 已安装可信版本 ∩ I ∩ [0.4.12, ∞) ∩ [lo, (lo 主版本, lo 小版本 + 1, 0))，lo 为 I 的下界。按升序尝试，第一个满足 D3 的版本为选定版本。支持范围 0.4.12 至 0.8.x 的最新补丁版本；实际可用范围受 D16 约束。
4. 无 pragma：先看同一编译单元内其他文件的 pragma，有则用它们的区间；否则按版本特征语法推断区间：特征与其引入或移除的版本只取自 Solidity 官方 changelog 与 breaking changes 文档（例如 0.5.0 起要求显式可见性与数据位置、移除 `throw`/`var`；0.8.0 起默认检查算术），推断规则与文档出处写在 rules/environment.py 并逐条测试；推断不出时按已安装版本升序。记 `no_pragma_inferred` 或 `no_pragma_guess`。MANDO 回归运行中按 6c 的已批准做法先试 0.4.25（回归配置，不是一般规则）。
5. 下界所在系列全部失败且 I 跨越下一系列时，才在 I 内下一系列升序尝试，记 `crossed_minor`（与 `versioning.py::mode_for` 拒绝跨 0.5.0 的口径一致）。
6. I 内没有可用编译器时（例如精确 pragma 指向未安装或官方没有构建的版本，或低于 0.4.12），才使用 3.2 节第 6 行 pragma 覆盖：候选为下界所在小版本系列中 ≥ 0.4.12 的已安装版本，按与下界的距离从近到远尝试；记 `pragma_overridden`，改动等级 rewrite，清单保留原 pragma 文本与所用版本。这是唯一允许离开声明区间的情形；不得跨小版本系列（越过系列会改变语言语义，证据 8）。

升序的理由：最接近作者声明的下界；证据 6 表明两端版本的图结构相同。

### 3.4 RAG（rag/）

| 来源 | 内容 | 检索键 |
|---|---|---|
| K1 文档 | 与选定编译器版本对应的 Solidity 官方文档（`ethereum/solidity` 仓库对应版本标签下的 `docs/`）与 breaking changes；SmCFixer 知识库在作者许可后加入 | solc 错误类型、抽象掉标识符的错误消息模板、版本 |
| K2 库索引 | 第 3 步建立的离线库源码索引（包名、发布版、文件路径、声明的合约/函数签名、pragma 区间） | 缺失的符号名、导入路径 |
| K3 修复记忆 | 以前通过全部检查的修复（错误模板 + 补丁），不含任何标签 | 错误模板 |

- 先按键精确查找，再用 BM25 关键词检索补足；嵌入检索只作为消融项。每次取前 k 条（k 由 CP7 在基准上确定）。
- K3 的防泄漏规则：评估某个项目（或 MANDO 中某个文件）时，K3 不得包含该项目（文件）自己的修复（留一项目）。

### 3.5 第一阶段代理（agents/stage1.py）

1. 定位：每个剩余错误的源位置前后若干行（行数由 CP8 在基准上确定），每行带行号；同时给出错误涉及的声明位置。
2. 检索：按 3.4 节取 K1–K3。
3. 一个修复模板：任务说明、编译器版本、带行号的代码、错误、检索内容、补丁格式说明与约束（不加注释；不改动错误定位行以外的原代码）。
4. 补丁格式：每个改动写出原代码行（含行号）与新代码；原代码行与文件不完全一致的补丁直接拒绝（RustAssistant 的做法）。新增声明写为“在某行之前插入”。
5. 每轮生成 N 个候选；逐个作用在副本上编译；取错误数最少者，相同时取改动字节最少者。
6. 剩余错误与本轮被拒绝的候选及其编译错误进入下一轮；预算（轮数、候选数、令牌与费用）用尽或连续两轮错误数不降时转入第二阶段。

### 3.6 第二阶段多代理（agents/stage2.py）

1. 失败分析代理：读第一阶段所有被拒绝的补丁及其编译错误，输出失败原因的判断（例如“缺失的类型是项目另一文件中的结构体，不是接口”）。
2. 上下文代理：按失败分析扩大可见范围：项目内其他文件、K2 库索引、K1 文档。
3. 2–3 个不同模型的提议代理：各自读取失败分析与扩展后的上下文，独立生成补丁，互不可见。
4. 工具裁决：编译、D3 判定、D7 检查；取错误最少、改动最小者；完全相同的补丁（规范化格式后）出现次数多者优先（Agentless 的规则）。
5. 全部失败时至多一轮交流：每个提议代理看到其他代理的补丁及其编译错误后修订一次；再失败则记为未修复。
6. 第二阶段从第一阶段的最佳中间状态开始，不从头开始。

### 3.7 改动记录与图标记（core/provenance.py）

- 每个文件的改动等级：none / additive / rewrite。
- 原字节到新字节的偏移映射；additive 文件的原字节全部保留（机械检查，不依赖 LLM）。
- Slither 节点按其 source_mapping 落在原字节、新增字节或改写字节中，分别标记 original / added / rewritten；跨越边界的节点标记 rewritten。

### 3.8 产物（core/store.py）

- 清单（每个编译单元一条）：输入路径与 SHA256、区间与版本来源、尝试过的版本与结果、每一步与每一轮的动作与结果、选定版本、改动等级、改动记录、LLM 调用次数与费用、Slither 结果、标志位。
- 存储：每个编译单元、每个声明的函数与修饰器以及顶层函数的节点（key5 + source length + 节点类型 + SlithIR + 标记）、CFG 边、调用（internal / high-level / low-level / library）。数据依赖由 D13 决定。
- seal：全部产物文件的 SHA256、编译器与 Slither 版本、代码提交号、LLM 模型与缓存索引。

### 3.9 评估（evaluation/）

- 每一步的贡献：确定性方法逐步、第一阶段、第二阶段各修复多少编译单元（按语料、按失败类别）。
- 破坏-修复基准：从可编译的编译单元中按 CP3 分类表的每一类构造破坏（删除库、基类、接口、事件、括号等；包括在现有语料中没有观察到、但分类表中列出的类别），修复后与原图按 key5、CFG 边、调用与 SlithIR 比较，并检查 added 标记是否只落在被删除的内容对应的节点上。
- 外部语料：每个语料的修复率、改动等级分布、费用。
- 消融：无 RAG / 去掉各个知识来源；候选数 N；单模型与异构模型；第二阶段与“给第一阶段同样额外预算”的对照；无失败分析；无交流轮；加入审查代理（D9）；LLM 视图中注释可见（D10）。
- 下游检测结果（D13 之后）按改动等级分开报告。

### 3.10 代码结构规范（D11，所有 Prompt 必须遵守）

原则：功能内聚（一个模块只负责一件事，相关函数放在一起）；分层目录（上层只依赖下层）；适度模块化（不把一个职责拆成多个小文件，也不把多个职责塞进一个文件）；非测试代码文件数受控。

目录（非测试 `.py` 文件上限 30 个，含 `__init__.py`；下表为 29 个）：

```
compile_repair/
  __init__.py
  cli.py                 # 命令行：只解析参数并调用 pipeline / evaluation
  pipeline.py            # 修复循环编排（3.1 节）
  core/                  # 第 0 层：数据与记录，不依赖其他层
    __init__.py
    model.py             # 数据结构：编译单元、编译结果、补丁、改动、清单记录
    provenance.py        # 改动记录、偏移映射、原字节检查、节点标记（3.7 节）
    store.py             # 产物目录、拒绝覆盖、seal、缓存
  toolchain/             # 第 1 层：外部工具，只依赖 core
    __init__.py
    solc.py              # 编译器清单与校验、调用、错误解析与分类
    slither.py           # Slither 运行、D3 判定、图序列化
    project.py           # 编译单元与导入闭包、remapping、standard-json 输入（第 2 步）
  rules/                 # 第 2 层：确定性方法，依赖 core、toolchain
    __init__.py
    environment.py       # 第 1、6、9 步
    dependencies.py      # 第 3、4 步
    normalize.py         # 第 5 步
    stubs.py             # 第 7、8 步
  rag/                   # 第 2 层：知识与检索，依赖 core、toolchain
    __init__.py
    knowledge.py         # K1–K3 的构建与存储
    retrieve.py          # 精确键与 BM25 检索
  agents/                # 第 3 层：LLM，依赖 core、toolchain、rag
    __init__.py
    llm.py               # 模型客户端、缓存、费用计量、密钥从环境变量读取
    prompt.py            # 唯一修复模板与上下文组装（定位、检索内容、匿名化）
    patch.py             # 补丁格式解析、原文校验、应用、D7 检查
    stage1.py            # 第一阶段（3.5 节）
    stage2.py            # 第二阶段（3.6 节）
  evaluation/            # 第 4 层：调查、基准与报告，可依赖以下全部
    __init__.py
    survey.py            # CP0、CP3 的只读调查与失败分类统计
    benchmark.py         # 破坏-修复基准
    report.py            # 指标、消融表、报告
  tests/                 # 不计入文件上限
  docs/                  # 交接、运行与改动记录、决策记录（只放 .md）
  artifacts/             # 数据与证据，不计入文件上限（cr_pre_v1、cr_pre_v2 中的证据脚本也不计入）
```

规则：
1. 依赖方向：core ← toolchain ← {rules, rag} ← agents ← pipeline ← {cli, evaluation}。下层不得导入上层；rules 与 rag 互不导入；pipeline 是唯一同时调用 rules 与 agents 的模块。由 `tests/test_layering.py` 用 ast 解析导入强制检查。
2. 不新建上表之外的非测试 `.py` 文件。确有必要时，在 CPn_REPORT.md 写明理由（为什么不能放进已有模块）并停下等审查；总数不得超过 30。
3. 不建 `utils.py`、`helpers.py`、`common.py` 之类的杂项模块；共用函数放在拥有该概念的层。
4. 单个模块超过约 800 行时，先检查是否混入了其他职责；只有职责确实不同才拆分，拆分仍须遵守规则 2。
5. 公共函数写 docstring，说明输入、输出与失败时的行为；模块顶部一段说明它对应本文哪一节。
6. 命令行入口只在 cli.py；其他模块不写 `if __name__ == "__main__"`。

---

## 4. Codex Prompts

### 4.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文（CompileRepair）

## 项目
在 MANDO-LLM 私有仓库上实现智能合约编译修复模块 CompileRepair：对任意合约（单文件或项目中的编译单元），先用确定性方法（换编译器、组装项目、补依赖、规范化、规则桩、结构补全），仍失败时用 LLM 代理（第一阶段单代理 + RAG，第二阶段多代理），使 solc 可编译且 Slither（版本见 D16；6c 回归用 0.8.0）能生成完整的 CFG/CG/SlithIR；记录每一处改动并在图中标记。方案全文在 compile_repair/PROMPTS.md（第 0–3 节设计，第 4 节各 Prompt），证据在 compile_repair/artifacts/cr_pre_v1/、cr_pre_v2/ 的 README，有疑问先查它们。

工作树：使用独立的 git worktree，不要在 EdgeSem 工作树（/home/zhao/SmartContract/ge-sc-llm-ddg-v11）中切换分支。建议路径 /home/zhao/SmartContract/ge-sc-llm-compile。第一次开始前（在 EdgeSem 工作树中执行，只新增 worktree，不切换当前分支）：
  git fetch origin compile-repair
  git worktree add /home/zhao/SmartContract/ge-sc-llm-compile -b compile-repair origin/compile-repair
之后的提交都在 compile-repair 上。不要 push，除非用户明确要求。每个 Prompt 开始前先 git pull --ff-only origin compile-repair，读取最新的 PROMPTS.md。

环境（WSL）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-compile
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12。代码必须兼容 Python 3.7：不要用 :=、list[str]/dict[str,int] 运行时注解、dict | dict、dataclass(slots=...)、match。
不得安装、升级或卸载任何包，不得下载编译器、语料、库或文档，不得调用任何 LLM API，除非当前 Prompt 明确写着可以且用户已在 compile_repair/artifacts/<批次>/authorization.json 中授权（写明内容、来源、版本、费用上限）。需要时列出清单与理由后停下。不得切换全局 solc 版本；一律传入可执行文件路径。外部语料放在仓库之外（建议 /home/zhao/SmartContract/corpora/<名称>@<提交>），不提交到仓库，只在产物中记录路径、提交号与文件 SHA256。

## 代码结构（PROMPTS.md 3.10 节，必须遵守）
- 只在 3.10 节目录表列出的文件中写代码；新文件需要在报告中说明理由并停下等审查；非测试 .py 文件总数不超过 30。
- 依赖方向：core ← toolchain ← {rules, rag} ← agents ← pipeline ← {cli, evaluation}；tests/test_layering.py 必须通过。
- 不建 utils/helpers/common 杂项模块；命令行入口只在 cli.py。

## 新代码位置
- 代码：compile_repair/（3.10 节的目录）
- 测试：compile_repair/tests/（fixtures 在 compile_repair/tests/fixtures/）
- 产物：compile_repair/artifacts/<批次名>/，拒绝覆盖已存在目录。cr_pre_v1、cr_pre_v2 是 Claude 的证据目录，只读，不导入其中脚本。
- 记录（强制）：每个编码任务（执行任何 CPn，含中途停下；Prompt 之外的修复或补测；产生新产物的运行）结束时、提交之前，按 compile_repair/docs/README.md 完成全部记录，缺一项不得提交：
  1. compile_repair/docs/CHANGE_LOG.md 追加一个编号小节，五段写全（任务、依据与范围 / 实施方式和重要选择 / 实测与数据结论 / 用户批准、原文差异与待确认设计 / 验收、资源、未执行事项与停止）；
  2. compile_repair/docs/HANDOVER.md 第 6 节追加交接记录；当前状态、下一步或必读事项有变化时同时更新第 0–5 节，并在交接记录中写明改了哪几条；
  3. compile_repair/PROGRESS.md 追加一节（做了什么、文件清单、测试命令与结果、验收数字、遗留问题、与 PROMPTS.md 不一致之处及处理），并写 compile_repair/CPn_REPORT.md（格式见 compile_repair/REPORT_TEMPLATE.md）；
  4. 决策状态有变化时更新 compile_repair/docs/DECISIONS.md；
  5. 对所有新建或追加的文档运行 doc_check，结果写进 CHANGE_LOG 第 5 段。
  记录只追加，不改旧文；每个数字给出来源；没运行的写“未运行”；写明修改者（修改 AI：Codex）。不得修改仓库根目录 HANDOVER.md 与 docs/training_changes_2026-10-07.md。
- 开始每个 Prompt 前先读 compile_repair/docs/HANDOVER.md 第 0–5 节与 CHANGE_LOG.md 最新一节。

## 禁止修改（以及禁止新增）
1. scripts/** 下的任何文件，也不得在其中新增文件（包括 scripts/DFG、scripts/node_sem；本分支没有 scripts/edge_sem，也不得新建）。
2. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py、auto_version_solc.py。
3. 语料 experiments/ge-sc-data/**（只读）与外部语料目录（只读）；所有已有产物、图、标签、折、特征、checkpoint、plan/seal。
4. 仓库根目录 HANDOVER.md 与 docs/training_changes_2026-10-07.md（本模块的记录写在 compile_repair/docs/）。
5. EdgeSem 工作树 /home/zhao/SmartContract/ge-sc-llm-ddg-v11 中的任何文件：只能读取 PROMPTS.md 1.2 节列出的 6c 本地结果，先核对 SHA256，不复制、不移动、不修改，不在其中执行 git 命令。
复用时用 import、子类化或组合。必须改变冻结函数的行为时，复制到 compile_repair 的对应模块，函数旁注明来源路径与原文件 SHA256，并加测试证明在旧输入上与原函数输出相同。禁止 monkeypatch。

## 不变量
- 原始输入文件只读；所有改动作用在工作副本上，副本与原文件的差异必须与改动记录完全一致（测试检查）。
- 确定性方法只读源码文本、编译器与 Slither 的运行结果、调用方提供的已知编译器版本（3.3 节第 2 条，可选）；不读文件名、目录名、任何标签或预测文件来做决定。类别目录与项目名只用于统计分组。
- LLM 输入中的文件路径与文件名替换为匿名编号，注释在 LLM 视图中遮蔽（不改文件）。此条为 D10，待用户确认；CP8 之前确定，确定前不涉及 LLM。
- 成功判据（D3，r2.3）：编译单元在选定 solc 下退出码 0；Slither 构造成功；所有 functions_and_modifiers_declared 以及所有 compilation_unit.functions_top_level 的每个节点 source_mapping 的文件名属于该编译单元的输入文件、start 不为 None；Slither 合约名称集合与 solc AST 中输入文件的 ContractDefinition 名称集合相同。
- Slither 的 source_mapping 在 0.8.x 是 dict，0.9 起是对象；toolchain 必须两种都正确处理，取不到映射时判为失败，不得当成空值通过。
- 节点身份用 key5 =（合约名或 <top-level>、函数 full_name、节点类型、起始字节偏移、序号）；序号是同一函数内按 Slither 节点顺序相同（类型, 起始偏移）的第几个；不得去重。source length 只记录。
- 每次编译、Slither 运行与 LLM 调用都记录：版本或模型、可执行文件 SHA256 或请求哈希、命令、退出码或结果、错误首行、耗时与费用。LLM 密钥只从环境变量读取，不写入任何文件或日志。
- 文档一律 UTF-8，用 Python 写文件；写完运行 python -B -m scripts.node_sem.doc_check --expect-cjk <文件>:<追加前字节数> ...（新文件不带字节数），不通过不得提交。

## 关键可复用模块（先读再用）
- scripts/DFG/state/stage_f/versioning.py（interval、recorded_version、mode_for）
- scripts/DFG/dfg_v2/validate_slither.py（inspect_environment、exact_version、compiler_for、slither_facts）
- scripts/DFG/dfg_v2/inputs.py（_check_metadata；6c 的 metadata 来源）
- auto_version_solc.py（规则 A，只作对照，不修改）

## 工作方式
- 每个 Prompt 只做它的范围。代码事实与本文不一致时以代码为准，在 PROGRESS.md 与 docs/CHANGE_LOG.md 记录；如果影响方案，停下来报告，不自行换方案。中途停下时同样按“记录（强制）”完成记录后再提交。
- 每个 Prompt 结束时运行（CPU）：
  python -B -m pytest -q -p no:cacheprovider compile_repair/tests
  python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
  并核对：git status 中除 compile_repair/ 外没有已跟踪文件改动；scripts/DFG 下的 experiment.run._code_refs() 未变化；非测试 .py 文件数 ≤ 30；“记录（强制）”五项已完成且 doc_check 通过。
  全部通过后 git commit，提交信息以 CPn 开头。
- 不启动任何 HGT 训练，不读写 GPU 锁。
- 失败就停，保留现场，不自动重试。
```

### 4.2 CP0：工具基线与 MANDO 回归基线（只读）

```text
# CP0：工具基线（全版本范围）与 MANDO 回归基线（只读：不改语料、不写存储）

说明：模块面向检测时的任意输入（PROMPTS.md 0 节“适用范围”）。本步第 3、5b 节检查整个支持范围（0.4.12–0.8.x）的编译器与 Slither；第 1、2、4、5 节用 MANDO 846 个文件建立与 6c 对照的回归基线，不用于决定模块覆盖范围。

本步新建：compile_repair/__init__.py、toolchain/__init__.py、toolchain/solc.py（编译器清单、校验、调用、错误首行解析）、toolchain/slither.py（运行与 D3 判定）、evaluation/__init__.py、evaluation/survey.py（本步的调查函数）、core/__init__.py 与 core/model.py（只放本步需要的数据结构）、cli.py（survey 子命令）、tests/test_layering.py 及本步的测试。
产出 compile_repair/RECON.md、compile_repair/artifacts/cp0_v1/recon.json 与 compile_repair/CP0_REPORT.md。每条结论附命令、路径、SHA 或计数。

## 1. 输入身份
- 846 个 source_files 的路径与 SHA256 清单；与 cr_pre_v1/compile_repro.json 的文件集合逐一对照。
- 6c 报告与 seal（从 EdgeSem 工作树以绝对路径只读读取，见 1.2 节与共享上下文禁止修改第 5 条）的 SHA256 是否与 PROMPTS.md 1.2 节一致；6c 的 256 个文件与本清单的对应关系（按 SHA256）。
- 6c 的 43 个 metadata 文件：来源记录在哪里（文件与字段），recorded version 的取值分布，其中 ≤ 0.4.11 的数量。

## 2. 与 6c 逐文件核对
- 从 6c 报告中列出 11 个 solc 失败与 6 个映射不可比文件（文件、所用版本、origin、错误首行）。
- 与 cr_pre_v1 的规则 A 结果逐一对照；每个差异说明原因（metadata、旧编译器可得性、调用方式等）。
- 读取 6c 报告的结构，提出 CP2 回归比较所用的键（只描述，不预设），说明它能否不依赖 source length 区分节点。

## 3. 编译器清单
- ~/.solc-select/artifacts 中已安装的版本与 SHA256，与 trusted_compilers_complete.json（EdgeSem 工作树，只读）的对应。
- 支持范围 0.4.12–0.8.x：按小版本系列（0.4、0.5、0.6、0.7、0.8）列出已安装与未安装的版本。已发布版本清单的来源写明（例如 solc-select 的版本列表或 ethereum/solidity 发布页）；无法在不联网的情况下取得时记为“未取得”，不猜测。
- 按 PROMPTS.md 3.3 节的候选集合，另列出 846 个文件（回归基线）需要但未安装的版本及涉及的文件数。
- 不要安装；把需要安装的版本清单与理由写入报告后停下，请求授权。

## 4. 编译矩阵（只用已安装可信版本）
- 每个文件、候选集合中每个已安装版本：solc 退出码与错误首行。说明调用方式（是否经 crytic-compile）及与 validate_slither 的一致性。
- 统计：规则 A 通过/失败；3.3 节升序与降序各自的选定版本；没有任何版本通过的文件（预期 0，若非 0 停下报告）；rule_version_outside_interval、moved_from_rule_version、crossed_minor 的数量。

## 5. Slither（只读运行，不写存储）
- 每个文件用升序选定版本跑一次 Slither 0.8.0，按 D3 记录成功与缺文件名节点数。
- 至少有两个版本通过 D3 的文件，再用最高版本跑一次，比较 key4、SlithIR 与 source length。
- 记录每次运行耗时，估计 CP2 全量运行时间。

## 5b. Slither 0.8.0 在各版本系列上的可用性（D16 的证据）
- 在 compile_repair/tests/fixtures/ 写小型手写合约，每个小版本系列一组，覆盖：状态读写、函数调用、修饰器、事件、外部调用、继承；0.6 起加 try/catch，0.8 起加 unchecked 块与自定义错误（只用该系列文档中存在的语法）。
- 对每个已安装版本编译并运行 Slither 0.8.0，按 D3 判定；记录失败版本、失败位置与错误信息。
- 不升级、不安装 Slither。若较新版本失败，在报告中列出受影响的版本范围，作为 D16 的输入后停下。

## 6. 结论
- 与第 0–3 节及 cr_pre_v1 证据不一致之处，逐一说明是否影响方案；影响方案的，停下报告。
- 给出 CP1 的参数：需要授权安装的编译器（支持范围与回归基线分别列出）、Slither 0.8.0 可用的版本范围（D16）、升序与降序的差异数、回归比较键。
- 列出本步新建的文件，确认都在 3.10 节目录表中，test_layering 通过。
```

### 4.2b CP0.1：CP0 审查修正（r2.3 新增；CP1 之前必须完成）

```text
# CP0.1：D3 加强、key5、source_mapping 兼容、生产 Slither 环境与重验

依据：PROMPTS.md r2.3 的修改说明与 1.6 节；审查证据 compile_repair/artifacts/cp0_review_v1/README.md（只读，不导入其中脚本，可参考其做法）。CP0 的产物（cp0_v1、cp0_v2 等）与报告一律不改、不重跑。
产物：compile_repair/artifacts/cp0_1_v1/（A 部分）、cp0_1_env_v1/（B 部分）、cp0_1_compilers_v1/（C 部分，只在授权后）。报告 compile_repair/CP0_1_REPORT.md。
分三部分。A 不需要任何授权，先做；B 需要 DECISIONS.md 中 D16 已由用户决定且 authorization.json 授权建环境；C 需要 D18 已决定且授权安装。缺哪一项就做到前一部分，按“记录（强制）”完成记录后停下。

## A. 代码修正与 mando 环境重验（Slither 0.8.0，不安装任何东西）

### A1. toolchain/slither.py
- source_mapping 读取统一为一个函数：dict 形式（0.8.x：filename_absolute、start、length）与对象形式（0.9 起：filename.absolute、start、length）都支持；两种都不是时抛出明确错误，不得返回空值后当作“缺文件名”以外的情况处理。测试用两种形式的替身对象。
- 节点遍历范围：每个合约的 functions_and_modifiers_declared，加上每个 compilation_unit 的 functions_top_level（合约名记为 "<top-level>"）。0.8.0 中 compilation_units 与 functions_top_level 的属性名先在 mando 环境实际检查并写进报告，不要猜。
- 节点身份 key5（D4）：按 Slither 的 function.nodes 顺序，对同一函数内相同（类型, start）的节点从 1 起编序号；不排序后再编号，不去重。
- D3（b）合约覆盖：Slither 中 source_mapping 文件属于输入文件的合约名称多重集合，必须等于 solc AST 中这些输入文件的 ContractDefinition 名称多重集合。AST 的取得方式（crytic-compile 已保存的 AST，或另一次记录在 invocations 中的 solc 调用）由你决定，但必须同时支持旧式 AST 与 compact AST，并用 0.4 与 0.8 的 fixture 测试；报告写明所用方式与原因。
- 新指纹 schema 命名为 node_facts_v2（字段：key5、有序 IR、length、所属声明种类）。保留 CP0 的 node_facts_sha256 计算作为“CP0 投影”（只在 cp0_v2 对照中使用，函数注释写明用途），不得改变它的结果。
- 工具链版本固定为显式配置：regression_6c = Slither 0.8.0 + crytic-compile 0.2.4；production = D16 决定的版本（D16 未定时只有 regression_6c）。运行时检测已安装版本，不在配置中则拒绝运行；每条 Slither 记录写入 profile 名称与两个版本号。不要自动接受其他版本。
- 代码仍须兼容 Python 3.7。

### A2. 测试（compile_repair/tests/）
- 两种 source_mapping 形式；取不到映射判失败。
- key5：三元表达式 fixture（例如 return a < b ? a : b;）产生两个相同（类型, start）的节点，序号为 1、2。
- D3（b）：AST 中有而 Slither 中没有的合约判失败（用替身对象构造）。
- 顶层函数：0.7.1 起的自由函数 fixture（需要已安装的 ≥ 0.7.1 编译器，没有则 skip 并记录）在 0.8.0 中的存放位置与 D3 判定。
- profile 拒绝未配置的版本。
- test_layering 仍通过；非测试 .py 文件数不变或在 3.10 节目录表之内。

### A3. mando 环境重验（产物 cp0_1_v1/）
- 846 个文件、在 cp0_v2/recon.json 的 selection.ascending 版本上：新 D3 通过数（预期 846）；其中（a）、（b）各自的失败数；顶层函数数量（预期 0）；CP0 投影指纹与 cp0_v2 invocations.jsonl 中同一（source_sha256, version）的 node_facts_sha256 相同的数量（预期 846）。
- 678 个跨版本文件：最低与最高 D3 版本按 key5 与有序 IR 比较（预期 678/678 相同）；其中有重复 key4 的文件单独计数。
- 任何一项与预期不同：列出全部不同条目并归因，停下报告，不要放宽判据。

## B. 生产 Slither 环境（需要 D16 已决定与授权）

- 按 D16 的决定建立独立 conda 环境（例如 Python 3.8 + slither-analyzer 0.9.6 + crytic-compile 0.3.11，以 DECISIONS.md 与 authorization.json 为准），不修改 mando 环境。记录全部包版本（pip freeze）与安装来源。
- 冻结模块的导入：scripts/DFG/state/stage_f/versioning.py 经 scripts/DFG/frontend.py 依赖 tree_sitter。先在 mando 中读取 tree_sitter 的版本与所用语言库文件的路径和 SHA256，在新环境中安装同一版本，确认 import 成功，并用新环境对 846 个文件计算 versioning.interval，与 mando 中的结果逐一相同。不同或无法导入时停下报告。
- 在新环境运行 compile_repair/tests（与 profile 无关的测试必须全部通过）。
- 846 个文件在同一批选定版本上：D3 通过数（预期 846）；与 A3 的 0.8.0 结果按 key5 比较节点结构，列出全部差异。审查测得的预期是只有 Slither 合成的 slitherConstructorConstantVariables() 的节点（审查在 743 个不同源文件上测得 22 个源文件、47 个节点；846 个文件含跨类别逐字节重复，按 source_sha256 去重后应得到相同数字），其他任何差异列出并停下。有序 IR 的差异只统计并给出前 20 个示例，不作为失败。
- 特征探针：在 tests/fixtures 中为 0.7.1 起的自由函数、0.8.4 自定义错误、0.8.8 UDVT、0.8.13 顶层 using for、0.8.19 全局用户定义运算符、0.8.24 transient 各写一个小合约（只用该版本文档中存在的语法），对每个已安装且不低于该特征起始版本的 0.8.x 编译器运行，按新 D3 判定。transient 的结果只记录“构造成功与否”，在报告中写明它不证明正确建模。
- 0.4.24 的 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol 单独列出结果（0.10、0.11 在这 3 个文件上崩溃；0.9.6 预期通过）。
- 记录每次运行耗时，估计 CP2 在生产环境的全量时间。

## C. 编译器补齐（需要 D18 已决定与授权）

- 按授权清单安装官方正式版本，沿用 cp0_compiler_install_v1 的双哈希校验与独立追加信任清单的做法，不改已有清单。
- 对新安装的每个版本运行 CP0 第 5b 节的兼容性 fixture 与 B 部分的特征探针（适用者），在 production 环境按新 D3 判定。
- 更新支持范围的覆盖统计（0.4.12 至官方快照最新版本，已安装/未安装）。

## 结论
- 逐项给出 A、B、C 的预期与实测；未执行的部分写“未执行”及原因。
- 给出 CP1 所需参数：production profile 的确切版本、已安装编译器清单与覆盖统计、pragma 覆盖（3.3 节第 6 条）在当前清单下仍会用到的情形。
- 列出新建或修改的文件，确认都在 3.10 节目录表中。
```

### 4.3 CP1：核心层与环境方法

```text
# CP1：core 层、版本策略、修复循环骨架（只含第 1、6 步）

前提：CP0.1 已通过审查；D5、D16、D18 已由用户决定；需要的编译器与环境已按授权安装并核验（否则停下）。

版本策略只实现一份，放在 rules/environment.py；evaluation/survey.py 中 CP0 的 candidate_versions、selection_priority 等选版代码改为调用它（CP0 的产物与报告保持不变，不重跑 cp0_v2）。测试证明：以 cp0_v2 的矩阵结果作为编译结果输入（不重新编译），新实现在 846 个文件上的升序选定版本与 cp0_v2/recon.json 的 selection.ascending 逐一相同。

本步实现的是一般输入的修复入口，不针对任何语料；MANDO 只作为第 5 节的回归样本。

## 1. core/
- model.py：编译单元、编译结果、补丁、改动、清单记录的数据结构（只放数据，不放流程）。
- provenance.py：改动记录、原字节到新字节的偏移映射、additive 原字节保留检查、节点按 source_mapping 标记 original/added/rewritten（3.7 节）。
- store.py：产物目录（拒绝覆盖）、清单写入、seal（全部产物 SHA256、工具版本、代码提交号）。

## 2. rules/environment.py
- 第 1 步：3.3 节第 1–5 条；区间计算先 import versioning.interval 复用，不能复用时复制并对 846 个文件逐一做等价测试。第 4 条的版本特征推断：每条规则注明 Solidity 官方 changelog 或 breaking changes 文档中的出处（版本与条目），没有出处的特征不得加入。
- 第 6 步：3.3 节第 6 条（只在区间内无可用编译器时；等长空格替换，下界所在小版本系列，距离从近到远；改动记录为 rewrite）。
- 不读文件名、目录名、注释或标签（测试：同一源码以不同文件名与目录调用，候选列表相同）。

## 3. pipeline.py 与 cli.py
- pipeline：3.1 节循环，本步只接入第 1、6 步；没有其他方法时直接记为未修复。
- cli：`repair <路径>...`（一个或多个 .sol 文件；`--snippet <文本文件>` 把文本作为单文件处理；目录输入在 CP3 实现 toolchain/project.py 之前报告“暂不支持”并以非零退出）；`--known-version <x.y.z>`（可选，3.3 节第 2 条）；`--output <产物目录>`；`--order ascending|descending`；`--regression mando`（回归配置：读取经校验的 SmartBugs versions.csv metadata（6c 的 43 份）作为已知版本，无 pragma 先试 0.4.25；只在回归运行中使用）。检测时与评估时都走这一入口。

## 4. 测试
- 区间：`^`、`~`、`=`、`>=`/`<` 组合、两条 pragma、无 pragma、`||`、空交集。
- 候选：已知版本在区间内/外/≤ 0.4.11/未提供；无 pragma 时每条版本特征推断规则至少一个正例与一个反例；`--regression mando` 与一般入口只在回归配置项上不同；下界 < 0.4.12；开放上界限制在下界系列；crossed_minor 只在本系列全部失败时出现；pragma 覆盖只在区间内无可用编译器时出现且保持字节偏移。
- D3：用 cr_pre_v1/probes 与一个能被 0.4.11 编译的小合约构造“编译成功但缺文件名”的情形，断言判为失败并继续下一个候选（0.4.11 未安装则该测试 skip 并记录）。
- provenance：副本与原文件的差异与改动记录一致；additive 检查能发现被改动的原字节。
- test_layering。

## 5. 小样本运行
- CP0 中规则 A 不通过的全部文件，以及每类按文件 SHA256 排序后用 Random(0) 抽取的 10 个通过文件，产物 compile_repair/artifacts/cp1_sample_v1/。
- 验收：样本中 D3 失败数为 0；每个文件的选定版本与 CP0 第 4 节预测相同。
```

### 4.4 CP2：MANDO 回归运行、存储与检查

```text
# CP2：MANDO 回归运行、存储与检查（与 6c 对照的回归基线，不决定模块覆盖范围）

前提：CP1 已通过审查。

## 1. 全量运行
- cli repair --regression mando（输入为 846 个 source_files），产物 compile_repair/artifacts/cr_store_mando_v1/：清单、每个编译单元的存储（3.8 节，报告中给出 schema）、seal。toolchain/slither.py 增加图序列化。
- 失败文件只进清单，不进存储；若失败数不为 0，停下报告。

## 2. 回归（6c 已比较的 239 个文件）
- 精确重放：在 mando 环境（Slither 0.8.0、crytic-compile 0.2.4）只 import、不修改冻结的 scripts/DFG/dfg_v2/validate_slither.py 中 6c 使用的编译与抽取函数，在 6c 记录的版本上对 239 个文件重跑，按 CP0 提出的 occurrence 多重集合键（cp0_v2/recon.json 中 cp2 键的提议，路径规范化后）与 6c 报告逐文件比较。预期 239/239 相同；不同的逐条列出并归因，不得放宽键。
- 6c 版本与当前升序选定不同的 1 个文件：另在选定版本上重跑，差异单列。
- 生产工具链（D16 决定的版本）构建的存储另与 Slither 0.8.0 按 key5 比较节点结构；若 D16 选 0.9.6，预期差异只有合成的 slitherConstructorConstantVariables()，其余差异逐条归因。不按 source length 判定差异。

## 3. 跨版本不变性
- 所有至少两个版本满足 D3 的文件：最低与最高版本按 key5 与有序 SlithIR 比较；报告相同数、不同数与全部不同条目。

## 4. 分布审计
- 按类别目录统计版本来源、选定版本系列、各标志的数量。不读标签。
```

### 4.5 CP3：失败分类表、外部语料获取与分类

```text
# CP3：与语料无关的失败分类表；外部语料获取与分类（只读：不修复）

## 0. 失败分类表（先于语料统计建立）
- 来源只限有文档依据的内容：solc 文档“Error types”一节列出的 13 种类型（JSONError、IOError、ParserError、DocstringParsingError、SyntaxError、DeclarationError、TypeError、UnimplementedFeatureError、InternalCompilerError、Exception、CompilerError、FatalError、Warning）；Solidity 0.5.0、0.6.0、0.7.0、0.8.0 的 breaking changes 文档逐条；solc 的导入路径解析与 remapping 规则；项目结构（多文件、闭包内版本冲突）；源码截断与扁平化产物。文档需要下载时，列出版本标签与路径写入 authorization 请求后停下。
- 表的每一行：类别名、对应的 solc 错误类型与消息模板（有 errorCode 时一并记录；errorCode 在 standard JSON 中是可选字段）、原因、文档出处、候选修复方式（确定性 / 代理）、确定性修复的验证方式（D3、D7 中哪几项）。
- 下文第 3 节的类别名是初始集合；分类表可以增加类别，不得删除有文档依据但在语料中未出现的类别。
- 表写入 compile_repair/artifacts/cp3_v1/taxonomy.json 与 CP3_REPORT.md；分类规则写在 toolchain/solc.py，测试覆盖每一类（用 tests/fixtures 中的手写合约，不依赖语料中是否出现）。

## 1. 获取（需要授权）
- 列出要获取的语料、仓库与提交（PROMPTS.md 1.4 节：DAppSCAN 66a56619…、SOChecker 5e56d754…、Trace 4260215b…）、预计大小与存放路径，写入 authorization 请求后停下。用户授权后获取，记录每个文件的 SHA256，并核对 cr_pre_v2/README.md 中的计数（项目数、文件数、import 统计、版本分布）；不一致时报告。
- 三个仓库没有 LICENSE 文件；只记录事实，由用户决定使用范围。

## 2. 编译单元
- DAppSCAN 与 Trace repo-level：每个 .sol 文件及其传递导入闭包为一个编译单元；在 toolchain/project.py 中实现导入闭包与 standard-json 输入组装（第 2 步）。导入无法解析时记录原因（包导入 / 相对路径缺失 / 其他），不补依赖。
- Trace on-chain、CVEs、MANDO：单文件即编译单元。
- SOChecker 片段：每条 input 为一个单元；先判定是否为 Solidity（规则写在 survey.py，判定依据记录在报告中），非 Solidity 的单列统计，不进入后续步骤。
- 编译单元数量过大使运行时间超过用户批准的上限时，按项目分层、文件 SHA256 排序后 Random(0) 抽样，记录抽样比例。

## 3. 只跑第 1、6 步之后的失败分类
- 每个编译单元：第 1、6 步后是否满足 D3；不满足的，按第 0 节分类表分类（初始类别：unresolved_package_import、missing_relative_file、undeclared_identifier、missing_base_contract、duplicate_definition、multiple_license_or_pragma、encoding、unbalanced_structure、parser_error_other、type_error_other、codegen_only（例如 Stack too deep）、closure_version_conflict（闭包内各文件区间交集为空）、slither_incomplete、other）。落入 other 的消息模板逐一列出，作为扩充分类表的依据。
- 每类给出：编译单元数、占剩余失败的比例、各语料分布、3 个以 SHA256 标识的示例（不贴源码）。
- 包导入：按包名与导入路径统计，作为第 3 步库索引的范围依据。
- 缺失的相对导入：在同一项目内按文件名查找候选，统计可唯一找到、多个候选、找不到的数量（只统计，不修改）。

## 4. 未验证前提的核实（只用已安装编译器与小型手写合约，放在 tests/fixtures）
- 第 5 步：各版本系列中哪些重复定义、重复许可证标识或重复 pragma 被 solc 拒绝。
- 第 9 步：codegen_only 类别中，Slither 能否在只生成 AST 的设置下工作，或编译设置能否避免该错误。

## 5. 结论
- 按 D6 对分类表逐类判定：有可确定性实施、且能被 D3 与 D7 机械检查验证的修复，列为规则（写明修复方式、改动等级与验证方式）；否则交给代理。语料中的出现频率只用于排列实现顺序，不作为是否实现的条件。
- 给出 CP4 基准的破坏算子清单：分类表中每一个能由删除或修改可编译代码构造出来的类别都要有算子，包括语料中未观察到的类别。
```

### 4.6 CP4–CP10（范围与验收；CP3 之后逐个细化）

| Prompt | 范围 | 代码位置 | 验收要点 |
|---|---|---|---|
| CP4 破坏-修复基准 | 按 CP3 的算子清单（覆盖分类表中每个可构造的类别），从 DAppSCAN、Trace 与 MANDO 846 的可编译单元构造破坏样本，保存原图作为真值 | evaluation/benchmark.py | 每个算子的样本数与构造规则；真值图与 CP2 存储一致 |
| CP5 项目组装与依赖 | 第 2–4 步：离线库索引（需授权下载库发布版并记录校验和）、DAI 两步兼容检查扩展到 0.4 与 CP3 统计的包、缺失文件搜索 | toolchain/project.py、rules/dependencies.py | 外部语料与基准上每步修复数；additive 检查全部通过 |
| CP6 规范化、规则桩、结构补全、codegen 设置及分类表新增的确定性规则 | CP3 分类表中判定为可确定性修复的全部类别（第 5、7、8、9 步及新增类别） | rules/normalize.py、rules/stubs.py、rules/environment.py | 同上；规则桩只加声明，不加函数体 |
| CP7 RAG 知识库 | K1（需授权下载对应版本文档）、K2（复用 CP5 索引）、K3（留一项目）；精确键与 BM25 检索 | rag/knowledge.py、rag/retrieve.py | 基准上正确知识进入前 k 的比例；K3 留一检查 |
| CP8 第一阶段代理 | 3.5 节；先用模拟 LLM 完成全部测试，再在用户授权的模型与费用上限内小样本运行 | agents/llm.py、prompt.py、patch.py、stage1.py；pipeline 接入 | 补丁原文校验拒绝不匹配的改动；匿名化与注释遮蔽测试；基准与外部语料修复率、费用 |
| CP9 第二阶段多代理 | 3.6 节 | agents/stage2.py | 与“第一阶段同等额外预算”的对照；交流轮只在全部失败时出现 |
| CP10 全量评估与消融 | 3.9 节全部表格 | evaluation/report.py | 每一步贡献、消融、费用；报告可复现 |

---

## 5. 与其他分支的关系

- 本分支只新增 compile_repair/，与 edge-sem 没有文件交集（记录写在 compile_repair/docs/，不追加仓库根目录的记录文档）。合并到集成分支时，在根目录 HANDOVER.md 追加一段指向 compile_repair/docs/ 的说明。
- 接入某个创新点（D13）在 EdgeSem 完成并冻结结果之后进行：新建集成分支，图来源作为配置开关；EdgeSem 在旧存储上的结果作为基线。
