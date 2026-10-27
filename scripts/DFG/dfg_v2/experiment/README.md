# DFG v2 Prompt 7 experiments

This is the v2-only training adapter. Frozen analyzers, graphs, tokenizer, HGT,
old training scripts, labels and fold files are not changed.

## Roles and numerical behavior

The original fixed full task graph is forwarded. Only `inner_train` file
batches/node masks supervise optimizer updates. Only `inner_val` loss selects
best and drives early stopping. Outer-test supervision is first accessed after
fitting. File components have no cross-file edges. Auxiliary env_source rows
are excluded from supervision, predictions, metrics and contract pooling.

The copied epoch engine comes from `experiments/paper_run.py::fit_variant`
(SHA recorded in trainer.py): Adam, unweighted cross entropy, one optimizer
and OneCycle step per epoch, then eval validation. Strict minimum validation
loss saves best; patience uses the separate delta reference. Per-task learning
rates remain those of the SHA-bound historical task manifests, not a shared
override. Production uses 50 scheduled/maximum epochs, patience 7, delta .001.
Generic `ddg-controlled-v1` serialization is wrapped with nested v2 binding.

This differs from paper_kfold, whose validation fold both selected and scored
the checkpoint. Historical paper-CV F1 is not a paired nested outer-test baseline.
Full fixed-graph/schema registration remains visible for every partition;
heldout labels do not enter optimization or checkpoint selection.

## Initialization

Seed 1 preserves constructor `10000 + fold + (1000 if contract else 0)`;
later seeds add `100000 * (seed - 1)`. Fit seed is constructor + 1000000.
Each model starts from a separately saved untrained state.

The user approved an explicit resolution of a specification conflict:
G0-shared parameters are exactly equal by semantic node/canonical identity.
New relation rows use semantic independent draws scaled by each receiving
profile's whole-bank Xavier bound. A new canonical shared by enhanced profiles
therefore need not have equal raw tensors when the banks have different sizes.
New env_source parameters are reproducible and do not depend on family order.
The initializer cannot detect arbitrary mislabeled external trained weights;
the runner supplies constructor provenance, zero steps, file and tensor hashes.

## Commands

Use WSL's existing mando environment. All output directories must be new.

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.dfg_v2.experiment.run plan \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --profiles G0,G3R --seeds 1 --folds 0 \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt7_pilot_NEW

python -u -B -m scripts.DFG.dfg_v2.experiment.run execute \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_pilot_NEW/plan.json \
  --only reentrancy_contract/0/1/G3R
~~~

Prompt 7 requires checking that first probe, including whole-card minimum free
memory >=100 MiB, before other GPU jobs. Its successful fit counts as one of
eight, not an extra warm-start model. An OOM, memory gate or integrity failure
stops execution. Do not lower dimensions, remove edges or fall back to CPU.
After diagnosis an explicit `--retry` starts the complete failed fit again from
the same saved initial state; it is not epoch resumption. Successful receipts
are independently verified and reused.

~~~bash
python -B -m scripts.DFG.dfg_v2.experiment.run verify --plan <batch>/plan.json
python -B -m scripts.DFG.dfg_v2.experiment.run select --plan <batch>/plan.json
python -B -m scripts.DFG.dfg_v2.experiment.run summarize --plan <batch>/plan.json
~~~

Selection reads only frozen-identity-verified inner-validation predictions.
The summary refuses to run before selection is sealed. Incomplete candidate/
fold matrices are pilot diagnostics; they cannot trigger extra seeds. The
Prompt 8 full statistical report is not implemented by this small pilot summary.

Production CLI cannot select CPU/test-mode configuration. CPU end-to-end tests
use a separately sealed, explicitly synthetic 20-file fixture and 2 epochs.

## Verification and memory

Each successful attempt has best/last checkpoint payloads and sidecars,
history, effective configuration, input fingerprint, binding, predictions,
resource/gradient audit and receipt hashes. Verification independently checks
prediction identities/truth against frozen data and checkpoint payload against
sidecar, weights digest, binding, selected epochs and exact reload assertions.
Receipt reuse does not train again. Failed attempts and reasons remain.

