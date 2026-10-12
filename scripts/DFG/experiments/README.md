# Main protocol: paper_kfold (Codex, 2026-10-12)

The default entry point is now **run_experiment --protocol paper_kfold**.
The previous **ddg-nested-paired-v1** remains the unchanged opt-in
**nested_strict** side comparison. Its inputs, code, strict schema policy,
checkpoints and logs have not been overwritten.

## Main protocol contract

- Version: ddg-paper-kfold-v1. Graph classification: 5 file folds; node
  classification: 10 file folds. Exactly convert the existing frozen folds:
  train = inner_train UNION inner_val; val = former outer_test.
  No new shuffle, seed selection, file exclusion or label reconstruction.
- Train updates parameters; post-update eval val loss selects best and stops
  training. The SAME val fold is scored. Results are **CV validation** and
  MUST NOT be described as independent outer test performance.
- Construct E0 from the complete E0 task graph, and E1 from complete E1.
  Every forward uses that full fixed graph. Node supervision uses file-derived
  node masks; contract supervision uses batches of selected filenames.
  Dataset A fits in one full training-file batch per update.
- Keep all nodes, edges, files, features and labels. Cross-file edges are an
  error, never silently filtered. No three-part GraphView in the main runner.
- Register each model's own full schema once. A registered node type/relation
  with no train instances is allowed at validation, and explicitly audited.
  Truly missing registration, wrong dictionary indices, input drift or
  test-time parameter creation are errors. No empty DDG relations in E0.
- Reuse the prior semantic common initialization algorithm unchanged:
  semantic-paired-native-xavier-v1. Initialization and protocol versions are
  separate. No trained E0 weights initialize E1; no parameter borrowing.
- Reuse current production HGT, inside_token features, optimizer schedule,
  StopMonitor and corrected best/last behavior. Main protocol changes the
  split, forward and scoring policy; it does NOT claim all paper code/training
  details are identical or recover the author's unpublished folds.
- DDG gradient reports distinguish no training instances from broken wiring.
  A validation-only DDG bank need not have nonzero supervised gradient.
  Contract Adam weight decay can still move these weights: that is not
  evidence of training supervision for the relation.
- Checkpoints use a distinct format, binding protocol, initialization version,
  full registered schema, forward scope, scoring role, graph/features/labels,
  split, support, initial state and effective config. Prediction exports are
  cv_validation_predictions.json. Best/last roundtrip logits must match.

## New implementation

paper_protocol.py converts and validates splits; paper_runtime.py provides
full-graph supervision/schema/support/gradient audits; paper_checkpoint.py
binds main checkpoints; paper_run.py trains and scores the main protocol.
run_experiment.py dispatches protocols. audit_paper.py checks all main folds;
summarize_paper.py exports CV-only metrics and rejects mixed scoring roles.
All existing experiment .py files and all DDG/model/tokenizer/trainer files
are preserved. New tests use synthetic graphs (not compiler-validated Solidity).

New results live ONLY under artifacts/paper_kfold/<version>/.
New nested alias runs live ONLY under artifacts/nested_strict/<version>/.
Legacy artifacts/20261012_v1 remain unchanged and are read-only input sources.
No existing output directory can be overwritten.

## Current inputs and commands

The two author-label prepared cohorts already exist; reuse them without
regenerating graphs or features. Converted main splits are under
artifacts/paper_kfold/20261012_v1/<cohort>/splits/.

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"

# Another short check; choose an unused output directory.
python -u -B -m scripts.DFG.experiments.run_experiment \
  --protocol paper_kfold \
  --prepared scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared \
  --splits scripts/DFG/experiments/artifacts/paper_kfold/20261012_v1/reentrancy_author/splits/node_folds.json \
  --task node --mode smoke --fold 0 --smoke_epochs 3 --epochs 50 \
  --device cpu --threads 2 \
  --output scripts/DFG/experiments/artifacts/paper_kfold/manual_reentrancy_node_01
~~~

For contract classification, use --task contract and contract_folds.json.
For access control, replace reentrancy_author with access_control_author.
Smoke runs three updates on the original 50-step schedule, not a compressed
three-step schedule. These scores are wiring checks, not full CV conclusions.

~~~bash
# Optional strict nested side comparison, not the main protocol.
python -u -B -m scripts.DFG.experiments.run_experiment \
  --protocol nested_strict \
  --prepared scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared \
  --splits scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/node_folds.json \
  --task node --mode smoke --fold 0 --smoke_epochs 3 --device cpu \
  --output scripts/DFG/experiments/artifacts/nested_strict/manual_reentrancy_node_01
