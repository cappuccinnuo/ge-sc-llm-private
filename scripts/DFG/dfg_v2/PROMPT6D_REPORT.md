# DFG v2 Prompt 6d：跨度对齐、差异归类与图不变验收

实施与复核：Codex；日期：2026-10-25；起始提交 f14194be329cae5eab236da3270afdfa8f1b74a8，分支 dfg-v2。

已先读取更新后的 PROMPTS.md §4.1 与 Prompt 6d，并执行 git pull --ff-only origin dfg-v2，返回已是最新。Prompt 6b/6c 已完成，本轮复用其最终图 graphs_v2_r1/store.json 和封存 Slither 报告，不重做6b、不扩展分析范围、不训练或开始 Prompt 7。

本轮增加外部对照验证工具。唯一分析器改动是文档明确允许的 new_expression 直接 call_argument 防御分支。四任务语料该形状计数均为0；最终图身份以文末实际重建验收为准。

结论的适用范围：固定 seed=0 抽样172条 other，逐条读原源码与两侧证据，未发现违反当前已声明支持范围的 v2_defect。未抽中的事件仍未完成人工语义证明；这不是“全部DDG正确”，不是漏洞F1，也不是人工边精确率。

## 1. 比较口径与修正

6c原指标完全保留；新指标以字节跨度计数，不替换原来的行/变量名/读写集合指标。新指标主表包含全部可比较上下文；排除 alias/modifier 的附加口径另列，因此两套分母也不同，不能把数值相减解释为分析器改善。

- L1候选取封存IR事件的语句anchor；入口定义取声明范围。每个不同IR event_id保留，不能因同一anchor和symbol合并事件。
- L2候选取F3 audit的occurrence；参考取封存Slither CFG节点start/end。使用半开字节区间，边界相接但无交集不匹配。
- 在同文件、同变量名、同读写类型内按起点贪心一对一匹配；同起点优先实际事件，再处理entry初始化，随后按终点和ID排序。不复用已匹配事件。
- Slither内部的 _scope_N 重命名，仅在参考声明起点与唯一AST声明身份吻合、源码原名得到验证时规范化。保留原名和证明；不会简单删除字符串后缀。
- 机械归类按Prompt顺序取首个成立条件。delete既处理完整链，也处理occurrence只记录operand标识符的情形；后者必须证明其直接AST父链为delete，普通赋值/其他一元表达式不归入。
- L2的supported/fallback分层沿用6c的L1函数状态，不能解释为L2自身回退。L2仍可能在L1回退函数中提取状态关系。

保留的比较局限：L1结构anchor可能覆盖子语句；名字＋跨度匹配不等于完整类型/绑定证明，声明一致性另记录；L2词法重复出现与Slither按CFG节点变量集合去重的分母不同。没有为提高指标改变图、标签或分析器策略。

已保存 alignment_v1、v2、v3 三轮输出。v1→v2修复不同IR事件合并、scope名称、entry抢配与delete链；v2→v3补齐identifier operand的两个delete分类。最终版本为dfg-v2-slither-span-alignment-v3。

## 2. 原6c与跨度附加指标

两类分别131/142、108/114个文件可比较，仍有8/3个编译失败、3/3个来源不可比较。文件及失败数没有变化。P/R是事件一致性，不是检测指标。

### 6c主指标（原样保留）

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|11821|9693|8623|72.9465|88.9611|
|重入|L2|7105|8082|7027|98.9022|86.9463|
|访问控制|L1|13956|9613|8447|60.5259|87.8706|
|访问控制|L2|3587|4128|3526|98.2994|85.4167|

### 新跨度主指标（含全部上下文）

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|12345|10215|8974|72.6934|87.8512|
|重入|L2|7658|8563|7368|96.2131|86.0446|
|访问控制|L1|14359|10024|8719|60.7215|86.9812|
|访问控制|L2|3994|4425|3802|95.1928|85.9209|

### 排除alias/modifier的辅助口径

