# CompileRepair v1：编译前端（让 Slither 能生成 CFG/CG/IR）方案与 Codex Prompts

版本：r1（2026-11-11）。分支：`compile-repair`，从 `node-sem@306c135b` 切出（与 `edge-sem` 的起点相同；不含进行中的 EdgeSem 代码）。
本文是对话中“编译修复模块”方案的第二版（下称 v2 方案；对话中第一版称 v1 方案）。v2 的全部事实依据在 `scripts/compile_repair/artifacts/cr_pre_v1/`（README 列出环境、脚本、结果与复现命令）。本文与证据不一致时以证据为准，并在 PROGRESS.md 记录。

使用方式：每次开新会话，先贴第 4.1 节共享上下文，再贴一个 Prompt。顺序：CP0 → CP1 → CP2。每个 Prompt 结束后先交审查，通过后再进下一个。CP3 之后（接入某个创新点）不在本版范围，见第 5 节。

---

## 0. v2 相对 v1 方案的修订（先读）

v1 方案按“版本选择 → 依赖补全（DAI/DAppSCAN）→ 规则桩 → LLM 多智能体修复（CompileAgent + SmCFixer + RAG）”分层设计，并假设语料中有相当数量“缺代码”的合约。对本仓库语料逐项核对后：

1. **语料没有依赖问题**：七类 `source_files` 共 846 个文件，0 个含 `import`（证据 1）。v1 的 T2（DAI/DAppSCAN 式依赖补全）对本语料没有作用对象。
2. **失败全部是版本选择问题，不是缺代码**：按仓库现有 `auto_version_solc.py` 规则（取 pragma 中第一个版本号、只试一次），39 个文件不通过；在各自合取 pragma 区间内、同一小版本系列中换一个版本后 39/39 可编译，不改一个字节（证据 2、3）。所以 v1 的 T3（规则桩）、T4（LLM 修复）、RAG 与多智能体在本语料上没有作用对象。
3. **6c 的 6 个“映射不可比”文件的原因已复现**：Slither 0.8.0 在 solc ≤ 0.4.11 时节点没有文件名，0.4.12 起正常（证据 5）。这是工具链下限问题，同样靠版本选择解决。
4. **版本选择不改变图结构**：39 个文件各在两个版本下跑 Slither，节点键（合约、函数、节点类型、起始偏移）与 SlithIR 全部相同，只有 3 个文件的 source length 不同（证据 6）。
5. **v1 中被证实的三条 solc 行为**（只在将来启用 T3 时用到）：等长空格替换 pragma 行保持全部字节偏移且可编译；基类必须先于派生类定义；无函数体的声明可编译（证据 8）。同一探针也证明 pragma 替换会越过作者声明的区间，所以 v2 不允许它。

因此 v2 把 v1 收缩为一个**确定性的版本策略 + Slither 成功判据 + 清单与审计**，不改源码、不调用 LLM。v1 的 T2–T4、保真基准与多智能体设计保留为“有触发条件的扩展”（第 5 节），只有在将来换语料（例如 DAppSCAN、真实仓库或代码片段）且版本策略之后仍有失败时才启用。

这也改变了研究定位：在本语料上，“不可编译”几乎全部来自版本选择规则，而不是源码缺失。CompileRepair v1 的价值是让后续创新点可以确定地使用 Slither/SlithIR，而不是一个修复算法本身。

---

## 1. 现状（2026-11-11 逐项核对代码与数据）

### 1.1 语料（证据：`cr_pre_v1/corpus_stats.json`）

`experiments/ge-sc-data/source_code/<类别>/source_files/*.sol`：

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

