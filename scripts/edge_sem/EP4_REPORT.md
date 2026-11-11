# EP4完成报告（2026-11-10，修改AI：Codex）

按PROMPTS.md r11完成EP4：通用F4构建、74维边属性、两任务端点检验与共同核心位。属性从原名源码、冻结事实和封存L1–L3证据计算；反向边留模型接入时复制正向向量。本轮未训练、未用GPU，没有检测性能或显存结论。旧图、标签、折、特征、初值、checkpoint和计划不改。

## 通用构建与历史一致性

生产build_f4/guard_edges去除recon和EP2/EP0运行依赖；历史比对移至recon/ep4_rebuild.py。新manifest版本edgesem-f4-v1，默认加载拒绝旧版本；历史产物显式只读核验。两个节点任务的新边与EP3逐字节一致，守卫分类和映射计数不变。

| 任务 | MOD_APPLY | CALL_SITE | GUARDS | 守卫记录 | 普通映射 | modifier映射 | unknown目标 |
|---|---|---|---|---|---|---|---|
| access_control_contract | 526 | 1247 | 8098 | 8165 | 6767/6767 | 1398/1398 | 59 |
| access_control_node | 195 | 564 | 4502 | 4537 | 3822/3822 | 715/715 | 12 |
| reentrancy_contract | 547 | 1317 | 10172 | 10274 | 8928/8928 | 1346/1346 | 18 |
| reentrancy_node | 178 | 570 | 6921 | 6956 | 6340/6340 | 616/616 | 12 |


合约任务只验证通用构建入口，不进入本机E-A/E-B。重入合约549个modifier应用去重为547条边；访问控制527个去重为526条。旧EP0访问控制计数528额外遍历了一个fallback_receive_definition，正式MOD_APPLY固定仅针对function_definition/constructor_definition。文件0x0d689d1d3ef39e379329d9fc88eabceccc1215a0.sol，源码SHA ac6e70721c9d4ff51c6c6653195b62892672321253cf38883bd5d4d771bb82de，fallback偏移3383，modifier跨度3409–3418。未扩展规则迎合旧计数；守卫记录10274/8165均与EP0一致，映射缺失为0。证据见development/contract_scope.py及execution/contract_scope.log。

## 属性产物和端点筛选

| 任务 | 属性行 | 全零行 | 全零比例 | 含缺项/未知诊断行 |
|---|---|---|---|---|
| access_control_node | 21830 | 2728 | 12.497% | 9530 |
| reentrancy_node | 31372 | 2786 | 8.881% | 14562 |


有效目录：scripts/edge_sem/artifacts/ep4_v1/attributes_attempt3。每任务有attrs.npz、manifest/seal、stats.json、diagnostics.json、fact_provenance.json和endpoint_test.json；共同layout/selection封存74维布局和共同筛选。uint8二值矩阵通过文件、端点、关系及多重边序号精确对齐；来源SHA、行序及numeric_digest均核验。

核心46维：[0, 1, 2, 5, 7, 8, 9, 10, 11, 12, 13, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 34, 35, 36, 37, 39, 40, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 68, 69, 71, 72]。

上下文26维：[3, 4, 16, 18, 30, 41, 42, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 69, 70, 71, 72, 73]；unknown位可同时属于两组。

两任务都全零而未纳入核心的候选：[6, 14, 33, 38]；第15位始终停用。

