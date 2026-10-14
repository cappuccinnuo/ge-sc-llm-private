# D1：DDG v1.1 正确性修复与覆盖恢复验收

修改 AI：Codex；日期：2026-10-13。

## 1. 版本与范围

原工作目录为 `/home/zhao/SmartContract/ge-sc-llm`，实际 HEAD 为 `359a7f13d94fb2c7d8d5d4656d76a94a967e10e4`，不是上一轮执行时的 3fb3fbc。新建 detached worktree `/home/zhao/SmartContract/ge-sc-llm-ddg-v11`，未 checkout/reset 原目录、未提交。原图、标签、token、训练划分、checkpoint、plan/seal 及旧诊断保持原样。

版本名 `ddg-v1.1-correctness-fix`；DDG 包版本 0.1.0→0.1.1。只修改两个核心实现及版本号。E2 是正确性修复版标量 DDG 的简称，不表示本轮已经训练 E2。

## 2. DOT 精确投影修复

原 `projection.code_equal` 用 `ast.literal_eval` 解码源码属性，混淆了 Python 转义和原 pydot 序列化。改为原始文本精确相等，或与实际 `pydot.quote_if_necessary(expected)` 结果精确相等。没有忽略空白、模糊匹配、最近行号或修改原节点 code。

仍检查 AST ID、节点类型、端点、唯一锚点及 raw/compat 映射。未修改 pipeline 的整文件投影回退策略。修复还阻止旧逻辑错误接受 Python hex/Unicode/tab 转义对应的另一份源码。

独立审查发现 pydot 编码并非完全单射：物理换行与字面反斜杠 n 在特定字符串中可冲突。新投影对序列化节点中的物理多行字符串保守拒绝，支持原始精确文本及字符串外的正常多行函数。这一守卫没有造成当前四套数据的旧边或事实丢失。严格序列化一致仍不是作者历史源码 SHA 的证明。

同一新测试文件：修复前 **7 failed / 14 passed**，修复后连同原投影测试 **30 passed**；测试 SHA 前后一致。8 个 cohort/file 真实失败样本全部恢复，验证 1,683 个原普通节点。证据见 `projection/`。

## 3. if/else 注释修复

实际 Tree-sitter 将 then/else 间的 comment 标记为 body。旧代码选取第二个 body 时选中注释，引发整个函数回退。

新增 `_if_bodies`：只在直接子节点层过滤 comment，核验 condition、then、else token、else body 的数量和顺序；额外 body、未知命名节点或不明确结构仍拒绝。不修改 GEN/KILL、RD、循环或终止语义。

原 25 项新测试：修复前 **18 failed / 7 passed**，修复后通过；另加 6 项条件注释测试。测试核验分支 union、重定义 KILL、嵌套/无花括号分支、真实 selfdestruct 参数读取和不可达后继，以及原 HCG 节点、属性、边与 use_ddg=false。

没有执行 solc 编译；真实源码解析/语义样例与故意损坏 AST 的健壮性样例已区分。

## 4. 四套输入的实际恢复量

以下前后值由同一冻结 E0、相同源码 manifest，在原版本和修复版本分别重放得到。修复前重放的每条语义 DDG 边和事实与封存 E1 一致；修复后与其逐条比较。

| 任务 | 支持函数 前→后 | 提取事实 前→后 | 投影事实 前→后 | DDG边 前→后 | 新边 | 新canonical |
|---|---:|---:|---:|---:|---:|---:|
| 重入·合约 | 2034→2035 | 5400→5415 | 4510→4822 | 3363→3561 | 198 | 0 |
| 重入·节点 | 1210→1210 | 2636→2636 | 2083→2380 | 1711→1894 | 183 | 2 |
| 访问控制·合约 | 2127→2128 | 6139→6145 | 5197→5624 | 3765→4032 | 267 | 0 |
| 访问控制·节点 | 1550→1550 | 4101→4101 | 3529→3858 | 2632→2836 | 204 | 1 |