- `import` 语句：0。首个版本号的小版本系列只有 0.4 与 0.5。15 个文件含两条不同的 `pragma solidity`。
- 合取区间上界分布（824 个有 pragma 的文件）：0.6.0 387，0.5.0 207，0.4.25 99，开放上界（只有 `>=`/`>`）62，0.4.22 21，0.4.24 16，其余较少。开放上界意味着版本策略必须自己限定小版本系列。
- “标签注释”指 `<yes> <report>`、`@vulnerable_at_lines`、`@source`、`@author` 等 SmartBugs curated 头注释；`cleaned_buggy_curated` 目录中为 0。v1 策略不读注释，见 D6。

### 1.2 DFG v2 Prompt 6c 已有的版本与 Slither 结果（证据：`scripts/DFG/dfg_v2/PROMPT6BC_REPORT.md`、`PROGRESS.md` 2026-10-25 节）

- 范围：重入 142、访问控制 114，共 256 个文件；26 个 solc 版本（solc-select 1.0.4 安装，SHA256 与 Keccak256 双校验）；Slither 0.8.0、crytic-compile 0.2.4。
- 版本来源：43 metadata（SolidiFI `BugLog_*.csv` 的 `compiled version`，经 `scripts/DFG/state/stage_f/versioning.py::recorded_version` 校验）、207 pragma_derived（`auto_version_solc` 规则）、6 fallback_default（无 pragma，用户批准沿用 0.4.25）。每文件只试一个版本，失败不换版本。
- 结果：重入 131 可比较 / 8 solc 失败 / 3 映射不可比；访问控制 108 / 3 / 3。11 个 solc 失败全部是 pragma_derived；6 个不可比文件使用 0.4.0/0.4.2/0.4.9，Slither 输出缺 CFG filename（含 simple_dao、parity_wallet_bug_2）。Slither 分析失败 0。
- 完整逐事件报告只在用户本地：`scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json`（151,967,233 字节，SHA256 `db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6`），seal `report.seal.json`（SHA256 `91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c`）。数字来自 `edge-sem` 分支 `scripts/edge_sem/artifacts/ep6_v1/compiler_history.json`。
- 可信编译器清单：`scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json`（本地）；`validate_slither.py::inspect_environment` 读取 `~/.solc-select/artifacts`。

### 1.3 复现与扩展（证据：`cr_pre_v1/compile_repro.json`、`slither_probe.json`、`cross_version.json`、`probes/RESULTS.txt`）

环境与 6c 不同（GitHub 静态 solc 0.4.11–0.5.17；Python 3.8；直接 `solc <文件>`），所以以下是需要 CP0 在用户环境复核的证据，不是最终数字。

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

### 1.4 文献与代码核对（对话中已逐一读代码与论文）

| 来源 | 代码 | 对本方案的用途 |
|---|---|---|
| CompileAgent（ACL 2025） | Ch3nYe/AutoCompiler | 只借鉴“先修环境、外部检查器判定成功、代理自报不算”。代码不可直接复用（发布版导入失败、C/C++ 专用、无源码保护） |
| SmCFixer（ICSME 2025） | Ylkylkylk/SMCFixer | 目标是版本迁移（改写源码），与 v2 不改源码相反；知识库 93 条（0.5–0.8 breaking changes）只在第 5 节扩展中可能用到，需作者许可（仓库无 LICENSE） |
| DAppSCAN（TSE 2024） | InPlusLab/DAppSCAN、MingxiYe/solc-DApp | 发布的编译工具只取 pragma 第一个版本、无重试，正是证据 2 中规则 A 的同类问题；依赖补全对本语料无对象 |
| DAI（SANER-C 2024） | 无 | 不支持 0.4；依赖补全对本语料无对象 |
| SOChecker（ISSTA 2024）、Trace（2025） | BugmakerCC/SOChecker、BugmakerCC/Trace | 只在扩展中作为基线：Trace 在明确禁止改动的提示下仍有 212/4263（5.0%）补全改动原函数 |
| SmartBugs 2.0（2023） | smartbugs/smartbugs | 其文档称 0.4.11 以下编译器难以获取，与证据 2 中 0.4.10 及更早版本的可得性问题一致 |

