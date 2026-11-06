"""Append NS-P6 docs after sealed reporting completes; never trains."""
from pathlib import Path
from collections import defaultdict
import json,csv,hashlib
ROOT=Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")
R=ROOT/"scripts/node_sem/artifacts/batch_NB_v1"
def read(p):return json.loads(Path(p).read_text(encoding="utf8"))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(encoding="utf8") as f:return list(csv.DictReader(f))
report=read(R/"reports/report.json")
assert report["passed"] and report["combined_fits"]==360
assert read(R/"diagnostics/complete.json")["count"]==90
assert read(R/"completion_status.json")["state"]=="analysis_complete_pending_documentation"
tasks=["reentrancy_contract","access_control_contract","reentrancy_node","access_control_node"]
cn=dict(zip(tasks,["重入合约","访问控制合约","重入节点","访问控制节点"]))
configs=["G3R/S2","G3R/S3","G3R/S4","G3R/S4g","G3R/S4m","G0/S4-noG"]
agg={(v["task_id"],v["profile"],v["checkpoint"],v["metric"]):v for v in report["aggregates"]}
lines=["\n\n## 2026-11-05 NS-P6 正式执行与汇报完成（Codex）","",
"本节为准备报告之后的完成记录，原记录保留。用户后续已明确授权训练；本轮“完成汇报”没有新增fit。N-B120/120正式结果验收，按封存收据引用N-A240个历史结果，共360个正式结果、720组best/last指标。另完成90次只读best前向，其中30次提供S4g门控，没有参数更新。",
"",
"### 1. 协议与配置","",
"主视图original，L-audit标签，8D固定分组折，seed=1。合约5折、节点10折；inner_train更新参数，inner_val早停并以严格最低loss选best，outer_test仅在训练结束评分。这里是完整图传导式grouped outer evaluation，不是早期paper_kfold的同一验证集评分，也不是独立外部测试。节点指标按HCG节点计算。Adam/OneCycle、各任务实际学习率、最多50轮、patience7/delta0.001和默认TF32保持；best为主、last单列。",
"",
"S2=CODE；S3=CODE+CTX；S4=CODE+CTX+STATIC拼接融合；S4g为门控融合；S4m仅遮蔽CTX名称，CODE原名保留；S4-noG使用G0且0层，但保留DFG派生CTX/STATIC。STATIC为冻结245维。S4-noG不是完全无依赖信息基线。",
"",
"### 2. best折均Buggy-F1（%，±样本标准差）","",
"|任务|S2|S3|S4|S4g|S4m|S4-noG|","|---|---:|---:|---:|---:|---:|---:|"]
for t in tasks:
    cells=[agg[(t,c,"best","buggy_f1")] for c in configs]
    lines.append("|"+cn[t]+"|"+"|".join("{:.4f} ± {:.4f}".format(v["mean"],v["sample_sd"]) for v in cells)+"|")
lines+=["","逐折BF1/Macro-F1/Precision/Recall及混淆矩阵见reports/fold_counts.csv；全部G0对照也保留。等权折均与pooled OOF另表，不混用。","",
"### 3. 配对差值：best/last分开","",
"|任务|左减右|best均差pp|升/平/降|last均差pp|","|---|---|---:|---|---:|"]
pairs=[("G3R/S3","G3R/S2"),("G3R/S4","G3R/S3"),("G3R/S4g","G3R/S4"),("G3R/S4","G3R/S4m"),("G3R/S4","G0/S4-noG")]
for t in tasks:
    for a,b in pairs:
        values=[next(x for x in report["paired"] if x["task_id"]==t and x["left"]==a and x["right"]==b and x["checkpoint"]==ck and x["metric"]=="buggy_f1") for ck in ("best","last")]
        v,last=values
        lines.append("|{}|{}−{}|{:+.5f}|{}/{}/{}|{:+.5f}|".format(cn[t],a,b,v["mean_delta_pp"],v["improved"],v["tied"],v["declined"],last["mean_delta_pp"]))
