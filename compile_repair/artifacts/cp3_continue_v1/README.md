# CP3 续做证据（修改 AI：Codex）

本批次起点为 compile-repair 分支 dc6c5fb44041e1023daef1bfd7d9760f534c7f0a，依据 PROMPTS r2.13 §4.1、§4.5。旧 cp3_preflight_v1、cp3_v1、cp3_delivery_v1 和 CP0–CP2.4 产物保持只读。当前 CP3 尚未完成，最后状态以本文件后续补记与 CP3_REPORT 为准。

## 授权与范围

- authorization.json 记录用户接受 SOChecker 来源差异的原话：“同意，继续使用原定 897 条（推荐）”。ours.json 仍是唯一输入，不合并附属 846 条子集。
- project_identity_authorization.json 记录：“批准项目图使用文件名 + key5（推荐）”。项目图新增相对文件名作为原 key5 的外层身份，节点、CFG 边与调用均保留文件上下文，原单文件与 6c 输出不变。
- alias_binding_review_request.json 尚待决定：原生 Slither 将不同文件中的同名合约类型错绑；建议新增项目图接受检查。该项未被前一项文件身份授权覆盖，当前没有实施。

本轮没有下载、安装、升级、全局 solc 切换、LLM 调用、HGT 训练或 GPU 锁操作。费用 0 美元。外部语料源码、工作副本、原始 stderr 与批量图留在仓库外 compile-repair-local/cp3_continue_v1，不纳入 Git。

## 已有实现与证据

toolchain/solc.py 增加 combined-json stderr 分类、约束细分和 Slither 工具限制分类。toolchain/project.py 增加只读传递导入闭包、缺失导入与同项目文件名候选计数、工作副本、匹配 solc/Slither 参数。pipeline.py 共用既有选版及设置循环，按闭包文件分别记录 provenance。toolchain/slither.py 支持项目完整 D3 和获批文件身份。cli.py 支持目录及显式 remapping，survey.py 判定片段语言，evaluation/report.py 按单元计数。生产模块为 16 个，目录与分层受 test_layering 约束，上限仍为 30。

taxonomy_verified.json 保留初表的 29 类和 125 条 breaking changes，并补充 30 个实测模板、92 个版本的格式证据。diagnostic_probe_acceptance.json 对应 548 次 combined-json、84 次仅诊断用途 standard JSON 和 6 组 tuple-call 前提组合。格式边界为 0.6.0；相同 SPDX 重复在 0.8.8 起被拒绝，重复相同 Solidity pragma 在 92 版均通过。上述版本结论只覆盖实际手写形态，不能泛化到所有重复内容。

codegen_probe_summary.json 对应 12 次 compiler 和 2 次 Slither 调用。此 Stack too deep 夹具在 0.8.38 的 via-ir + optimizer 下通过 D3；只请求 AST 在所测旧系列仍失败，0.8.38 的 AST 输出成功但当前原生构造调用未建立可用 Slither AST-only 路径。未增加编译设置重试，也未实现自定义 AST 适配器。

unit_inventory_summary.json 核验 29,611 份取得文件；编译单元原始清单为 31,307 条，其中 SOChecker 236 条无 Solidity 声明证据而单列，31,071 条进入运行序列。DAppSCAN 是既有口径的 608 个项目根，不能把更深一层的 682 个子目录误作项目数。语言判定是词法证据规则，保留不完整函数/声明，不能保证消除所有与 JavaScript 等语言共有语法的歧义。

## 发现的问题与暂停

project_identity_probe.json 证明原 key5 在两个合法导入的 C.f() 上冲突；用户已批准文件外层身份，相关实现与测试已通过。随后新增的跨文件调用测试发现进一步问题：alias_call_probe.json 中 solc AST 的参数 a、b 分别引用 A.sol 的 id 37 和 B.sol 的 id 48；原生 Slither 却把两个类型和调用目标均指向 A.sol。solc rc0 与原 D3(a/b) 均通过，故这是现有接受判据覆盖不到的工具限制，不能靠文件名序列化修正。

全量序列首段 120 个已正常封存；后段完成 752 个后受控中断，另有 cp3_30208 留下 9 条已记录调用。interrupted_segment_preservation.json 对 200,545,035 字节现场建立哈希清单，不伪造正常结束 seal，也不把未完成单元计入最终结果。corpus_stop_request.json 与对应 receipt 记录 SIGINT 的精确目标及 rc=-2。上述 872 个完整单元是部分证据，不是抽样最终验收或全量成功率。

待确认方案仅增加项目 AST/Slither 合约类型绑定一致性检查；保留原 D3 事实，错绑或无法验证时作为工具限制拒绝可用图输出，不改合法源码和已安装包。没有自动重试。若批准，先测试新判据，再在新批次处理受影响项目及中断/未运行单元；旧证据只读保留。

## 测试与记录状态

- tests_targeted_v2.log：110 passed。
- pytest_production_v4.log：714 passed、6 skipped，69.246 秒（驱动耗时）。
- pytest_mando_v1.log：268 passed、452 skipped，22.342 秒。
- pytest_dfg_v1.log：2,653 passed、9 既有 warnings，164.070 秒。
- pytest_project_acceptance_v1.log：24 passed、1 failed；失败是上述实际调用目标错绑，仍保留，未改为通过或跳过。

开发中修正了类型错误消息中的 expected type 被泛化为 parser 错误的匹配范围；导入路径改为 UTF-8 解码，无法支持的转义明确记录。旧搬迁测试的 14 文件假设更新为 16 文件并比较实际封存清单；旧 pragma 等价测试只新增五个明确不支持的 CP3 负向夹具清单，846 份旧输入与所有可读夹具仍逐字段比较。首次定向测试把手写 Missing 基类误写作 Absent，修正测试引用后通过。每次失败日志保留，没有把失败收据改写。

强制文档、doc_check 和最终冻结核验将在交付前完成。当前新增接受检查待批准，调用目标测试未通过，因此尚不满足 PROMPTS “全部通过后提交”的条件，未提交本批次，也未 push。


交付检查补记（2026-11-17，修改 AI：Codex）：六份 doc_check_v1 全部通过；frozen_audit 检查28,908份保护跟踪文件、25,828份旧封存文件、354项code refs、96份编译器文件、production/mando的145/118份环境元数据、29,611份语料和10份文档，均未变化。生产文件16个，历史文档字节段保留。tracked git diff --check通过，新增代码/文档无空白问题；仅322份逐一列明且SHA固定的原始工具输出保留其原空白，见whitespace_review，不豁免代码或验收项。本条追加后的最终doc_check收据为doc_check_final_invocation.json。上述记录和范围检查不代表新增绑定测试通过；24passed/1failed与待确认状态保持，本批次未提交、未push。


测量边界补记（修改 AI：Codex）：另有三次交互式诊断检查和一次初始项目 smoke check 未保留完整逐调用耗时/输出哈希；exploratory_observations.json 明确以 null 标示缺项，不混入正式548/84诊断矩阵及前提验收计数。development_issues.json登记了全部实质问题与解决或停止方法。新增绑定检查仍待确认，失败测试状态未变。