---

## 2. 决策

| 编号 | 决策 | 状态 |
|---|---|---|
| D1 | v1 范围：七类 `source_files` 共 846 个文件。CP0–CP2 不涉及其他语料 | 建议，待用户确认 |
| D2 | 版本策略见 3.1：metadata 优先；否则在合取区间 ∩ [0.4.12, ∞) ∩ 下界所在小版本系列内按升序取第一个“编译且 Slither 完整”的版本；无 pragma 先用 0.4.25 | 建议，待用户确认（升序 vs 降序见 3.1 末） |
| D3 | 成功判据：solc 退出码 0，且 Slither 构造成功，且所有声明函数与修饰器的每个 CFG 节点都有等于输入文件的文件名和起始偏移 | 已定（证据 5） |
| D4 | 跨版本节点身份用 key4；source length 只记录，不作身份 | 已定（证据 6） |
| D5 | v1 不改源码：不做 pragma 替换、不加桩、不补依赖、不调用 LLM | 已定（证据 1–3、8） |
| D6 | 策略只读 pragma 文本、SolidiFI 版本 metadata 与编译器/Slither 的运行结果；不读文件名、目录名、注释、标签 | 已定 |
| D7 | 产物写入 `scripts/compile_repair/artifacts/` 下的新版本化存储；不修改 `graphs_v2_r1` 与任何 EdgeSem/NodeSem 产物 | 已定 |
| D8 | 哪个创新点使用这些图（DFG 预言机覆盖、NodeSem 的 SlithIR 特征、EdgeSem 的 IR 依赖边）以及是否存数据依赖 | 待定，CP2 之后再议 |

---

## 3. CompileRepair v1 方案

### 3.1 版本策略（D2）

对每个文件：

1. 计算合取区间 I：语义与 `scripts/DFG/state/stage_f/versioning.py::interval` 相同（所有 `pragma solidity` 取交集；`||` 与无法解析的表达式视为不支持）。实现时先 import 复用；如果它依赖的 tree-sitter 根节点无法在这里方便获得，按共享上下文的“复制并证明等价”规则处理。
2. metadata：若 DFG v2 输入记录中该文件有已校验的 recorded version（与 6c 相同来源），且版本在 I 内，作为第一候选。若 recorded version ≤ 0.4.11，记为 `metadata_below_slither_floor`，继续第 3 步。
3. 候选集合 C = 已安装且可信的版本 ∩ I ∩ [0.4.12, ∞) ∩ [lo, (lo 的主版本, lo 的小版本 + 1, 0))，其中 lo 是 I 的下界。按升序逐个尝试，第一个满足 D3 的版本即为选定版本。
4. 无 pragma（I 为 None）：先试 0.4.25（auto_version_solc 默认值，6c 已获用户批准），失败再按升序试 0.4.12–0.4.26。
5. 第 3 步全部失败且 I 跨越下一个小版本系列时，才在 I 内下一个系列按升序尝试，并记 `crossed_minor`（与 `versioning.py::mode_for` 拒绝跨 0.5.0 的口径一致；证据 3 中此情况为 0）。
6. 仍失败：记为失败，保留原因链，不修改源码，不进入产物图。

升序（取区间内最早可用的版本）的理由：最接近作者声明的下界；证据 6 表明两端版本的图结构相同，所以选择不影响节点与 IR。降序（取最新补丁）同样可辩护；若用户偏好降序，只改第 3 步排序，CP0 会给出两种排序下 source length 不同的文件数。

### 3.2 运行与清单

每个文件一条清单记录：文件路径与 SHA256、类别目录、I、origin（metadata / pragma / default）、规则 A 版本（仅作对照）、尝试过的版本及每次的 solc 结果与错误首行、选定版本、Slither 是否成功、节点总数、缺文件名节点数、标志（`metadata_below_slither_floor`、`crossed_minor`、`rule_version_outside_interval`、`moved_from_rule_version`）。

