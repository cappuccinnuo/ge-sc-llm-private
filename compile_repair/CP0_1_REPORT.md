# CP0.1：D3、key5 与 mando 重验（修改 AI：Codex）

状态：**A 完成；B、C 未执行，等待 D16/D18 用户决定与具体安装授权。** 依据 PROMPTS r2.3 §4.1、§4.2b；起始 HEAD 61a3cb6a944140108763442999bbfd4199f53ca3，git pull --ff-only origin compile-repair 返回 Already up to date。记录时间 2026-11-12 08:54:02 EST（America/New_York）。

## 实现

模块仍面向未来检测时的任意损坏合约；MANDO 846 只用于回归，不定义支持范围。本轮没有实现 CP1 选版/修复流程，没有改变 PROMPTS 或既定方案。

| 文件 | 修改 |
|---|---|
| toolchain/slither.py | dict/对象映射统一读取；声明函数、修饰器与顶层函数遍历；key5；AST 合约覆盖；显式 profile；CP0 投影 |
| evaluation/survey.py | CP0.1 固定版本重验、CP0 seal 核验、完整调用/节点/差异归档；后续调查输出标为 v3 schema |
| cli.py | 新增 revalidate-cp0 --output，仅调度，不增加第二入口 |
| tests/test_toolchain.py | 比较测试使用 key5，替身补齐 compilation_units |
| tests/test_slither_v2.py | 映射、序号、合约遗漏、多重集合、AST 缺失、自由函数与 profile 测试 |
| tests/fixtures/ternary.sol、free_function.sol | 两个手写边界 fixture |
| CP0_1_REPORT.md、PROGRESS.md、docs/HANDOVER.md、CHANGE_LOG.md、DECISIONS.md | 本报告与强制记录 |
| artifacts/cp0_1_v1/、cp0_1_development_v1/ | 正式与开发证据；后者含待批准安装清单 |

生产 Python 文件仍为 9 个，均在 §3.10 目录表；survey.py 662 行、slither.py 248 行。其余原有文件、CP0 产物/报告及 PROMPTS 未修改。继续 import 冻结 scripts/DFG/dfg_v2/validate_slither.py 的 _compile，原文件 SHA256 为 4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8；没有复制或 monkeypatch 冻结函数。

1. **映射与遍历**：read_mapping 支持旧 dict 的 filename_absolute/start/length 和新对象的 filename.absolute/start/length。不支持的对象明确报错；已识别映射缺 filename/start 时 D3(a) 失败。检查所有 contracts[*].functions_and_modifiers_declared，以及 compilation_units[*].functions_top_level。构造成功与验证失败分开记录。
2. **key5**：在每个函数原始 nodes 顺序中，对相同（类型、start）从 1 编序号，随后才排序输出，不去重。类型使用 NodeType 枚举名，避开 0.8.0 的 ENTRY_POINT 与新版 NodeType.ENTRYPOINT 字符串差别。node_facts_v2 每行含 key5、有序 ir、length、declaration_kind（function/modifier/top_level_function）。
3. **AST 与 D3(b)**：使用 crytic_compile.compilation_units[*].asts 已保存的 AST，不额外编译。这是 A1 明确允许的选择，绑定本次 Slither 所用 AST 并避免第三次 solc 调用。旧式读取 name=ContractDefinition/attributes.name，compact 读取 nodeType=ContractDefinition/name。比较输入文件内合约、接口、库的名称多重集合；缺输入 AST 或非法结构拒绝。每条记录保存 AST 格式、名称重数及 AST SHA256。
4. **本机 API 核实**：真实 Slither 0.8.0 的 compilation_units 为 list，项为 SlitherCompilationUnit，functions_top_level 也是 list；crytic-compile unit.asts 以绝对路径字符串为键。实现前的 0.4.12/0.8.0 检查在 api_probe_*.json；0.7.6 自由函数探针进一步验证真实遍历。没有猜 API 或导入 cp0_review_v1 脚本。
5. **profile 与投影**：当前仅配置 regression_6c = Slither 0.8.0 + crytic-compile 0.2.4，production 不存在。运行时包版本不符或 profile 未配置则拒绝；每条 Slither 记录有 profile 和两个实测版本号。cp0_projection_sha256 仅用于 cp0_v2 对照，保留旧 key4、str(node.type)、IR、length、排序和 JSON 编码；新 node_facts_v2_sha256 单独记录。

## 真实验收

