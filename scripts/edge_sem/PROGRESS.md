# EdgeSem 实施进度

## EP0：输入与接入侦察（Codex，2026-11-10）

依据PROMPTS r3 §4.1/4.2；起始7692bc88，用户明确授权远程快进同步后到ce8fa93a。WSL DNS失败，使用Windows Git及既有代理完成同一ff-only同步；无reset/force/旧文件覆盖。本轮没有执行EP1。

新增recon/common.py、inventory.py、semantic.py、attributes.py、calls.py、model_probe.py、run.py、report.py及侦察测试；仅负责读历史输入、计数、内存CPU探针和输出报告。交付RECON.md、recon.json及artifacts/ep0_v1。复用旧解析/投影/CFG/模型构造，不修改DFG、NodeSem或作者代码。

四任务F0/F3、features、folds、label_view、源码及L1–L3 SHA核验通过，旧8H.load通过。记录30个历史G3R拟合的实际配置和best/last轮数，节点max_lr=.005/div_factor25，合约.01/20。每任务完整canonical/反射合并/稀疏计数、384文件CFG、声明和guard投影及匿名临时视图逐文件保存。

节点两任务：可修改回边26/29，cf_back禁用；bit15无来源恒0；modifier guard映射0/616和0/715；MOD_APPLY178/195、CALL_SITE180/186、可映射GUARDS6305/3787正向边。CALL_SITE最终分母已排除内置函数/事件，未解析重载13+13、super3+3分别保留，不把条件投影率当总召回。

CPU A state/forward精确相等；B typed完成一次inner_train loss backward，step0，关系参数和梯度核验通过，旧深度checkpoint入口预期拒绝；C随机同文件边规模前向峰值RSS约2.81GiB，仅CPU估计、不含未来边属性/backward/优化器。侦察探针未加载历史模型权重、无GPU、无新语义图。

方案差异见recon.json.discrepancies：modifier锚点事实不符；冻结checkpoint需独立适配；return变量类别/缺失声明类型/写入形态来源不完整；READS_STATE跨调用路径适用性未定义；匿名投影需已有临时代码副本；任务学习率段落需按封存值解释。只记录建议，未实施替代设计。EP1前交用户审查，D1–D3依然待确认。

验收：新增11项探针测试、NodeSem1353项、DFG v2 2653项通过；命令、耗时、退出码和日志SHA在execution目录。开发时的导入、包装器、空字段、缺失psutil、split结构与emit夹具错误均留证，只修正新侦察代码；没有重试正式训练。冻结输入、源码和三文档前缀/UTF-8最终校验见verification.json。

最终实验安排在显存充足服务器，本机4GiB只约束开发。本轮本地提交，不自动推送或训练。

最终交付补充只读verify.py，核对743份冻结源码、354项DFG运行源码引用和所有输入SHA。PROMPTS.md本地为CRLF、提交版本为LF，规范化换行后文字完全相同；保留现有文件字节，不将这项纯换行差异混入EP0提交。

最终检查记录：第一次git diff --check将PROMPTS既有CRLF当作行尾空白而退出；已保留该日志。仅在检查命令中声明cr-at-eol，继续检查实际行尾空白，不改文件；核验正文等价和原始SHA仍保持。


## EP0b：修饰器来源与CALL_SITE覆盖（Codex，2026-11-10）

依据r4/§4.1，输入HEAD 0ddbb07e；按已有授权快进同步，远端已最新。新增guard_source.py、recon/ep0b_{common,run,guards,calls,attributes,report,verify}.py及两份测试；独立ep0b_v1，RECON只追加§9，旧ep0_v1与recon.json保留。

list API返回record/invocation/inner_anchor；辅助inspect_modifier_guards供unresolved/audit核验，不修改原audit/cache。12285个函数实例逐一等价。节点modifier映射616/616、715/715，去重总GUARDS6921/4502；合约1346/1346、1398/1398，总10172/8098。按修饰器和每语句入边分布均保存。

内部调用覆盖178/464、197/591；排除无表达式76/76后45.88%/38.25%，未达80%。外部调用7/707、6/688单列。首轮诊断遗漏一元/二元callee后缀，仅用冻结_postfix修正候选定位，121条由无表达式改其他；旧输出/源码及变更保留，精确覆盖和EP0语句边180/186不变，不扩展解析或改门槛。

属性按r4计数，成功率89.57%–99.03%，多声明0，unknown不猜测；def_kind未知47/4200、49/5168；write_access均为plain/indexed/member。shape_safe真实差异为空，反例通过，无属性向量。

实际测试命令记录于execution：CPU pytest -q -p no:cacheprovider分别运行edge_sem/tests、node_sem/tests、DFG/dfg_v2/tests，34+1353+2653=4040通过。doc_check、冻结SHA、_code_refs、8H.load、EP0产物和旧文档前缀验收见verification.json。
EP0b完成，CALL_SITE门槛未通过，停止后续落地并提交审查，不自行改EP2或启动训练。最终实验在显存充足服务器，本机4GiB只用于开发；本轮本地提交，不自动push。


## EP0c：调用解析与类型参照集（Codex，2026-11-10）

依据r5 §4.1/4.2c，输入HEAD 8b5463e6，按既有授权快进同步后仍为最新。新增call_resolve.py、recon/ep0c_common.py、ep0c_run.py、ep0c_calls.py、ep0c_report.py、ep0c_verify.py及tests/test_call_resolve.py。只读产物独立写入ep0c_v1；RECON追加§10，三文档原前缀保留。

解析优先冻结resolve_callable，按定义身份区分internal/inherited/library；裸标识符重载只在实参数量唯一时解析。明确排除address_builtin、external_member、cast_member、new、builtin、event等；super与不能证明者保持unknown。实际address/type_cast、payable_conversion、emit AST适配仅落实模板指定范围，不扩展复合callee内部绑定。

重入/访问控制internal_confirmed=221/229、not_internal=105/225、rebinding=8/8、undetermined=54/53、no_expression=76/76，总数464/591。r5覆盖219/221与227/229，EP0同分母178/221与197/229；unknown比例24.43%/23.14%超过20%，两任务准入均失败，停在EP0c，不进入EP1、不训练。

语句候选322/321，原180/186全部保留；新增库139/132、重载3/3。原HCG无对应函数级internal_call的候选138/125单列。各2个emit中的调用缺精确源端投影。r5粗计数208/329只能复核为181/301，且未提供粗分类逐边身份；本轮保存全部逐边最终分类与原EP0b对照，不伪造历史成员清单。

定向首轮4失败/16通过，来源为新代码对address/payable/emit实际AST接口未适配及无效夹具；初版源码和失败记录保留，修正后20通过，再补5项边界。正式CPU回归：python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests、scripts/node_sem/tests、scripts/DFG/dfg_v2/tests，59+1353+2653=4065通过。实际wrapper命令、耗时、SHA见execution；独立验收重算类别/覆盖/差集，并核对冻结代码、输入、旧产物、8H.load、_code_refs、文档前缀和UTF-8。

限制：99%为resolver条件下的投影率，不能当独立语义召回；未改变r5阈值；未实现建议中的callee后缀绑定扩展或更改旧图。最终实验在显存充足服务器另建批次，本机4GiB只限制开发，本轮本地提交不自动push。


## EP0d：复合callee解析与门槛重算（Codex，2026-11-10）

依据PROMPTS r6 §4.1/4.2d，输入HEAD 099174ed；快进同步已为最新。修改call_resolve.py及test_call_resolve.py，新增recon/ep0d_common、ep0d_run、ep0d_calls、ep0d_equivalence、ep0d_report、ep0d_verify六个模块，独立写入artifacts/ep0d_v1；RECON追加§11，三份记录只追加。

冻结resolve_callable失败且callee为一元/二元时，冻结_postfix选择后缀，EdgeSem本地复制原绑定规则；成功reason=postfix_callee。普通identifier/member在EP0c全部原调用中3420+3287=6707项目标完全等价；旧成功绑定和候选均保留。仍不猜super、同参数数目重载或未确认类型。

与模板的唯一批准调整：!msg.sender.send(v)的取反实际在receiver，用户同意只对地址内置分类的receiver调用冻结_postfix，保留类型/遮蔽检查。首次1失败/36通过/2未选及修改前源码保留；批准后39通过/2未选，再完成全量回归。该修正没有增加真实语料的not_internal排除项。验收脚本写入前compile发现的括号错误已修复，未产生正式验收重试。

重入/访问控制HCG原总数464/591不变；internal_confirmed=259/268，undetermined=16/14，其余not_internal105/225、rebinding8/8、no_expression76/76不变。新确认38/39条均从undetermined而来，无改为not_internal/rebinding。投影257/259=99.23%、266/268=99.25%，未知比例6.18%/5.22%，原80%/20%门槛通过。候选360/354，较EP0c增加38/33（internal23/25、library15/8）。r6纠正r5粗分类，181/301仍为可复核对照，208/329仅保留历史来源。

实际命令使用mando python -B：
- -m scripts.edge_sem.recon.ep0d_common
- ep0d_run包装ep0d_calls --task reentrancy_node/access_control_node
- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests、scripts/node_sem/tests、scripts/DFG/dfg_v2/tests
- ep0d_report、doc_check --expect-cjk <路径:原字节数>、ep0d_verify
完整命令、环境、耗时、日志SHA见execution。正式三套CPU回归75+1353+2653=4081通过；冻结750源码、354计算引用、697输入、196旧产物、29其他EdgeSem源码及8H.load与原文档前缀纳入最终验收。

本轮只交付解析和证据，约99%不是独立语义召回/精度。残留重载12/12、super2/2、接收者2/0及各2条emit投影缺口保留；不建图、不训练，停止供审查，不自动EP1/push。最终实验将在显存充足服务器另建批次，本机4GiB只限制开发。


## EP0e：接收者类型、库候选召回与停止报告（Codex，2026-11-10）

- 起点：edge-sem `6e95c9d7`、PROMPTS r7；读取§4.1，保留 EP0–EP0d。完成 receiver_type、受限 using 绑定、call_option/ABI 分类，以及独立候选枚举、原绑定对照和残留证据。
- 用户批准：只跳过 `using L for *` 的通配 source 比较，仍检查库首参数类型和其他约束；冻结方法不改。首次失败、修正前源码、批准记录和合成等价例外均保存，真实语料例外0。
- 主要改动：`call_resolve.py`、`tests/test_call_resolve.py`；新增 `recon/ep0e_{common,run,using,calls,examples,report,verify}.py`。结果目录 `artifacts/ep0e_v1/`，RECON§12、HANDOVER和训练变更§103只追加。
- 结果：每任务独立库候选 **312/347＝89.9135%**，候选集外0，**未达90%，停止EP0e**。形状明细与35条缺口逐条保存。不改分母、不扩展规则追门槛。
- 原364/358个成功调用完全不变；普通callee等价6707项，using等价439/743。各新增194个已解析调用，经已有对和重复投影合并后各新增188个语句候选，总数548/542。只有候选统计，没写图。
- EP0d的1,055条HCG参照类别不变，覆盖99.23%/99.25%，unknown比6.18%/5.22%，原门槛仍通过；本轮库召回门槛另算。
- 剩余：同名重载18、限定类型字符串6、未知接收者11（每任务）；访问控制另有1个prefix option仍unknown。方案更改须另行讨论，未自动实施。
- CPU回归命令：`CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider <目录>`。EdgeSem115、NodeSem1353、DFG2653，共 **4121 passed**。只读核验8H load、750冻结源码、354_code_refs、697输入引用、239旧产物、35其他EdgeSem源码；四文档前缀字节及UTF-8/CJK核验。执行收据与完整命令在 `execution/`。
- 报告 `summary.json` 的 gate_pass=false；完整性 `verification.json` 的 passed=true 只说明核验通过，不能冒充90%准入通过。无训练、无EP1、无冻结输入修改。本地提交，不自动推送。
- 最终实验安排在显存充足的服务器；当前4GiB限制仅属于本机开发。产物留在WSL。