### 3.3 存储内容（CP2）

每个文件、每个声明的函数与修饰器：节点列表（key4 + source length + 节点类型 + SlithIR 字符串）、CFG 边（节点 → sons）、调用（internal / high-level / low-level / library，按目标 full_name）。数据依赖不在 v1 存储中，由 D8 决定。存储带 seal（文件清单与 SHA256）。

### 3.4 检查

- 回归：对 6c 已比较的 239 个文件，CP0 读取 6c 报告的结构后提出可比较的键（不预设字段名），CP2 证明 v1 存储在该键上与 6c 一致，或逐条解释差异。
- 跨版本不变性：对所有在 C 中至少有两个版本通过 D3 的文件，比较最低与最高版本的 key4 与 SlithIR（证据 6 的全量版本）。
- 分布审计：按类别目录统计 origin 与各标志的数量；不读标签。

---

## 4. Codex Prompts

### 4.1 共享上下文（每个会话先贴这一段）

```text
# 共享上下文（CompileRepair v1）

## 项目
在 MANDO-LLM 私有仓库上实现编译前端（CompileRepair v1）：为七类 source_files 语料的每个文件，按确定性版本策略选出 solc 版本，使 Slither 0.8.0 能生成完整（每个节点都有文件名与偏移）的 CFG/CG/SlithIR，并写出带 seal 的清单与存储。不修改任何源码，不调用 LLM。方案全文在 scripts/compile_repair/PROMPTS.md（第 0–3 节设计，第 4 节各 Prompt），证据在 scripts/compile_repair/artifacts/cr_pre_v1/README.md，有疑问先查它们。

工作树：使用独立的 git worktree，不要在 EdgeSem 工作树（/home/zhao/SmartContract/ge-sc-llm-ddg-v11）中切换分支。建议路径 /home/zhao/SmartContract/ge-sc-llm-compile。第一次开始前（在 EdgeSem 工作树中执行，只新增 worktree，不切换当前分支）：
  git fetch origin compile-repair
  git worktree add /home/zhao/SmartContract/ge-sc-llm-compile -b compile-repair origin/compile-repair
之后的提交都在 compile-repair 上。不要 push，除非用户明确要求。每个 Prompt 开始前先 git pull --ff-only origin compile-repair，读取最新的 PROMPTS.md。

环境（WSL）：
  conda activate mando
  cd /home/zhao/SmartContract/ge-sc-llm-compile
  export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
Python 3.7.12。代码必须兼容 Python 3.7：不要用 :=、list[str]/dict[str,int] 运行时注解、dict | dict、dataclass(slots=...)、match。
不得安装、升级或卸载任何包，不得下载编译器。需要新的 solc 版本时，列出版本与理由后停下，等用户授权（同 6c 的做法：授权后用 solc-select 安装，并核对 SHA256 与 Keccak256）。不得切换全局 solc 版本；一律传入可执行文件路径。

## 新代码位置
- 代码：scripts/compile_repair/（含 __init__.py）
- 测试：scripts/compile_repair/tests/（fixtures 在 scripts/compile_repair/tests/fixtures/）
- 产物：scripts/compile_repair/artifacts/<批次名>/，拒绝覆盖已存在目录。cr_pre_v1 是 Claude 的证据目录，只读。
- 进度：scripts/compile_repair/PROGRESS.md，每个 Prompt 结束追加一节（做了什么、文件清单、测试命令与结果、验收数字、遗留问题、与 PROMPTS.md 不一致之处及处理）。每个 Prompt 另写 scripts/compile_repair/CPn_REPORT.md，格式见 REPORT_TEMPLATE.md。同时在 HANDOVER.md 与 docs/training_changes_2026-10-07.md 末尾追加简短记录。三份记录文件只追加，不改旧文。

## 禁止修改（以及禁止新增）
1. scripts/DFG/** 下的任何文件，也不得在其中新增文件（experiment/run.py::_code_refs() 枚举其中的 .py）。
2. scripts/node_sem/**、scripts/edge_sem/**（本分支没有 edge_sem，也不得新建）。
3. 原作者代码：process_graphs/**、sco_models/**、node_classifier.py、graph_classifier.py、infer_smart_contract.py、experiments/*.py、auto_version_solc.py。
4. 语料 experiments/ge-sc-data/**（只读）；所有已有产物、图、标签、折、特征、checkpoint、plan/seal。
复用时用 import、子类化或组合。必须改变冻结函数的行为时，复制到 scripts/compile_repair，文件头写明来源路径与原文件 SHA256，并加测试证明在旧输入上与原函数输出相同。禁止 monkeypatch。

## 不变量
- 不写任何 .sol 文件到语料目录；需要临时文件时只在产物目录或系统临时目录中复制，且不修改内容（字节相同，SHA256 记录）。
- 版本策略只读：pragma 文本、DFG v2 输入记录中已校验的 recorded version、编译器与 Slither 的运行结果。不得读取文件名、目录名、注释、任何标签或预测文件来决定版本。类别目录只用于统计分组。
- 成功判据（D3）：solc 退出码 0；Slither 构造成功；所有 functions_and_modifiers_declared 的每个节点 source_mapping 的文件名等于输入文件、start 不为 None。
- 跨版本节点身份用 key4 =（合约名、函数 full_name、节点类型、起始字节偏移）；source length 只记录。
- 每次编译与 Slither 运行都记录：编译器版本、可执行文件 SHA256、命令、退出码、错误首行。
- 文档一律 UTF-8，用 Python 写文件；写完运行 python -B -m scripts.node_sem.doc_check --expect-cjk <文件>:<追加前字节数> ...（新文件不带字节数），不通过不得提交。

## 关键可复用模块（先读再用）
- scripts/DFG/state/stage_f/versioning.py（interval、recorded_version、mode_for）
- scripts/DFG/dfg_v2/validate_slither.py（inspect_environment、exact_version、compiler_for、slither_facts）
- scripts/DFG/dfg_v2/inputs.py（_check_metadata；6c 的 metadata 来源）
- auto_version_solc.py（规则 A，只作对照，不修改）
- scripts/compile_repair/artifacts/cr_pre_v1/（证据与参考脚本；不导入）

## 工作方式
- 每个 Prompt 只做它的范围。代码事实与本文不一致时以代码为准，在 PROGRESS.md 记录；如果影响方案（例如某个文件在 C 内没有任何版本满足 D3），停下来报告，不自行换方案，不修改源码。
- 每个 Prompt 结束时运行（CPU）：
  python -B -m pytest -q -p no:cacheprovider scripts/compile_repair/tests
  python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
  并核对：git status 中除 scripts/compile_repair/ 与两份记录文档外没有已跟踪文件改动；experiment.run._code_refs() 未变化。
  全部通过后 git commit，提交信息以 CPn 开头。
- 不启动任何 HGT 训练，不读写 GPU 锁。
- 失败就停，保留现场，不自动重试。
```

