from pathlib import Path
import json

root=Path.cwd()
out=root/"compile_repair/artifacts/cp2_3_v1"
baseline=json.loads((out/"baseline.json").read_text())
reg=json.loads((out/"regression.json").read_text())
archive=json.loads((out/"cr_store_mando_v5_archive_audit.json").read_text())
assert reg["passed"] and archive["readback_equal"]
head=baseline["head"]
seal=reg["seal_sha256"]
tar_sha=archive["archive_sha256"]
for name,entry in baseline["docs"].items():
    assert (root/name).stat().st_size==entry["bytes"], "Document changed before append: "+name

def append(relative, text):
    with (root/relative).open("a",encoding="utf8") as f:
        f.write("\n\n"+text.strip()+"\n")

report=f"""## CP2.3：独立读取 pragma 与接受非 UTF-8 输入（2026-11-17，修改 AI：Codex）

### 实现与范围

执行 PROMPTS r2.11 §4.4d；先读 §4.1，再完整阅读 PROMPTS、HANDOVER §0–5、DECISIONS、CHANGE_LOG §23/24、docs/README、REPORT_TEMPLATE 与 cp2_2_review_v1/README、probe_inputs.json。compile-repair 上 git pull --ff-only origin compile-repair 返回 Already up to date，起始 HEAD={head}。本轮仅修改 rules/environment.py 与 pipeline.py，生产文件保持 14；不迁移到 rtx5080-rebuild。

rules/environment.py 新增共用 _pragma_spans：在 code_only 等长遮盖注释/字符串后的字节上识别 Solidity pragma，仅接受花括号深度为 0 的指令，返回原字节区间；pragma_interval 与 pragma_patches 共用定位。新 _expression_interval 仅复制冻结 stage_f/versioning.py 的表达式求值（原 SHA256=130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18），保留 ^、~、关系运算、补丁版加一、空交集与不支持表达式的异常语义；冻结 interval 与 parse 只在本轮等价测试中调用，不改原模块。定位失败不会触发整文件解析；已识别但缺少分号的 pragma 抛 Unsupported，其他语法留编译器判定。

版本表达式与 infer_interval 使用无损 Latin-1 解码，pragma 改写保持字节处理、等长空格、CR/LF 与原偏移。pipeline.repair_unit 只捕获 Unsupported 为 unsupported_version_constraints，不再把 UnicodeDecodeError 归为该标志。mando_known_version 的 UTF-8/元数据哈希校验、D3/D5/key5、存储格式、settings_retry 均保持；原始源码只读。

| 生产文件/函数 | 新增行 | 删除行 |
|---|---:|---:|
| environment.py::_pragma_spans（新增） | 22 | 0 |
| environment.py::_expression_interval（新增） | 30 | 0 |
| environment.py::pragma_interval | 9 | 3 |
| environment.py::infer_interval | 1 | 1 |
| environment.py::pragma_patches | 4 | 7 |
| pipeline.py::repair_unit | 1 | 1 |

函数行数按函数正文差异统计；文件级 git diff --numstat 含导入、模块说明与空行：environment.py +72/-15，pipeline.py +1/-1，共 +73/-16。证据 code_change_summary.json。新增 tests/test_pragma_bytes.py；新增 tests/fixtures/pragma_inputs/ 下 latin1_comment.sol、no_pragma_latin1.sol、masked_pragma.sol、two_pragmas.sol、nested_pragma.sol、union_pragma.sol。Latin-1 注释夹具逐字节复制自审查目录（SHA256=18b5d22ac65f1f5895bc244cf590f3c53afca54ae4d7900fd5087c23f4af5aed），旧夹具不改。

### 真实验收

| 验收项 | 预期与实测 | 证据（artifacts/cp2_3_v1 下） |
|---|---|---|
| 修改前复现 | 5 个新语法输入抛 Unsupported、Latin-1 输入抛 UnicodeDecodeError；6 个 CLI 输入均拒绝 | reproduction.json、reproduction_cli |
| 直接工具对照 | 5 个新语法在 0.8.38；Latin-1 在 0.4.24/0.5.17/0.8.0/0.8.38；9/9 solc rc0、production D3 成立 | reproduction_invocations.jsonl |
| MANDO 冻结等价 | 两环境各 846/846 区间与异常类型、pragma 补丁字节区间相同 | equivalence.json、test_evidence_*.json.gz |
| 全部可解析夹具 | 36 个文件中冻结 parse/UTF-8 路径可处理 28 个，28/28 相同；其余 8 个明列原因 | 同上 fixtures/excluded |
| 生产 CLI 正例 | 9/9 成功、D3 成立、无源码改动；含要求的 6 个输入及伪 pragma、双 pragma、无 pragma Latin-1 对照 | probes.json、cli_probe_stores.tar.gz |
| 不支持的并集 | 含双竖线的 pragma 仍记录 unsupported_version_constraints，调用编译器 0 次 | 同上 unsupported 存储 |
| 顶层与字节边界 | 合约体内 pragma 不计；注释/字符串不计；双 pragma 交集、反向补丁、CR/LF/字节偏移、非 UTF-8 推断均通过 | test_pragma_bytes.py、pytest_* |
| 全量 production | 846 个输入，843 success、3 已知 slither_side_failure；92 个支持版本 | regression.json |
| 与 v3 记录相同 | 状态、reason、选定版本、设置、标志各 846/846 | regression_acceptance.jsonl |
| 与 v3 图相同 | 843/843 graph.json 字节相同；差异 0；失败输入没有 graph | 同上 |
| 6c | 本 CP 不重放，新增抽取 0 | 执行入口与记录 |

8 个不纳入冻结等价的夹具是原 5 个新语法、两个 Latin-1 文件及故意将 pragma 放在 contract 体内的非法夹具；它们有独立正/负测试，不把排除写成通过。13 组运算符/无效约束还直接与冻结表达式求值器比较，覆盖 ^0.0.x、^1.x、各关系符、缺补丁版、不支持表达式、空交集与并集。

CLI 选版依次为：using_global 0.8.13、user_operator 0.8.19、transient 0.8.28、file_event 0.8.22、layout_at 0.8.29、latin1_comment 0.4.24、masked_pragma 0.5.0、two_pragmas 0.5.1、no_pragma_latin1 0.4.16。全部由原升序策略选择；未指定回归标签或 known version，不靠文件名选版。嵌套 pragma 夹具只验证定位忽略，未声称它可编译。

v5 使用与 v3 相同顺序、同一 CLI、--regression mando --order ascending；三份已知失败仍为 reentrancy_bonus.sol、reentrancy_cross_function.sol、reentrancy_insecure.sol。repair CLI 返回 2 表示这三份未修复，严格逐文件验收驱动返回 0。运行耗时 {reg["elapsed_seconds"]:.2f} 秒（外层 241.22 秒）；不读取标签，不重跑已完成的旧批次。

### 测试与开发记录

production 模块 607 passed/6 skipped，69.72 秒；mando 模块 167 passed/446 skipped，13.33 秒；mando DFG v2 2653 passed/9 条既有弃用警告，150.01 秒。模块共 613 项，新增 22 项；生产的 6 个跳过为旧 profile/backport 专属，mando 的 446 个跳过为生产 profile/标准库专属。两个环境均运行等价测试；分层测试通过。详见 pytest_production/mando/dfg.json 与无损日志。生产 CLI 测试的已成功结果经 audit_tests 只读复算、原字节打包，没有为出报告重复编译。

基线准备首次遍历所有名为 seal.json 的旧文件时，发现 cp0_1_compilers_v1/README.md 与首次 seal 的哈希不同。其 README 已明确首次 seal 被 seal_v2.json 替代；当前 README 与上一轮基线及 seal_v2 均相同，最终 seal SHA=36724427a5c88c4c6c4b5e2d63f92a5d6c5216e317b674bebc0005ee830e7d6f。处理为：所有旧跟踪文件按起始 HEAD 保护，沿用前轮已审计的结果 seal 成员集合并加入 CP2.2 新存储；没有修改旧证据或放宽 CP2.3 验收。现场与依据见 development_issues.json。文档首次写入命令超过 Windows 创建进程的长度限制（os error 206），进程未启动、文档未变；改为分块写入本批 write_documents.py 后执行，并保留问题记录。正式复现、测试、CLI 正负例与全量回归均无意外失败、无自动重试；没有审批拒绝。

没有发现需要改变 CP2.3 方案的实质问题。本轮未实施替代方案。既有两项缺口继续登记而未处理：并集 pragma 仍不支持，Slither 进程内仍无超时；按 r2.11 留 CP3 分类并提出后续实现方案。9 个正例与 846 回归通过不证明任意源码、任意未来版本或图语义已穷举。

### 归档与复现

新批次 cp2_3_v1 保存复现、基线、测试、逐份比较、归档审计与记录；cr_store_mando_v5 保存新 production 存储。v5 seal SHA256={seal}；4,228 文件加 seal 共 4,229 成员，无损 store.tar.gz 为 {archive["archive_bytes"]} 字节，SHA256={tar_sha}，逐成员回读相同。9 个正例和 1 个负例的 CLI 存储另打包为 cli_probe_stores.tar.gz（58 成员），不依赖临时目录长期存在；SHA 与成员清单见 probes.json。完整交付文件与哈希见 delivery_inventory、delivery_seal。

production Python 3.10.21/Slither 0.11.6/crytic-compile 0.4.2；mando Python 3.7.12/0.8.0/0.2.4。OMP/MKL=2，全部 CPU，未测峰值资源。运行环境见 runtime.json；每次编译器绝对路径、版本/SHA、命令、设置、耗时、rc 与 profile 见 invocations、trust、seal 和测试存储；费用 0、LLM 调用 0。

以下是本次实际执行入口，批次文件均拒绝覆盖；只读审查直接读取已有产物，不重跑。完整 846 个输入路径的 CLI argv 见 regression_plan.json。

    cd /home/zhao/SmartContract/ge-sc-llm-compile
    export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
    export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py reproduction
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py production
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py mando
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/run_checks.py dfg
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py probes
    /home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp2_3_v1/launch_phase.py regression

### 停止位置与后续边界

CP2.3 本机功能和回归验收通过，待独立审查后进入 CP3。6c 已结束，不新增采样；D3/D5/D20/D20a 与其他既有决定不变。没有安装、下载编译器/依赖/语料/文档、LLM、训练、GPU 锁、全局 solc 或网络配置变更。强制记录及最终检查完成后本地提交，实际提交号见 git log；本轮不自动 push。doc_check 与最终完整性结果在文末补记。"""
append("compile_repair/CP2_REPORT.md",report)

