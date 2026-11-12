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