## EP1：关系注册与typed模型接入（Codex，2026-11-10）

依据PROMPTS r8 §4.1/4.3，起点a71b2bc1，ff-only同步已最新。r8允许本阶段独立推进；EP0e 312/347的90%历史召回门槛仍失败，未批准或实现EP2的解析扩展。

修改__init__.py；新增materialize.py、init.py、model.py、tests/test_materialize.py、tests/test_model_equivalence.py、recon/ep1_{common,run,report,verify}.py。报告EP1_REPORT.md；独立证据artifacts/ep1_v1。冻结源码、输入和旧产物保持，三份文档只追加。

- 登记8剖面；cf_back全部禁用；recursive_method_call归structure，MOD_APPLY归call。属性/安慰剂模型仅注册，当前入口显式拒绝冒充实现。
- merge基础边调用原reflect_graph；typed保留正向＋独立REV_；DFG反向委托冻结materialize。metadata增加anchor_key提供文档要求的key_map，保持原二元返回接口。
- 新鲜G3R锚逐位复制共享参数和来源关系行；E1无来源行以compact ASCII JSON canonical的SHA种子、锚模型Xavier范围初始化，不消耗全局RNG。没有使用训练权重。
- dfg_profile保留G3R锚来源，edge_profile记录实际结构；typed用独立深校验，不绕过冻结checkpoint。EP7再接入正式绑定。
- 首轮测试发现if_true/if_false注册遗漏，19通过、2失败、9错误、4未选，源码/日志留档；只补EdgeSem的control别名后30通过、4未选。模板实质方案不变，没有自行采用需审批的新方案。

| 任务/剖面 | fold | canonical关系数 | 参数量 | 构造秒数 | 验收 |
|---|---:|---:|---:|---:|---|
| reentrancy_node/G3R | 0 | 212 | 5,111,012 | 20.860 | 逐位等价 |
| reentrancy_node/G3R | 9 | 212 | 5,111,012 | 20.976 | 逐位等价 |
| reentrancy_node/G3R-T | 0 | 220 | 5,176,676 | 20.178 | 有限前后向 |
| access_control_node/G3R-T | 0 | 234 | 5,291,588 | 8.446 | 有限前后向 |

G3R的fold0/9键、端点、全部参数、eval输出逐位相同，最大绝对差0；typed每关系计数与EP0完全一致，CPU前向/反向均有限，optimizer step0。重入两层typed增参65,664；访问控制参数总量5,291,588。耗时为单次CPU入口构造测量，含锚模型/重建/校验。原图指纹不变。

真实探针复用8H历史N-anon-s作为等价夹具，本轮不决定后续主实验视图。typed反向目标mean(logits²)不使用标签；冻结装配仍检查标签。历史config的device保留cuda:0用于来源，实际执行为CPU、cuda_initialized=false。

CPU完整回归149+1353+2653=4155通过。实际命令：python -B -m scripts.edge_sem.recon.ep1_run --name <name> -- -m pytest -q -p no:cacheprovider <edge_sem/tests、node_sem/tests、DFG/dfg_v2/tests>；报告/核验为ep1_report、ep1_verify，doc_check --expect-cjk按原字节数验新增中文。完整命令/耗时/退出码/日志SHA在execution。只读核验750冻结源码、354_code_refs、43其他EdgeSem源码、287历史产物、697输入引用和8H.load；最终见verification.json。

以下逐条列出两个节点任务typed图中边数<20的canonical关系（计数为整个固定任务图，不是train/val分折支持）。分别94、114个；未做稀疏共享或删边。

<details>
<summary>reentrancy_node：94个低支持关系</summary>

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| constructor_definition | DATA_DEF_USE | if | 4 |
| constructor_definition | REV_READS_STATE | new_variable | 3 |
| constructor_definition | REV_next_line | contract_declaration | 3 |
| constructor_definition | external_call | function_definition | 8 |
| constructor_definition | first_next_line | end_if | 3 |
| constructor_definition | first_next_line | end_loop | 2 |
| constructor_definition | first_next_line | expression_statement | 1 |
| constructor_definition | first_next_line | function_definition | 1 |
| constructor_definition | internal_call | function_definition | 17 |
| constructor_definition | next_line | new_variable | 1 |
| continue_statement | REV_next_line | expression_statement | 1 |
| continue_statement | next_line | while | 1 |
| contract_declaration | REV_next_line | end_if | 5 |
| contract_declaration | next_line | constructor_definition | 3 |
| end_if | REV_end_if | if | 4 |
| end_if | REV_end_if | while | 1 |
| end_if | REV_first_next_line | constructor_definition | 3 |
| end_if | next_line | contract_declaration | 5 |
| end_if | next_line | modifier_definition | 1 |
| end_if | next_line | return | 10 |
| end_loop | REV_first_next_line | constructor_definition | 2 |
| end_loop | REV_neg_next | while | 7 |
| end_loop | next_line | expression_statement | 11 |
| end_loop | next_line | for | 2 |
| end_loop | next_line | if | 1 |
| end_loop | next_line | new_variable | 14 |
| end_loop | next_line | return | 6 |
| env_source | ENV_FLOW | return | 11 |
| expression_statement | DATA_DEF_USE | if | 8 |
| expression_statement | DATA_DEF_USE | return | 8 |
| expression_statement | DATA_DEF_USE | while | 4 |
| expression_statement | REV_first_next_line | constructor_definition | 1 |
| expression_statement | REV_next_line | end_loop | 11 |
| expression_statement | REV_pos_next | for | 13 |
| expression_statement | REV_pos_next | while | 3 |
| expression_statement | next_line | continue_statement | 1 |
| expression_statement | next_line | while | 6 |
| for | DATA_DEF_USE | new_variable | 11 |
| for | REV_DATA_DEF_USE | function_definition | 11 |
| for | REV_DATA_DEF_USE | new_variable | 2 |
| for | REV_READS_STATE | new_variable | 8 |
| for | REV_next_line | end_loop | 2 |
| for | REV_next_line | function_definition | 8 |
| for | REV_next_line | new_variable | 11 |
| for | pos_next | expression_statement | 13 |
| for | pos_next | new_variable | 13 |
| function_definition | DATA_DEF_USE | for | 11 |
| function_definition | REV_external_call | constructor_definition | 8 |
| function_definition | REV_external_call | modifier_definition | 4 |
| function_definition | REV_first_next_line | constructor_definition | 1 |
| function_definition | REV_internal_call | constructor_definition | 17 |
| function_definition | next_line | for | 8 |
| if | REV_DATA_DEF_USE | constructor_definition | 4 |
| if | REV_DATA_DEF_USE | expression_statement | 8 |
| if | REV_next_line | end_loop | 1 |
| if | REV_next_line | modifier_definition | 1 |
| if | end_if | end_if | 4 |
| if | neg_next | new_variable | 2 |
| if | neg_next | return | 1 |
| if | pos_next | new_variable | 14 |
| library_declaration | next_line | struct_declaration | 1 |
| modifier_definition | REV_next_line | end_if | 1 |
| modifier_definition | external_call | function_definition | 4 |
| modifier_definition | next_line | if | 1 |
| new_variable | DATA_DEF_USE | for | 2 |
| new_variable | DATA_DEF_USE | while | 4 |
| new_variable | READS_STATE | constructor_definition | 3 |
| new_variable | READS_STATE | for | 8 |
| new_variable | REV_DATA_DEF_USE | for | 11 |
| new_variable | REV_WRITES_STATE | new_variable | 2 |
| new_variable | REV_neg_next | if | 2 |
| new_variable | REV_next_line | constructor_definition | 1 |
| new_variable | REV_next_line | end_loop | 14 |
| new_variable | REV_pos_next | for | 13 |
| new_variable | REV_pos_next | if | 14 |
| new_variable | REV_pos_next | while | 4 |
| new_variable | WRITES_STATE | new_variable | 2 |
| new_variable | next_line | for | 11 |
| new_variable | next_line | while | 7 |
| return | REV_DATA_DEF_USE | expression_statement | 8 |
| return | REV_ENV_FLOW | env_source | 11 |
| return | REV_neg_next | if | 1 |
| return | REV_next_line | end_if | 10 |
| return | REV_next_line | end_loop | 6 |
| struct_declaration | REV_next_line | library_declaration | 1 |
| while | REV_DATA_DEF_USE | expression_statement | 4 |
| while | REV_DATA_DEF_USE | new_variable | 4 |
| while | REV_next_line | continue_statement | 1 |
| while | REV_next_line | expression_statement | 6 |
| while | REV_next_line | new_variable | 7 |
| while | end_if | end_if | 1 |
| while | neg_next | end_loop | 7 |
| while | pos_next | expression_statement | 3 |
| while | pos_next | new_variable | 4 |

</details>

<details>
<summary>access_control_node：114个低支持关系</summary>

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| constructor_definition | DATA_DEF_USE | if | 4 |
| constructor_definition | REV_READS_STATE | new_variable | 3 |
| constructor_definition | REV_next_line | contract_declaration | 3 |
| constructor_definition | external_call | function_definition | 8 |
| constructor_definition | first_next_line | end_if | 3 |
| constructor_definition | first_next_line | end_loop | 2 |
| constructor_definition | first_next_line | expression_statement | 1 |
| constructor_definition | first_next_line | modifier_definition | 1 |
| constructor_definition | internal_call | function_definition | 17 |
| constructor_definition | next_line | new_variable | 1 |
| continue_statement | REV_next_line | expression_statement | 1 |
| continue_statement | next_line | while | 1 |
| contract_declaration | next_line | constructor_definition | 3 |
| contract_declaration | next_line | struct_declaration | 4 |
| end_if | REV_end_if | if | 7 |
| end_if | REV_end_if | while | 1 |
| end_if | REV_first_next_line | constructor_definition | 3 |
| end_if | next_line | modifier_definition | 1 |
| end_if | next_line | return | 9 |
| end_if | next_line | struct_declaration | 1 |
| end_if | next_line | while | 2 |
| end_loop | REV_first_next_line | constructor_definition | 2 |
| end_loop | REV_neg_next | while | 9 |
| end_loop | next_line | expression_statement | 12 |
| end_loop | next_line | for | 2 |
| end_loop | next_line | function_definition | 13 |
| end_loop | next_line | if | 2 |
| end_loop | next_line | new_variable | 2 |
| end_loop | next_line | return | 3 |
| end_loop | next_line | while | 1 |
| env_source | ENV_FLOW | function_definition | 7 |
| env_source | ENV_FLOW | if | 17 |
| env_source | ENV_FLOW | return | 12 |
| expression_statement | DATA_DEF_USE | if | 8 |
| expression_statement | DATA_DEF_USE | return | 7 |
| expression_statement | DATA_DEF_USE | while | 6 |
| expression_statement | REV_first_next_line | constructor_definition | 1 |
| expression_statement | REV_next_line | end_loop | 12 |
| expression_statement | REV_pos_next | for | 13 |
| expression_statement | REV_pos_next | while | 4 |
| expression_statement | next_line | continue_statement | 1 |
| expression_statement | next_line | while | 8 |
| for | DATA_DEF_USE | if | 1 |
| for | DATA_DEF_USE | new_variable | 11 |
| for | REV_DATA_DEF_USE | function_definition | 10 |
| for | REV_DATA_DEF_USE | new_variable | 3 |
| for | REV_READS_STATE | new_variable | 8 |
| for | REV_next_line | end_loop | 2 |
| for | REV_next_line | function_definition | 8 |
| for | REV_next_line | new_variable | 9 |
| for | pos_next | expression_statement | 13 |
| for | pos_next | new_variable | 13 |
| function_definition | DATA_DEF_USE | for | 10 |
| function_definition | REV_ENV_FLOW | env_source | 7 |
| function_definition | REV_external_call | constructor_definition | 8 |
| function_definition | REV_external_call | modifier_definition | 4 |
| function_definition | REV_internal_call | constructor_definition | 17 |
| function_definition | REV_next_line | end_loop | 13 |
| function_definition | next_line | for | 8 |
| if | REV_DATA_DEF_USE | constructor_definition | 4 |
| if | REV_DATA_DEF_USE | expression_statement | 8 |
| if | REV_DATA_DEF_USE | for | 1 |
| if | REV_ENV_FLOW | env_source | 17 |
| if | REV_next_line | end_loop | 2 |
| if | REV_next_line | modifier_definition | 4 |
| if | REV_pos_next | if | 7 |
| if | end_if | end_if | 7 |
| if | neg_next | new_variable | 2 |
| if | neg_next | return | 2 |
| if | pos_next | if | 7 |
| if | pos_next | new_variable | 15 |
| library_declaration | next_line | struct_declaration | 1 |
| modifier_definition | REV_first_next_line | constructor_definition | 1 |
| modifier_definition | REV_next_line | end_if | 1 |
| modifier_definition | external_call | function_definition | 4 |
| modifier_definition | next_line | if | 4 |
| new_variable | DATA_DEF_USE | for | 3 |
| new_variable | DATA_DEF_USE | while | 6 |
| new_variable | READS_STATE | constructor_definition | 3 |
| new_variable | READS_STATE | for | 8 |
| new_variable | READS_STATE | while | 8 |
| new_variable | REV_DATA_DEF_USE | for | 11 |
| new_variable | REV_WRITES_STATE | new_variable | 2 |
| new_variable | REV_neg_next | if | 2 |
| new_variable | REV_next_line | constructor_definition | 1 |
| new_variable | REV_next_line | end_loop | 2 |
| new_variable | REV_pos_next | for | 13 |
| new_variable | REV_pos_next | if | 15 |
| new_variable | REV_pos_next | while | 4 |
| new_variable | WRITES_STATE | new_variable | 2 |
| new_variable | next_line | for | 9 |
| new_variable | next_line | while | 6 |
| return | REV_DATA_DEF_USE | expression_statement | 7 |
| return | REV_ENV_FLOW | env_source | 12 |
| return | REV_neg_next | if | 2 |
| return | REV_next_line | end_if | 9 |
| return | REV_next_line | end_loop | 3 |
| struct_declaration | REV_next_line | contract_declaration | 4 |
| struct_declaration | REV_next_line | end_if | 1 |
| struct_declaration | REV_next_line | library_declaration | 1 |
| while | REV_DATA_DEF_USE | expression_statement | 6 |
| while | REV_DATA_DEF_USE | new_variable | 6 |
| while | REV_READS_STATE | new_variable | 8 |
| while | REV_next_line | continue_statement | 1 |
| while | REV_next_line | end_if | 2 |
| while | REV_next_line | end_loop | 1 |
| while | REV_next_line | expression_statement | 8 |
| while | REV_next_line | new_variable | 6 |
| while | REV_pos_next | while | 1 |
| while | end_if | end_if | 1 |
| while | neg_next | end_loop | 9 |
| while | pos_next | expression_statement | 4 |
| while | pos_next | new_variable | 4 |
| while | pos_next | while | 1 |

