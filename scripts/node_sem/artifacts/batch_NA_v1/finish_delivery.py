"""Post-completion documentation/archive only; never imports or runs training.
Waits for the sealed N-A controller to finish, verifies immutable evidence,
writes the requested report and append-only records, then commits an explicit
small-file allowlist locally. No push, retry, GPU operation or metric selection.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

ROOT = Path(__file__).resolve().parents[4]
BATCH = Path(__file__).resolve().parent
REPORT = ROOT / "scripts/node_sem/NS_P5A_REPORT.md"
DOCS = ("HANDOVER.md", "docs/training_changes_2026-10-07.md", "scripts/node_sem/PROGRESS.md")
MARKER = "NS-P5A_FINAL_DELIVERY_V1"

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def check(r):
    p = Path(r["path"])
    if digest(p) != r["sha256"]:
        raise ValueError("SHA mismatch: " + str(p))
    return p

def write(path, value):
    with Path(path).open("x", encoding="utf8") as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write("\n")

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT)] + list(args), text=True).strip()

def need_complete():
    s = read(BATCH / "controller_status.json")
    if s["state"] != "complete" or s["completed"] != 240 or s.get("error"):
        raise ValueError("Full controller completion required before final delivery")
    return s

def render(result, evidence):
    primary = next(r for r in result["paired"] if r["task_id"] == "reentrancy_node"
        and r["graph"] == "G3R" and r["name"] == "S4" and r["baseline_name"] == "S0o"
        and r["checkpoint"] == "best")
    lines = ["# NS-P5A：N-A 原名视图完整实验报告", "",
        "本批是预先登记的本机 RTX3050 先导批次，默认 TF32 开启；正式训练 240/240、训练后注意力诊断 120/120 已验收。最终实验将按用户安排在显存充足服务器另建复现批次。本机 4GiB 是当前开发限制；两批不合并、不择优，结论不一致时都报告。", "",
        "修改 AI：Codex。输入代码 HEAD：" + evidence["input_head"] + "。", "",
        "## 完成范围", "",
        "- 四个任务，合约 5 折、节点 10 折；{S0o,S1o,S2,S4} × {G0,G3R}，seed=1，共 240 个独立正式 fit。两个先行 pilot 计入这 240 次。",
        "- 原名特征，固定 L-audit 标签视图和分组嵌套划分；inner_val 选择严格最低 loss 的 best、执行早停；outer_test 只在训练后评分。完整固定图前向，不能称独立外部测试。",
        "- 保留原图、DFG/HGT/tokenizer、标签、折、初值和训练配置；正式最多 50 轮，无单轮验收覆盖。best/last、折均值/pooled OOF、原标签辅助结果分别保存。",
        "- 匿名 8H 只作零步初始化来源和历史参考，不复用匿名成绩作为原名配对基线。G0+S4 仍含 DFG 派生特征，不是完全无 DFG 的对照。", "",
        "## 主结果", "",
        "| 任务 | 图/配置 | best Buggy-F1 折均值（%） | 样本标准差 |",
        "|---|---|---:|---:|"]
    for r in result["aggregates"]:
        if r["checkpoint"] == "best" and r["metric"] == "buggy_f1":
            lines.append("| {} | {} | {:.4f} | {:.4f} |".format(r["task_id"], r["profile"], r["mean"], r["sample_sd"]))
    lines += ["", "预登记主终点：重入节点 G3R，S4−S0o = **{:+.4f} 个百分点**；描述性 95% bootstrap 区间 [{:+.4f}, {:+.4f}]；10 折提升/持平/下降 = {}/{}/{}。".format(
        primary["difference_mean_pp"], *primary["bootstrap_ci95_pp"], primary["improved"], primary["tied"], primary["worsened"]),
        "该比较 Wilcoxon 原始 p = {:.6g}，四项预登记 Holm 校正 p = {:.6g}。折间训练数据重叠，单 seed 不能证明独立重复或语义因果贡献。".format(
            primary["p_raw"], result["holm"]["p_adjusted"]["S4-S0o"]), "",
        "S* = {}，只依据 inner_val 封存，作为参考，不替换预登记 S4。".format(result["selection"]["selected"]), "",
        "## 验收与资源", "",
        "- 32/32 载体及同种子模型逐位一致；6/6 非正式 CPU 验收 fit（1/2/2 轮两条路径），history、参数、Adam/调度器与预测一致。",
        "- 单元回归 3759 通过，0 失败、0 跳过，42 条既有警告；37 项定向测试已包含其中。",
        "- 240 个正式收据逐一校验输入/配置/初值/checkpoint/导出文件；设备类型与默认 TF32 一致；120 个 best checkpoint 注意力诊断均为 eval，无训练和权重修改。",
        "- 正式 fit 累计墙钟 {:.2f} 小时；最大 PyTorch allocated {:.1f} MiB、reserved {:.1f} MiB；所有任务中的最低整卡空闲 {:.1f} MiB；memory_tight 共 {} 项。子阶段计时有重叠，不能相加。".format(
            evidence["fit_wall_seconds"]/3600, evidence["max_allocated_mib"], evidence["max_reserved_mib"],
            evidence["min_free_mib"], evidence["memory_tight_fits"]),
        "- 正式失败记录 {} 份，外部中断记录 {} 份；失败现场保留，只允许已批准且原因确认的外部终止最多重跑一次。".format(
            evidence["failures"], evidence["external_interruptions"]), "",
        "## 决策与限制", "",
        "用户批准先运行重入节点和合约两个正式 pilot，再补完剩余 39 个主比较 fit；只在新 execution_revision 中绑定顺序，旧 plan/seal 不变。",
        "S0o 使用原 token；S1o、S2、S4 是已封存的特征配置，新增载体快路径只去除重复校验。正式训练仍调用冻结 trainer.fit，CPU 等价验收证明计算未改。",
        "注意力统计逐关系/head，同时区分单邻居权重必为 1 与多邻居集中；N-A 没有门控配置，门控分布不适用。",
        "SolidiFI/非 SolidiFI 分层是描述性分析；L-audit 不是已确立金标准。Wilson 区间只用于 Precision/Recall，BF1 报点估计。原名可能保留注入标记线索，不将分数解释为纯漏洞语义能力。",
        "本轮没有运行 N-B、多 seed、匿名主实验、七类全量、服务器训练或新的图/模型扩展。没有自动 push。", "",
        "## 文件与实际命令", "",
        "主产物：scripts/node_sem/artifacts/batch_NA_v1/。reports/REPORT.md、report.json、best_fold_means.csv、last_fold_means.csv、paired.csv、pooled_oof.csv、errors.csv、nonSolidifi_nodes.csv、resources.csv，以及 prediction_changes.json、relation_support_gradients.json 保存明细。",
        "execution_revision.json / authorization.json 单独绑定本轮；selection.json 在读取 outer 结果前封存。complete.json 与 attention/complete.json 是完整性索引。weights/NPZ 等重产物保留 WSL，不额外复制到 C 盘。", "",
        "```bash", "conda activate mando", "cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11",
        "export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64",
        "export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2",
        "CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.p5a_acceptance carriers",
        "CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.p5a_acceptance cpu",
        "CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/node_sem/tests",
        "CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests",
        "CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py",
        "CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.batch_na_controller seal",
        "# seal 已存在，不能重复创建；实际 tmux 启动命令存于 launch.json",
        "CUDA_VISIBLE_DEVICES=0 python -m scripts.node_sem.batch_na_controller run",
        "```", "", "完成后停止于 N-A 报告，未自动开启下一批。", ""]
    return "\n".join(lines), primary

def finalize():
    need_complete()
    delivery = read(BATCH / "delivery_revision.json")
    for item in delivery["sources"] + delivery["documents_before_final_append"]:
        check(item)
    if (BATCH / "delivery_complete.json").exists():
        raise ValueError("Delivery already completed; do not overwrite")
    revision = read(BATCH / "execution_revision.json")
    auth = read(BATCH / "authorization.json")
    check(auth["execution_revision"]); check(revision["plan"]); check(revision["seal"])
    plan = read(BATCH / "plan.json")
    for rel, sha in dict(plan["runtime"], **revision["runtime"]).items():
        if digest(ROOT / rel) != sha:
            raise ValueError("Frozen runtime differs: " + rel)
    for reference in revision["gates"].values():
        if not read(check(reference))["passed"]:
            raise ValueError("Acceptance gate failed")
    final = read(BATCH / "complete.json")
    if final["formal_fits"] != 240 or not final["passed"] or len(final["receipts"]) != 240:
        raise ValueError("Formal matrix incomplete")
    receipts = [read(check(r)) for r in final["receipts"]]
    keys = [(r["job"]["task_id"], r["job"]["profile"], r["job"]["name"], r["job"]["fold"]) for r in receipts]
    if len(set(keys)) != 240:
        raise ValueError("Duplicate formal identity")
    for r in receipts:
        if r["actual_device"] != r["job"]["device_policy"]:
            raise ValueError("Device comparison differs")
        for item in r["artifacts"]:
            check(item)
    attention = read(BATCH / "attention/complete.json")
    if not attention["passed"] or attention["count"] != 120 or len(attention["artifacts"]) != 120:
        raise ValueError("Attention matrix incomplete")
    for item in attention["artifacts"]:
        check(item)
    report_receipt = read(BATCH / "reports/receipt.json")
    for item in report_receipt["artifacts"]:
        check(item)
    result = read(BATCH / "reports/report.json")
    if not result["passed"] or result["formal_fits"] != 240 or result["selection"]["outer_test_used"]:
        raise ValueError("Report/selection identity differs")
    before = read(BATCH / "before_P5A.json")
    for name, old in before["documents"].items():
        if hashlib.sha256((ROOT/name).read_bytes()[:old["size"]]).hexdigest() != old["sha256"]:
            raise ValueError("Historical document prefix differs: " + name)
    ev = dict(input_head=before["head"], formal_fits=240, attention_evals=120,
        fit_wall_seconds=sum(r["total_seconds"] for r in receipts),
        max_allocated_mib=max(r["resources"]["peak_allocated_mib"] for r in receipts),
        max_reserved_mib=max(r["resources"]["peak_reserved_mib"] for r in receipts),
        min_free_mib=min(r["resources"]["minimum_free_mib"] for r in receipts),
        memory_tight_fits=sum(bool(r["resources"]["memory_tight"]) for r in receipts),
        failures=len(list((BATCH/"runs").glob("*/attempt_*/failure.json"))),
        external_interruptions=len(list((BATCH/"runs").glob("*/attempt_*/external_interruption.json"))),
        finalized_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    report_text, primary = render(result, ev)
    with REPORT.open("x", encoding="utf8") as f:
        f.write(report_text)
    title = "\n\n## NS-P5A N-A 全量完成（修改 AI：Codex）\n\n<!-- " + MARKER + " -->\n\n"
    body = ("240/240 原名正式 fit、120/120 G3R best 注意力 eval 已验收；两个正式 pilot 计入 240，不重复训练。"
        "32 组载体/模型逐位证明和 6 次 CPU 等价 fit 已通过；3759 单元回归通过，0 失败/跳过，42 既有警告。"
        "正式配置与计划逐字段相同，全部 checkpoint/预测重载和设备/TF32 一致性通过。\n\n"
        "主终点重入节点 G3R 的 S4−S0o 为 {:+.4f} 个百分点，提升/持平/下降 {}/{}/{} 折；Holm 校正 p={:.6g}。"
        "S*={} 仅按 inner_val 选择；best/last、折均值/OOF、原标签与 L-audit 分开。"
        "完整表、统计边界和命令见 NS_P5A_REPORT.md 与 batch_NA_v1/reports。\n\n"
        "最终服务器另建批次并按相同预登记复现；本机 4GiB 仅当前限制，两批不混合、不择优。"
        "本轮没有 N-B、多 seed、七类扩展或服务器运行；没有自动 push。\n").format(
            primary["difference_mean_pp"], primary["improved"], primary["tied"], primary["worsened"],
            result["holm"]["p_adjusted"]["S4-S0o"], result["selection"]["selected"])
    sizes = {}
    for name in DOCS:
        p = ROOT/name
        if MARKER in p.read_text(encoding="utf8"):
            raise ValueError("Final record already present: " + name)
        sizes[name] = p.stat().st_size
        extra = ""
        if name.startswith("docs/"):
            extra = ("\n### 85.5 最终验收补充\n\n" + json.dumps(ev, ensure_ascii=False, indent=2) +
                "\n\n本节追加到先前“验收/训练尚未开始”的时间点之后，不改历史状态。"
                "execution_revision SHA=" + digest(BATCH/"execution_revision.json") +
                "；原 plan/seal SHA 保持 §85.1 所记录值。正式失败与外部中断数量包含保留现场，重跑不计新 seed。"
                "收尾脚本仅在 controller complete 且 240/120 索引与文件 SHA 均通过后写报告、追加文档和本地提交；不会训练、修改旧产物或启动下一批。\n")
        with p.open("a", encoding="utf8") as f:
            f.write(title + body + extra)
    python = "/home/zhao/miniconda3/envs/mando/bin/python"
    subprocess.run([python, "-B", "-m", "scripts.node_sem.doc_check", "--expect-cjk",
        str(REPORT)] + [str(ROOT/n)+":"+str(sizes[n]) for n in DOCS],
        cwd=str(ROOT), check=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", CUDA_VISIBLE_DEVICES=""))
    write(BATCH/"delivery_evidence.json", ev)
    write(BATCH/"delivery_documents.json", dict(files=[dict(path=str(p),sha256=digest(p))
        for p in [REPORT]+[ROOT/n for n in DOCS]], old_sizes=sizes))
    # Stage only reviewed NodeSem code/docs and compact evidence, never checkpoints or user changes.
    if git("rev-parse", "HEAD") != before["head"] or git("diff", "--cached", "--name-only"):
        raise ValueError("HEAD/index changed: reports complete, local commit requires review")
    code = ["na_carrier.py","batch_na_worker.py","batch_na_controller.py","p5a_acceptance.py","reporting.py","na_attention.py",
            "tests/test_batch_na_worker.py","tests/test_na_reporting.py","NS_P5A_REPORT.md"]
    paths = [ROOT/"scripts/node_sem"/n for n in code] + [ROOT/n for n in DOCS] + [Path(__file__)]
    names = ["execution_revision.json","authorization.json","decisions_P5A.json","power_check.json",
        "pilot_acceptance.json","complete.json","selection.json","selection.seal.json","launch.json",
        "delivery_evidence.json","delivery_documents.json","delivery_revision.json",
        "acceptance/carriers/carrier_proof.json","acceptance/cpu/cpu_proof.json",
        "acceptance/regressions_final.json","acceptance/comparator_provenance.json",
        "attention/complete.json"]
    paths += [BATCH/n for n in names if (BATCH/n).is_file()]
    paths += [p for p in (BATCH/"reports").iterdir()
        if p.is_file() and p.suffix in (".md",".json",".csv") and p.stat().st_size < 5000000]
    for p in paths:
        p.resolve().relative_to(ROOT)
        if p.stat().st_size >= 10000000:
            raise ValueError("Unexpected large archive file: " + str(p))
    subprocess.run(["git","-C",str(ROOT),"add","-f","--"]+
        [str(p.relative_to(ROOT)) for p in paths], check=True)
    subprocess.run(["git","-C",str(ROOT),"diff","--cached","--check"],check=True)
    subprocess.run(["git","-C",str(ROOT),"commit","-m","Complete NS-P5A original-name N-A execution and results"],check=True)
    write(BATCH/"delivery_complete.json",dict(passed=True,commit=git("rev-parse","HEAD"),
        report=dict(path=str(REPORT),sha256=digest(REPORT)),pushed=False,
        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))

def main():
    p=argparse.ArgumentParser();p.add_argument("--wait",action="store_true");a=p.parse_args()
    if a.wait:
        while True:
            s=read(BATCH/"controller_status.json")
            if s["state"]=="stopped":
                raise RuntimeError("Controller stopped; no successful final delivery claimed")
            if s["state"]=="complete":break
            # Read-only polling; does not inspect scores before training completes.
            time.sleep(30)
    finalize()

if __name__=="__main__":
    try: main()
    except BaseException as error:
        failure=BATCH/("delivery_failure_"+str(os.getpid())+".json")
        if not failure.exists():
            write(failure,dict(error=repr(error),traceback=traceback.format_exc()))
        raise
