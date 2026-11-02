# NS-P3a3 实施与验收报告

修改 AI：Codex。输入分支 node-sem，HEAD 9c78d0e8；按 PROMPTS.md r11 的 NS-P3a3 执行，前置实现 e2d7e195。使用 original 原名视图，不读取匿名特征或模型评分。新事实位于 artifacts/facts_v1/accepted_attempt4/；CURRENT 已在验收通过后切换，旧 attempt3 的 23 份文件字节保持不变。

## 1. 完成内容

- 合取、析取与前缀取反统一按原 AST token 和括号分组，保留声明身份。修复正极性合取漏识别；未改变 grammar、源码或 DFG。直接比较的发送者与出现在 mapping 下标中的发送者分开，后者不能仅因包含 msg.sender 而被认定为发送者守卫。
- throw 作为语言关键字排除状态名字不确定。四任务分别纠正 10/10/32/8 条诊断和对应语句支持状态，原始 L2 诊断仍保留。
- K/L/M 使用三值汇总：确定 true 的存在性字段保持已知；read/write_functions 达到 many 后保持已知；已证实普通函数写入时 only_constructor_writes 是已知 false；可能继续增加的精确计数仍未知。status==unknown 当且仅当 unknown_fields 非空；未分析默认记录先明确掩码，不能虚构 supported。
- K 的不确定只作用于声明身份 targets：未解析标识符匹配同作用域同名状态声明；未知 storage alias 限定潜在引用类型；已确认的整数、地址、bool、固定 bytes 和合约/枚举值类型排除。未知用户类型保守保留为潜在引用，不因无法解析而宣称无影响。同文件继承收集仅用于潜在不确定目标，不用于选择重载、重写或产生新绑定事实。
- assembly 只按 AST 的 yul_evm_builtin 识别指定 storage 操作：sstore/delegatecall/callcode 记写不确定，sload 记读不确定；只有 extcodesize 等操作时不产生状态问题。CFG 本身不支持 assembly 时，其顺序事实仍未知。
- semantic CFG 支配树补入 entry→entry，原 networkx 2.6.3 和模拟缺少根条目的返回值产生完全相同结果。未安装或升级 NetworkX；不把模拟兼容测试称为在新版本环境完成实测。

## 2. 已征求用户并批准的调整

1. 模板“合取只保留发送者相等组合”与“未误解析条件完全一致”冲突。例如 (x==p)&&ready、!(x!=p)、(now==deadline)&&ready 原本分别有 state_param/time_state_param。用户批准保留能够证明的全部既有相等组合，发送者位仍只由发送者比较决定，析取仍要求每条可通过分支限制发送者。
2. 模板误解析判据只检查 member_expression.object 为 binary_expression，漏掉数组 base 跨越布尔运算。真实 buggy_21 的 msg.sender==feeAddress && tokendetails[tokenAddress].status==false 就属于这种情况。用户批准补充判据；原判据的四个任务各 1 条差异、完整源码 SHA、AST 和前后值均保留，未隐藏为零。

其他必要接入：K 支持状态的 Oracle 检查放到封存 L2 图测试，纯源码测试不假称有证据；既有三条“已有确定写入却仍掩码 state_write”的测试按本阶段三值规则更新，增加 true 已知与 auth_write 仍未知断言。uu 用嵌套同名 storage alias 触发冻结绑定器实际的不支持情形，未改绑定器。新夹具全部标记 parser_only_not_compiled。

## 3. 四任务逐行结果

