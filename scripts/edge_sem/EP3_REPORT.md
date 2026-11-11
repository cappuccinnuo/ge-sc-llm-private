# EP3：GUARDS构建与完整E1关系CPU验收

修改AI：Codex；2026-11-10。

两个节点任务完成，全部守卫记录精确映射，EP2旧行保持；本轮没有训练，不报告检测改善。

起点edge-sem f138c6b2b42cc2131866005deaf6d98bb070f651；PROMPTS r10 SHA 5946f94a53dd04f4e73a62967e0ef15f3e85f958f680bc00351deda5890ab00f。先读取§4.1及方案/EP3要求，ff-only同步确认已为最新；旧历史文档只追加。

## 实现与批准选择

修改build_f4.py和tests/test_build_f4_model.py；新增guard_edges.py、recon/ep3_common.py、ep3_archive.py、ep3_run.py、ep3_report.py、ep3_verify.py；新增tests/test_build_f4_guards.py、test_build_f4_guards_model.py和fixtures/ep3_guards.sol。报告EP3_REPORT.md，独立产物artifacts/ep3_v1。旧guard_source、call_resolve、DFG、NodeSem、作者代码及全部既有产物不改。

1. 每文件复用同一个GuardAnalyzer，目标仅为精确投影且AST类型属于STATEMENTS的节点，含条件/循环和修饰器体语句；定义节点不作GUARDS目标。非修饰器直接使用_anchor，映射缺失则保存完整审计并阻止任务manifest封存，不猜测邻近语句。
2. 修饰器来源由既有modifier_guard_sources取inner_anchor；每个目标的modifier记录必须位于for_node列表末尾，并与来源列表逐项public_record相等。GUARDS直接从修饰器体守卫到被修饰语句，保留invocation_anchor用于溯源，不经过MOD_APPLY。继承使用同文件原冻结绑定。
3. 同一源/目标只建一条GUARDS，evidence按for_node原顺序保留全部记录，顶层kind为去重排序列表。operand_classes保留msg.sender、timestamp等原始值，未映射成caller_identity。loop_cond的空operand_classes保留冻结设计；public_record实际还有offset=0，也原样保留，不将它当成新属性。
4. unknown目标仍保留已确认的守卫边；自环计数而不建边。add_edges对GUARDS两端增加STATEMENTS校验，其他两类角色校验不变，仍返回独立深拷贝。
5. 用户批准显式只读EP2归档加载（call_77a0cd9dcd464ce3b3ab20d7ad8bb54f）：旧manifest绑定build_f4 SHA，正常加载在实现变化后仍拒绝。ep3_archive核对旧verification/summary/报告、旧源码SHA、预修改快照及所有输入/产物；只允许两个固定EP2 manifest、两个明确修改文件的快照例外，旧plan/seal/产物不改。EP2模型回归改用该显式入口；默认生产load_edges仍检查当前SHA。
6. 延续已批准的Projector结构身份边界，只允许冻结代码读取label中的AST编号/类型/坐标。建边不使用漏洞标签、预测、标识符名字的漏洞含义；函数名只为最大入边位置的诊断显示，声明名字只参与原绑定过程。

## 真实结果

| 任务 | 文件实例 | MOD_APPLY | CALL_SITE | GUARDS正向边 | 守卫记录 | 多证据边 | unknown目标 |
|---|---:|---:|---:|---:|---:|---:|---:|
| reentrancy_node | 71 | 178 | 570 | 6921 | 6956 | 31 | 12 |
| access_control_node | 57 | 195 | 564 | 4502 | 4537 | 31 | 12 |

两个任务分别完成71、57个文件实例。GUARDS记录6956/4537，逐文件与EP0/RECON完全一致，无目标集合差异。非修饰器6340/6340、3822/3822，修饰器616/616、715/715全部精确映射；没有映射缺失或自环。去重后6921/4502条，和EP0b预计数量完全一致。

