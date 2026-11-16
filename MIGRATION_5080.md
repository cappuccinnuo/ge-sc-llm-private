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
