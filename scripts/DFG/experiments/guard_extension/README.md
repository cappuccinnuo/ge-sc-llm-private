# Author HCG + DDG + guard control dependence

This sidecar adds `CONTROL_DEPENDENCE` to the **already enhanced and frozen**
`overall_cv_v1` HCG_DDG graph. It does not replace DDG with a separate alternative.
Original HCG nodes, attributes, inside_token features, labels, CFG/CG and existing
DDG edges remain unchanged. The original HGT classifier forward is inherited.

## Versions and experiment matrix

- `HCG`: released author CFG+CG, 30 archived fits, read-only reuse.
- `HCG_DDG`: current four-relation DDG, 30 archived fits, read-only reuse.
- `HCG_DDG_GUARD`: the same HCG_DDG plus forward CONTROL_DEPENDENCE, 30 new fits.
- Two cohorts: reentrancy and access_control; contract 5 folds, node 10 folds.
- `paper_kfold`; same validation selects best and scores it: **CV validation**.
- Node metric unit remains the HCG node, not deduplicated source lines.
- Same frozen file lists, fit seeds, labels, features, task-specific LR and schedule,
  maximum 50 epochs, patience/delta and strict minimum validation loss selection.

## Minimum interface changes

`model.py` clones the existing constructor function with local graph-adapter
handlers. Original numerical constructor statements, feature conversion and HGT
layer implementations are unchanged. All five enhancement relations are forward
only; ordinary CFG/CG retains its old reflection behavior. No global monkeypatch
is performed and no parameters are created while scoring.

`prepare.py` loads the original saved HCG_DDG **untrained** state after checking
file hash, tensor hash, identity, optimizer_steps=0, graph and pairing identity.
It copies every shared parameter by node type/canonical relation, initializes
only CONTROL_DEPENDENCE slices deterministically, and verifies exact shared
semantic digests. It never loads best/last or regenerates an assumed-equivalent
historical random initialization. All constructors run on CPU.

`training.py` borrows the exact old epoch-loop and resource-wrapper function code.
Only checkpoint binding and relation-gradient auditing handlers differ.
`worker.py` borrows the old worker code and adds forward-relation metadata.
No optimizer, scheduler, supervision, feature, pooling or model calculations change.

`archive.py` verifies old plan/seal, all **recorded** runtime/input hashes and 60
complete-fit receipts. It does not compare an expanded directory listing to the
old snapshot, and does not rewrite an old seal. A changed old computation file
fails. New sidecar files are separately sealed in the new plan. HEAD is recorded
as provenance, not accepted as a substitute for runtime and input hashes.

## Commands (WSL mando environment)

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
conda activate mando
export PYTHONDONTWRITEBYTECODE=1
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64

# Read-only acceptance of the 60 archived baseline fits.
python -B -m scripts.DFG.experiments.guard_extension.control archive

# Immutable new graph build; default output must not already exist.
python -B -m scripts.DFG.experiments.guard_extension.build

# CPU only: 30 saved-initial extensions, task manifests and new plan/seal.
python -B -m scripts.DFG.experiments.guard_extension.control prepare

# First four fixed fold0 fits. These are formal fits, not separate smoke scores.
python -B -m scripts.DFG.experiments.guard_extension.control run --fold0
python -B -m scripts.DFG.experiments.guard_extension.control verify --fold0

# After the fold0 correctness/resource gate: reuse those four, run remaining 26.
python -B -m scripts.DFG.experiments.guard_extension.control run
python -B -m scripts.DFG.experiments.guard_extension.control verify
python -B -m scripts.DFG.experiments.guard_extension.control summarize
```

The default batch is
`scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/`.
`--output` and `--build-manifest` are real supported options. `prepare` refuses
existing prepared/plan outputs. Do not modify production Python after sealing.

No separate smoke suite is required: the first formal fold is the resource and
numeric gate. GPU execution is serial, one candidate per subprocess. Each fit
logs per epoch to `runs/<task>/fold_<n>/HCG_DDG_GUARD/attempt_<nnn>.log`:

```bash
tail -F scripts/DFG/experiments/artifacts/paper_kfold/guard_extension_v1/runs/reentrancy_author_contract/fold_0/HCG_DDG_GUARD/attempt_001.log
```

OOM/nonfinite/input/checkpoint failures retain the attempt and stop. There is no
CPU fallback, reduction in graph/model size or automatic retry. After diagnosis,
an explicit whole-fit retry from the same sealed initial can be requested:
`control run --fold0 --retry reentrancy_author_contract/fold_0/HCG_DDG_GUARD`.
This is not epoch resume or another seed. Successful receipts are always reused.
Four-fold acceptance is independent of whether F1 increases.

## Reports and limits

The report independently recomputes labels/metrics from file and original-node
identity. It emits best and last separately, equal-fold mean and sample standard
deviation, three paired contrasts, pooled OOF, prediction/probability changes,
source-SHA-bound file errors, relation train/val support and gradients, resources,
parameters and run times. Missing, duplicate or mixed-role predictions fail.
Historical result directories are never rewritten. OOF is still not independent
test evidence. Extra relation parameters and changed optimization are part of the
intervention; score changes cannot be attributed solely to dependency semantics.

## Tests

```bash
python -B -m pytest scripts/DFG/experiments/guard_extension/tests -q -p no:cacheprovider
```

Synthetic interface tests check 30-job identity, archived-file integrity,
direction and parallel relations, exact old forward alignment when no guard is
present, common initialization, registered val-only relation behavior, mask/file
supervision, rejection of schema/feature/label corruption, actual two-epoch CPU
HGT fits, best/last reload, explicit failure retry, and independent three-version
summary recomputation. They are not Solidity compiler or semantic-oracle tests;
those live under `scripts/DFG/control_dependency/tests/`.

## Completed batch (2026-10-20, Codex)

All 30 candidate fits completed (attempt_001 only; no failures, retries or OOM),
with 60 archived baseline fits reused read-only. The complete three-variant
comparison is in [RESULT_REPORT.md](../artifacts/paper_kfold/guard_extension_v1/RESULT_REPORT.md)
and [RESULT_TABLES.md](../artifacts/paper_kfold/guard_extension_v1/RESULT_TABLES.md).
The two node-task best BF1 gains over HCG_DDG are only +0.0183 and +0.0284
percentage points; contract-task best predictions are unchanged. This is not
stable-improvement evidence. All scores are CV validation.

`prediction_changes.csv` is a sparse changes table, not the population; use
`oof_predictions.csv` for complete identity-aligned scoring. The final auxiliary
`analysis_summary.json` includes zero-delta samples in its probability denominator.

A read-only review found a nested address-receiver call-binding boundary. The
only two matching functions in this fixed batch already fell back with zero new
facts; supported functions are unaffected. See `readonly_receiver_review.json`.
This remains a next-version correctness item before broader use, not a reason
to silently change this batch's sealed computation. No Solidity compilation was
performed. Do not describe the implementation as a complete Solidity analysis.
