# cp4_review_v1：CP4 审查证据（Claude，2026-11-22）

审查对象：`compile-repair@812f8ea01`（Codex 的 CP4：`evaluation/benchmark.py`、`core/provenance.py::compose_offsets`、`cli.py` 的两个子命令，`tests/test_benchmark.py`，产物 `cp4_v1/`，CP4_REPORT 与四份记录）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 环境

Claude 的云端环境：Python 3.12；solc 为 GitHub 发布的静态构建，SHA256 与官方 `list.json` 相同（本目录用 0.4.24、0.5.17、0.8.0、0.8.38）。

## 文件

| 文件 | 内容 |
|---|---|
| `fixtures/` | 审查手写的 8 个合约：删除中间或末尾合约的右花括号、函数与合约同名、字符串字面量中的非法 UTF-8、标识符中的非法 UTF-8、嵌套动态数组参数、两种“memory 结构体数组复制到 storage” |
| `probe_operator_messages.py` / `.json` | 每个夹具在 4 个版本上的 solc rc、首条错误或 `std::exception::what`，以及模块自己的 `parse_diagnostics` + `classify_diagnostic` 给出的类别 |

## 结论

1. **成立的部分**：基础单元筛选（排除 5,087 个 0 节点图与语言未定项，16,136 个入选）、按组哈希的 dev/test 划分、分层抽样、两阶段触发判定、200/200 对照、11,858 个纳入样本的精确还原（kept/边/调用比例为 1，lost 与 added 为 0）、22/22 故意错误修复被检出、MANDO 真值与 v5 字节相同。Codex 在精确还原首次失败（1/4,316）时停下、定位到嵌入创建码末尾的元数据哈希、经批准后在原路径只读重编通过，处理正确。
2. **问题一：分类器把常见的 solc 消息归为 other**（`probe_operator_messages.json`）。
   - 删除右花括号后，0.4.24、0.5.17、0.8.0、0.8.38 都报 `Function, variable, struct or modifier declaration expected.`；它不以 “Expected” 开头，`classify_diagnostic` 的解析规则不命中，归为 other。CP4 的 unbalanced_structure 950 个样本中 906 个因此主因为 other。
   - 函数与合约同名：`Functions are not allowed to have the same name as the contract…`，归为 other；CP4 的 declaration_error 908 个样本全部未纳入。原因是 declaration_error 规则依赖 `DeclarationError` 类型，而命令行只输出 `Error`（CP2.2 审查已实测）。
   - `This type is only supported in the new experimental ABI encoder`（0.4.24、0.5.17）归为 other。
   - 这些不只影响基准：CP3 的真实语料 other 模板（`cp3_binding_v1/failure_summary.json` 的 other_template_unit_counts）中有 `Function, variable, struct or modifier declaration expected.`（17 个单元）、同名函数（1）、`This type is only supported in ABI coder v2 / ABIEncoderV2`（5 + 5）、`Free functions cannot have visibility.`（158）、`Only constant variables are allowed at file level.`（7）等，主因与任一候选表中的 other 因此偏大，对应类别偏小。
3. **问题二：两个算子没有产生目标错误**（同上）。
   - encoding：把非法字节放在标识符里，solc 只报 `Expected identifier but got 'ILLEGAL'`（parser_error_other）。放在字符串字面量里，0.4.24、0.5.17 报 `contains invalid UTF-8 sequence`，0.8.0、0.8.38 报 `Invalid character in string.`，模块都归为 encoding。
   - unimplemented_feature：嵌套动态数组参数在 0.4.24、0.5.17 报“需要实验 ABI 编码器”（other），0.8.0、0.8.38 编译成功，不是未实现特性。“memory 结构体数组复制到 storage”在 0.4.24、0.5.17、0.8.0 抛 UnimplementedFeatureError（`Copying of type struct A.S memory[] memory to storage not yet supported.`），模块归为 unimplemented_feature；0.8.38 编译成功。支持从哪个版本开始未在审查环境确定。
4. **问题三：缺包依赖没有基准样本**。unresolved_package_import 是真实失败的 86%（8,454 个主因），但合格基础闭包中没有可删除的包依赖（适用 0）：语料没有 node_modules 与 remapping，凡是包导入的单元都编译失败、不会成为基础单元。CP5 的第 3、4 步因此没有带真值的评测样本。
5. **问题四：嵌入创建码的元数据哈希会使后续评分误判**。精确还原的失败例（cp3_23979，0.6.12）中，`deployPool` 的一个 IR 操作包含 11,199 字节的创建码，只有末尾 53 字节 CBOR 中的 IPFS 摘要不同，原因是源文件路径不同。solc 元数据包含源单元名与源内容的哈希，所以 CP5 以后的任何真实修复（源字节一定改变）都会改变该摘要；只要 IR 中嵌入了创建码，评分就会报告不相同，即使代码语义没有变化。原路径重编只解决了精确还原这一种情况。

## 复现

```bash
python3 -I probe_operator_messages.py <repo> <solc 目录> fixtures probe_operator_messages.json
```
