# RTX 5080 全创新整合分支

本分支由用户于 2026-11-14 要求创建，用于在新环境从 GitHub 获取全部已有创新，后续从源码重新构图、生成特征和训练权重。

## 当前状态

已完成分支和提交历史整合；尚未实施或验收 RTX 5080 环境升级、历史路径解耦及从零运行入口。
原 main、ddg-v1.1-correctness、dfg-v2、node-sem、edge-sem、compile-repair 分支及原工作目录保留。
这里“全部”指下表截止提交的 Git 已跟踪内容；本机未跟踪的模型、图、缓存和环境不因建分支自动加入 Git。

## 纳入的分支

| 来源 | 截止提交 |
| --- | --- |
| main | e76285a67a79dc5664c98309a8f2f32cd7342779 |
| ddg-v1.1-correctness | e7bcb8496d265c61e4d27566f78d26baa9e37594 |
| dfg-v2 | 1447c271a930edb26350f004ba8c63be70f1d2b7 |
| node-sem | 306c135b8a4f0c79b092e2690b0f0d10962f5290 |
| edge-sem | 88cc13a77538d327c54057f74ed42bc8d73fa298 |
| compile-repair | 0e6830edc00976e7df618e4d0b6ab28afd60cc26 |

所有列出的提交均为本分支祖先。核验记录见 [分支清单](docs/rtx5080_branch_manifest.json)。

- DFG v1.1、状态/控制依赖和完整 DFG v2：scripts/DFG/。
- 节点增强 CODE、CTX、STATIC、教师/学生模块及已跟踪结果：scripts/node_sem/。
- 边关系、边属性、边增强 HGT 及 EP9 结果：scripts/edge_sem/。
- 编译修复、Slither 图事实和 CP2.2 验收：compile_repair/。当前到 CP2.2，CP3 未执行；遵循该模块既有审查边界。
- main 的历史交接和归档提交已合入；其交接正文已包含在较新的 EdgeSem 文档前缀中。

合并没有修改算法：EdgeSem 起点的全部已跟踪文件仅 DFG PROMPTS 更新为该分支最新方案；compile_repair 子树与其截止提交逐文件 Git 对象一致。新加的本页、清单和交接追加属于本次整合说明。
main 的 README 冲突保留当前仓库内的集成入口；auto_version_solc.py 只在 main 多出三个前导空行，保留原代码字节。

## 在另一台机器获取

    git clone --branch rtx5080-rebuild https://github.com/cappuccinnuo/ge-sc-llm-private.git
    cd ge-sc-llm-private
    git branch --show-current
    git rev-parse HEAD

私有仓库访问使用新机器自己的 GitHub 授权。该命令获取代码与 Git 跟踪的结果记录，不会复制本机 conda 环境或未提交权重。

## 后续迁移边界

1. 新建支持 RTX 5080 的环境并验证 PyTorch、CUDA、DGL 的组合；现有 requirements.txt 记录的是旧参考环境，不能视为新环境安装完成。
2. 复用现有 compile_repair 和 tree-sitter 工具评估构图接入，明确节点粒度、源码锚点及独立的标签投影规则；不能直接把 Slither IR 节点当作原语句节点。
3. 将历史任务/绝对路径/8H plan 的接入改为新数据集清单；旧计划、seal 和结果作为历史证据保留。
4. 新图需要新生成 DFG 证据、CODE/CTX/STATIC、边属性及训练初值和权重。算法代码复用不代表旧逐节点数组可直接转用。
5. 外部预训练模型按固定 revision 下载；项目训练权重重新训练。Pre-trained-model、解析器编译产物、部分原始标注和外部依赖需要单独准备。
6. 原名视图作为后续主实验意图；匿名视图保留历史实现和对比接口。文档中更早批次的视图选择仍解释其历史批次，不自动覆盖新计划。
7. 在新图、同一标签和划分下重新建立基线与增强配置对照；全部创新代码同处一分支不代表三个模块叠加后的模型已经完成联合验收。
8. 先完成干净克隆的端到端验收，再开展正式批次。最终服务器实验另行登记；旧本机的显存限制不作为新环境的固定限制。

本次没有启动训练、安装依赖、重建图或改写历史实验配置。

## 2026-11-15：从源码构图（第 2 项）

`python -m hcg build` 已实现从源码构建七类 HGT 输入图，结果与作者图结构完全一致，详见 hcg/README.md。DFG v2、NodeSem、EdgeSem 改读新图并登记其余五类尚未进行。

## 2026-11-15：DFG 接入新图与项目重构（第 3、4 项）

- DFG 实现移入顶层 `dfg/` 包（schema / analysis / graph / model / inputs / store / train），直接读取 `python -m hcg build` 的输出，七类均已登记：`python -m dfg build`、`python -m dfg train`、`python -m dfg report`，详见 dfg/README.md。
- 等价性：新包对 7 类 × 2 任务 × F0–F3 的图内容指纹与重构前 `scripts/DFG` 代码逐位一致；重入/访问控制四任务的每个 profile 关系边数、fold0 五个 profile 初始参数摘要、全部节点匿名代码、30 个嵌套折、重复组划分均与封存的 Prompt 8 证据一致（tests/dfg/）。
- 发现并修复：CI 未固定 pydot（装到 4.x），而 DFG 投影调用了 pydot 3 起删除的 `quote_if_necessary`，新环境下 DFG 直接报错；`dfg` 改用 hcg 的 quote（七类 226,898 个字符串上与 pydot 1.4.2 结果一致），CI 固定 pydot==1.4.2。此修复也使 NodeSem 19 个原先失败的测试通过。
- 训练默认用 hcg 标签（10 月 10 日公开标注策略）与原名特征；`--features anonymous` 保留 8H 的匿名视图。L-audit 诊断标签、G0P 安慰剂、封存/收据/修订层不在主线，保存在归档分支 `archive/pre-restructure-2026-11-15`。
- `scripts/DFG` 只保留 NodeSem/EdgeSem 仍在导入的 131 个旧模块（集成这两个模块时再移除）；已迁移模块经 `scripts/DFG/__init__.py` 的导入映射指向 `dfg` 中同一模块对象。DFG 产物（约 5 GB）与 `scripts/verify_{e23,h1,h2}_archive.py` 已从主线移除；新训练结果写入不跟踪的 `runs/`。
- EdgeSem 对 HGT 层源码的导入时 SHA 检查改为测试（tests/dfg/test_units.py），所继承的层代码未变。

