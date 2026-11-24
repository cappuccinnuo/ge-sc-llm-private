# FULL vs G0 (grouped protocol, Dataset B, seeds 1, 2, 3)

Buggy-F1, best checkpoint. *Pooled*: all held-out folds of a seed together, mean ± sd over seeds. *Δ*: mean of FULL − G0 over (seed, fold) pairs; p: Wilcoxon signed-rank, Holm over categories. Main metric: `line_dappscan`.

## line_dappscan

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 2.39 ± 0.39 | 3.52 ± 0.44 | 2.50 | 9/9/12 | 0.7257 | 1.0000 |
| arithmetic | 6.68 ± 0.80 | 6.10 ± 3.39 | -0.50 | 13/5/12 | 0.9180 | 1.0000 |
| denial_of_service | 11.46 ± 0.89 | 19.56 ± 3.36 | 8.39 | 22/0/8 | 0.0007 | 0.0033 |
| front_running | 2.56 ± 0.21 | 3.37 ± 0.66 | -0.11 | 8/6/16 | 0.4462 | 1.0000 |
| reentrancy | 5.92 ± 0.54 | 11.18 ± 1.26 | 6.41 | 25/1/4 | 0.0001 | 0.0007 |
| time_manipulation | 0.52 ± 0.91 | 18.25 ± 4.37 | 19.61 | 24/6/0 | 0.0000 | 0.0000 |
| unchecked_low_level_calls | 0.77 ± 0.32 | 1.57 ± 0.91 | 0.68 | 6/21/3 | 0.4271 | 1.0000 |

## line_all

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 88.41 ± 0.25 | 89.06 ± 0.20 | 0.64 | 22/0/8 | 0.0076 | 0.0228 |
| arithmetic | 90.14 ± 0.05 | 90.80 ± 0.22 | 0.71 | 22/0/8 | 0.0076 | 0.0228 |
| denial_of_service | 89.02 ± 0.30 | 90.86 ± 0.29 | 1.86 | 25/0/5 | 0.0000 | 0.0001 |
| front_running | 96.22 ± 0.09 | 96.51 ± 0.07 | 0.30 | 24/1/5 | 0.0048 | 0.0193 |
| reentrancy | 90.65 ± 0.09 | 92.35 ± 0.09 | 1.66 | 25/0/5 | 0.0000 | 0.0000 |
| time_manipulation | 98.55 ± 0.03 | 98.79 ± 0.10 | 0.25 | 26/0/4 | 0.0024 | 0.0121 |
| unchecked_low_level_calls | 93.35 ± 0.14 | 93.45 ± 0.09 | 0.10 | 17/3/10 | 0.2711 | 0.2711 |

## contract_dappscan

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 48.30 ± 1.20 | 51.52 ± 2.75 | 3.19 | 9/1/5 | 0.2220 | 1.0000 |
| arithmetic | 47.15 ± 4.73 | 50.74 ± 3.25 | 2.98 | 10/0/5 | 0.3591 | 1.0000 |
| denial_of_service | 57.00 ± 2.05 | 55.01 ± 1.56 | -1.11 | 9/0/6 | 0.9773 | 1.0000 |
| front_running | 45.89 ± 2.66 | 43.13 ± 4.90 | -2.42 | 6/0/9 | 0.6387 | 1.0000 |
| reentrancy | 54.86 ± 2.25 | 54.32 ± 1.82 | -1.40 | 6/1/8 | 0.4777 | 1.0000 |
| time_manipulation | 35.09 ± 4.95 | 49.92 ± 4.17 | 13.31 | 12/1/2 | 0.0070 | 0.0488 |
| unchecked_low_level_calls | 45.33 ± 7.32 | 53.75 ± 4.91 | 8.93 | 12/0/3 | 0.0353 | 0.2120 |

## contract_all

| category | G0 pooled | FULL pooled | Δ (pp) | +/=/− | p | p (Holm) |
|---|---|---|---|---|---|---|
| access_control | 68.85 ± 0.60 | 71.91 ± 1.38 | 3.01 | 11/0/4 | 0.0730 | 0.4380 |
| arithmetic | 62.58 ± 1.45 | 63.86 ± 1.65 | 0.99 | 9/0/6 | 0.5995 | 1.0000 |
| denial_of_service | 71.11 ± 1.31 | 69.94 ± 1.21 | -0.93 | 8/0/7 | 0.7615 | 1.0000 |
| front_running | 69.14 ± 1.11 | 68.00 ± 1.71 | -0.97 | 6/0/9 | 0.6788 | 1.0000 |
| reentrancy | 68.70 ± 1.25 | 68.63 ± 0.68 | -0.39 | 7/0/8 | 0.8469 | 1.0000 |
| time_manipulation | 76.49 ± 1.48 | 78.45 ± 1.63 | 1.85 | 9/0/6 | 0.3303 | 1.0000 |
| unchecked_low_level_calls | 69.48 ± 2.88 | 73.95 ± 1.36 | 4.57 | 13/1/1 | 0.0059 | 0.0411 |
