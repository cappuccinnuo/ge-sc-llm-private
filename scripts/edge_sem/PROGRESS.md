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
