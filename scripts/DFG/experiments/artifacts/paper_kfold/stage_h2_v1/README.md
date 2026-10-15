# Stage H2 completed batch

26 new E3a fits, 4 audited Stage G fold0 references, 30 complete E3a results.
Together with the immutable H1 E2/E3b results: 90 formal results.
All metrics are CV validation, with HCG nodes as the node-task unit.
No additional training is needed. E2/E3b were not retrained.

Start with H2_RESULT_REPORT.md and E2_E3_COMPLETE_ABLATION_REPORT.md.
The main results use minimum-validation-loss best; last is auxiliary.
- summary.csv / last_summary.csv: 30 E3a rows each.
- three_variant_best.csv / three_variant_last.csv: 90 rows each.
- paired_deltas.csv / paired_statistics.csv: three contrasts, best/last.
- pooled_oof.csv: pooled metrics, separate from equal-fold means.
- error_changes.csv: probability and class changes, source SHA and node identity.
- file_error_analysis.csv: changes per source file and cohort.
- enhancement_support.csv / gradient_support_detail.csv: support and gradients.
- resource_folds.csv: all 90 fit resources; G/H1 historical fits included.
- plan.json / plan.seal.json: independent H2 authorization and immutable bindings.
- archive_audit.json / fold0_reuse_audit.json: historical and initialization checks.
- integration_tests.log/json: 71 tests passed, four existing DGL warnings.
- protected_after.json / delivery_manifest.json: final protection and delivery hashes.

Actual commands, run in the existing mando environment:
```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH=$PWD
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m scripts.DFG.experiments.e23_h2.control verify
python -B -m scripts.DFG.experiments.e23_h2.control summarize
```
The completed run used `python -u -B -m scripts.DFG.experiments.e23_h2.control run`.
Do not seal this batch again, alter old plans, or restart completed fits.
The controller requires the sealed HEAD. Future Git archival requires a separate
read-only archival verification; never rewrite historical seals to match a new HEAD.

Reports may be rendered from verified exports using this batch's render_reports.py.
interpretation.md is the reviewed analytical supplement; neither file participates
in training computation. H1/G reports and their outputs were not overwritten.
History E0/E1 tables are separate, because their initialization version differs.

No extra seeds, classes, relations, models, or independent-test evaluation executed.
