# CP1：核心层与环境方法（PROMPTS r2.6）

修改 AI：Codex。日期：2026-11-14（按用户会话日期，America/New_York）。起始分支 compile-repair，HEAD d5e84d39fe876ea1b4b00a8bb26dee47ca9e18a5；git pull --ff-only origin compile-repair 返回 Already up to date。

## 实现

本步完成一般单文件与文本片段的环境修复入口，仅接入第 1、6 步。成功表示 solc rc0 且 production D3 通过；不表示恢复了作者全部意图、漏洞消失或已完成完整 CFG/CG 存储。CP0、CP0.1 的产物、报告、Slither 实现和原编译函数不改。

| 文件（compile_repair 下） | 动作与职责 |
|---|---|
| core/model.py | 扩展编译单元、源码身份、补丁、改动、偏移分段、环境计划和清单记录；原 Compiler/Compilation 不变 |
| core/provenance.py（新） | 按当前副本字节坐标校验补丁原文、重放改动、压缩偏移映射、原字节保留检查、original/added/rewritten 标记 |
| core/store.py（新） | 拒绝目录/文件覆盖与路径逃逸；UTF-8 JSON、逐次 flush 的 JSONL；封存全部产物及工具/代码身份 |
| rules/__init__.py、rules/environment.py（新） | 唯一选版策略、已知版本优先、系列内顺序、失败后跨系列、无 pragma 推断、两行设置表、仅无区间内候选时的 pragma 覆盖 |
| pipeline.py（新） | 单文件工作副本、默认编译→匹配设置→同版 Slither→下一候选；未修复原因与每次调用记录 |
| toolchain/solc.py | 只追加已批准本地信任清单加载器；原 command/compile_file 等函数保持 AST 相同 |
| evaluation/survey.py | CP0 的候选、优先级、系列分组和端点选择委托给 environment；保留 CP0 无 pragma 清单窗口作为调查配置 |
| cli.py | repair 路径、多个文件、--snippet、--known-version、--output、--order、--regression mando；目录以非零退出并报告暂不支持 |
| tests/test_core.py、test_environment.py、test_pipeline.py（新） | 40 个参数化新增用例；不修改原 6 份测试或 28 份 fixture |

非测试 Python 共 14/30 个，均在 §3.10 文件表内；最长模块 survey.py 约 635 行。分层测试、Python 3.7 AST 解析和两个真实环境导入通过，身份见 artifacts/cp1_development_v1/implementation_audit.json。

区间直接 import scripts/DFG/state/stage_f/versioning.py 的 interval，复用文件 SHA256 为 130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18；没有复制或 monkeypatch。多文件 pragma 交集在纯策略接口中支持；项目导入闭包/目录入口仍留 CP3。无 pragma 推断采用三条文档已有依据的保守语法规则：throw、var 在 0.5.0 移除，unchecked 在 0.8.0 引入；每条写明官方版本、条目与 URL，并有正例/反例/注释与字符串排除测试。未出现特征时不反推语义，按可信版本顺序尝试。

known_version 在声明区间内优先；MANDO 配置才读取 hash 匹配的已验证 SmartBugs metadata 并调用 recorded_version 重查源码/CSV/行，且无 pragma 先试 0.4.25。一般入口不按目录或文件名决定版本。crossed_minor 表示正常候选系列耗尽后的跨系列尝试；显式已知版本优先另由 plan.priority 和 input_record 说明。降序只倒序系列内版本，系列推进仍须先耗尽当前系列。

设置表只含 r2.6 指定的 0.8.24 Cancun 与 0.8.26 require 自定义错误 via-IR。默认失败且类型/消息/版本匹配才重试同一版本一次；匿名的 Undeclared identifier 还核对诊断字节位置的 blobhash 标识符。Slither 收到相同有序设置；每条清单保留触发错误、表项出处、solc 返回码、profile、平台、异常、耗时和费用。Slither 侧失败不触发设置或源码改写。

