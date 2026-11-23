### 开发选版与每单元组合上限

固定规则为 `oldest`，每个单元最多实际编译 21 个依赖版本组合。以三个规则在真实开发集上的 D3 成功数为首要指标，缺包开发样本的编译、主 kept 和库文件字节用于次级比较。K 取所选规则下全部成功开发单元实际编译的最大组合数，覆盖其检查过的每个位置。

| 规则 | 真实开发集 D3 | 实际编译组合总数 | 基准成功 / 8 | 主 kept | 相同库文件 |
| --- | --- | --- | --- | --- | --- |
| closest | 1130/2316 | 1617 | 7 | 213/232 | 1/23 |
| latest | 1130/2316 | 1460 | 7 | 213/232 | 1/23 |
| oldest | 1131/2316 | 1323 | 7 | 213/232 | 2/23 |

各单元的首个成功位置、实际尝试清单、耗时及分布见 `real_dev.jsonl` 与 `policy.json`。

下表统计第 3 步记录了耗时、实际编译组合数为 0 的开发运行。时间包含依赖筛选、组装及收据写入。K 只限制实际编译次数。

| 规则 | 运行数 | 第 3 步累计秒数 | 最长单次秒数 |
| --- | --- | --- | --- |
| closest | 1105 | 356.51 | 150.83 |
| latest | 1105 | 355.1 | 149.51 |
| oldest | 1105 | 360.78 | 153.93 |

### 冻结规则后的损坏基准

下表采用汇总分子和分母。CFG 边和调用的分母是保留事实的并集。逐单元均值、改动等级、逐样本分数见 `benchmark_summary.json` 与 `benchmark.jsonl`。

| 划分 | 算子 | 单元 | 编译及 D3 | 主 kept | 存活 kept | 主 CFG | 存活 CFG | 主调用 | 存活调用 | 修复删除 | exact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev | closure_version_conflict | 78 | 0 | 0/23951 | 0/23951 | 0/19752 | 0/19752 | 0/10379 | 0/10379 | 0 | 0/78 (0.0%) |
| dev | io_error | 91 | 0 | 0/29392 | 0/29392 | 0/24166 | 0/24166 | 0/12911 | 0/12911 | 0 | 0/91 (0.0%) |
| dev | missing_relative_file | 90 | 0 | 0/19177 | 0/19177 | 0/15946 | 0/15946 | 0/8429 | 0/7754 | 0 | 0/90 (0.0%) |
| dev | missing_relative_file_moved | 94 | 40 | 12042/24476 | 12042/24476 | 9568/19856 | 9568/19856 | 5194/10676 | 5194/10676 | 0 | 0/94 (0.0%) |
| dev | unresolved_package_import | 8 | 7 | 213/232 | 213/232 | 161/174 | 161/174 | 123/137 | 84/92 | 0 | 0/8 (0.0%) |
| test | closure_version_conflict | 322 | 0 | 0/69743 | 0/69743 | 0/60339 | 0/60339 | 0/28567 | 0/28567 | 0 | 0/322 (0.0%) |
| test | io_error | 309 | 0 | 0/66886 | 0/66886 | 0/57532 | 0/57532 | 0/27298 | 0/27298 | 0 | 0/309 (0.0%) |
| test | missing_relative_file | 310 | 0 | 0/60885 | 0/60885 | 0/51255 | 0/51255 | 0/26503 | 0/25149 | 0 | 0/310 (0.0%) |
| test | missing_relative_file_moved | 306 | 149 | 24137/77682 | 24137/77682 | 20800/67253 | 20800/67253 | 9276/33347 | 9276/33347 | 0 | 1/306 (0.3%) |
| test | unresolved_package_import | 106 | 94 | 3929/5836 | 3929/5836 | 4451/4853 | 4451/4853 | 1832/3650 | 1394/3097 | 0 | 2/106 (1.9%) |

standard JSON 包装的统计如下。

| 划分 | 单元 | 编译及 D3 | 恢复节点 | lost | added | exact |
| --- | --- | --- | --- | --- | --- | --- |
| dev | 189 | 189 | 18272 | 0 | 0 | 77/189 (40.7%) |
| test | 761 | 761 | 71202 | 0 | 0 | 323/761 (42.4%) |

| 划分 | 算子 | 名称状态 | 改动等级 |
| --- | --- | --- | --- |
| dev | closure_version_conflict | rejected 78 | none 78 |
| dev | io_error | rejected 91 | none 91 |
| dev | missing_relative_file | rejected 90 | none 90 |
| dev | missing_relative_file_moved | identical 27、rejected 54、verified 13 | none 48、rewrite 46 |
| dev | standard_json_input | identical 189 | none 189 |
| dev | unresolved_package_import | identical 2、rejected 1、verified 5 | additive 8 |
| test | closure_version_conflict | rejected 322 | none 322 |
| test | io_error | rejected 309 | none 309 |
| test | missing_relative_file | rejected 310 | none 310 |
| test | missing_relative_file_moved | identical 107、rejected 158、verified 41 | none 146、rewrite 160 |
| test | standard_json_input | identical 761 | none 761 |
| test | unresolved_package_import | identical 34、rejected 28、verified 44 | additive 95、none 11 |

