"""Finalize NS-P6c2 reports and append-only records after sealed CPU checks."""
import argparse
import hashlib
from pathlib import Path
import re
import statistics
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, write, ref, checked
from .p6c2_run import ROOT, OUT, load
from .p6c2_report import build

NAMES={"reentrancy_contract":"重入合约","access_control_contract":"访问控制合约",
       "reentrancy_node":"重入节点","access_control_node":"访问控制节点"}

def number(v,digits=4):
    return "不可估" if v is None else ("%."+str(digits)+"f")%v


def finish(out=OUT):
    out=Path(out);load(out)
    binding=read(out/"reporting_binding_v2.json")
    for r in binding["sources"]:checked(r)
    tests=read(out/"checks/tests_final.json")
    if len(tests)!=3 or any(r["exit_code"] for r in tests):
        raise ValueError("Regression incomplete")
    passed=warnings=0
    for r in tests:
        log=checked(r["log"]).read_text()
        count=re.findall(r"(\d+) passed",log)
        if not count or re.search(r"\d+ (?:failed|error)",log):raise ValueError("Bad test log")
        passed+=int(count[-1])
        warning=re.findall(r"(\d+) warnings",log)
        warnings+=int(warning[-1]) if warning else 0
    for name,r in read(out/"doc_prefixes.json").items():
        if hashlib.sha256((ROOT/name).read_bytes()[:r["bytes"]]).hexdigest()!=r["sha256"]:
            raise ValueError("Prior documentation was changed")
    report=build(out)
    groups=report["groups"]
    allcode=[r for r in groups if r["level"]=="all" and r["source"]=="code"]
    answer="；".join(NAMES[r["task_id"]]+" %d/%d（%s%%，合格%d位）"%(r["high_auc_bits"],
        r["estimable_bits"],number(100*r["high_auc_fraction_estimable"],2),r["eligible_bits"]) for r in allcode)
    weakest=[]
    for task in NAMES:
        r=[x for x in groups if x["task_id"]==task and x["source"]=="code" and x["level"]=="parent"
           and x["group"] not in ("J","N") and x["median_fold_mean_auc"] is not None]
        r=sorted(r,key=lambda x:x["median_fold_mean_auc"])[:3]
        weakest.append(NAMES[task]+": "+", ".join(x["group"]+"="+number(x["median_fold_mean_auc"]) for x in r))
    sig=[]
    for task in ("reentrancy_node","access_control_node"):
        for comparison in ("static minus code","code_static minus code"):
            rows=[r for r in report["signal_paired"] if r["task_id"]==task and
                r["view"]=="statement_condition" and r["comparison"]==comparison]
            bf=[r["BF1_delta_pp"] for r in rows if r["BF1_delta_pp"] is not None]
            auc=[r["auc_delta"] for r in rows if r["auc_delta"] is not None]
            sig.append(NAMES[task]+" "+comparison+"：BF1 "+number(statistics.mean(bf) if bf else None)+
                "pp，AUC "+number(statistics.mean(auc) if auc else None)+"（%d/10折）"%len(bf))
    first=("按适用节点计算，CODE折均AUC≥0.95的STATIC位数/可估位数为："+answer+"。"
        "当前探针较弱的语义父组（组内位的折均AUC中位数最低三组）为"+"；".join(weakest)+"。"
        "这些低值不能证明CODE中不存在该信息；不可估组也不能称为无法预测。"
        "只保留非SolidiFI语句/条件节点后，"+"；".join(sig)+"。"
        "这是小样本、固定seed的描述性诊断，不能直接当作HGT增益或确定的因果结论。")
    lines=["# NS-P6c2：适用节点冗余探针与非SolidiFI敏感性分析（Codex）","",first,"",
        "原名original视图；CPU执行；新增HGT训练0、HGT模型加载0、GPU任务0。30个原文件折全部完成，"
        "%d个冗余探针结果、%d个敏感性结果；实际完成%d个C候选逻辑回归拟合，属于诊断计算。"%(
            report["probe_results"],report["signal_results"],report["accepted_logistic_fits"]),"",
        "## 1. 审查修正与实现","",
        "原NS-P6c没有限定字段适用人群，节点种类与不适用位可抬高AUC；这是旧探针口径的遗漏。"
        "本轮逐字段读取冻结behavior_schema.applicable，与已封存facts.node_kind按row_key和文件、代码身份对齐。"
        "CODE与STATIC存在位取交集，在该人群内计算[1%,99%]门槛。CTX必须在同一人群可用，不能静默换样本。"
        "one-hot的not_applicable位在适用人群内不变时自然不合格；某些稀有语义在适用人群内则新变为合格。","",
        "主分析仅CODE。CTX来自同一套facts，结果只称编码保真度，不作为独立冗余证据。"
        "额外对照只含facts.node_kind独热和冻结syntax字段；不读名称、漏洞标签或其他STATIC字段。"
        "J组目标已直接包含在对照输入中，其高AUC是结构性结果；N组描述分析支持/未知性，不等于漏洞语义。","",
        "直接复用未修改的p6c_core.logistic_probe、split_indices、原折、C={0.01,0.1,1,10}、seed=1。"
        "标准化与模型只拟合inner_train，C/阈值只由inner_val选择，outer_test仅评分。"
        "单类别或空折仍保留不可估，不借测试数据。全任务适用人群的比例筛选使用无漏洞标签数据，属于传导式特征审计。","",
        "新代码仅p6c2_core.py、p6c2_run.py、p6c2_report.py、p6c2_finalize.py与tests/test_p6c2.py。"
        "旧ns_p6c产物、源代码、图、标签、特征、初值、N-A/N-B计划与结果全部只读。"
        "CPU特征缓存复用上一轮SHA核验的文件；新目录只保存种类、对照输入、计划与诊断结果。","",
        "## 2. CODE：旧全部行与新适用人群","",
        "高AUC按每个位可估折的等权均值≥0.95；比例以可估位为分母，同时列出合格位数。"
        "新旧合格集合不同，不能只比较一个百分比；old_new.csv列出全部父组/原子组，"
        "paired_groups.csv另给同位同折的变化。","",
        "|任务|旧高AUC/可估位|新高AUC/可估位|旧/新合格位|新AUC中位数|",
        "|---|---:|---:|---:|---:|"]
    for r in report["old_new"]:
        if r["source"]=="code" and r["level"]=="all":
            lines.append("|%s|%d/%d|%d/%d|%d/%d|%s|"%(NAMES[r["task_id"]],r["old_high"],r["old_estimable"],
                r["new_high"],r["new_estimable"],r["old_eligible"],r["new_eligible"],number(r["new_median_auc"])))
    lines+=["","|任务|父组|合格/可估位|高AUC位|AUC中位数|全部折可估位|",
        "|---|---|---:|---:|---:|---:|"]
    for r in groups:
        if r["source"]=="code" and r["level"]=="parent":
            lines.append("|%s|%s|%d/%d|%d|%s|%d|"%(NAMES[r["task_id"]],r["group"],r["eligible_bits"],
                r["estimable_bits"],r["high_auc_bits"],number(r["median_fold_mean_auc"]),r["all_folds_estimable_bits"]))
    lines+=["","## 3. 节点/语法对照与CTX保真度","",
        "CODE减去对照使用同一位、同一折、两者均可估的AUC，先按位平均折，再汇总位；不把折或节点当作独立重复。"
        "完整父组差值见paired_groups.csv；全部逐折差值留本地产物并以SHA归档。","",
        "|任务|CODE−种类/语法 AUC差均值|匹配位数|匹配位折数|",
        "|---|---:|---:|---:|"]
    for r in report["paired_groups"]:
        if r["group"]=="ALL" and r["comparison"]=="CODE minus kind/syntax":
            lines.append("|%s|%s|%d|%d|"%(NAMES[r["task_id"]],number(r["mean_bit_mean_auc_delta"]),
                r["paired_bits"],r["paired_bit_folds"]))
    lines+=["","|任务|CTX高AUC位/可估位|CTX AUC中位数（由facts生成，仅编码保真度）|",
        "|---|---:|---:|"]
    for r in groups:
        if r["source"]=="ctx" and r["level"]=="all":
            lines.append("|%s|%d/%d|%s|"%(NAMES[r["task_id"]],r["high_auc_bits"],r["estimable_bits"],number(r["median_fold_mean_auc"])))
    lines+=["","## 4. 非SolidiFI：只含语句/条件的敏感性分析","",
        "|任务|原正例种类分布|原/限定正例数|原/限定节点数|",
        "|---|---|---:|---:|"]
    for task,r in report["positive_distributions"].items():
        lines.append("|%s|%s|%d/%d|%d/%d|"%(NAMES[task],", ".join(k+":"+str(v) for k,v in sorted(r["original_positive_kinds"].items())),
            sum(r["original_positive_kinds"].values()),r["statement_condition_positive"],r["all_n"],r["statement_condition_n"]))
    lines+=["","|任务|人群|输入|BF1均值%|BF1可估折|AUC均值|AUC可估折|",
        "|---|---|---|---:|---:|---:|---:|"]
    for r in report["signal_summary"]:
        lines.append("|%s|%s|%s|%s|%d/10|%s|%d/10|"%(NAMES[r["task_id"]],r["view"],r["source"],
            number(r["mean_BF1"]),r["BF1_folds"],number(r["mean_auc"]),r["auc_folds"]))
    lines+=["",
        "两种人群的节点总数和正例数不同，这是敏感性分析，不是对相同样本的新增模型收益。"
        "不删除困难文件、不调整标签或文件折。按inner_val AUC选C，再在inner_val选BF1阈值；"
        "AUC与BF1可能方向不同，二者均保留，不选更有利的指标。原分析从NS-P6c收据只读引用，未重算。","",
        "## 5. 验证、限制与下一步","",
        "%d项测试通过，0失败，%d条既有弃用警告；新增测试覆盖全部字段的适用范围、比例计算、"
        "源码身份、对照列边界、拟合/选择隔离、节点种类混杂反例、汇总分母与配对身份。"%(
            passed,warnings),
        "计划和来源SHA在执行前封存；每折有输入划分摘要、独立收据和不可估原因。"
        "旧354份DFG/作者运行源代码与8H生效修订继续核验。文档只追加，doc_check --expect-cjk通过后提交。","",
        "不把CTX可预测STATIC写成独立的冗余证明，不把较低线性AUC写成信息不存在。"
        "小幅移除敏感性也不能直接证明模型未使用STATIC；尺度差异与训练样本构成仍是待验证假设。"
        "本轮不改变STATIC尺度、匿名化视图、模型融合、训练损失或数据配比。NS-P7继续暂缓。","",
        "最终实验按用户安排在显存充足服务器另建批次；本机4GiB仅当前开发限制。"
        "本轮为CPU诊断，不受该显存限制，不混合本机与服务器结果。","",
        "## 6. 命令与归档","",
        "使用原mando环境，设置PYTHONDONTWRITEBYTECODE=1、TREE_SITTER_LIB_DIR、"
        "OMP_NUM_THREADS=2、MKL_NUM_THREADS=2、OPENBLAS_NUM_THREADS=2、CUDA_VISIBLE_DEVICES=''。","",
        "~~~bash",
        "python -B -m scripts.node_sem.p6c2_run prepare",
        "python -B -u -m scripts.node_sem.p6c2_run run",
        "python -B -m scripts.node_sem.p6c2_finalize",
        "python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests",
        "python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests",
        "python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py",
        "~~~","",
        "排他创建artifacts/ns_p6c2；重复运行须另设--out并重新封存。CPU 12进程仅改变调度。"
        "失败保留并停止，不自动重试。Git仅归档代码、计划、报告、紧凑表格、收据与SHA索引；"
        "逐行预测、对照数组、逐位候选明细留WSL，不上传权重或大缓存。运行中追加的日志不纳入结果身份清单；测试日志由tests_final单独绑定。报告入口在首次执行前收紧了这项归档规则，原源码与绑定保留在checks/finalizer_before_inventory_fix.py及reporting_binding.json，新绑定为reporting_binding_v2.json。"]
    text="\n".join(lines)+"\n"
    paths=[out/"REPORT.md",ROOT/"scripts/node_sem/NS_P6C2_REPORT.md"]
    for p in paths:
        with p.open("x",encoding="utf8") as f:f.write(text)
    brief="\n\n## 2026-11-08 NS-P6c2 完成（修改 AI：Codex）\n\n"+first+"\n\n"
    brief+=("按schema.applicable修正旧全部行探针的节点种类混杂；CTX改称facts编码保真度。"
        "30折CPU诊断完成，未加载HGT、未新增HGT训练；旧图、特征和NS-P6c结果保持不变。"
        "%d项测试通过；详情见scripts/node_sem/NS_P6C2_REPORT.md与artifacts/ns_p6c2。"
        "最终实验在显存充足服务器另建批次，本机显存只属开发限制。NS-P7暂缓。\n"%passed)
    for p in (ROOT/"HANDOVER.md",ROOT/"scripts/node_sem/PROGRESS.md"):
        with p.open("a",encoding="utf8") as f:f.write(brief)
    with (ROOT/"docs/training_changes_2026-10-07.md").open("a",encoding="utf8") as f:
        f.write("\n\n## 89. NS-P6c2 适用节点探针修正（2026-11-08，Codex）\n\n"+text)
    inventory=[dict(size_bytes=p.stat().st_size,**ref(p)) for p in sorted(out.rglob("*"))
        if p.is_file() and p.suffix!=".log" and p.name not in ("artifact_inventory.json","complete.json","progress.json")]
    write(out/"artifact_inventory.json",dict(files=inventory,generation_commands="NS_P6C2_REPORT.md section 6"))
    write(out/"complete.json",dict(passed=True,report=ref(out/"report.json"),markdown=ref(out/"REPORT.md"),
        inventory=ref(out/"artifact_inventory.json"),reporting_binding=ref(out/"reporting_binding_v2.json"),
        tests=ref(out/"checks/tests_final.json"),folds=30,new_HGT_fits=0,GPU_used=False))


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default=str(OUT));a=ap.parse_args();finish(a.out)
