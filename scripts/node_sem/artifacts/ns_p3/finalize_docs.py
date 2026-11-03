"""Finalize append-only documentation after sealed NS-P3b acceptance."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[4]
B=ROOT/"scripts/node_sem/artifacts/ns_p3"
A=B/"acceptance_v1"
v=json.loads((A/"validation.json").read_text())
s=json.loads((A/"stats.json").read_text())
assert v["passed"] and len(v["assemblies"])==32
assert all(not x["unexpected"] for x in v["masked_scan"].values())
enc=[(task,mode,data["encoding"]) for task,t in s["tasks"].items() for mode,data in t["names"].items()]
assert len(enc)==8 and all(e["repeat_bitwise"] and e["repeat_max_abs_error"]==0 for _,_,e in enc)
assert json.loads((B/"resume_attempt2/node_sem_verified_run.json").read_text())["exit_code"]==0
assert all(x["exit_code"]==0 for x in json.loads((B/"resume_attempt2/test_runs.json").read_text()))
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,text):
 with p.open("x",encoding="utf8") as f:f.write(text)
write(B/"stats.json",(A/"stats.json").read_text())
write(B/"CURRENT.json",json.dumps(dict(validation=ref(A/"validation.json"),seal=ref(A/"validation.seal.json"),
 stats=ref(B/"stats.json"),encoding_index=ref(B/"resume_attempt2/encoding_index.json")),indent=2)+"\n")
table="| 任务 | names | 行数 | 去重后文本 | 去重率 | 总秒数 | 最终截断级别 0/1/2/3/4/5/6/7/8 |\n| --- | --- | ---: | ---: | ---: | ---: | --- |\n"
for task,mode,e in enc:
 table+="| {} | {} | {} | {} | {:.2%} | {:.3f} | {} |\n".format(task,mode,e["rows"],e["unique_texts"],e["deduplication_rate"],e["elapsed_seconds"],"/".join(str(e["stages"].get(str(i),0)) for i in range(9)))
resources="成功编码合计{:.3f}秒；单进程peak allocated最大{:.3f}MiB。".format(sum(e["elapsed_seconds"] for _,_,e in enc),max(e["peak_allocated_bytes"] for _,_,e in enc)/2**20)
implementation="""
- ctx_alignment.py：冻结ProjectionView/Projector精确AST身份连接，补FUNC签名、声明角色及标识符跨度；临时sidecar不改facts/DFG/图，不按最近行猜测。兼容AST同跨度包装identifier只处理一次。
- ctx_fields.py：固定字段顺序和适用性，UNKNOWN逐字段处理，FROM/TO各最多2条并按相对距离选取；original保留拼写，masked按本节点首次出现和声明角色分配STATE/PARAM/LOCAL/FUNC/TYPE/IDENT占位名，保留内建/关键字和字面量。
- static_profile.py、behavior_schema.json：声明式列区间、适用性、独热/多热、未知位、encode/explain往返；K/L/M清单从facts_schema派生，不依赖变量拼写、文件身份、pragma版本或标签。
- p3_prepare.py：先验收CURRENT、seal、validation、闭包、源码/文本/图身份，再排他创建字段/STATIC及清单；STATIC float32二值、present全true。
- offline/encode_ctx.py、ctx_budget.py：独立CTX入口，复用旧encode.py的冻结加载配置、池化、锁、去重及重复编码函数；逐级限长、记录每行证据。
- p3_acceptance.py：独立重算STATIC、全量masked词法扫描、检查编码/载体身份、32次装配、旧CODE及8H运行闭包。
- tests/test_ctx_static.py、test_p3_acceptance.py、offline/test_ctx_budget.py：语义/未知、52 Oracle改名重抽、扰动、预算、漏名和封存篡改拒绝。
"""
decisions="""
1. 用户批准独立encode_ctx.py，保持旧encode.py不变，因为旧M1清单绑定其SHA，直接新增--ctx会使旧产物验收失败。
2. 用户批准只读AST辅助信息：封存facts/text没有FUNC签名及完整STMT/FROM标识符位置；原Projector精确对齐、声明角色与明确IDENT回退，不从symbol身份字符串截名字、不改旧事实。
3. 用户批准原七级之后的第8级限长：长FROM/TO可能令STMT清空后仍超过256。按固定优先级缩字段内容，所有标签保留，单列次数，不依赖tokenizer从尾部删除DEF/USE。
4. 原编码及回归进程/会话消失，没有失败或结束证据，原因未确认。用户批准保留现场，验收复用首份成功结果，新resume_attempt2只完成其余7项，并补完中断回归；不换参数、不自动无限重试。
"""
limits="""
- 本轮主视图仍original；保留旧anonymous配置、text/CODE/carrier接口和历史文件供后续比较。本轮不读匿名产物、不生成匿名facts；masked只是局部CTX对照，不是8G/8H整文件匿名视图。匿名事实到CTX全流程尚未接通；后续是否比较需另行明确绑定。
- 已批准的checked_call一层运算摘要未列入本轮§4.5/4.6表，故暂未编码。supported且result_condition_check=true的任务内行数AC合约/节点214/103、重入合约/节点271/105；不能声称所有已提取语义均已进入特征。未临时扩维使本批失效，证据unconsumed_facts.json。
- 仍继承受限AST/声明/别名/调用分析能力，unknown不等于否定；没有新的Solidity编译验证。原名CODE和字符串捷径未被局部masked CTX消除；未来需要匹配原名S0，不能将旧匿名8H得分当作配对基线。
- 截断文本是编码特征，不保证保留完整语法，不回送语义分析器。本轮没有HGT正式/冒烟训练、新F1、NS-P4融合或后续批次。
- 最终实验按用户安排使用显存充足服务器，当前RTX3050 4GiB只是本机开发限制；本轮没有部署或实测服务器。产物在WSL工作树，不额外向C盘写模型或训练日志。
"""
tests="""
最终NodeSem 727通过/4警告，DFG v2 2653通过/9警告，原DDG+graph_utils 223通过/29警告，离线6项OK；合计3609通过，0失败/跳过，42条既有DGL distutils / NetworkX gpickle弃用警告。

