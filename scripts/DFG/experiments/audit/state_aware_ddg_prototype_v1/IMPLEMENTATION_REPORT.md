# Stage E：State-aware DDG 原型实现与验收

修改 AI：Codex。日期：2026-10-14。开发工作树：/home/zhao/SmartContract/ge-sc-llm-ddg-v11，分支 ddg-v1.1-correctness，起始 HEAD 93c9684302aa964e37ec8ff3342c9f2dafcd16ae。

本轮完成状态分析旁路原型、自动化语义测试和两类真实困难样本审计；未运行训练。真实样本尚无可物化的 STATE_DEF_USE，因此不满足进入 E3 正式训练的条件。新模块可表达部分通用状态语义，但覆盖率和独立语义验收尚不足。

## 1. 实际改动及模板调整

全部新逻辑位于 scripts/DFG/state/，审计入口与文档位于本目录。既有标量 DDG、HGT、tokenizer、训练器均未修改。原仓库只追加既有训练变化与交接文档；本工作树也追加同样内容，保留原正文。

| 新文件 | 核心逻辑及理由 |
|---|---|
| state/__init__.py | 原型版本和 STATE_DEF_USE 常量，与旧标量版本分开 |
| state/models.py | 声明、位置、事件、事实、结果及独立 StateFunctionIR；不改变原 FunctionIR |
| state/locations.py | 作用域/声明绑定、简单 mapping 键与 EXACT/MAY/NO_ALIAS |
| state/access.py | 读写、复合更新、环境读、调用配置和 HAVOC；不猜测模糊求值顺序 |
| state/reaching_definitions.py | 入口未知、强弱更新、分支 union、循环 fixpoint、KILL 和 CFG witness |
| state/analyzer.py | 逐函数协调与完整回退，不发布不可信部分结果 |
| state/projection.py | 复用 v1.1 Projector 精确投影；保护全部旧节点和边 |
| state/model_adapter.py | 显式旁路关系加载；防止原 reflection 给状态边补反向 |
| state/audit.py | 状态访问/调用侧表和两层图上下文增量；不直接作为新模型关系 |
| state/tests/ | 56 项语义、投影、不变量、模型方向/梯度与审计测试 |
| 本目录 run_stage_e.py / oracle_review.py | 绑定来源、20个Oracle、选定真实文件与最终预期格式，拒绝覆盖旧attempt |

主要调整：
1. 当前仅重入和访问控制先导审计；替换模板中的七类全量准备为 TWO_PILOT_EXPERIMENT_PLAN.md。规则不使用漏洞类别或标签，新增6个通用合成规格验证范围。
2. 采用 state/ 子包而非六个平铺文件，保留独立 Side Table 与原语义 CFG。
3. StateReadEvent / StateWriteEvent 是同一不可变事件结构的别名，通过已校验 kind 区分，避免重复结构。
4. CFG witness 只保证结构可达且无强覆盖阻断，不宣称经过 SMT 证明的可行路径。
5. MAY alias 事实保留侧表，本版不物化；UNKNOWN/HAVOC 不增加模型节点。
6. 状态访问/调用顺序只交付侧表；modifier/control 不冒充数据依赖。
7. 没有因零增量放宽原 B1、替换 pragma、修改标签或定制难例规则。

## 2. Oracle 与审查状态

核对原9个真实函数及5个合成规格，补6个语义正反例，共20个。自动预定子集行为检查通过：13个完成分析，7个按已声明限制回退。真实函数核对 source SHA、UTF-8 byte span、合约声明、AST 与原 HCG node_id。

合成样例总计17条状态事实：16条EXACT位置、1条MAY位置；物化15条状态边（1条EXACT自身端点被过滤）。真实9个Oracle没有新增状态边。

ORACLE_EXPECTATIONS.json 的人工编写预期与分析器 observed 字段分开；审核者状态明确为 Codex 静态候选。独立人工批准0，solc编译验证0。原5个规格加新增6个共11个合成输入；回归中还有仅用于解析器健壮性的样例，不能以Tree-sitter通过声明语言合法。

## 3. 真实数据与投影结果

最终接受 results_attempt_002/；results_attempt_001/ 保留为复审修复前记录。两轮都没有训练。

| 集合 | 审计文件 | 函数 | 完成子集分析 | 回退 | 具体状态事实 | 新模型状态边 |
|---|---:|---:|---:|---:|---:|---:|
| 重入作者图对应源码 | 3 | 196 | 35 | 161 | 0 | 0 |
| 访问控制作者图对应源码 | 4 | 119 | 28 | 91 | 0 | 0 |

