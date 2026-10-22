# Four-cell CV validation tables

Generated from sealed input identities and independently checked predictions. Metrics in percent; differences in percentage points. Fold SD is sample SD, not repeated-seed uncertainty.

## reentrancy_author_contract

### best

| Fold | HCG mean BF1/MF1 | HCG attention BF1/MF1 | Enhanced mean BF1/MF1 | Enhanced attention BF1/MF1 |
| --- | --- | --- | --- | --- |
| 0 | 84.6154 / 86.0577 | 84.6154 / 86.0577 | 84.6154 / 86.0577 | 84.6154 / 86.0577 |
| 1 | 100.0000 / 100.0000 | 100.0000 / 100.0000 | 100.0000 / 100.0000 | 100.0000 / 100.0000 |
| 2 | 96.5517 / 96.4240 | 93.3333 / 92.8205 | 96.5517 / 96.4240 | 96.5517 / 96.4240 |
| 3 | 96.2963 / 96.4240 | 96.2963 / 96.4240 | 96.2963 / 96.4240 | 96.2963 / 96.4240 |
| 4 | 93.3333 / 92.8205 | 93.3333 / 92.8205 | 93.3333 / 92.8205 | 93.3333 / 92.8205 |

| Cell | BF1 mean +/- SD | MF1 mean +/- SD | Precision | Recall |
| --- | --- | --- | --- | --- |
| HCG:mean | 94.1593 +/- 5.8347 | 94.3452 +/- 5.2827 | 96.1667 | 93.2381 |
| HCG:attention | 93.5157 +/- 5.6802 | 93.6245 +/- 5.1729 | 95.0000 | 93.2381 |
| HCG_DDG_GUARD:mean | 94.1593 +/- 5.8347 | 94.3452 +/- 5.2827 | 96.1667 | 93.2381 |
| HCG_DDG_GUARD:attention | 94.1593 +/- 5.8347 | 94.3452 +/- 5.2827 | 96.1667 | 93.2381 |

| Contrast | BF1 delta mean +/- SD | Improved / tied / declined | Fixed / regressed |
| --- | --- | --- | --- |
| HCG:attention-HCG:mean | -0.6437 +/- 1.4393 | 0 / 4 / 1 | 0 / 1 |
| HCG_DDG_GUARD:attention-HCG_DDG_GUARD:mean | +0.0000 +/- 0.0000 | 0 / 5 / 0 | 1 / 1 |
| HCG_DDG_GUARD:mean-HCG:mean | +0.0000 +/- 0.0000 | 0 / 5 / 0 | 0 / 0 |
| HCG_DDG_GUARD:attention-HCG:attention | +0.6437 +/- 1.4393 | 1 / 4 / 0 | 1 / 0 |

| Cell | Pooled BF1 | Pooled MF1 | TN/FP/FN/TP |
| --- | --- | --- | --- |
| HCG:mean | 94.2857 | 94.3651 | [68, 3, 5, 66] |
| HCG:attention | 93.6170 | 93.6617 | [67, 4, 5, 66] |
| HCG_DDG_GUARD:mean | 94.2857 | 94.3651 | [68, 3, 5, 66] |
| HCG_DDG_GUARD:attention | 94.2857 | 94.3651 | [68, 3, 5, 66] |

### last

| Fold | HCG mean BF1/MF1 | HCG attention BF1/MF1 | Enhanced mean BF1/MF1 | Enhanced attention BF1/MF1 |
| --- | --- | --- | --- | --- |
| 0 | 92.8571 / 93.0952 | 88.8889 / 89.6057 | 88.8889 / 89.6057 | 88.8889 / 89.6057 |
| 1 | 85.7143 / 86.1905 | 100.0000 / 100.0000 | 89.6552 / 89.6552 | 96.5517 / 96.5517 |
| 2 | 89.6552 / 89.2720 | 93.3333 / 92.8205 | 93.3333 / 92.8205 | 93.3333 / 92.8205 |
| 3 | 89.6552 / 89.2720 | 89.6552 / 89.2720 | 89.6552 / 89.2720 | 89.6552 / 89.2720 |
| 4 | 96.5517 / 96.4240 | 93.3333 / 92.8205 | 96.5517 / 96.4240 | 93.3333 / 92.8205 |

