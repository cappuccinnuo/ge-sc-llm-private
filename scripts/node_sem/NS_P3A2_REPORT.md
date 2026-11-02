# NS-P3a2 验收报告

日期：2026-11-02。实现与核验：Codex。输入分支 node-sem，起点 a2792968；方案 PROMPTS r10，前置实现 bed6223f。

本轮完成状态未知精确化、析取发送者守卫、逐字段未知掩码、完整 AST 汇总与名字无关性验证。生产只用 original；没有训练、GPU、特征编码或 NS-P3b。模型效果不在本轮验收范围。

## 1. 根因与修改

原 facts.py::_bind_layers 将任一 L2 unresolved/fallback 诊断扩散到整个函数。冻结 L2 的 state_name_missing 同时包含 require/assert/哈希函数/now 等非状态名字，导致同函数中已确认状态写甚至普通算术也被误标未知。旧 K/L/M 又依赖已投影节点，缺失 emit 等事件会连带污染汇总。

- facts_state.py：按原 AST 位置、语法角色判断诊断；仅排除可确认的内置/类型/裸被调名，成员调用的未知接收者仍未知；缺少位置时只读重跑冻结 StateBinder/StateAccessExtractor，未恢复者保守未知。别名只影响相关声明与使用；scalar 重名诊断不被误作 storage 别名。保留旧行 unresolved 计数，独立保存精确诊断分类。
- facts_summary.py：K 读取全部封存 L2 证据，包括未投影访问，按声明/函数身份去重计数；L/M 的 AST 字段覆盖未投影 emit、revert、fallback 等。写入不确定只影响有关写入/保护/顺序字段；其余字段保留已知事实。
- facts_guards.py、facts_boolean.py：有效析取的每个分支都必须限制发送者；负极性按 De Morgan 处理。添加 disjunctive。混入普通布尔条件、非相等比较或不可靠表达式时不伪造发送者守卫。
- facts_schema.py：事实版本 nodesem-statement-facts-v1.1，K/L/M 增加 unknown_fields。组 status 是概览，后续编码必须按字段掩码，不能把整组清空或把未知当 false。
- facts_ast.py：仅为 fixture 名字无关性测试提供原拼写还原映射，用于既定的“函数与合约名字仅大小写不同”位。生产仍拒绝 anonymous。
- facts_revision_audit.py：按 row_key/顺序逐字段比较，拒绝非允许变更。状态读写的变量、形状、数量及原调用、环境、算术、语法、DFG 事实严格不变，授权位允许重新回填。

没有修改冻结 DFG、HGT、tokenizer、图、标签、折、8H 计划或结果。统计摘要恢复的是已有源码/封存证据表达能力，没有生成新的 DDG 边。

## 2. 已批准的具体调整

1. 用户批准 K/L/M 加 unknown_fields：旧 schema 只有整组 status，不能表达“仅受影响汇总位未知”。
2. 用户批准比较清单补入 order.status 与诊断变化；原要求正文包含这些修复，但原允许差异清单漏列。旧 state_* 行诊断计数仍逐项验证保留。
3. 用户批准受限布尔条件适配：真实冻结 grammar 把第二个 msg.sender 的成员后缀跨布尔运算符挂接。新适配只读原 AST token、括号和运算优先级，保留原声明身份；不改 grammar、源码或图，不按文本猜测变量绑定。

原名政策沿用用户明确指示与 EXPERIMENT_POLICY.md；未重启匿名实验，也未运行真实语料改名检查。测试夹具的双射仅用于证明事实不依赖名称。

## 3. 四任务结果

| 任务/图行数 | state未知：旧→新/分母 | K未知：旧→新/分母 | L未知：旧→新/分母 | M未知：旧→新/分母 |
| --- | --- | --- | --- | --- |
| 重入合约/18610 | 6627 -> 78 / 10067 | 2299 -> 410 / 2369 | 2951 -> 68 / 3981 | 503 -> 13 / 543 |
| 重入节点/12223 | 4350 -> 32 / 6635 | 1767 -> 299 / 1788 | 1764 -> 29 / 2247 | 204 -> 8 / 214 |
| 访问控制合约/13693 | 5947 -> 75 / 7858 | 851 -> 139 / 922 | 2981 -> 65 / 3723 | 437 -> 15 / 474 |
| 访问控制节点/7892 | 3774 -> 29 / 4664 | 401 -> 86 / 403 | 1857 -> 26 / 2182 | 172 -> 8 / 177 |


以上分母与旧 NS-P3a 保持相同：state/order 为适用语句节点，K/L/M 分别为声明/函数/合约节点；guard 未知仍按全部图行。新增字段本身会造成行变化，变化行数不能理解为修复了同样数量的错误事实。

