# EdgeSem EP0 侦察报告（Codex）

日期：2026-11-10。依据 PROMPTS r3，共享上下文 §4.1 与 EP0 §4.2；实际 HEAD ce8fa93a3b795f9daff1e64ca0363be0b8c09129。
本轮完成输入核验、四任务语义/边统计和三项 CPU 探针。正式训练 0、optimizer step 0、GPU 运行 0；不生成 F4、边特征或生产模型。EP0 完成不等于后续方案已全部验收。
所有机器证据在 recon.json 与 artifacts/ep0_v1/；路径均从已核验的历史 manifest/plan 取得。侦察探针未加载历史 pt 权重；回归测试保留既有合成序列化用例。

## 1. 输入身份与历史配置

8H plan SHA：cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c；plan.seal SHA：bd43c31ed0bec7a013524d088220378ca23bbf202e72917a18a8bcbdfbfa79fb。
图 store SHA：ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4；store.seal SHA：c12cb77c0e4e311e0ac7410e268c50ab5f82c203c1a69ebbf7075f48a7943bde。
inputs.json 逐项保存四任务 F0/F3、源码、L1–L3 证据、匿名特征 manifest/NPZ、分组折、label_view、零步准备 manifest 与历史 G3R 收据；全部实际使用文件先做 SHA 校验。匿名输入仅用于核验历史 8H 接入，不替用户批准新的主视图。
历史节点配置：initial_lr=0.0002、max_lr=0.005、div_factor=25；合约：0.0005、0.01、20。其余逐项见 inputs.json：50/50 schedule/max epoch、patience7、delta0.001、hidden128、2层、8头、shared_projection、mean。按各任务实际配置核验，不把段落简写作为配置来源。

| 任务 | 实际完成轮数（各折，1基计数） | best轮（1基） |
|---|---|---|
|access_control_contract|[15, 13, 15, 14, 15]|[8, 6, 8, 7, 8]|
|access_control_node|[24, 22, 37, 28, 19, 20, 19, 21, 19, 20]|[18, 22, 32, 28, 13, 13, 12, 21, 17, 13]|
|reentrancy_contract|[23, 15, 15, 16, 15]|[17, 8, 8, 9, 8]|
|reentrancy_node|[28, 25, 23, 22, 22, 26, 22, 25, 23, 23]|[21, 18, 17, 15, 15, 19, 16, 18, 17, 16]|

best/last 原字段为0基索引。读取收据、final_result/history/effective_config并核对哈希与轮数，未读取预测来选型。P2新增轮数可以由50减已完成轮数估算，但这不是实际服务器耗时预测。

## 2. 边类型、方向和参数量

| 任务 | 存储canonical | G3R merge | typed | 每层新增参数 | <20边的typed关系 |
|---|---:|---:|---:|---:|---:|
|access_control_contract|122|235|244|36936|110|
|access_control_node|117|225|234|36936|114|
|reentrancy_contract|123|233|246|53352|102|
|reentrancy_node|110|212|220|32832|94|

各任务 JSON 逐项列出反射前、基础反射后、G3R 和 typed 的canonical及边数；同类型合并、反向键撞已有正向键另列。typed 只在探针内存生成，不修改存储图。参数差为 ΔR×(2×8×16²+8)，两层骨干差为该数的2倍；稀疏关系不共享、不删除。

## 3. CFG、回边与投影

| 任务 | 有函数体总数 | CFG/支配支持 | 有限退出路径后支配全覆盖 | 语义回边 | 对应next_line | cf_back |
|---|---:|---:|---:|---:|---:|---|
|access_control_contract|3306|2943|2943|34|32|不启用|
|access_control_node|2019|1918|1918|31|29|不启用|
|reentrancy_contract|3569|3297|3297|26|26|不启用|
|reentrancy_node|2101|2018|2018|26|26|不启用|

