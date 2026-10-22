# 固定作者图上的标签上下文与合约读出诊断

实施与记录：Codex。2026-10-20（美国东部时间；产物 UTC 为 2026-10-21）。开发 HEAD：021a6f55ac9e3f94fc70feb441ff48b51b6a92ea。

本轮完成上一阶段推荐的两项低成本诊断：节点错误分层，以及已有合约 best 模型的读出检查。没有新 fit，没有改作者图、标签、特征、DDG/HGT、训练规则或旧结果。结论仍是 CV validation，节点仍按 HCG 节点计分。

## 1. 结论与下一步决定

1. 三个困难文件的主要节点错误与作者/公开端点参考分歧重合；同时仍有参考一致节点发生错误，不能将所有错误归为标签。
2. 新关系已改变合约概率，却未改变类别；本轮复放再次确认，不是汇总表误显示或模型未读取新图。
3. 所有合约漏报都有局部正向线性证据，但这种现象在绝大多数正确良性合约也存在。不能据此断言 mean 是唯一瓶颈，直接取最高分可能放大误报。
4. 重入漏报图比正确检出的漏洞图更小，不支持简单的“图太大所以均值稀释”解释。
5. 下一步候选仅保留一个合约注意力读出受控比较；原 DDG 关系冻结。详细方案 NEXT_STAGE_DESIGN.md，尚未实现或开始训练；不在现有 validation 上搜索 top-k/阈值/多个候选。

## 2. 新代码与运行范围

新增目录：scripts/DFG/experiments/readout_diagnostics/。

- core.py：捕获原最后一层 HGT 隐向量、真实 pool、真实 logits；验证行身份和均值；原后端 head 重放；float64 线性参考分解及独立数值残差。
- contract_readout.py：归档和输入核验、严格 checkpoint 重载、30 个 best 串行前向、逐文件及逐节点贡献导出、权重/梯度/输入保护。
- label_context.py：核验既有预测、五文件审计与来源 SHA，按参考一致/争议/未审计分层，保留 best/last 与作者 target。
- summarize.py：30 项完整矩阵、回执 SHA、分表与合并表身份验收；全体 TP/TN/FP/FN、文件配对变化、全部误判的最高三个节点示例。top3 仅用于展示，不生成新的预测。
- tests/test_core.py、tests/test_label_context.py：33 项定向回归。
- README.md：模块边界、实际执行命令及数值说明。

归档来源：overall_cv_v1、guard_extension_v1。HCG 是下载作者 CFG+CG 的本地复跑，HCG_DDG 为其上四类 DDG，GUARD 再追加 CONTROL_DEPENDENCE。不是论文原始分数。

## 3. 节点错误分层

60 个 node-fit 预测导出核验通过。59,238 条三配置 OOF 节点记录对应 19,746 个独立节点；其中五文件 1,127 节点已定点审查，353 节点有作者/公开端点投影分歧，另 18,619 节点保持 UNREVIEWED。两种参考一致也不代表语义真值已获认证。

表中依次是“参考一致 / 有争议 / 未审计”的错误数，全部按原作者 target 计错。

| 任务/权重 | HCG | HCG_DDG | GUARD |
| --- | --- | --- | --- |
| 重入 best | 55 / 199 / 174 | 55 / 199 / 175 | 55 / 199 / 169 |
| 重入 last | 9 / 214 / 61 | 9 / 215 / 122 | 11 / 215 / 77 |
| 访问控制 best | 6 / 125 / 80 | 7 / 125 / 84 | 5 / 125 / 84 |
| 访问控制 last | 2 / 134 / 95 | 5 / 134 / 197 | 7 / 134 / 193 |

GUARD 相对 DDG 的 best 重入错误 429→423，净减少 6 均来自未审计层，不能称“已核实干净标签上的改善”。访问控制 216→214，来自 parity_wallet_bug_2 的两个参考一致节点；未审计层净差为零但有不同文件之间的改善与退化。GUARD 访问控制 best 仍比 HCG 多 3 个错误。

| 困难文件 | 节点数 | best 错误 | 分歧节点上的错误 | 参考一致节点上的错误 |
| --- | ---: | ---: | ---: | ---: |
| 重入 buggy_18.sol | 424 | 252 | 197 | 55 |
| 访问控制 buggy_18.sol | 284 | 87 | 83 | 4 |
| 访问控制 buggy_26.sol | 143 | 42 | 42 | 0 |

三种配置在这三个文件上的上述 best 统计相同。同名文件按 cohort/source SHA 区分。它们的合约预测均为正确 TP；这里的困难是节点定位，不是合约漏检。

last 方向不稳定，表格完整保留，不能用较有利的 last 代替预定 best。公共 CSV 注入区间不等于已人工证明的最小漏洞语句；本轮既不修标签，也不把分歧直接归罪于作者。

## 4. 合约完整五折诊断

两个任务各五折、三配置，共 30 个已有 best，导出 768 条文件记录和 95,232 条节点贡献记录。每文件只使用其验证折模型。30 个模型的实际预测类别全部与历史导出一致，最大历史概率误差 1.1921e-7，小于固定 1e-5 要求。

HCG_DDG 和 GUARD 分别与 HCG 对比共 512 项，512 项概率变化、0 项类别变化。三配置均为：重入 TP66/TN68/FP3/FN5，访问控制 TP51/TN56/FP1/FN6。

