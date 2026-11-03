"""Append NS-P3b2 records only after verified production and all tests succeed."""
from pathlib import Path
import hashlib,json,subprocess
from datetime import datetime
from scripts.DFG.dfg_v2.benchmark_v2.prepare import read,checked,ref,write
ROOT=Path.cwd();BASE=Path(__file__).resolve().parent
assert read(BASE/"pipeline_status.json")["status"]=="complete"
assert read(BASE/"tests_status_v2.json")["status"]=="complete"
assert read(BASE/"acceptance_status.json")["status"]=="complete"
validation=read(BASE/"acceptance/validation.json")
assert validation["passed"]
assert read(BASE/"acceptance/validation.seal.json")["validation"]==ref(BASE/"acceptance/validation.json")
comparison=read(BASE/"comparison/summary.json")
assert comparison["passed"]
stats=read(BASE/"acceptance/stats.json")
runs=read(BASE/"tests_v2.json")
assert len(runs)==4 and all(r["exit_code"]==0 for r in runs)
started=read(BASE/"started.json")
for rel,item in started["documents"].items():
 data=(ROOT/rel).read_bytes()
 assert len(data)==item["bytes"] and hashlib.sha256(data).hexdigest()==item["sha256"]
date=datetime.now().date().isoformat()
table=["| 任务 | 行数 | 检查运算=1 | 检查运算未知 | CTX变化行（每套） | FROM unknown旧→新 | FROM entry |",
       "|---|---:|---:|---:|---:|---:|---:|"]
encoding=["| 任务 | 名字 | 去重文本 | 截断级别变化行 | 秒数 |",
          "|---|---|---:|---:|---:|"]
for task,s in comparison["tasks"].items():
 field=stats["tasks"][task]["names"]["original"]["fields"]["FROM"]
 old=read(ROOT/"scripts/node_sem/artifacts/ctx_v1/original"/task/"ctx_fields.manifest.json")["statistics"]["FROM"]
 table.append("| {} | {} | {} | {} | {} | {}→{} | {} |".format(task,stats["tasks"][task]["rows"],
  s["changes"]["arith.checked_by_helper=true"],s["changes"]["unknown.checked_call=true"],
  s["names"]["original"]["changed_rows"],old["unknown"],field["unknown"],field["entry"]))
 for mode,item in s["names"].items():
  e=item["encoding"]
  encoding.append("| {} | {} | {} | {} | {:.3f} |".format(task,mode,e["unique_texts"],item["stage_changed_rows"],e["elapsed_seconds"]))
table="\n".join(table);encoding="\n".join(encoding)
first=next(iter(comparison["tasks"].values()))["names"]["original"]["encoding"]
encoder_note=("CodeT5p110m revision "+first["revision"]+"；资产SHA "+first["model_sha256"]+
 "；pooling="+first["pooling"]+"，precision="+first["inference_dtype"]+
 "，max_length="+str(first["max_length"])+"。沿用原资产和离线环境，未下载/安装或修改tokenizer。")

