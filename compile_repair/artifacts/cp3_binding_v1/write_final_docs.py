"""Append final CP3 measurements only after the full, hash-verified merge."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
B = Path(__file__).resolve().parent
M = ROOT / "compile_repair"
summary = json.loads((B / "failure_summary.json").read_text())
assert summary["status"] == "complete"
facts = summary["measurement_facts"]
decisions = json.loads((B / "d6_cp4_final.json").read_text())
tests = {name:json.loads((B / ("pytest_" + name + "_final_v1.json")).read_text())
         for name in ["production", "mando", "dfg"]}
assert all(row["returncode"] == 0 for row in tests.values())
total = sum(summary["total"].values())
success = sum(summary["success"].values())
failed = sum(summary["remaining_failures"].values())
assert total == 31071 and success + failed == total
corpus_table = "| 语料 | 单元 | 成功 | 剩余失败 |\n|---|---:|---:|---:|\n"
for name, count in sorted(summary["total"].items()):
    corpus_table += "| {} | {} | {} | {} |\n".format(
        name, count, summary["success"].get(name, 0), summary["remaining_failures"].get(name, 0))
category_table = "| 类别 | 单元数 | 占剩余失败 |\n|---|---:|---:|\n"
for row in summary["category_unit_counts"]:
    category_table += "| {} | {} | {:.3%} |\n".format(row["category"], row["units"], row["fraction_remaining_failures"])
route_table = "| 类别 | D6 路由 | 改动等级 | 修复方式 |\n|---|---|---|---|\n"
for row in decisions["categories"]:
    route_table += "| {} | {} | {} | {} |\n".format(
        row["category"], row["route"], row["change_level"], row["repair"])
zero = [r["category"] for r in summary["category_unit_counts"] if not r["units"]]
paragraph = ("完整清单31,307条，其中SOChecker236条无Solidity声明证据单列；"
             "进入固定完整序列31,071条，成功{}、剩余失败{}。529个单文件观察复用，"
             "343个旧项目以新批次结果替换，再完成30,199条续跑；每单元只计一次，无抽样。").format(success, failed)
metrics = ("有效结果对应solc调用{}次、Slither调用{}次；原中断9次编译与被替换的旧项目335次编译/230次Slither不计入有效结果调用数，原始记录保留。"
           "旧整文件parse失败而新pragma读取成功{}个单元；unsupported_disjunction为{}个。"
           "项目Slither调用{}次，直接合约类型绑定核对{}条；D3为true但绑定检查拒绝的调用{}次。").format(
               facts["compiler_calls"], facts["slither_calls"],
               facts["old_parse_failed_new_read_succeeded"], facts["unsupported_disjunction_units"],
               facts.get("project_slither_calls",0), facts.get("direct_contract_bindings_examined",0),
               facts.get("d3_true_but_binding_rejected_calls",0))
report = """
## CP3 绑定检查获批后的完整分类（修改 AI：Codex）

### 范围、批准与方法

2026-11-17用户批准“批准项目图绑定检查（推荐）”；authorization.json绑定原request SHA。先验证旧检查点762成员及seal；所有新证据写cp3_binding_v1。此前source差异与文件名+key5批准仍有效。原D3(a/b)、单文件和6c路径保持；项目graph_usable必须额外通过直接合约类型绑定检查。检查使用编译单元内AST引用ID与原生对象文件/偏移，不按同名猜测目标；无法核验即拒绝该次图。没有修改安装包、合法源文件或版本策略。

### 全量结果

"""+paragraph+"\n\n"+corpus_table+"\n"+metrics+"""

原始语料、工作副本、stderr、AST相关事实和图保存在仓库外。本批次result_provenance逐单元绑定原/新result SHA与批次seal，final_aggregate先逐成员验证再汇总。单位是每个.sol入口及其闭包，闭包可以重叠；成功指满足当前全部接受条件，不表示合约安全，也不是所有Slither语义正确性的证明。

### 剩余失败分类

分母为全部剩余失败单元；同一单元可有多个类别，比例之和可能超过100%。每类分语料计数与最多三个完整SHA示例在failure_summary.category_unit_counts，少于三个时仅列已有例，不编造。unit_examples另给最多三个完整单元的unit_id、入口SHA和结果SHA；同字节入口可能属于不同项目闭包，结果SHA绑定各自完整记录。零观察类别保留："""+", ".join(zero)+".\n\n"+category_table+"""

最终D6清单由语料独立草案与完整频率表关联，保留原草案及SHA；频率只决定实现顺序。保护审计另核对已定位的Slither类型解析器源文件SHA，确认原生安装包没有变化。

所有other模板逐条列在failure_summary.other_templates及other_template_unit_counts，包含对应单元数和SHA示例。包名/路径与相对文件候选见unresolved_packages、unresolved_import_paths、relative_basename_candidates；前者按单元内导入位置计数。distinct_source_import_statistics另给跨重叠闭包按原始位置计数的结果，便于库索引规划。

