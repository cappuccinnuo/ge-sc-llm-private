# Stage G finite relation and Oracle review

Date: 2026-10-14. Reviewer: Codex separate review agent. Worktree HEAD supplied: c311c93927138f3fab3aab94b9afa6e63c90269e.

Result: no concrete semantic blocker was found in the frozen finite review. This gate permits the parent workflow to proceed to real-graph/schema/resource validation, not to claim complete Solidity soundness or a human-approved Oracle. No training, graph regeneration, frozen input edit, Stage F core change, or compilation occurred in this review.

## Fixed scope and evidence

- All 17 unique contract-graph STATE_DEF_USE edges: 6 reentrancy and 11 access control. Duplicate proofs sharing one endpoint/relation pair were all checked.
- Seed 1 deterministic semantic-diversity sampling: 8 STATE_ACCESS_ORDER edges across 8 functions / 8 normalized text templates, including 3 branching functions; 8 EXTERNAL_CALL_BEFORE_STATE_WRITE edges across 8 functions / 8 normalized templates, including 5 branching functions. The former includes both categories; access control has no frozen CALL->WRITE edges to sample.
- Strata use cohort, READ/WRITE kind pair, branching, call detail, key kind, normalized statement template and function identity. Labels, predictions and accuracy were not read for sampling. Injection suffix numbers are normalized before selecting template diversity. Text templates are not independently identified dataset injection-template IDs.
- `relation_evidence_index.json`: frozen hashes, identities, declarations, endpoint byte spans, projected node IDs, witnesses, selection policy. `source_snippets.md`: exact source excerpts. `static_source_review.json`: per-edge reviewer observations.
- `oracle_review.json`: all 20 frozen Oracle source hashes and source-defined assertions passed. Seven unsupported cases retain function fallback with zero partial facts. Thirteen supported cases remain explicitly limited to the supported subset.

## Independent checks and source review

The audit reads existing JSON and exact source bytes. It does not call the Stage F relation generator to validate itself. It separately builds adjacency over the saved event order and CFG successor lists. Every order witness is replayed; skipping events or invalid branch transitions fails. Def-Use is checked for WRITE->READ, exact declaration/location identity and an existing path without HAVOC or a strong same-location overwrite. Distinct state roots do not kill each other; branch bypass union is retained. All declaration SHA/byte spans are checked. Any unknown root/key evidence cannot be promoted to an EXACT data edge.

Access-order samples were checked for absence of an intervening same/MAY-location access. CALL->WRITE samples require an actual confirmed external-call event and the next state write on the witness. Calls inside a condition or require are still calls; a failed/reverted branch is not connected to a write on an incompatible successor. Same-node projection is checked by an existing regression, while reviewed serialized model edges have distinct endpoint IDs.

Source review found no wrong direction, cross-declaration binding or invented definite dependence among the selected edges. The frozen projected node IDs are read from hashed Stage F evidence; this JSON-only review does not independently deserialize graph files. Actual model endpoints and node/edge/label invariants remain mandatory checks in the parent real-graph integration gate.

Important interpretation: 12 of the 17 Def-Use edges occur in constructors. The remaining 5 come from one access-control pricing function: assignment to bonusCalculationFactor followed by conditional reads. These are legitimate dependencies but do not demonstrate that runtime balance/permission paths are now covered. E3b order samples include send/transfer/call followed by writes to balances, addresses, counters and booleans. They express structural order, not a vulnerability or unchanged state value across a call. Path predicates, gas behavior and exploitability are not proven.

## Oracle review boundary

The nine real Oracle functions were read from exact source spans. O1/O3/O5/O6/O8/O9 remain conservative fallbacks: unresolved version, complex mapping/alias, modifier, arrays or binding restrictions. O2 has entry reads plus opaque call/state update but no fake forward definition. O4 owner guard is an entry read rather than constructor-to-function or control-as-data relation. O7 contains only local/parameter arithmetic. Eleven synthetic cases cover different constant keys, MAY keys, branch union/KILL, loop-carried definitions, call HAVOC and absence of transitive closure. Existing frozen expectations were neither overwritten nor derived from new performance results.

`human_approved=false`, `compiled=false` for every reviewed case. This is an independent Codex static pass plus automated checks, not independent human approval or solc language validation. Unsupported syntax examples remain parser/semantic robustness cases. The old Oracle approval status is unchanged.

## Tests and commands

Run from the development worktree with existing mando Python and TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64; PYTHONDONTWRITEBYTECODE=1.

```bash
python -B scripts/DFG/experiments/e23_pilot/review/review_relations.py
python -B scripts/DFG/experiments/e23_pilot/review/review_oracle.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/stage_f/tests/test_relations.py
python -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/e23_pilot/review/test_review_checks.py
```

Results: 33/33 selected edge checks; 20/20 Oracle checks; existing relation tests 16 passed; new audit-checker tests 6 passed. No test failures, skips or warnings. The latter tests explicitly reject forged non-adjacent witnesses, HAVOC and strong KILL, and retain valid bypass paths and empty-block transitions. Logs and exact commands are preserved beside this report.

The existing relation suite covers: no actual final call/configuration-only; different storage roots; MAY keys; mutually exclusive or terminated branches; unknown user-call binding; read/call in the same statement; old parallel relations; label-independent construction; and missing-anchor writes still executing KILL.

## Approval-review event

An initial read-only command using pickle.load on cached IR was rejected by automatic approval review because pickle can execute arbitrary constructors. It was not executed or retried indirectly. The complete finite review used existing plain JSON instead; no pickle read is needed for this gate. This caused no remaining review blocker, but is recorded for transparency.

## Remaining limits

This finite sample is not a corpus-wide proof of absence of semantic defects. Accepted limits include unsolved path conditions, conservative HAVOC/alias handling, unsupported modifiers/complex inheritance and no compiler verification. This review does not license changing relation definitions, labels, pretrained model parameters or frozen folds. It also does not replace real-graph forward/gradient, checkpoint-binding and GPU-peak checks before the authorized pilot fits.
