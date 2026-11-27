# CompileRepair CP7 报告：RAG 知识库（修改 AI：Claude，2026-11-26；本报告于 2026-11-27 文档核对时补写）

规格：PROMPTS r2.36–r2.37 §4.7；记录：docs/CHANGE_LOG.md §83、§84；证据：artifacts/cp7_v1/。

## 实现
- `rag/knowledge.py`（新增）：K1 文档（92 个受支持版本标签的 `docs/*.rst`，按标题切节，跨版本相同的节合并）、K2 库索引（CP5 封存索引的每个文件）、K3 修复记忆（成功修复，带项目分组，无数据集标签）；`message_template` 只保留文档术语；封存的 JSON-lines 存储。
- `rag/retrieve.py`（新增）：每个来源先精确键再 BM25（k1=1.2、b=0.75、标题权重 3、轻量词干）；K1 版本过滤、K2 pragma 过滤、K3 留一项目（强制）。
- `evaluation/report.py`：`K1_TRUTH`（第一次检索前写定）、样本查询、命中率与 k 的选择。
- 测试 `tests/test_cp7.py` 15 项；`tests/test_cp1_1.py` 文件数 20 → 23。
- 与 PROMPTS 的差异：无。

## 真实验收

| 项 | 实际 | 来源 |
|---|---|---|
| K1（CP4 样本首行，test 6,717） | hit@5 0.826；dev 选出 k=5；去重后 960 个查询 hit@5 0.46 | artifacts/cp7_v1/k1_benchmark_cloud.json |
| K2（本机全量，114 个样本、421 个查询） | 同包同路径 test hit@5 0.977；字节相同发布版 hit@3 1.0 | artifacts/cp7_v1/local/k2_benchmark_local.json（Codex，提交 951b4db7） |
| K3（云端 72 条、59 个项目） | hit@5 0.93；同组返回 0；单组隔离 59/59 为空 | artifacts/cp7_v1/k3_benchmark_cloud.json |

未命中集中在 type_error_other（正确节定得窄）与 duplicate_definition；9 个 K2 未命中由 pragma 过滤造成（有意）。

## 测试与开发记录
生产测试 1,313 passed / 6 skipped（artifacts/cp7_v1/production_tests_cloud.json）。dev 上修正：首行 `Error:` 解析、代码例子中的 pragma 样板、0.8.39 文档误入。

## 归档与复现
- K1 获取：`python -B compile_repair/artifacts/cp7_v1/fetch_docs.py <工作目录> <文档根> <清单> <版本...>`；清单 `k1_docs_manifest.json`（提交、目录树、文件哈希）。文档不提交。
- 基准：`k1_benchmark.py`、`k2_benchmark.py`、`k3_benchmark.py`（用法见各文件首部）。

## 停止位置与后续边界
CP7 完成；下一步 CP8。
