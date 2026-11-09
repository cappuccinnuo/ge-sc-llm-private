"""Render NS-P9 read-only synthesis. Sources and model computation remain frozen."""
import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
import networkx as nx
from .summary import ART, BASE, DEFAULT, Sources, read, write, reference, csv_write

TASKS=("reentrancy_contract","access_control_contract","reentrancy_node","access_control_node")
LABELS=dict(zip(TASKS,("重入合约","访问控制合约","重入节点","访问控制节点")))
CATEGORIES={"a":"标签位置/范围待审","b":"特定语义关系缺口","c":"相关输入存在、同类型正例少","d":"当前证据无法定位"}


def cell(row):
    return "{:.4f} ± {:.4f}".format(row["mean"],row["sample_sd"])


def copy_exclusive(src,dst):
    with Path(dst).open("xb")as f:f.write(Path(src).read_bytes())
    if reference(src)["sha256"]!=reference(dst)["sha256"]:raise ValueError("Copy differs")


def build(root=DEFAULT):
    root=Path(root);out=root/"reports";sources=Sources()
    for directory,complete_name in (("collection_attempt3","collect_complete.json"),
                                    ("edge_review","complete.json"),("cases_attempt2","complete.json")):
        completion=read(sources.root(root/directory/complete_name))
        if not completion["passed"]:raise ValueError("Source stage incomplete")
        sources.refs(completion["artifacts"])
    for source in sorted((root/"collection_attempt3/reports").iterdir()):
        copy_exclusive(source,out/source.name)
    for name in ("persistent_cases.json","removed_fp_cases.json","train_support.csv","removed_false_positives.csv"):
        copy_exclusive(root/"cases_attempt2"/name,out/name)
    for name in ("paths_and_labels.json","paths.csv"):
        copy_exclusive(root/"edge_review"/name,out/name)
    notes=read(sources.root(root/"case_review_notes.json"))
    cases=read(out/"persistent_cases.json");paths=read(out/"paths_and_labels.json")
    if set(notes)!={r["task_id"]+"/"+str(r["original_graph_node_id"])for r in cases}:
        raise ValueError("Missing case review")
    reviews=[]
    for c in cases:
        n=notes[c["task_id"]+"/"+str(c["original_graph_node_id"])]
        reviews.append(dict(task_id=c["task_id"],file=c["file"],source_sha256=c["source_sha256"],
            node_id=c["original_graph_node_id"],node_type=c["node_type"],
            function=c["alignment"]["function"],raw_lines=c["alignment"]["raw_lines"],
            graph_stored_lines=c["alignment"]["graph_stored_lines"],
            category=n["category"],category_label=CATEGORIES[n["category"]],
            evidence_review=n["note"],candidate=n["next"],
            support_counts=[x["positive_nodes"]for x in c["same_type_nonSolidiFI_inner_train"]],
            gold_label_claim=False,causal_claim=False))
    write(out/"reviewed_cases.json",reviews);csv_write(out/"reviewed_cases.csv",reviews)
    aggregates=read(out/"aggregates.json")
    lookup={(r["task_id"],r["profile"],r["checkpoint"],r["metric"]):r for r in aggregates}
    cohorts=read(out/"cohort_scores.json")
    resources=list(csv.DictReader((out/"resources.csv").open(encoding="utf8")))
    inference=read(out/"registered_inference.json")
    costs=read(out/"training_costs.json");prep_cost=read(out/"preprocessing_costs.json")
    idx=read(sources.root(ART/"batch_NC2_v1/local_artifact_index.json"))
    sources.check(next(r for r in idx["files"]if r["path"].endswith("/student_summary.json")))
    ncplan=read(sources.root(ART/"batch_NC2_v1/plan.json"))
    graph_checks=[]
    for task in TASKS[2:]:
        job=next(j for j in ncplan["jobs"]if j["task_id"]==task)
        graph=nx.read_gpickle(sources.check(job["graph"]))
        crossing=[(u,v)for u,v in graph.edges()if graph.nodes[u]["source_file"]!=graph.nodes[v]["source_file"]]
        if crossing:raise ValueError("Per-file paths omit inter-file edges")
        graph_checks.append(dict(task_id=task,graph=job["graph"],cross_file_edges=0))
    write(out/"graph_scope_checks.json",graph_checks)
    candidates=[]
    for n in ("S0o","S2","S4","S5","S6"):
        for t in TASKS:
            rr=[r for r in resources if r["task_id"]==t and r["name"]==n and r["graph"]=="G3R"]
            candidates.append(dict(name=n,task_id=t,graph="G3R",
                best_BF1=lookup[t,"G3R/"+n,"best","buggy_f1"]["mean"],
                best_sd=lookup[t,"G3R/"+n,"best","buggy_f1"]["sample_sd"],
                fit_seconds_mean=statistics.mean(float(r["fit_seconds"])for r in rr),
                fit_seconds_min=min(float(r["fit_seconds"])for r in rr),
                fit_seconds_max=max(float(r["fit_seconds"])for r in rr)))
    csv_write(out/"baseline_candidates.csv",candidates);write(out/"baseline_candidates.json",candidates)
    lines=[
      "# NodeSem 本机阶段汇总与持续漏报分析（NS-P9，Codex）","",
      "本轮完成只读汇总：N-A/N-B/N-C1/N-C2共450次已有正式拟合、900条best/last逐折记录，660条历史重复引用逐位一致；四项指标的等权折均值及样本标准差也与来源逐位一致。新增训练、模型eval、LLM调用、特征均为0。S3m未运行；S4-noG保留真实G0、零HGT层身份。","",
      "**当前证据支持保留多个基线候选，不支持把全部持续漏报归结为缺边。** 主终点为重入节点G3R、best、L-audit外层折BF1。S2相对S0o的原预登记Holm p=0.03906；S4相对S0o校正p=0.07422，S4相对S2没有改善；S5相对S4差+0.00814pp、校正p=0.64560。访问控制节点S5去掉10个非SolidiFI误报，却仍漏18/20个正例；S6识别5/20。报告不替用户决定下一基线。","",
      "S0o/S2/S4/S6/S5/S8均漏报：重入6个、访问控制15个HCG节点。这不等于21个独立漏洞实例；函数与语句节点、同一行可能覆盖同一漏洞位置。21例均沿用作者原标签，没有通过本轮确立新的金标准。","",
      "## 1. 范围、来源与协议","",
      "- 依据PROMPTS r29 §5.1/§5.12和EXPERIMENT_POLICY，起始HEAD a5702240；原名original主视图，匿名N-D取消。",
      "- 分组嵌套CV：inner_train训练，inner_val选best，outer_test仅评分。这里是CV外层留出折，不是外部独立测试集。节点按HCG节点、合约按文件计分。",
      "- 合约5折、节点10折、seed=1。四任务分开汇总；best是预定主结果，last辅助且不得择优替换。pooled OOF与等权折均值分表。",
      "- N-A 240、N-B 120、N-C1 30、N-C2 60个正式结果；NS-P6c/6c2/7c诊断只读引用。逐来源SHA见source_inventory.json及各阶段收据。",
      "- N-A的480份best/last权重此前由用户删除。本轮只引用封存预测/收据，未重载或补训，不能声称重新验收了这些已删除权重。",
      "- 用户批准S3m标为未运行、不补训不替代；S4-noG保留G0身份。后者HGT层数0，不同于N-A的G0/S4。","",
      "## 2. best主表：等权折均值 ± 样本标准差（%）","",
      "S0o=原512维token ID直接Linear；S1o=可训练token嵌入与池化；S2=CodeT5+ CODE；S3=CODE+CTX；S4=CODE+CTX+STATIC（本批封存245维）；S4g为门控融合；S4m为masked CTX，源码仍为原名；S6增加教师向量；S5增加折内学生向量；S8为同初值同训练随机起点的学生向量置换对照。"
    ]
    for t in TASKS:
        lines+=["","### "+LABELS[t],"","|图/配置|Buggy-F1|Macro-F1|Precision|Recall|","|---|---:|---:|---:|---:|"]
        for p in sorted({r["profile"]for r in aggregates if r["task_id"]==t}):
            lines.append("|"+p+"|"+"|".join(cell(lookup[t,p,"best",m])for m in ("buggy_f1","macro_f1","precision","recall"))+"|")
        lines.append("|G3R/S3m|未运行|未运行|未运行|未运行|")
    lines+=["","## 3. last辅助结果与原预登记统计","",
        "last完整四指标见last_fold_means.csv；下表为BF1。原标签辅助四指标单列orig_all_fold_metrics.json，不与L-audit混算。","",
        "|图/配置|重入合约|访问控制合约|重入节点|访问控制节点|","|---|---:|---:|---:|---:|"]
    for p in sorted({r["profile"]for r in aggregates}):
        lines.append("|"+p+"|"+"|".join(cell(lookup[t,p,"last","buggy_f1"])for t in TASKS)+"|")
    lines+=["","仅原样引用已有主终点检验，来源SciPy均为1.7.3。N-A四项与N-C2两项各自保留Holm家族；N-C1为单一预登记检验，不并入其他家族；N-B只有描述分析。本轮不计算新p值、不合并家族。","",
        "|批次|对照|折均差 pp|原p|Holm p|","|---|---|---:|---:|---:|"]
    for fam in inference:
        for r in fam["primary"]:
            name=r["profile"].split("/")[-1]+"-"+r["baseline"].split("/")[-1]
            adjusted=(fam["holm"]or{}).get("p_adjusted",{}).get(name)
            lines.append("|{}|{}|{:+.6f}|{:.8f}|{}|".format(fam["batch"],name,r["difference_mean_pp"],r["p_raw"],
                "{:.8f}".format(adjusted)if adjusted is not None else "单一检验"))
    lines+=["","折共享训练样本，标准差不是独立seed的方差；不把p值解释为纯语义贡献。访问控制上的事后改善不能替代预登记主终点。","",
        "## 4. 非SolidiFI逐节点表与错误变化","",
        "positive_nodes_best/last.csv包含重入32、访问控制20个正例×六配置的预测、概率、source SHA/source_id、HCG ID和fold，共104条宽表。与N-C1 104条、N-C2 312条既有配对记录逐身份和概率浮点值一致。","",
        "以下为pooled OOF，不是等权折均值，也不是外部独立测试。","",
        "|任务|配置|TP|FP|FN|BF1 %|","|---|---|---:|---:|---:|---:|"]
    for r in cohorts:
        if r["cohort"]=="nonSolidiFI"and r["checkpoint"]=="best":
            lines.append("|{}|{}|{}|{}|{}|{:.4f}|".format(LABELS[r["task_id"]],r["name"],r["tp"],r["fp"],r["fn"],r["buggy_f1"]))
    lines+=["","S5相对S4去掉的10个访问控制误报如下。纠错相对于冻结标签，不等于重新人工证明这些语句绝对安全。","",
        "|文件 / HCG ID|函数|原源码行|节点类型|S4概率→S5概率|","|---|---|---|---|---|"]
    for r in read(out/"removed_fp_cases.json"):
        a=r["alignment"]
        lines.append("|{} / {}|{}|{}|{}|{:.6f}→{:.6f}|".format(r["file"],r["original_graph_node_id"],
            (a["function"]or"无").replace("\n"," "),a["raw_lines"],r["node_type"],r["S4_probability"],r["S5_probability"]))
    lines+=["","## 5. 持续漏报逐例证据","",
        "源码行来自冻结ProjectionView+Projector的精确AST身份映射，raw_lines与作者图预处理后的graph_stored_lines分别保存。G3R消息方向通过冻结materialize检查，REV_*不能当反向执行依赖。两份完整图的跨文件边均为0，因此逐文件路径未遗漏经其他文件的连接。",
        "路径存在不保证执行可行、授权保护或被模型利用；路径大于2跳也不证明完全无相关信息，CODE/CTX或共享声明可能提供其他线索。以下四类仅为附证据的初步判断，多因素可并存。",
        "标签链为8G source_preparation→8C node_label_audit/node_views→8D label_views。21例均非SolidiFI，rule_target=null、C1=orig=1、C2_include=true。这是标签来源核验，不是漏洞真值复核。",""]
    pathmap={(r["task_id"],r["node_id"]):r for r in paths}
    for c,r in zip(cases,reviews):
        a=c["alignment"];f=c["facts"]
        lines+=["### {}：{} / {}".format(LABELS[c["task_id"]],c["file"],c["original_graph_node_id"]),"",
            "源码SHA："+c["source_sha256"]+"。类型："+c["node_type"]+"。函数："+(a["function"]or"无").replace("\n"," ")+"。",
            "原源码行{}；图坐标{}；orig={}，L-audit={}。".format(a["raw_lines"],a["graph_stored_lines"],c["frozen_label"]["orig"],c["frozen_label"]["L-audit_target"]),
            "初步分类({}){}：{}".format(r["category"],r["category_label"],r["evidence_review"]),
            "候选："+r["candidate"],
            "每折inner_train同类型非SolidiFI正例数（fold0–9）："+str(r["support_counts"])+"。这是节点类型计数，不是完全相同漏洞模式的样本量。",
            "STATIC/facts：external={}；state={}；order={}；guard_status={}；fn_summary={}。".format(
                json.dumps(f["external"],ensure_ascii=False),json.dumps(f["state"],ensure_ascii=False),
                json.dumps(f["order"],ensure_ascii=False),f["guard_status"],json.dumps(f["fn_summary"],ensure_ascii=False)),
            "全部激活STATIC位："+", ".join(c["static_active_bits"])+"。",""]
        for q in pathmap[c["task_id"],c["original_graph_node_id"]]["queries"]:
            lines.append("- {}（{}→{}）：原始正向{}；G3R消息路径{}，关系{}。".format(q["question"],q["source"],q["target"],
                str(q["raw_forward_hops"])+"跳"if q["raw_forward_hops"]is not None else"不可达",
                q["G3R_message_shortest_path"],q["message_path_relations"]))
        lines+=["","原语句/函数：","","    "+a["source_text"].replace("\n","\n    "),""]

    lines+=["分类计数："+json.dumps(dict(Counter(r["category"]for r in reviews)),ensure_ascii=False)+"。(c)不等于已证明小样本导致漏报，(b)不等于新增关系必然有效。","",
        "## 6. 既有诊断与解释边界","",
        "- NS-P6c只评估30个S4g，不用它替代已缺失权重的S4。移除CTX/STATIC会改变预测，说明对该干预敏感，不直接证明独立语义贡献。",
        "- NS-P6c2限定字段适用节点后，CODE能线性预测部分STATIC；CTX来自同套facts，CTX高可预测性属于编码保真度，不是独立新信息。低AUC也不证明CODE不含该信息。",
        "- NS-P7c教师仅用summary/函数意图，排除role。节点类型均值的余弦本身较高；教师重构残差可能包含信息、噪声和非线性部分，不能把不可重构成分全称为有效新语义。summary仍可能有错误。",
        "- HGT的S6/S5结果才回答教师/学生是否转化为检测收益。S5访问控制收益主要体现为误报下降，非SolidiFI漏报仍18/20；S6正例覆盖更高，但主终点没有显著改善。","",
        "## 7. 已有成本与资源","",
        "fit小时从来源resources.csv的fit_seconds求和；成功进程小时是收据total_seconds之和，含装配等开销。两列不能相加，不是GPU利用率积分，未计失败attempt、诊断和控制器等待。","",
        "|批次|正式拟合|fit小时|成功进程小时|最小整卡空闲MiB|峰值allocated/reserved MiB|","|---|---:|---:|---:|---:|---:|"]
    for r in costs:
        lines.append("|{}|{}|{:.4f}|{:.4f}|{:.0f}|{:.2f}/{:.0f}|".format(r["batch"],r["formal_fits"],r["gpu_fit_hours"],r["gpu_process_hours"],r["minimum_free_mib"],r["peak_allocated_mib"],r["peak_reserved_mib"]))
    lines+=["","LLM生成{:.2f}秒（{:.4f}小时），教师句向量编码{:.2f}秒；30个学生CPU拟合和诊断{:.2f}秒，后者不含大部分SHA/最终导出准备。S8复用S5学生。共享成本不按任务重复累加，原引用见preprocessing_costs.json。NS-P9 GPU运行为0。".format(
        prep_cost["LLM_generation_seconds"],prep_cost["LLM_generation_seconds"]/3600,prep_cost["teacher_encoding_seconds"],prep_cost["student_fit_diagnostic_seconds"]),"",
        "## 8. 下一阶段基线候选（由用户决定）","",
        "|候选|重入节点主终点BF1、已有检验|非SolidiFI 重入 / 访问控制 TP,FP,FN|依赖|平均fit秒（重入合约/访问控制合约/重入节点/访问控制节点）|","|---|---|---|---|---|"]
    decisions={
      "S0o":("参照，无自身检验","原tokenizer/512 token ID + HGT；不需要新增CODE/CTX/教师"),
      "S2":("对S0o Holm p=0.03906","CodeT5+ CODE + HGT"),
      "S4":("对S0o Holm p=0.07422；对S2 p=0.22127","CodeT5+ CODE/CTX + facts/STATIC + HGT"),
      "S5":("对S4 Holm p=0.64560；对S8 p=0.27368","S4 + 折内CPU学生；学生训练需要教师，部署不需在线LLM"),
      "S6":("对S4单一p=0.95925","S4 + LLM描述/BGE教师编码，可离线缓存")}
    for n,(stat,dependency)in decisions.items():
        co=[]
        for t in TASKS[2:]:
            r=next(r for r in cohorts if r["task_id"]==t and r["name"]==n and r["cohort"]=="nonSolidiFI"and r["checkpoint"]=="best")
            co.append("{},{},{}".format(r["tp"],r["fp"],r["fn"]))
        times=[next(r for r in candidates if r["name"]==n and r["task_id"]==t)["fit_seconds_mean"]for t in TASKS]
        lines.append("|{}|{:.4f}%；{}|{}|{}|{}|".format(n,lookup["reentrancy_node","G3R/"+n,"best","buggy_f1"]["mean"],stat,
            " / ".join(co),dependency," / ".join("{:.1f}".format(v)for v in times)))
    sizes=[]
    for j in ncplan["jobs"]:
        if j["task_id"]in TASKS[:2]and j["name"]=="S5":
            n=len(j["split"]["outer_test_files"]);sizes.append(dict(task_id=j["task_id"],fold=j["fold"],files=n,one_file_accuracy_pp=100.0/n))
    write(out/"contract_fold_sizes.json",sizes)
    lines+=["","完整候选四任务指标和时间范围见baseline_candidates.csv。不按当前最高分自动选择，也不把不同粒度合成总F1。","",
        "## 9. 局限与模板事实修正","",
        "- 单seed、本机RTX3050；fold标准差是描述统计，不是seed重复方差。当前分组嵌套CV与早期paper_kfold不同，不能直接用差值宣称超越论文。",
        "- SolidiFI占主导，但不能统一声称所有FN为0：本次六配置节点表中，S0o重入best/last各4个SolidiFI FN，S6重入last有2个，其余所列条件为0。完整分母见cohort_scores.csv。高总F1与真实案例低召回可以同时存在。",
        "- 重入合约142文件、每折28–29；访问控制114文件、每折22–23。单文件改变accuracy约100/n个百分点，不是BF1固定改变3.4个百分点。实际折大小见contract_fold_sizes.json。",
        "- 3B本地LLM描述与过滤无法保证全部语义正确；不可核验教师保留unverified。排除role不代表summary无同类错误。",
        "- L-audit不是金标准；图、标签、折、特征、初值及历史产物均不修改。保留每个争议节点，不删困难文件。",
        "- 原名是主视图；G3R中的REV_*用于消息流，不等于反向依赖。路径、语义正确性、可行执行与模型实际利用分别讨论。",
        "- **最终实验计划迁往具备充足显存的服务器；当前显存限制只是本地电脑条件。** 服务器实验另建批次，不与本机成绩混成配对结论。",
        "- 本轮停止于只读汇总；不增加seed、漏洞类别、独立测试或新的模型/边扩展。下一基线和研究方向由用户选择。","",
        "## 10. 验收与复现","",
        "900条指标及其来源聚合逐位一致；缺失/SHA不符拒绝；输出排他创建；逐正例表与N-C1/N-C2一致。21个持续漏报和10个误报的AST、STATIC、图路径及标签链可复核。冻结8H load只读通过，354份计算源码与runtime_resume_v2一致。",
        "开发期保留三处新汇总器接入失败：原标签辅助行附加字段、重复n字段、辅助环境节点row_key。只修正本轮汇总器，旧产物无修改；有效收集为collection_attempt3、案例采集为cases_attempt2。验证命令和结果见README与verification。没有把这些开发失败记为模型训练失败。",
        "机器入口：fold_metrics.json、aggregates.json、registered_inference.json、positive_nodes_best/last.csv、reviewed_cases.json、paths_and_labels.json、baseline_candidates.csv；所有统计都可追到来源SHA。"
    ]
    target=BASE/"NODESEM_REPORT.md"
    with target.open("x",encoding="utf8")as f:f.write("\n".join(lines)+"\n")
    write(out/"finalization_sources.json",list(sources.verified.values()))
    write(root/"report_complete.json",dict(passed=True,report=reference(target),fits=450,metric_rows=900,
        persistent_fn=21,removed_fp=10,new_training=0,new_model_evals=0,new_LLM_calls=0,
        sources=list(sources.verified.values()),
        artifacts=[reference(p)for p in sorted(out.iterdir())if p.is_file()]))
    return target

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",default=str(DEFAULT));print(build(p.parse_args().root))
