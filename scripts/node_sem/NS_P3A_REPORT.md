# NS-P3a 完成报告：原名语句事实与语义验收

日期：2026-11-02。修改 AI：Codex。输入 node-sem@e62d56e536e0c2d07a43a050a0916aaa0198daa8，PROMPTS.md r9。已先读取开头设计与 §5.1；开始时按要求快进同步，远端无更新。本轮仅实现 NS-P3a，不推进 NS-P3b。

## 1. 实验口径与交付位置

用户明确要求后续实验使用原名，覆盖文档旧匿名主视图条款。本轮只生成 original，extract 明确拒绝 anonymous。旧 8H 仅提供固定图、原始源码和证据引用；没有读取匿名源码、复用匿名向量或使用历史得分评估本轮。旧训练入口没有改写。后续正式计划需要绑定原名特征和可比较的原名 S0 基线，不能直接将匿名 8H 成绩当作配对基线。详见 EXPERIMENT_POLICY.md。

**验收版本**：`artifacts/facts_v1/accepted_attempt2/`，四任务在其 `original/<task>/` 下。根目录 CURRENT.json 指向这个版本。根目录旧 `original/` 与首次 smoke 均保留为 superseded，不应作为 NS-P3b 输入。没有覆盖任何旧 seal。

## 2. 新增实现

| 文件 | 逻辑 |
| --- | --- |
| facts_schema.py | StatementFacts 分组、枚举、适用节点与严格 validate；金额和混合返回值处理支持明确 unknown |
| facts_ast.py | AST 声明绑定、调用类别/金额/返回值、算术、环境用途、数组变化、函数上下文与通用语法事实 |
| facts_guards.py | require/assert、分支极性、提前退出、modifier、唯一内部检查及一层运算结果检查摘要 |
| facts_cfg.py | 复用冻结语义 CFG；保留无事件/未投影块计算可达、支配和顺序；精确重建符号表 |
| facts_io.py | 核验封存图、原始源码、L1/L2/L3 证据及索引；拒绝不一致输入 |
| facts.py | 精确投影、证据拼接、K/L/M 汇总、统计与独立事实封存 |
| facts_acceptance.py | 四任务全量抽取、五类固定源码冒烟；类别仅出现在抽样编排，不进入特征规则 |
| facts_verify.py | 与原名 text_v1 逐行对齐、历史运行版本/输入/SHA 核验与 runtime closure |
| behavior_coverage.md | 各事实字段的通用语义、七类关联说明与边界；代码不按漏洞类别生成特征 |

新增 7 组测试文件及 38 个手写 Solidity fixture、手写期望 JSON。真实解析器执行 Oracle，另用图集成测试核对 DFG/顺序/投影。源码样例未执行 solc 编译验证，解析成功不等于语言合法性已获编译器验证。

原图节点、顺序、属性、CFG/CG/DFG 边、标签、tokenizer、HGT、训练器均不变。没有产生 CTX/STATIC 向量、模型参数或 checkpoint。

## 3. 用户已批准的方案细节

1. **极性**：只记录该分支上必然成立的相等条件。负极性的 conjunction 不能推导任意一项相等；存在守卫与证明授权相等分开。
2. **一层摘要**：纳入唯一可绑定的同文件内部/库函数运算检查。必须核对运算结果是否进入条件；不依赖 SafeMath 名字，不递归，重载不猜测。
3. **符号接口**：封存 L1 的 symbol 实际是完整身份字符串。按原 analysis_path 重建冻结 SymbolTable/ExtendedSymbolTable，以完整 ID 查找，输出 name/kind/类型类别；不截取 ID，不重算或新增 DDG。
4. **unknown**：无法确定调用金额来源、同句多调用返回处理不一致时明确 unknown 并记录原因；不能任取第一个调用。
5. **共享继承声明**：K 授权用途按同文件中已确认的完整声明身份汇总；函数、语句和合约仍保留各自作用域。无关同名 owner 不会混入。用户同意保留首次产物并在新目录重新验收。

以上决定另存 decisions.json。用户关于原名的直接指令已单独记录，不再运行匿名一致性实验。

## 4. 审查中修复的问题

- 确认的 `using L for uint; x.add(y)` 同文件库调用曾被计为外部调用；现在校验库、接收者类型、唯一方法与参数数量。
- 未解析 modifier 不再被当成确定没有保护。
- 原图遗漏唯一状态写节点时，不能据此报告支持完整、零写入；缺失投影传播 unknown，包括基类声明在派生函数中的写入。
- 未投影的 `++`、`--`、`delete` 和未知写入目标会使相关顺序事实 unknown。未投影事件不通过最近行号猜映射。
- 语义 CFG 可构造不代表状态写入证据完整。未解决的 storage alias、缺失写投影使顺序 unknown；已确认 require 的名称读取诊断本身不会禁用完整顺序。
- 统计区分布尔意义的 nonempty、排除 none/default/unknown 的 positive，以及适用字段数量，避免默认字符串被误报为语义命中。
- 新增独立 runtime closure，补齐直接生产者引用之外的冻结代码依赖核验。

修订前后逐行比较仅发生在授权声明、完整性状态和 unresolved 原因：共 1,183 行变化，其中 1 个共享声明授权标记、34 个状态声明完整性状态、604 个顺序状态改变；其余差异为诊断原因。所有实际依赖、节点身份、名字、调用和环境事实未变。完整逐行记录在 revision_comparison.json。未通过改标签、删样本或改图获得通过。

## 5. 四任务真实事实