|任务|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|
|重入|L1|12042|9796|8709|72.3219|88.9036|
|重入|L2|7260|8291|7086|97.6033|85.4662|
|访问控制|L1|14136|9705|8527|60.3212|87.8619|
|访问控制|L2|3733|4191|3578|95.8478|85.3734|

### 按原L1函数状态分组

L2的状态列沿用L1，不代表L2全部回退。unmapped包括独立modifier、合成初始化等未纳入L1普通函数状态的参考上下文。

|任务|层|状态|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|---|
|重入|L1|supported|12345|9009|8974|72.6934|99.6115|
|重入|L1|fallback|0|1162|0|—|0.0000|
|重入|L1|unmapped|0|44|0|—|0.0000|
|重入|L2|supported|7027|7034|6760|96.2004|96.1046|
|重入|L2|fallback|503|577|480|95.4274|83.1889|
|重入|L2|unmapped|128|952|128|100.0000|13.4454|
|访问控制|L1|supported|14359|8755|8719|60.7215|99.5888|
|访问控制|L1|fallback|0|1240|0|—|0.0000|
|访问控制|L1|unmapped|0|29|0|—|0.0000|
|访问控制|L2|supported|3212|3197|3044|94.7696|95.2143|
|访问控制|L2|fallback|663|756|639|96.3801|84.5238|
|访问控制|L2|unmapped|119|472|119|100.0000|25.2119|

### 按版本来源分组

|任务|来源|层|候选|参考|匹配|P (%)|R (%)|
|---|---|---|---|---|---|---|---|
|重入|metadata|L1|878|765|654|74.4875|85.4902|
|重入|metadata|L2|648|682|549|84.7222|80.4985|
|重入|pragma_derived|L1|11467|9448|8320|72.5560|88.0610|
|重入|pragma_derived|L2|7004|7875|6813|97.2730|86.5143|
|重入|fallback_default|L1|0|2|0|—|0.0000|
|重入|fallback_default|L2|6|6|6|100.0000|100.0000|
|访问控制|metadata|L1|64|70|40|62.5000|57.1429|
|访问控制|metadata|L2|128|130|123|96.0938|94.6154|
|访问控制|pragma_derived|L1|14295|9626|8679|60.7135|90.1621|
|访问控制|pragma_derived|L2|3694|4099|3508|94.9648|85.5818|
|访问控制|fallback_default|L1|0|328|0|—|0.0000|
|访问控制|fallback_default|L2|172|196|171|99.4186|87.2449|

### 行口径到跨度口径的匹配变化

第二数列要求旧extra与missing两侧均未匹配而现在匹配；它也包含经声明证明的名称规范化收益，不能全部称为跨行修复。

|任务|层|两侧起始行不同但匹配|旧双未匹配→新匹配事件对|
|---|---|---|---|
|重入|L1|6|31|
|重入|L2|58|57|
|访问控制|L1|0|25|
|访问控制|L2|51|51|


## 3. 全部差异的机械分类

共13,857条未匹配事件，每条恰归一类；other为773条，非other为13,084条。以下每格为数量（该任务、层、方向差异中的比例）。零值类别也保留，不能把类别归属当作已证明分析器正确。

### L1

|类别|重入FP|重入FN|访问控制FP|访问控制FN|
|---|---|---|---|---|
|entry_initialization|3347 (99.29%)|0 (0.00%)|5278 (93.58%)|0 (0.00%)|
|v2_fallback|0 (0.00%)|1162 (93.63%)|0 (0.00%)|1240 (95.02%)|
|unreachable_ir|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|named_return_implicit|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|declaration_without_initializer|9 (0.27%)|0 (0.00%)|10 (0.18%)|0 (0.00%)|
|tuple_or_var_declaration|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|other|15 (0.44%)|79 (6.37%)|352 (6.24%)|65 (4.98%)|

### L2

