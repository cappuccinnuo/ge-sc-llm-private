# NS-P5：N-A原名计划封存（2026-11-03，Codex）

本轮只准备和验收，**正式训练0次**。240是后续待授权的新fit计划数量。完整决定、逐项实现与命令另见training_changes§84。

## 计划及产物

输入node-sem@042c3c77347f83347a057d074af2421e39f53739，PROMPTS r16 SHA为bab1c93501f47a03ef054e99f67de81977944fcddb354e1b3b9e35e4fb310ed6。最新r16和EXPERIMENT_POLICY的原名要求优先于旧共享段残留的匿名文字。

| 任务 | 折数 | 图 | 特征 | 新fit计划 |
|---|---:|---|---|---:|
| reentrancy_contract | 5 | G0/G3R | S0o/S1o/S2/S4 | 40 |
| access_control_contract | 5 | G0/G3R | S0o/S1o/S2/S4 | 40 |
| reentrancy_node | 10 | G0/G3R | S0o/S1o/S2/S4 | 80 |
| access_control_node | 10 | G0/G3R | S0o/S1o/S2/S4 | 80 |

四配置各60个任务，seed1。S0o是原名token ID经原linear；S1o是原名token经可学习嵌入；S2是原名CODE；S4是原名CODE+CTX+STATIC。载体维数512/513/257/760，含相应可用性位；STATIC是245维。

独立目录：`scripts/node_sem/artifacts/batch_NA_v1/`。新增batch_na.py、p5_prepare.py、tests/test_batch_na.py；不修改旧执行器或冻结算法。

- 32套载体和manifest，来源SHA及行身份核验。
- 240份独立零步初值，逐一CPU strict reload、文件SHA与tensor digest验收，optimizer_steps=0。
- 32组额外fresh fold1模型证明：复用未训练结构与新建模型所有参数逐位一致。
- 16组S0o/S1o原token逐位一致；S0o全部参数与对应8H零步状态一致，其他配置gcs/classify共同参数一致。
- 所有折的schema、canonical relation、train/val支持与固定图一致；dropout身份包含ntype。
- 准备加深度验收约52.6分钟；未初始化CUDA或执行前向。

plan SHA：`fa880ce2a7d97187c4805adb35189e323b4332e7cb8e9a77b21d2271bebf8cb2`。验证记录：verification.json、preparation_audit.json、ns_p5/final_check.json。240份PT和32份NPZ留在WSL，以SHA引用，不提交大文件、不另复制C盘。

## 冻结协议与解释边界

沿用8H的dfg-v2-grouped-nested-v1、8D分组折、L-audit、完整固定任务图前向与原监督。inner_val早停并按严格最低loss选best；outer_test仅训练后评分。best/last分开，节点按HCG节点评分。该内部外层评分不是独立外部测试，也不是旧paper_kfold同val选型和评分。

实际配置逐任务读取历史manifest，不统一覆盖学习率。主终点：重入节点/G3R/S4−S0o的L-audit best外层BF1；Holm四比较S4−S0o、S1o−S0o、S2−S0o、S4−S2。S*仅在G3R候选S1o/S2/S4中，以最低inner_val loss checkpoint的inner_val BF1，任务内折均值再四任务等权选择；同分较小载体，不能用outer_test选择或替换预登记S4。

按buggy_文件名前缀分层，成员划分不用标签，评分使用冻结标签。非SolidiFI节点正例只读核对为重入32、访问控制20，后续逐节点概率表及重入全部非SolidiFI误报均预登记。Wilson区间用于P/R，BF1点估计；节点相关性、折重叠与单seed限制必须披露。

**G0+S4仍含DFG生成的CTX/STATIC，不能称完全无DFG对照。** 交互项描述特征和图边进入模型的组合效果，不是纯语义因果贡献。原名CODE/CTX仍可能带注入名字线索；旧匿名8H分数只历史参考，不能充当本批原名配对基线。

## 批准事项与资源

用户批准登记本机RTX3050先导，最终服务器另建批次；批准先证明逐位一致，再复用32组未训练结构，但240份初值仍独立封存。decisions.json保留选择。

同一任务全部折、图和配置绑定同一设备/torch/CUDA/TF32。当前GPU为RTX3050 Laptop 4096MiB，torch1.8.1+cu111/CUDA11.1；matmul/cudnn TF32均true。P4b临时关闭TF32仅用于eval等价验收，不改正式训练默认设置。

240fit名义估算8.03–8.68小时，依据8H对应60fit实测、本轮构造时间及S4的1.1–1.5倍假设。**不是实测ETA或上限**：原名视图可能改变早停，S2没有完整耗时测量，系统占用/显存回退可能显著拖慢。

P4b已有单轮数据：节点S4 reserved1434/minfree321MiB；合约S4 2194/44、S1o2074/81MiB。单轮成功不保证完整训练稳定。local_dev_v1启动≥3000MiB，运行低空闲仅提醒；OOM/CUDA/非有限值/输入/checkpoint错误仍整批停止，不自动重试或降配。迁服务器必须另建整任务全部配置的比较批次，不能仅移动失败配置混用。

最终实验将按用户安排在显存充足服务器开展；当前4GiB限制仅为本机开发限制，服务器本轮未部署或实测。

## 验证与命令

846 NodeSem＋2653 DFG v2＋223原回归＝**3722通过，0失败、0跳过**，42条既有弃用警告。定向首轮38通过，后补3项已计入全量NodeSem，不重复计数。覆盖矩阵、篡改、输入SHA、runtime、设备/TF32混用、视图及未授权启动。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p5_prepare verify
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
CUDA_VISIBLE_DEVICES='' python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
```

prepare已执行，命令和exit记录在ns_p5/run_prepare.py、prepare_exit.json；排他目录拒绝覆盖，不应重复运行prepare。check-launch预期拒绝，是保护验收。旧8H只读load、生效354源码、旧P4的274文件及三文档字节前缀核验通过，UTF8/CJK检查通过。

当前authorization.template.json仍false，训练0次，无新F1。旧execution.py仅支持匿名S0/S1，本轮不改白名单；NS-P5A另绑正式worker和用户授权，不改当前seal。沿用NS-P1b显式runtime清单，共364源码归档，特征生产者由manifest绑定。未下载模型/重编码/编译/启动服务器或下一阶段。本地提交NS-P5，不自动推送。