change=f"""## 25. 2026-11-17 CompileRepair CP2.3：修复字节级版本读取并保持回归（修改 AI：Codex）

### 25.1 任务、依据与范围

用户要求执行更新后的 CP2.3，先读共享上下文、通读 PROMPTS；实质方案改变先咨询并记录。执行 r2.11 §4.4d；起点 compile-repair@{head}，git pull --ff-only origin compile-repair 为 Already up to date。已读 PROMPTS 全文、HANDOVER §0–5、DECISIONS、本文 §23/24、docs/README、REPORT_TEMPLATE 与 cp2_2_review_v1 的 README/probe_inputs。先记录 baseline，再复现旧代码，随后修改。

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

原始输入身份取自 cp0_v2/recon.json（SHA256=bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6），846 源码逐一验哈希；回归原参照 v3 seal 首先验全体成员。新 v5 用时 {reg["elapsed_seconds"]:.2f} 秒，外层 241.22 秒；3 个失败仍是 reentrancy_bonus/reentrancy_cross_function/reentrancy_insecure，不写 graph。CLI rc2、验收驱动 rc0 均符合预期。v5 seal={seal}；tar={tar_sha}，{archive["archive_bytes"]} 字节、4,229 成员。每次调用的路径/版本/参数/耗时与失败记录均封存。

五个新语法 CLI 选择 0.8.13/0.8.19/0.8.28/0.8.22/0.8.29，Latin-1 选择 0.4.24；另外三个正例为 0.5.0/0.5.1/0.4.16。新源码未改写。全部受测正例成立不代表所有未来输入或图语义已经穷举；非法嵌套 pragma 只检验定位忽略，不声称可编译。

### 25.4 用户批准、原文差异与待确认设计

本轮依据用户 2026-11-17 的 CP2.3 指令实施已有 r2.11 方案，没有替代方案或额外下载/安装请求；D3/D5/key5/settings、D20/D20a、已知版本读取和既有决策状态不改。DECISIONS 只追加实现证据。基线 seal 选择的问题是证据版本识别，不改变任何 CP2.3 验收判据。

实质限制只登记两项既有缺口：双竖线 pragma 不支持、Slither 进程内没有超时，按 CP3 既定安排分类和提出后续方案，本轮不实现。D19 与 D9/D10 等待定状态保持。没有发现需要先咨询的新方案调整。

### 25.5 验收、资源、未执行事项与停止

§4.4d 的复现、指定修复、等价/边界测试、生产 CLI 正负例、两环境模块/DFG 测试与 846 全量验收全部符合预期。非测试文件 14，分层测试通过；只在当前两份生产文件改功能。环境为 production Python 3.10.21/Slither 0.11.6/crytic-compile 0.4.2 与 mando 3.7.12/0.8.0/0.2.4。CPU OMP/MKL=2，费用 0，峰值未测。

doc_check 使用追加前字节数 CP2_REPORT=43516、PROGRESS=38417、CHANGE_LOG=175780；HANDOVER、DECISIONS 和两个新 README 全文检查。最终结果在本节末尾补记。实际测试命令为各环境 python -B -m pytest -q -ra -x -p no:cacheprovider，加独立 --basetemp；详见 pytest_*.json。完整性审计核对旧跟踪内容、旧 seal 成员、源码、环境、solc、DFG _code_refs、函数保护与运行/测试代码指纹；最终结果见 frozen_audit。

CP2.3 本机验收通过后等待独立审查；CP3 未开始，6c 未重放。未安装、下载编译器/依赖/语料/文档、调用 LLM、训练、申请 GPU 锁或修改全局 solc、网络配置。强制记录/最终检查通过后本地提交，提交号见 git log；不自动 push。"""
append("compile_repair/docs/CHANGE_LOG.md",change)

