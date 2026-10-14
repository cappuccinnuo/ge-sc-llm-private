# Stage F 实施与验收报告

日期：2026-10-14；修改 AI：Codex；版本 state-aware-ddg-stage-f-v1。

本轮在独立工作树实现受限版本/继承绑定、独立状态顺序关系、精确投影与 HGT 兼容性旁路。
没有修改 DDG v1.1 / Stage E 原文件、HGT、tokenizer、标签、折、原训练器及旧实验结果；
只增加 state/stage_f/ 与本审计目录，另外按授权追加两工作树文档。
没有运行优化器、没有新 F1，也没有启动两类或七类完整训练。

## 实际版本与接受结果

保护清单记录本轮实际 HEAD：原工作树916145e4，开发工作树08a4488c。
历史报告的 HEAD 不作为本轮实际代码版本，旧 seal 没有重写。
保护范围13,579项，包含旧smoke资产完整目录；最终以 protected_after.json 的逐项结果为准。

F0_attempt_001 是冻结 Stage E 对完整两类语料的普查。
F1_attempt_002 与 F3_attempt_002 是最终接受结果；旧 attempt_001 原样保留。
完整统计：FINAL_ANALYSIS.json、PROJECTION_BREAKDOWN.json。
所有“支持”只表示完成当前子集分析，不表示实现全部 Solidity。

## 覆盖恢复

| Task | Functions | Stage E supported | Stage F supported | EXACT facts before/after |
|---|---|---|---|---|
| reentrancy_author/contract | 3404 | 1042 | 1316 | 10/17 |
| reentrancy_author/node | 2045 | 670 | 899 | 5/8 |
| access_control_author/contract | 3148 | 939 | 1299 | 12/29 |
| access_control_author/node | 1958 | 691 | 965 | 7/10 |

任务文件来自既有 prepared manifest + paper_kfold 文件清单。
合约任务142+114=256文件路径、254种唯一源码SHA；节点任务71+57是对应合约任务的子集。
各表不能跨任务相加为独立样本。完整函数对比6,552条，无丢失函数。

重入恢复274函数，其中原状态继承拒绝126、原B1继承拒绝79、多pragma69。
访问控制恢复360，其中状态继承268、B1继承2、多pragma90。
没有删除 import/多继承/版本不确定性保护来提高覆盖率。

全语料 Stage E 已有重入10、访问控制12条 EXACT 状态事实；
之前7困难文件的零事实不具有代表性。
语法先写后读候选为441/407函数，但语法共现不保证绑定、可达和无HAVOC。

## 实际候选图增量

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

上表是相对各自固定 E2 的新增模型边，E3b保留E3a全部状态数据边。
合约/节点原节点、ID、顺序、标签、token、源码属性、CFG/CG及标量DDG全部保留；
8图剥除新增关系后指纹等于E2，关闭增强也等于E2。

E3a是函数内状态定义—使用；E3b另加状态访问顺序和已确认外部调用后写入。
UNKNOWN调用关系、同位置READ→CALL→WRITE复合模式只保存在侧表，未伪装成数据边。
HGT两层“新增上下文”指实际适配后的有向图中新增可达节点对，不是性能增益。

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

投影损失主要是原HCG缺少语义锚点与同节点事件合并。
例如重入17条EXACT事实只有6条可投影；另11条缺少端点。
访问控制29条EXACT事实中14条缺端点，15份投影证据按相同端点关系去重为11边。
没有改成最近行号匹配或新增原图节点来凑边。

## Oracle、困难文件与语义结论

旧20项Oracle以原源码SHA/函数身份重查：13子集完成、7回退。
新45项Stage F测试包含10类顺序正反例、版本/继承/假内建、投影不变量、
canonical注册、梯度、checkpoint重载和共同初始化。
独立人工批准0、solc验证0；源码静态复核在ORACLE_SOURCE_REVIEW.md。

原7困难文件仍63/315函数完成，状态EXACT事实仍0；此次覆盖恢复来自其他源码。
R buggy_18仍13/69，存在开放版本上界与继承等回退；只是获得8条可投影访问顺序候选，
不能声称其关键余额调用路径已被状态DDG修好。
R buggy_27有3项同位置READ→CALL→WRITE结构候选，不能直接认定为可利用重入。
AC mapping_write实际为数组；onlyOwner、guard→transfer仍需单独控制语义验证。

