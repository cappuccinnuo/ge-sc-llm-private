# Condition extras addendum (Codex, 2026-10-13)

Root review requested an independent check of comments before/after the if
condition. The installed parser can assign `field=condition` to a trailing
comment, but `child_by_field_name("condition")` returns the preceding real
expression. Five actual AST snapshots are preserved in
`condition_comment_probe.json`. No additional core defect was found or changed.

Six supplemental tests in `test_semantic_cfg_conditions_v11.py` verify the
condition node, p/q read events, parameter-to-condition def-use facts, and both
branch definitions at the join. The original 25-test source remains byte-for-
byte unchanged from the before/after run. The final targeted command (saved in
`tests_condition_addendum.json`) passes **104 tests: 31 new + 73 existing**,
with zero failures, skips or warnings. `compile()` passes the modified core and
two new test source files without emitting bytecode.

This supplements, rather than overwrites, the earlier 98-pass result. Solidity
fixtures still have no local solc compilation verification.