lines+=["","N-B全部只作描述，不做显著性检验或Holm。S3−S2整体保留历史登记身份，r19新增分层/逐节点分析为事后，只计算一次。折间SD不是独立seed方差。","",
"### 4. 非SolidiFI节点子集","",
"|任务|配置|TP|FP|FN|pooled BF1 %|","|---|---|---:|---:|---:|---:|"]
for t in tasks:
    if not t.endswith("_node"):continue
    for c in configs:
        v=next(x for x in report["pooled_oof"] if x["task_id"]==t and x["profile"]==c and x["checkpoint"]=="best" and x["cohort"]=="nonSolidiFI")
        lines.append("|{}|{}|{}|{}|{}|{:.4f}|".format(cn[t],c,v["tp"],v["fp"],v["fn"],v["buggy_f1"]))
lines+=["","固定正例重入32、访问控制20个按task/fold/file/source SHA/node身份对齐，概率见nonSolidifi_positive_nodes.csv；误报也单列。这些是正例节点数，不是独立漏洞数。Wilson仅P/R，BF1只报点估计；L-audit不宣称金标准。","",
"### 5. 门控和注意力","",
"90/90 G3R best只读前向、0 optimizer step、权重摘要前后相同。S4g30个模型按节点类型和模态统计可用行均值、标准差、分位数及权重≥0.9比例；不把缺失行混入均值。S2没有可学习门控，不编造CODE门控值；S4-noG没有注意力，标为不适用。",
"",
"|任务|CODE平均权重|CTX平均权重|STATIC平均权重|CODE≥0.9占比|","|---|---:|---:|---:|---:|"]
gates=rows(R/"reports/gates.csv");gate_summary=[]
for t in tasks:
    values={}
    for m in ["code","ctx","static"]:
        z=[x for x in gates if x["job_id"].startswith(t+"__") and x["modality"]==m]
        n=sum(int(x["available_rows"]) for x in z)
        avg=sum(float(x["mean"])*int(x["available_rows"]) for x in z if x["mean"] not in ("","None"))/n if n else None
        frac=sum(float(x["fraction_ge_0_9"])*int(x["available_rows"]) for x in z if x["fraction_ge_0_9"] not in ("","None"))/n if n else None
        values[m]=dict(available_node_model_observations=n,mean=avg,fraction_ge_0_9=frac)
    gate_summary.append(dict(task=t,modalities=values))
    lines.append("|{}|{:.4f}|{:.4f}|{:.4f}|{:.2%}|".format(cn[t],values["code"]["mean"],values["ctx"]["mean"],values["static"]["mean"],values["code"]["fraction_ge_0_9"]))
