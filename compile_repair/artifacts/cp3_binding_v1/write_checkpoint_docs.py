"""Record a reviewed CP3 checkpoint without claiming final acceptance."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
B=Path(__file__).resolve().parent
M=ROOT/"compile_repair"
audit=json.loads((B/"frozen_audit.json").read_text());assert audit["passed"]
doc=json.loads((B/"doc_check_v1.json").read_text());assert doc["passed"]
tests={k:json.loads((B/("pytest_"+k+"_final_v1.json")).read_text()) for k in ["production","mando","dfg"]}
assert all(v["accepted"] for v in tests.values())
stamp=datetime.now(timezone(timedelta(hours=-5))).isoformat(timespec="seconds")
facts=json.loads((B/"failure_summary.json").read_text())["measurement_facts"]
assert facts.get("d3_true_but_binding_rejected_calls",0)==0
note=("""
本批次收尾检查（修改 AI：Codex；时间：%s，America/New_York/EST）：完整31,071单元观察与两个新运行seal全部核验，复验批次2,385文件、续跑批次193,136文件，运行实现SHA与当前16模块一致。三套最终无缓存回归均通过：production723passed/6skipped（%.3f秒）、mando271passed/458skipped（%.3f秒）、DFG2653passed/9既有warnings（%.3f秒），数据见pytest_*_final_v1.json。定向32passed沿用本轮既有收据，没有再次重跑。

doc_check_v1检查7份正文，全部UTF-8/CJK通过；本次补记完成后以doc_check_v2.json复查最终字节。frozen_audit通过：28,908份受保护跟踪文件、25,828份旧封存文件、753份上一检查点受保护成员、29,611份外部语料文件和10份资料无变化；96个solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither类型解析器SHA保持。文档历史前缀全部保留。这些是分别定义的检查范围，可能重叠，不能相加作为独立文件总数。

全量中34,973条直接合约类型声明被核对；D3为true但新增绑定检查拒绝的调用为0。139次未获绑定认证的项目调用全部属于Slither未构造成功，不能表述为139次错绑；手写alias用例独立证明已知错绑会拒绝图。原D3事实、源码和安装包均保持。

CP3最终验收仍暂停：11个连字符入口被误当solc选项（315次调用），修正请求见leading_dash_review_request.json，尚未批准、未修改project.py、未重验。当前统计为修正前完整观察，不能宣称CP3已完成。按PROMPTS的中途停止记录要求整理本地检查点；提交身份以包含本条记录的CP3提交为准，未push。无安装、下载、LLM、训练、GPU锁、全局solc或网络修改。所有原始数据与本轮新运行证据保留，后续修正须使用新批次。
""" % (stamp,tests["production"]["elapsed_seconds"],tests["mando"]["elapsed_seconds"],tests["dfg"]["elapsed_seconds"]))
for path,heading in [(M/"CP3_REPORT.md","\n\n### 收尾检查与待确认事项\n\n"),
                     (M/"PROGRESS.md","\n\n本批次收尾补记：\n\n"),
                     (M/"docs/CHANGE_LOG.md","\n\n#### 32.5.1 完整观测检查与待确认暂停（2026-11-18，修改 AI：Codex）\n\n")]:
 with path.open("a",encoding="utf8") as f:f.write(heading+note)
p=M/"docs/HANDOVER.md";old=p.read_text();history=old[old.index("## 6. "):]
head="""# CompileRepair 交接文档

> 新接手先读本文0–5、PROMPTS r2.13 §4.1/§4.5、CP3_REPORT最新续节、artifacts/cp3_binding_v1/README与leading_dash_review_request、DECISIONS、CHANGE_LOG §32。第6节历史只追加。

## 0. 一句话

项目图绑定检查已按批准实现；31,071单元全量观察完成，最终回归与保护审计通过。最终复核发现11个连字符入口参数错误，CP3尚未完成，修正与重验等待用户决定。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 当前实现 | 项目保留D3，再核对直接合约类型绑定；错绑/无法核验不存成功图 | slither.py、pipeline.py、report.py |
| 完整观察 | 31,071单元：21,150成功、9,921剩余失败；236非Solidity单列 | failure_summary、result_provenance |
| 当前阻塞 | 11个入口以-开头，被solc当选项；315次调用；不可计作源码错误 | leading_dash_review_request |
| 已定授权 | 897输入、文件名+key5、项目绑定检查均已批准 | 各authorization |
| 待确认 | 仅以-开头入口统一加./；四版本探针通过后新批次重验11单元 | 请求已发，不重复索取已有授权 |
| 测试 | 定向32；production723/6；mando271/458；DFG2653/9既有warnings | pytest_*收据 |
| 检查 | doc_check_v1七份通过；frozen_audit通过；补记后查v2 | doc_check_v*、frozen_audit |
| 交付边界 | 本地检查点，CP3未通过最终验收；未push | 本记录所在CP3提交与工作清单 |

## 2. 分支与工作树

