# CP7 证据：RAG 知识库（修改 AI：Claude，2026-11-26）

规格见 PROMPTS r2.36 §4.7，记录见 docs/CHANGE_LOG.md §83。云端完成 K1、K3 与全部测试；K2 的全量评测需要本机的完整 npm 离线索引与 CP5 缺包样本，由 Codex 运行一次（§4.7 本机步骤）。

## 实现

- `rag/knowledge.py`：K1 文档（每个受支持版本的 `docs/*.rst` 按标题切成节，跨版本逐字节相同的节合并并记录所属版本）、K2 库索引（CP5 封存索引中每个 Solidity 文件一条，键为声明的符号与发布的导入路径）、K3 修复记忆（流水线成功记录中带改动的修复，键为被消除错误的模板与类别，带项目分组，不含任何数据集标签）；`message_template` 只保留文档中出现过的术语与类型名，其余引号内的值换成 `<id>`；带 SHA-256 封存的 JSON-lines 存储。
- `rag/retrieve.py`：每个来源先精确键（K1 术语、K2 符号或导入路径、K3 模板或类别），再用 BM25（k1=1.2，b=0.75，标题词权重 3，轻量词干）补足到 k。过滤：K1 只取查询版本的文档，K2 要求文件 pragma 区间包含该版本，K3 排除查询自己的项目分组；K3 查询没有分组直接报错。
- `evaluation/report.py`：K1 正确知识表 `K1_TRUTH`（在第一次检索之前按文档写定）、CP4 样本查询、命中率与 k 的选择。
- 非测试文件 20 → 23（rag/ 包，PROMPTS 3.10 已列）；测试 `tests/test_cp7.py` 15 项。

## K1 来源

`fetch_docs.py` 对 ethereum/solidity 做无 blob 克隆，按 92 个受支持版本（0.4.12–0.8.38，与生产编译器清单一致）的标签导出 `docs/` 下 4,621 个 .rst；`k1_docs_manifest.json` 记录每个标签的提交、docs 目录树 id 与文件哈希。文档本身不提交（上游 GPL-3.0，本地研究使用）。合并后 3,791 节，词表 202 个术语（来自 cheatsheet、units-and-global-variables 与各版 breaking changes）。

## K1 基准（CP4 样本的首个错误行，k1_benchmark_cloud.json）

查询只用记录的首个错误行、类别、版本（选定或环境版本，否则该系列最新版本）。11,858 个包含的样本中，3,170 个属于没有 K1 正确知识的算子（项目或库上下文、或没有文档解释），200 个所在版本的文档没有正确的节，其余 8,488 个计分。开发中的取舍（词干、标题权重、例子样板行去除、`F:` 错误补“版本 pragma”）只在 dev 上判断；test 只运行一次。

| 划分 | 样本 | hit@1 | hit@3 | hit@5 | hit@10 |
|---|---|---|---|---|---|
| dev | 1,771 | 0.245 | 0.744 | 0.814 | 0.826 |
| test | 6,717 | 0.245 | 0.754 | **0.826** | 0.835 |

k 的规则：dev 上命中率达到 k=10 时 95% 的最小 k，得 **k=5**。

按算子（test hit@5）：版本 pragma 五类、ABI coder、NatSpec、可见性、标准 JSON、io_error 为 1.0，missing_relative_file 0.80，duplicate_definition 0.23，type_error_other 0.0。注意：样本按模板高度重复，8,488 个样本只有 67 种（算子、模板、版本）组合；按完整首行去重后的 960 个查询 hit@5 为 0.46，未命中几乎全是 type_error_other（329）与 duplicate_definition（188）。type_error_other 的正确节定为 control-structures 的 “Control Structures”（文档说明非布尔不转换为布尔），检索返回的是 “Implicit Conversions” 等相关节；这一限制如实保留，不在 test 之后改正确知识表。

## K3 基准与留一项目（k3_benchmark_cloud.json）

记忆来自云端 CP6.3 的 550 个与 CP6.5 的 319 个真实单元（合并后 625 个）中带改动的成功修复：72 条、59 个项目。每条记忆以它自己修复前的错误作查询，正确命中为来自其他项目、修复步骤集合相同的记忆。

| 核对 | 结果 |
|---|---|
| 计分查询 | 71 |
| hit@1 / hit@5 / hit@10 | 0.859 / 0.930 / 1.0 |
| 返回自己项目的记忆 | 0 次（全部查询、k=10） |
| 只含某一项目记忆时该项目的检索 | 59/59 为空 |

规模小，只说明机制；更大的 K3 在 CP8 由代理运行逐步积累，同样经过这两项检查。

## K2

`k2_benchmark.py` 以 CP5 缺包样本的 mutation.json 为输入：每个被移除的文件一个查询，只给损坏后源码仍在使用的导入路径与版本；正确命中为同包同路径的文件（任意发布版），另计与被移除文件字节相同的发布版。云端只用 CP6.4 的小索引（openzeppelin-solidity@2.3.0）做了冒烟运行（2/2 命中）；全量需本机运行。

## 云端核验

| 核对 | 结果 |
|---|---|
| 生产测试 | 1,313 passed / 6 skipped（production_tests_cloud.json；CP6.5 为 1,298 / 6） |
| 流水线 | 未改动；MANDO 回归不需要重跑 |
| 费用 | 0，没有 LLM 调用 |
