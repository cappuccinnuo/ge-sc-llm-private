# F3 候选图及进入训练的判断

| Task | Variant | STATE_DEF_USE | STATE_ACCESS_ORDER | CALL -> WRITE | New two-layer pairs | New context targets |
|---|---|---|---|---|---|---|
| reentrancy_author/contract | E3a | 6 | 0 | 0 | 1 | 1 |
| reentrancy_author/contract | E3b | 6 | 847 | 547 | 1546 | 576 |
| reentrancy_author/node | E3a | 3 | 0 | 0 | 1 | 1 |
| reentrancy_author/node | E3b | 3 | 829 | 547 | 1545 | 575 |
| access_control_author/contract | E3a | 11 | 0 | 0 | 17 | 12 |
| access_control_author/contract | E3b | 11 | 33 | 0 | 17 | 12 |
| access_control_author/node | E3a | 4 | 0 | 0 | 1 | 1 |
| access_control_author/node | E3b | 4 | 16 | 0 | 1 | 1 |

E3a = 固定E2 + EXACT STATE_DEF_USE；
E3b = E3a + STATE_ACCESS_ORDER + 已确认EXTERNAL_CALL_BEFORE_STATE_WRITE。
8个候选均有真实新增边，不覆盖E2；文件清单/SHA见F3_attempt_002/GRAPH_MANIFEST.json。

每条新边保留语义证据索引，指向同cohort的F3_EDGE_PROVENANCE.json。
节点、标签、token、映射、CFG/CG、DATA_DEF_USE全部保留。
使用精确AST映射；没有最近行号猜测。off恢复E2指纹，DGL未反射新关系。
EXACT表示位置精确，不表示路径必然执行或写入是所有路径的唯一来源。

| Task | Relation | Semantic candidates | Missing endpoint | Same HCG node | Projected evidence |
|---|---|---|---|---|---|
| reentrancy_author/contract | EXTERNAL_CALL_BEFORE_STATE_WRITE | 547 | 0 | 0 | 547 |
| reentrancy_author/contract | STATE_ACCESS_ORDER | 1108 | 57 | 204 | 847 |
| reentrancy_author/contract | STATE_DEF_USE | 17 | 11 | 0 | 6 |
| reentrancy_author/node | EXTERNAL_CALL_BEFORE_STATE_WRITE | 547 | 0 | 0 | 547 |
| reentrancy_author/node | STATE_ACCESS_ORDER | 1052 | 24 | 199 | 829 |
| reentrancy_author/node | STATE_DEF_USE | 8 | 5 | 0 | 3 |
| access_control_author/contract | STATE_ACCESS_ORDER | 111 | 55 | 22 | 34 |
| access_control_author/contract | STATE_DEF_USE | 29 | 14 | 0 | 15 |
| access_control_author/node | STATE_ACCESS_ORDER | 52 | 24 | 12 | 16 |
| access_control_author/node | STATE_DEF_USE | 10 | 5 | 0 | 5 |

事实、投影证据、去重模型边、两层新增节点对是不同分母。
已有两跳可达关系仍可能提供类型信息，不能自动称“冗余”；
新增可达上下文也不能自动换算成检测提升。

新候选具备继续语义审核和接口预检的条件；
尚不具备自动启动完整K折的全部证据：独立Oracle未批准、正式入口未迁移、
真实模型显存峰值未测。权限控制依赖独立处理。