~~~

The nested example can remain blocked for unseen inner-train schema; this is
intentional preserved behavior, not a reason to filter the data.

~~~bash
# Convert frozen splits into a NEW main version (does not rebuild graphs).
python -u -B -m scripts.DFG.experiments.paper_protocol \
  --nested_dir scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits \
  --output scripts/DFG/experiments/artifacts/paper_kfold/NEW_VERSION/reentrancy_author/splits

# Repeat after converting access_control_author too.
python -u -B -m scripts.DFG.experiments.audit_paper \
  --prepared_root scripts/DFG/experiments/artifacts/20261012_v1 \
  --splits_root scripts/DFG/experiments/artifacts/paper_kfold/NEW_VERSION \
  --output scripts/DFG/experiments/artifacts/paper_kfold/NEW_VERSION/structure_audit

python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests
python -B -m pytest -q -p no:cacheprovider tests
~~~

Full CV is implemented through explicit --mode full --all_folds, but is NOT
automatically run or promoted from smoke. No complete 60-model run was requested
in this stage. See PAPER_KFOLD_REPORT_2026-10-12.md for actual execution evidence.

## Encoding evidence and preserved historical record

REPORT_2026-10-12.md is valid UTF-8 but contains 2,602 literal ASCII question
marks and zero Chinese characters. This is lost file content, not a decoding
display issue. Original bytes remain unchanged; byte backup and SHA-256 evidence
are under audit/paper_kfold_v1/. No guessed restoration was performed.

The remaining text below is the preserved earlier **nested_strict** README
record. Its phase names, strict policy and legacy commands describe only that
side protocol; the main protocol is specified above.

---

# Frozen DDG E0/E1 experiments

Codex, 2026-10-12. All new orchestration, tests and results live here.
DDG algorithms, original tokenizer, HGT and original trainers are unchanged.

## Inputs

Dataset A reentrancy and access_control are independent cohorts.

| Cohort | Label version | Role |
|---|---|---|
| reentrancy_author | released author labels | primary |
| access_control_author | released author labels | primary |
| reentrancy_local_narrow | local narrow, source-range labels | optional separate cohort |
| access_control_local_narrow | local dataset_a_source_range_v1 labels | optional separate cohort |

The exact catalog paths are in prepare.py and saved manifests. Local narrow
reentrancy has **6,978** positives: it is not source_range-v2 with 6,976.
Local narrow cohorts are audited but have not been enhanced or trained this run.

E0 is the unchanged fixed HCG; E1 only adds DATA_DEF_USE using the frozen scalar
intraprocedural algorithm. Fallback samples, IDs, labels, features and base edges
remain. Contract task uses all source files. Node task induces the same graph
on graph-labelled buggy files. Node metrics do not deduplicate source lines.

Preparation compares the token-bearing graph to the raw graph: only token may
differ. All existing vectors are recomputed for verification without assignment.
Fixed cached tokenizer: Salesforce/codet5p-770m revision
3f7cc6e80aee6612f41253b5ee28f09f86faa35f, existing encode_ids, float32[512],
special tokens, truncation and padding. Input is exact stored node.code,
including author DOT quotes/escapes. No LLM weights/download/fine-tuning or
alternate normalization. Author graphs had no token; these are local features.

Label serialization is decoded only for validation/counts; original attributes
are unchanged. Source, grammar, feature assets and code hashes are recorded.
Strict projector is unchanged; no nearest-line matching. Accepted current
source anchors do not prove unpublished historical author source hashes.

## Nested evaluation

1. Outer graph StratifiedKFold(5); node KFold(10), fixed seed1, sorted filenames.
2. Fixed inner validation: 20% of each outer training population, stratified for
   graph task. Save exhaustive disjoint inner_train/inner_val/outer_test lists.
3. Only inner_train contributes supervised gradients. Only inner_val loss
   selects best.pt and drives early stopping.
4. Save best and last before reading outer test targets for scoring. No outer
   metric feeds back into checkpoint selection or configuration.
5. Each phase uses its own file-induced NetworkX/DGL view through unchanged
   production forward. Cross-file graph edges block the run.
6. Schema is created once. All inner_val/test node and canonical relation types
   must occur in inner_train, otherwise **block the whole paired fold** and
   report it. Never silently remove edges/samples or create test-time parameters.
7. Fresh E0/E1 constructors precede any optimizer. Copy common tensors by node
   name/canonical relation, including indexed K/Q/V/A/norm/skip. E1-only DDG
   slices use isolated seeds and native full-bank Xavier scale. E0 stays
   unchanged; trained E0 weights are never used.

