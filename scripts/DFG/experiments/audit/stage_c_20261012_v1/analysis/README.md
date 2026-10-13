# Stage C read-only reporting

This directory is outside the frozen runtime module glob. Only this directory was added.
The reporter uses Python standard-library code; it imports no torch, DGL or model module.

## Run after any task has been fully accepted

From the project root in the existing mando environment:

~~~bash
python -B scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/report_stage_c.py \
  --run scripts/DFG/experiments/artifacts/paper_kfold/formal_20261012_v1_stage_c \
  --output scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/reports/final_v1
~~~

Choose a new output directory for each report. Existing outputs are never overwritten.
Outputs must be outside the input run directory. Pending tasks do not contribute partial means.

## Evidence and outputs

- report.json: provenance, complete/pending tasks, all numerical statistics and available attempt history.
- REPORT.md: four-metric fold results, paired deltas, means/sample standard deviations, direction counts, errors and telemetry.
- fold_metrics.csv: each fold, E0/E1, best/last, four metrics and paired percentage-point deltas.
- metric_summary.csv: equal-weight fold means, sample std (ddof=1), and per-metric improved/tied/declined counts.
- fit_telemetry.csv: one row per fit, never duplicated for best/last; epochs, time, DDG support/gradient, parameters and GPU peaks.
- error_transitions.csv / changed_predictions.csv: correctness transitions, FP/FN changes and exact identities.
- attempts.csv: discovered attempt identities, current status and available log evidence.

Plan seal, frozen file hashes, accepted receipt hashes and each accepted output-tree fingerprint
must match. Prediction metrics and paired error transitions are independently recomputed.
Checkpoint tensor replay itself was performed by the original acceptance stage; this script
verifies its immutable receipt and artifact bytes, and does not load checkpoint tensors.
Unknown historical unaccepted attempts remain unknown when the old state was overwritten.
No missing failure code is fabricated from an unfinished result JSON.

All results are CV validation. Best is selected by minimum validation loss; last is auxiliary.
Node metrics count HCG nodes, not unique source lines. GPU peaks include the process with both
models resident; they are not an isolated-model or whole-card measurement. Fit time includes
validation, checkpoint IO and reload scoring. Gradient sums depend on training length and
parameter changes may include weight decay. Tie tolerance is 1e-10 percentage points.

## Tests

~~~bash
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/test_report_stage_c.py \
  --basetemp scripts/DFG/experiments/audit/stage_c_20261012_v1/analysis/test_tmp_manual
~~~

Use a new basetemp name to retain earlier test evidence. Tests use small synthetic JSON fixtures;
synthetic best.pt bytes only exercise integrity checks, not model execution. No GPU is accessed.
The real status_v1 report also completed successfully against the running batch; at that
snapshot all four tasks were pending, so no task means were published.