每任务31条边含多条证据，kind组合均为internal_check；共35条重复记录被合并到这些边，记录本身未删除。所有MOD_APPLY与CALL_SITE JSON行按规范化文本排序后逐行复现EP2（178/570、195/564），不仅核对汇总数。

每任务12个guard_status=unknown目标，其中2个仍有已确认GUARDS入边，保持未知状态。EP2的9个未解析modifier_invocation全部属于构造函数头，冻结一般标识符解析均为contract_declaration；原modifier成员查找为空，失败原因modifier_binding保持，因此不增加MOD_APPLY，也不把基类构造应用当成修饰器守卫。

| kind | 重入记录/映射 | 访问控制记录/映射 |
|---|---:|---:|
| require | 4082/4082 | 2586/2586 |
| if_branch | 994/994 | 748/748 |
| early_exit | 1008/1008 | 226/226 |
| loop_cond | 175/175 | 181/181 |
| modifier | 616/616 | 715/715 |
| internal_check | 81/81 | 81/81 |

## 入度统计与最大值身份

| 任务 | 分母 | 节点数 | 平均GUARDS入边 | 中位数 | 最大值 |
|---|---|---:|---:|---:|---:|
| reentrancy_node | 全部原F3节点（含env） | 12223 | 0.566228 | 0 | 13 |
| reentrancy_node | 作者节点（不含env） | 12036 | 0.575025 | 0.0 | 13 |
| reentrancy_node | 本轮语句目标 | 6635 | 1.043105 | 1 | 13 |
| access_control_node | 全部原F3节点（含env） | 7892 | 0.570451 | 0.0 | 13 |
| access_control_node | 作者节点（不含env） | 7710 | 0.583917 | 0.0 | 13 |
| access_control_node | 本轮语句目标 | 4664 | 0.965266 | 1.0 | 13 |

| 任务 | 文件/函数 | source SHA256 | 最大值节点ID |
|---|---|---|---|
| reentrancy_node | buggy_24.sol/invest | 56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb | 1868, 1869, 1870 |
| access_control_node | buggy_24.sol/invest | 1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b | 689, 690, 691 |

同名buggy_24.sol分别按task/cohort与source SHA识别；完整逐节点入度和直方图保存在f4_audit.json，不按文件名混同。

## CPU模型闸门

| 任务/fold0 | G3R-T→G4R canonical数 | 相对EP2新增GUARDS行 | 全部E1新行/层 | 参数量 | 构造秒数 | 前后向秒数 |
|---|---|---:|---:|---:|---:|---:|
| reentrancy_node | 220→274 | 42 | 54 | 5,619,908 | 24.695 | 5.436 |
| access_control_node | 234→292 | 46 | 58 | 5,767,652 | 10.453 | 3.289 |

两任务空E1的G4R与G3R-T在canonical键、端点、全部参数及eval输出逐位相同。完整三关系加入后通过独立validate_registration。相对EP2新增GUARDS/REV_GUARDS规范关系42/46行；加上原12行MOD_APPLY/CALL_SITE，共54/58行E1参数/层，全部用原relation_seed与锚模型Xavier范围逐位核对，重复新鲜构造相同；所有共享参数及旧关系行保持与G3R-T一致。

CPU目标为mean(logits²)，前向/反向有限、optimizer step=0；不是监督训练或检测成绩。构造/前后向时间只是本机单次记录，不能据此推断GPU显存或训练性能。历史8H特征仍只作EP1/EP2延续的CPU等价夹具，不决定后续主视图。记录中的config.device=cuda:0来自历史配置；实际CUDA_VISIBLE_DEVICES为空、cuda_initialized=false。

## 完整新增规范关系

