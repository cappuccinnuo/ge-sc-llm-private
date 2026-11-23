# CP4 破坏与修复评分基准

2026-11-22 · Codex · PROMPTS r2.16 §4.6a · compile-repair · 起点 06ad69c2

## 实现

CP4 为后续修复阶段提供带真值的评测输入和评分入口。在已有成功合约的副本上制造编译或输入错误，用历史 Slither 图衡量修复后的结果。实际修复规则由后续阶段实现。

新增 `evaluation/benchmark.py`，负责稳定分组、分层抽样、词法算子、两阶段触发判定与图评分。`core/provenance.py` 追加 `compose_offsets`，它核验两段编辑记录，以实际字节和左右边界恢复可证明的偏移对应关系。`cli.py` 增加 `benchmark` 和 `benchmark-score`。测试位于 `tests/test_benchmark.py` 和 `tests/test_cp1_1.py`。

## 真实验收

| 项目 | 预期 | 实测 |
|---|---|---|
| 历史真值 | MANDO 对齐 v5，项目满足 D3、绑定检查及 D21 | 846 项状态对齐，843 个成功项的图逐字节相同 |
| 对照 | 200 个实测成功，版本、设置与图字节相同 | 200/200 |
| 逆向还原 | 每个纳入样本的 kept、CFG、调用比例均为 1，lost 和 added 均为 0 | 11,858/11,858，涉及 5,965 个基础单元 |
| 错误修复 | 逐算子发现不等 | 22/22 个实际编译的错误修复和 1/1 个缺节点图被检出 |
| 历史回放 | 单列已保存的 Slither 失败 | 核对 24 份历史结果及其编译和图状态 |
| 范围 | 17 个生产文件，冻结代码一致 | 16 → 17，DFG 的 354 项代码引用一致 |

### 基础与划分

31,307 个既有单元中有 21,223 个历史成功。5,087 个成功图没有节点，其中 8 项的语言也未定，两个排除原因有重叠。其余 16,136 个作为基准。DAppSCAN 9,233、Trace_CVEs 14、Trace_on_chain 4,565、Trace_repo 1,345、MANDO 843、SOChecker 136。清单记录入口、完整闭包的原结果引用、选定版本与设置、图 SHA 和节点数。 [基础筛选](artifacts/cp4_v1/base_summary.json)

DAppSCAN、Trace_repo 按项目根，Trace_on_chain 按地址，Trace_CVEs 按 CVE，MANDO、SOChecker 使用同一内容 SHA 命名空间。对组 ID 加前缀 `cp4-split-v1:` 后取 SHA256 的前八位十六进制数，模 5 为零进 dev，其余进 test。采样种子 20261122。组决定划分，单元和样本比例由组大小决定。

| 集合 | dev 组 | dev 样本 | test 组 | test 样本 |
|---|---:|---:|---:|---:|
| 基础单元 | 1,204 | 3,933 | 4,808 | 12,203 |
| 未改动对照 | 40 | 48 | 125 | 152 |
| 构造候选 | 649 | 3,652 | 2,592 | 13,780 |
| 实际纳入 | 552 | 2,460 | 2,204 | 9,398 |

### 各算子实测

每个算子在每套语料中按编译器次版本系列分层抽取，上限 200。先固定抽样表，再运行各候选。同一个基础单元可以供不同算子使用。下表的示例为变异清单 SHA256 前 12 位，完整 SHA 和各类的两阶段诊断可在 JSON 中定位。506 行 TSV 给出各算子、语料与次版本系列的完整交叉统计。 [分层统计](artifacts/cp4_v1/strata.tsv) · [逐类示例与完整 SHA](artifacts/cp4_v1/benchmark_counts.json)

