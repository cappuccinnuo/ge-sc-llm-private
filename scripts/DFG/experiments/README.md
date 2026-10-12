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
