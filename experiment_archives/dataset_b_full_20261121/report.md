# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper (Dataset B)

Reference: MANDO-LLM, ACM TOSEM 2025, Tables 4 and 6 (Dataset B), row `codet5p-770m` (the tokenizer the pipeline uses); `paper best LLM row` is the best of the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; Δ = ours − paper.

Run settings: `{"categories": ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy", "time_manipulation", "unchecked_low_level_calls"], "device": "cuda:0", "epochs": null, "folds": null, "labels": "public", "profiles": ["G0"], "protocols": ["paper", "grouped", "upstream"], "seed": 1, "tracks": ["contract", "line", "cascade"]}`
Code commit: `49e44b2c0c1594ef076cfbbfc693de0e62d84d8f`

## G0 — paper protocol (held-out fold selects the checkpoint and is scored, as the authors' trainers)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 91.59 ± 4.10 | 85.71 | +5.88 | 91.66 ± 3.90 | 85.71 | +5.95 | 92.30 (solidity-t5) |
| arithmetic | 5 | 91.43 ± 2.37 | 84.93 | +6.50 | 91.52 ± 2.45 | 85.32 | +6.20 | 89.47 (starcoder) |
| denial_of_service | 5 | 96.12 ± 2.45 | 94.12 | +2.00 | 96.10 ± 2.47 | 93.73 | +2.37 | 94.12 (codet5p-770m) |
| front_running | 5 | 94.72 ± 4.12 | 88.00 | +6.72 | 94.77 ± 4.13 | 88.23 | +6.54 | 90.57 (starcoder) |
| reentrancy | 5 | 94.18 ± 2.68 | 92.54 | +1.64 | 94.11 ± 2.75 | 92.30 | +1.81 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 94.18 ± 4.63 | 97.14 | -2.96 | 94.18 ± 4.63 | 97.06 | -2.88 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 93.50 ± 3.49 | 88.46 | +5.04 | 93.37 ± 3.73 | 87.98 | +5.39 | 88.46 (codet5p-770m) |
| **mean** |  | 93.68 | 90.13 | +3.55 | 93.67 | 90.05 | +3.63 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 87.29 ± 10.18 | 71.78 | +15.51 | 75.29 (solidity-t5) | 91.64 ± 7.39 | 84.08 | 84.56 ± 11.40 | 95.33 | 77.21 | 92.6 | 49.2 |
| arithmetic | 10 | 89.92 ± 5.18 | 87.65 | +2.27 | 88.47 (starcoder) | 93.58 ± 3.14 | 91.15 | 89.22 ± 6.77 | 97.58 | 82.77 | 95.3 | 30.5 |
| denial_of_service | 10 | 88.80 ± 5.72 | 72.40 | +16.40 | 72.40 (codet5p-770m) | 93.20 ± 3.06 | 83.08 | 85.46 ± 5.26 | 94.21 | 78.46 | 90.1 | 56.5 |
| front_running | 10 | 95.60 ± 3.54 | 91.73 | +3.87 | 92.82 (starcoder) | 96.29 ± 2.44 | 93.54 | 94.56 ± 3.70 | 98.23 | 91.29 | 97.4 | 46.9 |
| reentrancy | 10 | 90.34 ± 5.27 | 84.77 | +5.57 | 85.47 (solidity-t5) | 93.43 ± 3.11 | 89.12 | 85.45 ± 6.71 | 95.67 | 77.52 | 89.7 | 44.7 |
| time_manipulation | 10 | 98.82 ± 0.54 | 82.54 | +16.28 | 82.54 (codet5p-770m) | 99.04 ± 0.38 | 87.27 | 98.72 ± 0.71 | 99.23 | 98.23 | 99.7 | 59.9 |
| unchecked_low_level_calls | 10 | 90.46 ± 12.70 | 89.32 | +1.14 | 91.14 (starcoder) | 94.62 ± 6.66 | 93.72 | 86.28 ± 16.72 | 98.07 | 79.76 | 93.7 | 43.8 |
| **mean** |  | 91.60 | 82.88 | +8.72 |  |  |  | 89.18 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 91.59 | 84.79 ± 5.78 | 95.27 | 76.86 | 84.81 | 84.50 | 88.60 | 47.5 |
| arithmetic | 5 | 91.43 | 89.12 ± 5.34 | 96.58 | 83.08 | 89.28 | 88.15 | 89.34 | 30.6 |
| denial_of_service | 5 | 96.12 | 84.99 ± 2.96 | 92.71 | 78.49 | 85.09 | 84.03 | 88.30 | 53.3 |
| front_running | 5 | 94.72 | 94.93 ± 1.84 | 98.27 | 91.83 | 94.95 | 92.97 | 95.99 | 45.1 |
| reentrancy | 5 | 94.18 | 86.32 ± 4.33 | 96.06 | 78.64 | 86.36 | 85.73 | 91.00 | 42.3 |
| time_manipulation | 5 | 94.18 | 98.70 ± 0.63 | 99.17 | 98.24 | 98.69 | 98.39 | 98.81 | 59.3 |
| unchecked_low_level_calls | 5 | 93.50 | 88.73 ± 5.89 | 96.81 | 82.29 | 88.79 | 88.21 | 92.46 | 43.7 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 85.71 | 3.44 | 2.70 | 1.79 | 90.91 | 97.33 | 96.84 | 98.24 |
| arithmetic | 88.12 | 7.00 | 3.77 | 2.57 | 88.50 | 99.44 | 99.51 | 99.26 |
| denial_of_service | 94.29 | 17.73 | 14.90 | 10.92 | 93.46 | 98.97 | 95.30 | 94.82 |
| front_running | 91.03 | 5.36 | 3.71 | 0.94 | 95.24 | 99.61 | 99.64 | 99.71 |
| reentrancy | 91.56 | 5.60 | 4.49 | 3.99 | 90.09 | 99.28 | 96.27 | 96.14 |
| time_manipulation | 86.11 | 1.61 | 1.47 | 1.49 | 95.24 | 99.80 | 99.79 | 99.75 |
| unchecked_low_level_calls | 88.89 | 1.74 | 1.08 | 1.37 | 91.74 | 99.78 | 99.74 | 99.45 |

