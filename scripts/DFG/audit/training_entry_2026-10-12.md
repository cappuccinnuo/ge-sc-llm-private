

**12. 函数内正向 DDG 第一阶段（Codex，2026-10-12）**

**12.1 时间、归属与授权**

修改 AI：**Codex**。记录日期按 America/New_York；验收摘要核对时间为 2026-10-12 02:03 EDT / 06:03 UTC。该时间不是 Git 提交时间。用户本轮明确授权按 Phase 1–10 实施，并更新本训练文档与 HANDOVER.md。

所有新增 DDG 核心、测试、分析、示例和审计位于 scripts/DFG/。原项目生产代码只在 sco_models/graph_utils.py 的 reflect_graph 增加一个分支。既有 tokenizer、HGT 核心、分类任务、梯度修复、早停、LR、划分和保存机制均未修改。

更早工作区已有改动不能算成本轮新实现。完整当前实施记录：[IMPLEMENTATION_NOTES.md](../scripts/DFG/IMPLEMENTATION_NOTES.md)；运行入口说明：[README.md](../scripts/DFG/README.md)。

**12.2 与上一轮分析的关系**

2026-10-11 Codex 只新增 DDG_INTEGRATION_ANALYSIS_2026-10-11.md 及 audit/review_manifest_2026-10-11.json，没有改算法或训练。那轮在内存证实旧 CFG 可将 return 接到后继语句，核对两类作者/本地节点对齐与 HGT 反射行为；这些是分析，不是已经实现 DDG。

本轮用户新要求优先：只实现函数内 Definition–Use、只新增 DATA_DEF_USE、不新增变量节点、暂不做 REV。上一轮报告的完整消融 runner、共同参数每折对齐、REV、任意源码 cascade 并未在本轮全部实施，不能把计划写成结果。更早 HANDOVER 提出的 Test_code 目录、首版必须含 mapping 等，是历史建议，本轮以此次明确授权为准。

**12.3 各 Phase 的文件、逻辑与测试**

下表测试数字是阶段当时累计数量，后续修正另记；最终全套为 140 passed。

| Phase | 新建文件（均在 scripts/DFG） | 修改及原因 / 核心逻辑 | 测试与限制 |
| --- | --- | --- | --- |
| 1 | __init__.py、models.py、tests/test_models.py | 不可变源码/符号/事件身份，内部 CFG 数据结构；不产生模型变量节点 | 2 passed；基础结构不代表语义完成 |
| 2 | frontend.py、symbol_table.py、tests/test_frontend.py、tests/test_symbols.py | raw/compat 双 AST、UTF-8 span、版本作用域、声明唯一 ID | 26 passed；复杂类型/版本歧义/modern同名初始化先回退 |
| 3 | access_extractor.py、tests/test_access.py | 事件内先 USE 后 DEF；赋值/复合赋值/递增/delete/tuple；未知 RHS 仍 kill 被赋值标量 | 46 passed；不确定副作用回退，storage 不冒充局部变量 |
| 4 | semantic_cfg.py、reaching_definitions.py 及两测试 | 独立控制流；静态 defID、GEN/KILL、worklist 固定点、收敛后 facts；过滤不可达块 | 70 passed；modifier/assembly/try等回退，未顺带修旧HCG |
| 5 | ddg_builder.py、tests/test_ddg_builder.py | 直接 facts 汇总、同端点同关系去重，保留多符号证据 | 79 passed；不做闭包，自环facts保留但不输出边 |
| 6 | projection.py、tests/test_projection.py | 按文件/AST ID/类型/代码/坐标唯一核验；缺节点不猜最近行 | 88 passed；emit等缺节点会损失覆盖 |
| 7 | pipeline.py、graph_audit.py、tests/test_pipeline.py、test_model_integration.py初版 | 深拷贝附边、不变量核验；原 reflect_graph 对 DATA_DEF_USE 保持方向 | 102 passed，含既有图工具；仅inside_token已认证 |
| 8 | model_validation.py；扩展模型测试 | 节点/合约前向反向、DDG梯度、更新、schema+输入摘要、重载 | 115 passed；集成20项；原正式训练未自动调用新validator |
| 9 | configuration.py、cli.py、tests/test_configuration.py | use_ddg默认false；同一原图生成E0/E1；新目录、拒绝覆盖、输入摘要和重读 | 121 passed；不补token、不改标签，缺源码保留并报告 |
| 10 | demo.py、tests/fixtures/minimal.sol、tests/test_end_to_end.py | 原生成器＋真实缓存tokenizer＋既有encode_ids＋DDG＋两模型单步更新/重载 | DDG 121 + 原测试19 = 140 passed；没有正式K折/F1结果 |

