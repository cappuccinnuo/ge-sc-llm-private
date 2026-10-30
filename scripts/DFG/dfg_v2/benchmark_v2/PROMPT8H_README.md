# Prompt 8H benchmark v2 execution

This adds a separate `dfg-v2-grouped-nested` execution path. The historical
`dfg-v2-nested` executor, original HGT/tokenizer/DFG and existing artifacts remain unchanged.

The authorized batch is `scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/`:
N-anon-s features, L-audit targets/masks, frozen grouped folds, seed 1,
local_dev_v1, 170 fits. L-audit is a diagnostic labeling view, not established ground truth.

Use the existing mando environment from the repository root:

```bash
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
conda activate mando
```

The following acceptance commands have already run. Their outputs are exclusive;
do not rerun them into existing directories or remove failure evidence:

```bash
CUDA_VISIBLE_DEVICES='' python -B -m scripts.DFG.dfg_v2.benchmark_v2.acceptance archive
CUDA_VISIBLE_DEVICES='' python -B -m scripts.DFG.dfg_v2.benchmark_v2.acceptance cpu
python -B -m scripts.DFG.dfg_v2.benchmark_v2.acceptance gpu
CUDA_VISIBLE_DEVICES='' python -B -m scripts.DFG.dfg_v2.benchmark_v2.real_acceptance
```

CPU acceptance uses `cpu_attempt2`; the first incomplete implementation attempt is retained.
GPU replay is acceptance only and cannot count toward the 170 new formal fits.
The real mask check tests direct loss gradients, retaining full graph propagation.
G0P's denominator proof is per layer at identical inputs, not a claim about constant
scaling of final logits.

The execution sequence is:

```bash
CUDA_VISIBLE_DEVICES='' python -B -m scripts.DFG.dfg_v2.benchmark_v2.initial_preparation
CUDA_VISIBLE_DEVICES='' python -B -m scripts.DFG.dfg_v2.benchmark_v2.execution prepare
python -B -m scripts.DFG.dfg_v2.benchmark_v2.execution pilots
python -B -m scripts.DFG.dfg_v2.benchmark_v2.execution all
python -B -m scripts.DFG.dfg_v2.benchmark_v2.reporting
```

Preparation creates fresh, zero-step semantic-aligned initial states and a new plan/seal.
The two complete pilot fits count toward the matrix and are reused by `all`.
Each GPU job runs in its own child process. Started/failed attempts block later jobs;
there is no automatic retry or epoch resume. Do not edit computation files after sealing.
No statistics are aggregated until the final 170-result acceptance.

Success acceptance checks checkpoint/state SHA, plan/schema/feature/label/split/initial
bindings, exact reload, the three deep-validation boundaries, source identities,
independently recomputed metrics, and resource/preflight evidence.
Prompt 8B.0's cache is reused for prior successful fits, with a live controller seal anchor.

Historical archive verification uses the exact recorded source inventory and checks actual
file hashes before calling the original amendment checks. This user-approved read-only
adapter permits new 8H files to coexist; it does not relax the historical execution entry.

Main results use best by inner validation loss and grouped outer evaluation.
All original HCG-node/original-label scores and last scores are separate auxiliaries.
Four profile-vs-G0 comparisons form the within-task Holm family; direction/placebo
comparisons are separate. Contracts and access-control nodes are descriptive.
Non-SolidiFI reports pooled counts and descriptive precision/recall Wilson intervals,
not a Wilson F1 interval or independent-node statistical evidence.

Final experiments are intended for a sufficiently provisioned server. This batch is
explicitly authorized on the local 4 GiB GPU; server deployment and extra seeds are separate.
Only disposable test basetemp files may be cleaned. Preserve plan/seals, weights,
initials, receipts, histories, failure evidence and source data.

CPU preparation uses the approved never-trained structure cache after its bitwise proof.
G0 is freshly constructed each fold; enhanced parameters are completely rewritten by
the unchanged semantic initializer. Fresh-reference partial attempts are retained.
The final plan uses prepared_attempt3; formal workers never use this cache.


Approved cache repair (2026-10-30): a separately sealed runtime_cache_fix_v1
binds the original plan and the final-resource acceptance adapter. Historical
result.json and all previous caches remain intact. Only the listed successful
first fit is reused without a new amendment field; subsequent starts bind it.
The commands `execution pilots`, `execution all`, then `reporting` resume the
approved matrix without retraining existing successes. See cache_fix_v1 proofs
and orchestration_resume_v1_status.json for the new controller state; the original
orchestration_status.json retains the historical cache failure.

Explicit interrupted-job resume: runtime_resume_v2.json binds the user request, 71 verified successes, and a single fresh retry at reentrancy_node/fold_7/seed_1/G3/attempt_002. Original attempt_001 and worker log remain at their original paths. A second interruption requires new review; automatic retry is disabled. The all/verify/reporting commands select the unique successful receipt per job, including 002. Detached orchestration is recorded in orchestration_resume_v2.command.json; live state is orchestration_resume_v2_status.json. Keep the host awake; no system power settings are changed.
