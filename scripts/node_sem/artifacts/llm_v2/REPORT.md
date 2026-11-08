# NS-P7b：修正度量与模板后的第二次试点

第二次50函数试点已完成，未通过预先封存门槛。按PROMPTS r24，无论结果如何均在此停止；未执行全量生成、judge生成、教师向量编码、HGT或学生训练。第一次试点的未通过结论及全部产物保持不变。

## 1. 版本、范围和来源

基于node-sem@3c084f7ca77e7a76d85a186b39e48e91f03b9db8，先ff-only同步并阅读共享上下文§5.1、NS-P7b §5.10b和§5R审查。本轮新增llm_protocol_v2、llm_inputs_v2、llm_cache_v2、llm_post_v2、llm_pilot_v2及独立offline v2入口；旧模块不改。三份文档只追加。模型继续使用已封存Qwen2.5-Coder-3B-Instruct Q4_K_M（revision f74adce6aa16316c625447af059dbebe4983757c），后端、CUDA库和全部推理参数不变，没有安装或下载新模型。

输出位于scripts/node_sem/artifacts/llm_v2，metrics_contract.json先于旧响应重算及新生成封存；新pilot_plan和seal绑定模板、度量、源码、输入、抽样、电源及旧资产seal。第1轮不改判，事后重算与新试点分别存放。

## 2. 按文档执行的修正

两侧读写表达式统一为根标识符，下标内的变量/环境量另计读取；msg.sender与msg.value等保持不同原子。沿用冻结L3的别名关系：now→block.timestamp、msg.gas→gasleft、address(this).balance→this.balance、block.blockhash→blockhash。未知或损坏路径保留原声明，不猜成已知变量；这不是新的状态/别名分析。

external布尔作为外部调用主指标，external_call/value_transfer角色并集作辅助指标；state_update对照状态写；access_check改查本句self_condition，有已确认相等约束的析取也适用。保护后续语句的guards不再被当成本句检查；不透明条件保持unknown。忠实性仍为读/写Jaccard和external一致性的三项平均；unknown仍为null、存在位0且保守计入全部节点分母。

describe_v2逐字加入文档规则6–9，并增加共享编号的contract头，保留旧式构造函数与合约名的相同/不同关系。judge_v2删除禁止安全判断的开场冲突，登记security_note字段及包含note的教师文本公式；本轮没有运行judge或编码。规则和SHA见metrics_contract.json。

## 3. 第一次响应的事后诊断

这部分仅重算已有50份响应，不构成第一次试点通过。相同节点中36项得分上升、1项下降；涉及下标路径35项，其他成员/环境根2项。逐条旧/新集合、分量及原因在posthoc_v1/change_decomposition.json。

忠实性中位数0.6667→0.8333，≥0.5为80/123→102/123；外部调用改用bool后召回9/26→18/26，精确率仍75%，角色并集精确率72%。状态写精确率仍34/47=72.34%。原access_check的0/26使用了错误字段；本句参考下为11/21=52.38%，另5个声明为unknown，不将原0%解释为模型能力。

下降项buggy_48（重入合约，源码SHA 1eacdda7fa2de58517083454d8de92932b7a0dec0eccfa1ac3a3081c085bf887）原本错误声称写balances[msg.sender]；归一同时补入msg.sender读取后，读集合也被扣分，0.6667→0.5。这说明修正并非单向抬分。

## 4. 第二次抽样、资源与结果

抽样seed=2，LLM生成仍seed=0；50个不同源码函数；26非SolidiFI、24 SolidiFI，满足至少10个非SolidiFI正例所在函数。按去注释、等长空白替换后的原函数UTF-8字节SHA排除第一次函数；不仅跨任务排除，也排除跨文件相同函数。实际重叠0，未使用文档允许的正例不足回退；无需换seed、删难例或重抽。四任务各12/13函数，完整分层及五个完整样例（至少两个非SolidiFI正例函数）见pilot_report.json。

384个文件实例、254个唯一源码SHA、7,670个唯一源码函数仍形成4,485个唯一提示；图/facts/text来源和所有节点身份与v1相同。全体提示最长2,617 token，中位542，均小于4096；50份响应的首轮实际prompt token与预检逐一相同。

推理墙钟402.17秒，均值7.976秒/函数，JSON重试1次；输入26390、输出11190 token。启动前GPU空闲3411 MiB；该值是启动读数，不是运行峰值。GPU锁、独立后台进程和15秒心跳沿用旧入口；没有自动错误重试。