## G0 — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 4)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 92.77 ± 2.86 | 85.71 | +7.06 | 92.48 ± 3.19 | 85.71 | +6.77 | 92.30 (solidity-t5) |
| arithmetic | 5 | 91.37 ± 3.45 | 84.93 | +6.44 | 91.53 ± 3.39 | 85.32 | +6.21 | 89.47 (starcoder) |
| denial_of_service | 5 | 95.58 ± 1.97 | 94.12 | +1.46 | 95.45 ± 2.13 | 93.73 | +1.72 | 94.12 (codet5p-770m) |
| front_running | 5 | 94.39 ± 0.94 | 88.00 | +6.39 | 94.34 ± 0.93 | 88.23 | +6.11 | 90.57 (starcoder) |
| reentrancy | 5 | 94.25 ± 3.02 | 92.54 | +1.71 | 94.11 ± 3.13 | 92.30 | +1.81 | 92.54 (codet5p-770m) |
| time_manipulation | 5 | 94.00 ± 4.37 | 97.14 | -3.14 | 94.18 ± 4.09 | 97.06 | -2.88 | 97.14 (codet5p-770m) |
| unchecked_low_level_calls | 5 | 94.91 ± 5.00 | 88.46 | +6.45 | 95.02 ± 4.80 | 87.98 | +7.04 | 88.46 (codet5p-770m) |
| **mean** |  | 93.90 | 90.13 | +3.77 | 93.87 | 90.05 | +3.83 |  |

