"""Write final docs from completed and independently reviewed evidence."""
from pathlib import Path
import json,hashlib
R=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
A=R/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1'
def read(p):return json.loads(Path(p).read_text())
def main():
 f=read(A/'report_facts.json');done=read(A/'BC_run/execution_complete.json')
 assert done['jobs']==300 and len(done['statuses'])==300 and all(s['returncode']==0 for s in done['statuses'])
 assert read(A/'tests/final_summary.json')['total_unique_passed']==2643
 assert read(A/'protected_pre_documentation.json')['status']=='passed'
 # Independent review is checked by root before this writer is called.
 def mean(row,mode,metric='buggy_f1'):return row[mode][metric]['mean']
 names={'reentrancy_node':'重入节点','access_control_node':'访问控制节点'}
 table=['|任务|剖面|原特征|8C idN|B全量同长|B匹配标记|C匹配普通名|','|---|---|---:|---:|---:|---:|---:|']
 for r in f['main']:
  b=mean(r,'B_full');delta=r['Bfull_minus_idN']['buggy_f1']['mean']
  table.append('|{}|{}|{:.4f}|{:.4f}|{:.4f}|{:.4f}|{:.4f}|'.format(names[r['task']],r['profile'],mean(r,'original'),b-delta,b,mean(r,'B_matched'),mean(r,'C_matched')))
 tabletext='\n'.join(table);short='\n'.join(table[:2]+[x for x in table[2:] if '|G0|' in x or '|G3R|' in x])
 v=f['resources']
 resources='300个worker内部合计{:.2f}秒（{:.2f}分钟，含加载、校验、前向），子进程墙钟合计{:.2f}秒；峰值allocated/reserved为{:.2f}/{:.2f}MiB。0失败、0重试、0正式训练。'.format(v['worker_internal_seconds_sum'],v['worker_internal_seconds_sum']/60,v['subprocess_seconds_sum'],v['peak_allocated_bytes']/1048576,v['peak_reserved_bytes']/1048576)
 interpretation=(A/'documentation_drafts/result_interpretation.md').read_text()
 intro="""# Prompt 8D：名称与位移诊断、分组基准准备

日期：2026-10-29；实施与复核：Codex。工作树ge-sc-llm-ddg-v11，分支dfg-v2，起点dd70fb966b64df43ac9e75a6f94f0b675fcaa593。先读更新后§4.1/§4.10e并完成git pull --ff-only核验，没有切换、重置或迁移旧批次。

**本轮A–E诊断和F候选方案准备已完成，300次推断全部验收，170次正式拟合未运行。关键未解决项：F选择性idN替换仍保留强烈注入标记，不可称已消除词法捷径；正式执行前需先征求用户对替代命名处理的意见。**

## B/C：已批准的300次对照与结果

原C要求匹配全部标记名称，但80个SolidiFI实例都缺少足量同token长度的普通名称。用户批准B_full100次、B_matched100次、C_matched100次。三组使用相同的100个best节点checkpoint，eval/no_grad；另有1次当前GPU恒等门槛，历史argmax与float32正类概率逐位一致。原归档没有logits，不宣称验证了归档logits。

下面是orig标签、全部原HCG节点、best checkpoint的10折等权Buggy-F1均值（%）。它们是测试时输入干预诊断，不是新特征重新训练后的成绩。逐折MF1/P/R、样本标准差、pooled、翻转率、概率及文件分布均保留在汇总。
"""
 details="""

匹配保证每文件唯一名称数和孤立token长度直方图；不匹配出现频率、语义角色和受影响节点数。10个AC文件没有可匹配名称，原样保留，不删样本。

|干预|重入/AC唯一名称数|重入/AC修改代码节点数|重入/AC节点文本内改写次数|
|---|---:|---:|---:|
|B_full|2585/2222|5678/2328|14790/7777|
|B_matched|100/146|310/224|522/514|
|C_matched|100/146|845/393|2135/1115|

节点文本可嵌套包含同一源码；词法次数不等于独立源码位置。全部视图核验整段未截断token长度、每处编辑的token区间，以及区间外所有token ID。独立CPU重编码9778条修改记录，证明与512维冻结配方一致。R三组分别1/8/15条、AC1/1/11条改写在截断之外，代码变化但向量不变。

三组非SolidiFI预测逐位不变：每组五剖面共R5725、AC2595行，分类和概率变化均0。汇总按task/fold/file/source SHA/node identity对齐，拒绝缺失/重复/错位/混合来源，绑定当前环境门槛及原checkpoint与state。B_full相对8C idN同时改变替代词token值和位移行为；不能将分差全部当作位移的纯因果贡献。C匹配组的代码暴露量更大，不能把全部差异归结为“标记词特殊性”。

"""
 fixed=(A/'documentation_drafts/report_fixed.md').read_text()
 fixed=fixed[fixed.index('## '):]
 end="""

## 本轮执行与证据入口

"""+resources+"""

GPU门槛和CPU恒等验收另计，不算正式拟合。实际执行命令见 [diagnostics8d/README.md](diagnostics8d/README.md)，候选准备接口见 [benchmark_v2/README.md](benchmark_v2/README.md)。既有目录拒绝覆盖，不能复制命令覆盖历史产物。

- [300次完整汇总](../experiments/artifacts/dfg_v2/prompt8d_v1/BC_run/summary/summary.json)
- [独立300结果复核](../experiments/artifacts/dfg_v2/prompt8d_v1/BC_final_summary_review/REVIEW.md)
- [测试结果](../experiments/artifacts/dfg_v2/prompt8d_v1/tests/final_summary.json)
- [结束历史保护核验](../experiments/artifacts/dfg_v2/prompt8d_v1/protected_final.json)
- [详细实施记录](../../../docs/training_changes_2026-10-07.md)

本轮本地提交，不自动push，不执行170fit、不增加seed或其余五类。原512/111条人工依赖核验仍未完成，不宣称完整Solidity语义或外部泛化已被证明。
"""
 commands="\n\nActual test commands in the existing mando environment (PYTHONDONTWRITEBYTECODE=1, OMP/MKL=2, existing TREE_SITTER_LIB_DIR):\n\n    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests\n    CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py\n"
 report=intro+'\n'+tabletext+'\n\n'+interpretation+details+fixed+commands+end
 output=R/'scripts/DFG/dfg_v2/PROMPT8D_REPORT.md'
 assert not output.exists()
 impl=(A/'documentation_drafts/implementation.md').read_text()
 impl=impl[impl.index('日期：'):]
 lines=[];n=0
 for line in impl.splitlines():
  if line.startswith('## '):
   n+=1;line='### 66.{} {}'.format(n,line[3:])
  lines.append(line)
 detailed='\n\n## 66. 2026-10-29 Prompt 8D：300次诊断与分组基准准备（Codex）\n\n'+'\n'.join(lines)
 detailed+='\n\n### 66.{} 已完成结果与方法限制\n\n'.format(n+1)+tabletext+'\n\n'+interpretation+details+'\n\n'+resources
 detailed+='\n\n### 66.{} 新发现：F命名政策尚不能消除捷径\n\n'.format(n+2)+(A/'F_naming_risk/CAVEAT.md').read_text()
 detailed+='\n\n### 66.{} A/D/E及F完整验收\n\n'.format(n+3)+fixed.replace('../experiments/artifacts/dfg_v2/', '../scripts/DFG/experiments/artifacts/dfg_v2/')
 detailed+='\n\n### 66.{} 收尾记录\n\n'.format(n+4)
 detailed+='实际命令完整记录在diagnostics8d/README.md和benchmark_v2/README.md。300份推断收据、指标重算及非SolidiFI不变核验通过。4071历史引用和298计算SHA一致，三份文档旧正文只保留并追加。新增代码14模块、7组测试、2README及报告；不提交大权重或改变旧归档。F170仍未授权，命名策略需先讨论、标签/seed/位置尚未选定。本轮本地commit，不自动push。\n'
 note="""**正式训练前的阻断项：只把注入名改为idN仍保留可识别标记。** 原文本中idN为0；改名后无学习idN规则在SolidiFI C2上AC99.983625、R99.977786 BF1。已记录证据，未静默换方案或修改F seal；必须先征求用户对普通/注入名称一致处理等替代策略的意见。C1/C2本身也只是诊断假设。
"""
 final="""最终2643测试通过（2420v2+223旧），0失败/错误/跳过，8/29条既有弃用警告。4071历史引用和298计算文件SHA一致，三份文档旧正文只追加。F170计划、30个分组嵌套折、51490行特征复核与恒等视图证明已准备，execution_authorized=false。两分支各1CPU epoch共2次验收optimizer更新，正式fit=0；scheduler地址比较首份失败保留，数值复核未重训。详细结果/选择/命令见PROMPT8D_REPORT.md、training_changes§66及README。
最终正式实验将按用户安排在显存充足服务器整批运行，当前RTX3050 4GiB只是本机限制；服务器未部署/实测，不混合两地成绩。当前停在F，不执行170fit、加seed或扩展五类。512/111人工依赖核验仍未完成。本轮本地提交，不push。
"""
 progress='\n\n## 2026-10-29 Prompt 8D完成（Codex）\n\n'
 progress+='新增diagnostics8d/benchmark_v2旁路、7组测试、两个README和报告；原DDG/HGT/tokenizer/训练器、图/标签/旧折、150项结果及8C不改。按用户批准完成B全量/B匹配标记/C匹配普通名各100，共300次best诊断推断；另1GPU恒等门槛逐位一致。下表是orig节点BF1等权折均值，不是重训后的成绩。\n\n'+short+'\n\n'+interpretation+'\n\n'+note+'\n\n'
 progress+='A的19746节点归属核验完成，D没有证明问题列表抄自buggy24，E揭示改名后简单关键词仍很强。匹配只保证名称数/长度，不保证改写次数/节点暴露。'+resources+'\n\n'+final
 hand='\n\n## 2026-10-29：DFG v2 Prompt 8D完成（修改AI：Codex）\n\n'
 hand+='新增诊断与候选分组基准旁路，原算法/图/标签/历史折/150结果/8C不改。按用户批准完成300次best推断（全量同长标记名、匹配标记子集、匹配普通名，各100）；0正式训练。下表为orig节点BF1等权折均值（%），不是新特征重训成绩。\n\n'+short+'\n\n'+note+'\n\n'
 hand+='A/D/E已完成；没有证据认定作者附带行列表来自buggy24。完整P/R/翻转/概率、独立复核及资源见PROMPT8D_REPORT。匹配覆盖不同，不作纯因果解读。\n\n'+final
 progress+=commands
 detailed+=commands
 start=read(A/'protected_start.json')
 additions={'docs/training_changes_2026-10-07.md':detailed,'scripts/DFG/dfg_v2/PROGRESS.md':progress,'HANDOVER.md':hand}
 for name in additions:
  assert hashlib.sha256((R/name).read_bytes()).hexdigest()==start['docs'][name],name
 with output.open('x',encoding='utf-8') as h:h.write(report)
 for name,text in additions.items():
  with (R/name).open('ab') as h:h.write(text.encode('utf-8'))
 print(json.dumps({'report':str(output),'appended':list(additions),'report_bytes':output.stat().st_size},indent=2))
if __name__=='__main__':main()
