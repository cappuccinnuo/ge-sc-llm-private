# CP2.1 开发、验收与停止记录（2026-11-14，修改 AI：Codex）

执行 PROMPTS r2.9 §4.4b，起始 compile-repair@1ed79a6708f505ecb9aa80b157a43f9e07608c9f。用户原话“同意 D20”的授权在 authorization.json，先于实现和运行保存；baseline.json 记录修改前源/代码/环境身份。生产仅修改 toolchain/slither.py 的 graph_facts，非测试文件保持 14 个，新增 18 个条件边测试。

两轮 production 各 843 成功/3 已知失败、843 图字节一致，只有 40 文件 86 个 IF 边标记按审查更正。6c 在第 227 份 reentrancy/buggy_44.sol 停止：223 精确同、3 差异文件符合 D20、1 个 reference_only 键失败，12 未运行；降序未运行。四个差异文件各在一个新进程连续取 10 次，合并 main 为 11 次；没有更多采样。完整事实、全部波动键和唯一失败键见 ../../CP2_REPORT.md 的 CP2.1。

| 文件 | 用途 |
|---|---|
| authorization、baseline、evidence_seal | 授权、修改前身份、14 个实际生产文件指纹 |
| run_corpus、ascending1/2_plan/acceptance/receipt/invocation | 复用 CLI 的完整参数与逐份严格验收；descending 分支未执行 |
| run_replay、replay_invocation、d20_rule_checks | 原顺序 main 与固定新进程 10 样本；规则边界检查 |
| run_checks、pytest_*、test_evidence_* | 完整模块与 DFG 测试、日志及测试生成产物 |
| audit_replay、captured_replay_audit | 只读复算现存原始提取，不执行编译/Slither；审计通过而 criterion_passed=false |
| summarize、cp2_1_summary | 实测状态、类别、成功选版与图数量；未运行明确标记 |
| package_store、*_archive_audit | 三个新正式批次的无损归档及逐成员回读 |
| audit_frozen、frozen_audit | 保护旧产物、环境、代码、历史文档和 occurrence 键 |
| check_docs、doc_check_v* | 9 份文档检查，追加文档使用原字节偏移 |
| delivery_inventory、delivery_seal | 最终精确交付路径与字节身份 |

主运行 227 次、追加 40 次提取，波动键 9 个（L1 DEF；5 继承、4 非继承），唯一失败为声明上下文 MultiHashWrapper 的 out DEF：参考重数 1，但 11 次全 0。观察不能定位内部根因。没有通过改键、顺序、设置、seed/GC 或追加样本寻找通过结果。

测试：production 585 passed/6 skipped，mando 147/444，冻结 DFG 2653 passed/9 既有 warnings；D20 边界 12 通过。全部测试及实际命令、环境、耗时、rc 在对应 receipt 中；日志以原字节 gzip 交付，本地原日志保留。正式 store.tar.gz 分别在 ../cr_store_mando_v3、../cr_store_mando_v4、../cp2_6c_v2，旧批次不修改。

整体 CP2.1 未通过；本轮完成生产修复并按门槛封存停止现场，等待独立审查。CP3、剩余 replay、降序均未执行；无安装、下载、LLM、训练或 push。当前脚本输出目录拒绝覆盖，不可直接重跑；任何续验应先确定范围并使用新批次。交接与训练改变记录见 ../../docs/HANDOVER.md、CHANGE_LOG.md §21、DECISIONS.md。