|类别|重入FP|重入FN|访问控制FP|访问控制FN|
|---|---|---|---|---|
|constant_excluded|0 (0.00%)|342 (28.62%)|0 (0.00%)|363 (58.27%)|
|state_initializer|0 (0.00%)|613 (51.30%)|0 (0.00%)|158 (25.36%)|
|write_base_read|0 (0.00%)|185 (15.48%)|0 (0.00%)|70 (11.24%)|
|modifier_inlining|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|alias|155 (53.45%)|2 (0.17%)|72 (37.50%)|2 (0.32%)|
|v2_binding_unresolved|0 (0.00%)|53 (4.44%)|0 (0.00%)|23 (3.69%)|
|assembly|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|push_pop_skipped|0 (0.00%)|0 (0.00%)|0 (0.00%)|0 (0.00%)|
|other|135 (46.55%)|0 (0.00%)|120 (62.50%)|7 (1.12%)|

每个非空分类的前5例（不足则全部）、原始行、Slither节点文本、v2证据和机械判据见 [PROMPT6D_CATEGORY_EXAMPLES.md](PROMPT6D_CATEGORY_EXAMPLES.md)，共119例/25组。完整字节证据与全量差异在本地产物category_examples.json及alignment_v3/report.json；这119例不是随机人工审阅样本。


## 4. 固定样本的逐条判断

最终共有773条other；按每任务、层、方向独立 Random(0)，排序 difference_id 后最多抽30条，不足全取，共172条。先后两轮抽样保留；最终v3与v2相同的165条完整事件证据逐字段相等后复用原判断，另7条由Codex逐条新核验。独立复核确认172条身份唯一完整、524项源码范围/上下文无错配。所有判断文件绑定源码SHA与最终selection。

172条均判为slither_convention（包括参考工具的IR口径与v2明确的保守支持范围差异），0条v2_defect、0条未修复comparator_artifact、0条unclear。它们主要是：

- 独立modifier体及其参数/局部变量被Slither纳入参考，而冻结L1不单独分析modifier体。原记录已是unmapped并带modifier标签，不能说成分析器普通函数漏提取。
- 循环条件上Slither额外记录DEF/WRITE；原条件中没有相应源码赋值。已只读检查安装的Slither SSA更新方法，支持控制流汇合记写的解释；封存报告未保留逐条IR，未宣称每个具体节点的Phi都已直接验证。
- 同一语句重复读取同一状态变量时，Slither按变量集合去重，v2保留不同词法出现。
- 局部数组/结构写入的基对象，v2 L1按既定粗粒度语义读取；Slither的对应IR写目标未必再记这个读取。
- 独立的 x; 及未真正调用的 to.call.value(amount);，源码遍历与操作IR的读取集合有差别。

访问控制剩余7条L2 FN全部检查：6条位于0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol，源码使用var局部别名，且无pragma/metadata版本依据；v2已记录legacy_alias_version_unconfirmed和callable_local_shadows_state。Prompt3只在确认legacy模式后支持这种隐式storage别名，而Slither使用fallback_default=0.4.25。此为已接受的保守范围限制，不把默认编译器当成源码真实版本，也不保证补版本后所有类型问题都会消失。另1条是rubixi.sol第72行纯while条件处的balance写入约定。

v2_defect模式清单：本次抽样未发现，因此没有新缺陷最小复现或受影响事件数量估计。不能将“0个抽样模式”写成“未抽样事件均无缺陷”。已有Oracle18/20的原始结果与期望问题保持，不重写为20/20。

## 5. 六文件映射与小项加固

六个缺CFG filename文件均只用已批准的原版本编译器做映射证据检查；没有import但仍不足以证明来源。254个节点中76个表达式与源码精确一致、98个没有独立表达式、80个文本不一致。任一节点不满足即整个文件继续not_comparable，六文件全部保持；没有公布部分匹配P/R，也没有并入6c报告。主要阻断是ENTRY/END没有可核对的独立文本，以及Slither格式化表达式与源码非逐字相同。

new_expression改动仅遍历其直接call_argument，类型名不记USE，原nested write/未知形状回退仍保留。修改前四任务new_expression总数为11/7/6/3（重入合约/节点、访问控制合约/节点），直接call_argument均0。测试覆盖new uint[](n)、new bytes(len)、new string(len)、new C(a,b)、直接参数的合成AST分支及嵌套写入拒绝；解析器测试不等同于solc语言合法性验证。

