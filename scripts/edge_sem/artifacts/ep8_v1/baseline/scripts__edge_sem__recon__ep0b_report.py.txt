"""Append EP0b measurements while preserving EP0 and frozen evidence."""
import hashlib
from collections import defaultdict
from .common import ROOT, ref, read, write, checked
from .ep0b_common import OUT, TASKS


def pct(value):
    return "不可估" if value is None else "{:.2%}".format(value)


def append_checked(name, addition, baseline):
    path=ROOT/name
    raw=path.read_bytes()
    expected=baseline["documents"][name]
    assert len(raw)==expected["bytes"] and hashlib.sha256(raw).hexdigest()==expected["sha256"],name
    with path.open("a",encoding="utf8") as stream:
        stream.write(addition)


def describe():
    before=read(OUT/"before.json")
    guards={t:read(OUT/("guards_"+t+".json"))for t in TASKS}
    calls={t:read(OUT/("calls_refined_"+t+".json"))for t in TASKS[:2]}
    attrs={t:read(OUT/("attributes_"+t+".json"))for t in TASKS[:2]}
    summary=dict(version="ep0b-v1",input_head=before["head"],prompt=before["prompt"],
        status="EP0b measurements complete; registered CALL_SITE gate failed",
        next_stage_authorized=False,training_runs=0,graphs_written=0,attribute_vectors_written=0,
        guard_equivalence=dict(passed=True,function_instances=sum(r["counts"]["functions_checked"]for r in guards.values())),
        guards={},calls={},attributes={},tests={},revisions=ref(OUT/"revisions/call_diagnostic_revision.json"))
    modifiers={}
    for task,report in guards.items():
        summary["guards"][task]={k:report[k]for k in ("counts","unique_modifier","unique_nonmodifier","unique_combined","with_reverse","incoming_distribution")}
        detailed=[]
        for row in report["files"]:
            groups={}
            for fn in row["functions"]:
                for record in fn["records"]:
                    group=groups.setdefault(tuple(record["modifier"]),dict(anchors=set(),mapped=set(),sources=set(),applications=0))
                    ident=tuple(record["inner_anchor"])
                    group["anchors"].add(ident)
                    group["applications"]+=1
                    if record["graph_node"] is not None:
                        group["mapped"].add(ident)
                        group["sources"].add(record["graph_node"])
            for k,g in groups.items():
                detailed.append(dict(file=row["file"],source=row["source"],modifier=list(k),
                    distinct_inner_anchors=len(g["anchors"]),mapped_inner_anchors=len(g["mapped"]),
                    applied_guard_records=g["applications"],
                    prospective_modifier_edges=sum(p["modifier"] and p["source"] in g["sources"]for p in row["prospective_pairs"])))
        modifiers[task]=detailed
    write(OUT/"modifier_mapping_summary.json",modifiers)
    changes,examples={},{}
    for task,report in calls.items():
        summary["calls"][task]=report["summary"]
        old=read(OUT/("calls_"+task+".json"))
        assert old["ep0_call_sites"]==report["ep0_call_sites"]
        delta=[];grouped=defaultdict(list)
        for a,b in zip(old["edges"],report["edges"]):
            keys=("file","relation","source_node","target_node","edge_key")
            assert all(a[k]==b[k]for k in keys) and a["covered"]==b["covered"]
            if a["category"]!=b["category"]:
                delta.append(dict(identity={k:b[k]for k in keys},old=a["category"],new=b["category"],new_candidates=b["expression_candidates"]))
            if not b["covered"]:
                grouped[(b["relation"],b["category"])].append(b)
        changes[task]=delta
        examples[task]={r+":"+c:rows[:3]for (r,c),rows in grouped.items()}
        for relation in ("internal_call","external_call"):
            rows=[e for e in report["edges"]if e["relation"]==relation]
            summary["calls"][task][relation]["unique_function_pairs"]=len({(e["source_node"],e["target_node"])for e in rows})
            summary["calls"][task][relation]["covered_unique_function_pairs"]=len({(e["source_node"],e["target_node"])for e in rows if e["covered"]})
        summary["calls"][task]["unique_ep0_statement_pairs"]=len({(r["source_node"],r["target_node"])for r in report["ep0_call_sites"]if r["projected"]})
    write(OUT/"call_category_changes.json",changes)
    write(OUT/"call_gap_examples.json",examples)
    for task,report in attrs.items():
        part=dict(counts=report["counts"],shape_differences=report["all_shape_differences"],rates={})
        for relation in ("DATA_DEF_USE","READS_STATE","WRITES_STATE"):
            c=report["counts"][relation+"_value_shape"];total=sum(c.values())
            part["rates"][relation]=dict(total=total,resolved=c.get("resolved",0),multiple=c.get("multiple_declarations",0),success_rate=c.get("resolved",0)/total if total else None)
        summary["attributes"][task]=part
    for name,count in (("regression_edge_sem2",34),("regression_node_sem",1353),("regression_dfg_v2",2653)):
        receipt=read(OUT/"execution"/(name+".json"))
        assert receipt["exit_code"]==0
        checked(receipt["log"])
        summary["tests"][name]=dict(passed=count,receipt=ref(OUT/"execution"/(name+".json")))
    summary["test_total"]=sum(r["passed"]for r in summary["tests"].values())
    names=["guards_"+t+".json"for t in TASKS]
    names+=["calls_refined_"+t+".json"for t in TASKS[:2]]
    names+=["attributes_"+t+".json"for t in TASKS[:2]]
    summary["evidence_refs"]=[ref(OUT/n)for n in names]
    summary["measurement_limits"]=[
        "Coverage counts HCG multigraph edges, not call expressions; exact source-owner and target identity are required.",
        "Spelling locates gap candidates only; uncertain matching expressions remain in the denominator.",
        "No expression means no corresponding parsed callee after frozen postfix inspection, not proof the HCG is wrong.",
        "Library, super, modifier and unresolved expressions remain in the registered adjusted denominator.",
        "source_lines/target_lines are frozen HCG coordinates; expression lines and byte anchors are raw-source coordinates.",
        "No production graph or attribute vector is built. Modifier equivalence is within frozen analyzer support.",
        "Final experiments will run on a sufficiently provisioned server; local RTX3050 4GiB is development only; no server deployed here."]
    write(OUT/"summary.json",summary)

    lines=["\n\n## 9. EP0b：修饰器来源与调用覆盖复核（Codex，2026-11-10）\n",
      "依据PROMPTS r4，输入HEAD "+before["head"][:8]+"。旧EP0输入与产物保留，新增ep0b_v1。最终口径是summary.json与calls_refined_*；首轮calls_*和修订源码均保留。只解析和计数，不建图、不训练。\n",
      "### 9.1 修饰器内层来源\n",
      "guard_source.py复现冻结_modifiers的绑定/过滤步骤，调用_scope/_bindings/_lexical/_require/_guard。所需list接口返回record、invocation、inner_anchor；辅助inspect_modifier_guards返回unresolved/audit供验收，不修改冻结audit或modifier cache。文件头注明来源行范围与SHA。\n",
      "四任务共12285个函数实例（含无体声明）逐函数记录序列、顺序、unresolved与audit增量完全一致。按for_node保护语句扩展：\n",
      "|任务|函数实例|modifier记录映射|去重modifier边|非modifier边|合计正向GUARDS|含REV预计|\n|---|---:|---:|---:|---:|---:|---:|"]
    for task in TASKS:
        r=guards[task];c=r["counts"]
        lines.append("|{}|{}|{}/{}|{}|{}|{}|{}|".format(task,c["functions_checked"],c.get("modifier_mapped",0),c.get("modifier_records",0),r["unique_modifier"],r["unique_nonmodifier"],r["unique_combined"],r["with_reverse"]))
    lines+=["\ninner_anchor映射率均100%，无映射失败。按修饰器独立anchor、应用记录和预计边数见modifier_mapping_summary.json；每语句入边分布（含0）见summary.json.guards，两节点任务最多13条。记录数与去重边数分开；原多placeholder、缺失绑定、参数不符等仍回退，不扩大语义覆盖。\n",
      "### 9.2 CALL_SITE覆盖与停止门槛\n",
      "逐条核对HCG多重边(f,g,key)，仅当存在EP0原口径的(s→g)且s精确归f，才判覆盖。函数级多重边、去重函数对、调用表达式与语句级边的数量不能直接相减。\n",
      "|任务|internal_call边|覆盖|原覆盖率|无表达式排除|调整后覆盖率|80%门槛|\n|---|---:|---:|---:|---:|---:|---|"]
    for task in TASKS[:2]:
        r=summary["calls"][task]["internal_call"]
        lines.append("|{}|{}|{}|{}|{}|{}/{} = {}|不通过|".format(task,r["edges"],r["covered"],pct(r["coverage"]),r["no_expression_excluded"],r["covered"],r["adjusted_denominator"],pct(r["adjusted_coverage"])))
    lines+=["\n未覆盖internal_call逐类计数；代表性文件、行号、表达式仅在artifacts，不进入正文：\n","|类别|重入节点|访问控制节点|\n|---|---:|---:|"]
    categories=[("overload","重载"),("super","super"),("modifier","modifier端点"),("library_using","库/using"),("no_call_expression","未找到对应表达式"),("multiple_declarations","同名候选对应多个声明"),("state_initializer","状态变量初始化"),("modifier_argument","modifier调用参数"),("other","其他")]
    for k,label in categories:
        lines.append("|{}|{}|{}|".format(label,summary["calls"][TASKS[0]]["internal_call"]["categories"].get(k,0),summary["calls"][TASKS[1]]["internal_call"]["categories"].get(k,0)))
    lines+=["\n同名表达式仅定位缺口，不证明绑定到HCG目标；尤其外部成员调用的同名也可能属于其他对象。不确定项保留分母。冻结AST会把一元/二元上下文包进callee；首轮误列无表达式的重入66条、访问控制55条（含external_call）经冻结_postfix定位后改列其他，其中internal_call为30/31条。覆盖布尔与EP0候选完全不变，修订SHA和逐条变化见revisions与call_category_changes.json。\n",
      "external_call仅单列：重入7/707、访问控制6/688对应EP0候选，其余主要为库或外部成员调用，超出当前内部调用子集，不作为内部调用门槛。internal_call去重函数对为396/530，覆盖146/164；EP0语句级去重边180/186。并行边与多个语句调用同一函数导致计数不同。\n",
      "**CALL_SITE预登记门槛未通过，停下报告，不自动进入EP1/EP2。** 这衡量当前受限子集与作者HCG的对应覆盖，不是真实内部调用召回率。不能删掉库、super或unknown凑到80%；无表达式也不代表已证明作者图错误。建议先审查范围排除、可唯一绑定但AST形状不支持的调用，以及HCG对应争议，再决定EP2修订；本轮只提出，不实施，不改门槛。\n",
      "### 9.3 r4属性来源可行性\n",
      "分母是已有数据边的变量证据，一条边可有多条证据。L1变量由完整symbol身份查冻结声明表取得，再按r4在目标语句匹配标识符并root_binding；L2用封存变量名，WRITES_STATE在源语句解析。缺失或任一未解析匹配保持unknown，不猜类型。\n",
      "|任务|关系|类型可解析|成功率|多声明|\n|---|---|---:|---:|---:|"]
    for task in TASKS[:2]:
        for relation,r in summary["attributes"][task]["rates"].items():
            lines.append("|{}|{}|{}/{}|{}|{}|".format(task,relation,r["resolved"],r["total"],pct(r["success_rate"]),r["multiple"]))
    lines+=["\n|任务|decl_or_param|assign|compound|incdec_or_delete|unknown|\n|---|---:|---:|---:|---:|---:|"]
    for task in TASKS[:2]:
        c=attrs[task]["counts"]["def_kind_edge_evidence"]
        lines.append("|{}|{}|{}|{}|{}|{}|".format(task,*[c.get(k,0)for k in ("decl_or_param","assign","compound","incdec_or_delete","unknown")]))
    lines+=["\ndef_kind未知为47/4200（1.12%）、49/5168（0.95%）；唯一“定义节点+变量”另报，避免高扇出重复计数。\n",
      "|任务|write_access plain|indexed|member|other/unknown|\n|---|---:|---:|---:|---:|"]
    for task in TASKS[:2]:
        c=attrs[task]["counts"]["write_access_event"]
        lines.append("|{}|{}|{}|{}|{}|".format(task,c.get("plain",0),c.get("indexed",0),c.get("member",0),c.get("other",0)+c.get("unknown",0)))
    lines+=["\n写操作按token：重入assign/increase/decrease/other=1783/236/209/26，访问控制680/36/36/15；x = x + 1保持assign，其他复合算符不猜increase/decrease。真实两任务shape_safe差异类型集合均为空；addressBook等反例测试通过，本批没有实际类型分类变化。全部类型名及逐条证据见attributes_*；没有生成73维向量。\n",
      "### 9.4 验收与边界\n",
      "CPU测试EdgeSem34、NodeSem1353、DFG v2 2653，共4040通过。实际命令、环境、耗时、退出码与日志SHA见execution。verification.json核对冻结源码、_code_refs、8H归档加载、输入/EP0产物和四文档旧字节前缀。没有HGT训练、GPU运行、历史模型权重加载、新图或属性向量。\n",
      "最终实验在显存充足服务器另建批次，RTX3050 4GiB只是本机开发条件；本轮未部署/验收服务器。主视图D1、P2等决定未被本次只读任务批准。\n"]
    append_checked("scripts/edge_sem/RECON.md","\n".join(lines),before)

    handover="""\n\n## 2026-11-10 EdgeSem EP0b完成，CALL_SITE门槛未通过（修改 AI：Codex）

按PROMPTS r4完成modifier内层来源、调用覆盖和属性计数。guard_source.py与冻结_modifiers在四任务12285个函数实例上记录序列、unresolved/audit完全一致；两节点任务616/715条modifier守卫均精确映射，预计GUARDS正向总数6921/4502（只计数）。

internal_call覆盖178/464、197/591；扣除无表达式76/76后45.88%/38.25%，低于预登记80%。停在EP0b，不自动实现后续调用边或训练；需审查范围排除、AST形状和HCG对应关系。诊断分类修正了取反/组合上下文调用的定位，首轮输出、源码与逐条变化均保留，EP0候选和门槛不改。

r4类型解析成功率89.57%–99.03%，未确认项保留unknown；真实shape_safe差异为空，反例测试通过。34+1353+2653=4040项测试通过，冻结代码/输入与EP0产物保持。详见RECON.md§9、ep0b_v1/summary.json与verification.json。

最终实验在显存充足服务器另建批次，本机RTX3050 4GiB仅限制开发；本轮未部署服务器、未训练。本地提交，不自动推送。
"""
    append_checked("HANDOVER.md",handover,before)
    progress="""\n\n## EP0b：修饰器来源与CALL_SITE覆盖（Codex，2026-11-10）

依据r4/§4.1，输入HEAD 0ddbb07e；按已有授权快进同步，远端已最新。新增guard_source.py、recon/ep0b_{common,run,guards,calls,attributes,report,verify}.py及两份测试；独立ep0b_v1，RECON只追加§9，旧ep0_v1与recon.json保留。

list API返回record/invocation/inner_anchor；辅助inspect_modifier_guards供unresolved/audit核验，不修改原audit/cache。12285个函数实例逐一等价。节点modifier映射616/616、715/715，去重总GUARDS6921/4502；合约1346/1346、1398/1398，总10172/8098。按修饰器和每语句入边分布均保存。

内部调用覆盖178/464、197/591；排除无表达式76/76后45.88%/38.25%，未达80%。外部调用7/707、6/688单列。首轮诊断遗漏一元/二元callee后缀，仅用冻结_postfix修正候选定位，121条由无表达式改其他；旧输出/源码及变更保留，精确覆盖和EP0语句边180/186不变，不扩展解析或改门槛。

属性按r4计数，成功率89.57%–99.03%，多声明0，unknown不猜测；def_kind未知47/4200、49/5168；write_access均为plain/indexed/member。shape_safe真实差异为空，反例通过，无属性向量。

实际测试命令记录于execution：CPU pytest -q -p no:cacheprovider分别运行edge_sem/tests、node_sem/tests、DFG/dfg_v2/tests，34+1353+2653=4040通过。doc_check、冻结SHA、_code_refs、8H.load、EP0产物和旧文档前缀验收见verification.json。
EP0b完成，CALL_SITE门槛未通过，停止后续落地并提交审查，不自行改EP2或启动训练。最终实验在显存充足服务器，本机4GiB只用于开发；本轮本地提交，不自动push。
"""
    append_checked("scripts/edge_sem/PROGRESS.md",progress,before)
    training="""\n\n## 100. 2026-11-10 EdgeSem EP0b来源等价与调用覆盖（修改 AI：Codex）

### 版本、授权和范围

用户要求完成EP0b。先读PROMPTS r4、共享上下文与各项要求；输入edge-sem@0ddbb07e，沿用已批准的git pull --ff-only origin edge-sem，Windows Git经既有代理返回Already up to date。未改主视图D1、训练协议D2或D3状态。独立ep0b_v1排他写入；旧EP0、DFG、NodeSem、作者代码与封存输入保留，RECON只追加第9节。无HGT拟合、GPU、历史权重加载、新图或属性向量。

### 守卫来源实现和验收口径

guard_source.py头部注明facts_guards.py第333–383行及SHA bb2bad3e65aab2e35a88955b7cc33d53ec324471156cca2f6987b377d24fbda5。复制仅_modifiers控制步骤，调用冻结_scope、_bindings、_lexical、_require、_guard及children/unwrap/walk。保留规则1/2/3并按原规则构造5/5p；record剔除内部字段，额外返回invocation和inner_anchor。required list接口不携带全局计数，另用inspect_modifier_guards返回unresolved/audit，不写原analyzer.audit或modifier cache。无语义替代设计。

逐函数public记录的顺序、字段、条数、unresolved与audit增量比较：重入节点2283、访问控制节点2206、重入合约4035、访问控制合约3761，共12285，全部相等。每个for_node的modifier子序列也按顺序对齐。按模板取内层anchor后全部映射：616/715/1346/1398条记录；去重modifier正向边616/715/1344/1397，与非modifier6305/3787/8828/6701合并为6921/4502/10172/8098。按modifier独立anchor/应用记录/预计边数及每语句入边分布保存，节点最大13条。多placeholder、缺失绑定及参数不符继续原有回退。

### CALL_SITE诊断、修订和门槛

沿用EP0的STATEMENTS、owned_nodes和classify/resolve_callable，不扩展内部调用集合。182/188个唯一绑定表达式得到180/186个语句级边，和EP0相同。每条HCG多重边(f,g,key)按精确owner及callee图身份核对，不能按同名猜匹配。

首轮gap诊断直接读取callee名字；抽查源码发现冻结grammar将取反/组合上下文包进callee，部分真实表达式被误记为无表达式。保留call_diagnostic_v1.py及calls_*.json；仅诊断定位改用冻结sem._postfix，新测试通过后生成calls_refined_*。重入66条、访问控制55条（含external_call）由无表达式改为其他，其中internal_call30/31条；覆盖布尔、EP0候选和门槛完全不变。旧/新源码SHA与逐条变化封存于revisions和call_category_changes.json。这是测量脚本纠错，不是生产绑定扩展，没有重跑任何模型。

最终重入internal_call464条覆盖178（38.36%）；缺口重载18、super2、modifier10、库/using38、无表达式76、多个同名声明75、其他67。访问控制591覆盖197（33.33%）；对应缺口18/2/8/27/76/150/113。状态初始化与modifier参数类别本批均0。只扣除无表达式后178/388=45.88%、197/515=38.25%，两者均低于预登记80%。外部调用单列7/707、6/688；主要超出内部调用子集，不作为内部解析准确率。

函数级去重对为396/530，覆盖146/164，与语句级180/186分母不同；并行边和多语句调用同一函数会改变计数。同名候选仅供诊断，成员调用不一定指向HCG同名目标，这些不确定项仍在分母。无表达式表示AST/冻结后缀定位未找到对应callee，不宣称证明作者HCG错误。代表性源码、文件和行号只在artifacts；raw byte anchor/source SHA可复核，保存的HCG行坐标与实际表达式行坐标明确区分。

### r4属性可行性与限制

DATA_DEF_USE通过FileCFG.symbol按完整身份查冻结符号表，不截取symbol字符串猜变量。随后按r4使用语句匹配同名标识符并root_binding；L2由封存证据取得变量名，写边用源语句。多声明或任一未解析匹配保留unknown；本次多声明0。
按变量证据的解析成功数：重入DATA_DEF_USE4150/4200、READS_STATE3042/3187、WRITES_STATE2142/2254；访问控制5118/5168、1105/1185、687/767，比例89.57%–99.03%。分母是边变量证据，不是单纯图边；别名/无同名出现或绑定类型未知不猜测。成功率不等于完整别名/类型系统正确性证明。

def_kind（decl_or_param/assign/compound/incdec_or_delete/unknown）重入3770/263/73/47/47，访问控制4857/200/7/55/49；唯一“定义节点+变量”另报。write_access按L2 occurrence精确AST：plain/indexed/member重入1036/972/246，访问控制352/277/138，other/unknown均0。write_op assign/increase/decrease/other为1783/236/209/26、680/36/36/15；x=x+1仍为assign，其他复合运算不猜增减。

shape_safe仅在侦察模块实现r4的精确address/address payable判断，mapping/array优先级保留。addressBook等反例测试通过，真实两任务与旧shape不同的类型名集合为空，不宣称本批有类型恢复收益。没有修改facts_ast或生成73维向量。

### 回归、记录及停止位置

新增测试覆盖继承、参数、早退、无/多placeholder、constant、类型、赋值语义、调用归属、重载和callee后缀；最终EdgeSem34、NodeSem1353、DFG v2 2653，共4040通过。execution保存命令/耗时/退出码/log SHA；verification.json验冻结文件、输入、_code_refs、8H.load、EP0产物及四文档旧字节前缀，doc_check确认UTF-8。

EP0b测量交付完成，但CALL_SITE门槛失败，停止后续调用边落地，不自动进入EP1/EP2或训练。建议下一步先审查范围排除、可绑定但AST形状不支持的调用与HCG对应争议，再由用户确定EP2修改；本轮只记录，不实施、不调整80%。最终实验会在显存充足服务器另建批次，本机RTX3050 4GiB只用于开发，未部署服务器。本轮代码/证据与三份记录文档本地提交，不自动push。
"""
    append_checked("docs/training_changes_2026-10-07.md",training,before)
    print("EP0b summary and append-only reports written",flush=True)


if __name__=="__main__":
    describe()