| task / rows | state unknown | K unknown | L unknown | M unknown |
| --- | --- | --- | --- | --- |
| reentrancy_contract / 18610 | 78 -> 68 / 10067 (0.77% -> 0.68%) | 410 -> 105 / 2369 (17.31% -> 4.43%) | 68 -> 52 / 3981 (1.71% -> 1.31%) | 13 -> 13 / 543 (2.39% -> 2.39%) |
| reentrancy_node / 12223 | 32 -> 22 / 6635 (0.48% -> 0.33%) | 299 -> 85 / 1788 (16.72% -> 4.75%) | 29 -> 18 / 2247 (1.29% -> 0.80%) | 8 -> 8 / 214 (3.74% -> 3.74%) |
| access_control_contract / 13693 | 75 -> 43 / 7858 (0.95% -> 0.55%) | 139 -> 33 / 922 (15.08% -> 3.58%) | 65 -> 52 / 3723 (1.75% -> 1.40%) | 15 -> 15 / 474 (3.16% -> 3.16%) |
| access_control_node / 7892 | 29 -> 21 / 4664 (0.62% -> 0.45%) | 86 -> 15 / 403 (21.34% -> 3.72%) | 26 -> 18 / 2182 (1.19% -> 0.82%) | 8 -> 8 / 177 (4.52% -> 4.52%) |

四任务共 52,418 行；依次 538/413/278/171 行变化，合计 1,400 个任务内行实例。节点身份、顺序、读写变量/形状/数量、调用、环境、算术、语法、DFG、图和标签全部保持原样；非允许差异为 0。严格比较器为 ns-p3a3 单独限制 K/L/M 可变字段，旧 ns-p3a2 比较规则仍可复现。

| task | guard | throw direct rows | three_value | target_scope |
| --- | ---: | ---: | ---: | ---: |
| reentrancy_contract | 21 | 10 | 97 | 210 |
| reentrancy_node | 21 | 10 | 85 | 133 |
| access_control_contract | 21 | 32 | 26 | 43 |
| access_control_node | 21 | 8 | 13 | 36 |

上述各列不是互斥消融：guard 是实际旧新字段差异；throw 是直接恢复的语句支持行，不包含间接 K 效果；three_value 是当前精确作用域下被三值规则解除的字段掩码；target_scope 是使用相同当前事实和三值规则，将旧宽作用域与新 targets 比较的字段变化。一个节点可出现在多列，不能相加声称独立修复数量，也不能解释为模型效果。详细 row_key 和字段列表在 precision_summary.json 与各任务 audit.json。

## 4. changeOwner 的具体证据

buggy_2 和 buggy_3 中 assert(msg.sender==owner && msg.sender!=newOwner) 后的 owner=newOwner：
旧 is_sender_guard=false、eq_pairs=[]；新为 true、[env_state]、disjunctive=false。owner 原本已因其他守卫被识别为授权变量，本轮修正的是该写入的保护判定；K 的 unguarded_write_functions 从 2→1，unguarded_writer 仍为 true，因为仍有另一个确定的未保护写入函数。未改漏洞标签。

| cohort | source | SHA256 | write row_key | declaration row_key |
| --- | --- | --- | --- | --- |
| reentrancy | buggy_2.sol | b6401bf3a4be6e2ce35cb53091fc04a306a57983e8b7e24488d619be13c27f9f | 5134 | 5042 |
| reentrancy | buggy_3.sol | 9eaa874f037cc6ee0f642d250d199a4722d3f8265e1654d9a33565a1237ca21a | 3515 | 3415 |
| access_control | buggy_2.sol | 2e1677e0a51e74bc0bcbc21bd83dfb29625521c56d2c8e1568cbbf10ed1f2bc3 | 3277 | 3212 |
| access_control | buggy_3.sol | b5b60378a837403ab39cdfd51c276a4312225acf42f73cbda52f5f4d06449f3a | 2336 | 2267 |

上表同类合约/节点任务使用同一原始源码但属于不同任务；不将重叠当独立样本。每个断言/函数/写入/声明节点的完整前后字段都在 precision_summary.json，按 task、源码 SHA 与 row_key 定位。

## 5. 条件一致性、测试和完整性

| population | well-grouped conditions | differences | original-heuristic differences |
| --- | ---: | ---: | ---: |
| oracle | 27 | 0 | 0 |
| reentrancy_contract | 4203 | 0 | 1 |
| reentrancy_node | 3195 | 0 | 1 |
| access_control_contract | 2926 | 0 | 1 |
| access_control_node | 1963 | 0 | 1 |