依据 artifacts/cp0_1_v1/revalidation.json.summary、完整 journals 与 cp0_1_development_v1/revalidation_audit.json。A3 固定使用 cp0_v2 的 selection.ascending、lowest_d3、highest_d3；没有重新选版或重跑 CP0 矩阵。

| 验收项 | 预期 | 实测 | 结论 |
|---|---:|---:|---|
| 输入文件 | 846 | 846 | 通过 |
| 新 D3 | 846 | 846 | 通过 |
| D3(a) / D3(b) 失败 | 0 / 0 | 0 / 0 | 通过 |
| 当前语料顶层函数 | 0 | 0 | 通过；另有正例 fixture |
| CP0 投影相同 | 846 | 846 | 通过 |
| 跨版本 key5 / 有序 IR 相同 | 678 / 678 | 678 / 678 | 通过 |
| 含重复 key4 的双端文件 / 相同 | 31 / 31 | 31 / 31 | 通过 |
| 选定版本有重复 key4 的文件 | 55 | 55 | 重数保留 |
| source length 相同 | 650 | 650 | 28 个不同，仅诊断 |
| B 生产环境、语料与特征重验 | 待授权 | 未执行 | 不记通过 |
| C 编译器补齐与重验 | 待授权 | 未执行 | 不记通过 |

直接 solc 1,546 次均退出码 0；Slither 1,546 次均构造成功且 D3(a)/(b) 通过。归档 1,546 组、201,044 条节点，每组指纹与 journal 一致，重复 key5 组数为 0。正式 A3 耗时 609.965 秒，外层进程 616.665 秒；所选 846 次 solc 合计 81.413 秒、Slither 合计 236.891 秒。DFG 测试与 A3 部分重叠运行；这些只是本次观测，**生产环境与 CP2 时间未测量**，也不证明 CFG/CG 边或任意合约语义相等。

真实 fixture：0.4.12 旧式 AST、0.8.0 compact AST 均通过且复现旧探针投影；0.4.13 三元表达式两个 RETURN 共用 start=127、ordinal 为 1/2；0.7.6 自由函数有 1 个顶层函数，整个输入共 4 个节点，D3 通过。0.4.11 负对照虽 solc rc0 且 Slither 构造成功，5 个节点无文件名，D3(a)/(b) 失败；0.4.13 同输入通过。见 fixture_results.json。

## 测试与开发记录

- python -B -m pytest -q -p no:cacheprovider compile_repair/tests：**55 passed、0 failed、0 skipped**，pytest 4.79 秒。先行工具链测试 37 passed、1.02 秒。
- 同参数运行 scripts/DFG/dfg_v2/tests：**2653 passed、0 failed、0 skipped、9 warnings**，188.01 秒；警告为既有 dgl/networkx 弃用提示。
- 实际命令另带独立 basetemp，完整 argv、退出码和进程耗时见开发目录 pytest_*.json/log。test_layering 随全套通过。
- 编辑工具问题：同目标 delete/add patch 被拒绝；两次 JavaScript 模板分隔符错误均发生在命令执行前；Windows apply_patch 因 WSL reparse point 无法读目标。已改用显式 wsl.exe 的 Python UTF-8 写入和安全文档模板，未改变授权范围或冻结文件。说明见 development_notes.json、document_write_note.json。
- 无测试失败、无正式运行失败，没有失败自动重试。文档检查与最终不变量审计见 CHANGE_LOG §8.5、final_audit.json、doc_check_v*.json。

## 归档与复现

旧 CP0 seal SHA256：16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b；recon SHA256：bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6。读取前逐一校验全部绑定文件。本次 seal SHA256：c28b7c7bc5269d2892027542c14724b1063a043c6d3322996a88f0146d186ff2；revalidation SHA256：97876bfd95e931058efa2c45f5675e6158bf551594a35ee150ae56adc5283ff3。

invocations.jsonl 记录真实直接 solc 退出码、命令、编译器/源码 SHA、耗时和诊断；Slither 内部子进程退出码不可观测，明确写 api_subprocess_returncodes_observed=false，未冒充观测值。完整节点在 node_facts_v2.jsonl.gz，678 对全部差异在 cross_version.jsonl。37 个编译器的绝对路径与 SHA256 列在 revalidation.json.compilers，均重新核验；Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4、solc-select 1.0.4 未变。

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
/home/zhao/miniconda3/envs/mando/bin/python -B -m compile_repair.cli revalidate-cp0 --output compile_repair/artifacts/cp0_1_v1
~~~

