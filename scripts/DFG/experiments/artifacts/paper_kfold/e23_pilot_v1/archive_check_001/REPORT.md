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

### best

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 0 | E1 | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 0 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 1 | E0 | 95.2381 | 95.6190 | 100.0000 | 90.9091 |
| 1 | E1 | 95.2381 | 95.6190 | 100.0000 | 90.9091 |
| 1 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 2 | E0 | 91.6667 | 91.2879 | 91.6667 | 91.6667 |
| 2 | E1 | 91.6667 | 91.2879 | 91.6667 | 91.6667 |
| 2 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 3 | E0 | 95.6522 | 95.6522 | 100.0000 | 91.6667 |
| 3 | E1 | 95.6522 | 95.6522 | 100.0000 | 91.6667 |
| 3 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 4 | E0 | 95.2381 | 95.4451 | 100.0000 | 90.9091 |
| 4 | E1 | 95.2381 | 95.4451 | 100.0000 | 90.9091 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 93.5590 +/- 2.5626 | 93.8316 +/- 2.3850 | 98.3333 +/- 3.7268 | 89.3939 +/- 4.2519 |
| E1 | 93.5590 +/- 2.5626 | 93.8316 +/- 2.3850 | 98.3333 +/- 3.7268 | 89.3939 +/- 4.2519 |
| E1-E0 | 0.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0000 +/- 0.0000 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 0 | 5 | 0 |
| macro_f1 | 0 | 5 | 0 |
| precision | 0 | 5 | 0 |
| recall | 0 | 5 | 0 |

Error changes: both_correct=107, e0_wrong_e1_correct=0, e0_correct_e1_wrong=0, both_wrong=7, corrected_fp=0, corrected_fn=0, introduced_fp=0, introduced_fn=0.

### last

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 90.9091 | 91.2879 | 90.9091 | 90.9091 |
| 0 | E1 | 83.3333 | 82.5758 | 76.9231 | 90.9091 |
| 0 | E1-E0 pp | -7.5758 | -8.7121 | -13.9860 | +0.0000 |
| 1 | E0 | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 1 | E1 | 90.0000 | 91.1538 | 100.0000 | 81.8182 |
| 1 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 2 | E0 | 88.0000 | 86.8571 | 84.6154 | 91.6667 |
| 2 | E1 | 88.0000 | 86.8571 | 84.6154 | 91.6667 |
| 2 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 3 | E0 | 75.0000 | 73.8636 | 75.0000 | 75.0000 |
| 3 | E1 | 72.0000 | 69.3333 | 69.2308 | 75.0000 |
| 3 | E1-E0 pp | -3.0000 | -4.5303 | -5.7692 | +0.0000 |
| 4 | E0 | 85.7143 | 86.3354 | 90.0000 | 81.8182 |
| 4 | E1 | 85.7143 | 86.3354 | 90.0000 | 81.8182 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 85.9247 +/- 6.4256 | 85.8996 +/- 7.1171 | 88.1049 +/- 9.1769 | 84.2424 +/- 7.0132 |
| E1 | 83.8095 +/- 7.0569 | 83.2511 +/- 8.3536 | 84.1538 +/- 11.8372 | 84.2424 +/- 7.0132 |
| E1-E0 | -2.1152 +/- 3.3175 | -2.6485 +/- 3.9164 | -3.9510 +/- 6.1408 | 0.0000 +/- 0.0000 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 0 | 3 | 2 |
| macro_f1 | 0 | 3 | 2 |
| precision | 0 | 3 | 2 |
| recall | 0 | 5 | 0 |

Error changes: both_correct=95, e0_wrong_e1_correct=0, e0_correct_e1_wrong=3, both_wrong=16, corrected_fp=0, corrected_fn=0, introduced_fp=3, introduced_fn=0.

### Fit telemetry (not counted twice for best/last)

| Model | Fits | Seconds total | Peak allocated MiB | Peak reserved MiB | Parameters | DDG train edges min-max | DDG gradient sum | Train-unseen relation folds |
|---|---:|---:|---:|---:|---|---|---:|---:|
| E0 | 5 | 308.801 | 1593.42 | 1686.00 | [4510546] | 0-0 | 0.000000 | 5 |
| E1 | 5 | 323.618 | 2130.55 | 2278.00 | [4641874] | 2848-3151 | 29.497752 | 5 |