52 Oracle双射改名后重抽facts，STATIC逐位和masked CTX逐字一致；独立逆字典序改名样例也一致。标签/漏洞元数据与DOT前缀扰动不改变新特征；损坏精确AST锚点拒绝。52,418行masked词法扫描无残留用户identifier，字符串和数值字面量不误作标识符，合法schema枚举保留。

8CTX、4STATIC、4旧原名CODE全量载体验收通过，行身份/顺序/源码/code SHA、向量和实现/资产SHA一致；4任务×2种CTX×2图×S3/S4共32次装配通过，原图节点/边/属性不变，只在深拷贝中写token。8H load及runtime_resume_v2一致，22,813冻结历史文件字节不变。读取图的完整性路径仍核对含标签的指纹，但标签不进入特征或统计。

开发期修正并留档：同跨度Yul包装/子identifier重复替换；截断测试不合法role夹具；扫描词表缺少合法one/many/zero/param_local/scalar枚举；独立审查发现CTX具名seal被错误按通用manifest.seal读取；该篡改测试又误用create-only write，导致1失败726通过。后者仅改为有意覆写临时夹具后，727通过；拒绝断言未改。旧失败、探针、被中断日志均保留，未删除测试或放宽关键断言。
"""
commands="""
mando：PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64；tests/acceptance用CUDA_VISIBLE_DEVICES=''。实际命令：

    python -B -m scripts.node_sem.p3_prepare --task <task_id> --ctx-out <新CTX目录> --static-out <新STATIC目录>
    /home/zhao/miniconda3/envs/nodesem/bin/python -s -B scripts/node_sem/offline/encode_ctx.py --fields <ctx_fields或ctx_fields_masked.jsonl> --out <新输出目录>
    python -B -m scripts.node_sem.p3_acceptance --encoding-index scripts/node_sem/artifacts/ns_p3/resume_attempt2/encoding_index.json --out <新验收目录>
    python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
    /home/zhao/miniconda3/envs/nodesem/bin/python -s -B -m unittest discover -s scripts/node_sem/offline -p test_ctx_budget.py