pragma 覆盖仅在声明交集内无可用可信支持版本时启用，按下界同系列距离排序；仅将 directive 字节替换为等长空格，CR/LF、UTF-8 字节偏移和同一行其他代码保持。改动记录包含原字节、新字节、步骤和轮次；字节以十六进制无损存储。等长改写保留位置对应，非等长删除/替换的原字节可映射为 None；节点跨新增/改写边界或删除拼接点标记 rewritten。

## 真实验收

| §4.3 条目 | 实测与证据 | 结论 |
|---|---|---|
| 冻结选版复现 | 37 个 CP0 身份、冻结 rc/D3 输入；两环境各升序 846/846、降序 846/846；不重新编译 CP0 | 通过；offline_replay_*.json.gz、offline_replay_audit.json |
| 区间/候选/来源保护/分层 | ^、~、=、上下界、多 pragma、多文件交集、无 pragma、OR/空交集拒绝、已知版本边界、系列推进、仅缺候选时覆盖、改名不改计划、逐字节重放 | 通过；三份新测试及 pytest 日志 |
| 自动设置 | 4 个精确 0.8.24 Cancun 副本、1 个精确 0.8.26 via-IR 副本、1 个 ^0.8.24 副本；6/6 先默认失败再同版设置 D3 通过 | 通过；settings_acceptance.json |
| 小样本规模 | 规则 A 不通过 25（22 failed、3 unavailable）+ 每类独立 Random(0) 的 10 个通过文件共 70；3 个指定重入文件已包含在前 25，去重后 95 | sample_plan.json |
| 小样本成功 | 92 成功；仅 3 个指定合约为 Slither 侧失败，其他未修复 0 | 通过；cp1_sample_v1/acceptance_summary.json |
| 选版对账 | 91 相同；1 个新增更低编译器；无法归因差异 0；覆盖/跨系列均 0；所有成功版本在区间内且 ≥0.4.12 | 通过；acceptance.jsonl、archive_audit.json |
| 原文件与节点来源 | 95 文件改动等级均 none；92 成功文件共 11,822 节点全部 original；95 个 case seal 回验通过 | archive_audit.json |
| 历史编译器测量 | 23 次前置编译 rc0，46 次 production Slither；只记录实测，不改变下限 | cp1_historical_v1/results.json、counts.json |

小样本实际执行 197 次 solc、101 次 Slither，347.413 秒。95 个文件中实际命中 SmartBugs metadata 为 0，无 pragma 为 1；不要把本次样本写成运行了全部 43 份 metadata。已知版本优先在 846 文件冻结重放中覆盖；通用 metadata 校验复用冻结 recorded_version。

唯一选版差异：unchecked_low_level_calls/source_files/0x366cf49c6bc3986b20ecf4fd7c05f0c617332e8c.sol，SHA256 f0028ebd798334727aa07d9857bc3996563b8dc250b899882cb1346fc5d24014，CP0 选 0.5.6，本次选 0.5.5。0.5.5 不在 CP0 的 37 版集合，在已批准新增清单中，处于原区间且 solc rc0、生产 D3 通过，属于 §5(a)；证据 cases/082/manifest.jsonl 与 input_record、trust、seal。§5(b)/(c) 在这个样本没有发生；设置重试另由六个真实测试证明。

三个预期未修复文件 reentrancy_bonus、reentrancy_cross_function、reentrancy_insecure：逐个尝试 0.4.12–0.4.26；0.4.12–0.4.23 为 solc 失败，0.4.24/25/26 均 rc0 但 Slither AssertionError。清单保留各候选完整 stderr、异常类型和首行；未越过 pragma，未实现 CP6 第 10 行改写。

历史测量覆盖 CP0 matrix 中四个老版本的全部 rc0 文件组合（9、4、2、4），加每版 compat_04，共 23 组合。前置 compile_file 在仓库根执行一次；相同输入/编译器在仓库根与 / 分别调用 run_slither。两个 CWD 逐版结果相同：