这是本次实际命令；该目录已存在，重用会被拒绝。获准复验时必须显式给出新目录，不能覆盖。开发目录按显式清单提交，不整体提交 pytest 临时树。

## 停止位置与后续边界

A 达到预期，**整个 CP0.1 尚未完成，CP1 不开始**。PROMPTS §4.2b 要求：“B 需要 DECISIONS.md 中 D16 已由用户决定且 authorization.json 授权建环境；C 需要 D18 已决定且授权安装。”本轮指令允许 A；此前批准仅覆盖已装的 11 个 solc。可独立执行的实现、重验和记录完成后，停在新的授权边界。

1. **D16/B 待批准**：environment_installation_request.json。按文档示例拟建独立 /home/zhao/miniconda3/envs/compile-repair-production，Python 3.8.20、Slither 0.9.6、crytic-compile 0.3.11、tree-sitter 0.20.4；测试工具精确版本、conda-forge/PyPI 来源及必要传递依赖留档要求在清单，费用上限 0 美元。mando 保留。现有 tree-sitter 库 /home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64/my-languages.so 的 SHA256 为 f424e0d52ebcdda4932a973af5357874fedd0348c78d87b1575bf15ee539d967；新环境的区间等价、结构和特征能力未验证。
2. **D18/C 待批准**：compiler_installation_request.json 列出 59 个精确版本的官方 URL、SHA256、Keccak256，费用上限 0 美元；仅在 B 通过后安装，独立追加信任清单，不改全局选择。依据已缓存官方快照（最新 0.8.38；索引 SHA256 b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac），本轮未刷新目录。

| 系列 | 已装/快照正式版本 | 缺少 |
|---|---:|---|
| 0.4.12–0.4.26 | 14/15 | 0.4.14 |
| 0.5 | 12/18 | 0.5.5、0.5.12–0.5.16 |
| 0.6 | 2/13 | 0.6.1–0.6.11 |
| 0.7 | 2/7 | 0.7.1–0.7.5 |
| 0.8 | 3/39 | 0.8.1–0.8.3、0.8.5–0.8.37 |
| 支持范围内合计 | 33/92 | 59 |

总安装 37 包含 4 个低于支持下限的历史负对照。CP1 不能假定 production 已配置或所有版本可用。第 6 步 pragma 覆盖仍可能用于精确指向缺少版本（如 0.4.14、0.5.5）的未来输入，以及官方无构建、低于 0.4.12 等使区间内无可用编译器的情况；本次 846 文件已有区间内成功版本，没有实施 rewrite。D5 用户决定与 CP0.1 审查也是 CP1 前提。

待核对项，未实施变更：B 文案写“0.8.24 transient”，审查 fixture cp0_review_v1/features/f0828_transient.sol 却写 pragma >=0.8.28，使用高级瞬态变量声明。进入 B 前须核对官方语法边界，不能直接把该 fixture 套到所有 >=0.8.24 版本；如果需要拆分探针或修改文案，先咨询用户并登记。A 没有不一致验收项，没有实施其他替代方案。

本轮仅本地提交，标题以 CP0.1 complete A 开头，提交号由包含本报告的提交确定并在最终答复给出。没有 push、新下载/安装、LLM 调用、HGT 训练、GPU 锁操作、输入改写或图存储。


## B. 2026-11-13 生产环境续作：已达到 r2.4 预期（修改 AI：Codex）

本节及随后 C 节是对上文 A 报告的追加；上文的历史状态与 A 结果原样保留。执行依据为完整 PROMPTS r2.4（尤其 §1.7、§4.1、§4.2b）、HANDOVER §0–5、DECISIONS 与 CHANGE_LOG §9、§10。起始 HEAD 为 897fbd03116040ddbc8d106db1b844624f512091，git pull --ff-only origin compile-repair 返回 Already up to date。没有重跑 A 或 cp0_v2。

### B.1 授权与环境身份

用户 2026-11-13 明确授权 D5 区间升序、D16 独立生产环境与 D18 在 B 全通过后安装 59 个编译器；此前原话为“I have followed the approach you recommended.”。两份 authorization.json 在任何安装之前创建，分别位于 artifacts/cp0_1_env_v1/ 和 cp0_1_compilers_v1/，包含精确版本、来源、用户原话、日期、0 美元上限和限制。旧 cp0_1_development_v1/environment_installation_request.json（0.9.6）已作废但未修改；替代请求位于 cp0_1_env_v1/environment_installation_request.json。