### 4.2 CP0：侦察与核对（只读）

```text
# CP0：侦察与核对（只读，不写策略代码）

产出 scripts/compile_repair/RECON.md、scripts/compile_repair/recon.json 与 scripts/compile_repair/CP0_REPORT.md；只读脚本放 scripts/compile_repair/recon/*.py。每条结论附命令、路径、SHA 或计数。

## 1. 输入身份
- 846 个 source_files 的路径与 SHA256 清单；与 cr_pre_v1/compile_repro.json 的文件集合逐一对照。
- 6c 报告与 seal 的 SHA256 是否与 PROMPTS.md 1.2 节一致；6c 的 256 个文件与本清单的对应关系（按 SHA256）。
- 6c 的 43 个 metadata 文件：来源记录在哪里（文件与字段），recorded version 的取值分布，其中 ≤ 0.4.11 的数量。

## 2. 与 6c 逐文件核对
- 从 6c 报告中列出 11 个 solc 失败与 6 个映射不可比文件（文件、所用版本、origin、错误首行）。
- 与 cr_pre_v1 的规则 A 结果逐一对照；每个差异说明原因（metadata、旧编译器可得性、调用方式等）。
- 读取 6c 报告的结构，提出 CP2 回归比较所用的键（只描述，不预设），说明它能否区分节点而不依赖 source length。

## 3. 编译器清单
- ~/.solc-select/artifacts 中已安装的版本、SHA256，与 trusted_compilers_complete.json 的对应。
- 按 PROMPTS.md 3.1 的候选集合 C，列出全部 846 个文件需要但未安装的版本（及涉及的文件数）。不要安装；需要时停下报告。

## 4. 编译矩阵（只用已安装可信版本）
- 对每个文件、C 中（以及无 pragma 时 0.4.12–0.4.26 中）每个已安装版本：solc 退出码与错误首行。调用方式与 validate_slither 一致（说明是否经 crytic-compile）。
- 统计：规则 A 通过/失败；按 3.1 升序与降序各自的选定版本；没有任何版本通过的文件（预期 0，若非 0 停下报告）；rule_version_outside_interval、moved_from_rule_version、crossed_minor 的数量。

## 5. Slither（只读运行，不写存储）
- 对每个文件用升序选定版本跑一次 Slither 0.8.0，按 D3 记录成功与缺文件名节点数。
- 对至少有两个版本通过 D3 的文件，再用该集合中的最高版本跑一次，比较 key4、SlithIR 与 source length（证据 6 的全量版本）。
- 记录每次运行的耗时，估计 CP2 全量运行的时间。

## 6. 结论
- 列出与本文第 0–3 节及 cr_pre_v1 证据不一致之处；每一处说明是否影响方案。影响方案的，停下报告。
- 给出 CP1 的参数：需要授权安装的编译器列表（如有）、升序与降序的差异数、回归比较键。
```