Blocked folds are not scores and cannot be silently excluded from an average.
Do not search for a favourable fold/seed. A different unseen-relation policy
requires a separately named protocol and documented tradeoff.

This is a new nested protocol, not exact paper reproduction or author-released
folds. It is file-level, NOT template deduplication. SolidiFI template overlap
and uncertain label provenance remain limitations.

## Training

Unchanged HGTVulNodeClassifier / HGTVulGraphClassifier; shared E0/E1 rules:

- hidden128, 2 layers, 8 heads, norm on, dropout0.2;
- full inner-training partition per step, unweighted cross entropy;
- Adam node initial LR0.0002, max0.005, weight_decay0;
  contract initial LR0.0005, max0.01, weight_decay5e-6;
- OneCycleLR node div_factor25 / contract20, final_div_factor1,
  cycle_momentum=True; default50-step schedule;
- patience7, delta0.001 on post-update eval inner loss. Save every strict new
  minimum independently of the delta patience reference. Save last at the end.
- Smoke defaults to fold0, maximum3 epochs using the **50-step schedule**.
  Smoke F1 is not efficacy evidence. No automatic promotion to full training.

Effective config records software/code versions. Per-variant optimizer_schedule
records actual defaults and a JSON representation of the schedule state;
history includes actual LR and Adam beta1. Raw scheduler state remains in .pt.

## Checkpoints

Fold stores E0_initial.pt/E1_initial.pt and initialization_audit.json. Trained
variants store best.pt/last.pt, metadata sidecars, model_input.json, binding.json,
history.jsonl, gradient_audit.json, phase view manifests, outer_predictions.json.

Existing capture_model_input/assert_model_input bind graph, frozen features,
labels, type/canonical dictionaries, prepared/source manifest, split, initial
weights, effective config and code. Before loading: verify file hash, binding,
model-input fingerprint and weight digest. Repeated restored eval predictions
must match exactly. No resume-training CLI is implemented.

Graphs preserve original IDs. Original model loader internally reindexes;
predictions record both indices and original graph IDs. Stored source lines are
original graph metadata, not newly certified original-source coordinates.

## Commands

Existing mando environment only; no dependency installation:

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
~~~

Primary v1 preparations and splits already exist. To generate a new version,
choose a new destination; existing directories cannot be overwritten.

~~~bash
python -u -B -m scripts.DFG.experiments.prepare \
  --cohort reentrancy_author \
  --output scripts/DFG/experiments/artifacts/NEW_VERSION/reentrancy_author/prepared

python -u -B -m scripts.DFG.experiments.freeze_splits \
  --prepared scripts/DFG/experiments/artifacts/NEW_VERSION/reentrancy_author/prepared \
  --output scripts/DFG/experiments/artifacts/NEW_VERSION/reentrancy_author/splits
~~~

Manual smoke against existing inputs (new output name required):

~~~bash
python -u -B -m scripts.DFG.experiments.run_pair \
  --prepared scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/prepared \
  --splits scripts/DFG/experiments/artifacts/20261012_v1/reentrancy_author/splits/node_folds.json \
  --task node --mode smoke --fold 0 --smoke_epochs 3 --device cpu \
  --output scripts/DFG/experiments/artifacts/manual_smoke_reentrancy_node_01
~~~

For contract use --task contract and contract_folds.json. For access control
replace reentrancy_author with access_control_author. No BASE/RUN_TAG needed.
Schema-blocked result.json is a diagnostic, not a trained result. Full mode
requires an explicit --mode full; --all_folds is rejected in smoke mode.

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests
python -B -m pytest -q -p no:cacheprovider \
  tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py
~~~

CLI --help documents implemented options. Original train_*.sh scripts are not
changed. summarize --runs ... --output ... exports metrics including blocked
folds. Percent scores and percentage-point deltas are distinguished.

## Limits

The experiment studies the frozen scalar DDG under one label/feature/protocol
version; it does not implement complete Solidity dependencies or recover author
annotation construction. Author labels are a reference, not certified truth.
Keep narrow comparisons separate. Template-grouped splits and relation-count
controls are possible follow-ups, not implemented/automatically run here.
State/mapping, reverse DDG and missing emit-node repairs remain outside scope.


## 2026-10-12：正式 paper_kfold 实验入口（Codex）