新环境 /home/zhao/miniconda3/envs/compile-repair-production 使用 Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2、solc-select 1.0.4、tree-sitter 0.20.4、pycryptodome 3.20.0、pytest 7.4.4。Python 与 31 个必要 conda 包全部来自已有缓存，逐项核对官方 repo.anaconda.com/pkgs/main 元数据 SHA256 后以 --offline --copy 建立；未下载 conda 包。PyPI 的 53 个包（含六个直接指定包和必要传递依赖）先解析精确版本、URL 与 SHA256，再用 --no-deps --require-hashes 按锁文件安装。全部 57 个 Python distribution 的路径均属于新环境，pip check 通过；完整版本见 pip_freeze.txt、environment.json，来源见 conda_packages.lock.json、conda_downloads.jsonl、pip_resolution_isolated.json、pip_install_report.json。

安装前发现 conda 默认读取 ~/.local/lib/python3.10/site-packages，最初解析会借用已有 typing_extensions。未使用这份解析安装；仅在新环境设置 PYTHONNOUSERSITE=1，并在每次直接调用显式传入，重新解析完整依赖。原始解析保留，处理见 isolation_adjustment.json；用户目录和其他环境未修改。所有联网经既有代理，不设置直连回退；未运行 solc-select install/use。

### B.2 限定实现与测试方式

仅修改生产代码 toolchain/slither.py：配置 production 的确切版本对；check_profile 优先标准库 importlib.metadata、Python 3.7 下回退 importlib_metadata；记录 crytic_compile_platform 及实际平台类。为了在 Slither 的已知 AssertionError 下仍保留实际平台，production 使用公开 API 组合 CryticCompile(target, 原 kwargs) 与 Slither(crytic, 原 kwargs)，未改变编译参数；regression_6c 仍调用冻结 _compile。真实三元表达式测试与冻结 _compile 的输出按 key5、有序 IR、length 全部相同，没有复制或 monkeypatch 冻结代码。

新增 tests/test_production.py，标准库与 backport 路径分别在生产 Python 3.10 和 mando Python 3.7 中实测。tests/test_slither_v2.py、test_toolchain.py 只对依赖 0.8.0 指纹/节点数的五个既有真实测试增加 profile 限定跳过；与 profile 无关的原有测试继续执行。19 个审查探针原字节复制到 tests/fixtures/features/，文件名均未改变；SHA256、来源与最低版本见 feature_probes_B.json。两处历史文件名并不等于源码下界：f0807_free_function.sol 的 pragma 为 >=0.7.1，h0811_encodecall.sol 为 >=0.8.12；适用范围按实际 pragma，未改探针。

语言库仍为 /home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64/my-languages.so，SHA256 f424e0d52ebcdda4932a973af5357874fedd0348c78d87b1575bf15ee539d967。使用冻结 frontend.parse 与 versioning.interval 在两个环境各计算 846 份源码，逐条区间、源码 SHA、tree-sitter 版本和库 SHA 全同，见 intervals_mando.json、intervals_production.json、interval_equivalence.json。该检查未编译 A 的矩阵，不构成重做 A。

### B.3 固定版本真实验收

输入仍为 cp0_v2/recon.json 的 846 个文件与 selection.ascending。原归档 cp0_1_v1/node_facts_v2.jsonl.gz 的 SHA256 5202a8754e8452af387a80e43c6b7d23aa796074273cfdaf8882af9c304a319b 在读取前核对，只读使用；比较完整 key5 多重集合，不按 source length 判定结构。

| 项目 | r2.4 预期 | 本机实测 | 结论 |
|---|---:|---:|---|
| 直接 solc rc0 | 846 | 846 | 通过 |
| production D3 | 843/846 | 843/846 | 通过 |
| 0.4.24 AssertionError | 指定 3 份 | 同 3 份 | 通过 |
| 构造成功后的 D3(a)/(b) 失败 | 0/0 | 0/0 | 通过 |
| 实际 crytic 平台 | solc | 846/846 为 solc，含三次断言失败 | 通过 |
| 结构不同文件 | 435 | 435 | 通过 |
| 新增隐式 RETURN / ENDASSEMBLY | 2182 / 128 | 2182 / 128 | 通过 |
| 减少合成 OTHER_ENTRYPOINT / 重数 EXPRESSION | 48 / 6 | 48 / 6 | 通过 |
| 全部 key5 相同文件 | 审查为 408 | 408 | 通过 |
| 19 特征、当前适用 0.8.x 组合 | 全通过 | 23/23 | 通过 |
| tree-sitter 区间等价 | 846/846 | 846/846 | 通过 |

