# Independent automated result review

**Status: passed. This is automated independent recomputation, not human approval.**

Reviewed 12 formal fits, 180 artifact hashes, and 24 best/last metric and confusion-matrix groups. The independent check verified strict-minimum best selection, delta=0.001/patience=7 counters, checkpoint epochs/bindings, and paired prediction identities. No model was loaded and no training or GPU computation was performed.

| Task | Variant | Best Buggy-F1 | Best Macro-F1 | Best epoch (0-based) |
|---|---|---:|---:|---:|
| reentrancy_author_contract | E2 | 88.8889 | 89.6057 | 6 |
| reentrancy_author_contract | E3a | 88.8889 | 89.6057 | 6 |
| reentrancy_author_contract | E3b | 88.8889 | 89.6057 | 6 |
| access_control_author_contract | E2 | 90.0000 | 91.1538 | 7 |
| access_control_author_contract | E3a | 90.0000 | 91.1538 | 7 |
| access_control_author_contract | E3b | 90.0000 | 91.1538 | 7 |
| reentrancy_author_node | E2 | 99.7071 | 99.5997 | 39 |
| reentrancy_author_node | E3a | 99.6487 | 99.5195 | 30 |
| reentrancy_author_node | E3b | 99.6491 | 99.5191 | 24 |
| access_control_author_node | E2 | 99.2883 | 99.3306 | 20 |
| access_control_author_node | E3a | 99.4652 | 99.4979 | 12 |
| access_control_author_node | E3b | 99.4652 | 99.4979 | 12 |

Both contract tasks have no classification changes. Reentrancy node E3b fixes one error and adds two; access-control node E3a/E3b each fix the same single false positive. Added relations receive nonzero training gradients, but state Def-Use support is sparse. In particular, access-control validation has no STATE_DEF_USE edges, so its one-node correction is not direct evidence of a new state edge helping that validation node.

Last is auxiliary: access-control node last Buggy-F1 is 99.4652 / 98.5866 / 96.7185 (E2 / E3a / E3b). It must not replace the prespecified best rule.

All values are CV validation on fold 0. Do not infer full-K-fold benefit, statistical significance, causal attribution, independent-test generalization, or that state dependencies are ineffective. Node metrics retain the HCG-node definition.

Evidence file SHA256 values, receipt identifiers, detailed best/last results, and paired error counts are preserved in independent_result_review.json.
