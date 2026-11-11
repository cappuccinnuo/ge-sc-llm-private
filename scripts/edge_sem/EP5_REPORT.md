# EdgeSem EP5 结果报告（2026-11-11）

基于PROMPTS r12、HEAD cf879c2c833230153f13e4ca134b95d799c07fa0。只完成两个节点任务的CPU诊断与属性修正，未训练、未用GPU、未推进EP6。

## EP4修正与硬条件

| 任务 | 正向属性行 | 原第20位=1 | 新第20位=1 | 循环头例外 |
| --- | --- | --- | --- | --- |
| 重入节点 | 31372 | 311 | 61 | 24 |
| 访问控制节点 | 21830 | 322 | 68 | 25 |

自然循环沿用回边目标支配源的定义；删除全部回边后，只要任一def/use块对前向可达即否决循环携带标记，已批准的同图节点自依赖例外除外。两个任务edge_keys逐行相同，除第20位外的73列逐位相同，新第20位为旧值的子集。其他关系第20位仍全0。EP4 attributes_attempt3及其seal保持原字节；后续EP6–EP9必须读取ep5_v1/attributes的两个manifest。

全零候选6/14/33/38进入core并标no_local_support，第15位仍禁用。core由46增至50，context为26不变，原向量仍74维；69/71/72在两组共享，因此组长度不能简单相加。selection.json同时保存每任务verdict。第20位端点检验：重入源29组中26组固定（0.896552）、目标49组中0组固定；访问控制源30组中27组固定（0.9）、目标56组中0组固定；均为core，第68位仍随组归入core。

use_context及依赖它的细项继续只适用于DATA_DEF_USE；其他数据关系没有对应sink时记不适用，不借另一条边推断上下文。这项诊断澄清没有改变其他73列。

## 用户批准的选择与恢复

1. 同语句循环自依赖：按§3.3明确例外，同一图节点的自依赖在自然循环内记1；其余边严格按§4.7多块可达规则。不同图节点即使在同块，仍为前向可达。
2. 循环头上下文：第20位=1且第59位=0的重入24条、访问控制25条，均通过精确AST核对为最外层for/while循环头。冻结loop.bound只看外层循环，不把循环头自身算入；用户批准保留第20位和其他73位。初次attribute_delta.json的unexplained字段保留历史值，最终解释见loop_context_audit.json与批准记录；这些不是unknown，也没有删除边。
3. 状态初始化callable：首个名字闸门在LogFile状态初始化处失败；冻结L2将state_variable_declaration也视为callable。用户批准按完整AST坐标补齐此接口类型，回归后用新attempt继续。
4. 重复文本end_if：第二次闸门在重入buggy_15.sol的三个end_if停止，原文相同但匿名后对应不同声明。用户批准仅在唯一neg_next父节点具有精确if AST锚点、原文本完全匹配时继承该身份。普通节点仍用冻结node_code_view；其他歧义仍失败。缺失、多重及错误角色父节点均有反例测试。
5. 历史案例摘要：首次topology误用feature_view.graph_fingerprint比较历史store的fingerprint。原图文件SHA本来一致；诊断确认graph_audit.fingerprint及integration.computation_fingerprint均等于历史值。入口改用这两种原算法，feature_view仅用于前后不变性。4项测试通过后用户批准topology_attempt2继续。

前两次匿名失败、首次统计失败、源码快照和日志均保留，批准记录见decisions.json、loop_context_decision.json、anonymous_resume1/2.json及topology_resume1.json。未修改冻结模块、原图、标签或属性选择规则来迎合检查。

## 名字不变性与覆盖

| 任务 | 文件实例 | 实际改名通过 | 原文回退通过 |
| --- | --- | --- | --- |
| 重入节点 | 71 | 30 | 41 |
| 访问控制节点 | 57 | 24 | 33 |

54/128个文件实例实际改名，74个按原匿名器回退为原文。回退只是恒等对照，不是非平凡不变性证据；不能宣称对所有Solidity语法或全量匿名覆盖均已证明名字无关。逐文件回退原因与绑定记录见anonymous_gate_attempt3。

适配器仅按“出现位置→声明→新名”精确翻译L1 symbol/函数/事件、L2状态名及callable、L3锚点和F3 state_vars；没有全局名字替换或近邻行猜测。源码SHA只在内存检查副本更新，extract_source传original_names以保留旧式构造函数判定。未被消费的诊断名字明确保留为历史诊断，不作为匿名连接依据。

