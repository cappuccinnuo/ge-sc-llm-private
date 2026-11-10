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


## 9. EP0b：修饰器来源与调用覆盖复核（Codex，2026-11-10）

依据PROMPTS r4，输入HEAD 0ddbb07e。旧EP0输入与产物保留，新增ep0b_v1。最终口径是summary.json与calls_refined_*；首轮calls_*和修订源码均保留。只解析和计数，不建图、不训练。

### 9.1 修饰器内层来源

guard_source.py复现冻结_modifiers的绑定/过滤步骤，调用_scope/_bindings/_lexical/_require/_guard。所需list接口返回record、invocation、inner_anchor；辅助inspect_modifier_guards返回unresolved/audit供验收，不修改冻结audit或modifier cache。文件头注明来源行范围与SHA。

四任务共12285个函数实例（含无体声明）逐函数记录序列、顺序、unresolved与audit增量完全一致。按for_node保护语句扩展：

|任务|函数实例|modifier记录映射|去重modifier边|非modifier边|合计正向GUARDS|含REV预计|
|---|---:|---:|---:|---:|---:|---:|
|reentrancy_node|2283|616/616|616|6305|6921|13842|
|access_control_node|2206|715/715|715|3787|4502|9004|
|reentrancy_contract|4035|1346/1346|1344|8828|10172|20344|
|access_control_contract|3761|1398/1398|1397|6701|8098|16196|

inner_anchor映射率均100%，无映射失败。按修饰器独立anchor、应用记录和预计边数见modifier_mapping_summary.json；每语句入边分布（含0）见summary.json.guards，两节点任务最多13条。记录数与去重边数分开；原多placeholder、缺失绑定、参数不符等仍回退，不扩大语义覆盖。

### 9.2 CALL_SITE覆盖与停止门槛

逐条核对HCG多重边(f,g,key)，仅当存在EP0原口径的(s→g)且s精确归f，才判覆盖。函数级多重边、去重函数对、调用表达式与语句级边的数量不能直接相减。

|任务|internal_call边|覆盖|原覆盖率|无表达式排除|调整后覆盖率|80%门槛|
|---|---:|---:|---:|---:|---:|---|
|reentrancy_node|464|178|38.36%|76|178/388 = 45.88%|不通过|
|access_control_node|591|197|33.33%|76|197/515 = 38.25%|不通过|

未覆盖internal_call逐类计数；代表性文件、行号、表达式仅在artifacts，不进入正文：

|类别|重入节点|访问控制节点|
|---|---:|---:|
|重载|18|18|
|super|2|2|
|modifier端点|10|8|
|库/using|38|27|
|未找到对应表达式|76|76|
|同名候选对应多个声明|75|150|
|状态变量初始化|0|0|
|modifier调用参数|0|0|
|其他|67|113|

同名表达式仅定位缺口，不证明绑定到HCG目标；尤其外部成员调用的同名也可能属于其他对象。不确定项保留分母。冻结AST会把一元/二元上下文包进callee；首轮误列无表达式的重入66条、访问控制55条（含external_call）经冻结_postfix定位后改列其他，其中internal_call为30/31条。覆盖布尔与EP0候选完全不变，修订SHA和逐条变化见revisions与call_category_changes.json。

external_call仅单列：重入7/707、访问控制6/688对应EP0候选，其余主要为库或外部成员调用，超出当前内部调用子集，不作为内部调用门槛。internal_call去重函数对为396/530，覆盖146/164；EP0语句级去重边180/186。并行边与多个语句调用同一函数导致计数不同。

**CALL_SITE预登记门槛未通过，停下报告，不自动进入EP1/EP2。** 这衡量当前受限子集与作者HCG的对应覆盖，不是真实内部调用召回率。不能删掉库、super或unknown凑到80%；无表达式也不代表已证明作者图错误。建议先审查范围排除、可唯一绑定但AST形状不支持的调用，以及HCG对应争议，再决定EP2修订；本轮只提出，不实施，不改门槛。

### 9.3 r4属性来源可行性

分母是已有数据边的变量证据，一条边可有多条证据。L1变量由完整symbol身份查冻结声明表取得，再按r4在目标语句匹配标识符并root_binding；L2用封存变量名，WRITES_STATE在源语句解析。缺失或任一未解析匹配保持unknown，不猜类型。

