# NS-P8a：N-C1 准备、初始化核验与封存报告

日期：2026-11-08（America/New_York）；执行与修改：Codex。依据 PROMPTS.md r27（Git b357441b）及用户批准的两项澄清。

**当前状态：准备通过、计划已封存，正式训练 0/30；等待独立训练授权。** 本批是本机 RTX3050 的 3B 教师向量先导实验。S6 的分数和是否继续 NS-P8b 均尚不可判定，不能以 NS-P7c 的逻辑回归结果替代。

## 1. 实验范围与冻结内容

N-C1 使用原名 S4（CODE＋CTX＋STATIC）增加 TEACHER，融合为 concat，仅 G3R，单个原固定 seed。30 次拟合按下表顺序执行。原图、节点、标签、分组划分、L-audit、HGT、optimizer/scheduler、epoch 上限、早停和 best 选择沿用对应 N-A 任务的实际配置，不统一改写学习率。best 按最低 inner_val loss，outer_test 仅评分；last 辅助单列。当前协议是既有分组内外层验证，不称原论文 paper_kfold 的完全同协议复现。

载体从760维扩展到1145维：CODE 256＋CTX 256＋STATIC 245＋三份存在位，另加 TEACHER 384＋存在位1。维数来自已封存 manifest/spec；没有根据本轮分数改变静态 schema。教师缺失仍保留原节点，以零向量和存在位0表达。

|执行顺序/任务|折数|载体行数（含辅助节点）|S6参数量|历史S4合计小时|历史S4最低整卡空闲MiB|
|---|---:|---:|---:|---:|---:|
|reentrancy_node|10|12223|6510180|0.527|232|
|access_control_node|10|7892|6616884|0.510|743|
|access_control_contract|5|13693|6698964|0.246|299|
|reentrancy_contract|5|18610|6682548|0.314|44|

四任务均新增848,640个参数。载体行数不是漏洞数量，也不是去重源码行数。

## 2. 初始化与历史复用

30/30 份 N-A S4/G3R 的零步初值都存在，SHA、task/fold/spec、optimizer_steps=0 和 tensor digest 全部核验。**本次没有重建 S4、没有重训 S4。** 60份对应的历史 best/last 已按用户先前清理决定缺失；本轮只读复用封存预测、指标和收据，不宣称能够重新加载这些已删除权重。

S6 只新增教师 LayerNorm/投影参数。全部原 S4 参数（包括 CODE/CTX/STATIC 适配器、HGT 和分类器）从该折真实初值逐张量复制；不能直接用 S6 spec 重新随机生成共同适配器。新教师参数沿用现有语义种子初始化。30份S6文件都为零步，保存、重载和共同参数逐位比较通过。

代码也支持文档要求的缺失初值路径：仅在原文件不存在时，用原初始化实现及原spec/8H锚点确定性重建，并强制匹配 N-A 已封存的完整 tensor digest。失败即停止；重建文件只能写入新批次目录。本轮仅对该路径做了合成回归，真实30折均走已有文件路径。

CPU准备复用4组未训练模型结构；每个任务另用 fold1 新建结构验证参数逐位相同、快路径载体与完整装配逐位相同。4份group_proof全部通过，原图指纹、节点身份、S4各模态与存在位、关系支持量均不变。没有CUDA初始化、GPU前向或optimizer step。

共同初值一致不保证相同训练轨迹：既有模态dropout种子含spec摘要，S6新增一个模态；参数数目及优化也改变。S6−S4不能全写成教师语义的纯因果贡献。

## 3. 接入代码与获批选择

新增 batch_nc1、nc1_history、nc1_init、p8a_prepare、batch_nc1_worker、batch_nc1_controller 和49项定向回归。运行核心直接引用冻结的 batch_na_worker.construct/run_core/formal_config/verify_attempt；载体采用已验证快路径。N-A/N-B入口、旧plan/seal及历史产物保持不变。

用户已批准：

1. N-A调度器硬编码240项及旧白名单，改为独立N-C1调度接入；仅调整批次准入、身份和顺序，不复制或修改训练算法。本轮先准备与封存。
2. 保留两个数值继续条件，未达时写“按预登记规则停止本机学生阶段”；不宣称学生数学上不可能更好。

原名 CODE/CTX/STATIC 不改为匿名主输入。TEACHER只引用NS-P7c已封存文本与向量；历史LLM提示层a_k映射不重新生成或扩展。教师文本不含role，但摘要/意图仍可能有误；静态不可核验而保留的教师仍按原manifest记录unverified，不能把它们写成已证实语义。

## 4. 预登记比较与停止规则