| 核心位 | 名称 | 共同决定 |
|---|---|---|
| 0 | ctrl_src_dominates_dst | undetermined |
| 1 | ctrl_dst_postdominates_src | undetermined |
| 2 | ctrl_branch_contains_ext_call | undetermined |
| 5 | var_kind_return_var | undetermined |
| 7 | value_shape_mapping | core |
| 8 | value_shape_array | core |
| 9 | value_shape_address | core |
| 10 | value_shape_integer | core |
| 11 | value_shape_bool | undetermined |
| 12 | value_shape_bytes_string | core |
| 13 | value_shape_struct_contract | core |
| 17 | def_kind_compound | undetermined |
| 19 | def_kind_incdec_or_delete | core |
| 20 | def_loop_carried | core |
| 21 | use_path_crosses_ext_call | core |
| 22 | use_context_condition | core |
| 23 | use_context_call | core |
| 24 | use_context_arithmetic | undetermined |
| 25 | use_context_state_write_value | core |
| 26 | use_context_return | core |
| 27 | arith_op_additive | undetermined |
| 28 | arith_op_multiplicative | undetermined |
| 29 | arith_op_exponent | undetermined |
| 31 | write_access_indexed | core |
| 32 | write_access_member | undetermined |
| 34 | write_op_assign | core |
| 35 | write_op_increase | undetermined |
| 36 | write_op_decrease | undetermined |
| 37 | call_low_level | undetermined |
| 39 | call_sends_value | undetermined |
| 40 | call_return_checked | undetermined |
| 43 | guard_kind_require | core |
| 44 | guard_kind_if_branch | core |
| 45 | guard_kind_early_exit | core |
| 46 | guard_kind_loop_cond | core |
| 47 | guard_kind_modifier | core |
| 48 | guard_kind_internal_check | undetermined |
| 49 | guard_operands_caller_identity | core |
| 50 | guard_operands_block_time | core |
| 51 | guard_operands_amount_balance | core |
| 52 | guard_operands_external_result | core |
| 53 | guard_operands_hash | core |
| 68 | unk_cfg | unknown位随限定字段归组 |
| 69 | unk_dfg | unknown位随限定字段归组 |
| 71 | unk_state | unknown位随限定字段归组 |
| 72 | unk_guard | unknown位随限定字段归组 |


门槛固定：同关系同侧至少2条边且至少一条为1才算合格；汇总合格数≥30且恒定比例≥99%时移入上下文。任一任务判为端点便移出共同核心；两侧不足30则保留并标未判定。未判定不等于已证明是独立边信息。unknown位随限定字段归组，不参与端点检验。筛选不使用标签或模型分数。

需要保留的实质局限：共同核心里有17个已知属性位仍是样本量不足的未判定项；它们按预登记规则保留，不作为新增独立信息已获证实。READS_STATE/ENV_FLOW等关系的use_context没有精确dfg.to来源，全0不表示没有上下文；end_if和部分控制边缺少可映射的语义CFG端点，unk_cfg比例高。后续解释与规则基线须读取相应unknown/缺口记录，本轮不扩展冻结事实来填补。

## 每关系每组非零比例

### access_control_node

| 关系 | 边数 | 全零 | control | var_kind | value_shape | def_kind | data_path | use_context | arith_op | write_access | write_op | call | guard_kind | guard_operands | context | env_kind | unknown | library |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CALL_SITE | 564 | 2.660% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 26.950% | 0.000% | 0.000% | 69.504% | 0.000% | 11.879% | 62.057% |
| DATA_DEF_USE | 3923 | 0.000% | 0.000% | 100.000% | 98.929% | 98.751% | 33.520% | 12.388% | 0.357% | 0.000% | 0.000% | 0.688% | 0.000% | 0.000% | 96.227% | 0.000% | 3.135% | 0.000% |
| ENV_FLOW | 1948 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.846% | 85.010% | 4.825% | 0.000% |
| GUARDS | 4502 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 57.774% | 88.627% | 0.000% | 20.347% | 0.000% |
| MOD_APPLY | 195 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.487% | 85.641% | 100.000% | 0.000% | 0.000% | 0.000% |
| READS_STATE | 1091 | 0.000% | 0.000% | 0.000% | 92.851% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 98.350% | 0.000% | 24.198% | 0.000% |
| WRITES_STATE | 767 | 0.000% | 0.000% | 0.000% | 89.570% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 98.044% | 0.000% | 0.000% | 0.000% | 84.355% | 0.000% | 22.034% | 0.000% |
| end_if | 221 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 31.674% | 0.000% | 100.000% | 0.000% |
| external_call | 688 | 68.023% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 5.523% | 0.000% | 0.000% | 29.797% | 0.000% | 0.000% | 0.000% |
| first_next_line | 73 | 0.000% | 1.370% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 93.151% | 0.000% | 98.630% | 0.000% |
| internal_call | 591 | 10.660% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 48.223% | 0.000% | 0.000% | 69.036% | 0.000% | 0.000% | 0.000% |
| neg_next | 239 | 0.000% | 26.360% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 34.728% | 0.000% | 74.895% | 0.000% |
| next_line | 4614 | 0.000% | 83.875% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 87.169% | 0.000% | 16.558% | 0.000% |
| pos_next | 232 | 0.000% | 81.897% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 85.776% | 0.000% | 28.017% | 0.000% |
| recursive_method_call | 2182 | 100.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% |