seconds=sum(n["encoding"]["elapsed_seconds"] for s in comparison["tasks"].values() for n in s["names"].values())
peak=max(n["encoding"]["peak_allocated_bytes"] for s in comparison["tasks"].values() for n in s["names"].values())/2**20
dims=sorted({x["dimension"] for x in validation["assemblies"]})
assert dims==[514,760] and len(validation["assemblies"])==32
intro=("输入 node-sem@"+started["head"][:8]+"、PROMPTS r13（文档日期2026-11-03），已按共享§5.1快进同步；实施与记录：Codex。"
"本轮仅NS-P3b2，不训练、不推进NS-P4。original为主、局部masked CTX为对照；不切换匿名主视图。")
logic="""- static_profile.py / behavior_schema.json：schema版本nodesem-static-v2，243→245维；G新增arith.checked_by_helper，N新增unknown.checked_call。严格要求supported且result_condition_check=true；歧义unknown时值为0、N为1，适用范围复用checked_call。
- B多热、C、D/D1/D2由字段unknown_policy=keep_true控制；未知时保留确定true、同时N=1。D的none用unknown_exclude排除；B读写数量独热与其他zero策略保持不变。没有按字段名硬编码未知保留分支。
- ctx_alignment.py只在已有精确投影sidecar加入node_kind；ctx_fields.py依据函数入口身份与参数声明角色生成entry，非入口或无法确定来源仍unknown，局部相对距离不变。constructor/fallback沿用事实function类别，modifier沿用modifier。
- p3_prepare.py分开统计entry与unknown，原始facts、代码文本、DFG、图、标签、折不改。新目录attempt_b2排他创建，旧ns_p3产物和seal保留，旧CURRENT先复制归档。
- p3_acceptance.py增加显式新目录/快照参数并保留默认入口；新增p3b2_acceptance.py，以旧schema列名重对齐、逐列审查STATIC、逐字符审查CTX，核验旧实现SHA与aa81bcde Git blob。旧产物不能用当前变更后的producer冒充同一运行版本；归档核验不改旧seal，新载体验收仍使用当前实现严格SHA。
- tests/test_p3b2.py新增检查函数/歧义、三值、入口身份/反例、独立差异拒绝测试；test_ctx_static按新245列契约更新维度及策略断言，保留原Oracle、扰动、身份与未知检测。"""
verification="""746 NodeSem + 2653 DFG v2 + 223 原DDG/graph_utils + 6离线预算测试，共3628通过；最终0失败、0跳过，4+9+29=42条既有DGL distutils/NetworkX gpickle弃用警告。52 Oracle改名重抽、STATIC与masked不变、标签/元数据/DOT前缀扰动和坏锚点拒绝继续通过。新增唯一helper与同名歧义均有AST实证；样例未在本轮执行Solidity编译。
8份CTX每份两遍逐位相同、误差0、隐式尾截断0；模型、revision、资产SHA、池化、fp16、256token与两遍规则不变，原encode_ctx.py及ctx_budget.py没有改动。8CTX+4STATIC+4旧CODE全载体验收、32次真实装配通过；S3=514，S4=760，G0/G3R均等于FeatureSpec.carrier_dim()。
8H execution.load及runtime_resume_v2核验通过；22813冻结历史文件不变，本轮开始快照中除授权文件与三份追加文档外无变化。事实CURRENT仍accepted_attempt4；不读取训练分数或以标签分组。"""
limits="""- 背景段提到checked_call未进入STATIC和CTX；本轮具体§1只要求STATIC补列，§2/§3只允许CTX unknown→entry。因此检查摘要已进入STATIC，未另加CTX字段；没有擅自扩展文本方案。
- 重入节点FROM含unknown仍468/6635（7.05%）：439行L1不支持，29行循环更新表达式被既有facts归为other且offset=None。来源节点存在，但冻结的相对距离没有定义；不是参数入口，不能全改entry，更未改facts来追求低unknown率。11行同时有entry和unknown，两个计数不可当互斥分类相减。
- 局部masked不等于8G全文件匿名，也不能去掉原名CODE中的名字捷径。沿用原名主视图和历史匿名接口，后续比较需匹配原名S0，不借用8H匿名成绩作配对基线。
- 仍是受限AST事实后端，没有完整Solidity绑定/别名系统；新增位描述经检查的算术，不是安全性证明，没有新增F1结论。
- 最终实验按用户安排在显存充足服务器执行；当前RTX3050 4GiB仅是本机开发限制，服务器未在本轮部署或实测。模型/产物在WSL工作树，不额外向C盘复制。"""
commands="""    python -B -m scripts.node_sem.p3_prepare --task <task> --ctx-out <新目录>/fields/original/<task> --static-out <新目录>/static/original/<task>
    /home/zhao/miniconda3/envs/nodesem/bin/python -s -B scripts/node_sem/offline/encode_ctx.py --fields <字段jsonl> --out <新编码目录>
    CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p3b2_acceptance --base scripts/node_sem/artifacts/ns_p3/attempt_b2
    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
    /home/zhao/miniconda3/envs/nodesem/bin/python -s -B -m unittest discover -s scripts/node_sem/offline -p test_ctx_budget.py
"""
failures="""开发期失败记录未删除：首轮4失败/90通过，测试误用不存在的constructor/fallback事实枚举；改为实际function统一类别后，另发现modifier夹具的既有L1不支持，不能期待entry，改为明确断言unknown且保留支持构造函数测试。随后94项通过。全套首次1失败/744通过，新差异测试夹具缺少file元数据；补齐身份及额外STATIC篡改拒绝测试后746通过。生产算法与验收关键断言未因这些夹具问题放宽；正式准备/编码无失败或重试。"""
restored=read(BASE/"restored_true_rows.json")
restored_note="实际恢复的行数（B多热/C全部五位/D-D2，按任务内去重）："+str(restored)+"。C若只数前四位为31/31/35/31，与背景计数一致；包含文档明确要求的ext_call_in_loop后每任务增加4行。状态存在读写条目也不一定对应多热位，例如标量读取的数量独热仍因unknown保持0，不把原始条目数当恢复行数。"
verification=restored_note+"\n\n"+encoder_note+"\n\n"+verification
report="# NS-P3b2：STATIC三值修正与CTX入口标签验收\n\n日期："+date+"。"+intro+"\n\n## 实施\n\n"+logic+"\n\n## 实际变化\n\n"+table+"""
\n旧243列的变化仅发生在授权keep_true列、unknown行的0→1；新增两列独立从封存checked_call重算。每列旧/新索引及变化数量见comparison/summary.json。CTX原名和masked逐行验证，仅允许FROM入口及参数来源的unknown→entry，其余字符完全相同。四任务变化行分别4602/3118/3671/1942，跨任务不当作独立源码样本。
\n## 编码与截断\n\n"""+encoding+"\n\n成功编码总耗时{:.3f}秒，peak allocated最大{:.3f}MiB；包含加载、限长、两遍推理、输出与校验，不是纯GPU计算时间或整卡使用量。".format(seconds,peak)+"\n\n## 验收与失败记录\n\n"+verification+"\n\n"+failures+"\n\n## 限制与方案核对\n\n"+limits+"\n\n## 实际命令与产物\n\n"+commands+"""
\n统一设置PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2和原TREE_SITTER_LIB_DIR；GPU离线编码使用原.training.lock非阻塞检查、每次仅一个进程。runner与完整命令/耗时见attempt_b2/pipeline_runs.json，测试见tests_v2.json，总验收见acceptance_status.json。
\n新结果集中artifacts/ns_p3/attempt_b2，comparison保存逐行差异和列名映射，acceptance保存载体与冻结核验。全部验收后才切换ns_p3/CURRENT；previous_CURRENT和所有旧产物保留。三历史文档只追加并校验原前缀SHA、UTF-8/CJK。源码、报告、字段文本、清单、统计和测试记录按既有方式本地提交；NPZ、权重、HF缓存仅本地保留。不自动推送，不进入NS-P4。
"""
report_path=ROOT/"scripts/node_sem/NS_P3B2_REPORT.md"
with report_path.open("x",encoding="utf8") as out:out.write(report)
detailed="\n\n## 81. "+date+" NodeSem NS-P3b2：STATIC补项/三值与CTX入口来源（Codex）\n\n"
detailed+="### 81.1 输入、范围与实施选择\n\n"+intro+"\n\n"+logic
detailed+="\n\n### 81.2 数据变化与编码\n\n"+table+"\n\n"+encoding
detailed+="\n\n每列映射与计数见attempt_b2/comparison/summary.json；逐行文本差异仅unknown→entry，所有非许可差异为0。成功编码{:.3f}秒，peak allocated最大{:.3f}MiB，不代表全图训练显存。".format(seconds,peak)
detailed+="\n\n### 81.3 测试、身份核验与失败现场\n\n"+verification+"\n\n"+failures
detailed+="\n\n### 81.4 命令、归档与未完成边界\n\n"+commands+"\n"+limits
detailed+="\n\n无新的方案偏离或未确认替代；按用户本轮授权实施r13三项修正。旧producer SHA从aa81bcde核验、新版本单独绑定；不改旧seal、不把旧243维与新245维混用。验收后CURRENT切到attempt_b2，旧CURRENT已保存；三文档只追加，详见NS_P3B2_REPORT.md、decisions.json。只本地提交，不推送、不启动NS-P4。\n"
short=("\n\n### "+date+" NodeSem NS-P3b2完成（修改 AI：Codex）\n\n"
"按r13完成STATIC检查运算两列与B/C/D三值修正，243→245维；CTX函数入口及参数来源unknown→entry。原名与局部masked各52418行重编码，8份均两遍逐位一致；旧facts/图/标签/DFG/HGT/tokenizer/8H不改。4任务helper=214/103/271/105，所有非授权列/文本差异为0。\n\n"
"3628测试通过，42条既有警告；32组合真实载体验收，S3/S4=514/760，旧CODE与8H有效runtime、22813冻结文件核验通过。新CURRENT指向ns_p3/attempt_b2，旧产物保留，详细选择、命令和失败夹具记录见training_changes§81及NS_P3B2_REPORT。重入FROM剩余468未知中439为L1回退、29为循环更新无相对距离，未伪造entry。\n\n"
"仍以original为主，masked仅CTX名字对照；本轮无HGT训练/新F1，不推进NS-P4，仅本地提交、不自动推送。最终实验将在用户安排的显存充足服务器执行，RTX3050 4GiB仅当前本机限制，服务器未实测。\n")
progress=short.replace("### ","## ",1)+"\n文件：static_profile、behavior_schema、ctx_alignment、ctx_fields、p3_prepare、p3_acceptance；新增p3b2_acceptance及test_p3b2，更新旧维度/未知策略断言。schema属性驱动keep_true/zero与none排除；入口来自精确投影元数据。源码来源、版本SHA、字段/编码/STATIC、列对照、截断变化与旧producer归档核验在attempt_b2中。没有新的设计替代需批准，checked_call本轮只进STATIC，CTX严格只做entry替换。\n"
for rel,text in (("docs/training_changes_2026-10-07.md",detailed),("HANDOVER.md",short),("scripts/node_sem/PROGRESS.md",progress)):
 with (ROOT/rel).open("a",encoding="utf8") as out:out.write(text)
