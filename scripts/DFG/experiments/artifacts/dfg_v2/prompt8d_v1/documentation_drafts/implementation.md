# Prompt 8D 实施记录草稿（最终推断汇总完成前不作为完成报告）

日期：2026-10-29；实施与核验：Codex。起点 dfg-v2 @ dd70fb966b64df43ac9e75a6f94f0b675fcaa593。读取更新后的 §4.1/Prompt8D，git pull --ff-only 已同步；未切换、重置或迁移历史实验。

## 范围和保留项

新增分析位于 diagnostics8d/，新分组基准准备位于 benchmark_v2/，测试位于现有 v2/tests。旧DDG、HGT、tokenizer、原训练器与冻结150项实验均不改。8D产物在独立 prompt8d_v1/，旧8C和失败开发尝试保留。没有新增依赖安装、编译器下载、外部数据上传。

diagnostics8d：__init__.py、renaming.py、prepared.py、inference.py、inference_batch.py、inference_summary.py、stratification.py、line_provenance.py、keyword_baselines.py、README.md。
benchmark_v2：__init__.py、feature_view.py、grouping.py、prepare.py、equivalence.py、README.md。
新增7组test_prompt8d_*测试：readonly、renaming、inference、summary、grouping_plan、benchmark_feature、equivalence。

inference.py只复制调整原8C前向的输入视图装配，头部绑定原文件SHA；继续调用原make_model、restore_checkpoint、DfgV2Supervision、eval/no_grad。原模型数学与512维inside_token配方不变。当前特征是浮点存储的tokenizer ID序列，不是CodeT5隐藏状态。

## 用户批准的调整与依据

原C要求普通名称与全部标记名称等量、同token长度；80个SolidiFI文件实例均无法满足。用户批准保留B_full100次，另做B_matched100和C_matched100，共300次推断。匹配按文件内唯一名称数量和孤立名称token长度直方图；不把出现频率、修改节点数量说成已匹配。10个AC文件无可匹配名称，仍以恒等映射保留。

未增加新模型、关系、标签修正或正式训练。F仍停在用户选择标签策略、seed集合和本机/服务器的位置。用户先前最终服务器显存充足的安排已记录；本机RTX3050 4GiB只是当前开发限制，尚未核验服务器环境，禁止混合两地成绩。

## 逐节点改名验收

候选词表固定、确定性生成；检查原源码全部名称碰撞。普通对照名称要求AST可识别的用户声明并排除关键字、内建/全局名及标记名称。字符串和注释不改。
除了孤立标识符token数，还核验每个完整节点文本的未截断长度、每个编辑位置的token区间，以及编辑区间外全部token ID。之后按冻结规则截断/填充512。prepared视图封存源码SHA、文件/节点身份、原/新code和向量摘要、位置证据；每次worker重新核对映射及预期改名节点集合。

80文件共18082个SolidiFI节点。全量标记名称R2585、AC2222；匹配每侧R100、AC146。B_full修改代码节点R5678/AC2328；B_matched310/224；C_matched845/393。两侧修改节点和词法出现数量不同，必须与分数一起解释。
独立CPU审计重新编码6视图的9778条修改文本记录，所有未截断位置与512向量完全一致。部分修改在512之后：R三视图分别1/8/15条、AC1/1/11条文本改变但向量不变，计入代码修改、不计入特征修改。

## 执行、绑定和失败策略

新执行plan/seal绑定原计划、原150结果验收、原8C门槛、本次GPU恒等门槛、准备视图、用户批准和4个worker源码SHA。固定300任务，单GPU进程串行，每个任务独立进程，错误停止、不自动重试、不切CPU；失败日志不能当作成功复用。

每个worker只替换outer_test文件的输入行，其他特征、原NX属性、全部基础/新增边和模型权重保持。保存原/新概率与argmax，身份按task/fold/file/source SHA/original node ID。最终汇总拒绝缺失、重复、错位、错误收据、过期代码、错图/初值/标签/特征；额外核验当前环境门槛与实际checkpoint/state。该校验只强化证据，不重新跑模型。