| 关系 | unk_cfg | unk_dfg | unk_order | unk_state | unk_guard |
|---|---|---|---|---|---|
| CALL_SITE | 0 / 0.000% | 0 / 0.000% | 67 / 11.879% | 0 / 0.000% | 0 / 0.000% |
| DATA_DEF_USE | 0 / 0.000% | 93 / 2.371% | 54 / 1.376% | 0 / 0.000% | 0 / 0.000% |
| ENV_FLOW | 0 / 0.000% | 92 / 4.723% | 54 / 2.772% | 0 / 0.000% | 8 / 0.411% |
| GUARDS | 0 / 0.000% | 0 / 0.000% | 916 / 20.347% | 0 / 0.000% | 2 / 0.044% |
| MOD_APPLY | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| READS_STATE | 0 / 0.000% | 250 / 22.915% | 166 / 15.215% | 9 / 0.825% | 12 / 1.100% |
| WRITES_STATE | 0 / 0.000% | 169 / 22.034% | 132 / 17.210% | 0 / 0.000% | 0 / 0.000% |
| end_if | 221 / 100.000% | 0 / 0.000% | 56 / 25.339% | 0 / 0.000% | 0 / 0.000% |
| external_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| first_next_line | 72 / 98.630% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| internal_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| neg_next | 177 / 74.059% | 0 / 0.000% | 64 / 26.778% | 0 / 0.000% | 0 / 0.000% |
| next_line | 744 / 16.125% | 0 / 0.000% | 370 / 8.019% | 0 / 0.000% | 12 / 0.260% |
| pos_next | 53 / 22.845% | 0 / 0.000% | 65 / 28.017% | 0 / 0.000% | 1 / 0.431% |
| recursive_method_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |


来源缺口：{"no_exact_dfg_to_for_this_edge": 6550, "target_dfg_inapplicable_var_kind_from_sealed_symbol": 22}。

### reentrancy_node

| 关系 | 边数 | 全零 | control | var_kind | value_shape | def_kind | data_path | use_context | arith_op | write_access | write_op | call | guard_kind | guard_operands | context | env_kind | unknown | library |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CALL_SITE | 570 | 2.456% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 27.895% | 0.000% | 0.000% | 72.632% | 0.000% | 9.825% | 63.860% |
| DATA_DEF_USE | 3469 | 0.000% | 0.000% | 100.000% | 98.789% | 98.645% | 50.649% | 31.450% | 0.922% | 0.000% | 0.000% | 6.486% | 0.000% | 0.000% | 95.734% | 0.000% | 3.488% | 0.000% |
| ENV_FLOW | 3200 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.906% | 93.562% | 2.594% | 0.000% |
| GUARDS | 6921 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 64.153% | 93.484% | 0.000% | 10.779% | 0.000% |
| MOD_APPLY | 178 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.438% | 84.831% | 100.000% | 0.000% | 0.000% | 0.000% |
| READS_STATE | 3070 | 0.000% | 0.000% | 0.000% | 96.059% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.414% | 0.000% | 8.404% | 0.000% |
| WRITES_STATE | 2254 | 0.000% | 0.000% | 0.000% | 95.031% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 98.846% | 0.000% | 0.000% | 0.000% | 94.676% | 0.000% | 7.542% | 0.000% |
| end_if | 379 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 63.325% | 0.000% | 100.000% | 0.000% |
| external_call | 707 | 66.195% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 12.588% | 0.000% | 0.000% | 31.683% | 0.000% | 0.000% | 0.000% |
| first_next_line | 67 | 0.000% | 1.493% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 2.985% | 0.000% | 98.507% | 0.000% |
| internal_call | 464 | 12.284% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 45.690% | 0.000% | 0.000% | 63.793% | 0.000% | 0.000% | 0.000% |
| neg_next | 1083 | 0.000% | 6.094% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 83.657% | 0.000% | 94.090% | 0.000% |
| next_line | 6355 | 0.000% | 78.993% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 80.661% | 0.000% | 21.353% | 0.000% |
| pos_next | 408 | 0.000% | 92.647% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 94.118% | 0.000% | 12.990% | 0.000% |
| recursive_method_call | 2247 | 100.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% |


