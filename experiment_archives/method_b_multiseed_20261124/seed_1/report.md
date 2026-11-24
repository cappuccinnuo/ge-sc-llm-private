# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper (Dataset B)

Reference: MANDO-LLM, ACM TOSEM 2025, Tables 4 and 6 (Dataset B), row `codet5p-770m` (the tokenizer the pipeline uses); `paper best LLM row` is the best of the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; Δ = ours − paper.

Run settings: `{"categories": ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy", "time_manipulation", "unchecked_low_level_calls"], "device": "cuda:0", "epochs": null, "folds": null, "labels": "public", "profiles": ["G0", "FULL"], "protocols": ["grouped"], "seed": 1, "tracks": ["contract", "line", "cascade"]}`
Code commit: `1aa68f5e1c85def49294467d957af3c7d3769979`

## FULL — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 71.04 ± 7.08 | 85.71 | -14.67 | 72.61 ± 6.51 | 85.71 | -13.10 | 92.30 (solidity-t5) |
| arithmetic | 5 | 64.91 ± 7.46 | 84.93 | -20.02 | 65.12 ± 3.83 | 85.32 | -20.20 | 89.47 (starcoder) |
| denial_of_service | 5 | 71.15 ± 9.00 | 94.12 | -22.97 | 72.67 ± 8.30 | 93.73 | -21.06 | 94.12 (codet5p-770m) |
| front_running | 5 | 68.42 ± 6.80 | 88.00 | -19.58 | 71.07 ± 4.68 | 88.23 | -17.16 | 90.57 (starcoder) |
| reentrancy | 5 | 67.15 ± 10.78 | 92.54 | -25.39 | 69.46 ± 7.83 | 92.30 | -22.84 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 78.60 ± 5.94 | 97.14 | -18.54 | 78.41 ± 5.94 | 97.06 | -18.65 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 74.93 ± 4.01 | 88.46 | -13.53 | 74.93 ± 5.07 | 87.98 | -13.05 | 88.46 (codet5p-770m) |
| **mean** |  | 70.88 | 90.13 | -19.24 | 72.04 | 90.05 | -18.01 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.96 ± 7.27 | 71.78 | +17.18 | 75.29 (solidity-t5) | 92.79 ± 4.94 | 84.08 | 85.51 ± 8.87 | 95.72 | 78.63 | 92.5 | 47.5 |
| arithmetic | 10 | 90.34 ± 6.56 | 87.65 | +2.69 | 88.47 (starcoder) | 93.83 ± 4.05 | 91.15 | 89.90 ± 8.35 | 97.51 | 84.50 | 95.9 | 32.2 |
| denial_of_service | 10 | 90.92 ± 3.20 | 72.40 | +18.52 | 72.40 (codet5p-770m) | 94.37 ± 1.90 | 83.08 | 87.27 ± 3.32 | 95.37 | 80.66 | 90.1 | 58.9 |
| front_running | 10 | 96.41 ± 2.73 | 91.73 | +4.68 | 92.82 (starcoder) | 96.73 ± 2.41 | 93.54 | 95.37 ± 3.34 | 98.95 | 92.20 | 97.7 | 45.1 |
| reentrancy | 10 | 92.10 ± 4.97 | 84.77 | +7.33 | 85.47 (solidity-t5) | 94.57 ± 3.16 | 89.12 | 87.09 ± 6.09 | 97.30 | 79.25 | 90.0 | 48.5 |
| time_manipulation | 10 | 98.87 ± 0.64 | 82.54 | +16.33 | 82.54 (codet5p-770m) | 99.06 ± 0.53 | 87.27 | 98.72 ± 0.97 | 98.89 | 98.57 | 99.7 | 68.9 |
| unchecked_low_level_calls | 10 | 93.14 ± 4.42 | 89.32 | +3.82 | 91.14 (starcoder) | 95.95 ± 2.56 | 93.72 | 89.74 ± 7.57 | 97.93 | 83.66 | 95.4 | 42.5 |
| **mean** |  | 92.96 | 82.88 | +10.08 |  |  |  | 90.51 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 71.04 | 85.34 ± 8.09 | 95.62 | 77.44 | 85.12 | 84.58 | 88.84 | 45.8 |
| arithmetic | 5 | 64.91 | 89.48 ± 3.57 | 96.01 | 84.00 | 89.81 | 88.27 | 89.62 | 31.7 |
| denial_of_service | 5 | 71.15 | 85.89 ± 2.77 | 93.76 | 79.55 | 86.37 | 84.58 | 89.21 | 43.8 |
| front_running | 5 | 68.42 | 95.25 ± 1.97 | 98.63 | 92.16 | 95.33 | 94.85 | 96.30 | 42.8 |
| reentrancy | 5 | 67.15 | 86.55 ± 3.55 | 96.28 | 78.82 | 87.06 | 85.99 | 91.54 | 39.1 |
| time_manipulation | 5 | 78.60 | 98.42 ± 0.80 | 98.38 | 98.47 | 98.79 | 98.12 | 98.56 | 67.6 |
| unchecked_low_level_calls | 5 | 74.93 | 90.35 ± 5.32 | 99.22 | 83.34 | 90.05 | 89.96 | 93.72 | 43.3 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 49.18 | 3.76 | 2.25 | 0.90 | 97.09 | 98.79 | 97.94 | 98.49 |
| arithmetic | 54.47 | 4.89 | 3.79 | 1.62 | 92.59 | 99.67 | 99.68 | 99.22 |
| denial_of_service | 56.68 | 21.64 | 19.87 | 7.94 | 98.04 | 99.71 | 95.88 | 95.93 |
| front_running | 44.80 | 3.94 | 2.89 | 0.69 | 98.04 | 99.78 | 99.78 | 99.65 |
| reentrancy | 52.48 | 11.16 | 8.35 | 3.53 | 99.01 | 99.85 | 96.73 | 96.70 |
| time_manipulation | 50.00 | 13.66 | 10.17 | 8.74 | 99.01 | 99.91 | 99.90 | 99.88 |
| unchecked_low_level_calls | 57.35 | 0.58 | 0.36 | 0.76 | 98.04 | 99.64 | 99.60 | 99.66 |

