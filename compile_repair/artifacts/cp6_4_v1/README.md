# CP6.4 证据与 CP6 总结（修改 AI：Claude，2026-11-25）

规格见 PROMPTS r2.33 §4.6o，记录见 docs/CHANGE_LOG.md §77。本目录放脚本与云端摘要；本机只运行 mando 环境测试与 D26 全量（PROMPTS §4.6o 的本地步骤）。

## 先测量

CP3 中仍失败、主因或候选类别含 codegen_only 或 slither_incomplete 的单元（另加 4 个 Frax 单元）共 64 个；CP6.3 的流水线下 0 个成功（codegen_slither_baseline_cloud.json）。按不同来源：只在代码生成阶段失败约 9 个项目（几乎都是 0.6/0.7 的 ABI 编码器生成的汇编中 Stack too deep，这些版本没有 via-IR），Slither 侧失败 4 个项目（递归深度 1、导入别名 2、三元表达式 1）。D26 的前缀 openzeppelin-solidity-2.3.0 在 CP5 目标中有 1,539 个单元、9 个项目。

## 实现

- 第 9 步：toolchain/solc.py `compile_ast_only`（standard JSON 只请求 AST 与 ABI）、toolchain/slither.py 的 AST-only 平台、rules/environment.py `codegen_only_retry`、core/model.py `Compilation.output`；pipeline 在同一版本上重试一次。
- 第 10 步：rules/normalize.py `import_alias_rewrites`（导入别名）；toolchain/slither.py `run_slither` 遇 RecursionError 在大栈线程中重做一次。
- D26：rules/dependencies.py `dependency_choices` 中的版本前缀身份。
- pipeline：修复试验沿用环境阶段已需要的 pragma 覆盖，覆盖记在已有改动之后。
- 非测试文件仍为 20 个；测试 tests/test_cp64.py 21 项。

开发中的核实：
- 命令行 combined JSON（0.7.0）即使只请求 ast 也做代码生成；standard JSON 在不请求字节码时从 0.5.2 起跳过代码生成（0.4.24、0.4.26、0.5.0、0.5.1 仍报错）。
- 正常编译与 AST-only 编译的图与节点在 0.5.17、0.6.12、0.7.6、0.8.38 上逐项相同（测试 test_ast_only_graph_equals_the_normal_graph）。
- 起初把门槛放宽到所有 Slither 侧失败，会让无关单元进入修复步骤；改为只在失败属于第 10 步有规则的类别时进入。
- 0x v1 的两个别名单元：改写已生成，但试验不允许 pragma 覆盖而无编译器可用；改为沿用环境阶段的覆盖后成功。第一次实现时覆盖丢掉了已有改动的记录（Working copy/provenance mismatch），改为把覆盖记在已有改动之后，并加测试。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,236 passed / 6 skipped（production_tests_cloud.json） |
| MANDO 回归 | passed=true：843 个图与 v5 逐字节相同，历史失败 3，steps_on_truths 0（mando_check_cloud.json，最终代码） |
| codegen / Slither 侧 64 个单元 | 63 个成功（CP6.3 下 0 个）：AST-only 43 个（9 个来源）、深递归重做 4 个（1 个来源）、别名改写 16 个（2 个来源）；剩 1 个三元表达式（工具限制）（codegen_slither_check_cloud.json） |
| D26（只含 openzeppelin-solidity@2.3.0 的小索引，9 个项目中直接导入该前缀的 23 个单元） | 第 3 步全部接受；20 个成功；发布版 T1、inferred=false，20 个带 D26_versioned_prefix 证据，3 个由锁文件钉住；其余 3 个还缺别的包或相对文件（d26_check_cloud.json） |
| CP6 全部规则下 550 个真实单元（CP6.3 目标集） | 49 个成功（49 个不同来源），与 CP6.3 逐单元相同，没有退步（CP6.4 的规则面向代码生成、Slither 侧与依赖类别，不在这个目标集中）；语料不变 |

## CP6 总结

| 子阶段 | 步骤 | 规则 | 云端或本机的主要结果 |
|---|---|---|---|
| CP6.0 | D3(c) | Slither 部分 IR 不算成功 | 4 个部分 IR 单元归为 slither_incomplete |
| CP6.1 | 第 5 步 | 逐字节相同的重复声明、重复 SPDX 与 pragma、pragma 分号、ABI 编码器 | 本机基准 300/300；真实 11/42 |
| CP6.2 | 第 8 步、D27 | 补右花括号、片段包装；编译阶段前进算进展 | 本机基准 68/68 严格 exact、32/32 正确拒绝；真实 40/522 |
| CP6.3 | 第 7 步 | 基类、修饰器、事件、接口声明桩 | 本机基准：事件 52/100、基类 17/100；真实 49/550 |
| CP6.4 | 第 9、10 步、D26 | AST-only 编译、导入别名、深递归、版本前缀 | 上表 |

CP6 之后仍不能确定性处理的：普通变量与普通调用的未声明（用法给不出类型）、内容不同的重名、括号结构有歧义的残缺代码、非 Solidity 内容、三元表达式的 SlithIR 限制。这些留给代理阶段（PROMPTS 中 CP6 之后的阶段）。

## 脚本

- `real_check.py`：同 cp6_3_v1，另记第 10 步、AST-only 与第 3 步；设置 COMPILE_REPAIR_DEPENDENCY_INDEX 时使用离线依赖索引。
- `select_targets.py`：同 cp6_3_v1。
- `select_d26_targets.py <索引目录> <targets.json>`：从 CP5.2 的续跑记录与本机 result.json 中选出未解决导入带 `name-X.Y.Z` 前缀、且索引中有 name@X.Y.Z 的单元（本机运行）。
