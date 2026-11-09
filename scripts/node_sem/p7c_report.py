"""NS-P7c final evidence/report, append-only documents, no inference or fitting."""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import re
import statistics
from .llm_full import BASE,ROOT,checked,read,reference,write
from .doc_check import check


def mean(values):
    values=[x for x in values if x is not None]
    return statistics.mean(values) if values else None


def fmt(x,percent=False):
    if x is None:return "不可估"
    return ("%.4f"%(100*x if percent else x))


def collect(base):
    base=Path(base)
    plan=read(checked(read(base/"diagnostics/plan.seal.json")["plan"]))
    completed=read(base/"diagnostics/completed.json")
    expected=sum(len(item["folds"]) for item in plan["tasks"].values())
    if (completed.get("passed") is not True or completed.get("folds")!=expected
            or completed.get("plan")!=reference(base/"diagnostics/plan.json")):
        raise ValueError("Diagnostic controller incomplete")
    results={}
    for task,item in plan["tasks"].items():
        found=[]
        for fold in item["folds"]:
            d=base/"diagnostics/folds"/(task+"__"+str(fold))
            receipt=read(d/"receipt.json")
            if receipt["passed"] is not True:raise ValueError("Failed diagnostic receipt")
            r=read(checked(receipt["result"]))
            if r["task_id"]!=task or r["fold"]!=fold or r["plan"]!=reference(base/"diagnostics/plan.json"):
                raise ValueError("Mixed diagnostic identity")
            found.append(r)
        if len({r["fold"] for r in found})!=len(item["folds"]):raise ValueError("Duplicate folds")
        ridge=[r["ridge"] for r in found if r["ridge"]["status"]=="ok"]
        summary=dict(folds=len(found),ridge_estimable=len(ridge),
            ridge_mean_cosine=mean([r["outer_mean_cosine"] for r in ridge]),
            baseline_mean_cosine=mean([r["baseline_mean_cosine"] for r in ridge]),
            ridge_on_baseline_population=mean([r["ridge_on_baseline_population"] for r in ridge]),
            baseline_unseen_rows=sum(r["baseline_unseen_rows"] for r in ridge),
            signal={})
        if task.endswith("_node"):
            for source in ("static","static_teacher"):
                values=[s for r in found for s in r["signal"] if s["source"]==source]
                summary["signal"][source]=dict(
                    f1_estimable=sum("buggy_f1" in s for s in values),
                    auc_estimable=sum(s.get("auc") is not None for s in values),
                    buggy_f1_mean=mean([s.get("buggy_f1") for s in values]),
                    auc_mean=mean([s.get("auc") for s in values]),
                    statuses={status:sum(s["status"]==status for s in values) for status in sorted({s["status"] for s in values})})
            paired=[]
            for r in found:
                a,b=({s["source"]:s for s in r["signal"]}[name] for name in ("static","static_teacher"))
                paired.append(dict(fold=r["fold"],
                    buggy_f1_delta=b["buggy_f1"]-a["buggy_f1"] if "buggy_f1" in a and "buggy_f1" in b else None,
                    auc_delta=b["auc"]-a["auc"] if a.get("auc") is not None and b.get("auc") is not None else None))
            summary["paired_signal"]=paired
            summary["paired_f1_delta"]=mean([p["buggy_f1_delta"] for p in paired])
            summary["paired_auc_delta"]=mean([p["auc_delta"] for p in paired])
        results[task]=dict(summary=summary,folds=found)
    return results