| 目标类别 | 构造规则 | 适用 | 抽取 | 纳入 | 环境解决 | 未触发 | 示例 SHA |
|---|---|---:|---:|---:|---:|---:|---|
| unresolved_package_import | 移除可解析的包依赖文件 | 0 | 0 | 0 | 0 | 0 | 无适用项 |
| missing_relative_file | 移除相对导入的依赖文件 | 7,059 | 400 | 400 | 0 | 0 | 1240e51381e7 |
| missing_base_contract | 删除唯一的本地基类定义 | 10,989 | 821 | 723 | 0 | 98 | acb1e1f7a3cc |
| undeclared_identifier | 删除另有引用的事件声明 | 10,115 | 828 | 734 | 33 | 61 | 5bc993201915 |
| duplicate_definition | 在同一作用域复制完整定义 | 16,136 | 950 | 864 | 0 | 86 | db32225b43ba |
| multiple_license_or_pragma | 插入冲突的 ABI coder 指令 | 6,595 | 635 | 616 | 0 | 19 | 9fb067b7744b |
| encoding | 将声明名首字节替换为非法 UTF-8 | 16,136 | 950 | 0 | 0 | 950 | 6f87aa039275 |
| unbalanced_structure | 删除顶层定义的结束花括号 | 16,136 | 950 | 0 | 0 | 950 | 61fec38a41d9 |
| parser_error_other | 用逗号替换声明名 | 16,136 | 950 | 950 | 0 | 0 | 3c6e87dcaaff |
| type_error_other | 将分支条件替换为整数表达式 | 11,985 | 831 | 755 | 0 | 76 | 0bbf4292486c |
| codegen_only | 插入同时使用多个局部变量的函数 | 14,546 | 949 | 763 | 80 | 106 | f2883cba04ec |
| closure_version_conflict | 将依赖 pragma 固定到入口区间外 | 7,046 | 400 | 400 | 0 | 0 | d65381df5604 |
| io_error | 将导入指向不存在的文件 | 7,059 | 400 | 400 | 0 | 0 | 5ce3ec29b8c9 |
| docstring_error | 在 NatSpec 注明不存在的参数 | 15,810 | 934 | 857 | 1 | 76 | d74f8bbc4245 |
| syntax_error | 删除函数显式可见性 | 15,714 | 933 | 657 | 207 | 69 | 05928c8e20ab |
| unimplemented_feature | 插入旧代码生成器上的嵌套动态数组赋值 | 12,256 | 921 | 0 | 422 | 499 | 0763f2a81d0b |
| unsupported_disjunction | 将 pragma 改为合法析取表达式 | 16,058 | 931 | 931 | 0 | 0 | 657741887584 |
| unsupported_expression | 将版本表达式换成不支持的符号 | 16,058 | 931 | 931 | 0 | 0 | 88bcadc09daf |
| unterminated_pragma | 删除 pragma 终止分号 | 16,058 | 931 | 689 | 0 | 242 | 1a5dae8ae65f |
| pragma_missing_semicolon_candidate | 删除下一条指令或声明前的 pragma 分号 | 16,045 | 929 | 238 | 0 | 691 | be71beb8bb0f |
| declaration_error | 将函数改为相应版本禁止的同合约名 | 13,298 | 908 | 0 | 0 | 908 | 2b0b570d5555 |
| standard_json_input | 将源文件和有效设置包装为 Standard JSON | 16,135 | 950 | 950 | 0 | 0 | 8fb20f0d78b4 |

17,432 个候选中纳入 11,858，环境解决 743，未触发 4,831。11,560 项单独使用选定 solc 与设置探测，环境流水线另有 172,620 次可观测 solc 调用、743 次 Slither 分析。其余 5,872 项的目标在版本规划、项目组装或输入阶段，省去单独的选定编译器调用。收据保留两阶段类别、诊断首行和独立工作目录中的编辑字节证据。

五个源码类别缺少可用于计算后续修复率的真实纳入样本。合格基础闭包内没有可删除的包依赖。950 个 encoding 均归入 parser_error_other。950 个 unbalanced_structure 中有 906 个主因为 other。921 个 unimplemented_feature 中有 422 个被环境解决，其余未通过目标归因。908 个 declaration_error 也未达到双重归因。各类诊断分布和未适用原因均已保留。

slither_incomplete 使用历史失败收据和手写缺节点图。另有八类在 CP3.2 清单中没有源码算子。other 需要进一步诊断，json_error 属输入封装，internal_compiler_error、compiler_exception、fatal_error 属工具限制，warning 为警告，slither_no_timeout 尚无确定的源码构造，non_solidity_input 为其他语言输入。

### 评分与停止现场

compiled 取实际 solc 成功且 D3 为真。按文件将真值节点起点经两段编辑映射到修复位置，比较 key5、节点类型及规范化 SlithIR。保留节点间的 CFG 边与调用保留重数，以交集重数除以并集重数，双方均空时取 1。另计破坏影响数、恢复后缺失数、新增节点位置、新增字节与破坏区间的顶层定义关系，以及修复改动等级。

