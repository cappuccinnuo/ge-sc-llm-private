# Stage E 状态位置与语义规范

修改 AI：Codex。2026-10-14。实现目录：scripts/DFG/state/，版本 state-aware-prototype-v1。

本轮在 ge-sc-llm-ddg-v11 工作树实施，仅对重入、访问控制的先导样本审计。分析器不接收漏洞类别、预测或标签，不按文件名设置规则。其他五类不在本轮运行范围。原标量分析、HGT、tokenizer、训练器保持不变。

## 实际接口

- analyzer.analyze_source / analyze_view：源码或已核验 SourceView → 逐函数 StateAnalysisResult。
- locations.LocationTable：源码 SHA、编译单元/文件、合约声明跨度、变量声明跨度 → DeclarationRef / StateLocation。
- access.StateExtractor：复用 CFGBuilder 的 FunctionIR，按原 block/event 身份建立独立 StateFunctionIR。
- reaching_definitions.solve：状态来源的 may-reaching 固定点分析；事件顺序重放；每条事实附无覆盖阻断的 CFG 路径。
- projection.augment_state(base, sources, enabled=True, selected_functions=None)：E2 → 独立 E3a 候选及审计；enabled=False 精确保持 E2 fingerprint。
- model_adapter.reflected_input / build_dgl：保留原基础关系反射和标量 DDG 方向，仅使 STATE_DEF_USE 保持单向。没有更改原加载器，也没有接入原 formal 训练入口。

StateReadEvent / StateWriteEvent 共用不可变 StateEvent 数据结构，通过 kind 区分。Location、Event、未知来源都只用于分析，不增加模型节点。

## 位置身份和键

直接状态标量：bool、address、整型、定长 bytes；不将声明名字等同身份。函数参数或块内局部变量遮蔽状态声明时按原 SymbolTable 解析。声明顺序不影响合约级收集。

简单 mapping：直接根声明，标量键和值。支持有类型且在范围内的常量键；同帧已确认 msg.sender；类型匹配且整函数内未重新赋值的值参数。不同参数名字不证明不同键。

被重新赋值的参数、局部键及复杂键表达式当前使用 UNKNOWN，不用同一静态定义 ID 冒充循环中不变的运行时值。不同常量键可证明 NO_ALIAS；不同根声明 NO_ALIAS；无法证明则 MAY。数组不会被识别成 mapping。

环境来源 msg.sender、tx.origin、block.timestamp、address.balance 等单列 ENVIRONMENT，不伪造状态声明。常量/immutable 状态声明、数组、嵌套 mapping、storage 引用、继承和导入绑定不在当前可完整分析范围。

## 到达定义与调用

- 每个位置以 ENTRY_UNKNOWN 开始，不虚构函数入口的具体状态定义。
- EXACT 单一位置写入对同一抽象位置强覆盖；可能别名的写入做弱更新，保留旧来源。
- 分支 union、循环固定点、不可达代码、return/revert/内建终止沿用原 CFG。
- 复合赋值和自增自减先读取再写入；不增加传递闭包。
- 外部或未知调用使用 HAVOC TOP。TOP 包含无法枚举的可能来源（包括原值未改变的可能），因此抑制调用前具体定义到调用后读取的确定物化，不宣称调用一定改写了状态。
- staticcall 当前也保守 TOP，不代表其允许写状态；精确只读摘要留待后续。
- .call.value(amount); 单独配置调用选项，不作为已发生的外部调用。
- 原 B1 绑定保护仍生效。pragma 范围不能确认内建可用性时不选择一个编译版本。require/assert 无法确认为内建时按未知调用影响保守处理，而不是假定纯函数。
- 操作数求值顺序不确定且含调用影响、条件表达式中的调用、复杂赋值等回退整个状态函数。
- 无 HCG 对应节点的写入仍参与覆盖；只是不物化该端点的边。
- 失败函数不发布临时事件或部分状态边，其他函数和原 HCG/标量 DDG 保留。

## 事实不等于所有路径必然依赖

StateFact.certainty 表示两个访问位置的 alias 判定 EXACT / MAY；即使位置 EXACT，事实仍是 may-reaching，而不是每条路径必执行。cfg_witness 只证明 CFG 上有未被覆盖截断的路径，不求解路径谓词，不宣称实际路径可满足。

本版只物化 EXACT 位置事实。MAY alias facts 留侧表，不能当作错误的 MUST 依赖加入 HGT。完整性与精度分开报告。

## 关系边界

STATE_DEF_USE 是模型候选关系。STATE_ACCESS_ORDER 是同位置下一次访问的侧表，不做全对全传递闭包。EXTERNAL_CALL_BEFORE_STATE_WRITE / UNKNOWN_CALL_BEFORE_STATE_WRITE 是调用到下一次写入的 CFG 顺序证据，不是 Def–Use。上述顺序侧表未加入 HGT。

CONTROL_DEPENDENCE、modifier 执行和跨函数状态摘要本轮没有实现。后写清零不能倒连为前读余额的定义；循环回边产生的真实下一迭代事实则保留 CFG 证据。
