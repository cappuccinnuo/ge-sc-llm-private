"""Write the required CP2.4 report and handover, preserving historical bytes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
baseline = json.loads((OUT / "baseline.json").read_text())
tests = json.loads((OUT / "test_acceptance.json").read_text())["tests"]
cli = json.loads((OUT / "cli_acceptance.json").read_text())
eq = json.loads((OUT / "equivalence.json").read_text())
assert eq["environments_equal"]
head = baseline["head"]

def append(path, text):
    p = ROOT / path
    assert p.stat().st_size == baseline["docs"][path], "Already appended: " + path
    with p.open("a", encoding="utf8") as stream:
        stream.write("\n\n" + text.strip() + "\n")

summary_lines = "\n".join("| " + name + " | " + value["summary"] + " | pytest_" + name + ".json / .log.gz |"
                           for name, value in tests.items())
report = """## CP2.4：pragma 内注释与未结束指令（2026-11-17，修改 AI：Codex）

### 实现与范围

按用户要求先读共享上下文，再通读 PROMPTS r2.12（尤其 §1.15、§3.3、§3.10、§4.4e），以及 HANDOVER §0–5、DECISIONS、CHANGE_LOG §25/26、记录模板和 cp2_3_review_v1/README、edge_cases。git pull --ff-only origin compile-repair 返回 Already up to date；起始 HEAD 为 __HEAD__。新批次只有 artifacts/cp2_4_v1；CP0–CP2.3 原产物和已审查结论保留。

生产仅修改 rules/environment.py 的 _pragma_spans 和 pragma_interval，共 +5/-4 行（含说明文字），生产文件仍为 14。前者遇到分号之前的左/右花括号或文件结束时，抛出 F: unterminated pragma directive；后者从 code_only 的等长遮盖字节中读取同一区间的表达式，再交给原 _expression_interval。pragma_patches 仍使用原始字节，不改变区间、替换内容、CRLF 或后续源码偏移。pipeline、选版策略、metadata、D3、key5、settings_retry 和图存储均不改。

新增 tests/test_pragma_comments.py（15 个测试实例）与 tests/fixtures/pragma_comments 下 comment_inside、line_comment_inside、missing_semicolon 三个原样夹具。旧 test_pragma_bytes.py 只追加两个新注释夹具的明确例外：先证明冻结 interval 抛 Unsupported，再交给新测试验证预期成功；所有旧夹具的冻结比较保留。夹具来源和 SHA256 见 fixture_sources.json。CP2.3 参照保存为 environment_cp23.py，SHA256=f0d4f4b9274532c0b3760d67341f37dba7f2f81430d9aad091f42644483429e0，与起始提交原文件逐字节相同；只在测试中载入，不用于生产或替换冻结函数。

### 真实验收

| 项目 | 预期与实测 | 证据（artifacts/cp2_4_v1/） |
|---|---|---|
| 修改前复现 | 两种注释分别在 solc 0.8.0/0.5.17 rc0、生产 D3 成立，但旧模块拒绝；缺分号在 0.5.17 报 Expected ';' but got end of source；四个 CLI 输入均旧同一错误且不编译 | reproduction.json、reproduction_invocations.jsonl、reproduction_cli/ |
| MANDO 等价 | 两环境各 846/846：pragma_interval、完整 Patch 和 EnvironmentPlan 全字段相同；升降序各比较一次 | equivalence.json、test_evidence_*.json.gz |
| 夹具等价 | 当前 39 文件中原 CP2.3 能读取的 35/35 全同；4 个异常文件明确列出：两个注释、缺分号、既有并集 | 同上 |
| 计划字段 | interval、effective_interval、origin、groups、priority、flags、inference、override 全部比较；每环境 881 个输入、1,762 份计划 | 同上 |
| 块注释 CLI | [0.8.0, 0.9.0)，选 0.8.0；solc rc0、production D3，源码零改动 | cli_acceptance.json |
| 行注释 CLI | [0.5.0, 0.6.0)，选 0.5.0；solc rc0、production D3，源码零改动 | 同上 |
| 缺分号 CLI | unrepaired、unsupported_version_constraints；error_first_line=F: unterminated pragma directive；没有工具调用 | 同上 |
| 并集 CLI | 标志不变；error_first_line=F: unsupported pragma expression；没有工具调用 | 同上 |
| 其他错误 | 非法表达式与空交集消息不变；左右花括号/EOF、伪分隔符、CRLF/Latin-1、原始补丁字节均有测试 | test_pragma_comments.py |
| 代码边界 | 非测试生产文件 14，仅 environment.py 两个函数改动；其余函数 AST、模块、DFG 引用保护 | frozen_audit.json、code_change_summary.json |