progress=f"""## 2026-11-17 CP2.3：版本读取修复与回归通过（修改 AI：Codex）

执行 PROMPTS r2.11 §4.4d，先 pull --ff-only origin compile-repair，起点 {head}；通读 PROMPTS、指定当前状态/审查证据和记录规范。旧缺陷先复现：6 个 CLI 输入被拒、直接 solc/production D3 9/9 通过。仅改 rules/environment.py 的字节定位/表达式求值/Latin-1 推断和 pipeline.py 的异常捕获，共 +73/-16；生产文件仍 14。新增一个测试文件和六个夹具，已有产物、测试和源码不变。

两个环境各 846 个输入与 28 个可解析夹具的区间及补丁字节范围均与冻结实现相同；其余 8 个夹具按真实异常明列。9 个 CLI 正例全部成功、1 个并集负例仍拒绝；新增探针与合约体内 pragma、CR/LF/偏移等边界都已测试。v5 全量一次：843 成功、3 已知 Slither 侧失败；846/846 记录字段与 v3 同，843/843 graph 字节同。证据 cp2_3_v1 与 cr_store_mando_v5，详见 CP2_REPORT 的 CP2.3。

测试 production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings。v5 耗时 {reg["elapsed_seconds"]:.2f} 秒，tar 4,229 成员逐哈希回读通过；探针存储 58 成员无损交付。基线准备遇到旧首次 seal 已被 seal_v2 替代的情况，核验既有 README/最终 seal 后使用登记的结果集合并保持所有旧字节，见 development_issues；正式验收无意外失败或重试。

已更新交接、训练改变记录（模块 CHANGE_LOG §25）、决策历史及报告；doc_check 与保护审计完成后本地提交，不自动 push。CP2.3 待独立审查，CP3 未开始；6c 不重放。没有方案外调整、安装/下载、LLM、训练、GPU 锁或全局 solc 变更，费用 0。"""
append("compile_repair/PROGRESS.md",progress)