All 5 paired receipts and their artifact fingerprints verified.

Per-fold epochs, telemetry and error identities are in CSV/JSON.

## reentrancy_author / node

### best

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 99.5904 | 99.4391 | 99.6487 | 99.5322 |
| 0 | E1 | 99.4740 | 99.2783 | 99.4159 | 99.5322 |
| 0 | E1-E0 pp | -0.1164 | -0.1609 | -0.2328 | +0.0000 |
| 1 | E0 | 99.5240 | 99.4189 | 99.4810 | 99.5671 |
| 1 | E1 | 99.5252 | 99.4182 | 99.2255 | 99.8268 |
| 1 | E1-E0 pp | +0.0012 | -0.0007 | -0.2555 | +0.2597 |
| 2 | E0 | 99.8897 | 99.8394 | 99.8897 | 99.8897 |
| 2 | E1 | 99.8345 | 99.7592 | 99.8896 | 99.7795 |
| 2 | E1-E0 pp | -0.0552 | -0.0802 | -0.0001 | -0.1103 |
| 3 | E0 | 99.7368 | 99.6309 | 99.6058 | 99.8682 |
| 3 | E1 | 99.4067 | 99.1708 | 99.4723 | 99.3412 |
| 3 | E1-E0 pp | -0.3301 | -0.4601 | -0.1335 | -0.5270 |
| 4 | E0 | 99.4575 | 99.5004 | 98.9209 | 100.0000 |
| 4 | E1 | 99.4575 | 99.5004 | 98.9209 | 100.0000 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 5 | E0 | 99.3744 | 99.4215 | 99.6416 | 99.1087 |
| 5 | E1 | 99.3756 | 99.4216 | 99.4643 | 99.2870 |
| 5 | E1-E0 pp | +0.0011 | +0.0002 | -0.1773 | +0.1783 |
| 6 | E0 | 99.6275 | 99.5527 | 99.3631 | 99.8933 |
| 6 | E1 | 99.5749 | 99.4885 | 99.1534 | 100.0000 |
| 6 | E1-E0 pp | -0.0525 | -0.0642 | -0.2096 | +0.1067 |
| 7 | E0 | 99.1597 | 99.1976 | 98.8275 | 99.4941 |
| 7 | E1 | 99.0764 | 99.1174 | 98.6622 | 99.4941 |
| 7 | E1-E0 pp | -0.0833 | -0.0802 | -0.1653 | +0.0000 |
| 8 | E0 | 67.1986 | 66.2121 | 52.7121 | 92.6650 |
| 8 | E1 | 67.5579 | 66.7696 | 53.1557 | 92.6650 |
| 8 | E1-E0 pp | +0.3594 | +0.5575 | +0.4436 | +0.0000 |
| 9 | E0 | 97.0213 | 97.8754 | 98.2759 | 95.7983 |
| 9 | E1 | 97.4576 | 98.1834 | 98.2906 | 96.6387 |
| 9 | E1-E0 pp | +0.4364 | +0.3079 | +0.0147 | +0.8403 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 96.0580 +/- 10.1730 | 96.0088 +/- 10.4832 | 94.6366 +/- 14.7388 | 98.5817 +/- 2.4230 |
| E1 | 96.0740 +/- 10.0411 | 96.0107 +/- 10.2829 | 94.5650 +/- 14.5568 | 98.6565 +/- 2.3225 |
| E1-E0 | 0.0161 +/- 0.2242 | 0.0019 +/- 0.2708 | -0.0716 +/- 0.2070 | 0.0748 +/- 0.3417 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 4 | 1 | 5 |
| macro_f1 | 3 | 1 | 6 |
| precision | 2 | 1 | 7 |
| recall | 4 | 4 | 2 |

Error changes: both_correct=11588, e0_wrong_e1_correct=17, e0_correct_e1_wrong=20, both_wrong=411, corrected_fp=9, corrected_fn=8, introduced_fp=13, introduced_fn=7.