本轮未重跑 846 全量生产编译；这是 §4.4e 明确规定的验收方式，完整 make_plan 相同加其他生产代码不变，证明本次改动未改变这些输入的选版计划。上轮 843 成功/3 个已知失败、843 图字节相同是 CP2.3 的历史结论，不标作本轮重测。6c 回归未重放。

### 测试与开发记录

| 环境/测试 | 实测 | 证据 |
|---|---|---|
__TESTS__

两环境的 CP2.4 等价明细完全相同。production 的 6 个跳过是 Python 3.7 回退或 regression_6c 专用；mando 的 447 个跳过由生产 profile 或 Python >=3.8 条件触发。DFG v2 在 mando 运行，既有 warning 明细保存在日志。pytest 全部首轮通过，无失败后自动重试；没有额外重跑成功的 CLI，只读审计和打包其原产物。

开发记录见 development_issues.json：Windows rg 读取 WSL UNC 返回 os error 5，改用 WSL Python/git 读取，未改权限或网络配置；不是自动审批拒绝。旧冻结测试对新注释夹具的失败预期需与 r2.12 的有意偏离一致，因此明确记录两项例外并保留所有既有输入的等价断言。此处理在正式测试前完成，没有放宽验收。没有发现需先咨询的新替代方案。

### 归档与复现

production 为 Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；mando 为 Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。runtime.json 是现场版本记录。可信安装 96 个，其中支持范围 92 个；工具信任链和每次 solc 路径、SHA256、命令、退出码、诊断、耗时、费用均在 invocations 和 CLI seal。CPU，OMP/MKL=2，费用 0，无 LLM。

新 CLI 存储归档 cli_acceptance_store.tar.gz，SHA256=__TAR__，__MEMBERS__ 个成员回读一致；seal SHA256=__SEAL__。其两成功、两预期拒绝共 2 次 solc 和 2 次 Slither，拒绝输入调用数 0。旧代码和旧产物按 baseline/frozen_audit 校验；新证据的最终哈希清单见 evidence_seal.json，精确交付清单见 delivery_inventory.json。原临时结果保留，不清理历史文件。

从仓库根可复现测试（输出使用新的批次或临时目录，不覆盖 cp2_4_v1）：

    export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
    /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
    /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider scripts/DFG/dfg_v2/tests

实际命令、独立临时目录和运行耗时以 pytest_*.json 为准。reproduce.py 用于修改前复现并校验旧实现哈希，当前新实现上不得再运行；audit_results.py 只读已有结果，写新证据时拒绝覆盖。doc_check 检查本轮六份文档；结果在 doc_check_v*_invocation.json，CHANGE_LOG §27.5 补记。

### 用户授权、差异与停止位置

用户 2026-11-17 明确要求执行更新文档的 CP2.4。本轮按 r2.12 授权，有意偏离冻结实现的两个拒绝行为：pragma 内注释现在接受；未结束指令仍拒绝但消息单列。已追加 DECISIONS 历史；既有 D3/D5/D16/D18/D20/D20a 状态和其他待定决定保持。未提出或实施方案外替代方案。

仅登记既有问题：六个测试模块的本机路径依赖，在 CI/迁移时处理；并集 pragma 与 Slither 进程内超时留后续 CP3 分类。不安装、不下载、不调用 LLM、不启动训练或读写 GPU 锁，不切换全局 solc。CP2.4 本机验收通过，完成记录、完整性和 doc_check 后本地提交；提交号见 git log，不自动 push。停止于待独立审查，CP3 未开始。
"""
report = report.replace("__HEAD__", head).replace("__TESTS__", summary_lines).replace("__TAR__", cli["archive_sha256"]).replace("__MEMBERS__", str(cli["archive_members"])).replace("__SEAL__", cli["seal_sha256"])
append("compile_repair/CP2_REPORT.md", report)

change = """## 27. 2026-11-17 CompileRepair CP2.4：读取 pragma 注释并区分未结束指令（修改 AI：Codex）