</details>


本轮未训练、未用GPU、未建新语义图；结构闸门不代表效果提升，typed也改变关系参数量与聚合分母。checkpoint适配和EdgeAware层仍待各自阶段，停止于EP1，本地提交而不自动push。最终实验将在显存充足服务器执行，本机RTX3050 4GiB仅为当前开发限制；本轮产物保存在WSL。


## 2026-11-10 EP2完成：MOD_APPLY/CALL_SITE与G4R CPU闸门（Codex）

r9起点799865ec；§0调用修正先通过，再构建两个节点任务全部文件。新增EP2_REPORT.md、build_f4.py、recon/ep2_*与三份测试/一份fixture；修改call_resolve.py和其中r9例外测试，产物独立存artifacts/ep2_v1。旧DFG、NodeSem、作者代码和历史产物不改。

两个节点任务都在各自冻结的347个EP0e候选上从312增到334，即96.2536%；各新增22个、剩余13个、候选集外绑定0。重入558/558、访问控制552/552个旧成功调用逐字段保持；修正逐条列表及旧绑定比较存于call_fix/<task>.json。

EP0d两项硬条件仍通过：重入投影257/259=99.2278%、未确定16/259=6.1776%；访问控制266/268=99.2537%、未确定14/268=5.2239%。这是已确认集合的投影覆盖，不是所有真实调用的语义召回。

这是看到EP0e结果后的修正。历史EP0e的312/347=89.9135%及90%门槛“未通过”原样保留，新334/347只作描述，不能据此改写预登记结论。两个call_fix运行成功并写出第0节报告后，才启动真实建边；时间顺序纳入最终核验。

1. r9 已明确要求两项修正：库方法先按“形参个数=实参+1、首参数规范类型=接收者类型”筛选再要求唯一；外层 call_option 只分类 address_builtin/call_option，不制造函数目标。同首参类型仍有多个候选就保留不确定。
2. 用户批准冻结 Projector 仅为 AST 编号、类型、坐标做 label 结构身份核验（call_c43ebd18ece144ba813d112d5caad2d3）。建边规则不使用漏洞标签、预测或 label 语义文本；标识符拼写只用于 AST 声明引用绑定，不按名称推断漏洞。未改 Projector。
3. r9 的预计18个直接修复之外，既有 receiver_type 递归自然恢复4个链式调用。用户批准保留实际22个新增、334/347与13个剩余（call_839a863f2dcb4911bdbeac95e9dcac0a）；没有新增类型推断规则。decisions.json、decisions_chain.json 保存决定。
4. add_edges 返回它自己创建的独立深拷贝；即使误传原图，也先完整校验后只修改副本。调用方必须使用返回值。所有旧节点、顺序、属性及原边key/属性不变；不写新gpickle。
5. MOD_APPLY 延用冻结 GuardAnalyzer 的作用域、继承、参数绑定和单一占位符规则，只表达应用关系，不证明权限保护。CALL_SITE 保留kind；每个语句的嵌套调用按精确AST身份枚举，同语句到同定义只建一条边，但保留每次调用证据。
6. 正式边基于 original 源码/F3；CPU模型等价探针沿用EP1绑定的历史8H特征夹具，不意味着重新启用匿名主实验。config中保存的cuda:0是历史配置，实际执行CUDA_VISIBLE_DEVICES为空、cuda_initialized=false。

### 全部文件与预计值对照

| 任务 | 文件实例 | MOD_APPLY | CALL_SITE | 合计正向边 | EP0预计MOD/CALL | EP0e CALL候选 |
|---|---:|---:|---:|---:|---|---:|
| reentrancy_node | 71 | 178 | 570 | 748 | 178/180 | 548 |
| access_control_node | 57 | 195 | 564 | 759 | 195/186 | 542 |

| 口径 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| 修饰器唯一解析/应用次数 | 178/187 = 95.1872% | 195/204 = 95.5882% |
| 已解析调用可投影/已解析调用次数 | 578/580 = 99.6552% | 572/574 = 99.6516% |

修饰器继承绑定88/86，各9个unresolved（modifier_binding）；not_unique/not_in_graph/self_loop/duplicate均0。调用580/574次resolved，各2次not_in_graph、8次duplicate；保留每次来源，但同语句同目标只连一次。以下为语句调用事件分布，address_builtin等预期排除类别不等于失败：

| 调用事件结果 | 重入节点 | 访问控制节点 |
|---|---:|---:|
| address_builtin | 1191 | 560 |
| builtin | 1443 | 1682 |
| call_option | 355 | 340 |
| cast_member | 22 | 20 |
| duplicate | 8 | 8 |
| emitted | 570 | 564 |
| event_or_struct | 11 | 22 |
| external_member | 69 | 31 |
| new_contract | 7 | 3 |
| not_in_graph | 2 | 2 |
| overload_unresolved | 10 | 10 |
| super | 3 | 3 |
| unknown | 139 | 87 |

| 已绑定调用kind（去重前） | 重入节点 | 访问控制节点 |
|---|---:|---:|
| internal | 198 | 208 |
| inherited | 7 | 6 |
| library | 372 | 357 |
| overload_arity | 3 | 3 |

| §0原始调用池unknown原因 | 重入修正前→后 | 访问控制修正前→后 |
|---|---:|---:|
| receiver_or_member_not_confirmed | 104→82 | 74→52 |
| unbound_or_unsupported_identifier | 61→61 | 36→36 |
| unsupported_callee_shape | 353→0 | 4→1 |

§0原始调用池与语句子树的分母不同。unknown→address_builtin/→call_option/→resolved重入351/2/22，访问控制0/3/22；每任务仍有13个冻结using候选未绑定。

### 模型与回归验收

| 任务/fold0 | G3R-T→G4R canonical数 | 新canonical行/层 | G4R参数量 | 构造秒数 | 前后向秒数 |
|---|---|---:|---:|---:|---:|
| reentrancy_node | 220→232 | 12 | 5,275,172 | 23.336 | 4.495 |
| access_control_node | 234→246 | 12 | 5,390,084 | 9.955 | 2.803 |

两任务空E1的G4R与G3R-T在canonical键、端点、全部参数和eval输出逐位相同。加入本轮E1后，通过独立validate_registration；每层12个新canonical行（含显式REV_）按已有relation_seed及锚模型Xavier范围逐位核验，第二次新鲜构造相同。共享的全部非关系参数和旧关系行均与G3R-T逐位一致。

每个任务参数增加98,496。一次CPU前后向采用mean(logits²)，只检查有限值和可微性，不使用监督目标、不调用optimizer，step=0。装配保留冻结的标签完整性核验。构造与计算时间为本机单次记录，不是性能基准或训练耗时。原F3文件SHA与内存图指纹保持。

完整CPU回归：EdgeSem 177 passed、NodeSem 1353 passed、DFG v2 2653 passed，共4183项，无跳过。EdgeSem较EP1增加28项，覆盖库重载/调用选项、改名/遮蔽反例、修饰器继承/参数/占位符、语句去重、边篡改拒绝、标签扰动不变性和真实G4R模型闸门。既有依赖弃用警告保留。

三个真实文件的期望先人工核对源码并固定source SHA，再运行构建器：reentrancy_bonus.sol为0条MOD_APPLY与1条withdrawReward调用；rubixi.sol为6条MOD_APPLY与3条CALL_SITE；unprotected0.sol两类均0，不能因为定义了未应用的modifier就补边。

保留三次开发失败及对应源码快照：
- call_fix_tests：新测试相对导入在非package目录收集失败，改为绝对导入。
- call_fix_tests_import：88通过、2失败；旧等价断言把内置now的legacy_type为空误当作不应改变。仅允许r9指定的同名重载在参数个数与规范接收者类型唯一匹配时差异，其他绑定继续严格比较；修正后90通过。
- builder_tests：14通过、3失败；NetworkX MultiDiGraph.get_edge_data第三个位置参数是key，改用default={}关键字。修正后17通过。

日志在execution/，旧实现快照在development/；没有覆盖失败记录，也没有重跑任何正式训练。全部修改完成后才执行三套完整回归，不把这些开发失败写成新增实验。

### 记录、命令和遗留

before.json绑定r9 HEAD 799865ec79f085ab100d009aadd8fed7a9a048f7与PROMPTS SHA 362d1d6462c39adaf16b10aef56f7c78386f76f8dafcce992f0cf04a02436455。开始时ff-only同步已为最新。每任务manifest绑定原F0/F3、plan、store、audit、源码、实现文件及JSONL/Audit SHA；不把文件名相同当作身份相同。

最终ep2_verify.py核对750份冻结源码、354项DFG _code_refs、51份其他EdgeSem源码、321份旧产物、697项输入引用与8H只读load；逐条验证新边端点AST锚点、来源证据及调用审计。将内存副本新增边移除后，整图指纹必须与原图相同。三文档原字节前缀不变，追加内容及新报告通过UTF-8/中文检查。通过收据保存在verification.json；summary.json与两份probes保存计算结果。