### 4.3 CP1：版本策略与运行器

```text
# CP1：版本策略、运行器与测试

前提：CP0 已通过审查；需要的编译器已由用户授权安装并核验（否则停下）。

## 1. scripts/compile_repair/policy.py
- interval(source_text)：合取区间，语义与 versioning.interval 相同；先尝试 import 复用，不能复用时按共享上下文规则复制并做等价测试（对 846 个文件逐一比较两者输出）。
- candidates(record, installed)：按 PROMPTS.md 3.1 第 2–5 步返回有序候选列表与每个候选的来源标签；排序方向由参数决定，默认按用户确认的 D2。
- 不读取文件名、目录名、注释或标签（加测试：同一源码以不同文件名与目录调用，候选列表相同）。

## 2. scripts/compile_repair/run.py
- 对单个文件按候选顺序执行 solc → Slither，第一个满足 D3 的版本为选定版本；记录 3.2 节清单字段。
- 输入只读复制到临时目录（字节相同，校验 SHA256）；不写语料目录。
- 命令行：--files 或 --all，--output 产物目录（拒绝覆盖），--order ascending|descending。

## 3. 测试 scripts/compile_repair/tests/
- 区间：`^`、`~`、`=`、`>=`/`<` 组合、两条 pragma、无 pragma、`||`（不支持）、空交集。
- 候选：metadata 在区间内 / 区间外 / ≤ 0.4.11；下界 < 0.4.12；开放上界被限制在下界小版本系列；crossed_minor 只在本系列全部失败时出现。
- D3：用 cr_pre_v1/probes 与一个 0.4.11 可编译的小合约构造“编译成功但缺文件名”的情形，断言判为失败并继续下一个候选（需要 0.4.11 已安装；未安装则该测试 skip 并在 PROGRESS 中记录）。
- 名字不变性测试（见第 1 节）。

## 4. 小样本运行
- 对 CP0 中规则 A 不通过的全部文件，以及每类随机（Random(0)，按文件 SHA256 排序后抽取）10 个通过文件，运行 run.py，产物 scripts/compile_repair/artifacts/cp1_sample_v1/。
- 验收：样本中 D3 失败数为 0；每个文件的选定版本与 CP0 第 4 节预测相同。

## 验收
测试全部通过；样本验收数字写入 CP1_REPORT.md。
```