新增review_v1b对两类合约F3新增的111条DATA_DEF_USE全量导出：重入51、访问控制60。沿用原CSV/seal和score_review，不抽样、不自动填verdict/note。人工分母为0，precision/Wilson为空，completed=false。原review_v1的512行和原seal不改，也没有把AI的172条事件判断混成人工边精度。

CSV SHA256：75b97a5e545c6b9f61304b274e94e6c0f61ccf41a13d913cf0ecdd90813e358a。


## 6. 文件与测试

|文件|改动及原因|
|---|---|
|l1_access.py、tests/test_l1_access.py|唯一分析器改动：new_expression直接参数读取；防止合法语法树形状变化时漏USE|
|slither_align.py、tests/test_slither_align.py|跨度一对一匹配、确定性分类、全部差异与分层指标、原指标保留|
|slither_mapping.py、tests/test_slither_mapping.py|6个缺filename文件的整文件可证明映射，失败继续不可比较|
|slither_review.py、tests/test_slither_review.py|固定抽样、source/selection/decision绑定、缺陷与比较器未完成门槛|
|review_supplement.py、tests/test_review_supplement.py|111条新边全量空白人工表及旧图等价证据核验|

最终v2全部测试970 passed，旧DDG/graph_utils 223 passed；合计1193通过，0失败/跳过。分别8/29条已有DGL distutils、NetworkX gpickle弃用warning。定向比较器34、映射23、抽样工具16项通过；L1/补充表/旧表组合92项通过（有重叠，不另加总）。

初始fixture导入和Path类型错误、映射测试异常包装预期，以及抽样工具局部ID不够唯一的候选问题均在正式验收前修复，旧日志保留；没有删除测试或放宽语义断言。抽样程序验证身份和绑定，无法自动证明AI语义判断正确，证据正文由本次独立人工辅助交叉检查补足。

实际环境与命令（已有输出目录不可覆盖，重跑须另取新目录）：
~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.slither_align \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3
python -B -m scripts.DFG.dfg_v2.slither_review prepare \
  --alignment scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3/report.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3
python -B -m scripts.DFG.dfg_v2.slither_review validate \
  --selection scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3/selection.json \
  --decisions scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/review_other_v3/decisions.json
python -B -m scripts.DFG.dfg_v2.cli build \
  --manifest scripts/DFG/experiments/artifacts/dfg_v2/inputs/manifest.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/temp_graphs_verify
~~~

六文件映射与补充表的实际入口：
~~~bash
python -B -m scripts.DFG.dfg_v2.slither_mapping \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --old-report scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full/report.json \
  --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/mapping/six_files
python -B -m scripts.DFG.dfg_v2.review_supplement \
  --diff scripts/DFG/experiments/artifacts/dfg_v2/prompt6b_v1/store_diff_r2/store_diff.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/review_v1b
~~~


## 7. 临时重建与不变量验收

cli build成功退出0，耗时842.47秒；其末尾verify_store真实读取图并复算完整/计算指纹和DGL schema。新旧实际文件SHA又单独核对；12张增强图两种指纹全部相同，4个F0原文件引用不变，20个模型schema/profile记录相同；16个图项的gpickle SHA也逐字节相同。

|任务|图|节点|边|完整指纹|计算指纹|文件SHA|
|---|---|---|---|---|---|---|
|reentrancy_contract|F1|18312|24977|相同|相同|相同|
|reentrancy_contract|F2|18312|32399|相同|相同|相同|
|reentrancy_contract|F3|18610|36256|相同|相同|相同|
|reentrancy_node|F1|12036|15179|相同|相同|相同|
|reentrancy_node|F2|12036|20503|相同|相同|相同|
|reentrancy_node|F3|12223|23703|相同|相同|相同|
|access_control_contract|F1|13432|21311|相同|相同|相同|
|access_control_contract|F2|13432|25128|相同|相同|相同|
|access_control_contract|F3|13693|27664|相同|相同|相同|
|access_control_node|F1|7710|12763|相同|相同|相同|
|access_control_node|F2|7710|14621|相同|相同|相同|
|access_control_node|F3|7892|16569|相同|相同|相同|

