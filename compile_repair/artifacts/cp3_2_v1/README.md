# CP3.2 输入语言、包装和版本阻碍

修改 AI 为 Codex。分支 `compile-repair` 的基线为 `992bec094fb5c3b25a70612e611e203e16198075`。批次只存判定、运行记录、哈希、计数及诊断模板。外部语料仅供本机只读研究。正式报告在 ../../CP3_REPORT.md 的 CP3.2，记录在 ../../docs/CHANGE_LOG.md §39。

| 阅读顺序 | 证据 |
|---|---|
| 原规则停止 | input_census.py、input_gate.json、input_observations.jsonl.gz、explain_gate.py、decision_request.json。31,307 个入口全部核对，8 个旧成功被误排 |
| 用户决定 | authorization.json 记录 2026-11-22 原话“批准三态判定及新旧统计口径”与请求 SHA |
| 生产入口与替换 | classify_inputs.py、language_acceptance.json、language_classifications.jsonl.gz、input_results.jsonl.gz、replacement_provenance.json。23 条替换各有原 SHA、所选旧结果、新结果文件与 SHA |
| 新旧统计口径 | aggregate.py、unit_attributions.jsonl.gz、failure_summary.json、non_solidity.json、unmeasured.jsonl.gz。23 项排除、236 项未测、31,048 项有工具测量；每个原始单元均保留身份 |
| 版本与路线 | version_blockers.json 含交集表、示例和前三个版本组合。taxonomy.json、d6_cp4_final.json 给出范围和顺序 |
| 检查 | scope_check.json 为生产改动前快照。run_suite.py、三个 *_tests.json 和日志记录完整套件。audit_results.py、verification.json 重核旧清单和 221 个原始诊断。doc_check.json、seal.json 记录文档和批次文件哈希 |

新语言状态直接从 `language_classifications.jsonl.gz` 的 `language.status` 读取。按 `corpus=MANDO` 过滤可取得 846 项逐条结果。已确认的 23 项均为 Trace on-chain。判定未定的 316 项包括旧成功 8 项、既有失败 72 项和旧排除 236 项。236 项均没有历史工具测量。对每个版本依赖单元，逐条归因的 `parseable_blockers` 为空列表表示 `none`，其他主因没有这列。

## 只读复现

从仓库根执行以下命令。脚本使用独占创建；临时结果放入新建目录。需要本机原语料及其固定 SHA 和 CP3.1 的归档路径。原规则脚本在首次判据不通过时按设计返回 2，结果保存在独立文件中。

```bash
b=compile_repair/artifacts/cp3_2_v1
py=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
mando=/home/zhao/miniconda3/envs/mando/bin/python
scratch=$(mktemp -d)
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES=""
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
"$py" -B "$b/input_census.py" --out "$scratch"
"$py" -B "$b/explain_gate.py" --census "$scratch/input_gate.json" --out "$scratch/decision_request.json"
"$py" -B "$b/classify_inputs.py" --out "$scratch" --local "$scratch/input_results"
"$py" -B "$b/aggregate.py" --out "$scratch"
"$py" -B -m pytest -x -q -p no:cacheprovider compile_repair/tests --basetemp="$scratch/test_prod"
"$mando" -B -m pytest -x -q -p no:cacheprovider compile_repair/tests --basetemp="$scratch/test_mando"
"$mando" -B -m pytest -x -q -p no:cacheprovider scripts/DFG/dfg_v2/tests --basetemp="$scratch/test_dfg"
```

生产语言判定放行全部 21,223 个既有成功输入。前后两个统计分母及原始工具记录足以复核统计变化。以上聚合只读取已保存的诊断；模块套件另含既有小型编译探针。指定新的临时目录会令含绝对路径的替换引用不同，比较时按单元 ID、原输入 SHA、旧引用、判定和统计复核。正式批次的逐文件身份以 seal.json 为准。
