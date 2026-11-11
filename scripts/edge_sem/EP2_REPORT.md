# EP2：修饰器应用与调用站点边构建结果

修改AI：Codex；2026-11-10；分支edge-sem；依据PROMPTS r9，完成§4.4 EP2并停止。

本轮完成受限调用解析修正、两任务全部128个文件实例的MOD_APPLY/CALL_SITE建边和CPU模型接入验收。共生成1507条正向JSONL边；它们是待装配的增量，原F3没有被写回。4183项完整回归通过，尚无检测效果结论。

## 实施文件与批准选择

- 修改 call_resolve.py；新增 build_f4.py。
- 新增 tests/test_call_fix.py、test_build_f4_calls.py、test_build_f4_model.py、fixtures/ep2_calls.sol；只收紧更新 test_call_resolve.py 的 r9 例外断言。
- 新增 recon/ep2_common.py、ep2_call_fix.py、ep2_run.py、ep2_report.py、ep2_verify.py。
- 新增 EP2_REPORT.md 和 artifacts/ep2_v1；只追加三份既有记录文档。

1. r9 已明确要求两项修正：库方法先按“形参个数=实参+1、首参数规范类型=接收者类型”筛选再要求唯一；外层 call_option 只分类 address_builtin/call_option，不制造函数目标。同首参类型仍有多个候选就保留不确定。
2. 用户批准冻结 Projector 仅为 AST 编号、类型、坐标做 label 结构身份核验（call_c43ebd18ece144ba813d112d5caad2d3）。建边规则不使用漏洞标签、预测或 label 语义文本；标识符拼写只用于 AST 声明引用绑定，不按名称推断漏洞。未改 Projector。
3. r9 的预计18个直接修复之外，既有 receiver_type 递归自然恢复4个链式调用。用户批准保留实际22个新增、334/347与13个剩余（call_839a863f2dcb4911bdbeac95e9dcac0a）；没有新增类型推断规则。decisions.json、decisions_chain.json 保存决定。
4. add_edges 返回它自己创建的独立深拷贝；即使误传原图，也先完整校验后只修改副本。调用方必须使用返回值。所有旧节点、顺序、属性及原边key/属性不变；不写新gpickle。
5. MOD_APPLY 延用冻结 GuardAnalyzer 的作用域、继承、参数绑定和单一占位符规则，只表达应用关系，不证明权限保护。CALL_SITE 保留kind；每个语句的嵌套调用按精确AST身份枚举，同语句到同定义只建一条边，但保留每次调用证据。
6. 正式边基于 original 源码/F3；CPU模型等价探针沿用EP1绑定的历史8H特征夹具，不意味着重新启用匿名主实验。config中保存的cuda:0是历史配置，实际执行CUDA_VISIBLE_DEVICES为空、cuda_initialized=false。

## 建边前调用解析验收

两个节点任务都在各自冻结的347个EP0e候选上从312增到334，即96.2536%；各新增22个、剩余13个、候选集外绑定0。重入558/558、访问控制552/552个旧成功调用逐字段保持；修正逐条列表及旧绑定比较存于call_fix/<task>.json。

EP0d两项硬条件仍通过：重入投影257/259=99.2278%、未确定16/259=6.1776%；访问控制266/268=99.2537%、未确定14/268=5.2239%。这是已确认集合的投影覆盖，不是所有真实调用的语义召回。

这是看到EP0e结果后的修正。历史EP0e的312/347=89.9135%及90%门槛“未通过”原样保留，新334/347只作描述，不能据此改写预登记结论。两个call_fix运行成功并写出第0节报告后，才启动真实建边；时间顺序纳入最终核验。

| §0原始调用池unknown原因 | 重入修正前→后 | 访问控制修正前→后 |
|---|---:|---:|
| receiver_or_member_not_confirmed | 104→82 | 74→52 |
| unbound_or_unsupported_identifier | 61→61 | 36→36 |
| unsupported_callee_shape | 353→0 | 4→1 |

重入unknown→address_builtin为351，unknown→call_option为2，unknown→resolved为22；访问控制分别0、3、22。不同任务原始调用类别基数不同，不互相套用计数。

## 两任务建边结果

