"""E-B reporting and frozen-schema synthesis, using the E-A/frozen scorers."""
from collections import defaultdict
from pathlib import Path
import statistics

import numpy as np
import torch
from scripts.DFG.dfg_v2.experiment import stats
from scripts.DFG.dfg_v2.diagnostics8c import scoring
from scripts.DFG.dfg_v2.benchmark_v2 import execution as h8
from . import execution as ex, RELATION_FAMILY
from .io import ROOT, ref, read, write, checked
from .analysis_ea import (score, csv_table, preparation_index, align_predictions,
                         relative_error_reduction, metadata)

PROFILES=("G4R-A","G4R-Api","G3R-TA")
BASELINES=("G3R","G3R-T","G4R")
CONTRASTS=(("G4R-A","G4R"),("G4R-A","G4R-Api"),("G3R-TA","G3R-T"))
EA=ROOT/"scripts/edge_sem/artifacts/ep8_v1"


def sealed_summary(root):
    path=Path(root)/"results/summary.json"
    if read(path.with_suffix(".seal.json")).get("summary")!=ref(path):
        raise ValueError("Analysis summary seal mismatch")
    value=read(path)
    if value.get("passed") is not True:raise ValueError("Analysis is not accepted")
    for item in value["tables"].values():checked(item)
    return path,value


def h2_family(paired, ea_summary):
    hypotheses={}
    for view in ("original","anonymous"):
        components=[r for r in paired if r["view"]==view and r["task_id"]=="reentrancy_node"
                    and r["checkpoint"]=="best" and r["metric"]=="buggy_f1"
                    and (r["profile"],r["baseline"]) in CONTRASTS[:2]]
        if len(components)!=2 or {(r["profile"],r["baseline"]) for r in components}!=set(CONTRASTS[:2]):
            raise ValueError("H2 requires both unique preregistered components")
        hypotheses[view]=dict(H2_raw_p=max(r["p_raw"] for r in components),
            both_mean_differences_positive=all(r["difference_mean_pp"]>0 for r in components),
            components=components,role="primary" if view=="original" else "descriptive_outside_Holm")
    raw={"H1":ea_summary["hypotheses"]["original"]["H1_raw_p"],
         "H2":hypotheses["original"]["H2_raw_p"]}
    adjustment=stats.holm_adjust(raw,expected_profiles=("H1","H2"))
    positives={"H1":ea_summary["hypotheses"]["original"]["both_mean_differences_positive"],
               "H2":hypotheses["original"]["both_mean_differences_positive"]}
    adjustment["alpha"]=.05
    adjustment["positive_means"]=positives
    adjustment["supported"]={h:positives[h] and adjustment["p_adjusted"][h]<.05 for h in raw}
    adjustment["anonymous_in_family"]=False
    return hypotheses,adjustment


def compare_profiles(records, inventory, view, task, labels):
    paired=[];errors=[];changes=[]
    for checkpoint in ("best","last"):
        for current,baseline in CONTRASTS:
            for metric in stats.METRICS:
                row=stats.paired_comparison(records,task,current,baseline,checkpoint,metric)
                row.update(view=view,analysis_role="primary" if view=="original" else "sensitivity",
                    confirmatory_component=(view=="original" and task=="reentrancy_node"
                        and checkpoint=="best" and metric=="buggy_f1" and (current,baseline) in CONTRASTS[:2]))
                paired.append(row)
            for fold in range(10):
                new=scoring.index_rows(inventory[current][fold])
                old=scoring.index_rows(inventory[baseline][fold])
                if set(new)!=set(old):raise ValueError("Paired populations differ")
                corrections=introductions=0;deltas=[]
                for key in sorted(new,key=repr):
                    a,b=new[key],old[key]
                    if a["target"]!=b["target"]:raise ValueError("Paired truth differs")
                    deltas.append(a[checkpoint+"_positive_probability"]-b[checkpoint+"_positive_probability"])
                    if a[checkpoint]==b[checkpoint]:continue
                    good=a[checkpoint]==a["target"]
                    corrections+=int(good);introductions+=int(not good)
                    label=labels[key]
                    changes.append(dict(view=view,task_id=task,fold=fold,checkpoint=checkpoint,
                        profile=current,baseline=baseline,file=key[0],original_graph_node_id=key[1],
                        source_sha256=label["source_sha256"],source_id=label["source_id"],
                        cohort="SolidiFI" if label["solidifi"] else "nonSolidiFI",
                        target=a["target"],previous=b[checkpoint],current=a[checkpoint],corrected=good,
                        previous_probability=b[checkpoint+"_positive_probability"],
                        current_probability=a[checkpoint+"_positive_probability"]))
                nc,bc=score(new.values(),checkpoint),score(old.values(),checkpoint)
                errors.append(dict(view=view,task_id=task,profile=current,baseline=baseline,fold=fold,
                    checkpoint=checkpoint,baseline_errors=bc["errors"],errors=nc["errors"],
                    corrected=corrections,introduced=introductions,
                    relative_error_reduction_pct=relative_error_reduction(bc["errors"],nc["errors"]),
                    mean_probability_change=statistics.mean(deltas),
                    mean_absolute_probability_change=statistics.mean(abs(x) for x in deltas),
                    max_absolute_probability_change=max(abs(x) for x in deltas)))
    return paired,errors,changes