逐样本读回破坏文件和替换字节，验证 SHA 后应用逆编辑。同一基础单元的每个逆编辑结果均与原闭包逐文件字节相同，因此可共享该闭包独立观测的生产图。累计比对 1,933,000 个保留节点、1,621,602 条 CFG 边和 816,743 条调用（按样本累计）。破坏时受影响节点 119,099，其中删除影响 119,081，最终 lost=0、added=0。5,965/5,965 份最终图亦与对应真值字节相同。 [最终验收](artifacts/cp4_v1/acceptance.json)

首轮逆编辑运行测了 4,316 项。cp3_23979 / codegen_only 的字节已还原，298/299 个保留节点相同。两份图仅一条 IR 不同，嵌入的 11,199 字节创建代码只有末尾 CBOR 中的 IPFS 摘要不同。两次工具使用相同 solc 0.6.12、设置和输入字节，输入文件都叫 input.sol，绝对路径不同。获准后逐次核验工作字节，在历史工具源路径只读重编。实测图字节相同，299/299 节点、254/254 边、147/147 调用相同。4,315 项原通过结果保留，在新批次评分 7,543 项（含探针）。 [首轮](artifacts/cp4_v1/inverse_acceptance.json) · [差异](artifacts/cp4_v1/restoration_identity_request.json) · [同路径探针](artifacts/cp4_v1/identity_continuation/probe.json) · [续跑](artifacts/cp4_v1/identity_continuation/acceptance.json)

手写项目在逆修复之外更改独立函数的返回值，22 个错误版本均能编译，评分均发现差异。历史类别用删去一个节点及其关联边调用的无害图，检测到一个保留节点缺失。该项另以 24 个旧单元核验失败归因。 [负例](artifacts/cp4_v1/wrong_repairs.json) · [历史回放](artifacts/cp4_v1/analyzer_history.json)

## 测试与开发记录

| 环境 / 套件 | 结果 |
|---|---|
| production | 815 passed, 6 skipped in 87.16s (0:01:27) |
| mando | 352 passed, 469 skipped in 53.89s |
| dfg | 2653 passed, 9 warnings in 227.31s (0:03:47) |

生产首轮在旧迁移测试的 16 文件断言停止，36 项通过、1 项失败。获准更新为 17 且包含 benchmark.py，原迁移执行和逐文件 SHA 检查完整保留，使用新目录续跑。新建 WSL 客户端期间曾出现 0x8007274c，通过共享工作树核对既有日志与收据，原实验进程继续运行，每个候选只构造一次。

生产代码逐函数行数在 acceptance.json 的 scope.changes_by_function。抽样执行时的源码快照与结项文件按字节前缀和新增函数名核验。

| 生产路径 | 新增行 | 删除行 |
|---|---:|---:|
| compile_repair/cli.py | 15 | 0 |
| compile_repair/core/provenance.py | 48 | 0 |
| compile_repair/evaluation/benchmark.py | 673 | 0 |

<details><summary>逐函数增删行数</summary>