|任务|关系|类型可解析|成功率|多声明|
|---|---|---:|---:|---:|
|reentrancy_node|DATA_DEF_USE|4150/4200|98.81%|0|
|reentrancy_node|READS_STATE|3042/3187|95.45%|0|
|reentrancy_node|WRITES_STATE|2142/2254|95.03%|0|
|access_control_node|DATA_DEF_USE|5118/5168|99.03%|0|
|access_control_node|READS_STATE|1105/1185|93.25%|0|
|access_control_node|WRITES_STATE|687/767|89.57%|0|

|任务|decl_or_param|assign|compound|incdec_or_delete|unknown|
|---|---:|---:|---:|---:|---:|
|reentrancy_node|3770|263|73|47|47|
|access_control_node|4857|200|7|55|49|

def_kind未知为47/4200（1.12%）、49/5168（0.95%）；唯一“定义节点+变量”另报，避免高扇出重复计数。

|任务|write_access plain|indexed|member|other/unknown|
|---|---:|---:|---:|---:|
|reentrancy_node|1036|972|246|0|
|access_control_node|352|277|138|0|

写操作按token：重入assign/increase/decrease/other=1783/236/209/26，访问控制680/36/36/15；x = x + 1保持assign，其他复合算符不猜increase/decrease。真实两任务shape_safe差异类型集合均为空；addressBook等反例测试通过，本批没有实际类型分类变化。全部类型名及逐条证据见attributes_*；没有生成73维向量。

### 9.4 验收与边界

CPU测试EdgeSem34、NodeSem1353、DFG v2 2653，共4040通过。实际命令、环境、耗时、退出码与日志SHA见execution。verification.json核对冻结源码、_code_refs、8H归档加载、输入/EP0产物和四文档旧字节前缀。没有HGT训练、GPU运行、历史模型权重加载、新图或属性向量。

最终实验在显存充足服务器另建批次，RTX3050 4GiB只是本机开发条件；本轮未部署/验收服务器。主视图D1、P2等决定未被本次只读任务批准。


## 10. EP0c：调用解析与类型参照集（Codex，2026-11-10）

依据 PROMPTS r5 §4.1/4.2c，起始 edge-sem@8b5463e6；快进同步返回 Already up to date。独立产物为 artifacts/ep0c_v1，旧 EP0/EP0b 原样保留。本轮实现 call_resolve.py 和只读测量，不建 F4、不生成边属性、不启动训练。

### 10.1 解析规则与验收边界

先使用冻结 AstSemantics.resolve_callable；唯一同文件目标按定义所在合约分为 internal、inherited、library。新增裸标识符同名重载的参数个数消歧：仅作用域可确认、没有变量绑定、同名成员全是函数且唯一参数个数匹配时返回 overload_arity；同参数个数的不同类型重载不猜测。目标是原 AST 定义身份，不是同名 HCG 节点。

地址内置、外部合约对象、类型转换后的成员、new、super、内置函数和事件/结构体只分类、不返回依赖目标。地址类型只接受精确 address/address payable；contract/interface 名称必须来自原声明和同文件类型定义，不能用名称前缀猜测。复杂接收者不能证明类型时保留 unknown。library 仅表示被调定义的归属，不证明其 EVM 调用方式。

定向测试确认 address(owner) 是无 type 字段的 type_cast_expression，payable(owner) 是 payable_conversion_expression，emit E(x) 是 emit_statement 而非 call_expression。按既定支持范围增加这些实际 AST 接入；emit 参数内部的普通调用仍逐一分析。首轮 4 failed/16 passed 记录和初版源码保留在 execution/resolver_tests_v1.* 与 development/，其中一项来自无效测试夹具；修正后 20 项通过，最终补齐真实边界后新增测试共 25 项。没有修改 grammar 或冻结分析器。

未为 !f()、a + f() 等复合 callee 新增内部绑定适配：冻结 resolve_callable 在这些实际 AST 上返回 None；冻结 _postfix 只用于沿用的诊断定位与非目标分类，不能据此假称已恢复内部定义。super 与同参数个数重载也继续未知。

### 10.2 全部 HCG internal_call 的参照类别

逐条保留 (task, file, source SHA, source node, target node, edge key)、AST 字节锚点、实际表达式和解析原因。表达式候选名单逐条与 EP0b 最终版本一致；同名只用于定位，确认内部调用必须匹配准确的目标定义。

| 参照类别 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| internal_confirmed | 221 | 229 |
| not_internal | 105 | 225 |
| rebinding | 8 | 8 |
| undetermined | 54 | 53 |
| no_expression | 76 | 76 |
| 合计原 HCG 多重边 | 464 | 591 |

