# Stage G fresh-initial replay audit

Status: **complete_passed**; passed pairs: 12/12.

This independent audit only reads completed artifacts. It does not import model libraries, load a GPU, train, or deserialize model tensors.

| Task | Variant | Status | Initial/seed | Binding/config | Scheduler | Complete first 3 history rows |
|---|---|---|---|---|---|---|
| reentrancy_author_contract | E2 | passed | True | True | True | True |
| reentrancy_author_contract | E3a | passed | True | True | True | True |
| reentrancy_author_contract | E3b | passed | True | True | True | True |
| access_control_author_contract | E2 | passed | True | True | True | True |
| access_control_author_contract | E3a | passed | True | True | True | True |
| access_control_author_contract | E3b | passed | True | True | True | True |
| reentrancy_author_node | E2 | passed | True | True | True | True |
| reentrancy_author_node | E3a | passed | True | True | True | True |
| reentrancy_author_node | E3b | passed | True | True | True | True |
| access_control_author_node | E2 | passed | True | True | True | True |
| access_control_author_node | E3a | passed | True | True | True | True |
| access_control_author_node | E3b | passed | True | True | True | True |

Allowed smoke/full differences are mode and the training cap (3 versus 50). Both use the full 50-step OneCycle schedule. The effective-config binding hash therefore differs intentionally.

Detailed checks, exact first-three-epoch JSON records, initial-state hashes, fit seeds and any failures are retained in `fresh_initial_replay_audit.json`.

## Interpretation

- Observed equality is specific to these artifacts and first three epochs; it is not a guarantee of deterministic GPU/DGL training across all processes or environments.
- Checkpoint roundtrip exactness checks repeated eval after restoring the same checkpoint; it is a different claim from retraining replay.
- Recorded initial tensor digests are checked against the sealed untrained initialization record and its binary SHA; tensors are not deserialized in this independent audit.