沿用冻结anon_parity：匿名内存源码不能复用绑定原磁盘SHA的编译器记录，实际改名只使用未改变的pragma，回退继续使用原记录。先核对原名重算与封存F4/EP5矩阵相同，再比较匿名边集合与属性。比较使用原图节点身份和edge_key，不比较必然改变的AST字节偏移。原名生产输入不变，未写入匿名正式图或训练输入。

## 两跳可达性

使用历史persistent_cases.json的全部21个持续漏报节点，按task/file/source SHA/原图节点ID/类型及图双摘要对齐。计数为生产materialize反射后的有向最短距离1至2跳，排除起点、按节点去重，四种证据总数取并集。

证据固定于原名事实：external.kinds非空的语句/条件、state.writes非空的语句/条件、封存GUARDS来源节点、node_kind为modifier的定义。只计已确认事实，unknown空列表不解释为没有漏洞。历史预测只选择文档指定的诊断案例，不参与边和属性构建。

| 任务 | 文件 / source SHA前12位 | 图节点ID | G3R | G3R-T | G4R | 增加 |
| --- | --- | --- | --- | --- | --- | --- |
| 重入节点 | etherbank.sol / 63d14a7dd1a1 | 15759 | 2 | 2 | 2 | 0 |
| 重入节点 | modifier_reentrancy.sol / 5675bc25a679 | 8498 | 5 | 5 | 7 | 2 |
| 重入节点 | reentrancy_bonus.sol / 628f60b16c87 | 12 | 3 | 3 | 5 | 2 |
| 重入节点 | reentrancy_dao.sol / e507ae792671 | 8315 | 5 | 5 | 5 | 0 |
| 重入节点 | spank_chain_payment.sol / 15724a9aecd2 | 12958 | 95 | 95 | 95 | 0 |
| 重入节点 | spank_chain_payment.sol / 15724a9aecd2 | 12961 | 95 | 95 | 95 | 0 |
| 访问控制节点 | FibonacciBalance.sol / d54dc819f08b | 10581 | 4 | 4 | 4 | 0 |
| 访问控制节点 | FibonacciBalance.sol / d54dc819f08b | 10583 | 2 | 2 | 2 | 0 |
| 访问控制节点 | arbitrary_location_write_simple.sol / bbbdb5367463 | 11472 | 5 | 5 | 5 | 0 |
| 访问控制节点 | mapping_write.sol / a4c6ab0924fe | 12959 | 2 | 2 | 2 | 0 |
| 访问控制节点 | multiowned_vulnerable.sol / ee0df823e630 | 3174 | 3 | 3 | 3 | 0 |
| 访问控制节点 | proxy.sol / 3016dcfca805 | 8854 | 0 | 0 | 0 | 0 |
| 访问控制节点 | rubixi.sol / a4c33aa1b035 | 11356 | 2 | 2 | 2 | 0 |
| 访问控制节点 | rubixi.sol / a4c33aa1b035 | 11357 | 6 | 6 | 6 | 0 |
| 访问控制节点 | simple_suicide.sol / 07ab4f0b502c | 12756 | 1 | 1 | 1 | 0 |
| 访问控制节点 | simple_suicide.sol / 07ab4f0b502c | 12757 | 0 | 0 | 0 | 0 |
| 访问控制节点 | unprotected0.sol / 8cfc8702a1a0 | 10847 | 2 | 2 | 2 | 0 |
| 访问控制节点 | wallet_02_refund_nosub.sol / 3bf849eea5a2 | 11913 | 7 | 7 | 7 | 0 |
| 访问控制节点 | wallet_03_wrong_constructor.sol / 6f5e18f2dbfb | 7893 | 1 | 1 | 1 | 0 |
| 访问控制节点 | wallet_03_wrong_constructor.sol / 6f5e18f2dbfb | 7894 | 6 | 6 | 6 | 0 |
| 访问控制节点 | wallet_04_confused_sign.sol / 5ec3d85c76b1 | 9865 | 6 | 6 | 6 | 0 |

重入2/6个案例增加：modifier_reentrancy.sol节点8498从5到7，新增8501/8504（8501同时是外部调用和守卫）；reentrancy_bonus.sol节点12从3到5，新增外部调用7和状态写6。访问控制0/15增加，其余19个案例不变。存在正增量，因此不触发“所有案例均无增量”的全局标红条件；访问控制无增量仍是限制。

这不是检测收益。G3R与G3R-T的数量相同也不代表关系参数或模型输出相同。逐类别数量、节点集合、距离和完整SHA见topology_attempt2/reachability.json与CSV；不改标签、不删困难案例。

## 反射后边统计

