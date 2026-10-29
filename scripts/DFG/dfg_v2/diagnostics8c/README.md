# Prompt 8C diagnostics

These tools read the frozen Prompt 8 batch. They do not retrain models, change labels, regenerate graphs, select a new profile, or authorize the placebo fits.

Run from the repository root in the existing `mando` environment:

```bash
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
PLAN=scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json
OUT=scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1
```

The existing output directories are exclusive evidence, not destinations to overwrite. Use a new output directory for a separately requested audit. All original plans, seals, graphs, labels, features, folds, checkpoints and predictions remain immutable.

## Components

- `common.py`: full read-only verification of all 150 receipts, best/last checkpoint digests and prediction identities. The historical runtime context first checks every recorded computation file and the actual approved amendment; new diagnostic modules are outside that historical inventory. It is never used to authorize training.
- `labels.py`: sequential original-to-cleaned line mapping, candidate label-rule reconstruction, missing-positive/spill evidence, public comment evidence, and source/CSV provenance. C1 and C2 are diagnostic views, not corrections to the frozen data or verified ground truth.
- `scoring.py`: independently recomputes metrics from existing predictions. Node fits have orig/C1/C2; contract fits use orig only. Non-SolidiFI scores are pooled; Wilson intervals apply only to precision/recall and are descriptive.
- `structure.py`: exact AST/HCG modifier correspondence, actual graph paths/isolation, and canonical relation counts in model inputs.
- `duplicates.py`: exact and near-source duplicates and their frozen fold positions. It does not change folds.
- `inference.py`: one CUDA best-checkpoint forward. Identifier intervention affects only outer-test original HCG node feature rows in memory; strings/comments and all other text are preserved. The file-level renaming order follows lexical first occurrence in the bound original source and skips existing idN names. Auxiliary env_source rows stay unchanged.
- `inference_batch.py`: freezes and executes 100 serial, fresh-process, inference-only jobs. The initial unmodified gate requires exact archived argmax and float32 positive probabilities (raw logits were not archived). A development probe is reusable only after every final rewritten text SHA is identical.
- `inference_summary.py`: aligns all 100 intervention results by task/file/original-node/source identity and scores orig/C1 without refitting.
- `placebo.py`: prepares 20 future G0P fits with `execution_authorized=false`. G0P keeps G0 nodes/features and adds zero-edge relations for original target types. The numerical proof is a same-input single-layer mean-denominator proof, not a claim of fixed scaling of final logits.

## Actual commands and interfaces

```bash
python -B -m scripts.DFG.dfg_v2.diagnostics8c.common --plan "$PLAN" --out "$OUT/verification_v2"

python -B -m scripts.DFG.dfg_v2.diagnostics8c.scoring \
  --plan "$PLAN" --views "$OUT/A/node_views.json" \
  --verification "$OUT/verification_v2/verification.json" --output "$OUT/B"

python -B -m scripts.DFG.dfg_v2.diagnostics8c.duplicates --plan "$PLAN" --output "$OUT/F"

python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference \
  --plan "$PLAN" --task reentrancy_node --fold 0 --profile G0 \
  --gate-only --out "$OUT/D/gate.json"

# The fixed-batch prepare command audits this first intervention before reuse.
python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference \
  --plan "$PLAN" --task reentrancy_node --fold 0 --profile G0 \
  --gate "$OUT/D/gate.json" --out "$OUT/D/jobs/reentrancy_node_0_G0.json"

python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference_batch prepare --plan "$PLAN" --out "$OUT/D"
python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference_batch execute --out "$OUT/D"
```

A/C/E were invoked through their Python APIs:
`labels.run_audit(repo, plan_path, output_dir, solidifi_repo)`,
`structure.run_structure(plan_path, output_dir)`,
`placebo.prepare_placebo(plan_path, structure_dir, output_dir)`.
The pinned CSV repository is the existing
`/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark`;
its working CSV bytes are checked against Git commit
`4b0573e1b3f7031396de6f48f7f3e7380222ad3a`.

After all 100 workers complete:

```bash
python -B -m scripts.DFG.dfg_v2.diagnostics8c.inference_summary \
  --plan "$PLAN" --views "$OUT/A/node_views.json" --output-dir-D "$OUT/D"
```

The independent reviewer script is run only as a comparison reference after A, never as the implementation. Its differing handling of `//*****` is preserved and explained in A's comparison evidence.

## Interpretation boundaries

Renaming only at inference measures sensitivity to vocabulary removal and distribution shift; it does not prove that every observed performance difference is caused by leakage. C1/C2, source similarity and structural paths do not establish true vulnerability semantics. Source-order overlap and missing labels do not identify the author's unpublished conversion algorithm.

No new hypothesis-test family, selection change, seed, graph relation or training run is introduced here. E remains at the authorization boundary. Final server experiments are a future, separately bound batch; the local RTX3050 VRAM restriction is not a requirement to reduce the final model.
