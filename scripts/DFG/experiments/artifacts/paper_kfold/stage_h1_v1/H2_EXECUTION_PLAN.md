# Stage H2 execution plan (NOT STARTED)

H1 reserves E3a for the complete three-variant ablation. Execution requires a later
review/authorization; the H1 worker deliberately rejects E3a.

## Fixed scope

Use h2_plan.json / h2_plan.seal.json and the original H1-bound task manifests.
All 30 E3a initial states follow fresh E2 -> fresh E3a -> fresh E3b semantic
initialization; no model in the chain has undergone an optimizer step.
Four fold0 E3a results are reused from Stage G after the same audits.
Remaining: reentrancy contract1-4, access_control contract1-4,
reentrancy node1-9, access_control node1-9 = 26 model fits.

Retain all folds regardless of H1 outcome. Same frozen inputs, labels, token features,
full graph forward, schema, RNG formula, optimization, early stopping and min-loss best.
Run one GPU model at a time. Preserve attempts; stop on errors without resizing.
No new seeds, no selected-fold ablation, no independent-test claim.

## Required future work before execution

1. Review H1 results and semantic/support limitations.
2. Implement and test a narrowly scoped H2 scheduler in a new sibling directory.
   It must verify original H1 hashes and reserved E3a state bytes; do not edit old seals.
3. Create a separate H2 execution plan/seal binding the preexisting reserved plan and
   all code/input/init identities. Audit any later Git archive change read-only.
4. Verify the four reused E3a receipts and exact training computation compatibility.
5. Run exactly 26 remaining E3a fits, never substitute fold0 for complete K-folds.
6. Verify all 30 E3a results and report best/last separately.

## Planned comparisons per task

- E3a - E2: incremental state definition-use relations.
- E3b - E3a: joint incremental state-access/call-before-write relations.
- E3b - E2: total added state relations.

Report fold means/sample std, paired differences, pooled OOF, errors, probabilities,
support, gradients, memory and time. Original E0/E1 remain explicitly historical
references unless common parameter initialization is separately proven.

If H2 cannot be completed, call it incomplete ablation; do not infer the two relation
groups' separate contribution from H1 or a single fold.