def distribution(values):
    x=np.asarray(values,dtype=np.float64).reshape(-1)
    if x.size==0:return dict(n=0,mean=None,sd=None,min=None,q05=None,median=None,q95=None,max=None)
    if not np.isfinite(x).all():raise ValueError("Nonfinite attention bias")
    return dict(n=int(x.size),mean=float(x.mean()),sd=float(x.std(ddof=1)) if x.size>1 else 0.,
        min=float(x.min()),q05=float(np.quantile(x,.05)),median=float(np.median(x)),
        q95=float(np.quantile(x,.95)),max=float(x.max()))


def mechanism(model, predictions):
    """Best-checkpoint eval bias; only scored outer-test destination nodes.

    Values are one per incoming edge and head, grouped by layer/family/label.
    Edge encoding is computed once; no graph label participates in encoding.
    """
    model.eval()
    labels=scoring.index_rows(predictions)
    graph=model.symmetrical_global_graph
    by_type={}
    observed=set()
    for typ,global_rows in model.node_ids_dict.items():
        target=torch.full((len(global_rows),),-1,dtype=torch.long)
        for local,global_row in enumerate(global_rows):
            node=model.nx_graph.nodes[global_row]
            key=(node["source_file"],model.original_graph_node_ids[global_row])
            if key in labels:
                if labels[key]["node_type"]!=typ:raise ValueError("Mechanism destination type mismatch")
                target[local]=labels[key]["target"];observed.add(key)
        by_type[typ]=target
    if observed!=set(labels):raise ValueError("Mechanism missed scored destinations")
    norms=[];buckets=defaultdict(list);edge_counts=defaultdict(int)
    with torch.no_grad():
        psi=model.edge_embeddings()
        for layer_index,layer in enumerate(model.gcs):
            for canonical,index in sorted(layer.edge_dict.items()):
                norms.append(dict(layer=layer_index,kind="u",canonical=list(canonical),
                    family=RELATION_FAMILY[canonical[1]],frobenius_norm=float(torch.norm(layer.u[index]))))
                _,dst=graph.edges(etype=canonical,order="eid")
                truth=by_type[canonical[2]][dst.cpu()]
                bias=(psi[canonical] @ layer.u[index]).cpu().numpy()
                for target in (0,1):
                    mask=truth.numpy()==target
                    for head in range(layer.n_heads):
                        key=(layer_index,RELATION_FAMILY[canonical[1]],target,head)
                        buckets[key].append(bias[mask,head])
                        edge_counts[key]+=int(mask.sum())
            for family,value in sorted(layer.U.items()):
                norms.append(dict(layer=layer_index,kind="U",canonical=None,
                    family=family,frobenius_norm=float(torch.norm(value))))
    summaries=[]
    for (layer,family,target,head),parts in sorted(buckets.items()):
        values=np.concatenate(parts)
        summaries.append(dict(layer=layer,family=family,target=target,head=head,
            edge_count=edge_counts[(layer,family,target,head)],**distribution(values)))
    return dict(norms=norms,bias=summaries,destinations=len(observed),checkpoint="best",
                eval_mode=True,statistical_test=False,unit="incoming edge per head; nodes/edges not independent")