decision="""### CP2.3 实现与回归验收（2026-11-17，修改 AI：Codex）

用户明确要求执行 PROMPTS r2.11 CP2.3。本轮仅改 pragma 定位与字节处理，不改变冻结约束求值语义或 D5；两环境各 846 输入及 28 个可解析夹具等价，9 个 CLI 正例通过。新 v5 对 v3 的状态/版本/设置/标志各 846/846 同，843 图字节同；D3/key5/settings_retry/known-version 保持。D20/D20a 的 6c 回归已经结束，本轮重放 0 次。

无新增方案决定或判据调整，当前决策表不改。并集 pragma 和 Slither 超时仍按 CP3 已定范围留待分类，未提前实现；没有安装或下载。证据 CP2_REPORT 的 CP2.3、CHANGE_LOG §25、artifacts/cp2_3_v1；本机验收通过，独立审查尚未进行。"""
append("compile_repair/docs/DECISIONS.md",decision)

handover=f"""# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.11（§1.14、§4.4d、§4.5）、CP2_REPORT 的 CP2.3、DECISIONS、CHANGE_LOG §24/25 及 artifacts/cp2_3_v1/README.md。第 6 节历史只追加。

## 0. 一句话

CP2.3 已完成本机验收：pragma 定位不再依赖整文件 parser，版本读取/推断接受非 UTF-8 字节；v5 的 846 个记录字段与 v3 相同，843 个图字节相同。下一步独立审查 CP2.3，审查通过后才进入 CP3。6c 回归已经结束，不再重放。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 决策 | PROMPTS r2.11；D5/D16/D18/D20/D20a 已定；既有待定项不改 | DECISIONS |
| CP0–CP2.2 | 已审查通过；6c 239/239 已结束 | cp2_2_review_v1 |
| CP2.3 实现 | 仅 environment.py/pipeline.py，+73/-16，生产文件 14 | code_change_summary.json |
| 冻结等价 | 两环境各 846 输入 + 28 可解析夹具相同 | cp2_3_v1/equivalence.json |
| 新 CLI 输入 | 9 正例成功、1 并集负例按预期拒绝 | probes.json |
| MANDO v5 | 843 成功、3 已知 Slither 侧失败；846 记录字段同，843 图字节同 | regression.json |
| 测试 | production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings | pytest_* |
| 下一步 | CP2.3 独立审查 → CP3；本轮没有开展 CP3 | PROMPTS §4.4d |

## 2. 分支与工作树

工作树 /home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair。本轮 pull --ff-only origin compile-repair 返回 Already up to date，起始 HEAD={head}。强制记录和检查后本地提交，提交号见 git log；本轮未自动 push，不在 EdgeSem 工作树执行 git。

新批次仅 cp2_3_v1、cr_store_mando_v5，旧批次不修改/覆盖。v5 用 store.tar.gz 交付，原散文件保留；探针 CLI 存储另用 cli_probe_stores.tar.gz。按 delivery_inventory 精确暂存，不递归 force-add 旧树，不清理历史未跟踪文件。CP2.3/CP3 继续当前分支，rtx5080-rebuild 的导入重构留迁移时合并。

## 3. 环境

production=/home/zhao/miniconda3/envs/compile-repair-production，Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；mando Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。runtime.json 已现场核对。可信 solc 96 个，其中 92 个支持版本；本轮无安装、下载或全局版本选择。

从仓库根运行，PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。全部 CPU，无 HGT/LLM/GPU 锁，费用 0；没有改变已有 Windows/WSL 代理和网络配置。

## 4. 必读事项（当前边界）

1. 目标是未来检测时任意合约；MANDO 846 仅回归，不按漏洞标签决定策略。
2. pragma_interval/pragma_patches 共用 code_only 后的顶层字节定位；只复制冻结表达式求值语义，源码字节不重编码。infer_interval 用无损 Latin-1。
3. MANDO recorded_version 的 UTF-8/元数据哈希保持；D3/D5/key5/settings_retry、图格式与标记保持。
4. 并集 pragma 仍为 unsupported_version_constraints；Slither 进程内仍无超时，按 CP3 分类和讨论后续实现，本轮不处理。
5. 6c 已按 D20/D20a 完成；历史样本与判据封存。本轮没有重放或追加样本。
6. v5 与 v3 的状态、reason、版本、settings、flags 各 846/846 同，843 图字节同；3 个已知失败不写图，CLI rc2、验收驱动 rc0 是预期。
7. 8 个夹具在冻结 parser/UTF-8 路径无法处理，明确排除旧实现等价、另做边界或 CLI 测试，未把它们当作旧实现通过。
8. 旧 cp0_1_compilers_v1 首次 seal 已由 README 指明被 seal_v2 替代；当前 README 与最终 seal 相同，不改历史。处理记录在 development_issues。
9. 所有旧代码/产物保护按 baseline 与 frozen_audit 检查；新测试和 v5 的代码指纹必须与本次实际实现一致。
10. docs/CHANGE_LOG 是本模块训练改变/运行记录，根目录两份文档不改。第 6 节及各旧报告历史保留。
11. CP2.3 已完成本机功能验收，仍需独立审查；不要将该状态写成已审查，不提前执行 CP3。
12. 未来任何方案变更先咨询用户并记录。本次未提出或实施替代方案；有限探针通过不证明所有输入和图语义已穷举。

## 5. 关键路径

| 内容（compile_repair 下） | 路径 |
|---|---|
| 当前报告和训练改变记录 | CP2_REPORT.md 的 CP2.3；docs/CHANGE_LOG.md §25 |
| CP2.3 证据总览 | artifacts/cp2_3_v1/README.md |
| 修改前复现 | cp2_3_v1/reproduction.json、reproduction_invocations.jsonl、reproduction_cli |
| 等价与 CLI 验收 | cp2_3_v1/equivalence.json、probes.json、cli_probe_stores.tar.gz |
| 新正式升序存储 | artifacts/cr_store_mando_v5/store.tar.gz |
| 严格逐份回归 | cp2_3_v1/regression_plan.json、regression_acceptance.jsonl、regression.json |
| 测试与最终检查 | cp2_3_v1/pytest_*、frozen_audit、doc_check_v*、delivery_inventory/seal |
| 冻结参照 | artifacts/cr_store_mando_v3/store.tar.gz；cp0_v2/recon.json |
| 上轮独立审查 | artifacts/cp2_2_review_v1/README.md、probe_inputs.json（只读） |

---

"""
p=root/"compile_repair/docs/HANDOVER.md"
old=p.read_text()
p.write_text(handover+old[old.index("## 6. "):],encoding="utf8")
append("compile_repair/docs/HANDOVER.md",f"""### 2026-11-17 CompileRepair CP2.3 本机验收完成（修改 AI：Codex）

在 compile-repair 工作树 pull --ff-only 后起始 HEAD={head}，先读共享上下文再通读 PROMPTS r2.11 及当前记录/审查证据。先写基线和复现，再仅修改 environment.py、pipeline.py；新增一个测试文件与六个夹具，生产文件仍 14。本文开头与第 0–5 节已同步当前状态、边界、证据和下一步，第 6 节旧历史逐字保留。

旧缺陷 6/6 复现，直接工具对照 9/9 成立；两个环境各 846 输入与 28 可解析夹具等价，9 个新 CLI 正例成功、1 个负例按预期拒绝。v5 全量 843 成功/3 已知失败，846 记录字段与 v3 同、843 图字节同；原图与旧存储不改。新存储 4,229 成员和探针存储 58 成员无损打包、哈希回读相同，详见 CP2_REPORT 与 CHANGE_LOG §25。

没有改变冻结约束语义、D3/D5/key5、settings 或已定决策，6c 不重放。基线初次选到历史首次 seal 的问题，按原 README 指定的 seal_v2 验证后解决，未改旧文件或放宽验收。并集 pragma 与 Slither 超时继续留 CP3；本机验收通过仍待独立审查，CP3 未开始。

production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings。强制记录、doc_check 和最终保护检查后本地提交，实际提交号见 git log，不自动 push；没有安装/下载、LLM、训练、GPU 锁、全局 solc 或网络配置变更，费用 0。最终检查结果在本段后补记。""")