### last

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 99.6487 | 99.5195 | 99.7655 | 99.5322 |
| 0 | E1 | 99.1182 | 98.8023 | 99.6454 | 98.5965 |
| 0 | E1-E0 pp | -0.5305 | -0.7172 | -0.1201 | -0.9357 |
| 1 | E0 | 99.6112 | 99.5242 | 99.3966 | 99.8268 |
| 1 | E1 | 99.7838 | 99.7358 | 99.6546 | 99.9134 |
| 1 | E1-E0 pp | +0.1726 | +0.2116 | +0.2580 | +0.0866 |
| 2 | E0 | 99.8897 | 99.8394 | 99.8897 | 99.8897 |
| 2 | E1 | 99.7245 | 99.5983 | 99.6696 | 99.7795 |
| 2 | E1-E0 pp | -0.1652 | -0.2411 | -0.2201 | -0.1103 |
| 3 | E0 | 99.7372 | 99.6305 | 99.4758 | 100.0000 |
| 3 | E1 | 98.9529 | 98.5172 | 98.3095 | 99.6047 |
| 3 | E1-E0 pp | -0.7843 | -1.1133 | -1.1663 | -0.3953 |
| 4 | E0 | 99.4575 | 99.5004 | 98.9209 | 100.0000 |
| 4 | E1 | 99.4575 | 99.5004 | 98.9209 | 100.0000 |
| 4 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 5 | E0 | 99.1023 | 99.1730 | 99.8192 | 98.3957 |
| 5 | E1 | 98.6547 | 98.7596 | 99.2780 | 98.0392 |
| 5 | E1-E0 pp | -0.4476 | -0.4133 | -0.5412 | -0.3565 |
| 6 | E0 | 99.5749 | 99.4885 | 99.1534 | 100.0000 |
| 6 | E1 | 99.6279 | 99.5525 | 99.2585 | 100.0000 |
| 6 | E1-E0 pp | +0.0529 | +0.0640 | +0.1050 | +0.0000 |
| 7 | E0 | 99.4941 | 99.5184 | 99.4941 | 99.4941 |
| 7 | E1 | 99.0764 | 99.1174 | 98.6622 | 99.4941 |
| 7 | E1-E0 pp | -0.4177 | -0.4010 | -0.8319 | +0.0000 |
| 8 | E0 | 77.9171 | 79.0451 | 64.3312 | 98.7775 |
| 8 | E1 | 77.9171 | 79.0451 | 64.3312 | 98.7775 |
| 8 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 9 | E0 | 97.0711 | 97.8957 | 96.6667 | 97.4790 |
| 9 | E1 | 96.6942 | 97.6118 | 95.1220 | 98.3193 |
| 9 | E1-E0 pp | -0.3769 | -0.2839 | -1.5447 | +0.8403 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 97.1504 +/- 6.8062 | 97.3135 +/- 6.4413 | 95.6913 +/- 11.0584 | 99.3395 +/- 0.8549 |
| E1 | 96.9007 +/- 6.7299 | 97.0240 +/- 6.3498 | 95.2852 +/- 10.9595 | 99.2524 +/- 0.7463 |
| E1-E0 | -0.2497 +/- 0.3073 | -0.2894 +/- 0.3994 | -0.4061 +/- 0.5984 | -0.0871 +/- 0.4483 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 2 | 2 | 6 |
| macro_f1 | 2 | 2 | 6 |
| precision | 2 | 2 | 6 |
| recall | 2 | 4 | 4 |

Error changes: both_correct=11709, e0_wrong_e1_correct=13, e0_correct_e1_wrong=43, both_wrong=271, corrected_fp=9, corrected_fn=4, introduced_fp=27, introduced_fn=16.

### Fit telemetry (not counted twice for best/last)

| Model | Fits | Seconds total | Peak allocated MiB | Peak reserved MiB | Parameters | DDG train edges min-max | DDG gradient sum | Train-unseen relation folds |
|---|---:|---:|---:|---:|---|---|---:|---:|
| E0 | 10 | 879.602 | 1391.53 | 1512.00 | [4371010] | 0-0 | 0.000000 | 6 |
| E1 | 10 | 890.973 | 1825.83 | 1962.00 | [4469506] | 1366-1666 | 121.145579 | 6 |

All 10 paired receipts and their artifact fingerprints verified.

Per-fold epochs, telemetry and error identities are in CSV/JSON.

## access_control_author / node

