"""Append-only UTF-8 EP4 documentation from successful run receipts."""
import hashlib
import json
from pathlib import Path
from .ep4_common import OUT
from scripts.edge_sem.io import read, ref, write, ROOT
from scripts.edge_sem.attrs import EDGE_FEATURE_NAMES, GROUPS

def pct(x):
    return "-" if x is None else "{:.3f}%".format(x*100)

def table(headers,rows):
    return "\n".join(["| "+" | ".join(headers)+" |","|"+"|".join(["---"]*len(headers))+"|"]+
        ["| "+" | ".join(str(x) for x in row)+" |" for row in rows])+"\n"

def document():
    data=read(OUT/"summary.json");before=read(OUT/"before.json")
    tests=data["execution"]
    for name in ("edge_tests_final","nodesem_tests","dfg_tests","attrs_target_complete","attributes_build_attempt3"):
        assert tests[name]["exit_code"]==0,name
    intro="""按PROMPTS.md r11完成EP4：通用F4构建、74维边属性、两任务端点检验与共同核心位。属性从原名源码、冻结事实和封存L1–L3证据计算；反向边留模型接入时复制正向向量。本轮未训练、未用GPU，没有检测性能或显存结论。旧图、标签、折、特征、初值、checkpoint和计划不改。"""
    sections=["# EP4完成报告（2026-11-10，修改AI：Codex）",intro,
        "## 通用构建与历史一致性",
        "生产build_f4/guard_edges去除recon和EP2/EP0运行依赖；历史比对移至recon/ep4_rebuild.py。新manifest版本edgesem-f4-v1，默认加载拒绝旧版本；历史产物显式只读核验。两个节点任务的新边与EP3逐字节一致，守卫分类和映射计数不变。"]
    build=[]
    for task,r in data["rebuild"].items():
        c=r["counts_by_relation"];g=r["guards"]["counts"]
        build.append([task,c["MOD_APPLY"],c["CALL_SITE"],c["GUARDS"],g["records"],
            str(g["nonmodifier_mapped"])+"/"+str(g["nonmodifier_records"]),
            str(g["modifier_mapped"])+"/"+str(g["modifier_records"]),g["unknown_targets"]])
    sections.append(table(["任务","MOD_APPLY","CALL_SITE","GUARDS","守卫记录","普通映射","modifier映射","unknown目标"],build))
    sections.append("""合约任务只验证通用构建入口，不进入本机E-A/E-B。重入合约549个modifier应用去重为547条边；访问控制527个去重为526条。旧EP0访问控制计数528额外遍历了一个fallback_receive_definition，正式MOD_APPLY固定仅针对function_definition/constructor_definition。文件0x0d689d1d3ef39e379329d9fc88eabceccc1215a0.sol，源码SHA ac6e70721c9d4ff51c6c6653195b62892672321253cf38883bd5d4d771bb82de，fallback偏移3383，modifier跨度3409–3418。未扩展规则迎合旧计数；守卫记录10274/8165均与EP0一致，映射缺失为0。证据见development/contract_scope.py及execution/contract_scope.log。""")
    sections.append("## 属性产物和端点筛选")
    totals=[]
    for task,r in data["tasks"].items():
        t=r["totals"];totals.append([task,t["edges"],t["all_zero_edges"],pct(t["all_zero_fraction"]),r["diagnostic_edges"]])
    sections.append(table(["任务","属性行","全零行","全零比例","含缺项/未知诊断行"],totals))
    root=Path(read(OUT/"resume2.json")["out_dir"])
    sel=data["selection"]
    sections.append("有效目录："+str(root.relative_to(ROOT))+"。每任务有attrs.npz、manifest/seal、stats.json、diagnostics.json、fact_provenance.json和endpoint_test.json；共同layout/selection封存74维布局和共同筛选。uint8二值矩阵通过文件、端点、关系及多重边序号精确对齐；来源SHA、行序及numeric_digest均核验。")
    sections.append("核心"+str(len(sel["core_indices"]))+"维："+str(sel["core_indices"])+"。")
    sections.append("上下文"+str(len(sel["context_indices"]))+"维："+str(sel["context_indices"])+"；unknown位可同时属于两组。")
    sections.append("两任务都全零而未纳入核心的候选："+str(sel["all_zero_candidates"])+"；第15位始终停用。")
    sections.append(table(["核心位","名称","共同决定"],[
        [b,EDGE_FEATURE_NAMES[b],sel["decisions"].get(str(b),"unknown位随限定字段归组")] for b in sel["core_indices"]]))
    sections.append("门槛固定：同关系同侧至少2条边且至少一条为1才算合格；汇总合格数≥30且恒定比例≥99%时移入上下文。任一任务判为端点便移出共同核心；两侧不足30则保留并标未判定。未判定不等于已证明是独立边信息。unknown位随限定字段归组，不参与端点检验。筛选不使用标签或模型分数。")
    unresolved=sum(v=="undetermined" for v in sel["decisions"].values())
    sections.append("需要保留的实质局限：共同核心里有"+str(unresolved)+"个已知属性位仍是样本量不足的未判定项；它们按预登记规则保留，不作为新增独立信息已获证实。READS_STATE/ENV_FLOW等关系的use_context没有精确dfg.to来源，全0不表示没有上下文；end_if和部分控制边缺少可映射的语义CFG端点，unk_cfg比例高。后续解释与规则基线须读取相应unknown/缺口记录，本轮不扩展冻结事实来填补。")
    sections.append("## 每关系每组非零比例")
    groups=list(GROUPS)
    for task,r in data["tasks"].items():
        sections.append("### "+task)
        sections.append(table(["关系","边数","全零"]+groups,[
            [rel,v["edges"],pct(v["all_zero_fraction"])]+[pct(v["groups"][g]["fraction"]) for g in groups]
            for rel,v in r["by_relation"].items()]))
        sections.append(table(["关系","unk_cfg","unk_dfg","unk_order","unk_state","unk_guard"],[
            [rel]+[str(v["bits"][EDGE_FEATURE_NAMES[i]]["ones"])+" / "+pct(v["bits"][EDGE_FEATURE_NAMES[i]]["fraction"]) for i in range(68,73)]
            for rel,v in r["by_relation"].items()]))
        sections.append("来源缺口："+json.dumps(r["source_gaps"],ensure_ascii=False,sort_keys=True)+"。")
    sections.append("stats.json另保存每位在原作者正/负目标节点入边中的比例。正负按node_info_vulnerabilities原规则（None为0，非None为1，env排除），不是L-audit；只在属性、筛选与seal完成后读取，不参与特征、样本、阈值或核心位决定。")
    sections.extend(["## 已批准调整与边界",
    """1. call_3ed2f55f68424011a5631df0cab83e86：同一数据边可能承载多个变量。var_kind/value_shape按全部证据取并为多热，仍74维，不拆边、不任选一个变量；其他单热组不变。
2. 同一批准：use_context仅从当前src/dst精确匹配的dfg.to取sink。READS_STATE/ENV_FLOW的源缺少该字段，WRITES_STATE及参数入口等可能无匹配，置0并记录source_gaps；不发明上下文。相应call/arith位仍受已知use_context限制。
3. call_ce3526a147bb49c0bb210e8a9c1349a6：五个unk位未覆盖全部未知来源；函数汇总、返回值处理、版本区间等未知置0，并逐边记录unknown_fields原因，不加维或借用其他unk含义；这些0不证明已确认不存在。
4. call_52397237416e41b3baa8612deb0ad2b4：首次因int原节点ID与str环境ID排序失败，改用保留类型和顺序的事实行数组计算摘要。旧attributes目录、失败日志和旧源码保留，批准后新建attributes_attempt2；没有生成NPZ，也没有训练。
5. call_fa5c42293d4747daa5a6ad5932843d4d：第二次发现两任务各22条依赖指向for头i++，冻结NodeSem将raw update_expression归other，dfg整组为空；仅此时从已精确核验的封存L1 symbol取var_kind并记录来源，非空facts不一致仍失败。未改NodeSem、DFG、图或事实，批准后新建attributes_attempt3。44条证据保存在development/dfg_target_diagnosis.json。
6. MOD_APPLY通过调用F取得守卫并按inner_anchor落入M过滤；空函数体仍有效，只加锁modifier无守卫时为0且不是unknown。GUARDS所有evidence取并，每任务12个unknown目标保留。
7. 冻结loop_cond操作数为空，49–54仍0；x=x+1记assign，其他未列写操作保持0；env14个保留键只映射表中四类。recursive_method_call全零。语义CFG或类型缺口按unk及sidecar记录，不宣称完整程序语义。"""])
    sections.append("## 验证与失败保留")
    for name in ("edge_tests_final","nodesem_tests","dfg_tests","attrs_target_complete"):
        r=tests[name];log=Path(r["log"]["path"]).read_text()
        result=next((l for l in reversed(log.splitlines()) if " passed" in l),"见日志")
        sections.append("- "+name+"："+result+"；exit 0。")
    sections.append("""定向测试覆盖74维、多证据类型、循环/调用路径、call返回检查、modifier独立来源、守卫操作数、unknown、端点门槛、快速改名、标签扰动不变、错误source/layout/图/数组拒绝、混合ID摘要及空dfg来源。
开发失败日志也保留：选择器误命中函数全文；参数入口没有dfg.to；tuple调用选择器需完整前缀；全零unknown测试必须提供正例才能测试继承；新循环测试的旧夹具没建raw update节点，补真实节点角色后通过。诊断脚本直接按路径启动缺包导入，改为-m入口。上述未改变冻结分析器，也不是训练或seed重复。
最终ep4_verify重新核对冻结源码、旧产物、8H只读load、DFG_code_refs、原图指纹/节点/原边、EP3边字节、属性行序与摘要、守卫并集、library和unknown位、端点筛选与统计重算。三文档原字节前缀保持，UTF-8/中文检查通过后提交；机器收据为artifacts/ep4_v1/verification.json。""")
    sections.append("## 文件与实际命令")
    sections.append("""生产代码：io.py、attrs.py、attr_sources.py、attr_batch.py、attr_stats.py及build_f4/guard_edges最小解耦；tests/test_f4_generic.py、test_attrs.py、test_attr_store.py与ep4_attributes.sol；recon/ep4_*为基线、只读历史比较、记录器、报告与核验。
生产入口为python -B -m scripts.edge_sem.attr_batch --out <新的目录>。write_attributes(task_id,out_dir)同样完成两个任务共同筛选，再返回指定任务manifest。所有目录拒绝覆盖。以下为实际运行命令，包含失败和诊断；不可原路径重复执行覆盖现场。""")
    for name,r in tests.items():
        sections.append("- "+name+"（exit="+str(r["exit_code"])+"）： "+" ".join(r["command"]))
    sections.extend(["## 后续与停止位置",
    """EP4完成属性准备，不证明检测提升。EP5真实全量改名/可达性闸门、EP6边感知层与EP7以后计划/训练尚未执行；快速fixture改名测试不能替代EP5。
D1匿名主视图、D2 P2协议、D3七类冻结仍须训练前确认，原名属性计算或历史夹具不构成授权。最终实验将在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机开发限制；本轮未部署服务器、未更改训练配置。产物留WSL，未向C盘另写大型缓存。按共享流程本地提交，停在EP4，不自动push。"""])
    report="\n\n".join(sections)+"\n"
    target=ROOT/"scripts/edge_sem/EP4_REPORT.md"
    with target.open("x",encoding="utf8") as f:f.write(report)
    detail=report[report.index("## 通用构建"):]
    handover="\n\n## 2026-11-10 EdgeSem EP4完成：通用F4与74维属性（修改AI：Codex）\n\n"+intro+"\n\n"+table(["任务","属性行","全零行","全零比例","诊断行"],totals)
    handover+="\n核心"+str(len(sel["core_indices"]))+"维，上下文"+str(len(sel["context_indices"]))+"维，unknown位可共享。两个节点任务F4与EP3逐字节一致，两合约任务只作构建冒烟。两次属性失败保留，用户批准后在第三目录完成；全部调整、统计与命令见scripts/edge_sem/EP4_REPORT.md及训练变更文档§107。\n\n"
    handover+="冻结代码/历史产物、8H load与DFG引用核验通过，三套CPU回归和文档检查完成。后续EP5/EP6未执行，D1–D3尚待训练前确认。最终实验将在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机限制；产物留WSL。本地提交，不自动push。\n"
    additions={
        "HANDOVER.md":handover,
        "docs/training_changes_2026-10-07.md":"\n\n## 107. EdgeSem EP4：通用F4与确定性边属性（2026-11-10，修改AI：Codex）\n\n"+intro+"\n\n"+detail,
        "scripts/edge_sem/PROGRESS.md":"\n\n# EP4：通用F4、74维属性与端点检验（2026-11-10，修改AI：Codex）\n\n"+intro+"\n\n"+detail}
    for name,text in additions.items():
        p=ROOT/name;original=p.read_bytes();r=before["documents"][name]
        assert len(original)==r["bytes"] and hashlib.sha256(original).hexdigest()==r["sha256"]
        with p.open("ab") as f:f.write(text.encode("utf8"))
    write(OUT/"document_outputs.json",dict(report=ref(target),documents={n:ref(ROOT/n) for n in additions}))
    print("EP4 report and three records appended in UTF-8",flush=True)

if __name__=="__main__":document()
