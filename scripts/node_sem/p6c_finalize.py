"""Finish NS-P6c documentation and compact archive after all sealed diagnostics."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,write,ref,checked
from .p6c_run import OUT,ROOT,load,worker
from .p6c_report import build


def fmt(x,digits=4):
    return "不可估" if x is None else ("{:.%df}"%digits).format(x)


def finish(out=OUT):
    out=Path(out);plan=load(out)
    if (out/"REPORT.md").exists():raise FileExistsError("Completed documentation exists")
    rev=out/"cpu_parallel_revision"
    revision=read(checked(read(rev/"seal.json")["revision"]))
    checked(revision["source"])
    cpu_done=read(rev/"complete.json")
    if cpu_done.get("passed") is not True or (cpu_done["new_folds"],cpu_done["reused_folds"])!=(29,1):
        raise ValueError("CPU scheduling revision not complete")
    if cpu_done["revision"]!=ref(rev/"revision.json"):
        raise ValueError("Mixed CPU revision")
    for task in revision["tasks"]:
        expected={e["job"]["fold"] for e in plan["jobs"] if e["job"]["task_id"]==task}
        dest=out/"probes"/task
        values=[read(p) for p in dest.glob("redundancy_fold_*.json")]
        got=[]
        population=read(dest/"population.json")
        for value in values:
            rows=value["results"]
            identities=[(r["fold"],r["source"],r["column"]["index"]) for r in rows]
            foldset={r["fold"] for r in rows}
            if len(foldset)!=1 or len(set(identities))!=len(identities):
                raise ValueError("Duplicate or mixed redundancy rows")
            fold=next(iter(foldset));got.append(fold)
            want={(fold,source,c["index"]) for source in ("code","ctx") for c in population["eligible"]}
            if set(identities)!=want or any(r["task_id"]!=task for r in rows):
                raise ValueError("Incomplete or mixed probe population")
        if len(got)!=len(expected) or set(got)!=expected:
            raise ValueError("Incomplete fold identities")
        if task.endswith("_node"):
            rows=read(dest/"signal.json")
            keys=[(r["fold"],r["source"]) for r in rows]
            if len(keys)!=30 or set(keys)!={(f,s) for f in expected for s in ("code","static","code_static")}:
                raise ValueError("Signal fold identities differ")
    report=build(out)
    folds=[read(out/"eval"/worker.job_id(e["job"])/"result.json") for e in plan["jobs"]]
    redundant=[]
    for d in (out/"probes").iterdir():
        for p in d.glob("redundancy_fold_*.json"):redundant.extend(read(p)["results"])
    signal=read(out/"signal_results.json")
    fitted=sum(len(r.get("candidates",[])) for r in redundant+signal)
    checks=ROOT/"scripts/node_sem/artifacts/ns_p6c_checks"
    tests=read(checks/"tests_final.json")
    if len(tests)!=3 or any(t["exit_code"] for t in tests):raise ValueError("Required regression incomplete")
    frozen=read(checks/"frozen_runtime.json")
    if not frozen["passed"]:raise ValueError("Frozen source check failed")
    for e in plan["jobs"]:checked(e["best"])
    prefix=read(checks/"doc_prefixes.json")
    for f,s in prefix.items():
        if hashlib.sha256((ROOT/f).read_bytes()[:s["bytes"]]).hexdigest()!=s["sha256"]:
            raise ValueError("Prior document bytes were changed")
    names={"reentrancy_contract":"重入合约","access_control_contract":"访问控制合约",
        "reentrancy_node":"重入节点","access_control_node":"访问控制节点"}
    contributions=report["effective_contributions"]
    removal=report["aggregate_removal"]
    groups=report["redundancy_groups"]
    paired=report["signal_paired"]
    totalchange=sum(r["total_changed"] for r in removal if r["condition"]=="code_only")
    positivechange=sum(r["positive_changed"] for r in removal if r["condition"]=="code_only" and r["task_id"].endswith("_node"))
    intro=("门控机制在工作，门控权重与投影范数的乘积已逐模型核验。"
        "同时去掉CTX和STATIC时，四任务共改变%d个外层预测，其中非SolidiFI正例节点改变%d个；"
        "是否使用这些输入应看各任务干预敏感性，不能只看门控权重。"
        "STATIC与CODE/CTX的可线性预测程度、非SolidiFI额外信号见下表；"
        "这些是条件性描述证据，不是语义因果证明。"%(totalchange,positivechange))
    redundancy_answer=[]
    for task in names:
        by_source={r["source"]:r for r in groups if r["task_id"]==task and r["group"]=="ALL"}
        redundancy_answer.append(names[task]+": "+", ".join(n+" %d/%d"%(by_source[n]["high_auc_bits"],by_source[n]["estimable_bits"]) for n in ("code","ctx")))
    signal_answer=[]
    for task in ("reentrancy_node","access_control_node"):
        values=[r["BF1_delta_pp"] for r in paired if r["task_id"]==task and r["BF1_delta_pp"] is not None]
        signal_answer.append(names[task]+": "+fmt(statistics.mean(values) if values else None)+"pp (%d/10可估折)"%len(values))
    intro += " STATIC位的折均AUC≥0.95数/可估位数为"+"；".join(redundancy_answer)+"。非SolidiFI的CODE+STATIC相对CODE平均BF1差为"+"；".join(signal_answer)+"；不能用少量可估折证明稳定增益。"
    lines=["# NS-P6c：模态贡献与冗余诊断（Codex）","",intro,"",
        "本轮新增HGT训练0、参数更新0；30个N-B S4g best模型，各4次eval，共120次。"
        "S4属于N-A，其30份best已由用户删除，本轮未执行、未替代、未重训。"
        "逻辑回归属于文档明确要求的CPU诊断探针，实际拟合%d次系数，不计入HGT正式实验次数。"%fitted,"",
        "## 1. 来源、协议与已批准调整","",
        "依据PROMPTS.md r20 §5.1/§5.9c与c6310b6d。原名original、冻结L-audit、8D文件分组嵌套折，"
        "合约5折/节点10折，inner_train拟合探针，inner_val选C/阈值，outer_test只评分。"
        "旧N-A/N-B图、标签、折、特征、计划、收据及批次报告均不修改；报告为事后机制诊断。",
        "",
        "用户批准三项澄清：只评估可用S4g，S4缺失单列；保留<0.1%分类变化且非SolidiFI正例不变的判据，"
        "结论收紧为未观察到明显分类敏感性；C解释为L2强度倒数，空/单类别划分不借用测试集补齐。"
        "原回复在decisions.json。当前输出排他创建，不覆盖旧批次。",
        "",
        "N-A480个正式best/last的缺失原因已根据用户提供的文档更正为用户主动删除；具体删除时间未提供。"
        "封存预测、收据、指标和删除前注意力诊断仍保留；当前无法重载N-A，服务器批次需重新训练。"
        "旧historical_weight_availability.json未改，新说明见na_checkpoint_note.json。",
        "",
        "## 2. 门控与有效贡献","",
        "下表先按每个任务/折/模型计算，再等权平均折。g为有该模态节点的门控均值；share为"
        "g×L2(P(normalized x))除以三模态此量之和的节点均值。没有纳入共享bias；零分母单列，"
        "不把范数份额解释为最终logit贡献，向量方向与抵消、GELU/HGT会继续影响输出。"
        "逐节点类型的完整分布、可用数量和分位数见contributions_by_type.json。",
        "",
        "|任务|模态|g折均|有效范数折均|范数份额折均|",
        "|---|---|---:|---:|---:|"]
    for r in contributions:
        lines.append("|%s|%s|%s|%s|%s|"%(names[r["task_id"]],r["modality"],fmt(r["gate"]["mean"]),
            fmt(r["effective"]["mean"]),fmt(r["share"]["mean"])))
    lines+=["","## 3. 推理时移除","",
        "仅在内存DGL local_scope中把存在位置零，向量本身不改；门控按实际缺失重新计算。"
        "与训练modality dropout的缺失处理等价测试通过；模型为eval，无反向，无优化器。"
        "full预测与各封存best导出逐身份核对，最大概率误差为%s；30个参数摘要前后相同。"%fmt(max(v["historical_baseline_max_probability_error"] for v in folds),9),
        "","|任务|条件|BF1折均 %|分类改变/评分数|非SolidiFI正例改变|概率MAE折均|",
        "|---|---|---:|---:|---:|---:|"]
    for r in removal:
        lines.append("|%s|%s|%s|%d/%d|%d|%s|"%(names[r["task_id"]],r["condition"],
            fmt(r["buggy_f1"]["mean"]),r["total_changed"],r["total_n"],r["positive_changed"],fmt(r["probability_MAE"]["mean"],6)))
    lines+=["",
        "逐折指标及改变比例见removal_folds.csv。nonSolidifi_changes.json保留全部重入32、访问控制20个正例，"
        "及任一条件下出现的非SolidiFI误报，包含文件、source SHA、节点身份及四种概率。"
        "这里的数量为HCG节点或合约文件，不是独立漏洞个数。",
        "",
        "移除干预改变了训练后模型的输入条件，不等于重训后的组件消融。分类不变仍可能有概率变化或冗余补偿；"
        "分类变化也不单独证明该模态提供了额外、正确的漏洞语义；存在位置零还会重归一其余模态的门控权重，"
        "因此测量包含模态内容移除与融合比例变化的联合效应。原<0.1%规则按每个模型记录，不据此修改配置。",
        "",
        "## 4. STATIC冗余探针","",
        "每任务STATIC可用行中取1比例在[1%,99%]的位；这是文档指定的全任务无漏洞标签筛选，属于"
        "传导式特征审计，不冒充纯归纳特征选择。标准化只在inner_train拟合。liblinear L2逻辑回归，"
        "C∈{0.01,0.1,1,10}，tol=1e-4、max_iter=1000、seed=1；按inner_val AUC选C，平局取较小C。"
        "不把inner_val并回训练；测试BA阈值0.5。单类别train/val不可估，单类别test的AUC/BA为null。"
        "所有位的逐折结果在本地probes目录，Git以SHA索引与生成命令归档。",
        "",
        "|任务|输入|符合比例的位|至少一折可估|折均AUC≥0.95位|占可估位比例|所有折可估位|",
        "|---|---|---:|---:|---:|---:|---:|"]
    for r in groups:
        if r["group"]!="ALL":continue
        lines.append("|%s|%s|%d|%d|%d|%s|%d|"%(names[r["task_id"]],r["source"],r["eligible_bits"],
            r["estimable_bits"],r["high_auc_bits"],fmt(r["high_auc_fraction"]),r["all_folds_estimable_bits"]))
    statuses={}
    for r in redundant:statuses[r["status"]]=statuses.get(r["status"],0)+1
    lines+=["","各A–N父组见redundancy_groups.csv；A1/D3等原子组在redundancy_bits.json保留。"
        "高AUC按该位可估折的等权均值判断，同时披露可估折数；不是把重复节点当独立样本。"
        "状态计数："+json.dumps(statuses,ensure_ascii=False)+"。",
        "高可预测性支持表示冗余解释，但不证明目标漏洞信号已被模型有效利用；低线性可预测性也不能证明没有非线性冗余。",
        "",
        "## 5. 非SolidiFI信号探针","",
        "仅两个节点任务的L-audit包含行，CODE/STATIC共有可用节点，固定文件折。C仍按inner_val AUC选择；"
        "BF1阈值在inner_val最大化，平局距0.5最近、再取更小阈值。空/单类别折不从outer_test借样本或调参。"
        "详细逐折AUC/BF1、阳性数、状态、阈值、C和预测在signal_results.json。",
        "",
        "|任务|输入|有BF1折数/10|BF1折均 %|有AUC折数/10|AUC折均|",
        "|---|---|---:|---:|---:|---:|"]
    for task in ("reentrancy_node","access_control_node"):
        for source in ("code","static","code_static"):
            rows=[r for r in signal if r["task_id"]==task and r["source"]==source]
            bf=[100*r["buggy_f1"] for r in rows if r.get("buggy_f1") is not None]
            auc=[r["auc"] for r in rows if r.get("auc") is not None]
            lines.append("|%s|%s|%d/10|%s|%d/10|%s|"%(names[task],source,len(bf),
                fmt(statistics.mean(bf) if bf else None),len(auc),fmt(statistics.mean(auc) if auc else None)))
    lines+=["","|任务|CODE+STATIC−CODE BF1平均差pp|有效配对折|AUC平均差|有效配对折|",
        "|---|---:|---:|---:|---:|"]
    for task in ("reentrancy_node","access_control_node"):
        rows=[r for r in paired if r["task_id"]==task]
        bf=[r["BF1_delta_pp"] for r in rows if r["BF1_delta_pp"] is not None]
        auc=[r["auc_delta"] for r in rows if r["auc_delta"] is not None]
        lines.append("|%s|%s|%d/10|%s|%d/10|"%(names[task],fmt(statistics.mean(bf) if bf else None),
            len(bf),fmt(statistics.mean(auc) if auc else None),len(auc)))
    lines+=["",
        "样本少，某些折没有足够正例，不能把可估子集的均值写成完整10折成功验证。"
        "BF1与AUC方向可能不同，不能挑其中更有利者。逐折差见signal_paired.csv，只有描述统计，无显著性检验。",
        "",
        "## 6. 代码、验证与不变量","",
        "新增p6c_core.py、p6c_run.py、p6c_probes.py、p6c_report.py、p6c_finalize.py、p6c_parallel.py和tests/test_p6c.py。"
        "冻结NodeSemAdapter、载体装配、模型构造与checkpoint_io直接复用；训练路径和DFG/作者源码零修改。",
        "",
        "定向13项包含在NodeSem974项中，不重复计数；DFGv2 2653、原DDG/graph_utils223，"
        "合计3850通过、0失败/跳过、42条既有DGL/distutils及NetworkX弃用警告。"
        "8H load170项及354份冻结源码与生效修订一致。三份记录及NS_P6_REPORT只追加，旧字节前缀核验。",
        "",
        "本次N-B成功best120份逐文件SHA核验并保留；S4g每次加载前核验文件SHA及tensor digest，"
        "binding与封存收据相符，full前向复现历史预测，干预前后参数摘要不变。"
        "S4未执行为已批准的缺失项；不补跑N-A，不更改旧availability。",
        "",
        "## 7. 实际命令与存储","",
        "在原mando环境、项目根目录，设置PYTHONDONTWRITEBYTECODE=1、TREE_SITTER_LIB_DIR、"
        "OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、OPENBLAS_NUM_THREADS=2。CPU命令另设CUDA_VISIBLE_DEVICES=''。",
        "",
        "~~~bash",
        "python -B -m scripts.node_sem.p6c_run prepare",
        "python -B -m scripts.node_sem.p6c_run eval --only <plan中的job_id>  # 30个，GPU串行",
        "CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_probes --task <task_id>  # 首次串行attempt，现场保留",
        "CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_parallel prepare",
        "CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6c_parallel run  # 经用户批准的29折调度修订",
        "python -B -m scripts.node_sem.p6c_finalize",
        "CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests",
        "CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests",
        "CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py",
        "~~~",
        "",
        "以上生成命令拒绝覆盖；重现应指定新的--out，并重新封存而不是写入本批目录。"
        "本批未训练新权重、未重编码特征；CPU调度生成了只读特征缓存，缓存和逐行/逐折明细留WSL，用artifact_inventory.json记录路径、大小和SHA。"
        "Git只归档代码、计划、封存、收据、报告、紧凑汇总与索引，不改写历史。"
        "运行前共享Git目录为%d字节（%.2f MiB）。"%(plan["git_size_bytes"],plan["git_size_bytes"]/1048576),
        "",
        "最终实验按用户安排在显存充足服务器开展；本机4GiB仅当前限制，服务器尚需实测并另建批次。"
        "不合并设备结果、不自动进入NS-P7、不启动新HGT训练、新seed或新模型。"]
    text="\n".join(lines)+"\n"
    (out/"REPORT.md").write_text(text,encoding="utf8")
    target=ROOT/"scripts/node_sem/NS_P6C_REPORT.md"
    with target.open("x",encoding="utf8") as stream:stream.write(text)
    summary="\n\n## 2026-11-08 NS-P6c 完成（修改 AI：Codex）\n\n"+intro+"\n\n"
    summary+=("30个S4g best完成120次只读前向，原full预测复现、SHA/state/binding及前后参数一致；"
        "S4权重不可用按批准跳过。四任务冗余探针及两个节点任务非SolidiFI信号探针完成，"
        "空/单类别折明确标记，未修改划分。3850测试通过、42既有警告，8H354冻结源码不变。"
        "新增代码/命令/逐折结果和限制见scripts/node_sem/NS_P6C_REPORT.md、artifacts/ns_p6c/。"
        "用户确认的三项澄清与N-A权重删除原因已留证。\n\n"
        "HGT新增训练0，不进入NS-P7；权重未删除，保留120份成功N-B best的SHA索引。"
        "服务器实验按用户安排另建显存充足批次，本机4GiB只属开发限制，不混合结果。\n")
    for f in ("HANDOVER.md","scripts/node_sem/PROGRESS.md"):
        with (ROOT/f).open("a",encoding="utf8") as stream:stream.write(summary)
    with (ROOT/"docs/training_changes_2026-10-07.md").open("a",encoding="utf8") as stream:
        stream.write("\n\n## 88. NS-P6c 模态贡献、移除与冗余诊断（2026-11-08，Codex）\n\n"+text)
    scheduling_note=("\n\nCPU调度修订：用户批准保留首轮现场，复用已完成的访问控制节点fold0，"
        "其余29折并行执行。原plan/seal与p6c_core.logistic_probe不变；特征缓存逐位相同，"
        "调度入口输出与原函数逐项相同测试通过。旧4个串行CPU进程经明确授权终止，"
        "未完成的中间计算不进入结果；表中探针拟合次数仅指进入最终报告的已完成C候选。"
        "修订、原进程与文件SHA、日志在cpu_parallel_revision/，不称新seed重复或HGT续训。\n")
    for path in (out/"REPORT.md",target,ROOT/"docs/training_changes_2026-10-07.md",ROOT/"scripts/node_sem/PROGRESS.md",ROOT/"HANDOVER.md"):
        with path.open("a",encoding="utf8") as stream:stream.write(scheduling_note)
    inventory=[]
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name!="artifact_inventory.json":
            inventory.append(dict(size_bytes=p.stat().st_size,**ref(p)))
    write(out/"artifact_inventory.json",dict(files=inventory,total_bytes=sum(r["size_bytes"] for r in inventory),
        generation_commands="NS_P6C_REPORT.md section 7; exclusive outputs; same sealed inputs and runtime",
        historical_artifacts_modified=False,weights_deleted=0))
    write(out/"complete.json",dict(passed=True,report=ref(out/"report.json"),markdown=ref(out/"REPORT.md"),
        inventory=ref(out/"artifact_inventory.json"),eval_models=30,eval_forwards=120,
        logistic_fits=fitted,redundancy_results=len(redundant),signal_results=len(signal),
        tests=ref(checks/"tests_final.json"),frozen=ref(checks/"frozen_runtime.json"),
        cpu_revision=ref(rev/"revision.json"),cpu_complete=ref(rev/"complete.json"),
        finalizer=ref(Path(__file__)),
        new_HGT_training=0,S4_unavailable=30))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(OUT));a=ap.parse_args();finish(a.out)