完整 435 份 key5 差异列在 structure_differences.json。843 个成功文件共 110996 个节点，顶层函数数为 0。key5 与有序 IR 全部相同的文件为 56；在两边共有 key5 上，783 个文件、24823 个节点的有序 IR 不同，前 20 个例子见 ir_differences.json；按原文仅统计，不作为失败。正式运行未出现非预期项、未重试，详见 production_comparison.json 与逐次 production_invocations.jsonl；节点归档为 production_node_facts_v2.jsonl.gz。

已知失败单列：reentrancy_bonus.sol（628f60b16c87…）、reentrancy_cross_function.sol（583b8636921a…）、reentrancy_insecure.sol（97bb37ef327f…），均使用 0.4.24、solc rc0、实际 solc 平台、Slither AssertionError。没有把构造失败当成 D3 通过。

### B.4 工作副本试验与能力边界

仅在 cp0_1_env_v1/rewrite/ 写三个工作副本，把各自唯一的“(bool success, ) =”改为“bool success =”；原始语料未修改，精确字节位置与前后 SHA 见 rewrite_manifest.json。三个副本在 production 与 regression_6c 下均 solc rc0、D3 通过；相对原 A 节点数分别为 11→10、11→10、6→5。逐节点 key5/IR/length 差异见 rewrite_production.json 与 rewrite_regression_6c.json，偏移随较短改写而变化，不能忽略。

此处仅是 B 指定的试验，没有实现 §3.2 第 10 行改写规则；规则仍属 CP6。探针通过只说明当前编译与 D3 构造成立，尤其 transient 未证明语义建模正确，也未证明全部 CFG/CG 边或任意合约行为等价。

### B.5 测试、耗时与进入 C 的门槛

生产环境：python -B -m pytest -q -ra -x -p no:cacheprovider --basetemp compile_repair/artifacts/cp0_1_env_v1/pytest_production_v2 compile_repair/tests，77 passed、6 skipped、8.31 秒。跳过的是 Python 3.7 backport 路径一项和 regression_6c 专属五项。mando 同模块测试 58 passed、25 skipped、1.96 秒，跳过 Python 3.10 路径一项及生产环境专属 24 项。mando 的 scripts/DFG/dfg_v2/tests 为 2653 passed、9 个既有警告、193.29 秒；test_layering 通过，非测试生产 Python 文件仍为 9 个。

开发期一次测试收集失败来自新测试正则的双重转义，尚未运行任何探针即报错；修正转义后重新测试，未改变特征、D3 或验收数字。pytest_production_v1.log 与 development_corrections.json 保留该现场。另有初次受限 WSL 只读调用被 sandbox 拒绝，改用显式 WSL 的获审升级调用成功；没有修改权限或绕过自动审查。

正式 B 比较耗时 292.588 秒；直接 solc 合计 75.771 秒，Slither 合计 189.683 秒。因此 CP2 固定版本 846 文件的编译与 D3 部分观测约 265.454 秒；这不含候选搜索、修复、图存储、跨版本或 6c 重放，不是 CP2 总时间保证。B_acceptance.json 于 2026-11-13 12:55:58 UTC（07:55:58 EST）记录全部门槛通过，包含包、区间、探针、三副本、两套测试、mando 元数据与已有 37 个 solc 文件不变、全局选择不变；只有此后才开始 C 下载。

复现命令源码作为只读执行证据保存在 production_batch_command.txt、interval_command.txt、rewrite_command.txt，并非新增模块入口。获准重新测量时应先改为新产物目录，不能覆盖本轮文件。当前结论为 B 通过；C 的安装与兼容性结果以下节为准。


## C. 2026-11-13 编译器补齐完成；兼容性失配后停止（修改 AI：Codex）

### C.1 安装与信任链

B_acceptance.json 全部通过后，才执行 cp0_1_compilers_v1/authorization.json 绑定的原始 59 版清单。每个版本从清单中的 https://binaries.soliditylang.org/linux-amd64/ 官方 URL 下载，先在内存中核对官方 SHA256 与 Keccak256，再排他创建此前不存在的 solc-VERSION 目录和二进制，设置执行权限并检查 --version 的精确版本及 rc0。没有运行 solc-select install/use，没有改已有 ~/.solc-select 文件、全局选择、旧可信清单或原安装请求。