复用 FileCFG 的 legacy CFGBuilder→V2CFGBuilder 路径及版本元数据；原因是它与已封存 L1 及 NodeSem 使用同一事件锚点。保留全部 CFG 块，从入口求支配；仅由目标支配源识别自然回边。投影只跨越无事件块寻找最近事件，再按精确AST锚点对应 HCG，最终只统计原图已存在的 next_line。没有用源码行号判断回边。
后支配以可达的真实出口连接分析用虚拟出口计算；只覆盖可达出口的有限退出路径，不宣称证明所有执行都会终止。不可支持函数、缺失事件锚点、未投影AST语句逐文件记录。所有任务可修改的next_line回边均少于50，按既定规则禁用cf_back。
匿名源码未另行写入文件，复用8G封存替换记录在内存重建。直接配原code文本的图会被Projector拒绝；复用既有node_code_view只调整临时副本code后，384/384任务文件的AST ID→原图节点映射完全一致。此处不是新增匿名实验或完整边语义不变性验收。

## 4. 新关系可行性（只计数）

| 任务 | MOD_APPLY候选/绑定/图端点 | CALL_SITE唯一绑定/图端点 | GUARDS记录/可映射/去重边 |
|---|---|---|---|
|access_control_contract|551/528/527|512/510|8165/6767/6701|
|access_control_node|204/195/195|188/186|4537/3822/3787|
|reentrancy_contract|566/549/549|488/486|10274/8928/8828|
|reentrancy_node|187/178/178|182/180|6956/6340/6305|

每类含REV的预计边数是去重正向边数×2；按canonical明细见各任务 prospective_relations。MOD_APPLY的绑定计数与GuardAnalyzer.audit分别记录：前者仅定义身份绑定，后者还检查占位符/参数/守卫，不能混成一个成功标准。
CALL_SITE全量表达式先区分内置函数、事件、类型转换、库、成员调用，再报告内部函数解析；最初粗扫的unknown含require等内置调用，最终分母以call_classification.json为准。两个节点任务分别有13个重载、3个super调用未解析；不能把180/182、186/188的条件投影率称为完整内部调用召回率。
GUARDS按kind和每语句数量完整分布见JSON。重入节点modifier 616条、访问控制715条，当前均0映射；实际_anchor是modifier_invocation。普通守卫的可映射记录不能弥补modifier源端缺失。预计GUARDS规模只包含当前可映射集合，不代表设计中的modifier连边已完成。

## 5. 73位属性来源

recon.json.attribute_slots逐位列出来源、状态和限制；attribute_sources.json给出四任务事实字段、实际枚举和L1证据键。
- L1没有strong/weak更新标记，第15位按模板保持0；这不等于证明每条边都是strong update。
- dfg变量kind实际含local、parameter、return；模板的四类未规定return。对象仅有var/kind/from_offset，没有类型字段。
- state.writes.shape是integer/address/mapping/array/struct_contract等声明类型，不能直接当成scalar/mapping/array/struct_member访问方式。syntax也没有直接表达所有decl/param/incdec区别。
- READS_STATE源端是状态声明，不能直接当作函数内def去检查跨调用路径；适用性需要明确。
- env_source值及每文件数量已逐项记录；pragma按冻结interval解析，缺失或不支持记unknown，不猜编译器版本。
- 图DOT label中的AST身份仅供Projector精确对齐，不使用漏洞标签决定关系；CPU B监督损失单独读取冻结L-audit标签。

## 6. CPU接入探针

