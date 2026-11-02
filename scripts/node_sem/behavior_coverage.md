# NodeSem NS-P3a 通用行为事实覆盖说明

This document explains generic Solidity behavior. It is documentation only;
production extraction never imports it or branches on the categories below.
NS-P3a produces facts, not STATIC vectors, context embeddings, predictions or
security judgments. The vector dimension is intentionally deferred to NS-P3b.

## Current policy and evidence boundary

The user's latest instruction supersedes the historical anonymous-view plan:
all new NS-P3a outputs use **original source spellings only**. No anonymous
source, anonymous feature file, model encoding, GPU execution or training is
produced. Old 8H records remain immutable provenance/reference material, not
an automatically paired original-name baseline.

Facts use the existing exact AST Projector. Its structural DOT `label` is used
only to establish identity; vulnerability labels, scores, split membership,
file names, absolute source positions and compiler versions are not behavior
features. Source coordinates and opaque symbol IDs can occur in audit joins,
but are not copied into feature groups. Node IDs in `dfg.from/to` and
`order.pre_ext_call` are references for later context lookup, not numeric
features. A relative `offset` is an AST-preorder distance within one callable;
`null` means it is unavailable (e.g. a modifier or parameter definition), not
zero.

Sealed F3 DATA_DEF_USE/READS_STATE/WRITES_STATE/ENV_FLOW evidence establishes
existing dependencies. L1 stores an opaque symbol identity rather than a
complete Symbol object; the approved lookup reconstructs the frozen route's
declaration table and performs an exact identity lookup, exposing only its
name and kind. It does not split an ID to guess a name or create new DDG edges.
The independent semantic CFG is an analysis IR and never replaces model edges.
Unprojected/eventless intermediate CFG blocks remain present.

## Group and field inventory

The following inventory covers the schema's public field names. Applicable
but unresolved analysis is `unknown`; known absence is a supported empty list
or false bit. Inapplicable groups are `{}` (or `[]` for list groups). This is
not a one-hot vector encoding yet.

### `external`

Fields: `kinds`, `value_attached`, `uninvoked_call_value`, `target_classes`, `value_class`, `data_class`, `return_handling`.

Applicable kinds: `statement`, `condition`.

A/A1-A4/F: `kinds` lists actually invoked call mechanisms; `value_attached` records value transfer syntax; `uninvoked_call_value` distinguishes a built call expression that is never invoked. `target_classes`, `value_class`, `data_class` describe expression origins without particular names. `return_handling` records a direct require/assert or if check, a supported later check of the assigned result, an unchecked assignment, or ignoring a result. Unknown amount/return binding is explicitly `unknown` with a reason, not none/ignored. These classifications do not prove a call succeeds or a check is sufficient.

### `state`

Fields: `writes`, `reads`, `array_size_change`, `status`.

Applicable kinds: `statement`, `condition`.

B: `reads`/`writes` are lists of `{var, shape, auth}` from sealed state dependencies. `var` is the original state spelling; `shape` is a type category, not source type text. `auth` means a declaration participates in an effective sender equality guard under the bounded rules. `array_size_change` covers confirmed array push/pop, length assignment or whole-array deletion. `status` separates complete supported access from unknown binding/projection. Positive partial evidence does not establish absence of other accesses.

### `dfg`

Fields: `defs`, `uses`, `from`, `to`, `status`.

Applicable kinds: `statement`, `condition`.

L1 context: `defs`/`uses` entries contain `{var, kind, from_offset}`. `from` contains `{node, offset}` and `to` contains `{node, offset, sink}`. They describe existing sealed edges and their use-site roles. `status` records whether the owning callable is supported. A definition with no projected consumer is not invented as an outgoing edge. Functions are not statement rows; a parameter definition can be referenced from a function node with a null relative distance.

### `order`

Fields: `reachable_from_ext_call`, `dominated_by_ext_call`, `write_then_call`, `call_then_write`, `ext_call_in_loop`, `status`, `pre_ext_call`.

Applicable kinds: `statement`, `condition`.

C and PRE_EXT_CALL: `reachable_from_ext_call` is same-function CFG reachability; `dominated_by_ext_call` requires a call on every CFG entry path to the destination. `write_then_call` and `call_then_write` relate different mapped statements. `ext_call_in_loop` is AST loop membership, not proof that a loop executes. `pre_ext_call` is a nearest reachable external-call node with relative distance. `status` is unknown when the semantic CFG or necessary projection is unsupported. This is syntactic control flow, not path feasibility, dynamic execution order or cross-function analysis.

### `checked_call`

Fields: `status`, `has_arithmetic`, `has_guard`, `result_condition_check`.

