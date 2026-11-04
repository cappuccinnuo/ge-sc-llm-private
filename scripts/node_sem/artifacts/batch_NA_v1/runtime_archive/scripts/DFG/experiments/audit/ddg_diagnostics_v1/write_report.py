"""Write the evidence-graded report from completed diagnostics; no model loads."""
import csv
import json
from pathlib import Path
from .diagnostic_common import ROOT, read_json
TASKS=[('reentrancy_author','contract'),('access_control_author','contract'),
       ('reentrancy_author','node'),('access_control_author','node')]
NAMES={TASKS[0]:'重入·合约',TASKS[1]:'访问控制·合约',TASKS[2]:'重入·节点',TASKS[3]:'访问控制·节点'}
def table(headers,rows):
    esc=lambda value:str(value).replace('|',r'\|')
    return '\n'.join(['| '+' | '.join(map(esc,headers))+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(map(esc,row))+' |' for row in rows])
def main():
    s=read_json(ROOT/'aggregate_summary.json')
    audit=read_json(ROOT/'input_audit.json')
    tests=read_json(ROOT/'final_tests.json')
    assert tests['returncode']==0
    assert s['paired_best_folds']==30 and s['independent_prediction_recomputation']=='passed'
    assert audit['final_drift_check']['passed']
    static=read_json(ROOT/'static/summary.json')['tasks']
    rows=s['main_best']
    find=lambda key,variant,condition:next(r for r in rows if (r['cohort'],r['task'])==key and r['variant']==variant and r['condition']==condition)
    metric=lambda r:r['equal_fold_metrics']['buggy_f1']['mean']
    base=[];zero=[];info=[];messages=[];rew=[]
    for key in TASKS:
        e0=find(key,'E0','N');n=find(key,'E1','N');z=find(key,'E1','Z')
        base.append([NAMES[key],f"{metric(e0):.4f}",f"{metric(n):.4f}",f"{metric(n)-metric(e0):+.4f}"])
        zero.append([NAMES[key],f"{metric(z):.4f}",f"{metric(z)-metric(n):+.4f}",
                     str(z['prediction_flips'])+'/'+str(z['pooled_count']),
                     str(z['corrected'])+'/'+str(z['introduced']),
                     f"{z['probability_abs_mean_pooled']:.6g}",
                     str(z['folds_with_probability_change'])+'/'+str(len(z['folds']))])
        st=static[key[0]+'_'+key[1]];i=st['information_increment'];c=st['counts']
        far=i['distance_buckets'].get('>2',0)+i['distance_buckets'].get('unreachable',0)
        info.append([NAMES[key],str(c['functions_analyzed'])+'/'+str(c['functions_total']),
                     str(c['facts_extracted'])+'/'+str(c['facts_projected']),
                     i['ddg_edges'],f"{far}/{i['ddg_edges']} ({100*far/i['ddg_edges']:.2f}%)",
                     f"{i['nodes_with_new_upstream_two']}/{i['nodes']} ({100*i['nodes_with_new_upstream_two']/i['nodes']:.2f}%)"])
        for layer in ['0','1']:
            m=next(r for r in s['message_summary'] if (r['cohort'],r['task'])==key and r['variant']=='E1'
                   and r['checkpoint']=='best' and r['condition']=='N' and str(r['layer'])==layer and r['branch']=='message_to_residual_ratio')
            d=next(r for r in s['message_summary'] if (r['cohort'],r['task'])==key and r['variant']=='E1'
                   and r['checkpoint']=='best' and r['condition']=='N' and str(r['layer'])==layer and r['branch']=='ddg_to_base_ratio')
            messages.append([NAMES[key],int(layer)+1,f"{m['node_weighted_mean_across_forwards']['mean']:.6g}",
                             f"{d['node_weighted_mean_across_forwards']['mean']:.6g}",
                             m['excluded_near_zero_denominator'],d['excluded_near_zero_denominator']])
    with (ROOT/'rewiring_validation.csv').open() as f:rv=list(csv.DictReader(f))
    for key in TASKS:
        for seed in [101,102,103]:
            v=[r for r in rv if (r['cohort'],r['task'])==key and int(r['seed'])==seed]
            edges=sum(int(r['validation_ddg_edges']) for r in v)
            changed=sum(int(r['validation_replaced_semantic_edges']) for r in v)
            zfolds=sum(int(r['validation_replaced_semantic_edges'])==0 for r in v)
            r=find(key,'E1','R'+str(seed))
            rew.append([NAMES[key],seed,f"{changed}/{edges} ({100*changed/edges:.3f}%)",
                        str(zfolds)+'/'+str(len(v)),r['prediction_flips'],
                        f"{metric(r)-metric(find(key,'E1','N')):+.4f}"])
    resources=[]
    for stage in ['pilot_v2','remaining']:
        comp=read_json(ROOT/'forward'/stage/'completion.json')
        for j in comp['jobs']:
            resources.extend(read_json(ROOT/'forward'/stage/j/'result.json')['variants'].values())
    max_mem=max(v['cuda_peak_allocated_bytes'] for v in resources)/2**20
    checkpoint_count=s['checkpoint_evaluations']
    text=f"""# MANDO-LLM + DDG 原因诊断报告

执行者：Codex；日期：2026-10-13。仅使用既有正式实验与冻结权重。主诊断包含全部30个配对折；7个预定试点另观察initial/last，共{checkpoint_count}次checkpoint状态评估。没有重新训练或挑选epoch。

## 核心结论

证据不支持“DDG没有接入模型”或“DDG对重入/访问控制无效”这两个笼统结论。DDG消息会改变概率和部分预测；其影响既有帮助也有损害，当前方案尚未产生稳定净收益。
已确认同时存在：局部标量/入口依赖占主导、关键状态与modifier范围缺失、大部分边端点原本就在两跳内、全折消息与残差的量级差异、模板重复和标签上下文冲突、少量真实投影/解析缺陷。尚未用受控重训练分离这些因素各自对F1的因果贡献。

本报告的证据类别：
- **直接证据**：冻结文件、原标签、预测、图计数和源码。
- **代码推导**：由已核验的实际实现及其数据结构可推出的机制。
- **诊断观察**：冻结模型N/Z/R的实际测量。
- **待验证假设**：需要新实验或独立标注核查才能证实的解释。

## 1. 归档、范围和正式结果

归档HEAD为3fb3fbcaed34c5c97976b570aac484935aa81484，训练基为646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc。使用既有report_stage_c.py只读核验，complete_tasks=4、pending_tasks=0；没有运行要求HEAD相等的formal verify。
最终5387份保护文件摘要不变、HEAD不变、没有新增保护范围内的文件。该集合包含原final_v1全部8份报告、主运行目录1217份资产、原fold0目录44份资产、全部既有已跟踪文件及本轮相关prepared输入。详见input_audit.json和archive/protection_scope.json。

正式best Buggy-F1等权折均值复核如下（单位%）。这些是CV validation，不是独立测试；节点任务单位是HCG节点，未改成去重后的源码行指标。

{table(['任务','E0','E1','E1−E0（百分点）'],base)}

所有有归档预测的已训练checkpoint，其正常离散预测、四指标和混淆矩阵与归档一致；概率通过事前声明的atol=1e-6、rtol=1e-5；N包装器与原生forward逐位相等；干预退出后输出、图、参数身份和权重摘要恢复。一次仅构造一套模型，已记录的峰值torch CUDA allocated为{max_mem:.2f} MiB（不含Windows/驱动等其他显存使用）。

## 2. Q1：当前覆盖了什么，遗漏什么？

**代码事实**：当前是函数内标量Definition–Use，symbol以声明/作用域标识；支持的参数、局部标量、命名返回值参与分析。状态存储内容、mapping内容、引用别名、modifier执行、跨过程摘要没有实现。成功分析一个函数并不代表已经覆盖这个函数全部数据依赖。

{table(['任务','分析成功/源码函数体','提取facts/投影facts','实际DDG边','原两跳之外的端点连接','获得新两跳上游的节点'],info)}

分母是任务文件中解析出的可调用函数体，不含modifier定义；完整文件回退函数也计入失败数。facts投影率只衡量已提取的局部事实，不能称为完整Solidity依赖覆盖率。facts合并到相同节点对后去重，亦有自环过滤；逐文件/函数与原因见coverage.csv、static/function_coverage.csv、static/facts.csv。

节点任务的入口来源边为重入1162/1711、访问控制2416/2632。入口定义还包含constructor和legacy模式局部默认定义，不能全称“参数边”。按符号事实来源，重入2014/2636、访问控制3833/4101为parameter，说明现有增强主要补充参数/局部值传播，而非存储状态安全语义。

**支持的解释**：重入的余额状态更新、权限检查里的owner状态、modifier及跨函数关系可能没有被当前DDG提供。
**不能推出**：所有错误都来自范围不足。AC buggy_18的87个共同错误有86个在两层DDG影响范围，buggy_26的42个共同错误全部在影响范围，仍未纠正。

## 3. Q2：新增上下文有多少？

上表的距离使用生产reflect_graph实际生成的基础拓扑，包含其原有反射规则；DDG仍只有正向DATA_DEF_USE。距离>2与不可达计入“原两跳之外”；0、自环和映射情况在逐边表单列。

节点任务仅25.31%（重入）、10.22%（访问控制）的DDG端点连接超出原两跳。这支持“直接扩大可达上下文的比例有限”，但近邻DDG仍增加了有类型的直接消息通道，不能把这些边全部称为无效重复。
“边端点超出两跳比例”与“获得新两跳上游的节点比例”不是同一个量：加一条DDG还会改变其相邻节点的两层传播路径。完整统计见edge_increment.csv及static/*_edges.csv、*_node_context.csv。

## 4. Q3：冻结模型究竟依赖DDG多少？

Z在两层实际消息参与cross mean前置零，保留图、关系字典、attention、E1权重和跨关系分母。Z不是重新训练的E0。以下是所有fold的Z相对正常E1结果，概率差为每任务val样本汇总平均绝对差（0到1量纲）。

{table(['任务','Z Buggy-F1','Z−N（百分点）','翻转/评分样本','修正/新增错误','平均|Δp|','概率改变折数'],zero)}

必须区分两种对照：E1−E0同时包含训练轨迹、参数和关系schema差异；N−Z只测当前E1固定权重下的DDG消息作用。因此，“正常E1优于置零E1”与“E1未稳定超过E0”可以同时成立，不能把两者当成同一个消融结论。

每折logit和概率的mean/median/p95/max、翻转、四指标、混淆矩阵见sensitivity.csv；LayerNorm前后表示差见representation_changes.csv。完整message_norms.csv约1.23GB；查看汇总优先使用aggregate_summary.json及message_global_by_fold.csv。F1相同、分类相同、概率相同、logits相同分别核验，不能混称“不变”。

困难例：重入节点fold8，N的Buggy-F1为67.5579，Z为67.1391；Z新增7个错误，没有纠正错误。可确认当前DDG消息对某些节点有益，但不足以解决buggy_18主导的错误。对该文件节点2706和2670，N/Z概率逐位相同；节点2675的概率从约0.432524降至0.430357，仍判负。冻结权重干预只解释当前模型敏感性，不代表删DDG后重训练的性能上限。

## 5. Q4：真实DDG与重连DDG有区别吗？

约束保持同文件、同可确认函数、同canonical和每节点该关系入出度。大量组只有一个源节点或少于两条边，无法充分交换。下表按全部折的val文件DDG边汇总，种子单列；未在测试时新建参数、跨文件交换或借标签选边。

{table(['任务','扰动种子','val语义边替换','零val扰动折数','预测翻转','R−N F1百分点'],rew)}

例如重入合约fold0：R101只替换val的6/698条边，R102为4/698，R103为0。R103虽改变训练文件里的边，其val logits完全相同是符合文件互不连接的预期，不能当成模型忽略依赖语义的证据。

**结论**：这些约束下R通常不足以广泛检验“正确依赖语义是否有价值”。保留所有三个种子，不只选择最大扰动或最好结果。本轮没有采用跨函数乱连来人为扩大扰动。详见rewiring_audit.json、rewiring_validation.csv。

## 6. Q5：关系平均、残差和初始化是否减弱作用？

**源码与运行时证据**：当前DGL0.6.1按canonical分别聚合，再对目标类型的已参与关系结果取mean。某节点对某关系没有入边时，零消息仍可进入该类型跨关系平均。合成测试验证了这一点。E1增加relation schema不仅影响DDG端点，也可能改变没有DDG入边节点的基础消息分母。

原HGT的attention softmax在每个canonical内部，不是基础关系与DDG之间统一的竞争门控。skip初始化为1，alpha=sigmoid(skip)约0.7311，但这不是分支实际范数比例；原始512维token ID经adapt线性层得到的自身表示在第一层可很大。

以下为E1 best正常前向：先按节点计算范数比，排除近零分母，再在互斥节点类型间按节点数合并；最后等权折平均。完整图包含train/val，不能把该表称val-only。

{table(['任务','层','消息分支/残差 均值','DDG和/基础和 均值','残差近零剔除累计','基础近零剔除累计'],messages)}

分支位置为alpha*drop(a_linear(cross_mean))与(1−alpha)*h；不是只对原始DDG向量比较。a_linear bias、不同关系向量抵消和LayerNorm都影响量级，范数比不能单独证明因果。type/file的median/p95和零值比例保留在message_norms.csv；不从分组分位数推造全体分位数。

DDG/基础的总体均值包含DDG消息为零的节点，所以同时受覆盖稀疏性和消息量级影响，不能把低均值直接等同于每条DDG消息都很小。

**初始化事实**：relation_att/msg对整个[relations,heads,d_k,d_k]四维bank调用Xavier，fan_in=heads*d_k²，fan_out=relations*d_k²。相对逐head方阵Xavier，当前新DDG理论std只有约2.59%到2.74%；实际initial矩阵std约0.00647到0.00687。E1共享关系来自E0 bank，新增关系来自E1 bank，已按来源分别计算，未混用形状。
试点best和last的DDG message参数std已经增大，说明“初值小”不等于“始终没学”。参数表见parameter_scales.csv；试点以外没有扩展initial/last诊断。

**全量观察与限制**：消息并非普遍接近零。节点任务的总message/residual均值第一层约0.59–0.71、第二层约0.66–0.67，已是不可忽略的量级，而且部分折超过1。不能把首个试点较弱的消息量级外推为“残差把DDG完全淹没”。关系平均和初始化仍是候选机制，但当前数据不足以把它们认定为主因。四维bank初始化还是E0/E1共同采用的原HGT规则，不能独自解释两者成绩差异。
**仍不能排除**：特征可分性、依赖覆盖、标签上下文和早停选择等解释；本轮未更改融合或初始化，因此不能判定哪一项是主因。

少量DDG关系只在val文件出现：重入合约2/70、访问控制合约3/80、重入节点1/120、访问控制节点4/150个relation×fold组合没有train边。其余有train边的组合在训练记录中均出现过非零message梯度。因此，不能将全部val敏感性都解释为已经学得的依赖语义；val-only关系仍可能主要反映初始化及非监督更新。见static/relation_support.csv。这里的“沿两层DDG路径影响”也不包含schema平均分母变化和共享参数训练影响。

## 7. Q6：重复、标签分布和困难文件有什么作用？

train-only精确匹配显示：节点任务的val正例，重入6556/6570（99.79%）、访问控制2948/2977（99.03%）可在本折train找到相同stored code；实际float32[512]特征的重复数量相同。索引先由train建立，val标签只用于匹配之后分组，不参与任何构图或干预。

这不是仅由结构节点造成：排除end_if/end_loop后，正例重复率仍为重入99.76%、AC99.03%；表达式节点正例重复率为99.82%、99.63%。四图stored code均非空。详见static/duplicate_strata.json/csv。按val类型分组，但查询仍允许所有train节点类型匹配。

相同局部代码也有标签冲突：重入5727/12036、AC2819/7710个val节点对应的train匹配组同时出现两类标签。这说明局部文本和程序上下文/标注范围并不等价；不能仅凭重复就宣称数据泄漏、纯记忆或标签错误。

重入buggy_18的252个共同错误中，214个能精确匹配train文本，194个只匹配到相反标签；节点2706（原源码115行的外部调用）自身原标签0，37个相同train文本全为1。AC buggy_18与buggy_26分别贡献87和42个共同错误，且多数也有相反标签匹配。
这些是“模板/标签上下文歧义影响评估”的直接观察，尚不能确定哪条ground truth正确。原作者标签一直保留，未按模型预测修正标签。

纠正与新增错误均有无DDG直接路径的案例。例如AC全部17个E0/E1分类变化节点都没有两层DDG消息路径；变化可以来自成对训练后的共享参数差异和schema改变，不能归因于节点处新增一条依赖边。完整源码、标签和N/Z/R见case_studies.md。

## 8. 已确认的原实现缺陷，本轮未修复

1. **DOT转义投影误拒绝**：scripts/DFG/projection.py:13–24、53–55以Python字符串规则解码DOT，部分合法源码转义被改变；pipeline.py:33–38随后整文件DDG回退。重入3文件、AC合约5文件（AC节点子集2文件）受影响。独立检查证明pydot对准确AST源码的序列化等于stored code，而现有code_equal为false。因此这是序列化适配缺陷，不能解释成已经证明的源文件版本不一致。
2. **if/else之间注释导致函数回退**：semantic_cfg.py:44–48的body字段收集包含comment；解析器样例加该注释得到0 facts并回退，移除注释得到3 facts。未执行solc编译验证，因此该探针只证明解析适配行为，不冒充编译合法性验收。

以上缺陷是对既有问题的独立复核，没有在本轮改变正式图或绕过回退。它们损失覆盖，但未经修复重训练，不能把全部F1差异归因于这两项。

## 9. Q7：下一步优先做什么？

当前没有证据支持立刻更换HGT或叠加模型模块。建议先分开处理“正确性”和“效果”，避免一个实验同时改标签、图与融合：

1. **最小正确性工作**：在独立版本修复上述两项确定的投影/解析适配缺陷，先以固定样例及真实受影响文件验证DDG恢复量和不变量；这不等同于扩展状态分析，也不承诺提升F1。
2. **最小数据解释工作**：对buggy_18及其相反标签train匹配片段逐条核对已有CSV/作者标签来源和完整函数上下文；保留不确定标签，不按预测改标签。随后可将模板分组或跨来源评价作为独立旁路，保持本次paper_kfold正式结果封存。
3. 在标签口径与评价问题明确后，用少量已人工核查函数验证状态余额/owner/modifier数据依赖能否覆盖目标安全语义，再决定是否扩展DDG。当前覆盖证据比“简单加更多局部参数边”更支持这一方向。
4. 融合/初始化的受控重训练应单独立项、共用同图同折，不与标注或DDG扩展同时修改。当前norm观察只构成候选解释，不构成改后必涨的保证。

本轮到此停止，没有执行以上修改或新训练。

## 10. 测试、失败记录与未执行事项

独立诊断测试覆盖N/native等价、关闭记录、Z消息归零与schema保留、无DDG无操作、异常恢复、R度数/边界/平行边、标签独立、身份对齐、归档门槛拒绝与指标独立重算。最终pytest为{tests['passed']} passed、0 failed、0 skipped、{tests['warnings']}条依赖弃用warning；完整输出见final_tests.log和final_tests.json；另有重复分层210项一致性断言。

首次pilot在模型构造前因torch1.8 CUDA未初始化时查询peak memory失败，独立诊断脚本补显式初始化顺序与回归测试；保留forward/pilot和日志，成功批次为pilot_v2。没有原生预测不一致后放宽容差。D1初稿的纯统计问题及修正也保留于static/draft_v1和diagnostic_statistics_corrections.json。
PyTorch/DGL旧版本的依赖弃用警告没有通过升级或改业务代码消除。

未执行：任何训练/优化器更新、全部last扩展、多训练seed、其他漏洞、模型/编译器下载、solc编译、原标签修订、无DDG关系删除对照、跨函数任意重连、状态或反向DDG扩展。单seed微小F1差异不作统计显著性结论。

所有新代码、日志、结果位于本诊断目录；README给出实际命令及口径。没有修改HANDOVER、training_changes、旧final_v1或正式实验配置。
"""
    with (ROOT/'diagnostic_report.md').open('x',encoding='utf8') as f:f.write(text)
    print('Written diagnostic_report.md')
if __name__=='__main__':main()