def mechanism_one(plan,job,attempt,predictions):
    receipt=read(Path(attempt)/"receipt.json")
    reference=dict(path=str(Path(attempt)/"best.pt"),sha256=receipt["artifacts"]["best.pt"])
    payload=ex.load_checked(reference)
    if payload["binding"]["edge_profile"]!=job["edge_profile"]:
        raise ValueError("Mechanism checkpoint profile mismatch")
    from scripts.DFG.experiments.common import tensor_digest
    if tensor_digest(payload["state_dict"])!=payload["state_sha256"]:
        raise ValueError("Mechanism checkpoint tensor hash mismatch")
    model=ex.construct(plan,job)
    model.load_state_dict(payload["state_dict"],strict=True)
    if tensor_digest(model.state_dict())!=payload["state_sha256"]:
        raise ValueError("Mechanism strict checkpoint reload mismatch")
    result=mechanism(model,predictions)
    result.update(best=reference,state_sha256=payload["state_sha256"])
    del model,payload
    import gc
    gc.collect()
    return result


def side_by_side(paired):
    lookup={(r["view"],r["task_id"],r["profile"],r["baseline"],r["checkpoint"],r["metric"]):r for r in paired}
    if len(lookup)!=len(paired):raise ValueError("Duplicate comparisons")
    rows=[]
    for r in paired:
        if r["view"]!="original":continue
        key=(r["task_id"],r["profile"],r["baseline"],r["checkpoint"],r["metric"])
        b=lookup[("anonymous",)+key]
        rows.append(dict(task_id=key[0],profile=key[1],baseline=key[2],checkpoint=key[3],metric=key[4],
            original_difference_pp=r["difference_mean_pp"],anonymous_difference_pp=b["difference_mean_pp"],
            original_p_raw=r["p_raw"],anonymous_p_raw=b["p_raw"],
            original_tied_folds=r["tied"],anonymous_tied_folds=b["tied"],
            anonymous_role="descriptive_sensitivity_outside_Holm"))
    return rows


