# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper (Dataset B)

Reference: MANDO-LLM, ACM TOSEM 2025, Tables 4 and 6 (Dataset B), row `codet5p-770m` (the tokenizer the pipeline uses); `paper best LLM row` is the best of the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; Δ = ours − paper.

Run settings: `{"categories": ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy", "time_manipulation", "unchecked_low_level_calls"], "device": "cuda:0", "epochs": null, "folds": null, "labels": "public", "profiles": ["G0", "FULL"], "protocols": ["grouped"], "seed": 2, "tracks": ["contract", "line", "cascade"]}`
Code commit: `1aa68f5e1c85def49294467d957af3c7d3769979`

## FULL — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 70.93 ± 4.89 | 85.71 | -14.78 | 72.73 ± 3.49 | 85.71 | -12.98 | 92.30 (solidity-t5) |
| arithmetic | 5 | 62.51 ± 6.29 | 84.93 | -22.42 | 64.93 ± 2.08 | 85.32 | -20.39 | 89.47 (starcoder) |
| denial_of_service | 5 | 69.30 ± 9.91 | 94.12 | -24.82 | 70.64 ± 8.81 | 93.73 | -23.09 | 94.12 (codet5p-770m) |
| front_running | 5 | 69.20 ± 5.29 | 88.00 | -18.80 | 70.78 ± 5.09 | 88.23 | -17.45 | 90.57 (starcoder) |
| reentrancy | 5 | 68.25 ± 6.61 | 92.54 | -24.29 | 68.60 ± 5.86 | 92.30 | -23.70 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 79.70 ± 3.40 | 97.14 | -17.44 | 79.40 ± 1.84 | 97.06 | -17.66 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 72.00 ± 6.91 | 88.46 | -16.46 | 75.19 ± 5.31 | 87.98 | -12.79 | 88.46 (codet5p-770m) |
| **mean** |  | 70.27 | 90.13 | -19.86 | 71.76 | 90.05 | -18.29 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 89.25 ± 7.32 | 71.78 | +17.47 | 75.29 (solidity-t5) | 92.98 ± 5.00 | 84.08 | 85.82 ± 8.92 | 96.39 | 78.63 | 92.5 | 48.3 |
| arithmetic | 10 | 90.75 ± 6.35 | 87.65 | +3.10 | 88.47 (starcoder) | 94.08 ± 3.95 | 91.15 | 90.32 ± 8.15 | 97.66 | 84.94 | 95.9 | 33.8 |
| denial_of_service | 10 | 90.36 ± 3.48 | 72.40 | +17.96 | 72.40 (codet5p-770m) | 94.02 ± 2.12 | 83.08 | 86.84 ± 3.43 | 95.27 | 80.08 | 90.1 | 53.6 |
| front_running | 10 | 96.41 ± 2.68 | 91.73 | +4.68 | 92.82 (starcoder) | 96.73 ± 2.35 | 93.54 | 95.37 ± 3.30 | 98.96 | 92.19 | 97.7 | 46.0 |
| reentrancy | 10 | 92.11 ± 4.98 | 84.77 | +7.34 | 85.47 (solidity-t5) | 94.59 ± 3.15 | 89.12 | 87.14 ± 6.05 | 97.56 | 79.16 | 90.0 | 45.4 |
| time_manipulation | 10 | 98.72 ± 0.81 | 82.54 | +16.18 | 82.54 (codet5p-770m) | 98.93 ± 0.67 | 87.27 | 98.60 ± 1.14 | 98.56 | 98.65 | 99.7 | 68.9 |
| unchecked_low_level_calls | 10 | 93.24 ± 4.31 | 89.32 | +3.92 | 91.14 (starcoder) | 96.01 ± 2.50 | 93.72 | 89.83 ± 7.47 | 98.05 | 83.73 | 95.4 | 44.2 |
| **mean** |  | 92.98 | 82.88 | +10.09 |  |  |  | 90.56 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 70.93 | 85.38 ± 7.70 | 95.88 | 77.40 | 84.87 | 84.22 | 88.90 | 45.0 |
| arithmetic | 5 | 62.51 | 89.71 ± 3.53 | 96.48 | 84.05 | 89.87 | 88.89 | 89.80 | 30.6 |
| denial_of_service | 5 | 69.30 | 86.82 ± 2.11 | 95.83 | 79.53 | 86.95 | 85.68 | 90.07 | 41.2 |
| front_running | 5 | 69.20 | 95.27 ± 2.17 | 98.65 | 92.16 | 95.40 | 94.93 | 96.29 | 41.1 |
| reentrancy | 5 | 68.25 | 86.41 ± 3.49 | 95.75 | 78.95 | 87.05 | 85.98 | 91.23 | 40.4 |
| time_manipulation | 5 | 79.70 | 98.14 ± 1.37 | 97.82 | 98.47 | 98.54 | 97.71 | 98.32 | 66.2 |
| unchecked_low_level_calls | 5 | 72.00 | 90.32 ± 5.36 | 99.22 | 83.27 | 90.00 | 89.84 | 93.65 | 41.7 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 50.85 | 3.80 | 2.39 | 0.52 | 93.46 | 99.00 | 98.22 | 98.46 |
| arithmetic | 49.15 | 9.92 | 8.32 | 2.18 | 94.34 | 99.82 | 99.81 | 99.53 |
| denial_of_service | 54.74 | 15.68 | 14.40 | 8.67 | 97.09 | 99.72 | 95.93 | 95.74 |
| front_running | 46.97 | 3.53 | 2.63 | 0.54 | 98.04 | 99.77 | 99.77 | 99.77 |
| reentrancy | 54.38 | 9.94 | 7.49 | 4.73 | 99.01 | 99.87 | 96.76 | 96.76 |
| time_manipulation | 54.05 | 18.71 | 16.22 | 7.76 | 99.01 | 99.74 | 99.73 | 99.83 |
| unchecked_low_level_calls | 48.15 | 1.76 | 1.08 | 0.00 | 98.04 | 99.62 | 99.59 | 99.66 |