not_internal 中，地址内置 99/219，其余已确认外部或转换调用 6/6。rebinding 的实际目标不是 HCG 目标，完整双定义身份见 gap_review.json；例如三个 SafeMath 不同参数数目的调用实际指向另一定义，而 HCG 原边指向当前同名函数。原图边保持不变。

**与 r5 粗分类对照：** r5 的 76/99/33=208 和 76/219/34=329，本轮严格分类可复核为 76/99/6=181 和 76/219/6=301，末项分别少 27/28。这里将 no_expression 和已确认非内部类合并仅为对照 r5，不能把“未找到表达式”写成已证明非内部。r5 提供了粗计数，没有保存其逐边成员清单，因此不能虚构“具体是哪 27/28 条改变了旧标签”。calls_*.json 的 rough_comparison 提供全部 1055 条边的原 EP0b 类别、最终类型、候选状态和原因；gap_review.json 给出全部已排除、未知、错绑及无表达式清单。粗数未被完整复现是待审查事项，不能继续当作已核验事实。

### 10.3 覆盖、门槛及停止结论

| 项目 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| EP0 原范围 / 已确认参照集 | 178/221 = 80.54% | 197/229 = 86.03% |
| r5 扩展范围 / 已确认参照集 | 219/221 = 99.10% | 227/229 = 99.13% |
| undetermined / internal_confirmed | 54/221 = 24.43% | 53/229 = 23.14% |
| 覆盖 ≥80% | 通过 | 通过 |
| 未确定比例 ≤20% | **不通过** | **不通过** |
| EP1 准入 | **停止** | **停止** |

这是使用同一 resolver 定义参照集后的投影覆盖，主要检验“已解析调用能否落到语句/函数图节点”，不是独立标注的内部调用召回率、准确率，也不能从约 99% 宣称语义完整。

两任务各 2 条缺失投影来自 buggy_43.sol、buggy_44.sol：emit 参数内 hasActiveOperator() 已绑定函数，但原 HCG 的 emit 语句没有精确源端投影。没有把它们强行挂到函数或邻近语句。全部未知项原因：

| 未确定边原因 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| 一元/二元等复合 callee 形状 | 38 | 39 |
| 参数个数仍不能唯一消歧 | 12 | 12 |
| super 分派未支持 | 2 | 2 |
| 接收者/成员仍无法确认 | 2 | 0 |

**EP0c 实现与测量交付完成，但准入门槛失败；按 r5 停在本阶段，不进入 EP1。** 未降低 80% 或提高 20%，也没有把 unknown 偷换成 not_internal 来通过门槛。可提交下一轮审查的方向是受限 callee 后缀绑定及粗分类来源核验；本轮未实施此替代设计。

### 10.4 语句级候选及 HCG 不对应项

这里只统计候选，不把它们写进任何图。EP0 已有候选集合逐条重放一致且全部保留。

| 候选 kind | 重入节点 | 访问控制节点 |
|---|---:|---:|
| internal | 173 | 180 |
| inherited | 7 | 6 |
| library | 139 | 132 |
| overload_arity | 3 | 3 |
| 唯一语句→定义候选 | 322 | 321 |
| EP0 原候选 | 180 | 186 |
| 新增候选 | 142 | 135 |
| 原 HCG 无对应函数级 internal_call | 138 | 125 |

新增全部来自库调用 139/132 和重载消歧 3/3。修饰器体内已解析调用表达式 7/9 个，按原语句归属处理；修饰器应用没有伪装成 CALL_SITE。无对应 HCG 边的候选中，库调用各 111，internal 20/8，inherited 7/6；“不对应”不自动等于新解析错误或原图错误，完整端点、调用锚点和来源见 projected_call_sites 与 gap_review.json。函数级平行边、调用表达式和去重语句边分母均分开。

### 10.5 回归、封存与边界

EdgeSem 59、NodeSem 1353、DFG v2 2653，共 **4065 项 CPU 回归通过**；新增解析与参照测试 25 项。execution 保存实际命令、耗时、退出码和日志 SHA；verification.json 独立重算分类、覆盖、候选差集，检查冻结源码、354 项 _code_refs、8H 归档 load、历史输入/EP0/EP0b 产物与四文档原字节前缀。文档按 UTF-8 追加并执行 doc_check。

没有正式模型训练、GPU运行、权重加载或图修改；回归中的合成计算不是新实验成绩。新入口只在 EdgeSem，三份记录同步追加并本地提交，不自动 push。最终实验将在显存充足的服务器另建批次；本机 RTX3050 4GiB 只约束本地开发，本轮未部署服务器。D1 主视图、D2 P2、D3 七类规则仍待后续明确确认。