### reentrancy_node：全部新增GUARDS规范关系

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | expression_statement | 3323 |
| expression_statement | GUARDS | for | 24 |
| expression_statement | GUARDS | if | 546 |
| expression_statement | GUARDS | new_variable | 575 |
| expression_statement | GUARDS | return | 249 |
| expression_statement | GUARDS | while | 18 |
| expression_statement | REV_GUARDS | expression_statement | 3323 |
| expression_statement | REV_GUARDS | for | 60 |
| expression_statement | REV_GUARDS | if | 1658 |
| expression_statement | REV_GUARDS | while | 36 |
| for | GUARDS | expression_statement | 60 |
| for | GUARDS | if | 21 |
| for | GUARDS | new_variable | 34 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | expression_statement | 24 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | expression_statement | 1658 |
| if | GUARDS | if | 173 |
| if | GUARDS | new_variable | 81 |
| if | GUARDS | return | 90 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | expression_statement | 546 |
| if | REV_GUARDS | for | 21 |
| if | REV_GUARDS | if | 173 |
| if | REV_GUARDS | while | 13 |
| new_variable | REV_GUARDS | expression_statement | 575 |
| new_variable | REV_GUARDS | for | 34 |
| new_variable | REV_GUARDS | if | 81 |
| new_variable | REV_GUARDS | while | 8 |
| return | REV_GUARDS | expression_statement | 249 |
| return | REV_GUARDS | if | 90 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | expression_statement | 36 |
| while | GUARDS | if | 13 |
| while | GUARDS | new_variable | 8 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |

### access_control_node：全部新增GUARDS规范关系

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | expression_statement | 2562 |
| expression_statement | GUARDS | for | 20 |
| expression_statement | GUARDS | if | 166 |
| expression_statement | GUARDS | new_variable | 237 |
| expression_statement | GUARDS | return | 240 |
| expression_statement | GUARDS | while | 18 |
| expression_statement | REV_GUARDS | expression_statement | 2562 |
| expression_statement | REV_GUARDS | for | 58 |
| expression_statement | REV_GUARDS | if | 678 |
| expression_statement | REV_GUARDS | while | 42 |
| for | GUARDS | expression_statement | 58 |
| for | GUARDS | if | 21 |
| for | GUARDS | new_variable | 33 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | expression_statement | 20 |
| for | REV_GUARDS | if | 1 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | expression_statement | 678 |
| if | GUARDS | for | 1 |
| if | GUARDS | if | 185 |
| if | GUARDS | new_variable | 90 |
| if | GUARDS | return | 115 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | expression_statement | 166 |
| if | REV_GUARDS | for | 21 |
| if | REV_GUARDS | if | 185 |
| if | REV_GUARDS | while | 14 |
| new_variable | REV_GUARDS | expression_statement | 237 |
| new_variable | REV_GUARDS | for | 33 |
| new_variable | REV_GUARDS | if | 90 |
| new_variable | REV_GUARDS | while | 8 |
| return | REV_GUARDS | expression_statement | 240 |
| return | REV_GUARDS | if | 115 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | expression_statement | 42 |
| while | GUARDS | if | 14 |
| while | GUARDS | new_variable | 8 |
| while | GUARDS | while | 2 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |
| while | REV_GUARDS | while | 2 |

## 稀疏新增规范关系（边数小于20）

### reentrancy_node：新增关系中边数小于20

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | while | 18 |
| for | GUARDS | while | 2 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | while | 13 |
| new_variable | REV_GUARDS | while | 8 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | if | 13 |
| while | GUARDS | new_variable | 8 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |

### access_control_node：新增关系中边数小于20

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | while | 18 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | if | 1 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | for | 1 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | while | 14 |
| new_variable | REV_GUARDS | while | 8 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | if | 14 |
| while | GUARDS | new_variable | 8 |
| while | GUARDS | while | 2 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |
| while | REV_GUARDS | while | 2 |

## 测试与开发失败记录

完整CPU回归：EdgeSem 198、NodeSem 1353、DFG v2 2653，合计4204项通过，无跳过。新增19项守卫/归档用例及2项真实模型闸门；原EP2模型测试仍运行。覆盖require、时间/假分支极性、内部检查多证据、双修饰器/继承、基类构造unknown、未知情况下保留已知边、early_exit、算术、循环/条件目标、缺失精确来源、非法GUARDS角色、输入不变与归档摘要篡改拒绝。

