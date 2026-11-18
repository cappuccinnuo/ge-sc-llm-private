# CP3 连字符入口限定修正记录

修改 AI：Codex；日期：2026-11-18（America/New_York）。起点compile-repair/e3fb634f，本批次延续CP3，不覆盖cp3_binding_v1。

用户批准“批准限定修正与 11 个单元重验（推荐）”，授权与原请求SHA见authorization.json。仅project.py对以-开头的入口补./，同一目标交给solc和Slither；新增tests/test_project.py四版本探针及两文件手写项目。源文件、候选、设置、D3与绑定门槛不变。

首次run_entry_probes.py漏建仓库外临时父目录，pytest初始化FileNotFoundError；entry_probes.json/stdout/stderr完整保留。0passed/1setup error、0编译/0Slither/0语料重验，不能据此判断四版本兼容性。已准备run_entry_probes_v2.py补父目录并采用新输出路径，不改测试条件，尚未运行。

probe_setup_retry_request.json请求按原门槛续跑一次八项检查（四个新增探针和四个既有普通入口检查）。需要确认是因为PROMPTS §4.1明确要求失败停止且不得自动重试。原11项重验批准仍有效，须等八项通过后执行；本轮不重新获取下载或安装权限。

当前CP3未完成；新汇总、完整回归、11项重验未运行。旧完整观察与所有历史记录保持，不自动push，无安装/下载/LLM/训练，费用0美元。文档见CHANGE_LOG §33与CP3_REPORT最新续节，doc_check及保护审计后补。


2026-11-18 停止检查点验收补记（修改 AI：Codex）：doc_check_v1对六份正文及五份原文快照共11份全部通过；本补记后的最终字节由doc_check_v2再次核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、841份上一检查点保护成员、29,611份语料和10份资料均未变化；96份solc相关文件、两环境145/118份元数据、354条DFG代码引用和原生Slither解析器SHA保持。这些检查集合可能重叠，不相加计数。Python3.7语法解析与tracked diff --check通过，记录static_review；这些都是范围/静态检查，不能代替未完成的四版本运行验收。

本轮仍停在探针初始化错误后的续跑确认，没有再次运行pytest、solc、Slither或11单元语料。将按中途停止记录要求提交本地检查点，实际提交号以包含本补记的CP3提交及仓库外提交收据为准，未push。现有失败脚本和输出封存；若用户随后允许续跑，须把已准备且SHA固定的run_entry_probes_v2.py原字节复制到新证据批次执行，维持旧批次只读，不覆盖任何旧文件。该脚本按自身目录写入新证据，并使用新的v2临时目录；测试、版本、条件和原11项批准范围保持。