原8C的idN、B_full和两匹配子集使用同一已训练best checkpoint；不是中性输入重新训练后的成绩。B_full与idN同时改变替代词token值及位移，不能把差值全部定量归于位移。匹配对照也不能消除词频、语义角色和修改节点暴露的差异。

## F：只准备分组基准

256源码身份合并为227个已知近重复/精确重复连通组，保留单例与全部文件。
R合约142文件124组/5折，R节点71文件57组/10折；
AC合约114文件107组/5折，AC节点57文件52组/10折。
30个外层折及各自inner train/val均按组隔离；每文件恰好一次outer，合约各部分均有两个类。分组优先于精确分层，不换seed挑结果。已知文本克隆隔离不等于消除了所有注入模板或语义重复；完整固定任务图前向仍是transductive。

新idN特征视图覆盖全部训练/验证/测试原HCG节点，51490行全部独立重新编码一致；env_source和非SolidiFI保持原输入。40次原/中性视图模型装配核验保持节点/顺序/边/非token属性。原磁盘图不改，只在深复制的图上绑定独立token视图。

L-orig使用冻结作者target。L-audit使用C1 target并将C2排除节点从loss和主评分掩蔽，不删除图节点，不把排除项改成负例。两策略都另报全体原HCG节点的orig辅助分数；合约标签不变。C1/C2仍为诊断假设，不应宣称为确证真值。

170任务=5剖面×30折+G0P×20节点折，默认建议seed1；execution_authorized=false，实际label/seed/location均null。初值须在后续授权执行计划中重新封存，不能复用旧训练权重。配置逐任务沿用实际LR/Adam/OneCycle/50轮/patience7/delta0.001/最低inner_val loss选best，last独立。G0P采用原8C零边分母设计，不新增env_source。
既有训练CLI尚未支持这个完整新计划；未来需要明确feature/label/split/G0P接入测试，不能现在声称已有可执行170训练命令。

## 数值等价性与开发记录

F特征接入验收使用原G0和恒等视图各1个CPU epoch，共2个optimizer更新、0正式fit。前向、loss、参数、Adam、scheduler数值与best/last评分逐位相同。train loss=0.6978223323822021，inner val loss=0.6693451404571533。
第一次报告只因反序列化scheduler bound-method实例地址不同判失败；原报告保留。新checker核对实际__func__身份及全部数值字段，用保存checkpoint复核通过，额外更新0，未放宽数值容差、未重训。

A初次有38个synthetic else-if节点归属未解析；复用原CFG的return_if_root构造规则补齐准确AST身份，不按最近行猜映射。最终19746节点全部归属可解释。
renaming预检v1-v5均保留：缺少下划线候选；遗漏transfer排除测试；空格前缀token签名；任务feature描述字典差异；长文候选检查性能问题。固定候选库/明确排除/按实际tokenizer配方/安全前缀签名缓存修正后v6全80通过；最终节点全文校验从未放宽，没有正式GPU失败重试。
最终summary额外绑定当前GPU恒等门槛，17项针对篡改的回归通过。2643唯一测试通过（2420v2+223旧），0失败/错误/跳过，8/29条既有DGL/NetworkX弃用警告。第一次2403v2通过记录保留，不重复累计。

## 资源和未执行事项

历史本机任务中位耗时对应新170任务约8.2791小时，仅计划参考，另需编排、验收和早停变化余量。服务器硬件未指定，1x/2x/4x只是8.279/4.140/2.070小时的条件情景，并非实测预测。
不执行170正式fit、不加seed、不扩展其余5类、不新增关系、不改标签、不运行新的solc验证，不声称完整DDG语义或真实泛化已证明。既有512/111条人工依赖审查未在本轮补齐。
