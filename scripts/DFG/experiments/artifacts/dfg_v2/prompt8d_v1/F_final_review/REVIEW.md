# Prompt 8D F final review

Status: passed for preparation only. No concrete correctness blocker was found.

The independent review checked the sealed 170-fit proposal, all referenced input
hashes, 256 source identities / 227 duplicate groups, every role of all 30 grouped
folds, and the original/C1/C2-mask relationship. Every original scoring unit is
retained; L-audit masks loss and its diagnostic score only. Contract labels remain
unchanged.

All 51,490 original and neutral feature rows were independently re-encoded using
the frozen tokenizer and the requested 8C idN rule. Every vector matched exactly.
The saved original and feature-bound one-epoch CPU model, Adam and scheduler
states match exactly. Scheduler callable implementation identity is compared,
not the distinct deserialized bound-object address. The initial failed report is
preserved. This review ran no model forward, optimizer step or formal fit.

The new plan does not claim that the historical trainer can execute grouped
L-audit/G0P tasks. That integration is explicitly a future gate. The original
auxiliary score rule is a preparation requirement and label support, not evidence
that a new grouped executor has already run.

Authorization still requires label policy (default L-audit), training seed set
(default [1]), and location (local or server). No authorization is inferred from
this review. Final server VRAM is expected sufficient; local RTX3050 limits do
not define the final hardware.

## Actual commands and evidence

The actual preparation called prepare_benchmark via the existing WSL mando
interpreter. Its equivalent CLI command is recorded verbatim in
../F/execution_command.json. Owned tests ran the exact command recorded in
../F/preparation_tests.command.json: 50 passed, 0 failed.

The preparation command refuses existing output files. Do not rerun it against
the sealed F directory. Use read-only verification for inspection.

Detailed command arguments, hash checks, partition counts, equality evidence and
remaining execution gates are in review.json. Historical median local timing
reference is 8.2791 hours, not a measured new benchmark duration; server timing is
conditional and unmeasured.