| 任务 | 文件实例 | MOD_APPLY | CALL_SITE | 合计正向边 | EP0预计MOD/CALL | EP0e CALL候选 |
|---|---:|---:|---:|---:|---|---:|
| reentrancy_node | 71 | 178 | 570 | 748 | 178/180 | 548 |
| access_control_node | 57 | 195 | 564 | 759 | 195/186 | 542 |

| 口径 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| 修饰器唯一解析/应用次数 | 178/187 = 95.1872% | 195/204 = 95.5882% |
| 已解析调用可投影/已解析调用次数 | 578/580 = 99.6552% | 572/574 = 99.6516% |

修饰器中继承绑定分别88、86次；各9次unresolved，原因均modifier_binding；not_unique、not_in_graph、自环与重复均0。按冻结规则识别的旧式constant关键字不当作modifier。

CALL_SITE的已解析调用分别580、574次：各2次无精确图节点、8次与同语句既有目标重复，其余570、564形成唯一边。投影比例仅在已解析调用中计算，不是语义召回。新增边比EP0预测多390、378；比EP0e候选各多22。外部调用、地址内置调用与cast等不需要同文件CALL_SITE，不应统称解析失败。

| 已绑定调用kind（去重前） | 重入节点 | 访问控制节点 |
|---|---:|---:|
| internal | 198 | 208 |
| inherited | 7 | 6 |
| library | 372 | 357 |
| overload_arity | 3 | 3 |

| 调用事件结果 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| address_builtin | 1191 | 560 |
| builtin | 1443 | 1682 |
| call_option | 355 | 340 |
| cast_member | 22 | 20 |
| duplicate | 8 | 8 |
| emitted | 570 | 564 |
| event_or_struct | 11 | 22 |
| external_member | 69 | 31 |
| new_contract | 7 | 3 |
| not_in_graph | 2 | 2 |
| overload_unresolved | 10 | 10 |
| super | 3 | 3 |
| unknown | 139 | 87 |

上述事件表来自语句子树，计数总量为3830/3332；§0原始调用池还含其他AST位置，因此unknown计数不同。完整逐文件原因和每次调用/修饰器的AST锚点见f4_audit.json。

## CPU模型验收

| 任务/fold0 | G3R-T→G4R canonical数 | 新canonical行/层 | G4R参数量 | 构造秒数 | 前后向秒数 |
|---|---|---:|---:|---:|---:|
| reentrancy_node | 220→232 | 12 | 5,275,172 | 23.336 | 4.495 |
| access_control_node | 234→246 | 12 | 5,390,084 | 9.955 | 2.803 |

两任务空E1的G4R与G3R-T在canonical键、端点、全部参数和eval输出逐位相同。加入本轮E1后，通过独立validate_registration；每层12个新canonical行（含显式REV_）按已有relation_seed及锚模型Xavier范围逐位核验，第二次新鲜构造相同。共享的全部非关系参数和旧关系行均与G3R-T逐位一致。

每个任务参数增加98,496。一次CPU前后向采用mean(logits²)，只检查有限值和可微性，不使用监督目标、不调用optimizer，step=0。装配保留冻结的标签完整性核验。构造与计算时间为本机单次记录，不是性能基准或训练耗时。原F3文件SHA与内存图指纹保持。

## 测试、异常和证据

完整CPU回归：EdgeSem 177 passed、NodeSem 1353 passed、DFG v2 2653 passed，共4183项，无跳过。EdgeSem较EP1增加28项，覆盖库重载/调用选项、改名/遮蔽反例、修饰器继承/参数/占位符、语句去重、边篡改拒绝、标签扰动不变性和真实G4R模型闸门。既有依赖弃用警告保留。

三个真实文件的期望先人工核对源码并固定source SHA，再运行构建器：reentrancy_bonus.sol为0条MOD_APPLY与1条withdrawReward调用；rubixi.sol为6条MOD_APPLY与3条CALL_SITE；unprotected0.sol两类均0，不能因为定义了未应用的modifier就补边。

