# DDG 第一阶段实施记录（Codex，2026-10-12）

本轮在 scripts/DFG/ 实现函数内、语句级、正向 Definition–Use DDG。使用用户确认的 [接入报告](DDG_INTEGRATION_ANALYSIS_2026-10-11.md)，以本轮十阶段要求为准：没有实现 REV_DATA_DEF_USE。

实现者：**Codex**。日期按 America/New_York。2026-10-12 02:03 EDT / 06:03 UTC 核验时，既有代码仅 sco_models/graph_utils.py 改变；之后按授权追加训练改动文档与 HANDOVER。当前工作树包含更早修改，本轮未重置它们。

## 交付边界

- 函数内显式标量、参数、命名返回值；原始/兼容双 AST；声明身份与作用域；有序读写事件；独立语义 CFG；固定点到达定义；严格原节点投影。
- 输出保留原节点、节点顺序、类型、代码、token、漏洞标签、源码位置、文件归属、原边类型/端点/key/重数。只附加 DATA_DEF_USE。
- 原 HGT 核心、tokenizer、分类头、合约池化、早停、学习率、两阶段任务逻辑未改。
- 本轮完成单元/集成测试、真实图单文件审计、最小示例的两类模型单步更新和重载；**没有运行正式 K 折训练，没有新 F1 结果，也没有实现完整消融实验 runner**。
- 2026-10-11 报告中的完整实验、共同参数逐折初始化、REV、任意源码 cascade 是后续范围；不能把报告的计划当作本轮已实现功能。

## Phase 1：基础结构

- 新建：__init__.py、models.py、tests/test_models.py。
- 修改既有代码：无。
- 原因/逻辑：定义不可变 Span、Symbol、Event、Definition、Fact；Block/FunctionIR 只服务分析，绝不变成模型变量节点。跨度为 UTF-8 半开字节区间。
- 测试：2 passed，日志 audit/phase01.log。
- 剩余问题：基础结构不承担 Solidity 语义。

## Phase 2：前端与 SymbolTable

