# CP4.5 普通评分的定义与使用核验

本批次以 `compile-repair@c8ca807a` 和 PROMPTS r2.21 §4.6f 为基线。根目录保存首次实现、测试、两项历史差异清单及逐项归因。第二次用户授权后的完整重验位于 `continuation/`。两轮比较的历史基线均为 CP4.4。

## 查看证据

| 问题 | 文件 |
|---|---|
| 哪些 REF 写回已获批准？ | [首次批准](authorization.json)、[中性夹具的重复定义](definition_request.json)、[第二次批准](continuation/authorization.json)、[两种写入的逐项核对](write_semantics_request.json) |
| 哪些样本在首轮发生了差异？ | [移动](moves_summary.json)、[精确还原](exact_summary.json)。[移动归因](moves_causes.jsonl.gz) 和 [还原归因](exact_causes.jsonl.gz) 每行给出单元、变异身份、受影响节点、指令位置、两侧运算形态和 SHA256。精确还原中单列的 `cp3_13918` 使用 TMP 作为删除目标，证据见写入核对脚本。 |
| 能否定位错误的节点？ | [探针测试](../../tests/test_cp45.py)、[22 项探针日志](continuation/anchor_tests.log)、[旧名探针与故意错误的新旧分数](continuation/fixture_comparison.json)、[六个生产图夹具](continuation/review_scores.json) |
| 历史分数是否一致？ | [200 项移动](continuation/moves_summary.json)、[14,196 项精确还原](continuation/exact_summary.json)、[114 项迁移](continuation/migration_summary.json)。每组另有同名压缩 JSONL，每行含输入身份、图哈希、原分、主指标、存活指标及证明。 |
| 如何核验交付？ | [最终验收](acceptance.json)、[生产函数逐项行数](continuation/scope.json)、[测试](continuation/suites/)、[文档检查](doc_check.json)、[最终 SHA256 清单](seal.json) |

## 复核方法

在仓库根目录使用已有的 `compile-repair-production` 环境。用 `gzip -dc` 逐行读取压缩 JSONL，再按 `unit_id`、`operator`、`mutation_sha256` 与 CP4.4 对齐。两个环境的模块测试与 DFG v2 的完整命令、工作目录、退出码和耗时见各自的 `*_tests.json`。真实手写夹具的历史图从 `compile-repair-local/cp4_4_v1/review/` 按已登记的 SHA256 读取。两轮测试的新临时产物在仓库外 `compile-repair-local/cp4_5_v1/`。

`comparison_stop_seal.json` 封存首次比较时的文件和生产实现哈希。清单中的 `initial_code.patch` 在 Git 中以 [无损 gzip](initial_code.patch.gz) 保存，解压后的字节对应清单里的 SHA256。最终证据封存文件记录两轮输入和结果；交付清单另外包含报告及代码。

```bash
python -B -m pytest -q -p no:cacheprovider compile_repair/tests/test_cp45.py
gzip -dc compile_repair/artifacts/cp4_5_v1/initial_code.patch.gz | sha256sum
```

审查冻结结果时只读检查收据。重算程序使用 `open("x")` 保护现有结果。运行入口依次为 `review_fixtures.py`、`replay_scores.py moves|exact|migration`、`negative.py` 和 `fixture_comparison.py`；完整历史重算依赖本地归档的工具输出和语料。全程使用 CPU，费用 0 美元。