| 任务 | 剖面 | 节点数 | 反射后边数 | canonical关系数 | 关系名数 |
| --- | --- | --- | --- | --- | --- |
| 重入节点 | G3R | 12223 | 47406 | 212 | 16 |
| 重入节点 | G3R-T | 12223 | 47406 | 220 | 24 |
| 重入节点 | G4R | 12223 | 62744 | 274 | 30 |
| 重入节点 | G4R-P | 12223 | 62744 | 274 | 30 |
| 访问控制节点 | G3R | 7892 | 33138 | 225 | 16 |
| 访问控制节点 | G3R-T | 7892 | 33138 | 234 | 24 |
| 访问控制节点 | G4R | 7892 | 43660 | 292 | 30 |
| 访问控制节点 | G4R-P | 7892 | 43660 | 292 | 30 |

完整逐canonical边数、逐关系边数及逐类型入度记录见topology_attempt2/<task>/graph_statistics.json。入度包括平行边和该类型的零入度节点：

| 任务 | 节点类型 | 节点数 | G3R均入度 | G3R-T均入度 | G4R均入度 |
| --- | --- | --- | --- | --- | --- |
| 重入节点 | constructor_definition | 67 | 4.179104 | 4.179104 | 4.223881 |
| 重入节点 | continue_statement | 1 | 2.000000 | 2.000000 | 6.000000 |
| 重入节点 | contract_declaration | 165 | 13.212121 | 13.212121 | 13.212121 |
| 重入节点 | end_if | 1025 | 1.590244 | 1.590244 | 1.590244 |
| 重入节点 | end_loop | 34 | 2.058824 | 2.058824 | 2.058824 |
| 重入节点 | env_source | 187 | 17.112299 | 17.112299 | 17.112299 |
| 重入节点 | expression_statement | 4312 | 3.558442 | 3.558442 | 5.934833 |
| 重入节点 | for | 27 | 7.222222 | 7.222222 | 12.444444 |
| 重入节点 | function_definition | 2124 | 3.950094 | 3.950094 | 4.300847 |
| 重入节点 | if | 1055 | 3.762085 | 3.762085 | 6.396209 |
| 重入节点 | interface_declaration | 20 | 6.300000 | 6.300000 | 6.300000 |
| 重入节点 | library_declaration | 29 | 5.482759 | 5.482759 | 5.482759 |
| 重入节点 | modifier_definition | 56 | 2.535714 | 2.535714 | 5.714286 |
| 重入节点 | new_variable | 2631 | 4.134170 | 4.134170 | 4.431775 |
| 重入节点 | return | 433 | 1.801386 | 1.801386 | 2.665127 |
| 重入节点 | struct_declaration | 50 | 0.500000 | 0.500000 | 0.500000 |
| 重入节点 | while | 7 | 5.285714 | 5.285714 | 17.285714 |
| 访问控制节点 | constructor_definition | 73 | 4.041096 | 4.041096 | 4.082192 |
| 访问控制节点 | continue_statement | 1 | 2.000000 | 2.000000 | 6.000000 |
| 访问控制节点 | contract_declaration | 129 | 16.131783 | 16.131783 | 16.131783 |
| 访问控制节点 | end_if | 180 | 2.827778 | 2.827778 | 2.827778 |
| 访问控制节点 | end_loop | 35 | 2.057143 | 2.057143 | 2.057143 |
| 访问控制节点 | env_source | 182 | 10.703297 | 10.703297 | 10.703297 |
| 访问控制节点 | expression_statement | 3731 | 3.388904 | 3.388904 | 5.267489 |
| 访问控制节点 | for | 26 | 7.538462 | 7.538462 | 12.730769 |
| 访问控制节点 | function_definition | 2048 | 4.747070 | 4.747070 | 5.116211 |
| 访问控制节点 | if | 209 | 4.267943 | 4.267943 | 11.377990 |
| 访问控制节点 | interface_declaration | 20 | 6.300000 | 6.300000 | 6.300000 |
| 访问控制节点 | library_declaration | 28 | 5.357143 | 5.357143 | 5.357143 |
| 访问控制节点 | modifier_definition | 61 | 2.524590 | 2.524590 | 5.721311 |
| 访问控制节点 | new_variable | 702 | 4.984330 | 4.984330 | 5.625356 |
| 访问控制节点 | return | 433 | 1.810624 | 1.810624 | 2.709007 |
| 访问控制节点 | struct_declaration | 25 | 0.240000 | 0.240000 | 0.240000 |
| 访问控制节点 | while | 9 | 6.444444 | 6.444444 | 17.000000 |

逐关系名的反射后边数：

重入节点：