### 27.1 任务、依据与范围

用户明确要求执行更新 PROMPTS 的 CP2.4，先读 §4.1、通读全文，若有实质替代方案须先咨询并记录。已执行 git pull --ff-only origin compile-repair，返回 Already up to date，起始 __HEAD__；已读 r2.12 全文、HANDOVER §0–5、DECISIONS、本文 §25/26、docs/README、REPORT_TEMPLATE 和 cp2_3_review_v1 的 README/edge_cases。工作树保持 ge-sc-llm-compile；先建立 baseline 并复现，再改生产代码。

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
"""
append("compile_repair/docs/CHANGE_LOG.md", change.replace("__HEAD__", head))

progress = """## 2026-11-17 CP2.4 完成：pragma 注释与未结束指令（修改 AI：Codex）

按 PROMPTS r2.12 §4.4e，起点 compile-repair@__HEAD__，pull 为 Already up to date。生产只改 rules/environment.py 两函数（+5/-4 行，生产文件 14），从遮盖后的字节读取版本表达式，并区分未结束 pragma。新增 test_pragma_comments.py、三个 pragma_comments 夹具，旧 test_pragma_bytes.py 显式登记两个新夹具的冻结拒绝边界；测试参照为经 SHA 校验的 CP2.3 原文件。pipeline、D3、D5、key5、settings、原始补丁区间及字节不变。

新批次 cp2_4_v1，修改前复现符合审查；两环境各 846 MANDO + 35 可读取夹具的 interval、Patch、EnvironmentPlan 八字段全同，升降序各一份，合计每环境 1,762 份计划。两个新注释 CLI 成功（0.8.0 / 0.5.0），源码不变；缺分号和 union 分别记录 unterminated pragma directive / unsupported pragma expression，均不调用编译器。验收证据为 equivalence.json、cli_acceptance.json、cli_acceptance_store.tar.gz。

production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG v2 2653 passed/9 warnings。命令均为指定环境 python -B -m pytest -q -ra -x -p no:cacheprovider，目标和独立临时目录见 pytest_*.json；没有失败后重跑。完整性与 doc_check 见 frozen_audit.json、doc_check_v*。CP2_REPORT 已追加 CP2.4；CHANGE_LOG §27、HANDOVER 与 DECISIONS 已同步，完整文件清单见 delivery_inventory.json。

与冻结实现的两项有意偏离由 r2.12 明确要求，未提出新的替代方案或放宽判据。UNC 文件访问问题通过 WSL 读取解决；旧冻结测试的两个新夹具例外明确断言并单独验收，详见 development_issues.json。既有测试可移植性、union 和 Slither 超时仍登记在后续边界。本轮不重跑全量生产或 6c，不安装/下载/LLM/训练，不切全局 solc；本地提交后待独立审查，未自动 push，CP3 未开始。
"""
append("compile_repair/PROGRESS.md", progress.replace("__HEAD__", head))

decision = """### CP2.4 执行：冻结拒绝行为的有意偏离（2026-11-17，修改 AI：Codex）

用户明确要求执行更新后的 CP2.4；按 PROMPTS r2.12 §4.4e 和上方审查历史实施。pragma 的约束表达式从 code_only 等长遮盖字节读取，因此旧冻结实现拒绝、而 solc 接受的块/行注释输入现在通过；已识别指令在分号前遇花括号或 EOF 仍被拒绝，error_first_line 改为 F: unterminated pragma directive。标志仍为 unsupported_version_constraints，union/无法解析/空交集的原消息不变，pragma_patches 原始区间和字节保持。