实际执行（mando、CPU；原TREE_SITTER_LIB_DIR、PYTHONDONTWRITEBYTECODE=1、OMP/MKL各2）：

    python -B -m scripts.edge_sem.recon.ep2_common
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_tests_legacy_type -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_call_fix.py scripts/edge_sem/tests/test_call_resolve.py
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_reentrancy_node -- -m scripts.edge_sem.recon.ep2_call_fix --task reentrancy_node
    python -B -m scripts.edge_sem.recon.ep2_run --name call_fix_access_control_node -- -m scripts.edge_sem.recon.ep2_call_fix --task access_control_node
    python -B -m scripts.edge_sem.recon.ep2_run --name builder_tests_multigraph -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_build_f4_calls.py
    python -B -m scripts.edge_sem.recon.ep2_run --name build_reentrancy_node -- -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/ep2_v1/reentrancy_node
    python -B -m scripts.edge_sem.recon.ep2_run --name build_access_control_node -- -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/ep2_v1/access_control_node
    python -B -m scripts.edge_sem.recon.ep2_run --name edge_tests -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name nodesem_tests -- -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name dfg_tests -- -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m scripts.edge_sem.recon.ep2_run --name collect_report -- -m scripts.edge_sem.recon.ep2_report
    python -B -m scripts.edge_sem.recon.ep2_run --name doc_check -- -m scripts.node_sem.doc_check --expect-cjk HANDOVER.md:291526 docs/training_changes_2026-10-07.md:1076536 scripts/edge_sem/PROGRESS.md:25964 scripts/edge_sem/EP2_REPORT.md scripts/edge_sem/artifacts/ep2_v1/call_fix/REPORT.md
    python -B -m scripts.edge_sem.recon.ep2_run --name verify -- -m scripts.edge_sem.recon.ep2_verify

首次正式edge_tests还设置EDGESEM_EP2_RECEIPTS为新批次probes绝对路径，成功才排他写入两份收据。日常回归不设置该变量；已有目录和收据拒绝覆盖。命令精确argv、开始时间、退出码、耗时与日志SHA均在execution/，不应照此再次运行覆盖已完成批次。

仍未实现GUARDS、边属性、EdgeAwareHGT层和正式checkpoint/训练调度；本轮G4R仅有MOD_APPLY/CALL_SITE部分E1。每任务9个modifier绑定失败、10个同参数数重载、3个super以及其他unknown按原规则保留；每任务2个已解析调用缺精确图投影，不做邻近节点补边。MOD_APPLY不能单独证明访问控制，CALL_SITE也不等于完整跨文件或动态调用分析。

最终实验将在显存充足的服务器另建批次；当前RTX3050 4GiB只限制本机开发，本轮没有部署或验收服务器。全部产物留在WSL，未向C盘另写大型缓存。本轮无GPU、无训练、无新权重，停止于EP2；按共享流程本地提交，不自动推送或进入EP3。


## 2026-11-10 EP3完成：GUARDS与完整E1接入（Codex）

起点edge-sem f138c6b2b42cc2131866005deaf6d98bb070f651；PROMPTS r10 SHA 5946f94a53dd04f4e73a62967e0ef15f3e85f958f680bc00351deda5890ab00f。先读取§4.1及方案/EP3要求，ff-only同步确认已为最新；旧历史文档只追加。

## 实现与批准选择

修改build_f4.py和tests/test_build_f4_model.py；新增guard_edges.py、recon/ep3_common.py、ep3_archive.py、ep3_run.py、ep3_report.py、ep3_verify.py；新增tests/test_build_f4_guards.py、test_build_f4_guards_model.py和fixtures/ep3_guards.sol。报告EP3_REPORT.md，独立产物artifacts/ep3_v1。旧guard_source、call_resolve、DFG、NodeSem、作者代码及全部既有产物不改。

1. 每文件复用同一个GuardAnalyzer，目标仅为精确投影且AST类型属于STATEMENTS的节点，含条件/循环和修饰器体语句；定义节点不作GUARDS目标。非修饰器直接使用_anchor，映射缺失则保存完整审计并阻止任务manifest封存，不猜测邻近语句。
2. 修饰器来源由既有modifier_guard_sources取inner_anchor；每个目标的modifier记录必须位于for_node列表末尾，并与来源列表逐项public_record相等。GUARDS直接从修饰器体守卫到被修饰语句，保留invocation_anchor用于溯源，不经过MOD_APPLY。继承使用同文件原冻结绑定。
3. 同一源/目标只建一条GUARDS，evidence按for_node原顺序保留全部记录，顶层kind为去重排序列表。operand_classes保留msg.sender、timestamp等原始值，未映射成caller_identity。loop_cond的空operand_classes保留冻结设计；public_record实际还有offset=0，也原样保留，不将它当成新属性。
4. unknown目标仍保留已确认的守卫边；自环计数而不建边。add_edges对GUARDS两端增加STATEMENTS校验，其他两类角色校验不变，仍返回独立深拷贝。
5. 用户批准显式只读EP2归档加载（call_77a0cd9dcd464ce3b3ab20d7ad8bb54f）：旧manifest绑定build_f4 SHA，正常加载在实现变化后仍拒绝。ep3_archive核对旧verification/summary/报告、旧源码SHA、预修改快照及所有输入/产物；只允许两个固定EP2 manifest、两个明确修改文件的快照例外，旧plan/seal/产物不改。EP2模型回归改用该显式入口；默认生产load_edges仍检查当前SHA。
6. 延续已批准的Projector结构身份边界，只允许冻结代码读取label中的AST编号/类型/坐标。建边不使用漏洞标签、预测、标识符名字的漏洞含义；函数名只为最大入边位置的诊断显示，声明名字只参与原绑定过程。

## 真实结果

| 任务 | 文件实例 | MOD_APPLY | CALL_SITE | GUARDS正向边 | 守卫记录 | 多证据边 | unknown目标 |
|---|---:|---:|---:|---:|---:|---:|---:|
| reentrancy_node | 71 | 178 | 570 | 6921 | 6956 | 31 | 12 |
| access_control_node | 57 | 195 | 564 | 4502 | 4537 | 31 | 12 |

两个任务分别完成71、57个文件实例。GUARDS记录6956/4537，逐文件与EP0/RECON完全一致，无目标集合差异。非修饰器6340/6340、3822/3822，修饰器616/616、715/715全部精确映射；没有映射缺失或自环。去重后6921/4502条，和EP0b预计数量完全一致。

每任务31条边含多条证据，kind组合均为internal_check；共35条重复记录被合并到这些边，记录本身未删除。所有MOD_APPLY与CALL_SITE JSON行按规范化文本排序后逐行复现EP2（178/570、195/564），不仅核对汇总数。

每任务12个guard_status=unknown目标，其中2个仍有已确认GUARDS入边，保持未知状态。EP2的9个未解析modifier_invocation全部属于构造函数头，冻结一般标识符解析均为contract_declaration；原modifier成员查找为空，失败原因modifier_binding保持，因此不增加MOD_APPLY，也不把基类构造应用当成修饰器守卫。

| kind | 重入记录/映射 | 访问控制记录/映射 |
|---|---:|---:|
| require | 4082/4082 | 2586/2586 |
| if_branch | 994/994 | 748/748 |
| early_exit | 1008/1008 | 226/226 |
| loop_cond | 175/175 | 181/181 |
| modifier | 616/616 | 715/715 |
| internal_check | 81/81 | 81/81 |

## 入度统计与最大值身份

| 任务 | 分母 | 节点数 | 平均GUARDS入边 | 中位数 | 最大值 |
|---|---|---:|---:|---:|---:|
| reentrancy_node | 全部原F3节点（含env） | 12223 | 0.566228 | 0 | 13 |
| reentrancy_node | 作者节点（不含env） | 12036 | 0.575025 | 0.0 | 13 |
| reentrancy_node | 本轮语句目标 | 6635 | 1.043105 | 1 | 13 |
| access_control_node | 全部原F3节点（含env） | 7892 | 0.570451 | 0.0 | 13 |
| access_control_node | 作者节点（不含env） | 7710 | 0.583917 | 0.0 | 13 |
| access_control_node | 本轮语句目标 | 4664 | 0.965266 | 1.0 | 13 |

| 任务 | 文件/函数 | source SHA256 | 最大值节点ID |
|---|---|---|---|
| reentrancy_node | buggy_24.sol/invest | 56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb | 1868, 1869, 1870 |
| access_control_node | buggy_24.sol/invest | 1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b | 689, 690, 691 |

同名buggy_24.sol分别按task/cohort与source SHA识别；完整逐节点入度和直方图保存在f4_audit.json，不按文件名混同。

## CPU模型闸门

| 任务/fold0 | G3R-T→G4R canonical数 | 相对EP2新增GUARDS行 | 全部E1新行/层 | 参数量 | 构造秒数 | 前后向秒数 |
|---|---|---:|---:|---:|---:|---:|
| reentrancy_node | 220→274 | 42 | 54 | 5,619,908 | 24.695 | 5.436 |
| access_control_node | 234→292 | 46 | 58 | 5,767,652 | 10.453 | 3.289 |

两任务空E1的G4R与G3R-T在canonical键、端点、全部参数及eval输出逐位相同。完整三关系加入后通过独立validate_registration。相对EP2新增GUARDS/REV_GUARDS规范关系42/46行；加上原12行MOD_APPLY/CALL_SITE，共54/58行E1参数/层，全部用原relation_seed与锚模型Xavier范围逐位核对，重复新鲜构造相同；所有共享参数及旧关系行保持与G3R-T一致。

CPU目标为mean(logits²)，前向/反向有限、optimizer step=0；不是监督训练或检测成绩。构造/前后向时间只是本机单次记录，不能据此推断GPU显存或训练性能。历史8H特征仍只作EP1/EP2延续的CPU等价夹具，不决定后续主视图。记录中的config.device=cuda:0来自历史配置；实际CUDA_VISIBLE_DEVICES为空、cuda_initialized=false。

## 完整新增规范关系

### reentrancy_node：全部新增GUARDS规范关系

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | expression_statement | 3323 |
| expression_statement | GUARDS | for | 24 |
| expression_statement | GUARDS | if | 546 |
| expression_statement | GUARDS | new_variable | 575 |
| expression_statement | GUARDS | return | 249 |
| expression_statement | GUARDS | while | 18 |
| expression_statement | REV_GUARDS | expression_statement | 3323 |
| expression_statement | REV_GUARDS | for | 60 |
| expression_statement | REV_GUARDS | if | 1658 |
| expression_statement | REV_GUARDS | while | 36 |
| for | GUARDS | expression_statement | 60 |
| for | GUARDS | if | 21 |
| for | GUARDS | new_variable | 34 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | expression_statement | 24 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | expression_statement | 1658 |
| if | GUARDS | if | 173 |
| if | GUARDS | new_variable | 81 |
| if | GUARDS | return | 90 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | expression_statement | 546 |
| if | REV_GUARDS | for | 21 |
| if | REV_GUARDS | if | 173 |
| if | REV_GUARDS | while | 13 |
| new_variable | REV_GUARDS | expression_statement | 575 |
| new_variable | REV_GUARDS | for | 34 |
| new_variable | REV_GUARDS | if | 81 |
| new_variable | REV_GUARDS | while | 8 |
| return | REV_GUARDS | expression_statement | 249 |
| return | REV_GUARDS | if | 90 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | expression_statement | 36 |
| while | GUARDS | if | 13 |
| while | GUARDS | new_variable | 8 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |

### access_control_node：全部新增GUARDS规范关系

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | expression_statement | 2562 |
| expression_statement | GUARDS | for | 20 |
| expression_statement | GUARDS | if | 166 |
| expression_statement | GUARDS | new_variable | 237 |
| expression_statement | GUARDS | return | 240 |
| expression_statement | GUARDS | while | 18 |
| expression_statement | REV_GUARDS | expression_statement | 2562 |
| expression_statement | REV_GUARDS | for | 58 |
| expression_statement | REV_GUARDS | if | 678 |
| expression_statement | REV_GUARDS | while | 42 |
| for | GUARDS | expression_statement | 58 |
| for | GUARDS | if | 21 |
| for | GUARDS | new_variable | 33 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | expression_statement | 20 |
| for | REV_GUARDS | if | 1 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | expression_statement | 678 |
| if | GUARDS | for | 1 |
| if | GUARDS | if | 185 |
| if | GUARDS | new_variable | 90 |
| if | GUARDS | return | 115 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | expression_statement | 166 |
| if | REV_GUARDS | for | 21 |
| if | REV_GUARDS | if | 185 |
| if | REV_GUARDS | while | 14 |
| new_variable | REV_GUARDS | expression_statement | 237 |
| new_variable | REV_GUARDS | for | 33 |
| new_variable | REV_GUARDS | if | 90 |
| new_variable | REV_GUARDS | while | 8 |
| return | REV_GUARDS | expression_statement | 240 |
| return | REV_GUARDS | if | 115 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | expression_statement | 42 |
| while | GUARDS | if | 14 |
| while | GUARDS | new_variable | 8 |
| while | GUARDS | while | 2 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |
| while | REV_GUARDS | while | 2 |

## 稀疏新增规范关系（边数小于20）

### reentrancy_node：新增关系中边数小于20

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | while | 18 |
| for | GUARDS | while | 2 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | while | 13 |
| new_variable | REV_GUARDS | while | 8 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | if | 13 |
| while | GUARDS | new_variable | 8 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |

### access_control_node：新增关系中边数小于20

| 源类型 | 关系 | 目标类型 | 边数 |
|---|---|---|---:|
| continue_statement | REV_GUARDS | expression_statement | 1 |
| continue_statement | REV_GUARDS | if | 2 |
| continue_statement | REV_GUARDS | while | 1 |
| expression_statement | GUARDS | continue_statement | 1 |
| expression_statement | GUARDS | while | 18 |
| for | GUARDS | while | 2 |
| for | REV_GUARDS | if | 1 |
| if | GUARDS | continue_statement | 2 |
| if | GUARDS | for | 1 |
| if | GUARDS | while | 6 |
| if | REV_GUARDS | while | 14 |
| new_variable | REV_GUARDS | while | 8 |
| while | GUARDS | continue_statement | 1 |
| while | GUARDS | if | 14 |
| while | GUARDS | new_variable | 8 |
| while | GUARDS | while | 2 |
| while | REV_GUARDS | expression_statement | 18 |
| while | REV_GUARDS | for | 2 |
| while | REV_GUARDS | if | 6 |
| while | REV_GUARDS | while | 2 |

## 测试与开发失败记录

完整CPU回归：EdgeSem 198、NodeSem 1353、DFG v2 2653，合计4204项通过，无跳过。新增19项守卫/归档用例及2项真实模型闸门；原EP2模型测试仍运行。覆盖require、时间/假分支极性、内部检查多证据、双修饰器/继承、基类构造unknown、未知情况下保留已知边、early_exit、算术、循环/条件目标、缺失精确来源、非法GUARDS角色、输入不变与归档摘要篡改拒绝。

首次guard_unit_tests为35 passed、1 failed：诊断代码错误地只查询ClosedScopeJ.declarations，它仅包含合约成员，不包含合约声明，因此基类构造函数名的声明类型为空。修正为使用冻结AstSemantics.resolve_identifier输出声明类型，同时保留modifier_scope_declaration_types/anchors原查询结果。这个修正只影响描述，不修改任何绑定、守卫或边选择规则。失败日志与原guard_edges源码快照保存在execution/和development/，修正后的guard_unit_identifier为36 passed。未覆盖失败现场，真实建边与模型闸门均一次通过，无训练重试。

最终只读ep3_verify核对750份冻结源码、354项DFG计算引用、60份其他EdgeSem源码、389份历史产物、697项输入引用和8H load。按原源码重新取得每个语句的冻结守卫序列，逐条核对JSONL的节点身份、锚点、来源、极性、原始操作数类别、顺序及全部证据；同时核对EP2行、逐节点入度及模型canonical边数。移除内存副本新增边后，指纹必须与原F3完全相同。验证收据见verification.json；三文档原字节前缀保持且UTF-8/中文检查通过。

## 执行命令

实际命令（mando、CPU；TREE_SITTER_LIB_DIR沿用原值，PYTHONDONTWRITEBYTECODE=1，OMP/MKL各2）：

    python -B -m scripts.edge_sem.recon.ep3_common
    python -B -m scripts.edge_sem.recon.ep3_run --name guard_unit_identifier -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_build_f4_guards.py scripts/edge_sem/tests/test_build_f4_calls.py
    python -B -m scripts.edge_sem.recon.ep3_run --name build_reentrancy_node -- -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/ep3_v1/reentrancy_node
    python -B -m scripts.edge_sem.recon.ep3_run --name build_access_control_node -- -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/ep3_v1/access_control_node
    python -B -m scripts.edge_sem.recon.ep3_run --name edge_tests -- -m pytest -q -p no:cacheprovider scripts/edge_sem/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name nodesem_tests -- -m pytest -q -p no:cacheprovider scripts/node_sem/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name dfg_tests -- -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
    python -B -m scripts.edge_sem.recon.ep3_run --name collect_report -- -m scripts.edge_sem.recon.ep3_report
    python -B -m scripts.edge_sem.recon.ep3_run --name doc_check -- -m scripts.node_sem.doc_check --expect-cjk HANDOVER.md:293293 docs/training_changes_2026-10-07.md:1087897 scripts/edge_sem/PROGRESS.md:37100 scripts/edge_sem/EP3_REPORT.md
    python -B -m scripts.edge_sem.recon.ep3_run --name verify -- -m scripts.edge_sem.recon.ep3_verify

首次完整EdgeSem回归设置EDGESEM_EP3_RECEIPTS为本批probes绝对路径，成功后排他写两份CPU收据。日常测试不设置它；所有输出目录/收据拒绝覆盖。精确argv、耗时、退出码与日志SHA存于execution/。不要再次运行这些命令覆盖已完成批次。

## 局限与停止位置

GUARDS表达冻结分析器支持范围内的词法/受限调用守卫证据，不证明完整控制依赖、授权正确性或漏洞防护有效。MOD_APPLY、CALL_SITE、GUARDS三种E1关系现已接入；E2边属性、EdgeAware层、正式执行器与效果评估仍属于后续Prompt，EP3不实现EP4。现有loop_cond操作数为空、unknown及调用覆盖局限保留。EP0e原312/347门槛未通过的历史结论不改写。

最终实验将在显存充足的服务器另建批次，本机RTX3050 4GiB仅限制当前开发；本轮未部署服务器、未测GPU显存、未训练。产物保存在WSL，未向C盘另存大型缓存。D1主视图、D2训练协议与D3七类冻结仍须在训练前按文档确认；本轮没有据CPU夹具默认批准它们。按共享流程本地提交，停在EP3，不自动push。


# EP4：通用F4、74维属性与端点检验（2026-11-10，修改AI：Codex）

按PROMPTS.md r11完成EP4：通用F4构建、74维边属性、两任务端点检验与共同核心位。属性从原名源码、冻结事实和封存L1–L3证据计算；反向边留模型接入时复制正向向量。本轮未训练、未用GPU，没有检测性能或显存结论。旧图、标签、折、特征、初值、checkpoint和计划不改。

## 通用构建与历史一致性

生产build_f4/guard_edges去除recon和EP2/EP0运行依赖；历史比对移至recon/ep4_rebuild.py。新manifest版本edgesem-f4-v1，默认加载拒绝旧版本；历史产物显式只读核验。两个节点任务的新边与EP3逐字节一致，守卫分类和映射计数不变。

| 任务 | MOD_APPLY | CALL_SITE | GUARDS | 守卫记录 | 普通映射 | modifier映射 | unknown目标 |
|---|---|---|---|---|---|---|---|
| access_control_contract | 526 | 1247 | 8098 | 8165 | 6767/6767 | 1398/1398 | 59 |
| access_control_node | 195 | 564 | 4502 | 4537 | 3822/3822 | 715/715 | 12 |
| reentrancy_contract | 547 | 1317 | 10172 | 10274 | 8928/8928 | 1346/1346 | 18 |
| reentrancy_node | 178 | 570 | 6921 | 6956 | 6340/6340 | 616/616 | 12 |


合约任务只验证通用构建入口，不进入本机E-A/E-B。重入合约549个modifier应用去重为547条边；访问控制527个去重为526条。旧EP0访问控制计数528额外遍历了一个fallback_receive_definition，正式MOD_APPLY固定仅针对function_definition/constructor_definition。文件0x0d689d1d3ef39e379329d9fc88eabceccc1215a0.sol，源码SHA ac6e70721c9d4ff51c6c6653195b62892672321253cf38883bd5d4d771bb82de，fallback偏移3383，modifier跨度3409–3418。未扩展规则迎合旧计数；守卫记录10274/8165均与EP0一致，映射缺失为0。证据见development/contract_scope.py及execution/contract_scope.log。

## 属性产物和端点筛选

| 任务 | 属性行 | 全零行 | 全零比例 | 含缺项/未知诊断行 |
|---|---|---|---|---|
| access_control_node | 21830 | 2728 | 12.497% | 9530 |
| reentrancy_node | 31372 | 2786 | 8.881% | 14562 |


有效目录：scripts/edge_sem/artifacts/ep4_v1/attributes_attempt3。每任务有attrs.npz、manifest/seal、stats.json、diagnostics.json、fact_provenance.json和endpoint_test.json；共同layout/selection封存74维布局和共同筛选。uint8二值矩阵通过文件、端点、关系及多重边序号精确对齐；来源SHA、行序及numeric_digest均核验。

核心46维：[0, 1, 2, 5, 7, 8, 9, 10, 11, 12, 13, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 32, 34, 35, 36, 37, 39, 40, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 68, 69, 71, 72]。

上下文26维：[3, 4, 16, 18, 30, 41, 42, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 69, 70, 71, 72, 73]；unknown位可同时属于两组。

两任务都全零而未纳入核心的候选：[6, 14, 33, 38]；第15位始终停用。

| 核心位 | 名称 | 共同决定 |
|---|---|---|
| 0 | ctrl_src_dominates_dst | undetermined |
| 1 | ctrl_dst_postdominates_src | undetermined |
| 2 | ctrl_branch_contains_ext_call | undetermined |
| 5 | var_kind_return_var | undetermined |
| 7 | value_shape_mapping | core |
| 8 | value_shape_array | core |
| 9 | value_shape_address | core |
| 10 | value_shape_integer | core |
| 11 | value_shape_bool | undetermined |
| 12 | value_shape_bytes_string | core |
| 13 | value_shape_struct_contract | core |
| 17 | def_kind_compound | undetermined |
| 19 | def_kind_incdec_or_delete | core |
| 20 | def_loop_carried | core |
| 21 | use_path_crosses_ext_call | core |
| 22 | use_context_condition | core |
| 23 | use_context_call | core |
| 24 | use_context_arithmetic | undetermined |
| 25 | use_context_state_write_value | core |
| 26 | use_context_return | core |
| 27 | arith_op_additive | undetermined |
| 28 | arith_op_multiplicative | undetermined |
| 29 | arith_op_exponent | undetermined |
| 31 | write_access_indexed | core |
| 32 | write_access_member | undetermined |
| 34 | write_op_assign | core |
| 35 | write_op_increase | undetermined |
| 36 | write_op_decrease | undetermined |
| 37 | call_low_level | undetermined |
| 39 | call_sends_value | undetermined |
| 40 | call_return_checked | undetermined |
| 43 | guard_kind_require | core |
| 44 | guard_kind_if_branch | core |
| 45 | guard_kind_early_exit | core |
| 46 | guard_kind_loop_cond | core |
| 47 | guard_kind_modifier | core |
| 48 | guard_kind_internal_check | undetermined |
| 49 | guard_operands_caller_identity | core |
| 50 | guard_operands_block_time | core |
| 51 | guard_operands_amount_balance | core |
| 52 | guard_operands_external_result | core |
| 53 | guard_operands_hash | core |
| 68 | unk_cfg | unknown位随限定字段归组 |
| 69 | unk_dfg | unknown位随限定字段归组 |
| 71 | unk_state | unknown位随限定字段归组 |
| 72 | unk_guard | unknown位随限定字段归组 |


