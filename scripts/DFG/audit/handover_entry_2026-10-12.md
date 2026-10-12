

#### 2026-10-12：DDG 第一阶段已实施（修改 AI：Codex）

本条是当前实现状态，覆盖前面 DDG 方案中“尚未实现”“放 Test_code”“首版必须包含mapping”等历史建议；其余历史不删。用户本轮要求函数内正向 Definition–Use、只新增 DATA_DEF_USE，暂不加REV、不新增变量节点。

- 新逻辑、测试、示例、审计全部在 scripts/DFG/。原生产代码只改 sco_models/graph_utils.py::reflect_graph：精确名 DATA_DEF_USE 保持方向，旧关系反射原样保留。
- 已实现双AST/UTF-8坐标、版本作用域、标量DEF/USE、独立语义CFG、固定点到达定义、原HCG严格投影、附边不变量、use_ddg开关、旁路checkpoint输入/schema校验。
- 不改原tokenizer、HGT核心、两阶段检测逻辑、标签、早停、LR或梯度修复。保存现有节点与全部原边，复杂/不确定情况保留图并报告回退。
- 最终测试 **140 passed = DDG 121 + 原测试19**。两类HGT在inside_token下forward/backward、DDG关系梯度、参数更新及checkpoint重载通过。E0对修改前reflect的权重和eval输出逐位一致。
- 最小例用真实缓存CodeT5p-770m tokenizer及原encode_ids：11节点/12边→11节点/19边，新增7条DATA_DEF_USE；节点和合约模型各一次优化，重载逐位一致。**没有新正式F1结果**。
- 真实buggy_18单文件：重入作者/本地图均74条新增边，访问控制均114条；按原源码span对齐相同，基础属性不变。每组10个未映射facts来自5个无HCG节点的emit，未猜最近行。
- 修复审查发现的for update粒度错误：现i++映射自己的原节点，非整个for头；原HCG/CFG不变。modifier、引用类型、复杂副作用等仍回退。
- 原图生成时源码SHA通常未知；本轮记录的是提供源码摘要及节点文本/锚点一致性，不能说完整恢复了作者历史生成过程。
- 本版覆盖率仅针对受支持标量facts；没有实现完整state/mapping、跨函数、隐式返回定位、任意源码cascade或完整消融runner。保留标签只保证控制变量，不能证明标签绝对正确或DDG必然提升。
- 完整E0/E1实验仍需固定折、标签、token、best/last及种子，并在每折对齐共同初始化；原训练器不会自动调用新schema校验器。

文档/产物：
- scripts/DFG/IMPLEMENTATION_NOTES.md：十阶段逐项文件、原因、逻辑、测试、遗留问题。
- docs/training_changes_2026-10-07.md **第12节**：详细修改与回退记录。
- scripts/DFG/README.md：验证、开关、附边和训练接入命令。
- scripts/DFG/artifacts/minimal_20261012_v1/result.json：最小端到端结果；audit/phase*.log为阶段日志。
- scripts/DFG/audit/real_projection_probe.json：两类作者/本地真实图单文件审计。
- scripts/DFG/audit/implementation_before_2026-10-12.json 与 implementation_after_2026-10-12.json：本轮范围/摘要核验，原代码和文档快照同目录。

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm
conda activate mando
export TREE_SITTER_LIB_DIR="$PWD/build/linux-x86_64"
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/tests tests/test_graph_utils.py tests/test_model_imports.py \
  tests/test_classifier_cli.py tests/test_early_stopping.py
~~~

最简回退：使用原图/--no_ddg，原反射函数无需撤回。若必须撤回代码接入，核对文件摘要后只移除 DDG FORWARD FIX 精确分支，勿整文件 git restore。两份最初方案文档和2026-10-11分析报告保持历史原文未改。