| solc | 每个 CWD 的输入数 | D3(a)/D3(b)/总 D3 通过 | 每个 CWD 缺 filename 节点 |
|---|---:|---:|---:|
| 0.4.0 | 10 | 0/0/0 | 287 |
| 0.4.2 | 5 | 0/0/0 | 50 |
| 0.4.9 | 3 | 0/0/0 | 362 |
| 0.4.11 | 5 | 5/5/5 | 0 |

46 次中 10 D3 通过、36 D3 不通过，都是按第 6 节记录的测量值，非计划外重试。合计缺 filename 1,398 个节点；原始逐条 D3(a)/(b) 诊断在 invocations.jsonl。测量用时 3.887 秒（不含信任清单加载；完整进程 7.351 秒）。建议维持 0.4.12：0.4.11 的五个输入不能证明任意输入完整图语义；若拟扩展到 0.4.11，须审查与用户决定后另定覆盖，不在本步调整。

## 测试与开发记录

| 环境/命令 | 结果 | pytest 耗时 |
|---|---|---:|
| production：python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests | 546 passed / 6 skipped | 41.79 秒 |
| mando：同上 | 116 passed / 436 skipped | 13.38 秒 |
| mando：同参数 scripts/DFG/dfg_v2/tests | 2653 passed / 9 个已有弃用警告 | 196.02 秒 |

完整 argv、独立 basetemp、环境变量、rc、日志 SHA 和进程耗时均在 cp1_development_v1/pytest_*.json；原始日志无损 gzip，明文仅本地保留。跳过源于 profile/Python 版本要求，未用 xfail 放宽标准。模块测试与正式测量均一次通过；没有编译失败后的隐式重复执行。

归档辅助检查曾把 pytest 的真实目录和 current 符号链接同时列为结果，因数量为 2 而退出（Replay archive missing）；检查两条路径后仅排除符号链接别名，读取原已通过结果，未重跑测试、未改验收。记录在 offline_replay_audit.json。新增源码封存扫描只遍历模块代码目录，不遍历旧 artifacts/pytest 临时树；这属于实现效率选择，不改变策略。

## 归档与复现

- artifacts/cp1_development_v1：基线、执行/审计/文档检查脚本、测试日志与收据、离线重放、设置验收、旧边界问题、冻结/文档/暂存检查。
- artifacts/cp1_sample_v1：sample_plan、95 个通过同一 repair CLI 的独立 case、acceptance 与独立归档审计。
- artifacts/cp1_historical_v1：23 组合计划、23 solc + 46 Slither 调用记录、逐条结果与聚合计数。
- 每个 case 的 seal.json 绑定全部文件、96 个可信二进制身份（候选只取支持范围 92 个）、生产工具版本、起始提交与 14 个实际实现文件 SHA。三个顶层 seal 与提交清单见 cp1_development_v1/seal_hashes.json、file_inventory.json；seal 的 SHA256 集中写在 seal_hashes，避免自引用。

