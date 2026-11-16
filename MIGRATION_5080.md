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
