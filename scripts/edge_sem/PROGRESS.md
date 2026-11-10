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
