"""Render accepted Stage I results and append existing project records."""
from pathlib import Path
import csv, json, hashlib

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
parts = json.loads((BASE / "report_sections.json").read_text())
verification = json.loads((BASE / "replay_verification.json").read_text())
stats = list(csv.DictReader((BASE / "intervention_statistics.csv").open()))
pooled = list(csv.DictReader((BASE / "intervention_pooled.csv").open()))
lookup = {(x["task_id"],x["variant"],x["checkpoint"],x["condition"]): x for x in stats}
pool = {(x["task_id"],x["variant"],x["checkpoint"],x["condition"]): x for x in pooled}
tasks = [
 ("reentrancy_author_contract","重入合约"),
 ("access_control_author_contract","访问控制合约"),
 ("reentrancy_author_node","重入节点"),
 ("access_control_author_node","访问控制节点")]
def table(ck):
 out=["| 任务 | 变体 | N BF1 | 屏蔽后BF1 | 等权ΔBF1/ΔMF1(pp) | 类别翻转 | 纠正/新增错误 | 概率变化数 |",
      "|---|---|---:|---:|---:|---:|---:|---:|"]
 for task,name in tasks:
  for variant in ("E3a","E3b"):
   n=lookup[(task,variant,ck,"N")];z=lookup[(task,variant,ck,"Z_ALL")];p=pool[(task,variant,ck,"Z_ALL")]
   out.append("| %s | %s | %.4f | %.4f | %+.6f / %+.6f | %s | %s / %s | %s |" %
      (name,variant,float(n["buggy_f1_mean"]),float(z["buggy_f1_mean"]),
       float(z["delta_buggy_f1_pp_mean"]),float(z["delta_macro_f1_pp_mean"]),
       p["prediction_flips"],p["corrected"],p["introduced"],p["probability_changed_count"]))
 return "\n".join(out)+"\n"

resources = ("\n本轮60项推理/校验记录耗时合计%.3f秒（约%.2f分钟）；最高allocated %.3f MiB、reserved %.1f MiB，整卡最低采样空闲%d MiB，采样错误0。这含加载、哈希、重复前向和范数同步，不是训练耗时，也不是连续监控显存的绝对最小值。\n" %
 (verification["replay_wall_seconds_sum"],verification["replay_wall_seconds_sum"]/60,
  verification["peak_allocated_mib"],verification["peak_reserved_mib"],verification["minimum_sampled_whole_card_free_mib"]))
resources += "\n完成后H1只读归档复核52新+8复用=60、H2复核26新+4复用=30，均通过。当前计划/源码/输入/静态证据摘要及60份回放收据均通过。最终文档前缀及用户改动保护清单见protected_after.json。\n"

report = parts["intro"]+"\n"+table("best")+parts["between"]+"\n"+table("last")+parts["afterlast"]+resources+parts["end"]
path=BASE/"STAGE_I_RESULT_REPORT.md"
assert not path.exists()
path.write_text(report,encoding="utf-8")

detail = """
**23.5 全折诊断完成与独立复算**

实际完成60模型、120份best/last checkpoint、720个条件评分，训练步数0。全部正常概率与历史逐位一致（最大误差0），native包装/恢复、权重及参数对象、原图/标签/特征/schema均通过。新增推理不写旧图或checkpoint。消息审计41,660项canonical-layer观察，其中1,020项状态消息正常均非零，Z_ALL均被正确置零，cross-mean分母保持。完整汇总在stage_i_v3/STAGE_I_RESULT_REPORT.md。

下表为best的Z_ALL−N固定权重诊断，负值代表屏蔽损害当前模型，不能当作新增训练成绩：
""" + "\n" + table("best") + """
**23.6 机制证据与后续边界**

两个合约任务及访问控制节点在全部条件、best/last中均无类别变化。重入E3b best屏蔽全部状态消息仅新增1漏报（buggy_42.sol/node12245），但有1331个节点概率变化；该点E2/E3a best原漏报，E3b约0.512159正确，Z_C约0.490741变漏报，有实际新上下文和训练支持。另有buggy_32构造器节点屏蔽STATE_DEF_USE变错，但E2原本正确，仅证明已训练模型依赖消息维持正确。buggy_24的两个end_if节点在last联合屏蔽两种顺序关系才漏报，单项不翻转；各种干预不能线性相加。完整身份/路径/概率在case_review.md。

重入E3b last Z_ALL纠正2/新增2，等权BF1+0.060467pp但pooled−0.000666pp，保留两个口径；不以last替代best。所有固定权重节点变化均在对应两层潜在影响范围内。四个困难文件所有干预类别不变；继承与modifier只是源码分析首个回退原因，不是保证恢复量或逐节点错误归因。

现有数据不支持“消息未接入”或“状态依赖毫无价值”的结论。更具体的限制是状态DU集中构造器、覆盖与错误重合少。后续优先核对实际困难函数的继承/绑定、原HCG锚点及modifier上下文，再决定小范围扩展；本轮不编码modifier或新关系，不增加训练。guard到操作属于独立控制依赖问题，不能冒充STATE_DEF_USE。

**23.7 后处理、测试、资源与保护**

新增产物级aggregate_stage_i.py（评分角色适配，附diff/来源SHA）、analyze_messages.py、join_prediction_context.py及各自测试；另有verify_delivery.py、render_report.py、report_sections.json、case_review.md、报告与资源/保护清单。原封存aggregate.py不改，默认run summarize角色检查错误和日志保留；README明确改用独立后处理命令。后处理不改metric公式、样本身份、输入和预测。

126项接入/相关回归+36项后处理测试，共162项通过、0失败/跳过；两次命令各4条既有DGL distutils警告。60回放无失败/OOM，无训练或训练重试；v1/v2预检历史保留。没有重新执行全部历史DDG语义测试、外部solc编译、正式训练或七类扩展。
""" + resources + """
两工作树training_changes与HANDOVER仅追加；原auto_version_solc.py用户修改的SHA保持bf3365c32f65f4c51932478eb54687a53c6aaad932f8f56a4d58687aaa493f31。旧H1/H2/G计划、源码计算及产物不覆盖，无Git写操作。最终交付索引见stage_i_v3/delivery_manifest.json。实施、审查与分析AI：Codex。
"""