此为已要求的有意偏离，不是新的策略决定：两个环境各 846 MANDO 与 35 个 CP2.3 可读取夹具，区间、完整补丁、EnvironmentPlan 八字段在升降序下全部相同。两个注释 CLI 成功且无源码改动；缺分号和 union 在编译前分别记录预期错误。证据：cp2_4_v1/equivalence.json、cli_acceptance.json；CP2_REPORT 的 CP2.4、CHANGE_LOG §27。生产仅 environment.py 两函数修改，其他决定表与历史保持，未提出额外替代方案；本机验收完成，等待独立审查，CP3 未开始。
"""
append("compile_repair/docs/DECISIONS.md", decision)

handover = """# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.12（§1.15、§4.4e CP2.4、§4.5 CP3）、CP2_REPORT 的 CP2.4、CHANGE_LOG §27、DECISIONS 和 artifacts/cp2_4_v1/README.md。第 6 节历史只追加，记录规则见 README.md。

## 0. 一句话

CP2.4 已完成本机验收并待独立审查：pragma 内块/行注释可以读取，未结束指令单列错误；两环境 846 MANDO 与 35 可读取夹具的完整计划保持，CLI 两正两负通过。顺序：CP2.4 审查通过后再进入 CP3。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案与决定 | PROMPTS r2.12；既有决定状态保持；新增有意偏离执行记录 | PROMPTS、DECISIONS |
| CP0–CP2.3 | 已审查通过；6c 239/239 已结束，不重放 | 各审查目录 |
| CP2.4 实现 | 仅 environment.py 两函数，表达式遮盖读取、未结束 pragma 独立消息；生产 14 文件 | code_change_summary.json |
| 等价 | production/mando 各 846 MANDO + 35 可读取夹具，interval/Patch/完整 EnvironmentPlan 全同；每环境 1,762 份升降序计划 | cp2_4_v1/equivalence.json |
| 生产 CLI | 两种注释成功且零改动，缺分号/union 两错误区分且不编译 | cli_acceptance.json |
| 测试 | production 622/6，mando 181/447（通过/跳过）；DFG 2653 通过、9 warnings | test_acceptance.json |
| 测试可移植性 | 6 个模块在用户本机之外收集失败（既有）；CI/迁移时处理，本轮不扩范围 | r2.12、development_issues.json |
| 分支 | 继续 compile-repair；5080 主线导入改动在迁移时合并 | PROMPTS r2.11 |
| 下一步 | CP2.4 独立审查；CP3 未开始 | §4.4e 与本轮停止边界 |

## 2. 分支与工作树

工作树 /home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair。CP2.4 pull --ff-only 返回 Already up to date，起始 HEAD=__HEAD__。本轮完成记录与检查后本地提交；提交号见 git log，不自动 push。

新批次仅 cp2_4_v1。CP0–CP2.3 旧产物保持，不重跑 v5 或 6c，不覆盖旧记录。按 delivery_inventory 精确暂存；历史未跟踪文件和原测试临时产物保留，不递归 force-add 旧树。当前没有执行 5080 主线迁移。

## 3. 环境

production=/home/zhao/miniconda3/envs/compile-repair-production，Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；mando Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。本轮 runtime.json 现场核对；可信 solc 96 个，其中 92 个支持版本，没有安装、下载或切全局版本。

从仓库根运行，PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。全部 CPU，费用 0；无 HGT/LLM/GPU 锁操作，无网络配置变化。

## 4. 必读事项（当前边界）

