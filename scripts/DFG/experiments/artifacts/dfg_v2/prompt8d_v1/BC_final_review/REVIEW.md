# Prompt 8D B/C final independent review

Status: passed for the completed snapshot; no correctness blocker found.

- CPU-only review; zero model forwards and zero training steps.
- All 80 source bundles, six prepared views, and 9,778 changed-code token rows were independently reencoded.
- Full untruncated token lengths, per-identifier token positions, unchanged outside-token IDs, and the exact clipped/padded 512-float vectors agree.
- Snapshot includes 28 completed B_full jobs; remaining live jobs are not claimed complete.
- Archived best checkpoint SHA, receipt, binding, graph identity, state digest, outer-test row scope and no-mapping-file exact predictions agree.
- Checked 411 bound references and rechecked every SHA after the audit.

## Clipping counts

| Task | B_full code-changed but vector-equal | B_matched | C_matched |
|---|---:|---:|---:|
| reentrancy_node | 1 | 8 | 15 |
| access_control_node | 1 | 1 | 11 |

These edits lie outside the consumed feature window; they remain recorded, and worker feature_changed counters correctly distinguish them.

## Interpretation boundaries

- B_full versus old idN changes both neutral lexical values and positional preservation; their difference is not a pure causal estimate of positional effects.
- B_matched and C_matched match unique identifier count and isolated token-length histograms, not occurrences, affected nodes, semantic roles or perturbed feature dose.
- Neutral candidates are fixed and deterministic but lexical token-ID numeric values still change. Inputs are 512 float tokenizer IDs, not CodeT5 hidden embeddings.
- Testing-only renamed inputs are distribution-shift diagnostics, not retraining, independent test generalization, or proofs of semantic vulnerability understanding.
- C eligibility is explicit declaration-backed with conservative builtin exclusions; rewrites are filewise lexical spellings, not a compiler-verified alpha conversion.
- The runtime boolean frozen_nx_attributes_untouched is supported by code ownership/deepcopy and absence of NX mutations, not a separate post-forward NX digest in the worker.
- No runtime files or existing artifacts were modified; this review snapshot does not claim remaining running jobs are complete.

Evidence: `audit.json` contains the complete checked-reference hashes and completed-job identities; `audit_cpu.py` is the actual read-only review command.