- 新建：frontend.py、symbol_table.py、tests/test_frontend.py、tests/test_symbols.py。
- 修改既有代码：无。
- 原因/逻辑：原源码 AST 负责语义；严格重现既有预处理得到兼容 AST。按 token 范围、AST 类型建立两视图映射；入口不编译合约，也不新建 grammar。使用现成 Linux .so。声明 ID 包含文件/函数/声明位置；0.4 legacy 全函数作用域，modern 块/for 作用域。legacy 默认定义在入口，modern 局部默认定义在声明。
- 测试：本阶段累计 26 passed，audit/phase02.log；后续加了字符串正文、多 pragma 护栏测试。
- 剩余问题：多条/跨边界/不支持版本约束、复杂类型、modern 初始化中的同名引用暂回退。编译器证据表明 modern RHS 在新声明激活前解析，但本版仍选择保守覆盖范围，不强行扩展。显式 scope_mode 仅用于没有已确定 pragma 的输入，不能覆盖矛盾版本。
- 参考：[Solidity v0.5.17 ReferencesResolver.cpp](https://github.com/ethereum/solidity/blob/v0.5.17/libsolidity/analysis/ReferencesResolver.cpp#L87)。

## Phase 3：DEF/USE

- 新建：access_extractor.py、tests/test_access.py。
- 修改既有代码：无。
- 原因/逻辑：每事件先读后写；普通/复合赋值、递增减、delete、tuple、参数、命名返回值。只跟踪可识别局部标量；未知 storage 不伪造定义。x=unknownState 仍产生 x 新定义，不能把旧 x 错误保留。
- 测试：累计 46 passed，audit/phase03.log。
- 剩余问题：嵌套副作用和不确定求值顺序回退；引用、storage/mapping 内容依赖、跨函数返回摘要未实现。诊断中的未知名称不计入已识别标量 use 分母。

## Phase 4：语义 CFG 与 Reaching Definitions

- 新建：semantic_cfg.py、reaching_definitions.py 及两份对应测试。
- 修改既有代码：无。
- 原因/逻辑：原 HCG 的 return 路径存在问题，因此单独建立分析 CFG；处理分支、while/for/do、break/continue、return/throw/revert。静态 def_id 固定，worklist 真正收敛后重放事件取得直接依赖；不可达块不传播，资源超限回退。
- 测试：阶段累计 70 passed，audit/phase04_cfg.log，RD 独立 16 项。
- 剩余问题：不解析 modifier/assembly/try 的完整语义；终止内建可能被同名声明、导入、继承遮蔽时回退。原训练用 CFG/CG 缺陷未在本轮顺带修改。
- 补修：注释不改变裸 return/throw 语义，for 条件里的注释被正确忽略；revert 参数按真实 AST 读取。

## Phase 5：DDGBuilder

- 新建：ddg_builder.py、tests/test_ddg_builder.py。
- 修改既有代码：无。
- 原因/逻辑：汇总每函数的直接 facts，默认不做传递闭包；投影后同 (src,dst,DATA_DEF_USE) 合并为一条模型边，多变量事实保留在侧表。自环 facts 单独统计，不输出模型自环。
- 测试：累计 79 passed，audit/phase05.log。
- 剩余问题：不能把 direct def-use 当污点闭包或可利用性证明。

## Phase 6：映射回原 HCG

- 新建：projection.py、tests/test_projection.py。
- 修改既有代码：无。
- 原因/逻辑：匹配 source_file、兼容 AST ID、语法角色、代码文本、预处理起止坐标；作者式 DOT 外层序列化只做明确解码。图全局 ID 可重编号；不用漏洞标签、行范围重叠或最近行猜测。缺失节点跳过对应 facts，源内容过期/重复锚点使该文件回退。
- 测试：累计 88 passed，audit/phase06.log。
- 剩余问题：当前 HCG 的部分 emit、do-while 条件没有节点，不能在“不新增节点”约束下完整投影。
- 后续复核发现 for update 本有独立节点，而初版错误归属 for 头；已暂停后续验收，改成 update 自身 span，增加真实 HCG 的 i++→y=i 测试。修复后含原图工具累计 103 passed，audit/phase07_projection_fix.log。for 初始化没有独立节点时仍归循环头，明确属于节点粒度限制。

## Phase 7：附边与元关系接入

- 新建：pipeline.py、graph_audit.py、tests/test_pipeline.py、tests/test_model_integration.py 的第一部分。
- 修改既有代码：**仅 sco_models/graph_utils.py::reflect_graph()**。
- 原因/逻辑：旁路深拷贝原图后附边；精确核对原图不变量。原 generate_hetero_graph_data 自动按 (src_type,DATA_DEF_USE,dst_type) 分类，无须改元关系提取器。新增一个精确关系名分支，禁止该关系被同名反射，其他旧逻辑逐行保留。
- 测试：累计 102 passed（含既有 graph_utils 测试），audit/phase07.log；for update 补修后 103。
- 剩余问题：只认证当前 inside_token 接口，未认证 HAN/metapath2vec；它们对对称关系有其他假设。

原接入修改：

~~~python
# DDG FORWARD FIX (Codex, 2026-10-12)
if metapath[1] == "DATA_DEF_USE":
    symmetrical_data[metapath] = value
    continue
# 原反射代码保持原样
~~~

旧代码没有被删掉，因此无需把整段旧反射复制成注释。原行为、移除分支的回退方式已在代码旁注明；完整修改前文本保存在 audit/graph_utils_before_2026-10-12.py.txt。

## Phase 8：HGT 验收与 checkpoint

- 新建：model_validation.py；扩展 tests/test_model_integration.py。
- 修改既有代码：无新增修改。
- 原因/逻辑：绑定实际输入、节点类型编号、有序 canonical relation 编号、DGL 边方向、冻结 inp、监督与文件归属；重载 state_dict 前校验。外部合约标签/折清单可由 external_inputs 绑定摘要。
- 实际结构差异：合约模型不保存 node_feature 属性。只在旁路辅助程序核验实际 inp 与 NX token，不给原模型增加属性。
- 测试：集成 20 项通过，阶段累计 115 passed，audit/phase08.log。两类模型有非零 DDG relation_msg 梯度并实际更新；重载 logits 逐位一致；孤立节点类型保留。E0 与快照中的旧 reflect 在相同 seed 下权重、eval 输出逐位一致。
- 剩余问题：原正式训练入口不会自动调用新 checkpoint validator。本轮没有接管训练循环/权重保存；增强图权重仍必须配套相同输入图。未来完整消融需在每折构造时对齐共同初始化，单独“同 seed”不够。

## Phase 9：use_ddg 配置和 CLI

- 新建：configuration.py、cli.py、tests/test_configuration.py；加强 models.py 资源上限类型检查。
- 修改既有代码：无。
- 原因/逻辑：默认 false 原样深拷贝；true 调用附边。两种模式都要求原始未增强 HCG，拒绝用已增强图伪装 off。输出必须是 scripts/DFG 下不存在的新目录，不覆盖输入。记录图、源码、grammar SHA；检查源码清单 SHA 及运行期间输入变更，保存后受限重读校验。
- 测试：累计 121 passed，audit/phase09.log。
- 剩余问题：不会自动生成 token 或更改合约标签；缺失源码保留样本并报告回退。源码清单 identity 必须与 source_file 完全对应。

## Phase 10：端到端验证

- 新建：demo.py、tests/fixtures/minimal.sol、tests/test_end_to_end.py。
- 修改既有代码：无。
- 原因/逻辑：实际调用原构图器；离线使用 Salesforce/codet5p-770m tokenizer 和原 encode_ids 生成 512 维 token；之后 DDG 阶段不再重编码。样例节点标签全部为 clean，仅用于接口测试。
- 测试：DDG 121 项 + 原测试 19 项，**合计 140 passed**；audit/phase10_unit.log。依赖仅原有弃用 warning。工具宿主时钟有跳变，pytest 日志个别耗时为负或跳跃，不能用于性能统计。
- 独立真实 tokenizer 示例：audit/phase10_demo.log；产物 artifacts/minimal_20261012_v1/。
- 原图 11 节点/12 边；增强图同 11 节点/19 边；只增加 7 条 DATA_DEF_USE。
- 节点输出 [11,2]、合约输出 [1,2]；DDG 梯度 L1 分别 3.91129184 / 5.12457860；两类更新和重载通过。该数值只是接口检查，不是论文实验结果。
- 剩余问题：未做全数据集附边、正式 K 折、F1 对比和任意新源码 cascade。

## 真实图补充审计

见 [real_projection_probe.json](audit/real_projection_probe.json)。只在内存中处理两类 buggy_18.sol 的作者与本地 narrow 子图，没有重写数据集。

| 类别 | 输入版本 | 普通/合成节点 | 支持函数 | facts/已投影 | 新增边 |
|---|---|---:|---:|---:|---:|
| 重入 | 作者与本地分别检查，均一致 | 383/41 | 45/69 | 96/86 | 74 |
| 访问控制 | 作者与本地分别检查，均一致 | 273/11 | 60/67 | 156/146 | 114 |

每组 10 个未投影 facts 对应 5 个无 HCG 节点的 emit。两版本新增边按原源码 span 对齐后相同。facts_projected 的分母仅包含当前支持并已分析的标量事实，**不是全部 Solidity 数据依赖覆盖率**。合约保留不等于其所有函数均成功分析。

## 变更核验、回退和后续

- 本轮前摘要：audit/implementation_before_2026-10-12.json。
- 最终摘要/授权范围检查：audit/implementation_after_2026-10-12.json。
- graph_utils.py 修改前 SHA256：1bdedc8f72ae3e1abd7cfa26cd5c5c071f590ea3456af225064e13ad850bcc48。
- 修改后 SHA256：5da9afc69f4528b63e4acf9595588b20b06d15cf3d508a49d56f10e33116015d。
- 最简单回退：使用原 HCG 或 --no_ddg，不必回退原反射函数；E0 等价已验证。不要给原图加载增强关系模型的权重。
- 如确需撤回原代码接入，只移除 DDG FORWARD FIX 的精确分支；先核对文件摘要，不用 git restore 覆盖更早修改。
- 尚未解决：state/mapping/ref、跨函数、modifier、复杂副作用、全部版本的精确语义、缺失节点的完整定位、正式实验协议和 DDG 的实际收益。
- 标签保持不变只保证可做相对控制，不能证明标签绝对正确；99 F1 与本轮工程验收无直接关系。