1. 目标是未来检测时任意合约；MANDO 846 仅回归，不根据标签选版。
2. CP2.4 表达式从 code_only 后的同一区间读取；_pragma_spans 仍是 interval/patches 共用的顶层定位。pragma_patches 保留原始字节、CRLF 与偏移。
3. 未结束 pragma 的 error_first_line 是 F: unterminated pragma directive，flags 仍为 unsupported_version_constraints。CP3 据此细分解析错误；本轮不补分号、不修原文。
4. union、非法表达式与空交集消息保持；pipeline、known version、D3、D5、key5、settings_retry、图格式不改。
5. 本轮等价参照为经 SHA 校验的 environment_cp23.py，只在测试中载入；冻结 interval 等价测试保留所有旧比较，新注释两夹具明确证明旧拒绝并另验新行为。
6. 当前 39 夹具中原 CP2.3 可读取 35；两个注释、缺分号和旧 union 不计作原可读取输入，全部单独测试，不能把排除写成原实现通过。
7. 每环境 846 个回归输入的完整 make_plan 相同，依 §4.4e 不重跑全量编译。CP2.3 的 v5 843 成功/3 旧失败、843 图同是历史结论。
8. 6c 已完成 D20/D20a；不重放、不新增采样、不变更其历史判据。
9. 旧 cp0_1_compilers_v1 首次 seal 被 seal_v2 替代的说明保持。新 baseline 沿用已核对的旧 seal 集合并加入 v5，未重解释旧证据。
10. 所有旧跟踪/封存文件、两环境和 solc、DFG _code_refs、非目标函数按 baseline/frozen_audit 校验。新 CLI seal 的 14 文件指纹必须与当前实现相同。
11. docs/CHANGE_LOG 是本模块的训练改变/运行记录，根目录两份文档不改；HANDOVER §6 和旧报告仅追加。
12. CP2.4 本机验收完成尚不等于独立审查；审查前不进入 CP3。任何方案外调整先咨询用户并记录，测试可移植性和 Slither 超时等既有事项按既定后续范围处理。

## 5. 关键路径

| 内容（compile_repair 下） | 路径 |
|---|---|
| 本轮报告与详细记录 | CP2_REPORT.md 的 CP2.4；docs/CHANGE_LOG.md §27 |
| 证据总览 | artifacts/cp2_4_v1/README.md |
| 旧实现复现 | cp2_4_v1/reproduction.json、reproduction_invocations.jsonl、reproduction_cli/ |
| 参照与来源 | cp2_4_v1/environment_cp23.py、fixture_sources.json、baseline.json |
| 等价明细 | cp2_4_v1/equivalence.json、test_evidence_production.json.gz、test_evidence_mando.json.gz |
| CLI 验收 | cp2_4_v1/cli_acceptance.json、cli_acceptance_store.tar.gz |
| 测试、问题与完整性 | cp2_4_v1/pytest_*、test_acceptance.json、development_issues.json、frozen_audit.json |
| 文档与交付 | cp2_4_v1/doc_check_v*、evidence_seal.json、delivery_inventory.json |
| 审查依据（只读） | artifacts/cp2_3_review_v1/README.md、edge_cases/ |
| 历史生产存储（未重跑） | artifacts/cr_store_mando_v5/store.tar.gz、cr_store_mando_v3/store.tar.gz |

---

"""
p = ROOT / "compile_repair/docs/HANDOVER.md"
assert p.stat().st_size == baseline["docs"]["compile_repair/docs/HANDOVER.md"]
original = p.read_text()
history = original[original.index("## 6. "):]
entry = """### 2026-11-17 CompileRepair CP2.4 完成（修改 AI：Codex）

在 compile-repair@__HEAD__ 开始，pull --ff-only 为 Already up to date，先读共享上下文和 PROMPTS r2.12 全文、HANDOVER §0–5、DECISIONS、CHANGE_LOG §25/26 与审查 README/edge_cases。生产只改 environment.py 两函数，共 +5/-4 行，生产文件仍为 14；新增三个 pragma_comments 夹具与 test_pragma_comments.py，旧 test_pragma_bytes.py 精确登记新注释夹具的冻结异常边界。所有新证据写 cp2_4_v1，旧产物/语料/scripts 不变。本轮更新本文开头、第 0 节摘要、第 1 节状态、第 2 节起点与批次、第 3 节环境依据、第 4 节当前边界、第 5 节关键路径；此前第 6 节原字节保留。

旧模块拒绝两类 solc/Slither 可接受注释输入、且缺分号与 union 消息相同，均已复现。修改后两注释生产 CLI 成功（0.8.0/0.5.0）并保持源码原字节；两种拒绝消息正确且不调用编译器。两环境各 846 MANDO 与 35 个 CP2.3 可读取夹具的区间、完整补丁与 EnvironmentPlan 八字段全部相同，升降序共每环境 1,762 份计划；四个旧拒绝输入明确单列。证据见 equivalence.json、cli_acceptance.json，CLI 归档 21 成员回读一致。

