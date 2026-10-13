# Dataset A formal CV validation report

- Protocol: paper_kfold / ddg-paper-kfold-v1.
- Best: minimum validation loss. Last: auxiliary, reported separately.
- Node metrics count HCG nodes; they are not deduplicated source-line metrics.
- Metrics: percent. Delta: E1-E0 percentage points. Std: sample, ddof=1.

## reentrancy_author / contract

### best

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 84.6154 | 86.0577 | 100.0000 | 73.3333 |
| 0 | E1 | 84.6154 | 86.0577 | 100.0000 | 73.3333 |
| 0 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 1 | E0 | 100.0000 | 100.0000 | 100.0000 | 100.0000 |
| 1 | E1 | 100.0000 | 100.0000 | 100.0000 | 100.0000 |
| 1 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 2 | E0 | 96.5517 | 96.4240 | 93.3333 | 100.0000 |
| 2 | E1 | 93.3333 | 92.8205 | 87.5000 | 100.0000 |
| 2 | E1-E0 pp | -3.2184 | -3.6035 | -5.8333 | +0.0000 |
| 3 | E0 | 96.2963 | 96.4240 | 100.0000 | 92.8571 |
| 3 | E1 | 96.2963 | 96.4240 | 100.0000 | 92.8571 |
| 3 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 4 | E0 | 93.3333 | 92.8205 | 87.5000 | 100.0000 |
| 4 | E1 | 93.3333 | 92.8205 | 87.5000 | 100.0000 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 94.1593 +/- 5.8347 | 94.3452 +/- 5.2827 | 96.1667 +/- 5.6396 | 93.2381 +/- 11.5490 |
| E1 | 93.5157 +/- 5.6802 | 93.6245 +/- 5.1729 | 95.0000 +/- 6.8465 | 93.2381 +/- 11.5490 |
| E1-E0 | -0.6437 +/- 1.4393 | -0.7207 +/- 1.6115 | -1.1667 +/- 2.6087 | 0.0000 +/- 0.0000 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 0 | 4 | 1 |
| macro_f1 | 0 | 4 | 1 |
| precision | 0 | 4 | 1 |
| recall | 0 | 5 | 0 |

Error changes: both_correct=133, e0_wrong_e1_correct=0, e0_correct_e1_wrong=1, both_wrong=8, corrected_fp=0, corrected_fn=0, introduced_fp=1, introduced_fn=0.

### last

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 92.8571 | 93.0952 | 100.0000 | 86.6667 |
| 0 | E1 | 88.8889 | 89.6057 | 100.0000 | 80.0000 |
| 0 | E1-E0 pp | -3.9683 | -3.4895 | +0.0000 | -6.6667 |
| 1 | E0 | 85.7143 | 86.1905 | 85.7143 | 85.7143 |
| 1 | E1 | 85.7143 | 86.1905 | 85.7143 | 85.7143 |
| 1 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 2 | E0 | 89.6552 | 89.2720 | 86.6667 | 92.8571 |
| 2 | E1 | 83.8710 | 81.9355 | 76.4706 | 92.8571 |
| 2 | E1-E0 pp | -5.7842 | -7.3365 | -10.1961 | +0.0000 |
| 3 | E0 | 89.6552 | 89.2720 | 86.6667 | 92.8571 |
| 3 | E1 | 89.6552 | 89.2720 | 86.6667 | 92.8571 |
| 3 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 4 | E0 | 96.5517 | 96.4240 | 93.3333 | 100.0000 |
| 4 | E1 | 96.5517 | 96.4240 | 93.3333 | 100.0000 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 90.8867 +/- 4.0547 | 90.8508 +/- 3.9624 | 90.4762 +/- 6.1353 | 91.6190 +/- 5.7597 |
| E1 | 88.9362 +/- 4.8619 | 88.6855 +/- 5.3119 | 88.4370 +/- 8.8235 | 90.2857 +/- 7.6532 |
| E1-E0 | -1.9505 +/- 2.7469 | -2.1652 +/- 3.2619 | -2.0392 +/- 4.5598 | -1.3333 +/- 2.9814 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 0 | 3 | 2 |
| macro_f1 | 0 | 3 | 2 |
| precision | 0 | 4 | 1 |
| recall | 0 | 4 | 1 |

Error changes: both_correct=126, e0_wrong_e1_correct=0, e0_correct_e1_wrong=3, both_wrong=13, corrected_fp=0, corrected_fn=0, introduced_fp=2, introduced_fn=1.

### Fit telemetry (not counted twice for best/last)

| Model | Fits | Seconds total | Peak allocated MiB | Peak reserved MiB | Parameters | DDG train edges min-max | DDG gradient sum | Train-unseen relation folds |
|---|---:|---:|---:|---:|---|---|---:|---:|
| E0 | 5 | 1446.370 | 2159.49 | 2348.00 | [4526962] | 0-0 | 0.000000 | 2 |
| E1 | 5 | 2392.578 | 2749.57 | 2954.00 | [4641874] | 2592-2844 | 24.375570 | 3 |

All 5 paired receipts and their artifact fingerprints verified.

Per-fold epochs, telemetry and error identities are in CSV/JSON.

## access_control_author / contract

PENDING: no task mean; accepted entries in snapshot = 0/5

## reentrancy_author / node

PENDING: no task mean; accepted entries in snapshot = 0/10

## access_control_author / node

PENDING: no task mean; accepted entries in snapshot = 0/10

## Attempts and scope

{"attempts_discovered": 6, "current_state_failed": 0, "retry_attempts": 0, "historical_unaccepted_unknown": 0}

All discovered attempts and available error evidence are listed in attempts.csv/report.json.
Pending/unknown historical attempts are not reported as successful or fabricated failures.

- All main results are CV validation: the same fold validation set selects best and is scored.
- Best uses the lowest validation loss, not the highest F1; last is a separate auxiliary result.
- Metrics are percentages; E1 minus E0 is in percentage points.
- Unweighted fold mean and sample standard deviation (ddof=1); not a confidence interval.
- Node scores use HCG node identities (file + original node id), not deduplicated source-line F1.
- Fit time includes fitting, validation, checkpoint IO and reload scoring; count each fit once.
- GPU peaks are PyTorch process peaks with both models resident, not standalone model or whole-card memory.
- Cumulative DDG gradient depends on epoch count; parameter changes may include weight decay.
- No partial-fold task mean; no nested/narrow/multi-seed mixing; no graph, label or model changes.
- Historical unaccepted attempts without state evidence have unknown status, not invented failure reasons.
