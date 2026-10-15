# Stage H1: full E2/E3b paper_kfold CV

This sibling runner leaves e23_pilot and all Stage G receipts/seals untouched.
It reuses the exact Stage G model, supervision, fit, checkpoint and per-fit verifier.
The new worker adds fold/batch binding and exclusive-GPU preflight; no numerical rule changes.

## Frozen experiment

- E2: author HCG + corrected v1.1 scalar DATA_DEF_USE.
- E3a: E2 + STATE_DEF_USE (initial states reserved, no new training in H1).
- E3b: E3a + STATE_ACCESS_ORDER + EXTERNAL_CALL_BEFORE_STATE_WRITE.
- Reentrancy and access_control, 5 contract folds and 10 node folds.
- H1: 60 accepted fits = 8 reused Stage G fold0 + 52 fresh fits.
- H2: 30 E3a fits = 4 reused Stage G fold0 + 26 fresh fits; NOT authorized here.
- paper_kfold, seed1 and existing per-fold seed derivation; 50-epoch ceiling.
- All numerical settings are copied and verified from the frozen Stage G / Stage C configs.
- Strict minimum validation loss selects best; last reported independently.
- CV validation: the same validation fold selects and scores checkpoints.
- Node metrics remain HCG-node metrics, not deduplicated source-line scores.

Preparation creates fresh E2 -> fresh E3a -> fresh E3b chains for all 30 folds on CPU.
For fold0 it verifies identical tensor digests/support/supervision and reuses Stage G;
for other folds it saves all three untrained states, including E3a for later H2.
Models are trained one at a time from their sealed state and fixed fit RNG.
No trained checkpoint, including smoke checkpoints, initializes a new fit.

## Commands (existing mando environment; development worktree)

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.DFG.experiments.e23_cv.control verify
python -B -m scripts.DFG.experiments.e23_cv.control run
python -B -m scripts.DFG.experiments.e23_cv.control summarize
~~~

Default output:
scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/

Do not repeat prepare or seal on this batch. They are immutable setup operations.
run revalidates and reuses success; failed/partial attempts block automatic continuation.
After investigating a failure, an explicitly authorized retry uses:
--retry reentrancy_author_contract/fold_1/E2 (replace with the exact failed job).
It starts that entire model fit again, not an epoch resume or new-seed repetition.
Other attempts remain intact; multiple successful attempts for one job are rejected.

Two flock locks cover the whole controller; the worker checks for existing GPU compute
processes before using CUDA. OOM/execution/nonfinite/checkpoint failures stop the batch.
No model shrinkage, graph edits, CPU fallback or automatic retry.

## Outputs and interpretation

plan.json / plan.seal.json bind source/input/init/config identities.
h2_plan.json is separately sealed with execution_authorized=false.
fold0_reuse_audit.json records exact source receipt and initial tensor checks.
Every fit has best/last, history, predictions, support/gradient/resource audit and receipt.
summary.csv and last_summary.csv contain per-fold results.
fold_statistics.csv uses equally weighted fold means and sample standard deviations.
paired_deltas.csv and paired_statistics.csv describe E3b minus E2 in percentage points.
pooled_oof.csv pools validation predictions and is explicitly separate from fold means.
error_changes.csv includes probability changes and discrete corrected/regressed cases.
Original E0/E1 results are independently verified from their archived receipts:
baseline_* and historical_baseline_deltas.csv are historical same-fold comparisons.
Their old initialization algorithm is not silently treated as the new paired initialization.
H1_RESULT_REPORT.md is written only after all 60 accepted results are verified.
H2_EXECUTION_PLAN.md reserves the complete E3a ablation; H1 does not launch it.

Runtime source hashes cover this entire Python directory. Do not edit code during a run.
No DDG, HGT, tokenizer, labels, graph, partition or original training-script edits.
