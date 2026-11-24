# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper (Dataset B)

Reference: MANDO-LLM, ACM TOSEM 2025, Tables 4 and 6 (Dataset B), row `codet5p-770m` (the tokenizer the pipeline uses); `paper best LLM row` is the best of the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; Δ = ours − paper.

Run settings: `{"categories": ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy", "time_manipulation", "unchecked_low_level_calls"], "device": "cuda:0", "epochs": null, "folds": null, "labels": "public", "profiles": ["G0", "FULL"], "protocols": ["grouped"], "seed": 3, "tracks": ["contract", "line", "cascade"]}`
Code commit: `1aa68f5e1c85def49294467d957af3c7d3769979`

## FULL — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 73.39 ± 4.00 | 85.71 | -12.32 | 73.96 ± 3.74 | 85.71 | -11.75 | 92.30 (solidity-t5) |
| arithmetic | 5 | 62.23 ± 7.36 | 84.93 | -22.70 | 63.93 ± 4.97 | 85.32 | -21.39 | 89.47 (starcoder) |
| denial_of_service | 5 | 68.63 ± 7.69 | 94.12 | -25.49 | 69.74 ± 6.09 | 93.73 | -23.99 | 94.12 (codet5p-770m) |
| front_running | 5 | 65.58 ± 8.52 | 88.00 | -22.42 | 69.53 ± 5.82 | 88.23 | -18.70 | 90.57 (starcoder) |
| reentrancy | 5 | 69.30 ± 6.68 | 92.54 | -23.24 | 68.99 ± 7.31 | 92.30 | -23.31 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 76.65 ± 3.57 | 97.14 | -20.49 | 76.55 ± 3.57 | 97.06 | -20.51 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 74.70 ± 4.14 | 88.46 | -13.76 | 75.86 ± 5.23 | 87.98 | -12.12 | 88.46 (codet5p-770m) |
| **mean** |  | 70.07 | 90.13 | -20.06 | 71.22 | 90.05 | -18.82 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.83 ± 7.16 | 71.78 | +17.05 | 75.29 (solidity-t5) | 92.71 ± 4.87 | 84.08 | 85.49 ± 8.82 | 95.73 | 78.57 | 92.5 | 45.8 |
| arithmetic | 10 | 90.27 ± 6.92 | 87.65 | +2.62 | 88.47 (starcoder) | 93.79 ± 4.28 | 91.15 | 89.84 ± 8.65 | 97.48 | 84.44 | 95.9 | 31.6 |
| denial_of_service | 10 | 90.76 ± 3.09 | 72.40 | +18.36 | 72.40 (codet5p-770m) | 94.27 ± 1.85 | 83.08 | 87.15 ± 3.12 | 95.23 | 80.55 | 90.1 | 61.4 |
| front_running | 10 | 96.29 ± 2.73 | 91.73 | +4.56 | 92.82 (starcoder) | 96.62 ± 2.43 | 93.54 | 95.25 ± 3.35 | 98.75 | 92.16 | 97.7 | 44.3 |
| reentrancy | 10 | 91.95 ± 5.09 | 84.77 | +7.18 | 85.47 (solidity-t5) | 94.47 ± 3.23 | 89.12 | 86.98 ± 6.17 | 96.72 | 79.40 | 90.0 | 50.4 |
| time_manipulation | 10 | 98.90 ± 0.47 | 82.54 | +16.36 | 82.54 (codet5p-770m) | 99.09 ± 0.39 | 87.27 | 98.85 ± 0.77 | 98.99 | 98.72 | 99.7 | 72.2 |
| unchecked_low_level_calls | 10 | 93.34 ± 4.31 | 89.32 | +4.02 | 91.14 (starcoder) | 96.06 ± 2.51 | 93.72 | 89.93 ± 7.50 | 98.18 | 83.76 | 95.4 | 44.2 |
| **mean** |  | 92.91 | 82.88 | +10.02 |  |  |  | 90.50 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 73.39 | 85.31 ± 8.26 | 95.56 | 77.40 | 85.29 | 84.63 | 88.87 | 43.3 |
| arithmetic | 5 | 62.23 | 89.31 ± 3.96 | 95.81 | 83.95 | 89.36 | 88.39 | 89.39 | 30.6 |
| denial_of_service | 5 | 68.63 | 85.87 ± 1.99 | 93.34 | 79.84 | 86.16 | 84.64 | 89.20 | 46.4 |
| front_running | 5 | 65.58 | 95.32 ± 1.98 | 98.79 | 92.15 | 95.37 | 94.82 | 96.36 | 42.0 |
| reentrancy | 5 | 69.30 | 86.39 ± 3.56 | 95.46 | 79.09 | 87.14 | 86.06 | 91.24 | 43.4 |
| time_manipulation | 5 | 76.65 | 98.20 ± 1.02 | 97.99 | 98.44 | 98.79 | 98.05 | 98.40 | 64.0 |
| unchecked_low_level_calls | 5 | 74.70 | 90.23 ± 5.44 | 98.90 | 83.34 | 89.90 | 89.56 | 93.58 | 43.3 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 54.55 | 3.01 | 1.84 | 0.52 | 98.04 | 98.88 | 98.11 | 98.49 |
| arithmetic | 48.58 | 3.48 | 2.96 | 1.32 | 96.15 | 99.74 | 99.73 | 99.53 |
| denial_of_service | 53.61 | 21.36 | 18.58 | 10.57 | 98.04 | 99.57 | 95.77 | 95.50 |
| front_running | 37.61 | 2.64 | 1.94 | 0.42 | 99.01 | 99.68 | 99.67 | 99.69 |
| reentrancy | 56.11 | 12.45 | 9.63 | 6.05 | 98.04 | 99.75 | 96.65 | 96.72 |
| time_manipulation | 45.71 | 22.36 | 22.35 | 6.22 | 98.04 | 99.83 | 99.82 | 99.85 |
| unchecked_low_level_calls | 55.74 | 2.37 | 1.45 | 0.76 | 97.09 | 99.62 | 99.59 | 99.51 |