### Line level (paper Table 6: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | node Macro-F1 | paper | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 88.00 ± 6.64 | 71.78 | +16.22 | 75.29 (solidity-t5) | 92.18 ± 4.40 | 84.08 | 84.42 ± 9.39 | 93.18 | 78.47 | 92.3 | 51.7 |
| arithmetic | 10 | 89.90 ± 6.66 | 87.65 | +2.25 | 88.47 (starcoder) | 93.56 ± 4.11 | 91.15 | 89.65 ± 7.24 | 97.01 | 83.89 | 95.7 | 31.7 |
| denial_of_service | 10 | 88.61 ± 2.84 | 72.40 | +16.21 | 72.40 (codet5p-770m) | 92.95 ± 1.64 | 83.08 | 85.34 ± 3.12 | 93.36 | 78.72 | 90.0 | 52.7 |
| front_running | 10 | 95.95 ± 2.36 | 91.73 | +4.22 | 92.82 (starcoder) | 96.34 ± 2.04 | 93.54 | 94.89 ± 2.75 | 98.18 | 91.92 | 97.6 | 46.9 |
| reentrancy | 10 | 90.59 ± 3.36 | 84.77 | +5.82 | 85.47 (solidity-t5) | 93.50 ± 2.15 | 89.12 | 85.75 ± 4.56 | 95.76 | 78.09 | 89.9 | 42.8 |
| time_manipulation | 10 | 98.65 ± 0.54 | 82.54 | +16.11 | 82.54 (codet5p-770m) | 98.90 ± 0.41 | 87.27 | 98.52 ± 0.63 | 98.97 | 98.09 | 99.7 | 58.3 |
| unchecked_low_level_calls | 10 | 93.18 ± 4.06 | 89.32 | +3.86 | 91.14 (starcoder) | 95.98 ± 2.36 | 93.72 | 89.71 ± 7.64 | 98.18 | 83.35 | 95.1 | 42.9 |
| **mean** |  | 92.12 | 82.88 | +9.24 |  |  |  | 89.75 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 92.77 | 84.54 ± 7.05 | 93.60 | 77.73 | 84.66 | 84.25 | 88.11 | 47.5 |
| arithmetic | 5 | 91.37 | 89.66 ± 3.02 | 96.75 | 83.71 | 89.75 | 88.48 | 89.82 | 29.0 |
| denial_of_service | 5 | 95.58 | 85.55 ± 2.08 | 93.46 | 78.93 | 85.57 | 84.61 | 88.92 | 52.6 |
| front_running | 5 | 94.39 | 94.87 ± 1.80 | 97.82 | 92.14 | 94.89 | 93.24 | 95.88 | 46.0 |
| reentrancy | 5 | 94.25 | 84.96 ± 4.88 | 95.09 | 77.23 | 85.94 | 85.00 | 89.37 | 42.3 |
| time_manipulation | 5 | 94.00 | 98.51 ± 0.54 | 98.92 | 98.11 | 98.55 | 98.18 | 98.65 | 58.2 |
| unchecked_low_level_calls | 5 | 94.91 | 89.82 ± 5.44 | 97.91 | 83.20 | 89.82 | 89.41 | 93.29 | 44.7 |

### By contract source (Buggy-F1, pooled over folds)

Each source's vulnerable contracts with all clean contracts (contract, detector) or alone (line): what the model does on SolidiFI's injected templates versus real-world code.

| category | DAppSCAN: contract | line (nodes) | line (source lines) | detector lines | SolidiFI: contract | line (nodes) | line (source lines) | detector lines |
|---|---|---|---|---|---|---|---|---|
| access_control | 87.84 | 3.82 | 3.24 | 1.71 | 88.50 | 98.72 | 97.93 | 97.95 |
| arithmetic | 88.03 | 4.97 | 3.79 | 1.88 | 89.29 | 99.42 | 99.49 | 99.22 |
| denial_of_service | 93.46 | 11.10 | 9.57 | 10.35 | 90.91 | 98.33 | 94.76 | 94.98 |
| front_running | 90.67 | 1.82 | 1.30 | 1.50 | 92.59 | 99.60 | 99.59 | 99.60 |
| reentrancy | 92.17 | 5.59 | 4.32 | 4.46 | 87.50 | 99.14 | 96.14 | 95.01 |
| time_manipulation | 85.29 | 0.00 | 0.00 | 0.00 | 97.09 | 99.72 | 99.71 | 99.68 |
| unchecked_low_level_calls | 91.43 | 1.15 | 0.71 | 2.46 | 95.24 | 99.74 | 99.70 | 99.72 |

## The authors' trainers on the rebuilt graphs (paper protocol)

| category | contract Buggy-F1 | paper | contract Macro-F1 | line (node) Buggy-F1 | paper |
|---|---|---|---|---|---|
| access_control | 91.24 ± 4.34 | 85.71 | 91.25 ± 4.27 | 87.45 ± 9.72 | 71.78 |
| arithmetic | 92.64 ± 2.52 | 84.93 | 92.62 ± 2.48 | 89.70 ± 5.35 | 87.65 |
| denial_of_service | 96.11 ± 2.93 | 94.12 | 96.09 ± 2.96 | 88.78 ± 6.11 | 72.40 |
| front_running | 95.15 ± 4.37 | 88.00 | 95.18 ± 4.37 | 95.48 ± 3.82 | 91.73 |
| reentrancy | 95.08 ± 2.07 | 92.54 | 95.03 ± 2.03 | 90.05 ± 5.43 | 84.77 |
| time_manipulation | 94.75 ± 4.40 | 97.14 | 94.75 ± 4.37 | 98.77 ± 0.67 | 82.54 |
| unchecked_low_level_calls | 91.73 ± 4.89 | 88.46 | 91.72 ± 4.90 | 90.32 ± 12.50 | 89.32 |

Source lines are preprocessed lines spoken for by node label endpoints (`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks for, `contracts hit` the share of vulnerable contracts with at least one annotated line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`.
