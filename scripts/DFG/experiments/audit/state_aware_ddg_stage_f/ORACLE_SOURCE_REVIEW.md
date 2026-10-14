# Oracle 源码复核

日期：2026-10-14；复核者：Codex。独立人工审阅者：未提供；human_approved=false。
源码、字节跨度和旧预期均来自冻结 ORACLE_EXPECTATIONS.json，未改写旧文件。
自动重查结果：F3_attempt_002/F2_ORACLE_RESULTS.json。
以下为源码静态复核意见，不是编译通过或独立语义认证。

| Oracle | 核对结果与边界 |
|---|---|
| O1 / R buggy_18 withdrawBalance_re_ent33 | 先读余额作 call.value 参数，再在非 revert 后继清零。清零不是此前读取的定义。开放 pragma 上界无精确元数据，revert 绑定仍回退，不能虚构已分析事实。 |
| O2 / R buggy_18 withdrawFunds_re_ent10 | require 读取 mapping，send 参数为标量参数，末尾 -= 包含状态读写；调用后来源未知。开放版本区间导致调用分类保守，只保留未知调用模式，不升级已确认外部调用。 |
| O3 / R buggy_27 transferFrom | _allowed 为嵌套 mapping，from/to 可能相等，还有 SafeMath/内部调用。不能因参数名不同而断言不别名；当前回退有必要。 |
| O4 / AC mapping_write withdraw | owner 是入口读取，guard 后 transfer 不包含 owner 写入；guard→transfer 是待验证控制约束，不能伪造 STATE_DEF_USE。 |
| O5 / AC buggy_18 transferOwnership | onlyOwner modifier 执行约束不可忽略。状态赋值 newOwner 不足以表达权限条件，保持 modifier 回退。 |
| O6 / AC mapping_write set | map 实际是动态数组，含 length 修改和元素写入；不能按文件名当简单 mapping。继续回退。 |
| O7 / R buggy_36 SafeMath.mul | a/b/c 都是标量参数或局部，状态事件应为空；已有标量 E2 不改。require 的宽版本绑定另行保守。 |
| O8 / AC buggy_26 transferTo_txorigin31 | owner_txorigin31 是参数；to.call.value(amount) 未执行最终调用。不可将它当已执行外部调用；继承接口边界仍回退。 |
| O9 / AC arbitrary_location_write_simple PopBonusCode | unsigned length 检查与 -- 是数组/版本相关语义；不支持数组时继续回退，不把后续写入当此前检查的来源。 |

11 个旧合成 Oracle 同样保留源 SHA 重查；新的测试补充 10 类事件次序正反例和继承/版本反例。
新测试中部分同名 builtin 构造仅用于解析器健壮性，未验证其目标版本语言合法性。
20 个重查条目为“观察结果”，没有把自动观察值回填成独立 ground truth。

已静态确认的真实新增顺序例子还包括 buggy_11.sol 的 send 条件后更新状态：
这是 CALL→WRITE 的结构顺序，写入位置可以是 lastPlayer，不应命名为“余额数据依赖”。
F3_EDGE_PROVENANCE 给出具体事件、声明身份、原节点和 CFG witness，可供后续逐条人工复核。