handover = """
### 2026-10-19 Stage I 第1、2步完成：状态消息诊断（Codex）

- 已完成能力/版本编号/入口约束清单，以及60个E3a/E3b模型、120份best/last checkpoint、720条件的只读诊断；新增训练0。实现位于开发树scripts/DFG/experiments/stage_i_diagnostics，主报告位于artifacts/paper_kfold/stage_i_v3/STAGE_I_RESULT_REPORT.md。
- 正常输出与历史概率全相同；图、标签、特征、参数、schema及聚合分母保持。1,020项状态canonical-layer消息正常均非零，说明确实进入HGT。
- E3b best屏蔽全部状态消息：两个合约任务与访问控制节点均0类别变化；重入节点1331概率变化、仅1新增漏报，等权BF1−0.011342pp。不是新训练消融结果。
- 状态DU在节点任务仅3/4条且都在构造器；重入96.13%的E2错误处于新增关系潜在影响域外，访问控制全部E2错误在域外。困难文件干预后仍无类别变化。支持“覆盖与主要错误重合少”，不支持“所有DDG无用”或“已证明泛化”。
- case_review.md给出构造器补偿、顺序联合效应、buggy_42直接目标正向案例；单关系和联合屏蔽不可相加。last单独保留，不改变best规则。
- 162项测试通过；120 checkpoint输入/恢复验收、H1 60与H2 30历史归档复核通过。旧summarize评分角色错误保留，使用README中的独立后处理脚本；旧seal和数据不改。
- 受限modifier尚未实现：初稿未展开，后续接入分析提出适配/回退；当前仍函数级回退。候选是先支持唯一绑定、明确参数与单一占位符执行顺序的子集，不能按onlyOwner名字猜，也不等同控制依赖。
- 详细修改/资源/限制见training_changes第23节、STAGE_I_RESULT_REPORT.md及protected_after.json。原工作树用户auto_version_solc.py改动保留。修改与分析AI：Codex；完成本轮后停止，未启动新训练/关系扩展。
"""
protection=json.loads((BASE/"documentation_protection_before.json").read_text())
for raw,item in protection.items():
 data=Path(raw).read_bytes()
 sample=data[:item["bytes"]] if item["rule"]=="append_only" else data
 assert hashlib.sha256(sample).hexdigest()==item["sha256"],raw
for root in (Path("/home/zhao/SmartContract/ge-sc-llm"),Path("/home/zhao/SmartContract/ge-sc-llm-ddg-v11")):
 for relative,addition,marker in (
  ("docs/training_changes_2026-10-07.md",detail,"**23.5 全折诊断完成与独立复算**"),
  ("HANDOVER.md",handover,"### 2026-10-19 Stage I 第1、2步完成")):
  p=root/relative
  assert marker not in p.read_text(encoding="utf-8"),str(p)
  with p.open("a",encoding="utf-8") as f:f.write("\n"+addition)
print(str(path))
print("4 existing documentation files appended; original byte prefixes preserved")