| task | 文件数 | 原节点 | env 节点 | 事实行数 | 精确 L1 符号查找 |
| --- | ---: | ---: | ---: | ---: | ---: |
| reentrancy_contract | 142 | 18,312 | 298 | 18,610 | 7,445 |
| reentrancy_node | 71 | 12,036 | 187 | 12,223 | 4,200 |
| access_control_contract | 114 | 13,432 | 261 | 13,693 | 7,868 |
| access_control_node | 57 | 7,710 | 182 | 7,892 | 5,168 |

合计 52,418 行，24,681 次完整符号身份查找；文件数是各任务内数量，不跨任务相加当作独立源码。全部行 schema、原名 text_v1 行身份/顺序/源码 SHA、原图引用核验通过。抽取墙钟 183.048 秒，CPU、0 GPU、0 fit。

| task | DFG unknown / 适用行 | order unknown / 适用行 | state unknown / 适用行 | guard unknown / 全部行 |
| --- | ---: | ---: | ---: | ---: |
| reentrancy_contract | 1073/10067 | 941/10067 | 6627/10067 | 18/18610 |
| reentrancy_node | 439/6635 | 475/6635 | 4350/6635 | 12/12223 |
| access_control_contract | 1417/7858 | 1254/7858 | 5947/7858 | 59/13693 |
| access_control_node | 534/4664 | 548/4664 | 3774/4664 | 12/7892 |

guard 的 JSON 分母按全部行统计，和前三组分母不同，不能直接比较比例。state unknown 较高，包含冻结 L2 名称解析/别名限制及保守的函数级传播；并不表示这些行全部没有已确认状态事实。unknown 不能解释为安全、无读写或无保护。不得把目前方案称为完整 Solidity 数据流分析。

各字段命中/占用、规则 1–6、modifier 成功/失败/继承、授权变量分布、unresolved 原因在 stats.json 与各任务 audit.json。访问控制两任务各 334 个 uninvoked_call_value 记录保留“不真正调用”语义，不计为实际外部调用；没有读取或据此修改标签。

## 6. 五类源码冒烟

每类按文件名排序固定取 5 个 buggy_ 源码和 5 个其他源码，仅原名、无图、无标签。

| 类别 | 文件 | 函数单元 | 事实行 |
| --- | ---: | ---: | ---: |
| arithmetic | 10 | 412 | 1475 |
| denial_of_service | 10 | 406 | 1568 |
| front_running | 10 | 506 | 2133 |
| time_manipulation | 10 | 401 | 1614 |
| unchecked_low_level_calls | 10 | 373 | 1226 |

共 50 文件、2,098 函数单元、8,016 行；0 解析失败、0 执行异常，墙钟 16.296 秒。无图时 DFG、CFG 顺序及证据相关状态事实明确 unknown；这验证通用源码接口能运行，不是这五类完整图特征或检测效果验收。详见 cross_category_smoke.json。

## 7. 测试、不变量与复现

mando 环境，CUDA_VISIBLE_DEVICES 为空、PYTHONDONTWRITEBYTECODE=1、OMP/MKL=2，沿用既有 TREE_SITTER_LIB_DIR。

| 命令（python -B -m pytest -q -p no:cacheprovider 后接） | 通过 | 警告 |
| --- | ---: | ---: |
| scripts/node_sem/tests | 496 | 4 |
| scripts/DFG/dfg_v2/tests | 2653 | 9 |
| scripts/DFG/tests tests/test_graph_utils.py | 223 | 29 |

合计 **3372 passed，0 failed，0 skipped**；42 条既有依赖弃用警告，无依赖升级。最终日志与完整命令在 accepted_attempt2/final_tests.json。含作用域/遮蔽、guard 极性、返回值、未调用 value、投影损坏、证据篡改、标签属性扰动、完整性传播及 inherited 反例。标签扰动测试沿用已批准的“输入指纹核验”和“事实不变性”分开口径；冻结 Projector 可读取结构 label 做身份对齐，特征逻辑不读取标签内容。

独立核验检查开始快照 23,168 个已跟踪文件，其中 22,813 个冻结文件字节不变；8H execution.load 和 runtime_resume_v2 运行版本一致。核验器不反序列化图或 checkpoint、不解析标签/评分；生产者只使用允许的图投影与封存语义证据。runtime_closure.json、final_validation.json、verification.seal.json 给出完整引用。

新目录复现（必须选择不存在的任务输出目录，不能覆盖 accepted_attempt2）：

```bash
python -B -m scripts.node_sem.facts_acceptance tasks --out scripts/node_sem/artifacts/facts_replay_NEW
python -B -m scripts.node_sem.facts_acceptance smoke --out scripts/node_sem/artifacts/facts_replay_NEW
python -B -m scripts.node_sem.facts_verify --out scripts/node_sem/artifacts/facts_replay_NEW
```

## 8. 剩余范围与停止点

本轮完成通用事实提取，不是完整 NodeSem、完整 Solidity 类型/绑定系统或检测收益证明。modifier、继承、调用及状态别名只在冻结支持范围内确认；无法证明的状态使用 unknown。源码 Oracle 没有编译验证。没有生成 CTX/STATIC、执行向量编码、模型训练、F1 比较或推进 NS-P3b。

最终实验按用户安排使用显存充足服务器；当前 RTX3050 4 GiB 仅为本机开发限制，服务器尚未部署实测。本轮产物留在 WSL，未创建新的 C 盘大日志/模型下载；本地提交后停止，不自动推送。
