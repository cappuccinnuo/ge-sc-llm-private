# Stage G fixed fold 0 coverage note

Date: 2026-10-14. Codex. Read-only structural explanation; no performance predictions.

All counts were independently counted from one frozen E3b graph at a time and matched task_manifest support. Only the existing restricted NetworkX reader was used; neither torch nor DGL was imported. No graph, model, source, split, label or sealed code was changed.

E2 has zero edges in the three new relations. E3a uses only STATE_DEF_USE; E3b additionally uses the two order relations. Target counts are unique directly targeted HCG nodes, not independently evaluated source lines or measured prediction changes.

| Task | Relation | Train edges / files / targets | CV val edges / files / targets |
|---|---|---:|---:|
| reentrancy_author_contract | STATE_DEF_USE | 5 / 4 / 4 | 1 / 1 / 1 |
| reentrancy_author_contract | STATE_ACCESS_ORDER | 675 / 44 / 674 | 172 / 17 / 172 |
| reentrancy_author_contract | EXTERNAL_CALL_BEFORE_STATE_WRITE | 427 / 22 / 427 | 120 / 10 / 120 |
| access_control_author_contract | STATE_DEF_USE | 11 / 6 / 10 | 0 / 0 / 0 |
| access_control_author_contract | STATE_ACCESS_ORDER | 29 / 21 / 28 | 4 / 3 / 4 |
| access_control_author_contract | EXTERNAL_CALL_BEFORE_STATE_WRITE | 0 / 0 / 0 | 0 / 0 / 0 |
| reentrancy_author_node | STATE_DEF_USE | 1 / 1 / 1 | 2 / 1 / 1 |
| reentrancy_author_node | STATE_ACCESS_ORDER | 711 / 39 / 711 | 118 / 5 / 117 |
| reentrancy_author_node | EXTERNAL_CALL_BEFORE_STATE_WRITE | 457 / 27 / 457 | 90 / 5 / 90 |
| access_control_author_node | STATE_DEF_USE | 4 / 3 / 3 | 0 / 0 / 0 |
| access_control_author_node | STATE_ACCESS_ORDER | 12 / 11 / 11 | 4 / 4 / 4 |
| access_control_author_node | EXTERNAL_CALL_BEFORE_STATE_WRITE | 0 / 0 / 0 | 0 / 0 / 0 |

## Validation files with direct added relations

### reentrancy_author_contract

Frozen files: train 113, CV validation 29.

- STATE_DEF_USE: 0xa5b91fbfec2f9a708592f9cd3c9e20becdfcb816.sol
- STATE_ACCESS_ORDER: 0x9652847049867929260c9e16b31dfbb3b011817f.sol, 0xa08d1762538439848b71a39cfef7f0454f1176ed.sol, 0xa5b91fbfec2f9a708592f9cd3c9e20becdfcb816.sol, 0xa7f1863212762d6b6f7b958b46a21ba9e4818422.sol, buggy_17.sol, buggy_20.sol, buggy_25.sol, buggy_27.sol, buggy_31.sol, buggy_39.sol, buggy_44.sol, buggy_7.sol, modifier_reentrancy.sol, reentrancy_bonus.sol, reentrancy_insecure.sol, reentrancy_simple.sol, simple_dao.sol
- EXTERNAL_CALL_BEFORE_STATE_WRITE: buggy_17.sol, buggy_20.sol, buggy_25.sol, buggy_27.sol, buggy_39.sol, buggy_44.sol, buggy_7.sol, reentrancy_insecure.sol, reentrancy_simple.sol, simple_dao.sol
### access_control_author_contract

Frozen files: train 91, CV validation 23.

- STATE_DEF_USE: (none)
- STATE_ACCESS_ORDER: 0x0a7073207bac23865e0e3b204615364b5a9d3783.sol, buggy_43.sol, buggy_49.sol
- EXTERNAL_CALL_BEFORE_STATE_WRITE: (none)

Registered relation types without train edges (allowed, audited; no training-support claim):
- ['expression_statement', 'STATE_ACCESS_ORDER', 'new_variable']: val edges=1
- ['new_variable', 'STATE_ACCESS_ORDER', 'expression_statement']: val edges=1
### reentrancy_author_node

Frozen files: train 63, CV validation 8.

- STATE_DEF_USE: buggy_47.sol
- STATE_ACCESS_ORDER: buggy_19.sol, buggy_2.sol, buggy_47.sol, reentrancy_cross_function.sol, reentrancy_insecure.sol
- EXTERNAL_CALL_BEFORE_STATE_WRITE: buggy_19.sol, buggy_2.sol, buggy_47.sol, reentrancy_cross_function.sol, reentrancy_insecure.sol
### access_control_author_node

Frozen files: train 51, CV validation 6.

- STATE_DEF_USE: (none)
- STATE_ACCESS_ORDER: buggy_11.sol, buggy_43.sol, buggy_44.sol, buggy_49.sol
- EXTERNAL_CALL_BEFORE_STATE_WRITE: (none)

## Where the STATE_DEF_USE evidence resides

