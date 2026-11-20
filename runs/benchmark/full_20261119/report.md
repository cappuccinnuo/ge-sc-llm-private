# Benchmark: rebuilt MANDO-LLM pipeline vs. the paper

Reference: MANDO-LLM, ACM TOSEM 2025, Tables 3 and 5 (Dataset A), row `codet5p-770m` (the tokenizer the pipeline uses); `paper best LLM row` is the best of the paper's three tokenizer rows. Scores are fold means (± SD) of the best checkpoint in percent; Δ = ours − paper.

Run settings: `{"categories": ["access_control", "arithmetic", "denial_of_service", "front_running", "reentrancy", "time_manipulation", "unchecked_low_level_calls"], "device": "cuda:0", "epochs": null, "folds": null, "profiles": ["G0"], "protocols": ["paper", "grouped", "upstream"], "seed": 1}`
Code commit: `5118e21cd1105150beab560cc7de0310b5517cdb`

## G0 — paper protocol (held-out fold selects the checkpoint and is scored, as the authors' trainers)

### Contract level (paper Table 3)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 93.56 ± 2.56 | 86.71 | +6.85 | 93.83 ± 2.39 | 85.63 | +8.20 | 87.60 (starcoder) |
| arithmetic | 5 | 92.29 ± 3.44 | 86.82 | +5.47 | 92.47 ± 3.50 | 85.64 | +6.83 | 88.02 (solidity-t5) |
| denial_of_service | 5 | 95.77 ± 2.40 | 91.20 | +4.57 | 95.64 ± 2.44 | 89.90 | +5.74 | 91.20 (codet5p-770m) |
| front_running | 5 | 96.31 ± 3.38 | 95.42 | +0.89 | 96.52 ± 3.18 | 95.54 | +0.98 | 95.42 (codet5p-770m) |
| reentrancy | 5 | 94.85 ± 6.37 | 91.67 | +3.18 | 95.06 ± 5.85 | 91.49 | +3.57 | 94.26 (starcoder) |
| time_manipulation | 5 | 94.73 ± 5.29 | 95.14 | -0.41 | 94.98 ± 5.03 | 94.56 | +0.42 | 96.18 (starcoder) |
| unchecked_low_level_calls | 5 | 92.17 ± 5.99 | 82.23 | +9.94 | 92.10 ± 6.18 | 82.09 | +10.01 | 86.65 (solidity-t5) |
| **mean** |  | 94.24 | 89.88 | +4.36 | 94.37 | 89.26 | +5.11 |  |

### Line level (paper Table 5: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 99.04 ± 0.80 | 94.53 | +4.51 | 96.49 (starcoder) | 97.90 ± 2.31 | 97.29 | 98.54 | 99.8 | 75.3 |
| arithmetic | 10 | 99.52 ± 0.37 | 94.33 | +5.19 | 95.42 (solidity-t5) | 99.58 ± 0.35 | 99.43 | 99.73 | 100.0 | 85.0 |
| denial_of_service | 10 | 99.21 ± 0.68 | 98.19 | +1.02 | 98.23 (solidity-t5) | 95.50 ± 0.59 | 99.11 | 92.15 | 92.6 | 89.0 |
| front_running | 10 | 99.73 ± 0.51 | 94.95 | +4.78 | 95.66 (starcoder) | 99.75 ± 0.51 | 99.57 | 99.92 | 100.0 | 93.0 |
| reentrancy | 10 | 99.49 ± 0.36 | 96.78 | +2.71 | 96.78 (codet5p-770m) | 96.19 ± 0.81 | 98.84 | 93.68 | 94.0 | 84.8 |
| time_manipulation | 10 | 99.73 ± 0.29 | 96.40 | +3.33 | 97.29 (solidity-t5) | 99.76 ± 0.24 | 99.72 | 99.80 | 100.0 | 94.0 |
| unchecked_low_level_calls | 10 | 98.39 ± 1.02 | 96.62 | +1.77 | 96.62 (codet5p-770m) | 98.38 ± 1.01 | 99.12 | 97.66 | 100.0 | 67.3 |
| **mean** |  | 99.30 | 95.97 | +3.33 |  | 98.15 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 93.56 | 97.94 ± 1.51 | 97.36 | 98.55 | 97.87 | 97.48 | 99.06 | 73.6 |
| arithmetic | 5 | 92.29 | 99.39 ± 0.51 | 99.12 | 99.67 | 99.40 | 98.73 | 99.32 | 80.0 |
| denial_of_service | 5 | 95.77 | 95.21 ± 0.96 | 98.57 | 92.07 | 95.39 | 94.08 | 98.72 | 86.9 |
| front_running | 5 | 96.31 | 99.83 ± 0.14 | 99.75 | 99.92 | 99.83 | 99.66 | 99.82 | 90.8 |
| reentrancy | 5 | 94.85 | 96.32 ± 0.09 | 99.02 | 93.77 | 96.30 | 95.76 | 99.49 | 84.8 |
| time_manipulation | 5 | 94.73 | 99.67 ± 0.30 | 99.57 | 99.76 | 99.65 | 99.03 | 99.68 | 92.0 |
| unchecked_low_level_calls | 5 | 92.17 | 98.19 ± 1.31 | 98.83 | 97.57 | 98.19 | 97.52 | 98.17 | 68.4 |