以下局部正证据是当前合约分类头作用于上下文化节点隐向量后的参考分数，绝非独立节点漏洞预测。其公式为 `(w1-w0)·h_i+(b1-b0)`，包含共同 bias；归一化节点贡献则是 `(w1-w0)·h_i/N`，不含 bias，两者不要混淆。

| HCG 诊断 | 重入 | 访问控制 |
| --- | ---: | ---: |
| 漏报合约中存在正局部证据 | 5/5 | 6/6 |
| 正确良性合约中存在正局部证据 | 65/68 | 56/56 |
| 漏报平均节点数 | 14.60 | 51.17 |
| 正确检出漏洞合约平均节点数 | 181.26 | 145.16 |
| 漏报节点数中位数 | 13 | 14.5 |

GUARD 的“正局部证据”计数同样为 5/5、6/6、65/68、56/56。例：重入 simple_dao.sol 在 HCG 中有 11 个节点、4 个局部正分，局部最大约 6.715，但合约实际 margin 为 −1.442；GUARD 中仍 4 个局部正分，实际 margin 约 −1.460。因此改变关系和概率并不保证分类翻转。

全部 15 个不同误判文件已导出，不仅展示上述例子。重入漏报：modifier_reentrancy、reentrancy_bonus、reentrancy_simple、simple_dao、etherstore。访问控制漏报：parity_wallet_bug_2、phishable、FibonacciBalance、mycontract、multiowned_vulnerable、unprotected0。误报的完整地址文件见 analysis/all_graph_errors.csv。

参考正证据与负证据在 TP/TN/FP/FN 中普遍共存。不能从这次观察判定 pooling、表示质量、数据分布或优化中哪一个是唯一根因；不同配置已训练权重也不同，贡献差值不是纯新增边的因果效应。

## 5. 数值验收与保留的失败

attempt_001：首个 checkpoint 预测忠实，但把 float64 参考 margin 与 CUDA 实际结果直接作 1e-4 检查失败。失败文件、运行源码快照、float32_probe.json 均保留。快照与该次计划记录 SHA 一致。未覆盖该目录，未改变原模型或精度设置。

attempt_002 使用更准确的分层验证：

- 同设备、dtype、批量形状、权重与精度标志下，F.linear 重放与实际 logits 的 torch.equal：30/30。
- float64 节点参考贡献之和加独立 bias 与参考 margin 的最大误差：3.553e-15，要求 1e-10。
- 最大 pooling margin 残差：5.162e-7；最大 head 数值残差：8.0242e-4；两者之和单独核对。
- 旧逐 logit 容差失败 211/768、旧 margin 容差失败 330/768，全部记录，未隐藏。
- 参考/实际类别不一致：0/768。实际分类和正式概率仍由原 GPU logits 决定，未由双精度参考替换。

Torch1.8.1+cu111 的 matmul/cudnn allow_tf32 均为 true。未切换后端做精度对照，因此只把它记录为允许的精度环境，不单凭标志认定差异全部由 TF32 造成。实际 logits 约 ±1，探针不支持“大公共 logit 抵消”解释。

30 个目标 checkpoint 成功诊断之外，失败尝试和只读数值探针额外执行各 1 次模型前向；合计 32 次模型前向、0 次 fit/backward。原运行和后端 head 重放计数分开理解。

## 6. 测试、资源和保护

- 初版 27 tests 通过；增加诊断数值/历史概率/标签语义回归后 33 tests 全通过，0 失败、0 跳过，无测试 warning。
- logits 篡改、错误 pool、错误行字典、NaN/Inf、错标签/图摘要、重复或缺失身份等仍被拒绝，没有删除关键断言以让检查通过。
- 全量汇总核验 30 项任务矩阵、全部逐模型表 SHA 与合并表一致、768/95,232 身份数量通过。
- 30 次成功诊断含归档/哈希与导出耗时 670.16 秒；峰值 allocated 631.81 MiB、reserved 654 MiB。串行、无 OOM，无 CPU 替换。
- 权重 digest 未变、梯度为空、受保护输入/图/标签/源码/checkpoint SHA 前后未变；运行期间原计算版本不变。
- 本轮仅运行新增模块的定向测试，没有声称复跑全部历史 DDG 测试或完整训练。未运行 solc、新 seed、七类扩展、独立测试或新读出训练。

## 7. 交付文件

- label_context/{audit.json,aggregate.csv,per_file.csv,node_context.csv}
- contract_best/attempt_001/：保留失败与 runtime_snapshot。
- contract_best/attempt_002/{diagnostic_plan.json,archive_acceptance.json,summary.json,contract_files.csv,node_contributions.csv}，以及30组回执。
- analysis/{analysis.json,outcome_groups.csv,paired_file_changes.csv,all_graph_errors.csv,error_top_nodes.csv}
- tests_001.log、tests_002.log、contract_readout_001.log、contract_readout_002.log、summary_001.log、float32_probe.json。
- NEXT_STAGE_DESIGN.md：单一读出候选、2×2矩阵、未来条件成立时新增20次合约fit、复用验收和停止边界。候选尚无可运行训练参数。

报告对应本轮实际诊断；后续注意力读出是待检验假设，不承诺提升，也不能将尚未执行的20次写成已完成实验。