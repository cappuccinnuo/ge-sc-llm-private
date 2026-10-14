# F2 独立关系规格

日期：2026-10-14；Codex。实现：state/stage_f/relations.py、projection.py。
语义分析只读源码与版本证据，不接收漏洞分类/标签/预测。

| 关系 | 精确定义 | 模型候选 |
|---|---|---|
| STATE_DEF_USE | 函数内某具体写入到读取的 reaching-definition；位置相等证明为 EXACT | 是 |
| STATE_ACCESS_ORDER | 同一 EXACT 状态位置的前一次访问，到 CFG 路径上下一次同位置访问；遇 MAY 别名访问停止此路径 | 是 |
| EXTERNAL_CALL_BEFORE_STATE_WRITE | 已确认外部调用之后，路径上下一次状态写入；不要求此前有读取或同位置 | 是 |
| UNKNOWN_CALL_BEFORE_STATE_WRITE | 调用身份未确定，但可见调用到后续写入顺序 | 仅侧表 |
| READ_CALL_WRITE_SAME_LOCATION | 同一位置的 READ→确认外部CALL→WRITE，途中无可能覆盖该位置的写入或第二次不透明调用 | 仅复合事件侧表 |
| READ_CALL_WRITE_DIFFERENT_LOCATION / MAY_ALIAS | 相应位置不同或可能别名的复合候选 | 仅侧表 |
| READ_OPAQUE_CALL_UNRESOLVED | 读取后遇到无法确认的调用，不能升级为已确认外部调用模式 | 仅侧表 |

STATE_DEF_USE 的 EXACT 是位置/别名精度，不是“所有执行路径必然来源于这一写入”：
RD 在分支上做 union，仍然是可能到达的定义。CFG witness 只证明结构可达，
未求解路径条件，不表示交易一定成功、不证明漏洞可利用。

访问顺序可以跨 HAVOC；证据中保留经过的已确认和未知调用。
这不表示调用前的状态值在调用后保持不变。
调用→写入关系可以指向任意状态位置，因此不能把它解释为“同一余额”的严格模式。
读→调用→写入单独检查位置身份与中间覆盖，不能把未来写入连作此前读取的定义。

一个语句里 READ 与 CALL 可为不同语义事件，但可能映到同一 HCG 节点。
事件内部次序保存在侧表；投影后的自边被计数后过滤，不新增节点或猜邻近行号。
同端点不同 relation 可共存；重复相同 relation 端点合并，保留全部证据索引。

投影之前语义 IR 已完成 RD/GEN/KILL，包括原图没有锚点的写入；
不能为了投影丢失而把这些写入从数据流分析中移除。
未知语义整函数回退，无部分 DDG 残留；其原 E2 子图和样本仍保留。

全部 20 个旧 Oracle 用原 SHA 和 AST 函数身份重查，另外用 10 类顺序正反例测试
同位置、不同位置、MAY alias、互斥分支、终止后不可达、call 配置、参数读取、
未知调用、无调用和 HAVOC。不将测试代码编写者的预期标成独立人工批准。