### best

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 99.4652 | 99.4979 | 100.0000 | 98.9362 |
| 0 | E1 | 99.1119 | 99.1635 | 99.2883 | 98.9362 |
| 0 | E1-E0 pp | -0.3533 | -0.3344 | -0.7117 | +0.0000 |
| 1 | E0 | 99.5090 | 99.6093 | 100.0000 | 99.0228 |
| 1 | E1 | 99.0228 | 99.2201 | 99.0228 | 99.0228 |
| 1 | E1-E0 pp | -0.4862 | -0.3892 | -0.9772 | +0.0000 |
| 2 | E0 | 98.6264 | 98.6738 | 100.0000 | 97.2900 |
| 2 | E1 | 98.6264 | 98.6738 | 100.0000 | 97.2900 |
| 2 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 3 | E0 | 97.4560 | 97.6779 | 100.0000 | 95.0382 |
| 3 | E1 | 96.8627 | 97.1410 | 99.5968 | 94.2748 |
| 3 | E1-E0 pp | -0.5932 | -0.5369 | -0.4032 | -0.7634 |
| 4 | E0 | 99.5569 | 99.6738 | 99.1176 | 100.0000 |
| 4 | E1 | 99.8519 | 99.8911 | 99.7041 | 100.0000 |
| 4 | E1-E0 pp | +0.2950 | +0.2173 | +0.5865 | +0.0000 |
| 5 | E0 | 98.1308 | 98.5482 | 100.0000 | 96.3303 |
| 5 | E1 | 97.3561 | 97.9447 | 99.0506 | 95.7187 |
| 5 | E1-E0 pp | -0.7747 | -0.6035 | -0.9494 | -0.6116 |
| 6 | E0 | 99.3443 | 99.4566 | 99.6711 | 99.0196 |
| 6 | E1 | 99.3443 | 99.4566 | 99.6711 | 99.0196 |
| 6 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 7 | E0 | 75.8333 | 82.0104 | 65.4676 | 90.0990 |
| 7 | E1 | 75.9916 | 82.1464 | 65.7040 | 90.0990 |
| 7 | E1-E0 pp | +0.1583 | +0.1360 | +0.2363 | +0.0000 |
| 8 | E0 | 91.9580 | 93.7589 | 85.6678 | 99.2453 |
| 8 | E1 | 92.1191 | 93.8898 | 85.9477 | 99.2453 |
| 8 | E1-E0 pp | +0.1610 | +0.1309 | +0.2800 | +0.0000 |
| 9 | E0 | 99.8435 | 99.8574 | 100.0000 | 99.6875 |
| 9 | E1 | 99.8435 | 99.8574 | 100.0000 | 99.6875 |
| 9 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 95.9723 +/- 7.4499 | 96.8764 +/- 5.5287 | 94.9924 +/- 11.2942 | 97.4669 +/- 3.0370 |
| E1 | 95.8130 +/- 7.3344 | 96.7384 +/- 5.4314 | 94.7985 +/- 11.0848 | 97.3294 +/- 3.1424 |
| E1-E0 | -0.1593 +/- 0.3648 | -0.1380 +/- 0.2997 | -0.1939 +/- 0.5403 | -0.1375 +/- 0.2921 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 3 | 3 | 4 |
| macro_f1 | 3 | 3 | 4 |
| precision | 3 | 3 | 4 |
| recall | 0 | 8 | 2 |

Error changes: both_correct=7486, e0_wrong_e1_correct=4, e0_correct_e1_wrong=13, both_wrong=207, corrected_fp=4, corrected_fn=0, introduced_fp=9, introduced_fn=4.

### last