环境：production Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2，隔离用户 site-packages；mando Python 3.7.12 / 0.8.0 / 0.2.4 只做冻结回归。92 个支持编译器与 4 个历史对照均沿用已有信任链，检测入口不下载。每次编译和 Slither 调用都校验二进制/源码身份。

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
# 通用修复：输出必须是尚不存在的新目录。
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m compile_repair.cli repair compile_repair/tests/fixtures/compat_04.sol --output compile_repair/artifacts/cp1_manual_new
# 本次实际验收命令（原批次已存在时拒绝覆盖）。
/home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp1_development_v1/run_checks.py production
/home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp1_development_v1/run_checks.py mando
/home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp1_development_v1/run_checks.py sample
/home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp1_development_v1/run_checks.py historical
/home/zhao/miniconda3/envs/mando/bin/python -B compile_repair/artifacts/cp1_development_v1/run_checks.py dfg
```

复验小样本使用 sample_plan.json 的完整文件清单；每个文件的完整 cli_argv 均在 acceptance.jsonl，替换 --output 为新的目录后可独立复现。测试的直接 argv 也保存在收据中，复验时仅更换 basetemp 与日志目标，不能覆盖本轮证据。

## 停止位置与后续边界

CP1 规定的 §4–6 验收已完成，下一步等待审查，不能自动进入 CP2。完整 CFG 边/调用序列化、项目/依赖组装、其他确定性修复、LLM、CP6 Slither 改写均未执行。没有下载、安装、升级、全局 solc 切换、训练或 GPU 锁操作；费用 0 美元。本轮只本地提交，不 push。

值得审查的既有问题只有一项：toolchain/solc.py 的 command() 用 source[len(cwd)+1:] 构造相对路径，在 cwd=/ 时会把 /home/... 变成 ome/...。本轮只读构造命令确认该参数对应文件不存在（cwd_command_inspection.json），没有把它当作编译器失败实测，也没有修改 CP0.1 原函数。第 6 节只要求两种 CWD 下运行 run_slither，前置编译仍在仓库根，因此该测量未受影响。建议后续经用户确认，用路径函数替代字符串前缀截取，并对 / 和目录前缀相近的情形补测试；尚未实施，当前通用 CLI 应从项目工作目录运行。


交接写入补记（修改 AI：Codex）：最后四份文档的写入命令曾在 WSL 启动阶段报 Wsl/Service/0x8007274c。四份文件 SHA256 仍与 baseline 一致，确认未写入；只读状态显示 WSL Running，短 stat 命令恢复后分批完成记录。未定位根因，未重启服务或重跑实验；证据 documentation_interruption.json，CHANGE_LOG §15.2。


归档补记（修改 AI：Codex）：95 个原始源码副本中 57 个含原有行尾空白；为保持源码原字节和所有 case seal，将 852 个 case 文件（12,212,867 原字节）确定性打包为 cases.tar.gz，逐成员回读 SHA256/长度全部相同。原 case 目录本地保留且不改，Git 提交无损包和 case_archive_index.json；报告中的 cases/NNN 路径是包内路径。未清理源码空白或排除已暂存文件的检查。审查时在全新目录解包，逐文件按 index 与各 case seal 校验，不能覆盖本地现有 cases。

最终记录检查：首轮 doc_check 八份全部通过、历史前缀审计通过，初次 57 文件暂存格式检查 rc0；最终补记后的八份检查、封存与提交清单以 cp1_development_v1/doc_check_v2_invocation.json、seal_hashes.json、file_inventory.json 为准。


## CP1.1：路径与健壮性修复（2026-11-14，修改 AI：Codex）

### 实现与范围

依据 PROMPTS r2.7 §4.1、§4.3b、§1.10、docs/HANDOVER §0–5、DECISIONS、CHANGE_LOG §15/16 和 cp1_review_v1/README。在 compile-repair 执行 git pull --ff-only origin compile-repair，结果 Already up to date，起始 HEAD d4f4b48a2484591dc185b90475f775f6c9f5498d。本文旧 CP1 内容原字节保留；CP0–CP1 正式产物与结论不重跑、不改写。

生产代码仅修改 toolchain/solc.py、toolchain/slither.py、pipeline.py，新增测试 tests/test_cp1_1.py；生产文件仍 14 个，测试文件现 10 个。solc.command 用 Path.relative_to 判断路径组件，目录内使用相对路径，目录外保留绝对路径，其余参数与顺序不变。regression_6c 在调用任何工具之前拒绝 cwd=/ 或字符前缀相同但不包含输入的目录；冻结 _compile、crytic-compile 0.2.4 原实现不动。

repair_unit 将 timed_out 调用先写入日志与 attempts，再把该输入封存为 unrepaired / solc_timeout；不重试、不试后续候选，批次继续下一个输入。已有信任或完整性异常的停止路径保留。repair 新增可选 compile_fn 参数用于批次测试，默认仍为原 compile_file，没有 monkeypatch。取不到 Git HEAD 时只捕获 CalledProcessError / FileNotFoundError，code_commit=null，summary.flags 含 code_commit_unavailable，14 个实现文件 SHA256 照常封存；其他异常不借此隐藏。

### 真实验收

证据均位于 artifacts/cp1_1_v1/；module_acceptance.json 汇总两个环境的测试证据，cli_acceptance.json 汇总 CLI。

| 验收 | 预期 | 实测 |
|---|---|---|
| 仓库根目录下 MANDO argv | 846 个输入逐个相同 | 两环境各 846/846；选用每个输入的 CP0 升序版本，仅构造 argv，不重新编译语料 |
| C 续兼容性 argv | 所有计划项相同 | 两环境各 501/501，含 5 个设置正例；旧算法仅留测试内 |
| 五种 cwd 的真实 solc | 全部 rc0 | 两环境各 5/5；根目录、前缀兄弟、无关目录、包含目录、文件父目录；solc 0.5.17 |
| regression_6c 危险 cwd | 调用前明确拒绝 | 两环境的 / 与前缀兄弟测试通过，源文件和编译器故意不存在，证明未进入工具或完整性读取 |
| 输入超时 | 记录、终止本输入、不重试 | 首次、已有 Slither 失败后、设置重试中三种情况，两环境各 3/3；末次 timed_out=true、reason=solc_timeout |
| 批次边界 | 超时继续、信任错误停止 | production 注入超时后第二输入真实编译成功；注入信任错误后批次 stopped，不调用第二输入 |
| 无 Git 封存 | null + 标记 + 文件哈希 | production 在 /tmp 的非 Git 模块副本与 PATH 无 Git 两种真实子进程中均 complete；14 个实现哈希一致 |
| CLI 三目录等价 | 3 fixture × 3 cwd 全成功，节点逐项相同 | 9/9；每例 10 个节点，key5 + 有序 IR + 标记完全相同，90 个节点均 original；所有 case seal 回读通过 |

CLI 的三个 fixture：compat_05.sol 原字节副本选 0.5.0、默认设置；y0824_tstore_asm.sol 的精确 0.8.24 副本先默认失败，再用同版 --evm-version cancun 成功；compat_04.sol 的精确 0.4.10 副本经等长 pragma 覆盖后选 0.4.12，等级 rewrite，节点不覆盖 pragma，因此仍 original。共 12 次前置 solc、9 次生产 Slither。输入与原 fixture 哈希均保持；命令、cwd、stdout/stderr、耗时见 cli_invocations.jsonl，各次工具身份与调用见 cwd/out2/*/invocations.jsonl、trust.json、seal.json。

### 测试与开发记录

| 命令目标 | 环境 | 结果 | pytest 耗时 |
|---|---|---|---|
| compile_repair/tests | production，Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2 | 562 passed / 6 skipped | 60.88 秒 |
| compile_repair/tests | mando，Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4 | 128 passed / 440 skipped | 13.18 秒 |
| scripts/DFG/dfg_v2/tests | mando | 2653 passed / 9 个原有依赖弃用警告 | 160.19 秒 |

三轮均一次运行，无测试失败或重试；跳过项由 profile/Python 版本限定。完整 argv、环境变量、墙钟耗时、日志 SHA256 在 pytest_*.json，日志无损压缩为 pytest_*.log.gz。新增行为的原始 JSON/JSONL 证据打包在 test_evidence_production.json.gz（43 项）、test_evidence_mando.json.gz（9 项）；pytest 临时树位于 /tmp，未提交，未删除。

开发时 WSL 没有 rg，改用现有 Python、sed、grep 读取；一次路径检索包含不存在的 test_solc.py，随后读取实际 test_toolchain.py。两者均为只读检索问题，没有重试失败的编译或变更验收标准。没有新增方案替代建议；已知 || pragma 和 Slither 进程内无超时仍按 r2.7 留 CP3，D19 仍为建议，本步不改变 0.4.12 下限。

### 归档与复现

产物目录 artifacts/cp1_1_v1，README 说明布局与精确复现命令。baseline.json 绑定起始 HEAD、28,331 个跟踪文件、354 个 code_refs、96 个 solc 文件及两环境包元数据；frozen_audit.json 在提交前核验范围与历史字节，seal.json 封存本次交付的产物，file_inventory.json 列出提交文件与 SHA256。旧 CP1 样本未重跑；argv 相同性与实现范围审计用于证明该路径修复不改变原工作目录下的既有结果。

复现测试可在仓库根直接执行（新证据目录要求未存在；下列 pytest 的临时目录由 pytest 自行选择）：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider scripts/DFG/dfg_v2/tests
```

