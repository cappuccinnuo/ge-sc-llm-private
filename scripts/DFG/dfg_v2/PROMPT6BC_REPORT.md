# Prompt 6b / 6c 完成报告

日期：2026-10-25。实施、验证与记录：Codex。分支：dfg-v2。

## 结果

Prompt 6b的L1读取缺口已修复，四任务新图重建和差异验收通过。Prompt 6c已完成真实Slither对照。旧HCG节点、标签、特征、基础边及L2/L3关系保持；没有训练模型。

后续图入口为：
`scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json`。

`graphs_v1`保留历史；首次`graphs_v2`因临时候选.py进入运行文件摘要而封存失败，保留失败记录，不得使用。同输入独立重建r1后，387个运行文件摘要一致，16图项与20个schema通过核验。

## 6b：修复和恢复量

L1仅修改`l1_access.py::ExtendedAccessExtractor.reads`：call选项读取接收者与字段值、不读取字段名；new表达式类型名不作为变量读取，构造参数仍由调用路径读取。旧DDG、CFG、符号表、投影和到达定义算法保持。

|任务|恢复函数实例|新增DATA_DEF_USE|旧边删除|
|---|---:|---:|---:|
|重入合约|7|51|0|
|重入节点|4|50|0|
|访问控制合约|6|60|0|
|访问控制节点|3|34|0|

新增数对每个累积F1/F2/F3图相同，不能将重复计数585当成独立新增事实。20为任务函数实例，不是去重函数数量。真实语料恢复均来自new_expression；call选项的修复由定向测试及Oracle16证明。

用户事先批准并严格记录：
1. 补齐new_expression类型名的最小读取处理。
2. ddg_fact_indices允许重编号，但解析出的证据同序、同重数、全字段一致；其他旧边属性及身份严格保持。
3. 仍回退函数允许原因推进，但必须事实为空、partial=false、无残留边且身份等字段不变。重入两个任务各3个此类变化，均在spank_chain_payment.sol，未计为恢复。
4. 六个无pragma文件保持原默认0.4.25，单列fallback_default，编译失败不换版本。

原512条人工抽查边语义全部保持，76行只有引用编号变化；两个合约任务新增111条边不在旧抽查范围。表格未重采样、未代填，完成数0，人工精确率为null。

Oracle：18/20例完全匹配；16_call_option_fields已修复，剩余7个差异沿用原“期望问题”分类。原期望和分类文件未改，新CLASSIFICATIONS_v2绑定修复提交。现代Oracle样例未执行编译验证，不能将Tree-sitter解析或真实语料的solc结果当作其语言合法性证明。

新增store_diff和score_review的equivalence校验保留篡改、错引用、重复引用及回退残留的失败测试。定向修复前失败、修复后通过证据见training_changes第49节及prompt6b_v1日志。

## 6c：真实外部对照

用户明确允许安装/下载。新增solc-select1.0.4和pycryptodome3.20.0，原环境包版本保持；26个编译器核对SHA256、Keccak256和版本。未修改全局solc版本。

256文件的版本来源：43 metadata、207 pragma_derived、6 fallback_default。版本选择遵循原auto_version_solc规则，不把推导版本注入内部分析元数据。每文件只尝试预先选定版本。

|任务|文件|可比较|solc失败|映射不可比|L1 precision / recall|L2 precision / recall|
|---|---:|---:|---:|---:|---|---|
|重入|142|131|8|3|72.946% / 88.961%|98.902% / 86.946%|
|访问控制|114|108|3|3|60.526% / 87.871%|98.299% / 85.417%|

Slither分析失败、未知阶段失败、工具缺失跳过均0。这些是原始行/变量/读写的micro事件集合一致性，**不是漏洞F1，也不是DDG边召回率**。

- L1额外项中，重入98.59%、访问控制93.16%来自入口初始化差异：内部参数/返回值DEF在Slither CFG写集合中没有对应项，不能直接解释为错误边。
- L1缺失项中，重入96.54%、访问控制97.43%来自保留的函数回退。已支持函数召回99.573%/99.646%仅作诊断，主分母不变。
- 六个不可比文件使用旧0.4.0/0.4.2/0.4.9，当前Slither输出缺CFG filename，包括simple_dao和parity_wallet_bug_2。整文件不报部分P/R，未猜测来源；模型图与样本保留。
- 已确认L2三例：状态声明初始化不在当前L2函数内写范围；另外两例是跨行位置口径不同，实际投影边存在。其余不一致尚未逐一人工判断，不自动标成实现缺陷。
- 主比较三元组不能完全证明声明身份；附加身份审计保留歧义。别名/modifier排除与继承上下文并集分别记录。

## 测试、保护与提交

|验证|结果|
|---|---|
|全部v2单元测试|886通过，0失败/跳过，8条既有弃用警告|
|旧DDG及graph_utils回归|223通过，0失败/跳过，29条既有弃用警告|
|合计|1109通过|
|原跟踪文件保护|11,172个非授权修改文件SHA保持|
|文档|原历史前缀保持，只追加本轮记录|

实现提交：
- f270ed6：L1修复与定向回归。
- c09bbbc：新旧store等价性、人工表绑定及新版Oracle分类。
- 7918427：完整L1出现集合及版本绑定Slither验证。

## 复核入口与实际命令

详细实施、每次选择、失败记录、版本来源及SHA见[训练变化文档第49/50节](../../../docs/training_changes_2026-10-07.md)、[PROGRESS](PROGRESS.md)及[HANDOVER](../../../HANDOVER.md)。

本地产物根：`scripts/DFG/experiments/artifacts/dfg_v2/`：

- `prompt6b_v1/store_diff_r2/store_diff.json`与seal：旧图、原抽查表及新图的证据身份绑定。
- `prompt6b_v1/score_review_equivalent_r2.json`：原表映射新store的实际评分。
- `prompt6c_v1/slither_full/report.json`与seal：完整逐事件记录（约152MB，保留本地）。
- `prompt6c_v1/results_compact.json`、`result_review.json`：摘要及独立只读复核。
- `prompt6c_v1/final_acceptance.json`：输入、保护文件、测试与产物摘要。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.DFG.dfg_v2.validate_slither \
  --store scripts/DFG/experiments/artifacts/dfg_v2/graphs_v2_r1/store.json \
  --trusted-compilers scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/trusted_compilers_complete.json \
  --output scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/slither_full
~~~

正式输出已存在，若重跑须使用新目录。当前实现验证完成，不代表完整Solidity DFG已实现或模型提升已证明。人工边标注仍未完成，17个未能比较的文件与未人工判定差异保留。本轮未启动Prompt7/8、模型训练、更多类别或push。
