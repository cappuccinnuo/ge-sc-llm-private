> **Archive note, 2026-10-21 (Codex):** This completed batch remains sealed under its original runtime. Later sidecar files make the historical discovery-based `control verify` unsuitable for archival review. Use `python -B -m scripts.DFG.integration.archive --batch scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1 --output <new-outside-batch.json>` instead. It checks every recorded old runtime/input identity and result receipt; it does not change the seal or authorize new training. Historical execution instructions below remain for provenance.
# Original HCG versus frozen overall DDG

This independent experiment compares HCG (the prepared author CFG+CG without our DDG) with HCG_DDG (the same graph with the frozen Stage K positive relations). Both use the existing corrected numerical trainer; old training defects are not restored.

The matrix is reentrancy/access_control, contract 5 folds/node 10 folds, two variants: 60 fresh formal fits. HCG node IDs, labels, token features and CFG/CG edges are identical within each pair. Each pair starts from independently stored, semantically equal common untrained parameters. Enhanced-only relation parameters are deterministically initialized. Prior Stage K B1 is only a historical reference because that pair was anchored to E3b.

Protocol: paper_kfold, full fixed graph forward, original frozen file splits, train supervision, validation loss for early stopping and strict-minimum-loss best selection, then scoring on the same validation fold. Results are CV validation, not independent test. Node metrics count HCG nodes, not deduplicated source lines. Maximum 50 epochs, patience 7, delta 0.001; each task keeps its recorded learning-rate/scheduler configuration. best and last are reported separately.

The entry only schedules and binds experiments. It imports the existing model and clones existing training function bodies with a local checkpoint binding; it does not change HGT, tokenizer, DDG construction, labels, folds or numerical fit rules.

## Execution in the existing WSL mando environment

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.DFG.experiments.overall_cv.control prepare
python -u -B -m scripts.DFG.experiments.overall_cv.control run --first-pair
python -u -B -m scripts.DFG.experiments.overall_cv.control run
python -B -m scripts.DFG.experiments.overall_cv.control verify
python -B -m scripts.DFG.experiments.overall_cv.control summarize
```

Default output: scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/. Preparation is immutable and cannot be repeated in an existing prepared directory. Do not repeat prepare after the plan exists. run verifies and reuses successful results, never resumes from a trained epoch checkpoint. A previous failed attempt blocks progress until diagnosed and explicitly retried using --retry task_id/fold_N/variant. Old attempts remain. CUDA errors stop; no CPU fallback, graph shrinking or parameter changes. A process lock serializes workers. First paired fold and complete-task checks gate progression.

To inspect live epoch output, tail the current runs/TASK/fold_N/VARIANT/attempt_001.log. Each fit writes history.jsonl, best.pt, last.pt, exported predictions, resource/gradient audits and a receipt. Final tables include per-fold metrics, equal-fold means/sample standard deviations, paired changes, pooled OOF, identity-aligned error changes, source SHA, support, memory and elapsed time. Exact node-code overlap is descriptive only.

## Verification

```bash
python -B -m pytest scripts/DFG/experiments/overall_cv/tests -q
```

New tests cover immutable inputs, baseline relation registration, common semantic initialization, original frozen splits, direct numerical-loop reuse, CPU node/contract gradient and checkpoint checks, corrupt bindings, prediction identities, and failure/reuse scheduling. Tests do not train formal models. The first test run exposed a missing category in a synthetic fixture; the fixture was fixed without altering production labels.

Current phase intentionally excludes new relations, algorithms, seven-category expansion, additional seeds, independent holdout evaluation and per-component ablations. Changes in scores include new relation parameters/aggregation/optimization, and cannot be attributed exclusively to dependence semantics.

## Archive and epoch conventions

The current execution/verification entry binds the exact HEAD and recorded runtime hashes. Do not rewrite the plan or seal after a future archive commit. A post-commit read-only archive verifier is outside this batch. CSV best_epoch/last_epoch use the existing zero-based convention; epoch logs display one-based numbers.