### 停止位置与后续边界

按用户本次指令完成 CP1.1 后提交，不自动 push；待独立审查通过再进入 CP2。本轮没有 CP2 全量运行、旧 CP1 样本重跑、CP6 改写、外部语料获取、安装升级、全局 solc 切换、HGT 训练、GPU 锁操作或 LLM 调用，费用 0 美元。最终冻结审计、doc_check 与提交检查结果追加于 CHANGE_LOG §17.5，准确提交号以 git log 的 CP1.1 条目为准。


开发记录补记（修改 AI：Codex）：冻结审计辅助脚本第一次从文件路径启动时，在执行检查前因未把仓库根加入 sys.path 而报 ModuleNotFoundError: scripts；没有生成 frozen_audit.json，没有实际冻结判据失败。保留 frozen_audit_launch_error.json 后，只给本批次辅助脚本补齐仓库导入路径，再执行冻结核验。生产代码、验收标准、已通过的三轮 pytest 和九组 CLI 没有修改或重跑；这是证据脚本启动问题，不是编译器或环境缺包，也未安装任何内容。


最终检查补记（修改 AI：Codex）：frozen_audit.json 的 passed=true，28,323 个受保护跟踪文件、354 个 code_refs、96 个 solc 文件及 mando/production 的 117/144 份包元数据均未变化；模块外跟踪改动为 0，生产文件仍 14，未授权的工具链函数 AST 变化为 0。旧 CP1_REPORT、PROGRESS、CHANGE_LOG 前缀及 HANDOVER/DECISIONS 历史原字节保留，14 个实现哈希与测试时两份封存相同。doc_check_v1 的 6 行全部 passed=true、rc0；本补记写入后按相同目标运行 doc_check_v2，最终收据为 doc_check_v2.jsonl / doc_check_v2_invocation.json。随后封存证据、按 file_inventory 精确暂存并检查 git diff --cached --check，成功后提交 CP1.1；本步不 push。


