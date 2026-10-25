# Prompt 6：依赖正确性验证结果

日期：2026-10-25。实施、独立复核与记录：Codex。分支：dfg-v2。

本轮完成验证工具与规定产物；发现1项L1覆盖缺口并登记为Prompt 6b输入。没有修改L1/L2/L3、pipeline、HGT、tokenizer、图、标签或训练逻辑。不能将本报告解释为Oracle全通过或完整Solidity语义已验证。

## 版本及验证独立性

起点f5e1260；先封存20对手写源码/期望，提交aded5023a0adb759cb458b2e238ccdc480be1d35，再运行分析器。工具/测试/封存与分类提交f80073f34d6747a9e94fa67c0a1fefa93e231bc9。所有40个原始Oracle文件保持SHA；期望没有依据运行结果回写。

用户已批准tuple按现有语句粒度验证：x/y定义→tuple、tuple→a/b使用，检查声明身份和禁止边；不验证tuple内部逐元素来源，不新增节点。所有样例未执行编译验证。

## Oracle结果

最终依据：../experiments/artifacts/dfg_v2/prompt6_v1/oracle_run_v2/summary.json（相对本目录需回到scripts/DFG后进入experiments）。20例执行，17例完全匹配，3例有差异。32条禁止边约束全部满足；8项差异全部有绑定报告SHA的逐项分类。

| 用例 | 差异数 | 分类及原因 |
| --- | ---: | --- |
| 04_for_update | 6 | 期望错误：原CFG已有独立i++更新节点，手写期望误投到整个for |
| 18_environment_synonyms | 1 | 期望属性拼写错误：源码是gasleft()，不能用gasleft作原始拼写 |
| 16_call_option_fields | 1 | 实现覆盖缺口：L1不识别call选项的struct_expression，整函数回退漏掉x读取 |

for的实际节点来自CFG_solidity.py的update_node_id，循环更新顺序可参见[Solidity 0.5.17控制结构](https://docs.soliditylang.org/en/v0.5.17/control-structures.html#control-structures)。环境拼写依据为[Solidity 0.4.26环境量](https://docs.soliditylang.org/en/v0.4.26/units-and-global-variables.html#block-and-transaction-properties)。期望错误有代码/语言证据，原期望与SHA仍保留。

实现缺口的最小例子：
~~~solidity
uint x = 1;
target.call{value: x}("");
~~~
L1在AccessExtractor.reads及v2的V2AccessExtractor.reads处对struct_expression回退；没有提交该函数的部分DDG，原函数/HCG仍在。L2正常读取target并排除value/gas/salt字段标签。value中的x确实是读取表达式，参见[Solidity 0.6.12外部调用](https://docs.soliditylang.org/en/v0.6.12/control-structures.html#external-function-calls)。这是保守漏边，不是错误连边；未核查真实语料恢复量，不能据此解释历史F1。

| 关系 | TP/FP/FN | Precision | Recall |
| --- | --- | ---: | ---: |
| DATA_DEF_USE | 47/4/3 | 92.16% | 94.00% |
| WRITES_STATE | 8/0/0 | 100% | 100% |
| READS_STATE | 15/0/0 | 100% | 100% |
| ENV_FLOW | 12/0/0 | 100% | 100% |

这是相对原始封存期望的计数，包含期望错误；不能当成全语料真实正确率。24条设计近似显式标记。v1报告保留；v2补充spellings/via_alias属性、执行错误完整性及配对检查，避免只看边端点掩盖问题。

## Slither与人工抽查

Slither0.8.0/crytic_compile0.2.4存在，但没有solc-select和获准的离线编译器。R的142文件、AC的114文件全部明确跳过；其中213文件还缺精确版本metadata。编译次数、比较次数均0，指标null。没有下载、安装或执行新solc。L1审计仅有投影端点，外部事件级对照为partial，不能宣称已验证完整召回。

人工表位于：
scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv

固定seed=0，R/AC各15文件，共512条边；DATA_DEF_USE 132、WRITES_STATE 122、READS_STATE 129、ENV_FLOW 129。原源码位置与证据、空表及seal齐全。AI未填写任何verdict。

只填写verdict（correct/wrong/unsure）和note，其他列、顺序与行数不要改。评分时校验这些不变量；correct/(correct+wrong)与Wilson95%区间按关系报告，unsure及空白单列。全空表指标为null。

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
python -B -m scripts.DFG.dfg_v2.score_review \
  --csv scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.csv \
  --seal scripts/DFG/experiments/artifacts/dfg_v2/review_v1/review_sheet.seal.json
~~~

## 测试与不变量

最终765项v2测试＋223项旧DDG/graph_utils回归＝988 passed，0失败/跳过。8/29条既有DGL/NetworkX弃用warning。Oracle/Slither/review定向测试分别19/19/28 passed。测试通过包括“正确检出错误”的测试，不代表全部Oracle匹配。

~~~bash
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
~~~

11128个保护文件SHA及三份历史文档前缀保持。store SHA：
43e45227f7ccd9ebcbb034cb9e64b2cf430acf2c81dfb458b6ceadc344c67d5b

验收证据：scripts/DFG/experiments/artifacts/dfg_v2/prompt6_v1/final_acceptance.json。完整实施/用户选择/命令见docs/training_changes_2026-10-07.md第48节和PROGRESS本轮记录。

## 停止位置

本轮达到“所有Oracle差异已归类、外部对照有明确跳过原因、空表与封存已交付”的要求。Prompt 6b仍须修复调用选项L1覆盖缺口，构建新graphs_v2并复验；不覆盖本轮图/报告。人工复核与实际编译对照尚未完成。

没有开始Prompt 6b/7/8、GPU预检、模型训练或新增类别实验。按共享上下文完成三次本地提交后停止，未自动push。新增中文文档的管道编码问题已在提交前修复，历史正文未变。