门槛固定：同关系同侧至少2条边且至少一条为1才算合格；汇总合格数≥30且恒定比例≥99%时移入上下文。任一任务判为端点便移出共同核心；两侧不足30则保留并标未判定。未判定不等于已证明是独立边信息。unknown位随限定字段归组，不参与端点检验。筛选不使用标签或模型分数。

需要保留的实质局限：共同核心里有17个已知属性位仍是样本量不足的未判定项；它们按预登记规则保留，不作为新增独立信息已获证实。READS_STATE/ENV_FLOW等关系的use_context没有精确dfg.to来源，全0不表示没有上下文；end_if和部分控制边缺少可映射的语义CFG端点，unk_cfg比例高。后续解释与规则基线须读取相应unknown/缺口记录，本轮不扩展冻结事实来填补。

## 每关系每组非零比例

### access_control_node

| 关系 | 边数 | 全零 | control | var_kind | value_shape | def_kind | data_path | use_context | arith_op | write_access | write_op | call | guard_kind | guard_operands | context | env_kind | unknown | library |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CALL_SITE | 564 | 2.660% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 26.950% | 0.000% | 0.000% | 69.504% | 0.000% | 11.879% | 62.057% |
| DATA_DEF_USE | 3923 | 0.000% | 0.000% | 100.000% | 98.929% | 98.751% | 33.520% | 12.388% | 0.357% | 0.000% | 0.000% | 0.688% | 0.000% | 0.000% | 96.227% | 0.000% | 3.135% | 0.000% |
| ENV_FLOW | 1948 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.846% | 85.010% | 4.825% | 0.000% |
| GUARDS | 4502 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 57.774% | 88.627% | 0.000% | 20.347% | 0.000% |
| MOD_APPLY | 195 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.487% | 85.641% | 100.000% | 0.000% | 0.000% | 0.000% |
| READS_STATE | 1091 | 0.000% | 0.000% | 0.000% | 92.851% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 98.350% | 0.000% | 24.198% | 0.000% |
| WRITES_STATE | 767 | 0.000% | 0.000% | 0.000% | 89.570% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 98.044% | 0.000% | 0.000% | 0.000% | 84.355% | 0.000% | 22.034% | 0.000% |
| end_if | 221 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 31.674% | 0.000% | 100.000% | 0.000% |
| external_call | 688 | 68.023% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 5.523% | 0.000% | 0.000% | 29.797% | 0.000% | 0.000% | 0.000% |
| first_next_line | 73 | 0.000% | 1.370% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 93.151% | 0.000% | 98.630% | 0.000% |
| internal_call | 591 | 10.660% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 48.223% | 0.000% | 0.000% | 69.036% | 0.000% | 0.000% | 0.000% |
| neg_next | 239 | 0.000% | 26.360% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 34.728% | 0.000% | 74.895% | 0.000% |
| next_line | 4614 | 0.000% | 83.875% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 87.169% | 0.000% | 16.558% | 0.000% |
| pos_next | 232 | 0.000% | 81.897% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 85.776% | 0.000% | 28.017% | 0.000% |
| recursive_method_call | 2182 | 100.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% |


| 关系 | unk_cfg | unk_dfg | unk_order | unk_state | unk_guard |
|---|---|---|---|---|---|
| CALL_SITE | 0 / 0.000% | 0 / 0.000% | 67 / 11.879% | 0 / 0.000% | 0 / 0.000% |
| DATA_DEF_USE | 0 / 0.000% | 93 / 2.371% | 54 / 1.376% | 0 / 0.000% | 0 / 0.000% |
| ENV_FLOW | 0 / 0.000% | 92 / 4.723% | 54 / 2.772% | 0 / 0.000% | 8 / 0.411% |
| GUARDS | 0 / 0.000% | 0 / 0.000% | 916 / 20.347% | 0 / 0.000% | 2 / 0.044% |
| MOD_APPLY | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| READS_STATE | 0 / 0.000% | 250 / 22.915% | 166 / 15.215% | 9 / 0.825% | 12 / 1.100% |
| WRITES_STATE | 0 / 0.000% | 169 / 22.034% | 132 / 17.210% | 0 / 0.000% | 0 / 0.000% |
| end_if | 221 / 100.000% | 0 / 0.000% | 56 / 25.339% | 0 / 0.000% | 0 / 0.000% |
| external_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| first_next_line | 72 / 98.630% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| internal_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| neg_next | 177 / 74.059% | 0 / 0.000% | 64 / 26.778% | 0 / 0.000% | 0 / 0.000% |
| next_line | 744 / 16.125% | 0 / 0.000% | 370 / 8.019% | 0 / 0.000% | 12 / 0.260% |
| pos_next | 53 / 22.845% | 0 / 0.000% | 65 / 28.017% | 0 / 0.000% | 1 / 0.431% |
| recursive_method_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |


来源缺口：{"no_exact_dfg_to_for_this_edge": 6550, "target_dfg_inapplicable_var_kind_from_sealed_symbol": 22}。

### reentrancy_node

| 关系 | 边数 | 全零 | control | var_kind | value_shape | def_kind | data_path | use_context | arith_op | write_access | write_op | call | guard_kind | guard_operands | context | env_kind | unknown | library |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CALL_SITE | 570 | 2.456% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 27.895% | 0.000% | 0.000% | 72.632% | 0.000% | 9.825% | 63.860% |
| DATA_DEF_USE | 3469 | 0.000% | 0.000% | 100.000% | 98.789% | 98.645% | 50.649% | 31.450% | 0.922% | 0.000% | 0.000% | 6.486% | 0.000% | 0.000% | 95.734% | 0.000% | 3.488% | 0.000% |
| ENV_FLOW | 3200 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.906% | 93.562% | 2.594% | 0.000% |
| GUARDS | 6921 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 64.153% | 93.484% | 0.000% | 10.779% | 0.000% |
| MOD_APPLY | 178 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.438% | 84.831% | 100.000% | 0.000% | 0.000% | 0.000% |
| READS_STATE | 3070 | 0.000% | 0.000% | 0.000% | 96.059% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 99.414% | 0.000% | 8.404% | 0.000% |
| WRITES_STATE | 2254 | 0.000% | 0.000% | 0.000% | 95.031% | 0.000% | 0.000% | 0.000% | 0.000% | 100.000% | 98.846% | 0.000% | 0.000% | 0.000% | 94.676% | 0.000% | 7.542% | 0.000% |
| end_if | 379 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 63.325% | 0.000% | 100.000% | 0.000% |
| external_call | 707 | 66.195% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 12.588% | 0.000% | 0.000% | 31.683% | 0.000% | 0.000% | 0.000% |
| first_next_line | 67 | 0.000% | 1.493% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 2.985% | 0.000% | 98.507% | 0.000% |
| internal_call | 464 | 12.284% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 45.690% | 0.000% | 0.000% | 63.793% | 0.000% | 0.000% | 0.000% |
| neg_next | 1083 | 0.000% | 6.094% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 83.657% | 0.000% | 94.090% | 0.000% |
| next_line | 6355 | 0.000% | 78.993% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 80.661% | 0.000% | 21.353% | 0.000% |
| pos_next | 408 | 0.000% | 92.647% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 94.118% | 0.000% | 12.990% | 0.000% |
| recursive_method_call | 2247 | 100.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% |


| 关系 | unk_cfg | unk_dfg | unk_order | unk_state | unk_guard |
|---|---|---|---|---|---|
| CALL_SITE | 0 / 0.000% | 0 / 0.000% | 56 / 9.825% | 0 / 0.000% | 0 / 0.000% |
| DATA_DEF_USE | 0 / 0.000% | 91 / 2.623% | 54 / 1.557% | 0 / 0.000% | 0 / 0.000% |
| ENV_FLOW | 0 / 0.000% | 80 / 2.500% | 46 / 1.438% | 0 / 0.000% | 8 / 0.250% |
| GUARDS | 0 / 0.000% | 0 / 0.000% | 746 / 10.779% | 0 / 0.000% | 2 / 0.029% |
| MOD_APPLY | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| READS_STATE | 0 / 0.000% | 244 / 7.948% | 114 / 3.713% | 9 / 0.293% | 12 / 0.391% |
| WRITES_STATE | 0 / 0.000% | 169 / 7.498% | 96 / 4.259% | 0 / 0.000% | 0 / 0.000% |
| end_if | 379 / 100.000% | 0 / 0.000% | 39 / 10.290% | 0 / 0.000% | 0 / 0.000% |
| external_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| first_next_line | 66 / 98.507% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| internal_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |
| neg_next | 1017 / 93.906% | 0 / 0.000% | 44 / 4.063% | 0 / 0.000% | 0 / 0.000% |
| next_line | 1335 / 21.007% | 0 / 0.000% | 308 / 4.847% | 0 / 0.000% | 12 / 0.189% |
| pos_next | 41 / 10.049% | 0 / 0.000% | 53 / 12.990% | 0 / 0.000% | 1 / 0.245% |
| recursive_method_call | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% | 0 / 0.000% |


来源缺口：{"no_exact_dfg_to_for_this_edge": 10195, "target_dfg_inapplicable_var_kind_from_sealed_symbol": 22}。

stats.json另保存每位在原作者正/负目标节点入边中的比例。正负按node_info_vulnerabilities原规则（None为0，非None为1，env排除），不是L-audit；只在属性、筛选与seal完成后读取，不参与特征、样本、阈值或核心位决定。

## 已批准调整与边界

1. call_3ed2f55f68424011a5631df0cab83e86：同一数据边可能承载多个变量。var_kind/value_shape按全部证据取并为多热，仍74维，不拆边、不任选一个变量；其他单热组不变。
2. 同一批准：use_context仅从当前src/dst精确匹配的dfg.to取sink。READS_STATE/ENV_FLOW的源缺少该字段，WRITES_STATE及参数入口等可能无匹配，置0并记录source_gaps；不发明上下文。相应call/arith位仍受已知use_context限制。
3. call_ce3526a147bb49c0bb210e8a9c1349a6：五个unk位未覆盖全部未知来源；函数汇总、返回值处理、版本区间等未知置0，并逐边记录unknown_fields原因，不加维或借用其他unk含义；这些0不证明已确认不存在。
4. call_52397237416e41b3baa8612deb0ad2b4：首次因int原节点ID与str环境ID排序失败，改用保留类型和顺序的事实行数组计算摘要。旧attributes目录、失败日志和旧源码保留，批准后新建attributes_attempt2；没有生成NPZ，也没有训练。
5. call_fa5c42293d4747daa5a6ad5932843d4d：第二次发现两任务各22条依赖指向for头i++，冻结NodeSem将raw update_expression归other，dfg整组为空；仅此时从已精确核验的封存L1 symbol取var_kind并记录来源，非空facts不一致仍失败。未改NodeSem、DFG、图或事实，批准后新建attributes_attempt3。44条证据保存在development/dfg_target_diagnosis.json。
6. MOD_APPLY通过调用F取得守卫并按inner_anchor落入M过滤；空函数体仍有效，只加锁modifier无守卫时为0且不是unknown。GUARDS所有evidence取并，每任务12个unknown目标保留。
7. 冻结loop_cond操作数为空，49–54仍0；x=x+1记assign，其他未列写操作保持0；env14个保留键只映射表中四类。recursive_method_call全零。语义CFG或类型缺口按unk及sidecar记录，不宣称完整程序语义。