|指标|第1轮原指标|第1轮事后重算|第2轮预定指标|门槛|
|---|---:|---:|---:|---:|
|解析成功率|100.00%|100.00%|98.00%|≥95%|
|忠实性中位数|0.6667|0.8333|1.0000|≥0.7|
|全部节点忠实性≥0.5|65.04%|82.93%|70.00%|≥80%|
|描述黑名单比例|1.63%|1.63%|4.00%|≤5%|
|外部调用精确率|75.00%（单role）|75.00%（bool）|66.67%（bool）|≥80%|
|状态写精确率|72.34%|72.34%|70.00%|≥80%|

第2轮未通过项：faithfulness_ge_half、external_call、state_update。两轮样本不同且模板不同，跨轮差异不能当作配对提升或单独的模板因果效应。

|角色指标|精确率|召回率|可核验声称数|unknown声称数|
|---|---:|---:|---:|---:|
|external_call|66.67%|77.78%|21|0|
|external_role|72.22%|72.22%|18|0|
|state_update|70.00%|97.67%|60|3|
|access_check|36.67%|100.00%|30|4|

|语料层|目标节点|可核验|忠实性中位数|有效描述|
|---|---:|---:|---:|---:|
|solidifi|76|58|1.0000|55|
|non_solidifi|74|56|0.8333|50|

所有指标针对冻结静态参考，而非人工完整语义真值；真实模型遗漏、根变量抽象、分析unknown和一行多个HCG节点的限制分别保留。分层与新/重叠样本单独统计，未用有效描述过滤来缩小门槛分母。

本次35个目标的静态读写事实不可核验：32个DFG unknown、3个facts.node_kind=other而读写组不适用；另有1个模型漏行，所以实际取得忠实性分数114/150。仅由静态参考决定的理论最高比例为115/150=76.67%，已低于80%门槛。这是当前固定样本与保守unknown规则的可达到性限制；更大LLM本身不能消除静态unknown。本轮不删样本、不改门槛、不改判。下一批应先经用户确认如何分别衡量可核验覆盖与有参考时的描述质量，再封存新的规则。

具体错误：to.call.value(amount); 只是调用配置而未执行后续调用，模型仍描述为转账（如重入buggy_18/25/45）；return true、return a - b及uint free = 1等被标为state_update；throw被声明为外部调用。完整节点、源码SHA、原句、模型输出和参考事实见pilot_report/error_evidence.json，共7个可核验external误报、18个state_update误报、9个低于0.5的节点（类别可重叠）。这些错误与静态unknown分别统计。

另1个接口声明函数（重入合约buggy_23，源码SHA 0ea2e8d84a5c1f18db073809e603c2c5743af4f0f139dd613c168982b339fa56）没有目标语句，模型两次都耗尽2048输出token而JSON不完整，按规则记parse_failed，无第三次重试。该项耗时约149.29秒，已纳入总耗时和98%解析成功率；约9.94小时的全量粗略外推因少量长尾而不稳定。

## 5. 独立思考与后续边界

发现文档规则8的最后一句“同合约函数调用不是外部调用”过宽：this.f()仍是外部消息调用。全量候选有2个此类提示，本次固定50函数中0个；本轮按要求保留已登记逐字模板，将该边界记录为未来全量前需确认的修正，不临时改模板。函数提示也不能提供完整继承/被调函数/类型定义，模型输出只能按现有上下文审查。

第二次仍未通过；本机不继续调整模板或更换样本。建议下一阶段在服务器上评估更大的代码模型，并先确认模板与静态参考的剩余边界；须另建计划，不能覆盖本批。

最终正式实验按用户安排将在显存充足的服务器运行并另建批次；当前RTX3050 4GiB只限制本机开发。此次未通过时，应与语义门槛及样本证据联系，不能归因于未发生的OOM，也不能据此认定DFG或LLM整条路线无效。

## 6. 测试与验收

4033通过、0失败、0跳过；42条既有弃用警告。NodeSem 1157，DFG v2 2653，原DDG/graph_utils 223。新测试40项包含路径正反例、角色双指标、自身检查与受保护语句区别、旧式构造函数名、改名/标签扰动、分段、重试和缓存篡改、抽样重叠限制。

8H只读load通过、354份冻结源码SHA一致；旧llm_v1的256份产物及9个实现文件逐一哈希不变。输入身份核验通过；旧plan/seal/报告未改。中文doc_check对新报告及三份文档追加部分强制expect-cjk。

~~~bash
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

真实输入命令见inputs_execution.json；GPU命令、独立CUDA库路径和PID见launch.json；计划pilot_plan.json、模板/度量metrics_contract.json、旧响应重算posthoc_v1/、新结果pilot_report/、逐节点CSV与验收记录finalization/。目录排他创建，不原样重复运行；这不是全量授权。

Git仅保存新增代码、模板、计划、报告、紧凑结果和SHA索引；模型、运行库、安装包、完整提示和响应缓存继续留在WSL。未进入NS-P8，本轮不push。
