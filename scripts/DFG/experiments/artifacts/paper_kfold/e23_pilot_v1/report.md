# Stage G fold-0 pilot results

All primary values are **CV validation**, selected by minimum validation loss and scored on the same fold.
These are four separate tasks, not an independent test or a complete K-fold experiment.

| Task | Variant | Best Buggy-F1 | Best Macro-F1 | Precision | Recall | Best epoch (0-based) |
|---|---|---:|---:|---:|---:|---:|
| reentrancy_author_contract | E2 | 88.8889 | 89.6057 | 100.0000 | 80.0000 | 6 |
| reentrancy_author_contract | E3a | 88.8889 | 89.6057 | 100.0000 | 80.0000 | 6 |
| reentrancy_author_contract | E3b | 88.8889 | 89.6057 | 100.0000 | 80.0000 | 6 |
| access_control_author_contract | E2 | 90.0000 | 91.1538 | 100.0000 | 81.8182 | 7 |
| access_control_author_contract | E3a | 90.0000 | 91.1538 | 100.0000 | 81.8182 | 7 |
| access_control_author_contract | E3b | 90.0000 | 91.1538 | 100.0000 | 81.8182 | 7 |
| reentrancy_author_node | E2 | 99.7071 | 99.5997 | 99.8826 | 99.5322 | 39 |
| reentrancy_author_node | E3a | 99.6487 | 99.5195 | 99.7655 | 99.5322 | 30 |
| reentrancy_author_node | E3b | 99.6491 | 99.5191 | 99.6491 | 99.6491 | 24 |
| access_control_author_node | E2 | 99.2883 | 99.3306 | 99.6429 | 98.9362 | 20 |
| access_control_author_node | E3a | 99.4652 | 99.4979 | 100.0000 | 98.9362 | 12 |
| access_control_author_node | E3b | 99.4652 | 99.4979 | 100.0000 | 98.9362 | 12 |

Last checkpoints are auxiliary and appear separately in last_summary.csv.
paired_deltas.csv reports percentage-point differences; error_changes.csv includes prediction flips and probability-only changes.
No task-average, standard deviation, significance, or generalization claim is computed.
