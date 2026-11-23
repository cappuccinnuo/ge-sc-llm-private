"""Append measured final counts once and synchronize the current handover after all scientific gates."""
from collections import Counter
from datetime import date
from pathlib import Path

from population import OUT, ROOT, load, sha256


def append(path, section):
    with path.open("a",encoding="utf8",newline="\n") as fp:
        fp.write("\n"+section.strip()+"\n")


def main():
    module=ROOT/"compile_repair"
    audit=load(OUT/"final_audit.json")
    finish=load(OUT/"measurement_completion.json")
    frozen=load(OUT/"policy.json")
    real=load(OUT/"external_summary.json")
    benchmark=load(OUT/"benchmark_summary.json")
    official=load(OUT/"frozen_mando/summary.json")
    archives=load(OUT/"record_archives.json")
    assert audit["mando_implementation_matches_worktree"] and finish["status"]=="complete"
    tables=(OUT/"final_tables.md").read_text(encoding="utf8")
    assert sha256(OUT/"final_tables.md")==finish["tables_sha256"]
    label="### CP5.1 最终验收与资源"
    report=module/"CP5_REPORT.md"
    assert label not in report.read_text(encoding="utf8") and "### 使用测试集前的选版记录" in report.read_text(encoding="utf8")
    results=benchmark["scores"][frozen["policy"]]
    solved={s:sum(v["compiled"] for v in group.values()) for s,group in results.items()}
    sample={s:sum(v["units"] for v in group.values()) for s,group in results.items()}
    assert sum(sample.values())==2664
    headline=("真实语料 "+str(real["d3"])+"/9,138 通过 D3，其中 "+str(real["truncated"])+" 个触发编译组合上限。"
              "基准开发集 "+str(solved["dev"])+"/"+str(sample["dev"])+"、测试集 "+str(solved["test"])+"/"+
              str(sample["test"])+" 通过编译和 D3。")
    ir=load(OUT/"partial_ir_summary.json")
    observed=ir["selected_measurements"]["real_full"][0]
    ir_evidence=("冻结规则下该单元的整图 SHA256 与开发阶段确认的部分 IR 图一致。" if
                 observed.get("exactly_matches_confirmed_partial_graph") else
                 "冻结规则下该单元与已确认开发图的逐字节比较见收据。")
    ir_note=("D3 检查编译、节点映射和合约覆盖。开发单元 cp3_19463 的 readOracle 出现 SlithIR 生成中断。"
             +ir_evidence+"可核对的单元收据与各阶段原生日志的独立事件数见 partial_ir_summary.json。"
             "同一单元或未接受的候选均可多次产生日志，无法据此估计全部成功图的 IR 缺失率。")
    defaults="正式默认规则为 `"+frozen["policy"]+"`，K="+str(frozen["limit"])+"。"
    metrics=Counter()
    for stage in ("real_full","benchmark"):
        metrics.update(audit["mechanical"][stage])
    provenance=("外部全量与基准合计核验 "+str(metrics["rounds"])+" 个候选轮，包含被拒绝的轮次。"
                "其中新增文件编辑 "+str(metrics["additive_edits"])+" 次，导入字符串改写 "+str(metrics["rewrite_edits"])+
                " 次。未改变的输入按原始文件 SHA 复核。各阶段和逐项调用收据索引见 `*_provenance.json`、`invocation_seals.json`。")
    suite_text="。".join(k+" 为 "+v["summary"] for k,v in audit["suites"].items())+"。"
    code="\n".join("| "+k+" | "+str(v["added"])+" | "+str(v["removed"])+" | "+", ".join("`"+f+"`" for f in v["functions"])+" |" for k,v in sorted(audit["changed"].items()))
    durations={
        "新增 400 个移动样本的触发与逆操作":load(OUT/"moved_summary.json")["elapsed_seconds"],
        "真实开发集三规则，有效单元耗时之和":load(OUT/"real_dev_summary.json")["elapsed_seconds"],
        "8 个缺包开发样本的三规则":load(OUT/"package_dev_summary.json")["elapsed_seconds"],
        "冻结策略的完整基准":benchmark["elapsed_seconds"],
        "锁版本遮蔽参照":load(OUT/"real_masked_summary.json")["elapsed_seconds"],
        "9,138 个外部单元，两分片工作进程耗时之和":load(OUT/"real_full_summary.json")["sum_worker_seconds"],
        "最终 MANDO 回归":official["elapsed_seconds"]}
    times="\n".join("| "+k+" | "+str(round(v,2))+" |" for k,v in durations.items())
    append(report,tables+"\n\n"+label+"\n\n"+headline+" "+provenance+"\n\n"+
        ir_note+"\n\n"+"最终 MANDO CLI 加载完整离线索引。843 张图与 v5 逐字节相同，3 项历史失败保留，成功图触发第 2–4 步 0 次。"
        "实施文件仍为 18 个。354 项 DFG 引用与基线一致。最终测试为 "+suite_text+"\n\n"+
        "| 生产文件 | 增加行 | 移除行 | 改动函数 |\n|---|---|---|---|\n"+code+"\n\n"+
        "| 阶段 | 秒 |\n|---|---|\n"+times+"\n\n"+
        "开发耗时为 6,948 份完整观测各自的墙钟时间之和。中断前另有 31 次 solc 调用，其耗时之和为 "+str(round(load(OUT/"development_continuation/resume_summary.json")["old_incomplete_solc_seconds"],3))+" 秒，单独留存。两个外部语料分片分别记录并作加总。正式阶段边界与逐条命令见 `test_environment_resume_v2/stage_runs.jsonl`，首轮停点留在原 `stage_runs.jsonl`。CPU 本地执行，LLM 调用 0，费用 0 美元。")
    append(module/"PROGRESS.md",defaults+" "+headline+" 400 项移动逆操作和最终 846 项 MANDO 回归通过。结果见 `CP5_REPORT.md`、`final_audit.json` 和 `external_summary.json`。")
    append(module/"docs/CHANGE_LOG.md","最终验收采用冻结后的默认设置。"+defaults+" "+headline+" "+provenance+
           " 两个分片按冻结输入顺序合并，逐行核验 9,138 个不同身份。最终测试与生产文件变化见 `final_audit.json`，详细表格见 `CP5_REPORT.md`。"
           "本轮本地提交，下一步为独立复核。")
    handover=module/"docs/HANDOVER.md"
    text=handover.read_text(encoding="utf8")
    phrase="真实开发集上的三规则比较决定依赖选择规则和每单元编译组合上限，之后以固定设置评估测试集。"
    assert text.count(phrase)==1
    text=text.replace(phrase,defaults+" "+headline)
    phrase="| 下一步 | CP5.1 → 审查 → CP6 |"
    assert text.count(phrase)==1
    text=text.replace(phrase,"| 下一步 | 独立复核 CP5.1 的策略、基准和外部主因表，之后按方案进入 CP6。 |")
    with handover.open("w",encoding="utf8",newline="\n") as fp: fp.write(text)
    append(handover,"完成全量后，第 0–1 节同步为最终状态。"+defaults+" "+headline+
           "复核从 `policy.json`、`benchmark_summary.json`、`external_summary.json` 和 `frozen_mando/summary.json` 开始。")
    append(module/"docs/DECISIONS.md","### CP5.1 开发集冻结结果（记录者 Codex）\n\n| 日期 | 决定 | 依据 |\n|---|---|---|\n| "+
           str(date.today())+" | "+defaults+" | 仅用真实开发集及 8 个开发缺包样本。冻结记录见 `policy.json` 和 `policy_application.json`。 |")
    append(OUT/"README.md","### 正式验收\n\n"+defaults+" "+headline+
           "\n\n| 内容 | 文件 |\n|---|---|\n| 选版、K 与逐单元未截断观测 | `policy.json`、`policy_application.json`、`real_dev.jsonl` |\n"+
           "| 完整基准、负对照成功样本 | `benchmark_summary.json`、`benchmark.jsonl`、`final_tables.md` |\n"+
           "| 真实单元、分类及 73 项锁版本参照 | `real_full.jsonl`、`real_masked.jsonl`、`external_summary.json` |\n"+
           "| 原始字节、导入字符串与逐轮收据 | `*_provenance.json`、`invocation_seals.jsonl.gz` |\n"+
           "| 最终代码、测试和 MANDO 图回归 | `final_audit.json`、`test_environment_resume_v2/suites/`、`frozen_mando/summary.json` |\n"+
           "| D3 与 SlithIR 缺失的独立记录 | `partial_ir_review.json`、`partial_ir_decision.json`、`partial_ir_summary.json` |\n"+
           "| 正式阶段用时及批次封存 | `test_environment_resume_v2/stage_runs.jsonl`、`measurement_completion.json`、`seal.json` |\n\n"+
           "Git 以无损 gzip 保存 "+str(len(archives["files"]))+" 份较大的 JSONL 表。解码前后 SHA256 和字节数在 `record_archives.json`。"
           "新检出需要原始表时，可从仓库根目录运行 `python -B compile_repair/artifacts/cp5_1_v1/record_archives.py restore`。"
           "该入口只还原清单中的本地表，已有文件先核验字节。原生编译与分析日志可能带有第三方源码表达式，仅供本地研究。各本地日志的路径、长度和 SHA256 见 `partial_ir_summary.json`。")
    print(defaults,headline,flush=True)


if __name__=="__main__":
    main()
