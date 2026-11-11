"""Render EP0 evidence and bounded conclusions; no change to the design template."""
import ast
import re
from collections import Counter,defaultdict
from .common import ROOT,OUT,ref,read,write

def references():
    rows=[]
    selected={
      "scripts/DFG/dfg_v2/benchmark_v2/runtime_model.py":["make_placebo","validate_registration"],
      "scripts/DFG/dfg_v2/benchmark_v2/checkpoint.py":["build_binding","validate_binding"],
      "scripts/DFG/dfg_v2/diagnostics8c/placebo.py":["copy_common_layer_parameters"],
      "scripts/DFG/dfg_v2/model.py":["_construct","validate_registration"],
      "scripts/DFG/dfg_v2/benchmark_v2/support.py":["gradient_audit","model_support"],
      "scripts/node_sem/facts_guards.py":["_guard","_modifiers","for_node"],
      "scripts/node_sem/facts_ast.py":["resolve_callable"],
      "scripts/DFG/projection.py":["__init__"],
    }
    for name,functions in selected.items():
        tree=ast.parse((ROOT/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef)and node.name in functions:
                # ast.end_lineno is absent in the mandated Python 3.7 runtime.
                ends=[getattr(n,"lineno",node.lineno)for n in ast.walk(node)]
                rows.append(dict(file=ref(ROOT/name),function=node.name,start=node.lineno,end=max(ends)))
    return rows

def source_table():
    """One row for each of the 73 proposed slots, not a feature encoder."""
    mapping=[
      (0,1,"semantic CFG dominance/postdominance","conditional","Only supported functions and mapped endpoints; preserve unknown CFG."),
      (2,2,"branch AST scope + external.kinds","conditional","Needs branch-specific scan; not a saved scalar."),
      (3,6,"dfg.defs/uses.kind + L2/L3 edge provenance","needs_design_decision","Observed kinds include return; no state/environment in L1 kind. A return-kind policy is missing."),
      (7,14,"exact declaration type / facts_schema.SHAPES","needs_source_join","dfg variable objects have no type/shape; declaration identity join is required."),
      (15,15,"L1 strong/weak metadata","unavailable_zero_as_specified","No such field in sealed L1 evidence; must stay zero, not guess."),
      (16,19,"definition AST + syntax","needs_source_join","syntax bag has assign/add_assign/sub_assign/compound_assign/delete but no declaration/parameter/incdec distinction."),
      (20,20,"CFG backedge path for exact def/use","conditional","Reachability alone does not distinguish a loop-carried reaching definition."),
      (21,21,"CFG path and external-call nodes","conditional","Must join exact endpoints. State declaration READS_STATE source is not an intra-function definition."),
      (22,26,"dfg.to[].sink for exact dependency","needs_source_join","Sink values exist; L2/L3 do not automatically have matching L1 to rows."),
      (27,29,"arith.ops","available","Group +,- / *,/,% / **; identify relevant use."),
      (30,33,"state.writes[].shape + AST access path","needs_design_decision","shape is declaration category (integer/address/mapping/struct_contract...), not scalar vs struct_member access."),
      (34,36,"syntax plus write AST","conditional","Simple/add/sub assignment exist; increment/decrement require explicit AST treatment."),
      (37,39,"external.kinds/value_attached","available","Endpoint facts; endpoint test decides eligibility."),
      (40,40,"external.return_handling","available","unknown is explicit; checked categories require no inference."),
      (41,42,"resolved callee fn_summary and unknown_fields","conditional","Use per-field unknown, not solely group status."),
      (43,48,"in-memory GuardAnalyzer kind and anchor","needs_design_decision","Modifier anchors are invocation nodes, not modifier-body condition nodes."),
      (49,54,"guards.operand_classes","conditional","loop_cond deliberately has empty operands in frozen analyzer; unknown must remain distinct."),
      (55,56,"external.kinds","available","Endpoint context only."),
      (57,58,"order.reachable_from_ext_call","conditional","Check order.status."),
      (59,59,"loop.bound","available","unknown loop bound still means syntactically inside a loop."),
      (60,60,"syntax exit/return","available","Context only."),
      (61,61,"arith.in_unchecked + pragma interval","conditional","Missing/unsupported pragma cannot be treated as pre-0.8."),
      (62,62,"function_ctx.visibility","available","Endpoint context only."),
      (63,63,"order.ext_call_in_loop","conditional","Honor order uncertainty."),
      (64,67,"env_source.code","conditional","Existing 14-key vocabulary; four proposed groups are not exhaustive."),
      (68,68,"semantic CFG support and projection","available","Computed support metadata."),
      (69,69,"dfg.status","available","Nonapplicable empty group is not unknown."),
      (70,70,"order.status","available","Nonapplicable empty group is not unknown."),
      (71,71,"state.status + field-level support","available","Nonapplicable empty group is not unknown."),
      (72,72,"guard_status","available","Unknown is separate from known absence.")
    ]
    result=[]
    for lo,hi,path,status,note in mapping:
        for i in range(lo,hi+1):result.append(dict(index=i,source=path,status=status,note=note))
    assert [r["index"]for r in result]==list(range(73))
    return result

def aggregate(task):
    g=defaultdict(Counter);mods=Counter();audit=Counter();guards_dist=Counter()
    fns=[]
    for row in task["files"]:
        mods.update(row["modifiers"]);audit.update(row["guard_analyzer_audit"])
        guards_dist.update(row["guards_per_statement"])
        fns.extend(row["cfg_functions"])
        for kind,counts in row["guards"].items():g[kind].update(counts)
    return dict(modifiers=dict(mods),modifier_audit=dict(audit),
        guards={k:dict(v)for k,v in g.items()},guards_per_statement=dict(guards_dist),
        cfg_total=len(fns),cfg_supported=sum(f["status"]=="supported"for f in fns),
        postdom_full=sum(f.get("postdominance_full",False)for f in fns),
        semantic_backedges=sum(f.get("semantic_backedges",0)for f in fns),
        unmapped_event_anchors=sum(f.get("unmapped_event_anchors",0)for f in fns),
        unmapped_ast_statements=sum(f["unmapped_ast_statements"]for f in task["files"]),
        anonymous_code_view_pass=sum(f["anonymous_projection"]["code_view_same_ast_to_hcg"]for f in task["files"]),
        anonymous_direct_pass=sum(f["anonymous_projection"]["direct_original_graph"]["passed"]for f in task["files"]),
        pragma_pre08=sum(f["pragma_interval"].get("pre_08")is True for f in task["files"]),
        pragma_unknown=sum(f["pragma_interval"].get("pre_08")is None for f in task["files"]))

def main():
    inv=read(OUT/"inputs.json");attrs=read(OUT/"attribute_sources.json");calls=read(OUT/"call_classification.json")
    tasks={tid:read(OUT/(tid+".json"))for tid in inv["tasks"]}
    ag={tid:aggregate(t)for tid,t in tasks.items()}
    cpu={n:read(OUT/("cpu_"+n+".json"))for n in "ABC"}
    changes=[
      dict(id="D-01",impact="EP3 blocker",finding="Modifier _anchor is modifier_invocation, not the guard statement in its body; all modifier records unmapped.",
           proposal="Later add an EdgeSem-local read-only provenance resolver using frozen binding/guard logic; do not edit NodeSem. Requires approval before implementation."),
      dict(id="D-02",impact="EP1/checkpoint integration blocker",finding="Existing checkpoint.validate_binding imports frozen runtime registration; neither G3R nor G3R-T can pass typed deep validation.",
           proposal="An EdgeSem-local binding adapter must dispatch to its own registration. A profile string alone is insufficient. No bypass implemented."),
      dict(id="D-03",impact="EP4 source/schema blocker",finding="L1 kind includes return; variable facts lack declaration type; state.writes.shape describes root declaration type rather than scalar/member access.",
           proposal="Decide return-kind mapping and exact declaration/access joins before attribute implementation; do not silently coerce or broaden schemas."),
      dict(id="D-04",impact="EP4 applicability clarification",finding="READS_STATE starts at a state declaration; intra-function def-to-use path is not directly defined for that source.",
           proposal="Specify applicability/unknown handling for cross-call attribute on READS_STATE; do not invent a reaching definition."),
      dict(id="D-05",impact="EP5 integration prerequisite",finding="Renamed source cannot be checked against unchanged original code text by Projector.",
           proposal="Reuse existing temporary node_code_view for parity only; all 384 task/file identities pass; formal graph stays original."),
      dict(id="D-06",impact="documentation",finding="Section 1.4 gives contract LR values; node tasks use initial_lr=.0002/max_lr=.005/div_factor=25.",
           proposal="Bind future execution to task-specific sealed configuration; r3 introduction already acknowledges node max_lr."),
    ]
    result=dict(version="edgesem-ep0-recon-v1",scope="read-only evidence and bounded CPU probes",
        status="EP0 complete; design discrepancies prevent automatic EP1 continuation",
        inputs=ref(OUT/"inputs.json"),task_summaries=ag,attribute_slots=source_table(),
        interfaces=references(),discrepancies=changes,cpu=cpu,
        parameters=dict(cf_back={tid:dict(enable=t["cf_back_enable_threshold50"],mapped_next_line=t["cf_back_existing_next_line"])for tid,t in tasks.items()},
            bit15_available=False,typed_sparse_sharing=False),
        artifact_refs=[ref(p)for p in sorted(OUT.glob("*.json"))],
        no_formal_training=True,no_gpu=True,no_new_semantic_graph=True,
        final_server_intent="Final experiments will use a sufficiently provisioned server in a separate batch; RTX3050 4GiB is only the local development constraint.")
    write(ROOT/"scripts/edge_sem/recon.json",result)
    lines=["# EdgeSem EP0 侦察报告（Codex）","",
      "日期：2026-11-10。依据 PROMPTS r3，共享上下文 §4.1 与 EP0 §4.2；实际 HEAD "+inv["head"]+"。",
      "本轮完成输入核验、四任务语义/边统计和三项 CPU 探针。正式训练 0、optimizer step 0、GPU 运行 0；不生成 F4、边特征或生产模型。EP0 完成不等于后续方案已全部验收。",
      "所有机器证据在 recon.json 与 artifacts/ep0_v1/；路径均从已核验的历史 manifest/plan 取得。侦察探针未加载历史 pt 权重；回归测试保留既有合成序列化用例。","",
      "## 1. 输入身份与历史配置","",
      "8H plan SHA："+inv["plan"]["sha256"]+"；plan.seal SHA："+inv["seal"]["sha256"]+"。",
      "图 store SHA："+inv["store"]["sha256"]+"；store.seal SHA："+inv["store_seal"]["sha256"]+"。",
      "inputs.json 逐项保存四任务 F0/F3、源码、L1–L3 证据、匿名特征 manifest/NPZ、分组折、label_view、零步准备 manifest 与历史 G3R 收据；全部实际使用文件先做 SHA 校验。匿名输入仅用于核验历史 8H 接入，不替用户批准新的主视图。",
      "历史节点配置：initial_lr=0.0002、max_lr=0.005、div_factor=25；合约：0.0005、0.01、20。其余逐项见 inputs.json：50/50 schedule/max epoch、patience7、delta0.001、hidden128、2层、8头、shared_projection、mean。按各任务实际配置核验，不把段落简写作为配置来源。","",
      "| 任务 | 实际完成轮数（各折，1基计数） | best轮（1基） |","|---|---|---|"]
    for tid,t in inv["tasks"].items():
        lines.append("|"+tid+"|"+str([r["epochs_completed"]for r in t["run_epochs"]])+"|"+str([r["best_epoch_one_based"]for r in t["run_epochs"]])+"|")
    lines+=["","best/last 原字段为0基索引。读取收据、final_result/history/effective_config并核对哈希与轮数，未读取预测来选型。P2新增轮数可以由50减已完成轮数估算，但这不是实际服务器耗时预测。","",
      "## 2. 边类型、方向和参数量","",
      "| 任务 | 存储canonical | G3R merge | typed | 每层新增参数 | <20边的typed关系 |",
      "|---|---:|---:|---:|---:|---:|"]
    for tid,t in tasks.items():
        c=t["graph_counts"];lines.append("|{}|{}|{}|{}|{}|{}|".format(tid,len(c["raw"]),len(c["merge"]),len(c["typed"]),c["added_parameters_per_layer"],len(c["typed_sparse_lt20"])))
    lines+=["","各任务 JSON 逐项列出反射前、基础反射后、G3R 和 typed 的canonical及边数；同类型合并、反向键撞已有正向键另列。typed 只在探针内存生成，不修改存储图。参数差为 ΔR×(2×8×16²+8)，两层骨干差为该数的2倍；稀疏关系不共享、不删除。","",
      "## 3. CFG、回边与投影","",
      "| 任务 | 有函数体总数 | CFG/支配支持 | 有限退出路径后支配全覆盖 | 语义回边 | 对应next_line | cf_back |",
      "|---|---:|---:|---:|---:|---:|---|"]
    for tid,t in tasks.items():
        a=ag[tid];lines.append("|{}|{}|{}|{}|{}|{}|不启用|".format(tid,a["cfg_total"],a["cfg_supported"],a["postdom_full"],a["semantic_backedges"],t["cf_back_existing_next_line"]))
    lines+=["","复用 FileCFG 的 legacy CFGBuilder→V2CFGBuilder 路径及版本元数据；原因是它与已封存 L1 及 NodeSem 使用同一事件锚点。保留全部 CFG 块，从入口求支配；仅由目标支配源识别自然回边。投影只跨越无事件块寻找最近事件，再按精确AST锚点对应 HCG，最终只统计原图已存在的 next_line。没有用源码行号判断回边。",
      "后支配以可达的真实出口连接分析用虚拟出口计算；只覆盖可达出口的有限退出路径，不宣称证明所有执行都会终止。不可支持函数、缺失事件锚点、未投影AST语句逐文件记录。所有任务可修改的next_line回边均少于50，按既定规则禁用cf_back。",
      "匿名源码未另行写入文件，复用8G封存替换记录在内存重建。直接配原code文本的图会被Projector拒绝；复用既有node_code_view只调整临时副本code后，384/384任务文件的AST ID→原图节点映射完全一致。此处不是新增匿名实验或完整边语义不变性验收。","",
      "## 4. 新关系可行性（只计数）","",
      "| 任务 | MOD_APPLY候选/绑定/图端点 | CALL_SITE唯一绑定/图端点 | GUARDS记录/可映射/去重边 |",
      "|---|---|---|---|"]
    for tid,t in tasks.items():
        a=ag[tid];m=a["modifiers"];c=calls[tid]["total"];gr=a["guards"]
        lines.append("|{}|{}/{}/{}|{}/{}|{}/{}/{}|".format(tid,m.get("invocations",0),m.get("unique_definition",0),m.get("both_endpoints",0),c["resolved_internal"],c["projected_internal"],sum(x["records"]for x in gr.values()),sum(x.get("mapped",0)for x in gr.values()),t["prospective_relations"]["GUARDS"]["unique_forward"]))
    lines+=["","每类含REV的预计边数是去重正向边数×2；按canonical明细见各任务 prospective_relations。MOD_APPLY的绑定计数与GuardAnalyzer.audit分别记录：前者仅定义身份绑定，后者还检查占位符/参数/守卫，不能混成一个成功标准。",
      "CALL_SITE全量表达式先区分内置函数、事件、类型转换、库、成员调用，再报告内部函数解析；最初粗扫的unknown含require等内置调用，最终分母以call_classification.json为准。两个节点任务分别有13个重载、3个super调用未解析；不能把180/182、186/188的条件投影率称为完整内部调用召回率。",
      "GUARDS按kind和每语句数量完整分布见JSON。重入节点modifier 616条、访问控制715条，当前均0映射；实际_anchor是modifier_invocation。普通守卫的可映射记录不能弥补modifier源端缺失。预计GUARDS规模只包含当前可映射集合，不代表设计中的modifier连边已完成。","",
      "## 5. 73位属性来源","",
      "recon.json.attribute_slots逐位列出来源、状态和限制；attribute_sources.json给出四任务事实字段、实际枚举和L1证据键。",
      "- L1没有strong/weak更新标记，第15位按模板保持0；这不等于证明每条边都是strong update。",
      "- dfg变量kind实际含local、parameter、return；模板的四类未规定return。对象仅有var/kind/from_offset，没有类型字段。",
      "- state.writes.shape是integer/address/mapping/array/struct_contract等声明类型，不能直接当成scalar/mapping/array/struct_member访问方式。syntax也没有直接表达所有decl/param/incdec区别。",
      "- READS_STATE源端是状态声明，不能直接当作函数内def去检查跨调用路径；适用性需要明确。",
      "- env_source值及每文件数量已逐项记录；pragma按冻结interval解析，缺失或不支持记unknown，不猜编译器版本。",
      "- 图DOT label中的AST身份仅供Projector精确对齐，不使用漏洞标签决定关系；CPU B监督损失单独读取冻结L-audit标签。","",
      "## 6. CPU接入探针","",
      "A：重入节点fold0，新鲜G3R锚模型；原样重建DGL图/层并复制全部参数，state digest一致、eval前向逐位一致，最大绝对差0。",
      "B：typed模型220个canonical、参数"+str(cpu["B"]["parameter_count"])+"，冻结inner_train "+str(cpu["B"]["inner_train_nodes"])+"个节点仅做一次交叉熵backward；optimizer step=0。所有复制关系行逐位相同，有限前后向和冻结gradient_audit通过。无训练支持关系保留并按0梯度处理。",
      "B的浅层schema/梯度检查通过不意味着checkpoint通过：dfg_profile=G3R时深验报Graph/schema mismatch；G3R-T时报Unknown DFG v2 profile。旧checkpoint.validate_binding先比较task/profile/reducer/layer_impl，再调用冻结runtime_model.validate_registration并核对canonical、辅助节点、initial SHA、配置和graph/folds/labels/label_view/feature_view/feature_npz文件引用。必须提供独立的EdgeSem绑定适配，不能改旧白名单或伪装G0P。",
      "C：同文件随机端点仅模拟当前可映射G4R规模：{}个canonical、{}条有向边、{}参数。CPU train-mode前向（保留autograd）{:.3f}秒；前向前RSS {:.2f}MiB，采样峰值 {:.2f}MiB，增量 {:.2f}MiB，进程高水位 {:.2f}MiB。".format(cpu["C"]["relations"],cpu["C"]["edges"],cpu["C"]["parameter_count"],cpu["C"]["seconds"],cpu["C"]["rss_before_forward_bytes"]/2**20,cpu["C"]["peak_sampled_rss_bytes"]/2**20,cpu["C"]["incremental_forward_rss_bytes"]/2**20,cpu["C"]["process_high_water_rss_bytes"]/2**20),
      "C不包含尚无法映射的modifier守卫、未来边属性激活、backward或Adam状态；随机新关系使用普通构造器初值，只作内存估计，不作为r3初始化验收或预测成绩。CPU RSS不能换算成GPU显存；正式GPU探针仍在EP7。",
      "接入函数逐行范围和文件SHA见recon.json.interfaces；未用monkeypatch修改任何冻结入口。","",
      "## 7. 需要后续决策的差异",""]
    for d in changes:lines.append("- **"+d["id"]+" "+d["impact"]+"**："+d["finding"]+" "+d["proposal"])
    lines+=["","本轮保留这些差异，不自行修正PROMPTS或冻结分析器，不进入EP1。D1主视图、D2训练协议、D3七类冻结规则也仍待用户确认；EP0结果不能充当训练授权。","",
      "## 8. 执行、回归与边界","",
      "命令均在mando、CUDA_VISIBLE_DEVICES=''、PYTHONDONTWRITEBYTECODE=1、OMP/MKL=2下运行。每个execution/*.started.json记录实际命令，*.json记录退出码/耗时/log SHA。",
      "顺序：python -B -m scripts.edge_sem.recon.inventory；semantic --task <四任务>；attributes；calls；model_probe --probe A/B/C；随后pytest三套目录与doc_check。输出排他创建，不覆盖成功产物。",
      "开发接入错误均保留：首次STATEMENTS导入位置、run包装器的--分隔符、辅助节点空dfg组、mando缺少psutil（改用Linux/proc，无依赖安装）、split含元数据不能当三路列表。只修正新侦察脚本，无生产训练失败/自动重试；成功探针不重复执行。",
      "验证结果与冻结源码/文档前缀验收见artifacts/ep0_v1/verification.json；脚本与报告在本地提交，不自动推送。",
      "最终实验将在显存充足服务器上另建批次；RTX3050 4GiB仅是本机开发限制。服务器尚未在本轮部署/验收，不混合本机与服务器结果。"]
    p=ROOT/"scripts/edge_sem/RECON.md"
    with p.open("x",encoding="utf8")as f:f.write("\n".join(lines)+"\n")
    print("EP0 report rendered",flush=True)

if __name__=="__main__":main()
