# Dataset A formal CV validation report

- Protocol: paper_kfold / ddg-paper-kfold-v1.
- Best: minimum validation loss. Last: auxiliary, reported separately.
- Node metrics count HCG nodes; they are not deduplicated source-line metrics.
- Metrics: percent. Delta: E1-E0 percentage points. Std: sample, ddof=1.

## reentrancy_author / contract

PENDING: no task mean; accepted entries in snapshot = 1/5

## access_control_author / contract

PENDING: no task mean; accepted entries in snapshot = 0/5

## reentrancy_author / node

PENDING: no task mean; accepted entries in snapshot = 0/10

## access_control_author / node

PENDING: no task mean; accepted entries in snapshot = 0/10

## Attempts and scope

{"attempts_discovered": 2, "current_state_failed": 0, "retry_attempts": 0, "historical_unaccepted_unknown": 0}

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