## 2026-11-16：NodeSem 接入新图（含 LLM）与重构

- 复查：发现并修复 `dfg.train` 两处问题——未检查 DFG 图是否由当前 HCG 构建；续跑时不同配置的结果可能混入同一目录（均已拒绝）。另发现移植时节点任务 OneCycle `div_factor` 误用 20，8H 实际为 25（合约任务 20），已修正并加测试固定两类任务配置。
- NodeSem 移入顶层 `nodesem/` 包（inputs、text、facts/、context、static、pipeline、store、encode、llm/、student、features、model、init、train），读取 `data/hcg` 与 `data/dfg`，七类均可运行：`python -m nodesem analyze|encode|describe|train|report`，详见 nodesem/README.md。按用户决定包含全部配置（S0o/S1o/S2/S3/S3m/S4/S4g/S4m/S4-noG/S5/S6/S8，含 LLM 教师与学生）。
- 等价性：分析阶段（代码文本、facts、CTX、STATIC）在七类 × 两任务上与原 NodeSem 代码逐位一致；重入/访问控制与封存产物逐文件一致（访问控制 6 个节点的状态读取列表顺序随图边顺序不同，内容相同）；新图上的 LLM 提示共 4,485 个缓存键，与封存 llm_v3 完全相同，因此原机器上的回复缓存可直接复制到 `data/nodesem/llm_cache` 复用；S0o/S2/S4 × G0/G3R 的 fold0 初始权重与封存 N-A 摘要一致；教师文本路径在合成回复上与原代码逐行一致。
- `scripts/node_sem` 只保留 EdgeSem 仍导入的 15 个模块与测试夹具（集成 EdgeSem 时移除），其余 5,014 个文件（含约 6 GB 产物）已从主线移除，保存在归档分支；EdgeSem 测试结果与清理前逐项相同。
- 编码器与 LLM 在 GPU 上以 fp16 运行（与原实验一致），向量与旧结果在 fp16 精度内一致而非逐位一致。

## 2026-11-16：EdgeSem 接入新图与重构；移除旧目录

- EdgeSem 移入顶层 `edgesem/` 包（schema、graph/（F4 = F3 + MOD_APPLY/CALL_SITE/GUARDS）、attributes/（74 位边属性）、pipeline、store、model/（关系物化、类型化初值、边感知 HGT、安慰剂、构建与校验）、train），读取 `data/hcg` 与 `data/dfg`，facts 由 `nodesem.facts` 从同一输入重算，不依赖 NodeSem 存储。七类两任务均可运行：`python -m edgesem build|train|report`，详见 edgesem/README.md。
- 训练沿用冻结的 P2：DFG 任务配置、patience 51（固定 50 轮）、严格最小内验证损失选 best；每折所有 profile 由该折构造种子下全新的 G3R 锚点派生（G3R、G3R-T、G4R、G4R-P、G3R-TA、G4R-A、G4R-Api、G4R-AC）。折、标签、节点 token 与 `dfg.train` 同一任务一致（hcg 标签；`--features anonymous` 仅替换 token，边属性始终原名视图）。EdgeSem 的 G3R 是其自身基线（`dfg.train` 的 G3R 由 G0 家族初始化）。
- 等价性：新图上 F4 边与旧 EdgeSem 代码逐条一致，并与封存 f4_v2 四个任务（重入/访问控制 × 节点/合约）按源码锚点与证据完全一致；重入/访问控制节点任务的边属性（31,372 / 21,830 行）与封存 ep6 逐位一致；7 个已训练 profile 的初始参数摘要与封存 EP7–EP9 一致（测试核对 fold 0 与 fold 9）。七类 14 个任务的新包输出与旧代码在新图上的输出一致（tests/edgesem/reference/old_code.json）。
- 发现并修复：networkx ≥ 3.5 的 `immediate_dominators` 不再包含起点，旧 EdgeSem 在新环境中计算支配位时会 KeyError（或把入口判为不自支配）；已补回根节点映射，与封存时的 networkx 2.6.3 语义一致，并加单元测试模拟新行为。
- 发现并修复（上一轮引入）：DFG 重构删除了 `scripts/DFG/dfg_v2/validate_slither.py`，但 compile_repair 仍延迟导入其中的编译器清点函数；所需 5 个函数已原样移至 `compile_repair/toolchain/inventory.py`。compile_repair 经旧别名导入的 frontend/ir 改为直接导入 `dfg.analysis`（同一模块对象）；`metadata_refs` 读取的注册表常量内联（数值不变）。
- 移除 `scripts/edge_sem`（含约 6 GB 封存产物）、`scripts/node_sem`、`scripts/DFG`（含别名映射与 dfg_v2）；全部保存在归档分支 `archive/pre-restructure-2026-11-15`。新主线的 hcg → dfg → nodesem → edgesem 只依赖重新生成的输出。