| 关系 | G3R | G3R-T | G4R | G4R-P |
| --- | --- | --- | --- | --- |
| CALL_SITE | 0 | 0 | 570 | 570 |
| DATA_DEF_USE | 3469 | 3469 | 3469 | 3469 |
| ENV_FLOW | 3200 | 3200 | 3200 | 3200 |
| GUARDS | 0 | 0 | 6921 | 6921 |
| MOD_APPLY | 0 | 0 | 178 | 178 |
| READS_STATE | 3070 | 3070 | 3070 | 3070 |
| REV_CALL_SITE | 0 | 0 | 570 | 570 |
| REV_DATA_DEF_USE | 3469 | 3469 | 3469 | 3469 |
| REV_ENV_FLOW | 3200 | 3200 | 3200 | 3200 |
| REV_GUARDS | 0 | 0 | 6921 | 6921 |
| REV_MOD_APPLY | 0 | 0 | 178 | 178 |
| REV_READS_STATE | 3070 | 3070 | 3070 | 3070 |
| REV_WRITES_STATE | 2254 | 2254 | 2254 | 2254 |
| REV_end_if | 0 | 379 | 379 | 379 |
| REV_external_call | 0 | 707 | 707 | 707 |
| REV_first_next_line | 0 | 67 | 67 | 67 |
| REV_internal_call | 0 | 464 | 464 | 464 |
| REV_neg_next | 0 | 1083 | 1083 | 1083 |
| REV_next_line | 0 | 6355 | 6355 | 6355 |
| REV_pos_next | 0 | 408 | 408 | 408 |
| REV_recursive_method_call | 0 | 2247 | 2247 | 2247 |
| WRITES_STATE | 2254 | 2254 | 2254 | 2254 |
| end_if | 758 | 379 | 379 | 379 |
| external_call | 1414 | 707 | 707 | 707 |
| first_next_line | 134 | 67 | 67 | 67 |
| internal_call | 928 | 464 | 464 | 464 |
| neg_next | 2166 | 1083 | 1083 | 1083 |
| next_line | 12710 | 6355 | 6355 | 6355 |
| pos_next | 816 | 408 | 408 | 408 |
| recursive_method_call | 4494 | 2247 | 2247 | 2247 |

访问控制节点：

| 关系 | G3R | G3R-T | G4R | G4R-P |
| --- | --- | --- | --- | --- |
| CALL_SITE | 0 | 0 | 564 | 564 |
| DATA_DEF_USE | 3923 | 3923 | 3923 | 3923 |
| ENV_FLOW | 1948 | 1948 | 1948 | 1948 |
| GUARDS | 0 | 0 | 4502 | 4502 |
| MOD_APPLY | 0 | 0 | 195 | 195 |
| READS_STATE | 1091 | 1091 | 1091 | 1091 |
| REV_CALL_SITE | 0 | 0 | 564 | 564 |
| REV_DATA_DEF_USE | 3923 | 3923 | 3923 | 3923 |
| REV_ENV_FLOW | 1948 | 1948 | 1948 | 1948 |
| REV_GUARDS | 0 | 0 | 4502 | 4502 |
| REV_MOD_APPLY | 0 | 0 | 195 | 195 |
| REV_READS_STATE | 1091 | 1091 | 1091 | 1091 |
| REV_WRITES_STATE | 767 | 767 | 767 | 767 |
| REV_end_if | 0 | 221 | 221 | 221 |
| REV_external_call | 0 | 688 | 688 | 688 |
| REV_first_next_line | 0 | 73 | 73 | 73 |
| REV_internal_call | 0 | 591 | 591 | 591 |
| REV_neg_next | 0 | 239 | 239 | 239 |
| REV_next_line | 0 | 4614 | 4614 | 4614 |
| REV_pos_next | 0 | 232 | 232 | 232 |
| REV_recursive_method_call | 0 | 2182 | 2182 | 2182 |
| WRITES_STATE | 767 | 767 | 767 | 767 |
| end_if | 442 | 221 | 221 | 221 |
| external_call | 1376 | 688 | 688 | 688 |
| first_next_line | 146 | 73 | 73 | 73 |
| internal_call | 1182 | 591 | 591 | 591 |
| neg_next | 478 | 239 | 239 | 239 |
| next_line | 9228 | 4614 | 4614 | 4614 |
| pos_next | 464 | 232 | 232 | 232 |
| recursive_method_call | 4364 | 2182 | 2182 | 2182 |

## 两种安慰剂

固定seed=1729。G4R-P只重连三种E1边，在文件及canonical关系内做双边交换，逐节点入度/出度、文件和源目标类型严格保持，避免自环及重复。固定尝试预算为每组边数×10；有界交换不声称均匀抽样。随机边标为topology-only，不沿用错误的原AST证据。

