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