59/59 安装与双哈希/版本校验通过，下载总字节 722168656，耗时 335.193 秒，见 installation_summary.json、installation_invocations.jsonl。独立新增 trusted_compilers_addition.json 绑定本批授权、B 门槛和原官方索引；调用现有 load_additions 再核验完整信任链通过。索引 SHA256 仍为 b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac，未刷新快照。

| 支持系列 | 已安装 / 快照正式版本 | 缺少 |
|---|---:|---:|
| 0.4.12–0.4.26 | 15/15 | 0 |
| 0.5 | 18/18 | 0 |
| 0.6 | 13/13 | 0 |
| 0.7 | 7/7 | 0 |
| 0.8.0–0.8.38 | 39/39 | 0 |
| 支持范围内合计 | 92/92 | 0 |

总安装 96 个，含原有 4 个低于支持下限的负对照。coverage.json 记录的是安装完成时的快照，compatibility_validation_status 当时为 pending；最终兼容性状态以 compatibility.json、final_status.json 为准。92/92 不是所有语法或图建模全部验证通过。

### C.2 真实兼容性验收与停止现场

安装后按预先记录的 compatibility_plan.json 执行：版本升序，每版先跑原 CP0 §5b 系列 fixture，0.8.4 起加 custom errors，再跑适用的 19 个审查特征。自由函数 probe 也适用于新装的 0.7.1–0.7.5；没有改源码、默认编译选项或特征下界。计划 496 组，遇首个非预期项即停，不自动重试。

| 类别 | 计划 | 已执行 | 通过 | 失败 | 未执行 |
|---|---:|---:|---:|---:|---:|
| CP0 §5b 系列 fixture | 59 | 46 | 46 | 0 | 13 |
| CP0 custom errors | 33 | 20 | 20 | 0 | 13 |
| 19 个审查特征的适用组合 | 404 | 159 | 158 | 1 | 245 |
| 合计 | 496 | 225 | 224 | 1 | 271 |

45 个新版本的全部适用组合通过；0.8.24 已执行 12/18（11 过、1 失败）；0.8.25–0.8.37 共 13 个新版本未开始兼容性验证。已执行部分 wall time 12.224 秒，直接 solc 合计 1.455 秒、Slither 合计 3.562 秒，逐次命令、退出码、诊断、平台与耗时见 compatibility_invocations.jsonl，节点见 compatibility_node_facts_v2.jsonl.gz。

首个非预期项：solc 0.8.24 + tests/fixtures/features/h0824_blob.sol，文件 SHA256 c9e90c95e2aa4ff6fca95636caf80ceca31c2ba40cdefdfcfa204b18de141cf2，编译器 SHA256 fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f。实际 solc 退出码为 1，错误首行为 Error: Undeclared identifier. Did you mean "blockhash"?，指向 blobhash(0)；Slither 未运行。实际命令如下（仅记录，不代表获准重跑）：

~~~bash
/home/zhao/.solc-select/artifacts/solc-0.8.24/solc-0.8.24 /home/zhao/SmartContract/ge-sc-llm-compile/compile_repair/tests/fixtures/features/h0824_blob.sol --combined-json abi,ast,bin,bin-runtime,srcmap,srcmap-runtime,userdoc,devdoc,hashes --allow-paths . compile_repair/tests/fixtures/features/h0824_blob.sol
~~~

### C.3 与原文的差异、未实施建议及后续边界

本结果不符合 r2.4 对 production 特征探针全部通过的预期，因此 C 未通过，CP0.1 整体仍未完成，CP1 不开始。按用户要求及 §4.1“失败就停，保留现场，不自动重试”，停止余下 271 组，不通过降低判据、改变编译参数、改写 probe 或忽略失败使其通过。19 个审查 probe 在 0.8.38 上的成功，不能单独证明其在声明的最低版本及当前默认编译配置上也成立。

只登记、未实施的后续建议：先核对 h0824_blob 的高级语法引入版本与适用 EVM 设置，并审查同类特征下界的证据；若需调整 fixture 下界或编译配置，先请用户确认，再以新批次验证剩余矩阵及受影响组合。当前失败消息不足以证明仅修改 EVM 参数即可解决，本轮没有做这类试验，也没有下载文档或引入其他方案。