发现原聚合器的包/路径字段来自项目组装，单文件CLI诊断缺少这些字段。最终只读统计据保存的工作源码SHA与诊断字节位置补计，12个当时已观察到的单元验证通过；原分类/结果与生产实现不变。无法唯一恢复的导入明确计入missing_import_identity_records，不按basename猜测。相对文件候选搜索只在声明的项目内进行，单文件不扩展目录搜索。

### D6与CP4清单

"""+route_table+"""

各类完整机械检查、兜底路由、CP4破坏算子和没有源码算子的原因在d6_cp4_final；29类和125条breaking-change记录全部保留。源码算子从可编译/D3成立的基础单元删除或修改，实际触发目标诊断后才纳入类别。纯Warning、运行语义、调用方JSON和无法一般构造的工具崩溃不伪造源码算子。频率只排实现先后，不删除低频/零频规则候选。

规则前提包括D3、D7原字节/偏移/节点标记、改写限错误行，以及批准的项目绑定门槛；等价性、签名或依赖身份不能唯一确定时交代理分析。合法源码的Slither原生错绑归工具限制；不会让代理“修”合法源码。0.4.x tuple-call只列已验证候选，实际改写仍留CP6。本轮不实现CP4基准或其他依赖/结构/类型修复规则。

### 已知缺口与前提实测

|| pragma频率见上；后续并集求值与版本升序尝试仍未实现。Slither仍为进程内调用，无强制超时；全部选定调用已完成不证明未来不会挂起，最大已完成Slither耗时见failure_summary。后续建议子进程隔离/明确截止时间。D19下限涉及的原区间（允许0.4.11但不允许0.4.12）逐单元列于d19_intervals_allowing_0411_but_not_0412，当前0.4.12下限未调整。

沿用前批次已封存前提：92版诊断格式切换0.6.0；重复SPDX同形探针从0.8.8拒绝，相同Solidity pragma不因此失败；tuple-call等价形态探针通过；AST-only不足以使原生Slither避开所测codegen失败，0.8.38的via-ir+optimizer组合在手写探针通过。没有重跑或修改这些旧证据。

### 测试、交付与限制

定向32passed；production723passed/6skipped，mando271passed/458skipped，DFG2653passed/9既有warnings；命令、环境、退出码与耗时见pytest_*收据。精确alias拒绝证据由既有测试产物导出，原D3(a/b)true、b预期B.sol而原生A.sol、没有graph.json。四版本正常项目核对七条直接类型声明及A/B调用位置。

生产仍16个模块，本次批准后只改slither.py、pipeline.py、evaluation/report.py及项目测试；之前CP3改动一并交付，精确清单见最终inventory。无安装/下载/LLM/训练/GPU锁/全局solc更改，0美元。最终doc_check、保护审计、空白检查与本地提交在后续补记；未自动push。
"""
progress = """
## CP3 项目绑定检查与全量分类续做（2026-11-17，修改 AI：Codex）

用户批准绑定检查后新增cp3_binding_v1，原762成员检查点/旧运行现场保持。生产修改限slither.py与对应pipeline/report处理，项目测试更新；新增证据脚本、回归收据、逐单元复用/重验清单、统计和D6/CP4清单。DECISIONS更新已定授权，CHANGE_LOG §32记录实现、问题解决与资源；HANDOVER0–5同步，第6节追加。

"""+paragraph+"\n\n"+metrics+"""

测试：production命令为既有生产Python -B -m pytest -q -p no:cacheprovider compile_repair/tests（723/6）；mando同目录271/458；mando DFGv2目录2653passed/9warnings；定向32passed。完整命令/基线及耗时见pytest_*。新绑定检查是用户批准的D3之外接受条件，原D3事实未改；旧停止记录不回写。包/路径统计补计单文件诊断的方式和证据见import_statistics_validation。

后续仍包括依赖与规则修复、并集pragma、Slither子进程截止时间以及CP4基准实现；本次清单不代表已实现。完成后先独立审查CP3，再按后续Prompt推进。最终doc_check/保护检查与提交状态见本节后补记，不自动push。
"""
change = "\n\n32.3/32.5 全量补记（修改 AI：Codex）："+paragraph+"\n\n"+metrics+"""

343项目复验230成功/113未修复，状态、选版、设置与flags全部与原记录相同，230个成功项目均通过新增绑定门槛。三套完整回归通过：production723/6、mando271/458、DFG2653/9既有warnings；定向32通过。单文件导入缺字段仅在最终只读统计补计，12个已保存实例核对通过；生产/原结果未改。复核脚本一度把slither=null当dict，已修正读法，失败的启动前置检查没有创建运行；无实验重试，见development_issues。