| 路径与函数 | 新增行 | 删除行 |
|---|---:|---:|
| compile_repair/cli.py · main | 15 | 0 |
| compile_repair/core/provenance.py · 模块级 | 2 | 0 |
| compile_repair/core/provenance.py · compose_offsets | 46 | 0 |
| compile_repair/evaluation/benchmark.py · 模块级 | 102 | 0 |
| compile_repair/evaluation/benchmark.py · _digest | 2 | 0 |
| compile_repair/evaluation/benchmark.py · group_and_split | 6 | 0 |
| compile_repair/evaluation/benchmark.py · stratified_sample | 17 | 0 |
| compile_repair/evaluation/benchmark.py · environment_observation | 8 | 0 |
| compile_repair/evaluation/benchmark.py · control_observation | 23 | 0 |
| compile_repair/evaluation/benchmark.py · __init__ | 46 | 0 |
| compile_repair/evaluation/benchmark.py · _until | 4 | 0 |
| compile_repair/evaluation/benchmark.py · bounds | 2 | 0 |
| compile_repair/evaluation/benchmark.py · top_regions | 19 | 0 |
| compile_repair/evaluation/benchmark.py · base_contents | 12 | 0 |
| compile_repair/evaluation/benchmark.py · _settings_object | 9 | 0 |
| compile_repair/evaluation/benchmark.py · mutation_sites | 95 | 0 |
| compile_repair/evaluation/benchmark.py · site | 2 | 0 |
| compile_repair/evaluation/benchmark.py · build_mutation | 20 | 0 |
| compile_repair/evaluation/benchmark.py · classify_trigger | 7 | 0 |
| compile_repair/evaluation/benchmark.py · _materialize_closure | 9 | 0 |
| compile_repair/evaluation/benchmark.py · assess_mutation | 65 | 0 |
| compile_repair/evaluation/benchmark.py · _damaged_ranges | 16 | 0 |
| compile_repair/evaluation/benchmark.py · _near | 9 | 0 |
| compile_repair/evaluation/benchmark.py · _correspondence | 30 | 0 |
| compile_repair/evaluation/benchmark.py · _identity | 4 | 0 |
| compile_repair/evaluation/benchmark.py · _nodes | 8 | 0 |
| compile_repair/evaluation/benchmark.py · _at_original | 2 | 0 |
| compile_repair/evaluation/benchmark.py · _edges_and_calls | 12 | 0 |
| compile_repair/evaluation/benchmark.py · _multiset_score | 5 | 0 |
| compile_repair/evaluation/benchmark.py · score_graphs | 64 | 0 |
| compile_repair/evaluation/benchmark.py · benchmark_entry | 31 | 0 |
| compile_repair/evaluation/benchmark.py · score_request | 26 | 0 |
| compile_repair/evaluation/benchmark.py · content | 7 | 0 |
| compile_repair/evaluation/benchmark.py · decoded | 4 | 0 |
| compile_repair/evaluation/benchmark.py · replay | 7 | 0 |

</details>

## 归档与复现

证据 seal.json 的 SHA256 为 `23fa2d392f9a776fe1c4636e2ddc7c8a36e96b1c8dfc67de5cbb70f0dbaeec7c`。生产使用 Slither 0.11.6、crytic-compile 0.4.2，支持快照 92 个 solc。execution_settings.json 绑定信任清单，control_acceptance.json 指向含逐编译器可执行文件 SHA 的外部 seal。候选阶段使用 6 个进程，耗时 831.451 秒。对照 159.101 秒，首轮逆向评分 689.102 秒，补充逆向评分 486.799 秒。费用 0 美元。源码和替换字节只保存在已批准的本地目录。 [复现命令、CLI 请求与归档索引](artifacts/cp4_v1/README.md) · [封存](artifacts/cp4_v1/seal.json)

## 停止位置与后续边界

CP4 实施和验收完成，下一步为独立审查。CP5–CP9 可使用 dev 的 2,460 个纳入样本开发，test 的 9,398 个用于报告。五个零纳入类别及历史回放类别应分别报告。该基准测量图事实的保留程度，实际规则修复能力由后续阶段测量。


## CP4.1

### 2026-11-22 诊断清点与运行环境检查点（修改 AI：Codex）

PROMPTS r2.17 §4.6b 的类型测量和全量重判尚待执行。表内的 CP4 数量引用上轮封存的观测；本轮已实际执行旧诊断模板的清点。 [清点证据](artifacts/cp4_1_v1/old_other_templates.json)

| 观测范围 | 本次核对的原始调用数 | 旧分类器的 other 诊断出现次数 |
|---|---:|---:|
| CP3 有测量的 31,071 个单元 | 76,402 | 13,321 |
| CP4 原候选的环境阶段 | 172,620 | 59,569 |
| CP4 原候选的选定版本 | 11,560 | 3,004 |

去重得到 96 个模板。95 个已准备源码夹具，1 个 solc 0.4.12 内部异常只留存历史诊断证据。用户批准用封存的 stderr、版本和环境结果重新判定 17,432 个原候选，并保留新增样本与还原的实测要求。 [授权记录](artifacts/cp4_1_v1/authorization.json)

