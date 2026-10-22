from pathlib import Path
import csv,json,datetime
B=Path(__file__).resolve().parent
def read(n):return json.loads((B/n).read_text())
def rows(n):
 with (B/n).open() as f:return list(csv.DictReader(f))
def fmt(x):return "{:.4f}".format(float(x))
def table(head,data):
 return "\n".join(["| "+" | ".join(head)+" |","| "+" | ".join(["---"]*len(head))+" |"]+["| "+" | ".join(map(str,r))+" |" for r in data])+"\n"
def pick(seq,**kw):return next(x for x in seq if all(x[k]==v for k,v in kw.items()))
r=read("report.json");assert r["status"]=="complete" and r["formal_fits"]==60
TASKS=("reentrancy_author_contract","access_control_author_contract","reentrancy_author_node","access_control_author_node")
NAMES=dict(zip(TASKS,("重入合约","访问控制合约","重入节点","访问控制节点")))
st=r["statistics"];pair=r["paired"];resources=r["resources"];changes=rows("paired_deltas.csv")
lines=["# 原始HCG与整体DDG完整交叉验证结果（Codex）","",
"本批已完成60次新正式拟合：重入及访问控制，合约各5折、节点各10折，每折HCG/HCG_DDG成对训练。原图、作者标签、token特征、划分及训练数值规则均冻结。所有结果是CV validation；节点按HCG节点计分，不是独立测试或去重源码行F1。","",
"## 对照与计算","",
"- HCG：原作者CFG+CG，没有本地新增DDG。两个分支都保留既有梯度/eval/早停保存修复。",
"- HCG_DDG：同图增加冻结Stage K整体标量、状态Def–Use及状态顺序关系，含受限继承/modifier与版本分析域恢复；本轮未改变其构图算法。",
"- 新共同初始化以HCG为锚；旧Stage K B1以E3b为锚，初值摘要不同，只作历史参照，不复用成绩。",
"- paper_kfold原5/10文件折，完整固定图前向、train监督，同一val选best/早停并评分。最多50轮，patience7/delta0.001；best严格最低val loss，last另报。",
"- 合约initial_lr/max_lr=.0005/.01、weight_decay=5e-6；节点=.0002/.005、weight_decay=0。HGT hidden128、2层、8头、512维inside_token和原Adam/OneCycle不变。",
"- 单GPU串行；不按结果挑折、重训、删样本、改超参或换CPU。",""]
for ck,title in (("best","主结果：best"),("last","辅助结果：last")):
 lines+=["## "+title,"","等权折均值±样本标准差，单位%；差值单位百分点。",""];data=[]
 for t in TASKS:
  a=pick(st,task_id=t,variant="HCG",checkpoint=ck);b=pick(st,task_id=t,variant="HCG_DDG",checkpoint=ck);d=pick(pair,task_id=t,checkpoint=ck)
  data.append([NAMES[t],a["folds"],fmt(a["buggy_f1_mean"])+" ± "+fmt(a["buggy_f1_sample_std"]),fmt(b["buggy_f1_mean"])+" ± "+fmt(b["buggy_f1_sample_std"]),"{:+.4f}".format(d["buggy_f1_delta_pp_mean"]),fmt(a["macro_f1_mean"]),fmt(b["macro_f1_mean"]),"{}/{}/{}".format(d["buggy_f1_improved"],d["buggy_f1_tied"],d["buggy_f1_declined"])])
 lines+=[table(["任务","折","HCG BF1","HCG_DDG BF1","ΔBF1","HCG MF1","HCG_DDG MF1","BF1升/平/降"],data),""]
lines+=["逐折Precision/Recall、混淆矩阵、best/last epoch见[fold_results.csv](fold_results.csv)，完整配对差值及标准差见[paired_deltas.csv](paired_deltas.csv)、[paired_statistics.csv](paired_statistics.csv)。","",
"## pooled OOF与错误变化","","OOF每文件/节点只出现一次，仍受同val选模影响，不是独立测试。与等权折均值分开报告。",""];data=[]
for t in TASKS:
 a=pick(r["pooled_oof"],task_id=t,variant="HCG",checkpoint="best");b=pick(r["pooled_oof"],task_id=t,variant="HCG_DDG",checkpoint="best");group=[x for x in changes if x["task_id"]==t and x["checkpoint"]=="best"]
 data.append([NAMES[t],a["n"],fmt(a["buggy_f1"]),fmt(b["buggy_f1"]),sum(int(x["fixed"]) for x in group),sum(int(x["regressed"]) for x in group),sum(int(x["probability_changed"]) for x in group),sum(int(x["prediction_changed"]) for x in group)])