lines+=["","以上为可用节点×模型观测加权汇总，同一节点在不同折模型重复出现，不作为独立样本。逐类型分布见gates.csv。注意力沿用已验证的首层观察器，单邻居权重1是结构结果，多邻居目标单列；门控/注意力不等于因果贡献。","",
"### 6. 完整性、恢复与复现限制","",
"N-B120份成功收据与全部产物SHA通过，240个best/last文件当前可验证；训练期checkpoint重载/预测一致性通过。诊断加载前核对best SHA，再核对state digest和binding。原plan/seal、图、特征、标签、折、初值和训练代码不改。",
"",
"唯一正式失败：访问控制节点S4m fold8 attempt_001的显存采样读数失败（15轮记录，cuda_oom=false），不是OOM、数值错误或指标下降。用户独立授权“从中断启动后面的”，manual_resume_20261105_v1封存授权；attempt_002从同一零步初值重跑，之前115项成功复用，失败现场保留。恢复worker计算主体AST与原worker相同，不称新seed或epoch续训。",
"",
"本轮额外深验N-A当前checkpoint失败：240个best与240个last均不在原路径，原因未查明。N-A收据、预测、配置、资源及全部非checkpoint产物SHA通过，按NS-P6的receipt SHA历史引用要求独立复算指标；不能声称现在可重载N-A。此前cleanup_NA_cpu_weights_20261105只删除12个非正式CPU权重，其结束记录曾确认正式480个权重仍在，不能据此认定本次缺失由该清理造成。本轮没有删除权重，也不重训补造。首次失败analysis_checks/audit.*保留，historical_weight_availability.json列明全部缺失引用。",
"",
"### 7. 实现、验证和命令","",
"新增nb_diagnostics.py（冻结观察器与门控）、nb_reporting.py（复用冻结指标和标签对齐）、nb_finalize.py（独立分析封存与串行调度）、tests/test_nb_analysis.py。训练核心和旧验收入口不改；analysis_revision.json单独绑定新分析源码。",
"",
"CPU回归：NodeSem961、DFGv2 2653、原DDG/graph_utils223，共3837通过，0失败/跳过、42条既有DGL/distutils与NetworkX弃用警告。36项定向包含于961，不重复累计。额外N-A权重审计失败单列，不把所有尝试写成零失败。8H load170项、354冻结源码与生效修订完全一致。",
"",
"在既有mando环境和共享上下文变量下实际执行（CPU测试带CUDA_VISIBLE_DEVICES=''）：",
"",
"    python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests/test_nb_analysis.py",
"    python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests",
"    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests",
"    python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py",
"    python -B -m scripts.node_sem.nb_finalize audit",
"    python -B -m scripts.node_sem.nb_finalize seal",
"    python -B -m scripts.node_sem.nb_finalize run",
"    python -B -m scripts.node_sem.nb_diagnostics --root scripts/node_sem/artifacts/batch_NB_v1 --verify",
"",
"已有seal/report拒绝覆盖，不应重跑audit/seal/build生成命令；verify只读核对已有诊断。PT/NPZ留WSL，不上传权重或写入C盘副本。",
"",
"### 8. 结论与停止位置","",
"CTX相对CODE当前收益很小且不稳定；加入STATIC后S4四任务best均低于S3，完整拼接没有超越强CODE基线的证据。门控也未一致改善。重入节点S4相对零层版提高1.5981pp、10折均升，说明当前配置需要图消息传递，但不能单独归因为新增DFG边。",
"",
"S4m两个节点任务微升、两个合约任务下降；CODE仍原名，不能写成全量匿名化更好或排除命名捷径。非SolidiFI访问控制仍大量漏检，总体99%不能遮盖。best/last方向有不一致，按预定best报告，不择优替换。",
"",
"边界：S2 modality_dropout=0而S3/S4=0.1；新增adapter种子含spec.digest，共同HGT/分类器相同不保证adapter跨配置相同。这是系统配置比较，不是纯语义因果消融。S4−S3仅回答已有CTX时STATIC的条件增量。保留此前inner_val选出的S2参考，不依据本批outer结果重新选型；下一阶段先明确必要机制证据，不机械新增更多配置。",
"",
"最终实验按用户安排将在显存充足服务器开展，当前RTX3050 4GiB仅本机限制；服务器尚未实测，另建批次且不混合择优。本轮不进入NS-P7、新seed、新关系或服务器训练。",""]
resource_summary={};resources=rows(R/"reports/resources.csv")
nb=[x for x in resources if x["name"] in ("S3","S4g","S4m","S4-noG")]
assert len(nb)==120
lines+=["","### 9. 正式运行资源","",
"|任务|fit数|拟合小时|进程累计小时|峰值allocated MiB|峰值reserved MiB|整卡最低free MiB|","|---|---:|---:|---:|---:|---:|---:|"]
for t in tasks:
 z=[x for x in nb if x["task_id"]==t]
 v=dict(fits=len(z),fit_hours=sum(float(x["fit_seconds"]) for x in z)/3600,
     pipeline_hours=sum(float(x["total_seconds"]) for x in z)/3600,
     peak_allocated_mib=max(float(x["peak_allocated_mib"]) for x in z),
     peak_reserved_mib=max(float(x["peak_reserved_mib"]) for x in z),
     minimum_free_mib=min(float(x["minimum_free_mib"]) for x in z))
 resource_summary[t]=v
 lines.append("|{}|{}|{:.3f}|{:.3f}|{:.1f}|{:.1f}|{:.1f}|".format(cn[t],v["fits"],v["fit_hours"],v["pipeline_hours"],v["peak_allocated_mib"],v["peak_reserved_mib"],v["minimum_free_mib"]))
