# FULL vs G0 (grouped protocol, Dataset B, seeds 1)

Buggy-F1, best checkpoint. *Pooled*: all held-out folds of a seed together, mean ± sd over seeds. *Δ*: mean of FULL − G0 over (seed, fold) pairs; p: Wilcoxon signed-rank, Holm over categories. Main metric: `line_dappscan`.

## line_dappscan

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 2.75 ± 0.00 | 3.76 ± 0.00 | 2.47 | 3/2/5 | 0.8672 | 1.0000 |
| arithmetic | 6.09 ± 0.00 | 4.89 ± 0.00 | -1.33 | 5/2/3 | 0.8047 | 1.0000 |
| denial_of_service | 10.54 ± 0.00 | 21.64 ± 0.00 | 11.51 | 9/0/1 | 0.0059 | 0.0410 |
| front_running | 2.72 ± 0.00 | 3.94 ± 0.00 | 0.64 | 3/1/6 | 1.0000 | 1.0000 |
| reentrancy | 6.44 ± 0.00 | 11.16 ± 0.00 | 6.20 | 8/0/2 | 0.0371 | 0.1855 |
| time_manipulation | 1.57 ± 0.00 | 13.66 ± 0.00 | 15.83 | 8/2/0 | 0.0078 | 0.0469 |
| unchecked_low_level_calls | 1.14 ± 0.00 | 0.58 ± 0.00 | -0.97 | 1/7/2 | 0.7500 | 1.0000 |

## line_all

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 88.13 ± 0.00 | 89.02 ± 0.00 | 0.85 | 8/0/2 | 0.0840 | 0.4199 |
| arithmetic | 90.10 ± 0.00 | 90.70 ± 0.00 | 0.63 | 7/0/3 | 0.1602 | 0.4199 |
| denial_of_service | 88.97 ± 0.00 | 91.12 ± 0.00 | 2.16 | 8/0/2 | 0.0098 | 0.0586 |
| front_running | 96.25 ± 0.00 | 96.55 ± 0.00 | 0.30 | 8/0/2 | 0.1055 | 0.4199 |
| reentrancy | 90.57 ± 0.00 | 92.40 ± 0.00 | 1.78 | 9/0/1 | 0.0039 | 0.0273 |
| time_manipulation | 98.58 ± 0.00 | 98.84 ± 0.00 | 0.24 | 9/0/1 | 0.0840 | 0.4199 |
| unchecked_low_level_calls | 93.22 ± 0.00 | 93.36 ± 0.00 | 0.13 | 7/1/2 | 0.3477 | 0.4199 |

## contract_dappscan

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 49.60 ± 0.00 | 49.18 ± 0.00 | -0.81 | 2/1/2 | 0.8750 | 1.0000 |
| arithmetic | 42.57 ± 0.00 | 54.47 ± 0.00 | 11.78 | 4/0/1 | 0.1250 | 0.7500 |
| denial_of_service | 58.33 ± 0.00 | 56.68 ± 0.00 | -1.59 | 3/0/2 | 1.0000 | 1.0000 |
| front_running | 45.93 ± 0.00 | 44.80 ± 0.00 | -1.04 | 2/0/3 | 0.8125 | 1.0000 |
| reentrancy | 52.29 ± 0.00 | 52.48 ± 0.00 | -1.69 | 2/0/3 | 1.0000 | 1.0000 |
| time_manipulation | 36.36 ± 0.00 | 50.00 ± 0.00 | 14.39 | 5/0/0 | 0.0625 | 0.4375 |
| unchecked_low_level_calls | 53.12 ± 0.00 | 57.35 ± 0.00 | 5.09 | 4/0/1 | 0.1250 | 0.7500 |

## contract_all

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 69.53 ± 0.00 | 71.11 ± 0.00 | 1.52 | 3/0/2 | 0.8125 | 1.0000 |
| arithmetic | 61.39 ± 0.00 | 65.75 ± 0.00 | 4.13 | 4/0/1 | 0.1875 | 1.0000 |
| denial_of_service | 71.86 ± 0.00 | 71.28 ± 0.00 | -0.62 | 3/0/2 | 1.0000 | 1.0000 |
| front_running | 68.94 ± 0.00 | 68.72 ± 0.00 | -0.11 | 2/0/3 | 0.8125 | 1.0000 |
| reentrancy | 67.30 ± 0.00 | 67.99 ± 0.00 | -0.10 | 2/0/3 | 1.0000 | 1.0000 |
| time_manipulation | 76.92 ± 0.00 | 78.61 ± 0.00 | 1.77 | 3/0/2 | 0.6250 | 1.0000 |
| unchecked_low_level_calls | 72.41 ± 0.00 | 74.79 ± 0.00 | 2.50 | 4/1/0 | 0.1250 | 0.8750 |