def finalize(base=BASE):
    base=Path(base);out=base/"finalization";out.mkdir(exist_ok=False)
    start=read(base/"start.json")
    for r in read(base/"old_artifacts.json"):checked(r)
    for r in read(base/"plan.json")["implementation"].values():checked(r)
    results=collect(base)
    tests=[]
    for name in ("nodesem","dfg_v2","legacy"):
        p=base/"regressions"/("nodesem_final.log" if name=="nodesem" else name+".log")
        lines=p.read_text().strip().splitlines();last=lines[-1]
        match=re.search(r"(\d+) passed",last)
        if not match or "failed" in last or "error" in last.lower():
            raise ValueError("Regression incomplete: "+name)
        tests.append(dict(suite=name,passed=int(match.group(1)),summary=last,log=reference(p)))
    frozen=read(base/"frozen_audit.json")
    if not frozen["passed"]:raise ValueError("Frozen audit failed")
    done=read(checked(read(base/"run1/completed.seal.json")["completed"]))
    posts=read(checked(read(base/"post/index.seal.json")["index"]))
    teacher=read(checked(read(base/"teacher/index.seal.json")["index"]))
    if set(teacher["tasks"])!=set(results) or set(posts["tasks"])!=set(results):raise ValueError("Missing task")
    summaries={t:v["summary"] for t,v in results.items()}
    write(out/"results.json",dict(tasks=results,tests=tests,prior_pilots_passed=False,
        full_generation_authorized_by_user=True,HGT_training=0,student_training=0,
        diagnostic_regression_fits=True,teacher=reference(base/"teacher/index.json")))
    fold_fields=["task","fold","ridge_cosine","baseline_cosine","ridge_paired_cosine","baseline_unseen_rows",
                 "static_auc","static_teacher_auc","static_bf1","static_teacher_bf1"]
    with (out/"folds.csv").open("x",encoding="utf8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fold_fields,lineterminator="\n");writer.writeheader()
        for task,data in results.items():
            for r in data["folds"]:
                ridge=r["ridge"];signals={s["source"]:s for s in r["signal"]}
                writer.writerow(dict(task=task,fold=r["fold"],ridge_cosine=ridge.get("outer_mean_cosine"),
                    baseline_cosine=ridge.get("baseline_mean_cosine"),ridge_paired_cosine=ridge.get("ridge_on_baseline_population"),
                    baseline_unseen_rows=ridge.get("baseline_unseen_rows"),
                    **{name+"_"+metric:signals.get(name,{}).get(key)
                       for name in ("static","static_teacher") for metric,key in (("auc","auc"),("bf1","buggy_f1"))}))
    diagnostics="；".join(t+" 岭回归余弦 "+fmt(s["ridge_mean_cosine"])+" / 同类型均值 "+fmt(s["baseline_mean_cosine"])
                           for t,s in summaries.items())
    signal="；".join(t+" STATIC+TEACHER−STATIC：BF1 "+fmt(s["paired_f1_delta"],True)+"pp，AUC "+fmt(s["paired_auc_delta"])
                    for t,s in summaries.items() if s["signal"])
    body=["# NS-P7c：当前3B模型全量描述、无role教师向量与必要诊断","",
        diagnostics+"。"+signal+"。两次50函数试点均未通过；本次全量运行是用户在知情后按PROMPTS r26作出的决定，不改写旧结论。",
        "","## 1. 范围与实际改动","",
        "基于node-sem@"+start["HEAD"]+"，读取最新共享上下文及NS-P7c。使用原describe_v2、Qwen2.5-Coder-3B-Instruct Q4_K_M及已封存参数，未更换模型或下载新权重；不运行judge、不训练HGT或学生。本轮CPU岭回归和逻辑回归拟合只用于诊断。",
        "新增llm_full、offline/llm_full调度，llm_teacher后处理，teacher_vectors、offline/teacher_encode，teacher_diagnostics、p7c_diagnostics、p7c_report和必要测试。旧模板、LLM试点、DFG、HGT、图、标签、特征与划分保持不变。",
        "","## 2. 全量生成与教师覆盖","",
        "4,485个唯一提示逐个有收据；无函数体且无语句目标的单元跳过，有函数体但无目标仍生成函数意图。重入节点优先；历史同模板响应按SHA只读复用。后台进程独立于对话与网络，15秒心跳，整体解析失败率按已完成推理单元计算、排除跳过项；超过5%停止。其他执行或输入完整性错误也停止，不自动重试。",
        "最终单元状态："+json.dumps(posts["generated_statuses"],ensure_ascii=False)+"。本轮生成阶段墙钟 %.2f 小时。"%(done["elapsed_seconds"]/3600),
        "教师只编码summary与function_intent，不把role字段拼入文本；这只适用于当前3B模型。静态参考未知但描述有效的节点保留并标unverified，已核验忠实性<0.5或黑名单描述仍缺失。unverified不代表已证明正确；自由摘要与函数意图没有被读写集合检查完整验证。",
        "",
        "|任务|全部行|教师存在|旧规则存在|unverified语句|可核验语句中≥0.5|",
        "|---|---:|---:|---:|---:|---:|"]
    quality=[]
    for task,ref in posts["tasks"].items():
        meta=read(checked(ref));q=meta["quality"]
        body.append("|%s|%d|%d|%d|%d|%s%%|"%(task,q["rows"],q["present"],q["old_present"],q["unverified_statements"],fmt(q["verifiable_ge_half_fraction"],True)))
        quality.append(dict(task=task,quality=q,cohorts=meta["cohorts"]))
    write(out/"quality.json",quality)
    body+=["","解析、黑名单、忠实性、unverified与role精确率/召回率的SolidiFI/非SolidiFI分层详见finalization/quality.json；本轮不以role质量作为继续生成的门槛。去掉role字段不能保证自然语言summary不再包含相同的错误判断。",
        "","## 3. 编码与载体","",
        "复用已登记BAAI/bge-small-en-v1.5（revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a），本地加载、冻结、384维、归一化，两遍编码逐位一致。每任务F3全集按身份和顺序对应，缺失写零向量＋存在位0；G0/G3R共用该模态。TEACHER在原FeatureSpec白名单已存在，本轮验证384＋1布局，不新增训练配置。",
        "","## 4. 两项诊断与解释边界","",
        "全部30折逐任务报告；岭回归仅在教师/CTX/STATIC存在的节点拟合，标准化与拟合只用inner_train，inner_val平均余弦选择alpha={0.01,0.1,1,10}，outer_test仅评分。同类型均值只用inner_train；训练未见节点类型单列不可估，同时给出共同可估节点上的岭回归结果。",
        "非SolidiFI信号只用原语句/条件节点集合，两个特征对照样本一致；教师缺失用零向量及存在位表示，不删除困难节点。C={0.01,0.1,1,10}、seed1及逻辑回归算法沿用NS-P6c2，inner_val选C和阈值；空或单类别划分按原规则不可估。合约任务没有相应节点标签终点，因此仅做可重建性诊断。",
        "|任务|岭回归余弦|同类型均值余弦|共同可估节点岭回归余弦|未见类型节点|",
        "|---|---:|---:|---:|---:|"]
    for t,s in summaries.items():
        body.append("|%s|%s|%s|%s|%d|"%(t,fmt(s["ridge_mean_cosine"]),fmt(s["baseline_mean_cosine"]),fmt(s["ridge_on_baseline_population"]),s["baseline_unseen_rows"]))
    body+=["","|任务|STATIC BF1|STATIC+TEACHER BF1|差值pp|STATIC AUC|STATIC+TEACHER AUC|BF1/AUC可估折|",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for t,s in summaries.items():
        if not s["signal"]:continue
        a,b=(s["signal"][k] for k in ("static","static_teacher"))
        body.append("|%s|%s|%s|%s|%s|%s|%d/%d|"%(t,fmt(a["buggy_f1_mean"],True),fmt(b["buggy_f1_mean"],True),fmt(s["paired_f1_delta"],True),fmt(a["auc_mean"]),fmt(b["auc_mean"]),b["f1_estimable"],b["auc_estimable"]))
    body+=["","以上为等权可估折均值，完整逐折、缺失与配对差值在finalization/results.json、folds.csv。它们是冻结划分上的描述性CPU诊断，不是HGT收益或新增独立数据集的泛化证明。高余弦说明线性可预测程度高，不能严格推出学生不可能改善下游优化；高均值基线也提示嵌入共性方向的影响。",
        "","## 5. 实施选择、失败与限制","",
        "用户批准两项接入澄清：(1)旧NS-P6c2没有岭回归网格，本轮预先固定alpha和无泄漏规则；(2)carrier要求每份manifest唯一task_id，故teacher/<task>/teacher.npz逐任务保存并提供总索引，未修改载体。",
        "封存前第一次准备因构造函数/modifier片段脱离合约上下文解析失败；保留llm_v3_setup_attempt1/failure.json，尚未加载模型或生成响应。只在判断函数体时增加语法容器，真实提示字节不变；1,064个该类函数实例在容器中均可解析，修复后完成准备。",
        "保留describe_v2第8条this.f()已知边界、external只能布尔导致unknown表达受限、单角色和根变量抽象限制；按本轮明确要求不改模板。函数意图和摘要仍可能错误，移除role并不等于解决全部语义错误。",
        "最终实验将在显存充足的服务器另建批次；本机RTX3050 4GiB只限制当前开发。本轮不自动更换更大模型、不自动进入NS-P8a。",
        "","## 6. 测试与实际命令","",
        "测试："+str(sum(t["passed"] for t in tests))+"通过。各套日志摘要："+json.dumps([t["summary"] for t in tests],ensure_ascii=False)+"。",
        "旧实验记录SHA核验数量："+str(len(read(base/"old_artifacts.json")))+"；8H只读装载与冻结源码核验通过，详见frozen_audit.json。模型/后端继续按原资产seal核验。",
        "",
        "~~~bash",
        "python -B -m scripts.node_sem.llm_full prepare",
        "python -B -m scripts.node_sem.llm_full seal",
        "python -s -B scripts/node_sem/offline/llm_full.py --out scripts/node_sem/artifacts/llm_v3",
        "python -B -m scripts.node_sem.llm_teacher --out scripts/node_sem/artifacts/llm_v3",
        "python -s -B scripts/node_sem/offline/teacher_encode.py --out scripts/node_sem/artifacts/llm_v3",
        "python -B -m scripts.node_sem.p7c_diagnostics prepare",
        "python -B -m scripts.node_sem.p7c_diagnostics run",
        "~~~",
        "",
        "实际解释器、环境、PID和命令见launch.json与后续阶段执行记录；已存在目录拒绝覆盖，以上不是可原地重复执行的命令。Git仅归档代码、计划、报告、紧凑统计和SHA索引；权重、完整响应、向量留在WSL。",""]
    text="\n".join(body)
    report=ROOT/"scripts/node_sem/NS_P7C_REPORT.md"
    with report.open("x",encoding="utf8") as f:f.write(text)
    with (base/"REPORT.md").open("x",encoding="utf8") as f:f.write(text)
    date=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    short="\n\n## "+date+" NS-P7c 完成（修改 AI：Codex）\n\n"+diagnostics+"。"+signal+"。\n\n两次试点未通过的结论保持；本次按用户r26决定完成3B全量describe_v2、无role教师向量及必要CPU诊断。未训练HGT或学生，未运行judge，不进入NS-P8a。详细记录见scripts/node_sem/NS_P7C_REPORT.md。用户确认岭回归网格和逐任务教师产物布局。最终实验将在显存充足服务器另建批次，本机4GiB只属开发限制。\n"
    docchecks=[]
    for name,prior in start["documents"].items():
        p=ROOT/name;raw=p.read_bytes()
        if hashlib.sha256(raw[:prior["bytes"]]).hexdigest()!=prior["sha256"]:
            raise ValueError("Historical document prefix changed")
        offset=len(raw)
        with p.open("a",encoding="utf8") as stream:
            stream.write("\n\n## 92. "+date+" NS-P7c 实施与选择记录（Codex）\n\n"+text if name.startswith("docs/") else short)
        docchecks.append(check(p,offset,expect_cjk=True))
    docchecks += [check(report,expect_cjk=True),check(base/"REPORT.md",expect_cjk=True)]
    write(out/"doc_check.json",docchecks)
    write(out/"complete.json",dict(passed=True,report=reference(report),results=reference(out/"results.json"),
        tests=sum(t["passed"] for t in tests),HGT_training=0,student_training=0,NS_P8a_started=False))
    print(json.dumps(summaries,indent=2))


if __name__=="__main__":finalize()
