# NS-P7c：当前3B模型全量描述、无role教师向量与必要诊断

access_control_contract 岭回归余弦 0.8790 / 同类型均值 0.8181；access_control_node 岭回归余弦 0.8772 / 同类型均值 0.8298；reentrancy_contract 岭回归余弦 0.8784 / 同类型均值 0.8162；reentrancy_node 岭回归余弦 0.8854 / 同类型均值 0.8254。access_control_node STATIC+TEACHER−STATIC：BF1 1.4815pp，AUC 0.0730；reentrancy_node STATIC+TEACHER−STATIC：BF1 2.7143pp，AUC -0.0196。两次50函数试点均未通过；本次全量运行是用户在知情后按PROMPTS r26作出的决定，不改写旧结论。

## 1. 范围与实际改动

基于node-sem@05bff064d991ed2c8a8f4f30f1b8006f26a08d34，读取最新共享上下文及NS-P7c。使用原describe_v2、Qwen2.5-Coder-3B-Instruct Q4_K_M及已封存参数，未更换模型或下载新权重；不运行judge、不训练HGT或学生。本轮CPU岭回归和逻辑回归拟合只用于诊断。
新增llm_full、offline/llm_full调度，llm_teacher后处理，teacher_vectors、offline/teacher_encode，teacher_diagnostics、p7c_diagnostics、p7c_report和必要测试。旧模板、LLM试点、DFG、HGT、图、标签、特征与划分保持不变。

## 2. 全量生成与教师覆盖

4,485个唯一提示逐个有收据；无函数体且无语句目标的单元跳过，有函数体但无目标仍生成函数意图。重入节点优先；历史同模板响应按SHA只读复用。后台进程独立于对话与网络，15秒心跳，整体解析失败率按已完成推理单元计算、排除跳过项；超过5%停止。其他执行或输入完整性错误也停止，不自动重试。
最终单元状态：{"ok": 4197, "parse_failed": 4, "skipped_no_body": 284}。本轮生成阶段墙钟 7.45 小时。
教师只编码summary与function_intent，不把role字段拼入文本；这只适用于当前3B模型。静态参考未知但描述有效的节点保留并标unverified，已核验忠实性<0.5或黑名单描述仍缺失。unverified不代表已证明正确；自由摘要与函数意图没有被读写集合检查完整验证。

|任务|全部行|教师存在|旧规则存在|unverified语句|可核验语句中≥0.5|
|---|---:|---:|---:|---:|---:|
|access_control_contract|13693|10232|8927|1454|91.0299%|
|access_control_node|7892|6140|5660|588|92.9195%|
|reentrancy_contract|18610|12397|11404|1134|90.1062%|
|reentrancy_node|12223|7918|7533|493|90.9839%|

解析、黑名单、忠实性、unverified与role精确率/召回率的SolidiFI/非SolidiFI分层详见finalization/quality.json；本轮不以role质量作为继续生成的门槛。去掉role字段不能保证自然语言summary不再包含相同的错误判断。

## 3. 编码与载体

复用已登记BAAI/bge-small-en-v1.5（revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a），本地加载、冻结、384维、归一化，两遍编码逐位一致。每任务F3全集按身份和顺序对应，缺失写零向量＋存在位0；G0/G3R共用该模态。TEACHER在原FeatureSpec白名单已存在，本轮验证384＋1布局，不新增训练配置。

## 4. 两项诊断与解释边界

全部30折逐任务报告；岭回归仅在教师/CTX/STATIC存在的节点拟合，标准化与拟合只用inner_train，inner_val平均余弦选择alpha={0.01,0.1,1,10}，outer_test仅评分。同类型均值只用inner_train；训练未见节点类型单列不可估，同时给出共同可估节点上的岭回归结果。
非SolidiFI信号只用原语句/条件节点集合，两个特征对照样本一致；教师缺失用零向量及存在位表示，不删除困难节点。C={0.01,0.1,1,10}、seed1及逻辑回归算法沿用NS-P6c2，inner_val选C和阈值；空或单类别划分按原规则不可估。合约任务没有相应节点标签终点，因此仅做可重建性诊断。
|任务|岭回归余弦|同类型均值余弦|共同可估节点岭回归余弦|未见类型节点|
|---|---:|---:|---:|---:|
|access_control_contract|0.8790|0.8181|0.8790|1|
|access_control_node|0.8772|0.8298|0.8773|4|
|reentrancy_contract|0.8784|0.8162|0.8784|1|
|reentrancy_node|0.8854|0.8254|0.8855|1|

|任务|STATIC BF1|STATIC+TEACHER BF1|差值pp|STATIC AUC|STATIC+TEACHER AUC|BF1/AUC可估折|
|---|---:|---:|---:|---:|---:|---:|
|access_control_node|5.5556|7.0370|1.4815|0.5718|0.6448|9/8|
|reentrancy_node|88.2381|90.9524|2.7143|0.9943|0.9747|10/10|

以上为等权可估折均值，完整逐折、缺失与配对差值在finalization/results.json、folds.csv。它们是冻结划分上的描述性CPU诊断，不是HGT收益或新增独立数据集的泛化证明。高余弦说明线性可预测程度高，不能严格推出学生不可能改善下游优化；高均值基线也提示嵌入共性方向的影响。

## 5. 实施选择、失败与限制

用户批准两项接入澄清：(1)旧NS-P6c2没有岭回归网格，本轮预先固定alpha和无泄漏规则；(2)carrier要求每份manifest唯一task_id，故teacher/<task>/teacher.npz逐任务保存并提供总索引，未修改载体。
封存前第一次准备因构造函数/modifier片段脱离合约上下文解析失败；保留llm_v3_setup_attempt1/failure.json，尚未加载模型或生成响应。只在判断函数体时增加语法容器，真实提示字节不变；1,064个该类函数实例在容器中均可解析，修复后完成准备。
保留describe_v2第8条this.f()已知边界、external只能布尔导致unknown表达受限、单角色和根变量抽象限制；按本轮明确要求不改模板。函数意图和摘要仍可能错误，移除role并不等于解决全部语义错误。
最终实验将在显存充足的服务器另建批次；本机RTX3050 4GiB只限制当前开发。本轮不自动更换更大模型、不自动进入NS-P8a。

## 6. 测试与实际命令

测试：4066通过。各套日志摘要：["1190 passed, 4 warnings in 22.57s", "2653 passed, 9 warnings in 172.59s (0:02:52)", "223 passed, 29 warnings in 3.71s"]。
旧实验记录SHA核验数量：504；8H只读装载与冻结源码核验通过，详见frozen_audit.json。模型/后端继续按原资产seal核验。

~~~bash
python -B -m scripts.node_sem.llm_full prepare
python -B -m scripts.node_sem.llm_full seal
python -s -B scripts/node_sem/offline/llm_full.py --out scripts/node_sem/artifacts/llm_v3
python -B -m scripts.node_sem.llm_teacher --out scripts/node_sem/artifacts/llm_v3
python -s -B scripts/node_sem/offline/teacher_encode.py --out scripts/node_sem/artifacts/llm_v3
python -B -m scripts.node_sem.p7c_diagnostics prepare
python -B -m scripts.node_sem.p7c_diagnostics run
~~~

实际解释器、环境、PID和命令见launch.json与后续阶段执行记录；已存在目录拒绝覆盖，以上不是可原地重复执行的命令。Git仅归档代码、计划、报告、紧凑统计和SHA索引；权重、完整响应、向量留在WSL。
