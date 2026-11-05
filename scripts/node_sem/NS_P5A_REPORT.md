# NS-P5A：N-A 原名视图完整实验报告

本批是预先登记的本机 RTX3050 先导批次，默认 TF32 开启；正式训练 240/240、训练后注意力诊断 120/120 已验收。最终实验将按用户安排在显存充足服务器另建复现批次。本机 4GiB 是当前开发限制；两批不合并、不择优，结论不一致时都报告。

修改 AI：Codex。输入代码 HEAD：b7d8ef883e75b207f8655d1cd58469fc3938425c。

## 完成范围

- 四个任务，合约 5 折、节点 10 折；{S0o,S1o,S2,S4} × {G0,G3R}，seed=1，共 240 个独立正式 fit。两个先行 pilot 计入这 240 次。
- 原名特征，固定 L-audit 标签视图和分组嵌套划分；inner_val 选择严格最低 loss 的 best、执行早停；outer_test 只在训练后评分。完整固定图前向，不能称独立外部测试。
- 保留原图、DFG/HGT/tokenizer、标签、折、初值和训练配置；正式最多 50 轮，无单轮验收覆盖。best/last、折均值/pooled OOF、原标签辅助结果分别保存。
- 匿名 8H 只作零步初始化来源和历史参考，不复用匿名成绩作为原名配对基线。G0+S4 仍含 DFG 派生特征，不是完全无 DFG 的对照。

## 主结果

| 任务 | 图/配置 | best Buggy-F1 折均值（%） | 样本标准差 |
|---|---|---:|---:|
| access_control_contract | G0/S0o | 90.1781 | 6.3092 |
| access_control_contract | G0/S1o | 91.1359 | 2.9445 |
| access_control_contract | G0/S2 | 89.7036 | 4.7122 |
| access_control_contract | G0/S4 | 92.2245 | 3.3468 |
| access_control_contract | G3R/S0o | 91.8961 | 6.2196 |
| access_control_contract | G3R/S1o | 92.8750 | 2.3710 |
| access_control_contract | G3R/S2 | 92.9578 | 2.4789 |
| access_control_contract | G3R/S4 | 92.2245 | 3.3468 |
| access_control_node | G0/S0o | 99.3753 | 0.3460 |
| access_control_node | G0/S1o | 99.5401 | 0.2716 |
| access_control_node | G0/S2 | 99.2319 | 1.2344 |
| access_control_node | G0/S4 | 99.6358 | 0.2673 |
| access_control_node | G3R/S0o | 99.4998 | 0.2182 |
| access_control_node | G3R/S1o | 99.5388 | 0.2543 |
| access_control_node | G3R/S2 | 99.5595 | 0.2334 |
| access_control_node | G3R/S4 | 99.5074 | 0.3519 |
| reentrancy_contract | G0/S0o | 95.1016 | 5.2643 |
| reentrancy_contract | G0/S1o | 95.9080 | 1.4393 |
| reentrancy_contract | G0/S2 | 97.8818 | 3.1811 |
| reentrancy_contract | G0/S4 | 97.1921 | 2.9741 |
| reentrancy_contract | G3R/S0o | 94.9188 | 4.2129 |
| reentrancy_contract | G3R/S1o | 97.2414 | 1.5421 |
| reentrancy_contract | G3R/S2 | 97.2348 | 1.5550 |
| reentrancy_contract | G3R/S4 | 96.5977 | 2.3579 |
| reentrancy_node | G0/S0o | 99.4203 | 0.3418 |
| reentrancy_node | G0/S1o | 99.3952 | 0.4974 |
| reentrancy_node | G0/S2 | 99.7162 | 0.2609 |
| reentrancy_node | G0/S4 | 99.7435 | 0.2145 |
| reentrancy_node | G3R/S0o | 99.6247 | 0.2818 |
| reentrancy_node | G3R/S1o | 99.7894 | 0.2299 |
| reentrancy_node | G3R/S2 | 99.8265 | 0.1151 |
| reentrancy_node | G3R/S4 | 99.7721 | 0.1885 |

预登记主终点：重入节点 G3R，S4−S0o = **+0.1474 个百分点**；描述性 95% bootstrap 区间 [+0.0320, +0.2608]；10 折提升/持平/下降 = 8/0/2。
该比较 Wilcoxon 原始 p = 0.0371094，四项预登记 Holm 校正 p = 0.0742188。折间训练数据重叠，单 seed 不能证明独立重复或语义因果贡献。

S* = S2，只依据 inner_val 封存，作为参考，不替换预登记 S4。