## G0 — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 68.53 ± 3.23 | 85.71 | -17.18 | 69.06 ± 2.32 | 85.71 | -16.65 | 92.30 (solidity-t5) |
| arithmetic | 5 | 63.81 ± 4.54 | 84.93 | -21.12 | 62.61 ± 2.14 | 85.32 | -22.71 | 89.47 (starcoder) |
| denial_of_service | 5 | 68.71 ± 9.40 | 94.12 | -25.41 | 69.82 ± 6.88 | 93.73 | -23.91 | 94.12 (codet5p-770m) |
| front_running | 5 | 67.58 ± 10.18 | 88.00 | -20.42 | 70.46 ± 7.62 | 88.23 | -17.77 | 90.57 (starcoder) |
| reentrancy | 5 | 68.98 ± 3.84 | 92.54 | -23.56 | 68.33 ± 4.22 | 92.30 | -23.97 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 74.94 ± 3.16 | 97.14 | -22.20 | 77.11 ± 3.37 | 97.06 | -19.95 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 69.08 ± 5.67 | 88.46 | -19.38 | 71.23 ± 4.41 | 87.98 | -16.75 | 88.46 (codet5p-770m) |
| **mean** |  | 68.80 | 90.13 | -21.32 | 69.80 | 90.05 | -20.24 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.41 ± 7.23 | 71.78 | +16.63 | 75.29 (solidity-t5) | 92.43 ± 4.90 | 84.08 | 85.08 ± 8.93 | 94.64 | 78.52 | 92.5 | 45.8 |
| arithmetic | 10 | 89.79 ± 6.82 | 87.65 | +2.14 | 88.47 (starcoder) | 93.48 ± 4.22 | 91.15 | 89.54 ± 8.65 | 96.83 | 84.33 | 95.9 | 31.7 |
| denial_of_service | 10 | 88.58 ± 2.98 | 72.40 | +16.18 | 72.40 (codet5p-770m) | 92.91 ± 1.74 | 83.08 | 85.21 ± 2.99 | 92.95 | 78.86 | 90.1 | 47.8 |
| front_running | 10 | 96.14 ± 2.53 | 91.73 | +4.41 | 92.82 (starcoder) | 96.48 ± 2.21 | 93.54 | 95.11 ± 3.17 | 98.50 | 92.12 | 97.7 | 45.9 |
| reentrancy | 10 | 90.49 ± 4.63 | 84.77 | +5.72 | 85.47 (solidity-t5) | 93.45 ± 2.91 | 89.12 | 85.75 ± 5.61 | 95.21 | 78.44 | 90.0 | 44.7 |
| time_manipulation | 10 | 98.56 ± 0.57 | 82.54 | +16.02 | 82.54 (codet5p-770m) | 98.81 ± 0.48 | 87.27 | 98.53 ± 0.77 | 99.03 | 98.04 | 99.7 | 58.3 |
| unchecked_low_level_calls | 10 | 93.29 ± 4.34 | 89.32 | +3.97 | 91.14 (starcoder) | 96.03 ± 2.52 | 93.72 | 89.86 ± 7.52 | 98.19 | 83.66 | 95.4 | 42.5 |
| **mean** |  | 92.18 | 82.88 | +9.30 |  |  |  | 89.87 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 68.53 | 84.87 ± 7.75 | 94.43 | 77.45 | 84.91 | 83.17 | 88.25 | 45.8 |
| arithmetic | 5 | 63.81 | 89.61 ± 3.19 | 96.30 | 84.01 | 89.82 | 88.21 | 89.53 | 31.7 |
| denial_of_service | 5 | 68.71 | 84.98 ± 2.72 | 92.98 | 78.40 | 85.21 | 82.80 | 88.24 | 41.2 |
| front_running | 5 | 67.58 | 95.22 ± 1.97 | 98.64 | 92.10 | 95.13 | 94.09 | 96.24 | 44.4 |
| reentrancy | 5 | 68.98 | 85.43 ± 3.74 | 94.44 | 78.17 | 85.84 | 84.49 | 90.14 | 37.3 |
| time_manipulation | 5 | 74.94 | 98.74 ± 0.36 | 99.34 | 98.15 | 98.63 | 97.93 | 98.79 | 58.2 |
| unchecked_low_level_calls | 5 | 69.08 | 90.20 ± 5.17 | 98.93 | 83.30 | 89.63 | 89.24 | 93.55 | 42.5 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 48.06 | 1.98 | 1.63 | 1.51 | 93.46 | 99.12 | 98.27 | 98.15 |
| arithmetic | 52.01 | 6.35 | 3.76 | 3.19 | 96.15 | 99.31 | 99.36 | 99.41 |
| denial_of_service | 54.64 | 11.54 | 9.45 | 3.99 | 98.04 | 98.87 | 95.13 | 95.06 |
| front_running | 43.20 | 2.32 | 1.74 | 0.96 | 99.01 | 99.68 | 99.69 | 99.64 |
| reentrancy | 55.75 | 5.96 | 4.59 | 3.48 | 99.01 | 99.16 | 96.17 | 96.11 |
| time_manipulation | 29.63 | 0.00 | 0.00 | 0.00 | 99.01 | 99.48 | 99.46 | 99.72 |
| unchecked_low_level_calls | 44.26 | 0.59 | 0.36 | 0.37 | 100.00 | 99.74 | 99.70 | 99.70 |

Source lines are preprocessed lines spoken for by node label endpoints (`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks for, `contracts hit` the share of vulnerable contracts with at least one annotated line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`.
