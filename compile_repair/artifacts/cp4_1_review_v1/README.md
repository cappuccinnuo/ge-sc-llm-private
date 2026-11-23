# cp4_1_review_v1：CP4.1 审查证据（Claude，2026-11-22）

审查对象：`compile-repair@6950dc7b8`（Codex 的 CP4.1：`toolchain/solc.py`、`evaluation/benchmark.py`、`evaluation/report.py` 的差异，`tests/test_cp41.py`，产物 `cp4_1_v1/`，CP4_REPORT 的 CP4.1 节、四份记录与 CHANGE_LOG §43–§45）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12，Slither 0.11.6 + crytic-compile 0.4.2；solc 为 GitHub 发布的静态构建（本目录用 0.4.24、0.5.17、0.8.0、0.8.38）。

## 文件

| 文件 | 内容 |
|---|---|
| `probe_operator_messages_cp41.json` | CP4 审查的 8 个夹具（`../cp4_review_v1/fixtures/`）在 4 个版本上用 CP4.1 的分类器重新分类 |
| `struct_copy_bin.json` | 结构体数组复制夹具在 0.8.0、0.8.38 上只输出 abi 与输出 bin 的结果 |
| `probe_counter_shift.py` / `.json` | 用模块自己的 `graph_facts` 与 `score_graphs` 比较两种语义相同的修复：原位置恢复被删函数、把同一函数插到合约开头 |

## 结论

1. **成立的部分**
   - 计数一致：候选 19,354 = 17,432 + 1,922；纳入 14,196 = 11,858 + 952（重判升级）+ 1,386（新算子，其中 1,300 + 86 补样）；新算子纳入 114 + 511 + 761 = 1,386；精确还原 14,196/14,196，对照 200/200。
   - 分类器：8 个夹具重新分类后，删除右花括号在 4 个版本上都归为 unbalanced_structure，嵌套动态数组参数在 0.4.24、0.5.17 归为 abi_coder_required，同名函数在 0.5.17 以后归为 syntax_error（standard JSON 给出的类型就是 SyntaxError，见 `cp4_1_v1/same_name_types.json`）。CP3 主因表中 other 由 36 降到 0，模板逐条有归属。
   - 结构体数组复制：Codex 的结论正确，审查 CP4 时的说法有误。审查当时只用 `--combined-json abi`，0.8.38 返回 0；生产路径要求字节码，0.8.38 输出 bin 时报 `Copying of type struct A.S memory[] memory to storage is not supported in legacy (only supported by the IR pipeline).`（`struct_copy_bin.json`）。
   - declaration_error 0 纳入：同名函数实际是 SyntaxError，不是 DeclarationError；该类别在 CP3 主因中只有 2 个单元。接受为已知限制，D6 中注明没有基准样本。
   - 缺包依赖：114 个真实样本（DAppSCAN 112、Trace_repo 2），没有改用合成包名；迁移还原 114/114（53 个原样相同，61 个经生成名称对应核验）。核验很严：要求逐条 IR 的非计数部分相同、计数名一一对应且定义在对齐节点中、源码中没有同名词与字面量、源字节只在导入路径上不同。
   - 创建码规范化：含元数据的精确还原评分 28 个，规范化只作用于比较。
   - 测试：审查环境运行 `test_cp41.py` 与 `test_benchmark.py`，272 项通过。
2. **未解决的问题：生成名称对应只用于迁移，普通修复的评分会误报**（`probe_counter_shift.json`）。
   - Slither 的 TMP/REF/TUPLE 编号按处理顺序累加，在同一合约或同一编译单元中位于前面的代码改变后，后面所有未改动节点的编号都会变化。
   - 实测：原合约中 `h()` 在 `g()` 之后，破坏为删除 `h()`。原位置恢复时 kept 比例为 1；把完全相同的 `h()` 插到合约开头时，`g()` 的 IR 从 `TMP_0…TMP_2、REF_0、REF_1` 变成 `TMP_4…TMP_6、REF_1、REF_2`，kept 比例为 0.5，exact 为 false。两种修复的语义相同。
   - `score_graphs` 只在给出文件改名映射时做对应核验，所以 CP5 以后凡是插入存根、补导入文件、在别处补声明的修复，未改动的代码都会被算作改变。精确还原自检无法发现这个问题，因为它恢复原字节，编号不变。
   - 处理：CP4.2（PROMPTS §4.6c）把同一套核验推广到所有评分，只作用于 kept 节点，原样分数并列报告，并增加“移动一个函数”的自检。

## 复现

```bash
python3 -I probe_counter_shift.py <repo> <solc-0.8.38 路径>
python3 -I ../cp4_review_v1/probe_operator_messages.py <repo> <solc 目录> ../cp4_review_v1/fixtures probe_operator_messages_cp41.json
```