## G0 — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 68.26 ± 2.96 | 85.71 | -17.45 | 68.71 ± 4.02 | 85.71 | -17.00 | 92.30 (solidity-t5) |
| arithmetic | 5 | 62.09 ± 4.01 | 84.93 | -22.84 | 64.43 ± 3.67 | 85.32 | -20.89 | 89.47 (starcoder) |
| denial_of_service | 5 | 71.39 ± 6.03 | 94.12 | -22.73 | 72.51 ± 3.99 | 93.73 | -21.22 | 94.12 (codet5p-770m) |
| front_running | 5 | 70.01 ± 7.14 | 88.00 | -17.99 | 71.50 ± 5.68 | 88.23 | -16.73 | 90.57 (starcoder) |
| reentrancy | 5 | 69.63 ± 2.94 | 92.54 | -22.91 | 68.61 ± 4.21 | 92.30 | -23.69 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 77.64 ± 5.14 | 97.14 | -19.50 | 79.47 ± 4.45 | 97.06 | -17.59 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 66.41 ± 3.72 | 88.46 | -22.05 | 69.35 ± 3.09 | 87.98 | -18.63 | 88.46 (codet5p-770m) |
| **mean** |  | 69.35 | 90.13 | -20.78 | 70.65 | 90.05 | -19.39 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.59 ± 7.29 | 71.78 | +16.81 | 75.29 (solidity-t5) | 92.54 ± 4.96 | 84.08 | 85.19 ± 8.97 | 94.83 | 78.53 | 92.5 | 46.7 |
| arithmetic | 10 | 89.73 ± 6.82 | 87.65 | +2.08 | 88.47 (starcoder) | 93.43 ± 4.23 | 91.15 | 89.43 ± 8.68 | 96.53 | 84.37 | 95.9 | 31.7 |
| denial_of_service | 10 | 89.12 ± 3.30 | 72.40 | +16.72 | 72.40 (codet5p-770m) | 93.26 ± 1.95 | 83.08 | 85.87 ± 3.33 | 94.19 | 79.05 | 90.1 | 48.5 |
| front_running | 10 | 95.98 ± 2.54 | 91.73 | +4.25 | 92.82 (starcoder) | 96.33 ± 2.22 | 93.54 | 94.95 ± 3.20 | 98.18 | 92.10 | 97.7 | 49.9 |
| reentrancy | 10 | 90.37 ± 4.54 | 84.77 | +5.60 | 85.47 (solidity-t5) | 93.36 ± 2.82 | 89.12 | 85.63 ± 5.55 | 95.04 | 78.43 | 90.0 | 41.6 |
| time_manipulation | 10 | 98.56 ± 0.57 | 82.54 | +16.02 | 82.54 (codet5p-770m) | 98.81 ± 0.47 | 87.27 | 98.52 ± 0.74 | 98.97 | 98.07 | 99.7 | 58.3 |
| unchecked_low_level_calls | 10 | 93.11 ± 4.29 | 89.32 | +3.79 | 91.14 (starcoder) | 95.93 ± 2.50 | 93.72 | 89.70 ± 7.49 | 97.80 | 83.66 | 95.4 | 42.5 |
| **mean** |  | 92.21 | 82.88 | +9.33 |  |  |  | 89.90 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 68.26 | 84.52 ± 7.79 | 93.44 | 77.56 | 84.69 | 82.52 | 87.96 | 45.8 |
| arithmetic | 5 | 62.09 | 89.78 ± 3.34 | 97.02 | 83.74 | 89.84 | 88.33 | 89.76 | 29.5 |
| denial_of_service | 5 | 71.39 | 85.00 ± 2.71 | 93.78 | 77.94 | 85.33 | 83.30 | 88.40 | 41.9 |
| front_running | 5 | 70.01 | 95.06 ± 1.72 | 98.34 | 92.08 | 94.98 | 93.92 | 96.08 | 43.6 |
| reentrancy | 5 | 69.63 | 85.40 ± 3.40 | 94.49 | 78.15 | 85.81 | 84.54 | 89.98 | 38.5 |
| time_manipulation | 5 | 77.64 | 98.47 ± 0.29 | 99.19 | 97.77 | 98.36 | 97.60 | 98.54 | 58.2 |
| unchecked_low_level_calls | 5 | 66.41 | 90.22 ± 5.32 | 98.99 | 83.27 | 89.84 | 89.54 | 93.54 | 41.7 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 47.24 | 2.43 | 1.76 | 1.83 | 93.46 | 99.16 | 98.34 | 98.02 |
| arithmetic | 46.86 | 7.58 | 4.07 | 2.14 | 98.04 | 99.24 | 99.28 | 99.33 |
| denial_of_service | 58.03 | 12.30 | 10.45 | 4.95 | 98.04 | 98.68 | 95.08 | 94.62 |
| front_running | 48.53 | 2.65 | 1.96 | 0.79 | 100.00 | 99.62 | 99.62 | 99.64 |
| reentrancy | 56.52 | 5.36 | 3.95 | 4.05 | 100.00 | 99.28 | 96.27 | 96.01 |
| time_manipulation | 39.29 | 0.00 | 0.00 | 0.00 | 99.01 | 99.58 | 99.56 | 99.47 |
| unchecked_low_level_calls | 38.60 | 0.58 | 0.36 | 0.00 | 98.04 | 99.64 | 99.60 | 99.66 |

Source lines are preprocessed lines spoken for by node label endpoints (`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks for, `contracts hit` the share of vulnerable contracts with at least one annotated line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`.