G4R-Aπ同关系内置换完整74维行（允许跨文件），保留多重集。未来反向边须复制对应已置换正向向量，本轮尚不接入EP6。分别记录位置移动与向量数值变化，不能把二者混为一谈。

| 任务 | E1边 | 最终改变的边 | 零次改接分组/全部 | 属性实际变化行/全部 |
| --- | --- | --- | --- | --- |
| 重入节点 | 7669 | 5805 | 195/487 | 25679/31372 |
| 访问控制节点 | 5261 | 3444 | 184/393 | 16309/21830 |

随机边反射后的canonical边数和逐节点度数均与G4R相同。零次交换的单边/星形等分组全部披露，不声称每条边都改变。全零recursive_method_call属性交换位置后仍为零。完整随机边、映射、分组变化率及NPZ见topology_attempt2。

## 回归和完整性

| 套件 | 通过 | 耗时秒 | 收据 |
| --- | --- | --- | --- |
| EdgeSem | 268 | 499.83 | edge_tests.json |
| NodeSem | 1353 | 26.07 | nodesem_tests.json |
| DFG v2 | 2653 | 163.51 | dfg_tests.json |

三套合计4274项通过。最终独立验收入口为recon/ep5_verify.py，结果为artifacts/ep5_v1/verification.json：检查冻结源码/历史产物、8H只读load、DFG引用、属性差值、全部匿名行、安慰剂及文档原前缀。

另保留两项开发记录：循环多块测试夹具曾漏前向出口边，修正夹具后通过；只读投影诊断首次直接序列化图特征数组失败，部分JSON保留，后续仅导出相关结构字段到projection_diagnostic_details.json。均未变更冻结输入。

实际命令（CUDA_VISIBLE_DEVICES为空，其余环境沿用§4.1；日志SHA均在execution收据）：

| 运行 | exit | 秒 | 命令 |
| --- | --- | --- | --- |
| anon_tests | 0 | 2.88 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest scripts/edge_sem/tests/test_ep5_anon.py -q |
| anon_tests_end_if | 0 | 5.26 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_ep5_anon.py |
| anon_tests_initializer | 0 | 5.04 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest scripts/edge_sem/tests/test_ep5_anon.py -q |
| anonymous_gate | 1 | 12.68 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_anon_run |
| anonymous_gate_attempt2 | 1 | 38.44 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_anon_run --out scripts/edge_sem/artifacts/ep5_v1/anonymous_gate_attempt2 |
| anonymous_gate_attempt3 | 0 | 392.56 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_anon_run --out scripts/edge_sem/artifacts/ep5_v1/anonymous_gate_attempt3 |
| attribute_delta | 0 | 94.95 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_delta |
| attributes | 0 | 129.26 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep5_v1/attributes |
| attrs_tests | 1 | 6.29 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py -q |
| attrs_tests_corrected | 0 | 6.05 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py -q |
| dfg_tests | 0 | 163.51 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests |
| edge_tests | 0 | 499.83 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests |
| loop_context | 0 | 12.64 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_loop_context |
| nodesem_tests | 0 | 26.07 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests |
| placebo_tests | 0 | 0.5 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest scripts/edge_sem/tests/test_placebo.py -q |
| topology | 1 | 72.6 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_topology |
| topology_attempt2 | 0 | 191.11 | /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep5_topology --out scripts/edge_sem/artifacts/ep5_v1/topology_attempt2 |
| topology_identity_tests | 0 | 2.67 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_ep5_topology.py |
| topology_tests | 0 | 3.18 | /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_ep5_topology.py scripts/edge_sem/tests/test_placebo.py |

## 收尾工具故障记录

报告生成脚本首次两次写入均遇到自动审批服务未在期限内返回结果，文件尚未创建；这不是策略明确拒绝。沙箱内直接访问WSL另有E_ACCESSDENIED，正常审批的短WSL命令与临时文件写入/回读/删除已成功。采用分段写入并核对完整源码后继续，未更改审批、沙箱或代理设置；未取得服务端根因证据，不宣称修复了审批服务本身。

## 停止位置

本轮未训练、未用GPU，没有F1或显存收益结论。守卫为既有有界结构事实，改名回退与不可交换分组均是限制。停在EP5，不自动执行EP6或更改训练协议；后续批次授权按对应Prompt处理。

最终实验将在显存充足的服务器另建批次；当前RTX3050 4GiB仅限制本机开发。本轮产物留WSL项目目录，未向C盘另写大型缓存。本地提交，不自动推送GitHub。