| Fold | Model | Buggy-F1 | Macro-F1 | Precision | Recall |
|---:|---|---:|---:|---:|---:|
| 0 | E0 | 97.1223 | 97.3189 | 98.5401 | 95.7447 |
| 0 | E1 | 98.9362 | 98.9964 | 98.9362 | 98.9362 |
| 0 | E1-E0 pp | +1.8139 | +1.6775 | +0.3960 | +3.1915 |
| 1 | E0 | 99.0228 | 99.2201 | 99.0228 | 99.0228 |
| 1 | E1 | 99.5090 | 99.6093 | 100.0000 | 99.0228 |
| 1 | E1-E0 pp | +0.4862 | +0.3892 | +0.9772 | +0.0000 |
| 2 | E0 | 98.6264 | 98.6738 | 100.0000 | 97.2900 |
| 2 | E1 | 98.6264 | 98.6738 | 100.0000 | 97.2900 |
| 2 | E1-E0 pp | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 3 | E0 | 97.4560 | 97.6779 | 100.0000 | 95.0382 |
| 3 | E1 | 97.0530 | 97.3188 | 100.0000 | 94.2748 |
| 3 | E1-E0 pp | -0.4029 | -0.3591 | +0.0000 | -0.7634 |
| 4 | E0 | 99.4100 | 99.5653 | 98.8270 | 100.0000 |
| 4 | E1 | 98.8060 | 99.1252 | 99.3994 | 98.2196 |
| 4 | E1-E0 pp | -0.6041 | -0.4401 | +0.5724 | -1.7804 |
| 5 | E0 | 98.1308 | 98.5482 | 100.0000 | 96.3303 |
| 5 | E1 | 97.3396 | 97.9389 | 99.6795 | 95.1070 |
| 5 | E1-E0 pp | -0.7912 | -0.6093 | -0.3205 | -1.2232 |
| 6 | E0 | 99.3443 | 99.4566 | 99.6711 | 99.0196 |
| 6 | E1 | 97.1619 | 97.6757 | 99.3174 | 95.0980 |
| 6 | E1-E0 pp | -2.1823 | -1.7809 | -0.3536 | -3.9216 |
| 7 | E0 | 80.4040 | 85.1865 | 67.9181 | 98.5149 |
| 7 | E1 | 76.9826 | 82.1950 | 63.1746 | 98.5149 |
| 7 | E1-E0 pp | -3.4214 | -2.9915 | -4.7435 | +0.0000 |
| 8 | E0 | 92.1191 | 93.8898 | 85.9477 | 99.2453 |
| 8 | E1 | 91.9580 | 93.7589 | 85.6678 | 99.2453 |
| 8 | E1-E0 pp | -0.1610 | -0.1309 | -0.2800 | +0.0000 |
| 9 | E0 | 96.3746 | 96.5958 | 93.2749 | 99.6875 |
| 9 | E1 | 95.9398 | 96.1723 | 92.4638 | 99.6875 |
| 9 | E1-E0 pp | -0.4348 | -0.4235 | -0.8111 | +0.0000 |

| Model | Buggy-F1 mean +/- std | Macro-F1 mean +/- std | Precision mean +/- std | Recall mean +/- std |
|---|---:|---:|---:|---:|
| E0 | 95.8010 +/- 5.8196 | 96.6133 +/- 4.3615 | 94.3202 +/- 10.2951 | 97.9893 +/- 1.7607 |
| E1 | 95.2313 +/- 6.7664 | 96.1464 +/- 5.1923 | 93.8639 +/- 11.7561 | 97.5396 +/- 1.9913 |
| E1-E0 | -0.5698 +/- 1.4188 | -0.4669 +/- 1.2381 | -0.4563 +/- 1.5924 | -0.4497 +/- 1.7886 |

| Metric | Improved | Tied | Declined |
|---|---:|---:|---:|
| buggy_f1 | 2 | 1 | 7 |
| macro_f1 | 2 | 1 | 7 |
| precision | 3 | 2 | 5 |
| recall | 1 | 5 | 4 |

Error changes: both_correct=7422, e0_wrong_e1_correct=20, e0_correct_e1_wrong=57, both_wrong=211, corrected_fp=11, corrected_fn=9, introduced_fp=33, introduced_fn=24.

### Fit telemetry (not counted twice for best/last)

| Model | Fits | Seconds total | Peak allocated MiB | Peak reserved MiB | Parameters | DDG train edges min-max | DDG gradient sum | Train-unseen relation folds |
|---|---:|---:|---:|---:|---|---|---:|---:|
| E0 | 10 | 797.038 | 954.49 | 1038.00 | [4428466] | 0-0 | 0.000000 | 6 |
| E1 | 10 | 805.595 | 1365.21 | 1486.00 | [4551586] | 2288-2438 | 239.132191 | 7 |

All 10 paired receipts and their artifact fingerprints verified.

Per-fold epochs, telemetry and error identities are in CSV/JSON.

## Attempts and scope

{"attempts_discovered": 30, "current_state_failed": 0, "retry_attempts": 0, "historical_unaccepted_unknown": 0}

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