A：重入节点fold0，新鲜G3R锚模型；原样重建DGL图/层并复制全部参数，state digest一致、eval前向逐位一致，最大绝对差0。
B：typed模型220个canonical、参数5176676，冻结inner_train 8518个节点仅做一次交叉熵backward；optimizer step=0。所有复制关系行逐位相同，有限前后向和冻结gradient_audit通过。无训练支持关系保留并按0梯度处理。
B的浅层schema/梯度检查通过不意味着checkpoint通过：dfg_profile=G3R时深验报Graph/schema mismatch；G3R-T时报Unknown DFG v2 profile。旧checkpoint.validate_binding先比较task/profile/reducer/layer_impl，再调用冻结runtime_model.validate_registration并核对canonical、辅助节点、initial SHA、配置和graph/folds/labels/label_view/feature_view/feature_npz文件引用。必须提供独立的EdgeSem绑定适配，不能改旧白名单或伪装G0P。
C：同文件随机端点仅模拟当前可映射G4R规模：274个canonical、60732条有向边、5619908参数。CPU train-mode前向（保留autograd）2.216秒；前向前RSS 1469.62MiB，采样峰值 2878.14MiB，增量 1408.51MiB，进程高水位 2886.52MiB。
C不包含尚无法映射的modifier守卫、未来边属性激活、backward或Adam状态；随机新关系使用普通构造器初值，只作内存估计，不作为r3初始化验收或预测成绩。CPU RSS不能换算成GPU显存；正式GPU探针仍在EP7。
接入函数逐行范围和文件SHA见recon.json.interfaces；未用monkeypatch修改任何冻结入口。

## 7. 需要后续决策的差异

- **D-01 EP3 blocker**：Modifier _anchor is modifier_invocation, not the guard statement in its body; all modifier records unmapped. Later add an EdgeSem-local read-only provenance resolver using frozen binding/guard logic; do not edit NodeSem. Requires approval before implementation.
- **D-02 EP1/checkpoint integration blocker**：Existing checkpoint.validate_binding imports frozen runtime registration; neither G3R nor G3R-T can pass typed deep validation. An EdgeSem-local binding adapter must dispatch to its own registration. A profile string alone is insufficient. No bypass implemented.
- **D-03 EP4 source/schema blocker**：L1 kind includes return; variable facts lack declaration type; state.writes.shape describes root declaration type rather than scalar/member access. Decide return-kind mapping and exact declaration/access joins before attribute implementation; do not silently coerce or broaden schemas.
- **D-04 EP4 applicability clarification**：READS_STATE starts at a state declaration; intra-function def-to-use path is not directly defined for that source. Specify applicability/unknown handling for cross-call attribute on READS_STATE; do not invent a reaching definition.
- **D-05 EP5 integration prerequisite**：Renamed source cannot be checked against unchanged original code text by Projector. Reuse existing temporary node_code_view for parity only; all 384 task/file identities pass; formal graph stays original.
- **D-06 documentation**：Section 1.4 gives contract LR values; node tasks use initial_lr=.0002/max_lr=.005/div_factor=25. Bind future execution to task-specific sealed configuration; r3 introduction already acknowledges node max_lr.

本轮保留这些差异，不自行修正PROMPTS或冻结分析器，不进入EP1。D1主视图、D2训练协议、D3七类冻结规则也仍待用户确认；EP0结果不能充当训练授权。

## 8. 执行、回归与边界

命令均在mando、CUDA_VISIBLE_DEVICES=''、PYTHONDONTWRITEBYTECODE=1、OMP/MKL=2下运行。每个execution/*.started.json记录实际命令，*.json记录退出码/耗时/log SHA。
顺序：python -B -m scripts.edge_sem.recon.inventory；semantic --task <四任务>；attributes；calls；model_probe --probe A/B/C；随后pytest三套目录与doc_check。输出排他创建，不覆盖成功产物。
开发接入错误均保留：首次STATEMENTS导入位置、run包装器的--分隔符、辅助节点空dfg组、mando缺少psutil（改用Linux/proc，无依赖安装）、split含元数据不能当三路列表。只修正新侦察脚本，无生产训练失败/自动重试；成功探针不重复执行。
验证结果与冻结源码/文档前缀验收见artifacts/ep0_v1/verification.json；脚本与报告在本地提交，不自动推送。
最终实验将在显存充足服务器上另建批次；RTX3050 4GiB仅是本机开发限制。服务器尚未在本轮部署/验收，不混合本机与服务器结果。
