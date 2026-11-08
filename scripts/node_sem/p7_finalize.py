"""NS-P7 pilot handover; no inference, training, threshold changes or old-file edits."""
import csv
import hashlib
import json
from pathlib import Path
import re
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read, checked, ref, write

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"scripts/node_sem/artifacts/llm_v1"


def finalize(base=BASE, output_name="finalization_attempt2"):
    base=Path(base)
    output=base/output_name
    output.mkdir(exist_ok=False)
    report_path=base/"pilot_report/pilot_report.json"
    report=read(checked(read(base/"pilot_report/report.seal.json")["report"]))
    plan=read(checked(read(base/"pilot_plan.seal.json")["plan"]))
    for value in plan["implementation"].values():checked(value)
    assets=read(checked(plan["assets"]))
    for value in assets["implementation"].values():checked(value)
    if not read(base/"frozen_audit.json")["passed"]:raise ValueError("Frozen audit failed")
    checks=read(base/"pilot_report/independent_checks.json")
    if not checks["tokenizer_usage_matches"]:raise ValueError("Token counts differ")
    tests=[]
    for name in ("nodesem_final","dfg_v2","legacy"):
        path=base/"regressions"/(name+".log")
        line=path.read_text(encoding="utf8").splitlines()[-1]
        match=re.search(r"(\d+) passed(?:, (\d+) warnings)?",line)
        if not match or "failed" in line:raise ValueError("Regression failed: "+name)
        tests.append(dict(suite=name,passed=int(match.group(1)),warnings=int(match.group(2) or 0),log=ref(path),summary=line))
    total=sum(t["passed"] for t in tests)
    warnings=sum(t["warnings"] for t in tests)
    write(output/"tests.json",dict(tests=tests,passed=total,failed=0,skipped=0,warnings=warnings))
    review_path=base/"access_check_review/review.json"
    review=read(review_path) if review_path.exists() else None
    if review is not None:
        if read(review_path.with_name("review.seal.json"))["review"]!=ref(review_path):raise ValueError("Review seal differs")
        if review["gates_unchanged"]!=report["gates"]:raise ValueError("Review changed gates")
    scores=[json.loads(s) for s in checked(read(base/"pilot_report/report.seal.json")["rows"]).read_text(encoding="utf8").splitlines()]
    columns=("task_id","file","source_sha256","original_row_key","target_kind","role","faithfulness","present","flags")
    with (output/"node_scores.csv").open("x",encoding="utf8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for row in scores:
            data={k:row.get(k) for k in columns}
            data["flags"]=";".join(row["flags"])
            writer.writerow(data)
    gate=report["gates"]
    rows=[
        "# NS-P7：LLM 行为描述本机试点报告",
        "",
        "50个函数试点已经完成，但没有通过预先封存的语义一致性门槛。当前不能进入全量describe/judge生成、教师向量或学生训练。教师向量能否被CTX+STATIC重建、是否提供超出STATIC的信号，本轮尚无结果：这些只读诊断位于试点通过后的阶段，未执行。",
        "",
        "## 1. 本轮实际范围与输入",
        "",
        "执行2026-11-08读取的PROMPTS r23 §5.1、§5.10。文档只有NS-P7，无单独NS-P7A；用户请求中的NS-P6按已完成阶段的旧模板文本处理。本轮按NS-P7第4节在50函数试点后停止。",
        "",
        "facts来自CURRENT的accepted_attempt4，行身份来自text_v1原名视图。四任务共384个文件实例、254个唯一源码SHA；12,285个任务函数实例对应7,670个唯一源码函数，去重为4,485个提示。没有超过120行的真实函数；分段逻辑由合成测试验证。",
        "",
        "原图、作者标签、文件折、CODE/CTX/STATIC、HGT和既有训练配置均未改变。按r23仅在LLM提示层将非保留标识符改成a1、a2等；原名保留在本地prompt_map，不切换实验特征视图。保留名表仍沿用NS-P2，因此如balance/value等保留拼写不改。原名双射还原、AST精确对齐及标签/坐标扰动测试通过。",
        "",
        "## 2. 资产、环境和执行",
        "",
        "使用Qwen/Qwen2.5-Coder-3B-Instruct-GGUF的Q4_K_M。revision为f74adce6aa16316c625447af059dbebe4983757c；GGUF为2,104,932,800字节，SHA256为724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7。许可证、模型卡和BGE原登记摘要均已核验。模型与大产物只保存在WSL项目目录，不进入Git。",
        "",
        "用户明确批准下载模型及安装必要推理后端。只在nodesem新增llama-cpp-python 0.3.19和diskcache 5.6.3；CUDA12运行库、cuBLAS安装到本批独立backend_runtime目录，通过单进程LD_LIBRARY_PATH接入。所有原有nodesem包版本不变，mando及现有PyTorch均未改动。首次wheel下载HTTP504、初次导入缺少CUDA12库的记录保留；均发生在正式试点前，没有失败后偷偷换模型或重跑试点。",
        "",
        "资产登记最初版本保留为预检记录；v2将CUDA后端发现也置于既有.training.lock内。正式试点仅使用v2资产seal。temperature=0、top_k=1、seed=0、n_ctx=4096、n_gpu_layers=-1、n_batch=128、n_threads=4、max_tokens=2048、repeat_penalty=1.0，JSON schema约束。所有输入最长2,472 token，中位数396，50次实际prompt token数与预检逐条一致。超出完成预算时不得截断语义后伪装成功；本次没有触发格式重试。",
        "",
        "试点由setsid独立进程执行，15秒心跳，GPU锁与HGT互斥，启动前核验交流供电、自动睡眠和休眠计时均关闭。50次生成全部完成，JSON重试0次，OOM/运行异常0次，总墙钟约242.35秒；每单元平均4.776秒。输入19,580 token、输出6,627 token。",
        "",
        "运行前空闲显存3,418MiB，运行中一次采样空闲861MiB、已用3,115MiB；未持续采样，不能把该值称作峰值。较小上下文的llama警告属于固定4096相对模型训练窗口32768的提示；词表预检的n_ctx_train=0警告不表示真实提示溢出，实际usage与预检一致。",
        "",
        "## 3. 固定样本与通过门槛",
        "",
        "seed=1，四任务分层：两个合约任务各6个非SolidiFI+6个SolidiFI；两个节点任务各7+6，总计26个非SolidiFI、24个SolidiFI。包含10个有非SolidiFI正例节点的函数；抽样前核验访问控制20、重入32个原有正例节点身份。标签只用于抽样，未进入提示或后处理的事实比较。",
        "",
        "|验收项|结果|预定要求|结论|",
        "|---|---:|---:|---|",
        "|JSON解析成功|50/50，100%|≥95%|通过|",
        "|可核验节点faithfulness中位数|0.6667|≥0.7|未通过|",
        "|全部目标节点faithfulness≥0.5|80/123，65.04%|≥80%|未通过|",
        "|描述黑名单命中（语句节点）|2/123，1.63%|≤5%|通过|",
        "|external_call声明与事实一致|9/12，75.00%|≥80%|未通过|",
        "|state_update声明与事实一致|34/47，72.34%|≥80%|未通过|",
        "",
        "123个语句/条件目标中112个可核验，11个facts unknown。按用户批准：unknown保留、faithfulness为null、存在位0，并计入“未达到0.5”的总分母；中位数只在可核验节点计算。另有49个可投影函数节点，其中48个intent有效；第50个源码函数没有对应的函数级HCG目标，未新增节点。",
        "",
        "role门槛按用户批准采用“可核验且模型声称该角色”的准确比例，同时报告召回率与unknown。external_call召回9/26=34.62%，state_update召回34/35=97.14%；没有可核验预测不能自动通过。分层语句有效率：SolidiFI 41/60，非SolidiFI 39/63；两组faithfulness中位数均0.6667。原始三份完整提示/响应样例保留在pilot_report.json。",
        "",
        "## 4. 具体问题与结论边界",
        "",
        "真实样例包括：将uint256 c = a / b这样的局部计算归为state_update；外部调用描述未列出实际读取的金额/目标；把对象成员调用说成事件或状态更新；buggy_50的若干摘要对应到错误的目标行。部分reads/writes使用下标或成员路径，而封存事实使用抽象变量根，现有Jaccard并不是完整别名等价判定。因此数值是与当前静态参考的一致性，不是人工判定的绝对语义正确率。",
        "",
        "试点有2个源码行分别对应2个HCG节点，严格保留一行到多个节点的映射；同一行摘要会分别接受各节点事实检查，未按最近行号猜测或新增表达式节点。函数内提示没有所有被调函数、继承和类型定义，不能要求模型凭空恢复缺失上下文。",
        "",
        "发现一处本轮报告代码问题：原access_check诊断用guards（保护本节点的条件）代替了self_condition（本句的条件），原0/26不得解释成LLM的授权检查识别准确率。该项不在通过门槛中，其他门槛和本轮未通过结论不受影响。",
    ]
    if review is None:
        rows += ["只读修订已准备并通过4个反例测试，当前尚待用户确认；未替换原报告或在真实样本应用该修订。"]
    else:
        a=review["corrected_agreement"]["access_check"]
        rows += ["用户已批准只读修订。原报告/seal/响应保留，在access_check_review/review.json另存纠正结果：可核验声称%d个、与本句已确认发送者相等条件一致%d个、声称unknown %d个。未重新生成任何文本，门槛逐项不变。"%(
            a["claimed_verifiable"],a["correct"],a["claimed_unknown"])]
    rows += [
        "",
        "## 5. 已确认的调整与尚未执行的建议",
        "",
        "本轮批准并记录了：必要后端安装；role一致率固定分母并公开召回/缺失/unknown；未知静态事实不冒充空集合且保守计入门槛。独立GGUF登记入口复用原资产校验，不改旧asset_registry.py，从而保持旧CODE/CTX/BGE产物的实现SHA有效。",
        "",
        "建议下一轮先统一读写名称的抽象口径和role含义，特别是持久状态写与局部赋值的区别，再决定是否在服务器改用更大的模型。需另建模板版本和新试点，不能覆盖本批或下调门槛。当前没有证据支持直接进行全量教师生成或学生训练。",
        "",
        "另有两个后续设计问题仅列出、不自动修改：judge_v1按文档原文保留了“never assess security”，却又允许security_note；且当前教师编码公式不包含security_note，不能把该对照解释为直接输入判断文本的收益。未来执行judge对照前应先确认其含义。函数/状态提示缺少部分调用定义和旧式构造函数的合约名关联，单纯扩大模型无法保证弥补这些信息。",
        "",
        "按describe试点吞吐粗略外推4,485个唯一提示约5.95小时；judge只能暂用同速参考，约另5.95小时，实际可能因多输出字段更慢。分层试点不是按全量token加权抽样，此估计不是运行承诺，也不是已获全量授权。",
        "",
        "## 6. 完成项、未完成项与测试",
        "",
        "已实现并运行：源代码提示对齐/局部编号、完整模板与缓存身份、独立资产登记、固定抽样与seal、离线GPU生成/心跳/一次JSON重试、后处理、保守忠实性与试点报告。原实现和旧运行产物保留。",
        "",
        "按失败停止规则，尚未执行全量describe/judge、教师384维BGE编码、教师冗余/信号探针、HGT或学生训练；也未接入S5–S8。teacher_encode与完整教师诊断的后续接入留待新的方案与授权，不能称为已完成全部NS-P7或证明教师有增益。",
        "",
        "%d项最终测试通过，0失败、0跳过；%d条既有弃用警告（DGL/distutils、NetworkX gpickle等）。NodeSem %d、DFG v2 %d、原DDG/graph_utils %d。8H只读load及354份运行源码哈希一致。新增测试20项覆盖提示不变性、分段、精确映射、格式重试、缓存篡改、黑名单、成员路径不混同、unknown分母、固定抽样及诊断反例。"%(
            total,warnings,tests[0]["passed"],tests[1]["passed"],tests[2]["passed"]),
        "",
        "## 7. 已执行命令与产物",
        "",
        "mando环境运行（CUDA_VISIBLE_DEVICES为空，TREE_SITTER_LIB_DIR沿用现有路径）：",
        "",
        "~~~bash",
        "python -B -m scripts.node_sem.llm_inputs --out scripts/node_sem/artifacts/llm_v1/inputs --asset-sha 724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7 --parameters scripts/node_sem/artifacts/llm_v1/parameters.json",
        "python -B -m scripts.node_sem.llm_pilot prepare --inputs scripts/node_sem/artifacts/llm_v1/inputs/manifest.json --assets scripts/node_sem/artifacts/llm_v1/llm_assets_v2.json --power scripts/node_sem/artifacts/llm_v1/power_check.json --approval scripts/node_sem/artifacts/llm_v1/authorization.json --out scripts/node_sem/artifacts/llm_v1/pilot_plan.json",
        "python -B -m scripts.node_sem.llm_pilot report --plan scripts/node_sem/artifacts/llm_v1/pilot_plan.json --run scripts/node_sem/artifacts/llm_v1/pilot_run1 --out scripts/node_sem/artifacts/llm_v1/pilot_report",
        "python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests",
        "python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests",
        "python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py",
        "~~~",
        "",
        "nodesem环境设置本批独立CUDA库的LD_LIBRARY_PATH，实际完整命令与PID见launch.json；离线入口为：",
        "",
        "~~~bash",
        "python -s -B scripts/node_sem/offline/llm_describe.py --plan scripts/node_sem/artifacts/llm_v1/pilot_plan.json --assets scripts/node_sem/artifacts/llm_v1/llm_assets_v2.json --out scripts/node_sem/artifacts/llm_v1/pilot_run1 --cache-dir scripts/node_sem/artifacts/llm_v1/cache/describe_v1",
        "~~~",
        "",
        "以上是已执行命令记录，目标目录排他创建。不要原样重复执行或复写旧目录；当前门槛未通过，不自动启动新尝试。只读报告来自既有缓存，格式重试之外没有自动重试。",
        "",
        "Git仅提交代码、报告、计划、资产引用、紧凑结果与SHA索引；模型、wheel、CUDA库、完整提示/原始响应缓存和逐行教师文本留在WSL。三份交接/训练变化/进度文档按原格式只追加，UTF-8及doc_check --expect-cjk通过后提交；本轮不push。",
        "",
        "## 8. 后续资源安排",
        "",
        "最终正式实验按用户安排将在显存充足的服务器另建批次；当前4GiB仅本地开发条件，不能据此判断方案的最终资源上限。此次GPU推理完成，停止原因是预定语义验收未通过。服务器上的数值与本机试点分别记录。",
        ""
    ]
    body="\n".join(rows)
    report_doc=ROOT/"scripts/node_sem/NS_P7_REPORT.md"
    for path in (report_doc,base/"REPORT.md"):
        if path.exists():
            if path.read_text(encoding="utf8")!=body:
                raise ValueError("Existing report differs: "+str(path))
        else:
            with path.open("x",encoding="utf8") as stream:stream.write(body)
    short=("\n\n## 2026-11-08 NS-P7 50函数试点完成、门槛未通过（修改 AI：Codex）\n\n"
        "在原名源码上实现LLM提示层a_k编号，原图/CODE/CTX/STATIC/HGT/标签/划分不变。254个源码SHA、7,670个唯一函数形成4,485个唯一提示。固定50函数（26非SolidiFI，含10个正例所在函数）使用本地Qwen2.5-Coder-3B-Instruct Q4_K_M完成，约242.35秒、50/50 JSON成功、0重试/0OOM。faithfulness中位0.6667、≥0.5为80/123=65.04%，external_call精确率75%、state_update72.34%，未达预定门槛，停止全量生成和后续教师/学生工作。\n\n"
        "用户批准后端最小安装、role分母及unknown保守处理；只新增nodesem后端与本批独立CUDA库，原包与mando不变。access_check原诊断误用了保护范围guards，0%不可解释为识别准确率；更正状态见NS_P7_REPORT.md及独立审核记录。"
        "%d项最终回归通过、42条既有警告，8H及354冻结源码一致。详见scripts/node_sem/NS_P7_REPORT.md、artifacts/llm_v1。最终实验仍在显存充足服务器另建批次，本机显存只是开发限制；没有启动NS-P8。\n").replace("%d",str(total))
    docs=("HANDOVER.md","scripts/node_sem/PROGRESS.md","docs/training_changes_2026-10-07.md")
    start=read(base/"start.json")["documents"]
    prefixes={}
    for name in docs:
        p=ROOT/name;data=p.read_bytes();old=start[name]
        if hashlib.sha256(data[:old["bytes"]]).hexdigest()!=old["sha256"]:
            raise ValueError("Old document prefix changed: "+name)
        prefixes[name]=len(data)
        with p.open("a",encoding="utf8") as stream:
            stream.write(("\n\n## 90. 2026-11-08 NS-P7 实施与选择记录（Codex）\n\n"+body)
                if name.startswith("docs/") else short)
    write(output/"document_prefixes.json",prefixes)
    write(output/"status.json",dict(pilot_completed=True,pilot_passed=gate["passed"],
        full_generation_authorized=False,full_generation_executed=False,
        HGT_training=0,student_training=0,report=ref(report_doc),tests=ref(output/"tests.json"),
        access_check_review=ref(review_path) if review else None,
        access_check_review_pending=review is None))
    print(json.dumps(dict(tests=total,pilot_passed=gate["passed"],review_applied=review is not None),indent=2))


if __name__=="__main__":finalize()