D6与CP4逐类清单完成，29类/125变化保留；最终统计与SHA来源在failure_summary、result_provenance、d6_cp4_final。强制doc_check与frozen_audit待随后补记，不提前写为通过；本地提交须在全部记录与检查通过后，未push。
"""
handover_note = "\n\n### 2026-11-17 CP3 项目绑定检查与完整分类（修改 AI：Codex）\n\n"+paragraph+"""

本轮按用户授权增加项目直接合约类型检查，保留D3并增加graph_usable；错绑/无法核验不存成功图。定向32、production723/6、mando271/458、DFG2653passed；旧检查点与中断现场保持。单文件包统计缺字段通过最终只读、位置与SHA核验补计。更新本文0–5的当前状态、已定授权、运行完成状态、测试、下一步与证据入口；第6节既有历史保留。报告、CHANGE_LOG §32、PROGRESS与DECISIONS同步；最终文档/保护检查后本地提交，未push。没有安装、下载、LLM、训练或全局solc改动。
"""
completed_at = datetime.now(timezone(timedelta(hours=-5))).isoformat(timespec="seconds")
completion_note = "\n\n完整分类文档记录时间：" + completed_at + "（America/New_York，EST；依据本次脚本系统时间）。授权日期仍为2026-11-17。\n"
report += completion_note
progress = progress.replace("续做（2026-11-17，修改 AI", "续做（" + completed_at[:10] + "，修改 AI") + completion_note
change += completion_note
handover_note = handover_note.replace("### 2026-11-17 CP3", "### " + completed_at[:10] + " CP3") + completion_note
blocker_note = '\n\n最终复核暂停（2026-11-18，修改 AI：Codex）：完整观测统计已生成，但CP3最终验收尚未通过。11个DAppSCAN项目入口以连字符开头，project_command与slither_arguments原样传入入口；315次solc调用将路径当选项拒绝。该问题属于参数组装，不属于源码损坏，原9,921个剩余失败包含这11项，当前统计仅为修正前观察。具体清单、命令与SHA、限定./前缀方案及新批次11单元重验请求见leading_dash_review_request.json；已向用户询问，尚未修改参数或重跑。当前批次、所有旧产物及其统计保持，修正后应另建批次、仅替换这11条观察，不把现有数字写成最终接受结果。\n\n三套最终无缓存回归均通过，但它们未覆盖本次发现的连字符入口问题，不能据此放行CP3。读取完成收据的自动审批一度超时，按工具允许仅重试一次只读检查后成功；随后WSL新命令暂报Wsl/Service/0x8007274c，使用只读UNC检查并在最小连接探测恢复后继续，没有重启WSL或修改网络。诊断提取首次漏读reason字段，随后只遍历续跑批次得10项；补入项目复验批次后确认共11项。这些是只读提取修正，没有重试编译。\n'
report += blocker_note
progress += blocker_note
change += blocker_note
handover_note += blocker_note
updates = {
    M/"CP3_REPORT.md":report, M/"PROGRESS.md":progress,
    M/"docs/CHANGE_LOG.md":change, M/"docs/HANDOVER.md":handover_note
}
for path, text in updates.items():
    assert text[:80] not in path.read_text(), str(path)
for path, text in updates.items():
    with path.open("a") as f:
        f.write(text)
p=M/"docs/HANDOVER.md"
s=p.read_text().replace("正按新批次恢复完整分类。CP3最终统计及验收尚未完成。",
                       "完整分类及D6/CP4清单已完成；最终文档/保护检查后本地提交。")
s=s.replace("DFG进行中", "DFG2653passed/9既有warnings")
s=s.replace("30,199单元待继续", "30,199单元续跑完成")
s=s.replace("30,199单元正在续跑", "30,199单元续跑完成")
s=s.replace("全量和最终检查后本地提交", "最终检查后本地提交")
s=s.replace("完整分类及D6/CP4清单已完成；最终文档/保护检查后本地提交。", "全量观测与D6/CP4清单已完成，但发现11个入口参数错误；CP3最终验收暂停，等待修正授权。")
s=s.replace("尚未提交、未push；最终检查后本地提交", "尚未提交、未push；等待11个入口参数问题的修正授权")
p.write_text(s)
p=B/"README.md"
with p.open("a") as f:
    f.write("\n完整运行补记（Codex）："+paragraph+"\n\n"+metrics+
            "\n\nfailure_summary、result_provenance及d6_cp4_final为最终统计入口；final_aggregate和write_final_docs可复核过程，拒绝覆盖结果。最终审计与文档收据见后续记录。\n")
with (B/"README.md").open("a") as f:f.write(blocker_note)
print(json.dumps({"written_documents":len(updates)+1,"total":total,"success":success,"failed":failed}))
