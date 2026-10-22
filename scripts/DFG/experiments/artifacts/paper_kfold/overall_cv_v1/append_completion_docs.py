from pathlib import Path
import json,csv,datetime
B=Path(__file__).resolve().parent
R=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11");O=Path("/home/zhao/SmartContract/ge-sc-llm")
def read(n):return json.loads((B/n).read_text())
def pick(seq,**kw):return next(x for x in seq if all(x[k]==v for k,v in kw.items()))
def tab(head,rows):return "\n".join(["| "+" | ".join(head)+" |","| "+" | ".join(["---"]*len(head))+" |"]+["| "+" | ".join(map(str,x))+" |" for x in rows])
r=read("report.json");a=read("final_selection_audit.json")
assert r["status"]=="complete" and r["formal_fits"]==a["fits"]==60 and a["status"]=="passed"
assert (B/"OVERALL_CV_RESULT_REPORT.md").exists()
tasks=["reentrancy_author_contract","access_control_author_contract","reentrancy_author_node","access_control_author_node"]
names=dict(zip(tasks,["重入合约","访问控制合约","重入节点","访问控制节点"]))
st=r["statistics"];paired=r["paired"]
table=[]
for t in tasks:
 x=pick(st,task_id=t,variant="HCG",checkpoint="best");y=pick(st,task_id=t,variant="HCG_DDG",checkpoint="best");d=pick(paired,task_id=t,checkpoint="best")
 table.append([names[t],x["folds"],"{:.4f}".format(x["buggy_f1_mean"]),"{:.4f}".format(y["buggy_f1_mean"]),"{:+.4f}".format(d["buggy_f1_delta_pp_mean"]),"{:.4f}".format(x["macro_f1_mean"]),"{:.4f}".format(y["macro_f1_mean"]),"{}/{}/{}".format(d["buggy_f1_improved"],d["buggy_f1_tied"],d["buggy_f1_declined"])])
tbl=tab(["任务","折","HCG BF1","HCG_DDG BF1","ΔBF1(pp)","HCG MF1","HCG_DDG MF1","BF1升/平/降"],table)
with (B/"paired_deltas.csv").open() as f:delta=list(csv.DictReader(f))
err=[]
for t in tasks:
 q=[x for x in delta if x["task_id"]==t and x["checkpoint"]=="best"]
 err.append("- "+names[t]+"：纠正{}个错误、新增{}个错误、类别变化{}个、概率发生浮点变化{}个。".format(sum(int(x["fixed"]) for x in q),sum(int(x["regressed"]) for x in q),sum(int(x["prediction_changed"]) for x in q),sum(int(x["probability_changed"]) for x in q)))
last=[]
for t in tasks:
 x=pick(st,task_id=t,variant="HCG",checkpoint="last");y=pick(st,task_id=t,variant="HCG_DDG",checkpoint="last")
 last.append("- "+names[t]+" last：BF1 {:.4f}→{:.4f}；MF1 {:.4f}→{:.4f}。".format(x["buggy_f1_mean"],y["buggy_f1_mean"],x["macro_f1_mean"],y["macro_f1_mean"]))