### 4.4 CP2：全量运行、存储与检查

```text
# CP2：全量运行、存储、回归与审计

前提：CP1 已通过审查。

## 1. 全量运行
- run.py --all，产物 scripts/compile_repair/artifacts/cr_store_v1/：manifest.jsonl（3.2 节字段）、每文件的存储（3.3 节内容，格式在报告中给出 schema）、store.seal.json（全部产物文件的 SHA256、编译器与 Slither 版本、代码提交号）。
- 失败文件只进 manifest，不进存储；若失败数不为 0，停下报告。

## 2. 回归（对 6c 已比较的 239 个文件）
- 用 CP0 提出的比较键，证明 cr_store_v1 与 6c 报告一致；差异逐条列出并归因（例如所用版本不同）。不按 source length 判定差异。

## 3. 跨版本不变性
- 对所有至少两个版本满足 D3 的文件，比较最低与最高版本的 key4 与 SlithIR；报告相同数、不同数与全部不同的条目。

## 4. 分布审计
- 按类别目录统计 origin、选定版本小版本系列、各标志（metadata_below_slither_floor、crossed_minor、rule_version_outside_interval、moved_from_rule_version）的数量。不读标签。

## 验收
- D3 成功数 = 846（或停下报告的数字）；回归差异全部有归因；跨版本 key4 与 SlithIR 不同数为 0，或逐条列出；三份记录文档已追加。
```

---

## 5. 有触发条件的扩展（本版不执行）

只有在用户决定纳入新语料，并且对新语料执行 CP0 同样的侦察后，版本策略之后仍有失败文件时，才设计以下层。届时另起 r 版本，先做失败分类再决定启用哪一层。

| 层 | 触发条件 | 设计要点（来自 v1 方案与文献核对） |
|---|---|---|
| T2 依赖补全 | 新语料出现 `import` 且无法解析 | DAI 的“路径 + pragma”两步兼容检查，扩展到 0.4 时代的库发布（DAI 不支持 0.4）；DAppSCAN 的依赖图先编译叶子文件；离线库索引 |
| T1b pragma 槽 | 仅当作者声明区间内没有可用编译器 | 等长空格替换（证据 8 保持偏移）；只允许同一小版本系列；越过声明区间视为改写，排除 |
| T3 规则桩 | 缺声明（未声明标识符、缺基类、缺接口） | 只加声明、不加函数体（证据 8 可编译）；基类桩放在单独文件并经同长槽导入（基类必须先定义，证据 8）；桩节点打标记并在图中屏蔽 |
| T4 LLM 修复 | T3 后仍有失败且数量值得 | 只允许追加型补丁语言；多模型候选按编译与守卫择优（不用 CompileAgent 的字词重叠投票）；检索先用 solc 错误模板精确键（SmCFixer 的 SocR 权重未发布）；LLM 只见匿名 ID、注释被遮蔽 |
| 保真基准 | 启用 T3 或 T4 时 | 从可编译文件人为删除库/基类/接口，修复后与原图按 key4 比较；Trace 式仅靠提示的补全作为基线 |

---

## 6. 与其他分支的关系

- 本分支只新增 scripts/compile_repair/ 与两份记录文档的追加内容，与 edge-sem 没有文件交集。
- 接入某个创新点（D8）在 EdgeSem 完成并冻结结果之后进行：新建集成分支，图来源作为配置开关；EdgeSem 在旧存储上的结果作为基线。