2026-11-22 美东 08:31 和 08:34，WSL 启动新命令两次超时。内核在相应时刻无法为 Hyper-V 通道取得 512 KiB 连续物理内存。该检查发生在 CP4.1 新编译调用之前。92 个受支持版本的测量、正式的模板类型映射、候选重判、补充样本、图评分及回归测试均待完成。 [故障证据](artifacts/cp4_1_v1/wsl_startup_diagnosis.json)

### CP4.1 生产测量、适用边界与两处迁移差异

修改 AI 为 Codex。基线为 e8ec530d，生产使用 92 个 0.4.12–0.8.38 编译器。所有新结果、逐次命令索引及原始分数见 [本批说明](artifacts/cp4_1_v1/README.md)。

| §4.6b 验收项 | 实测 |
|---|---|
| 旧 other 诊断逐模板归因 | 96 个模板中，92 个有同型且同类型的 standard JSON 证据，1 个有跨版本的版本拒绝证据，1 个由同类结构体成员的类型支持，1 个使用获批的历史异常文本。剩余 1 个保留 other。95 份手写源码共调用 standard JSON 642 次。 |
| CP3 全量重算及 D6 | 31,307 个输入中 31,071 个有历史观测，236 个未测。主因 other 从 36 降到 0，任一候选含 other 的单元从 202 降到 2，原始 other 诊断从 13,321 降到 128 次。补充三类的 D6 路线及优先序见 d6_routes.json。 |
| 编码与结构体数组 | 字符串内部插入非法字节，859 个新候选纳入 511 项。结构体数组算子在 92 版生产字节码路径上均被拒绝。0.8.28–0.8.38 的 11 版报告只支持 IR 流水线。审查夹具在相同 0.8.38 下仅输出 ABI 时成功，输出生产字节码时失败。按获批口径抽样 949 项，两阶段确认后纳入 761 项。 |
| 原算子 | 17,432 个旧候选均校验原种子、编辑字节及收据 SHA，11,858 项继续纳入，另增结构不平衡 950 项、类型错误 2 项。declaration_error 算子仍为 0，手写同名函数在所测五版均为 SyntaxError。CP3 的 declaration_error 主因有 2 项。 |
| 实际包缺失 | DAppSCAN 适用及纳入各 112，Trace_repo 各 2，其他四组各 0。DAppSCAN 有 openzeppelin-solidity 79、@openzeppelin/contracts 17、@openzeppelin/contracts-upgradeable 12、@openzeppelin/contracts-ethereum-package 4。Trace_repo 的 2 项均为 @openzeppelin/contracts。 |
| 创建码尾部 | 16,136 个基础单元中 33 个含创建码常量、2 个含运行时代码常量。30 个单元有通过校验的元数据尾部。cp3_23979 在不同路径使用相同源码实编，保留节点由 298/299 变为 299/299。手写项目仅改变子合约注释，由 5/6 变为 6/6。 |
| 对照和精确还原 | 200 个旧对照按计划、结果与外部封存 SHA 核对。原 11,858 个已纳入样本重新评分全部满分。新增的原候选 952 个逐一实编并通过 D3 和精确还原。 |
| 新样本与迁移 | 1,922 个新候选中 1,386 项触发，364 项未触发，172 项由环境步骤解决。两批共 114 个缺包样本触发。首轮有 1,274 项完成全部评分，随后 cp3_15167 与补批 cp3_15136 分别因迁移后的 IR 编号差异停止。完整迁移验收待决。 |
| 测试与范围 | 最后一次生产环境 1,016 通过、6 跳过。mando 553 通过、469 跳过。DFG v2 为 2,653 通过、9 条告警。生产文件保持 17 个，354 项冻结 DFG 代码身份一致。 |

CP3 主因的其他变化包括 parser_error_other 257→267、version_dependent 221→219、unbalanced_structure 55→64、type_error_other 6→11、file_level_member 0→9、declaration_error 0→2、syntax_error 0→1。abi_coder_required 在任一候选中出现于 5 个单元。35 行主因、34 行任一候选及完整旧 other 模板频数在 [归因对照](artifacts/cp4_1_v1/cp3_before_after.json)。证据未能定类的模板在 [诊断映射](artifacts/cp4_1_v1/diagnostic_mapping.json)。

合计 19,354 个候选，其中 14,196 个达到触发条件。各算子的原始、重判、新增数量在 [算子全表](artifacts/cp4_1_v1/operators.tsv)，语料及编译器小版本数据在 [分层表](artifacts/cp4_1_v1/strata.tsv)。该计数用于构造基准，实际修复效果由后续阶段测量。