Applicable kinds: `statement`, `condition`, `function`, `modifier`.

Approved bounded extension: `status`, `has_arithmetic`, `has_guard`, `result_condition_check` summarize a uniquely resolved same-file internal/private or library call. The result-condition field requires the calculated result's identity to participate in a condition; co-occurrence of an unrelated guard is insufficient. No recursion, ambiguous overload resolution, external call summary or claim that arithmetic is safe is made. Unknown binding remains unknown.

### `self_condition`

Fields: `operand_classes`, `eq_pairs`, `early_exit_if`.

Applicable kinds: `condition`.

D3: `operand_classes` and `eq_pairs` describe only this require/assert/if/while/for condition; `early_exit_if` identifies the specified exit shape. An equality within a disjunction is not treated as an enforced equality. This is distinct from guards applying to a later or nested statement.

### `env`

Fields: `keys`, `uses`.

Applicable kinds: `statement`, `condition`, `state_decl`, `env`.

E/E1: `keys` uses 14 canonical environment keys. `uses` reports arithmetic, hash input, guard, state-write or call-target/value roles that are structurally supported. An env_source row supplies its key only and has no consumption use. Taint through arbitrary aliases or calls is not claimed.

### `arith`

Fields: `ops`, `on_state`, `small_int`, `from_param`, `from_env`, `sinks`, `in_unchecked`.

Applicable kinds: `statement`, `condition`.

G: `ops` identifies +, -, *, /, %, ** including supported compound/update forms. `on_state`, `small_int`, `from_param`, `from_env` describe resolved operands. `sinks` describes supported direct or sealed def-use destinations. `in_unchecked` denotes the Solidity unchecked syntax block; it is not a dataset-category switch. Presence of an operation does not assert overflow, underflow or an arithmetic defect.

### `loop`

Fields: `bound`.

Applicable kinds: `statement`, `condition`.

H: `bound` is none, constant, state/array-length, parameter/local or unknown. It describes the enclosing loop's bound expression, not termination, an execution count or computational complexity.

### `function_ctx`

Fields: `visibility`, `payable`, `read_only`, `is_constructor`, `is_fallback`, `has_modifier`, `name_case_only_differs_from_contract`.

Applicable kinds: `statement`, `condition`, `function`, `modifier`.

I: `visibility`, `payable`, `read_only`, `is_constructor`, `is_fallback`, `has_modifier`, `name_case_only_differs_from_contract` record callable context. Constructor identity follows constructor syntax or an exact old-style contract-name match. The sole permitted user-name feature is the case-only mismatch boolean; the names themselves are not emitted in this bit. This exception is documented rather than hidden as name-invariant semantics.

### `state_decl`

Fields: `shape`, `public`, `constant_immutable`, `has_initializer`, `auth`, `write_functions`, `read_functions`, `unguarded_write_functions`, `status`, `only_constructor_writes`, `unguarded_writer`, `read_in_guard`, `used_as_call_value_or_target`.

Applicable kinds: `state_decl`.

K and STATE_DECL: `shape`, `public`, `constant_immutable`, `has_initializer`, `auth` describe the declaration. `read_functions`/`write_functions` use zero/one/many categories; `unguarded_write_functions` is the number of known writing functions without a sender guard. `only_constructor_writes`, `unguarded_writer`, `read_in_guard`, `used_as_call_value_or_target` summarize supported uses. `status` marks incomplete binding or projection. A zero known count under unknown status must not be interpreted as proven absence.

### `fn_summary`

Fields: `status`, `external_call`, `state_write`, `sender_guard`, `auth_write`, `selfdestruct`, `delegatecall`, `loop`, `ext_call_in_loop`, `timestamp`, `tx_origin`, `write_then_call`, `call_then_write`.

Applicable kinds: `function`, `modifier`.

L: `external_call`, `state_write`, `sender_guard`, `auth_write`, `selfdestruct`, `delegatecall`, `loop`, `ext_call_in_loop`, `timestamp`, `tx_origin`, `write_then_call`, `call_then_write` summarize a callable's mapped facts. `status` reports incompleteness. Summaries are of this callable, without recursively following arbitrary callees.

### `contract_summary`

Fields: `status`, `kind`, `auth_state_count`, `explicit_constructor`, `payable_fallback`, `selfdestruct`, `auth_state`.

Applicable kinds: `contract`.

M and CONTRACT: `kind` distinguishes contract/library/interface; `explicit_constructor`, `payable_fallback`, `selfdestruct`, `auth_state` summarize declarations and callable facts. `auth_state_count` is the count of resolved authorization declarations, including supported same-file base scope. `status` records incompleteness. It does not infer deployed behavior or inherited code from unavailable external files.