工作树/home/zhao/SmartContract/ge-sc-llm-compile，分支compile-repair。本任务起点dc6c5fb44041e1023daef1bfd7d9760f534c7f0a；当前交付身份由包含本记录的CP3提交确定，运行实现另有16模块SHA。此前同一任务已pull，未在带修改的树上再次pull。

本批次artifacts/cp3_binding_v1保存授权、完整观察、测试、待确认请求与封存清单。旧cp3_continue_v1及更早产物只读保持。原语料与批量输出位于仓库外/home/zhao/SmartContract/corpora与compile-repair-local；未跟踪的旧临时产物不清理、不混入交付。

## 3. 环境

production为Python3.10.21、Slither0.11.6、crytic-compile0.4.2；mando为Python3.7.12、Slither0.8.0、crytic-compile0.2.4。92支持版本来自既有工具链，96个solc相关文件核验未变；未安装、升级或切换全局solc。

从仓库根运行，PYTHONDONTWRITEBYTECODE=1、PYTHONNOUSERSITE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2，TREE_SITTER_LIB_DIR沿用既有linux-x86_64路径。CPU、0美元，无LLM、HGT或GPU锁。WSL曾短暂返回0x8007274c，后只读最小探测恢复；没有重启或更改网络。

## 4. 必读与下一步

1. 面向未来任意合约，语料仅评估；29类和125条breaking changes保留，频率只排实现先后。
2. 绑定检查原话“批准项目图绑定检查（推荐）”已实施，不再次询问。新增入口参数修正仍待答复。
3. 11入口的命令、源码/结果SHA及精确范围见leading_dash_review_request；仅./前缀建议尚未实施。批准后才修正、运行四版本探针和新批次11单元重验；异常即停。
4. 现有全量观察每单元计一次：529单文件复用，343项目新验证，30,199续跑。旧被替换观察和原中断9次编译不覆盖。
5. 当前21,150/9,921是修正前观察；11项属于调用组装失败，不能当源码损坏。新结果须另建汇总并逐项标明替换来源。
6. 项目graph_usable额外检查直接合约类型绑定；D3事实保留。检查不覆盖全部嵌套类型、表达式、继承或IR语义，成功不是全图语义证明。
7. 全量未发现D3true而新增绑定拒绝；139次未获认证均为Slither未构造，不等于139次错绑。手写alias精确拒绝证据保留。
8. || pragma并集和Slither进程内无超时仍留后续CP；当前不补依赖、不改写tuple或实现CP4基准。
9. 不执行语料脚本、不再分发外部源码；外部输入只读。源码、Slither安装和全局solc保持。
10. 原scripts、模型、根交接/训练文档、EdgeSem工作树和旧产物禁止修改；Python3.7、分层与30模块上限保持，目前16模块。
11. 修正方案及所有问题处理均写本模块CHANGE_LOG/HANDOVER/PROGRESS/CP3_REPORT；原历史只追加。
12. 当前CP3尚未最终完成；不能因常规测试通过就忽略未覆盖的入口参数问题。

## 5. 关键路径

| 内容（compile_repair下） | 路径 |
|---|---|
| 当前授权与原请求 | artifacts/cp3_binding_v1/authorization.json；cp3_continue_v1/alias_binding_review_request.json |
| 当前待确认 | cp3_binding_v1/leading_dash_review_request.json、acceptance_status.json |
| 完整观察与来源 | cp3_binding_v1/failure_summary.json、result_provenance.json |
| D6与CP4清单 | cp3_binding_v1/d6_cp4_final.json |
| 原生错绑拒绝与正例 | cp3_binding_v1/binding_rejection_acceptance、pytest_targeted_v1 |
| 测试与保护检查 | cp3_binding_v1/pytest_*_final_v1、doc_check_v*、frozen_audit |
| 输入与分类表 | cp3_continue_v1/unit_inventory.jsonl、taxonomy_verified.json |
| 报告与交接 | CP3_REPORT、PROGRESS、docs/CHANGE_LOG §32、DECISIONS |

---

"""
history+="\n\n### 2026-11-18 CP3 完整观察与入口参数问题暂停（修改 AI：Codex）\n\n"+note+"\n更新本文0–5为实际完整观察、测试/审计结果、未完成状态与待确认修正范围；第6节既有历史字节保持。\n"
p.write_text(head+history,encoding="utf8")
with (B/"README.md").open("a",encoding="utf8") as f:f.write("\n\n## 本批次收尾状态\n\n"+note)
with (B/"closure_record.json").open("x") as f:
 json.dump({"recorded_at_est":stamp,"status":"awaiting_leading_dash_entry_decision","cp3_complete":False,"tests_passed":True,"frozen_audit_passed":True,"doc_check_v1_passed":True,"doc_check_after_append":"v2 pending","native_binding_rejections_with_d3_true":0,"no_experimental_retry":True,"push_performed":False},f,indent=2);f.write("\n")
print(json.dumps({"records_written":5,"recorded_at_est":stamp,"cp3_complete":False}))
