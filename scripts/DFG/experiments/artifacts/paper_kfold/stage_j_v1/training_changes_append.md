

## 24. 2026-10-19 Stage J：DDG整体构图入口与覆盖恢复（Codex）

**24.1 授权、设计选择与版本**

用户要求根据此前推荐完成DDG整体板块。基于Stage I的继承回退与错误覆盖证据，采用旁路实现“受限继承→受限modifier→精确投影→融合与审计”，没有跳过语义验证直接重训。整体闭环不等于完整Solidity分析；反向/控制依赖/跨函数摘要仍另行设计。

开发树ge-sc-llm-ddg-v11，HEAD保持021a6f55ac9e3f94fc70feb441ff48b51b6a92ea；原树HEAD保持f3dfc17908029355c5fc45d6d3932f203068fcf5。实现版本ddg-stage-j-coverage-v1，批次stage_j_v1。原DDG/Stage F、HGT、tokenizer、训练器、作者标签和旧实验不修改；无pull/checkout/reset/commit/push。修改、执行与分析AI：Codex；完成时间2026-10-19 UTC。

**24.2 新增文件、原因与关键逻辑**

主要新增目录：scripts/DFG/state/stage_j/，不搬移旧实现。

- binding.py：同一源码唯一基类、右侧优先C3和菱形去重；无参数基类、有限interface声明。保存声明span/owner身份；同名冲突、import、循环、无唯一基类、library/base参数等回退，不猜重载分派。
- modifiers.py：唯一且无参数modifier，恰有一个末尾顶层占位符；直线前缀支持已有表达式，require/assert须确认内建绑定及版本。拒绝多modifier、参数、后缀、多/条件占位符、前缀局部声明和副作用未知调用。
- analyzer.py：先执行旧Stage F；原成功结果复用，只重试回退函数。独立语义CFG为“参数入口→modifier前缀→函数体”，不替换模型CFG/CG。仍调用旧状态位置、提取及reaching definitions；失败函数无部分事实。另记录legacy构造器/运行时函数，避免把构造器恢复当作运行时提升。
- configuration.py：use_ddg、add_scalar、state_mode(off/def_use/orders)、recovery(frozen/inheritance/modifiers)、迭代上限。关闭时精确复制传入图，不反向删除已有DDG；恢复baseline必须传原baseline输入。
- pipeline.py：统一调用标量模块、版本/源文件分析、旧精确Projector及materializer。新事实加coverage来源与materializer/producer版本，最终再次验证指纹。禁止已有状态图二次叠加，不改node ID/token/标签/基础边；缺失投影保留原图、不按最近行猜。
- cli.py：显式本地图/源码SHA、拒绝覆盖、导出enhanced.gpickle/audit/manifest；复用Stage F四类正向关系DGL适配，检查真实canonical边数量。不会重写训练脚本。
- tests/__init__.py、test_semantics.py、test_pipeline.py：新增54项，覆盖继承/绑定/modifier/回退、投影/KILL、标签特征独立性、同端点多关系、配置及原HGT接口。
- README.md、DESIGN_AND_ACCEPTANCE.md：整体架构、实现边界、官方语言规则引用、真实入口和命令。
- scripts/DFG/experiments/stage_j_coverage/run.py及README：冻结manifest派生四任务三模式图，来源SHA/独立plan/seal/收据、增量覆盖统计；没有训练代码。

本次恢复主要发生于状态分析；原标量DATA_DEF_USE规则未扩展。本批以冻结E2为输入，标量边直接保留。通用入口可从原HCG调用add_scalar复用原模块。数据依赖事实投影到同一语句节点后与CFG/CG合并，不新建变量节点或独立图编码器。

**24.3 回退、方向与不变量**

原成功Stage F函数不重新解释。未知/不支持函数级回退，无临时DDG残留；原图所有样本保留。未投影写入仍执行KILL，未投影控制结构仍在分析IR中；原HCG锚点缺失只丢弃不可投影事实，不补点或猜最近行。

DATA_DEF_USE、STATE_DEF_USE、STATE_ACCESS_ORDER、EXTERNAL_CALL_BEFORE_STATE_WRITE均正向；增强在schema提取前物化。同端点不同relation保留；同relation重复证据合并边并保存侧表。状态顺序不是Def–Use；modifier权限检查也不自动等于控制依赖。内建终止和状态HAVOC沿用既有语义。

新增语义不使用标签或token值；对应扰动测试通过。新图仍有原图的标签语义不确定性，本轮未重新标注，也不声称解决作者标注来源问题。

**24.4 真实图生成与结果**

独立批次scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build。输入来自e23_pilot_v1/input_manifest，accepted Stage F sidecar由delivery摘要验证；sidecar是本批观察绑定，不能追认为旧H2 seal认证。

四任务各frozen/inheritance/modifiers，共12图。frozen复现原E3b状态关系集合；后两模式关系单调保留；全部原图指纹和实际DGL方向计数通过。

