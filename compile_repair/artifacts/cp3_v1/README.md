# CP3 已授权资料获取检查点：SOChecker 输入集合差异

2026-11-17（EST），修改 AI：Codex。当前状态：stopped_on_structure_mismatch。本批次是 CP3 的部分进展，不是 CP3 完成验收；生产代码未修改，非测试生产文件仍为 14。

用户已批准：“批准全部资料，仅本地研究使用（推荐）”。授权先写入 authorization.json，再执行下载；来源、完整提交、路径、费用上限和原话均已记录。原请求为已提交的 cp3_preflight_v1/authorization_request.json（SHA256 1862b4aa6deafca0267ef168b4b358738f4d1635fcc983fc5bc2925a09433808）。本批次继承 88b499e714883066b3bc1379f42a5a89ce8ba1d6，不重做或覆盖此前产物。

## 已完成

- 官方 Solidity 文档 10 份、188,817 字节；全部通过大小、Git blob SHA1 和 SHA256 验证。见 document_manifest.json、document_acquisition_status.json。
- DAppSCAN 固定提交指定目录：21,495 文件、109,776,516 字节，其中 21,457 个 .sol。
- SOChecker 固定提交 evaluation/RQ1/*.json：4 文件、3,762,624 字节。
- Trace 固定提交 datasets：8,112 文件、122,296,616 字节，其中 8,107 个 .sol。
- 三语料合计 29,611 文件、235,835,756 字节。每个文件的路径、Git blob 身份、大小与 SHA256 见 acquisition/<语料>/manifest.jsonl.gz；三个获取收据均 passed=true，内容保存在仓库外 corpora/，不提交原语料。
- 初始分类表先于语料内容统计建立：taxonomy.json 的 29 个类别和 125 个 breaking-change 条目（0.5:59、0.6:23、0.7:22、0.8:21）；文档逐条覆盖校验见 breaking_change_coverage。SHA256 7096c70be45debbbd671919674ee2afd63dc59e3bf08c969ed977353299832bb。这仍是待诊断探针与逐类测试验证的初表，空 verified_versions 不代表已实测。
- 三文件夹具同时含相对导入、子目录和 @vendor/ remapping；0.4.12、0.4.24、0.5.17、0.8.38 共 4/4 solc rc0，production Slither 构造与 D3(a/b) 成功，节点文件名覆盖全部三文件。见 project_probe_acceptance.json、project_probe_invocations.jsonl。此探针不代表 project.py 已实现。

## 停止原因与具体待确认方案

structure_acceptance.json 的 DAppSCAN 四项比较（summary、pragma_minor_of_first_version、import_kinds_top、projects）全部与 cr_pre_v2 相同；608 项目、473 含导入、405 存静态未解析导入、38,122 相对可找到、1,094 相对缺失。Trace 的 5,000 / 83 项目与 3,092 文件 / 15 全部相同。

SOChecker 的 ours.json、gpt-3.5-turbo.json、gpt-4.json 均为 897 条，input 按顺序、集合和重数完全一致，历史 contract/function 子串计数均为 656。ours+GPT.json 为 846 条、同口径 621 条；它严格包含于 ours.json，缺少 51 条，没有额外 input，也没有重复 input。差异 SHA256 清单见 structure_review_request.json；未贴源码、未合并、未去重。

获批请求 after_approval 明确写了“内容核验计数不符……保留现场并停止”，PROMPTS §4.5.1 要求不一致时报告。因此暂停后续 CP3 实施。具体建议：保留原定 ours.json 的 897 条作为唯一 SOChecker 分类输入，将 ours+GPT.json 记录为 846 条的附属子集，仅作来源核对；用户接受这一核验差异后按原 CP3 继续。该建议待确认，当前下载授权仍有效，无须重新授权相同资料。

## 已运行与未运行的边界

旧测试、doc_check 和冻结审计由本批次 run_checks.py、verify_checkpoint.py 记录；最终收据为 test_acceptance.json、doc_check_v2_invocation.json、frozen_audit.json。开发问题与处理见 development_issues.json。交付清单和封存为 delivery_inventory.json、evidence_seal.json，强制记录见 CHANGE_LOG §30、HANDOVER 新追加段及 CP3_REPORT 的续节。

未实现生产分类器、项目闭包、Solidity 片段判定；未做语料编译、逐类失败统计、0.6/0.7 诊断格式探针、tuple-call 改写夹具复核、重复定义/许可/pragma 与 codegen 前提探针、CP4 最终算子验收。初表中的修复候选均是后续判定，未运行修复或调用 LLM。未安装、升级、下载新编译器/库、切换全局 solc、训练或 push；费用 0 美元。

续做须先处理 structure_review_request.json 的待确认项，使用新的执行批次，不覆盖本批次或旧产物；既有 taxonomy 初表及资料可只读复用，按证据追加校验结果。


本轮终审补记（Codex）：production 622/6、mando 181/447、DFG 2653 passed/9既有warnings；六份doc_check v1通过，补记后以v2收据为准。冻结审计确认28,779个保护跟踪文件、25,828个旧封存文件、354个引用、96个编译器、两套环境及14个生产文件不变；29,611份语料文件和10份文档哈希保持。SOChecker差异仍待确认，CP3未完成，仅本地检查点提交。收据数字解析的转义错误已在development_issues记录并从既有日志纠正，无测试重跑。
