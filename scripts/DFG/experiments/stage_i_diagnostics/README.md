# Stage I: capability inventory and frozen-checkpoint state-message diagnostics

This side module implements the authorized next steps 1 and 2. It does not train,
construct new graph relations, change DDG semantics, or implement modifiers.

- `CAPABILITIES.md`: original design versus current implemented capabilities; original E numbering is not current Stage G/H numbering.
- `ENTRY_POINTS.md` / `entry_validation.py`: explicit routing checks. These do not intercept commands run directly through legacy scripts.
- `modifier_scope.md`: why a future restricted modifier implementation is a separate correctness task.
- `evidence.py`: source/semantic sidecar/projection/HCG context/archived prediction evidence.
- `interventions.py`: reversible per-instance canonical message zeroing using the existing HGT computation.
- `common.py` / `run.py`: sealed read-only replay, one CUDA worker at a time, accepted checkpoint and identity binding.
- `aggregate.py`: independently recomputed metrics, fold means/SD, pooled CV validation, file and prediction changes.

## Frozen scope and interpretation

The matrix is all four author-label tasks, E3a and E3b, all 5 contract folds and 10
node folds: 60 accepted models, each best and last (120 checkpoint replays).
No optimizer is created, no backward is called, and no model is retrained.
The six conditions are normal N, Z_D (STATE_DEF_USE), Z_S (STATE_ACCESS_ORDER),
Z_C (EXTERNAL_CALL_BEFORE_STATE_WRITE), Z_SC (both order relations), and Z_ALL
(all three). The original scalar DATA_DEF_USE and CFG/CG messages are retained.
A condition zeroes selected canonical messages before cross-relation mean;
it does not remove graph edges, schema, parameters, or mean denominator.
Absent relations must be exact no-ops. Normal wrapper and restored outputs must
be bitwise equal to native. Archived class predictions and metrics must match;
archived probability differences retain the previous diagnostic tolerances.
All graph/input/label/schema hashes and parameter tensors/objects are checked.

This tests reliance on messages at already-trained weights. It does not identify
pure semantic causal contributions, emulate retraining without a relation, or
remove the effects of schema/parameter initialization and optimization history.
The scoring population remains CV validation, selected on the same fold. Node
metrics count HCG nodes, not deduplicated source lines. Pooled results are not an
independent test. No multi-seed or seven-category claims are made.

## Output provenance

- `../artifacts/paper_kfold/stage_i_v1/static/`: immutable static evidence.
- `stage_i_v1/plan*`: first pre-execution seal; no model replay.
- `stage_i_v2/plan*` and `fold0_replay.log`: preserved pre-model Path API failure.
- `stage_i_v3/`: actual fixed-checkpoint replay and summary.

The new plans never replace old G/H1/H2 seals. Stage F semantic sidecars match
its delivery manifest but that manifest was not itself in the H2 frozen-file
map. They are explicitly observed and sealed for this audit, not retroactively
certified by H2. See static/PROVENANCE_ASSURANCE.json. Graph/checkpoint inputs
remain bound to the accepted historical task manifests and receipts.

## Commands (existing WSL mando environment)

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.verify_h1_archive
python -B -m scripts.verify_h2_archive
python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/stage_i_diagnostics/tests
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v3/aggregate_stage_i.py
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v3/analyze_messages.py
python -B scripts/DFG/experiments/artifacts/paper_kfold/stage_i_v3/join_prediction_context.py
```

To resume verified replay (not training), use `run replay --output` with that
same directory. Successful jobs are verified and reused. Partial/failed output
is preserved and blocks automatic retry. No CPU fallback, shrinking, changing
hyperparameters, or closing other processes is performed. A process lock and
existing CUDA-process precheck reject overlapping workers; Windows graphics
programs may still share the card, so actual memory samples are reported.

`run prepare --output <new-directory>` is only for an explicitly new diagnostic
batch. Do not call prepare over an existing plan. The default directory is the
original v1 name for compatibility with the preserved static artifact; always
supply the actual v3 path in the commands above.

The sealed source aggregate.py retained the original cv_validation role and rejects the new diagnostic role. It is preserved for provenance. The artifact-only aggregate_stage_i.py corrects that role binding, with a source SHA and unified diff; use the command above. This changes no replay, inputs, or metric formulas. analyze_messages.py and join_prediction_context.py are read-only postprocessors.
