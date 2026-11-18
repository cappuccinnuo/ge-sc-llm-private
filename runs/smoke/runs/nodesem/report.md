# DFG run report

Outer-test, best checkpoint, fold mean (SD), percent.

| task | profile | folds | buggy F1 | macro F1 | precision | recall |
|---|---|---|---|---|---|---|
| access_control_node | S0o@G0 | 1 | 84.01 | 84.39 | 72.42 | 100.00 |
| access_control_node | S0o@G3R | 1 | 84.12 | 84.52 | 72.60 | 100.00 |
| access_control_node | S2@G0 | 1 | 53.94 | 63.46 | 60.49 | 48.68 |
| access_control_node | S2@G3R | 1 | 85.88 | 86.54 | 75.44 | 99.67 |
| access_control_node | S4@G0 | 1 | 77.28 | 75.91 | 63.10 | 99.67 |
| access_control_node | S4@G3R | 1 | 86.74 | 87.47 | 76.79 | 99.67 |

Paired with S0o@G3R (buggy F1, best checkpoint):

| task | profile | mean diff (pp) | improved/tied/worse | p | p Holm |
|---|---|---|---|---|---|
| access_control_node | S0o@G0 | -0.12 | 0/0/1 | - | - |
| access_control_node | S2@G0 | -30.18 | 0/0/1 | - | - |
| access_control_node | S2@G3R | +1.75 | 1/0/0 | - | - |
| access_control_node | S4@G0 | -6.84 | 0/0/1 | - | - |
| access_control_node | S4@G3R | +2.62 | 1/0/0 | - | - |
