# DFG run report

Outer-test, best checkpoint, fold mean (SD), percent.

| task | profile | folds | buggy F1 | macro F1 | precision | recall |
|---|---|---|---|---|---|---|
| access_control_contract | G3R | 1 | 90.91 | 91.29 | 90.91 | 90.91 |
| access_control_contract | G4R-A | 1 | 90.91 | 91.29 | 90.91 | 90.91 |
| access_control_contract | G4R-P | 1 | 90.91 | 91.29 | 90.91 | 90.91 |
| access_control_node | G3R | 1 | 80.43 | 80.05 | 67.26 | 100.00 |
| access_control_node | G4R-A | 1 | 80.11 | 79.64 | 66.81 | 100.00 |
| access_control_node | G4R-P | 1 | 80.11 | 79.64 | 66.81 | 100.00 |

Paired with G3R (buggy F1, best checkpoint):

| task | profile | mean diff (pp) | improved/tied/worse | p | p Holm |
|---|---|---|---|---|---|
| access_control_contract | G4R-A | +0.00 | 0/1/0 | - | - |
| access_control_contract | G4R-P | +0.00 | 0/1/0 | - | - |
| access_control_node | G4R-A | -0.32 | 0/0/1 | - | - |
| access_control_node | G4R-P | -0.32 | 0/0/1 | - | - |

Selected profile (inner validation only): **G3R**