生产入口拒绝覆盖已有目录。四任务实际路径在preparation_runs.json；首个成功命令在encoding_runs.json；恢复7项在resume_attempt2/runs.json；测试/验收命令和结果各有run记录。nodesem GPU编码用原.training.lock非阻塞锁且串行，未与训练并发。
"""
report="""# NS-P3b：CTX与STATIC实现及验收

日期2026-11-02；实施与记录：Codex。输入node-sem@e77d42d3、PROMPTS r12、共享§5.1与§5.5b。启动git pull因WSL DNS无法解析github.com失败，使用本地r12；未声称远端已同步。

## 已完成

CURRENT→accepted_attempt4/original的事实v1.1与原名text_v1，共52,418行。原名/局部masked CTX各一套，共104,836个256维向量；STATIC四套243维。临时S3=CODE256+CTX256+2存在位=514，S4=256+256+243+3=758。只装配载体，不登记NS-P4配置或训练。

## 文件与逻辑
"""+implementation+"""
STATIC实际243维由schema决定，不是硬填“约200”。A/A1/A2/A3/A4=9/1/8/10/5，B/C/D/D1/D2/D3=14/5/8/12/6/20，E/E1/F/G/H/I/J=11/5/7/12/6/12/16，K/L/M/N=21/12/8/35。增加量来自明确不适用、已接受unknown枚举与逐字段未知位。普通独热恰好1位（包括不适用）；适用但未知时取值位全0并置N，遵循§5.5b明确规则，不清空其他确定字段。

## 已批准调整
"""+decisions+"""
## 实际编码与统计

CodeT5p110m revision d9f3a534af4252f04b10cd9f78e05037542d10f6；资产SHA 2e4c548e3ebeb2f8a1c05cbe0197f8381c9f3249682e14dccb827c1827f55140；model_default池化、模型内归一化、fp16冻结CUDA推理、float32输出、batch32、max_length256。与旧CODE的资产/池化/精度核对一致，CODE自身仍128token。没有新下载、升级或环境改变。

"""+table+"""
8份均两遍逐位相同、最大绝对差0，tokenizer隐式尾截断0。第8级在四个masked任务各1次，均是buggy_35对应任务内实例：418→七级后261→第8级256，仅缩TO内容，全部标签保留；原名0次。跨任务重复不能当作4个独立源码事件。详见fallback_examples及encoded_text。
"""+resources+"""耗时含加载、限长、两次推理、输出与校验，峰值不是整卡或训练需求。未完成旧attempt耗时未知，未纳入成功之和。每STATIC列1比例、每CTX字段非空/unknown率、截断与去重详见artifacts/ns_p3/stats.json，不按标签分组。

## 测试与完整性
"""+tests+"""
## 边界与停止位置
"""+limits+"""
## 命令和归档
"""+commands+"""
CURRENT.json连接validation/seal、stats及显式编码索引（1复用+7新结果），旧attempt不覆盖。源码、字段文本、manifest、统计和收据按既有方式提交；NPZ、模型权重和HF缓存保留本地。三份历史记录仅追加并校验原前缀SHA，doc_check强制UTF-8/CJK。按共享上下文完成本地NS-P3b提交后停止，不自动推送。
"""
write(ROOT/"scripts/node_sem/NS_P3B_REPORT.md",report)
paths=["HANDOVER.md","docs/training_changes_2026-10-07.md","scripts/node_sem/PROGRESS.md","scripts/node_sem/EXPERIMENT_POLICY.md"]
before={p:dict(bytes=(ROOT/p).stat().st_size,sha256=ref(ROOT/p)["sha256"]) for p in paths}
write(B/"document_before.json",json.dumps(before,indent=2)+"\n")
handover="""