CP1 的已知参数：D5 升序；production 为 0.11.6/0.4.2；上述 92 个支持范围内编译器均安装并可信，具体绝对路径及 SHA 见原 recon 与独立 addition。pragma 覆盖不再因 0.4.12–0.8.38 快照内缺少补丁版本而触发，但低于支持下限、超出快照或无官方构建导致区间内没有可用编译器的情形仍需区分；区间内编译失败或 Slither 失败本身不满足“没有可用编译器”的覆盖前提。C 的未通过状态及后续审查仍阻止 CP1。

### C.4 冻结检查与提交边界

frozen_audit.json 核对 27845 个模块外已跟踪文件、204 个已有产物、37 个旧 solc 文件、205 个 mando 包元数据文件，差异均为 0；experiment.run._code_refs() 的 354 项一致。A 报告旧字节前缀与原 0.9.6 请求哈希不变，生产代码仍为 §3.10 内的 9 个文件。源码原件、EdgeSem、原 CP0/A 产物与仓库根目录记录均未改。

本轮费用 0 美元，LLM 调用 0；无训练、GPU 锁或图存储操作，没有实现 CP1/CP6。已完成的 B 测试结果见上节；C 失败后未继续生产探针或重复正式运行。按强制记录完成 CHANGE_LOG §11、HANDOVER 当前状态与四段交接、PROGRESS、DECISIONS、两批 README、doc_check 后本地提交，不 push。


## C 续：编译设置、IR 确定性与兼容性续验（2026-11-13，修改 AI：Codex）

### C 续.1 范围与实现

起始提交 3742fb75e535b5517ded58659e78737a01b51000，按用户要求先 pull --ff-only，结果 Already up to date；完整阅读 PROMPTS r2.5（含 §4.1）、HANDOVER §0–5、DECISIONS、CHANGE_LOG §11/§12 和 cp0_1bc_review_v1/README。A、B 与原 C 报告前缀保持原字节，只在此追加。

生产代码只修改 `core/model.py`、`toolchain/solc.py`、`toolchain/slither.py`。Compilation 增加默认空的有序 settings 元组，保留原有位置参数兼容性。compile_file/command 仅允许 --evm-version 后跟单个名称和 --via-ir，保持调用方顺序并追加到命令末尾；拒绝未知选项、重复选项与包含空白的名称。错误首行解析在崩溃时把原 banner 与 std::exception::what 消息一起记录，完整 stderr 仍原样保存，因而不会丢失 0.8.26 的 via-ir 原因。

production 把同一个 settings 通过 solc_args 同时传给公开 CryticCompile 与 Slither 构造器，空设置不传；regression_6c 对非空设置显式抛错，冻结 _compile 不改。node_facts 把限定形式的 Python 对象 repr 规范化为模块/类名，counts 增加 ir_object_repr_replacements 与 ir_object_repr_unresolved；仍有对象地址时 D3(a) 失败，并给出 key5、IR 行号和原文诊断。只处理该 repr 模式，普通十六进制字面量保留，CP0 投影函数 AST 与起始提交完全相同。

测试修改 `tests/test_production.py`，新增 `tests/test_settings.py`。既有 feature 参数化保留全部原组合，把 r2.5 指定的 5 个默认失败组合改为严格负对照，并加入对应设置正对照，没有 xfail 或放宽 D3；另测试参数白名单、命令及记录、regression 拒绝、真实错误文本、替身 IR 的稳定结果/替换次数/残留失败。28 个 Solidity fixture（包括 19 个特征探针）未改字节。生产 Python 仍为 9 个，测试文件现为 6 个；文件表与分层遵守 §3.10。

### C 续.2 真实验收

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

两次生产 wall 分别 309.983、282.392 秒；20 文件回归 12.248 秒；501 组兼容性 28.131 秒，均为各自 json 中 monotonic 实测。兼容性全部 59 版通过，包括审查未覆盖的 0.8.28–0.8.37（逐版结果见 compatibility.json）。

### C 续.3 测试与开发记录

| 检查 | 实测 | 原始日志 |
|---|---|---|
| 新逻辑与分层（production / mando） | 各 27 passed | unit_production.log、unit_mando.log |
| 完整模块（production） | 506 passed，6 skipped，28.69 秒 | pytest_production.log |
| 完整模块（mando） | 83 passed，429 skipped，6.60 秒 | pytest_mando.log |
| 冻结 DFG v2（mando） | 2653 passed，9 warnings，181.50 秒 | pytest_dfg.log |