## G0 — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 69.52 ± 2.22 | 85.71 | -16.19 | 70.21 ± 3.23 | 85.71 | -15.50 | 92.30 (solidity-t5) |
| arithmetic | 5 | 60.78 ± 8.53 | 84.93 | -24.15 | 66.56 ± 5.97 | 85.32 | -18.76 | 89.47 (starcoder) |
| denial_of_service | 5 | 71.77 ± 6.47 | 94.12 | -22.35 | 72.69 ± 6.14 | 93.73 | -21.04 | 94.12 (codet5p-770m) |
| front_running | 5 | 68.53 ± 9.20 | 88.00 | -19.47 | 70.38 ± 7.32 | 88.23 | -17.85 | 90.57 (starcoder) |
| reentrancy | 5 | 67.24 ± 5.37 | 92.54 | -25.30 | 67.46 ± 6.07 | 92.30 | -24.84 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 76.83 ± 5.91 | 97.14 | -20.31 | 78.85 ± 5.14 | 97.06 | -18.21 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 72.43 ± 3.70 | 88.46 | -16.03 | 73.15 ± 4.48 | 87.98 | -14.83 | 88.46 (codet5p-770m) |
| **mean** |  | 69.59 | 90.13 | -20.54 | 71.33 | 90.05 | -18.72 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.11 ± 7.32 | 71.78 | +16.33 | 75.29 (solidity-t5) | 92.21 ± 4.97 | 84.08 | 84.73 ± 9.12 | 93.78 | 78.48 | 92.5 | 49.2 |
| arithmetic | 10 | 89.71 ± 6.75 | 87.65 | +2.06 | 88.47 (starcoder) | 93.43 ± 4.17 | 91.15 | 89.52 ± 8.44 | 97.11 | 84.12 | 95.9 | 30.6 |
| denial_of_service | 10 | 88.75 ± 3.43 | 72.40 | +16.35 | 72.40 (codet5p-770m) | 93.03 ± 2.04 | 83.08 | 85.50 ± 3.51 | 93.98 | 78.60 | 90.1 | 47.7 |
| front_running | 10 | 96.11 ± 2.58 | 91.73 | +4.38 | 92.82 (starcoder) | 96.45 ± 2.25 | 93.54 | 95.08 ± 3.22 | 98.45 | 92.09 | 97.7 | 47.6 |
| reentrancy | 10 | 90.31 ± 4.60 | 84.77 | +5.54 | 85.47 (solidity-t5) | 93.32 ± 2.86 | 89.12 | 85.57 ± 5.59 | 94.95 | 78.33 | 90.0 | 45.3 |
| time_manipulation | 10 | 98.63 ± 0.55 | 82.54 | +16.09 | 82.54 (codet5p-770m) | 98.86 ± 0.47 | 87.27 | 98.60 ± 0.77 | 99.06 | 98.14 | 99.7 | 59.4 |
| unchecked_low_level_calls | 10 | 93.00 ± 4.56 | 89.32 | +3.68 | 91.14 (starcoder) | 95.87 ± 2.65 | 93.72 | 89.58 ± 7.67 | 97.39 | 83.69 | 95.4 | 43.3 |
| **mean** |  | 92.09 | 82.88 | +9.20 |  |  |  | 89.80 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 69.52 | 84.72 ± 7.67 | 94.08 | 77.47 | 84.88 | 82.99 | 88.03 | 45.0 |
| arithmetic | 5 | 60.78 | 89.64 ± 2.83 | 96.65 | 83.86 | 89.73 | 88.18 | 89.55 | 30.1 |
| denial_of_service | 5 | 71.77 | 84.93 ± 2.91 | 93.28 | 78.11 | 85.15 | 83.09 | 88.34 | 41.2 |
| front_running | 5 | 68.53 | 95.03 ± 1.85 | 98.27 | 92.06 | 95.01 | 93.95 | 96.02 | 43.6 |
| reentrancy | 5 | 67.24 | 85.47 ± 3.80 | 94.32 | 78.28 | 85.87 | 84.32 | 90.09 | 37.9 |
| time_manipulation | 5 | 76.83 | 98.68 ± 0.38 | 99.35 | 98.03 | 98.59 | 98.05 | 98.75 | 58.2 |
| unchecked_low_level_calls | 5 | 72.43 | 89.86 ± 5.43 | 98.08 | 83.31 | 89.55 | 88.97 | 93.17 | 42.5 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 49.60 | 2.75 | 2.06 | 1.12 | 92.59 | 99.01 | 98.19 | 98.15 |
| arithmetic | 42.57 | 6.09 | 3.56 | 1.68 | 99.01 | 99.19 | 99.27 | 99.06 |
| denial_of_service | 58.33 | 10.54 | 8.54 | 3.67 | 97.09 | 98.58 | 94.99 | 94.89 |
| front_running | 45.93 | 2.72 | 1.87 | 0.92 | 100.00 | 99.67 | 99.67 | 99.65 |
| reentrancy | 52.29 | 6.44 | 4.84 | 3.41 | 100.00 | 99.12 | 96.13 | 96.12 |
| time_manipulation | 36.36 | 1.57 | 1.53 | 0.00 | 99.01 | 99.55 | 99.54 | 99.68 |
| unchecked_low_level_calls | 53.12 | 1.14 | 0.71 | 0.37 | 96.15 | 99.59 | 99.51 | 99.35 |

Source lines are preprocessed lines spoken for by node label endpoints (`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks for, `contracts hit` the share of vulnerable contracts with at least one annotated line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`.