主比较只有 reentrancy_node / G3R / S6−S4 / L-audit / best outer BF1，10折双侧Wilcoxon，沿用既有zsplit等约定，本批一个检验。四任务分别报告逐折差值、等权折均值与样本标准差；best/last分开；SolidiFI与非SolidiFI分别pooled TP/FP/FN/BF1；重入32个、访问控制20个非SolidiFI正例节点按源码SHA与节点身份列出S4/S6概率。

仅读取两个预登记数值：重入节点折均BF1差、重入节点非SolidiFI pooled BF1差。任一个严格大于0则建议继续；两者均不满足则按资源规则停止本机学生阶段。缺失或非有限数值不得当作0。即使建议继续，也需下一批独立计划和授权，不自动执行NS-P8b。折间差异是固定seed的描述，不是独立seed方差；使用这些outer结果指导后续研究属于探索性决策。

## 5. 资源与执行边界

30次历史S4共约1.597小时。按历史1–2倍列出的情景范围约1.60–3.19小时，**不是S6实测、置信区间或完成承诺**；新增模态、早停轮数和显存压力都可能使其更长。S6显存峰值尚未测量；重入合约的历史44MiB余量提示可能OOM，不能由CPU准备通过推断本机一定可完成。

设备族绑定原RTX3050 Laptop 4096MiB、PyTorch 1.8.1+cu111和原TF32设置。单GPU锁、逐任务独立进程串行，local_dev_v1：启动前空闲门槛沿用原3000MiB，运行中低于100MiB只记录memory_tight；OOM/非有限值/输入/检查点错误停止，保留attempt，不降配、不切CPU、不自动重试。旧成功结果核验后复用。

准备前电源检查为插电、禁睡眠、禁休眠，未改变Windows设置；正式启动时仍须重新记录。若某任务OOM，只报告已完成部分；受影响任务的S4与S6应在未来服务器新批次一起运行，不能只把S6换设备后与本机S4配对。

**最终实验按用户安排在显存充足的服务器开展；当前限制只是本机开发资源。** 服务器另建批次并核验环境，不与本机结果混合或择优。

## 6. 验收、产物与当前停止位置

CPU准备与深度核验共约11.12分钟。三套回归：NodeSem 1239、DFG v2 2653、旧DDG/graph_utils 223，共4115通过；42条既有警告。8H只读装载、354份冻结源码核验通过；N-C1绑定375份运行源码，准备前后摘要一致。

49项新增测试覆盖任务矩阵/白名单、计划篡改、历史SHA、设备/TF32、共同初值与重建摘要、教师缺失、旧训练核心复用、授权拒绝和继续条件。开发阶段两次合成断言失败已保留在development_checks.json：不同carrier布局float32计算不能要求输出逐位相同；直接传float64载体也违反冻结float32接口。最终采用同计算的float64函数参考及明确容差核验零教师行为；生产数值设置、共同参数逐位要求和真实验收标准均未改变。这不是正式训练失败或重试。

关键产物位于 artifacts/batch_NC1_v1/：

- plan.json / plan.seal.json、authorization.template.json（false）；
- na_result_index.json（30个S4历史引用及权重缺失说明）；
- prepared/ 下4组载体、30份零步初值、逐折preparation与4份group_proof；
- preparation_audit、verification及seal、regressions、resource_estimate；
- local_artifact_index.json：大文件路径/大小/SHA。权重、NPZ、完整行manifest和运行源码副本留在WSL，Git只收紧凑计划、核验记录及索引。

计划SHA256：`a92c7577daedcc70c7c64262e8ba9cc24cfa70d88b35ed57d5ab6704f577f552`。
实际命令和授权后入口见 [NS_P8A_README.md](NS_P8A_README.md)；日志与批准记录在 artifacts/ns_p8a_checks/。本轮本地提交，不自动推送。

PROMPTS.md §5.11明确要求：“写授权模板（execution_authorized=false），停下等用户。”因此当前交付完成的是准备与封存；30次正式拟合、结果汇总与继续判定尚未执行。


## 2026-11-08 NS-P8a N-C1获授权并后台启动（修改 AI：Codex）

用户明确授权“授权训练，可以在后台训练就行”。已新建execution_decisions、execution_revision与authorization，绑定原30项plan/seal；原authorization.template=false保持不变。后台控制器PID 725002，独立WSL会话、日志重定向、单GPU锁串行；已进入重入节点G3R/S6 fold0。此处记录为启动状态，尚非30项完成或效果结论。

启动前确认插电、禁睡眠、禁休眠，GPU空闲约3391MiB；没有修改Windows电源设置。训练沿用冻结配置和零步初值，OOM等错误停止并保留attempt，不自动重试、不启动NS-P8b。进度看scripts/node_sem/artifacts/batch_NC1_v1/controller_status.json，逐项日志与收据在runs/。正式服务器实验仍另建显存充足批次，本机限制不改变本轮计算。
