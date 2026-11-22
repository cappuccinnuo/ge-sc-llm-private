# CP4 破坏与修复评分基准

本目录保存 PROMPTS r2.16 §4.6a 的抽样计划、逐样本观测、验收及运行脚本。起始提交为 `06ad69c26fcb13c163a55333ab95738bfaf71fdd`。先读模块根目录的 `CP4_REPORT.md`。成本为 0 美元，使用本机已有的 production 工具链和编译器信任清单。

## 从统计回查一个样本

| 目的 | 本目录文件 | 关联键与证据 |
|---|---|---|
| 核对基础单元、图及排除原因 | `base_summary.json`、`bases.jsonl.gz`、`base_exclusions.jsonl.gz` | `unit_id`、入口及真值图 SHA256、原结果路径 |
| 查项目划分与可用编辑位置 | `applicability.jsonl.gz`、`sampling.json`、`sample_plan.jsonl.gz` | 每个单元的组、划分、版本系列，各类别的适用性与未适用原因 |
| 查不破坏的对照 | `control_plan.json`、`controls.jsonl`、`control_acceptance.json` | 原图和实测图的 SHA、选定版本及设置，外部封存清单 |
| 查样本及两轮诊断 | `sample_receipts.jsonl.gz`、`benchmark_counts.json` | 按 `(operator, unit_id)` 连接。选定编译器与环境主因分别记录。每个阶段保留诊断首行 |
| 查实际编辑字节 | 收据的 `mutation_path`、`mutation_sha256` | 清单记录文件、原字节区间及 SHA、新字节文件及 SHA、受损闭包每个文件的 SHA。原始资料与源码副本限本地研究 |
| 查精确还原 | `inverse_scores.jsonl.gz`、`inverse_graphs.jsonl.gz`、`inverse_acceptance.json` | 逐样本核验逆编辑，再按单元关联生产工具的实际图、D3 和输入；`affected_by_deletion` 与最终 `lost` 分开 |
| 查错误修复与历史回放 | `negative_probes.py`、`wrong_repairs.json`、`analyzer_history.json` | 22 个源码或格式算子各一项手写错误修复，另有无害缺节点图。历史记录单独以原结果 SHA 核对 |
| 查范围、授权及交付 | `authorization.json`、`design_review_request.json`、`execution_settings.json`、`acceptance.json`、`archives.json`、`seal.json`、`doc_check.json` | 封存覆盖数值证据、生产代码摘要、运行脚本及日志；文档检查在报告写入后独立保存 |

每个源样本使用独立工作目录，归档中只保存允许提交的元数据。术语 `included` 表示构造了预定主因，`resolved_by_environment` 表示环境步骤已可编译并通过图检查，`not_triggered` 表示实测归因未满足该算子的判据。协议给出了各组的唯一划分，后续开发使用 dev，test 用于报告。

## 本机复现