today=datetime.datetime.utcnow().strftime("%Y-%m-%d")
gap=read("timing_gap_observation.json")
res=r["resources"]
elapsed=sum(x["seconds"] for x in res)
detail=[
"","",
"**26.7 全部正式训练完成与最终验收（"+today+" UTC，Codex）**","",
"已完成本批60次新正式拟合：重入/访问控制合约各10次、节点各20次；均为attempt_001，无训练失败、重试或OOM。首对验收后继续剩余58次，每项任务通过完整性和从冻结标签独立复算后才进入下一项。原K/H1/H2成绩未混入，也没有重跑来挑选分数。","",
"final_verify.log及final_summary.log记录60项验收；final_selection_audit.json再次核验60项完整history、实际配置、严格最低val loss对应best和120份checkpoint重载一致。训练前向/评分没有临时创建参数，主干参数均更新。完整报告OVERALL_CV_RESULT_REPORT.md位于overall_cv_v1独立批次。","",
"**26.8 主结果与辅助结果**","",
"以下是CV validation的等权折均值（百分数）；节点按HCG节点口径。逐折Precision/Recall、混淆矩阵、样本标准差、OOF及来源身份在对应CSV完整保存。","",tbl,"",
"best的实际错误变化：","",
*err,"",
"last独立辅助结果，不代替预定best：","",
*last,"",
"两个合约任务best均没有离散分类收益。重入节点平均BF1仅提高约0.0447个百分点，纠正33个同时新增34个错误；困难fold8约67%，并非所有折都99。概率变化、等权折均值和pooled OOF必须分别解释，不能选择对增强更有利的一种口径。访问控制节点best BF1下降0.0837个百分点，MF1下降约0.0701个百分点，2折上升/4折持平/4折下降，纠正2个而新增7个错误；其buggy_18和buggy_26分别仍87和42错误。两个节点任务的pooled OOF BF1都略降，本批不支持整体DDG有稳定收益。","",
"**26.9 覆盖、限制、资源与时间异常**","",
"增强仅为冻结四类正向关系；节点STATE_DEF_USE仍仅重入4条、访问控制5条，访问控制没有EXTERNAL_CALL_BEFORE_STATE_WRITE。逐canonical/fold训练/验证支持、梯度及未见关系审计在relation_support_gradients.csv。少量状态DU和大量模板重复是结果解释的线索，不足以单独证明无收益的因果原因。原标签冻结保证受控对比，不能据此证明作者ground truth完全正确。","",
"困难文件按cohort/source SHA区分：重入buggy_18的best错误252→252；buggy_36为60→57。访问控制buggy_18/26及所有变化文件见file_error_analysis.csv及最终报告，不改标签、不删除困难文件。","",
"全部fit计时器秒数合计{:.2f}，最大allocated {:.2f} MiB、reserved {:.2f} MiB；最小整卡free {} MiB。资源表保留每折参数量、轮次和真实记录；各分支新增参数/聚合/优化轨迹也变化，不能把分差完全归为纯依赖语义效应。".format(elapsed,max(x["peak_allocated_mib"] for x in res),max(x["peak_reserved_mib"] for x in res),min(x["minimum_card_free_mib"] for x in res)),"",
"监控UTC时间从2026-10-19 14:21:20跳至2026-10-20 01:03:45，间隔约{:.2f}秒，同一个访问控制节点fold2/HCG进程仍继续且最终正常完成；其单调计时训练秒数{:.2f}。原因未证实，可能涉及宿主机挂起/调度或时钟行为。未从记录中擅自扣除时间、重训或更改配置；不把批次墙钟或资源秒数当作排除系统影响的速度基准。详见timing_gap_observation.json。".format(gap["observed_timestamp_gap_seconds"],gap["affected_fit_result"]["seconds_monotonic"]),"",
"**26.10 交付、复核与停止边界**","",
"新增报告/验收辅助脚本仅置于overall_cv_v1产物目录，不进入冻结训练源码。report.json、fold_results.csv、fold_statistics.csv、paired_deltas.csv、paired_statistics.csv、pooled_oof.csv、oof_predictions.csv、prediction_changes.csv、file_error_analysis.csv、relation_support_gradients.csv、resources.csv、code_overlap.csv以及各fit best.pt/last.pt/日志/收据均保留。","",
"测试结论沿用26.4：新23项通过；联合727通过/1个历史路径测试失败，同一旧测试在原资源所属工作树通过。没有为取得全绿修改历史资源或运行代码。历史失败日志和解释保留；最终保护检查另见protected_after.json，交付摘要见delivery_manifest.json。","",
"复核命令（已执行）：","",
"~~~bash","conda activate mando","cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11","python -B -m scripts.DFG.experiments.overall_cv.control verify","python -B -m scripts.DFG.experiments.overall_cv.control summarize","~~~","",
"训练入口仍为python -u -B -m scripts.DFG.experiments.overall_cv.control run；成功收据验收后复用，失败需明确重试，不能称epoch断点续训。精确HEAD/资产绑定保持；未来归档提交后需要适用的只读历史验证，不能改旧seal。","",
"本轮结束在完整原HCG与整体DDG对照、分析及文档交付。没有启动新seed、七类全量、独立测试、新关系、完整storage/跨函数分析或逐小点消融。下一步应由完整误差证据决定，不能仅为追求提升继续堆关系。实施、执行、核验与分析AI：Codex。",""]
handover=["","","## "+today+" 原始HCG与整体DDG完整对照完成（Codex）","",
"- overall_cv_v1已完成60次新正式fit，30配对折，全部attempt_001、0训练失败/重试/OOM。重入及访问控制合约各5折、节点各10折；两分支共同新初值，以原HCG为锚，不混用旧K B1或H1/H2成绩。","",
tbl,"",
"- 主结果全部为CV validation，按最低val loss选best；节点按HCG节点，last及OOF分表。两个合约best类别完全相同。重入节点平均BF1仅+0.0447pp，纠正33/新增34；困难文件buggy_18仍252错误，buggy_36 60→57。访问控制节点best BF1−0.0837pp，纠正2/新增7，buggy_18/26仍87/42错误；两个节点pooled OOF均略降。本批未证实稳定增益。last及完整误差另报。","",
"- 原DDG算法/HGT/tokenizer/作者标签/原折/学习率/早停未改。60历史轮次/配置与120份checkpoint重载验收通过，节点/特征/原基础边不变量通过。状态DU仍很少，访问控制无调用→写入边；不能把概率变化当作分类收益或证明七类泛化。","",
"- 约10小时监控UTC间隔与fit单调耗时不一致，保留timing_gap_observation.json，原因未确定；受影响fit正常完成，无重训或自动降配，不拿该时间作为公平速度基准。","",
"- 新23测试通过；联合727通过+1历史路径失败，该项在原树通过。保护/交付见protected_after.json与delivery_manifest.json，原用户文件保留、文档仅追加。完整详细记录training_changes第26.7–26.10节。","",
"- 入口scripts/DFG/experiments/overall_cv/README.md；产物scripts/DFG/experiments/artifacts/paper_kfold/overall_cv_v1/OVERALL_CV_RESULT_REPORT.md及逐折/误差/关系/资源CSV。此批停止，未自动扩类别、seed、关系或新训练。实施、执行、分析AI：Codex。",""]
for root in (R,O):
 for rel,parts,marker in [("docs/training_changes_2026-10-07.md",detail,"**26.7 全部正式训练完成"),("HANDOVER.md",handover,"原始HCG与整体DDG完整对照完成（Codex）")]:
  p=root/rel;text=p.read_text(encoding="utf-8")
  if marker in text:raise RuntimeError("Already appended: "+str(p))
  with p.open("a",encoding="utf-8") as f:f.write("\n".join(parts))
  print("APPENDED",p)
