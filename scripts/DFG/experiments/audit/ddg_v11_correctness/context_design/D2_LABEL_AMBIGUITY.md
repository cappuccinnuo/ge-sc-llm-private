# D2 label ambiguity and provenance

## 中文结论与证据边界

本轮在 D1 门槛通过后，审计了 12 个固定案例、480 个来自冻结训练文件的精确重复来源。12 个案例的公共 SolidiFI / SmartBugs 对应源码 SHA 均与实际输入一致；447 个训练重复来源完成了完整函数级精确回映，33 个因多个 pragma 的既有前端限制只保留文件、源码 SHA、原节点 ID、标签和明确原因，不猜测源码位置。

**本次只借助 v1.1 Projector 修复精确源码对应；这里的标签、预测、DDG 入出边与两层影响范围，全部仍来自封存 E0/E1。没有把新 E2 边混入旧 F1 或宣称运行了 E2。**

- 重入 buggy_18 的节点2706：作者标签0；公共 CSV 的[111,116]覆盖原行115；37个精确训练同文本均为正例。这是可复核的标注上下文差异，但不能唯一反推作者转换算法，也不等于已证明作者标错。
- 访问控制 buggy_26 的节点2418/2421：作者标签0，而公共注入范围覆盖；各36个精确训练重复中35个为正例。其 owner_txorigin 参数已经有标量 DDG，不是尚未分析的 owner 状态。
- mapping_write.sol 的 map 实际为 uint256[] 数组；不能因为文件名就按 mapping 处理。其 SmartBugs 标注原行20的数组写，与原行27的 owner 检查是不同节点。
- arbitrary_location_write_simple.sol 的公共标注原行27是无效的无符号长度下界检查，紧邻原行28的长度递减；原行37的 owner 检查不在该标注行。
- AC buggy_18 节点1285为纯算术 mul，已有2条 DDG 入边仍预测错；R buggy_36 节点5961是标量 DDG 真正产生有益消息作用的例子。不能把所有问题归结为缺少状态依赖。
- 某些样例只有 to.call.value(amount) 的调用选项表达式，缺少最后的调用括号；不能未经绑定和执行语义核验就写成“已经执行外部调用”。

当前证据同时支持三类问题：D1 已验证的构图正确性问题、当前范围外的状态/控制/调用语义，以及重复片段的标签上下文歧义；没有证据给三者分配完整因果比例。本轮未更改标签，未完成正式漏洞标注认证，未编译样例，也未重新训练。


Codex, 2026-10-13. No labels changed; no formal annotation certification.

| Case | Author label | Public SHA match | Public location | Train matches / opposite | Review |
|---|---:|---|---|---|---|
| reentrancy_author/buggy_18.sol/2706 | 0 | True | CSV [(111, 116)] | 37 / 37 | C: no automatic correction |
| reentrancy_author/buggy_18.sol/2670 | 1 | True | CSV [(62, 69)] | 8 / 0 | C: no automatic correction |
| reentrancy_author/buggy_18.sol/2675 | 1 | True | CSV [(71, 77)] | 85 / 0 | C: no automatic correction |
| reentrancy_author/buggy_36.sol/5961 | 0 | True | CSV [] | 17 / 0 | C: no automatic correction |
| reentrancy_author/buggy_36.sol/6101 | 0 | True | CSV [] | 1 / 0 | C: no automatic correction |
| reentrancy_author/buggy_27.sol/4672 | 1 | True | CSV [(160, 167)] | 3 / 1 | C: no automatic correction |
| access_control_author/mapping_write.sol/12963 | 0 | True | SmartBugs [20] | 12 / 0 | C: no automatic correction |
| access_control_author/arbitrary_location_write_simple.sol/11479 | 0 | True | SmartBugs [27] | 10 / 0 | C: no automatic correction |
| access_control_author/buggy_18.sol/1285 | 0 | True | CSV [] | 3 / 0 | C: no automatic correction |
| access_control_author/buggy_18.sol/1306 | 1 | True | CSV [(71, 74)] | 232 / 3 | C: no automatic correction |
| access_control_author/buggy_26.sol/2418 | 0 | True | CSV [(103, 105)] | 36 / 35 | C: no automatic correction |
| access_control_author/buggy_26.sol/2421 | 0 | True | CSV [(109, 112)] | 36 / 35 | C: no automatic correction |

## Follow-up evidence

Request author source SHA, annotation records, coordinate map and conversion script for disputed nodes. Preserve overlapping CSV records; overlap alone is not corruption.
Inspect named train file+node matches and full functions. Equal text does not establish equal state, callers, modifiers, storage roots or ground-truth scope.
SmartBugs examples demonstrate a vulnerable contract can contain a correctly labeled negative owner guard. Do not mark all statements positive.
Model error/confidence never suffices to replace a label.
