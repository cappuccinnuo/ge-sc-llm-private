# Prompt 8H GitHub archive

Date: 2026-10-31. Author: Codex. Target: origin/dfg-v2.

Includes the three implementation commits d6cdf957, 00c731e6 and 02db061c,
the completed 170-fit results, predictions, best/last metadata, gradients,
resources, plans/seals/amendments, initialization manifests, acceptance
records, tests, interrupted attempts and final reports. No new training.

4959 text artifacts: 2217158875 original bytes; 1909092494 archived bytes,
before Git transport compression. See the adjacent JSON inventory for each
original/archive path, size and SHA256.

Two reports exceed the 90 MiB archive threshold. Lossless gzip copies are
under prompt8h_v1/github_archive/reports/:
- error_probability_changes.json: 124234255 -> 4590017 bytes.
- relation_support_gradients.json: 198202153 -> 9780010 bytes.

Both were actually decompressed and hashed. Original files and their old
receipt hashes remain unchanged. After cloning, decompress the copies to
the original report paths if needed.

542 .pt tensor files and one runtime lock remain local (31179442636 bytes).
Their paths/sizes are inventoried; sealed manifests/receipts bind tensor
hashes. This archive step did not independently hash all tensor files again.
A clone supports reviewing text results; model reloading requires those
local binaries and existing input graphs/features. Other batches' untracked
files are excluded. Nothing was deleted.

170 successful receipts, 16 final reports and the interrupted-attempt files
were verified by SHA. All archived text passed UTF-8, JSON/JSONL and common
credential-pattern checks. The implementation previously passed 2876 unique
tests. No tests or training were rerun just for archiving. Original log/CSV
whitespace is preserved to retain sealed bytes. Staging uses explicit paths.

WSL direct DNS failed. Use the existing Windows Git, Windows proxy at
127.0.0.1:7897 and WSL gh credential helper, with command-scoped settings.
No credentials are printed or global settings changed. Remote 39801a87 is
an ancestor of local HEAD. Normal push only to origin/dfg-v2; no force push
or writes to upstream. Actual remote SHA determines synchronization.

Results use N-anon-s, L-audit and grouped nested CV. Inner validation loss
selects best; this is not an independent external test. G* is G3 selected
using inner validation; the primary contrast remains reentrancy-node
G3R versus G0. Best/last, orig-all and pooled results remain separate.

Final experiments are intended for a server with sufficient VRAM. This
batch ran on the local RTX3050 4GiB; do not mix future server results.

See [implementation report](../scripts/DFG/dfg_v2/PROMPT8H_REPORT.md),
[final report](../scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/reports/REPORT.md)
and [inventory](github_archive_prompt8h_2026-10-31.json).