lines+=[table(["任务","OOF数","HCG BF1","HCG_DDG BF1","纠正错误","新增错误","概率变化","类别变化"],data),"","概率变化指浮点输出不完全相同，不自动表示有意义的分类提升。变化按task/fold/file/node identity对齐，详见[prediction_changes.csv](prediction_changes.csv)。","",
"## 已有困难文件","","身份同时绑定cohort与源码SHA，两类同名buggy_18不能混用。下表是节点best错误数。",""]
fe=rows("file_error_analysis.csv");data=[]
for t,files in [("reentrancy_author_node",("buggy_18.sol","buggy_36.sol")),("access_control_author_node",("buggy_18.sol","buggy_26.sol"))]:
 for name in files:
  matches=[x for x in fe if x["task_id"]==t and x["file"]==name and x["checkpoint"]=="best"];assert len(matches)==2
  a=pick(matches,variant="HCG");b=pick(matches,variant="HCG_DDG");assert a["source_sha256"]==b["source_sha256"] and a["fold"]==b["fold"]
  data.append([NAMES[t],name,a["fold"],a["source_sha256"][:12],a["errors"],b["errors"],int(b["errors"])-int(a["errors"])])
lines+=[table(["任务","文件","fold","源SHA前12位","HCG错误","HCG_DDG错误","错误差"],data),"",
"## 图不变量、关系支持与资源","","四任务原节点/属性/标签/特征/CFG+CG边逐项不变；原HCG前向与原模型bitwise一致，见[input_inventory.json](input_inventory.json)。",""]
data=[]
for x in read("input_inventory.json"):
 a=x["invariants"];z=a["added_relations"];data.append([NAMES[x["task_id"]],a["nodes"],a["base_edges"],a["enhanced_edges"],z.get("DATA_DEF_USE",0),z.get("STATE_DEF_USE",0),z.get("STATE_ACCESS_ORDER",0),z.get("EXTERNAL_CALL_BEFORE_STATE_WRITE",0)])
lines+=[table(["任务","节点","原边","增强边","标量DU","状态DU","状态顺序","调用→写入"],data),""]
gr=rows("relation_support_gradients.csv");supported=[x for x in gr if int(x["train_edges"])>0];unsupported=[x for x in gr if int(x["train_edges"])==0];zero=[x for x in supported if float(x["max_message_gradient_l1"])==0]
lines+=["增强canonical/fold记录{}项：有训练支持{}项，无训练支持{}项；有支持但全程message梯度为0有{}项。无训练支持的已注册关系单列，不视为接入异常，也不在评分时建参。访问控制没有调用→写入边，状态DU仍稀少。".format(len(gr),len(supported),len(unsupported),len(zero)),"",
"120份best/last checkpoint重载预测一致；输入、未训练初值、schema及收据验收通过。",""];data=[]
for t in TASKS:
 for v in ("HCG","HCG_DDG"):
  q=[x for x in resources if x["task_id"]==t and x["variant"]==v]
  data.append([NAMES[t],v,q[0]["parameters"],fmt(sum(x["seconds"] for x in q)),fmt(max(x["peak_allocated_mib"] for x in q)),fmt(max(x["peak_reserved_mib"] for x in q)),min(x["minimum_card_free_mib"] for x in q)])
lines+=[table(["任务","变体","参数","fit总秒","最大allocated MiB","最大reserved MiB","最小整卡free MiB"],data),"","失败记录{}项。实际attempt和资源见[resources.csv](resources.csv)。4GiB显存余量较小，耗时不应当作排除了系统影响的公平速度基准。".format(len(r["failures"])),"",
"## 高分与结论边界","","完整折结果而非fold0决定结论。文件隔离仍可能有跨文件重复注入模板。验证正节点在train存在完全相同(node type,code)的比例范围如下；它只是描述统计，不是记忆效应的因果证明，本轮没有重新划分。",""]
ov=rows("code_overlap.csv")
for t in ("reentrancy_author_node","access_control_author_node"):
 vals=[int(x["positive_exact_type_code_in_train"])/int(x["validation_positive_nodes"])*100 for x in ov if x["task_id"]==t and int(x["validation_positive_nodes"])]
 lines.append("- "+NAMES[t]+"："+fmt(min(vals))+"%–"+fmt(max(vals))+"%。")
