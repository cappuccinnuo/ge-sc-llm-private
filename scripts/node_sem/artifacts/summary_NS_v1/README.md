# NS-P9 复现与产物说明（Codex）

本轮只读汇总已有450次正式拟合；没有新增正式训练、模型推理、LLM调用或特征。原名original为主视图，四任务分别报告，best主、last辅。

## 执行环境

WSL Ubuntu22.04；mando Python3.7.12 / PyTorch1.8.1 / DGL0.6.1。
CPU执行，CUDA_VISIBLE_DEVICES为空；OMP/MKL线程数2。
TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64。
所有新产物留在WSL，未写入C盘模型/运行缓存。

## 本次有效命令

在仓库根目录执行：
    python -B -m scripts.node_sem.summary --out scripts/node_sem/artifacts/summary_NS_v1/collection_attempt3
    python -B -m scripts.node_sem.summary_cases
    python -B -m scripts.node_sem.summary_edges
    python -B -m scripts.node_sem.summary_report

命令拒绝覆盖已有目录/文件；不要在已完成目录上再次运行。这里记录的是本次实际有效阶段，不是要求再运行。需要复现时用独立root、依次执行全部阶段并保持阶段名称；report输出同样拒绝覆盖，先在独立工作树复现。

有效中间数据位于collection_attempt3、cases_attempt2、edge_review。正式机器表位于reports；NODESEM_REPORT.md位于scripts/node_sem根目录。根目录complete.json为最终完成记录；report_complete.json只对应报告生成阶段。

collection_attempt1_failure.json、collection_attempt2/failure.json、cases/failure.json保留开发期三处汇总器接入失败。失败没有触碰旧模型/图/标签/预测；不是正式训练失败或新seed。失败目录不作为有效结果。

## 核验

- 封存plan/seal、成功收据、报告引用、输入/事实来源逐一核SHA；缺失或不匹配拒绝。
- 来源四指标重复记录、等权均值和样本标准差按binary64逐位比较；原标签辅助行先按冻结validate_records保留规定四指标，来源额外混淆矩阵不参与格式比较。
- 900条主指标、660条重复引用；104条正例宽表与N-C1 104/N-C2 312条配对表一致。
- 21个持续FN和10个移除FP精确AST投影、原源码/图坐标分列；STATIC只解码既有245维，不重新生成。
- 图路径使用冻结materialize；原F3正向关系、G3R消息反向分别输出；不是可执行路径或因果证明。
- 保存原Holm家族和p值及SciPy1.7.3，不做新检验。
- 三套回归和冻结8H只读核验、354源码核验见verification。
- doc_check检查新报告及三份追加文档，旧前缀字节不变。

## 范围与限制

用户批准S3m标为未运行、S4-noG保持G0/零HGT层；不补训、不替代。
N-A历史权重删除事实不变，只能引用预测/收据；本轮不声称重载这些权重。
下一阶段候选为S0o/S2/S4/S5/S6，用户决定；不自动扩展模型、seed或漏洞。
最终服务器实验使用充足显存并另建批次；本机RTX3050显存只限制当前开发，结果不与服务器批次混合。

## 最终验证

新增最终只读入口：python -B -m scripts.node_sem.summary_verify；当前输出也排他创建。独立核对899份来源、节点fold/身份及旧文件前缀。最终回归1353+2653+223=4229项，通过；NS-P9新增12项测试。冻结8H354份计算源码不变。

主报告：[NODESEM_REPORT.md](../../NODESEM_REPORT.md)。所有来源清单见source_inventory.json；实验输出与合成单元测试分开计数。