The contract-level set consists of 12 constructor edges and 5 edges in one pricing function. This counts task graph edges, not independent vulnerabilities. The node task is a subset of the corresponding contract task and must not be added as independent evidence.

| Task | Split | File | Function | Edge count |
|---|---|---|---|---:|
| reentrancy_author_contract | train | 0xa4f9fe0ad9b9765dc0364444332fa4c69923a6d3.sol | constructor() public | 1 |
| reentrancy_author_contract | train | 0xa8ec550c291993a450ea525d90863e61a7ebef5c.sol | constructor () public | 1 |
| reentrancy_author_contract | train | buggy_32.sol | constructor() public | 1 |
| reentrancy_author_contract | train | buggy_47.sol | constructor() public | 2 |
| reentrancy_author_contract | val | 0xa5b91fbfec2f9a708592f9cd3c9e20becdfcb816.sol | constructor() public | 1 |
| access_control_author_contract | train | 0x0c6e8a8358cbde54f8e4cd7f07d5ac38aec8c5a4.sol | constructor() public | 1 |
| access_control_author_contract | train | 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol | function getCurrentTokenPrice() private returns (uint) | 5 |
| access_control_author_contract | train | 0x0ef23ae0a27130999bf9d886e9598ff355ecf323.sol | constructor(bytes32 voucher_token, uint _lifetime) public | 1 |
| access_control_author_contract | train | buggy_32.sol | constructor() public | 1 |
| access_control_author_contract | train | buggy_47.sol | constructor() public | 2 |
| access_control_author_contract | train | multiowned_vulnerable.sol | constructor() public | 1 |
| reentrancy_author_node | train | buggy_32.sol | constructor() public | 1 |
| reentrancy_author_node | val | buggy_47.sol | constructor() public | 2 |
| access_control_author_node | train | buggy_32.sol | constructor() public | 1 |
| access_control_author_node | train | buggy_47.sol | constructor() public | 2 |
| access_control_author_node | train | multiowned_vulnerable.sol | constructor() public | 1 |

## Interpretation boundaries

- Both access-control fold-0 validation populations have zero STATE_DEF_USE edges. All five pricing-function edges are in the access-control contract TRAIN partition; that source file is absent from the node task. This limits what this fold can directly test about state dependence at validation time. It does not imply E3a predictions must equal E2, because shared parameters are trained differently.
- Access-control E3b adds only 33/16 STATE_ACCESS_ORDER edges (contract/node) and no CALL->WRITE edges. Its frozen full-task new two-layer reachability remains 17 pairs/12 targets for contract, 1 pair/1 target for node, the same as E3a relative to E2. Thus those order edges add relation semantics but no further two-layer reachable pairs beyond E3a in this graph; this is not proof that typed messages have no value.
- Reentrancy has broader order-edge coverage, but much of it may reflect repeated injection templates. Relation presence and matching counts are not evidence of improved F1 or of exploitability.
- A send/transfer/call followed by a write is a structural may-reach order. It is not a definite dependency, does not preserve values across callbacks and does not establish a successful transaction or exploitable vulnerability.
- The pricing function reads bonusCalculationFactor after assigning it; constructor edges initialize owner/founder/supply/root/time fields. Neither set establishes runtime permission-control dependence or cross-function state summaries.
- Frozen Stage F topology counts cover the complete task graph. The tables above split direct edge endpoints by file membership; they are not a fresh full-model receptive-field or counterfactual prediction analysis.
- No labels/predictions were used to decide the included files or relations. No weak fold was dropped or replaced.


## Frozen HGT aggregation caveat (source-verified)

The actual **HGTLayer uses relation-wise sum, then cross-canonical `mean`**, not cross-relation sum. In `sco_models/model_hgt.py:110-117`, `active_edge_dict` includes canonical relations present in the full graph and the registered dictionary; it is not filtered to the relations with incoming edges in each validation file or node. The relation operation is attention-weighted `fn.u_mul_e` followed by `fn.sum`; `G.multi_update_all(..., cross_reducer='mean')` combines those outputs.

The installed DGL implementation at `heterograph.py:4762-4778` gathers every supplied relation output by destination node type. `reduce_dict_data` at `heterograph.py:5920-5936` stacks those tensors and applies mean across the relation axis. This merge does not apply a per-node nonzero-incoming-degree mask. The separate HeteroRGCNLayer later in the project file uses `sum`; that is not the HGTLayer under review.

Consequently, **zero direct added edges in a validation file does not guarantee unchanged logits**. There are two distinct reasons:

1. Enhanced-graph training may change the shared HGT/classifier parameters, which are also used for that validation file.
2. New registered canonical relations participate in the aggregation for their destination node types in the full fixed graph. A new relation output can alter the cross-relation mean/normalization even at a node with no incoming edge of that relation. Subsequent projection, residual mixing and normalization further determine the representation; unchanged output is not guaranteed merely from the direct-edge count.

The coverage table therefore measures direct structural support, not an exact set of predictions that can change. This is a source-based explanation of possible mechanisms, **not evidence that a representation changed in a measured run or that accuracy improved**. No runtime counterfactual or GPU experiment was performed for this note. Source hashes and code locations are recorded in `coverage_note.json`.