测试日志位于 scripts/DFG/audit/phase*.log。另有 README.md、IMPLEMENTATION_NOTES.md、本节与 HANDOVER 的追加条目、运行前后摘要及回退快照。没有修改两份最初的 DFG 方案文档。

**12.4 唯一原项目生产接入**

文件 sco_models/graph_utils.py，reflect_graph 原 L426 起；新增分支位于 for metapath, value 循环内部、原反射 if 之前：

~~~python
# DDG FORWARD FIX (Codex, 2026-10-12): only the new relation is directed.
# Original behavior below reflected every relation, including DDG.
# Removing this branch restores the original behavior; no base edge changes.
if metapath[1] == "DATA_DEF_USE":
    symmetrical_data[metapath] = value
    continue
~~~

其余旧反射分支未删除、未重写；因此保留旧代码本体与说明注释，没有复制整段旧函数造成双份实现。快照：scripts/DFG/audit/graph_utils_before_2026-10-12.py.txt。

原 generate_hetero_graph_data 已按 (src.node_type, edge_type, dst.node_type) 自动建元关系，不需要改。现有两个 HGT 模型直接从增强图建立新增关系参数，无需重写 HGTLayer。新增边类型会增加 canonical relation 和参数量，不能说模型参数量完全不变。

**12.5 复核中发现的问题及限定修正**

1. frontend 的叶节点比较起初遗漏字符串正文；改为完整 literal token，并加预处理改变字符串必须拒绝的测试。多条 pragma 暂回退，不用 experimental 掩盖矛盾版本。
2. pytest 将名为 setup 的测试辅助函数识别成生命周期函数，首轮产生18个 setup error；只重命名测试辅助函数，之后通过，未为此改变算法。
3. 注释不应改变裸 return/throw 和 for condition 的语义；先过滤注释。普通 revert 参数的实际 AST 有 parenthesized_expression，不只 revert_arguments，已据真实形状修正。
4. 终止 builtin 可能被同名用户函数、导入、继承遮蔽时保守回退，避免把后续代码错误判为不可达。
5. for 更新表达式在原 HCG 有独立 i++ 节点，初版归整个 for 头是错误映射。已暂停后续验收并说明，改成更新表达式自己的 span，加入真实图 oracle 测试，补修后累计103通过。for初始化无独立节点时仍归循环头，明确为投影粒度限制。
6. 合约模型接收但不保存 node_feature 属性，新 validator 初次假设该属性存在导致两项测试失败。只改旁路校验为实际 inp/token 一致性检查，不向原模型增加属性；最终20项模型集成通过。
7. 原 HGT 已有孤立类型的零消息分支，本轮只测试其仍能工作，不将它冒充本轮新增修复。

**12.6 保护条件与实测**

- 输入图不被修改。新图节点顺序、ID、类型、code、token字节/shape/dtype、漏洞标注、源码字段、文件归属、旧边类型/端点/key/重数逐项核验。
- DDG构建不读取漏洞标签进行决策；打乱标签后依赖边不变。Projector中的 label 是 AST 标识字符串，与 node_info_vulnerabilities 不同。
- 不支持的函数仍在输出HCG中；只是不附加未经证明的数据边。某些 storage 表达式仍可读取已知局部索引，但不表示实现了 storage 内容依赖。
- DGL中同/跨类型 DATA_DEF_USE 的方向与输入完全相同；不会自动产生同名反向或 REV。
- E0使用冻结旧反射与新反射，在相同seed下权重和eval logits逐位一致。
- 当前源码SHA、实际代码/锚点一致性是本轮审计；原图通常没有生成时源码SHA，因此不能声称完整恢复了作者图的历史源码身份。