def summarize(root,output):
    root=Path(root);output=Path(output)
    if output.exists():raise FileExistsError("Analysis output already exists")
    ea_path,ea=sealed_summary(EA)
    index_path,index=preparation_index(root)
    reg=read(checked(index["registration"]))
    if ref(ea_path)!=reg["H1_source"] or ea["hypotheses"]["original"]["H1_raw_p"]!=reg["H1_raw_p"]:
        raise ValueError("Sealed H1 source/value changed")
    source=h8.load(checked(index["source_h8_plan"]))
    old_tables={name:read(checked(r)) for name,r in ea["tables"].items()}
    inventory={v:{t:{p:{} for p in BASELINES+PROFILES} for t in ex.TASKS} for v in ("original","anonymous")}
    tables={name:[] for name in ("folds","pooled","fold_means","paired","error_changes","changed_nodes",
        "non_solidifi_nodes","persistent_cases","resources","relation_support","parameter_norms","attention_bias")}
    # Rule inputs and scored populations are frozen. Preserve the already
    # independently scored E-A rule tables instead of reimplementing the rules.
    tables["rule_baselines"]=old_tables["rule_baselines"]
    accepted=[]
    for view,role in (("original","primary"),("anonymous","sensitivity")):
        paths=[checked(r) for r in reg["baseline_plans"][view]]+[root/role/"plan.json"]
        for path in paths:
            plan=ex.load(path,mode="verify")
            if ex.selected_view(plan)!=view:raise ValueError("Mixed result views")
            for job in plan["jobs"]:
                profile=job["edge_profile"]
                if profile not in BASELINES+PROFILES:continue
                task,fold=job["task_id"],job["fold"]
                if fold in inventory[view][task][profile]:raise ValueError("Duplicate fit")
                verified=ex.verify_one(path,plan,job);attempt=Path(verified["attempt"])
                predictions=read(attempt/"outer_test_predictions.json")
                inventory[view][task][profile][fold]=predictions
                tag=dict(view=view,task_id=task,profile=profile,fold=fold)
                accepted.append(dict(tag,plan=ref(path),job_id=ex.job_id(job),receipt=ref(attempt/"receipt.json"),
                                     new_fit=profile in PROFILES))
                r=verified["result"]
                tables["resources"].append(dict(tag,seconds=r["seconds"],best_epoch_1based=r["best_epoch"]+1,
                    last_epoch_1based=r["last_epoch"]+1,peak_allocated_mib=r["resources"]["peak_allocated_mib"],
                    peak_reserved_mib=r["resources"]["peak_reserved_mib"],parameter_count=r["parameter_count"],
                    resources=r["resources"],receipt=accepted[-1]["receipt"]))
                tables["relation_support"].append(dict(tag,support=job["support"],
                    gradient_audit=ref(attempt/"gradient_audit.json") if (attempt/"gradient_audit.json").is_file() else None))
                if profile in PROFILES:
                    result=mechanism_one(plan,job,attempt,predictions)
                    for name,key in (("parameter_norms","norms"),("attention_bias","bias")):
                        tables[name].extend(dict(tag,checkpoint="best",best=result["best"],**row) for row in result[key])
                print("EP9 verified/analyzed",view,ex.job_id(job),flush=True)
    if len(accepted)!=240 or sum(r["new_fit"] for r in accepted)!=120:
        raise ValueError("E-B requires 120 new and 120 baseline results")
    oof={}
    for view,by_task in inventory.items():
        for task,by_profile in by_task.items():
            labels,lexical,rules=metadata(source,index["analysis_inputs"],task)
            expected={k for k,r in labels.items() if r["L-audit_include"]}
            records=[];fold_identity=None
            for profile,folds in by_profile.items():
                if set(folds)!=set(range(10)):raise ValueError("Incomplete profile folds")
                seen=set();pooled=[];identities={}
                for fold,rows in sorted(folds.items()):
                    table=align_predictions(rows,labels)
                    if seen & set(table):raise ValueError("Overlapping OOF folds")
                    seen.update(table);pooled.extend(rows);identities[fold]=set(table)
                    for ck in ("best","last"):
                        s=score(rows,ck)
                        tables["folds"].append(dict(view=view,task_id=task,profile=profile,fold=fold,checkpoint=ck,**s))
                        records.append(dict(task_id=task,task_kind="node",profile=profile,fold=fold,seed=1,
                            checkpoint=ck,metrics={m:s[m] for m in stats.METRICS}))
                        if profile in PROFILES:
                            for node in rows:
                                key=scoring.identity(node);label=labels[key]
                                if label["solidifi"] or not (node["target"] or node[ck]):continue
                                tables["non_solidifi_nodes"].append(dict(view=view,task_id=task,profile=profile,
                                    fold=fold,checkpoint=ck,file=key[0],original_graph_node_id=key[1],
                                    source_sha256=label["source_sha256"],source_id=label["source_id"],
                                    target=node["target"],prediction=node[ck],probability=node[ck+"_positive_probability"],
                                    classification=("TP" if node[ck] else "FN") if node["target"] else "FP"))
                if seen!=expected or fold_identity is not None and identities!=fold_identity:
                    raise ValueError("OOF population or fold identity differs")
                fold_identity=identities;oof[(view,task,profile)]=scoring.index_rows(pooled)
                for ck in ("best","last"):
                    for stratum in scoring.STRATA:
                        tables["pooled"].append(dict(view=view,task_id=task,profile=profile,checkpoint=ck,
                            stratum=stratum,aggregation="pooled_OOF",**score(pooled,ck,stratum)))
            tables["fold_means"].extend(dict(view=view,**r) for r in stats.aggregate_metrics(records))
            comparisons,errors,changes=compare_profiles(records,by_profile,view,task,labels)
            tables["paired"].extend(comparisons);tables["error_changes"].extend(errors);tables["changed_nodes"].extend(changes)
    for task in ex.TASKS:
        for profile in BASELINES+PROFILES:
            for fold in range(10):
                a=scoring.index_rows(inventory["original"][task][profile][fold])
                b=scoring.index_rows(inventory["anonymous"][task][profile][fold])
                if set(a)!=set(b) or any(a[k]["target"]!=b[k]["target"] for k in a):
                    raise ValueError("Cross-view identity mismatch")
    tables["non_solidifi_nodes"].extend(r for r in old_tables["non_solidifi_nodes"] if r["profile"] in BASELINES)
    for case in old_tables["persistent_cases"]:
        row=dict(case);row["predictions"]=dict(case["predictions"]);row["probabilities"]=dict(case["probabilities"])
        for profile in PROFILES:
            node=oof[(case["view"],case["task_id"],profile)][scoring.identity(case)]
            if node["target"]!=case["target"]:raise ValueError("Persistent case truth mismatch")
            row["predictions"][profile]=node[case["checkpoint"]]
            row["probabilities"][profile]=node[case["checkpoint"]+"_positive_probability"]
        tables["persistent_cases"].append(row)
    hypotheses,holm=h2_family(tables["paired"],ea)
    tables["contrasts_by_view"]=side_by_side(tables["paired"])
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in tables.items():
        write(output/(name+".json"),rows);csv_table(output/(name+".csv"),rows)
    summary=dict(version="edgesem-E-B-analysis-r18-v1",passed=True,new_fits=120,reused_fits=120,
        hypotheses=hypotheses,holm=holm,EP8_summary=ref(ea_path),accepted=accepted,
        preparation=ref(index_path),registration=index["registration"],
        tables={name:ref(output/(name+".json")) for name in tables},
        analysis_source=ref(Path(__file__)),scoring_source=ref(Path(scoring.__file__)),
        E_A_helpers_source=ref(ROOT/"scripts/edge_sem/analysis_ea.py"),
        rule_baseline_source=ea["tables"]["rule_baselines"],training_launched_by_analysis=False,
        notes=ea["notes"]+[ "H1 and H2 now form the completed two-hypothesis Holm family.",
            "Best-checkpoint edge bias distributions are descriptive; edge/node counts are not independent experiments."])
    # The historical pending-H2 note describes E-A only; do not repeat it as current.
    summary["notes"]=[s for s in summary["notes"] if not s.startswith("Holm awaits")]
    write(output/"summary.json",summary);write(output/"summary.seal.json",dict(summary=ref(output/"summary.json")))
    return summary


