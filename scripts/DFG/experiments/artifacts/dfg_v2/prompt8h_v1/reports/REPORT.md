# Prompt 8H results

170/170 fits accepted. Primary: L-audit, best by inner validation loss; grouped outer evaluation.

| Task | Profile | BF1 mean | Sample SD |
|---|---|---:|---:|
| access_control_contract | G0 | 91.0199 | 4.2681 |
| access_control_contract | G1R | 92.0589 | 3.1358 |
| access_control_contract | G2R | 92.0589 | 3.1358 |
| access_control_contract | G3 | 93.0075 | 3.4068 |
| access_control_contract | G3R | 93.0075 | 3.4068 |
| access_control_node | G0 | 97.7105 | 3.0655 |
| access_control_node | G0P | 97.5643 | 3.3446 |
| access_control_node | G1R | 97.7369 | 3.6370 |
| access_control_node | G2R | 98.2142 | 3.4705 |
| access_control_node | G3 | 98.1856 | 2.8476 |
| access_control_node | G3R | 98.3536 | 2.9961 |
| reentrancy_contract | G0 | 93.6807 | 3.0938 |
| reentrancy_contract | G1R | 95.1111 | 4.8177 |
| reentrancy_contract | G2R | 95.0159 | 4.8661 |
| reentrancy_contract | G3 | 95.1526 | 5.2800 |
| reentrancy_contract | G3R | 95.0159 | 4.8661 |
| reentrancy_node | G0 | 98.0885 | 0.7907 |
| reentrancy_node | G0P | 98.0312 | 0.8744 |
| reentrancy_node | G1R | 98.2683 | 0.7196 |
| reentrancy_node | G2R | 99.1376 | 0.4561 |
| reentrancy_node | G3 | 98.9613 | 0.4002 |
| reentrancy_node | G3R | 99.1246 | 0.4167 |

Selected G*: G3 (inner validation only).

See paired.csv, holm.csv, orig_all_fold_means.csv, last_fold_means.csv and pooled_oof.csv; folds and pooled scores are separate.
Precision/recall Wilson intervals are descriptive; F1 has no Wilson interval.

Final experiments are intended for a server with sufficient VRAM; current results were run locally with frozen local_dev_v1.
No additional seeds, vulnerability categories, or model extensions were started.
