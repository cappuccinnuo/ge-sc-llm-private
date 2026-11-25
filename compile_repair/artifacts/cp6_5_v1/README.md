# CP6.5 证据：CP6 补全（修改 AI：Claude，2026-11-25）

规格见 PROMPTS r2.35 §4.6p，记录见 docs/CHANGE_LOG.md §82。全部在云端完成；没有需要本机大数据的步骤。

## 为什么有 CP6.5

用户要求逐项核对 CP6 是否完成。按 D6 表（artifacts/cp3_2_v1/d6_cp4_final.json）逐类别对照，CP6.4 的总结漏了以下几类：

| D6 类别 | D6 路由 | CP6.4 时的状态 | CP6.5 |
|---|---|---|---|
| version_dependent、syntax_error | 有版本文档、含义唯一时迁移 | 未实现 | 第 5 步文档迁移 |
| docstring_error | 第 5 步 | 未实现 | NatSpec `@param` 行置空 |
| unsupported_disjunction | 并集求值、去重升序尝试 | 未实现 | 第 1 步并集选版 |
| slither_incomplete（元组调用） | 第 10 步 | 3.2 节第 10 行的原例未实现 | 第 10 步元组调用 |
| undeclared_identifier（结构体） | 第 7 步 | 结构体没有桩 | 具名构造推出字段的结构体桩 |
| other、io_error、closure_version_conflict | 先诊断 | 没有逐项诊断 | 见下文“诊断” |

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,298 passed / 6 skipped（production_tests_cloud.json；CP6.4 为 1,236 / 6，test_cp65.py 63 项，删去 1 个 `||` 参数） |
| MANDO 回归 | passed=true：843 个图与 v5 逐字节相同、steps_on_truths 0；v5 的 3 个历史失败（input_0550/0551/0553，Slither 在元组调用上断言）现在只经第 10 步成功，仍用 0.4.24，D3(c) 为 true（mando_check_cloud.json，脚本 mando_check.py） |
| 真实单元（D6 中 CP6.5 涉及的类别，319 个单元、280 个来源） | CP6.4 代码 65 个成功（46 个来源）→ CP6.5 67 个（48 个来源）；无退步，已成功单元的版本都不变；corpus_unchanged true（real_base_cloud.json、real_final_cloud.json 与逐单元 rows） |

第 5 步迁移在 0.5.0、0.5.17、0.6.12、0.7.6、0.8.38 上逐个版本由测试验证（每类迁移一个输入）。真实单元中迁移被接受 3 次，只多出 1 个成功：这些单元大多是 SOChecker 的问答片段（241 个），迁移之后的阻塞是没有导入的 ERC20、Ownable 等合约和不完整的代码，需要上下文，属于代理阶段。剩余的 version_dependent 141 个单元的首个错误：未声明标识符、片段结构（Expected pragma, import directive …）、Identifier not found；没有一个是迁移模板的消息。

## 诊断（不加规则）

| 类别 | 单元 / 来源 | 结论 | D6 回退 |
|---|---|---|---|
| other | 36 / 34 | 当前分类器已全部归入已有类别：CP6.5 下 7 个成功，其余为 parser_error_other 10、undeclared_identifier 6、type_error_other 5、unbalanced_structure 5、declaration_error 2、duplicate_definition 1 | 按所归类别 |
| io_error | 28 / 20 | 导入越出项目根且文件不在语料中（相对路径 61 条；DAppSCAN 只收录被审计的文件），或是 https://github.com/… URL（24 条、2 个项目）。没有可证明的目标 | agent_if_dependency_unknown |
| closure_version_conflict | 5 / 3 | Aave V3 的 Certora 测试夹具仍写 `0.6.12`，而它导入的全部文件是 `0.8.7`（3 个单元、1 个项目）；2 个问答片段在同一文件里有两个不相容 pragma | agent_if_original_version_unknown（D6 不允许跨小版本覆盖） |

## 开发中的核实

- 冻结 pragma 读取（CP2 起的等价测试与 MANDO 回归依赖它）一度被改为接受 `||`，导致 9 个测试失败；改为保持冻结读取不变，读取失败后由单独规则处理。
- 第 10 步改写后的行在 0.4.12 也合法，第一次实现时 MANDO 的 3 个单元改在 0.4.12 编译；改为试验先用 solc 已通过的版本（测试 test_tuple_rewrite_keeps_the_version_solc_accepted）。
- solc 一个阶段只报第一个 payable 错误，所以一次提出全部可证明的位置；构造函数与 fallback 的重叠、selfdestruct 的接收方各补了模板与测试。
- 迁移规则并入 rules/normalize.py，非测试文件仍为 20 个。

## 脚本与数据

- `mando_check.py <mando_v5> <out> <summary> --repo-root <checkout>`：在 cp6_0_v1 的检查上把 3 个历史失败改为“必须只经第 10 步成功、版本 0.4.24、D3(c)”。
- 真实单元用 `artifacts/cp6_4_v1/real_check.py`；目标清单 real_targets_cloud.json.gz（路径中的 `<scratch>` 为云端语料副本的根）。

## CP6 总结（替代 cp6_4_v1/README.md 中的总结）

| 子阶段 | 步骤 | 规则 |
|---|---|---|
| CP6.0 | D3(c) | Slither 部分 IR 不算成功 |
| CP6.1 | 第 5 步 | 逐字节相同的重复、SPDX 与 pragma、pragma 分号、ABI 编码器 |
| CP6.2 | 第 8 步、D27 | 补右花括号、片段包装；编译阶段前进算进展 |
| CP6.3 | 第 7 步 | 基类、修饰器、事件、接口声明桩 |
| CP6.4 | 第 9、10 步、D26 | AST-only 编译、导入别名、深递归、版本前缀 |
| CP6.5 | 第 1、5、7、10 步 | `||` 并集选版、文档迁移与 NatSpec、结构体桩、元组调用 |

CP6 之后仍不能确定性处理、留给代理阶段的：普通变量与普通调用的未声明、片段中没有导入的库合约、内容不同的重名、括号结构有歧义的残缺代码、非 Solidity 内容、不在语料中的导入目标、不相容的 pragma、throw/var/callcode、三元表达式的 SlithIR 限制。
