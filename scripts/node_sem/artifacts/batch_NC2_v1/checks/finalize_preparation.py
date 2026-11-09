from pathlib import Path
import csv,hashlib,json,re,statistics
root=Path('scripts/node_sem/artifacts/batch_NC2_v1')
load=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
reference=lambda p:dict(path=str(Path(p).resolve()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest())
verification=load(root/'verification.json')
reg=load(root/'regressions.json')
audit=load(root/'checks/frozen_audit.json')
assert verification['passed'] and reg['passed'] and audit['passed']
assert load(root/'checks/student_export_audit.json')['passed']
assert verification['HGT_fits']==0 and not (root/'authorization.json').exists()
plan=load(root/'plan.json')
summary=load(root/'student_summary.json')
counts={}
for suite in reg['suites']:
 text=(root/'checks'/(suite['suite']+'.log')).read_text()
 counts[suite['suite']]=int(re.findall(r'(\d+) passed',text)[-1])
total=sum(counts.values())
labels={'reentrancy_node':'重入节点','access_control_node':'访问控制节点','access_control_contract':'访问控制合约','reentrancy_contract':'重入合约'}
table='|任务|折数|每折导出节点|学生 outer 余弦均值±样本SD|原岭回归均值|运行轮数范围|\n|---|---:|---:|---:|---:|---:|\n'
for g in summary['groups']:
 table+='|{}|{}|{}|{:.6f} ± {:.6f}|{:.6f}|{}–{}|\n'.format(labels[g['task_id']],g['folds'],g['all_nodes'],
 g['student_outer_cosine_mean'],g['student_outer_cosine_sample_sd'],g['ridge_outer_cosine_mean'],*g['epochs_range'])
cost=summary['cost']
report=f"""# NS-P8b：按折学生蒸馏与 N-C2 准备报告

2026-11-09，修改与执行：Codex。依据 PROMPTS.md r28 §4.8、§5.1、§5.11b。

**30/30 个 CPU 学生已经训练、导出并验收；30项S5与30项条件S8已准备载体和零步初值，计划已封存。正式 HGT 训练为0次，等待本批独立授权。** 这里的“准备完成”不等于S5/S8的检测实验已经完成。

## 1. 为什么继续以及本轮实际范围

N-C1的预登记继续条件(b)满足：重入节点非SolidiFI pooled BF1增加0.6629pp；整体best折均差反为−0.0490pp，主比较p=0.9592。沿用该资源决策，不能将微弱的继续依据写成教师已经稳定有效。

本轮主输入保持原名。图仍为冻结G3R（作者HCG上的CG/CFG与DFG增量），不重新构图、增加关系、改标签或折。沿用既有256维CTX和245维STATIC，共501维学生输入；245维来自已封存模态，本轮没有新增静态位。HGT的S5为S4+384维STUDENT及一个存在位，载体760→1145维；S8只对该STUDENT做固定置换。未重新生成LLM描述或教师向量。

每个任务/外层折独立CPU学生：CTX逐维标准化后拼接STATIC，501→512→384，GELU、Dropout0.1；AdamW lr=0.001、weight_decay=0.0001，batch1024，最多30轮，patience5，严格最低inner_val余弦损失保存最佳学生。仅使用1−cos损失，不使用role头、分类标签或漏洞预测。

训练与早停均只使用各自文件分区内teacher存在的节点；CTX均值、总体方差只从这些inner_train节点估计并保存，零方差scale取1。学生导出所有节点，包括辅助节点和teacher缺失节点，STUDENT存在位全部为1。outer_test教师仅在最佳学生已经选定、向量导出后计算诊断，绝不用于拟合、早停或选超参。

## 2. 学生诊断：并非漏洞检测分数

{table}
上表为等权外层折均值与样本标准差。原岭回归与学生的inner_train/inner_val/outer_test节点身份逐折摘要完全相同；没有另跑岭回归或重新挑选其alpha。这些有效节点数指有教师向量的节点，不是漏洞正例数。逐折训练/早停/外层教师节点数、best epoch、余弦和耗时见student_diagnostics.csv及各fold的diagnostics.json。

四任务学生比岭回归更接近教师，幅度约0.010–0.014余弦；嵌入本身与同类型均值的余弦也很高，不能由0.89推导“保留89%的漏洞知识”。这不是BF1、准确率或独立测试集上的检测收益。

教师向量只覆盖其描述有效的节点，而学生覆盖全部节点；因此后续S5−S6还包含覆盖差异，不能作为纯压缩损失。S6只是经验参照，并非数学性能上限。仅在S6−S4为正时给出描述性保留比值；为零或负时该比值不作解释，直接报告百分点差。

## 3. 初值、对照与执行规则

30份N-A S4零步初值仍可核验，S4共同参数逐位复制；缺失时的确定性重建及原digest门槛仍保留，不允许用训练后的S4或S6启动。S5仅新增STUDENT投影/归一化参数，按语义种子生成。S8复制同折S5的全部零步参数；两个payload各自绑定真实spec，张量摘要完全相同。

S5/S8的fit种子与模态dropout随机身份一致。冻结run_core每次都会重新设置dropout，故N-C2只在S8构造后将适配层的随机身份设为同折S5；实际S8 spec、向量、载体、checkpoint身份不变。相关前向重复与随机流一致性测试通过。S5与历史S4的模态数及随机流仍不同，因此S5−S4不是纯教师语义的因果贡献。

S8置换限定在同一任务、同一折、同节点类型内，可跨该折文件分区；这保持了模板的置换定义，不使用标签。每折保存完整映射，不重新采样有利置换。

固定顺序为重入节点10折、访问控制节点10折、访问控制合约5折、重入合约5折。先验收全部30项S5，再仅根据重入节点best外层BF1的S5−S4等权折均差决定：严格大于0才跑完整30项S8，否则全部跳过。不是按某个有利fold或非SolidiFI子集启动S8。执行控制器和直接worker均有门槛，不自动无限重试。

主比较双侧Wilcoxon为重入节点S5−S4；若执行S8，S5−S8与S5−S4共同做Holm校正。按结果触发S8仍属探索性选择，Holm不能消除该选择过程。best/last、原标签/L-audit、折均/pooled、两个漏洞及两种粒度分别报告；32/20非SolidiFI正例逐节点对齐要求不变。

## 4. 用户批准的三项调整

1. 模板的2文件不足以构成互不相交且非空的三路分区。已批准使用3文件、2个玩具外层折，保留全部节点导出、防泄漏和逐位确定性测试。
2. 特征manifest参与原初始化种子；S8置换后若照常独立初始化，会同时改变参数。已批准S8复制S5完整零步初值及训练随机起点，使该对照仅改变学生向量排列。
3. 已批准复用封存S4载体和未训练模型结构以减少重复解析。四任务分别对S5/S8完整装配与快路径做8次逐位核验；每任务fold1新建模型与复用结构的初值做4次逐位核验。每fold仍独立保存spec、载体、初值和proof，正式fit仍独立进程。

原student_plan与decisions不回写；第三项记录在独立preparation_decisions.json。来源与选择全部保留，不覆盖旧N-A/N-C1或8H计划。

## 5. 成本与资源

|项目|本轮是否新增|已记录成本|
|---|---|---:|
|NS-P7c 3B生成：4485单元，4197成功、4解析失败、284无函数体跳过|否，沿用既有结果|{cost['LLM_generation_seconds']/3600:.4f}小时|
|BGE教师编码：7960唯一文本，两次逐位一致核验|否|{cost['teacher_encoding_seconds']:.2f}秒|
|30个CPU学生拟合、导出前诊断|是|累计{cost['student_fit_diagnostic_seconds']:.2f}秒|
|S5/S8正式HGT拟合|尚未授权|0次|

学生累计秒数不包含大部分输入SHA读取、载体装配与HGT初值封存，不能当作本轮总墙钟。历史LLM成本不会因复用而消失，但本轮LLM调用与教师重新编码均为0。

HGT设备族沿用本机RTX3050及N-A/N-C1的TF32配置，local_dev_v1和OOM停止规则不变。最终实验会在显存充足服务器另建批次；当前4GiB限制仅来自本机开发，不混合设备结果、不自动单边迁移。

## 6. 验收与停止位置

定向测试57项通过；完整回归NodeSem {counts['nodesem']}、DFG v2 {counts['dfg_v2']}、旧模块 {counts['legacy']}，共{total}项通过。8H只读装载及有效修订354份源码一致；N-C1原375份运行源码不变。学生不读取标签的输入白名单、outer教师/特征扰动不改变训练参数、outer节点注入拒绝、同seed逐位重复、类型内置换和S8唯一门槛测试通过。

另以独立读取核验30对S5/S8 NPZ与置换映射，确认全部节点身份、存在位不变，向量严格为类型内排列。60份预备HGT初值严格加载与tensor digest核验、30对S4共有参数及S5/S8完整参数一致性通过。固定输入、schema、支持量与S4一致，原图保持不变。prepare/学生失败0、自动重试0；没有正式HGT fit或GPU初始化。

新plan SHA256：{reference(root/'plan.json')['sha256']}。运行源码绑定{len(plan['runtime'])}个文件。授权模板仍为false；没有execution_revision或authorization。按§5.11b“先计划与封存，写授权模板并停下”，当前停在这里。S5是否改善检测、S8是否需要运行、S5−S6实际差距尚无新结果，不能提前给结论。

命令见NS_P8B_README.md；完整权重、向量、载体与证据保存在WSL。Git只提交代码、测试、文档、紧凑诊断、计划及SHA索引，不提交大型权重或特征缓存。详细实施记录同步到HANDOVER.md、training_changes_2026-10-07.md和PROGRESS.md。
"""
Path('scripts/node_sem/NS_P8B_REPORT.md').write_text(report,encoding='utf8')
brief=f"""
## 2026-11-09 NS-P8b N-C2学生与计划准备完成（修改 AI：Codex）

30/30个CPU学生蒸馏、全节点导出和诊断已完成；30项S5＋30项条件S8的逐折载体、零步初值和plan/seal已封存。正式HGT训练0次，授权模板false，按PROMPTS §5.11b等待本批独立训练授权。原名视图、S4/G3R、冻结标签/划分/配置保持。

学生outer教师余弦均值：重入节点0.895862、访问控制节点0.890985、访问控制合约0.890789、重入合约0.888804，均略高于原岭回归；这是向量拟合诊断，不是漏洞检测提升。学生全部节点存在，教师仅有效描述节点存在，后续S5/S6差异含覆盖变化。

用户批准3文件两折防泄漏测试、S5/S8共享全部初值与随机起点、完整验收后复用冻结S4载体与未训练结构。{total}项回归通过，8H354与N-C1原375份源码不变；失败0/重试0。S8只在重入节点best的S5−S4等权折均差>0时全体运行，否则全体跳过。详情见scripts/node_sem/NS_P8B_REPORT.md、NS_P8B_README.md及batch_NC2_v1。

最终服务器实验另建显存充足批次；本机RTX3050 4GiB仅开发限制。本轮不启动下一阶段、不自动推送。
"""
before=load(root/'checks/documentation_before.json')
for name in ['HANDOVER.md','scripts/node_sem/PROGRESS.md']:
 p=Path(name);raw=p.read_bytes()
 assert len(raw)==before[name]['bytes'] and hashlib.sha256(raw).hexdigest()==before[name]['sha256']
 with p.open('a',encoding='utf8') as f:
  f.write('\n'+brief)
  if name.endswith('PROGRESS.md'):
   f.write('\n新增文件：student.py、student_artifacts.py、p8b_students.py、nc2_init.py、nc2_carrier.py、batch_nc2.py、p8b_prepare.py、batch_nc2_worker.py、batch_nc2_controller.py、nc2_gate.py，以及test_student.py/test_batch_nc2.py、NS_P8B报告与README。测试命令为mando CPU下python -B -m pytest -q -p no:cacheprovider，分别指定scripts/node_sem/tests、scripts/DFG/dfg_v2/tests、scripts/DFG/tests tests/test_graph_utils.py；日志在batch_NC2_v1/checks。\n')
p=Path('docs/training_changes_2026-10-07.md');raw=p.read_bytes()
assert len(raw)==before[str(p)]['bytes'] and hashlib.sha256(raw).hexdigest()==before[str(p)]['sha256']
with p.open('a',encoding='utf8') as f:
 f.write('\n\n## 95. NS-P8b按折学生与N-C2准备（2026-11-09，Codex）\n\n'+report)
 f.write("""
详细实现清单：student.py为纯CPU、无标签MLP及严格split检查；student_artifacts.py按已封存CTX/STATIC/TEACHER身份加载并输出state/scaler/manifest；p8b_students.py封存30项学生计划；nc2_carrier.py复用S4矩阵并与完整carry比较；nc2_init.py严格复制共同参数且绑定S5/S8随机身份；batch_nc2.py校验独立计划、旧收据与输入；p8b_prepare.py独立保存60项载体和零步初值；batch_nc2_worker/controller复用冻结训练核心，nc2_gate.py从已验收预测与冻结标签重算唯一S8终点。没有复制训练算法或修改旧运行入口。

CPU学生通过后，逐任务图仅作为HGT装配与完整性核验输入；学生核心只接收向量、teacher存在位、文件分区和派生种子，不接收标签或预测。完整图装配仍按冻结实现检查标签元数据，此点不应误写成整个准备流程完全没有接触标签。新增代码都位于node_sem，原产物和已封存学生计划只读。

代码中的S8 spec_digest随机身份适配只在构造阶段改变适配层用于reset_dropout的身份；model.nodesem_spec、nodesem_spec_sha256及载体内容仍为实际S8。S5正常路径原样调用冻结construct/run_core；compute body与已验收worker除purpose外一致的测试通过，且S5/S8相同输入及权重时随机前向逐位相同。真正正式HGT执行与checkpoint往返验收仍待授权后完成，准备验收不能代替正式fit成功。

30个学生使用相同原fold不同派生种子，属于一套固定seed的交叉验证，不是30次独立seed重复。S8每类型固定置换保存映射；不按指标重选或删困难节点。大权重和NPZ留在WSL，不删除历史模型。
""")
(root/'preparation_summary.json').write_text(json.dumps(dict(passed=True,stage='prepared_waiting_HGT_authorization',
 students=30,HGT_fits=0,S5_jobs=30,conditional_S8_jobs=30,tests=counts,total_tests=total,
 plan=reference(root/'plan.json'),report=reference('scripts/node_sem/NS_P8B_REPORT.md'),
 frozen_audit=reference(root/'checks/frozen_audit.json'),diagnostics=reference(root/'student_summary.json')),indent=2))
print('documents appended; tests',total)
