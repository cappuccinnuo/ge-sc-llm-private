# DFG run report

Outer-test, best checkpoint, fold mean (SD), percent.

| task | profile | folds | buggy F1 | macro F1 | precision | recall |
|---|---|---|---|---|---|---|
| access_control_contract | G0 | 1 | 90.91 | 91.29 | 90.91 | 90.91 |
| access_control_contract | G3R | 1 | 90.91 | 91.29 | 90.91 | 90.91 |
| access_control_node | G0 | 1 | 84.01 | 84.39 | 72.42 | 100.00 |
| access_control_node | G3R | 1 | 84.12 | 84.52 | 72.60 | 100.00 |

Paired with G0 (buggy F1, best checkpoint):

| task | profile | mean diff (pp) | improved/tied/worse | p | p Holm |
|---|---|---|---|---|---|
| access_control_contract | G3R | +0.00 | 0/1/0 | - | - |
| access_control_node | G3R | +0.12 | 1/0/0 | - | - |

Selected profile (inner validation only): **G3R**