Whole-card memory is sampled at 0.5-second intervals and at gate boundaries.
This is an observed minimum, not a guarantee that sub-interval dips were seen.
Failure to obtain a current reading stops rather than reusing stale data.
The inherited checkpoint loader maps its optimizer payload to the device;
that transient memory remains measured without changing its numerical path.

## Engine checks

`experiment.equivalence` replays the historical R contract fold0 paper split
with the exact saved untrained initial state. It is an explicit numerical
diagnostic, not a nested result. Old/new CPU engines each execute three epochs;
the new GPU engine executes three epochs for comparison with the historical
GPU history, keeping the 50-step schedule. The user approved counting these
three short runs separately from the eight pilot fits and performing the G3R
memory gate before the GPU historical replay.

~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.equivalence \
  --manifest scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/prepared/reentrancy_author_contract/fold_0/task.json \
  --output <NEW_CPU_DIAGNOSTIC_DIRECTORY> --device cpu
~~~

GPU equivalence additionally uses `--device cuda:0 --historical-history`
pointing to the receipt-verified historical `HCG/attempt_001/history.jsonl`.
CPU loss tolerance is 1e-6; GPU historical tolerance is 1e-4. Do not compare a
nested split's first epochs to paper-split history.

No standalone F1 improvement conclusion is supported by these four fold0 tasks.
No Prompt 8 matrix, new seed, or additional vulnerability category runs here.


## Prompt 7b: shared projection implementation and acceptance

`make_model(..., layer_impl="original")` retains the old default.
`layer_impl="shared_projection"` selects the optional shared per-node-type
K/V/Q implementation; both `mean` and `nonempty_mean` reducers are supported.
Constructors, parameter keys/shapes and construction RNG consumption are
unchanged. Backward accumulation order is different. This is **not** a claim
that multi-epoch optimization is bitwise identical.

The implementation identity is bound to plans, effective configs, untrained
states, initialization records, checkpoints and results. Restoring a checkpoint
under another implementation is rejected even when initial tensor digests match.
A missing historical field means `original`; old artifacts are not rewritten.

New numerical diagnostics use `experiment.projection_validation`. All CPU cases
must pass before GPU numerical comparisons, the memory probe or pilot training.
The user approved this precise gradient criterion before real-data execution:

```
max_abs_gradient_difference <= 1e-8 + 1e-5 * max(max_abs_old, max_abs_new)
```

Tensor-relative and elementwise-relative errors are both retained. The absolute
term covers near-zero gradient cancellation; it does not change either the exact
forward requirement or the CPU 3-epoch loss tolerance of 1e-6. The planned six
CPU pairs (twelve three-epoch diagnostic fits) are separate from the eight pilot
fits. This run stopped after four trajectory pairs and the fifth static pair;
only eight three-epoch CPU fits actually ran. See the report for failed gates.

Example CPU diagnostic (the destination must be new):

~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.projection_validation cpu-case \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt7_v1/pilot/plan.json \
  --task access_control_node --profile G0 --reducer mean \
  --output <NEW_CPU_CASE_DIRECTORY>
~~~

For an accepted future batch, plan creation accepts
`--layer-impl shared_projection`; use a new batch directory. Never retry or
reseal the original Prompt 7 plan under a different implementation. See
`../PROMPT7B_REPORT.md` for the actual gate outcome. A failed CPU trajectory gate
blocks GPU and pilot execution; the existence of this CLI is not an acceptance.
No Prompt 8 execution or F1 efficacy conclusion follows from these diagnostics.


## Prompt 8: staged full matrix (2026-10-26)

This section supersedes the pilot-only summary limitation above for new
registered Prompt 8 plans. Historical plans and resource policies are kept.

Batch 1 contains 150 new fits: four registered tasks, contract 5 folds/node
10 folds, seed 1, profiles G0/G1R/G2R/G3R/G3. Stage A contains G0/G3R (60);
stage B contains G1R/G2R/G3 (90). batch_plan freezes the entire matrix,
fresh untrained initial states, report specification and preparation authority.
The eight pilot fits are not reused. Existing numerical training, graph inputs,
features, labels, folds and initialization algorithms remain unchanged.

