# Case studies: frozen-checkpoint DDG diagnosis

Author: Codex. Source: accepted Stage C best predictions and frozen author-labeled HCG; no retraining.
This report combines the source/label/coverage evidence with complete best-checkpoint N/Z/R diagnostics for all eight preselected cases. It uses only successful pilot_v2 and remaining runs, excluding failed pilot output.

## Label version and source coordinates

Both cohorts use released_author_node_labels in the frozen prepared manifest, not local narrow/rebuilt endpoint labels. E0 and E1 retain these same labels. The raw author graph path and SHA256, prepared E0/E1 node graph hashes, source manifest and exact source hashes are preserved in case_evidence.json -> label_and_graph_versions and each case's source.

All raw line references below are physical one-based lines in the manifest-bound original Solidity source. They are distinct from graph_stored_source_lines, which is retained separately in archived predictions. Full absolute source paths and exact enclosing-function text are present for every selected case.

## Identity and interpretation boundary

Every selected node was joined by source_file and original_graph_node_id. Raw source positions were recovered using the saved AST ID/type/endpoints and SourceView executable-token alignment, not nearest-line matching. Raw labels were cross-checked against archived targets. No original labels or graphs were changed.
All FP/FN statements below mean disagreement with the frozen graph labels. Equal node text does not establish equal program semantics, and a large FP count does not establish incorrect ground truth.

## Reentrancy: buggy_18.sol, node fold 8

The file has 424 nodes, 35 labeled positive. E0 and E1 both make 252 errors: 250 FP and 2 FN. Only 29 of these jointly wrong nodes have direct DDG input; 48 are in the two-layer DDG influence set.
214/252 jointly wrong nodes have exactly repeated stored code in the training files; 198 have at least one opposite-label training match, and 194 have only opposite-label training matches. The exact float32 512-feature analysis has the same counts here. Matching indexes were built from train only. These counts support local-label/context ambiguity as a serious alternative explanation to missing DDG alone; they do not prove leakage, memorization, or wrong labels.

| Node | Raw line | Original label | E0/E1 best | Positive probability E0/E1 | DDG input | Observation |
|---|---:|---:|---|---|---:|---|
| 2706 | 115 | 0 | 1/1 | 0.835075/0.834034 | 0 | External-call statement; matching train snippets all have the opposite label |
| 2670 | 68 | 1 | 0/0 | 0.357989/0.358373 | 0 | Counter update; function binding fallback |
| 2675 | 75 | 1 | 0/0 | 0.429794/0.432524 | 1 | Parameter use covered, mapping contents not represented |

Node 2706 is the raw line 115 call in withdrawBalance_re_ent33 (lines 112-120). Its function also clears userBalance_re_ent33[msg.sender] after the call. The actual DDG audit reports builtin_not_guaranteed_over_pragma_interval for revert: the source pragma has lower bound 0.5.9 and no finite upper bound. This is the deliberately conservative binding fallback, not the DOT projection defect. The function contributes no DDG. Node 2706 has 37 exactly matching training snippets, all positive; its own frozen graph label is negative. Annotation provenance or program context would need independent investigation before changing that label.

Node 2670 is raw line 68, counter_re_ent21 += 1, and also lies in a binding-fallback function. Node 2675 is raw line 75, require(msg.sender.send(_weiToWithdraw)). Its function is successfully analyzed and receives three parameter-origin facts; the specific node receives the _weiToWithdraw entry fact. The original source declares balances_re_ent10 as a mapping, but mapping contents are outside the frozen analyzer. This illustrates that successful function analysis does not mean complete security-relevant dependence coverage.

## One correction and one newly introduced error in the same fold

Reentrancy buggy_36.sol node 5961, raw line 179 (uint256 c = a * b), is a frozen negative. E0 predicts positive at 0.503773 and E1 negative at 0.494171. It has one incoming DDG edge (two parameter facts a/b merged onto the same entry-node pair) and two outgoing local-c edges to require and return. This is compatible with useful scalar context, but paired training differences alone do not identify the DDG edge as the cause. The fixed-weight N/Z result below provides the additional direct sensitivity evidence.

In the same file/fold, node 6101 at raw line 451 (_minimumTokensToVote = 1) changes from correct negative at 0.499245 to FP at 0.502355. It has no direct DDG endpoint and no two-layer DDG influence in the static topology. The function has a Token parameter and onlyOwner modifier; its actual first fallback reason is Unsupported non-scalar or inferred type: Token. The small threshold crossing can arise from shared parameter changes or changed relation aggregation and cannot be explained as a direct new edge at this node.

A further correction demonstrates why direct edge explanations require care: buggy_27.sol node 4672, raw line 163 (require(redeemableEther_re_ent18[msg.sender] > 0)), improves from FN p=0.399095 to positive p=0.960331, despite no DDG endpoint and no two-layer DDG influence. The function has one different local-scalar dependence; the mapping contents are not modeled.

## Access control cases and difficult files