| 任务 | 文件/节点 | 原可分析→恢复后 | 恢复函数/其中运行时 | 新增状态关系 | 新上游上下文目标 |
|---|---:|---:|---:|---:|---:|
| 重入合约 | 142/18312 | 1316→2033 | 717/700 | 863 | 464 |
| 访问控制合约 | 114/13432 | 1299→2045 | 746/738 | 70 | 123 |
| 重入节点 | 71/12036 | 899→1372 | 473/470 | 806 | 415 |
| 访问控制节点 | 57/7710 | 965→1482 | 517/514 | 40 | 89 |

最终STATE_DEF_USE/STATE_ACCESS_ORDER/EXTERNAL_CALL_BEFORE_STATE_WRITE分别为重入合约9/1388/866，访问控制合约14/100/0，重入节点4/1322/859，访问控制节点5/55/0。两个节点任务新增STATE_DEF_USE各1条仍来自buggy_16构造器；不能宣称运行时DU稀疏已解决。

函数总量3388/3043/2045/1958与accepted F1逐文件一致。旧Stage I静态表额外16/105个合约函数记录均为file_fallback，来自2/6个版本证据不足/跨作用域版本边界文件；本批仍保留这些文件的原图，未进入函数分析，见function_population_note.json。

**24.5 后处理、困难文件与真实语义证据**

新增产物级audit_coverage.py/v2.py按task/file/sourceSHA/nodeID及原target对齐旧E2/E3b best预测；仅构图后诊断，不将错误标签送入分析。

重入旧E3b 425错误中39进入新增边两层局部范围、6有新上游节点；访问控制旧196错误均在范围外。旧E2对应439/39/8和206/0/0。局部范围不是新训练的因果边界，共享参数和canonical聚合还可能影响范围外；新增边不等于收益。

重入buggy_18新增17关系、恢复18函数，275旧错误中37进入局部范围、6有新上下文；buggy_36新增12关系但58旧错误未覆盖。访问控制buggy_18/26恢复33/30函数但新增模型边0，94/42旧错误未覆盖。

Codex源码证据核对：重入buggy_18 claimReward_re_ent18第249行读取→251清零产生STATE_ACCESS_ORDER，非反向伪Def–Use；访问控制buggy_17 onlyOwner第63行读取owner→68行写owner产生状态访问顺序，未制造权限控制边。完整SHA/原nodeID/字节锚点及源码在opportunity_v2/new_edge_cases.json；不是独立人工Oracle或编译验证。

后处理v1因合约/节点CSV字段不同在写表时失败，失败脚本和日志保留。v2改为列并集写入opportunity_v2，构图源码、图、统计定义不变。首次全DDG pytest收集时test_pipeline模块同名冲突，通过给新增tests补__init__.py解决；未删除或放宽测试。

**24.6 测试、验收命令与实际结果**

在mando环境、开发树、TREE_SITTER_LIB_DIR指向原项目现有build/linux-x86_64：

~~~bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests scripts/DFG/state/tests scripts/DFG/state/stage_f/tests scripts/DFG/state/stage_j/tests
python -B -m pytest -q -p no:cacheprovider tests
python -B -m scripts.verify_h1_archive
python -B -m scripts.verify_h2_archive
~~~

DDG377通过（含新增54），0失败/跳过，28条既有DGL/NetworkX弃用警告；原项目25通过，0失败/跳过，7条既有TensorBoard/DGL/NetworkX警告。合成HGTLayer前向、关系非零有限梯度及checkpoint重载通过，optimizer_steps=0。真实12图不变量/SHA/schema通过；H1 52+8=60、H2 26+4=30只读归档复核通过。

真实构图命令：
~~~bash
python -B -m scripts.DFG.experiments.stage_j_coverage.run \
  --input-manifest scripts/DFG/experiments/artifacts/paper_kfold/e23_pilot_v1/input_manifest.json \
  --output scripts/DFG/experiments/artifacts/paper_kfold/stage_j_v1/build
~~~
目录已存在，重复命令会拒绝覆盖。通用入口及源码manifest格式见state/stage_j/README。输出包含各模式enhanced.gpickle/audit.json/manifest.json及批次plan/seal/receipt。新图不能直接替换冻结训练计划的输入，必须另行绑定新图/schema/初始化。

**24.7 未执行、剩余边界与保护**

没有运行新正式训练、GPU短检查、其他五类、反向DDG、控制依赖或跨函数摘要；没有下载/执行新solc。新增样例是解析/静态语义夹具，未完成编译验证；不把解析成功当作合法性证明。

后续优先核验新恢复事实和剩余错误缺口，按新候选图单独建立实验计划后再短检查；访问控制未覆盖的权限语义需要独立小型控制依赖Oracle，不能冒充状态DU。

旧183项代码/用户文件SHA不变，两工作树4文档仅追加；旧图/标签/token/计划/seal/权重不改。原用户auto_version_solc.py SHA保持bf3365c32f65f4c51932478eb54687a53c6aaad932f8f56a4d58687aaa493f31。保护与完整交付清单在stage_j_v1/protected_after.json、delivery_manifest.json。主报告STAGE_J_RESULT_REPORT.md。完成后停止，不自动训练；修改与分析AI：Codex。