docs=[str(report_path)]+[str(ROOT/rel)+":"+str(item["bytes"]) for rel,item in started["documents"].items()]
cmd=["/home/zhao/miniconda3/envs/mando/bin/python","-B","-m","scripts.node_sem.doc_check","--expect-cjk"]+docs
result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
(BASE/"doc_check.log").write_text(result.stdout,encoding="utf8")
if result.returncode:raise RuntimeError("Document check failed")
for rel,item in started["documents"].items():
 assert hashlib.sha256((ROOT/rel).read_bytes()[:item["bytes"]]).hexdigest()==item["sha256"]
new_current=dict(validation=ref(BASE/"acceptance/validation.json"),seal=ref(BASE/"acceptance/validation.seal.json"),
 stats=ref(BASE/"acceptance/stats.json"),encoding_index=ref(BASE/"encoding_index.json"),
 comparison=ref(BASE/"comparison/summary.json"),previous_current=ref(BASE/"previous_CURRENT.json"))
write(BASE/"new_CURRENT.json",new_current)
current=ROOT/"scripts/node_sem/artifacts/ns_p3/CURRENT.json"
assert current.read_bytes()==(BASE/"previous_CURRENT.json").read_bytes()
temporary=current.with_name("CURRENT.b2.tmp")
with temporary.open("xb") as stream:stream.write((BASE/"new_CURRENT.json").read_bytes())
temporary.replace(current)
write(BASE/"documentation.json",dict(report=ref(report_path),docs={rel:ref(ROOT/rel) for rel in started["documents"]},
 original_prefixes_unchanged=True,doc_check_exit=0,current=ref(current),training_executed=False))
print(result.stdout)
print("NS-P3b2 docs appended and CURRENT atomically updated")