## G0 — grouped protocol (duplicate-disjoint folds, checkpoint selected on inner validation)

### Contract level (paper Table 3)

| category | folds | Buggy-F1 | paper | Δ | Macro-F1 | paper | Δ | paper best LLM row |
|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 91.32 ± 8.20 | 86.71 | +4.61 | 92.05 ± 7.24 | 85.63 | +6.42 | 87.60 (starcoder) |
| arithmetic | 5 | 94.62 ± 3.83 | 86.82 | +7.80 | 94.97 ± 3.51 | 85.64 | +9.33 | 88.02 (solidity-t5) |
| denial_of_service | 5 | 94.60 ± 5.30 | 91.20 | +3.40 | 94.52 ± 5.46 | 89.90 | +4.62 | 91.20 (codet5p-770m) |
| front_running | 5 | 95.29 ± 2.63 | 95.42 | -0.13 | 95.48 ± 2.53 | 95.54 | -0.06 | 95.42 (codet5p-770m) |
| reentrancy | 5 | 94.91 ± 3.31 | 91.67 | +3.24 | 95.06 ± 3.18 | 91.49 | +3.57 | 94.26 (starcoder) |
| time_manipulation | 5 | 95.89 ± 4.22 | 95.14 | +0.75 | 95.99 ± 4.18 | 94.56 | +1.43 | 96.18 (starcoder) |
| unchecked_low_level_calls | 5 | 89.13 ± 3.81 | 82.23 | +6.90 | 88.92 ± 3.91 | 82.09 | +6.83 | 86.65 (solidity-t5) |
| **mean** |  | 93.68 | 89.88 | +3.80 | 93.86 | 89.26 | +4.59 |  |

### Line level (paper Table 5: node scores on vulnerable contracts; plus the same predictions on source lines)

| category | folds | node Buggy-F1 | paper | Δ | paper best LLM row | source-line Buggy-F1 | P | R | line coverage % | contracts hit % |
|---|---|---|---|---|---|---|---|---|---|---|
| access_control | 10 | 98.71 ± 1.49 | 94.53 | +4.18 | 96.49 (starcoder) | 97.53 ± 3.75 | 96.99 | 98.10 | 99.8 | 70.7 |
| arithmetic | 10 | 99.16 ± 0.33 | 94.33 | +4.83 | 95.42 (solidity-t5) | 99.22 ± 0.39 | 99.09 | 99.37 | 100.0 | 80.5 |
| denial_of_service | 10 | 99.06 ± 0.39 | 98.19 | +0.87 | 98.23 (solidity-t5) | 95.43 ± 0.40 | 98.99 | 92.13 | 92.7 | 90.0 |
| front_running | 10 | 99.76 ± 0.19 | 94.95 | +4.81 | 95.66 (starcoder) | 99.79 ± 0.19 | 99.63 | 99.94 | 100.0 | 94.0 |
| reentrancy | 10 | 99.45 ± 0.28 | 96.78 | +2.67 | 96.78 (codet5p-770m) | 96.31 ± 0.32 | 99.11 | 93.66 | 94.1 | 84.5 |
| time_manipulation | 10 | 99.72 ± 0.19 | 96.40 | +3.32 | 97.29 (solidity-t5) | 99.74 ± 0.18 | 99.65 | 99.83 | 100.0 | 94.0 |
| unchecked_low_level_calls | 10 | 98.53 ± 0.38 | 96.62 | +1.91 | 96.62 (codet5p-770m) | 98.53 ± 0.49 | 99.15 | 97.92 | 100.0 | 69.1 |
| **mean** |  | 99.20 | 95.97 | +3.23 |  | 98.08 |  |  |  |  |