## 验证与失败保留

- edge_tests_final：238 passed, 4 warnings in 464.95s (0:07:44)；exit 0。

- nodesem_tests：1353 passed, 4 warnings in 28.66s；exit 0。

- dfg_tests：2653 passed, 9 warnings in 192.39s (0:03:12)；exit 0。

- attrs_target_complete：34 passed, 4 warnings in 4.19s；exit 0。

定向测试覆盖74维、多证据类型、循环/调用路径、call返回检查、modifier独立来源、守卫操作数、unknown、端点门槛、快速改名、标签扰动不变、错误source/layout/图/数组拒绝、混合ID摘要及空dfg来源。
开发失败日志也保留：选择器误命中函数全文；参数入口没有dfg.to；tuple调用选择器需完整前缀；全零unknown测试必须提供正例才能测试继承；新循环测试的旧夹具没建raw update节点，补真实节点角色后通过。诊断脚本直接按路径启动缺包导入，改为-m入口。上述未改变冻结分析器，也不是训练或seed重复。
最终ep4_verify重新核对冻结源码、旧产物、8H只读load、DFG_code_refs、原图指纹/节点/原边、EP3边字节、属性行序与摘要、守卫并集、library和unknown位、端点筛选与统计重算。三文档原字节前缀保持，UTF-8/中文检查通过后提交；机器收据为artifacts/ep4_v1/verification.json。

## 文件与实际命令

生产代码：io.py、attrs.py、attr_sources.py、attr_batch.py、attr_stats.py及build_f4/guard_edges最小解耦；tests/test_f4_generic.py、test_attrs.py、test_attr_store.py与ep4_attributes.sol；recon/ep4_*为基线、只读历史比较、记录器、报告与核验。
生产入口为python -B -m scripts.edge_sem.attr_batch --out <新的目录>。write_attributes(task_id,out_dir)同样完成两个任务共同筛选，再返回指定任务manifest。所有目录拒绝覆盖。以下为实际运行命令，包含失败和诊断；不可原路径重复执行覆盖现场。

- attr_loader_boundary（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attr_store.py

- attributes_build（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes

- attributes_build_attempt2（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes_attempt2

- attributes_build_attempt3（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.attr_batch --out scripts/edge_sem/artifacts/ep4_v1/attributes_attempt3

- attrs_storage_identity_fix（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_target_complete（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_target_facts_fix（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py scripts/edge_sem/tests/test_attr_store.py

- attrs_unit_complete（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_exact_selectors（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_final（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_initial（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- attrs_unit_source_corrected（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_attrs.py

- build_access_control_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task access_control_contract --out scripts/edge_sem/artifacts/f4_v1/access_control_contract

- build_access_control_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task access_control_node --out scripts/edge_sem/artifacts/f4_v1/access_control_node

- build_reentrancy_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task reentrancy_contract --out scripts/edge_sem/artifacts/f4_v1/reentrancy_contract

- build_reentrancy_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.build_f4 --task reentrancy_node --out scripts/edge_sem/artifacts/f4_v1/reentrancy_node

- contract_scope（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.contract_scope

- dfg_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests

- diagnose_dfg_target（exit=1）： /home/zhao/miniconda3/envs/mando/bin/python -B scripts/edge_sem/artifacts/ep4_v1/development/diagnose_dfg_target.py

- diagnose_dfg_target_module（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.diagnose_dfg_target

- diagnose_initial（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.artifacts.ep4_v1.development.diagnose_initial

- edge_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests

- edge_tests_final（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests

- generic_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/edge_sem/tests/test_f4_generic.py scripts/edge_sem/tests/test_build_f4_guards.py scripts/edge_sem/tests/test_build_f4_calls.py

- nodesem_tests（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests

- verify_access_control_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task access_control_contract

- verify_access_control_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task access_control_node

- verify_reentrancy_contract（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task reentrancy_contract

- verify_reentrancy_node（exit=0）： /home/zhao/miniconda3/envs/mando/bin/python -B -m scripts.edge_sem.recon.ep4_rebuild --task reentrancy_node

## 后续与停止位置

EP4完成属性准备，不证明检测提升。EP5真实全量改名/可达性闸门、EP6边感知层与EP7以后计划/训练尚未执行；快速fixture改名测试不能替代EP5。
D1匿名主视图、D2 P2协议、D3七类冻结仍须训练前确认，原名属性计算或历史夹具不构成授权。最终实验将在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机开发限制；本轮未部署服务器、未更改训练配置。产物留WSL，未向C盘另写大型缓存。按共享流程本地提交，停在EP4，不自动push。


## 2026-11-11 EdgeSem EP5完成：不变性、可达性与安慰剂（修改AI：Codex）

完成EP5，未训练或用GPU。第20位重入311→61、访问控制322→68；edge_keys及其他73列严格不变。核心46→50，新增全零候选6/14/33/38，上下文26维不变；后续EP6–EP9读取ep5_v1/attributes。

128个实例均检查通过：54个实际改名、74个原文回退；回退不作为非平凡不变性证据。用户批准状态初始化callable和唯一neg_next/AST锚定end_if适配，冻结模块未改。49条循环头上下文例外保留；统计按历史store双摘要修复后在新目录恢复。所有失败、快照和批准记录保留。

21例中，重入modifier_reentrancy.sol节点8498及reentrancy_bonus.sol节点12各增加2个两跳证据节点；其余19个不变，访问控制15个均无增量。仅为路径诊断，不证明检测改善。两种安慰剂分别保持逐节点canonical度数和关系内属性多重集，未变化的分组和向量均披露。

三套CPU回归4274项通过。详见EP5_REPORT.md、训练变更§108及ep5_v1/verification.json。最终实验在显存充足服务器另建批次，RTX3050 4GiB仅为当前本机限制；产物留WSL。停在EP5，本地提交，不自动push。

| 任务 | 正向属性行 | 原第20位=1 | 新第20位=1 | 循环头例外 |
| --- | --- | --- | --- | --- |
| 重入节点 | 31372 | 311 | 61 | 24 |
| 访问控制节点 | 21830 | 322 | 68 | 25 |

| 任务 | 文件实例 | 实际改名通过 | 原文回退通过 |
| --- | --- | --- | --- |
| 重入节点 | 71 | 30 | 41 |
| 访问控制节点 | 57 | 24 | 33 |

| 任务 | 文件 / source SHA前12位 | 图节点ID | G3R | G3R-T | G4R | 增加 |
| --- | --- | --- | --- | --- | --- | --- |
| 重入节点 | etherbank.sol / 63d14a7dd1a1 | 15759 | 2 | 2 | 2 | 0 |
| 重入节点 | modifier_reentrancy.sol / 5675bc25a679 | 8498 | 5 | 5 | 7 | 2 |
| 重入节点 | reentrancy_bonus.sol / 628f60b16c87 | 12 | 3 | 3 | 5 | 2 |
| 重入节点 | reentrancy_dao.sol / e507ae792671 | 8315 | 5 | 5 | 5 | 0 |
| 重入节点 | spank_chain_payment.sol / 15724a9aecd2 | 12958 | 95 | 95 | 95 | 0 |
| 重入节点 | spank_chain_payment.sol / 15724a9aecd2 | 12961 | 95 | 95 | 95 | 0 |
| 访问控制节点 | FibonacciBalance.sol / d54dc819f08b | 10581 | 4 | 4 | 4 | 0 |
| 访问控制节点 | FibonacciBalance.sol / d54dc819f08b | 10583 | 2 | 2 | 2 | 0 |
| 访问控制节点 | arbitrary_location_write_simple.sol / bbbdb5367463 | 11472 | 5 | 5 | 5 | 0 |
| 访问控制节点 | mapping_write.sol / a4c6ab0924fe | 12959 | 2 | 2 | 2 | 0 |
| 访问控制节点 | multiowned_vulnerable.sol / ee0df823e630 | 3174 | 3 | 3 | 3 | 0 |
| 访问控制节点 | proxy.sol / 3016dcfca805 | 8854 | 0 | 0 | 0 | 0 |
| 访问控制节点 | rubixi.sol / a4c33aa1b035 | 11356 | 2 | 2 | 2 | 0 |
| 访问控制节点 | rubixi.sol / a4c33aa1b035 | 11357 | 6 | 6 | 6 | 0 |
| 访问控制节点 | simple_suicide.sol / 07ab4f0b502c | 12756 | 1 | 1 | 1 | 0 |
| 访问控制节点 | simple_suicide.sol / 07ab4f0b502c | 12757 | 0 | 0 | 0 | 0 |
| 访问控制节点 | unprotected0.sol / 8cfc8702a1a0 | 10847 | 2 | 2 | 2 | 0 |
| 访问控制节点 | wallet_02_refund_nosub.sol / 3bf849eea5a2 | 11913 | 7 | 7 | 7 | 0 |
| 访问控制节点 | wallet_03_wrong_constructor.sol / 6f5e18f2dbfb | 7893 | 1 | 1 | 1 | 0 |
| 访问控制节点 | wallet_03_wrong_constructor.sol / 6f5e18f2dbfb | 7894 | 6 | 6 | 6 | 0 |
| 访问控制节点 | wallet_04_confused_sign.sol / 5ec3d85c76b1 | 9865 | 6 | 6 | 6 | 0 |

| 任务 | 剖面 | 节点数 | 反射后边数 | canonical关系数 | 关系名数 |
| --- | --- | --- | --- | --- | --- |
| 重入节点 | G3R | 12223 | 47406 | 212 | 16 |
| 重入节点 | G3R-T | 12223 | 47406 | 220 | 24 |
| 重入节点 | G4R | 12223 | 62744 | 274 | 30 |
| 重入节点 | G4R-P | 12223 | 62744 | 274 | 30 |
| 访问控制节点 | G3R | 7892 | 33138 | 225 | 16 |
| 访问控制节点 | G3R-T | 7892 | 33138 | 234 | 24 |
| 访问控制节点 | G4R | 7892 | 43660 | 292 | 30 |
| 访问控制节点 | G4R-P | 7892 | 43660 | 292 | 30 |

| 任务 | E1边 | 最终改变的边 | 零次改接分组/全部 | 属性实际变化行/全部 |
| --- | --- | --- | --- | --- |
| 重入节点 | 7669 | 5805 | 195/487 | 25679/31372 |
| 访问控制节点 | 5261 | 3444 | 184/393 | 16309/21830 |

| 套件 | 通过 | 秒 | 收据 |
| --- | --- | --- | --- |
| EdgeSem | 268 | 499.83 | edge_tests.json |
| NodeSem | 1353 | 26.07 | nodesem_tests.json |
| DFG v2 | 2653 | 163.51 | dfg_tests.json |

实施选择：循环内同节点自依赖例外；最外层循环头保留第59位；初始化callable按精确AST翻译；歧义end_if仅允许唯一neg_next锚点；历史图采用store的双摘要。各次批准、首次失败及新attempt均见ep5_v1记录，完整解释和命令见报告。

文件：attrs.py、attr_sources.py、placebo.py；recon/ep5_common、ep5_run、ep5_delta、ep5_loop_context、ep5_anon、ep5_anon_run、ep5_projection_diagnostic、ep5_topology、ep5_verify、ep5_report；test_attrs.py、test_ep5_anon.py、test_ep5_topology.py、test_placebo.py。逐关系统计/逐类型均入度见报告和topology_attempt2/<task>/graph_statistics.json。


### EP5 收尾验收修正与恢复批准（2026-11-11，Codex）

报告写入曾两次遇到自动审批服务超时；经正常审批的短WSL命令及临时文件写入/回读/删除成功，改为分段写入后已恢复。未修改审批、沙箱或代理设置，服务端根因没有证据，不能称审批服务本身已修复。

