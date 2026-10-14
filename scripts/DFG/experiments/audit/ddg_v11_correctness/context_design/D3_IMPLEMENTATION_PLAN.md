# D3 implementation and experiment plan — design only

Codex, 2026-10-13. No training or state-analysis algorithm is implemented this round.

## Minimal stages

1. Future state/state_models.py + state_locations.py: source/declaration identity, simple key versions, MAY/UNKNOWN. Test shadowing, same names across contracts, changing keys, typed constants, missing binding.
2. state_access.py: read/write/call inventory. Keep FunctionIR unchanged initially; side table references verified block/event IDs. Inventory is not DDG.
3. state_reaching_definitions.py: strong/weak updates, branch alternatives, loops, unknown entry, call HAVOC and unprojectable overwriting writes. Return completeness/fallback; scalar KILL assumptions cannot simply be reused.
4. state_projection.py: v1.1 exact Projector and explicit relation policy. No location nodes. Each fact retains source identity and CFG witness. Same endpoints/different relation coexist.
5. Independent oracle and negative fixtures. Expected dependencies come from source/semantic review, never model predictions.
6. Audit actual generated edges and new information at difficult nodes before any training. Zero concrete state edges for entry-read -> call -> reset is valid.
7. modifier_context.py and separate control-dependence analysis only in a later explicit version. Owner predicate -> write is not state Def–Use.
8. Versioned prepared graphs, schema audit and short model-registration check only after acceptance. Full K-fold requires another reviewed run plan.

## Acceptance

Every concrete edge has declaration/key proof, def/use anchors and forward CFG witness. Unknown call/reference cannot retain unjustified strong definitions. Missing projection does not disable semantic KILL. Unsupported state functions retain scalar/HCG and no partial state edges. use_state=false gives scalar fingerprint exactly. Permuting labels in memory must leave state output unchanged. Exact EVM slots, full alias analysis, cross-transaction causality, full modifiers and complete Solidity are not implied.

## Future controlled experiments (not run)

| Experiment | Intended change |
|---|---|
| E0 | original CFG+CG, immutable |
| E1 | archived scalar DDG, immutable |
| E2 | v1.1 correctness repair, separate graphs |
| E3 | E2 + oracle-approved state subset |
| E4 | separately controlled optional fusion/initialization |

Keep author labels, files, splits, tokenizer/features, HGT core, optimizer/LR, early stop and best rule fixed. Align shared parameters by node/canonical identity; never initialize from trained E0. Record E2/E3 relation counts and parameter changes. Same DDG label does not imply identical capacity.

Primary protocol remains paper_kfold **CV validation**, not independent test. Nested/template-disjoint evaluation is a separately named side result. Repeated-label ambiguity is not fixed by choosing a lower F1. Old results remain intact.

## Retraining gate

D1 establishes correctness recovery, not improved F1. E2 training follows accepted coverage/provenance and a new run plan. E3 follows independently reviewed state oracles, supported/unknown coverage and actual projected-information audit. Do not train E3 merely because the design sounds relevant.

Stop this round after evidence and design/oracle documents. No state implementation, optimizer update, training or checkpoint replacement.