lines+=["","- 整体DDG对照同时改变新关系参数、聚合及优化轨迹，不能把全部差值写成纯语义因果贡献。",
"- 单固定seed、同val选模评分；折间标准差是描述统计，不是独立seed方差。节点不是大量独立实验。",
"- 不因last更高或某折下降改变主规则。高F1不证明七类泛化，未提升也不证明所有数据依赖无用。",
"- 本轮未运行更多seed、其余五类、独立测试、新关系或逐小点消融。后续研究需基于完整对照，未经授权不自动执行。","",
"## 测试与复核","","新增23项通过；联合回归727通过、1项旧资源路径绑定失败。同一旧测试在资源报告所属原树通过；保留失败日志，未改生产规则或历史资源。共728个不同用例得到对应环境验证，31条联合警告均为既有弃用提示。见[test_acceptance.json](test_acceptance.json)。","",
"~~~bash","conda activate mando","cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11","python -B -m scripts.DFG.experiments.overall_cv.control verify","python -B -m scripts.DFG.experiments.overall_cv.control summarize","~~~","",
"plan/seal、每折task.json和未训练初值、每fit日志/history/best/last/预测/收据、全部CSV保存在本独立目录；历史实验不覆盖。运行与恢复说明见新模块README。","",
"生成时间："+datetime.datetime.utcnow().isoformat()+"Z；实施、审查、执行与分析AI：Codex。"]

lines+=["","## 结果解读与时间记录","",
"两个合约任务的best离散预测完全相同，因此本批没有合约分类收益。重入节点等权平均BF1仅+0.0447个百分点，33次纠错与34次新增错误并存；这不足以支持稳定改善的结论，也不能只凭七折上升忽略错误总数。访问控制节点BF1下降0.0837个百分点，2折上升/4折持平/4折下降，纠正2个而新增7个错误；两个困难文件错误均不变。两个节点任务的pooled OOF BF1都略降。因此本批没有证明整体DDG具有稳定分类收益。 本轮验收证明的是冻结输入与训练接入的一致性及本批结果可复核，不等于已实现或验证完整Solidity数据依赖语义。","",
"该受控实验检验的是冻结整体DDG在当前数据、标签、特征及训练配置上的增量；没有独立验证集外测试或多seed证据。部分折高分与大量跨文件相同代码片段并存，不能仅凭F1接近99认定程序错误，也不能把它作为真实合约泛化已经充分解决的证据。","",
"本轮不继续增加关系或自动训练。当前优先交付可复核的完整结果；下一轮若继续研究，宜先依据错误变化检查当前新增依赖是否覆盖真正难例，再由用户决定更有区分度的独立评估，而非为提升数字改本批规则。",""]
gap=read("timing_gap_observation.json")
lines+=["监控UTC时间在"+gap["last_monitor_before_gap"]+"与"+gap["first_monitor_after_gap"]+"之间出现约{:.2f}秒间隔；同一访问控制节点fold2/HCG最终正常完成，fit单调计时为{:.2f}秒。原因未确证。原始记录均保留，没有人为扣减或因此重训，不把该间隔或批次墙钟解释为正常计算时间。见[timing_gap_observation.json](timing_gap_observation.json)。".format(gap["observed_timestamp_gap_seconds"],gap["affected_fit_result"]["seconds_monotonic"]),"",
"独立轮次验收见[final_selection_audit.json](final_selection_audit.json)：60项best均对应各自history中严格最低val loss，实际学习率和早停配置一致，120份checkpoint重载预测一致。文件保护和交付摘要分别见[protected_after.json](protected_after.json)、[delivery_manifest.json](delivery_manifest.json)。",""]

(B/"OVERALL_CV_RESULT_REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
print(B/"OVERALL_CV_RESULT_REPORT.md")