| 关系 | unk_cfg | unk_dfg | unk_order | unk_state | unk_guard |
|---|---|---|---|---|---|
| CALL_SITE | 0 / 0.000% | 0 / 0.000% | 56 / 9.825% | 0 / 0.000% | 0 / 0.000% |
| DATA_DEF_USE | 0 / 0.000% | 91 / 2.623% | 54 / 1.557% | 0 / 0.000% | 0 / 0.000% |
| ENV_FLOW | 0 / 0.000% | 80 / 2.500% | 46 / 1.438% | 0 / 0.000% | 8 / 0.250% |
| GUARDS | 0 / 0.000% | 0 / 0.000% | 746 / 10.779% | 0 / 0.000% | 2 / 0.029% |
| MOD_APPLY | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| READS_STATE | 0 / 0.000% | 244 / 7.948% | 114 / 3.713% | 9 / 0.293% | 12 / 0.391% |
| WRITES_STATE | 0 / 0.000% | 169 / 7.498% | 96 / 4.259% | 0 / 0.000% | 0 / 0.000% |
| end_if | 379 / 100.000% | 0 / 0.000% | 39 / 10.290% | 0 / 0.000% | 0 / 0.000% |
| external_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| first_next_line | 66 / 98.507% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| internal_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| neg_next | 1017 / 93.906% | 0 / 0.000% | 44 / 4.063% | 0 / 0.000% | 0 / 0.000% |
| next_line | 1335 / 21.007% | 0 / 0.000% | 308 / 4.847% | 0 / 0.000% | 12 / 0.189% |
| pos_next | 41 / 10.049% | 0 / 0.000% | 53 / 12.990% | 0 / 0.000% | 1 / 0.245% |
| recursive_method_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |


来源缺口：{"no_exact_dfg_to_for_this_edge": 10195, "target_dfg_inapplicable_var_kind_from_sealed_symbol": 22}。

stats.json另保存每位在原作者正/负目标节点入边中的比例。正负按node_info_vulnerabilities原规则（None为0，非None为1，env排除），不是L-audit；只在属性、筛选与seal完成后读取，不参与特征、样本、阈值或核心位决定。

## 已批准调整与边界

1. call_3ed2f55f68424011a5631df0cab83e86：同一数据边可能承载多个变量。var_kind/value_shape按全部证据取并为多热，仍74维，不拆边、不任选一个变量；其他单热组不变。
2. 同一批准：use_context仅从当前src/dst精确匹配的dfg.to取sink。READS_STATE/ENV_FLOW的源缺少该字段，WRITES_STATE及参数入口等可能无匹配，置0并记录source_gaps；不发明上下文。相应call/arith位仍受已知use_context限制。
3. call_ce3526a147bb49c0bb210e8a9c1349a6：五个unk位未覆盖全部未知来源；函数汇总、返回值处理、版本区间等未知置0，并逐边记录unknown_fields原因，不加维或借用其他unk含义；这些0不证明已确认不存在。
4. call_52397237416e41b3baa8612deb0ad2b4：首次因int原节点ID与str环境ID排序失败，改用保留类型和顺序的事实行数组计算摘要。旧attributes目录、失败日志和旧源码保留，批准后新建attributes_attempt2；没有生成NPZ，也没有训练。
5. call_fa5c42293d4747daa5a6ad5932843d4d：第二次发现两任务各22条依赖指向for头i++，冻结NodeSem将raw update_expression归other，dfg整组为空；仅此时从已精确核验的封存L1 symbol取var_kind并记录来源，非空facts不一致仍失败。未改NodeSem、DFG、图或事实，批准后新建attributes_attempt3。44条证据保存在development/dfg_target_diagnosis.json。
6. MOD_APPLY通过调用F取得守卫并按inner_anchor落入M过滤；空函数体仍有效，只加锁modifier无守卫时为0且不是unknown。GUARDS所有evidence取并，每任务12个unknown目标保留。
7. 冻结loop_cond操作数为空，49–54仍0；x=x+1记assign，其他未列写操作保持0；env14个保留键只映射表中四类。recursive_method_call全零。语义CFG或类型缺口按unk及sidecar记录，不宣称完整程序语义。