保留三次开发失败及对应源码快照：
- call_fix_tests：新测试相对导入在非package目录收集失败，改为绝对导入。
- call_fix_tests_import：88通过、2失败；旧等价断言把内置now的legacy_type为空误当作不应改变。仅允许r9指定的同名重载在参数个数与规范接收者类型唯一匹配时差异，其他绑定继续严格比较；修正后90通过。
- builder_tests：14通过、3失败；NetworkX MultiDiGraph.get_edge_data第三个位置参数是key，改用default={}关键字。修正后17通过。

日志在execution/，旧实现快照在development/；没有覆盖失败记录，也没有重跑任何正式训练。全部修改完成后才执行三套完整回归，不把这些开发失败写成新增实验。

before.json绑定r9 HEAD 799865ec79f085ab100d009aadd8fed7a9a048f7与PROMPTS SHA 362d1d6462c39adaf16b10aef56f7c78386f76f8dafcce992f0cf04a02436455。开始时ff-only同步已为最新。每任务manifest绑定原F0/F3、plan、store、audit、源码、实现文件及JSONL/Audit SHA；不把文件名相同当作身份相同。

最终ep2_verify.py核对750份冻结源码、354项DFG _code_refs、51份其他EdgeSem源码、321份旧产物、697项输入引用与8H只读load；逐条验证新边端点AST锚点、来源证据及调用审计。将内存副本新增边移除后，整图指纹必须与原图相同。三文档原字节前缀不变，追加内容及新报告通过UTF-8/中文检查。通过收据保存在verification.json；summary.json与两份probes保存计算结果。

## 实际命令

实际执行（mando、CPU；原TREE_SITTER_LIB_DIR、PYTHONDONTWRITEBYTECODE=1、OMP/MKL各2）：

    python -B -m scripts.edge_sem.recon.ep2_common
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_tests_legacy_type -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_call_fix.py scripts/edge_sem/tests/test_call_resolve.py
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_reentrancy_node -- -m scripts.edge_sem.recon.ep2_call_fix --task reentrancy_node
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_access_control_node -- -m scripts.edge_sem.recon.ep2_call_fix --task access_control_node
    python -B -m scripts.edge_sem.recon.ep2_run --name builder_tests_multigraph -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_build_f4_calls.py
    python -B -m scripts.edge_sem.recon.ep2_run --name build_reentrancy_node -- -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/ep2_v1/reentrancy_node
    python -B -m scripts.edge_sem.recon.ep2_run --name build_access_control_node -- -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/ep2_v1/access_control_node
    python -B -m scripts.edge_sem.recon.ep2_run --name edge_tests -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name nodesem_tests -- -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name dfg_tests -- -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name collect_report -- -m scripts.edge_sem.recon.ep2_report
    python -B -m scripts.edge_sem.recon.ep2_run --name doc_check -- -m scripts.node_sem.doc_check --expect-cjk HANDOVER.md:291526 docs/training_changes_2026-10-07.md:1076536 scripts/edge_sem/PROGRESS.md:25964 scripts/edge_sem/EP2_REPORT.md scripts/edge_sem/artifacts/ep2_v1/call_fix/REPORT.md
    python -B -m scripts.edge_sem.recon.ep2_run --name verify -- -m scripts.edge_sem.recon.ep2_verify

首次正式edge_tests还设置EDGESEM_EP2_RECEIPTS为新批次probes绝对路径，成功才排他写入两份收据。日常回归不设置该变量；已有目录和收据拒绝覆盖。命令精确argv、开始时间、退出码、耗时与日志SHA均在execution/，不应照此再次运行覆盖已完成批次。

## 限制与停止位置

仍未实现GUARDS、边属性、EdgeAwareHGT层和正式checkpoint/训练调度；本轮G4R仅有MOD_APPLY/CALL_SITE部分E1。每任务9个modifier绑定失败、10个同参数数重载、3个super以及其他unknown按原规则保留；每任务2个已解析调用缺精确图投影，不做邻近节点补边。MOD_APPLY不能单独证明访问控制，CALL_SITE也不等于完整跨文件或动态调用分析。

最终实验将在显存充足的服务器另建批次；当前RTX3050 4GiB只限制本机开发，本轮没有部署或验收服务器。全部产物留在WSL，未向C盘另写大型缓存。本轮无GPU、无训练、无新权重，停止于EP2；按共享流程本地提交，不自动推送或进入EP3。