### 2026-11-02 NodeSem NS-P3b 完成（修改 AI：Codex）

原名accepted_attempt4事实生成原名/局部masked CTX各52,418行，8套256维编码；STATIC四套243维。用户批准独立encode_ctx保留旧CODE源码SHA、只读AST签名/标识符辅助对齐、保留标签的最终限长兜底。中断后获准保留现场、复用首份成功并在新attempt完成余7项，未换模型/参数。详情见training_changes§80、decisions.json。

8套两遍编码逐位一致、max error=0；全量masked标识符残留0。S3/S4=514/758维，G0/G3R两种CTX共32次真实装配通过；3609测试通过，42条既有警告。旧CODE、8H及22,813冻结文件核验通过。报告NS_P3B_REPORT，产物CURRENT连接明确的复用/新编码索引。

仍以original为主，保留匿名接口供以后比较，masked仅局部CTX对照。checked_call摘要未在本轮字段表中、尚未消费；没有HGT训练/F1/NS-P4。最终实验按用户安排使用显存充足服务器，4GiB只是本机开发限制；本轮未部署服务器。本地提交、不自动推送。
"""
training="""

## 80. 2026-11-02 NodeSem NS-P3b：CTX与STATIC全量实现（修改 AI：Codex）

### 80.1 输入、范围与已批准选择

基于e77d42d3/PROMPTS r12，读共享§5.1及§4.5/4.6/5.5b。git pull因DNS未成功，使用本地版本如实记录。只读CURRENT→accepted_attempt4/original事实v1.1、原名text_v1及固定F0/F3引用，先校验seal/validation/闭包/SHA，再做新字段和向量；原DFG/HGT/tokenizer、图/标签/折、旧facts/CODE/8H均不修改。所有新增逻辑在scripts/node_sem。
"""+decisions+"""
用户最新要求保留匿名接口以备后续对比，原有VIEWS、text/CODE/carrier及匿名历史保持，不将旧8H匿名成绩作为原名基线。本轮仍original，masked仅本节点内部占位，未生成匿名facts/匿名CODE；后续视图选择需明确计划。generic“一位独热”与逐字段未知全0存在字面冲突，本轮以明确未知规则为准：取值位全0+N，其他确定字段正常，不增新方案。

### 80.2 文件、实现与实际维度
"""+implementation+"""
STATIC243维由schema生成，包含35个N位（5组级+30逐字段）。A3/F/H等保留此前已接受unknown枚举，额外不适用默认避免把非适用当否定。原名和masked共享同一渲染逻辑，名字之外不改变语义字段；文件/绝对跨度只在身份元数据，特征只使用相对offset。载体只在深拷贝token上拼接：S3=514，S4=758，无HGT构造或trainer接入修改。

### 80.3 实际编码与统计

CodeT5p110m revision d9f3a534af4252f04b10cd9f78e05037542d10f6，fp16冻结、batch32、256token、256维、model_default池化；同旧M1资产/池化/精度，M1原128token不变。无下载/安装/升级。原名+局部masked共104836行，STATIC52418行。

"""+table+"""
8份两遍编码逐位相同、误差0、隐式尾截断0。四个masked任务各1个buggy_35任务实例七级后仍261token，第8级缩TO到256，标签保留，原名0次。每字段非空/unknown率、每维1比例、不按标签分组的统计及完整截断史见stats.json、encoded_text和fallback_examples。
"""+resources+"""含模型加载/文本限长/双遍推理/输出与校验，不是单纯GPU计算时间；peak不是整卡或未来训练峰值。未完成旧attempt无完整耗时，不补造数值。

### 80.4 验收、失败与恢复
"""+tests+"""
最终验收读取全部8CTX/4STATIC/4旧CODE清单，32组合不变式通过；facts精确身份和STATIC独立重算一致。原8H图/源码/运行引用仅作为冻结来源，不读取历史评分来生成特征。GPU离线锁沿用原.training.lock，串行且与训练互斥；新恢复索引严格记录首份复用+7新结果，未称作训练断点续跑。

