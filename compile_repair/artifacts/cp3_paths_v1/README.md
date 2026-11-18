# CP3 绝对允许路径修正与最终验收

修改 AI：Codex；2026-11-18（America/New_York）。起点compile-repair/967d0890，用户原话“批准参数修正、探针与103项重验（推荐）”。authorization绑定请求SHA与精确103项清单，baseline合并核验912个旧交付成员；旧批次全部只读。

生产仅project.py两处允许路径改为解析后的项目根绝对路径；物理根、./入口、源字节、候选政策、设置、D3和绑定门槛保持。新增普通嵌套入口四版本测试，原八项探针和原夹具不改。12项全通过，随后103项各执行一次，原79成功保持且恢复更早版本，新增10成功，最终89成功/14未修复。

## 证据与问题处理

- path_probes：12项定向测试及8个嵌套项目的编译/Slither证据；普通根入口四项沿用原测试。
- driver_comparison_recovery：首项已经成功，脚本tuple与JSON list直接比较造成误报；保存计划逐字段相同。复用首项已封存结果，只继续未执行的102项，没有重复编译。原summary零值是分类尚未追加，不是调用没有发生；实际1编译/1Slither另记，单元精确结束耗时未保存则写null。
- revalidation/continuation收据与仓库外两个运行seal：103个不同ID，每项一次，453编译/265Slither；原79成功无回退，输入与序列化候选计划保持。
- aggregate_inventory_correction：历史中断段原本只有封存保全清单；只读汇总改按其已登记SHA验证，不制造正常完成seal，不重跑编译。
- replacement_summary/result_provenance：精确103条新旧结果SHA及30,968条未改来源；旧1032/187次观察保留但不计入新的有效统计。
- failure_summary：31,071有效、21,160成功、9,911剩余；236非Solidity单列，完整分类、包/路径、其他模板及例证。
- d6_cp4_final：29类、125条breaking changes、10个零频类别保持，频率只排实现顺序。
- runtime_acceptance与pytest_*：唯一执行、版本更早、全部三套回归的收据；最终文档和保护检查另补。

## 结果与边界

production731passed/6skipped、mando271passed/466skipped、DFG2653passed/9既有warnings。原14个未修复单元为12项Slither工具限制、1项类型错误和1项未声明标识符；不通过改写合法源码或放宽判据伪造成功。有效全量统计为115,192次编译、21,376次Slither；207次绑定未获认证全为Slither未构造，不等于207次原生错绑，D3true但绑定拒绝为0。

本批次0美元，无安装、下载、LLM、训练、GPU锁、全局solc或网络修改。原始运行与语料在仓库外，旧产物不覆盖，旧未跟踪临时文件不清理。CP3实验与回归已完成，最终范围/doc_check通过后本地提交，不自动push；后续CP4及修复规则实施未启动。详见CHANGE_LOG §35、HANDOVER与CP3_REPORT最终续节。


2026-11-18 最终交付核验补记（修改 AI：Codex）：frozen_audit通过，28,908份保护跟踪文件、25,828份旧封存文件、905份上一检查点保护成员、29,611份外部语料及10份官方资料均未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA保持。这些检查集合可能重叠，不相加作总文件数。历史文档均保留，生产仍16模块。Python3.7语法检查、tracked diff空白检查及本批次新文件空白检查通过，没有新增豁免。

doc_check_v1对六份正文与五份原文快照共11份通过；本补记及当前状态更新后的最终字节由doc_check_v2再次核验，提交以该收据通过并绑定各文档SHA为前置条件。新证据由evidence_seal与delivery_inventory封存，acceptance_status汇总最终门槛。完整回归与保护检查已通过，此后只补交付记录，没有再跑实验或修改生产代码。

CP3本地实施与验收完成，后续交独立审查。仅本地提交compile-repair，实际提交号以包含本记录的CP3提交及仓库外delivery_commit_receipt为准；本轮未push，未实施CP4或新增修复规则。参数修正及103项批准全部落实，无新增待批准执行事项；已知工具与版本边界继续按本报告保留。
