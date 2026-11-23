# cp5_review_v1：CP5 检查点审查证据（Claude，2026-11-23）

审查对象：`compile-repair@3c7ae7ee5`（Codex 的 CP5 检查点：`toolchain/project.py`、新增 `rules/dependencies.py`、`pipeline.py`、`cli.py`、`evaluation/benchmark.py`、`evaluation/report.py`，`tests/test_cp5.py`，产物 `cp5_v1/`，CP5_REPORT、四份记录与 CHANGE_LOG §55）。本目录是独立复核证据，不是生产代码；不含外部语料原文。

## 状态

CP5 尚未完成。Codex 的报告明确写为检查点：172 个获批发布版中下载了 149 个，第 23 个在 HTTP 状态之前断开；包装的 optimizer 设置等待用户决定；完整索引、版本选择规则、2,264 个基准样本的评分与 9,138 个外部单元的重跑都没有运行。

## 文件

| 文件 | 内容 |
|---|---|
| `combination_bound.json` | 由 `cp5_v1/d23_download_request.json` 与 `measurement_units.jsonl.gz` 计算：每个单元待补、且在下载清单中的包的发布版数之积（第 3 步在词法过滤之前的组合上限） |

## 已核对、成立的部分

1. 第 0 节：16,136 个真值图自比全部 exact、identical（`self_summary.json`）；CP4.5 历史评分中 rejected 为 0（`historical_status.json`）。CP4.5 带入的两项限制都已核验。
2. 测量的加减关系：8,469 个待补包单元 = T1 73 + T2 0 + 至少一个 T3 8,396；五个主因合计 9,308，单元可多因，去重 9,138，另有 6 个只在候选原因中出现，共 9,144。
3. D22、D23 经用户批准；下载逐个核对 npm SHA512 与本地 SHA256，原始包在仓库外；失败时停下、没有部分文件、保留日志。处理正确。
4. 代码：
   - 第 3 步：发布版的传递导入必须在发布版内解析、不得越出发布版目录；导入符号必须有声明；pragma 交集非空；发布版写入保留目录 `.compile_repair/deps/<包>@<版本>/`，用 remapping 接入；已解析的项目导入若会因此改变字节即拒绝（`existing_import_would_change`）；原文件在修复前后核对 SHA。
   - 第 4 步：只替换导入字面量的字节，替换前核对原字节；候选须声明所需符号且 pragma 相容；只有唯一最佳候选才改写。
   - “closest” 规则在 pipeline 中按实际选定编译器与首选编译器的小版本距离比较，“latest”“oldest” 按版本排序；三条规则有对照测试。
5. MANDO 回归：843 个成功图与 v5 逐字节相同，第 2–4 步触发 0 次（`final_mando/summary.json`）。
6. 测试：`tests/test_cp5.py` 依赖用户本机的编译器目录与授权文件，在审查环境无法收集（既有的可移植性限制），以 Codex 记录的 1,126 / 651 / 2,653 项结果为准。

## 问题

1. **第 4 步在基准上没有可评测的样本。** CP4 的 missing_relative_file 算子删除被导入的文件（`benchmark.py` 中 `delete_file`），io_error 算子把导入改为 `file:cp4_nonexistent_dependency.sol`。第 4 步只按文件名在项目中找候选，这两类样本只有在项目里恰好另有同名副本时才可能修复。开发探针 cp3_00318、cp3_00138 都以 `unresolved_imports` 结束，符合这一点。D6 路线写的是“删除或移动相对依赖”，“移动”变体没有构造。真实语料的 412 个缺相对文件单元中，项目内有同名候选的数量也没有测量。
2. **第 3 步没有候选数上限。** `dependency_choices` 对每个包的全部相容发布版递归组合，每个组合都要编译；最新规则在第一次成功时停止，但其他错误使单元无法成功时，所有组合都会编译。按下载清单计算，组合上限达到 100 的单元有 783 个，达到 1,000 的 184 个，最大 13,824（`combination_bound.json`）。词法过滤会削减实际数量，但削减多少没有测量。9,138 个单元的全量重跑可能因此耗时失控。
3. **版本选择规则的依据太少。** 缺包基准的 dev 划分只有 8 个样本，用来在三条规则中选一条不够。另外，每个包只下载了至多 12 个代表发布版，“所选发布版与原始包字节相同”的比例天然受限，应与编译成功率分开解读。
4. **standard JSON 样本的 kept 分母为 0。** 包装算子把整个源文件作为破坏区间，kept 比例恒为 1，exact 由 lost 与 added 为 0 决定。报告这一算子时应使用恢复节点数、lost 与 added，而不是 kept 比例。

## 对 Codex 两项请求的判断

- **optimizer**：同意 Codex 的方案（只在 `toolchain/solc.py::validate_settings` 中允许经校验的 `--optimize` 与 `--optimize-runs`，runs 为 32 位无符号十进制，其余字段记录不用）。理由：图来自 AST，不受 optimizer 影响；但 104 个包装使用 viaIR，viaIR 在不开 optimizer 时更容易出现 Stack too deep 而编译失败，而包装自带的就是作者部署时的设置。只用于包装自带的设置，不作为通用重试。需要用户确认（D24）。
- **续传**：同意。只下载 D23 清单中剩余的 23 个精确 URL，每个版本新建连接，沿用原有单个与累计上限，再次失败即停。仍在 D23 授权范围内。

## 处理

CP5.1（PROMPTS §4.6h）：确认 D24 与续传后完成索引；第 3 步加候选编译上限并先在 dev 上测量；版本规则用 dev 基准与 dev 划分的真实单元共同选择；增加缺相对文件的“移动”算子并测量真实语料中的同名候选；然后完成 CP5 第 6 节的全部评估。