本轮的 E0 是冻结作者 HCG/标签 + 本地已核验的 CodeT5p-770m tokenizer IDs
（512 维、inside_token）+ 当前 HGT/训练规则；E1 在同一任务图上只增加正向
DATA_DEF_USE。E0 不注册空 DDG 关系。共同类型和关系的参数按语义成对初始化；
E1 的新增关系有独立初始参数，不使用训练后的 E0 权重。

新的入口是 formal.py，包裹原 paper_run.py，不改变已有计算和训练规则。
固定 full、50 epoch 上限、seed=1、现有 patience=7/delta=0.001；CLI 不提供临时
改这些参数的选项。统计角色固定 CV validation，best 与 last 分开报告。
初批正式范围是 Dataset A 的两个漏洞，合约5折/节点10折，共30配对折=60次拟合，
不是已经完成全部7类。nested_strict 不进入本批汇总。

### 已准备批次及运行命令

以下命令在 WSL 的项目根目录、mando 环境运行，无须 BASE/RUN_TAG：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

# 只验证冻结文件、已完成折及其 checkpoint；完整任务才生成均值/标准差
python -B -m scripts.DFG.experiments.formal verify \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1

# 阶段B：只运行重入合约 fold0 配对；已通过时仅验证、复用，不重训
python -u -B -m scripts.DFG.experiments.formal stage-b \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1
~~~

阶段C须在阶段B通过后由用户明确选择执行。此命令才会运行其余折，严格按重入合约、
访问控制合约、重入节点、访问控制节点的顺序；每个任务完整验收后才进入下一个：

~~~bash
python -u -B -m scripts.DFG.experiments.formal stage-c \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1 \
  --confirm-stage-c
~~~

查看单折训练实时信息：

~~~bash
tail -F scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1/jobs/reentrancy_author_contract_fold0/attempt_001.log
~~~

若运行失败，先检查日志/故障原因，**不能把失败折删掉**。同一冻结代码和输入下，
给原 stage-b/stage-c 命令追加 --retry-failed，创建新的 attempt 重新运行整对，
保留旧日志、权重及失败证据。这里不是 epoch 级续训。已通过折会检查文件哈希后复用。
控制器互斥锁和 worker PID+启动时刻检查防止重复运行；存活的旧 worker 会阻止重试。
修复导致冻结代码改变时，本批拒绝继续，应明确建立另一版本，不能静默混用结果。

### 产物与解释

- plan.json/plan.seal.json：任务顺序、代码与数据哈希、设备、资源证据和固定配置。
- state.json：本批与各折执行状态；不是训练 checkpoint。
- jobs/<任务>_foldN/attempt_NNN/：原运行器完整产物及新增 telemetry.json。
- attempt_NNN.receipt.json：验收记录、全部产物摘要和逐样本 E0/E1 错误转移。
- summaries/<任务>/folds.csv：best/last 各折 BF1、MF1、正类 Precision/Recall、
  E1−E0（百分点）、epoch、耗时、参数量、DDG 支持量和梯度。
- summary.json：等权折均值、样本标准差（ddof=1），不是置信区间。
- audit/formal_20261012_v1/：GPU 探针、测试输出、执行与不变量检查。
- FORMAL_EXPERIMENT_REPORT_2026-10-12.md：本轮实际执行结果及限制。

正式验收重算导出预测的四项指标、检查 mask/文件覆盖、训练/验证标签和输入绑定，
逐轮重放学习率与早停、核对 best/last、梯度、参数量和 checkpoint 哈希。
不改变原运行器的 checkpoint 重载一致性判据；若该判据失败，停止后续正式实验。
没有训练实例的已注册关系可以保留零监督梯度；不能删除这些折。新增 DDG 参数的
权重更新也可能包含 weight decay，不等同于有监督梯度。

GPU 预检使用一次性模型，完成 E0/E1 同时加载及各一次完整图前向/反向/Adam更新。
探针权重不用于正式初始化。已通过的一步探针不保证未来没有显存竞争或CUDA数值问题。
正式耗时采用 monotonic/perf_counter，含训练、验证、checkpoint IO及重载评分；
不是纯 GPU kernel 时间。

新建不同批次需使用新目录，并重新核验资源报告与代码/输入，不能覆盖现有结果。
本轮没有运行新的 narrow、nested_strict、多 seed 或随机边对照。后续分析先看成对折
差值、错误转移、DDG 覆盖/支持以及 best/last；没有提升也须保留。作者标签历史、
SolidiFI 模板复用、同 val 选模偏差仍存在。新增关系也改变参数量及 HGT 关系聚合，
不能单凭 E1 优于 E0 就把全部提升归因于数据语义。
