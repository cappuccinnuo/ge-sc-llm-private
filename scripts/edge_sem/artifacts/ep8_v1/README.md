# EP8 E-A 批次

原名为唯一主视图；N-anon-s 为预登记描述性敏感性视图，不进入 Holm 族。

- 原名：60 个新拟合，复用 EP7 的20个 G3R。
- 匿名：80 个新拟合，必须在主批完成验收后启动。
- 两任务均为节点任务、10折、seed1、P2完整50轮；best按最低inner_val loss选择，last为辅助。
- 初值准备可以在CPU后台运行；正式GPU拟合逐任务独立进程、串行，共用既有GPU锁。
- 最终实验将在显存充足的服务器开展；当前限制仅来自本机。

## 状态与依据

decisions.json / protocol_p2/registration.json：选择、独立登记和封存。
before.json：修改前源码、旧产物及三份文档前缀。
baseline_verification/：20个历史G3R只读验收。
cpu_tests_v1/：三套完整CPU回归；postfix_tests/及preparation_revision_v2/targeted_tests.json为后续定向验收。
preparation/：初次CPU准备，因已批准的效率优化主动停止，保留现场。
preparation_revision_v2/：原始批准、前后源码；preparation_attempt2/为续作目录。
preparation_index.json：仅在全部准备验收完成后创建，指向成功索引；不存在时表示尚未全部准备完毕。
primary/、sensitivity/：分别封存计划及后续执行授权；结果不得混合。
results/与EP8_REPORT.md：只在140新拟合与20历史结果全部核验后生成。

## 命令

所有命令在仓库根目录、mando环境运行，设置PYTHONDONTWRITEBYTECODE=1、OMP_NUM_THREADS=2、MKL_NUM_THREADS=2和既有TREE_SITTER_LIB_DIR。

准备（当前已启动；不要重复执行）：

    CUDA_VISIBLE_DEVICES='' python -B -m scripts.edge_sem.recon.ep8_run prepare --root scripts/edge_sem/artifacts/ep8_v1 --preparation-name preparation_attempt2

准备完成后封存：

    CUDA_VISIBLE_DEVICES='' python -B -m scripts.edge_sem.recon.ep8_run seal --root scripts/edge_sem/artifacts/ep8_v1

登记必须已提交；CPU验收通过且具备本批授权记录后：

    CUDA_VISIBLE_DEVICES='' python -B -m scripts.edge_sem.recon.ep8_run authorize --root scripts/edge_sem/artifacts/ep8_v1 --registration-commit COMMIT --request-file APPROVAL_JSON
    python -B -m scripts.edge_sem.recon.ep8_run run --root scripts/edge_sem/artifacts/ep8_v1

完成后只读验收：

    CUDA_VISIBLE_DEVICES='' python -B -m scripts.edge_sem.recon.ep8_run verify --root scripts/edge_sem/artifacts/ep8_v1
    CUDA_VISIBLE_DEVICES='' python -B -m scripts.edge_sem.recon.ep8_run frozen --root scripts/edge_sem/artifacts/ep8_v1

run会自动汇总；analyze只用于尚不存在results目录时的独立汇总。禁止覆盖已有结果。失败停止、保留现场、不自动重试、不降配、不自动进入EP9。

权重文件保存在本地，不作为普通Git文本产物上传；manifest记录其SHA和身份。当前训练结果尚未产生，不将CPU准备误称为正式训练完成。

后台衔接（先提交登记，绑定本轮EP8请求后启动一次）：

    python -B -m scripts.edge_sem.recon.ep8_run finish-preparation --root scripts/edge_sem/artifacts/ep8_v1 --registration-commit COMMIT --request-file APPROVAL_JSON

该入口等待准备进程结束，验收后封存和授权，再调用原run路径。followup_started/failure/complete记录可定位状态；不得重复运行。


## EP8 GitHub 同步快照（2026-11-12 06:01 UTC）

140项初值准备及CPU验收已完成，6组真实任务/剖面的快捷装配与完整装配逐位一致。两个计划分别封存为原名主批60次和匿名敏感性批80次。后台当前正在执行原名主批；本次固定快照收录11个已完成正式拟合，匿名批为0个。该数量仅表示快照时刻，不是EP8完成结论；最终报告尚未生成。

同步范围包括已提交的EP8实现、测试及文档，以及准备索引、初值身份摘要、独立计划/seal、执行授权和上述11次的完整文本收据、预测、指标与资源记录。逐份核对收据/seal、任务归属和所有收据产物SHA（含仅留本地的权重）；没有重训或修改运行代码。未完成attempt、活动日志和锁不纳入快照；pt权重/初值张量仍保留本地，不上传。明细见 scripts/edge_sem/artifacts/ep8_v1/github_sync_20261112T060127Z.json。

后台仍按原名60次验收后再执行匿名80次的既定顺序运行，失败停止，不自动重试。最终实验将在显存充足的服务器运行；当前资源限制仅来自本机，本次未更改模型、训练设置或批次身份。


## EP8 E-A 完成验收（2026-11-13 UTC）

训练与汇总均已完成：原名主批60/60、N-anon-s敏感性批80/80，另只读复用EP7原名G3R的20份结果，总计160份正式结果。两批complete、pipeline_complete与followup_complete均为passed=true，后台进程已退出；最终报告于2026-11-12 20:27 UTC生成。本节取代前文“仍在训练”的时点状态，不改历史记录。

结果采用节点级L-audit、10折seed1、P2完整50轮，best主终点、last辅助，不是合约级或论文同协议复现。原名G4R−G3R-T的best BF1：重入+0.0188pp、访问控制+0.3986pp；匿名分别+0.3083pp、+0.1328pp。重入H1两项均值均正，但原名H1原始p=0.1996767915，匿名描述性p=0.16015625；均不能宣称H1显著，Holm等待EP9的H2，匿名不进入检验族。访问控制last不保持全部优势。匿名nonSolidiFI重入G4R pooled best BF1=63.1579，低于G3R的72.7273和G4R-P的75.0000；不能以整体高分宣称困难样本或泛化已解决。

交付：scripts/edge_sem/EP8_REPORT.md；ep8_v1/results/内的逐折、均值、配对、零差折、错误变化、pooled混淆矩阵、SolidiFI分层及Wilson P/R区间、词法与两条无学习边规则、非SolidiFI逐节点、持续案例与资源表（JSON/CSV），以及封存summary。新增最终复核记录保存本轮完成链和报告SHA；已核验160份收据/seal、汇总表及分析/评分源码SHA。CPU执行 ep8_run frozen 成功，冻结源码、历史产物、旧_code_refs及文档前缀仍保持。此前340项EdgeSem、1353项NodeSem、2653项DFG回归及39项最终定向测试的证据保留；本次收尾只追加文档和验收记录，没有改变训练代码或重复拟合。

保留所有历史attempt和已批准调整。此处停止在EP8，不自动启动EP9；EP9视图安排等待用户确认。最终七类实验将另建显存充足的服务器批次，当前资源限制仅属于本机。权重保留本地，完成报告与收尾记录本地提交，尚未进行新的GitHub推送。