无损交付归档补记（修改 AI：Codex）：首次暂存清单 123 文件，内容 SHA 检查通过，但 git diff --cached --check 返回 2：三个精确 0.4.10 case 的 pragma_overridden.sol 第 3 行是按方案要求生成的等长空格，触发行尾空白检查。该空格不能删除，否则会改变字节偏移与既有 case seal。沿用 CP1 的交付方式，把九组 CLI 输出的 84 个文件无损打包为 cli_cases.tar.gz，逐成员 SHA256/长度回读 84/84 一致；原文件和九个 case seal 在本地保留不改。未放宽 Git 检查，未重新运行 CLI，未修改生产存储格式。

CLI 归档 SHA256 为 bec8f18cdc4510bf066d4bf79abe4489ab8d70c8c8e61a263b60ee63f1cf844b，大小 95,681 字节，archive_audit.json 保存成员清单。前文 cwd/out2/* 路径现在表示归档内成员，替代此前“按原目录提交”的交付说明。首次 seal.json、file_inventory.json、final_validation.json 均保留原字节，作为归档前阶段快照；当时的六份文档保存于 prepackaging_documents.tar.gz，与初版文档哈希完全一致。最终交付以 delivery_seal.json、delivery_inventory.json 为准，它们绑定最终文档及两个压缩包；不得将初版快照误当最终提交清单。失败现场为 staging_failure.json，当前原始目录只留本地，不删除、不提交重复副本。

归档说明纳入 CP1_REPORT、PROGRESS、CHANGE_LOG §17.5、HANDOVER 和本批次 README；追加记录遵守历史字节边界。doc_check_v1/v2 均已 6/6 通过，归档补记后按相同六目标再检查并保存新收据，完成后重新核对精确暂存范围和格式，再本地提交；编译、测试与 CLI 的已通过结果保持。