原长任务被中断的根因无法从日志确定，没有据此宣称OOM、模型错误或训练完成。用户授权后仅新目录继续；旧encoding_status、未完成started及截断的测试日志保留。测试夹具和验收器修复没有改生产向量，也没有删测试、放宽未知/身份/数值断言。

### 80.5 命令、文档与归档
"""+commands+"""
产物CURRENT连接acceptance_v1验证与seal、stats和恢复编码索引。源码、可审查字段、清单、统计/命令/失败及通过日志入本次提交；NPZ、权重、HF缓存按旧规则本地保留。三历史文档只追加，document_before保存旧长度/SHA；新增报告与追加范围做doc_check --expect-cjk，避免中文问号损坏。实际产物在WSL项目目录，不向C盘额外复制模型或训练日志。

### 80.6 未完成项与停止位置
"""+limits+"""
完成本地NS-P3b提交后停止，不自动推送、不开始下一阶段。
"""
progress="""

## 2026-11-02 NS-P3b 完成：CTX/STATIC（修改 AI：Codex）

输入e77d42d3/PROMPTS r12，读取共享§5.1。git pull DNS失败有记录；本轮only original，从accepted_attempt4与text_v1生成。用户批准独立encode_ctx、精确AST临时sidecar和保留标签的第8级限长；保留anonymous接口但不新建匿名产物，masked为局部CTX名字对照。

新增ctx_alignment/ctx_fields/static_profile/behavior_schema/p3_prepare/p3_acceptance、offline/encode_ctx/ctx_budget及3组测试。K/L/M按unknown_fields逐字段清零+N，不因整组unknown丢确定信息。实际STATIC243维、N35；S3/S4=514/758维。

四任务AC合约/节点、重入合约/节点13693/7892/18610/12223行；8份CTX两次编码逐位一致、误差0，共104836向量，4份STATIC共52418。第8级仅四个masked各1次（七级后261→256，标签留）；全量masked残留标识符0，52 Oracle改名后STATIC/文本一致。统计/去重/耗时见stats.json和NS_P3B_REPORT。

原编码/回归进程消失、无失败或完成证据，原因未知；用户批准保留现场、复用首份成功并在resume_attempt2完成剩余7份，测试补完。encoding_index连接全部8份结果，不覆盖原目录。独立审查修正具名seal路径；扫描词表/临时篡改夹具修正留档，严格断言保留。

727+2653+223+6=3609测试通过，0失败/跳过，42既有警告；8CTX/4STATIC/4旧CODE核验，32组合真实装配通过。8H生效runtime/load及22,813冻结文件一致；原图/标签/折/HGT/tokenizer/旧CODE/facts不改。CURRENT连接验收seal与索引，详细选择/命令/失败记录见training_changes§80。

checked_call摘要未纳入本轮表，尚未消费；局部masked不消除原名CODE捷径。无HGT训练/F1/编译/NS-P4；本地提交、不自动推送。最终实验按用户计划在显存充足服务器运行，RTX3050 4GiB仅本机开发限制，服务器本轮未部署。
"""
policy="""

## 2026-11-02 NS-P3b 用户后续指令（修改 AI：Codex）

当前生产仍original；保留既有anonymous配置、text/CODE/carrier接口及历史文件供未来明确绑定的比较。本轮未读匿名产物、未生成匿名facts，不能称匿名事实→CTX全流程已接通。masked CTX只是局部名称对照；是否用于训练由后续计划决定，不自动切换主目标。
"""
for p,append in zip(paths,[handover,training,progress,policy]):
 with (ROOT/p).open("a",encoding="utf8") as f:f.write(append)
 assert hashlib.sha256((ROOT/p).read_bytes()[:before[p]["bytes"]]).hexdigest()==before[p]["sha256"]
print("Final report, statistics, and append-only records written")
