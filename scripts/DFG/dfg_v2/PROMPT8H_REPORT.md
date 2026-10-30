# Prompt 8H：执行器已接入，首个试点完成，缓存验收阻断（Codex）

本轮起点：dfg-v2@39801a87。批次：scripts/DFG/experiments/artifacts/dfg_v2/prompt8h_v1/。授权：L-audit、N-anon-s、seed=[1]、本机local_dev_v1，共170次正式拟合。

**当前状态：正式训练完成1/170；首个试点完整只读验收通过，但控制器创建验收缓存失败，整批已停止。没有自动重试，第二个试点及剩余169次均未启动，尚无完整矩阵或最终F1统计。**

## 1. 已实现范围

新增benchmark_v2执行器、协议分派、L-audit监督mask、checkpoint绑定、三次深度校验/快速输入检查、G0P模型适配、归档核验、验收工具、完整矩阵统计入口及测试。原DDG/HGT/tokenizer和旧训练脚本未修改；703个起始Python文件SHA一致。详细文件列表与实施选择见training_changes§70。

节点主监督使用C1，C2_include=false排除直接loss、best选择和主指标；被排除节点仍保留图内传播。原标签辅助结果覆盖全部原HCG节点。合约标签不变。G0P保留G0节点与特征，只添加零边canonical；无新增env_source。

## 2. 获批的两项调整

1. 旧8B.0运行清单拒绝任何新增Python文件，用户批准只读归档核验：逐项检查历史绑定源码、输入、修订、seal及150个收据；新执行器单独封存，旧入口不放宽。
2. CPU初始化准备耗时较长，用户批准先证明逐位一致，再复用从未训练的增强剖面结构。每折G0新建，四种增强剖面全部参数由未修改的initialize_family重写，G0P逐折新建；正式worker仍是独立进程并加载各自封存初值。

真实重入合约3折×5剖面共15项、5562张量/74068122参数值与原逐折新建参照逐位一致。acceptance/structure_reuse.json保存证据；参照权重只用于比较，没有加载进待生成模型。两次中止的CPU准备保留，新最终输出prepared_attempt3/。

## 3. 门槛与测试

- 150个旧结果归档核验通过。
- 原输入CPU新旧路径各2轮：loss、参数、optimizer、scheduler及预测逐位一致。
- GPU完整历史重入节点fold0 G0：best epoch及全部best/last分类一致。
- 真实节点三个分区的mask数值核验通过；被屏蔽位置的直接logit梯度为0，改变这些标签不改loss/选择/主指标。
- G0P一轮CPU冒烟：空关系梯度0、参数不变；前向分母证明限于同输入单层，不声称最终logits固定倍数。
- v2全套2614通过，9条既有警告；原回归223通过，29条既有警告。总2837唯一测试，0失败/跳过。新增41项定向测试已包含在2614内。
- 新旧训练入口共用.training.lock的回归通过，防止跨协议并行占GPU。
- 开发期CPU缺import、测试临时目录与同源fixture更正均有保留记录，未放宽关键断言。

## 4. 正式计划与首个试点

170份零步初值/30折已生成。新plan SHA：

cb8daf22ed9fb9cd81fe575548d338408a5420f62e7a6da529d402c148eb8a2c

首个正式fit：reentrancy_contract / fold0 / seed1 / G0。完成19轮，best为第12轮（zero-based=11），last为第19轮（zero-based=18）；inner_val/outer_test的best/last重载一致。无OOM，非有限数值错误未出现。完整只读verify_one再次通过，记录cache_failure_diagnosis.json。

资源：peak allocated=1230.8384MiB，peak reserved=1410MiB，整卡最小空闲=400MiB，memory_tight=false。精确训练耗时与资源原始证据在诊断JSON及final_result.json中。此处不提前汇总F1，也不把1个试点当作170结果。

## 5. 阻断根因与影响

新execution.fit_one在资源采样器仍运行时保留trainer写出的result.json；退出采样器后另写final_result.json。旧experiment/acceptance_cache.py::_dependencies固定读取result.json的raw_samples_sha256，同时又读取已完整写完的相邻memory_samples.jsonl，于是同一路径得到两个SHA，触发Conflicting or changing dependency。

- 中间result记录：b42367719a11c6dc88be383e0da78b7cd5cff6edbf0a5c35dbc0b64f4d44230a。
- final_result记录和实际完整日志均为：d37dcf6f805e1d4013f1dd25dde1f09d40dcc21707c6ae6f48a918e6d7c8bdd0。
- 这是新增缓存接入接口缺陷，与DDG语义、模型梯度或训练数值无关。
- worker成功收据已写入，完整验收通过；控制器失败，尚未生成pilots总验收或启动第二个fit。
- 既有测试覆盖监督/模型/输入/锁，但没有覆盖“真实异步资源采样结束后再创建旧缓存”的接口组合，这是本轮测试缺口。

保留原计划/seal、result/final_result、采样日志、worker/控制器日志、成功收据和停止状态。未覆盖任何历史文件，未自行重跑或改变冻结计算源码。

## 6. 待批准修复

已向用户提出：仅新增8H缓存依赖适配，使其读取final_result.json作为最终资源记录，继续校验全部收据文件及采样原文SHA；旧缓存不改。新增独立运行版本修订记录绑定旧plan/seal与新适配代码，保持模型、初值、数据、训练规则不变。补充真实日志接口回归、篡改拒绝检查，通过后复用首个已验收fit，再继续剩余169项。

截至本报告条目，该修复与恢复执行尚在等待确认；未实施新的运行版本、未重签旧seal、未重训首个试点。Prompt8H明确要求任何失败后停止并等用户确认。

## 7. 运行与未执行事项

已执行acceptance archive/cpu/gpu、real_acceptance、initial_preparation、execution prepare、execution pilots。实际命令见benchmark_v2/PROMPT8H_README.md和orchestration.command.json。pilots已在缓存步骤停止，不能直接重跑命令冒称恢复完成。

未执行：第二个正式试点、其余完整矩阵、170/170最终验收、G*选择、F1/配对统计、更多seed、其他五类、服务器训练。L-audit仍是诊断标签视图，不是已证明的ground truth；人工512/111依赖核验等既有范围限制未因此解决。

仅清理本批两个可重建pytest临时树，共466323719字节（444.72MiB）；重要日志、权重、初值及用户文件保留。产物位于WSL，不另写C盘。

最终正式实验按用户安排在显存充足服务器运行；当前本机RTX3050 4GiB只是开发资源限制。本次停止由缓存一致性错误引起，不是显存不足。
