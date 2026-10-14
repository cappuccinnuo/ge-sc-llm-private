# DDG v1.1 正确性修复、上下文审查与状态依赖设计

修改 AI：Codex。日期：2026-10-13。版本：`ddg-v1.1-correctness-fix`。

## 目录与版本

- 原封存仓库：`/home/zhao/SmartContract/ge-sc-llm`。
- 隔离开发工作树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`。
- 两者起点 HEAD：`359a7f13d94fb2c7d8d5d4656d76a94a967e10e4`。
- 封存模型训练基仍为 `646e9b3495c0fe7f2c4a6e4b72d0bab64d6ee2fc`。
- 未提交、推送、更新依赖或下载编译器。原业务源码没有切换到v1.1。
- 原仓库仅按用户要求向 HANDOVER 和 training_changes 追加记录；旧字节前缀保留。代码修复发生在隔离工作树，旧图、checkpoint、plan/seal、诊断报告不变。

## 阅读入口

| 交付 | 内容 |
|---|---|
| D1_FIX_REPORT.md | 两处缺陷的修复、恢复量、回归及限制 |
| D1_CHANGED_FILES.md | 核心和测试修改位置 |
| D1_COVERAGE_BEFORE_AFTER.csv | 四任务前后统计 |
| D1_REGRESSION_RESULTS.json | D1通过后允许D2的验收记录 |
| D1_PROVENANCE.json | 新图、原输入、代码版本和SHA |
| D1_RECOVERY_ATTRIBUTION.json | 每条新边的事实级恢复原因 |
| D1_FUNCTION_CHANGES.json | 函数分析/投影状态的前后差异 |
| context_design/D2_CONTEXT_REVIEW.md | 真实函数上下文与语义边界 |
| context_design/D2_LABEL_AMBIGUITY.md | 作者标签、公共标注与局部重复歧义 |
| context_design/results/D2_CASE_AUDIT.csv | 逐案例精确身份及审查表 |
| context_design/results/D2_CASE_EVIDENCE.json | 全函数、原始节点和原标签证据 |
| context_design/results/D2_TRAIN_DUPLICATES.json | 训练重复来源的文件、原ID及源码 |
| context_design/D3_STATE_AWARE_DDG_DESIGN.md | 状态位置、事件、别名与关系语义规范 |
| context_design/D3_ORACLE_SPEC.md | 待独立人工核验的正反例，不是漏洞认证 |
| context_design/D3_IMPLEMENTATION_PLAN.md | 后续模块、测试、实验设计；本轮未实施 |
| protected_before.json / protected_after.json | 原资产保护与授权文档追加结果 |

## 已完成与未执行

D1实际修复并重新生成四套增强图；D2实际审查，不重标注；D3仅设计、接口与Oracle。没有 Dataset A 模型训练，没有新的F1，也没有State-aware实现。原E0/E1不变，新图简称E2，不表示已有E2成绩。

新图位于：
`after/reentrancy_author/E2_contract.gpickle`、`E2_node.gpickle`；
`after/access_control_author/E2_contract.gpickle`、`E2_node.gpickle`。

E0直接引用原manifest里的固定输入，不重新序列化。E2的DDG元数据版本和证据索引可不同，旧端点/canonical/语义事实不变。节点图的canonical增加可能改变后续模型参数量；不能把旧checkpoint直接当成新图训练结果，也不得为此改旧seal。

## 实际环境与测试命令

Python：`/home/zhao/miniconda3/envs/mando/bin/python`；沿用Python3.7、PyTorch1.8、DGL0.6.1。语法库为原本地库的SHA一致拷贝；没有执行solc编译。

从隔离worktree运行：
~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2

python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests scripts/DFG/experiments/tests tests \
  scripts/DFG/experiments/audit/ddg_v11_correctness/context_design/test_context_audit.py \
  -k 'not test_actual_prepared_inputs_form_exactly_thirty_paired_jobs'

python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/audit/ddg_v11_correctness/test_audit_guards.py
~~~

原绝对路径资源断言必须在原目录执行，测试和formal源码均未修改：
~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/experiments/tests/test_formal_controller.py::test_actual_prepared_inputs_form_exactly_thirty_paired_jobs
~~~

上述第一命令在D2后增加3个完整性测试后收集数会比初次389多3；本轮各次实际命令及输出以对应JSON/log为准。不通过删除测试或修改期望解决绝对路径绑定。

## 构图审计与D2执行记录

`coverage_rebuild.py --repo <原目录> --stage before` 实际重放封存版本；
`--repo <新工作树> --stage after` 实际生成修复图；
随后 `finalize_d1.py` 核验并产生D1门槛；
`context_design/context_audit.py --d1-gate <D1_REGRESSION_RESULTS.json>` 执行D2。

这些命令均拒绝覆盖已有输出；不要直接重跑来改写本次证据。后续重新生成应使用新的审计版本目录，并保留当前输入和代码摘要。D1阶段失败尝试、测试修正环境的说明及前后日志都保留。

## 与模板相比的必要调整

1. 独立worktree保留原代码与封存资产；原根目录只追加用户明确要求的两份历史文档。
2. 精确pydot匹配之外增加多行字符串歧义拒绝，防止修复反而放宽错误匹配。
3. 本地资产与绝对路径测试分开执行，未改历史资源路径或seal。
4. 函数支持率、提取事实、投影事实和最终边分开统计；不把缺陷修复冒充完整数据依赖支持。
5. D2区分 state owner、参数owner_txorigin、数组map与真实mapping；不按文件名或变量名字推断语义。
6. D3入口未知状态和外部调用失效必须从最小原型就处理；modifier控制依赖另行设计。先读余额再调用再清零可能不产生具体的函数内state DEF→USE边，不能为了增加边数倒连后续写入。
7. 只有后续Oracle、支持边界和实际投影量通过，才值得建立新的E2/E3训练计划；本轮停止于报告。