lines+=["","仅统计120成功结果，失败attempt、准备、排队和90次诊断单列；累计进程时间不是自然墙钟训练时长。参数量/epoch逐折见resources.csv，支持与梯度见relation_support_gradients.json。",""]
lines+=["","### 10. 关系训练支持复核","",
"90个G3R模型的已有梯度日志中，按轮次×canonical relation计：134870条有训练支持且非零梯度，6516条没有训练支持，1730条有支持但当轮零梯度。全部梯度数值有限。这些是重复观测计数，不是独立关系/样本数；不把零梯度单项自动当作错误，也不把非零梯度当作有效性的证明。",
"",
"每折v2训练边（含既有正反关系）范围：重入合约21594–22650、访问控制合约14912–15942、重入节点16858–17664、访问控制节点10722–11586。已注册但无train支持的canonical关系保留；不删折、删边或评分时建参。完整逐折证据见analysis_checks/support_summary.json及reports/relation_support_gradients.json。",""]
lines+=["","### 11. 概率变化与离散错误变化","",
"访问控制合约S3−S2：114个样本的best概率全部改变，但离散预测0改变，所以F1逐折完全相同。重入合约该比较142个概率改变、4个分类改变（纠正2、新增错误2）。这不是重复使用同一预测文件。",
"",
"重入节点S3−S2：11806个概率改变，12个分类改变（纠正6、新增错误6）；访问控制节点7289个概率改变，13个分类改变（纠正7、新增错误6）。S4−S3的重入节点纠正6、新增错误14；访问控制节点纠正4、新增错误8。高分背景下少量节点就可改变差值方向。完整各文件/source SHA分布和其他比较见prediction_change_summary.csv、file_error_changes.csv和prediction_changes.jsonl。",""]
content="\n".join(lines)
summary="""

## 2026-11-05 NS-P6 N-B完成汇报（修改 AI：Codex）

N-B120/120正式结果验收，引用N-A240项，共360结果；新增90次只读best诊断（含30份S4g门控），本轮新增训练0。3837项回归通过，8H354冻结源码不变。详细结果、命令和限制见scripts/node_sem/NS_P6_REPORT.md及batch_NB_v1/reports/。

S3相对S2收益很小；S4相对S3四任务best均下降；门控不一致改善；重入节点S4相对零层版提高1.5981pp，10折均升。S4m节点微升、合约下降，不代表全量匿名更优。best/last、非SolidiFI子集单列，不按outer分数重新选型。保留dropout与adapter种子混杂边界，暂停扩展。

正式唯一失败为访问控制节点S4m fold8显存采样失败，经单独授权同初值重跑一次成功，旧attempt与115项前序成功保留。当前N-A480个正式best/last权重缺失、原因未查明；收据及非权重产物SHA通过，指标据封存预测复算，不能宣称当前可重载N-A。此前12个CPU测试权重清理记录不能解释此缺失。N-B240正式checkpoint核验通过。

原计划/输入/训练计算不改，新增分析单独封存。最终服务器显存充足安排保留，但另建批次、不混合本机结果；本轮不进入NS-P7或新训练，不自动push。
"""
paths={ROOT/"scripts/node_sem/NS_P6_REPORT.md":content,
 ROOT/"docs/training_changes_2026-10-07.md":"\n\n## 87. 2026-11-05 NS-P6执行验收和完整汇报（Codex）\n"+content,
 ROOT/"HANDOVER.md":summary,
 ROOT/"scripts/node_sem/PROGRESS.md":summary+"\n新增nb_finalize.py、nb_diagnostics.py、nb_reporting.py、tests/test_nb_analysis.py。额外历史权重审计失败后，按§5.9原有receipt SHA引用边界完成报告，未改变旧verify或伪造缺失文件；原失败保留。\n",
 ROOT/"scripts/node_sem/NS_P6_README.md":"\n\n## 2026-11-05执行完成后的复核\n\n后续已单独授权并完成120次训练与本轮只读诊断，上述准备期未授权叙述为历史状态。当前结果和限制以NS_P6_REPORT完成节为准。使用nb_diagnostics --verify核对90次诊断，不覆盖已有plan/seal/报告。N-A权重当前缺失，原p6_prepare verify深度核验可能失败，不宣称完整可重载。\n"}
manifest=[]
for path,text in paths.items():
 old=path.read_bytes()
 if text.encode("utf8") in old:raise ValueError("Already appended")
 with path.open("ab") as f:f.write(text.encode("utf8"))
 assert path.read_bytes()[:len(old)]==old
 manifest.append(dict(path=str(path),before_bytes=len(old),before_sha256=hashlib.sha256(old).hexdigest(),after_sha256=sha(path)))
(R/"documentation_append.json").write_text(json.dumps(dict(files=manifest,gate_summary=gate_summary,resource_summary=resource_summary),ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps(dict(gate_summary=gate_summary,resource_summary=resource_summary),ensure_ascii=False,indent=2))