### End to end: contract model → line model on every held-out contract

`detector`: lines of contracts the contract model flags; `true contract gate`: the line model on the truly vulnerable contracts only; `no gate`: the line model alone.

| category | folds | contract Buggy-F1 | line Buggy-F1 (detector) | P | R | line, true contract gate | line, no gate | node Buggy-F1 (detector) | vulnerable contracts hit % |
|---|---|---|---|---|---|---|---|---|---|
| access_control | 5 | 91.32 | 97.87 ± 2.32 | 97.52 | 98.23 | 97.82 | 97.45 | 98.87 | 70.3 |
| arithmetic | 5 | 94.62 | 99.47 ± 0.28 | 99.24 | 99.70 | 99.47 | 98.75 | 99.39 | 80.0 |
| denial_of_service | 5 | 94.60 | 95.43 ± 0.39 | 98.95 | 92.16 | 95.53 | 94.59 | 99.02 | 89.3 |
| front_running | 5 | 95.29 | 99.75 ± 0.09 | 99.57 | 99.92 | 99.73 | 99.55 | 99.73 | 91.1 |
| reentrancy | 5 | 94.91 | 96.09 ± 0.29 | 98.73 | 93.59 | 96.09 | 95.47 | 99.21 | 83.0 |
| time_manipulation | 5 | 95.89 | 99.65 ± 0.15 | 99.58 | 99.72 | 99.66 | 99.16 | 99.65 | 90.0 |
| unchecked_low_level_calls | 5 | 89.13 | 98.16 ± 0.32 | 99.16 | 97.19 | 98.14 | 97.76 | 98.16 | 50.5 |

## The authors' trainers on the rebuilt graphs (paper protocol)

| category | contract Buggy-F1 | paper | contract Macro-F1 | line (node) Buggy-F1 | paper |
|---|---|---|---|---|---|
| access_control | 93.56 ± 2.56 | 86.71 | 93.83 ± 2.39 | 99.01 ± 0.81 | 94.53 |
| arithmetic | 95.78 ± 5.87 | 86.82 | 95.82 ± 5.91 | 99.57 ± 0.28 | 94.33 |
| denial_of_service | 97.77 ± 3.06 | 91.20 | 97.82 ± 2.99 | 99.28 ± 0.67 | 98.19 |
| front_running | 96.31 ± 3.38 | 95.42 | 96.52 ± 3.18 | 99.69 ± 0.61 | 94.95 |
| reentrancy | 94.06 ± 5.86 | 91.67 | 94.35 ± 5.28 | 99.38 ± 0.42 | 96.78 |
| time_manipulation | 94.73 ± 5.29 | 95.14 | 94.98 ± 5.03 | 99.68 ± 0.37 | 96.40 |
| unchecked_low_level_calls | 92.06 ± 7.90 | 82.23 | 92.10 ± 7.89 | 98.53 ± 0.95 | 96.62 |

Source lines are preprocessed lines spoken for by node label endpoints (`benchmark/lines.py`); `line coverage` is the share of annotated lines any node speaks for, `contracts hit` the share of vulnerable contracts with at least one annotated line flagged. Per-contract detector output: `findings/<protocol>/<profile>/<category>.json`.
