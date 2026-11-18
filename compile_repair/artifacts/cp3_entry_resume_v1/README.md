# CP3 获准探针续跑与允许路径问题

修改 AI：Codex；2026-11-18（America/New_York）。起点compile-repair/8900abe8，本批次只读保存旧批次，authorization记录用户“允许修正脚本并续跑一次（推荐）”。

一次续跑的八项测试未改：普通入口四版本通过，首个连字符0.4.12失败后-x停止，余下三版本未运行。失败消息为File outside of allowed directories，导入文件真实存在于物化工作根内。证据见entry_probes_v2.json/stdout和probes_v2下compiled.json；4passed/1failed/27deselected，耗时4.440440秒，语料重验0项。

执行前仅修正收据glob重复收集pytest current符号链接，原字节脚本和执行副本都保存；pre_execution_review给出差异和SHA。此差异只影响证据收集，未改八项测试、版本和判据，未额外重试。生产代码、测试和夹具本轮均未改。

只读核对31,071份旧result.json及其SHA后，发现92项/521次同类目录拒绝，79后来成功、13未修复；涉及0.4.12–0.4.17。1,473条诊断路径全部存在且在各自工作根内，此数不是独立文件数。详细证据在allowed_paths_existing_evidence和allowed_paths_source_verification。

## 待确认的具体方案

proposed_project_allowed_paths.diff仅建议project.py两处--allow-paths改为解析后的项目根绝对路径，solc和Slither同步，物理目录范围不变。原./入口、源字节、候选和设置政策、D3及绑定门槛不改，补丁尚未应用。

建议保留当前八项探针和失败夹具，再加普通嵌套入口/兄弟导入四版本检查；12项全通过后，仅重验与原11项不重叠的92项并集，共103项。旧成功79项也可能因更早候选恢复而改选版本，因此纳入清单。新结果另建汇总，旧31,071项和所有现场不覆盖。绝对路径在四版本上能否解决问题仍待实测，不预先宣称通过。

完整请求和精确单元列表在allowed_paths_review_request.json，SHA256 141e6bc425aee16c4c2198d2881f3d5b1187cff1667b00d74bf32fc72a08d43d。需批准是因为PROMPTS §4.5第2节规定参数不兼容时记录并停下报告，且§4.1禁止自动重试；原授权只允许入口前缀和11项语料重验。

## 当前交付

CP3尚未完成，本轮未运行完整production/mando/DFG回归、任何语料重验或新最终统计。记录位于CHANGE_LOG §34、HANDOVER、DECISIONS、PROGRESS、CP3_REPORT；保护与doc_check结果后补。0美元，无安装、下载、LLM、HGT、GPU锁或全局solc改动，本地停止检查点，不自动push。


2026-11-18 停止检查点核验补记（修改 AI：Codex）：doc_check_v1对六份正文与五份文档快照共11份全部通过，最终补记字节另由doc_check_v2核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、874份上一检查点保护成员、29,611份语料和10份资料未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA不变。这些范围可能重叠，不相加作总文件数。生产仍16模块，本轮生产/测试/夹具均未修改。

Python3.7语法与未应用补丁的git apply --check通过，静态检查不替代四版本运行。tracked diff空白检查通过；唯一保留的是建议补丁.diff的四条空源行上下文，其单个前导空格属于统一diff格式，文件SHA与行号精确绑定于whitespace_review，不豁免生产代码、测试或正文的空白问题。补丁仍未应用。

一次探针续跑已经使用，后续三个连字符版本与任何语料均未继续。当前等待allowed_paths_review_request对应参数及103项范围批准；完整回归、新汇总和最终验收未运行，CP3未完成。按中途停止要求提交本地证据检查点，提交号以包含本条记录的CP3提交及仓库外收据为准，未push。后续批准后须在新批次继续，不向本批次或任何旧批次覆盖写入。
