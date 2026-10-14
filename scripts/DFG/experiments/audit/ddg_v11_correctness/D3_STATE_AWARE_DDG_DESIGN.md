# D3 State-aware DDG design — proposed, not implemented

## 中文实施建议：先验证表达价值，再扩大分析

D1 的四套输入分别恢复实际 DDG 边198、183、267、204条（重入合约、重入节点、访问控制合约、访问控制节点）。原有语义边与事实保留，基础 HCG 不变；节点任务没有新增支持函数，主要是既有事实恢复投影。本轮困难案例所在文件不在这些修复影响名单中，不能说它们已经因 D1 被解决，也没有新的 F1。

建议下一步只实现一个可审计的小型状态位置原型：同一合约内可明确绑定的直接状态标量和简单单根 mapping 键；函数入口未知状态、未知外部调用的状态失效、强/弱更新和 MAY alias 从第一版就必须处理。状态事件先做旁路清单，再决定哪些能生成严格的前向定义—使用边。modifier 执行与控制依赖应单独验收，不能塞进 DATA_DEF_USE。

特别是“入口余额读取→外部调用→余额清零”可能没有任何更早的函数内余额定义，因此正确的 state Def–Use 也可能新增0条边。需要先证明小样例是否真的补入任务所缺信息；如果需要的是同位置访问顺序、控制约束或回调关系，应另立语义与消融，不可把后写伪造成前读的定义。

D2 中的数组、参数型 owner_txorigin、纯算术错误是必要反例；设计不能只选择支持加状态依赖的样例。当前证据足以支持小规模原型与人工 Oracle 复核，尚不足以承诺全量 E3 必有提升。

E2 的节点 schema 已实际新增两种 canonical tuple（重入 expression_statement→if/return）和一种（访问控制 expression_statement→return），关系名仍为 DATA_DEF_USE。未来训练必须重建并绑定新 schema 与参数初始化，不能拿旧 checkpoint 当作新图训练结果。


Author: Codex. Date: 2026-10-13. Version: ddg-v1.1-correctness-fix / state-design-v1.
Status: design only. No state events, new relations, training or labels are implemented by this document. D2 results and their evidence levels must be read alongside this proposal.

## Decision and scope

The next prototype should first test whether security-relevant state events can be resolved and projected, not assume that more edges improve F1. Scalar DDG remains an independent product. Scalar function success does not certify state completeness.

Use source-level **storage locations**, not claimed EVM slots. A state declaration identity includes source SHA256, source/compilation unit identity, contract declaration span and variable declaration span. Unresolved inheritance/import binding is UNKNOWN, not a name match. Existing semantic CFG remains analysis-only and must not replace model CFG/CG.

Start with directly declared scalar state and mapping entries with a provable single root and simple key identity. Arrays, nested mappings, storage references, inheritance and modifier execution each require an explicit support gate. Their syntax may be inventoried before support; inventory is not dependency analysis.

Unknown-entry and call-clobber handling are mandatory from the first prototype. Delaying them would make simple state reaching definitions unsound in reentrancy cases.

## Proposed identities and interfaces

These specifications are not executable replacements for models.py.

- DeclarationRef(source_sha256, unit_id, contract_span, declaration_span, type_evidence)
- KeyIdentity(kind, typed_constant OR local_definition_version OR builtin_frame_identity, expression_span, proof_id, stability_region)
- StateLocation(root: DeclarationRef, path: FieldStep/IndexStep sequence, identity_status: EXACT/MAY/UNKNOWN, alias_class, evidence)
- StateReadEvent(event_id, function_id, anchor: Span, locations, path_condition_id)
- StateWriteEvent(event_id, function_id, anchor: Span, locations, update_kind: STRONG/WEAK/HAVOC, rhs_scalar_reads, rhs_state_reads)
- StateAccessSummary(function_id, reads, writes, calls, unresolved, completeness)
- StateFact(def_event_id, use_event_id, location_id, certainty, cfg_witness, evidence)
- StateAnalysisResult(events, may_reaching_defs, facts, diagnostics, status)

The actual project has FunctionIR(id,file,entry,blocks,symbols), Event(reads,writes) and scalar Definition/Fact. Do not overload scalar symbol strings with locations. Initially use a separate StateFunctionIR(base_function_id,cfg_ref,state_events_by_block) side table and verify every referenced block/event identity. No model variable/location/event nodes.

Proposed APIs: resolve_state_roots(source_view,binding_evidence) -> LocationTable; extract_state_accesses(source_view,location_table,scalar_ir) -> StateAccessSummary; analyze_state_flow(scalar_ir,summary,call_policy,max_iterations) -> StateAnalysisResult; project_state_facts(facts,exact_projector,relation_policy) -> EdgeBatch+Diagnostics.

No API accepts vulnerability labels or predictions. D2 findings select oracle examples only.

## Alias, keys and transfer rules

