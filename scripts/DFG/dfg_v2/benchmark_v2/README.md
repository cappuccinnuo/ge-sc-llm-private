# Prompt 8D benchmark v2 — prepared, not authorized

This directory prepares a separate grouped, nested benchmark. It does not run
training and does not add a fake G0P flag to the historical experiment CLI.

The frozen Prompt 8C duplicate audit supplies global exact/near connected
components. Singleton sources remain separate groups. Each task retains all
original files and nodes. A deterministic greedy allocator balances original
file class, source cohort, and original positive/negative node support while
keeping groups indivisible. Outer folds are 5 for contract tasks and 10 for node
tasks. Each outer training population is split into group-disjoint inner train
and validation with target fractions 0.8/0.2. Grouping takes priority over exact
stratification; impossible or classless contract partitions fail explicitly.

The split seed is 1. Ties use SHA256 of the seed and stable group identity, not
Python's randomized hash. Inner seeds derive deterministically from split seed,
task identity and fold. Model predictions, new scores, and the later choice of
L-orig/L-audit never enter assignment.

Preparation produces:

- Global source/group identities and per-task population manifests.
- Grouped split manifests with each role's file, group, cohort, original label
  and proposed audit-label support.
- L-orig and L-audit supervision views. L-audit uses C1 targets and masks
  C2-excluded nodes from both loss and its diagnostic metric; it never removes
  graph nodes. Contract labels are unchanged. Original-label outer scores must
  also include every original supervised unit.
- An independent 170-fit proposal: five ordinary profiles over all four tasks
  (150 fits), plus G0P over the two node tasks (20 fits), default training seed1.
- Input, feature-view, equality-proof, source, and historical-statistics SHA
  bindings; plan/seal and authorization template.
- Historical local timing references, explicitly conditional server timing
  scenarios, and the requirement not to mix devices in one batch.

The unchanged statistical family is copied from the historical report spec:
G1R/G2R/G3R/G3 versus G0, within task/checkpoint/metric. G0P is a separate
diagnostic comparison. Training remains nested: lowest inner-validation loss
selects best, and final scoring uses the outer fold. Full fixed-graph forward
is transductive, so these grouped folds are not an independent external dataset.

G0P reuses the frozen 8C denominator-only design on original G0 node types:
empty canonical relations match G3R target-type counts without adding
env_source. Its equal-input single-layer numerical proof does not imply that
final multilayer logits differ by a constant scale.

Example **preparation-only** invocation, after feature artifacts exist:

```bash
python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare \
  --old-plan scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json \
  --duplicates scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1/F \
  --node-views scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1/A/node_views.json \
  --feature-manifest scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/features/manifest.json \
  --feature-equivalence scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F/equivalence_review/equivalence.json \
  --keyword-baselines scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/E/keyword_baselines.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F
```

Output files are exclusive; a previously prepared plan is never overwritten.
The parent F directory may already contain features/equivalence artifacts.

Stop after preparation. The user must choose a label policy, training seeds and
execution location. A later executable plan must bind that choice, fresh
zero-step initialization, current runtime/environment, new split support and
checkpoint identity, and a tested executor that accepts feature/label views and
G0P. A preparation seal or authorization template cannot authorize any fit.

Final experiments are intended for a server with sufficient VRAM; the current
RTX3050 4GB limit belongs to local development. Neither sufficient VRAM nor a
textual duplicate detector guarantees model accuracy or complete leakage removal.

The current accepted equality review is in F/equivalence_review/equivalence.json;
its review_of SHA binds the preserved original scheduler-comparison failure.
Both branches already executed one acceptance epoch; the evidence review ran
no extra optimizer step. F/acceptance_evidence_verification.json checks that
reference chain. F/plan.json remains unauthorized and F/verification.json
checks all 170 proposed identities and group-disjoint folds.


## Unresolved naming-policy issue before execution

The requested 8C feature rule replaces only marker identifiers with id0, id1,
and so on, while ordinary user names remain unchanged. A newly trained model
can potentially learn that replacement-name family as an injection cue.
Therefore the prepared F plan is a candidate benchmark, not evidence that name
leakage has been eliminated. Its existing seal is preserved and training stays
unauthorized. The separate F_naming_risk evidence audits this limitation without
model training. A revised naming policy (for example consistent treatment of
all identifiable user names) must first be discussed and approved, then bound
to a new plan; it is not implemented silently here.