| 任务 | 析取守卫记录 | 新增授权声明节点 | 变化行 |
| --- | --- | --- | --- |
| 重入合约 | 14 | 2 | 14923 |
| 重入节点 | 14 | 2 | 9620 |
| 访问控制合约 | 23 | 4 | 11763 |
| 访问控制节点 | 16 | 4 | 6910 |


52,418 行全部对齐，变化 43,216 行，非允许变化为 0。K 的 shape/public/constant/initializer、M 的 kind 亦严格不变。原每行 state_* 诊断计数保留；精确诊断按原因另存 precision_summary.json，诊断出现次数与唯一未知节点数分开解释。

重入 reentrancy_bonus.sol 有 8 行状态支持恢复的具体前后证据，含源码 SHA 与 row_key，见 precision_summary.json 的 examples。这不是改变漏洞标注，也不是检测结果或 F1 提升。

剩余状态不确定包括声明歧义、真正无法绑定的取值、storage 别名、未投影状态效应及 assembly；没有为了降低 unknown 比例删除样本或将未知默认安全。

## 4. 测试与完整性

最终 NodeSem 587 passed / 0 failed / 0 skipped；DFG v2 2653 passed；原回归 223 passed。合计 3463 passed，42 条既有依赖弃用警告（4+9+29），环境未升级。

44 个手写 Oracle（包含新增 ii–nn）逐一做确定性名字双射比较；另对 6 个新 Oracle 做带封存 L1/L2 的名字字段、定义使用和状态访问一致性测试。按双射还原名字载体后逐项相同；provenance 中源码 SHA 随源码变化，单独核验而非当成语义事实。夹具仅经 parser 验证，本轮没有执行 Solidity 编译。

另五类固定 50 个原名源码、2098 个函数单元、8016 行：0 异常、0 解析失败。它们没有完整图证据，不能称五类模型实验或完整数据流验收。

facts_verify 对 accepted_attempt3 通过：四任务原名 text_v1 行身份/顺序/源码 SHA、图与证据引用、当前生产代码摘要通过；22,813 个冻结文件字节不变；8H execution.load 与生效 runtime_resume_v2 完全一致。旧 accepted_attempt2 的 36 个文件额外逐一核对 SHA，全部不变。

初始定向检查出现三个旧测试预期/fixture 差异：未投影写的 K 计数从 zero 改为 one，同时继续要求 write_functions 在 unknown_fields；另两个 guard fixture 补齐新 disjunctive 字段。新测试初次收集还遇到 namespace package 的相对导入错误，已改绝对导入。最终回归通过，未删除测试或放宽身份断言。记录在 artifacts/ns_p3a2/decisions.json。

抽取约 201.235 秒、五类冒烟 17.813 秒、逐行比较 10.450 秒、facts_verify 39.26 秒。均为本机 CPU 墙钟，不是训练时间。

## 5. 产物与复现

当前接受目录：scripts/node_sem/artifacts/facts_v1/accepted_attempt3/。
CURRENT.json 只在测试、比较及核验通过后更新；accepted_attempt2 与更早目录只读保留，标记 superseded，不覆盖。

关键记录：original/*/{facts.jsonl,audit.json,manifest.json,manifest.seal.json}、stats.json、revision_comparison.json、precision_summary.json、cross_category_smoke.json、runtime_closure.json、final_validation.json、verification.seal.json。执行命令/日志/批准选择/历史 SHA 在 artifacts/ns_p3a2/。

mando 环境，设置 CUDA_VISIBLE_DEVICES=''、PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.node_sem.facts_acceptance tasks --out NEW_OUTPUT
python -B -m scripts.node_sem.facts_acceptance smoke --out NEW_OUTPUT
python -B -m scripts.node_sem.facts_revision_audit --old scripts/node_sem/artifacts/facts_v1/accepted_attempt2 --new NEW_OUTPUT --out NEW_OUTPUT/revision_comparison.json
python -B -m scripts.node_sem.facts_verify --out NEW_OUTPUT
```

已封存目录拒绝覆盖；重新运行使用新目录。三份记录只追加并通过 doc_check --expect-cjk。完成本地 NS-P3a2 提交，不自动推送或推进 NS-P3b。

## 6. 仍然存在的边界

这是受限语义提取与正确性修复，不是完整 Solidity 类型/别名/跨函数分析；读写列表仍只消费原有投影证据，完整 AST 汇总与节点证据的覆盖范围不同。unknown_fields 消费规则必须在 NS-P3b 编码时落实。析取适配不推广为任意布尔定理证明器。

本轮没有训练和新 F1，不能据此声称漏洞检测改善。后续仍使用原名数据与匹配的原名 S0 基线，不能复用匿名 8H 得分冒充受控基线。

最终实验按用户安排在显存充足的服务器执行；当前 RTX3050 4GiB 仅为本机开发限制，服务器尚未在本轮部署或实测。
