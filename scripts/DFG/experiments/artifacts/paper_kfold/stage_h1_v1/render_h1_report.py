"""Render H1 review from immutable summaries; does not train or change inputs."""
from pathlib import Path
import csv,json,statistics
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def rows(n):return list(csv.DictReader((P/n).open()))
def num(x):return "%.4f"%float(x)
def table(headers,data):
 return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join(["---"]*len(headers))+" |"]+["| "+" | ".join(map(str,r))+" |" for r in data])+"\n"
def main():
 report=read("report.json");a=read("analysis.json");assert report["status"]=="complete"
 names={"reentrancy_author_contract":"重入·合约","access_control_author_contract":"访问控制·合约","reentrancy_author_node":"重入·节点","access_control_author_node":"访问控制·节点"}
 stats=rows("fold_statistics.csv");last=rows("last_fold_statistics.csv");pairs=rows("paired_statistics.csv")
 summary=rows("summary.csv");lastrows=rows("last_summary.csv");deltas=rows("paired_deltas.csv");pool=rows("pooled_oof.csv")
 baseline=rows("baseline_statistics.csv");support=rows("enhancement_support.csv");files=rows("file_error_analysis.csv")
 text=["# Stage H1 完整交叉验证结果报告\n\n2026-10-14；执行与分析：Codex。状态：H1 已完成，H2 未执行。\n",
 "## 1. 结论与实验身份\n\nE3b 在两个节点任务的 best 上取得小幅平均收益，未证明稳定或普遍提升；两个合约任务的 best 类别预测完全一致。主要困难文件尚未改善。不能据此宣称七类漏洞泛化或状态依赖已经全面有效。\n\n本批严格成对比较：E2=修复 v1.1 标量 DDG；E3b=E2+STATE_DEF_USE+STATE_ACCESS_ORDER+EXTERNAL_CALL_BEFORE_STATE_WRITE。原 E0=作者 HCG、E1=早期标量 DDG，另作为历史同折参考。\n\n独立批次 stage_h1_v1：52 次新增拟合、8 次 Stage G fold0 复用，共60个正式模型；30组 fresh E2→fresh E3a→fresh E3b 初始化完整保留。E3a 与 E3b 共享的状态关系初值一致，未从训练后模型初始化。H2 仅固定计划：26次新增+4次复用，尚未运行。\n\nHEAD 44e7337bb7b47738bc49a947ed5625809f7f006a，分支 ddg-v1.1-correctness。GitHub 最新报告与本地一致；Stage G 训练 HEAD c311c939... 的75份运行源码逐一一致，本批封存82份运行源码和684项固定资产。未提交、推送、重置、迁移或覆盖旧实验。复用证据见 fold0_reuse_audit.json；独立计划及封印见 plan.json、plan.seal.json、h2_plan.json、h2_plan.seal.json。\n",
 "## 2. 固定训练与评分口径\n\npaper_kfold：合约5折、节点10折，单个固定seed1及既定每折随机状态公式。完整任务图前向，节点train/val mask、合约文件监督；训练更新仅用train标签，同一val用于早停、best选择及评分。因此全部结果为 **CV validation**，pooled OOF也不是独立测试。节点指标单位为原HCG节点，不是源码行去重指标。\n\nHGT隐藏128、2层、8头、dropout0.2、原inside_token；Adam初始lr0.0005、OneCycle max_lr0.01、50步、weight_decay5e-6；最多50epoch、patience7、delta0.001。严格最低val loss保存best，delta控制patience参考；last独立报告。新关系、标签、token、折、HGT、学习率及早停数值均未改变。未注册schema仍报错；训练未见但已注册的关系保留并审计，不在评分阶段创建参数。\n\n本批全部52次新拟合均attempt_001成功：0失败、0重试、0 OOM、0非有限loss中止。没有删除困难折、文件或边。\n",
 "## 3. Best 主结果：等权折均值与样本标准差\n\n单位：百分数；±为折间样本标准差。Precision/Recall均指buggy正类。\n"]
 def stat_table(data):
  return table(["任务","模型","Buggy-F1 ± SD","Macro-F1 ± SD","Precision ± SD","Recall ± SD"],
   [[names[r["task_id"]],r["variant"]]+[num(r[m+"_mean"])+" ± "+num(r[m+"_sample_std"]) for m in ("buggy_f1","macro_f1","precision","recall")] for r in data])
 text.append(stat_table(stats))
 text.append("\n配对差值单位为百分点，单独计算每折E3b−E2再求均值与样本标准差。折之间训练集有重叠，以下为描述统计，不能把折当独立seed重复。\n")
 text.append(table(["任务","ΔBF1 ± SD","ΔMF1 ± SD","BF1 提升/持平/下降","MF1 提升/持平/下降"],
  [[names[r["task_id"]],num(r["buggy_f1_delta_pp_mean"])+" ± "+num(r["buggy_f1_delta_pp_sample_std"]),num(r["macro_f1_delta_pp_mean"])+" ± "+num(r["macro_f1_delta_pp_sample_std"]),
   "/".join(r["buggy_f1_"+s] for s in ("improved","tied","declined")),"/".join(r["macro_f1_"+s] for s in ("improved","tied","declined"))] for r in pairs if r["checkpoint"]=="best"]))
 text.append("\n## 4. Best 每折指标、混淆矩阵与轮次\n\nBF/MF/P/R=Buggy-F1/Macro-F1/Precision/Recall。混淆矩阵顺序[ TN, FP, FN, TP ]。下表轮次为1起始；CSV原字段为0起始。每个fold0来自Stage G且未重训。\n")
 for task in names:
  text.append("\n### "+names[task]+"\n")
  data=[]
  for f in range(5 if task.endswith("_contract") else 10):
   aa=next(r for r in summary if r["task_id"]==task and int(r["fold"])==f and r["variant"]=="E2")
   bb=next(r for r in summary if r["task_id"]==task and int(r["fold"])==f and r["variant"]=="E3b")
   dd=next(r for r in deltas if r["task_id"]==task and int(r["fold"])==f and r["checkpoint"]=="best")
   fmt=lambda r:" / ".join(num(r[m]) for m in ("buggy_f1","macro_f1","precision","recall"))
   epochs=lambda r:str(int(r["best_epoch"])+1)+"/"+str(int(r["last_epoch"])+1)
   data.append([f,fmt(aa),fmt(bb),num(dd["buggy_f1_delta_pp"])+" / "+num(dd["macro_f1_delta_pp"]),
    aa["tn_fp_fn_tp"]+" / "+bb["tn_fp_fn_tp"],epochs(aa)+" / "+epochs(bb),dd["fixed"]+"/"+dd["regressed"]])
  text.append(table(["fold","E2 BF/MF/P/R","E3b BF/MF/P/R","ΔBF/ΔMF","混淆矩阵 E2 / E3b","best/last轮 E2 / E3b","纠正/新增错误"],data))
 text.append("\n## 5. Last 辅助结果（不替换best）\n")
 text.append(stat_table(last))
 text.append(table(["任务","last ΔBF1 ± SD","last ΔMF1 ± SD","BF1 提升/持平/下降"],
  [[names[r["task_id"]],num(r["buggy_f1_delta_pp_mean"])+" ± "+num(r["buggy_f1_delta_pp_sample_std"]),num(r["macro_f1_delta_pp_mean"])+" ± "+num(r["macro_f1_delta_pp_sample_std"]),
  "/".join(r["buggy_f1_"+s] for s in ("improved","tied","declined"))] for r in pairs if r["checkpoint"]=="last"]))
 text.append("\n完整逐折last、混淆矩阵及资源见[last_summary.csv](last_summary.csv)。访问控制节点last平均BF1下降1.3058个百分点，新增错误多于纠正；best的小幅收益不能解释为整个训练轨迹都更稳定。重入last的等权折均值差为负而pooled OOF差为正，是样本权重不同，不能挑选有利口径代替预定主指标。\n")
 text.append("\n## 6. Pooled OOF（独立于等权折均值）\n\n每个原文件恰好在一个val折出现；节点身份无重复，覆盖142/114个合约文件、12036/7710个节点。仍是使用同val选模后的CV验证预测拼接，不能称独立测试。\n")
 text.append(table(["任务","模型","checkpoint","BF1","MF1","Precision","Recall","[TN,FP,FN,TP]"],
  [[names[r["task_id"]],r["variant"],r["checkpoint"]]+[num(r[m]) for m in ("buggy_f1","macro_f1","precision","recall")]+[r["tn_fp_fn_tp"]] for r in pool]))
 text.append("\n## 7. 离散预测、概率变化与困难文件\n")
 text.append(table(["任务","checkpoint","样本数","纠正错误","新增错误","分类改变","仅概率改变","平均绝对概率变化(pp)","最大变化(pp)"],
  [[names[r["task_id"]],r["checkpoint"],r["n"],r["fixed"],r["regressed"],r["prediction_changed"],r["probability_only_changed"],num(100*r["mean_absolute_probability_delta"]),num(100*r["max_absolute_probability_delta"])] for r in a["pair_prediction_summary"]]))
 text.append("\nBest：重入节点纠正13漏报+18误报，新增7漏报+10误报，净少14错误；访问控制纠正5漏报+8误报，新增2漏报+1误报，净少10错误。两个合约任务全部best分类相同，主要表现为概率变化。节点绝大多数样本也只改变概率；少数样本跨越分类阈值。不能把概率改变数量当作正确性收益。\n")
 for task in ("reentrancy_author_node","access_control_author_node"):
  ff=sorted([r for r in files if r["task_id"]==task and r["checkpoint"]=="best"],key=lambda r:int(r["E2_errors"]),reverse=True)[:8]
  text.append("\n### "+names[task]+"：错误最多的文件\n")
  text.append(table(["文件","fold","节点/正例","E2 FP/FN","E3b FP/FN","错误 E2→E3b"],
   [[r["file"],r["fold"],r["n"]+"/"+r["positive"],r["E2_fp"]+"/"+r["E2_fn"],r["E3b_fp"]+"/"+r["E3b_fn"],r["E2_errors"]+"→"+r["E3b_errors"]] for r in ff]))
 text.append("\n重入fold8：BF1 67.5236→67.6370，仅纠正buggy_42.sol的一项漏报；buggy_18.sol的275错误和buggy_36.sol的58错误均未变。访问控制fold7：79.1252→80.0805，减少6个其他文件的误报；buggy_18.sol的94个误报仍未变。现象支持“主要困难尚未解决”，不等同于证明标签错误。冻结作者标签保持原样，之前的标注上下文问题不能凭本次训练宣布已解决。\n\n重入提升fold1/2/4/5/8/9，持平7，下降0/3/6；访问控制提升0/4/6/7，持平1/2/5/9，下降3/8。重入最大BF1增量在fold9(+0.8439pp)，访问控制最大增量在fold7(+0.9552pp)。提升不只发生在一个fold，但并非一致提升，也未修复主要困难文件。\n\n见[file_error_analysis.csv](file_error_analysis.csv)、[error_changes.csv](error_changes.csv)、[prediction_change_summary.csv](prediction_change_summary.csv)。\n")
 text.append("\n## 8. 新关系覆盖、训练支持与梯度\n\nE2/E3b节点集合、原节点属性/标签/token摘要一致，原CFG/CG边保留，只加入既定正向关系。下表的total是完整固定图边数，范围是各折train/val文件内结构支持量；不是语义正确率，也不是实际纠错数。\n")
 data=[]
 for task in names:
  for rel in ("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
   rr=[r for r in support if r["task_id"]==task and r["variant"]=="E3b" and r["relation"]==rel]
   train=[int(r["train"]) for r in rr];val=[int(r["val"]) for r in rr];totals={t+v for t,v in zip(train,val)};assert len(totals)==1
   data.append([names[task],rel,totals.pop(),str(min(train))+"–"+str(max(train)),str(min(val))+"–"+str(max(val)),sum(t==0 for t in train),sum(v==0 for v in val)])
 text.append(table(["任务","关系","total","train范围","val范围","train=0折数","val=0折数"],data))
 text.append("\n访问控制没有CALL→WRITE关系，未人为注册空关系。全60模型共1120个增强canonical审计记录（含原DATA_DEF_USE）；1091个有训练支持者均有过非零有限梯度，29个无训练支持者无梯度并独立保留。没有把只有val支持的关系当成接入故障，也没有在评分时创建随机参数。关系attention/priority梯度为0不自动等于断梯度，例如单入边softmax；本次逐bank原值均保留。参数更新可能含weight decay，所以梯度历史与参数更新分开记录。\n\n这证明新关系进入实际前向/训练计算，不能证明新增边语义均正确或全部收益来自数据依赖语义。沿用Stage G有限Oracle审查：17条状态Def–Use中12条在构造器、5条在定价函数，远未覆盖通用权限guard/modifier或跨调用状态。当前无独立人工批准、无新solc编译验证；本轮没有扩大语义范围。原HGT跨canonical聚合方式和新增参数也会改变共享参数训练，H1不能分离Def–Use与顺序关系贡献，需H2完整消融。\n\n见[enhancement_support.csv](enhancement_support.csv)、[canonical_support.csv](canonical_support.csv)、[gradient_support_detail.csv](gradient_support_detail.csv)。\n")
 text.append("\n## 9. 与原E0/E1基线比较\n\n下表是best等权折均值，单元格BF1/MF1。原Stage C E0/E1全60模型收据、数值配置、同折身份与标签均已复核。旧初始化semantic-paired-native-xavier-v1与本批state-forward/triple-chain不同，未证明跨批共同张量相同；因此这是历史同折参考，不能将差值认定为严格成对DDG因果增量，也不能用论文原数字替代本地E0。\n")
 data=[]
 for task in names:
  cells=[]
  for v in ("E0","E1","E2","E3b"):
   r=next(r for r in (baseline if v in ("E0","E1") else stats) if r["task_id"]==task and r["variant"]==v and (v not in ("E0","E1") or r["checkpoint"]=="best"))
   cells.append(num(r["buggy_f1_mean"])+" / "+num(r["macro_f1_mean"]))
  data.append([names[task]]+cells)
 text.append(table(["任务","E0 历史","E1 历史","E2 本批","E3b 本批"],data))
 text.append("\n访问控制合约的E2/E3b低于历史E0/E1约1.9962pp BF1，必须如实保留；不能宣称所有任务均超过原基线。详见baseline_statistics.csv、baseline_folds.csv、historical_baseline_deltas.csv、baseline_comparison_audit.json。\n")
 text.append("\n## 10. 参数量、显存、耗时和停止轮数\n\nRTX3050 Laptop 4GiB，单GPU worker串行。表内含复用fold0，逐折资源与best/last轮次见resource_folds.csv；这里只汇总每任务/变体。\n")
 text.append(table(["任务","模型","参数量","训练轮范围","平均秒","总秒(含复用)","峰值allocated/reserved GiB","最小整卡free MiB"],
  [[names[r["task_id"]],r["variant"],r["parameters"][0],str(r["epochs_min"])+"–"+str(r["epochs_max"]),num(r["fit_seconds_mean"]),num(r["fit_seconds_sum"]),num(r["peak_allocated_gib"])+" / "+num(r["peak_reserved_gib"]),r["min_card_free_mib"]] for r in a["resource_summary"]]))
 text.append("\n52个新fit记录的monotonic耗时合计 "+num(a["new_fit_seconds"])+" 秒；串行控制器10564.2432秒（约2.93小时），包括输入校验、进程启动、保存/重载及任务验收。\n\n首个新增重入合约fold1/E2耗时656.4475秒，曾遇Windows GPU资源竞争，采样整卡free低至14MiB。GameViewerServer专用显存分配计数约916MiB，用户表示自行关闭；随后运行速度恢复，但未独立确认进程已退出。没有替用户关闭程序、重启该fit或改参数。不同停止轮数及系统竞争条件使耗时不可作为纯算法速度比较，不能根据E3b在某任务更快声称计算效率提升。Windows分配计数不能直接相加解释物理驻留显存。\n")
 text.append("\n## 11. 实施、测试与完整性验收\n\n本轮实际新增e23_cv旁路调度/初始化/封存/验收/统计和16项回归测试；旧e23_pilot、DDG/state、HGT、tokenizer、训练脚本均未改。另在本批产物目录增加只读analyze_h1_results.py、render_h1_report.py、verify_protected_after.py作交付分析，不进入模型运行版本。两工作树已有training_changes_2026-10-07.md及HANDOVER仅追加，注明Codex。\n\n607个不同测试通过，0失败、0跳过：开发原回归480、原入口110、新H1测试16、原工作树资源测试1；选择性deselect的一项在原工作树补跑。封存前H1的16项再检查也通过，不重复计数。警告仅既有DGL/TensorBoard distutils与NetworkX弃用，无依赖升级。\n\n测试命令：\n\n```bash\npython -B -m pytest -q -p no:cacheprovider scripts/DFG/state scripts/DFG/tests scripts/DFG/experiments/tests tests -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'\npython -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/e23_pilot\npython -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/e23_cv/tests\n# 以下一项在原ge-sc-llm目录执行：\npython -B -m pytest -q -p no:cacheprovider scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs\n```\n\n最终control verify：new_complete=52、stage_g_reused=8、total_complete=expected_total=60。全部best/last重载输出一致，未在训练/评分创建参数；每折图/标签/特征/关系schema/折/初始化/配置/checkpoint绑定通过。summary独立重新计算120组best/last指标，历史基线另验收，pooled OOF覆盖/去重通过。最终旧资产14253项与7个完整旧目录的检查见protected_after.json；详细文档追加证据见documentation_phase2.json。\n\n日志：integration_tests.json、original_resource_test.json、final_verification.log、summary_execution.log、driver_execution.json。没有H2新拟合、其他seed、七类全量、narrow/nested实验、solc下载或新语义扩展。\n")
 text.append("\n## 12. 后续判断与停止位置\n\n1. **是否稳定改善？** 合约无收益；两个节点任务best平均小幅改善，但有下降折、明显折间差异及last退化，不能称稳定普遍提升或显著泛化提升。\n2. **受益与下降？** 见完整逐折表。多数容易折已接近满分；重入fold8与访问控制fold7略有改善，但buggy_18的主要错误未解决。\n3. **关系支持？** 有支持关系确实参与训练；状态Def–Use非常稀疏，访问控制无调用→写入，不能代表完整状态/权限语义。\n4. **概率还是类别？** 合约best仅概率改变；节点以概率改变为主，重入48个、访问控制16个节点改变类别，净少14/10错误。\n5. **是否值得H2？** 若目标是完整的研究消融，值得按已冻结全26次补齐，以区分Def–Use增量和两类顺序关系联合增量；目的应是解释有限收益与退化，不能预设它会提高分数。本轮只保留H2_EXECUTION_PLAN.md及全部E3a初值，不执行。若资源受限，应明确称消融未完成。\n6. **是否可扩七类？** 接口、schema、复用和执行链已有技术基础，但本结果不构成七类有效性的证据。应先审查H1困难文件和语义覆盖、完成H2后再决定预注册的新实验；不自动启动扩展。\n\n剩余限制：单seed、同val选模与评分、文件划分未消除既有模板相似性、冻结作者标签的历史上下文仍有疑点、有限标量/状态范围与保守回退、缺少独立人工/编译语义认证。本轮训练无新的执行正确性阻断，不能据测试通过宣称完整Solidity DDG。\n")
 text.append("\n## 13. 可运行的只读验收命令\n\n```bash\nconda activate mando\ncd /home/zhao/SmartContract/ge-sc-llm-ddg-v11\nexport PYTHONPATH=/home/zhao/SmartContract/ge-sc-llm-ddg-v11\nexport TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64\nexport PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2\npython -B -m scripts.DFG.experiments.e23_cv.control verify\npython -B -m scripts.DFG.experiments.e23_cv.control summarize\npython -B scripts/DFG/experiments/artifacts/paper_kfold/stage_h1_v1/analyze_h1_results.py\n```\n\nverify/summarize不启动训练；成功结果重复验收不覆盖不同内容。后续若提交归档导致HEAD改变，不能修改旧seal绕过身份检查，应单独设计只读归档验收。\n")
 content="\n".join(text)
 f=P/"H1_RESULT_REPORT.md"
 if f.exists() and f.read_text()!=content:raise ValueError("Refuse differing report")
 if not f.exists():f.write_text(content,encoding="utf8")
 print("Rendered",f,len(content),"characters")
if __name__=="__main__":main()