| Cell | BF1 mean +/- SD | MF1 mean +/- SD | Precision | Recall |
| --- | --- | --- | --- | --- |
| HCG:mean | 90.8867 +/- 4.0547 | 90.8508 +/- 3.9624 | 90.4762 | 91.6190 |
| HCG:attention | 93.0421 +/- 4.3961 | 92.9038 +/- 4.3138 | 92.3333 | 94.5714 |
| HCG_DDG_GUARD:mean | 91.6169 +/- 3.2572 | 91.5555 +/- 3.0794 | 90.8333 | 93.1429 |
| HCG_DDG_GUARD:attention | 92.3525 +/- 3.1157 | 92.2141 +/- 2.9585 | 91.0000 | 94.5714 |

| Contrast | BF1 delta mean +/- SD | Improved / tied / declined | Fixed / regressed |
| --- | --- | --- | --- |
| HCG:attention-HCG:mean | +2.1554 +/- 7.4244 | 2 / 1 / 2 | 6 / 3 |
| HCG_DDG_GUARD:attention-HCG_DDG_GUARD:mean | +0.7356 +/- 3.7153 | 1 / 3 / 1 | 3 / 2 |
| HCG_DDG_GUARD:mean-HCG:mean | +0.7302 +/- 3.2458 | 2 / 2 / 1 | 2 / 1 |
| HCG_DDG_GUARD:attention-HCG:attention | -0.6897 +/- 1.5421 | 0 / 4 / 1 | 0 / 1 |

| Cell | Pooled BF1 | Pooled MF1 | TN/FP/FN/TP |
| --- | --- | --- | --- |
| HCG:mean | 90.9091 | 90.8446 | [64, 7, 6, 65] |
| HCG:attention | 93.0556 | 92.9563 | [65, 6, 4, 67] |
| HCG_DDG_GUARD:mean | 91.6667 | 91.5476 | [64, 7, 5, 66] |
| HCG_DDG_GUARD:attention | 92.4138 | 92.2501 | [64, 7, 4, 67] |

## access_control_author_contract

### best

| Fold | HCG mean BF1/MF1 | HCG attention BF1/MF1 | Enhanced mean BF1/MF1 | Enhanced attention BF1/MF1 |
| --- | --- | --- | --- | --- |
| 0 | 90.0000 / 91.1538 | 90.0000 / 91.1538 | 90.0000 / 91.1538 | 90.0000 / 91.1538 |
| 1 | 95.2381 / 95.6190 | 95.2381 / 95.6190 | 95.2381 / 95.6190 | 84.2105 / 86.5497 |
| 2 | 91.6667 / 91.2879 | 91.6667 / 91.2879 | 91.6667 / 91.2879 | 91.6667 / 91.2879 |
| 3 | 95.6522 / 95.6522 | 91.6667 / 91.2879 | 95.6522 / 95.6522 | 91.6667 / 91.2879 |
| 4 | 95.2381 / 95.4451 | 95.2381 / 95.4451 | 95.2381 / 95.4451 | 95.2381 / 95.4451 |

| Cell | BF1 mean +/- SD | MF1 mean +/- SD | Precision | Recall |
| --- | --- | --- | --- | --- |
| HCG:mean | 93.5590 +/- 2.5626 | 93.8316 +/- 2.3850 | 98.3333 | 89.3939 |
| HCG:attention | 92.7619 +/- 2.3606 | 92.9588 +/- 2.3506 | 96.6667 | 89.3939 |
| HCG_DDG_GUARD:mean | 93.5590 +/- 2.5626 | 93.8316 +/- 2.3850 | 98.3333 | 89.3939 |
| HCG_DDG_GUARD:attention | 90.5564 +/- 4.0300 | 91.1449 +/- 3.1484 | 96.6667 | 85.7576 |