The new batch authorization is preparation only. Stage A must be confirmed
after reviewing the sealed plan and disk/time estimates. Stage B needs a separate
decision bound to the completed stage A interim report. The old eight-job
local_dev_v1 approval remains historical policy evidence. Separate execution
records do not modify the plan after sealing.

Preparation command (existing output is rejected):

~~~bash
python -B -m scripts.DFG.dfg_v2.experiment.run plan \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --tasks reentrancy_contract,reentrancy_node,access_control_contract,access_control_node \
  --profiles G0,G1R,G2R,G3R,G3 --seeds 1 \
  --layer-impl shared_projection --resource-policy local_dev_v1 \
  --approval-record scripts/DFG/experiments/artifacts/dfg_v2/prompt7c_v1/local_policy_approval.json \
  --authorization-record scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch_authorization.json \
  --report-spec scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/report_spec.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1
~~~

After explicit stage authorization is recorded, run:

~~~bash
python -u -B -m scripts.DFG.dfg_v2.experiment.batch execute \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json \
  --stage A --authorization-record <APPROVED_STAGE_A_JSON>
python -B -m scripts.DFG.dfg_v2.experiment.batch verify \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
python -B -m scripts.DFG.dfg_v2.experiment.batch interim \
  --plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json --stage A
~~~

Each fit runs in a fresh child process, with one GPU worker and exclusive logs.
Only verified successful fits are reused. Failures, including preflight failures
before a fit directory exists, stop the batch. After diagnosis, a new decision
must name the failed job and bind the latest failure SHA; --retry TASK/FOLD/SEED/PROFILE
restarts that fit from its original untrained state. No automatic retry or epoch
resumption is implemented. Direct run execute also enforces authorization and
registered order.

Stage authorization records use version
prompt8-stage-execution-authorization-v1, approved, stage, the exact
plan path/SHA, the ordered authorized_jobs, user_answer, and recorded_at.
Stage B additionally binds interim_receipt; an explicit retry additionally
binds retry_job and retry_evidence. No approved execution record is fabricated
during preparation.

Stage A writes reports/interim_A/REPORT_INTERIM_A.md, CSV/JSON and a receipt;
batch_records/interim_A.json binds all outputs. It reports fixed G3R vs G0,
does not select G*, and leaves four-comparison Holm adjustment pending. After
review and approval, stage B uses --stage B with its own authorization.
Then execute run verify, run select, and run summarize. Full reporting requires
sealed inner-validation-only selection; outputs are in reports/final/REPORT.md
plus CSV/JSON and linked from summary.json.

Main results use best selected by inner_val loss; last is separate. Outer-test
labels are used only after fitting, while the fixed full graph participates in
forward passes. This is not the old paper_kfold protocol or a fully inductive
unseen-graph test. Original HCG nodes determine node metrics; env_source never
counts as a prediction target.

Statistics are task-generic: equal-fold mean/sample SD, paired fold differences,
A12 across score distributions, paired bootstrap (10000, seed 0), node Wilcoxon
two-sided/zsplit and per-task four-comparison Holm; contract five-fold results
are descriptive only. Pooled OOF, source-SHA-bound sensitivity analysis, directed
canonical 1/2-hop associations, error/probability changes, support/gradients and
resources are separate tables. Blank manual reviews are reported as unfinished.
No causal contribution or independent-seed significance is inferred.

Current batch runs locally under local_dev_v1 (startup free >=3000 MiB; runtime
<100 MiB is a warning; OOM/nonfinite/integrity failures stop). Estimates are about
5.8 hours for A and 9.0 hours for B, with substantial fold/load uncertainty.
Final experiments are intended for a server with sufficient VRAM; the present
4 GiB restriction is local. Server environment verification and an entirely new
server batch remain future work; local and server results must not be mixed.

Optional reducer diagnostics, additional seeds and the other five vulnerability
categories are not authorized here. Follow ../EXTENDING.md for future task
registration, source/token checks, frozen splits and graph build; reuse the
R/AC inner-selected G* without selecting anew on each added category.