全文件投影失败依次由 **3、3、5、2 → 0**。语义前端文件回退仍为 **6、2、12、2**；这些涉及未支持语义等原限制，没有为提高覆盖率放宽。

注释修复真正恢复的两个函数：
- 重入合约集合 `0x173566176a1deebb47569c8366e84ba7b10b3b8b.sol::calculateTokens`，原行224–251，新增15 facts。
- 访问控制合约集合 `0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol::getCurrentTokenPrice`，原行147–164，新增6 facts。

两者不在本次节点任务的 buggy-file 子集中，因此节点任务提取 facts 和支持函数数不增加。节点任务的增加来自已有事实恢复投影，不能称为扩大了数据流分析范围。

重入节点新增 `(expression_statement, DATA_DEF_USE, if)` 和 `(expression_statement, DATA_DEF_USE, return)`；访问控制节点新增后者。关系名称仍只有 DATA_DEF_USE，但 canonical 三元组变多，将影响未来模型的关系参数量。

## 5. 不变量与影响归因

- 四套 E0 原节点顺序、ID、类型、code、token、标签、源码映射、图属性、CFG/CG 多重边及 key 均完全保留。
- 每条旧 DDG 的端点、canonical 和语义事实保留；删除边为0。
- DDG语义未改变的文件数依次为 **138/142、68/71、108/114、55/57**。
- “语义未改变”不表示新文件字节与旧 E1 相同：新版本号和新增事实引起全局证据索引变化是已记录的元数据变化。
- 每条新增边可追溯到原始 AST span、声明符号、definition/use事件及严格原 HCG ID。
- `after/added_edges_with_evidence.json` 的 cause 是文件级背景；准确的逐事实归因见 `D1_RECOVERY_ATTRIBUTION.json`，不将文件里其他函数的回退原因冒充每条边的原因。
- 原合约/节点任务共享 prepared 输入这一实际条件单独断言；节点图仅诱导原节点名单，未按新分析结果筛选文件或节点。

新增图为 `after/<cohort>/E2_contract.gpickle`、`E2_node.gpickle`。SHA、原输入 manifest、源码与运行代码摘要见 `D1_PROVENANCE.json` 和 `after/summary.json`。不是旧 formal plan 的替代品，不可改写旧 seal 或将旧 checkpoint 冒充新图训练结果。

## 6. 测试与环境处理

第一次全量尝试 372 passed / 18 failed。17 个失败来自旧作用域测试硬编码 worktree 相对语法库，1 个来自拷贝到 worktree 的旧资源报告仍绑定原绝对路径。没有改断言、删除测试或修改旧资源记录。

复制已有 `my-languages.so` 到新 worktree 的原相对位置，SHA相等；没有下载或重新编译。原路径绑定测试在原目录执行，因其测试和 formal 实现逐字节未变；其余在修改版 worktree 执行：
- 修改版 389 passed、1 deselected、31 warnings。
- 被分开的原路径绑定测试 1 passed、4 warnings。
- 合计390个不同测试全部执行。被分开运行不是跳过。
- 随后审计守卫与强化的上下文验证 19 passed；其中10项已在主回归覆盖，另外9项为新检查。因此本轮截至该验收累计399个不同测试通过。
- warning 为 DGL/PyTorch distutils 和 NetworkX gpickle 弃用提示。
- 回归中的合成小图模型测试沿用原项目；没有 Dataset A 拟合或 K折训练。

D1门槛见 `D1_REGRESSION_RESULTS.json`。旧训练归档只读 reporter 验收 complete_tasks=4、pending_tasks=0。最终原资产摘要检查在 D2/D3 与授权文档追加后单独记录，不能将本次版本源码拿去替换原 seal。

## 7. 结论与限制

已修复两项真实正确性问题，恢复了可追溯的标量 DDG 边。原有正确分析结果保留，困难的 buggy_18 等文件不能因此宣称已解决。

边数恢复不是检测能力提升。本轮没有新的F1，也没有证明状态增强或消息融合调整必然有效。D2将继续使用封存标签及预测；D3只交付设计和Oracle。
