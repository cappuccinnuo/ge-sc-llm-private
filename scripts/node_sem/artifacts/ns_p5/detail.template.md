## 84. 2026-11-03 NodeSem NS-P5 N-A original plan (Codex)

本轮只准备和验收，**正式训练0次**。240是后续待授权的新fit计划数量。完整决定、逐项实现与命令另见training_changes§84。

### 84.1 计划及产物

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
- 准备加深度验收约@@MIN@@分钟；未初始化CUDA或执行前向。

plan SHA：`@@SHA@@`。验证记录：verification.json、preparation_audit.json、ns_p5/final_check.json。240份PT和32份NPZ留在WSL，以SHA引用，不提交大文件、不另复制C盘。

### 84.2 冻结协议与解释边界

沿用8H的dfg-v2-grouped-nested-v1、8D分组折、L-audit、完整固定任务图前向与原监督。inner_val早停并按严格最低loss选best；outer_test仅训练后评分。best/last分开，节点按HCG节点评分。该内部外层评分不是独立外部测试，也不是旧paper_kfold同val选型和评分。

实际配置逐任务读取历史manifest，不统一覆盖学习率。主终点：重入节点/G3R/S4−S0o的L-audit best外层BF1；Holm四比较S4−S0o、S1o−S0o、S2−S0o、S4−S2。S*仅在G3R候选S1o/S2/S4中，以最低inner_val loss checkpoint的inner_val BF1，任务内折均值再四任务等权选择；同分较小载体，不能用outer_test选择或替换预登记S4。

按buggy_文件名前缀分层，成员划分不用标签，评分使用冻结标签。非SolidiFI节点正例只读核对为重入32、访问控制20，后续逐节点概率表及重入全部非SolidiFI误报均预登记。Wilson区间用于P/R，BF1点估计；节点相关性、折重叠与单seed限制必须披露。

**G0+S4仍含DFG生成的CTX/STATIC，不能称完全无DFG对照。** 交互项描述特征和图边进入模型的组合效果，不是纯语义因果贡献。原名CODE/CTX仍可能带注入名字线索；旧匿名8H分数只历史参考，不能充当本批原名配对基线。

### 84.3 批准事项与资源

用户批准登记本机RTX3050先导，最终服务器另建批次；批准先证明逐位一致，再复用32组未训练结构，但240份初值仍独立封存。decisions.json保留选择。

同一任务全部折、图和配置绑定同一设备/torch/CUDA/TF32。当前GPU为RTX3050 Laptop 4096MiB，torch1.8.1+cu111/CUDA11.1；matmul/cudnn TF32均true。P4b临时关闭TF32仅用于eval等价验收，不改正式训练默认设置。

240fit名义估算@@LOW@@–@@HIGH@@小时，依据8H对应60fit实测、本轮构造时间及S4的1.1–1.5倍假设。**不是实测ETA或上限**：原名视图可能改变早停，S2没有完整耗时测量，系统占用/显存回退可能显著拖慢。

P4b已有单轮数据：节点S4 reserved1434/minfree321MiB；合约S4 2194/44、S1o2074/81MiB。单轮成功不保证完整训练稳定。local_dev_v1启动≥3000MiB，运行低空闲仅提醒；OOM/CUDA/非有限值/输入/checkpoint错误仍整批停止，不自动重试或降配。迁服务器必须另建整任务全部配置的比较批次，不能仅移动失败配置混用。

最终实验将按用户安排在显存充足服务器开展；当前4GiB限制仅为本机开发限制，服务器本轮未部署或实测。

### 84.4 验证与命令

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

### 84.5 实施选择与历史接口说明

本轮不是新增模型能力，而是将已通过NS-P4b验收的特征组合落实为不可变计划。S0o/S1o的token来自原图已封存原名视图，不从匿名特征反推；S2/S4取ns_p3/CURRENT所指accepted attempt_b2，STATIC245维，不使用旧243维产物。CURRENT内容另存不可变快照，以免将来移动指针破坏本批来源；PROMPTS与EXPERIMENT_POLICY也归档原始字节。

用户原答复分别为“登记本机先导批次，服务器另建批次（推荐）”和“先证明逐位一致，再复用未训练结构（推荐）”。第一项解决运行位置歧义，第二项避免240次重复图装配而不改变初始化。证明使用额外fresh fold1构造器、相同semantic seed和对应8H零步锚点，逐参数torch.equal；证明后每折仍独立生成state_dict、保存和CPU严格加载。没有使用旧训练结果初始化，也没有因某折支持少而重新选seed。

当前模型构造、监督、训练算法均沿用原实现；本轮没有任何optimizer step。构造器耗时按同组测量估算未来每fit装配时间，不把当前准备的结构复用误当作未来GPU训练内存共享。

原runtime“遍历所有Python”的文字在NS-P1b已被明确修订：RUNTIME_MODULES只列实际训练模块，producer在模态manifest绑定。本轮继续该已批准边界，并加入batch_na/p5_prepare两份源码，共364归档；不修改旧354冻结列表。read-only模式核对归档SHA，启动模式要求当前runtime一致，不通过修改旧seal迎合变化。

旧匿名执行器的白名单没有覆盖本批新配置，因此本轮只交付准备和核验入口；正式worker留NS-P5A，这是计划阶段与执行阶段的边界，不是假装旧参数已经可用。未来新增worker后必须独立绑定运行版本及授权；成功结果复用、失败attempt保留、初始化恢复等仍需正式执行器验收。

统计中的Wilson仅P/R沿用8C已批准规则，无需把不适用F1的区间硬套到BF1。原始正例计数从冻结label_views只读核验，未读取预测，也未修改特征。S*名称虽写inner_val best BF1，具体以已冻结“最低inner_val loss checkpoint的BF1”为准，不另挑最高BF1 epoch。

### 84.6 实际记录与未执行项

完整测试命令、退出码、warnings和耗时在ns_p5/{nodesem,dfg_v2,legacy}.json/.log；首次定向测试38通过，扩充后三套最终3722通过。准备前快照before.json记录三份文档字节数/SHA，文档完成后核对旧前缀完全不变；所有新中文通过doc_check --expect-cjk。

最终追加记录：准备@@MIN@@分钟，planSHA为@@SHA@@，名义运行估算@@LOW@@–@@HIGH@@小时。所有重产物留WSL且SHA引用，不复制至C盘。文档辅助写入曾因Windows命令长度限制和UNC直接写入受限未启动/未落盘；改用短ASCII脚本、Unicode转义写UTF8模板，没有影响准备进程、图、初值、测试或seal。

未执行240次训练、GPU前向、服务器部署、NS-P5A、额外模型下载/编码/编译、新关系或更多seed；不以计划完整声称实验完成。新授权模板execution_authorized=false，标签L-audit/seed[1]/original/local_dev_v1预填，run_location/user_request等待执行授权。按用户服务器意图和共享上下文本地提交NS-P5，未推送。