mapping_write.sol node 12963 at raw line 27 is require(msg.sender == owner). The original label is negative; E0 p=0.014382 is correct and E1 p=0.651479 introduces an FP. The original source declares owner as contract state. The withdraw function is classified analyzed but has zero extracted DDG facts; the current SymbolTable collects local/parameter/return scalar declarations, not owner state.

arbitrary_location_write_simple.sol node 11479 at raw line 37 has the same displayed require statement, original negative label, and changes from FP p=0.508923 to correct p=0.484182. Destroy is analyzed with zero facts. This is a complementary correction with no direct DDG, rather than a claim that adding DDG consistently helps or harms owner checks.

Access-control buggy_18.sol contributes 87 shared errors among 284 nodes (17 positives), and buggy_26.sol contributes 42 among 143 nodes (21 positives). Respectively 53 and 27 shared errors have direct DDG input; 86 and 42 are in the two-layer influence set. Thus these files cannot be explained merely as having no DDG coverage.
Among the shared errors, buggy_18 has 85/87 opposite-label training matches, while buggy_26 has 42/42, of which 41 also have same-label training matches. Context, source/label provenance, feature equivalence, and graph aggregation remain competing explanations.

## Frozen analyzer limitations confirmed in source

- Symbol collection: scripts/DFG/symbol_table.py:70-85 collects parameters, named return variables, and local declarations.
- Unresolved/nonlocal names and opaque storage/member access: scripts/DFG/access_extractor.py:22-58,68-74. Mapping writes do not create mapping-content definitions.
- Modifier fallback: scripts/DFG/semantic_cfg.py:18-19.
- The selected declarations and exact source snippets are preserved in case_evidence.json. No additional attack path is asserted.

## HGT aggregation, residual and initialization: source facts

model_hgt.py:104-108 normalizes attention separately inside each canonical relation. Lines 110-117 reduce per-relation messages and use cross_reducer=mean. The interpretation of zero-degree destinations depends on installed DGL semantics and must be backed by the separate synthetic runtime test, not just this source excerpt.
model_hgt.py:125-139 computes alpha=sigmoid(skip[type]), applies a_linear/dropout to the merged message, then alpha*message+(1-alpha)*h followed by LayerNorm. skip is initialized to one at line 71, so initial alpha is approximately 0.731059. This coefficient alone does not establish the message/residual norm ratio; measured branch tensors are required.
model_hgt.py:68-75 initializes the entire [relations, heads, d_k, d_k] relation_att/msg banks with Xavier. PyTorch fan_in=heads*d_k*d_k and fan_out=relations*d_k*d_k for these four-dimensional banks, rather than the per-head matrix fan values. The resulting theoretical standard deviation is sqrt(2/((heads+relations)*d_k*d_k)); per-matrix Xavier would be sqrt(1/d_k).
protocol.py:191 copies shared E0 relations into E1 by semantic identity. Lines 200-205 draw only added DDG relation slices at the E1 full-bank scale. Therefore E1 common slices have the source E0 bank initialization distribution and DDG-only slices have the E1 bank distribution. Initial scale is a measurable design property, not evidence by itself that it caused the final outcomes.

## Existing implementation defects: independently reproduced, not fixed

| Diagnostic | Frozen behavior | Independent check | Interpretation |
|---|---|---|---|
| DOT source encoding | 3 reentrancy files and 5 access-control files reject whole-file projection | For each rejected node, pydot.quote_if_necessary(exact AST source) equals stored graph code; code_equal returns false | Confirmed serializer mismatch, not demonstrated source-version mismatch |
| Comment between if and else | Frozen analyzer falls back the function with Unsupported statement: comment | Same parser-only sample without that comment yields 3 facts; with it yields 0 | Confirmed parser-adaptation defect; no solc compilation performed |

The DOT issue is at projection.py:13-24 and53-55, propagated to whole-file fallback by pipeline.py:33-38. The if/else issue is at semantic_cfg.py:44-48, where field-name body collection does not exclude comments. Both probes use the frozen implementation; no monkeypatch, graph regeneration or repaired-graph retraining was performed.
The eight rejected files and exact stored/expected/decoded representations are in case_evidence.json. All those files retain the original HCG and zero added DDG edges.

## What is and is not established

Direct evidence: original labels/predictions, exact source locations, extracted/projected facts, per-node static coverage, duplicate train matches, and the two reproducible analyzer defects.
Supported explanations: limited state/modifier context, training-label/context ambiguity for recurring snippets, threshold sensitivity, and aggregation/parameter changes could all contribute; different cases support different explanations.
Unverified: whether fixing either defect raises F1, whether state dependencies improve generalization, whether labels are incorrect, and the causal magnitude of DDG messages. Independent annotation checks remain necessary. The N/Z/R evidence below addresses frozen-model sensitivity but does not establish the effect of a repaired or expanded model after retraining.
The following section performs the fixed-checkpoint comparison at the exact same identities. No labels or training rules were changed, and these exploratory cases are not independent tests.


## Complete N/Z/R evidence for the selected identities

N uses the accepted E1 best weights and original graph. Z zeros DDG messages in both layers while preserving the graph, canonical relations, attention computation, and cross-relation mean denominator. R101/R102/R103 are the three predeclared constrained rewiring seeds. E0 below is its normal best replay.