唯一分析器防御分支没有触发现有语料。原HCG节点/属性、标签/token、CFG/CG、L1/L2/L3关系及model schema保持，不更换正式输入。graphs_v2_r1/store.json是Prompt7/8沿用的最终图存储；这只说明通过本阶段门槛，不等同已完成人工精度或新训练验收。

按Prompt6d要求，只删除本轮新建的temp_graphs_verify：31文件、839,208,415字节（约0.84GB）。删除前核验精确绝对路径在工作树内、无符号链接、目录文件名单与大小完全一致，保留temporary_rebuild_comparison.json、执行日志及清理收据。没有清理C盘、旧图或其他历史产物；本项目仍写入位于E盘的WSL。

原11,188个跟踪文件中只允许本轮两个旧v2文件和三份文档变化；其余11,183个文件须逐SHA一致，三份文档原始前缀须完全保留。最终保护收据为prompt6d_v1/final_acceptance.json。


## 8. 执行偏差、保留事项与停止点

本轮没有另提或实施需要替代原方案的设计；比较器修正属于Prompt6d明确要求的错误修复。前轮用户批准的new类型处理、证据索引重排、回退原因推进、默认编译器单列等决定继续沿用，未扩大解释范围。

必须记录一项执行偏差：辅助复核过程中，代理额外对访问控制buggy_43.sol执行1次、buggy_30.sol执行2次只读Slither探针，超出了本轮仅允许重跑6个映射文件的范围。发现后已立即停止；共2文件3次调用，使用已有可信编译器，无安装下载、无源码/图/标签修改。其结果没有并入正式6c/6d统计，也没有用来替换封存证据；命令和原始输出保留在review_other_v1/unplanned_read_only_verification.json。这项偏差不被表述为用户批准的变更。

另有一次人工辅助判断被纠正：旧5条modifier事件本来就标为unmapped/modifier_inlining；初读误认为_scope误判，复核封存SHA后撤回。旧判断与v1_modifier_correction.json都保留，原selection/report未改。不能据此前误读再改比较器。

仍未执行：完整Slither重跑、现代Oracle样例的新增编译验证、人工111边判定、全部other人工检查、训练、Prompt7/8和push。6c的11个编译失败与6个不可比较文件保持；不删除数据集样本。

本轮结束在Prompt6d验收。若未来发现支持范围内的提取错误，应单独进入6e，不能为通过当前比较而直接改分析器。

## 9. 产物、摘要与后续入口

所有本轮机器产物位于scripts/DFG/experiments/artifacts/dfg_v2/prompt6d_v1/；review_v1b单独位于同级目录。大图与百MB级报告继续本地保存，不随代码提交。

|相对artifacts/dfg_v2的路径|SHA256|
|---|---|
|graphs_v2_r1/store.json|ed02ad029392db4a142e1a17a0a1a3577bc9f104377bf304bc64f630c6d286c4|
|prompt6c_v1/slither_full/report.json|db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6|
|prompt6d_v1/alignment_v3/report.json|c1f68cd9ea37d00653700545d3cce322114f132ce29db127f6222f8ae6cbd22a|
|prompt6d_v1/review_other_v3/selection.json|50be18b44f273821bb9f37a82e12ea8037caa335059659b35909b2ebac743188|
|prompt6d_v1/review_other_v3/decisions.json|99554b42ba8e92df7638f857e0b2662254873711555a9b955bc2d88efbffd619|
|prompt6d_v1/temporary_rebuild_comparison.json|d546366f3b2bea1ad19618e4386101f7e00b8c6d32ec68f3f78a63e65f03ed93|

机器统计：alignment_v3_compact.json、category_counts.csv；抽样与逐条依据：review_other_v3/；六文件证明：mapping/six_files/；新增空表：review_v1b/。旧v1/v2报告与判断均保留，不能把候选版本混作最终统计。