真实单文件审计（audit/real_projection_probe.json）：

| 类别 | 作者/本地均一致的节点 | 支持函数 | facts / 投影facts | 新增边 |
| --- | --- | --- | --- | --- |
| 重入 buggy_18.sol | 383普通 + 41合成 | 45/69 | 96/86 | 74 |
| 访问控制 buggy_18.sol | 273普通 + 11合成 | 60/67 | 156/146 | 114 |

两版本新增边按原源码 span 对齐后相同，每组10未投影facts对应5个没有原HCG节点的emit。支持率/投影率仅针对当前分析范围，不等于整个Solidity程序的数据依赖完备率。

最小真实tokenizer示例（artifacts/minimal_20261012_v1/result.json）：

| 项 | 结果 |
| --- | --- |
| tokenizer | Salesforce/codet5p-770m，本地缓存，无完整LLM前向 |
| 特征 | 原 encode_ids，float32[512] |
| 原图→增强图 | 11节点/12边 → 11节点/19边 |
| 新增关系 | 7条 DATA_DEF_USE，无REV |
| 节点/合约输出 | [11,2] / [1,2] |
| DDG relation_msg 梯度L1 | 3.91129184 / 5.12457860 |
| 更新/重载 | 两模型均通过，重载logits逐位相同 |

样例全clean标签只用于接口检查，不是漏洞标注实验，不能据其loss或预测声称检测性能。测试宿主时钟偶有跳变，pytest个别耗时异常，未将日志耗时用于性能比较。

**12.7 终端命令与产物**

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"

PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests \
  tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py

python -B -m scripts.DFG.demo \
  --output scripts/DFG/artifacts/minimal_manual_v1
~~~

输出目录须未存在，再次运行换名字。最小示例只做单步更新，不跑正式折训练。

给现有窄图附边的入口（本轮未自动跑完整语料）：

~~~bash
python -B -m scripts.DFG.cli \
  --graph experiments/ge-sc-data/source_code/reentrancy/tokenizer_ids_narrow.gpickle \
  --source_dir experiments/ge-sc-data/source_code/reentrancy/source_files \
  --output scripts/DFG/artifacts/reentrancy_narrow_forward_v1 \
  --use_ddg
~~~

对照用同一原图配 --no_ddg、新输出目录；行级需换成原漏洞子图作为输入。新 hcg.gpickle 可传原训练脚本，标签JSON仍由原流程提供。详细参数/正式训练接入示例见DFG README。

**12.8 待解决事项与回退**

- 暂无本轮测试失败；仍不支持完整storage/mapping/reference依赖、跨函数摘要、modifier执行、复杂副作用、隐式返回的完整投影和任意源码cascade。
- 没有运行正式K折或比较F1。下一次完整E0/E1实验需固定标签/图/token/折/种子/权重选择，并在每折构造时对齐共同初始化；只加同seed不够。
- 新 checkpoint validator 是旁路辅助，原训练器未自动调用。正式实验必须额外绑定合约标签和fold摘要，不只绑定图。
- 节点标签保持不变不等于证明ground-truth正确；新增DDG能否提升、是否受模板记忆影响仍待实验。
- 最简回退是输入原图或--no_ddg，旧关系行为已验证一致。不要给原图加载增强图关系权重。
- 如需撤销原接入，核对摘要后只移除 DDG FORWARD FIX 分支；不要 git restore 整文件覆盖历史工作。

| 文件 | 本轮前SHA256 | 本轮后SHA256 |
| --- | --- | --- |
| sco_models/graph_utils.py | 1bdedc8f72ae3e1abd7cfa26cd5c5c071f590ea3456af225064e13ad850bcc48 | 5da9afc69f4528b63e4acf9595588b20b06d15cf3d508a49d56f10e33116015d |

完整前后清单：scripts/DFG/audit/implementation_before_2026-10-12.json、implementation_after_2026-10-12.json。两个文档的修改前快照也在该 audit 目录。本节追加，不删除前文历史。
