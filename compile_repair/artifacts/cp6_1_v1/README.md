# CP6.1 证据：第 5 步规范化（修改 AI：Claude，2026-11-24）

规格见 PROMPTS r2.29 §4.6l，记录见 docs/CHANGE_LOG.md §66。本目录只放脚本与云端摘要；运行目录在云端临时空间，本机复核的输出写到仓库外 compile-repair-local/cp6_1_v1/。

## 实现

- `rules/normalize.py`（新文件，非测试文件 19 个，仍在 3.10 节上限内；分层 rules ← toolchain/core 不变）：五条规则。
  - identical_duplicates：被报 duplicate_definition 的声明，只有同一作用域中存在逐字节相同的同类同名声明时，把后面的副本换成空格（保留换行，偏移与行号不变），等级 rewrite。
  - duplicate_licenses：文件中所有 SPDX 标识相同时，删去后面的重复注释；标识不同时不处理（different_licenses）。
  - duplicate_pragmas：非 solidity 的 pragma 逐字节重复时删去后面的副本；abicoder 取值冲突时不选择（conflicting_abicoder）。
  - pragma_terminators：`pragma solidity <版本>` 后直接遇到指令或声明关键字，或者到达文件末尾时，补一个分号，等级 additive。
  - abi_coder_pragma：报 abi_coder_required 且文件没有选择 ABI 编码器时，在 solidity pragma 后加 `pragma experimental ABIEncoderV2;`（文档写法），等级 additive。
- `pipeline.py`：第 5 步在第 2–4 步之后运行，输入为当前最佳记录的诊断（多个候选版本报告的同一诊断只保留一次，记录 versions）；不修改第 3 步加入的依赖发布版；接受规则与 3.1 节相同；修复资格增加五个规范化类别。
- 测试：`tests/test_cp61.py` 20 项；CP2.4 的两项测试与 CP1.1 的文件数检查随新行为更新（见 CHANGE_LOG §66.2）。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,183 passed / 6 skipped（CP6.0.1 为 1,163 / 6；test_cp61.py 新增 20 项），production_tests_cloud.json |
| MANDO 回归（cp6_0_v1/mando_check.py） | passed=true：843 个图与 v5 逐字节相同，d3_c 843，历史失败 3，steps_on_truths 0（mando_check_cloud.json；在加入文件末尾分号规则之前运行，MANDO 单元不会进入第 5 步） |
| 破坏-修复小基准（mini_benchmark.py，每个算子 15 个 DAppSCAN 单文件基） | 45/45 修复成功；字节还原：未终止 pragma 15/15、缺分号 15/15、重复定义 0/15（重复副本被换成空格，按设计不还原）；严格 exact 39/45；屏蔽元数据哈希后 exact 45/45 |
| 真实单元（real_check.py，select_targets.py 选出的 42 个：DAppSCAN 24、SOChecker 18） | 11 个成功，全部由第 5 步接受；语料文件不变。按来源计：2 个 DAppSCAN 项目、2 个 SOChecker 片段（real_check_cloud.json、targets_cloud.json） |

## 真实单元的结果（按来源计数）

| 结果 | 单元 | 来源 | 说明 |
|---|---|---|---|
| 成功：重复 SPDX | 8 | 1 个项目（Coinfabrik-MintingFactoryV2…） | 展平文件中逐字相同的 SPDX 行 |
| 成功：逐字节相同的重复声明 | 2 | consensys-Zer0_zNS、片段 cp3_30104 | 同一接口被粘贴两次 |
| 成功：文件末尾缺分号 | 1 | 片段 cp3_29802 | 片段只有一行 pragma，图为空 |
| 未修复：ABI 编码器已补，下一个阻碍是 Stack too deep | 4 | Trail_of_Bits-FraxQ42021 | 错误数 1 → 1，不接受；属于第 9 步（CP6.3），届时考虑“错误进入更后的编译阶段”也算进展 |
| 未修复：同名但内容不同 | 18 | 4 个项目 + 14 个片段 | 不是规范化可以决定的，留给后续步骤或代理 |
| 未修复：重名但不是同类声明 | 9 | 6 个项目 + 2 个片段 | 例如常量变量与继承来的同名函数（Compound 系 certora 模型，多个审计项目共用）、文件级的非常量变量；不能删 |

严格 exact 的 6 个例外来自两个工厂合约（Mdex、WaultSwap）。差异只在 `type(X).creationCode` 内嵌子合约元数据的 bzzr1 哈希：真值运行的源单元名是绝对路径，修复运行是项目内的 `input.sol`，哈希随之不同。已有的 normalized_node_ir 只处理末尾的元数据，对 0.5 的 `type(address)(X)` 写法也不触发。这是评测设置造成的差异，不是修复错误；没有修改 CP4 的评分器，脚本同时报告严格值与屏蔽哈希后的值。

## 脚本

- `mini_benchmark.py <bases.jsonl.gz> <DAppSCAN-source> <每个算子样本数> <输出目录> <summary.json>`：真值是本流水线对原文件的图；修复后的单文件以单文件项目（文件名 input.sol）编译，评分前用 benchmark 的 `_single_file_wrapper_graph` 转回单文件身份。
- `select_targets.py <targets.json> [旧前缀=新前缀 ...] [单元号 ...]`：从已提交的 CP3 清单与归因中选出未修复、主因或候选类别含第 5 步类别的单元；逐个校验入口 SHA-256。四个 Frax 单元（cp3_16451/16472/16473/16474）在当前分类器下才出现 abi_coder_required，按单元号加入。
- `real_check.py <targets.json> <输出目录> <summary.json>`：有项目根的单元按项目修复，片段与单文件不搜索其他文件；核对语料文件运行前后不变。

## r2.30 修正（修改 AI：Claude）

Codex 本地运行到第 27 个基时中止：cp3_00111 与 cp3_00290 是同一个文件，运行器按内容哈希命名目录。现在每个不同内容只取一次，跳过的相同内容记入 repeated_contents_skipped。云端每个算子 30 个复验（mini_benchmark_cloud_r2.json）：90/90 修复成功；字节还原：两个分号算子 30/30；严格 exact 84/90，屏蔽元数据哈希后 90/90；跳过 15 个相同内容。严格例外仍只来自 Mdex、WaultSwap 两个工厂合约。