### Guard lists, syntax, names and audit metadata

- `guards`: each entry has `rule`, `kind`, `polarity`, `operand_classes`,
  `eq_pairs`, `is_sender_guard`, `offset`. Rules are preceding require/assert
  (1), enclosing if branch (2), earlier exiting if (3), loop condition (4),
  modifier prefix (5), modifier conditional placeholder (5p), or one-level
  internal/private check (6). Modifier resolution is same-file and bounded.
  Negative branch/early-exit polarity is normalized; OR alternatives do not
  establish an enforced equality. Loop conditions do not contribute D1/D2.
- `guard_status`: none/present/unknown; `nearest`: a guard-list index or null.
  An unresolved modifier must not become a claim of no guard. Guards after an
  if join are not inferred by plain CFG dominance.
- `syntax`: assign, add_assign, sub_assign, compound_assign, delete, emit,
  ternary, index, deep_member, literal, hash, ecrecover, abi_encode, exit,
  return, assembly. These are behavioral syntax flags, not safety labels.
- `names`: original variable spellings used by M2, isolated from the static
  profile. They come from supported symbol/state evidence. This separation
  must be retained by NS-P3b.
- `unresolved`: reason-to-positive-count map for auditable incompleteness.
- `provenance`: `source_sha256`, `store_refs` (path/SHA records), `view`.
  Current `view` is strictly original. Provenance is not a feature group.
- `node_kind`: statement, condition, state_decl, function, modifier,
  contract, env, end or other. End nodes contain only defaults; env nodes
  contain only their environment key in applicable behavior groups.

## Exact canonical vocabulary counts

- external kinds: **8**; `call`, `delegatecall`, `staticcall`, `send`, `transfer`, `member`, `new`, `selfdestruct`.
- call target classes: **8**; `msg.sender`, `tx.origin`, `param`, `state`, `local`, `literal`, `this`, `other`.
- amount classes including unknown: **9**; `none`, `literal`, `param`, `state`, `msg.value`, `this.balance`, `local`, `arith`, `unknown`.
- data classes: **4**; `none`, `msg.data`, `param`, `other`.
- return handling including unknown: **7**; `not_applicable`, `checked_in_require`, `checked_in_if`, `assigned_checked`, `assigned_unchecked`, `ignored`, `unknown`.
- condition operand classes: **12**; `msg.sender`, `tx.origin`, `state`, `param`, `local`, `literal`, `timestamp`, `block`, `msg.value`, `balance`, `external_result`, `hash`.
- effective equality combinations: **6**; `env_state`, `env_param`, `env_literal`, `state_param`, `hash_state_literal`, `time_state_param`.
- state shapes: **8**; `mapping`, `array`, `address`, `integer`, `bool`, `bytes_string`, `struct_contract`, `other`.
- syntax flags: **16**; `assign`, `add_assign`, `sub_assign`, `compound_assign`, `delete`, `emit`, `ternary`, `index`, `deep_member`, `literal`, `hash`, `ecrecover`, `abi_encode`, `exit`, `return`, `assembly`.
- canonical environment keys: **14**; `msg.sender`, `msg.value`, `msg.data`, `msg.sig`, `tx.origin`, `tx.gasprice`, `block.timestamp`, `block.number`, `block.difficulty`, `block.coinbase`, `block.gaslimit`, `blockhash`, `gasleft`, `this.balance`.

The frozen L3 SPELLINGS dictionary has exactly **18 spelling entries** for
**14 environment keys**: four extra spellings are now, msg.gas,
block.blockhash(...), and address(this).balance. These counts were checked
against the actual frozen module, not inferred from the diagram.

The 14 environment keys later merge into the 11 E-group categories specified
by the design (for example msg.data/msg.sig); no such vector is generated in
NS-P3a. The following spelling aliases are explicit, not guessed from a
compiler version:

| Syntax spellings | Generic fact |
|---|---|
| now; block.timestamp | block.timestamp |
| msg.gas; gasleft() | gasleft |
| this.balance; address(this).balance | this.balance |
| block.blockhash(...); blockhash(...) | blockhash |
| throw; revert(...); require(false) | exit syntax, after applicable builtin-binding checks |
| sha3; keccak256 | hash syntax; sha256/ripemd160 also contribute the generic hash flag |
| suicide; selfdestruct | selfdestruct call kind, after binding checks |
| callcode; delegatecall | delegatecall call kind |
| .value(x) followed by invocation; {value:x} invocation | attached-value call; an uninvoked .call.value(x) remains separate |
| legacy constant function; view; pure | read_only callable flag |

