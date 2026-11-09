# NS-P8b / N-C2 操作说明

修改与实现：Codex，2026-11-09。

本批在原名 S4、冻结 G3R 图上增加按折训练的 STUDENT 向量。每任务外层折一个 CPU 学生，全部节点导出；HGT 的 S5 有30项，S8有30项条件任务。当前停在计划、初值和验收封存阶段，正式 HGT 拟合需要另行授权。

## 环境与已执行的准备命令

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES='' python -B -u -m scripts.node_sem.p8b_students
CUDA_VISIBLE_DEVICES='' python -B -u -m scripts.node_sem.p8b_prepare
```

两个入口拒绝覆盖已有目录。第一步封存学生训练输入并完成30个CPU学生；第二步只准备载体和HGT零步初值，不训练HGT。不得原地重复运行，也不得把准备过程当作HGT训练成绩。已批准的准备优化依据保存在 preparation_decisions.json，学生阶段原 decisions.json 不回写。

只读核验：

```bash
CUDA_VISIBLE_DEVICES='' python -B -c "from scripts.node_sem.batch_nc2 import load,DEFAULT; load(DEFAULT/'plan.json',deep=True)"
```

## 后续授权入口（当前未执行）

用户批准后，在 batch_NC2_v1 新建 execution_decisions.json，绑定 plan.json 的 path/SHA、jobs=60、view=original、用户原文、execution_authorized=true，以及当时实际的电源检查引用。jobs=60表示30项S5加最多30项条件S8，不表示无条件执行60次。不得改写原 authorization.template.json 或旧 seal。

启动前按原规则检查插电、禁睡眠/休眠、GPU设备及TF32、GPU锁和资源；有错误停止，不自动降配或重试。单次运行必须有新 execution_revision 与 authorization：

```bash
python -B -m scripts.node_sem.batch_nc2_controller seal
python -B -u -m scripts.node_sem.batch_nc2_controller run
python -B -m scripts.node_sem.batch_nc2_controller verify
```

后台运行应由独立会话启动、stdout/stderr保存到WSL产物目录；上述命令本身没有授权任何自动运行。S5顺序为重入节点10折、访问控制节点10折、访问控制合约5折、重入合约5折。全部30份S5收据通过后，只读取预登记的重入节点best外层BF1等权折均差；严格大于0才执行全体30项S8，否则明确跳过。不能按有利fold选择性补跑。

S8重新使用同折S5的全套初始参数及训练/模态dropout随机身份。S8的真实spec、特征manifest与checkpoint绑定仍独立保存；随机身份的复用仅影响随机流，不覆盖实际输入身份。学生向量在同任务、同折、同节点类型内置换，可能跨该折的文件分区；没有使用标签或outer_test教师进行学生拟合。

## 产物及边界

- student_plan.json / student_plan.seal.json：CPU学生输入和训练协议。
- students/<task>/fold_n/：state.npz、scaler.npz、逐轮诊断、S5/S8向量与manifest、置换映射；全部保留本地。
- plan.json / plan.seal.json：30项S5＋30项条件S8的固定矩阵。
- prepared/<task>/fold_n/{S5,S8}/：独立载体、spec、HGT零步initial.pt及核验记录。
- checks/ 与 regressions.json：回归、文档和历史冻结版本核验。
- student_diagnostics.csv / preparation_summary.json：学生诊断和准备结果。
- NS_P8B_REPORT.md：当前阶段说明；正式结果必须在授权训练和收据验收完成后另行汇总。

HGT训练核心复用 N-A 的 construct/run_core/verify_attempt；S8仅在构造后的新适配层中绑定S5的模态dropout种子身份。未修改旧 HGT、DFG、图、标签、划分、特征文件、训练配置或旧计划。

主比较为重入节点 S5−S4，best为主、last辅助，按冻结L-audit及分组内外层协议评分。另报告S5−S6；S6是经验参照，不是数学上限。S6−S4为零或负时，不解释“保留比例”。若运行S8，S5−S8与S5−S4共同做Holm校正，仍披露按结果触发S8的探索性选择。

最终实验将在显存充足服务器另建批次。本机RTX3050 4GiB只是开发限制，不将本机与服务器结果混合，不自动迁移或重跑。


## 执行状态更新（2026-11-09，Codex）

用户授权后，60次S5/S8已全部完成并验收，报告已生成。上文“未执行”描述保留为准备时历史记录。报告入口为python -B -m scripts.node_sem.nc2_reporting（CPU、只读输入，已有输出拒绝覆盖）；机器报告在batch_NC2_v1/reports，说明见NS_P8B_REPORT.md。4217项回归通过。未启动下一阶段。
