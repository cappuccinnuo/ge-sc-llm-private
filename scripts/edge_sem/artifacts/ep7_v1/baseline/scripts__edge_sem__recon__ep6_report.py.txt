"""EP6 report from accepted receipts; append existing records only."""
from .common import ROOT, read, ref, write
from .ep6_common import OUT
from scripts.edge_sem.attrs import EDGE_FEATURE_NAMES

def main():
    before=read(OUT/"before.json");delta=read(OUT/"attribute_delta.json")
    cpu=read(OUT/"real_cpu.json");cov=read(OUT/"anonymous_gate/coverage.json");f4=read(OUT/"f4_delta.json")
    for name in ("nodesem_tests","dfg_tests","archive_recheck"):
        if not read(OUT/"execution"/name/"result.json")["passed"]:raise ValueError("Missing accepted tests")
    report=["# EP6：边感知 HGT 与 r14 前置修正验收","",
        "基于 "+before["head"]+"，按 PROMPTS.md r14 完成。本轮只有 CPU 构造、前向/反向验收，optimizer_steps=0；没有正式训练、GPU 检查或新评分。","",
        "## 授权与历史边界","",
        "用户批准 call_1c4fc0064fb94266be56b656e6399928：用冻结 sem.sink(目标 AST, 精确封存符号) 补齐参数入口缺失的 dfg.to；已有记录必须一致。授权见 artifacts/ep6_v1/decisions.json。原图、冻结 NodeSem/DFG/作者模型与旧产物均保留。",
        "新边写入 artifacts/f4_v2，属性写入 artifacts/ep6_v1/attributes。manifest 的 v1 表示存储格式，批次由路径、源码 SHA 和输入引用区分。生产加载器仍要求当前源码 SHA；旧 EP2 回归通过显式归档路径读取准确的旧源码快照，旧 seal 未修改。","",
        "## F4 重建与属性差值","",
        "|任务|旧 E1 行|新 E1 行|新增 fallback MOD_APPLY|","|---|---:|---:|---:|"]
    for task,r in f4["tasks"].items():
        report.append("|{}|{}|{}|{}|".format(task,r["old_rows"],r["new_rows"],len(r["extra_rows"])))
    for row in f4["tasks"]["access_control_contract"]["extra_rows"]:
        report.extend(["","新增身份："+row["file"]+"，源码 SHA "+row["source_sha256"]+
                       "，源锚点 "+str(row["src_anchor"])+"，证据 "+str(row["evidence"])+"。"])
    report.extend(["","模板预期访问控制合约新增1条fallback MOD_APPLY，实际新增0条：0x0d689d1d3ef39e379329d9fc88eabceccc1215a0.sol（源码SHA ac6e70721c9d4ff51c6c6653195b62892672321253cf38883bd5d4d771bb82de）的fallback锚点3383–3446、调用3409–3418已唯一绑定目标modifier 2048–2112，但冻结投影为not_in_graph。按第0.1节跳过，不放宽投影。其余三任务没有fallback修饰器候选。四任务新旧边文件SHA分别完全相同；见documentation_revision1/fallback_projection.json。"])
    report.extend(["","节点任务 edge_keys 完全相同；仅旧 no_exact_dfg_to_for_this_edge 的 DATA_DEF_USE 上，第22–29/37–40位发生0→1，其余列逐位相同。","",
        "|位|含义|重入：旧→新（参数入口新增）|访问控制：旧→新（参数入口新增）|","|---:|---|---:|---:|"])
    for bit in list(range(22,30))+list(range(37,41)):
        cells=[]
        for task in ("reentrancy_node","access_control_node"):
            x=delta["tasks"][task]["bits"][str(bit)]
            cells.append("{}→{}（{}）".format(x["old"],x["new"],x["parameter_entry_added"]))
        report.append("|{}|{}|{}|{}|".format(bit,EDGE_FEATURE_NAMES[bit],*cells))
    for task,r in delta["tasks"].items():
        report.extend(["","{}：变化{}条边 / {}位；已有sink集合比较{}条边，全一致；DATA_DEF_USE仍有{}条边无第22–26位映射，保留冻结分类与unknown规则。".format(task,
            r["delta"]["changed_edges"],r["delta"]["changed_bits"],r["sink_consistency_compared"],r["data_without_mapped_sink"])])
    report.extend(["","新端点检验已重算，core_indices仍50位、context_indices仍26位；合并去重为73位（第15位停用），相对EP5均无变化。完整端点统计见 attributes/selection.json。","",
        "第61位每任务8个文件无法由绑定pragma/metadata判定 <0.8 或 ≥0.8。pragma分布均为 >=0.5.9：1、>=0.5.1：2、>=0.5.11：5，当前source metadata未绑定精确分析版本。按任务、文件、源码SHA对齐封存6c报告，这16个文件实例都有历史pragma_derived编译选择记录；历史验证所选编译器不能反推分析/部署版本，本轮不注入属性。详见 compiler_history.json。","",
        "## 名字不变性与覆盖","",
        "128文件全部通过：54个实际改名，74个原文回退对照。匿名侧用翻译后的封存符号计算sink。原图及原证据未改。","",
        "|任务|实际改名文件|改名文件边 / 全部边|library CALL_SITE覆盖|","|---|---:|---:|---:|"])
    for task,r in cov["tasks"].items():
        lib=r["by_relation"]["CALL_SITE:library"]
        report.append("|{}|{} / {}|{} / {}（{:.2%}）|{} / {}|".format(task,r["renamed_files"],r["files"],
            r["covered_edges"],r["all_edges"],r["covered_edges"]/r["all_edges"],lib["renamed"],lib["total"]))
    report.extend(["","coverage.json列出全部关系、CALL_SITE实际kind、GUARDS各kind及回退原因；GUARDS多kind计数可重叠。回退不算真实改名证据，不能宣称全语料已验证。新增库调用合成用例覆盖库名、方法、结构类型、接收者、重载、同名成员及不同名字长度，按AST遍历身份比较；它不能替代真实覆盖。","",
        "## E3实现及CPU验收","",
        "- hgt_edge.py导入时核验两个冻结源码SHA；父构造器先执行，再建立零初始化u和五族U。",
        "- 单模型EdgeAttrEncoder：uint8→float，Linear(选中位数,32)→GELU→Linear(32,16)→dropout(0.1)。每次前向每个规范关系编码一次，各HGT层复用psi。",
        "- 仅增加softmax前的关系注意力偏置和按关系族共享的消息增量；共享投影、mean聚合、残差、HGT dropout与LayerNorm保留父层行为。psi=None直接调用父层。",
        "- G4R-A、G4R-Api、G4R-AC、G3R-TA接通；Api按constructor seed调用placebo.py置换完整属性行；AC合并索引去重。其他结构剖面保留原路径。",
        "- 原图多重边key精确对齐实际EID，REV_复制正向uint8[74]。注册核验manifest、索引、逐边NPZ、层类型及置换来源；无事实重算或评分时建参。",
        "- EP1新鲜结构装配先复制共享参数，自有子类接管该私有模型状态，没有monkeypatch冻结模块。新层再次严格复制共享参数；编码器在隔离的constructor seed RNG中默认初始化。","",
        "真实reentrancy_node fold0：hidden128、heads8、layers2、512维inside_token，使用冻结原始F3作结构验收。实际设备CPU；收据config中的cuda:0是引用的历史训练字段，不代表执行设备。EP7训练特征视图、监督与P2协议仍须独立绑定。","",
        "|测量|结果|","|---|---:|",
        "|G4R参数|{}|".format(cpu["structural_parameters"]),
        "|G4R-A参数|{}|".format(cpu["parameters"]),
        "|新增参数|{}|".format(cpu["added_parameters"]),
        "|构造秒|{:.3f}|".format(cpu["construction_seconds"]),
        "|CPU前向秒|{:.3f}|".format(cpu["forward_seconds"]),
        "|CPU反向秒|{:.3f}|".format(cpu["backward_seconds"]),
        "|零初值最大绝对差|{}|".format(cpu["zero_initial_max_abs"]),
        "|编码次数 / 规范关系|{} / {}|".format(cpu["encoder_calls"],cpu["canonical_relations"]), "",
        "前后向有限，共享参数逐位相同，原图指纹不变，CUDA未初始化。进程RSS峰值{:.1f}MiB是整套测试进程历史峰值，不是模型独占内存或GPU显存。小图验证psi=None在eval/train固定RNG下逐位相同；零u/U的eval误差≤1e-6；非零u/U时输出改变且梯度到达u/U/编码器。u/U全零时编码器初始梯度为0符合链式法则，不是断图。模型级等价为eval检查，新增dropout后不能声称任意训练随机轨迹也相同。".format(cpu["peak_process_rss_mib"]),
        "",
        "## 回归与运行记录","",
        "最终4,300项独立测试通过：EdgeSem294、NodeSem1,353、DFG v2 2,653。EdgeSem首次全量288通过、4个旧EP2归档用例因更新后的测试源码SHA被拒绝；保留失败日志。扩展显式归档校验后，仅复核原4项及2个新拒绝用例，6项通过；其余成功检查和真实CPU收据复用，没有重建属性。",
        "开发阶段修正了helper导入作用域、合成fallback图缺节点及库参数类型限定名。两套冻结回归曾合并收集，因同名test_model.py冲突而未执行；保留日志后按文档分别运行。摘要见 development_notes.json，实际命令/退出码/日志SHA见 execution/<步骤>/started.json和result.json。","",
        "## 结论与停止位置","",
        "EP6前置修正与边感知层CPU接入完成。尚无E3训练分数、检测提升或GPU资源结论；不启动EP7、新seed或其余漏洞类别。",
        "最终实验将在显存充足的服务器运行；RTX3050 4GiB限制仅来自当前本机开发。服务器仍须做目标设备的资源与数值验收。",
        "证据入口：artifacts/ep6_v1/summary.json、verification.json、real_cpu.json、attribute_delta.json、anonymous_gate/coverage.json。"])
    dest=ROOT/"scripts/edge_sem/EP6_REPORT.md"
    with dest.open("x",encoding="utf8") as f:f.write("\n".join(report)+"\n")
    brief="""\n\n## EP6完成：r14前置修正与边感知HGT（2026-11-11）\n\n已完成四任务f4_v2、两节点任务新属性和名字不变性核验，接通G4R-A / G4R-Api / G4R-AC / G3R-TA。用户批准call_1c4fc0064fb94266be56b656e6399928，按封存符号调用冻结sink补齐参数入口，已有记录严格比对。原图、旧产物与冻结实现保留。报告：scripts/edge_sem/EP6_REPORT.md。\n\n四任务F4边集合均不变；访问控制合约的1个fallback修饰器绑定成功，但冻结投影为not_in_graph，因此未加边。补齐重入1,727条、访问控制2,941条边；仅指定列0→1，其余逐位相同。实际改名54文件通过，74回退只作原文对照；core/context仍50/26位。\n\n真实重入fold0 CPU：新增92,784参数、零初值最大差0、前向1.43秒、反向2.28秒，共享参数逐位一致，optimizer_steps=0，未用GPU。最终4,300项测试通过（EdgeSem294、NodeSem1353、DFG2653）；归档SHA失败保留，修复只读快照核验后定向复核。没有正式训练或检测收益结论。\n\n最终实验将在显存充足的服务器运行；当前限制仅来自本机。EP7须独立计划与授权，本轮本地提交，不自动推送。\n"""
    for name in before["documents"]:
        with (ROOT/name).open("a",encoding="utf8") as f:f.write(brief)
    detail="""\nEP6详细选择：冻结sem.sink(target,sealed_symbol)补齐缺失记录，不用名字启发式；源已有to精确比较集合。未知与非DATA_DEF_USE规则保留。f4_v2/ep6_v1为新目录，旧seal不改。第61位各8个未知文件有历史pragma_derived编译选择记录，但未绑定分析版本，本轮不改该位。\n\n单模型32→16边MLP使用输出dropout0.1，每关系每次前向一次，各层共享。u按规范关系，U按control/call/data/guard/structure五族，全部零初始化；共有参数来自EP1结构装配。Api按同折constructor种子置换完整74位，AC索引去重。零初值等价是eval检查，不宣称任意训练dropout轨迹一致。\n\n接入记录：EP3模型回归按r14改读f4_v2；EP2归档核对修改前的测试/模型源码快照，生产load_edges仍严格拒绝旧实现。首次开发错误、合并收集错误与4项归档失败保留；复用成功产物。新增反例拒绝错误SHA和未登记快照。不改冻结训练，不重训。最终ep6_verify核对源码、旧产物、8H入口、文档前缀及新结果。\n"""
    with (ROOT/"docs/training_changes_2026-10-07.md").open("a",encoding="utf8") as f:f.write(detail)
    write(OUT/"development_notes.json",dict(initial_unit_development=dict(passed=30,failed=10,errors=17,
        causes=["helper local import scope","synthetic CFG omitted fallback","qualified library parameter type fixture"],
        fixed_without_analyzer_changes=True),
        collection_error="Combined suites have duplicate test_model.py; prescribed separate commands used",
        historical_archive="4 failures retained; exact snapshots verified; affected cases rechecked",
        no_production_retry=True))
    commands=["# EP6产物与执行记录","","新文件采用排他写入；以下是执行记录，不应在已有目录重复生成。",
        "环境：mando；CUDA_VISIBLE_DEVICES为空；PYTHONDONTWRITEBYTECODE=1；OMP_NUM_THREADS=2；MKL_NUM_THREADS=2；TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。",
        "真实CPU收据由EDGESEM_EP6_PROBE指向本目录real_cpu.json，其他测试复用收据。","","    python -B -m scripts.edge_sem.recon.ep6_common"]
    for p in sorted((OUT/"execution").glob("*/started.json")):
        commands.append("    "+" ".join(read(p)["command"]))
    commands.extend(["    python -B -m scripts.edge_sem.recon.ep6_report","    python -B -m scripts.edge_sem.recon.ep6_verify","",
        "包含保留的失败记录。最终实验转服务器，本机限制不代表最终显存预算。"])
    with (OUT/"README.md").open("x",encoding="utf8") as f:f.write("\n".join(commands)+"\n")
    write(OUT/"summary.json",dict(passed=True,report=ref(dest),before=ref(OUT/"before.json"),
        decisions=ref(OUT/"decisions.json"),cpu=ref(OUT/"real_cpu.json"),
        checks={k:ref(OUT/p) for k,p in (("prerequisites","prerequisites.json"),("compiler_history","compiler_history.json"),
            ("nodesem","execution/nodesem_tests/result.json"),("dfg","execution/dfg_tests/result.json"),
            ("edge_initial","execution/edge_tests/result.json"),("edge_archive_recheck","execution/archive_recheck/result.json"))},
        final_tests=dict(edge=294,nodesem=1353,dfg=2653,total=4300),actual_device="cpu",
        training_executed=False,gpu_executed=False,optimizer_steps=0,
        final_experiments="Server with sufficient VRAM; local 4GiB is temporary"))
    print("EP6 report and three append-only records written",flush=True)

if __name__=="__main__":main()