文件为重入 buggy_18/27/36.sol，访问控制 mapping_write.sol、buggy_18/26.sol、arbitrary_location_write_simple.sol。只分析选定文件内函数，其他文件仍留在候选完整图里且不增强。不是全数据集覆盖统计。

四个 E3a_selected_contract/node.gpickle 的 SHA 与对应 E2 完全相同。所有旧节点、node_id、类型、标签、token、源码映射、CFG/CG多重边和 DATA_DEF_USE 均保持；关闭状态开关 fingerprint 相同。

无新增 STATE_DEF_USE 的原因分两层：
- 可分析函数主要是入口状态读取→调用→后续更新，没有函数内先写后读；部分调用将来源转为未知。
- 大量困难函数受继承绑定、原B1版本保护、modifier、数组或非标量边界限制，尚不能作完整判断。

这不是投影丢失造成的零增量：本次真实事实数先于投影就是0，missing anchors也为0。也不证明状态依赖对两个漏洞无用。

真实模型新增canonical、两层新增上下文、条件参数增量均0。侧表识别32条同状态访问顺序、15条外部调用到写入顺序、15条未确认调用到写入顺序；这些数值不混入DDG或模型增量。

## 4. 模型兼容性

原 sco_models/graph_utils.reflect_graph 只特殊保护 DATA_DEF_USE，直接输入 STATE_DEF_USE 会补反向。本轮没有更改其逻辑；旁路 model_adapter 保持原基础反射与标量方向，并单独保留状态正向。

合成 HGT 测试验证 canonical relation 真正注册、前向读取和反向传播得到非零关系梯度，不只验证文件存储。未运行完整训练器、optimizer、GPU或正式checkpoint。

正式训练入口尚未接入适配器；不能直接运行旧命令。后续必须显式新建协议/输入/schema绑定，检查新参数的语义初始化、训练支持与关系方向。新增 canonical 在 hidden128/heads8/layers2 条件下每项增加8208参数的审计仅是条件公式，不是本轮完整模型参数测量。

## 5. 测试与复审修复

- 新状态套件：56 passed。
- v1.1工作树完整回归：435 passed、1 deselected、31 warnings。
- 被排除的原绝对资源测试单独在原工作树：1 passed、4 warnings。
- 合并不同测试：436 passed，0 failed，0 skipped；重复运行不重复计数。
- 警告来自现有 DGL/Torch distutils 与 NetworkX gpickle 弃用，无依赖升级。
- 新增两项复审测试在修复前2 failed，修复后通过且测试SHA未变：emit的嵌套参数避免重复遍历；未知事件kind必须拒绝。没有删除测试或放松断言。见 review_correction.json / review_regression_before.log。
- 最终审计复跑267.16秒；这是源码分析与序列化，不是训练时间。
- 原封存reporter重算4任务complete、0pending。首次因预建输出目录触发拒绝覆盖，保留 archive_check.log；第二次新目录 archive_check_002/通过，未改reporter。
- 首次新模块写入曾被自动审批按旧D3只设计边界拒绝；核对本轮附件明确授权E-A/B/C实施后重新提交获准。拒绝时无写入，没有绕过审批。

完整命令、计数及日志见 REGRESSION_RESULTS.json。命令使用既有mando环境和既有语法库，无外部solc下载、依赖安装或版本升级。

## 6. 保护、限制和下一步

保护清单与结束核验见 protected_before.json / protected_after_verified.json；文档追加记录见 documentation_update.json / documentation_update_002.json。原始E0/E1正式图、模型、plan/seal、v1.1 E2及旧审计原文均保留。两仓库HEAD不变，无提交/推送。

限制：目前拒绝所有继承/导入上下文；modifier执行、数组、嵌套mapping、storage引用、assembly、跨函数/跨交易摘要未完成。复杂键/重赋值键UNKNOWN，HAVOC和staticcall较保守；未求解路径谓词；独立Oracle认证和编译未完成。

下一步优先逐一解决可核验的覆盖瓶颈（准确版本/绑定证据、受限继承解析），或者单独验证已经观察到的访问/调用顺序语义。权限guard→敏感操作需要控制依赖与modifier执行设计；不是增加STATE_DEF_USE就能替代。未验证这些之前，不扩展融合模型、不直接启动60次训练。

本轮交付为可审计的状态分析原型，不是完整Solidity DDG，也没有新的E2/E3 F1。

???????????protected_after.json??requires_review??????????????203??smoke??????SHA??????????????????203??????????????????????????????????protected_after_verified.json?