LIMITATIONS=[
    "fallback/receive function nodes are unavailable in the frozen projector; MOD_APPLY is not_in_graph; E-C0 must report owner type.",
    "The anonymous gate covers about 16%/14% of attribute rows and only 3 library calls per task.",
    "Attribute bit 61 can be unknown when pragma has no upper bound; report the sealed per-task proportions.",
    "Bits 46/50/51/53 describe the source-side near endpoint.",
    "MOD_APPLY guard-type bit is always 47.",
    "Modified functions and synthetic nodes lack semantic CFG (unk_cfg).",
    "ENV/state edges lack a use_context evidence source.",
    "Original names leak injected patterns; the frozen lexical rule can match or exceed the model.",
    "Folds share training data; one seed and pooled OOF are not independent external validation.",
    "P/R Wilson intervals are descriptive and do not model within-file node dependence.",
    "Graph parameters, aggregation and optimization change too; score gains do not isolate pure semantic causation.",
]


def reports(root, schema_ref):
    root=Path(root)
    path,eb=sealed_summary(root);ea_path,ea=sealed_summary(EA)
    current={k:read(checked(v)) for k,v in eb["tables"].items()}
    previous={k:read(checked(v)) for k,v in ea["tables"].items()}
    def write_report(name,combined):
        rows=current["contrasts_by_view"]+(previous["contrasts_by_view"] if combined else [])
        lines=["# "+("EdgeSem v1 E-A/E-B 综合报告" if combined else "EP9 E-B 结果报告"),"",
            "本轮原名60次、匿名60次正式拟合均已验收；原名是唯一主视图，匿名为预登记的描述性敏感性检查。",
            "P2固定50轮，最低inner_val loss选best，last为辅助；本批仅两个节点任务。",
            "本批不是合约级检测，也不能直接对比论文原始协议下的分数。","",
            "## 登记检验","",
            "|假设|原始p|Holm校正p|两项差值均正|登记条件通过|","|---|---|---|---|---|"]
        for h in ("H1","H2"):
            v=eb["holm"]
            lines.append("|{}|{:.8g}|{:.8g}|{}|{}|".format(h,v["p_raw"][h],v["p_adjusted"][h],
                v["positive_means"][h],v["supported"][h]))
        lines.extend(["","H1原始p约0.1997，EP8已不显著；Holm不会改变这一结论。匿名结果不进入检验族。",
            "差值单位为百分点；折间标准差为描述统计。","",
            "## 两视图登记对照","",
            "|任务|对照|checkpoint|原名差值|匿名差值|原名原始p|匿名原始p|零差折原/匿|",
            "|---|---|---|---|---|---|---|---|"])
        for r in rows:
            if r["metric"]!="buggy_f1":continue
            lines.append("|{}|{} − {}|{}|{:+.4f}|{:+.4f}|{:.6g}|{:.6g}|{}/{}|".format(
                r["task_id"],r["profile"],r["baseline"],r["checkpoint"],r["original_difference_pp"],
                r["anonymous_difference_pp"],r["original_p_raw"],r["anonymous_p_raw"],
                r["original_tied_folds"],r["anonymous_tied_folds"]))
        means=list(current["fold_means"])
        if combined:means.extend(r for r in previous["fold_means"] if r["profile"]=="G4R-P")
        lines.extend(["","## 逐折BF1汇总","","|视图|任务|剖面|checkpoint|均值±样本标准差|","|---|---|---|---|---|"])
        for r in means:
            if r["metric"]=="buggy_f1":
                lines.append("|{}|{}|{}|{}|{:.4f} ± {:.4f}|".format(r["view"],r["task_id"],r["profile"],
                    r["checkpoint"],r["mean"],r["sample_sd"]))
        pooled=list(current["pooled"])
        if combined:pooled.extend(r for r in previous["pooled"] if r["profile"]=="G4R-P")
        lines.extend(["","## 非SolidiFI与名字规则","","|视图|任务|剖面|best TN/FP/FN/TP|BF1|","|---|---|---|---|---|"])
        for r in pooled:
            if r["stratum"]=="nonSolidiFI" and r["checkpoint"]=="best":
                lines.append("|{}|{}|{}|{}|{:.4f}|".format(r["view"],r["task_id"],r["profile"],
                    "/".join(map(str,r["tn_fp_fn_tp"])),r["buggy_f1"]))
        for r in current["rule_baselines"]:
            if r["rule"]==scoring.LEXICAL:
                lines.append("- 名字规则 {} / {} / {}：BF1 {:.4f}；混淆矩阵 {}。".format(
                    r["view"],r["task_id"],r["stratum"],r["buggy_f1"],r["tn_fp_fn_tp"]))
        lines.extend(["","名字规则沿用原名审计记录，两视图相同；不是从匿名输入预测的规则。",
            "逐折错误变化、相对错误减少率、分层Wilson P/R区间、非SolidiFI正例和误报逐节点、持续案例、两条无学习边规则见同名JSON/CSV。",
            "每次fit的best检查点均读取u/U范数和outer_test目标入边偏置；按层/关系族/头/目标标签汇总，仅作描述，不作独立节点显著性检验。",
            "机制输出见 parameter_norms.json 与 attention_bias.json；不上传权重。","",
            "## 冻结与局限",""])
        lines.extend("- "+s for s in LIMITATIONS)
        schema=read(checked(schema_ref))
        for task,item in schema["bit61_unknown"].items():
            lines.append("- 第61位未知 {}：{}/{}条属性行（{:.2%}）；分母为全部正向属性行。".format(
                task,item["unknown_edges"],item["all_forward_attribute_rows"],item["fraction_of_all_rows"]))
        lines.extend(["","冻结schema："+schema_ref["path"],
            "最终七类实验将在显存充足的服务器另建批次；当前显存限制仅来自本机，本轮不自动启动服务器阶段。",
            "结果来源："+str(path),"E-A来源："+str(ea_path),"",
            "执行：python -B -m scripts.edge_sem.recon.ep9_run run",
            "分析：python -B -m scripts.edge_sem.recon.ep9_run analyze",""])
        target=ROOT/"scripts/edge_sem"/name
        with target.open("x",encoding="utf8") as stream:stream.write("\n".join(lines))
    write_report("EP9_REPORT.md",False);write_report("EDGESEM_REPORT.md",True)