## 验证与失败保留

- edge_tests_final：238 passed, 4 warnings in 464.95s (0:07:44)；exit 0。

- nodesem_tests：1353 passed, 4 warnings in 28.66s；exit 0。

- dfg_tests：2653 passed, 9 warnings in 192.39s (0:03:12)；exit 0。

- attrs_target_complete：34 passed, 4 warnings in 4.19s；exit 0。

定向测试覆盖74维、多证据类型、循环/调用路径、call返回检查、modifier独立来源、守卫操作数、unknown、端点门槛、快速改名、标签扰动不变、错误source/layout/图/数组拒绝、混合ID摘要及空dfg来源。
开发失败日志也保留：选择器误命中函数全文；参数入口没有dfg.to；tuple调用选择器需完整前缀；全零unknown测试必须提供正例才能测试继承；新循环测试的旧夹具没建raw update节点，补真实节点角色后通过。诊断脚本直接按路径启动缺包导入，改为-m入口。上述未改变冻结分析器，也不是训练或seed重复。
最终ep4_verify重新核对冻结源码、旧产物、8H只读load、DFG_code_refs、原图指纹/节点/原边、EP3边字节、属性行序与摘要、守卫并集、library和unknown位、端点筛选与统计重算。三文档原字节前缀保持，UTF-8/中文检查通过后提交；机器收据为artifacts/ep4_v1/verification.json。

## 文件与实际命令

生产代码：io.py、attrs.py、attr_sources.py、attr_batch.py、attr_stats.py及build_f4/guard_edges最小解耦；tests/test_f4_generic.py、test_attrs.py、test_attr_store.py与ep4_attributes.sol；recon/ep4_*为基线、只读历史比较、记录器、报告与核验。
生产入口为python -B -m scripts.edge_sem.attr_batch --out <新的目录>。write_attributes(task_id,out_dir)同样完成两个任务共同筛选，再返回指定任务manifest。所有目录拒绝覆盖。以下为实际运行命令，包含失败和诊断；不可原路径重复执行覆盖现场。

- attr_loader_boundary（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attr_store.py

- attributes_build（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes

- attributes_build_attempt2（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes_attempt2

- attributes_build_attempt3（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes_attempt3

- attrs_storage_identity_fix（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_target_complete（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_target_facts_fix（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_unit_complete（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_exact_selectors（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_final（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_initial（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_source_corrected（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- build_access_control_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task access_control_contract --out scripts/edge_sem/artifacts/f4_v1/access_control_contract

- build_access_control_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/f4_v1/access_control_node

- build_reentrancy_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task reentrancy_contract --out scripts/edge_sem/artifacts/f4_v1/reentrancy_contract

- build_reentrancy_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/f4_v1/reentrancy_node

- contract_scope（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.contract_scope

- dfg_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests

- diagnose_dfg_target（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B scripts/edge_sem/artifacts/ep4_v1/development/diagnose_dfg_target.py

- diagnose_dfg_target_module（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.diagnose_dfg_target

- diagnose_initial（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.diagnose_initial

- edge_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests

- edge_tests_final（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests

- generic_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_f4_generic.py scripts/edge_sem/tests/test_build_f4_guards.py scripts/edge_sem/tests/test_build_f4_calls.py

- nodesem_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests

- verify_access_control_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task access_control_contract

- verify_access_control_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task access_control_node

- verify_reentrancy_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task reentrancy_contract

- verify_reentrancy_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task reentrancy_node

## 后续与停止位置

EP4完成属性准备，不证明检测提升。EP5真实全量改名/可达性闸门、EP6边感知层与EP7以后计划/训练尚未执行；快速fixture改名测试不能替代EP5。
D1匿名主视图、D2 P2协议、D3七类冻结仍须训练前确认，原名属性计算或历史夹具不构成授权。最终实验将在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机开发限制；本轮未部署服务器、未更改训练配置。产物留WSL，未向C盘另写大型缓存。按共享流程本地提交，停在EP4，不自动push。
