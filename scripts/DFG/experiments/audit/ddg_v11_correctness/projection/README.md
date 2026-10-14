# Projection v1.1: exact DOT correspondence

Author: Codex. Scope: isolated `/home/zhao/SmartContract/ge-sc-llm-ddg-v11` worktree.

## Change

Only `scripts/DFG/projection.py` was changed by this subtask. New tests are in `scripts/DFG/tests/test_projection_v11.py`. The original repository and all existing tests were unchanged.

The original producer `process_graphs/tree_sitter_codeviews/utils/postprocessor.py` calls NetworkX's pydot writer. Installed pydot is 1.4.2; `quote_if_necessary` escapes double quotes and physical LF/CR, but does not escape pre-existing Solidity backslashes. The old `ast.literal_eval` comparison interprets Solidity textual escapes as Python escapes. This caused both false rejection of exact source and false acceptance of differently spelled source (`\x41` vs `A`, `\u0041` vs `A`, literal `\t` vs tab, and distinct backslash counts).

`code_equal` now accepts exact raw bytes-as-text or exact `pydot.quote_if_necessary(expected)` representation. It does not normalize whitespace, decode arbitrary Python/JSON alternate spellings, search nearest lines, or guess among AST nodes. Existing AST identity, role, endpoint and duplicate-anchor checks remain intact. The existing JSON-style ordinary ASCII fixture still passes because its output coincides with actual DOT quoting; arbitrary JSON encoding is not assumed to be a separately trusted input format.

## Non-injective serialization safeguard

Canonical DOT equality alone cannot prove original source identity. In pydot 1.4.2 a physical LF and a literal backslash-n can collide. A concrete parser-only counterexample swaps a backslash+physical-LF string continuation with a double-backslash+n string sequence between adjacent strings. Both variants parse with the current grammar, have the same HCG AST anchors/types/endpoints, and serialize to the same code field.

For serialized code only, `Projector` now rejects physical LF/CR within existing string AST spans with `Ambiguous DOT serialization of multiline string`. Exact raw source remains supported, and physical newlines outside strings remain supported. No new compiler/type-system/lexer or fuzzy mapping was added. This is a conservative guard for the demonstrated ambiguity; the comparison still cannot independently prove the author's historical source bytes. Full dataset audits must report any newly rejected files rather than silently treating a coverage loss as success.

## Regression evidence

- Before: `before_targeted.log` / `.json`: **7 failed, 14 passed**, original projection SHA recorded. The newly written assertions were run before changing core code.
- After: `after_targeted_v1.log` / `.json`: **30 passed, 0 failed, 0 skipped**, consisting of all 21 new tests plus all 9 existing projection tests.
- `test_integrity.json` confirms the new test file has identical hashes before/after, the existing projection test file was not changed, and the archive implementation still has its original hash.
- The old run's negative elapsed duration in pytest output is a host-clock artifact; status/counts are used as evidence, not that duration.
- Test fixtures are parser-level / string-serialization tests. **No Solidity compilation validation was executed**, and no compiler was installed/downloaded.

Tests cover exact raw and DOT representations, ordinary source, quotes, backslashes, physical LF/CR, tabs, Unicode, both-direction source mismatch rejection, AST ID/type/endpoints corruption, duplicate anchors, positive DDG projection, original node/label/edge immutability, and conservative rejection of the demonstrated serialized-string collision.

## Actual archived nodes

`reproduce_author_nodes.py` loads the exact manifest-bound source and frozen contract E0 graph read-only, verifies source SHA, reproduces each original Projector failure using the original module, and runs the fixed Projector over the whole affected file. `author_projection_before_after.json` records paths and hashes.

All **8 cohort/file entries** recovered strict projection, verifying **1,683 existing ordinary HCG nodes**. These are the 3 reentrancy and 5 access-control cases previously diagnosed; counts are not unique source hashes and are not new DDG-edge counts. Root's separate full coverage audit measures actual facts/edges and unchanged files.

The new facts/edge counts and any F1 benefit are not established by this focused projection test; no model training or checkpoint forward pass was run here.

## Commands

From the isolated worktree, with the existing mando Python and grammar:

```bash
export PYTHONDONTWRITEBYTECODE=1
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests/test_projection_v11.py scripts/DFG/tests/test_projection.py
/home/zhao/miniconda3/envs/mando/bin/python -B scripts/DFG/experiments/audit/ddg_v11_correctness/projection/reproduce_author_nodes.py
```

The reproduction script intentionally refuses to overwrite an existing evidence JSON.