These aliases are syntax normalization, not proof that all language versions
have identical operational semantics. The modern call-options Oracle uses a
0.6 pragma; calling it valid 0.5 Solidity would be incorrect. No Oracle in
this batch claims solc validation.

## Relevance to the original seven task categories

This is an explanatory mapping only. None of these names is an extractor
parameter, enum value, feature field or branch condition. Generic facts can
matter to several categories; their relevance does not prove predictive gain.

| Category | Potentially informative generic behavior | What these facts do not prove |
|---|---|---|
| reentrancy | Actual calls, state access, call/write order, guards, value/target origins | Callback execution, exploitability, cross-contract feasibility |
| access_control | Effective sender equalities, modifier/internal checks, authorization-state writes, constructors, delegatecall | A complete authorization policy or correct deployment initialization |
| arithmetic | Operator/type-width/origin facts, sinks, explicit checked-result summaries, unchecked syntax | Integer bounds or that a helper prevents all incorrect arithmetic |
| denial_of_service | Loop bound classes, external calls inside loops, array growth, return handling | Gas bounds, liveness or an adversarial execution schedule |
| front_running | Environment origins, state transitions, hash guards, targets and amounts | Mempool behavior, transaction ordering or economic incentives |
| time_manipulation | Timestamp/block operands, hash/arithmetic/guard uses, state and call sinks | Miner influence bounds or a feasible timing attack |
| unchecked_low_level_calls | Low-level call types, assigned/ignored/checked return handling, unsupported binding | Exhaustive path-sensitive checking or safe error recovery |

## Support limits and interpretation

1. The other five categories' smoke checks parse original source only. They
   have no sealed F3 evidence input. DFG, state-access completeness and semantic
   CFG order therefore remain unknown. Successful execution means interface
   portability and AST behavior coverage, not complete feature coverage.
2. Frozen L1 has a scalar and bounded syntax scope. Unknown definitions, state
   aliases, absent projections, unresolved modifiers and ambiguous overloads
   are not converted into known negative facts. Names or nearest line numbers
   are never used to fabricate a dependency.
3. Statement granularity cannot encode every element inside a tuple or every
   event inside one merged HCG condition separately. Original HCG nodes, base
   relations, labels, tokenizer and HGT stay unchanged.
4. The bounded checked-call extension distinguishes a result check from mere
   arithmetic/guard co-occurrence. It is not a complete type system, a safety
   proof, recursive summary analysis or interprocedural DFG.
5. A function/contract summary can contain known positive facts while its
   status is unknown. Consumers must retain the unknown status; absence of a
   positive bit alone is not complete evidence.
6. Models, STATIC encoding, M2 rendering, training plans and any claim of
   detector improvement are outside NS-P3a. Original-view experiments need
   appropriately matched original-view baselines; anonymous 8H results cannot
   be silently relabeled as such baselines.
7. Final model experiments are planned for a server with sufficient VRAM.
   The RTX3050 4GiB restriction is local development hardware, not a reason
   to reduce the scientific model design or silently change its parameters.


## Statistical and reproducibility notes

Categorical defaults (none, not_applicable, zero and default) must not be
interpreted as active positive features simply because their strings are
nonempty. The extractor's `nonempty` counts are serialized-presence counts;
interpret the accompanying `positive` and `field_applicable` counts when
assessing behavior coverage. Guard-unknown statistics use all emitted rows as
the recorded denominator; a statement/condition-only denominator can be
computed explicitly and should not be silently substituted.

The batch runtime closure binds each manifest SHA, all NodeSem fact producer
modules and the complete frozen `_code_refs` dependency snapshot. It supplements
individual manifests' direct implementation references without changing any
already-sealed manifest or historical input. Final byte-level snapshot checks
must verify frozen code did not change during extraction.

## NS-P3a2 correction (2026-11-02)

State support now follows each statement's own AST access roles; historical
unresolved counts remain diagnostics, not a blanket function-level status.
K/L/M use unknown_fields: mask only listed fields when encoding, retaining
the other known facts. K consumes all sealed L2 access identities, even without
HCG projection. L/M inspect the full AST, including unprojected emit/fallback.

All effective OR alternatives must restrict msg.sender/tx.origin for a
disjunctive sender guard. Negative conjunctions use De Morgan. Original AST
token grouping is adapted only inside NodeSem; unresolved expressions do not
prove a guard. This is not general boolean theorem proving.

44 hand-written Oracle sources pass deterministic spelling-bijection checks,
with 6 additional sealed-layer checks. These are parser-only fixtures, not
compiled Solidity or a new anonymous experiment. Production remains original.
Remaining uncertainties and exact before/after counts are in NS_P3A2_REPORT.md.