| Contrast | BF1 delta mean +/- SD | Improved / tied / declined | Fixed / regressed |
| --- | --- | --- | --- |
| HCG:attention-HCG:mean | -0.7971 +/- 1.7824 | 0 / 4 / 1 | 0 / 1 |
| HCG_DDG_GUARD:attention-HCG_DDG_GUARD:mean | -3.0026 +/- 4.8066 | 0 / 3 / 2 | 0 / 3 |
| HCG_DDG_GUARD:mean-HCG:mean | +0.0000 +/- 0.0000 | 0 / 5 / 0 | 0 / 0 |
| HCG_DDG_GUARD:attention-HCG:attention | -2.2055 +/- 4.9317 | 0 / 4 / 1 | 0 / 2 |

| Cell | Pooled BF1 | Pooled MF1 | TN/FP/FN/TP |
| --- | --- | --- | --- |
| HCG:mean | 93.5780 | 93.8478 | [56, 1, 6, 51] |
| HCG:attention | 92.7273 | 92.9738 | [55, 2, 6, 51] |
| HCG_DDG_GUARD:mean | 93.5780 | 93.8478 | [56, 1, 6, 51] |
| HCG_DDG_GUARD:attention | 90.7407 | 91.2037 | [55, 2, 8, 49] |

### last

| Fold | HCG mean BF1/MF1 | HCG attention BF1/MF1 | Enhanced mean BF1/MF1 | Enhanced attention BF1/MF1 |
| --- | --- | --- | --- | --- |
| 0 | 90.9091 / 91.2879 | 90.9091 / 91.2879 | 83.3333 / 82.5758 | 90.9091 / 91.2879 |
| 1 | 90.0000 / 91.1538 | 75.0000 / 73.8636 | 90.0000 / 91.1538 | 78.2609 / 78.2609 |
| 2 | 88.0000 / 86.8571 | 88.0000 / 86.8571 | 91.6667 / 91.2879 | 88.0000 / 86.8571 |
| 3 | 75.0000 / 73.8636 | 66.6667 / 59.6491 | 72.0000 / 69.3333 | 72.0000 / 69.3333 |
| 4 | 85.7143 / 86.3354 | 83.3333 / 81.6667 | 85.7143 / 86.3354 | 83.3333 / 81.6667 |

| Cell | BF1 mean +/- SD | MF1 mean +/- SD | Precision | Recall |
| --- | --- | --- | --- | --- |
| HCG:mean | 85.9247 +/- 6.4256 | 85.8996 +/- 7.1171 | 88.1049 | 84.2424 |
| HCG:attention | 80.7818 +/- 9.9227 | 78.6649 +/- 12.4511 | 76.3357 | 86.0606 |
| HCG_DDG_GUARD:mean | 84.5429 +/- 7.7571 | 84.1372 +/- 9.0387 | 85.5641 | 84.2424 |
| HCG_DDG_GUARD:attention | 82.5007 +/- 7.5809 | 81.4812 +/- 8.4120 | 79.3357 | 86.0606 |

| Contrast | BF1 delta mean +/- SD | Improved / tied / declined | Fixed / regressed |
| --- | --- | --- | --- |
| HCG:attention-HCG:mean | -5.1429 +/- 6.4782 | 0 / 2 / 3 | 5 / 13 |
| HCG_DDG_GUARD:attention-HCG_DDG_GUARD:mean | -2.0422 +/- 6.9545 | 1 / 1 / 3 | 7 / 10 |
| HCG_DDG_GUARD:mean-HCG:mean | -1.3818 +/- 4.1919 | 1 / 2 / 2 | 1 / 3 |
| HCG_DDG_GUARD:attention-HCG:attention | +1.7188 +/- 2.4650 | 2 / 3 / 0 | 3 / 0 |

| Cell | Pooled BF1 | Pooled MF1 | TN/FP/FN/TP |
| --- | --- | --- | --- |
| HCG:mean | 85.7143 | 85.9606 | [50, 7, 9, 48] |
| HCG:attention | 80.3279 | 78.8432 | [41, 16, 8, 49] |
| HCG_DDG_GUARD:mean | 84.2105 | 84.2105 | [48, 9, 9, 48] |
| HCG_DDG_GUARD:attention | 82.3529 | 81.5434 | [44, 13, 8, 49] |

