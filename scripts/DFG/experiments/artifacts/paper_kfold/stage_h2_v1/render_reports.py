"""Render accepted H2 outputs only; never load a model or train."""
from pathlib import Path
import csv,json,statistics,hashlib
O=Path(__file__).resolve().parent
R=O.parents[5]
def load(name): return json.loads((O/name).read_text(encoding="utf8"))
def csvrows(name):
    with (O/name).open(encoding="utf8") as f:return list(csv.DictReader(f))
def table(headers, rows):
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"]+
        ["| "+" | ".join(map(str,row))+" |" for row in rows])+"\n"
def number(x): return format(float(x),".4f")
def label(task):
    return ("重入" if task.startswith("reentrancy") else "访问控制")+("·合约" if task.endswith("contract") else "·节点")
def main():
    report=load("report.json");plan=load("plan.json");execution=load("execution.json")
    assert report["status"]=="complete" and report["complete_three_variants"]==90 and execution["returncode"]==0
    best=csvrows("three_variant_best.csv");last=csvrows("three_variant_last.csv")
    paired=csvrows("paired_statistics.csv");file_errors=csvrows("file_error_analysis.csv")
    probs=csvrows("prediction_change_summary.csv");resources=csvrows("resource_folds.csv")
    supports=csvrows("enhancement_support.csv");grad=csvrows("gradient_support_detail.csv")
    tasks=list(dict.fromkeys(x["task_id"] for x in best))
    text=["# E2/E3a/E3b 完整三变体消融报告","",
        "2026-10-15；执行与分析：Codex。26次新增E3a + 4个Stage G复用 = 30个E3a；合并H1的60个E2/E3b，共90个正式模型。",
        "全部主结果为 **CV validation**，同一val选best并评分；节点按HCG节点计分。不是独立测试。best严格按最低验证loss选择，last仅作辅助。",
        "E2为修复标量DDG；E3a增加STATE_DEF_USE；E3b再增加STATE_ACCESS_ORDER及EXTERNAL_CALL_BEFORE_STATE_WRITE。",
        "训练、数据、模型、tokenizer、标签、折和初值全部冻结。三组差值包括关系参数、聚合和优化轨迹改变，不等同纯语义因果贡献。",
        "重入E3b−E3a包含两种顺序关系的联合增量，不能拆成各自贡献；访问控制没有调用→写入边，不能将其差值解释为调用关系收益。",""]
    for ck,name in [("best","fold_statistics.csv"),("last","last_fold_statistics.csv")]:
        stats=csvrows(name)
        text += ["## "+ck+"：等权折均值与样本标准差","",
            table(["任务","变体","BF1 ± SD","MF1 ± SD","Precision ± SD","Recall ± SD"],
                  [[label(x["task_id"]),x["variant"]]+[number(x[m+"_mean"])+" ± "+number(x[m+"_sample_std"]) for m in ("buggy_f1","macro_f1","precision","recall")] for x in stats]),
            "差值为每折相减后求等权均值；百分点；折间SD是描述统计，不是独立seed重复方差。",
            table(["任务","对照","ΔBF1 ± SD","ΔMF1 ± SD","BF1升/平/降"],
                  [[label(x["task_id"]),x["contrast"],number(x["buggy_f1_delta_pp_mean"])+" ± "+number(x["buggy_f1_delta_pp_sample_std"]),
                    number(x["macro_f1_delta_pp_mean"])+" ± "+number(x["macro_f1_delta_pp_sample_std"]),
                    "/".join(x["buggy_f1_"+s] for s in ("improved","tied","declined"))] for x in paired if x["checkpoint"]==ck]),""]
    for task in tasks:
        text += ["## "+label(task)+"：逐折结果",""]
        for ck,rows in [("best",best),("last",last)]:
            text += ["### "+ck,"",
                table(["fold","变体","BF1","MF1","Precision","Recall","TN/FP/FN/TP","best/last epoch（0起始）"],
                    [[x["fold"],x["variant"]]+[number(x[m]) for m in ("buggy_f1","macro_f1","precision","recall")]+
                    [x["tn_fp_fn_tp"],x["best_epoch"]+"/"+x["last_epoch"]] for x in rows if x["task_id"]==task]),""]
    text += ["## Pooled OOF：另报、不替换等权均值","",
        "全部原文件恰好落在一个验证折；预测按文件/原节点身份匹配，标签从冻结图独立核对。pooled OOF仍使用同val选模后的预测，不是独立测试。",
        table(["任务","变体","checkpoint","BF1","MF1","P","R","TN/FP/FN/TP"],
            [[label(x["task_id"]),x["variant"],x["checkpoint"]]+[number(x[m]) for m in ("buggy_f1","macro_f1","precision","recall")]+[x["tn_fp_fn_tp"]] for x in csvrows("pooled_oof.csv")]),""]
    text += ["## 错误与概率变化",""]
    aggregated=[]
    for task in tasks:
        for ck in ("best","last"):
            for contrast in ("E3a-E2","E3b-E3a","E3b-E2"):
                subset=[x for x in probs if (x["task_id"],x["checkpoint"],x["contrast"])==(task,ck,contrast)]
                n=sum(int(x["n"]) for x in subset)
                aggregated.append([label(task),ck,contrast]+[sum(int(x[k]) for x in subset) for k in ("fixed","regressed","prediction_changed","probability_only")]+
                    [number(100*sum(float(x["mean_abs_probability_delta"])*int(x["n"]) for x in subset)/n)])
    text += [table(["任务","checkpoint","对照","纠正","新增错误","类别改变","仅概率改变","平均绝对概率变化(pp)"],aggregated),
        "各文件及每个改变节点的cohort、source SHA、原节点ID、预测和概率见file_error_analysis.csv、error_changes.csv与oof_predictions.json；不按CSV行号假定身份。",""]
    focus={("reentrancy_author_node","buggy_18.sol"),("reentrancy_author_node","buggy_36.sol"),
           ("access_control_author_node","buggy_18.sol"),("access_control_author_node","buggy_26.sol")}
    text += ["## 预先指定困难文件","",
        table(["任务","文件","source SHA","fold","checkpoint","对照","错误前→后","FP前→后","FN前→后","纠正/新增"],
            [[label(x["task_id"]),x["file"],x["source_sha256"],x["fold"],x["checkpoint"],x["contrast"],
              x["before_errors"]+"→"+x["after_errors"],x["before_fp"]+"→"+x["after_fp"],x["before_fn"]+"→"+x["after_fn"],x["fixed"]+"/"+x["regressed"]]
             for x in file_errors if (x["task_id"],x["file"]) in focus]),
        "以上错误相对冻结作者标签定义，不据此证明标签本身正确或错误；本轮没有改变或重新审核标签。",""]
    text += ["## 关系支持与梯度",""]
    sr=[]
    for task in tasks:
        for v in ("E2","E3a","E3b"):
            for rel in ("STATE_DEF_USE","STATE_ACCESS_ORDER","EXTERNAL_CALL_BEFORE_STATE_WRITE"):
                ss=[x for x in supports if (x["task_id"],x["variant"],x["relation"])==(task,v,rel)]
                tr=[int(x["train"]) for x in ss];va=[int(x["val"]) for x in ss]
                sr.append([label(task),v,rel,str(min(tr))+"–"+str(max(tr)),str(min(va))+"–"+str(max(va)),sum(x==0 for x in tr),sum(x==0 for x in va)])
    text += [table(["任务","变体","关系","train边范围","val边范围","train=0折","val=0折"],sr),
        "canonical梯度状态："+json.dumps(report["gradient_status"],ensure_ascii=False)+"；非有限记录="+str(report["nonfinite_gradient_records"])+"。",
        "训练未见但已注册关系保留，不要求其具有非零监督梯度。参数更新可能包含weight decay；梯度历史和参数变化分开保存。计算接入不证明完整Solidity依赖语义或每条边的因果收益。",""]
    rr=[]
    for task in tasks:
        for v in ("E2","E3a","E3b"):
            items=[x for x in resources if x["task_id"]==task and x["variant"]==v]
            rr.append([label(task),v,items[0]["parameters"],number(max(int(x["peak_allocated_bytes"]) for x in items)/2**30),
                number(max(int(x["peak_reserved_bytes"]) for x in items)/2**30),
                min(int(x["minimum_whole_card_free_mib"]) for x in items),
                number(sum(float(x["wall_seconds_monotonic"]) for x in items))])
    text += ["## 资源与训练规则","",table(["任务","变体","参数量","peak allocated GiB","peak reserved GiB","最低整卡free MiB","fit耗时合计(s)"],rr),
        "H2控制器耗时："+number(execution["seconds"])+"秒；不同早停轮数、历史批次和系统显存竞争使这些时间不能直接当公平速度对比。",
        "配置澄清：合约initial_lr=0.0005、max_lr=0.01、div_factor=20、weight_decay=5e-6；节点initial_lr=0.0002、max_lr=0.005、div_factor=25、weight_decay=0。旧H1报告简略段落只写了合约配置，H2使用各task manifest的真实配置。",
        "Adam/OneCycle、50轮上限、patience7/delta0.001、原argmax均未改变。正式fit前恢复原fit_seed；只加载已保存的untrained_initial，未使用smoke/已训练权重。","",
        "## 历史参照与解释边界","",
        "E0/E1仍是历史同折参照，初始化版本不同，不能称本批严格共同初始化对照。H1的baseline_statistics.csv保留原样。",
        "单seed；折间训练集重叠；没有独立测试；有限状态语义/覆盖与作者标签上下文限制仍在。不能把节点数当独立实验数扩大显著性，也不能由两个类别直接推广七类。",
        "本轮停止于90个正式结果的完整三变体消融；未新增seed、其他类别、关系或模型。",""]
    historical_dir=Path(plan["historical_h1_plan"]).parent
    old_manifest=json.loads((historical_dir/"delivery_manifest.json").read_text())
    historical_name="baseline_statistics.csv"
    payload=(historical_dir/historical_name).read_bytes()
    assert hashlib.sha256(payload).hexdigest()==old_manifest["top_level_delivery_sha256"][historical_name]
    historical=list(csv.DictReader(payload.decode("utf8").splitlines()))
    (O/"historical_baseline_statistics.csv").write_bytes(payload)
    (O/"historical_reference_provenance.json").write_text(json.dumps({
        "source":str(historical_dir/historical_name),"sha256":hashlib.sha256(payload).hexdigest(),
        "comparison_role":"historical_same_fold_not_common_initialized",
        "source_delivery_manifest_sha256":hashlib.sha256((historical_dir/"delivery_manifest.json").read_bytes()).hexdigest()
        },indent=2)+"\n",encoding="utf8")
    text += ["## E0/E1 历史参照数值","",
        "以下是旧批次已验收结果，单独保留，不据此计算本批严格消融。",
        table(["任务","历史变体","checkpoint","BF1 ± SD","MF1 ± SD"],
            [[label(x["task_id"]),x["variant"],x["checkpoint"],
              number(x["buggy_f1_mean"])+" ± "+number(x["buggy_f1_sample_std"]),
              number(x["macro_f1_mean"])+" ± "+number(x["macro_f1_sample_std"])] for x in historical]),""]
    (O/"E2_E3_COMPLETE_ABLATION_REPORT.md").write_text("\n".join(text),encoding="utf8")
    runs=list((O/"runs").rglob("receipt.json"))
    failures=list((O/"runs").rglob("*.failure.json"))
    brief=["# Stage H2 执行与验收报告","",
        "2026-10-15，Codex。26个新E3a结果、4个Stage G fold0复用，共30个；联合E2/E3a/E3b共90个正式结果。",
        "新增收据数="+str(len(runs))+"；失败sidecar数="+str(len(failures))+"。完整三变体结果、逐折统计和解释见[E2_E3_COMPLETE_ABLATION_REPORT.md](E2_E3_COMPLETE_ABLATION_REPORT.md)。",
        "HEAD："+plan["base_git_head"]+"。原H1/H2预留plan及seal未改；原预留execution_authorized=false保持，新H2独立plan记录本轮授权。",
        "沿用H1专用只读归档核验。启动前H1 60结果、30份E3a初值、四个G E3a fold0通过验证；本批封存"+str(len(plan["runtime_code_sha256"]))+"份运行源码、"+str(len(plan["frozen_files"]))+"项固定资产。",
        "必要测试71通过/0失败/0跳过，4条既有DGL弃用警告。未重跑四任务smoke或扩大静态审查。原fit、模型装配、监督、checkpoint算法直接复用。",
        "best/last重载一致由每fit收据验证；90组预测与冻结标签按身份独立复算；OOF无重复文件/节点，仍为CV validation。",
        "源文件身份和跨cohort同名文件在导出中携带source SHA；困难文件没有删除或重标。",
        "代码范围：scripts/DFG/experiments/e23_h2/；新产物仅stage_h2_v1/；历史H1/G结果只读。训练数值代码封存后未改。",
        "正式运行命令：","",
        "~~~bash","conda activate mando","cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11",
        "export PYTHONPATH=$PWD","export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2",
        "export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64",
        "python -u -B -m scripts.DFG.experiments.e23_h2.control run",
        "python -B -m scripts.DFG.experiments.e23_h2.control verify",
        "python -B -m scripts.DFG.experiments.e23_h2.control summarize","~~~","",
        "已成功结果自动核验复用；本轮结束后不需要重训。若HEAD在后续归档发生变化，不改旧seal；新增只读归档验收另行处理。",""]
    (O/"H2_RESULT_REPORT.md").write_text("\n".join(brief),encoding="utf8")
if __name__=="__main__": main()

# Final interpretation is a separately reviewed, output-only artifact.
for report_name in ['H2_RESULT_REPORT.md', 'E2_E3_COMPLETE_ABLATION_REPORT.md']:
    with (O / report_name).open('a', encoding='utf-8') as report_file:
        report_file.write((O / 'interpretation.md').read_text(encoding='utf-8'))