首次guard_unit_tests为35 passed、1 failed：诊断代码错误地只查询ClosedScopeJ.declarations，它仅包含合约成员，不包含合约声明，因此基类构造函数名的声明类型为空。修正为使用冻结AstSemantics.resolve_identifier输出声明类型，同时保留modifier_scope_declaration_types/anchors原查询结果。这个修正只影响描述，不修改任何绑定、守卫或边选择规则。失败日志与原guard_edges源码快照保存在execution/和development/，修正后的guard_unit_identifier为36 passed。未覆盖失败现场，真实建边与模型闸门均一次通过，无训练重试。

最终只读ep3_verify核对750份冻结源码、354项DFG计算引用、60份其他EdgeSem源码、389份历史产物、697项输入引用和8H load。按原源码重新取得每个语句的冻结守卫序列，逐条核对JSONL的节点身份、锚点、来源、极性、原始操作数类别、顺序及全部证据；同时核对EP2行、逐节点入度及模型canonical边数。移除内存副本新增边后，指纹必须与原F3完全相同。验证收据见verification.json；三文档原字节前缀保持且UTF-8/中文检查通过。

## 执行命令

实际命令（mando、CPU；TREE_SITTER_LIB_DIR沿用原值，PYTHONDONTWRITEBYTECODE=1，OMP/MKL各2）：

    python -B -m scripts.edge_sem.recon.ep3_common
    python -B -m scripts.edge_sem.recon.ep3_run --name guard_unit_identifier -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_build_f4_guards.py scripts/edge_sem/tests/test_build_f4_calls.py
    python -B -m scripts.edge_sem.recon.ep3_run --name build_reentrancy_node -- -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/ep3_v1/reentrancy_node
    python -B -m scripts.edge_sem.recon.ep3_run --name build_access_control_node -- -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/ep3_v1/access_control_node
    python -B -m scripts.edge_sem.recon.ep3_run --name edge_tests -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name nodesem_tests -- -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name dfg_tests -- -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name collect_report -- -m scripts.edge_sem.recon.ep3_report
    python -B -m scripts.edge_sem.recon.ep3_run --name doc_check -- -m scripts.node_sem.doc_check --expect-cjk HANDOVER.md:293293 docs/training_changes_2026-10-07.md:1087897 scripts/edge_sem/PROGRESS.md:37100 scripts/edge_sem/EP3_REPORT.md
    python -B -m scripts.edge_sem.recon.ep3_run --name verify -- -m scripts.edge_sem.recon.ep3_verify

首次完整EdgeSem回归设置EDGESEM_EP3_RECEIPTS为本批probes绝对路径，成功后排他写两份CPU收据。日常测试不设置它；所有输出目录/收据拒绝覆盖。精确argv、耗时、退出码与日志SHA存于execution/。不要再次运行这些命令覆盖已完成批次。

## 局限与停止位置

GUARDS表达冻结分析器支持范围内的词法/受限调用守卫证据，不证明完整控制依赖、授权正确性或漏洞防护有效。MOD_APPLY、CALL_SITE、GUARDS三种E1关系现已接入；E2边属性、EdgeAware层、正式执行器与效果评估仍属于后续Prompt，EP3不实现EP4。现有loop_cond操作数为空、unknown及调用覆盖局限保留。EP0e原312/347门槛未通过的历史结论不改写。

最终实验将在显存充足的服务器另建批次，本机RTX3050 4GiB仅限制当前开发；本轮未部署服务器、未测GPU显存、未训练。产物保存在WSL，未向C盘另存大型缓存。D1主视图、D2训练协议与D3七类冻结仍须在训练前按文档确认；本轮没有据CPU夹具默认批准它们。按共享流程本地提交，停在EP3，不自动push。
