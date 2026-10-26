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