最终验收首次因逐文件数字摘要的行顺序不同而停止：原闸门使用文件子图遍历顺序，验收器错误使用整图过滤顺序。只读核对发现80/128个文件顺序不同；恢复原生成顺序后128/128份封存摘要全部匹配，边身份和向量不变。新增3项定向回归通过，覆盖顺序差异、向量篡改/缺失及空文件。原三套回归4274项通过记录保留。

用户批准保留首次验收收据、旧验收器及诊断，在verify_attempt2收据下继续最终验收和本地提交。批准见ep5_v1/verification_resume1.json；最终结果见execution/verify_attempt2.json和verification.json。未重算属性、未重跑匿名闸门、未训练。EP5_REPORT.md及initial summary保持写入时字节；本段补充其后发生的验收修正。


## EP6完成：r14前置修正与边感知HGT（2026-11-11）

已完成四任务f4_v2、两节点任务新属性和名字不变性核验，接通G4R-A / G4R-Api / G4R-AC / G3R-TA。用户批准call_1c4fc0064fb94266be56b656e6399928，按封存符号调用冻结sink补齐参数入口，已有记录严格比对。原图、旧产物与冻结实现保留。报告：scripts/edge_sem/EP6_REPORT.md。

四任务F4边集合均不变；访问控制合约的1个fallback修饰器绑定成功，但冻结投影为not_in_graph，因此未加边。补齐重入1,727条、访问控制2,941条边；仅指定列0→1，其余逐位相同。实际改名54文件通过，74回退只作原文对照；core/context仍50/26位。

真实重入fold0 CPU：新增92,784参数、零初值最大差0、前向1.43秒、反向2.28秒，共享参数逐位一致，optimizer_steps=0，未用GPU。最终4,300项测试通过（EdgeSem294、NodeSem1353、DFG2653）；归档SHA失败保留，修复只读快照核验后定向复核。没有正式训练或检测收益结论。

最终实验将在显存充足的服务器运行；当前限制仅来自本机。EP7须独立计划与授权，本轮本地提交，不自动推送。


## 2026-11-11 — EdgeSem EP7 实现与训练前封存

已完成 G4R-P、P2 执行器及训练前 CPU 验收；报告 scripts/edge_sem/EP7_REPORT.md，命令 scripts/edge_sem/EP7_README.md。尚未启动 GPU：探针0/8、范数试点0/1、正式G3R 0/20，D1–D3和本轮训练授权待确认。registration.json须先提交；计划保持execution_authorized=false，批准后另建decisions和执行授权，不修改旧seal。

用户批准call_fa9553b4bee0410b8b1dfa2fcc7c490b的两项接入调整：冻结trainer无校验替换接口，允许EdgeSem中带来源SHA的最小适配副本（只换校验/审计导入）；范数试点另设train_only，禁止验证/测试评分及best选择。正式_fit/fit的AST与原版相同，小图CPU三轮参数、损失、预测、Adam及OneCycle状态逐位一致。冻结源码、图、标签、折和历史产物未改。

三套回归4318通过（EdgeSem312、NodeSem1353、DFG2653）。两任务G4R-P逐节点规范度数保持，初值与G4R逐位相同；改边5834/7669与3487/5261。26份零步初值已封存并重载，约524.6 MiB，本地权重不纳入普通Git上传。核验750份冻结源码、1134份历史产物，8H入口仍通过，历史文档前缀不变。

本轮新鲜G3R锚初值与8H配对初值不同，按原设计保留；将来与8H只作描述性对照，不能把差异全归因于P2取消早停。P2有效配置只改patience 7→51，完整50轮、严格最低inner_val loss选best。D1提案为N-anon-s主视图（不是沿用NodeSem原名主视图的授权）；D2为P2及新G3R基线；D3为EP9后冻结并供七类复用。

最终实验将在显存充足的服务器运行，当前限制仅来自本机RTX3050 4GiB。后续若获授权，依次运行8个单轮显存探针、1个50轮仅训练范数试点、20个G3R正式fit；资源/数值/输入错误即停，不自动重试，不自动进入EP8/9。只进行本地提交，未获推送指令。


## 2026-11-11 — EP7改为原名主视图并获顺序训练授权

用户在call_f3878be032dc4782ae2d23b4a5711b9b选择“先调整主视图，再封存执行方案”，同时授权8个GPU探针→1个50轮范数试点→20个G3R正式fit。结合此前明确的原名主视图要求，D1改为original S0；D2的P2与D3的EP9冻结规则保留。匿名接口保留，本轮不执行匿名计划。原始答复与解释见ep7_original_v1/user_decision.json。

新建scripts/edge_sem/artifacts/ep7_original_v1，保留ep7_v1及旧registration/plan/seal/初值不变。原名特征从8H封存source_preparation索引取得，复用冻结assemble；两任务分别12036/7710行，其中11224/7436行向量相对匿名视图改变。图、节点、标签、划分、边属性、配置和种子不变。26项原名准备全部证明新构造参数与旧零步初值逐位一致，直接复用26份旧初值，没有新增权重文件。

原4318项回归保留，本轮26项定向测试通过；封存后G3R和G4R-A真实CPU装配/绑定通过。旧3个匿名计划只读核验通过，299份旧EP7文件、750份冻结源码和1134份更早产物均不变。新runtime共382项（28 EdgeSem+354冻结）。新P2登记提交后另写decisions/执行授权，再实际启动；不需要重复索取本轮顺序训练授权。

报告：scripts/edge_sem/EP7_ORIGINAL_REPORT.md。与8H比较同时涉及视图、初值、停止规则差异，只能描述，不作单因素归因。最终实验在显存充足的服务器运行，当前限制仅来自本机；未自动授权EP8/9或GitHub推送。


## EP7 原名主视图执行完成（2026-11-11）

8/8显存探针、1/1 G4R-A 50轮范数试点、20/20正式G3R全部完成验收。正式各50轮，共1000轮，无训练失败/重试。原名S0主视图，匿名接口备用。best BF1十折均值±样本SD：重入99.729±0.206%、访问控制99.203±1.080%；last分别99.788±0.171%、99.568±0.269%，主结果仍取best。

报告：scripts/edge_sem/EP7_ORIGINAL_REPORT.md；逐折/OOF：scripts/edge_sem/artifacts/ep7_original_v1/results/；资源、独立复算和完整性收据：同批次completion_attempt2/。当前是后续边增强需要的新G3R基线，尚未证明边增强分类收益。与8H差值同时受原名/匿名、初值和停止规则影响，仅描述。最终实验上显存充足的服务器，本机限制仅属本地试验。未启动EP8/EP9，未推送GitHub。

详细实施记录：

- 训练提交6f634746ca655d6ba7e2a6d31a503e4d466faea9。原名选择和用户原始答复在user_decision.json/view_revision.json；旧匿名计划和seal未改。
- 先8探针，再范数试点，再重入fold0–9和访问控制fold0–9；每任务独立进程，GPU串行。26份准备初值按SHA复用；未复制权重。
- P2的patience=51，50轮不早停，其余优化器/OneCycle/监督不变；按严格最低inner_val loss选best，未因last更高改选。
- 范数试点不读验证/测试评分；首次更新后编码器梯度L1=0.000921278304304，最终两层u范数0.032152813/0.846325636，所有U族超过1e-3。
- 单轮探针最大reserved1696MiB；范数试点1820MiB，最低整卡空闲52MiB按local_dev_v1记memory_tight。无OOM、降配、CPU替代或关闭其他程序。
- 相对历史8H，best均值差重入+0.604845、访问控制+0.849090个百分点；提升/持平/下降折数分别10/0/0、3/3/4。不是单因素因果证据。
- 原执行器验收20/20；补充独立核验503文件（40份checkpoint），逐折/OOF重算一致；历史299份EP7文件、750份源码、1134份旧产物未变。
- 报告附加脚本曾将正式状态写成success，实际为complete；completion/保留失败和旧源码，completion_attempt2/按真实接口通过。没有改正式验收器或重训。
- 既有4318项回归和原名修订26项定向测试保留，本次未重复运行。新增工作是结果独立复算、归档核验和文档UTF-8/CJK检查。
- 训练命令：python -u -B -m scripts.edge_sem.recon.ep7_run --root scripts/edge_sem/artifacts/ep7_original_v1。CPU历史核验：python -B -m scripts.edge_sem.recon.ep7_original frozen。


## 2026-11-11 — EP8 登记与CPU准备恢复（尚未完成正式拟合）

范围按PROMPTS r16：原名60新fit+复用EP7原名G3R20份，匿名敏感性80新fit，主批先行，匿名不进Holm。只新增analysis_ea.py与recon/ep8_run.py；修改execution/feature_views/protocol_p2/runtime接入角色登记，旧训练数值函数AST不变，冻结目录不改。

已完成：用户选择及双视图登记写入ep8_v1；20份EP7基线checkpoint/预测/指标只读核验通过。全CPU回归340+1353+2653通过；稀疏diagnostics接口修正35项定向通过，准备优化37项定向通过。首个重入G3R-T快/完整装配逐位证明通过。

已批准选择：call_068df1e5a5b44c43930a9e7fb1018a34显式区分主批与敏感性批；call_545e729cd68640a39272d166dc807d0e仅准备阶段安装封存匿名token，须每任务/剖面先与完整构建证明一致。后者保留旧准备16份完整记录及初值，停自有CPU进程，新preparation_attempt2继续；正式训练仍独立进程完整装配。新索引通过独立preparation_index.json/seal引用，保留旧目录及源码。

开发差异：属性诊断是稀疏异常清单，首个分析检查错误假设其全覆盖；已保留旧脚本/失败、改成子集合法且外来/重复拒绝，第二次只读检查通过，未改任何旧属性。规则预测不等于漏洞标签，L-audit仍是冻结诊断标签。

当前恢复进程：preparation_attempt2_process.json；命令python -B -m scripts.edge_sem.recon.ep8_run prepare --root scripts/edge_sem/artifacts/ep8_v1 --preparation-name preparation_attempt2，勿重复运行。后续全部准备验收→封存两个计划→登记提交后授权→原名60→匿名80→160结果核验与EP8报告。任何失败停止，不自动重试。此处不宣称训练已完成。

最终实验在显存充足的服务器运行；本机RTX3050 4GiB仅用于先导。不启动EP9、更多seed、类别或合约任务。三份历史文档前缀保留，暂未推送。


EP8恢复补记：同一recon入口增加finish-preparation后台衔接，等待已批准的CPU准备结束；只有六组逐位证明、80份唯一零步初值、三套回归、39项最终定向检查和冻结文件核验通过，才封存并按本轮“实现EP8、继续中断任务”的指令生成独立执行授权。登记提交在授权之前。衔接直接调用既有seal/authorize/run与执行器，不另造训练路径；失败与重复启动反例通过。全部初值及准备记录完成前不启动GPU拟合。此处记录的是执行顺序，不是结果已完成。


## EP8 GitHub 同步快照（2026-11-12 06:01 UTC）

140项初值准备及CPU验收已完成，6组真实任务/剖面的快捷装配与完整装配逐位一致。两个计划分别封存为原名主批60次和匿名敏感性批80次。后台当前正在执行原名主批；本次固定快照收录11个已完成正式拟合，匿名批为0个。该数量仅表示快照时刻，不是EP8完成结论；最终报告尚未生成。

同步范围包括已提交的EP8实现、测试及文档，以及准备索引、初值身份摘要、独立计划/seal、执行授权和上述11次的完整文本收据、预测、指标与资源记录。逐份核对收据/seal、任务归属和所有收据产物SHA（含仅留本地的权重）；没有重训或修改运行代码。未完成attempt、活动日志和锁不纳入快照；pt权重/初值张量仍保留本地，不上传。明细见 scripts/edge_sem/artifacts/ep8_v1/github_sync_20261112T060127Z.json。

后台仍按原名60次验收后再执行匿名80次的既定顺序运行，失败停止，不自动重试。最终实验将在显存充足的服务器运行；当前资源限制仅来自本机，本次未更改模型、训练设置或批次身份。
