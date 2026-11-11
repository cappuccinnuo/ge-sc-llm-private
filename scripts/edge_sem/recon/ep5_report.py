"""Generate EP5 UTF-8 documents from completed CPU receipts."""
import hashlib
import re
from .common import ROOT,read,write,ref,checked
from .ep5_common import OUT,TASKS

def table(headers,rows):
    def cell(x):return str(x).replace("|","/").replace("\n"," ")
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"]+
                     ["| "+" | ".join(cell(x) for x in r)+" |" for r in rows])+"\n"

def main():
    before=read(OUT/"before.json")
    anon_path=OUT/"anonymous_gate_attempt3/summary.json"
    topo_path=OUT/"topology_attempt2/summary.json"
    anon=read(anon_path);topo=read(topo_path);delta=read(OUT/"attribute_delta.json")
    assert anon["passed"] and topo["passed"] and delta["passed"]
    tests=[]
    for name,title in [("edge_tests","EdgeSem"),("nodesem_tests","NodeSem"),("dfg_tests","DFG v2")]:
        r=read(OUT/"execution"/(name+".json"));assert r["exit_code"]==0
        count=int(re.findall(r"(\d+) passed",checked(r["log"]).read_text())[-1])
        tests.append([title,count,round(r["seconds"],2),name+".json"])
    total=sum(t[1] for t in tests)
    selection=read(OUT/"attributes/selection.json")
    cases=read(checked(topo["reachability"]))
    stats={t:read(checked(topo["tasks"][t]["graph_statistics"])) for t in TASKS}
    attrs={t:read(OUT/"attributes"/t/"manifest.json") for t in TASKS}
    random={t:read(checked(topo["tasks"][t]["placebo_audit"])) for t in TASKS}
    permutations={t:read(OUT/"topology_attempt2"/t/"permutation_audit.json") for t in TASKS}
    names={"reentrancy_node":"重入节点","access_control_node":"访问控制节点"}
    attr_table=table(["任务","正向属性行","原第20位=1","新第20位=1","循环头例外"],
        [[names[t],attrs[t]["rows"],delta["tasks"][t]["per_relation_bit20"]["DATA_DEF_USE"]["old"],
          delta["tasks"][t]["per_relation_bit20"]["DATA_DEF_USE"]["new"],len(delta["tasks"][t]["ctx_in_loop_zero"])] for t in TASKS])
    anon_table=table(["任务","文件实例","实际改名通过","原文回退通过"],
        [[names[t],anon["tasks"][t]["files"],anon["tasks"][t]["statuses"]["renamed"],anon["tasks"][t]["statuses"]["fallback"]] for t in TASKS])
    graph_table=table(["任务","剖面","节点数","反射后边数","canonical关系数","关系名数"],
        [[names[t],p,s["nodes"],s["edges"],s["canonical_relations"],s["relation_names"]] for t in TASKS for p,s in stats[t].items()])
    reach_table=table(["任务","文件 / source SHA前12位","图节点ID","G3R","G3R-T","G4R","增加"],
        [[names[c["task_id"]],c["file"]+" / "+c["source_sha256"][:12],c["original_graph_node_id"],
          c["profiles"]["G3R"]["total_unique"],c["profiles"]["G3R-T"]["total_unique"],
          c["profiles"]["G4R"]["total_unique"],c["delta_total_unique"]] for c in cases])
    placebo_table=table(["任务","E1边","最终改变的边","零次改接分组/全部","属性实际变化行/全部"],
        [[names[t],random[t]["total_edges"],random[t]["changed_edges"],
          str(random[t]["zero_switch_partitions"])+"/"+str(len(random[t]["partitions"])),
          str(sum(v["changed_vectors"] for v in permutations[t]["per_relation"].values()))+"/"+str(attrs[t]["rows"])] for t in TASKS])
    report="# EdgeSem EP5 结果报告（2026-11-11）\n\n"
    report+="基于PROMPTS r12、HEAD "+before["head"]+"。只完成两个节点任务的CPU诊断与属性修正，未训练、未用GPU、未推进EP6。\n\n"
    report+="## EP4修正与硬条件\n\n"+attr_table
    report+="""
自然循环沿用回边目标支配源的定义；删除全部回边后，只要任一def/use块对前向可达即否决循环携带标记，已批准的同图节点自依赖例外除外。两个任务edge_keys逐行相同，除第20位外的73列逐位相同，新第20位为旧值的子集。其他关系第20位仍全0。EP4 attributes_attempt3及其seal保持原字节；后续EP6–EP9必须读取ep5_v1/attributes的两个manifest。

全零候选6/14/33/38进入core并标no_local_support，第15位仍禁用。core由46增至50，context为26不变，原向量仍74维；69/71/72在两组共享，因此组长度不能简单相加。selection.json同时保存每任务verdict。第20位端点检验：重入源29组中26组固定（0.896552）、目标49组中0组固定；访问控制源30组中27组固定（0.9）、目标56组中0组固定；均为core，第68位仍随组归入core。

use_context及依赖它的细项继续只适用于DATA_DEF_USE；其他数据关系没有对应sink时记不适用，不借另一条边推断上下文。这项诊断澄清没有改变其他73列。

## 用户批准的选择与恢复

1. 同语句循环自依赖：按§3.3明确例外，同一图节点的自依赖在自然循环内记1；其余边严格按§4.7多块可达规则。不同图节点即使在同块，仍为前向可达。
2. 循环头上下文：第20位=1且第59位=0的重入24条、访问控制25条，均通过精确AST核对为最外层for/while循环头。冻结loop.bound只看外层循环，不把循环头自身算入；用户批准保留第20位和其他73位。初次attribute_delta.json的unexplained字段保留历史值，最终解释见loop_context_audit.json与批准记录；这些不是unknown，也没有删除边。
3. 状态初始化callable：首个名字闸门在LogFile状态初始化处失败；冻结L2将state_variable_declaration也视为callable。用户批准按完整AST坐标补齐此接口类型，回归后用新attempt继续。
4. 重复文本end_if：第二次闸门在重入buggy_15.sol的三个end_if停止，原文相同但匿名后对应不同声明。用户批准仅在唯一neg_next父节点具有精确if AST锚点、原文本完全匹配时继承该身份。普通节点仍用冻结node_code_view；其他歧义仍失败。缺失、多重及错误角色父节点均有反例测试。
5. 历史案例摘要：首次topology误用feature_view.graph_fingerprint比较历史store的fingerprint。原图文件SHA本来一致；诊断确认graph_audit.fingerprint及integration.computation_fingerprint均等于历史值。入口改用这两种原算法，feature_view仅用于前后不变性。4项测试通过后用户批准topology_attempt2继续。

前两次匿名失败、首次统计失败、源码快照和日志均保留，批准记录见decisions.json、loop_context_decision.json、anonymous_resume1/2.json及topology_resume1.json。未修改冻结模块、原图、标签或属性选择规则来迎合检查。

## 名字不变性与覆盖

"""+anon_table+"""
54/128个文件实例实际改名，74个按原匿名器回退为原文。回退只是恒等对照，不是非平凡不变性证据；不能宣称对所有Solidity语法或全量匿名覆盖均已证明名字无关。逐文件回退原因与绑定记录见anonymous_gate_attempt3。

适配器仅按“出现位置→声明→新名”精确翻译L1 symbol/函数/事件、L2状态名及callable、L3锚点和F3 state_vars；没有全局名字替换或近邻行猜测。源码SHA只在内存检查副本更新，extract_source传original_names以保留旧式构造函数判定。未被消费的诊断名字明确保留为历史诊断，不作为匿名连接依据。

沿用冻结anon_parity：匿名内存源码不能复用绑定原磁盘SHA的编译器记录，实际改名只使用未改变的pragma，回退继续使用原记录。先核对原名重算与封存F4/EP5矩阵相同，再比较匿名边集合与属性。比较使用原图节点身份和edge_key，不比较必然改变的AST字节偏移。原名生产输入不变，未写入匿名正式图或训练输入。

## 两跳可达性

使用历史persistent_cases.json的全部21个持续漏报节点，按task/file/source SHA/原图节点ID/类型及图双摘要对齐。计数为生产materialize反射后的有向最短距离1至2跳，排除起点、按节点去重，四种证据总数取并集。

证据固定于原名事实：external.kinds非空的语句/条件、state.writes非空的语句/条件、封存GUARDS来源节点、node_kind为modifier的定义。只计已确认事实，unknown空列表不解释为没有漏洞。历史预测只选择文档指定的诊断案例，不参与边和属性构建。

"""+reach_table+"""
重入2/6个案例增加：modifier_reentrancy.sol节点8498从5到7，新增8501/8504（8501同时是外部调用和守卫）；reentrancy_bonus.sol节点12从3到5，新增外部调用7和状态写6。访问控制0/15增加，其余19个案例不变。存在正增量，因此不触发“所有案例均无增量”的全局标红条件；访问控制无增量仍是限制。

这不是检测收益。G3R与G3R-T的数量相同也不代表关系参数或模型输出相同。逐类别数量、节点集合、距离和完整SHA见topology_attempt2/reachability.json与CSV；不改标签、不删困难案例。

## 反射后边统计

"""+graph_table+"""
完整逐canonical边数、逐关系边数及逐类型入度记录见topology_attempt2/<task>/graph_statistics.json。入度包括平行边和该类型的零入度节点：
"""
    degree_rows=[]
    for t in TASKS:
        for typ in sorted(stats[t]["G3R"]["indegree_by_node_type"]):
            ss=[stats[t][p]["indegree_by_node_type"][typ] for p in ("G3R","G3R-T","G4R")]
            degree_rows.append([names[t],typ,ss[0]["nodes"]]+["{:.6f}".format(s["mean_indegree"]) for s in ss])
    report+="\n"+table(["任务","节点类型","节点数","G3R均入度","G3R-T均入度","G4R均入度"],degree_rows)
    report+="\n逐关系名的反射后边数：\n"
    for t in TASKS:
        rels=sorted({r for s in stats[t].values() for r in s["by_relation"]})
        report+="\n"+names[t]+"：\n\n"+table(["关系","G3R","G3R-T","G4R","G4R-P"],
            [[r]+[stats[t][p]["by_relation"].get(r,0) for p in ("G3R","G3R-T","G4R","G4R-P")] for r in rels])
    report+="""
## 两种安慰剂

固定seed=1729。G4R-P只重连三种E1边，在文件及canonical关系内做双边交换，逐节点入度/出度、文件和源目标类型严格保持，避免自环及重复。固定尝试预算为每组边数×10；有界交换不声称均匀抽样。随机边标为topology-only，不沿用错误的原AST证据。

G4R-Aπ同关系内置换完整74维行（允许跨文件），保留多重集。未来反向边须复制对应已置换正向向量，本轮尚不接入EP6。分别记录位置移动与向量数值变化，不能把二者混为一谈。

"""+placebo_table+"""
随机边反射后的canonical边数和逐节点度数均与G4R相同。零次交换的单边/星形等分组全部披露，不声称每条边都改变。全零recursive_method_call属性交换位置后仍为零。完整随机边、映射、分组变化率及NPZ见topology_attempt2。

## 回归和完整性

"""+table(["套件","通过","耗时秒","收据"],tests)
    report+="\n三套合计"+str(total)+"项通过。最终独立验收入口为recon/ep5_verify.py，结果为artifacts/ep5_v1/verification.json：检查冻结源码/历史产物、8H只读load、DFG引用、属性差值、全部匿名行、安慰剂及文档原前缀。\n"
    report+="\n另保留两项开发记录：循环多块测试夹具曾漏前向出口边，修正夹具后通过；只读投影诊断首次直接序列化图特征数组失败，部分JSON保留，后续仅导出相关结构字段到projection_diagnostic_details.json。均未变更冻结输入。\n"
    commands=[]
    for p in sorted((OUT/"execution").glob("*.json")):
        if p.name.endswith(".started.json"):continue
        r=read(p)
        if "command" in r:commands.append([p.stem,r["exit_code"],round(r["seconds"],2)," ".join(r["command"])])
    report+="\n实际命令（CUDA_VISIBLE_DEVICES为空，其余环境沿用§4.1；日志SHA均在execution收据）：\n\n"+table(["运行","exit","秒","命令"],commands)
    report+="""
## 收尾工具故障记录

报告生成脚本首次两次写入均遇到自动审批服务未在期限内返回结果，文件尚未创建；这不是策略明确拒绝。沙箱内直接访问WSL另有E_ACCESSDENIED，正常审批的短WSL命令与临时文件写入/回读/删除已成功。采用分段写入并核对完整源码后继续，未更改审批、沙箱或代理设置；未取得服务端根因证据，不宣称修复了审批服务本身。

## 停止位置

本轮未训练、未用GPU，没有F1或显存收益结论。守卫为既有有界结构事实，改名回退与不可交换分组均是限制。停在EP5，不自动执行EP6或更改训练协议；后续批次授权按对应Prompt处理。

最终实验将在显存充足的服务器另建批次；当前RTX3050 4GiB仅限制本机开发。本轮产物留WSL项目目录，未向C盘另写大型缓存。本地提交，不自动推送GitHub。
"""
    report_path=ROOT/"scripts/edge_sem/EP5_REPORT.md"
    with report_path.open("x",encoding="utf8") as f:f.write(report)
    write(OUT/"summary.json",dict(passed=True,scope="EP5 CPU-only diagnostics",training_executed=False,gpu_executed=False,
        checks=dict(attributes=ref(OUT/"attributes/summary.json"),delta=ref(OUT/"attribute_delta.json"),
        loop=ref(OUT/"loop_context_audit.json"),anonymous=ref(anon_path),topology=ref(topo_path)),
        tests={n:ref(OUT/"execution"/(n+".json")) for n in ("edge_tests","nodesem_tests","dfg_tests")},
        decisions={n:ref(OUT/(n+".json")) for n in ("decisions","loop_context_decision","anonymous_resume1","anonymous_resume2","topology_resume1")},
        test_total=total,report=ref(report_path),stage6_started=False))
    intro="\n\n## 2026-11-11 EdgeSem EP5完成：不变性、可达性与安慰剂（修改AI：Codex）\n\n"
    short=("完成EP5，未训练或用GPU。第20位重入311→61、访问控制322→68；edge_keys及其他73列严格不变。核心46→50，新增全零候选6/14/33/38，上下文26维不变；后续EP6–EP9读取ep5_v1/attributes。\n\n"
        "128个实例均检查通过：54个实际改名、74个原文回退；回退不作为非平凡不变性证据。用户批准状态初始化callable和唯一neg_next/AST锚定end_if适配，冻结模块未改。49条循环头上下文例外保留；统计按历史store双摘要修复后在新目录恢复。所有失败、快照和批准记录保留。\n\n"
        "21例中，重入modifier_reentrancy.sol节点8498及reentrancy_bonus.sol节点12各增加2个两跳证据节点；其余19个不变，访问控制15个均无增量。仅为路径诊断，不证明检测改善。两种安慰剂分别保持逐节点canonical度数和关系内属性多重集，未变化的分组和向量均披露。\n\n"
        "三套CPU回归"+str(total)+"项通过。详见EP5_REPORT.md、训练变更§108及ep5_v1/verification.json。最终实验在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机限制；产物留WSL。停在EP5，本地提交，不自动push。\n")
    progress=intro+short+"\n"+attr_table+"\n"+anon_table+"\n"+reach_table+"\n"+graph_table+"\n"+placebo_table+"\n"+table(["套件","通过","秒","收据"],tests)
    progress+="\n实施选择：循环内同节点自依赖例外；最外层循环头保留第59位；初始化callable按精确AST翻译；歧义end_if仅允许唯一neg_next锚点；历史图采用store的双摘要。各次批准、首次失败及新attempt均见ep5_v1记录，完整解释和命令见报告。\n"
    progress+="\n文件：attrs.py、attr_sources.py、placebo.py；recon/ep5_common、ep5_run、ep5_delta、ep5_loop_context、ep5_anon、ep5_anon_run、ep5_projection_diagnostic、ep5_topology、ep5_verify、ep5_report；test_attrs.py、test_ep5_anon.py、test_ep5_topology.py、test_placebo.py。逐关系统计/逐类型均入度见报告和topology_attempt2/<task>/graph_statistics.json。\n"
    for name,text in [("HANDOVER.md",intro+short),("scripts/edge_sem/PROGRESS.md",progress),
                      ("docs/training_changes_2026-10-07.md","\n\n# 108. 2026-11-11 EdgeSem EP5（修改AI：Codex）\n\n"+report)]:
        p=ROOT/name;old=p.read_bytes();r=before["documents"][name]
        assert len(old)==r["bytes"] and hashlib.sha256(old).hexdigest()==r["sha256"]
        with p.open("ab") as f:f.write(text.encode("utf8"))
    print("EP5 report and three append-only records written",flush=True)
if __name__=="__main__":main()