一致性比较器从 SHA 固定的旧 facts_boolean/facts_guards 源码加载独立参考实现，没有 monkeypatch 冻结模块或重绑定字节码。枚举全部 Oracle、四任务中的 require/assert、if 与循环条件；else/early-exit 加负极性。修复数组判据前的原始失败结果与实现中查出的 mapping 下标反例均保留；最终正确分组条件差异为 0。

| suite | passed | failed/errors | skipped | warnings | seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| node_sem | 650 | 0 | 0 | 4 | 10.942 |
| dfg_v2 | 2653 | 0 | 0 | 9 | 166.812 |
| original | 223 | 0 | 0 | 29 | 3.699 |

新增 8 个 Oracle oo–vv，总数 52；图证据测试、名字双射、未知真值表、同名继承/引用类型/assembly、缺根支配树、严格差异拒绝等通过。首轮定向测试为 20 失败、6 通过，最终修复后通过；初期旧测试预期冲突和一致性失败也保存，未删除关键断言。

另外五类固定各 10 文件、合计 50 文件、2,098 个函数单元、8,016 行纯源码冒烟：0 解析失败、0 异常。它只验证通用提取运行，不等于五类完整图特征/模型实验或 Solidity 编译验证。

facts_verify 对四份 manifest、封存输入、原名文本行身份/顺序、源码 SHA、全部实现引用和 schema 通过；8H execution.load 与已批准 runtime_resume_v2 一致，22,813 个冻结文件字节不变。旧 attempt3 全部 23 文件额外 SHA 核对通过。原图没有被重新生成或重标。

## 6. 文件与命令

核心修改：facts_boolean、facts_guards、facts_state、facts_summary、facts_cfg、facts_schema；facts.py 只增加汇总诊断接入，facts_revision_audit 增加阶段限定；新 facts_consistency 是只读验收工具。测试、8 份 Oracle、旧实现参考、失败与通过收据、修正选择记录均在 scripts/node_sem 下。

mando / CPU，沿用 TREE_SITTER_LIB_DIR、PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、CUDA_VISIBLE_DEVICES=''：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.node_sem.facts_consistency --out <新路径>/boolean_consistency.json
python -B -m scripts.node_sem.facts_acceptance tasks --out <新目录>
python -B -m scripts.node_sem.facts_acceptance smoke --out <新目录>
python -B -m scripts.node_sem.facts_revision_audit --revision ns-p3a3 --old scripts/node_sem/artifacts/facts_v1/accepted_attempt3 --new <新目录> --out <新路径>/revision_comparison.json
python -B -m scripts.node_sem.facts_verify --out <新目录>
```

实际本轮目的地为 accepted_attempt4，已经封存，不应再次写入。reporting.py 保存本轮逐行影响与困难文件报告的重建方式，执行记录在 artifacts/ns_p3a3/。首次用冻结 create-only write 更新 CURRENT 被拒绝；旧文件未受损，随后仅将允许更新的 CURRENT 原子替换，原因记录在 current_switch.json。三份记录按旧格式只追加，编码用 Python UTF-8 与 ASCII 转义写入，并运行 doc_check --expect-cjk。

## 7. 限制与停止

这不是完整 Solidity 绑定/别名/跨函数分析，未知字段仍需后续 NS-P3b 按字段消费；存在已知位不等于整组完整。CFG、状态解析和节点投影的支持范围不同，不把 unknown 当作安全或没有漏洞。没有训练、GPU、向量编码、编译器验证或新的 F1。

最终实验按用户安排在显存充足的服务器执行；当前 RTX3050 4 GiB 只是本机开发限制，本轮未部署服务器。所有新产物在 WSL 项目内，没有向 C 盘写大模型或重复训练日志。完成本地 NS-P3a3 提交后停止，不自动推送、不推进 NS-P3b。
