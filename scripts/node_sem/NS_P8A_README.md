# NS-P8a / N-C1 使用说明

本批是本机 RTX3050 上的 3B 教师向量试验。S6 在原名 S4（CODE、CTX、STATIC）上增加 TEACHER；只使用 G3R。四任务共30折，顺序固定为重入节点10折、访问控制节点10折、访问控制合约5折、重入合约5折。

## 当前阶段

2026-11-09：用户单独授权后，30/30次S6训练及最终报告已完成。原 `authorization.template.json` 仍为false，执行授权在独立authorization.json；旧模板、plan和seal不变。结果见NS_P8A_REPORT.md。以下准备与启动命令是历史执行说明，不能覆盖既有批次或重复训练。

## 输入与初始化

- 历史比较来自N-A的30个S4/G3R结果，按原收据SHA只读引用。已删除的best/last明确列为缺失；不声称能够重载历史权重。
- N-A的S4零步文件存在时核验SHA、身份和tensor digest，再逐张量复制全部共有参数。
- 文件缺失时仅允许用原 `node_sem.init`、原spec和8H零步锚点重建S4，并严格匹配旧计划的state digest；保存在本批新目录。摘要不符立即停止，不随机补建。
- 教师LayerNorm/投影是仅有的新参数，按现有语义种子规则初始化。共同参数完全一致不意味着训练轨迹一致：模态dropout种子含spec，S6也多一个模态。
- 载体1145维 = S4的760维 + 教师384维 + 存在位1维。缺失教师为零向量/存在位0，原节点不删除。
- 完整图、监督划分、L-audit、原名CODE/CTX/STATIC、HGT、训练配置保持冻结。LLM提示层的历史a_k映射不改变本批原名主输入。

## 准备与核验命令

在WSL项目目录和mando环境中：

~~~bash
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p8a_prepare prepare \
  --decisions scripts/node_sem/artifacts/ns_p8a_checks/decisions.json \
  --power scripts/node_sem/artifacts/ns_p8a_checks/power_check.json
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p8a_prepare verify
~~~

prepare拒绝覆盖既有目录，不可原地重跑；成功后只使用verify。原始命令、日志、收据和计划位于 `artifacts/ns_p8a_checks/` 与 `artifacts/batch_NC1_v1/`。

## 授权后的独立执行入口

先由用户明确授权30项N-C1训练，记录到新的execution_decisions文件，绑定最终plan SHA及新鲜电源检查；不得修改旧授权模板。随后才可执行：

~~~bash
python -B -m scripts.node_sem.batch_nc1_controller seal
python -B -u -m scripts.node_sem.batch_nc1_controller run
python -B -m scripts.node_sem.batch_nc1_controller verify
~~~

执行时必须清除CPU检查使用的 `CUDA_VISIBLE_DEVICES=''`。训练控制器需以独立后台进程启动，逐项使用原GPU锁和新进程，心跳写入controller_status。封存执行修订、回归门槛和授权缺一不可。不能将准备阶段的授权当作正式训练授权。

模型仍使用冻结construct/run_core/fit；没有50轮、学习率或早停覆盖。启动前空闲显存门槛沿用local_dev_v1，运行中低于100MiB只记录；OOM/数值/输入异常停止并保留attempt，不自动降配、换CPU或重试。已完成收据核验后复用。OOM后报告已有任务；受影响任务的S4和S6须在未来服务器新批次一起运行，不能单边换设备。

## 统计与停止位置

主比较只有重入节点的S6−S4、L-audit、best、10折BF1，采用既有双侧Wilcoxon/zsplit约定。四任务best/last分别描述，报告SolidiFI/非SolidiFI pooled TP/FP/FN/BF1，以及32/20个非SolidiFI正例的身份对齐概率。

是否建议进入NS-P8b只读两个预登记数值：重入节点折均BF1差、非SolidiFI pooled BF1差；任一严格大于0则建议继续，否则按资源决策停止。缺失值不可当作0。即使建议继续，也不自动启动学生阶段。这个规则不能证明学生数学上不可能改善；教师仅是经验参照。

最终实验计划在显存充足的服务器另建批次；本机4GiB是当前开发限制。两种设备结果不混合、不择优。本轮不推送GitHub，不自动运行NS-P8b。