迁移的两个项目均通过原始字节的精确还原。cp3_15167 在迁移后保留节点 16/18 相等，cp3_15136 为 2/4。两者的保留 CFG 边分别为 14/14、3/3。对已保存的全图逐字核对后发现，前者 34 个节点中有 5 个涉及 Slither 生成的临时编号，后者 82 个中有 19 个。工具按编译单元分配 TMP 和 REF 编号。双向唯一的编号对应可以解释两个实例的全部 IR 差异，两个项目的全部 11 与 34 个调用也分别吻合。该观察单列为诊断。原分及是否通过仍遵循此次运行时的判据。

本次 3 个生产文件的增删行按 Git 统计为 benchmark.py +346/−26、report.py +7/−2、solc.py +80/−3。逐函数增删见 [范围核验](artifacts/cp4_1_v1/migration_stop_scope.json)。详细任务选择与用户授权见 CHANGE_LOG §44。


### CP4.1 最终验收与图迁移复核（2026-11-22，修改 AI 为 Codex）

19,354 个候选中有 14,196 个符合两阶段触发条件，全部通过生产 solc、D3 和原位置精确还原评分。按编辑和样本身份去重核对后，构成为原纳入 11,858 项、原候选新纳入 952 项、新算子首批 1,300 项、补批 86 项。200 个对照与原封存一致。114 个真实缺包样本还完成了文件位置迁移，含 DAppSCAN 112 个、Trace_repo 2 个，开发集 8 个、测试集 106 个。[全量验收](artifacts/cp4_1_v1/migration_continuation/acceptance.json) · [逐项迁移表](artifacts/cp4_1_v1/migration_continuation/packages.tsv)

| 验收对象 | 结果 |
|---|---|
| 原位置精确还原 | 14,196/14,196。保留节点、CFG 边和调用的匹配率均为 1，最终丢失、缺失保留节点和新增节点均为 0。28 份评分使用已认可的字节码元数据比较。 |
| 真实包迁移 | 53/114 按原分即可匹配。其余 61 项通过完整图上的生成名称核验，共 114/114。61 项涉及 TMP、32 项涉及 REF、2 项涉及 TUPLE，各类可重叠。原分逐项保留。 |
| 两个旧停点及元组 | `cp3_15136` 和 `cp3_15167` 复现停点原分后通过。 `cp3_03927` 的单个元组定义及两处解包使用同一换号映射，索引仍依次为 0、1。该图的 167 个节点、137 条边、81 个调用全部核对。 |
| Yul 源文件编号 | `cp3_00706` 的同一段 164 字节源码在 solc AST 中分别为 `1628:164:2`、`1628:164:3`。两次原命令结果逐字匹配旧 stdout 哈希，两个编号经各自源文件清单指向同一迁移文件。189 个节点、150 条边、102 个调用全部核对。授权上限 4 次，实用 2 次。 |
| 数组分配定义 | `cp3_15161` 的两个 TMP 定义由 Slither 的 NewArray 打印器输出，赋值符前有两个空格。按实际格式识别左值后，733 个节点、632 条边、355 个调用全部核对。 |
| 生产文件与回归 | CP4.1 对基线 `e8ec530d` 改动 3 个生产文件，分别为 benchmark.py +657/−27、report.py +7/−2、solc.py +80/−3。此次续作只修改 benchmark.py 和既有 test_cp41.py 的代码。生产文件总数为 17，原有 354 项 DFG 代码身份均匹配。最终 production 1,068 通过、6 跳过，mando 605 通过、469 跳过，DFG v2 为 2,653 通过、9 条告警。 |

完整方法、授权、逐函数行数和可重查的收据分别见本批说明与范围核验。评分程序在源文件改名时检查节点位置、指令、声明、所有边和调用端点，也核对源码标识符及解码字面量。缺完整收据或无法解释的差异仍会拒绝该次图对应。这里测量的是已知逆向编辑对图事实的还原能力。未知输入的自动修复率留待后续阶段测量。[批次说明](artifacts/cp4_1_v1/migration_continuation/README.md) · [代码范围与逐函数行数](artifacts/cp4_1_v1/migration_continuation/final_scope.json)