| Situation | Identity | Transfer |
|---|---|---|
| Same direct scalar state declaration | singleton EXACT | definite write strong-KILL old location definitions |
| Same mapping root + same typed constant | EXACT | strong update only with proved singleton location |
| Same key declaration reassigned between accesses | not automatically equal | key definition version changes; MAY/UNKNOWN |
| msg.sender within one call frame | stable builtin frame value | exact only after binding/type confirmation |
| Different key spellings a,b | not proof of inequality | MAY alias unless values are proven distinct |
| Distinct typed constants at same root | NO_ALIAS when conversion verified | no content dependency |
| Proven storage-reference alias | EXACT target | reference rebinding != content write |
| Unknown reference/assembly/delegatecall | UNKNOWN reachable state | HAVOC or state function fallback |

Reaching definitions are a **may-analysis** even when the location is EXACT. Branch union yields alternative definitions, not claims that all paths execute all definitions. Keep location certainty separate from path/definition certainty.

Weak write adds a possible definition without killing prior possibilities. Strong KILL requires one definitely written location and proved alias/key identity, with no unaccounted external effect. A write lacking an HCG projection must still update/KILL in semantic analysis; skip only edge materialization.

Entry environment contains ENTRY_UNKNOWN(location) metadata. This is not a fabricated current-function statement and must not silently become a DATA_DEF_USE edge from the function-definition node. Initial prototype emits no model edge for unresolved entry state. Count these reads separately.

A possibly reentrant call can alter state before return. Conservatively HAVOC affected/all accessible state for unresolved external calls; post-call origin becomes unknown. Do not assert a must-reaching pre-call write. A complete may-analysis may retain explicit unknown origin plus feasible pre-call alternatives; otherwise state analysis falls back at function scope. Proven staticcall/effect summaries need their own binding/version evidence. No gas-stipend assumption silently makes send/transfer safe. Delegatecall and assembly initially fall back state analysis.

Loop fixpoint, branch union, unreachable paths and return/revert termination remain required. Failed transactional paths cannot establish committed updates.

## Preserve relation meaning

| Evidence | Candidate output | Initial policy |
|---|---|---|
| concrete earlier state write reaches later read | STATE_DEF_USE | proposed forward relation; exact endpoints |
| same location read before later write | STATE_ACCESS_ORDER | side table initially; never reverse into DEF_USE |
| require/if guards sensitive write | CONTROL_DEPENDENCE | separate future analysis |
| unresolved entry value | ENTRY_UNKNOWN | metadata only |
| call invalidates state assumptions | call-clobber diagnostic | metadata/fallback |
| cross-function effect | summary evidence | outside first subset |

The later reset of a balance is not the definition of an earlier balance read. Entry-balance -> external call -> reset can legitimately yield **no concrete in-function state Def–Use edge**. Do not invent backward edges to encode the vulnerability. Access-order/call-event relations need their own semantics and ablation.

Propose STATE_DEF_USE separately from scalar DATA_DEF_USE for semantic/provenance clarity. HGT dynamically registers canonical tuples, but extra tuples can add parameter slices; this is not parameter-neutral. Original E0 and archived E1/schema remain unchanged.

## Modifier boundary

Owner predicate -> sensitive write is not automatically data dependence. First inventory definitions, invocations, argument binding and underscore placeholders. Future execution support should initially require a uniquely resolved modifier, exactly one underscore, supported body and exact argument binding. Expand only analysis CFG, with context identity (function,invocation_span,modifier_span).

Distinct invocations may share physical HCG nodes: preserve analysis contexts and merged-pair evidence. Do not claim invocation sensitivity survives graph merging. Multiple underscores, ambiguous inheritance/overloads, recursion, unsupported returns or missing HCG anchors stay unsupported. Any control-dependence experiment is separate from state Def–Use.

## Projection and compatibility

Reuse v1.1 serializer-aware Projector, raw/compat executable-token alignment, AST ID/type/coordinate validation and evidence tables. No nearest-line or code-similarity mapping. No new HCG nodes, token/source-map changes or labels. Missing endpoints remain missing and are counted. State fallback leaves scalar DDG and original HCG intact; failed state analysis contributes no partial untrusted edge batch.

Version location semantics and relation policy. Preserve graph fingerprints, source hashes, parser/build identity, event provenance, CFG witnesses, missing projections and completeness.

## Primary references

- [Solidity 0.5.17 types](https://docs.soliditylang.org/en/v0.5.17/types.html): storage/reference and call semantics guide alias/call boundaries, not a claim of complete tree-sitter binding.
- [Solidity 0.5.17 modifiers](https://docs.soliditylang.org/en/v0.5.17/contracts.html#function-modifiers): execution ordering motivates explicit underscore handling.
- [Solidity 0.5.17 reentrancy](https://docs.soliditylang.org/en/v0.5.17/security-considerations.html#re-entrancy): external effects motivate the proposed conservative call-clobber policy; the exact IR is our design.
- [Solidity 0.5.17 storage layout](https://docs.soliditylang.org/en/v0.5.17/miscellaneous.html#layout-of-state-variables-in-storage): physical layout differs from symbolic location identity.
- [Slither source](https://github.com/crytic/slither/blob/master/slither/analyses/data_dependency/data_dependency.py) and [maintainer API](https://github.com/crytic/slither/wiki/data-dependency): SSA/reference/context distinctions are useful external checks. Its transitive variable-dependency API is not equivalent to this direct statement reaching-definition relation. No Slither installation/execution.

References checked 2026-10-13. Legacy 0.4.x examples require their own version verification; these documents do not certify the whole corpus.
