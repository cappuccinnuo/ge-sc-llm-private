# Prompt 8D: name and token-position diagnostics

This directory reads the frozen Prompt 8/8C results. DDG, HGT, tokenizer recipe,
author targets, historical folds and checkpoints remain unchanged.

The approved matrix uses the same 100 best node checkpoints in three modes:

- B_full: all marker names renamed with token lengths and positions preserved.
- B_matched: the available marker-name subset matched by unique-name count and
  isolated-token-length histogram.
- C_matched: the corresponding ordinary user-name subset.

Full matching is impossible in all 80 SolidiFI instances; the user approved
300 serial inference jobs. Ten AC files have empty matched subsets and remain
unchanged in the matrix. Counts of occurrences and affected nodes are not
matched; the report exports both rather than assuming equal exposure.

Deterministic candidate names avoid file-level collisions. Strings/comments
and ordinary-control exclusions are respected. Checks use untruncated node
token lengths, edited token positions and all unedited token IDs. Features
retain the original 512 truncation/padding recipe. This is a token-feature
diagnostic, not compilation validation or deployed-accuracy estimation.

## Recorded commands

Run in the existing mando WSL environment:

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json
OLD=scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1
OUT=scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1

python -B -m scripts.DFG.dfg_v2.diagnostics8d.stratification \
  --plan "$PLAN" --frozen-root "$OLD" --output "$OUT/A_v2"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.line_provenance \
  --plan "$PLAN" --frozen-root "$OLD" --output "$OUT/D"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.keyword_baselines \
  --plan "$PLAN" --frozen-root "$OLD" --scope-path "$OUT/A_v2/stratification.json" \
  --output "$OUT/E"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.renaming \
  --plan "$PLAN" --out "$OUT/renaming_v6"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.prepared \
  --plan "$PLAN" --bundles "$OUT/renaming_v6/preflight_summary.json" --out "$OUT/BC_prepared"
python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference \
  --plan "$PLAN" --task reentrancy_node --fold 0 --profile G0 \
  --gate-only --out "$OUT/current_identity_gate.json"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.inference_batch prepare \
  --plan "$PLAN" --prepared "$OUT/BC_prepared/manifest.json" --old-root "$OLD" \
  --approval "$OUT/user_decisions.json" --out "$OUT/BC_run"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.inference_batch execute --out "$OUT/BC_run"
python -B -m scripts.DFG.dfg_v2.diagnostics8d.inference_summary \
  --execution-plan "$OUT/BC_run/execution_plan.json" --old-root "$OLD" \
  --output "$OUT/BC_run/summary"
```

Outputs already exist after this run; preparation refuses overwriting them.
Before preparation, the current unmodified GPU gate must pass and be saved as
current_identity_gate.json. It uses diagnostics8c.inference gate-only on
reentrancy_node/fold0/G0 and checks archived probabilities and argmax bitwise.
The actual command is recorded in the artifacts.

Execution uses a fresh GPU process per job, stops on errors, preserves failed
logs, and never automatically retries or switches to CPU. Only verified
successes are reusable. Do not edit the four sealed worker files during a run.

## Evidence and limits

A stratifies existing idN results by exact AST ownership. D compares attached
annotation line lists against pinned CSV mappings and saved node endpoints.
E exports no-learning keyword baselines under orig/C1/C2 and by source cohort.
F is preparation-only; see ../benchmark_v2/README.md.

The final summary requires all 300 receipts. Prediction matching uses task,
fold, file, source SHA and original node identity. Equal nonempty-fold means
and pooled OOF are separate. Outputs include BF1/P/R, positive/negative flips,
probability changes and actual lexical/node exposure.

B_full versus old idN changes replacement token values as well as positional
behavior; it cannot isolate a pure causal position contribution.
B_matched versus C_matched matches unique-name count and length, not occurrence
frequency/context. C1/C2 are diagnostic assumptions, not established truth.
Inference-only results do not predict performance after neutralized retraining.

## Tests and stop point

```bash
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

The separate identity-feature proof runs one CPU epoch per branch, two
acceptance optimizer updates, zero formal fits. B/C has zero optimizer steps.
The original scheduler-instance comparison failure is preserved; the accepted
review compares its actual function and every numeric state without retraining.

No grouped benchmark fit is authorized. L-orig/L-audit, training seeds and
execution location require user selection and a tested execution entry.
Final experiments are intended for a server with sufficient VRAM; 4GB is the
current local limitation. Do not mix local and server fits in one batch.


## Unresolved naming-policy issue before execution

The requested 8C feature rule replaces only marker identifiers with id0, id1,
and so on, while ordinary user names remain unchanged. A newly trained model
can potentially learn that replacement-name family as an injection cue.
Therefore the prepared F plan is a candidate benchmark, not evidence that name
leakage has been eliminated. Its existing seal is preserved and training stays
unauthorized. The separate F_naming_risk evidence audits this limitation without
model training. A revised naming policy (for example consistent treatment of
all identifiable user names) must first be discussed and approved, then bound
to a new plan; it is not implemented silently here.