readme=f"""# CP2.3 本机证据（Codex，2026-11-17）

本批次实现 PROMPTS r2.11 §4.4d，起始 HEAD={head}。只修改 rules/environment.py 与 pipeline.py，生产文件 14；新测试/夹具覆盖版本读取的语法与编码缺陷。详见 ../../CP2_REPORT.md 的 CP2.3 和 ../../docs/CHANGE_LOG.md §25。本目录不覆盖旧证据，不导入审查脚本。

| 证据 | 内容 |
|---|---|
| baseline.json | 开始前跟踪文件、旧结果成员、源码、环境、solc、DFG 引用及文档字节数 |
| reproduction* | 修改前 6 个 CLI 拒绝及 9 次 solc/production D3 成功对照，含调用记录 |
| code_change_summary.json、reuse_sources.json | 修改函数/行数与冻结算法/驱动来源 SHA |
| development_issues.json | 旧首次 seal 已被最终 seal_v2 替代的既有事实及处理 |
| pytest_*.json / .log.gz | production 607/6、mando 167/446、DFG 2653 passed/9 既有 warnings |
| test_evidence_*.json.gz、equivalence.json | 两环境各 846 输入 + 28 夹具等价，8 个旧路径无法解析的夹具明列 |
| probes.json、cli_probe_stores.tar.gz | 9 成功与 1 预期拒绝的真实 CLI；58 成员无损归档，审计未重复编译 |
| regression_plan/acceptance/regression | 同 v3 参数、846 逐份检查、843 图字节一致、3 已知失败 |
| cr_store_mando_v5_archive_audit.json | v5 4,229 成员逐哈希回读；tar SHA={tar_sha} |
| runtime.json、frozen_audit.json | 实际版本及最终保护审计 |
| doc_check_v*、delivery_inventory/seal | 强制文档检查与本批精确交付身份 |

执行驱动均以本目录为写入范围且拒绝覆盖；launch_phase 的 reproduction/probes/regression 分别执行旧缺陷复现、已通过测试的只读审计和一次新全量回归。reproduce.py 明确要求旧生产文件哈希，因此实现后不再运行。run_checks 使用独立临时目录；probe 的完整封存存储已随 tar 交付，临时目录无需作为长期依赖。

完整命令在 CP2_REPORT 与各 invocation/pytest JSON 中。原日志和 v5 散文件保留在本地，交付时只添加清单所列文件，不清理旧未跟踪内容。本机验收完成、待独立审查；CP3 未执行，6c 不重放，无安装、下载、LLM、训练或全局 solc 操作，费用 0。"""
with (out/"README.md").open("x",encoding="utf8") as f:f.write(readme+"\n")
store_readme=f"""# cr_store_mando_v5：CP2.3 生产升序回归（Codex，2026-11-17）

同一 CLI 与 v3 的 846 输入顺序、--regression mando --order ascending；production profile、92 个支持编译器。843 success、3 已知 Slither 侧失败（reentrancy_bonus、reentrancy_cross_function、reentrancy_insecure）；失败没有 graph。846/846 状态、reason、选定版本、settings、flags 与 v3 相同，843/843 graph.json 字节相同。证据 ../cp2_3_v1/regression.json 与 regression_acceptance.jsonl。

store.tar.gz 是无损交付格式：4,228 个 seal 文件加 seal.json，共 4,229 成员，{archive["archive_bytes"]} 字节；SHA256={tar_sha}。seal.json SHA256={seal}。每个成员 SHA 已回读验证，成员清单见 ../cp2_3_v1/cr_store_mando_v5_archive_audit.json。本地散文件保留，README 与 tar 属交付说明，不在运行 seal 内。

运行约 {reg["elapsed_seconds"]:.2f} 秒，CLI rc2 为三份预期未修复，外层验收驱动 rc0。编译器绝对路径/版本/哈希、源码身份、settings、profile、调用耗时和实现 SHA 在 trust、manifest、invocations、seal。旧 v3 和 CP0–CP2.2 批次不改。本批拒绝覆盖或原地重跑；6c 回归已结束，CP2.3 待独立审查，无 LLM 调用和费用。
"""
with (out.parent/"cr_store_mando_v5/README.md").open("x",encoding="utf8") as f:f.write(store_readme+"\n")
print("Updated five required module records and two new READMEs; prior histories retained.")