完整命令含 -x、-p no:cacheprovider 和新批次 basetemp，见 test_summary.json 与各 pytest_*.json。production 跳过 1 项 Python 3.7 backport 路径及 5 项 regression 专用检查；mando 跳过 1 项标准库路径及 428 项 production 专用检查。与 profile 无关的测试均通过，DFG 的 9 条均为既有 distutils/networkx 弃用警告。

本轮没有非预期验收结果，没有测试失败后重跑，也没有方案外算法变更。读取阶段 WSL 未安装 rg，按现有 Python/sed 完成只读检查；ir_object_repr.json 实际是两个连续 JSON 对象，首次单对象 json.loads 报 Extra data 后按原格式分别 raw_decode，原文件不改。这属于证据格式适配，不改变 4 文件/4 行预期。生产原始诊断保留已知断言的源码缩进，以无损 gzip 提交并逐字节回读校验，原日志留在本地，SHA 与压缩对应关系见 log_compression.json。

### C 续.4 归档与复现

新产物只在 artifacts/cp0_1_env_v2/ 与 cp0_1_compilers_v2/。完整提交文件清单见 cp0_1_env_v2/file_inventory.json；各目录 seal.json 的 SHA256 见 cp0_1_env_v2/seal_hashes.json。invocations 逐次保留源码/编译器 SHA、实际命令、settings、退出码或 D3、错误与耗时，节点归档独立重算指纹通过；baseline 与 frozen_audit 记录冻结检查。未提交二进制、下载缓存或 pytest 临时树。

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
# 下列是实际等价命令；所有输出采用 x/xb 创建，已存在时拒绝覆盖。
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' production_run1
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' production_run2
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/production_command.txt").read(), "production_command.txt", "exec"))' regression_sample
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_compilers_v2/compatibility_command.txt").read(), "compatibility_command.txt", "exec"))'
# run_checks 会使用对应的已安装解释器、-x 和独立 --basetemp；完整 argv 在同名 json 中。
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_production
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_mando
/home/zhao/miniconda3/envs/mando/bin/python -B -c 'exec(compile(open("compile_repair/artifacts/cp0_1_env_v2/run_checks.txt").read(), "run_checks.txt", "exec"))' pytest_dfg
```

复现时须使用新的空批次目录并相应设置脚本的 out/envout 路径，不能原地重跑已封存批次。实际 Windows 调用为 UTF-8 PowerShell here-string 经 wsl.exe --cd 进入本工作树，执行相同脚本文本；没有 shell 字符串拼接 solc 参数。

### C 续.5 CP1 参数与停止边界

CP1 输入参数：production 固定 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2；regression_6c 固定 mando 0.8.0 / 0.2.4。可信编译器沿用 cp0_v2/recon.json 中 37 个身份与 cp0_1_compilers_v1/trusted_compilers_addition.json 中 59 个新增身份，其中 92 个在支持区间、4 个历史负对照低于下限，必须经原信任链校验。设置表第 1 行是 0.8.24 中 Cancun 内置函数/全局量未找到或未声明时加 --evm-version cancun（4/4 正负对照验证）；第 2 行是 Require with a custom error is only available using the via-ir pipeline. 时加 --via-ir（0.8.26 的 1/1 正负对照验证）。依据仍为 PROMPTS §1.8、§3.3 第 3a 条和审查中已核对的官方发布说明，本步不额外下载文档。

口径限制：501 组是明确批准的 59 个新增版本矩阵，不是对 92 个版本、每一种语法或完整 CFG/CG 语义的穷举证明。另 33 个先前安装版本的原证据保留在 cp0_v2 与 cp0_1_env_v1，不为扩大结论而重跑 A/B。三个合法旧合约的 Slither AssertionError 仍是已知问题；没有把它们写成已修复。

用户本轮明确要求执行 r2.5 §4.2c，并规定需要安装/下载或验收不符即停。本次未发生上述停止条件；没有新增授权请求，没有安装、下载编译器/语料/文档、LLM 调用、全局 solc 切换或 HGT 训练，费用 0 美元。A、B 结论、旧产物和既有 C 失败现场均保留。本步只完成工具链接口与验证：按错误自动触发设置、版本升序选择和两行设置表属于 CP1；第 10 行源码改写属于 CP6，均未实现。CP0.1 C 续已完成本机验收，仍须审查通过后才能开始 CP1。