## 验收与资源

- 32/32 载体及同种子模型逐位一致；6/6 非正式 CPU 验收 fit（1/2/2 轮两条路径），history、参数、Adam/调度器与预测一致。
- 单元回归 3759 通过，0 失败、0 跳过，42 条既有警告；37 项定向测试已包含其中。
- 240 个正式收据逐一校验输入/配置/初值/checkpoint/导出文件；设备类型与默认 TF32 一致；120 个 best checkpoint 注意力诊断均为 eval，无训练和权重修改。
- 正式 fit 累计墙钟 10.48 小时；最大 PyTorch allocated 1958.7 MiB、reserved 2386.0 MiB；所有任务中的最低整卡空闲 34.0 MiB；memory_tight 共 20 项。子阶段计时有重叠，不能相加。
- 正式失败记录 0 份，外部中断记录 0 份；失败现场保留，只允许已批准且原因确认的外部终止最多重跑一次。

## 决策与限制

用户批准先运行重入节点和合约两个正式 pilot，再补完剩余 39 个主比较 fit；只在新 execution_revision 中绑定顺序，旧 plan/seal 不变。
S0o 使用原 token；S1o、S2、S4 是已封存的特征配置，新增载体快路径只去除重复校验。正式训练仍调用冻结 trainer.fit，CPU 等价验收证明计算未改。
注意力统计逐关系/head，同时区分单邻居权重必为 1 与多邻居集中；N-A 没有门控配置，门控分布不适用。
SolidiFI/非 SolidiFI 分层是描述性分析；L-audit 不是已确立金标准。Wilson 区间只用于 Precision/Recall，BF1 报点估计。原名可能保留注入标记线索，不将分数解释为纯漏洞语义能力。
本轮没有运行 N-B、多 seed、匿名主实验、七类全量、服务器训练或新的图/模型扩展。没有自动 push。

## 文件与实际命令

主产物：scripts/node_sem/artifacts/batch_NA_v1/。reports/REPORT.md、report.json、best_fold_means.csv、last_fold_means.csv、paired.csv、pooled_oof.csv、errors.csv、nonSolidifi_nodes.csv、resources.csv，以及 prediction_changes.json、relation_support_gradients.json 保存明细。
execution_revision.json / authorization.json 单独绑定本轮；selection.json 在读取 outer 结果前封存。complete.json 与 attention/complete.json 是完整性索引。weights/NPZ 等重产物保留 WSL，不额外复制到 C 盘。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.p5a_acceptance carriers
CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.p5a_acceptance cpu
CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
CUDA_VISIBLE_DEVICES='' python -m scripts.node_sem.batch_na_controller seal
# seal 已存在，不能重复创建；实际 tmux 启动命令存于 launch.json
CUDA_VISIBLE_DEVICES=0 python -m scripts.node_sem.batch_na_controller run
```

完成后停止于 N-A 报告，未自动开启下一批。


## 2026-11-04 NS-P5A 收尾核验补充（修改 AI：Codex）

240次正式训练和120次注意力eval全部完成，失败/外部中断/重试均为0。独立收尾脚本已经生成报告及三文档最终记录，但本地提交在git diff --cached --check处退出：冻结CSV使用标准CRLF，Git默认将行末CR提示为trailing whitespace。使用仅本次命令的git -c core.whitespace=cr-at-eol diff --cached --check复查通过；未转换CSV、未修改训练/报告统计源码、旧seal或结果字节，也未重训。保留delivery_failure_295895.json和旧日志，另写delivery_recovery.json，再完成本地提交；不自动push。

结果解读：G3R上的S4相对S0o，重入合约/访问控制合约/重入节点/访问控制节点best折均BF1分别增加1.6789/0.3284/0.1474/0.0076个百分点。主终点重入节点8升2降，Holm p=0.07421875，不能声称通过0.05的校正显著性标准。仅CODE的S2在重入节点达到99.8265%，高于S4的99.7721%；inner_val选出的参考S*也是S2，因此现有证据未证明CTX+STATIC联合增强优于CODE。

非SolidiFI节点pool单列：重入S0o→S4为TP20→25、FP11→7、FN12→7，BF1 63.49%→78.13%；访问控制为TP0→2、FP3→10、FN20→18，BF1 0%→12.5%，仍然漏掉18/20个正例。总体99%以上不能等同真实来源文件已解决。该分层是小样本诊断，并非独立重复。best预登记主结果不因last更好而替换；重入节点last的S4−S0o为-0.0326个百分点，与best的小正向不同。