完整重入合约语料得到714项同位置READ→CALL→WRITE结构候选，
以及84项不同位置和124项未确认调用模式；这些可能含重复模板，不是独立漏洞数量。
访问控制有254个已确认外部调用事件，却没有当前支持子集中的确认CALL→后续状态写入边。
这说明当前顺序关系对两类语料的信息覆盖不均，不证明权限漏洞无需数据流。

## 复审发现与修复证据

非内建用户函数revert()被解析成revert_statement时，旧状态提取未记录调用HAVOC。
先加回归得到1 failed，再仅在新Stage F适配器修复为NON_BUILTIN追加HAVOC；
真内建终止和参数读取不变。review_regression_before / review_tests_after保留证据。
全语料重跑后本批事实统计不变，但合成反例已修正。旧Stage E源码作为历史对照未覆盖。

第一次F1统计漏列121个前后均文件前端失败的函数，已用F0函数身份补齐。
这是比较分母修正，原图/样本始终保留。最终接受attempt002，首次结果留存。

## HGT与训练边界

真实图已验证增强关系正向canonical及DGL边数。
CPU合成图复用原HGTLayer：STATE_DEF_USE / STATE_ACCESS_ORDER /
EXTERNAL_CALL_BEFORE_STATE_WRITE的relation_msg梯度L1分别为
15.386905、19.373989、3.987084；重载后输出逐元素相同。
这是未训练初始化状态的单次反传，optimizer_steps=0。

语义共同初始化的新旁路仅扩大允许schema，原DATA_DEF_USE情形与旧算法逐张量一致。
没有借用训练好的E0。hidden128/heads8/layers2时，每个新canonical预计增加8208参数；
表中公式不是完整模型实测，不能把参数变化与数据语义效应混为一谈。

RTX3050 4GB资源快照有2913MiB空闲，但未测真实配对模型峰值；
不宣布正式训练ready。旧formal入口仍须迁移forward adapter、schema/初始化版本、
输入checkpoint绑定和显存预检，不能用原命令直接跑本轮候选。

## 测试命令与验收

在mando环境，设置TREE_SITTER_LIB_DIR指向原已有语法库，
PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2。

开发工作树：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/stage_f/tests
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/state scripts/DFG/tests scripts/DFG/experiments/tests tests \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'
```

原绝对资源测试在原工作树：

```bash
cd /home/zhao/SmartContract/ge-sc-llm
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs
```

结果45定向通过；全量480通过/1 deselected，再单独1通过；
合计481个不同测试通过，0失败、0跳过。定向重复不累计。
全量31+原路径4条警告来自已有distutils/NetworkX弃用，未升级依赖。
原路径分开执行是因为该测试绑定原项目实际prepared资产，不是跳过失败。
新的独立verify_delivery核验当前输入/代码SHA、6552函数身份、8图SHA与不变量。
F0/F1/F3耗时以各run.json的monotonic时间为准，不使用WSL回拨的wall clock。

## 对参考模板的调整与下一步

1. 没有先处理更多模型或训练；先以冻结全语料区分需求候选、事实与可投影边。
2. 继承仅支持闭合单链，未扩展C3、导入、跨函数摘要或modifier。
3. 三事件复合模式留作侧表；UNKNOWN调用不进入已确认外部调用关系。
4. E3a/E3b独立候选已经有非零增量，但仍不登记为正式完成训练的模型。
5. Oracle缺独立批准、真实峰值显存未测、正式训练接口未迁移，故本轮停止在候选验收。

建议先针对重入新增顺序边抽查模板重复、分支与状态位置，独立批准Oracle；
访问控制则另行定义guard/modifier→敏感操作的控制依赖正反例。
随后在独立新实验入口完成真实全图前向/反向和绑定预检，再预先固定小折E2/E3a/E3b对照。
不通过调整标签、删除困难文件、换折或修改关系语义来追求更高F1。