r2.12 明确要求的有意偏离已记入 DECISIONS；既有决定状态、失败标志和策略不改。没有新的替代方案或验收偏差；开发文件访问处理与测试例外说明已记录于 development_issues.json、CHANGE_LOG §27。六模块测试可移植性、union 和 Slither 超时仍是既有后续事项，不提前实现。停止于本机验收完成、待独立审查；CP3 尚未开始。

production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG 2653 passed/9 warnings；完整命令和耗时见 pytest_*.json。六份文档按 doc_check 核验，最终结果及完整性记录见 doc_check_v*、frozen_audit.json；强制记录通过后本地提交，提交号见 git log，不自动 push。无下载、安装、LLM、训练、GPU 锁或全局 solc/网络改动。按 §4.4e 不重跑全量生产，6c 已完成且不重放。
"""
p.write_text(handover.replace("__HEAD__", head) + history + "\n\n" + entry.replace("__HEAD__", head).strip() + "\n", encoding="utf8")

readme = """# cp2_4_v1：pragma 注释与未结束指令验收（修改 AI：Codex）

本批次按 PROMPTS r2.12 §4.4e 执行。旧批次只读；生产只改 environment.py，使用已有 production/mando 环境和 92 个支持版本，不安装或下载。完整说明在 CP2_REPORT 的 CP2.4、CHANGE_LOG §27，当前状态为本机验收通过、待独立审查。

| 文件 | 用途 |
|---|---|
| baseline.json、environment_cp23.py | 起始跟踪/封存/环境哈希；测试专用 CP2.3 原实现快照 |
| fixture_sources.json、reuse_sources.json | 三个原样夹具与复用驱动的来源 SHA |
| reproduce.py、reproduction.json、reproduction_invocations.jsonl、reproduction_cli/ | 修改前复现；两注释直接工具成功、旧 CLI 拒绝，缺分号与 union 旧消息相同 |
| run_checks.py、pytest_*.json / .log.gz、test_evidence_*.json.gz | 两环境模块与 DFG 测试命令、日志和明细 |
| equivalence.json | 每环境 846 MANDO + 35 可读取夹具，1,762 份完整计划全同；4 个原拒绝输入明列 |
| cli_acceptance.json、cli_acceptance_store.tar.gz | 原测试 CLI 的两正两负结果；21 成员逐个回读，无重复运行 |
| runtime.json、development_issues.json | 现场版本、开发处理与既有待处理问题 |
| audit_results.py、audit_frozen.py、code_change_summary.json、frozen_audit.json | 只读验收与保护检查，生产文件数及函数改动 |
| write_documents.py、check_docs.py、doc_check_v* | UTF-8 文档写入与检查；旧记录按字节前缀保护 |
| evidence_seal.json、delivery_inventory.json | 本轮证据与精确交付清单（不包含这些文件自身的循环哈希） |

测试：production 622 passed/6 skipped，mando 181 passed/447 skipped，DFG 2653 passed/9 warnings。两注释 CLI 分别选 0.8.0、0.5.0，D3 成立，源码不变；缺分号和 union 保留同一 flags、不同 error_first_line，工具调用为零。原始临时目录与调用参数见 pytest_*.json，旧 846 全量生产与 6c 本轮未运行。

复现测试命令见 CP2_REPORT；从仓库根设置 PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2 和既有 TREE_SITTER_LIB_DIR。各驱动输出拒绝覆盖，后续需新建批次；reproduce.py 必须在未修改的 CP2.3 实现上运行，当前实现不能通过其旧代码哈希检查。原文件和临时结果保留，未清理历史未跟踪内容。

成本 0；无 LLM、下载、安装、训练、GPU 锁或全局 solc 选择。两项语义偏离由 CP2.4 明确授权，详见 DECISIONS；没有方案外调整。
"""
with (OUT / "README.md").open("x", encoding="utf8") as f:
    f.write(readme.strip() + "\n")
print("Wrote six CP2.4 documents; old history retained.")