| Cohort/file/raw line/node | Target | E0 probability(pred) | N probability(pred) | Z probability(pred) | R101 probability(pred) | R102 probability(pred) | R103 probability(pred) |
|---|---:|---:|---:|---:|---:|---:|---:|
| reentrancy_author/buggy_18.sol/L115/2706 | 0 | 0.835074842 (1) | 0.834033906 (1) | 0.834033906 (1) | 0.834033906 (1) | 0.834033906 (1) | 0.834033906 (1) |
| reentrancy_author/buggy_18.sol/L68/2670 | 1 | 0.357989103 (0) | 0.358373255 (0) | 0.358373255 (0) | 0.358373255 (0) | 0.358373255 (0) | 0.358373255 (0) |
| reentrancy_author/buggy_18.sol/L75/2675 | 1 | 0.429793775 (0) | 0.432523608 (0) | 0.430357456 (0) | 0.432523608 (0) | 0.432523608 (0) | 0.432523608 (0) |
| reentrancy_author/buggy_36.sol/L179/5961 | 0 | 0.503772676 (1) | 0.494170934 (0) | 0.505743802 (1) | 0.494170934 (0) | 0.494170934 (0) | 0.494170934 (0) |
| reentrancy_author/buggy_36.sol/L451/6101 | 0 | 0.499244541 (0) | 0.502355397 (1) | 0.502355397 (1) | 0.502355397 (1) | 0.502355397 (1) | 0.502355397 (1) |
| reentrancy_author/buggy_27.sol/L163/4672 | 1 | 0.399095476 (0) | 0.960331082 (1) | 0.960331082 (1) | 0.960331082 (1) | 0.960331082 (1) | 0.960331082 (1) |
| access_control_author/mapping_write.sol/L27/12963 | 0 | 0.014381565 (0) | 0.651479125 (1) | 0.651479125 (1) | 0.651479125 (1) | 0.651479125 (1) | 0.651479125 (1) |
| access_control_author/arbitrary_location_write_simple.sol/L37/11479 | 0 | 0.508923292 (1) | 0.484181672 (0) | 0.484181672 (0) | 0.484181672 (0) | 0.484181672 (0) | 0.484181672 (0) |

### Correction supported by DDG message sensitivity

buggy_36.sol node 5961 provides a concrete positive case: the accepted E1 prediction is correct (N=0.494170934), and zeroing all DATA_DEF_USE messages in both layers at frozen weights changes this node to FP (Z=0.505743802). The positive probability increases by 0.011572868, or approximately 1.1573 percentage points. Thus this particular correction does depend on DDG messages in the frozen E1 model. This does not establish aggregate benefit or that retraining without DDG would reproduce E0.

### Errors without frozen-message sensitivity

For buggy_18 node 2706 and node 2670, N/Z/R logits and probabilities are exactly identical and the errors persist. This agrees with their lack of DDG influence under the static topology and binding fallback. For node 2675, Z changes the positive probability from 0.432523608 to 0.430357456 (about -0.2166 percentage points), but both remain FN. The model is sensitive to the available parameter DDG while the missing mapping-state semantics remain unrepresented; this single observation cannot establish the reason it stays wrong.

The newly introduced error at buggy_36 node 6101 and the access-control mapping_write node 12963 is unchanged under Z, including logits. Therefore these specific E0-to-E1 errors cannot be described as direct dependence on nonzero DDG message content at the fitted E1 checkpoint. Changes in learned shared parameters, relation registration/mean behavior, and training trajectory remain possible explanations. Z preserves the relation denominator and does not isolate those alternatives.

The corrected nodes buggy_27 node 4672 and access-control arbitrary_location_write_simple node 11479 are also N/Z invariant. Their correction relative to E0 must not be presented as direct frozen DDG-message sensitivity.

### Rewiring control is locally insufficient

All three R seeds leave the predictions/probabilities/logits of all eight cases exactly equal to N. Crucially, the selected enclosing functions have zero replaced semantic edges for every seed. Some have no DDG; others are too small or have single-source groups constrained by canonical relation. Consequently, these case-level R comparisons cannot establish that definition-use placement is semantically irrelevant.
Global perturbation and each selected function group, including zero-group cases, are preserved in case_interventions.json. No cross-function fallback or label-directed rewiring was used to enlarge the perturbation.

### Replay checks and remaining uncertainty

All eight cases were found in exactly one successful output directory; file identity, typed original node ID, fold, target, and archived discrete prediction were checked. Native-versus-wrapper and post-context native recovery gates passed; stored before/after parameter hashes match.
Normal replay probabilities were checked against archived values using the predeclared tolerance, not silently rounded to equality. For access-control node 11479 the replay probability differs from the stored archival probability by about 2.98e-8, within the fixed gate. Exact N/Z/R claims above refer to the same-device diagnostic outputs, not to cross-run archival probability equality.
The original label provenance, context-dependent meaning of repeated code, counterfactual retraining outcome, and possible gain from state/modifier extensions remain unresolved. No proposal here guarantees an increase in F1.