| 缺包划分 | 字节相同文件 | 原库文件 | 比例 |
| --- | --- | --- | --- |
| dev | 2 | 23 | 0.087 |
| test | 66 | 398 | 0.1658 |

第 2–4 步利用项目内文件、离线发布版和可验证的导入路径。这三个步骤通常保留删除源文件、无效 I/O 路径和修改 pragma 所致的失败。三个对照算子共有 0 个成功样本。原改动和逐条路径依据见 `benchmark_summary.json` 的 `negative_control_successes`。

本轮三个对照算子中，因项目内已有同名文件而成功的样本为 0 个。

### 真实语料与锁版本参照

9,138 个原主因目标中有 5880 个通过生产 D3，14 个触发实际编译组合上限。下表按最后接纳步骤和本次使用的最低身份等级统计。

| 语料 | 最后步骤 | 身份 | 单元 | D3 | 截断 |
| --- | --- | --- | --- | --- | --- |
| DAppSCAN | 1 | no_release | 2109 | 0 | 8 |
| DAppSCAN | 2 | T3 | 20 | 10 | 0 |
| DAppSCAN | 2 | no_release | 612 | 569 | 0 |
| DAppSCAN | 3 | T1 | 73 | 73 | 0 |
| DAppSCAN | 3 | T3 | 4791 | 4161 | 6 |
| DAppSCAN | 4 | T3 | 12 | 4 | 0 |
| DAppSCAN | 4 | no_release | 77 | 23 | 0 |
| SOChecker | 1 | no_release | 14 | 0 | 0 |
| SOChecker | 3 | T3 | 19 | 17 | 0 |
| Trace_on_chain | 1 | no_release | 40 | 0 | 0 |
| Trace_on_chain | 2 | no_release | 369 | 369 | 0 |
| Trace_on_chain | 4 | no_release | 1 | 1 | 0 |
| Trace_repo | 1 | no_release | 293 | 0 | 0 |
| Trace_repo | 2 | no_release | 7 | 5 | 0 |
| Trace_repo | 3 | T3 | 701 | 648 | 0 |

73 个 T1 单元来自同一测试项目。三种规则都在隐藏版本和清单范围后运行，参照分母包括未修复的单元。

| 规则 | 参照数 | D3 | 同锁版本 | 同版本或闭包文件字节相同 | 截断 |
| --- | --- | --- | --- | --- | --- |
| closest | 73 | 73 | 8 | 10 | 0 |
| latest | 73 | 73 | 8 | 10 | 0 |
| oldest | 73 | 73 | 70 | 73 | 0 |

另按成功单元实际接受的步骤计数。一次修复可先后采用多个步骤，所以下表各行不能相加作为成功总数。

| 语料 | 接受的步骤 | 最终通过 D3 的单元 |
| --- | --- | --- |
| DAppSCAN | 2 | 652 |
| DAppSCAN | 3 | 4248 |
| DAppSCAN | 4 | 30 |
| SOChecker | 3 | 17 |
| Trace_on_chain | 2 | 369 |
| Trace_on_chain | 4 | 1 |
| Trace_repo | 2 | 7 |
| Trace_repo | 3 | 648 |

按 CP3.1 对同一批 31,307 个输入重新统计，可计量分母由 31048 至 31048。修复前有 9825 个失败单元，修复后有 3945 个。一个单元可有多个主因。语言排除项和未测单元分开留存在 `external_summary.json`。

| 剩余主因 | 修复前 | 修复后 |
| --- | --- | --- |
| abi_coder_required | 0 | 0 |
| closure_version_conflict | 4 | 4 |
| codegen_only | 39 | 62 |
| compiler_exception | 0 | 0 |
| declaration_error | 2 | 2 |
| docstring_error | 0 | 0 |
| duplicate_definition | 19 | 24 |
| encoding | 0 | 0 |
| fatal_error | 0 | 0 |
| file_level_member | 9 | 9 |
| internal_compiler_error | 0 | 0 |
| io_error | 28 | 28 |
| json_error | 0 | 0 |
| missing_base_contract | 2 | 2 |
| missing_relative_file | 412 | 357 |
| multiple_license_or_pragma | 8 | 8 |
| non_solidity_input | 0 | 0 |
| other | 0 | 1 |
| parser_error_other | 267 | 268 |
| pragma_missing_semicolon_candidate | 0 | 0 |
| slither_incomplete | 24 | 24 |
| slither_no_timeout | 0 | 0 |
| standard_json_input | 410 | 40 |
| syntax_error | 1 | 1 |
| type_error_other | 11 | 49 |
| unbalanced_structure | 64 | 64 |
| undeclared_identifier | 25 | 40 |
| unimplemented_feature | 0 | 0 |
| unresolved_package_import | 8454 | 2804 |
| unsupported_disjunction | 1 | 1 |
| unsupported_expression | 4 | 4 |
| unterminated_pragma | 1 | 1 |
| version_dependent | 219 | 219 |
| version_mismatch | 0 | 0 |
| warning | 0 | 0 |