在仓库根目录运行。前提是已有 CP3 的固定本地语料、历史结果及可信编译器。下例创建全新的证据目录与外部工作目录；每条命令返回成功后才运行下一条。失败现场应原样保留。本目录中的既有运行可直接用 `gzip -cd` 读取，逐样本原始字节流摘要见 `archives.json`。

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
batch=compile_repair/artifacts/cp4_v1
prod=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
mando_py=/home/zhao/miniconda3/envs/mando/bin/python
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES="" TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export CP4_OUTPUT="$(mktemp -d /home/zhao/SmartContract/compile-repair-local/cp4-receipts.XXXXXXXX)"
export CP4_SCRATCH="$(mktemp -d /home/zhao/SmartContract/compile-repair-local/cp4-run.XXXXXXXX)"
cp "$batch/authorization.json" "$batch/design_review_request.json" "$CP4_OUTPUT/"
set -e
"$prod" -B "$batch/prepare_bases.py"
"$prod" -B "$batch/controls.py"
"$prod" -B "$batch/plan_samples.py"
"$prod" -B "$batch/run_samples.py"
"$prod" -B "$batch/audit_samples.py"
"$prod" -B "$batch/inverse_scores.py"
"$prod" -B "$batch/negative_probes.py"
"$prod" -B "$batch/run_suite.py" production
"$mando_py" -B "$batch/run_suite.py" mando
"$mando_py" -B "$batch/run_suite.py" dfg
"$prod" -B "$batch/verify_results.py"
"$prod" -B "$batch/archive_receipts.py"
"$prod" -B "$batch/seal.py"
```

每个目录由调用方提供，输出采用独占创建。样本选择和原文件身份可在新目录比对。绝对运行路径、计时和并发写入顺序也进入部分收据，因此独立批次以组、算子、单元、源或图摘要及观测事实对应。

## 单样本入口

```bash
"$prod" -B -m compile_repair.cli benchmark --catalog "$batch/bases.jsonl.gz" --unit-id cp3_17264 --operator control --output "$CP4_SCRATCH/one-control"
"$prod" -B -m compile_repair.cli benchmark-score --request /path/to/score-request.json --output "$CP4_SCRATCH/one-score"
```

`benchmark-score` 接收 JSON 对象。`truth_graph`、可选的 `repaired_graph` 及每个文件的 `original`、`damaged`、`repaired` 以 `{"path": "...", "sha256": "..."}` 绑定实际字节，缺失的文件用 null。每个 `files` 元素的 `name` 是图中的项目相对路径，单文件用空字符串。可选 `damage_changes` 与 `repair_changes` 分别使用该阶段输入坐标，元素含 `start`、`end`、`old`、`new`、`step`；字节对象用 `{"encoding":"hex","data":"..."}`。同时提供观测到的 `solc_returncode` 和布尔值 `d3`。测试 `compile_repair/tests/test_benchmark.py` 中有可执行的完整请求示例。

## 本批两次停止与续跑

迁移测试初次运行在 16 文件断言处停止。用户批准把 CP4 的精确数量改为 17 并断言 `evaluation/benchmark.py` 存在；原日志保存在本目录，生产环境的通过日志保存在 `test_continuation/`。mando 与 DFG 使用各自的首轮日志。

精确还原首轮保留 `inverse_acceptance.json` 的失败状态。只读调查 `investigate_restoration.py` 将两份实际图的唯一差异定位为嵌入创建代码的 IPFS 摘要，见 `restoration_identity_request.json`。本次批准只覆盖该停止现场，见 `restoration_identity_authorization.json`。 `resume_inverse.py --probe` 先在历史编译源路径上逐字节核对工作副本，调用原生产编译入口，把结果写入新的外部目录。`--continue` 只在探针的图字节和评分均相同后运行。每次单文件调用前后验证历史工作文件；需要复用既有对照图时校验其收据和哈希。

最终逆向评分按 `(operator, unit_id)` 连接。取首轮 `inverse_scores.jsonl.gz` 中 `score.exact=true` 的行，再取 `identity_continuation/scores.jsonl.gz` 全部行。首轮失败项仍可在原文件检索。两套图收据相应见 `inverse_graphs.jsonl.gz` 及 `identity_continuation/graphs.jsonl.gz`。 `verify_results.py` 验证唯一性、键集合与逐样本图／编辑摘要，以及续跑授权的适用范围。506 行分层表可直接用电子表格打开 `strata.tsv`。

可用以下命令在仓库根目录只读检查已交付文件，无需运行 solc。仓库外的源及图仍需原本机资料才能复核。
```bash
python -B - <<'PY'
import hashlib, json
from pathlib import Path
p = Path("compile_repair/artifacts/cp4_v1")
seal = json.loads((p / "seal.json").read_bytes())
for name, record in seal["artifacts"].items():
    assert hashlib.sha256((p / name).read_bytes()).hexdigest() == record["sha256"], name
for name, digest in seal["implementation"].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
print(len(seal["artifacts"]), "evidence files verified")
PY
```
