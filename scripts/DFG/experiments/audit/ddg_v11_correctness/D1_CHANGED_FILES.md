# D1 changed files

Codex · 2026-10-13 · isolated worktree only.

| File | Change | Reason |
|---|---|---|
| scripts/DFG/projection.py | exact pydot forward encoding + multiline-string ambiguity guard | incorrect Python escape decoding; preserve strict anchors |
| scripts/DFG/semantic_cfg.py | validate direct if/else AST bodies after excluding comments | comment misclassified as alternate branch |
| scripts/DFG/__init__.py | 0.1.0 to 0.1.1 | distinguish recovered graph provenance |
| scripts/DFG/tests/test_projection_v11.py | 21 regression cases | forward/negative DOT matches, strict identity, ambiguity |
| scripts/DFG/tests/test_semantic_cfg_v11.py | 25 regression cases | branch/control/dataflow and graph invariants |
| scripts/DFG/tests/test_semantic_cfg_conditions_v11.py | 6 condition cases | preserve condition DEF/USE with comments |
| audit/ddg_v11_correctness/protect_assets.py | before/after hashes and new-file detection | preserve original archive; allow only historical-doc append |
| audit/ddg_v11_correctness/coverage_rebuild.py | original/fixed full scalar DDG replay, graph artifacts | evidence-backed recovery counts |
| audit/ddg_v11_correctness/finalize_d1.py | exact input/core/fact checks and D2 gate | prevent unexplained differences |
| audit/ddg_v11_correctness/test_audit_guards.py | 6 audit regression cases | reject forged evidence and unexpected changes |

No edits to pipeline.py, symbol_table.py, access_extractor.py, reaching_definitions.py, HGT, tokenizer, labels, original training scripts or frozen artifacts. The worktree contains a SHA-identical copy of the existing grammar for tests. D2/D3 and documentation edits are separately inventoried at completion.
