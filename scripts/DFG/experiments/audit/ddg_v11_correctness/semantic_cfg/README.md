# D1 semantic CFG comment repair (Codex, 2026-10-13)

Only the isolated worktree implementation in `scripts/DFG/semantic_cfg.py` changed.
The archived original repository and HCG inputs were not changed.

The installed grammar assigns a between-branches comment `field=body`; the old
implementation consequently analyzed the comment as the else branch and fell
back the function. `ast_fields_before.json` records actual parser fields.

The repair removes comment extras from branch selection and validates the
complete direct-child condition/body/else shape before creating CFG blocks.
It rejects additional bodies, missing else bodies, misplaced or duplicate else,
and unknown named children. Nested/dangling else uses the AST rather than text.

The same 25 new tests produce **18 failed / 7 passed before** and all pass after;
combined with 73 existing semantic CFG, RD, projection and call-binding tests,
the post-repair run reports **98 passed, 0 failed, 0 skipped**. Test hashes match
before/after. Exact commands and source hashes are in `tests_before.json` and
`tests_after.json`; complete outputs are preserved alongside them.

Assertions cover CFG paths, branch union and KILL, return/true builtin terminal
behavior and argument reads, unreachable definitions, HCG IDs/labels/features/
base-edge invariants, and DDG-disabled identity. Six malformed AST proxies are
robustness tests, not Solidity-validity examples. Source fixtures are parsed and
semantically checked but **not solc-compiled**; no compiler download occurred.

This repair does not enlarge scalar MVP scope or demonstrate a metric gain.
Full-dataset recovery counts and all-project regression are separate root audits.
